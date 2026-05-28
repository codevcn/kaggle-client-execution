# Tài liệu Input / Output cho `keep_server_awake.py`

## 1. Mục đích của script

`keep_server_awake.py` là một CLI tool dùng để **gửi HTTP GET request định kỳ đến một healthcheck URL** nhằm giữ cho remote server luôn được đánh thức.

Script phù hợp với các server miễn phí hoặc server có cơ chế sleep khi không có traffic, ví dụ như server deploy trên Render, Kaggle remote service, hoặc các backend nhỏ cần ping định kỳ.

---

## 2. Cách chạy tổng quát

```bash
python keep_server_awake.py [healthcheck_url] [-i INTERVAL]
```

Trong đó:

| Thành phần         | Bắt buộc | Mô tả                                                                                         |
| ------------------ | -------: | --------------------------------------------------------------------------------------------- |
| `healthcheck_url`  |    Không | URL healthcheck của server cần ping. Nếu không truyền, script dùng URL mặc định.              |
| `-i`, `--interval` |    Không | Cấu hình thời gian nghỉ giữa các lần request. Có thể là thời gian cố định hoặc khoảng random. |

---

## 3. Input của script

Script nhận input thông qua **command-line arguments**.

### 3.1. Input 1: `healthcheck_url`

Đây là positional argument, dùng để chỉ định URL mà script sẽ gửi request đến.

#### Cú pháp

```bash
python keep_server_awake.py <healthcheck_url>
```

#### Ví dụ

```bash
python keep_server_awake.py https://example.com/healthcheck
```

#### Nếu không truyền `healthcheck_url`

Script sẽ dùng URL mặc định:

```text
https://b6-remote-server-kaggle-2026.onrender.com/healthcheck
```

Ví dụ:

```bash
python keep_server_awake.py
```

Tương đương với:

```bash
python keep_server_awake.py https://b6-remote-server-kaggle-2026.onrender.com/healthcheck
```

---

### 3.2. Input 2: `-i` / `--interval`

Tham số `-i` hoặc `--interval` dùng để cấu hình thời gian nghỉ giữa các lần request.

Script hỗ trợ 2 chế độ interval:

1. **Fixed interval**: thời gian cố định.
2. **Random interval**: random trong một khoảng thời gian.

---

## 4. Fixed interval input

Fixed interval nghĩa là mỗi lần request cách nhau đúng một khoảng thời gian cố định.

### 4.1. Cú pháp

```bash
python keep_server_awake.py -i <value>
```

Hoặc:

```bash
python keep_server_awake.py --interval <value>
```

### 4.2. Các đơn vị được hỗ trợ

| Đơn vị          | Ý nghĩa          |  Ví dụ | Giá trị quy đổi |
| --------------- | ---------------- | -----: | --------------: |
| `s`             | giây             |   `6s` |          6 giây |
| `m`             | phút             |   `2m` |        120 giây |
| `h`             | giờ              | `1.5h` |       5400 giây |
| Không có đơn vị | mặc định là giây |  `300` |        300 giây |

Đơn vị có thể viết hoa hoặc viết thường, ví dụ `6S`, `2M`, `1H` đều hợp lệ.

### 4.3. Ví dụ fixed interval

#### Gọi mỗi 6 giây

```bash
python keep_server_awake.py -i 6s
```

#### Gọi mỗi 2 phút

```bash
python keep_server_awake.py -i 2m
```

#### Gọi mỗi 1.5 giờ

```bash
python keep_server_awake.py -i 1.5h
```

#### Gọi mỗi 300 giây

```bash
python keep_server_awake.py -i 300
```

### 4.4. Output khi dùng fixed interval

Khi chạy ở fixed interval, phần log khởi động sẽ có dạng:

```text
======================================================================
🚀 KHỞI ĐỘNG TRÌNH GIỮ NHỊP (KEEP-ALIVE) CHO MÁY CHỦ TỪ XA
Mục tiêu giám sát : https://example.com/healthcheck
Chế độ interval : CỐ ĐỊNH
Thời gian nghỉ   : 2 phút
Quy tắc an toàn   : Giảm thời gian chờ xuống 2 phút nếu máy chủ phản hồi chậm.
Nhấn tổ hợp phím [Ctrl + C] để dừng chương trình.
======================================================================
```

