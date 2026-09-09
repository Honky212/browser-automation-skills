# 基础工作流示例

## 示例 1：登录测试

### 测试目标
验证网站登录功能的正确性

### 执行步骤
```yaml
- id: TC_LOGIN_001
  name: 标准用户登录
  description: 验证有效凭据登录成功
  steps: |
    1. 导航到登录页面
    2. 输入用户名：test@example.com
    3. 输入密码：password123
    4. 点击登录按钮
    5. 验证跳转到首页
    6. 验证显示欢迎消息
  expected_result: 用户成功登录并进入首页
  priority: high
  setup_url: https://example.com/login
  timeout: 60
```

### 执行命令
```bash
python -c "
from agent.browser_agent import BrowserAgent
agent = BrowserAgent()
result = await agent.execute_task('帮我测试登录功能，用户名 test@example.com，密码 password123')
print(result)
"
```

## 示例 2：表单验证测试

### 测试目标
验证表单验证逻辑

### 执行步骤
```yaml
- id: TC_FORM_001
  name: 必填字段验证
  description: 验证表单必填字段提示
  steps: |
    1. 导航到注册页面
    2. 直接点击提交按钮（不填写任何字段）
    3. 验证显示用户名必填提示
    4. 验证显示邮箱必填提示
    5. 验证显示密码必填提示
  expected_result: 所有必填字段提示正确显示
  priority: medium
  setup_url: https://example.com/register
  timeout: 45
```

## 示例 3：搜索功能测试

### 测试目标
验证搜索功能正常工作

### 执行步骤
```yaml
- id: TC_SEARCH_001
  name: 关键词搜索
  description: 验证搜索结果包含关键词
  steps: |
    1. 导航到首页
    2. 在搜索框输入"AI测试"
    3. 点击搜索按钮
    4. 等待搜索结果加载
    5. 验证结果列表包含"AI测试"相关内容
    6. 验证结果数量大于0
  expected_result: 搜索结果正确显示
  priority: high
  setup_url: https://example.com
  timeout: 30
```