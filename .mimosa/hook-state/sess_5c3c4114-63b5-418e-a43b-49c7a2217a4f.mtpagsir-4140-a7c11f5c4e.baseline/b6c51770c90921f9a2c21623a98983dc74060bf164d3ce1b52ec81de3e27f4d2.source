#!/usr/bin/env python3
"""
P3.2: Web UI 可视化面板 - 风格分析 + 预览 + 导出

功能：
1. 视频上传与风格分析
2. 分类结果可视化（Top-5概率、特征雷达图）
3. JSX脚本预览与下载
4. 用户反馈（评分/修正）
5. 批量任务管理
6. 系统状态监控

启动：
    python scripts/web_ui.py --port 8765
    访问 http://localhost:8765
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("需要安装: pip install fastapi uvicorn python-multipart")
    sys.exit(1)

app = FastAPI(title="漫剪风格管线 Web UI", version="2.0.0")

# 上传目录
UPLOAD_DIR = PROJECT_ROOT / "output" / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页面"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>漫剪风格管线</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; margin: 20px 0; color: #00d4ff; font-size: 2em; }
        .upload-zone { border: 2px dashed #444; border-radius: 12px; padding: 40px; text-align: center; margin: 20px 0; cursor: pointer; transition: all 0.3s; }
        .upload-zone:hover { border-color: #00d4ff; background: rgba(0,212,255,0.05); }
        .upload-zone.dragover { border-color: #00ff88; background: rgba(0,255,136,0.1); }
        .btn { background: #00d4ff; color: #000; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; }
        .btn:hover { background: #00ff88; }
        .btn:disabled { background: #555; cursor: not-allowed; }
        .result-card { background: #16213e; border-radius: 12px; padding: 20px; margin: 15px 0; border: 1px solid #333; }
        .style-badge { display: inline-block; background: #00d4ff; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; margin: 5px; }
        .prob-bar { height: 24px; background: #333; border-radius: 12px; overflow: hidden; margin: 5px 0; }
        .prob-fill { height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 12px; transition: width 0.5s; display: flex; align-items: center; padding-left: 10px; font-size: 12px; color: #000; font-weight: bold; }
        .feedback-section { margin-top: 15px; padding-top: 15px; border-top: 1px solid #333; }
        .stars { font-size: 24px; cursor: pointer; }
        .stars span { color: #555; }
        .stars span.active { color: #ffd700; }
        .status-bar { background: #0f3460; padding: 10px 20px; border-radius: 8px; margin: 10px 0; font-size: 14px; }
        .jsx-preview { background: #0d1117; border-radius: 8px; padding: 15px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; white-space: pre-wrap; color: #7ee787; }
        select, input { background: #16213e; color: #eee; border: 1px solid #444; padding: 8px 12px; border-radius: 6px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 漫剪风格管线</h1>
        <div class="status-bar" id="status">系统就绪 | 支持23种风格分类 | 5种差异化视觉效果</div>
        
        <div class="upload-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
            <p style="font-size: 48px;">📁</p>
            <p>拖拽视频文件到此处，或点击选择</p>
            <p style="color: #888; font-size: 14px;">支持 MP4 / MKV / WebM</p>
            <input type="file" id="fileInput" accept="video/*" style="display:none" onchange="handleFile(this.files[0])">
        </div>

        <div id="results"></div>
    </div>

    <script>
        const dropZone = document.getElementById('dropZone');
        dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFile(e.dataTransfer.files[0]); });

        async function handleFile(file) {
            if (!file) return;
            document.getElementById('status').textContent = '⏳ 分析中: ' + file.name;
            const formData = new FormData();
            formData.append('file', file);
            try {
                const resp = await fetch('/api/analyze', { method: 'POST', body: formData });
                const data = await resp.json();
                renderResult(data);
                document.getElementById('status').textContent = '✓ 分析完成: ' + data.style + ' (' + (data.confidence*100).toFixed(1) + '%)';
            } catch(e) {
                document.getElementById('status').textContent = '✗ 分析失败: ' + e.message;
            }
        }

        function renderResult(data) {
            const probs = Object.entries(data.probabilities || {}).sort((a,b) => b[1]-a[1]).slice(0,5);
            let probHtml = probs.map(([style, p]) => 
                `<div style="margin:3px 0"><span style="width:150px;display:inline-block">${style}</span><div class="prob-bar" style="display:inline-block;width:60%;vertical-align:middle"><div class="prob-fill" style="width:${p*100}%">${(p*100).toFixed(1)}%</div></div></div>`
            ).join('');
            
            document.getElementById('results').innerHTML = `
                <div class="result-card">
                    <h3>分析结果</h3>
                    <p>风格: <span class="style-badge">${data.style}</span> 置信度: ${(data.confidence*100).toFixed(1)}%</p>
                    <p>延迟: ${data.latency_ms?.toFixed(0) || 0}ms</p>
                    <h4 style="margin-top:10px">Top-5 概率:</h4>
                    ${probHtml}
                </div>
                <div class="result-card">
                    <h3>JSX 脚本预览</h3>
                    <div class="jsx-preview">${(data.jsx_content || '生成中...').substring(0, 2000)}</div>
                    <button class="btn" style="margin-top:10px" onclick="downloadJsx('${data.jsx_path || ''}')">下载 JSX</button>
                </div>
                <div class="result-card feedback-section">
                    <h3>反馈</h3>
                    <p>这个分类准确吗？</p>
                    <div class="stars" onclick="rate(event)">
                        <span data-v="1">★</span><span data-v="2">★</span><span data-v="3">★</span><span data-v="4">★</span><span data-v="5">★</span>
                    </div>
                    <select id="correctStyle" style="margin:10px 0">
                        <option value="">-- 修正为 --</option>
                        ${Object.keys(data.all_styles || {}).map(s => `<option value="${s}">${s}</option>`).join('')}
                    </select>
                    <button class="btn" onclick="submitFeedback('${data.video || ''}', '${data.style}')">提交反馈</button>
                </div>
            `;
        }

        let currentRating = 0;
        function rate(e) {
            currentRating = parseInt(e.target.dataset.v || 0);
            document.querySelectorAll('.stars span').forEach((s,i) => s.classList.toggle('active', i < currentRating));
        }

        async function submitFeedback(video, predicted) {
            const correction = document.getElementById('correctStyle').value || null;
            await fetch('/api/feedback', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ video, predicted, user_label: correction, rating: currentRating })
            });
            alert('反馈已提交，感谢！');
        }

        function downloadJsx(path) { if(path) window.open('/api/download?path=' + encodeURIComponent(path)); }
    </script>
</body>
</html>
    """


