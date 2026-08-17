#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR 全自动控制器 - 通过 Startup 桥接脚本控制 Premiere Pro
使用方法:
  1. 将 pr_startup_bridge.jsx 复制到 PR 的 Scripts/Startup/ 目录
  2. 重启 Premiere Pro
  3. 运行本脚本
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import tempfile
import shutil

PR_INSTALL_DIR = Path(r"D:\Pr25\Adobe Premiere Pro 2025")
STARTUP_DIR = PR_INSTALL_DIR / "Scripts" / "Startup"
BRIDGE_SCRIPT_SRC = Path(__file__).parent / "pr_startup_bridge.jsx"
BRIDGE_DIR = Path(tempfile.gettempdir()) / "ae_kv_pr_bridge"


class PRController:
    """Premiere Pro 控制器。"""

    def __init__(self):
        self.bridge_dir = BRIDGE_DIR
        self.bridge_dir.mkdir(exist_ok=True)
        self.cmd_counter = 0

    def install_bridge(self) -> bool:
        """安装桥接脚本到 PR Startup 目录。"""
        if not BRIDGE_SCRIPT_SRC.exists():
            print(f"桥接脚本不存在: {BRIDGE_SCRIPT_SRC}")
            return False

        dest = STARTUP_DIR / "99_ae_kv_bridge.jsx"
        try:
            shutil.copy2(BRIDGE_SCRIPT_SRC, dest)
            print(f"✓ 桥接脚本已安装: {dest}")
            return True
        except Exception as e:
            print(f"安装桥接脚本失败: {e}")
            return False

    def is_bridge_ready(self) -> bool:
        """检查桥接是否就绪。"""
        ready_file = self.bridge_dir / "bridge_ready.txt"
        return ready_file.exists()

    def send_command(self, action: str, **params) -> dict:
        """发送命令并等待结果。"""
        self.cmd_counter += 1
        cmd_id = f"{self.cmd_counter:06d}_{int(time.time())}"
        cmd_file = self.bridge_dir / f"cmd_{cmd_id}.json"
        result_file = self.bridge_dir / f"result_{cmd_id}.json"

        # 删除旧结果
        if result_file.exists():
            result_file.unlink()

        # 写入命令
        cmd_data = {"action": action, **params}
        cmd_file.write_text(json.dumps(cmd_data, ensure_ascii=False), encoding="utf-8")
        print(f"  → 发送命令: {action}")

        # 等待结果（最多 30 秒）
        for _ in range(60):
            time.sleep(0.5)
            if result_file.exists():
                try:
                    result = json.loads(result_file.read_text(encoding="utf-8"))
                    return result
                except Exception:
                    pass
        return {"status": "timeout", "error": "命令执行超时"}

    # ====== 便捷方法 ======

    def ping(self) -> bool:
        """测试连接。"""
        result = self.send_command("ping")
        return result.get("status") == "success"

    def import_media(self, file_paths: list[str | Path]) -> int:
        """导入媒体文件。"""
        files = [str(p) for p in file_paths]
        result = self.send_command("importMedia", files=files)
        return result.get("result", {}).get("imported", 0)

    def create_sequence(self, name: str = "Auto Sequence",
                       preset: str = "DSLR 1080p30") -> bool:
        """创建序列。"""
        result = self.send_command("createSequence", name=name, preset=preset)
        return result.get("status") == "success"

    def add_clip_to_track(self, clip_path: str, track: int = 0,
                          start_time: float = 0) -> bool:
        """添加剪辑到轨道。"""
        result = self.send_command(
            "addClipToTrack", clipPath=clip_path,
            track=track, startTime=start_time
        )
        return result.get("result", {}).get("added", False)

    def apply_transition(self, clip_index: int, track: int = 0,
                        transition: str = "Cross Dissolve",
                        duration: float = 0.5) -> bool:
        """应用转场。"""
        result = self.send_command(
            "applyTransition", clipIndex=clip_index,
            track=track, transition=transition, duration=duration
        )
        return result.get("result", {}).get("applied", False)

    def add_effect(self, clip_index: int, effect: str = "Lumetri Color",
                   track: int = 0) -> bool:
        """添加效果。"""
        result = self.send_command(
            "addEffect", clipIndex=clip_index,
            effect=effect, track=track
        )
        return result.get("result", {}).get("applied", False)

    def get_info(self) -> dict:
        """获取项目信息。"""
        result = self.send_command("getProjectInfo")
        return result.get("result", {})

    def save_project(self) -> bool:
        """保存项目。"""
        result = self.send_command("saveProject")
        return result.get("result", {}).get("saved", False)


