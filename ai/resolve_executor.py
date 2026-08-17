# -*- coding: utf-8 -*-
"""T16: ResolveExecutor — ShotScript→Resolve自动化执行器。

将ShotScript镜头脚本转化为Resolve实际时间线操作:
1. 自动启动Resolve(无则拉起)
2. create_project(项目名=ShotScript.title)
3. import_media(只导入脚本引用的素材)
4. create_timeline_with_media(按镜头顺序排列)
5. set_speed/apply_speed_curve(变速)
6. apply_cdl/apply_lut(调色)
7. 添加转场

验收: 给定ShotScript自动产出带变速时间线; Resolve未启动时自动拉起。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai.shot_script import ShotScript, ShotUnit


class ResolveExecutor:
    """ShotScript→Resolve执行器"""

    def __init__(self, fuscript_path: Optional[str] = None):
        self.fuscript_path = fuscript_path or self._find_fuscript()
        self.engine = None
        self._log("ResolveExecutor初始化")

    def _find_fuscript(self) -> str:
        """查找fuscript.exe路径"""
        # 常见安装路径
        candidates = [
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fuscript.exe",
            r"C:\Program Files (x86)\Blackmagic Design\DaVinci Resolve\fuscript.exe",
            r"D:\Blackmagic Design\DaVinci Resolve\fuscript.exe",
        ]
        for p in candidates:
            if Path(p).exists():
                return p
        return ""

    def _log(self, msg: str):
        print(f"[ResolveExecutor] {msg}", flush=True)

    def check_resolve_running(self) -> bool:
        """检查Resolve是否运行"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
                capture_output=True, text=True, timeout=5
            )
            return "Resolve.exe" in result.stdout
        except Exception:
            return False

    def launch_resolve(self) -> bool:
        """启动Resolve"""
        candidates = [
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
            r"C:\Program Files (x86)\Blackmagic Design\DaVinci Resolve\Resolve.exe",
            r"D:\Blackmagic Design\DaVinci Resolve\Resolve.exe",
        ]
        for p in candidates:
            if Path(p).exists():
                self._log(f"启动Resolve: {p}")
                subprocess.Popen([p], shell=True)
                time.sleep(5)  # 等待启动
                return True
        self._log("❌ 未找到Resolve安装")
        return False

    def execute(self, script: ShotScript, dry_run: bool = False) -> Dict:
        """执行ShotScript→Resolve时间线

        Args:
            script: ShotScript对象
            dry_run: 仅模拟不实际执行

        Returns:
            执行报告
        """
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "title": script.metadata.title,
            "shot_count": len(script.shots),
            "dry_run": dry_run,
            "steps": [],
            "success": False,
        }

        # 1. 检查/启动Resolve
        if not dry_run:
            if not self.check_resolve_running():
                self._log("Resolve未运行，尝试启动...")
                if not self.launch_resolve():
                    report["error"] = "Resolve启动失败"
                    return report
                time.sleep(10)  # 等待完全启动
            report["steps"].append({"step": "resolve_ready", "ok": True})

        # 2. 收集需要导入的素材
        media_files = set()
        for shot in script.shots:
            if shot.source_video:
                # 构建完整路径(假设素材在data/real_amv_test)
                media_path = _PROJECT_ROOT / "data" / "real_amv_test" / shot.source_video
                if media_path.exists():
                    media_files.add(str(media_path))
                else:
                    self._log(f"⚠️ 素材不存在: {media_path}")

        report["media_count"] = len(media_files)
        self._log(f"需要导入 {len(media_files)} 个素材文件")

        if dry_run:
            report["steps"].append({
                "step": "import_media",
                "ok": True,
                "files": list(media_files),
                "dry_run": True,
            })
            report["success"] = True
            return report

        # 3. 初始化引擎
        try:
            from integrations.resolve_engine import ResolveAutomationEngine
            self.engine = ResolveAutomationEngine()
            report["steps"].append({"step": "engine_init", "ok": True})
        except Exception as e:
            report["error"] = f"引擎初始化失败: {e}"
            return report

        # 4. 创建项目
        project_name = script.metadata.title or "ShotScript_Project"
        try:
            result = self.engine.create_project(project_name)
            report["steps"].append({
                "step": "create_project",
                "ok": True,
                "project_name": project_name,
            })
            self._log(f"✅ 创建项目: {project_name}")
        except Exception as e:
            report["error"] = f"创建项目失败: {e}"
            return report

        # 5. 导入素材
        try:
            imported = self.engine.import_media(project_name, list(media_files))
            report["steps"].append({
                "step": "import_media",
                "ok": True,
                "imported_count": len(imported),
            })
            self._log(f"✅ 导入素材: {len(imported)}个")
        except Exception as e:
            report["error"] = f"导入素材失败: {e}"
            return report

        # 6. 创建时间线
        timeline_name = f"{project_name}_Timeline"
        try:
            # 构建镜头列表(源文件+入出点)
            shot_list = []
            for shot in script.shots:
                media_path = _PROJECT_ROOT / "data" / "real_amv_test" / shot.source_video
                if media_path.exists():
                    shot_list.append({
                        "media_path": str(media_path),
                        "start_frame": int(shot.in_tc * script.global_settings.fps),
                        "end_frame": int(shot.out_tc * script.global_settings.fps),
                    })

            result = self.engine.create_timeline_with_media(
                project_name, timeline_name, shot_list
            )
            report["steps"].append({
                "step": "create_timeline",
                "ok": True,
                "timeline_name": timeline_name,
                "shot_count": len(shot_list),
            })
            self._log(f"✅ 创建时间线: {timeline_name} ({len(shot_list)}个镜头)")
        except Exception as e:
            report["error"] = f"创建时间线失败: {e}"
            return report

        # 7. 应用变速(如果有)
        speed_applied = 0
        for i, shot in enumerate(script.shots):
            if shot.speed_curve and len(shot.speed_curve) > 0:
                # 使用第一段速度(简化处理)
                speed = shot.speed_curve[0].speed
                if speed != 1.0:
                    try:
                        self.engine.set_speed(project_name, i + 1, speed)
                        speed_applied += 1
                    except Exception as e:
                        self._log(f"⚠️ 设置变速失败 shot[{i}]: {e}")

        report["speed_applied"] = speed_applied
        if speed_applied > 0:
            report["steps"].append({
                "step": "apply_speed",
                "ok": True,
                "count": speed_applied,
            })
            self._log(f"✅ 应用变速: {speed_applied}个镜头")

        # 8. 应用CDL(如果有)
        cdl_applied = 0
        for i, shot in enumerate(script.shots):
            if shot.cdl:
                try:
                    self.engine.apply_cdl(
                        project_name, timeline_name,
                        slope=shot.cdl.slope,
                        offset=shot.cdl.offset,
                        power=shot.cdl.power,
                        clip_index=i + 1,
                    )
                    cdl_applied += 1
                except Exception as e:
                    self._log(f"⚠️ 应用CDL失败 shot[{i}]: {e}")

        report["cdl_applied"] = cdl_applied
        if cdl_applied > 0:
            report["steps"].append({
                "step": "apply_cdl",
                "ok": True,
                "count": cdl_applied,
            })
            self._log(f"✅ 应用CDL: {cdl_applied}个镜头")

        report["success"] = True
        self._log(f"🎬 执行完成: {project_name}")
        return report


