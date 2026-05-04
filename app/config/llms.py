# config/llms.py — thin compatibility layer over centralized settings

from app.config.settings import settings

LLM_MODEL_NAME = settings.llm_model_name
RAG_MODEL_NAME = settings.llm_model_name
SERVICE_RESOLVER_MODEL_NAME = settings.llm_model_name
EMBEDDING_MODEL_NAME = settings.embedding_model_name
