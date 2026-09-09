---
name: browser-automation-skills
description: "Playwright-based browser automation skill framework. Exposes MCP tools for navigation, clicks, form interactions, assertions, tab management, screenshots, chained steps, AI-driven task execution, batch testing, visual analysis, and DOM indexing."
---

# Browser Use Skill

browser-automation-skills 是一个基于 **Playwright + LLM** 的浏览器自动化测试 Skill 框架。它将浏览器操作封装为可复用的 Skill 单元，并支持 AI 驱动的自然语言任务执行、多模态视觉分析和批量测试。

## 适用场景

- 基于 Playwright 的网页导航、UI 交互、表单填写、断言、截图和标签页控制
- 通过 `execute_task` 用自然语言描述测试任务，由 AI Agent 自动规划并执行
- 通过 `execute_batch_testcases` 从 JSON/YAML/Excel 文件导入测试用例并批量执行
- 通过 `analyze_page` 使用多模态视觉模型（OpenAI GPT-4o / DashScope qwen-vl）分析页面内容
- 通过 `get_dom_snapshot` + `click_by_index` / `fill_by_index` 进行无需 CSS 选择器的元素交互

## 配置步骤

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 安装 Playwright 浏览器运行时：
   ```bash
   python -m playwright install chromium
   ```
3. 配置 `config/config.yaml`（Agent、Vision 模型的 API Key 等）
4. 启动 MCP 服务：
   ```bash
   python -m browser_automation_skills.mcp_server
   ```
5. 如果需要可见浏览器模式：
   ```bash
   python -m browser_automation_skills.mcp_server --headed
   ```

## 所有可用 Skill（70+）

### 浏览器操作（20 个）
| Skill | 功能 | 参数 |
|-------|------|------|
| `navigate` | 导航到指定 URL | `url`, `wait_until` |
| `click` | 点击页面元素 | `selector` |
| `screenshot` | 截取页面截图 | `path`, `full_page` |
| `wait_for_element` | 等待元素出现 | `selector`, `timeout` |
| `get_text` | 获取元素文本 | `selector` |
| `get_attribute` | 获取元素属性 | `selector`, `name` |
| `get_page_info` | 获取页面 URL、标题 | — |
| `get_current_page_info` | 获取当前页上下文信息 | — |
| `execute_js` | 执行页面 JavaScript | `script` |
| `get_html` | 获取页面或元素 HTML | `selector` |
| `scroll_into_view` | 将元素滚动到可视区域 | `selector` |
| `scroll_to` | 滚动页面到指定位置 | `x`, `y` |
| `focus` | 聚焦指定元素 | `selector` |
| `blur` | 失去元素焦点 | `selector` |
| `double_click` | 双击页面元素 | `selector` |
| `right_click` | 右键点击页面元素 | `selector` |
| `wait` | 等待指定时间 | `seconds` |
| `reload` | 刷新页面 | — |
| `go_back` | 浏览器后退 | — |
| `go_forward` | 浏览器前进 | — |

### 标签页管理（5 个）
| Skill | 功能 | 参数 |
|-------|------|------|
| `open_new_tab` | 打开新标签页 | `url`, `wait_until` |
| `close_tab` | 关闭指定标签页 | `index` |
| `switch_tab` | 切换到指定标签页 | `index` |
| `get_tabs` | 获取所有标签页信息 | — |
| `close_other_tabs` | 关闭其他标签页 | — |

### 表单操作（12 个）
| Skill | 功能 | 参数 |
|-------|------|------|
| `fill_input` | 填写输入框 | `selector`, `value` |
| `type_text` | 模拟键盘逐字输入 | `selector`, `text`, `delay` |
| `select_option` | 选择下拉选项 | `selector`, `value` 或 `label` |
| `check_checkbox` | 勾选复选框 | `selector` |
| `uncheck_checkbox` | 取消勾选复选框 | `selector` |
| `upload_file` | 上传文件（自动适配多种上传场景） | `selector`(可选), `file_path`, `button_text`(可选), `multiple`, `upload_trigger` |
| `fill_form` | 批量填写表单 | `fields` (dict) |
| `submit_form` | 提交表单 | `selector` |
| `clear_input` | 清空输入框 | `selector` |
| `hover` | 鼠标悬停 | `selector` |
| `press_key` | 模拟按键 | `key` |
| `set_date` | 设置日期控件 | `selector`, `date` |

