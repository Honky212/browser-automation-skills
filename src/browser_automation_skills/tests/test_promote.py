"""promote 工具测试（录制 → 用例 YAML 固化）"""

import os

import yaml

from browser_automation_skills.promote import (
    _block_to_text,
    _upsert_field,
    main,
    promote_recorded_actions,
)

CASE_TEMPLATE = """# 顶部注释必须保留
- id: TC_01
  name: 百度首页打开测试
  steps: |
    打开百度首页并验证标题
  expected_result: 标题包含百度
  priority: high
  setup_url: https://www.baidu.com
  timeout: 30

# 中间注释也必须保留
- id: TC_02
  name: 百度搜索
  steps: 搜索关键词
  timeout: 60
"""


def _write_case_file(tmp_path, text=CASE_TEMPLATE):
    path = tmp_path / "cases.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_recording(tmp_path, case_id, payload):
    record_dir = tmp_path / "recorded_actions"
    record_dir.mkdir(exist_ok=True)
    (record_dir / f"{case_id}.actions.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return str(record_dir)


# ============================================================
# 文本级字段插入/替换
# ============================================================

class TestUpsertField:

    def test_insert_into_case_block(self):
        lines = CASE_TEMPLATE.splitlines()
        new_lines, replaced = _upsert_field(
            lines, "TC_01", "actions", ["  actions:", "    - skill: navigate"]
        )
        assert replaced is False
        text = "\n".join(new_lines)
        # 插到 TC_01 块内、且 TC_02 仍在其后
        assert text.index("actions:") < text.index("# 中间注释也必须保留")
        # 其它字段与注释原样保留
        assert "# 顶部注释必须保留" in text
        assert "  timeout: 30" in text

    def test_replace_existing_field(self):
        text = (
            "- id: TC_01\n"
            "  name: t\n"
            "  actions:\n"
            "    - skill: old\n"
            "      params: {}\n"
            "  timeout: 30\n"
        )
        new_lines, replaced = _upsert_field(
            text.splitlines(), "TC_01", "actions", ["  actions:", "    - skill: new"]
        )
        assert replaced is True
        result = "\n".join(new_lines)
        assert "skill: old" not in result
        assert "skill: new" in result
        assert "timeout: 30" in result      # 后续字段未被吞掉

    def test_block_to_text_renders_params_and_anchor(self):
        block = _block_to_text([{
            "skill": "fill_by_index",
            "params": {"index": 13, "value": "自动化测试"},
            "anchor": {"element_id": "kw"},
        }], "actions")
        text = "\n".join(block)
        assert "  actions:" in text
        assert "value: 自动化测试" in text
        assert "anchor:" in text
        assert "element_id: kw" in text


# ============================================================
# 固化主流程
# ============================================================

class TestPromote:

    def test_promote_creates_actions_block(self, tmp_path):
        case_file = _write_case_file(tmp_path)
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01",
            "actions": [
                {"skill": "navigate", "params": {"url": "https://www.baidu.com"}},
                {"skill": "fill_by_index", "params": {"index": 13, "value": "x"},
                 "anchor": {"element_id": "kw"}},
            ],
        })

        result = promote_recorded_actions(case_file, record_dir=record_dir)

        assert result.promoted == 1
        data = yaml.safe_load(open(case_file, encoding="utf-8"))
        actions = data[0]["actions"]
        assert [a["skill"] for a in actions] == ["navigate", "fill_by_index"]
        assert actions[1]["anchor"]["element_id"] == "kw"
        # 保留注释 + 生成备份
        text = open(case_file, encoding="utf-8").read()
        assert "# 中间注释也必须保留" in text
        assert os.path.exists(case_file + ".bak")
        assert result.diff_text

    def test_no_recording_is_reported(self, tmp_path):
        case_file = _write_case_file(tmp_path)
        record_dir = str(tmp_path / "recorded_actions")
        os.makedirs(record_dir, exist_ok=True)

        result = promote_recorded_actions(case_file, record_dir=record_dir)

        assert result.promoted == 0
        assert {c.status for c in result.cases} == {"no_recording"}

    def test_skips_existing_actions_without_overwrite(self, tmp_path):
        case_file = _write_case_file(tmp_path, CASE_TEMPLATE.replace(
            "  timeout: 30\n", "  actions:\n    - skill: hand_written\n      params: {}\n  timeout: 30\n"
        ))
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01", "actions": [{"skill": "navigate", "params": {}}],
        })

        result = promote_recorded_actions(case_file, record_dir=record_dir)

        assert result.promoted == 0
        assert result.cases[0].status == "skipped_exists"
        assert not os.path.exists(case_file + ".bak")

    def test_overwrite_replaces_handwritten_actions(self, tmp_path):
        case_file = _write_case_file(tmp_path, CASE_TEMPLATE.replace(
            "  timeout: 30\n", "  actions:\n    - skill: hand_written\n      params: {}\n  timeout: 30\n"
        ))
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01", "actions": [{"skill": "navigate", "params": {"url": "https://x"}}],
        })

        result = promote_recorded_actions(case_file, record_dir=record_dir, overwrite=True)

        assert result.promoted == 1
        data = yaml.safe_load(open(case_file, encoding="utf-8"))
        assert [a["skill"] for a in data[0]["actions"]] == ["navigate"]
        assert "hand_written" not in open(case_file, encoding="utf-8").read()

    def test_dry_run_does_not_write(self, tmp_path):
        case_file = _write_case_file(tmp_path)
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01", "actions": [{"skill": "navigate", "params": {}}],
        })
        before = open(case_file, encoding="utf-8").read()

        result = promote_recorded_actions(case_file, record_dir=record_dir, dry_run=True)

        assert result.promoted == 1
        assert result.diff_text                     # 有 diff 可看
        assert open(case_file, encoding="utf-8").read() == before
        assert not os.path.exists(case_file + ".bak")

    def test_output_to_new_file_keeps_original(self, tmp_path):
        case_file = _write_case_file(tmp_path)
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01", "actions": [{"skill": "navigate", "params": {}}],
        })
        output = str(tmp_path / "cases.promoted.yaml")
        before = open(case_file, encoding="utf-8").read()

        result = promote_recorded_actions(case_file, record_dir=record_dir, output=output)

        assert result.promoted == 1
        assert open(case_file, encoding="utf-8").read() == before   # 原文件不动
        assert not os.path.exists(case_file + ".bak")
        assert os.path.exists(output)
        assert yaml.safe_load(open(output, encoding="utf-8"))[0]["actions"]

    def test_with_assertions_promotes_drafts(self, tmp_path):
        case_file = _write_case_file(tmp_path)
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01",
            "actions": [{"skill": "navigate", "params": {}}],
            "assertions": [
                {"skill": "title_contains", "params": {"expected": "百度"}},
            ],
        })

        result = promote_recorded_actions(
            case_file, record_dir=record_dir, with_assertions=True
        )

        assert result.promoted == 1
        assert result.cases[0].assertion_count == 1
        data = yaml.safe_load(open(case_file, encoding="utf-8"))
        assert data[0]["assertions"][0]["params"]["expected"] == "百度"

    def test_audited_js_step_is_kept_and_marked(self, tmp_path):
        """
        audit 技能（execute_js）**不会被跳过**，而是照常固化 + 加注释标注 + 汇总告警。
        （框架不禁用 execute_js：某些元素确实只能靠 JS 操作）
        """
        case_file = _write_case_file(tmp_path)
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01",
            "actions": [
                {"skill": "execute_js", "params": {"script": "document.querySelector('#su').click()"},
                 "audited": True},
                {"skill": "url_contains", "params": {"expected": "wd="}},
            ],
        })

        result = promote_recorded_actions(case_file, record_dir=record_dir)

        assert result.promoted == 1
        assert result.cases[0].audited_skills == ["execute_js"]

        text = open(case_file, encoding="utf-8").read()
        data = yaml.safe_load(text)
        # 步骤保留（没有被跳过）
        assert [a["skill"] for a in data[0]["actions"]] == ["execute_js", "url_contains"]
        # 有注释标注 + 汇总里有告警
        assert "audit 技能（execute_js）" in text
        summary = result.format_summary()
        assert "execute_js" in summary
        assert "audit" in summary

    def test_cli_dry_run_returns_zero(self, tmp_path, capsys):
        case_file = _write_case_file(tmp_path)
        record_dir = _write_recording(tmp_path, "TC_01", {
            "id": "TC_01", "actions": [{"skill": "navigate", "params": {}}],
        })

        code = main(["--cases", case_file, "--record-dir", record_dir, "--dry-run"])

        out = capsys.readouterr().out
        assert code == 0
        assert "promote 汇总" in out
        assert "dry-run" in out
        assert not os.path.exists(case_file + ".bak")


