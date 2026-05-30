"""
Filter: check_keeping_remote_server_awake.py
=============================================
Kiểm tra xem tính năng 'mod run keep-awake' có đang chạy hay không.
Nếu không, ném lỗi và yêu cầu chạy trước khi thực thi flow.
"""

import sys
import psutil

# Fix UnicodeEncodeError khi log tiếng Việt trên Windows (cp1252 → utf-8)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

FILTER_NAME = "check_keeping_remote_server_awake"

KEEP_REMOTE_SERVER_AWAKE_COMMAND = "mod run keep-awake"


def _log(message: str) -> None:
    print(f"[filter:{FILTER_NAME}]  {message}", flush=True)


def is_keep_awake_running() -> bool:
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline")
            if cmdline:
                cmd_str = " ".join(cmdline).lower()
                if "mod" in cmd_str and "run" in cmd_str and "keep-awake" in cmd_str:
                    _log(
                        f"Phát hiện process đang chạy! PID: {proc.info['pid']}, Command: {cmd_str}"
                    )
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def main() -> None:
    _log("=" * 60)
    _log(f"🚦 BẮT ĐẦU FILTER: {FILTER_NAME}")
    _log("=" * 60)

    if is_keep_awake_running():
        _log("✅ FILTER HOÀN TẤT — Tính năng 'mod run keep-awake' ĐANG chạy.")
        sys.exit(0)
    else:
        _log(
            "❌ FILTER THẤT BẠI — Bạn chưa chạy keep-awake cho remote server, hãy chạy nó trước khi thực thi flow."
        )
        _log(f"👉 Chạy keep-awake bằng câu lệnh: {KEEP_REMOTE_SERVER_AWAKE_COMMAND}")
        sys.exit(1)


if __name__ == "__main__":
    main()
