"""Result detail dialog — full evidence for a single validation run."""

from uuid import UUID

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from raven_validator.database.models import (
    CapabilitySnapshotRecord,
    ModelSnapshotRecord,
    ProbeResultRecord,
    QuotaSnapshotRecord,
    RateLimitSnapshotRecord,
    ValidationErrorRecord,
    ValidationRunRecord,
)


class ResultDetailDialog(QDialog):
    def __init__(self, run_id: UUID, run: ValidationRunRecord, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Result — {run.status}")
        self.resize(700, 650)

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        scroll.setWidget(inner)
        vbox = QVBoxLayout(inner)

        def section(title: str, lines: list[str]) -> None:
            vbox.addWidget(QLabel(f"<b>{title}</b>"))
            for line in lines:
                lbl = QLabel(line)
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: #ccc; font-size: 12px;")
                vbox.addWidget(lbl)
            # Small spacer
            spacer = QLabel("")
            spacer.setFixedHeight(4)
            vbox.addWidget(spacer)

        # — Summary
        section(
            "Summary",
            [
                f"Overall Status: {run.status}",
                f"Confidence: {run.confidence or 0:.2f}",
                f"Mode: {run.mode}",
                f"Started: {run.started_at}",
                f"Completed: {run.completed_at or '—'}",
            ],
        )

        # — Connectivity
        section(
            "Connectivity",
            [
                f"Reachable: {run.reachable}",
                f"HTTP Status Category: {run.status}",
                f"Request Count: {run.request_count}",
                f"Error Count: {run.error_count}",
            ],
        )

        # — Protocol
        section(
            "Protocol",
            [
                f"Detected Protocol: {run.detected_protocol or 'unknown'}",
                f"Why: {'Protocol detection evidence was captured from endpoint probes and URL structure.' if run.detected_protocol else 'No protocol signal was strong enough — classified as unknown.'}",
            ],
        )

        # — Authentication (explicit evidence)
        probes = session.query(ProbeResultRecord).filter_by(run_id=str(run_id)).order_by(ProbeResultRecord.created_at).all()
        auth_probe = next((p for p in probes if p.probe_type == "auth_requirement"), None)
        if auth_probe:
            auth_lines = [
                f"Auth Required: {'Yes' if 'auth_required' in (auth_probe.safe_response_excerpt or '').lower() or run.status == 'REACHABLE_AUTH_REQUIRED' else '—'}",
                f"Scheme Evidence: {auth_probe.safe_response_excerpt or auth_probe.status or '—'}",
                f"HTTP Status: {auth_probe.http_status or '—'}",
            ]
            # Also try to infer from run status.
            if run.status == "REACHABLE_AUTH_REQUIRED":
                auth_lines.insert(0, "Authentication required — evidence: HTTP 401/403 or WWW-Authenticate header observed.")
            section("Authentication", auth_lines)
        else:
            section("Authentication", ["No auth probe data for this run.", f"Run status: {run.status}"])

        # — Probe Timeline (the authoritative evidence trail)
        if probes:
            timeline: list[str] = []
            for p in probes:
                latency = f" {p.latency_ms:.0f}ms" if p.latency_ms else ""
                http_s = f" HTTP {p.http_status}" if p.http_status else ""
                excerpt = f" — {p.safe_response_excerpt[:120]}" if p.safe_response_excerpt else ""
                timeline.append(f"• {p.probe_type} [{p.method or '—'} {p.endpoint or ''}]{http_s}{latency}{excerpt}")
            section("Probe Timeline", timeline)
        else:
            section("Probe Timeline", ["No probe results recorded."])

        # — Capabilities
        caps = session.query(CapabilitySnapshotRecord).filter_by(run_id=str(run_id)).first()
        if caps:
            section(
                "Capabilities",
                [
                    f"Models: {caps.models}",
                    f"Chat Completions: {caps.chat_completions}",
                    f"Responses: {caps.responses}",
                    f"Streaming: {caps.streaming}",
                    f"Embeddings: {caps.embeddings}",
                    f"Images: {caps.images}",
                    f"Audio: {caps.audio}",
                ],
            )
        else:
            section("Capabilities", ["No capability snapshot for this run."])

        # — Models
        models = session.query(ModelSnapshotRecord).filter_by(run_id=str(run_id)).all()
        if models:
            section("Models", [f"• {m.model_id}" for m in models])
            section("Models (detail)", [f"Count: {len(models)} — double-click to choose default test model in future."])
        else:
            section("Models", ["No models discovered.", "Models list is only available when a /v1/models endpoint exists and is reachable."])

        # — Functional Test (generation)
        gen_probe = next((p for p in probes if p.probe_type == "generation"), None)
        if gen_probe:
            section(
                "Functional Test (Minimal Generation)",
                [
                    f"Success: {gen_probe.http_status in (200, 201)}",
                    f"HTTP Status: {gen_probe.http_status or '—'}",
                    f"Excerpt (redacted): {gen_probe.safe_response_excerpt[:200] if gen_probe.safe_response_excerpt else '—'}",
                    f"Latency: {gen_probe.latency_ms:.0f}ms" if gen_probe.latency_ms else "Latency: —",
                ],
            )
        else:
            section("Functional Test", ["Not tested — requires an authorized credential profile (Credentials page)."])

        # — Streaming
        stream_probe = next((p for p in probes if p.probe_type == "streaming"), None)
        if stream_probe:
            section(
                "Streaming",
                [
                    f"Success: {stream_probe.http_status in (200, 201)}",
                    f"HTTP Status: {stream_probe.http_status or '—'}",
                    f"Excerpt: {stream_probe.safe_response_excerpt[:200] if stream_probe.safe_response_excerpt else '—'}",
                ],
            )
        else:
            section("Streaming", ["Not tested — enable 'Test streaming' in Validator before running."])

        # — Rate Limits
        rl = session.query(RateLimitSnapshotRecord).filter_by(run_id=str(run_id)).first()
        if rl:
            section("Rate Limits", [f"Known: {rl.known}", f"Limit: {rl.limit}", f"Remaining: {rl.remaining}", f"Reset: {rl.reset_at or '—'}", f"Source: {rl.source or '—'}"])
        else:
            section("Rate Limits", ["No rate-limit snapshot — inspect RateLimit headers via Standard mode."])

        # — Quota / Credits (visibly optional)
        quota = session.query(QuotaSnapshotRecord).filter_by(run_id=str(run_id)).first()
        if quota:
            section(
                "Quota / Credits",
                [f"Status: {quota.status}", f"Known: {quota.known}", f"Balance: {quota.balance}", f"Unit: {quota.unit or '—'}", f"Reason: {quota.reason or '—'}"],
            )
        else:
            section("Quota / Credits", ["Not checked — enable 'Check quota / credits' in Validator (requires authorized credential)."])

        # — Errors
        errors = session.query(ValidationErrorRecord).filter_by(run_id=str(run_id)).all()
        if errors:
            section("Errors", [f"[{e.error_type}] {e.message}" for e in errors])
        else:
            section("Errors", ["No errors recorded."])

        section("Evidence & Security", ["All excerpts are redacted — full credentials never appear here.", "Authentication required evidence, when present, cites HTTP 401/403, WWW-Authenticate, and response body markers."])
        vbox.addStretch()

        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