Sau mỗi lần request thành công, script sẽ log:

```text
[12:00:00] Chế độ CỐ ĐỊNH: Lần gọi tiếp theo sau 2 phút.
```

---

## 5. Random interval input

Random interval nghĩa là sau mỗi request, script sẽ chọn ngẫu nhiên một thời gian nghỉ trong khoảng được chỉ định.

### 5.1. Random interval mặc định

Nếu không truyền `-i`, script mặc định random trong khoảng:

```text
3 phút đến 6 phút
```

Tương đương:

```text
180 giây đến 360 giây
```

Ví dụ:

```bash
python keep_server_awake.py
```

Output khởi động sẽ hiển thị:

```text
Chế độ interval : NGẪU NHIÊN
Thời gian nghỉ   : Nằm trong khoảng 3 phút đến 6 phút
```

### 5.2. Random interval tùy chỉnh

Để truyền khoảng random tùy chỉnh, dùng định dạng:

```text
mm:ss-mm:ss
```

Trong đó:

| Thành phần | Ý nghĩa                                           |
| ---------- | ------------------------------------------------- |
| `mm`       | số phút                                           |
| `ss`       | số giây                                           |
| `-`        | phân cách thời gian bắt đầu và thời gian kết thúc |

### 5.3. Ví dụ random interval

#### Random từ 3 phút đến 6 phút

```bash
python keep_server_awake.py -i 03:00-06:00
```

#### Random từ 1 phút 30 giây đến 2 phút 45 giây

```bash
python keep_server_awake.py -i 01:30-02:45
```

### 5.4. Output khi dùng random interval

Khi chạy ở random interval, phần log khởi động sẽ có dạng:

```text
======================================================================
🚀 KHỞI ĐỘNG TRÌNH GIỮ NHỊP (KEEP-ALIVE) CHO MÁY CHỦ TỪ XA
Mục tiêu giám sát : https://example.com/healthcheck
Chế độ interval : NGẪU NHIÊN
Thời gian nghỉ   : Nằm trong khoảng 3 phút đến 6 phút
Quy tắc an toàn   : Giảm thời gian chờ xuống 2 phút nếu máy chủ phản hồi chậm.
Nhấn tổ hợp phím [Ctrl + C] để dừng chương trình.
======================================================================
```

Sau mỗi lần request thành công, script sẽ log thời gian được random cho lần tiếp theo:

```text
[12:00:00] Chế độ NGẪU NHIÊN: Đã chọn lần gọi tiếp theo sau 4 phút 12 giây.
```

---

## 6. Output chính của script

Script không tạo file output. Output chính là:

1. **Log in ra terminal / console**.
2. **HTTP GET request gửi đến healthcheck URL**.
3. **Trạng thái xử lý sau mỗi request**.

---

## 7. Các loại output log

### 7.1. Log khởi động

Khi bắt đầu chạy, script luôn in ra banner cấu hình:

```text
======================================================================
🚀 KHỞI ĐỘNG TRÌNH GIỮ NHỊP (KEEP-ALIVE) CHO MÁY CHỦ TỪ XA
Mục tiêu giám sát : <HEALTHCHECK_URL>
Chế độ interval : <CỐ ĐỊNH hoặc NGẪU NHIÊN>
Thời gian nghỉ   : <mô tả interval>
Quy tắc an toàn   : Giảm thời gian chờ xuống 2 phút nếu máy chủ phản hồi chậm.
Nhấn tổ hợp phím [Ctrl + C] để dừng chương trình.
======================================================================
```

Ý nghĩa:

