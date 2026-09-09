"""
Browser-Automation-Skills MCP Server
将 Skills 暴露为 MCP 工具，供 AI 助手调用
"""

# 设置 Playwright 浏览器路径（仅在未手动指定时使用默认路径）
import os
import sys

if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    if sys.platform == "win32":
        # Windows: %LOCALAPPDATA%\ms-playwright
        _local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(_local_app_data, "ms-playwright")
    elif sys.platform == "darwin":
        # macOS: ~/Library/Caches/ms-playwright
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")
    else:
        # Linux/其他: ~/.cache/ms-playwright
        _cache_dir = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(_cache_dir, "ms-playwright")

import asyncio
import inspect
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional, Dict, List, Union

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    ServerCapabilities,
)

from playwright.async_api import BrowserContext

try:
    # v1.5.0+ 布局：mcp_server 位于 browser_automation_skills 包内
    from . import create_manager
    from .base import SkillResult
    from .browser_launcher import BrowserLauncher
except ImportError:
    # 兼容旧布局：mcp_server.py 位于项目根目录
    from browser_automation_skills import create_manager
    from browser_automation_skills.base import SkillResult
    from browser_launcher import BrowserLauncher


_PARAM_HINTS = {
    "selector": "CSS 选择器或 XPath，用于定位目标元素",
    "url": "要打开的页面 URL",
    "timeout": "等待超时，单位为毫秒",
    "wait_until": "导航或刷新时等待的页面加载状态，如 load、domcontentloaded 或 networkidle",
    "text": "要查找或比较的文本内容",
    "attribute": "元素属性名",
    "expected": "期望值，用于比较或断言",
    "exact": "是否执行精确匹配",
    "case_sensitive": "是否区分大小写",
    "path": "本地文件路径",
    "full_page": "是否截取完整页面截图",
    "action": "弹窗操作类型，例如 accept、dismiss 或 prompt",
    "prompt_text": "prompt 弹窗中输入的文本",
    "trigger_selector": "触发下载的元素选择器",
    "cookies": "要设置的 Cookie 列表",
    "data": "要写入 Local Storage 的键值对",
    "page_index": "目标标签页索引，从 0 开始",
    "keep_index": "要保留的标签页索引，从 0 开始",
    "seconds": "等待时长，单位为秒",
    "expression": "要在页面上下文中评估为 true 的 JavaScript 表达式",
    "arg": "传递给脚本的可选参数",
    # DOM 索引化 Skills 参数
    "index": "元素索引（从 1 开始），对应 get_dom_snapshot 返回的元素列表序号",
    "readable": "是否返回人类可读的文本格式",
    "max_elements": "最大返回元素数量",
    "value": "要填写的值",
    # Agent Skills 参数
    "task": "自然语言任务描述，例如 '打开百度，搜索 browser-automation-skills'",
    "max_steps": "最大执行步数，用于限制 Agent 最大尝试次数",
    "max_retries": "最大连续失败次数，超过此值后 Agent 将停止执行",
    # Vision Skills 参数
    "prompt": "分析提示词，用于描述你想了解页面什么内容",
    "model": "视觉模型名称，如 gpt-4o",
    # Performance Skills 参数
    "cache_type": "缓存类型：all（全部）、dom（DOM 快照）、llm（LLM 响应）",
    "use_cache": "是否使用缓存（默认 True）",
}


# 已知枚举值映射（参数名 → 可选值列表）
_PARAM_ENUMS: Dict[str, List[str]] = {
    "button": ["left", "right", "middle"],
    "wait_until": ["load", "domcontentloaded", "networkidle", "commit"],
    "action": ["accept", "dismiss"],
    "state": ["visible", "hidden", "attached", "detached"],
    "browser_type": ["chromium", "firefox", "webkit"],
    "cache_type": ["all", "dom", "llm"],
    "selector_type": ["css", "xpath"],
}


def _annotation_to_json_type(annotation) -> dict:
    """将 Python 类型注解转换为 JSON Schema 类型片段"""
    # 无注解或 None → 默认 string
    if annotation is inspect._empty or annotation is None:
        return {"type": "string"}

    # 基本类型映射
    _PRIMITIVE_MAP = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    if annotation in _PRIMITIVE_MAP:
        return {"type": _PRIMITIVE_MAP[annotation]}

    # 裸容器类型
    if annotation in (dict, Dict):
        return {"type": "object"}
    if annotation in (list, List):
        return {"type": "array"}

    # Any → string（MCP 工具不支持任意类型，退化为 string）
    if annotation is Any:
        return {"type": "string"}

    # 处理泛型：Optional[T] / Union[...] / Dict[K,V] / List[T]
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    # Optional[T] / Union[T, None] / Union[T1, T2, ...]
    if origin is Union:
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            # Optional[T] → 递归处理 T
            return _annotation_to_json_type(non_none_args[0])
        elif len(non_none_args) > 1:
            # 多类型 Union → anyOf
            return {"anyOf": [_annotation_to_json_type(a) for a in non_none_args]}
        else:
            return {"type": "string"}

    # Dict[K, V] → object
    if origin is dict:
        return {"type": "object"}

    # List[T] → array
    if origin is list:
        return {"type": "array"}

    # 未知类型 → string
    return {"type": "string"}


