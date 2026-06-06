"""
routers/misc.py — Miscellaneous endpoints
==========================================
Endpoints:
  GET  /                  : health check + trạng thái server
  GET  /manage            : serve file manage.html
  POST /receive-test-data : giả lập nhận payload (dùng để test thủ công)
"""

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from config import MANAGE_HTML_PATH
from models import TestPayload
import state

router = APIRouter(tags=["misc"])
logger = logging.getLogger("local-server")


@router.get("/", response_class=JSONResponse)
def root():
    """Endpoint kiểm tra trạng thái Local Server."""
    return JSONResponse(content={
        "status": "local fastapi running",
        "cloudflare_url": state.cloudflare_url
    })


@router.get("/manage", response_class=HTMLResponse)
def get_manage_page():
    """Trả về giao diện HTML để quản lý config và chạy flow."""
    if not MANAGE_HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file manage.html")
    return MANAGE_HTML_PATH.read_text(encoding="utf-8")


@router.post("/receive-test-data")
def receive_test_data(payload: TestPayload):
    """
    API giả lập nhận dữ liệu — dùng để test thủ công.

    Ví dụ:
        curl -X POST "http://127.0.0.1:8000/receive-test-data" \\
             -H "Content-Type: application/json" \\
             -d '{"action":"test","job_id":"job-abc-123","data":{"msg":"Hello"}}'
    """
    print("\n" + "=" * 60)
    logger.info("🔔 [DATA RECEIVED - SIMULATED POST] NHẬN PAYLOAD GIẢ LẬP (POST API):")
    print(json.dumps(payload.dict(), indent=2, ensure_ascii=False))
    print("=" * 60 + "\n")

    return {
        "success": True,
        "message": "Đã giả lập nhận payload thành công. Xem log tại Console của Local Server.",
        "payload_received": payload.dict(),
    }
