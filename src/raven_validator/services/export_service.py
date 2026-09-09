"""Secret-free result export."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from raven_validator.domain.results import ValidationResult


def export_json(results: list[ValidationResult], path: str | Path) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def export_csv(results: list[ValidationResult], path: str | Path) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["base_url","overall_status","detected_protocol","reachable","auth_required","auth_scheme","credential_configured","credential_used","authorized_test_succeeded","models","request_count","latency_ms","quota_status"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in results:
            w.writerow({
                "base_url": r.base_url, "overall_status": r.overall_status.value,
                "detected_protocol": r.detected_protocol, "reachable": r.reachable,
                "auth_required": r.auth_required, "auth_scheme": r.auth_scheme,
                "credential_configured": r.credential_configured, "credential_used": r.credential_used,
                "authorized_test_succeeded": r.authorized_test_succeeded,
                "models": ";".join(r.models), "request_count": r.request_count,
                "latency_ms": r.latency_ms, "quota_status": r.quota.status,
            })
    return path