| Dòng log            | Ý nghĩa                                                          |
| ------------------- | ---------------------------------------------------------------- |
| `Mục tiêu giám sát` | URL sẽ được gửi request định kỳ.                                 |
| `Chế độ interval`   | Cho biết script đang chạy fixed hay random interval.             |
| `Thời gian nghỉ`    | Khoảng thời gian nghỉ giữa các lần request.                      |
| `Quy tắc an toàn`   | Nếu request bị timeout, lần retry tiếp theo sẽ rút xuống 2 phút. |
| `Ctrl + C`          | Cách dừng vòng lặp.                                              |

---

### 7.2. Log trước khi gửi request

Trước mỗi request, script in ra:

```text
[12:00:00] [REQ #1] Đang gửi yêu cầu đánh thức đến máy chủ...
```

Ý nghĩa:

| Thành phần   | Ý nghĩa                                   |
| ------------ | ----------------------------------------- |
| `[12:00:00]` | Thời gian hiện tại theo local machine.    |
| `[REQ #1]`   | Số thứ tự request.                        |
| Nội dung log | Cho biết script đang chuẩn bị gọi server. |

---

### 7.3. Output khi request thành công và response là JSON

Nếu server trả về HTTP status thành công và body là JSON hợp lệ, script sẽ parse JSON.

Nếu JSON có key `timestamp`, script sẽ in timestamp đó ra.

Ví dụ response từ server:

```json
{
  "status": "ok",
  "timestamp": "2026-05-28T12:00:00Z"
}
```

Output:

```text
[12:00:00] [REQ #1] THÀNH CÔNG: Máy chủ phản hồi ổn định (JSON) - 2026-05-28T12:00:00Z
```

Nếu JSON không có key `timestamp`, script sẽ in:

```text
[12:00:00] [REQ #1] THÀNH CÔNG: Máy chủ phản hồi ổn định (JSON) - Không có dữ liệu thời gian
```

---

### 7.4. Output khi request thành công nhưng response không phải JSON

Nếu server trả về HTTP status thành công nhưng body là text hoặc HTML, script vẫn xem là thành công.

Ví dụ output:

```text
[12:00:00] [REQ #1] THÀNH CÔNG: Máy chủ phản hồi ổn định (Text/HTML) - Mã trạng thái: 200
```

Trường hợp này thường xảy ra khi endpoint trả về:

```text
OK
```

Hoặc HTML:

```html
<html>
  ...
</html>
```

---

### 7.5. Output khi server timeout

Mỗi request có timeout là `15` giây.

Nếu server phản hồi quá chậm và vượt quá timeout này, script sẽ log:

```text
[12:00:00] [REQ #1] CẢNH BÁO: Máy chủ phản hồi quá chậm.
```

Sau đó, script chuyển sang chế độ phục hồi:

```text
[12:00:15] Chế độ PHỤC HỒI: Rút ngắn lần gọi tiếp theo xuống còn 2 phút.
```

Ý nghĩa:

| Tình huống              | Hành vi                          |
| ----------------------- | -------------------------------- |
| Server bị timeout       | `ping_server()` trả về `True`.   |
| Request tiếp theo       | Không dùng interval bình thường. |
| Thời gian chờ tiếp theo | Cố định 2 phút.                  |

---

### 7.6. Output khi lỗi kết nối hoặc lỗi HTTP

Nếu có lỗi thuộc nhóm `requests.exceptions.RequestException`, script sẽ log lỗi hệ thống.

Ví dụ:

```text
[12:00:00] [REQ #1] LỖI HỆ THỐNG: Không thể kết nối đến máy chủ. Chi tiết: HTTPSConnectionPool(...)
```

Các lỗi có thể rơi vào nhóm này:

| Loại lỗi                 | Ví dụ                                                      |
| ------------------------ | ---------------------------------------------------------- |
| URL sai định dạng        | `Invalid URL`                                              |
| Không có mạng            | `ConnectionError`                                          |
| DNS lỗi                  | `NameResolutionError`                                      |
| Server trả về HTTP error | `404`, `500`, `503`, sau khi `raise_for_status()` được gọi |

Lưu ý: với lỗi hệ thống, script **không chuyển sang chế độ phục hồi 2 phút**. Nó tiếp tục dùng interval đã cấu hình ban đầu.

