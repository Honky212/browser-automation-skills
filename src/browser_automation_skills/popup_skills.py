"""弹窗处理 Skills - 用于处理 window.open 弹窗、iframe 等"""

from typing import Optional, Dict, Any

from playwright.async_api import Page

from .base import BaseSkill, SkillResult


class GetPopupPagesSkill(BaseSkill):
    """获取所有已打开的弹窗/标签页信息"""

    name = "get_popup_pages"
    description = "获取所有已打开的弹窗/标签页信息（包括 window.open 打开的窗口）"

    async def run(self) -> SkillResult:
        """获取所有弹窗/标签页信息"""
        pages = self.browser_context.pages

        pages_info = []
        for i, page in enumerate(pages):
            try:
                title = await page.title()
                url = page.url
                pages_info.append({
                    "index": i,
                    "url": url,
                    "title": title,
                    "is_current": (page == self._page)
                })
            except Exception:
                pages_info.append({
                    "index": i,
                    "url": "unknown",
                    "title": "unknown",
                    "is_current": (page == self._page)
                })

        return SkillResult(
            success=True,
            message=f"Found {len(pages)} pages/tabs",
            data={"pages": pages_info, "page_count": len(pages)}
        )


class SwitchToPopupSkill(BaseSkill):
    """切换到指定的弹窗/标签页"""

    name = "switch_to_popup"
    description = "切换到指定的弹窗或标签页（通过索引或URL匹配）"

    async def run(self, page_index: Optional[int] = None, 
                  url_contains: Optional[str] = None,
                  title_contains: Optional[str] = None,
                  timeout: int = 5000) -> SkillResult:
        """
        切换到指定的弹窗或标签页

        Args:
            page_index: 页面索引（从 0 开始）
            url_contains: URL 包含的字符串（用于模糊匹配）
            title_contains: 标题包含的字符串（用于模糊匹配）
            timeout: 等待超时（毫秒）
        """
        pages = self.browser_context.pages

        if not pages:
            return SkillResult(
                success=False,
                message="No pages available to switch to"
            )

        target_page = None

        # 优先使用索引
        if page_index is not None:
            if page_index < 0 or page_index >= len(pages):
                return SkillResult(
                    success=False,
                    message=f"Invalid page index: {page_index}, valid range: 0-{len(pages) - 1}"
                )
            target_page = pages[page_index]
        else:
            # 通过 URL 或标题匹配查找
            for page in pages:
                try:
                    match = True
                    if url_contains:
                        page_url = page.url
                        match = match and (url_contains.lower() in page_url.lower())
                    if title_contains and match:
                        page_title = await page.title()
                        match = match and (title_contains.lower() in page_title.lower())
                    if match:
                        target_page = page
                        break
                except Exception:
                    continue

        if target_page is None:
            return SkillResult(
                success=False,
                message=f"Could not find matching page. Available pages: {len(pages)}"
            )

        # 切换到目标页面
        await target_page.bring_to_front()
        self.set_page(target_page)

        return SkillResult(
            success=True,
            message=f"Switched to page: {target_page.url}",
            data={
                "url": target_page.url,
                "title": await target_page.title(),
                "page_count": len(pages)
            }
        )


class WaitForPopupSkill(BaseSkill):
    """等待弹窗出现"""

    name = "wait_for_popup"
    description = "等待弹窗出现（通过 window.open 或新标签页打开的窗口）"

    async def run(self, url_contains: Optional[str] = None,
                  title_contains: Optional[str] = None,
                  timeout: int = 10000,
                  min_pages: int = 2) -> SkillResult:
        """
        等待弹窗出现

        Args:
            url_contains: URL 包含的字符串
            title_contains: 标题包含的字符串
            timeout: 等待超时（毫秒）
            min_pages: 期望的最小页面数（包括原页面和弹窗）
        """
        import asyncio

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        timeout_seconds = timeout / 1000

        while (loop.time() - start_time) < timeout_seconds:
            pages = self.browser_context.pages

            if len(pages) >= min_pages:
                # 查找匹配的页面
                for page in pages:
                    try:
                        match = True
                        if url_contains:
                            match = match and (url_contains.lower() in page.url.lower())
                        if title_contains and match:
                            page_title = await page.title()
                            match = match and (title_contains.lower() in page_title.lower())
                        if match:
                            self.set_page(page)
                            return SkillResult(
                                success=True,
                                message=f"Popup found: {page.url}",
                                data={
                                    "url": page.url,
                                    "title": await page.title(),
                                    "page_count": len(pages)
                                }
                            )
                    except Exception:
                        continue

            await asyncio.sleep(0.5)

        return SkillResult(
            success=False,
            message=f"Timeout waiting for popup. Current pages: {len(self.browser_context.pages)}",
            data={"page_count": len(self.browser_context.pages)}
        )


