"""examples/batch_run_example.py 的冒烟测试（不启动浏览器、不调用 LLM）"""

from pathlib import Path

from browser_automation_skills.examples import batch_run_example as example


class TestArgParsing:

    def test_defaults_point_to_bundled_case_file(self):
        args = example.build_parser().parse_args([])
        assert Path(args.cases).exists(), "默认用例文件应随包发布"
        assert "structured_actions_demo" in args.cases
        assert args.max_steps == 20
        assert args.max_retries == 3
        assert args.headless is None, "未指定时应回落到 config 的 headless"

    def test_headless_flags(self):
        assert example.build_parser().parse_args(["--headless"]).headless is True
        assert example.build_parser().parse_args(["--headed"]).headless is False


class TestConfigLookup:

    def test_find_config_priority(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert example.find_config(None) is None

        (tmp_path / "config.yaml").write_text("agent: {}\n", encoding="utf-8")
        assert example.find_config(None) == Path("config.yaml")

        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "config.yaml").write_text("agent: {}\n", encoding="utf-8")
        # ./config/config.yaml 优先于 ./config.yaml
        assert example.find_config(None) == Path("config") / "config.yaml"

    def test_explicit_config_missing_returns_none(self, tmp_path):
        assert example.find_config(str(tmp_path / "nope.yaml")) is None


class TestParseOnly:

    def test_parse_only_with_bundled_cases(self, capsys):
        """--parse-only：解析包内默认用例并打印概要，退出码 0"""
        code = example.main(["--parse-only"])
        out = capsys.readouterr().out

        assert code == 0
        assert "确定性(actions)" in out
        assert "TC_DET_01" in out
        assert "未启动浏览器" in out

    def test_missing_case_file(self, tmp_path, capsys):
        code = example.main(["--cases", str(tmp_path / "nope.yaml")])
        assert code == 2
        assert "用例文件不存在" in capsys.readouterr().out

    def test_invalid_case_file(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not-a-list: 1\n", encoding="utf-8")

        code = example.main(["--cases", str(bad)])

        assert code == 2
        assert "解析用例文件失败" in capsys.readouterr().out
