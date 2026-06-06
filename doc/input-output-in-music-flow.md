# Mô tả Input / Output của 2 flow xử lý lyrics theo timestamp

Tài liệu này mô tả chi tiết input và output của 2 notebook/flow:

1. `assign-timestamp-for-each-word-flow.ipynb`
2. `display-words-on-video-by-timestamp.ipynb`

Mục tiêu tổng thể:

```text
Flow 1:
video + audio + lyrics txt + font
→ align timestamp cho từng word
→ xuất karaoke_words.json + karaoke_words.srt
→ upload lại đủ file gốc + file xử lý lên Google Drive

Flow 2:
video + karaoke_words.json/srt + font
→ render từng word lên video theo timestamp
→ xuất video mới có chữ chạy theo lời
```

---

## 1. Tổng quan pipeline

Pipeline gồm 2 bước chính:

```text
Google Drive input folder của Flow 1
        ↓
Flow 1: Assign timestamp for each word
        ↓
Google Drive output folder của Flow 1
        ↓
Flow 2: Display words on video by timestamp
        ↓
Google Drive output folder của Flow 2
```

Sau khi sửa logic mới, output của Flow 1 đã được chuẩn hóa để có thể làm input trực tiếp cho Flow 2.

---

# FLOW 1 — Assign Timestamp For Each Word

## 1.1. Mục đích của Flow 1

Flow 1 dùng để gán timestamp cho từng từ trong lyrics.

Input là các file gốc gồm:

```text
video
audio
lyrics txt
font
```

Flow sẽ dùng audio và lyrics `.txt` để align từng từ, sau đó tạo ra:

```text
karaoke_words.json
karaoke_words.srt
```

Ngoài 2 file xử lý này, Flow 1 cũng copy lại các file gốc đã tải về gồm:

```text
video
audio
txt
ttf/otf/ttc
```

để folder output có thể dùng tiếp cho Flow 2.

---

## 1.2. Input của Flow 1

Input của Flow 1 là một Google Drive folder.

Trong folder này, mỗi bài/video nên có các file sau:

```text
<name>.mp4
<name>.wav
<name>.txt
Montserrat-Bold.ttf
```

Ví dụ:

```text
input-folder/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
└── Montserrat-Bold.ttf
```

Trong đó:

| File                  | Vai trò                                                     |
| --------------------- | ----------------------------------------------------------- |
| `song_01.mp4`         | Video gốc, dùng cho Flow 2 để render chữ                    |
| `song_01.wav`         | Audio gốc, dùng cho Flow 1 để align timestamp               |
| `song_01.txt`         | Lyrics text, dùng cho Flow 1 để biết danh sách từ cần align |
| `Montserrat-Bold.ttf` | Font dùng cho Flow 2 khi render chữ lên video               |

---

## 1.3. Quy tắc đặt tên file trong Flow 1

Audio và file `.txt` phải cùng tên stem.

Đúng:

```text
song_01.wav
song_01.txt
```

Sai:

```text
song_01.wav
lyrics_song_01.txt
```

Vì Flow 1 sẽ lấy stem của audio để tìm lyrics tương ứng.

Ví dụ:

```text
song_01.wav → cần song_01.txt
my_music.mp3 → cần my_music.txt
```

---

## 1.4. Các định dạng file được hỗ trợ ở Flow 1

### Audio

```python
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a"}
```

Các file audio hợp lệ:

```text
.mp3
.wav
.flac
.m4a
```

### Video

```python
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
```

Các file video hợp lệ:

```text
.mp4
.mov
.mkv
.avi
.webm
.m4v
```

### Font

```python
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
```

Các file font hợp lệ:

```text
.ttf
.otf
.ttc
```

### Lyrics

Lyrics phải là file:

```text
.txt
```

---

## 1.5. Cấu trúc input khuyến nghị cho 1 bài

```text
input-folder/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
└── Montserrat-Bold.ttf
```

Hoặc nếu dùng `.mp3`:

```text
input-folder/
├── song_01.mp4
├── song_01.mp3
├── song_01.txt
└── Montserrat-Bold.ttf
```

---

## 1.6. Cấu trúc input khuyến nghị cho nhiều bài

