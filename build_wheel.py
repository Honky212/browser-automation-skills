#!/usr/bin/env python3
"""
build_wheel.py —— 从 src/browser_automation_skills 构建 wheel

项目根目录布局:
    src/browser_automation_skills/    可编辑源码（从 wheel 解包而来）
    build_wheel.py                    本构建脚本
    dist/                             构建产物输出目录

用法:
    python build_wheel.py                   # 使用 __init__.py 里的 __version__
    python build_wheel.py --version 1.5.5   # 临时覆盖版本号
    python build_wheel.py --output dist     # 指定输出目录（默认 dist，可用 . 输出到项目根）
    python build_wheel.py --keep-all        # 不排除任何目录（连 resources 一起打包）
    python build_wheel.py --exclude docs    # 追加要排除的顶层目录（可重复）

打包范围说明:
    默认排除包内顶层 `resources/`（best_practices.md、test_case_templates/*.json 等
    文档与示例素材，非运行时代码，也没有任何模块 import 它）。
    被排除的目录只影响**该层同名目录**，不会误伤子包里的同名文件夹。

构建产物:
    <output>/browser_automation_skills-<version>-py3-none-any.whl
"""

import argparse
import base64
import hashlib
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_PKG = ROOT / "src" / "browser_automation_skills"
DIST_DIR = ROOT / "dist"

PACKAGE_NAME = "browser_automation_skills"
DIST_INFO_PREFIX = "browser_automation_skills"  # dist-info 目录前缀（Name 归一化后）

# 默认不打包的包内顶层目录（文档/示例素材，非运行时代码）
DEFAULT_EXCLUDED_DIRS = ("resources",)

# METADATA 元数据（Version 用占位符，长描述在结尾追加）
METADATA_HEADER = """Metadata-Version: 2.4
Name: browser-automation-skills
Version: {version}
Summary: AI-driven browser automation testing framework based on Playwright + LLM. 70+ reusable MCP Skills for web navigation, form filling, assertions, AI agent execution, and visual analysis.
Author:  Honky212
License-Expression: Apache-2.0
Project-URL: Homepage, https://github.com/Honky212/browser-automation-skills
Project-URL: Documentation, https://github.com/Honky212/browser-automation-skills#readme
Project-URL: Issues, https://github.com/Honky212/browser-automation-skills/issues
Keywords: browser-automation,playwright,mcp,ai-agent,testing,automation,skills,llm
Classifier: Development Status :: 4 - Beta
Classifier: Intended Audience :: Developers
Classifier: Operating System :: OS Independent
Classifier: Programming Language :: Python :: 3
Classifier: Programming Language :: Python :: 3.9
Classifier: Programming Language :: Python :: 3.10
Classifier: Programming Language :: Python :: 3.11
Classifier: Programming Language :: Python :: 3.12
Classifier: Topic :: Software Development :: Testing
Classifier: Topic :: Internet :: WWW/HTTP :: Browsers
Requires-Python: >=3.9
Description-Content-Type: text/markdown
Requires-Dist: playwright>=1.40.0
Requires-Dist: mcp>=1.0.0,<2.0.0
Requires-Dist: pyyaml>=6.0
Requires-Dist: openai>=1.0.0
Requires-Dist: openpyxl>=3.0.0
Provides-Extra: test
Requires-Dist: pytest>=7.0.0; extra == "test"
Requires-Dist: pytest-asyncio>=0.21.0; extra == "test"
Requires-Dist: pytest-html>=4.0.0; extra == "test"

"""

WHEEL_METADATA = """Wheel-Version: 1.0
Generator: build_wheel.py
Root-Is-Purelib: true
Tag: py3-none-any

"""

ENTRY_POINTS = """[console_scripts]
browser-automation-mcp = browser_automation_skills.mcp_server:main
"""

TOP_LEVEL = "browser_automation_skills\n"


def read_version() -> str:
    """从 __init__.py 读取 __version__，作为唯一版本号来源。"""
    init = SRC_PKG / "__init__.py"
    text = init.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not m:
        raise SystemExit(f"无法在 {init} 中找到 __version__")
    return m.group(1)


def read_long_description() -> str:
    """从包内 README.md 读取长描述。"""
    readme = SRC_PKG / "README.md"
    if readme.exists():
        return readme.read_text(encoding="utf-8")
    return "AI-driven browser automation testing framework."


