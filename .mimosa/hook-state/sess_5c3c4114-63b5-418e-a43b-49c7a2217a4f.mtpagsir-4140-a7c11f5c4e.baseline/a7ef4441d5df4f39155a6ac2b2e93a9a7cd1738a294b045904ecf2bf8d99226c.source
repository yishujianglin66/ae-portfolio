"""tests/test_material_tag_fusion.py — 素材三源标签融合测试"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def tag_files(tmp_path):
    content = {
        "summary": {},
        "results": [
            {"video": "C:/x/v1.mp4", "dominant": "bangumi",
             "votes": {"bangumi": 10, "not_painting": 6}, "mean_probs": {}},
            {"video": "C:/x/v2.mp4", "dominant": "3d",
             "votes": {"3d": 12}, "mean_probs": {}},
        ],
    }
    atmo = {
        "results": {
            "v1.mp4": {"atmosphere": "燃向", "energy": 9, "emotion": "热血",
                       "scene_type": "战斗", "confidence": 0.9},
            "v3.mp4": {"atmosphere": "治愈", "energy": 5},
        },
    }
    c_path = tmp_path / "content.json"
    c_path.write_text(json.dumps(content), encoding="utf-8")
    a_dir = tmp_path / "atmo"
    a_dir.mkdir()
    (a_dir / "batch1.json").write_text(json.dumps(atmo), encoding="utf-8")
    return c_path, a_dir


class TestLoaders:
    def test_load_content_tags(self, tag_files):
        from models.tagging.material_tag_fusion import load_content_tags
        c = load_content_tags(tag_files[0])
        assert c["v1.mp4"]["dominant"] == "bangumi"
        assert c["v2.mp4"]["dominant"] == "3d"

    def test_load_content_missing(self, tmp_path):
        from models.tagging.material_tag_fusion import load_content_tags
        assert load_content_tags(tmp_path / "nope.json") == {}

    def test_load_atmosphere_tags(self, tag_files):
        from models.tagging.material_tag_fusion import load_atmosphere_tags
        a = load_atmosphere_tags(tag_files[1])
        assert a["v1.mp4"]["atmosphere"] == "燃向"
        assert a["v3.mp4"]["energy"] == 5


class TestFusion:
    def test_fuse_three_sources(self, tag_files, tmp_path):
        from models.tagging.material_tag_fusion import fuse_material_tags
        out = tmp_path / "unified.json"
        fused = fuse_material_tags(
            video_names=["v1.mp4", "v2.mp4", "v3.mp4"],
            camera_tags={"v1.mp4": "pan_left", "v2.mp4": "static"},
            out_path=out,
            content_path=tag_files[0],
            anno_dir=tag_files[1],
        )
        assert set(fused) == {"v1.mp4", "v2.mp4", "v3.mp4"}
        v1 = fused["v1.mp4"]
        assert v1["content"] == "bangumi"
        assert v1["atmosphere"] == "燃向"
        assert v1["camera"] == "pan_left"
        assert v1["sources"] == {"content": True, "atmosphere": True,
                                 "camera": True}
        v3 = fused["v3.mp4"]
        assert v3["atmosphere"] == "治愈"
        assert v3["content"] is None  # 无内容标签
        # 落盘 payload 结构
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["n_materials"] == 3
        assert payload["coverage"]["content"] == 2
        assert payload["coverage"]["atmosphere"] == 2
        assert payload["coverage"]["camera"] == 2

    def test_fuse_union_of_names(self, tag_files, tmp_path):
        from models.tagging.material_tag_fusion import fuse_material_tags
        fused = fuse_material_tags(out_path=tmp_path / "u2.json",
                                   content_path=tag_files[0],
                                   anno_dir=tag_files[1])
        # 三源并集: v1,v2 (content) + v3 (atmo)
        assert {"v1.mp4", "v2.mp4", "v3.mp4"} <= set(fused)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
