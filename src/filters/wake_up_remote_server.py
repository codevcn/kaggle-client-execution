"""
Filter: wake_up_remote_server.py
=================================
Entrance filter — plug and play.

Nhiệm vụ:
  Gửi lệnh `mod run keep-awake <HEALTHCHECK_URL>` để đánh thức remote server.
  Đọc output realtime từ quá trình con; khi phát hiện dòng thành công,
  thoát với exit code 0. Nếu quá trình con kết thúc mà không có dòng
  thành công nào, thoát với exit code 1.

Điều kiện thành công (theo tài liệu keep_server_awake_io_documentation.md):
  Output log chứa chuỗi "THÀNH CÔNG" → server đã phản hồi ổn định.
"""

import subprocess
import sys

# ─────────────────────────────────────────────
# Fix UnicodeEncodeError khi log emoji/tiếng Việt trên Windows (cp1252 → utf-8)
# Phải reconfigure TRƯỚC khi in bất kỳ thứ gì ra stdout/stderr
# ─────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════════
# ⚙️  CẤU HÌNH — chỉnh các giá trị này cho phù hợp
# ═══════════════════════════════════════════════════════════════════

# URL healthcheck của remote server cần đánh thức
HEALTHCHECK_URL: str = "https://b6-remote-server-kaggle-2026.onrender.com/healthcheck"

# Chuỗi marker trong output xác nhận server đã phản hồi thành công
# Dựa trên tài liệu: "[REQ #N] THÀNH CÔNG: Máy chủ phản hồi ổn định (...)"
SUCCESS_MARKER: str = "THÀNH CÔNG"

# Tên filter (dùng cho log)
FILTER_NAME: str = "wake_up_remote_server"


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _log(message: str) -> None:
    """In log có prefix filter name để dễ trace khi chạy trong pipeline."""
    print(f"[filter:{FILTER_NAME}]  {message}", flush=True)


def _build_command() -> list[str]:
    """
    Xây dựng lệnh thực thi keep-awake.
    Lệnh: mod run keep-awake <HEALTHCHECK_URL>
    """
    return ["mod", "run", "keep-awake", HEALTHCHECK_URL]


# ═══════════════════════════════════════════════════════════════════
# Logic chính — chạy keep-awake và theo dõi output
# ═══════════════════════════════════════════════════════════════════


def run_keep_awake_until_success() -> bool:
    """
    Khởi động tiến trình `mod run keep-awake <HEALTHCHECK_URL>`,
    đọc stdout realtime từng dòng.

    Khi phát hiện SUCCESS_MARKER trong một dòng output:
      - Log dòng đó.
      - Terminate tiến trình con.
      - Trả về True.

    Nếu tiến trình con thoát mà không có dòng thành công:
      - Trả về False.
    """
    command = _build_command()
    _log(f"▶  Lệnh thực thi : {' '.join(command)}")
    _log(f"   Healthcheck URL: {HEALTHCHECK_URL}")
    _log(f"   Chờ server phản hồi với marker: '{SUCCESS_MARKER}'...")
    _log("-" * 60)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Gộp stderr vào stdout để đọc 1 luồng
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            # In thẳng output từ keep-awake để giữ nguyên thông tin gốc
            print(line, flush=True)

            if SUCCESS_MARKER in line:
                _log("-" * 60)
                _log(f"✅ Phát hiện dòng thành công: {line.strip()}")
                _log("   Đang dừng tiến trình keep-awake...")
                process.terminate()
                process.wait(timeout=5)
                return True

    except Exception as exc:
        _log(f"⚠️  Lỗi khi đọc output: {exc}")
        process.kill()
        process.wait()
        return False

    # Tiến trình kết thúc tự nhiên (không có dòng thành công)
    return_code = process.wait()
    _log(f"⚠️  Tiến trình kết thúc với returncode={return_code} nhưng không tìm thấy dòng thành công.")
    return False


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════


def main() -> None:
    _log("=" * 60)
    _log("🚦 BẮT ĐẦU FILTER: wake_up_remote_server")
    _log(f"   HEALTHCHECK_URL : {HEALTHCHECK_URL}")
    _log(f"   SUCCESS_MARKER  : '{SUCCESS_MARKER}'")
    _log("=" * 60)

    success = run_keep_awake_until_success()

    if success:
        _log("✅ FILTER HOÀN TẤT — Remote server đã được đánh thức thành công.")
        sys.exit(0)
    else:
        _log("❌ FILTER THẤT BẠI — Không nhận được phản hồi thành công từ remote server.")
        sys.exit(1)


if __name__ == "__main__":
    main()
