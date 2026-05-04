-- Run once on a Postgres database with pgvector installed (e.g. CREATE EXTENSION vector;).
-- Dimension must match your embedding model (1536 for OpenAI text-embedding-3-small default).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS service_code_embeddings (
    id                bigserial PRIMARY KEY,
    primary_svc_cd    text NOT NULL,
    servc_type        text,
    description       text NOT NULL,  -- was "Consumer-Friendly Description"
    title             text,             -- was "Consumer-Friendly Title"
    total_claim_count double precision NOT NULL DEFAULT 0,
    embedding         vector(1536) NOT NULL
);

-- After bulk load, create the ANN index (see scripts/load_faiss_into_pgvector.py).
-- If your embedding model is not 1536 dims, change vector(1536) to match faiss index .d

COMMENT ON TABLE service_code_embeddings IS 'Service catalog rows + embedding; loaded from FAISS + pickle via scripts/load_faiss_into_pgvector.py';