class ClickInPopupSkill(BaseSkill):
    """在弹窗中点击元素"""

    name = "click_in_popup"
    description = "在弹窗/指定页面中点击元素"

    async def run(self, selector: str, 
                  page_index: Optional[int] = None,
                  url_contains: Optional[str] = None,
                  timeout: int = 10000,
                  button: str = "left",
                  force: bool = False) -> SkillResult:
        """
        在弹窗中点击元素

        Args:
            selector: CSS 选择器
            page_index: 目标页面索引
            url_contains: 目标页面URL包含的字符串
            timeout: 超时时间（毫秒）
            button: 鼠标按钮
            force: 是否强制执行
        """
        # 先切换到目标页面
        if page_index is not None or url_contains is not None:
            switch_result = await SwitchToPopupSkill(
                self.browser_context, page=self._page, manager=self.manager
            ).run(page_index=page_index, url_contains=url_contains)
            if not switch_result.success:
                return switch_result

        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, 
                                                   retries=3, backoff=0.5, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found in popup: {selector}"
                )

            if force:
                await element.click(button=button, force=True)
            else:
                await element.click(button=button)

            return SkillResult(
                success=True,
                message=f"Clicked element in popup: {selector}",
                data={"selector": selector, "page_url": page.url}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to click in popup: {str(e)}",
                error=str(e)
            )


class FillInPopupSkill(BaseSkill):
    """在弹窗中填写输入框"""

    name = "fill_in_popup"
    description = "在弹窗/指定页面中填写输入框"

    async def run(self, selector: str, value: str,
                  page_index: Optional[int] = None,
                  url_contains: Optional[str] = None,
                  timeout: int = 5000,
                  clear: bool = True) -> SkillResult:
        """
        在弹窗中填写输入框

        Args:
            selector: CSS 选择器
            value: 要填写的值
            page_index: 目标页面索引
            url_contains: 目标页面URL包含的字符串
            timeout: 超时时间（毫秒）
            clear: 是否先清空
        """
        # 先切换到目标页面
        if page_index is not None or url_contains is not None:
            switch_result = await SwitchToPopupSkill(
                self.browser_context, page=self._page, manager=self.manager
            ).run(page_index=page_index, url_contains=url_contains)
            if not switch_result.success:
                return switch_result

        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout,
                                                   retries=3, backoff=0.5, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Input element not found in popup: {selector}"
                )

            if clear:
                await element.fill("")
            await element.fill(value)

            return SkillResult(
                success=True,
                message=f"Filled input in popup: {selector}",
                data={"selector": selector, "value": value, "page_url": page.url}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to fill in popup: {str(e)}",
                error=str(e)
            )


class SelectInPopupSkill(BaseSkill):
    """在弹窗中选择下拉框选项"""

    name = "select_in_popup"
    description = "在弹窗/指定页面中选择下拉框选项"

    async def run(self, selector: str,
                  value: Optional[str] = None,
                  label: Optional[str] = None,
                  index: Optional[int] = None,
                  page_index: Optional[int] = None,
                  url_contains: Optional[str] = None,
                  timeout: int = 5000) -> SkillResult:
        """
        在弹窗中选择下拉框选项

        Args:
            selector: CSS 选择器
            value: 选项的 value 属性值
            label: 选项的显示文本
            index: 选项的索引（从 0 开始）
            page_index: 目标页面索引
            url_contains: 目标页面URL包含的字符串
            timeout: 超时时间（毫秒）
        """
        # 先切换到目标页面
        if page_index is not None or url_contains is not None:
            switch_result = await SwitchToPopupSkill(
                self.browser_context, page=self._page, manager=self.manager
            ).run(page_index=page_index, url_contains=url_contains)
            if not switch_result.success:
                return switch_result

        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout,
                                                   retries=3, backoff=0.5, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Select element not found in popup: {selector}"
                )

            # 尝试原生 select
            try:
                if value:
                    await element.select_option(value=value)
                elif label:
                    await element.select_option(label=label)
                elif index is not None:
                    await element.select_option(index=index)
                else:
                    return SkillResult(
                        success=False,
                        message="Must provide value, label, or index for select"
                    )
                return SkillResult(
                    success=True,
                    message=f"Selected option in popup: {selector}",
                    data={"selector": selector, "page_url": page.url}
                )
            except Exception:
                # 如果不是原生 select，尝试点击方式
                return SkillResult(
                    success=False,
                    message=f"Failed to select in popup, element may not be a native select: {selector}",
                    error="Not a native select element"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to select in popup: {str(e)}",
                error=str(e)
            )


