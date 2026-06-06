# 🧠 Kiến Trúc và Logic Hoạt Động Của Kaggle Master Controller

> Tài liệu mô tả chi tiết toàn bộ logic, các tính năng, giao diện UI, và cách cấu hình của server điều phối chuỗi Kaggle Notebooks.

---

## 📖 1. Tổng Quan Hệ Thống

**Kaggle Master Controller** là một máy chủ trung tâm (phát triển bằng FastAPI) có nhiệm vụ tự động hóa và điều phối các công việc xử lý theo chuỗi trên nền tảng Kaggle (được nhóm B6 phát triển cho quy trình xử lý video TikTok).

Khi một Notebook trên Kaggle hoàn thành, nó sẽ gửi webhook về máy chủ này. Dựa trên vị trí của Notebook trong chuỗi (start, mid, end), hệ thống sẽ tự động cấu hình và kích hoạt (trigger) Notebook tiếp theo chạy thông qua Kaggle CLI, đồng thời gửi thông báo tiến trình cho nhóm qua Telegram.

Hệ thống còn hỗ trợ giao diện quản trị (Admin Panel) để theo dõi log và quản lý các cấu hình động.

---

## ⚡ 2. Các Tính Năng Chính

### 2.1. Điều Phối Chuỗi Notebook (Pipeline Orchestration)

- **Nhận Webhook:** Tiếp nhận trạng thái từ các Kaggle Notebook qua endpoint `POST /webhook/notebook`.
- **Tự Động Kích Hoạt (Auto Triggering):** Sử dụng `kaggle-cli` để pull (tải về), tự động điều chỉnh siêu dữ liệu (kernel-metadata.json), tiêm (inject) các biến cấu hình động vào trực tiếp mã nguồn `.ipynb`, và push (đẩy lên) để Kaggle chạy Notebook tiếp theo.
- **Tiêm Biến Cấu Hình (Variable Patching):** Server hỗ trợ ghi đè biến trong cell code có chứa dấu `# === KAGGLE_RUN_CONFIG ===` thông qua cấu hình trong `configs.json`.

### 2.2. Thông Báo Hệ Thống (Telegram Notification)

- Tích hợp với Telegram Bot qua Async HTTP (`httpx`).
- Gửi tin nhắn tự động khi nhận được webhook mới.
- Cảnh báo hoặc báo cáo hoàn thành toàn bộ Pipeline khi chuỗi kết thúc (`notebook_index_type: end`).
- Hỗ trợ truyền theo dữ liệu từ Notebook thông qua trường `text_data`.

### 2.3. Quản Lý Qua Giao Diện Admin Panel (UI)

- **Log Theo Dõi (Logs Monitor):** Giao diện Web hiển thị log (runtime.log) trực tiếp.
- **Quản lý Job ID:** Chỉ định `active_job_id` nhằm giới hạn server chỉ tiếp nhận webhook của Job đang chạy.
- **Quản lý Biến Kaggle (Kaggle Vars):** Giao diện CRUD quản lý các giá trị động sẽ được truyền cho các notebook trước khi trigger. (Cấu trúc: `{username}/{slug}/{var}/{value}`).

### 2.4. Cơ Chế Giữ Thức (Keep Alive)

- Được trang bị endpoint `/healthcheck` cho phép các công cụ như UptimeRobot ping mỗi 5 phút để giữ server không bị tắt khi host trên Render.com (gói miễn phí).
- Tích hợp script ping cục bộ `scripts/keep_render_awake.py`.

---

## 🏗 3. Luồng Hoạt Động Chi Tiết (Detailed Workflow)

1. **Notebook A hoàn thành:** Kích hoạt gửi POST payload JSON về API `/webhook/notebook`.
   - Chứa thông tin: `job_id`, `notebook_index_type`, `status`, `next_notebook_ref`...
2. **Server Kiểm Tra:**
   - Kiểm tra API Key (Header `X-API-Key`).
   - Khớp `job_id` với `active_job_id` trong cấu hình (nếu có).
3. **Phát Xử Lý Bất Đồng Bộ (Background Task):**
   - Báo cáo webhook lên Telegram.
