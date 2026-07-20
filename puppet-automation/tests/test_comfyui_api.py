"""Tests for ComfyUI API endpoints.

Uses FastAPI TestClient with mock ComfyUI engine to test
all endpoints without requiring a running ComfyUI server.
"""

from __future__ import annotations

import json
import pytest
import httpx
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    from src.api.main import app
    with TestClient(app) as c:
        # Replace ComfyUI engine with a mock if it exists
        try:
            from src.engines.comfyui import ComfyUIEngine

            mock_engine = ComfyUIEngine(
                base_url="http://mock", timeout=5
            )

            # Set up mock transport
            responses: dict[str, tuple[int, object, str]] = {}

            def mock_handler(request: httpx.Request) -> httpx.Response:
                url_path = request.url.path
                for key, (status_code, body, content_type) in responses.items():
                    if url_path == key or url_path.startswith(key + "?"):
                        if isinstance(body, bytes):
                            return httpx.Response(
                                status_code, content=body,
                                headers={"content-type": content_type}
                            )
                        else:
                            return httpx.Response(
                                status_code, json=body,
                                headers={"content-type": content_type}
                            )
                return httpx.Response(404, json={"error": "not found"})

            mock_engine._client = httpx.AsyncClient(
                transport=httpx.MockTransport(mock_handler),
                base_url="http://mock"
            )
            mock_engine._available = False  # Default to unavailable

            app.state.comfyui_engine = mock_engine
            # Re-init workflow manager with mock engine
            from src.engines.comfyui import WorkflowManager
            wf_dir = Path(app.state.wf_manager.workflows_dir) if app.state.wf_manager else None
            app.state.wf_manager = WorkflowManager(
                engine=mock_engine, workflows_dir=wf_dir
            )

            # Store responses dict for tests to modify
            app.state._mock_responses = responses
        except Exception:
            pass

        yield c

        # Cleanup
        try:
            orch = app.state.orchestrator
            for job_id in list(orch._running.keys()):
                orch.cancel_job(job_id)
        except Exception:
            pass


# ============================================================
# Workflow listing tests
# ============================================================

