"""Validator page — depth/mode selection, concurrency, toggles, start/cancel."""

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


class ValidatorPage(QWidget):
    def __init__(self, settings: AppSettings, database: Database) -> None:
        super().__init__()
        self.settings = settings
        self.database = database

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Validator</h2>"))

        # Selected APIs list.
        layout.addWidget(QLabel("Selected APIs (from Candidates):"))
        self.api_list = QListWidget()
        self.api_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.api_list)

        # Depth / concurrency row.
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

        # Toggles — quota/credits and streaming must be visibly optional (M5).
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

        # Info labels.
        self.hint_label = QLabel("Mode: Standard — reachability + protocol + auth + models + rate-limit metadata.")
        self.hint_label.setStyleSheet("color: #888;")
        layout.addWidget(self.hint_label)
        self.depth_combo.currentTextChanged.connect(self._on_depth_changed)

        # Progress + buttons.
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
        with self.database.session() as sess:
            for c in Repository(sess).list_candidates():
                self.api_list.addItem(f"{c.name} — {c.base_url}")

    def _on_depth_changed(self, text: str) -> None:
        hints = {
            "Quick": "Quick — reachability + protocol + authentication requirement.",
            "Standard": "Standard — Quick + models + rate-limit metadata.",
            "Authorized": "Authorized — Standard + minimal functional test (requires credential).",
            "Custom": "Custom — select probes manually (future).",
        }
        self.hint_label.setText(f"Mode: {hints.get(text, '')}")

    def _on_start(self) -> None:
        selected = self.api_list.selectedItems()
        if not selected:
            self.status_label.setText("Select at least one API from the list.")
            return
        if self.depth_combo.currentText() == "Authorized":
            self.status_label.setText("Authorized mode requires an associated credential profile (M8).")
            return
        # M8 will run the real engine here; for M7 we simulate progress.
        self._running = True
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate
        count = len(selected)
        names = ", ".join(i.text().split(" — ")[0] for i in selected)
        self.status_label.setText(f"Validating {count} API(s): {names} — (engine in Milestone 8)")
        # For M7 acceptance: immediately complete.
        self._on_complete()

    def _on_complete(self) -> None:
        self.progress.setVisible(False)
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._running = False

    def _on_cancel(self) -> None:
        if not self._running:
            return
        self.status_label.setText("Cancelled.")
        self._on_complete()
