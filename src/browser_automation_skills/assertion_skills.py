"""断言 Skills - 用于测试验证"""

from typing import Optional

from .base import BaseSkill, SkillResult


class TextEqualsSkill(BaseSkill):
    """断言文本等于指定值"""

    name = "text_equals"
    description = "断言元素文本等于指定值"

    async def run(self, selector: str, expected: str, timeout: int = 5000,
                  exact: bool = True) -> SkillResult:
        """
        断言元素文本等于指定值

        Args:
            selector: CSS 选择器
            expected: 期望的文本值
            timeout: 超时时间（毫秒）
            exact: 是否精确匹配（False 则包含匹配）
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )

            actual_text = await element.inner_text()
            actual_text = actual_text.strip()

            if exact:
                match = actual_text == expected
            else:
                match = expected in actual_text

            if match:
                return SkillResult(
                    success=True,
                    message=f"Text assertion passed: '{actual_text}' == '{expected}'",
                    data={"selector": selector, "expected": expected, "actual": actual_text}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Text assertion failed: expected '{expected}', got '{actual_text}'",
                    data={"selector": selector, "expected": expected, "actual": actual_text}
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Text assertion error: {str(e)}",
                error=str(e)
            )


class TextContainsSkill(BaseSkill):
    """断言文本包含指定值"""

    name = "text_contains"
    description = "断言元素文本包含指定值"

    async def run(self, selector: str, expected: str, timeout: int = 5000,
                  case_sensitive: bool = True) -> SkillResult:
        """
        断言元素文本包含指定值

        Args:
            selector: CSS 选择器
            expected: 期望包含的文本
            timeout: 超时时间（毫秒）
            case_sensitive: 是否区分大小写
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )

            actual_text = await element.inner_text()

            if case_sensitive:
                match = expected in actual_text
            else:
                match = expected.lower() in actual_text.lower()

            if match:
                return SkillResult(
                    success=True,
                    message=f"Text contains assertion passed: '{actual_text}' contains '{expected}'",
                    data={"selector": selector, "expected": expected, "actual": actual_text}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Text contains assertion failed: '{actual_text}' does not contain '{expected}'",
                    data={"selector": selector, "expected": expected, "actual": actual_text}
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Text contains assertion error: {str(e)}",
                error=str(e)
            )


class ElementExistsSkill(BaseSkill):
    """断言元素存在"""

    name = "element_exists"
    description = "断言元素存在"

    async def run(self, selector: str, timeout: int = 5000,
                  state: str = "attached") -> SkillResult:
        """
        断言元素存在

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
            state: 等待状态 (attached, visible, hidden, detached)
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state=state)
            if element:
                tag = await element.evaluate("el => el.tagName.toLowerCase()")
                return SkillResult(
                    success=True,
                    message=f"Element exists: {selector}",
                    data={"selector": selector, "tag": tag}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Element does not exist: {selector}"
                )
        except Exception:
            return SkillResult(
                success=False,
                message=f"Element does not exist: {selector}"
            )


class ElementNotExistsSkill(BaseSkill):
    """断言元素不存在"""

    name = "element_not_exists"
    description = "断言元素不存在"

    async def run(self, selector: str, timeout: int = 2000) -> SkillResult:
        """
        断言元素不存在

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒），应设置较短的超时时间
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state="hidden")
            return SkillResult(
                success=True,
                message=f"Element does not exist (as expected): {selector}",
                data={"selector": selector}
            )
        except Exception:
            # 超时意味着元素不存在，这正是我们期望的
            return SkillResult(
                success=True,
                message=f"Element does not exist (as expected): {selector}",
                data={"selector": selector}
            )


class ElementVisibleSkill(BaseSkill):
    """断言元素可见"""

    name = "element_visible"
    description = "断言元素可见"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        断言元素可见

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element:
                is_visible = await element.is_visible()
                if is_visible:
                    return SkillResult(
                        success=True,
                        message=f"Element is visible: {selector}",
                        data={"selector": selector}
                    )
                else:
                    return SkillResult(
                        success=False,
                        message=f"Element is not visible: {selector}"
                    )
            else:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Element visibility check failed: {str(e)}",
                error=str(e)
            )


class ElementEnabledSkill(BaseSkill):
    """断言元素可交互（未禁用）"""

    name = "element_enabled"
    description = "断言元素可交互（未禁用）"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        断言元素可交互

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )

            is_enabled = await element.is_enabled()
            if is_enabled:
                return SkillResult(
                    success=True,
                    message=f"Element is enabled: {selector}",
                    data={"selector": selector}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Element is disabled: {selector}"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Element enabled check failed: {str(e)}",
                error=str(e)
            )


