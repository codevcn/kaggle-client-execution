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

# Danh sách các folder đã tải về từ GDrive URL qua webhook
# Tự động reset (rỗng) mỗi lần server khởi động lại vì là biến in-memory
downloaded_folders: list[dict] = []
# Mỗi entry: { "name": str, "path": str, "source_url": str, "created_at": str }
