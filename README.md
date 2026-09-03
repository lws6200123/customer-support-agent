# Customer Support Ticket Agent

## Project Overview

Customer Support Ticket Agent is a planned intelligent customer-support ticket processing system based on LangGraph. The repository currently contains only the Stage 0 project scaffold and foundational configuration.

## Planned Architecture

The Python application will use a `src` layout. Planned package boundaries separate agent orchestration, tools, services, persistence, API delivery, and shared core configuration. Data, knowledge, scripts, tests, frontend assets, and container-related files have dedicated top-level directories.

The LangGraph agent, retrieval workflows, FastAPI business endpoints, frontend, and persistence behavior are future-stage work and are not implemented in Stage 0.

## Data Strategy

- Olist will be used as an anonymized real-world e-commerce transaction data source.
- Internal customer-support tickets, risk flags, refund approvals, and similar operational data will be explicitly labeled as **synthetic**.
- Knowledge policies will distinguish **public-policy-derived** material from **simulated internal policy** material.
- Raw source data and processed outputs will remain outside Git, while placeholder files preserve the intended directory layout.

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

**Stage 1 — Olist real-data acquisition and audit completed.**

The nine official Kaggle CSV files are present in the ignored raw-data directory. The project virtual environment, minimal pandas dependency, reusable audit script, raw-file manifest, Stage 1 audit report, and focused tests are ready.

After the official files are placed in `data/raw/olist/`, run:

```bash
.venv/bin/python scripts/audit_olist.py
```

No agent behavior, RAG integration, business API, frontend implementation, database logic, data transformation, synthetic-data generator, or evaluation pipeline exists yet.
