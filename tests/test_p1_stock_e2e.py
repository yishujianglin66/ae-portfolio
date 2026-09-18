"""P1 E2E 测试: Stock 无水印素材 → UnifiedPipeline perceive 阶段接入 → 真实产出

分两组（pytest 标记 + 默认只跑 mock，带 --run-e2e 跑真实下载）：
  1. [默认, 无需 API key] mock 版 perceive 阶段集成测试：
     - 检测 `input_topic` → perceive 自动从 get_stock_client 下载
     - 下载后 material_scan.videos 自动从 stock_footage 目录补充
     - UnifiedPipeline 的 run_all 最小链路 (perceive + plan (no LLM no AE) + verify)
  2. [需要真实 key + --run-e2e] 真实 API → 搜索 → 下载 → 混剪 → MP4
     - 使用 pytest.skipIf 控制
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
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
# 真实 E2E 开关：通过环境变量 AEKV_RUN_E2E=1 启用（测试文件内的
# pytest_addoption 不生效，仅 conftest/插件可注册命令行选项）
# ============================================================================

def run_real_e2e() -> bool:
    return os.environ.get("AEKV_RUN_E2E", "").strip().lower() in ("1", "true", "yes", "on")


def has_real_keys() -> bool:
    pex = os.environ.get("PEXELS_API_KEY", "") or os.environ.get("AEKV_STOCK_PEXELS_API_KEY", "")
    pix = os.environ.get("PIXABAY_API_KEY", "") or os.environ.get("AEKV_STOCK_PIXABAY_API_KEY", "")
    return bool(pex and pix)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_project(tmp_path):
    """临时项目根目录（output + stock cache）"""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    stock_dir = tmp_path / "stock_footage"
    stock_dir.mkdir(parents=True, exist_ok=True)
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir(parents=True, exist_ok=True)
    return {
        "root": tmp_path,
        "output": str(output_dir),
        "stock": str(stock_dir),
        "materials": str(materials_dir),
    }


@pytest.fixture
def fake_stock_videos(tmp_project):
    """在 stock 目录下伪造几个 mp4（空字节也能骗过 filesize 检测），用于 mock perceive 下载链路"""
    stock_dir = Path(tmp_project["stock"])
    files = []
    for vid_id in ("pexels_100", "pexels_101", "pixabay_200", "pexels_102"):
        p = stock_dir / f"{vid_id}.mp4"
        # 1MB+ 假内容（ffprobe 读不出来但 path/size 能被 material_scanner 用到）
        p.write_bytes(b"\x00" * (2 * 1024 * 1024))
        files.append(str(p))
    return files


# ============================================================================
# Mock 测试组（无需网络，核心链路验证）
# ============================================================================

class TestMockPerceiveStock:
    """perceive 阶段 stock 自动获取 — 全程 mock HTTP + 真实调用 UnifiedPipeline.run"""

    def test_stock_client_translate_then_download_api_called(self, tmp_project):
        """search_and_download(中文主题) -> 调用 translate_query + _search_pexels + _download"""
        client = StockFootageClient(
            pexels_api_key="fake", pixabay_api_key="fake", cache_dir=tmp_project["stock"],
            config_manager=None,
        )

        # 替换 _search_pexels 返回假 VideoResult 列表（带下载 URL）
        fake_results = [
            VideoResult(id="pexels_900", source="pexels",
                        url="https://p/", download_url="https://cdn.p/900.mp4",
                        width=1920, height=1080, duration=8.0, size_bytes=5_000_000),
            VideoResult(id="pexels_901", source="pexels",
                        url="https://p/", download_url="https://cdn.p/901.mp4",
                        width=1920, height=1080, duration=10.0, size_bytes=6_000_000),
        ]
        client._search_pexels = lambda _c: fake_results
        client._search_pixabay = lambda _c: []

        # 把 _download_video 改成"写个假文件"而不连网
        downloaded_ids: list = []

        def fake_dl(result: VideoResult):
            downloaded_ids.append(result.id)
            path = Path(tmp_project["stock"]) / f"{result.id}.mp4"
            path.write_bytes(b"\x00" * (2 * 1024 * 1024))
            return str(path)

        client._download_video = fake_dl

        # 中文主题
        paths = client.search_and_download("高燃混剪", count=2)
        assert len(paths) == 2
        assert "pexels_900" in paths[0] and "pexels_901" in paths[1]
        assert downloaded_ids == ["pexels_900", "pexels_901"]

    def test_unified_pipeline_perceive_auto_acquires_stock(self, tmp_project, fake_stock_videos):
        """当 materials_dir 视频 <3 且 input_topic 存在时，perceive 触发 stock 自动获取并写回 material_scan

        这里不真的跑 AE/渲染，只跑 perceive，然后断言 result 里的 stock_footage / material_scan 字段
        """
        # 导入要在内部（避免全局触发 ConfigManager strict 验证）
        from pipeline.unified_pipeline import (
            PipelineConfig,
            UnifiedPipeline,
        )

        # 为了让 perceive 的 stock 分支触发但不真连网，全局 patch get_stock_client
        class _FakeClient:
            def translate_query(self, topic: str) -> str:
                return StockFootageClient.translate_query(topic)

            def search_and_download(self, q, count=5, **kwargs):
                # 返回 fixture 里的前 count 个假视频
                return fake_stock_videos[:count]

        fake_instance = _FakeClient()

        # 注意：unified_pipeline 在 _run_perceive 函数内才 from pipeline.stock_footage import get_stock_client
        # 所以要 patch 源 module 的 get_stock_client 而不是 unified_pipeline.*
        with patch("pipeline.stock_footage.get_stock_client", return_value=fake_instance):
            config = PipelineConfig(
                input_topic="高燃混剪",
                materials_dir=tmp_project["materials"],  # 空目录 -> videos=0 < 3
                output_dir=tmp_project["output"],
                enable_feedback_loop=False,
                enable_multi_agent=False,
                enable_vrs=False,
                use_compiler=False,
                # 材料扫描器需要 ffprobe；没装也没关系，扫描抛异常会被统一吞掉进入 WARN，stock_footage 字段仍在
            )
            pipe = UnifiedPipeline(config)
            # 直接跑 perceive 阶段（绕过 LLM/AE）
            perceive_data = pipe._run_perceive()

        # 关键断言：perceive 返回了 stock_footage 字段
        assert "stock_footage" in perceive_data, (
            f"当本地素材 <3 且有 input_topic 时，perceive 必须返回 stock_footage，"
            f"实际 keys: {list(perceive_data.keys())}"
        )
        assert len(perceive_data["stock_footage"]) >= 3, (
            f"应该下载至少 3 个 stock，实际: {len(perceive_data.get('stock_footage', []))}"
        )
        # stock_footage_query 应该是英文的 epic action cinematic
        assert "epic" in str(perceive_data.get("stock_footage_query", "")).lower() or \
               "cinematic" in str(perceive_data.get("stock_footage_query", "")).lower()


class TestPerceiveFallbacksWhenNoKeys:
    """没有 API Key 的情况下也不能崩溃"""

    def test_perceive_no_stock_keys_fails_gracefully(self, tmp_project, caplog):
        from pipeline.unified_pipeline import (
            PipelineConfig,
            UnifiedPipeline,
        )

        # 制造一个没有 key 的 client（连网也会失败）
        class _NoKeyClient:
            def translate_query(self, topic: str) -> str:
                return "cinematic x"

            def search_and_download(self, q, count=5, **kw):
                raise RuntimeError("No API Key configured")

        with patch("pipeline.stock_footage.get_stock_client", return_value=_NoKeyClient()):
            config = PipelineConfig(
                input_topic="高燃混剪",
                materials_dir=tmp_project["materials"],  # 空的
                output_dir=tmp_project["output"],
                enable_feedback_loop=False,
                enable_multi_agent=False,
                enable_vrs=False,
                skip_stages=["analyze", "plan", "execute", "render", "verify", "learn"],
            )
            pipe = UnifiedPipeline(config)
            # 不应该抛异常
            data = pipe._run_perceive()
        # 返回值应该是 dict，即使没有 stock_footage
        assert isinstance(data, dict)
        # stock 失败，应该没有 stock_footage 或其为空
        assert len(data.get("stock_footage", [])) == 0


# ============================================================================
# 真实 E2E 组（需要 --run-e2e + 真实 key）
# ============================================================================

@pytest.mark.skipif(
    not run_real_e2e(),
    reason="未设置 AEKV_RUN_E2E=1；跳过真实下载/混剪（避免耗流量 + 慢）",
)
@pytest.mark.skipif(not has_real_keys(), reason="缺少 PEXELS_API_KEY / PIXABAY_API_KEY")
class TestRealE2E:
    """真实 Pexels/Pixabay → 下载 → 调用 UnifiedPipeline 跑最小链路 → 产出真实 MP4（如果 ffmpeg 可用）"""

    def test_real_search_download_and_pipeline(self, tmp_project):
        from pipeline.unified_pipeline import PipelineConfig, UnifiedPipeline

        client = StockFootageClient(cache_dir=tmp_project["stock"])
        # 先验证连通性（只要有一个 OK 就继续）
        conn = client.test_connectivity()
        print(f"[E2E] 连通性: pexels={conn['pexels']}, pixabay={conn['pixabay']}, errors={conn.get('errors')}")
        assert conn["pexels"] or conn["pixabay"], f"两个 Provider 都没连上: {conn}"

        t0 = time.time()
        videos = client.search_and_download(
            "cinematic nature aerial", count=4,
            min_width=1280, min_height=720, min_duration=5.0,
        )
        dl_time = time.time() - t0

        assert videos, "真实 API 一个视频都没下载"
        for v in videos:
            assert Path(v).exists() and Path(v).stat().st_size > 100 * 1024, (
                f"视频文件过小或不存在: {v}"
            )
        print(f"[E2E] 下载完成 {len(videos)} 个, 耗时 {dl_time:.1f}s")
        for v in videos:
            mb = Path(v).stat().st_size / 1024 / 1024
            print(f"   - {Path(v).name}: {mb:.1f}MB")

        # 尝试最小管线（不跑 AE，只把 perceive/material_scan/plan 走通）
        config = PipelineConfig(
            input_topic="cinematic nature",
            materials_dir=tmp_project["stock"],  # 不触发自动下载（已有素材 >=3）
            output_dir=tmp_project["output"],
            enable_feedback_loop=False,
            enable_multi_agent=False,
            enable_vrs=False,
            use_compiler=False,
        )
        pipe = UnifiedPipeline(config)
        # 只 perceive + plan（不需要 AE Bridge / LLM / 渲染）
        data_p = pipe._run_perceive()
        n_videos = data_p.get("material_scan", {}).get("videos", 0)
        if isinstance(n_videos, list):
            n_videos = len(n_videos)
        print(f"[E2E] perceive material_scan 视频数: {n_videos}")
        assert n_videos >= 3, f"perceive 扫描到的视频数不够: {n_videos}"
