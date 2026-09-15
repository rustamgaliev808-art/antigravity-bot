"""Paths are independent of the polling process working directory."""
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def database_path(name=None, data_dir=None):
    path = Path(name or os.getenv("DB_NAME", "click_lunch_v6.db"))
    root = Path(data_dir or os.getenv("DATA_DIR") or PROJECT_DIR)
    if not root.is_absolute():
        root = PROJECT_DIR / root
    return str(path if path.is_absolute() else root / path)
