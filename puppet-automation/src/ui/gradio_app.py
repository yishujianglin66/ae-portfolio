"""Gradio frontend Dashboard for Puppet Video Automation Pipeline.

Features:
- Video upload with preview
- Style selection (8 puppet styles + ComfyUI workflows)
- Pipeline execution with real-time progress
- Result display and download
- Workflow management (list, upload, delete)
- ComfyUI server status
- Audio transcription with speaker diarization
- Video scene detection and keyframe extraction
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import gradio as gr
import httpx

# API Configuration
API_BASE_URL = "http://127.0.0.1:8000"


# ============================================================
# API Client
# ============================================================

class APIClient:
    """HTTP client for Puppet Automation Pipeline API."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def health(self) -> dict:
        resp = await self._client.get(f"{self.base_url}/health")
        return resp.json()

    async def list_styles(self) -> dict:
        resp = await self._client.get(f"{self.base_url}/api/v1/ai/styles")
        return resp.json()

    async def list_workflows(self, category: str | None = None) -> dict:
        params = {"category": category} if category else {}
        resp = await self._client.get(f"{self.base_url}/api/v1/comfyui/workflows", params=params)
        return resp.json()

    async def comfyui_status(self) -> dict:
        try:
            resp = await self._client.get(f"{self.base_url}/api/v1/comfyui/status")
            return resp.json()
        except Exception:
            return {"available": False, "error": "API not reachable"}

    async def execute_workflow(self, workflow_name: str, params: dict | None = None) -> dict:
        data = {"workflow_name": workflow_name}
        if params:
            data["params"] = params
        resp = await self._client.post(f"{self.base_url}/api/v1/comfyui/execute", json=data)
        return resp.json()

    async def create_pipeline_job(self, job: dict) -> dict:
        resp = await self._client.post(f"{self.base_url}/api/v1/pipeline/jobs", json=job)
        return resp.json()

    async def get_pipeline_job(self, job_id: str) -> dict:
        resp = await self._client.get(f"{self.base_url}/api/v1/pipeline/jobs/{job_id}")
        return resp.json()

    async def transcribe_audio(self, file_path: str, detect_speakers: bool = False) -> dict:
        with open(file_path, "rb") as f:
            resp = await self._client.post(
                f"{self.base_url}/api/v1/audio/transcribe",
                files={"file": (Path(file_path).name, f, "audio/wav")},
                data={"detect_speakers": str(detect_speakers).lower()},
            )
        return resp.json()

    async def detect_scenes(self, file_path: str, threshold: float = 30.0) -> dict:
        with open(file_path, "rb") as f:
            resp = await self._client.post(
                f"{self.base_url}/api/v1/video/detect-scenes",
                files={"file": (Path(file_path).name, f, "video/mp4")},
                data={"threshold": str(threshold)},
            )
        return resp.json()


# ============================================================
# UI Components
# ============================================================

async def fetch_styles() -> dict:
    """Fetch available puppet styles from API."""
    async with APIClient() as client:
        try:
            return await client.list_styles()
        except Exception:
            return {"styles": {}}


async def fetch_workflows() -> list:
    """Fetch available ComfyUI workflows."""
    async with APIClient() as client:
        try:
            result = await client.list_workflows()
            return result.get("workflows", [])
        except Exception:
            return []


async def fetch_comfyui_status() -> dict:
    """Fetch ComfyUI server status."""
    async with APIClient() as client:
        return await client.comfyui_status()


# ============================================================
# Main Interface
# ============================================================

