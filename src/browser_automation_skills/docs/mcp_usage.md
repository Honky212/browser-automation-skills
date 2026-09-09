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

## 可用的 MCP 工具列表

### 浏览器操作 (12个)
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `navigate` | 导航到 URL | `url`, `wait_until` |
| `click` | 点击元素 | `selector` |
| `screenshot` | 截图 | `path`, `full_page` |
| `wait_for_element` | 等待元素 | `selector`, `timeout` |
| `get_text` | 获取文本 | `selector` |
| `get_page_info` | 获取页面信息 | - |
| `reload` | 刷新页面 | - |
| `go_back` | 后退 | - |
| `go_forward` | 前进 | - |
| `wait` | 等待 | `seconds` |
| `get_attribute` | 获取属性 | `selector`, `attribute` |

### 标签页管理 (5个)
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `open_new_tab` | 打开新标签页 | `url` |
| `close_tab` | 关闭标签页 | `page_index` |
| `switch_tab` | 切换标签页 | `page_index` |
| `get_tabs` | 获取所有标签页 | - |
| `close_other_tabs` | 关闭其他标签页 | `keep_index` |

### 表单操作 (11个)
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `fill_input` | 填写输入框 | `selector`, `value`, `clear` |
| `type_text` | 逐字输入 | `selector`, `text`, `delay` |
| `select_option` | 选择下拉选项 | `selector`, `value/label/index` |
| `check_checkbox` | 勾选复选框 | `selector` |
| `uncheck_checkbox` | 取消勾选 | `selector` |
| `upload_file` | 上传文件 | `selector`, `file_path` |
| `fill_form` | 批量填写表单 | `fields` |
| `submit_form` | 提交表单 | `submit_selector` |
| `clear_input` | 清空输入框 | `selector` |
| `hover` | 鼠标悬停 | `selector` |
| `press_key` | 按键 | `key`, `selector` |

### 断言 Skills (13个)
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `text_equals` | 断言文本相等 | `selector`, `expected` |
| `text_contains` | 断言文本包含 | `selector`, `expected` |
| `element_exists` | 断言元素存在 | `selector` |
| `element_not_exists` | 断言元素不存在 | `selector` |
| `element_visible` | 断言元素可见 | `selector` |
| `element_enabled` | 断言元素可用 | `selector` |
| `element_disabled` | 断言元素禁用 | `selector` |
| `url_contains` | 断言 URL 包含 | `expected` |
| `url_equals` | 断言 URL 相等 | `expected` |
| `attribute_equals` | 断言属性相等 | `selector`, `attribute`, `expected` |
| `count_elements` | 断言元素数量 | `selector`, `expected_count` |
| `checkbox_checked` | 断言复选框勾选 | `selector` |

### 链式执行
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `execute_chain` | 执行多个操作 | `steps` (数组) |

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

1. **选择器**：使用 CSS 选择器，如 `#id`, `.class`, `tag[attr=value]`
2. **超时**：默认超时 10 秒，可根据需要调整
3. **截图**：截图会保存到指定路径，不指定则只返回 base64
4. **多标签页**：标签页索引从 0 开始
5. **浏览器模式**：默认无头模式（不可见），可加 `--headed` 参数显示浏览器窗口

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