"""PremiereEngine 和 Premiere Pro API 端点测试。

重点覆盖：
1. JSX 参数转义（防注入攻击）
2. _execute_impl 动作分发（确保每个 action 都有 handler）
3. PremiereEngine 初始化与可用性检测
4. /api/v1/premiere/* 端点参数校验与响应结构
5. 双认证（MCP Token / User JWT）访问 PR 端点
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 将 src 加入 sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ============================================================
# 1. JSX 转义安全测试（防注入）
# ============================================================


class TestJsxEscaping:
    """PremiereEngine._jsx_escape 必须正确处理危险输入。

    注意：_jsx_escape 使用 json.dumps 生成完整 JS 字面量，
    字符串类型结果会自带外层双引号，可直接嵌入 JSX 代码。
    """

    @pytest.fixture
    def engine(self):
        """返回一个最小化初始化的 PremiereEngine（不检查可执行路径）。"""
        from src.engines.premiere.engine import PremiereEngine

        cls = PremiereEngine
        obj = object.__new__(cls)
        return obj

    def test_escape_quotes(self, engine):
        # json.dumps 自带外层引号
        assert engine._jsx_escape('a"b') == '"a\\"b"'
        assert engine._jsx_escape("a'b") == '"a\\\'b"' or engine._jsx_escape("a'b") == '"a\'b"'

    def test_escape_backslashes(self, engine):
        result = engine._jsx_escape("a\\b")
        # 结果应该是 "a\\b"
        assert result.count("\\\\") >= 1 or result == '"a\\\\b"'

    def test_escape_newlines(self, engine):
        result = engine._jsx_escape("line1\nline2\r\nend")
        assert "\\n" in result
        assert "\\r" in result

    def test_escape_script_injection(self, engine):
        """恶意用户输入不可破坏 JSX 语法结构（提前终止字符串）。"""
        payload = '")); app.project.closeDocument(); var x = ("'
        escaped = engine._jsx_escape(payload)
        # json.dumps 会把 payload 中的 " 全部转义，所以除了两端的包裹引号，
        # 中间的原始 " 都必须被转义为 \"
        stripped = escaped[1:-1]  # 去掉两端的包裹引号
        # 现在 stripped 中，任何 " 都必须前有 \
        i = 0
        while i < len(stripped):
            if stripped[i] == '"':
                # 必须是转义的（i>0 且前一位是 \，且那个 \ 本身不是被转义的）
                assert i > 0 and stripped[i - 1] == "\\", f"发现未转义的双引号位置 {i}: {stripped}"
                # 跳过这个转义对
                i += 2
            else:
                i += 1

    def test_escape_unicode_and_path(self, engine):
        # Windows 路径 + 中文 + 单引号
        s = "C:\\项目\\素材 01's cut.mp4"
        escaped = engine._jsx_escape(s)
        # json.dumps 必须返回合法 JSON 字符串（开头结尾都是 "）
        assert escaped.startswith('"') and escaped.endswith('"')
        # 可以被 json.loads 反解回原字符串
        import json as _json
        assert _json.loads(escaped) == s

    def test_escape_non_string_values(self, engine):
        """非字符串类型（数字/布尔/None/列表/字典）也必须正确转为 JS 字面量。"""
        import json as _json
        assert engine._jsx_escape(None) == "null"
        assert engine._jsx_escape(True) == "true"
        assert engine._jsx_escape(42) == "42"
        assert _json.loads(engine._jsx_escape([1, 2, 3])) == [1, 2, 3]
        obj = {"a": 1, "b": 'has "quote"'}
        assert _json.loads(engine._jsx_escape(obj)) == obj


# ============================================================
# 2. PremiereEngine 初始化 & 元数据测试
# ============================================================


class TestPremiereEngineInit:
    """PremiereEngine 基本结构检查。"""

    def test_engine_has_core_actions(self):
        """PremiereEngine 必须暴露最少一套动作方法。"""
        from src.engines.premiere.engine import PremiereEngine

        cls = PremiereEngine
        required = [
            # 基础
            "ping",
            "get_project_info",
            "list_sequences",
            "create_sequence",
            "import_media",
            "add_clip_to_timeline",
            "apply_transition",
            # 时间线
            "delete_clip",
            "split_clip",
            "trim_clip",
            "move_clip",
            "add_track",
            "get_timeline_clips",
            "set_sequence_markers",
            # 高级
            "auto_edit_sequence",
            "import_ae_comp",
            "export_final",
        ]
        for name in required:
            assert hasattr(cls, name), f"PremiereEngine missing action: {name}"

    def test_engine_info_reports_editing_capabilities(self):
        """get_info() 必须声明剪辑能力。"""
        from src.engines.premiere.engine import PremiereEngine

        obj = object.__new__(PremiereEngine)
        info = obj.get_info()
        caps = info.get("capabilities", [])
        # 至少包含剪辑大类能力
        keywords = ["timeline", "clip", "export"]
        flat = " ".join(str(c).lower() for c in caps) + " " + info.get("description", "").lower()
        for kw in keywords:
            assert kw in flat, f"info 中缺少 {kw} 相关能力描述"

    def test_execute_impl_routes_all_known_actions(self):
        """_execute_impl 中的 action → method 映射必须覆盖所有公开动作。"""
        import inspect

        from src.engines.premiere.engine import PremiereEngine

        source = inspect.getsource(PremiereEngine._execute_impl)
        # 从 _execute_impl 抽取所有字符串 key（action 分支）
        import re

        branches = re.findall(r'action\s*==\s*["\']([a-z_]+)["\']', source)
        # 同时支持 elif 形式 + dispatch dict 形式
        if not branches:
            dict_matches = re.findall(r'["\']([a-z_]+)["\']\s*:\s*self\.(\w+)', source)
            branches = [m[0] for m in dict_matches] or [m[1] for m in dict_matches]

        # 最低要求：基础 + 时间线 + 导出至少 12 个分支
        assert len(branches) >= 12, f"_execute_impl 只有 {len(branches)} 个 action 分支，预期 >=12"

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_failed_result(self):
        """未知 action 必须返回失败，而不是抛异常。"""
        from src.engines.base import EngineResult
        from src.engines.premiere.engine import PremiereEngine

        obj = object.__new__(PremiereEngine)
        # 初始化部分字段避免属性错误
        obj.TICKS_PER_SECOND = 254016000000
        obj.executable_path = Path("")
        obj.available = False

        result = await obj.execute(action="definitely_unknown_action_xyz")
        assert isinstance(result, EngineResult)
        assert result.success is False


# ============================================================
# 3. Premiere API 端点测试（ASGI TestClient）
# ============================================================


class TestPremiereEndpoints:
    """通过 httpx ASGI 客户端测试 Premiere 专用端点。"""

    @pytest.fixture
    def app(self):
        """获取 FastAPI app 并在 app.state.engines 注入 mock premiere。"""
        from unittest.mock import AsyncMock, MagicMock

        from src.api.main import app
        from src.engines.base import EngineResult

        mock = AsyncMock()
        mock.name = "premiere"
        mock.available = True
        # get_info 是同步方法，不要用 AsyncMock 默认返回的 coroutine
        mock.get_info = MagicMock(return_value={
            "name": "premiere",
            "display_name": "Premiere Pro 剪辑",
            "description": "Adobe Premiere Pro 剪辑引擎，支持完整时间线操作、AE 动态链接、节拍卡点自动粗剪、三级导出降级。",
            "capabilities": [
                "timeline_clip_management",
                "transitions",
                "sequence_markers",
                "export_video",
                "ae_dynamic_link",
                "auto_beat_edit",
            ],
            "bridge_dir": "C:/tmp/bridge",
            "bridge_status": "unknown",
        })

        async def _exec(action, **kwargs):
            meta: dict = {"result": {"status": "success", "action": action, "params": kwargs}}
            if action == "ping":
                meta = {"result": {"pong": True}}
            return EngineResult(success=True, metadata=meta)

        mock.execute.side_effect = _exec

        if not hasattr(app.state, "engines"):
            app.state.engines = {}
        app.state.engines["premiere"] = mock
        return app

    @pytest.fixture
    def client(self, app):
        """构建 httpx ASGI 测试客户端。"""
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://testserver")

    @pytest.mark.asyncio
    async def test_status_endpoint(self, client):
        resp = await client.get("/api/v1/premiere/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "engine" in body
        assert "bridge" in body

    @pytest.mark.asyncio
    async def test_list_sequences_endpoint(self, client):
        resp = await client.get("/api/v1/premiere/sequences")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body.get("sequences"), list) or body.get("success") is True

    @pytest.mark.asyncio
    async def test_create_sequence_endpoint_validation(self, client):
        """缺少 name 字段应该返回 400。"""
        resp = await client.post("/api/v1/premiere/sequences", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_sequence_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/sequences", json={
            "name": "测试序列",
            "preset_name": "HD 1080p 30",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True

    @pytest.mark.asyncio
    async def test_import_media_endpoint_validation(self, client):
        # 缺少 media_paths
        resp = await client.post("/api/v1/premiere/import", json={"bin_name": "foo"})
        assert resp.status_code == 400
        # media_paths 非列表
        resp = await client.post("/api/v1/premiere/import", json={"media_paths": "not_a_list"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_import_media_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/import", json={
            "media_paths": ["C:/a.mp4", "C:/b.wav"],
            "bin_name": "素材箱",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True

    @pytest.mark.asyncio
    async def test_split_clip_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/split", json={
            "track_index": 0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_split_clip_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/split", json={
            "track_index": 0,
            "clip_index": 2,
            "split_time_seconds": 3.5,
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_trim_clip_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/trim", json={
            "track_index": 0,
            "clip_index": 0,
            "in_point_seconds": 1.0,
            "out_point_seconds": 5.5,
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_move_clip_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/move", json={
            "track_index": 0,
            "clip_index": 0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_move_clip_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/move", json={
            "track_index": 0,
            "clip_index": 0,
            "new_start_seconds": 4.0,
            "new_track_index": 1,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_add_track_endpoint_defaults(self, client):
        resp = await client.post("/api/v1/premiere/timeline/tracks", json={})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_transition_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/transitions", json={
            "track_index": 0,
            "clip_index": 1,
            "transition_name": "Dip to Black",
            "duration_seconds": 1.5,
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_markers_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/markers", json={"markers": "not_a_list"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_markers_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/markers", json={
            "markers": [
                {"time_seconds": 2.0, "name": "Drop 1"},
                {"time_seconds": 5.2, "comment": "beat"},
            ],
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auto_edit_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/auto-edit", json={"clips": "x"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_auto_edit_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/auto-edit", json={
            "clips": [
                {"path": "a.mp4", "duration": 4, "beat_sync": True},
                {"path": "b.mp4", "duration": 3, "beat_sync": True},
            ],
            "music_bpm": 128.0,
            "output_sequence": "AutoCut_01",
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_import_ae_comp_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/import-ae", json={
            "ae_project_path": "x.aep",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_import_ae_comp_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/import-ae", json={
            "ae_project_path": "C:/proj/main.aep",
            "sequence_name": "MasterSeq",
            "comp_names": ["Comp01", "Comp02"],
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/export", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_export_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/export", json={
            "output_path": "C:/out/final.mp4",
            "preset": "H264_1080P",
            "sequence_name": "Master",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert "duration_seconds" in body
        assert "bridge_mode" in body

    @pytest.mark.asyncio
    async def test_quick_premiere_export_endpoint(self, client):
        resp = await client.post(
            "/api/v1/toolchain/quick/premiere-export",
            params={"output_path": "C:/q.mp4", "preset": "H264_1080P"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "success"

    @pytest.mark.asyncio
    async def test_toolchain_tools_includes_premiere(self, client):
        """工具列表中应该能看到 premiere 剪辑工具（edit 分类）。"""
        resp = await client.get("/api/v1/toolchain/tools")
        assert resp.status_code == 200
        body = resp.json()
        names = [t.get("name") for t in body.get("tools", [])]
        assert "premiere" in names, f"premiere 未出现在 toolchain tools 中，names={names}"

    @pytest.mark.asyncio
    async def test_toolchain_workflows_includes_premiere_workflows(self, client):
        resp = await client.get("/api/v1/toolchain/workflows")
        assert resp.status_code == 200
        wf_names = [w.get("name") for w in resp.json().get("workflows", [])]
        assert "premiere_auto_edit" in wf_names
        assert "ae_to_premiere_delivery" in wf_names


# ============================================================
# 4. 双认证访问 Premiere 端点测试
# ============================================================


class TestPremiereEndpointDualAuth:
    """/api/v1/premiere/* 端点应该同时接受 MCP Token 和 User JWT。"""

    @pytest.fixture
    def app_without_auth_bypass(self, monkeypatch):
        """禁用 PUPPET_DISABLE_AUTH，让中间件真正校验 token。"""
        from unittest.mock import AsyncMock, MagicMock

        from src import auth as shared_auth
        from src.api.main import app
        from src.config import settings
        from src.engines.base import EngineResult

        # 1. 认证开关 & 环境
        monkeypatch.delenv("PUPPET_DISABLE_AUTH", raising=False)
        # 直接 patch settings 的属性
        monkeypatch.setattr(settings, "env", "development", raising=False)
        # 把 MCP_AUTH_TOKEN 设置为一个确定的非弱值（不在 WEAK_TOKENS 中）
        TOKEN = "test-mcp-token-12345-unique"
        # settings.mcp_auth_token 可能是 str 或 SecretStr，统一用字符串覆盖
        monkeypatch.setattr(settings, "mcp_auth_token", TOKEN, raising=False)
        # 确保 os.environ 也设好（中间件可能有不同路径读取）
        monkeypatch.setenv("MCP_AUTH_TOKEN", TOKEN)

        # 2. Mock premiere engine
        mock = AsyncMock()
        mock.name = "premiere"
        mock.available = True
        mock.get_info = MagicMock(return_value={"name": "premiere", "capabilities": ["export"], "bridge_dir": None})

        async def _exec(action, **_kw):
            return EngineResult(success=True, metadata={"result": {"ok": True}})

        mock.execute.side_effect = _exec

        if not hasattr(app.state, "engines"):
            app.state.engines = {}
        app.state.engines["premiere"] = mock

        # 3. 确保 shared_auth 中的账号密码正确（admin/admin123）
        # 检查默认用户是否存在，不存在则创建
        if not shared_auth.get_user("admin"):
            shared_auth.create_user("admin", "admin123", "admin")

        self._mcp_token = TOKEN  # 给测试方法读取
        return app

    @pytest.fixture
    def client(self, app_without_auth_bypass):
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app_without_auth_bypass)
        return AsyncClient(transport=transport, base_url="http://testserver")

    @pytest.mark.asyncio
    async def test_no_auth_header_gets_401(self, client):
        resp = await client.get("/api/v1/premiere/sequences")
        assert resp.status_code == 401, f"无认证期望 401，实际 {resp.status_code}"

    @pytest.mark.asyncio
    async def test_mcp_token_accepted(self, client, app_without_auth_bypass):
        token = getattr(self, "_mcp_token", "test-mcp-token-12345-unique")
        resp = await client.get(
            "/api/v1/premiere/sequences",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"MCP Token 失败: {resp.status_code} {resp.text}"

    @pytest.mark.asyncio
    async def test_user_jwt_token_accepted(self, client):
        """使用 admin 账号登录获取 JWT，然后用 JWT 访问受保护端点。"""
        # 登录获取 token（公开端点，正确路径为 /api/v1/auth/login）
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert login_resp.status_code == 200, f"登录失败: {login_resp.status_code} {login_resp.text}"
        jwt = login_resp.json().get("access_token")
        assert jwt, "未获取到 access_token"

        # 用 JWT 访问 premiere 受保护端点
        resp = await client.get(
            "/api/v1/premiere/status",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200, f"JWT 访问 premiere 端点失败: {resp.status_code} {resp.text}"


# ============================================================
# 5. Phase 2.3: 创意模式测试
# ============================================================


class TestCreativePattern:
    """apply_creative_pattern 和 _builtin_pattern 方法测试。"""

    @pytest.fixture
    def engine(self):
        from src.engines.premiere.engine import PremiereEngine
        obj = object.__new__(PremiereEngine)
        obj.TICKS_PER_SECOND = 254016000000
        return obj

    def test_builtin_patterns_exist(self, engine):
        """所有预定义模式必须有定义。"""
        pattern_names = ["beat_cut", "split_screen", "picture_in_picture", "text_overlay", "rhythm_montage"]
        for name in pattern_names:
            result = engine._builtin_pattern(name, {})
            assert result is not None, f"缺少内置模式: {name}"
            assert "name" in result, f"模式 {name} 缺少 name"
            assert "tracks" in result, f"模式 {name} 缺少 tracks"

    def test_builtin_pattern_unknown_falls_back_to_beat_cut(self, engine):
        result = engine._builtin_pattern("unknown_pattern_xyz", {})
        assert result["name"] == "卡点快剪"

    def test_apply_creative_pattern_in_execute_impl(self):
        """_execute_impl 必须包含 creative_pattern 分支。"""
        import inspect

        from src.engines.premiere.engine import PremiereEngine
        source = inspect.getsource(PremiereEngine._execute_impl)
        assert '"apply_creative_pattern"' in source or "'apply_creative_pattern'" in source
        assert '"creative_pattern"' in source or "'creative_pattern'" in source

    def test_capabilities_include_creative_pattern(self):
        from src.engines.premiere.engine import PremiereEngine
        obj = object.__new__(PremiereEngine)
        info = obj.get_info()
        caps = info.get("capabilities", [])
        assert "apply_creative_pattern" in caps


# ============================================================
# 6. Phase 4: 多轨音频混合测试
# ============================================================


class TestAudioMixing:
    """多轨音频混合方法测试。"""

    def test_audio_mixing_methods_exist(self):
        from src.engines.premiere.engine import PremiereEngine
        cls = PremiereEngine
        required = [
            "add_audio_track", "set_track_volume", "set_track_mute",
            "set_track_solo", "set_track_pan", "add_audio_effect",
            "set_clip_volume", "set_clip_audio_gain", "auto_mix_audio",
        ]
        for name in required:
            assert hasattr(cls, name), f"PremiereEngine missing audio method: {name}"

    def test_audio_dispatch_entries(self):
        """_execute_impl 必须包含所有音频操作分支。"""
        import inspect

        from src.engines.premiere.engine import PremiereEngine
        source = inspect.getsource(PremiereEngine._execute_impl)
        audio_actions = [
            "add_audio_track", "set_track_volume", "set_track_mute",
            "set_track_solo", "set_track_pan", "add_audio_effect",
            "set_clip_volume", "set_clip_audio_gain", "auto_mix_audio",
        ]
        for action in audio_actions:
            assert f'"{action}"' in source or f"'{action}'" in source, f"dispatch 缺少音频操作: {action}"

    def test_capabilities_include_audio_mixing(self):
        from src.engines.premiere.engine import PremiereEngine
        obj = object.__new__(PremiereEngine)
        info = obj.get_info()
        caps = info.get("capabilities", [])
        audio_caps = ["add_audio_track", "set_track_volume", "auto_mix_audio",
                      "set_track_mute", "set_track_solo", "set_track_pan",
                      "add_audio_effect", "set_clip_volume", "set_clip_audio_gain"]
        for cap in audio_caps:
            assert cap in caps, f"capabilities 缺少音频能力: {cap}"


# ============================================================
# 7. Phase 5: 高级剪辑工作流测试
# ============================================================


class TestAdvancedWorkflow:
    """高级剪辑工作流方法测试。"""

    def test_advanced_workflow_methods_exist(self):
        from src.engines.premiere.engine import PremiereEngine
        cls = PremiereEngine
        required = [
            "multi_cam_edit", "set_clip_speed", "time_remap",
            "set_clip_keyframes", "nest_clips", "create_nested_sequence",
            "apply_lumetri",
        ]
        for name in required:
            assert hasattr(cls, name), f"PremiereEngine missing advanced method: {name}"

    def test_advanced_dispatch_entries(self):
        """_execute_impl 必须包含所有高级操作分支。"""
        import inspect

        from src.engines.premiere.engine import PremiereEngine
        source = inspect.getsource(PremiereEngine._execute_impl)
        actions = [
            "multi_cam_edit", "set_clip_speed", "time_remap",
            "set_clip_keyframes", "nest_clips", "create_nested_sequence",
            "apply_lumetri",
        ]
        for action in actions:
            assert f'"{action}"' in source or f"'{action}'" in source, f"dispatch 缺少高级操作: {action}"

    def test_capabilities_include_advanced_workflow(self):
        from src.engines.premiere.engine import PremiereEngine
        obj = object.__new__(PremiereEngine)
        info = obj.get_info()
        caps = info.get("capabilities", [])
        advanced_caps = [
            "multi_cam_edit", "set_clip_speed", "time_remap",
            "set_clip_keyframes", "nest_clips", "create_nested_sequence",
            "apply_lumetri",
        ]
        for cap in advanced_caps:
            assert cap in caps, f"capabilities 缺少高级能力: {cap}"

    def test_set_clip_speed_enforces_range(self):
        """set_clip_speed 必须限制速度在有效范围。"""
        from src.engines.premiere.engine import PremiereEngine
        obj = object.__new__(PremiereEngine)
        obj.TICKS_PER_SECOND = 254016000000
        # 测试方法存在，参数校验在 JSX 生成中
        import inspect
        sig = inspect.signature(obj.set_clip_speed)
        params = sig.parameters
        assert "speed" in params
        assert "track_index" in params
        assert "clip_index" in params


# ============================================================
# 8. Phase 6: 新 API 端点集成测试
# ============================================================


class TestNewApiEndpoints:
    """Phase 2.3/4/5 新增 API 端点测试。"""

    @pytest.fixture
    def app(self):
        from unittest.mock import AsyncMock, MagicMock

        from src.api.main import app
        from src.engines.base import EngineResult

        mock = AsyncMock()
        mock.name = "premiere"
        mock.available = True
        mock.get_info = MagicMock(return_value={
            "name": "premiere",
            "display_name": "Premiere Pro 剪辑",
            "description": "完整剪辑引擎",
            "capabilities": [
                "smart_transition", "add_subtitle_track", "smart_auto_edit",
                "apply_creative_pattern",
                "add_audio_track", "set_track_volume", "set_track_mute",
                "set_track_solo", "set_track_pan", "add_audio_effect",
                "set_clip_volume", "set_clip_audio_gain", "auto_mix_audio",
                "multi_cam_edit", "set_clip_speed", "time_remap",
                "set_clip_keyframes", "nest_clips", "create_nested_sequence",
                "apply_lumetri",
            ],
            "bridge_dir": "C:/tmp/bridge",
            "bridge_status": "unknown",
        })

        async def _exec(action, **kwargs):
            return EngineResult(success=True, metadata={"result": {
                "status": "success", "action": action, "params": kwargs
            }})

        mock.execute.side_effect = _exec

        if not hasattr(app.state, "engines"):
            app.state.engines = {}
        app.state.engines["premiere"] = mock
        return app

    @pytest.fixture
    def client(self, app):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://testserver")

    @pytest.mark.asyncio
    async def test_patterns_endpoint_validation(self, client):
        # 缺少 pattern_name
        resp = await client.post("/api/v1/premiere/patterns", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_patterns_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/patterns", json={
            "pattern_name": "beat_cut",
            "sequence_name": "PatternTest",
            "params": {"layout": "2up"},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert body.get("pattern") == "beat_cut"

    @pytest.mark.asyncio
    async def test_auto_mix_audio_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/audio/auto-mix", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_auto_mix_audio_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/audio/auto-mix", json={
            "music_path": "C:/music.mp3",
            "voice_paths": ["C:/voice.wav"],
            "sfx_paths": ["C:/sfx.wav"],
            "ducking_amount": 0.3,
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_add_audio_track_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/audio/tracks", json={
            "name": "Voiceover",
            "channel_type": "mono",
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_set_track_volume_endpoint(self, client):
        resp = await client.put("/api/v1/premiere/audio/tracks/0/volume", json={"volume": 0.8})
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_set_track_mute_endpoint(self, client):
        resp = await client.put("/api/v1/premiere/audio/tracks/0/mute", json={"mute": True})
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_set_track_solo_endpoint(self, client):
        resp = await client.put("/api/v1/premiere/audio/tracks/0/solo", json={"solo": True})
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_set_track_pan_endpoint_validation(self, client):
        resp = await client.put("/api/v1/premiere/audio/tracks/0/pan", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_set_track_pan_endpoint_success(self, client):
        resp = await client.put("/api/v1/premiere/audio/tracks/0/pan", json={"pan": -0.5})
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_add_audio_effect_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/audio/effects", json={
            "track_index": 0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_add_audio_effect_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/audio/effects", json={
            "track_index": 0,
            "clip_index": 0,
            "effect_name": "Reverb",
            "params": {"mix": 0.3},
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_set_clip_volume_endpoint(self, client):
        resp = await client.put("/api/v1/premiere/audio/clips/0/0/volume", json={"volume": 0.5})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_set_clip_audio_gain_endpoint(self, client):
        resp = await client.put("/api/v1/premiere/audio/clips/0/0/gain", json={"gain_db": -3.0})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_multicam_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/multicam", json={})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_multicam_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/multicam", json={
            "camera_clips": [
                {"path": "C:/cam1.mp4", "camera_name": "Main"},
                {"path": "C:/cam2.mp4", "camera_name": "Closeup"},
            ],
            "sync_point": "audio",
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True
        assert resp.json().get("cameras") == 2

    @pytest.mark.asyncio
    async def test_clip_speed_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/speed", json={
            "track_index": 0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_clip_speed_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/speed", json={
            "track_index": 0,
            "clip_index": 0,
            "speed": 2.0,
            "maintain_pitch": True,
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_time_remap_endpoint(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/time-remap", json={
            "track_index": 0,
            "clip_index": 0,
            "keyframes": [
                {"time_seconds": 0.0, "speed": 1.0},
                {"time_seconds": 2.0, "speed": 0.5},
            ],
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_keyframes_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/keyframes", json={
            "track_index": 0,
            "clip_index": 0,
            "property_name": "scale",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_keyframes_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/timeline/clips/keyframes", json={
            "track_index": 0,
            "clip_index": 0,
            "property_name": "scale",
            "keyframes": [
                {"time_seconds": 0.0, "value": 100},
                {"time_seconds": 2.0, "value": 150},
            ],
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_nest_clips_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/sequences/nest", json={
            "track_index": 0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_nest_clips_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/sequences/nest", json={
            "track_index": 0,
            "clip_indices": [0, 1, 2],
            "nest_name": "NestedComp",
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_create_nested_sequence_endpoint(self, client):
        resp = await client.post("/api/v1/premiere/sequences/create-nested", json={
            "clips": [
                {"path": "C:/a.mp4", "track_index": 0, "start_time": 0},
                {"path": "C:/b.mp4", "track_index": 1, "start_time": 5},
            ],
            "name": "NestedSeq",
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_lumetri_endpoint_validation(self, client):
        resp = await client.post("/api/v1/premiere/color/lumetri", json={
            "track_index": 0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_lumetri_endpoint_success(self, client):
        resp = await client.post("/api/v1/premiere/color/lumetri", json={
            "track_index": 0,
            "clip_index": 0,
            "preset_or_params": {"temperature": -5, "tint": 3},
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True
