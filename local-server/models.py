"""
models.py — Pydantic request/response models
=============================================
Tất cả Pydantic models dùng chung trong local-server.
Module này không import bất kỳ module nội bộ nào.
"""

from typing import Optional

from pydantic import BaseModel


class TestPayload(BaseModel):
    """Payload giả lập dùng để test endpoint /receive-test-data."""

    action: str
    job_id: str
    data: Optional[dict] = None


class WebhookPayload(BaseModel):
    job_id: str
    notebook_title: str
    notebook_index_type: str  # start, mid, end
    status: str
    progress: Optional[str] = None
    next_notebook_ref: Optional[str] = None
    text_data: Optional[str] = None
