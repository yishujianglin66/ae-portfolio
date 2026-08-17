"""tests/test_model_registry_bridge.py — 资产清单 ↔ 生命周期注册中心桥接测试

背景 (2026-08-14 统一方案):
  - 资产清单 models/model_registry.json = "盘上有什么" (唯一事实源)
  - 生命周期注册中心 (deployment.ModelRegistry) = "哪个版本可用"
  - sync_from_inventory 把前者桥接到后者, 且默认路径从 cwd 相对
    ("./model_registry", 曾散落 4 份副本) 改为稳定绝对路径 data/model_lifecycle
"""
from __future__ import annotations

import json

import pytest


def _write_inventory(path, entries):
    path.write_text(
        json.dumps({"n_models": len(entries), "models": entries},
                   ensure_ascii=False),
        encoding="utf-8",
    )


def test_sync_from_inventory_adds_staging_entries(tmp_path):
    from models.deployment.model_registry import ModelRegistry
    inv = tmp_path / "inventory.json"
    _write_inventory(inv, [
        {"id": "videomae_movieshots_movement", "task": "运镜分类",
         "type": "videomae_finetuned", "path": "D:\\fake\\model.safetensors",
         "size_mb": 329, "source": "gullalc", "status": "active"},
        {"id": "yolov8x_det", "task": "目标检测", "type": "yolo_detector",
         "path": "models\\yolov8x.pt", "size_mb": 130, "source": "ultralytics",
         "status": "active"},
    ])
    reg = ModelRegistry(registry_path=str(tmp_path / "lifecycle"))
    result = reg.sync_from_inventory(str(inv))
    assert result["added"] == 2
    assert result["updated"] == 0

    info = reg.get_model("videomae_movieshots_movement")
    assert info is not None
    assert info.model_type == "videomae_finetuned"
    assert info.status == "staging"          # 清单同步默认 staging
    assert info.metadata["inventory"]["size_mb"] == 329


def test_sync_from_inventory_updates_without_clobbering_status(tmp_path):
    from models.deployment.model_registry import ModelRegistry
    inv = tmp_path / "inventory.json"
    _write_inventory(inv, [{"id": "m1", "task": "t", "type": "t1",
                            "path": "p1.pt", "size_mb": 1, "status": "active"}])
    reg = ModelRegistry(registry_path=str(tmp_path / "lifecycle"))
    reg.sync_from_inventory(str(inv))
    # 提升为 production 后再次同步: 生命周期状态不得被回滚
    reg.promote_to_production("m1", "inventory")
    result = reg.sync_from_inventory(str(inv))
    assert result["updated"] == 1
    prod = reg.get_production_model("m1")
    assert prod is not None
    assert prod.model_path == "p1.pt"


def test_sync_missing_inventory_returns_zero(tmp_path):
    from models.deployment.model_registry import ModelRegistry
    reg = ModelRegistry(registry_path=str(tmp_path / "lifecycle"))
    result = reg.sync_from_inventory(str(tmp_path / "nope.json"))
    assert result == {"added": 0, "updated": 0}


def test_default_path_is_stable_and_absolute():
    from models.deployment.model_registry import ModelRegistry
    reg = ModelRegistry()
    assert reg.registry_path.endswith("model_lifecycle")
    assert "\\" in reg.registry_path or "/" in reg.registry_path  # 绝对路径
    assert "Desktop" in reg.registry_path  # 位于项目根 data/ 下


def test_load_registry_helper():
    from models.deployment.model_registry import load_registry
    reg = load_registry()
    assert isinstance(reg, load_registry.__module__ and __import__(
        "models.deployment.model_registry", fromlist=["ModelRegistry"]).ModelRegistry)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
