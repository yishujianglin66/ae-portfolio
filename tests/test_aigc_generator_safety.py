# -*- coding: utf-8 -*-
"""AIGC 生成器安全层与离线路径特征化测试（2026-09-20）。

背景：`ai/aigc_generator.py` 在覆盖率快照里是 **0.00%**（621 语句），而它恰好承载
本会话修过的两处**休眠 bug**：
  1. `_safe_urlopen` 原实现**递归调用自身**（重构事故）→ 任何调用都 RecursionError
     且被上层 except 吞掉 ⇒ 全部适配器（含本地 ComfyUI 通道）**从未真正发出过请求**；
  2. `_validate_url` 一律拒绝回环地址 ⇒ ComfyUI 本地通道恒不可用，
     "一开 ComfyUI 自动升级"链路从未生效（已加 `_LOCAL_HOSTS` 显式白名单）。

这两个 bug 的共同特征是"**静默**"——没有测试就永远不会有人发现。本测试把安全层
的真实契约钉住（含回归哨兵），并覆盖可离线执行的 Mock 通道与提示词生成。
"""
import sys
import urllib.request
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ai import aigc_generator as ag  # noqa: E402


# ---------------------------------------------------------------------------
# _validate_url —— SSRF 防线
# ---------------------------------------------------------------------------

