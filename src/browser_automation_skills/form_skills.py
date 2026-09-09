"""表单操作 Skills"""

import os
from typing import List, Optional, Union

from .base import BaseSkill, SkillResult


class FillInputSkill(BaseSkill):
    """填写输入框"""

    name = "fill_input"
    description = "填写输入框内容"

    async def run(self, selector: str, value: str, timeout: int = 5000,
                  clear: bool = True) -> SkillResult:
        """
        填写输入框

        Args:
            selector: CSS 选择器
            value: 填写内容
            timeout: 超时时间（毫秒）
            clear: 是否先清空输入框
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )

            if clear:
                await element.fill("")

            await element.fill(value)
            return SkillResult(
                success=True,
                message=f"Filled input: {selector}",
                data={"selector": selector, "value": value}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to fill input: {str(e)}",
                error=str(e)
            )


class TypeTextSkill(BaseSkill):
    """模拟键盘输入（逐字输入）"""

    name = "type_text"
    description = "模拟键盘逐字输入"

    async def run(self, selector: str, text: str, delay: float = 50,
                  timeout: int = 5000) -> SkillResult:
        """
        模拟键盘逐字输入

        Args:
            selector: CSS 选择器
            text: 输入文本
            delay: 每个字符之间的延迟（毫秒）
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

            await element.click()
            await page.keyboard.type(text, delay=delay)
            return SkillResult(
                success=True,
                message=f"Typed text into: {selector}",
                data={"selector": selector, "text": text}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to type text: {str(e)}",
                error=str(e)
            )


