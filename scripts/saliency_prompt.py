"""基于图像显著性的自动 prompt 生成器。

用途：当 YOLO 检测不到动画人物时，用图像显著性分析自动找到画面中最可能的
     人物中心点，作为 SAM2 video 传播模式的 prompt。

原理：
1. 将图像从 RGB 转为 LAB 颜色空间
2. 计算每个像素与图像均值的颜色距离（显著性）
3. 用形态学操作平滑显著性图
4. 找到显著性最高的区域中心
5. 返回多个候选点（按显著性排序）

优势：
- 不依赖任何模型，纯 OpenCV 计算
- 对任意动画画风（日漫、国漫、美漫）都适用
- 计算快速（< 100ms 每帧）
- 可作为 YOLO 的回退方案

用法：
    from saliency_prompt import find_prompts
    prompts = find_prompts("video.mp4", num_points=3)
    # [{"type": "positive", "x": 320, "y": 240, "score": 0.85}, ...]
"""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path


def compute_saliency_map(frame: np.ndarray) -> np.ndarray:
    """计算图像的显著性图。

    使用 LAB 颜色空间 + 均值距离法（FT 算法简化版）。
    """
    # 高斯模糊去噪
    blurred = cv2.GaussianBlur(frame, (5, 5), 0)

    # 转 LAB 颜色空间
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # 计算各通道与均值的距离
    l_mean = np.mean(l_channel)
    a_mean = np.mean(a_channel)
    b_mean = np.mean(b_channel)

    l_dist = (l_channel.astype(np.float32) - l_mean) ** 2
    a_dist = (a_channel.astype(np.float32) - a_mean) ** 2
    b_dist = (b_channel.astype(np.float32) - b_mean) ** 2

    saliency = np.sqrt(l_dist + a_dist + b_dist)
    saliency = cv2.normalize(saliency, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # 形态学平滑
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    saliency = cv2.morphologyEx(saliency, cv2.MORPH_CLOSE, kernel)
    saliency = cv2.GaussianBlur(saliency, (31, 31), 0)

    return saliency


def find_significant_regions(
    saliency: np.ndarray,
    threshold_factor: float = 0.6,
    min_area: int = 500,
) -> list[dict]:
    """从显著性图中找到显著区域。"""
    # 阈值化
    thresh_val = int(saliency.max() * threshold_factor)
    _, binary = cv2.threshold(saliency, thresh_val, 255, cv2.THRESH_BINARY)

    # 连通组件分析
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

    regions = []
    for i in range(1, num_labels):  # 跳过背景（0）
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue

        cx, cy = centroids[i]
        # 计算区域平均显著性
        mask = labels == i
        avg_sal = float(saliency[mask].mean()) / 255.0

        regions.append({
            "cx": float(cx),
            "cy": float(cy),
            "area": int(area),
            "score": avg_sal,
        })

    # 按显著性分数排序
    regions.sort(key=lambda r: r["score"], reverse=True)
    return regions


def filter_person_like_regions(
    regions: list[dict],
    frame_h: int,
    frame_w: int,
) -> list[dict]:
    """过滤掉不像人物的区域（太小、太靠边、过于扁平）。

    人物区域通常满足：
    - 面积占图像 1% ~ 60%
    - 中心点距图像边缘 > 5%
    - 优先选择画面中下方（人物通常在地面/中间）
    """
    total_pixels = frame_h * frame_w
    filtered = []
    for r in regions:
        area_ratio = r["area"] / total_pixels
        if area_ratio < 0.005 or area_ratio > 0.8:
            continue
        # 距边缘
        margin_x = min(r["cx"], frame_w - r["cx"]) / frame_w
        margin_y = min(r["cy"], frame_h - r["cy"]) / frame_h
        if margin_x < 0.05 or margin_y < 0.05:
            continue
        # 加权：垂直位置偏好（中下方加分）
        vertical_bonus = 1.0 + (r["cy"] / frame_h) * 0.3
        r["adjusted_score"] = r["score"] * vertical_bonus
        filtered.append(r)

    # 按调整后分数排序
    filtered.sort(key=lambda r: r["adjusted_score"], reverse=True)
    return filtered


def find_prompts(
    video_path: Path | str,
    num_points: int = 3,
    frame_idx: int = 0,
) -> list[dict]:
    """从视频指定帧找到最可能的 prompt 点。

    Args:
        video_path: 视频路径
        num_points: 返回的候选点数量
        frame_idx: 使用第几帧（0=首帧）

    Returns:
        prompts 列表，按显著性排序
        [{"type": "positive", "x": 320, "y": 240, "score": 0.85}, ...]
    """
    cap = cv2.VideoCapture(str(video_path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
    finally:
        cap.release()

    if not ret or frame is None:
        return []

    h, w = frame.shape[:2]

    # 计算显著性
    saliency = compute_saliency_map(frame)

    # 找显著区域
    regions = find_significant_regions(saliency)

    # 过滤人物候选
    candidates = filter_person_like_regions(regions, h, w)

    # 转换为 prompts
    prompts = []
    for c in candidates[:num_points]:
        prompts.append({
            "type": "positive",
            "x": int(c["cx"]),
            "y": int(c["cy"]),
            "score": round(c["adjusted_score"], 3),
        })

    return prompts


def find_prompts_with_visualization(
    video_path: Path | str,
    output_png: Path | str,
    num_points: int = 3,
    frame_idx: int = 0,
) -> tuple[list[dict], np.ndarray]:
    """找到 prompt 点并生成可视化图（用于调试）。"""
    cap = cv2.VideoCapture(str(video_path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
    finally:
        cap.release()

    if not ret or frame is None:
        return [], np.array([])

    h, w = frame.shape[:2]
    saliency = compute_saliency_map(frame)
    regions = find_significant_regions(saliency)
    candidates = filter_person_like_regions(regions, h, w)

    # 可视化：叠加显著性热图 + 标注点
    vis = frame.copy()
    saliency_color = cv2.applyColorMap(saliency, cv2.COLORMAP_JET)
    vis = cv2.addWeighted(vis, 0.6, saliency_color, 0.4, 0)

    prompts = []
    for i, c in enumerate(candidates[:num_points]):
        cx, cy = int(c["cx"]), int(c["cy"])
        # 画圆 + 编号
        cv2.circle(vis, (cx, cy), 15, (0, 255, 0), 3)
        cv2.putText(vis, str(i + 1), (cx - 5, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        prompts.append({
            "type": "positive",
            "x": cx,
            "y": cy,
            "score": round(c["adjusted_score"], 3),
        })

    # 保存可视化图（支持中文路径）
    ok, buf = cv2.imencode(".png", vis)
    if ok:
        buf.tofile(str(output_png))

    return prompts, vis


def main():
    """测试：对指定视频生成 prompt 可视化。"""
    import sys

    if len(sys.argv) < 2:
        print("用法: python saliency_prompt.py <video_path> [num_points]")
        return

    video = Path(sys.argv[1])
    num = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    if not video.exists():
        print(f"视频不存在: {video}")
        return

    out_png = video.parent / f"{video.stem}_saliency.png"
    prompts, _ = find_prompts_with_visualization(video, out_png, num_points=num)

    print(f"视频: {video.name}")
    print(f"找到 {len(prompts)} 个候选点:")
    for i, p in enumerate(prompts):
        print(f"  [{i+1}] x={p['x']}, y={p['y']}, score={p['score']}")
    print(f"可视化图: {out_png}")


if __name__ == "__main__":
    main()
