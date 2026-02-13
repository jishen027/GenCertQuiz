from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncpg
import os
from dotenv import load_dotenv
from pathlib import Path
import tempfile
from models.schemas import HealthResponse, IngestResponse, QuestionRequest, QuestionResponse
from services.pdf_parser import PDFParser
from services.embedder import EmbeddingService
from services.vision import VisionService
from services.rag_engine import RAGEngine
from services.pdf_exporter import PDFExporter

# Load environment variables
load_dotenv()

# Database connection pool
db_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global db_pool
    
    # Startup: Create database connection pool
    database_url = os.getenv("DATABASE_URL")
    try:
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        print("✓ Database connection pool created")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        db_pool = None
    
    yield
    
    # Shutdown: Close database connection pool
    if db_pool:
        await db_pool.close()
        print("✓ Database connection pool closed")


# Create FastAPI application
app = FastAPI(
    title="GenCertQuiz API",
    description="RAG-powered certification quiz generator",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "disconnected"
    
    # Try to query the database
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="ok",
        database=db_status
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GenCertQuiz API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    source_type: str = "textbook"
):
    """
    Ingest a PDF file: parse, extract images, generate embeddings, and store.
    
    Args:
        file: PDF file to ingest
        source_type: Type of content ('textbook' or 'question')
    """
    if not db_pool:
        raise HTTPException(status_code=503, message="Database not available")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Step 1: Parse PDF
        parser = PDFParser()
        parsed_data = await parser.parse_pdf(tmp_path)
        
        # Step 2: Process images with vision service (if any)
        images_processed = 0
        if parsed_data['images'] and os.getenv("ANTHROPIC_API_KEY"):
            try:
                vision_service = VisionService()
                descriptions = await vision_service.batch_describe(
                    parsed_data['images'],
                    context=f"From {file.filename}"
                )
                
                # Add image descriptions as additional chunks
                for idx, desc in enumerate(descriptions):
                    parsed_data['chunks'].append({
                        'content': desc,
                        'metadata': {
                            'source': 'vision',
                            'image_index': idx,
                            'filename': file.filename
                        }
                    })
                images_processed = len(descriptions)
            except Exception as e:
                print(f"Warning: Failed to process images: {e}")
        
        # Step 3: Generate embeddings and store
        embedder = EmbeddingService(db_pool)
        stats = await embedder.process_and_store(
            parsed_data['chunks'],
            source_type
        )
        
        return IngestResponse(
            chunks_processed=stats['chunks_stored'],
            embeddings_created=stats['embeddings_generated'],
            images_processed=images_processed,
            message=f"Successfully ingested {file.filename}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/generate", response_model=List[QuestionResponse])
async def generate_questions(request: QuestionRequest):
    """
    Generate exam questions using RAG.
    
    Args:
        request: Question generation parameters
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Initialize services
        embedder = EmbeddingService(db_pool)
        rag_engine = RAGEngine(
            db_pool,
            embedder,
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
        )
        
        # Generate questions
        questions = await rag_engine.generate_questions(
            topic=request.topic,
            count=request.count,
            difficulty=request.difficulty
        )
        
        if not questions:
            raise HTTPException(
                status_code=404,
                detail=f"Could not generate questions for topic: {request.topic}"
            )
        
        return [QuestionResponse(**q) for q in questions]
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/export-pdf")
async def export_pdf(request: QuestionRequest):
    """
    Generate questions and export as PDF file.
    
    Request body:
    - topic: string (required)
    - difficulty: string (easy/medium/hard)
    - count: int (number of questions)
    
    Returns:
    - PDF file download
    """
    try:
        # Generate questions (reuse same logic as /generate)
        embedder = EmbeddingService(db_pool)
        rag_engine = RAGEngine(db_pool, embedder)
        
        questions = await rag_engine.generate_questions(
            topic=request.topic,
            count=request.count,
            difficulty=request.difficulty
        )
        
        if not questions:
            raise HTTPException(
                status_code=404,
                detail=f"Could not generate questions for topic: {request.topic}"
            )
        
        # Generate PDF
        exporter = PDFExporter()
        pdf_buffer = exporter.generate_pdf(questions, request.topic, request.difficulty)
        
        # Return as downloadable file
        filename = f"{request.topic.replace(' ', '_')}_questions.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
