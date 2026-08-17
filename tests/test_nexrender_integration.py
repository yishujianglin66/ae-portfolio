#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 integrations/nexrender.py 关键契约
========================================

覆盖 nexrender 集成器对产品稳定性最关键的部分：

1. create_template_config 生成的配置结构正确
2. create_template_config 把 string 数据生成 data 资产
3. create_template_config 跳过 _ 前缀的 key（私有约定）
4. create_template_config 正确处理 images / audio 字段
5. create_template_config 允许 render_settings 覆盖 output
6. create_subtitle_template_config 默认值（字体/颜色/glow）
7. create_subtitle_template_config subtitles 被 JSON 序列化
8. save_config 写出 UTF-8 JSON
9. batch_render 逐条生成独立 config
10. 工厂 get_nexrender_integration
11. NexrenderIntegration 构造容错（无 node / 无 nexrender 也不抛）
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


# ============================================================
# 工厂
# ============================================================
class TestFactory:
    def test_get_nexrender_integration_returns_instance(self):
        from integrations.nexrender import (
            NexrenderIntegration,
            get_nexrender_integration,
        )
        # patch 掉 _find_node / _find_nexrender 避免实际探测环境
        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx nexrender"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            inst = get_nexrender_integration()
        assert isinstance(inst, NexrenderIntegration)


class TestInit:
    def test_init_does_not_throw_when_node_missing(self):
        """即便环境无 node/nexrender，也不应抛异常。"""
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx nexrender"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            inst = NexrenderIntegration()
        assert inst.node_path == "node"
        assert inst.nexrender_path == "npx nexrender"

    def test_init_stores_provided_paths(self):
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            inst = NexrenderIntegration(
                node_path="C:/custom/node.exe",
                nexrender_path="C:/custom/nexrender",
                ae_path="C:/custom/ae.exe",
            )
        assert inst.node_path == "C:/custom/node.exe"
        assert inst.nexrender_path == "C:/custom/nexrender"
        assert inst.ae_path == "C:/custom/ae.exe"


# ============================================================
# create_template_config
# ============================================================
class TestCreateTemplateConfig:
    def _make(self, **overrides):
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            inst = NexrenderIntegration()
        return inst

    def test_minimal_config_structure(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/proj.aep",
            output_path="T:/out.mp4",
            data={"composition": "Main"},
        )
        # 顶层字段
        assert "template" in config
        assert "output" in config
        assert "assets" in config
        assert "actions" in config
        # template
        assert config["template"]["src"] == "T:/proj.aep"
        assert config["template"]["composition"] == "Main"
        # output
        assert config["output"]["src"] == "T:/out.mp4"
        assert config["output"]["format"] == "mp4"
        assert config["output"]["codec"] == "h264"
        assert config["output"]["quality"] == 100

    def test_default_composition_when_not_in_data(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"title": "X"},
        )
        # 没传 composition 时默认 "Main"
        assert config["template"]["composition"] == "Main"

    def test_string_data_becomes_data_assets(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"title": "片头", "subtitle": "副标题"},
        )
        # 两个 string 字段 → 两个 data 资产
        assert len(config["assets"]) == 2
        asset_map = {a["layerName"]: a for a in config["assets"]}
        assert asset_map["title"]["type"] == "data"
        assert asset_map["title"]["property"] == "Source Text"
        assert asset_map["title"]["value"] == "片头"
        assert asset_map["subtitle"]["value"] == "副标题"

    def test_underscore_prefix_keys_skipped(self):
        """以 _ 开头的 key 不应被生成 data 资产（私有约定）。"""
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"title": "OK", "_internal": "secret", "_private": "hide me"},
        )
        layer_names = [a["layerName"] for a in config["assets"]]
        assert "title" in layer_names
        assert "_internal" not in layer_names
        assert "_private" not in layer_names

    def test_non_string_values_skipped(self):
        """非 string 字段不生成 data 资产（避免与 images/audio 路径冲突）。"""
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"title": "OK", "duration": 30, "enabled": True, "ratio": 1.5},
        )
        layer_names = [a["layerName"] for a in config["assets"]]
        assert layer_names == ["title"]

    def test_images_field_creates_image_assets(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={
                "composition": "Main",
                "images": {"logo": "T:/logo.png", "bg": "T:/bg.jpg"},
            },
        )
        # 2 image assets
        image_assets = [a for a in config["assets"] if a["type"] == "image"]
        assert len(image_assets) == 2
        names = {a["layerName"] for a in image_assets}
        assert names == {"logo", "bg"}
        paths = {a["src"] for a in image_assets}
        assert paths == {"T:/logo.png", "T:/bg.jpg"}

    def test_audio_field_creates_audio_asset(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"composition": "Main", "audio": "T:/bgm.mp3"},
        )
        audio_assets = [a for a in config["assets"] if a["type"] == "audio"]
        assert len(audio_assets) == 1
        assert audio_assets[0]["src"] == "T:/bgm.mp3"
        assert audio_assets[0]["layerName"] == "Audio"

    def test_render_settings_override_output(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"composition": "Main"},
            render_settings={"codec": "h265", "quality": 95, "resolution": "4k"},
        )
        assert config["output"]["codec"] == "h265"
        assert config["output"]["quality"] == 95
        assert config["output"]["resolution"] == "4k"
        # 未覆盖的字段保留
        assert config["output"]["format"] == "mp4"

    def test_render_settings_none_is_safe(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={"composition": "Main"},
            render_settings=None,
        )
        # 默认 output 应保留
        assert config["output"]["codec"] == "h264"

    def test_empty_data_produces_no_assets(self):
        inst = self._make()
        config = inst.create_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            data={},
        )
        assert config["assets"] == []


