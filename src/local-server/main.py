import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.parse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

# Thiết lập encoding UTF-8 cho console để in tiếng Việt không bị lỗi trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load cấu hình từ file .env cùng thư mục
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # Sẽ được cài đặt thông qua file .cmd nếu chạy thực tế

import websockets
from websockets.exceptions import ConnectionClosed

# ─────────────────────────────────────────────
# CẤU HÌNH & LOGGING
# ─────────────────────────────────────────────
REMOTE_WS_URL = os.getenv(
    "REMOTE_WS_URL", "ws://127.0.0.1:8000/ws/local/karina-pc?token=codevcn0008"
)
try:
    MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE = int(
        os.getenv("MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE", "5000")
    )
except ValueError:
    MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE = 5000

CLONED_DATA_LOCAL_DIR_PATH = os.getenv(
    "CLONED_DATA_LOCAL_DIR_PATH",
    "D:/D-Jobs/ae-B6/TikTok-Beta/servers/kaggle-client-execution/media/cloned-data",
)
RCLONE_CONFIG_PATH = os.getenv(
    "RCLONE_CONFIG_PATH", "C:/Users/dell/AppData/Roaming/rclone/rclone.conf"
)

CONFIG_JSON_PATH = (
    Path(__file__).resolve().parent.parent.parent / "configs" / "base_config.json"
)
CONFIG_HTML_PATH = Path(__file__).resolve().parent / "config.html"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Thiết lập logging định dạng trực quan cho Console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("local-server")


# Trạng thái kết nối hiện tại tới Remote Server
class ConnectionStatus:
    is_connected = False
    remote_url = REMOTE_WS_URL
    last_ping_rtt: Optional[float] = None
    last_error: Optional[str] = None


status_tracker = ConnectionStatus()


# ─────────────────────────────────────────────
# BACKGROUND WORKER (WEBSOCKET CLIENT & PINGER)
# ─────────────────────────────────────────────


async def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Không thể gửi Telegram vì thiếu cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }).encode("utf-8")
    
    try:
        def do_request():
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req) as response:
                pass
        await asyncio.to_thread(do_request)
        logger.info("📩 Đã gửi thông báo Telegram thành công.")
    except Exception as e:
        logger.error(f"❌ Lỗi khi gửi thông báo Telegram: {e}")


