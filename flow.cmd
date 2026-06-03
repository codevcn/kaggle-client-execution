@echo off
chcp 65001 >nul
setlocal

REM Di chuyen ve thu muc goc chua flow.cmd nay
cd /d "%~dp0"

REM Kich hoat moi truong ao .venv
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

REM Chay orchestrator chinh
python -u src/main.py