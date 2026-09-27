"""稳定性与判定严谨性功能测试

覆盖本轮框架优化：
1. 参数别名归一化（text/value、text/expected 等 LLM 常见传参差异）
2. 选择器等待总预算 + 技能级硬超时（消除“3 × 3”相乘空转）
3. 断言硬门禁（无断言 / 最后一次断言失败都不允许 done）
4. 用例级超时与用例隔离
5. 报告中的断言证据
"""

import asyncio
import os
import time

import yaml

from browser_automation_skills.agent import (
    AgentResult,
    BatchTestAgent,
    BatchTestResult,
    BrowserAgent,
    Plan,
    PlanStep,
    PlanStatus,
    TestCase,
    TestCaseContext,
    TestCaseParser,
    TestCaseResult,
    is_assertion_skill,
)
from browser_automation_skills.assertion_skills import TitleContainsSkill, UrlContainsSkill
from browser_automation_skills.base import BaseSkill, SkillResult
from browser_automation_skills.dom_snapshot import FillByIndexSkill
from browser_automation_skills.manager import normalize_skill_params


# ============================================================
# 测试替身
# ============================================================

class StubManager:
    """只提供超时/重试配置的轻量 manager 替身"""

    def __init__(self, skill_timeout=30.0, wait_budget=6.0, selector_timeout_ms=3000,
                 max_attempts=1, backoff=0.0):
        self._timeout_settings = {
            "skill_timeout": skill_timeout,
            "selector_wait_budget": wait_budget,
            "selector_timeout_ms": selector_timeout_ms,
        }
        self._retry_settings = {
            "max_attempts": max_attempts, "backoff": backoff, "retry_on": ["timeout"]
        }
        self.current_page = None

    def set_current_page(self, page):
        self.current_page = page


class SelectorProbeSkill(BaseSkill):
    """调用 wait_for_selector，用于验证总等待预算"""

    name = "probe_selector"

    async def run(self, selector: str = "#missing"):
        handle = await self.wait_for_selector(selector, timeout=5000, retries=5)
        return SkillResult(success=handle is not None, message="probe done")


class SlowSkill(BaseSkill):
    """永远超时的慢技能，用于验证技能级硬超时"""

    name = "slow_skill"

    async def run(self):
        await asyncio.sleep(3)
        return SkillResult(success=True, message="slow done")


# ============================================================
# 1. 参数别名归一化
# ============================================================

class TestParamNormalization:

    def test_text_is_mapped_to_value(self):
        """fill_by_index(text=...) 应被纠正为 value"""
        params, notes = normalize_skill_params(
            "fill_by_index", FillByIndexSkill, {"index": 13, "text": "自动化测试"}
        )
        assert params["index"] == 13
        assert params["value"] == "自动化测试"
        assert "text->value" in notes

    def test_text_is_mapped_to_expected(self):
        """title_contains(text=...) 应被纠正为 expected"""
        params, notes = normalize_skill_params(
            "title_contains", TitleContainsSkill, {"text": "百度"}
        )
        assert params["expected"] == "百度"
        assert "text->expected" in notes

    def test_value_is_mapped_to_text_by_signature(self):
        """type_text(value=...) 应按签名纠正为 text"""
        params, notes = normalize_skill_params(
            "type_text", TitleContainsSkill, {"value": "百度"}
        )
        # TitleContainsSkill.run 只接受 expected，因此 value 应被纠正为 expected
        assert params["expected"] == "百度"

    def test_unknown_param_is_dropped_with_note(self):
        params, notes = normalize_skill_params(
            "url_contains", UrlContainsSkill, {"expected": "wd=", "unexpected": 1}
        )
        assert params == {"expected": "wd="}
        assert any("unexpected" in n for n in notes)

    def test_manager_execute_accepts_alias(self, skill_manager, mock_page):
        """端到端：manager.execute 用别名调用也能成功"""
        result = asyncio.run(skill_manager.execute("title_contains", text="Example"))
        assert result.success is True
        assert "Example" in result.message
        assert getattr(result, "param_notes", []) == ["text->expected"]


