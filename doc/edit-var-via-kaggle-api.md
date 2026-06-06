# Hướng dẫn chuẩn: Edit Vars trong Kaggle Notebook bằng Kaggle API

## 1. Mục tiêu

Tài liệu này mô tả cách **sửa giá trị biến trong file Kaggle Notebook `.ipynb` ở local trước khi push lên Kaggle**.

Cách làm này phù hợp khi bạn có một notebook chạy trên Kaggle, nhưng trước mỗi lần chạy cần đổi một số biến cấu hình như:

```python
RUN_MODE = "prod"
HEALTHCHECK_URL = "https://example.com/healthcheck"
INTERVAL_SECONDS = 300
ENABLE_DEBUG = False
CURRENT_JOB_ID = "job_001"
```

Thay vì mở Kaggle Notebook trên trình duyệt rồi sửa tay, ta sẽ:

```text
Sửa biến trong notebook local bằng script
→ push notebook đã sửa lên Kaggle bằng Kaggle API
→ Kaggle chạy version notebook mới
```

Điểm quan trọng cần hiểu:

> Kaggle API không hoạt động giống kiểu truyền tham số runtime trực tiếp như `python script.py --arg value`.
>
> Với Kaggle Notebook, cách ổn định hơn là tạo sẵn một **cell config** trong notebook, rồi dùng script local ghi đè cell đó trước khi push.

---

## 2. Luồng hoạt động tổng quan

Workflow chuẩn:

```text
1. Chuẩn bị notebook `.ipynb` ở local
2. Tạo một cell config riêng trong notebook
3. Đánh dấu cell config bằng marker cố định
4. Dùng script Python sửa value trong cell config
5. Kiểm tra notebook local đã được patch đúng chưa
6. Dùng Kaggle API push notebook lên Kaggle
7. Kaggle tự chạy version notebook mới
8. Theo dõi status và tải output nếu cần
```

Trong hệ thống backend tự động, luồng thường là:

