"""
backend/services/token_tracking_service.py
─────────────────────────────────────────────────────
Per-agent token counting and cost estimation.
Cost formula: total_tokens / 1000 * 0.005  (GPT-4o rate).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

_GPT4O_COST_PER_1K = 0.005  # USD per 1000 tokens

_lock = Lock()


def count_tokens(text: str) -> int:
    """Approximate token count: words * 1.3."""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)


def record_token_usage(
    run_id: str,
    agent_name: str,
    input_text: str,
    output_text: str,
    output_dir: str,
) -> Dict:
    """Compute token counts, persist to token_usage.json, return the entry."""
    input_tokens = count_tokens(input_text)
    output_tokens = count_tokens(output_text)
    total_tokens = input_tokens + output_tokens
    estimated_cost = round(total_tokens / 1000 * _GPT4O_COST_PER_1K, 6)

    entry = {
        "run_id": run_id,
        "agent_name": agent_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    token_file = os.path.join(output_dir, "token_usage.json")

    with _lock:
        records = _load(token_file)
        records.append(entry)
        _save(token_file, records)

    return entry


def get_token_usage(run_id: str, output_dir: str) -> List[Dict]:
    token_file = os.path.join(output_dir, "token_usage.json")
    return _load(token_file)


# ─── Private ─────────────────────────────────────────────────────────────────

def _load(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(path: str, records: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)
    os.replace(tmp, path)
