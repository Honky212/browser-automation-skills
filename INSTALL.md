# Browser-Automation-Skills 安装说明

> 版本：`browser-automation_skills-1.5.1`
> 此版本已修复 1.5.0 在 Trae / Claude Code / Cline / CodeBuddy 等 MCP 客户端里
> "工具列表为空 / No tools yet" 的问题。请用这个 whl，不要用旧的 1.5.0。

---

## 0. 你会拿到什么

- `browser_automation_skills-1.5.1-py3-none-any.whl`（本包）
- 本安装说明

配置模板（`config.template.yaml`）和 MCP 配置示例（`mcp_config.json`）包里自带，
但包里那个 `mcp_config.json` 是旧布局的过时示例（路径写死、启动方式已不适用），
**不要直接照抄**，请用本文第 4 节给的配置。

---

## 1. 环境要求

- **Python >= 3.9**（建议 3.11）
- Windows / macOS / Linux 均可（本文以 Windows 为例，macOS/Linux 自行调整路径分隔符）
- 磁盘空间：Playwright 浏览器二进制约 300MB+

---

## 2. 安装步骤

### 2.1 建虚拟环境（推荐）

```powershell
# 选一个工作目录，例如 D:\bas
python -m venv .venv
.venv\Scripts\activate
```

### 2.2 安装 whl（会自动装依赖）

```powershell
pip install browser_automation_skills-1.5.1-py3-none-any.whl
```

依赖会自动装：`playwright>=1.40.0`、`mcp>=1.0.0,<2.0.0`、`pyyaml>=6.0`、`openai>=1.0.0`、`openpyxl>=3.0.0`。

> **⚠️ mcp 版本注意**：必须使用 `mcp>=1.0.0,<2.0.0`（推荐 1.29.0）。
> mcp 2.0.0+ 移除了 `@server.list_tools()` 装饰器 API，会导致启动报错：
> `AttributeError: 'Server' object has no attribute 'list_tools'`。
> 如已误装 2.x，执行 `pip install "mcp>=1.0.0,<2.0.0"` 降级即可。

### 2.3 安装 Playwright 浏览器（关键，易漏！）

pip 只装了 Playwright 的 Python 库，**浏览器二进制要单独下载**，否则所有浏览器工具会报
"找不到浏览器"：

```powershell
playwright install chromium
```

> 默认装到 `%LOCALAPPDATA%\ms-playwright`（Windows）。**不要额外设 `PLAYWRIGHT_BROWSERS_PATH`**，
> 让它走默认路径最省事——包里的启动器在没设该环境变量时会自动用这个默认位置。
> 如果你非要用自定义路径，记得 `playwright install` 和启动时的环境变量指向同一处。

> **⚠️ Playwright 版本与 Chromium 构建号严格绑定**（复用已有浏览器时务必注意）：
>
> | Playwright 版本 | 对应 Chromium 构建 | Chrome 版本 |
> |----------------|-------------------|-------------|
> | 1.59.x | `chromium-1223` | 148.0.7778.96 |
> | 1.62.x | `chromium-1234` | 151.0.7922.34 |
>
> 查看已有浏览器：`dir %LOCALAPPDATA%\ms-playwright`
>
> **复用本机已有浏览器有两种方式**：
>
> **方式A（推荐，免下载）**：任意 Playwright 版本 + 在 `config.yaml` 中配置 `browser.executable_path`
> 指向已有浏览器的可执行文件，例如：
> ```yaml
> browser:
>   executable_path: 'C:\Users\<用户名>\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe'
> ```
> 这样 Playwright 会直接使用该浏览器，绕开版本绑定检查，无需重新下载。
>
> **方式B**：安装与已有浏览器构建号匹配的 Playwright 版本（如已有 `chromium-1223` 则
> `pip install playwright==1.59.0`），然后正常跑 `playwright install chromium`（会秒过校验）。

---

## 3. 配置文件 config.yaml（可选，但推荐）

- **只列工具/做基础浏览器操作**：不配也能跑（用默认空配置）。
- **要用视觉分析 `analyze_page` / 自然语言任务 `execute_task`**：必须填 API key。

