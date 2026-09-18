"""ColorGradeArtifact 跨软件互通测试

测试 Resolve / FFmpeg / AE 三端之间的调色描述互通：
- Resolve -> Artifact -> FFmpeg
- Resolve -> Artifact -> AE (JSX)
- AE -> Artifact -> FFmpeg
- AE -> Artifact -> Resolve
- Artifact 序列化/反序列化
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import (
    FFMPEG_COLOR_PRESETS,
    RESOLVE_PRESETS,
    ColorGradeArtifact,
    ColorGradeConfig,
    ColorWheelParams,
    ResolveColorEngine,
)


class TestColorGradeArtifactBasics:
    """Artifact 基础功能测试"""

    def test_artifact_create_default(self):
        """创建默认 Artifact"""
        artifact = ColorGradeArtifact()
        assert artifact.version == "1.0"
        assert artifact.preset_name == ""
        assert artifact.source == "auto"
        assert artifact.nodes == []
        assert artifact.ffmpeg_filter == ""
        assert isinstance(artifact.metadata, dict)

    def test_artifact_to_dict_roundtrip(self):
        """to_dict / from_dict 往返一致"""
        artifact = ColorGradeArtifact(
            preset_name="cinematic",
            source="resolve",
            nodes=[{"node_type": "primary", "name": "test", "settings": {"saturation": 1.2}}],
            ffmpeg_filter="eq=saturation=1.2",
            metadata={"test": True},
        )
        d = artifact.to_dict()
        restored = ColorGradeArtifact.from_dict(d)
        assert restored.preset_name == artifact.preset_name
        assert restored.source == artifact.source
        assert restored.nodes == artifact.nodes
        assert restored.ffmpeg_filter == artifact.ffmpeg_filter
        assert restored.metadata["test"] == True

    def test_artifact_json_roundtrip(self):
        """JSON 序列化/反序列化"""
        artifact = ColorGradeArtifact(
            preset_name="warm_vintage",
            source="ffmpeg",
            nodes=[{"node_type": "primary", "name": "test", "settings": {"contrast": 1.1}}],
        )
        json_str = artifact.to_json()
        data = json.loads(json_str)
        restored = ColorGradeArtifact.from_dict(data)
        assert restored.preset_name == "warm_vintage"
        assert restored.source == "ffmpeg"
        assert len(restored.nodes) == 1

    def test_artifact_save_load(self, tmp_path):
        """保存到文件 / 从文件加载"""
        artifact = ColorGradeArtifact(preset_name="cool_teal", source="resolve")
        path = str(tmp_path / "test_artifact.json")
        artifact.save(path)
        assert Path(path).exists()
        loaded = ColorGradeArtifact.load(path)
        assert loaded.preset_name == "cool_teal"
        assert loaded.source == "resolve"


class TestResolveToArtifact:
    """Resolve 预设 -> Artifact"""

    def setup_method(self):
        self.engine = ResolveColorEngine()

    def test_build_artifact_from_resolve_preset(self):
        """从 Resolve 预设生成 Artifact"""
        artifact = self.engine.build_artifact("cinematic", source="resolve")
        assert artifact.preset_name == "cinematic"
        assert artifact.source == "resolve"
        assert len(artifact.nodes) > 0
        assert artifact.nodes[0]["node_type"] == "primary"
        assert "saturation" in artifact.nodes[0]["settings"]
        assert "contrast" in artifact.nodes[0]["settings"]

    def test_build_artifact_all_resolve_presets(self):
        """所有 RESOLVE_PRESETS 都能生成 Artifact"""
        for preset_name in RESOLVE_PRESETS:
            artifact = self.engine.build_artifact(preset_name)
            assert artifact is not None
            assert artifact.preset_name == preset_name

    def test_build_artifact_from_ffmpeg_preset(self):
        """从 FFmpeg 预设生成 Artifact"""
        artifact = self.engine.build_artifact("warm", source="ffmpeg")
        assert artifact.preset_name == "warm"
        assert artifact.ffmpeg_filter != ""
        assert "eq=" in artifact.ffmpeg_filter

    def test_build_artifact_unknown_preset(self):
        """未知预设生成空 Artifact"""
        artifact = self.engine.build_artifact("nonexistent_preset")
        assert artifact.preset_name == "nonexistent_preset"
        assert artifact.nodes == []
        assert artifact.ffmpeg_filter == ""


class TestArtifactToFFmpeg:
    """Artifact -> FFmpeg 滤镜"""

    def setup_method(self):
        self.engine = ResolveColorEngine()

    def test_artifact_with_direct_ffmpeg_filter(self):
        """Artifact 直接包含 ffmpeg_filter 时直接使用"""
        artifact = ColorGradeArtifact(
            preset_name="test",
            ffmpeg_filter="eq=saturation=1.5:contrast=1.2",
        )
        result = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert result == "eq=saturation=1.5:contrast=1.2"

    def test_artifact_from_resolve_preset_to_ffmpeg(self):
        """Resolve 预设 Artifact 可转为 FFmpeg 滤镜"""
        artifact = self.engine.build_artifact("cinematic")
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert ffmpeg_filter is not None
        assert len(ffmpeg_filter) > 0
        assert "eq=" in ffmpeg_filter or "colorbalance=" in ffmpeg_filter

    def test_artifact_primary_node_saturation(self):
        """primary 节点 saturation 正确映射到 FFmpeg"""
        artifact = ColorGradeArtifact(
            preset_name="test_sat",
            nodes=[{
                "node_type": "primary",
                "name": "Test",
                "enabled": True,
                "settings": {"saturation": 1.5},
            }],
        )
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert "saturation=1.500" in ffmpeg_filter

    def test_artifact_primary_node_contrast(self):
        """primary 节点 contrast 正确映射到 FFmpeg"""
        artifact = ColorGradeArtifact(
            preset_name="test_contrast",
            nodes=[{
                "node_type": "primary",
                "name": "Test",
                "enabled": True,
                "settings": {"contrast": 1.3},
            }],
        )
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert "contrast=1.300" in ffmpeg_filter

    def test_artifact_disabled_node_skipped(self):
        """禁用节点应被跳过"""
        artifact = ColorGradeArtifact(
            preset_name="test_disabled",
            nodes=[{
                "node_type": "primary",
                "name": "Disabled",
                "enabled": False,
                "settings": {"saturation": 1.5},
            }],
        )
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        # 禁用节点应不生成滤镜，回退到 natural 预设
        assert ffmpeg_filter == FFMPEG_COLOR_PRESETS["natural"]["ffmpeg_filter"]

    def test_artifact_ffmpeg_node_type(self):
        """ffmpeg 类型节点正确处理"""
        artifact = ColorGradeArtifact(
            preset_name="test_ffmpeg_node",
            nodes=[{
                "node_type": "ffmpeg",
                "name": "warm",
                "enabled": True,
                "settings": {"saturation": 1.1, "contrast": 1.05, "brightness": 0.02},
            }],
        )
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert "saturation=1.100" in ffmpeg_filter
        assert "contrast=1.050" in ffmpeg_filter
        assert "brightness=0.020" in ffmpeg_filter

    def test_empty_artifact_fallback_to_natural(self):
        """空 Artifact 回退到 natural 预设"""
        artifact = ColorGradeArtifact()
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert ffmpeg_filter == FFMPEG_COLOR_PRESETS["natural"]["ffmpeg_filter"]

    def test_artifact_color_wheel_to_colorbalance(self):
        """色轮参数正确映射到 colorbalance 滤镜"""
        artifact = ColorGradeArtifact(
            preset_name="test_colorwheel",
            nodes=[{
                "node_type": "primary",
                "name": "Test",
                "enabled": True,
                "settings": {
                    "lift": [1.1, 0.9, 1.0, 0.0],
                    "gamma": [1.0, 1.0, 1.0, 0.0],
                    "gain": [0.95, 1.0, 1.05, 0.0],
                },
            }],
        )
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert "colorbalance=" in ffmpeg_filter
        assert "rs=" in ffmpeg_filter
        assert "bs=" in ffmpeg_filter
        assert "rh=" in ffmpeg_filter


class TestArtifactToAE:
    """Artifact -> AE ExtendScript"""

    def setup_method(self):
        self.engine = ResolveColorEngine()

    def test_artifact_to_ae_jsx_basic(self):
        """基础 Artifact 生成 AE JSX"""
        artifact = self.engine.build_artifact("cinematic")
        jsx = self.engine.artifact_to_ae_jsx(artifact)
        assert jsx is not None
        assert len(jsx) > 0
        assert "var comp = app.project.activeItem;" in jsx
        assert "adjLayer.adjustmentLayer = true;" in jsx

    def test_artifact_to_ae_jsx_with_layer_name(self):
        """自定义调整层名称"""
        artifact = ColorGradeArtifact(preset_name="test")
        jsx = self.engine.artifact_to_ae_jsx(artifact, layer_name="My Grade")
        assert "My Grade" in jsx

    def test_artifact_to_ae_jsx_brightness_contrast(self):
        """亮度对比度正确生成 BC 效果"""
        artifact = ColorGradeArtifact(
            preset_name="test_bc",
            nodes=[{
                "node_type": "primary",
                "name": "TestBC",
                "enabled": True,
                "settings": {
                    "gain": [1.0, 1.0, 1.0, 0.1],
                    "contrast": 1.2,
                },
            }],
        )
        jsx = self.engine.artifact_to_ae_jsx(artifact)
        assert "ADBE Brightness & Contrast" in jsx
        assert "TestBC - BC" in jsx

    def test_artifact_to_ae_jsx_hue_saturation(self):
        """饱和度正确生成 HS 效果"""
        artifact = ColorGradeArtifact(
            preset_name="test_hs",
            nodes=[{
                "node_type": "primary",
                "name": "TestHS",
                "enabled": True,
                "settings": {"saturation": 1.3},
            }],
        )
        jsx = self.engine.artifact_to_ae_jsx(artifact)
        assert "ADBE Hue Saturation" in jsx
        assert "TestHS - HS" in jsx

    def test_artifact_to_ae_jsx_color_balance(self):
        """色轮正确生成 Color Balance 效果"""
        artifact = ColorGradeArtifact(
            preset_name="test_cb",
            nodes=[{
                "node_type": "primary",
                "name": "TestCB",
                "enabled": True,
                "settings": {
                    "lift": [1.2, 0.8, 1.0, 0.0],
                    "gamma": [1.0, 1.0, 1.0, 0.0],
                    "gain": [0.9, 1.0, 1.1, 0.0],
                },
            }],
        )
        jsx = self.engine.artifact_to_ae_jsx(artifact)
        assert "ADBE Color Balance" in jsx
        assert "TestCB - CB" in jsx
        assert "ADBE Color Balance-0001" in jsx
        assert "ADBE Color Balance-0002" in jsx
        assert "ADBE Color Balance-0003" in jsx

    def test_artifact_to_ae_jsx_save_to_file(self, tmp_path):
        """JSX 保存到文件"""
        artifact = self.engine.build_artifact("cinematic")
        output_path = str(tmp_path / "grade.jsx")
        jsx = self.engine.artifact_to_ae_jsx(artifact, output_path=output_path)
        assert Path(output_path).exists()
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == jsx

    def test_artifact_to_ae_jsx_special_chars_layer_name(self):
        """层名称包含特殊字符时正确转义"""
        artifact = ColorGradeArtifact(preset_name="test")
        jsx = self.engine.artifact_to_ae_jsx(artifact, layer_name='Test "Quote" Layer')
        assert '\\"' in jsx


class TestAEToArtifact:
    """AE 效果 -> Artifact"""

    def setup_method(self):
        self.engine = ResolveColorEngine()

    def test_build_artifact_from_ae_empty(self):
        """空 AE 效果列表生成基础 Artifact"""
        artifact = self.engine.build_artifact_from_ae([])
        assert artifact.source == "after_effects"
        assert artifact.preset_name == "from_ae"
        assert len(artifact.nodes) == 1
        assert artifact.nodes[0]["node_type"] == "primary"

    def test_build_artifact_from_ae_brightness_contrast(self):
        """AE Brightness & Contrast 效果正确映射"""
        ae_effects = [
            {
                "matchName": "ADBE Brightness & Contrast",
                "name": "Brightness & Contrast",
                "properties": {
                    "ADBE Brightness-Contrast-1": 10.0,
                    "ADBE Brightness-Contrast-2": 20.0,
                },
            }
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects, preset_name="bc_test")
        assert artifact.preset_name == "bc_test"
        settings = artifact.nodes[0]["settings"]
        assert settings["contrast"] == pytest.approx(1.2, rel=1e-3)
        assert settings["gain"][3] == pytest.approx(0.1, rel=1e-3)
        assert "brightness=0.100" in artifact.ffmpeg_filter
        assert "contrast=1.200" in artifact.ffmpeg_filter

    def test_build_artifact_from_ae_hue_saturation(self):
        """AE Hue/Saturation 效果正确映射"""
        ae_effects = [
            {
                "matchName": "ADBE Hue Saturation",
                "name": "Hue/Saturation",
                "properties": {"ADBE HSL-2": 30.0},
            }
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects)
        settings = artifact.nodes[0]["settings"]
        assert settings["saturation"] == pytest.approx(1.3, rel=1e-3)

    def test_build_artifact_from_ae_color_balance(self):
        """AE Color Balance 效果正确映射"""
        ae_effects = [
            {
                "matchName": "ADBE Color Balance",
                "name": "Color Balance",
                "properties": {
                    "ADBE Color Balance-0001": [5.0, -5.0, 0.0],
                    "ADBE Color Balance-0002": [0.0, 0.0, 0.0],
                    "ADBE Color Balance-0003": [-5.0, 0.0, 5.0],
                },
            }
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects)
        settings = artifact.nodes[0]["settings"]
        assert settings["lift"][0] == pytest.approx(1.1, rel=1e-3)
        assert settings["lift"][1] == pytest.approx(0.9, rel=1e-3)
        assert settings["gain"][0] == pytest.approx(0.9, rel=1e-3)
        assert settings["gain"][2] == pytest.approx(1.1, rel=1e-3)

    def test_build_artifact_from_ae_multiple_effects(self):
        """多个 AE 效果组合正确映射"""
        ae_effects = [
            {
                "matchName": "ADBE Brightness & Contrast",
                "name": "BC",
                "properties": {
                    "ADBE Brightness-Contrast-1": 5.0,
                    "ADBE Brightness-Contrast-2": 10.0,
                },
            },
            {
                "matchName": "ADBE Hue Saturation",
                "name": "HS",
                "properties": {"ADBE HSL-2": 20.0},
            },
            {
                "matchName": "ADBE Color Balance",
                "name": "CB",
                "properties": {
                    "ADBE Color Balance-0001": [5.0, 0.0, -5.0],
                    "ADBE Color Balance-0002": [0.0, 0.0, 0.0],
                    "ADBE Color Balance-0003": [0.0, 0.0, 0.0],
                },
            },
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects)
        assert artifact.metadata["ae_effects_count"] == 3
        settings = artifact.nodes[0]["settings"]
        assert settings["saturation"] == pytest.approx(1.2, rel=1e-3)
        assert settings["contrast"] == pytest.approx(1.1, rel=1e-3)

    def test_build_artifact_from_ae_unknown_effects_ignored(self):
        """未知 AE 效果应被忽略"""
        ae_effects = [
            {
                "matchName": "ADBE Unknown Effect",
                "name": "Unknown",
                "properties": {"some_prop": 42},
            }
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects)
        settings = artifact.nodes[0]["settings"]
        assert settings["saturation"] == 1.0
        assert settings["contrast"] == 1.0


class TestCrossPlatformRoundtrip:
    """跨平台往返测试"""

    def setup_method(self):
        self.engine = ResolveColorEngine()

    def test_resolve_artifact_ffmpeg_roundtrip(self):
        """Resolve -> Artifact -> FFmpeg 滤镜一致性"""
        artifact = self.engine.build_artifact("cinematic")
        ffmpeg_filter_1 = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert ffmpeg_filter_1 is not None
        assert len(ffmpeg_filter_1) > 0

    def test_ae_artifact_ffmpeg_roundtrip(self):
        """AE -> Artifact -> FFmpeg 滤镜可用"""
        ae_effects = [
            {
                "matchName": "ADBE Brightness & Contrast",
                "name": "BC",
                "properties": {
                    "ADBE Brightness-Contrast-1": 5.0,
                    "ADBE Brightness-Contrast-2": 15.0,
                },
            }
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects)
        ffmpeg_filter = self.engine.artifact_to_ffmpeg_filter(artifact)
        assert "brightness=" in ffmpeg_filter
        assert "contrast=" in ffmpeg_filter

    def test_resolve_artifact_ae_jsx_valid(self):
        """Resolve -> Artifact -> AE JSX 语法有效"""
        artifact = self.engine.build_artifact("warm_vintage")
        jsx = self.engine.artifact_to_ae_jsx(artifact)
        # 基本语法检查
        assert jsx.count("{") == jsx.count("}")
        assert jsx.count('"') % 2 == 0

    def test_ae_artifact_ae_jsx_roundtrip(self):
        """AE -> Artifact -> AE JSX 往返效果一致"""
        ae_effects = [
            {
                "matchName": "ADBE Color Balance",
                "name": "CB",
                "properties": {
                    "ADBE Color Balance-0001": [10.0, -5.0, 0.0],
                    "ADBE Color Balance-0002": [0.0, 0.0, 0.0],
                    "ADBE Color Balance-0003": [0.0, 0.0, 0.0],
                },
            }
        ]
        artifact = self.engine.build_artifact_from_ae(ae_effects)
        jsx = self.engine.artifact_to_ae_jsx(artifact)
        assert "ADBE Color Balance" in jsx
        assert "10.0" in jsx or "10.00" in jsx

    def test_artifact_json_roundtrip_preserves_data(self):
        """Artifact JSON 往返保留所有字段"""
        original = ColorGradeArtifact(
            preset_name="test_roundtrip",
            source="after_effects",
            nodes=[
                {
                    "node_type": "primary",
                    "name": "Test Node",
                    "enabled": True,
                    "settings": {
                        "lift": [1.1, 0.9, 1.0, 0.05],
                        "gamma": [1.0, 1.0, 1.0, 0.0],
                        "gain": [0.95, 1.0, 1.05, -0.02],
                        "saturation": 1.2,
                        "contrast": 1.15,
                        "pivot": 0.5,
                    },
                }
            ],
            ffmpeg_filter="eq=saturation=1.2:contrast=1.15",
            metadata={"test": True, "version": 2},
        )
        json_str = original.to_json()
        restored = ColorGradeArtifact.from_dict(json.loads(json_str))
        assert restored.preset_name == original.preset_name
        assert restored.source == original.source
        assert restored.ffmpeg_filter == original.ffmpeg_filter
        assert len(restored.nodes) == len(original.nodes)
        assert restored.nodes[0]["settings"]["saturation"] == original.nodes[0]["settings"]["saturation"]
        assert restored.metadata["test"] == True

    def test_artifact_to_color_grade_config(self):
        """Artifact 正确转为 ColorGradeConfig"""
        artifact = ColorGradeArtifact(
            preset_name="test_config",
            nodes=[{
                "node_type": "primary",
                "name": "Test",
                "enabled": True,
                "settings": {
                    "saturation": 1.2,
                    "contrast": 1.1,
                    "pivot": 0.5,
                    "lift": [0.9, 0.92, 1.0, 0.02],
                    "gamma": [1.0, 1.0, 1.02, 0.0],
                    "gain": [1.08, 1.05, 0.98, 0.0],
                },
            }],
        )
        config = self.engine._artifact_to_color_grade_config(artifact)
        assert isinstance(config, ColorGradeConfig)
        assert config.saturation == 1.2
        assert config.contrast == 1.1
        assert config.pivot == 0.5
        assert isinstance(config.lift, ColorWheelParams)
        assert config.lift.red == 0.9
        assert config.lift.green == 0.92
        assert config.lift.blue == 1.0
        assert config.lift.master == 0.02
        assert config.gamma.red == 1.0
        assert config.gain.red == 1.08
        assert config.gain.blue == 0.98
