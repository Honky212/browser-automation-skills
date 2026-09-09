# API 参考文档

## 核心类

### BaseSkill

所有 Skill 的基类。

```python
class BaseSkill:
    """Skill 基类"""
    
    name: str           # Skill 名称（唯一标识）
    description: str    # Skill 描述
    
    def __init__(self, browser_context: BrowserContext):
        """初始化 Skill"""
        self.browser_context = browser_context
    
    async def run(self, **kwargs) -> SkillResult:
        """执行 Skill（子类必须实现）"""
        ...
```

### SkillResult

Skill 执行结果。

```python
@dataclass
class SkillResult:
    success: bool                    # 是否成功
    message: str                     # 结果消息
    data: Dict[str, Any] = {}        # 结果数据
    error: Optional[str] = None      # 错误信息
    execution_time: float = 0.0      # 执行时间（秒）
```

### SkillManager

Skill 管理器，负责注册和执行 Skills。

```python
class SkillManager:
    def __init__(self, browser_context: BrowserContext = None):
        """初始化 Manager"""
        ...
    
    def register(self, skill_class: Type[BaseSkill]):
        """注册一个 Skill 类"""
        ...
    
    async def execute(self, skill_name: str, **kwargs) -> SkillResult:
        """执行单个 Skill"""
        ...
    
    async def execute_chain(self, chain: List[Dict], stop_on_failure: bool = True) -> List[SkillResult]:
        """按顺序执行多个 Skills，并可选择在失败时停止"""
        ...
    
    def list_skills(self) -> List[Type[BaseSkill]]:
        """列出所有已注册的 Skills"""
        ...
    
    def list_skill_names(self) -> List[str]:
        """列出所有 Skill 名称"""
        ...
```

### create_manager

创建并预配置的 Skill Manager。

```python
def create_manager(browser_context: BrowserContext = None) -> SkillManager:
    """创建并预配置的 Skill Manager"""
    ...
```

## 浏览器操作 Skills

### navigate

导航到指定 URL。

```python
{"skill": "navigate", "params": {"url": "https://example.com"}}
```

**参数:**
- `url` (str): 目标 URL

**返回数据:**
- `url` (str): 当前 URL
- `title` (str): 页面标题
- `status` (int): HTTP 状态码

### click

点击页面元素。

```python
{"skill": "click", "params": {"selector": "#button", "timeout": 5000}}
```

**参数:**
- `selector` (str): CSS 选择器
- `timeout` (int): 超时时间（毫秒），默认 5000

### screenshot

截取页面截图。

```python
{"skill": "screenshot", "params": {"path": "screenshot.png", "full_page": true, "return_base64": false}}
```

**参数:**
- `path` (str): 保存路径
- `full_page` (bool): 是否截取全页，默认 False
- `return_base64` (bool): 是否返回 base64，默认 False

**返回数据:**
- `path` (str): 截图路径
- `base64` (str): base64 编码的截图（如果 return_base64=True）

### wait_for_element

等待元素出现。

```python
{"skill": "wait_for_element", "params": {"selector": ".loading", "timeout": 10000, "state": "visible"}}
```

**参数:**
- `selector` (str): CSS 选择器
- `timeout` (int): 超时时间（毫秒），默认 10000
- `state` (str): 等待状态 (attached/visible/hidden/detached)

### get_text

获取元素文本。

```python
{"skill": "get_text", "params": {"selector": "h1"}}
```

**参数:**
- `selector` (str): CSS 选择器
- `timeout` (int): 超时时间（毫秒），默认 5000

**返回数据:**
- `text` (str): 元素文本

### get_attribute

获取元素属性。

```python
{"skill": "get_attribute", "params": {"selector": "a", "attribute": "href"}}
```

**参数:**
- `selector` (str): CSS 选择器
- `attribute` (str): 属性名
- `timeout` (int): 超时时间（毫秒），默认 5000

