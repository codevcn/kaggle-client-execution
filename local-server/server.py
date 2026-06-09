"""
server.py — Local FastAPI Server Entry Point
=============================================
File này chỉ làm 3 việc:
  1. Kích hoạt config (logging + dotenv) bằng cách import config
  2. Định nghĩa lifespan: dọn dẹp khi tắt (dừng flow đang chạy)
  3. Tạo FastAPI app và đăng ký tất cả routers

Mọi logic nghiệp vụ nằm trong:
  core/       — flow_manager, telegram
  routers/    — flows, configs, filters, docs, misc
  config.py   — env vars, paths, logging
  state.py    — global singletons
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import config  # noqa: F401 — kích hoạt logging.basicConfig và load_dotenv

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from state import flow_manager
from core.cloudflare import tunnel_manager
from routers import configs, docs, filters, flows, misc, webhook, notifications

logger = logging.getLogger("local-server")


# ─────────────────────────────────────────────
# Lifespan — startup / shutdown hooks
# ─────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup: khởi động Cloudflare Tunnel ────────────────────────────
    success = await tunnel_manager.start()
    if not success:
        logger.error("❌ Không thể khởi động Cloudflare Tunnel. Dừng server.")
        # Lưu ý: FastAPI không dừng ngay lập tức khi raise trong lifespan
        # Nhưng nó sẽ chặn ứng dụng nhận request hoặc crash.
        import sys
        sys.exit(1)

    yield
    
    # ── Shutdown: dừng flow đang chạy và cloudflare ────────────────────────────
    if flow_manager.is_running():
        logger.info("⏹️ Đang dừng tiến trình chạy flow...")
        await flow_manager.stop()
        
    await tunnel_manager.stop()

    logger.info("⏹️ Local Server đã dừng.")


# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────


app = FastAPI(
    title="Local FastAPI Server",
    description="FastAPI Local Server quản lý và chạy flow pipeline Kaggle",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount thư mục static (CSS, JS, ...)
app.mount("/static", StaticFiles(directory=str(config.LOCAL_SERVER_DIR / "static")), name="static")

# Đăng ký routers
app.include_router(misc.router)
app.include_router(flows.router)
app.include_router(configs.router)
app.include_router(filters.router)
app.include_router(docs.router)
app.include_router(webhook.router)
app.include_router(notifications.router)


# ─────────────────────────────────────────────
# Entrypoint khi chạy trực tiếp: python server.py
# ─────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn
    from config import LOCAL_HOST, LOCAL_PORT

    logger.info(f"🚀 Khởi động Local FastAPI Server tại http://{LOCAL_HOST}:{LOCAL_PORT}")
    logger.info(f"🔗 Trang quản lý: http://{LOCAL_HOST}:{LOCAL_PORT}/manage")
    uvicorn.run("server:app", host=LOCAL_HOST, port=LOCAL_PORT, reload=True)