4. **Trigger Notebook Tiếp Theo:** (Nếu trạng thái là start/mid)
   - Lệnh Kaggle pull metadata (`kernel-metadata.json`) và source code (`.ipynb`).
   - Thiết lập `enable_internet = True` và xử lý dọn dẹp `machine_shape` tránh lỗi API.
   - Quét cấu hình `configs.json`, nếu có thiết lập biến cho notebook này, server sẽ đọc file JSON (notebook), tìm cell chứa `# === KAGGLE_RUN_CONFIG ===` và ghi đè nội dung theo giá trị mới nhất.
   - Lệnh Kaggle push để kích hoạt chạy.
5. **Dọn Dẹp:** Xoá folder code tạm trong thư mục `tmp/`.
6. **Hoàn Tất Mạch Cảm Xúc (End Job):** Notebook cuối đánh dấu `progress="done"`, Server báo cáo tổng kết toàn chuỗi cho Telegram.

---

## ⚙️ 4. Cấu Hình & Lưu Trữ (Configuration & Storage)

### 4.1. Biến Môi Trường (`.env`)

Chứa các dữ liệu bí mật ảnh hưởng đến khởi động hệ thống:

- `SERVER_API_KEY`: Key cố định dùng bảo vệ Endpoints.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: Cấu hình Bot nhắn tin.
- `KAGGLE_ACCOUNTS`: Dạng JSON chứa cặp `{"username": "api_key"}` cho phép sử dụng nhiều acc Kaggle để kích hoạt chéo.

### 4.2. Cấu Hình Động Hệ Thống (`src/configs/configs.json`)

File này được ghi / đọc trực tiếp khi cập nhật qua Admin Panel.
Cấu trúc:

```json
{
  "active_job_id": "job_01",
  "kaggle": {
    "username_1": {
      "notebook_slug_a": {
        "var_name": "value",
        "retry_count": 3,
        "use_gpu": true
      }
    }
  }
}
```

### 4.3. Quản Lý Log Thông Minh

Cơ chế Log được viết lại tùy chỉnh (`_TrimmedFileHandler`) cho phép lưu lại `runtime.log` với dung lượng được kiểm soát. Khi log vượt quá một số dòng xác định (ví dụ 400), nó sẽ tự cắt bỏ các dòng cũ, chỉ giữ lại số dòng mới nhất (ví dụ 300) để chống tràn ổ cứng máy chủ.

---

## 💻 5. Giao Diện Người Dùng (Admin UI)

- **Đường dẫn:** `GET /admin/manage`
- **Tài nguyên:**
  - Giao diện HTML được load từ `src/templates/admin.html`
  - Giao diện CSS load từ `src/static/admin.css`
- **Tính năng UI:**
  - **Live Logs:** Bấm nút tải log, hệ thống fetch `GET /admin/api/logs` hoặc tải file về.
  - **Quản lý Job ID:** Khung nhập thiết lập giới hạn Job ID.
  - **Bảng Kaggle Variables:** Giao diện thêm/xoá các biến môi trường cho Notebook theo form chuẩn xác dạng `{username}/{notebook-slug}/{variable}/{new-value}`. Giao tiếp với backend qua RESTful (`POST` / `DELETE` cho API `/admin/api/config/kaggle-vars`).

---

## 🔌 6. Danh Sách Các Endpoint API

### 6.1. Webhook (Public nhưng yêu cầu Auth Key)

- `POST /webhook/notebook`: Cổng nhận lệnh từ Kaggle Notebooks.

### 6.2. API Internal / Admin (Không Schema Docs)

- `GET /admin/manage`: Trang giao diện Admin.
- `GET /admin/api/logs`: Lấy nội dung logs hiện tại.
- `GET /admin/api/logs/download`: Tải file logs.
- `GET /admin/api/config`: Lấy Active Job ID.
- `POST /admin/api/config/job-id`: Sửa Active Job ID.
- `GET /admin/api/config/file`: Lấy nội dung toàn bộ `configs.json`.
- `GET /admin/api/config/kaggle-vars`: Lấy danh sách các biến động.
- `POST /admin/api/config/kaggle-vars`: Thêm / Cập nhật giá trị biến động mới.
- `DELETE /admin/api/config/kaggle-vars`: Xoá một biến khỏi chuỗi điều khiển.

### 6.3. Monitor

- `GET /healthcheck`: Trả về Status OK và Server Time để giữ ứng dụng tồn tại.

---

_Tài liệu tự động tổng hợp từ mã nguồn. Đảm bảo giữ bảo mật API Key trong quá trình triển khai hệ thống!_
