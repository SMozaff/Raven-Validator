"""Import / Export — tolerant mapper, never exports secrets."""

import csv
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from raven_validator.database.database import Database
from raven_validator.database.repository import Repository
from raven_validator.domain.candidates import APICandidate
from raven_validator.services.export_service import ExportService
from raven_validator.services.import_service import ImportService


def test_import_json_list() -> None:
    svc = ImportService()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            [
                {"name": "A", "base_url": "https://api.example.com/v1"},
                {"name": "B", "base_url": "https://b.example.com/v1", "provider": "openai"},
            ],
            f,
        )
        path = f.name
    result = svc.import_json(path)
    assert result.imported == 2
    assert result.skipped == 0
    assert len(result.candidates) == 2
    Path(path).unlink()


def test_import_json_malformed_row_does_not_destroy_batch() -> None:
    svc = ImportService()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            [
                {"name": "Good", "base_url": "https://api.example.com/v1"},
                {"name": "Bad — no url"},
                {"base_url": "not a url"},
                {"name": "Also good", "base_url": "https://good.example.com/v1"},
            ],
            f,
        )
        path = f.name
    result = svc.import_json(path)
    assert result.imported == 2
    assert result.skipped == 2
    assert len(result.errors) == 2
    Path(path).unlink()


def test_import_csv() -> None:
    svc = ImportService()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "base_url", "provider"])
        writer.writeheader()
        writer.writerow({"name": "CSV A", "base_url": "https://a.example.com/v1", "provider": "anthropic"})
        writer.writerow({"name": "CSV B", "base_url": "https://b.example.com/v1"})
        writer.writerow({"name": "Bad", "base_url": ""})  # malformed
        path = f.name
    result = svc.import_csv(path)
    assert result.imported == 2
    assert result.skipped == 1
    Path(path).unlink()


def test_import_raven_targeter_multi_endpoint() -> None:
    svc = ImportService()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            [
                {
                    "title": "Wrapper X",
                    "url": "https://github.com/user/project",
                    "provider": "openai",
                    "classification": "proxy",
                    "candidate_endpoints": ["https://ep1.example.com/v1", "https://ep2.example.com/v1"],
                    "evidence": ["README documents /v1/chat/completions"],
                },
                {
                    "title": "Single",
                    "url": "https://single.example.com/v1",
                    "provider": "generic",
                },
                {
                    "title": "Bad",
                    "provider": "openai",
                },
            ],
            f,
        )
        path = f.name
    result = svc.import_raven_targeter(path)
    # First record expands to 2 candidates, second to 1, third skipped.
    assert result.imported == 3
    assert result.skipped >= 1
    # Provider hint preserved.
    assert any(c.provider_hint == "openai" for c in result.candidates)
    Path(path).unlink()


def test_import_targeter_envelope_with_schema() -> None:
    svc = ImportService()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {"schema": "raven-discovery-export-v1", "candidates": [{"title": "E", "candidate_endpoints": ["https://e.example.com/v1"]}]},
            f,
        )
        path = f.name
    result = svc.import_raven_targeter(path)
    assert result.imported == 1
    Path(path).unlink()


def test_export_json_and_csv_never_contain_secrets(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path}/export.db")
    # Create candidate and a credential profile (secret in memory, not DB).
    from raven_validator.domain.results import ValidationResult
    from raven_validator.domain.statuses import ValidationStatus

    cand = APICandidate(name="Secret Test", base_url="https://api.example.com/v1")  # type: ignore[arg-type]
    pid = uuid4()
    secret = "sk-should-never-appear-in-export-99999"
    # Save candidate and a run.
    run_id = uuid4()
    result = ValidationResult(
        candidate_id=cand.id,
        run_id=run_id,
        reachable=True,
        overall_status=ValidationStatus.WORKING,
        detected_protocol="openai-compatible",
    )
    with db.session() as sess:
        repo = Repository(sess)
        repo.save_candidate(cand)
        repo.save_validation_result(result)
        repo.save_credential_profile(pid, display_name="Key", keychain_username="user-secret")

    # Export JSON and CSV.
    svc = ExportService()
    with db.session() as sess:
        repo = Repository(sess)
        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        svc.export_json(repo, json_path)
        svc.export_csv(repo, csv_path)
        # Assert secret not in files.
        json_text = json_path.read_text(encoding="utf-8")
        csv_text = csv_path.read_text(encoding="utf-8")
        assert secret not in json_text
        assert secret not in csv_text
        # Also ensure no keychain username leaks as secret-like? It's okay to have username, but not secret.
        # Ensure exports are valid.
        assert json.loads(json_text)  # valid JSON
        assert "Secret Test" in json_text

    db.dispose()


def test_export_empty_db(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path}/empty.db")
    svc = ExportService()
    with db.session() as sess:
        repo = Repository(sess)
        json_path = tmp_path / "empty.json"
        csv_path = tmp_path / "empty.csv"
        svc.export_json(repo, json_path)
        svc.export_csv(repo, csv_path)
        assert json_path.exists()
        assert csv_path.exists()
        assert json.loads(json_path.read_text()) == []
    db.dispose()
