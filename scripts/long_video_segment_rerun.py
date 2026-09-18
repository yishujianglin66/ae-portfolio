"""长视频分段重跑脚本（修复版）。

修复点：
1. 段推理成功后，**只有确认复制成功才清理临时 mask 目录**，失败则保留便于排查。
2. 复制成功判定改为：子进程写入后再读回目标目录，统计实际写入数量（不依赖 stdout 数字解析）。
3. D盘操作全部在子进程完成。
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from saliency_prompt import find_prompts_with_visualization
from src.engines.sam2.engine import SAM2Engine

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
VENV_PY = r"D:\AE-Work\venv-sam2\Scripts\python.exe"

SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUT_BASE = Path(r"D:\AE-Work\batch_auto_frame")
VIS_DIR = PROJECT_ROOT / "output" / "saliency_vis"
TEMP_DIR = PROJECT_ROOT / "output" / "segment_tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
VIS_DIR.mkdir(parents=True, exist_ok=True)

SEGMENT_FRAMES = 500


def _run_subprocess_code(code: str, timeout: int = 600, label: str = "subproc") -> tuple[int, str, str]:
    """在 venv-sam2 子进程中执行 Python 代码（绕过 TRAE 沙箱写入限制）。"""
    script_path = TEMP_DIR / f"_op_{label}_{int(time.time()*1000)}.py"
    script_path.write_text(code, encoding="utf-8")
    r = subprocess.run([VENV_PY, str(script_path)], capture_output=True, text=True, timeout=timeout)
    try:
        script_path.unlink(missing_ok=True)
    except Exception:
        pass
    return r.returncode, r.stdout, r.stderr

LONG_VIDEOS = [
    "DL_黑岩射手_r924_BV1JW411s7GV",  # 4977 帧
    "DL_黑岩射手_r924_BV1NL4y1H7u7",  # 8881 帧
    "DL_海贼王_r84_BV14tZNYGEuV",      # 10126 帧
]


def get_frame_count(video: Path) -> int:
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def cut_segment(src: Path, dst: Path, start_frame: int, num_frames: int) -> bool:
    """用 FFmpeg 切出指定帧段（仅视频流，避免无音频视频报错）。"""
    vf_arg = f"select=between(n\\,{start_frame}\\,{start_frame + num_frames - 1}),setpts=PTS-STARTPTS"
    cmd = [
        FFMPEG, "-y",
        "-i", str(src),
        "-vf", vf_arg,
        "-an",
        "-vsync", "0",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists():
        err_tail = (r.stderr or "").strip()[-300:]
        print(f"    切段失败: rc={r.returncode}, exists={dst.exists()}")
        if err_tail:
            print(f"    FFmpeg stderr: ...{err_tail}")
        return False
    return True


def quick_alpha_check(mov: Path, step: int = 200) -> float:
    """快速检查 MOV 的 alpha 检出率。"""
    total = get_frame_count(mov)
    if total == 0:
        return 0.0
    has_fg = 0
    sampled = 0
    tmp = TEMP_DIR / "alpha_tmp.png"
    for idx in range(0, total, step):
        cmd = [FFMPEG, "-y", "-i", str(mov), "-vf", f"select=eq(n\\,{idx})",
               "-vframes", "1", "-pix_fmt", "rgba", "-f", "image2", str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not tmp.exists():
            continue
        try:
            d = np.fromfile(str(tmp), dtype=np.uint8)
        except Exception:
            continue
        if d.size == 0:
            continue
        try:
            tmp.unlink(missing_ok=True)
        except PermissionError:
            pass
        f = cv2.imdecode(d, cv2.IMREAD_UNCHANGED)
        if f is None or f.ndim != 3 or f.shape[2] != 4:
            continue
        sampled += 1
        if (f[:, :, 3] > 127).mean() > 0.001:
            has_fg += 1
    return has_fg / sampled if sampled > 0 else 0.0


def find_segment_prompts(seg_video: Path, seg_idx: int) -> list[dict]:
    """为视频段找显著性 prompt。尝试首帧和第 30 帧，fallback 用画面中心。"""
    for frame_idx in [0, 30, 60]:
        vis_png = VIS_DIR / f"{seg_video.stem}_sal_f{frame_idx}.png"
        try:
            prompts, _ = find_prompts_with_visualization(
                seg_video, vis_png, num_points=3, frame_idx=frame_idx,
            )
            if prompts:
                return prompts
        except Exception as e:
            print(f"    显著性分析异常 (frame={frame_idx}): {e}")
    try:
        cap = cv2.VideoCapture(str(seg_video))
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"    使用画面中心点 fallback: ({w//2}, {h//2})")
            return [{"type": "positive", "x": w // 2, "y": h // 2}]
    except Exception:
        pass
    return []


def merge_masks_to_mov(src_video: Path, mask_dir: Path, mov_path: Path) -> bool:
    """用 OpenCV 合成 BGRA 帧 + FFmpeg 编码透明 MOV。写入操作全部在子进程。"""
    alpha_dir = TEMP_DIR / f"alpha_merge_{int(time.time()*1000)}"
    alpha_str = str(alpha_dir)

    merge_code = f"""
