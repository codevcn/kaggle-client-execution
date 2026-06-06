"""
core/telegram.py — Telegram notifications & rclone GDrive downloader
=====================================================================
Cung cấp:
  - send_telegram_message(message)       : gửi thông báo Telegram async
  - handle_rclone_downloads(urls)        : tải nhiều GDrive folder qua rclone
  - _extract_gdrive_id(url)              : trích folder ID từ GDrive URL (private)
  - _get_rclone_remote_name(config_path) : đọc tên remote đầu tiên từ rclone.conf (private)
"""

import asyncio
import logging
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from config import (
    CLONED_DATA_LOCAL_DIR_PATH,
    RCLONE_CONFIG_PATH,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

logger = logging.getLogger("local-server")


# ─────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────


async def send_telegram_message(message: str) -> None:
    """Gửi tin nhắn văn bản đến Telegram chat qua Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "⚠️ Không thể gửi Telegram vì thiếu cấu hình "
            "TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID."
        )
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    ).encode("utf-8")

    def _do_request() -> None:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req):
            pass

    try:
        await asyncio.to_thread(_do_request)
        logger.info("📩 Đã gửi thông báo Telegram thành công.")
    except Exception as e:
        logger.error(f"❌ Lỗi khi gửi thông báo Telegram: {e}")


# ─────────────────────────────────────────────
# rclone helpers (private)
# ─────────────────────────────────────────────


def _extract_gdrive_id(url: str) -> str:
    """Trích folder ID từ GDrive URL dạng /folders/<id> hoặc ?id=<id>."""
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return ""


def _get_rclone_remote_name(config_path: str) -> str:
    """Đọc tên remote đầu tiên trong rclone.conf. Fallback về 'gdrive'."""
    cfg = Path(config_path)
    if not cfg.exists():
        return "gdrive"
    for line in cfg.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            return line[1:-1]
    return "gdrive"


# ─────────────────────────────────────────────
# rclone download handler
# ─────────────────────────────────────────────


async def handle_rclone_downloads(urls_to_handle: list[str]) -> None:
    """
    Tải toàn bộ danh sách GDrive folder URL về local bằng rclone copy.
    Tạo thư mục con {datetime} trong CLONED_DATA_LOCAL_DIR_PATH.
    Gửi thông báo Telegram khi hoàn tất.
    """
    if not urls_to_handle:
        return

    # Tạo thư mục nhận data theo timestamp
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target_dir = Path(CLONED_DATA_LOCAL_DIR_PATH) / now_str
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📂 [RCLONE] Đã tạo thư mục nhận data: {target_dir}")

    remote_name = _get_rclone_remote_name(RCLONE_CONFIG_PATH)

    for url in urls_to_handle:
        folder_id = _extract_gdrive_id(url)
        if not folder_id:
            logger.warning(f"⚠️ [RCLONE] Không thể trích xuất folder ID từ URL: {url}")
            continue

        logger.info(f"⬇️ [RCLONE] Đang tải data từ folder ID: {folder_id}...")

        cmd = [
            "rclone", "copy",
            f"--drive-root-folder-id={folder_id}",
            f"{remote_name}:",
            str(target_dir),
            "--config", RCLONE_CONFIG_PATH,
            "-v",
        ]

        def _run_rclone() -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )

        process = await asyncio.to_thread(_run_rclone)

        if process.returncode == 0:
            logger.info(f"✅ [RCLONE] Tải data thành công từ {url}")
        else:
            logger.error(
                f"❌ [RCLONE] Lỗi khi tải data từ {url}. Output:\n{process.stdout}"
            )

    # Thông báo hoàn tất toàn bộ batch
    msg = (
        f"✅ [LOCAL SERVER] Đã hoàn tất tải toàn bộ "
        f"{len(urls_to_handle)} thư mục GDrive.\n"
        f"📁 Lưu tại: {target_dir}"
    )
    await send_telegram_message(msg)
