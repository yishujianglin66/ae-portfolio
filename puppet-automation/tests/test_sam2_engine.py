"""SAM2 引擎单元测试。

验证：
1. 模型档位映射包含 4 个档位（base/large/base_lc/large_lc）
2. _resolve_checkpoint 在无权重时返回 (None, None)
3. _resolve_checkpoint 在有权重时返回正确路径和 cfg
4. auto_mask 在无权重时返回明确错误而非假遮罩
5. get_info 包含新档位信息
"""
from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def sam2_engine_no_weights():
    """创建一个无权重的 SAM2Engine 实例。"""
    from src.engines.sam2.engine import SAM2Engine

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SAM2Engine(
            executable_path=Path("python"),
            model_dir=Path(tmpdir),
        )
        yield engine


@pytest.fixture
def sam2_engine_with_fake_weights():
    """创建一个有假权重文件的 SAM2Engine 实例。"""
    from src.engines.sam2.engine import SAM2Engine

    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir)
        # 创建假权重文件
        (model_dir / "sam2.1_hiera_base_plus.pt").write_bytes(b"fake_weights")
        engine = SAM2Engine(
            executable_path=Path("python"),
            model_dir=model_dir,
        )
        yield engine, model_dir


class TestModelConfigs:
    """模型档位映射测试。"""

    def test_model_configs_has_four_tiers(self):
        """_MODEL_CONFIGS 应包含 4 个档位。"""
        from src.engines.sam2.engine import _MODEL_CONFIGS

        expected = {"base", "large", "small", "tiny"}
        assert set(_MODEL_CONFIGS.keys()) == expected

    def test_base_is_default_recommended(self):
        """base 应存在于配置中（8GB 显存最优平衡）。"""
        from src.engines.sam2.engine import _MODEL_CONFIGS

        assert "base" in _MODEL_CONFIGS
        assert "base_plus" in _MODEL_CONFIGS["base"]["checkpoint"]

    def test_each_config_has_checkpoint_and_cfg(self):
        """每个档位应有 checkpoint 和 model_cfg 字段。"""
        from src.engines.sam2.engine import _MODEL_CONFIGS

        for name, cfg in _MODEL_CONFIGS.items():
            assert "checkpoint" in cfg, f"{name} 缺少 checkpoint"
            assert "model_cfg" in cfg, f"{name} 缺少 model_cfg"


class TestResolveCheckpoint:
    """权重解析测试。"""

    def test_no_weights_returns_none(self, sam2_engine_no_weights):
        """无权重文件时应返回 (None, None)。"""
        checkpoint, cfg = sam2_engine_no_weights._resolve_checkpoint("base")
        assert checkpoint is None
        assert cfg is None  # 无权重时返回 (None, None)

    def test_exact_match(self, sam2_engine_with_fake_weights):
        """有权重时应返回正确路径。"""
        engine, model_dir = sam2_engine_with_fake_weights
        checkpoint, cfg = engine._resolve_checkpoint("base")
        assert checkpoint is not None
        assert checkpoint.name == "sam2.1_hiera_base_plus.pt"
        assert "sam2.1_hiera_b+" in cfg

    def test_fallback_to_any_pt(self, sam2_engine_with_fake_weights):
        """档位不匹配时回退到目录中任意 .pt 文件。"""
        engine, model_dir = sam2_engine_with_fake_weights
        checkpoint, cfg = engine._resolve_checkpoint("large")
        # 目录中只有 base_plus，large 精确匹配失败，应回退
        assert checkpoint is not None
        assert checkpoint.suffix == ".pt"


class TestAutoMaskNoWeights:
    """无权重时的 auto_mask 行为测试。"""

    @pytest.mark.asyncio
    async def test_auto_mask_returns_error_without_weights(self, sam2_engine_no_weights):
        """无权重时 auto_mask 应返回 success=False。"""
        import asyncio

        # 创建假视频文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake_video")
            video_path = f.name

        with tempfile.TemporaryDirectory() as outdir:
            result = await sam2_engine_no_weights.auto_mask(
                video_path=video_path,
                output_dir=outdir,
            )

        assert result.success is False
        assert "权重不可用" in result.error or "not installed" in result.error

    @pytest.mark.asyncio
    async def test_auto_mask_no_fake_masks(self, sam2_engine_no_weights):
        """无权重时绝不能生成假遮罩文件。"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake_video")
            video_path = f.name

        with tempfile.TemporaryDirectory() as outdir:
            result = await sam2_engine_no_weights.auto_mask(
                video_path=video_path,
                output_dir=outdir,
            )
            # 确保没有生成假遮罩
            out_path = Path(outdir)
            masks = list(out_path.glob("*.png"))
            assert len(masks) == 0, "无权重时不应生成任何遮罩文件"


class TestGetInfo:
    """get_info 方法测试。"""

    def test_get_info_contains_model_configs(self, sam2_engine_no_weights):
        """get_info 应包含 model_configs 字段。"""
        info = sam2_engine_no_weights.get_info()
        assert "model_configs" in info
        assert "base" in info["model_configs"]
        assert "large" in info["model_configs"]

    def test_get_info_contains_checkpoint_info(self, sam2_engine_with_fake_weights):
        """有权重时 get_info 应显示 checkpoint 路径。"""
        engine, _ = sam2_engine_with_fake_weights
        info = engine.get_info()
        assert info["checkpoint"] is not None