Nếu mỗi bài dùng chung một font:

```text
input-folder/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
├── song_02.mp4
├── song_02.wav
├── song_02.txt
├── song_03.mp4
├── song_03.wav
├── song_03.txt
└── Montserrat-Bold.ttf
```

Flow 1 sẽ copy font chung này vào từng folder output.

Output mong muốn:

```text
output/
├── song_01/
│   ├── song_01.mp4
│   ├── song_01.wav
│   ├── song_01.txt
│   ├── Montserrat-Bold.ttf
│   ├── karaoke_words.json
│   └── karaoke_words.srt
├── song_02/
│   ├── song_02.mp4
│   ├── song_02.wav
│   ├── song_02.txt
│   ├── Montserrat-Bold.ttf
│   ├── karaoke_words.json
│   └── karaoke_words.srt
└── song_03/
    ├── song_03.mp4
    ├── song_03.wav
    ├── song_03.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    └── karaoke_words.srt
```

---

## 1.7. Cấu trúc input nếu mỗi bài có font riêng

Nếu mỗi bài dùng font riêng, nên đặt tên font theo stem bài hát hoặc để trong logic tìm font phù hợp.

Ví dụ:

```text
input-folder/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
├── song_01.ttf
├── song_02.mp4
├── song_02.wav
├── song_02.txt
└── song_02.ttf
```

Output mong muốn:

```text
output/
├── song_01/
│   ├── song_01.mp4
│   ├── song_01.wav
│   ├── song_01.txt
│   ├── song_01.ttf
│   ├── karaoke_words.json
│   └── karaoke_words.srt
└── song_02/
    ├── song_02.mp4
    ├── song_02.wav
    ├── song_02.txt
    ├── song_02.ttf
    ├── karaoke_words.json
    └── karaoke_words.srt
```

Tuy nhiên, cách đơn giản nhất vẫn là dùng chung một font `Montserrat-Bold.ttf`.

---

## 1.8. Output local của Flow 1

Flow 1 ghi output vào:

```text
/kaggle/working/output/
```

Mỗi bài sẽ có một folder riêng theo tên stem của audio.

Ví dụ audio là:

```text
song_01.wav
```

thì output folder là:

```text
/kaggle/working/output/song_01/
```

---

## 1.9. Output cuối cùng của Flow 1

Sau khi chạy xong, mỗi folder bài hát/video sẽ có 6 nhóm file chính:

```text
/song_01/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
├── Montserrat-Bold.ttf
├── karaoke_words.json
└── karaoke_words.srt
```

Trong đó:

| File                  | Nguồn gốc                    | Vai trò                                 |
| --------------------- | ---------------------------- | --------------------------------------- |
| `song_01.mp4`         | File gốc tải từ input folder | Dùng cho Flow 2 để render chữ lên video |
| `song_01.wav`         | File gốc tải từ input folder | Audio đã dùng để align lyrics           |
| `song_01.txt`         | File gốc tải từ input folder | Lyrics gốc                              |
| `Montserrat-Bold.ttf` | File gốc tải từ input folder | Font render chữ                         |
| `karaoke_words.json`  | File được Flow 1 tạo ra      | Timestamp từng word dạng JSON           |
| `karaoke_words.srt`   | File được Flow 1 tạo ra      | Timestamp từng word dạng SRT            |

---

## 1.10. File `karaoke_words.json`

Đây là output quan trọng nhất của Flow 1.

Cấu trúc tổng quát:

```json
{
  "format": "karaoke_words_v1",
  "song_name": "song_01",
  "audio_filename": "song_01.wav",
  "language": "vi",
  "created_at": "...",
  "word_count": 100,
  "line_count": 20,
  "unmatched_word_count": 0,
  "words": [],
  "lines": [],
  "unmatched_words": []
}
```

---

## 1.11. Cấu trúc `words[]` trong JSON

Mỗi item trong `words` đại diện cho một từ đã được gán timestamp.

Ví dụ:

```json
{
  "index": 0,
  "line_index": 0,
  "word_index_in_line": 0,
  "word": "em",
  "normalized_word": "em",
  "start": 0.14,
  "end": 0.24,
  "start_ms": 140,
  "end_ms": 240,
  "duration_ms": 100,
  "score": 0.9876
}
```

