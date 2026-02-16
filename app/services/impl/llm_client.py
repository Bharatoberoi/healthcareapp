# services/impl/llm_client.py

import os
from typing import List
from openai import OpenAI


# ============================================================
# OpenAI Embedding Client
# ============================================================
class OpenAIEmbeddingClient:
    """
    Uses OpenAI embeddings instead of Vertex AI.
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._model = model

    def embed(self, text: str) -> List[float]:
        response = self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding


# ============================================================
# OpenAI LLM Client (RAG + Selector)
# ============================================================

class OpenAILLMClient:
    def __init__(self, model_name: str):
        self._model_name = model_name
        # Always initialize OpenAI client for fallback/default use
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if "claude" in model_name.lower():
            self._delegate = ClaudeLLMClient(model_name)
        else:
            self._delegate = None

    def generate(self, prompt: str) -> str:
        if self._delegate:
            try:
                return self._delegate.generate(prompt)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Claude LLM failed, falling back to OpenAI: {e}")
                # Fallback to OpenAI logic below using a default OpenAI model
                # temporarily override model name for fallback
                fallback_model = "gpt-4o-mini"
            
        model_to_use = locals().get("fallback_model", self._model_name)
        
        response = self._client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": "You are a medical coding assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

# ============================================================
# Claude Haiku 4.5 Client (Anthropic)
# ============================================================
import requests
class ClaudeLLMClient:
    def __init__(self, model_name: str = "claude-haiku-4.5"):
        self._model_name = model_name
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        self._api_url = "https://api.anthropic.com/v1/messages"

    def generate(self, prompt: str) -> str:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": self._model_name,
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post(self._api_url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
