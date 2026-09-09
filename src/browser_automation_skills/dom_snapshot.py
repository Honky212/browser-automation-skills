"""DOM 索引化模块 - 提供页面 DOM 快照和索引化操作 Skills"""

from dataclasses import dataclass, field
from typing import Optional, List
import time

from playwright.async_api import Page, ElementHandle

from .base import BaseSkill, SkillResult


@dataclass
class ElementInfo:
    """单个可交互元素的信息"""
    index: int                          # 索引（从 1 开始）
    tag: str                            # 元素标签 (button, input, a, etc.)
    text: str                           # 可见文本
    placeholder: str                    # 占位符（input 专用）
    value: str                          # 当前值（input 专用）
    element_id: str                     # 元素 id 属性
    name: str                           # 元素 name 属性
    classes: List[str]                  # CSS class 列表
    aria_label: str                     # 无障碍标签
    role: str                           # ARIA role
    is_visible: bool                    # 是否可见
    is_enabled: bool                    # 是否可交互
    selector: str                       # 稳定 CSS Selector（自动生成）
    skill_id: str                       # 注入的 data-skill-id 属性值


@dataclass
class DOMSnapshot:
    """页面 DOM 快照"""
    url: str
    title: str
    elements: List[ElementInfo] = field(default_factory=list)
    timestamp: float = 0.0

    def to_readable_text(self, max_elements: int = 100) -> str:
        """转换为 LLM 可读的文本格式"""
        lines = [
            f"页面: {self.url}",
            f"标题: {self.title}",
            f"元素列表 (共 {len(self.elements)} 个):",
            ""
        ]
        for el in self.elements[:max_elements]:
            if not el.is_visible:
                continue
            desc = self._describe_element(el)
            lines.append(f"  [{el.index}] {desc}")
        return "\n".join(lines)

    def _describe_element(self, el: "ElementInfo") -> str:
        """生成元素描述文本"""
        parts = [el.tag.capitalize()]
        if el.text:
            parts.append(f'"{el.text}"')
        if el.placeholder:
            parts.append(f'placeholder="{el.placeholder}"')
        if el.element_id:
            parts.append(f'id="{el.element_id}"')
        if el.aria_label:
            parts.append(f'aria-label="{el.aria_label}"')
        if el.role:
            parts.append(f'role="{el.role}"')
        return " ".join(parts)

    def get_element_by_index(self, index: int) -> Optional["ElementInfo"]:
        """通过索引获取元素信息"""
        for el in self.elements:
            if el.index == index:
                return el
        return None


