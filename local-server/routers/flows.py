"""
routers/flows.py — Flow management API
========================================
Endpoints:
  POST /api/run-flows     : khởi chạy flow pipeline
  GET  /api/flow-status   : lấy trạng thái + log stream (hỗ trợ offset)
  POST /api/stop-flows    : dừng khẩn cấp flow đang chạy
"""

from fastapi import APIRouter, HTTPException

from state import flow_manager

router = APIRouter(prefix="/api", tags=["flows"])


@router.post("/run-flows")
async def run_flows():
    """Khởi chạy tất cả flow bằng orchestrator chính."""
    if flow_manager.is_running():
        raise HTTPException(
            status_code=400,
            detail="Một tiến trình chạy flow đang diễn ra.",
        )
    success = await flow_manager.run()
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Không thể khởi chạy các flow.",
        )
    return {"success": True, "message": "Bắt đầu chạy tất cả flow."}


@router.get("/flow-status")
def get_flow_status(offset: int = 0):
    """
    Lấy trạng thái và các dòng log mới của tiến trình chạy flow.
    Dùng `offset` để chỉ lấy các dòng log mới (log streaming pattern).
    """
    return {
        "is_running": flow_manager.is_running(),
        "returncode": flow_manager.returncode,
        "logs": flow_manager.logs[offset:],
    }


@router.post("/stop-flows")
async def stop_flows():
    """Dừng khẩn cấp tiến trình chạy flow."""
    if not flow_manager.is_running():
        return {"success": True, "message": "Không có tiến trình nào đang chạy."}
    await flow_manager.stop()
    return {"success": True, "message": "Đã ngắt tiến trình chạy flow."}