def _get_param_description(name: str, annotation, default) -> str:
    if name in _PARAM_HINTS:
        return _PARAM_HINTS[name]
    if name.endswith("_selector"):
        return "CSS 选择器或 XPath，用于定位目标元素"
    if name in {"page_index", "keep_index"}:
        return "目标标签页索引，从 0 开始"
    if name.endswith("_index"):
        return "元素索引，用于定位目标元素"
    if name == "data":
        return "要写入当前页面/浏览器上下文的数据对象"
    if name == "cookies":
        return "要设置的 Cookie 数组，每项为 Cookie 对象"
    if name == "full_page":
        return "是否对整个页面进行截屏"
    if name == "wait_until":
        return "导航完成前等待的页面加载状态"
    if name == "prompt_text":
        return "用于 prompt 弹窗的输入文本"
    if default is not inspect._empty and default is not None:
        return f"可选参数，默认值为 {default}"
    return ""


def _get_tool_description(skill_class) -> str:
    desc = getattr(skill_class, "description", "") or ""
    if desc:
        return desc
    class_doc = inspect.getdoc(skill_class) or ""
    if class_doc:
        return class_doc.splitlines()[0]
    run_doc = inspect.getdoc(skill_class.run) or ""
    return run_doc.splitlines()[0] if run_doc else ""


logger = logging.getLogger(__name__)


def _default_config_candidates() -> List[Path]:
    """默认配置文件搜索路径（按优先级），兼容开发/部署布局"""
    here = Path(__file__).resolve().parent
    candidates: List[Path] = []
    # 0) 环境变量显式指定（绝对路径，最可靠）
    env_cfg = os.environ.get("BROWSER_AUTOMATION_SKILLS_CONFIG")
    if env_cfg:
        candidates.append(Path(env_cfg))
    # 1) 从包位置逐级向上查找（覆盖“源码装在 site-packages / venv 内”的布局，不依赖 cwd）
    for base in [here, *here.parents]:
        candidates.append(base / "config" / "config.yaml")
        candidates.append(base / "config.yaml")
    # 2) 工作目录兜底（cwd 为项目根目录时的标准部署布局）
    candidates.append(Path.cwd() / "config" / "config.yaml")
    candidates.append(Path.cwd() / "config.yaml")
    # 去重并保持优先级顺序
    seen = set()
    result = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _load_config(config_path: Optional[str] = None) -> dict:
    if config_path is None:
        config_path = next((p for p in _default_config_candidates() if p.exists()), None)
        if config_path is None:
            logger.warning("Config file not found in default locations. Using defaults.")
            return {}
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}. Using defaults.")
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config if isinstance(config, dict) else {}
    except Exception as e:
        logger.exception(f"Failed to load config from {config_path}: {e}")
        return {}


