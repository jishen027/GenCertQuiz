-- Migration 002: Add topics table
-- Topics extracted from textbooks via LLM

CREATE TABLE IF NOT EXISTS public.topics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_filename VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Prevent duplicate topics per file
CREATE UNIQUE INDEX IF NOT EXISTS topics_name_source_idx ON public.topics (name, source_filename);

-- Index for fast lookup by source file
CREATE INDEX IF NOT EXISTS topics_source_filename_idx ON public.topics (source_filename);
