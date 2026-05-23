"""
scripts/init_kafka_topics.py
─────────────────────────────────────────────────────
Creates required Kafka topics on the local broker.
Run once after `docker compose up -d` and before starting the backend.

    python scripts/init_kafka_topics.py

Reads bootstrap_servers and topic name from config.yaml.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import yaml


CONFIG_PATH = "config.yaml"


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh) or {}


def wait_for_kafka(bootstrap_servers: str, max_retries: int = 20, delay: float = 3.0) -> bool:
    """Poll until Kafka is ready, up to max_retries × delay seconds."""
    from kafka import KafkaConsumer  # type: ignore
    from kafka.errors import NoBrokersAvailable  # type: ignore

    print(f"[init_kafka] Waiting for Kafka at {bootstrap_servers} ...")
    for attempt in range(1, max_retries + 1):
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=2000,
                request_timeout_ms=3000,
            )
            consumer.topics()
            consumer.close()
            print(f"[init_kafka] ✓ Kafka is ready (attempt {attempt})")
            return True
        except Exception as exc:
            print(f"[init_kafka]   Attempt {attempt}/{max_retries}: not ready yet ({exc})")
            time.sleep(delay)

    print(f"[init_kafka] ✗ Kafka not available after {max_retries} attempts")
    return False


def create_topic(
    bootstrap_servers: str,
    topic_name: str,
    num_partitions: int = 1,
    replication_factor: int = 1,
) -> bool:
    from kafka import KafkaAdminClient  # type: ignore
    from kafka.admin import NewTopic  # type: ignore
    from kafka.errors import TopicAlreadyExistsError  # type: ignore

    admin = None
    try:
        admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers, request_timeout_ms=5000)
        new_topic = NewTopic(
            name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
        )
        admin.create_topics([new_topic])
        print(f"[init_kafka] ✓ Topic '{topic_name}' created (partitions={num_partitions})")
        return True
    except TopicAlreadyExistsError:
        print(f"[init_kafka] ✓ Topic '{topic_name}' already exists — skipping")
        return True
    except Exception as exc:
        print(f"[init_kafka] ✗ Failed to create topic '{topic_name}': {exc}")
        return False
    finally:
        if admin:
            try:
                admin.close()
            except Exception:
                pass


def verify_topic(bootstrap_servers: str, topic_name: str) -> bool:
    from kafka import KafkaConsumer  # type: ignore

    try:
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            consumer_timeout_ms=2000,
        )
        topics = consumer.topics()
        consumer.close()
        if topic_name in topics:
            print(f"[init_kafka] ✓ Topic '{topic_name}' verified in broker")
            return True
        else:
            print(f"[init_kafka] ✗ Topic '{topic_name}' NOT found in broker topics: {topics}")
            return False
    except Exception as exc:
        print(f"[init_kafka] ✗ Verification failed: {exc}")
        return False


def main() -> None:
    cfg = load_config()
    kafka_cfg = cfg.get("kafka", {})
    bootstrap = os.environ.get(
        "KAFKA_BOOTSTRAP_SERVERS",
        kafka_cfg.get("bootstrap_servers", "localhost:9092"),
    )
    topic = kafka_cfg.get("topic", "clinical_trial_events")

    print(f"[init_kafka] Bootstrap servers: {bootstrap}")
    print(f"[init_kafka] Target topic: {topic}")
    print()

    # Wait for Kafka
    if not wait_for_kafka(bootstrap):
        print("[init_kafka] ✗ Aborting — Kafka is not available")
        sys.exit(1)

    # Create topic
    if not create_topic(bootstrap, topic):
        print("[init_kafka] ✗ Topic creation failed")
        sys.exit(1)

    # Verify
    time.sleep(1)
    verify_topic(bootstrap, topic)

    # Write init record
    os.makedirs("config", exist_ok=True)
    record = {
        "initialized_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_servers": bootstrap,
        "topics_created": [topic],
    }
    with open("config/kafka_init.json", "w") as fh:
        json.dump(record, fh, indent=2)

    print(f"\n[init_kafka] ✓ Kafka initialization complete")
    print(f"[init_kafka]   Record saved to config/kafka_init.json\n")


if __name__ == "__main__":
    main()
