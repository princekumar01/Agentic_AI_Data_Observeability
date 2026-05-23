# Clinical Trial AI Observability System — v6.0

**Agentic AI Data Observability for Clinical Trials with Real-Time Kafka Streaming**

---

## Quick Start

### 1. Infrastructure
```bash
docker compose up -d
# Wait ~30 seconds for Kafka to become healthy
docker compose ps
```

### 2. Backend Setup
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 3. Configuration
```bash
cp .env.example .env
# Edit .env — add OPENAI_API_KEY, JWT_SECRET, PIPELINE_API_KEY
```

### 4. Data
```bash
# Place your clinical trial CSV at:
#   data/clinical/clinical_trial_data.csv
# Required columns: patient_id, patient_name, age, gender, diagnosis,
#   treatment_group, visit_date, glucose_level, side_effects, severity
```

### 5. Initialise
```bash
python scripts/setup_baseline.py
python scripts/init_kafka_topics.py
```

### 6. Run
**Terminal 1 — Backend:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend && npm install && npm run dev
```

**Browser:** http://localhost:5173  
**Default login:** `admin` / `admin123`

---

## Architecture

```
Data Sources → Pre-Ingest Validation → Kafka Streaming
            → AI Agents (LangGraph) → HITL Review
            → Dashboard & Audit Trail
```

### Technology Stack
| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.111.0 |
| Agent Orchestration | LangGraph 0.1.9 + LangChain 0.2.3 |
| LLM | OpenAI GPT-4o |
| Message Broker | Apache Kafka 3.6 (Docker) |
| PII/PHI Masking | Microsoft Presidio 2.2.354 + spaCy |
| Auth | JWT (python-jose) + API Key |
| Storage | Local filesystem — output/runs/ |

---

## Data Modes

| Mode | Description |
|------|-------------|
| Mode 1 | Upload CSV — place in `data/clinical/` |
| Mode 2 | Synthetic data — generated in memory |
| Mode 3 | External API / Synthea FHIR |

## Compliance
- FDA 21 CFR Part 11
- ICH E6 GCP
- HIPAA PHI masking (Presidio)
- All data stays local — no cloud storage