### 断言（17 个）
| Skill | 功能 | 参数 |
|-------|------|------|
| `text_equals` | 断言文本等于指定值 | `selector`, `expected` |
| `text_contains` | 断言文本包含指定值 | `selector`, `expected` |
| `element_exists` | 断言元素存在 | `selector` |
| `element_not_exists` | 断言元素不存在 | `selector` |
| `element_visible` | 断言元素可见 | `selector` |
| `element_enabled` | 断言元素可交互 | `selector` |
| `element_disabled` | 断言元素已禁用 | `selector` |
| `url_contains` | 断言 URL 包含指定字符串 | `expected` |
| `url_equals` | 断言 URL 等于指定值 | `expected` |
| `title_contains` | 断言标题包含指定字符串 | `expected` |
| `title_equals` | 断言标题等于指定值 | `expected` |
| `page_contains_text` | 断言页面包含指定文本 | `expected` |
| `attribute_equals` | 断言属性等于指定值 | `selector`, `name`, `expected` |
| `count_elements` | 断言元素数量 | `selector`, `expected` |
| `checkbox_checked` | 断言复选框已勾选 | `selector` |
| `element_has_class` | 断言元素包含指定 class | `selector`, `class_name` |
| `element_selected` | 断言元素已选中 | `selector` |

### 弹窗/iframe 处理（10 个）
| Skill | 功能 | 参数 |
|-------|------|------|
| `get_popup_pages` | 获取所有弹窗页面 | — |
| `switch_to_popup` | 切换到弹窗页面 | `index` |
| `wait_for_popup` | 等待弹窗出现 | `timeout` |
| `click_in_popup` | 在弹窗中点击元素 | `selector` |
| `fill_in_popup` | 在弹窗中填写输入框 | `selector`, `value` |
| `select_in_popup` | 在弹窗中选择下拉选项 | `selector`, `value` |
| `get_text_in_popup` | 获取弹窗中元素文本 | `selector` |
| `close_popup` | 关闭弹窗 | `index` |
| `handle_iframe` | 在 iframe 中操作 | `selector`, `action`, `params` |
| `click_and_wait_for_popup` | 点击并等待弹窗 | `selector`, `timeout` |

### DOM 索引操作（3 个）
通过给 DOM 元素打索引号来操作，无需手写 CSS 选择器。

| Skill | 功能 | 参数 |
|-------|------|------|
| `get_dom_snapshot` | 获取页面可交互元素索引快照 | `readable`, `max_elements` |
| `click_by_index` | 通过索引号点击元素 | `index` |
| `fill_by_index` | 通过索引号填写输入框 | `index`, `value` |

---

## 多模态视觉 Skill（vision.py）

使用多模态大模型对页面截图进行分析，支持识别页面元素、布局、文本内容等。

### 配置（config.yaml）

```yaml
vision:
  provider: "dashscope"          # 可选: openai, dashscope, aliyun, qwen
  model: "qwen3-vl-plus"         # OpenAI: gpt-4o, gpt-4o-mini; DashScope: qwen-vl-max, qwen-vl-plus
  api_key: "sk-xxx"              # 留空则使用环境变量
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 1024
  temperature: 0.1
```

### 支持的视觉模型适配器

| 适配器 | 类名 | 支持模型 |
|--------|------|----------|
| OpenAI | `OpenAIVisionAdapter` | gpt-4o, gpt-4o-mini, gpt-4-turbo |
| DashScope | `DashScopeVisionAdapter` | qwen-vl-max, qwen-vl-plus, qwen3-vl-plus |
| Dummy | `DummyVisionAdapter` | 虚拟适配器，用于测试 |

