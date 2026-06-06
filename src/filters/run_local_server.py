"""
Filter: run_local_server.py
======================================
Khởi chạy local server qua file local-server/run-server.cmd.
Nếu server HTTP phản hồi thành công (GET / → 200) → Filter thành công.
Nếu thất bại hoặc timeout → Filter thất bại và ném lỗi.
"""

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
SRC_DIR = FILTER_DIR.parent                   # …/src/
ROOT_DIR = SRC_DIR.parent                     # …/kaggle-client-execution/
CMD_PATH = ROOT_DIR / "local-server" / "run-server.cmd"

# Thời gian tối đa chờ server HTTP phản hồi (giây)
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


def is_server_up() -> bool:
    """Trả về True nếu HTTP API của local server phản hồi 200."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=2) as res:
            return res.status == 200
    except Exception:
        return False


def main() -> None:
    logger.info("=" * 60)
    logger.info("🚦 BẮT ĐẦU FILTER: run_local_server")
    logger.info("=" * 60)

    try:
        # 1. Kiểm tra server đã chạy chưa
        if is_server_up():
            logger.info("✅ Local Server ĐÃ ĐANG CHẠY và phản hồi HTTP.")
            logger.info("✅ FILTER HOÀN TẤT.")
            sys.exit(0)

        # 2. Khởi chạy server nếu chưa chạy
        logger.info(f"🚀 Bắt đầu khởi chạy Local Server qua file: {CMD_PATH}")
        if not CMD_PATH.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {CMD_PATH}")

        # Mở cửa sổ Console mới trên Windows để chạy local server (độc lập)
        CREATE_NEW_CONSOLE = 0x00000010
        subprocess.Popen(
            ["cmd.exe", "/c", str(CMD_PATH)],
            cwd=str(CMD_PATH.parent),
            creationflags=CREATE_NEW_CONSOLE,
        )
        logger.info("⏳ Đã gửi lệnh khởi chạy. Đang đợi Local Server phản hồi HTTP...")

        # 3. Vòng lặp chờ server HTTP sẵn sàng
        max_retries = int(MAX_WAIT_SECONDS / 2)
        for i in range(max_retries):
            time.sleep(2)
            if is_server_up():
                logger.info("✅ Local Server đã khởi động và phản hồi HTTP thành công!")
                logger.info("✅ FILTER HOÀN TẤT.")
                sys.exit(0)
            else:
                logger.info(f"⏳ Đang chờ Local Server HTTP API khởi động... ({(i + 1) * 2}/{MAX_WAIT_SECONDS}s)")

        raise TimeoutError(
            f"Quá thời gian chờ {MAX_WAIT_SECONDS}s: Local Server không phản hồi HTTP."
        )

    except Exception as exc:
        logger.error(f"❌ FILTER THẤT BẠI: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