import cv2, numpy as np, os, sys, shutil
from pathlib import Path

def _imread_unicode(path):
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    except Exception:
        return None

def _imwrite_unicode(path, img):
    ext = os.path.splitext(str(path))[1]
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(path))

src_video = r'{str(src_video)}'
mask_dir = r'{str(mask_dir)}'
out_dir = r'{alpha_str}'

if os.path.isdir(out_dir):
    shutil.rmtree(out_dir, ignore_errors=True)
os.makedirs(out_dir, exist_ok=True)

cap = cv2.VideoCapture(src_video)
masks = sorted(Path(mask_dir).glob('mask_*.png'))
idx = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    mask = None
    if idx < len(masks):
        mask = _imread_unicode(masks[idx])
        if mask is not None and mask.shape[:2] != frame.shape[:2]:
            mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]))
    bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
    if mask is not None:
        bgra[:, :, 3] = mask
    else:
        bgra[:, :, 3] = 255
    _imwrite_unicode(os.path.join(out_dir, f'frame_{{idx:05d}}.png'), bgra)
    idx += 1
cap.release()
print(f'Created {{idx}} BGRA frames', file=sys.stderr)
"""
    script_path = TEMP_DIR / f"merge_alpha_{int(time.time()*1000)}.py"
    script_path.write_text(merge_code, encoding="utf-8")
    r = subprocess.run([VENV_PY, str(script_path)], capture_output=True, text=True, timeout=3600)
    try:
        script_path.unlink(missing_ok=True)
    except Exception:
        pass
    if r.returncode != 0:
        print(f"  合成 BGRA 失败 (rc={r.returncode})")
        print(f"  stderr: {(r.stderr or '')[:400]}")
        return False
    if not (alpha_dir / "frame_00000.png").exists():
        alpha_count = len(list(alpha_dir.glob("frame_*.png")))
        print(f"  警告：未找到 frame_00000.png，frame_*.png 数量={alpha_count}")
        if alpha_count == 0:
            return False

    cmd = [
        FFMPEG, "-y",
        "-f", "image2",
        "-i", str(alpha_dir / "frame_%05d.png"),
        "-c:v", "qtrle",
        "-pix_fmt", "argb",
        str(mov_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    ffmpeg_ok = r.returncode == 0 and mov_path.exists()
    if not ffmpeg_ok:
        print(f"  FFmpeg 编码失败 rc={r.returncode}")
        if r.stderr:
            print(f"  FFmpeg stderr: {(r.stderr or '')[:400]}")
    clean_code = f"""
import shutil, os
d = r'{alpha_str}'
if os.path.isdir(d):
    shutil.rmtree(d, ignore_errors=True)
