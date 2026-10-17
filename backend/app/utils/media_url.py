"""媒体外链 CDN 改写：raw.githubusercontent.com → 可配置镜像（默认 jsDelivr）。

背景：PokeAPI 的官方图鉴图片与叫声托管在 raw.githubusercontent.com，国内网络常不可达，
前端浏览器直连时每张图都要卡到超时。处理原则：
**数据库忠实保存 PokeAPI 原始响应（存量数据不动），改写只发生在读出口径**——
    API 响应（app/core/schemas.py 的 field_validator）、
    统计聚合（app/core/aggregations.py）、
    数据导出（app/services/export_service.py）。

同一规则不硬编码仓库名，天然覆盖两个上游仓库：
    raw.githubusercontent.com/PokeAPI/sprites@master/...   官方图鉴图片
    raw.githubusercontent.com/PokeAPI/cries@main/...        叫声
jsDelivr 的 @ref 段支持分支名 / tag / commit hash。
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from config.settings import get_settings

# raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}；path 段必须非空
_RAW_RE = re.compile(r"^/([^/]+)/([^/]+)/([^/]+)(/.+)$")

# 模板必须包含全部占位符，缺任何一个都视为配置错误 → 透传原 URL，不产坏链
_PLACEHOLDERS = ("{owner}", "{repo}", "{ref}", "{path}")


def to_cdn_url(url: str | None, template: str | None = None) -> str | None:
    """把 raw.githubusercontent.com 外链改写为 CDN 镜像地址。

    以下输入原样返回：
        None / 空串 / 纯空白；
        非 raw.githubusercontent.com 域名（example.com、pokeapi.co、已是 CDN 的地址
        ——因此幂等，可对同一 URL 重复调用）；
        不含文件路径的仓库根 URL；
        不含全部占位符的 template（配置错误保护）。

    template 为空串 = 显式关闭改写（一键回退开关）；
    template 为 None = 取 settings.media_cdn_template（lru_cache，无热循环开销）。
    """
    if not url or not url.strip():
        return url
    if template is None:
        template = get_settings().media_cdn_template
    if not template:
        return url

    parts = urlsplit(url.strip())
    # hostname 属性已做小写归一：大小写混写、http 与 https 均可命中
    if parts.hostname != "raw.githubusercontent.com":
        return url
    m = _RAW_RE.match(parts.path)
    if m is None or not all(p in template for p in _PLACEHOLDERS):
        return url

    owner, repo, ref, path = m.groups()
    out = template.format(owner=owner, repo=repo, ref=ref, path=path.lstrip("/"))
    # 保留 query / fragment（当前数据没有，防御性处理）
    if parts.query:
        out += "?" + parts.query
    if parts.fragment:
        out += "#" + parts.fragment
    return out
