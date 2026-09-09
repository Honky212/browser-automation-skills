# 浏览器自动化测试最佳实践

## 一、测试用例设计原则

### 1. 独立性原则
- 每个测试用例应独立运行，不依赖其他用例的执行结果
- 使用 `setup_url` 确保每个用例从正确的起点开始
- 测试完成后清理状态，不影响后续测试

### 2. 可验证性原则
- 每个用例应有明确的预期结果
- 使用断言验证操作结果
- 失败时截图保存证据

### 3. 可读性原则
- 使用自然语言描述测试步骤
- 避免技术细节（如 CSS 选择器）出现在用例中
- 用例应易于理解和维护

## 二、选择器最佳实践

### 优先级策略
1. **属性选择器**：`[name='username']` - 最稳定，适合表单
2. **ID 选择器**：`#submit-btn` - 唯一标识
3. **类选择器**：`.btn-primary` - 适合同类元素
4. **DOM 索引**：无需选择器，AI 自动定位

### 避免使用
- 绝对 XPath：`/html/body/div[2]/div[1]/button`
- 动态生成的类名：`.sc-fdsjf923`
- 位置依赖的选择器：`div:nth-child(3)`

## 三、等待策略

### 推荐方式
```python
# 等待元素可见
await manager.execute("wait_for_element", selector="#btn", timeout=10000)

# 等待网络空闲
await manager.execute("navigate", url="https://example.com", wait_until="networkidle")

# 等待特定条件
await manager.execute("wait_for_function", script="return document.readyState === 'complete'")
```

### 避免方式
```python
# ❌ 不推荐：固定等待
await manager.execute("wait", seconds=5)
```

## 四、异常处理

### 重试机制
```python
def safe_click(selector, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await manager.execute("click", selector=selector)
            if result.success:
                return result
            await manager.execute("wait", seconds=1)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await manager.execute("wait", seconds=2)
```

### 常见异常处理
| 异常 | 处理策略 |
|------|----------|
| 元素未找到 | 重试 + 超时 |
| 网络超时 | 刷新页面 |
| 权限错误 | 记录并跳过 |
| 页面加载失败 | 降级处理 |

## 五、性能优化

### 1. DOM 缓存
```python
# 获取 DOM 快照后多次使用
await manager.execute("get_dom_snapshot")
await manager.execute("click_by_index", index=0)
await manager.execute("click_by_index", index=1)
```

### 2. 批量操作
```python
# 使用链式执行减少往返
await manager.execute("execute_chain", steps=[
    {"skill": "navigate", "params": {"url": "https://example.com"}},
    {"skill": "fill_input", "params": {"selector": "input", "value": "test"}}
])
```

### 3. 并行测试
```python
# 使用 BatchExecutor 并行执行
executor = BatchExecutor(parallel=True, max_workers=3)
result = executor.run_from_file("test_cases.xlsx")
```

## 六、安全实践

### 1. 敏感数据保护
- 不在测试用例中硬编码密码
- 使用环境变量或配置文件
- 清理测试数据

### 2. 权限控制
- 使用最小权限原则
- 限制测试账户的权限范围
- 测试完成后撤销权限

### 3. 资源限制
- 设置合理的超时时间
- 限制并发连接数
- 定期清理临时文件

## 七、测试报告最佳实践

### 报告内容
- 测试用例总数、通过数、失败数
- 每个用例的执行时间
- 失败用例的截图和错误信息
- 测试执行时间线

### 报告格式选择
- **HTML**：交互式报告，便于查看
- **PDF**：存档和分享
- **JSON**：便于程序处理和集成

## 八、与其他工具集成

### 持续集成
```yaml
# GitHub Actions 示例
- name: Run Tests
  run: |
    python -m pytest tests/
    python batch_runner.py --input test_cases.xlsx --output report.html

- name: Upload Report
  uses: actions/upload-artifact@v4
  with:
    name: test-report
    path: report.html
```

### 测试管理平台
- 集成 TestRail、Jira 等测试管理工具
- 自动同步测试结果
- 生成趋势分析报告

## 九、调试技巧

### 1. 可见模式
```bash
python -m browser_automation_skills.mcp_server --headed
```

### 2. 放慢操作节奏
> MCP 服务目前仅支持 `--headed` 与 `--config` 参数，没有 `--slow-mo` 选项。如需放慢操作节奏，可在步骤之间插入等待：

```python
await manager.execute("wait", seconds=1)
```

### 3. 日志记录
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 4. 截图调试
```python
await manager.execute("screenshot", path="debug.png")
```

## 十、常见问题与解决方案

### 问题 1：元素定位不稳定
**原因**：页面动态加载、选择器不稳定
**解决方案**：使用属性选择器、增加等待时间、使用 DOM 索引

### 问题 2：测试执行速度慢
**原因**：等待时间过长、串行执行
**解决方案**：优化等待策略、使用并行执行、启用缓存

### 问题 3：验证码拦截
**原因**：网站安全机制
**解决方案**：使用测试环境绕过、配置验证码服务、使用视觉识别

### 问题 4：页面加载超时
**原因**：网络问题、页面资源过大
**解决方案**：增加超时时间、使用网络空闲等待、优化网络环境

## 十一、版本控制最佳实践

### 测试用例管理
- 将测试用例纳入版本控制
- 使用分支管理不同版本的测试
- 定期审查和更新测试用例

### 配置管理
- 敏感配置使用环境变量
- 配置文件模板化
- 不同环境使用不同配置

## 十二、团队协作

### 代码审查
- 测试代码同样需要审查
- 确保测试用例质量
- 共享最佳实践

### 知识共享
- 定期分享测试经验
- 维护测试文档
- 建立测试用例库

---

## 附录：检查清单

### 测试用例检查
- [ ] 用例独立可运行
- [ ] 有明确的预期结果
- [ ] 设置了合理的超时时间
- [ ] 使用了稳定的选择器

### 测试执行检查
- [ ] 启用了 DOM 缓存
- [ ] 使用了合适的等待策略
- [ ] 设置了异常处理
- [ ] 失败时保存了截图

### 报告检查
- [ ] 包含完整的统计信息
- [ ] 失败用例有详细信息
- [ ] 报告格式易于阅读
- [ ] 包含执行时间信息