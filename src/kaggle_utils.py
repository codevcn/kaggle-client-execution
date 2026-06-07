"""
kaggle_utils.py
===============
Shared utilities dùng chung cho tất cả FlowModule.
Chứa toàn bộ logic: Kaggle trigger, rclone upload, notebook patching.
Không import từ bất kỳ FlowModule nào — không có circular dependency.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Marker cố định để nhận diện cell config trong notebook
_KAGGLE_CONFIG_MARKER = "# === KAGGLE_RUN_CONFIG ==="


# ──────────────────────────────────────────────────────────────
# Credentials & Config helpers
# ──────────────────────────────────────────────────────────────

def load_kaggle_accounts(credentials_path: str) -> dict[str, str]:
    """Đọc KAGGLE_ACCOUNTS từ file .env và trả về dict {username: api_key}."""
    env_file = Path(credentials_path)
    if not env_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials: {credentials_path}")

    raw_text = env_file.read_text(encoding="utf-8")
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("KAGGLE_ACCOUNTS="):
            value = line[len("KAGGLE_ACCOUNTS="):]
            value = value.strip().strip("\"'")
            try:
                accounts = json.loads(value)
                logger.info(f"  ✅ Đã load {len(accounts)} tài khoản Kaggle từ credentials.")
                return accounts
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Không parse được KAGGLE_ACCOUNTS từ {credentials_path}:\n"
                    f"  Giá trị: {value}\n"
                    f"  Lỗi: {e}"
                )

    raise KeyError(f"Không tìm thấy key KAGGLE_ACCOUNTS trong {credentials_path}")


def extract_gdrive_folder_id(gdrive_folder_url: str) -> str:
    """Trích xuất folder ID từ Google Drive URL."""
    match = re.search(r"/folders/([^/?&]+)", gdrive_folder_url)
    if not match:
        raise ValueError(f"Không thể trích xuất folder ID từ URL: {gdrive_folder_url}")
    return match.group(1)


def get_rclone_remote_name(rclone_config_path: str) -> str:
    """Đọc tên remote đầu tiên từ file rclone.conf."""
    config_file = Path(rclone_config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Không tìm thấy rclone config: {rclone_config_path}")

    for line in config_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            remote_name = line[1:-1]
            logger.info(f"  🔗 Tìm thấy rclone remote: [{remote_name}]")
            return remote_name

    raise ValueError(f"Không tìm thấy remote nào trong rclone config: {rclone_config_path}")


# ──────────────────────────────────────────────────────────────
# rclone Upload helpers
# ──────────────────────────────────────────────────────────────

def upload_file_to_gdrive(
    file_path: Path,
    gdrive_folder_url: str,
    rclone_config_path: str,
    tmp_dir: Path,
) -> bool:
    """
    Upload 1 file lên GDrive qua rclone sync.
    Tạo staging dir tạm để đảm bảo chỉ file đó được sync (tránh xóa nhầm).
    """
    folder_id = extract_gdrive_folder_id(gdrive_folder_url)
    remote_name = get_rclone_remote_name(rclone_config_path)
    rclone_remote_root = f"{remote_name}:"

    staging_dir = tmp_dir / f"_staging_{file_path.stem}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_file = staging_dir / file_path.name

    try:
        shutil.copy2(file_path, staging_file)
        logger.info(f"  📦 Staging: {file_path.name}  →  {staging_dir}")

        cmd = [
            "rclone", "sync",
            str(staging_dir),
            rclone_remote_root,
            "--drive-root-folder-id", folder_id,
            "--config", rclone_config_path,
            "--progress", "--stats-one-line", "--log-level", "INFO",
        ]

        logger.info(f"  📤 rclone sync: {file_path.name}  →  GDrive folder ID [{folder_id}]")
        logger.info(f"       (file cũ trên GDrive sẽ bị xóa)")
        logger.info(f"       Lệnh: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if result.stdout.strip():
            logger.info(f"       [rclone stdout]\n{result.stdout.strip()}")
        if result.stderr.strip():
            logger.warning(f"       [rclone stderr]\n{result.stderr.strip()}")

        if result.returncode != 0:
            logger.error(f"  ❌ Sync thất bại (returncode={result.returncode}): {file_path.name}")
            return False

        logger.info(f"  ✅ Sync thành công: {file_path.name}")
        logger.info(f"  🔗 GDrive folder: {gdrive_folder_url}")
        return True

    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
            logger.info(f"  🧹 Đã xóa staging dir: {staging_dir.name}")


def upload_dir_to_gdrive(
    dir_path: Path,
    gdrive_folder_url: str,
    rclone_config_path: str,
) -> bool:
    """
    Upload toàn bộ nội dung 1 thư mục lên GDrive qua rclone sync.
    Không cần staging dir — sync trực tiếp thư mục.
    """
    folder_id = extract_gdrive_folder_id(gdrive_folder_url)
    remote_name = get_rclone_remote_name(rclone_config_path)
    rclone_remote_root = f"{remote_name}:"

    try:
        cmd = [
            "rclone", "sync",
            str(dir_path),
            rclone_remote_root,
            "--drive-root-folder-id", folder_id,
            "--config", rclone_config_path,
            "--progress", "--stats-one-line", "--log-level", "INFO",
        ]

        logger.info(f"  📤 rclone sync: {dir_path.name} (dir)  →  GDrive folder ID [{folder_id}]")
        logger.info(f"       (file/thư mục cũ trên GDrive sẽ bị xóa để đồng bộ)")
        logger.info(f"       Lệnh: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if result.stdout.strip():
            logger.info(f"       [rclone stdout]\n{result.stdout.strip()}")
        if result.stderr.strip():
            logger.warning(f"       [rclone stderr]\n{result.stderr.strip()}")

        if result.returncode != 0:
            logger.error(f"  ❌ Sync thất bại (returncode={result.returncode}): {dir_path.name}")
            return False

        logger.info(f"  ✅ Sync thành công: {dir_path.name}")
        logger.info(f"  🔗 GDrive folder: {gdrive_folder_url}")
        return True

    except Exception as e:
        logger.error(f"  ❌ Lỗi khi upload {dir_path.name}: {e}")
        return False


# ──────────────────────────────────────────────────────────────
# Notebook patching helpers
# ──────────────────────────────────────────────────────────────

def _filter_stderr(raw_stderr: str) -> str:
    """Lọc bỏ các warning không liên quan từ stderr của subprocess."""
    return "\n".join(
        line for line in raw_stderr.splitlines()
        if "SyntaxWarning" not in line and "invalid escape sequence" not in line
    ).strip()


def _parse_value(raw):
    """
    Parse value sang kiểu Python phù hợp.
    - bool/int/float từ JSON native → giữ nguyên
    - String "true"/"false" → bool
    - String số → int/float
    - Còn lại → giữ nguyên string
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw
    if not isinstance(raw, str):
        return raw
    stripped = raw.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return raw


