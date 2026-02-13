-- Migration: Add hybrid search support (vector + keyword)
-- This enables Reciprocal Rank Fusion for better retrieval

-- Update source_type to include exam_paper
ALTER TABLE knowledge_base 
DROP CONSTRAINT knowledge_base_source_type_check;

ALTER TABLE knowledge_base 
ADD CONSTRAINT knowledge_base_source_type_check 
CHECK (source_type IN ('textbook', 'question', 'diagram', 'exam_paper'));

-- Add tsvector column for full-text keyword search
ALTER TABLE knowledge_base 
ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;

-- Create GIN index for fast full-text search
CREATE INDEX knowledge_base_tsv_idx ON knowledge_base USING GIN(tsv);

-- Create style_profiles table to cache extracted style analyses
CREATE TABLE style_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_filename VARCHAR(255) NOT NULL,
    topic_keywords TEXT[],
    profile JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on source_filename for quick lookups
CREATE INDEX style_profiles_source_filename_idx ON style_profiles(source_filename);

-- Create index on topic_keywords for topic-based style retrieval
CREATE INDEX style_profiles_topic_keywords_idx ON style_profiles USING GIN(topic_keywords);

-- Add comment for documentation
COMMENT ON COLUMN knowledge_base.tsv IS 'Text search vector for keyword-based retrieval (hybrid search)';
COMMENT ON TABLE style_profiles IS 'Cached style profiles extracted from exam papers for psychometrician agent';