def _get_tool_input_schema(skill_class) -> dict:
    sig = inspect.signature(skill_class.run)
    properties = {}
    required = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue

        annotation = param.annotation
        # 使用辅助函数推断 JSON Schema 类型
        schema: dict = {"title": name, **_annotation_to_json_type(annotation)}

        # 枚举约束：如果参数名在已知枚举映射中，添加 enum
        if name in _PARAM_ENUMS:
            schema["enum"] = _PARAM_ENUMS[name]

        param_desc = _get_param_description(name, annotation, param.default)
        if param_desc:
            schema["description"] = param_desc
        if param.default is inspect._empty:
            required.append(name)
        else:
            schema["default"] = param.default

        properties[name] = schema

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class BrowserSkillServer:
    """Browser Skill MCP Server"""

    def __init__(self, config_path: Optional[str] = None):
        self.server = Server("browser-automation-skills")
        self._launcher: Optional[BrowserLauncher] = None
        self.browser_context: Optional[BrowserContext] = None
        self._headless = True
        self.config = _load_config(config_path)
        self.manager = create_manager(browser_context=None, config=self.config)
        self._setup_handlers()

    def _setup_handlers(self):
        """设置 MCP 处理器"""
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """列出所有可用的浏览器操作工具（动态从 manager 枚举）"""
            logger.debug("Listing tools via MCP request")
            tools = []
            # 如果 manager 尚未初始化，返回一个通用空列表（或少量启动工具）
            if self.manager is None:
                return tools

            for name, skill_class in self.manager._skills.items():
                tools.append(Tool(
                    name=name,
                    description=_get_tool_description(skill_class),
                    inputSchema=_get_tool_input_schema(skill_class)
                ))

            # 保证 execute_chain 工具存在
            tools.append(Tool(
                name="execute_chain",
                description="执行多个操作的链（一次性执行多个步骤）",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "description": "操作步骤列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "skill": {"type": "string", "description": "Skill 名称"},
                                    "params": {"type": "object", "description": "Skill 参数"}
                                },
                                "required": ["skill"]
                            }
                        }
                    },
                    "required": ["steps"]
                }
            ))

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """调用指定的工具"""
            logger.debug("MCP tool call: %s args=%s", name, arguments)
            if self.browser_context is None:
                logger.info("Lazy launching browser for tool: %s", name)
                await self.launch_browser(self._headless)

            try:
                if name == "execute_chain":
                    # 处理链式执行
                    steps = arguments.get("steps", [])
                    chain = []
                    for step in steps:
                        if not isinstance(step, dict):
                            continue
                        skill_name = step.get("skill")
                        params = step.get("params", step.get("args", {})) or {}
                        chain.append({"skill": skill_name, "params": params})
                    logger.info("Executing skill chain with %d steps", len(chain))
                    results = await self.manager.execute_chain(chain)
                    return [TextContent(type="text", text=json.dumps({
                        "success": all(r.success for r in results),
                        "results": [
                            {
                                "skill": chain[i]["skill"] if i < len(chain) else "unknown",
                                "success": r.success,
                                "message": r.message,
                                "data": r.data,
                                "error": r.error,
                            }
                            for i, r in enumerate(results)
                        ]
                    }, ensure_ascii=False, indent=2))]
                else:
                    # 处理单个 Skill
                    result = await self.manager.execute(name, **arguments)
                    return [TextContent(type="text", text=json.dumps({
                        "success": result.success,
                        "message": result.message,
                        "data": result.data,
                        "error": result.error
                    }, ensure_ascii=False, indent=2))]
            except Exception as e:
                logger.exception("Tool execution error for %s", name)
                return [TextContent(type="text", text=json.dumps({
                    "success": False,
                    "message": f"Tool execution error: {str(e)}",
                    "error": str(e)
                }, ensure_ascii=False, indent=2))]

    async def launch_browser(self, headless: bool = True):
        """启动浏览器（复用 BrowserLauncher）"""
        browser_config = self.config.get("browser", {}) if self.config else {}
        browser_type = browser_config.get("browser_type", "chromium")
        executable_path = browser_config.get("executable_path")
        viewport_config = browser_config.get("window_size", {}) or {}
        width = viewport_config.get("width", 1920)
        height = viewport_config.get("height", 1080)

        self._launcher = BrowserLauncher(
            headless=headless,
            viewport={"width": width, "height": height},
            browser_type=browser_type,
            executable_path=executable_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            disable_automation=True,
        )
        self.browser_context = await self._launcher.launch()
        self.manager = create_manager(browser_context=self.browser_context, config=self.config)
        logger.info("Browser launched and skill manager initialized (config loaded)")

    async def cleanup(self):
        """清理资源（委托 BrowserLauncher）"""
        logger.info("Cleaning up browser resources")
        if self._launcher is not None:
            await self._launcher.close()
            self._launcher = None
        self.browser_context = None

    async def run(self, headless: bool = True):
        """运行 MCP Server"""
        self._headless = headless

        # 使用 create_initialization_options() 自动根据已注册的处理器
        # （list_tools / call_tool 等）填充 capabilities，
        # 否则握手时声明空 capabilities，合规客户端（如 Trae）会认为
        # 本服务没有 tools 能力，从而不列出工具（显示 "No tools yet"）。
        init_options = self.server.create_initialization_options()
        
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    init_options,
                    raise_exceptions=True
                )
        finally:
            await self.cleanup()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Browser-Automation-Skills MCP Server")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    parser.add_argument("--config", type=str, default=None, help="Path to configuration YAML file")
    args = parser.parse_args()

    config = _load_config(args.config)
    log_config = config.get("logging", {})
    logging.basicConfig(
        level=log_config.get("level", "INFO"),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    browser_config = config.get("browser", {})
    headless = False if args.headed else browser_config.get("headless", True)

    server = BrowserSkillServer(config_path=args.config)
    await server.run(headless=headless)


if __name__ == "__main__":
    asyncio.run(main())