"""
Filter: split_bgm_vocals_on_kaggle.py
======================================
Entrance filter — tự quản lý input/output (plug and play).

Luồng:
  1. Dùng rclone sync upload toàn bộ file trong INPUT_FOLDER_PATH
     lên GDrive folder GDRIVE_DEST_FOLDER_URL
  2. Trigger Kaggle notebook nguyenthanhtrungn21/KAGGLE_NOTEBOOK_TO_RUN
     qua Kaggle CLI (pull metadata → pull code → fix → push)
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────
# Đường dẫn gốc
# ─────────────────────────────────────────────
FILTER_DIR = Path(__file__).resolve().parent  # …/src/filters/
SRC_DIR = FILTER_DIR.parent  # …/src/
ROOT_DIR = SRC_DIR.parent  # …/kaggle-client-execution/

# ═══════════════════════════════════════════════════════════════════
# ⚙️  CẤU HÌNH — chỉnh các giá trị này cho phù hợp
# ═══════════════════════════════════════════════════════════════════

# Thư mục local chứa file cần upload lên GDrive
INPUT_FOLDER_PATH: Path = ROOT_DIR / "media" / "audios"

# GDrive folder đích (URL đầy đủ hoặc chỉ folder ID)
GDRIVE_DEST_FOLDER_URL: str = (
    "https://drive.google.com/drive/folders/1QMWUxtQHc5hS5Mad_J-1NbPM8XDCpfua"
)

# Slug của notebook Kaggle (phần sau username)
KAGGLE_NOTEBOOK_TO_RUN: str = "demucs-split-bgm-vocals-flow"

# Đường dẫn rclone config
RCLONE_CONFIG_PATH: str = "C:/Users/dell/AppData/Roaming/rclone/rclone.conf"

# Tài khoản Kaggle sở hữu notebook
KAGGLE_USERNAME: str = "nguyenthanhtrungn21"

# File .env chứa KAGGLE_ACCOUNTS
ENV_FILE_PATH: Path = ROOT_DIR / ".env"

# Fix UnicodeEncodeError khi log emoji/tiếng Việt trên Windows (cp1252 → utf-8)
# Phải reconfigure TRƯỚC khi logging.basicConfig vì StreamHandler giữ ref đến stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [filter:split_bgm_vocals_on_kaggle]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def extract_gdrive_folder_id(url: str) -> str:
    """Trích folder ID từ GDrive URL hoặc trả nguyên nếu đã là ID."""
    match = re.search(r"/folders/([^/?&]+)", url)
    if match:
        return match.group(1)
    if re.match(r"^[\w\-]+$", url):
        return url
    raise ValueError(f"Không thể trích folder ID từ: {url}")


def get_rclone_remote_name(config_path: str) -> str:
    """Đọc tên remote đầu tiên trong rclone.conf."""
    cfg = Path(config_path)
    if not cfg.exists():
        raise FileNotFoundError(f"Không tìm thấy rclone config: {config_path}")
    for line in cfg.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            return line[1:-1]
    raise ValueError(f"Không tìm thấy remote nào trong: {config_path}")


def load_kaggle_key(env_path: Path, username: str) -> str:
    """Đọc API key của username từ KAGGLE_ACCOUNTS trong .env."""
    if not env_path.exists():
        raise FileNotFoundError(f"Không tìm thấy .env: {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("KAGGLE_ACCOUNTS="):
            raw = line[len("KAGGLE_ACCOUNTS=") :].strip().strip("\"'")
            accounts: dict = json.loads(raw)
            if username not in accounts:
                raise KeyError(
                    f"Tài khoản '{username}' không có trong KAGGLE_ACCOUNTS. "
                    f"Các tài khoản hiện có: {list(accounts.keys())}"
                )
            return accounts[username]
    raise KeyError("Không tìm thấy KAGGLE_ACCOUNTS trong .env")


def _filter_stderr(raw: str) -> str:
    """Lọc SyntaxWarning từ Kaggle CLI (Python 3.12)."""
    return "\n".join(
        l
        for l in raw.splitlines()
        if "SyntaxWarning" not in l and "invalid escape sequence" not in l
    ).strip()


# ═══════════════════════════════════════════════════════════════════
# Bước 1 — Upload lên GDrive bằng rclone sync
# ═══════════════════════════════════════════════════════════════════


def upload_to_gdrive() -> None:
    """
    Sync toàn bộ INPUT_FOLDER_PATH lên GDrive folder chỉ định.
    Dùng --drive-root-folder-id để đảm bảo đúng folder.
    """
    if not INPUT_FOLDER_PATH.exists():
        raise FileNotFoundError(f"INPUT_FOLDER_PATH không tồn tại: {INPUT_FOLDER_PATH}")

    folder_id = extract_gdrive_folder_id(GDRIVE_DEST_FOLDER_URL)
    remote_name = get_rclone_remote_name(RCLONE_CONFIG_PATH)
    remote_root = f"{remote_name}:"

    files = [f for f in INPUT_FOLDER_PATH.iterdir() if f.is_file()]
    logger.info(f"📂 Tìm thấy {len(files)} file trong {INPUT_FOLDER_PATH}")
    logger.info(f"📤 rclone sync → GDrive folder ID [{folder_id}]")

    cmd = [
        "rclone",
        "sync",
        str(INPUT_FOLDER_PATH),  # nguồn: toàn bộ thư mục local
        remote_root,  # đích: root của remote
        "--drive-root-folder-id",
        folder_id,
        "--config",
        RCLONE_CONFIG_PATH,
        "--progress",
        "--stats-one-line",
        "--log-level",
        "INFO",
    ]
    logger.info(f"     Lệnh: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.stdout.strip():
        logger.info(f"     [rclone stdout]\n{result.stdout.strip()}")
    if result.stderr.strip():
        logger.warning(f"     [rclone stderr]\n{result.stderr.strip()}")

    if result.returncode != 0:
        raise RuntimeError(f"rclone sync thất bại (returncode={result.returncode})")

    logger.info(f"✅ Upload thành công → {GDRIVE_DEST_FOLDER_URL}")


# ═══════════════════════════════════════════════════════════════════
# Bước 2 — Trigger Kaggle notebook
# ═══════════════════════════════════════════════════════════════════


def trigger_kaggle_notebook() -> None:
    """
    Pull metadata + code → fix machine_shape → push để kích hoạt notebook.
    """
    notebook_ref = f"{KAGGLE_USERNAME}/{KAGGLE_NOTEBOOK_TO_RUN}"
    api_key = load_kaggle_key(ENV_FILE_PATH, KAGGLE_USERNAME)

    # Isolated env — tránh race condition nếu chạy song song
    env = os.environ.copy()
    env["KAGGLE_USERNAME"] = KAGGLE_USERNAME
    env["KAGGLE_KEY"] = api_key
    env["PYTHONWARNINGS"] = "ignore"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Thư mục tạm riêng cho filter này
    folder_name = notebook_ref.replace("/", "_")
    tmp_dir = ROOT_DIR / "tmp" / f"filter_{folder_name}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Thư mục tạm: {tmp_dir}")

    run_opts = dict(
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        # ── Bước 1: Pull metadata ────────────────────────────────
        logger.info(f"🔽 [1/3] Pull metadata: {notebook_ref}")
        r = subprocess.run(
            ["kaggle", "kernels", "pull", notebook_ref, "-p", str(tmp_dir), "-m"],
            **run_opts,
        )
        stderr = _filter_stderr(r.stderr)
        if r.returncode != 0:
            raise RuntimeError(
                f"Pull metadata thất bại:\n  stderr: {stderr}\n  stdout: {r.stdout.strip()}"
            )
        if stderr:
            logger.warning(f"     [stderr] {stderr}")
        logger.info(f"     ✅ {r.stdout.strip()}")

        # ── Bước 2: Pull notebook (.ipynb) ───────────────────────
        logger.info(f"🔽 [2/3] Pull notebook code: {notebook_ref}")
        r = subprocess.run(
            ["kaggle", "kernels", "pull", notebook_ref, "-p", str(tmp_dir)],
            **run_opts,
        )
        stderr = _filter_stderr(r.stderr)
        if r.returncode != 0:
            raise RuntimeError(
                f"Pull notebook thất bại:\n  stderr: {stderr}\n  stdout: {r.stdout.strip()}"
            )
        if stderr:
            logger.warning(f"     [stderr] {stderr}")
        logger.info(f"     ✅ {r.stdout.strip()}")

        # ── Chuẩn hóa kernel-metadata.json ──────────────────────
        meta_path = tmp_dir / "kernel-metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("machine_shape") == "None":
                meta["machine_shape"] = None
                logger.info("     🔧 Chuẩn hóa machine_shape: 'None' → null")
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # ── Bước 3: Push để trigger chạy ────────────────────────
        logger.info(f"🚀 [3/3] Push notebook: {notebook_ref}")
        r = subprocess.run(
            ["kaggle", "kernels", "push", "-p", str(tmp_dir)],
            **run_opts,
        )
        stderr = _filter_stderr(r.stderr)
        if r.returncode != 0:
            raise RuntimeError(
                f"Push notebook thất bại:\n  stderr: {stderr}\n  stdout: {r.stdout.strip()}"
            )
        if stderr:
            logger.warning(f"     [stderr] {stderr}")
        if r.stdout.strip():
            logger.info(f"     ✅ {r.stdout.strip()}")

        logger.info(f"🎉 Notebook kích hoạt thành công: {notebook_ref}")

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.info(f"🧹 Đã xóa thư mục tạm: {tmp_dir.name}")


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════


def main() -> None:
    logger.info("=" * 60)
    logger.info("🚦 BẮT ĐẦU FILTER: split_bgm_vocals_on_kaggle")
    logger.info(f"   INPUT_FOLDER_PATH      : {INPUT_FOLDER_PATH}")
    logger.info(f"   GDRIVE_DEST_FOLDER_URL : {GDRIVE_DEST_FOLDER_URL}")
    logger.info(
        f"   KAGGLE_NOTEBOOK        : {KAGGLE_USERNAME}/{KAGGLE_NOTEBOOK_TO_RUN}"
    )
    logger.info("=" * 60)

    try:
        upload_to_gdrive()
        trigger_kaggle_notebook()
        logger.info("✅ FILTER HOÀN TẤT.")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"❌ FILTER THẤT BẠI: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
