"""
测试报告模块 - 生成 HTML 测试报告和可视化统计
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TestStepResult:
    """测试步骤结果"""
    step_number: int
    skill_name: str
    success: bool
    message: str
    execution_time: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    screenshot: Optional[str] = None  # base64
    error: Optional[str] = None


@dataclass
class TestCaseResult:
    """测试用例结果"""
    test_name: str
    test_file: str
    success: bool
    total_steps: int
    passed_steps: int
    failed_steps: int
    skipped_steps: int
    total_time: float
    steps: List[TestStepResult] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: str = ""
    screenshot_path: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TestReporter:
    """
    测试报告生成器

    功能：
    - 收集测试结果
    - 生成 HTML 报告
    - 生成 JSON 报告
    - 统计信息
    """

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        self.results: List[TestCaseResult] = []
        self.start_time = time.time()

    def add_result(self, result: TestCaseResult):
        """添加测试结果"""
        self.results.append(result)

    def add_chain_result(self, test_name: str, test_file: str,
                         chain_results: List, total_time: float = 0.0,
                         error_message: Optional[str] = None, screenshot_path: Optional[str] = None) -> TestCaseResult:
        """
        从 Skill 链执行结果创建 TestCaseResult

        Args:
            test_name: 测试名称
            test_file: 测试文件
            chain_results: execute_chain 返回的结果列表
            total_time: 总执行时间
            error_message: 错误信息
            screenshot_path: 截图路径
        """
        steps = []
        passed = 0
        failed = 0

        for i, result in enumerate(chain_results):
            step = TestStepResult(
                step_number=i + 1,
                skill_name=result.data.get("skill", "unknown") if result.data else "unknown",
                success=result.success,
                message=result.message,
                execution_time=result.execution_time,
                data=result.data or {},
                error=result.error
            )
            steps.append(step)
            if result.success:
                passed += 1
            else:
                failed += 1

        case_result = TestCaseResult(
            test_name=test_name,
            test_file=test_file,
            success=failed == 0,
            total_steps=len(steps),
            passed_steps=passed,
            failed_steps=failed,
            skipped_steps=0,
            total_time=total_time,
            steps=steps,
            error_message=error_message,
            screenshot_path=screenshot_path
        )
        self.add_result(case_result)
        return case_result

    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        total_time = sum(r.total_time for r in self.results)
        total_steps = sum(r.total_steps for r in self.results)
        passed_steps = sum(r.passed_steps for r in self.results)
        failed_steps = sum(r.failed_steps for r in self.results)

        return {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": failed,
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "total_time": total_time,
            "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def generate_html_report(self, filename: str = "test_report.html") -> str:
        """
        生成 HTML 测试报告

        Args:
            filename: 报告文件名

        Returns:
            报告文件完整路径
        """
        os.makedirs(self.output_dir, exist_ok=True)
        filepath = os.path.join(self.output_dir, filename)
        summary = self.get_summary()

        html = self._build_html_report(summary)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        return filepath

    def generate_json_report(self, filename: str = "test_report.json") -> str:
        """生成 JSON 测试报告"""
        os.makedirs(self.output_dir, exist_ok=True)
        filepath = os.path.join(self.output_dir, filename)

        report = {
            "summary": self.get_summary(),
            "test_cases": [
                {
                    "test_name": r.test_name,
                    "test_file": r.test_file,
                    "success": r.success,
                    "total_steps": r.total_steps,
                    "passed_steps": r.passed_steps,
                    "failed_steps": r.failed_steps,
                    "total_time": r.total_time,
                    "timestamp": r.timestamp,
                    "error_message": r.error_message,
                    "steps": [
                        {
                            "step_number": s.step_number,
                            "skill_name": s.skill_name,
                            "success": s.success,
                            "message": s.message,
                            "execution_time": s.execution_time,
                            "error": s.error
                        }
                        for s in r.steps
                    ]
                }
                for r in self.results
            ]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return filepath

    def _build_html_report(self, summary: Dict) -> str:
        """构建 HTML 报告内容"""
        # 计算通过率颜色
        pass_rate = summary["pass_rate"]
        pass_rate_num = float(pass_rate.replace("%", ""))
        if pass_rate_num >= 90:
            pass_rate_color = "#28a745"
        elif pass_rate_num >= 70:
            pass_rate_color = "#ffc107"
        else:
            pass_rate_color = "#dc3545"

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Browser-Automation-Skills 测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
        .card .number {{ font-size: 36px; font-weight: bold; margin: 10px 0; }}
        .card .label {{ color: #666; font-size: 14px; }}
        .card.passed .number {{ color: #28a745; }}
        .card.failed .number {{ color: #dc3545; }}
        .card.total .number {{ color: #667eea; }}
        .card.time .number {{ color: #17a2b8; }}
        .card.rate .number {{ color: {pass_rate_color}; }}
        .test-case {{ background: white; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .test-case-header {{ padding: 15px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
        .test-case-header.passed {{ background: #d4edda; border-left: 4px solid #28a745; }}
        .test-case-header.failed {{ background: #f8d7da; border-left: 4px solid #dc3545; }}
        .test-case-header .name {{ font-weight: bold; font-size: 16px; }}
        .test-case-header .status {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
        .test-case-header.passed .status {{ background: #28a745; color: white; }}
        .test-case-header.failed .status {{ background: #dc3545; color: white; }}
        .test-case-body {{ display: none; padding: 20px; }}
        .test-case-body.show {{ display: block; }}
        .step {{ display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #eee; }}
        .step:last-child {{ border-bottom: none; }}
        .step .step-num {{ width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; margin-right: 10px; }}
        .step.passed .step-num {{ background: #28a745; color: white; }}
        .step.failed .step-num {{ background: #dc3545; color: white; }}
        .step .step-info {{ flex: 1; }}
        .step .step-name {{ font-weight: bold; }}
        .step .step-msg {{ color: #666; font-size: 13px; }}
        .step .step-time {{ color: #999; font-size: 12px; margin-left: 10px; }}
        .progress-bar {{ height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden; margin: 10px 0; }}
        .progress-bar .fill {{ height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.3s; }}
        .error-msg {{ background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; margin-top: 10px; font-family: monospace; white-space: pre-wrap; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 14px; }}
        .toggle-btn {{ background: none; border: none; cursor: pointer; font-size: 18px; transition: transform 0.3s; }}
        .toggle-btn.open {{ transform: rotate(180deg); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Browser-Automation-Skills 测试报告</h1>
            <p>生成时间: {summary['timestamp']}</p>
        </div>

        <div class="summary-cards">
            <div class="card total">
                <div class="label">总测试数</div>
                <div class="number">{summary['total_tests']}</div>
            </div>
            <div class="card passed">
                <div class="label">通过</div>
                <div class="number">{summary['passed_tests']}</div>
            </div>
            <div class="card failed">
                <div class="label">失败</div>
                <div class="number">{summary['failed_tests']}</div>
            </div>
            <div class="card rate">
                <div class="label">通过率</div>
                <div class="number">{summary['pass_rate']}</div>
            </div>
            <div class="card time">
                <div class="label">总耗时</div>
                <div class="number">{summary['total_time']:.2f}s</div>
            </div>
        </div>

        <div class="progress-bar">
            <div class="fill" style="width: {pass_rate_num}%"></div>
        </div>

        <div class="test-cases">
"""
        for result in self.results:
            status_class = "passed" if result.success else "failed"
            status_text = "PASSED" if result.success else "FAILED"

            html += f"""
            <div class="test-case">
                <div class="test-case-header {status_class}" onclick="toggleTestCase(this)">
                    <div>
                        <span class="name">{result.test_name}</span>
                        <span style="color: #666; font-size: 13px; margin-left: 10px;">{result.test_file}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 13px; color: #666;">
                            {result.passed_steps}✓ {result.failed_steps}✗ | {result.total_time:.2f}s
                        </span>
                        <span class="status">{status_text}</span>
                        <button class="toggle-btn">▼</button>
                    </div>
                </div>
                <div class="test-case-body">
"""
            for step in result.steps:
                step_class = "passed" if step.success else "failed"
                html += f"""
                    <div class="step {step_class}">
                        <div class="step-num">{step.step_number}</div>
                        <div class="step-info">
                            <div class="step-name">{step.skill_name}</div>
                            <div class="step-msg">{step.message}</div>
                        </div>
                        <div class="step-time">{step.execution_time:.2f}s</div>
                    </div>
"""
            if result.error_message:
                html += f'<div class="error-msg">{result.error_message}</div>'

            html += """
                </div>
            </div>
"""

        html += f"""
        </div>

        <div class="footer">
            <p>Browser-Automation-Skills Test Reporter | Generated at {summary['timestamp']}</p>
        </div>
    </div>

    <script>
        function toggleTestCase(header) {{
            const body = header.nextElementSibling;
            const btn = header.querySelector('.toggle-btn');
            body.classList.toggle('show');
            btn.classList.toggle('open');
        }}
    </script>
</body>
</html>"""

        return html

    def print_summary(self):
        """打印测试摘要到控制台"""
        summary = self.get_summary()
        print("\n" + "=" * 60)
        print("📊 测试报告摘要")
        print("=" * 60)
        print(f"  总测试数:   {summary['total_tests']}")
        print(f"  通过:       {summary['passed_tests']}")
        print(f"  失败:       {summary['failed_tests']}")
        print(f"  通过率:     {summary['pass_rate']}")
        print(f"  总步骤数:   {summary['total_steps']} (通过: {summary['passed_steps']}, 失败: {summary['failed_steps']})")
        print(f"  总耗时:     {summary['total_time']:.2f}s")
        print("=" * 60)

    def save_all_reports(self, base_name: str = "test_report") -> Dict[str, str]:
        """
        保存所有格式报告

        Returns:
            报告文件路径字典
        """
        files = {}
        files["html"] = self.generate_html_report(f"{base_name}.html")
        files["json"] = self.generate_json_report(f"{base_name}.json")
        return files