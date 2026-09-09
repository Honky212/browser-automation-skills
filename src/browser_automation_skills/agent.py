"""Agent 层模块 - 提供自然语言任务自动规划和执行"""

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
            "| 序号 | 用例ID | 用例名称 | 状态 | 步数 | 失败原因 |",
            "|------|--------|----------|------|------|----------|",
        ]

        for idx, case in enumerate(self.case_results, 1):
            status = "✅ PASS" if case.success else "❌ FAIL"
            report_lines.append(
                f"| {idx} | {case.test_case_id} | {case.test_case_name} | {status} | {len(case.steps_executed)} | {case.failure_reason or '-'} |"
            )

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
            result.add_case_result(case_result)
            case_context.end_time = time.time()
            case_context.status = "passed" if case_result.success else "failed"

        result.end_time = time.time()
        return result

    async def _execute_single_case(self, context: TestCaseContext) -> TestCaseResult:
        case = context.test_case
        start_ts = time.time()

        if case.setup_url:
            await self.manager.execute("navigate", url=case.setup_url)
            await self.manager.execute("wait", seconds=2)

        if self.llm is None:
            return TestCaseResult(
                test_case_id=case.id,
                test_case_name=case.name,
                success=False,
                message="LLM client not configured",
                failure_reason="LLM client not configured",
            )

        browser_agent = BrowserAgent(
            skill_manager=self.manager,
            llm_client=self.llm,
            max_steps=self.max_steps_per_case,
            max_retries=self.max_retries_per_case,
            model=self.model,
            temperature=self.temperature,
        )

        task_prompt = case.steps
        if case.expected_result:
            task_prompt = f"{task_prompt}\n\n预期结果: {case.expected_result}"

        agent_result = await browser_agent.execute_task(task_prompt)
        duration = time.time() - start_ts

        screenshot_paths: List[str] = []
        if self.screenshot_on_failure and not agent_result.success:
            path = os.path.join(self.screenshot_dir, f"{case.id}_failure.png")
            screenshot_result = await self.manager.execute("screenshot", path=path)
            if screenshot_result.success:
                screenshot_paths.append(path)

        return TestCaseResult(
            test_case_id=case.id,
            test_case_name=case.name,
            success=agent_result.success,
            message=agent_result.final_message,
            steps_executed=agent_result.steps_executed,
            failure_reason=agent_result.error,
            duration=duration,
            screenshots=screenshot_paths,
        )


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
        """
        self.manager = skill_manager
        self.llm = llm_client
        self.max_steps = max_steps
        self.max_retries = max_retries
        # model 未显式传入时，从 config 的 agent 段读取（与 BatchTestAgent 保持一致）
        if model:
            self.model = model
        else:
            self.model = _get_agent_config_from_manager(skill_manager).get("model", "gpt-4o")
        self.temperature = temperature
        self.max_repeats = max_repeats
        self.use_cache = use_cache

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

        logger.info(f"Agent starting task: {task}")

        for step_num in range(1, self.max_steps + 1):
            logger.info(f"--- Step {step_num}/{self.max_steps} ---")

            # 1. 获取页面状态
            page_state = await self._get_page_state()

            # 2. 让 LLM 规划下一步
            plan = await self._plan_next_step(task, page_state, history)

            if plan.status == PlanStatus.DONE:
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
                step_result = await self.manager.execute(plan.step.skill, **plan.step.params)

                step_record = {
                    "step": step_num,
                    "skill": plan.step.skill,
                    "params": plan.step.params,
                    "description": plan.step.description,
                    "success": step_result.success,
                    "message": step_result.message,
                }
                steps_executed.append(step_record)
                history.append(step_record)

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
                }
                steps_executed.append(step_record)
                history.append(step_record)
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
        if not result.final_message:
            result.final_message = result.error or "Task execution ended"

        return result

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
        """让 LLM 规划下一步操作"""
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

        try:
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=self.temperature,
            )

            content = response.choices[0].message.content or "{}"
            
            # 仅在启用缓存时缓存 LLM 响应
            if self.use_cache:
                await self._cache_llm_response(messages, content)
            
            return self._parse_plan(content)
        except Exception as e:
            logger.exception(f"LLM planning failed: {e}")
            return Plan(
                status=PlanStatus.FAILED,
                error=f"LLM error: {str(e)}",
            )

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
        available_skills = self.manager.list_skills()
        skills_list = "\n".join(
            f"- {s['name']}: {s['description']}"
            for s in available_skills
        )

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