import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import threading
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
        os.getenv("MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE", "10000")
    )
except ValueError:
    MS_INTERVAL_CHECK_REMOTE_SERVER_ALIVE = 10000

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
MANAGE_HTML_PATH = Path(__file__).resolve().parent / "manage.html"

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
# BỘ QUẢN LÝ TIẾN TRÌNH CHẠY FLOW (SUBPROCESS ORCHESTRATOR)
# ─────────────────────────────────────────────
class FlowExecutionManager:
    def __init__(self):
        self.process = None
        self.logs = []
        self.thread = None

    async def run(self):
        if self.is_running():
            return False

        self.logs = []

        # Thư mục gốc của project (chứa flow.cmd và src/main.py)
        base_dir = Path(__file__).resolve().parent.parent.parent
        flow_cmd = base_dir / "flow.cmd"

        # ── Xây dựng môi trường sạch, KHÔNG kế thừa VIRTUAL_ENV / PYTHONPATH
        # của local-server để tránh xung đột. flow.cmd sẽ tự activate .venv.
        clean_env = os.environ.copy()
        for var in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
            clean_env.pop(var, None)
        # Loại bỏ đường dẫn .venv/Scripts khỏi PATH để python gốc hệ thống được dùng,
        # sau đó flow.cmd tự kích hoạt .venv đúng cách.
        path_parts = clean_env.get("PATH", "").split(os.pathsep)
        venv_scripts = str(base_dir / ".venv" / "Scripts").lower()
        clean_env["PATH"] = os.pathsep.join(
            p for p in path_parts if p.lower() != venv_scripts
        )
        clean_env["PYTHONIOENCODING"] = "utf-8"
        clean_env["PYTHONUNBUFFERED"] = "1"

        try:
            if flow_cmd.exists():
                # Chạy flow.cmd qua cmd /c — giống như người dùng chạy tay từ terminal
                cmd = ["cmd", "/c", str(flow_cmd)]
            else:
                # Fallback: chạy trực tiếp src/main.py nếu flow.cmd không tồn tại
                logger.warning("⚠️ Không tìm thấy flow.cmd, fallback sang python src/main.py")
                cmd = ["python", "-u", str(base_dir / "src" / "main.py")]

            logger.info(f"▶️ [FLOW] Khởi chạy process mới: {' '.join(cmd)}")
            logger.info(f"   Thư mục làm việc: {base_dir}")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(base_dir),
                env=clean_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                # CREATE_NEW_PROCESS_GROUP: process con có group riêng,
                # không bị tắt khi local-server nhận Ctrl+C
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except Exception as e:
            self.logs.append(f"[SYSTEM ERROR] Không thể khởi chạy tiến trình: {str(e)}")
            logger.error(f"❌ [FLOW] Lỗi khởi chạy: {e}")
            return False

        self.thread = threading.Thread(target=self._read_logs, daemon=True)
        self.thread.start()
        return True

    def _read_logs(self):
        # Đọc từng dòng text stream từ stdout của subprocess
        for line in iter(self.process.stdout.readline, ""):
            stripped_line = line.rstrip("\r\n")
            self.logs.append(stripped_line)
            # In thẳng ra console của local-server để user theo dõi trực tiếp
            sys.stdout.write(stripped_line + "\n")
            sys.stdout.flush()
        self.process.stdout.close()
        self.process.wait()

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def returncode(self) -> Optional[int]:
        if self.process:
            return self.process.poll()
        return None

    async def stop(self):
        if not self.is_running():
            return

        try:
            # Gửi CTRL_BREAK_EVENT cho process group riêng (Windows)
            self.process.send_signal(subprocess.signal.CTRL_BREAK_EVENT)
            for _ in range(50):
                if not self.is_running():
                    break
                await asyncio.sleep(0.1)
            if self.is_running():
                self.process.terminate()
            for _ in range(30):
                if not self.is_running():
                    break
                await asyncio.sleep(0.1)
            if self.is_running():
                self.process.kill()
        except Exception as e:
            self.logs.append(f"[SYSTEM ERROR] Lỗi khi ngắt tiến trình: {str(e)}")


flow_manager = FlowExecutionManager()


# ─────────────────────────────────────────────
# BACKGROUND WORKER (WEBSOCKET CLIENT & PINGER)
# ─────────────────────────────────────────────


async def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "⚠️ Không thể gửi Telegram vì thiếu cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID."
        )
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    ).encode("utf-8")

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

        def run_rclone():
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )

        process = await asyncio.to_thread(run_rclone)

        if process.returncode == 0:
            logger.info(f"✅ [RCLONE] Tải data thành công từ {url}")
        else:
            logger.error(
                f"❌ [RCLONE] Lỗi khi tải data từ {url}. Output:\n{process.stdout}"
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
                    msg = (
                        f"🚀 [LOCAL SERVER] Nhận yêu cầu tải data (action: handle).\n🔗 Số lượng folder: {len(urls_to_handle)}\n"
                        + "\n".join(urls_to_handle)
                    )
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
    # KHI TẮT SERVER: Huỷ background task và dừng các flow con đang chạy
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    if flow_manager.is_running():
        logger.info("⏹️ Đang dừng tiến trình chạy flow...")
        await flow_manager.stop()

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


@app.get("/manage", response_class=HTMLResponse)
def get_manage_page():
    """Trả về giao diện HTML để quản lý config và chạy flow"""
    if not MANAGE_HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file manage.html")
    return MANAGE_HTML_PATH.read_text(encoding="utf-8")


@app.post("/api/run-flows")
async def run_flows():
    """Khởi chạy tất cả flow bằng orchestrator chính"""
    if flow_manager.is_running():
        raise HTTPException(
            status_code=400, detail="Một tiến trình chạy flow đang diễn ra."
        )
    success = await flow_manager.run()
    if not success:
        raise HTTPException(status_code=500, detail="Không thể khởi chạy các flow.")
    return {"success": True, "message": "Bắt đầu chạy tất cả flow."}


@app.get("/api/flow-status")
def get_flow_status(offset: int = 0):
    """Lấy trạng thái và các dòng log mới của tiến trình chạy flow"""
    logs = flow_manager.logs[offset:]
    return {
        "is_running": flow_manager.is_running(),
        "returncode": flow_manager.returncode,
        "logs": logs,
    }


@app.post("/api/stop-flows")
async def stop_flows():
    """Dừng khẩn cấp tiến trình chạy flow"""
    if not flow_manager.is_running():
        return {"success": True, "message": "Không có tiến trình nào đang chạy."}
    await flow_manager.stop()
    return {"success": True, "message": "Đã ngắt tiến trình chạy flow."}


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
    logger.info(f"🔗 Trang quản lý: http://{host}:{port}/manage")
    # Chạy uvicorn với tính năng auto-reload
    uvicorn.run("server:app", host=host, port=port, reload=True)
