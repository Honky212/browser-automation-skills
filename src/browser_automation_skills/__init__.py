"""Browser-Automation-Skills - 自动化测试 Skills 框架"""

__version__ = "1.6.0"
from .base import BaseSkill, SkillResult
from .manager import SkillManager
from .reporter import TestReporter
from .screenshot_manager import ScreenshotManager

# 浏览器操作 Skills
from .browser_skills import (
    NavigateSkill,
    ClickSkill,
    ScreenshotSkill,
    WaitForElementSkill,
    GetTextSkill,
    GetAttributeSkill,
    GetPageInfoSkill,
    GetCurrentPageInfoSkill,
    ExecuteJSSkill,
    GetHTMLSkill,
    ScrollIntoViewSkill,
    ScrollToSkill,
    FocusSkill,
    BlurSkill,
    DoubleClickSkill,
    RightClickSkill,
    WaitSkill,
    ReloadSkill,
    GoBackSkill,
    GoForwardSkill,
    # 多标签页管理 Skills
    OpenNewTabSkill,
    CloseTabSkill,
    SwitchTabSkill,
    GetTabsSkill,
    CloseOtherTabsSkill,
)

# 表单操作 Skills
from .form_skills import (
    FillInputSkill,
    TypeTextSkill,
    SelectOptionSkill,
    CheckCheckboxSkill,
    UncheckCheckboxSkill,
    UploadFileSkill,
    FillFormSkill,
    SubmitFormSkill,
    ClearInputSkill,
    HoverSkill,
    PressKeySkill,
    SetDateSkill,
)

# 断言 Skills
from .assertion_skills import (
    TextEqualsSkill,
    TextContainsSkill,
    ElementExistsSkill,
    ElementNotExistsSkill,
    ElementVisibleSkill,
    ElementEnabledSkill,
    ElementDisabledSkill,
    UrlContainsSkill,
    UrlEqualsSkill,
    TitleContainsSkill,
    TitleEqualsSkill,
    PageContainsTextSkill,
    ElementHasClassSkill,
    ElementSelectedSkill,
    AttributeEqualsSkill,
    CountElementsSkill,
    CheckboxCheckedSkill,
)

# 弹窗处理 Skills
from .popup_skills import (
    GetPopupPagesSkill,
    SwitchToPopupSkill,
    WaitForPopupSkill,
    ClickInPopupSkill,
    FillInPopupSkill,
    SelectInPopupSkill,
    GetTextInPopupSkill,
    ClosePopupSkill,
    HandleIframeSkill,
    ClickAndWaitForPopupSkill,
)

# DOM 索引化 Skills (Phase 1 - P0)
from .dom_snapshot import (
    GetDomSnapshotSkill,
    ClickByIndexSkill,
    FillByIndexSkill,
)

# Agent Skills (Phase 2 - P1)
from .agent import (
    ExecuteTaskSkill,
    ExecuteBatchTestCasesSkill,
    BatchTestAgent,
    TestCaseParser,
)

# Vision Skills (Phase 3 - P1)
from .vision import (
    ScreenshotVisionSkill,
    AnalyzePageSkill,
)

# Performance Skills (Phase 6 - P2)
from .performance import (
    GetCacheStatsSkill,
    ClearCacheSkill,
)

