"""
Feature Module: Burn ass subtitle & music cho video
=================================================
Được gọi từ main.py khi chạy flow tương ứng.
Thực hiện upload lên GDrive và kích hoạt Kaggle notebook.
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

def load_kaggle_accounts(credentials_path: str) -> dict[str, str]:
    env_file = Path(credentials_path)
    if not env_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file credentials: {credentials_path}")

    raw_text = env_file.read_text(encoding="utf-8")
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("KAGGLE_ACCOUNTS="):
            value = line[len("KAGGLE_ACCOUNTS=") :]
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


def collect_works_to_upload(local_data_input: str) -> list[Path]:
    folder = Path(local_data_input)
    if not folder.exists():
        logger.warning(f"  ⚠️  Thư mục local_data_input không tồn tại: {folder}")
        return []

    works = sorted([d for d in folder.iterdir() if d.is_dir()])
    logger.info(f"  📂 Tìm thấy {len(works)} work (sub-dir) trong {folder}")
    return works


def extract_gdrive_folder_id(gdrive_folder_url: str) -> str:
    match = re.search(r"/folders/([^/?&]+)", gdrive_folder_url)
    if not match:
        raise ValueError(f"Không thể trích xuất folder ID từ URL: {gdrive_folder_url}")
    return match.group(1)


def get_rclone_remote_name(rclone_config_path: str) -> str:
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


def upload_work_to_gdrive(work_dir: Path, gdrive_folder_url: str, rclone_config_path: str) -> bool:
    folder_id = extract_gdrive_folder_id(gdrive_folder_url)
    remote_name = get_rclone_remote_name(rclone_config_path)
    rclone_remote_root = f"{remote_name}:"

    try:
        cmd = [
            "rclone", "sync",
            str(work_dir),
            rclone_remote_root,
            "--drive-root-folder-id", folder_id,
            "--config", rclone_config_path,
            "--progress", "--stats-one-line", "--log-level", "INFO",
        ]

        logger.info(f"  📤 rclone sync: {work_dir.name} (dir)  →  GDrive folder ID [{folder_id}]")
        logger.info(f"       (file/thư mục cũ trên GDrive sẽ bị xóa để đồng bộ)")
        logger.info(f"       Lệnh: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if result.stdout.strip():
            logger.info(f"       [rclone stdout]\n{result.stdout.strip()}")
        if result.stderr.strip():
            logger.warning(f"       [rclone stderr]\n{result.stderr.strip()}")

        if result.returncode != 0:
            logger.error(f"  ❌ Sync thất bại (returncode={result.returncode}): {work_dir.name}")
            return False

        logger.info(f"  ✅ Sync thành công: {work_dir.name} (Gdrive đã được đồng bộ)")
        logger.info(f"  🔗 GDrive folder: {gdrive_folder_url}")
        return True

    except Exception as e:
        logger.error(f"  ❌ Lỗi khi upload {work_dir.name}: {e}")
        return False


def _filter_stderr(raw_stderr: str) -> str:
    return "\n".join(
        line for line in raw_stderr.splitlines()
        if "SyntaxWarning" not in line and "invalid escape sequence" not in line
    ).strip()


def _parse_value(raw: str):
    """
    Parse value từ string sang kiểu Python phù hợp.
    Ví dụ: "300" → 300 (int), "true" → True (bool), "1.5" → 1.5 (float), "prod" → "prod" (str)
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
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

    Trả về True nếu patch thành công, False nếu không tìm thấy marker.
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


def trigger_kaggle_notebook(
    notebook_ref: str,
    kaggle_accounts: dict[str, str],
    tmp_dir: Path,
    edit_vars: dict | None = None,
) -> bool:
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
        logger.info(f"  🔽 [Bước 1] Pull metadata: {notebook_ref}")
        pull_meta_cmd = ["kaggle", "kernels", "pull", notebook_ref, "-p", str(folder_path), "-m"]
        pull_meta_result = subprocess.run(pull_meta_cmd, env=isolated_env, capture_output=True, text=True, encoding="utf-8", errors="replace")

        real_stderr_meta = _filter_stderr(pull_meta_result.stderr)
        if pull_meta_result.returncode != 0:
            logger.error(f"  ❌ Lỗi pull metadata {notebook_ref}:\n       stderr: {real_stderr_meta}\n       stdout: {pull_meta_result.stdout.strip()}")
            return False

        if real_stderr_meta:
            logger.warning(f"       [stderr] {real_stderr_meta}")
        if pull_meta_result.stdout.strip():
            logger.info(f"       ✅ {pull_meta_result.stdout.strip()}")

        logger.info(f"  🔽 [Bước 2] Pull notebook code: {notebook_ref}")
        pull_nb_cmd = ["kaggle", "kernels", "pull", notebook_ref, "-p", str(folder_path)]
        pull_nb_result = subprocess.run(pull_nb_cmd, env=isolated_env, capture_output=True, text=True, encoding="utf-8", errors="replace")

        real_stderr_nb = _filter_stderr(pull_nb_result.stderr)
        if pull_nb_result.returncode != 0:
            logger.error(f"  ❌ Lỗi pull notebook code {notebook_ref}:\n       stderr: {real_stderr_nb}\n       stdout: {pull_nb_result.stdout.strip()}")
            return False

        if real_stderr_nb:
            logger.warning(f"       [stderr] {real_stderr_nb}")
        if pull_nb_result.stdout.strip():
            logger.info(f"       ✅ {pull_nb_result.stdout.strip()}")

        # ── Patch edit_vars vào cell config của notebook (nếu có) ─────────
        if edit_vars:
            # Tìm file .ipynb đã pull về trong folder_path
            ipynb_files = list(folder_path.glob("*.ipynb"))
            if ipynb_files:
                notebook_file = ipynb_files[0]
                logger.info(f"  🔧 [Bước 2.5] Patch edit_vars vào notebook: {notebook_file.name}")
                patch_notebook_config_cell(notebook_file, edit_vars)
            else:
                logger.warning("  ⚠️  Không tìm thấy file .ipynb để patch edit_vars.")

        metadata_path = folder_path / "kernel-metadata.json"
        if metadata_path.exists():
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            if meta.get("machine_shape") == "None":
                meta["machine_shape"] = None
                logger.info("       🔧 Đã chuẩn hóa machine_shape: 'None' → null")

            meta["enable_internet"] = True
            logger.info("       🌐 Đã đảm bảo enable_internet = true")

            metadata_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        logger.info(f"  🚀 [Bước 3] Push notebook để kích hoạt chạy: {notebook_ref}")
        push_cmd = ["kaggle", "kernels", "push", "-p", str(folder_path)]
        push_result = subprocess.run(push_cmd, env=isolated_env, capture_output=True, text=True, encoding="utf-8", errors="replace")

        real_stderr_push = _filter_stderr(push_result.stderr)
        if push_result.returncode != 0:
            logger.error(f"  ❌ Lỗi push notebook {notebook_ref}:\n       stderr: {real_stderr_push}\n       stdout: {push_result.stdout.strip()}")
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