class TestValidateUrl:
    def test_rejects_non_http_schemes(self):
        for bad in ("ftp://api.openai.com/x", "file:///etc/passwd",
                    "javascript:alert(1)", "not-a-url"):
            with pytest.raises(ValueError):
                ag._validate_url(bad)

    def test_rejects_non_whitelisted_host(self):
        with pytest.raises(ValueError, match="非白名单域"):
            ag._validate_url("https://evil.example.com/steal")

    def test_accepts_whitelisted_public_host(self, monkeypatch):
        monkeypatch.setattr("socket.getaddrinfo",
                            lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
        assert ag._validate_url("https://api.openai.com/v1/models").startswith("https://")

    def test_rejects_whitelisted_host_resolving_to_private_ip(self, monkeypatch):
        """白名单域名被解析到内网/回环 ⇒ 拒绝（DNS 重绑定类攻击的兜底）。"""
        for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.1.1"):
            monkeypatch.setattr("socket.getaddrinfo",
                                lambda *a, **k: [(2, 1, 6, "", (ip, 443))])
            with pytest.raises(ValueError, match="内网地址"):
                ag._validate_url("https://api.openai.com/v1")

    # ---- 本地 ComfyUI 通道（本会话修复点）----

    def test_local_comfyui_http_8188_allowed(self):
        """回归哨兵：修复前 loopback 一律被拒 → ComfyUI 通道从未可达。"""
        assert ag._validate_url("http://127.0.0.1:8188/prompt").startswith("http://127.0.0.1")

    def test_local_host_requires_http(self):
        with pytest.raises(ValueError, match="非法本地服务"):
            ag._validate_url("https://127.0.0.1:8188/prompt")

    def test_local_host_requires_known_port(self):
        with pytest.raises(ValueError, match="非法本地服务"):
            ag._validate_url("http://127.0.0.1:9999/prompt")

    def test_other_localhosts_follow_same_rule(self):
        assert ag._validate_url("http://localhost:8188/x")
        assert ag._validate_url("http://::1:8188/x".replace("::1", "localhost"))


# ---------------------------------------------------------------------------
# _safe_urlopen —— 递归事故回归哨兵
# ---------------------------------------------------------------------------

class TestSafeUrlopen:
    def test_uses_opener_not_recursion(self, monkeypatch):
        """核心回归：原实现递归调自身 → RecursionError 被吞 ⇒ 从无真实请求。"""
        opened = {}

        class _FakeOpener:
            def open(self, req, timeout=None):
                opened["url"] = req.full_url
                opened["timeout"] = timeout
                return "RESP"

        monkeypatch.setattr(ag.urllib.request, "build_opener", lambda *a, **k: _FakeOpener())
        monkeypatch.setattr("socket.getaddrinfo",
                            lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
        req = urllib.request.Request("https://api.openai.com/v1/models")
        assert ag._safe_urlopen(req, timeout=7) == "RESP"
        assert opened["url"].startswith("https://api.openai.com")
        assert opened["timeout"] == 7

    def test_validates_before_any_network(self, monkeypatch):
        """非法 URL 必须在建连之前就被拒（不得触碰网络）。"""
        def _boom(*a, **k):
            raise AssertionError("不应发起网络调用")
        monkeypatch.setattr(ag.urllib.request, "build_opener", _boom)
        with pytest.raises(ValueError):
            ag._safe_urlopen(urllib.request.Request("https://evil.example.com/x"),
                             timeout=1)


# ---------------------------------------------------------------------------
# 落盘路径约束
# ---------------------------------------------------------------------------

class TestOutputPathGuard:
    def test_inside_output_dir_allowed(self, tmp_path, monkeypatch):
        out_dir = tmp_path / "materials"
        monkeypatch.setattr(ag, "OUTPUT_DIR", out_dir)
        assert Path(ag._safe_output_path(str(out_dir / "a.mp4"))).name == "a.mp4"
        assert out_dir.exists()          # 目录被按需创建

    def test_traversal_outside_output_dir_rejected(self, tmp_path, monkeypatch):
        out_dir = tmp_path / "materials"
        out_dir.mkdir()
        monkeypatch.setattr(ag, "OUTPUT_DIR", out_dir)
        with pytest.raises(ValueError, match="越界输出路径"):
            ag._safe_output_path(str(out_dir / ".." / "escaped.mp4"))

    def test_download_validates_url_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ag, "OUTPUT_DIR", tmp_path / "materials")
        called = {"n": 0}
        monkeypatch.setattr(ag.urllib.request, "urlretrieve",
                            lambda *a, **k: called.__setitem__("n", called["n"] + 1))
        with pytest.raises(ValueError):
            ag._safe_download("https://evil.example.com/x.mp4",
                              str(tmp_path / "materials" / "x.mp4"))
        assert called["n"] == 0, "URL 未过校验就发起了下载"


# ---------------------------------------------------------------------------
# 提示词生成（离线纯逻辑）
# ---------------------------------------------------------------------------

class TestPromptGenerator:
    def test_generates_english_prompt_with_style_and_quality(self):
        pg = ag.PromptGenerator()
        prompt = pg.generate_video_prompt("一只猫在雨中奔跑", style="cinematic")
        assert "high quality" in prompt and "4K" in prompt
        assert prompt == prompt.strip(", ")

    def test_chinese_style_keywords_mapped(self):
        pg = ag.PromptGenerator()
        assert ag.PromptGenerator.STYLE_MAP["高燃"] == "epic intense dramatic"
        prompt = pg.generate_video_prompt("火焰特效", style="高燃")
        assert isinstance(prompt, str) and prompt

    def test_empty_input_still_returns_string(self):
        assert isinstance(ag.PromptGenerator().generate_video_prompt(""), str)


# ---------------------------------------------------------------------------
# Mock 通道（离线可跑：代表"无 API key 时的兜底路径"）
# ---------------------------------------------------------------------------

class TestMockAdapter:
    def test_always_available(self):
        assert ag.MockAIGCAdapter().is_available() is True

    def test_generate_image_writes_file(self, tmp_path):
        out = tmp_path / "placeholder.png"
        res = ag.MockAIGCAdapter().generate_image("x", str(out), size="32x24")
        assert res["success"] is True and out.exists() and out.stat().st_size > 0
        assert res["source"] == "Mock"

    def test_generate_image_bad_size_reports_error_not_raise(self, tmp_path):
        """解析失败的 size 要**返回错误字典**而非抛异常（适配器契约：永不抛）。"""
        res = ag.MockAIGCAdapter().generate_image("x", str(tmp_path / "p.png"),
                                                  size="10x")
        assert res["success"] is False and "error" in res

    def test_generate_image_unparsable_size_falls_back_to_default(self, tmp_path):
        """无 "x" 分隔符时按默认 1024x1024 兜底（实现是容错而非报错）。"""
        out = tmp_path / "d.png"
        res = ag.MockAIGCAdapter().generate_image("x", str(out), size="bad")
        assert res["success"] is True and out.exists()


class TestGeneratorFacade:
    def test_lists_services_with_availability(self):
        services = ag.AIGCGenerator().list_available_services()
        assert services and all({"name", "available"} <= set(s) for s in services)

    def test_mock_is_in_adapter_chain(self):
        names = [a.name for a in ag.AIGCGenerator().adapters]
        assert "Mock" in names, "Mock 必须常备 —— 它是无 key 时的兜底通道"

    def test_generate_supplementary_returns_list(self, tmp_path, monkeypatch):
        """离线环境下（无任何 key）也必须返回列表而非抛异常。"""
        gen = ag.AIGCGenerator(output_dir=tmp_path)
        out = gen.generate_supplementary("测试素材", missing_count=1)
        assert isinstance(out, list)
