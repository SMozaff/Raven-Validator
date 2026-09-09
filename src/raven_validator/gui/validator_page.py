"""Validator page (stub — full implementation in Milestones 7-8)."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from raven_validator.config.settings import AppSettings


class ValidatorPage(QWidget):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Validator — coming in Milestone 7-8"))
