# GenCertQuiz

A RAG-powered certification quiz generator that ingests textbook PDFs and generates exam-style questions using AI.

## Features

- 📚 **Multi-modal PDF Ingestion** - Extract text, images, and diagrams using Docling
- 🧠 **Dual-Path RAG** - Separate retrieval for factual content and question style
- 🎯 **Smart Question Generation** - Uses **OpenAI GPT-4o** for high-quality question generation
- 👁️ **Vision Analysis** - Uses **Claude 3.5 Sonnet** for understanding diagrams and charts
- ⚡ **Optimized Search** - Semantic deduplication and pgvector-based retrieval
- 📝 **Exam Interface** - Full-featured quiz-taking experience
- 📤 **PDF Export** - Download generated question sets

## Quick Start

### Prerequisites

- Docker Desktop (for PostgreSQL)
- Python 3.11+
- Node.js 18+ (for frontend)
- OpenAI API key
- Anthropic API key (optional, for vision features)

### 1. Start Database

```bash
docker-compose up -d
```

### 2. Configure Backend

```bash
cd backend
cp .env.example .env
# Edit .env and add your API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY)
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

### 5. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:3000

### 6. Verify Setup

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
│   ├── main.py                 # Application entry point
│   ├── models/                 # Pydantic schemas
│   └── services/               # Business logic (RAG, Vision, Embedding)
└── frontend/                   # Next.js frontend
```

## Development Status

✅ **Foundation** (COMPLETE)
- Docker Compose setup & Database schema with pgvector
- FastAPI skeleton with health check

✅ **Ingestion Pipeline** (COMPLETE)
- PDF Parsing & Text Chunking
- OpenAI Embedding Generation
- Vector Storage

✅ **RAG Core** (COMPLETE)
- Dual-path retrieval (Facts + Style)
- GPT-4o Question Generation
- Semantic Deduplication

✅ **Frontend** (COMPLETE)
- Next.js Application
- File Upload & Management
- Quiz Interface

⏳ **Production Ready** (IN PROGRESS)
- Comprehensive Testing
- CI/CD Pipelines
- Deployment Optimization

## API Documentation

Once the backend is running, visit:

## License

MIT