class DomSnapshotService:
    """DOM 快照服务 - 负责捕获和解析页面元素"""

    # 可交互元素的选择器
    INTERACTIVE_SELECTORS = (
        'a[href], button:not([disabled]), '
        'input:not([type="hidden"]):not([disabled]), '
        'select:not([disabled]), textarea:not([disabled]), '
        '[role="button"], [role="link"], [role="tab"], '
        '[role="checkbox"], [role="radio"], '
        '[tabindex]:not([tabindex="-1"])'
    )

    async def capture(self, page: Page) -> DOMSnapshot:
        """
        捕获页面 DOM 快照

        步骤：
        1. 注入 data-skill-id 到所有可交互元素
        2. 收集元素信息和稳定属性
        3. 生成唯一 selector
        """
        # 1. 注入 skill-id
        await self._inject_skill_ids(page)

        # 2. 收集元素信息
        elements_js = await page.evaluate(self._COLLECT_ELEMENTS_JS)

        # 3. 构建快照
        timestamp = await page.evaluate("() => Date.now() / 1000")
        snapshot = DOMSnapshot(
            url=page.url,
            title=await page.title(),
            timestamp=timestamp,
        )

        for i, el_data in enumerate(elements_js, 1):
            el_info = ElementInfo(
                index=i,
                tag=el_data.get("tag", ""),
                text=el_data.get("text", ""),
                placeholder=el_data.get("placeholder", ""),
                value=el_data.get("value", ""),
                element_id=el_data.get("id", ""),
                name=el_data.get("name", ""),
                classes=el_data.get("classes", []),
                aria_label=el_data.get("ariaLabel", ""),
                role=el_data.get("role", ""),
                is_visible=el_data.get("visible", True),
                is_enabled=el_data.get("enabled", True),
                selector=el_data.get("selector", ""),
                skill_id=el_data.get("skillId", ""),
            )
            snapshot.elements.append(el_info)

        return snapshot

    async def _inject_skill_ids(self, page: Page):
        """为所有可交互元素注入唯一的 data-skill-id"""
        await page.evaluate("""
        () => {
            const selectors = document.querySelectorAll(
                'a[href], button, input:not([type="hidden"]), select, textarea, ' +
                '[role="button"], [role="link"], [role="tab"], ' +
                '[role="checkbox"], [role="radio"], [tabindex]:not([tabindex="-1"])'
            );
            selectors.forEach((el, i) => {
                el.setAttribute('data-skill-id', 'skill-' + i);
            });
        }
        """)

    async def get_element_by_skill_id(self, page: Page, skill_id: str) -> Optional[ElementHandle]:
        """通过 skill-id 获取元素句柄"""
        return await page.query_selector(f'[data-skill-id="{skill_id}"]')

    async def get_element_by_index(self, page: Page, index: int) -> Optional[ElementHandle]:
        """通过索引获取元素句柄（先获取快照，再通过 skill-id 定位）"""
        snapshot = await self.capture(page)
        el_info = snapshot.get_element_by_index(index)
        if el_info:
            return await self.get_element_by_skill_id(page, el_info.skill_id)
        return None

    # JavaScript 代码：收集元素信息
    _COLLECT_ELEMENTS_JS = """
    () => {
        const elements = document.querySelectorAll(
            'a[href], button, input:not([type="hidden"]), select, textarea, ' +
            '[role="button"], [role="link"], [role="tab"], ' +
            '[role="checkbox"], [role="radio"], [tabindex]:not([tabindex="-1"])'
        );
        const results = [];
        elements.forEach((el) => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return; // 跳过不可见元素

            const tag = el.tagName.toLowerCase();
            let text = el.innerText?.trim() || '';
            if (!text && (tag === 'input' || tag === 'textarea')) {
                text = el.value || '';
            }

            // 生成稳定 selector
            let selector = '';
            if (el.id) {
                selector = '#' + CSS.escape(el.id);
            } else if (el.name) {
                selector = tag + '[name="' + el.name + '"]';
            } else {
                // 使用 class + 标签
                const classes = Array.from(el.classList).filter(c => !c.startsWith('css-')).slice(0, 2);
                selector = tag + (classes.length > 0 ? '.' + classes.join('.') : '');
            }

            results.push({
                tag: tag,
                text: text,
                placeholder: el.placeholder || '',
                value: el.value || '',
                id: el.id || '',
                name: el.name || '',
                classes: Array.from(el.classList),
                ariaLabel: el.getAttribute('aria-label') || '',
                role: el.getAttribute('role') || '',
                visible: rect.width > 0 && rect.height > 0,
                enabled: !el.disabled && el.getAttribute('aria-disabled') !== 'true',
                selector: selector,
                skillId: el.getAttribute('data-skill-id') || ''
            });
        });
        return results;
    }
    """


