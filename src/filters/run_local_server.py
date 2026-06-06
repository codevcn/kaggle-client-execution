"""
Filter: run_local_server.py
======================================
Khởi chạy local server qua file local-server/run-server.cmd.
Nếu chạy thành công và local server kết nối/ping tới remote server thành công -> Filter thành công.
Nếu thất bại hoặc timeout -> Filter thất bại và ném lỗi.
"""

import json
import logging
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─────────────────────────────────────────────
# Đường dẫn gốc
# ─────────────────────────────────────────────
FILTER_DIR = Path(__file__).resolve().parent  # …/src/filters/
SRC_DIR = FILTER_DIR.parent  # …/src/
ROOT_DIR = SRC_DIR.parent  # …/kaggle-client-execution/
CMD_PATH = ROOT_DIR / "local-server" / "run-server.cmd"

# Cấu hình thời gian tối đa để chờ server khởi động và ping thành công (giây)
MAX_WAIT_SECONDS = 30


# Fix UnicodeEncodeError khi log tiếng Việt trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [filter:run_local_server]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def check_server_status() -> dict:
    """Gọi API nội bộ của local server để lấy trạng thái kết nối."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/")
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass
    return {}


def main() -> None:
    logger.info("=" * 60)
    logger.info("🚦 BẮT ĐẦU FILTER: run_local_server")
    logger.info("=" * 60)

    try:
        # 1. Kiểm tra xem server đã chạy và kết nối ổn chưa
        status = check_server_status()
        if status:
            ws_client = status.get("websocket_client", {})
            if (
                ws_client.get("connected")
                and ws_client.get("last_ping_rtt_ms") is not None
            ):
                logger.info(
                    "✅ Local Server ĐÃ ĐANG CHẠY và đã kết nối thành công tới Remote Server."
                )
                logger.info("✅ FILTER HOÀN TẤT.")
                sys.exit(0)
            else:
                logger.warning(
                    "⚠️ Local Server đang chạy nhưng chưa kết nối hoàn toàn. Sẽ tiếp tục theo dõi..."
                )
        else:
            # 2. Khởi chạy server nếu chưa chạy
            logger.info(f"🚀 Bắt đầu khởi chạy Local Server qua file: {CMD_PATH}")
            if not CMD_PATH.exists():
                raise FileNotFoundError(f"Không tìm thấy file: {CMD_PATH}")

            # Mở một cửa sổ Console mới trên Windows để chạy local server (độc lập)
            CREATE_NEW_CONSOLE = 0x00000010
            subprocess.Popen(
                ["cmd.exe", "/c", str(CMD_PATH)],
                cwd=str(CMD_PATH.parent),
                creationflags=CREATE_NEW_CONSOLE,
            )
            logger.info(
                "⏳ Đã gửi lệnh khởi chạy (Cửa sổ Console mới sẽ hiện lên). Đang đợi Local Server phản hồi..."
            )

        # 3. Vòng lặp chờ server khởi động và ping thành công
        max_retries = int(MAX_WAIT_SECONDS / 2)
        for i in range(max_retries):
            time.sleep(2)
            status = check_server_status()

            if status:
                ws_client = status.get("websocket_client", {})
                is_connected = ws_client.get("connected")
                rtt = ws_client.get("last_ping_rtt_ms")
                last_err = ws_client.get("last_error")

                if is_connected and rtt is not None:
                    logger.info(
                        f"✅ Local Server đã kết nối thành công tới Remote Server! (Ping RTT: {rtt:.2f}ms)"
                    )
                    logger.info("✅ FILTER HOÀN TẤT.")
                    sys.exit(0)
                else:
                    if last_err:
                        logger.warning(
                            f"⏳ Đang chờ kết nối... (Lỗi gần nhất: {last_err})"
                        )
                    else:
                        logger.info("⏳ Đang chờ kết nối tới Remote Server...")
            else:
                logger.info("⏳ Đang chờ Local Server HTTP API khởi động...")

        # Quá thời gian mà chưa kết nối thành công
        raise TimeoutError(
            f"Quá thời gian chờ {MAX_WAIT_SECONDS}s: Local server không thể kết nối tới remote server hoặc không phản hồi ping."
        )

    except Exception as exc:
        logger.error(f"❌ FILTER THẤT BẠI: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
