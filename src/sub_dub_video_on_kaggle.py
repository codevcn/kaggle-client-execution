"""
Kaggle Client Execution - Main Runner
======================================
Flow:
  1. Đọc base_config.json để lấy danh sách các flow
  2. Với mỗi flow, dò trong local_data_input tìm file thuộc file_type_to_upload
  3. Với từng file: upload lên GDrive bằng rclone, rồi trigger notebook Kaggle
  4. Thực thi tuần tự: file-by-file, flow-by-flow
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
# Đường dẫn log file (định nghĩa trước để dùng trong logging setup)
# ─────────────────────────────────────────────
_LOG_FILE = (
    Path(__file__).resolve().parent.parent / "runtime.log"
)  # …/kaggle-client-execution/runtime.log

# ─────────────────────────────────────────────
# Cấu hình logging
# ─────────────────────────────────────────────
_log_formatter = logging.Formatter(
    fmt="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Handler 1: console (stdout)
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_log_formatter)

# Handler 2: file — ghi đè mỗi lần chạy (mode="w"), UTF-8
_file_handler = logging.FileHandler(_LOG_FILE, mode="w", encoding="utf-8")
_file_handler.setFormatter(_log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_console_handler, _file_handler],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Đường dẫn gốc
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # …/kaggle-client-execution/
CONFIG_PATH = BASE_DIR / "configs" / "base_config.json"
TMP_DIR = BASE_DIR / "tmp"
FILTERS_DIR = BASE_DIR / "src" / "filters"  # …/src/filters/


# ═══════════════════════════════════════════════════════════════════
# Phần 1 — Đọc Config
# ═══════════════════════════════════════════════════════════════════


def load_config(config_path: Path) -> dict:
    """Đọc và trả về nội dung file base_config.json."""
    if not config_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file config: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# Phần 2 — Load Kaggle credentials từ .env
# ═══════════════════════════════════════════════════════════════════


def load_kaggle_accounts(credentials_path: str) -> dict[str, str]:
    """
    Đọc file .env, tìm dòng KAGGLE_ACCOUNTS="..." và parse thành dict.
    Hỗ trợ cú pháp: KAGGLE_ACCOUNTS="{...}" hoặc KAGGLE_ACCOUNTS='{...}'
    """
    env_file = Path(credentials_path)
    if not env_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials: {credentials_path}")

    raw_text = env_file.read_text(encoding="utf-8")

    # Tìm dòng KAGGLE_ACCOUNTS=...
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("KAGGLE_ACCOUNTS="):
            value = line[len("KAGGLE_ACCOUNTS=") :]
            # Bỏ dấu nháy ngoài cùng nếu có
            value = value.strip().strip("\"'")
            try:
                accounts = json.loads(value)
                logger.info(
                    f"  ✅ Đã load {len(accounts)} tài khoản Kaggle từ credentials."
                )
                return accounts
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Không parse được KAGGLE_ACCOUNTS từ {credentials_path}:\n"
                    f"  Giá trị: {value}\n"
                    f"  Lỗi: {e}"
                )

    raise KeyError(f"Không tìm thấy key KAGGLE_ACCOUNTS trong {credentials_path}")


# ═══════════════════════════════════════════════════════════════════
# Phần 3 — Dò file trong local_data_input
# ═══════════════════════════════════════════════════════════════════


def collect_files_to_upload(local_data_input: str) -> list[Path]:
    """
    Lấy toàn bộ file (không đệ quy) trong thư mục local_data_input.
    """
    folder = Path(local_data_input)
    if not folder.exists():
        logger.warning(f"  ⚠️  Thư mục local_data_input không tồn tại: {folder}")
        return []

    files = sorted([f for f in folder.iterdir() if f.is_file()])
    logger.info(f"  📂 Tìm thấy {len(files)} file trong {folder}")
    return files


# ═══════════════════════════════════════════════════════════════════
# Phần 4 — Upload lên Google Drive bằng rclone
# ═══════════════════════════════════════════════════════════════════


def extract_gdrive_folder_id(gdrive_folder_url: str) -> str:
    """
    Trích xuất folder ID từ Google Drive URL.
    VD: https://drive.google.com/drive/folders/1-nPUSPBIgzgCzAmbdbtGvbUl8BKDv6xq?usp=...
        → 1-nPUSPBIgzgCzAmbdbtGvbUl8BKDv6xq
    """
    match = re.search(r"/folders/([^/?&]+)", gdrive_folder_url)
    if not match:
        raise ValueError(f"Không thể trích xuất folder ID từ URL: {gdrive_folder_url}")
    return match.group(1)


def get_rclone_remote_name(rclone_config_path: str) -> str:
    """
    Đọc rclone.conf và trả về tên remote đầu tiên tìm thấy.
    VD: [gdrive] → "gdrive"
    """
    config_file = Path(rclone_config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Không tìm thấy rclone config: {rclone_config_path}")

    for line in config_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            remote_name = line[1:-1]
            logger.info(f"  🔗 Tìm thấy rclone remote: [{remote_name}]")
            return remote_name

    raise ValueError(
        f"Không tìm thấy remote nào trong rclone config: {rclone_config_path}"
    )


def upload_file_to_gdrive(
    file_path: Path,
    gdrive_folder_url: str,
    rclone_config_path: str,
) -> bool:
    """
    Upload một file đơn lên Google Drive bằng rclone SYNC.

    Chiến lược dùng staging directory:
      1. Tạo thư mục staging tạm chỉ chứa đúng 1 file cần upload
      2. rclone sync <staging_dir> <remote>:<folderID>
         → xóa toàn bộ file cũ trên GDrive, chỉ giữ file mới
      3. Dọn staging dir

    Trả về True nếu thành công, False nếu thất bại.
    """
    folder_id = extract_gdrive_folder_id(gdrive_folder_url)
    remote_name = get_rclone_remote_name(rclone_config_path)
    # Dùng "remote:" (root) + --drive-root-folder-id để chỉ đúng folder ID trên GDrive.
    # KHÔNG dùng "remote:folderID" vì rclone sẽ tạo thư mục TÊN là folderID thay vì
    # sync vào folder có ID đó.
    rclone_remote_root = f"{remote_name}:"

    # ── Tạo staging directory chứa đúng 1 file ──────────────────
    staging_dir = TMP_DIR / f"_staging_{file_path.stem}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_file = staging_dir / file_path.name

    try:
        # Copy file vào staging (không di chuyển, giữ nguyên file gốc)
        shutil.copy2(file_path, staging_file)
        logger.info(f"  📦 Staging: {file_path.name}  →  {staging_dir}")

        # ── rclone sync: staging_dir → GDrive folder ────────────
        # sync sẽ XÓA file cũ trên GDrive và chỉ giữ file trong staging.
        # --drive-root-folder-id: chỉ định đúng folder bằng ID, tránh rclone
        # tạo nhầm thư mục tên là folderID ở root GDrive.
        cmd = [
            "rclone",
            "sync",
            str(staging_dir),  # nguồn: thư mục staging chứa đúng 1 file
            rclone_remote_root,  # đích: remote: (root, folder sẽ do --drive-root-folder-id xác định)
            "--drive-root-folder-id",
            folder_id,  # chỉ định đúng GDrive folder ID
            "--config",
            rclone_config_path,
            "--progress",
            "--stats-one-line",
            "--log-level",
            "INFO",
        ]

        logger.info(
            f"  📤 rclone sync: {file_path.name}  →  GDrive folder ID [{folder_id}]"
        )
        logger.info(f"       (file cũ trên GDrive sẽ bị xóa)")
        logger.info(f"       Lệnh: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.stdout.strip():
            logger.info(f"       [rclone stdout]\n{result.stdout.strip()}")
        if result.stderr.strip():
            logger.warning(f"       [rclone stderr]\n{result.stderr.strip()}")

        if result.returncode != 0:
            logger.error(
                f"  ❌ Sync thất bại (returncode={result.returncode}): {file_path.name}"
            )
            return False

        logger.info(
            f"  ✅ Sync thành công: {file_path.name} (file cũ trên GDrive đã được xóa)"
        )
        logger.info(f"  🔗 GDrive folder: {gdrive_folder_url}")
        return True

    finally:
        # ── Dọn staging dir dù thành công hay thất bại ──────────
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
            logger.info(f"  🧹 Đã xóa staging dir: {staging_dir.name}")


# ═══════════════════════════════════════════════════════════════════
# Phần 5 — Trigger Kaggle Notebook
# ═══════════════════════════════════════════════════════════════════


def _filter_stderr(raw_stderr: str) -> str:
    """Lọc bỏ SyntaxWarning gây nhiễu từ thư viện kaggle trên Python 3.12."""
    return "\n".join(
        line
        for line in raw_stderr.splitlines()
        if "SyntaxWarning" not in line and "invalid escape sequence" not in line
    ).strip()


def trigger_kaggle_notebook(notebook_ref: str, kaggle_accounts: dict[str, str]) -> bool:
    """
    Kích hoạt một Kaggle notebook bằng cách:
      1. Pull metadata (kernel-metadata.json)
      2. Pull notebook (.ipynb)
      3. Chuẩn hóa machine_shape "None" → null
      4. Push để trigger chạy lại
    Trả về True nếu thành công, False nếu thất bại.
    """
    # ── Xác thực tài khoản ──────────────────────────────────────
    username = notebook_ref.split("/")[0]
    if username not in kaggle_accounts:
        logger.error(
            f"  ❌ Không tìm thấy API Key cho tài khoản [{username}] "
            f"(notebook: {notebook_ref})."
        )
        return False

    # ── Isolated environment ────────────────────────────────────
    isolated_env = os.environ.copy()
    isolated_env["KAGGLE_USERNAME"] = username
    isolated_env["KAGGLE_KEY"] = kaggle_accounts[username]
    isolated_env["PYTHONWARNINGS"] = "ignore"  # Tắt SyntaxWarning
    isolated_env["PYTHONUTF8"] = "1"  # Ép toàn bộ I/O dùng UTF-8 (Python 3.7+)
    isolated_env["PYTHONIOENCODING"] = "utf-8"  # Fallback cho Python cũ hơn

    # ── Tạo thư mục tạm ─────────────────────────────────────────
    folder_name = notebook_ref.replace("/", "_")
    folder_path = TMP_DIR / folder_name
    os.makedirs(folder_path, exist_ok=True)
    logger.info(f"  📁 Thư mục tạm: {folder_path}")

    try:
        # ── Bước 1: Pull metadata ────────────────────────────────
        logger.info(f"  🔽 [Bước 1] Pull metadata: {notebook_ref}")
        pull_meta_cmd = [
            "kaggle",
            "kernels",
            "pull",
            notebook_ref,
            "-p",
            str(folder_path),
            "-m",  # Chỉ pull metadata
        ]
        pull_meta_result = subprocess.run(
            pull_meta_cmd,
            env=isolated_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        real_stderr_meta = _filter_stderr(pull_meta_result.stderr)
        if pull_meta_result.returncode != 0:
            logger.error(
                f"  ❌ Lỗi pull metadata {notebook_ref}:\n"
                f"       stderr: {real_stderr_meta}\n"
                f"       stdout: {pull_meta_result.stdout.strip()}"
            )
            return False

        if real_stderr_meta:
            logger.warning(f"       [stderr] {real_stderr_meta}")
        if pull_meta_result.stdout.strip():
            logger.info(f"       ✅ {pull_meta_result.stdout.strip()}")

        # ── Bước 2: Pull notebook (.ipynb) ───────────────────────
        logger.info(f"  🔽 [Bước 2] Pull notebook code: {notebook_ref}")
        pull_nb_cmd = [
            "kaggle",
            "kernels",
            "pull",
            notebook_ref,
            "-p",
            str(folder_path),
            # Không có -m → pull cả code
        ]
        pull_nb_result = subprocess.run(
            pull_nb_cmd,
            env=isolated_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        real_stderr_nb = _filter_stderr(pull_nb_result.stderr)
        if pull_nb_result.returncode != 0:
            logger.error(
                f"  ❌ Lỗi pull notebook code {notebook_ref}:\n"
                f"       stderr: {real_stderr_nb}\n"
                f"       stdout: {pull_nb_result.stdout.strip()}"
            )
            return False

        if real_stderr_nb:
            logger.warning(f"       [stderr] {real_stderr_nb}")
        if pull_nb_result.stdout.strip():
            logger.info(f"       ✅ {pull_nb_result.stdout.strip()}")

        # ── Bước 3a: Chuẩn hóa kernel-metadata.json ─────────────
        metadata_path = folder_path / "kernel-metadata.json"
        if metadata_path.exists():
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            if meta.get("machine_shape") == "None":
                meta["machine_shape"] = None
                logger.info("       🔧 Đã chuẩn hóa machine_shape: 'None' → null")

            # Đảm bảo enable_internet = true để notebook có thể truy cập internet khi chạy
            meta["enable_internet"] = True
            logger.info("       🌐 Đã đảm bảo enable_internet = true")

            metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # ── Bước 3b: Push để trigger chạy ───────────────────────
        logger.info(f"  🚀 [Bước 3] Push notebook để kích hoạt chạy: {notebook_ref}")
        push_cmd = [
            "kaggle",
            "kernels",
            "push",
            "-p",
            str(folder_path),
        ]
        push_result = subprocess.run(
            push_cmd,
            env=isolated_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        real_stderr_push = _filter_stderr(push_result.stderr)
        if push_result.returncode != 0:
            logger.error(
                f"  ❌ Lỗi push notebook {notebook_ref}:\n"
                f"       stderr: {real_stderr_push}\n"
                f"       stdout: {push_result.stdout.strip()}"
            )
            return False

        if real_stderr_push:
            logger.warning(f"       [stderr] {real_stderr_push}")
        if push_result.stdout.strip():
            logger.info(f"       ✅ {push_result.stdout.strip()}")
        logger.info(f"  🎉 Notebook kích hoạt thành công: {notebook_ref}")
        return True

    finally:
        # ── Dọn dẹp thư mục tạm dù thành công hay thất bại ───────
        if folder_path.exists():
            shutil.rmtree(folder_path, ignore_errors=True)
            logger.info(f"  🧹 Đã xóa thư mục tạm: {folder_path.name}")


# ═══════════════════════════════════════════════════════════════════
# Phần 6 — Chạy Entrance Filters
# ═══════════════════════════════════════════════════════════════════


def run_entrance_filters(entrance_filters: list[dict]) -> bool:
    """
    Chạy tuần tự từng filter trong danh sách entrance_filters.
    Mỗi filter là 1 file .py trong FILTERS_DIR (src/filters/).
    Filter tự quản lý input/output của mình (plug and play).
    Trả về True nếu tất cả filter đều thành công, False nếu có bất kỳ filter nào thất bại.
    """
    if not entrance_filters:
        return True  # Không có filter nào → tiếp tục bình thường

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
            stderr=subprocess.STDOUT,  # Gộp chung để dễ đọc realtime
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        try:
            # Đọc log realtime từ tiến trình con
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    logger.info(f"       [filter:{filter_name}] {line}")
            
            # Chờ tiến trình kết thúc tự nhiên
            process.wait()

        except KeyboardInterrupt:
            logger.warning(f"\n  ⚠️  Người dùng đã ngắt (Hủy) filter '{filter_name}' bằng phím tắt!")
            process.terminate()
            process.wait(timeout=5)
            # Trả về False để dừng luồng chính
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


# ═══════════════════════════════════════════════════════════════════
# Phần 7 — Hàm chính: thực thi toàn bộ flows
# ═══════════════════════════════════════════════════════════════════


def run_all_flows(config: dict) -> None:
    """
    Duyệt qua tất cả flow trong config.flows và thực thi tuần tự:
      - Mỗi flow → nhiều file
      - Mỗi file: upload GDrive → trigger Kaggle notebook
      - Xong file này → mới sang file kế tiếp
      - Xong flow này → mới sang flow kế tiếp
    """
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

        # ── Đọc thông tin flow ──────────────────────────────────
        entrance_filters: list[dict] = flow.get("entrance_filters", [])
        local_data_input: str = flow.get("local_data_input", "")

        gdrive_cfg: dict = flow.get("gdrive", {})
        gdrive_folder_url: str = gdrive_cfg.get("upload_gdrive_folder_url", "")
        rclone_config_path: str = gdrive_cfg.get("rclone_config_path", "")

        kaggle_cfg: dict = flow.get("kaggle", {})
        notebook_to_execute: str = kaggle_cfg.get("notebook_to_execute", "")
        credentials_path: str = kaggle_cfg.get("credentials_path", "")

        logger.info(f"\n{'═'*60}")
        logger.info(f"▶  FLOW {flow_idx}/{total_flows}: {title}")
        logger.info(
            f"   entrance_filters   : {[f.get('name') for f in entrance_filters]}"
        )
        logger.info(f"   local_data_input   : {local_data_input}")
        logger.info(f"   gdrive_folder_url  : {gdrive_folder_url}")
        logger.info(f"   rclone_config_path : {rclone_config_path}")
        logger.info(f"   notebook_to_execute: {notebook_to_execute}")
        logger.info(f"   credentials_path   : {credentials_path}")
        logger.info(f"{'═'*60}")

        # ── Kiểm tra các trường bắt buộc ───────────────────────
        missing = []
        if not local_data_input:
            missing.append("local_data_input")
        if not gdrive_folder_url:
            missing.append("gdrive.upload_gdrive_folder_url")
        if not rclone_config_path:
            missing.append("gdrive.rclone_config_path")
        if not notebook_to_execute:
            missing.append("kaggle.notebook_to_execute")
        if not credentials_path:
            missing.append("kaggle.credentials_path")

        if missing:
            logger.error(
                f"  ❌ Flow {flow_idx} thiếu các trường bắt buộc: {missing} — bỏ qua flow này."
            )
            continue

        # ── Load Kaggle accounts từ .env ────────────────────────
        try:
            kaggle_accounts = load_kaggle_accounts(credentials_path)
        except (FileNotFoundError, KeyError, ValueError) as e:
            logger.error(
                f"  ❌ Không load được Kaggle credentials: {e} — bỏ qua flow {flow_idx}."
            )
            continue

        # ── Bước 0: Chạy entrance filters ─────────────────────────
        filters_ok = run_entrance_filters(entrance_filters)
        if not filters_ok:
            logger.error(
                f"  ❌ Flow {flow_idx}: Entrance filter thất bại — bỏ qua flow này."
            )
            continue

        # ── Dò file cần upload ──────────────────────────────────
        files_to_process = collect_files_to_upload(local_data_input)
        if not files_to_process:
            logger.warning(
                f"  ⚠️  Flow {flow_idx}: Không tìm thấy file nào trong "
                f"'{local_data_input}' — bỏ qua flow này."
            )
            continue

        total_files = len(files_to_process)
        flow_success = 0
        flow_failed = 0

        # ── Xử lý tuần tự từng file ─────────────────────────────
        for file_idx, file_path in enumerate(files_to_process, start=1):
            logger.info(f"\n  ── File {file_idx}/{total_files}: {file_path.name} ──")

            # Step A: Upload lên GDrive
            upload_ok = upload_file_to_gdrive(
                file_path=file_path,
                gdrive_folder_url=gdrive_folder_url,
                rclone_config_path=rclone_config_path,
            )
            if not upload_ok:
                logger.error(
                    f"  ❌ Upload thất bại cho {file_path.name} — "
                    f"bỏ qua trigger Kaggle cho file này."
                )
                flow_failed += 1
                continue

            # Step B: Trigger Kaggle notebook
            kaggle_ok = trigger_kaggle_notebook(
                notebook_ref=notebook_to_execute,
                kaggle_accounts=kaggle_accounts,
            )
            if kaggle_ok:
                flow_success += 1
                logger.info(
                    f"  ✅ Hoàn tất file {file_idx}/{total_files}: {file_path.name}"
                )
            else:
                flow_failed += 1
                logger.error(f"  ❌ Trigger Kaggle thất bại cho file {file_path.name}")

        # ── Tổng kết flow ───────────────────────────────────────
        logger.info(f"\n  📊 Flow {flow_idx} hoàn tất:")
        logger.info(f"     ✅ Thành công : {flow_success}/{total_files}")
        logger.info(f"     ❌ Thất bại   : {flow_failed}/{total_files}")

    logger.info(f"\n{'═'*60}")
    logger.info("🏁 Đã xử lý xong toàn bộ flow.")
    logger.info(f"{'═'*60}\n")


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════


def main():
    logger.info("🚀 Khởi động Kaggle Client Execution")
    logger.info(f"   Config  : {CONFIG_PATH}")
    logger.info(f"   Tmp dir : {TMP_DIR}")
    logger.info(f"   Log file: {_LOG_FILE}")

    # Đảm bảo thư mục tmp tồn tại
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        config = load_config(CONFIG_PATH)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    run_all_flows(config)
