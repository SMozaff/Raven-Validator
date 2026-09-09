"""Request policy: safety levels, budgets, and credential-use boundary.

A discovered credential-like string must NEVER become an authorized
credential automatically. Only a user-configured credential profile
(see credentials/manager.py, Milestone 4) may authorize requests,
and only probes at MINIMAL_GENERATION or CUSTOM_AUTHORIZED level
may carry it.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class ProbeSafetyLevel(StrEnum):
    """Safety classification for every probe."""

    PASSIVE = "passive"
    READ_ONLY = "read_only"
    MINIMAL_GENERATION = "minimal_generation"
    CUSTOM_AUTHORIZED = "custom_authorized"

    def allows_credential(self) -> bool:
        """Only generation-level probes may carry an authorized credential."""
        return self in (
            ProbeSafetyLevel.MINIMAL_GENERATION,
            ProbeSafetyLevel.CUSTOM_AUTHORIZED,
        )


@dataclass
class RequestPolicy:
    """Enforces per-run request budgets and safety ceilings."""

    max_requests_per_api: int = 6
    max_concurrency: int = 10
    max_safety_level: ProbeSafetyLevel = ProbeSafetyLevel.READ_ONLY
    credential_profile_id: str | None = None
    requests_made: int = 0
    _credential_authorized: bool = field(default=False, repr=False)

    def authorize_credential(self, profile_id: str) -> None:
        """Mark an explicitly user-configured credential profile as usable.

        Must only be called with a profile the user deliberately
        associated — never with discovered secret material.
        """
        self._credential_authorized = True
        self.credential_profile_id = profile_id

    @property
    def credential_usable(self) -> bool:
        return self._credential_authorized and self.credential_profile_id is not None

    def check_probe_allowed(self, safety: ProbeSafetyLevel) -> bool:
        """Reject probes above the run's safety ceiling or needing a credential."""
        order = list(ProbeSafetyLevel)
        if order.index(safety) > order.index(self.max_safety_level):
            return False
        if safety.allows_credential():
            return self.credential_usable
        return True

    def check_budget(self) -> bool:
        """True while the per-API request budget is not exhausted."""
        return self.requests_made < self.max_requests_per_api

    def record_request(self) -> None:
        """Count one outgoing request. Raises when the budget is exhausted."""
        if not self.check_budget():
            raise BudgetExceededError(
                f"Request budget exhausted ({self.max_requests_per_api} per API)"
            )
        self.requests_made += 1


class BudgetExceededError(RuntimeError):
    """Raised when a run would exceed its per-API request budget."""
