"""Skill Manager - 负责 Skills 的注册、加载和执行"""

import importlib
import importlib.util
import inspect
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union
import asyncio

from .base import BaseSkill, SkillResult
from .performance import DOMSnapshotCache, LLMResponseCache, PerformanceMonitor

logger = logging.getLogger(__name__)


# ============================================================
# 参数归一化：容忍 LLM 传参命名差异（如 text/value、text/expected 混用）
# ============================================================

# canonical -> 可接受的别名
PARAM_ALIASES: Dict[str, tuple] = {
    "value": ("text", "content", "val", "input_value"),
    "text": ("value", "content", "keyword", "expected", "expected_text"),
    "expected": ("text", "value", "expected_text", "expected_value"),
    "selector": ("locator", "css", "css_selector", "xpath", "element"),
    "url": ("href", "address", "target_url"),
    "seconds": ("duration", "wait", "time", "second"),
    "path": ("file_path", "filepath", "filename", "save_path"),
    "index": ("idx", "element_index"),
}


def _accepted_params(skill_class: Type[BaseSkill]) -> Optional[set]:
    """
    解析 skill.run 的形参名集合。

    返回 None 表示该技能接受任意关键字参数（含 **kwargs），无需归一化。
    """
    try:
        signature = inspect.signature(skill_class.run)
    except (TypeError, ValueError):
        return None

    names = set()
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if param.kind in (param.VAR_KEYWORD, param.VAR_POSITIONAL):
            return None
        names.add(name)
    return names


def normalize_skill_params(
    skill_name: str,
    skill_class: Type[BaseSkill],
    kwargs: Dict[str, Any],
) -> tuple:
    """
    把调用方（通常是 LLM）传入的参数映射到技能真实签名上。

    处理顺序：
    1. 已被签名接受的原样保留；
    2. 命中别名表的做重命名（如 `text` -> `value`、`text` -> `expected`）；
    3. 仍无法识别的参数丢弃并记录，避免 TypeError 直接判整步失败。

    Returns:
        (params, notes)：归一化后的参数字典与变更说明列表
    """
    if not kwargs:
        return kwargs, []

    accepted = _accepted_params(skill_class)
    if accepted is None:
        return kwargs, []

    params: Dict[str, Any] = {}
    notes: List[str] = []
    pending = dict(kwargs)

    # 1) 先保留被接受的参数
    for key in list(pending.keys()):
        if key in accepted:
            params[key] = pending.pop(key)

    # 2) 别名映射（只映射到该技能确实接受、且尚未赋值的形参）
    for key in list(pending.keys()):
        for canonical, aliases in PARAM_ALIASES.items():
            if canonical in accepted and canonical not in params and key in aliases:
                params[canonical] = pending.pop(key)
                notes.append(f"{key}->{canonical}")
                break

    # 3) 剩余未知参数：丢弃并记录
    for key in list(pending.keys()):
        dropped = pending.pop(key)
        notes.append(f"忽略未知参数 {key}={dropped!r}")

    return params, notes


