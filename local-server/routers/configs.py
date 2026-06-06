"""
routers/configs.py — Config file API
=======================================
Endpoints:
  GET  /api/configs : đọc nội dung base_config.json
  POST /api/configs : ghi dữ liệu JSON vào base_config.json
"""

import json

from fastapi import APIRouter, HTTPException, Request

from config import CONFIG_JSON_PATH

router = APIRouter(prefix="/api", tags=["configs"])


@router.get("/configs")
def get_configs():
    """Trả về nội dung file base_config.json dưới dạng JSON."""
    if not CONFIG_JSON_PATH.exists():
        return {"flows": []}
    try:
        return json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi đọc file config: {str(e)}",
        )


@router.post("/configs")
async def save_configs(request: Request):
    """Lưu data JSON vào file base_config.json (ghi đè toàn bộ)."""
    try:
        data = await request.json()
        CONFIG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_JSON_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"success": True, "message": "Đã lưu cấu hình"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi lưu file config: {str(e)}",
        )