# ============================================================
# 2. 等待预算与硬超时
# ============================================================

class TestTimeoutBudget:

    def test_selector_wait_budget_caps_total_wait(self, mock_browser_context, mock_page):
        """选择器等待受总预算约束（旧实现会白等 3 × 5s）"""
        mock_page.wait_for_selector.side_effect = TimeoutError("timeout")
        manager = StubManager(wait_budget=0.8, selector_timeout_ms=500)
        skill = SelectorProbeSkill(mock_browser_context, page=mock_page, manager=manager)

        start = time.monotonic()
        result = asyncio.run(skill.execute())
        elapsed = time.monotonic() - start

        assert result.success is False
        assert elapsed < 2.0, f"总等待应被预算约束，实际 {elapsed:.2f}s"

    def test_retry_multiplication_is_bounded(self, mock_browser_context, mock_page):
        """技能级重试 × 选择器重试 不再相乘放大到几十秒"""
        mock_page.wait_for_selector.side_effect = TimeoutError("timeout")
        manager = StubManager(wait_budget=0.5, selector_timeout_ms=500, max_attempts=3, backoff=0.1)
        skill = SelectorProbeSkill(mock_browser_context, page=mock_page, manager=manager)

        start = time.monotonic()
        result = asyncio.run(skill.execute())
        elapsed = time.monotonic() - start

        assert result.success is False
        assert elapsed < 4.0, f"最坏应约为 max_attempts × 预算，实际 {elapsed:.2f}s"

    def test_skill_hard_timeout(self, mock_browser_context, mock_page):
        """技能级硬超时：慢技能不会拖垮整条用例"""
        manager = StubManager(skill_timeout=0.4, max_attempts=1)
        skill = SlowSkill(mock_browser_context, page=mock_page, manager=manager)

        start = time.monotonic()
        result = asyncio.run(skill.execute())
        elapsed = time.monotonic() - start

        assert result.success is False
        assert "timed out" in result.message
        assert elapsed < 2.0


# ============================================================
# 3. 断言硬门禁
# ============================================================

def _make_agent(skill_manager, require_assertion=True, gate_retries=1):
    return BrowserAgent(
        skill_manager=skill_manager,
        llm_client=object(),
        max_steps=10,
        require_assertion=require_assertion,
        assertion_gate_retries=gate_retries,
        step_timeout=5,
        llm_retries=1,
    )


def _patch_page_state(agent):
    async def mock_get_page_state():
        return {
            "url": "https://example.com",
            "title": "Page",
            "dom_snapshot": "",
            "dom_elements_count": 0,
        }

    agent._get_page_state = mock_get_page_state


