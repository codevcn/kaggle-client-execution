# Hướng dẫn chi tiết: Logic xử lý của các Entrance Filters

Trong kiến trúc của **Kaggle Client Execution**, các **Entrance Filters** đóng vai trò là "người gác cổng" (gatekeepers) hoặc "người chuẩn bị dữ liệu" (pre-processors) trước khi Master Controller thực sự bắt đầu chuỗi công việc (như tải dữ liệu lên GDrive hoặc kích hoạt Kaggle Notebook). 

Mỗi filter là một kịch bản Python độc lập nằm trong thư mục `src/filters/`. Hệ thống sẽ chạy lần lượt các filter được định nghĩa trong `base_config.json`. Nếu bất kỳ filter nào thất bại (`exit 1`), toàn bộ quy trình của Flow sẽ bị hủy bỏ để đảm bảo an toàn.

Dưới đây là giải thích chi tiết về cách hoạt động của 4 filter đang có sẵn trong dự án:

---

## 1. `check_if_video_file_exists.py`

**Mục đích:** Đảm bảo rằng thư mục đầu vào thực sự chứa dữ liệu video hợp lệ trước khi đẩy lên Google Drive. Tránh trường hợp chạy một luồng xử lý rỗng gây lãng phí tài nguyên và báo lỗi giả.

**Logic hoạt động:**
1. Trỏ đến thư mục đầu vào được cấu hình (mặc định: `media/others/music-videos`).
2. Quét đệ quy (recursive) toàn bộ các thư mục con bên trong để tìm các tệp tin có phần mở rộng (đuôi file) nằm trong danh sách các định dạng video phổ biến (VD: `.mp4`, `.mkv`, `.avi`, `.mov`, `.flv`, `.webm`, v.v.).
3. **Kết quả:**
   - **Thành công (Exit 0):** Tìm thấy ít nhất 1 file video hợp lệ.
   - **Thất bại (Exit 1):** Không tìm thấy file video nào, hoặc đường dẫn thư mục không tồn tại. Hệ thống sẽ in ra lỗi nhắc nhở người dùng cung cấp video.

---

## 2. `check_valid_file_pairs.py`

**Mục đích:** Dành riêng cho các tác vụ cần sự đồng bộ 1-1 giữa tệp âm thanh và kịch bản văn bản (ví dụ: gán phụ đề (sub/dub) vào nhạc). Đảm bảo không có dữ liệu nào bị "mồ côi" trước khi đẩy lên Kaggle xử lý.

**Logic hoạt động:**
1. Trỏ đến thư mục đầu vào (mặc định: `media/others/music-videos`).
2. Quét qua từng thư mục con bên trong.
3. Trong mỗi thư mục con, gom nhóm các file âm thanh (định dạng như `.wav`, `.mp3`, `.flac`, `.m4a`...) và các file `.txt`.
4. So khớp theo tên file cơ sở (stem - tên file không tính đuôi mở rộng). 
   - **Điều kiện:** File `audio_name.wav` BẮT BUỘC phải có file `audio_name.txt` đi kèm, và ngược lại.
5. **Kết quả:**
   - **Thành công (Exit 0):** Mọi file đều có cặp ghép đôi hoàn hảo.
   - **Thất bại (Exit 1):** Bắt được bất kỳ file nào lẻ loi (thiếu `.txt` hoặc thiếu file âm thanh), filter sẽ log ra chính xác tên file đang bị thiếu cặp và dừng ngay quy trình.

---

## 3. `extract_audio_from_video.py`

**Mục đích:** Tự động hóa quá trình tiền xử lý dữ liệu âm thanh. Thay vì người dùng phải tự tách âm thanh từ video gốc một cách thủ công, filter này sẽ tự động làm điều đó.

**Logic hoạt động:**
1. Đọc các file video đầu vào từ thư mục `media/videos`.
2. Tạo (hoặc làm sạch) thư mục đầu ra `media/audios` (xóa hết toàn bộ file cũ để tránh bị lẫn lộn dữ liệu rác từ các lần chạy trước).
3. Dùng công cụ mã nguồn mở **FFmpeg** (`subprocess.run(["ffmpeg", ...])`) lặp qua từng video và trích xuất luồng âm thanh (audio stream).
4. Các thông số FFmpeg được sử dụng để xuất ra file chất lượng cao:
   - `-vn`: Bỏ qua hình ảnh (Video None).
   - `-acodec pcm_s16le`: Định dạng không nén (Lossless WAV 16-bit).
   - `-ar 44100`: Tần số lấy mẫu 44.1kHz (Chuẩn CD).
   - `-ac 2`: Âm thanh Stereo 2 kênh.
5. **Kết quả:** Các file `.wav` sẽ xuất hiện ở thư mục đầu ra, sẵn sàng cho Rclone đẩy lên GDrive.

---

## 4. `run_local_server.py`

**Mục đích:** Đảm bảo rằng ứng dụng Master Controller (Local Server Fast API) đang thức và sẵn sàng nhận Webhook từ Kaggle trả về. 

**Logic hoạt động:**
1. Gửi một HTTP GET Request (Ping) tới API `http://127.0.0.1:8000/`.
2. **Nếu API phản hồi mã 200 (OK):** Chứng tỏ Local Server đang chạy tốt. Filter thành công ngay lập tức.
3. **Nếu API không phản hồi (Server đang tắt):**
   - Filter tự động kích hoạt file kịch bản `local-server/run-server.cmd`.
   - Trên hệ điều hành Windows, câu lệnh này sẽ gọi một cửa sổ Console (Terminal) hoàn toàn mới và chạy Local Server độc lập trong đó.
   - Filter sẽ rơi vào vòng lặp chờ (Polling), định kỳ kiểm tra API mỗi 2 giây.
4. **Kết quả:**
   - **Thành công (Exit 0):** Server phản hồi ổn định trong vòng 30 giây (Max Timeout).
   - **Thất bại (Exit 1):** Chờ quá 30 giây nhưng Local Server vẫn không khởi động được (có thể do lỗi code, cổng 8000 đang bị chiếm dụng, v.v.). Filter sẽ quăng lỗi để chặn quá trình đẩy lên Kaggle, tránh trường hợp Kaggle chạy xong nhưng không có Server hứng Webhook.