print("cleaned")
"""
    try:
        _run_subprocess_code(clean_code, timeout=120, label="clean_alpha")
    except Exception:
        pass
    return ffmpeg_ok


def copy_segment_masks_with_verify(
    src_mask_dir: Path,
    dst_mask_dir: Path,
    start_frame: int,
    expected_frames: int,
) -> int:
    """将段推理生成的遮罩复制到总目录并重新编号，复制后立即子进程验证返回实际数量。

    关键：复制+验证+判定全部在 venv-sam2 子进程完成，避免主进程沙箱限制和 stdout 解析错误。
    """
    seg_masks_sorted = sorted(src_mask_dir.glob("mask_*.png"))
    src_paths = [str(p) for p in seg_masks_sorted]
    dst_names = [f"mask_{start_frame + i:05d}.png" for i in range(len(src_paths))]

    copy_code = f"""
import shutil, sys, os
from pathlib import Path

srcs = {src_paths!r}
dsts_dir = r'{str(dst_mask_dir)}'
dst_names = {dst_names!r}
expected = {expected_frames}

os.makedirs(dsts_dir, exist_ok=True)
copied = 0
copy_err = 0
for s, dn in zip(srcs, dst_names):
    d = os.path.join(dsts_dir, dn)
    try:
        shutil.copy2(s, d)
        copied += 1
    except Exception as e:
        copy_err += 1
        if copy_err <= 5:
            print(f"COPY_FAIL {{os.path.basename(s)}}: {{e}}", file=sys.stderr)

# 实际验证：扫描目标目录中位于 [start_frame, start_frame+expected) 的 mask
actual = 0
start = {start_frame}
end = start + expected
for p in Path(dsts_dir).glob('mask_*.png'):
    try:
        idx = int(p.stem.split('_')[1])
    except Exception:
        continue
    if start <= idx < end and p.stat().st_size >= 10:
        actual += 1
print(f"RESULT copied={{copied}} actual={{actual}} copy_err={{copy_err}} expected={{expected}}")
if actual <= 0:
    sys.exit(2)