Các field quan trọng nhất đối với Flow 2:

| Field   | Ý nghĩa                                     |
| ------- | ------------------------------------------- |
| `word`  | Từ cần hiển thị                             |
| `start` | Thời điểm bắt đầu hiển thị, tính bằng giây  |
| `end`   | Thời điểm kết thúc hiển thị, tính bằng giây |

Flow 2 chủ yếu cần 3 field này:

```json
{
  "word": "em",
  "start": 0.14,
  "end": 0.24
}
```

---

## 1.12. Cấu trúc `lines[]` trong JSON

Mỗi item trong `lines` đại diện cho một dòng lyrics.

Ví dụ:

```json
{
  "line_index": 0,
  "text": "em cũng đã từng",
  "start": 0.14,
  "end": 1.8,
  "start_ms": 140,
  "end_ms": 1800,
  "duration_ms": 1660,
  "word_start_index": 0,
  "word_end_index": 3,
  "word_count": 4
}
```

Phần này hữu ích nếu sau này muốn render theo dòng, nhưng Flow 2 hiện tại chủ yếu render theo từng word.

---

## 1.13. Cấu trúc `unmatched_words[]`

Nếu có từ trong lyrics không match được timestamp, từ đó sẽ nằm trong:

```json
{
  "line_index": 0,
  "word_index_in_line": 2,
  "word": "..."
}
```

Nếu `unmatched_word_count` lớn, nghĩa là align chưa tốt hoặc lyrics không khớp với audio.

---

## 1.14. File `karaoke_words.srt`

Flow 1 cũng tạo thêm file SRT word-level.

Ví dụ:

```srt
1
00:00:00,140 --> 00:00:00,240
em

2
00:00:00,460 --> 00:00:01,100
cũng
```

Mỗi block SRT tương ứng với một word.

File này có thể dùng làm fallback cho Flow 2 nếu không dùng JSON.

---

## 1.15. Upload output của Flow 1 lên Google Drive

Sau khi xử lý xong, Flow 1 sync folder:

```text
/kaggle/working/output/
```

lên Google Drive remote folder đã cấu hình.

Do logic mới đã copy đủ file gốc vào output folder, nên folder Google Drive sau khi upload cũng có đủ:

```text
video
audio
txt
font
json
srt
```

Ví dụ:

```text
assigned-words-bridged-data/
└── song_01/
    ├── song_01.mp4
    ├── song_01.wav
    ├── song_01.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    └── karaoke_words.srt
```

---

# FLOW 2 — Display Words On Video By Timestamp

## 2.1. Mục đích của Flow 2

Flow 2 dùng để render từng word lên video theo timestamp.

Input chính của Flow 2 là output của Flow 1.

Flow 2 sẽ đọc:

```text
video
karaoke_words.json hoặc karaoke_words.srt
font
```

Sau đó tạo ra video mới có chữ hiển thị theo từng từ.

---

## 2.2. Input của Flow 2

Input của Flow 2 là một Google Drive folder chứa nhiều subfolder.

Mỗi subfolder là một bài/video.

Cấu trúc input chuẩn:

```text
input-folder/
└── song_01/
    ├── song_01.mp4
    ├── song_01.wav
    ├── song_01.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    └── karaoke_words.srt
```

Flow 2 thật sự cần 3 file sau:

```text
song_01.mp4
karaoke_words.json hoặc karaoke_words.srt
Montserrat-Bold.ttf
```

Các file còn lại:

```text
song_01.wav
song_01.txt
```

không bắt buộc cho việc render, nhưng được giữ lại để trace/debug và để folder output đầy đủ.

---

## 2.3. Các file bắt buộc để Flow 2 render thành công

Trong mỗi subfolder, cần có:

| File                                   | Bắt buộc? | Ghi chú                      |
| -------------------------------------- | --------: | ---------------------------- |
| Video `.mp4/.mov/.mkv/.avi/.webm/.m4v` |        Có | Video nền để burn subtitle   |
| `karaoke_words.json`                   |    Nên có | Dữ liệu timestamp word-level |
| `karaoke_words.srt`                    |  Fallback | Dùng nếu không có JSON       |
| Font `.ttf/.otf/.ttc`                  |        Có | Font để render chữ           |

