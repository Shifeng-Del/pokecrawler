"""日志配置：控制台 + 文件轮转。"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from config.settings import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "crawler.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 压制第三方库的噪音
    for noisy in (
        "httpx",
        "httpcore",
        "apscheduler.executors.default",
        "asyncio",
        "aiosqlite",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
