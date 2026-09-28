# 项目文件存放路径及各智能体 MCP 优化方案 2

- 编写日期：2026-09-28
- 适用基线：`browser_automation_skills` 1.5.5；Cline 4.1.19；Trae CN；CodeBuddy
- 当前工作区：`D:\browser_automation_skills`
- 目标：批量执行某个项目的用例时，截图、报告、录制动作等产物归入该项目；没有用例上下文的临时浏览产物归入 MCP server 工作区的 `screenshots/`。
- 状态：方案修订稿，尚未实施代码或 MCP 配置变更。

---

## 0. 结论

目标可以实现，但不能仅靠 MCP 配置中的静态 `cwd` 完成“同一个 server 根据每次用例切换输出目录”。建议采用以下约定：

1. MCP server 的 `cwd` 固定为 `D:\browser_automation_skills`，临时浏览截图默认写入 `D:\browser_automation_skills\screenshots`。
2. 每个被测项目根目录放置一个项目标记文件 `.browser-automation-project.yaml`。批量工具根据用例文件向上查找标记，找到后将该目录确定为本批次的产物根目录。
3. 批量执行的失败截图、报告和录制动作使用同一批次产物根目录；不修改进程全局 `cwd`，不修改 server 共享的 `config` 字典。
4. 不同 MCP 请求之间不共享批次的 `ContextVar` 上下文。只有批次内部发出的截图操作跟随该批次；另一个独立 MCP 请求仍走默认 `cwd` 规则。若要求多个请求互不影响，应使用独立 server / 浏览器实例。
5. 报告必须显式创建父目录，并使用与内容一致的 `.md` 扩展名。用例路径须限制在批准的工作区范围内，不能允许模型通过任意绝对路径把产物写到其他位置。

项目根不能可靠地只靠“用例文件的父目录”推断：用例放在 `project-1/testcases/case.json` 时，父目录是 `testcases`，而非 `project-1`。项目标记明确了目录边界，也允许用例目录任意嵌套。

---

## 1. 期望目录布局

```text
D:\browser_automation_skills\
├── config\
│   └── config.yaml                    # 当前 MCP server 的配置
├── screenshots\                       # 无批次上下文时的默认截图目录
├── project-1\
│   ├── .browser-automation-project.yaml
│   ├── config\
│   │   └── config.yaml                # 可选；作为项目资料，不自动切换 server 配置
│   ├── testcases\
│   │   └── test_cases_baidu.json
│   ├── screenshots\                  # 此项目批次产生的截图
│   ├── reports\                      # 此项目批次报告
│   └── recorded_actions\             # 启用录制时产生
└── project-2\
    ├── .browser-automation-project.yaml
    └── testcases\
        └── cases.yaml
```

项目标记文件可以只包含项目名，作为明确的目录边界：

```yaml
name: project-1
```

若项目目录本身就是用例文件的父目录，仍建议保留标记，避免未来调整目录结构后产物落点改变。

---

## 2. 输出目录契约

| 场景 | 目录锚点 | 期望目录 | 说明 |
|---|---|---|---|
| 普通 `screenshot` 工具调用，没有批量用例上下文 | MCP server `cwd` + `screenshot.output_dir` | `D:\browser_automation_skills\screenshots` | 需将 server `cwd` 固定为工作区根，配置保持 `./screenshots` |
| 批量用例中的失败截图 | 当前批次的项目根 | `<项目根>/screenshots` | 与单张截图目录一致；失败截图路径和实际文件路径必须一致 |
| 批量测试报告 | 当前批次的项目根 | `<项目根>/reports/<文件名>.md` | 批量结果当前由 `BatchTestResult.generate_report()` 生成 Markdown |
| LLM 成功执行后录制的动作 | 当前批次的项目根 | `<项目根>/recorded_actions` | 只有启用 `record_actions` 且有可录制步骤时才会生成 |
| 批次内的其他截图技能调用 | 当前批次上下文 | `<项目根>/screenshots` | 仅限同一批次调用链中的工具操作 |
| 独立并发的 MCP 截图请求 | 该请求自己的上下文 | 默认 `cwd/screenshots` | 不继承另一 MCP 请求的批次上下文 |

“没有项目、没有测试用例”的临时浏览，不创建项目目录，也不尝试从当前打开的网页推断项目；它固定走 server 的默认截图目录。

---

## 3. 当前源码行为与影响

