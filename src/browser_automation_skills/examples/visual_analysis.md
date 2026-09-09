# 视觉分析示例

## 场景 1：页面元素识别

### 目标
识别页面上的所有按钮及其功能

### 执行步骤
```python
# 使用视觉分析功能
result = await manager.execute(
    "analyze_page",
    prompt="识别页面上所有按钮及其功能描述",
    full_page=True
)

# 结果示例
"""
{
  "buttons": [
    {"text": "登录", "position": {"x": 100, "y": 200}, "function": "用户登录"},
    {"text": "注册", "position": {"x": 200, "y": 200}, "function": "用户注册"},
    {"text": "搜索", "position": {"x": 300, "y": 100}, "function": "执行搜索"}
  ]
}
"""
```

## 场景 2：页面布局分析

### 目标
分析页面布局结构，识别主要区域

### 执行步骤
```python
result = await manager.execute(
    "analyze_page",
    prompt="分析页面布局，识别导航栏、内容区、侧边栏、页脚等主要区域",
    full_page=True
)
```

## 场景 3：UI 差异检测

### 目标
检测两个页面之间的视觉差异

### 执行步骤
```python
# 截取基准页面
await manager.execute("navigate", url="https://example.com/v1")
await manager.execute("screenshot", path="screenshots/baseline.png", full_page=True)

# 截取测试页面
await manager.execute("navigate", url="https://example.com/v2")
await manager.execute("screenshot", path="screenshots/test.png", full_page=True)

# 分析差异
result = await manager.execute(
    "analyze_page",
    prompt="比较这两个页面的差异，列出所有视觉变化",
    images=["screenshots/baseline.png", "screenshots/test.png"]
)
```

## 场景 4：验证码识别（需要配置视觉模型）

### 目标
识别并提取验证码内容

### 执行步骤
```python
# 获取验证码图片
await manager.execute("navigate", url="https://example.com/captcha")
await manager.execute("screenshot", path="screenshots/captcha.png")

# 识别验证码
result = await manager.execute(
    "analyze_page",
    prompt="识别图片中的验证码文字，只返回数字和字母",
    images=["screenshots/captcha.png"]
)

# 使用识别结果
captcha_text = result.get("text", "")
await manager.execute("fill_input", selector="#captcha", value=captcha_text)
```

## 场景 5：OCR 文本提取

### 目标
从页面截图中提取文本内容

### 执行步骤
```python
# 截取页面
await manager.execute("screenshot", path="screenshots/page.png", full_page=True)

# OCR 识别
result = await manager.execute(
    "analyze_page",
    prompt="提取图片中的所有文本内容，按区域分组",
    images=["screenshots/page.png"]
)

# 提取的文本示例
"""
{
  "header": ["网站标题", "导航链接1", "导航链接2"],
  "content": ["段落1内容", "段落2内容"],
  "footer": ["版权信息", "联系方式"]
}
"""
```

## 视觉分析配置

### 必需配置
```yaml
vision:
  provider: "dashscope"
  model: "qwen3-vl-plus"
  api_key: "sk-xxx"
  timeout: 60
```

### 支持的视觉模型
| 模型 | 提供商 | 功能 |
|------|--------|------|
| qwen3-vl-plus | DashScope | 通用视觉理解、OCR |
| gpt-4o | OpenAI | 通用视觉理解、OCR |
| claude-3-opus | Anthropic | 通用视觉理解 |

## 最佳实践

### 1. 选择合适的截图范围
```python
# 全屏截图（适合页面分析）
await manager.execute("screenshot", full_page=True)

# 区域截图（适合特定元素）
await manager.execute("screenshot", selector="#captcha")

# 指定尺寸截图
await manager.execute("screenshot", clip={"x": 0, "y": 0, "width": 800, "height": 600})
```

### 2. 优化提示词
```python
# 清晰的指令
prompt = """
请分析这个页面截图：
1. 识别所有交互元素（按钮、链接、输入框）
2. 描述每个元素的位置和功能
3. 提供 CSS 选择器建议
"""
```

### 3. 错误处理
```python
try:
    result = await manager.execute("analyze_page", prompt="分析页面")
    if not result.success:
        # 降级处理：使用 DOM 分析
        await manager.execute("get_dom_snapshot")
except Exception as e:
    print(f"视觉分析失败: {e}")
```