class GetTextInPopupSkill(BaseSkill):
    """获取弹窗中的文本"""

    name = "get_text_in_popup"
    description = "获取弹窗/指定页面中的元素文本"

    async def run(self, selector: str,
                  page_index: Optional[int] = None,
                  url_contains: Optional[str] = None,
                  timeout: int = 5000) -> SkillResult:
        """
        获取弹窗中的元素文本

        Args:
            selector: CSS 选择器
            page_index: 目标页面索引
            url_contains: 目标页面URL包含的字符串
            timeout: 超时时间（毫秒）
        """
        # 先切换到目标页面
        if page_index is not None or url_contains is not None:
            switch_result = await SwitchToPopupSkill(
                self.browser_context, page=self._page, manager=self.manager
            ).run(page_index=page_index, url_contains=url_contains)
            if not switch_result.success:
                return switch_result

        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout,
                                                   retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found in popup: {selector}"
                )

            text = await element.inner_text()
            return SkillResult(
                success=True,
                message=f"Got text from popup element: {selector}",
                data={"selector": selector, "text": text, "page_url": page.url}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to get text in popup: {str(e)}",
                error=str(e)
            )


class ClosePopupSkill(BaseSkill):
    """关闭弹窗/标签页"""

    name = "close_popup"
    description = "关闭弹窗/指定标签页"

    async def run(self, page_index: Optional[int] = None,
                  url_contains: Optional[str] = None) -> SkillResult:
        """
        关闭弹窗/标签页

        Args:
            page_index: 要关闭的页面索引
            url_contains: 要关闭的页面URL包含的字符串
        """
        pages = self.browser_context.pages

        if len(pages) <= 1:
            return SkillResult(
                success=False,
                message="Cannot close the last page"
            )

        target_page = None

        if page_index is not None:
            if page_index < 0 or page_index >= len(pages):
                return SkillResult(
                    success=False,
                    message=f"Invalid page index: {page_index}"
                )
            target_page = pages[page_index]
        elif url_contains:
            for page in pages:
                if url_contains.lower() in page.url.lower():
                    target_page = page
                    break
            if target_page is None:
                return SkillResult(
                    success=False,
                    message=f"No page found with URL containing: {url_contains}"
                )
        else:
            # 关闭当前页面（除了第一个页面）
            current = await self.get_page()
            if current != pages[0]:
                target_page = current
            else:
                target_page = pages[-1]

        await target_page.close()

        # 更新当前页面引用
        if self.browser_context.pages:
            self.set_page(self.browser_context.pages[0])

        return SkillResult(
            success=True,
            message="Popup/page closed",
            data={"page_count": len(self.browser_context.pages)}
        )


