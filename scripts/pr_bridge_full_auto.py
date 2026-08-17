"""
AE Knowledge Vault - Premiere Pro 全自动剪辑控制器
通过 Startup 桥接脚本与 PR 通信
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
import tempfile


class PRBridgeController:
    def __init__(self):
        self.bridge_dir = Path(tempfile.gettempdir()) / "ae_kv_pr_bridge"
        self.bridge_dir.mkdir(parents=True, exist_ok=True)

    def _wait_for_result(self, cmd_id: str, timeout: int = 60) -> dict:
        """等待命令执行结果"""
        result_file = self.bridge_dir / f"result_{cmd_id}.json"
        start = time.time()
        while time.time() - start < timeout:
            if result_file.exists():
                time.sleep(0.3)
                try:
                    return json.loads(result_file.read_text(encoding="utf-8"))
                except Exception:
                    time.sleep(0.5)
            time.sleep(0.5)
        raise TimeoutError(f"Command {cmd_id} timed out after {timeout}s")

    def send_command(self, action: str, **kwargs) -> dict:
        """发送命令到 PR 桥接"""
        cmd_id = f"{action}_{uuid.uuid4().hex[:8]}"
        cmd_file = self.bridge_dir / f"cmd_{cmd_id}.json"

        cmd = {"action": action, **kwargs}
        cmd_file.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
        print(f"  → 发送命令: {action} ({cmd_id})")

        result = self._wait_for_result(cmd_id)
        status = result.get("status", "unknown")
        print(f"  ← 结果: {status}")
        return result

    def wait_for_bridge(self, timeout: int = 120) -> bool:
        """等待桥接就绪"""
        ready_file = self.bridge_dir / "bridge_ready.txt"
        start = time.time()
        print("等待 PR 桥接就绪...", end="", flush=True)
        while time.time() - start < timeout:
            if ready_file.exists():
                print(" ✓")
                return True
            time.sleep(1)
            print(".", end="", flush=True)
        print(" ✗ 超时")
        return False

    def get_log(self) -> str:
        """获取桥接日志"""
        log_file = self.bridge_dir / "bridge_log.txt"
        if log_file.exists():
            return log_file.read_text(encoding="utf-8", errors="ignore")
        return ""


def run_full_auto_pipeline():
    """运行全自动剪辑流程"""
    print("=" * 60)
    print("AE Knowledge Vault - Premiere Pro 全自动剪辑")
    print("=" * 60)

    ctrl = PRBridgeController()

    # 0. 等待桥接
    if not ctrl.wait_for_bridge():
        print("✗ PR 桥接未就绪，请检查 PR 是否启动")
        return False

    # 1. Ping 测试
    print("\n[1/8] 连接测试...")
    result = ctrl.send_command("ping")
    if result.get("status") != "success":
        print("✗ 连接失败")
        return False
    print(f"  PR 版本: {result['result'].get('version', 'unknown')}")

    # 2. 获取项目信息
    print("\n[2/8] 获取项目信息...")
    result = ctrl.send_command("getProjectInfo")
    info = result.get("result", {})
    print(f"  序列数: {info.get('numSequences', 0)}")
    print(f"  素材数: {info.get('numItems', 0)}")

    # 3. 生成测试素材 (FFmpeg)
    print("\n[3/8] 生成测试素材...")
    test_clips = generate_test_clips()
    print(f"  生成 {len(test_clips)} 个测试片段")

    # 4. 导入素材
    print("\n[4/8] 导入素材到 PR...")
    clip_paths = [str(p) for p in test_clips]
    result = ctrl.send_command("importMedia", files=clip_paths)
    imported = result.get("result", {}).get("imported", 0)
    clip_names = result.get("result", {}).get("clipNames", [])
    print(f"  成功导入 {imported} 个素材")
    for name in clip_names:
        print(f"    - {name}")

    if imported == 0:
        print("✗ 素材导入失败")
        return False

    # 5. 创建序列
    print("\n[5/8] 创建序列...")
    result = ctrl.send_command("createSequence", name="Auto Edit Sequence")
    if result.get("status") != "success" or not result.get("result", {}).get("created"):
        print("✗ 序列创建失败，尝试用素材创建...")
        # 再试一次，可能需要素材先导入
        time.sleep(1)
        result = ctrl.send_command("createSequence", name="Auto Edit Sequence")

    seq_info = result.get("result", {})
    print(f"  序列名: {seq_info.get('sequenceName', 'unknown')}")
    print(f"  创建方式: {seq_info.get('method', 'direct')}")

    # 6. 添加素材到时间轴
    print("\n[6/8] 添加素材到时间轴...")
    for i, name in enumerate(clip_names):
        result = ctrl.send_command(
            "addClipToTrack",
            track=0,
            startTime=i * 3.0,
            clipName=name
        )
        added = result.get("result", {}).get("added", False)
        status = "✓" if added else "✗"
        print(f"  {status} 片段 {i+1}: {name}")
        if result.get("result", {}).get("error"):
            print(f"    错误: {result['result']['error']}")

    # 7. 应用转场
    print("\n[7/8] 应用转场效果...")
    result = ctrl.send_command("getProjectInfo")
    seqs = result.get("result", {}).get("sequences", [])
    if seqs and seqs[0].get("clipsOnV1", 0) > 1:
        num_clips = seqs[0]["clipsOnV1"]
        print(f"  V1 轨道有 {num_clips} 个片段")
        for i in range(num_clips - 1):
            result = ctrl.send_command(
                "applyTransition",
                track=0,
                clipIndex=i,
                transition="Cross Dissolve",
                duration=0.5
            )
            applied = result.get("result", {}).get("applied", False)
            status = "✓" if applied else "~"
            print(f"  {status} 转场 {i+1}: Cross Dissolve")
    else:
        print("  片段不足，跳过转场")

    # 8. 保存项目
    print("\n[8/8] 保存项目...")
    result = ctrl.send_command("saveProject")
    saved = result.get("result", {}).get("saved", False)
    print(f"  {'✓ 已保存' if saved else '✗ 保存失败'}")

    print("\n" + "=" * 60)
    print("✓ PR 全自动剪辑流程完成!")
    print(f"  桥接目录: {ctrl.bridge_dir}")
    print("=" * 60)
    return True


def generate_test_clips() -> list[Path]:
    """使用 FFmpeg 生成测试片段"""
    import subprocess

    output_dir = Path(tempfile.gettempdir()) / "ae_kv_pr_test_clips"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 查找 FFmpeg
    ffmpeg = "ffmpeg"
    project_root = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
    for p in [
        project_root / "puppet-automation" / "bin" / "ffmpeg" / "bin" / "ffmpeg.exe",
        project_root / "bin" / "ffmpeg.exe",
    ]:
        if p.exists():
            ffmpeg = str(p)
            break

    clips = []
    styles = [
        {"name": "clip1_sceneA", "color": "1a1a2e", "accent": "e94560", "duration": 4},
        {"name": "clip2_sceneB", "color": "16213e", "accent": "0f3460", "duration": 4},
        {"name": "clip3_sceneC", "color": "0f0f23", "accent": "00d9ff", "duration": 4},
        {"name": "clip4_sceneD", "color": "1a1a1a", "accent": "ff6b35", "duration": 4},
    ]

    for style in styles:
        out_path = output_dir / f"{style['name']}.mp4"
        if out_path.exists() and out_path.stat().st_size > 10000:
            clips.append(out_path)
            continue

        vf = (
            f"color=c=#{style['color']}:s=1920x1080:d={style['duration']},"
            f"drawbox=x=100:y=100:w=400:h=120:color=#{style['accent']}@0.7:t=fill,"
            f"drawbox=x=0:y=1040:w=1920:h=40:color=#{style['accent']}@0.3:t=fill"
        )

        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"color=c=#{style['color']}:s=1920x1080:d={style['duration']}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={style['duration']}",
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(out_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and out_path.exists():
                clips.append(out_path)
        except Exception as e:
            print(f"  生成 {style['name']} 失败: {e}")

    return clips


if __name__ == "__main__":
    run_full_auto_pipeline()