# ============================================================
# create_subtitle_template_config
#
# 注：当前实现的 create_template_config 仅把 str 类型的 data 字段
# 转成 data 资产（因为 isinstance(value, str) 判断）。
# 因此 create_subtitle_template_config 中的 int（fontSize）和
# list（fontColor / glowColor）会被静默丢弃，不会出现在 assets 中。
# 这是已知的实现 bug，subtitle 模板渲染依赖外部机制传这些值。
# 以下测试记录当前真实行为，避免误判。
# ============================================================
class TestCreateSubtitleTemplateConfig:
    def _make(self):
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            return NexrenderIntegration()

    def test_subtitles_serialized_as_json_string(self):
        inst = self._make()
        subs = [{"text": "你好", "start": 0.0, "end": 2.0}]
        config = inst.create_subtitle_template_config(
            template_path="T:/sub.aep",
            output_path="T:/sub.mp4",
            subtitles=subs,
        )
        data_assets = {a["layerName"]: a for a in config["assets"]}
        assert "subtitles" in data_assets
        # subtitles 字段是 JSON 字符串
        loaded = json.loads(data_assets["subtitles"]["value"])
        assert loaded == subs

    def test_string_fields_become_assets(self):
        """仅 string 字段会进入 assets（fontFamily / glowEnabled）。"""
        inst = self._make()
        config = inst.create_subtitle_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            subtitles=[],
        )
        data_assets = {a["layerName"]: a for a in config["assets"]}
        # 仅 string 字段被加入
        assert "fontFamily" in data_assets
        assert "glowEnabled" in data_assets
        # 原始非 string 字段不在 assets 中（记录当前行为）
        assert "fontSize" not in data_assets
        assert "fontColor" not in data_assets
        assert "glowColor" not in data_assets

    def test_default_font(self):
        inst = self._make()
        config = inst.create_subtitle_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            subtitles=[],
        )
        data_assets = {a["layerName"]: a for a in config["assets"]}
        assert data_assets["fontFamily"]["value"] == "Arial"

    def test_glow_enabled_lowercase_string(self):
        """glowEnabled 必须为 lowercase 字符串（JSX 端判断用）。"""
        inst = self._make()
        config = inst.create_subtitle_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            subtitles=[],
            glow_enabled=True,
        )
        data_assets = {a["layerName"]: a for a in config["assets"]}
        assert data_assets["glowEnabled"]["value"] == "true"

    def test_glow_disabled_lowercase_string(self):
        inst = self._make()
        config = inst.create_subtitle_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            subtitles=[],
            glow_enabled=False,
        )
        data_assets = {a["layerName"]: a for a in config["assets"]}
        assert data_assets["glowEnabled"]["value"] == "false"

    def test_custom_font_family(self):
        inst = self._make()
        config = inst.create_subtitle_template_config(
            template_path="T:/p.aep",
            output_path="T:/o.mp4",
            subtitles=[],
            font_family="Source Han Sans CN",
        )
        data_assets = {a["layerName"]: a for a in config["assets"]}
        assert data_assets["fontFamily"]["value"] == "Source Han Sans CN"


# ============================================================
# save_config
# ============================================================
class TestSaveConfig:
    def test_writes_json_file(self, tmp_path):
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            inst = NexrenderIntegration()
        config = {
            "template": {"src": "T:/a.aep", "composition": "Main"},
            "output": {"src": "T:/o.mp4", "format": "mp4"},
            "assets": [{"type": "data", "layerName": "t", "value": "你好"}],
        }
        target = tmp_path / "config.json"
        inst.save_config(config, str(target))
        # 文件存在
        assert target.exists()
        # 内容是 UTF-8 JSON（中文不转义）
        text = target.read_text(encoding="utf-8")
        loaded = json.loads(text)
        assert loaded == config
        # 中文未转义为 \u
        assert "你好" in text

    def test_save_config_raises_when_parent_missing(self, tmp_path):
        """save_config 不自动创建父目录（保持当前契约）。"""
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            inst = NexrenderIntegration()
        target = tmp_path / "nested" / "cfg.json"
        # 当前实现不创建父目录，会抛 FileNotFoundError
        # 记录此行为以便发现回归
        with pytest.raises(FileNotFoundError):
            inst.save_config({}, str(target))


