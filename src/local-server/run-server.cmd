@echo off
title Local FastAPI Server (Kaggle Client Execution)
chcp 65001 >nul

REM Di chuyen vao thu muc chua file .cmd nay (luu lai vi tri cu)
pushd "%~dp0"

echo ================================================================
echo           KAGLE CLIENT EXECUTION - LOCAL SERVER
echo ================================================================
echo.

REM Kich hoat moi truong ao .venv tu thu muc goc
if exist "..\..\.venv\Scripts\activate.bat" (
    echo [ENV] Đang kích hoạt môi trường ảo .venv tại thư mục gốc...
    call "..\..\.venv\Scripts\activate.bat"
) else (
    echo [ENV] [CẢNH BÁO] Không tìm thấy môi trường ảo .venv tại thư mục gốc!
    echo [ENV] Sẽ thử chạy bằng Python mặc định của hệ thống.
)
echo.

REM Tu dong kiem tra va cai dat cac goi can thiet
echo [SETUP] Đang kiểm tra các thư viện cần thiết...
python -c "import fastapi, uvicorn, websockets, dotenv" 2>nul
if %errorlevel% neq 0 (
    echo [SETUP] Phát hiện thiếu thư viện. Đang tự động cài đặt qua pip...
    pip install fastapi uvicorn websockets python-dotenv
    if %errorlevel% neq 0 (
        echo [SETUP] [LỖI] Không thể tự động cài đặt thư viện. Vui lòng kiểm tra kết nối mạng và pip!
        popd
        pause
        exit /b 1
    )
    echo [SETUP] Cài đặt hoàn tất.
) else (
    echo [SETUP] Tất cả các thư viện fastapi, uvicorn, websockets, python-dotenv đã sẵn sàng.
)
echo.

REM Khoi chay Local Server
echo [RUN] Đang khởi chạy Local Server...
echo ================================================================
python main.py
echo ================================================================
echo.
echo [RUN] Server đã dừng.
popd
pause
