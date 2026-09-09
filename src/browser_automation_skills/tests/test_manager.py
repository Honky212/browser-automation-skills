"""测试 SkillManager 注册、别名解析、链式执行"""

import asyncio
import pytest

from browser_automation_skills.base import BaseSkill, SkillResult
from browser_automation_skills.manager import SkillManager


class TestSkillRegistration:
    """Skill 注册测试"""

    def test_register_single_skill(self, mock_browser_context):
        """测试注册单个 Skill"""

        class DummySkill(BaseSkill):
            name = "dummy_test"
            description = "test skill"
            async def run(self, **kwargs):
                return SkillResult(success=True, message="ok")

        manager = SkillManager(browser_context=mock_browser_context)
        manager.register(DummySkill)

        assert "dummy_test" in manager
        assert len(manager) == 1

    def test_register_with_alias(self, mock_browser_context):
        """测试注册带别名的 Skill"""

        class DummySkill(BaseSkill):
            name = "dummy_aliased"
            description = "test skill"
            async def run(self, **kwargs):
                return SkillResult(success=True, message="ok")

        manager = SkillManager(browser_context=mock_browser_context)
        manager.register(DummySkill, aliases=["dummy_alias", "da"])

        assert "dummy_aliased" in manager
        assert "dummy_alias" in manager  # 别名也可查找
        assert "da" in manager

    def test_list_skills(self, skill_manager):
        """测试列出所有已注册 Skills"""
        skills = skill_manager.list_skills()
        assert len(skills) > 0
        # 检查关键 skills 已注册
        skill_names = [s["name"] for s in skills]
        assert "navigate" in skill_names
        assert "click" in skill_names
        assert "screenshot" in skill_names
        assert "execute_task" in skill_names

    def test_list_skill_names_includes_aliases(self, mock_browser_context):
        """测试 list_skill_names 包含别名"""

        class DummySkill(BaseSkill):
            name = "dummy_names"
            description = "test"
            async def run(self, **kwargs):
                return SkillResult(success=True, message="ok")

        manager = SkillManager(browser_context=mock_browser_context)
        manager.register(DummySkill, aliases=["dn"])
        names = manager.list_skill_names()
        assert "dummy_names" in names
        assert "dn" in names


class TestSkillExecution:
    """Skill 执行测试"""

    def test_execute_skill_not_found(self, skill_manager):
        """测试执行不存在的 Skill"""
        result = asyncio.get_event_loop().run_until_complete(
            skill_manager.execute("nonexistent_skill")
        )
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_execute_skill_success(self, skill_manager, mock_page):
        """测试成功执行 Skill"""
        # navigate skill 的 mock 设置已在 conftest 中
        mock_page.goto.return_value = None  # response = None → 失败路径

        result = asyncio.get_event_loop().run_until_complete(
            skill_manager.execute("wait", seconds=0.01)
        )
        assert result.success is True

    def test_execute_chain(self, skill_manager, mock_page):
        """测试链式执行"""
        mock_page.goto.return_value = None

        chain = [
            {"skill": "wait", "params": {"seconds": 0.01}},
            {"skill": "wait", "params": {"seconds": 0.01}},
        ]
        results = asyncio.get_event_loop().run_until_complete(
            skill_manager.execute_chain(chain)
        )
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_execute_chain_stop_on_failure(self, skill_manager):
        """测试链式执行遇失败停止"""
        chain = [
            {"skill": "nonexistent", "params": {}},  # 第一步就失败
            {"skill": "wait", "params": {"seconds": 0.01}},
        ]
        results = asyncio.get_event_loop().run_until_complete(
            skill_manager.execute_chain(chain, stop_on_failure=True)
        )
        assert len(results) == 1  # 第一步失败，不执行第二步
        assert results[0].success is False

    def test_execute_chain_no_stop_on_failure(self, skill_manager, mock_page):
        """测试链式执行遇失败不停止"""
        chain = [
            {"skill": "nonexistent", "params": {}},
            {"skill": "wait", "params": {"seconds": 0.01}},
        ]
        results = asyncio.get_event_loop().run_until_complete(
            skill_manager.execute_chain(chain, stop_on_failure=False)
        )
        assert len(results) == 2  # 两步都执行了

    def test_execute_chain_missing_skill_key(self, skill_manager):
        """测试链式执行中缺少 skill 键"""
        chain = [{"params": {}}]  # 缺少 skill 键
        results = asyncio.get_event_loop().run_until_complete(
            skill_manager.execute_chain(chain)
        )
        assert len(results) == 1
        assert results[0].success is False
        assert "Missing" in results[0].message