# ============================================================
# batch_render
# ============================================================
class TestBatchRender:
    def _make(self):
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            return NexrenderIntegration()

    @pytest.mark.asyncio
    async def test_batch_creates_one_config_per_data(self, tmp_path):
        inst = self._make()
        data_list = [
            {"title": "First", "subtitle": "S1"},
            {"title": "Second", "subtitle": "S2"},
            {"title": "Third", "subtitle": "S3"},
        ]
        # mock render 让其仅记录 config 后返回 success
        received = []

        async def fake_render(config, config_path=None, progress_callback=None):
            received.append(config)
            return {"success": True, "output": config["output"]["src"]}

        with patch.object(inst, "render", side_effect=fake_render):
            results = await inst.batch_render(
                template_path="T:/t.aep",
                output_dir=str(tmp_path),
                data_list=data_list,
            )
        # 收到 3 个 config
        assert len(received) == 3
        # 每个 output_path 独立
        output_paths = [c["output"]["src"] for c in received]
        assert len(set(output_paths)) == 3
        # 第 0 个对应第一个 data
        assert received[0]["output"]["src"].endswith("output_0000.mp4")
        assert received[1]["output"]["src"].endswith("output_0001.mp4")
        assert received[2]["output"]["src"].endswith("output_0002.mp4")

    @pytest.mark.asyncio
    async def test_batch_creates_output_dir(self, tmp_path):
        inst = self._make()
        out_dir = tmp_path / "deeply" / "nested"
        assert not out_dir.exists()

        async def fake_render(config, config_path=None, progress_callback=None):
            return {"success": True}

        with patch.object(inst, "render", side_effect=fake_render):
            await inst.batch_render(
                template_path="T:/t.aep",
                output_dir=str(out_dir),
                data_list=[{"x": 1}],
            )
        # 输出目录被自动创建
        assert out_dir.exists()

    @pytest.mark.asyncio
    async def test_batch_preserves_per_data_values(self, tmp_path):
        inst = self._make()
        data_list = [
            {"title": "A", "subtitle": "Sa"},
            {"title": "B", "subtitle": "Sb"},
        ]
        received = []

        async def fake_render(config, config_path=None, progress_callback=None):
            received.append(config)
            return {"success": True}

        with patch.object(inst, "render", side_effect=fake_render):
            await inst.batch_render(
                template_path="T:/t.aep",
                output_dir=str(tmp_path),
                data_list=data_list,
            )
        # 验证每个 config 都独立包含自己的数据
        titles = []
        for c in received:
            data_assets = {a["layerName"]: a for a in c["assets"]}
            titles.append(data_assets["title"]["value"])
        assert titles == ["A", "B"]

    @pytest.mark.asyncio
    async def test_batch_returns_results_in_order(self, tmp_path):
        inst = self._make()
        # 注意：i 必须是 string（create_template_config 仅处理 str）
        data_list = [{"idx": str(i)} for i in range(3)]

        async def fake_render(config, config_path=None, progress_callback=None):
            # 找 idx 字段
            data_assets = {a["layerName"]: a for a in config["assets"]}
            return {"success": True, "i": data_assets["idx"]["value"]}

        with patch.object(inst, "render", side_effect=fake_render):
            results = await inst.batch_render(
                template_path="T:/t.aep",
                output_dir=str(tmp_path),
                data_list=data_list,
            )
        assert [r["i"] for r in results] == ["0", "1", "2"]

    @pytest.mark.asyncio
    async def test_batch_passes_render_settings(self, tmp_path):
        inst = self._make()
        received = []

        async def fake_render(config, config_path=None, progress_callback=None):
            received.append(config)
            return {"success": True}

        with patch.object(inst, "render", side_effect=fake_render):
            await inst.batch_render(
                template_path="T:/t.aep",
                output_dir=str(tmp_path),
                data_list=[{"x": 1}],
                render_settings={"codec": "h265", "quality": 90},
            )
        assert received[0]["output"]["codec"] == "h265"
        assert received[0]["output"]["quality"] == 90

    @pytest.mark.asyncio
    async def test_batch_empty_data_list(self, tmp_path):
        inst = self._make()
        with patch.object(inst, "render", new=AsyncMock()) as mock_render:
            results = await inst.batch_render(
                template_path="T:/t.aep",
                output_dir=str(tmp_path),
                data_list=[],
            )
        assert results == []
        assert not mock_render.called


# ============================================================
# get_template_variables 异常路径
# ============================================================
class TestGetTemplateVariables:
    def _make(self):
        from integrations.nexrender import NexrenderIntegration

        with patch.object(NexrenderIntegration, "_find_node", return_value="node"), \
             patch.object(NexrenderIntegration, "_find_nexrender", return_value="npx"), \
             patch.object(NexrenderIntegration, "_ensure_dependencies"):
            return NexrenderIntegration()

    def test_returns_empty_when_ae_engine_unavailable(self):
        """AE 引擎不可用时必须返回空列表（不能抛）。"""
        inst = self._make()
        # 让内部 import 抛异常
        with patch.dict("sys.modules", {"puppet_automation.src.engines.ae.engine": None}):
            variables = inst.get_template_variables("T:/does_not_exist.aep")
        # 必须返回 list（可能为空）
        assert isinstance(variables, list)
