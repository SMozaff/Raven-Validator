"""Dashboard — aggregated stats from the database."""

from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from raven_validator.config.settings import AppSettings
from raven_validator.database.database import Database
from raven_validator.database.models import APICandidateRecord, ValidationRunRecord


class StatCard(QLabel):
    def __init__(self, title: str, value: str = "—") -> None:
        super().__init__()
        self._title = title
        self.setText(f"{title}\n{value}")
        self.setStyleSheet("QLabel { border: 1px solid #444; border-radius: 8px; padding: 16px; font-size: 14px; }")


class DashboardPage(QWidget):
    def __init__(self, settings: AppSettings, database: Database) -> None:
        super().__init__()
        self.settings = settings
        self.database = database
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(QLabel("<h2>Dashboard</h2>"))
        self._grid = QGridLayout()
        self._layout.addLayout(self._grid)
        self._layout.addStretch()

        self._cards: dict[str, StatCard] = {}
        titles = [
            "Total APIs",
            "Working",
            "Auth Required",
            "Rate Limited",
            "Insufficient Credits",
            "Offline / Unreachable",
            "Unknown",
            "Last Validation",
        ]
        for idx, title in enumerate(titles):
            card = StatCard(title)
            self._cards[title] = card
            self._grid.addWidget(card, idx // 4, idx % 4)

        self.refresh()

    def refresh(self) -> None:
        with self.database.session() as sess:
            total = sess.query(APICandidateRecord).count()
            runs = sess.query(ValidationRunRecord).all()
            by_status: dict[str, int] = {}
            last = None
            for r in runs:
                by_status[r.status] = by_status.get(r.status, 0) + 1
                if last is None or (r.completed_at and r.completed_at > last):
                    last = r.completed_at

        self._cards["Total APIs"].setText(f"Total APIs\n{total}")
        self._cards["Working"].setText(f"Working\n{by_status.get('WORKING', 0)}")
        self._cards["Auth Required"].setText(f"Auth Required\n{by_status.get('REACHABLE_AUTH_REQUIRED', 0)}")
        self._cards["Rate Limited"].setText(f"Rate Limited\n{by_status.get('RATE_LIMITED', 0)}")
        self._cards["Insufficient Credits"].setText(f"Insufficient Credits\n{by_status.get('INSUFFICIENT_CREDITS', 0)}")
        offline = by_status.get("CONNECTION_ERROR", 0) + by_status.get("TIMEOUT", 0) + by_status.get("DNS_ERROR", 0)
        self._cards["Offline / Unreachable"].setText(f"Offline / Unreachable\n{offline}")
        self._cards["Unknown"].setText(f"Unknown\n{by_status.get('UNKNOWN', 0)}")
        last_text = last.isoformat() if last else "Never"
        self._cards["Last Validation"].setText(f"Last Validation\n{last_text}")

        if total == 0:
            empty = self.findChild(QLabel, "dashboard_empty")
            if empty is None:
                lbl = QLabel("No APIs yet — add one in Candidates.")
                lbl.setObjectName("dashboard_empty")
                lbl.setStyleSheet("color: #888;")
                self._layout.addWidget(lbl)
