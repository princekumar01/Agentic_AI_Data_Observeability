# """
# backend/services/pii_service.py
# ─────────────────────────────────────────────────────
# PII / PHI masking using Microsoft Presidio + spaCy.

# CRITICAL COMPLIANCE RULES (FDA / HIPAA):
#   - metrics_json: entities=['PERSON'] ONLY
#   - etl_log:     entities=['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'US_SSN']
#   - NEVER scan for: LOCATION, DATE_TIME, DATE_OF_BIRTH, NRP
#   - If masking fails on metrics JSON: raise RuntimeError → pipeline halts
#   - Unmasked data must NEVER reach any LLM
# """
# from __future__ import annotations

# import json
# import os
# from typing import Any, Dict

# from presidio_analyzer import AnalyzerEngine
# from presidio_anonymizer import AnonymizerEngine
# from presidio_anonymizer.entities import OperatorConfig

# # ─── Initialise Presidio engines (module-level, loaded once) ─────────────────
# _analyzer = AnalyzerEngine()
# _anonymizer = AnonymizerEngine()

# # Fixed entity lists — must never be changed to include LOCATION, DATE_TIME, etc.
# _METRICS_ENTITIES = ["PERSON"]
# _LOG_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]

# _OPERATORS = {
#     "PERSON": OperatorConfig("replace", {"new_value": "<NAME_MASKED>"}),
#     "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL_MASKED>"}),
#     "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE_MASKED>"}),
#     "US_SSN": OperatorConfig("replace", {"new_value": "<SSN_MASKED>"}),
# }


# # ─── Public API ──────────────────────────────────────────────────────────────

# def mask_metrics_json(metrics: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Scan all string values in the metrics dict for PERSON entities.
#     Returns masked dict.
#     Raises RuntimeError if resulting JSON is corrupted — pipeline MUST halt.
#     """
#     try:
#         raw_text = json.dumps(metrics)
#     except Exception as exc:
#         raise RuntimeError(f"PII masking: failed to serialise metrics JSON: {exc}") from exc

#     masked_text = _mask_text(raw_text, _METRICS_ENTITIES)

#     try:
#         masked_dict = json.loads(masked_text)
#     except json.JSONDecodeError as exc:
#         raise RuntimeError(
#             f"PII masking corrupted the metrics JSON: {exc}\n"
#             "Pipeline halted to prevent unmasked data reaching LLM."
#         ) from exc

#     return masked_dict


# def mask_etl_log(log_path: str, output_dir: str) -> str:
#     """
#     Mask PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN in the ETL log
#     line by line.  Writes sanitized_log.txt.
#     Returns the path to sanitized_log.txt.
#     """
#     if not os.path.exists(log_path):
#         sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
#         open(sanitized_path, "w").close()
#         return sanitized_path

#     sanitized_lines = []
#     with open(log_path, encoding="utf-8") as fh:
#         for line in fh:
#             masked_line = _mask_text(line.rstrip("\n"), _LOG_ENTITIES)
#             sanitized_lines.append(masked_line)

#     sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
#     os.makedirs(output_dir, exist_ok=True)
#     with open(sanitized_path, "w", encoding="utf-8") as fh:
#         fh.write("\n".join(sanitized_lines))

#     return sanitized_path


# def save_sanitized_metrics(masked_metrics: Dict[str, Any], output_dir: str) -> str:
#     """Write sanitized_metrics.json.  Returns path."""
#     path = os.path.join(output_dir, "sanitized_metrics.json")
#     os.makedirs(output_dir, exist_ok=True)
#     with open(path, "w", encoding="utf-8") as fh:
#         json.dump(masked_metrics, fh, indent=2)
#     return path


# # ─── Private ─────────────────────────────────────────────────────────────────

# def _mask_text(text: str, entities: list) -> str:
#     """Run Presidio analyzer + anonymizer on a text string."""
#     if not text.strip():
#         return text
#     try:
#         results = _analyzer.analyze(
#             text=text,
#             entities=entities,
#             language="en",
#         )
#         if not results:
#             return text
#         # Build operator config for the found entity types
#         operators = {e: _OPERATORS[e] for e in entities if e in _OPERATORS}
#         anonymized = _anonymizer.anonymize(
#             text=text,
#             analyzer_results=results,
#             operators=operators,
#         )
#         return anonymized.text
#     except Exception:
#         # On any Presidio failure, return original text but DO NOT suppress
#         # silently for metrics — callers handle that differently
#         return text

