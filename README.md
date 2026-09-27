# Browser-Automation-Skills

基于 **Playwright + LLM** 的 AI 驱动浏览器自动化测试 Skills 框架。

将复杂的浏览器操作封装为 70+ 个可复用的 Skill 单元，支持自然语言任务执行、多模态视觉分析、DOM 索引操作和批量测试用例执行。

## 核心能力

| 能力 | 说明 |
|------|------|
| **浏览器操作** | 20 个 Skill：导航、点击、截图、滚动、JS 执行等 |
| **表单操作** | 12 个 Skill：填写、选择、勾选、上传、日期控件等 |
| **断言验证** | 17 个 Skill：文本/元素/URL/属性/数量等 |
| **标签页管理** | 5 个 Skill：新建、切换、关闭、列表 |
| **弹窗/iframe** | 10 个 Skill：弹窗识别、iframe 内操作 |
| **DOM 索引** | 3 个 Skill：快照 + 索引点击/填写，无需 CSS 选择器 |
| **多模态视觉** | 2 个 Skill：截图 + AI 视觉分析（OpenAI/DashScope） |
| **AI Agent** | 自然语言任务自动规划执行 + 批量测试 |
| **性能优化** | DOM/LLM 缓存、LRU 淘汰、批量优化器 |

## 快速开始

### 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

> **⚠️ 重要：mcp 版本要求 `>=1.0.0,<2.0.0`**
>
> 本项目的 MCP Server 使用 mcp 1.x 的装饰器 API（`@server.list_tools()`），
> 与 mcp 2.0.0+ 不兼容。如果 pip 自动安装了 mcp 2.x，启动时会报
> `AttributeError: 'Server' object has no attribute 'list_tools'`。
>
> 修复方法：`pip install "mcp>=1.0.0,<2.0.0"`（已验证 1.29.0 可用）

### 配置

编辑 `config/config.yaml`：

```yaml
# Agent 配置（自然语言任务执行）
agent:
  model: "deepseek-v4-flash"
  api_key: "sk-xxx"
  base_url: "https://api.deepseek.com"

# 视觉模型配置（页面分析）
vision:
  provider: "dashscope"
  model: "qwen3-vl-plus"
  api_key: "sk-xxx"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 运行示例

```bash
# 批量执行用例并生成报告（包内自带的可运行示例，开箱即跑：默认用例为确定性 actions）
python -m browser_automation_skills.examples.batch_run_example

# 只解析用例、打印概要（不启动浏览器，可用于 CI 冒烟）
python -m browser_automation_skills.examples.batch_run_example --parse-only

