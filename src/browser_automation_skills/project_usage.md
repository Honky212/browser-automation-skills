# Browser-Automation-Skills 项目使用指南

> 本文档整合自《项目介绍》与《批量测试》两份说明,经校对与重新排版。
> 适用版本:v1.5.0+ | 整理日期:2026-08-21

---

## 目录

- [一、项目定位](#一项目定位)
- [二、三层架构](#二三层架构)
- [三、关键组件解读](#三关键组件解读)
- [四、三种使用模式对照](#四三种使用模式对照)
- [五、版本演进](#五版本演进)
- [六、项目源码位置说明](#六项目源码位置说明)
- [七、批量测试实现详解](#七批量测试实现详解)
- [八、测试用例文件放置与调用](#八测试用例文件放置与调用)

---

## 一、项目定位

**Browser-Automation-Skills** 是一个基于 **Playwright + LLM** 的 AI 驱动浏览器自动化框架。

核心思想是把浏览器操作封装成 70+ 个可复用的 **Skill** 单元,再通过三条路径对外暴露:

1. 直接 Python API
2. MCP 工具
3. 自然语言 Agent

---

## 二、三层架构

```text
┌──────────────────────────────────────────────┐
│  外部调用方                                    │  ① Skill 直调  ② MCP 客户端  ③ 自然语言
├──────────────────────────────────────────────┤
│  对接层                                        │
│   • mcp_server.py     ← MCP stdio 服务        │
│   • agent.py          ← LLM Agent + 批量测试  │
│   • create_manager    ← 工厂函数              │
├──────────────────────────────────────────────┤
│  调度层                                        │
│   • manager.py (SkillManager) 注册/执行/链式  │
│   • performance.py   缓存 + 性能监控          │
├──────────────────────────────────────────────┤
│  能力层 (70+ Skills)                          │
│   base.py            ← BaseSkill 抽象基类      │
│   browser_skills.py   (20 浏览器 + 5 标签页)  │
│   form_skills.py      (12 表单)               │
│   assertion_skills.py (17 断言)               │
│   popup_skills.py     (10 弹窗/iframe)       │
│   dom_snapshot.py     (3 DOM 索引化)          │
│   vision.py           (2 多模态视觉)          │
├──────────────────────────────────────────────┤
│  基础设施层                                    │
│   browser_launcher.py  Playwright 启动/关闭  │
│   screenshot_manager / reporter              │
└──────────────────────────────────────────────┘
```

---

## 三、关键组件解读

### 1. base.py — 抽象基类

定义了所有 Skill 的契约:

- `SkillResult` dataclass:统一的执行结果(success / message / data / error / screenshot / execution_time)
- `BaseSkill(ABC)` 抽象类:子类只需实现 `run(**kwargs)`,基类提供:
  - `get_page()` — 智能获取当前 Page(优先级:`_page` → `manager.current_page` → `context.pages[0]` → 新建)
  - `execute(**kwargs)` — 自带异常捕获、计时、指数退避重试(由 `_retry_settings` 控制)
  - `wait_for_selector()` — 多窗口重试等待

### 2. manager.py — 调度引擎

`SkillManager` 负责:

- **注册**:`register()` 单个、`register_from_module/package` 批量
- **执行**:`execute(skill_name, **kwargs)` 带锁保护 `current_page` 读取,但执行时不持锁(支持并发)
- **链式**:`execute_chain()` 顺序执行多个 Skill,可 `stop_on_failure`
- **别名**:支持 `_skill_aliases` 让 LLM 用同义词调用
- 内置 `DOMSnapshotCache` / `LLMResponseCache` / `PerformanceMonitor`(来自 `performance.py`)

### 3. mcp_server.py — MCP 暴露层

把 Skills 变成 MCP 工具的关键。设计上很巧妙:**完全靠反射**而非手写工具列表。

- `_get_tool_input_schema()` 用 `inspect.signature(skill_class.run)` 自动从 `run()` 的函数签名生成 JSON Schema
- `_annotation_to_json_type()` 把 Python 类型注解(`Optional[T]`、`Union`、`Dict`、`List`…)转换为 JSON Schema 类型
- `_PARAM_HINTS` / `_PARAM_ENUMS` 为常见参数补充中文描述和枚举约束(`button`、`wait_until`、`cache_type` 等)
- **懒启动**:工具调用时若 `browser_context is None` 才调用 `launch_browser`
- 用 `self.server.create_initialization_options()` 自动声明 capabilities —— 这是修复 "No tools yet" 问题的关键点

### 4. browser_launcher.py — Playwright 封装

简洁的浏览器启动器:

- 支持 chromium / firefox / webkit
- 自定义 User-Agent
- 反自动化检测(`--disable-blink-features=AutomationControlled`)
- 有头模式不限制 viewport
- `close()` 按 context → browser → playwright 顺序清理,带异常保护

### 5. __init__.py — 工厂入口

`create_manager()` 是统一入口:

- 创建 `SkillManager`
- 设置默认重试策略(`max_attempts=3`,退避关键词含 `timeout` / `not found` 等)
- 一次性注册全部 70+ Skills

另外提供 `create_enhanced_manager()` 用于注入 LLM client 给 Agent Skills 使用。

---

## 四、三种使用模式对照

| 模式       | 调用方            | 抽象层级 | 适合场景               |
|------------|-------------------|----------|------------------------|
| Skill 直调 | Python 脚本      | 底层 API | 精确控制,CI 集成      |
| AI Agent   | 自然语言          | 中层     | 一次性任务,探索性测试 |
| 批量测试   | Excel/JSON/YAML   | 高层     | 回归测试套件,报告生成 |

---

## 五、版本演进

- **v1.5.0**:打包重构,所有内容(`mcp_server.py`、`browser_launcher.py`、docs/examples/tests)收进单一顶层包;入口点改为 `python -m browser_automation_skills.mcp_server`;`_load_config` 支持多级路径搜索
- **v1.5.1**:修复 MCP 握手时声明空 `ServerCapabilities()` 导致客户端显示 "No tools yet" —— 改用 `create_initialization_options()` 自动检测;修正 `PLAYWRIGHT_BROWSERS_PATH` 为 `.playwright-browsers`
- **v1.5.2**:`browser_skills.py` 的 `ScreenshotSkill.run` 被改造为强制读取 `config.yaml` 的 `screenshot.output_dir`,忽略调用方传入的 path 目录,保证所有截图归集到 `./screenshots`

---

## 六、项目源码位置说明

源码有两种布局,容易混淆:

- **打包源码(已安装)**:`D:\browser_automation_skills\.venv\Lib\site-packages\browser_automation_skills\*.py`
- **项目根**:只有 `repack.py`、`start_mcp.py`、测试脚本和打包好的 `.whl`

说明当前目录是一个**部署 / 二次打包工作区**,真正的开发源码在 wheel 内或上游仓库。

> **修改源码的约定**:改完需要用 `repack.py` 重新打包并重装,然后重启 MCP server 才能生效。

---

## 七、批量测试实现详解

### 7.1 涉及的组件

批量测试由 4 个组件协作完成,全部定义在 `agent.py`:

| 组件                          | 角色                                                                                       |
|-------------------------------|--------------------------------------------------------------------------------------------|
| `TestCaseParser`              | 用例解析器,把 JSON/YAML/Excel 转成 `List[TestCase]`                                       |
| `TestCase`                    | 用例数据模型(id / name / steps / expected_result / setup_url / timeout / priority)       |
| `BatchTestAgent`              | 批量执行引擎,顺序驱动每个用例                                                             |
| `ExecuteBatchTestCasesSkill`  | 把上述能力封装成一个 Skill,挂到 MCP 工具 `execute_batch_testcases`                        |

### 7.2 整体执行流程

```text
execute_batch_testcases(file_path, report_path?, ...)
   │
   ├─① TestCaseParser.from_file(file_path)     # 解析 → List[TestCase]
   │
   ├─② 创建 BatchTestAgent(manager, llm_client)
   │
   └─③ agent.execute_batch(test_cases)
         │
         for case in test_cases:
           │
           ├─ 防雪崩:连续失败 ≥ 5 → break,记录 stop_reason
           │
           ├─ _execute_single_case(case):
           │    ├─ 若有 setup_url → navigate(setup_url) + wait(2s)
           │    ├─ 拼装 task_prompt = steps + "\n预期结果: " + expected_result
           │    ├─ 创建 BrowserAgent(manager, llm)
           │    └─ browser_agent.execute_task(task_prompt)   ← 把自然语言交给 LLM 规划
           │
           ├─ 失败时按 screenshot_on_failure 截图保存到 screenshot_dir
           │
           └─ 累积到 BatchTestResult
         │
         └─④ BatchTestResult.generate_report(report_path)  # Markdown 报告
```

### 7.3 关键洞察:用例的 `steps` 字段是自然语言,不是代码

这是设计上最特殊的地方。`agent.py` 中的核心代码:

```python
task_prompt = case.steps
if case.expected_result:
    task_prompt = f"{task_prompt}\n\n预期结果: {case.expected_result}"
agent_result = await browser_agent.execute_task(task_prompt)
```

每个用例本质上是把一段自然语言任务交给 `BrowserAgent`,由 LLM 在每一步:

1. `_get_page_state()` 调用 `get_dom_snapshot` skill 抓当前页 DOM 快照(最多 50 个元素)
2. `_plan_next_step()` 让 LLM 看 (任务 + 页面状态 + 最近 5 步历史) 输出严格 JSON,指定下一步 `{skill, params, status}`
3. 通过 `manager.execute(plan.step.skill, **plan.step.params)` 执行
4. 防环检测:连续重复同一操作 ≥ 3 次,或连续失败 ≥ 3 次,立即停止

> **结论**:批量测试 = **外层循环遍历用例 + 内层用 LLM Agent 自动规划每一步**。只需写"做什么",不用写"怎么点"。

### 7.4 LLM 配置来源

`_create_llm_client()` 按优先级取值:

1. `config["llm_client"]`(代码注入,如 `create_enhanced_manager(llm_client=...)`)
2. `config.yaml` 的 `agent` 段(`api_key` + `base_url`)→ 创建 `AsyncOpenAI`
3. 环境变量 `OPENAI_API_KEY` / `OPENAI_BASE_URL`
4. 都没有 → 返回 None,执行时直接报 "LLM client not configured"

---

## 八、测试用例文件放置与调用

### 8.1 用例文件的位置不固定

`ExecuteBatchTestCasesSkill.run()` 只接收一个 `file_path` 参数,路径由调用方传入。因此:

> **用例文件放哪里都行,只要调用时传对路径即可。**

路径可以是:

- **绝对路径** —— 永远可靠,例如 `D:\browser_automation_skills\test_cases_baidu.json`
- **相对路径** —— 相对于"进程工作目录(cwd)"解析

### 8.2 `test_cases_baidu.json` 在项目中的分布

以 `test_cases_baidu.json` 为例,项目里实际存在三份:

| 路径                                                                  | 说明                          |
|----------------------------------------------------------------------|-------------------------------|
| `D:\browser_automation_skills\test_cases_baidu.json`                  | 工作目录文件(可直接使用)    |
| `D:\browser_automation_skills\.venv\Lib\site-packages\browser_automation_skills\test_cases_baidu.json` | 包内附带的同名示例 |
| `D:\browser_automation_skills\_repack\browser_automation_skills\test_cases_baidu.json` | 打包 staging 目录副本 |

三份内容完全一致(1296 字节,3 条百度搜索用例)。

### 8.3 两种调用方式

由于 MCP 配置里 `cwd` 是 `d:\browser_automation_skills`,所以在该目录下放文件,MCP 调用时既能用绝对路径也能用相对路径。

#### 方式 A:通过 MCP 工具调用

```yaml
工具: execute_batch_testcases
参数:
  file_path: "D:\\browser_automation_skills\\test_cases_baidu.json"
  report_path: "D:\\browser_automation_skills\\batch_report.md"
  max_steps_per_case: 20
  max_retries_per_case: 3
  screenshot_on_failure: true
```

#### 方式 B:Python 脚本调用

```python
import asyncio
from browser_automation_skills import create_manager
from browser_automation_skills.browser_launcher import BrowserLauncher


async def main():
    launcher = BrowserLauncher(headless=False)
    ctx = await launcher.launch()
    manager = create_manager(browser_context=ctx, config={})

    result = await manager.execute(
        "execute_batch_testcases",
        file_path=r"D:\browser_automation_skills\test_cases_baidu.json",
        report_path=r"D:\browser_automation_skills\batch_report.md",
    )
    print(result.message, result.data)
    await launcher.close()


asyncio.run(main())
```

> ⚠️ **前提条件**:无论方式 A 还是 B,`config/config.yaml` 里的 `agent` 段必须配好 `model` / `api_key` / `base_url`(目前默认指向 DeepSeek)。否则 LLM 客户端为 None,会在第二步直接报 "LLM client not configured"。

### 8.4 推荐的用例放置约定

虽然代码不限位置,但根据项目惯例(MCP 的 cwd),建议放在以下任一处:

1. **工作目录根的子目录**:`D:\browser_automation_skills\test_cases\`
   —— 适合集中管理业务用例,推荐做法
2. **包内 resources/**(随包分发,适合做示例):
   `.venv\Lib\site-packages\browser_automation_skills\resources\`

直接放在 `D:\browser_automation_skills\test_cases_baidu.json` 也能正常工作,只是和项目根的脚本混在一起,用例多了会显得杂乱。建议挪到 `test_cases\` 子目录下统一管理。