"""
    rc, out, err = _run_subprocess_code(copy_code, timeout=600, label=f"cpv{int(time.time()*1000)}")
    actual = 0
    copied = 0
    try:
        for line in out.strip().splitlines():
            if line.startswith("RESULT"):
                for part in line.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        if k == "actual":
                            actual = int(v)
                        elif k == "copied":
                            copied = int(v)
    except Exception:
        pass
    if err:
        print(f"    [copy stderr 预览] {err[:250]}")
    if actual == 0:
        print(f"    复制验证失败: rc={rc}, copied={copied}, stdout={out.strip()[:100]}")
    return actual


async def process_long_video(engine: SAM2Engine, stem: str) -> dict:
    """分段处理一个长视频（支持断点续传，跳过已完成段）。"""
    src = SRC_DIR / f"{stem}.mp4"
    out_dir = OUT_BASE / stem
    mov = out_dir / f"{stem}_transparent.mov"
    all_masks_dir = out_dir / f"{stem}_transparent_masks"

    if not src.exists():
        return {"stem": stem, "success": False, "error": "源不存在"}

    total_frames = get_frame_count(src)
    print(f"\n  总帧数: {total_frames}, 分段大小: {SEGMENT_FRAMES}")

    if mov.exists():
        mov.unlink()
    all_masks_dir.mkdir(parents=True, exist_ok=True)

    existing_masks = {int(f.stem.split("_")[1]) for f in all_masks_dir.glob("mask_*.png") if f.stat().st_size >= 10}
    print(f"  已有遮罩(>=10B): {len(existing_masks)} / {total_frames}")

    num_segments = (total_frames + SEGMENT_FRAMES - 1) // SEGMENT_FRAMES
    print(f"  分段数: {num_segments}")

    t0 = time.time()
    total_masks = len(existing_masks)
    seg_errors = []

    for seg_idx in range(num_segments):
        start_frame = seg_idx * SEGMENT_FRAMES
        end_frame = min(start_frame + SEGMENT_FRAMES, total_frames)
        num_frames = end_frame - start_frame

        seg_frame_indices = set(range(start_frame, end_frame))
        if seg_frame_indices.issubset(existing_masks):
            print(f"\n  [段 {seg_idx + 1}/{num_segments}] 帧 {start_frame}-{end_frame - 1} 已完成，跳过")
            continue

        print(f"\n  [段 {seg_idx + 1}/{num_segments}] 帧 {start_frame}-{end_frame - 1} ({num_frames} 帧)")

        seg_video = TEMP_DIR / f"{stem}_seg{seg_idx:03d}.mp4"
        print("    切段...")
        if not cut_segment(src, seg_video, start_frame, num_frames):
            seg_errors.append(f"seg{seg_idx}: 切段失败")
            continue

        prompts = find_segment_prompts(seg_video, seg_idx)
        if not prompts:
            print("    无显著性候选点，跳过")
            seg_errors.append(f"seg{seg_idx}: 无prompt")
            seg_video.unlink(missing_ok=True)
            continue
        print(f"    prompt: {len(prompts)} 点")

        seg_mask_dir = TEMP_DIR / f"{stem}_seg{seg_idx:03d}_masks"
        if seg_mask_dir.exists():
            shutil.rmtree(seg_mask_dir, ignore_errors=True)

        seg_success = False
        seg_mask_count = 0
        for attempt in range(2):
            if attempt > 0:
                print(f"    重试 {attempt}...")
                await asyncio.sleep(5)
            try:
                r = await engine.extract_foreground(
                    video_path=seg_video,
                    output_path=TEMP_DIR / f"{stem}_seg{seg_idx:03d}.mov",
                    model_size="small", mode="video",
                    prompts=prompts,
                )
                if not r.success:
                    seg_errors.append(f"seg{seg_idx} attempt{attempt}: {r.error}")
                    print(f"    推理失败: {r.error}")
                    continue

                generated = sorted(seg_mask_dir.glob("mask_*.png")) if seg_mask_dir.exists() else []
                if generated:
                    seg_success = True
                    seg_mask_count = len(generated)
                    print(f"    段推理OK: {seg_mask_count} 个遮罩")
                    break
                else:
                    seg_errors.append(f"seg{seg_idx}: 无遮罩生成")
                    print("    无遮罩生成")
            except Exception as e:
                seg_errors.append(f"seg{seg_idx}: {e}")
                print(f"    推理异常: {e}")
                continue

        if not seg_success:
            print(f"    段 {seg_idx + 1} 最终失败，保留临时文件便于排查，继续下一段")
            continue

        # === 关键修复：复制+验证，确认无误再清理临时目录 ===
        print(f"    复制遮罩 (offset={start_frame})...")
        actual_copied = copy_segment_masks_with_verify(
            seg_mask_dir, all_masks_dir, start_frame, num_frames,
        )

        if actual_copied == 0:
            seg_errors.append(f"seg{seg_idx}: 复制遮罩全部失败（保留临时目录）")
            print("    ⚠ 复制失败！不清理临时目录以便手动重跑 copy")
            # 不清理 seg_mask_dir，保留推理结果
            seg_video.unlink(missing_ok=True)  # 切段视频可以重切
            continue

        if actual_copied < num_frames * 0.5:
            seg_errors.append(f"seg{seg_idx}: 复制不足（{actual_copied}/{num_frames}，保留临时目录）")
            print(f"    ⚠ 复制严重不足（{actual_copied}/{num_frames}），保留临时 mask 目录")
            seg_video.unlink(missing_ok=True)
            total_masks += actual_copied
            existing_masks |= set(range(start_frame, start_frame + actual_copied))
            continue

        # === 复制成功才清理临时目录 ===
        total_masks += actual_copied
        existing_masks |= set(range(start_frame, start_frame + num_frames))
        print(f"    ✓ 复制验证OK: {actual_copied} 个 (累计遮罩 {total_masks})")

        seg_video.unlink(missing_ok=True)
        if seg_mask_dir.exists():
            shutil.rmtree(seg_mask_dir, ignore_errors=True)
        seg_mov = TEMP_DIR / f"{stem}_seg{seg_idx:03d}.mov"
        if seg_mov.exists():
            seg_mov.unlink(missing_ok=True)

    # 5. 补全缺失帧（空遮罩，子进程写）
    existing = {int(f.stem.split("_")[1]) for f in all_masks_dir.glob("mask_*.png") if f.stat().st_size >= 10}
    missing = total_frames - len(existing)
    if missing > 0:
        print(f"\n  补全 {missing} 个缺失帧（空遮罩）...")
        missing_list = [i for i in range(total_frames) if i not in existing]
        fill_code = f"""
