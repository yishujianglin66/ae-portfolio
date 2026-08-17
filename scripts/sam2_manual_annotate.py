"""SAM2 video 传播模式手动标注工具。

用途：对 YOLO 完全检不出人物的动画视频，在 Web UI 中手动点击首帧人物中心点，
     调用 SAM2 video 传播模式生成遮罩序列。

使用流程：
1. 启动: python sam2_manual_annotate.py
2. 浏览器访问 http://127.0.0.1:8777
3. 选择 0% 检出率的视频
4. 在首帧预览图上点击人物中心（可多次点击多个目标）
5. 点击"提交标注"按钮
6. 工具自动调用 SAM2Engine.extract_foreground(mode="video", prompts=...)
7. 显示处理结果和检出率

特点：
- 独立 Web 服务，不干扰批量重跑脚本运行
- 支持多目标标注（每次点击新增一个 positive prompt）
- 支持负点标注（右键点击排除区域）
- 实时显示处理进度
- 处理完成后自动验证检出率
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))

from src.engines.sam2.engine import SAM2Engine

# 配置
SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUT_BASE = Path(r"D:\AE-Work\batch_auto_frame")
PREVIEW_DIR = Path(r"D:\AE-Work\manual_annotate_preview")
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

# 全局状态
_engine: SAM2Engine | None = None
_processing_lock = asyncio.Lock()
_processing_status: dict[str, Any] = {}  # stem -> {status, progress, result}


def get_engine() -> SAM2Engine:
    global _engine
    if _engine is None:
        _engine = SAM2Engine()
    return _engine


def get_frame_count(mov: Path) -> int:
    import subprocess
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(mov)],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def quick_alpha_check(mov: Path, step: int = 200) -> float:
    """快速检查 MOV 的 alpha 检出率。"""
    import subprocess
    total = get_frame_count(mov)
    if total == 0:
        return 0.0
    has_fg = 0
    sampled = 0
    tmp = Path(r"D:\AE-Work\alpha_tmp.png")
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


def extract_first_frame(video_path: Path, output_png: Path) -> bool:
    """提取视频首帧为 PNG 预览图。"""
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return False
    # 编码为 PNG（支持中文路径）
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return False
    buf.tofile(str(output_png))
    return True


def scan_zero_detection_videos() -> list[dict]:
    """扫描所有 0% 检出率的视频。"""
    results = []
    if not SRC_DIR.exists():
        return results

    for mp4 in sorted(SRC_DIR.glob("*.mp4")):
        stem = mp4.stem
        mov = OUT_BASE / stem / f"{stem}_transparent.mov"

        # 检查成品是否存在
        if not mov.exists():
            # 未处理视频，纳入标注列表
            results.append({
                "stem": stem,
                "status": "未处理",
                "detection_rate": None,
                "mov_size_mb": 0,
            })
            continue

        # 快速检测（采样间隔加大，避免阻塞）
        rate = quick_alpha_check(mov, step=300)
        if rate < 0.05:  # 0% 或接近 0%
            results.append({
                "stem": stem,
                "status": f"{rate:.0%}",
                "detection_rate": round(rate, 3),
                "mov_size_mb": round(mov.stat().st_size / 1048576, 1),
            })

    return results


def ensure_preview(stem: str) -> Path:
    """确保首帧预览图存在。"""
    preview = PREVIEW_DIR / f"{stem}.png"
    if preview.exists():
        return preview

    src = SRC_DIR / f"{stem}.mp4"
    if not src.exists():
        raise FileNotFoundError(f"源视频不存在: {src}")

    if not extract_first_frame(src, preview):
        raise RuntimeError(f"提取首帧失败: {src}")

    return preview


# FastAPI 应用
app = FastAPI(title="SAM2 手动标注工具")


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页：列出所有 0% 检出率视频。"""
    videos = scan_zero_detection_videos()
    processing = _processing_status

    video_cards = ""
    for v in videos:
        stem = v["stem"]
        status = v["status"]
        rate = v.get("detection_rate")
        rate_str = f"{rate:.0%}" if rate is not None else "未处理"
        card = f"""
        <div class="card" data-stem="{stem}" onclick="openVideo('{stem}')">
            <div class="card-title">{stem[:60]}</div>
            <div class="card-status">检出率: <span class="rate">{rate_str}</span></div>
            <div class="card-size">大小: {v['mov_size_mb']} MB</div>
            <div class="card-proc" id="proc-{stem}">{processing.get(stem, {}).get('status', '待标注')}</div>
        </div>
        """
        video_cards += card

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>SAM2 手动标注工具</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: #1a1a1a; color: #e0e0e0; margin: 0; padding: 20px; }}
        h1 {{ color: #4fc3f7; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .info {{ background: #2a2a2a; padding: 15px; border-radius: 8px; margin-bottom: 20px;
                 border-left: 4px solid #4fc3f7; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                 gap: 15px; }}
        .card {{ background: #2a2a2a; padding: 15px; border-radius: 8px; cursor: pointer;
                 transition: all 0.2s; border: 1px solid #444; }}
        .card:hover {{ background: #333; border-color: #4fc3f7; transform: translateY(-2px); }}
        .card-title {{ font-size: 13px; font-weight: 600; margin-bottom: 8px;
                       white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .card-status, .card-size {{ font-size: 12px; color: #aaa; margin: 4px 0; }}
        .rate {{ color: #f44336; font-weight: 600; }}
        .card-proc {{ font-size: 11px; color: #888; margin-top: 6px; font-style: italic; }}
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                  background: rgba(0,0,0,0.9); z-index: 1000; }}
        .modal-content {{ max-width: 90%; max-height: 90%; margin: 30px auto; background: #2a2a2a;
                          padding: 20px; border-radius: 8px; position: relative; }}
        .modal-close {{ position: absolute; top: 10px; right: 15px; font-size: 28px;
                        color: #fff; cursor: pointer; }}
        .modal-title {{ color: #4fc3f7; margin-bottom: 15px; word-break: break-all; }}
        .frame-container {{ position: relative; display: inline-block; cursor: crosshair; }}
        .frame-container img {{ max-width: 100%; max-height: 70vh; display: block; }}
        .marker {{ position: absolute; width: 16px; height: 16px; border-radius: 50%;
                   border: 2px solid #fff; transform: translate(-50%, -50%); pointer-events: none; }}
        .marker.positive {{ background: rgba(76, 175, 80, 0.8); }}
        .marker.negative {{ background: rgba(244, 67, 54, 0.8); }}
        .controls {{ margin-top: 15px; padding: 15px; background: #1a1a1a; border-radius: 8px; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;
                font-size: 14px; margin-right: 10px; }}
        .btn-primary {{ background: #4fc3f7; color: #000; }}
        .btn-danger {{ background: #f44336; color: #fff; }}
        .btn-secondary {{ background: #555; color: #fff; }}
        .btn:hover {{ opacity: 0.85; }}
        .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
        .progress {{ margin-top: 10px; padding: 10px; background: #1a1a1a; border-radius: 4px;
                     display: none; }}
        .progress.show {{ display: block; }}
        .legend {{ font-size: 12px; color: #aaa; margin-top: 8px; }}
        .legend span {{ display: inline-block; margin-right: 15px; }}
        .legend .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%;
                        margin-right: 4px; vertical-align: middle; }}
    </style>
</head>
<body>
    <h1>SAM2 手动标注工具</h1>
    <div class="info">
        <strong>使用说明：</strong>
        1. 点击下方视频卡片查看首帧<br>
        2. 在首帧上<strong>左键</strong>点击人物中心点（绿色正点）<br>
        3. 如需排除区域，<strong>右键</strong>点击（红色负点）<br>
        4. 可多次点击标注多个目标<br>
        5. 点击"提交标注"调用 SAM2 video 传播模式重跑<br>
        <strong>适用场景：</strong>YOLO 检测不到的动画人物、非人物角色、特殊画风
    </div>
    <div class="grid">
        {video_cards}
    </div>

    <div class="modal" id="modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeModal()">&times;</span>
            <div class="modal-title" id="modal-title"></div>
            <div class="frame-container" id="frame-container">
                <img id="frame-img" src="" alt="首帧">
            </div>
            <div class="controls">
                <button class="btn btn-primary" id="submit-btn" onclick="submitAnnotation()">提交标注</button>
                <button class="btn btn-secondary" onclick="clearMarkers()">清空标注</button>
                <button class="btn btn-danger" onclick="closeModal()">关闭</button>
                <div class="legend">
                    <span><span class="dot" style="background:#4caf50;"></span>正点（人物中心）</span>
                    <span><span class="dot" style="background:#f44336;"></span>负点（排除区域）</span>
                    <span id="marker-count">已标注: 0 个点</span>
                </div>
            </div>
            <div class="progress" id="progress">
                <div id="progress-text">处理中...</div>
            </div>
        </div>
    </div>

    <script>
        let currentStem = '';
        let markers = [];

        function openVideo(stem) {{
            currentStem = stem;
            document.getElementById('modal-title').textContent = stem;
            document.getElementById('frame-img').src = `/preview-img/${{stem}}`;
            document.getElementById('modal').style.display = 'block';
            clearMarkers();
            document.getElementById('progress').classList.remove('show');
            document.getElementById('submit-btn').disabled = false;
        }}

        function closeModal() {{
            document.getElementById('modal').style.display = 'none';
        }}

        function clearMarkers() {{
            markers = [];
            document.querySelectorAll('.marker').forEach(m => m.remove());
            updateMarkerCount();
        }}

        function updateMarkerCount() {{
            const pos = markers.filter(m => m.type === 'positive').length;
            const neg = markers.filter(m => m.type === 'negative').length;
            document.getElementById('marker-count').textContent =
                `已标注: ${{pos}} 正点 + ${{neg}} 负点`;
        }}

        document.getElementById('frame-container').addEventListener('click', function(e) {{
            if (e.target.tagName !== 'IMG') return;
            e.preventDefault();
            addMarker(e, 'positive');
        }});

        document.getElementById('frame-container').addEventListener('contextmenu', function(e) {{
            if (e.target.tagName !== 'IMG') return;
            e.preventDefault();
            addMarker(e, 'negative');
        }});

        function addMarker(e, type) {{
            const img = e.target;
            const rect = img.getBoundingClientRect();
            const x = Math.round((e.clientX - rect.left) / rect.width * img.naturalWidth);
            const y = Math.round((e.clientY - rect.top) / rect.height * img.naturalHeight);

            const marker = document.createElement('div');
            marker.className = `marker ${{type}}`;
            marker.style.left = `${{(e.clientX - rect.left)}}px`;
            marker.style.top = `${{(e.clientY - rect.top)}}px`;
            document.getElementById('frame-container').appendChild(marker);

            markers.push({{type, x, y}});
            updateMarkerCount();
        }}

        async function submitAnnotation() {{
            if (markers.length === 0) {{
                alert('请至少标注一个正点！');
                return;
            }}
            const positives = markers.filter(m => m.type === 'positive');
            if (positives.length === 0) {{
                alert('至少需要一个正点（左键点击）');
                return;
            }}

            document.getElementById('submit-btn').disabled = true;
            document.getElementById('progress').classList.add('show');
            document.getElementById('progress-text').textContent = '调用 SAM2 video 传播模式...';

            try {{
                const resp = await fetch('/annotate', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        stem: currentStem,
                        markers: markers
                    }})
                }});
                const data = await resp.json();
                if (data.success) {{
                    document.getElementById('progress-text').innerHTML =
                        `<strong style="color:#4caf50;">完成!</strong><br>` +
                        `检出率: ${{(data.detection_rate * 100).toFixed(1)}}%<br>` +
                        `遮罩: ${{data.mask_count}} 帧<br>` +
                        `耗时: ${{data.elapsed}}s`;
                }} else {{
                    document.getElementById('progress-text').innerHTML =
                        `<strong style="color:#f44336;">失败:</strong> ${{data.error}}`;
                }}
            }} catch (err) {{
                document.getElementById('progress-text').innerHTML =
                    `<strong style="color:#f44336;">错误:</strong> ${{err}}`;
            }}
            document.getElementById('submit-btn').disabled = false;
        }}

        // ESC 关闭弹窗
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>
    """


@app.get("/preview/{stem}")
async def preview(stem: str):
    """返回首帧预览图。"""
    try:
        preview = ensure_preview(stem)
        data = preview.read_bytes()
        return JSONResponse({
            "success": True,
            "_image_data": base64.b64encode(data).decode(),
        })
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/preview-img/{stem}")
async def preview_img(stem: str):
    """直接返回 PNG 图片（用于 img src）。"""
    try:
        preview = ensure_preview(stem)
        data = preview.read_bytes()
        return HTMLResponse(
            content=data,
            media_type="image/png",
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/annotate")
async def annotate(request: Request):
    """接收标注并调用 SAM2 video 传播模式。"""
    data = await request.json()
    stem = data["stem"]
    markers = data["markers"]

    # 转换为 SAM2 prompts
    prompts = []
    for m in markers:
        prompts.append({
            "type": m["type"],
            "x": int(m["x"]),
            "y": int(m["y"]),
        })

    # 加锁避免并发
    async with _processing_lock:
        _processing_status[stem] = {"status": "处理中", "start": time.time()}
        try:
            src = SRC_DIR / f"{stem}.mp4"
            out_dir = OUT_BASE / stem
            mov = out_dir / f"{stem}_transparent.mov"

            # 删除旧成品
            if mov.exists():
                mov.unlink()
            import shutil
            for sub in list(out_dir.iterdir()) if out_dir.exists() else []:
                if sub.is_dir():
                    shutil.rmtree(sub, ignore_errors=True)

            engine = get_engine()
            t0 = time.time()
            r = await engine.extract_foreground(
                video_path=src, output_path=mov,
                model_size="base", mode="video",
                prompts=prompts,
            )
            elapsed = round(time.time() - t0, 0)

            if not r.success:
                _processing_status[stem] = {
                    "status": f"失败: {r.error[:100]}",
                    "elapsed": elapsed,
                }
                return {"success": False, "error": r.error, "elapsed": elapsed}

            # 验证检出率
            rate = quick_alpha_check(mov) if mov.exists() else 0.0
            mask_count = r.metadata.get("mask_count", 0)

            _processing_status[stem] = {
                "status": f"完成 ({rate:.0%})",
                "elapsed": elapsed,
                "detection_rate": rate,
                "mask_count": mask_count,
            }

            return {
                "success": True,
                "detection_rate": rate,
                "mask_count": mask_count,
                "elapsed": elapsed,
            }

        except Exception as e:
            _processing_status[stem] = {"status": f"异常: {str(e)[:100]}"}
            return {"success": False, "error": str(e)}


@app.get("/status")
async def status():
    """返回所有处理状态。"""
    return _processing_status


def main():
    import uvicorn
    print("=" * 70)
    print("SAM2 手动标注工具")
    print("=" * 70)
    print(f"源视频目录: {SRC_DIR}")
    print(f"成品目录:   {OUT_BASE}")
    print(f"预览目录:   {PREVIEW_DIR}")
    print()

    # 预扫描
    print("扫描 0% 检出率视频...")
    videos = scan_zero_detection_videos()
    print(f"发现 {len(videos)} 个视频需要手动标注:")
    for v in videos:
        print(f"  - {v['stem'][:60]}  检出率={v['status']}")

    print()
    print("启动 Web 服务: http://127.0.0.1:8777")
    print("按 Ctrl+C 退出")
    print()

    uvicorn.run(app, host="127.0.0.1", port=8777, log_level="warning")


if __name__ == "__main__":
    main()
