"""共享 pytest fixtures - 使用 mock，不依赖真实浏览器"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_automation_skills import create_manager
from browser_automation_skills.base import BaseSkill, SkillResult


@pytest.fixture
def mock_page():
    """Mock Playwright Page 对象"""
    page = AsyncMock()
    page.url = "https://example.com"
    page.title = AsyncMock(return_value="Example Page")
    page.goto = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake_screenshot_bytes")
    page.wait_for_selector = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Mock</body></html>")
    return page


@pytest.fixture
def mock_browser_context(mock_page):
    """Mock Playwright BrowserContext 对象"""
    ctx = MagicMock()
    ctx.pages = [mock_page]
    ctx.new_page = AsyncMock(return_value=mock_page)
    return ctx


@pytest.fixture
def skill_manager(mock_browser_context):
    """创建已注册所有 Skills 的 Manager（使用 mock browser_context）"""
    return create_manager(browser_context=mock_browser_context)


@pytest.fixture
def mock_response_ok():
    """Mock HTTP 200 响应"""
    resp = MagicMock()
    resp.ok = True
    resp.status = 200
    return resp


@pytest.fixture
def mock_response_404():
    """Mock HTTP 404 响应"""
    resp = MagicMock()
    resp.ok = False
    resp.status = 404
    return resp


@pytest.fixture
def mock_response_500():
    """Mock HTTP 500 响应"""
    resp = MagicMock()
    resp.ok = False
    resp.status = 500
    return resp


@pytest.fixture
def mock_response_none():
    """Mock 无响应（None）"""
    return None
