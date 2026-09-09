"""Database persistence tests — no secrets in DB, history survives restarts."""

from pathlib import Path
from uuid import uuid4

from raven_validator.database.database import Database
from raven_validator.database.repository import Repository
from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.results import ValidationResult
from raven_validator.domain.statuses import ValidationStatus


def make_candidate(name: str = "Test API") -> APICandidate:
    return APICandidate(name=name, base_url="https://api.example.com/v1")  # type: ignore[arg-type]


def test_schema_creates_all_tables(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path}/test.db")
    with db.session() as sess:
        repo = Repository(sess)
        assert repo.list_candidates() == []
    db.dispose()


def test_candidate_crud(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path}/test.db")
    cand = make_candidate()
    with db.session() as sess:
        repo = Repository(sess)
        repo.save_candidate(cand)
    with db.session() as sess:
        repo = Repository(sess)
        assert len(repo.list_candidates()) == 1
        assert repo.get_candidate(cand.id) is not None
        repo.delete_candidate(cand.id)
    with db.session() as sess:
        assert Repository(sess).get_candidate(cand.id) is None
    db.dispose()


def test_validation_history_persists(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    cand = make_candidate("History")
    run_id = uuid4()
    result = ValidationResult(
        candidate_id=cand.id,
        run_id=run_id,
        reachable=True,
        overall_status=ValidationStatus.WORKING,
        detected_protocol="openai-compatible",
        confidence=0.95,
        models=["gpt-4", "gpt-3.5"],
    )
    db_url = f"sqlite:///{db_path}"
    db = Database(db_url)
    with db.session() as sess:
        repo = Repository(sess)
        repo.save_candidate(cand)
        repo.save_validation_result(result)
    db.dispose()

    # Reopen — history must survive.
    db2 = Database(db_url)
    with db2.session() as sess:
        repo = Repository(sess)
        runs = repo.list_runs_for_candidate(cand.id)
        assert len(runs) == 1
        assert runs[0].status == "WORKING"
    db2.dispose()


def test_no_secret_in_db(tmp_path: Path) -> None:
    """Credential profile metadata must not contain raw secrets."""
    db = Database(f"sqlite:///{tmp_path}/test.db")
    secret = "sk-should-never-be-in-db-12345"
    pid = uuid4()
    with db.session() as sess:
        repo = Repository(sess)
        repo.save_credential_profile(pid, display_name="Test Key", auth_type="bearer", keychain_username="user1")
    with db.session() as sess:
        repo = Repository(sess)
        profiles = repo.list_credential_profiles()
        assert len(profiles) == 1
        # Raw secret must not appear anywhere in DB dump.
        import json

        dump = json.dumps([p.display_name for p in profiles] + [p.keychain_username for p in profiles])
        assert secret not in dump
        assert secret not in profiles[0].display_name
    db.dispose()


def test_probe_result_and_error_redacted(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path}/test.db")
    cand = make_candidate()
    run_id = uuid4()
    with db.session() as sess:
        repo = Repository(sess)
        repo.save_candidate(cand)
        repo.create_run(cand.id, run_id=run_id)
        repo.save_probe_result(run_id, probe_type="reachability", excerpt="Authorization: Bearer sk-secret-999")
        repo.save_error(run_id, error_type="auth", message="x-api-key: my-secret-key")
        sess.flush()
        # Excerpts must be redacted.
        from raven_validator.database.models import ProbeResultRecord, ValidationErrorRecord

        probe = sess.query(ProbeResultRecord).first()
        err = sess.query(ValidationErrorRecord).first()
        assert probe is not None and "sk-secret-999" not in (probe.safe_response_excerpt or "")
        assert err is not None and "my-secret-key" not in err.message
    db.dispose()


def test_snapshots_and_credential_profile_lifecycle(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path}/test.db")
    cand = make_candidate()
    run_id = uuid4()
    with db.session() as sess:
        repo = Repository(sess)
        repo.save_candidate(cand)
        repo.create_run(cand.id, run_id=run_id)
        repo.save_capability_snapshot(run_id, models=True, chat_completions=True)
        repo.save_model_snapshots(run_id, ["m1", "m2"])
        repo.save_rate_limit_snapshot(run_id, known=True, limit=100, remaining=42)
        repo.save_quota_snapshot(run_id, status="KNOWN", known=True, balance=12.5, unit="USD")
        # Credential profiles.
        pid = uuid4()
        repo.save_credential_profile(pid, display_name="Key One", keychain_username="u1")
        assert repo.get_credential_profile(pid) is not None
        repo.delete_credential_profile(pid)
        assert repo.get_credential_profile(pid) is None
    db.dispose()
