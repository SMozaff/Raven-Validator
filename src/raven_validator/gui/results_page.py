"""Results page — validation run table with status chips."""

from uuid import UUID

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
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

STATUS_COLORS = {
    "WORKING": "#2e7d32",
    "REACHABLE_AUTH_REQUIRED": "#ef6c00",
    "REACHABLE_UNSUPPORTED": "#6a1b9a",
    "RATE_LIMITED": "#f9a825",
    "INSUFFICIENT_CREDITS": "#c62828",
    "TIMEOUT": "#616161",
    "UNKNOWN": "#78909c",
}


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

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Results</h2>"))

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
        # Resize first columns reasonably.
        for idx in range(len(self.COLUMNS)):
            self.table.setColumnWidth(idx, 110)
        layout.addWidget(self.table)

        self.empty_label = QLabel("No validation runs yet — run one from Validator.")
        self.empty_label.setStyleSheet("color: #888;")
        layout.addWidget(self.empty_label)

        self.refresh_btn.clicked.connect(self.refresh)
        self.detail_btn.clicked.connect(self._on_detail)
        self.table.doubleClicked.connect(self._on_detail)
        self.export_json_btn.clicked.connect(lambda: self._on_export("json"))
        self.export_csv_btn.clicked.connect(lambda: self._on_export("csv"))

        self.refresh()

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

        self._run_ids = [row["id"] for row in rows]
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

        has_rows = len(all_runs) > 0
        self.empty_label.setVisible(not has_rows)
        self.table.setVisible(has_rows)

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        if col == 0:
            item.setToolTip(text)
        self.table.setItem(row, col, item)

    def _on_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._run_ids):
            return
        run_id = UUID(self._run_ids[row])
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
