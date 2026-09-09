"""测试 BrowserAgent 防环机制（对应问题 #7 修复）"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from browser_automation_skills.agent import BrowserAgent, Plan, PlanStep, PlanStatus, AgentResult
from browser_automation_skills.base import SkillResult


class TestLoopDetection:
    """防环机制测试"""

    def _create_agent(self, skill_manager, max_repeats=3):
        """创建测试用 Agent"""
        llm_client = MagicMock()
        return BrowserAgent(
            skill_manager=skill_manager,
            llm_client=llm_client,
            max_steps=10,
            max_repeats=max_repeats,
            use_cache=False,
        )

    def test_allows_repeated_operation_within_limit(self, skill_manager, mock_page):
        """测试允许在阈值内的重复操作（如翻页）"""
        agent = self._create_agent(skill_manager, max_repeats=3)

        # 模拟 LLM 连续返回相同的 click 操作（翻页场景）
        call_count = {"plan": 0, "exec": 0}

        async def mock_plan_next_step(task, page_state, history):
            call_count["plan"] += 1
            if call_count["plan"] <= 2:
                # 连续 2 次相同操作（< max_repeats=3），应允许
                return Plan(
                    step=PlanStep(skill="click", params={"selector": ".next-page"}),
                    status=PlanStatus.CONTINUE,
                )
            return Plan(status=PlanStatus.DONE, reasoning="completed")

        async def mock_get_page_state():
            return {"url": "https://example.com", "title": "Page", "dom_snapshot": "", "dom_elements_count": 0}

        agent._plan_next_step = mock_plan_next_step
        agent._get_page_state = mock_get_page_state

        # mock execute 返回成功
        original_execute = skill_manager.execute
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        result = asyncio.get_event_loop().run_until_complete(agent.execute_task("test"))

        assert result.success is True
        assert call_count["plan"] == 3  # 2 次操作 + 1 次 done

        skill_manager.execute = original_execute

    def test_detects_loop_after_max_repeats(self, skill_manager, mock_page):
        """测试连续重复超过阈值时判定为死循环"""
        agent = self._create_agent(skill_manager, max_repeats=3)

        plan_count = {"n": 0}

        async def mock_plan_next_step(task, page_state, history):
            plan_count["n"] += 1
            # 永远返回相同操作
            return Plan(
                step=PlanStep(skill="click", params={"selector": ".stuck"}),
                status=PlanStatus.CONTINUE,
            )

        async def mock_get_page_state():
            return {"url": "https://example.com", "title": "Page", "dom_snapshot": "", "dom_elements_count": 0}

        agent._plan_next_step = mock_plan_next_step
        agent._get_page_state = mock_get_page_state

        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        result = asyncio.get_event_loop().run_until_complete(agent.execute_task("test"))

        assert result.success is False
        assert "Loop detected" in result.error
        assert "repeated" in result.error

    def test_different_operations_reset_counter(self, skill_manager, mock_page):
        """测试不同操作重置连续重复计数"""
        agent = self._create_agent(skill_manager, max_repeats=3)

        plan_count = {"n": 0}

        async def mock_plan_next_step(task, page_state, history):
            plan_count["n"] += 1
            if plan_count["n"] == 1:
                return Plan(step=PlanStep(skill="click", params={"selector": "#a"}), status=PlanStatus.CONTINUE)
            elif plan_count["n"] == 2:
                # 不同操作，应重置计数
                return Plan(step=PlanStep(skill="click", params={"selector": "#b"}), status=PlanStatus.CONTINUE)
            elif plan_count["n"] == 3:
                # 与第 2 步相同，但连续次数=1 < 3，应允许
                return Plan(step=PlanStep(skill="click", params={"selector": "#b"}), status=PlanStatus.CONTINUE)
            return Plan(status=PlanStatus.DONE, reasoning="done")

        async def mock_get_page_state():
            return {"url": "https://example.com", "title": "Page", "dom_snapshot": "", "dom_elements_count": 0}

        agent._plan_next_step = mock_plan_next_step
        agent._get_page_state = mock_get_page_state
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        result = asyncio.get_event_loop().run_until_complete(agent.execute_task("test"))

        assert result.success is True
        assert plan_count["n"] == 4  # 3 次操作 + 1 次 done

    def test_max_steps_limit(self, skill_manager, mock_page):
        """测试达到最大步数限制"""
        agent = self._create_agent(skill_manager, max_repeats=100)  # 高阈值避免触发防环

        async def mock_plan_next_step(task, page_state, history):
            return Plan(
                step=PlanStep(skill="wait", params={"seconds": 0.01}),
                status=PlanStatus.CONTINUE,
            )

        async def mock_get_page_state():
            return {"url": "https://example.com", "title": "Page", "dom_snapshot": "", "dom_elements_count": 0}

        agent._plan_next_step = mock_plan_next_step
        agent._get_page_state = mock_get_page_state
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        agent.max_steps = 3
        result = asyncio.get_event_loop().run_until_complete(agent.execute_task("test"))

        assert result.success is False
        assert "Max steps" in result.error
