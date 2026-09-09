"""浏览器操作 Skills"""

import base64
import os
from typing import Any, Optional, Dict, List

from playwright.async_api import Page, Download

from .base import BaseSkill, SkillResult

# 默认截图目录
DEFAULT_SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")


class NavigateSkill(BaseSkill):
    """导航到指定 URL"""

    name = "navigate"
    description = "导航到指定URL"

    async def run(self, url: str, timeout: int = 30000, wait_until: str = "load") -> SkillResult:
        """
        导航到指定 URL

        Args:
            url: 目标 URL
            timeout: 超时时间（毫秒），默认 30000
            wait_until: 等待条件，可选 "load", "domcontentloaded", "networkidle", "commit"
        """
        page = await self.get_page()
        response = await page.goto(url, timeout=timeout, wait_until=wait_until)

        if response is None:
            return SkillResult(
                success=False,
                message=f"Failed to navigate to {url}: no response received"
            )

        status = response.status
        # 收集页面信息（即使状态码非 2xx，页面可能仍加载了内容）
        page_info = {"url": page.url, "status": status, "title": await page.title()}

        if response.ok:
            # 2xx 成功
            return SkillResult(
                success=True,
                message=f"Navigated to {url} (status: {status})",
                data=page_info
            )
        elif 300 <= status < 400:
            # 3xx 重定向（Playwright 通常已自动跟随，此处保留状态码信息）
            return SkillResult(
                success=True,
                message=f"Navigated to {url} (redirect, status: {status})",
                data=page_info
            )
        else:
            # 4xx/5xx 错误
            return SkillResult(
                success=False,
                message=f"Navigation to {url} returned error status: {status}",
                error=f"HTTP {status}",
                data=page_info
            )


class ClickSkill(BaseSkill):
    """点击页面元素"""

    name = "click"
    description = "点击页面元素"

    async def run(self, selector: str, timeout: int = 10000,
                  button: str = "left", click_count: int = 1,
                  force: bool = False) -> SkillResult:
        """
        点击页面元素

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒），默认 10000
            button: 鼠标按钮，可选 "left", "right", "middle"
            click_count: 点击次数
            force: 是否强制执行（跳过可见性检查）
        """
        page = await self.get_page()
        element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="visible")

        if element is None:
            return SkillResult(
                success=False,
                message=f"Element not found after retries: {selector}"
            )

        try:
            if force:
                await element.click(button=button, click_count=click_count, force=True)
            else:
                await element.click(button=button, click_count=click_count)

            return SkillResult(
                success=True,
                message=f"Clicked element: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to click element: {str(e)}",
                error=str(e)
            )


class ScreenshotSkill(BaseSkill):
    """截取页面截图"""

    name = "screenshot"
    description = "截取当前页面截图"

    def _resolve_screenshot_dir(self) -> str:
        """
        解析截图保存目录。

        优先级：
        1. config.yaml 里 screenshot.output_dir（通过 manager.config 读取）
        2. 模块常量 DEFAULT_SCREENSHOT_DIR（兼容旧行为）

        output_dir 若为相对路径，按 MCP server 的 cwd 解析
        （即 mcp.json 里配置的 cwd，通常是项目根目录）。
        """
        cfg = {}
        if self.manager is not None and getattr(self.manager, "config", None):
            cfg = self.manager.config.get("screenshot", {}) or {}

        output_dir = cfg.get("output_dir") or DEFAULT_SCREENSHOT_DIR

        # 相对路径按 cwd 解析；os.path.join 遇到绝对路径会自动丢弃前面的 cwd
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.getcwd(), output_dir)

        return os.path.normpath(output_dir)

    async def run(self, path: Optional[str] = None, full_page: bool = False,
                  return_base64: bool = False) -> SkillResult:
        """
        截取页面截图

        所有截图统一保存到 config.yaml 中 screenshot.output_dir 指定的目录
        （默认 DEFAULT_SCREENSHOT_DIR）。调用方传入的 path 只取 basename 作为
        文件名，防止因传入 "./xxx.png" 或绝对路径导致截图散落到 cwd 或其它位置。

        Args:
            path: 保存文件名（可选；只取 basename，目录由配置决定）
            full_page: 是否截取全页
            return_base64: 是否返回 base64 编码
        """
        page = await self.get_page()

        # 统一目录：来自 config.yaml 的 screenshot.output_dir（相对路径按 cwd 解析）
        output_dir = self._resolve_screenshot_dir()
        os.makedirs(output_dir, exist_ok=True)

        # 文件名：调用方只决定文件名（取 basename），目录固定
        if path:
            filename = os.path.basename(path) or "screenshot.png"
            # 若 basename 没扩展名，补 .png
            if not os.path.splitext(filename)[1]:
                filename += ".png"
        else:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

        path = os.path.join(output_dir, filename)

        try:
            screenshot_bytes = await page.screenshot(full_page=full_page, path=path)

            result_data = {"path": path}
            screenshot_b64 = None

            if return_base64:
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                result_data["base64"] = screenshot_b64

            return SkillResult(
                success=True,
                message=f"Screenshot saved to {path}",
                data=result_data,
                screenshot=screenshot_b64
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to take screenshot: {str(e)}",
                error=str(e)
            )


