# 优化 browser-automation-skills Agent 2.0 方案

## 1. 结论

当前项目已有基础 Agent 能力：
- `skills/agent.py` 中的 `BrowserAgent` 和 `ExecuteTaskSkill`
- `skills/dom_snapshot.py` 中的 `GetDomSnapshotSkill`, `ClickByIndexSkill`, `FillByIndexSkill`

因此，文档中提到的优化目标是适合该项目的，也能够实现。

不过，`docs/优化browser-automation-skills-agent.md` 目前更像是一份设计提案，而非与当前代码完全一致的实现说明。要把它落实为可执行功能，需要补齐 `BatchTestAgent`、批量执行、用例上下文、失败分析、报告生成等模块。

## 2. 现有文档评估

### 2.1 优点

- 目标明确：用例级上下文隔离、智能规划、失败分析、结果验证、批量执行
- 设计合理：将 `SkillManager` 作为共享执行层，将 Agent 作为调度层
- 与现有项目契合度高：已具备 LLM 规划、DOM 快照、索引点击等关键基础

### 2.2 主要问题 / 不一致点

- 当前代码并未实现 `BatchTestAgent`、`TestCaseContext`、`BatchTestResult` 等类
- 文档中出现了 `FailureAnalysis`、`VerificationResult`、`TestCaseResult` 等数据类型，但项目里无对应实现
- 文档假设 `execute_batch_testcases` Skill 可以直接从文件执行批量用例，但现有 `BaseSkill` 和 `mcp_server` 未实现文件读取/Excel 依赖处理
- `BatchTestAgent` 的 LLM 规划、失败分析、预期验证等部分需要与现有 `BrowserAgent` 做整合，而不是完全独立复制
- 文档提到“每个用例独立上下文”，现有 `SkillManager` 其实只维护一个 `current_page`，还需额外设计用例级状态管理

### 2.3 适不适合优化

适合。理由：
- 项目定位正是“Playwright + MCP + LLM 自动化”，Agent 优化是自然扩展
- 现有 `SkillManager`、DOM 索引、MCP 工具暴露机制为 Agent 进阶打下了基础
- 现在的 Agent 已具备规划能力，优化重点应放在“结构化批量测试”和“可靠执行”上

## 3. 可行性分析

### 3.1 已具备的可复用能力

- LLM 计划执行：`BrowserAgent.execute_task`
- DOM 可读快照：`GetDomSnapshotSkill`
- 索引点击/填写：`ClickByIndexSkill`, `FillByIndexSkill`
- Skill 执行框架：`SkillManager.execute`, `execute_chain`
- MCP 动态工具生成：`mcp_server.py`

### 3.2 尚待实现的模块

- `BatchTestAgent` / `TestCaseContext` / `BatchTestResult`
- 预期结果验证模块
- 失败分析和智能重试策略
- 批量用例导入（建议先实现 JSON，再观察是否需要 Excel）
- `execute_batch_testcases` Skill（可选，但建议先做成纯 Python 执行器，再扩展为 Skill）
- 报告生成功能

### 3.3 实现难度

- 低到中：核心逻辑并不复杂，关键在于设计清晰的执行流程和状态管理
- 中到高：LLM 输出错误处理、上下文长度控制、页面状态与失败原因分析需要谨慎

## 4. 推荐实现架构

### 4.1 总体结构

- `SkillManager` 继续负责 Skill 注册和执行
- `BrowserAgent` 保留单任务自动规划能力
- 新增 `BatchTestAgent` 负责“批量测试用例执行”
- 新增数据模型：`TestCase`, `TestCaseContext`, `TestCaseResult`, `BatchTestResult`
- 批量测试执行器采用“单用例独立上下文 + 共享 SkillManager”
- 仅传递最近若干步历史给 LLM，避免上下文过大

### 4.2 关键职责

- `BatchTestAgent`：
  - 接收多个测试用例
  - 为每个用例创建独立上下文
  - 通过 `BrowserAgent` 或类似逻辑执行单个用例
  - 收集测试结果并生成汇总报告

- `BrowserAgent`：
  - 保持单任务自动规划能力
  - 提供 `execute_task` / `_plan_next_step` / `_get_page_state`
  - 借助 DOM 快照与索引技能降级选择器依赖

