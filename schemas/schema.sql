-- RAG System Database Schema
-- PostgreSQL 15+ with pgvector and pg_trgm extensions
-- This schema is idempotent - safe to run multiple times

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Article type enumeration
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'article_type') THEN
        CREATE TYPE article_type AS ENUM (
            'ANNOUNCEMENT',   -- Announcements, releases
            'EVENT_REPORT',   -- Event reports, study sessions
            'INTERVIEW',      -- Employee interviews
            'CULTURE'         -- Company culture, policies
        );
    END IF;
END$$;

-- Documents table for storing article chunks with embeddings
CREATE TABLE IF NOT EXISTS documents (
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
CREATE INDEX IF NOT EXISTS idx_embedding ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Trigram index for full-text similarity search
CREATE INDEX IF NOT EXISTS idx_content_trgm ON documents
    USING gin (content gin_trgm_ops);

-- Article type filter index
CREATE INDEX IF NOT EXISTS idx_article_type ON documents (article_type);

-- JSONB metadata index for flexible queries
CREATE INDEX IF NOT EXISTS idx_metadata ON documents USING gin (metadata);

-- Source file index for deduplication
CREATE INDEX IF NOT EXISTS idx_source_file ON documents (source_file);

-- RRF (Reciprocal Rank Fusion) score calculation function
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

-- Drop and recreate trigger to ensure it's up to date
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Useful view for document statistics by article type
CREATE OR REPLACE VIEW document_stats AS
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

-- =============================================================================
-- Style Profiles Table (Dify v3 compatible)
-- =============================================================================
-- Stores style profiles and excerpts for each article category
-- Profile type 'profile' contains the writing style rules
-- Profile type 'excerpt' contains sample excerpts for style reference

CREATE TABLE IF NOT EXISTS style_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_type article_type NOT NULL,
    profile_type VARCHAR(20) NOT NULL CHECK (profile_type IN ('profile', 'excerpt')),
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure only one 'profile' per article_type (excerpts can have multiple)
CREATE UNIQUE INDEX IF NOT EXISTS idx_style_profile_unique
    ON style_profiles(article_type)
    WHERE profile_type = 'profile';

-- Search index for article_type and profile_type filtering
CREATE INDEX IF NOT EXISTS idx_style_profiles_type
    ON style_profiles(article_type, profile_type);

-- Vector similarity index for excerpt search
CREATE INDEX IF NOT EXISTS idx_style_profiles_embedding
    ON style_profiles USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Trigger to update updated_at timestamp for style_profiles
DROP TRIGGER IF EXISTS update_style_profiles_updated_at ON style_profiles;
CREATE TRIGGER update_style_profiles_updated_at
    BEFORE UPDATE ON style_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comment on style_profiles table
COMMENT ON TABLE style_profiles IS 'Stores writing style profiles and excerpts for each article category';
COMMENT ON COLUMN style_profiles.profile_type IS 'Type of profile: "profile" for style rules, "excerpt" for sample text';
COMMENT ON COLUMN style_profiles.embedding IS 'Vector embedding for excerpt similarity search';

-- =============================================================================
-- Generated Articles Table
-- =============================================================================
-- Stores generated article history for recruiters to review and manage

CREATE TABLE IF NOT EXISTS generated_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_material TEXT NOT NULL,
    article_type article_type NOT NULL,
    generated_content JSONB NOT NULL,
    markdown TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for listing articles by creation date (most recent first)
CREATE INDEX IF NOT EXISTS idx_generated_articles_created_at
    ON generated_articles(created_at DESC);

-- Index for filtering by article type
CREATE INDEX IF NOT EXISTS idx_generated_articles_type
    ON generated_articles(article_type);

-- Comment on generated_articles table
COMMENT ON TABLE generated_articles IS 'Stores generated article history for review and management';
COMMENT ON COLUMN generated_articles.input_material IS 'Original input material provided by the user';
COMMENT ON COLUMN generated_articles.generated_content IS 'Generated article content as JSONB (titles, lead, sections, closing)';
COMMENT ON COLUMN generated_articles.markdown IS 'Complete article in Markdown format for preview';
