"""Export of validation results / candidates — never includes secrets."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from raven_validator.database.models import (
    CapabilitySnapshotRecord,
    ModelSnapshotRecord,
    QuotaSnapshotRecord,
    RateLimitSnapshotRecord,
    ValidationRunRecord,
)
from raven_validator.database.repository import Repository


def _run_to_dict(run: ValidationRunRecord, candidate_name: str, candidate_url: str, session) -> dict[str, object]:
    caps = session.query(CapabilitySnapshotRecord).filter_by(run_id=run.id).first()
    models = session.query(ModelSnapshotRecord).filter_by(run_id=run.id).all()
    rl = session.query(RateLimitSnapshotRecord).filter_by(run_id=run.id).first()
    quota = session.query(QuotaSnapshotRecord).filter_by(run_id=run.id).first()

    return {
        "name": candidate_name,
        "base_url": candidate_url,
        "status": run.status,
        "reachable": run.reachable,
        "protocol": run.detected_protocol,
        "confidence": run.confidence,
        "mode": run.mode,
        "capabilities": {
            "models": caps.models if caps else None,
            "chat_completions": caps.chat_completions if caps else None,
            "responses": caps.responses if caps else None,
            "streaming": caps.streaming if caps else None,
            "embeddings": caps.embeddings if caps else None,
        } if caps else None,
        "models_count": len(models),
        "models": [m.model_id for m in models],
        "rate_limit": {
            "known": rl.known if rl else False,
            "limit": rl.limit if rl else None,
            "remaining": rl.remaining if rl else None,
            "reset_at": rl.reset_at.isoformat() if rl and rl.reset_at else None,
            "source": rl.source if rl else None,
        },
        "quota": {
            "status": quota.status if quota else "UNKNOWN",
            "known": quota.known if quota else False,
            "balance": quota.balance if quota else None,
            "unit": quota.unit if quota else None,
            "reason": quota.reason if quota else None,
        },
        "latency_ms": None,  # per-run aggregate not stored; per-probe available
        "tested_at": (run.completed_at or run.started_at).isoformat() if run.completed_at or run.started_at else None,
        "exported_at": datetime.now(UTC).isoformat(),
    }


class ExportService:
    """Writes validation results to JSON/CSV. Secret-free by construction."""

    def export_json(
        self,
        repository: Repository,
        dest: str | Path,
        candidate_ids: list[UUID] | None = None,
    ) -> Path:
        session = repository.session
        candidates = repository.list_candidates()
        if candidate_ids is not None:
            wanted = {str(cid) for cid in candidate_ids}
            candidates = [c for c in candidates if c.id in wanted]

        payload: list[dict[str, object]] = []
        for c in candidates:
            runs = repository.list_runs_for_candidate(UUID(c.id))
            if not runs:
                payload.append(
                    {
                        "name": c.name,
                        "base_url": c.base_url,
                        "status": "NOT_TESTED",
                        "tested_at": None,
                    }
                )
                continue
            for run in runs:
                payload.append(_run_to_dict(run, c.name, c.base_url, session))

        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with dest_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

        return dest_path

    def export_csv(
        self,
        repository: Repository,
        dest: str | Path,
        candidate_ids: list[UUID] | None = None,
    ) -> Path:
        session = repository.session
        candidates = repository.list_candidates()
        if candidate_ids is not None:
            wanted = {str(cid) for cid in candidate_ids}
            candidates = [c for c in candidates if c.id in wanted]

        fieldnames = [
            "name",
            "base_url",
            "status",
            "reachable",
            "protocol",
            "confidence",
            "mode",
            "models_count",
            "rate_limit_known",
            "quota_status",
            "tested_at",
        ]

        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with dest_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for c in candidates:
                runs = repository.list_runs_for_candidate(UUID(c.id))
                if not runs:
                    writer.writerow(
                        {
                            "name": c.name,
                            "base_url": c.base_url,
                            "status": "NOT_TESTED",
                            "reachable": "",
                            "protocol": c.protocol_hint or "",
                            "confidence": "",
                            "mode": "",
                            "models_count": 0,
                            "rate_limit_known": False,
                            "quota_status": "UNKNOWN",
                            "tested_at": "",
                        }
                    )
                    continue
                for run in runs:
                    # Need rate/quota for this run.
                    rl = session.query(RateLimitSnapshotRecord).filter_by(run_id=run.id).first()
                    quota = session.query(QuotaSnapshotRecord).filter_by(run_id=run.id).first()
                    models = session.query(ModelSnapshotRecord).filter_by(run_id=run.id).all()
                    writer.writerow(
                        {
                            "name": c.name,
                            "base_url": c.base_url,
                            "status": run.status,
                            "reachable": run.reachable,
                            "protocol": run.detected_protocol or "",
                            "confidence": run.confidence if run.confidence is not None else "",
                            "mode": run.mode,
                            "models_count": len(models),
                            "rate_limit_known": rl.known if rl else False,
                            "quota_status": quota.status if quota else "UNKNOWN",
                            "tested_at": (run.completed_at or run.started_at).isoformat() if (run.completed_at or run.started_at) else "",
                        }
                    )

        return dest_path
