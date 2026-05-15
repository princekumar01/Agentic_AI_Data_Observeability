# llm_config.py
# ─────────────────────────────────────────────────────────────────────────────
# Configures the LLM using HuggingFace OpenAI-compatible endpoint via LangChain.
# All agents in this project import `llm` from this file.
# ─────────────────────────────────────────────────────────────────────────────

import os
from langchain_openai import ChatOpenAI


def _load_local_env(path: str = ".env") -> None:
    """Manually load .env file without requiring python-dotenv at import time."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

# ==========================================================
# 1. Load API Key
# ==========================================================
LLM_MODEL = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
HF_API_KEY = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")

if not HF_API_KEY:
    raise RuntimeError(
        "HuggingFace API key not found. "
        "Set HF_API_KEY or HF_TOKEN in your .env file or environment variables."
    )

os.environ["HF_TOKEN"] = HF_API_KEY

# ==========================================================
# 2. Primary LLM — used by all agents
# ==========================================================
llm = ChatOpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_API_KEY,
    model_name="meta-llama/Llama-3.1-8B-Instruct",
    temperature=0.5,
    max_tokens=2048,
    request_timeout=150,
)

# ==========================================================
# 3. High-capacity LLM — used for complex agents (RCA, Compliance)
# ==========================================================
llm1 = ChatOpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_API_KEY,
    model_name="openai/gpt-oss-120b",
    temperature=0.7,
    max_tokens=1024,
    request_timeout=120,
)

# ==========================================================
# 4. Quick connection test (run this file directly to verify)
# ==========================================================
if __name__ == "__main__":
    print("Testing LLM connection...")
    try:
        response = llm.invoke("Reply with: CONNECTION OK")
        print(f"LLM response: {response.content}")
        print("LLM configured successfully!")
    except Exception as e:
        print(f"LLM connection failed: {e}")