Ưu tiên:

```text
karaoke_words.json > karaoke_words.srt
```

Tức là nếu có JSON, Flow 2 nên dùng JSON. Nếu không có JSON, mới fallback sang SRT.

---

## 2.4. Các định dạng video được hỗ trợ ở Flow 2

```python
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"
}
```

Các file hợp lệ:

```text
.mp4
.mov
.mkv
.avi
.webm
.m4v
```

---

## 2.5. Các định dạng subtitle/timestamp được hỗ trợ ở Flow 2

### JSON

```python
SUPPORTED_JSON_EXTENSIONS = {".json"}
```

File mặc định:

```text
karaoke_words.json
```

### SRT

```python
SUPPORTED_SRT_EXTENSIONS = {".srt"}
```

File mặc định:

```text
karaoke_words.srt
```

---

## 2.6. Các định dạng font được hỗ trợ ở Flow 2

```python
SUPPORTED_FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
```

Font mặc định đang dùng:

```text
Montserrat-Bold.ttf
```

---

## 2.7. Quy tắc tìm file trong Flow 2

Nếu các biến cấu hình để `None`:

```python
VIDEO_FILE_NAME = None
JSON_FILE_NAME = None
SRT_FILE_NAME = None
```

Flow 2 sẽ tự tìm file trong từng subfolder.

Tuy nhiên có một lưu ý quan trọng:

Nếu trong một subfolder có nhiều video hoặc nhiều JSON/SRT, Flow 2 có thể báo lỗi vì không biết nên chọn file nào.

Ví dụ dễ lỗi:

```text
song_01/
├── song_01.mp4
├── song_01_backup.mp4
├── karaoke_words.json
└── Montserrat-Bold.ttf
```

Nên giữ mỗi folder chỉ có một video chính.

Hoặc cấu hình rõ tên file:

```python
VIDEO_FILE_NAME = "song_01.mp4"
JSON_FILE_NAME = "karaoke_words.json"
SRT_FILE_NAME = "karaoke_words.srt"
```

---

## 2.8. Output local của Flow 2

Flow 2 ghi video output vào chính folder bài/video.

Nếu input là:

```text
/kaggle/working/output/song_01/song_01.mp4
```

thì output mặc định là:

```text
/kaggle/working/output/song_01/song_01_with_words.mp4
```

---

## 2.9. Output cuối cùng của Flow 2

Sau khi Flow 2 chạy xong, mỗi folder sẽ có thêm file video render chữ:

```text
output/
└── song_01/
    ├── song_01.mp4
    ├── song_01.wav
    ├── song_01.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    ├── karaoke_words.srt
    └── song_01_with_words.mp4
```

Trong đó:

| File                     | Vai trò                        |
| ------------------------ | ------------------------------ |
| `song_01.mp4`            | Video gốc                      |
| `song_01.wav`            | Audio gốc                      |
| `song_01.txt`            | Lyrics gốc                     |
| `Montserrat-Bold.ttf`    | Font render                    |
| `karaoke_words.json`     | Timestamp word-level dạng JSON |
| `karaoke_words.srt`      | Timestamp word-level dạng SRT  |
| `song_01_with_words.mp4` | Video output cuối cùng có chữ  |

---

# Quan hệ Input / Output giữa 2 flow

## 3.1. Output Flow 1 là Input Flow 2

Sau khi sửa logic mới, output của Flow 1 có dạng:

```text
flow-1-output/
└── song_01/
    ├── song_01.mp4
    ├── song_01.wav
    ├── song_01.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    └── karaoke_words.srt
```

Đây chính là input hợp lệ cho Flow 2.

Flow 2 sẽ dùng:

```text
song_01.mp4
karaoke_words.json
Montserrat-Bold.ttf
```

để tạo:

```text
song_01_with_words.mp4
```

---

## 3.2. Pipeline đầy đủ

