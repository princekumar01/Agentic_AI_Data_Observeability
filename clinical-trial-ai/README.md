# Clinical Trial AI — Agentic Data Observability System

AI-powered observability platform for clinical trial data pipelines with real-time Kafka streaming, multi-agent analysis, and human-in-the-loop review.

---

## Project Structure

```
clinical-trial-ai/
├── backend/        # FastAPI backend
│   ├── main.py
│   └── requirements.txt
└── frontend/       # React + Vite frontend
    ├── src/
    └── package.json
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm 9+

---

## Running the Backend

```bash
cd backend
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the server:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000`

---

## Running the Frontend

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the dev server:

```bash
npm run dev
```



## Quick Start

Open two terminals and run both servers simultaneously:

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open `http://localhost:5173` in your browser.

---

## Default Login

| Field    | Value      |
|----------|------------|
| Username | `admin`    |
| Password | `admin123` |