**返回数据:**
- `attribute` (str): 属性名
- `value` (str): 属性值

### execute_js

执行页面 JavaScript。

```python
{"skill": "execute_js", "params": {"script": "() => 1 + 2"}}
```

**参数:**
- `script` (str): JavaScript 代码字符串，必须返回值
- `arg` (Any): 可选参数

**返回数据:**
- `result` (Any): JS 执行结果

### get_html

获取页面或元素 HTML。

```python
{"skill": "get_html", "params": {"selector": "body"}}
```

**参数:**
- `selector` (str): CSS 选择器（可选），不指定则返回整个页面 HTML
- `outer` (bool): 是否返回 `outerHTML`，默认 `False`

**返回数据:**
- `html` (str): HTML 内容

### get_current_page_info

获取当前 SkillManager 管理的页面信息。

```python
{"skill": "get_current_page_info", "params": {}}
```

**参数:**
- 无

**返回数据:**
- `url` (str): 当前页面 URL
- `title` (str): 当前页面标题
- `page_index` (int): 当前页面在上下文中的索引

### scroll_into_view

将元素滚动到可视区域。

```python
{"skill": "scroll_into_view", "params": {"selector": "#target"}}
```

**参数:**
- `selector` (str): CSS 选择器

### scroll_to

滚动页面到指定位置。

```python
{"skill": "scroll_to", "params": {"x": 0, "y": 500}}
```

**参数:**
- `x` (int): 水平坐标
- `y` (int): 垂直坐标

### focus

聚焦指定元素。

```python
{"skill": "focus", "params": {"selector": "#input"}}
```

**参数:**
- `selector` (str): CSS 选择器

### blur

使指定元素失去焦点。

```python
{"skill": "blur", "params": {"selector": "#input"}}
```

**参数:**
- `selector` (str): CSS 选择器

### double_click

双击页面元素。

```python
{"skill": "double_click", "params": {"selector": "#button"}}
```

**参数:**
- `selector` (str): CSS 选择器

### right_click

右键点击页面元素。

```python
{"skill": "right_click", "params": {"selector": "#button"}}
```

**参数:**
- `selector` (str): CSS 选择器

## 标签页管理 Skills

### open_new_tab

打开新标签页，并可选导航到指定 URL。

```python
{"skill": "open_new_tab", "params": {"url": "https://example.com"}}
```

**参数:**
- `url` (str): 可选，打开后导航的 URL

### close_tab

关闭当前标签页或指定标签页。

```python
{"skill": "close_tab", "params": {"page_index": 1}}
```

**参数:**
- `page_index` (int): 要关闭的标签页索引；若不指定则关闭当前页

### switch_tab

切换到指定标签页。

```python
{"skill": "switch_tab", "params": {"page_index": 1}}
```

**参数:**
- `page_index` (int): 标签页索引（从 0 开始）

### get_tabs

获取当前上下文中所有标签页信息。

```python
{"skill": "get_tabs", "params": {}}
```

**返回数据:**
- `tabs` (list): 每个标签页的索引、URL 和标题
- `tab_count` (int): 标签页总数

### close_other_tabs

关闭除当前页（或指定页）外的所有标签页。

```python
{"skill": "close_other_tabs", "params": {}}
```

**参数:**
- `keep_index` (int): 可选，保留的标签页索引；默认保留当前页

### get_page_info

获取页面信息。

```python
{"skill": "get_page_info", "params": {}}
```

**返回数据:**
- `url` (str): 当前 URL
- `title` (str): 页面标题

### wait

等待指定时间。

```python
{"skill": "wait", "params": {"seconds": 2}}
```

**参数:**
- `seconds` (float): 等待时间（秒），默认 1

### reload / go_back / go_forward

浏览器导航操作。

```python
{"skill": "reload", "params": {}}
{"skill": "go_back", "params": {}}
{"skill": "go_forward", "params": {}}
```

## 表单操作 Skills

### fill_input

填写输入框。

