"""SAM2 引擎单元测试。

验证：
1. 模型档位映射包含 4 个档位（base/large/base_lc/large_lc）
2. _resolve_checkpoint 在无权重时返回 (None, None)
3. _resolve_checkpoint 在有权重时返回正确路径和 cfg
4. auto_mask 在无权重时返回明确错误而非假遮罩
5. get_info 包含新档位信息
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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


class TestModelSizeParam:
    """模型档位现状：engine 重构后走 model_size 参数 + 权重目录扫描（非旧 4 档字典）。

    断言同步 2026-09-25：旧 _MODEL_CONFIGS 字典已随重构移除，
    现行契约是 auto_mask/segment_object/extract_foreground 的 model_size 参数（base/large）。
    """

    def test_public_methods_accept_model_size(self):
        import inspect

        from src.engines.sam2.engine import SAM2Engine

        for meth in ("auto_mask", "segment_object", "extract_foreground", "export_mask_sequence"):
            sig = inspect.signature(getattr(SAM2Engine, meth))
            assert "model_size" in sig.parameters, f"{meth} 缺 model_size 参数"

    def test_missing_weights_error_is_honest(self, sam2_engine_no_weights):
        """无权重失败结果必须明说拒绝推理，绝不假成功。"""
        result = sam2_engine_no_weights._missing_weights_error()
        assert result.success is False
        assert "拒绝推理" in result.error


class TestFindCheckpoint:
    """权重查找测试（引擎重构后 API：_find_checkpoint，无档位回退概念）。"""

    def test_no_weights_returns_none(self, sam2_engine_no_weights):
        """空目录应返回 None。"""
        assert sam2_engine_no_weights._find_checkpoint() is None

    def test_finds_pt_file(self, sam2_engine_with_fake_weights):
        engine, _ = sam2_engine_with_fake_weights
        found = engine._find_checkpoint()
        assert found is not None
        assert found.name == "sam2.1_hiera_base_plus.pt"

    def test_falls_back_to_pth_ckpt(self):
        """目录内只有 .pth/.ckpt 时也能发现（诚实：发现权重≠能推理，后续子进程会自检）。"""
        import tempfile as _tf

        from src.engines.sam2.engine import SAM2Engine

        with _tf.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "model.ckpt").write_bytes(b"x")
            engine = SAM2Engine(executable_path=Path("python"), model_dir=d)
            assert engine._find_checkpoint() is not None
            assert engine._find_checkpoint().suffix == ".ckpt"


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
    """get_info 方法测试（断言同步引擎重构后字段）。"""

    def test_get_info_contains_model_dir_fields(self, sam2_engine_no_weights):
        info = sam2_engine_no_weights.get_info()
        assert "model_dir" in info
        assert "model_dir_exists" in info
        assert "capabilities" in info
        assert "auto_mask" in info["capabilities"]

    def test_get_info_installed_flag(self, sam2_engine_no_weights):
        """installed 字段如实反映 sam2 包是否可导入（本机未装则必为 False）。"""
        info = sam2_engine_no_weights.get_info()
        assert info["installed"] is (sam2_engine_no_weights._sam2 is not None)
