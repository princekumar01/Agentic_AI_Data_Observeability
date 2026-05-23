#!/usr/bin/env bash
set -euo pipefail

KAFKA_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:29092}"
DELAY_MS="${INTER_EVENT_DELAY_MS:-50}"
MODE="${DATA_MODE:-csv}"

echo "[simulator_entrypoint] Waiting for Kafka at ${KAFKA_SERVERS} ..."

until python3 - <<'EOF'
import sys, os
from kafka import KafkaProducer
servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
try:
    p = KafkaProducer(bootstrap_servers=servers, request_timeout_ms=3000)
    p.close()
    sys.exit(0)
except Exception as e:
    print(f"Kafka not ready: {e}", file=sys.stderr)
    sys.exit(1)
EOF
do
    echo "[simulator_entrypoint] Kafka not ready yet — retrying in 3s ..."
    sleep 3
done

echo "[simulator_entrypoint] Kafka is ready. Starting producer in mode='${MODE}' delay=${DELAY_MS}ms ..."

exec python3 -m backend.kafka.producer \
    --mode "${MODE}" \
    --kafka-servers "${KAFKA_SERVERS}" \
    --delay-ms "${DELAY_MS}"
