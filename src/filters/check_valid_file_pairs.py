"""
Filter: check_valid_file_pairs.py
===================================
Kiểm tra thư mục LOCAL_FOLDER_PATH_TO_CHECK có chứa các cặp file hợp lệ không.

Quy tắc hợp lệ:
  - Mỗi file audio phải có một file .txt cùng tên (cùng stem) trong cùng thư mục.
  - Mỗi file .txt phải có một file audio cùng tên (cùng stem) trong cùng thư mục.
  - Thiếu bất kỳ file nào trong cặp → filter thất bại.
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

# Thư mục cần kiểm tra cặp file
LOCAL_FOLDER_PATH_TO_CHECK: Path = ROOT_DIR / "media" / "others" / "music-videos"

# Các đuôi file được coi là "audio"
AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".wav",
        ".mp3",
        ".flac",
        ".m4a",
        ".ogg",
        ".aac",
        ".opus",
        ".wma",
    }
)

# ═══════════════════════════════════════════════════════════════════
FILTER_NAME = "check_valid_file_pairs"


def _log(message: str) -> None:
    print(f"[filter:{FILTER_NAME}]  {message}", flush=True)


def check_file_pairs(folder: Path) -> tuple[list[str], list[str]]:
    """
    Quét các thư mục con trong folder và trả về:
      - valid_pairs  : danh sách stem của các cặp hợp lệ (audio + txt đều có)
      - errors       : danh sách thông báo lỗi cho từng file thiếu cặp
    """
    if not folder.exists():
        return [], [f"Thư mục không tồn tại: {folder}"]

    if not folder.is_dir():
        return [], [f"Đường dẫn không phải thư mục: {folder}"]

    subdirs = [d for d in folder.iterdir() if d.is_dir()]
    if not subdirs:
        return [], [f"Thư mục '{folder}' không chứa thư mục con (work) nào."]

    valid_pairs: list[str] = []
    errors: list[str] = []

    for subdir in subdirs:
        all_files = [f for f in subdir.iterdir() if f.is_file()]

        audio_stems: dict[str, Path] = {}
        txt_stems: dict[str, Path] = {}

        for f in all_files:
            ext = f.suffix.lower()
            if ext in AUDIO_EXTENSIONS:
                audio_stems[f.stem] = f
            elif ext == ".txt":
                txt_stems[f.stem] = f

        all_stems = set(audio_stems) | set(txt_stems)

        if not all_stems:
            errors.append(
                f"Thư mục con '{subdir.name}' không chứa file audio hoặc .txt nào."
            )
            continue

        for stem in sorted(all_stems):
            has_audio = stem in audio_stems
            has_txt = stem in txt_stems

            if has_audio and has_txt:
                valid_pairs.append(f"{subdir.name}/{stem}")
            elif has_audio and not has_txt:
                errors.append(
                    f"[{subdir.name}] File audio '{audio_stems[stem].name}' thiếu file txt tương ứng "
                    f"(cần có: '{stem}.txt')"
                )
            else:  # has_txt and not has_audio
                errors.append(
                    f"[{subdir.name}] File txt '{txt_stems[stem].name}' thiếu file audio tương ứng "
                    f"(cần có: '{stem}.<audio_ext>')"
                )

    return valid_pairs, errors


def main() -> None:
    _log("=" * 60)
    _log(f"🚦 BẮT ĐẦU FILTER: {FILTER_NAME}")
    _log(f"   LOCAL_FOLDER_PATH_TO_CHECK : {LOCAL_FOLDER_PATH_TO_CHECK}")
    _log("=" * 60)

    valid_pairs, errors = check_file_pairs(LOCAL_FOLDER_PATH_TO_CHECK)

    if valid_pairs:
        _log(f"✅ Tìm thấy {len(valid_pairs)} cặp file hợp lệ:")
        for stem in valid_pairs:
            _log(f"   • {stem}")
    else:
        _log("⚠️  Không có cặp file hợp lệ nào.")

    if errors:
        _log(f"❌ Phát hiện {len(errors)} file không hợp lệ (thiếu cặp):")
        for err in errors:
            _log(f"   ✗ {err}")
        _log(
            "❌ FILTER THẤT BẠI — Hãy đảm bảo mỗi file audio đều có file .txt cùng tên và ngược lại."
        )
        sys.exit(1)

    _log("✅ FILTER HOÀN TẤT — Tất cả file đều có đủ cặp hợp lệ.")
    sys.exit(0)


if __name__ == "__main__":
    main()
