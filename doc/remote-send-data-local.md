Được, mình khuyên bạn dùng mô hình này:

```txt
Local FastAPI chủ động mở WebSocket lên Render
Render giữ connection đó
Khi Render cần gửi data -> gửi qua WebSocket đang mở
Local nhận data và xử lý
```

FastAPI hỗ trợ WebSocket endpoint qua `@app.websocket(...)`, cần `await websocket.accept()` trước khi gửi/nhận dữ liệu; khi client ngắt kết nối thì thường xử lý bằng `WebSocketDisconnect`. ([FastAPI][1])
Phía local có thể dùng thư viện `websockets`, đây là thư viện Python phổ biến để làm WebSocket client/server trên nền `asyncio`. ([websockets][2])

---

## 1. Server FastAPI trên Render

Tạo file `main.py` trên server Render:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException
from typing import Dict
import json

app = FastAPI()

# Lưu các local client đang kết nối
connected_locals: Dict[str, WebSocket] = {}

SECRET_TOKEN = "my-secret-token"


@app.get("/")
def root():
    return {"status": "render server running"}


@app.websocket("/ws/local/{client_id}")
async def local_ws(websocket: WebSocket, client_id: str):
    token = websocket.query_params.get("token")

    if token != SECRET_TOKEN:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connected_locals[client_id] = websocket

    print(f"Local client connected: {client_id}")

    try:
        while True:
            # Nhận heartbeat hoặc message từ local
            message = await websocket.receive_text()
            print(f"Message from {client_id}: {message}")

    except WebSocketDisconnect:
        print(f"Local client disconnected: {client_id}")

    finally:
        if client_id in connected_locals:
            del connected_locals[client_id]


@app.post("/send-to-local/{client_id}")
async def send_to_local(client_id: str, payload: dict, x_api_key: str = Header(None)):
    if x_api_key != SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API key")

    websocket = connected_locals.get(client_id)

    if websocket is None:
        return {
            "success": False,
            "message": f"Local client '{client_id}' is not connected"
        }

    try:
        await websocket.send_json(payload)

        return {
            "success": True,
            "sent_to": client_id,
            "payload": payload
        }

    except Exception as e:
        if client_id in connected_locals:
            del connected_locals[client_id]

        return {
            "success": False,
            "message": "Failed to send data to local client",
            "error": str(e)
        }


@app.get("/connected-locals")
def get_connected_locals():
    return {
        "connected_clients": list(connected_locals.keys()),
        "count": len(connected_locals)
    }
```

---

## 2. `requirements.txt` cho Render

```txt
fastapi
uvicorn
```

Nếu deploy trên Render, start command thường là:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 3. Local client chủ động kết nối lên Render

Tạo file `local_client.py` ở máy local:

```python
import asyncio
import json
import websockets

RENDER_WS_URL = "wss://your-render-app.onrender.com/ws/local/my-local-pc?token=my-secret-token"


async def handle_message(data: dict):
    print("Nhận data từ Render:")
    print(data)

    # TODO: xử lý logic local ở đây
    # Ví dụ:
    # - gọi API FastAPI local
    # - lưu file
    # - chạy tool
    # - xử lý job
    # - trả kết quả ngược lại Render


async def connect_to_render():
    while True:
        try:
            print("Đang kết nối đến Render...")

            async with websockets.connect(RENDER_WS_URL) as websocket:
                print("Đã kết nối WebSocket đến Render")

                await websocket.send(json.dumps({
                    "type": "hello",
                    "message": "Local client connected"
                }))

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    await handle_message(data)

        except Exception as e:
            print("Mất kết nối hoặc lỗi:", e)
            print("Thử kết nối lại sau 5 giây...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(connect_to_render())
```

Cài thư viện ở local:

```bash
pip install websockets
```

Chạy local client:

```bash
python local_client.py
```

---

## 4. Test gửi data từ Render về local

Khi `local_client.py` đang chạy, gọi API này:

```bash
curl -X POST "https://your-render-app.onrender.com/send-to-local/my-local-pc" \
  -H "Content-Type: application/json" \
  -H "x-api-key: my-secret-token" \
  -d "{\"action\":\"print\",\"message\":\"Hello local from Render\"}"
```

Local sẽ in ra:

```txt
Nhận data từ Render:
{'action': 'print', 'message': 'Hello local from Render'}
```

---

## 5. Nếu local cũng là FastAPI server thì làm thế nào?

Bạn có thể để FastAPI local chạy như bình thường, rồi tạo một background task kết nối lên Render khi app start.

Ví dụ `local_main.py`:

```python
from fastapi import FastAPI
import asyncio
import json
import websockets

app = FastAPI()

RENDER_WS_URL = "wss://your-render-app.onrender.com/ws/local/my-local-pc?token=my-secret-token"


async def process_render_data(data: dict):
    print("Local FastAPI nhận data từ Render:", data)

    # Xử lý logic local ở đây
    # Ví dụ gọi function nội bộ, ghi database, chạy script...


async def websocket_worker():
    while True:
        try:
            print("Local FastAPI đang kết nối WebSocket đến Render...")

            async with websockets.connect(RENDER_WS_URL) as websocket:
                print("Local FastAPI đã kết nối Render")

                await websocket.send(json.dumps({
                    "type": "hello",
                    "message": "Local FastAPI connected"
                }))

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    await process_render_data(data)

        except Exception as e:
            print("WebSocket error:", e)
            print("Reconnect sau 5 giây...")
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(websocket_worker())


@app.get("/")
def root():
    return {"status": "local fastapi running"}
```

Chạy local:

```bash
uvicorn local_main:app --host 127.0.0.1 --port 8000
```

---

## Flow tổng thể

```txt
1. Local chạy local_client.py hoặc local FastAPI
2. Local mở WebSocket đến Render
3. Render lưu connection theo client_id
4. Một request gọi vào Render /send-to-local/my-local-pc
5. Render gửi JSON qua WebSocket
6. Local nhận JSON và xử lý
```

Điểm quan trọng: **Render không cần biết IP máy local**, vì local là bên chủ động mở kết nối trước. Đây là cách hợp lý hơn tunnel nếu bạn muốn local “nghe lệnh” từ server cloud.

[1]: https://fastapi.tiangolo.com/advanced/websockets/?utm_source=chatgpt.com "WebSockets"
[2]: https://websockets.readthedocs.io/?utm_source=chatgpt.com "websockets 16.0 documentation"