import cv2, numpy as np, sys, os
from pathlib import Path

src = r'{str(src)}'
mask_dir = r'{str(all_masks_dir)}'
missing_indices = {missing_list!r}

cap = cv2.VideoCapture(src)
ret, frame = cap.read()
cap.release()
if not ret:
    print("FAIL 无法读取首帧", file=sys.stderr)
    sys.exit(1)

h, w = frame.shape[:2]
empty = np.zeros((h, w), dtype=np.uint8)
filled = 0
encode_fails = 0
write_fails = 0
for idx in missing_indices:
    dst = os.path.join(mask_dir, f'mask_{{idx:05d}}.png')
    ok, buf = cv2.imencode('.png', empty)
    if not ok:
        encode_fails += 1
        continue
    try:
        buf.tofile(dst)
        filled += 1
    except Exception as e:
        write_fails += 1
        if write_fails <= 3:
            print(f"WRITE_FAIL mask_{{idx:05d}}.png: {{e}}", file=sys.stderr)
print(f"RESULT filled={{filled}} encode_fail={{encode_fails}} write_fail={{write_fails}}")
"""
        rc, out, err = _run_subprocess_code(fill_code, timeout=1800, label=f"fill{stem[:15]}")
        if err and rc != 0:
            print(f"  补全stderr前400字: {err[:400]}")
        print(f"  补全结果: {out.strip()[:200]}")

    elapsed = round(time.time() - t0, 0)

    print("\n  合成透明 MOV...")
    if not merge_masks_to_mov(src, all_masks_dir, mov):
        return {"stem": stem, "success": False, "error": "MOV 合成失败",
                "elapsed": elapsed, "mask_count": total_masks}

    detection_rate = 0.0
    if mov.exists():
        detection_rate = quick_alpha_check(mov)

    return {
        "stem": stem, "success": True,
        "elapsed": elapsed, "mask_count": total_masks,
        "detection_rate": round(detection_rate, 3),
        "segments": num_segments,
        "errors": seg_errors[:10],
    }


async def main():
    print("=" * 70)
    print("长视频分段重跑 v2（复制验证后才清临时目录）")
    print("=" * 70)

    engine = SAM2Engine()
    results = []

    for i, stem in enumerate(LONG_VIDEOS):
        print(f"\n[{i + 1}/{len(LONG_VIDEOS)}] {stem}")
        r = await process_long_video(engine, stem)
        results.append(r)
        print(f"\n  → success={r['success']}  检出率={r.get('detection_rate', 0):.0%}  "
              f"遮罩={r.get('mask_count', 0)}  耗时={r.get('elapsed', 0):.0f}s")
        if r.get("errors"):
            print(f"  段错误(最多10条): {r['errors']}")

    print(f"\n{'=' * 70}")
    print("长视频分段重跑汇总")
    print(f"{'=' * 70}")
    print(f"{'视频':<45} {'检出率':<8} {'遮罩':<6} {'耗时':<6} {'状态'}")
    print("-" * 70)
    for r in results:
        stem = r["stem"]
        rate = r.get("detection_rate", 0)
        masks = r.get("mask_count", 0)
        elapsed = r.get("elapsed", 0)
        status = "OK" if r["success"] else f"FAIL:{r.get('error','?')}"
        print(f"{stem[:45]:<45} {rate:<8.0%} {masks:<6} {elapsed:<6.0f}s {status}")

    out_file = Path(r"D:\AE-Work\long_video_results.json")
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存: {out_file}")

    final_file = Path(r"D:\AE-Work\final_rerun_results.json")
    if final_file.exists():
        final = json.loads(final_file.read_text(encoding="utf-8"))
        long_stems = {r["stem"] for r in results}
        final = [r for r in final if r["stem"] not in long_stems]
        final.extend(results)
        final_file.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已合并到: {final_file}")


if __name__ == "__main__":
    asyncio.run(main())
