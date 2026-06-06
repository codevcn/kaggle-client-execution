# Hướng dẫn tích hợp `markdown-it` vào project Web Vanilla JavaScript

Tài liệu này mô tả chi tiết cách tích hợp thư viện [`markdown-it`](https://github.com/markdown-it/markdown-it) vào một project web dùng **HTML + CSS + JavaScript thuần**.

`markdown-it` là thư viện JavaScript dùng để chuyển đổi nội dung Markdown sang HTML. Thư viện này phù hợp khi bạn muốn xây dựng các tính năng như:

- Preview Markdown realtime.
- Hiển thị bài viết Markdown trong website.
- Làm editor ghi chú đơn giản.
- Render nội dung Markdown lấy từ API, file `.md`, CMS hoặc database.
- Tùy biến cú pháp Markdown bằng plugin.

---

## 1. Ý tưởng tích hợp tổng quát

Luồng hoạt động cơ bản:

```txt
Người dùng nhập Markdown
        ↓
JavaScript lấy nội dung Markdown
        ↓
markdown-it chuyển Markdown thành HTML
        ↓
Đưa HTML đã render vào DOM
```

Ví dụ:

```md
# Hello Markdown

Đây là **chữ in đậm**.
```

Sau khi render sẽ thành HTML tương tự:

```html
<h1>Hello Markdown</h1>
<p>Đây là <strong>chữ in đậm</strong>.</p>
```

---

## 2. Cấu trúc project đề xuất

Bạn có thể tổ chức project vanilla JS như sau:

```txt
markdown-it-demo/
├── index.html
├── css/
│   └── style.css
└── js/
    └── main.js
```

Trong đó:

- `index.html`: chứa layout giao diện.
- `style.css`: chứa CSS cho textarea và vùng preview.
- `main.js`: khởi tạo `markdown-it`, bắt sự kiện nhập liệu và render Markdown.

---

## 3. Cách 1: Tích hợp bằng CDN

Đây là cách đơn giản nhất cho project HTML/CSS/JS thuần, không cần bundler như Vite/Webpack.

### 3.1. Thêm CDN vào `index.html`

Tạo file `index.html`:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Markdown-it Vanilla JS Demo</title>
  <link rel="stylesheet" href="./css/style.css" />
</head>
<body>
  <main class="app">
    <h1>Markdown Preview với markdown-it</h1>

    <section class="editor-layout">
      <div class="editor-panel">
        <h2>Markdown Input</h2>
        <textarea id="markdownInput" spellcheck="false"># Xin chào

Đây là **Markdown Preview** dùng `markdown-it`.

- Item 1
- Item 2
- Item 3

[GitHub](https://github.com/markdown-it/markdown-it)
        </textarea>
      </div>

      <div class="preview-panel">
        <h2>HTML Preview</h2>
        <div id="preview" class="markdown-body"></div>
      </div>
    </section>
  </main>

  <!-- markdown-it CDN -->
  <script src="https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js"></script>

  <!-- App script -->
  <script src="./js/main.js"></script>
</body>
</html>
```

Khi dùng bản browser qua CDN, thư viện sẽ gắn vào `window` với tên:

```js
window.markdownit
```

Lưu ý: tên global là `markdownit`, **không có dấu gạch ngang**.

---

### 3.2. Viết CSS cơ bản

Tạo file `css/style.css`:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f5f5f5;
  color: #222;
}

.app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

h1 {
  margin-bottom: 24px;
}

.editor-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.editor-panel,
.preview-panel {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
}

textarea {
  width: 100%;
  min-height: 500px;
  padding: 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-family: Consolas, Monaco, monospace;
  font-size: 15px;
  line-height: 1.5;
  resize: vertical;
}

.markdown-body {
  min-height: 500px;
  padding: 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fafafa;
  line-height: 1.6;
  overflow-wrap: break-word;
}

.markdown-body pre {
  padding: 12px;
  background: #282c34;
  color: #fff;
  overflow-x: auto;
  border-radius: 6px;
}

.markdown-body code {
  font-family: Consolas, Monaco, monospace;
}

.markdown-body blockquote {
  margin-left: 0;
  padding-left: 16px;
  border-left: 4px solid #ccc;
  color: #666;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #ccc;
  padding: 8px;
}

@media (max-width: 768px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
}
```

---

### 3.3. Khởi tạo `markdown-it` trong JavaScript

Tạo file `js/main.js`:

```js
const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');

const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
  breaks: false,
});

function renderMarkdown() {
  const markdownText = markdownInput.value;
  const html = md.render(markdownText);
  preview.innerHTML = html;
}

markdownInput.addEventListener('input', renderMarkdown);

renderMarkdown();
```

Giải thích:

```js
const md = window.markdownit({...});
```

Dòng này tạo một instance của markdown-it.

```js
md.render(markdownText);
```

Dòng này chuyển chuỗi Markdown thành chuỗi HTML.

```js
preview.innerHTML = html;
```

Dòng này đưa HTML đã render vào giao diện.

---

## 4. Các option quan trọng của `markdown-it`

Bạn có thể cấu hình `markdown-it` khi khởi tạo:

```js
const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
  breaks: false,
});
```

### 4.1. `html`

```js
html: false
```

Quy định có cho phép HTML thô trong Markdown hay không.

Ví dụ Markdown:

```md
# Title

<script>alert('xss')</script>
```

Nếu `html: true`, HTML thô có thể được render ra DOM.

Khuyến nghị:

```js
html: false
```

Đặc biệt nếu Markdown đến từ người dùng, database, API hoặc nguồn không tin cậy.

---

### 4.2. `linkify`

```js
linkify: true
```

Tự động chuyển URL dạng text thành link.

Ví dụ:

```md
https://example.com
```

Có thể được render thành:

```html
<a href="https://example.com">https://example.com</a>
```

---

### 4.3. `typographer`

```js
typographer: true
```

Bật một số thay thế ký tự đẹp hơn, ví dụ smart quotes hoặc một số ký tự typography.

Ví dụ:

```txt
"Hello"
```

Có thể được xử lý thành dấu ngoặc kép đẹp hơn tùy nội dung.

---

### 4.4. `breaks`

```js
breaks: false
```

Quy định có chuyển xuống dòng đơn `\n` thành thẻ `<br>` hay không.

Nếu bạn muốn textarea nhập xuống dòng là preview cũng xuống dòng ngay, có thể bật:

```js
breaks: true
```

Ví dụ:

```js
const md = window.markdownit({
  breaks: true,
});
```

---

## 5. Render Markdown inline

Ngoài `render()`, markdown-it còn có `renderInline()`.

### 5.1. `render()`

Dùng cho nội dung Markdown đầy đủ:

```js
md.render('# Hello');
```

Kết quả:

```html
<h1>Hello</h1>
```

### 5.2. `renderInline()`

Dùng cho nội dung ngắn, không muốn tự bọc bằng thẻ `<p>`.

```js
md.renderInline('Hello **world**');
```

Kết quả:

```html
Hello <strong>world</strong>
```

Use case:

- Render tiêu đề nhỏ.
- Render comment ngắn.
- Render label, tooltip, caption.

---

## 6. Tích hợp với DOMPurify để an toàn hơn

Khi render Markdown ra HTML rồi gán bằng `innerHTML`, bạn cần cẩn thận với XSS.

Với nội dung Markdown do người dùng nhập hoặc lấy từ nguồn không tin cậy, nên sanitize HTML trước khi đưa vào DOM.

### 6.1. Thêm DOMPurify bằng CDN

Trong `index.html`, thêm DOMPurify trước file `main.js`:

```html
<script src="https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>
<script src="./js/main.js"></script>
```

### 6.2. Cập nhật `main.js`

```js
const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');

const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
});

function renderMarkdown() {
  const markdownText = markdownInput.value;
  const rawHtml = md.render(markdownText);
  const safeHtml = DOMPurify.sanitize(rawHtml);

  preview.innerHTML = safeHtml;
}

markdownInput.addEventListener('input', renderMarkdown);
renderMarkdown();
```

Khuyến nghị thực tế:

```txt
Markdown source → markdown-it render → DOMPurify sanitize → innerHTML
```

Không nên xem `html: false` là lớp bảo vệ duy nhất nếu dữ liệu đầu vào không tin cậy.

---

## 7. Cách 2: Tích hợp bằng npm trong project Vite/Vanilla JS

Nếu project vanilla JS của bạn dùng Vite, bạn có thể cài bằng npm.

### 7.1. Tạo project Vite vanilla

```bash
npm create vite@latest markdown-it-vite-demo -- --template vanilla
cd markdown-it-vite-demo
npm install
```

### 7.2. Cài `markdown-it`

```bash
npm install markdown-it
```

Nếu cần sanitize HTML:

```bash
npm install dompurify
```

Nếu cần syntax highlighting:

```bash
npm install highlight.js
```

---

### 7.3. Import trong `main.js`

```js
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import './style.css';

const app = document.querySelector('#app');

app.innerHTML = `
  <main class="app">
    <h1>Markdown-it với Vite Vanilla JS</h1>

    <section class="editor-layout">
      <textarea id="markdownInput"># Hello Vite

Đây là **Markdown Preview** dùng npm package.
      </textarea>

      <div id="preview" class="markdown-body"></div>
    </section>
  </main>
`;

const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
});

function renderMarkdown() {
  const rawHtml = md.render(markdownInput.value);
  const safeHtml = DOMPurify.sanitize(rawHtml);

  preview.innerHTML = safeHtml;
}

markdownInput.addEventListener('input', renderMarkdown);
renderMarkdown();
```

Chạy project:

```bash
npm run dev
```

---

## 8. Thêm syntax highlighting cho code block

Nếu bạn muốn Markdown hỗ trợ code block đẹp hơn, có thể kết hợp `highlight.js`.

Ví dụ Markdown:

````md
```js
function hello() {
  console.log('Hello markdown-it');
}
```
````

---

### 8.1. Dùng CDN

Thêm vào `index.html`:

```html
<link
  rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/highlight.js/styles/github-dark.min.css"
/>

<script src="https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/highlight.js/lib/common.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>
<script src="./js/main.js"></script>
```

Cập nhật `main.js`:

```js
const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');

const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, {
          language: lang,
          ignoreIllegals: true,
        }).value;
      } catch (error) {
        console.warn(error);
      }
    }

    return '';
  },
});

function renderMarkdown() {
  const rawHtml = md.render(markdownInput.value);
  const safeHtml = DOMPurify.sanitize(rawHtml);
  preview.innerHTML = safeHtml;
}

markdownInput.addEventListener('input', renderMarkdown);
renderMarkdown();
```

---

### 8.2. Dùng npm/Vite

```bash
npm install highlight.js
```

Trong `main.js`:

```js
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import './style.css';

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, {
          language: lang,
          ignoreIllegals: true,
        }).value;
      } catch (error) {
        console.warn(error);
      }
    }

    return '';
  },
});
```

---

## 9. Dùng plugin với `markdown-it`

Một điểm mạnh của `markdown-it` là hệ sinh thái plugin.

Cách dùng chung:

```js
md.use(pluginName, options);
```

Ví dụ với npm:

```bash
npm install markdown-it-anchor
```

```js
import MarkdownIt from 'markdown-it';
import markdownItAnchor from 'markdown-it-anchor';

const md = new MarkdownIt({
  html: false,
  linkify: true,
});

md.use(markdownItAnchor, {
  permalink: markdownItAnchor.permalink.headerLink(),
});
```

Plugin này có thể tự tạo `id` cho heading, giúp bạn làm mục lục hoặc anchor link.

Ví dụ Markdown:

```md
## Cài đặt
```

Có thể render thành:

```html
<h2 id="cai-dat">Cài đặt</h2>
```

Tùy plugin và cấu hình cụ thể, HTML output có thể khác nhau.

---

## 10. Load nội dung Markdown từ file `.md`

Nếu bạn có file Markdown riêng, ví dụ:

```txt
posts/
└── hello.md
```

Nội dung `posts/hello.md`:

```md
# Bài viết đầu tiên

Đây là nội dung được load từ file `.md`.
```

Bạn có thể dùng `fetch()` để load file:

```js
const preview = document.getElementById('preview');

const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
});

async function loadMarkdownFile() {
  try {
    const response = await fetch('./posts/hello.md');

    if (!response.ok) {
      throw new Error('Không thể tải file Markdown');
    }

    const markdownText = await response.text();
    const rawHtml = md.render(markdownText);
    const safeHtml = DOMPurify.sanitize(rawHtml);

    preview.innerHTML = safeHtml;
  } catch (error) {
    console.error(error);
    preview.innerHTML = '<p>Không thể tải nội dung.</p>';
  }
}

loadMarkdownFile();
```

Lưu ý: Cách này cần chạy qua local server, không nên mở trực tiếp bằng `file://`.

Có thể dùng extension Live Server trong VS Code hoặc chạy server đơn giản:

```bash
npx serve .
```

---

## 11. Tạo module riêng để render Markdown

Khi project lớn hơn, nên tách logic render Markdown ra file riêng.

Cấu trúc:

```txt
js/
├── main.js
└── markdown-renderer.js
```

File `js/markdown-renderer.js`:

```js
export function createMarkdownRenderer() {
  const md = window.markdownit({
    html: false,
    linkify: true,
    typographer: true,
  });

  function render(markdownText) {
    const rawHtml = md.render(markdownText);
    return DOMPurify.sanitize(rawHtml);
  }

  function renderInline(markdownText) {
    const rawHtml = md.renderInline(markdownText);
    return DOMPurify.sanitize(rawHtml);
  }

  return {
    render,
    renderInline,
  };
}
```

File `js/main.js`:

```js
import { createMarkdownRenderer } from './markdown-renderer.js';

const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');

const markdownRenderer = createMarkdownRenderer();

function updatePreview() {
  preview.innerHTML = markdownRenderer.render(markdownInput.value);
}

markdownInput.addEventListener('input', updatePreview);
updatePreview();
```

Trong `index.html`, cần dùng script type module:

```html
<script src="https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>
<script type="module" src="./js/main.js"></script>
```

---

## 12. Tùy biến link để mở tab mới

Mặc định link Markdown render ra thường là:

```html
<a href="https://example.com">https://example.com</a>
```

Nếu muốn link mở tab mới, bạn có thể override rule render link.

```js
const md = window.markdownit({
  html: false,
  linkify: true,
});

const defaultRender = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
  return self.renderToken(tokens, idx, options);
};

md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const targetIndex = tokens[idx].attrIndex('target');

  if (targetIndex < 0) {
    tokens[idx].attrPush(['target', '_blank']);
  } else {
    tokens[idx].attrs[targetIndex][1] = '_blank';
  }

  const relIndex = tokens[idx].attrIndex('rel');

  if (relIndex < 0) {
    tokens[idx].attrPush(['rel', 'noopener noreferrer']);
  } else {
    tokens[idx].attrs[relIndex][1] = 'noopener noreferrer';
  }

  return defaultRender(tokens, idx, options, env, self);
};
```

Nên thêm:

```html
target="_blank" rel="noopener noreferrer"
```

để mở tab mới an toàn hơn.

---

## 13. Tùy biến image render

Markdown image:

```md
![Alt text](./image.png)
```

Nếu muốn mọi ảnh có class riêng:

```js
const defaultImageRender = md.renderer.rules.image || function (tokens, idx, options, env, self) {
  return self.renderToken(tokens, idx, options);
};

md.renderer.rules.image = function (tokens, idx, options, env, self) {
  const classIndex = tokens[idx].attrIndex('class');

  if (classIndex < 0) {
    tokens[idx].attrPush(['class', 'markdown-image']);
  } else {
    tokens[idx].attrs[classIndex][1] += ' markdown-image';
  }

  return defaultImageRender(tokens, idx, options, env, self);
};
```

CSS:

```css
.markdown-image {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
```

---

## 14. Tạo Markdown Preview realtime hoàn chỉnh

Dưới đây là phiên bản hoàn chỉnh dùng CDN, phù hợp để copy chạy ngay.

### 14.1. `index.html`

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Markdown-it Preview</title>
  <link rel="stylesheet" href="./css/style.css" />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/highlight.js/styles/github-dark.min.css"
  />
</head>
<body>
  <main class="app">
    <h1>Markdown-it Preview</h1>

    <section class="editor-layout">
      <div class="panel">
        <h2>Editor</h2>
        <textarea id="markdownInput" spellcheck="false"># Markdown-it Preview

Đây là ví dụ **Markdown realtime preview**.

## Danh sách

- Vanilla JS
- markdown-it
- DOMPurify
- highlight.js

## Code

```js
function hello(name) {
  console.log(`Hello ${name}`);
}

hello('markdown-it');
```

## Link

https://github.com/markdown-it/markdown-it

> Đây là blockquote.
        </textarea>
      </div>

      <div class="panel">
        <h2>Preview</h2>
        <div id="preview" class="markdown-body"></div>
      </div>
    </section>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/highlight.js/lib/common.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>
  <script src="./js/main.js"></script>
</body>
</html>
```

### 14.2. `css/style.css`

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f4f4f5;
  color: #202124;
}

.app {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}

.editor-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.panel {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 16px;
  min-width: 0;
}

textarea,
.markdown-body {
  width: 100%;
  min-height: 600px;
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 16px;
}

textarea {
  font-family: Consolas, Monaco, monospace;
  font-size: 15px;
  line-height: 1.6;
  resize: vertical;
}

.markdown-body {
  background: #fafafa;
  line-height: 1.7;
  overflow-x: auto;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3 {
  line-height: 1.3;
}

.markdown-body img {
  max-width: 100%;
  height: auto;
}

.markdown-body pre {
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body code {
  font-family: Consolas, Monaco, monospace;
}

.markdown-body :not(pre) > code {
  padding: 2px 5px;
  border-radius: 4px;
  background: #eee;
}

.markdown-body blockquote {
  margin-left: 0;
  padding: 8px 16px;
  border-left: 4px solid #bbb;
  background: #f1f1f1;
  color: #555;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #ccc;
  padding: 8px 10px;
}

.markdown-body th {
  background: #eee;
}

@media (max-width: 768px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
}
```

### 14.3. `js/main.js`

```js
const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');

const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
  breaks: false,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, {
          language: lang,
          ignoreIllegals: true,
        }).value;
      } catch (error) {
        console.warn(error);
      }
    }

    return '';
  },
});

const defaultLinkOpenRender = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
  return self.renderToken(tokens, idx, options);
};

md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const targetIndex = tokens[idx].attrIndex('target');

  if (targetIndex < 0) {
    tokens[idx].attrPush(['target', '_blank']);
  } else {
    tokens[idx].attrs[targetIndex][1] = '_blank';
  }

  const relIndex = tokens[idx].attrIndex('rel');

  if (relIndex < 0) {
    tokens[idx].attrPush(['rel', 'noopener noreferrer']);
  } else {
    tokens[idx].attrs[relIndex][1] = 'noopener noreferrer';
  }

  return defaultLinkOpenRender(tokens, idx, options, env, self);
};

function renderMarkdown() {
  const markdownText = markdownInput.value;
  const rawHtml = md.render(markdownText);
  const safeHtml = DOMPurify.sanitize(rawHtml);

  preview.innerHTML = safeHtml;
}

markdownInput.addEventListener('input', renderMarkdown);
renderMarkdown();
```

---

## 15. Checklist tích hợp nhanh

Khi tích hợp vào project thật, kiểm tra các điểm sau:

- [ ] Đã thêm `markdown-it` bằng CDN hoặc npm.
- [ ] Đã khởi tạo instance `markdownit()` hoặc `new MarkdownIt()`.
- [ ] Đã dùng `md.render(markdownText)` để chuyển Markdown sang HTML.
- [ ] Đã render kết quả vào DOM.
- [ ] Nếu nội dung không tin cậy, đã dùng DOMPurify trước khi gán `innerHTML`.
- [ ] Nếu dùng code block, đã cân nhắc thêm `highlight.js`.
- [ ] Nếu link mở tab mới, đã thêm `target="_blank"` và `rel="noopener noreferrer"`.
- [ ] Nếu load file `.md`, project đang chạy qua local server, không mở trực tiếp bằng `file://`.

---

## 16. Lỗi thường gặp

### 16.1. `markdownit is not defined`

Nguyên nhân thường gặp:

- Chưa thêm script CDN.
- File `main.js` chạy trước khi CDN load xong.
- Viết sai tên global.

Sai:

```js
window.markdown-it()
```

Đúng:

```js
window.markdownit()
```

Đảm bảo thứ tự script:

```html
<script src="https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js"></script>
<script src="./js/main.js"></script>
```

---

### 16.2. Preview không cập nhật

Kiểm tra lại ID trong HTML và JavaScript.

HTML:

```html
<textarea id="markdownInput"></textarea>
<div id="preview"></div>
```

JS:

```js
const markdownInput = document.getElementById('markdownInput');
const preview = document.getElementById('preview');
```

---

### 16.3. File `.md` không load được

Nếu dùng:

```js
fetch('./posts/hello.md')
```

mà bị lỗi, hãy kiểm tra:

- File có đúng đường dẫn không.
- Project có đang chạy bằng local server không.
- DevTools Console có báo CORS hoặc 404 không.

Không nên mở file HTML trực tiếp bằng:

```txt
file:///...
```

Nên chạy local server.

---

### 16.4. HTML trong Markdown không render

Nếu bạn viết:

```md
<div>Hello</div>
```

nhưng không thấy HTML hoạt động, có thể do đang để:

```js
html: false
```

Nếu bạn thật sự cần cho phép HTML thô:

```js
const md = window.markdownit({
  html: true,
});
```

Nhưng cần nhớ: `html: true` có thể nguy hiểm nếu nội dung Markdown không đáng tin cậy. Khi bật `html: true`, nên dùng DOMPurify hoặc một cơ chế sanitize chặt chẽ.

---

## 17. Gợi ý cấu hình production

Với nội dung Markdown do admin tự viết và kiểm soát:

```js
const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
});
```

Với nội dung Markdown do user nhập:

```js
const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
});

const safeHtml = DOMPurify.sanitize(md.render(userMarkdown));
```

Với blog/documentation cần code highlighting:

```js
const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(str, {
        language: lang,
        ignoreIllegals: true,
      }).value;
    }

    return '';
  },
});
```

---

## 18. Kết luận

Để tích hợp `markdown-it` vào một project web vanilla JS, bạn chỉ cần:

1. Thêm thư viện bằng CDN hoặc npm.
2. Tạo instance `markdownit()`.
3. Dùng `md.render()` để chuyển Markdown thành HTML.
4. Đưa HTML vào vùng preview.
5. Dùng DOMPurify nếu dữ liệu đầu vào không tin cậy.

Cấu hình khuyến nghị cho đa số project:

```js
const md = window.markdownit({
  html: false,
  linkify: true,
  typographer: true,
});
```

Với cấu hình này, bạn có thể nhanh chóng xây dựng Markdown preview/editor trong project HTML/CSS/JS thuần mà vẫn dễ mở rộng thêm plugin, syntax highlighting và custom renderer sau này.
