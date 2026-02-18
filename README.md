# 🎓 GenCertQuiz: Transform Textbooks into Professional Exams with Multi-Agent AI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)

> **Don't just read the textbook—master it.** GenCertQuiz uses a sophisticated RAG-powered Multi-Agent system to analyze your study materials and generate high-quality, exam-style quizzes that mimic real certification standards.

## 🌟 Why GenCertQuiz?
Most AI quiz generators just rephrase text. GenCertQuiz acts like a professional exam board:
- **The Researcher** deep-dives into facts.
- **The Style Analyzer** mimics the tone of specific exams (e.g., AWS SAA-C03).
- **The Critic** ensures no hallucinations and high academic rigor.

<div align="center">
  <img src="media/homepage.png" alt="Homepage"/>
</div>

## 🚀 Key Features

- **🤖 Multi-Agent RAG Pipeline**
  - **Researcher Agent**: Extracts core facts and definitions from uploaded textbooks.
  - **Style Analyzer**: Analyzes uploaded exam papers to extract question patterns, difficulty, and tone.
  - **Psychometrician Agent**: Drafts questions that combine factual accuracy with exam-style formatting.
  - **Critic Agent**: Reviews and refines questions to ensure quality and remove hallucinations.

- **📚 Content Management**
  - **PDF Ingestion**: Upload textbooks and exam papers (text & vision analysis).
  - **File Management**: View and delete uploaded files.
  - **Vector Search**: Semantic retrieval using `pgvector`.

- **📝 Interactive Quiz**
  - Generate quizzes with adjustable difficulty.
  - Real-time feedback and explanations.

## 🛠️ Tech Stack

- **Backend**: FastAPI, Python 3.11+, Pydantic AI Agents
- **AI/ML**: OpenAI GPT-4o, Anthropic Claude 3.5 Sonnet
- **Database**: PostgreSQL with `pgvector`
- **Frontend**: Next.js 14, React, Tailwind CSS, Lucide Icons
- **Infrastructure**: Docker Compose

## 🏗️ Architecture

```mermaid
graph TD
    User[User] -->|Uploads PDF| InpestAPI[Ingest API]
    User -->|Requests Quiz| GenAPI[Generate API]
    
    subgraph "Data Layer"
        Postgres[(PostgreSQL + pgvector)]
    end
    
    subgraph "Agentic RAG Engine"
        Researcher[Researcher Agent]
        StyleAnalyzer[Style Analyzer]
        Psychometrician[Psychometrician Agent]
        Critic[Critic Agent]
    end
    
    InpestAPI -->|Chunks & Embeds| Postgres
    InpestAPI -->|Extracts Style| StyleAnalyzer
    StyleAnalyzer -->|Caches Profile| Postgres
    
    GenAPI --> Researcher
    Researcher -->|Retrieves Facts| Postgres
    Researcher -->|Facts| Psychometrician
    
    StyleAnalyzer -->|Style Profile| Psychometrician
    
    Psychometrician -->|Drafts Question| Critic
    Critic -->|Feedback| Psychometrician
    Critic -->|Approved Question| User
```

## ⚡ Quick Start (Docker)

The easiest way to run the application is using Docker Compose, which handles the frontend, backend, and database.

### Prerequisites
- Docker & Docker Compose
- API Keys (OpenAI, Anthropic)

### 1. Configure Environment
Create a `.env` file in the `backend/` directory (or rely on the default `docker-compose.yml` mapping):

```bash
# Copy example env in backend
cp backend/.env.example backend/.env
# Edit backend/.env to add your API keys
```

### 2. Run with Docker Compose
```bash
docker-compose up --build
```

Access the application:
- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs

---

## 🛠️ Development Setup (Manual)

If you want to run services individually for development:

### 1. Database
```bash
docker-compose up -d db
```

### 2. Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # Add your API keys
uvicorn main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
