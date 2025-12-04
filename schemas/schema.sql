-- RAG System Database Schema
-- PostgreSQL 15+ with pgvector and pg_trgm extensions

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Article type enumeration
CREATE TYPE article_type AS ENUM (
    'ANNOUNCEMENT',   -- Announcements, releases
    'EVENT_REPORT',   -- Event reports, study sessions
    'INTERVIEW',      -- Employee interviews
    'CULTURE'         -- Company culture, policies
);

-- Documents table for storing article chunks with embeddings
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(768),  -- Vertex AI text-embedding-004 dimension
    article_type article_type NOT NULL,
    source_file TEXT,
    chunk_index INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector similarity index (IVFFlat for approximate nearest neighbor)
-- Note: For production with large datasets, consider HNSW index
CREATE INDEX idx_embedding ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Trigram index for full-text similarity search
CREATE INDEX idx_content_trgm ON documents
    USING gin (content gin_trgm_ops);

-- Article type filter index
CREATE INDEX idx_article_type ON documents (article_type);

-- JSONB metadata index for flexible queries
CREATE INDEX idx_metadata ON documents USING gin (metadata);

-- Source file index for deduplication
CREATE INDEX idx_source_file ON documents (source_file);

-- RRF (Reciprocal Rank Fusion) score calculation function
-- Formula: 1 / (rank + k) where k is typically 50-60
CREATE OR REPLACE FUNCTION rrf_score(rank bigint, rrf_k int DEFAULT 50)
    RETURNS numeric AS $$
    SELECT COALESCE(1.0 / ($1 + $2), 0.0);
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE;

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Useful view for document statistics by article type
CREATE VIEW document_stats AS
SELECT
    article_type,
    COUNT(*) as document_count,
    COUNT(DISTINCT source_file) as file_count,
    AVG(LENGTH(content)) as avg_content_length,
    MAX(created_at) as latest_created
FROM documents
GROUP BY article_type;

-- Comment on table and columns for documentation
COMMENT ON TABLE documents IS 'Stores article chunks with vector embeddings for RAG retrieval';
COMMENT ON COLUMN documents.embedding IS 'Vector embedding from Vertex AI text-embedding-004 (768 dimensions)';
COMMENT ON COLUMN documents.article_type IS 'Category of the article for type-specific retrieval';
COMMENT ON COLUMN documents.chunk_index IS 'Position of this chunk within the original document';
COMMENT ON COLUMN documents.total_chunks IS 'Total number of chunks the original document was split into';
COMMENT ON FUNCTION rrf_score IS 'Calculates Reciprocal Rank Fusion score for hybrid search';
