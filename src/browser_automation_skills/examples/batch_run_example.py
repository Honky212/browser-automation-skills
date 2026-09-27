# -*- coding: utf-8 -*-
"""
批量测试可运行示例 —— 启动浏览器、批量执行用例、生成 Markdown 报告

为什么用命令行而不是 MCP 工具：
    MCP 客户端对单次请求通常有 60s 超时，而批量执行（每条用例都要 LLM 多步规划）
    往往需要数分钟。本示例不受该限制；功能与 MCP 工具 `execute_batch_testcases` 等价。

用法：
    # 开箱即跑（默认用例是纯确定性 actions，不调用 LLM，只需浏览器）
    python -m browser_automation_skills.examples.batch_run_example

    # 跑"自然语言 + 框架断言"的示例（需要 config 里配好 LLM）
    python -m browser_automation_skills.examples.batch_run_example \\
        --cases test_case_templates/test_cases_baidu.yaml --headed

    # 指定用例文件与报告路径
    python -m browser_automation_skills.examples.batch_run_example \\
        --cases my_cases.yaml --report reports/my_report.md

    # 只解析用例、打印概要（不启动浏览器，可用于 CI 冒烟）
    python -m browser_automation_skills.examples.batch_run_example --parse-only

也可以用文件方式直接运行（不加 -m）：
    python path/to/browser_automation_skills/examples/batch_run_example.py --cases my_cases.yaml

配置文件查找顺序（可用 --config 显式指定）：
    ./config/config.yaml  ->  ./config.yaml
    找不到时会给出指引并退出（退出码 2）。
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .. import create_manager
from ..agent import BatchTestAgent, TestCase, TestCaseParser
from ..browser_launcher import BrowserLauncher

DEFAULT_CASE_FILE = (
    Path(__file__).resolve().parent / "test_case_templates" / "structured_actions_demo.yaml"
)
DEFAULT_REPORT_FILE = Path("batch_report.md")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CONFIG_CANDIDATES = (Path("config") / "config.yaml", Path("config.yaml"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m browser_automation_skills.examples.batch_run_example",
        description="批量执行测试用例并生成报告（可运行示例）",
    )
    parser.add_argument("--cases", default=str(DEFAULT_CASE_FILE),
                        help="用例文件（.yaml/.yml/.json/.xlsx；默认用包内示例用例）")
    parser.add_argument("--sheet", default=None, help="Excel 用例的 sheet 名（.xlsx 时可用）")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_FILE),
                        help="Markdown 报告输出路径（默认 ./batch_report.md）")
    parser.add_argument("--config", default=None,
                        help="配置文件路径（默认依次查找 ./config/config.yaml、./config.yaml）")
    parser.add_argument("--model", default=None, help="覆盖 config 里的 agent.model")
    parser.add_argument("--max-steps", type=int, default=20, help="每条用例最大步数（默认 20）")
    parser.add_argument("--max-retries", type=int, default=3, help="每条用例连续失败上限（默认 3）")
    parser.add_argument("--headless", dest="headless", action="store_true", default=None,
                        help="强制无头模式")
    parser.add_argument("--headed", dest="headless", action="store_false",
                        help="强制有头模式（可见浏览器）")
    parser.add_argument("--parse-only", action="store_true",
                        help="只解析用例并打印概要，不启动浏览器")
    parser.add_argument("--verbose", action="store_true", help="输出 DEBUG 日志")
    return parser


def find_config(explicit: Optional[str]) -> Optional[Path]:
    """定位配置文件：显式指定优先，否则按 CONFIG_CANDIDATES 顺序查找"""
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    for candidate in CONFIG_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _case_summary(case: TestCase) -> str:
    """用例概要（模式、步数、断言数）"""
    if case.actions:
        mode = "确定性(actions)"
    else:
        mode = "LLM 规划"
    parts = [f"模式={mode}"]
    if case.actions:
        parts.append(f"actions={len(case.actions)}")
    if case.assertions:
        parts.append(f"assertions={len(case.assertions)}")
    if case.setup_url:
        parts.append(f"setup={case.setup_url}")
    parts.append(f"timeout={case.timeout}s")
    return "，".join(parts)


def print_case_overview(cases: List[TestCase]) -> None:
    """打印用例概览（--parse-only 与正式运行都会调用）"""
    print(f"[INFO] 共解析到 {len(cases)} 条用例：")
    for index, case in enumerate(cases, 1):
        print(f"  {index}. {case.id}  {case.name}")
        print(f"     {_case_summary(case)}")


def print_batch_result(result) -> None:
    """打印逐条结果：状态 / 执行模式 / 耗时 / 断言 / 审计技能 / 失败原因"""
    print("\n========== 逐条结果 ==========")
    for case_result in result.case_results:
        status = "PASS" if case_result.success else "FAIL"
        assertions = case_result.assertions or []
        assertion_passed = sum(1 for item in assertions if item.get("success"))

        if case_result.fallback_used:
            mode = "确定性失败→回退 LLM"
        elif case_result.mode == "deterministic":
            source = {
                "case": "用例声明 actions",
                "replay": "录制回放",
            }.get(case_result.actions_source, "actions")
            mode = f"确定性({source})"
        else:
            mode = "LLM 规划"

        line = (
            f"  [{status}] {case_result.test_case_id} {case_result.test_case_name}"
            f" | {mode} | {case_result.duration:.1f}s"
            f" | 断言 {assertion_passed}/{len(assertions)}"
            f" | 步数 {len(case_result.steps_executed)}"
        )
        if case_result.retry_count:
            line += f" | 重跑 {case_result.retry_count}"
        print(line)

        if case_result.audited_skills:
            print(f"        使用了 audit 技能（会绕过真实 UI，已披露）: {', '.join(case_result.audited_skills)}")
        if case_result.recorded_actions_path:
            print(f"        已录制动作: {case_result.recorded_actions_path}")
        if not case_result.success:
            print(f"        失败原因: {case_result.failure_reason or case_result.message}")


async def run_batch(
    args: argparse.Namespace,
    config: Dict[str, Any],
    config_path: Path,
    case_file: Path,
    report_file: Path,
    cases: List[TestCase],
) -> int:
    """启动浏览器 → 批量执行 → 打印结果 → 生成 Markdown 报告"""
    browser_config = config.get("browser", {}) or {}
    viewport = browser_config.get("window_size", {}) or {}
    headless = args.headless if args.headless is not None else bool(browser_config.get("headless", True))

    print(f"[INFO] 配置文件: {config_path}")
    print(f"[INFO] 用例文件: {case_file}")
    print(f"[INFO] 报告路径: {report_file}")
    print(f"[INFO] 浏览器: type={browser_config.get('browser_type', 'chromium')} headless={headless}")

    launcher = BrowserLauncher(
        headless=headless,
        viewport={"width": viewport.get("width", 1920), "height": viewport.get("height", 1080)},
        browser_type=browser_config.get("browser_type", "chromium"),
        executable_path=browser_config.get("executable_path"),
        user_agent=USER_AGENT,
        disable_automation=True,
        # 让 config.yaml 的 browser.timeout 对页面操作生效
        default_timeout=browser_config.get("timeout"),
    )

    context = await launcher.launch()
    try:
        manager = create_manager(browser_context=context, config=config)
        agent = BatchTestAgent(
            skill_manager=manager,
            llm_client=None,            # 不传则用 config 的 agent 段创建（model/api_key/base_url）
            model=args.model,           # None 时同样回落到 config
            max_steps_per_case=args.max_steps,
            max_retries_per_case=args.max_retries,
            screenshot_on_failure=True,
        )
        if agent.llm is None:
            print(
                "[WARN] 未配置可用的 LLM 客户端（检查 config.agent.api_key / base_url）："
                "声明了 actions 的用例仍可确定性执行，需要 LLM 规划的用例会失败"
            )
        result = await agent.execute_batch(cases)
    finally:
        await launcher.close()

    report_file.parent.mkdir(parents=True, exist_ok=True)
    result.generate_report(str(report_file))
    print_batch_result(result)

    print("\n========== 汇总 ==========")
    print(
        f"总计: {result.total}  通过: {result.passed}  失败: {result.failed}"
        f"  通过率: {result.pass_rate:.1f}%  耗时: {result.duration:.1f}s"
    )
    print(f"报告已写入: {report_file}")
    if result.stop_reason:
        print(f"[WARN] 提前停止: {result.stop_reason}")

    return 0 if result.failed == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    # 控制台可能是不支持 emoji 的编码（如 Windows GBK）：只兜底编码错误、保留原生编码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:  # pragma: no cover - 老版本解释器/特殊流兜底
            pass

    args = build_parser().parse_args(argv)

    # ① 解析用例（--parse-only 到此为止：不启动浏览器、也不需要配置）
    case_file = Path(args.cases).expanduser().resolve()
    if not case_file.exists():
        print(f"[ERROR] 用例文件不存在: {case_file}")
        return 2
    try:
        cases = TestCaseParser.from_file(str(case_file), sheet_name=args.sheet)
    except Exception as e:
        print(f"[ERROR] 解析用例文件失败: {e}")
        return 2
    if not cases:
        print("[ERROR] 用例文件里没有解析到任何用例")
        return 2

    print_case_overview(cases)
    if args.parse_only:
        print("[INFO] --parse-only：仅解析用例，未启动浏览器")
        return 0

    # ② 配置
    config_path = find_config(args.config)
    if config_path is None:
        print("[ERROR] 找不到配置文件，请任选其一：")
        print("        1) 从包内模板复制到 ./config/config.yaml：")
        print("           python -c \"import shutil, pathlib, browser_automation_skills as b; "
              "shutil.copy(pathlib.Path(b.__file__).parent / 'config.template.yaml', 'config/config.yaml')\"")
        print("        2) 用 --config <path> 指定配置文件")
        return 2

    config = load_config(config_path)
    log_config = config.get("logging", {}) or {}
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else log_config.get("level", "INFO"),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
    )

    # ③ 执行 + 出报告
    report_file = Path(args.report).expanduser().resolve()
    try:
        return asyncio.run(
            run_batch(args, config, config_path, case_file, report_file, cases)
        )
    except KeyboardInterrupt:  # pragma: no cover - 交互式中断
        print("\n[WARN] 已被用户中断")
        return 130
    except Exception as e:
        print(f"[ERROR] 执行失败: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