class SelectOptionSkill(BaseSkill):
    """选择下拉选项（支持原生 select 和自定义下拉框）"""

    name = "select_option"
    description = "选择下拉框选项（支持原生 select、Ant Design、Element UI 等）"

    async def run(self, selector: str, value: Optional[str] = None,
                  label: Optional[str] = None, index: Optional[int] = None,
                  timeout: int = 5000) -> SkillResult:
        """
        选择下拉框选项

        策略：
        1. 优先尝试原生 <select> 的 select_option
        2. 如果失败，回退到模拟点击（点击触发器 → 等待选项列表 → 点击目标选项）

        Args:
            selector: CSS 选择器
            value: 选项的 value 属性值
            label: 选项的显示文本
            index: 选项的索引（从 0 开始）
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

            # 检查是否为原生 <select> 元素
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")

            if tag_name == "select":
                # 原生 <select>：直接使用 Playwright 的 select_option
                return await self._select_native_option(element, selector, value, label, index)
            else:
                # 非原生下拉框：使用模拟点击策略
                return await self._select_custom_option(page, element, selector, label or value, timeout)

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to select option: {str(e)}",
                error=str(e)
            )

    async def _select_native_option(self, element, selector: str, value: Optional[str],
                                    label: Optional[str], index: Optional[int]) -> SkillResult:
        """处理原生 <select> 元素"""
        if value is not None:
            await element.select_option(value=value)
        elif label is not None:
            await element.select_option(label=label)
        elif index is not None:
            await element.select_option(index=index)
        else:
            return SkillResult(
                success=False,
                message="Must provide value, label, or index"
            )

        return SkillResult(
            success=True,
            message=f"Selected option in native select: {selector}",
            data={"selector": selector, "value": value or label or index}
        )

    async def _select_custom_option(self, page, element, selector: str,
                                    option_text: Optional[str], timeout: int) -> SkillResult:
        """
        处理非原生下拉框（Ant Design、Element UI、React-Select 等）
        策略：点击触发器 → 等待选项列表 → 点击目标选项
        """
        if not option_text:
            return SkillResult(
                success=False,
                message="Custom dropdown requires 'label' parameter for option text"
            )

        # 1. 寻找触发器（可点击展开下拉框的元素）
        trigger_selectors = [
            '.select2-selection',
            '.ant-select-selector',
            '.el-select__input',
            '.el-input__inner',
            '.v-select',
            '[role="combobox"]',
            'input[readonly]',
            '.dropdown-toggle',
            '.dropdown-trigger',
        ]

        trigger = None
        for ts in trigger_selectors:
            try:
                trigger = await element.query_selector(ts)
                if trigger:
                    break
            except Exception:
                continue

        # 如果没找到触发器，就点击元素本身
        if not trigger:
            trigger = element

        # 2. 点击触发器展开下拉面板
        await trigger.click()

        # 3. 等待选项列表出现
        option_list_selectors = [
            '.select2-results',
            '.ant-select-dropdown',
            '.el-select-dropdown',
            '.v-select-menu',
            '[role="listbox"]',
            '.dropdown-menu',
            'ul[class*="options"]',
            'div[class*="dropdown"]',
            'div[class*="select"]',
        ]

        options_container = None
        for ols in option_list_selectors:
            try:
                options_container = await page.wait_for_selector(ols, timeout=timeout, state="visible")
                if options_container:
                    break
            except Exception:
                continue

        if not options_container:
            return SkillResult(
                success=False,
                message=f"Could not find dropdown options list for: {selector}"
            )

        # 4. 在容器中寻找目标选项并点击
        option_selectors = [
            '.select2-results__option',
            '.ant-select-item-option',
            '.el-select-dropdown__item',
            'li[role="option"]',
            'div[role="option"]',
            'li',
            'div[class*="option"]',
        ]

        option_el = None
        for os_sel in option_selectors:
            try:
                options = await options_container.query_selector_all(os_sel)
                for opt in options:
                    text = await opt.inner_text()
                    if text.strip() == option_text:
                        option_el = opt
                        break
                if option_el:
                    break
            except Exception:
                continue

        # 兜底：遍历所有可见子元素
        if not option_el:
            try:
                all_items = await options_container.query_selector_all('*')
                for item in all_items:
                    try:
                        text = await item.inner_text()
                        is_visible = await item.is_visible()
                        if text.strip() == option_text and is_visible:
                            option_el = item
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if not option_el:
            return SkillResult(
                success=False,
                message=f"Option '{option_text}' not found in dropdown for: {selector}"
            )

        await option_el.click()

        return SkillResult(
            success=True,
            message=f"Selected option '{option_text}' in custom dropdown: {selector}",
            data={"selector": selector, "label": option_text}
        )


class CheckCheckboxSkill(BaseSkill):
    """勾选复选框"""

    name = "check_checkbox"
    description = "勾选复选框"

    async def run(self, selector: str, timeout: int = 5000,
                  force: bool = False) -> SkillResult:
        """
        勾选复选框

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
            force: 是否强制执行
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )

            if force:
                await element.check(force=True)
            else:
                await element.check()

            return SkillResult(
                success=True,
                message=f"Checked checkbox: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to check checkbox: {str(e)}",
                error=str(e)
            )


class UncheckCheckboxSkill(BaseSkill):
    """取消勾选复选框"""

    name = "uncheck_checkbox"
    description = "取消勾选复选框"

    async def run(self, selector: str, timeout: int = 5000,
                  force: bool = False) -> SkillResult:
        """
        取消勾选复选框

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
            force: 是否强制执行
        """
        page = await self.get_page()

        try:
            element = await self.wait_for_selector(selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"Element not found after retries: {selector}"
                )

            if force:
                await element.uncheck(force=True)
            else:
                await element.uncheck()

            return SkillResult(
                success=True,
                message=f"Unchecked checkbox: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to uncheck checkbox: {str(e)}",
                error=str(e)
            )