本节以当前安装包 `D:\browser_automation_skills\.venv\Lib\site-packages\browser_automation_skills` 为准。

| 组件 | 当前行为 | 对目标的影响 |
|---|---|---|
| `ScreenshotSkill` | 从 `manager.config['screenshot']['output_dir']` 取目录；相对目录按 `os.getcwd()` 解析；传入的 `path` 只取 basename | 批次中不能靠传完整路径切换截图目录，需要受控的批次上下文 |
| `BatchTestAgent` | 默认失败截图目录为 `cwd/screenshots`；构造时创建该目录；录制目录取配置或 `cwd/recorded_actions` | 需要在创建 Agent 时传入本批次的截图和录制目录 |
| `ExecuteBatchTestCasesSkill` | 解析 `file_path`，创建 `BatchTestAgent`；`report_path` 未提供时不生成报告 | 批量入口应统一解析产物根并提供默认报告路径 |
| `BatchTestResult.generate_report()` | 生成 Markdown；直接打开 `output_path` 写入，不创建父目录 | 路由层必须先创建 `reports/`，报告扩展名应为 `.md` |
| `SkillManager` | 每次技能调用创建技能实例；`manager.config` 为同一 server 共享配置 | 不应通过临时改 `config` 或实例属性实现请求间路由 |
| MCP 低层 server | 将收到的消息分别调度为任务处理 | 两个独立 MCP 请求不会共享一个请求中设置的 `ContextVar` 值 |

### 3.1 配置文件与产物目录是两件事

按用例文件选择产物目录，不会自动切换 LLM 配置、API key、浏览器设置或 `skill_policy`。当前包的配置搜索会优先检查包位置附近及显式配置，再回退到工作目录等路径；仅仅把项目 `config/config.yaml` 放进项目，不代表 server 一定会自动使用它。

本方案第一阶段只路由产物。若不同项目还要求不同的模型、密钥、浏览器实例或技能策略，应为项目配置独立 MCP server 条目，或另行设计经过隔离的项目配置加载机制。

### 3.2 不要在处理请求时调用 `os.chdir`

`cwd` 是进程级状态，不是请求级状态。server 同时处理多个请求时，在批次期间切换 `cwd` 会让其他请求、相对配置路径和文件操作受到影响。请求级路由应使用明确的绝对输出路径和任务局部上下文，不能用 `chdir` 充当路由机制。

---

## 4. 项目根目录解析规则

批量执行开始时，先解析并校验用例文件，再确定项目根：

1. 将 `file_path` 解析为绝对路径，并确认文件存在且为普通文件。
2. 确认该文件位于配置的允许工作区根目录之内。
3. 从用例文件的父目录开始向上查找 `.browser-automation-project.yaml`，在允许工作区根目录以内找到的最近标记目录即为项目根。
4. 如果在允许工作区根目录内没有找到项目标记，按“未识别项目”处理：批量产物回退到 server 默认根，记录明确警告。若部署策略要求每个批量用例必须归属项目，可改成直接拒绝执行，避免静默落错目录。
5. 若路径不在允许工作区根目录内，拒绝执行，不读取用例，也不在该路径旁写入报告、截图或录制文件。

路径校验必须在 `resolve()` 后进行，并覆盖 `..`、绝对路径、盘符切换和符号链接等情况。不要让模型通过 `file_path` 间接指定任意产物目录。

> 当前 `project-1` 只有 `test_cases_baidu.json`，尚无项目标记。实施前需要在 `project-1` 创建标记文件，并可将用例继续放在根目录或迁入 `testcases/`；两种布局都会解析到同一个项目根。

---

## 5. 实现建议

### 5.1 优先修改包的正式实现

推荐在 `browser_automation_skills` 的正式源码中增加一个清晰的产物上下文，而不是长期依赖启动脚本猴补丁：

- 增加项目根解析与允许目录校验函数。
- 批量技能入口解析项目根后，创建本次执行的 `ArtifactContext`，至少包含 `project_root`、`screenshot_dir`、`report_dir`、`record_dir`。
- 在批次执行期间通过 `ContextVar` 保存该上下文，并在 `finally` 中恢复旧值。
- 创建 `BatchTestAgent` 时显式传入 `screenshot_dir` 和 `record_dir`。
- 批次中的 `ScreenshotSkill` 从当前 `ArtifactContext` 取截图目录；没有批次上下文时沿用原来的 `config + cwd` 行为。
- 报告路径由批次入口确定；写入前创建父目录，并返回实际写入路径。
- 失败截图记录的路径应取截图技能实际返回的路径，避免报告中的路径与落盘位置不一致。