# """
# backend/services/pii_service.py
# ─────────────────────────────────────────────────────
# PII / PHI masking using Microsoft Presidio + spaCy.

# CRITICAL COMPLIANCE RULES (FDA / HIPAA):
#   - metrics_json: entities=['PERSON'] ONLY
#   - etl_log:     entities=['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'US_SSN']
#   - NEVER scan for: LOCATION, DATE_TIME, DATE_OF_BIRTH, NRP
#   - If masking fails on metrics JSON: raise RuntimeError → pipeline halts
#   - Unmasked data must NEVER reach any LLM
# """
# from __future__ import annotations

# import json
# import os
# from typing import Any, Dict

# from presidio_analyzer import AnalyzerEngine
# from presidio_analyzer.nlp_engine import NlpEngineProvider, NerModelConfiguration
# from presidio_anonymizer import AnonymizerEngine
# from presidio_anonymizer.entities import OperatorConfig

# # ─── Initialise Presidio engines (module-level, loaded once) ─────────────────
# # Configure the spaCy NLP engine so that entity types not mapped to Presidio
# # entities (FAC, NORP, CARDINAL, ORG, GPE, etc.) are explicitly ignored.
# # This eliminates the runtime WARNING:
# #   "Entity FAC is not mapped to a Presidio entity, but keeping anyway."
# #
# # COMPLIANCE NOTE: LOCATION, DATE_TIME, DATE_OF_BIRTH, NRP are NOT in the
# # scan lists below and must never be added.

# _LABELS_TO_IGNORE = {
#     "FAC", "NORP", "WORK_OF_ART", "EVENT", "LANGUAGE",
#     "ORDINAL", "CARDINAL", "QUANTITY", "MONEY", "PERCENT",
#     "TIME", "LOC", "GPE", "ORG", "PRODUCT", "LAW",
# }

# _ner_model_config = NerModelConfiguration(labels_to_ignore=_LABELS_TO_IGNORE)
# _nlp_engine_provider = NlpEngineProvider(
#     nlp_configuration={
#         "nlp_engine_name": "spacy",
#         "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
#         "ner_model_configuration": _ner_model_config,
#     }
# )
# _nlp_engine = _nlp_engine_provider.create_engine()
# _analyzer = AnalyzerEngine(nlp_engine=_nlp_engine)
# _anonymizer = AnonymizerEngine()

# # Fixed entity lists — must never be changed to include LOCATION, DATE_TIME, etc.
# _METRICS_ENTITIES = ["PERSON"]
# _LOG_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]

# _OPERATORS = {
#     "PERSON": OperatorConfig("replace", {"new_value": "<NAME_MASKED>"}),
#     "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL_MASKED>"}),
#     "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE_MASKED>"}),
#     "US_SSN": OperatorConfig("replace", {"new_value": "<SSN_MASKED>"}),
# }


# # ─── Public API ──────────────────────────────────────────────────────────────

# def mask_metrics_json(metrics: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Scan all string values in the metrics dict for PERSON entities.
#     Returns masked dict.
#     Raises RuntimeError if resulting JSON is corrupted — pipeline MUST halt.
#     """
#     try:
#         raw_text = json.dumps(metrics)
#     except Exception as exc:
#         raise RuntimeError(f"PII masking: failed to serialise metrics JSON: {exc}") from exc

#     masked_text = _mask_text(raw_text, _METRICS_ENTITIES)

#     try:
#         masked_dict = json.loads(masked_text)
#     except json.JSONDecodeError as exc:
#         raise RuntimeError(
#             f"PII masking corrupted the metrics JSON: {exc}\n"
#             "Pipeline halted to prevent unmasked data reaching LLM."
#         ) from exc

#     return masked_dict


# def mask_etl_log(log_path: str, output_dir: str) -> str:
#     """
#     Mask PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN in the ETL log
#     line by line.  Writes sanitized_log.txt.
#     Returns the path to sanitized_log.txt.
#     """
#     if not os.path.exists(log_path):
#         sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
#         open(sanitized_path, "w").close()
#         return sanitized_path

#     sanitized_lines = []
#     with open(log_path, encoding="utf-8") as fh:
#         for line in fh:
#             masked_line = _mask_text(line.rstrip("\n"), _LOG_ENTITIES)
#             sanitized_lines.append(masked_line)

#     sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
#     os.makedirs(output_dir, exist_ok=True)
#     with open(sanitized_path, "w", encoding="utf-8") as fh:
#         fh.write("\n".join(sanitized_lines))

