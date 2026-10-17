"""脚本公共引导：把 backend 目录加入 sys.path 并统一 Windows 事件循环策略。"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()


def silence_closed_pipe_noise() -> None:
    """屏蔽解释器退出时的 '_ProactorBasePipeTransport.__del__' 噪音。

    Playwright 的 Node 驱动是子进程，Windows Proactor 下它的管道 transport
    可能在回收时抛 'I/O operation on closed pipe'。此时任务已经跑完、结果已写入，
    这类异常纯属收尾噪音，直接吞掉；其余 unraisable 异常照常输出。
    """
    import sys

    default_hook = sys.__unraisablehook__

    def hook(unraisable) -> None:
        if "I/O operation on closed pipe" in str(unraisable.exc_value):
            return
        default_hook(unraisable)

    sys.unraisablehook = hook


silence_closed_pipe_noise()
