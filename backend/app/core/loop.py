"""Windows 事件循环策略。

背景：Playwright 需要通过子进程启动它的 Node 驱动，而 asyncio 在 Windows 上
只有 **Proactor** 事件循环实现了子进程支持；如果当前策略是
`WindowsSelectorEventLoopPolicy`，`loop.subprocess_exec()` 会直接抛
`NotImplementedError`（报错栈落在 `base_events._make_subprocess_transport`）。

因此本项目必须显式使用 Proactor，且要在创建任何事件循环之前设置。
"""

from __future__ import annotations

import asyncio
import sys


def setup_event_loop_policy() -> None:
    """把 Windows 事件循环策略固定为 Proactor（其他平台为空操作）。"""
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
