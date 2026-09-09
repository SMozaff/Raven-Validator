"""Settings page — app configuration (env vars are defaults)."""

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from raven_validator.config.settings import AppSettings


class SettingsPage(QWidget):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Settings</h2>"))
        layout.addWidget(QLabel("Environment variables are defaults — these fields override for the current session."))

        form = QFormLayout()
        self.db_edit = QLineEdit(settings.db_url)
        self.log_combo = QComboBox()
        self.log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        idx = self.log_combo.findText(settings.log_level.upper())
        if idx >= 0:
            self.log_combo.setCurrentIndex(idx)
        self.connect_spin = QSpinBox()
        self.connect_spin.setRange(1, 60)
        self.connect_spin.setValue(int(settings.connect_timeout))
        self.read_spin = QSpinBox()
        self.read_spin.setRange(5, 300)
        self.read_spin.setValue(int(settings.read_timeout))
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 50)
        self.concurrency_spin.setValue(settings.max_concurrency)
        self.max_req_spin = QSpinBox()
        self.max_req_spin.setRange(1, 20)
        self.max_req_spin.setValue(settings.max_requests_per_api)
        self.depth_combo = QComboBox()
        self.depth_combo.addItems(["quick", "standard", "authorized"])
        self.depth_combo.setCurrentText("standard")

        form.addRow("Database URL", self.db_edit)
        form.addRow("Log Level", self.log_combo)
        form.addRow("Connect Timeout (s)", self.connect_spin)
        form.addRow("Read Timeout (s)", self.read_spin)
        form.addRow("Max Concurrency", self.concurrency_spin)
        form.addRow("Max Requests per API", self.max_req_spin)
        form.addRow("Default Validation Depth", self.depth_combo)
        layout.addLayout(form)

        self.save_btn = QPushButton("Save (session only)")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2e7d32;")
        layout.addWidget(self.save_btn)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.save_btn.clicked.connect(self._on_save)

    def _on_save(self) -> None:
        self.settings.db_url = self.db_edit.text().strip()
        self.settings.log_level = self.log_combo.currentText()
        self.settings.connect_timeout = float(self.connect_spin.value())
        self.settings.read_timeout = float(self.read_spin.value())
        self.settings.max_concurrency = self.concurrency_spin.value()
        self.settings.max_requests_per_api = self.max_req_spin.value()
        self.status_label.setText("Settings updated for this session.")

    def refresh(self) -> None:
        # No-op — settings page does not need DB refresh.
        pass
