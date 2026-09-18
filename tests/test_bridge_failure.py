# -*- coding: utf-8 -*-
"""test_bridge_failure.py — 桥接失败结构化纯函数测试"""
import json
from pathlib import Path

from core.bridge_failure import (
    CATEGORIES,
    BridgeFailure,
    classify,
    failures_summary,
    from_reason,
)


def test_classify_bridge_down():
    assert classify("AE未运行且启动失败") == "BRIDGE_DOWN"
    assert classify("Bridge无响应(300s超时)") == "TIMEOUT"
    assert classify("计划为空或aerender不存在") == "BRIDGE_DOWN"


def test_classify_timeout():
    assert classify("Bridge无响应(300s超时)") == "TIMEOUT"
    assert classify("subprocess timeout after 1800s") == "TIMEOUT"


def test_classify_output_corrupt():
    assert classify("输出文件损坏") == "OUTPUT_CORRUPT"
    assert classify("文件截断, size=0") == "OUTPUT_CORRUPT"


def test_classify_script_syntax():
    assert classify("JSX syntax error at line 42") == "SCRIPT_SYNTAX"
    assert classify("ExtendScript error: undefined variable") == "SCRIPT_SYNTAX"


def test_classify_disk_full():
    assert classify("No space left on device") == "DISK_FULL"
    assert classify("ENOSPC") == "DISK_FULL"


def test_classify_license():
    assert classify("License missing for plugin XYZ") == "LICENSE_MISSING"
    assert classify("许可弹窗 blocking render") == "LICENCE_POPUP_BLOCKING"


def test_classify_default():
    assert classify("something completely unknown") == "BRIDGE_DOWN"


def test_from_reason_structure():
    bf = from_reason("AE未运行且启动失败", "ae_launch")
    assert bf.category == "BRIDGE_DOWN"
    assert bf.stage == "ae_launch"
    assert bf.detail == "AE未运行且启动失败"
    assert bf.recoverable is True
    assert bf.ts


def test_from_reason_not_recoverable():
    bf = from_reason("合成构建失败: ['shot_001: error']", "build_validate")
    assert bf.category == "BRIDGE_DOWN"
    assert bf.recoverable is True
    bf2 = from_reason("输出文件损坏", "normalize")
    assert bf2.category == "OUTPUT_CORRUPT"
    assert bf2.recoverable is False


def test_to_dict_serializable():
    bf = from_reason("Bridge无响应(300s超时)", "bridge_build")
    d = bf.to_dict()
    assert set(d.keys()) == {"category", "stage", "detail", "recoverable", "ts"}
    assert json.dumps(d, ensure_ascii=False)


def test_failures_summary_empty():
    s = failures_summary([])
    assert s == {"count": 0, "by_category": {}, "recoverable": False}


def test_failures_summary_aggregation():
    fs = [
        from_reason("AE未运行", "ae_launch"),
        from_reason("Bridge无响应(300s超时)", "bridge_build"),
        from_reason("输出文件损坏", "normalize"),
    ]
    s = failures_summary(fs)
    assert s["count"] == 3
    assert s["by_category"]["BRIDGE_DOWN"] == 1
    assert s["by_category"]["TIMEOUT"] == 1
    assert s["by_category"]["OUTPUT_CORRUPT"] == 1
    assert s["recoverable"] is True


def test_failures_summary_all_unrecoverable():
    fs = [from_reason("输出文件损坏", "normalize")]
    s = failures_summary(fs)
    assert s["recoverable"] is False


def test_ae_failures_read_from_run_dir(tmp_path):
    from scripts.render_audit import ae_failures
    failures = [
        from_reason("AE未运行", "ae_launch").to_dict(),
        from_reason("Bridge无响应(300s超时)", "bridge_build").to_dict(),
    ]
    (tmp_path / "ae_failures.json").write_text(
        json.dumps(failures, ensure_ascii=False), encoding="utf-8")
    result = ae_failures(tmp_path)
    assert len(result) == 2
    assert result[0]["category"] == "BRIDGE_DOWN"
    assert result[1]["stage"] == "bridge_build"


def test_ae_failures_missing_file(tmp_path):
    from scripts.render_audit import ae_failures
    assert ae_failures(tmp_path) == []
