"""
AutoDownloader - 自动化下载调度器
================================

智能下载调度器，支持多种下载引擎：
- aria2 (主力): 支持磁力/HTTP/BT/FTP 全协议，JSON-RPC 控制
- FileCxx (备选): 文件快传，P2P加速
- yt-dlp (专用): 视频平台下载

工作流:
1. 接收下载任务 (磁力链接/HTTP URL/文件路径)
2. 选择最佳下载引擎
3. 自动下载并监控进度
4. 下载完成后触发回调

用法:
    from auto_downloader import AutoDownloader
    
    downloader = AutoDownloader()
    result = downloader.download("magnet:?xt=urn:btih:xxx", output_dir="D:/AE-Work/素材")
"""

import os
import sys
import json
import time
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  下载引擎类型
# ================================================================
class EngineType(Enum):
    ARIA2 = "aria2"
    FILECXX = "filecxx"
    YTDLP = "ytdlp"


# ================================================================
#  下载任务状态
# ================================================================
@dataclass
class DownloadTask:
    url: str
    output_dir: str
    filename: Optional[str] = None
    engine: EngineType = EngineType.ARIA2
    status: str = "pending"  # pending, downloading, completed, failed
    progress: float = 0.0
    speed: str = ""
    size: str = ""
    error: str = ""
    gid: str = ""  # aria2 download ID
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "output_dir": self.output_dir,
            "filename": self.filename,
            "engine": self.engine.value,
            "status": self.status,
            "progress": self.progress,
            "speed": self.speed,
            "size": self.size,
            "error": self.error,
            "gid": self.gid,
            "duration": (self.end_time or time.time()) - self.start_time,
        }


# ================================================================
#  aria2 JSON-RPC 客户端
# ================================================================
class Aria2RPC:
    """aria2 JSON-RPC 客户端"""
    
    def __init__(self, port: int = 6800, secret: str = ""):
        self.port = port
        self.secret = secret
        self.url = f"http://127.0.0.1:{port}/jsonrpc"
        self._id_counter = 0
    
    def _call(self, method: str, params: List = None) -> Dict:
        """调用 JSON-RPC 方法"""
        self._id_counter += 1
        payload = {
            "jsonrpc": "2.0",
            "id": str(self._id_counter),
            "method": method,
            "params": params or [],
        }
        
        if self.secret:
            payload["params"].insert(0, f"token:{self.secret}")
        
        try:
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e)}
    
    def add_uri(self, uri: str, options: Dict = None) -> str:
        """添加下载任务"""
        params = [[uri]]
        if options:
            params.append(options)
        result = self._call("aria2.addUri", params)
        return result.get("result", "")
    
    def add_torrent(self, torrent_path: str, options: Dict = None) -> str:
        """添加BT种子"""
        import base64
        with open(torrent_path, "rb") as f:
            torrent_data = base64.b64encode(f.read()).decode("utf-8")
        params = [torrent_data, [], options or {}]
        result = self._call("aria2.addTorrent", params)
        return result.get("result", "")
    
    def tell_status(self, gid: str) -> Dict:
        """查询任务状态"""
        result = self._call("aria2.tellStatus", [gid])
        return result.get("result", {})
    
    def tell_active(self) -> List:
        """查询活跃任务"""
        result = self._call("aria2.tellActive", [])
        return result.get("result", [])
    
    def remove(self, gid: str) -> bool:
        """移除任务"""
        result = self._call("aria2.remove", [gid])
        return "result" in result
    
    def pause(self, gid: str) -> bool:
        """暂停任务"""
        result = self._call("aria2.pause", [gid])
        return "result" in result
    
    def unpause(self, gid: str) -> bool:
        """恢复任务"""
        result = self._call("aria2.unpause", [gid])
        return "result" in result
    
    def get_global_stat(self) -> Dict:
        """获取全局统计"""
        result = self._call("aria2.getGlobalStat", [])
        return result.get("result", {})


