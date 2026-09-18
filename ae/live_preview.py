"""
Live Preview — 实时预览管道
===========================
提供剪辑过程中的实时预览能力，支持本地预览和远程流式传输。

核心能力:
- 本地 OpenCV 预览窗口
- WebSocket 流式推送（浏览器预览）
- NDI 网络预览（专业广播）
- 帧缓存管理
- 低延迟渲染管道
- 预览标记叠加（时间码/安全框/字幕/调色LUT）

依赖:
    pip install opencv-python flask-socketio numpy pillow

用法:
    preview = LivePreview()
    preview.serve_websocket(port=5001)
    preview.push_frame(frame)  # 推送帧
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================
class PreviewMode(Enum):
    LOCAL = "local"             # 本地 OpenCV 窗口
    WEBSOCKET = "websocket"     # WebSocket 浏览器
    NDI = "ndi"                 # NDI 专业广播
    RTSP = "rtsp"               # RTSP 流


@dataclass
class PreviewOverlay:
    """预览叠加信息"""
    timecode: str | None = None
    frame_number: int | None = None
    subtitle: str | None = None
    safe_zone: bool = True      # 安全框
    grid: bool = False          # 三分构图线
    histogram: bool = False     # 直方图
    waveform: bool = False      # 波形图


@dataclass
class PreviewConfig:
    """预览配置"""
    width: int = 1280
    height: int = 720
    fps: float = 30.0
    mode: PreviewMode = PreviewMode.LOCAL
    quality: int = 80            # JPEG 质量 (WebSocket模式)
    overlay: PreviewOverlay = field(default_factory=PreviewOverlay)
    apply_lut: str | None = None  # LUT 文件路径


# ================================================================
#  帧缓存
# ================================================================
class FrameBuffer:
    """帧缓存管理"""

    def __init__(self, max_frames: int = 300):
        self.max_frames = max_frames
        self._frames: dict[int, Any] = {}
        self._keys: deque = deque()
        self._lock = threading.Lock()

    def put(self, frame_number: int, frame: Any):
        with self._lock:
            if frame_number in self._frames:
                self._keys.remove(frame_number)
            self._keys.append(frame_number)
            self._frames[frame_number] = frame.copy() if hasattr(frame, 'copy') else frame

            # 淘汰旧帧
            while len(self._keys) > self.max_frames:
                old_key = self._keys.popleft()
                del self._frames[old_key]

    def get(self, frame_number: int) -> Any | None:
        with self._lock:
            return self._frames.get(frame_number)

    def get_latest(self) -> tuple[int, Any] | None:
        with self._lock:
            if self._keys:
                key = self._keys[-1]
                return key, self._frames[key]
            return None

    def get_range(self, start: int, end: int) -> list[Any]:
        with self._lock:
            return [self._frames.get(k) for k in self._keys if start <= k <= end and k in self._frames]

    def clear(self):
        with self._lock:
            self._frames.clear()
            self._keys.clear()

    @property
    def size(self) -> int:
        return len(self._frames)


# ================================================================
#  实时预览引擎
# ================================================================
class LivePreview:
    """实时预览管道引擎"""

    def __init__(self, config: PreviewConfig = None):
        self.config = config or PreviewConfig()
        self.frame_buffer = FrameBuffer(max_frames=300)
        self._running = False
        self._threads: list[threading.Thread] = []
        self._clients: dict[str, Any] = {}
        self._frame_queue: queue.Queue = queue.Queue(maxsize=30)

        # 统计
        self._frames_pushed = 0
        self._frames_displayed = 0
        self._start_time = 0.0

    # ================================================================
    #  帧推送
    # ================================================================
    def push_frame(
        self,
        frame: Any,
        frame_number: int = None,
        overlay: PreviewOverlay = None,
    ):
        """
        推送帧到预览管道。

        Args:
            frame: numpy array (H, W, 3) BGR
            frame_number: 帧号（用于时间码显示）
            overlay: 叠加信息覆盖
        """
        import cv2
        import numpy as np

        if frame_number is None:
            frame_number = self._frames_pushed

        # 应用 LUT
        if self.config.apply_lut and os.path.exists(self.config.apply_lut):
            frame = self._apply_lut(frame, self.config.apply_lut)

        # 缩放
        if frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
            frame = cv2.resize(frame, (self.config.width, self.config.height))

        # 叠加信息
        ov = overlay or self.config.overlay
        frame = self._draw_overlay(frame, frame_number, ov)

        # 存入帧缓存
        self.frame_buffer.put(frame_number, frame)

        # 推送到队列
        try:
            self._frame_queue.put_nowait((frame_number, frame))
        except queue.Full:
            pass  # 丢弃旧帧，保证实时性

        self._frames_pushed += 1

    def _draw_overlay(self, frame: Any, frame_number: int, overlay: PreviewOverlay) -> Any:
        """在帧上绘制叠加信息"""
        import cv2

        h, w = frame.shape[:2]

        # 时间码
        if overlay.timecode or overlay.frame_number is not None:
            fn = overlay.frame_number or frame_number
            tc = overlay.timecode or self._frame_to_tc(fn)
            cv2.putText(frame, tc, (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, (255, 255, 255), 2, cv2.LINE_AA)

        # 帧号
        if overlay.frame_number is not None:
            cv2.putText(frame, f"#{frame_number}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # 安全框
        if overlay.safe_zone:
            action = (int(w * 0.05), int(h * 0.05), int(w * 0.95), int(h * 0.95))
            title = (int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9))
            cv2.rectangle(frame, (action[0], action[1]), (action[2], action[3]), (0, 255, 255), 1)
            cv2.rectangle(frame, (title[0], title[1]), (title[2], title[3]), (0, 200, 255), 1)

        # 三分构图线
        if overlay.grid:
            cv2.line(frame, (w // 3, 0), (w // 3, h), (255, 255, 255), 1)
            cv2.line(frame, (2 * w // 3, 0), (2 * w // 3, h), (255, 255, 255), 1)
            cv2.line(frame, (0, h // 3), (w, h // 3), (255, 255, 255), 1)
            cv2.line(frame, (0, 2 * h // 3), (w, 2 * h // 3), (255, 255, 255), 1)

        return frame

    def _apply_lut(self, frame: Any, lut_path: str) -> Any:
        """应用 3D LUT"""
        import cv2
        import numpy as np

        try:
            lut_data = cv2.imread(lut_path, cv2.IMREAD_ANYCOLOR)
            if lut_data is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.LUT(frame, lut_data)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception:
            pass
        return frame

    # ================================================================
    #  本地预览
    # ================================================================
    def start_local_preview(self, window_name: str = "AE Preview") -> threading.Thread:
        """启动本地 OpenCV 预览窗口"""
        if self._running:
            return None

        self._running = True
        self._start_time = time.time()

        thread = threading.Thread(
            target=self._local_preview_loop,
            args=(window_name,),
            daemon=True,
        )
        thread.start()
        self._threads.append(thread)
        return thread

    def _local_preview_loop(self, window_name: str):
        """本地预览循环"""
        import cv2

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, self.config.width, self.config.height)

        while self._running:
            try:
                _, frame = self._frame_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            cv2.imshow(window_name, frame)
            self._frames_displayed += 1

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                self._running = False
            elif key == 32:  # Space
                cv2.waitKey(0)  # 暂停

        cv2.destroyWindow(window_name)

    # ================================================================
    #  WebSocket 预览
    # ================================================================
    def serve_websocket(self, host: str = "127.0.0.1", port: int = 5001):
        """启动 WebSocket 预览服务器"""
        import threading
        self._running = True
        self._ws_config = {"host": host, "port": port}

        thread = threading.Thread(
            target=self._websocket_server_loop,
            args=(host, port),
            daemon=True,
        )
        thread.start()
        self._threads.append(thread)

    def _websocket_server_loop(self, host: str, port: int):
        """WebSocket 服务器循环"""
        try:
            import cv2
            from flask import Flask, Response
            from flask_socketio import SocketIO, emit

            app = Flask(__name__)
            app.config['SECRET_KEY'] = 'ae-preview'
            socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

            @socketio.on('connect')
            def handle_connect():
                client_id = id(threading.current_thread())
                self._clients[str(client_id)] = time.time()
                client_count = len(self._clients)

            @socketio.on('disconnect')
            def handle_disconnect():
                client_id = str(id(threading.current_thread()))
                self._clients.pop(client_id, None)

            def broadcast_frames():
                while self._running:
                    try:
                        _, frame = self._frame_queue.get(timeout=0.1)
                    except queue.Empty:
                        socketio.sleep(0.01)
                        continue

                    if self._clients:
                        _, jpeg = cv2.imencode(
                            '.jpg', frame,
                            [cv2.IMWRITE_JPEG_QUALITY, self.config.quality]
                        )
                        b64 = base64.b64encode(jpeg).decode('utf-8')
                        socketio.emit('frame', {
                            'image': b64,
                            'frame_number': self._frames_pushed,
                            'timestamp': time.time(),
                        })
                    socketio.sleep(0.001)

            socketio.start_background_task(broadcast_frames)
            socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)

        except ImportError:
            print("[LivePreview] flask-socketio not installed. Run: pip install flask-socketio")
            self._running = False

    def get_websocket_html(self) -> str:
        """生成 WebSocket 预览客户端 HTML"""
        host = getattr(self, '_ws_config', {}).get('host', '127.0.0.1')
        port = getattr(self, '_ws_config', {}).get('port', 5001)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>AE Live Preview</title>
    <style>
        body {{ margin: 0; background: #1a1a2e; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
        #preview {{ max-width: 100vw; max-height: 100vh; border: 2px solid #333; }}
        #info {{ position: fixed; top: 10px; left: 10px; color: #fff; font-family: monospace; background: rgba(0,0,0,0.7); padding: 8px 12px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div id="info">Frame: -- | FPS: --</div>
    <img id="preview" src="" alt="Preview">

    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <script>
        const socket = io('http://{host}:{port}');
        const img = document.getElementById('preview');
        const info = document.getElementById('info');
        let lastTime = Date.now();
        let frameCount = 0;
        let fps = 0;

        socket.on('frame', (data) => {{
            img.src = 'data:image/jpeg;base64,' + data.image;
            frameCount++;
            const now = Date.now();
            if (now - lastTime > 1000) {{
                fps = Math.round(frameCount / ((now - lastTime) / 1000));
                info.textContent = 'Frame: ' + data.frame_number + ' | FPS: ' + fps;
                frameCount = 0;
                lastTime = now;
            }}
        }});
    </script>
</body>
</html>"""

    # ================================================================
    #  NDI 预览
    # ================================================================
    def start_ndi_preview(self, source_name: str = "AE-Knowledge-Vault") -> threading.Thread:
        """启动 NDI 预览（需要 NDI SDK）"""
        try:
            import cv2

            # NDI 需要额外安装
            # pip install ndi-python
            import NDIlib as ndi
            import numpy as np
        except ImportError:
            print("[LivePreview] NDI SDK not installed. Visit: https://ndi.video")
            return None

        self._running = True

        thread = threading.Thread(
            target=self._ndi_preview_loop,
            args=(source_name,),
            daemon=True,
        )
        thread.start()
        self._threads.append(thread)
        return thread

    def _ndi_preview_loop(self, source_name: str):
        """NDI 发送循环"""
        try:
            import NDIlib as ndi
            import numpy as np

            ndi_send = ndi.send_create()
            if not ndi_send:
                print("[LivePreview] Failed to create NDI sender")
                return

            video_frame = ndi.VideoFrameV2()

            while self._running:
                try:
                    _, frame = self._frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 转换为 NDI 格式 (BGR -> BGRA)
                bgra = np.zeros((self.config.height, self.config.width, 4), dtype=np.uint8)
                bgra[:, :, :3] = frame[:, :, :3]
                bgra[:, :, 3] = 255

                video_frame.data = bgra
                video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRX
                video_frame.frame_rate_N = int(self.config.fps * 1000)
                video_frame.frame_rate_D = 1000

                ndi.send_send_video_v2(ndi_send, video_frame)

            ndi.send_destroy(ndi_send)

        except Exception as e:
            print(f"[LivePreview] NDI error: {e}")

    # ================================================================
    #  RTSP 预览
    # ================================================================
    def start_rtsp_preview(self, port: int = 8554, stream_name: str = "ae_preview"):
        """启动 RTSP 流式预览（使用 GStreamer/FFmpeg）"""
        info = {
            "url": f"rtsp://localhost:{port}/{stream_name}",
            "command": (
                f"ffmpeg -f rawvideo -pixel_format bgr24 "
                f"-video_size {self.config.width}x{self.config.height} "
                f"-framerate {self.config.fps} -i - "
                f"-c:v libx264 -preset ultrafast -tune zerolatency "
                f"-f rtsp rtsp://localhost:{port}/{stream_name}"
            ),
        }
        return info

    # ================================================================
    #  统计
    # ================================================================
    def get_stats(self) -> dict[str, Any]:
        """获取预览统计"""
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0
        return {
            "running": self._running,
            "frames_pushed": self._frames_pushed,
            "frames_displayed": self._frames_displayed,
            "fps_pushed": round(self._frames_pushed / max(1, elapsed), 1),
            "fps_displayed": round(self._frames_displayed / max(1, elapsed), 1),
            "buffer_size": self.frame_buffer.size,
            "queue_size": self._frame_queue.qsize(),
            "clients": len(self._clients),
            "mode": self.config.mode.value,
        }

    def stop(self):
        """停止预览"""
        self._running = False
        for t in self._threads:
            t.join(timeout=2.0)
        self.frame_buffer.clear()

    @staticmethod
    def _frame_to_tc(frame_number: int, fps: float = 30.0) -> str:
        total_seconds = frame_number / fps
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        s = int(total_seconds % 60)
        f = int((total_seconds - int(total_seconds)) * fps)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


__all__ = [
    "LivePreview",
    "PreviewMode",
    "PreviewConfig",
    "PreviewOverlay",
    "FrameBuffer",
]
