"""Default configuration constants.

Single source of truth for application defaults.
Environment variables (see settings.py) override these at runtime.
"""

from pathlib import Path

DEFAULT_DB_URL = "sqlite:///data/raven_validator.db"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 30.0
DEFAULT_MAX_CONCURRENCY = 10
DEFAULT_MAX_REQUESTS_PER_API = 6
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_FUNCTIONAL_REQUESTS = 1
DEFAULT_VALIDATION_DEPTH = "standard"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_EXPORTS_DIR = PROJECT_ROOT / "exports"