__all__ = [
    # Core
    "BaseSkill",
    "SkillResult",
    "SkillManager",
    # Browser Skills
    "NavigateSkill",
    "ClickSkill",
    "ScreenshotSkill",
    "WaitForElementSkill",
    "GetTextSkill",
    "GetAttributeSkill",
    "GetPageInfoSkill",
    "GetCurrentPageInfoSkill",
    "WaitSkill",
    "ReloadSkill",
    "GoBackSkill",
    "GoForwardSkill",
    # Tab Management Skills
    "OpenNewTabSkill",
    "CloseTabSkill",
    "SwitchTabSkill",
    "GetTabsSkill",
    "CloseOtherTabsSkill",
    # Form Skills
    "FillInputSkill",
    "TypeTextSkill",
    "SelectOptionSkill",
    "CheckCheckboxSkill",
    "UncheckCheckboxSkill",
    "UploadFileSkill",
    "FillFormSkill",
    "SubmitFormSkill",
    "ClearInputSkill",
    "HoverSkill",
    "PressKeySkill",
    "SetDateSkill",
    # Assertion Skills
    "TextEqualsSkill",
    "TextContainsSkill",
    "ElementExistsSkill",
    "ElementNotExistsSkill",
    "ElementVisibleSkill",
    "ElementEnabledSkill",
    "ElementDisabledSkill",
    "UrlContainsSkill",
    "UrlEqualsSkill",
    "TitleContainsSkill",
    "TitleEqualsSkill",
    "PageContainsTextSkill",
    "ElementHasClassSkill",
    "ElementSelectedSkill",
    "AttributeEqualsSkill",
    "CountElementsSkill",
    "CheckboxCheckedSkill",
    # Popup Skills
    "GetPopupPagesSkill",
    "SwitchToPopupSkill",
    "WaitForPopupSkill",
    "ClickInPopupSkill",
    "FillInPopupSkill",
    "SelectInPopupSkill",
    "GetTextInPopupSkill",
    "ClosePopupSkill",
    "HandleIframeSkill",
    "ClickAndWaitForPopupSkill",
    # DOM Index Skills (Phase 1 - P0)
    "GetDomSnapshotSkill",
    "ClickByIndexSkill",
    "FillByIndexSkill",
    # Agent Skills (Phase 2 - P1)
    "ExecuteTaskSkill",
    "ExecuteBatchTestCasesSkill",
    # Vision Skills (Phase 3 - P1)
    "ScreenshotVisionSkill",
    "AnalyzePageSkill",
    # Performance Skills (Phase 6 - P2)
    "GetCacheStatsSkill",
    "ClearCacheSkill",
    # Agent Skills (Batch)
    "BatchTestAgent",
    "TestCaseParser",
]


