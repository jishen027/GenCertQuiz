from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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


@app.get("/files")
async def list_files():
    """
    Get list of uploaded files grouped by source type.
    Returns metadata about uploaded PDFs stored in the database.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT 
                    metadata->>'filename' as filename,
                    source_type,
                    MIN(metadata->>'page_number') as first_page,
                    COUNT(*) as chunk_count
                FROM knowledge_base
                WHERE metadata->>'filename' IS NOT NULL
                GROUP BY metadata->>'filename', source_type
                ORDER BY source_type, filename
                """
            )
            
            # Group by source type
            textbooks = []
            exam_papers = []
            
            for row in rows:
                file_info = {
                    "name": row['filename'],
                    "source_type": row['source_type'],
                    "chunks": row['chunk_count']
                }
                
                if row['source_type'] == 'textbook':
                    textbooks.append(file_info)
                elif row['source_type'] == 'exam_paper':
                    exam_papers.append(file_info)
            
            return {
                "textbooks": textbooks,
                "exam_papers": exam_papers
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve files: {str(e)}")


@app.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    source_type: str = Form("textbook")
):
    """
    Ingest a PDF file: parse, extract images, generate embeddings, and store.
    
    Args:
        file: PDF file to ingest
        source_type: Type of content ('textbook' or 'question')
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
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
        
        # Step 2: Process images with vision service (optional)
        images_processed = 0
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if parsed_data['images'] and anthropic_key and anthropic_key.startswith('sk-ant-'):
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
                # Silently skip image processing if it fails
                # This is optional functionality
                pass
        
        
        # Step 3: Generate embeddings and store
        # Inject document-level metadata (filename) into each chunk
        for chunk in parsed_data['chunks']:
            if 'metadata' not in chunk:
                chunk['metadata'] = {}
            chunk['metadata']['filename'] = file.filename
            
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
