"""视觉支持模块 - 提供多模态页面分析能力"""

import base64
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from playwright.async_api import Page

from .base import BaseSkill, SkillResult
from .manager import SkillManager

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class VisionAnalysisResult:
    """视觉分析结果"""
    success: bool = False
    description: str = ""             # 页面描述
    elements_found: List[Dict] = field(default_factory=list)  # 识别到的元素
    answer: str = ""                  # 对用户问题的回答
    raw_response: str = ""            # 原始响应
    error: str = ""                   # 错误信息


# ============================================================
# 视觉模型适配器协议
# ============================================================

class VisionModelAdapter(Protocol):
    """视觉模型适配器协议（插件化）"""

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        **kwargs,
    ) -> str:
        """
        分析图片并返回文本结果

        Args:
            image_base64: Base64 编码的图片
            prompt: 分析提示词
            **kwargs: 其他参数

        Returns:
            str: 分析结果文本
        """
        ...


# ============================================================
# 具体适配器实现
# ============================================================

class OpenAIVisionAdapter:
    """OpenAI 视觉模型适配器（支持 gpt-4o 等多模态模型）"""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        config: Optional[dict] = None,
    ):
        # 优先使用传入参数，其次使用配置字典，最后使用环境变量
        self.model = model
        self.api_key = api_key or (config or {}).get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or (config or {}).get("base_url", "") or os.environ.get("OPENAI_BASE_URL")
        self.max_tokens = max_tokens or (config or {}).get("max_tokens", 1024)
        self.temperature = temperature or (config or {}).get("temperature", 0.1)
        self._client = None

    def _get_client(self):
        """懒加载客户端"""
        if self._client is None:
            from openai import AsyncOpenAI
            kwargs = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        **kwargs,
    ) -> str:
        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "low",  # 低分辨率，减少 token 消耗
                            },
                        },
                    ],
                }
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        return response.choices[0].message.content or ""


class DashScopeVisionAdapter:
    """阿里云 DashScope 视觉模型适配器（支持 qwen-vl-plus、qwen-vl-max 等多模态模型）"""

    def __init__(
        self,
        model: str = "qwen-vl-max",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        config: Optional[dict] = None,
    ):
        # 优先使用传入参数，其次使用配置字典，最后使用环境变量
        self.model = model
        self.api_key = api_key or (config or {}).get("api_key", "") or os.environ.get("DASHSCOPE_API_KEY", "")
        self.base_url = base_url or (config or {}).get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.max_tokens = max_tokens or (config or {}).get("max_tokens", 1024)
        self.temperature = temperature or (config or {}).get("temperature", 0.1)
        self._client = None

    def _get_client(self):
        """懒加载客户端"""
        if self._client is None:
            from openai import AsyncOpenAI
            kwargs = {
                "api_key": self.api_key,
                "base_url": self.base_url,
            }
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        **kwargs,
    ) -> str:
        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                                "detail": "low",  # 低分辨率，减少 token 消耗
                            },
                        },
                    ],
                }
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        return response.choices[0].message.content or ""


class DummyVisionAdapter:
    """虚拟视觉模型适配器（用于测试或无 LLM 环境）"""

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        **kwargs,
    ) -> str:
        return f"[Dummy Analysis] Received prompt: {prompt[:50]}... Image size: {len(image_base64)} bytes"


# ============================================================
# VisionSupport - 视觉支持核心类
# ============================================================

class VisionSupport:
    """
    视觉支持核心类

    提供页面截图、视觉分析等能力。
    使用插件化适配器，支持多种视觉模型后端。
    """

    def __init__(self, adapter: Optional[Any] = None):
        """
        初始化视觉支持

        Args:
            adapter: 视觉模型适配器（实现 VisionModelAdapter 协议）
        """
        self.adapter = adapter or DummyVisionAdapter()

    async def capture_screenshot_base64(
        self,
        page: Page,
        full_page: bool = False,
    ) -> str:
        """
        截取页面截图并返回 Base64 编码

        Args:
            page: Playwright Page 实例
            full_page: 是否截取完整页面

        Returns:
            str: Base64 编码的 PNG 图片
        """
        screenshot_bytes = await page.screenshot(full_page=full_page, type="png")
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def analyze_page(
        self,
        page: Page,
        prompt: str,
        full_page: bool = False,
        **adapter_kwargs,
    ) -> VisionAnalysisResult:
        """
        分析当前页面

        Args:
            page: Playwright Page 实例
            prompt: 分析提示词
            full_page: 是否使用完整页面截图
            **adapter_kwargs: 传递给适配器的额外参数

        Returns:
            VisionAnalysisResult: 分析结果
        """
        try:
            # 1. 截取页面截图
            image_base64 = await self.capture_screenshot_base64(page, full_page)

            # 2. 构建增强提示词
            enhanced_prompt = self._build_analysis_prompt(prompt, page)

            # 3. 调用适配器分析
            raw_response = await self.adapter.analyze_image(
                image_base64,
                enhanced_prompt,
                **adapter_kwargs,
            )

            return VisionAnalysisResult(
                success=True,
                description=raw_response,
                raw_response=raw_response,
            )

        except Exception as e:
            logger.exception(f"Page analysis failed: {e}")
            return VisionAnalysisResult(
                success=False,
                error=str(e),
            )

    def _build_analysis_prompt(self, user_prompt: str, page: Page) -> str:
        """构建页面分析提示词"""
        return f"""你是一个页面分析助手。请仔细观察这张页面截图，并回答用户的问题。

页面信息：
- URL: {page.url}

用户问题：
{user_prompt}

请详细描述你看到的内容，包括：
1. 页面的主要布局
2. 可见的文本内容
3. 可交互元素（按钮、输入框、链接等）
4. 任何弹窗或覆盖层

如果用户问了具体问题，请直接回答。"""