---

### 7.7. Output khi người dùng dừng bằng Ctrl + C

Khi người dùng nhấn:

```text
Ctrl + C
```

Script sẽ bắt `KeyboardInterrupt` và in:

```text
[HỆ THỐNG] Đã nhận lệnh dừng từ người dùng. Đang tắt chương trình...
```

Sau đó chương trình kết thúc.

---

## 8. Validation input

Script dùng `argparse.ArgumentTypeError` để báo lỗi khi input của `-i` không hợp lệ.

### 8.1. Lỗi khi fixed interval nhỏ hơn hoặc bằng 0

Input lỗi:

```bash
python keep_server_awake.py -i 0
```

Hoặc:

```bash
python keep_server_awake.py -i -5s
```

Output lỗi:

```text
error: argument -i/--interval: Thời gian phải lớn hơn 0.
```

---

### 8.2. Lỗi khi random range có thời gian bắt đầu lớn hơn hoặc bằng thời gian kết thúc

Input lỗi:

```bash
python keep_server_awake.py -i 06:00-03:00
```

Output lỗi:

```text
error: argument -i/--interval: Khoảng thời gian không hợp lệ. Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc.
```

Input lỗi khác:

```bash
python keep_server_awake.py -i 03:00-03:00
```

Vì thời gian bắt đầu bằng thời gian kết thúc nên cũng không hợp lệ.

---

### 8.3. Lỗi khi format interval sai

Input lỗi:

```bash
python keep_server_awake.py -i abc
```

Hoặc:

```bash
python keep_server_awake.py -i 3minutes
```

Hoặc:

```bash
python keep_server_awake.py -i 1d
```

Output lỗi:

```text
error: argument -i/--interval: Tham số -i không hợp lệ. Vui lòng nhập số cố định (Ví dụ: 6s, 2m, 300) hoặc khoảng thời gian theo định dạng mm:ss-mm:ss (Ví dụ: 03:00-06:00).
```

---

## 9. Luồng xử lý tổng quát

```text
Bắt đầu
  ↓
Parse command-line arguments
  ↓
Xác định HEALTHCHECK_URL
  ↓
Xác định interval_config
  ↓
In banner khởi động
  ↓
request_index = 1
  ↓
Lặp vô hạn:
  ↓
Gửi HTTP GET request đến HEALTHCHECK_URL
  ↓
Nếu thành công:
    - In log thành công JSON hoặc Text/HTML
    - Chọn thời gian nghỉ tiếp theo theo fixed/random interval
  ↓
Nếu timeout:
    - In cảnh báo timeout
    - Chờ 2 phút trước request tiếp theo
  ↓
Nếu lỗi hệ thống:
    - In chi tiết lỗi
    - Chọn thời gian nghỉ tiếp theo theo fixed/random interval
  ↓
Tăng request_index
  ↓
sleep(next_interval_seconds)
  ↓
Lặp lại
```

---

## 10. Giá trị mặc định trong script

| Tên biến                         |                                                         Giá trị | Ý nghĩa                                       |
| -------------------------------- | --------------------------------------------------------------: | --------------------------------------------- |
| `DEFAULT_HEALTHCHECK_URL`        | `https://b6-remote-server-kaggle-2026.onrender.com/healthcheck` | URL mặc định nếu không truyền positional URL. |
| `RANDOM_MIN_INTERVAL_SECONDS`    |                                                           `180` | Random interval thấp nhất mặc định: 3 phút.   |
| `RANDOM_MAX_INTERVAL_SECONDS`    |                                                           `360` | Random interval cao nhất mặc định: 6 phút.    |
| `TIMEOUT_RETRY_INTERVAL_SECONDS` |                                                           `120` | Thời gian chờ sau khi server timeout: 2 phút. |
| `requests.get(..., timeout=15)`  |                                                            `15` | Timeout cho mỗi HTTP GET request.             |

---

## 11. Ví dụ chạy thực tế

### 11.1. Chạy với URL mặc định và random interval mặc định

Command:

```bash
python keep_server_awake.py
```

