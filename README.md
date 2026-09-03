# Customer Support Ticket Agent

## Project Overview

Customer Support Ticket Agent is a planned intelligent customer-support ticket processing system based on LangGraph. Stage 3 adds a governed DemoShop customer-service knowledge base to the reproducible operational Demo database created in Stage 2.

**DemoShop is a portfolio simulation.** Transactional records and policy reference materials come from different public sources and are not claimed to belong to the same real company. Olist supplies anonymized real transaction data; JD.com Help Center pages are paraphrased public-policy references; DemoShop workflow controls are simulated internal policies.

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
- Public-policy-derived documents are paraphrased/adapted references and do not represent a real JD.com or Olist internal customer-service system.
- Simulated internal workflow thresholds have one machine-readable source of truth: `knowledge/business_rules.yaml`.

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

**Stage 3 — Customer-service business rules and knowledge base completed.**

The knowledge base contains six public-policy-derived customer-service documents and four clearly labeled simulated internal operational policies. Its official-source registry, canonical business rules, six-intent taxonomy, decision examples, and deterministic conflict audit provide stable inputs for later retrieval and rule-engine work. The Stage 2 data pipeline and database remain reproducible and unchanged in scope.

Rebuild and verify Stage 2 from the project root:

```bash
env -u PYTHONPATH .venv/bin/python scripts/build_demo_dataset.py
env -u PYTHONPATH .venv/bin/python scripts/init_db.py
env -u PYTHONPATH .venv/bin/python scripts/run_smoke_queries.py
env -u PYTHONPATH .venv/bin/python scripts/audit_policies.py
env -u PYTHONPATH .venv/bin/python -m pytest -q
```

No RAGFlow upload, embedding, retrieval, agent behavior, LangGraph orchestration, business API, frontend, LLM call, MCP integration, or final evaluation benchmark is implemented yet.
