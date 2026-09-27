# -*- coding: utf-8 -*-
"""
promote 工具 —— 把录制文件固化为用例 YAML 的 `actions` / `assertions`

背景：
    自然语言用例（模式 A）跑通后，框架会录制 `recorded_actions/<用例ID>.actions.yaml`。
    手工把录制内容抄进用例文件既繁琐又易错，本工具负责这一步（离线操作，不改变运行时语义）。

用法：
    python -m browser_automation_skills.promote --cases test_case/test_cases_baidu.yaml
    python -m browser_automation_skills.promote --cases <file> --with-assertions --dry-run
    python -m browser_automation_skills.promote --cases <file> --output <new_file>

设计要点：
    1. **不禁用任何技能**：录制里的 `execute_js` 等 audit 技能照常固化，
       只在 YAML 里加注释标注 + 在汇总里告警，是否保留由人工 review 决定；
    2. **文本级插入**：只替换/插入 `actions:`、`assertions:` 两个字段块，
       保留用例文件里其它字段、注释与排版（不整份重新序列化）；
    3. 默认写前备份（`<file>.bak`），`--dry-run` 只打印 diff。
"""

import argparse
import difflib
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

DEFAULT_RECORD_DIR = "./recorded_actions"
CASE_ITEM_RE = re.compile(r"^- id:\s*(?P<id>.+?)\s*$")
FIELD_RE_TEMPLATE = r"^(?P<indent>\s*){field}:"


@dataclass
class PromoteCaseResult:
    """单条用例的固化结果"""
    case_id: str
    status: str                     # promoted | skipped_exists | no_recording | error
    detail: str = ""
    action_count: int = 0
    assertion_count: int = 0
    audited_skills: List[str] = field(default_factory=list)


@dataclass
class PromoteResult:
    """一次固化的总体结果"""
    case_file: str
    output_file: str
    dry_run: bool
    cases: List[PromoteCaseResult] = field(default_factory=list)
    diff_text: str = ""

    @property
    def promoted(self) -> int:
        return sum(1 for c in self.cases if c.status == "promoted")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.status == "error")

    def format_summary(self) -> str:
        """生成控制台汇总文本"""
        lines = [
            f"用例文件: {self.case_file}",
            f"输出文件: {self.output_file}{'（dry-run，未写盘）' if self.dry_run else ''}",
            f"固化成功: {self.promoted} / 共扫描 {len(self.cases)} 条用例",
            "",
        ]
        icons = {
            "promoted": "✅",
            "skipped_exists": "⏭️ ",
            "no_recording": "➖",
            "error": "❌",
        }
        for item in self.cases:
            lines.append(
                f"{icons.get(item.status, '?')} {item.case_id}: {item.status}"
                f"（actions={item.action_count}, assertions={item.assertion_count}）"
                f"{' — ' + item.detail if item.detail else ''}"
            )
        audited = sorted({s for c in self.cases for s in c.audited_skills})
        if audited:
            lines.extend([
                "",
                f"⚠️ 固化内容包含 audit 技能（绕过 UI 的降级手段，允许使用，请 review 必要性）：{', '.join(audited)}",
                "   相关步骤已在 YAML 中加注释标注；框架不会替你禁用这些技能。",
            ])
        return "\n".join(lines)


def _load_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_recorded(record_path: str) -> Optional[Dict[str, Any]]:
    """读取录制文件（不存在或格式异常时返回 None）"""
    if not os.path.exists(record_path):
        return None
    try:
        data = _load_yaml(record_path) or {}
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _case_ids_from_file(case_file: str) -> List[str]:
    """用 YAML 解析出用例 ID 顺序（保证与文件顺序一致）"""
    data = _load_yaml(case_file)
    if not isinstance(data, list):
        raise ValueError("用例文件应为 YAML 列表")
    ids: List[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids


def _block_bounds(lines: List[str], case_id: str) -> Tuple[int, int]:
    """找出某条用例在文本中的行区间 [start, end)（end 为下一条用例或文件末尾）"""
    start = None
    for index, line in enumerate(lines):
        match = CASE_ITEM_RE.match(line)
        if not match:
            continue
        if start is None and match.group("id").strip().strip("'\"") == case_id:
            start = index
            continue
        if start is not None:
            return start, index
    if start is None:
        raise ValueError(f"用例文件中找不到 id={case_id}")
    return start, len(lines)


def _scalar(value: Any) -> str:
    """把标量安全地渲染成 YAML 单行值"""
    dumped = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True).strip()
    if dumped.endswith("..."):
        dumped = dumped[:-3].strip()
    return dumped


