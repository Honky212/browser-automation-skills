# -*- coding: utf-8 -*-
"""产物路径路由测试：允许根校验、截图目录解析、报告路径、批量入口路由。

全部为纯单元测试：不启动浏览器、不调用 LLM、不访问网络。
"""

import inspect
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from browser_automation_skills.agent import (
    BatchTestAgent,
    BatchTestResult,
    ExecuteBatchTestCasesSkill,
)
from browser_automation_skills.base import (
    ArtifactPathError,
    ensure_within_roots,
    is_within_roots,
    normalize_abs_path,
    resolve_allowed_roots,
)
from browser_automation_skills.browser_skills import ScreenshotSkill


def _real(path) -> str:
    """与实现保持一致的规范化比较基准。"""
    return os.path.realpath(str(path))


# ============================================================
# 1. 允许根解析
# ============================================================

class TestResolveAllowedRoots:

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        roots = resolve_allowed_roots({})
        assert roots == [_real(tmp_path)]

    def test_config_roots_resolve_relative_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        roots = resolve_allowed_roots({"artifact_routing": {"allowed_roots": [".", "sub"]}})
        assert _real(tmp_path) in roots
        assert _real(tmp_path / "sub") in roots

    def test_absolute_output_dir_keeps_working_as_root(self, tmp_path, monkeypatch):
        """既有「绝对路径 output_dir」配置不能因为加校验而失效。"""
        workdir = tmp_path / "work"
        render_dir = tmp_path / "render"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        roots = resolve_allowed_roots({"screenshot": {"output_dir": str(render_dir)}})
        assert _real(render_dir) in roots

    def test_absolute_record_dir_keeps_working_as_root(self, tmp_path, monkeypatch):
        workdir = tmp_path / "work"
        record_dir = tmp_path / "records"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        roots = resolve_allowed_roots({"agent": {"record_dir": str(record_dir)}})
        assert _real(record_dir) in roots

    def test_relative_output_dir_adds_no_extra_root(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        roots = resolve_allowed_roots({"screenshot": {"output_dir": "./screenshots"}})
        assert roots == [_real(tmp_path)]


# ============================================================
# 2. 归属判定
# ============================================================

class TestIsWithinRoots:

    def test_inside_and_equal_are_allowed(self, tmp_path):
        root = str(tmp_path)
        assert is_within_roots(str(tmp_path / "a" / "b"), [root]) is True
        assert is_within_roots(root, [root]) is True

    def test_parent_escape_is_rejected(self, tmp_path):
        project = tmp_path / "project-1"
        project.mkdir()
        assert is_within_roots(str(project / ".."), [str(project)]) is False

    def test_dotdot_escape_is_rejected(self, tmp_path):
        project = tmp_path / "project-1"
        project.mkdir()
        assert is_within_roots(str(project / ".." / "elsewhere"), [str(project)]) is False

    def test_other_drive_is_rejected(self, tmp_path):
        if os.name != "nt":
            pytest.skip("仅 Windows 存在盘符差异")
        assert is_within_roots(r"C:\Windows\Temp\probe.png", [str(tmp_path)]) is False

    def test_no_roots_rejects(self, tmp_path):
        assert is_within_roots(str(tmp_path), []) is False


class TestNormalizeAndEnsure:

    def test_normalize_relative_uses_base_dir(self, tmp_path):
        assert normalize_abs_path("a/b", str(tmp_path)) == _real(tmp_path / "a" / "b")

    def test_ensure_returns_resolved_path_inside(self, tmp_path):
        project = tmp_path / "project-1"
        project.mkdir()
        assert ensure_within_roots(
            str(project / "screenshots"), [str(project)], label="output_dir"
        ) == _real(project / "screenshots")

    def test_ensure_raises_artifact_path_error_outside(self, tmp_path):
        project = tmp_path / "project-1"
        project.mkdir()
        with pytest.raises(ArtifactPathError):
            ensure_within_roots(str(tmp_path / "outside"), [str(project)], label="output_dir")

    def test_artifact_path_error_is_value_error(self):
        assert issubclass(ArtifactPathError, ValueError)


# ============================================================
# 3. screenshot 技能的输出目录
# ============================================================

def _screenshot_skill(mock_browser_context, mock_page, config=None):
    manager = MagicMock()
    manager.config = {} if config is None else config
    return ScreenshotSkill(
        browser_context=mock_browser_context, page=mock_page, manager=manager
    )


class TestScreenshotOutputDir:

    def test_without_output_dir_uses_config_relative_to_cwd(
        self, tmp_path, monkeypatch, mock_browser_context, mock_page
    ):
        monkeypatch.chdir(tmp_path)
        skill = _screenshot_skill(
            mock_browser_context, mock_page,
            {"screenshot": {"output_dir": "./screenshots"}},
        )
        assert os.path.normcase(skill._resolve_screenshot_dir()) == os.path.normcase(
            _real(tmp_path / "screenshots")
        )

    def test_without_config_falls_back_to_default_dir(
        self, mock_browser_context, mock_page
    ):
        from browser_automation_skills.browser_skills import DEFAULT_SCREENSHOT_DIR
        skill = _screenshot_skill(mock_browser_context, mock_page, {})
        assert os.path.normcase(skill._resolve_screenshot_dir()) == os.path.normcase(
            DEFAULT_SCREENSHOT_DIR
        )

    def test_explicit_output_dir_takes_precedence(
        self, tmp_path, monkeypatch, mock_browser_context, mock_page
    ):
        monkeypatch.chdir(tmp_path)
        skill = _screenshot_skill(
            mock_browser_context, mock_page,
            {"screenshot": {"output_dir": "./screenshots"}},
        )
        target = tmp_path / "project-1" / "screenshots"
        assert os.path.normcase(skill._resolve_screenshot_dir(str(target))) == os.path.normcase(
            _real(target)
        )

    def test_explicit_output_dir_outside_roots_raises(
        self, tmp_path, monkeypatch, mock_browser_context, mock_page
    ):
        workdir = tmp_path / "work"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        skill = _screenshot_skill(mock_browser_context, mock_page, {})
        with pytest.raises(ArtifactPathError):
            skill._resolve_screenshot_dir(str(tmp_path / "outside"))

    async def test_run_returns_real_path_inside_output_dir(
        self, tmp_path, monkeypatch, mock_browser_context, mock_page
    ):
        monkeypatch.chdir(tmp_path)
        skill = _screenshot_skill(mock_browser_context, mock_page, {})
        target = tmp_path / "project-1" / "screenshots"

        result = await skill.run(path="./shot.png", output_dir=str(target))

        assert result.success is True
        expected = os.path.join(_real(target), "shot.png")
        assert os.path.normcase(result.data["path"]) == os.path.normcase(expected)
        assert target.exists()

    async def test_run_rejects_output_dir_outside_roots(
        self, tmp_path, monkeypatch, mock_browser_context, mock_page
    ):
        workdir = tmp_path / "work"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        skill = _screenshot_skill(mock_browser_context, mock_page, {})
        outside = tmp_path / "outside"

        result = await skill.run(path="shot.png", output_dir=str(outside))

        assert result.success is False
        assert "output_dir" in result.message
        # 越界时不得创建目录、不得写文件
        assert not outside.exists()


# ============================================================
# 4. 报告写入
# ============================================================

class TestGenerateReport:

    def test_creates_parent_dir_and_appends_md(self, tmp_path):
        result = BatchTestResult(total=1, passed=1)
        content = result.generate_report(str(tmp_path / "reports" / "run"))

        written = tmp_path / "reports" / "run.md"
        assert "# 批量测试报告" in content
        assert written.exists()
        assert written.read_text(encoding="utf-8") == content
        assert result.report_path == str(written)

    def test_keeps_explicit_md_suffix(self, tmp_path):
        result = BatchTestResult()
        result.generate_report(str(tmp_path / "r.md"))
        assert (tmp_path / "r.md").exists()
        assert result.report_path == str(tmp_path / "r.md")

    def test_without_path_only_returns_content(self):
        result = BatchTestResult()
        assert "# 批量测试报告" in result.generate_report()
        assert result.report_path is None

    def test_lists_failure_screenshots(self):
        from browser_automation_skills.agent import TestCaseResult

        shot = r"C:\proj\screenshots\TC_1_failure.png"
        case = TestCaseResult(
            test_case_id="TC_1", test_case_name="示例", success=False,
            message="failed", screenshots=[shot],
        )
        content = BatchTestResult(total=1, failed=1, case_results=[case]).generate_report()

        assert "## 失败截图" in content
        assert shot in content


# ============================================================
# 5. 批量入口产物路由
# ============================================================

def _write_cases(path: Path) -> None:
    path.write_text(
        json.dumps([{"id": "TC_1", "name": "示例", "steps": "打开页面"}], ensure_ascii=False),
        encoding="utf-8",
    )


def _batch_skill(config=None):
    manager = MagicMock()
    # 注入假 LLM 客户端：既不联网，也不要求安装 openai
    manager.config = {"llm_client": object()} if config is None else config
    return ExecuteBatchTestCasesSkill(browser_context=MagicMock(), manager=manager)


def _patch_execute_batch(monkeypatch, captured=None):
    """把 BatchTestAgent.execute_batch 换成假实现，记录收到的目录参数。"""
    async def fake_execute_batch(self, test_cases):
        if captured is not None:
            captured["called"] = True
            captured["screenshot_dir"] = self.screenshot_dir
            captured["record_dir"] = self.record_dir
            captured["case_count"] = len(test_cases)
        return BatchTestResult(total=len(test_cases), passed=len(test_cases))

    monkeypatch.setattr(BatchTestAgent, "execute_batch", fake_execute_batch)
    return captured


class TestBatchArtifactRouting:

    async def test_routes_artifacts_into_case_directory(self, tmp_path, monkeypatch):
        project = tmp_path / "project-1"
        project.mkdir()
        case_file = project / "test_cases.json"
        _write_cases(case_file)

        monkeypatch.chdir(tmp_path)
        captured = _patch_execute_batch(monkeypatch, {})
        skill = _batch_skill()

        result = await skill.run(file_path=str(case_file))

        assert result.success is True
        assert captured["case_count"] == 1
        assert os.path.normcase(captured["screenshot_dir"]) == os.path.normcase(
            os.path.join(_real(project), "screenshots")
        )
        assert os.path.normcase(captured["record_dir"]) == os.path.normcase(
            os.path.join(_real(project), "recorded_actions")
        )
        assert os.path.normcase(result.data["artifact_root"]) == os.path.normcase(_real(project))
        assert os.path.normcase(result.data["screenshot_dir"]) == os.path.normcase(
            os.path.join(_real(project), "screenshots")
        )

    async def test_default_report_is_unique_md_under_project_reports(self, tmp_path, monkeypatch):
        project = tmp_path / "project-1"
        project.mkdir()
        case_file = project / "test_cases.json"
        _write_cases(case_file)
        monkeypatch.chdir(tmp_path)
        _patch_execute_batch(monkeypatch)
        skill = _batch_skill()

        first = await skill.run(file_path=str(case_file))
        second = await skill.run(file_path=str(case_file))

        reports = [Path(first.data["report_path"]), Path(second.data["report_path"])]
        for report in reports:
            assert report.suffix == ".md"
            assert report.exists()
            assert report.parent.name == "reports"
            assert os.path.normcase(str(report.parent.parent)) == os.path.normcase(_real(project))
        assert reports[0] != reports[1]

    async def test_explicit_report_path_appends_md_and_creates_parent(self, tmp_path, monkeypatch):
        project = tmp_path / "project-1"
        project.mkdir()
        case_file = project / "test_cases.json"
        _write_cases(case_file)
        monkeypatch.chdir(tmp_path)
        _patch_execute_batch(monkeypatch)
        skill = _batch_skill()

        target = project / "custom" / "my_report"
        result = await skill.run(file_path=str(case_file), report_path=str(target))

        assert result.data["report_path"] == str(target) + ".md"
        assert (project / "custom" / "my_report.md").exists()

    async def test_honors_explicit_artifact_root(self, tmp_path, monkeypatch):
        _write_cases(tmp_path / "test_cases.json")
        out = tmp_path / "artifacts"
        monkeypatch.chdir(tmp_path)
        captured = _patch_execute_batch(monkeypatch, {})
        skill = _batch_skill()

        result = await skill.run(file_path="test_cases.json", artifact_root=str(out))

        assert os.path.normcase(result.data["artifact_root"]) == os.path.normcase(_real(out))
        assert os.path.normcase(captured["screenshot_dir"]) == os.path.normcase(
            os.path.join(_real(out), "screenshots")
        )
        assert Path(result.data["report_path"]).parent == out / "reports"

    async def test_relative_case_path_resolves_against_cwd(self, tmp_path, monkeypatch):
        _write_cases(tmp_path / "test_cases.json")
        monkeypatch.chdir(tmp_path)
        _patch_execute_batch(monkeypatch)
        skill = _batch_skill()

        result = await skill.run(file_path="test_cases.json")

        assert result.success is True
        assert os.path.normcase(result.data["artifact_root"]) == os.path.normcase(_real(tmp_path))

    async def test_rejects_case_file_outside_workspace(self, tmp_path, monkeypatch):
        workdir = tmp_path / "work"
        workdir.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        case_file = outside / "test_cases.json"
        _write_cases(case_file)
        monkeypatch.chdir(workdir)
        captured = _patch_execute_batch(monkeypatch, {})
        skill = _batch_skill()

        result = await skill.run(file_path=str(case_file))

        assert result.success is False
        assert "file_path" in result.message
        assert captured.get("called") is None          # 未启动 Agent
        assert not (outside / "screenshots").exists()  # 未创建任何产物目录
        assert not (outside / "reports").exists()

    async def test_rejects_report_path_outside_workspace(self, tmp_path, monkeypatch):
        workdir = tmp_path / "work"
        workdir.mkdir()
        _write_cases(workdir / "test_cases.json")
        monkeypatch.chdir(workdir)
        captured = _patch_execute_batch(monkeypatch, {})
        skill = _batch_skill()

        result = await skill.run(
            file_path="test_cases.json",
            report_path=str(tmp_path / "outside" / "r.md"),
        )

        assert result.success is False
        assert "report_path" in result.message
        assert captured.get("called") is None
        # 报告路径校验发生在 BatchTestAgent 构造之前，因此不应留下任何目录
        assert not (workdir / "screenshots").exists()
        assert not (tmp_path / "outside").exists()

    async def test_missing_case_file_returns_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _patch_execute_batch(monkeypatch)
        skill = _batch_skill()

        result = await skill.run(file_path="not_exists.json")

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_new_params_stay_optional_for_mcp_schema(self):
        batch_sig = inspect.signature(ExecuteBatchTestCasesSkill.run)
        assert batch_sig.parameters["file_path"].default is inspect.Parameter.empty
        assert batch_sig.parameters["artifact_root"].default is None
        assert batch_sig.parameters["report_path"].default is None

        shot_sig = inspect.signature(ScreenshotSkill.run)
        assert shot_sig.parameters["output_dir"].default is None
        assert shot_sig.parameters["path"].default is None