```text
Input GDrive của Flow 1:
├── song_01.mp4
├── song_01.wav
├── song_01.txt
└── Montserrat-Bold.ttf

        ↓ Flow 1

Output GDrive của Flow 1:
└── song_01/
    ├── song_01.mp4
    ├── song_01.wav
    ├── song_01.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    └── karaoke_words.srt

        ↓ Flow 2

Output GDrive của Flow 2:
└── song_01/
    ├── song_01.mp4
    ├── song_01.wav
    ├── song_01.txt
    ├── Montserrat-Bold.ttf
    ├── karaoke_words.json
    ├── karaoke_words.srt
    └── song_01_with_words.mp4
```

---

# Checklist chuẩn trước khi chạy

## Checklist input Flow 1

Trước khi chạy Flow 1, mỗi bài nên có:

```text
[ ] 1 file video: .mp4 / .mov / .mkv / .avi / .webm / .m4v
[ ] 1 file audio: .mp3 / .wav / .flac / .m4a
[ ] 1 file lyrics: .txt
[ ] 1 file font: .ttf / .otf / .ttc
```

Audio và `.txt` phải cùng stem name:

```text
song_01.wav
song_01.txt
```

Nên để video cùng stem name:

```text
song_01.mp4
song_01.wav
song_01.txt
```

Font có thể dùng chung:

```text
Montserrat-Bold.ttf
```

---

## Checklist output Flow 1

Sau khi Flow 1 chạy xong, mỗi folder output phải có:

```text
[ ] video gốc
[ ] audio gốc
[ ] txt gốc
[ ] font gốc
[ ] karaoke_words.json
[ ] karaoke_words.srt
```

Ví dụ:

```text
song_01/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
├── Montserrat-Bold.ttf
├── karaoke_words.json
└── karaoke_words.srt
```

---

## Checklist input Flow 2

Trước khi chạy Flow 2, mỗi subfolder phải có:

```text
[ ] video gốc
[ ] karaoke_words.json hoặc karaoke_words.srt
[ ] font
```

Khuyến nghị đầy đủ:

```text
song_01/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
├── Montserrat-Bold.ttf
├── karaoke_words.json
└── karaoke_words.srt
```

---

## Checklist output Flow 2

Sau khi Flow 2 chạy xong, mỗi subfolder phải có thêm:

```text
[ ] <video_stem>_with_words.mp4
```

Ví dụ:

```text
song_01/
├── song_01.mp4
├── song_01.wav
├── song_01.txt
├── Montserrat-Bold.ttf
├── karaoke_words.json
├── karaoke_words.srt
└── song_01_with_words.mp4
```

---

# Lưu ý quan trọng

## 1. Không nên để nhiều video trong cùng một folder bài

Flow 2 có thể không biết chọn video nào nếu một folder có nhiều video.

Không nên:

```text
song_01/
├── song_01.mp4
├── song_01_old.mp4
├── song_01_backup.mp4
├── karaoke_words.json
└── Montserrat-Bold.ttf
```

Nên:

```text
song_01/
├── song_01.mp4
├── karaoke_words.json
└── Montserrat-Bold.ttf
```

---

## 2. Audio và txt phải cùng tên

Đúng:

```text
song_01.wav
song_01.txt
```

Sai:

```text
song_01.wav
lyrics.txt
```

Nếu sai tên, Flow 1 có thể không tìm thấy lyrics tương ứng.

---

## 3. Nên dùng chung một font để đơn giản hóa pipeline

Khuyến nghị:

```text
Montserrat-Bold.ttf
```

Upload một file font chung vào input folder của Flow 1.

Flow 1 sẽ copy font này vào từng folder output.

---

## 4. JSON là định dạng ưu tiên

Flow 2 nên ưu tiên dùng:

```text
karaoke_words.json
```

SRT chỉ nên dùng làm fallback:

```text
karaoke_words.srt
```

---

## 5. Output của Flow 1 hiện tại đã đủ làm input cho Flow 2

Sau khi sửa logic copy file gốc, Flow 1 không còn chỉ upload:

```text
karaoke_words.json
karaoke_words.srt
```

mà upload đầy đủ:

```text
video
audio
txt
font
json
srt
```

Vì vậy Flow 2 có thể chạy tiếp ngay từ folder output của Flow 1.