class WaitForElementSkill(BaseSkill):
    """等待元素出现"""

    name = "wait_for_element"
    description = "等待元素出现"

    async def run(self, selector: str, timeout: int = 10000,
                  state: str = "visible") -> SkillResult:
        """
        等待元素出现

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒），默认 10000
            state: 等待状态，可选 "visible", "hidden", "attached", "detached"
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state=state)
            if element:
                tag = await element.evaluate("el => el.tagName.toLowerCase()")
                return SkillResult(
                    success=True,
                    message=f"Element found: {selector}",
                    data={"selector": selector, "tag": tag}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Timeout waiting for element: {selector}",
                error=str(e)
            )


class GetTextSkill(BaseSkill):
    """获取元素文本内容"""

    name = "get_text"
    description = "获取元素文本内容"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        获取元素文本内容

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒），默认 5000
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )

            text = await element.inner_text()
            return SkillResult(
                success=True,
                message=f"Got text from element: {selector}",
                data={"selector": selector, "text": text}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to get text: {str(e)}",
                error=str(e)
            )


class GetAttributeSkill(BaseSkill):
    """获取元素属性"""

    name = "get_attribute"
    description = "获取元素属性"

    async def run(self, selector: str, attribute: str, timeout: int = 5000) -> SkillResult:
        """
        获取元素属性

        Args:
            selector: CSS 选择器
            attribute: 属性名
            timeout: 超时时间（毫秒），默认 5000
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )

            value = await element.get_attribute(attribute)
            return SkillResult(
                success=True,
                message=f"Got attribute '{attribute}' from element: {selector}",
                data={"selector": selector, "attribute": attribute, "value": value}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to get attribute: {str(e)}",
                error=str(e)
            )


class GetPageInfoSkill(BaseSkill):
    """获取页面信息"""

    name = "get_page_info"
    description = "获取当前页面信息（URL、标题等）"

    async def run(self) -> SkillResult:
        """获取当前页面信息"""
        page = await self.get_page()

        url = page.url
        title = await page.title()

        return SkillResult(
            success=True,
            message="Got page info",
            data={"url": url, "title": title}
        )


class GetCurrentPageInfoSkill(BaseSkill):
    """获取当前页上下文信息"""

    name = "get_current_page_info"
    description = "获取当前 SkillManager 当前页面信息"

    async def run(self) -> SkillResult:
        page = await self.get_page()
        page_index = None
        if self.manager is not None and hasattr(self.manager, "get_current_page_index"):
            page_index = self.manager.get_current_page_index()

        return SkillResult(
            success=True,
            message="Got current page info",
            data={
                "url": page.url,
                "title": await page.title(),
                "page_index": page_index
            }
        )


