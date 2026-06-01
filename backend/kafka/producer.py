"""
backend/kafka/producer.py
─────────────────────────────────────────────────────
Hospital API Simulator — Kafka producer.

Can be invoked:
  1. As CLI entry-point from the Docker simulator container:
     python -m backend.kafka.producer --mode csv --kafka-servers kafka:29092 --delay-ms 50

  2. Programmatically via run_hospital_api_simulator().

The KAFKA_BOOTSTRAP_SERVERS env var controls whether to use kafka:29092
(inside Docker) or localhost:9092 (host machine direct).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Normalise a raw data row into the 10-column Kafka event schema ───────────

def _build_event(row: Dict[str, Any], run_id: str, source: str) -> Dict[str, Any]:
    from backend.services.null_detection import (
        get_record_field,
        normalize_record_columns,
        preserve_optional_float,
        preserve_optional_int,
        preserve_optional_str,
    )

    row = normalize_record_columns(row)

    return {
        # Required data columns — preserve JSON null for missing values
        "patient_id": preserve_optional_str(get_record_field(row, "patient_id")),
        "patient_name": preserve_optional_str(get_record_field(row, "patient_name")),
        "age": preserve_optional_int(get_record_field(row, "age")),
        "gender": preserve_optional_str(get_record_field(row, "gender")),
        "diagnosis": preserve_optional_str(get_record_field(row, "diagnosis")),
        "treatment_group": preserve_optional_str(get_record_field(row, "treatment_group")),
        "visit_date": preserve_optional_str(get_record_field(row, "visit_date")),
        "glucose_level": preserve_optional_float(get_record_field(row, "glucose_level")),
        "side_effects": preserve_optional_str(get_record_field(row, "side_effects")),
        "severity": preserve_optional_str(get_record_field(row, "severity")),
        # Metadata
        "event_id": str(uuid.uuid4()),
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "run_id": run_id,
    }


# ─── Data-source loaders ─────────────────────────────────────────────────────

def _load_csv(csv_path: str) -> List[Dict[str, Any]]:
    import pandas as pd  # type: ignore
    df = pd.read_csv(csv_path, on_bad_lines="skip")
    df.columns = [c.lower().strip() for c in df.columns]
    return df.where(pd.notnull(df), None).to_dict(orient="records")


def _load_synthetic(scenario: str, rows: int) -> List[Dict[str, Any]]:
    """Import and call generate_synthetic_data."""
    try:
        # Running inside Docker: scripts is at /app/scripts
        sys.path.insert(0, "/app")
        from scripts.generate_synthetic_data import generate_dataset  # type: ignore
    except ImportError:
        # Running on host
        from scripts.generate_synthetic_data import generate_dataset  # type: ignore
    return generate_dataset(scenario=scenario, rows=rows)


def _load_external_api(
    url: str,
    api_key: Optional[str],
    max_records: int,
    auth_type: str = "Bearer",
) -> List[Dict[str, Any]]:
    import requests  # type: ignore
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    safe_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    logger.info(
        "[Producer] Calling external API | url=%s auth_type=%s max_records=%s",
        safe_url,
        auth_type,
        max_records,
    )
    headers = {}
    if api_key:
        if auth_type == "API Key":
            headers["X-API-Key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    logger.info("[Producer] External API response received | status=%s", resp.status_code)
    body = resp.json()
    if isinstance(body, list):
        return body[:max_records]
    for key in ("data", "results", "records", "patients"):
        if key in body and isinstance(body[key], list):
            return body[key][:max_records]
    return [body]


def _load_synthea(synthea_url: str, max_records: int) -> List[Dict[str, Any]]:
    import requests  # type: ignore
    resp = requests.get(f"{synthea_url}/fhir/Patient", timeout=15)
    resp.raise_for_status()
    bundle = resp.json()
    entries = bundle.get("entry", [])[:max_records]
    rows = []
    for entry in entries:
        resource = entry.get("resource", {})
        rows.append({
            "patient_id": resource.get("id", str(uuid.uuid4())),
            "patient_name": _fhir_name(resource),
            "age": _fhir_age(resource),
            "gender": resource.get("gender", "unknown"),
            "diagnosis": "Unknown",
            "treatment_group": "Control",
            "visit_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "glucose_level": 100.0,
            "side_effects": "None",
            "severity": "Low",
        })
    return rows


def _fhir_name(resource: Dict) -> str:
    names = resource.get("name", [])
    if names:
        n = names[0]
        given = " ".join(n.get("given", []))
        family = n.get("family", "")
        return f"{given} {family}".strip()
    return "Unknown"


def _fhir_age(resource: Dict) -> int:
    bd = resource.get("birthDate", "")
    if bd:
        try:
            birth = datetime.strptime(bd, "%Y-%m-%d")
            return (datetime.now() - birth).days // 365
        except ValueError:
            pass
    return 0


# ─── Main producer function ──────────────────────────────────────────────────

def run_hospital_api_simulator(
    csv_path: Optional[str] = None,
    run_id: Optional[str] = None,
    config: Optional[Dict] = None,
    logger_: Optional[logging.Logger] = None,
    audit_service: Any = None,
    mode: str = "csv",
    kafka_servers: str = "localhost:9092",
    delay_ms: int = 50,
    scenario: str = "normal",
    rows: int = 500,
    topic: str = "clinical_trial_events",
    streaming_state: Any = None,
) -> Dict[str, Any]:
    """
    Produce events to Kafka from the chosen data source.
    Returns summary dict.
    """
    from kafka import KafkaProducer  # type: ignore
    from kafka.errors import KafkaError  # type: ignore

    log = logger_ or logging.getLogger(__name__)
    run_id = run_id or str(uuid.uuid4())
    kafka_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", kafka_servers)

    if config:
        topic = config.get("kafka", {}).get("topic", topic)

    # Load data
    if mode == "csv":
        path = csv_path or os.path.join(
            (config or {}).get("data", {}).get("csv_directory", "data/clinical"),
            (config or {}).get("data", {}).get("csv_filename", "clinical_trial_data.csv"),
        )
        records = _load_csv(path)
        source = "hospital_api_simulator"
    elif mode == "synthetic":
        records = _load_synthetic(scenario, rows)
        source = "synthetic_generator"
    elif mode == "synthea":
        synthea_url = os.environ.get("SYNTHEA_URL", "http://synthea:8080")
        records = _load_synthea(synthea_url, rows)
        source = "synthea_fhir"
    elif mode == "api":
        api_cfg = (config or {}).get("external_api", {})
        ext_url = api_cfg.get("url") or os.environ.get("EXTERNAL_API_URL", "")
        api_key = api_cfg.get("token") or os.environ.get("API_KEY")  # never logged
        auth_type = api_cfg.get("auth_type") or os.environ.get("API_AUTH_TYPE", "Bearer")
        max_records = int(api_cfg.get("max_records_per_poll") or rows)
        if not ext_url:
            raise ValueError("EXTERNAL_API_URL env var not set for mode=api")
        records = _load_external_api(ext_url, api_key, max_records, auth_type)
        source = "external_api"
    else:
        raise ValueError(f"Unknown producer mode: {mode}")

    log.info(f"[Producer] Loaded {len(records)} records | mode={mode} | topic={topic}")

    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=kafka_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        retries=3,
        request_timeout_ms=15000,
    )

    events_published = 0
    errors = 0
    t_start = time.time()

    for row in records:
        event = _build_event(row, run_id, source)
        try:
            producer.send(topic, value=event)
            events_published += 1
            log.debug(f"[Producer] Published event_id={event['event_id']}")

            # Update streaming state if available
            if streaming_state is not None:
                streaming_state.record_published(event)

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        except KafkaError as exc:
            errors += 1
            log.error(f"[Producer] Publish failed for row {events_published}: {exc}")

    try:
        producer.flush(timeout=30)
    except Exception as exc:
        log.warning(f"[Producer] Flush warning: {exc}")
    finally:
        producer.close()

    duration = round(time.time() - t_start, 2)
    summary = {
        "events_published": events_published,
        "errors": errors,
        "duration_seconds": duration,
        "topic": topic,
        "mode": mode,
    }
    log.info(f"[Producer] Done: {summary}")
    return summary


# ─── CLI entry-point ─────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hospital API Simulator Kafka Producer")
    parser.add_argument("--mode", choices=["csv", "synthetic", "synthea", "api"], default="csv")
    parser.add_argument("--kafka-servers", default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"))
    parser.add_argument("--delay-ms", type=int, default=int(os.environ.get("INTER_EVENT_DELAY_MS", "50")))
    parser.add_argument("--scenario", default=os.environ.get("SCENARIO", "normal"))
    parser.add_argument("--rows", type=int, default=int(os.environ.get("ROWS", "500")))
    parser.add_argument("--topic", default="clinical_trial_events")
    parser.add_argument("--run-id", default=str(uuid.uuid4()))
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    args = _parse_args()

    # Load config.yaml if available
    cfg: Dict = {}
    try:
        import yaml  # type: ignore
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        if os.path.exists(cfg_path):
            with open(cfg_path) as fh:
                cfg = yaml.safe_load(fh)
    except Exception:
        pass

    result = run_hospital_api_simulator(
        mode=args.mode,
        kafka_servers=args.kafka_servers,
        delay_ms=args.delay_ms,
        scenario=args.scenario,
        rows=args.rows,
        topic=args.topic,
        run_id=args.run_id,
        config=cfg,
    )
    print(json.dumps(result, indent=2))
