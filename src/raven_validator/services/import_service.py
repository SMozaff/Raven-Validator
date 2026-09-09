"""Tolerant import with a strict Raven-Targeter endpoint contract."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raven_validator.domain.candidates import APICandidate


@dataclass
class ImportResult:
    candidates: list[APICandidate] = field(default_factory=list)
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def imported(self) -> int:
        return len(self.candidates)


def _candidate(raw: dict[str, Any]) -> APICandidate | None:
    url = raw.get("base_url") or raw.get("endpoint") or raw.get("api_url")
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        return APICandidate(
            name=str(raw.get("name") or raw.get("title") or "Imported API"),
            base_url=url.strip(),
            provider_hint=str(raw.get("provider_hint") or raw.get("provider") or "").strip() or None,
            protocol_hint=str(raw.get("protocol_hint") or raw.get("protocol") or raw.get("classification") or "").strip() or None,
            source_url=raw.get("source_url") if isinstance(raw.get("source_url"), str) else None,
            source_type=str(raw.get("source_type") or "").strip() or None,
            notes=str(raw.get("notes") or "").strip() or None,
        )
    except Exception:
        return None


class ImportService:
    def import_raven_targeter(self, path: str | Path) -> ImportResult:
        result = ImportResult()
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            result.errors.append(f"Failed to read JSON: {exc}")
            return result
        if not isinstance(payload, dict) or payload.get("schema") != "raven-discovery-export-v1":
            result.errors.append("Not a raven-discovery-export-v1 document")
            return result
        discoveries = payload.get("discoveries")
        if not isinstance(discoveries, list):
            result.errors.append("Missing discoveries[]")
            return result
        for i, rec in enumerate(discoveries):
            if not isinstance(rec, dict):
                result.skipped += 1; result.errors.append(f"Row {i}: invalid discovery"); continue
            endpoints = rec.get("candidate_endpoints")
            # Critical contract: never fall back to the GitHub source URL.
            if not isinstance(endpoints, list) or not endpoints:
                result.skipped += 1
                result.errors.append(f"Row {i}: no candidate_endpoints; source URL was not treated as an API")
                continue
            for ep in endpoints:
                if isinstance(ep, str):
                    url, evidence = ep, ""
                elif isinstance(ep, dict):
                    url, evidence = ep.get("url"), ep.get("evidence", "")
                else:
                    url, evidence = None, ""
                if not isinstance(url, str) or not url.strip():
                    result.skipped += 1; continue
                cand = _candidate({
                    "name": rec.get("title") or "Targeter API",
                    "base_url": url,
                    "provider": rec.get("provider"),
                    "classification": rec.get("classification"),
                    "source_url": rec.get("source_url"),
                    "source_type": rec.get("source_type"),
                    "notes": evidence,
                })
                if cand:
                    result.candidates.append(cand)
                else:
                    result.skipped += 1
        return result

    def import_json(self, path: str | Path) -> ImportResult:
        result = ImportResult()
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            result.errors.append(str(exc)); return result
        if isinstance(payload, dict) and payload.get("schema") == "raven-discovery-export-v1":
            return self.import_raven_targeter(path)
        items = payload if isinstance(payload, list) else [payload]
        for i, raw in enumerate(items):
            if not isinstance(raw, dict):
                result.skipped += 1; continue
            cand = _candidate(raw)
            if cand: result.candidates.append(cand)
            else: result.skipped += 1; result.errors.append(f"Row {i}: invalid base_url")
        return result

    def import_csv(self, path: str | Path) -> ImportResult:
        result = ImportResult()
        try:
            with Path(path).open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception as exc:
            result.errors.append(str(exc)); return result
        for i, row in enumerate(rows):
            cand = _candidate(row)
            if cand: result.candidates.append(cand)
            else: result.skipped += 1; result.errors.append(f"Row {i}: invalid base_url")
        return result