class ExecuteJSSkill(BaseSkill):
    """执行页面 JavaScript 代码"""

    name = "execute_js"
    description = "在当前页面执行 JavaScript 代码"

    async def run(self, script: str, arg: Optional[Any] = None) -> SkillResult:
        """
        执行页面 JavaScript

        Args:
            script: JavaScript 代码字符串，必须返回值
            arg: 可选参数，传递给脚本
        """
        page = await self.get_page()

        try:
            if arg is not None:
                result = await page.evaluate(script, arg)
            else:
                result = await page.evaluate(script)
            return SkillResult(
                success=True,
                message="Executed JavaScript successfully",
                data={"result": result}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to execute JS: {str(e)}",
                error=str(e)
            )


class GetHTMLSkill(BaseSkill):
    """获取元素或页面 HTML"""

    name = "get_html"
    description = "获取当前页面或指定元素的 HTML 内容"

    async def run(self, selector: Optional[str] = None, outer: bool = False,
                  timeout: int = 5000) -> SkillResult:
        """
        获取 HTML 内容

        Args:
            selector: CSS 选择器，若不提供则返回整个页面 HTML
            outer: 是否返回 outerHTML，默认返回 innerHTML
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            if selector:
                element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
                if element is None:
                    return SkillResult(
                        success=False,
                        message=f"Element not found after retries: {selector}"
                    )
                html = await element.evaluate("el => el.outerHTML" if outer else "el => el.innerHTML")
            else:
                html = await page.content()

            return SkillResult(
                success=True,
                message=f"Got HTML for {'page' if not selector else selector}",
                data={"html": html}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to get HTML: {str(e)}",
                error=str(e)
            )


class ScrollIntoViewSkill(BaseSkill):
    """将元素滚动到可视区域"""

    name = "scroll_into_view"
    description = "将元素滚动到可视区域"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        将元素滚动到可视区域

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )
            await element.scroll_into_view_if_needed()
            return SkillResult(
                success=True,
                message=f"Scrolled element into view: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to scroll element into view: {str(e)}",
                error=str(e)
            )


class ScrollToSkill(BaseSkill):
    """滚动页面到指定位置"""

    name = "scroll_to"
    description = "滚动页面到指定位置"

    async def run(self, x: int = 0, y: int = 0) -> SkillResult:
        """
        滚动页面到指定坐标

        Args:
            x: 水平坐标
            y: 垂直坐标
        """
        page = await self.get_page()

        try:
            await page.evaluate(f"window.scrollTo({{left: {x}, top: {y}}})")
            return SkillResult(
                success=True,
                message=f"Scrolled page to ({x}, {y})",
                data={"x": x, "y": y}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to scroll page: {str(e)}",
                error=str(e)
            )


class FocusSkill(BaseSkill):
    """聚焦元素"""

    name = "focus"
    description = "聚焦指定元素"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        聚焦元素

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )
            await element.focus()
            return SkillResult(
                success=True,
                message=f"Focused element: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to focus element: {str(e)}",
                error=str(e)
            )


class BlurSkill(BaseSkill):
    """失焦元素"""

    name = "blur"
    description = "使指定元素失去焦点"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        使元素失焦

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )
            await element.evaluate("el => el.blur()")
            return SkillResult(
                success=True,
                message=f"Blurred element: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to blur element: {str(e)}",
                error=str(e)
            )


class DoubleClickSkill(BaseSkill):
    """双击元素"""

    name = "double_click"
    description = "双击页面元素"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        双击元素

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )
            await element.dblclick()
            return SkillResult(
                success=True,
                message=f"Double clicked element: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to double click: {str(e)}",
                error=str(e)
            )


class RightClickSkill(BaseSkill):
    """右键点击元素"""

    name = "right_click"
    description = "右键点击页面元素"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        右键点击元素

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )
            await element.click(button="right")
            return SkillResult(
                success=True,
                message=f"Right clicked element: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to right click: {str(e)}",
                error=str(e)
            )


class HandleDialogSkill(BaseSkill):
    """处理页面对话框"""

    name = "handle_dialog"
    description = "处理浏览器弹出对话框（accept/dismiss/prompt）"

    async def run(self, action: str = "accept", prompt_text: Optional[str] = None, timeout: int = 10000) -> SkillResult:
        page = await self.get_page()

        try:
            dialog = await page.wait_for_event("dialog", timeout=timeout)
            if action == "accept":
                if prompt_text is not None:
                    await dialog.accept(prompt_text)
                else:
                    await dialog.accept()
            elif action == "dismiss":
                await dialog.dismiss()
            else:
                return SkillResult(
                    success=False,
                    message=f"Unsupported dialog action: {action}"
                )

            return SkillResult(
                success=True,
                message=f"Dialog {action}ed successfully",
                data={"type": dialog.type, "message": dialog.message}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to handle dialog: {str(e)}",
                error=str(e)
            )


class WaitForDownloadSkill(BaseSkill):
    """等待下载完成"""

    name = "wait_for_download"
    description = "等待文件下载并返回下载结果"

    async def run(self, trigger_selector: Optional[str] = None,
                  save_path: Optional[str] = None,
                  timeout: int = 30000) -> SkillResult:
        page = await self.get_page()

        try:
            if trigger_selector:
                async with page.expect_download(timeout=timeout) as download_info:
                    await page.click(trigger_selector)
                download = await download_info.value
            else:
                download = await page.wait_for_event("download", timeout=timeout)

            if save_path:
                if os.path.dirname(save_path):
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                await download.save_as(save_path)
                local_path = save_path
            else:
                local_path = await download.path()

            return SkillResult(
                success=True,
                message=f"Download completed: {download.suggested_filename}",
                data={
                    "url": download.url,
                    "suggested_filename": download.suggested_filename,
                    "path": local_path,
                }
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to wait for download: {str(e)}",
                error=str(e)
            )


class DownloadFileSkill(BaseSkill):
    """下载文件并保存到指定路径"""

    name = "download_file"
    description = "触发文件下载并保存到指定路径"

    async def run(self, trigger_selector: Optional[str] = None,
                  save_path: Optional[str] = None,
                  timeout: int = 30000) -> SkillResult:
        return await WaitForDownloadSkill(self.browser_context, page=self._page, manager=self.manager).run(
            trigger_selector=trigger_selector,
            save_path=save_path,
            timeout=timeout
        )


class GetCookiesSkill(BaseSkill):
    """获取当前浏览器上下文 Cookie"""

    name = "get_cookies"
    description = "获取当前浏览器上下文中的所有 Cookie"

    async def run(self) -> SkillResult:
        try:
            cookies = await self.browser_context.cookies()
            return SkillResult(
                success=True,
                message="Fetched cookies",
                data={"cookies": cookies}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to get cookies: {str(e)}",
                error=str(e)
            )


class SetCookiesSkill(BaseSkill):
    """设置 Cookie"""

    name = "set_cookies"
    description = "设置当前浏览器上下文的 Cookie"

    async def run(self, cookies: List[Dict[str, Any]]) -> SkillResult:
        try:
            if not isinstance(cookies, list):
                return SkillResult(
                    success=False,
                    message="cookies must be a list of cookie dicts"
                )
            await self.browser_context.add_cookies(cookies)
            return SkillResult(
                success=True,
                message="Cookies set successfully",
                data={"cookies": cookies}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to set cookies: {str(e)}",
                error=str(e)
            )


class ClearCookiesSkill(BaseSkill):
    """清除 Cookie"""

    name = "clear_cookies"
    description = "清除当前浏览器上下文中的 Cookie"

    async def run(self) -> SkillResult:
        try:
            await self.browser_context.clear_cookies()
            return SkillResult(
                success=True,
                message="Cookies cleared"
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to clear cookies: {str(e)}",
                error=str(e)
            )


class GetLocalStorageSkill(BaseSkill):
    """获取 Local Storage"""

    name = "get_local_storage"
    description = "获取当前页面 Local Storage 内容"

    async def run(self) -> SkillResult:
        page = await self.get_page()
        try:
            data = await page.evaluate("() => Object.fromEntries(Object.entries(window.localStorage))")
            return SkillResult(
                success=True,
                message="Fetched local storage",
                data={"local_storage": data}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to get local storage: {str(e)}",
                error=str(e)
            )


class SetLocalStorageSkill(BaseSkill):
    """设置 Local Storage"""

    name = "set_local_storage"
    description = "设置当前页面 Local Storage"

    async def run(self, data: Dict[str, Any]) -> SkillResult:
        page = await self.get_page()
        try:
            if not isinstance(data, dict):
                return SkillResult(
                    success=False,
                    message="Data must be a dictionary"
                )
            await page.evaluate("data => { for (const [key, value] of Object.entries(data)) { window.localStorage.setItem(key, value); } }", data)
            return SkillResult(
                success=True,
                message="Local storage set successfully",
                data={"local_storage": data}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to set local storage: {str(e)}",
                error=str(e)
            )


class ClearLocalStorageSkill(BaseSkill):
    """清空 Local Storage"""

    name = "clear_local_storage"
    description = "清空当前页面 Local Storage"

    async def run(self) -> SkillResult:
        page = await self.get_page()
        try:
            await page.evaluate("() => window.localStorage.clear()")
            return SkillResult(
                success=True,
                message="Local storage cleared"
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to clear local storage: {str(e)}",
                error=str(e)
            )


class WaitForTextSkill(BaseSkill):
    """等待元素文本出现"""

    name = "wait_for_text"
    description = "等待指定元素包含文本"

    async def run(self, selector: str, text: str, timeout: int = 10000,
                  case_sensitive: bool = True, exact: bool = False) -> SkillResult:
        page = await self.get_page()
        try:
            await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            expression = (
                "(selector, expected, exact, case_sensitive) => {"
                "  const el = document.querySelector(selector);"
                "  if (!el) return false;"
                "  let actual = el.innerText;"
                "  if (!case_sensitive) { actual = actual.toLowerCase(); expected = expected.toLowerCase(); }"
                "  return exact ? actual === expected : actual.includes(expected);"
                "}"
            )
            await page.wait_for_function(expression, selector, text, exact, case_sensitive, timeout=timeout)
            actual_text = await page.evaluate("selector => document.querySelector(selector).innerText", selector)
            return SkillResult(
                success=True,
                message=f"Text condition met for {selector}",
                data={"selector": selector, "text": actual_text}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to wait for text: {str(e)}",
                error=str(e)
            )


class WaitForAttributeSkill(BaseSkill):
    """等待元素属性值满足条件"""

    name = "wait_for_attribute"
    description = "等待指定元素属性满足预期值"

    async def run(self, selector: str, attribute: str, expected: str,
                  timeout: int = 10000, exact: bool = True) -> SkillResult:
        page = await self.get_page()
        try:
            expression = (
                "(selector, attribute, expected, exact) => {"
                "  const el = document.querySelector(selector);"
                "  if (!el) return false;"
                "  const actual = el.getAttribute(attribute);"
                "  return exact ? actual === expected : actual !== null && actual.includes(expected);"
                "}"
            )
            await page.wait_for_function(expression, selector, attribute, expected, exact, timeout=timeout)
            actual = await page.evaluate("(selector, attribute) => document.querySelector(selector)?.getAttribute(attribute)", selector, attribute)
            return SkillResult(
                success=True,
                message=f"Attribute condition met for {selector}",
                data={"selector": selector, "attribute": attribute, "value": actual}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to wait for attribute: {str(e)}",
                error=str(e)
            )


class JSExpressionTrueSkill(BaseSkill):
    """断言 JS 表达式为真"""

    name = "js_expression_true"
    description = "等待 JavaScript 表达式评估为真"

    async def run(self, expression: str, timeout: int = 10000) -> SkillResult:
        page = await self.get_page()
        try:
            handle = await page.wait_for_function(expression, timeout=timeout)
            value = await handle.json_value()
            return SkillResult(
                success=True,
                message=f"JavaScript expression evaluated to true",
                data={"expression": expression, "value": value}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"JS expression check failed: {str(e)}",
                error=str(e)
            )


class WaitSkill(BaseSkill):
    """等待指定时间"""

    name = "wait"
    description = "等待指定时间（秒）"

    async def run(self, seconds: float = 1.0) -> SkillResult:
        """
        等待指定时间

        Args:
            seconds: 等待时间（秒）
        """
        import asyncio
        await asyncio.sleep(seconds)
        return SkillResult(
            success=True,
            message=f"Waited for {seconds} seconds",
            data={"waited_seconds": seconds}
        )


class ReloadSkill(BaseSkill):
    """刷新页面"""

    name = "reload"
    description = "刷新当前页面"

    async def run(self, timeout: int = 30000, wait_until: str = "load") -> SkillResult:
        """
        刷新当前页面

        Args:
            timeout: 超时时间（毫秒）
            wait_until: 等待条件
        """
        page = await self.get_page()

        try:
            await page.reload(timeout=timeout, wait_until=wait_until)
            return SkillResult(
                success=True,
                message="Page reloaded",
                data={"url": page.url, "title": await page.title()}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to reload page: {str(e)}",
                error=str(e)
            )


class GoBackSkill(BaseSkill):
    """浏览器后退"""

    name = "go_back"
    description = "浏览器后退"

    async def run(self, timeout: int = 30000) -> SkillResult:
        """浏览器后退"""
        page = await self.get_page()

        try:
            await page.go_back(timeout=timeout)
            return SkillResult(
                success=True,
                message="Navigated back",
                data={"url": page.url, "title": await page.title()}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to go back: {str(e)}",
                error=str(e)
            )


class GoForwardSkill(BaseSkill):
    """浏览器前进"""

    name = "go_forward"
    description = "浏览器前进"

    async def run(self, timeout: int = 30000) -> SkillResult:
        """浏览器前进"""
        page = await self.get_page()

        try:
            await page.go_forward(timeout=timeout)
            return SkillResult(
                success=True,
                message="Navigated forward",
                data={"url": page.url, "title": await page.title()}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to go forward: {str(e)}",
                error=str(e)
            )


# ==================== 多标签页管理 Skills ====================


class OpenNewTabSkill(BaseSkill):
    """打开新标签页"""

    name = "open_new_tab"
    description = "打开新标签页"

    async def run(self, url: Optional[str] = None, timeout: int = 30000,
                  wait_until: str = "load") -> SkillResult:
        """
        打开新标签页

        Args:
            url: 可选，打开新标签页后导航到的 URL
            timeout: 超时时间（毫秒）
            wait_until: 等待条件
        """
        page = await self.browser_context.new_page()
        self.set_page(page)

        if url:
            await page.goto(url, timeout=timeout, wait_until=wait_until)

        return SkillResult(
            success=True,
            message=f"Opened new tab{' and navigated to ' + url if url else ''}",
            data={"url": page.url, "title": await page.title(), "tab_count": len(self.browser_context.pages)}
        )


class CloseTabSkill(BaseSkill):
    """关闭当前标签页"""

    name = "close_tab"
    description = "关闭当前标签页"

    async def run(self, page_index: Optional[int] = None) -> SkillResult:
        """
        关闭指定标签页

        Args:
            page_index: 要关闭的标签页索引（从 0 开始），不指定则关闭当前页
        """
        pages = self.browser_context.pages

        if len(pages) <= 1:
            return SkillResult(
                success=False,
                message="Cannot close the last tab"
            )

        if page_index is not None:
            if page_index < 0 or page_index >= len(pages):
                return SkillResult(
                    success=False,
                    message=f"Invalid page index: {page_index}, valid range: 0-{len(pages) - 1}"
                )
            page_to_close = pages[page_index]
        else:
            page_to_close = await self.get_page()

        await page_to_close.close()

        # 更新当前页面引用
        if self.browser_context.pages:
            self.set_page(self.browser_context.pages[0])

        return SkillResult(
            success=True,
            message="Tab closed",
            data={"tab_count": len(self.browser_context.pages)}
        )


class SwitchTabSkill(BaseSkill):
    """切换到指定标签页"""

    name = "switch_tab"
    description = "切换到指定标签页"

    async def run(self, page_index: int = 0) -> SkillResult:
        """
        切换到指定标签页

        Args:
            page_index: 标签页索引（从 0 开始）
        """
        pages = self.browser_context.pages

        if page_index < 0 or page_index >= len(pages):
            return SkillResult(
                success=False,
                message=f"Invalid page index: {page_index}, valid range: 0-{len(pages) - 1}"
            )

        target_page = pages[page_index]
        await target_page.bring_to_front()
        self.set_page(target_page)

        return SkillResult(
            success=True,
            message=f"Switched to tab {page_index}",
            data={
                "page_index": page_index,
                "url": target_page.url,
                "title": await target_page.title(),
                "tab_count": len(pages)
            }
        )


class GetTabsSkill(BaseSkill):
    """获取所有标签页信息"""

    name = "get_tabs"
    description = "获取所有标签页信息"

    async def run(self) -> SkillResult:
        """获取所有标签页信息"""
        pages = self.browser_context.pages

        tabs_info = []
        for i, page in enumerate(pages):
            tabs_info.append({
                "index": i,
                "url": page.url,
                "title": await page.title()
            })

        return SkillResult(
            success=True,
            message=f"Found {len(pages)} tabs",
            data={"tabs": tabs_info, "tab_count": len(pages)}
        )


class MaximizeWindowSkill(BaseSkill):
    """最大化浏览器窗口"""

    name = "maximize_window"
    description = "最大化浏览器窗口到屏幕可用区域"

    async def run(self) -> SkillResult:
        """
        最大化浏览器窗口
        
        通过JavaScript设置窗口位置和大小到屏幕可用区域
        """
        page = await self.get_page()

        try:
            # 获取屏幕可用尺寸并设置窗口
            result = await page.evaluate("""() => {
                return {
                    availWidth: screen.availWidth,
                    availHeight: screen.availHeight,
                    width: window.outerWidth,
                    height: window.outerHeight
                };
            }""")
            
            # 设置窗口位置和大小
            await page.evaluate("""() => {
                window.moveTo(0, 0);
                window.resizeTo(screen.availWidth, screen.availHeight);
            }""")
            
            return SkillResult(
                success=True,
                message="Window maximized",
                data={
                    "screen_width": result.get("availWidth"),
                    "screen_height": result.get("availHeight"),
                    "window_width": result.get("width"),
                    "window_height": result.get("height")
                }
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to maximize window: {str(e)}",
                error=str(e)
            )


class SetWindowSizeSkill(BaseSkill):
    """设置浏览器窗口大小"""

    name = "set_window_size"
    description = "设置浏览器窗口大小"

    async def run(self, width: int = 1920, height: int = 1080) -> SkillResult:
        """
        设置浏览器窗口大小

        Args:
            width: 窗口宽度（像素）
            height: 窗口高度（像素）
        """
        page = await self.get_page()

        try:
            await page.set_viewport_size({"width": width, "height": height})
            return SkillResult(
                success=True,
                message=f"Window size set to {width}x{height}",
                data={"width": width, "height": height}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to set window size: {str(e)}",
                error=str(e)
            )


class CloseOtherTabsSkill(BaseSkill):
    """关闭其他标签页"""

    name = "close_other_tabs"
    description = "关闭除当前标签页外的所有标签页"

    async def run(self, keep_index: Optional[int] = None) -> SkillResult:
        """
        关闭除指定标签页外的所有标签页

        Args:
            keep_index: 要保留的标签页索引，不指定则保留当前页
        """
        pages = list(self.browser_context.pages)

        if keep_index is None:
            if self.manager is not None:
                current_index = self.manager.get_current_page_index()
                keep_index = current_index if current_index is not None else 0
            else:
                keep_index = 0

        keep_index = 0 if keep_index is None else keep_index
        if keep_index < 0 or keep_index >= len(pages):
            return SkillResult(
                success=False,
                message=f"Invalid page index: {keep_index}"
            )

        page_to_keep = pages[keep_index]
        closed_count = 0

        for i, page in enumerate(pages):
            if i != keep_index:
                await page.close()
                closed_count += 1

        self.set_page(page_to_keep)

        return SkillResult(
            success=True,
            message=f"Closed {closed_count} tabs, kept tab {keep_index}",
            data={"closed_count": closed_count, "tab_count": len(self.browser_context.pages)}
        )