async def ping_loop(websocket):
    """
    Vòng lặp gửi ping định kỳ đến Remote Server để kiểm tra kết nối và đo độ trễ.
    """
    interval_seconds = MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE / 1000.0
    logger.info(
        f"[PING] Khởi động chu kỳ kiểm tra kết nối (Ping): "
        f"{MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE} ms ({interval_seconds}s)"
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            # Gửi ping frame và đo độ trễ Round Trip Time (RTT)
            start_time = time.perf_counter()
            pong_waiter = await websocket.ping()

            # Đợi phản hồi pong
            await pong_waiter
            rtt = (time.perf_counter() - start_time) * 1000.0

            status_tracker.last_ping_rtt = rtt
            status_tracker.last_error = None

            # In kết quả ping ra console
            logger.info(
                f"🟢 [PING] Kết nối Remote Server ổn định. Độ trễ (RTT): {rtt:.2f} ms"
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(
                f"🔴 [PING ERROR] Lỗi khi gửi ping đến Remote Server: {str(e)}"
            )
            status_tracker.last_error = f"Ping error: {str(e)}"
            # Cho phép ngoại lệ ném lên để vòng lặp cha xử lý kết nối lại
            raise e


def extract_gdrive_id(url: str) -> str:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return ""


def get_rclone_remote_name(config_path: str) -> str:
    cfg = Path(config_path)
    if not cfg.exists():
        return "gdrive"  # Default to gdrive if file not found
    for line in cfg.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            return line[1:-1]
    return "gdrive"


async def handle_rclone_downloads(urls_to_handle: list):
    if not urls_to_handle:
        return

    # Tạo folder con với format {date.now()}
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target_dir = Path(CLONED_DATA_LOCAL_DIR_PATH) / now_str
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📂 [RCLONE] Đã tạo thư mục nhận data: {target_dir}")
    remote_name = get_rclone_remote_name(RCLONE_CONFIG_PATH)

    for url in urls_to_handle:
        folder_id = extract_gdrive_id(url)
        if not folder_id:
            logger.warning(f"⚠️ [RCLONE] Không thể trích xuất folder ID từ URL: {url}")
            continue

        logger.info(f"⬇️ [RCLONE] Đang tải data từ folder ID: {folder_id}...")

        # rclone command using drive root folder ID
        cmd = [
            "rclone",
            "copy",
            f"--drive-root-folder-id={folder_id}",
            f"{remote_name}:",
            str(target_dir),
            "--config",
            RCLONE_CONFIG_PATH,
            "-v",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        stdout, _ = await process.communicate()
        if process.returncode == 0:
            logger.info(f"✅ [RCLONE] Tải data thành công từ {url}")
        else:
            logger.error(
                f"❌ [RCLONE] Lỗi khi tải data từ {url}. Output:\n{stdout.decode(errors='replace')}"
            )

    # Gửi thông báo khi hoàn tất toàn bộ tiến trình tải
    msg = f"✅ [LOCAL SERVER] Đã hoàn tất tải toàn bộ {len(urls_to_handle)} thư mục GDrive.\n📁 Lưu tại: {target_dir}"
    await send_telegram_message(msg)


async def receive_loop(websocket):
    """
    Vòng lặp lắng nghe dữ liệu JSON được gửi về từ Remote Server qua kết nối WebSocket.
    """
    logger.info("📥 [RECEIVER] Sẵn sàng nhận tin nhắn từ Remote Server...")
    while True:
        try:
            message = await websocket.recv()

            # Thử parse dữ liệu nhận được thành JSON để hiển thị đẹp mắt
            try:
                data = json.loads(message)
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)

                print("\n" + "=" * 60)
                logger.info(f"🔔 [DATA RECEIVED] NHẬN GÓI TIN TỪ REMOTE SERVER:")
                print(formatted_json)
                print("=" * 60 + "\n")

                # Logic xử lý payload thực tế
                action = data.get("action")
                urls_to_handle = data.get("urls_to_handle")
                if action == "handle" and isinstance(urls_to_handle, list):
                    # Gửi thông báo Telegram khi bắt đầu
                    msg = f"🚀 [LOCAL SERVER] Nhận yêu cầu tải data (action: handle).\n🔗 Số lượng folder: {len(urls_to_handle)}\n" + "\n".join(urls_to_handle)
                    asyncio.create_task(send_telegram_message(msg))
                    
                    # Khởi chạy background task rclone để không block vòng lặp nhận tin nhắn
                    asyncio.create_task(handle_rclone_downloads(urls_to_handle))

            except json.JSONDecodeError:
                # Nếu không phải JSON, in ra dạng text thô
                print("\n" + "=" * 60)
                logger.info(
                    f"🔔 [DATA RECEIVED - RAW] Nhận dữ liệu thô từ Remote Server:"
                )
                print(message)
                print("=" * 60 + "\n")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"🔴 [RECEIVER ERROR] Lỗi trong luồng nhận tin nhắn: {str(e)}")
            status_tracker.last_error = f"Receive error: {str(e)}"
            raise e


async def websocket_client_worker():
    """
    Worker chinh duy tri ket noi WebSocket toi Remote Server, thuc hien tu dong ket noi lai (auto-reconnect).
    """
    reconnect_delay = 5  # Giây

    while True:
        try:
            logger.info(
                f"🔗 [CONNECTION] Đang kết nối tới Remote Server: {REMOTE_WS_URL}"
            )

            async with websockets.connect(REMOTE_WS_URL) as websocket:
                status_tracker.is_connected = True
                status_tracker.last_error = None
                logger.info("✅ [CONNECTION] Đã kết nối thành công đến Remote Server!")

                # Gui message chao hoi ban dau (Heartbeat/Hello)
                hello_msg = json.dumps(
                    {
                        "type": "hello",
                        "client_id": "local-fastapi-server",
                        "message": "Local FastAPI Server is connected and listening.",
                    }
                )
                await websocket.send(hello_msg)
                logger.info(
                    "📤 [CONNECTION] Đã gửi bản tin đăng ký (hello) lên Remote Server."
                )

                # Chạy đồng thời luồng nhận dữ liệu và luồng ping định kỳ
                # Nếu một trong hai luồng gặp lỗi hoặc kết thúc, asyncio.gather sẽ ném ngoại lệ
                await asyncio.gather(receive_loop(websocket), ping_loop(websocket))

        except (ConnectionClosed, Exception) as e:
            status_tracker.is_connected = False
            status_tracker.last_ping_rtt = None
            status_tracker.last_error = str(e)

            logger.warning(
                f"⚠️ [DISCONNECTED] Mất kết nối hoặc không thể kết nối đến Remote Server."
            )
            logger.warning(f"   Chi tiết lỗi: {str(e)}")
            logger.info(f"   Sẽ tự động kết nối lại sau {reconnect_delay} giây...")

            await asyncio.sleep(reconnect_delay)


# ─────────────────────────────────────────────
# FASTAPI LIFESPAN
# ─────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # KHI KHỞI ĐỘNG SERVER: Chạy background task kết nối WebSocket
    worker_task = asyncio.create_task(websocket_client_worker())
    yield
    # KHI TẮT SERVER: Huỷ background task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("⏹️ Local Server đã dừng.")


app = FastAPI(
    title="Local FastAPI Server",
    description="FastAPI Local Server nhan du lieu tu Remote Server qua WebSocket ngam",
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# ENDPOINTS / APIS
# ─────────────────────────────────────────────


class TestPayload(BaseModel):
    action: str
    job_id: str
    data: Optional[dict] = None


@app.get("/config", response_class=HTMLResponse)
def get_config_page():
    """Trả về giao diện HTML để chỉnh sửa config"""
    if not CONFIG_HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file config.html")
    return CONFIG_HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/configs")
def get_configs():
    """Trả về nội dung file base_config.json"""
    if not CONFIG_JSON_PATH.exists():
        return {"flows": []}
    try:
        data = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file config: {str(e)}")


@app.get("/api/available-filters")
def get_available_filters():
    """Quét thư mục src/filters và trả về danh sách tên filter"""
    filters_dir = Path(__file__).resolve().parent.parent / "filters"
    if not filters_dir.exists():
        return []
    filters = []
    for f in filters_dir.iterdir():
        if f.is_file() and f.name.endswith(".py") and f.name != "__init__.py":
            filters.append(f.stem)
    return sorted(filters)


@app.post("/api/configs")
async def save_configs(request: Request):
    """Lưu data JSON vào file base_config.json"""
    try:
        data = await request.json()
        CONFIG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_JSON_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {"success": True, "message": "Đã lưu cấu hình"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file config: {str(e)}")


@app.get("/")
def root():
    """
    Endpoint kiem tra trang thai Local Server.
    """
    return JSONResponse(
        content={
            "status": "local fastapi running",
            "websocket_client": {
                "remote_url": status_tracker.remote_url,
                "connected": status_tracker.is_connected,
                "last_ping_rtt_ms": status_tracker.last_ping_rtt,
                "last_error": status_tracker.last_error,
                "ping_interval_ms": MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE,
            },
        }
    )


@app.post("/receive-test-data")
def receive_test_data(payload: TestPayload):
    """
    API gia lap nhan du lieu tu Remote Server.
    Dung de test thu cong bang cach goi:
    curl -X POST "http://127.0.0.1:8000/receive-test-data" -H "Content-Type: application/json" -d "{\"action\":\"test\",\"job_id\":\"job-abc-123\",\"data\":{\"msg\":\"Hello local console\"}}"
    """
    # In ra console dung dinh dang giong nhu nhan tu WebSocket
    print("\n" + "=" * 60)
    logger.info(f"🔔 [DATA RECEIVED - SIMULATED POST] NHẬN PAYLOAD GIẢ LẬP (POST API):")
    formatted_json = json.dumps(payload.dict(), indent=2, ensure_ascii=False)
    print(formatted_json)
    print("=" * 60 + "\n")

    return {
        "success": True,
        "message": "Đã giả lập nhận payload thành công. Xem log tại Console của Local Server.",
        "payload_received": payload.dict(),
    }


if __name__ == "__main__":
    import uvicorn

    # Đọc cấu hình host/port để khởi động
    host = os.getenv("LOCAL_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("LOCAL_PORT", "8000"))
    except ValueError:
        port = 8000

    logger.info(f"🚀 Khởi động Local FastAPI Server tại http://{host}:{port}")
    logger.info(f"🔗 Trang cấu hình: http://{host}:{port}/config")
    # Chạy uvicorn với tính năng auto-reload
    uvicorn.run("main:app", host=host, port=port, reload=True)