- `ExecuteTaskSkill`：
  - 作为 MCP/Skill 入口，调用 `BrowserAgent`
  - 继承 `BaseSkill`，可被 MCP 服务暴露

- `TestCaseParser`：
  - 支持 JSON 导入
  - Excel 可作为可选扩展，避免初期过多依赖

## 5. 2.0 实现计划

### Phase 0：评估与准备

- [ ] 确认当前 `skills/agent.py` 的 `BrowserAgent` 逻辑是否稳定
- [ ] 确认 `mcp_server.py` 是否已在 `SkillManager` 注册新 Skill 的情况下正确暴露
- [ ] 评估是否需要把 `LLM client` 抽象成统一入口，减少多处重复获取逻辑

### Phase 1：批量测试执行与上下文隔离

- [ ] 新增 `TestCase` 数据模型
- [ ] 新增 `TestCaseContext` / `TestCaseResult` / `BatchTestResult`
- [ ] 新增 `BatchTestAgent`，实现 `execute_batch(test_cases)`
- [ ] 新增 `_execute_single_case()`，支持：
  - 单用例独立 history
  - 操作去重防环
  - 前置 URL
  - 连续失败停止
- [ ] 先实现 JSON 用例导入，后续按需扩展 Excel

### Phase 2：预期结果验证与失败分析

- [ ] 实现 `VerificationResult`/`FailureAnalysis` 数据模型
- [ ] 新增 `_verify_expected_result(expected, page_state)`，使用 LLM 或技能组合判断是否完成
- [ ] 新增 `_analyze_failure(step_record, page_state)`，并根据错误类型生成重试建议
- [ ] 将失败分析结果纳入 `BatchTestAgent` 的决策

### Phase 3：报告与输出

- [ ] 实现 `BatchTestResult.generate_report(output_path=None)`
- [ ] 先支持 Markdown 简洁报告
- [ ] 可选扩展 HTML 报告、截图列表、失败原因细节

### Phase 4：Skill 级入口与 MCP 暴露

- [ ] 新增 `ExecuteBatchTestCasesSkill` 或类似 Skill（可选）
- [ ] 使 `mcp_server.py` 能暴露批量执行工具
- [ ] 优化 `Tool` 描述与参数 schema

### Phase 5：测试与迭代

- [ ] 编写单元测试：`skills/agent.py`、`skills/dom_snapshot.py`
- [ ] 编写集成测试：`test_execute_task.py` 扩展为 `test_batch_execute_task.py`
- [ ] 使用真实用例验证成功率、失败处理、上下文隔离效果

## 6. 具体文件与改动建议

### 6.1 新增文件

- `docs/优化browser-automation-skills-agent2.0.md`：实现计划与设计说明

### 6.2 修改文件

- `skills/agent.py`
  - 新增 `BatchTestAgent`，组织批量执行逻辑
  - 新增数据模型与辅助方法
  - 保留并优化现有 `BrowserAgent`

- `skills/__init__.py`
  - 导出 `BatchTestAgent`、`TestCaseParser` 等新能力

- `skills/dom_snapshot.py`
  - 若需要，可增加 `get_page_state` 或更结构化的快照返回

- `mcp_server.py`
  - 如果需要将批量执行暴露为 MCP 工具，注册新 Skill 或新增工具入口

- `tests/test_execute_task.py`
  - 扩展为 `tests/test_batch_execute_task.py`
  - 新增 JSON 用例解析与执行验证

## 7. 推荐改进顺序

1. 先实现 `BatchTestAgent` 的基本框架和 JSON 导入
2. 再补齐 `VerificationResult` 和 `_verify_expected_result`
3. 接着实现失败分类与智能重试
4. 最后补报告与 MCP Skill 暴露

## 8. 风险与注意点

- LLM 输出稳定性：必须添加 JSON 解析容错与降级策略
- 页面变化导致 DOM 快照失效：索引点击后应及时失效缓存或重新捕获
- 批量执行时浏览器状态连续性：建议在执行多个用例前后清理或重设页面状态
- Excel 依赖建议后置实现，避免增加初期复杂度

## 9. 结论建议

这个优化方案是可行的，且适合 `browser-automation-skills` 的发展方向。

建议先把现有文档中“愿景性内容”整理为执行计划，优先落地“批量用例执行 + 用例隔离 + 失败分析 + 结果报告”，再根据实现效果决定是否继续补 Excel 和 HTML 报告。