class GetDomSnapshotSkill(BaseSkill):
    """获取当前页面 DOM 快照"""

    name = "get_dom_snapshot"
    description = "获取当前页面可交互元素的索引列表，返回结构化数据供 LLM 理解页面"

    async def run(self, readable: bool = True, max_elements: int = 100, use_cache: bool = True) -> SkillResult:
        page = await self.get_page()
        
        # 尝试从缓存获取
        if use_cache and hasattr(self.manager, '_dom_cache'):
            cached = await self.manager._dom_cache.get(page, max_elements)
            if cached is not None:
                return SkillResult(
                    success=True,
                    message=f"DOM snapshot from cache: {cached['element_count']} elements",
                    data=cached,
                )
        
        # 缓存未命中，重新捕获
        service = DomSnapshotService()
        snapshot = await service.capture(page)

        result_data = {
            "url": snapshot.url,
            "title": snapshot.title,
            "element_count": len(snapshot.elements),
        }
        
        if readable:
            result_data["readable"] = snapshot.to_readable_text(max_elements)
        else:
            result_data["elements"] = [
                {
                    "index": el.index,
                    "tag": el.tag,
                    "text": el.text,
                    "placeholder": el.placeholder,
                    "selector": el.selector,
                    "skill_id": el.skill_id,
                }
                for el in snapshot.elements
            ]

        # 存入缓存
        if use_cache and hasattr(self.manager, '_dom_cache'):
            await self.manager._dom_cache.set(page, result_data, max_elements)

        return SkillResult(
            success=True,
            message=f"DOM snapshot captured: {len(snapshot.elements)} elements",
            data=result_data,
        )


class ClickByIndexSkill(BaseSkill):
    """通过 DOM 索引点击元素"""

    name = "click_by_index"
    description = "通过 DOM 索引（index）点击页面上的可交互元素"

    async def run(self, index: int, timeout: int = 5000, use_cache: bool = True) -> SkillResult:
        page = await self.get_page()
        service = DomSnapshotService()

        # 获取快照（缓存会在 capture 时自动检查）
        snapshot = await service.capture(page)
        
        el_info = snapshot.get_element_by_index(index)

        if not el_info:
            return SkillResult(
                success=False,
                message=f"Element with index {index} not found (total: {len(snapshot.elements)} elements)"
            )

        if not el_info.is_visible:
            return SkillResult(
                success=False,
                message=f"Element [{index}] is not visible: {el_info.tag} {el_info.text}"
            )

        if not el_info.is_enabled:
            return SkillResult(
                success=False,
                message=f"Element [{index}] is disabled: {el_info.tag} {el_info.text}"
            )

        # 通过 skill-id 获取元素并点击
        element = await service.get_element_by_skill_id(page, el_info.skill_id)
        if element:
            await element.click()
            # 点击后页面可能变化，使缓存失效
            if hasattr(self.manager, '_dom_cache'):
                await self.manager._dom_cache.invalidate(page)
            return SkillResult(
                success=True,
                message=f"Clicked element [{index}]: {el_info.tag} \"{el_info.text}\"",
                data={"index": index, "element": el_info.__dict__}
            )
        else:
            return SkillResult(
                success=False,
                message=f"Element [{index}] not found in DOM (page may have changed)"
            )


class FillByIndexSkill(BaseSkill):
    """通过 DOM 索引填写输入框"""

    name = "fill_by_index"
    description = "通过 DOM 索引（index）填写页面上的输入框"

    async def run(self, index: int, value: str, timeout: int = 5000, use_cache: bool = True) -> SkillResult:
        page = await self.get_page()
        service = DomSnapshotService()

        # 获取快照（优先使用缓存）
        snapshot = await service.capture(page)
        el_info = snapshot.get_element_by_index(index)

        if not el_info:
            return SkillResult(
                success=False,
                message=f"Element with index {index} not found"
            )

        if el_info.tag not in ('input', 'textarea'):
            return SkillResult(
                success=False,
                message=f"Element [{index}] is not an input field: {el_info.tag}"
            )

        element = await service.get_element_by_skill_id(page, el_info.skill_id)
        if element:
            await element.fill(value)
            # 填写后使缓存失效
            if hasattr(self.manager, '_dom_cache'):
                await self.manager._dom_cache.invalidate(page)
            return SkillResult(
                success=True,
                message=f"Filled element [{index}] with \"{value}\"",
                data={"index": index, "value": value}
            )
        else:
            return SkillResult(
                success=False,
                message=f"Element [{index}] not found in DOM"
            )