`ContextVar` 只用于批次调用链内部传递上下文，不代表其他独立 MCP 请求会跟随该批次。若需要让独立请求也带项目上下文，应让调用方显式传项目标识，并单独校验和解析。

### 5.2 如暂时只能在安装环境加启动层

若暂时不能修改并重打 wheel，可用一个版本锁定的启动适配层承载路由，但应满足：

- 所有补丁目标、原方法和签名在修改前一次性校验。
- `try/except` 覆盖完整的补丁安装过程；校验失败时不修改任何类，并按明确策略回退或退出。
- 包装方法使用 `functools.wraps`，保持 MCP 工具的输入 schema。
- 把 `None`、缺省和空字符串报告路径统一为自动报告路径。
- 创建输出目录；使用 `.md`；并记录实际生成的绝对路径。
- 有自动化测试覆盖指定的包版本；升级 `browser_automation_skills` 后重新运行测试。

不要把“补丁出错后继续启动”作为无条件的安全策略：如果路由失效会造成产物写到错误目录，应在日志中显著报错；严格部署可拒绝启动或拒绝批次，而不是静默降级。

---

## 6. MCP 客户端配置

### 6.1 通用要求

- `cwd` 固定为 MCP 工作区根：`D:\browser_automation_skills`。
- `command` 指向当前安装包所在 Python 环境的解释器。
- 使用 `python -m browser_automation_skills.mcp_server --headed` 启动；不要使用已发现存在异步入口问题的 console script。
- 通过 `BROWSER_AUTOMATION_SKILLS_CONFIG` 显式指定当前 server 配置文件，避免包目录向上搜索时先命中其他 `config/config.yaml`。
- 默认截图目录保持相对路径 `./screenshots`。
- API key 使用客户端 `env` 显式传入或使用未提交的本地配置；不得把真实密钥提交到仓库。

### 6.2 Cline 配置形状

