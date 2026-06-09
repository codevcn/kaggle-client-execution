import subprocess
import sys
import argparse
from pathlib import Path

# Fix UnicodeEncodeError khi print tiếng Việt trên Windows (cp1252 → utf-8)
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
INPUT_FOLDER_PATH = ROOT_DIR / "media" / "videos"
OUTPUT_FOLDER_PATH = ROOT_DIR / "media" / "audios"


def extract_audio_from_videos(input_folder_path: str, output_folder_path: str) -> None:
    """
    Hàm nhận vào thư mục chứa video và thư mục đầu ra,
    sau đó sử dụng FFmpeg để trích xuất âm thanh thành tệp .wav.
    """
    input_dir = Path(input_folder_path)
    output_dir = Path(output_folder_path)

    # Kiểm tra xem thư mục đầu vào có tồn tại hay không
    if not input_dir.exists() or not input_dir.is_dir():
        print(
            f"Lỗi: Thư mục đầu vào '{input_folder_path}' không tồn tại hoặc không hợp lệ."
        )
        return

    # Tạo thư mục đầu ra nếu chưa tồn tại
    output_dir.mkdir(parents=True, exist_ok=True)

    # Làm sạch toàn bộ file cũ trong thư mục đầu ra trước khi extract
    existing_files = [f for f in output_dir.iterdir() if f.is_file()]
    if existing_files:
        print(f"Đang xóa {len(existing_files)} file cũ trong '{output_dir}'...")
        for f in existing_files:
            f.unlink()
            print(f"  Đã xóa: {f.name}")
        print("Làm sạch hoàn tất.")


    # Danh sách các định dạng video phổ biến để lọc
    video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"}

    # Tìm tất cả các tệp tin trong thư mục đầu vào
    video_files = [
        f
        for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in video_extensions
    ]

    if not video_files:
        print(f"Không tìm thấy tệp tin video nào trong thư mục '{input_folder_path}'.")
        return

    print(
        f"Tìm thấy {len(video_files)} tệp tin video. Bắt đầu quá trình trích xuất âm thanh..."
    )

    # Lặp qua từng tệp video và gọi lệnh FFmpeg
    for video_path in video_files:
        # Tạo tên tệp đầu ra với đuôi .wav
        output_filename = video_path.stem + ".wav"
        output_path = output_dir / output_filename

        # Xây dựng câu lệnh FFmpeg
        # -y: Ghi đè tệp nếu đã tồn tại mà không cần hỏi
        # -nostdin: Vô hiệu hóa tương tác qua stdin để ngăn FFmpeg bị treo
        # -i: Đường dẫn tệp đầu vào
        # -vn: Bỏ qua luồng video (chỉ lấy âm thanh)
        # -acodec pcm_s16le -ar 44100 -ac 2: Các thông số chuẩn cho tệp wav chất lượng tốt
        command = [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(output_path),
        ]

        try:
            print(f"Đang xử lý: {video_path.name} -> {output_filename}")
            # Thực thi lệnh FFmpeg, ẩn các thông báo log dài dòng của FFmpeg
            # Thiết lập stdin=subprocess.DEVNULL để chắc chắn FFmpeg không cố đọc input từ terminal
            subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            print(f"Thành công: Đã lưu {output_filename}")
        except subprocess.CalledProcessError:
            print(f"Thất bại: Đã xảy ra lỗi khi xử lý tệp {video_path.name}")
        except FileNotFoundError:
            print(
                "Lỗi: Không tìm thấy FFmpeg. Vui lòng đảm bảo rằng bạn đã cài đặt FFmpeg và thêm vào biến môi trường PATH."
            )
            break

    print("Hoàn tất toàn bộ quá trình trích xuất.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract audio from videos.")
    parser.add_argument("--input_path", type=str, default=str(INPUT_FOLDER_PATH), help="Input folder containing videos")
    parser.add_argument("--output_path", type=str, default=str(OUTPUT_FOLDER_PATH), help="Output folder for extracted audio")
    
    args = parser.parse_args()

    # Thực thi hàm chính
    extract_audio_from_videos(
        args.input_path,
        args.output_path,
    )