class TestAssertionGate:

    def test_is_assertion_skill_helper(self):
        assert is_assertion_skill("url_contains") is True
        assert is_assertion_skill("URL_CONTAINS") is True
        assert is_assertion_skill("click_by_index") is False

    def test_gate_nudges_model_to_assert_then_passes(self, skill_manager):
        """未执行断言就想 done：门禁拦截 -> 模型补断言 -> 通过"""
        from unittest.mock import AsyncMock

        agent = _make_agent(skill_manager)
        _patch_page_state(agent)

        plans = [
            Plan(status=PlanStatus.DONE, reasoning="页面看着没问题"),
            Plan(
                step=PlanStep(skill="url_contains", params={"expected": "example"}),
                status=PlanStatus.CONTINUE,
            ),
            Plan(status=PlanStatus.DONE, reasoning="断言已通过"),
        ]
        calls = {"n": 0}

        async def mock_plan(task, page_state, history):
            plan = plans[min(calls["n"], len(plans) - 1)]
            calls["n"] += 1
            return plan

        agent._plan_next_step = mock_plan
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="assert ok"))

        result = asyncio.run(agent.execute_task("test"))

        assert result.success is True
        assert calls["n"] == 3, "门禁应多规划一次让模型补断言"
        assert len(result.assertions) == 1
        assert result.assertions[0]["skill"] == "url_contains"

    def test_gate_rejects_when_last_assertion_failed(self, skill_manager):
        """最后一次断言失败仍然 done：门禁最终判为不通过"""
        from unittest.mock import AsyncMock

        agent = _make_agent(skill_manager, gate_retries=1)
        _patch_page_state(agent)

        state = {"first": True}

        async def mock_plan(task, page_state, history):
            if state["first"]:
                state["first"] = False
                return Plan(
                    step=PlanStep(skill="url_contains", params={"expected": "wd="}),
                    status=PlanStatus.CONTINUE,
                )
            return Plan(status=PlanStatus.DONE, reasoning="我觉得可以了")

        agent._plan_next_step = mock_plan
        skill_manager.execute = AsyncMock(
            return_value=SkillResult(success=False, message="URL 不含 wd=")
        )

        result = asyncio.run(agent.execute_task("test"))

        assert result.success is False
        assert "断言门禁" in result.error
        assert result.assertions and result.assertions[-1]["success"] is False

    def test_gate_off_keeps_legacy_behaviour(self, skill_manager):
        """require_assertion=False 时保持原行为（兼容既有用法）"""
        from unittest.mock import AsyncMock

        agent = _make_agent(skill_manager, require_assertion=False)
        _patch_page_state(agent)

        async def mock_plan(task, page_state, history):
            return Plan(status=PlanStatus.DONE, reasoning="done")

        agent._plan_next_step = mock_plan
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        result = asyncio.run(agent.execute_task("test"))
        assert result.success is True


# ============================================================
# 4. 用例级超时 / 报告证据
# ============================================================

class TestBatchStability:

    def test_case_timeout_marks_failure(self, monkeypatch, skill_manager):
        agent = BatchTestAgent(
            skill_manager=skill_manager,
            llm_client=object(),
            isolate_pages=False,
            case_timeout=0.3,
        )

        async def slow_execute_task(self, task):
            await asyncio.sleep(3)
            return AgentResult(task=task, success=True)

        monkeypatch.setattr(BrowserAgent, "execute_task", slow_execute_task)

        case = TestCase(id="TC_TIME", name="超时用例", steps="1. 什么都不做", timeout=0)
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.success is False
        assert "超时" in (result.failure_reason or "")

    def test_case_timeout_uses_case_field(self, monkeypatch, skill_manager):
        """用例文件里的 timeout 优先于 agent.case_timeout"""
        agent = BatchTestAgent(
            skill_manager=skill_manager,
            llm_client=object(),
            isolate_pages=False,
            case_timeout=30,
        )

        async def slow_execute_task(self, task):
            await asyncio.sleep(3)
            return AgentResult(task=task, success=True)

        monkeypatch.setattr(BrowserAgent, "execute_task", slow_execute_task)

        case = TestCase(id="TC_TIME2", name="超时用例2", steps="1. 什么都不做", timeout=1)
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.success is False
        assert "1 秒" in (result.failure_reason or "")

    def test_report_contains_assertion_evidence(self):
        case_result = TestCaseResult(
            test_case_id="TC_01",
            test_case_name="百度首页打开测试",
            success=True,
            message="ok",
            steps_executed=[{"step": 1, "skill": "navigate"}],
            duration=3.2,
            assertions=[{
                "step": 2,
                "skill": "title_contains",
                "params": {"expected": "百度"},
                "success": True,
                "message": "Title contains assertion passed",
            }],
        )
        batch = BatchTestResult(total=1, passed=1, case_results=[case_result])

        report = batch.generate_report()

        assert "断言证据" in report
        assert "title_contains" in report
        assert "1/1" in report


# ============================================================
# 5. 复合技能超时豁免
# ============================================================

class LongRunningCompositeSkill(BaseSkill):
    """模拟复合技能（名称在默认豁免名单中），耗时超过技能级硬超时"""

    name = "analyze_page"

    async def run(self):
        await asyncio.sleep(0.6)
        return SkillResult(success=True, message="long task done")


