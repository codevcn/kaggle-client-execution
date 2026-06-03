Mình đọc 3 notebook rồi. Chuỗi input/output hiện tại là:

```text
.way audio folder
→ transcribe-audio-file-flow
→ *_fixed.srt
→ translate-srt-flow
→ *_fixed_merged_translated.srt
→ omnivoice-speech-flow
→ *_speech_vn.wav
```

Lưu ý: file audio đầu vào là **`.wav`**, không phải `.way`.

## 1. `transcribe-audio-file-flow.ipynb`

Flow này nhận **folder Google Drive chứa file audio `.wav`**.

Điều kiện input cần thỏa:

```text
Input chính: Google Drive folder
File bên trong: *.wav
```

Cụ thể:

- Biến input là:

```python
DATA_INPUT_GDRIVE_URL = "https://drive.google.com/open?id=..."
```

- Link có thể là dạng:

```text
https://drive.google.com/open?id=<folder_id>
```

hoặc chỉ folder ID, vì code có hàm `extract_gdrive_id()`.

- Flow chỉ tìm file:

```python
glob.glob(f"{DOWNLOAD_DIR}/**/*.wav", recursive=True)
```

và sau đó xử lý:

```python
wav_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.wav')]
```

Nghĩa là file phải có đuôi chính xác:

```text
.wav
```

Nếu file là `.mp3`, `.m4a`, `.aac`, `.mp4`, `.WAV` viết hoa thì **hiện tại không được xử lý**.

Sau khi tải về, flow có `flatten_directory()`, nên file `.wav` có thể nằm trong thư mục con của Google Drive. Nó sẽ kéo toàn bộ `.wav` ra thư mục gốc để xử lý.

Output của flow này là:

```text
<base_name>_fixed.json
<base_name>_fixed.srt
```

Ví dụ:

```text
video01.wav
→ video01_fixed.json
→ video01_fixed.srt
```

## 2. `translate-srt-flow(1).ipynb`

Flow này nhận **folder Google Drive chứa file SRT đã được transcribe**, cụ thể là file có đuôi:

```text
*_fixed.srt
```

Điều kiện input cần thỏa:

```text
Input chính: Google Drive folder
File bên trong: *_fixed.srt
Format file: SRT chuẩn
```

Code quét file như sau:

```python
all_srt = glob.glob(os.path.join(output_dir, "*.srt"))
srt_files = sorted([f for f in all_srt if f.endswith("_fixed.srt")])
```

Vì vậy tên file bắt buộc phải kết thúc bằng:

```text
_fixed.srt
```

Ví dụ hợp lệ:

```text
abc_fixed.srt
movie_001_fixed.srt
audio_test_fixed.srt
```

Ví dụ không được xử lý:

```text
abc.srt
abc_translated.srt
abc_fixed_merged.srt
abc_fixed.SRT
```

Format SRT cần dạng chuẩn:

```text
1
00:00:01,000 --> 00:00:03,500
Subtitle text here

2
00:00:04,000 --> 00:00:06,000
Another subtitle line
```

Mỗi block cần ít nhất 3 dòng:

```text
index
timestamp
text
```

Timestamp phải có dấu:

```text
 -->
```

vì code dùng:

```python
start_str, end_str = lines[1].split(' --> ')
```

Nếu timestamp sai format hoặc thiếu `-->` thì dễ lỗi.

Flow này sẽ:

1. Tìm `*_fixed.srt`
2. Gộp các block gần nhau thành:

```text
*_fixed_merged.srt
```

3. Dịch hoặc skip LLM tùy biến:

```python
SKIP_LLM_TRANSLATION = True
```

4. Tạo output:

```text
*_fixed_merged_translated.json
*_fixed_merged_translated.srt
```

Nếu `SKIP_LLM_TRANSLATION = True`, flow vẫn tạo file `*_translated.srt`, nhưng nội dung giữ nguyên text gốc.

## 3. `omnivoice-speech-flow.ipynb`

Flow này nhận **2 loại input**:

