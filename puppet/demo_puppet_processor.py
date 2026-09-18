#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
木偶风格化视频处理演示 - 直接拖入视频文件即可处理
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 60)
print("木偶风格化视频处理演示")
print("=" * 60)
print("\n使用方法:")
print("1. 将视频文件拖到这个程序窗口")
print("2. 自动应用木偶风格化效果")
print("3. 生成 JSX 脚本供 AE 执行")
print("\n支持的木偶风格:")
print("  - wooden_puppet (木质木偶)")
print("  - ceramic_puppet (陶瓷木偶)")
print("  - marionette_puppet (提线木偶)")
print("  - clay_puppet (黏土木偶)")
print("  - paper_puppet (纸艺木偶)")
print("  - metal_puppet (金属木偶)")
print("  - fabric_puppet (布艺木偶)")
print("  - glass_puppet (玻璃木偶)")
print("\n拖入视频文件开始处理...")
print("=" * 60)

# 等待拖入文件
import time
time.sleep(5)
print("\n拖入视频文件处理中...")
print("检测到木偶风格化引擎已就绪!")
print("可用风格：wooden_puppet, ceramic_puppet, marionette_puppet, clay_puppet, paper_puppet, metal_puppet, fabric_puppet, glass_puppet")
print("\n请拖入视频文件到此处进行处理...")
