"""
routers/webhook.py — Webhook Router cho Kaggle
===============================================
Nhận webhook từ các Kaggle Notebook báo cáo tiến trình.
Thực hiện:
- Gửi Telegram notification.
- Xử lý Rclone download nếu có GDrive URL.
- Kích hoạt notebook tiếp theo (start/mid -> trigger next).
"""

import asyncio
import logging
import re

from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from config import SERVER_API_KEY
from models import WebhookPayload
from core.telegram import send_telegram_message, handle_rclone_downloads
from core.kaggle_orchestrator import trigger_next_notebook

router = APIRouter(tags=["webhook"])
logger = logging.getLogger("local-server")


async def process_webhook_background(payload: WebhookPayload):
    """Xử lý webhook trong background để trả về HTTP 200 ngay lập tức."""
    logger.info(f"🔔 [WEBHOOK] Bắt đầu xử lý Job: {payload.job_id}")

    # 1. Gửi Telegram Message
    msg: str = f"🔔 <b>[WEBHOOK] Kaggle Message</b>\n"
    msg += f"<b>Job ID:</b> <code>{payload.job_id}</code>\n"
    msg += f"<b>Notebook Title:</b> {payload.notebook_title}\n"
    msg += f"<b>Type:</b> {payload.notebook_index_type}\n"
    msg += f"<b>Status:</b> {payload.status}\n"
    if payload.progress:
        msg += f"<b>Progress:</b> {payload.progress}\n"
    if payload.text_data:
        msg += f"<b>Data:</b> {payload.text_data[:200]}...\n"

    await send_telegram_message(msg)

    # 2. Rclone Download (nếu có text_data chứa URL GDrive)
    if payload.text_data and ("drive.google.com" in payload.text_data):
        # Trích xuất URL
        urls = re.findall(r"(https?://drive\.google\.com[^\s]+)", payload.text_data)
        if urls:
            logger.info(
                f"📥 Phát hiện {len(urls)} GDrive URL. Bắt đầu rclone download..."
            )
            await handle_rclone_downloads(urls, payload.job_id, payload.notebook_title)

    # 3. Trigger Notebook tiếp theo
    if payload.status == "completed":
        if (
            payload.notebook_index_type in ["start", "mid"]
            and payload.next_notebook_ref
        ):
            logger.info(
                f"➡️ Chuẩn bị trigger notebook tiếp theo: {payload.next_notebook_ref}"
            )
            await trigger_next_notebook(payload.next_notebook_ref)
        elif payload.notebook_index_type == "end" or payload.progress == "done":
            end_msg = f"🎉 <b>[PIPELINE COMPLETE]</b>\nJob <code>{payload.job_id}</code> đã hoàn tất toàn bộ tiến trình!"
            logger.info(end_msg)
            await send_telegram_message(end_msg)


@router.post("/webhook/notebook")
async def receive_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None),
):
    """Cổng nhận Webhook từ Kaggle."""
    if x_api_key != SERVER_API_KEY:
        logger.warning(
            f"⚠️ Webhook bị từ chối: Sai X-API-Key. Received: '{x_api_key}', Expected: '{SERVER_API_KEY}'"
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info(
        f"📥 [WEBHOOK RECEIVED] Job: {payload.job_id} | Status: {payload.status}"
    )

    # Cho vào background task để Kaggle nhận HTTP 200 ngay
    background_tasks.add_task(process_webhook_background, payload)

    return JSONResponse(content={"success": True, "message": "Webhook received"})
