"""按 report.json 的时间段生成多段成片质量报告。

该脚本只做本地 OpenCV 统计，不调用外部模型；用于在真实 CNN/Qwen 评分前
定位黑帧、低亮度和纹理代理指标异常的段。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np


BLACK_THRESHOLD = 3.0
LOW_BRIGHTNESS_THRESHOLD = 8.0


def _frame_metrics(frame: np.ndarray) -> Dict[str, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return {
        "mean_bgr": float(frame.mean()),
        "std_bgr": float(frame.std()),
        "mean_gray": float(gray.mean()),
        "edge_density": float((cv2.Canny(gray, 80, 160) > 0).mean()),
        "texture_variance": float(laplacian.var()),
    }


def _scan_segment(cap: cv2.VideoCapture, fps: float, start: float, end: float) -> Dict[str, Any]:
    start_frame = max(0, int(round(start * fps)))
    end_frame = max(start_frame, int(round(end * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    metrics: List[Dict[str, float]] = []
    black_frames: List[int] = []
    low_frames: List[int] = []
    previous_gray = None
    diffs: List[float] = []
    frame_index = start_frame
    while frame_index < end_frame:
        ok, frame = cap.read()
        if not ok:
            break
        current = _frame_metrics(frame)
        metrics.append(current)
        if current["mean_bgr"] < BLACK_THRESHOLD:
            black_frames.append(frame_index)
        if current["mean_bgr"] < LOW_BRIGHTNESS_THRESHOLD:
            low_frames.append(frame_index)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if previous_gray is not None:
            diffs.append(float(cv2.absdiff(gray, previous_gray).mean()))
        previous_gray = gray
        frame_index += 1

    def avg(key: str) -> float:
        values = [item[key] for item in metrics]
        return float(np.mean(values)) if values else 0.0

    return {
        "time_range": [start, end],
        "requested_frames": end_frame - start_frame,
        "scanned_frames": len(metrics),
        "black_frame_count": len(black_frames),
        "black_frames": black_frames,
        "low_brightness_frame_count": len(low_frames),
        "low_brightness_frames": low_frames,
        "mean_bgr": avg("mean_bgr"),
        "mean_gray": avg("mean_gray"),
        "std_bgr": avg("std_bgr"),
        "edge_density": avg("edge_density"),
        "texture_variance": avg("texture_variance"),
        "mean_frame_diff": float(np.mean(diffs)) if diffs else 0.0,
        "min_frame_mean_bgr": min((item["mean_bgr"] for item in metrics), default=0.0),
        "max_frame_mean_bgr": max((item["mean_bgr"] for item in metrics), default=0.0),
    }


def score_video(video_path: Path, report_path: Path, output_path: Path) -> Dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    segments = {}
    for name, data in report.get("segments", {}).items():
        start, end = data["time_range"]
        segments[name] = _scan_segment(cap, fps, float(start), float(end))
    cap.release()
    result = {
        "video": str(video_path),
        "fps": fps,
        "frame_count": frame_count,
        "duration": frame_count / fps if fps else 0.0,
        "thresholds": {
            "black_mean_bgr": BLACK_THRESHOLD,
            "low_brightness_mean_bgr": LOW_BRIGHTNESS_THRESHOLD,
        },
        "segments": segments,
        "passed": all(item["black_frame_count"] == 0 for item in segments.values()),
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score_video(args.video, args.report, args.output)
    for name, segment in result["segments"].items():
        print(
            f"{name}: frames={segment['scanned_frames']}/{segment['requested_frames']} "
            f"black={segment['black_frame_count']} low={segment['low_brightness_frame_count']} "
            f"mean={segment['mean_bgr']:.3f} texture_var={segment['texture_variance']:.3f}"
        )
    print(f"passed={result['passed']} output={args.output}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
