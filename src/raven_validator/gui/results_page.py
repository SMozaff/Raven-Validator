"""Results page — validation run table with status chips, filter & sort."""

from uuid import UUID

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from raven_validator.config.settings import AppSettings
from raven_validator.database.database import Database
from raven_validator.database.repository import Repository
from raven_validator.gui.result_detail import ResultDetailDialog


class ResultsPage(QWidget):
    COLUMNS = [
        "Status",
        "API",
        "Protocol",
        "Reachable",
        "Auth",
        "Credential",
        "Models",
        "Generation",
        "Streaming",
        "Rate Limit",
        "Quota",
        "Latency",
        "Last Checked",
    ]

    def __init__(self, settings: AppSettings, database: Database) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self._run_ids: list[str] = []
        self._all_rows: list[dict[str, str]] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Results</h2>"))

        # Filter / sort bar.
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by API or status…")
        filter_row.addWidget(self.search_edit)
        filter_row.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "WORKING", "REACHABLE_AUTH_REQUIRED", "RATE_LIMITED", "INSUFFICIENT_CREDITS", "TIMEOUT", "UNKNOWN", "CANCELLED"])
        filter_row.addWidget(self.status_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.detail_btn = QPushButton("View Detail")
        self.export_json_btn = QPushButton("Export JSON")
        self.export_csv_btn = QPushButton("Export CSV")
        for b in [self.refresh_btn, self.detail_btn, self.export_json_btn, self.export_csv_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        for idx in range(len(self.COLUMNS)):
            self.table.setColumnWidth(idx, 110)
        layout.addWidget(self.table)

        self.empty_label = QLabel("No validation runs yet — run one from Validator.")
        self.empty_label.setStyleSheet("color: #888;")
        layout.addWidget(self.empty_label)

        # Helpful empty-state hint when filtered to zero.
        self.filtered_empty = QLabel("No results match the current filter.")
        self.filtered_empty.setStyleSheet("color: #888; font-style: italic;")
        self.filtered_empty.setVisible(False)
        layout.addWidget(self.filtered_empty)

        self.refresh_btn.clicked.connect(self.refresh)
        self.detail_btn.clicked.connect(self._on_detail)
        self.table.doubleClicked.connect(self._on_detail)
        self.export_json_btn.clicked.connect(lambda: self._on_export("json"))
        self.export_csv_btn.clicked.connect(lambda: self._on_export("csv"))
        self.search_edit.textChanged.connect(self._apply_filter)
        self.status_combo.currentTextChanged.connect(self._apply_filter)

        self.refresh()

    def _apply_filter(self) -> None:
        query = self.search_edit.text().lower().strip()
        status_filter = self.status_combo.currentText()
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            status = status_item.text() if status_item else ""
            name = name_item.text().lower() if name_item else ""
            visible = True
            if status_filter != "All" and status != status_filter:
                visible = False
            if query and query not in name and query not in status.lower():
                visible = False
            self.table.setRowHidden(row, not visible)

        # Show filtered-empty hint if all rows hidden but some exist.
        has_any = self.table.rowCount() > 0
        has_visible = any(not self.table.isRowHidden(r) for r in range(self.table.rowCount()))
        self.filtered_empty.setVisible(has_any and not has_visible)

    def refresh(self) -> None:
        rows: list[dict[str, str]] = []
        with self.database.session() as sess:
            repo = Repository(sess)
            candidates = {c.id: c.name for c in repo.list_candidates()}
            all_runs = []
            for cid in candidates:
                all_runs.extend(repo.list_runs_for_candidate(UUID(cid)))
            all_runs.sort(key=lambda r: str(r.started_at), reverse=True)
            for r in all_runs:
                rows.append(
                    {
                        "id": r.id,
                        "status": r.status,
                        "name": candidates.get(r.candidate_id, r.candidate_id[:8]),
                        "protocol": r.detected_protocol or "—",
                        "reachable": "Yes" if r.reachable else ("No" if r.reachable is False else "—"),
                        "confidence": f"{r.confidence:.2f}" if r.confidence else "—",
                        "ts": str(r.completed_at or r.started_at)[:19],
                    }
                )

        self._all_rows = rows
        # Temporarily disable sorting while repopulating to avoid flicker.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            self._set_cell(idx, 0, row["status"])
            self._set_cell(idx, 1, row["name"])
            self._set_cell(idx, 2, row["protocol"])
            self._set_cell(idx, 3, row["reachable"])
            self._set_cell(idx, 4, "—")
            self._set_cell(idx, 5, "—")
            self._set_cell(idx, 6, "—")
            self._set_cell(idx, 7, "—")
            self._set_cell(idx, 8, "—")
            self._set_cell(idx, 9, "—")
            self._set_cell(idx, 10, "—")
            self._set_cell(idx, 11, row["confidence"])
            self._set_cell(idx, 12, row["ts"])
            # Store run id for detail lookup (survives sorting/filtering).
            item = self.table.item(idx, 0)
            if item is not None:
                item.setData(256, row["id"])
        self.table.setSortingEnabled(True)

        has_rows = len(rows) > 0
        self.empty_label.setVisible(not has_rows)
        self.table.setVisible(has_rows)
        self._apply_filter()

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        if col == 0:
            item.setToolTip(text)
        self.table.setItem(row, col, item)

    def _on_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        run_id_str = item.data(256)
        if not isinstance(run_id_str, str):
            return
        run_id = UUID(run_id_str)
        with self.database.session() as sess:
            repo = Repository(sess)
            run = repo.get_run(run_id)
            if run is None:
                return
            dlg = ResultDetailDialog(run_id, run, sess, self)
            dlg.exec()

    def _on_export(self, fmt: str) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        filt = "JSON (*.json)" if fmt == "json" else "CSV (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, f"Export {fmt.upper()}", f"raven_validator_export.{fmt}", filt)
        if not path:
            return
        from raven_validator.database.repository import Repository
        from raven_validator.services.export_service import ExportService

        with self.database.session() as sess:
            repo = Repository(sess)
            svc = ExportService()
            try:
                if fmt == "json":
                    out = svc.export_json(repo, path)
                else:
                    out = svc.export_csv(repo, path)
                QMessageBox.information(self, "Export", f"Exported to:\n{out}")
            except OSError as exc:
                QMessageBox.warning(self, "Export Failed", str(exc))