def _build_config_cell_source(edit_vars: dict) -> str:
    """Tạo nội dung cell config mới từ dict edit_vars."""
    lines = [
        _KAGGLE_CONFIG_MARKER,
        "# Auto-generated by kaggle-client-execution",
        "# Do not edit this cell manually before automated Kaggle push.\n",
    ]
    for key, value in edit_vars.items():
        parsed_value = _parse_value(value)
        lines.append(f"{key} = {repr(parsed_value)}")
    return "\n".join(lines)


def patch_notebook_config_cell(notebook_path: Path, edit_vars: dict) -> bool:
    """
    Tìm cell có marker KAGGLE_RUN_CONFIG trong file .ipynb và thay thế
    toàn bộ nội dung cell đó bằng các biến trong edit_vars.
    Trả về True nếu patch thành công.
    """
    try:
        import nbformat
    except ImportError:
        logger.error("  ❌ Thiếu thư viện 'nbformat'. Cài bằng: pip install nbformat")
        return False

    if not notebook_path.exists():
        logger.error(f"  ❌ Không tìm thấy file notebook: {notebook_path}")
        return False

    nb = nbformat.read(str(notebook_path), as_version=4)
    new_source = _build_config_cell_source(edit_vars)

    patched = False
    for cell in nb.cells:
        if cell.get("cell_type") == "code" and _KAGGLE_CONFIG_MARKER in cell.get("source", ""):
            cell["source"] = new_source
            patched = True
            break

    if not patched:
        logger.warning(
            f"  ⚠️  Không tìm thấy marker '{_KAGGLE_CONFIG_MARKER}' trong {notebook_path.name}. "
            "Bỏ qua bước patch edit_vars."
        )
        return False

    nbformat.write(nb, str(notebook_path))
    logger.info(f"  🔧 Đã patch edit_vars vào cell config ({notebook_path.name}):")
    for key, value in edit_vars.items():
        logger.info(f"       {key} = {repr(value)}")
    return True