class TestTimeoutExemption:

    def test_default_exempt_list_ignores_hard_timeout(self, mock_browser_context, mock_page):
        """复合技能（默认豁免名单）不会被技能级硬超时切断，也不会被整段重跑"""
        manager = StubManager(skill_timeout=0.2, max_attempts=2)
        skill = LongRunningCompositeSkill(mock_browser_context, page=mock_page, manager=manager)

        result = asyncio.run(skill.execute())

        assert result.success is True
        assert "long task done" in result.message

    def test_class_flag_exempts_skill(self, mock_browser_context, mock_page):
        """通过 timeout_exempt = True 标记的技能同样豁免"""
        class CustomCompositeSkill(BaseSkill):
            name = "custom_composite"
            timeout_exempt = True

            async def run(self):
                await asyncio.sleep(0.6)
                return SkillResult(success=True, message="composite ok")

        manager = StubManager(skill_timeout=0.2, max_attempts=2)
        skill = CustomCompositeSkill(mock_browser_context, page=mock_page, manager=manager)

        result = asyncio.run(skill.execute())

        assert result.success is True
        assert result.message == "composite ok"


# ============================================================
# 6. 结构化用例解析（actions / assertions）
# ============================================================

class TestStructuredCaseParsing:

    def test_normalize_step_list_forms(self):
        assert TestCaseParser._normalize_step_list("click_by_index") == [
            {"skill": "click_by_index", "params": {}}
        ]
        assert TestCaseParser._normalize_step_list('click_by_index: {"index": 6}') == [
            {"skill": "click_by_index", "params": {"index": 6}}
        ]
        assert TestCaseParser._normalize_step_list('[{"skill": "a", "params": {"x": 1}}]') == [
            {"skill": "a", "params": {"x": 1}}
        ]
        assert TestCaseParser._normalize_step_list({"skill": "a", "x": 1}) == [
            {"skill": "a", "params": {"x": 1}}
        ]
        assert TestCaseParser._normalize_step_list("a\nb") == [
            {"skill": "a", "params": {}}, {"skill": "b", "params": {}}
        ]

    def test_yaml_case_with_actions_and_assertions(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(
            "- id: T1\n"
            "  name: t\n"
            "  actions:\n"
            "    - {skill: navigate, params: {url: \"https://example.com\"}}\n"
            "  assertions:\n"
            "    - {skill: url_contains, params: {expected: example}}\n",
            encoding="utf-8",
        )
        cases = TestCaseParser.from_yaml(str(path))
        assert cases[0].actions == [{"skill": "navigate", "params": {"url": "https://example.com"}}]
        assert cases[0].assertions == [{"skill": "url_contains", "params": {"expected": "example"}}]


# ============================================================
# 7. 技能策略（allow / audit / deny）
# ============================================================

class TestSkillPolicy:

    def test_deny_blocks_skill(self, skill_manager):
        skill_manager.set_skill_policy({"execute_js": "deny"})
        result = asyncio.run(skill_manager.execute("execute_js", script="1+1"))
        assert result.success is False
        assert "skill policy" in (result.error or "")
        assert "disabled" in result.message

    def test_audit_marks_result(self, skill_manager):
        skill_manager.set_skill_policy({"execute_js": "audit"})
        result = asyncio.run(skill_manager.execute("execute_js", script="1+1"))
        assert getattr(result, "audited", False) is True

    def test_default_policy_is_allow(self, skill_manager):
        assert skill_manager.get_skill_policy("click") == "allow"
        assert "execute_js" not in skill_manager.get_skill_policy("click")


# ============================================================
# 8. 确定性的 actions 与框架断言
# ============================================================

class TestDeterministicActions:

    def test_actions_skip_llm(self, monkeypatch, skill_manager):
        """声明 actions 时完全不调用 LLM"""
        from unittest.mock import AsyncMock

        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(),
            isolate_pages=False, record_actions=False,
        )
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        called = {"llm": False}

        async def boom(self, task):
            called["llm"] = True
            raise AssertionError("LLM 不应被调用")

        monkeypatch.setattr(BrowserAgent, "execute_task", boom)

        case = TestCase(
            id="TC_DET", name="确定性用例",
            actions=[{"skill": "click_by_index", "params": {"index": 1}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert called["llm"] is False
        assert result.mode == "deterministic"
        assert result.success is True

    def test_declared_assertion_failure_fails_case(self, skill_manager):
        """框架断言失败时，即使操作全部成功，用例也判为不通过"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(),
            isolate_pages=False, record_actions=False,
        )

        async def fake_execute(skill, **params):
            ok = skill != "url_contains"
            return SkillResult(success=ok, message=f"{skill} {'ok' if ok else 'failed'}")

        skill_manager.execute = fake_execute

        case = TestCase(
            id="TC_ASSERT", name="框架断言失败",
            actions=[{"skill": "click_by_index", "params": {"index": 1}}],
            assertions=[{"skill": "url_contains", "params": {"expected": "wd="}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.success is False
        assert "框架断言失败" in (result.failure_reason or "")
        assert result.assertions and result.assertions[0]["declared"] is True
        assert result.assertions[0]["success"] is False


# ============================================================
# 9. 录制 / 回放 / 审计报告
# ============================================================

# ============================================================
# 10. 锚点语义回退（跨布局/改版）
# ============================================================

class TestAnchorFallback:

    def test_fuzzy_match_prefers_text(self):
        from types import SimpleNamespace

        from browser_automation_skills.agent import fuzzy_match_anchor

        elements = [
            SimpleNamespace(index=5, tag="input", text="", is_visible=True),
            SimpleNamespace(index=6, tag="button", text="百度一下", is_visible=True),
        ]
        assert fuzzy_match_anchor({"tag": "button", "text": "百度一下"}, elements) == 6

    def test_fuzzy_match_input_by_tag(self):
        from types import SimpleNamespace

        from browser_automation_skills.agent import fuzzy_match_anchor

        elements = [
            SimpleNamespace(index=3, tag="a", text="导航", is_visible=True),
            SimpleNamespace(index=13, tag="textarea", text="", is_visible=True),
            SimpleNamespace(index=20, tag="input", text="", is_visible=False),
        ]
        # #kw 在 AI 版首页不可见 → 回退到当前可见的输入框（textarea[13]）
        assert fuzzy_match_anchor({"element_id": "kw", "tag": "input"}, elements) == 13

    def test_fuzzy_match_ignores_invisible_elements(self):
        from types import SimpleNamespace

        from browser_automation_skills.agent import fuzzy_match_anchor

        elements = [SimpleNamespace(index=1, tag="input", text="", is_visible=False)]
        assert fuzzy_match_anchor({"tag": "input"}, elements) is None


class TestRecordingAndAudit:

    def test_record_actions_written_on_success(self, monkeypatch, tmp_path, skill_manager):
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=True, record_dir=str(tmp_path),
        )

        async def fake_execute_task(self, task):
            return AgentResult(
                task=task, success=True, final_message="ok",
                steps_executed=[
                    {"step": 1, "skill": "navigate", "params": {"url": "https://x"},
                     "success": True, "message": "ok"},
                    {"step": 2, "skill": "url_contains", "params": {"expected": "x"},
                     "success": True, "message": "ok"},
                ],
            )

        monkeypatch.setattr(BrowserAgent, "execute_task", fake_execute_task)

        case = TestCase(id="TC_REC", name="录制", steps="do it")
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.recorded_actions_path and os.path.exists(result.recorded_actions_path)
        with open(result.recorded_actions_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        # 断言类步骤不进入录制，只录制可复现的操作步骤
        assert [a["skill"] for a in data["actions"]] == ["navigate"]

    def test_replay_recorded_actions(self, tmp_path, skill_manager):
        """开启回放后，有录制文件的用例走确定性执行"""
        from unittest.mock import AsyncMock

        (tmp_path / "TC_RP.actions.yaml").write_text(
            'actions:\n  - {skill: navigate, params: {url: "https://x"}}\n',
            encoding="utf-8",
        )
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False, replay_recorded=True, record_dir=str(tmp_path),
        )
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        case = TestCase(id="TC_RP", name="回放", steps="模糊描述也没关系")
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.mode == "deterministic"
        assert result.success is True

    def test_report_includes_audit_section(self):
        case_result = TestCaseResult(
            test_case_id="TC_AUD", test_case_name="审计用例", success=True, message="ok",
            steps_executed=[{"step": 1, "skill": "execute_js", "audited": True}],
            audited_skills=["execute_js"], mode="deterministic", actions_source="replay",
        )
        report = BatchTestResult(total=1, passed=1, case_results=[case_result]).generate_report()

        assert "执行模式与审计" in report
        assert "execute_js" in report
        assert "确定性执行（来源：录制回放" in report

    def test_report_labels_llm_mode(self):
        case_result = TestCaseResult(
            test_case_id="TC_LLM", test_case_name="LLM 用例", success=True, message="ok",
            mode="llm",
        )
        report = BatchTestResult(total=1, passed=1, case_results=[case_result]).generate_report()

        assert "执行模式: LLM 规划" in report

    def test_declared_actions_take_priority_over_replay(self, tmp_path, skill_manager):
        """优先级：用例声明 actions > 录制回放 > LLM 规划"""
        from unittest.mock import AsyncMock

        (tmp_path / "TC_PRI.actions.yaml").write_text(
            'actions:\n  - {skill: navigate, params: {url: "https://replay"}}\n',
            encoding="utf-8",
        )
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False, replay_recorded=True, record_dir=str(tmp_path),
        )

        captured: Dict[str, Any] = {}

        async def fake_execute(skill, **params):
            captured.update(params)
            return SkillResult(success=True, message="ok")

        skill_manager.execute = fake_execute

        case = TestCase(
            id="TC_PRI", name="优先级", steps="x",
            actions=[{"skill": "navigate", "params": {"url": "https://declared"}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.actions_source == "case"
        assert result.mode == "deterministic"
        assert captured.get("url") == "https://declared"

    def test_record_includes_anchor(self, monkeypatch, tmp_path, skill_manager):
        """录制时写入稳定锚点（索引易漂移，锚点用于回放重解析）"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=True, record_dir=str(tmp_path),
        )

        async def fake_execute_task(self, task):
            return AgentResult(
                task=task, success=True, final_message="ok",
                steps_executed=[
                    {"step": 1, "skill": "fill_by_index", "params": {"index": 13, "value": "x"},
                     "success": True, "message": "ok",
                     "anchor": {"element_id": "kw", "tag": "input"}},
                ],
            )

        monkeypatch.setattr(BrowserAgent, "execute_task", fake_execute_task)

        case = TestCase(id="TC_ANC", name="锚点录制", steps="do it")
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        with open(result.recorded_actions_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        assert data["actions"][0]["anchor"]["element_id"] == "kw"

    def test_record_uses_normalized_params(self, monkeypatch, tmp_path, skill_manager):
        """录制时优先保存归一化后的参数，避免把模型别名写法固化到文件里"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=True, record_dir=str(tmp_path),
        )

        async def fake_execute_task(self, task):
            return AgentResult(
                task=task, success=True, final_message="ok",
                steps_executed=[
                    {"step": 1, "skill": "fill_by_index",
                     "params": {"index": 13, "text": "x"},
                     "normalized_params": {"index": 13, "value": "x"},
                     "success": True, "message": "ok"},
                ],
            )

        monkeypatch.setattr(BrowserAgent, "execute_task", fake_execute_task)

        case = TestCase(id="TC_NORM", name="归一化录制", steps="do it")
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        with open(result.recorded_actions_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        assert data["actions"][0]["params"] == {"index": 13, "value": "x"}

    def test_replay_reresolves_index_from_anchor(self, tmp_path, skill_manager, monkeypatch):
        """回放时按锚点把录制索引（13）重解析为当前索引（10）"""
        (tmp_path / "TC_RS.actions.yaml").write_text(
            "actions:\n"
            "  - skill: fill_by_index\n"
            "    params: {index: 13, value: x}\n"
            "    anchor: {element_id: kw, tag: input}\n",
            encoding="utf-8",
        )
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False, replay_recorded=True, record_dir=str(tmp_path),
        )

        async def fake_resolve(anchor, fallback_index):
            return 10

        monkeypatch.setattr(agent, "_resolve_index_from_anchor", fake_resolve)

        captured: Dict[str, Any] = {}

        async def fake_execute(skill, **params):
            captured.update(params)
            return SkillResult(success=True, message="ok")

        skill_manager.execute = fake_execute

        case = TestCase(id="TC_RS", name="锚点回放", steps="模糊描述")
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert captured.get("index") == 10
        assert result.success is True
        assert result.mode == "deterministic"


# ============================================================
# 11. 确定性失败 → 回退 LLM（fallback_to_llm_on_action_failure）
# ============================================================

class TestFallbackToLLM:

    @staticmethod
    async def _failing_execute(skill, **params):
        if skill == "url_contains":
            return SkillResult(success=True, message="assert ok")
        return SkillResult(success=False, message=f"{skill} failed")

    def test_fallback_disabled_by_default(self, monkeypatch, skill_manager):
        """默认关闭：actions 失败即失败，且不调用 LLM"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False,
        )
        skill_manager.execute = self._failing_execute

        called = {"llm": 0}

        async def fake_execute_task(self, task):
            called["llm"] += 1
            return AgentResult(task=task, success=True, final_message="llm ok")

        monkeypatch.setattr(BrowserAgent, "execute_task", fake_execute_task)

        case = TestCase(
            id="TC_FB0", name="默认不回退", steps="搜索并验证",
            actions=[{"skill": "fill_by_index", "params": {"index": 999, "value": "x"}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert called["llm"] == 0
        assert result.success is False
        assert result.mode == "deterministic"
        assert result.fallback_used is False

    def test_fallback_to_llm_on_action_failure(self, monkeypatch, skill_manager):
        """开启回退：actions 失败 → LLM 兜底执行，并标注“已回退”"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False, fallback_to_llm_on_action_failure=True,
        )
        skill_manager.execute = self._failing_execute

        seen = {"llm": 0, "prompt": ""}

        async def fake_execute_task(self, task):
            seen["llm"] += 1
            seen["prompt"] = task
            return AgentResult(
                task=task, success=True, final_message="llm ok",
                steps_executed=[
                    {"step": 1, "skill": "get_dom_snapshot", "params": {},
                     "success": True, "message": "ok"},
                    {"step": 2, "skill": "click_by_index", "params": {"index": 6},
                     "success": True, "message": "ok"},
                ],
            )

        monkeypatch.setattr(BrowserAgent, "execute_task", fake_execute_task)

        case = TestCase(
            id="TC_FB1", name="回退", steps="在百度搜索 x 并验证结果页",
            actions=[{"skill": "fill_by_index", "params": {"index": 999, "value": "x"}}],
            assertions=[{"skill": "url_contains", "params": {"expected": "wd="}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert seen["llm"] == 1
        assert "[回退说明]" in seen["prompt"]          # 回退上下文已传给模型
        assert result.success is True
        assert result.fallback_used is True
        assert result.mode == "llm"
        assert "步骤 1 失败" in result.fallback_reason
        # 两阶段步骤都保留，并标注 stage / 序号连续
        stages = [step.get("stage") for step in result.steps_executed]
        assert stages[0] == "deterministic"
        assert stages[-1] == "llm"
        assert result.steps_executed[-1]["step"] > result.steps_executed[0]["step"]
        # 框架断言仍然照常执行（判定与执行路径解耦）
        assert result.assertions and result.assertions[0]["declared"] is True

    def test_no_fallback_when_actions_succeed(self, monkeypatch, skill_manager):
        """actions 成功时不会调用 LLM，也不会标记回退"""
        from unittest.mock import AsyncMock

        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False, fallback_to_llm_on_action_failure=True,
        )
        skill_manager.execute = AsyncMock(return_value=SkillResult(success=True, message="ok"))

        called = {"llm": 0}

        async def fake_execute_task(self, task):
            called["llm"] += 1
            return AgentResult(task=task, success=True, final_message="llm ok")

        monkeypatch.setattr(BrowserAgent, "execute_task", fake_execute_task)

        case = TestCase(
            id="TC_FB2", name="成功不回退", steps="x",
            actions=[{"skill": "click_by_index", "params": {"index": 1}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert called["llm"] == 0
        assert result.fallback_used is False
        assert result.mode == "deterministic"

    def test_declared_assertions_wait_for_page_settle(self, skill_manager):
        """框架断言前会先等页面 load，规避“URL 已变、标题未更新”的竞态"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False,
        )
        wait_state = {"called": False}

        async def fake_wait_for_load_state(state, timeout=0):
            wait_state["called"] = True
            assert state == "load"

        skill_manager.current_page.wait_for_load_state = fake_wait_for_load_state

        observed = {"waited_before_assert": None}

        async def fake_execute(skill, **params):
            if skill == "url_contains":
                observed["waited_before_assert"] = wait_state["called"]
            return SkillResult(success=True, message="ok")

        skill_manager.execute = fake_execute

        case = TestCase(
            id="TC_SETTLE", name="断言前等待", steps="x",
            actions=[{"skill": "click_by_index", "params": {"index": 1}}],
            assertions=[{"skill": "url_contains", "params": {"expected": "x"}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert wait_state["called"] is True
        assert observed["waited_before_assert"] is True
        assert result.success is True

    def test_declared_assertion_retries_until_success(self, skill_manager):
        """断言有限重试：前两次失败、第三次通过 → 用例通过且记录尝试次数"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False,
        )
        agent.assertion_retry_interval_ms = 0        # 测试里不做真实等待

        calls = {"n": 0}

        async def flaky_execute(skill, **params):
            if skill == "url_contains":
                calls["n"] += 1
                return SkillResult(success=calls["n"] >= 3, message=f"attempt {calls['n']}")
            return SkillResult(success=True, message="ok")

        skill_manager.execute = flaky_execute

        case = TestCase(
            id="TC_RETRY", name="断言重试", steps="x",
            actions=[{"skill": "click_by_index", "params": {"index": 1}}],
            assertions=[{"skill": "url_contains", "params": {"expected": "wd="}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert calls["n"] == 3
        assert result.success is True
        assertion = result.assertions[0]
        assert assertion["attempts"] == 3
        assert "第 3 次尝试后通过" in assertion["message"]

    def test_declared_assertion_retry_gives_up(self, skill_manager):
        """断言有限重试：始终失败 → 用例判不通过（不会无限重试）"""
        agent = BatchTestAgent(
            skill_manager=skill_manager, llm_client=object(), isolate_pages=False,
            record_actions=False,
        )
        agent.assertion_retry_interval_ms = 0

        calls = {"n": 0}

        async def failing_execute(skill, **params):
            if skill == "url_contains":
                calls["n"] += 1
                return SkillResult(success=False, message="still failing")
            return SkillResult(success=True, message="ok")

        skill_manager.execute = failing_execute

        case = TestCase(
            id="TC_RETRY2", name="断言仍失败", steps="x",
            actions=[{"skill": "click_by_index", "params": {"index": 1}}],
            assertions=[{"skill": "url_contains", "params": {"expected": "wd="}}],
        )
        result = asyncio.run(agent._execute_single_case(TestCaseContext(test_case=case)))

        assert result.success is False
        assert calls["n"] == agent.assertion_retries
        assert "框架断言失败" in (result.failure_reason or "")

    def test_report_labels_fallback(self):
        case_result = TestCaseResult(
            test_case_id="TC_FB", test_case_name="回退用例", success=True, message="ok",
            mode="llm", actions_source="case",
            fallback_used=True, fallback_reason="步骤 1 失败: fill_by_index({\"index\": 999}) - failed",
        )
        report = BatchTestResult(total=1, passed=1, case_results=[case_result]).generate_report()

        assert "已回退 LLM 规划" in report
        assert "步骤 1 失败" in report


