"""Local visual preview: temporary synthetic database, no Telegram polling."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aiohttp import web
import main
from lunch_api import create_app

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="click-lunch-preview-") as directory:
        main.DB_NAME = str(Path(directory) / "synthetic.db")
        main.TOKEN = "synthetic-preview-only"
        main.ADMIN_ID = 900
        main.BOT_USERNAME = ""
        main.API_ALLOWED_ORIGINS = ["http://127.0.0.1:3000", "http://localhost:3000", "http://127.0.0.1:3001", "http://localhost:3001"]
        main.init_db()
        web.run_app(create_app(main), host="127.0.0.1", port=8089, access_log=None)
