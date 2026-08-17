"""SAM2 子进程推理脚本。

在 venv-sam2 虚拟环境中以子进程方式运行，避免主 Python 环境安装 PyTorch/SAM2。
通过 JSON 参数文件接收输入，通过 marker 文件返回结果。

用法:
    python sam2_infer.py <params_json_path>

params JSON 格式:
{
    "video_path": "D:/path/to/video.mp4",
    "output_dir": "D:/path/to/masks/",
    "checkpoint": "D:/AE-Work/models/sam2/sam2.1_hiera_base_plus.pt",
    "model_cfg": "configs/sam2.1/sam2.1_hiera_b+.yaml",
    "prompts": [{"type": "positive", "x": 100, "y": 200}],
    "mask_prefix": "mask_",
    "start_frame": 0,
    "marker_path": "C:/tmp/sam2_result.marker"
}
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def write_marker(marker_path: str, success: bool, info: dict | None = None, error: str | None = None) -> None:
    """写入结果 marker 文件。"""
    result = {"success": success}
    if info:
        result["info"] = info
    if error:
        result["error"] = error
    Path(marker_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python sam2_infer.py <params_json_path>", file=sys.stderr)
        return 2

    params_path = Path(sys.argv[1])
    if not params_path.exists():
        print(f"Params file not found: {params_path}", file=sys.stderr)
        return 2

    params = json.loads(params_path.read_text(encoding="utf-8"))
    marker_path = params.get("marker_path")
    if not marker_path:
        print("Missing marker_path in params", file=sys.stderr)
        return 2

    try:
        _run_inference(params)
        write_marker(
            marker_path,
            success=True,
            info={
                "mask_count": params.get("_mask_count", 0),
                "output_dir": params["output_dir"],
                "checkpoint": params["checkpoint"],
            },
        )
        return 0
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        write_marker(marker_path, success=False, error=error_msg)
        print(error_msg, file=sys.stderr)
        return 1


def _run_inference_auto_frame(params: dict) -> int:
    """全自动逐帧分割模式：每帧 YOLO 检测人物 → SAM2 单帧分割。

    适用于人物快速运动 / 镜头剧烈变化的素材。
    每帧独立分割，互不影响，不存在传播漂移问题。
    无人物帧输出全黑遮罩，保持帧对齐。
    """
    import cv2
    import numpy as np
    import torch

    video_path = Path(params["video_path"])
    output_dir = Path(params["output_dir"])
    checkpoint = Path(params["checkpoint"])
    model_cfg = params["model_cfg"]
    mask_prefix = params.get("mask_prefix", "mask_")
    start_frame = params.get("start_frame", 0)
    conf_threshold = params.get("detect_conf", 0.30)
    # 允许指定检测类别（默认 person，也可用 "all" 取最大检测框）
    detect_class = params.get("detect_class", "person")

    if not checkpoint.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    output_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("WARNING: CUDA 不可用，使用 CPU 推理（速度会显著下降）", file=sys.stderr)

    print(f"[SAM2] 逐帧模式加载模型: {checkpoint.name} | device={device}", file=sys.stderr)

    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    model = build_sam2(model_cfg, str(checkpoint), device=device)
    predictor = SAM2ImagePredictor(model)

    # 加载 YOLO 检测器（支持自定义模型路径）
    yolo_model_path = params.get("yolo_model", "yolov8n.pt")
    try:
        import os as _os
        _os.environ.setdefault("YOLO_CONFIG_DIR", str(Path.home() / ".cache" / "ultralytics"))
        from ultralytics import YOLO
        yolo = YOLO(yolo_model_path, verbose=False)
        print(f"[SAM2] YOLO 检测器加载完成: {yolo_model_path} (detect_class={detect_class}, conf={conf_threshold})", file=sys.stderr)
    except Exception as e:
        raise RuntimeError(f"YOLO 加载失败: {e}. 请先: pip install ultralytics") from e

    autocast_ctx = (
        torch.autocast("cuda", dtype=torch.float16)
        if device == "cuda"
        else torch.cuda.amp.autocast(enabled=False)
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    mask_count = 0
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        best_box = None
        best_area = 0
        # YOLO 检测
        results = yolo(frame, conf=conf_threshold, verbose=False)
        for r in results:
            for box in r.boxes:
                cls_name = yolo.names[int(box.cls[0])]
                if detect_class != "all" and cls_name != detect_class:
                    continue
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_box = np.array([x1, y1, x2, y2], dtype=np.float32)

        export_idx = frame_idx - start_frame
        if export_idx < 0:
            frame_idx += 1
            continue

        mask_out = np.zeros((h, w), np.uint8)
        if best_box is not None:
            # SAM2 单帧分割（box 提示）
            with torch.inference_mode(), autocast_ctx:
                predictor.set_image(frame)
                masks, scores, _ = predictor.predict(
                    box=best_box,
                    multimask_output=False,
                )
            m = (masks[0] > 0.0).astype(np.uint8).squeeze()
            if m.shape == (h, w):
                mask_out = m * 255
            elif m.shape[0] == h and m.shape[1] == w:
                mask_out = m * 255
            mask_count += 1

        mask_path = output_dir / f"{mask_prefix}{export_idx:05d}.png"
        _ok, _buf = cv2.imencode(".png", mask_out)
        if _ok:
            _buf.tofile(str(mask_path))
        frame_idx += 1

    cap.release()
    print(f"[SAM2] 逐帧分割完成: {mask_count} 帧含目标, 共 {frame_idx} 帧写入 {output_dir}", file=sys.stderr)
    return mask_count


def _run_inference(params: dict) -> None:
    """执行 SAM2 视频分割推理。"""
    import torch

    video_path = Path(params["video_path"])
    output_dir = Path(params["output_dir"])
    checkpoint = Path(params["checkpoint"])
    model_cfg = params["model_cfg"]
    prompts = params.get("prompts")
    mask_prefix = params.get("mask_prefix", "mask_")
    start_frame = params.get("start_frame", 0)
    mode = params.get("mode", "video")

    if not checkpoint.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 全自动逐帧模式：无需 prompts，自动检测+分割
    if mode == "auto_frame":
        mask_count = _run_inference_auto_frame(params)
        params["_mask_count"] = mask_count
        return

    # 选择设备
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("WARNING: CUDA 不可用，使用 CPU 推理（速度会显著下降）", file=sys.stderr)

    print(f"[SAM2] 加载模型: {checkpoint.name} | device={device} | cfg={model_cfg}", file=sys.stderr)

    from sam2.build_sam import build_sam2_video_predictor

    predictor = build_sam2_video_predictor(
        config_file=model_cfg,
        ckpt_path=str(checkpoint),
        device=device,
    )

    autocast_ctx = (
        torch.autocast("cuda", dtype=torch.float16)
        if device == "cuda"
        else torch.cuda.amp.autocast(enabled=False)
    )

    mask_count = 0

    with torch.inference_mode(), autocast_ctx:
        inference_state = predictor.init_state(video_path=str(video_path))

        # 注入点提示 / 框提示（支持 type: positive/negative/box）
        if prompts:
            positive_points = []
            negative_points = []
            boxes = []
            for p in prompts:
                pt_type = p.get("type", "positive")
                if pt_type == "box":
                    # box: [x1, y1, x2, y2]
                    x1, y1, x2, y2 = p.get("x1", 0), p.get("y1", 0), p.get("x2", 0), p.get("y2", 0)
                    boxes.append([x1, y1, x2, y2])
                elif pt_type == "negative":
                    negative_points.append([p.get("x", 0), p.get("y", 0)])
                else:
                    positive_points.append([p.get("x", 0), p.get("y", 0)])

            all_points = positive_points + negative_points
            labels = [1] * len(positive_points) + [0] * len(negative_points)

            if all_points or boxes:
                kwargs = {
                    "inference_state": inference_state,
                    "frame_idx": 0,
                    "obj_id": 0,
                }
                if all_points:
                    kwargs["points"] = all_points
                    kwargs["labels"] = labels
                if boxes:
                    kwargs["box"] = boxes[0]  # 取第一个框
                predictor.add_new_points_or_box(**kwargs)
                print(
                    f"[SAM2] 注入 {len(positive_points)} 正点 + {len(negative_points)} 负点"
                    + (f" + 框{boxes}" if boxes else ""),
                    file=sys.stderr,
                )

        # 逐帧传播生成遮罩
        import cv2

        for frame_idx, obj_ids, mask_logits in predictor.propagate_in_video(inference_state):
            mask = (mask_logits[0] > 0.0).cpu().numpy().astype("uint8") * 255
            mask = mask.squeeze()  # 确保是 2D 数组
            export_idx = frame_idx - start_frame
            if export_idx < 0:
                continue
            mask_path = output_dir / f"{mask_prefix}{export_idx:05d}.png"
            _ok, _buf = cv2.imencode(".png", mask)
            if _ok:
                _buf.tofile(str(mask_path))
                mask_count += 1
            else:
                print(f"[SAM2] 遮罩编码失败: frame_idx={frame_idx}", file=sys.stderr)

        print(f"[SAM2] 遮罩生成完成: {mask_count} 帧写入 {output_dir}", file=sys.stderr)

    # 子进程退出时自动释放显存，无需手动清理
    params["_mask_count"] = mask_count


if __name__ == "__main__":
    sys.exit(main())
