# -*- coding: utf-8 -*-
"""
FIX-02 验证：ai/auto_produce.py 退出码与成功语义诚实化（审计 F1 根治回归守卫）
================================================================================
契约出处: docs/execution_result_contract.md §1/§2.3/§4
锁死的行为规约（回归即红）:
  1. dry_run 无论步骤如何，report["success"] 必须为 False，
     execution_path="simulated"，dry_run_completed 单独表达"流程冒烟通过"。
  2. 真实模式(dry_run=False)下 step6 未产出可验文件 → ok=False、success=False。
  3. success=True 仅当真实模式 + 产物内容级验证通过。
  4. _artifact_verified 对垃圾文件/缺失文件必须 False（fail-closed）。
  5. api/toolchain_api 与 api_server 任务处理器不得再出现 mode 默认 simulate/auto
     （静态断言，配合 FIX-09 扫描器形成双层守护）。
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path

import pytest

import ai.auto_produce as ap

REPO_ROOT = Path(__file__).resolve().parents[1]


class _OKExecutor:
    """桩执行器：像真实 dry-run 一样回报 success=True（考验的正是聚合层诚实性）"""

    def execute(self, script, dry_run: bool = False):  # noqa: ANN001
        return {
            "success": True,
            "media_count": len(script.shots),
            "total_overlays": 1,
            "success_count": 1,
        }


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """把 _PROJECT_ROOT/CORPUS 重定向到 tmp，杜绝写真实 output/ 与依赖 D 盘语料。"""
    random.seed(7)  # _fallback_shots 无内部种子：固定序列，防 validate 时长偏差断言随机飘
    monkeypatch.setattr(ap, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ap, "CORPUS_META_PATH", tmp_path / "no_corpus.json")
    lib = tmp_path / "data" / "real_amv_test"
    lib.mkdir(parents=True)
    (lib / "src_a.mp4").write_bytes(b"\x00" * 2048)  # 让 step1 有候选
    monkeypatch.setattr(ap, "ResolveExecutor", _OKExecutor)
    monkeypatch.setattr(ap, "AEExecutor", _OKExecutor)
    return tmp_path


class TestDryRunNeverClaimsSuccess:
    def test_dry_run_success_is_false(self, sandbox):
        rep = ap.auto_produce(theme="t", duration_target=45.0, dry_run=True)
        assert rep["success"] is False, "dry_run 不得报 success=True（F1 根治点）"
        assert rep["execution_path"] == "simulated"
        assert rep["dry_run_completed"] is True
        assert rep["step6_render"]["ok"] is False
        assert rep["step6_render"]["executed"] is False

    def test_dry_run_report_written_to_disk(self, sandbox):
        rep = ap.auto_produce(theme="t2", duration_target=45.0, dry_run=True)
        report_path = sandbox / "output" / "t2_production_report.json"
        assert report_path.exists()
        text = report_path.read_text(encoding="utf-8")
        # 落盘报告本身也必须携带 simulated 标记（读者不得被误导）
        assert '"execution_path": "simulated"' in text
        assert rep  # 返回值与落盘同源


class TestRealModeArtifactGating:
    def test_missing_artifact_fails(self, sandbox):
        # 真实模式：桩执行器"成功"但无人渲染文件 → step6 必须 False
        rep = ap.auto_produce(theme="t", duration_target=45.0, dry_run=False)
        assert rep["step6_render"]["ok"] is False
        assert rep["step6_render"]["execution_path"] == "failed"
        assert rep["success"] is False
        assert rep["execution_path"] == "failed"
        assert rep["step6_render"]["artifact_verified"] is False

    def test_verified_artifact_succeeds(self, sandbox, monkeypatch):
        out = sandbox / "output"
        out.mkdir(parents=True, exist_ok=True)
        (out / "t_AMV.mp4").write_bytes(b"\x00" * 4096)
        # 注入验证通过（不依赖本机 ffprobe）——验证的是"聚合逻辑"而非 ffprobe 本身，
        # ffprobe 行为由下一条测试单独实证
        monkeypatch.setattr(ap, "_artifact_verified", lambda p: p.exists())
        rep = ap.auto_produce(theme="t", duration_target=45.0, dry_run=False)
        assert rep["step6_render"]["ok"] is True
        assert rep["success"] is True
        assert rep["execution_path"] == "real"


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="本机无 ffprobe，跳过内容级验证实测")
class TestArtifactVerifiedFailClosed:
    def test_nonexistent_false(self, tmp_path):
        assert ap._artifact_verified(tmp_path / "nope.mp4") is False

    def test_garbage_file_false(self, tmp_path):
        # 正是审计 A 类形态：seek 撑大的"看起来存在"文件必须被内容级验证拦下
        f = tmp_path / "fake.mp4"
        f.write_bytes(b"AI_VIDEO_SIMULATED_OUTPUT" + b"\x00" * 4096)
        assert ap._artifact_verified(f) is False


class TestDownstreamDefaultsHonest:
    """静态断言：FIX-02 已切断的默认值不得回涨（行为由 FIX-09 扫描器全量接管）"""

    def test_toolchain_api_no_auto_default(self):
        text = (REPO_ROOT / "api" / "toolchain_api.py").read_text(encoding="utf-8")
        assert 'Field("auto"' not in text
        assert 'Query("auto"' not in text

    def test_api_server_task_handlers_no_simulate_default(self):
        text = (REPO_ROOT / "api_server.py").read_text(encoding="utf-8")
        assert 'config.get("mode", "simulate")' not in text

    def test_api_server_fake_metrics_removed(self):
        text = (REPO_ROOT / "api_server.py").read_text(encoding="utf-8")
        assert '"frames_processed": 100' not in text
        assert '"psnr": 38.5' not in text