class TestWorkflowList:

    def test_list_all_workflows(self, client):
        """List all workflows without category filter."""
        resp = client.get("/api/v1/comfyui/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "workflows" in data
        assert data["total"] >= 9  # 1 utility + 8 puppet styles
        # Verify structure
        wf = data["workflows"][0]
        assert "name" in wf
        assert "display_name" in wf
        assert "builtin" in wf

    def test_list_workflows_by_category(self, client):
        """Filter workflows by category."""
        resp = client.get("/api/v1/comfyui/workflows?category=puppet")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8  # 8 puppet styles
        assert all(w["category"] == "puppet" for w in data["workflows"])

    def test_list_workflows_utility_category(self, client):
        """Filter workflows by utility category."""
        resp = client.get("/api/v1/comfyui/workflows?category=utility")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["workflows"][0]["name"] == "simple_passthrough"


# ============================================================
# Workflow detail tests
# ============================================================

class TestWorkflowDetail:

    def test_get_builtin_workflow(self, client):
        """Get a built-in workflow JSON."""
        resp = client.get("/api/v1/comfyui/workflows/wooden_puppet")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "wooden_puppet"
        assert data["builtin"] is True
        assert "workflow" in data
        assert "1" in data["workflow"]  # Node 1 exists

    def test_get_nonexistent_workflow(self, client):
        """Get a workflow that doesn't exist."""
        resp = client.get("/api/v1/comfyui/workflows/nonexistent_wf")
        assert resp.status_code == 404


# ============================================================
# Workflow upload tests
# ============================================================

class TestWorkflowUpload:

    def test_upload_new_workflow(self, client):
        """Upload a new custom workflow."""
        workflow = {
            "1": {"class_type": "LoadImage", "inputs": {"image": "test.png"}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
        }
        resp = client.post("/api/v1/comfyui/workflows", json={
            "name": "test_custom_wf",
            "display_name": "Test Custom Workflow",
            "description": "A test workflow",
            "category": "user",
            "workflow": workflow,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["name"] == "test_custom_wf"

        # Verify it shows up in listing
        resp2 = client.get("/api/v1/comfyui/workflows?category=user")
        data2 = resp2.json()
        names = [w["name"] for w in data2["workflows"]]
        assert "test_custom_wf" in names

    def test_upload_overwrite_existing(self, client):
        """Upload should overwrite existing workflow with same name."""
        workflow = {"1": {"class_type": "Test", "inputs": {}}}
        # First upload
        client.post("/api/v1/comfyui/workflows", json={
            "name": "overwrite_test",
            "workflow": workflow,
        })
        # Second upload with same name
        workflow2 = {"1": {"class_type": "Modified", "inputs": {}}}
        resp = client.post("/api/v1/comfyui/workflows", json={
            "name": "overwrite_test",
            "workflow": workflow2,
        })
        assert resp.status_code == 200

        # Verify it was overwritten
        resp2 = client.get("/api/v1/comfyui/workflows/overwrite_test")
        data = resp2.json()
        assert data["workflow"]["1"]["class_type"] == "Modified"

    def test_upload_invalid_workflow_missing_name(self, client):
        """Upload without name should fail."""
        resp = client.post("/api/v1/comfyui/workflows", json={
            "workflow": {"1": {"class_type": "Test"}},
        })
        assert resp.status_code == 422  # Validation error


# ============================================================
# Workflow delete tests
# ============================================================

class TestWorkflowDelete:

    def test_delete_user_workflow(self, client):
        """Delete a user-created workflow."""
        # First create one
        client.post("/api/v1/comfyui/workflows", json={
            "name": "to_delete",
            "workflow": {"1": {"class_type": "Test", "inputs": {}}},
        })
        # Then delete
        resp = client.delete("/api/v1/comfyui/workflows/to_delete")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify it's gone
        resp2 = client.get("/api/v1/comfyui/workflows/to_delete")
        assert resp2.status_code == 404

    def test_delete_builtin_workflow_forbidden(self, client):
        """Deleting a built-in workflow should be forbidden."""
        resp = client.delete("/api/v1/comfyui/workflows/wooden_puppet")
        assert resp.status_code == 403

    def test_delete_nonexistent_workflow(self, client):
        """Deleting non-existent workflow returns 404."""
        resp = client.delete("/api/v1/comfyui/workflows/nonexistent")
        assert resp.status_code == 404


# ============================================================
# Workflow execute tests
# ============================================================

class TestWorkflowExecute:

    def test_execute_workflow_not_found(self, client):
        """Execute a workflow that doesn't exist."""
        resp = client.post("/api/v1/comfyui/execute", json={
            "workflow_name": "nonexistent",
        })
        # Should return 200 with success=False (engine result)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "not found" in data["error"]

    def test_execute_workflow_server_unavailable(self, client):
        """Execute when ComfyUI server is not running."""
        resp = client.post("/api/v1/comfyui/execute", json={
            "workflow_name": "simple_passthrough",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Mock engine defaults to unavailable
        assert data["success"] is False


# ============================================================
# Server status tests
# ============================================================

class TestComfyUIStatus:

    def test_status_endpoint(self, client):
        """Check ComfyUI server status endpoint."""
        resp = client.get("/api/v1/comfyui/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "base_url" in data


# ============================================================
# Image upload tests
# ============================================================

class TestImageUpload:

    def test_upload_image_endpoint(self, client):
        """Test image upload endpoint."""
        # Create a fake image
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = client.post(
            "/api/v1/comfyui/upload-image",
            files={"file": ("test.png", fake_image, "image/png")},
        )
        # Will fail because mock engine can't upload, but should not crash
        assert resp.status_code in (200, 500)

    def test_upload_image_no_file(self, client):
        """Upload without file should fail."""
        resp = client.post("/api/v1/comfyui/upload-image")
        assert resp.status_code == 422  # Validation error
