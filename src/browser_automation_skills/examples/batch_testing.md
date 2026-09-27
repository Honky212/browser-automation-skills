# 批量测试示例

## 可运行示例（推荐先跑这个）

包内自带一个开箱即用的命令行示例，会启动浏览器、批量执行用例并生成 Markdown 报告：

```bash
# ① 开箱即跑：默认用例是纯确定性 actions（不调用 LLM，只需浏览器）
python -m browser_automation_skills.examples.batch_run_example

# ② 跑"自然语言 + 框架断言"的示例（需要 config 里配好 LLM）
python -m browser_automation_skills.examples.batch_run_example \
    --cases test_case_templates/test_cases_baidu.yaml --headed

# ③ 只解析用例、打印概要（不启动浏览器，可用于 CI 冒烟）
python -m browser_automation_skills.examples.batch_run_example --parse-only

# ④ 指定用例文件与报告路径
python -m browser_automation_skills.examples.batch_run_example \
    --cases my_cases.yaml --report reports/my_report.md
```

| 参数 | 说明 |
|------|------|
| `--cases` | 用例文件（`.yaml/.yml/.json/.xlsx`）；默认用包内示例用例 |
| `--sheet` | Excel 用例的 sheet 名 |
| `--report` | Markdown 报告输出路径（默认 `./batch_report.md`） |
| `--config` | 配置文件路径（默认依次找 `./config/config.yaml`、`./config.yaml`） |
| `--model` | 覆盖 config 里的 `agent.model` |
| `--max-steps` / `--max-retries` | 每条用例的步数与连续失败上限（默认 20 / 3） |
| `--headless` / `--headed` | 强制无头 / 有头模式（默认取 config） |
| `--parse-only` | 只解析并打印用例概要，不启动浏览器 |
| `--verbose` | 输出 DEBUG 日志 |

示例输出：

```text
[INFO] 共解析到 2 条用例：
  1. TC_DET_01  百度首页打开（确定性执行）
     模式=确定性(actions)，actions=1，assertions=2，setup=https://www.baidu.com，timeout=60s
[INFO] 配置文件: config\config.yaml
[INFO] 浏览器: type=chromium headless=False

========== 逐条结果 ==========
  [PASS] TC_DET_01 百度首页打开（确定性执行） | 确定性(用例声明 actions) | 5.2s | 断言 2/2 | 步数 1
  [PASS] TC_DET_02 百度搜索自动化测试（确定性执行） | 确定性(用例声明 actions) | 2.6s | 断言 2/2 | 步数 3

========== 汇总 ==========
总计: 2  通过: 2  失败: 0  通过率: 100.0%  耗时: 7.8s
报告已写入: batch_report.md
```

> 该示例功能与 MCP 工具 `execute_batch_testcases` 等价，但不受 MCP 客户端 60s 请求超时限制
> （批量执行通常需要数分钟）。
> 退出码：全部通过 `0`，有用例失败 `1`，用法/配置/解析错误 `2`。

## 前置条件

批量测试需要正确配置 `config.yaml` 中的 `agent` 段（model、api_key、base_url），
因为每条测试用例都通过 LLM Agent 自动规划步骤并执行。

```yaml
agent:
  model: "deepseek-v4-flash"     # 你的 LLM 模型
  api_key: "sk-xxx"              # API Key
  base_url: "https://api.deepseek.com"  # API 地址
  max_steps: 20
  max_retries: 3
  temperature: 0.1
```

## 用例文件格式

### JSON 格式（顶层为数组）

```json
[
  {
    "id": "TC_01",
    "name": "百度搜索测试",
    "steps": "打开百度，在搜索框输入'AI测试'，点击搜索，验证结果页包含'AI测试'",
    "expected_result": "搜索结果页显示相关结果",
    "priority": "high",
    "setup_url": "https://www.baidu.com",
    "timeout": 60
  }
]
```

### Excel 格式（支持中英文双表头）

| ID | 用例名称 | 操作步骤 | 预期结果 | 优先级 | 前置URL | 超时时间 |
|----|---------|---------|---------|--------|---------|---------|
| TC_01 | 百度搜索 | 打开百度，搜索"AI测试" | 显示搜索结果 | high | https://www.baidu.com | 60 |

### YAML 格式

```yaml
- id: TC_01
  name: 百度搜索测试
  steps: |
    打开百度，在搜索框输入'AI测试'，点击搜索，验证结果页包含'AI测试'
  expected_result: 搜索结果页显示相关结果
  setup_url: https://www.baidu.com
  timeout: 60
```

## 批量执行代码

```python
from browser_automation_skills import create_manager
from browser_automation_skills.agent import TestCaseParser, BatchTestAgent
from openai import AsyncOpenAI

manager = create_manager(browser_context=context, config=config)

# 读取测试用例
test_cases = TestCaseParser.from_file("test_cases.xlsx", sheet_name="登录模块")
# 也支持: from_json("cases.json"), from_yaml("cases.yaml")

# 创建批量执行 Agent（model 不传时自动从 config.yaml 读取）
agent = BatchTestAgent(
    skill_manager=manager,
    llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
    model="deepseek-v4-flash",       # 建议显式指定
    max_steps_per_case=20,
    max_retries_per_case=3,
    max_consecutive_failures=5,      # 连续失败 5 个用例后熔断
    screenshot_on_failure=True,
)

# 执行
result = await agent.execute_batch(test_cases)

# 查看结果
print(f"总计: {result.total}, 通过: {result.passed}, 失败: {result.failed}")
print(f"通过率: {result.pass_rate:.1f}%")

# 生成 Markdown 报告
result.generate_report("batch_report.md")
```

## 安全熔断机制

| 机制 | 默认值 | 说明 |
|------|--------|------|
| 连续失败熔断 | 5 次 | 连续失败 N 个用例后停止 |
| 每用例步数限制 | 20 步 | 防止 LLM 无限循环 |
| 每用例重试限制 | 3 次 | 单用例内连续失败 3 次停止 |
| 操作去重防环 | 开启 | 相同 skill+params 不重复执行 |
| 失败截图 | 开启 | 失败用例自动截图保存 |