# ================================================================
#  aria2 下载引擎
# ================================================================
class Aria2Engine:
    """aria2 下载引擎"""
    
    ARIA2_PATH = r"C:\aria2\aria2-1.37.0-win-64bit-build1\aria2c.exe"
    DEFAULT_PORT = 6800
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.rpc: Optional[Aria2RPC] = None
        self._started = False
    
    def is_available(self) -> bool:
        return Path(self.ARIA2_PATH).exists()
    
    def start_daemon(self, download_dir: str = None) -> bool:
        """启动 aria2 守护进程"""
        if self._started:
            return True
        
        if not self.is_available():
            log(f"aria2 未找到: {self.ARIA2_PATH}", "ERROR")
            return False
        
        try:
            cmd = [
                self.ARIA2_PATH,
                "--enable-rpc",
                f"--rpc-listen-port={self.DEFAULT_PORT}",
                "--rpc-allow-origin-all",
                "--continue",
                "--max-connection-per-server=16",
                "--split=16",
                "--min-split-size=1M",
                "--max-tries=10",
                "--retry-wait=5",
                "--bt-stop-timeout=300",
                "--seed-time=0",  # 不上传
                # BT 优化配置
                "--enable-dht=true",
                "--enable-dht6=true",
                "--bt-enable-lpd=true",
                "--bt-max-peers=80",
                "--bt-request-peer-speed-limit=1M",
                "--follow-torrent=mem",
                "--peer-agent=aria2/1.37.0",
                "--peer-id-prefix=-AR2037-",
                "--file-allocation=none",  # 不预分配，加快速度
            ]
            
            if download_dir:
                cmd.append(f"--dir={download_dir}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            
            # 等待 RPC 就绪
            time.sleep(1)
            self.rpc = Aria2RPC(self.DEFAULT_PORT)
            
            # 验证连接
            stat = self.rpc.get_global_stat()
            if "error" not in stat:
                self._started = True
                log(f"aria2 守护进程已启动 (PID: {self.process.pid})")
                return True
            
        except Exception as e:
            log(f"aria2 启动失败: {e}", "ERROR")
        
        return False
    
    def stop_daemon(self):
        """停止守护进程"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self._started = False
            log("aria2 守护进程已停止")
    
    def download(self, url: str, output_dir: str, filename: str = None) -> DownloadTask:
        """下载文件"""
        task = DownloadTask(url=url, output_dir=output_dir, filename=filename, engine=EngineType.ARIA2)
        
        if not self._started:
            if not self.start_daemon(output_dir):
                task.status = "failed"
                task.error = "aria2 启动失败"
                return task
        
        # 构建选项
        options = {"dir": output_dir}
        if filename:
            options["out"] = filename
        
        # 添加任务
        gid = self.rpc.add_uri(url, options)
        if not gid:
            task.status = "failed"
            task.error = "添加任务失败"
            return task
        
        task.gid = gid
        task.status = "downloading"
        log(f"aria2 下载开始: {url[:50]}... (GID: {gid})")
        
        return task
    
    def check_progress(self, gid: str) -> Dict:
        """检查下载进度"""
        if not self.rpc:
            return {"status": "error", "error": "RPC未连接"}
        
        status = self.rpc.tell_status(gid)
        if not status:
            return {"status": "error", "error": "任务不存在"}
        
        total = int(status.get("totalLength", 0))
        completed = int(status.get("completedLength", 0))
        speed = int(status.get("downloadSpeed", 0))
        
        progress = (completed / total * 100) if total > 0 else 0
        
        return {
            "status": status.get("status", "unknown"),
            "progress": round(progress, 1),
            "speed": f"{speed / 1024 / 1024:.2f} MB/s",
            "size": f"{completed / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB",
            "files": [f.get("path", "") for f in status.get("files", [])],
        }
    
    def wait_complete(self, gid: str, timeout: int = 3600) -> DownloadTask:
        """等待下载完成"""
        task = DownloadTask(url="", output_dir="", gid=gid, engine=EngineType.ARIA2)
        start = time.time()
        
        while time.time() - start < timeout:
            progress = self.check_progress(gid)
            task.progress = progress.get("progress", 0)
            task.speed = progress.get("speed", "")
            task.size = progress.get("size", "")
            
            status = progress.get("status", "")
            if status == "complete":
                task.status = "completed"
                task.end_time = time.time()
                files = progress.get("files", [])
                if files:
                    task.filename = Path(files[0]).name
                log(f"下载完成: {task.filename} ({task.size})")
                return task
            elif status == "error" or status == "removed":
                task.status = "failed"
                task.error = f"下载失败: {status}"
                task.end_time = time.time()
                return task
            
            # 打印进度
            print(f"\r  进度: {task.progress}% | 速度: {task.speed} | {task.size}", end="", flush=True)
            time.sleep(2)
        
        task.status = "failed"
        task.error = f"下载超时 ({timeout}s)"
        task.end_time = time.time()
        return task


# ================================================================
#  FileCxx 下载引擎 (备选)
# ================================================================
class FileCxxEngine:
    """FileCxx 文件快传引擎 (备选)"""
    
    FILEC_PATH = r"D:\BaiduNetdiskDownload\素材网站\磁力链接下载软件+教程\filecxx_latest_win_x64\lib\filec.exe"
    DEFAULT_PORT = 10111
    
    def __init__(self):
        self._started = False
    
    def is_available(self) -> bool:
        return Path(self.FILEC_PATH).exists()
    
    def start_daemon(self) -> bool:
        """启动 FileCxx 守护进程 (需要管理员权限)"""
        if self._started:
            return True
        
        try:
            result = subprocess.run(
                [self.FILEC_PATH, "-y"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self._started = True
                log("FileCxx 守护进程已启动")
                return True
            else:
                log(f"FileCxx 启动失败 (可能需要管理员权限): {result.stderr}", "WARN")
        except Exception as e:
            log(f"FileCxx 启动失败: {e}", "WARN")
        
        return False
    
    def download(self, url: str, output_dir: str, filename: str = None) -> DownloadTask:
        """下载文件 (通过命令行)"""
        task = DownloadTask(url=url, output_dir=output_dir, filename=filename, engine=EngineType.FILECXX)
        
        # FileCxx 命令行添加任务
        cmd = [self.FILEC_PATH, "-c", f"add {url}"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                task.status = "downloading"
                log(f"FileCxx 下载开始: {url[:50]}...")
            else:
                task.status = "failed"
                task.error = f"添加任务失败: {result.stderr}"
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
        
        return task


# ================================================================
#  自动下载调度器
# ================================================================
class AutoDownloader:
    """智能下载调度器"""
    
    def __init__(self, default_output_dir: str = None):
        self.default_output_dir = default_output_dir or r"D:\AE-Work\素材"
        Path(self.default_output_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化引擎
        self.aria2 = Aria2Engine()
        self.filecxx = FileCxxEngine()
        
        # 任务历史
        self.tasks: List[DownloadTask] = []
    
    def download(self, url: str, output_dir: str = None, 
                 filename: str = None, engine: EngineType = None) -> DownloadTask:
        """
        下载文件 (自动选择引擎)
        
        Args:
            url: 下载链接 (磁力/HTTP/BT)
            output_dir: 输出目录
            filename: 输出文件名
            engine: 指定引擎 (None=自动选择)
        
        Returns:
            DownloadTask 对象
        """
        output_dir = output_dir or self.default_output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 自动选择引擎
        if engine is None:
            engine = self._select_engine(url)
        
        log(f"下载: {url[:60]}...")
        log(f"引擎: {engine.value} | 目录: {output_dir}")
        
        # 执行下载
        if engine == EngineType.ARIA2:
            task = self.aria2.download(url, output_dir, filename)
        elif engine == EngineType.FILECXX:
            task = self.filecxx.download(url, output_dir, filename)
        else:
            task = DownloadTask(url=url, output_dir=output_dir, status="failed", error="未知引擎")
        
        self.tasks.append(task)
        return task
    
    def download_batch(self, urls: List[str], output_dir: str = None) -> List[DownloadTask]:
        """批量下载"""
        tasks = []
        for url in urls:
            task = self.download(url, output_dir)
            tasks.append(task)
        return tasks
    
    def download_magnet(self, magnet: str, output_dir: str = None) -> DownloadTask:
        """下载磁力链接"""
        return self.download(magnet, output_dir)
    
    def download_http(self, url: str, output_dir: str = None, 
                      filename: str = None) -> DownloadTask:
        """下载 HTTP 链接"""
        return self.download(url, output_dir, filename)
    
    def wait_all(self, timeout: int = 7200) -> List[DownloadTask]:
        """等待所有任务完成"""
        results = []
        for task in self.tasks:
            if task.status == "downloading" and task.gid:
                result = self.aria2.wait_complete(task.gid, timeout)
                results.append(result)
        return results
    
    def _select_engine(self, url: str) -> EngineType:
        """智能选择下载引擎"""
        url_lower = url.lower()
        
        # 磁力链接 → aria2
        if url_lower.startswith("magnet:"):
            if self.aria2.is_available():
                return EngineType.ARIA2
            elif self.filecxx.is_available():
                return EngineType.FILECXX
        
        # HTTP/HTTPS → aria2
        if url_lower.startswith(("http://", "https://")):
            if self.aria2.is_available():
                return EngineType.ARIA2
            elif self.filecxx.is_available():
                return EngineType.FILECXX
        
        # 视频平台 → yt-dlp
        if any(p in url_lower for p in ["bilibili.com", "douyin.com", "youtube.com"]):
            return EngineType.YTDLP
        
        # 默认 aria2
        return EngineType.ARIA2
    
    def get_status(self) -> Dict:
        """获取所有任务状态"""
        return {
            "total": len(self.tasks),
            "completed": sum(1 for t in self.tasks if t.status == "completed"),
            "downloading": sum(1 for t in self.tasks if t.status == "downloading"),
            "failed": sum(1 for t in self.tasks if t.status == "failed"),
            "tasks": [t.to_dict() for t in self.tasks],
        }
    
    def cleanup(self):
        """清理资源"""
        self.aria2.stop_daemon()


# ================================================================
#  便捷函数
# ================================================================
def quick_download(url: str, output_dir: str = None) -> Dict:
    """快速下载 (同步)"""
    downloader = AutoDownloader()
    try:
        task = downloader.download(url, output_dir)
        if task.gid:
            result = downloader.aria2.wait_complete(task.gid)
            return result.to_dict()
        return task.to_dict()
    finally:
        downloader.cleanup()


if __name__ == "__main__":
    # 测试
    print("=== AutoDownloader 测试 ===\n")
    
    downloader = AutoDownloader()
    
    # 检查引擎可用性
    print(f"aria2 可用: {downloader.aria2.is_available()}")
    print(f"FileCxx 可用: {downloader.filecxx.is_available()}")
    
    # 测试 HTTP 下载
    test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    print(f"\n测试下载: {test_url}")
    task = downloader.download(test_url)
    
    if task.gid:
        result = downloader.aria2.wait_complete(task.gid, timeout=60)
        print(f"\n结果: {result.to_dict()}")
    
    downloader.cleanup()
