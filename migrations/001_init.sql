-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create knowledge base table
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    source_type VARCHAR(20) CHECK (source_type IN ('textbook', 'question', 'diagram')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create vector similarity index
CREATE INDEX knowledge_base_embedding_idx ON knowledge_base 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index on source_type for filtering
CREATE INDEX knowledge_base_source_type_idx ON knowledge_base(source_type);

-- Create index on created_at for sorting
CREATE INDEX knowledge_base_created_at_idx ON knowledge_base(created_at DESC);