def execute_shot_script(script_path: Path, dry_run: bool = False) -> Dict:
    """便捷函数: 加载ShotScript并执行"""
    script = ShotScript.load(script_path)
    executor = ResolveExecutor()
    return executor.execute(script, dry_run=dry_run)


if __name__ == "__main__":
    # 自检: dry_run模式测试
    print("=" * 60)
    print("T16 ResolveExecutor自检")
    print("=" * 60)

    # 加载演示ShotScript
    demo_path = _PROJECT_ROOT / "output" / "shot_script_demo.json"
    if not demo_path.exists():
        print(f"❌ 演示ShotScript不存在: {demo_path}")
        print("   请先运行: python tmp/t15_shot_script_demo.py")
        sys.exit(1)

    script = ShotScript.load(demo_path)
    print(f"\n加载ShotScript: {demo_path}")
    print(f"  标题: {script.metadata.title}")
    print(f"  镜头数: {len(script.shots)}")
    print(f"  目标时长: {script.metadata.duration_target}s")

    # dry_run执行
    executor = ResolveExecutor()
    print(f"\n[dry_run模式]")
    report = executor.execute(script, dry_run=True)

    print(f"\n执行报告:")
    print(f"  成功: {report['success']}")
    print(f"  素材数: {report.get('media_count', 0)}")
    print(f"  步骤:")
    for step in report["steps"]:
        status = "✅" if step.get("ok") else "❌"
        print(f"    {status} {step['step']}")

    print("\n" + "=" * 60)
    print("T16 ResolveExecutor自检完成")
    print("=" * 60)
