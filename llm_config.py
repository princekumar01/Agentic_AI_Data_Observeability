"""
llm_config.py
─────────────────────────────────────────────────────
Shared OpenAI LLM instances.  ALL agents import from here.
No agent may instantiate its own LLM.
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set. "
        "Copy .env.example → .env and add your key."
    )

# Primary LLM — used by data_quality, log_analysis, rca, recommendation agents
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.3,
    max_tokens=2048,
    api_key=_api_key,
)

# Fast LLM — used by compliance agent only
llm_fast = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    max_tokens=1024,
    api_key=_api_key,
)
