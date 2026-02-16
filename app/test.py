import pandas as pd
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer

# ============================================================
# CONFIG
# ============================================================

CSV_PATH = "data.csv"

FAISS_INDEX_OUT = "scm_index_v2.faiss"
METADATA_OUT = "scm_metadata_v2.pkl"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_CLAIM_RANK = 50

# ============================================================
# LOAD CSV
# ============================================================

print("Loading CSV...")
df = pd.read_csv(CSV_PATH)

# ------------------------------------------------------------
# COLUMN NAMES (from your CSV header)
# ------------------------------------------------------------

RAG_QUERY_COL = "RAG Query"
CONVO_COL = "Conversation Thread"
GROUND_TRUTH_COL = "Ground Truth"

# ------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------

required_cols = [RAG_QUERY_COL, CONVO_COL, GROUND_TRUTH_COL]
missing = [c for c in required_cols if c not in df.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}")

df = df.dropna(subset=[GROUND_TRUTH_COL]).reset_index(drop=True)

# ============================================================
# BUILD EMBEDDING TEXT
# ============================================================

def build_embedding_text(row):
    return f"{row[RAG_QUERY_COL]} {row[CONVO_COL]}".lower()

print("Preparing embedding text...")
df["embedding_text"] = df.apply(build_embedding_text, axis=1)

# ============================================================
# METADATA (MATCHES VALIDATOR)
# ============================================================

metadata = pd.DataFrame({
    "primary_svc_cd": df[GROUND_TRUTH_COL].astype(str),
    "consumer_friendly_description": "",
    "claim_volume_rank": DEFAULT_CLAIM_RANK,
    "servc_type": "PRIMARY_CARE"
})

# ============================================================
# EMBEDDINGS
# ============================================================

print("Loading embedding model...")
model = SentenceTransformer(EMBEDDING_MODEL_NAME)

print("Generating embeddings...")
embeddings = model.encode(
    df["embedding_text"].tolist(),
    normalize_embeddings=True,
    show_progress_bar=True
)

embeddings = np.array(embeddings).astype("float32")

# ============================================================
# BUILD FAISS INDEX
# ============================================================

print("Building FAISS index...")
dim = embeddings.shape[1]
index = faiss.IndexFlatIP(dim)
index.add(embeddings)

# ============================================================
# SAVE OUTPUTS
# ============================================================

faiss.write_index(index, FAISS_INDEX_OUT)

with open(METADATA_OUT, "wb") as f:
    pickle.dump(metadata, f)

# ============================================================
# DONE
# ============================================================

print("\n✅ FAISS rebuild complete")
print(f"Vectors indexed : {index.ntotal}")
print(f"Embedding dim  : {dim}")
print(f"FAISS file     : {FAISS_INDEX_OUT}")
print(f"Metadata file  : {METADATA_OUT}")
