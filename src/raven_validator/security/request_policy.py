"""Probe safety and true outbound-request budget."""
from dataclasses import dataclass
from enum import IntEnum


class ProbeSafetyLevel(IntEnum):
    PASSIVE = 0
    READ_ONLY = 1
    MINIMAL_GENERATION = 2
    CUSTOM_AUTHORIZED = 3


class RequestBudgetExceeded(RuntimeError):
    pass


@dataclass
class RequestPolicy:
    max_requests: int = 6
    max_safety_level: ProbeSafetyLevel = ProbeSafetyLevel.READ_ONLY
    requests_made: int = 0

    def allow(self, level: ProbeSafetyLevel) -> bool:
        return level <= self.max_safety_level

    def consume_request(self) -> None:
        if self.requests_made >= self.max_requests:
            raise RequestBudgetExceeded(f"HTTP request budget exhausted ({self.max_requests})")
        self.requests_made += 1