class UploadFileSkill(BaseSkill):
    """上传文件 — 支持多种 Web 上传场景"""

    name = "upload_file"
    description = "上传文件（自动适配：原生 file input / 自定义按钮触发 / 自动发现上传按钮）"

    # 上传按钮常见文本模式（中英文）
    _UPLOAD_BUTTON_TEXTS = [
        "上传文件", "选择文件", "点击上传", "附件上传",
        "上传", "浏览", "选择", "选取文件", "添加附件",
        "文件上传", "导入文件", "批量上传",
        "Choose File", "Browse", "Upload", "Upload File",
        "Select File", "Attach File", "Add File",
    ]

    # 常见上传按钮的 CSS class 关键词
    _UPLOAD_BUTTON_CLASSES = [
        ".upload-btn", ".file-upload", ".upload-button",
        ".btn-upload", ".ant-upload", ".el-upload",
        ".upload-trigger", ".file-picker", ".file-input-trigger",
        "[class*='upload']", "[class*='file-pick']",
    ]

    async def run(
        self,
        selector: Optional[str] = None,
        file_path: Union[str, List[str]] = "",
        button_text: Optional[str] = None,
        multiple: bool = False,
        upload_trigger: str = "auto",
        timeout: int = 10000,
    ) -> SkillResult:
        """
        上传文件（增强版：支持多种 Web 上传场景）

        策略链（按 upload_trigger 决定，默认 auto 自动尝试）：
        1. selector 是 <input type="file"> → 直接 set_input_files()（绕过弹窗）
        2. selector 是自定义按钮       → 点击 → filechooser 事件注入文件
        3. button_text 指定按钮文本   → 按文本匹配按钮 → 点击 → filechooser
        4. 都未指定                  → 自动发现上传按钮/隐藏 input → 上传
        5. filechooser 失败回退      → 查找附近隐藏的 <input type="file"> → set_input_files()

        Args:
            selector:      CSS 选择器，可以是 <input type="file"> 或触发按钮（可选）
            file_path:     文件路径（字符串或列表，多文件时用列表或逗号分隔）
            button_text:   上传按钮的显示文本（用于自动匹配，如"选择文件"）
            multiple:      是否允许选择多个文件（默认 False）
            upload_trigger: 触发策略，可选 "auto"(默认) / "set_files" / "filechooser"
            timeout:       超时时间（毫秒）
        """
        page = await self.get_page()

        # ── 归一化文件路径 ──
        files = self._normalize_file_paths(file_path)
        if not files:
            return SkillResult(
                success=False,
                message="No valid file paths provided"
            )
        for fp in files:
            if not os.path.exists(fp):
                return SkillResult(
                    success=False,
                    message=f"File not found: {fp}"
                )

        strategy_used = "auto"

        try:
            # ── 策略 1：selector 明确指定，且是 <input type="file"> ──
            if selector and upload_trigger in ("auto", "set_files"):
                result = await self._try_set_input_files(page, selector, files, timeout)
                if result is not None:
                    return result

            # ── 策略 2：selector 明确指定，但可能是触发按钮 → filechooser ──
            if selector and upload_trigger in ("auto", "filechooser"):
                strategy_used = "filechooser_by_selector"
                return await self._upload_via_filechooser(
                    page, trigger_selector=selector, files=files,
                    multiple=multiple, timeout=timeout, strategy=strategy_used
                )

            # ── 策略 3：button_text 或自动发现 ──
            trigger_btn = await self._find_upload_button(page, button_text, timeout)
            if trigger_btn:
                strategy_used = f"filechooser_by_{'button_text' if button_text else 'auto_discovery'}"
                # 点击按钮并同时监听 filechooser
                try:
                    async with page.expect_file_chooser(timeout=timeout) as fc_info:
                        await trigger_btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(files if multiple else files[0])
                    strategy_used += "+filechooser"
                    return SkillResult(
                        success=True,
                        message=f"Uploaded {len(files)} file(s) via filechooser: {files}",
                        data={
                            "file_paths": files,
                            "file_count": len(files),
                            "strategy": strategy_used,
                            "button_text": button_text,
                        }
                    )
                except Exception as fc_err:
                    # filechooser 失败 → 回退：查找隐藏的 file input
                    hidden_input = await self._find_hidden_file_input(page, timeout)
                    if hidden_input:
                        await hidden_input.set_input_files(files if multiple else files[0])
                        strategy_used += "_fallback_set_files"
                        return SkillResult(
                            success=True,
                            message=f"Uploaded {len(files)} file(s) via hidden file input (fallback): {files}",
                            data={
                                "file_paths": files,
                                "file_count": len(files),
                                "strategy": strategy_used,
                            }
                        )
                    raise fc_err

            # ── 策略 4：自动发现隐藏的 file input（未指定 selector/button_text 且未找到按钮） ──
            if not selector:
                hidden_input = await self._find_hidden_file_input(page, timeout)
                if hidden_input:
                    await hidden_input.set_input_files(files if multiple else files[0])
                    strategy_used = "auto_hidden_input"
                    return SkillResult(
                        success=True,
                        message=f"Uploaded {len(files)} file(s) via auto-discovered hidden file input: {files}",
                        data={
                            "file_paths": files,
                            "file_count": len(files),
                            "strategy": strategy_used,
                        }
                    )

            return SkillResult(
                success=False,
                message="Could not find any upload element. Please provide 'selector' or 'button_text'."
            )

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to upload file: {str(e)}",
                error=str(e),
                data={"strategy": strategy_used}
            )

    # ═══════════════════════════════════════════════════════════════
    #  内部辅助方法
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _normalize_file_paths(file_path: Union[str, List[str]]) -> List[str]:
        """将 file_path 归一化为文件路径列表"""
        if isinstance(file_path, list):
            return [fp.strip() for fp in file_path if fp and isinstance(fp, str)]
        if isinstance(file_path, str):
            if "," in file_path:
                return [fp.strip() for fp in file_path.split(",") if fp.strip()]
            return [file_path.strip()] if file_path.strip() else []
        return []

    async def _try_set_input_files(self, page, selector: str, files: List[str], timeout: int):
        """尝试将 selector 视为 <input type="file"> 直接 set_input_files"""
        try:
            element = await self.wait_for_selector(
                selector, timeout=timeout, retries=2, backoff=0.3, state="attached"
            )
            if element is None:
                return None

            # 验证是否为 file input
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.evaluate("el => el.type || ''")
            if tag != "input" or input_type != "file":
                return None  # 不是 file input，交由后续策略处理

            await element.set_input_files(files if len(files) > 1 else files[0])
            return SkillResult(
                success=True,
                message=f"Uploaded {len(files)} file(s) via set_input_files: {files}",
                data={
                    "file_paths": files,
                    "file_count": len(files),
                    "strategy": "set_input_files",
                    "selector": selector,
                }
            )
        except Exception:
            return None  # 失败，交由后续策略

    async def _upload_via_filechooser(
        self, page, trigger_selector: str, files: List[str],
        multiple: bool, timeout: int, strategy: str
    ) -> SkillResult:
        """通过 filechooser 事件上传文件（点击按钮后弹出文件对话框）"""
        trigger_btn = await self.wait_for_selector(
            trigger_selector, timeout=timeout, retries=3, backoff=0.5, state="visible"
        )
        if trigger_btn is None:
            return SkillResult(
                success=False,
                message=f"Upload trigger element not found: {trigger_selector}"
            )

        try:
            async with page.expect_file_chooser(timeout=timeout) as fc_info:
                await trigger_btn.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(files if multiple else files[0])
            return SkillResult(
                success=True,
                message=f"Uploaded {len(files)} file(s) via filechooser: {files}",
                data={
                    "file_paths": files,
                    "file_count": len(files),
                    "strategy": strategy,
                    "selector": trigger_selector,
                }
            )
        except Exception as e:
            # filechooser 失败，回退到查找隐藏的 file input
            hidden_input = await self._find_hidden_file_input(page, timeout)
            if hidden_input:
                await hidden_input.set_input_files(files if multiple else files[0])
                return SkillResult(
                    success=True,
                    message=f"Uploaded {len(files)} file(s) via hidden file input (filechooser fallback): {files}",
                    data={
                        "file_paths": files,
                        "file_count": len(files),
                        "strategy": strategy + "_fallback_set_files",
                    }
                )
            return SkillResult(
                success=False,
                message=f"File upload failed: {str(e)}",
                error=str(e)
            )

    async def _find_upload_button(self, page, button_text: Optional[str], timeout: int):
        """查找上传按钮：优先 button_text 匹配，否则自动发现"""
        if button_text:
            # ── 精确匹配 ──
            button = await self._find_button_by_text(page, button_text, timeout)
            if button:
                return button

        # ── 自动发现 ──
        # 1. 按常见文本模式匹配
        for text in self._UPLOAD_BUTTON_TEXTS:
            button = await self._find_button_by_text(page, text, timeout=2000)
            if button:
                return button

        # 2. 按常见 CSS class 匹配
        for css in self._UPLOAD_BUTTON_CLASSES:
            try:
                elem = await page.query_selector(css)
                if elem and await elem.is_visible():
                    return elem
            except Exception:
                continue

        # 3. 查找 aria-label 包含 upload/file 的元素
        aria_selectors = [
            '[aria-label*="upload" i]',
            '[aria-label*="file" i]',
            '[aria-label*="上传" i]',
            '[aria-label*="选择" i]',
            '[title*="upload" i]',
            '[title*="上传" i]',
        ]
        for sel in aria_selectors:
            try:
                elem = await page.query_selector(sel)
                if elem and await elem.is_visible():
                    return elem
            except Exception:
                continue

        return None

    async def _find_button_by_text(self, page, text: str, timeout: int):
        """按显示文本查找按钮（支持 button/a/label/div/span 等）"""
        # 精确文本匹配
        selectors = [
            f'button:has-text("{text}")',
            f'a:has-text("{text}")',
            f'label:has-text("{text}")',
            f'div[role="button"]:has-text("{text}")',
            f'span:has-text("{text}")',
            f'div:has-text("{text}")',
            f'[type="button"]:has-text("{text}")',
        ]
        for sel in selectors:
            try:
                elem = await page.wait_for_selector(sel, timeout=min(timeout, 2000), state="visible")
                if elem:
                    return elem
            except Exception:
                continue
        return None

    async def _find_hidden_file_input(self, page, timeout: int):
        """查找页面上隐藏的 <input type="file">（常见的被 CSS 隐藏的上传控件）"""
        try:
            # 查找所有 file input（包括隐藏的）
            file_inputs = await page.query_selector_all('input[type="file"]')
            for fi in file_inputs:
                try:
                    # 优先选择可见的，找不到再用隐藏的
                    if await fi.is_visible():
                        return fi
                except Exception:
                    continue
            # 没有可见的，返回第一个（即使是隐藏的也可以 set_input_files）
            if file_inputs:
                return file_inputs[0]
        except Exception:
            pass
        return None