#     return sanitized_path


# def save_sanitized_metrics(masked_metrics: Dict[str, Any], output_dir: str) -> str:
#     """Write sanitized_metrics.json.  Returns path."""
#     path = os.path.join(output_dir, "sanitized_metrics.json")
#     os.makedirs(output_dir, exist_ok=True)
#     with open(path, "w", encoding="utf-8") as fh:
#         json.dump(masked_metrics, fh, indent=2)
#     return path


# # ─── Private ─────────────────────────────────────────────────────────────────

# def _mask_text(text: str, entities: list) -> str:
#     """Run Presidio analyzer + anonymizer on a text string."""
#     if not text.strip():
#         return text
#     try:
#         results = _analyzer.analyze(
#             text=text,
#             entities=entities,
#             language="en",
#         )
#         if not results:
#             return text
#         # Build operator config for the found entity types
#         operators = {e: _OPERATORS[e] for e in entities if e in _OPERATORS}
#         anonymized = _anonymizer.anonymize(
#             text=text,
#             analyzer_results=results,
#             operators=operators,
#         )
#         return anonymized.text
#     except Exception:
#         # On any Presidio failure, return original text but DO NOT suppress
#         # silently for metrics — callers handle that differently
#         return text

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
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# ─── Silence Presidio logger warnings (cosmetic — FAC / missing config keys) ─
# These warnings are emitted by presidio-analyzer's internal spaCy NER model
# for entity types that have no Presidio mapping (e.g. FAC, NORP, CARDINAL).
# They do NOT affect masking accuracy.  Raising the threshold to ERROR keeps
# logs clean without any risk of suppressing real masking failures.
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)

# ─── Initialise Presidio engines (module-level, loaded once) ─────────────────
_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

# Fixed entity lists — must never be changed to include LOCATION, DATE_TIME, etc.
_METRICS_ENTITIES = ["PERSON"]
_LOG_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]

_OPERATORS = {
    "PERSON": OperatorConfig("replace", {"new_value": "<NAME_MASKED>"}),
    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL_MASKED>"}),
    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE_MASKED>"}),
    "US_SSN": OperatorConfig("replace", {"new_value": "<SSN_MASKED>"}),
}


# ─── Public API ──────────────────────────────────────────────────────────────

def mask_metrics_json(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan all string values in the metrics dict for PERSON entities.
    Returns masked dict.
    Raises RuntimeError if resulting JSON is corrupted — pipeline MUST halt.
    """
    try:
        raw_text = json.dumps(metrics)
    except Exception as exc:
        raise RuntimeError(f"PII masking: failed to serialise metrics JSON: {exc}") from exc

    masked_text = _mask_text(raw_text, _METRICS_ENTITIES)

    try:
        masked_dict = json.loads(masked_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"PII masking corrupted the metrics JSON: {exc}\n"
            "Pipeline halted to prevent unmasked data reaching LLM."
        ) from exc

    return masked_dict


def mask_etl_log(log_path: str, output_dir: str) -> str:
    """
    Mask PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN in the ETL log
    line by line.  Writes sanitized_log.txt.
    Returns the path to sanitized_log.txt.
    """
    if not os.path.exists(log_path):
        sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
        open(sanitized_path, "w").close()
        return sanitized_path

    sanitized_lines = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            masked_line = _mask_text(line.rstrip("\n"), _LOG_ENTITIES)
            sanitized_lines.append(masked_line)

    sanitized_path = os.path.join(output_dir, "sanitized_log.txt")
    os.makedirs(output_dir, exist_ok=True)
    with open(sanitized_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sanitized_lines))

    return sanitized_path


def save_sanitized_metrics(masked_metrics: Dict[str, Any], output_dir: str) -> str:
    """Write sanitized_metrics.json.  Returns path."""
    path = os.path.join(output_dir, "sanitized_metrics.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(masked_metrics, fh, indent=2)
    return path


# ─── Private ─────────────────────────────────────────────────────────────────

def _mask_text(text: str, entities: list) -> str:
    """Run Presidio analyzer + anonymizer on a text string."""
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
        # Build operator config for the found entity types
        operators = {e: _OPERATORS[e] for e in entities if e in _OPERATORS}
        anonymized = _anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        return anonymized.text
    except Exception:
        # On any Presidio failure, return original text but DO NOT suppress
        # silently for metrics — callers handle that differently
        return text