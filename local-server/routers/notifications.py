"""
routers/notifications.py — API quản lý thông báo
===============================================
Cung cấp endpoint để frontend lấy danh sách thông báo và đánh dấu đã đọc.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import state

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("")
def get_notifications():
    """Lấy danh sách thông báo hiện tại."""
    return {"notifications": state.notifications}

@router.post("/read-all")
def mark_all_as_read():
    """Đánh dấu tất cả thông báo đã đọc."""
    for n in state.notifications:
        n["seen"] = True
    return JSONResponse(content={"success": True})

@router.post("/{notif_id}/read")
def mark_as_read(notif_id: int):
    """Đánh dấu một thông báo đã đọc."""
    for n in state.notifications:
        if n["id"] == notif_id:
            n["seen"] = True
            return JSONResponse(content={"success": True})
    return JSONResponse(status_code=404, content={"success": False, "detail": "Not found"})
