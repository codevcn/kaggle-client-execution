"""
models.py — Pydantic request/response models
=============================================
Tất cả Pydantic models dùng chung trong local-server.
Module này không import bất kỳ module nội bộ nào.
"""

from typing import Optional

from pydantic import BaseModel


class TestPayload(BaseModel):
    """Payload giả lập nhận dữ liệu từ Remote Server (dùng cho endpoint test)."""

    action: str
    job_id: str
    data: Optional[dict] = None
