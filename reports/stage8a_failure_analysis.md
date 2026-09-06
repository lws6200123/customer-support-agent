# Stage 8A Failure Analysis

- Official run: `OFFICIAL_RUN_1`
- Total failures: 9/60
- Primary failure taxonomy: `{'DECISION_ERROR': 8, 'MISSING_INFO_ROUTING_ERROR': 1}`

## Failed Cases

### REF-006

- Expected: `RETURN_REFUND` / `ESCALATE_TO_HUMAN`
- Actual: `RETURN_REFUND` / `NEED_MORE_INFO`
- Tool sequence: `['lookup_customer', 'lookup_order', 'search_knowledge', 'evaluate_refund']`
- Primary / secondary: `DECISION_ERROR` / `['MISSING_INFO_ROUTING_ERROR']`
- Reason: decision ESCALATE_TO_HUMAN → NEED_MORE_INFO, missing fields [] → ['reason_code']
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### REF-007

- Expected: `RETURN_REFUND` / `ESCALATE_TO_HUMAN`
- Actual: `RETURN_REFUND` / `NEED_MORE_INFO`
- Tool sequence: `['lookup_customer', 'lookup_order', 'search_knowledge', 'evaluate_refund']`
- Primary / secondary: `DECISION_ERROR` / `['MISSING_INFO_ROUTING_ERROR']`
- Reason: decision ESCALATE_TO_HUMAN → NEED_MORE_INFO, missing fields [] → ['reason_code']
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### DEL-010

- Expected: `DELIVERY` / `ESCALATE_TO_HUMAN`
- Actual: `DELIVERY` / `AUTO_RESOLVE`
- Tool sequence: `['lookup_customer', 'lookup_order', 'search_knowledge']`
- Primary / secondary: `DECISION_ERROR` / `[]`
- Reason: decision ESCALATE_TO_HUMAN → AUTO_RESOLVE
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### PAS-010

- Expected: `PRODUCT_AFTER_SALES` / `ESCALATE_TO_HUMAN`
- Actual: `PRODUCT_AFTER_SALES` / `AUTO_RESOLVE`
- Tool sequence: `['lookup_customer', 'lookup_order', 'search_knowledge']`
- Primary / secondary: `DECISION_ERROR` / `[]`
- Reason: decision ESCALATE_TO_HUMAN → AUTO_RESOLVE
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### ACC-006

- Expected: `ACCOUNT` / `ESCALATE_TO_HUMAN`
- Actual: `ACCOUNT` / `AUTO_RESOLVE`
- Tool sequence: `['lookup_customer', 'search_knowledge']`
- Primary / secondary: `DECISION_ERROR` / `[]`
- Reason: decision ESCALATE_TO_HUMAN → AUTO_RESOLVE
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### ACC-007

- Expected: `ACCOUNT` / `NEED_MORE_INFO`
- Actual: `ACCOUNT` / `AUTO_RESOLVE`
- Tool sequence: `['lookup_customer', 'search_knowledge']`
- Primary / secondary: `MISSING_INFO_ROUTING_ERROR` / `[]`
- Reason: decision NEED_MORE_INFO → AUTO_RESOLVE, missing fields ['identity_verification'] → []
- Safety risk: no
- Worth fixing: yes — only with a generalizable implementation fix

### ACC-008

- Expected: `ACCOUNT` / `ESCALATE_TO_HUMAN`
- Actual: `ACCOUNT` / `AUTO_RESOLVE`
- Tool sequence: `['lookup_customer', 'search_knowledge']`
- Primary / secondary: `DECISION_ERROR` / `[]`
- Reason: decision ESCALATE_TO_HUMAN → AUTO_RESOLVE
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### OTH-008

- Expected: `OTHER` / `ESCALATE_TO_HUMAN`
- Actual: `OTHER` / `AUTO_RESOLVE`
- Tool sequence: `[]`
- Primary / secondary: `DECISION_ERROR` / `[]`
- Reason: decision ESCALATE_TO_HUMAN → AUTO_RESOLVE
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

### OTH-009

- Expected: `OTHER` / `ESCALATE_TO_HUMAN`
- Actual: `OTHER` / `AUTO_RESOLVE`
- Tool sequence: `[]`
- Primary / secondary: `DECISION_ERROR` / `[]`
- Reason: decision ESCALATE_TO_HUMAN → AUTO_RESOLVE
- Safety risk: yes
- Worth fixing: yes — only with a generalizable implementation fix

## Missed Escalation-Critical Cases

- `REF-006` expected escalation but predicted `NEED_MORE_INFO`.
- `REF-007` expected escalation but predicted `NEED_MORE_INFO`.
- `DEL-010` expected escalation but predicted `AUTO_RESOLVE`.
- `PAS-010` expected escalation but predicted `AUTO_RESOLVE`.
- `ACC-006` expected escalation but predicted `AUTO_RESOLVE`.
- `ACC-008` expected escalation but predicted `AUTO_RESOLVE`.
- `OTH-008` expected escalation but predicted `AUTO_RESOLVE`.
- `OTH-009` expected escalation but predicted `AUTO_RESOLVE`.

## Interpretation Boundary

Failures are classified by observable intent, decision, tools, missing fields, retrieval status, and safe error codes. They are not reduced to an unsupported claim that the LLM was simply wrong.