class SkillManager:
    """
    Skill 管理器

    负责：
    - 注册 Skills
    - 从模块批量加载 Skills
    - 执行单个 Skill 或 Skill 链
    """

    def __init__(self, browser_context=None, config=None):
        """
        初始化 Skill Manager

        Args:
            browser_context: Playwright BrowserContext 实例（可选，后续设置）
            config: 配置字典（可选，包含 vision、agent 等配置）
        """
        self._skills: Dict[str, Type[BaseSkill]] = {}
        self._browser_context = browser_context
        self._current_page = None
        self._skill_aliases: Dict[str, str] = {}  # 别名 -> 技能名
        self._skill_policy: Dict[str, str] = {}   # 技能名 -> allow | audit | deny
        self._lock = asyncio.Lock()
        self.config = config or {}
        
        # 性能优化组件
        cache_config = self.config.get("cache", {})
        self._dom_cache = DOMSnapshotCache(
            max_size=cache_config.get("dom_max_size", 50),
            ttl=cache_config.get("dom_ttl", 60.0),
        )
        self._llm_cache = LLMResponseCache(
            max_size=cache_config.get("llm_max_size", 200),
            ttl=cache_config.get("llm_ttl", 3600.0),
        )
        self._perf_monitor = PerformanceMonitor()

    def set_browser_context(self, browser_context):
        """设置浏览器上下文"""
        self._browser_context = browser_context
        if browser_context.pages:
            self._current_page = browser_context.pages[0]

    @property
    def browser_context(self):
        """获取浏览器上下文"""
        if self._browser_context is None:
            raise RuntimeError("Browser context not set. Call set_browser_context() first.")
        return self._browser_context

    @property
    def current_page(self):
        """获取当前页面"""
        if self._current_page is not None:
            return self._current_page
        if self.browser_context.pages:
            self._current_page = self.browser_context.pages[0]
            return self._current_page
        return None

    def set_current_page(self, page):
        """设置当前页面"""
        self._current_page = page

    def get_current_page_index(self) -> Optional[int]:
        """获取当前页在浏览器上下文中的索引"""
        current = self.current_page
        if current is None:
            return None

        for index, page in enumerate(self.browser_context.pages):
            if page == current:
                return index
        return None

    def register(self, skill_class: Type[BaseSkill], name: Optional[str] = None, aliases: Optional[List[str]] = None):
        """
        注册单个 Skill

        Args:
            skill_class: Skill 类
            name: 技能名称（默认使用类的 name 属性）
            aliases: 别名列表
        """
        skill_name = name or skill_class.name
        self._skills[skill_name] = skill_class

        # 注册别名
        if aliases:
            for alias in aliases:
                self._skill_aliases[alias] = skill_name

        logger.debug(f"Registered skill: {skill_name}")

    def register_from_module(self, module_path: Union[str, Path]):
        """
        从 Python 模块文件批量注册 Skills

        Args:
            module_path: 模块文件路径
        """
        module_path = Path(module_path)
        if not module_path.exists():
            raise FileNotFoundError(f"Module not found: {module_path}")

        spec = importlib.util.spec_from_file_location("skills_module", str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to load module spec from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        count = 0
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                    issubclass(attr, BaseSkill) and
                    attr != BaseSkill):
                self.register(attr)
                count += 1

        logger.info(f"Registered {count} skills from {module_path}")
        return count

    def register_from_package(self, package_path: Union[str, Path]):
        """
        从包目录批量注册 Skills

        Args:
            package_path: 包目录路径
        """
        package_path = Path(package_path)
        if not package_path.exists():
            raise FileNotFoundError(f"Package not found: {package_path}")

        total = 0
        for py_file in package_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                count = self.register_from_module(py_file)
                total += count
            except Exception as e:
                logger.error(f"Failed to load skills from {py_file}: {e}")

        logger.info(f"Total registered {total} skills from {package_path}")
        return total

    def _resolve_skill_name(self, name: str) -> str:
        """解析技能名称（包括别名）"""
        return self._skill_aliases.get(name, name)

    def set_skill_policy(self, policy: Optional[Dict[str, str]]) -> None:
        """
        设置技能策略：skill_name -> "allow" | "audit" | "deny"

        - allow：默认，正常执行
        - audit：允许执行，但会被标记为“已审计”（如 execute_js 这类绕过 UI 的降级手段），
                 由上层记录到报告，供人工评审
        - deny ：直接拒绝执行（返回失败结果，模型会据此改走别的路径）
        """
        cleaned: Dict[str, str] = {}
        for name, mode in (policy or {}).items():
            mode_text = str(mode).strip().lower()
            if mode_text in ("allow", "audit", "deny"):
                cleaned[str(name).strip()] = mode_text
        self._skill_policy = cleaned
        if cleaned:
            logger.info("Skill policy loaded: %s", cleaned)

    def get_skill_policy(self, skill_name: str) -> str:
        """获取技能策略（默认 allow）"""
        return self._skill_policy.get(skill_name, "allow")

    def list_skill_policies(self) -> Dict[str, str]:
        """列出已配置的技能策略"""
        return dict(self._skill_policy)

    async def _build_failure_hint(self, params: Dict[str, Any], result: SkillResult) -> Optional[str]:
        """
        元素类失败时给出“结构化提示”（候选元素清单），减少模型瞎猜索引/反复重抓快照。

        仅在失败信息命中元素相关关键字时触发；任何异常都被吞掉，不影响主流程。
        """
        message = ((result.error or "") + " " + (result.message or "")).lower()
        keywords = ("not found", "not an input", "not visible", "not attached", "detached", "disabled")
        if not any(k in message for k in keywords):
            return None

        page = self._current_page
        if page is None:
            return None

        try:
            from .dom_snapshot import DomSnapshotService

            snapshot = await DomSnapshotService().capture(page)
        except Exception:
            return None

        want_input = "input" in message or "input" in str(params.get("skill", ""))
        items: List[str] = []
        try:
            for element in snapshot.elements:
                if not element.is_visible:
                    continue
                if want_input and element.tag not in ("input", "textarea"):
                    continue
                desc = f"[{element.index}] {element.tag}"
                if element.text:
                    desc += f' "{element.text[:20]}"'
                if element.placeholder:
                    desc += f' placeholder="{element.placeholder[:20]}"'
                if element.element_id:
                    desc += f" id={element.element_id}"
                items.append(desc)
                if len(items) >= 8:
                    break
        except Exception:
            return None

        if not items:
            return None
        kind = "可输入元素" if want_input else "可交互元素"
        return f"当前页面{kind}（可用索引重试）: " + "; ".join(items)

    async def execute(self, skill_name: str, **kwargs) -> SkillResult:
        """
        执行单个 Skill

        Args:
            skill_name: 技能名称或别名
            **kwargs: 传递给 Skill 的参数

        Returns:
            SkillResult: 执行结果
        """
        resolved_name = self._resolve_skill_name(skill_name)
        logger.debug("Executing skill '%s' resolved as '%s' with args: %s", skill_name, resolved_name, kwargs)

        if resolved_name not in self._skills:
            logger.warning("Skill not found: %s (resolved: %s)", skill_name, resolved_name)
            return SkillResult(
                success=False,
                message=f"Skill not found: '{skill_name}' (resolved: '{resolved_name}'). "
                        f"Available skills: {', '.join(self.list_skill_names())}"
            )

        skill_class = self._skills[resolved_name]

        # 技能策略：deny 直接拒绝（模型据失败信息改走别的路径）
        policy = self.get_skill_policy(resolved_name)
        if policy == "deny":
            logger.warning("Skill '%s' blocked by skill policy (deny)", resolved_name)
            return SkillResult(
                success=False,
                message=(
                    f"Skill '{resolved_name}' is disabled by skill policy (deny)。"
                    f"请改用其它可用技能完成该步骤。"
                ),
                error="denied by skill policy",
            )

        # 参数归一化：把 LLM 常见的命名差异映射到技能真实签名（并丢弃未知参数）
        params, param_notes = normalize_skill_params(resolved_name, skill_class, kwargs)
        if param_notes:
            logger.info("Skill '%s' 参数归一化: %s", resolved_name, "; ".join(param_notes))

        # 性能监控
        self._perf_monitor.start_timer(f"skill.{resolved_name}")

        # 锁仅保护 current_page 的读取（临界区很小），不阻塞并发执行
        async with self._lock:
            current_page = self.current_page
            skill_instance = skill_class(self.browser_context, page=current_page, manager=self)

        # 执行 skill（不持锁，允许并发执行独立操作）
        # 注意：并发操作同一 page 时的竞态由调用者负责；
        # 不同 page 的并发是安全的；BatchOperationOptimizer 用于独立操作并发
        result = await skill_instance.execute(**params)
        if param_notes:
            # 供上层（Agent/报告）记录“发生过参数纠正”，便于观测模型传参质量
            try:
                result.param_notes = param_notes
                # 归一化后的真实参数（录制/回放时使用，避免文件里保留模型别名写法）
                result.normalized_params = params
            except Exception:
                pass

        # 执行后在锁内更新 current_page（如 OpenNewTabSkill 等会切换 page）
        if skill_instance._page is not None and skill_instance._page is not current_page:
            async with self._lock:
                self._current_page = skill_instance._page

        # audit 策略：标记为“已审计”（如 execute_js 这类绕过 UI 的降级手段），由报告披露
        if policy == "audit":
            try:
                result.audited = True
            except Exception:
                pass

        # 元素类失败：附加结构化提示（候选元素清单），帮助模型一次纠正
        if not result.success:
            try:
                hint = await self._build_failure_hint(params, result)
            except Exception:
                hint = None
            if hint:
                if not isinstance(result.data, dict):
                    result.data = {}
                result.data.setdefault("hint", hint)
                result.message = f"{result.message} | 提示: {hint}"

        # 记录性能指标
        elapsed = self._perf_monitor.end_timer(f"skill.{resolved_name}")

        if result.success:
            logger.debug("Skill '%s' executed successfully in %.3fs", resolved_name, elapsed)
        else:
            logger.warning("Skill '%s' failed: %s", resolved_name, result.message)

        return result

    async def execute_chain(self, chain: List[Dict[str, Any]],
                            stop_on_failure: bool = True) -> List[SkillResult]:
        """
        执行 Skill 链

        Args:
            chain: Skill 步骤列表，格式为 [{"skill": "name", "params": {...}}, ...]
            stop_on_failure: 失败时是否停止执行

        Returns:
            List[SkillResult]: 每步执行结果
        """
        results = []
        logger.info("Starting skill chain execution with %d steps", len(chain))
        for i, step in enumerate(chain):
            skill_name = step.get("skill")
            if not skill_name:
                result = SkillResult(
                    success=False,
                    message=f"Step {i}: Missing 'skill' key in chain step"
                )
                results.append(result)
                if stop_on_failure:
                    break
                continue

            params = step.get("params", {})
            logger.debug("Executing step %d/%d: %s with params %s", i + 1, len(chain), skill_name, params)

            result = await self.execute(skill_name, **params)
            results.append(result)

            if not result.success and stop_on_failure:
                logger.warning("Skill chain stopped at step %d: %s", i + 1, result.message)
                break

        return results

    def get_skill(self, name: str) -> Optional[Type[BaseSkill]]:
        """获取 Skill 类"""
        resolved_name = self._resolve_skill_name(name)
        return self._skills.get(resolved_name)

    def list_skills(self) -> List[Dict[str, str]]:
        """
        列出所有已注册的 Skills

        Returns:
            列表，每项包含 name 和 description
        """
        return [
            {"name": name, "description": skill.description or ""}
            for name, skill in self._skills.items()
        ]

    def list_skill_names(self) -> List[str]:
        """列出所有已注册的 Skill 名称（包括别名）"""
        names = list(self._skills.keys())
        aliases = list(self._skill_aliases.keys())
        return sorted(set(names + aliases))

    def __contains__(self, name: str) -> bool:
        """检查 Skill 是否已注册"""
        resolved = self._resolve_skill_name(name)
        return resolved in self._skills

    def __len__(self) -> int:
        """返回已注册的 Skill 数量"""
        return len(self._skills)