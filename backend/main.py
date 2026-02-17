from contextlib import asynccontextmanager
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncpg
import os
from dotenv import load_dotenv
from pathlib import Path
import tempfile
import asyncio

from models.schemas import (
    HealthResponse,
    IngestResponse,
    QuestionRequest,
    QuestionResponse,
    QuestionResponseV2,
    GenerationMetadata,
    FilesResponse,
    StyleProfile,
    AnalysisResult,
    ExportRequest
)
from services.pdf_parser import PDFParser
from services.embedder import EmbeddingService
from services.vision import VisionService
from services.rag_engine import MultiAgentRAGEngine, RAGEngine
from services.pdf_exporter import PDFExporter
from services.style_analyzer import StyleAnalyzer

# Load environment variables
load_dotenv()

# Database connection pool
db_pool = None


import json

# ... (imports)

async def init_connection(conn):
    """Initialize database connection with JSON codec"""
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )
    await conn.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )

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
            command_timeout=60,
            init=init_connection
        )

        print("✓ Database connection pool created")
        
        # Check API Keys
        if not os.getenv("OPENAI_API_KEY"):
            print("! WARNING: OPENAI_API_KEY is not set")
        else:
            print("✓ OPENAI_API_KEY found")
            
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("! WARNING: ANTHROPIC_API_KEY is not set")
        else:
            print("✓ ANTHROPIC_API_KEY found")
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
    description="Multi-Agent RAG-powered certification quiz generator",
    version="0.2.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "disconnected"
    
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
        "version": "0.2.0",
        "docs": "/docs",
        "multi_agent": True
    }


