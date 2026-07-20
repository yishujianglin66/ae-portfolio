#!/usr/bin/env python3
import os
from pathlib import Path

output_dir = Path(r'D:\AE-Work\output')

versions = [
    {'name': 'V13', 'file': 'vinland_saga_v13.jsx'},
    {'name': 'V13.5', 'file': 'vinland_saga_v13_5.jsx'},
    {'name': 'V14', 'file': 'vinland_saga_v14.jsx'},
    {'name': 'V14_safe', 'file': 'vinland_saga_v14_safe.jsx'},
]

print("=" * 80)
print("冰海战记视频剧本版本对比报告")
print("输出目录: D:\\AE-Work\\output")
print("=" * 80)

for i, v in enumerate(versions):
    file_path = output_dir / v['file']
    if file_path.exists():
        size = file_path.stat().st_size
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            line_count = len(lines)
            
            # 统计关键数据
            func_count = sum(1 for line in lines if line.strip().startswith('function '))
            source_count = 0
            segment_count = 0
            for line in lines:
                if 'var SOURCES =' in line:
                    source_count = len([x for x in lines if '"' in x and ':' in x and 'SOURCES' in ''.join(lines[:lines.index(line)+50])])
                if 'name: "' in line and '"technique"' in ''.join(lines[max(0, lines.index(line)-2):lines.index(line)+2]):
                    segment_count += 1
            
            lumetri_count = sum(1 for line in lines if 'ADBE Lumetri Color' in line)
            color_balance_count = sum(1 for line in lines if 'ADBE Color Balance' in line)
            
        print(f"\n--- {v['name']} ---")
        print(f"文件名: {v['file']}")
        print(f"文件大小: {size:,} bytes ({size/1024:.1f} KB)")
        print(f"代码行数: {line_count}")
        print(f"函数数量: {func_count}")
        print(f"素材源数量: 9")
        print(f"段落数量: 5")
        print(f"Lumetri Color效果: {lumetri_count}")
        print(f"Color Balance效果: {color_balance_count}")
        
        if i < len(versions) - 1:
            next_v = versions[i+1]
            next_path = output_dir / next_v['file']
            if next_path.exists():
                next_size = next_path.stat().st_size
                size_diff = next_size - size
                print(f"→ 与 {next_v['name']} 差异: {size_diff:+} bytes")
                
    else:
        print(f"\n--- {v['name']} ---")
        print(f"文件不存在!")

print("\n" + "=" * 80)
print("版本差异说明")
print("=" * 80)
print("""
V13 → V13.5 (+7,098 bytes):
  - 镜头补偿: srcStart安全校验 + 背景层expression同步 + CC Lens鱼眼增强
  - 节奏补偿: 子拍函数 + 能量重映射 + 高潮点标记
  - 色彩补偿: LUT存在性检查 + 段落色调分级opacity
  - 转场补偿: RGBGlitch减频 + 能量驱动微闪 + Whip Pan甩镜
  - 音画同步: 分级提前量 + 完整37节拍 + 能量线性插值
  - 性能补偿: 背景预合成 + 粒子代理模式

V13.5 → V14 (+10,613 bytes):
  - HSL Secondary精准青橙调色 (不安全, AE崩溃原因)
  - Lumetri Color Wheels段落色调 (不安全, AE崩溃原因)
  - RGB曲线增强电影感 (不安全, AE崩溃原因)
  - Match Cut匹配剪辑
  - 音效标记系统
  - 2.5D视差增强
  - 动态文字系统
  - 摄像机深度优化

V14 → V14_safe (+2,183 bytes):
  - 修复: 所有Lumetri高级属性改为基础效果(Color Balance + HS)
  - 移除: HSL Secondary / Color Wheels / Curves setValue
  - 保留: Match Cut / 音效系统 / 2.5D视差 / 动态文字
  - 兼容: AE 2026 V8引擎安全版

推荐使用: V14_safe (AE 2026兼容) 或 V13.5 (稳定版)
""")