# 把录制文件固化成用例的 actions/assertions
python -m browser_automation_skills.promote --cases my_cases.yaml --dry-run
```

更多资料：

| 文件 | 内容 |
|------|------|
| `examples/basic_workflow.md` | 基本工作流（Skill 直调） |
| `examples/batch_testing.md` | 批量测试：命令行示例的参数说明、用例格式、熔断机制 |
| `examples/visual_analysis.md` | 多模态视觉分析 |
| `examples/test_case_templates/` | 用例模板：`yaml_template.yaml`、`json_template.json`、`test_cases_baidu.yaml/.json`、`structured_actions_demo.yaml`、`fallback_demo.yaml`、`login/search/ecommerce_test.json` |

## 项目结构

```
browser-use-skill/
├── browser_automation_skills/             # Skills 核心模块（主包）
│   ├── __init__.py                        # 导出 + create_manager() 工厂函数
│   ├── base.py                            # BaseSkill 抽象类 + SkillResult
│   ├── manager.py                         # SkillManager 注册/执行引擎
│   ├── browser_skills.py                  # 浏览器操作 Skills (20 个 + 标签页 5 个)
│   ├── form_skills.py                     # 表单操作 Skills (12 个)
│   ├── assertion_skills.py                # 断言 Skills (17 个)
│   ├── popup_skills.py                    # 弹窗/iframe Skills (10 个)
│   ├── dom_snapshot.py                    # DOM 索引化 Skills (3 个)
│   ├── agent.py                           # AI Agent + 批量测试
│   │   ├── BrowserAgent                   #   自然语言任务执行
│   │   ├── BatchTestAgent                 #   批量测试引擎
│   │   ├── TestCaseParser                 #   用例解析 (JSON/YAML/Excel)
│   │   ├── ExecuteTaskSkill               #   单任务 Skill
│   │   └── ExecuteBatchTestCasesSkill     #   批量任务 Skill
│   ├── vision.py                          # 多模态视觉 Skills
│   │   ├── OpenAIVisionAdapter            #   OpenAI 适配器
│   │   ├── DashScopeVisionAdapter         #   DashScope 适配器
│   │   ├── DummyVisionAdapter             #   测试用虚拟适配器
│   │   ├── ScreenshotVisionSkill          #   Base64 截图
│   │   └── AnalyzePageSkill               #   页面视觉分析
│   ├── performance.py                     # 缓存 + 性能监控
│   ├── reporter.py                        # HTML/JSON 测试报告
│   └── screenshot_manager.py              # 截图管理
├── mcp_server.py                          # MCP 服务入口（源码位于根目录；v1.5.0 wheel 中已移入包内）
├── browser_launcher.py                    # 浏览器启动器（源码位于根目录；v1.5.0 wheel 中已移入包内）
├── config/
│   └── config.yaml                        # 统一配置（不入包，仅模板入包）
├── docs/                                  # 文档
│   ├── getting_started.md
│   ├── api_reference.md
│   └── mcp_usage.md
├── examples/                              # 示例文档与用例模板
├── tests/                                 # 单元测试
├── resources/                             # 资源文档与用例模板
├── build_wheel_v150.py                    # v1.5.0 staging 构建脚本
├── dist/                                  # 构建产物（.whl）
└── README.md
```

> **v1.5.0 wheel 布局**：自 v1.5.0 起，wheel 采用单一顶层包设计——`mcp_server.py`、`browser_launcher.py`、`docs/`、`examples/`、`tests/`、`resources/` 及配置模板等数据文件全部位于 `browser_automation_skills` 包内。安装后的使用方式：
>
> ```python
> # v1.5.0 导入方式
> from browser_automation_skills.browser_launcher import BrowserLauncher
> ```
>
> ```bash
> # v1.5.0 启动方式（旧的 python -m mcp_server 不再可用）
> python -m browser_automation_skills.mcp_server --headed
> ```

## 三种使用模式

### 模式一：Skill 直调（底层 API）

直接调用单个 Skill，适合精确控制的场景：

```python
from browser_automation_skills import create_manager

manager = create_manager(browser_context=context, config=config)

# 导航
await manager.execute("navigate", url="https://www.baidu.com")

# 填写输入框
await manager.execute("fill_input", selector="#kw", value="AI测试")

# 点击
await manager.execute("click", selector="#su")

# 断言
result = await manager.execute("text_contains", selector="#content", expected="AI测试")
print(result.success)  # True/False
```

### 模式二：AI Agent 自然语言执行（中层 API）

用自然语言描述任务，AI 自动规划并执行：

```python
from browser_automation_skills import create_manager
from browser_automation_skills.agent import BrowserAgent
from openai import AsyncOpenAI

manager = create_manager(browser_context=context, config=config)

agent = BrowserAgent(
    skill_manager=manager,
    llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
    max_steps=20,
)

result = await agent.execute_task(
    "打开百度，搜索'AI智能化测试'，截图保存"
)

print(f"成功: {result.success}")
print(f"执行了 {len(result.steps_executed)} 个步骤")
```

### 模式三：批量测试（高层 API）

从 Excel/JSON/YAML 文件导入用例，自动批量执行并生成报告：

> **注意**：`BatchTestAgent` 使用 `config.yaml` 中 `agent` 段的配置（model、api_key、base_url）。创建时可显式传入 `model` 参数，不传则自动从配置读取。

```python
from browser_automation_skills import create_manager
from browser_automation_skills.agent import TestCaseParser, BatchTestAgent

manager = create_manager(browser_context=context, config=config)

# 从 Excel 读取用例
test_cases = TestCaseParser.from_excel("test_cases.xlsx")

# 批量执行（model 不传时自动从 config.yaml 读取）
agent = BatchTestAgent(
    skill_manager=manager,
    llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
    model="deepseek-v4-flash",       # ← 建议显式指定，与 config.yaml 保持一致
    screenshot_on_failure=True,
)

result = await agent.execute_batch(test_cases)

