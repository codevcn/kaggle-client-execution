"""
Filter: check_if_video_file_exists.py
=======================================
Kiểm tra thư mục LOCAL_INPUT_VIDEO_DIR_PATH có chứa ít nhất một file video
với định dạng phổ biến hay không.
Nếu không có file nào → filter thất bại.
"""

import sys
from pathlib import Path

# Fix UnicodeEncodeError khi log tiếng Việt trên Windows (cp1252 → utf-8)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────
# Đường dẫn gốc
# ─────────────────────────────────────────────
FILTER_DIR = Path(__file__).resolve().parent  # …/src/filters/
SRC_DIR = FILTER_DIR.parent  # …/src/
ROOT_DIR = SRC_DIR.parent  # …/kaggle-client-execution/

# ═══════════════════════════════════════════════════════════════════
# ⚙️  CẤU HÌNH — chỉnh các giá trị này cho phù hợp
# ═══════════════════════════════════════════════════════════════════

# Thư mục chứa video cần kiểm tra
LOCAL_INPUT_VIDEO_DIR_PATH: Path = ROOT_DIR / "media" / "others" / "music-videos"

# Các định dạng video phổ biến
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".flv",
        ".wmv",
        ".webm",
        ".m4v",
        ".ts",
        ".mpeg",
        ".mpg",
        ".3gp",
        ".rm",
        ".rmvb",
        ".vob",
    }
)

# ═══════════════════════════════════════════════════════════════════
FILTER_NAME = "check_if_video_file_exists"


def _log(message: str) -> None:
    print(f"[filter:{FILTER_NAME}]  {message}", flush=True)


def find_video_files(folder: Path) -> tuple[list[Path], str | None]:
    """
    Tìm tất cả file video trong folder.

    Trả về:
      - list[Path] : danh sách file video tìm được (rỗng nếu không có)
      - str | None : thông báo lỗi nếu folder có vấn đề, None nếu bình thường
    """
    if not folder.exists():
        return [], f"Thư mục không tồn tại: {folder}"

    if not folder.is_dir():
        return [], f"Đường dẫn không phải thư mục: {folder}"

    video_files = [
        f
        for f in sorted(folder.iterdir())
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]

    return video_files, None


def main() -> None:
    _log("=" * 60)
    _log(f"🚦 BẮT ĐẦU FILTER: {FILTER_NAME}")
    _log(f"   LOCAL_INPUT_VIDEO_DIR_PATH : {LOCAL_INPUT_VIDEO_DIR_PATH}")
    _log(f"   Định dạng hợp lệ    : {', '.join(sorted(VIDEO_EXTENSIONS))}")
    _log("=" * 60)

    video_files, error = find_video_files(LOCAL_INPUT_VIDEO_DIR_PATH)

    if error:
        _log(f"❌ FILTER THẤT BẠI — {error}")
        sys.exit(1)

    if not video_files:
        _log(
            f"❌ FILTER THẤT BẠI — Không tìm thấy file video nào trong: {LOCAL_INPUT_VIDEO_DIR_PATH}"
        )
        _log(f"👉 Hãy đặt ít nhất một file video vào thư mục trên rồi chạy lại.")
        sys.exit(1)

    _log(f"✅ Tìm thấy {len(video_files)} file video:")
    for f in video_files:
        _log(f"   • {f.name}")

    _log("✅ FILTER HOÀN TẤT — Thư mục video hợp lệ.")
    sys.exit(0)


if __name__ == "__main__":
    main()
