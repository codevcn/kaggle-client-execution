"""
core/telegram.py — Telegram & Rclone Services
==============================================
"""

import asyncio
import logging
from typing import List
import datetime

import httpx
import state
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CLONED_DATA_LOCAL_DIR_PATH, RCLONE_CONFIG_PATH

logger = logging.getLogger("local-server")


async def send_telegram_message(message: str) -> None:
    """Gửi tin nhắn thông báo lên Telegram qua Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Tắt gửi Telegram: Chưa cấu hình BOT_TOKEN hoặc CHAT_ID.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"❌ Lỗi gửi Telegram: {resp.text}")
    except Exception as e:
        logger.error(f"❌ Exception khi gửi Telegram: {e}")


def _get_rclone_remote_name(config_path: str) -> str:
    """Đọc tên remote đầu tiên trong rclone.conf. Fallback về 'gdrive' nếu lỗi."""
    import os
    if not os.path.exists(config_path):
        logger.warning(f"⚠️ Không tìm thấy file {config_path}. Dùng mặc định 'gdrive'.")
        return "gdrive"
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    remote_name = line[1:-1]
                    return remote_name
    except Exception as e:
        logger.error(f"❌ Lỗi đọc rclone config {config_path}: {e}")
    return "gdrive"


async def handle_rclone_downloads(urls_to_handle: List[str], job_id: str = "unknown", notebook_title: str = "unknown") -> None:
    """
    Tải nhiều GDrive folder qua rclone đồng thời dựa trên danh sách URL.
    Sử dụng asyncio.gather để song song hóa các tiến trình.
    """
    if not urls_to_handle:
        return

    import os
    import datetime
    import re
    remote_name = _get_rclone_remote_name(RCLONE_CONFIG_PATH)

    async def _download_single(url: str):
        # Trích xuất folder_id từ nhiều dạng URL GDrive:
        #   1. https://drive.google.com/drive/folders/FOLDER_ID
        #   2. https://drive.google.com/open?id=FOLDER_ID
        #   3. https://drive.google.com/file/d/FILE_ID/view
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        if "id" in qs:
            # Dạng ?id=FOLDER_ID (open, uc, export...)
            folder_id = qs["id"][0]
        else:
            # Dạng /folders/FOLDER_ID hoặc /d/FILE_ID
            parts = [p for p in parsed.path.split("/") if p]
            folder_id = parts[-1] if parts else ""

        if not folder_id or folder_id in ("open", "view", "edit"):
            logger.error(f"❌ Không thể trích xuất folder_id hợp lệ từ URL: {url}")
            await send_telegram_message(f"❌ URL GDrive không hợp lệ, không tìm được ID:\n<code>{url}</code>")
            return
        
        # Xử lý prefix cho thư mục tải về: {job_id}-{notebook_title}-{date.now()}
        # Làm sạch notebook_title tránh ký tự đặc biệt của OS
        safe_title = re.sub(r'[\\/*?:"<>|]', "", notebook_title).strip()
        safe_title = safe_title.replace(" ", "_")
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{job_id}-{safe_title}-{now_str}"
        
        local_target_dir = os.path.join(CLONED_DATA_LOCAL_DIR_PATH, folder_name)

        msg_start = f"⏳ Bắt đầu tải dữ liệu từ {url}\nThư mục đích: <code>{local_target_dir}</code>"
        logger.info(f"⬇️ {msg_start}")
        await send_telegram_message(msg_start)

        cmd = [
            "rclone",
            "copy",
            f"{remote_name}:",
            local_target_dir,
            "--drive-root-folder-id", folder_id,
            "--config", RCLONE_CONFIG_PATH,
            "-v"
        ]

        logger.info(f"🚀 Lệnh chạy rclone: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                msg = f"✅ Tải thành công từ {url}"
                logger.info(msg)
                await send_telegram_message(msg)

                # Đăng ký folder vào state để hiển thị trên UI
                state.downloaded_folders.append({
                    "name": folder_name,
                    "path": local_target_dir,
                    "source_url": url,
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                err_text = stderr.decode()[:500]
                msg = f"❌ Lỗi rclone tải {url}:\n<pre>{err_text}</pre>"
                logger.error(msg)
                await send_telegram_message(msg)
        except Exception as e:
            logger.error(f"❌ Lỗi thực thi rclone: {e}")
            await send_telegram_message(f"❌ Lỗi hệ thống khi tải từ {url}: {str(e)}")

    # Khởi chạy song song
    tasks = [_download_single(url) for url in urls_to_handle]
    await asyncio.gather(*tasks)
