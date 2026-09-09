"""性能优化模块 - 提供缓存和批量操作优化"""

import asyncio
import hashlib
import urllib.parse as _urlparse
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from playwright.async_api import Page

from .base import BaseSkill, SkillResult

if TYPE_CHECKING:
    from .manager import SkillManager

logger = logging.getLogger(__name__)


# ============================================================
# 缓存基础设施
# ============================================================

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class LRUCache:
    """
    LRU (Least Recently Used) 缓存实现
    
    特性：
    - 固定最大容量
    - 自动淘汰最久未使用的条目
    - 支持 TTL 过期
    - 线程安全（异步安全）
    """

    def __init__(
        self,
        max_size: int = 100,
        default_ttl: float = 300.0,  # 5 分钟
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # 访问顺序记录
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired:
                await self._remove(key)
                return None
            
            # 更新访问记录
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._update_access_order(key)
            
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """设置缓存值"""
        async with self._lock:
            now = time.time()
            actual_ttl = ttl if ttl is not None else self.default_ttl
            
            if key in self._cache:
                # 更新现有条目
                self._cache[key].value = value
                self._cache[key].expires_at = now + actual_ttl
                self._cache[key].last_accessed = now
                self._update_access_order(key)
            else:
                # 检查是否需要淘汰
                if len(self._cache) >= self.max_size:
                    await self._evict()
                
                self._cache[key] = CacheEntry(
                    key=key,
                    value=value,
                    created_at=now,
                    expires_at=now + actual_ttl,
                    access_count=1,
                    last_accessed=now,
                )
                self._access_order.append(key)

    async def delete(self, key: str) -> bool:
        """删除缓存条目"""
        async with self._lock:
            return await self._remove(key)

    async def clear(self) -> int:
        """清空缓存"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            return count

    async def clear_by_prefix(self, prefix: str) -> int:
        """按键前缀清除缓存，返回被清除的条目数"""
        async with self._lock:
            keys_to_remove = [k for k in list(self._cache.keys()) if k.startswith(prefix)]
            for k in keys_to_remove:
                await self._remove(k)
            return len(keys_to_remove)

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        async with self._lock:
            now = time.time()
            expired = sum(1 for e in self._cache.values() if e.is_expired)
            total_accesses = sum(e.access_count for e in self._cache.values())
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "expired_entries": expired,
                "total_accesses": total_accesses,
                "hit_rate": self._calculate_hit_rate(),
            }

    async def cleanup_expired(self) -> int:
        """清理过期条目"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                await self._remove(key)
            return len(expired_keys)

    async def _remove(self, key: str) -> bool:
        """内部删除方法（需要在锁内调用）"""
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    async def _evict(self) -> None:
        """淘汰最久未使用的条目（需要在锁内调用）"""
        # 先清理过期的
        expired = [k for k, v in self._cache.items() if v.is_expired]
        if expired:
            for key in expired:
                await self._remove(key)
            return
        
        # 否则淘汰最久未访问的
        if self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]

    def _update_access_order(self, key: str) -> None:
        """更新访问顺序（需要在锁内调用）"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _calculate_hit_rate(self) -> float:
        """计算命中率（需要在锁内调用）"""
        if not self._access_order:
            return 0.0
        return len(self._access_order) / max(1, sum(
            e.access_count for e in self._cache.values()
        ))


# ============================================================
# DOM 快照缓存
# ============================================================

class DOMSnapshotCache:
    """
    DOM 快照缓存
    
    特性：
    - 基于 URL + 页面哈希的缓存键
    - 智能失效（页面导航时自动失效）
    - 可配置的 TTL
    """

    def __init__(
        self,
        max_size: int = 50,
        ttl: float = 60.0,  # DOM 快照默认 1 分钟
    ):
        self._cache = LRUCache(max_size=max_size, default_ttl=ttl)
        self._page_url_map: Dict[int, str] = {}  # page_id -> url

    async def _generate_cache_key(self, page: Page, max_elements: int = 100) -> str:
        """生成缓存键（带可读前缀，便于按页面失效）"""
        url = page.url or ""
        title = await page.title()
        url_s = _urlparse.quote_plus(url)
        title_s = _urlparse.quote_plus(title)
        # 使用可读前缀（dom_snapshot:...）+ 参数组合，便于按页面前缀清理
        return f"dom_snapshot:{url_s}:{title_s}:{max_elements}"

    async def get(self, page: Page, max_elements: int = 100) -> Optional[Any]:
        """获取缓存的 DOM 快照"""
        key = await self._generate_cache_key(page, max_elements)
        return await self._cache.get(key)

    async def set(self, page: Page, snapshot: Any, max_elements: int = 100, ttl: Optional[float] = None) -> None:
        """缓存 DOM 快照"""
        key = await self._generate_cache_key(page, max_elements)
        # 记录页面 -> URL 映射，便于页面失效时定位
        try:
            self._page_url_map[id(page)] = page.url or ""
        except Exception:
            # 保底：若 page 对象无法使用 id 或 url，则忽略映射
            pass
        await self._cache.set(key, snapshot, ttl=ttl)

    async def invalidate(self, page: Optional[Page] = None) -> int:
        """使指定页面或全部缓存失效"""
        if page is None:
            return await self._cache.clear()

        # 优先使用记录的 page->url 映射
        url = page.url or self._page_url_map.get(id(page), "")
        if not url:
            # 无法定位到 URL，则退化为清空所有缓存
            return await self._cache.clear()

        prefix = f"dom_snapshot:{_urlparse.quote_plus(url)}"
        return await self._cache.clear_by_prefix(prefix)

    async def clear_all(self) -> int:
        """清空所有 DOM 快照缓存"""
        return await self._cache.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return await self._cache.get_stats()


# ============================================================
# LLM 响应缓存
# ============================================================

class LLMResponseCache:
    """
    LLM 响应缓存
    
    特性：
    - 基于请求内容的哈希作为缓存键
    - 较长的 TTL（LLM 响应通常更稳定）
    - 支持批量预填充
    """

    def __init__(
        self,
        max_size: int = 200,
        ttl: float = 3600.0,  # 1 小时
    ):
        self._cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def _generate_cache_key(
        self,
        model: str,
        messages: List[Dict],
        temperature: float = 0.1,
    ) -> str:
        """生成 LLM 请求的缓存键"""
        key_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        key_str = str(key_data)
        return f"llm:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    async def get(
        self,
        model: str,
        messages: List[Dict],
        temperature: float = 0.1,
    ) -> Optional[str]:
        """获取缓存的 LLM 响应"""
        key = self._generate_cache_key(model, messages, temperature)
        return await self._cache.get(key)

    async def set(
        self,
        model: str,
        messages: List[Dict],
        response: str,
        temperature: float = 0.1,
        ttl: Optional[float] = None,
    ) -> None:
        """缓存 LLM 响应"""
        key = self._generate_cache_key(model, messages, temperature)
        await self._cache.set(key, response, ttl=ttl)

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return await self._cache.get_stats()

    async def clear_all(self) -> int:
        """清空所有 LLM 响应缓存"""
        return await self._cache.clear()


# ============================================================
# 批量操作优化
# ============================================================

@dataclass
class BatchOperationResult:
    """批量操作结果"""
    success_count: int = 0
    failure_count: int = 0
    results: List[SkillResult] = field(default_factory=list)
    total_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class BatchOperationOptimizer:
    """
    批量操作优化器
    
    特性：
    - 并发执行独立操作
    - 智能批处理（分组相关操作）
    - 错误隔离（单个失败不影响其他）
    """

    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency

    async def execute_batch(
        self,
        manager: "SkillManager",
        operations: List[Tuple[str, Dict]],
    ) -> BatchOperationResult:
        """
        批量执行操作
        
        Args:
            manager: SkillManager 实例
            operations: 操作列表 [(skill_name, params), ...]
        
        Returns:
            BatchOperationResult: 批量执行结果
        """
        start_time = time.time()
        results: List[SkillResult] = []
        errors: List[str] = []
        success_count = 0
        failure_count = 0

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def execute_single(skill_name: str, params: Dict) -> SkillResult:
            async with semaphore:
                try:
                    result = await manager.execute(skill_name, **params)
                    return result
                except Exception as e:
                    return SkillResult(
                        success=False,
                        message=f"Exception: {str(e)}",
                        error=str(e),
                    )

        # 并发执行所有操作
        tasks = [
            execute_single(skill_name, params)
            for skill_name, params in operations
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # 统计结果
        for result in results:
            if result.success:
                success_count += 1
            else:
                failure_count += 1
                if result.error:
                    errors.append(result.error)

        total_time = time.time() - start_time

        return BatchOperationResult(
            success_count=success_count,
            failure_count=failure_count,
            results=list(results),
            total_time=total_time,
            errors=errors,
        )

    async def execute_form_batch(
        self,
        manager: "SkillManager",
        fields: Dict[str, str],
        selector_type: str = "css",
    ) -> BatchOperationResult:
        """
        批量填写表单字段（优化版）
        
        使用 fill_form skill 一次性填写所有字段，而不是逐个填写
        """
        start_time = time.time()
        try:
            result = await manager.execute("fill_form", fields=fields, selector_type=selector_type)
            total_time = time.time() - start_time
            
            return BatchOperationResult(
                success_count=len(fields) if result.success else 0,
                failure_count=0 if result.success else len(fields),
                results=[result],
                total_time=total_time,
                errors=[result.message] if not result.success else [],
            )
        except Exception as e:
            total_time = time.time() - start_time
            return BatchOperationResult(
                success_count=0,
                failure_count=len(fields),
                results=[],
                total_time=total_time,
                errors=[str(e)],
            )


# ============================================================
# 性能监控
# ============================================================

class PerformanceMonitor:
    """
    性能监控器
    
    跟踪和报告各项性能指标
    """

    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}
        self._start_times: Dict[str, float] = {}

    def start_timer(self, operation: str) -> None:
        """开始计时"""
        self._start_times[operation] = time.time()

    def end_timer(self, operation: str) -> float:
        """结束计时并记录"""
        if operation in self._start_times:
            elapsed = time.time() - self._start_times[operation]
            self.record_metric(operation, elapsed)
            del self._start_times[operation]
            return elapsed
        return 0.0

    def record_metric(self, name: str, value: float) -> None:
        """记录性能指标"""
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)

    def get_stats(self, name: str) -> Dict[str, float]:
        """获取指标统计"""
        if name not in self._metrics:
            return {}
        
        values = self._metrics[name]
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "total": sum(values),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """获取所有指标统计"""
        return {
            name: self.get_stats(name)
            for name in self._metrics
        }

    def reset(self) -> None:
        """重置所有指标"""
        self._metrics.clear()
        self._start_times.clear()


# ============================================================
# Skills
# ============================================================

class GetCacheStatsSkill(BaseSkill):
    """获取缓存统计信息"""

    name = "get_cache_stats"
    description = "获取当前缓存状态和性能统计"

    async def run(self) -> SkillResult:
        # 获取全局缓存实例（从 manager 获取）
        dom_cache = getattr(self.manager, '_dom_cache', None)
        llm_cache = getattr(self.manager, '_llm_cache', None)
        perf_monitor = getattr(self.manager, '_perf_monitor', None)

        stats = {
            "dom_cache": await dom_cache.get_stats() if dom_cache else "Not initialized",
            "llm_cache": await llm_cache.get_stats() if llm_cache else "Not initialized",
            "performance": perf_monitor.get_all_stats() if perf_monitor else "Not initialized",
        }

        return SkillResult(
            success=True,
            message="Cache stats retrieved",
            data=stats,
        )


class ClearCacheSkill(BaseSkill):
    """清空缓存"""

    name = "clear_cache"
    description = "清空所有缓存"

    async def run(self, cache_type: str = "all") -> SkillResult:
        dom_cache = getattr(self.manager, '_dom_cache', None)
        llm_cache = getattr(self.manager, '_llm_cache', None)

        cleared = 0

        if cache_type in ("all", "dom"):
            if dom_cache:
                cleared += await dom_cache.clear_all()

        if cache_type in ("all", "llm"):
            if llm_cache:
                cleared += await llm_cache.clear_all()

        return SkillResult(
            success=True,
            message=f"Cleared {cleared} cache entries",
            data={"cleared_count": cleared, "cache_type": cache_type},
        )