class FillFormSkill(BaseSkill):
    """批量填写表单"""

    name = "fill_form"
    description = "批量填写表单字段"

    async def run(self, fields: dict, selector_type: str = "css",
                  timeout: int = 5000) -> SkillResult:
        """
        批量填写表单

        Args:
            fields: 字段字典，格式 {选择器: 值, ...}
                   值可以是字符串（input）或列表（select 选项）
            selector_type: 选择器类型 (css, xpath)
            timeout: 每个字段的超时时间（毫秒）

        示例:
            fields = {
                "#username": "testuser",
                "#email": "test@example.com",
                "#country": "China",  # select by value
                "#agree": "checked"   # checkbox
            }
        """
        page = await self.get_page()

        results = {}
        failed = []

        for selector, value in fields.items():
            try:
                element = await self.wait_for_selector(selector, timeout=timeout, retries=2, backoff=0.3, state="attached")
                if element is None:
                    failed.append({"selector": selector, "error": "Element not found after retries"})
                    continue

                tag = await element.evaluate("el => el.tagName.toLowerCase()")
                input_type = await element.evaluate("el => el.type || 'text'")

                if tag == "select":
                    await element.select_option(value=str(value))
                    results[selector] = "selected"
                elif tag == "textarea":
                    await element.fill(str(value))
                    results[selector] = "filled"
                elif input_type == "checkbox":
                    if str(value).lower() in ("checked", "true", "1", "yes"):
                        await element.check()
                    else:
                        await element.uncheck()
                    results[selector] = "toggled"
                elif input_type == "radio":
                    await element.click()
                    results[selector] = "selected"
                elif input_type == "file":
                    if os.path.exists(str(value)):
                        await element.set_input_files(str(value))
                        results[selector] = "uploaded"
                    else:
                        failed.append({"selector": selector, "error": f"File not found: {value}"})
                else:
                    await element.fill(str(value))
                    results[selector] = "filled"

            except Exception as e:
                failed.append({"selector": selector, "error": str(e)})

        if failed:
            return SkillResult(
                success=False,
                message=f"Form partially filled. Success: {len(results)}, Failed: {len(failed)}",
                data={"success": results, "failed": failed}
            )

        return SkillResult(
            success=True,
            message=f"Form filled successfully ({len(results)} fields)",
            data={"success": results}
        )