```text
1. Frontend gửi danh sách biến cần sửa xuống backend
2. Backend lưu các biến này trong `edit_vars`
3. Backend pull notebook từ Kaggle về thư mục tạm
4. Backend dùng `nbformat` đọc file `.ipynb`
5. Backend tìm cell chứa marker `# === KAGGLE_RUN_CONFIG ===`
6. Backend ghi đè toàn bộ cell config bằng biến mới
7. Backend push notebook đã patch lên Kaggle
8. Kaggle chạy notebook mới
```

---

## 3. Cấu trúc thư mục khuyến nghị

Ví dụ cấu trúc thư mục local:

```text
kaggle-runner/
│
├─ main.ipynb
├─ kernel-metadata.json
├─ patch_kaggle_notebook_config.py
└─ push_to_kaggle.ps1
```

Vai trò từng file:

| File                              | Vai trò                                            |
| --------------------------------- | -------------------------------------------------- |
| `main.ipynb`                      | Notebook sẽ chạy trên Kaggle                       |
| `kernel-metadata.json`            | Metadata để Kaggle biết notebook nào cần push      |
| `patch_kaggle_notebook_config.py` | Script sửa biến trong notebook trước khi push      |
| `push_to_kaggle.ps1`              | Script PowerShell chạy trọn quy trình patch + push |

Nếu muốn giữ file gốc sạch, có thể tạo thêm file build:

```text
kaggle-runner/
│
├─ main.ipynb
├─ main.kaggle.ipynb
├─ kernel-metadata.json
├─ patch_kaggle_notebook_config.py
└─ push_to_kaggle.ps1
```

Khi đó `main.ipynb` là bản gốc, còn `main.kaggle.ipynb` là bản đã patch để upload lên Kaggle.

---

## 4. Cài Kaggle API trên máy cá nhân

Cài Kaggle CLI:

```powershell
pip install kaggle
```

Kiểm tra lệnh `kaggle` đã dùng được chưa:

```powershell
kaggle --help
```

Nếu Windows báo không nhận lệnh `kaggle`, có thể dùng:

```powershell
python -m kaggle --help
```

Hoặc thêm thư mục `Scripts` của Python vào `PATH`, ví dụ:

```text
C:\Users\<USERNAME>\AppData\Roaming\Python\Python3xx\Scripts
```

---

## 5. Cấu hình xác thực Kaggle API

Có 2 cách phổ biến.

### Cách A: Đăng nhập bằng CLI

```powershell
kaggle auth login
```

Lệnh này sẽ mở quy trình đăng nhập bằng trình duyệt.

### Cách B: Dùng file `kaggle.json`

Vào Kaggle Account Settings, tạo API key rồi tải file `kaggle.json`.

Trên Windows, đặt file tại:

```text
C:\Users\<USERNAME>\.kaggle\kaggle.json
```

Trên Linux/macOS, đặt file tại:

```bash
~/.kaggle/kaggle.json
```

Sau đó test:

```powershell
kaggle kernels list --mine
```

Nếu trả về danh sách notebook/kernel của bạn thì xác thực đã hoạt động.

---

## 6. Chuẩn bị `kernel-metadata.json`

Trong thư mục chứa notebook, chạy:

```powershell
kaggle kernels init -p .
```

Lệnh này tạo file `kernel-metadata.json` mẫu.

Ví dụ nội dung:

```json
{
  "id": "your-kaggle-username/my-kaggle-notebook",
  "title": "My Kaggle Notebook",
  "code_file": "main.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": "true",
  "enable_gpu": "false",
  "enable_internet": "false",
  "dataset_sources": [],
  "competition_sources": [],
  "kernel_sources": [],
  "model_sources": []
}
```

Các field quan trọng:

| Field             | Ý nghĩa                                                  |
| ----------------- | -------------------------------------------------------- |
| `id`              | Slug notebook trên Kaggle, dạng `username/notebook-slug` |
| `title`           | Tên notebook hiển thị trên Kaggle                        |
| `code_file`       | Tên file notebook local sẽ được push                     |
| `language`        | Với Python notebook thì để `python`                      |
| `kernel_type`     | Với `.ipynb` thì để `notebook`                           |
| `is_private`      | `true` nếu muốn notebook private                         |
| `enable_gpu`      | `true` nếu cần GPU                                       |
| `enable_internet` | `true` nếu notebook cần internet                         |

Lưu ý:

- `code_file` phải trỏ đúng tới file `.ipynb` cần push.
- File `.ipynb` nên nằm cùng thư mục với `kernel-metadata.json`.
- Nếu dùng bản build `main.kaggle.ipynb`, cần đổi:

```json
"code_file": "main.kaggle.ipynb"
```

---

## 7. Tạo cell config trong notebook

Trong `main.ipynb`, tạo một code cell riêng ở gần đầu notebook:

```python
# === KAGGLE_RUN_CONFIG ===
RUN_MODE = "dev"
HEALTHCHECK_URL = "https://default-url.com/healthcheck"
INTERVAL_SECONDS = 300
ENABLE_DEBUG = True
CURRENT_JOB_ID = "local_test"
```

Marker bắt buộc là:

```python
# === KAGGLE_RUN_CONFIG ===
```

Script sẽ tìm cell chứa marker này và ghi đè toàn bộ nội dung cell bằng config mới.

Khuyến nghị:

- Chỉ có **duy nhất 1 cell code** chứa marker này.
- Đặt cell config gần đầu notebook.
- Không đặt logic xử lý phức tạp trong cell config.
- Không đặt code quan trọng trong cell config, vì cell này sẽ bị ghi đè hoàn toàn.
- Các cell phía sau chỉ đọc lại biến đã khai báo.

Ví dụ cell phía sau:

```python
print("RUN_MODE:", RUN_MODE)
print("HEALTHCHECK_URL:", HEALTHCHECK_URL)
print("INTERVAL_SECONDS:", INTERVAL_SECONDS)
print("ENABLE_DEBUG:", ENABLE_DEBUG)
print("CURRENT_JOB_ID:", CURRENT_JOB_ID)
```

---

## 8. Cài thư viện cần thiết để patch notebook

Script patch cần thư viện `nbformat` để đọc và ghi file `.ipynb`.

Cài bằng:

```powershell
pip install nbformat
```

Nếu đang chạy trong môi trường ảo `.venv`, cần cài đúng vào môi trường đó:

```powershell
.\.venv\Scripts\python.exe -m pip install nbformat
```

Nên thêm vào `requirements.txt`:

```text
nbformat
```

Nếu thiếu `nbformat`, script có thể không sửa được notebook. Trong một số hệ thống, lỗi này chỉ hiện log rồi bỏ qua bước patch, dẫn đến notebook trên Kaggle vẫn giữ nguyên biến cũ.

---

## 9. Script Python sửa biến trong notebook

Tạo file `patch_kaggle_notebook_config.py`:

```python
import argparse
import json
from pathlib import Path

