"""
core/flow_manager.py — FlowExecutionManager
=============================================
Quản lý subprocess chạy flow (flow.cmd hoặc src/main.py).
Cung cấp interface async: run(), stop(), is_running(), returncode, logs.
"""

import asyncio
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from config import BASE_DIR

logger = logging.getLogger("local-server")


class FlowExecutionManager:
    """Subprocess orchestrator cho flow pipeline chính."""

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None
        self.logs: list[str] = []
        self.thread: Optional[threading.Thread] = None

    async def run(self) -> bool:
        """
        Khởi chạy flow. Trả về False nếu đang có flow chạy rồi.
        Tự động chọn flow.cmd nếu tồn tại, fallback sang python src/main.py.
        """
        if self.is_running():
            return False

        self.logs = []
        flow_cmd = BASE_DIR / "flow.cmd"

        # ── Xây dựng môi trường sạch — tránh xung đột VIRTUAL_ENV / PYTHONPATH
        # của local-server. flow.cmd sẽ tự activate .venv đúng cách.
        clean_env = os.environ.copy()
        for var in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
            clean_env.pop(var, None)
        path_parts = clean_env.get("PATH", "").split(os.pathsep)
        venv_scripts = str(BASE_DIR / ".venv" / "Scripts").lower()
        clean_env["PATH"] = os.pathsep.join(
            p for p in path_parts if p.lower() != venv_scripts
        )
        clean_env["PYTHONIOENCODING"] = "utf-8"
        clean_env["PYTHONUNBUFFERED"] = "1"

        try:
            if flow_cmd.exists():
                # Chạy flow.cmd qua cmd /c — giống người dùng chạy tay từ terminal
                cmd = ["cmd", "/c", str(flow_cmd)]
            else:
                logger.warning("⚠️ Không tìm thấy flow.cmd, fallback sang python src/main.py")
                cmd = ["python", "-u", str(BASE_DIR / "src" / "main.py")]

            logger.info(f"▶️ [FLOW] Khởi chạy process mới: {' '.join(cmd)}")
            logger.info(f"   Thư mục làm việc: {BASE_DIR}")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
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

    def _read_logs(self) -> None:
        """Đọc từng dòng stdout của subprocess và lưu vào self.logs."""
        for line in iter(self.process.stdout.readline, ""):
            stripped = line.rstrip("\r\n")
            self.logs.append(stripped)
            # In thẳng ra console của local-server để user theo dõi trực tiếp
            sys.stdout.write(stripped + "\n")
            sys.stdout.flush()
        self.process.stdout.close()
        self.process.wait()

    def is_running(self) -> bool:
        """Trả về True nếu subprocess vẫn đang chạy."""
        return self.process is not None and self.process.poll() is None

    @property
    def returncode(self) -> Optional[int]:
        """Return code của subprocess (None nếu đang chạy hoặc chưa chạy)."""
        return self.process.poll() if self.process else None

    async def stop(self) -> None:
        """
        Dừng subprocess theo thứ tự: CTRL_BREAK → terminate → kill.
        Mỗi bước chờ tối đa vài giây trước khi escalate.
        """
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
