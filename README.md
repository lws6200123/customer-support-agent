# Customer Support Ticket Agent

## Project Overview

Customer Support Ticket Agent is a planned intelligent customer-support ticket processing system based on LangGraph. Stage 2 provides a reproducible operational Demo database built from anonymized Olist transaction data plus an explicitly synthetic customer-support overlay.

## Planned Architecture

The Python application will use a `src` layout. Planned package boundaries separate agent orchestration, tools, services, persistence, API delivery, and shared core configuration. Data, knowledge, scripts, tests, frontend assets, and container-related files have dedicated top-level directories.

The LangGraph agent, retrieval workflows, FastAPI business endpoints, and frontend remain future-stage work. Stage 2 implements only the data build, SQLite schema/loader, and read-only query validation needed by later stages.

## Data Strategy

- Olist will be used as an anonymized real-world e-commerce transaction data source.
- Internal customer-support tickets, risk flags, refund approvals, and similar operational data will be explicitly labeled as **synthetic**.
- Knowledge policies will distinguish **public-policy-derived** material from **simulated internal policy** material.
- Raw source data and processed outputs will remain outside Git, while placeholder files preserve the intended directory layout.
- A fixed simulation clock (`2026-09-03T12:00:00`) and fixed seed make the Demo build reproducible.
- Scenario-aware selection retains 2,000 unique orders covering delivery, fulfillment-state, review, multi-item, and multi-payment cases.
- One offset per order normalizes every associated timestamp while preserving original intervals, late-delivery relationships, and flagged source chronology anomalies.
- Membership, risk, account status, identity verification, language, tickets, and refunds are synthetic operational data—not Olist facts.

## Planned Tech Stack

- Python 3.10+
- FastAPI and Uvicorn
- LangChain and LangGraph
- SQLAlchemy and SQLite
- Pydantic
- httpx
- pytest
- Vue (planned frontend)

## Development Status

**Stage 2 — Demo business dataset and SQLite operational database completed.**

The nine official Kaggle CSV files remain immutable and ignored. The repository now contains deterministic build logic, SQLAlchemy models, atomic database initialization, business-query smoke checks, Stage 1/2 reports, and focused tests. Generated processed CSVs and the SQLite database remain outside Git.

Rebuild and verify Stage 2 from the project root:

```bash
env -u PYTHONPATH .venv/bin/python scripts/build_demo_dataset.py
env -u PYTHONPATH .venv/bin/python scripts/init_db.py
env -u PYTHONPATH .venv/bin/python scripts/run_smoke_queries.py
env -u PYTHONPATH .venv/bin/python -m pytest -q
```

No agent behavior, LangGraph orchestration, RAG integration, business API, frontend, LLM call, MCP integration, or evaluation-case pipeline is implemented yet.
