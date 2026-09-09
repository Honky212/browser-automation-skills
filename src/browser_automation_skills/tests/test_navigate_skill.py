"""测试 NavigateSkill 状态码判断（对应问题 #3 修复）"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from browser_automation_skills.browser_skills import NavigateSkill
from browser_automation_skills.base import SkillResult


class TestNavigateSkillStatusCodes:
    """测试不同 HTTP 状态码的导航结果"""

    def _setup_skill(self, mock_browser_context, mock_page, response):
        skill = NavigateSkill(mock_browser_context, page=mock_page)
        mock_page.goto.return_value = response
        return skill

    def test_2xx_success(self, mock_browser_context, mock_page, mock_response_ok):
        """2xx 应标记为成功"""
        skill = self._setup_skill(mock_browser_context, mock_page, mock_response_ok)
        result = asyncio.get_event_loop().run_until_complete(
            skill.run(url="https://example.com")
        )
        assert result.success is True
        assert result.data["status"] == 200

    def test_404_failure(self, mock_browser_context, mock_page, mock_response_404):
        """404 应标记为失败"""
        skill = self._setup_skill(mock_browser_context, mock_page, mock_response_404)
        result = asyncio.get_event_loop().run_until_complete(
            skill.run(url="https://example.com/notfound")
        )
        assert result.success is False
        assert result.error == "HTTP 404"
        assert result.data["status"] == 404  # 仍然返回页面信息

    def test_500_failure(self, mock_browser_context, mock_page, mock_response_500):
        """500 应标记为失败"""
        skill = self._setup_skill(mock_browser_context, mock_page, mock_response_500)
        result = asyncio.get_event_loop().run_until_complete(
            skill.run(url="https://example.com/error")
        )
        assert result.success is False
        assert result.error == "HTTP 500"

    def test_none_response_failure(self, mock_browser_context, mock_page, mock_response_none):
        """无响应应标记为失败"""
        skill = self._setup_skill(mock_browser_context, mock_page, mock_response_none)
        result = asyncio.get_event_loop().run_until_complete(
            skill.run(url="https://example.com")
        )
        assert result.success is False
        assert "no response" in result.message.lower()

    def test_3xx_redirect_success(self, mock_browser_context, mock_page):
        """3xx 重定向应标记为成功"""
        resp = MagicMock()
        resp.ok = False
        resp.status = 302
        skill = self._setup_skill(mock_browser_context, mock_page, resp)
        result = asyncio.get_event_loop().run_until_complete(
            skill.run(url="https://example.com/redirect")
        )
        assert result.success is True
        assert "redirect" in result.message.lower()

    def test_error_page_still_returns_data(self, mock_browser_context, mock_page, mock_response_404):
        """失败时仍应返回页面信息供排查"""
        skill = self._setup_skill(mock_browser_context, mock_page, mock_response_404)
        result = asyncio.get_event_loop().run_until_complete(
            skill.run(url="https://example.com/notfound")
        )
        assert result.data is not None
        assert "url" in result.data
        assert "status" in result.data
        assert "title" in result.data
