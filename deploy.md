# 部署指南（Windows）

本文档介绍如何在另一台 Windows 电脑上通过 wheel 包安装部署 `browser-automation-skills`。

---

## 一、前置条件

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11（64 位） |
| Python | ≥ 3.9（推荐 3.11） |
| 网络 | 可访问 PyPI 和 LLM API 服务 |

检查 Python 是否已安装：
```powershell
python --version
```

> 如未安装 Python，请前往 [python.org](https://www.python.org/downloads/) 下载安装，安装时勾选 **"Add Python to PATH"**。

---

## 二、获取安装包

从源机拷贝 wheel 文件到目标电脑：

```
browser_automation_skills-1.5.0-py3-none-any.whl
```

> 文件位于源机的 `dist/` 目录下。可通过 U 盘、网络共享、网盘等方式传输。
>
> **v1.5.0 起的变化**：所有内容（含 `mcp_server.py`、`browser_launcher.py`、`docs/`、`examples/`、`tests/`、`resources/` 等）均打包在 `browser_automation_skills` 包内，安装后不再有散落的顶层模块。

---

## 三、安装步骤

### 1. 安装 wheel 包

在 wheel 文件所在目录打开 PowerShell，执行：

```powershell
pip install browser_automation_skills-1.5.0-py3-none-any.whl
```

此命令会自动安装以下依赖：

| 依赖 | 用途 |
|------|------|
| `playwright>=1.40.0` | 浏览器自动化引擎 |
| `mcp>=1.0.0,<2.0.0` | MCP 协议支持（**必须 1.x，不兼容 2.0**） |
| `pyyaml>=6.0` | 配置文件解析 |
| `openai>=1.0.0` | LLM / 视觉模型客户端 |
| `openpyxl>=3.0.0` | Excel 测试用例解析 |

> **⚠️ mcp 版本警告**：本项目使用 mcp 1.x 的装饰器 API，与 mcp 2.0.0+ 不兼容。
> 如 pip 自动安装了 mcp 2.x，启动时会报 `AttributeError: 'Server' object has no attribute 'list_tools'`。
> 修复：`pip install "mcp>=1.0.0,<2.0.0"`（已验证 1.29.0 可用）

### 2. 安装 Playwright 浏览器运行时

```powershell
python -m playwright install chromium
```

> 此命令会下载 Chromium 浏览器到 `%LOCALAPPDATA%\ms-playwright`，约 150MB。

如需 Firefox 或 WebKit：
```powershell
python -m playwright install firefox webkit
```

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

### 3. 验证安装

```powershell
# 验证包已安装
python -c "import browser_automation_skills; print(browser_automation_skills.__version__)"

# 验证入口命令可用
browser-automation-mcp --help
```

预期输出版本号 `1.5.0` 即安装成功。

---

## 四、配置文件

### 1. 创建工作目录

选择一个目录作为运行工作区（例如 `D:\browser-skills`），在其中创建 `config` 子目录：

```powershell
mkdir D:\browser-skills\config
cd D:\browser-skills
```

### 2. 创建配置文件

在 `config\` 目录下创建 `config.yaml`，内容如下（请填入你自己的 API Key）：

```yaml
# 浏览器配置
browser:
  headless: false                    # true=无头后台运行，false=显示浏览器窗口
  # executable_path: ''             # 留空则使用 Playwright 自带浏览器
  window_size:
    width: 1920
    height: 1080
  timeout: 30000                     # 默认超时（毫秒）
  browser_type: chromium             # 可选: chromium, firefox, webkit

# 日志配置
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 截图配置
screenshot:
  output_dir: "./screenshots"
  full_page: true

# 视觉模型配置（用于多模态页面分析，如 analyze_page）
vision:
  provider: "dashscope"              # 可选: openai, dashscope, aliyun, qwen
  model: "qwen3-vl-plus"             # OpenAI: gpt-4o / DashScope: qwen-vl-max
  api_key: "sk-xxx"                  # 填入你的 API Key
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 1024
  temperature: 0.1

# Agent 配置（用于自然语言任务执行 execute_task / 批量测试）
agent:
  model: "deepseek-v4-flash"         # 兼容 OpenAI API 的模型均可
  api_key: "sk-xxx"                  # 填入你的 API Key
  base_url: "https://api.deepseek.com"
  max_steps: 20                      # 单任务最大步数
  max_retries: 3                     # 连续失败重试上限
  temperature: 0.1

# 缓存配置
cache:
  dom_max_size: 50
  dom_ttl: 60.0
  llm_max_size: 200
  llm_ttl: 3600.0
```

> **配置优先级**：代码显式传参 > config.yaml > 环境变量（`OPENAI_API_KEY` / `OPENAI_BASE_URL`）
>
> **提示**：安装包内自带配置模板，也可以直接从已安装的包中导出到工作目录（在工作目录下执行）：
> ```powershell
> python -c "import shutil, pathlib, browser_automation_skills as b; shutil.copy(pathlib.Path(b.__file__).parent / 'config.template.yaml', 'config/config.yaml')"
> ```

---

## 五、启动 MCP 服务

### 方式一：命令行直接启动

在工作目录（`config.yaml` 所在的上级目录）下执行：

```powershell
# 无头模式（后台运行，不显示浏览器窗口）
browser-automation-mcp

# 有头模式（显示浏览器窗口，便于调试）
python -m browser_automation_skills.mcp_server --headed

# 指定自定义配置文件路径
python -m browser_automation_skills.mcp_server --config D:\browser-skills\config\config.yaml --headed
```

> `browser-automation-mcp` 是安装 wheel 时自动注册的命令行入口（定义于 `pyproject.toml` 的 `[project.scripts]`）。
>
> 自 v1.5.0 起，`mcp_server.py` 已移入包内，模块启动方式由 `python -m mcp_server` 变更为 `python -m browser_automation_skills.mcp_server`。

### 方式二：作为 MCP 客户端的后端配置

如果你使用 Claude Desktop、Cursor 等 MCP 客户端，需在客户端的 MCP 配置文件中添加本服务。

配置示例（JSON 格式，路径按实际环境修改）：

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "python",
      "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
      "cwd": "D:\\browser-skills",
      "env": {
        "PYTHONPATH": "D:\\browser-skills"
      }
    }
  }
}
```

> **关键点**：
> - `cwd` 或 `PYTHONPATH` 需指向 `config.yaml` 所在的目录，否则服务找不到配置文件。
> - `command` 可使用 `python` 或 Python 解释器的完整路径（如 `C:\Python311\python.exe`）。
> - 如使用虚拟环境，`command` 指向虚拟环境的 python：`D:\browser-skills\.venv\Scripts\python.exe`。

---

## 六、功能验证

### 1. 验证浏览器基础操作

创建测试脚本 `test_install.py`：

```python
import asyncio
from browser_automation_skills.browser_launcher import BrowserLauncher
from browser_automation_skills import create_manager

async def main():
    launcher = BrowserLauncher(headless=True)
    context = await launcher.launch()
    manager = create_manager(browser_context=context)

    # 导航测试
    result = await manager.execute("navigate", url="https://www.baidu.com")
    print(f"导航: {result.success} - {result.message}")

    # 获取页面信息
    info = await manager.execute("get_page_info")
    print(f"页面信息: {info.data}")

    await launcher.close()
    print("验证通过！")

asyncio.run(main())
```

运行：
```powershell
python test_install.py
```

### 2. 验证 AI Agent（可选，需配置 LLM）

```python
import asyncio
from browser_automation_skills.browser_launcher import BrowserLauncher
from browser_automation_skills import create_manager
from browser_automation_skills.agent import BrowserAgent
from openai import AsyncOpenAI

async def main():
    launcher = BrowserLauncher(headless=True)
    context = await launcher.launch()
    manager = create_manager(browser_context=context)

    agent = BrowserAgent(
        skill_manager=manager,
        llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
        model="deepseek-v4-flash",
        max_steps=10,
    )

    result = await agent.execute_task("打开百度，搜索'AI测试'，截图保存")
    print(f"成功: {result.success}")
    print(f"步数: {len(result.steps_executed)}")

    await launcher.close()

asyncio.run(main())
```

---

## 七、常见问题

### Q1: `browser-automation-mcp` 命令找不到？

**原因**：Python Scripts 目录未加入 PATH。

**解决**：
```powershell
# 查看 Scripts 目录
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"

# 将输出的目录添加到系统 PATH，或直接用完整路径调用
python -m browser_automation_skills.mcp_server --headed
```

### Q2: Playwright 报错 "Executable doesn't exist"？

**原因**：未安装浏览器运行时。

**解决**：
```powershell
python -m playwright install chromium
```

如安装在非默认路径，设置环境变量：
```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "D:\playwright-browsers"
python -m playwright install chromium
```

### Q3: `config.yaml` 找不到？

**原因**：服务默认在工作目录的 `config/config.yaml` 查找配置。

**解决**：确保目录结构如下：
```
D:\browser-skills\           ← 工作目录（在此启动服务）
├── config\
│   └── config.yaml          ← 配置文件
└── screenshots\             ← 截图输出（自动创建）
```

或用 `--config` 参数指定路径：
```powershell
python -m browser_automation_skills.mcp_server --config D:\browser-skills\config\config.yaml
```

### Q4: LLM 调用失败？

**检查项**：
1. `config.yaml` 中 `agent.api_key` 和 `agent.base_url` 是否正确
2. 网络是否能访问对应的 API 服务
3. 模型名称是否被服务商支持
4. 也可通过环境变量配置：`OPENAI_API_KEY` 和 `OPENAI_BASE_URL`

### Q5: 启动报错 `AttributeError: 'Server' object has no attribute 'list_tools'`？

**原因**：安装了 mcp 2.0.0+，该版本移除了 1.x 的装饰器 API。

**解决**：
```powershell
pip install "mcp>=1.0.0,<2.0.0"
```

### Q6: 如何使用虚拟环境隔离？

```powershell
# 创建虚拟环境
python -m venv .venv

# 激活
.\.venv\Scripts\Activate.ps1

# 安装 wheel
pip install browser_automation_skills-1.5.0-py3-none-any.whl

# 安装浏览器
python -m playwright install chromium

# 启动（使用虚拟环境的 python）
.\.venv\Scripts\python.exe -m browser_automation_skills.mcp_server --headed
```

MCP 客户端配置中 `command` 改为虚拟环境路径：
```json
{
  "command": "D:\\browser-skills\\.venv\\Scripts\\python.exe",
  "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
  "cwd": "D:\\browser-skills"
}
```

---

## 八、目录结构参考

部署完成后的工作目录结构：

```
D:\browser-skills\
├── config\
│   └── config.yaml              # 配置文件（必填）
├── screenshots\                 # 截图输出目录（自动创建）
├── reports\                     # 测试报告输出目录（按需创建）
├── test_cases.json              # 批量测试用例（按需创建）
└── test_install.py              # 验证脚本（可选）
```

> `browser_automation_skills` 包（v1.5.0 起 `mcp_server`、`browser_launcher`、`docs/`、`examples/`、`tests/`、`resources/` 等均位于包内）已通过 pip 安装到 Python 环境中，无需拷贝源码到工作目录。

---

## 九、卸载

如需卸载：
```powershell
pip uninstall browser-automation-skills
```

清理浏览器运行时（可选）：
```powershell
python -m playwright uninstall chromium
```