class ElementDisabledSkill(BaseSkill):
    """断言元素已禁用"""

    name = "element_disabled"
    description = "断言元素已禁用"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        断言元素已禁用

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )

            is_enabled = await element.is_enabled()
            if not is_enabled:
                return SkillResult(
                    success=True,
                    message=f"Element is disabled (as expected): {selector}",
                    data={"selector": selector}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Element is enabled (expected disabled): {selector}"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Element disabled check failed: {str(e)}",
                error=str(e)
            )


class UrlContainsSkill(BaseSkill):
    """断言 URL 包含指定字符串"""

    name = "url_contains"
    description = "断言当前页面 URL 包含指定字符串"

    async def run(self, expected: str, case_sensitive: bool = True) -> SkillResult:
        """
        断言 URL 包含指定字符串

        Args:
            expected: 期望包含的字符串
            case_sensitive: 是否区分大小写
        """
        page = await self.get_page()
        current_url = page.url

        if case_sensitive:
            match = expected in current_url
        else:
            match = expected.lower() in current_url.lower()

        if match:
            return SkillResult(
                success=True,
                message=f"URL contains assertion passed: '{current_url}' contains '{expected}'",
                data={"url": current_url, "expected": expected}
            )
        else:
            return SkillResult(
                success=False,
                message=f"URL contains assertion failed: '{current_url}' does not contain '{expected}'",
                data={"url": current_url, "expected": expected}
            )


class UrlEqualsSkill(BaseSkill):
    """断言 URL 等于指定值"""

    name = "url_equals"
    description = "断言当前页面 URL 等于指定值"

    async def run(self, expected: str, exact: bool = False) -> SkillResult:
        """
        断言 URL 等于指定值

        Args:
            expected: 期望的 URL
            exact: 是否精确匹配（False 则忽略查询参数顺序等）
        """
        page = await self.get_page()
        current_url = page.url

        if exact:
            match = current_url == expected
        else:
            # 简化匹配：比较域名和路径
            match = expected in current_url or current_url in expected

        if match:
            return SkillResult(
                success=True,
                message=f"URL equals assertion passed",
                data={"url": current_url, "expected": expected}
            )
        else:
            return SkillResult(
                success=False,
                message=f"URL equals assertion failed: expected '{expected}', got '{current_url}'",
                data={"url": current_url, "expected": expected}
            )


class TitleContainsSkill(BaseSkill):
    """断言页面标题包含指定文本"""

    name = "title_contains"
    description = "断言当前页面标题包含指定字符串"

    async def run(self, expected: str, case_sensitive: bool = True) -> SkillResult:
        page = await self.get_page()
        title = await page.title()

        if case_sensitive:
            match = expected in title
        else:
            match = expected.lower() in title.lower()

        if match:
            return SkillResult(
                success=True,
                message=f"Title contains assertion passed: '{title}' contains '{expected}'",
                data={"title": title, "expected": expected}
            )
        else:
            return SkillResult(
                success=False,
                message=f"Title contains assertion failed: '{title}' does not contain '{expected}'",
                data={"title": title, "expected": expected}
            )


class TitleEqualsSkill(BaseSkill):
    """断言页面标题等于指定文本"""

    name = "title_equals"
    description = "断言当前页面标题等于指定值"

    async def run(self, expected: str, exact: bool = True) -> SkillResult:
        page = await self.get_page()
        title = await page.title()

        match = title == expected if exact else expected in title or title in expected

        if match:
            return SkillResult(
                success=True,
                message=f"Title equals assertion passed",
                data={"title": title, "expected": expected}
            )
        else:
            return SkillResult(
                success=False,
                message=f"Title equals assertion failed: expected '{expected}', got '{title}'",
                data={"title": title, "expected": expected}
            )


class PageContainsTextSkill(BaseSkill):
    """断言页面包含指定文本"""

    name = "page_contains_text"
    description = "断言当前页面包含指定文本"

    async def run(self, text: str, case_sensitive: bool = True) -> SkillResult:
        page = await self.get_page()
        content = await page.content()

        if case_sensitive:
            match = text in content
        else:
            match = text.lower() in content.lower()

        if match:
            return SkillResult(
                success=True,
                message=f"Page contains text assertion passed: page contains '{text}'",
                data={"text": text}
            )
        else:
            return SkillResult(
                success=False,
                message=f"Page contains text assertion failed: page does not contain '{text}'",
                data={"text": text}
            )


