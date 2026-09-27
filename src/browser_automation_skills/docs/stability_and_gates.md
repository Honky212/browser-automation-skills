# 稳定性与判定严谨性（v1.5.5）

本文说明 v1.5.5 为“**用例稳定执行** + **通过结果可信**”所做的框架级改造，全部能力都在框架层实现，**不需要修改测试用例**。

## 1. 解决的问题

| 现象 | 根因 | 修复 |
|------|------|------|
| 找不到元素时白等 57s / 102s | 技能级重试与选择器重试**相乘**：`3 × 3 × timeout` | 选择器等待加总预算 `selector_wait_budget`；技能级重试降为 2 次 |
| 单步/单用例可能长时间挂死 | 用例的 `timeout` 字段此前不被执行链路使用 | 步骤级 + 用例级硬超时（`asyncio.wait_for`） |
| 模型传参笔误导致整步失败 | `fill_by_index(text=...)`、`title_contains(text=...)` 等命名差异直接抛 `TypeError` | `SkillManager.execute` 按技能签名做**参数别名归一化**，未知参数丢弃并记录 |
| 一次 LLM 抖动/非法 JSON 判死整条用例 | `_plan_next_step` 出错即返回 FAILED，无重试 | LLM 调用重试 + 非法 JSON 回喂重试 |
| 页面重渲染后 `not attached` 直接失败 | `click_by_index`/`fill_by_index` 句柄失效即报错 | 元素失效**自愈**：重抓快照 → 按 id/索引+文本重定位 → 重试一次 |
| 用例间状态互相污染 | 复用同一个 page | 每条用例前自动新建页面并关闭旧页（`isolate_pages`） |
| “没有断言的用例也能 PASS” | `success` 完全由模型返回的 `status=done` 决定 | **断言硬门禁**：无断言证据或最后一次断言失败 → 不允许 done |
| 失败无证据、报告看不出可信度 | 报告只有状态与步数 | 报告新增 耗时/断言/重试 列 + “断言证据”章节 |

## 2. 新增/生效的配置项

```yaml
agent:
  require_assertion: true       # 断言硬门禁总开关（默认 false，兼容既有用法）
  assertion_gate_retries: 1     # 被门禁拦截后允许模型补救的次数
  step_timeout: 60              # 单步超时（秒），0 = 不限制
  case_timeout: 120             # 用例级默认超时（秒），用例文件的 timeout 优先
  llm_retries: 3                # LLM 规划调用 / 非法 JSON 的重试次数
  isolate_pages: true           # 每条用例使用全新页面
  retry_failed_cases: 0         # 用例失败后自动重跑次数（默认关闭）

skill_retry:
  max_attempts: 2               # 技能级重试（与选择器重试不再相乘放大）
  backoff: 0.5
  retry_on: ["timeout", "timed out", "not found", "failed to", "timeout waiting"]

skill_timeout:
  per_skill_seconds: 30         # 单个技能单次执行硬超时
  selector_wait_budget_seconds: 6.0   # 单个选择器等待的总预算（关键）
  selector_timeout_ms: 3000
  exempt_skills: [execute_task, execute_batch_testcases, analyze_page, screenshot_vision]
```

另外 `browser.timeout` 现在真正生效：`BrowserLauncher(default_timeout=...)` 会调用
`context.set_default_timeout()` / `set_default_navigation_timeout()`。

## 3. 关键语义

### 3.1 超时的三层结构

```
用例级 timeout（用例文件 > agent.case_timeout）
└── 步骤级 step_timeout（单个技能调用）
    └── 技能级 per_skill_seconds（单次执行，复合技能豁免）
        └── 选择器总预算 selector_wait_budget（一次等待，不论内部重试几次）
```

最坏情况下“找不到元素”的耗时 ≈ `max_attempts × selector_wait_budget`（默认约 12 秒），
而不是旧实现的 `3 × 3 × timeout`（最坏近百秒）。

### 3.2 断言硬门禁

`require_assertion: true` 时，`BrowserAgent` 会记录所有断言类技能的执行结果，并在模型返回
`status=done` 时校验：

1. **未执行任何断言** → 拦截，写入一条“门禁提示”让模型补执行断言（次数 = `assertion_gate_retries`）；
2. **最后一次断言失败** → 同上拦截；补救次数用尽仍如此 → 用例判为 **不通过**（`error` 以“断言门禁”开头）；
3. 同时系统提示词会加入硬性规则 8/9（软门禁），从源头减少“无断言就 done”。

断言类技能名单见 `agent.ASSERTION_SKILL_NAMES`（`url_contains`/`title_contains`/`page_contains_text`/
`element_exists`/`text_equals`/`attribute_equals`/`count_elements` 等 17 个）。

### 3.3 参数别名归一化

`manager.normalize_skill_params()` 依据技能 `run` 签名做映射（`PARAM_ALIASES`）：

