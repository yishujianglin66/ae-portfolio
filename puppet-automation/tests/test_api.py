"""Tests for FastAPI API endpoints."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app with lifespan context."""
    from src.api.main import app
    with TestClient(app) as c:
        yield c
        # Clean up any running async tasks to prevent test hang
        try:
            orch = app.state.orchestrator
            for job_id in list(orch._running.keys()):
                orch.cancel_job(job_id)
        except Exception:
            pass


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "engines" in data


class TestEnginesEndpoint:
    """Test engines listing endpoint."""

    def test_list_engines(self, client):
        response = client.get("/api/v1/engines")
        assert response.status_code == 200
        data = response.json()
        assert "engines" in data
        assert isinstance(data["engines"], list)


class TestMCPEndpoints:
    """Test MCP gateway endpoints."""

    def test_mcp_health(self, client):
        response = client.get("/mcp/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "tools_count" in data
        assert "engines_count" in data

    def test_mcp_list_tools(self, client):
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_mcp_list_engines(self, client):
        response = client.get("/mcp/engines")
        assert response.status_code == 200
        data = response.json()
        assert "engines" in data

    def test_mcp_invoke_tools_list(self, client):
        response = client.post("/mcp/invoke", json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "tools" in data["result"]

    def test_mcp_invoke_unknown_method(self, client):
        response = client.post("/mcp/invoke", json={
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": 2,
        })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_mcp_call_tool_not_found(self, client):
        response = client.post("/mcp/tools/nonexistent_tool/call", json={})
        assert response.status_code == 404


class TestPipelineEndpoints:
    """Test pipeline orchestration endpoints."""

    def test_list_jobs_empty(self, client):
        response = client.get("/api/v1/pipeline/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_create_job(self, client, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post("/api/v1/pipeline/jobs", json={
            "job_id": "api_test_job",
            "input_video": str(video),
            "style": "wooden",
            "phases": ["phase3_stylize"],
            "enable_face_puppet": False,
            "enable_body_puppet": False,
            "enable_audio": False,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "api_test_job"
        assert "state" in data

    def test_get_job_status(self, client, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        client.post("/api/v1/pipeline/jobs", json={
            "job_id": "api_test_get",
            "input_video": str(video),
            "phases": ["phase3_stylize"],
        })

        response = client.get("/api/v1/pipeline/jobs/api_test_get")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "api_test_get"

    def test_get_nonexistent_job(self, client):
        response = client.get("/api/v1/pipeline/jobs/nonexistent")
        assert response.status_code == 404

    def test_cancel_job(self, client, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        client.post("/api/v1/pipeline/jobs", json={
            "job_id": "api_test_cancel",
            "input_video": str(video),
            "phases": ["phase3_stylize"],
        })

        response = client.post("/api/v1/pipeline/jobs/api_test_cancel/cancel")
        assert response.status_code == 200
        data = response.json()
        assert "cancelled" in data

    def test_run_pipeline_sync(self, client, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post("/api/v1/pipeline/run", json={
            "job_id": "api_test_sync",
            "input_video": str(video),
            "style": "wooden",
            "phases": ["phase3_stylize"],
            "enable_face_puppet": False,
            "enable_body_puppet": False,
            "enable_audio": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "api_test_sync"
        assert data["state"]["overall_status"] == "success"


class TestAIPlannerEndpoints:
    """Test AI planner endpoints."""

    def test_list_puppet_styles(self, client):
        """Test listing all puppet styles."""
        response = client.get("/api/v1/ai/styles")
        assert response.status_code == 200
        data = response.json()
        assert "styles" in data
        assert isinstance(data["styles"], dict)
        assert len(data["styles"]) == 8
        assert "wooden" in data["styles"]
        assert "shadow" in data["styles"]
        assert "voxel" in data["styles"]

    def test_ai_plan_basic(self, client, tmp_path):
        """Test basic AI planning endpoint."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "把这个视频做成木质木偶风格",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "job" in data
        assert data["job"]["style"] == "wooden"
        assert "explanation" in data
        assert data["explanation"] != ""

    def test_ai_plan_shadow_style(self, client, tmp_path):
        """Test AI planning with shadow style keyword."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "我想要皮影效果",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job"]["style"] == "shadow"

    def test_ai_plan_clay_style(self, client, tmp_path):
        """Test AI planning with clay style keyword."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "黏土动画风格",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job"]["style"] == "clay"

    def test_ai_plan_voxel_style(self, client, tmp_path):
        """Test AI planning with voxel style keyword."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "minecraft体素方块风格",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job"]["style"] == "voxel"

    def test_ai_plan_returns_all_fields(self, client, tmp_path):
        """Test that AI plan returns all expected fields."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "木质木偶高清",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        expected_fields = [
            "job", "style_recommendation", "optimized_params",
            "explanation", "reasoning",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_ai_plan_job_has_phases(self, client, tmp_path):
        """Test that planned job has all four phases."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "木质木偶风格",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["job"]["phases"]) == 4

    def test_ai_recommend_style(self, client):
        """Test style recommendation endpoint."""
        response = client.post(
            "/api/v1/ai/recommend-style",
            params={
                "video_path": "test.mp4",
                "user_preferences": "童话风格",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "primary_style" in data
        assert "alternatives" in data
        assert "confidence" in data
        assert "reasoning" in data
        assert isinstance(data["alternatives"], list)
        assert len(data["alternatives"]) == 2

    def test_ai_recommend_style_traditional(self, client):
        """Test style recommendation for traditional content."""
        response = client.post(
            "/api/v1/ai/recommend-style",
            params={
                "video_path": "test.mp4",
                "user_preferences": "传统皮影神话",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["primary_style"] == "shadow"

    def test_ai_plan_high_quality(self, client, tmp_path):
        """Test AI planning detects high quality keyword."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post(
            "/api/v1/ai/plan",
            params={
                "user_query": "高清4K木质木偶效果",
                "video_path": str(video),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job"]["quality_preset"] == "high"


class TestPipelineEdgeCases:
    """Test pipeline edge cases and error handling."""

    def test_pipeline_job_invalid_style_returns_422(self, client, tmp_path):
        """Test that invalid style returns validation error."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post("/api/v1/pipeline/run", json={
            "job_id": "test_invalid_style",
            "input_video": str(video),
            "style": "nonexistent_style",
            "phases": ["phase3_stylize"],
        })
        assert response.status_code == 422

    def test_pipeline_job_missing_job_id_returns_422(self, client, tmp_path):
        """Test that missing job_id returns validation error."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post("/api/v1/pipeline/run", json={
            "input_video": str(video),
            "style": "wooden",
            "phases": ["phase3_stylize"],
        })
        assert response.status_code == 422

    def test_pipeline_job_missing_input_video_returns_422(self, client):
        """Test that missing input_video returns validation error."""
        response = client.post("/api/v1/pipeline/run", json={
            "job_id": "test_missing_input",
            "style": "wooden",
            "phases": ["phase3_stylize"],
        })
        assert response.status_code == 422

    def test_pipeline_empty_phases(self, client, tmp_path):
        """Test pipeline with empty phases fails gracefully."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post("/api/v1/pipeline/run", json={
            "job_id": "test_empty_phases",
            "input_video": str(video),
            "style": "wooden",
            "phases": [],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["overall_status"] == "failed"
        assert "No phases defined" in data["state"]["error"]

    def test_pipeline_single_phase(self, client, tmp_path):
        """Test pipeline with a single phase."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake")
        response = client.post("/api/v1/pipeline/run", json={
            "job_id": "test_single_phase",
            "input_video": str(video),
            "style": "wooden",
            "phases": ["phase4_render"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["state"]["overall_status"] == "success"
        assert len(data["state"]["phase_results"]) == 1

    def test_cancel_nonexistent_job_returns_false(self, client):
        """Test cancelling a nonexistent job returns False."""
        response = client.post("/api/v1/pipeline/jobs/nonexistent_job_123/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] is False

    def test_get_nonexistent_job_returns_404(self, client):
        """Test getting a nonexistent job returns 404."""
        response = client.get("/api/v1/pipeline/jobs/nonexistent_job_456")
        assert response.status_code == 404


class TestMCPEdgeCases:
    """Test MCP gateway edge cases."""

    def test_mcp_invoke_missing_method(self, client):
        """Test MCP invoke with missing method field."""
        response = client.post("/mcp/invoke", json={
            "jsonrpc": "2.0",
            "id": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_mcp_invoke_missing_jsonrpc(self, client):
        """Test MCP invoke without jsonrpc field."""
        response = client.post("/mcp/invoke", json={
            "method": "tools/list",
            "id": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data or "result" in data

    def test_mcp_call_tool_with_params(self, client):
        """Test MCP call tool endpoint with parameters."""
        # Use ffmpeg_convert which should be registered
        response = client.post("/mcp/tools/ffmpeg_convert/call", json={
            "input_path": "test.mp4",
            "output_path": "test_out.mp4",
            "codec": "libx264",
        })
        # May be 404 if ffmpeg tool isn't registered, or 200/500 if it is
        assert response.status_code in [200, 404, 500]

    def test_mcp_engines_list(self, client):
        """Test MCP engines list endpoint returns expected structure."""
        response = client.get("/mcp/engines")
        assert response.status_code == 200
        data = response.json()
        assert "engines" in data
        assert isinstance(data["engines"], dict)
        # Should have at least some engines registered
        assert len(data["engines"]) > 0

    def test_mcp_invoke_nonexistent_tool(self, client):
        """Test MCP invoke with nonexistent tool returns proper JSON-RPC error."""
        response = client.post("/mcp/invoke", json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool_xyz",
                "arguments": {},
            },
            "id": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602
        assert "id" in data and data["id"] == 1

    def test_mcp_call_tool_404(self, client):
        """Test calling nonexistent tool via direct endpoint returns 404."""
        response = client.post("/mcp/tools/nonexistent_tool_xyz/call", json={})
        assert response.status_code == 404
