"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# parents[1] 即 backend/，保证 `uvicorn app.main:app` 从任意目录启动都能导入
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.api.v1.router import api_router  # noqa: E402
from app.core.database import dispose_engine, init_db  # noqa: E402
from app.core.errors import install_error_handlers  # noqa: E402
from app.crawler.pipeline import mark_stale_jobs  # noqa: E402
from app.crawler.scheduler import setup_scheduler, shutdown_scheduler  # noqa: E402
from config.logging_config import setup_logging  # noqa: E402
from config.settings import get_settings  # noqa: E402

settings = get_settings()
setup_logging("DEBUG" if settings.debug else "INFO")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    stale = await mark_stale_jobs()
    if stale:
        logger.warning("已将 %s 个残留运行任务标记为失败", stale)
    setup_scheduler()
    logger.info("%s v%s 已启动：http://%s:%s", settings.app_name, settings.version, settings.api_host, settings.api_port)
    yield
    shutdown_scheduler()
    await dispose_engine()
    logger.info("服务已停止")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="宝可梦数据采集平台：爬虫 + 查询 + 可视化",
    lifespan=lifespan,
)

install_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


# 生产模式：前端构建产物存在时同源托管
#
# 注意：不能把 StaticFiles 挂在 "/"。挂载会按前缀吃掉所有路径，
# 命中不到的路径直接返回 404，注册在它后面的 SPA 回退路由永远不会被执行
# （表现为刷新 /charts 这类前端路由时得到 404）。
# 因此这里只挂 /assets，其余路径交给下面的显式路由处理。
def _mount_frontend() -> bool:
    dist = Path(settings.frontend_dist)
    if not dist.exists():
        logger.info("未检测到前端构建产物（%s），仅提供 API 服务", dist)
        return False
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    return True


_has_frontend = _mount_frontend()


if _has_frontend:
    _DIST = Path(settings.frontend_dist)

    @app.get("/")  # pragma: no cover - 仅生产托管时生效
    async def spa_index():
        return FileResponse(_DIST / "index.html")

    @app.get("/{full_path:path}")  # pragma: no cover - 仅生产托管时生效
    async def spa_fallback(full_path: str):
        """真实存在的静态文件直接返回，其余一律回退 index.html 交给前端路由。"""
        if full_path:
            candidate = (_DIST / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(_DIST.resolve()):
                return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
