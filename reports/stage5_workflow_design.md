# Stage 5 Guarded Agent Workflow Design

## Preflight status

- Git working tree was clean at Stage 5 start.
- Stage 1–4 regression suite passed before implementation.
- The Demo SQLite database rebuilt successfully.
- The real Stage 4 RAGFlow smoke remained Top-3 15/15.
- RAGFlow configuration is present.
- DeepSeek and RAGFlow configuration are present; values and credentials are intentionally omitted.
- The real DeepSeek + Stage 4 Tools + RAGFlow smoke completed 10/10 fixed cases after structured sub-intents were constrained to the canonical taxonomy.

## Graph

`initialize_run → classify_ticket → plan_actions → validate_plan → execute_action (bounded loop) → evaluate_resolution → draft_response → persist_result`

The action loop executes at most `MAX_AGENT_STEPS` tool calls. Classification, planning, and response drafting use the injected language-model adapter. Initialization, plan validation, tool mapping, loop bounds, resolution, ticket lifecycle, and persistence are deterministic.

## LLM boundaries

The model returns Pydantic `TicketClassification`, `ActionPlan`, and `ResponseDraft` values. The classification schema uses canonical intent and priority enums. The planner can emit only:

- `LOOKUP_CUSTOMER`
- `LOOKUP_ORDER`
- `LIST_CUSTOMER_ORDERS`
- `SEARCH_KNOWLEDGE`
- `EVALUATE_REFUND`

It cannot request SQL, arbitrary tools, ticket mutation, or money movement. The response schema has no decision field, so drafted language cannot overwrite the deterministic decision.

## Guardrails

- Required lookups and policy retrieval are added deterministically from intent and known identifiers.
- `EVALUATE_REFUND` is rejected without an order identifier and for every non-refund intent.
- Customer-order discovery requires a customer identifier.
- Duplicate actions are rejected by the plan schema and deduplicated by validation.
- Refund routing is copied only from the Stage 4 deterministic `RefundDecisionService` result.
- Missing customer/order information routes to `NEED_MORE_INFO`.
- Missing policy evidence, RAGFlow failure, structured LLM failure, database failure, or the step limit routes conservatively to `ESCALATE_TO_HUMAN`.
- Unsafe customer wording that exposes internal risk language or claims a completed refund falls back to a neutral deterministic response.
- No workflow node writes a refund record or executes money movement.

## Ticket lifecycle

Stage 5 reuses the canonical Stage 3 statuses instead of introducing aliases:

- active processing: `under_review`
- `AUTO_RESOLVE`: `resolved`
- `NEED_MORE_INFO`: `awaiting_customer`
- `ESCALATE_TO_HUMAN`: `under_review` with the decision recorded

Run status is separate and uses `RUNNING`, `COMPLETED`, `FAILED`, `ESCALATED`, or `NEED_MORE_INFO`.

## Trace persistence

`agent_runs` stores the run/ticket/customer/order identifiers, redacted user message, intent, deterministic decision, status, timestamps, total latency, tool-call count, error-code summary, final response, and internal agent summary.

Ordered `agent_steps` store node, action, tool name, status, latency, sanitized input/output summaries, error code, and timestamp. They do not store API keys, full prompts, credentials, or complete RAG chunks.

## Test strategy

The scripted fake model replaces only external classification, planning, and drafting. Tests continue to execute the compiled LangGraph, real SQLite services, Stage 4 structured tools, deterministic refund engine, plan validation, resolution routing, ticket transitions, and trace persistence.
