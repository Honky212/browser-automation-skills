"""测试 SkillResult 数据类和 BaseSkill 基类"""

import asyncio
import pytest
from unittest.mock import MagicMock

from browser_automation_skills.base import BaseSkill, SkillResult


class TestSkillResult:
    """SkillResult 数据类测试"""

    def test_success_result_str(self):
        """测试成功结果的字符串表示"""
        result = SkillResult(success=True, message="Done", execution_time=1.5)
        assert "[SUCCESS]" in str(result)
        assert "Done" in str(result)
        assert "1.50s" in str(result)

    def test_failed_result_str(self):
        """测试失败结果的字符串表示"""
        result = SkillResult(success=False, message="Failed", execution_time=0.5)
        assert "[FAILED]" in str(result)
        assert "Failed" in str(result)

    def test_default_values(self):
        """测试默认值"""
        result = SkillResult(success=True, message="ok")
        assert result.data is None
        assert result.error is None
        assert result.screenshot is None
        assert result.execution_time == 0.0

    def test_assert_success_passes(self):
        """测试 assert_success 在成功时不抛异常"""
        result = SkillResult(success=True, message="ok")
        result.assert_success()  # 不应抛异常

    def test_assert_success_raises(self):
        """测试 assert_success 在失败时抛 AssertionError"""
        result = SkillResult(success=False, message="fail", error="some error")
        with pytest.raises(AssertionError, match="Skill failed"):
            result.assert_success()


class TestBaseSkillExecute:
    """BaseSkill.execute 重试逻辑测试"""

    def test_execute_success_no_retry(self, mock_browser_context, mock_page):
        """测试成功执行不重试"""

        class DummySkill(BaseSkill):
            name = "dummy"
            description = "dummy skill"
            call_count = 0

            async def run(self, **kwargs):
                DummySkill.call_count += 1
                return SkillResult(success=True, message="ok")

        skill = DummySkill(mock_browser_context, page=mock_page)
        result = asyncio.get_event_loop().run_until_complete(skill.execute())

        assert result.success is True
        assert DummySkill.call_count == 1

    def test_execute_retry_on_timeout(self, mock_browser_context, mock_page):
        """测试超时错误时重试"""

        class FlakySkill(BaseSkill):
            name = "flaky"
            description = "flaky skill"
            call_count = 0

            async def run(self, **kwargs):
                FlakySkill.call_count += 1
                if FlakySkill.call_count < 3:
                    return SkillResult(
                        success=False, message="timeout waiting for element", error="timeout"
                    )
                return SkillResult(success=True, message="ok on retry")

        skill = FlakySkill(mock_browser_context, page=mock_page)
        # 模拟 manager 提供重试配置
        mock_manager = MagicMock()
        mock_manager._retry_settings = {"max_attempts": 3, "backoff": 0, "retry_on": ["timeout"]}
        mock_manager.current_page = mock_page
        mock_manager.set_current_page = MagicMock()
        skill.manager = mock_manager
        skill._retry_settings = mock_manager._retry_settings

        result = asyncio.get_event_loop().run_until_complete(skill.execute())

        assert result.success is True
        assert FlakySkill.call_count == 3

    def test_execute_no_retry_on_unmatched_error(self, mock_browser_context, mock_page):
        """测试非匹配错误不重试"""

        class FailSkill(BaseSkill):
            name = "fail"
            description = "fail skill"
            call_count = 0

            async def run(self, **kwargs):
                FailSkill.call_count += 1
                return SkillResult(success=False, message="element has wrong text", error="wrong text")

        skill = FailSkill(mock_browser_context, page=mock_page)
        mock_manager = MagicMock()
        mock_manager._retry_settings = {"max_attempts": 3, "backoff": 0, "retry_on": ["timeout"]}
        skill.manager = mock_manager
        skill._retry_settings = mock_manager._retry_settings

        result = asyncio.get_event_loop().run_until_complete(skill.execute())

        assert result.success is False
        assert FailSkill.call_count == 1  # 不匹配 retry_on，不重试