class HandleIframeSkill(BaseSkill):
    """处理 iframe 内容"""

    name = "handle_iframe"
    description = "获取并操作 iframe 中的内容"

    async def run(self, selector: str,
                  action: str = "get_content",
                  inner_selector: Optional[str] = None,
                  value: Optional[str] = None,
                  timeout: int = 5000) -> SkillResult:
        """
        处理 iframe 内容

        Args:
            selector: iframe 的 CSS 选择器
            action: 操作类型，可选 "get_content", "click", "fill", "get_text"
            inner_selector: iframe 内部元素的选择器
            value: 填写的值（仅 fill 操作需要）
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            # 等待 iframe 出现
            frame_element = await self.wait_for_selector(selector, timeout=timeout,
                                                         retries=3, backoff=0.5, state="attached")
            if frame_element is None:
                return SkillResult(
                    success=False,
                    message=f"iframe not found: {selector}"
                )

            # 获取 iframe 的 frame 对象
            frame = await frame_element.content_frame()
            if frame is None:
                return SkillResult(
                    success=False,
                    message="Could not access iframe content"
                )

            if action == "get_content":
                content = await frame.content()
                return SkillResult(
                    success=True,
                    message="Got iframe content",
                    data={"content": content[:5000]}  # 限制返回长度
                )
            elif action == "click":
                if inner_selector is None:
                    return SkillResult(
                        success=False,
                        message="inner_selector required for click action"
                    )
                element = await frame.wait_for_selector(inner_selector, timeout=timeout, state="visible")
                if element is None:
                    return SkillResult(
                        success=False,
                        message=f"Element not found in iframe: {inner_selector}"
                    )
                await element.click()
                return SkillResult(
                    success=True,
                    message=f"Clicked element in iframe: {inner_selector}",
                    data={"selector": inner_selector}
                )
            elif action == "fill":
                if inner_selector is None or value is None:
                    return SkillResult(
                        success=False,
                        message="inner_selector and value required for fill action"
                    )
                element = await frame.wait_for_selector(inner_selector, timeout=timeout, state="visible")
                if element is None:
                    return SkillResult(
                        success=False,
                        message=f"Element not found in iframe: {inner_selector}"
                    )
                await element.fill(value)
                return SkillResult(
                    success=True,
                    message=f"Filled element in iframe: {inner_selector}",
                    data={"selector": inner_selector, "value": value}
                )
            elif action == "get_text":
                if inner_selector is None:
                    return SkillResult(
                        success=False,
                        message="inner_selector required for get_text action"
                    )
                element = await frame.wait_for_selector(inner_selector, timeout=timeout, state="attached")
                if element is None:
                    return SkillResult(
                        success=False,
                        message=f"Element not found in iframe: {inner_selector}"
                    )
                text = await element.inner_text()
                return SkillResult(
                    success=True,
                    message=f"Got text from iframe element: {inner_selector}",
                    data={"selector": inner_selector, "text": text}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Unknown action: {action}. Supported: get_content, click, fill, get_text"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to handle iframe: {str(e)}",
                error=str(e)
            )


class ClickAndWaitForPopupSkill(BaseSkill):
    """点击元素并等待弹窗出现"""

    name = "click_and_wait_popup"
    description = "点击元素并等待弹窗出现（适用于点击后打开新窗口的场景）"

    async def run(self, selector: str,
                  url_contains: Optional[str] = None,
                  title_contains: Optional[str] = None,
                  timeout: int = 10000) -> SkillResult:
        """
        点击元素并等待弹窗出现

        Args:
            selector: 要点击的元素选择器
            url_contains: 弹窗URL包含的字符串
            title_contains: 弹窗标题包含的字符串
            timeout: 等待超时（毫秒）
        """
        page = await self.get_page()
        initial_page_count = len(self.browser_context.pages)

        try:
            # 设置监听新页面事件
            async with page.context.expect_page(timeout=timeout) as page_info:
                # 点击元素
                element = await self.wait_for_selector(selector, timeout=timeout,
                                                       retries=3, backoff=0.5, state="visible")
                if element is None:
                    return SkillResult(
                        success=False,
                        message=f"Element not found: {selector}"
                    )
                await element.click()

            # 获取新页面
            new_page = await page_info.value

            # 等待页面加载
            try:
                await new_page.wait_for_load_state("load", timeout=timeout)
            except Exception:
                pass  # 忽略加载状态错误

            # 检查是否匹配条件
            match = True
            if url_contains:
                match = match and (url_contains.lower() in new_page.url.lower())
            if title_contains and match:
                try:
                    page_title = await new_page.title()
                    match = match and (title_contains.lower() in page_title.lower())
                except Exception:
                    pass

            if match:
                self.set_page(new_page)
                return SkillResult(
                    success=True,
                    message=f"Popup opened after clicking: {selector}",
                    data={
                        "url": new_page.url,
                        "title": await new_page.title(),
                        "page_count": len(self.browser_context.pages)
                    }
                )
            else:
                return SkillResult(
                    success=False,
                    message="Popup opened but did not match expected criteria",
                    data={"url": new_page.url}
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to click and wait for popup: {str(e)}",
                error=str(e)
            )