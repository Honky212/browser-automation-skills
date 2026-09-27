"""Skill 基类定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import asyncio
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

    # 是否豁免技能级硬超时（长耗时/复合技能：execute_task、execute_batch_testcases、视觉分析等）
    timeout_exempt: bool = False

    # 稳定性默认值（可被 create_manager 注入的 _timeout_settings 覆盖）
    DEFAULT_SKILL_TIMEOUT = 30.0        # 单个技能单次执行的硬超时（秒）
    DEFAULT_SELECTOR_WAIT_BUDGET = 6.0  # 单个选择器等待的“总”时间预算（秒）
    DEFAULT_SELECTOR_TIMEOUT_MS = 3000  # 单次 wait_for_selector 的超时（毫秒）
    DEFAULT_TIMEOUT_EXEMPT_SKILLS = (
        "execute_task",
        "execute_batch_testcases",
        "analyze_page",
        "screenshot_vision",
    )

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

        # 超时预算配置（由 create_manager 注入）
        # 格式: {"skill_timeout": float, "selector_wait_budget": float, "selector_timeout_ms": int}
        self._timeout_settings = (getattr(manager, "_timeout_settings", None) or {}) if manager is not None else {}

    # ---------- 超时/预算解析 ----------

    def _positive_float(self, value: Any, fallback: float) -> float:
        """把配置值安全地转为正数，非法或不大于 0 时回退到 fallback。"""
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 else fallback

    @property
    def skill_timeout(self) -> float:
        """单个技能单次执行的硬超时（秒）；返回 0 表示不限制。"""
        raw = (self._timeout_settings or {}).get("skill_timeout")
        if raw is None:
            raw = (self._retry_settings or {}).get("skill_timeout")
        if raw is None:
            return self.DEFAULT_SKILL_TIMEOUT
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return self.DEFAULT_SKILL_TIMEOUT
        return parsed if parsed > 0 else 0.0

    @property
    def selector_wait_budget(self) -> float:
        """单个选择器等待的总时间预算（秒）；返回 0 表示不限制。"""
        raw = (self._timeout_settings or {}).get("selector_wait_budget")
        if raw is None:
            return self.DEFAULT_SELECTOR_WAIT_BUDGET
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return self.DEFAULT_SELECTOR_WAIT_BUDGET
        return parsed if parsed > 0 else 0.0

    @property
    def selector_timeout_ms(self) -> int:
        """单次 wait_for_selector 的超时（毫秒）。"""
        raw = (self._timeout_settings or {}).get("selector_timeout_ms")
        return int(self._positive_float(raw, float(self.DEFAULT_SELECTOR_TIMEOUT_MS)))

    @property
    def is_timeout_exempt(self) -> bool:
        """长耗时/复合技能（execute_task、批量执行、视觉分析等）豁免技能级硬超时。"""
        if self.timeout_exempt:
            return True
        exempt = (self._timeout_settings or {}).get("exempt_skills")
        if exempt is None:
            exempt = self.DEFAULT_TIMEOUT_EXEMPT_SKILLS
        try:
            return self.name in set(exempt)
        except TypeError:
            return False

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
        exempt = self.is_timeout_exempt
        # 复合/长耗时技能：既不套用硬超时，也不在失败后整段重跑
        max_attempts = 1 if exempt else int(settings.get("max_attempts", 1))
        backoff = float(settings.get("backoff", 0))
        retry_on = settings.get("retry_on", ["timeout", "timed out", "not found", "failed to", "timeout waiting"]) or []
        skill_timeout = 0.0 if exempt else self.skill_timeout

        attempt = 0
        last_result: Optional[SkillResult] = None

        while attempt < max_attempts:
            attempt += 1
            try:
                if skill_timeout > 0:
                    # 硬超时：避免单个技能（尤其元素等待类）长时间挂住
                    result = await asyncio.wait_for(self.run(**kwargs), timeout=skill_timeout)
                else:
                    result = await self.run(**kwargs)
            except asyncio.TimeoutError:
                result = SkillResult(
                    success=False,
                    message=f"Skill '{self.name}' timed out after {skill_timeout:.1f}s",
                    error=f"timeout after {skill_timeout:.1f}s",
                )
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

    async def wait_for_selector(self, selector: str, timeout: Optional[int] = None,
                                retries: int = 3, backoff: float = 0.5, state: str = "visible"):
        """
        智能等待辅助：在多个重试窗口内等待元素，返回 Playwright 元素句柄或 None

        Args:
            selector: CSS 选择器或 XPath
            timeout: 单次等待超时时间（毫秒）；None 时使用配置的 selector_timeout_ms
            retries: 重试次数（受 selector_wait_budget 总预算约束）
            backoff: 重试间隔基数（秒），会按尝试次数线性增长
            state: 等待状态

        稳定性说明：
            旧实现下“技能级重试（3）× 选择器级重试（3）× 单次 timeout”会让一个不存在的
            元素白等近 1 分钟。这里给整个等待过程加了一个**总时间预算**
            （默认 6 秒，见 selector_wait_budget），预算耗尽立即返回 None。
        """
        page = await self.get_page()

        timeout_ms = int(timeout) if timeout else self.selector_timeout_ms
        budget = self.selector_wait_budget
        deadline = time.monotonic() + budget if budget > 0 else None

        total_attempts = max(1, int(retries))
        attempt = 0
        while attempt < total_attempts:
            attempt += 1

            wait_ms = timeout_ms
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                wait_ms = max(1, int(min(timeout_ms, remaining * 1000)))

            try:
                handle = await page.wait_for_selector(selector, timeout=wait_ms, state=state)
                if handle:
                    return handle
            except Exception:
                # 忽略并重试
                pass

            if attempt >= total_attempts:
                break

            sleep_seconds = backoff * attempt
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sleep_seconds = min(sleep_seconds, remaining)
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)

        return None

    @abstractmethod
    async def run(self, **kwargs) -> SkillResult:
        """
        具体的执行逻辑（子类必须实现）

        Returns:
            SkillResult: 执行结果
        """
        pass