import nbformat

MARKER = "# === KAGGLE_RUN_CONFIG ==="


def parse_value(raw: str):
    """
    Parse value từ command line hoặc frontend.

    Ví dụ:
    - 300       -> int
    - 1.5       -> float
    - true      -> bool True
    - false     -> bool False
    - null      -> None
    - abc       -> string "abc"
    - "prod"    -> string "prod"
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def build_config_source(config: dict) -> str:
    lines = [MARKER]
    lines.append("# Auto-generated by patch_kaggle_notebook_config.py")
    lines.append("# Do not edit this cell manually before automated Kaggle push.\n")

    for key, value in config.items():
        parsed_value = parse_value(str(value)) if isinstance(value, str) else value
        lines.append(f"{key} = {repr(parsed_value)}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Patch Kaggle notebook config cell before pushing to Kaggle."
    )

    parser.add_argument(
        "--notebook",
        required=True,
        help="Path to .ipynb file, for example: main.ipynb",
    )

    parser.add_argument(
        "--out",
        default=None,
        help="Output .ipynb path. If omitted, overwrite the input notebook.",
    )

    parser.add_argument(
        "--set",
        action="append",
        default=[],
        help="Set variable value, format: NAME=VALUE. Example: --set RUN_MODE=prod",
    )

    args = parser.parse_args()

    notebook_path = Path(args.notebook)
    output_path = Path(args.out) if args.out else notebook_path

    if not notebook_path.exists():
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")

    config = {}

    for item in args.set:
        if "=" not in item:
            raise ValueError(f"Invalid --set value: {item}. Expected NAME=VALUE")

        key, raw_value = item.split("=", 1)
        key = key.strip()

        if not key.isidentifier():
            raise ValueError(f"Invalid Python variable name: {key}")

        config[key] = parse_value(raw_value.strip())

    if not config:
        raise ValueError("No config provided. Use --set NAME=VALUE")

    nb = nbformat.read(notebook_path, as_version=4)

    patched = False
    new_source = build_config_source(config)

    for cell in nb.cells:
        if cell.get("cell_type") == "code" and MARKER in cell.get("source", ""):
            cell["source"] = new_source
            patched = True
            break

    if not patched:
        raise RuntimeError(
            f"Cannot find config cell marker: {MARKER}. "
            "Please add this marker to a code cell in the notebook."
        )

    nbformat.write(nb, output_path)

    print(f"Patched notebook saved to: {output_path}")
    print("Updated config:")

    for key, value in config.items():
        print(f"  {key} = {repr(value)}")


if __name__ == "__main__":
    main()
```

Điểm quan trọng trong script:

```python
parsed_value = parse_value(str(value)) if isinstance(value, str) else value
lines.append(f"{key} = {repr(parsed_value)}")
```

Lý do cần parse value:

- Frontend/backend thường gửi mọi giá trị dưới dạng string.
- Nếu không parse, `"False"` sẽ bị ghi thành `'False'`.
- Trong Python, chuỗi `'False'` vẫn là truthy, nên `if MY_FLAG:` sẽ chạy như `True`.
- Sau khi parse đúng, `"False"` sẽ thành boolean `False`, `"300"` sẽ thành số `300`.

---

## 10. Test sửa biến ở local

Ví dụ muốn đổi config thành production:

```powershell
python patch_kaggle_notebook_config.py `
  --notebook main.ipynb `
  --set RUN_MODE=prod `
  --set HEALTHCHECK_URL=https://b6-remote-server-kaggle-2026.onrender.com/healthcheck `
  --set INTERVAL_SECONDS=300 `
  --set ENABLE_DEBUG=false `
  --set CURRENT_JOB_ID=job_001
```

Sau khi chạy, cell config trong notebook sẽ được đổi thành:

```python
# === KAGGLE_RUN_CONFIG ===
# Auto-generated by patch_kaggle_notebook_config.py
# Do not edit this cell manually before automated Kaggle push.

RUN_MODE = 'prod'
HEALTHCHECK_URL = 'https://b6-remote-server-kaggle-2026.onrender.com/healthcheck'
INTERVAL_SECONDS = 300
ENABLE_DEBUG = False
CURRENT_JOB_ID = 'job_001'
```

Bảng mapping kiểu dữ liệu:

| Giá trị truyền vào           | Python nhận được    |
| ---------------------------- | ------------------- |
| `--set INTERVAL_SECONDS=300` | `300` kiểu `int`    |
| `--set ENABLE_DEBUG=false`   | `False` kiểu `bool` |
| `--set ENABLE_DEBUG=true`    | `True` kiểu `bool`  |
| `--set RATE=1.5`             | `1.5` kiểu `float`  |
| `--set OPTIONAL_VALUE=null`  | `None`              |
| `--set RUN_MODE=prod`        | `'prod'` kiểu `str` |
| `--set RUN_MODE="prod"`      | `'prod'` kiểu `str` |

---

## 11. Kiểm tra nhanh cell config sau khi patch

Cách 1: mở `main.ipynb` và xem cell config.

Cách 2: dùng Python kiểm tra nhanh.

Trên PowerShell:

```powershell
python -c "import nbformat; nb=nbformat.read('main.ipynb', as_version=4); [print(c.source) for c in nb.cells if c.cell_type=='code' and '# === KAGGLE_RUN_CONFIG ===' in c.source]"
```

Nếu dùng bản build:

```powershell
python -c "import nbformat; nb=nbformat.read('main.kaggle.ipynb', as_version=4); [print(c.source) for c in nb.cells if c.cell_type=='code' and '# === KAGGLE_RUN_CONFIG ===' in c.source]"
```

---

## 12. Push notebook lên Kaggle

Sau khi notebook đã được patch:

```powershell
kaggle kernels push -p .
```

Lệnh này sẽ:

```text
1. Đọc `kernel-metadata.json`
2. Lấy file notebook được khai báo trong `code_file`
3. Upload notebook lên Kaggle
4. Tạo version mới cho notebook/kernel
5. Kaggle tự chạy version mới đó
```

Nếu cần GPU, có thể chỉnh trong `kernel-metadata.json`:

```json
"enable_gpu": "true"
```

Hoặc nếu Kaggle CLI đang dùng có hỗ trợ accelerator:

```powershell
kaggle kernels push -p . --accelerator NvidiaTeslaT4
```

---

## 13. Theo dõi status và tải output

Kiểm tra trạng thái notebook:

```powershell
kaggle kernels status your-kaggle-username/my-kaggle-notebook
```

Ví dụ:

```powershell
kaggle kernels status ohyun/my-kaggle-notebook
```

Tải output sau khi notebook chạy xong:

```powershell
kaggle kernels output your-kaggle-username/my-kaggle-notebook -p ./output
```

Ghi đè output cũ nếu cần:

```powershell
kaggle kernels output your-kaggle-username/my-kaggle-notebook -p ./output -o
```

---

## 14. Script PowerShell chạy trọn quy trình

Tạo file `push_to_kaggle.ps1`:

```powershell
param(
    [string]$RunMode = "prod",
    [string]$HealthcheckUrl = "https://b6-remote-server-kaggle-2026.onrender.com/healthcheck",
    [int]$IntervalSeconds = 300,
    [bool]$EnableDebug = $false,
    [string]$CurrentJobId = "job_001"
)

Write-Host "Patching notebook config..."

python patch_kaggle_notebook_config.py `
  --notebook main.ipynb `
  --set RUN_MODE=$RunMode `
  --set HEALTHCHECK_URL=$HealthcheckUrl `
  --set INTERVAL_SECONDS=$IntervalSeconds `
  --set ENABLE_DEBUG=$($EnableDebug.ToString().ToLower()) `
  --set CURRENT_JOB_ID=$CurrentJobId

if ($LASTEXITCODE -ne 0) {
    Write-Error "Patch notebook failed. Stop."
    exit 1
}

Write-Host "Pushing notebook to Kaggle..."

kaggle kernels push -p .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Kaggle push failed."
    exit 1
}

Write-Host "Done. Kaggle is now running the pushed notebook version."
```

Chạy script:

```powershell
.\push_to_kaggle.ps1 `
  -RunMode "prod" `
  -HealthcheckUrl "https://b6-remote-server-kaggle-2026.onrender.com/healthcheck" `
  -IntervalSeconds 300 `
  -EnableDebug $false `
  -CurrentJobId "job_001"
```

---

## 15. Workflow thực tế mỗi lần muốn chạy Kaggle

Mỗi lần muốn chạy notebook trên Kaggle với value mới:

```powershell
.\push_to_kaggle.ps1 `
  -RunMode "prod" `
  -HealthcheckUrl "https://b6-remote-server-kaggle-2026.onrender.com/healthcheck" `
  -IntervalSeconds 300 `
  -EnableDebug $false `
  -CurrentJobId "job_001"
```

Sau đó kiểm tra status:

```powershell
kaggle kernels status your-kaggle-username/my-kaggle-notebook
```

Và tải output nếu cần:

```powershell
kaggle kernels output your-kaggle-username/my-kaggle-notebook -p ./output -o
```

---

## 16. Cách tích hợp vào backend có `edit_vars`

Nếu backend nhận `edit_vars` từ frontend, cần đảm bảo trước khi ghi vào notebook phải parse lại kiểu dữ liệu.

Ví dụ `edit_vars` nhận được:

```python
edit_vars = {
    "CURRENT_JOB_ID": "job_001",
    "ENABLE_DEBUG": "False",
    "INTERVAL_SECONDS": "300",
}
```

Không nên ghi trực tiếp:

```python
for key, value in edit_vars.items():
    lines.append(f"{key} = {repr(value)}")
```

Vì kết quả sẽ sai:

```python
CURRENT_JOB_ID = 'job_001'
ENABLE_DEBUG = 'False'
INTERVAL_SECONDS = '300'
```

Nên parse trước khi ghi:

```python
for key, value in edit_vars.items():
    parsed_value = _parse_value(value)
    lines.append(f"{key} = {repr(parsed_value)}")
```

Kết quả đúng:

```python
CURRENT_JOB_ID = 'job_001'
ENABLE_DEBUG = False
INTERVAL_SECONDS = 300
```

Hàm `_parse_value()` có thể viết như sau:

```python
import json


def _parse_value(raw):
    if not isinstance(raw, str):
        return raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
```

Nếu trong code hiện tại có các file như:

```text
src/sub_dub_video_on_kaggle.py
src/burn_ass_sub_music_on_kaggle.py
```

Thì phần build config cell nên sửa theo hướng:

```diff
for key, value in edit_vars.items():
-    lines.append(f"{key} = {repr(value)}")
+    parsed_value = _parse_value(value)
+    lines.append(f"{key} = {repr(parsed_value)}")
```

---

## 17. Best practices

### 17.1. Gom tất cả biến cần sửa vào một cell config duy nhất

Nên dùng:

```python
# === KAGGLE_RUN_CONFIG ===
RUN_MODE = "prod"
INTERVAL_SECONDS = 300
ENABLE_DEBUG = False
```

Không nên rải biến ở nhiều cell:

```python
# cell 1
RUN_MODE = "prod"

# cell 10
INTERVAL_SECONDS = 300

# cell 27
ENABLE_DEBUG = False
```

Lý do: script sẽ khó tìm và sửa chính xác nếu config bị rải nhiều nơi.

---

### 17.2. Dùng marker cố định

Nên dùng marker rõ ràng:

```python
# === KAGGLE_RUN_CONFIG ===
```

Không nên tìm cell theo tên biến như `RUN_MODE`, vì tên biến có thể xuất hiện ở nhiều cell khác.

---

### 17.3. Không để secret trực tiếp trong notebook

Không nên hard-code API key, token, password vào notebook:

```python
OPENAI_API_KEY = "sk-xxxxx"
```

Nên dùng Kaggle Secrets hoặc cơ chế secret riêng của hệ thống.

---

### 17.4. Luôn kiểm tra notebook sau khi patch

Trước khi push thật, nên kiểm tra cell config đã được ghi đúng kiểu dữ liệu chưa.

Đặc biệt kiểm tra các biến boolean và số:

```python
ENABLE_DEBUG = False
INTERVAL_SECONDS = 300
```

Không được thành:

```python
ENABLE_DEBUG = 'False'
INTERVAL_SECONDS = '300'
```

---

### 17.5. Commit notebook trước khi patch nếu dùng Git

Nếu patch trực tiếp vào `main.ipynb`, file sẽ bị thay đổi trong Git.

Có 2 hướng xử lý.

#### Hướng A: Cho phép patch trực tiếp `main.ipynb`

Phù hợp nếu bạn muốn lưu lại config đã chạy.

#### Hướng B: Tạo bản notebook riêng để push

Ví dụ:

```powershell
python patch_kaggle_notebook_config.py `
  --notebook main.ipynb `
  --out main.kaggle.ipynb `
  --set RUN_MODE=prod `
  --set ENABLE_DEBUG=false
```

Sau đó chỉnh `kernel-metadata.json`:

```json
"code_file": "main.kaggle.ipynb"
```

Cách này giúp `main.ipynb` sạch hơn, còn `main.kaggle.ipynb` là bản build để upload.

---

## 18. Lỗi thường gặp và cách xử lý

### Lỗi 1: `kaggle: command not found`

Nguyên nhân: Kaggle CLI chưa nằm trong `PATH`.

Cách xử lý:

```powershell
python -m kaggle --help
```

Nếu chạy được, có thể thay `kaggle` bằng `python -m kaggle` trong script.

---

### Lỗi 2: `403 Forbidden` hoặc lỗi authentication

Nguyên nhân thường gặp:

- Chưa login Kaggle API.
- File `kaggle.json` đặt sai vị trí.
- Token hết hạn hoặc sai.

Cách xử lý:

```powershell
kaggle auth login
```

Hoặc tải lại API token từ Kaggle settings rồi đặt lại file `kaggle.json`.

---

### Lỗi 3: `kernel-metadata.json` không hợp lệ

Kiểm tra các field quan trọng:

```json
{
  "id": "your-kaggle-username/my-kaggle-notebook",
  "code_file": "main.ipynb",
  "language": "python",
  "kernel_type": "notebook"
}
```

Cần kiểm tra:

- `id` có đúng username/slug không.
- `code_file` có đúng tên file `.ipynb` không.
- File `.ipynb` có nằm cùng thư mục với `kernel-metadata.json` không.

---

### Lỗi 4: Script không tìm thấy config cell

Thông báo thường gặp:

```text
Cannot find config cell marker: # === KAGGLE_RUN_CONFIG ===
```

Cách xử lý: thêm một code cell vào notebook:

```python
# === KAGGLE_RUN_CONFIG ===
RUN_MODE = "dev"
```

Sau đó chạy lại script patch.

---

### Lỗi 5: Thiếu `nbformat`

Hiện tượng:

```text
No module named 'nbformat'
```

Hoặc log kiểu:

```text
Thiếu thư viện 'nbformat'. Cài bằng: pip install nbformat
```

Cách xử lý:

```powershell
pip install nbformat
```

Nếu dùng `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install nbformat
```

Và thêm vào `requirements.txt`:

```text
nbformat
```

---

### Lỗi 6: Biến `False` vẫn chạy như `True`

Hiện tượng:

```python
ENABLE_DEBUG = 'False'
```

Và code:

```python
if ENABLE_DEBUG:
    print("Debug mode")
```

vẫn chạy.

Nguyên nhân: `'False'` là string không rỗng, nên trong Python nó là truthy.

Cách xử lý: parse value trước khi dùng `repr()`:

```python
parsed_value = _parse_value(value)
lines.append(f"{key} = {repr(parsed_value)}")
```

Kết quả đúng phải là:

```python
ENABLE_DEBUG = False
```

---

## 19. Kết luận

Cách làm chuẩn là:

```text
Không sửa trực tiếp trên Kaggle UI
→ tạo cell config có marker trong notebook
→ sửa biến trong notebook local bằng script
→ push notebook lên Kaggle bằng Kaggle API
→ Kaggle chạy version notebook mới đã được sửa value
```

Hai lệnh quan trọng nhất:

```powershell
python patch_kaggle_notebook_config.py --notebook main.ipynb --set RUN_MODE=prod
kaggle kernels push -p .
```

Nếu làm đúng, bạn có thể điều khiển biến trong Kaggle Notebook trước mỗi lần chạy thật mà không cần mở trình duyệt để sửa tay.

---

## 20. Nguồn tham khảo

- Kaggle CLI documentation: https://github.com/Kaggle/kaggle-cli/blob/main/docs/README.md
- Kaggle kernels command documentation: https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md
- Kaggle kernel metadata documentation: https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md
