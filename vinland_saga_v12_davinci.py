#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vinland Saga V12 - DaVinci Resolve 二级调色脚本

工作流:
  V11 AE 合成输出 → DaVinci Resolve 节点二级调色 → V12 调色完成

调色策略:
  1. 一级调色: 基础校正 (Lift/Gamma/Gain + 对比度 + 饱和度)
  2. 二级调色: 选择性调色 (限定器选肤色/天空/暗部)
  3. 风格化: 电影颗粒 + 暗角 + 色调偏移
  4. 导出: ProRes 4444 XQ (保留质量) + H.264 (交付)
"""

import asyncio
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "puppet-automation" / "src"
sys.path.insert(0, str(SRC_DIR))

from engines.davinci.engine import DavinciEngine


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
    "ColorWheels": {
        "Offset": [0.02, 0.01, -0.02, 0.0],
        "ToneCurve": "LogC",
    },
    "MidtonesContrast": {
        "Strength": 0.2,
        "Frequency": 2.0,
    },
}


async def main():
    print("=" * 60)
    print("Vinland Saga V12 - DaVinci Resolve 二级调色")
    print("=" * 60)
    
    input_path = Path(V11_INPUT)
    if not input_path.exists():
        print(f"ERROR: V11 输入文件不存在: {input_path}")
        return
    
    print(f"输入文件: {input_path.name} ({input_path.stat().st_size / MB:.2f} MB)")
    print(f"输出目录: {V12_OUTPUT_DIR}")
    print(f"分辨率: {RESOLUTION[0]}x{RESOLUTION[1]}")
    print()
    
    print("[1/3] 初始化 DaVinci Engine...")
    engine = DavinciEngine()
    print(f"  Resolve路径: {engine.executable_path}")
    
    print("[2/3] 应用战斗电影风格调色...")
    print("  调色预设: Battle Cinematic")
    print("  - 一级调色: Lift/Gamma/Gain 冷色调")
    print("  - 风格化: 电影颗粒 + 暗角")
    print("  - 对比度: 提升中间调")
    
    result = await engine.apply_color_grade(
        input_path=input_path,
        output_dir=V12_OUTPUT_DIR,
        grade_preset=BATTLE_CINEMATIC_PRESET,
        style="cinematic",
        resolution=RESOLUTION,
    )
    
    print()
    print("[3/3] 验证结果...")
    if result.success:
        output_path = Path(V12_OUTPUT_DIR) / f"{V12_OUTPUT_NAME}_graded.mp4"
        if output_path.exists():
            print(f"✅ 调色成功!")
            print(f"   输出文件: {output_path.name}")
            print(f"   文件大小: {output_path.stat().st_size / MB:.2f} MB")
            print(f"   风格: {result.metadata.get('style', 'cinematic')}")
        else:
            print(f"⚠️  引擎返回成功，但输出文件未找到")
            print(f"   元数据: {result.metadata}")
    else:
        print(f"❌ 调色失败!")
        print(f"   错误: {result.error}")
    
    print()
    print("=" * 60)
    print("V12 调色完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