# ============================================================
# Skills
# ============================================================

class ScreenshotVisionSkill(BaseSkill):
    """截取页面截图并返回 Base64 编码（用于视觉分析，不保存文件）"""

    name = "screenshot_vision"
    description = "截取当前页面截图并返回 Base64 编码的图片"

    async def run(self, full_page: bool = False) -> SkillResult:
        page = await self.get_page()
        vision = VisionSupport()
        image_base64 = await vision.capture_screenshot_base64(page, full_page)

        return SkillResult(
            success=True,
            message=f"Screenshot captured ({'full page' if full_page else 'viewport'})",
            data={
                "image_base64": image_base64,
                "full_page": full_page,
                "url": page.url,
            },
        )


class AnalyzePageSkill(BaseSkill):
    """使用视觉模型分析当前页面"""

    name = "analyze_page"
    description = "使用多模态视觉模型分析当前页面，回答关于页面内容的问题"

    async def run(
        self,
        prompt: str,
        full_page: bool = False,
        model: Optional[str] = None,
    ) -> SkillResult:
        page = await self.get_page()

        # 创建适配器（不传 model 则从配置读取）
        adapter = self._create_adapter(model)
        if adapter is None:
            return SkillResult(
                success=False,
                message=f"Vision model not available. Please configure vision settings in config.yaml.",
            )

        vision = VisionSupport(adapter=adapter)
        result = await vision.analyze_page(page, prompt, full_page)

        if result.success:
            return SkillResult(
                success=True,
                message=f"Page analysis completed",
                data={
                    "description": result.description,
                    "url": page.url,
                    "prompt": prompt,
                },
            )
        else:
            return SkillResult(
                success=False,
                message=f"Page analysis failed: {result.error}",
                error=result.error,
            )

    def _create_adapter(self, model: Optional[str] = None) -> Optional[Any]:
        """创建视觉模型适配器"""
        try:
            # 从 manager 获取配置
            config = self._get_vision_config()
            provider = config.get("provider", "openai").lower()

            # 未指定 model 时，优先从配置读取，否则使用 provider 默认值
            if model is None:
                model = config.get("model") or (
                    "qwen-vl-max" if provider in ("dashscope", "aliyun", "qwen") else "gpt-4o"
                )

            # 根据 provider 选择适配器
            if provider == "dashscope" or provider == "aliyun" or provider == "qwen":
                logger.info("Using DashScope vision adapter with model=%s", model)
                return DashScopeVisionAdapter(model=model, config=config)
            else:
                # 默认使用 OpenAI 适配器
                return OpenAIVisionAdapter(model=model, config=config)
        except ImportError:
            logger.warning("openai package not installed, using dummy adapter")
            return DummyVisionAdapter()

    def _get_vision_config(self) -> dict:
        """从 manager 获取视觉模型配置（带回退：磁盘 config.yaml → 环境变量）"""
        # 第 1 级：从 manager 获取配置（原逻辑）
        try:
            if hasattr(self.manager, 'config') and self.manager.config:
                cfg = self.manager.config.get("vision", {})
                if cfg:
                    return cfg
        except Exception:
            pass

        # 第 2 级：直接从磁盘 config.yaml 读取（关键修复，多候选路径）
        try:
            import yaml
            from pathlib import Path
            candidates = []
            env_cfg = os.environ.get("BROWSER_AUTOMATION_SKILLS_CONFIG")
            if env_cfg:
                candidates.append(Path(env_cfg))
            _here = Path(__file__).resolve().parent
            for base in [_here, *_here.parents]:
                candidates.append(base / "config" / "config.yaml")
                candidates.append(base / "config.yaml")
            candidates.append(Path.cwd() / "config" / "config.yaml")
            candidates.append(Path.cwd() / "config.yaml")
            _seen = set()
            _unique = []
            for _p in candidates:
                if _p not in _seen:
                    _seen.add(_p)
                    _unique.append(_p)
            candidates = _unique
            for cfg_path in candidates:
                if not cfg_path.exists():
                    continue
                with cfg_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict) and data.get("vision"):
                    return data.get("vision", {})
        except Exception:
            pass

        # 第 3 级：从环境变量构建（最终兜底）
        env_cfg: dict = {}
        if os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            provider = "dashscope" if os.environ.get("DASHSCOPE_API_KEY") else "openai"
            env_cfg["provider"] = provider
            env_cfg["api_key"] = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
            if os.environ.get("OPENAI_BASE_URL"):
                env_cfg["base_url"] = os.environ["OPENAI_BASE_URL"]
            elif provider == "dashscope":
                env_cfg["base_url"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return env_cfg
