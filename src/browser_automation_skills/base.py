"""Skill 基类定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import time

from playwright.async_api import Page, BrowserContext


@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    message: str
    data: Any = None
    error: Optional[str] = None
    screenshot: Optional[str] = None  # base64 截图
    execution_time: float = 0.0

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"[{status}] {self.message} ({self.execution_time:.2f}s)"

    def assert_success(self) -> None:
        """断言执行成功，否则抛出异常"""
        if not self.success:
            raise AssertionError(f"Skill failed: {self.error or self.message}")


class BaseSkill(ABC):
    """Skill 基类 - 所有 Skills 必须继承此类"""

    name: str = "base_skill"
    description: str = "Base skill class"

    def __init__(self, browser_context: BrowserContext, page: Optional[Page] = None, manager: Optional[Any] = None):
        """
        初始化 Skill

        Args:
            browser_context: Playwright BrowserContext 实例
            page: Playwright Page 实例（可选，如果不提供则自动获取）
            manager: SkillManager 实例（可选，用于当前页上下文管理）
        """
        self.browser_context = browser_context
        self._page = page
        self.manager = manager

        # 内部重试/等待配置（可由 SkillManager 或 create_manager 覆盖）
        # 格式: {"max_attempts": int, "backoff": float, "retry_on": [str,...]}
        self._retry_settings = getattr(manager, "_retry_settings", None) if manager is not None else None

    async def get_page(self) -> Page:
        """
        获取当前页面

        Returns:
            Page: Playwright Page 实例
        """
        if self._page is not None:
            return self._page

        if self.manager is not None and getattr(self.manager, "current_page", None) is not None:
            self._page = self.manager.current_page
            return self._page

        if self.browser_context.pages:
            self._page = self.browser_context.pages[0]
            if self.manager is not None:
                self.manager.set_current_page(self._page)
            return self._page

        self._page = await self.browser_context.new_page()
        if self.manager is not None:
            self.manager.set_current_page(self._page)
        return self._page

    def set_page(self, page: Page) -> None:
        """
        设置当前页面

        Args:
            page: Playwright Page 实例
        """
        self._page = page
        if self.manager is not None:
            self.manager.set_current_page(page)

    async def execute(self, **kwargs) -> SkillResult:
        """
        执行 Skill（带异常处理和计时）

        Returns:
            SkillResult: 执行结果
        """
        start_time = time.time()

        # 重试逻辑：如果 manager 提供了 _retry_settings，则在失败时重试
        settings = self._retry_settings or {}
        max_attempts = int(settings.get("max_attempts", 1))
        backoff = float(settings.get("backoff", 0))
        retry_on = settings.get("retry_on", ["timeout", "timed out", "not found", "failed to", "timeout waiting"]) or []

        attempt = 0
        last_result: Optional[SkillResult] = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.run(**kwargs)
            except Exception as e:
                result = SkillResult(
                    success=False,
                    message=f"Skill '{self.name}' execution raised exception: {str(e)}",
                    error=str(e)
                )

            result.execution_time = time.time() - start_time
            # 规范化 message
            if result.message is None:
                result.message = f"Skill '{self.name}' executed"

            # 成功直接返回
            if result.success:
                return result

            # 记录最后一次结果
            last_result = result

            # 决定是否重试：基于错误信息匹配或未命中的选择器/超时相关关键词
            msg_lower = (result.error or result.message or "").lower()
            should_retry = any(k in msg_lower for k in [s.lower() for s in retry_on])

            if not should_retry or attempt >= max_attempts:
                break

            # 等待指数退避
            wait_seconds = backoff * (attempt if attempt > 0 else 1)
            if wait_seconds and wait_seconds > 0:
                import asyncio as _asyncio
                await _asyncio.sleep(wait_seconds)

        # 所有尝试结束，返回最后一次结果（若无则返回失败占位）
        if last_result is not None:
            return last_result

        return SkillResult(
            success=False,
            message=f"Skill '{self.name}' execution failed without result",
            error="no result",
            execution_time=time.time() - start_time
        )

    async def wait_for_selector(self, selector: str, timeout: int = 5000,
                                retries: int = 3, backoff: float = 0.5, state: str = "visible"):
        """
        智能等待辅助：在多个重试窗口内等待元素，返回 Playwright 元素句柄或 None

        Args:
            selector: CSS 选择器或 XPath
            timeout: 单次等待超时时间（毫秒）
            retries: 重试次数
            backoff: 重试间隔基数（秒），会按尝试次数线性增长
            state: 等待状态
        """
        page = await self.get_page()
        import asyncio as _asyncio

        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                handle = await page.wait_for_selector(selector, timeout=timeout, state=state)
                if handle:
                    return handle
            except Exception:
                # 忽略并重试
                pass

            await _asyncio.sleep(backoff * attempt)

        return None

    @abstractmethod
    async def run(self, **kwargs) -> SkillResult:
        """
        具体的执行逻辑（子类必须实现）

        Returns:
            SkillResult: 执行结果
        """
        pass