# 快速入门指南

本指南将帮助你快速上手 Browser-Automation-Skills 框架。

## 环境要求

- Python 3.9+
- Playwright

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd browser-automation-skills
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 安装浏览器

```bash
playwright install chromium
```

## 第一个测试

### 创建测试文件

创建 `my_first_test.py`:

```python
import asyncio
from playwright.async_api import async_playwright
from browser_automation_skills import create_manager

async def main():
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # 创建 Skill Manager
        manager = create_manager(browser_context=context)
        
        # 执行测试链
        results = await manager.execute_chain([
            # 导航到百度
            {"skill": "navigate", "params": {"url": "https://www.baidu.com"}},
            
            # 搜索框输入
            {"skill": "fill_input", "params": {
                "selector": "#kw",
                "value": "Browser-Automation-Skills"
            }},
            
            # 点击搜索按钮
            {"skill": "click", "params": {"selector": "#su"}},
            
            # 等待搜索结果
            {"skill": "wait_for_element", "params": {
                "selector": "#content_left",
                "timeout": 10000
            }},
            
            # 验证搜索结果
            {"skill": "text_contains", "params": {
                "selector": "#content_left",
                "expected": "Browser"
            }},
            
            # 截图
            {"skill": "screenshot", "params": {
                "path": "search_result.png"
            }},
        ])
        
        # 打印结果
        for i, result in enumerate(results):
            status = "✓" if result.success else "✗"
            print(f"步骤 {i+1}: [{status}] {result.message}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### 运行测试

```bash
python my_first_test.py
```

## 使用 pytest 运行

### 创建测试类

创建 `tests/test_my_test.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio

class TestBaiduSearch:
    async def test_search(self, manager):
        results = await manager.execute_chain([
            {"skill": "navigate", "params": {"url": "https://www.baidu.com"}},
            {"skill": "fill_input", "params": {"selector": "#kw", "value": "test"}},
            {"skill": "click", "params": {"selector": "#su"}},
            {"skill": "wait_for_element", "params": {"selector": "#content_left", "timeout": 10000}},
        ])
        assert all(r.success for r in results)
```

### 运行测试

```bash
pytest tests/test_my_test.py -v
```

## 常用 Skills 速查

### 浏览器操作
```python
# 导航
{"skill": "navigate", "params": {"url": "https://example.com"}}

# 点击
{"skill": "click", "params": {"selector": "#button"}}

# 等待元素
{"skill": "wait_for_element", "params": {"selector": ".loading", "timeout": 5000}}

# 获取文本
{"skill": "get_text", "params": {"selector": "h1"}}

# 截图
{"skill": "screenshot", "params": {"path": "screenshot.png"}}
```

### 表单操作
```python
# 填写输入框
{"skill": "fill_input", "params": {"selector": "#username", "value": "admin"}}

# 选择下拉选项
{"skill": "select_option", "params": {"selector": "#role", "value": "admin"}}

# 勾选复选框
{"skill": "check_checkbox", "params": {"selector": "#remember"}}
```

### 断言
```python
# 文本包含
{"skill": "text_contains", "params": {"selector": ".message", "expected": "成功"}}

# 元素存在
{"skill": "element_exists", "params": {"selector": "#header"}}

# URL 包含
{"skill": "url_contains", "params": {"expected": "/dashboard"}}
```

## 下一步

- 查看 [Skills 完整列表](../README.md#已实现的-skills36个)
- 查看 [示例代码](../examples/)
- 查看 [API 文档](api_reference.md)