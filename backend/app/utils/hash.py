"""内容指纹：用于增量判定。"""

from __future__ import annotations

import hashlib
import json


def content_hash(payload: object) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