### 可用 Skill

| Skill | 功能 | 参数 |
|-------|------|------|
| `screenshot_vision` | 截图并返回 Base64 编码 | `full_page` (bool) |
| `analyze_page` | 使用视觉模型分析页面内容 | `prompt` (str), `full_page` (bool), `model` (str) |

### 使用示例

**示例 1：截图并分析页面**

```json
{
  "skill": "analyze_page",
  "arguments": {
    "prompt": "这个页面上有哪些输入框？请列出它们的标签和位置。",
    "full_page": false,
    "model": "gpt-4o"
  }
}
```

**示例 2：Python 编程调用**

```python
from browser_automation_skills.vision import VisionSupport, OpenAIVisionAdapter

# 创建视觉分析器
adapter = OpenAIVisionAdapter(model="gpt-4o", api_key="sk-xxx")
vision = VisionSupport(adapter=adapter)

# 分析页面
result = await vision.analyze_page(
    page,
    prompt="找出页面中所有的按钮，并描述它们的功能"
)
print(result.description)
```

**示例 3：配合 Agent 使用自然语言**

```
请打开百度首页 (https://www.baidu.com)，截图，然后识别图片中"百度一下"按钮的位置
```

Agent 会自动调用 `navigate` → `screenshot_vision` → `analyze_page` 完成。

---

## AI Agent 与批量测试（agent.py）

### Agent 架构

```
自然语言任务
    │
    ▼
BrowserAgent.execute_task()
    │
    ├── 1. 获取页面状态 (get_dom_snapshot + URL + 标题)
    ├── 2. LLM 规划下一步 (返回 JSON: skill + params)
    ├── 3. SkillManager 执行该 Skill
    ├── 4. 防环检测 → 循环 1-4
    └── 5. 返回 AgentResult
```

### 配置（config.yaml）

```yaml
agent:
  model: "deepseek-v4-flash"     # LLM 模型（兼容 OpenAI API 的均可）
  api_key: "sk-xxx"              # 留空则使用环境变量 OPENAI_API_KEY
  base_url: "https://api.deepseek.com"
  max_steps: 20                  # 单任务最大步数
  max_retries: 3                 # 连续失败重试上限
  temperature: 0.1
```

### 可用 Skill

| Skill | 功能 | 参数 |
|-------|------|------|
| `execute_task` | 接收自然语言任务，AI 自动规划并执行 | `task` (str), `max_steps`, `max_retries` |
| `execute_batch_testcases` | 从文件批量导入并执行测试用例 | `file_path` (str), `file_type`, `sheet_name`, `report_path` |

### Python 编程使用

#### 单任务执行

```python
from browser_automation_skills import create_manager
from browser_automation_skills.agent import BrowserAgent
from openai import AsyncOpenAI

# 创建 Manager
manager = create_manager(browser_context=context, config=config)

# 创建 Agent
agent = BrowserAgent(
    skill_manager=manager,
    llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
    max_steps=20,
    max_retries=3,
    model="deepseek-v4-flash",
)

# 自然语言执行
result = await agent.execute_task("打开百度，搜索'AI测试'，验证搜索结果页包含'AI测试'")
print(f"成功: {result.success}")
print(f"执行步数: {len(result.steps_executed)}")
for step in result.steps_executed:
    print(f"  Step {step['step']}: {step['skill']}({step['params']})")
```

#### 通过对话/MCP 调用

```
请帮我执行任务：打开百度，搜索AI测试，截图保存
```

Agent 会自动调用 `execute_task` Skill。

---

### 批量测试

browser-automation-skills 支持从 **JSON / YAML / Excel** 文件导入多条测试用例，自动逐条执行并生成报告。

