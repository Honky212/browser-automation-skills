"""浏览器启动器 - 简化浏览器启动和管理"""

import logging
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)


class BrowserLauncher:
    """
    浏览器启动器

    负责浏览器的启动、上下文创建和关闭。
    支持 async context manager 协议，也可独立使用。
    """

    def __init__(
        self,
        headless: bool = True,
        viewport: Optional[dict] = None,
        browser_type: str = "chromium",
        extra_args: Optional[list] = None,
        executable_path: Optional[str] = None,
        user_agent: Optional[str] = None,
        disable_automation: bool = True,
    ):
        """
        初始化浏览器启动器

        Args:
            headless: 是否使用无头模式
            viewport: 视口大小，默认 {"width": 1920, "height": 1080}；
                      无头模式下使用此值，有头模式下默认不限制（no_viewport=True）
            browser_type: 浏览器类型 (chromium, firefox, webkit)
            extra_args: 额外的浏览器启动参数
            executable_path: 浏览器可执行文件路径（可选，不指定则用 Playwright 自带）
            user_agent: 自定义 User-Agent（可选）
            disable_automation: 是否添加 --disable-blink-features=AutomationControlled 参数
        """
        self.headless = headless
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.browser_type = browser_type
        self.extra_args = extra_args or []
        self.executable_path = executable_path
        self.user_agent = user_agent
        self.disable_automation = disable_automation

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def launch(self) -> BrowserContext:
        """
        启动浏览器并创建上下文

        Returns:
            BrowserContext: 浏览器上下文
        """
        self._playwright = await async_playwright().start()

        # 构建启动参数
        launch_args = list(self.extra_args) + ['--start-maximized']
        if self.disable_automation:
            launch_args.append('--disable-blink-features=AutomationControlled')

        launch_kwargs = {
            "headless": self.headless,
            "args": launch_args,
        }
        if self.executable_path:
            launch_kwargs["executable_path"] = self.executable_path

        browser_launcher = getattr(self._playwright, self.browser_type)
        self._browser = await browser_launcher.launch(**launch_kwargs)

        # 构建上下文参数
        context_kwargs = {}
        if self.user_agent:
            context_kwargs["user_agent"] = self.user_agent

        # 无头模式：使用配置的 viewport；有头模式：不限制 viewport 让页面自适应
        if self.headless:
            context_kwargs["viewport"] = self.viewport
        else:
            context_kwargs["no_viewport"] = True

        self._context = await self._browser.new_context(**context_kwargs)

        logger.info(
            "Browser launched: %s (headless=%s, executable_path=%s)",
            self.browser_type, self.headless, self.executable_path,
        )
        return self._context

    async def close(self):
        """关闭浏览器（按正确顺序：context → browser → playwright，带异常保护）"""
        if self._context:
            try:
                await self._context.close()
                logger.info("Browser context closed")
            except Exception as e:
                logger.exception("Error closing browser context: %s", e)
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
                logger.info("Browser closed")
            except Exception as e:
                logger.exception("Error closing browser: %s", e)
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
                logger.info("Playwright stopped")
            except Exception as e:
                logger.exception("Error stopping Playwright: %s", e)
            self._playwright = None

    @property
    def context(self) -> Optional[BrowserContext]:
        """获取浏览器上下文"""
        return self._context

    @property
    def browser(self) -> Optional[Browser]:
        """获取浏览器实例"""
        return self._browser

    async def __aenter__(self) -> BrowserContext:
        """支持异步上下文管理器"""
        return await self.launch()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持异步上下文管理器"""
        await self.close()
