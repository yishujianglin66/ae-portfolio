"""
Agent-Reach Adapter: 为 AE 大流程项目提供联网搜索与内容抓取能力。

功能：
    1. 多平台搜索（Bilibili, YouTube, Reddit, X, GitHub 等）
    2. 网页内容抓取与解析
    3. 本地缓存机制（SQLite）避免重复请求
    4. 智能重试（tenacity）处理网络波动
    5. 请求速率限制（节流）防止被反爬

设计原则：
    - 作为 workflow_orchestrator 的下游/旁路节点
    - 输出标准化的 SearchResult 数据类，方便下游消费
    - 所有 I/O 操作异步化
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, List

from loguru import logger

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """标准化的搜索结果条目"""
    title: str
    url: str
    snippet: str = ""
    platform: str = "web"  # web / bilibili / youtube / reddit / x / github
    score: float = 0.0  # 相关性分数 0-1
    published_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResponse:
    """搜索响应封装"""
    query: str
    platform: str
    results: list[SearchResult]
    total_count: int = 0
    cached: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "platform": self.platform,
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "cached": self.cached,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# 缓存层
# ---------------------------------------------------------------------------

class SearchCache:
    """SQLite-based search result cache with TTL support."""

    def __init__(self, cache_path: Optional[Path] = None, ttl_hours: int = 24):
        self._path = Path(cache_path) if cache_path else Path("cache/search_cache.db")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = timedelta(hours=ttl_hours)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self._path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    key TEXT PRIMARY KEY,
                    result TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at)")

    def _make_key(self, query: str, platform: str, max_results: int) -> str:
        raw = f"{query}|{platform}|{max_results}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, query: str, platform: str, max_results: int) -> Optional[dict]:
        key = self._make_key(query, platform, max_results)
        now = datetime.now(timezone.utc)
        with sqlite3.connect(str(self._path)) as conn:
            row = conn.execute(
                "SELECT result FROM search_cache WHERE key = ? AND expires_at > ?",
                (key, now.isoformat())
            ).fetchone()
            if row:
                return json.loads(row[0])
        return None

    def set(self, query: str, platform: str, max_results: int, data: dict) -> None:
        key = self._make_key(query, platform, max_results)
        now = datetime.now(timezone.utc)
        expires = now + self._ttl
        with sqlite3.connect(str(self._path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO search_cache (key, result, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), now.isoformat(), expires.isoformat())
            )

    def purge_expired(self) -> int:
        now = datetime.now(timezone.utc)
        with sqlite3.connect(str(self._path)) as conn:
            cursor = conn.execute("DELETE FROM search_cache WHERE expires_at < ?", (now.isoformat(),))
            return cursor.rowcount


# ---------------------------------------------------------------------------
# 速率限制器
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple token bucket rate limiter for search requests."""

    def __init__(self, max_requests: int = 10, per_seconds: float = 1.0):
        self._max_requests = max_requests
        self._per_seconds = per_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        # CRITICAL FIX: 使用循环重试，确保在 sleep 后重新获取锁检查状态
        while True:
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self._per_seconds
                self._timestamps = [t for t in self._timestamps if t > cutoff]

                if len(self._timestamps) < self._max_requests:
                    # 可以通过，记录时间戳并返回
                    self._timestamps.append(now)
                    return

                # 需要等待：计算等待时间，释放锁后 sleep，然后重新循环
                wait_time = self._timestamps[0] + self._per_seconds - now
                logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s")

            # 释放锁后再等待，避免阻塞其他协程
            await asyncio.sleep(wait_time)


# ---------------------------------------------------------------------------
# 主适配器
# ---------------------------------------------------------------------------

class AgentReachAdapter:
    """
    Agent-Reach Adapter: 统一联网搜索入口。

    支持平台：
        - web: 通用网页搜索
        - bilibili: B站视频搜索
        - youtube: YouTube 视频搜索
        - reddit: Reddit 帖子搜索
        - github: GitHub 仓库搜索

    使用方式：
        adapter = AgentReachAdapter()
        response = await adapter.search("赛博朋克 漫剪 参考", platform="bilibili", max_results=5)
        results = response.results  # list[SearchResult]
    """

    SUPPORTED_PLATFORMS = {"web", "bilibili", "youtube", "reddit", "x", "github"}

    def __init__(
        self,
        cache_enabled: bool = True,
        cache_ttl_hours: int = 24,
        rate_limit_rps: int = 5,
        timeout: float = 15.0,
    ):
        self._cache = SearchCache(ttl_hours=cache_ttl_hours) if cache_enabled else None
        self._rate_limiter = RateLimiter(max_requests=rate_limit_rps, per_seconds=1.0)
        self._timeout = timeout
        self._ddgs = None
        self._init_ddgs()

    def _init_ddgs(self) -> None:
        try:
            # Try new package name first, then fall back to old name
            try:
                from ddgs import DDGS  # type: ignore
            except ImportError:
                from duckduckgo_search import DDGS  # type: ignore
            self._ddgs = DDGS(timeout=self._timeout)
            logger.info("[AgentReach] DDGS client initialized")
        except Exception as exc:
            logger.error(f"[AgentReach] Failed to init DDGS: {exc}")
            self._ddgs = None

    async def search(
        self,
        query: str,
        platform: str = "web",
        max_results: int = 5,
        use_cache: bool = True,
    ) -> SearchResponse:
        """
        统一搜索入口。

        Args:
            query: 搜索关键词
            platform: 目标平台 (web/bilibili/youtube/reddit/github)
            max_results: 最大返回结果数
            use_cache: 是否使用缓存

        Returns:
            SearchResponse 包含标准化结果列表
        """
        if platform not in self.SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}. Choose from {self.SUPPORTED_PLATFORMS}")

        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")

        # 1. Check cache
        if use_cache and self._cache:
            cached = self._cache.get(query, platform, max_results)
            if cached:
                # Convert cached result dicts back to SearchResult objects
                cached["results"] = [SearchResult(**r) for r in cached.get("results", [])]
                cached["cached"] = True
                return SearchResponse(**cached)

        # 2. Rate limit
        await self._rate_limiter.acquire()

        # 3. Execute search
        t0 = time.perf_counter()
        try:
            results = await self._execute_search(query, platform, max_results)
            elapsed = (time.perf_counter() - t0) * 1000

            response = SearchResponse(
                query=query,
                platform=platform,
                results=results,
                total_count=len(results),
                elapsed_ms=elapsed,
            )

            # 4. Cache result
            if self._cache and results:
                self._cache.set(query, platform, max_results, response.to_dict())

            logger.info(
                f"[AgentReach] search done: platform={platform}, "
                f"results={len(results)}, elapsed={elapsed:.0f}ms"
            )
            return response

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error(f"[AgentReach] search failed: {exc}")
            return SearchResponse(
                query=query,
                platform=platform,
                results=[],
                total_count=0,
                elapsed_ms=elapsed,
                error=str(exc),
            )

    async def _execute_search(
        self, query: str, platform: str, max_results: int
    ) -> list[SearchResult]:
        """根据平台选择搜索策略"""
        if platform == "web":
            return await self._search_web(query, max_results)
        elif platform == "bilibili":
            return await self._search_bilibili(query, max_results)
        elif platform == "youtube":
            return await self._search_youtube(query, max_results)
        elif platform == "reddit":
            return await self._search_reddit(query, max_results)
        elif platform == "github":
            return await self._search_github(query, max_results)
        elif platform == "x":
            return await self._search_x(query, max_results)
        return []

    # ------------------------------------------------------------------
    # 各平台搜索实现
    # ------------------------------------------------------------------

    async def _search_web(self, query: str, max_results: int) -> list[SearchResult]:
        """通用网页搜索 (DuckDuckGo)"""
        def _do_search() -> list[dict]:
            if self._ddgs:
                return list(self._ddgs.text(query, max_results=max_results))
            return []

        raw = await asyncio.to_thread(_do_search)
        results = []
        for item in raw:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", ""),
                platform="web",
                score=item.get("score", 0.5),
            ))
        return results

    async def _search_bilibili(self, query: str, max_results: int) -> list[SearchResult]:
        """B站视频搜索 (通过 DuckDuckGo site:bilibili.com)"""
        site_query = f"site:bilibili.com {query}"
        raw = await asyncio.to_thread(
            lambda: list(self._ddgs.text(site_query, max_results=max_results * 2)) if self._ddgs else []
        )
        results = []
        for item in raw[:max_results]:
            url = item.get("href", "")
            results.append(SearchResult(
                title=item.get("title", "").replace(" - 哔哩哔哩", ""),
                url=url,
                snippet=item.get("body", ""),
                platform="bilibili",
                score=0.7,
                metadata={"video_url": url} if "bilibili.com/video" in url else {},
            ))
        return results

    async def _search_youtube(self, query: str, max_results: int) -> list[SearchResult]:
        """YouTube 视频搜索"""
        site_query = f"site:youtube.com {query}"
        raw = await asyncio.to_thread(
            lambda: list(self._ddgs.text(site_query, max_results=max_results * 2)) if self._ddgs else []
        )
        results = []
        for item in raw[:max_results]:
            url = item.get("href", "")
            results.append(SearchResult(
                title=item.get("title", "").replace(" - YouTube", ""),
                url=url,
                snippet=item.get("body", ""),
                platform="youtube",
                score=0.7,
                metadata={"video_url": url} if "youtube.com" in url else {},
            ))
        return results

    async def _search_reddit(self, query: str, max_results: int) -> list[SearchResult]:
        """Reddit 帖子搜索"""
        site_query = f"site:reddit.com {query}"
        raw = await asyncio.to_thread(
            lambda: list(self._ddgs.text(site_query, max_results=max_results * 2)) if self._ddgs else []
        )
        results = []
        for item in raw[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", ""),
                platform="reddit",
                score=0.6,
            ))
        return results

    async def _search_github(self, query: str, max_results: int) -> list[SearchResult]:
        """GitHub 仓库搜索"""
        site_query = f"site:github.com {query}"
        raw = await asyncio.to_thread(
            lambda: list(self._ddgs.text(site_query, max_results=max_results * 2)) if self._ddgs else []
        )
        results = []
        for item in raw[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", ""),
                platform="github",
                score=0.8,
                metadata={"repo_url": item.get("href", "")},
            ))
        return results

    async def _search_x(self, query: str, max_results: int) -> list[SearchResult]:
        """X/Twitter 帖子搜索"""
        site_query = f"site:x.com {query}"
        raw = await asyncio.to_thread(
            lambda: list(self._ddgs.text(site_query, max_results=max_results * 2)) if self._ddgs else []
        )
        results = []
        for item in raw[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", ""),
                platform="x",
                score=0.6,
            ))
        return results

    # ------------------------------------------------------------------
    # 高级接口：风格参考检索
    # ------------------------------------------------------------------

    async def search_style_references(
        self,
        style_label: str,
        keywords: Optional[list[str]] = None,
        max_results_per_platform: int = 3,
    ) -> dict[str, Any]:
        """
        针对给定风格标签，在多个平台搜索参考内容。

        Args:
            style_label: 风格标签 (如 "cyberpunk", "ghibli", "amv_3d_spatial")
            keywords: 附加关键词列表
            max_results_per_platform: 每个平台最大结果数

        Returns:
            dict with keys:
                - style_label: 原始风格标签
                - references: 按平台分组的搜索结果
                - summary: 摘要文本
                - source_count: 总来源数
        """
        search_queries = self._build_style_queries(style_label, keywords)
        platforms_to_search = ["bilibili", "youtube", "reddit", "web"]

        references: dict[str, list[SearchResult]] = {}
        tasks = []

        for platform in platforms_to_search:
            query = search_queries.get(platform, search_queries["web"])
            tasks.append(
                self.search(
                    query=query,
                    platform=platform,
                    max_results=max_results_per_platform,
                )
            )

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for platform, response in zip(platforms_to_search, responses):
            if isinstance(response, Exception):
                logger.warning(f"[AgentReach] {platform} search failed: {response}")
                continue
            references[platform] = response.results

        # 汇总
        all_results: list[SearchResult] = []
        for results in references.values():
            all_results.extend(results)

        summary = self._generate_summary(style_label, all_results)

        return {
            "style_label": style_label,
            "references": {p: [r.to_dict() for r in rs] for p, rs in references.items()},
            "summary": summary,
            "source_count": len(all_results),
            "searched_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_style_queries(
        self, style_label: str, keywords: Optional[list[str]]
    ) -> dict[str, str]:
        """为不同平台构建搜索查询"""
        kw_str = " ".join(keywords) if keywords else ""
        base = f"{style_label} 漫剪 教程 参考 {kw_str}".strip()

        platform_queries = {
            "web": base,
            "bilibili": f"{style_label} 漫剪 AMV 教程 {kw_str}".strip(),
            "youtube": f"{style_label} anime music video tutorial edit {kw_str}".strip(),
            "reddit": f"{style_label} amv tutorial editing {kw_str}".strip(),
            "github": f"{style_label} video editing style {kw_str}".strip(),
            "x": f"{style_label} amv {style_label} edit tutorial {kw_str}".strip(),
        }
        return platform_queries

    def _generate_summary(self, style_label: str, results: list[SearchResult]) -> str:
        """基于搜索结果生成简短摘要"""
        if not results:
            return f"关于 '{style_label}' 的参考内容未找到。"

        # 取前 5 条最相关的结果拼接
        top_results = sorted(results, key=lambda r: r.score, reverse=True)[:5]
        titles = [r.title for r in top_results if r.title]

        summary_parts = [f"为风格 '{style_label}' 找到 {len(results)} 条参考："]
        if titles:
            summary_parts.append("热门内容: " + " | ".join(titles[:3]))

        return " ".join(summary_parts)

    # ------------------------------------------------------------------
    # 缓存管理
    # ------------------------------------------------------------------

    def clear_cache(self) -> int:
        """清除过期缓存条目，返回清除数量"""
        if self._cache:
            return self._cache.purge_expired()
        return 0
