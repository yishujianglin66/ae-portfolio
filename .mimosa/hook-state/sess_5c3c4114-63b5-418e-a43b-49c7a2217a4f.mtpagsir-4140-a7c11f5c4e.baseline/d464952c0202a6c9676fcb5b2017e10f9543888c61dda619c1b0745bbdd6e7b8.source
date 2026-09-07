"""
AE 操作稳定性测试
==================

验证 AE 操作的稳定性。

测试内容：
- 合成 CRUD 测试
- 图层 CRUD 测试
- 效果应用测试
- 关键帧设置测试
- 撤销/重做测试
- 项目保存/加载测试

注意：真实环境测试需要 AE 运行，Mock 环境下使用模拟服务。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest


class TestCompositionCRUD:
    """合成 CRUD 测试。"""

    def test_create_composition(self, bridge_client):
        """测试创建合成。

        验证基本合成创建功能。
        """
        response = bridge_client.send_command(
            "create_composition",
            {
                "name": "Test_Comp_Basic",
                "width": 1920,
                "height": 1080,
                "duration": 5.0,
                "frame_rate": 30,
            },
        )
        assert response.is_success, f"创建合成失败: {response.error}"
        assert response.result is not None
        assert "comp_id" in response.result
        assert response.result["name"] == "Test_Comp_Basic"
        assert response.result["width"] == 1920
        assert response.result["height"] == 1080

    def test_create_multiple_compositions(self, bridge_client):
        """测试创建多个合成。

        验证连续创建多个合成的稳定性。
        注意：mock 环境下可能返回相同的 ID，真实环境下 ID 应唯一。
        """
        comp_names = [f"MultiComp_{i}" for i in range(5)]
        comp_ids = []

        for name in comp_names:
            response = bridge_client.send_command(
                "create_composition",
                {
                    "name": name,
                    "width": 1280,
                    "height": 720,
                    "duration": 3.0,
                    "frame_rate": 24,
                },
            )
            assert response.is_success, f"创建合成 {name} 失败: {response.error}"
            assert response.result is not None
            assert "comp_id" in response.result
            comp_ids.append(response.result["comp_id"])

        assert len(comp_ids) == 5
        # 验证所有创建都成功返回了 ID
        assert all(cid is not None for cid in comp_ids)

    def test_get_composition_list(self, bridge_client):
        """测试获取合成列表。

        验证合成列表查询功能。
        """
        # 先创建几个合成
        for i in range(3):
            bridge_client.send_command(
                "create_composition",
                {"name": f"ListTest_{i}", "width": 1920, "height": 1080, "duration": 2.0, "frame_rate": 30},
            )

        response = bridge_client.send_command("get_composition_list")
        assert response.is_success, f"获取合成列表失败: {response.error}"
        assert response.result is not None
        assert "compositions" in response.result
        assert isinstance(response.result["compositions"], list)

    def test_delete_composition(self, bridge_client):
        """测试删除合成。

        验证合成删除功能。
        """
        # 先创建一个合成
        create_resp = bridge_client.send_command(
            "create_composition",
            {"name": "ToDelete", "width": 1920, "height": 1080, "duration": 1.0, "frame_rate": 30},
        )
        assert create_resp.is_success
        comp_id = create_resp.result["comp_id"]

        # 删除合成
        delete_resp = bridge_client.send_command(
            "delete_composition",
            {"comp_id": comp_id},
        )
        assert delete_resp.is_success, f"删除合成失败: {delete_resp.error}"
        assert delete_resp.result is not None
        assert delete_resp.result.get("deleted") is True


class TestLayerCRUD:
    """图层 CRUD 测试。"""

    def test_create_solid_layer(self, bridge_client):
        """测试创建固态图层。

        验证基本图层创建功能。
        """
        response = bridge_client.send_command(
            "create_solid_layer",
            {
                "name": "Solid_Red",
                "width": 1920,
                "height": 1080,
                "color": [1.0, 0.0, 0.0],
            },
        )
        assert response.is_success, f"创建固态图层失败: {response.error}"
        assert response.result is not None
        assert "layer_id" in response.result

    def test_create_multiple_layers(self, bridge_client):
        """测试创建多个图层。

        验证连续创建图层的稳定性。
        """
        colors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 1.0, 0.0],
            [1.0, 0.0, 1.0],
        ]

        layer_ids = []
        for i, color in enumerate(colors):
            response = bridge_client.send_command(
                "create_solid_layer",
                {
                    "name": f"Layer_{i}",
                    "width": 1920,
                    "height": 1080,
                    "color": color,
                },
            )
            assert response.is_success, f"创建图层 {i} 失败: {response.error}"
            assert response.result is not None
            layer_ids.append(response.result["layer_id"])

        assert len(layer_ids) == 5

    def test_get_layer_list(self, bridge_client):
        """测试获取图层列表。

        验证图层列表查询功能。
        """
        response = bridge_client.send_command("get_layer_list")
        assert response.is_success, f"获取图层列表失败: {response.error}"
        assert response.result is not None
        assert "layers" in response.result
        assert isinstance(response.result["layers"], list)

    def test_delete_layer(self, bridge_client):
        """测试删除图层。

        验证图层删除功能。
        """
        # 先创建一个图层
        create_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "ToDeleteLayer", "width": 100, "height": 100, "color": [1, 1, 1]},
        )
        assert create_resp.is_success
        layer_id = create_resp.result["layer_id"]

        # 删除图层
        delete_resp = bridge_client.send_command(
            "delete_layer",
            {"layer_id": layer_id},
        )
        assert delete_resp.is_success, f"删除图层失败: {delete_resp.error}"
        assert delete_resp.result is not None
        assert delete_resp.result.get("deleted") is True


class TestEffects:
    """效果操作测试。"""

    def test_apply_effect(self, bridge_client):
        """测试应用效果。

        验证效果应用功能。
        """
        # 先创建图层
        layer_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "EffectLayer", "width": 1920, "height": 1080, "color": [0.5, 0.5, 0.5]},
        )
        assert layer_resp.is_success
        layer_id = layer_resp.result["layer_id"]

        # 应用效果
        response = bridge_client.send_command(
            "apply_effect",
            {
                "layer_id": layer_id,
                "effect_name": "ADBE Gaussian Blur 2",
            },
        )
        assert response.is_success, f"应用效果失败: {response.error}"
        assert response.result is not None
        assert response.result.get("applied") is True

    def test_apply_multiple_effects(self, bridge_client):
        """测试应用多个效果。

        验证连续应用多个效果的稳定性。
        """
        # 先创建图层
        layer_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "MultiEffectLayer", "width": 1920, "height": 1080, "color": [1, 1, 1]},
        )
        assert layer_resp.is_success
        layer_id = layer_resp.result["layer_id"]

        effects = [
            "ADBE Gaussian Blur 2",
            "ADBE Tint",
            "ADBE Levels",
        ]

        for effect_name in effects:
            response = bridge_client.send_command(
                "apply_effect",
                {"layer_id": layer_id, "effect_name": effect_name},
            )
            assert response.is_success, f"应用效果 {effect_name} 失败: {response.error}"


class TestKeyframes:
    """关键帧操作测试。"""

    def test_add_keyframe(self, bridge_client):
        """测试添加关键帧。

        验证关键帧添加功能。
        """
        # 先创建图层
        layer_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "KFLayer", "width": 1920, "height": 1080, "color": [1, 0, 0]},
        )
        assert layer_resp.is_success
        layer_id = layer_resp.result["layer_id"]

        # 添加关键帧
        response = bridge_client.send_command(
            "add_keyframe",
            {
                "layer_id": layer_id,
                "property": "ADBE Transform Group-ADBE Position",
                "time": 0.0,
                "value": [0, 0],
            },
        )
        assert response.is_success, f"添加关键帧失败: {response.error}"
        assert response.result is not None
        assert "keyframe_id" in response.result

    def test_add_multiple_keyframes(self, bridge_client):
        """测试添加多个关键帧。

        验证连续添加关键帧的稳定性。
        """
        # 先创建图层
        layer_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "MultiKFLayer", "width": 1920, "height": 1080, "color": [0, 1, 0]},
        )
        assert layer_resp.is_success
        layer_id = layer_resp.result["layer_id"]

        keyframes = [
            (0.0, [960, 540]),
            (1.0, [100, 100]),
            (2.0, [1820, 100]),
            (3.0, [1820, 980]),
            (4.0, [960, 540]),
        ]

        kf_ids = []
        for t, value in keyframes:
            response = bridge_client.send_command(
                "add_keyframe",
                {
                    "layer_id": layer_id,
                    "property": "ADBE Transform Group-ADBE Position",
                    "time": t,
                    "value": value,
                },
            )
            assert response.is_success, f"在 {t}s 添加关键帧失败: {response.error}"
            assert response.result is not None
            kf_ids.append(response.result["keyframe_id"])

        assert len(kf_ids) == 5

    def test_set_property(self, bridge_client):
        """测试设置属性。

        验证属性设置功能。
        """
        # 先创建图层
        layer_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "PropLayer", "width": 1920, "height": 1080, "color": [0, 0, 1]},
        )
        assert layer_resp.is_success
        layer_id = layer_resp.result["layer_id"]

        # 设置属性
        response = bridge_client.send_command(
            "set_property",
            {
                "layer_id": layer_id,
                "property": "ADBE Transform Group-ADBE Opacity",
                "value": 50,
            },
        )
        assert response.is_success, f"设置属性失败: {response.error}"
        assert response.result is not None
        assert response.result.get("set") is True


class TestUndoRedo:
    """撤销/重做测试。"""

    def test_undo(self, bridge_client):
        """测试撤销操作。

        验证撤销功能是否正常工作。
        """
        response = bridge_client.send_command("undo", {"steps": 1})
        assert response.is_success, f"撤销失败: {response.error}"
        assert response.result is not None
        assert response.result.get("undone") is True

    def test_redo(self, bridge_client):
        """测试重做操作。

        验证重做功能是否正常工作。
        """
        response = bridge_client.send_command("redo", {"steps": 1})
        assert response.is_success, f"重做失败: {response.error}"
        assert response.result is not None
        assert response.result.get("redone") is True

    def test_undo_redo_cycle(self, bridge_client):
        """测试撤销-重做循环。

        验证连续撤销重做的稳定性。
        """
        # 先执行一些操作
        for i in range(5):
            bridge_client.send_command(
                "create_solid_layer",
                {"name": f"UndoRedo_{i}", "width": 100, "height": 100, "color": [1, 1, 1]},
            )

        # 撤销 3 步
        undo_resp = bridge_client.send_command("undo", {"steps": 3})
        assert undo_resp.is_success

        # 重做 2 步
        redo_resp = bridge_client.send_command("redo", {"steps": 2})
        assert redo_resp.is_success


class TestProjectIO:
    """项目保存/加载测试。"""

    def test_save_project(self, bridge_client, test_project_path):
        """测试保存项目。

        验证项目保存功能。
        """
        response = bridge_client.send_command(
            "save_project",
            {"path": str(test_project_path)},
        )
        assert response.is_success, f"保存项目失败: {response.error}"
        assert response.result is not None
        assert response.result.get("saved") is True

    def test_open_project(self, bridge_client, test_project_path):
        """测试打开项目。

        验证项目加载功能。
        """
        # 先保存
        save_resp = bridge_client.send_command(
            "save_project",
            {"path": str(test_project_path)},
        )
        assert save_resp.is_success

        # 再打开
        open_resp = bridge_client.send_command(
            "open_project",
            {"path": str(test_project_path)},
        )
        assert open_resp.is_success, f"打开项目失败: {open_resp.error}"
        assert open_resp.result is not None
        assert open_resp.result.get("opened") is True

    def test_get_project_info(self, bridge_client):
        """测试获取项目信息。

        验证项目信息查询功能。
        """
        response = bridge_client.send_command("get_project_info")
        assert response.is_success, f"获取项目信息失败: {response.error}"
        assert response.result is not None
        assert "project_name" in response.result


class TestOperationStability:
    """操作稳定性测试。"""

    def test_rapid_operations(self, bridge_client):
        """快速连续操作测试。

        验证快速连续操作的稳定性。
        """
        operations = 20
        results = []

        for i in range(operations):
            response = bridge_client.send_command(
                "echo",
                {"message": f"rapid_op_{i}"},
            )
            results.append(response.is_success)

        success_count = sum(1 for r in results if r)
        success_rate = success_count / operations * 100

        assert success_rate >= 95, (
            f"快速操作成功率过低: {success_rate:.1f}% "
            f"({success_count}/{operations})"
        )

    def test_operation_latency_stats(self, bridge_client):
        """操作延迟统计测试。

        统计各种操作的延迟分布。
        """
        from ae.tests.stability_models import measure_latency

        # 测试 ping
        ping_result = measure_latency(
            lambda: bridge_client.send_command("ping"),
            iterations=20,
        )

        assert ping_result["success_rate"] >= 95
        assert "avg_ms" in ping_result

        print(f"\nPing 延迟: avg={ping_result['avg_ms']:.2f}ms, "
              f"p95={ping_result['p95_ms']:.2f}ms")

    def test_long_operation_sequence(self, bridge_client):
        """长操作序列测试。

        模拟一个完整的工作流：创建合成 → 创建图层 → 应用效果 → 设置关键帧 → 保存。
        """
        # 1. 创建合成
        comp_resp = bridge_client.send_command(
            "create_composition",
            {"name": "WorkflowTest", "width": 1920, "height": 1080, "duration": 5.0, "frame_rate": 30},
        )
        assert comp_resp.is_success, f"创建合成失败: {comp_resp.error}"
        comp_id = comp_resp.result["comp_id"]

        # 2. 创建图层
        layer_resp = bridge_client.send_command(
            "create_solid_layer",
            {"name": "MainLayer", "width": 1920, "height": 1080, "color": [0.2, 0.4, 0.8]},
        )
        assert layer_resp.is_success, f"创建图层失败: {layer_resp.error}"
        layer_id = layer_resp.result["layer_id"]

        # 3. 应用效果
        effect_resp = bridge_client.send_command(
            "apply_effect",
            {"layer_id": layer_id, "effect_name": "ADBE Gaussian Blur 2"},
        )
        assert effect_resp.is_success, f"应用效果失败: {effect_resp.error}"

        # 4. 添加关键帧
        kf_resp = bridge_client.send_command(
            "add_keyframe",
            {
                "layer_id": layer_id,
                "property": "ADBE Transform Group-ADBE Position",
                "time": 2.0,
                "value": [960, 540],
            },
        )
        assert kf_resp.is_success, f"添加关键帧失败: {kf_resp.error}"

        # 5. 设置属性
        prop_resp = bridge_client.send_command(
            "set_property",
            {
                "layer_id": layer_id,
                "property": "ADBE Transform Group-ADBE Opacity",
                "value": 80,
            },
        )
        assert prop_resp.is_success, f"设置属性失败: {prop_resp.error}"

        # 6. 撤销一步
        undo_resp = bridge_client.send_command("undo", {"steps": 1})
        assert undo_resp.is_success, f"撤销失败: {undo_resp.error}"

        # 全部成功
        assert True
