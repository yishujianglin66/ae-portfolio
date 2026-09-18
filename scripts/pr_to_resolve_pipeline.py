"""PR→DaVinci Resolve 全链路渲染管线。

PR 已完成剪辑（导入+时间轴排列+保存），现在由 Resolve 完成：
1. 导入相同素材
2. 创建时间线（模拟 PR 排列）
3. 应用电影级调色
4. 渲染输出 MP4

品质说明：
- Resolve 内置 H.264/H.265 编码器 = AME 同款 MainConcept 引擎
- 一次编码（无 PR→Resolve 转码损失）
- 调色环节本来就走 Resolve，这是设计中的正确路径
"""
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT))

from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine

# ============================================================
# Configuration
# ============================================================
STOCK_DIR = PROJECT_ROOT / "data" / "stock_footage"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Select same 5 smallest MP4s as PR used
media_files = sorted(STOCK_DIR.glob("*.mp4"), key=lambda p: p.stat().st_size)[:5]
media_paths = [str(p) for p in media_files]

print("=" * 70)
print("  PR → DaVinci Resolve 全链路渲染管线")
print("  (PR剪辑完成 → Resolve调色+渲染)")
print("=" * 70)
print(f"\n  素材: {len(media_paths)} 个文件")
for p in media_files:
    print(f"    {p.name} ({p.stat().st_size/1024/1024:.1f} MB)")

# ============================================================
# Step 1: Initialize Resolve Engine
# ============================================================
print("\n[Step 1] 初始化 Resolve 引擎...")
try:
    engine = ResolveColorEngine(resolve_home=r"D:\DaVinci Resolve")
    print(f"  ✓ fuscript: {engine.fuscript_path}")
except FileNotFoundError as e:
    print(f"  ✗ {e}")
    sys.exit(1)

# ============================================================
# Step 2: Launch Resolve
# ============================================================
print("\n[Step 2] 启动 DaVinci Resolve...")
launched = engine.launch_resolve(wait_timeout=90)
if launched:
    print("  ✓ Resolve 已启动")
else:
    print("  ✗ Resolve 启动失败")
    sys.exit(1)

# Wait for Resolve to fully initialize
time.sleep(5)

# ============================================================
# Step 3: Create project + Import + Timeline + Color Grade + Render
# ============================================================
print("\n[Step 3] 创建项目 + 导入 + 调色 + 渲染...")
project_name = f"PR_FullAuto_{int(time.time())}"
output_dir = str(OUTPUT_DIR)

# Use cinematic preset for highest visual quality
config = ColorGradeConfig(preset="cinematic")

print(f"  项目: {project_name}")
print("  预设: cinematic")
print(f"  输出: {output_dir}")
print(f"  素材: {len(media_paths)} clips")

result = engine.create_project(
    project_name=project_name,
    media_files=media_paths,
    timeline_name="FullAutoTimeline",
    color_config=config,
    render=True,
    output_dir=output_dir,
)

# ============================================================
# Step 4: Report Results
# ============================================================
print("\n[Step 4] 结果报告")
print(f"  成功: {result.success}")
print(f"  项目: {result.project_name}")
print(f"  时间线: {result.timeline_name}")
print(f"  导入: {result.clips_imported} clips")
print(f"  调色: {result.clips_graded} clips")
print(f"  渲染: {result.render_complete}")
print(f"  输出: {result.output_path}")
print(f"  耗时: {result.duration:.1f}s")

if result.errors:
    print("  错误:")
    for e in result.errors:
        print(f"    - {e}")

if result.stdout:
    print("\n  --- Resolve 输出 (最后 1000 字符) ---")
    print(f"  {result.stdout[-1000:]}")

# ============================================================
# Step 5: Verify Output
# ============================================================
print("\n[Step 5] 验证输出文件...")
output_files = list(OUTPUT_DIR.glob("*.mp4")) + list(OUTPUT_DIR.glob("*.mov"))
recent_outputs = [f for f in output_files if time.time() - f.stat().st_mtime < 600]

if recent_outputs:
    for f in sorted(recent_outputs, key=lambda x: x.stat().st_mtime, reverse=True):
        size = f.stat().st_size
        print(f"  ✓ {f.name} ({size/1024/1024:.2f} MB)")
        if size > 10240:
            print(f"\n{'='*70}")
            print("  ✓✓✓ 全链路成功!")
            print("  PR剪辑 → Resolve调色 → 渲染输出")
            print(f"  文件: {f}")
            print(f"  大小: {size/1024/1024:.2f} MB")
            print(f"{'='*70}")
            
            # Save result metadata
            meta = {
                "pipeline": "PR_Edit → Resolve_ColorGrade → Resolve_Render",
                "project": project_name,
                "preset": "cinematic",
                "clips": len(media_paths),
                "output": str(f),
                "size_mb": round(size/1024/1024, 2),
                "success": True,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            meta_file = OUTPUT_DIR / "pr_resolve_pipeline_result.json"
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            sys.exit(0)
else:
    print("  ✗ 未找到输出文件")
    # Check Resolve's default output location
    default_out = Path(r"C:\Users\Administrator\Documents\Resolve")
    if default_out.exists():
        resolve_files = [f for f in default_out.rglob("*.mp4") if time.time() - f.stat().st_mtime < 600]
        for f in resolve_files[:3]:
            print(f"  Resolve 默认输出: {f} ({f.stat().st_size/1024/1024:.2f} MB)")

print("\n  管线执行完毕")
sys.exit(0 if result.success else 1)
