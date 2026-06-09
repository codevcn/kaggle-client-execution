# Hướng Dẫn & Phân Tích Tính Năng: Chế Độ Duyệt Flow Bằng ToC

Tính năng "Chế độ duyệt Flow bằng ToC" (Table of Contents - Mục Lục) là một cải tiến về mặt UX/UI trên hệ thống Local Server (trang `manage.html`), nhằm giúp người dùng có thể dễ dàng quản lý và điều hướng nhanh chóng giữa nhiều cấu hình Flow khác nhau trên cùng một trang.

> [!TIP]
> **Phím tắt nhanh:** Nhấn tổ hợp phím **`Ctrl + /`** để truy cập nhanh vào chế độ duyệt ToC.

---

## 1. Tổng Quan

Khi cấu hình hệ thống ngày càng lớn, người dùng có thể thiết lập hàng chục Flow (với nhiều Notebook và Filter đi kèm) trên cùng một giao diện. Việc cuộn chuột thủ công lên xuống để tìm kiếm một Flow cụ thể sẽ mất nhiều thời gian và làm giảm hiệu suất thao tác.

Chế độ duyệt Flow bằng ToC mang đến một menu **Mục lục động** cố định trên màn hình, tự động đồng bộ hóa với danh sách Flow hiện tại.

### Các lợi ích chính:
- **Điều hướng siêu tốc:** Nhấp vào một Flow trong ToC sẽ tự động cuộn trang đến đúng vị trí của Flow đó.
- **Theo dõi vị trí hiện tại:** ToC tự động tô sáng (highlight) tên Flow đang hiển thị trên màn hình trong lúc người dùng cuộn chuột.
- **Tính năng động:** Khi thêm mới, xóa, thay đổi tên (Title) hoặc đổi vị trí Flow, ToC sẽ cập nhật theo thời gian thực.

---

## 2. Các Thành Phần Giao Diện (UI Components)

- **Container Mục Lục (`#toc-container`)**: Nằm cố định (thường ở cạnh phải hoặc trái của màn hình), chứa danh sách các mục lục. Có thể ẩn đi nếu không có Flow nào.
- **Danh sách Item (`.toc-item`)**: Mỗi thẻ Flow trên màn hình tương ứng với một thẻ liên kết `<a>` trong ToC, mang nội dung định dạng `[Số thứ tự]. [Tên Flow]`.
- **Trạng thái Active (`.active-toc`)**: Class CSS được dùng để làm nổi bật item trong ToC tương ứng với Flow đang hiển thị trên màn hình.
- **Hiệu ứng Focus (`.flow-focused`)**: Khi bấm từ ToC để nhảy đến Flow, thẻ Flow đó sẽ nháy sáng hoặc nổi bật lên trong vài giây để người dùng nhận biết được đích đến.

---

## 3. Phân Tích Kỹ Thuật & Cấu Trúc Mã Nguồn

Tính năng ToC được triển khai chủ yếu qua file Javascript giao diện (`manage.js`), liên kết chặt chẽ với DOM (Document Object Model) của trang.

### 3.1 Hàm `renderToc()`
Hàm này chịu trách nhiệm khởi tạo và cập nhật danh sách ToC dựa trên biến toàn cục `configData.flows`.
- **Cơ chế hoạt động:** 
  1. Xóa rỗng nội dung hiện tại của ToC.
  2. Duyệt qua mảng `configData.flows`, tạo một thẻ `<a>` cho mỗi Flow, neo href tới `#flow-card-{index}`.
  3. Gắn bộ lắng nghe sự kiện `click` để khi nhấp vào:
     - Tính toán vị trí `targetTop` (trừ đi chiều cao của header để không bị che khuất).
     - Dùng `window.scrollTo` để cuộn ngay lập tức hoặc mượt mà đến vị trí đó.
     - Thêm class `.flow-focused` vào Flow được nhấp để báo hiệu.

### 3.2 Hàm `updateActiveFlowIndicator()`
Chức năng cốt lõi giúp ToC hoạt động tương tác với thao tác cuộn (scroll) của người dùng.
- **Cơ chế hoạt động:**
  1. Duyệt qua danh sách các DOM node `.flow-card`.
  2. Dùng hàm `getBoundingClientRect()` để tính tọa độ Y của thẻ so với khung nhìn (viewport).
  3. Dựa trên tính toán khoảng cách trừ đi vùng an toàn (chiều cao header + padding), xác định xem Flow nào đang hiển thị chính diện.
  4. Sau khi tìm được chỉ mục (index) của Flow hiển thị, hàm sẽ quét qua các DOM node trong ToC và áp dụng class `.active-toc` cho phần tử khớp chỉ mục, đồng thời gỡ bỏ ở các phần tử khác.