# 查看结果
print(f"通过: {result.passed}/{result.total} ({result.pass_rate:.1f}%)")
result.generate_report("report.md")
```

## 多模态视觉分析

使用多模态大模型分析页面截图，定位元素位置、描述页面布局等：

```python
from browser_automation_skills.vision import VisionSupport, OpenAIVisionAdapter

adapter = OpenAIVisionAdapter(model="gpt-4o", api_key="sk-xxx")
vision = VisionSupport(adapter=adapter)

# 分析页面
result = await vision.analyze_page(
    page,
    prompt="找出页面上所有的按钮并描述它们的功能"
)
print(result.description)
```

支持三种适配器：

| 适配器 | 适用服务 | 模型示例 |
|--------|----------|----------|
| `OpenAIVisionAdapter` | OpenAI 兼容 API | gpt-4o, gpt-4o-mini |
| `DashScopeVisionAdapter` | 阿里云 DashScope | qwen-vl-max, qwen3-vl-plus |
| `DummyVisionAdapter` | 测试/离线 | — |

## 批量测试用例格式

测试用例的「操作步骤」列填写**自然语言**即可，无需写代码或选择器：

### Excel 格式

| ID | 用例名称 | 操作步骤 | 预期结果 | 优先级 | 前置URL |
|----|---------|---------|---------|--------|---------|
| TC_01 | 百度搜索 | 打开百度，搜索"AI测试"，验证结果包含"AI测试" | 显示搜索结果 | high | https://www.baidu.com |
| TC_02 | 登录验证 | 打开登录页，输入用户名admin密码123456，点击登录，验证页面显示"欢迎" | 登录成功 | high | https://example.com/login |

### JSON 格式

```json
[
  {
    "id": "TC_01",
    "name": "百度搜索",
    "steps": "打开百度，搜索'AI测试'，验证结果包含'AI测试'",
    "expected_result": "显示搜索结果",
    "setup_url": "https://www.baidu.com"
  }
]
```

### YAML 格式（支持 `actions` / `assertions`）

```yaml
- id: TC_02
  name: 百度搜索自动化测试
  steps: "在百度搜索自动化测试并验证结果页"      # 自然语言，交给 LLM 规划
  setup_url: https://www.baidu.com
  timeout: 60
  assertions:                                # 可选：由**框架**在最后强制执行并判定通过与否
    - {skill: url_contains,       params: {expected: "wd="}}
    - {skill: page_contains_text, params: {text: "自动化测试"}}

- id: TC_03
  name: 百度搜索AI技术（确定性执行）
  steps: "搜索 AI技术发展趋势"                 # 仅作可读说明
  setup_url: https://www.baidu.com
  actions:                                   # 可选：声明后**完全不调用 LLM**，按序执行
    - {skill: get_dom_snapshot, params: {}}
    - {skill: fill_by_index,    params: {index: 13, value: "AI技术发展趋势"}}
    - {skill: click_by_index,   params: {index: 6}}
  assertions:
    - {skill: url_contains,   params: {expected: "wd="}}
    - {skill: title_contains, params: {expected: "百度搜索"}}
```

| 字段 | 作用 |
|------|------|
| `steps` | 自然语言步骤说明（模式 A 下由 LLM 逐步规划；模式 B/C 下仅作说明） |
| `assertions` | 框架强制断言：LLM/actions 执行完后由框架执行，任一失败则用例不通过（判定与 LLM 解耦） |
| `actions` | 确定性步骤：声明后不调用 LLM，按序执行（每步受 `step_timeout` 保护），随后执行 `assertions` |

## 用例执行模式：自然语言 / 确定性 actions / 录制回放

**一条用例走哪条路，由「用例文件 + 配置」决定，不由大模型自己决定。** 判定优先级如下：

| 优先级 | 触发条件 | 执行方式 | 是否调用 LLM |
|--------|----------|----------|--------------|
| **1** | 用例里声明了非空 `actions` | 按 `actions` 顺序执行 → 再执行 `assertions` 判定 | **❌ 不调用** |
| **2** | 没有 `actions`，且 `agent.replay_recorded: true`，且存在 `recorded_actions/<用例ID>.actions.yaml` | 回放录制动作（含锚点重解析）→ 再执行 `assertions` 判定 | **❌ 不调用** |
| **3** | 以上都不满足 | `steps` 自然语言交给 LLM 逐步规划；若声明了 `assertions`，框架在最后强制执行并判定 | ✅ 调用 |

实现位置：`BatchTestAgent._execute_single_case`（`declared_actions = case.actions` → 有则 `actions_source="case"`；
否则读录制文件 → `actions_source="replay"`；都没有则 `mode="llm"`）。

**报告里会明确写出每条用例实际走的是哪条路**，无需猜测：

```text
## 执行模式与审计