def _block_to_text(items: List[Dict[str, Any]], field_name: str) -> List[str]:
    """把 actions/assertions 列表渲染成用例文件里的 YAML 片段（含 audit 注释）"""
    rendered: List[str] = []
    for item in items:
        skill = item.get("skill")
        params = item.get("params") or {}
        if item.get("audited"):
            rendered.append(
                f"    # ⚠️ 该步骤使用 audit 技能（{skill}）：会绕过真实 UI 操作——已允许使用，请 review 其必要性"
            )
        rendered.append(f"    - skill: {skill}")
        if params:
            rendered.append("      params:")
            for key, value in params.items():
                rendered.append(f"        {key}: {_scalar(value)}")
        else:
            rendered.append("      params: {}")
        anchor = item.get("anchor")
        if isinstance(anchor, dict) and anchor:
            rendered.append("      anchor:")
            for key, value in anchor.items():
                rendered.append(f"        {key}: {_scalar(value)}")

    body = rendered or ["    []"]
    return [f"  {field_name}:"] + body


def _upsert_field(
    lines: List[str], case_id: str, field_name: str, block: List[str]
) -> Tuple[List[str], bool]:
    """
    在指定用例块内插入/替换某个字段块（文本级操作，保留其它内容与注释）。

    Returns:
        (新的行列表, 是否为“替换既有字段”)
    """
    start, end = _block_bounds(lines, case_id)
    pattern = re.compile(FIELD_RE_TEMPLATE.format(field=re.escape(field_name)))
    field_start = None
    field_end = None

    for index in range(start + 1, end):
        if pattern.match(lines[index]):
            field_start = index
            indent = len(lines[index]) - len(lines[index].lstrip())
            field_end = index + 1
            while field_end < end:
                candidate = lines[field_end]
                if not candidate.strip():
                    break
                current_indent = len(candidate) - len(candidate.lstrip())
                if current_indent <= indent:
                    break
                field_end += 1
            break

    if field_start is not None:
        return lines[:field_start] + block + lines[field_end:], True

    # 未找到字段 → 插到用例块末尾（回退掉“空行 + 属于下一条用例的注释行”）
    insert_at = end
    while insert_at - 1 > start:
        candidate = lines[insert_at - 1].strip()
        if candidate and not candidate.startswith("#"):
            break
        insert_at -= 1
    return lines[:insert_at] + block + lines[insert_at:], False


def _render_diff(before: List[str], after: List[str], limit: int = 200) -> str:
    """生成行级 unified diff（超出 limit 行时截断）"""
    diff = list(difflib.unified_diff(before, after, fromfile="before", tofile="after", lineterm=""))
    if len(diff) > limit:
        diff = diff[:limit] + [f"... （diff 共 {len(diff)} 行，已截断）"]
    return "\n".join(diff)


