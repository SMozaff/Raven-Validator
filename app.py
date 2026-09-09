#!/usr/bin/env python3
"""Raven-Validator entry point. Launches the PySide6 desktop application."""

import sys

from PySide6.QtWidgets import QApplication

from raven_validator.config.settings import get_settings
from raven_validator.gui.main_window import MainWindow
from raven_validator.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting Raven-Validator")
    app = QApplication(sys.argv)
    app.setApplicationName("Raven-Validator")
    app.setOrganizationName("Raven")
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
