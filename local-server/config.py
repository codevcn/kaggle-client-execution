"""
config.py — Cấu hình tập trung
================================
Tất cả biến môi trường, đường dẫn tĩnh, và khởi tạo logging.
Module này là "lá" trong dependency tree — không import bất kỳ module nội bộ nào.
"""

import logging
import os
import sys
from pathlib import Path

# ─────────────────────────────────────────────
# Fix encoding UTF-8 cho console Windows
# (phải chạy TRƯỚC logging.basicConfig)
# ─────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────
# Load .env cùng thư mục local-server/
# ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except ImportError:
    pass  # Sẽ được cài qua run-server.cmd nếu chạy thực tế

# ─────────────────────────────────────────────
# Đường dẫn gốc
# __file__            → local-server/config.py
# .parent             → local-server/
# .parent.parent      → kaggle-client-execution/   (project root)
# ─────────────────────────────────────────────
LOCAL_SERVER_DIR: Path = Path(__file__).resolve().parent
BASE_DIR: Path = LOCAL_SERVER_DIR.parent

MANAGE_HTML_PATH: Path = LOCAL_SERVER_DIR / "manage.html"
CONFIG_JSON_PATH: Path = BASE_DIR / "configs" / "base_config.json"
FILTERS_DIR: Path = BASE_DIR / "src" / "filters"
DOCS_DIR: Path = BASE_DIR / "doc"

# ─────────────────────────────────────────────
# WebSocket — kết nối tới Remote Server
# ─────────────────────────────────────────────
REMOTE_WS_URL: str = os.getenv(
    "REMOTE_WS_URL",
    "ws://127.0.0.1:8000/ws/local/karina-pc?token=codevcn0008",
)

try:
    MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE: int = int(
        os.getenv("MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE", "10000")
    )
except ValueError:
    MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE = 10000

# ─────────────────────────────────────────────
# rclone / GDrive
# ─────────────────────────────────────────────
CLONED_DATA_LOCAL_DIR_PATH: str = os.getenv(
    "CLONED_DATA_LOCAL_DIR_PATH",
    str(BASE_DIR / "media" / "cloned-data"),
)
RCLONE_CONFIG_PATH: str = os.getenv(
    "RCLONE_CONFIG_PATH",
    "C:/Users/dell/AppData/Roaming/rclone/rclone.conf",
)

# ─────────────────────────────────────────────
# Telegram Bot
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")

# ─────────────────────────────────────────────
# HTTP Server
# ─────────────────────────────────────────────
LOCAL_HOST: str = os.getenv("LOCAL_HOST", "127.0.0.1")
try:
    LOCAL_PORT: int = int(os.getenv("LOCAL_PORT", "8000"))
except ValueError:
    LOCAL_PORT = 8000

# ─────────────────────────────────────────────
# Logging — thiết lập một lần duy nhất tại đây
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
