"""
state.py — Global singleton instances
=======================================
Điểm khởi tạo duy nhất cho các singleton dùng chung giữa routers và core workers.

Tại sao cần file riêng này?
  - Tránh circular import: routers cần flow_manager,
    core workers không cần import ngược lại.
  - Singleton guarantee: chỉ một instance tồn tại trong suốt lifetime của app.
"""

from core.flow_manager import FlowExecutionManager

# Singleton quản lý subprocess chạy flow pipeline
flow_manager = FlowExecutionManager()

# URL Public của Cloudflare Tunnel (sẽ được cập nhật khi tunnel khởi động)
cloudflare_url: str | None = None