Cline 4.1.19 的 stdio 配置把 `cwd` 放在 `transport` 对象内，与 `command`、`args` 和 `env` 同级：

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "transport": {
        "type": "stdio",
        "command": "D:\\browser_automation_skills\\.venv\\Scripts\\python.exe",
        "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
        "cwd": "D:\\browser_automation_skills",
        "env": {
          "BROWSER_AUTOMATION_SKILLS_CONFIG": "D:\\browser_automation_skills\\config\\config.yaml"
        }
      },
      "disabled": false,
      "autoApprove": [],
      "timeout": 60
    }
  }
}
```

本机记录显示 Cline 有 live 配置和旧副本；修改时先确认实际生效文件，并在修改后重启 server 验证。客户端版本升级后应重新验证 `cwd` 的运行时行为，不只依赖扩展源码结论。

### 6.3 Trae CN / CodeBuddy 配置形状

两者按当前记录使用扁平 stdio 字段：

```json
{
  "mcpServers": {
    "browser-automation-skills": {
      "command": "D:\\browser_automation_skills\\.venv\\Scripts\\python.exe",
      "args": ["-m", "browser_automation_skills.mcp_server", "--headed"],
      "cwd": "D:\\browser_automation_skills",
      "env": {
        "BROWSER_AUTOMATION_SKILLS_CONFIG": "D:\\browser_automation_skills\\config\\config.yaml"
      },
      "disabled": false
    }
  }
}
```

客户端 schema 与版本有关。将配置复制到 Trae CN 或 CodeBuddy 前，应以该客户端当前版本的配置格式为准，不要把 Cline 的 `transport` 嵌套结构照搬过去。

---

## 7. 部署与迁移步骤

1. 确认 server 使用的 Python 环境已安装 `browser_automation_skills==1.5.5` 和所需 Playwright 浏览器。
2. 在 `project-1` 建立 `.browser-automation-project.yaml`；按需把用例放在项目根或 `testcases/`。
3. 检查 server `config/config.yaml` 的 `screenshot.output_dir` 为 `./screenshots`，并显式配置 MCP `cwd` 与 `BROWSER_AUTOMATION_SKILLS_CONFIG`。
4. 先只调整一个 MCP 客户端配置，重启其 server；确认启动命令、Python 解释器、`cwd` 和配置文件路径。
5. 在单独的验证用例上测试：默认临时截图、项目批次成功、项目批次失败、报告默认路径、录制路径。
6. 验证通过后再同步更新其他客户端配置。
7. 保留现有 `start_mcp.py`，直到新配置已在实际客户端完成运行验收；不要先删除仍被客户端引用的启动脚本。
8. 实施完成后更新部署文档、配置示例和版本说明；真实 API key 保持在本地配置或客户端环境变量中。

---

## 8. 验收测试

| 编号 | 输入 / 操作 | 预期结果 |
|---|---|---|
| T1 | 在 server `cwd` 下直接调用 `screenshot` | 文件出现在 `D:\browser_automation_skills\screenshots`；响应返回的路径指向该文件 |
| T2 | 执行 `project-1/test_cases_baidu.json` | 截图、报告和启用的录制文件出现在 `project-1` 对应子目录 |
| T3 | 执行 `project-1/testcases/case.json` | 仍路由到 `project-1`，不能落在 `project-1/testcases` |
| T4 | 用例路径为绝对路径，且位于允许工作区 | 与相对路径得到相同项目根 |
| T5 | 用例位于允许工作区但没有项目标记 | 按已配置策略回退到默认根并警告，或明确拒绝；不得猜错项目根 |
| T6 | 用例路径包含 `..`、指向工作区外或通过符号链接逃逸 | 拒绝执行，不在越界位置创建文件 |
| T7 | `report_path` 缺省或显式为 `null` | 自动创建 `reports/`，生成 `.md` 报告，并在工具响应中返回实际路径 |
| T8 | 报告指定路径的父目录不存在 | 自动创建目录后成功写入 |
| T9 | 用例失败并触发失败截图 | 失败截图的响应路径、报告记录路径和实际文件路径完全一致 |
| T10 | 批次执行期间另一个独立 MCP 请求调用 `screenshot` | 仍写到默认 `cwd/screenshots`；不依赖另一个请求的 `ContextVar` |
| T11 | 同一项目短时间内执行多个报告任务 | 不覆盖其他报告；文件名具有足够唯一性 |
| T12 | 升级包或变更工具签名 | 路由测试失败时能够明确阻止错误落盘，不静默伪装为成功 |

批量测试和普通截图共用一个 MCP server / 浏览器实例时，还应避免同时执行会相互干扰的浏览器操作。路由上下文隔离不等于浏览器页面操作隔离；确实要求并发硬隔离时，为不同项目启动独立 server 和浏览器实例。

---

## 9. 风险边界与决策

| 议题 | 决策 |
|---|---|
| 一个 server 服务多个项目，只要求产物归属正确 | 使用项目标记 + 批次产物上下文 |
| 项目需要独立模型、密钥、浏览器或技能策略 | 单独 MCP server 条目；产物路由规则仍可保留 |
| 独立请求是否继承正在执行的批次项目 | 不继承；默认回到 server `cwd`，避免隐式跨请求状态 |
| 如何从任意用例路径判断项目 | 必须找到明确标记；不把“用例文件父目录”当作通用项目根 |
| 启动脚本是否立即废弃 | 否；待新 `cwd` 配置和路由实现通过真实客户端验收后再决定 |
| 当前方案是否已落地 | 否；文档、包源码和 MCP 客户端配置尚未因本方案修改 |

---

## 10. 当前证据与待确认项

### 已从安装包源码确认

- 安装包版本为 1.5.5。
- 截图技能的相对目录按当前工作目录解析，传入截图路径只使用 basename。
- 批量 Agent 的失败截图和录制目录可通过构造参数指定。
- 批量报告由 `BatchTestResult.generate_report()` 输出 Markdown，且不自动创建父目录。
- MCP server 使用并发任务处理请求；独立请求不应假设会继承另一个请求的 `ContextVar`。
- 批量入口当前不会自动从用例路径推导项目输出目录。

### 实施前仍需运行验证

- Cline 当前 live 配置在重启后的 `cwd` 是否按预期生效。
- Trae CN、CodeBuddy 当前安装版本的配置 schema 与 `cwd` 实际传递行为。
- 新路由实现是否覆盖所有本项目要求的产物，以及工具响应中报告/截图路径是否为最终绝对路径。
- 失败截图和默认报告在客户端真实批次中的行为。

本方案 2 是路径规则和实施验收方案，不代表上述运行验证已经完成。
