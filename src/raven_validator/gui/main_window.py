"""Main application window with sidebar navigation."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from raven_validator.config.settings import AppSettings
from raven_validator.database.database import Database
from raven_validator.gui.candidates_page import CandidatesPage
from raven_validator.gui.credentials_page import CredentialsPage
from raven_validator.gui.dashboard import DashboardPage
from raven_validator.gui.results_page import ResultsPage
from raven_validator.gui.settings_page import SettingsPage
from raven_validator.gui.validator_page import ValidatorPage

NAV_ITEMS = [
    "Dashboard",
    "Candidates",
    "Validator",
    "Results",
    "Credentials",
    "Settings",
]


class MainWindow(QMainWindow):
    """Root window. Navigation only — no network I/O here."""

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.database = Database(settings.db_url)
        self.setWindowTitle("Raven-Validator")
        self.resize(1100, 700)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self.nav = QListWidget()
        self.nav.addItems(NAV_ITEMS)
        self.nav.setFixedWidth(160)
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.pages: list[QWidget] = [
            DashboardPage(settings, self.database),
            CandidatesPage(settings, self.database),
            ValidatorPage(settings, self.database),
            ResultsPage(settings, self.database),
            CredentialsPage(settings, self.database),
            SettingsPage(settings),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        layout.addWidget(self.stack, stretch=1)

        self.nav.setCurrentRow(0)
        self.statusBar().showMessage("Ready")

    def _on_nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        # Refresh pages when navigated to (lightweight).
        page = self.stack.widget(row)
        if hasattr(page, "refresh"):
            page.refresh()  # type: ignore[operator]

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.database.dispose()
        super().closeEvent(event)
