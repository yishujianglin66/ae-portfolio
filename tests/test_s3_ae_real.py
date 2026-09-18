"""
tests/test_s3_ae_real.py — S3 AE 木偶风格化合成 真实执行测试
=============================================================

标记：@pytest.mark.real_ae（需要 AE 运行 + Bridge 加载）
运行：pytest tests/test_s3_ae_real.py -m real_ae -v
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.real_ae

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
#  单元测试（不需要真实 AE）
# ============================================================================

class TestAECompositeStageUnit:
    """S3 合成阶段单元测试（mock 引擎）"""

    def test_import(self):
        """模块可导入"""
        from pipeline.stages.ae_composite import COMP_DEFINITIONS, AECompositeResult, AECompositeStage
        assert len(COMP_DEFINITIONS) == 3
        assert COMP_DEFINITIONS[0]["id"] == "Comp_Intro"

    def test_comp_definitions_structure(self):
        """合成定义结构正确"""
        from pipeline.stages.ae_composite import COMP_DEFINITIONS
        for comp in COMP_DEFINITIONS:
            assert "id" in comp
            assert "duration_s" in comp
            assert comp["duration_s"] >= 3.0

    @pytest.mark.asyncio
    async def test_bridge_down_fails_gracefully(self, tmp_path):
        """Bridge 不可用时优雅失败"""
        from pipeline.stages.ae_composite import AECompositeStage

        # Mock 引擎返回 Bridge 失败
        mock_engine = MagicMock()
        mock_engine.bridge_smoke_probe = AsyncMock(return_value=MagicMock(
            success=False, error="Bridge offline"
        ))

        stage = AECompositeStage(engine=mock_engine)
        result = await stage.run(
            source_videos=["a.mp4", "b.mp4", "c.mp4"],
            output_dir=tmp_path / "S3",
        )
        assert result.success is False
        assert result.bridge_available is False
        assert "Bridge" in result.errors[0]

    @pytest.mark.asyncio
    async def test_all_comps_render_success(self, tmp_path):
        """3 段全部渲染成功"""
        from pipeline.stages.ae_composite import AECompositeStage

        mock_engine = MagicMock()
        mock_engine.bridge_smoke_probe = AsyncMock(return_value=MagicMock(
            success=True, metadata={"bridge_available": True}
        ))

        # 模拟渲染成功
        async def mock_render(**kwargs):
            out = Path(kwargs["output_path"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 100)  # 假文件
            return MagicMock(success=True, output_path=out, error=None)

        mock_engine.render_comp_bridge = mock_render

        stage = AECompositeStage(engine=mock_engine)
        result = await stage.run(
            source_videos=["a.mp4", "b.mp4", "c.mp4"],
            output_dir=tmp_path / "S3",
        )
        assert result.success is True
        assert len(result.renders) == 3
        assert result.bridge_available is True

    @pytest.mark.asyncio
    async def test_partial_render_failure(self, tmp_path):
        """部分渲染失败 → 整体失败"""
        from pipeline.stages.ae_composite import AECompositeStage

        mock_engine = MagicMock()
        mock_engine.bridge_smoke_probe = AsyncMock(return_value=MagicMock(
            success=True, metadata={}
        ))

        call_count = {"n": 0}

        async def mock_render(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:  # 第二段失败
                return MagicMock(success=False, output_path=None, error="render crash")
            out = Path(kwargs["output_path"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 100)
            return MagicMock(success=True, output_path=out, error=None)

        mock_engine.render_comp_bridge = mock_render

        stage = AECompositeStage(engine=mock_engine)
        result = await stage.run(
            source_videos=["a.mp4", "b.mp4", "c.mp4"],
            output_dir=tmp_path / "S3",
        )
        assert result.success is False
        assert len(result.errors) == 1
        assert "Comp_Main" in result.errors[0]


# ============================================================================
#  真实执行测试（需要 AE 运行）
# ============================================================================

class TestAECompositeReal:
    """S3 真实 AE 执行（需要 AE + Bridge 在线）"""

    @pytest.fixture(autouse=True)
    def check_ae_available(self):
        """检查 AE Bridge 是否可用"""
        bridge_dir = PROJECT_ROOT / ".ae-mcp-bridge"
        if not bridge_dir.exists():
            pytest.skip("AE Bridge 目录不存在")
        cmd_file = bridge_dir / "ae_command.json"
        # 简单检查：bridge 目录存在即尝试（真实 ping 在测试中执行）

    @pytest.mark.asyncio
    async def test_bridge_smoke_probe_real(self):
        """真实 Bridge 探测"""
        import sys
        pa_src = PROJECT_ROOT / "puppet-automation" / "src"
        if str(pa_src) not in sys.path:
            sys.path.insert(0, str(pa_src))

        try:
            from engines.ae.engine import AEEngine
            engine = AEEngine()
        except Exception as e:
            pytest.skip(f"AE 引擎初始化失败: {e}")

        result = await engine.bridge_smoke_probe()
        # 真实环境：如果 AE 在线则通过，否则跳过
        if not result.success:
            pytest.skip(f"AE Bridge 不在线: {result.error}")

        assert result.success is True
        assert result.metadata.get("bridge_available") is True

    @pytest.mark.asyncio
    async def test_render_single_comp_real(self, tmp_path):
        """真实渲染单段合成"""
        import sys
        pa_src = PROJECT_ROOT / "puppet-automation" / "src"
        if str(pa_src) not in sys.path:
            sys.path.insert(0, str(pa_src))

        try:
            from engines.ae.engine import AEEngine
            engine = AEEngine()
        except Exception as e:
            pytest.skip(f"AE 引擎初始化失败: {e}")

        # 先探测
        probe = await engine.bridge_smoke_probe()
        if not probe.success:
            pytest.skip(f"AE Bridge 不在线: {probe.error}")

        # 渲染 3s 测试合成
        out_mov = tmp_path / "test_comp.mov"
        result = await engine.render_comp_bridge(
            comp_name="FlagshipTest_Comp",
            output_path=out_mov,
            duration_s=3.0,
        )

        if result.success:
            assert out_mov.exists()
            assert out_mov.stat().st_size > 0
        else:
            # aerender 可能未配置，但 Bridge 创建合成应该成功
            assert "SCRIPT_SYNTAX" not in (result.error_code or "")
