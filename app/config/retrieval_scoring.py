# config/retrieval_scoring.py — thin compatibility layer over centralized settings

from app.config.settings import settings

FAISS_INDEX_PATH = settings.faiss_index_path
FAISS_METADATA_PATH = settings.faiss_metadata_path
TOP_K_RESULTS = settings.top_k_results
SEMANTIC_SIMILARITY_WEIGHT = settings.semantic_similarity_weight
CLAIM_VOLUME_WEIGHT = settings.claim_volume_weight
