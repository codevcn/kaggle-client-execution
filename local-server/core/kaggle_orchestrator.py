"""
core/kaggle_orchestrator.py — Kaggle Pipeline Orchestration
============================================================
Chịu trách nhiệm pull, patch (tiêm biến), và push Kaggle Notebook.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path

import state
from config import BASE_DIR, CONFIG_JSON_PATH

logger = logging.getLogger("local-server")


async def run_cmd(cmd: list[str], cwd: str, env: dict = None) -> bool:
    """Chạy lệnh CLI và log output."""
    logger.info(f"🚀 Running: {' '.join(cmd)}")
    try:
        def _run():
            import subprocess
            return subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        result = await asyncio.to_thread(_run)
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            if output:
                logger.info(f"✅ Lệnh thành công:\n{output}")
            else:
                logger.info("✅ Lệnh thành công.")
            return True
        else:
            logger.error(f"❌ Lệnh thất bại (code {result.returncode}):\n{output}")
            return False
    except Exception as e:
        import traceback
        logger.error(f"❌ Lỗi thực thi lệnh: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        return False


def get_kaggle_vars_for_notebook(username: str, slug: str) -> dict:
    """Đọc cấu hình động từ configs.json cho notebook cụ thể."""
    if not CONFIG_JSON_PATH.exists():
        return {}
    try:
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        target_ref = f"{username}/{slug}"
        for flow in data.get("flows", []):
            kaggle_data = flow.get("kaggle", {})
            notebooks = kaggle_data.get("notbooks", [])
            for nb in notebooks:
                nb_exec = nb.get("notebook_to_execute")
                # Xử lý trường hợp key sai tên (ví dụ: " " thay vì "notebook_to_execute")
                if not nb_exec:
                    nb_exec = nb.get(" ", "")
                if nb_exec == target_ref:
                    return nb.get("edit_vars", {})
        return {}
    except Exception as e:
        logger.error(f"❌ Lỗi đọc config: {e}")
        return {}


def inject_webhook_to_config(webhook_url: str):
    """Tiêm trực tiếp MASTER_CONTROLLER_WEBHOOK_URL vào base_config.json cho TẤT CẢ notebook."""
    if not CONFIG_JSON_PATH.exists():
        return
    try:
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        modified = False
        full_webhook_url = f"{webhook_url.rstrip('/')}/webhook/notebook"

        for flow in data.get("flows", []):
            kaggle_data = flow.get("kaggle", {})
            notebooks = kaggle_data.get("notbooks", [])
            for nb in notebooks:
                if "edit_vars" not in nb:
                    nb["edit_vars"] = {}
                # Ghi đè hoặc thêm mới
                nb["edit_vars"]["MASTER_CONTROLLER_WEBHOOK_URL"] = full_webhook_url
                
                from config import SERVER_API_KEY
                nb["edit_vars"]["MASTER_CONTROLLER_API_KEY"] = SERVER_API_KEY
                
                modified = True
        
        if modified:
            with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("✅ Đã cập nhật MASTER_CONTROLLER_WEBHOOK_URL vào configs/base_config.json")
    except Exception as e:
        logger.error(f"❌ Lỗi khi inject webhook vào config: {e}")


def patch_notebook(ipynb_path: Path, vars_dict: dict) -> bool:
    """
    Tiêm biến vào cell chứa `# === KAGGLE_RUN_CONFIG ===`.
    """
    try:
        with open(ipynb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)

        patched = False
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            
            # source có thể là chuỗi hoặc mảng chuỗi
            source = cell.get("source", [])
            source_str = "".join(source) if isinstance(source, list) else source

            if "# === KAGGLE_RUN_CONFIG ===" in source_str:
                # Tạo nội dung mới
                new_source = ["# === KAGGLE_RUN_CONFIG ===\n"]
                
                # Các biến khác từ config
                for k, v in vars_dict.items():
                    if isinstance(v, str):
                        new_source.append(f'{k} = "{v}"\n')
                    else:
                        new_source.append(f'{k} = {v}\n')
                
                cell["source"] = new_source
                patched = True
                break

        if patched:
            with open(ipynb_path, "w", encoding="utf-8") as f:
                json.dump(nb, f, indent=1)
            logger.info(f"✅ Đã tiêm cấu hình vào {ipynb_path.name}")
            return True
        else:
            logger.warning(f"⚠️ Không tìm thấy block '# === KAGGLE_RUN_CONFIG ===' trong {ipynb_path.name}")
            return False

    except Exception as e:
        logger.error(f"❌ Lỗi patch notebook {ipynb_path}: {e}")
        return False


def patch_metadata(metadata_path: Path) -> bool:
    """Đảm bảo metadata có enable_internet = true."""
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        meta["enable_internet"] = True
        
        # Dọn dẹp máy tránh lỗi Kaggle nếu profile lưu GPU cũ
        if "machine_shape" in meta:
            del meta["machine_shape"]

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"❌ Lỗi patch metadata {metadata_path}: {e}")
        return False


async def trigger_next_notebook(notebook_ref: str) -> bool:
    """
    Thực thi Pull -> Patch -> Push notebook.
    notebook_ref format: "username/slug"
    """
    if "/" not in notebook_ref:
        logger.error(f"❌ Sai định dạng notebook_ref: {notebook_ref}. Yêu cầu: username/slug")
        return False

    username, slug = notebook_ref.split("/", 1)
    
    # ── Đọc KAGGLE_ACCOUNTS từ .env ──
    kaggle_key = ""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("KAGGLE_ACCOUNTS="):
                val = line[len("KAGGLE_ACCOUNTS="):].strip().strip("\"'")
                try:
                    accounts = json.loads(val)
                    kaggle_key = accounts.get(username, "")
                except json.JSONDecodeError:
                    pass
                break
    
    if not kaggle_key:
        logger.error(f"❌ Không tìm thấy API Key cho tài khoản '{username}' trong .env")
        return False

    isolated_env = os.environ.copy()
    isolated_env["KAGGLE_USERNAME"] = username
    isolated_env["KAGGLE_KEY"] = kaggle_key
    isolated_env["PYTHONWARNINGS"] = "ignore"
    isolated_env["PYTHONUTF8"] = "1"
    isolated_env["PYTHONIOENCODING"] = "utf-8"

    # Định vị file kaggle.exe trên hệ thống
    kaggle_cmd = shutil.which("kaggle")
    if not kaggle_cmd:
        logger.error("❌ Không tìm thấy lệnh 'kaggle' trong PATH hệ thống. Vui lòng cài đặt kaggle-cli.")
        return False

    tmp_dir = BASE_DIR / "tmp" / slug
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"🔄 Đang trigger notebook tiếp theo: {notebook_ref}")

    # 1. Pull
    pull_cmd = [kaggle_cmd, "kernels", "pull", notebook_ref, "-p", str(tmp_dir), "-m"]
    if not await run_cmd(pull_cmd, str(tmp_dir), env=isolated_env):
        return False

    # 2. Patch
    ipynb_file = tmp_dir / f"{slug}.ipynb"
    metadata_file = tmp_dir / "kernel-metadata.json"

    if ipynb_file.exists() and metadata_file.exists():
        patch_metadata(metadata_file)
        vars_dict = get_kaggle_vars_for_notebook(username, slug)
        patch_notebook(ipynb_file, vars_dict)
    else:
        logger.error(f"❌ Lỗi pull notebook: Không thấy file ipynb hoặc metadata ở {tmp_dir}")
        return False

    # 3. Push
    push_cmd = [kaggle_cmd, "kernels", "push", "-p", str(tmp_dir)]
    if not await run_cmd(push_cmd, str(tmp_dir), env=isolated_env):
        return False

    # Dọn dẹp
    shutil.rmtree(tmp_dir, ignore_errors=True)
    logger.info(f"✅ Đã trigger thành công notebook: {notebook_ref}")
    return True