| 技能形参 | 可接受的别名 |
|----------|--------------|
| `value` | `text`, `content`, `val`, `input_value` |
| `text` | `value`, `content`, `keyword`, `expected`, `expected_text` |
| `expected` | `text`, `value`, `expected_text`, `expected_value` |
| `selector` | `locator`, `css`, `css_selector`, `xpath`, `element` |
| `url` | `href`, `address`, `target_url` |
| `seconds` | `duration`, `wait`, `time`, `second` |
| `path` | `file_path`, `filepath`, `filename`, `save_path` |
| `index` | `idx`, `element_index` |

归一化记录会写入 `SkillResult.param_notes`，最终出现在批量报告的“参数归一化记录”章节。

## 4. 兼容性说明（升级注意）

- `skill_retry.max_attempts` 默认由 **3 降为 2**，`backoff` 由 1.0 降为 0.5：重试次数减少换取耗时可控；如需更容忍抖动可在配置里调回。
- 新增 `_timeout_settings`，未配置时使用内置默认值（技能 30s、选择器预算 6s）。
- `require_assertion` 默认 **false**（保持库的既有行为）；本项目 `config/config.yaml` 显式设为 true。
- 断言门禁开启后，**没有断言步骤的旧用例会变成不通过**，这是预期行为（等价于“无证据不放行”）。

## 6. 模型绕路抑制与“确定性执行”（v1.5.5 第二轮）

第一轮解决了“跑得动、不假通过”，第二轮解决“跑得稳、可复现”。

### 6.1 技能策略：allow / audit / deny（不硬禁 `execute_js`）

有些元素确实点不动，只能用 JS。因此对这类“绕过 UI”的技能采用 **audit（允许但记录）**而非 deny：

```yaml
skill_policy:
  execute_js: audit      # 允许使用，但会在报告的“执行模式与审计”章节披露
  # upload_file: deny    # 如需硬禁某技能，改为 deny（规划提示词中会剔除该技能）
```

- `deny`：`SkillManager.execute` 直接返回失败（不执行），并且**从系统提示词的可用技能列表中剔除**；
- `audit`：正常执行，但 `SkillResult.audited = True`，最终写入报告：

```text
## 执行模式与审计
- TC_03: 执行模式: LLM 规划；⚠️ 使用了审计技能（绕过 UI 的降级手段）: execute_js
```

这样“用 JS 兜底”变成**可披露、可评审**的事实，而不是静默作弊。

### 6.2 失败结果的结构化提示（减少瞎猜与绕路）

元素类技能失败时（`not found` / `not an input field` / `not visible` / `not attached`…），
`SkillManager` 会自动抓一次快照，把候选元素清单附加到失败信息与 `result.data["hint"]`：

```text
❌ Step 2 failed: Element [10] is not an input field: a | 提示: 当前页面可输入元素（可用索引重试）:
   [13] textarea id=chat-textarea; [25] input id=... 
```

模型据此一次改对，避免“重抓快照 → 再猜错 → 换 JS”的连锁绕路。

### 6.3 用例声明框架断言：`assertions`（判定与 LLM 解耦）

```yaml
- id: TC_02
  steps: "在百度搜索 自动化测试 并验证结果页"     # 文案可以写得模糊
  setup_url: https://www.baidu.com
  assertions:
    - {skill: url_contains,       params: {expected: "wd="}}
    - {skill: page_contains_text, params: {text: "自动化测试"}}
```

- 这些断言**由框架自己执行**（与 LLM 自述无关），任一失败 → 用例判为不通过，
  失败原因形如 `框架断言失败: url_contains({"expected": "wd="}) - ...`；
- 声明了 `assertions` 的用例，LLM 侧的断言硬门禁自动关闭（判定权已交给框架）；
- 报告里这些证据会标注“（框架断言）”。

### 6.4 结构化 `actions`：确定性执行（不经过 LLM 规划）

**判定优先级（由用例文件 + 配置决定，不由模型决定）**：

| 优先级 | 条件 | 执行方式 | 调用 LLM |
|--------|------|----------|----------|
| 1 | 用例声明了非空 `actions` | 顺序执行 actions → 执行 `assertions` 判定 | ❌ |
| 2 | 无 actions，且 `agent.replay_recorded: true` 且存在录制文件 | 回放（含锚点重解析）→ 执行 `assertions` 判定 | ❌ |
| 3 | 以上都不满足 | `steps` 交给 LLM 逐步规划；`assertions`（若声明）由框架最后执行 | ✅ |

代码位置：`BatchTestAgent._execute_single_case` → `actions_source` 取 `case` / `replay` / `""`，
并写入 `TestCaseResult.mode`（`deterministic` / `llm`）与 `TestCaseResult.actions_source`，
最终体现为报告“执行模式与审计”章节里的 `确定性执行（来源：用例声明 actions）` /
`确定性执行（来源：录制回放）` / `LLM 规划`。

