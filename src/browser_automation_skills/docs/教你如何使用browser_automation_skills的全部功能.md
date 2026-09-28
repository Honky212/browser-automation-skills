# 教你使用 browser_automation_skills 的全部功能（小白版）

> - **适用版本**：1.5.6（本文所有工具、参数、默认值、产物路径都以当前安装包**实测**为准）
> - **本项目位置**：`D:\BaiduNetdiskDownload\browser_automation_skills`
> - **怎么读这份文档**
>   - 只想先跑起来 → 直接看 [第 0 章](#第-0-章-先跑起来5-分钟) + [第 2 章](#第-2-章-把它装好环境准备)
>   - 只想让 AI 帮我操作浏览器 → [第 4 章](#第-4-章-用法一接进-mcp-客户端最常用)
>   - 想写测试用例做回归 → [第 7 章](#第-7-章-用法四批量测试重点)
>   - 查"某个工具的参数怎么填" → [第 8 章](#第-8-章-全部-74-个工具速查表)
>   - 遇到报错 → [第 10 章 FAQ](#第-10-章-常见问题排查faq)

---

## 目录

- [第 0 章 先跑起来（5 分钟）](#第-0-章-先跑起来5-分钟)
- [第 1 章 这是什么、能干什么](#第-1-章-这是什么能干什么)
- [第 2 章 把它装好（环境准备）](#第-2-章-把它装好环境准备)
- [第 3 章 配置文件 config.yaml 完全解读](#第-3-章-配置文件-configyaml-完全解读)
- [第 4 章 用法一：接进 MCP 客户端（最常用）](#第-4-章-用法一接进-mcp-客户端最常用)
- [第 5 章 用法二：Python 脚本直调（最精确）](#第-5-章-用法二python-脚本直调最精确)
- [第 6 章 用法三：自然语言任务 execute_task](#第-6-章-用法三自然语言任务-execute_task)
- [第 7 章 用法四：批量测试（重点）](#第-7-章-用法四批量测试重点)
- [第 8 章 全部 74 个工具速查表](#第-8-章-全部-74-个工具速查表)
- [第 9 章 用例怎么写才稳（最佳实践）](#第-9-章-用例怎么写才稳最佳实践)
- [第 10 章 常见问题排查（FAQ）](#第-10-章-常见问题排查faq)
- [第 11 章 注意事项与边界（必读）](#第-11-章-注意事项与边界必读)
- [附录 A 常用命令速查](#附录-a-常用命令速查)
- [附录 B 相关文档索引](#附录-b-相关文档索引)

---

## 第 0 章 先跑起来（5 分钟）

不用理解原理，先看到效果。全程只有 3 步。

### 第 1 步：确认环境（复制粘贴运行）

打开 PowerShell，逐行执行：

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills
.\myvenv\Scripts\python.exe -c "import browser_automation_skills as b; print('版本', b.__version__)"
```

看到 `版本 1.5.6` 就说明包已装好。

```powershell
.\myvenv\Scripts\python.exe -m playwright --version
```

能看到版本号就说明浏览器驱动就绪。若报错，去 [第 2 章](#第-2-章-把它装好环境准备)。

### 第 2 步：只解析用例，不开浏览器（最快的自检）

```powershell
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example --parse-only
```

这个命令**不启动浏览器、不需要 API Key**，只把包内自带示例用例读出来打印。能正常打印用例清单，说明框架本体没问题。

### 第 3 步：真跑一次批量测试（10 秒左右）

```powershell
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example
```

会发生什么：

1. 启动一个无头 Chromium；
2. 执行 2 条**确定性用例**（按用例里写好的 `actions` 逐步执行，**不调用大模型、不花 token**）；
3. 在**当前目录**生成 `batch_report.md`，并打印通过率。

打开 `batch_report.md`，你会看到 `## 概要`、`## 详细结果`、`## 断言证据`、`## 执行模式与审计` 四个章节 —— 这就是这个项目最终交付的东西：**一份可追溯的测试报告**。

> 到这里你就已经用完了"批量测试"这条主链路。剩下的章节是把它接到 AI 客户端、写自己的用例、以及排查问题。

---

## 第 1 章 这是什么、能干什么

### 1.1 一句话理解

它是一个**用 Playwright 操作浏览器的工具箱**，把"打开网页、点按钮、填表单、断言结果、截图"这些动作封装成 **74 个标准工具（MCP 工具）**，然后：

- 你可以让 **AI 客户端**（Cline / Trae CN / CodeBuddy / Claude Code）直接调用这些工具帮你操作浏览器；
- 你也可以在 **Python 脚本**里逐条调用，做精确的自动化；
- 你还可以写一份**用例文件**（JSON / YAML / Excel），一条命令批量跑完并出报告。

### 1.2 74 个工具的分类地图

| 分类 | 数量 | 干什么 | 典型工具 |
|---|---|---|---|
| 浏览器操作 | 25 | 导航、点击、截图、滚动、执行 JS、标签页管理 | `navigate`、`click`、`screenshot`、`switch_tab` |
| 表单操作 | 12 | 填输入框、下拉选择、勾选、上传文件、日期控件 | `fill_input`、`select_option`、`upload_file` |
| 断言验证 | 17 | 判断"结果对不对"（文本/元素/URL/标题/属性/数量） | `title_contains`、`element_exists`、`page_contains_text` |
| 弹窗 / iframe | 10 | 处理 `window.open` 新窗口、iframe 内部元素 | `wait_for_popup`、`click_in_popup`、`handle_iframe` |
| DOM 索引 | 3 | **不用写 CSS 选择器**，直接按快照编号点元素 | `get_dom_snapshot`、`click_by_index` |
| AI Agent | 2 | 自然语言任务、批量用例执行 | `execute_task`、`execute_batch_testcases` |
| 多模态视觉 | 2 | 截图交给视觉大模型"看图回答" | `screenshot_vision`、`analyze_page` |
| 缓存 / 性能 | 2 | 查看和清理 DOM、LLM 缓存 | `get_cache_stats`、`clear_cache` |
| 链式执行 | 1 | 一次调用跑多步，减少往返 | `execute_chain` |

> 完整参数表（含默认值与可选枚举）见 [第 8 章](#第-8-章-全部-74-个工具速查表)。

### 1.3 四种用法怎么选

| 用法 | 入口 | 适合谁 / 什么场景 | 成本 |
|---|---|---|---|
| **A. MCP 客户端** | 在 Cline/Trae 里说人话 | 探索性操作、一次性任务、"帮我看看这个页面" | 每次都要 AI 参与，慢 |
| **B. Python 脚本** | `create_manager()` + `manager.execute()` | 精确控制、接入你自己已有的 CI/脚本 | 无 AI 成本 |
| **C. 自然语言 Agent** | `execute_task` | 任务步骤模糊、页面会变、不想写选择器 | 调 LLM，有 token 成本 |
| **D. 批量测试** | `execute_batch_testcases` 或命令行 | 回归测试套件、要出报告、要长期维护 | 取决于用例模式（可做到 0 token） |

**新手推荐路线**：第 0 章跑通 → 第 4 章接进 AI 客户端玩一玩 → 第 7 章写自己的批量用例 → 需要精确定位时回来看第 5 章。

> 一个关键认知：**A/B/C 都是"操作浏览器"，D 是"用前三种方式跑一堆用例并出报告"。** 学 D 之前先会用 A 或 C，思路会顺很多。

---

## 第 2 章 把它装好（环境准备）

### 2.1 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| Python | **3.9 以上**（实测 3.12 可用） | 建议 3.11 / 3.12 |
| `mcp` 库 | **必须 `>=1.0.0,<2.0.0`** | ⚠️ mcp 2.x 不兼容，会报 `'Server' object has no attribute 'list_tools'` |
| Playwright 浏览器 | Chromium 二进制约 300MB+ | pip 装的是**库**，浏览器要**单独下载** |
| 磁盘 | 预留 1GB | 浏览器 + 依赖 + 截图 |

### 2.2 安装（四种情况，对号入座）

**情况 A：你要用现成的这套（本机就是这种）** —— 什么都不用装，直接用 `myvenv`：

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills
.\myvenv\Scripts\python.exe -c "import browser_automation_skills as b; print(b.__version__)"
```

**情况 B：换一台新电脑，用打好的 wheel 安装**

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install browser_automation_skills-1.5.6-py3-none-any.whl   # 在 dist\ 或项目根下
playwright install chromium
```

**情况 C：从源码安装（要改代码时用）**

源码在 `src\browser_automation_skills`，打包脚本是项目根的 `build_wheel.py`：

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills
.\myvenv\Scripts\python.exe build_wheel.py                 # 产出 dist\browser_automation_skills-1.5.6-py3-none-any.whl
.\myvenv\Scripts\python.exe -m pip install --no-deps --force-reinstall dist\browser_automation_skills-1.5.6-py3-none-any.whl
```

> ⚠️ **改了源码必须重新打包 + 重装才生效**。`myvenv` 里装的是 `site-packages` 下的**副本**，不是指向 `src` 的链接。
>
> 只做临时验证可以绕过重装：设 `$env:PYTHONPATH="D:\BaiduNetdiskDownload\browser_automation_skills\src"`，让 Python 优先加载源码。

**情况 D：只有 `requirements.txt`**

```powershell
pip install -r requirements.txt
playwright install chromium
```

### 2.3 验证清单（三条命令，全过才算装好）

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills

# ① 包版本
.\myvenv\Scripts\python.exe -c "import browser_automation_skills as b; print(b.__version__)"

# ② MCP 工具数（应输出 74）
.\myvenv\Scripts\python.exe -c "from browser_automation_skills import create_manager; m=create_manager(browser_context=None); print('技能数:', len(m._skills), '+ execute_chain = ', len(m._skills)+1)"

# ③ 用例解析（不开浏览器）
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example --parse-only
```

### 2.4 浏览器二进制的两种放置方式

| 方式 | 怎么做 | 适用 |
|---|---|---|
| **默认位置（推荐）** | `playwright install chromium`，装到 `%LOCALAPPDATA%\ms-playwright` | 最省事，不用设任何环境变量 |
| **指定位置** | 设环境变量 `PLAYWRIGHT_BROWSERS_PATH`，且 `playwright install` 与启动时指向**同一处** | 想统一管理浏览器文件 |

> 本机 `config\config.yaml` 里用 `browser.executable_path` 直接指向已存在的 Chrome：
> `C:\Users\10503\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe`
> 这样连 `playwright install` 都能省掉 —— 复用本机已有浏览器。

### 2.5 本机现状速查（先记住这张表，后面章节都会用到）

| 名称 | 路径 |
|---|---|
| 工作区（也建议作为 MCP 的 cwd） | `D:\BaiduNetdiskDownload\browser_automation_skills` |
| 源码 | `src\browser_automation_skills\` |
| 虚拟环境解释器 | `myvenv\Scripts\python.exe` |
| 配置文件 | `config\config.yaml` |
| 启动 MCP 的批处理 | `start_mcp.bat` |
| 打好的安装包 | `dist\browser_automation_skills-1.5.6-py3-none-any.whl` |
| 历史产物（旧行为残留） | 工作区根的 `screenshots\`、`recorded_actions\` |

---

## 第 3 章 配置文件 config.yaml 完全解读

### 3.1 配置文件放在哪

框架按**固定顺序**查找，命中第一个就用（实测行为）：

1. 环境变量 `BROWSER_AUTOMATION_SKILLS_CONFIG` 指定的文件（最可靠，推荐在 MCP 客户端里显式设置）
2. 从**包所在位置**逐级向上找 `config/config.yaml`
3. 从**当前工作目录（cwd）**找 `config/config.yaml` / `config.yaml`

本机命中的是第 2 条：包在 `myvenv\Lib\site-packages\browser_automation_skills`，向上 3 级就是工作区根，于是
`D:\BaiduNetdiskDownload\browser_automation_skills\config\config.yaml` 生效。

> 全找不到时**不报错**，用内置默认值 —— 但需要 Key 的功能（`execute_task`、`analyze_page`）会在调用时报"没有 Key"。

### 3.2 各配置段说明

下面按 `config/config.yaml` 里的顺序讲。**标 ⭐ 的是新手必须关心的。**

#### ① `browser` —— 浏览器本身 ⭐

```yaml
browser:
  headless: false                 # false=显示浏览器窗口；true=后台运行
  executable_path: 'C:\...\chrome.exe'   # 指定浏览器可执行文件；注释掉则用 Playwright 自带
  window_size: { width: 1920, height: 1080 }
  timeout: 30000                  # 页面操作默认超时（毫秒），对 导航/点击 等真正生效
  browser_type: chromium          # chromium / firefox / webkit
```

- **调试期建议 `headless: false`**：能亲眼看到 AI 在点哪里，出问题一目了然。
- 稳定后再改 `true`（省资源、可无人值守）。
- `executable_path` 指向本机已有 Chrome 时，可跳过 `playwright install chromium`。

#### ② `logging` —— 日志

```yaml
logging:
  level: INFO        # DEBUG 会打印每一步细节，排查时改成 DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

MCP 场景下日志走 **stderr**（不污染 JSON-RPC 协议），所以在客户端里能看到。

#### ③ `screenshot` —— 单张截图的默认目录 ⭐

```yaml
screenshot:
  output_dir: "./screenshots"    # 相对路径 → 相对 MCP server 的 cwd 解析
  full_page: true
```

- 这是**普通 `screenshot` 工具调用**（不在批量用例里）时的落盘目录。
- 相对路径按 **server 的 cwd** 解析；写成绝对路径也能用。
- 该目录必须在"允许工作区"内，否则会被拒绝（见 `artifact_routing`）。

#### ④ `artifact_routing` —— 产物路径边界（v1.5.6 新增，可选）⭐

```yaml
artifact_routing:
  allowed_roots: ["."]     # 允许写产物的根目录（相对 cwd）；默认只有工作区根
```

**它解决什么问题**：防止"用例文件路径"或"报告路径"把文件写到工作区之外（比如 `C:\Windows\Temp`）。

- 默认 `["."]` = 只允许工作区根及其子目录。
- 要把产物放到工作区外面时，在这里追加绝对路径，例如：
  ```yaml
  artifact_routing:
    allowed_roots: [".", "D:\\test-artifacts"]
  ```
- 越界时不是静默落错地方，而是**直接报错拒绝**（错误信息里会列出当前允许的根目录）。

> 另外：`screenshot.output_dir` 和 `agent.record_dir` 若写成**绝对路径**，会被自动视为额外允许根，老配置不会失效。

#### ⑤ `vision` —— 视觉模型（`analyze_page` / `screenshot_vision` 用）

```yaml
vision:
  provider: "dashscope"        # openai / dashscope / aliyun / qwen
  model: "qwen3-vl-plus"       # OpenAI: gpt-4o、gpt-4o-mini；DashScope: qwen-vl-max、qwen3-vl-plus
  api_key: ""                  # 留空则读环境变量 DASHSCOPE_API_KEY / OPENAI_API_KEY
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 1024
  temperature: 0.1
```

用途：把页面截图发给"看得懂图"的大模型，回答"这个页面上有哪些输入框"这类问题。
**不填 key 也能用其它 72 个工具**，只有这两个视觉工具会失败。

#### ⑥ `agent` —— 大模型与稳定性开关（最重要的一段）⭐

拆成三部分看。

**(a) 模型三件套**（`execute_task`、批量测试都要用）

```yaml
agent:
  model: "deepseek-v4-flash"
  api_key: "sk-xxx"                              # 留空则读 OPENAI_API_KEY / DASHSCOPE_API_KEY
  base_url: "https://api.deepseek.com"
  max_steps: 20          # 单条任务最多规划多少步（防跑飞）
  max_retries: 3         # 连续失败几次就放弃
  temperature: 0.1       # 越低越稳定，自动化场景别调高
```

> 只要用例声明了 `actions`（确定性执行），**完全不调用大模型** —— 此时这三项没配好也能跑。

**(b) 稳定性与"通过可信度"开关**（v1.5.5 起新增，决定报告可不可信）

| 配置项 | 默认 | 作用 | 新手建议 |
|---|---|---|---|
| `require_assertion` | 本机 `true` | **断言硬门禁**：没有断言证据 / 最后一次断言失败 → 不允许判定通过 | **保持 true** |
| `assertion_gate_retries` | 1 | 被门禁拦下后，允许模型补救执行断言的次数 | 1 |
| `step_timeout` | 60 | 单个技能调用超时（秒），0=不限 | 60 |
| `case_timeout` | 120 | 单条用例总超时（秒），**用例文件里的 `timeout` 优先** | 120 |
| `llm_retries` | 3 | LLM 调用失败 / 返回非法 JSON 的重试次数 | 3 |
| `isolate_pages` | true | 每条用例新建一个页面，避免用例间互相污染 | true |
| `retry_failed_cases` | 0 | 失败用例自动重跑次数。**开启会掩盖真实缺陷** | CI 保持 0 |
| `assertion_settle_ms` | 3000 | 断言前先等页面稳定（毫秒），避免"URL 变了但内容还没渲染"的误判 | 3000 |
| `assertion_retries` | 3 | 框架断言的"最终满足"重试次数 | 3 |
| `assertion_retry_interval_ms` | 500 | 上述重试间隔 | 500 |

**(c) 录制与回放**（把"能跑通的一次"固化成"每次都能跑"）

| 配置项 | 默认 | 作用 |
|---|---|---|
| `record_actions` | 本机 `true` | **用例成功后**，把实际执行过的步骤录到 `<用例所在目录>/recorded_actions/<用例ID>.actions.yaml` |
| `replay_recorded` | false | 置 `true` 后：没写 `actions` 的用例，若存在对应录制文件，就走**确定性回放**（不调 LLM） |
| `record_dir` | `./recorded_actions` | 录制目录。⚠️ **批量执行时会被自动改成 `<用例所在目录>/recorded_actions`**，此处的相对路径只在 `promote` 等独立工具里生效 |
| `continue_on_action_failure` | false | 确定性执行中某步失败后，是否继续执行后面的步骤（false=失败即停） |
| `fallback_to_llm_on_action_failure` | 本机 `true` | 确定性执行失败后是否自动回退给 LLM 规划兜底。`true` 更稳但结果不再是纯确定性；**CI 门禁建议 false** |

> 一句话理解 (c)：**让机器先"学一遍"，之后就不需要大模型了** —— 这是把测试从"每次 30 秒 + 花 token"变成"每次 7 秒 + 零成本"的关键。

#### ⑦ `skill_policy` —— 技能策略（三种态度）

```yaml
skill_policy:
  execute_js: audit     # allow（放行）/ audit（放行但在报告里披露）/ deny（禁用）
```

推荐把 `execute_js` 设为 `audit`：有些页面元素真的只能用 JS 点，但这是"绕过了真实 UI"的降级手段，
报告里的 `## 执行模式与审计` 会明确标出来，方便人工 review。

#### ⑧ `skill_retry` / `skill_timeout` —— 重试与超时预算（稳定性关键）

```yaml
skill_retry:
  max_attempts: 2        # 单个技能失败后重试次数（含首次）
  backoff: 0.5           # 线性退避基数（秒）
  retry_on: ["timeout", "timed out", "not found", "failed to", "timeout waiting"]

skill_timeout:
  per_skill_seconds: 30              # 单个技能单次执行硬超时
  selector_wait_budget_seconds: 6.0  # ★ 单个选择器等待的"总"预算
  selector_timeout_ms: 3000          # 单次 wait_for_selector 超时
  exempt_skills: [execute_task, execute_batch_testcases, analyze_page, screenshot_vision]
```

**为什么要有 `selector_wait_budget_seconds`**：老版本是"技能重试 3 次 × 选择器重试 3 次 × 每次 10 秒"，
一个不存在的元素能白等近 1 分钟。现在加了这个总预算后，最坏也就 `max_attempts × 6 秒 ≈ 12 秒`。

#### ⑨ `cache` —— 缓存（省时间、省 token）

```yaml
cache:
  dom_max_size: 50      # DOM 快照缓存条数
  dom_ttl: 60.0         # 有效期（秒）
  llm_max_size: 200     # LLM 响应缓存条数
  llm_ttl: 3600.0       # 有效期（秒）
```

页面结构变了但结果不对时，可以先 `clear_cache` 或把 `dom_ttl` 调小。

### 3.3 API Key 怎么填（三种常见服务）

| 服务 | `base_url` | `model` 示例 | Key 从哪来 |
|---|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash` | platform.deepseek.com |
| 阿里云百炼 / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3-vl-plus`（视觉）、`qwen-max` | 百炼控制台 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` | platform.openai.com |

优先级：**配置文件里的 `api_key` > 环境变量**（`OPENAI_API_KEY` / `DASHSCOPE_API_KEY`）。

> ⚠️ **安全提醒**：`config/config.yaml` 已被 `.gitignore` 排除，**不要把真实 Key 提交到仓库**。
> 要分享配置就给对方 `config.template.yaml`（包里自带，全是空值）。

### 3.4 一份"能跑起来的最小配置"

只有浏览器操作 + 确定性批量用例，一个字都不用配 Key：

```yaml
browser:
  headless: false
  timeout: 30000
  browser_type: chromium

screenshot:
  output_dir: "./screenshots"

agent:
  require_assertion: true
  isolate_pages: true
```

要加自然语言能力，再补上 `agent.model / api_key / base_url` 三行即可。

> **改完配置必须重启 MCP server**（改完不会自动生效，这是新手最容易踩的坑之一）。

---

## 第 4 章 用法一：接进 MCP 客户端（最常用）

### 4.1 原理一句话

MCP 让 AI 客户端（Cline / Trae / CodeBuddy / Claude Code）能**直接调用这 74 个工具**。
你正常说人话，AI 自己决定调 `navigate`、`click` 还是 `fill_input`。

```
你："帮我在百度搜一下 browser-automation-skills"
      ↓
AI 客户端 ──MCP 协议──> browser_automation_skills.mcp_server（本地进程）
      ↓                        ↓
  看到 74 个工具          真正驱动 Playwright 操作浏览器
```

### 4.2 配置写法（四大客户端）

**通用原则（先记住这 3 条）**：

1. 启动方式固定为 `-m browser_automation_skills.mcp_server`，**不要**写成 `mcp_server.py` 文件路径；
2. `command` 指向**装了本包的那个解释器**：本机是 `myvenv\Scripts\python.exe`；
3. `cwd` 一定要指向**工作区根** `D:\BaiduNetdiskDownload\browser_automation_skills`（原因见 4.3）。

**Cline（4.1.19 实测：`cwd` 嵌在 `transport` 里）**

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "transport": {
        "type": "stdio",
        "command": "D:\\BaiduNetdiskDownload\\browser_automation_skills\\myvenv\\Scripts\\python.exe",
        "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
        "cwd": "D:\\BaiduNetdiskDownload\\browser_automation_skills",
        "env": {
          "BROWSER_AUTOMATION_SKILLS_CONFIG": "D:\\BaiduNetdiskDownload\\browser_automation_skills\\config\\config.yaml"
        }
      },
      "disabled": false,
      "autoApprove": [],
      "timeout": 60
    }
  }
}
```

> ⚠️ 批量测试常超过 60 秒，建议把 `timeout` 调大，或改用命令行方式跑批量（见 [7.4](#74-怎么触发批量执行三种入口)）。

**Trae CN / CodeBuddy（扁平结构，`cwd` 与 `command` 同级）**

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "D:\\BaiduNetdiskDownload\\browser_automation_skills\\myvenv\\Scripts\\python.exe",
      "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
      "cwd": "D:\\BaiduNetdiskDownload\\browser_automation_skills",
      "env": {
        "BROWSER_AUTOMATION_SKILLS_CONFIG": "D:\\BaiduNetdiskDownload\\browser_automation_skills\\config\\config.yaml"
      },
      "disabled": false
    }
  }
}
```

- Trae CN 的配置文件一般在：`C:\Users\<你>\AppData\Roaming\Trae CN\User\mcp.json`
- CodeBuddy / Claude Code：按各自"添加 MCP Server"的入口填同样的 command / args / cwd。

**也可以完全不用 `cwd`**：前提是显式给 `BROWSER_AUTOMATION_SKILLS_CONFIG` 指定配置文件绝对路径。
两个都给最稳。

### 4.3 `cwd` 为什么这么重要

`cwd`（工作目录）决定了三件和你息息相关的事：

| 受 `cwd` 影响的东西 | 说明 |
|---|---|
| 找 `config/config.yaml` | 找不到就退回默认值（可能没有 API Key） |
| 相对路径解析 | `screenshot.output_dir: "./screenshots"`、用例文件相对路径都按 `cwd` 解析 |
| **产物落点** | 默认截图目录、批量产物的"允许工作区"边界都以 `cwd` 为基准 |

**配错的典型症状**：截图出现在 `D:\Microsoft VS Code\screenshots` 或某个莫名其妙的地方 —— 那就是 `cwd` 没配对。

### 4.4 怎么跟 AI 说话（决定成败）

**✅ 好例子（明确、可验证）**

```
请用 navigate 打开 https://www.baidu.com，
然后 get_dom_snapshot 看有哪些元素，
告诉我页面标题是什么。
```

```
请在百度搜索 "AI 测试"，搜索完成后：
1. 用 url_contains 断言 URL 含 wd=
2. 用 page_contains_text 断言页面含 "AI 测试"
3. 截图保存为 baidu_search.png
```

**❌ 坏例子（模糊、无法判定）**

```
帮我测一下这个网站正不正常
```
→ 什么叫"正常"？AI 无法给出可判定的结论。

```
随便点点看有没有 bug
```
→ 没有目标，AI 会乱点，还容易触发防爬。

**经验总结**：**把"要验证什么"说清楚**。AI 擅长执行"打开→操作→检查某个具体事实"，
不擅长替你定义"什么算通过"。

### 4.5 验证接好了

1. 重启客户端（Cline：在 MCP 面板里点 Restart；Trae/CodeBuddy：重启 IDE 或该 server）。
2. 在 MCP 面板里应显示 **74 个工具**。
3. 试一句："帮我用 navigate 打开 https://example.com，然后告诉我页面标题"。
   - 成功 → 你会看到浏览器窗口（因为有 `--headed`）并返回 "Example Domain"。
   - 显示 `No tools yet` → 见 [第 10 章 FAQ](#第-10-章-常见问题排查faq)。

---

## 第 5 章 用法二：Python 脚本直调（最精确）

### 5.1 最小骨架（复制就能跑）

新建 `my_first_test.py`（放在工作区根）：

```python
# -*- coding: utf-8 -*-
import asyncio
from pathlib import Path
import yaml

from browser_automation_skills import create_manager
from browser_automation_skills.browser_launcher import BrowserLauncher

ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8")) or {}


async def main():
    bc = CONFIG.get("browser", {}) or {}
    vp = bc.get("window_size", {}) or {}

    # ① 启动浏览器
    launcher = BrowserLauncher(
        headless=False,                                  # True 则不显示窗口
        viewport={"width": vp.get("width", 1920), "height": vp.get("height", 1080)},
        browser_type=bc.get("browser_type", "chromium"),
        executable_path=bc.get("executable_path"),        # 可为 None，用 Playwright 自带
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        disable_automation=True,                          # 降低被识别为机器人的概率
        default_timeout=bc.get("timeout"),                # 让 config 的 timeout 生效
    )
    context = await launcher.launch()

    try:
        # ② 创建 SkillManager（注册全部 73 个技能）
        manager = create_manager(browser_context=context, config=CONFIG)

        # ③ 执行单个技能
        r = await manager.execute("navigate", url="https://www.baidu.com")
        print("navigate:", r.success, r.message)

        # ④ 链式执行：一次调用跑多步
        results = await manager.execute_chain([
            {"skill": "get_dom_snapshot", "params": {}},
            {"skill": "fill_by_index", "params": {"index": 13, "value": "browser automation"}},
            {"skill": "click_by_index", "params": {"index": 6}},
            {"skill": "wait_for_element", "params": {"selector": "#content_left", "timeout": 10000}},
            {"skill": "url_contains", "params": {"expected": "wd="}},
            {"skill": "screenshot", "params": {"path": "search.png", "full_page": True}},
        ])
        for i, res in enumerate(results, 1):
            print(f"  步骤{i}: {'OK ' if res.success else 'FAIL'} {res.message[:70]}")
    finally:
        await launcher.close()          # 一定要关，否则浏览器进程残留


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills
.\myvenv\Scripts\python.exe my_first_test.py
```

### 5.2 两种调用方式对比

| 方式 | 写法 | 特点 |
|---|---|---|
| `execute(技能名, **参数)` | `manager.execute("click", selector="#su")` | 单步调用，参数直接展开；技能级重试/超时自动生效 |
| `execute_chain([{skill, params}, ...])` | 见上面示例 | 一次调用跑多步；`stop_on_failure=True`（默认）时遇失败即停 |

> 两种方式都会自动套用 `skill_retry` 重试与 `skill_timeout` 超时预算。

### 5.3 返回值 `SkillResult` 怎么读

```python
r = await manager.execute("get_text", selector="h1")

r.success        # bool   —— 这一步是否成功
r.message        # str    —— 人类可读的结果描述（报告里用的就是它）
r.data           # dict   —— 结构化数据，例如 {"text": "..."} / {"path": "截图路径"}
r.error          # str|None —— 失败时的错误摘要
r.screenshot     # str|None —— base64 截图（仅 return_base64=True 时）
r.execution_time # float  —— 本步耗时（秒）
```

**新手最常用的两个字段**：`r.success`（判成败）、`r.data["path"]`（截图/文件的**真实**落盘路径）。

### 5.4 附赠的两个工具类

**TestReporter** —— 生成 HTML / JSON 报告：

```python
from browser_automation_skills.reporter import TestReporter

reporter = TestReporter(output_dir="reports")
reporter.add_chain_result(
    test_name="登录流程",
    test_file="tests/test_login.py",
    chain_results=results,      # execute_chain 的返回值
    total_time=10.5,
)
reporter.print_summary()          # 控制台打印摘要
files = reporter.save_all_reports()  # 生成 HTML + JSON
```

**ScreenshotManager** —— 按"测试名 / 步骤名 / 成败"归档截图：

```python
from browser_automation_skills.screenshot_manager import ScreenshotManager

mgr = ScreenshotManager(output_dir="screenshots")
path = mgr.save_screenshot(
    screenshot_bytes=bytes_data, test_name="登录", step_name="step1", success=False
)
print(path, mgr.get_summary())    # 文件路径 + 汇总统计
```

---

## 第 6 章 用法三：自然语言任务 `execute_task`

### 6.1 一条命令让 AI 自己完成整件事

**在 MCP 客户端里**（推荐，最省事）：

```
请帮我执行任务：打开 https://www.baidu.com，
搜索 "AI 测试"，然后确认结果页包含 "AI 测试" 并截图。
```

**在 Python 里**：

```python
from browser_automation_skills.agent import BrowserAgent
from openai import AsyncOpenAI

agent = BrowserAgent(
    skill_manager=manager,                     # create_manager 的返回值
    llm_client=AsyncOpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com"),
    model="deepseek-v4-flash",                 # 不传则读 config 的 agent.model
    max_steps=20,
)

result = await agent.execute_task("打开百度，搜索 AI 测试，验证结果页包含该关键词")
print(result.success, len(result.steps_executed))
for step in result.steps_executed:
    print(f"  第{step['step']}步: {step['skill']}({step['params']})")
```

### 6.2 它是怎么"自己想办法"的

AI 每走一步都在做这三件事：

1. 调 `get_dom_snapshot` 抓当前页面的**可交互元素清单**（带编号）；
2. 把"任务 + 页面状态 + 最近 5 步历史"发给大模型，让模型输出严格的 JSON：
   `{skill: "click_by_index", params: {index: 6}, status: "continue"}`；
3. 执行这个技能，然后回到第 1 步继续，直到模型返回 `status: "done"`。

**所以它不需要你写选择器** —— 但代价是每步都要调一次大模型（慢、花钱）。

### 6.3 内置的"跑飞保护"

| 保护 | 默认 | 说明 |
|---|---|---|
| 最大步数 | 20 | 超过即停止 |
| 操作去重防环 | 连续 3 次相同操作即停 | 防止"反复点同一个按钮" |
| 连续失败即停 | 3 次 | 防止一直失败还硬试 |
| 单步超时 | 60 秒 | `agent.step_timeout` |
| 用例/任务超时 | 120 秒 | `agent.case_timeout` |

### 6.4 断言门禁：为什么"没断言的通过"不算通过

开着 `agent.require_assertion: true` 时，模型说"我做完了"**不算数**：

- 如果它**一次断言技能都没调** → 框架拦下来，提示它"你必须实际执行断言技能"；
- 如果**最后一次断言是失败的** → 同样拦下；
- 补救次数用完还这样 → 这条用例判定为**不通过**，`error` 以"断言门禁"开头。

这条规则是整个项目"**通过结果可信**"的地基。写用例时请务必带 `assertions`（见第 7 章）。

---

## 第 7 章 用法四：批量测试（重点）

前面三种用法都是"一次操作"。批量测试是**写一份用例文件 → 一条命令全跑完 → 出报告**，是长期回归的主战场。

### 7.1 先搞懂：一条用例走哪条路

这是整个项目**最反直觉、也最重要**的一点：**用例走哪条路，是由"用例文件 + 配置"决定的，不是大模型自己决定的。**

判定顺序（优先级从高到低）：

| 优先级 | 触发条件 | 执行方式 | 调用 LLM？ | 速度 |
|---|---|---|---|---|
| **1** | 用例里写了非空 `actions` | 按 `actions` 顺序执行 → 再用 `assertions` 判定 | ❌ **不调用** | 快（≈7 秒/2 条） |
| **2** | 没写 `actions`，且 `replay_recorded: true`，且存在 `recorded_actions/<用例ID>.actions.yaml` | 回放录制动作 → 再用 `assertions` 判定 | ❌ 不调用 | 快 |
| **3** | 以上都不满足 | 把 `steps` 自然语言交给 LLM 逐步规划；若写了 `assertions`，框架最后强制执行并判定 | ✅ 调用 | 慢（30~70 秒/条） |

报告里会明确写出每条用例实际走了哪条路（`## 执行模式与审计` 章节）：

```text
- TC_01: 执行模式: LLM 规划；已录制动作: ./recorded_actions/TC_01.actions.yaml
- TC_03: 执行模式: 确定性执行（来源：用例声明 actions，不调用 LLM）
```

**新手路径建议**：先用模式 3（自然语言）快速把流程跑通 → 打开 `record_actions` 录一遍 → 用 `promote` 固化进用例 → 之后长期跑模式 1（确定性、免费、快）。

### 7.2 用例文件怎么写（三种格式 + 字段表）

#### 全部可用字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 建议 | 用例编号，如 `TC_01`。**失败截图和录制文件名都用它** |
| `name` | 建议 | 用例名称（报告里显示） |
| `description` | 否 | 补充描述 |
| `steps` | 是* | 自然语言步骤（模式 3 用；模式 1 下仅作可读说明） |
| `expected_result` | 否 | 预期结果，会拼进给 LLM 的提示词 |
| `setup_url` | 否 | **执行前先导航到这个 URL**（强烈建议写，避免用例从空白页开始） |
| `timeout` | 否 | 本条用例超时（秒），优先级高于 `agent.case_timeout` |
| `priority` | 否 | high / medium / low，仅记录 |
| `tags` | 否 | 标签，字符串或数组都行（逗号/分号/竖线/顿号分隔均可） |
| `actions` | 否 | **确定性步骤数组**（写了就走模式 1，不调 LLM） |
| `assertions` | 强烈建议 | **判定用的断言数组**（决定这条用例算不算通过） |

> \* 只写 `actions` 不写 `steps` 也能跑；但建议都写上 —— `steps` 供人阅读。

#### 格式 A：YAML（可读性最好，推荐手写）

```yaml
- id: TC_01
  name: 百度首页打开
  description: 验证首页能打开，标题与域名正确
  steps: |
    1. 打开 https://www.baidu.com
    2. 断言页面标题包含 "百度"
    3. 断言 URL 含 "baidu.com"
  expected_result: 两个断言都通过
  priority: high
  setup_url: https://www.baidu.com
  timeout: 30
  actions:
    - {skill: navigate, params: {url: "https://www.baidu.com"}}
  assertions:
    - {skill: title_contains, params: {expected: "百度"}}
    - {skill: url_contains, params: {expected: "baidu.com"}}

- id: TC_02
  name: 百度搜索（不写 actions，走 LLM 规划）
  steps: 在百度搜索框输入"自动化测试"，点击搜索按钮
  setup_url: https://www.baidu.com
  timeout: 60
  assertions:
    - {skill: url_contains, params: {expected: "wd="}}
    - {skill: page_contains_text, params: {text: "自动化测试"}}
```

`actions` / `assertions` 有三种等价写法，随便用哪种：

```yaml
# ① 标准写法
- {skill: click_by_index, params: {index: 6}}
# ② 扁平写法（params 省略）
- {skill: click_by_index, index: 6}
# ③ 字符串写法
- "click_by_index: {\"index\": 6}"
```

#### 格式 B：JSON

```json
[
  {
    "id": "TC_01",
    "name": "百度搜索",
    "steps": "打开百度，搜索 AI 测试",
    "setup_url": "https://www.baidu.com",
    "timeout": 60,
    "actions": [
      {"skill": "navigate", "params": {"url": "https://www.baidu.com"}},
      {"skill": "get_dom_snapshot", "params": {}},
      {"skill": "fill_by_index", "params": {"index": 13, "value": "AI 测试"}},
      {"skill": "click_by_index", "params": {"index": 6}}
    ],
    "assertions": [
      {"skill": "url_contains", "params": {"expected": "wd="}},
      {"skill": "page_contains_text", "params": {"text": "AI 测试"}}
    ]
  }
]
```

#### 格式 C：Excel（.xlsx，适合给非技术人员维护）

第一行是表头，支持中英文两套（任选一套，不要混）：

| 中文表头 | ID | 用例名称 | 描述 | 操作步骤 | 预期结果 | 优先级 | 前置URL | 超时时间 | 标签 | 确定性步骤 | 断言 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 英文表头 | id | name | description | steps | expected_result | priority | setup_url | timeout | tags | actions | assertions |

其中 `确定性步骤` / `断言` 两列可以填 JSON 文本，例如：

```
[{"skill":"url_contains","params":{"expected":"wd="}}]
```

> **`操作步骤` 列请写自然语言**（"打开百度，搜索 XX，验证结果包含 XX"），不要写选择器或代码 —— 那是给 AI 读的。

### 7.3 为什么每条用例都必须写断言

因为**只有断言能决定"通过"。**

- 没有断言时，AI 说"我点完了"就结束 —— 页面明明报错它也可能判通过；
- 写了断言后，框架在最后**强制执行**断言，**断言失败 = 用例失败**，模型无权更改这个结论。

可用的 17 个断言工具（详见 [第 8 章](#83-断言验证17-个)）：`title_contains`、`url_contains`、`page_contains_text`、`element_exists`、`text_equals`、`count_elements`……

**选断言的实用原则**：一条用例配 2~3 条，覆盖三个层次：

| 层次 | 例子 | 作用 |
|---|---|---|
| 页面跳转 | `url_contains: {expected: "wd="}` | 确认操作真的生效 |
| 内容出现 | `page_contains_text: {text: "自动化测试"}` | 确认结果正确 |
| 元素状态 | `element_exists: {selector: "#content_left"}` | 确认关键区域已渲染 |

### 7.4 怎么触发批量执行（三种入口）

#### 入口 A：MCP 客户端（适合少量用例、要 AI 帮你分析结果）

```
请批量执行 D:\BaiduNetdiskDownload\browser_automation_skills\test_case\test_cases_baidu.yaml
```

AI 会调用工具 `execute_batch_testcases`，其参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `file_path` | ✅ | 用例文件路径 |
| `file_type` | 否 | `json` / `yaml` / `xls` / `xlsx`；不填则按扩展名自动判断 |
| `sheet_name` | 否 | Excel 的 sheet 名 |
| `report_path` | 否 | 报告路径；**不填则自动生成** `<用例所在目录>/reports/<用例文件名>_report_<时间戳>_<pid>_<序号>.md` |
| `artifact_root` | 否 | **产物根目录**；不填 = 用例文件所在目录（截图/录制/报告都放这里） |
| `max_steps_per_case` | 否 | 默认 20 |
| `max_retries_per_case` | 否 | 默认 3 |
| `screenshot_on_failure` | 否 | 默认 true（失败自动截图） |

> ⚠️ **注意 MCP 客户端的单次请求超时**（Cline 默认 60 秒）。用例多、或走 LLM 规划时，
> 会超时失败 —— 这种情况**请用入口 B**。

#### 入口 B：命令行（推荐，不受超时限制）⭐

包内自带一个可运行示例，用法与 MCP 工具等价：

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills

# ① 只解析用例、打印概要（不启动浏览器、不用 Key，适合冒烟）
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example --parse-only

# ② 跑包内自带示例（确定性用例，不花钱）
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example

# ③ 跑自己的用例 + 指定报告（有头模式，方便观察）
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example `
    --cases test_case\test_cases_baidu.yaml `
    --report test_case\reports\baidu_report.md `
    --headed
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--cases` | 用例文件（默认用包内示例） |
| `--report` | 报告输出路径（默认 `./batch_report.md`） |
| `--config` | 指定配置文件（默认依次找 `./config/config.yaml`、`./config.yaml`） |
| `--sheet` | Excel 的 sheet 名 |
| `--model` | 临时覆盖 `agent.model` |
| `--max-steps` / `--max-retries` | 每用例步数 / 重试上限 |
| `--headless` / `--headed` | 强制无头 / 有头 |
| `--parse-only` | 只解析用例不执行 |
| `--verbose` | 打印 DEBUG 日志 |

#### 入口 C：Python 脚本（适合接入你自己的 CI）

```python
import asyncio
from pathlib import Path
from browser_automation_skills import create_manager
from browser_automation_skills.browser_launcher import BrowserLauncher

async def main():
    launcher = BrowserLauncher(headless=True)
    ctx = await launcher.launch()
    try:
        manager = create_manager(browser_context=ctx, config=config)   # config 从 config.yaml 读入
        result = await manager.execute(
            "execute_batch_testcases",
            file_path=r"D:\BaiduNetdiskDownload\browser_automation_skills\test_case\test_cases_baidu.yaml",
            report_path=r"D:\BaiduNetdiskDownload\browser_automation_skills\test_case\reports\run.md",
            screenshot_on_failure=True,
        )
        print(result.success, result.message)
        print("报告:", result.data["report_path"])        # 真实落盘路径
        print("截图目录:", result.data["screenshot_dir"])
    finally:
        await launcher.close()

asyncio.run(main())
```

返回值 `result.data` 里包含：`total` / `passed` / `failed` / `pass_rate` / `duration` /
**`report_path`（真实路径）** / `artifact_root` / `screenshot_dir` / `record_dir`。

> 取退出码做 CI 门禁：`execute_batch_testcases` 在**有失败用例时 `success=False`**，脚本里据此 `sys.exit(1)` 即可。

### 7.5 报告怎么看

报告是标准 Markdown，章节固定，逐段含义如下：

| 章节 | 内容 | 怎么用 |
|---|---|---|
| `## 概要` | 总数 / 通过 / 失败 / 跳过 / 通过率 / 执行时长 | 一眼看健康度 |
| `## 详细结果` | 逐条用例的状态、步数、耗时、**断言通过数**、重试次数、失败原因 | 定位哪条挂了 |
| `## 断言证据` | 每条断言的实际参数与返回消息（✅/❌），框架断言会标注"（框架断言）" | **验证"通过"是真通过** |
| `## 失败截图` | 失败用例的截图**真实绝对路径** | 直接打开看现场 |
| `## 执行模式与审计` | 每条用例走了哪条路（LLM / 确定性 / 回放）、是否用了 `execute_js` 之类降级手段、是否回退了 LLM | 判断结果可复现性 |
| `## 参数归一化记录` | 模型传参笔误被自动纠正的记录（如 `text` → `value`） | 观察 AI 传参质量 |
| `## 停止原因` | 触发熔断时的原因（如"连续失败 5 次"） | 排查批量中断 |

一个"通过"的可信度排序（从高到低）：
**确定性 actions + 框架断言** > **回放 + 断言** > **LLM 规划 + 断言** > **LLM 规划（无断言）**。

### 7.6 产物到底落在哪（最容易困惑的地方）⭐

先说结论：**v1.5.6 起，批量执行的产物跟着"用例文件所在目录"走**，不再散落到工作区根。

#### 批量测试的产物

| 产物 | 何时产生 | 落盘位置 | 怎么改 |
|---|---|---|---|
| 失败截图 | 用例失败且 `screenshot_on_failure=true`（默认） | `<用例所在目录>\screenshots\<用例ID>_failure.png` | 传 `artifact_root` 参数换成别的根 |
| 录制动作 | 用例成功且 `record_actions: true` | `<用例所在目录>\recorded_actions\<用例ID>.actions.yaml` | 同上 |
| 测试报告 | **每次都会生成** | `<用例所在目录>\reports\<用例文件名>_report_<时间戳>_<pid>_<序号>.md` | 传 `report_path` 指定路径 |

举例：用例文件是 `project01\test01.yaml`，跑完之后：

```
project01\
├── test01.yaml
├── screenshots\TC_001_failure.png          ← 失败截图
├── recorded_actions\TC_001.actions.yaml    ← 录制动作
└── reports\test01_report_20260928_191022_11836_001.md   ← 报告
```

**一句话**：用例文件放哪，产物就在它旁边。所以最自然的做法是**一个项目一个目录**：

```
工作区根\
├── project-01\
│   ├── cases.yaml
│   ├── screenshots\      ← 自动产生
│   ├── reports\          ← 自动产生
│   └── recorded_actions\ ← 自动产生
└── project-02\
    └── cases.yaml
```

#### 非批量场景（直接调 `screenshot` 工具）

| 场景 | 落盘位置 |
|---|---|
| 不传 `output_dir` | `config` 里 `screenshot.output_dir`（默认 `./screenshots`，相对 server 的 cwd） |
| 传了 `output_dir` | 指定目录（**必须**在工作区内，否则拒绝） |
| 传了 `path` | 只取**文件名**部分；目录**一律**由上面两条决定（防止路径乱飞） |

#### 路径安全规则（v1.5.6）

- 允许写入的根目录 = **MCP server 的 cwd** 及其子目录（可用 `artifact_routing.allowed_roots` 追加）；
- 越界时**直接报错拒绝**，错误信息里会写明当前允许的根目录；
- 被校验的 4 个路径参数：`file_path`（用例文件）、`artifact_root`、`report_path`、`screenshot.output_dir`。

报错长这样（说明"凭什么拒绝"）：

```text
report_path 不在允许的工作区内: C:\Windows\Temp\r.md
（允许根: D:\BaiduNetdiskDownload\browser_automation_skills；
如需放开，请在配置的 artifact_routing.allowed_roots 中追加目录）
```

> **旧产物去哪了**：工作区根下那几个 `screenshots\TC_*_failure.png`、`recorded_actions\TC_*.actions.yaml`
> 是 1.5.6 之前留下的，属于历史文件，不影响新流程 —— 可以自己归档或删除。

### 7.7 从"能跑到"到"每次都能跑"：录制 → 固化（进阶但强烈推荐）

这是本项目最有价值的工作流，四步走：

**第 1 步：让 AI 先跑通一次**（模式 3）

```yaml
# cases.yaml
- id: TC_01
  name: 百度搜索
  steps: 在百度搜索 "自动化测试" 并验证结果页
  setup_url: https://www.baidu.com
  assertions:
    - {skill: url_contains, params: {expected: "wd="}}
```

用命令行跑一次（配置里 `record_actions: true`）。成功后会自动生成：

```
<用例所在目录>\recorded_actions\TC_01.actions.yaml
```

**第 2 步：人工 review 录制文件**

打开看一眼，确认它记录的是"你认可的操作路径"（里面还会带元素锚点，用于回放时抗页面小改动）。

**第 3 步：一条命令固化进用例文件**

```powershell
# 先看要改什么（不写盘）
.\myvenv\Scripts\python.exe -m browser_automation_skills.promote --cases cases.yaml --dry-run

# 确认没问题，原地写入（自动备份 cases.yaml.bak）
.\myvenv\Scripts\python.exe -m browser_automation_skills.promote --cases cases.yaml --with-assertions
```

| `promote` 参数 | 作用 |
|---|---|
| `--cases` | 用例文件（YAML） |
| `--record-dir` | 录制目录（默认 `./recorded_actions`） |
| `--output` | 写到新文件（默认原地修改） |
| `--dry-run` | 只打印 diff，不写盘 |
| `--overwrite` | 覆盖用例里已有的 `actions` / `assertions` |
| `--with-assertions` | 连同录制里的断言草稿一起固化 |
| `--no-backup` | 不生成 `.bak` 备份 |

**第 4 步：以后每次都是纯确定性执行**

用例文件里已经有了 `actions` → 走模式 1 → **不调 LLM、不花钱、速度快、结果可复现**。
而且**用例文件成了唯一事实来源**：可以进 Git、可以 code review、可以当 CI 门禁。

> 实测效果：自然语言规划 ≈ 30~70 秒/条 → 固化后 ≈ 3~4 秒/条，且通过率不再抖动。
>
> 注意：`promote` **不会禁用** `execute_js` 这类"降级手段"——它会照常固化，只在文件里加注释标注并在汇总里告警，
> 是否保留由你 review 决定。

### 7.8 批量执行的"熔断"与安全机制

| 机制 | 默认值 | 说明 |
|---|---|---|
| 连续失败熔断 | 5 条 | 连续失败这么多条就整体停止（避免在有问题的环境里空跑） |
| 每用例最大步数 | 20 | `max_steps_per_case` |
| 每用例连续失败上限 | 3 | `max_retries_per_case` |
| 操作去重防环 | 开启 | 连续 3 次相同 skill+params 即判死循环 |
| 用例级硬超时 | 120 秒 | 用例文件 `timeout` 优先 |
| 失败自动截图 | 开启 | 落 `<用例目录>\screenshots\<用例ID>_failure.png` |
| 用例间页面隔离 | `isolate_pages: true` | 每条用例新开页面，避免状态污染 |
| 断言硬门禁 | `require_assertion` | 无断言/断言失败 → 不允许通过 |

---

## 第 8 章 全部 74 个工具速查表

> 本表由框架**实际生成的 MCP schema**导出，参数名、默认值、可选枚举都是权威值 —— 照抄不会错。
> 表格里 `参数=默认值` 表示可选参数；**没有 `=` 的是必填参数**。

### 8.1 浏览器操作（25 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `navigate` | 导航到指定 URL | `url` | `timeout=30000`、`wait_until="load"`（load/domcontentloaded/networkidle/commit） |
| `click` | 点击页面元素 | `selector` | `timeout=10000`、`button="left"`（left/right/middle）、`click_count=1`、`force=false` |
| `screenshot` | 截取当前页面截图 | — | `path`、`full_page=false`、`return_base64=false`、`output_dir` |
| `wait_for_element` | 等待元素出现 | `selector` | `timeout=10000`、`state="visible"`（visible/hidden/attached/detached） |
| `get_text` | 获取元素文本 | `selector` | `timeout=5000` |
| `get_attribute` | 获取元素属性 | `selector`、`attribute` | `timeout=5000` |
| `get_page_info` | 获取页面 URL、标题 | — | — |
| `get_current_page_info` | 获取当前页上下文信息 | — | — |
| `execute_js` | 在页面执行 JavaScript | `script` | `arg` |
| `get_html` | 获取页面或元素 HTML | — | `selector`、`outer=false`、`timeout=5000` |
| `scroll_into_view` | 把元素滚到可视区域 | `selector` | `timeout=5000` |
| `scroll_to` | 滚动到指定位置 | — | `x=0`、`y=0` |
| `focus` | 聚焦元素 | `selector` | `timeout=5000` |
| `blur` | 取消元素焦点 | `selector` | `timeout=5000` |
| `double_click` | 双击元素 | `selector` | `timeout=5000` |
| `right_click` | 右键点击元素 | `selector` | `timeout=5000` |
| `wait` | 等待指定秒数 | — | `seconds=1.0` |
| `reload` | 刷新页面 | — | `timeout=30000`、`wait_until="load"` |
| `go_back` | 浏览器后退 | — | `timeout=30000` |
| `go_forward` | 浏览器前进 | — | `timeout=30000` |
| `open_new_tab` | 打开新标签页 | — | `url`、`timeout=30000`、`wait_until="load"` |
| `close_tab` | 关闭标签页 | — | `page_index` |
| `switch_tab` | 切换到指定标签页 | — | `page_index=0` |
| `get_tabs` | 列出所有标签页 | — | — |
| `close_other_tabs` | 关闭其他标签页 | — | `keep_index` |

> **标签页索引从 0 开始**。`page_index` 不要写成 `index`（这是常见手误，框架对部分技能能自动纠正，但别指望）。

### 8.2 表单操作（12 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `fill_input` | 填写输入框 | `selector`、`value` | `timeout=5000`、`clear=true` |
| `type_text` | 逐字符输入（更拟人） | `selector`、`text` | `delay=50`、`timeout=5000` |
| `select_option` | 选择下拉项（支持原生/AntD/Element UI） | `selector` | `value`、`label`、`index`、`timeout=5000` |
| `check_checkbox` | 勾选复选框 | `selector` | `timeout=5000`、`force=false` |
| `uncheck_checkbox` | 取消勾选 | `selector` | `timeout=5000`、`force=false` |
| `upload_file` | 上传文件（自动适配多种场景） | — | `selector`、`file_path=""`、`button_text`、`multiple=false`、`upload_trigger="auto"`、`timeout=10000` |
| `fill_form` | 批量填多个字段 | `fields` | `selector_type="css"`（css/xpath）、`timeout=5000` |
| `submit_form` | 提交表单 | — | `submit_selector`、`form_selector`、`wait_for`、`wait_for_timeout=10000`、`timeout=5000` |
| `clear_input` | 清空输入框 | `selector` | `timeout=5000` |
| `hover` | 鼠标悬停 | `selector` | `timeout=5000` |
| `press_key` | 按键 | `key` | `selector` |
| `set_date` | 设置日期/时间控件 | `selector`、`value` | `date_format="auto"`、`force_click=false`、`timeout=5000` |

> `select_option` 三选一：`value`（按值）、`label`（按显示文本）、`index`（按顺序）。
> `fill_form` 的 `fields` 示例：`{"#user": "admin", "#pwd": "123456", "#remember": true}`

### 8.3 断言验证（17 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `text_equals` | 断言元素文本**等于**指定值 | `selector`、`expected` | `timeout=5000`、`exact=true` |
| `text_contains` | 断言元素文本**包含**指定值 | `selector`、`expected` | `timeout=5000`、`case_sensitive=true` |
| `element_exists` | 断言元素存在 | `selector` | `timeout=5000`、`state="attached"`（visible/hidden/attached/detached） |
| `element_not_exists` | 断言元素不存在 | `selector` | `timeout=2000` |
| `element_visible` | 断言元素可见 | `selector` | `timeout=5000` |
| `element_enabled` | 断言元素可交互 | `selector` | `timeout=5000` |
| `element_disabled` | 断言元素已禁用 | `selector` | `timeout=5000` |
| `url_contains` | 断言 URL 包含指定字符串 | `expected` | `case_sensitive=true` |
| `url_equals` | 断言 URL 等于指定值 | `expected` | `exact=false` |
| `title_contains` | 断言标题包含指定字符串 | `expected` | `case_sensitive=true` |
| `title_equals` | 断言标题等于指定值 | `expected` | `exact=true` |
| `page_contains_text` | 断言**整页**包含指定文本 | `text` ⚠️ | `case_sensitive=true` |
| `element_has_class` | 断言元素含指定 class | `selector`、`class_name` | `timeout=5000` |
| `element_selected` | 断言元素已选中 | `selector` | `timeout=5000` |
| `attribute_equals` | 断言属性等于指定值 | `selector`、`attribute`、`expected` | `timeout=5000` |
| `count_elements` | 断言匹配元素数量 | `selector`、`expected_count` ⚠️ | `timeout=5000` |
| `checkbox_checked` | 断言复选框已勾选 | `selector` | `timeout=5000`、`expected=true` |

> ⚠️ **两个高频踩坑点**（参数名和其他断言不一样）：
> - `page_contains_text` 用的是 **`text`**，不是 `expected`；
> - `count_elements` 用的是 **`expected_count`**，不是 `expected`。
>
> 写错了会直接报参数错误（框架会尝试用别名表纠正，但不要依赖它）。

### 8.4 弹窗 / iframe（10 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `get_popup_pages` | 列出所有弹窗/标签页（含 `window.open`） | — | — |
| `switch_to_popup` | 切到指定弹窗（按索引或 URL/标题匹配） | — | `page_index`、`url_contains`、`title_contains`、`timeout=5000` |
| `wait_for_popup` | 等待弹窗出现 | — | `url_contains`、`title_contains`、`timeout=10000`、`min_pages=2` |
| `click_in_popup` | 在弹窗里点击 | `selector` | `page_index`、`url_contains`、`timeout=10000`、`button="left"`、`force=false` |
| `fill_in_popup` | 在弹窗里填写 | `selector`、`value` | `page_index`、`url_contains`、`timeout=5000`、`clear=true` |
| `select_in_popup` | 在弹窗里选下拉 | `selector` | `value`、`label`、`index`、`page_index`、`url_contains`、`timeout=5000` |
| `get_text_in_popup` | 读弹窗里的文本 | `selector` | `page_index`、`url_contains`、`timeout=5000` |
| `close_popup` | 关闭弹窗 | — | `page_index`、`url_contains` |
| `handle_iframe` | 操作 iframe 内的内容 | `selector` | `action="get_content"`（accept/dismiss）、`inner_selector`、`value`、`timeout=5000` |
| `click_and_wait_popup` | 点击并等弹窗（点开新窗口场景） | `selector` | `url_contains`、`title_contains`、`timeout=10000` |

**典型用法**：点了"登录"按钮弹出新窗口 →

```yaml
- {skill: click_and_wait_popup, params: {selector: "a.login"}}   # 点击并等弹窗
- {skill: fill_in_popup, params: {selector: "#username", value: "admin"}}
- {skill: fill_in_popup, params: {selector: "#password", value: "123456"}}
- {skill: click_in_popup, params: {selector: "button[type=submit]"}}
- {skill: handle_iframe, params: {selector: "iframe#pay", inner_selector: "#card", value: "6222..."}}
```

### 8.5 DOM 索引操作（3 个）—— 不会写选择器的救星 ⭐

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `get_dom_snapshot` | 获取页面可交互元素的**索引快照** | — | `readable=true`、`max_elements=100`、`use_cache=true` |
| `click_by_index` | 按索引点击元素 | `index` | `timeout=5000`、`use_cache=true` |
| `fill_by_index` | 按索引填写输入框 | `index`、`value` | `timeout=5000`、`use_cache=true` |

**为什么它很重要**：很多页面（尤其百度这种）元素没有稳定的 `id`/`class`，
手写 CSS 选择器很容易失效。用这三件套就变成"看图点第几个"：

```yaml
actions:
  - {skill: get_dom_snapshot, params: {}}            # ① 先把页面元素编号
  - {skill: fill_by_index, params: {index: 13, value: "自动化测试"}}  # ② 第 13 号是搜索框
  - {skill: click_by_index, params: {index: 6}}      # ③ 第 6 号是搜索按钮
```

> ⚠️ **索引会随页面变化**：编号取决于"当前快照里可交互元素的顺序"，页面改版或加载状态不同，
> 同一个元素可能是别的编号。所以：
> - 写确定性 `actions` 时，**每次执行前都先 `get_dom_snapshot`**（上面示例就是这样）；
> - 录制时框架会自动记录元素的**稳定锚点**（id/placeholder/text），回放时按锚点重新解析索引。

### 8.6 AI Agent（2 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `execute_task` | 自然语言任务：自动规划并执行 | `task` | `max_steps=20`、`max_retries=3` |
| `execute_batch_testcases` | 批量执行用例文件 | `file_path` | `file_type`、`sheet_name`、`report_path`、`max_steps_per_case=20`、`max_retries_per_case=3`、`screenshot_on_failure=true`、`artifact_root` |

### 8.7 多模态视觉（2 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `screenshot_vision` | 截图并返回 Base64 | — | `full_page=false` |
| `analyze_page` | 让视觉大模型"看图回答" | `prompt` | `full_page=false`、`model` |

用法示例（在 MCP 客户端里说）：

```
请打开 https://www.baidu.com，截图，然后告诉我页面上有哪些输入框、它们的位置在哪里。
```

AI 会自动组合 `navigate` → `screenshot_vision` / `analyze_page`。
需要 `config` 里配好 `vision.api_key`（或环境变量 `DASHSCOPE_API_KEY` / `OPENAI_API_KEY`）。

**什么时候值得用**：元素定位实在找不到、或要验证"视觉上是否正常显示"（比如按钮有没有被遮挡）。

### 8.8 缓存 / 性能（2 个）

| 工具 | 功能 | 必填参数 | 可选参数（含默认值/枚举） |
|---|---|---|---|
| `get_cache_stats` | 查看缓存命中情况 | — | — |
| `clear_cache` | 清空缓存 | — | `cache_type="all"`（all/dom/llm） |

> 页面明明变了但结果还是旧的 → 试 `clear_cache`（`cache_type="dom"`）。

### 8.9 链式执行（1 个）

| 工具 | 功能 | 必填参数 | 可选参数 |
|---|---|---|---|
| `execute_chain` | 一次调用跑多个技能 | `steps`（数组） | — |

```json
{
  "steps": [
    {"skill": "navigate", "params": {"url": "https://example.com"}},
    {"skill": "fill_input", "params": {"selector": "#kw", "value": "hello"}},
    {"skill": "click", "params": {"selector": "#su"}},
    {"skill": "text_contains", "params": {"selector": "#content_left", "expected": "hello"}}
  ]
}
```

**优点**：减少"客户端 ↔ server"往返，比让 AI 一步步调更快、更省 token。

---

## 第 9 章 用例怎么写才稳（最佳实践）

### 9.1 六条铁律

1. **每条用例必须写 `assertions`** —— 这是"通过"的唯一依据（断言门禁会拦住没有断言的通过）。
2. **每条用例写 `setup_url`** —— 明确起点，避免"上一条用例留下的页面状态"影响这一条。
3. **用例之间不要有依赖** —— 第 2 条用例不能假设"第 1 条已经登录了"。
4. **能用确定性 `actions` 就别用自然语言** —— 快、省钱、结果可复现（见 7.7 的录制固化流程）。
5. **别写绝对 XPath / 动态 class** —— `/html/body/div[2]/button` 和 `.sc-fdsjf923` 一定会失效。
6. **`timeout` 要按实际给** —— 简单页面 30 秒足够，重页面给 60~120 秒。

### 9.2 选择器优先级（从稳到不稳）

| 优先级 | 写法 | 适用 |
|---|---|---|
| ⭐⭐⭐⭐⭐ | `[name='username']` 属性选择器 | 表单最稳 |
| ⭐⭐⭐⭐ | `#submit-btn` id 选择器 | 有唯一 id 时 |
| ⭐⭐⭐ | `.btn-primary` class 选择器 | 同类型元素 |
| ⭐⭐⭐⭐ | **DOM 索引**（`get_dom_snapshot` + `click_by_index`） | 选择器都不稳时的兜底 |
| ❌ | `/html/body/div[2]/div[1]/button` | 绝对 XPath，改版必挂 |
| ❌ | `div:nth-child(3)` | 依赖位置的脆弱写法 |
| ❌ | `.sc-fdsjf923` | 构建工具生成的随机类名 |

### 9.3 等待策略

**✅ 推荐**：等"具体条件"

```yaml
- {skill: wait_for_element, params: {selector: "#result", timeout: 10000, state: "visible"}}
- {skill: navigate, params: {url: "https://x.com", wait_until: "networkidle"}}   # 等网络空闲
```

**❌ 避免**：固定睡几秒

```yaml
- {skill: wait, params: {seconds: 5}}     # 要么不够、要么白等
```

`wait` 只适合"页面有明显动画、且你知道大概要多久"的极少数场景。

### 9.4 超时与重试怎么调

| 症状 | 调整方向 |
|---|---|
| 报错"元素找不到"，但其实页面只是慢 | 调大 `skill_timeout.selector_wait_budget_seconds`（如 10），或给该步骤单独传 `timeout` |
| 整体太慢 | 调小 `selector_wait_budget_seconds`，并检查是否在反复重试同一个不存在的元素 |
| 偶尔抖动失败 | 开 `retry_failed_cases: 1`（注意：会掩盖真实缺陷，CI 慎用） |
| 某条用例总是卡住 | 给它单独的 `timeout`，并检查是不是进了死循环（防环机制会处理，但值得看报告） |

### 9.5 目录与命名约定（建议）

```
工作区根\
├── project-A\
│   ├── cases.yaml                  # 用例（进 Git）
│   ├── screenshots\                # 产物（建议 gitignore）
│   ├── reports\                    # 产物（建议 gitignore）
│   └── recorded_actions\           # 产物（建议 gitignore）
└── project-B\
    └── cases.yaml
```

- 用例 `id` 用 `TC_01`、`TC_02` 这种规范编号（失败截图/录制文件都用它命名）；
- 用例文件名最好能说明项目/模块，例如 `test_cases_baidu.yaml`。

### 9.6 提交前自检清单

- [ ] 每条用例都有 `assertions`，且断言数量 ≥ 2；
- [ ] 每条用例都有 `setup_url`（除了纯本地页面）；
- [ ] 用例之间无依赖，随机顺序跑也成立；
- [ ] `timeout` 给得合理；
- [ ] 没有绝对 XPath、没有动态 class；
- [ ] 用 `--parse-only` 通过（格式没错）；
- [ ] 用 `--headed` 实跑一次，肉眼确认操作路径正确；
- [ ] 需要长期稳定的用例，已固化 `actions`（不依赖 LLM）；
- [ ] 产物目录已加进 `.gitignore`（截图/报告/录制不建议进 Git）；
- [ ] 用例文件里的 `actions` 确认没有泄漏账号密码等敏感信息。

---

## 第 10 章 常见问题排查（FAQ）

### 10.1 一键自检（先跑这个）

```powershell
cd D:\BaiduNetdiskDownload\browser_automation_skills

# 包能不能导入？版本对不对？
.\myvenv\Scripts\python.exe -c "import browser_automation_skills as b; print(b.__version__, b.__file__)"

# 有几个工具？（应输出 74）
.\myvenv\Scripts\python.exe -c "from browser_automation_skills import create_manager; m=create_manager(browser_context=None); print(len(m._skills)+1)"

# 用例能不能解析？（不启动浏览器）
.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example --parse-only
```

### 10.2 症状对照表

| 症状 | 最可能的原因 | 解决办法 |
|---|---|---|
| MCP 面板显示 `No tools yet` / 工具数为 0 | ① `mcp` 装成 2.x；② 客户端没重启；③ 启动命令写成了 `mcp_server.py` 文件路径 | ① `pip install "mcp>=1.0.0,<2.0.0"`；② 重启该 server；③ 改用 `-m browser_automation_skills.mcp_server` |
| `'Server' object has no attribute 'list_tools'` | mcp 2.x | 同上 ① |
| 报"找不到浏览器"/启动失败 | 没装 Playwright 浏览器 | `playwright install chromium`，或在 config 里指定 `browser.executable_path` |
| `execute_task` / `analyze_page` 报 401 或"没有 Key" | `agent.api_key` / `vision.api_key` 没填 | 在 `config/config.yaml` 填好，或设环境变量；**改完重启 server** |
| `LLM client not configured` | 同上（批量走 LLM 规划时需要 Key） | 填 Key；或给用例加 `actions` 走确定性执行（不需要 Key） |
| 报告没生成 | ① 路径越界被拒；② 目录不可写 | 看工具返回的 `message`/`error`；报告默认会写到 `<用例目录>\reports\` |
| 报错 `xxx 不在允许的工作区内` | 路径跑到工作区外了 | 把文件放到工作区内，或在 config 里加 `artifact_routing.allowed_roots` |
| 批量跑到一半停了 | 连续失败熔断（默认 5 条） | 看报告的 `## 停止原因`；先修失败的用例 |
| 截图出现在 `D:\Microsoft VS Code\screenshots` 之类的地方 | MCP 配置的 `cwd` 不对 | 把 `cwd` 改成工作区根并重启 |
| 改了配置不生效 | 没重启 MCP server | 重启 server（Trae/CodeBuddy 重启 IDE 或该 server） |
| 改了源码不生效 | 装的是 `site-packages` 副本 | 重新 `build_wheel.py` + `pip install --force-reinstall`；或临时设 `PYTHONPATH=src` |
| 用例全部失败、都报元素找不到 | ① 没写 `setup_url`（页面还是空白页）；② 用了过时的选择器 | ① 补 `setup_url`；② 改用 `get_dom_snapshot` + `*_by_index` |
| 用例通过但感觉不对 | 没有断言 | 补 `assertions`；开 `require_assertion: true` |
| 同一条用例有时过有时不过 | 页面加载竞态 | 调大 `assertion_settle_ms`、用 `wait_for_element` 代替 `wait` |
| 控制台中文乱码 | Windows 控制台编码 | 框架已做兜底；仍乱码时改用 `--verbose` 或把日志重定向到文件 |
| `pytest` 收集阶段报错/中断 | 测试文件里的硬编码路径 | 用 1.5.6 及以上版本的测试（已修复）；`pytest` 应在工作区根或包目录执行 |

### 10.3 三个"为什么"

**Q：为什么我说了"打开百度"却没反应？**
A：MCP 工具需要浏览器实例。第一次调用会**懒加载**浏览器（约 3~10 秒），请稍等；
或检查是不是 `--headed` 没加、窗口在后台。

**Q：为什么批量执行没有生成失败截图？**
A：三个前提：① `screenshot_on_failure=true`（默认）；② 用例**真的失败了**；
③ 失败发生在"判定之后"。检查 `<用例目录>\screenshots\` 目录。

**Q：为什么录制的 actions 和我手动点的不一样？**
A：录制记录的是 **AI 实际执行的路径**（可能绕了路）。所以第 7.7 节强调"人工 review 后再固化" ——
你可以在固化前手工删掉多余的步骤。

---

## 第 11 章 注意事项与边界（必读）

### 11.1 安全与合规

1. **不要把真实 API Key 提交到 Git**。`config/config.yaml` 已在 `.gitignore` 里；分享用 `config.template.yaml`。
2. **不要用本工具做违反目标网站服务条款的事**（批量刷单、爬取隐私数据、绕过风控等）。
3. **控制访问频率**。虽然框架带 `disable_automation`（降低被识别为机器人的概率），但高频请求仍可能被限流/封禁。
4. **用例里不要硬编码真实账号密码**。用占位符 + 环境变量，或只在本地跑。

### 11.2 架构上的边界（提前知道能省很多时间）

| 边界 | 说明 | 应对 |
|---|---|---|
| **一个 server 一个浏览器实例** | 同一个 MCP server 的多个请求**共享**浏览器和页面 | 需要硬隔离 → 给不同项目配**不同的 MCP server 条目** |
| **MCP 请求有超时** | Cline 默认 60 秒，批量跑长任务会超时 | 批量走命令行（入口 B） |
| **并发操作会互相干扰** | 多个请求同时点同一个页面，结果不可预期 | 不要并发驱动同一浏览器；必要时串行 |
| **确定性回放不是 100%** | 页面改版、验证码、慢加载都会让回放失败 | 保留断言兜底；失败就看截图 + 重新录制 |
| **`actions` 里的索引会漂移** | 元素顺序变了，`index` 就指错 | 每次执行前 `get_dom_snapshot`；或依赖录制的锚点重解析 |
| **AI 规划有成本** | 每条用例每步都调一次大模型 | 跑通后立刻用 `promote` 固化成确定性 `actions` |

### 11.3 版本与维护

- 当前版本 **1.5.6**，关键变化：
  - 批量产物**跟着用例目录走**（截图/录制/报告）；
  - `screenshot` 新增 `output_dir`；`execute_batch_testcases` 新增 `artifact_root`；
  - 报告**每次都会生成**（以前没传 `report_path` 就不生成）；
  - 报告新增 `## 失败截图` 章节；
  - 路径越界会**拒绝**而不是静默乱写。
- **改源码 → 必须重新打包安装**（第 2.2 节情况 C）。
- 想验证你的安装是否健康：

  ```powershell
  cd D:\BaiduNetdiskDownload\browser_automation_skills
  .\myvenv\Scripts\python.exe -m pytest -q
  ```
  正常应输出 `138 passed`（这些测试不联网、不启动浏览器）。

---

## 附录 A 常用命令速查

> 统一前缀：`cd D:\BaiduNetdiskDownload\browser_automation_skills`，解释器用 `.\myvenv\Scripts\python.exe`。

### 自检与诊断

| 目的 | 命令 |
|---|---|
| 看版本 | `.\myvenv\Scripts\python.exe -c "import browser_automation_skills as b; print(b.__version__)"` |
| 看包来自哪 | `.\myvenv\Scripts\python.exe -c "import browser_automation_skills as b; print(b.__file__)"` |
| 看工具数（应 74） | `.\myvenv\Scripts\python.exe -c "from browser_automation_skills import create_manager; m=create_manager(browser_context=None); print(len(m._skills)+1)"` |
| 跑单元测试（应 138 passed） | `.\myvenv\Scripts\python.exe -m pytest -q` |
| 只解析用例（不开浏览器） | `.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example --parse-only` |

### 运行批量测试

| 目的 | 命令 |
|---|---|
| 跑包内示例（不花钱） | `.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example` |
| 跑自己的用例（有头观察） | `.\myvenv\Scripts\python.exe -m browser_automation_skills.examples.batch_run_example --cases <用例文件> --report <报告路径> --headed` |
| 指定配置/模型 | 追加 `--config <config.yaml> --model <模型名>` |
| Excel 指定 sheet | 追加 `--sheet <sheet名>` |

### 录制与固化

| 目的 | 命令 |
|---|---|
| 看固化会改什么 | `.\myvenv\Scripts\python.exe -m browser_automation_skills.promote --cases <用例.yaml> --dry-run` |
| 固化（原地，自动备份） | `.\myvenv\Scripts\python.exe -m browser_automation_skills.promote --cases <用例.yaml> --with-assertions` |

### 打包与安装（改源码后）

```powershell
.\myvenv\Scripts\python.exe build_wheel.py
.\myvenv\Scripts\python.exe -m pip install --no-deps --force-reinstall dist\browser_automation_skills-1.5.6-py3-none-any.whl
```

### 启动 MCP server（手工调试）

```powershell
# 方式一：项目自带的批处理
.\start_mcp.bat

# 方式二：直接跑模块（--headed 显示浏览器窗口）
.\myvenv\Scripts\python.exe -m browser_automation_skills.mcp_server --headed
```

---

## 附录 B 相关文档索引

| 文档 | 位置 | 内容 |
|---|---|---|
| 本指南 | `src\browser_automation_skills\docs\教你如何使用browser_automation_skills的全部功能.md` | 全功能使用（你正在看的） |
| 技能清单 | `src\browser_automation_skills\SKILL.md` | 74 个技能的简表 |
| 快速入门 | `src\browser_automation_skills\docs\getting_started.md` | 最小可跑示例 |
| API 参考 | `src\browser_automation_skills\docs\api_reference.md` | 关键类与技能参数 |
| MCP 用法 | `src\browser_automation_skills\docs\mcp_usage.md` | 接入 MCP 客户端 |
| 稳定性与门禁 | `src\browser_automation_skills\docs\stability_and_gates.md` | 超时/重试/断言门禁/录制回放**（进阶必读）** |
| 安装说明 | `src\browser_automation_skills\INSTALL.md` | 安装与常见坑 |
| 项目使用指南 | `src\browser_automation_skills\project_usage.md` | 架构与批量测试实现细节 |
| 改动清单 | `src\browser_automation_skills\docs\建议的改动清单.md` | 1.5.6 产物路由改动的来龙去脉 |
| 部署说明 | `src\browser_automation_skills\deploy.md` | 部署相关 |

### 一图记住整个流程

```
① 装好（venv + 包 + 浏览器）
        ↓
② 配好（config.yaml：cwd、Key、稳定性开关）
        ↓
③ 接好（MCP 客户端能列出 74 个工具）
        ↓
④ 试好（让 AI 用自然语言跑通一次流程）
        ↓
⑤ 录好（record_actions=true → 生成 recorded_actions/*.actions.yaml）
        ↓
⑥ 固化（promote 把录制写进用例的 actions）
        ↓
⑦ 回归（写用例 + assertions → 一条命令批量跑 → 看报告）
```

**新手最常走错的三个地方**，再强调一遍：

1. `cwd` 没指向工作区根 → 配置找不到、截图乱飞；
2. 用例不写 `assertions` → "通过"毫无意义；
3. 改了配置/源码不重启不重装 → 以为改了其实没生效。

把这三点记住，剩下的都可以慢慢查本文档。














