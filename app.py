from raven_validator.config.settings import get_settings
from raven_validator.gui.main_window import run_app

if __name__ == "__main__":
    raise SystemExit(run_app(get_settings()))
