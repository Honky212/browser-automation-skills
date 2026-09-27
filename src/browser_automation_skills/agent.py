"""Agent 层模块 - 提供自然语言任务自动规划和执行"""

import asyncio
import json
import logging
import os
import time
import yaml
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
from pathlib import Path

from .base import BaseSkill, SkillResult
from .manager import SkillManager

logger = logging.getLogger(__name__)


# ============================================================
# 断言类技能（用于“断言硬门禁”：没有断言证据就不算通过）
# ============================================================

ASSERTION_SKILL_NAMES = frozenset({
    "text_equals",
    "text_contains",
    "element_exists",
    "element_not_exists",
    "element_visible",
    "element_enabled",
    "element_disabled",
    "url_contains",
    "url_equals",
    "title_contains",
    "title_equals",
    "page_contains_text",
    "element_has_class",
    "element_selected",
    "attribute_equals",
    "count_elements",
    "checkbox_checked",
})


def is_assertion_skill(skill_name: str) -> bool:
    """判断某个技能是否属于断言类技能。"""
    return (skill_name or "").strip().lower() in ASSERTION_SKILL_NAMES


# 锚点字段：录制/回放时用于把“易变的索引”重新解析为稳定定位
ANCHOR_FIELDS = ("element_id", "placeholder", "selector", "tag", "text", "name")


def extract_element_anchor(result_data: Any) -> Optional[Dict[str, Any]]:
    """
    从 *_by_index 技能返回的 data 中提取稳定定位锚点。

    索引（index）依赖页面元素顺序，页面重渲染/改版后会漂移；因此录制时同时记录
    id / placeholder / selector / tag+text，回放时据此重新解析索引。
    """
    if not isinstance(result_data, dict):
        return None
    element = result_data.get("element")
    if not isinstance(element, dict):
        return None
    anchor = {k: str(element.get(k)) for k in ANCHOR_FIELDS if element.get(k)}
    return anchor or None


def fuzzy_match_anchor(anchor: Dict[str, Any], elements: Any) -> Optional[int]:
    """
    锚点精确匹配失败时的“语义回退”（同一站点可能存在多套布局，例如百度首页的
    经典版 #kw/#su 与 AI 版 #chat-textarea/#chat-submit-button）。

    回退顺序：
    1. 可见元素中文本完全相等（如按钮“百度一下”）；
    2. 锚点是输入类 → 取首个可见的 input/textarea；
    3. 锚点是按钮/链接类 → 取首个可见且带文本的 button/a。

    Returns:
        匹配到的当前索引；无法判定时返回 None
    """
    try:
        visible = [element for element in elements if element.is_visible]
    except Exception:
        return None

    text = anchor.get("text")
    tag = anchor.get("tag")

    if text:
        for element in visible:
            if element.text == text:
                return element.index

    if tag in ("input", "textarea"):
        for element in visible:
            if element.tag in ("input", "textarea"):
                return element.index

    if tag in ("button", "a", "input"):
        for element in visible:
            if element.tag in ("button", "a") and element.text:
                return element.index

    return None


# ============================================================
# 数据模型
# ============================================================

class PlanStatus(str, Enum):
    """规划状态"""
    CONTINUE = "continue"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PlanStep:
    """单步规划结果"""
    skill: str                          # 要执行的 Skill 名称
    params: Dict[str, Any] = field(default_factory=dict)  # Skill 参数
    description: str = ""               # 步骤描述（用于日志）


@dataclass
class Plan:
    """规划结果"""
    step: Optional[PlanStep] = None     # 下一步操作
    status: PlanStatus = PlanStatus.CONTINUE  # 任务状态
    reasoning: str = ""                 # 选择此步骤的原因
    error: str = ""                     # 错误信息（如果失败）


@dataclass
class AgentResult:
    """Agent 执行结果"""
    task: str                           # 原始任务描述
    success: bool = False               # 是否成功
    final_message: str = ""             # 最终消息
    error: str = ""                     # 错误信息
    steps_executed: List[Dict] = field(default_factory=list)  # 已执行的步骤记录
    assertions: List[Dict[str, Any]] = field(default_factory=list)  # 已执行的断言记录（硬门禁证据）
    param_notes: List[str] = field(default_factory=list)      # 参数归一化记录（观测用）


@dataclass
class TestCase:
    """测试用例数据模型"""
    id: str
    name: str
    description: str = ""
    steps: str = ""
    expected_result: str = ""
    priority: str = "medium"
    tags: List[str] = field(default_factory=list)
    setup_url: Optional[str] = None
    timeout: int = 60
    # 确定性步骤（可选）：声明后不再依赖 LLM 规划，直接按序执行，格式
    # [{"skill": "fill_by_index", "params": {"index": 13, "value": "x"}}, ...]
    actions: List[Dict[str, Any]] = field(default_factory=list)
    # 框架强制断言（可选）：LLM/actions 执行完后由框架自己执行并决定 PASS/FAIL，
    # 格式 [{"skill": "url_contains", "params": {"expected": "wd="}}, ...]
    assertions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TestCaseContext:
    """单个测试用例执行上下文"""
    test_case: TestCase
    history: List[Dict[str, Any]] = field(default_factory=list)
    operation_history: set = field(default_factory=set)
    consecutive_failures: int = 0
    step_count: int = 0
    screenshots: List[str] = field(default_factory=list)
    error_log: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: str = "pending"
    failure_reason: str = ""


@dataclass
class TestCaseResult:
    """单个测试用例执行结果"""
    test_case_id: str
    test_case_name: str
    success: bool
    message: str
    steps_executed: List[Dict[str, Any]] = field(default_factory=list)
    failure_reason: str = ""
    duration: float = 0.0
    screenshots: List[str] = field(default_factory=list)
    assertions: List[Dict[str, Any]] = field(default_factory=list)  # 断言证据
    retry_count: int = 0                                            # 因失败自动重跑的次数
    param_notes: List[str] = field(default_factory=list)             # 参数归一化记录
    audited_skills: List[str] = field(default_factory=list)          # 命中 audit 策略的技能（如 execute_js）
    recorded_actions_path: Optional[str] = None                      # 录制动作文件路径
    mode: str = "llm"                                                # 执行模式：llm | deterministic
    actions_source: str = ""                                         # 确定性来源：case（用例声明）| replay（录制回放）
    fallback_used: bool = False                                      # 是否发生「确定性失败 → 回退 LLM 规划」
    fallback_reason: str = ""                                        # 回退原因（确定性阶段的首次失败说明）