```text
1. Folder dữ liệu chính chứa file *_fixed_merged_translated.srt
2. Folder ref audio chứa ít nhất 1 file .wav
```

### Input chính: file phụ đề

Notebook đang cấu hình:

```python
FILENAME_COMPONENT_TO_USE = "*_fixed_merged_translated.srt"
```

và tìm file bằng:

```python
all_translated_srts = glob.glob(os.path.join(OUTPUT_PATH, FILENAME_COMPONENT_TO_USE))
translated_srts = all_translated_srts[:1]
```

Điều kiện file SRT:

```text
Tên file phải match: *_fixed_merged_translated.srt
Format phải là SRT chuẩn
Encoding nên là UTF-8
```

Ví dụ hợp lệ:

```text
video01_fixed_merged_translated.srt
```

Flow chỉ xử lý **1 file đầu tiên** vì có dòng:

```python
translated_srts = all_translated_srts[:1]
```

Nghĩa là nếu folder có nhiều file `*_fixed_merged_translated.srt`, hiện tại OmniVoice chỉ lấy file đầu tiên.

Format block cũng cần chuẩn:

```text
1
00:00:01,000 --> 00:00:03,500
Nội dung cần đọc

2
00:00:04,000 --> 00:00:06,000
Nội dung tiếp theo
```

Timestamp phải theo format:

```text
%H:%M:%S,%f
```

Ví dụ:

```text
00:01:23,456
```

### Input phụ: ref audio

Notebook tải ref audio từ:

```python
REF_AUDIO_GDRIVE_FOLDER_URL
```

Sau đó tìm:

```python
glob.glob(os.path.join(REF_AUDIO_LOCATION_DIR, "**", "*.wav"), recursive=True)
```

Điều kiện ref audio:

```text
Folder ref audio phải có ít nhất 1 file .wav
```

Nếu không có `.wav`, notebook sẽ lỗi:

```python
raise FileNotFoundError("Không tìm thấy file âm thanh tham chiếu (ref audio) nào")
```

Ref audio có thể stereo hoặc sample rate khác 24000 Hz, vì code tự xử lý:

```python
Stereo → mono
Resample → 24000Hz
```

Nhưng file phải đọc được bằng `soundfile`:

```python
sf.read(REF_AUDIO_PATH, dtype="float32")
```

Output của flow này là:

```text
<base_name>_speech_vn.wav
```

Ví dụ:

```text
video01_fixed_merged_translated.srt
→ video01_fixed_merged_translated_speech_vn.wav
```

Ngoài ra cell sau còn tạo thêm file split subtitle:

```text
*_fixed_merged_translated_split.srt
```

## Tóm tắt điều kiện input của từng flow

| Flow                         | Input cần có                               | Tên file bắt buộc                              | Ghi chú                                   |
| ---------------------------- | ------------------------------------------ | ---------------------------------------------- | ----------------------------------------- |
| `transcribe-audio-file-flow` | Folder Google Drive chứa audio             | `*.wav`                                        | Chỉ xử lý `.wav` lowercase                |
| `translate-srt-flow`         | Folder chứa SRT từ bước transcribe         | `*_fixed.srt`                                  | SRT phải đúng format index/timestamp/text |
| `omnivoice-speech-flow`      | Folder chứa SRT đã dịch + folder ref audio | `*_fixed_merged_translated.srt` và ref `*.wav` | Chỉ xử lý 1 file SRT đầu tiên             |

## Kết luận quan trọng

Pipeline hiện tại yêu cầu tên file nối tiếp đúng như sau:

```text
audio.wav
→ audio_fixed.srt
→ audio_fixed_merged.srt
→ audio_fixed_merged_translated.srt
→ audio_fixed_merged_translated_speech_vn.wav
```

Nếu muốn feed file thủ công vào từng flow thì cần đảm bảo:

```text
Transcribe input: .wav
Translate input: *_fixed.srt
OmniVoice input: *_fixed_merged_translated.srt + ref audio .wav
```
