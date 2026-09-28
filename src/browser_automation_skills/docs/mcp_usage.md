# 如何使用 Browser-Automation-Skills MCP Server

## 概述

Browser-Automation-Skills MCP Server 将 70+ 个浏览器操作 Skills 暴露为 MCP 工具，让 AI 助手（如 Cline）可以直接调用它们来操作浏览器。

## 安装步骤

### 1. 安装依赖

```bash
# 方式一：安装 wheel（v1.5.0+，推荐）
pip install browser_automation_skills-1.5.0-py3-none-any.whl
playwright install chromium

# 方式二：从源码目录运行
cd D:\aitestui\browser-use-skill
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 MCP Server

在 Cline 的 MCP 配置文件中添加以下内容（通常在 `~/.cline/mcp.json` 或 VS Code 设置中）：

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "python",
      "args": ["-m", "browser_automation_skills.mcp_server", "--headed"]
    }
  }
}
```

> 自 v1.5.0 起 `mcp_server.py` 已移入包内，通过模块方式启动，无需设置 `PYTHONPATH`。
> 若从源码目录运行（不安装 wheel），可将 `args` 改为 `["D:\\aitestui\\browser-use-skill\\mcp_server.py"]`，并在 `env` 中设置 `PYTHONPATH` 指向源码目录。

### 3. 重启 Cline

配置完成后，重启 Cline 或 VS Code，MCP Server 会自动启动。

## 使用方式

### 方式一：直接告诉 Cline 操作浏览器

你只需用自然语言告诉 Cline 你要做什么，例如：

- "帮我打开浏览器，访问 https://www.google.com"
- "在百度搜索 'Cline AI'"
- "帮我登录 GitHub，用户名 test，密码 123456"
- "截图当前页面"

Cline 会自动调用 MCP 工具来完成这些操作。

### 方式二：指定具体操作

如果你想更精确地控制，可以指定具体的 Skill：

```
请使用 navigate 技能打开 https://example.com
然后点击 #login 按钮
填写 #username 输入框为 admin
```

## 可用的 MCP 工具列表（共 74 个）

| 分类 | 数量 | 工具 |
|---|---|---|
| 浏览器操作 | 20 | `navigate` `click` `screenshot` `wait_for_element` `get_text` `get_attribute` `get_page_info` `get_current_page_info` `execute_js` `get_html` `scroll_into_view` `scroll_to` `focus` `blur` `double_click` `right_click` `wait` `reload` `go_back` `go_forward` |
| 标签页管理 | 5 | `open_new_tab` `close_tab` `switch_tab` `get_tabs` `close_other_tabs` |
| 表单操作 | 12 | `fill_input` `type_text` `select_option` `check_checkbox` `uncheck_checkbox` `upload_file` `fill_form` `submit_form` `clear_input` `hover` `press_key` `set_date` |
| 断言验证 | 17 | `text_equals` `text_contains` `element_exists` `element_not_exists` `element_visible` `element_enabled` `element_disabled` `url_contains` `url_equals` `title_contains` `title_equals` `page_contains_text` `element_has_class` `element_selected` `attribute_equals` `count_elements` `checkbox_checked` |
| 弹窗 / iframe | 10 | `get_popup_pages` `switch_to_popup` `wait_for_popup` `click_in_popup` `fill_in_popup` `select_in_popup` `get_text_in_popup` `close_popup` `handle_iframe` `click_and_wait_popup` |
| DOM 索引 | 3 | `get_dom_snapshot` `click_by_index` `fill_by_index` |
| AI Agent | 2 | `execute_task` `execute_batch_testcases` |
| 多模态视觉 | 2 | `screenshot_vision` `analyze_page` |
| 缓存 / 性能 | 2 | `get_cache_stats` `clear_cache` |
| 链式执行 | 1 | `execute_chain` |

> 本表只列工具名。**每个工具的完整参数、默认值与可选枚举**以客户端里展开看到的 schema 为准
> （它由框架从技能签名自动生成），也可查 `SKILL.md` 或
> `docs/教你如何使用browser_automation_skills的全部功能.md` 第 8 章。

## 使用示例

### 示例 1：打开网页
```
用户：帮我打开百度
Cline：调用 navigate(url="https://www.baidu.com")
```

### 示例 2：搜索
```
用户：在百度搜索 "Cline AI"
Cline：
1. navigate(url="https://www.baidu.com")
2. fill_input(selector="#kw", value="Cline AI")
3. click(selector="#su")
```

### 示例 3：登录
```
用户：帮我登录 GitHub
Cline：
1. navigate(url="https://github.com/login")
2. fill_input(selector="#login_field", value="your_username")
3. fill_input(selector="#password", value="your_password")
4. click(selector="[type='submit']")
```

### 示例 4：链式执行
```json
{
  "steps": [
    {"skill": "navigate", "args": {"url": "https://example.com"}},
    {"skill": "click", "args": {"selector": "#login"}},
    {"skill": "fill_input", "args": {"selector": "#username", "value": "admin"}},
    {"skill": "screenshot", "args": {"path": "login_page.png"}}
  ]
}
```

## 注意事项

1. **选择器**：CSS 选择器（`#id`、`.class`、`tag[attr=value]`）或 XPath；定位不稳时改用 DOM 索引三件套（`get_dom_snapshot` + `click_by_index` / `fill_by_index`）。
2. **超时**：各技能默认值不同（页面操作 5~30 秒，展开工具 schema 可见），单次调用还受 `skill_timeout.per_skill_seconds` 约束。
3. **截图**：**始终落盘**。目录由 `screenshot.output_dir`（默认 `./screenshots`，相对 server 的 cwd）或 `output_dir` 参数决定；
   传入的 `path` **只作文件名**，其中的目录部分会被忽略。需要 base64 时另加 `return_base64=true`。
4. **多标签页**：索引从 0 开始，参数名是 `page_index`（不是 `index`）。
5. **浏览器模式**：默认无头（不可见），加 `--headed` 显示窗口。
6. **上下文隔离**：同一个 server 的所有请求共享一个浏览器实例与页面，不要并发驱动同一页面；
   需要硬隔离请配置多个 server 条目。

## 故障排除

### 问题 1：MCP Server 无法启动
- 检查 Python 环境是否正确安装
- 检查依赖是否安装：`pip install -r requirements.txt`
- 检查 Playwright 浏览器是否安装：`playwright install chromium`

### 问题 2：操作失败
- 检查选择器是否正确
- 检查页面是否加载完成
- 尝试增加超时时间

### 问题 3：截图不清晰
- 调整 `config/config.yaml` 中 `browser.window_size` 窗口大小设置
- 使用 `full_page=true` 获取完整页面截图