"""Candidates page — table of APIs with CRUD and import hooks."""

from uuid import UUID, uuid4

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from raven_validator.config.settings import AppSettings
from raven_validator.database.database import Database
from raven_validator.database.repository import Repository
from raven_validator.domain.candidates import APICandidate
from raven_validator.utils.urls import URLValidationError, normalize_url


class AddCandidateDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, candidate: APICandidate | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit API" if candidate else "Add API")
        self._candidate = candidate
        form = QFormLayout(self)
        self.name_edit = QLineEdit(candidate.name if candidate else "")
        self.url_edit = QLineEdit(str(candidate.base_url) if candidate else "")
        self.provider_edit = QLineEdit(candidate.provider_hint or "" if candidate else "")
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["", "openai-compatible", "anthropic-compatible", "generic-rest", "unknown"])
        if candidate and candidate.protocol_hint:
            idx = self.protocol_combo.findText(candidate.protocol_hint)
            if idx >= 0:
                self.protocol_combo.setCurrentIndex(idx)
        self.source_edit = QLineEdit(str(candidate.source_url) if candidate and candidate.source_url else "")
        self.notes_edit = QLineEdit(candidate.notes or "" if candidate else "")
        form.addRow("Name *", self.name_edit)
        form.addRow("Base URL *", self.url_edit)
        form.addRow("Provider Hint", self.provider_edit)
        form.addRow("Protocol Hint", self.protocol_combo)
        form.addRow("Source URL", self.source_edit)
        form.addRow("Notes", self.notes_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def get_candidate(self) -> APICandidate | None:
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        if not name or not url:
            QMessageBox.warning(self, "Validation", "Name and Base URL are required.")
            return None
        try:
            normalize_url(url)
        except URLValidationError as exc:
            QMessageBox.warning(self, "Invalid URL", str(exc))
            return None
        return APICandidate(
            id=self._candidate.id if self._candidate else uuid4(),
            name=name,
            base_url=url,  # type: ignore[arg-type]
            provider_hint=self.provider_edit.text().strip() or None,
            protocol_hint=self.protocol_combo.currentText() or None,
            source_url=self.source_edit.text().strip() or None,  # type: ignore[arg-type]
            notes=self.notes_edit.text().strip() or None,
            credential_profile_id=self._candidate.credential_profile_id if self._candidate else None,
        )


class CandidatesPage(QWidget):
    COLUMNS = ["Name", "Base URL", "Provider", "Protocol", "Source", "Last Status"]

    def __init__(self, settings: AppSettings, database: Database) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self._ids: list[UUID] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Candidates</h2>"))

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add API")
        self.import_json_btn = QPushButton("Import JSON")
        self.import_csv_btn = QPushButton("Import CSV")
        self.import_targeter_btn = QPushButton("Import Raven-Targeter")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.validate_btn = QPushButton("Validate Selected")
        for btn in [self.add_btn, self.import_json_btn, self.import_csv_btn, self.import_targeter_btn, self.edit_btn, self.delete_btn, self.validate_btn]:
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.empty_label = QLabel("No APIs yet — add one or import.")
        self.empty_label.setStyleSheet("color: #888;")
        layout.addWidget(self.empty_label)

        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        self.import_json_btn.clicked.connect(lambda: self._on_import("json"))
        self.import_csv_btn.clicked.connect(lambda: self._on_import("csv"))
        self.import_targeter_btn.clicked.connect(lambda: self._on_import("targeter"))
        self.validate_btn.clicked.connect(self._on_validate)

        self.refresh()

    def refresh(self) -> None:
        # Collect plain data before session closes (avoid DetachedInstanceError).
        candidates_data: list[tuple[UUID, str, str, str | None, str | None, str | None, str]] = []
        with self.database.session() as sess:
            repo = Repository(sess)
            candidates = repo.list_candidates()
            for c in candidates:
                runs = repo.list_runs_for_candidate(UUID(c.id))
                last_status = runs[0].status if runs else "—"
                candidates_data.append(
                    (UUID(c.id), c.name, c.base_url, c.provider_hint, c.protocol_hint, c.source_url, last_status)
                )

        self._ids = [cid for cid, *_ in candidates_data]
        self.table.setRowCount(len(candidates_data))
        for row, (_, name, base_url, provider_hint, protocol_hint, source_url, last_status) in enumerate(candidates_data):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(base_url))
            self.table.setItem(row, 2, QTableWidgetItem(provider_hint or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(protocol_hint or "—"))
            self.table.setItem(row, 4, QTableWidgetItem(source_url or "—"))
            self.table.setItem(row, 5, QTableWidgetItem(last_status))

        has_rows = len(candidates_data) > 0
        self.empty_label.setVisible(not has_rows)
        self.table.setVisible(has_rows)

    def _selected_candidate(self) -> tuple[UUID, APICandidate] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._ids):
            QMessageBox.warning(self, "Selection", "Select a row first.")
            return None
        cid = self._ids[row]
        with self.database.session() as sess:
            repo = Repository(sess)
            rec = repo.get_candidate(cid)
            if rec is None:
                return None
            cand = APICandidate(
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
            return cid, cand

    def _on_add(self) -> None:
        dlg = AddCandidateDialog(self)
        if dlg.exec() == QDialog.Accepted:
            cand = dlg.get_candidate()
            if cand is None:
                return
            with self.database.session() as sess:
                Repository(sess).save_candidate(cand)
            self.refresh()

    def _on_edit(self) -> None:
        sel = self._selected_candidate()
        if sel is None:
            return
        _, cand = sel
        dlg = AddCandidateDialog(self, cand)
        if dlg.exec() == QDialog.Accepted:
            updated = dlg.get_candidate()
            if updated is None:
                return
            with self.database.session() as sess:
                Repository(sess).save_candidate(updated)
            self.refresh()

    def _on_delete(self) -> None:
        sel = self._selected_candidate()
        if sel is None:
            return
        cid, cand = sel
        if QMessageBox.question(self, "Delete", f"Delete '{cand.name}'?") != QMessageBox.Yes:
            return
        with self.database.session() as sess:
            Repository(sess).delete_candidate(cid)
        self.refresh()

    def _on_import(self, kind: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, f"Import {kind}", "", "JSON (*.json);;CSV (*.csv);;All (*)" if kind != "targeter" else "JSON (*.json)")
        if not path:
            return
        # Defer to import service in M9 — show placeholder for now.
        QMessageBox.information(self, "Import", f"Import ({kind}) will be available in Milestone 9.\nSelected: {path}")

    def _on_validate(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Validate", "Select an API to validate.")
            return
        QMessageBox.information(self, "Validate", "Validation will be available when Milestone 8 is connected.\nUse Candidates → Validate Selected after M8.")
