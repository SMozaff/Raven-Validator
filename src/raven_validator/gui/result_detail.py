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
    QuotaSnapshotRecord,
    RateLimitSnapshotRecord,
    ValidationErrorRecord,
    ValidationRunRecord,
)


class ResultDetailDialog(QDialog):
    def __init__(self, run_id: UUID, run: ValidationRunRecord, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Result — {run.status}")
        self.resize(700, 600)

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
                lbl.setStyleSheet("color: #ccc;")
                vbox.addWidget(lbl)

        section("Summary", [f"Status: {run.status}", f"Mode: {run.mode}", f"Reachable: {run.reachable}", f"Protocol: {run.detected_protocol or '—'}", f"Confidence: {run.confidence or 0:.2f}", f"Started: {run.started_at}", f"Completed: {run.completed_at or '—'}"])
        section("Connectivity", [f"HTTP status: {run.status}", f"Request count: {run.request_count}", f"Error count: {run.error_count}"])

        caps = session.query(CapabilitySnapshotRecord).filter_by(run_id=str(run_id)).first()
        if caps:
            section("Capabilities", [f"Models: {caps.models}", f"Chat completions: {caps.chat_completions}", f"Responses: {caps.responses}", f"Streaming: {caps.streaming}", f"Embeddings: {caps.embeddings}"])
        else:
            section("Capabilities", ["No capability snapshot for this run."])

        models = session.query(ModelSnapshotRecord).filter_by(run_id=str(run_id)).all()
        if models:
            section("Models", [m.model_id for m in models])
        else:
            section("Models", ["No models discovered."])

        rl = session.query(RateLimitSnapshotRecord).filter_by(run_id=str(run_id)).first()
        if rl:
            section("Rate Limits", [f"Known: {rl.known}", f"Limit: {rl.limit}", f"Remaining: {rl.remaining}", f"Reset: {rl.reset_at or '—'}", f"Source: {rl.source or '—'}"])

        quota = session.query(QuotaSnapshotRecord).filter_by(run_id=str(run_id)).first()
        if quota:
            section("Quota / Credits", [f"Status: {quota.status}", f"Known: {quota.known}", f"Balance: {quota.balance}", f"Unit: {quota.unit or '—'}", f"Reason: {quota.reason or '—'}"])

        errors = session.query(ValidationErrorRecord).filter_by(run_id=str(run_id)).all()
        if errors:
            section("Errors", [f"[{e.error_type}] {e.message}" for e in errors])
        else:
            section("Errors", ["No errors recorded."])

        section("Evidence", ["(Never exposes full credentials — all excerpts are redacted.)"])
        vbox.addStretch()

        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