@dataclass
class BatchTestResult:
    """批量测试结果"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    case_results: List[TestCaseResult] = field(default_factory=list)
    consecutive_failures: int = 0
    stop_reason: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total * 100

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def add_case_result(self, case_result: TestCaseResult):
        self.case_results.append(case_result)
        self.total += 1
        if case_result.success:
            self.passed += 1
            self.consecutive_failures = 0
        else:
            self.failed += 1
            self.consecutive_failures += 1

    def generate_report(self, output_path: Optional[str] = None) -> str:
        report_lines = [
            "# 批量测试报告",
            "",
            "## 概要",
            f"- 总用例数: {self.total}",
            f"- 通过: {self.passed}",
            f"- 失败: {self.failed}",
            f"- 跳过: {self.skipped}",
            f"- 通过率: {self.pass_rate:.1f}%",
            f"- 执行时长: {self.duration:.1f} 秒",
            "",
            "## 详细结果",
            "| 序号 | 用例ID | 用例名称 | 状态 | 步数 | 耗时(秒) | 断言 | 重试 | 失败原因 |",
            "|------|--------|----------|------|------|----------|------|------|----------|",
        ]

        for idx, case in enumerate(self.case_results, 1):
            status = "✅ PASS" if case.success else "❌ FAIL"
            assertions = case.assertions or []
            passed_assertions = sum(1 for a in assertions if a.get("success"))
            assertion_text = f"{passed_assertions}/{len(assertions)}" if assertions else "无"
            reason = (case.failure_reason or "-").replace("|", "\\|").replace("\n", " ")
            report_lines.append(
                f"| {idx} | {case.test_case_id} | {case.test_case_name} | {status} | "
                f"{len(case.steps_executed)} | {case.duration:.1f} | {assertion_text} | "
                f"{case.retry_count} | {reason} |"
            )

        # 断言证据：让“通过”可追溯（硬门禁开启时，无断言的用例不会 PASS）
        evidence_lines: List[str] = []
        for case in self.case_results:
            if not case.assertions:
                evidence_lines.append(f"### {case.test_case_id} {case.test_case_name}")
                evidence_lines.append("- ⚠️ 本次执行未产生断言证据")
                evidence_lines.append("")
                continue
            evidence_lines.append(f"### {case.test_case_id} {case.test_case_name}")
            for item in case.assertions:
                icon = "✅" if item.get("success") else "❌"
                params = json.dumps(item.get("params", {}), ensure_ascii=False)
                tag = "（框架断言）" if item.get("declared") else ""
                evidence_lines.append(
                    f"- {icon} 步骤 {item.get('step')} `{item.get('skill')}({params})`{tag} — "
                    f"{(item.get('message') or '').replace(chr(10), ' ')}"
                )
            evidence_lines.append("")

        if evidence_lines:
            report_lines.extend(["## 断言证据", ""] + evidence_lines)

        # 执行模式与审计：确定性执行 / 是否使用了 audit 类降级技能（如 execute_js）
        audit_lines: List[str] = []
        for case in self.case_results:
            source_label = {
                "case": "用例声明 actions",
                "replay": "录制回放",
            }.get(case.actions_source, "actions")

            if case.fallback_used:
                mode_label = (
                    f"确定性执行（来源：{source_label}）失败 → ⚠️ 已回退 LLM 规划"
                    f"（回退原因: {case.fallback_reason or '-'}）"
                )
            elif case.mode == "deterministic":
                mode_label = f"确定性执行（来源：{source_label}，不调用 LLM）"
            else:
                mode_label = "LLM 规划"
            details = [f"执行模式: {mode_label}"]
            if case.audited_skills:
                details.append(
                    f"⚠️ 使用了审计技能（绕过 UI 的降级手段）: {', '.join(case.audited_skills)}"
                )
            if case.mode == "deterministic" and not case.assertions:
                details.append("⚠️ 该用例为确定性执行但未声明框架断言（等价于“操作成功即通过”）")
            if case.recorded_actions_path:
                details.append(f"已录制动作: {case.recorded_actions_path}")
            audit_lines.append(f"- {case.test_case_id}: " + "；".join(details))

        if audit_lines:
            report_lines.extend(["## 执行模式与审计", ""] + audit_lines + [""])

        # 参数纠正记录（观测模型传参质量，不影响判定）
        note_lines: List[str] = []
        for case in self.case_results:
            if case.param_notes:
                note_lines.append(f"- {case.test_case_id}: {'; '.join(case.param_notes)}")
        if note_lines:
            report_lines.extend(["## 参数归一化记录", ""] + note_lines + [""])

        if self.stop_reason:
            report_lines.extend(["", "## 停止原因", self.stop_reason])

        report = "\n".join(report_lines)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
        return report


class TestCaseParser:
    """测试用例解析器，支持 YAML、JSON、Excel"""

    @staticmethod
    def _normalize_tags(value) -> List[str]:
        """将 tags 值统一转为 list，支持字符串分割（逗号/分号/竖线/顿号）"""
        import re
        if value is None:
            return []
        if isinstance(value, list):
            return [str(t).strip() for t in value if t]
        if isinstance(value, str):
            parts = re.split(r'[,;，；|、]', value)
            return [p.strip() for p in parts if p.strip()]
        # 其他类型转为单元素 list
        return [str(value)]

    @staticmethod
    def _normalize_step_list(value) -> List[Dict[str, Any]]:
        """
        把 actions / assertions 统一成 [{"skill": str, "params": dict}, ...]

        支持的写法（YAML/JSON/Excel 通用）：
        - dict:  {"skill": "click_by_index", "params": {"index": 6}}
        - dict 扁平: {"skill": "click_by_index", "index": 6}
        - str:   "click_by_index"  或  "click_by_index: {\"index\": 6}"
        """
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            # Excel / JSON 单元格里可能是 JSON 数组或对象
            if text.startswith("[") or text.startswith("{"):
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
                if isinstance(parsed, (list, dict)):
                    return TestCaseParser._normalize_step_list(parsed)
            # 或多行文本，每行一个步骤
            if "\n" in text:
                return TestCaseParser._normalize_step_list(
                    [line for line in text.splitlines() if line.strip()]
                )
            value = [value]
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []

        result: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if not text:
                    continue
                skill, _, raw = text.partition(":")
                skill = skill.strip()
                if not skill:
                    continue
                params: Any = {}
                raw = raw.strip()
                if raw:
                    try:
                        params = json.loads(raw)
                    except Exception:
                        params = {}
                result.append({"skill": skill, "params": params if isinstance(params, dict) else {}})
            elif isinstance(item, dict):
                skill = item.get("skill") or item.get("action") or item.get("name")
                if not skill:
                    continue
                params = item.get("params")
                if not isinstance(params, dict):
                    params = {
                        k: v for k, v in item.items()
                        if k not in ("skill", "action", "name", "params", "anchor")
                    }
                step: Dict[str, Any] = {"skill": str(skill).strip(), "params": params or {}}
                # 保留稳定锚点（录制回放时用于重解析易漂移的索引）
                anchor = item.get("anchor")
                if isinstance(anchor, dict) and anchor:
                    step["anchor"] = anchor
                result.append(step)
        return result

    @staticmethod
    def from_json(file_path: str) -> List[TestCase]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        test_cases: List[TestCase] = []
        for item in data:
            test_cases.append(TestCase(
                id=str(item.get("id", f"TC_{len(test_cases)+1}")),
                name=item.get("name", ""),
                description=item.get("description", ""),
                steps=item.get("steps", ""),
                expected_result=item.get("expected_result", ""),
                priority=item.get("priority", "medium"),
                tags=TestCaseParser._normalize_tags(item.get("tags", [])),
                setup_url=item.get("setup_url"),
                timeout=int(item.get("timeout", 60)),
                actions=TestCaseParser._normalize_step_list(item.get("actions")),
                assertions=TestCaseParser._normalize_step_list(item.get("assertions")),
            ))
        return test_cases

    @staticmethod
    def from_yaml(file_path: str) -> List[TestCase]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, list):
            raise ValueError("YAML test case file must contain a list of test cases.")

        test_cases: List[TestCase] = []
        for item in data:
            test_cases.append(TestCase(
                id=str(item.get("id", f"TC_{len(test_cases)+1}")),
                name=item.get("name", ""),
                description=item.get("description", ""),
                steps=item.get("steps", ""),
                expected_result=item.get("expected_result", ""),
                priority=item.get("priority", "medium"),
                tags=TestCaseParser._normalize_tags(item.get("tags", [])),
                setup_url=item.get("setup_url"),
                timeout=int(item.get("timeout", 60)),
                actions=TestCaseParser._normalize_step_list(item.get("actions")),
                assertions=TestCaseParser._normalize_step_list(item.get("assertions")),
            ))
        return test_cases

    @staticmethod
    def from_excel(file_path: str, sheet_name: Optional[str] = None) -> List[TestCase]:
        try:
            import openpyxl
        except ImportError as e:
            raise ImportError("请安装 openpyxl: pip install openpyxl") from e

        workbook = openpyxl.load_workbook(file_path, read_only=True)
        worksheet = workbook[sheet_name] if sheet_name else workbook.active
        rows = list(worksheet.iter_rows(values_only=True))

        if not rows:
            workbook.close()
            return []

        headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
        test_cases: List[TestCase] = []
        for row in rows[1:]:
            case_data = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
            test_cases.append(TestCase(
                id=str(case_data.get("ID", case_data.get("id", f"TC_{len(test_cases)+1}"))),
                name=str(case_data.get("用例名称", case_data.get("name", "")) or ""),
                description=str(case_data.get("描述", case_data.get("description", "")) or ""),
                steps=str(case_data.get("操作步骤", case_data.get("steps", "")) or ""),
                expected_result=str(case_data.get("预期结果", case_data.get("expected_result", "")) or ""),
                priority=str(case_data.get("优先级", case_data.get("priority", "medium")) or "medium"),
                tags=TestCaseParser._normalize_tags(case_data.get("标签", case_data.get("tags", []))),
                setup_url=str(case_data.get("前置URL", case_data.get("setup_url", "")) or ""),
                timeout=int(case_data.get("超时时间", case_data.get("timeout", 60)) or 60),
                actions=TestCaseParser._normalize_step_list(
                    case_data.get("确定性步骤", case_data.get("actions"))
                ),
                assertions=TestCaseParser._normalize_step_list(
                    case_data.get("断言", case_data.get("assertions"))
                ),
            ))
        workbook.close()
        return test_cases

    @staticmethod
    def from_file(file_path: str, sheet_name: Optional[str] = None) -> List[TestCase]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            return TestCaseParser.from_yaml(file_path)
        if suffix == ".json":
            return TestCaseParser.from_json(file_path)
        if suffix in {".xls", ".xlsx"}:
            return TestCaseParser.from_excel(file_path, sheet_name=sheet_name)
        raise ValueError(f"Unsupported test case file type: {suffix}")


# ============================================================
# 公共辅助函数（供 BatchTestAgent / ExecuteTaskSkill / ExecuteBatchTestCasesSkill 共用）
# ============================================================

def _get_agent_config_from_manager(manager: Any) -> dict:
    """从 SkillManager 获取 Agent 配置段"""
    try:
        if hasattr(manager, 'config') and manager.config:
            return manager.config.get("agent", {})
    except Exception:
        pass
    return {}


def _create_llm_client(manager: Any) -> Optional[Any]:
    """
    创建或获取 LLM 客户端

    优先级：
    1. manager.config 中注入的 llm_client（如 create_enhanced_manager(llm_client=...) 传入）
    2. 从 agent 配置（api_key/base_url）创建 AsyncOpenAI
    3. 从环境变量（OPENAI_API_KEY/OPENAI_BASE_URL）创建 AsyncOpenAI
    4. openai 未安装时返回 None
    """
    # 优先使用 config 中注入的 llm_client
    if hasattr(manager, 'config') and manager.config:
        injected = manager.config.get("llm_client")
        if injected is not None:
            return injected
    try:
        from openai import AsyncOpenAI
        config = _get_agent_config_from_manager(manager)
        kwargs = {}
        api_key = config.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        base_url = config.get("base_url", "") or os.environ.get("OPENAI_BASE_URL")
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)
    except ImportError:
        return None





class BatchTestAgent:
    """批量测试执行 Agent"""

    def __init__(
        self,
        skill_manager: SkillManager,
        llm_client: Any = None,
        max_steps_per_case: int = 20,
        max_retries_per_case: int = 3,
        max_consecutive_failures: int = 5,
        model: Optional[str] = None,
        temperature: float = 0.1,
        screenshot_on_failure: bool = True,
        screenshot_dir: Optional[str] = None,
        isolate_pages: Optional[bool] = None,
        case_timeout: Optional[float] = None,
        retry_failed_cases: Optional[int] = None,
        require_assertion: Optional[bool] = None,
        step_timeout: Optional[float] = None,
        llm_retries: Optional[int] = None,
        record_actions: Optional[bool] = None,
        replay_recorded: Optional[bool] = None,
        record_dir: Optional[str] = None,
        continue_on_action_failure: Optional[bool] = None,
        fallback_to_llm_on_action_failure: Optional[bool] = None,
    ):
        self.manager = skill_manager
        self.llm = llm_client or self._get_llm_client()
        self.max_steps_per_case = max_steps_per_case
        self.max_retries_per_case = max_retries_per_case
        self.max_consecutive_failures = max_consecutive_failures
        # 优先使用传入的 model，其次从 config 读取，最后 fallback
        if model:
            self.model = model
        else:
            config = self._get_agent_config()
            self.model = config.get("model", "gpt-4o")
        self.temperature = temperature
        self.screenshot_on_failure = screenshot_on_failure
        self.screenshot_dir = screenshot_dir or os.path.join(os.getcwd(), "screenshots")
        os.makedirs(self.screenshot_dir, exist_ok=True)

        # ---------- 稳定性选项（显式参数优先，其次 config.yaml 的 agent 段） ----------
        agent_cfg = self._get_agent_config()
        self.isolate_pages = self._resolve_bool(
            isolate_pages, agent_cfg.get("isolate_pages", True)
        )
        self.case_timeout = self._resolve_float(
            case_timeout, agent_cfg.get("case_timeout", 120), allow_zero=True
        )
        self.retry_failed_cases = self._resolve_int(
            retry_failed_cases, agent_cfg.get("retry_failed_cases", 0)
        )
        self.require_assertion = self._resolve_bool(
            require_assertion, agent_cfg.get("require_assertion", False)
        )
        self.step_timeout = self._resolve_float(
            step_timeout, agent_cfg.get("step_timeout", 60), allow_zero=True
        )
        self.llm_retries = self._resolve_int(
            llm_retries, agent_cfg.get("llm_retries", 3)
        )
        # 录制/回放：录制默认关闭（生成“动作建议”文件），回放需人工确认后开启
        self.record_actions = self._resolve_bool(
            record_actions, agent_cfg.get("record_actions", False)
        )
        self.replay_recorded = self._resolve_bool(
            replay_recorded, agent_cfg.get("replay_recorded", False)
        )
        self.record_dir = record_dir or agent_cfg.get("record_dir") or os.path.join(
            os.getcwd(), "recorded_actions"
        )
        self.continue_on_action_failure = self._resolve_bool(
            continue_on_action_failure, agent_cfg.get("continue_on_action_failure", False)
        )
        # 确定性执行（actions/回放）失败后是否回退 LLM 规划（默认关闭：保持“确定性=可复现”语义）
        self.fallback_to_llm_on_action_failure = self._resolve_bool(
            fallback_to_llm_on_action_failure,
            agent_cfg.get("fallback_to_llm_on_action_failure", False),
        )
        # 框架断言前的页面稳定等待（毫秒）：避免“URL 已变、标题/内容未更新”的竞态
        self.assertion_settle_ms = self._resolve_int(
            None, agent_cfg.get("assertion_settle_ms", 3000)
        )
        # 框架断言的有限重试（“最终满足”语义）：导航/渲染未完成时不会误判
        self.assertion_retries = self._resolve_int(
            None, agent_cfg.get("assertion_retries", 3), allow_zero=False
        )
        self.assertion_retry_interval_ms = self._resolve_int(
            None, agent_cfg.get("assertion_retry_interval_ms", 500)
        )

    # ---------- 配置解析辅助 ----------

    @staticmethod
    def _resolve_bool(explicit: Optional[bool], fallback: Any) -> bool:
        if explicit is not None:
            return bool(explicit)
        if isinstance(fallback, str):
            return fallback.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(fallback)

    @staticmethod
    def _resolve_int(explicit: Optional[int], fallback: Any, allow_zero: bool = True) -> int:
        value = explicit if explicit is not None else fallback
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 0
        if not allow_zero and parsed <= 0:
            parsed = 1
        return max(0, parsed)

    @staticmethod
    def _resolve_float(explicit: Optional[float], fallback: Any, allow_zero: bool = True) -> float:
        value = explicit if explicit is not None else fallback
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        if not allow_zero and parsed <= 0:
            parsed = 1.0
        return max(0.0, parsed)

    def _get_agent_config(self) -> dict:
        return _get_agent_config_from_manager(self.manager)

    def _get_llm_client(self):
        return _create_llm_client(self.manager)

    async def execute_batch(self, test_cases: List[TestCase]) -> BatchTestResult:
        result = BatchTestResult()
        result.start_time = time.time()

        for case in test_cases:
            if result.consecutive_failures >= self.max_consecutive_failures:
                result.stop_reason = f"连续失败 {result.consecutive_failures} 次，停止执行"
                break

            case_context = TestCaseContext(test_case=case)
            case_context.start_time = time.time()
            case_context.status = "running"

            case_result = await self._execute_single_case(case_context)

            # 用例级自动重跑（默认关闭；对网络/UI 抖动有效，但会掩盖真实缺陷）
            attempts = 0
            while (not case_result.success) and attempts < self.retry_failed_cases:
                attempts += 1
                logger.warning(
                    "用例 %s 第 %d 次重跑（上次失败原因：%s）",
                    case.id, attempts, case_result.failure_reason or case_result.message,
                )
                case_result = await self._execute_single_case(case_context)
            case_result.retry_count = attempts

            result.add_case_result(case_result)
            case_context.end_time = time.time()
            case_context.status = "passed" if case_result.success else "failed"

        result.end_time = time.time()
        return result

    async def _execute_single_case(self, context: TestCaseContext) -> TestCaseResult:
        case = context.test_case
        start_ts = time.time()

        # 用例间隔离：每条用例使用全新页面，避免上一条用例的 DOM/URL 残留
        if self.isolate_pages:
            await self._isolate_page()

        if case.setup_url:
            await self.manager.execute("navigate", url=case.setup_url)
            await self.manager.execute("wait", seconds=2)

        # ① 执行阶段：判定走哪条路（优先级：用例声明 actions > 录制回放 > LLM 规划）
        declared_actions = list(case.actions)          # 用例文件里显式声明的确定性步骤
        recorded_actions = self._load_recorded_actions(case)  # 仅当 replay_recorded=true 且存在录制文件

        if declared_actions:
            actions, actions_source = declared_actions, "case"
        else:
            actions, actions_source = recorded_actions, ("replay" if recorded_actions else "")

        mode = "deterministic" if actions else "llm"
        logger.info(
            "用例 %s 执行模式: %s%s",
            case.id,
            "确定性执行" if mode == "deterministic" else "LLM 规划",
            f"（来源：{'用例声明 actions' if actions_source == 'case' else '录制回放'}，"
            f"{len(actions)} 步，不调用 LLM）" if mode == "deterministic" else "",
        )

        agent_result: Optional[AgentResult] = None
        fallback_used = False
        fallback_reason = ""

        if mode == "deterministic":
            steps, param_notes, audited, actions_ok = await self._run_action_list(actions)
            final_message = f"确定性执行：{sum(1 for s in steps if s.get('success'))}/{len(actions)} 步成功"
            agent_error = "" if actions_ok else self._first_failure_reason(steps)

            # 确定性执行失败 → 可选回退 LLM 规划（默认关闭）
            if not actions_ok and self.fallback_to_llm_on_action_failure and self.llm is not None:
                fallback_used = True
                fallback_reason = agent_error or "确定性步骤执行失败"
                logger.warning(
                    "用例 %s 确定性执行失败，回退 LLM 规划；原因：%s", case.id, fallback_reason
                )
                try:
                    agent_result = await self._run_llm_stage(
                        case,
                        fallback_note=(
                            f"上一次确定性执行失败（{fallback_reason}）。"
                            "当前页面可能处于执行到一半的中间状态，请先确认页面状态，再继续完成任务。"
                        ),
                    )
                except asyncio.TimeoutError:
                    return await self._timeout_case_result(
                        case, start_ts, "llm", self._case_timeout_of(case), True, fallback_reason
                    )

                # 合并两阶段步骤：确定性步骤在前、LLM 步骤在后（标注 stage，便于复盘）
                for record in steps:
                    record.setdefault("stage", "deterministic")
                offset = len(steps)
                for record in agent_result.steps_executed:
                    merged = dict(record)
                    merged["step"] = offset + int(merged.get("step") or 0)
                    merged["stage"] = "llm"
                    steps.append(merged)
                param_notes.extend(agent_result.param_notes or [])
                for record in agent_result.steps_executed:
                    skill = str(record.get("skill"))
                    if record.get("audited") and skill not in audited:
                        audited.append(skill)

                actions_ok = agent_result.success
                mode = "llm"
                final_message = agent_result.final_message
                agent_error = agent_result.error
        else:
            if self.llm is None:
                return TestCaseResult(
                    test_case_id=case.id,
                    test_case_name=case.name,
                    success=False,
                    message="LLM client not configured",
                    failure_reason="LLM client not configured",
                )

            try:
                agent_result = await self._run_llm_stage(case)
            except asyncio.TimeoutError:
                return await self._timeout_case_result(
                    case, start_ts, mode, self._case_timeout_of(case)
                )

            steps = agent_result.steps_executed
            param_notes = list(agent_result.param_notes)
            audited = sorted({
                str(s.get("skill")) for s in steps if s.get("audited")
            })
            actions_ok = agent_result.success
            final_message = agent_result.final_message
            agent_error = agent_result.error

        # ② 判定阶段：框架强制断言（确定性执行，与 LLM 自述解耦）
        declared_assertions = await self._run_declared_assertions(case) if case.assertions else []
        failed_declared = [a for a in declared_assertions if not a["success"]]

        assertions = list(declared_assertions)
        if agent_result is not None:
            assertions = list(agent_result.assertions) + declared_assertions

        if failed_declared:
            success = False
            failure_reason = "框架断言失败: " + "; ".join(
                f"{a['skill']}({json.dumps(a['params'], ensure_ascii=False)}) - {a['message']}"
                for a in failed_declared
            )
        else:
            success = actions_ok
            failure_reason = "" if success else (
                agent_error or self._first_failure_reason(steps) or "用例执行失败"
            )

        duration = time.time() - start_ts

        screenshots: List[str] = []
        if self.screenshot_on_failure and not success:
            screenshots = await self._capture_failure_screenshot(case)

        # ③ 成功后录制动作（供人工确认后固化为 actions，实现确定性回放）
        recorded_path = None
        if success and mode == "llm":
            recorded_path = self._record_actions(case, steps, assertions=assertions)

        return TestCaseResult(
            test_case_id=case.id,
            test_case_name=case.name,
            success=success,
            message=final_message,
            steps_executed=steps,
            failure_reason=failure_reason,
            duration=duration,
            screenshots=screenshots,
            assertions=assertions,
            param_notes=param_notes,
            audited_skills=audited,
            recorded_actions_path=recorded_path,
            mode=mode,
            actions_source=actions_source,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

    def _case_timeout_of(self, case: TestCase) -> float:
        """用例级超时：用例文件的 timeout 优先，其次 agent.case_timeout"""
        return float(case.timeout) if case.timeout and case.timeout > 0 else self.case_timeout

    async def _run_llm_stage(self, case: TestCase, fallback_note: str = "") -> AgentResult:
        """
        LLM 规划执行阶段（模式 A 与「actions 失败回退」共用）。

        Args:
            case: 测试用例
            fallback_note: 回退说明，会前置到任务提示词，让模型知道上一次确定性执行失败的上下文

        Raises:
            asyncio.TimeoutError: 触发用例级超时
        """
        browser_agent = BrowserAgent(
            skill_manager=self.manager,
            llm_client=self.llm,
            max_steps=self.max_steps_per_case,
            max_retries=self.max_retries_per_case,
            model=self.model,
            temperature=self.temperature,
            # 用例声明了框架断言时，由框架负责判定，无需再要求模型自己产出断言
            require_assertion=self.require_assertion and not case.assertions,
            step_timeout=self.step_timeout,
            llm_retries=self.llm_retries,
        )

        task_prompt = case.steps
        if fallback_note:
            task_prompt = f"[回退说明] {fallback_note}\n\n{task_prompt}"
        if case.expected_result:
            task_prompt = f"{task_prompt}\n\n预期结果: {case.expected_result}"

        case_timeout = self._case_timeout_of(case)
        if case_timeout and case_timeout > 0:
            return await asyncio.wait_for(
                browser_agent.execute_task(task_prompt), timeout=case_timeout
            )
        return await browser_agent.execute_task(task_prompt)

    async def _timeout_case_result(
        self,
        case: TestCase,
        start_ts: float,
        mode: str,
        timeout: float,
        fallback_used: bool = False,
        fallback_reason: str = "",
    ) -> TestCaseResult:
        """构造「用例级超时」失败结果（带失败截图与回退标注）"""
        duration = time.time() - start_ts
        reason = f"用例执行超时（{timeout:.0f} 秒）"
        logger.warning("用例 %s %s", case.id, reason)
        screenshots = await self._capture_failure_screenshot(case)
        return TestCaseResult(
            test_case_id=case.id,
            test_case_name=case.name,
            success=False,
            message=reason,
            steps_executed=[],
            failure_reason=reason,
            duration=duration,
            screenshots=screenshots,
            mode=mode,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

    async def _execute_step_with_timeout(self, skill: str, params: Dict[str, Any]):
        """执行单个技能（带步骤级超时），供 actions / 框架断言复用"""
        if self.step_timeout and self.step_timeout > 0:
            try:
                return await asyncio.wait_for(
                    self.manager.execute(skill, **params), timeout=self.step_timeout
                )
            except asyncio.TimeoutError:
                return SkillResult(
                    success=False,
                    message=f"Step timed out after {self.step_timeout:.0f}s: {skill}",
                    error="step timeout",
                )
        return await self.manager.execute(skill, **params)

    def _first_failure_reason(self, steps: List[Dict[str, Any]]) -> str:
        """取第一个失败步骤的原因（用于确定性执行的失败说明）"""
        for step in steps:
            if not step.get("success"):
                return (
                    f"步骤 {step.get('step')} 失败: {step.get('skill')}"
                    f"({json.dumps(step.get('params', {}), ensure_ascii=False)}) - {step.get('message')}"
                )
        return ""

    async def _run_action_list(self, actions: List[Dict[str, Any]]) -> tuple:
        """
        确定性执行 actions（不经过 LLM 规划）。

        Returns:
            (steps, param_notes, audited_skills, all_success)
        """
        steps: List[Dict[str, Any]] = []
        notes: List[str] = []
        audited: List[str] = []
        all_ok = True

        for index, action in enumerate(actions, 1):
            skill = str(action.get("skill") or "").strip()
            params = action.get("params") or {}
            if not skill:
                continue

            # 回放时用锚点重解析索引（索引会随页面元素顺序漂移）
            anchor = action.get("anchor")
            if skill.endswith("_by_index") and isinstance(anchor, dict) and "index" in params:
                resolved = await self._resolve_index_from_anchor(anchor, params.get("index"))
                if resolved is not None and resolved != params.get("index"):
                    logger.info(
                        "回放锚点重解析: %s index %s -> [%s]（锚点 %s）",
                        skill, params.get("index"), resolved, anchor,
                    )
                    params = {**params, "index": resolved}

            result = await self._execute_step_with_timeout(skill, params)
            is_audited = bool(getattr(result, "audited", False))
            record = {
                "step": index,
                "skill": skill,
                "params": params,
                "success": result.success,
                "message": result.message,
                "deterministic": True,
                "audited": is_audited,
            }
            step_anchor = extract_element_anchor(result.data)
            if step_anchor:
                record["anchor"] = step_anchor
            steps.append(record)

            step_notes = getattr(result, "param_notes", None)
            if step_notes:
                notes.extend(f"步骤{index} {skill}: {n}" for n in step_notes)
            if is_audited and skill not in audited:
                audited.append(skill)

            logger.info(
                "%s 确定性步骤 %d/%d: %s(%s) - %s",
                "✅" if result.success else "❌", index, len(actions), skill,
                json.dumps(params, ensure_ascii=False), result.message,
            )

            if not result.success:
                all_ok = False
                if not self.continue_on_action_failure:
                    break

        return steps, notes, audited, all_ok

    async def _run_declared_assertions(self, case: TestCase) -> List[Dict[str, Any]]:
        """执行用例声明的框架断言，返回断言证据记录"""
        records: List[Dict[str, Any]] = []

        # 断言前先等页面到达 load 状态：避免"URL 已变、标题/内容还没更新"的竞态误判
        if self.assertion_settle_ms and self.assertion_settle_ms > 0:
            try:
                page = self.manager.current_page
                if page is not None and hasattr(page, "wait_for_load_state"):
                    await page.wait_for_load_state("load", timeout=self.assertion_settle_ms)
            except Exception:
                pass  # SPA/长连接页面可能永远不触发 load，等不到就继续（有超时兜底）

        total = len(case.assertions)

        for index, assertion in enumerate(case.assertions, 1):
            skill = str(assertion.get("skill") or "").strip()
            params = assertion.get("params") or {}
            if not skill:
                continue

            # 有限重试：“最终满足”语义，避免断言早于页面渲染而误判失败
            attempts = 0
            result = None
            while attempts < self.assertion_retries:
                attempts += 1
                result = await self._execute_step_with_timeout(skill, params)
                if result.success:
                    break
                if attempts < self.assertion_retries and self.assertion_retry_interval_ms > 0:
                    await asyncio.sleep(self.assertion_retry_interval_ms / 1000)

            message = result.message
            if attempts > 1 and result.success:
                message = f"{message}（第 {attempts} 次尝试后通过）"

            records.append({
                "step": index,
                "skill": skill,
                "params": params,
                "success": result.success,
                "message": message,
                "attempts": attempts,
                "declared": True,
                "audited": bool(getattr(result, "audited", False)),
            })
            logger.info(
                "%s 框架断言 %d/%d: %s(%s) - %s（尝试 %d 次）",
                "✅" if result.success else "❌", index, total, skill,
                json.dumps(params, ensure_ascii=False), message, attempts,
            )

        return records

    def _recorded_actions_path(self, case: TestCase) -> str:
        """录制文件路径：<record_dir>/<case_id>.actions.yaml"""
        return os.path.join(self.record_dir, f"{case.id}.actions.yaml")

    async def _resolve_index_from_anchor(self, anchor: Dict[str, Any], fallback_index: Any) -> Optional[int]:
        """
        回放时用稳定锚点重新解析索引。

        匹配优先级：元素 id → placeholder → selector(+tag) → tag+text → name。
        匹配不到时返回 None（调用方沿用录制时的索引）。
        """
        try:
            from .dom_snapshot import DomSnapshotService

            page = self.manager.current_page
            if page is None:
                return None
            snapshot = await DomSnapshotService().capture(page)
        except Exception:
            return None

        anchor_id = anchor.get("element_id")
        anchor_placeholder = anchor.get("placeholder")
        anchor_selector = anchor.get("selector")
        anchor_tag = anchor.get("tag")
        anchor_text = anchor.get("text")
        anchor_name = anchor.get("name")

        try:
            for element in snapshot.elements:
                if anchor_id and element.element_id == anchor_id:
                    return element.index
                if anchor_placeholder and element.placeholder == anchor_placeholder:
                    return element.index
                if anchor_selector and element.selector == anchor_selector and (
                    not anchor_tag or element.tag == anchor_tag
                ):
                    return element.index
                if anchor_tag and anchor_text and element.tag == anchor_tag and element.text == anchor_text:
                    return element.index
                if anchor_name and element.name == anchor_name:
                    return element.index
        except Exception:
            return None

        # 精确锚点未命中（页面布局变体/改版）：语义回退 + 明确记录，便于人工评审
        fallback = fuzzy_match_anchor(anchor, snapshot.elements)
        if fallback is not None and fallback != fallback_index:
            logger.warning(
                "回放锚点未精确命中（锚点 %s），已按语义回退：index %s -> [%s]；"
                "如结果异常请重新录制该用例",
                anchor, fallback_index, fallback,
            )
            return fallback

        logger.warning("回放锚点未命中且无法语义回退（锚点 %s），沿用录制索引 %s", anchor, fallback_index)
        return None

    def _load_recorded_actions(self, case: TestCase) -> List[Dict[str, Any]]:
        """回放模式：读取录制的动作（需显式开启 replay_recorded）"""
        if not self.replay_recorded:
            return []

        path = self._recorded_actions_path(case)
        if not os.path.exists(path):
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            actions = TestCaseParser._normalize_step_list(data.get("actions"))
            if actions:
                logger.info("用例 %s 命中录制动作，回放 %d 步：%s", case.id, len(actions), path)
            return actions
        except Exception as e:
            logger.warning("读取录制动作失败（忽略）：%s", e)
            return []

    def _record_actions(
        self,
        case: TestCase,
        steps: List[Dict[str, Any]],
        assertions: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        把成功执行的动作序列录制为 YAML，供人工确认后固化为 case.actions

        - `actions`：可复现的操作步骤（不含断言），带稳定锚点与归一化后的参数
        - `assertions`：本次执行中用到的断言（草稿），供 `--with-assertions` 一并固化
        - audit 技能（如 execute_js）**照常录制**，只是在写文件时标注告警，交由人工 review
        """
        if not self.record_actions:
            return None

        try:
            usable: List[Dict[str, Any]] = []
            for step in steps:
                if not step.get("success") or is_assertion_skill(str(step.get("skill"))):
                    continue
                item: Dict[str, Any] = {
                    "skill": step.get("skill"),
                    # 优先录制归一化后的参数（避免把模型别名写法固化到文件里）
                    "params": step.get("normalized_params") or step.get("params", {}),
                }
                # 记录稳定锚点：回放时据此重解析索引，抵抗页面元素顺序漂移
                if step.get("anchor"):
                    item["anchor"] = step["anchor"]
                if step.get("audited"):
                    item["audited"] = True   # 标注：该步骤使用了 audit 技能（允许，但需 review）
                usable.append(item)
            if not usable:
                return None

            assertion_drafts: List[Dict[str, Any]] = []
            for record in (assertions or []):
                if not record.get("success"):
                    continue
                assertion_drafts.append({
                    "skill": record.get("skill"),
                    "params": record.get("normalized_params") or record.get("params", {}),
                })

            os.makedirs(self.record_dir, exist_ok=True)
            path = self._recorded_actions_path(case)
            payload = {
                "id": case.id,
                "name": case.name,
                "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "recorded_from": "llm",
                "actions": usable,
            }
            if assertion_drafts:
                payload["assertions"] = assertion_drafts
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
            logger.info("已录制用例 %s 的动作到 %s（%d 步）", case.id, path, len(usable))
            return path
        except Exception as e:
            logger.warning("录制动作失败（忽略）：%s", e)
            return None

    async def _isolate_page(self) -> None:
        """
        为当前用例切换到一个全新页面，避免用例间状态污染。

        失败时仅记录日志并沿用当前页（不影响用例继续执行）。
        """
        browser_context = getattr(self.manager, "_browser_context", None)
        if browser_context is None:
            return

        try:
            previous = self.manager.current_page
            new_page = await browser_context.new_page()
            self.manager.set_current_page(new_page)

            if hasattr(self.manager, "_dom_cache"):
                try:
                    await self.manager._dom_cache.invalidate(new_page)
                except Exception:
                    pass

            if previous is not None and previous is not new_page:
                try:
                    await previous.close()
                except Exception as e:
                    logger.debug("关闭上一条用例页面失败（忽略）：%s", e)
        except Exception as e:
            logger.debug("用例页面隔离失败（沿用当前页）：%s", e)

    async def _capture_failure_screenshot(self, case: TestCase) -> List[str]:
        """失败截图（带异常保护，截图失败不影响用例结果）"""
        screenshots: List[str] = []
        try:
            path = os.path.join(self.screenshot_dir, f"{case.id}_failure.png")
            screenshot_result = await self.manager.execute("screenshot", path=path)
            if screenshot_result.success:
                screenshots.append(path)
        except Exception as e:
            logger.debug("失败截图失败（忽略）：%s", e)
        return screenshots


