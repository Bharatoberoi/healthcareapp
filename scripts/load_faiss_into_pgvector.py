#!/usr/bin/env python3
"""
Load existing FAISS index + metadata pickle into PostgreSQL (pgvector).

Prerequisites:
  1. Postgres with pgvector (Cloud SQL, Neon, local Docker, etc.)
  2. Run ops/pgvector/schema.sql (adjust vector(N) if your index dimension differs)
  3. pip install psycopg[binary] pgvector
  4. Set DATABASE_URL, e.g. postgresql://user:pass@localhost:5432/dbname

Usage (from repo root):
  python scripts/load_faiss_into_pgvector.py

Uses the same row order as FAISS: vector i = index.reconstruct(i) pairs with metadata.iloc[i].
"""
from __future__ import annotations

import os
import re
import sys

# Repo root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import faiss  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tqdm import tqdm  # noqa: E402

CODE_COL = "primary_svc_cd"
TYPE_COL = "servc_type"
DESC_COL = "Consumer-Friendly Description"
TITLE_COL = "Consumer-Friendly Title"
CLAIM_COL = "total_claim_count"


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set DATABASE_URL to a postgresql:// connection string.", file=sys.stderr)
        sys.exit(1)

    from app.config.settings import settings

    index_path = settings.faiss_index_path
    meta_path = settings.faiss_metadata_path

    index = faiss.read_index(index_path)
    try:
        _ = index.reconstruct(0)
    except Exception as e:
        print(
            "This FAISS index does not support reconstruct(i). "
            "Use a flat index (e.g. IndexFlatL2) or export vectors from your index build.",
            e,
            file=sys.stderr,
        )
        sys.exit(1)

    meta = pd.read_pickle(meta_path)
    n_index = int(index.ntotal)
    n_meta = len(meta)

    if n_index != n_meta:
        print(
            f"Warning: FAISS ntotal ({n_index}) != metadata rows ({n_meta}). "
            "Rows will be loaded up to min(n_index, n_meta)).",
            file=sys.stderr,
        )
    n = min(n_index, n_meta)
    dim = int(index.d)

    print(f"Index: {index_path}  vectors={n_index}  dim={dim}")
    print(f"Metadata: {meta_path}  rows={n_meta}  loading={n}")

    import psycopg
    from pgvector.psycopg import register_vector

    conn = psycopg.connect(dsn, autocommit=True)
    register_vector(conn)

    def _embedding_column_dims(cur) -> tuple[int | None, str]:
        """Return (dimensions, format_type text) for public.service_code_embeddings.embedding."""
        cur.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod) AS ft
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = 'service_code_embeddings'
              AND c.relkind = 'r'
              AND a.attname = 'embedding'
              AND a.attnum > 0
              AND NOT a.attisdropped
            """
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return None, ""
        ft = str(row[0])
        m = re.search(r"vector\s*\(\s*(\d+)\s*\)", ft, re.I)
        if m:
            return int(m.group(1)), ft
        return None, ft

    with conn.cursor() as cur:
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        row = cur.fetchone()
        if not row:
            print("pgvector extension not found. Run: CREATE EXTENSION vector;", file=sys.stderr)
            sys.exit(1)

        declared_dim, col_type = _embedding_column_dims(cur)
        if declared_dim is None:
            print(
                f"Could not read embedding dimensions from DB (column type: {col_type!r}). "
                "Create public.service_code_embeddings with embedding vector(N) matching FAISS.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"DB column type: {col_type}  (parsed dim={declared_dim})")
        if declared_dim != dim:
            print(
                f"Table embedding dimension ({declared_dim}) != FAISS dim ({dim}). "
                "In Cloud SQL Studio, run DROP TABLE public.service_code_embeddings CASCADE; "
                "then CREATE with embedding vector(1536). Click Run (not only Validate). "
                "Ensure the Cloud SQL proxy points at the same instance as Studio.",
                file=sys.stderr,
            )
            sys.exit(1)

        cur.execute("DROP INDEX IF EXISTS idx_service_code_embeddings_hnsw")
        cur.execute("TRUNCATE service_code_embeddings RESTART IDENTITY")

    batch: list[tuple] = []
    BATCH = 500

    def flush():
        nonlocal batch
        if not batch:
            return
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO service_code_embeddings
                    (primary_svc_cd, servc_type, description, title, total_claim_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                batch,
            )
        batch = []

    for i in tqdm(range(n), desc="vectors"):
        vec = index.reconstruct(int(i))
        row = meta.iloc[i]
        code = str(row.get(CODE_COL, "") or "")
        stype = row.get(TYPE_COL)
        if pd.isna(stype):
            stype = None
        else:
            stype = str(stype)
        desc = row.get(DESC_COL, "")
        if pd.isna(desc):
            desc = ""
        else:
            desc = str(desc)
        title = row.get(TITLE_COL, "")
        if pd.isna(title):
            title = None
        else:
            title = str(title)
        claims = row.get(CLAIM_COL, 0.0)
        if pd.isna(claims):
            claims = 0.0
        else:
            claims = float(claims)

        batch.append((code, stype, desc, title, claims, np.asarray(vec, dtype=np.float32)))
        if len(batch) >= BATCH:
            flush()

    flush()

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE INDEX idx_service_code_embeddings_hnsw
                ON service_code_embeddings
                USING hnsw (embedding vector_l2_ops)
                WITH (m = 16, ef_construction = 64)
            """
        )

    conn.close()
    print("Done. HNSW index created on service_code_embeddings(embedding).")


if __name__ == "__main__":
    main()
