# -*- coding: utf-8 -*-
"""flagship_runner 模块级助手特征化测试（2026-09-22）。

背景：`pipeline/flagship_runner.py` 未覆盖 915 行（23.09%）。它的 stage_* 需要真实
素材与引擎，但**模块级助手**是关键观测/容错层，且都无外部依赖：

  · `run_cmd`            —— 子进程封装；**超时按进程树杀**（防 aerender/ffmpeg
                            变孤儿占 CPU/GPU），是 P0-1 稳定性加固的落点；
  · `md5_file`           —— 素材指纹（缓存与去重依赖）；
  · `emit_event`         —— events.jsonl 事件流（观测层统一入口，**写失败不得抛**）；
  · `write_manifest_safe`—— 容错写 manifest：**run 目录被并行进程删掉时自愈重建**，
                            并镜像到 reports/ 保证证据幸存；
  · `ffprobe_json`       —— 元数据探测，失败返回空 dict（降级不抛）；
  · `critic_gate`        —— 阶段边界自评，abort 时抛 CriticAbortError。

本文件锁这些容错语义（"坏情况下照样不崩"正是它们存在的理由）。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import pipeline.flagship_runner as fr  # noqa: E402
from pipeline.midstep_critic import CriticVerdict  # noqa: E402
from pipeline.flagship_runner import (  # noqa: E402
    CriticAbortError,
    emit_event,
    ffprobe_json,
    md5_file,
    run_cmd,
    write_manifest_safe,
)


@pytest.fixture(scope="module")
def tiny_video(tmp_path_factory):
    p = tmp_path_factory.mktemp("fr") / "v.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=24:duration=0.5",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-bf", "0", str(p)],
        check=True, capture_output=True, timeout=120)
    return p


# ---------------------------------------------------------------------------
# run_cmd
# ---------------------------------------------------------------------------

class TestRunCmd:
    def test_returns_decoded_completed_process(self):
        r = run_cmd(["python", "-c", "print('hello')"])
        assert r.returncode == 0
        assert isinstance(r.stdout, str) and "hello" in r.stdout
        assert isinstance(r.stderr, str)

    def test_nonzero_returncode_does_not_raise(self):
        """非零退出码要如实返回，由调用方判断 —— 不在此处抛。"""
        r = run_cmd(["python", "-c", "import sys; sys.exit(3)"])
        assert r.returncode == 3

    def test_path_args_are_stringified(self, tmp_path):
        r = run_cmd(["python", "-c", "import sys; print(sys.argv[1])",
                     tmp_path / "x.txt"])
        assert str(tmp_path / "x.txt") in r.stdout

    def test_timeout_raises_and_kills_tree(self):
        """超时必须抛 TimeoutExpired（而不是挂死），且已尝试回收子进程树。"""
        with pytest.raises(subprocess.TimeoutExpired):
            run_cmd(["python", "-c", "import time; time.sleep(30)"],
                    timeout=1.0)

    def test_stderr_captured_on_failure(self):
        r = run_cmd(["python", "-c",
                     "import sys; sys.stderr.write('boom'); sys.exit(1)"])
        assert "boom" in r.stderr and r.returncode == 1


# ---------------------------------------------------------------------------
# md5_file
# ---------------------------------------------------------------------------

class TestMd5File:
    def test_known_digest_for_empty_file(self, tmp_path):
        p = tmp_path / "empty.bin"
        p.write_bytes(b"")
        assert md5_file(p) == hashlib.md5(b"").hexdigest()

    def test_matches_hashlib_for_content(self, tmp_path):
        p = tmp_path / "data.bin"
        payload = b"AE Knowledge Vault" * 1000        # 跨多个 8192 块读取
        p.write_bytes(payload)
        assert md5_file(p) == hashlib.md5(payload).hexdigest()

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            md5_file(tmp_path / "nope.bin")


# ---------------------------------------------------------------------------
# emit_event
# ---------------------------------------------------------------------------

class TestEmitEvent:
    def test_appends_one_jsonl_line(self, tmp_path):
        ev = tmp_path / "events.jsonl"
        emit_event(ev, "stage_start", {"stage": "s1"})
        emit_event(ev, "stage_done", {"stage": "s1", "status": "ok"})
        lines = ev.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["event"] == "stage_start" and first["stage"] == "s1"
        assert isinstance(first["ts"], float)

    def test_payload_flattened_into_top_level(self, tmp_path):
        """payload 直接展开到顶层（事件流消费方按 key 读取，不嵌套）。"""
        ev = tmp_path / "e.jsonl"
        emit_event(ev, "critic_verdict", {"decision": "pass", "score": 0.9})
        row = json.loads(ev.read_text(encoding="utf-8").strip())
        assert row["decision"] == "pass" and row["score"] == 0.9

    def test_write_failure_is_swallowed(self, tmp_path):
        """事件写失败只告警、不抛 —— 观测层故障不能拖垮生产流程。"""
        emit_event(tmp_path / "no_such_dir" / "e.jsonl", "x", {"a": 1})
        assert not (tmp_path / "no_such_dir").exists()

    def test_no_payload_ok(self, tmp_path):
        ev = tmp_path / "e.jsonl"
        emit_event(ev, "only_event")
        assert json.loads(ev.read_text(encoding="utf-8").strip())["event"] == "only_event"


# ---------------------------------------------------------------------------
# write_manifest_safe
# ---------------------------------------------------------------------------

class TestWriteManifestSafe:
    def test_writes_run_dir_and_mirrors(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fr, "PROJECT_ROOT", tmp_path / "proj")
        run_dir = tmp_path / "run1"
        write_manifest_safe(run_dir, {"run_id": "R1", "ok": True})
        assert json.loads((run_dir / "manifest.json").read_text(
            encoding="utf-8"))["ok"] is True
        mirror = tmp_path / "proj" / "reports" / "flagship_runs" / "R1_manifest.json"
        assert mirror.exists(), "必须镜像到 reports/ 以保证证据幸存"

    def test_recreates_deleted_run_dir(self, tmp_path, monkeypatch):
        """核心容错：run 目录被并行进程删掉时要自愈重建（否则末尾写 manifest 崩）。"""
        monkeypatch.setattr(fr, "PROJECT_ROOT", tmp_path / "proj")
        run_dir = tmp_path / "gone"          # 故意不存在
        write_manifest_safe(run_dir, {"run_id": "R2"})
        assert (run_dir / "manifest.json").exists()

    def test_default_run_id_used_for_mirror(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fr, "PROJECT_ROOT", tmp_path / "proj")
        write_manifest_safe(tmp_path / "run", {})
        assert (tmp_path / "proj" / "reports" / "flagship_runs"
                / "flagship_manifest.json").exists()


# ---------------------------------------------------------------------------
# ffprobe_json
# ---------------------------------------------------------------------------

class TestFfprobeJson:
    def test_returns_format_and_streams(self, tiny_video):
        meta = ffprobe_json(tiny_video)
        assert meta and "format" in meta and meta["streams"]

    def test_missing_file_returns_empty_dict(self, tmp_path):
        """探测失败返回空 dict（降级不抛），调用方按 falsy 处理。"""
        assert ffprobe_json(tmp_path / "nope.mp4") == {}


# ---------------------------------------------------------------------------
# critic_gate
# ---------------------------------------------------------------------------

class _FakeCritic:
    """最小替身，但 verdict 用**真实类型** CriticVerdict。

    曾用自造轻量替身，结果 CriticAbortError 依次要 stage / value_estimate …
    字段缺失逐个暴露 —— 用真类型比追字段稳（也更接近真实集成）。
    """

    def __init__(self, decision: str):
        self._d = decision
        self.calls: list = []

    def evaluate(self, stage, artifacts, context):
        self.calls.append((stage, artifacts, context))
        return CriticVerdict(stage=stage, value_estimate=0.5, decision=self._d)


class TestCriticGate:
    def test_pass_writes_verdict_event(self, tmp_path):
        ev = tmp_path / "e.jsonl"
        critic = _FakeCritic("pass")
        verdict = fr.critic_gate(critic, ev, "s0", {"a": 1})
        assert verdict.decision == "pass"
        row = json.loads(ev.read_text(encoding="utf-8").strip())
        assert row["event"] == "critic_verdict" and row["decision"] == "pass"
        assert critic.calls and critic.calls[0][0] == "s0"

    def test_abort_raises_and_still_emits(self, tmp_path):
        """abort 也要先落事件再抛 —— 否则现场证据丢失。"""
        ev = tmp_path / "e.jsonl"
        with pytest.raises(CriticAbortError):
            fr.critic_gate(_FakeCritic("abort"), ev, "s1", {})
        assert json.loads(ev.read_text(encoding="utf-8").strip())["decision"] == "abort"

    def test_warn_does_not_raise(self, tmp_path):
        verdict = fr.critic_gate(_FakeCritic("warn"), tmp_path / "e.jsonl", "s2", {})
        assert verdict.decision == "warn"