# ============================================================
# LLM 客户端协议
# ============================================================

class LLMClientProtocol(Protocol):
    """LLM 客户端协议（兼容 OpenAI AsyncOpenAI）"""

    class Chat:
        class Completions:
            async def create(self, **kwargs) -> Any: ...
        completions: "Completions"
    chat: Chat


# ============================================================
# BrowserAgent - 浏览器操作智能体
# ============================================================

class BrowserAgent:
    """
    浏览器操作智能体

    接收自然语言任务描述，自动规划并执行一系列操作。
    内置防环机制，避免无限循环。
    """

    def __init__(
        self,
        skill_manager: SkillManager,
        llm_client: Any,
        max_steps: int = 20,
        max_retries: int = 3,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_repeats: int = 3,
        use_cache: bool = False,
        require_assertion: Optional[bool] = None,
        assertion_gate_retries: Optional[int] = None,
        step_timeout: Optional[float] = None,
        llm_retries: Optional[int] = None,
    ):
        """
        初始化 Agent

        Args:
            skill_manager: SkillManager 实例
            llm_client: LLM 客户端（兼容 OpenAI AsyncOpenAI）
            max_steps: 最大执行步数
            max_retries: 最大连续失败次数
            model: LLM 模型名称
            temperature: LLM 温度参数
            max_repeats: 连续重复同一操作的最大次数，超过则判定为死循环
            use_cache: 是否启用 LLM 响应缓存（默认关闭，因为 Agent 规划依赖实时页面状态，缓存可能导致过期规划）
            require_assertion: 断言硬门禁：未执行断言 / 最后一次断言失败时不允许判定为 done
                               （未显式传入时读取 config 的 agent.require_assertion，默认 False）
            assertion_gate_retries: 门禁拦截后允许模型补救的次数（默认读取 agent.assertion_gate_retries）
            step_timeout: 单步（单个技能调用）超时秒数，<=0 表示不限制（默认读取 agent.step_timeout）
            llm_retries: LLM 规划调用失败/JSON 解析失败的重试次数（默认读取 agent.llm_retries）
        """
        self.manager = skill_manager
        self.llm = llm_client
        self.max_steps = max_steps
        self.max_retries = max_retries
        agent_cfg = _get_agent_config_from_manager(skill_manager)
        # model 未显式传入时，从 config 的 agent 段读取（与 BatchTestAgent 保持一致）
        if model:
            self.model = model
        else:
            self.model = agent_cfg.get("model", "gpt-4o")
        self.temperature = temperature
        self.max_repeats = max_repeats
        self.use_cache = use_cache

        # ---------- 稳定性 / 判定严谨性选项 ----------
        self.require_assertion = BatchTestAgent._resolve_bool(
            require_assertion, agent_cfg.get("require_assertion", False)
        )
        self.assertion_gate_retries = BatchTestAgent._resolve_int(
            assertion_gate_retries, agent_cfg.get("assertion_gate_retries", 1)
        )
        self.step_timeout = BatchTestAgent._resolve_float(
            step_timeout, agent_cfg.get("step_timeout", 60)
        )
        self.llm_retries = BatchTestAgent._resolve_int(
            llm_retries, agent_cfg.get("llm_retries", 3), allow_zero=False
        )

    async def execute_task(self, task: str) -> AgentResult:
        """
        执行自然语言任务

        流程：
        1. 获取当前页面状态
        2. 让 LLM 规划下一步
        3. 执行该步
        4. 检查是否完成或触发防环机制
        5. 重复 1-4 直到完成或达到限制

        Args:
            task: 自然语言任务描述

        Returns:
            AgentResult: 执行结果
        """
        result = AgentResult(task=task)
        history: List[Dict] = []
        steps_executed: List[Dict] = []
        consecutive_failures = 0
        # 防环检测：记录上一次操作和连续重复次数
        last_op_key: Optional[str] = None
        consecutive_repeats = 0
        # 断言证据（硬门禁依据）与参数归一化记录
        assertions: List[Dict[str, Any]] = []
        param_notes: List[str] = []
        gate_nudges = 0

        logger.info(f"Agent starting task: {task}")

        for step_num in range(1, self.max_steps + 1):
            logger.info(f"--- Step {step_num}/{self.max_steps} ---")

            # 1. 获取页面状态
            page_state = await self._get_page_state()

            # 2. 让 LLM 规划下一步
            plan = await self._plan_next_step(task, page_state, history)

            if plan.status == PlanStatus.DONE:
                # 断言硬门禁：没有断言证据（或最后一次断言失败）时不允许判定为 done
                gate_error = (
                    self._assertion_gate_error(assertions) if self.require_assertion else ""
                )
                if gate_error:
                    if gate_nudges < self.assertion_gate_retries:
                        gate_nudges += 1
                        logger.warning(
                            "断言门禁拦截 done（第 %d 次）：%s", gate_nudges, gate_error
                        )
                        history.append({
                            "step": step_num,
                            "skill": "assertion_gate",
                            "params": {},
                            "description": "断言门禁拦截",
                            "success": False,
                            "message": (
                                f"{gate_error} 请立即执行所需的断言技能，"
                                f"确认其返回成功后才能结束任务。"
                            ),
                        })
                        continue

                    result.success = False
                    result.error = f"断言门禁：{gate_error}"
                    result.final_message = f"Task not accepted at step {step_num}: {result.error}"
                    logger.warning(result.final_message)
                    break

                result.success = True
                result.final_message = plan.reasoning or f"Task completed after {step_num - 1} steps"
                logger.info(f"Task completed: {result.final_message}")
                break

            if plan.status == PlanStatus.FAILED:
                result.error = plan.error or plan.reasoning
                result.final_message = f"Task failed at step {step_num}: {result.error}"
                logger.warning(f"Task failed: {result.final_message}")
                break

            if plan.step is None:
                result.error = "LLM returned no step but status is continue"
                break

            # 3. 防环检查：连续重复同一操作达到阈值才判定为死循环
            #    允许合理的重复操作（如翻页、轮询），仅拦截真正卡住的情况
            op_key = f"{plan.step.skill}:{json.dumps(plan.step.params, sort_keys=True)}"
            if op_key == last_op_key:
                consecutive_repeats += 1
                if consecutive_repeats >= self.max_repeats:
                    result.error = (
                        f"Loop detected: operation '{op_key}' repeated "
                        f"{consecutive_repeats} times consecutively"
                    )
                    result.final_message = f"Task stopped due to loop detection at step {step_num}"
                    logger.warning(result.error)
                    break
            else:
                consecutive_repeats = 0
            last_op_key = op_key

            # 4. 执行该步
            try:
                logger.info(f"Executing: {plan.step.skill}({plan.step.params})")
                step_result = await self._run_step(plan.step)

                step_record = {
                    "step": step_num,
                    "skill": plan.step.skill,
                    "params": plan.step.params,
                    "description": plan.step.description,
                    "success": step_result.success,
                    "message": step_result.message,
                    "audited": bool(getattr(step_result, "audited", False)),
                }
                anchor = extract_element_anchor(step_result.data)
                if anchor:
                    step_record["anchor"] = anchor
                normalized = getattr(step_result, "normalized_params", None)
                if normalized:
                    step_record["normalized_params"] = normalized
                steps_executed.append(step_record)
                history.append(step_record)

                # 记录参数归一化（模型传参质量观测）
                step_notes = getattr(step_result, "param_notes", None)
                if step_notes:
                    param_notes.extend(f"步骤{step_num} {plan.step.skill}: {n}" for n in step_notes)

                # 记录断言证据（硬门禁依据）
                if is_assertion_skill(plan.step.skill):
                    assertions.append(dict(step_record))

                if step_result.success:
                    consecutive_failures = 0
                    logger.info(f"✅ Step {step_num}: {plan.step.skill}({plan.step.params}) - {step_result.message}")
                else:
                    consecutive_failures += 1
                    logger.warning(f"❌ Step {step_num} failed: {step_result.message}")

                    # 防环检查：连续失败
                    if consecutive_failures >= self.max_retries:
                        result.error = f"Consecutive failures reached limit: {consecutive_failures}"
                        result.final_message = f"Task stopped due to repeated failures at step {step_num}"
                        logger.warning(result.error)
                        break

            except Exception as e:
                consecutive_failures += 1
                step_record = {
                    "step": step_num,
                    "skill": plan.step.skill,
                    "params": plan.step.params,
                    "description": plan.step.description,
                    "success": False,
                    "message": f"Exception: {str(e)}",
                    "audited": False,
                }
                steps_executed.append(step_record)
                history.append(step_record)
                if is_assertion_skill(plan.step.skill):
                    assertions.append(dict(step_record))
                logger.exception(f"Step {step_num} raised exception: {e}")

                if consecutive_failures >= self.max_retries:
                    result.error = f"Consecutive exceptions reached limit: {consecutive_failures}"
                    break

        else:
            # 达到最大步数
            result.error = f"Max steps ({self.max_steps}) reached without completion"
            result.final_message = result.error
            logger.warning(result.error)

        result.steps_executed = steps_executed
        result.assertions = assertions
        result.param_notes = param_notes
        if not result.final_message:
            result.final_message = result.error or "Task execution ended"

        return result

    async def _run_step(self, step: PlanStep) -> SkillResult:
        """
        执行单个步骤（带步骤级超时保护）

        步骤级超时用于兜底：单个技能卡住时不会拖垮整条用例（用例级超时见 BatchTestAgent）。
        """
        if self.step_timeout and self.step_timeout > 0:
            try:
                return await asyncio.wait_for(
                    self.manager.execute(step.skill, **step.params),
                    timeout=self.step_timeout,
                )
            except asyncio.TimeoutError:
                return SkillResult(
                    success=False,
                    message=f"Step timed out after {self.step_timeout:.0f}s: {step.skill}",
                    error=f"step timeout after {self.step_timeout:.0f}s",
                )
        return await self.manager.execute(step.skill, **step.params)

    def _assertion_gate_error(self, assertions: List[Dict[str, Any]]) -> str:
        """
        断言硬门禁判定。

        Returns:
            空字符串表示允许判定为 done；非空字符串为拦截原因。
        """
        if not assertions:
            return "本次任务未执行任何断言类技能，缺少可验证的通过依据。"

        last = assertions[-1]
        if not last.get("success"):
            params = json.dumps(last.get("params", {}), ensure_ascii=False)
            return (
                f"最后一次断言失败：{last.get('skill')}({params}) - {last.get('message')}"
            )
        return ""

    async def _get_page_state(self) -> dict:
        """获取当前页面状态（URL、标题、DOM 快照）"""
        page = self.manager.current_page
        if page is None:
            return {"url": "", "title": "", "dom_snapshot": "No page open", "dom_elements_count": 0}

        # 获取 DOM 快照（使用已注册的 get_dom_snapshot skill）
        try:
            snapshot_result = await self.manager.execute("get_dom_snapshot", readable=True, max_elements=50)
            dom_text = snapshot_result.data.get("readable", "Failed to capture DOM") if snapshot_result.success else "Failed to capture DOM"
            element_count = snapshot_result.data.get("element_count", 0) if snapshot_result.success else 0
        except Exception:
            dom_text = "Failed to capture DOM"
            element_count = 0

        return {
            "url": page.url,
            "title": await page.title(),
            "dom_snapshot": dom_text,
            "dom_elements_count": element_count,
        }

    async def _plan_next_step(
        self,
        task: str,
        page_state: dict,
        history: list[dict],
    ) -> Plan:
        """让 LLM 规划下一步操作（带 LLM 调用 / JSON 解析重试，避免一次抖动判死整条用例）"""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(task, page_state, history)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 尝试从缓存获取 LLM 响应（仅在显式启用缓存时）
        # 注意：Agent 规划依赖实时页面状态，缓存可能导致过期规划，默认不启用
        if self.use_cache:
            cached_response = await self._get_cached_llm_response(messages)
            if cached_response is not None:
                logger.info("Using cached LLM response")
                return self._parse_plan(cached_response)

        attempts = max(1, int(self.llm_retries or 1))
        last_error = ""

        for attempt in range(1, attempts + 1):
            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=self.temperature,
                )

                content = response.choices[0].message.content or "{}"
                plan = self._parse_plan(content)

                # JSON 解析失败：把错误回喂给模型再试一次，而不是直接判整条用例失败
                if plan.status == PlanStatus.FAILED and "Invalid JSON" in (plan.error or ""):
                    last_error = plan.error
                    if attempt < attempts:
                        logger.warning(
                            "LLM 规划输出非法 JSON（第 %d/%d 次），回喂错误后重试", attempt, attempts
                        )
                        messages.append({"role": "assistant", "content": content[:2000]})
                        messages.append({
                            "role": "user",
                            "content": (
                                f"上一条回复不是合法 JSON（{plan.error}）。"
                                "请只输出一个合法的 JSON 对象，不要输出解释文字或代码块。"
                            ),
                        })
                        continue
                    return plan

                # 仅在启用缓存时缓存 LLM 响应
                if self.use_cache:
                    await self._cache_llm_response(messages, content)

                return plan

            except Exception as e:
                last_error = f"LLM error: {str(e)}"
                logger.warning("LLM 规划调用失败（第 %d/%d 次）：%s", attempt, attempts, e)
                if attempt < attempts:
                    await asyncio.sleep(min(1.0 * attempt, 3.0))

        return Plan(status=PlanStatus.FAILED, error=last_error or "LLM planning failed")

    async def _get_cached_llm_response(self, messages: list) -> Optional[str]:
        """从缓存获取 LLM 响应"""
        if hasattr(self.manager, '_llm_cache'):
            return await self.manager._llm_cache.get(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
        return None

    async def _cache_llm_response(self, messages: list, response: str) -> None:
        """缓存 LLM 响应"""
        if hasattr(self.manager, '_llm_cache'):
            await self.manager._llm_cache.set(
                model=self.model,
                messages=messages,
                response=response,
                temperature=self.temperature,
            )

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 技能策略：deny 的技能从可选列表剔除，audit 的技能提示“会被记录”
        policies: Dict[str, str] = {}
        try:
            policies = self.manager.list_skill_policies() or {}
        except Exception:
            policies = {}

        available_skills = [
            skill for skill in self.manager.list_skills()
            if policies.get(skill["name"], "allow") != "deny"
        ]
        skills_list = "\n".join(
            f"- {s['name']}: {s['description']}"
            for s in available_skills
        )

        denied_skills = [name for name, mode in policies.items() if mode == "deny"]
        audited_skills = [name for name, mode in policies.items() if mode == "audit"]

        policy_rules = ""
        if denied_skills:
            policy_rules += f"\n10. 以下技能已被禁用，禁止调用：{', '.join(denied_skills)}"
        if audited_skills:
            policy_rules += (
                f"\n11. 以下技能属于“审计技能”（可能绕过真实 UI 操作，使用后会被记录并在测试报告中"
                f"披露）：{', '.join(audited_skills)}。只有在页面上的 UI 交互技能"
                f"（click / click_by_index / fill_input / fill_by_index 等）确实无法完成该步骤时才可使用，"
                f"并在 description 中说明降级原因"
            )
        policy_rules += (
            "\n12. 若某步失败信息里带有“提示: 当前页面可输入元素/可交互元素（可用索引重试）…”，"
            "请直接按提示给出的索引重试，不要再猜测其它索引"
        )

        # 断言门禁开启时，把“必须有断言证据”写进提示词（软门禁，与硬门禁互补）
        assertion_rules = ""
        if self.require_assertion:
            assertion_rules = """
8. 【硬性要求】只有实际执行过断言类技能（url_contains / url_equals / title_contains /
   title_equals / page_contains_text / text_equals / text_contains / element_exists /
   element_visible / attribute_equals / count_elements 等）且其返回成功，才允许设置
   status 为 "done"
9. 【硬性要求】若最近一次断言失败，禁止设置 status 为 "done"：必须重试该断言或改用
   其它可行的验证方式；仍然失败则设置 status 为 "failed" 并说明原因
"""

        return f"""你是一个浏览器操作规划器。你的任务是根据用户的目标和当前页面状态，
规划下一步需要执行的操作。

## 可用的 Skills
{skills_list}

## 规则
1. 每次只规划一个步骤
2. 使用可用的 Skills 来完成任务
3. 如果任务已完成，设置 status 为 "done"
4. 如果任务无法完成，设置 status 为 "failed" 并说明原因
5. 避免重复执行相同的操作
6. 优先使用索引操作（click_by_index, fill_by_index）而不是手写 selector
7. 在操作前确保页面已导航到正确的 URL
7.1 若某个选择器找不到元素，不要反复重试同一个选择器：先调用 get_dom_snapshot 拿到
    当前元素索引，再改用 click_by_index / fill_by_index
7.2 元素属性已变化（not attached）通常说明页面已跳转，此时应直接校验当前页面状态，
    不要重复点击同一个索引
{assertion_rules}{policy_rules}
## 输出格式
必须返回严格的 JSON：
{{
    "step": {{
        "skill": "skill_name",
        "params": {{"param1": "value1"}},
        "description": "步骤描述"
    }},
    "status": "continue" | "done" | "failed",
    "reasoning": "为什么选择这个步骤"
}}

如果任务已完成，step 可以为 null。
"""

    def _build_user_prompt(self, task: str, page_state: dict, history: list[dict]) -> str:
        """构建用户提示词"""
        history_text = ""
        if history:
            history_text = "\n## 已执行的操作\n"
            for h in history[-5:]:  # 只显示最近 5 步
                status = "✅" if h["success"] else "❌"
                history_text += f"{status} Step {h['step']}: {h['skill']}({h['params']}) - {h['message']}\n"

        return f"""## 用户任务
{task}

## 当前页面状态
- URL: {page_state['url']}
- 标题: {page_state['title']}
- 可交互元素数量: {page_state['dom_elements_count']}

## 当前页面元素列表
{page_state['dom_snapshot']}
{history_text}

请规划下一步操作。"""

    def _parse_plan(self, json_str: str) -> Plan:
        """解析 LLM 输出的 JSON"""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {json_str}")
            return Plan(status=PlanStatus.FAILED, error=f"Invalid JSON: {e}")

        status_str = data.get("status", "continue")
        status = PlanStatus(status_str) if status_str in ("continue", "done", "failed") else PlanStatus.CONTINUE

        step_data = data.get("step")
        step = None
        if step_data and step_data.get("skill"):
            step = PlanStep(
                skill=step_data["skill"],
                params=step_data.get("params", {}),
                description=step_data.get("description", ""),
            )

        return Plan(
            step=step,
            status=status,
            reasoning=data.get("reasoning", ""),
            error=data.get("error", ""),
        )


# ============================================================
# ExecuteTaskSkill - 执行自然语言任务的 Skill
# ============================================================

class ExecuteTaskSkill(BaseSkill):
    """执行高层级自然语言任务"""

    name = "execute_task"
    description = "接收自然语言任务描述，自动规划并执行一系列操作"
    timeout_exempt = True  # 复合技能：内部有自己的步数/重试控制，不套用技能级硬超时

    async def run(
        self,
        task: str,
        max_steps: int = 20,
        max_retries: int = 3,
    ) -> SkillResult:
        """
        执行自然语言任务

        Args:
            task: 自然语言任务描述
            max_steps: 最大执行步数
            max_retries: 最大连续失败次数
        """
        page = await self.get_page()

        # 获取 LLM 客户端
        llm_client = self._get_llm_client()
        if llm_client is None:
            return SkillResult(
                success=False,
                message="LLM client not configured. Please configure vision.model in config.yaml or set OPENAI_API_KEY environment variable.",
            )

        agent = BrowserAgent(
            skill_manager=self.manager,
            llm_client=llm_client,
            max_steps=max_steps,
            max_retries=max_retries,
        )

        result = await agent.execute_task(task)

        return SkillResult(
            success=result.success,
            message=result.final_message or result.error,
            data={
                "task": result.task,
                "steps": result.steps_executed,
                "success": result.success,
            },
            error=result.error if not result.success else None,
        )

    def _get_llm_client(self):
        """获取 LLM 客户端（委托公共函数）"""
        return _create_llm_client(self.manager)

    def _get_agent_config(self) -> dict:
        """从 manager 获取 Agent 配置"""
        return _get_agent_config_from_manager(self.manager)


class ExecuteBatchTestCasesSkill(BaseSkill):
    """批量执行测试用例文件"""

    name = "execute_batch_testcases"
    description = "从 JSON/YAML/Excel 文件导入测试用例并按顺序批量执行"
    timeout_exempt = True  # 复合技能：整批用例可能运行数分钟，不能按单技能超时切断

    async def run(
        self,
        file_path: str,
        file_type: Optional[str] = None,
        sheet_name: Optional[str] = None,
        report_path: Optional[str] = None,
        max_steps_per_case: int = 20,
        max_retries_per_case: int = 3,
        screenshot_on_failure: bool = True,
    ) -> SkillResult:
        try:
            if file_type:
                suffix = file_type.lower()
                if suffix not in {"yaml", "yml", "json", "xls", "xlsx"}:
                    return SkillResult(success=False, message=f"Unsupported file_type: {file_type}")
                if suffix in {"yaml", "yml"}:
                    test_cases = TestCaseParser.from_yaml(file_path)
                elif suffix == "json":
                    test_cases = TestCaseParser.from_json(file_path)
                else:
                    test_cases = TestCaseParser.from_excel(file_path, sheet_name=sheet_name)
            else:
                test_cases = TestCaseParser.from_file(file_path, sheet_name=sheet_name)
        except Exception as e:
            return SkillResult(success=False, message=f"Failed to parse test case file: {str(e)}", error=str(e))

        llm_client = self._get_llm_client()
        if llm_client is None:
            return SkillResult(success=False, message="LLM client not configured")

        agent = BatchTestAgent(
            skill_manager=self.manager,
            llm_client=llm_client,
            max_steps_per_case=max_steps_per_case,
            max_retries_per_case=max_retries_per_case,
            screenshot_on_failure=screenshot_on_failure,
        )

        batch_result = await agent.execute_batch(test_cases)
        if report_path:
            batch_result.generate_report(report_path)

        success = batch_result.failed == 0
        return SkillResult(
            success=success,
            message=f"Batch execution completed: {batch_result.passed}/{batch_result.total} passed",
            data={
                "total": batch_result.total,
                "passed": batch_result.passed,
                "failed": batch_result.failed,
                "pass_rate": batch_result.pass_rate,
                "duration": batch_result.duration,
                "report_path": report_path,
            },
        )

    def _get_llm_client(self):
        """获取 LLM 客户端（委托公共函数）"""
        return _create_llm_client(self.manager)

    def _get_agent_config(self) -> dict:
        """从 manager 获取 Agent 配置"""
        return _get_agent_config_from_manager(self.manager)