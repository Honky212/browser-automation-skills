"""Browser-Automation-Skills - 自动化测试 Skills 框架"""

__version__ = "1.5.4"
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

    # 默认重试配置：全局可覆盖
    manager._retry_settings = {
        "max_attempts": 3,
        "backoff": 1.0,
        "retry_on": ["timeout", "timed out", "not found", "failed to", "timeout waiting"]
    }

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