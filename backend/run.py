"""启动入口。

事件循环策略必须在导入 uvicorn / 任何创建事件循环的代码之前设置，
否则 Windows 下 Playwright 无法启动子进程。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()

import uvicorn  # noqa: E402

from config.logging_config import setup_logging  # noqa: E402
from config.settings import get_settings  # noqa: E402


def main() -> None:
    s = get_settings()
    setup_logging("DEBUG" if s.debug else "INFO")
    # Render 等 PaaS 会注入 PORT 环境变量：存在时监听 0.0.0.0:$PORT
    # （云端容器必须对外暴露）；本地无 PORT，仍走 settings 的 127.0.0.1:8000
    port = int(os.environ.get("PORT") or s.api_port)
    host = "0.0.0.0" if os.environ.get("PORT") else s.api_host
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # reload 会导致定时调度重复注册
        log_level="debug" if s.debug else "info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