def create_manager(browser_context=None, config=None) -> SkillManager:
    """
    创建并预配置的 Skill Manager 实例

    Args:
        browser_context: Playwright BrowserContext 实例
        config: 配置字典（可选，包含 vision、agent 等配置）

    Returns:
        SkillManager: 已注册所有内置 Skills 的 Manager
    """
    manager = SkillManager(browser_context=browser_context, config=config)

    # 技能级重试 + 超时预算（可通过 config.yaml 的 skill_retry / skill_timeout 段覆盖）
    #
    # 背景：技能级重试与 wait_for_selector 内部重试是**相乘**关系
    # （3 × 3 × 单次 timeout），一个不存在的元素会白等近 1 分钟。
    # 这里把两者都降下来，并给选择器等待加总预算，避免长时间空转。
    cfg = config or {}
    retry_cfg = cfg.get("skill_retry", {}) or {}
    timeout_cfg = cfg.get("skill_timeout", {}) or {}

    manager._retry_settings = {
        "max_attempts": int(retry_cfg.get("max_attempts", 2)),
        "backoff": float(retry_cfg.get("backoff", 0.5)),
        "retry_on": list(
            retry_cfg.get("retry_on")
            or ["timeout", "timed out", "not found", "failed to", "timeout waiting"]
        ),
    }
    manager._timeout_settings = {
        # 单个技能单次执行的硬超时（秒），<=0 表示不限制
        "skill_timeout": float(timeout_cfg.get("per_skill_seconds", 30)),
        # 单个选择器等待的总预算（秒），<=0 表示不限制
        "selector_wait_budget": float(timeout_cfg.get("selector_wait_budget_seconds", 6.0)),
        # 单次 wait_for_selector 的超时（毫秒）
        "selector_timeout_ms": int(timeout_cfg.get("selector_timeout_ms", 3000)),
        # 豁免硬超时/整段重跑的复合技能（批量执行、Agent 执行、视觉分析等）
        "exempt_skills": list(
            timeout_cfg.get("exempt_skills") or BaseSkill.DEFAULT_TIMEOUT_EXEMPT_SKILLS
        ),
    }

    # 技能策略：allow | audit | deny（audit 表示“允许但记录”，如 execute_js 这类 UI 降级手段）
    manager.set_skill_policy(cfg.get("skill_policy"))

    # 注册所有内置 Skills
    all_skills = [
        # Browser Skills
        NavigateSkill,
        ClickSkill,
        ScreenshotSkill,
        WaitForElementSkill,
        GetTextSkill,
        GetAttributeSkill,
        GetPageInfoSkill,
        GetCurrentPageInfoSkill,
        ExecuteJSSkill,
        GetHTMLSkill,
        ScrollIntoViewSkill,
        ScrollToSkill,
        FocusSkill,
        BlurSkill,
        DoubleClickSkill,
        RightClickSkill,
        WaitSkill,
        ReloadSkill,
        GoBackSkill,
        GoForwardSkill,
        # Tab Management Skills
        OpenNewTabSkill,
        CloseTabSkill,
        SwitchTabSkill,
        GetTabsSkill,
        CloseOtherTabsSkill,
        # Form Skills
        FillInputSkill,
        TypeTextSkill,
        SelectOptionSkill,
        CheckCheckboxSkill,
        UncheckCheckboxSkill,
        UploadFileSkill,
        FillFormSkill,
        SubmitFormSkill,
        ClearInputSkill,
        HoverSkill,
        PressKeySkill,
        SetDateSkill,
        # Assertion Skills
        TextEqualsSkill,
        TextContainsSkill,
        ElementExistsSkill,
        ElementNotExistsSkill,
        ElementVisibleSkill,
        ElementEnabledSkill,
        ElementDisabledSkill,
        UrlContainsSkill,
        UrlEqualsSkill,
        TitleContainsSkill,
        TitleEqualsSkill,
        PageContainsTextSkill,
        ElementHasClassSkill,
        ElementSelectedSkill,
        AttributeEqualsSkill,
        CountElementsSkill,
        CheckboxCheckedSkill,
        # Popup Skills
        GetPopupPagesSkill,
        SwitchToPopupSkill,
        WaitForPopupSkill,
        ClickInPopupSkill,
        FillInPopupSkill,
        SelectInPopupSkill,
        GetTextInPopupSkill,
        ClosePopupSkill,
        HandleIframeSkill,
        ClickAndWaitForPopupSkill,
        # DOM Index Skills (Phase 1 - P0)
        GetDomSnapshotSkill,
        ClickByIndexSkill,
        FillByIndexSkill,
        # Agent Skills (Phase 2 - P1)
        ExecuteTaskSkill,
        ExecuteBatchTestCasesSkill,
        # Vision Skills (Phase 3 - P1)
        ScreenshotVisionSkill,
        AnalyzePageSkill,
        # Performance Skills (Phase 6 - P2)
        GetCacheStatsSkill,
        ClearCacheSkill,
    ]

    for skill_class in all_skills:
        manager.register(skill_class)

    return manager


def create_enhanced_manager(browser_context=None, config=None, llm_client=None) -> "SkillManager":
    """
    创建增强版 Skill Manager 实例（包含所有新 Skills）

    Args:
        browser_context: Playwright BrowserContext 实例
        config: 配置字典（可选，包含 vision、agent 等配置）
        llm_client: LLM 客户端实例（可选，传入后注入 config 供 Agent Skills 使用）

    Returns:
        SkillManager: 已注册所有内置 Skills 的 Manager
    """
    # 如果传入了 llm_client，注入到 config 中供 Agent Skills 使用
    if llm_client is not None:
        config = dict(config) if config else {}
        config["llm_client"] = llm_client

    # create_manager 已注册所有内置 Skills（含 DOM 索引化 Skills），无需重复注册
    manager = create_manager(browser_context, config=config)

    return manager