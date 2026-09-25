"""SadTalker engine tests.

验证 SadTalkerEngine 引擎适配器的导入、实例化与端到端视频生成能力。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


class TestSadTalkerEngine:
    """Test SadTalkerEngine adapter."""

    def test_sadtalker_engine_init(self):
        """引擎能正确初始化。"""
        from src.engines.sadtalker import SadTalkerEngine

        engine = SadTalkerEngine()
        assert engine is not None
        assert engine.name == "sadtalker"
        assert hasattr(engine, "generate")
        assert hasattr(engine, "execute")

    def test_sadtalker_engine_info(self):
        """get_info 返回正确的引擎信息。"""
        from src.engines.sadtalker import SadTalkerEngine

        engine = SadTalkerEngine()
        info = engine.get_info()
        assert info["name"] == "sadtalker"
        assert "capabilities" in info
        assert "generate" in info["capabilities"]
        # script_exists 取决于本机是否安装 SadTalker（D:\AE-Work\sadtalker），
        # 断言字段存在而非硬编码布尔（测试环境无关性 2026-09-25）
        assert "script_exists" in info

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sadtalker_generate_e2e(self):
        """端到端测试：图片 + 音频 → 口型同步视频。"""
        from src.engines.sadtalker import SadTalkerEngine

        source_image = Path("D:/AE-Work/sadtalker/examples/source_image/full_body_1.png")
        driven_audio = Path("D:/AE-Work/sadtalker/examples/driven_audio/bus_chinese.wav")

        if not source_image.exists() or not driven_audio.exists():
            pytest.skip("SadTalker example assets not available")

        engine = SadTalkerEngine()
        result = await engine.generate(
            source_image=source_image,
            driven_audio=driven_audio,
            output_path=Path("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/sadtalker/sadtalker_engine_e2e.mp4"),
            preprocess="crop",
            size=256,
            timeout=300,
        )

        assert result.success is True
        assert result.output_path is not None
        assert Path(result.output_path).exists()
        assert result.duration_seconds > 0


if __name__ == "__main__":
    """直接运行端到端测试。"""

    async def _run_e2e():
        from src.engines.sadtalker import SadTalkerEngine

        engine = SadTalkerEngine()
        print("Engine info:", engine.get_info())

        result = await engine.generate(
            source_image=r"D:\AE-Work\sadtalker\examples\source_image\full_body_1.png",
            driven_audio=r"D:\AE-Work\sadtalker\examples\driven_audio\bus_chinese.wav",
            output_path=r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\sadtalker\sadtalker_engine_e2e.mp4",
            preprocess="crop",
            size=256,
            timeout=300,
        )

        print(f"Success: {result.success}")
        print(f"Output: {result.output_path}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        if result.error:
            print(f"Error: {result.error[:500]}")
        print(f"Metadata: {result.metadata}")

    asyncio.run(_run_e2e())
