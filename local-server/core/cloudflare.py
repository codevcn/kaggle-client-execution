"""
core/cloudflare.py — Cloudflare Tunnel Manager
===============================================
Quản lý tiến trình cloudflared để expose local server ra internet.
"""

import asyncio
import logging
import re
import shutil
import subprocess
from typing import Optional

import state
from config import LOCAL_PORT
from core.kaggle_orchestrator import inject_webhook_to_config

logger = logging.getLogger("local-server")


class CloudflareTunnelManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.url: Optional[str] = None

    def is_installed(self) -> bool:
        """Kiểm tra xem cloudflared đã được cài đặt chưa."""
        return shutil.which("cloudflared") is not None

    async def start(self) -> bool:
        """Khởi động tunnel và chờ để lấy URL."""
        if not self.is_installed():
            logger.error("❌ Không tìm thấy 'cloudflared'. Vui lòng cài đặt và thêm vào PATH.")
            return False

        if self.process and self.process.poll() is None:
            logger.warning("⚠️ Cloudflare Tunnel đã đang chạy.")
            return True

        logger.info("⏳ Đang khởi động Cloudflare Tunnel...")
        
        # Chạy cloudflared tunnel
        cmd = ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{LOCAL_PORT}"]
        
        # cloudflared log ra stderr
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        # Đọc stderr để lấy URL
        url_pattern = re.compile(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com")
        
        async def _read_stderr():
            loop = asyncio.get_event_loop()
            while True:
                # Dùng asyncio.to_thread để tránh block event loop
                line = await loop.run_in_executor(None, self.process.stderr.readline)
                if not line:
                    break
                
                # In log cloudflared ra console
                stripped = line.strip()
                if stripped:
                    # Tắt log thừa để đỡ rối, chỉ log nếu có lỗi hoặc URL
                    if "INF" in stripped and "trycloudflare.com" not in stripped:
                        continue
                    
                match = url_pattern.search(line)
                if match:
                    self.url = match.group(0)
                    state.cloudflare_url = self.url
                    logger.info("=" * 60)
                    logger.info(f"🌐 CLOUDFLARE PUBLIC URL: {self.url}")
                    logger.info("=" * 60)
                    
                    # Tự động tiêm URL mới vào file base_config.json
                    inject_webhook_to_config(self.url)
                    
                    break # Lấy được URL là xong việc của reader loop này

        # Chờ tối đa 15s để lấy URL
        try:
            await asyncio.wait_for(_read_stderr(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.error("❌ Quá thời gian chờ lấy URL từ Cloudflare Tunnel.")
            await self.stop()
            return False

        if not self.url:
            logger.error("❌ Không tìm thấy URL trong output của Cloudflare.")
            await self.stop()
            return False

        return True

    async def stop(self) -> None:
        """Dừng tiến trình cloudflared."""
        if self.process and self.process.poll() is None:
            logger.info("⏹️ Đang tắt Cloudflare Tunnel...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            self.url = None
            state.cloudflare_url = None

# Singleton
tunnel_manager = CloudflareTunnelManager()