# ──────────────────────────────────────────────────────────────
# Kaggle notebook trigger
# ──────────────────────────────────────────────────────────────

def trigger_kaggle_notebook(
    notebook_ref: str,
    kaggle_accounts: dict[str, str],
    tmp_dir: Path,
    edit_vars: dict | None = None,
) -> bool:
    """
    Pull notebook từ Kaggle, patch edit_vars (nếu có), rồi push lại để kích hoạt chạy.
    """
    username = notebook_ref.split("/")[0]
    if username not in kaggle_accounts:
        logger.error(f"  ❌ Không tìm thấy API Key cho tài khoản [{username}] (notebook: {notebook_ref}).")
        return False

    isolated_env = os.environ.copy()
    isolated_env["KAGGLE_USERNAME"] = username
    isolated_env["KAGGLE_KEY"] = kaggle_accounts[username]
    isolated_env["PYTHONWARNINGS"] = "ignore"
    isolated_env["PYTHONUTF8"] = "1"
    isolated_env["PYTHONIOENCODING"] = "utf-8"

    folder_name = notebook_ref.replace("/", "_")
    folder_path = tmp_dir / folder_name
    os.makedirs(folder_path, exist_ok=True)
    logger.info(f"  📁 Thư mục tạm: {folder_path}")

    try:
        # ── Bước 1: Pull metadata ────────────────────────────────
        logger.info(f"  🔽 [Bước 1] Pull metadata: {notebook_ref}")
        pull_meta_cmd = ["kaggle", "kernels", "pull", notebook_ref, "-p", str(folder_path), "-m"]
        pull_meta_result = subprocess.run(
            pull_meta_cmd, env=isolated_env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
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

        # ── Bước 2: Pull notebook code ───────────────────────────
        logger.info(f"  🔽 [Bước 2] Pull notebook code: {notebook_ref}")
        pull_nb_cmd = ["kaggle", "kernels", "pull", notebook_ref, "-p", str(folder_path)]
        pull_nb_result = subprocess.run(
            pull_nb_cmd, env=isolated_env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
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

        # ── Bước 2.5: Patch edit_vars vào notebook ───────────────
        if edit_vars:
            ipynb_files = list(folder_path.glob("*.ipynb"))
            if ipynb_files:
                notebook_file = ipynb_files[0]
                logger.info(f"  🔧 [Bước 2.5] Patch edit_vars vào notebook: {notebook_file.name}")
                patch_notebook_config_cell(notebook_file, edit_vars)
            else:
                logger.warning("  ⚠️  Không tìm thấy file .ipynb để patch edit_vars.")

        # ── Chuẩn hóa kernel-metadata.json ───────────────────────
        metadata_path = folder_path / "kernel-metadata.json"
        if metadata_path.exists():
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            if meta.get("machine_shape") == "None":
                meta["machine_shape"] = None
                logger.info("       🔧 Đã chuẩn hóa machine_shape: 'None' → null")

            meta["enable_internet"] = True
            logger.info("       🌐 Đã đảm bảo enable_internet = true")
            metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # ── Bước 3: Push để kích hoạt chạy ───────────────────────
        logger.info(f"  🚀 [Bước 3] Push notebook để kích hoạt chạy: {notebook_ref}")
        push_cmd = ["kaggle", "kernels", "push", "-p", str(folder_path)]
        push_result = subprocess.run(
            push_cmd, env=isolated_env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
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
        if folder_path.exists():
            shutil.rmtree(folder_path, ignore_errors=True)
            logger.info(f"  🧹 Đã xóa thư mục tạm: {folder_path.name}")