```yaml
- id: TC_03
  steps: "搜索 AI技术发展趋势"                    # 仅作可读说明
  actions:
    - {skill: get_dom_snapshot, params: {}}
    - {skill: fill_by_index,    params: {index: 13, value: "AI技术发展趋势"}}
    - {skill: click_by_index,   params: {index: 6}}
  assertions:
    - {skill: url_contains,   params: {expected: "wd="}}
    - {skill: title_contains, params: {expected: "百度搜索"}}
```

- 有 `actions` → **完全不调用 LLM**，按序执行（每步受 `step_timeout` 保护），失败即停
  （`agent.continue_on_action_failure: true` 可改为继续）；随后执行 `assertions` 判定；
- 这是“用例写得不清楚也能稳定执行”的**唯一可靠路径**：稳定性不再取决于模型对文案的理解。

### 6.5 录制 / 回放（让模糊用例逐步固化）

```yaml
agent:
  record_actions: true      # 成功后把实际动作序列写到 recorded_actions/<用例ID>.actions.yaml
  replay_recorded: false    # 人工确认录制文件后再开启（开启后自动走确定性回放）
  record_dir: "./recorded_actions"
  continue_on_action_failure: false
```

典型工作流：**先用自然语言跑一次（LLM 规划）→ 框架录制动作 → 人工 review 录制文件 →
把 `actions` 固化进用例（或开启 `replay_recorded`）→ 之后每次都是确定性执行**。

### 6.6 锚点重解析：让回放扛得住“索引漂移”与“多套布局”

**问题（实测暴露）**：回放录制文件时，里面的 `index` 是**易失**的——
同一站点两次加载的元素顺序/数量都可能不同（实测百度首页 28 个元素时搜索框在 `[10]`，
32 个元素时在 `[13]`）。更极端的情况是站点存在**两套布局**（百度首页的经典版 `#kw/#su`
与 AI 版 `#chat-textarea/#chat-submit-button`）。

**做法**：录制 `*_by_index` 步骤时同时记录**稳定锚点**，回放时据此重解析索引。

```yaml
- skill: fill_by_index
  params: {index: 13, value: AI技术发展趋势}
  anchor: {element_id: chat-textarea, selector: '#chat-textarea', tag: textarea}
- skill: click_by_index
  params: {index: 6}
  anchor: {element_id: chat-submit-button, selector: '#chat-submit-button', tag: button, text: 百度一下}
```

回放时的解析顺序：

1. **精确匹配**：元素 id → placeholder → selector(+tag) → tag+text → name；
2. **语义回退**（精确未命中，通常是布局变体/改版）：先按 `text` 全等（如“百度一下”），
   输入类再退到“首个可见的 input/textarea”，按钮类退到“首个可见且带文本的 button/a”；
3. 两者都失败 → 沿用录制索引，并打印明确的 WARNING（便于人工重新录制）。

每次回退都会记录日志，例如实测：

```text
WARNING 回放锚点未精确命中（锚点 {'element_id': 'chat-textarea', ...}），已按语义回退：index 13 -> [10]；如结果异常请重新录制该用例
WARNING 回放锚点未精确命中（锚点 {'element_id': 'chat-submit-button', 'text': '百度一下', ...}），已按语义回退：index 6 -> [11]；如结果异常请重新录制该用例
```

**实测效果**（同一天两种百度布局之间切换）：

| 运行 | 模式 | 结果 | 耗时 |
|------|------|------|------|
| LLM 规划 | llm | 3/3 | 27~67 秒（方差大） |
| 声明 actions（演示用例） | deterministic | 2/2 | 7.3 秒 |
| 回放（**无**锚点重解析） | deterministic | 2/3 ❌ | 7.2 秒 |
| 回放 + 锚点语义回退 | deterministic | **3/3** ✅ | **6.2 秒** |

> 注意：语义回退是“有断言兜底”的兜底手段——它会记录 WARNING，且用例的 `assertions`
> 仍然决定通过与否；如果站点结构变化过大（连语义锚点都匹配不到），回放会失败并提示重新录制。
> 因此**推荐做法仍是把 review 过的 `actions` + `assertions` 固化到用例文件里**，而不是长期依赖回放。

### 6.7 确定性失败 → 回退 LLM（`fallback_to_llm_on_action_failure`）

确定性执行（`actions` / 录制回放）失败时，可选择自动让 LLM 规划兜底：

```yaml
agent:
  fallback_to_llm_on_action_failure: false   # 默认 false（严格确定性；CI 门禁建议保持 false）
```

行为细节：

