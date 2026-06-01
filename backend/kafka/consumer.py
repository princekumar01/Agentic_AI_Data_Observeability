# """
# backend/kafka/consumer.py
# ─────────────────────────────────────────────────────
# StreamProcessor — consumes clinical_trial_events from Kafka,
# accumulates events in a rolling window buffer, validates schema,
# and exposes streaming metadata.
# """
# from __future__ import annotations

# import json
# import logging
# import os
# import threading
# from collections import deque
# from datetime import datetime, timezone
# from typing import Any, Deque, Dict, List, Optional, Tuple

# from kafka import KafkaConsumer  # type: ignore
# from kafka.errors import KafkaError  # type: ignore

# REQUIRED_COLUMNS = [
#     "patient_id", "patient_name", "age", "gender", "diagnosis",
#     "treatment_group", "visit_date", "glucose_level", "side_effects", "severity",
# ]
# VALID_SEVERITIES = {"Low", "Medium", "High", "Critical"}


# class StreamProcessor:
#     """
#     Consumes from Kafka topic clinical_trial_events.
#     Fills window_buffer until len >= window_threshold.
#     All events written to stream_events.jsonl as they arrive.
#     """

#     def __init__(
#         self,
#         run_id: str,
#         config: Dict[str, Any],
#         etl_logger: logging.Logger,
#         audit_service: Any,
#         output_dir: str,
#         streaming_state: Any = None,
#     ) -> None:
#         self.run_id = run_id
#         self.config = config
#         self.etl_logger = etl_logger
#         self.audit_service = audit_service
#         self.output_dir = output_dir
#         self.streaming_state = streaming_state

#         kafka_cfg = config.get("kafka", {})
#         self._bootstrap_servers: str = kafka_cfg.get("bootstrap_servers", "localhost:9092")
#         self._topic: str = kafka_cfg.get("topic", "clinical_trial_events")
#         self._window_threshold: int = kafka_cfg.get("window_threshold", 5)
#         self._consumer_timeout_ms: int = kafka_cfg.get("consumer_timeout_ms", 10000)

#         self.window_buffer: Deque[Dict] = deque()
#         self.schema_errors: List[Dict] = []
#         self.events_received: int = 0
#         self.events_valid: int = 0
#         self.events_invalid: int = 0
#         self.consumer_lag_samples: List[int] = []
#         self.api_timeouts: int = 0
#         self.is_done: threading.Event = threading.Event()

#         self._jsonl_path = os.path.join(output_dir, "stream_events.jsonl")

#     # ── Public API ────────────────────────────────────────────────────────────

#     def consume_and_process(self) -> List[Dict]:
#         """
#         Block until window_threshold events collected or consumer times out.
#         Returns list of valid events from window_buffer.
#         """
#         os.makedirs(self.output_dir, exist_ok=True)
#         group_id = f"clinical_observability_{self.run_id[:8]}"

#         try:
#             consumer = KafkaConsumer(
#                 self._topic,
#                 bootstrap_servers=self._bootstrap_servers,
#                 auto_offset_reset="earliest",
#                 group_id=group_id,
#                 consumer_timeout_ms=self._consumer_timeout_ms,
#                 max_poll_records=50,
#                 value_deserializer=lambda b: json.loads(b.decode("utf-8")),
#                 request_timeout_ms=35000,
#                 session_timeout_ms=30000,
#                 heartbeat_interval_ms=3000,
#             )
#         except KafkaError as exc:
#             self.etl_logger.error(f"[Consumer] Failed to create KafkaConsumer: {exc}")
#             self.is_done.set()
#             return []

#         self.etl_logger.info(
#             f"[Consumer] Started | topic={self._topic} group={group_id} "
#             f"threshold={self._window_threshold}"
#         )

#         try:
#             with open(self._jsonl_path, "w", encoding="utf-8") as jsonl_fh:
#                 for message in consumer:
#                     try:
#                         event = message.value
#                         if not isinstance(event, dict):
#                             self.events_invalid += 1
#                             continue

#                         if event.get("run_id") != self.run_id:
#                             continue

#                         self.events_received += 1

#                         # Record consumer lag
#                         lag = max(0, message.offset)
#                         self.consumer_lag_samples.append(lag)

#                         # Schema validation
#                         is_valid, errors = self._validate_event_schema(event)
#                         if not is_valid:
#                             self.events_invalid += 1
#                             self.schema_errors.append({
#                                 "event_id": event.get("event_id", "?"),
#                                 "errors": errors,
#                             })
#                             self.etl_logger.warning(
#                                 f"[Consumer] Schema error event_id={event.get('event_id','?')}: {errors}"
#                             )
#                             continue