Ý nghĩa:

- Ping URL mặc định.
- Random thời gian nghỉ từ 3 phút đến 6 phút.
- Nếu timeout thì lần tiếp theo chờ 2 phút.

---

### 11.2. Chạy với URL tùy chỉnh và interval cố định 5 phút

Command:

```bash
python keep_server_awake.py https://example.com/healthcheck -i 5m
```

Ý nghĩa:

- Ping `https://example.com/healthcheck`.
- Sau mỗi lần request bình thường, chờ đúng 5 phút.
- Nếu request bị timeout, lần kế tiếp chờ 2 phút.

---

### 11.3. Chạy với URL tùy chỉnh và random interval 1 phút đến 3 phút

Command:

```bash
python keep_server_awake.py https://example.com/healthcheck -i 01:00-03:00
```

Ý nghĩa:

- Ping `https://example.com/healthcheck`.
- Sau mỗi lần request bình thường, random thời gian nghỉ từ 1 phút đến 3 phút.
- Nếu request bị timeout, lần kế tiếp chờ 2 phút.

---

## 12. Bảng tóm tắt input/output

| Trường hợp chạy        | Input                               | Output chính                                            |
| ---------------------- | ----------------------------------- | ------------------------------------------------------- |
| Không truyền gì        | `python keep_server_awake.py`       | Ping URL mặc định, random 3–6 phút, log ra terminal.    |
| Truyền URL             | `python keep_server_awake.py <url>` | Ping URL được truyền, random 3–6 phút, log ra terminal. |
| Truyền fixed interval  | `-i 2m`                             | Ping theo chu kỳ cố định 2 phút.                        |
| Truyền random interval | `-i 03:00-06:00`                    | Ping theo chu kỳ random từ 3 đến 6 phút.                |
| Server trả JSON        | HTTP response JSON                  | Log `THÀNH CÔNG ... (JSON)` và timestamp nếu có.        |
| Server trả text/HTML   | HTTP response non-JSON              | Log `THÀNH CÔNG ... (Text/HTML)` và status code.        |
| Server timeout         | Quá 15 giây chưa phản hồi           | Log `CẢNH BÁO`, lần kế tiếp chờ 2 phút.                 |
| Lỗi request            | DNS, network, HTTP error, URL lỗi   | Log `LỖI HỆ THỐNG` kèm chi tiết exception.              |
| Người dùng nhấn Ctrl+C | KeyboardInterrupt                   | Log dừng chương trình và thoát.                         |

---

## 13. Ghi chú kỹ thuật quan trọng

- Script chạy vòng lặp vô hạn cho đến khi người dùng dừng bằng `Ctrl + C`.
- Script chỉ dùng HTTP `GET`, không gửi `POST`, không gửi payload body.
- Script không lưu lịch sử request vào file.
- Script không retry ngay lập tức khi lỗi kết nối thông thường.
- Chỉ riêng lỗi timeout mới kích hoạt chế độ phục hồi với interval 2 phút.
- Nếu response là JSON nhưng không có field `timestamp`, script vẫn coi là thành công.
- Nếu response không phải JSON nhưng HTTP status vẫn thành công, script vẫn coi là thành công.
- Nếu server trả về HTTP status lỗi như `404`, `500`, `503`, `response.raise_for_status()` sẽ ném exception và script log là lỗi hệ thống.

---

## 14. Checklist kiểm thử nhanh

Có thể test script bằng các command sau:

```bash
# Test default URL + random interval mặc định
python keep_server_awake.py

# Test URL riêng + fixed interval 10 giây
python keep_server_awake.py https://example.com/healthcheck -i 10s

# Test URL riêng + fixed interval 2 phút
python keep_server_awake.py https://example.com/healthcheck -i 2m

# Test random interval từ 30 giây đến 1 phút
python keep_server_awake.py https://example.com/healthcheck -i 00:30-01:00

# Test lỗi format interval
python keep_server_awake.py -i abc

# Test lỗi khoảng random ngược
python keep_server_awake.py -i 06:00-03:00
```
