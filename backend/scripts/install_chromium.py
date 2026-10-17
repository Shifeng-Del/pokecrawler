"""手动安装 Playwright Chromium 内核。

当 `playwright install chromium` 因网络问题卡住时，可先用任意方式把
官方 zip 下载到本地，再用本脚本解压到 ms-playwright 约定目录并打上
INSTALLATION_COMPLETE 标记。

用法：
    python scripts/install_chromium.py \
        --chromium /tmp/pw/chrome-win64.zip \
        --shell /tmp/pw/chrome-headless-shell-win64.zip \
        --revision 1248
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path


def default_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ms-playwright"


def extract(zip_path: Path, dest: Path) -> None:
    if not zip_path.is_file():
        raise FileNotFoundError(f"找不到压缩包：{zip_path}")
    dest.mkdir(parents=True, exist_ok=True)
    print(f"解压 {zip_path.name} ({zip_path.stat().st_size / 1048576:.1f} MB) -> {dest}")
    with zipfile.ZipFile(zip_path) as zf:
        total = len(zf.infolist())
        for i, info in enumerate(zf.infolist(), 1):
            zf.extract(info, dest)
            if i % 200 == 0 or i == total:
                print(f"  {i}/{total}")
    # zip 内部分文件（如 headless_shell.exe）需要可执行位
    for p in dest.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".exe", ".sh", ".dll"}:
            try:
                os.chmod(p, 0o755)
            except OSError:
                pass
    marker = dest / "INSTALLATION_COMPLETE"
    marker.write_text("1", encoding="utf-8")
    print(f"  已写入标记 {marker}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chromium", type=Path, required=False)
    ap.add_argument("--shell", type=Path, required=False)
    ap.add_argument("--revision", default="1248")
    ap.add_argument("--root", type=Path, default=None)
    args = ap.parse_args()

    root = args.root or default_root()
    root.mkdir(parents=True, exist_ok=True)
    print(f"安装根目录：{root}")

    if args.chromium:
        extract(args.chromium, root / f"chromium-{args.revision}")
    if args.shell:
        extract(args.shell, root / f"chromium_headless_shell-{args.revision}")

    print("完成。可用以下命令验证：")
    print("  python -c \"from playwright.async_api import async_playwright;\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
