"""Deterministic, non-LLM refund eligibility and escalation engine."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError

from customer_support_agent.core.config import SIMULATION_NOW
from customer_support_agent.core.errors import DatabaseError, OrderNotFoundError
from customer_support_agent.core.schemas import (
    Decision,
    RefundDecisionResult,
    RefundEvaluationInput,
)
from customer_support_agent.db.models import Refund
from customer_support_agent.services.customer_service import CustomerService
from customer_support_agent.services.order_service import OrderService
from customer_support_agent.services.rules import load_business_rules, resolve_rule_reference


class RefundDecisionService:
    """Evaluate canonical rules while keeping policy eligibility separate from decision."""

    def __init__(self, engine: Engine, clock: datetime = SIMULATION_NOW) -> None:
        self.engine = engine
        self.clock = clock
        self.rules = load_business_rules()
        self.customers = CustomerService(engine)
        self.orders = OrderService(engine)

    @property
    def currency(self) -> str:
        return str(self.rules["simulation_business"]["currency"])

    def _need_more_info(
        self,
        request: RefundEvaluationInput,
        missing: list[str],
        customer_id: str | None = None,
        payment_total: float | None = None,
    ) -> RefundDecisionResult:
        return RefundDecisionResult(
            decision=Decision.NEED_MORE_INFO,
            eligible=None,
            reason_codes=["MISSING_REQUIRED_INFORMATION"],
            human_readable_reasons=[f"Required information is missing: {', '.join(missing)}."],
            policy_requirements=["Provide every missing field before eligibility is evaluated."],
            missing_fields=missing,
            order_id=request.order_id,
            customer_id=customer_id,
            requested_amount=request.requested_amount,
            payment_total=payment_total,
            currency=self.currency,
            prior_approved_refunds_in_window=None,
        )

    def _prior_refund_count(self, customer_id: str) -> int:
        semantics = self.rules["refund_frequency_semantics"]
        window_days = int(resolve_rule_reference(self.rules, semantics["window_days_ref"]))
        start = self.clock - timedelta(days=window_days)
        statuses = list(semantics["counted_statuses"])
        try:
            with self.engine.connect() as connection:
                count = connection.scalar(
                    select(func.count())
                    .select_from(Refund)
                    .where(
                        Refund.customer_id == customer_id,
                        Refund.status.in_(statuses),
                        Refund.requested_at >= start,
                        Refund.requested_at < self.clock,
                    )
                )
        except SQLAlchemyError as exc:
            raise DatabaseError() from exc
        return int(count or 0)

    def evaluate(self, request: RefundEvaluationInput) -> RefundDecisionResult:
        initial_missing = [
            name
            for name, value in (
                ("order_id", request.order_id),
                ("reason_code", request.reason_code),
                ("requested_amount", request.requested_amount),
                ("issue_description", request.issue_description),
            )
            if value is None or (isinstance(value, str) and not value.strip())
        ]
        if initial_missing:
            return self._need_more_info(request, initial_missing)
        assert request.order_id is not None
        assert request.reason_code is not None
        assert request.requested_amount is not None

        order = self.orders.get_order_context(request.order_id)
        customer = self.customers.get_customer_context(order.customer_id)
        reason_rule = self.rules["refund_eligibility"]["reason_requirements"].get(
            request.reason_code.value
        )
        if reason_rule is None:
            return self._need_more_info(request, ["reason_code"], order.customer_id, order.payment_total)
        evidence_field = reason_rule["required_true_field"]
        evidence_value = getattr(request, evidence_field)
        if evidence_value is None:
            return self._need_more_info(
                request, [evidence_field], order.customer_id, order.payment_total
            )

        policy_codes: list[str] = []
        policy_reasons: list[str] = []
        requirements = [
            f"Order status must be one of {self.rules['refund_eligibility']['eligible_order_statuses']}.",
            f"Reason-specific evidence field `{evidence_field}` must be true.",
            "Request must be within the canonical reason-specific window.",
            "Requested amount must not exceed recorded payment total.",
        ]
        eligible = True
        if order.status not in self.rules["refund_eligibility"]["eligible_order_statuses"]:
            eligible = False
            policy_codes.append("ORDER_STATUS_NOT_ELIGIBLE")
            policy_reasons.append(f"Order status `{order.status}` is not return-refund eligible.")
        if evidence_value is not True:
            eligible = False
            policy_codes.append("POLICY_EVIDENCE_NOT_SATISFIED")
            policy_reasons.append(f"Required evidence `{evidence_field}` is not satisfied.")
        if order.delivered_at is None:
            eligible = False
            policy_codes.append("DELIVERY_TIMESTAMP_MISSING")
            policy_reasons.append("A delivered timestamp is required for the policy window.")
        else:
            if "window_days_ref" in reason_rule:
                duration = timedelta(
                    days=float(resolve_rule_reference(self.rules, reason_rule["window_days_ref"]))
                )
            else:
                duration = timedelta(
                    hours=float(resolve_rule_reference(self.rules, reason_rule["window_hours_ref"]))
                )
            elapsed = self.clock - order.delivered_at
            if elapsed < timedelta(0) or elapsed > duration:
                eligible = False
                policy_codes.append("OUTSIDE_POLICY_WINDOW")
                policy_reasons.append("The request is outside the canonical reason-specific window.")
        if request.requested_amount > order.payment_total:
            eligible = False
            policy_codes.append("AMOUNT_EXCEEDS_PAYMENT_TOTAL")
            policy_reasons.append("Requested amount exceeds the recorded payment total.")

        prior_count = self._prior_refund_count(order.customer_id)
        control_codes: list[str] = []
        control_reasons: list[str] = []
        auto_limit = float(self.rules["simulation_business"]["auto_refund_limit"])
        frequency_limit = int(
            resolve_rule_reference(
                self.rules, self.rules["refund_frequency_semantics"]["maximum_ref"]
            )
        )
        if request.requested_amount > auto_limit:
            control_codes.append("AUTO_REFUND_LIMIT_EXCEEDED")
            control_reasons.append(
                f"Amount exceeds the simulated DemoShop automatic limit in {self.currency}."
            )
        if customer.risk_flag:
            control_codes.append("RISK_FLAGGED")
            control_reasons.append("The customer profile has a risk flag.")
        if customer.account_status != "active":
            control_codes.append("ACCOUNT_NOT_ACTIVE")
            control_reasons.append("The customer account is not active.")
        if not customer.identity_verified:
            control_codes.append("IDENTITY_NOT_VERIFIED")
            control_reasons.append("Identity verification is required for this sensitive action.")
        if prior_count >= frequency_limit:
            control_codes.append("REFUND_FREQUENCY_LIMIT_REACHED")
            control_reasons.append("Prior approved-refund frequency reached the canonical limit.")
        if order.source_data_quality_flag != "none":
            control_codes.append("SOURCE_DATA_QUALITY_ANOMALY")
            control_reasons.append("A source data-quality anomaly affects automatic handling.")

        if eligible and not control_codes:
            return RefundDecisionResult(
                decision=Decision.AUTO_RESOLVE,
                eligible=True,
                reason_codes=["POLICY_ELIGIBLE", "AUTO_REFUND_CONTROLS_PASSED"],
                human_readable_reasons=[
                    "Policy eligibility and all simulated automatic controls passed."
                ],
                policy_requirements=requirements,
                missing_fields=[],
                order_id=order.order_id,
                customer_id=order.customer_id,
                requested_amount=request.requested_amount,
                payment_total=order.payment_total,
                currency=self.currency,
                prior_approved_refunds_in_window=prior_count,
            )
        return RefundDecisionResult(
            decision=Decision.ESCALATE_TO_HUMAN,
            eligible=eligible,
            reason_codes=policy_codes + control_codes,
            human_readable_reasons=policy_reasons + control_reasons,
            policy_requirements=requirements,
            missing_fields=[],
            order_id=order.order_id,
            customer_id=order.customer_id,
            requested_amount=request.requested_amount,
            payment_total=order.payment_total,
            currency=self.currency,
            prior_approved_refunds_in_window=prior_count,
        )