def promote_recorded_actions(
    case_file: str,
    record_dir: Optional[str] = None,
    output: Optional[str] = None,
    dry_run: bool = False,
    overwrite: bool = False,
    with_assertions: bool = False,
    backup: bool = True,
) -> PromoteResult:
    """
    把录制文件固化为用例文件的 actions（可选 assertions）。

    Args:
        case_file: 用例文件（.yaml/.yml）
        record_dir: 录制文件目录（默认 ./recorded_actions）
        output: 输出文件（默认原地修改）
        dry_run: 只生成 diff，不写盘
        overwrite: 用例已有 actions 时是否覆盖（默认跳过）
        with_assertions: 连同录制里的断言草稿一起固化（用例已有 assertions 时同样受 overwrite 控制）
        backup: 写盘前备份 <file>.bak
    """
    case_file = os.path.abspath(case_file)
    output_file = os.path.abspath(output) if output else case_file
    record_dir = record_dir or DEFAULT_RECORD_DIR

    result = PromoteResult(case_file=case_file, output_file=output_file, dry_run=dry_run)

    if not os.path.exists(case_file):
        raise FileNotFoundError(f"用例文件不存在: {case_file}")
    if not case_file.lower().endswith((".yaml", ".yml")):
        raise ValueError("当前仅支持 YAML 用例文件（JSON/Excel 请先转成 YAML）")

    with open(case_file, "r", encoding="utf-8") as handle:
        original_text = handle.read()
    original_lines = original_text.splitlines()

    yaml_cases = _load_yaml(case_file)
    case_ids = _case_ids_from_file(case_file)
    existing_fields = {
        str(item.get("id")): {
            "actions": bool(item.get("actions")),
            "assertions": bool(item.get("assertions")),
        }
        for item in yaml_cases if isinstance(item, dict)
    }

    working_lines = list(original_lines)

    for case_id in case_ids:
        record_path = os.path.join(record_dir, f"{case_id}.actions.yaml")
        recorded = load_recorded(record_path)

        if recorded is None:
            result.cases.append(PromoteCaseResult(case_id, "no_recording", f"未找到 {record_path}"))
            continue

        actions = recorded.get("actions") or []
        assertion_drafts = recorded.get("assertions") or []

        if not actions:
            result.cases.append(PromoteCaseResult(case_id, "no_recording", "录制里没有可固化的操作步骤"))
            continue

        has_actions = existing_fields.get(case_id, {}).get("actions", False)
        has_assertions = existing_fields.get(case_id, {}).get("assertions", False)
        if has_actions and not overwrite:
            result.cases.append(PromoteCaseResult(
                case_id, "skipped_exists", "用例已有 actions（用 --overwrite 覆盖）"
            ))
            continue

        audited_skills = sorted({str(item.get("skill")) for item in actions if item.get("audited")})

        try:
            working_lines, _ = _upsert_field(
                working_lines, case_id, "actions", _block_to_text(actions, "actions")
            )
            written_assertions = 0
            if with_assertions and assertion_drafts and (overwrite or not has_assertions):
                working_lines, _ = _upsert_field(
                    working_lines, case_id, "assertions",
                    _block_to_text(assertion_drafts, "assertions"),
                )
                written_assertions = len(assertion_drafts)

            result.cases.append(PromoteCaseResult(
                case_id=case_id,
                status="promoted",
                detail=f"来源: {record_path}",
                action_count=len(actions),
                assertion_count=written_assertions,
                audited_skills=audited_skills,
            ))
        except Exception as e:
            result.cases.append(PromoteCaseResult(case_id, "error", str(e)))

    new_text = "\n".join(working_lines)
    if original_text.endswith("\n"):
        new_text += "\n"

    if result.promoted:
        result.diff_text = _render_diff(original_lines, new_text.splitlines())
        if not dry_run:
            if backup and output_file == case_file and os.path.exists(case_file):
                shutil.copy2(case_file, case_file + ".bak")
            os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
            with open(output_file, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(new_text)

    return result


def main(argv: Optional[List[str]] = None) -> int:
    # 只兜底编码错误（保留终端原生编码）：避免 emoji 在 GBK 控制台触发 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:  # pragma: no cover - 老版本解释器/特殊流兜底
            pass

    parser = argparse.ArgumentParser(
        prog="python -m browser_automation_skills.promote",
        description="把 recorded_actions/<用例ID>.actions.yaml 固化为用例 YAML 的 actions（可选 assertions）",
    )
    parser.add_argument("--cases", required=True, help="用例文件（YAML）")
    parser.add_argument("--record-dir", default=DEFAULT_RECORD_DIR,
                        help="录制文件目录（默认 ./recorded_actions）")
    parser.add_argument("--output", default=None, help="输出文件（默认原地修改）")
    parser.add_argument("--dry-run", action="store_true", help="只打印 diff，不写盘")
    parser.add_argument("--overwrite", action="store_true", help="覆盖用例已有的 actions/assertions")
    parser.add_argument("--with-assertions", action="store_true", help="连同录制里的断言草稿一起固化")
    parser.add_argument("--no-backup", action="store_true", help="写盘前不生成 .bak 备份")
    args = parser.parse_args(argv)

    try:
        result = promote_recorded_actions(
            case_file=args.cases,
            record_dir=args.record_dir,
            output=args.output,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            with_assertions=args.with_assertions,
            backup=not args.no_backup,
        )
    except Exception as e:
        print(f"❌ 固化失败: {e}")
        return 1

    print("========== promote 汇总 ==========")
    print(result.format_summary())
    if result.diff_text:
        print("\n========== 变更 diff ==========")
        print(result.diff_text)
    if result.promoted and not result.dry_run:
        print(f"\n[OK] 已写入 {result.output_file}")
        if args.output is None and not args.no_backup:
            print(f"[OK] 原文件已备份为 {result.output_file}.bak")
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())