@app.post("/api/analyze")
async def analyze_video(file: UploadFile = File(..., max_length=512 * 1024 * 1024)):
    """分析上传的视频"""
    # 保存文件
    safe_name = Path(file.filename).name
    save_path = UPLOAD_DIR / safe_name
    content = await file.read()
    save_path.write_bytes(content)

    # 运行管线
    from core.style_pipeline import analyze_video_style
    from core.style_preset_adapter import style_to_atomic_params, STYLE_PRESET_MAP
    from core.jsx_generator import generate_jsx_from_style

    result = await analyze_video_style(str(save_path), enable_vision=False)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    style = result["style"]
    confidence = result["confidence"]
    atomic_params = style_to_atomic_params(style, confidence)

    # 生成JSX
    jsx_content = generate_jsx_from_style(
        style=style,
        confidence=confidence,
        atomic_params=atomic_params,
        video_path=str(save_path),
    )

    # 保存JSX
    jsx_path = UPLOAD_DIR / f"{save_path.stem}_{style}.jsx"
    jsx_path.write_text(jsx_content, encoding="utf-8")

    return {
        "video": file.filename,
        "style": style,
        "confidence": confidence,
        "probabilities": result.get("probabilities", {}),
        "features": result.get("features", []),
        "latency_ms": result.get("latency_ms", 0),
        "jsx_path": str(jsx_path),
        "jsx_content": jsx_content[:3000],
        "all_styles": {k: True for k in STYLE_PRESET_MAP.keys()},
    }


@app.post("/api/feedback")
async def submit_feedback(data: Dict):
    """提交用户反馈"""
    from core.feedback_loop import FeedbackLoop

    fb = FeedbackLoop()
    record = fb.record(
        video=data.get("video", ""),
        predicted=data.get("predicted", ""),
        user_label=data.get("user_label"),
        rating=data.get("rating"),
    )
    return {"success": True, "record": record}


@app.get("/api/download")
async def download_file(path: str):
    """下载文件"""
    file_path = Path(path).resolve()
    allowed_root = PROJECT_ROOT.resolve()
    if not str(file_path).startswith(str(allowed_root)):
        raise HTTPException(status_code=403, detail="禁止访问该路径")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, filename=file_path.name)


@app.get("/api/status")
async def system_status():
    """系统状态"""
    from scripts.ae_automation import is_ae_running, health_check

    return {
        "ae_running": is_ae_running(),
        "styles_supported": 23,
        "differentiated_styles": 23,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="漫剪风格管线 Web UI")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  漫剪风格管线 Web UI")
    print(f"  访问: http://localhost:{args.port}")
    print(f"{'='*50}\n")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