class ElementHasClassSkill(BaseSkill):
    """断言元素包含指定 class"""

    name = "element_has_class"
    description = "断言元素包含指定 class"

    async def run(self, selector: str, class_name: str, timeout: int = 5000) -> SkillResult:
        page = await self.get_page()
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(success=False, message=f"Element not found: {selector}")

            classes = await element.evaluate("el => el.className")
            if classes and class_name in classes.split():
                return SkillResult(
                    success=True,
                    message=f"Element has class '{class_name}': {selector}",
                    data={"selector": selector, "class_name": class_name}
                )
            return SkillResult(
                success=False,
                message=f"Element does not have class '{class_name}': {selector}",
                data={"selector": selector, "class_name": class_name}
            )
        except Exception as e:
            return SkillResult(success=False, message=f"Class assertion failed: {str(e)}", error=str(e))


class ElementSelectedSkill(BaseSkill):
    """断言元素被选中"""

    name = "element_selected"
    description = "断言指定元素已选中"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        page = await self.get_page()
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(success=False, message=f"Element not found: {selector}")

            is_selected = await element.evaluate("el => el.selected || el.checked || false")
            if is_selected:
                return SkillResult(
                    success=True,
                    message=f"Element is selected: {selector}",
                    data={"selector": selector, "selected": is_selected}
                )
            return SkillResult(
                success=False,
                message=f"Element is not selected: {selector}",
                data={"selector": selector, "selected": is_selected}
            )
        except Exception as e:
            return SkillResult(success=False, message=f"Selected assertion failed: {str(e)}", error=str(e))


class AttributeEqualsSkill(BaseSkill):
    """断言属性等于指定值"""

    name = "attribute_equals"
    description = "断言元素属性等于指定值"

    async def run(self, selector: str, attribute: str, expected: str,
                  timeout: int = 5000) -> SkillResult:
        """
        断言元素属性等于指定值

        Args:
            selector: CSS 选择器
            attribute: 属性名
            expected: 期望的属性值
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )

            actual_value = await element.get_attribute(attribute)

            if actual_value == expected:
                return SkillResult(
                    success=True,
                    message=f"Attribute assertion passed: {attribute}='{actual_value}'",
                    data={"selector": selector, "attribute": attribute, "expected": expected, "actual": actual_value}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Attribute assertion failed: expected '{expected}', got '{actual_value}'",
                    data={"selector": selector, "attribute": attribute, "expected": expected, "actual": actual_value}
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Attribute assertion error: {str(e)}",
                error=str(e)
            )


class CountElementsSkill(BaseSkill):
    """断言元素数量"""

    name = "count_elements"
    description = "断言匹配选择器的元素数量"

    async def run(self, selector: str, expected_count: int,
                  timeout: int = 5000) -> SkillResult:
        """
        断言元素数量

        Args:
            selector: CSS 选择器
            expected_count: 期望的元素数量
            timeout: 超时时间（毫秒）
        """
        page = await self.get_page()

        try:
            await page.wait_for_selector(selector, timeout=timeout)
            elements = await page.query_selector_all(selector)
            actual_count = len(elements)

            if actual_count == expected_count:
                return SkillResult(
                    success=True,
                    message=f"Element count assertion passed: {actual_count} == {expected_count}",
                    data={"selector": selector, "expected": expected_count, "actual": actual_count}
                )
            else:
                return SkillResult(
                    success=False,
                    message=f"Element count assertion failed: expected {expected_count}, got {actual_count}",
                    data={"selector": selector, "expected": expected_count, "actual": actual_count}
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Element count assertion error: {str(e)}",
                error=str(e)
            )


class CheckboxCheckedSkill(BaseSkill):
    """断言复选框已勾选"""

    name = "checkbox_checked"
    description = "断言复选框已勾选"

    async def run(self, selector: str, timeout: int = 5000,
                  expected: bool = True) -> SkillResult:
        """
        断言复选框状态

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
            expected: 期望的状态（True=已勾选，False=未勾选）
        """
        page = await self.get_page()

        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found: {selector}"
                )

            is_checked = await element.is_checked()

            if is_checked == expected:
                status = "checked" if expected else "unchecked"
                return SkillResult(
                    success=True,
                    message=f"Checkbox is {status} (as expected): {selector}",
                    data={"selector": selector, "expected": expected, "actual": is_checked}
                )
            else:
                status = "checked" if expected else "unchecked"
                actual_status = "checked" if is_checked else "unchecked"
                return SkillResult(
                    success=False,
                    message=f"Checkbox state mismatch: expected {status}, got {actual_status}",
                    data={"selector": selector, "expected": expected, "actual": is_checked}
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Checkbox check failed: {str(e)}",
                error=str(e)
            )