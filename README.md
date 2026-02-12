# GenCertQuiz

A RAG-powered certification quiz generator that ingests textbook PDFs and generates exam-style questions using AI.

## Features

- 📚 **Multi-modal PDF Ingestion** - Extract text, images, and diagrams using Docling
- 🧠 **Dual-Path RAG** - Separate retrieval for factual content and question style
- 🎯 **Smart Question Generation** - Uses Claude AI with semantic deduplication
- 🗺️ **Interactive Mind Map** - Visual topic exploration interface
- 📝 **Exam Interface** - Full-featured quiz-taking experience
- 📤 **PDF Export** - Download generated question sets

## Quick Start

### Prerequisites

- Docker Desktop (for PostgreSQL)
- Python 3.11+
- Node.js 18+ (for frontend)
- OpenAI API key
- Anthropic API key (optional)

### 1. Start Database

```bash
docker-compose up -d
```

### 2. Configure Backend

```bash
cd backend
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Install Backend Dependencies

```bash
pip install -e .
```

### 4. Run Backend

```bash
python main.py
```

Backend will be available at http://localhost:8000

### 5. Verify Setup

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "database": "healthy"
}
```

## Project Structure

```
GenCertQuiz/
├── docker-compose.yml          # PostgreSQL + pgvector
├── migrations/                 # Database migrations
├── backend/                    # FastAPI backend
│   ├── main.py                # Application entry point
│   ├── models/                # Pydantic schemas
│   └── services/              # Business logic
└── frontend/                   # Next.js frontend (coming soon)
```

## Development Status

✅ Sprint 1: Foundation (COMPLETE)
- Docker Compose setup
- Database schema with pgvector
- FastAPI skeleton with health check

⏳ Sprint 2: Ingestion Pipeline (PENDING)
⏳ Sprint 3: RAG Core (PENDING)
⏳ Sprint 4: Frontend (PENDING)
⏳ Sprint 5: Production Ready (PENDING)

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT
