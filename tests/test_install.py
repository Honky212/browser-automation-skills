# -*- coding: utf-8 -*-
"""手动运行的安装冒烟脚本（非 pytest 用例）：启动浏览器 → 访问百度 → 读取页面信息。

    python tests/test_install.py

依赖真实浏览器与外网，因此不纳入 pytest 自动收集；
模块顶层不再执行任何逻辑，避免被收集时产生副作用。
"""
import asyncio

from browser_automation_skills.browser_launcher import BrowserLauncher
from browser_automation_skills import create_manager


async def main():
    launcher = BrowserLauncher(headless=True)
    context = await launcher.launch()
    manager = create_manager(browser_context=context)

    result = await manager.execute("navigate", url="https://www.baidu.com")
    print(f"导航: {result.success} - {result.message}")

    info = await manager.execute("get_page_info")
    print(f"页面信息: {info.data}")

    await launcher.close()
    print("验证通过！")


if __name__ == "__main__":
    asyncio.run(main())
