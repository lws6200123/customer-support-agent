# Customer Support Ticket Agent

## Project Overview

Customer Support Ticket Agent is a staged portfolio project for a future LangGraph-based customer-support ticket system. Stage 4 provides deterministic business services, structured Agent-ready tools, and retrieval-only access to the governed DemoShop policy corpus. It does not yet implement an Agent or autonomous ticket handling.

**DemoShop is a portfolio simulation.** Transactional records and policy reference materials come from different public sources and are not claimed to belong to the same real company. Olist supplies anonymized real transaction data; JD.com Help Center pages are paraphrased public-policy references; DemoShop workflow controls are simulated internal policies.

## Current and Planned Architecture

The Python application uses a `src` layout. Package boundaries separate future Agent orchestration, thin tools, business services, persistence, future API delivery, and shared configuration/contracts.

```text
SQLite
  ↓
Business Services
  ↓
LangChain Structured Tools

Knowledge Markdown
  ↓
RAGFlow Retrieval API
  ↓
KnowledgeTool
```

The current tools retrieve customer/order context, list customer orders, evaluate refund candidates, manage synthetic tickets, and retrieve policy evidence. The LangGraph workflow, LLM calls, FastAPI business endpoints, and frontend remain future-stage work.

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
- Olist monetary values and the simulated automatic-refund threshold share the canonical `BRL` semantic; no currency conversion is applied.
- Refund frequency means prior `approved` refunds for the same customer in `[simulation_now - 30 days, simulation_now)`; the current request is excluded and a count of 2 or more requires escalation.

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

**Stage 4 — Business Tools and Knowledge Retrieval completed.**

Implemented capabilities are intentionally below the Agent layer:

- typed `CustomerService`, `OrderService`, `TicketService`, and `RefundDecisionService`;
- a deterministic refund engine that separates policy eligibility from operational decision;
- six LangChain structured tools with one JSON-safe success/error envelope;
- RAGFlow v0.27.1 retrieval-only integration with local policy metadata normalization;
- real retrieval and disposable-database tool smoke suites.

`AUTO_RESOLVE` denotes a rule-qualified candidate only; no refund is executed. Knowledge retrieval returns evidence chunks and does not generate an answer.

Rebuild and verify Stage 2 from the project root:

```bash
env -u PYTHONPATH .venv/bin/python scripts/build_demo_dataset.py
env -u PYTHONPATH .venv/bin/python scripts/init_db.py
env -u PYTHONPATH .venv/bin/python scripts/run_smoke_queries.py
env -u PYTHONPATH .venv/bin/python scripts/audit_policies.py
env -u PYTHONPATH .venv/bin/python scripts/run_stage4_knowledge_smoke.py
env -u PYTHONPATH .venv/bin/python scripts/run_stage4_tool_smoke.py
env -u PYTHONPATH .venv/bin/python -m pytest -q
```

The Stage 4 retrieval scripts require a locally configured `.env` and an available, already-populated RAGFlow dataset. No API key is stored in the repository or printed in reports.

No Agent behavior, LangGraph orchestration, LLM call, business API, frontend, MCP integration, or final evaluation benchmark is implemented yet.
