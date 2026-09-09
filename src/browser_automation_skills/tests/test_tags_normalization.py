"""测试 TestCaseParser._normalize_tags（对应问题 #12 修复）"""

import pytest
import json

from browser_automation_skills.agent import TestCaseParser


class TestNormalizeTags:
    """_normalize_tags 类型转换测试"""

    def test_none_returns_empty_list(self):
        """None → []"""
        assert TestCaseParser._normalize_tags(None) == []

    def test_empty_string_returns_empty_list(self):
        """空字符串 → []"""
        assert TestCaseParser._normalize_tags("") == []

    def test_single_tag_string(self):
        """单个标签字符串 → 单元素 list"""
        assert TestCaseParser._normalize_tags("登录") == ["登录"]

    def test_comma_separated(self):
        """逗号分隔（英文）"""
        assert TestCaseParser._normalize_tags("登录,注册,注销") == ["登录", "注册", "注销"]

    def test_chinese_comma_separated(self):
        """中文逗号分隔"""
        assert TestCaseParser._normalize_tags("登录，注册，注销") == ["登录", "注册", "注销"]

    def test_semicolon_separated(self):
        """分号分隔（中英文）"""
        assert TestCaseParser._normalize_tags("登录;注册；注销") == ["登录", "注册", "注销"]

    def test_pipe_separated(self):
        """竖线分隔"""
        assert TestCaseParser._normalize_tags("登录|注册") == ["登录", "注册"]

    def test_list_input_passthrough(self):
        """list 输入直接处理"""
        result = TestCaseParser._normalize_tags(["登录", "注册"])
        assert result == ["登录", "注册"]

    def test_list_with_none_elements(self):
        """list 含 None/空元素时过滤"""
        result = TestCaseParser._normalize_tags(["登录", None, "", "注册"])
        assert result == ["登录", "注册"]

    def test_mixed_separators(self):
        """混合分隔符"""
        assert TestCaseParser._normalize_tags("登录,注册；注销|退出") == ["登录", "注册", "注销", "退出"]

    def test_whitespace_trimmed(self):
        """前后空格被去除"""
        assert TestCaseParser._normalize_tags(" 登录 , 注册 ") == ["登录", "注册"]

    def test_int_input(self):
        """非字符串/非 list 类型 → 单元素 list"""
        assert TestCaseParser._normalize_tags(123) == ["123"]


class TestFromJsonTags:
    """from_json 中 tags 处理测试"""

    def _write_and_parse(self, data, tmp_path):
        """写入临时 JSON 文件并解析"""
        file_path = str(tmp_path / "test_tags.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return TestCaseParser.from_json(file_path)

    def test_json_string_tags(self, tmp_path):
        """JSON 中 tags 为字符串时正确分割"""
        data = [{"id": "TC1", "name": "test", "tags": "登录,注册,注销"}]
        cases = self._write_and_parse(data, tmp_path)
        assert cases[0].tags == ["登录", "注册", "注销"]

    def test_json_list_tags(self, tmp_path):
        """JSON 中 tags 为 list 时正常处理"""
        data = [{"id": "TC1", "name": "test", "tags": ["登录", "注册"]}]
        cases = self._write_and_parse(data, tmp_path)
        assert cases[0].tags == ["登录", "注册"]

    def test_json_no_tags(self, tmp_path):
        """JSON 中无 tags 字段时返回空 list"""
        data = [{"id": "TC1", "name": "test"}]
        cases = self._write_and_parse(data, tmp_path)
        assert cases[0].tags == []
