"""
integrations/comfyui_handdrawn_adapter.py — ComfyUI 手绘风格化适配器
====================================================================

手书动画集成方案 P1-4: 基于 ComfyUI 的高质量手绘风格化管线。

与 core/handdrawn_styler.py (OpenCV 快速版) 的关系:
  - HanddrawnStyler: CPU 实时、零依赖、质量一般 (降级方案)
  - HanddrawnComfyUIAdapter: GPU 扩散模型重绘、质量高 (主方案)
  - HanddrawnPipeline 自动检测: ComfyUI 可用则优先, 否则降级 OpenCV

工作流模板: data/comfyui_workflows/handdrawn_style_transfer.json
  (img2img: LoadImage → VAEEncode → KSampler → VAEDecode → SaveImage)

用法:
    from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
    adapter = HanddrawnComfyUIAdapter()
    result = adapter.execute("stylize_image", {
        "input_image": "frame_001.png",
        "output_path": "frame_001_sketch.png",
        "style": "pencil_sketch",
    })
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import shutil
import time
import uuid
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_TEMPLATE = (
    _PROJECT_ROOT / "data" / "comfyui_workflows" / "handdrawn_style_transfer.json"
)


class HanddrawnComfyUIAdapter:
    """ComfyUI 手绘风格化适配器

    封装 ComfyUI img2img 风格化管线，提供:
    1. stylize_image: 单张图像风格化
    2. batch_stylize: 批量风格化 (关键帧序列)
    3. build_workflow: 仅生成工作流 JSON (dry-run)
    4. check_environment: 环境检查 (服务端 + 模型)
    5. list_styles: 支持的风格列表
    """

    TOOL_NAME = "comfyui_handdrawn"
    SUPPORTED_OPERATIONS = [
        "stylize_image",
        "batch_stylize",
        "build_workflow",
        "check_environment",
        "list_styles",
    ]

    # 六种风格对应的扩散模型提示词 (与 HanddrawnStyler 风格对齐)
    STYLE_PROMPTS = {
        "pencil_sketch": (
            "pencil sketch drawing, graphite strokes, hand-drawn line art, "
            "cross-hatching shading, sketchbook style, monochrome"
        ),
        "ink_drawing": (
            "ink drawing, black ink on white paper, bold brush strokes, "
            "high contrast line art, sumi-e influence, hand-drawn"
        ),
        "watercolor": (
            "watercolor painting, soft bleeding edges, translucent washes, "
            "paper texture, hand-painted, artistic illustration"
        ),
        "comic": (
            "comic book style, bold ink outlines, halftone shading, "
            "cel shading, manga panel aesthetic, vibrant flat colors"
        ),
        "crayon": (
            "crayon drawing, childlike hand-drawn style, waxy texture, "
            "rough strokes, colored pencils on paper"
        ),
        "doodle": (
            "doodle art, playful hand-drawn scribbles, simple lines, "
            "sketchy marker style, casual illustration"
        ),
    }

    NEGATIVE_PROMPT = (
        "photorealistic, 3d render, blurry, low quality, watermark, "
        "text, signature, deformed"
    )

    DEFAULT_CHECKPOINT = "sd_xl_base_1.0.safetensors"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.base_url = self.config.get(
            "comfyui_url", os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        )
        self._server_online = self._ping_server()
        self._simulate = not self._server_online

    # ------------------------------------------------------------------
    #  环境探测
    # ------------------------------------------------------------------
    def _ping_server(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def check_available(self) -> bool:
        """适配器可用 = ComfyUI 服务端在线"""
        return self._ping_server()

    # ------------------------------------------------------------------
    #  工作流构建
    # ------------------------------------------------------------------
    def build_workflow(
        self,
        style: str,
        input_image: str,
        output_prefix: str = "handdrawn",
        checkpoint: Optional[str] = None,
        denoise: float = 0.75,
        steps: int = 20,
        cfg: float = 7.0,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """从模板构建可提交的工作流 JSON (纯本地, 无需服务端)"""
        if style not in self.STYLE_PROMPTS:
            raise ValueError(
                f"未知风格 '{style}', 支持: {list(self.STYLE_PROMPTS)}"
            )
        if not _WORKFLOW_TEMPLATE.is_file():
            raise FileNotFoundError(f"工作流模板不存在: {_WORKFLOW_TEMPLATE}")

        with open(_WORKFLOW_TEMPLATE, "r", encoding="utf-8") as f:
            raw = f.read()

        replacements = {
            "{{CHECKPOINT}}": checkpoint or self.DEFAULT_CHECKPOINT,
            "{{INPUT_IMAGE}}": Path(input_image).name,
            "{{STYLE_PROMPT}}": self.STYLE_PROMPTS[style],
            "{{NEGATIVE_PROMPT}}": self.NEGATIVE_PROMPT,
            "{{SEED}}": seed if seed is not None else uuid.uuid4().int % (2**32),
            "{{STEPS}}": steps,
            "{{CFG}}": cfg,
            "{{DENOISE}}": denoise,
            "{{OUTPUT_PREFIX}}": output_prefix,
        }
        for placeholder, value in replacements.items():
            raw = raw.replace(placeholder, str(value))

        workflow = json.loads(raw)
        workflow.pop("_meta", None)
        # 占位符替换会将 KSampler 数值字段变成字符串, 强转回数值类型 (ComfyUI API 要求)
        ks = workflow["6"]["inputs"]
        ks["seed"] = int(ks["seed"])
        ks["steps"] = int(ks["steps"])
        ks["cfg"] = float(ks["cfg"])
        ks["denoise"] = float(ks["denoise"])
        return workflow

    # ------------------------------------------------------------------
    #  ComfyUI HTTP 交互
    # ------------------------------------------------------------------
    def _upload_image(self, image_path: Path) -> str:
        """上传输入图像到 ComfyUI input 目录, 返回服务端文件名"""
        boundary = uuid.uuid4().hex
        mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
        with open(image_path, "rb") as f:
            data = f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; '
            f'filename="{image_path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8") + data + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
            f"true\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/upload/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("name", image_path.name)

    def _queue_and_wait(
        self, workflow: Dict[str, Any], max_wait: int = 600
    ) -> Dict[str, Any]:
        data = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/prompt", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            prompt_id = json.loads(resp.read().decode("utf-8")).get("prompt_id", "")

        start = time.time()
        while time.time() - start < max_wait:
            try:
                with urllib.request.urlopen(
                    f"{self.base_url}/history/{prompt_id}", timeout=10
                ) as resp:
                    history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    entry = history[prompt_id]
                    if entry.get("outputs") or entry.get("status", {}).get("completed"):
                        return entry
            except Exception:
                pass
            time.sleep(3)
        raise TimeoutError(f"ComfyUI 任务超时 ({max_wait}s): {prompt_id}")

    def _download_output(self, entry: Dict[str, Any], output_path: Path) -> Optional[Path]:
        """从历史条目中提取图片并下载"""
        images: List[Dict[str, str]] = []
        for outputs in entry.get("outputs", {}).values():
            for img in outputs.get("images", []):
                images.append(img)
        if not images:
            return None
        img = images[0]
        url = (
            f"{self.base_url}/view?filename={img['filename']}"
            f"&subfolder={img.get('subfolder', '')}&type={img.get('type', 'output')}"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as resp:
            output_path.write_bytes(resp.read())
        return output_path

    # ------------------------------------------------------------------
    #  执行入口
    # ------------------------------------------------------------------
    def execute(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if operation not in self.SUPPORTED_OPERATIONS:
            return {"status": "error", "error": f"不支持的操作: {operation}"}

        if operation == "list_styles":
            return {
                "status": "success",
                "styles": list(self.STYLE_PROMPTS),
                "prompts": self.STYLE_PROMPTS,
            }
        if operation == "check_environment":
            return {"status": "success", **self._env_report()}
        if operation == "build_workflow":
            try:
                wf = self.build_workflow(
                    style=params.get("style", "pencil_sketch"),
                    input_image=params.get("input_image", "input.png"),
                    output_prefix=params.get("output_prefix", "handdrawn"),
                    denoise=params.get("denoise", 0.75),
                    steps=params.get("steps", 20),
                    cfg=params.get("cfg", 7.0),
                    seed=params.get("seed"),
                )
                return {"status": "success", "workflow": wf, "node_count": len(wf)}
            except (ValueError, FileNotFoundError) as e:
                return {"status": "error", "error": str(e)}
        if operation == "stylize_image":
            return self._stylize_image(params)
        if operation == "batch_stylize":
            return self._batch_stylize(params)
        return {"status": "error", "error": "未实现的操作"}

    def _env_report(self) -> Dict[str, Any]:
        online = self._ping_server()
        report: Dict[str, Any] = {
            "server_url": self.base_url,
            "server_online": online,
            "simulate_mode": not online,
            "workflow_template_exists": _WORKFLOW_TEMPLATE.is_file(),
            "styles": list(self.STYLE_PROMPTS),
        }
        if online:
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/object_info/CheckpointLoaderSimple"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    info = json.loads(resp.read().decode("utf-8"))
                report["checkpoints"] = (
                    info.get("CheckpointLoaderSimple", {})
                    .get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
                )
            except Exception:
                report["checkpoints"] = []
        return report

    def _stylize_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        style = params.get("style", "pencil_sketch")
        input_image = params.get("input_image", "")
        output_path = Path(params.get("output_path", "output_handdrawn.png"))

        if not input_image or not Path(input_image).is_file():
            return {"status": "error", "error": f"输入图像不存在: {input_image}"}

        # 模拟模式: 仅生成工作流 JSON, 不真正提交
        if self._simulate:
            wf = self.build_workflow(style, input_image,
                                     output_prefix=output_path.stem)
            dry_run_path = output_path.with_suffix(".workflow.json")
            dry_run_path.parent.mkdir(parents=True, exist_ok=True)
            dry_run_path.write_text(
                json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.warning("[ComfyUI手绘] 服务端离线, 模拟模式: 已生成 %s", dry_run_path)
            return {
                "status": "success",
                "simulate": True,
                "style": style,
                "workflow_json": str(dry_run_path),
                "message": "ComfyUI 服务端离线, 已生成可提交工作流 (dry-run)",
            }

        try:
            self._upload_image(Path(input_image))
            wf = self.build_workflow(style, input_image,
                                     output_prefix=output_path.stem)
            entry = self._queue_and_wait(wf, max_wait=params.get("timeout", 600))
            saved = self._download_output(entry, output_path)
            if saved is None:
                return {"status": "error", "error": "任务完成但无图像输出"}
            return {
                "status": "success",
                "simulate": False,
                "style": style,
                "output_path": str(saved),
            }
        except Exception as e:
            logger.exception("[ComfyUI手绘] 风格化失败")
            return {"status": "error", "error": str(e)}

    def _batch_stylize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """批量风格化: 关键帧序列 → 风格化序列"""
        frames: List[str] = params.get("frames", [])
        style = params.get("style", "pencil_sketch")
        out_dir = Path(params.get("output_dir", "output_handdrawn_frames"))
        if not frames:
            return {"status": "error", "error": "frames 列表为空"}

        out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for idx, frame in enumerate(frames):
            out_path = out_dir / f"{idx:04d}_{style}.png"
            r = self._stylize_image({
                **params,
                "input_image": frame,
                "output_path": str(out_path),
            })
            results.append(r)
            if r.get("status") != "success":
                logger.warning("[ComfyUI手绘] 第 %d 帧失败: %s", idx, r.get("error"))

        ok = sum(1 for r in results if r["status"] == "success")
        return {
            "status": "success" if ok == len(results) else "partial",
            "processed": ok,
            "total": len(results),
            "output_dir": str(out_dir),
            "results": results,
        }