class SubmitFormSkill(BaseSkill):
    """提交表单"""

    name = "submit_form"
    description = "提交表单（点击提交按钮或回车）"

    async def run(self, submit_selector: Optional[str] = None,
                  form_selector: Optional[str] = None,
                  wait_for: Optional[str] = None,
                  wait_for_timeout: int = 10000,
                  timeout: int = 5000) -> SkillResult:
        """
        提交表单

        Args:
            submit_selector: 提交按钮的选择器
            form_selector: 表单的选择器（用于回车提交）
            wait_for: 提交后等待出现的元素选择器
            wait_for_timeout: 等待元素的超时时间
            timeout: 操作超时时间
        """
        page = await self.get_page()

        try:
            if submit_selector:
                # 点击提交按钮（使用智能等待）
                submit_btn = await self.wait_for_selector(submit_selector, timeout=timeout, retries=3, backoff=0.5, state="visible")
                if submit_btn is None:
                    return SkillResult(
                        success=False,
                        message=f"Submit button not found after retries: {submit_selector}"
                    )
                await submit_btn.click()
            elif form_selector:
                # 在表单中回车提交（等待表单存在）
                form = await self.wait_for_selector(form_selector, timeout=timeout, retries=3, backoff=0.5, state="attached")
                if form is None:
                    return SkillResult(
                        success=False,
                        message=f"Form not found after retries: {form_selector}"
                    )
                await form.press("Enter")
            else:
                return SkillResult(
                    success=False,
                    message="Must provide submit_selector or form_selector"
                )

            # 等待目标元素出现
            if wait_for:
                try:
                    handle = await self.wait_for_selector(wait_for, timeout=wait_for_timeout, retries=3, backoff=0.5, state="attached")
                    if handle is None:
                        return SkillResult(
                            success=False,
                            message=f"Timeout waiting for element after submit: {wait_for}"
                        )
                except Exception:
                    return SkillResult(
                        success=False,
                        message=f"Timeout waiting for element after submit: {wait_for}"
                    )

            return SkillResult(
                success=True,
                message="Form submitted",
                data={"url": page.url, "title": await page.title()}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to submit form: {str(e)}",
                error=str(e)
            )