@app.get("/files", response_model=FilesResponse)
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
                    COUNT(*) as chunk_count
                FROM knowledge_base
                WHERE metadata->>'filename' IS NOT NULL
                GROUP BY metadata->>'filename', source_type
                ORDER BY source_type, filename
                """
            )
            
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
            
            return FilesResponse(
                textbooks=textbooks,
                exam_papers=exam_papers
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve files: {str(e)}")


@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """
    Delete a file and all its associated data (chunks, embeddings, style profiles).
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with db_pool.acquire() as conn:
            # Delete from knowledge_base
            # CAST to text to ensure type matching if needed, though usually auto-cast works
            kb_result = await conn.execute(
                "DELETE FROM knowledge_base WHERE metadata->>'filename' = $1",
                filename
            )
            
            # Delete from style_profiles
            sp_result = await conn.execute(
                "DELETE FROM style_profiles WHERE source_filename = $1",
                filename
            )
            
            return {
                "message": f"Deleted {filename}",
                "details": {
                    "knowledge_base_chunks": kb_result.replace("DELETE ", ""),
                    "style_profiles": sp_result.replace("DELETE ", "")
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@app.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    source_type: str = Form("textbook")
):
    """
    Ingest a PDF file: parse, extract images, generate embeddings, and store.
    
    Args:
        file: PDF file to ingest
        source_type: Type of content ('textbook', 'question', 'exam_paper', or 'diagram')
    
    Note: For 'exam_paper' source type, a style profile will be automatically extracted
    and cached for use in question generation.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Validate source_type
    valid_types = ['textbook', 'question', 'exam_paper', 'diagram']
    if source_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Must be one of: {valid_types}"
        )
    
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
                pass
        
        # Step 3: Generate embeddings and store
        for chunk in parsed_data['chunks']:
            if 'metadata' not in chunk:
                chunk['metadata'] = {}
            chunk['metadata']['filename'] = file.filename
            
        embedder = EmbeddingService(db_pool)
        stats = await embedder.process_and_store(
            parsed_data['chunks'],
            source_type
        )
        
        # Step 4: If exam_paper, extract and cache style profile
        if source_type == 'exam_paper' and stats['chunks_stored'] > 0:
            try:
                style_analyzer = StyleAnalyzer(db_pool)
                await style_analyzer.analyze_exam_paper(file.filename)
            except Exception as e:
                print(f"Style analysis skipped: {e}")
        
        return IngestResponse(
            chunks_processed=stats['chunks_stored'],
            embeddings_created=stats['embeddings_generated'],
            images_processed=images_processed,
            message=f"Successfully ingested {file.filename} as {source_type}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/generate", response_model=List[QuestionResponse])
async def generate_questions(request: QuestionRequest):
    """
    Generate exam questions using the Multi-Agent RAG pipeline.
    
    This endpoint uses the three-agent architecture:
    1. Researcher: Extracts core facts from textbook
    2. Psychometrician: Drafts questions with style synthesis
    3. Critic: Quality gate with reflection and iteration
    
    Args:
        request: Question generation parameters
        
    Returns:
        List of generated questions
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        embedder = EmbeddingService(db_pool)
        rag_engine = MultiAgentRAGEngine(
            db_pool,
            embedder,
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
        )
        
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
        
        # Return in original format (strip multi-agent metadata)
        return [QuestionResponse(**q) for q in questions]
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/generate/v2", response_model=List[QuestionResponseV2])
async def generate_questions_v2(request: QuestionRequest):
    """
    Generate exam questions with full multi-agent metadata.
    
    Returns enhanced response including:
    - distractor_reasoning: Why each distractor was chosen
    - cognitive_level: recall/application/analysis/synthesis
    - quality_score: Critic agent's quality assessment
    - quality_checks: Detailed quality check results
    - source_references: Textbook sources used
    
    Args:
        request: Question generation parameters
        
    Returns:
        List of generated questions with full metadata
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        embedder = EmbeddingService(db_pool)
        rag_engine = MultiAgentRAGEngine(
            db_pool,
            embedder,
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
        )
        
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
        
        return [QuestionResponseV2(**q) for q in questions]
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/analyze-style/{filename}", response_model=AnalysisResult)
async def analyze_style_profile(filename: str):
    """
    Analyze an exam paper to extract its style profile.
    
    This endpoint analyzes the linguistic style, question patterns, and
    distractor structures of an uploaded exam paper. The extracted style
    profile is cached and used to guide future question generation.
    
    Args:
        filename: The filename of the exam paper to analyze
        
    Returns:
        Style profile with question stems, complexity, misconceptions, etc.
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        style_analyzer = StyleAnalyzer(db_pool)
        profile = await style_analyzer.analyze_exam_paper(filename, [filename])
        
        return AnalysisResult(
            source_filename=filename,
            chunk_count=profile.get('chunk_count', 0),
            profile=StyleProfile(**profile)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/export-pdf")
async def export_pdf(request: ExportRequest):
    """
    Generate PDF file from provided questions.
    
    Request body:
    - questions: List of question objects (required)
    - topic: string (required)
    - difficulty: string
    
    Returns:
    - PDF file download
    """
    try:
        exporter = PDFExporter()
        pdf_buffer = exporter.generate_pdf(request.questions, request.topic, request.difficulty)
        
        filename = f"{request.topic.replace(' ', '_')}_questions.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@app.post("/generate/stream")
async def generate_questions_stream(request: QuestionRequest):
    """
    Generate exam questions with real-time progress streaming using SSE.
    
    Returns a stream of JSON events:
    - {"type": "progress", "stage": "...", "message": "..."}
    - {"type": "question", "data": {...}}
    - {"type": "done"}
    - {"type": "error", "message": "..."}
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    async def event_generator():
        try:
            embedder = EmbeddingService(db_pool)
            rag_engine = MultiAgentRAGEngine(
                db_pool,
                embedder,
                similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
            )
            
            # Progress callback to report to stream
            async def progress_callback(stage: str, message: str):
                event = {
                    "type": "progress",
                    "stage": stage,
                    "message": message
                }
                yield f"data: {json.dumps(event)}\n\n"

            # Generate questions
            # Note: We need to iterate over the generator if generate_questions was a generator,
            # but here we are passing a callback to a regular async function.
            # To bridge the callback (which yields) with this generator, we need a different approach 
            # OR we can just rely on the fact that we can't easily yield from within the callback 
            # if the callback is just awaited.
            
            # Wait, the callback *cannot* yield to the outer generator directly.
            # I need to use an asyncio.Queue to bridge the callback and the generator.
            
            queue = asyncio.Queue()
            
            async def progress_callback_wrapper(stage: str, message: str):
                await queue.put({
                    "type": "progress",
                    "stage": stage,
                    "message": message
                })
            
            # Question callback to report to stream
            async def question_callback(question_data: Dict[str, Any]):
                 # Ensure all fields are present for V2 schema
                q_obj = QuestionResponseV2(**question_data)
                event = {
                    "type": "question",
                    "data": q_obj.model_dump()
                }
                await queue.put(event)

            # Run generation in a separate task
            task = asyncio.create_task(
                rag_engine.generate_questions(
                    topic=request.topic,
                    count=request.count,
                    difficulty=request.difficulty,
                    progress_callback=progress_callback_wrapper,
                    question_callback=question_callback
                )
            )
            
            # Consumer loop
            while not task.done():
                try:
                    # Wait for next event or task completion
                    # We use a timeout to check task status periodically if no events come
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield f"data: {json.dumps(event)}\n\n"
                    queue.task_done()
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    error_event = {"type": "error", "message": f"Stream error: {str(e)}"}
                    yield f"data: {json.dumps(error_event)}\n\n"
            
            # Check for exceptions in the task
            try:
                questions = await task
                if not questions:
                     # Only send error if NO questions were generated and it wasn't a partial success
                     # But generate_questions returns list, so if empty list, then error
                    error_event = {
                        "type": "error", 
                        "message": f"Could not generate questions for topic: {request.topic}"
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                else:
                    # Yield done event instead of list
                    done_event = {"type": "done"}
                    yield f"data: {json.dumps(done_event)}\n\n"
                    
            except Exception as e:
                error_event = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_event)}\n\n"
                
            # Yield any remaining events in queue
            while not queue.empty():
                event = queue.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_event = {"type": "error", "message": f"Server Error: {str(e)}"}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )