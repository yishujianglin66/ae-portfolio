"""P1: 帧序列 batch 抠像 + 时序一致性验证。

步骤：
1. 从 portrait_test_input.jpg 生成 20 帧微动序列（平移+微旋转模拟视频拆帧）
2. MODNet + RMBG-1.4 双模型 batch_frames
3. 生成对比动图 GIF（原图 / MODNet alpha / RMBG alpha 三轨并排）
4. 量化时序稳定性：帧间 alpha diff 均值 + 闪烁热力图 + 指标表
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\src")

import cv2
import numpy as np

# ======================================================================
# 配置
# ======================================================================
ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
OUT = ROOT / "tests" / "output" / "matting_e2e" / "p1_temporal"
FRAMES_DIR = OUT / "input_frames"
MODNET_ALPHA = OUT / "modnet" / "alpha"
RMBG_ALPHA = OUT / "rmbg14" / "alpha"
MODNET_RGBA = OUT / "modnet" / "rgba"
RMBG_RGBA = OUT / "rmbg14" / "rgba"

SRC_IMG = ROOT / "tests" / "output" / "matting_e2e" / "portrait_test_input.jpg"
MODEL_DIR = Path(r"D:\AE-Work\models\matting")

NUM_FRAMES = 20
# 微动参数：模拟手持相机的轻微晃动
MAX_SHIFT_X = 12   # 像素
MAX_SHIFT_Y = 8
MAX_ROT = 1.5      # 度

for d in [FRAMES_DIR, MODNET_ALPHA, RMBG_RGBA, RMBG_ALPHA]:
    d.mkdir(parents=True, exist_ok=True)


# ======================================================================
# 工具函数
# ======================================================================
def imread(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite(path: Path, img: np.ndarray) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(path))
    return ok


def checker_bg(w, h, tile=16):
    c1 = np.full((tile, tile, 3), (230, 230, 230), dtype=np.uint8)
    c2 = np.full((tile, tile, 3), (150, 150, 150), dtype=np.uint8)
    block = np.concatenate([
        np.concatenate([c1, c2], axis=1),
        np.concatenate([c2, c1], axis=1)
    ], axis=0)
    big = np.tile(block, ((h + tile - 1) // tile, (w + tile - 1) // tile, 1))
    return big[:h, :w]


# ======================================================================
# Step 1: 生成微动帧序列
# ======================================================================
def generate_frames():
    print("=" * 60)
    print("Step 1: 生成 20 帧微动序列")
    print("=" * 60)

    src = imread(SRC_IMG)
    assert src is not None, f"无法读取源图: {SRC_IMG}"
    H, W = src.shape[:2]
    print(f"  源图尺寸: {W}x{H}")

    # 缩小到 1280x720 加速 batch 推理
    TW, TH = 1280, 720
    src = cv2.resize(src, (TW, TH), interpolation=cv2.INTER_AREA)
    print(f"  缩放到: {TW}x{TH} (加速 batch)")

    for i in range(NUM_FRAMES):
        t = i / (NUM_FRAMES - 1)  # 0..1
        # 正弦波微动（平滑循环）
        dx = int(MAX_SHIFT_X * np.sin(2 * np.pi * t))
        dy = int(MAX_SHIFT_Y * np.sin(2 * np.pi * t * 1.3))
        angle = MAX_ROT * np.sin(2 * np.pi * t * 0.7)

        M = cv2.getRotationMatrix2D((TW / 2, TH / 2), angle, 1.0)
        M[0, 2] += dx
        M[1, 2] += dy
        frame = cv2.warpAffine(src, M, (TW, TH), borderMode=cv2.BORDER_REFLECT_101)

        fname = f"frame_{i:04d}.jpg"
        imwrite(FRAMES_DIR / fname, frame)

    print(f"  生成 {NUM_FRAMES} 帧 -> {FRAMES_DIR}")
    return TW, TH


# ======================================================================
# Step 2: 双模型 batch 抠像
# ======================================================================
async def run_batch_matting():
    print()
    print("=" * 60)
    print("Step 2: 双模型 batch_frames 抠像")
    print("=" * 60)

    from engines.matting.engine import MattingEngine

    eng = MattingEngine()
    eng._model_dir = MODEL_DIR
    eng._model_index = {
        "modnet": MODEL_DIR / "modnet_xenova.onnx",
        "rmbg14": MODEL_DIR / "rmbg14.onnx",
    }

    results = {}
    for model_key, alpha_dir in [
        ("modnet", MODNET_ALPHA),
        ("rmbg14", RMBG_ALPHA),
    ]:
        alpha_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = await eng.batch_frames(
            input_path=FRAMES_DIR,
            output_dir=alpha_dir,
            model_name=model_key,
        )
        dt = time.time() - t0
        success = r.success
        count = r.metadata.get("processed_count", 0) if success else 0
        avg = dt / count if count > 0 else 0
        print(f"  [{model_key}] success={success}  frames={count}/{NUM_FRAMES}  total={dt:.2f}s  avg={avg:.3f}s/帧")
        if not success:
            print(f"    ERROR: {r.error}")
        results[model_key] = {
            "success": success,
            "count": count,
            "total_s": round(dt, 2),
            "avg_s": round(avg, 3),
        }
    return results


# ======================================================================
# Step 3: 生成对比动图 GIF
# ======================================================================
def make_comparison_gif(W, H):
    print()
    print("=" * 60)
    print("Step 3: 生成对比动图 GIF")
    print("=" * 60)

    frames = []
    for i in range(NUM_FRAMES):
        stem = f"frame_{i:04d}"

        # 原图
        orig = imread(FRAMES_DIR / f"{stem}.jpg")
        if orig is None:
            continue

        # 从 alpha + 原图合成棋盘格
        def composite_from_alpha(alpha_dir):
            ap = alpha_dir / f"{stem}.png"
            if not ap.exists():
                return None
            a_data = np.fromfile(str(ap), dtype=np.uint8)
            a = cv2.imdecode(a_data, cv2.IMREAD_GRAYSCALE)
            if a is None:
                return None
            a_f = a.astype(np.float32) / 255.0
            bg = checker_bg(W, H)
            # 确保尺寸匹配
            if a_f.shape[:2] != (H, W):
                a_f = cv2.resize(a_f, (W, H), interpolation=cv2.INTER_LINEAR)
            fg = orig.astype(np.float32)
            return (fg * a_f[..., None] + bg.astype(np.float32) * (1 - a_f[..., None])).astype(np.uint8)

        mod_comp = composite_from_alpha(MODNET_ALPHA)
        rmbg_comp = composite_from_alpha(RMBG_ALPHA)

        # 缩小到 320 宽度做 GIF
        SCALE = 320
        sw = SCALE
        sh = int(H * SCALE / W)
        orig_s = cv2.resize(orig, (sw, sh))
        panels = [orig_s]
        labels = ["Original"]

        if mod_comp is not None:
            panels.append(cv2.resize(mod_comp, (sw, sh)))
            labels.append("MODNet")
        else:
            panels.append(np.full((sh, sw, 3), 40, dtype=np.uint8))
            labels.append("MODNet (missing)")

        if rmbg_comp is not None:
            panels.append(cv2.resize(rmbg_comp, (sw, sh)))
            labels.append("RMBG-1.4")
        else:
            panels.append(np.full((sh, sw, 3), 40, dtype=np.uint8))
            labels.append("RMBG (missing)")

        # 添加标签条
        bar_h = 28
        labeled = []
        for panel, label in zip(panels, labels):
            bar = np.full((bar_h, sw, 3), (20, 20, 20), dtype=np.uint8)
            cv2.putText(bar, label, (8, bar_h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            labeled.append(np.concatenate([bar, panel], axis=0))

        row = np.concatenate(labeled, axis=1)
        frames.append(row)

    if not frames:
        print("  ERROR: 没有可用的帧")
        return None

    # 写 GIF
    gif_path = OUT / "temporal_comparison.gif"
    import imageio.v2 as imageio
    imageio.mimsave(str(gif_path), frames, duration=0.15, loop=0)
    print(f"  GIF 已生成: {gif_path}  ({len(frames)} 帧, {frames[0].shape[1]}x{frames[0].shape[0]})")
    return gif_path


# ======================================================================
# Step 4: 量化时序稳定性
# ======================================================================
def quantify_temporal():
    print()
    print("=" * 60)
    print("Step 4: 量化时序稳定性")
    print("=" * 60)

    models = {
        "MODNet": MODNET_ALPHA,
        "RMBG-1.4": RMBG_ALPHA,
    }

    all_metrics = {}

    for model_name, alpha_dir in models.items():
        print(f"\n  --- {model_name} ---")

        # 读取全部 alpha
        alphas = []
        for i in range(NUM_FRAMES):
            p = alpha_dir / f"frame_{i:04d}.png"
            if not p.exists():
                print(f"    警告: 缺失 {p.name}")
                continue
            a = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
            alphas.append(a)

        if len(alphas) < 2:
            print("    alpha 帧不足，跳过")
            continue

        # === 指标1: 帧间 diff 均值（越小越稳定）===
        diffs = []
        for i in range(1, len(alphas)):
            d = np.abs(alphas[i] - alphas[i - 1])
            diffs.append(float(np.mean(d)))

        mean_diff = float(np.mean(diffs))
        max_diff = float(np.max(diffs))

        # === 指标2: 闪烁像素比（diff > 0.1 的像素占比）===
        flicker_ratios = []
        for i in range(1, len(alphas)):
            d = np.abs(alphas[i] - alphas[i - 1])
            flicker_ratios.append(float(np.mean(d > 0.1)))

        mean_flicker = float(np.mean(flicker_ratios))
        max_flicker = float(np.max(flicker_ratios))

        # === 指标3: alpha 方差图（时间维度上每个像素的 std）===
        alpha_stack = np.stack(alphas, axis=0)  # [N, H, W]
        pixel_std = np.std(alpha_stack, axis=0)  # [H, W]
        mean_pixel_std = float(np.mean(pixel_std))
        max_pixel_std = float(np.max(pixel_std))

        # === 指标4: 边缘区域闪烁（在 alpha 0.1~0.9 的软边区域）===
        edge_mask = np.zeros_like(alphas[0], dtype=bool)
        for a in alphas:
            edge_mask |= (a > 0.1) & (a < 0.9)
        edge_flicker = float(np.mean(pixel_std[edge_mask])) if edge_mask.any() else 0.0

        # === 输出 ===
        print(f"    帧间 diff 均值:     {mean_diff:.5f}  (越小越稳定)")
        print(f"    帧间 diff 最大值:   {max_diff:.5f}")
        print(f"    闪烁像素比 (>0.1):  {mean_flicker:.4f}  ({mean_flicker*100:.1f}%)")
        print(f"    闪烁像素比峰值:     {max_flicker:.4f}  ({max_flicker*100:.1f}%)")
        print(f"    像素时间标准差均值: {mean_pixel_std:.5f}")
        print(f"    像素时间标准差峰值: {max_pixel_std:.5f}")
        print(f"    边缘区闪烁强度:     {edge_flicker:.5f}")

        all_metrics[model_name] = {
            "mean_diff": round(mean_diff, 5),
            "max_diff": round(max_diff, 5),
            "flicker_ratio": round(mean_flicker, 4),
            "flicker_peak": round(max_flicker, 4),
            "pixel_std_mean": round(mean_pixel_std, 5),
            "pixel_std_max": round(max_pixel_std, 5),
            "edge_flicker": round(edge_flicker, 5),
        }

        # === 生成闪烁热力图 ===
        heat = (pixel_std / max(max_pixel_std, 1e-6) * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
        # 叠加原图灰度做参考
        orig_gray = cv2.cvtColor(imread(FRAMES_DIR / "frame_0000.jpg"), cv2.COLOR_BGR2GRAY)
        orig_gray = cv2.resize(orig_gray, (heat.shape[1], heat.shape[0]))
        overlay = cv2.addWeighted(cv2.cvtColor(orig_gray, cv2.COLOR_GRAY2BGR), 0.4, heat_color, 0.6, 0)

        heat_path = OUT / f"flicker_heatmap_{model_name.lower().replace('-', '').replace('.', '')}.jpg"
        imwrite(heat_path, overlay)
        print(f"    闪烁热力图: {heat_path}")

    # === 汇总表 ===
    print()
    print("  " + "=" * 70)
    print("  时序稳定性汇总对比")
    print("  " + "=" * 70)
    header = f"  {'指标':<20s} {'MODNet':>12s} {'RMBG-1.4':>12s} {'胜者':>8s}"
    print(header)
    print("  " + "-" * 56)

    metrics_to_compare = [
        ("帧间diff均值", "mean_diff", "lower"),
        ("帧间diff最大", "max_diff", "lower"),
        ("闪烁像素比(%)", "flicker_ratio", "lower"),
        ("闪烁峰值(%)", "flicker_peak", "lower"),
        ("像素std均值", "pixel_std_mean", "lower"),
        ("像素std峰值", "pixel_std_max", "lower"),
        ("边缘区闪烁", "edge_flicker", "lower"),
    ]

    for label, key, direction in metrics_to_compare:
        m_val = all_metrics.get("MODNet", {}).get(key, 0)
        r_val = all_metrics.get("RMBG-1.4", {}).get(key, 0)
        if direction == "lower":
            winner = "MODNet" if m_val < r_val else "RMBG-1.4" if r_val < m_val else "平手"
            if key in ("flicker_ratio", "flicker_peak"):
                m_display = f"{m_val*100:.1f}%"
                r_display = f"{r_val*100:.1f}%"
            else:
                m_display = f"{m_val:.5f}"
                r_display = f"{r_val:.5f}"
        else:
            winner = "MODNet" if m_val > r_val else "RMBG-1.4"
            m_display = f"{m_val:.5f}"
            r_display = f"{r_val:.5f}"
        print(f"  {label:<20s} {m_display:>12s} {r_display:>12s} {winner:>8s}")

    return all_metrics


# ======================================================================
# 主入口
# ======================================================================
def main():
    print("P1: 帧序列 batch 抠像 + 时序一致性验证")
    print(f"输出目录: {OUT}")
    print()

    # Step 1: 生成微动帧
    W, H = generate_frames()

    # Step 2: batch 抠像
    batch_results = asyncio.run(run_batch_matting())

    # Step 3: 对比动图
    gif_path = make_comparison_gif(W, H)

    # Step 4: 量化
    temporal_metrics = quantify_temporal()

    # === 最终汇总 ===
    print()
    print("=" * 60)
    print("P1 最终汇总")
    print("=" * 60)
    print(f"  帧数: {NUM_FRAMES}")
    print(f"  分辨率: {W}x{H}")
    print()
    print("  性能:")
    for model, data in batch_results.items():
        print(f"    {model}: {data['count']}帧 / {data['total_s']}s / 均{data['avg_s']}s/帧")
    print()
    print("  时序稳定性:")
    for model, data in temporal_metrics.items():
        print(f"    {model}: diff={data['mean_diff']}  flicker={data['flicker_ratio']*100:.1f}%  edge={data['edge_flicker']}")
    print()
    print("  产物:")
    print(f"    GIF: {gif_path}")
    print(f"    热力图: {OUT}/flicker_heatmap_*.jpg")
    print(f"    Alpha 序列: {OUT}/{{modnet,rmbg14}}/alpha/")
    print()
    print("DONE.")


if __name__ == "__main__":
    main()
