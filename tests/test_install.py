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

asyncio.run(main())
