"""Tolerant import of candidates from JSON, CSV, and Raven-Targeter exports."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from raven_validator.domain.candidates import APICandidate
from raven_validator.utils.urls import URLValidationError, normalize_url


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    candidates: list[APICandidate] = field(default_factory=list)


def _make_candidate(raw: dict[str, Any]) -> APICandidate | None:
    """Map a raw dict to APICandidate; return None if unrecoverable."""
    # Accept flexible keys: name/title, base_url/url/endpoint/candidate_endpoints[0]
    name = raw.get("name") or raw.get("title") or raw.get("candidate_name") or "Imported API"
    base_url = raw.get("base_url") or raw.get("url") or raw.get("endpoint") or raw.get("api_url")
    # Raven-Targeter: candidate_endpoints list
    if not base_url and isinstance(raw.get("candidate_endpoints"), list) and raw["candidate_endpoints"]:
        base_url = raw["candidate_endpoints"][0]

    if not isinstance(base_url, str) or not base_url.strip():
        return None

    try:
        normalize_url(base_url.strip())
    except URLValidationError:
        return None

    try:
        return APICandidate(
            id=uuid4(),
            name=str(name).strip() or "Imported API",
            base_url=base_url.strip(),  # type: ignore[arg-type]
            provider_hint=str(raw.get("provider_hint") or raw.get("provider") or "").strip() or None,
            protocol_hint=str(raw.get("protocol_hint") or raw.get("protocol") or raw.get("classification") or "").strip() or None,
            source_url=str(raw.get("source_url") or raw.get("source") or "").strip() or None,  # type: ignore[arg-type]
            source_type=str(raw.get("source_type") or raw.get("sourceType") or "").strip() or None,
            notes=str(raw.get("notes") or raw.get("evidence") or "").strip() or None,
        )
    except (ValidationError, ValueError, TypeError):
        return None


class ImportService:
    """Batch importer that never fails the whole import for one bad row."""

    def import_json(self, path: str | Path) -> ImportResult:
        result = ImportResult()
        try:
            text = Path(path).read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            result.errors.append(f"Failed to read JSON: {exc}")
            return result

        # Support: list, dict with candidates/items/data, single dict, or raven-discovery-export envelope.
        items: list[Any] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Raven-Targeter v1 envelope: schema + items
            for key in ("candidates", "items", "data", "results", "apis", "endpoints"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
            else:
                # Heuristic: if dict has base_url/url/title then it's a single candidate
                if any(k in data for k in ("base_url", "url", "title", "candidate_endpoints")):
                    items = [data]
                else:
                    # Otherwise treat top-level dict as one wrapped record
                    items = [data]

        for idx, raw in enumerate(items):
            if not isinstance(raw, dict):
                result.skipped += 1
                result.errors.append(f"Row {idx}: not a JSON object (got {type(raw).__name__})")
                continue
            # Filter non-candidate keys but still try to make a candidate.
            cand = _make_candidate(raw)
            if cand is None:
                result.skipped += 1
                result.errors.append(f"Row {idx}: missing or invalid base_url")
                continue
            result.candidates.append(cand)
            result.imported += 1

        return result

    def import_csv(self, path: str | Path) -> ImportResult:
        result = ImportResult()
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            result.errors.append(f"Failed to read CSV: {exc}")
            return result

        try:
            reader = csv.DictReader(text.splitlines())
            if reader.fieldnames is None:
                result.errors.append("CSV has no header row")
                return result
            for idx, row in enumerate(reader):
                # Build normalized row dict.
                norm: dict[str, Any] = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    lk = k.strip().lower()
                    # Map common variants
                    if lk in ("base_url", "baseurl", "url", "endpoint", "api_url"):
                        norm["base_url"] = v
                    elif lk in ("name", "title", "candidate_name"):
                        norm["name"] = v
                    elif lk in ("provider", "provider_hint"):
                        norm["provider_hint"] = v
                    elif lk in ("protocol", "protocol_hint", "classification"):
                        norm["protocol_hint"] = v
                    elif lk in ("source", "source_url"):
                        norm["source_url"] = v
                    elif lk in ("source_type", "sourcetype"):
                        norm["source_type"] = v
                    elif lk == "notes":
                        norm["notes"] = v
                    else:
                        norm[lk] = v

                cand = _make_candidate(norm)
                if cand is None:
                    result.skipped += 1
                    result.errors.append(f"Row {idx}: missing or invalid base_url (row: {dict(row)})")
                    continue
                result.candidates.append(cand)
                result.imported += 1
        except (csv.Error, UnicodeDecodeError) as exc:
            result.errors.append(f"CSV parse error: {exc}")

        return result

    def import_raven_targeter(self, path: str | Path) -> ImportResult:
        """Import a Raven-Targeter raven-discovery-export-v1 file.

        Each record may expand to multiple candidates (one per candidate_endpoints).
        Malformed records are skipped, not fatal.
        """
        text_result = ImportResult()
        try:
            text = Path(path).read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            text_result.errors.append(f"Failed to read Targeter JSON: {exc}")
            return text_result

        # Normalize to list of discovery records.
        records: list[Any] = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # Envelope with versioned schema
            for key in ("candidates", "items", "results", "discoveries", "data"):
                if isinstance(data.get(key), list):
                    records = data[key]
                    break
            else:
                records = [data]

        result = ImportResult()
        for idx, rec in enumerate(records):
            if not isinstance(rec, dict):
                result.skipped += 1
                result.errors.append(f"Targeter row {idx}: not an object")
                continue

            endpoints = rec.get("candidate_endpoints") or rec.get("endpoints") or rec.get("urls") or []
            if isinstance(endpoints, str):
                endpoints = [endpoints]
            if not isinstance(endpoints, list) or not endpoints:
                # Fall back to single-url fields.
                single = rec.get("url") or rec.get("base_url") or rec.get("api_url")
                if isinstance(single, str) and single.strip():
                    endpoints = [single]
                else:
                    result.skipped += 1
                    result.errors.append(f"Targeter row {idx}: no candidate_endpoints or url")
                    continue

            for ep in endpoints:
                if not isinstance(ep, str) or not ep.strip():
                    result.skipped += 1
                    result.errors.append(f"Targeter row {idx}: invalid endpoint {ep!r}")
                    continue
                raw: dict[str, Any] = {
                    "base_url": ep.strip(),
                    "name": rec.get("title") or rec.get("name") or f"Targeter {ep}",
                    "provider_hint": rec.get("provider"),
                    "protocol_hint": rec.get("classification") or rec.get("protocol"),
                    "source_url": rec.get("url") if rec.get("url") != ep else rec.get("source"),
                    "source_type": rec.get("source_type"),
                    "notes": "; ".join(rec["evidence"]) if isinstance(rec.get("evidence"), list) else rec.get("evidence"),
                }
                # Clean None-ish values
                raw = {k: v for k, v in raw.items() if v not in (None, "")}
                cand = _make_candidate(raw)
                if cand is None:
                    result.skipped += 1
                    result.errors.append(f"Targeter row {idx}: invalid endpoint {ep!r}")
                    continue
                # Enrich with source metadata
                if not cand.source_url and isinstance(rec.get("source"), str):
                    try:
                        cand.source_url = rec["source"]  # type: ignore[assignment]
                    except Exception:
                        pass
                result.candidates.append(cand)
                result.imported += 1

        return result
