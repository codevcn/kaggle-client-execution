"""
core/ws_client.py — WebSocket client worker
============================================
Cung cấp:
  - ConnectionStatus           : dataclass trạng thái kết nối (injected vào worker)
  - websocket_client_worker()  : vòng lặp kết nối/reconnect chính (nhận status là param)
  - ping_loop()                : gửi ping định kỳ và đo RTT
  - receive_loop()             : lắng nghe và xử lý message JSON từ Remote Server

Thiết kế: tất cả function nhận `status: ConnectionStatus` là parameter thay vì
truy cập global, giúp dễ test và tránh side effects khi import.
"""

import asyncio
import json
import logging
import time
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed

from config import MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE, REMOTE_WS_URL
from core.telegram import handle_rclone_downloads, send_telegram_message

logger = logging.getLogger("local-server")


# ─────────────────────────────────────────────
# Trạng thái kết nối
# ─────────────────────────────────────────────


class ConnectionStatus:
    """Lưu trạng thái kết nối WebSocket hiện tại tới Remote Server."""

    def __init__(self) -> None:
        self.is_connected: bool = False
        self.remote_url: str = REMOTE_WS_URL
        self.last_ping_rtt: Optional[float] = None
        self.last_error: Optional[str] = None


# ─────────────────────────────────────────────
# Ping loop
# ─────────────────────────────────────────────


async def ping_loop(websocket, status: ConnectionStatus) -> None:
    """
    Vòng lặp gửi ping định kỳ đến Remote Server để kiểm tra kết nối và đo RTT.
    Ném exception nếu ping thất bại để vòng lặp cha xử lý reconnect.
    """
    interval_seconds = MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE / 1000.0
    logger.info(
        f"[PING] Khởi động chu kỳ kiểm tra kết nối: "
        f"{MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE} ms ({interval_seconds}s)"
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            start = time.perf_counter()
            pong_waiter = await websocket.ping()
            await pong_waiter
            rtt = (time.perf_counter() - start) * 1000.0

            status.last_ping_rtt = rtt
            status.last_error = None
            logger.info(
                f"🟢 [PING] Kết nối Remote Server ổn định. Độ trễ (RTT): {rtt:.2f} ms"
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"🔴 [PING ERROR] Lỗi khi gửi ping đến Remote Server: {str(e)}")
            status.last_error = f"Ping error: {str(e)}"
            raise  # Cho phép ngoại lệ ném lên để vòng lặp cha xử lý reconnect


# ─────────────────────────────────────────────
# Receive loop
# ─────────────────────────────────────────────


async def receive_loop(websocket, status: ConnectionStatus) -> None:
    """
    Vòng lặp lắng nghe dữ liệu JSON từ Remote Server qua WebSocket.
    Xử lý action 'handle' bằng cách trigger rclone download background task.
    """
    logger.info("📥 [RECEIVER] Sẵn sàng nhận tin nhắn từ Remote Server...")

    while True:
        try:
            message = await websocket.recv()

            try:
                data = json.loads(message)
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)

                print("\n" + "=" * 60)
                logger.info("🔔 [DATA RECEIVED] NHẬN GÓI TIN TỪ REMOTE SERVER:")
                print(formatted_json)
                print("=" * 60 + "\n")

                # ── Xử lý action 'handle' ────────────────────────────────
                action = data.get("action")
                urls_to_handle = data.get("urls_to_handle")
                if action == "handle" and isinstance(urls_to_handle, list):
                    msg = (
                        f"🚀 [LOCAL SERVER] Nhận yêu cầu tải data (action: handle).\n"
                        f"🔗 Số lượng folder: {len(urls_to_handle)}\n"
                        + "\n".join(urls_to_handle)
                    )
                    asyncio.create_task(send_telegram_message(msg))
                    asyncio.create_task(handle_rclone_downloads(urls_to_handle))

            except json.JSONDecodeError:
                # Nếu không phải JSON, in ra dạng text thô
                print("\n" + "=" * 60)
                logger.info("🔔 [DATA RECEIVED - RAW] Nhận dữ liệu thô từ Remote Server:")
                print(message)
                print("=" * 60 + "\n")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"🔴 [RECEIVER ERROR] Lỗi trong luồng nhận tin nhắn: {str(e)}")
            status.last_error = f"Receive error: {str(e)}"
            raise  # Cho phép vòng lặp cha xử lý reconnect


# ─────────────────────────────────────────────
# WebSocket client worker (main)
# ─────────────────────────────────────────────


async def websocket_client_worker(status: ConnectionStatus) -> None:
    """
    Worker chính duy trì kết nối WebSocket tới Remote Server.
    Tự động kết nối lại (auto-reconnect) khi mất kết nối.
    Chạy song song ping_loop và receive_loop; nếu một trong hai lỗi → reconnect.
    """
    reconnect_delay = 5  # giây

    while True:
        try:
            logger.info(
                f"🔗 [CONNECTION] Đang kết nối tới Remote Server: {REMOTE_WS_URL}"
            )

            async with websockets.connect(REMOTE_WS_URL) as websocket:
                status.is_connected = True
                status.last_error = None
                logger.info("✅ [CONNECTION] Đã kết nối thành công đến Remote Server!")

                # Gửi bản tin đăng ký (hello/heartbeat)
                hello_msg = json.dumps({
                    "type": "hello",
                    "client_id": "local-fastapi-server",
                    "message": "Local FastAPI Server is connected and listening.",
                })
                await websocket.send(hello_msg)
                logger.info(
                    "📤 [CONNECTION] Đã gửi bản tin đăng ký (hello) lên Remote Server."
                )

                # Chạy đồng thời receive + ping;
                # nếu một trong hai lỗi → asyncio.gather ném exception → reconnect
                await asyncio.gather(
                    receive_loop(websocket, status),
                    ping_loop(websocket, status),
                )

        except (ConnectionClosed, Exception) as e:
            status.is_connected = False
            status.last_ping_rtt = None
            status.last_error = str(e)

            logger.warning(
                "⚠️ [DISCONNECTED] Mất kết nối hoặc không thể kết nối đến Remote Server."
            )
            logger.warning(f"   Chi tiết lỗi: {str(e)}")
            logger.info(f"   Sẽ tự động kết nối lại sau {reconnect_delay} giây...")

            await asyncio.sleep(reconnect_delay)
