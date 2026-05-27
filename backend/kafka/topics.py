# """
# backend/kafka/topics.py
# ─────────────────────────────────────────────────────
# Kafka topic management utilities.
# """
# from __future__ import annotations

# import logging

# from kafka import KafkaAdminClient, KafkaConsumer  # type: ignore
# from kafka.admin import NewTopic  # type: ignore
# from kafka.errors import TopicAlreadyExistsError  # type: ignore

# logger = logging.getLogger(__name__)


# def ensure_topic_exists(
#     bootstrap_servers: str,
#     topic_name: str,
#     num_partitions: int = 1,
#     replication_factor: int = 1,
# ) -> None:
#     """
#     Create the Kafka topic if it does not already exist.
#     Silently ignores TopicAlreadyExistsError.
#     """
#     admin: KafkaAdminClient | None = None
#     try:
#         admin = KafkaAdminClient(
#             bootstrap_servers=bootstrap_servers,
#             request_timeout_ms=5000,
#         )
#         new_topic = NewTopic(
#             name=topic_name,
#             num_partitions=num_partitions,
#             replication_factor=replication_factor,
#         )
#         admin.create_topics([new_topic])
#         logger.info("Created Kafka topic '%s'", topic_name)
#     except TopicAlreadyExistsError:
#         logger.debug("Topic '%s' already exists — skipping creation", topic_name)
#     except Exception as exc:
#         logger.warning("Could not create topic '%s': %s", topic_name, exc)
#     finally:
#         if admin:
#             try:
#                 admin.close()
#             except Exception:
#                 pass


# def check_kafka_available(bootstrap_servers: str) -> bool:
#     """
#     Attempt a lightweight consumer connection to test Kafka availability.
#     Returns True if Kafka is reachable, False otherwise.
#     """
#     consumer: KafkaConsumer | None = None
#     try:
#         consumer = KafkaConsumer(
#             bootstrap_servers=bootstrap_servers,
#             consumer_timeout_ms=3000,
#             request_timeout_ms=4000,
#         )
#         consumer.topics()  # triggers metadata fetch
#         return True
#     except Exception as exc:
#         logger.debug("Kafka availability check failed: %s", exc)
#         return False
#     finally:
#         if consumer:
#             try:
#                 consumer.close()
#             except Exception:
#                 pass


# def list_topics(bootstrap_servers: str) -> list:
#     """Return list of topic names, or empty list on error."""
#     consumer: KafkaConsumer | None = None
#     try:
#         consumer = KafkaConsumer(
#             bootstrap_servers=bootstrap_servers,
#             consumer_timeout_ms=3000,
#         )
#         return list(consumer.topics())
#     except Exception:
#         return []
#     finally:
#         if consumer:
#             try:
#                 consumer.close()
#             except Exception:
#                 pass


"""
backend/kafka/topics.py
─────────────────────────────────────────────────────
Kafka topic management utilities.
"""
from __future__ import annotations

import logging

from kafka import KafkaAdminClient, KafkaConsumer  # type: ignore
from kafka.admin import NewTopic  # type: ignore
from kafka.errors import TopicAlreadyExistsError  # type: ignore

logger = logging.getLogger(__name__)


def ensure_topic_exists(
    bootstrap_servers: str,
    topic_name: str,
    num_partitions: int = 1,
    replication_factor: int = 1,
) -> None:
    """
    Create the Kafka topic if it does not already exist.
    Silently ignores TopicAlreadyExistsError.
    """
    admin: KafkaAdminClient | None = None
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            request_timeout_ms=5000,
        )
        new_topic = NewTopic(
            name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
        )
        admin.create_topics([new_topic])
        logger.info("Created Kafka topic '%s'", topic_name)
    except TopicAlreadyExistsError:
        logger.debug("Topic '%s' already exists — skipping creation", topic_name)
    except Exception as exc:
        logger.warning("Could not create topic '%s': %s", topic_name, exc)
    finally:
        if admin:
            try:
                admin.close()
            except Exception:
                pass


def check_kafka_available(bootstrap_servers: str) -> bool:
    """
    Attempt a lightweight consumer connection to test Kafka availability.
    Returns True if Kafka is reachable, False otherwise.

    Note: request_timeout_ms must be greater than session_timeout_ms
    (kafka-python default session timeout is 10000 ms).
    """
    consumer: KafkaConsumer | None = None
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            consumer_timeout_ms=5000,
            request_timeout_ms=15000,
            api_version=(2, 5, 0),
        )
        consumer.topics()  # triggers metadata fetch
        return True
    except Exception as exc:
        logger.warning("Kafka availability check failed: %s", exc)
        return False
    finally:
        if consumer:
            try:
                consumer.close()
            except Exception:
                pass


def list_topics(bootstrap_servers: str) -> list:
    """Return list of topic names, or empty list on error."""
    consumer: KafkaConsumer | None = None
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            consumer_timeout_ms=5000,
            request_timeout_ms=15000,
            api_version=(2, 5, 0),
        )
        return list(consumer.topics())
    except Exception:
        return []
    finally:
        if consumer:
            try:
                consumer.close()
            except Exception:
                pass