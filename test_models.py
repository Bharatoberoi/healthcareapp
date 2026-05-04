import os
import time
import logging
from typing import Dict, Any
from openai import OpenAI
import requests
import google.generativeai as genai  # pip install google-generativeai

logger = logging.getLogger(__name__)

# API Keys (set in env)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Sample prompt for medical coding
TEST_PROMPT = """
You are a medical coding assistant. Given the query: "chiropractor visit for back pain"
Select the most appropriate CPT code from: 99213 (Office visit), 97110 (Therapeutic exercise), 98940 (Chiropractic manipulative treatment).
Return only the code.
"""

def test_openai_model(model: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"error": "No OpenAI key"}
    client = OpenAI(api_key=OPENAI_API_KEY)
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=50
        )
        latency = time.time() - start
        return {"response": response.choices[0].message.content, "latency": latency}
    except Exception as e:
        return {"error": str(e)}

def test_claude_model(model: str) -> Dict[str, Any]:
    if not ANTHROPIC_API_KEY:
        return {"error": "No Anthropic key"}
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    data = {
        "model": model,
        "max_tokens": 50,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
    }
    start = time.time()
    try:
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
        response.raise_for_status()
        latency = time.time() - start
        return {"response": response.json()["content"][0]["text"], "latency": latency}
    except Exception as e:
        return {"error": str(e)}

def test_gemini_model(model: str) -> Dict[str, Any]:
    if not GOOGLE_API_KEY:
        return {"error": "No Google key"}
    genai.configure(api_key=GOOGLE_API_KEY)
    client = genai.GenerativeModel(model)
    start = time.time()
    try:
        response = client.generate_content(TEST_PROMPT)
        latency = time.time() - start
        return {"response": response.text, "latency": latency}
    except Exception as e:
        return {"error": str(e)}

def test_deepseek_model(model: str) -> Dict[str, Any]:
    if not DEEPSEEK_API_KEY:
        return {"error": "No DeepSeek key"}
    # Assuming DeepSeek API similar to OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")  # Hypothetical
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=50
        )
        latency = time.time() - start
        return {"response": response.choices[0].message.content, "latency": latency}
    except Exception as e:
        return {"error": str(e)}

# Test all
models = {
    "OpenAI GPT-4o": ("gpt-4o", test_openai_model),
    "OpenAI GPT-4o-mini": ("gpt-4o-mini", test_openai_model),
    "Claude-3.5 Sonnet": ("claude-3-5-sonnet-20241022", test_claude_model),
    "Claude-3 Haiku": ("claude-3-haiku-20240307", test_claude_model),
    "Gemini 1.5 Pro": ("gemini-1.5-pro", test_gemini_model),
    "Gemini 1.5 Flash": ("gemini-1.5-flash", test_gemini_model),
    "DeepSeek-V3": ("deepseek-chat", test_deepseek_model),  # Adjust model name
}

results = {}
for name, (model, func) in models.items():
    print(f"Testing {name}...")
    results[name] = func(model)
    print(results[name])

print("\nResults:")
for name, res in results.items():
    print(f"{name}: {res}")