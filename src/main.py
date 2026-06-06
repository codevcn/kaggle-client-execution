"""
Kaggle Client Execution - Main Orchestrator
===========================================
Đọc cấu hình từ base_config.json, thiết lập logging,
chạy các entrance filter, và điều phối các luồng xử lý cụ thể.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────
# Đường dẫn gốc
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # …/kaggle-client-execution/
CONFIG_PATH = BASE_DIR / "configs" / "base_config.json"
TMP_DIR = BASE_DIR / "tmp"
FILTERS_DIR = BASE_DIR / "src" / "filters"
_LOG_FILE = BASE_DIR / "runtime.log"

# ─────────────────────────────────────────────
# Cấu hình logging
# ─────────────────────────────────────────────
_log_formatter = logging.Formatter(
    fmt="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_log_formatter)

_file_handler = logging.FileHandler(_LOG_FILE, mode="w", encoding="utf-8")
_file_handler.setFormatter(_log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_console_handler, _file_handler],
)
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file config: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def run_entrance_filters(entrance_filters: list[dict]) -> bool:
    if not entrance_filters:
        return True

    total = len(entrance_filters)
    logger.info(f"  🔍 Chạy {total} entrance filter(s)...")

    for idx, f_cfg in enumerate(entrance_filters, start=1):
        filter_name: str = f_cfg.get("name", "").strip()
        if not filter_name:
            logger.warning(f"  ⚠️  Filter #{idx} thiếu trường 'name' — bỏ qua.")
            continue

        filter_file = FILTERS_DIR / f"{filter_name}.py"
        if not filter_file.exists():
            logger.error(f"  ❌ Không tìm thấy filter file: {filter_file} — dừng flow.")
            return False

        logger.info(f"  ▶️  [{idx}/{total}] Chạy filter: {filter_name}.py")
        process = subprocess.Popen(
            [sys.executable, "-u", str(filter_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    logger.info(f"       [filter:{filter_name}] {line}")
            process.wait()
        except KeyboardInterrupt:
            logger.warning(f"\n  ⚠️  Người dùng đã ngắt (Hủy) filter '{filter_name}' bằng phím tắt!")
            process.terminate()
            process.wait(timeout=5)
            return False

        if process.returncode != 0:
            logger.error(
                f"  ❌ Filter '{filter_name}' thất bại "
                f"(returncode={process.returncode}) — dừng flow."
            )
            return False

        logger.info(f"  ✅ Filter '{filter_name}' hoàn tất.")

    logger.info(f"  🌟 Tất cả {total} filter đã chạy xong.")
    return True


def run_all_flows(config: dict) -> None:
    flows: list[dict] = config.get("flows", [])
    if not flows:
        logger.warning("⚠️  Không có flow nào trong config. Kết thúc.")
        return

    total_flows = len(flows)
    logger.info(f"🗂️  Tổng số flow: {total_flows}")
    logger.info("=" * 60)

    for flow_idx, flow in enumerate(flows, start=1):
        title: str = flow.get("flow_title", f"Flow {flow_idx}")
        skip: bool = flow.get("skip", False)

        if skip:
            logger.info(f"\n{'═'*60}")
            logger.info(f"⏭️  BỎ QUA FLOW {flow_idx}/{total_flows}: {title}")
            logger.info(f"{'═'*60}")
            continue

        logger.info(f"\n{'═'*60}")
        logger.info(f"▶  FLOW {flow_idx}/{total_flows}: {title}")
        
        entrance_filters: list[dict] = flow.get("entrance_filters", [])
        if entrance_filters:
            logger.info(f"   entrance_filters   : {[f.get('name') for f in entrance_filters]}")

        # ── Bước 0: Chạy entrance filters ─────────────────────────
        filters_ok = run_entrance_filters(entrance_filters)
        if not filters_ok:
            logger.error(f"  ❌ Flow {flow_idx}: Entrance filter thất bại — bỏ qua flow này.")
            continue

        # ── Route flow ──────────────────────────────────────────
        try:
            from sub_dub_video_on_kaggle import run_feature
            run_feature(flow, flow_idx, total_flows, TMP_DIR)
        except Exception as e:
            logger.error(f"  ❌ Lỗi khi chạy flow '{title}': {e}")

    logger.info(f"\n{'═'*60}")
    logger.info("🏁 Đã xử lý xong tất cả các flow.")
    logger.info(f"{'═'*60}\n")


if __name__ == "__main__":
    logger.info("🚀 Khởi động Kaggle Client Execution")
    logger.info(f"   Config  : {CONFIG_PATH}")
    logger.info(f"   Tmp dir : {TMP_DIR}")
    logger.info(f"   Log file: {_LOG_FILE}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        config = load_config(CONFIG_PATH)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    run_all_flows(config)
