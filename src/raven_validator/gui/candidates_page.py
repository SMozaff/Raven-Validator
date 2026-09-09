"""Candidates page (stub — full implementation in Milestone 7)."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from raven_validator.config.settings import AppSettings


class CandidatesPage(QWidget):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Candidates — coming in Milestone 7"))
