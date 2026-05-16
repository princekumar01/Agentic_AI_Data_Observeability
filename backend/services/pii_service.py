"""
pii_service.py
PII/PHI detection and masking using Microsoft Presidio.
Runs BEFORE any data is sent to the LLM layer.

Processes:
  1. Metrics JSON  → sanitized_metrics.json
  2. ETL log file  → sanitized_log.txt

If masking fails at any point, the pipeline halts.
PHI safety is non-negotiable.
"""

import os
import json
import logging
import re

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)

# Only these values should be masked in this project:
# - patient names
# - patient IDs such as P1038
#
# The previous broader Presidio entity list caused false positives on ordinary
# metric text such as "Rash", "KS=0.1000", and even UUID fragments.
_ENTITIES = ["PERSON"]
_PATIENT_ID_PATTERN = re.compile(r"\bP\d+\b")

# Lazy-initialise engines (spaCy model load is slow)
_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None


def _get_engines() -> tuple:
    global _analyzer, _anonymizer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


def _is_likely_patient_name(value: str) -> bool:
    """Keep PERSON detections focused on full names, not one-word clinical terms."""
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", value)
    return len(tokens) >= 2 and " " in value and not any(ch.isdigit() for ch in value)


def _find_sensitive_entities(text: str, analyzer: AnalyzerEngine) -> list[RecognizerResult]:
    """Return only actual patient names and patient IDs."""
    person_results = analyzer.analyze(text=text, entities=_ENTITIES, language="en")
    filtered_results = [
        result
        for result in person_results
        if _is_likely_patient_name(text[result.start:result.end])
    ]
    filtered_results.extend(
        RecognizerResult(
            entity_type="PATIENT_ID",
            start=match.start(),
            end=match.end(),
            score=1.0,
        )
        for match in _PATIENT_ID_PATTERN.finditer(text)
    )
    return filtered_results


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def mask_metrics_json(metrics: dict) -> dict:
    """
    Scan the Metrics JSON for PII/PHI and replace with anonymized tokens.

    The Metrics JSON should only contain aggregate stats (not raw patient rows),
    but this scan catches any accidental leakage from error messages or debug values.

    Args:
        metrics: Raw metrics dict from preprocessing.

    Returns:
        Sanitized metrics dict safe to pass to the AI layer.

    Raises:
        RuntimeError if masking fails (PHI safety is non-negotiable).
    """
    analyzer, anonymizer = _get_engines()

    try:
        metrics_str = json.dumps(metrics, default=str)
        results = _find_sensitive_entities(metrics_str, analyzer)

        if results:
            logger.warning(
                f"PII/PHI detected in Metrics JSON — {len(results)} entity/entities found. "
                f"Applying masking."
            )
            anonymized = anonymizer.anonymize(
                text=metrics_str,
                analyzer_results=results,
                operators={"DEFAULT": OperatorConfig("replace", {"new_value": "<MASKED>"})},
            )
            sanitized_str = anonymized.text
        else:
            logger.info("PII check on Metrics JSON: CLEAN — no entities detected.")
            sanitized_str = metrics_str

        return json.loads(sanitized_str)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Presidio masking corrupted Metrics JSON structure: {exc}. "
            f"Pipeline halted — manual PHI review required."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Presidio masking FAILED on Metrics JSON: {exc}. "
            f"Pipeline halted — PHI safety requires this step to succeed."
        ) from exc


def mask_etl_log(log_path: str, output_dir: str) -> str:
    """
    Scan the ETL log file line-by-line for PII/PHI.
    Masked output is saved as sanitized_log.txt.

    Args:
        log_path: Path to the raw etl_run.log file.
        output_dir: Run output directory.

    Returns:
        Path to the sanitized_log.txt file.

    Raises:
        RuntimeError if masking fails.
    """
    analyzer, anonymizer = _get_engines()
    sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
    sanitized_lines = []
    total_entities_found = 0

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()

        for i, line in enumerate(raw_lines):
            try:
                results = _find_sensitive_entities(line, analyzer)
                if results:
                    total_entities_found += len(results)
                    anonymized = anonymizer.anonymize(
                        text=line,
                        analyzer_results=results,
                        operators={
                            "DEFAULT": OperatorConfig(
                                "replace", {"new_value": "<MASKED>"}
                            )
                        },
                    )
                    sanitized_lines.append(anonymized.text)
                else:
                    sanitized_lines.append(line)
            except Exception as exc:
                logger.warning(
                    f"Presidio failed on log line {i+1}: {exc}. "
                    f"Dropping line for safety."
                )
                sanitized_lines.append(
                    f"[LINE {i+1} REDACTED — Presidio masking error]\n"
                )

        if total_entities_found > 0:
            logger.warning(
                f"PII/PHI detected in ETL log: {total_entities_found} total "
                f"entity occurrence(s) masked across {len(raw_lines)} lines."
            )
        else:
            logger.info(
                f"PII check on ETL log: CLEAN — no entities detected across "
                f"{len(raw_lines)} log lines."
            )

        with open(sanitized_path, "w", encoding="utf-8") as f:
            f.writelines(sanitized_lines)

        logger.info(f"Sanitized log saved to: {sanitized_path}")
        return sanitized_path

    except FileNotFoundError:
        raise RuntimeError(
            f"ETL log file not found at '{log_path}'. "
            f"Preprocessing may have failed to generate it."
        )
    except Exception as exc:
        raise RuntimeError(
            f"Presidio masking FAILED on ETL log: {exc}. "
            f"Pipeline halted — PHI safety requires this step to succeed."
        ) from exc


def save_sanitized_metrics(sanitized_metrics: dict, output_dir: str) -> str:
    """Save the sanitized Metrics JSON to disk."""
    path = os.path.join(output_dir, "sanitized_metrics.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sanitized_metrics, f, indent=2, default=str)
    logger.info(f"Sanitized metrics saved to: {path}")
    return path