### 3.3 Tích hợp Sự Kiện DOM
```javascript
// Cập nhật Active Indicator mỗi khi trang được cuộn
document.addEventListener("scroll", updateActiveFlowIndicator, { passive: true });
```
Sử dụng cờ `{ passive: true }` giúp cải thiện hiệu suất cuộn (không khóa luồng chính). Ngoài ra, mỗi khi người dùng thay đổi tên Flow qua input text, sự kiện `oninput` sẽ kích hoạt hàm `updateTitleDisplay()` và hàm này ngay lập tức gọi tiếp `renderToc()` để cập nhật tên trong Mục lục.

---

## 4. Hướng Dẫn Sử Dụng Đối Với Người Dùng

1. **Mở quản lý Flow**: Truy cập vào giao diện Local Server Config.
2. **Xem Mục Lục**: Nhìn sang bên phải màn hình, bảng ToC sẽ liệt kê danh sách toàn bộ các Flow bạn đang có.
3. **Thao Tác Nhanh**:
   - Nhấp vào một mục bất kỳ trên ToC, hệ thống sẽ đưa bạn đến khung nhập liệu của Flow đó ngay lập tức. Thẻ Flow đó sẽ chớp sáng.
   - Khi bạn lăn chuột lên xuống để kiểm tra các cấu hình, mục lục trên ToC tương ứng với vị trí hiển thị sẽ chuyển sang màu làm nổi bật, giúp bạn luôn biết mình đang sửa cấu hình của Flow nào.
4. **Đồng Bộ Tự Động**: Đổi tên (Flow Title), dùng các nút mũi tên để dời vị trí, xóa hay thêm mới Flow đều sẽ tự động phản ánh trực tiếp ngay trên khung ToC.

---

## 5. Thao Tác Nâng Cao: Chế Độ Duyệt Bằng Phím Tắt (ToC Mode)

Nhằm tối đa hóa tốc độ làm việc mà không cần dùng chuột, hệ thống tích hợp sẵn một "Chế độ duyệt ToC" (ToC Mode) điều khiển hoàn toàn bằng bàn phím.

### Kích hoạt và Sử dụng:
1. **Bật/Tắt chế độ:** Bấm tổ hợp phím **`Ctrl + /`**. Lúc này, một thông báo góc màn hình sẽ hiện lên xác nhận "Chế độ duyệt ToC: Bật", và bảng Mục Lục sẽ được làm nổi bật.
2. **Khởi tạo vị trí:** Ngay khi vừa bật, màn hình sẽ tự động focus và nhảy đến Flow đầu tiên.
3. **Di chuyển nhanh giữa các Flow:** Khi đang ở trong ToC Mode, bạn có thể sử dụng các phím điều hướng để nhảy lập tức đến các Flow khác:
   - **`Mũi tên Xuống` (Arrow Down) / `Mũi tên Phải` (Arrow Right):** Đi đến Flow tiếp theo.
   - **`Mũi tên Lên` (Arrow Up) / `Mũi tên Trái` (Arrow Left):** Quay lại Flow trước đó.

### Tiện ích và Lưu ý:
- **Di chuyển chính xác (Absolute Scroll):** Khác với cuộn chuột thông thường, việc bấm phím mũi tên sẽ đưa chính xác khung nhập liệu của Flow tương ứng vào vị trí quan sát tốt nhất trên màn hình, đi kèm hiệu ứng chớp sáng báo hiệu.
- **Không cản trở việc nhập liệu:** Tính năng phím mũi tên chuyển Flow được tự động vô hiệu hóa nếu con trỏ (cursor) của bạn đang nằm trong một ô text (`<input>`, `<textarea>`). Nhờ vậy, bạn vẫn có thể gõ văn bản và dùng mũi tên để sửa chữ một cách bình thường.

---

## 6. Mở Rộng / Tùy Biến Thêm (Tương lai)

- **ToC có thể gập/mở (Collapse/Expand)**: Cho phép ẩn Mục lục nếu nó che khuất màn hình (hiện đang dùng `toc-handle` để đóng/mở ToC qua CSS).
- **Smooth Scroll**: Tùy chỉnh hiệu ứng chuyển động mượt thay vì `behavior: "instant"` để tăng tính thẩm mỹ.
- **Phân nhóm (Groups)**: Nếu số lượng Flow lớn có thể phân nhánh mục lục theo "Module" hoặc "Project".
