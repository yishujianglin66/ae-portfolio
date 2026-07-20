#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vinland Saga V12 - DaVinci Resolve 二级调色脚本 (独立版)

直接使用 DaVinci Resolve Python API，不依赖 puppet-automation 框架

工作流:
  V11 AE 合成输出 → DaVinci Resolve 节点二级调色 → V12 调色完成

调色策略:
  1. 一级调色: 基础校正 (Lift/Gamma/Gain + 对比度 + 饱和度)
  2. 风格化: 电影颗粒 + 暗角
  3. 导出: H.264 交付格式
"""

import sys
import os
import json
import tempfile
from pathlib import Path

V11_INPUT = "D:/AE-Work/output/VinlandSaga_Battle_V11.mp4"
V12_OUTPUT_DIR = "D:/AE-Work/output"
V12_OUTPUT_NAME = "VinlandSaga_Battle_V12"
RESOLUTION = (1080, 1920)
MB = 1024 * 1024


BATTLE_CINEMATIC_PRESET = {
    "Primary": {
        "Lift": [0.92, 0.94, 0.97, 1.0],
        "Gamma": [1.08, 1.03, 0.95, 1.0],
        "Gain": [1.05, 1.0, 0.92, 1.0],
        "Contrast": 1.15,
        "Saturation": 0.85,
        "Exposure": 0.05,
    },
    "FilmGrain": {
        "Amount": 0.18,
        "Size": 0.6,
        "Softness": 0.3,
    },
    "Vignette": {
        "Amount": 0.25,
        "Size": 0.75,
        "Feather": 0.8,
        "Roundness": 1.0,
    },
}


GRADE_SCRIPT_TEMPLATE = '''
"""Auto-generated Resolve grading script."""
import sys
import os
import json
import time

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

try:
    import DaVinciResolveScript as bmd
except ImportError:
    print("ERROR: DaVinciResolveScript not found", file=sys.stderr)
    sys.exit(1)

resolve = bmd.scriptapp("Resolve")
if not resolve:
    print("ERROR: Cannot connect to Resolve - is it running?", file=sys.stderr)
    sys.exit(1)

project_manager = resolve.GetProjectManager()
project = project_manager.GetCurrentProject()
if not project:
    project = project_manager.CreateProject("AutoGrade_VinlandSaga_V12")

media_pool = project.GetMediaPool()
folder = media_pool.GetRootFolder()
media_item = media_pool.ImportMedia([_PARAMS["input_path"]])
if not media_item:
    print("ERROR: Failed to import media", file=sys.stderr)
    sys.exit(1)

timeline = media_pool.CreateEmptyTimeline("V12_Grade_Timeline")
media_pool.AppendToTimeline(media_item)

timeline = project.GetCurrentTimeline()
clip = timeline.GetItemListInTrack("video", 1)[0]
node_graph = clip.GetNodeGraph()

grade_preset = _PARAMS["grade_preset"]
for node_name, params in grade_preset.items():
    node = node_graph.AddNode()
    node.SetName(node_name)
    for param_name, value in params.items():
        node.SetParameterValue(param_name, value)

project.SetRenderSettings({
    "TargetDir": _PARAMS["output_dir"],
    "CustomName": _PARAMS["output_name"],
    "FormatWidth": _PARAMS["width"],
    "FormatHeight": _PARAMS["height"],
    "Format": "mp4",
    "Codec": "H.264",
})

job_id = project.AddRenderJob()
if job_id:
    project.StartRendering(job_id)
    while project.IsRenderingInProgress():
        time.sleep(1)
    status = project.GetRenderJobStatus(job_id)
    if status.get("JobStatus") == "Complete":
        print("RENDER_SUCCESS")
    else:
        print("RENDER_FAILED: " + str(status), file=sys.stderr)
        sys.exit(1)
else:
    print("ERROR: Failed to add render job", file=sys.stderr)
    sys.exit(1)
'''


def main():
    print("=" * 60)
    print("Vinland Saga V12 - DaVinci Resolve 二级调色")
    print("=" * 60)
    
    input_path = Path(V11_INPUT)
    if not input_path.exists():
        print(f"ERROR: V11 输入文件不存在: {input_path}")
        return 1
    
    print(f"输入文件: {input_path.name} ({input_path.stat().st_size / MB:.2f} MB)")
    print(f"输出目录: {V12_OUTPUT_DIR}")
    print(f"分辨率: {RESOLUTION[0]}x{RESOLUTION[1]}")
    print()
    
    print("[1/3] 创建 Resolve 调色脚本...")
    params = {
        "input_path": str(input_path),
        "output_dir": V12_OUTPUT_DIR,
        "output_name": V12_OUTPUT_NAME,
        "width": RESOLUTION[0],
        "height": RESOLUTION[1],
        "grade_preset": BATTLE_CINEMATIC_PRESET,
    }
    params_json = json.dumps(params, ensure_ascii=False, indent=2)
    
    script_file = Path(tempfile.gettempdir()) / f"dr_grade_v12.py"
    script_content = GRADE_SCRIPT_TEMPLATE.replace("%PARAMS_JSON%", params_json)
    script_file.write_text(script_content, encoding="utf-8")
    print(f"  脚本已生成: {script_file.name}")
    
    print("[2/3] 检查 DaVinci Resolve 状态...")
    resolve_exe = Path("D:/DaVinci Resolve/Resolve.exe")
    if not resolve_exe.exists():
        print(f"ERROR: DaVinci Resolve 未找到: {resolve_exe}")
        return 1
    print(f"  Resolve路径: {resolve_exe}")
    
    import subprocess
    print("[3/3] 启动 DaVinci Resolve 执行调色...")
    print("  注意: DaVinci Resolve 需要先运行才能执行脚本")
    print("  调色预设: Battle Cinematic")
    print("  - 一级调色: Lift/Gamma/Gain 冷色调")
    print("  - 风格化: 电影颗粒 + 暗角")
    print()
    
    fuscript_exe = Path("D:/DaVinci Resolve/fuscript.exe")
    cmd = [str(fuscript_exe), "-py3", str(script_file)]
    print(f"  命令: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
        )
        print(f"  退出码: {result.returncode}")
        if result.stdout:
            print(f"  标准输出:\n{result.stdout}")
        if result.stderr:
            print(f"  错误输出:\n{result.stderr}")
        
        if result.returncode == 0 and "RENDER_SUCCESS" in result.stdout:
            print()
            print("✅ 调色成功!")
            output_path = Path(V12_OUTPUT_DIR) / f"{V12_OUTPUT_NAME}.mp4"
            if output_path.exists():
                print(f"   输出文件: {output_path.name}")
                print(f"   文件大小: {output_path.stat().st_size / MB:.2f} MB")
            return 0
        else:
            print()
            print("❌ 调色失败!")
            return 1
    except subprocess.TimeoutExpired:
        print("❌ 调色超时!")
        return 1
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