```python
{"skill": "fill_input", "params": {"selector": "#username", "value": "admin"}}
```

**参数:**
- `selector` (str): CSS 选择器
- `value` (str): 要填写的值
- `timeout` (int): 超时时间（毫秒），默认 5000

### type_text

模拟键盘逐字输入。

```python
{"skill": "type_text", "params": {"selector": "#search", "text": "hello", "delay": 100}}
```

**参数:**
- `selector` (str): CSS 选择器
- `text` (str): 要输入的文本
- `delay` (int): 每个字符之间的延迟（毫秒），默认 50

### select_option

选择下拉选项。

```python
# 按 value 选择
{"skill": "select_option", "params": {"selector": "#role", "value": "admin"}}

# 按 label 选择
{"skill": "select_option", "params": {"selector": "#role", "label": "管理员"}}

# 按 index 选择
{"skill": "select_option", "params": {"selector": "#role", "index": 0}}
```

### check_checkbox / uncheck_checkbox

勾选/取消勾选复选框。

```python
{"skill": "check_checkbox", "params": {"selector": "#remember"}}
{"skill": "uncheck_checkbox", "params": {"selector": "#remember"}}
```

### fill_form

批量填写表单。

```python
{"skill": "fill_form", "params": {
    "selector": "#login-form",
    "fields": {
        "username": "admin",
        "password": "123456",
        "remember": True
    }
}}
```

### submit_form

提交表单。

```python
{"skill": "submit_form", "params": {
    "form_selector": "#login-form",
    "submit_selector": "button[type=submit]"
}}
```

## 断言 Skills

### text_equals / text_contains

文本断言。

```python
{"skill": "text_equals", "params": {"selector": "h1", "expected": "Welcome"}}
{"skill": "text_contains", "params": {"selector": ".message", "expected": "成功", "case_sensitive": true}}
```

### element_exists / element_not_exists

元素存在断言。

```python
{"skill": "element_exists", "params": {"selector": "#header"}}
{"skill": "element_not_exists", "params": {"selector": "#error"}}
```

### element_visible / element_enabled / element_disabled

元素状态断言。

```python
{"skill": "element_visible", "params": {"selector": "#modal"}}
{"skill": "element_enabled", "params": {"selector": "#submit"}}
{"skill": "element_disabled", "params": {"selector": "#submit"}}
```

### url_contains / url_equals

URL 断言。

```python
{"skill": "url_contains", "params": {"expected": "/dashboard"}}
{"skill": "url_equals", "params": {"expected": "https://example.com/login"}}
```

### attribute_equals

属性断言。

```python
{"skill": "attribute_equals", "params": {
    "selector": "input[type=email]",
    "attribute": "type",
    "expected": "email"
}}
```

### count_elements

元素数量断言。

```python
{"skill": "count_elements", "params": {"selector": ".item", "expected_count": 5}}
```

### checkbox_checked

复选框状态断言。

```python
{"skill": "checkbox_checked", "params": {"selector": "#remember", "expected": true}}
```

## 报告模块

### TestReporter

测试报告生成器。

```python
from browser_automation_skills.reporter import TestReporter

reporter = TestReporter(output_dir="reports")

# 添加链执行结果
reporter.add_chain_result(
    test_name="登录测试",
    test_file="tests/test_login.py",
    chain_results=results,
    total_time=10.5
)

# 生成报告
reporter.print_summary()
files = reporter.save_all_reports()  # 生成 HTML 和 JSON 报告
```

### ScreenshotManager

截图管理器。

```python
from browser_automation_skills.screenshot_manager import ScreenshotManager

screenshot_mgr = ScreenshotManager(output_dir="screenshots")

# 保存截图
screenshot_mgr.save_screenshot(
    screenshot_bytes=bytes_data,
    test_name="登录测试",
    step_name="step_1",
    success=True
)

# 获取失败截图
failed = screenshot_mgr.get_failed_screenshots()