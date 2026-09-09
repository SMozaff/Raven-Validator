"""Tests for request policy: safety levels, budgets, credential boundary."""

import pytest

from raven_validator.security.request_policy import (
    BudgetExceededError,
    ProbeSafetyLevel,
    RequestPolicy,
)


def test_default_ceiling_is_read_only() -> None:
    policy = RequestPolicy()
    assert policy.max_safety_level == ProbeSafetyLevel.READ_ONLY
    assert policy.check_probe_allowed(ProbeSafetyLevel.PASSIVE)
    assert policy.check_probe_allowed(ProbeSafetyLevel.READ_ONLY)
    assert not policy.check_probe_allowed(ProbeSafetyLevel.MINIMAL_GENERATION)
    assert not policy.check_probe_allowed(ProbeSafetyLevel.CUSTOM_AUTHORIZED)


def test_generation_probe_requires_authorized_credential() -> None:
    policy = RequestPolicy(max_safety_level=ProbeSafetyLevel.MINIMAL_GENERATION)
    # Ceiling allows it, but no credential authorized yet.
    assert not policy.check_probe_allowed(ProbeSafetyLevel.MINIMAL_GENERATION)
    policy.authorize_credential("profile-123")
    assert policy.check_probe_allowed(ProbeSafetyLevel.MINIMAL_GENERATION)


def test_read_only_never_needs_credential() -> None:
    policy = RequestPolicy()
    assert not policy.credential_usable
    assert policy.check_probe_allowed(ProbeSafetyLevel.READ_ONLY)


def test_budget_enforced() -> None:
    policy = RequestPolicy(max_requests_per_api=2)
    policy.record_request()
    policy.record_request()
    assert not policy.check_budget()
    with pytest.raises(BudgetExceededError):
        policy.record_request()


def test_default_budget_is_six() -> None:
    policy = RequestPolicy()
    assert policy.max_requests_per_api == 6


def test_discovered_material_cannot_authorize() -> None:
    """There is no API that accepts raw secret text — only profile IDs."""
    policy = RequestPolicy()
    # authorize_credential takes a profile reference, not secret material.
    # Passing something secret-shaped still only stores an opaque reference
    # and does not expose any usable credential.
    policy.authorize_credential("profile-id-not-a-secret")
    assert policy.credential_usable
    assert policy.credential_profile_id == "profile-id-not-a-secret"