在你准备作为工作目录（cwd）的文件夹下，新建 `config.yaml`，内容如下（按需改 api_key）：

```yaml
# Browser-Automation-Skills 配置文件
browser:
  headless: false            # 调试时 false（可见窗口），稳定后可改 true
  window_size: { width: 1920, height: 1080 }
  timeout: 30000
  browser_type: chromium

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

screenshot:
  output_dir: "./screenshots"
  full_page: true

# 视觉模型（多模态页面分析，analyze_page 用）
vision:
  provider: "dashscope"     # 可选: openai, dashscope, aliyun, qwen
  model: "qwen3-vl-plus"
  api_key: ""                # ← 填你的 DashScope key，或留空走环境变量 DASHSCOPE_API_KEY
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 1024
  temperature: 0.1

# Agent（自然语言任务，execute_task 用）
agent:
  model: "deepseek-v4-flash"
  api_key: ""                # ← 填你的 key，或留空走环境变量 OPENAI_API_KEY / DASHSCOPE_API_KEY
  base_url: "https://api.deepseek.com"
  max_steps: 20
  max_retries: 3
  temperature: 0.1

cache:
  dom_max_size: 50
  dom_ttl: 60.0
  llm_max_size: 200
  llm_ttl: 3600.0
```

> 服务器按以下顺序找配置：`<cwd>/config.yaml` → `<cwd>/config/config.yaml` → 包内默认。
> 所以把 `config.yaml` 放在你启动时的工作目录下即可。

---

## 4. 在 MCP 客户端里配置（Trae / Claude Code / Cline / CodeBuddy 等）

### 通用 JSON 模板（请替换路径）

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "<你的venv路径>\\Scripts\\python.exe",
      "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
      "cwd": "<你的工作目录（放config.yaml的地方）>"
    }
  }
}
```

> 关键：**用 `-m browser_automation_skills.mcp_server`，不要用 `mcp_server.py` 文件路径**
> （1.5.x 起入口在包内部，项目根没有 mcp_server.py，用文件路径会报错）。
> 一般**不需要**设 `env`；浏览器走 Playwright 默认路径即可。

### Windows 示例（假设 venv 在 D:\bas\.venv，config 在 D:\bas）

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "d:\\browser_automation_skills\\.venv\\Scripts\\python.exe",
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
```

- **Trae**：把上面的 JSON 放进 `C:\Users\<你>\AppData\Roaming\Trae CN\User\mcp.json`（合并到已有的 `mcpServers` 里），然后在 MCP 面板重启该 server。
- **Claude Code / Cline / CodeBuddy**：按各自"添加 MCP Server"的位置填同样的 command / args / cwd。

---

## 5. 验证装好了

在客户端里该 server 应显示 **74 个工具**（navigate / click / screenshot / ... / execute_chain）。
若仍显示 "No tools yet"，确认你装的是 **1.5.1** 而非 1.5.0：

```powershell
pip show browser-automation-skills
```

---

## 6. 常见坑

| 现象 | 原因 / 解决 |
| --- | --- |
| 工具列表为空 / No tools yet | 装成 1.5.0 了，重装 1.5.1：`pip install --force-reinstall --no-deps browser_automation_skills-1.5.1-py3-none-any.whl` |
| 调浏览器工具报找不到浏览器 | 没装 Playwright 浏览器：跑 `playwright install chromium` |
| `execute_task` / `analyze_page` 报 401 / 无 key | `config.yaml` 里 `agent.api_key` / `vision.api_key` 没填 |
| 用包里的 `mcp_config.json` 启动报错 | 那是旧示例（用 `mcp_server.py` 文件路径），改用第 4 节的 `-m` 方式 |
| 改了配置不生效 | 在客户端里**重启**该 MCP server（不是改完就生效） |

---

## 7. 可选：命令行直接跑（不接 MCP 客户端时验证）

装包后会生成命令 `browser-automation-mcp`，等价于 `python -m browser_automation_skills.mcp_server`：

```powershell
browser-automation-mcp --headed
```

它会从 stdin 读 JSON-RPC、stdout 输出，方便手动测试。
```