> **注意**：批量测试和单任务执行共用同一份 `agent` 配置。批量测试前请确保 `config.yaml` 中 `agent.model`、`agent.api_key`、`agent.base_url` 配置正确。
>
> `BatchTestAgent` 会优先使用传入的 `model` 参数，未传入时自动从 `config.yaml` 的 `agent.model` 读取，两者都未设置时默认使用 `gpt-4o`。

#### 批量执行流程

```
测试用例文件 (JSON/YAML/Excel)
    │
    ▼
TestCaseParser.from_file()       ← 解析为 TestCase 对象列表
    │
    ▼
BatchTestAgent.execute_batch()   ← 逐条执行
    │
    ├── 对每条用例：
    │   ├── setup_url 存在则先导航
    │   ├── 创建 BrowserAgent，将 steps 传给 LLM
    │   ├── LLM 逐步规划 + 执行
    │   ├── 失败时自动截图
    │   └── 记录结果（耗时、步数、失败原因）
    │
    ├── 安全熔断：连续失败 5 次自动停止
    └── 返回 BatchTestResult（通过率、详细列表、报告）
```

#### 安全机制

| 机制 | 默认值 | 说明 |
|------|--------|------|
| 连续失败熔断 | 5 次 | 连续失败 N 个用例后停止 |
| 每用例步数限制 | 20 步 | 防止 LLM 无限循环 |
| 每用例重试限制 | 3 次 | 单用例内连续失败 N 次停止 |
| 操作去重防环 | 开启 | 相同 skill+params 不重复执行 |
| 失败截图 | 开启 | 失败用例自动截图保存 |

#### 测试用例文件格式

##### Excel 格式（支持中英文双表头）

| ID | 用例名称 | 描述 | 操作步骤 | 预期结果 | 优先级 | 前置URL | 超时时间 |
|----|---------|------|---------|---------|--------|---------|---------|
| TC_01 | 百度搜索 | 验证搜索功能 | 打开百度，搜索"AI测试"，验证结果页包含"AI测试" | 搜索结果页显示相关结果 | high | https://www.baidu.com | 60 |
| TC_02 | 页面导航 | 验证页面跳转 | 打开 https://example.com，验证页面标题包含"Example" | 页面标题显示 Example Domain | medium | | 30 |

> **重点**：「操作步骤」列填写**自然语言**即可，无需写选择器或代码。Agent 会自动解析并执行。

##### JSON 格式

```json
[
  {
    "id": "TC_01",
    "name": "百度搜索测试",
    "description": "验证百度搜索功能",
    "steps": "打开百度，在搜索框输入'AI测试'，点击搜索，验证结果页包含'AI测试'",
    "expected_result": "搜索结果页显示相关结果",
    "priority": "high",
    "setup_url": "https://www.baidu.com",
    "timeout": 60
  },
  {
    "id": "TC_02",
    "name": "页面导航测试",
    "steps": "打开 https://example.com，验证页面标题包含 Example"
  }
]
```

##### YAML 格式

```yaml
- id: TC_01
  name: 百度搜索测试
  description: 验证百度搜索功能
  steps: 打开百度，在搜索框输入'AI测试'，点击搜索，验证结果页包含'AI测试'
  expected_result: 搜索结果页显示相关结果
  priority: high
  setup_url: https://www.baidu.com
  timeout: 60

- id: TC_02
  name: 页面导航测试
  steps: 打开 https://example.com，验证页面标题包含 Example
```

#### 批量测试 Python 代码