def run_feature(flow: dict, flow_idx: int, total_flows: int, tmp_dir: Path) -> None:
    local_data_input: str = flow.get("local_data_input", "")

    gdrive_cfg: dict = flow.get("gdrive", {})
    gdrive_folder_url: str = gdrive_cfg.get("upload_gdrive_folder_url", "")
    rclone_config_path: str = gdrive_cfg.get("rclone_config_path", "")

    # ── Đọc cấu trúc kaggle mới: { "notbooks": [...] } ────────────────────
    kaggle_cfg: dict = flow.get("kaggle", {})
    notebooks: list = kaggle_cfg.get("notbooks", [])

    # Tìm notebook duy nhất có to_execute = true
    active_notebook: dict | None = None
    for nb in notebooks:
        if nb.get("to_execute") is True:
            active_notebook = nb
            break

    if active_notebook is None:
        logger.error(
            f"  ❌ Flow {flow_idx}: Không tìm thấy notebook nào có 'to_execute: true' "
            f"trong kaggle.notbooks — bỏ qua flow này."
        )
        return

    notebook_to_execute: str = active_notebook.get("notebook_to_execute", "")
    credentials_path: str = active_notebook.get("credentials_path", "")
    edit_vars: dict = active_notebook.get("edit_vars", {})

    logger.info(f"   local_data_input   : {local_data_input}")
    logger.info(f"   gdrive_folder_url  : {gdrive_folder_url}")
    logger.info(f"   rclone_config_path : {rclone_config_path}")
    logger.info(f"   notebook_to_execute: {notebook_to_execute}  [to_execute=true]")
    logger.info(f"   credentials_path   : {credentials_path}")
    logger.info(f"   Tổng notebooks trong flow: {len(notebooks)} (chỉ 1 được chạy)")
    logger.info(f"{'═'*60}")

    missing = []
    if not local_data_input:
        missing.append("local_data_input")
    if not gdrive_folder_url:
        missing.append("gdrive.upload_gdrive_folder_url")
    if not rclone_config_path:
        missing.append("gdrive.rclone_config_path")
    if not notebook_to_execute:
        missing.append("kaggle.notbooks[to_execute].notebook_to_execute")
    if not credentials_path:
        missing.append("kaggle.notbooks[to_execute].credentials_path")

    if missing:
        logger.error(f"  ❌ Flow {flow_idx}: Thiếu các trường bắt buộc: {missing} — bỏ qua flow này.")
        return

    try:
        kaggle_accounts = load_kaggle_accounts(credentials_path)
    except (FileNotFoundError, KeyError, ValueError) as e:
        logger.error(f"  ❌ Flow {flow_idx}: Không load được Kaggle credentials: {e} — bỏ qua flow này.")
        return

    works_to_process = collect_works_to_upload(local_data_input)
    if not works_to_process:
        logger.warning(f"  ⚠️  Flow {flow_idx}: Không tìm thấy work (sub-dir) nào trong '{local_data_input}' — kết thúc flow.")
        return

    total_works = len(works_to_process)
    works_success = 0
    works_failed  = 0

    for work_idx, work_dir in enumerate(works_to_process, start=1):
        logger.info(f"\n  ── Work {work_idx}/{total_works}: {work_dir.name} ──")

        upload_ok = upload_work_to_gdrive(
            work_dir=work_dir,
            gdrive_folder_url=gdrive_folder_url,
            rclone_config_path=rclone_config_path,
        )
        if not upload_ok:
            logger.error(f"  ❌ Upload thất bại cho work {work_dir.name} — bỏ qua trigger Kaggle cho work này.")
            works_failed += 1
            continue

        kaggle_ok = trigger_kaggle_notebook(
            notebook_ref=notebook_to_execute,
            kaggle_accounts=kaggle_accounts,
            tmp_dir=tmp_dir,
            edit_vars=edit_vars if edit_vars else None,
        )
        if kaggle_ok:
            works_success += 1
            logger.info(f"  ✅ Hoàn tất work {work_idx}/{total_works}: {work_dir.name}")
        else:
            works_failed += 1
            logger.error(f"  ❌ Trigger Kaggle thất bại cho work {work_dir.name}")

    logger.info(f"\n  📊 Flow {flow_idx} hoàn tất — kết quả xử lý {total_works} work:")
    logger.info(f"     ✅ Work thành công : {works_success}/{total_works}")
    logger.info(f"     ❌ Work thất bại   : {works_failed}/{total_works}")
