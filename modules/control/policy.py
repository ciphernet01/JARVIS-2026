"""Deny-by-default policy for the A.S.T.R.A privileged control broker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ActionRule:
    mutating: bool
    allowed_parameters: frozenset[str]


@dataclass(frozen=True)
class BrokerDecision:
    allowed: bool
    action: str
    reason: str
    mutating: bool = False


class BrokerPolicy:
    """Validate broker requests without interpreting arbitrary commands."""

    RULES = {
        "broker.health": ActionRule(False, frozenset()),
        "service.status": ActionRule(False, frozenset({"name"})),
        "service.restart": ActionRule(True, frozenset({"name"})),
    }
    SERVICE_ALLOWLIST = frozenset({"jarvis.service", "astra-shell.service"})

    def evaluate(self, request: Mapping[str, Any]) -> BrokerDecision:
        action = request.get("action")
        if not isinstance(action, str) or not action:
            return BrokerDecision(False, "", "A non-empty action is required")

        rule = self.RULES.get(action)
        if rule is None:
            return BrokerDecision(False, action, "Action is not allowlisted")

        params = request.get("params", {})
        if not isinstance(params, dict):
            return BrokerDecision(False, action, "params must be an object", rule.mutating)
        unknown = set(params) - rule.allowed_parameters
        if unknown:
            return BrokerDecision(
                False,
                action,
                f"Unexpected parameters: {', '.join(sorted(unknown))}",
                rule.mutating,
            )

        if action.startswith("service."):
            name = params.get("name")
            if name not in self.SERVICE_ALLOWLIST:
                return BrokerDecision(False, action, "Service is not allowlisted", rule.mutating)

        if rule.mutating:
            if request.get("confirmed") is not True:
                return BrokerDecision(False, action, "Explicit confirmation is required", True)
            reason = request.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                return BrokerDecision(False, action, "A reason is required", True)
            request_id = request.get("request_id")
            if not isinstance(request_id, str) or not request_id.strip():
                return BrokerDecision(False, action, "A request_id is required", True)

        return BrokerDecision(True, action, "Allowed by broker policy", rule.mutating)