def build_metadata(version: str, long_desc: str) -> str:
    return METADATA_HEADER.format(version=version) + long_desc


def record_hash(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")


def make_ignore(excluded_dirs):
    """
    生成 copytree 的 ignore 回调。

    - 始终忽略缓存/编译产物；
    - 仅当当前层就是包根目录时，才排除 excluded_dirs 里列出的顶层目录
      （避免误伤子包中的同名目录）。
    """
    cache_ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    excluded = {str(name).strip().strip("/\\") for name in (excluded_dirs or ()) if str(name).strip()}
    root = os.path.abspath(str(SRC_PKG))

    def _ignore(dir_path, names):
        ignored = set(cache_ignore(dir_path, names))
        if excluded and os.path.abspath(str(dir_path)) == root:
            ignored.update(name for name in names if name in excluded)
        return ignored

    return _ignore


def build_wheel(version: str, output_dir: Path, excluded_dirs=None) -> Path:
    if not SRC_PKG.exists():
        raise SystemExit(f"源码目录不存在: {SRC_PKG}")

    if excluded_dirs is None:
        excluded_dirs = DEFAULT_EXCLUDED_DIRS

    output_dir.mkdir(parents=True, exist_ok=True)
    dist_info = f"{DIST_INFO_PREFIX}-{version}.dist-info"
    wheel_name = f"{DIST_INFO_PREFIX}-{version}-py3-none-any.whl"
    wheel_path = output_dir / wheel_name

    staging = Path(tempfile.mkdtemp(prefix="whl_build_"))
    try:
        # 1) 复制源码（排除缓存/编译产物，以及 excluded_dirs 指定的顶层目录）
        pkg_staging = staging / PACKAGE_NAME
        shutil.copytree(SRC_PKG, pkg_staging, ignore=make_ignore(excluded_dirs))

        # 2) 生成 dist-info
        info_dir = staging / dist_info
        info_dir.mkdir()
        (info_dir / "METADATA").write_text(
            build_metadata(version, read_long_description()), encoding="utf-8", newline="\n"
        )
        (info_dir / "WHEEL").write_text(WHEEL_METADATA, encoding="utf-8", newline="\n")
        (info_dir / "entry_points.txt").write_text(ENTRY_POINTS, encoding="utf-8", newline="\n")
        (info_dir / "top_level.txt").write_text(TOP_LEVEL, encoding="utf-8", newline="\n")

        # 3) 生成 RECORD
        lines = []
        for root, dirs, files in os.walk(staging):
            dirs.sort()
            for f in sorted(files):
                full = Path(root) / f
                rel = full.relative_to(staging).as_posix()
                if rel.endswith("/RECORD"):
                    continue
                data = full.read_bytes()
                lines.append(f"{rel},sha256={record_hash(data)},{len(data)}")
        lines.append(f"{dist_info}/RECORD,,")
        (info_dir / "RECORD").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

        # 4) 打包 wheel
        if wheel_path.exists():
            wheel_path.unlink()
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(staging):
                dirs.sort()
                for f in sorted(files):
                    full = Path(root) / f
                    zf.write(full, full.relative_to(staging).as_posix())
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return wheel_path


def main():
    parser = argparse.ArgumentParser(description="从 src/browser_automation_skills 构建 wheel")
    parser.add_argument("--version", help="覆盖 __init__.py 中的版本号")
    parser.add_argument("--output", default=str(DIST_DIR), help="输出目录 (默认 dist)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help=f"追加要排除的顶层目录（可重复；默认排除 {', '.join(DEFAULT_EXCLUDED_DIRS)}）",
    )
    parser.add_argument(
        "--keep-all", action="store_true", help="不排除任何目录（连 resources 一起打包）"
    )
    args = parser.parse_args()

    if args.keep_all:
        excluded = ()
    else:
        excluded = tuple(DEFAULT_EXCLUDED_DIRS) + tuple(args.exclude or ())

    version = args.version or read_version()
    wheel_path = build_wheel(version, Path(args.output), excluded_dirs=excluded)
    print(f"Built: {wheel_path}")
    print(f"Version: {version}")
    print(f"Size: {wheel_path.stat().st_size} bytes")
    print(f"Excluded top-level dirs: {list(excluded) if excluded else '（无）'}")


if __name__ == "__main__":
    main()