with gr.Blocks(title="Puppet Video Automation Pipeline") as demo:
    gr.Markdown("# 🎬 Puppet Video Automation Pipeline")
    gr.Markdown("Automate puppet-style video production with AI-powered workflows")

    # ============================================================
    # Tabs
    # ============================================================
    with gr.Tabs():
        # ============================================================
        # Tab 1: Quick Style Transfer
        # ============================================================
        with gr.Tab("Quick Style Transfer"):
            with gr.Row():
                with gr.Column(scale=1):
                    video_input = gr.Video(label="Upload Video", format="mp4")
                    image_input = gr.Image(label="Upload Image", type="filepath")

                with gr.Column(scale=1):
                    gr.Markdown("### Select Style")
                    style_choice = gr.Radio(
                        label="Puppet Style",
                        choices=[],
                        value=None,
                    )
                    workflow_choice = gr.Radio(
                        label="ComfyUI Workflow",
                        choices=[],
                        value=None,
                        visible=False,
                    )
                    use_comfyui = gr.Checkbox(
                        label="Use ComfyUI for AI Stylization",
                        value=False,
                    )

                    quality_preset = gr.Radio(
                        label="Quality Preset",
                        choices=["fast", "standard", "high"],
                        value="standard",
                    )

                    with gr.Row():
                        execute_btn = gr.Button("Execute", variant="primary")
                        cancel_btn = gr.Button("Cancel", variant="secondary")

            with gr.Row():
                with gr.Column(scale=1):
                    progress = gr.Progress()
                    status_text = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=3,
                    )

                with gr.Column(scale=1):
                    result_output = gr.Video(
                        label="Result",
                        interactive=False,
                    )
                    result_image = gr.Image(
                        label="Preview",
                        interactive=False,
                        visible=False,
                    )

        # ============================================================
        # Tab 2: Audio Analysis
        # ============================================================
        with gr.Tab("Audio Analysis"):
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(label="Upload Audio", type="filepath")
                    detect_speakers_check = gr.Checkbox(
                        label="Detect Speakers (Multi-speaker diarization)",
                        value=False,
                    )
                    transcribe_btn = gr.Button("Transcribe", variant="primary")

                with gr.Column(scale=2):
                    gr.Markdown("### Transcription Result")
                    transcription_text = gr.Textbox(
                        label="Full Transcript",
                        interactive=False,
                        lines=8,
                    )
                    transcription_json = gr.JSON(label="Detailed Results")

            with gr.Row():
                speakers_info = gr.Dataframe(
                    label="Speaker Segments",
                    headers=["Speaker", "Start Time", "End Time"],
                    datatype=["str", "number", "number"],
                    interactive=False,
                )

        # ============================================================
        # Tab 3: Scene Detection
        # ============================================================
        with gr.Tab("Scene Detection"):
            with gr.Row():
                with gr.Column(scale=1):
                    scene_video_input = gr.Video(label="Upload Video", format="mp4")
                    scene_threshold = gr.Slider(
                        label="Scene Detection Threshold",
                        minimum=10,
                        maximum=100,
                        value=30,
                        step=5,
                    )
                    detect_scenes_btn = gr.Button("Detect Scenes", variant="primary")

                with gr.Column(scale=2):
                    gr.Markdown("### Scene List")
                    scenes_table = gr.Dataframe(
                        label="Detected Scenes",
                        headers=["Scene ID", "Start Frame", "End Frame", "Start Time", "End Time", "Duration"],
                        datatype=["number", "number", "number", "number", "number", "number"],
                        interactive=False,
                    )

            with gr.Row():
                scene_summary = gr.Textbox(
                    label="Summary",
                    interactive=False,
                    lines=2,
                )

        # ============================================================
        # Tab 4: Workflow Manager
        # ============================================================
        with gr.Tab("Workflow Manager"):
            with gr.Row():
                with gr.Column(scale=1):
                    workflows_list = gr.Dataframe(
                        label="Available Workflows",
                        headers=["Name", "Display Name", "Category", "Style", "Built-in"],
                        datatype=["str", "str", "str", "str", "bool"],
                        interactive=False,
                    )
                    refresh_workflows_btn = gr.Button("Refresh Workflows")

                with gr.Column(scale=1):
                    gr.Markdown("### Upload Custom Workflow")
                    wf_name = gr.Textbox(label="Workflow Name")
                    wf_display_name = gr.Textbox(label="Display Name")
                    wf_description = gr.Textbox(label="Description", lines=2)
                    wf_category = gr.Dropdown(
                        label="Category",
                        choices=["user", "puppet", "utility"],
                        value="user",
                    )
                    wf_style = gr.Textbox(label="Style (optional)")
                    wf_json = gr.Textbox(
                        label="Workflow JSON",
                        lines=10,
                        placeholder='{"1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}}}',
                    )
                    upload_wf_btn = gr.Button("Upload Workflow", variant="primary")
                    delete_wf_btn = gr.Button("Delete Selected", variant="stop")

            workflow_detail = gr.JSON(label="Workflow Details")

        # ============================================================
        # Tab 5: System Status
        # ============================================================
        with gr.Tab("System Status"):
            with gr.Row():
                with gr.Column(scale=1):
                    comfyui_status_card = gr.JSON(label="ComfyUI Server")
                    comfyui_status_btn = gr.Button("Check ComfyUI Status")

                with gr.Column(scale=1):
                    api_status_card = gr.JSON(label="API Server")
                    api_status_btn = gr.Button("Check API Status")

            with gr.Row():
                engines_status = gr.Dataframe(
                    label="Engine Status",
                    headers=["Name", "Executable/URL", "Available"],
                    datatype=["str", "str", "bool"],
                )
                refresh_engines_btn = gr.Button("Refresh Engines")

    # ============================================================
    # Event Handlers
    # ============================================================

    async def update_style_choices():
        styles = await fetch_styles()
        style_items = [(k, v) for k, v in styles.get("styles", {}).items()]
        return gr.update(choices=style_items)

    async def update_workflow_choices():
        workflows = await fetch_workflows()
        workflow_items = [
            (w["name"], w["display_name"])
            for w in workflows
            if not w["builtin"] or w["category"] == "puppet"
        ]
        return gr.update(choices=workflow_items)

    def toggle_comfyui(use_comfy):
        return gr.update(visible=use_comfy)

    async def on_execute(
        video, image, style, workflow, use_comfy, quality, progress=gr.Progress()
    ):
        status_text.value = "Starting..."
        progress(0, desc="Initializing")

        if use_comfy and workflow:
            status_text.value = f"Running ComfyUI workflow: {workflow}..."
            progress(20, desc="Executing ComfyUI workflow")
            async with APIClient() as client:
                params = {}
                if image:
                    params = {"1": {"image": Path(image).name}}
                result = await client.execute_workflow(workflow, params)

            if result.get("success"):
                progress(100, desc="Complete")
                status_text.value = f"✅ Success! Output: {result.get('output_path')}"
                output_path = result.get("output_path")
                if output_path and Path(output_path).exists():
                    return gr.update(value=output_path)
                else:
                    return gr.update(value=None)
            else:
                status_text.value = f"❌ Failed: {result.get('error')}"
                return gr.update(value=None)
        elif style:
            status_text.value = f"Applying {style} style..."
            progress(50, desc="Processing")
            await asyncio.sleep(2)
            progress(100, desc="Complete")
            status_text.value = f"✅ Style '{style}' applied successfully (simulated)"
            return gr.update(value=None)
        else:
            status_text.value = "❌ Please select a style or workflow"
            return gr.update(value=None)

    async def on_transcribe(audio_file, detect_speakers, progress=gr.Progress()):
        if not audio_file:
            return gr.update(value=""), gr.update(value={}), gr.update(value=[])

        progress(0, desc="Loading audio...")
        async with APIClient() as client:
            progress(20, desc="Transcribing...")
            result = await client.transcribe_audio(audio_file, detect_speakers)

        if result.get("success"):
            progress(100, desc="Complete")
            text = result.get("text", "")
            speaker_segments = []
            if "speaker_segments" in result:
                for seg in result["speaker_segments"]:
                    speaker_segments.append([
                        seg.get("speaker", "Unknown"),
                        seg.get("start", 0),
                        seg.get("end", 0),
                    ])
            return text, result, speaker_segments
        else:
            error = result.get("error", "Unknown error")
            return f"❌ Failed: {error}", result, []

    async def on_detect_scenes(video_file, threshold, progress=gr.Progress()):
        if not video_file:
            return gr.update(value=[]), gr.update(value="")

        progress(0, desc="Loading video...")
        async with APIClient() as client:
            progress(30, desc="Analyzing scenes...")
            result = await client.detect_scenes(video_file, threshold)

        if result.get("success"):
            progress(100, desc="Complete")
            scenes = result.get("scenes", [])
            table_data = []
            for scene in scenes:
                table_data.append([
                    scene.get("id"),
                    scene.get("start_frame"),
                    scene.get("end_frame"),
                    scene.get("start_time"),
                    scene.get("end_time"),
                    scene.get("duration"),
                ])
            summary = f"✅ Found {result.get('total_scenes', 0)} scenes using {result.get('method', 'unknown')} method"
            return table_data, summary
        else:
            error = result.get("error", "Unknown error")
            return [], f"❌ Failed: {error}"

    async def load_workflows():
        workflows = await fetch_workflows()
        data = [
            [
                w["name"],
                w["display_name"],
                w["category"],
                w["style"] or "-",
                w["builtin"],
            ]
            for w in workflows
        ]
        return gr.update(value=data)

    async def upload_workflow(name, display_name, description, category, style, wf_json):
        if not name or not wf_json:
            return "❌ Name and workflow JSON are required"
        try:
            workflow = json.loads(wf_json)
        except json.JSONDecodeError:
            return "❌ Invalid JSON format"

        async with APIClient() as client:
            resp = await client._client.post(
                f"{client.base_url}/api/v1/comfyui/workflows",
                json={
                    "name": name,
                    "display_name": display_name or name,
                    "description": description,
                    "category": category,
                    "style": style,
                    "workflow": workflow,
                },
            )
            if resp.status_code == 200:
                return f"✅ Workflow '{name}' uploaded successfully"
            else:
                return f"❌ Failed: {resp.text}"

    async def check_comfyui_status():
        status = await fetch_comfyui_status()
        return gr.update(value=status)

    async def check_api_status():
        async with APIClient() as client:
            try:
                return gr.update(value=await client.health())
            except Exception as e:
                return gr.update(value={"status": "unavailable", "error": str(e)})

    async def load_engines():
        async with APIClient() as client:
            try:
                resp = await client._client.get(f"{client.base_url}/api/v1/engines")
                data = resp.json()
                rows = [
                    [
                        e["name"],
                        e.get("executable") or e.get("url") or "-",
                        e.get("available", False) or "N/A",
                    ]
                    for e in data.get("engines", [])
                ]
                return gr.update(value=rows)
            except Exception:
                return gr.update(value=[])

    # ============================================================
    # Bind Events
    # ============================================================
    demo.load(update_style_choices, None, style_choice)
    demo.load(update_workflow_choices, None, workflow_choice)
    demo.load(load_workflows, None, workflows_list)
    demo.load(check_comfyui_status, None, comfyui_status_card)
    demo.load(check_api_status, None, api_status_card)
    demo.load(load_engines, None, engines_status)

    use_comfyui.change(toggle_comfyui, use_comfyui, workflow_choice)

    execute_btn.click(
        on_execute,
        inputs=[video_input, image_input, style_choice, workflow_choice, use_comfyui, quality_preset],
        outputs=[result_output],
    )

    transcribe_btn.click(
        on_transcribe,
        inputs=[audio_input, detect_speakers_check],
        outputs=[transcription_text, transcription_json, speakers_info],
    )

    detect_scenes_btn.click(
        on_detect_scenes,
        inputs=[scene_video_input, scene_threshold],
        outputs=[scenes_table, scene_summary],
    )

    refresh_workflows_btn.click(load_workflows, None, workflows_list)
    upload_wf_btn.click(
        upload_workflow,
        inputs=[wf_name, wf_display_name, wf_description, wf_category, wf_style, wf_json],
        outputs=[status_text],
    )

    comfyui_status_btn.click(check_comfyui_status, None, comfyui_status_card)
    api_status_btn.click(check_api_status, None, api_status_card)
    refresh_engines_btn.click(load_engines, None, engines_status)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )