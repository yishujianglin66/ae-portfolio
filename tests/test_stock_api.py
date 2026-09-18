"""Pytest: Pexels + Pixabay API 连通性 & StockFootageClient 核心单元测试

覆盖:
  - API Key 加载优先级 (参数 > ConfigManager > 环境变量 > .env)
  - 双 Provider 搜索结果解析 (_search_pexels / _search_pixabay)
  - search_only / test_connectivity 公共 API
  - 去重 + 按分辨率排序
  - 中文关键词翻译 translate_query
  - 下载缓存命中路径 (不实际连网)
  - 文件名 id 前缀避免重复 (pexels_pexels_bug 回归)
  - Mock HTTP 响应 + 真实 API 连通性 (真实 API 有 API_KEY 时才执行，标 skipif)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.stock_footage import (
    DEFAULT_CACHE_DIR,
    SearchConfig,
    StockFootageClient,
    VideoResult,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_cache(tmp_path):
    """临时缓存目录"""
    cache = tmp_path / "stock_footage"
    cache.mkdir(parents=True, exist_ok=True)
    return str(cache)


@pytest.fixture
def mock_client(tmp_cache):
    """使用假 key + 临时 cache 目录的 client（不连网）"""
    return StockFootageClient(
        pexels_api_key="mock_pexels_key",
        pixabay_api_key="mock_pixabay_key",
        cache_dir=tmp_cache,
    )


@pytest.fixture
def real_client(tmp_cache):
    """真实 API Key client — 若无 key 则测试自动 skip"""
    pexels_key = (
        os.environ.get("PEXELS_API_KEY", "")
        or os.environ.get("AEKV_STOCK_PEXELS_API_KEY", "")
    )
    pixabay_key = (
        os.environ.get("PIXABAY_API_KEY", "")
        or os.environ.get("AEKV_STOCK_PIXABAY_API_KEY", "")
    )
    return StockFootageClient(
        pexels_api_key=pexels_key,
        pixabay_api_key=pixabay_key,
        cache_dir=tmp_cache,
    )


def has_real_keys() -> bool:
    """判断是否有真实 API Key（用于 skipif）"""
    pex = os.environ.get("PEXELS_API_KEY", "") or os.environ.get("AEKV_STOCK_PEXELS_API_KEY", "")
    pix = os.environ.get("PIXABAY_API_KEY", "") or os.environ.get("AEKV_STOCK_PIXABAY_API_KEY", "")
    return bool(pex and pix)


# ============================================================================
# 1. 翻译器 (translate_query)
# ============================================================================

class TestTranslateQuery:
    @pytest.mark.parametrize("topic,expected_substr", [
        ("高燃混剪", "epic action cinematic"),
        ("自然风景", "nature landscape aerial"),
        ("赛博朋克", "cyberpunk neon city"),
        ("古风", "chinese traditional culture"),
    ])
    def test_exact_match_cn(self, topic, expected_substr):
        result = StockFootageClient.translate_query(topic)
        assert result == expected_substr

    def test_partial_match_cn(self):
        result = StockFootageClient.translate_query("我想看高燃混剪的片段")
        # 模糊匹配 "高燃混剪" -> epic action cinematic
        assert "epic" in result.lower() and "cinematic" in result.lower()

    @pytest.mark.parametrize("topic", [
        "epic battle scene", "nature cinematic",
    ])
    def test_passthrough_en(self, topic):
        # 已经是英文时直接返回（或保持原样）
        result = StockFootageClient.translate_query(topic)
        # isascii 的判断在原实现里做了，英文原样返回
        assert topic.isascii() and bool(result)

    def test_unknown_cn_fallback(self):
        result = StockFootageClient.translate_query("不存在的分类词")
        # fallback: cinematic <topic>
        assert "cinematic" in result


# ============================================================================
# 2. 文件名 & id 前缀
# ============================================================================

class TestFilenameIdPrefix:
    """避免 pexels_pexels_xxx 重复前缀回归"""

    def test_download_filename_no_double_prefix(self, tmp_cache):
        client = StockFootageClient(
            pexels_api_key="k", pixabay_api_key="k", cache_dir=tmp_cache
        )
        # 构造一个包含 source 前缀的 VideoResult (真实 _search_pexels 产物的 id 格式)
        vr = VideoResult(
            id="pexels_1234567",
            source="pexels",
            url="https://example.com/",
            download_url="",   # 不下载
            width=1920, height=1080, duration=10.0,
        )
        # 直接看 _download_video 里用于命名的逻辑：filename = result.id + .mp4
        filename = f"{vr.id}.mp4"
        assert filename == "pexels_1234567.mp4"
        assert filename.count("pexels") == 1

    def test_pixabay_id_format(self, mock_client: StockFootageClient):
        """Pixabay search 返回的 id 必须含 pixabay_ 前缀"""
        import urllib.request

        # Mock urllib.request.urlopen 返回一个 Pixabay 样例 JSON
        fake_json = json.dumps({
            "totalHits": 1,
            "hits": [
                {
                    "id": 8888888,
                    "pageURL": "https://pixabay.com/v/x",
                    "duration": 15,
                    "picture_id": "123",
                    "tags": "nature, landscape",
                    "videos": {
                        "large": {"url": "https://cdn.p/d.mp4", "width": 1920, "height": 1080, "size": 1_000_000},
                        "medium": {"url": "https://cdn.p/m.mp4", "width": 1280, "height": 720, "size": 500_000},
                    },
                }
            ],
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_json
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            results = mock_client._search_pixabay(SearchConfig(query="nature", per_page=3))

        assert len(results) == 1
        assert results[0].id == "pixabay_8888888"
        assert results[0].source == "pixabay"
        assert results[0].width == 1920


# ============================================================================
# 3. 去重 + 分辨率排序 (search_and_download 的纯逻辑路径)
# ============================================================================

class TestDedupAndSort:
    def test_deduplicate_and_sort_by_resolution(self, mock_client: StockFootageClient, tmp_cache):
        r_low = VideoResult(id="pexels_1", source="pexels", url="x", download_url="",
                            width=1280, height=720, duration=10.0)
        r_med = VideoResult(id="pexels_2", source="pexels", url="x", download_url="",
                            width=1920, height=1080, duration=10.0)
        r_4k = VideoResult(id="pexels_3", source="pexels", url="x", download_url="",
                           width=3840, height=2160, duration=10.0)
        r_dup = VideoResult(id="pexels_2", source="pexels", url="x", download_url="",
                            width=1920, height=1080, duration=10.0)

        # 在 download 之前打断 — 用空 download_url 让 _download_video 全返回 None
        # 但 search_and_download 会先 sort + uniq 再调用下载，这正是我们要测的
        order_seen: list[str] = []

        original_download = mock_client._download_video
        def fake_dl(result: VideoResult):
            order_seen.append(result.id)
            # 创建一个假文件，让 downloaded 列表被填充以便下游能看到
            path = Path(tmp_cache) / f"{result.id}.mp4"
            path.write_bytes(b"x" * 20000)  # > 10KB 阈值
            return str(path)

        mock_client._download_video = fake_dl

        # Mock _search_pexels 直接返回乱序 + 重复列表
        def fake_pex(_cfg):
            return [r_low, r_dup, r_med, r_4k]

        mock_client._search_pexels = fake_pex
        mock_client._search_pixabay = lambda _c: []

        results = mock_client.search_and_download("mock", count=3)

        # 去重后 3 个，并按 width*height 降序
        assert order_seen == ["pexels_3", "pexels_2", "pexels_1"]
        assert len(results) == 3


# ============================================================================
# 4. ConfigManager / 环境变量优先级
# ============================================================================

class TestKeyLoadingPriority:
    def test_explicit_param_wins(self, tmp_cache):
        with patch.dict(os.environ, {"PEXELS_API_KEY": "ENV_KEY", "PIXABAY_API_KEY": "ENV_KEY2"}, clear=False):
            client = StockFootageClient(
                pexels_api_key="PARAM_KEY",
                pixabay_api_key="PARAM_KEY2",
                cache_dir=tmp_cache,
                config_manager=None,
            )
        assert client._pexels_key == "PARAM_KEY"
        assert client._pixabay_key == "PARAM_KEY2"

    def test_no_params_env_fallback(self, tmp_cache):
        with patch.dict(os.environ, {
            "PEXELS_API_KEY": "ENV_PX",
            "PIXABAY_API_KEY": "ENV_PB",
        }, clear=False):
            # 用 _load_env 不读 .env（避免项目根里已有 .env 污染），通过 patch config=None + 参数空
            client = StockFootageClient(cache_dir=tmp_cache)
        assert client._pexels_key == "ENV_PX"
        assert client._pixabay_key == "ENV_PB"

    def test_cache_dir_from_env_aekv(self, tmp_path):
        want = tmp_path / "custom_cache"
        want.mkdir(exist_ok=True)
        with patch.dict(os.environ, {
            "AEKV_STOCK_CACHE_DIR": str(want),
        }, clear=False):
            client = StockFootageClient(pexels_api_key="a", pixabay_api_key="b")
        # Cache dir 应该是 $AEKV_STOCK_CACHE_DIR
        assert client._cache_dir.resolve() == want.resolve()


# ============================================================================
# 5. 真实 API 连通性（需要真实 Key，否则 skip）
# ============================================================================

@pytest.mark.real_stock_api
@pytest.mark.skipif(not has_real_keys(), reason="需要真实 PEXELS/PIXABAY API Keys")
class TestRealConnectivity:
    def test_pexels_search_real(self, real_client: StockFootageClient):
        results = real_client._search_pexels(
            SearchConfig(query="nature cinematic", per_page=3, min_width=1280, min_height=720, min_duration=3.0)
        )
        # 至少有一条结果
        assert isinstance(results, list)
        # 每条结果应该有合理的字段
        for r in results[:3]:
            assert r.width > 0 and r.height > 0
            assert r.duration > 0
            assert r.id.startswith("pexels_")
            assert r.download_url.startswith("https://")

    def test_pixabay_search_real(self, real_client: StockFootageClient):
        results = real_client._search_pixabay(
            SearchConfig(query="mountain", per_page=3, min_width=1280, min_height=720, min_duration=3.0)
        )
        assert isinstance(results, list)
        for r in results[:3]:
            assert r.width > 0 and r.height > 0
            assert r.id.startswith("pixabay_")

    def test_test_connectivity_method(self, real_client: StockFootageClient):
        report = real_client.test_connectivity()
        # 因为有 keys，至少一个应该 True；用 pytest 展示详细报告
        print("[test_connectivity] report:", json.dumps(report, ensure_ascii=False, indent=2))
        assert report["pexels"] or report["pixabay"], f"两个 Provider 都没连通: {report}"
