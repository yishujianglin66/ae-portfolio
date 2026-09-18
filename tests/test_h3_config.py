#!/usr/bin/env python3
"""MiniMax H3接入：配置块 + ConfigValidator校验。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestDefaultConfigContainsH3Block:
    """B 组：默认配置含 minimax_h3 块。"""

    def test_default_config_has_minimax_h3(self):
        """ConfigManager 默认配置存在 minimax_h3。"""
        from core.config import ConfigManager

        mgr = ConfigManager(auto_load=False)
        # 自动 merge 默认配置层即可
        default_cfg = mgr._config or {}
        # _register_default_config 之后 _sources[0] 是默认层
        if not default_cfg and mgr._sources:
            default_cfg = mgr._sources[0].data
        assert "minimax_h3" in default_cfg, "默认配置无 minimax_h3 块"
        h3 = default_cfg["minimax_h3"]
        assert isinstance(h3, dict)
        # 关键 key 存在
        for k in ("base_url", "api_key", "cost_per_sec_2k", "cost_per_sec_768p",
                  "default_resolution", "default_duration_sec", "default_fps",
                  "default_aspect_ratio", "download_dir", "cache_dir",
                  "local_deployment", "timeout_sec", "max_retries"):
            assert k in h3, f"minimax_h3 缺少关键 key: {k}"

    def test_h3_defaults_sane_values(self):
        """默认值区间合理：成本>0、时长[5,15]、fps=24、分辨率在允许集合。"""
        from core.config import ConfigManager

        mgr = ConfigManager(auto_load=False)
        default_cfg = mgr._sources[0].data if mgr._sources else mgr._config
        h3 = (default_cfg or {}).get("minimax_h3", {})
        assert h3["cost_per_sec_2k"] > 0
        assert h3["cost_per_sec_768p"] > 0
        assert 5 <= h3["default_duration_sec"] <= 15
        assert h3["default_fps"] == 24
        assert h3["default_resolution"] in ("768p", "2k", "1440p")
        assert h3["default_aspect_ratio"] in ("9:16", "16:9", "1:1", "4:3", "21:9")
        local = h3.get("local_deployment")
        assert isinstance(local, dict)
        assert "enabled" in local


class TestH3ConfigValidation:
    """ConfigValidator H3 校验规则。"""

    def _validate(self, cfg_overrides: dict[str, Any]):
        from core.config import ConfigManager, ConfigValidator
        # 拿默认配置 + 覆写
        mgr = ConfigManager(auto_load=False)
        default_cfg = mgr._sources[0].data if mgr._sources else {}
        cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in default_cfg.items()}
        if "minimax_h3" not in cfg:
            cfg["minimax_h3"] = {}
        cfg["minimax_h3"].update(cfg_overrides)
        validator = ConfigValidator(strict=False)
        return validator.validate(cfg)

    def test_url_set_requires_5_errors_when_baseurl_without_apikey(self):
        """base_url 非空 + api_key 空 => warning。"""
        errors, warnings = self._validate({"base_url": "https://api.minimaxi.com/v1", "api_key": ""})
        joined_w = " ".join(w.lower() for w in warnings)
        assert any("minimax_h3" in w for w in warnings)
        assert len(errors) == 0, f"不应 error: {errors}"

    def test_duration_out_of_range_18_error(self):
        """default_duration_sec=18（>15）=> error。"""
        errors, _ = self._validate({"default_duration_sec": 18})
        joined_e = " ".join(errors).lower()
        assert "default_duration_sec" in joined_e

    def test_duration_out_of_range_3_error(self):
        """default_duration_sec=3 (<5) => error。"""
        errors, _ = self._validate({"default_duration_sec": 3})
        joined_e = " ".join(errors).lower()
        assert "default_duration_sec" in joined_e

    def test_resolution_invalid_error(self):
        """default_resolution="1080p" 非官方支持 => error。"""
        errors, _ = self._validate({"default_resolution": "1080p"})
        joined_e = " ".join(errors).lower()
        assert "default_resolution" in joined_e

    def test_resolution_2k_and_1440p_ok(self):
        """default_resolution="2k" 与 "1440p" 通过。"""
        for res in ("2k", "1440p", "768p"):
            errors, _ = self._validate({"default_resolution": res})
            assert not any("default_resolution" in e.lower() for e in errors), f"{res} 失败: {errors}"

    def test_fps_not_24_warning(self):
        """default_fps=30 => warning（not error。"""
        errors, warnings = self._validate({"default_fps": 30})
        joined_w = " ".join(warnings).lower()
        assert any("default_fps" in w for w in warnings), f"缺少 fps warning: {warnings}"
        assert not any("default_fps" in e.lower() for e in errors), "fps 不应为 error"

    def test_poll_wait_too_small_error(self):
        """max_poll_wait_sec=30（<60）=> error。"""
        errors, _ = self._validate({"max_poll_wait_sec": 30})
        joined_e = " ".join(errors).lower()
        assert "max_poll_wait_sec" in joined_e

    def test_download_cache_dirs_normalized_to_abs(self):
        """download_dir、cache_dir 相对路径经校验后转绝对。"""
        from core.config import ConfigManager, ConfigValidator
        mgr = ConfigManager(auto_load=False)
        default_cfg = mgr._sources[0].data if mgr._sources else {}
        cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in default_cfg.items()}
        cfg["minimax_h3"] = dict(default_cfg.get("minimax_h3", {}).copy())
        cfg["minimax_h3"]["download_dir"] = "./output/h3_downloads"
        cfg["minimax_h3"]["cache_dir"] = "./data/h3_cache"
        validator = ConfigValidator(strict=False)
        validator.validate(cfg)
        dl = cfg["minimax_h3"]["download_dir"]
        cc = cfg["minimax_h3"]["cache_dir"]
        assert os.path.isabs(dl), f"download_dir 未归一化: {dl!r}"
        assert os.path.isabs(cc), f"cache_dir 未归一化: {cc!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider"])