class ClearInputSkill(BaseSkill):
    """清空输入框"""

    name = "clear_input"
    description = "清空输入框内容"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        清空输入框

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

            await element.fill("")
            return SkillResult(
                success=True,
                message=f"Cleared input: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to clear input: {str(e)}",
                error=str(e)
            )


class HoverSkill(BaseSkill):
    """鼠标悬停"""

    name = "hover"
    description = "鼠标悬停在元素上"

    async def run(self, selector: str, timeout: int = 5000) -> SkillResult:
        """
        鼠标悬停

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

            await element.hover()
            return SkillResult(
                success=True,
                message=f"Hovered element: {selector}",
                data={"selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to hover: {str(e)}",
                error=str(e)
            )


class PressKeySkill(BaseSkill):
    """按键"""

    name = "press_key"
    description = "模拟按键按下"

    async def run(self, key: str, selector: Optional[str] = None) -> SkillResult:
        """
        模拟按键

        Args:
            key: 按键名称 (Enter, Tab, Escape, ArrowDown, etc.)
            selector: 目标元素选择器（可选，不指定则在当前焦点元素上按键）
        """
        page = await self.get_page()

        try:
            if selector:
                element = await page.query_selector(selector)
                if element is None:
                    return SkillResult(
                        success=False,
                        message=f"Element not found: {selector}"
                    )
                await element.press(key)
            else:
                await page.keyboard.press(key)

            return SkillResult(
                success=True,
                message=f"Pressed key: {key}",
                data={"key": key, "selector": selector}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Failed to press key: {str(e)}",
                error=str(e)
            )


class SetDateSkill(BaseSkill):
    """设置日期/时间控件的值"""

    name = "set_date"
    description = "设置日期或时间控件的值（支持原生 input、Ant Design、Element UI 等）"

    async def run(self, selector: str, value: str,
                  date_format: str = "auto", force_click: bool = False,
                  timeout: int = 5000) -> SkillResult:
        """
        在网页中自动选择或输入日期

        策略链：
        1. 优先尝试直接 fill（适用于 <input type="date">）
        2. 如果是只读输入框，移除 readonly 属性后 fill
        3. 逐字输入（press_sequentially）
        4. 最后回退到点击弹出日历面板选择

        Args:
            selector: CSS 选择器，定位日期输入框
            value: 目标日期字符串，支持 '2025-12-31', '2025/12/31', '2025年12月31日' 等
            date_format: 日期格式，可选 'yyyy-MM-dd', 'yyyy/MM/dd', 'MM/dd/yyyy','auto' 自动推断
            force_click: 是否强制通过点击日历面板来选择日期
            timeout: 超时时间（毫秒）

        Returns:
            SkillResult: 执行结果
        """
        page = await self.get_page()

        # 1. 解析日期
        date_obj = self._parse_date(value)
        if date_obj is None:
            return SkillResult(
                success=False,
                message=f"无法解析日期字符串: {value}",
                error="ParseError"
            )

        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element is None:
                return SkillResult(
                    success=False,
                    message=f"找不到可见的日期输入框: {selector}",
                    error="ElementNotFoundError"
                )

            # 2. 确定日期格式
            fmt = date_format if date_format != "auto" else await self._detect_format(element)
            formatted_date = self._format_date(date_obj, fmt)

            # 3. 执行选择策略
            is_disabled = await element.is_disabled()

            if force_click or is_disabled:
                success, msg = await self._select_via_calendar(page, element, date_obj, timeout)
            else:
                # 尝试直接输入策略链
                is_readonly = await element.evaluate("el => el.hasAttribute('readonly')")
                if is_readonly:
                    success, msg = await self._fill_by_removing_readonly(element, formatted_date)
                else:
                    success, msg = await self._safe_fill(element, formatted_date)

                if not success:
                    success, msg = await self._type_sequentially(page, element, formatted_date)

                if not success:
                    success, msg = await self._select_via_calendar(page, element, date_obj, timeout)

            if success:
                actual_val = await element.input_value() if await element.evaluate("el => el.tagName === 'INPUT'") else "N/A"
                return SkillResult(
                    success=True,
                    message=msg,
                    data={"selector": selector, "target_date": value, "actual_value": actual_val}
                )
            else:
                return SkillResult(
                    success=False,
                    message=msg,
                    error="ActionFailedError"
                )

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"设置日期失败: {str(e)}",
                error=str(e)
            )

    def _parse_date(self, date_str: str):
        """解析日期字符串"""
        import re
        from datetime import datetime

        # 清理中文
        cleaned = re.sub(r'[年月日]', '-', date_str)
        cleaned = re.sub(r'[/\.]', '-', cleaned)

        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y年%m月%d日"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # 尝试清理后的格式
        for fmt in ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y"]:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

        return None

    def _format_date(self, date, fmt: str) -> str:
        """格式化日期"""
        mapping = {
            'yyyy/MM/dd': "%Y/%m/%d",
            'MM/dd/yyyy': "%m/%d/%Y",
            'dd/MM/yyyy': "%d/%m/%Y",
            'yyyy-MM-dd': "%Y-%m-%d",
        }
        return date.strftime(mapping.get(fmt, "%Y-%m-%d"))

    async def _detect_format(self, element) -> str:
        """检测日期格式"""
        placeholder = await element.get_attribute("placeholder") or ""
        if "yyyy/MM/dd" in placeholder or "YYYY/MM/DD" in placeholder:
            return 'yyyy/MM/dd'
        if "MM/dd/yyyy" in placeholder:
            return 'MM/dd/yyyy'
        if "dd/MM/yyyy" in placeholder:
            return 'dd/MM/yyyy'
        return 'yyyy-MM-dd'

    async def _safe_fill(self, element, value: str) -> tuple:
        """安全地 fill 日期"""
        try:
            await element.fill(value)
            await element.press("Enter")
            input_val = await element.input_value()
            if self._clean_date(input_val) == self._clean_date(value):
                return True, "通过原生 fill 成功输入日期"
            return False, "原生 fill 后值未生效"
        except Exception as e:
            return False, f"原生 fill 失败: {str(e)}"

    async def _fill_by_removing_readonly(self, element, value: str) -> tuple:
        """移除 readonly 属性后 fill 日期"""
        try:
            await element.evaluate("""(el, val) => {
                el.removeAttribute('readonly');
                el.removeAttribute('disabled');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                if (setter) setter.call(el, val); else el.value = val;
            }""", value)
            await element.fill(value)
            await element.press("Enter")
            await element.dispatch_event("blur")

            input_val = await element.input_value()
            if self._clean_date(input_val) == self._clean_date(value):
                return True, "通过破除只读属性成功输入日期"
            return False, "破除只读后输入，但值未生效"
        except Exception as e:
            return False, f"破除只读输入失败: {str(e)}"

    async def _type_sequentially(self, page, element, value: str) -> tuple:
        """逐字输入日期"""
        try:
            await element.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await element.press_sequentially(value, delay=50)
            await element.press("Enter")
            return True, "通过逐字敲击成功输入日期"
        except Exception as e:
            return False, f"逐字输入失败: {str(e)}"

    async def _select_via_calendar(self, page, element, target_date, timeout: int) -> tuple:
        """通过点击日历面板选择日期"""
        try:
            await element.click()

            # 等待日历面板出现
            panel_selectors = [
                ".ant-picker-panel",
                ".el-picker-panel",
                ".MuiPickersCalendar-root",
                ".datepicker",
                "[role='dialog']",
                ".calendar-panel",
                "div[class*='calendar']",
                "div[class*='picker']",
            ]

            panel = None
            for sel in panel_selectors:
                try:
                    p = await page.wait_for_selector(sel, timeout=1000, state="visible")
                    if p:
                        panel = p
                        break
                except Exception:
                    continue

            if panel is None:
                return False, "点击输入框后未找到日历面板"

            # 翻页选择年月
            target_year = target_date.year
            next_btn = panel.locator("[class*='next'], [aria-label*='Next'], button:has-text('>')").first
            prev_btn = panel.locator("[class*='prev'], [aria-label*='Previous'], button:has-text('<')").first

            for _ in range(24):
                # 查找目标日期单元格
                day_str = str(target_date.day)
                try:
                    target_cell = panel.locator(f"text={day_str}").first
                    if await target_cell.is_visible(timeout=300):
                        await target_cell.click()
                        return True, "通过点击日历面板成功选择日期"
                except Exception:
                    pass

                # 翻页
                if target_year < target_date.year:
                    await prev_btn.click()
                else:
                    await next_btn.click()
                await page.wait_for_timeout(200)

            return False, "在日历面板中翻页 24 次仍未找到目标日期"
        except Exception as e:
            return False, f"操作日历面板时发生错误: {str(e)}"

    def _clean_date(self, date_str: str) -> str:
        """清理日期字符串用于比较"""
        import re
        return re.sub(r"[-/\.年日月]", "", date_str or "")
