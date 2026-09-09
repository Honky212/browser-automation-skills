import os
import sys

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"d:\browser_automation_skills\.playwright-browsers"
os.chdir(r"d:\browser_automation_skills")

from browser_automation_skills.mcp_server import main
import asyncio
asyncio.run(main())
