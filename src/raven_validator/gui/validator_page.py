"""Validator page — depth/mode selection, concurrency, toggles, start/cancel."""

import asyncio
from uuid import UUID

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from raven_validator.config.settings import AppSettings
from raven_validator.database.database import Database
from raven_validator.database.repository import Repository
from raven_validator.domain.candidates import APICandidate
from raven_validator.services.validation_service import (
    BatchEvent,
    ValidationOptions,
    ValidationService,
)


class ValidationWorker(QObject):
    event_emitted = Signal(object)
    finished = Signal()

    def __init__(
        self,
        service: ValidationService,
        candidates: list[APICandidate],
        options: ValidationOptions,
    ) -> None:
        super().__init__()
        self.service = service
        self.candidates = candidates
        self.options = options
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.service.cancel()

    async def _run(self) -> None:
        async for event in self.service.validate_batch(self.candidates, self.options):
            if self._cancelled:
                break
            self.event_emitted.emit(event)
            if event.kind in ("run_finished", "run_cancelled"):
                break

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run())
        except Exception:
            pass
        finally:
            try:
                loop.close()
            except Exception:
                pass
            self.finished.emit()


class ValidatorPage(QWidget):
    batch_event = Signal(object)

    def __init__(self, settings: AppSettings, database: Database) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self._candidate_ids: list[UUID] = []
        self._thread: QThread | None = None
        self._worker: ValidationWorker | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Validator</h2>"))

        layout.addWidget(QLabel("Selected APIs (from Candidates):"))
        self.api_list = QListWidget()
        self.api_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.api_list)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Validation Depth:"))
        self.depth_combo = QComboBox()
        self.depth_combo.addItems(["Quick", "Standard", "Authorized", "Custom"])
        self.depth_combo.setCurrentText("Standard")
        row1.addWidget(self.depth_combo)
        row1.addWidget(QLabel("Concurrency:"))
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 50)
        self.concurrency_spin.setValue(settings.max_concurrency)
        row1.addWidget(self.concurrency_spin)
        row1.addWidget(QLabel("Timeout (s):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(2, 120)
        self.timeout_spin.setValue(int(settings.connect_timeout + settings.read_timeout))
        row1.addWidget(self.timeout_spin)
        row1.addStretch()
        layout.addLayout(row1)

        toggles = QHBoxLayout()
        self.streaming_check = QCheckBox("Test streaming (optional)")
        self.streaming_check.setChecked(False)
        self.quota_check = QCheckBox("Check quota / credits (optional)")
        self.quota_check.setChecked(False)
        self.rate_limit_check = QCheckBox("Inspect rate limits")
        self.rate_limit_check.setChecked(True)
        for cb in [self.streaming_check, self.quota_check, self.rate_limit_check]:
            toggles.addWidget(cb)
        toggles.addStretch()
        layout.addLayout(toggles)

        self.hint_label = QLabel("Mode: Standard — reachability + protocol + auth + models + rate-limit metadata.")
        self.hint_label.setStyleSheet("color: #888;")
        layout.addWidget(self.hint_label)
        self.depth_combo.currentTextChanged.connect(self._on_depth_changed)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("START VALIDATION")
        self.start_btn.setStyleSheet("QPushButton { font-weight: bold; padding: 8px 16px; }")
        self.cancel_btn = QPushButton("CANCEL")
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.start_btn.clicked.connect(self._on_start)
        self.cancel_btn.clicked.connect(self._on_cancel)

        self._running = False
        self.refresh()

    def refresh(self) -> None:
        self.api_list.clear()
        self._candidate_ids.clear()
        with self.database.session() as sess:
            for c in Repository(sess).list_candidates():
                self.api_list.addItem(f"{c.name} — {c.base_url}")
                # Store UUID for selection mapping.
                from uuid import UUID as _UUID

                self._candidate_ids.append(_UUID(c.id))

    def _on_depth_changed(self, text: str) -> None:
        hints = {
            "Quick": "Quick — reachability + protocol + authentication requirement.",
            "Standard": "Standard — Quick + models + rate-limit metadata.",
            "Authorized": "Authorized — Standard + minimal functional test (requires credential).",
            "Custom": "Custom — select probes manually (future).",
        }
        self.hint_label.setText(f"Mode: {hints.get(text, '')}")

    def _selected_candidates(self) -> list[APICandidate]:
        selected_rows = {self.api_list.row(item) for item in self.api_list.selectedItems()}
        if not selected_rows:
            return []
        cands: list[APICandidate] = []
        with self.database.session() as sess:
            repo = Repository(sess)
            all_cands = repo.list_candidates()
            for idx, rec in enumerate(all_cands):
                if idx not in selected_rows:
                    continue
                cands.append(
                    APICandidate(
                        id=UUID(rec.id),
                        name=rec.name,
                        base_url=rec.base_url,  # type: ignore[arg-type]
                        provider_hint=rec.provider_hint,
                        protocol_hint=rec.protocol_hint,
                        source_url=rec.source_url,  # type: ignore[arg-type]
                        source_type=rec.source_type,
                        notes=rec.notes,
                        credential_profile_id=UUID(rec.credential_profile_id) if rec.credential_profile_id else None,
                    )
                )
        return cands

    def _on_start(self) -> None:
        candidates = self._selected_candidates()
        if not candidates:
            self.status_label.setText("Select at least one API from the list.")
            return

        mode = self.depth_combo.currentText().lower()

        # Build credential store from DB + in-memory fallback.
        credential_store: dict[UUID, str] = {}
        # Try to load from GUI credentials page store if available.
        try:
            parent = self.parent()
            while parent is not None and not hasattr(parent, "pages"):
                parent = parent.parent()  # type: ignore[union-attr]
            if parent is not None:
                cred_page = None
                for p in getattr(parent, "pages", []):  # type: ignore[union-attr]
                    if type(p).__name__ == "CredentialsPage":
                        cred_page = p
                        break
                if cred_page is not None:
                    credential_store.update(getattr(cred_page, "_keychain_store", {}))  # type: ignore[union-attr]
                    # Map string keys to UUID if needed.
                    fixed: dict[UUID, str] = {}
                    for k, v in list(credential_store.items()):
                        if isinstance(k, str):
                            try:
                                fixed[UUID(k)] = v
                            except ValueError:
                                continue
                        elif isinstance(k, UUID):
                            fixed[k] = v
                    credential_store = fixed
        except Exception:
            pass

        # Also try direct DB credential profiles — need actual secrets from keychain store.
        # For now, if authorized mode and no credential, warn.
        has_any_cred = any(c.credential_profile_id and c.credential_profile_id in credential_store for c in candidates)
        if mode == "authorized" and not has_any_cred:
            # Still allow — service will report auth-required but not generation.
            self.status_label.setText("Authorized mode: no associated credential found — will run as Standard.")

        # Override settings for this run.
        self.settings.max_concurrency = self.concurrency_spin.value()

        options = ValidationOptions(
            mode=mode,
            test_streaming=self.streaming_check.isChecked(),
            check_quota=self.quota_check.isChecked(),
        )

        # Handle credentials: map candidate's credential_profile_id to secret.
        store_for_service: dict[UUID, str] = {}
        for c in candidates:
            if c.credential_profile_id and c.credential_profile_id in credential_store:
                store_for_service[c.credential_profile_id] = credential_store[c.credential_profile_id]

        service = ValidationService(self.settings, self.database, credential_store=store_for_service)

        self._thread = QThread(self)
        self._worker = ValidationWorker(service, candidates, options)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event_emitted.connect(self._on_batch_event)
        self._worker.event_emitted.connect(self.batch_event.emit)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._running = True
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(candidates))
        self.progress.setValue(0)
        self.status_label.setText(f"Validating {len(candidates)} API(s)…")

        self._thread.start()

    def _on_batch_event(self, event: BatchEvent) -> None:
        if event.kind == "progress" and event.progress:
            done, total = event.progress
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status_label.setText(f"Progress: {done}/{total}")
        elif event.kind == "candidate_finished" and event.progress:
            done, total = event.progress
            self.progress.setValue(done)
        elif event.kind == "run_finished":
            self.status_label.setText("Validation complete.")
            self._on_complete()
        elif event.kind == "run_cancelled":
            self.status_label.setText("Validation cancelled.")
            self._on_complete()
        elif event.kind == "candidate_started" and event.candidate_id:
            self.status_label.setText(f"Starting {event.candidate_id}…")

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._thread = None
        # Refresh will be triggered by MainWindow via batch_event signal or navigation.
        self._on_complete()

    def _on_complete(self) -> None:
        self.progress.setVisible(False)
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._running = False

    def _on_cancel(self) -> None:
        if not self._running or self._worker is None:
            return
        self.status_label.setText("Cancelling…")
        self._worker.cancel()