- TC_01: 执行模式: LLM 规划；已录制动作: ./recorded_actions/TC_01.actions.yaml
- TC_03: 执行模式: 确定性执行（来源：用例声明 actions，不调用 LLM）
```

### 怎么选？（经验规则）

| 你的场景 | 建议模式 | 理由 |
|----------|----------|------|
| 早期探索 / 页面常变 / 步骤还不确定 | 自然语言 | 让 LLM 先跑通，成本最低 |
| 关键回归，要求快且稳定 | 确定性 actions | 不调 LLM、无方差；实测 6~7 秒 vs 29~67 秒 |
| 自然语言用例已跑通，想固化 | 先录制 → 人工 review → 固化成 actions | 自动生成 actions 草稿，省手写 |
| 不允许"用 JS 绕过 UI 操作" | `skill_policy: {execute_js: deny}` | 硬禁（默认是 `audit`：允许但会在报告中披露） |

> 混合用法：模式 A 也可以用 `assertions`。此时"怎么点、怎么填"由 LLM 规划，
> 但"是否通过"由框架的断言决定——即使 `steps` 写得很模糊，也不会出现"假通过"。

### 模式 A：自然语言（最省事）

```yaml
- id: TC_01
  name: 百度首页打开测试
  steps: "打开百度首页并验证标题包含'百度'"     # LLM 逐步规划
  assertions:                                  # 判定交给框架
    - {skill: title_contains, params: {expected: "百度"}}
  timeout: 60
```

### 模式 B：确定性 actions（推荐用于长期回归）

```yaml
- id: TC_03
  name: 百度搜索AI技术（确定性执行）
  steps: "搜索 AI技术发展趋势"                   # 仅作说明，实际按 actions 执行
  actions:
    - {skill: get_dom_snapshot, params: {}}
    - {skill: fill_by_index,    params: {index: 13, value: "AI技术发展趋势"}}
    - {skill: click_by_index,   params: {index: 6}}
  assertions:
    - {skill: url_contains,   params: {expected: "wd="}}
    - {skill: title_contains, params: {expected: "百度搜索"}}
```

- 完全不调用 LLM；失败即停（`agent.continue_on_action_failure: true` 可改为继续执行后续动作）
- 索引会漂移？可用 `get_dom_snapshot` 先取快照，或直接写 `anchor`（见下）

### 模式 C：录制回放（自动生成 actions 草稿）

```yaml
agent:
  record_actions: true      # 自然语言跑成功后，自动录制到 recorded_actions/<用例ID>.actions.yaml
  replay_recorded: false    # 人工 review 后置 true，即可让已录制用例走确定性回放
  record_dir: "./recorded_actions"
```

录制文件形如（`anchor` 用于回放时重解析易漂移的索引）：

```yaml
id: TC_03
recorded_at: '2026-09-28 00:01:36'
recorded_from: llm
actions:
- skill: get_dom_snapshot
  params: {}
- skill: fill_by_index
  params: {index: 13, value: AI技术发展趋势}
  anchor: {element_id: chat-textarea, selector: '#chat-textarea', tag: textarea}
- skill: click_by_index
  params: {index: 6}
  anchor: {element_id: chat-submit-button, selector: '#chat-submit-button', tag: button, text: 百度一下}
```

推荐工作流：**模式 A 跑通 → 框架录制 → 人工 review → 把 actions 固化进用例文件（模式 B）**。
回放（`replay_recorded: true`）适合临时提速；页面大改版时它会失败并提示重新录制。

### 回退：确定性失败时自动让 LLM 兜底（可选）

```yaml
agent:
  fallback_to_llm_on_action_failure: true   # 默认 false（严格确定性）