1. 仅当 **确定性阶段执行失败** 时触发（actions 成功但框架断言失败 → 不回退，因为判定失败是真实结论）；
2. 回退时把失败原因作为 `[回退说明]` 前缀拼进任务提示词，提示模型“页面可能处于执行到一半的中间状态”；
3. 两阶段步骤都保留在 `steps_executed` 中，并标注 `stage: deterministic` / `stage: llm`（LLM 阶段步号顺延）；
4. 回退后 `mode="llm"`、`fallback_used=True`、`fallback_reason` 记录本次回退原因；
5. 报告“执行模式与审计”章节明确披露：

```text
- TC_FB: 执行模式: 确定性执行（来源：用例声明 actions）失败 → ⚠️ 已回退 LLM 规划（回退原因: 步骤 1 失败: fill_by_index({"index": 999}) - ...）
```

**取舍**：更稳（失败有兜底），但“通过”不再是纯确定性复现的结果，因此报告必须披露、CI 门禁建议关闭。

### 6.8 固化工具：`python -m browser_automation_skills.promote`

把 `recorded_actions/<用例ID>.actions.yaml` 一条命令写进用例文件的 `actions`（可选 `assertions`），
取代“人工 review + 手抄 YAML”。

```powershell
# 1) 先看 diff（不写盘）
python -m browser_automation_skills.promote --cases test_case/test_cases_baidu.yaml --dry-run

# 2) 连断言草稿一起固化到新文件（原文件不动）
python -m browser_automation_skills.promote --cases <file> --with-assertions --output <new_file>

# 3) 原地固化（自动备份 <file>.bak；用例已有 actions 时需 --overwrite）
python -m browser_automation_skills.promote --cases <file> --overwrite --with-assertions
```

| 参数 | 作用 |
|------|------|
| `--cases` | 用例文件（YAML） |
| `--record-dir` | 录制文件目录（默认 `./recorded_actions`） |
| `--output` | 输出到新文件（默认原地修改） |
| `--dry-run` | 只打印 diff，不写盘 |
| `--overwrite` | 覆盖用例已有的 `actions` / `assertions` |
| `--with-assertions` | 连同录制里的断言草稿一起固化 |
| `--no-backup` | 写盘前不生成 `.bak` |

实现要点：

1. **不禁用任何技能**：`execute_js` 等 audit 步骤**照常固化**（有些元素确实只能靠 JS），
   只在 YAML 里加注释标注 + 汇总里告警，是否保留由人工 review 决定；
2. **文本级插入**：只替换/插入 `actions:`、`assertions:` 两个字段块，
   用例文件里其它字段、注释与排版都原样保留（不整份重新序列化）；
3. 默认写前备份 `*.bak`，`--dry-run` 先给 diff；
4. 固化后**用例文件成为唯一事实来源**：可进版本管理、可 code review、可做 CI 门禁，
   不再依赖会被 gitignore 的运行时目录。

完整闭环（实测）：**模式 A 跑通（29~67s）→ 自动录制 → `promote` 固化 → 之后每次确定性执行（≈7s）**。

## 7. 效果与边界

| 手段 | 通过率稳定性 | 通过可信度 |
|------|--------------|------------|
| 提示词/用例措辞优化 | 🟡 压方差，不根治（实测同输入 31.3s vs 66.8s，2.1×） | 🟡 |
| 技能策略 + 失败结构化提示 | 🟢 明显减少绕路与空转 | 🟢 JSON 兜底被披露 |
| 框架强制断言 | 🟡 不改善执行 | 🟢 判定完全脱离 LLM |
| 结构化 actions + 录制回放 | 🟢🟢 接近确定性 | 🟢🟢 |

**边界**：确定性回放仍受页面改版、验证码、慢加载影响；因此失败截图、用例级重试、
选择器等待预算等兜底机制仍然必要。“100% 稳定”不存在，目标是**失败快、可定位、可复放**。

## 8. 验证方式

```powershell
# 单元测试（含新增稳定性用例）
$env:PYTHONPATH='src'; python -m pytest src/browser_automation_skills/tests -q

# 端到端：批量执行 + 生成报告（包内自带的可运行示例；默认用例为确定性 actions，不调用 LLM）
python -m browser_automation_skills.examples.batch_run_example

# 只解析用例、打印概要（不启动浏览器）
python -m browser_automation_skills.examples.batch_run_example --parse-only

# 确定性执行演示（用例声明 actions + assertions，不调用 LLM）
python test_case/run_batch_baidu.py test_case/test_cases_deterministic_demo.yaml test_case/reports/deterministic_demo_report.md

# 录制 → 用例 YAML 固化
python -m browser_automation_skills.promote --cases <cases.yaml> --dry-run
```

相关测试：`tests/test_stability_features.py`（参数归一化、等待预算、硬超时、复合技能豁免、
断言门禁、用例超时、报告证据、结构化解析、技能策略、确定性执行、框架断言、录制回放、审计报告）。
