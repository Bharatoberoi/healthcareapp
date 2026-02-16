import os
import faiss
import pickle
import pandas as pd
import numpy as np

from services.impl.llm_client import OpenAIEmbeddingClient

# ================= CONFIG =================
DATA_PATH = "data.csv"

FAISS_INDEX_PATH = "scm_index_v2.faiss"
FAISS_METADATA_PATH = "scm_metadata_v2.pkl"

TEXT_COL = "Consumer-Friendly Description"
EMBED_DIM = 1536  # OpenAI text-embedding-3-small
# =========================================

def main():
    # --------------------------------------------------
    # 1️⃣ Load cleaned dataset
    # --------------------------------------------------
    df = pd.read_csv(DATA_PATH)

    if TEXT_COL not in df.columns:
        raise ValueError(f"Missing column: {TEXT_COL}")

    texts = df[TEXT_COL].fillna("").astype(str).tolist()
    print(f"Loaded {len(texts)} rows for FAISS")

    # --------------------------------------------------
    # 2️⃣ Generate embeddings
    # --------------------------------------------------
    embed_client = OpenAIEmbeddingClient()

    vectors = []
    for i, text in enumerate(texts):
        vec = embed_client.embed(text)
        vectors.append(vec)

        if i % 50 == 0:
            print(f"Embedded {i}/{len(texts)}")

    embeddings = np.array(vectors).astype("float32")

    if embeddings.shape[1] != EMBED_DIM:
        raise ValueError("Embedding dimension mismatch")

    # --------------------------------------------------
    # 3️⃣ Build FAISS index (L2)
    # --------------------------------------------------
    index = faiss.IndexFlatL2(EMBED_DIM)
    index.add(embeddings)

    faiss.write_index(index, FAISS_INDEX_PATH)
    print(f"✅ FAISS index written to {FAISS_INDEX_PATH}")

    # --------------------------------------------------
    # 4️⃣ Save metadata PKL
    # --------------------------------------------------
    with open(FAISS_METADATA_PATH, "wb") as f:
        pickle.dump(df, f)

    print(f"✅ Metadata PKL written to {FAISS_METADATA_PATH}")

    print("\n🎉 FAISS + PKL rebuild complete")

if __name__ == "__main__":
    main()
