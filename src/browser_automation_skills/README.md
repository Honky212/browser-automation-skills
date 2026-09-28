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

```powershell
# ① 批量测试可运行示例（默认用例为确定性 actions，不调用 LLM）
python -m browser_automation_skills.examples.batch_run_example

# ② 只解析用例、打印概要（不启动浏览器，可用于冒烟）
python -m browser_automation_skills.examples.batch_run_example --parse-only

# ③ 跑自己的用例并指定报告（--headed 显示浏览器窗口）
python -m browser_automation_skills.examples.batch_run_example --cases my_cases.yaml --report reports/my_report.md --headed

# ④ 启动 MCP server（供 AI 客户端调用，列出 74 个工具）
python -m browser_automation_skills.mcp_server --headed
```

> 完整使用指南见 `docs/教你如何使用browser_automation_skills的全部功能.md`；
> `examples/` 内含 4 篇示例文档与 `test_case_templates/` 用例模板。

## 项目结构

```
browser_automation_skills/                     # 包目录（安装后在 site-packages 下）
├── __init__.py                        # 导出 + create_manager() / create_enhanced_manager()
├── base.py                            # BaseSkill 抽象类 + SkillResult + 产物路径工具
├── manager.py                         # SkillManager 注册/执行引擎
├── browser_skills.py                  # 浏览器操作 20 个 + 标签页 5 个
├── form_skills.py                     # 表单操作 12 个
├── assertion_skills.py                # 断言 17 个
├── popup_skills.py                    # 弹窗/iframe 10 个
├── dom_snapshot.py                    # DOM 索引化 3 个
├── agent.py                           # BrowserAgent / BatchTestAgent / TestCaseParser
│                                      #   + ExecuteTaskSkill / ExecuteBatchTestCasesSkill
├── vision.py                          # 多模态视觉（OpenAI / DashScope / Dummy 适配器）
├── mcp_server.py                      # MCP 服务入口（暴露 74 个工具）
├── browser_launcher.py                # Playwright 启动器
├── performance.py                     # 缓存 + 性能监控
├── promote.py                         # 录制动作 → 用例 YAML 固化（CLI）
├── reporter.py                        # HTML/JSON 测试报告
├── screenshot_manager.py              # 截图归档管理
├── config.template.yaml               # 配置模板（复制为 config/config.yaml 后填写）
├── docs/                              # 文档（含《教你如何使用…全部功能.md》）
├── examples/                          # 示例文档 + test_case_templates/ 用例模板
├── tests/                             # 单元测试（pytest）
└── resources/                         # 参考资料
```

> 构建脚本 `build_wheel.py` 与运行配置 `config/config.yaml` 位于**项目根（工作区）**而非包内；
> 包内 `config.template.yaml` 是可直接复制使用的模板。

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

## 用例执行模式：自然语言 / 确定性 actions / 录制回放

**一条用例走哪条路，由「用例文件 + 配置」决定，不由大模型自己决定。** 判定优先级：

| 优先级 | 触发条件 | 执行方式 | 是否调用 LLM |
|--------|----------|----------|--------------|
| **1** | 用例里声明了非空 `actions` | 按 `actions` 顺序执行 → 再执行 `assertions` 判定 | **❌ 不调用** |
| **2** | 无 `actions`，且 `agent.replay_recorded: true`，且存在 `recorded_actions/<用例ID>.actions.yaml` | 回放录制动作（含锚点重解析）→ 再执行 `assertions` 判定 | **❌ 不调用** |
| **3** | 以上都不满足 | `steps` 自然语言交给 LLM 逐步规划；若声明了 `assertions`，框架最后强制执行并判定 | ✅ 调用 |

报告会明确写出每条用例实际走了哪条路（`## 执行模式与审计` 章节）：

```text
- TC_01: 执行模式: LLM 规划；已录制动作: ./recorded_actions/TC_01.actions.yaml
- TC_03: 执行模式: 确定性执行（来源：用例声明 actions，不调用 LLM）
```

```yaml
# 模式 A：自然语言（判定仍由框架断言负责，措辞模糊也不会“假通过”）
- id: TC_01
  steps: "打开百度首页并验证标题包含'百度'"
  assertions:
    - {skill: title_contains, params: {expected: "百度"}}

# 模式 B：确定性 actions（不调用 LLM，推荐用于关键回归）
- id: TC_03
  steps: "搜索 AI技术发展趋势"          # 仅作可读说明
  actions:
    - {skill: get_dom_snapshot, params: {}}
    - {skill: fill_by_index,    params: {index: 13, value: "AI技术发展趋势"}}
    - {skill: click_by_index,   params: {index: 6}}
  assertions:
    - {skill: url_contains,   params: {expected: "wd="}}
    - {skill: title_contains, params: {expected: "百度搜索"}}
```

```yaml
# 模式 C：录制回放（模式 A 跑通后自动生成 actions 草稿，人工 review 后固化）
agent:
  record_actions: true      # 成功后录制到 recorded_actions/<用例ID>.actions.yaml
  replay_recorded: false    # 人工确认后置 true，已录制用例走确定性回放
  fallback_to_llm_on_action_failure: false   # 确定性失败时是否回退 LLM（默认 false，严格确定性）
```

回退开启后，报告会明确标注：`确定性执行（来源：用例声明 actions）失败 → ⚠️ 已回退 LLM 规划（回退原因: ...）`。

### 固化：`python -m browser_automation_skills.promote`

```bash
python -m browser_automation_skills.promote --cases <cases.yaml> --dry-run              # 先看 diff
python -m browser_automation_skills.promote --cases <cases.yaml> --with-assertions      # 原地固化（自动 .bak）
```

把 `recorded_actions/<用例ID>.actions.yaml` 写进用例文件的 `actions`（可选 `assertions`），
取代人工手抄；`execute_js` 等 audit 步骤照常固化（仅加注释标注 + 汇总告警，**不禁用**）。

详见包内文档 `browser_automation_skills/docs/stability_and_gates.md`。

## 运行测试

```powershell
# 跑全部测试（138 项；不联网、不启动浏览器）
python -m pytest -q

# 只跑某个文件
python -m pytest tests/test_manager.py -v

# 只解析用例走一遍（冒烟）
python -m browser_automation_skills.examples.batch_run_example --parse-only
```

> 需要真实浏览器的两个脚本（`tests/test_install.py`、`tests/test_screenshot_path.py`）不会被 pytest 自动收集，需手动运行：
> `python tests/test_install.py`

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

## MCP 配置

> 关键三条：① 用 `-m browser_automation_skills.mcp_server` 启动（**不要**写 `mcp_server.py` 文件路径）；
> ② `command` 指向装了本包的解释器；③ `cwd` 指向工作区根（配置文件与产物路径都以它为基准）。

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "<你的venv>\\Scripts\\python.exe",
      "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
      "cwd": "<工作区根>",
      "env": {
        "BROWSER_AUTOMATION_SKILLS_CONFIG": "<工作区根>\\config\\config.yaml"
      }
    }
  }
}
```

一般**不需要**设 `PLAYWRIGHT_BROWSERS_PATH`（默认走 `%LOCALAPPDATA%\ms-playwright`）；
只有自定义浏览器目录时才需要设置，且必须与 `playwright install` 时指向同一处。

各客户端的具体配置形状（Cline 的 `cwd` 嵌在 `transport` 内、Trae CN / CodeBuddy 用扁平结构）
见 `docs/教你如何使用browser_automation_skills的全部功能.md` 第 4 章。