```

- actions / 回放失败 → 自动改用 LLM 规划兜底，并把失败原因以 `[回退说明]` 前缀喂给模型
  （告知"页面可能处于执行到一半的中间状态"）；
- 报告中明确标注，**不会静默**：
  `执行模式: 确定性执行（来源：用例声明 actions）失败 → ⚠️ 已回退 LLM 规划（回退原因: 步骤 1 失败: ...）`
- 回退后的步骤记录会保留两阶段（`stage: deterministic` / `stage: llm`），便于复盘；
- 取舍：更稳，但"通过"不再是纯确定性的。**CI 门禁建议保持 `false`**（严格确定性）；本地调试、生产巡检可设 `true`。

### 固化：`python -m browser_automation_skills.promote`

把 `recorded_actions/<用例ID>.actions.yaml` 一条命令写进用例文件的 `actions`（可选 `assertions`），
取代"人工 review + 手抄 YAML"。

```bash
# 1) 先看 diff（不写盘）
python -m browser_automation_skills.promote --cases test_case/test_cases_baidu.yaml --dry-run

# 2) 连断言草稿一起固化到新文件（原文件不动，推荐先这样）
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
| `--no-backup` | 写盘前不生成 `.bak` 备份 |

实现要点：

- **绝不禁用任何技能**：录制里的 `execute_js` 等 audit 步骤**照常固化**（有些元素确实只能靠 JS 操作），
  只在 YAML 里加注释标注 + 在汇总里告警，是否保留由人工 review 决定：
  ```yaml
      # ⚠️ 该步骤使用 audit 技能（execute_js）：会绕过真实 UI 操作——已允许使用，请 review 其必要性
      - skill: execute_js
        params: {script: document.querySelector('#su').click()}
  ```
- **只动 `actions:` / `assertions:` 两个字段块**：用例文件里其它字段、注释与排版原样保留（不整份重新序列化）；
- 默认写前备份 `.bak`，`--dry-run` 先给 diff；固化后用例文件成为**唯一事实来源**
  （可进版本管理、可 code review、可做 CI 门禁），不再依赖会被 gitignore 的运行时目录。

完整闭环实测（同一批 3 条用例）：

| 阶段 | 模式 | 结果 | 耗时 |
|------|------|------|------|
| ① 自然语言跑通（自动录制，含 anchor + 断言草稿） | LLM | 3/3 | 52.5s |
| ② `promote --with-assertions --output <new>` | 离线工具 | 固化 3 条 | — |
| ③ review 后跑固化文件 | 确定性、零 LLM | **3/3** | **约 10s** |

> 注意：录制给的是**草稿**。若某次 LLM 是靠"副作用"过关（例如填写输入框后页面自动跳转，
> 录制里就没有点击步骤），回放会被**断言**拦下——此时按 review 补上缺的步骤即可。
> 这也是"固化 + 断言"组合最有价值的地方：**不粉饰、不假通过**。

## 运行测试

```bash
# 运行所有测试
python run_tests.py

# 有头模式（可见浏览器）
python run_tests.py --headed

# 慢动作模式（调试用）
python run_tests.py --slow-mo 500

# 生成 HTML 报告
python run_tests.py --html
```

## 文档

- [快速入门指南](docs/getting_started.md)
- [API 参考文档](docs/api_reference.md)
- [MCP 使用文档](docs/mcp_usage.md)
- [SKILL.md](SKILL.md) — 完整 Skill 列表和参数说明

## 开发计划

- [x] 核心架构搭建（BaseSkill + SkillManager）
- [x] 浏览器操作 Skills
- [x] 表单和断言 Skills
- [x] 标签页管理 Skills
- [x] 弹窗/iframe Skills
- [x] DOM 索引化 Skills
- [x] 多模态视觉分析
- [x] AI Agent 自然语言执行
- [x] 批量测试（JSON/YAML/Excel）
- [x] 测试报告生成（HTML/JSON/Markdown）
- [x] 性能优化（缓存 + LRU）
- [x] MCP Server 集成

## MCP配置：
将安装目录下的 `playwright-browsers` 目录添加到环境变量 `PLAYWRIGHT_BROWSERS_PATH` 中，即可在 MCP 中使用。
```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "D:\\browser_automation_skills\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "browser_automation_skills.mcp_server",
        "--headed"
      ],
      "cwd": "d:\\browser_automation_skills",
      "env": {
        "PLAYWRIGHT_BROWSERS_PATH": "d:\\browser_automation_skills\\.playwright-browsers"
      }
    }
  }
}