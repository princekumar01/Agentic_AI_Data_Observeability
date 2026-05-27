"""
backend/services/pii_service.py
─────────────────────────────────────────────────────
PII / PHI masking using Microsoft Presidio + spaCy.

CRITICAL COMPLIANCE RULES (FDA / HIPAA):
  - metrics_json: entities=['PERSON'] ONLY
  - etl_log:     entities=['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'US_SSN']
  - NEVER scan for: LOCATION, DATE_TIME, DATE_OF_BIRTH, NRP
  - If masking fails on metrics JSON: raise RuntimeError → pipeline halts
  - Unmasked data must NEVER reach any LLM

SAFE IMPLEMENTATION:
  - Recursively walks dict/list structure
  - Masks ONLY leaf string values
  - Never passes raw JSON structure into Presidio
  - Prevents JSON corruption issues
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


# ─── Presidio Engines ─────────────────────────────────────────────────────────

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()


# ─── Entity Configuration ────────────────────────────────────────────────────

# NEVER add LOCATION, DATE_TIME, DATE_OF_BIRTH, NRP

_METRICS_ENTITIES = ["PERSON"]

_LOG_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
]

_OPERATORS = {
    "PERSON": OperatorConfig(
        "replace",
        {"new_value": "<NAME_MASKED>"},
    ),
    "EMAIL_ADDRESS": OperatorConfig(
        "replace",
        {"new_value": "<EMAIL_MASKED>"},
    ),
    "PHONE_NUMBER": OperatorConfig(
        "replace",
        {"new_value": "<PHONE_MASKED>"},
    ),
    "US_SSN": OperatorConfig(
        "replace",
        {"new_value": "<SSN_MASKED>"},
    ),
}


# ─── Public API ──────────────────────────────────────────────────────────────

def mask_metrics_json(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively mask PERSON entities in all leaf string values.

    JSON structure itself is NEVER passed into Presidio,
    preventing JSON corruption issues.
    """

    try:
        masked = _mask_value_recursive(
            metrics,
            _METRICS_ENTITIES,
        )

    except Exception as exc:
        raise RuntimeError(
            f"PII masking failed during recursive processing: {exc}\n"
            "Pipeline halted to prevent unmasked data reaching LLM."
        ) from exc

    # Validate resulting structure is still serializable

    try:
        json.loads(json.dumps(masked))

    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"PII masking produced invalid JSON structure: {exc}\n"
            "Pipeline halted to prevent unmasked data reaching LLM."
        ) from exc

    return masked


def mask_etl_log(log_path: str, output_dir: str) -> str:
    """
    Mask PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN
    in ETL logs line-by-line.
    """

    os.makedirs(output_dir, exist_ok=True)

    sanitized_path = os.path.join(
        output_dir,
        "sanitized_log.txt",
    )

    if not os.path.exists(log_path):
        open(sanitized_path, "w").close()
        return sanitized_path

    sanitized_lines = []

    with open(log_path, encoding="utf-8") as fh:

        for line in fh:

            stripped = line.rstrip("\n")

            if stripped.strip():

                masked_line = _mask_text(
                    stripped,
                    _LOG_ENTITIES,
                )

            else:
                masked_line = stripped

            sanitized_lines.append(masked_line)

    with open(
        sanitized_path,
        "w",
        encoding="utf-8",
    ) as fh:

        fh.write("\n".join(sanitized_lines))

    return sanitized_path


def save_sanitized_metrics(
    masked_metrics: Dict[str, Any],
    output_dir: str,
) -> str:
    """
    Save sanitized metrics JSON file.
    """

    os.makedirs(output_dir, exist_ok=True)

    path = os.path.join(
        output_dir,
        "sanitized_metrics.json",
    )

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(masked_metrics, fh, indent=2)

    return path


# ─── Recursive Processing ────────────────────────────────────────────────────

def _mask_value_recursive(
    obj: Any,
    entities: list,
) -> Any:
    """
    Recursively walk:
      - dicts
      - lists
      - strings

    Only leaf string values are masked.
    """

    if isinstance(obj, dict):

        return {
            key: _mask_value_recursive(value, entities)
            for key, value in obj.items()
        }

    if isinstance(obj, list):

        return [
            _mask_value_recursive(item, entities)
            for item in obj
        ]

    if isinstance(obj, str):

        if obj.strip():
            return _mask_text(obj, entities)

        return obj

    return obj


# ─── Text Masking ────────────────────────────────────────────────────────────

def _mask_text(
    text: str,
    entities: list,
) -> str:
    """
    Run Presidio analyzer + anonymizer on plain text.
    """

    if not text.strip():
        return text

    try:

        results = _analyzer.analyze(
            text=text,
            entities=entities,
            language="en",
        )

        if not results:
            return text

        operators = {
            entity: _OPERATORS[entity]
            for entity in entities
            if entity in _OPERATORS
        }

        anonymized = _anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )

        return anonymized.text

    except Exception as exc:

        logger.error(
            "Presidio masking failed: %s",
            exc,
        )

        # STRICT COMPLIANCE FAILURE
        raise RuntimeError(
            f"PII masking failure: {exc}"
        ) from exc