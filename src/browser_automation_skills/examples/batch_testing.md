# 批量测试示例

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