#                         self.events_valid += 1
#                         self.window_buffer.append(event)

#                         # Persist raw event
#                         jsonl_fh.write(json.dumps(event) + "\n")

#                         self.etl_logger.info(
#                             f"[Consumer] Consumed event_id={event.get('event_id','?')} "
#                             f"patient_id={event.get('patient_id','?')} "
#                             f"window={len(self.window_buffer)}/{self._window_threshold}"
#                         )

#                         # Update streaming state
#                         if self.streaming_state is not None:
#                             self.streaming_state.record_consumed(lag)

#                         # Check window threshold
#                         if len(self.window_buffer) >= self._window_threshold:
#                             self.etl_logger.info(
#                                 f"[Consumer] Window threshold {self._window_threshold} reached — stopping"
#                             )
#                             break

#                     except Exception as exc:
#                         self.events_invalid += 1
#                         self.etl_logger.error(f"[Consumer] Message processing error: {exc}")

#         except Exception as exc:
#             self.etl_logger.error(f"[Consumer] Consumer loop error: {exc}")
#         finally:
#             try:
#                 consumer.close()
#             except Exception:
#                 pass
#             self.is_done.set()
#             if self.streaming_state is not None:
#                 self.streaming_state.set_consumer_done()

#         self.etl_logger.info(
#             f"[Consumer] Done | received={self.events_received} valid={self.events_valid} "
#             f"invalid={self.events_invalid} in_buffer={len(self.window_buffer)}"
#         )

#         # Persist data fingerprint
#         self._write_data_fingerprint()

#         return list(self.window_buffer)

#     def _validate_event_schema(self, event: Dict) -> Tuple[bool, List[str]]:
#         """Check all 10 required columns, numeric ranges, and severity values."""
#         errors: List[str] = []

#         for col in REQUIRED_COLUMNS:
#             if col not in event:
#                 errors.append(f"Missing column: {col}")

#         if errors:
#             return False, errors

#         # age: numeric, 0–130
#         try:
#             age = float(event["age"])
#             if not (0 <= age <= 130):
#                 errors.append(f"age out of range: {age}")
#         except (TypeError, ValueError):
#             errors.append(f"age not numeric: {event.get('age')}")

#         # glucose_level: numeric, 0–2000
#         try:
#             gluc = float(event["glucose_level"])
#             if not (0 <= gluc <= 2000):
#                 errors.append(f"glucose_level out of range: {gluc}")
#         except (TypeError, ValueError):
#             errors.append(f"glucose_level not numeric: {event.get('glucose_level')}")

#         # severity
#         sev = str(event.get("severity", ""))
#         if sev not in VALID_SEVERITIES:
#             errors.append(f"severity invalid: '{sev}' (expected one of {VALID_SEVERITIES})")

#         return len(errors) == 0, errors

#     def get_streaming_metadata(self) -> Dict[str, Any]:
#         lag_samples = self.consumer_lag_samples
#         return {
#             "events_received": self.events_received,
#             "events_valid": self.events_valid,
#             "events_invalid": self.events_invalid,
#             "schema_errors": self.schema_errors,
#             "consumer_lag_avg": (
#                 round(sum(lag_samples) / len(lag_samples), 2) if lag_samples else 0.0
#             ),
#             "consumer_lag_max": max(lag_samples, default=0),
#             "window_size": len(self.window_buffer),
#             "api_timeouts": self.api_timeouts,
#         }

#     def _write_data_fingerprint(self) -> None:
#         """Write data_fingerprint.json with MD5 hash, row count, and source."""
#         import hashlib

#         fp_path = os.path.join(self.output_dir, "data_fingerprint.json")
#         # Hash first event's run_id + count as a simple fingerprint
#         raw = f"{self.run_id}-{self.events_valid}".encode()
#         fingerprint = {
#             "run_id": self.run_id,
#             "md5_fingerprint": hashlib.md5(raw).hexdigest(),
#             "row_count": self.events_valid,
#             "events_in_window": len(self.window_buffer),
#             "data_source": "kafka_stream",
#             "created_at": datetime.now(timezone.utc).isoformat(),
#         }
#         os.makedirs(self.output_dir, exist_ok=True)
#         with open(fp_path, "w", encoding="utf-8") as fh:
#             json.dump(fingerprint, fh, indent=2)