```python
from browser_automation_skills import create_manager
from browser_automation_skills.agent import TestCaseParser, BatchTestAgent
from openai import AsyncOpenAI

manager = create_manager(browser_context=context, config=config)

# 方式一：从 Excel 读取（推荐）
test_cases = TestCaseParser.from_excel("test_cases.xlsx")
# 指定工作表名
test_cases = TestCaseParser.from_excel("test_cases.xlsx", sheet_name="登录模块")

# 方式二：从 JSON 读取
test_cases = TestCaseParser.from_json("test_cases.json")

# 方式三：从 YAML 读取
test_cases = TestCaseParser.from_yaml("test_cases.yaml")

# 方式四：自动识别文件类型
test_cases = TestCaseParser.from_file("test_cases.xlsx")

# 创建批量执行 Agent（model 不传时自动从 config.yaml 读取）
agent = BatchTestAgent(
    skill_manager=manager,
    llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
    model="deepseek-v4-flash",       # ← 建议显式指定，与 config.yaml 保持一致
    max_steps_per_case=20,
    max_retries_per_case=3,
    max_consecutive_failures=5,
    screenshot_on_failure=True,
)

# 执行批量测试
result = await agent.execute_batch(test_cases)

# 查看结果
print(f"总计: {result.total}")
print(f"通过: {result.passed}")
print(f"失败: {result.failed}")
print(f"通过率: {result.pass_rate:.1f}%")
print(f"总耗时: {result.duration:.1f} 秒")

# 生成报告
result.generate_report("test_report.md")

# 遍历每个用例详情
for case in result.case_results:
    status = "✅" if case.success else "❌"
    print(f"{status} {case.test_case_id}: {case.test_case_name} ({case.duration:.1f}s)")
    if not case.success:
        print(f"   失败原因: {case.failure_reason}")
```

#### 通过对话/MCP 批量执行

只需指定文件路径，框架自动解析并执行：

```
请批量执行 d:/test_cases.xlsx 中的所有测试用例
```

Agent 会调用 `execute_batch_testcases(file_path="d:/test_cases.xlsx")`。

指定生成报告路径：

```
请批量执行 d:/test_cases.json，并将报告保存到 d:/report.md
```

---

## 链式执行

```json
{
  "skill": "execute_chain",
  "arguments": {
    "steps": [
      {"skill": "navigate", "params": {"url": "https://example.com"}},
      {"skill": "click", "params": {"selector": "button.login"}},
      {"skill": "fill_input", "params": {"selector": "input[name=account]", "value": "user"}},
      {"skill": "fill_input", "params": {"selector": "input[name=password]", "value": "pass"}},
      {"skill": "click", "params": {"selector": "button.submit"}},
      {"skill": "text_contains", "params": {"selector": ".welcome", "expected": "欢迎"}}
    ]
  }
}
```

## 性能优化

| Skill | 功能 | 参数 |
|-------|------|------|
| `get_cache_stats` | 获取缓存统计信息 | — |
| `clear_cache` | 清除所有缓存 | — |

框架内置三级缓存：
- **DOM 快照缓存**：避免重复获取页面 DOM，TTL 60 秒
- **LLM 响应缓存**：相同上下文跳过 LLM 调用，TTL 1 小时
- **LRU 淘汰策略**：防止缓存无限增长

## 注意事项

- 使用 MCP Skill 时需保持 MCP 服务进程（`browser_automation_skills.mcp_server` 模块）运行
- `execute_task` 和 `execute_batch_testcases` 都共用 `config.yaml` 中 `agent` 段的配置（model、api_key、base_url），请确保配置正确
- 如果 Python 代码中显式传入 `model` 参数，优先级高于 config.yaml 中的配置
- 建议在执行多个用例前后清理或重设页面状态
- 「操作步骤」请使用自然语言，由 Agent 自动规划执行

## 主要入口文件

- `browser_automation_skills/__init__.py`：所有 Skill 导出和 `create_manager()` 工厂函数
- `browser_automation_skills/agent.py`：`BrowserAgent`、`BatchTestAgent`、`TestCaseParser`
- `browser_automation_skills/vision.py`：多模态视觉适配器和 Skill
- `browser_automation_skills/dom_snapshot.py`：DOM 索引化 Skill
- `browser_automation_skills/manager.py`：SkillManager 注册和执行引擎
- `browser_automation_skills/mcp_server.py`：MCP 服务入口（源码树中为根目录 `mcp_server.py`，v1.5.0 起打包进包内）