def run_full_auto_edit():
    """运行全自动剪辑流程。"""
    print("=" * 60)
    print("Premiere Pro 全自动剪辑")
    print("=" * 60)

    ctrl = PRController()

    # 步骤 0: 安装桥接
    print("\n【步骤 0】安装桥接脚本...")
    installed = ctrl.install_bridge()
    if not installed:
        print("  ⚠ 无法安装桥接脚本，可能需要管理员权限")
        print("  请手动复制:")
        print(f"    源: {BRIDGE_SCRIPT_SRC}")
        print(f"    目标: {STARTUP_DIR / '99_ae_kv_bridge.jsx'}")
        return False

    # 检查桥接是否就绪
    print("\n【步骤 0.1】等待桥接就绪...")
    if ctrl.is_bridge_ready():
        print("  ✓ 桥接已就绪")
    else:
        print("  ⚠ 桥接尚未就绪 (PR 需要重启以加载 Startup 脚本)")
        print("  请重启 Premiere Pro 后再次运行本脚本")
        print()
        print("  或者，你可以手动运行:")
        print(f"    文件 → 脚本 → 运行脚本文件 → {BRIDGE_SCRIPT_SRC}")
        print()
        print("  重启后再次运行: python pr_auto_controller.py")
        return False

    # 测试连接
    print("\n【步骤 1】测试连接...")
    if ctrl.ping():
        print("  ✓ 连接成功")
    else:
        print("  ✗ 连接失败")
        return False

    # 获取素材路径
    clips_dir = Path(__file__).parent.parent / "output" / "pr_final_output" / "clips"
    clip_files = sorted(clips_dir.glob("clip_*.mp4"))
    print(f"\n【步骤 2】导入素材 ({len(clip_files)} 个)...")

    imported = ctrl.import_media([str(p) for p in clip_files])
    print(f"  ✓ 导入 {imported} 个素材")

    # 创建序列
    print("\n【步骤 3】创建序列...")
    ctrl.create_sequence("Auto Edit Sequence", "DSLR 1080p30")
    print("  ✓ 序列已创建")

    # 添加剪辑到时间轴
    print(f"\n【步骤 4】添加剪辑到时间轴 ({len(clip_files)} 个)...")
    start_time = 0
    for i, clip in enumerate(clip_files):
        # 每段 3 秒
        ctrl.add_clip_to_track(str(clip), track=0, start_time=start_time)
        start_time += 3.0
        print(f"  ✓ 片段 {i+1}")

    # 应用转场
    print(f"\n【步骤 5】应用转场 ({len(clip_files)-1} 个)...")
    for i in range(len(clip_files) - 1):
        ctrl.apply_transition(i, track=0, transition="Cross Dissolve", duration=0.5)
        print(f"  ✓ 转场 {i+1}")

    # 应用调色
    print(f"\n【步骤 6】应用调色效果...")
    for i in range(len(clip_files)):
        ctrl.add_effect(i, effect="Lumetri Color", track=0)
    print(f"  ✓ 已添加 Lumetri Color 到 {len(clip_files)} 个剪辑")

    # 保存项目
    print("\n【步骤 7】保存项目...")
    ctrl.save_project()
    print("  ✓ 项目已保存")

    # 获取项目信息
    info = ctrl.get_info()
    print(f"\n  序列: {info.get('sequenceName', 'N/A')}")
    print(f"  视频轨道: {info.get('videoTracks', 0)}")
    print(f"  剪辑数量: {info.get('clipsOnTrack0', 0)}")

    print("\n" + "=" * 60)
    print("  ✓ 全自动剪辑完成!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    run_full_auto_edit()