"""
backend/kafka/consumer.py
─────────────────────────────────────────────────────
StreamProcessor — consumes clinical_trial_events from Kafka,
accumulates events in a rolling window buffer, validates schema,
and exposes streaming metadata.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from kafka import KafkaConsumer  # type: ignore
from kafka.errors import KafkaError  # type: ignore

REQUIRED_COLUMNS = [
    "patient_id", "patient_name", "age", "gender", "diagnosis",
    "treatment_group", "visit_date", "glucose_level", "side_effects", "severity",
]
VALID_SEVERITIES = {"Low", "Medium", "High", "Critical"}

# Non-standard severity labels found in real-world CSVs → mapped to canonical values
# before schema validation runs.  Events are normalised IN-PLACE so none are
# silently dropped due to upstream naming differences.
SEVERITY_NORMALISE: dict = {
    "moderate": "Medium", "Moderate": "Medium", "MODERATE": "Medium",
    "severe":   "High",   "Severe":   "High",   "SEVERE":   "High",
    "minor":    "Low",    "Minor":    "Low",    "MINOR":    "Low",
    "none":     "Low",    "None":     "Low",    "NONE":     "Low",
    "extreme":  "Critical","Extreme": "Critical","EXTREME": "Critical",
    "fatal":    "Critical","Fatal":   "Critical","FATAL":   "Critical",
}


class StreamProcessor:
    """
    Consumes from Kafka topic clinical_trial_events.
    Fills window_buffer until len >= window_threshold.
    All events written to stream_events.jsonl as they arrive.
    """

    def __init__(
        self,
        run_id: str,
        config: Dict[str, Any],
        etl_logger: logging.Logger,
        audit_service: Any,
        output_dir: str,
        streaming_state: Any = None,
    ) -> None:
        self.run_id = run_id
        self.config = config
        self.etl_logger = etl_logger
        self.audit_service = audit_service
        self.output_dir = output_dir
        self.streaming_state = streaming_state

        kafka_cfg = config.get("kafka", {})
        self._bootstrap_servers: str = kafka_cfg.get("bootstrap_servers", "localhost:9092")
        self._topic: str = kafka_cfg.get("topic", "clinical_trial_events")
        self._window_threshold: int = kafka_cfg.get("window_threshold", 5)
        self._consumer_timeout_ms: int = kafka_cfg.get("consumer_timeout_ms", 10000)

        self.window_buffer: Deque[Dict] = deque()
        self.schema_errors: List[Dict] = []
        self.events_received: int = 0
        self.events_valid: int = 0
        self.events_invalid: int = 0
        self.consumer_lag_samples: List[int] = []
        self.api_timeouts: int = 0
        self.is_done: threading.Event = threading.Event()

        self._jsonl_path = os.path.join(output_dir, "stream_events.jsonl")

    # ── Public API ────────────────────────────────────────────────────────────

    def consume_and_process(self) -> List[Dict]:
        """
        Block until window_threshold events collected or consumer times out.
        Returns list of valid events from window_buffer.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        group_id = f"clinical_observability_{self.run_id[:8]}"

        try:
            consumer = KafkaConsumer(
                self._topic,
                bootstrap_servers=self._bootstrap_servers,
                auto_offset_reset="earliest",
                group_id=group_id,
                consumer_timeout_ms=self._consumer_timeout_ms,
                max_poll_records=50,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
                request_timeout_ms=35000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=3000,
            )
        except KafkaError as exc:
            self.etl_logger.error(f"[Consumer] Failed to create KafkaConsumer: {exc}")
            self.is_done.set()
            return []

        self.etl_logger.info(
            f"[Consumer] Started | topic={self._topic} group={group_id} "
            f"threshold={self._window_threshold}"
        )

        try:
            with open(self._jsonl_path, "w", encoding="utf-8") as jsonl_fh:
                for message in consumer:
                    try:
                        event = message.value
                        if not isinstance(event, dict):
                            self.events_invalid += 1
                            continue

                        if event.get("run_id") != self.run_id:
                            continue

                        self.events_received += 1

                        # Record consumer lag
                        lag = max(0, message.offset)
                        self.consumer_lag_samples.append(lag)

                        # Schema validation
                        is_valid, errors = self._validate_event_schema(event)
                        if not is_valid:
                            self.events_invalid += 1
                            self.schema_errors.append({
                                "event_id": event.get("event_id", "?"),
                                "errors": errors,
                            })
                            self.etl_logger.warning(
                                f"[Consumer] Schema error event_id={event.get('event_id','?')}: {errors}"
                            )
                            continue

                        self.events_valid += 1
                        self.window_buffer.append(event)

                        # Persist raw event
                        jsonl_fh.write(json.dumps(event) + "\n")

                        self.etl_logger.info(
                            f"[Consumer] Consumed event_id={event.get('event_id','?')} "
                            f"patient_id={event.get('patient_id','?')} "
                            f"window={len(self.window_buffer)}/{self._window_threshold}"
                        )

                        # Update streaming state
                        if self.streaming_state is not None:
                            self.streaming_state.record_consumed(lag)

                        # Check window threshold
                        if len(self.window_buffer) >= self._window_threshold:
                            self.etl_logger.info(
                                f"[Consumer] Window threshold {self._window_threshold} reached — stopping"
                            )
                            break

                    except Exception as exc:
                        self.events_invalid += 1
                        self.etl_logger.error(f"[Consumer] Message processing error: {exc}")

        except Exception as exc:
            self.etl_logger.error(f"[Consumer] Consumer loop error: {exc}")
        finally:
            try:
                consumer.close()
            except Exception:
                pass
            self.is_done.set()
            if self.streaming_state is not None:
                self.streaming_state.set_consumer_done()

        self.etl_logger.info(
            f"[Consumer] Done | received={self.events_received} valid={self.events_valid} "
            f"invalid={self.events_invalid} in_buffer={len(self.window_buffer)}"
        )

        # Persist data fingerprint
        self._write_data_fingerprint()

        return list(self.window_buffer)

    def _validate_event_schema(self, event: Dict) -> Tuple[bool, List[str]]:
        """Check all 10 required columns, numeric ranges, and severity values."""
        errors: List[str] = []

        for col in REQUIRED_COLUMNS:
            if col not in event:
                errors.append(f"Missing column: {col}")

        if errors:
            return False, errors

        # age: optional; when present must be numeric 0–130
        age_val = event.get("age")
        if age_val is not None:
            try:
                age = float(age_val)
                if not (0 <= age <= 130):
                    errors.append(f"age out of range: {age}")
            except (TypeError, ValueError):
                errors.append(f"age not numeric: {age_val}")

        # glucose_level: optional; when present must be numeric 0–2000
        gluc_val = event.get("glucose_level")
        if gluc_val is not None:
            try:
                gluc = float(gluc_val)
                if not (0 <= gluc <= 2000):
                    errors.append(f"glucose_level out of range: {gluc}")
            except (TypeError, ValueError):
                errors.append(f"glucose_level not numeric: {gluc_val}")

        # severity — null allowed; normalise non-standard labels when present
        raw_sev = event.get("severity")
        if raw_sev is not None:
            raw_sev_str = str(raw_sev)
            normalised_sev = SEVERITY_NORMALISE.get(raw_sev_str, raw_sev_str)
            if normalised_sev != raw_sev_str:
                event["severity"] = normalised_sev
            if normalised_sev not in VALID_SEVERITIES:
                errors.append(
                    f"severity invalid: '{raw_sev_str}' (expected one of {VALID_SEVERITIES})"
                )

        return len(errors) == 0, errors

    def get_streaming_metadata(self) -> Dict[str, Any]:
        lag_samples = self.consumer_lag_samples
        return {
            "events_received": self.events_received,
            "events_valid": self.events_valid,
            "events_invalid": self.events_invalid,
            "schema_errors": self.schema_errors,
            "consumer_lag_avg": (
                round(sum(lag_samples) / len(lag_samples), 2) if lag_samples else 0.0
            ),
            "consumer_lag_max": max(lag_samples, default=0),
            "window_size": len(self.window_buffer),
            "api_timeouts": self.api_timeouts,
        }

    def _write_data_fingerprint(self) -> None:
        """Write data_fingerprint.json with MD5 hash, row count, and source."""
        import hashlib

        fp_path = os.path.join(self.output_dir, "data_fingerprint.json")
        # Hash first event's run_id + count as a simple fingerprint
        raw = f"{self.run_id}-{self.events_valid}".encode()
        fingerprint = {
            "run_id": self.run_id,
            "md5_fingerprint": hashlib.md5(raw).hexdigest(),
            "row_count": self.events_valid,
            "events_in_window": len(self.window_buffer),
            "data_source": "kafka_stream",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(self.output_dir, exist_ok=True)
        with open(fp_path, "w", encoding="utf-8") as fh:
            json.dump(fingerprint, fh, indent=2)