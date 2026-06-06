"""
state.py — Global singleton instances
=======================================
Điểm khởi tạo duy nhất cho các singleton dùng chung giữa routers và core workers.

Tại sao cần file riêng này?
  - Tránh circular import: routers cần flow_manager & status_tracker,
    core workers không cần import ngược lại.
  - Singleton guarantee: chỉ một instance tồn tại trong suốt lifetime của app.
"""

from core.flow_manager import FlowExecutionManager
from core.ws_client import ConnectionStatus

# Singleton trạng thái kết nối WebSocket tới Remote Server
status_tracker = ConnectionStatus()

# Singleton quản lý subprocess chạy flow pipeline
flow_manager = FlowExecutionManager()
