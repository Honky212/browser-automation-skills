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
# 基本浏览器操作
python examples/basic_test.py

# 表单测试
python examples/form_test.py

# 报告生成
python examples/report_demo.py

# 增强 Skills 演示
python examples/enhanced_skills_demo.py

# 高级用法（自定义 Skill、Page Object、数据驱动）
python examples/advanced_usage.py
```

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