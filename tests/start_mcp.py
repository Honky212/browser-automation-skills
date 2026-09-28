# -*- coding: utf-8 -*-
"""手动启动 MCP server 的辅助脚本（等价于 start_mcp.bat）。

    python tests/start_mcp.py --headed

路径不再硬编码：解释器用当前解释器，工作区从本文件位置逐级向上查找
含 `config/config.yaml` 的目录；浏览器目录仅在环境变量未设置且确实存在时才使用。
"""
import asyncio
import os
import sys
from pathlib import Path


def _find_workspace_root() -> Path:
    here = Path(__file__).resolve()
    for base in [here.parent, *here.parents, Path.cwd()]:
        if (base / "config" / "config.yaml").exists():
            return base
    return Path.cwd()


ROOT = _find_workspace_root()
_browsers_dir = ROOT / ".playwright-browsers"
if _browsers_dir.exists() and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_browsers_dir)

from browser_automation_skills.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    os.chdir(ROOT)
    asyncio.run(main())
