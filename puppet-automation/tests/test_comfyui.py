"""Tests for ComfyUI engine and workflow manager integration.

Uses httpx.MockTransport to simulate ComfyUI server responses
so tests don't require a running ComfyUI instance.
"""

import json
import pytest
import httpx
from pathlib import Path

from src.engines.comfyui import ComfyUIEngine, WorkflowManager, WorkflowInfo
from src.engines.base import EngineResult


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_workflow() -> dict:
    """A simple test workflow."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "test.png"},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "output"},
        },
    }


@pytest.fixture
def engine_with_mock():
    """Create a ComfyUIEngine with a mock transport.

    Returns (engine, mock_handler) where mock_handler is a dict
    that can be populated with responses keyed by path.
    """
    responses: dict[str, tuple[int, dict | bytes, str]] = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        # Strip query params for matching
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

    transport = httpx.MockTransport(mock_handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    engine = ComfyUIEngine(base_url="http://test", timeout=10)
    engine._client = client
    return engine, responses


# ============================================================
# ComfyUIEngine tests
# ============================================================

class TestComfyUIEngine:

    @pytest.mark.asyncio
    async def test_is_available_true(self, engine_with_mock):
        engine, responses = engine_with_mock
        responses["/system_stats"] = (200, {"system": "ok"}, "application/json")
        result = await engine.is_available(force_check=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_false(self, engine_with_mock):
        engine, responses = engine_with_mock
        responses["/system_stats"] = (500, {}, "application/json")
        result = await engine.is_available(force_check=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_cached(self, engine_with_mock):
        engine, responses = engine_with_mock
        responses["/system_stats"] = (200, {"system": "ok"}, "application/json")
        await engine.is_available(force_check=True)
        # Second call should use cache (we change response but it shouldn't matter)
        responses["/system_stats"] = (500, {}, "application/json")
        result = await engine.is_available(force_check=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_system_stats(self, engine_with_mock):
        engine, responses = engine_with_mock
        responses["/system_stats"] = (
            200,
            {"system": {"os": "windows"}, "devices": [{"name": "NVIDIA"}]},
            "application/json",
        )
        stats = await engine.get_system_stats()
        assert "system" in stats
        assert "devices" in stats

    @pytest.mark.asyncio
    async def test_get_queue(self, engine_with_mock):
        engine, responses = engine_with_mock
        responses["/queue"] = (
            200,
            {"queue_running": [], "queue_pending": []},
            "application/json",
        )
        queue = await engine.get_queue()
        assert "queue_running" in queue

    @pytest.mark.asyncio
    async def test_queue_prompt(self, engine_with_mock, sample_workflow):
        engine, responses = engine_with_mock
        responses["/prompt"] = (
            200,
            {"prompt_id": "test_prompt_123", "number": 0},
            "application/json",
        )
        prompt_id = await engine.queue_prompt(sample_workflow)
        assert prompt_id == "test_prompt_123"

    @pytest.mark.asyncio
    async def test_run_workflow_success(self, engine_with_mock, sample_workflow, tmp_path):
        engine, responses = engine_with_mock

        responses["/system_stats"] = (200, {"system": "ok"}, "application/json")
        responses["/prompt"] = (
            200,
            {"prompt_id": "wf_001"},
            "application/json",
        )
        responses["/history/wf_001"] = (
            200,
            {
                "wf_001": {
                    "status": {"completed": True},
                    "outputs": {
                        "2": {
                            "images": [
                                {"filename": "output_00001_.png", "subfolder": "", "type": "output"}
                            ]
                        }
                    },
                }
            },
            "application/json",
        )
        # Simulate image download
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        responses["/view"] = (200, fake_png, "image/png")

        output_dir = tmp_path / "output"
        result = await engine.run_workflow(sample_workflow, output_dir=output_dir)
        assert result.success is True
        assert result.output_path is not None
        assert result.metadata["prompt_id"] == "wf_001"
        assert result.metadata["output_count"] == 1
        # Verify file was downloaded
        assert Path(result.output_path).exists()

    @pytest.mark.asyncio
    async def test_run_workflow_server_unavailable(self, engine_with_mock, sample_workflow):
        engine, responses = engine_with_mock
        responses["/system_stats"] = (500, {}, "application/json")
        result = await engine.run_workflow(sample_workflow)
        assert result.success is False
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_set_workflow_input(self, sample_workflow):
        modified = ComfyUIEngine.set_workflow_input(
            sample_workflow, "1", image="new_image.png"
        )
        assert modified["1"]["inputs"]["image"] == "new_image.png"
        # Original should not be modified
        assert sample_workflow["1"]["inputs"]["image"] == "test.png"

    @pytest.mark.asyncio
    async def test_find_node_by_class(self, sample_workflow):
        node_id = ComfyUIEngine.find_node_by_class(sample_workflow, "LoadImage")
        assert node_id == "1"
        node_id = ComfyUIEngine.find_node_by_class(sample_workflow, "SaveImage")
        assert node_id == "2"
        node_id = ComfyUIEngine.find_node_by_class(sample_workflow, "NonExistent")
        assert node_id is None


# ============================================================
# WorkflowManager tests
# ============================================================

class TestWorkflowManager:

    def test_init(self, tmp_path):
        wf_dir = tmp_path / "workflows"
        wf_mgr = WorkflowManager(workflows_dir=wf_dir)
        assert wf_mgr.workflows_dir == wf_dir
        assert wf_dir.exists()

    def test_list_builtin_workflows(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        workflows = wf_mgr.list_workflows()
        assert len(workflows) >= 9  # 1 utility + 8 puppet styles
        names = [w.name for w in workflows]
        assert "simple_passthrough" in names
        assert "wooden_puppet" in names
        assert "stop_motion_puppet" in names
        assert "clay_puppet" in names
        assert "shadow_puppet" in names
        assert "paper_puppet" in names
        assert "voxel_puppet" in names
        assert "handle_puppet" in names
        assert "miniature_puppet" in names

    def test_list_by_category(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        puppet_wfs = wf_mgr.list_workflows(category="puppet")
        assert len(puppet_wfs) == 8
        assert all(w.category == "puppet" for w in puppet_wfs)

        utility_wfs = wf_mgr.list_workflows(category="utility")
        assert len(utility_wfs) == 1
        assert utility_wfs[0].name == "simple_passthrough"

    def test_get_builtin_workflow(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        wf = wf_mgr.get_workflow("wooden_puppet")
        assert wf is not None
        assert "1" in wf
        assert wf["1"]["class_type"] == "LoadImage"

    def test_get_nonexistent_workflow(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        wf = wf_mgr.get_workflow("nonexistent")
        assert wf is None

    def test_save_workflow(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        test_wf = {
            "1": {"class_type": "TestNode", "inputs": {}}
        }
        path = wf_mgr.save_workflow(
            "test_workflow",
            test_wf,
            metadata={"display_name": "Test Workflow", "description": "A test"},
        )
        assert path.exists()
        # Verify we can read it back
        loaded = wf_mgr.get_workflow("test_workflow")
        assert loaded is not None
        assert "1" in loaded

    def test_delete_workflow(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        test_wf = {"1": {"class_type": "Test", "inputs": {}}}
        wf_mgr.save_workflow("to_delete", test_wf)
        assert wf_mgr.get_workflow("to_delete") is not None

        result = wf_mgr.delete_workflow("to_delete")
        assert result is True
        assert wf_mgr.get_workflow("to_delete") is None

    def test_delete_nonexistent_workflow(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path)
        result = wf_mgr.delete_workflow("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_workflow_no_engine(self, tmp_path):
        wf_mgr = WorkflowManager(workflows_dir=tmp_path, engine=None)
        result = await wf_mgr.execute_workflow("simple_passthrough")
        assert result.success is False
        assert "No ComfyUI engine" in result.error

    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self, engine_with_mock, tmp_path):
        engine, _ = engine_with_mock
        wf_mgr = WorkflowManager(workflows_dir=tmp_path, engine=engine)
        result = await wf_mgr.execute_workflow("nonexistent_workflow")
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_workflow_with_params(self, engine_with_mock, tmp_path, sample_workflow):
        engine, responses = engine_with_mock
        responses["/system_stats"] = (200, {"system": "ok"}, "application/json")
        responses["/prompt"] = (200, {"prompt_id": "param_test"}, "application/json")
        responses["/history/param_test"] = (
            200,
            {"param_test": {"status": {"completed": True}, "outputs": {}}},
            "application/json",
        )

        wf_mgr = WorkflowManager(workflows_dir=tmp_path, engine=engine)
        # Save a workflow we can execute
        wf_mgr.save_workflow("test_wf", sample_workflow)

        result = await wf_mgr.execute_workflow(
            "test_wf",
            params={"1": {"image": "custom.png"}},
            output_dir=tmp_path / "out",
        )
        # Should succeed (empty outputs but completed)
        assert result.success is True
        assert result.metadata["prompt_id"] == "param_test"


# ============================================================
# WorkflowInfo tests
# ============================================================

class TestWorkflowInfo:

    def test_workflow_info_creation(self):
        info = WorkflowInfo(
            name="test_wf",
            display_name="Test Workflow",
            description="A test workflow",
            category="puppet",
            style="wooden",
            builtin=True,
        )
        assert info.name == "test_wf"
        assert info.display_name == "Test Workflow"
        assert info.category == "puppet"
        assert info.style == "wooden"
        assert info.builtin is True
