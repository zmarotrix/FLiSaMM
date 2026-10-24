"""Entry point: `python -m flisamm` (or main.py, or the packaged .exe)."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from .paths import app_data_dir


def setup_logging(data_dir):
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers = [RotatingFileHandler(log_dir / "flisamm.log", maxBytes=1_000_000,
                                    backupCount=3, encoding="utf-8")]
    if sys.stderr:  # Absent in windowed (pythonw / packaged) builds.
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = lambda *exc: logging.getLogger("flisamm").critical("Fatal error", exc_info=exc)


def main():
    data_dir = app_data_dir()
    setup_logging(data_dir)
    logging.getLogger("flisamm").info("Starting; data folder is %s", data_dir)
    from .ui.app import App
    App(data_dir).mainloop()


if __name__ == "__main__":
    main()
