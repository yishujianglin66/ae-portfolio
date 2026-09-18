#!/usr/bin/env python3
"""
冰海战记 V15 - 完整构建与渲染脚本
- 修复 V14_safe 的兼容性问题
- 分两步：创建工程 → 渲染输出
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from pathlib import Path

# ============ 路径配置 ============
V14_SAFE = Path(r"D:\AE-Work\output\vinland_saga_v14_safe.jsx")
V15_BUILD = Path(r"D:\AE-Work\output\vinland_saga_v15_build.jsx")
V15_OUTPUT = Path(r"D:\AE-Work\output\VinlandSaga_Battle_V15.mp4")
AEP_PATH = Path(r"D:\AE-Work\VinlandSaga_V15.aep")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")
AFTERFX = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe")


def patch_v14_to_v15():
    """从 V14_safe 生成 V15 构建脚本。"""
    print("=" * 60)
    print("生成 V15 构建脚本")
    print("=" * 60)

    content = V14_SAFE.read_text(encoding="utf-8")

    # 1. 改版本号和合成名
    content = content.replace("VinlandSaga_Cinematic_V14", "VinlandSaga_Cinematic_V15")
    content = content.replace("V14_safe", "V15")
    content = content.replace("VinlandSaga_Battle_V14_safe.mp4", "VinlandSaga_Battle_V15.mp4")

    # 2. 修复 AE 2026 路径 → 2025
    content = content.replace(
        '"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Lumetri/LUTs/Creative/"',
        '"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Lumetri/LUTs/Creative/"'
    )
    content = content.replace(
        '"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Lumetri/LUTs/Technical/"',
        '"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Lumetri/LUTs/Technical/"'
    )

    # 3. 修复 Kodak LUT 文件名（AE 2025 里的名字不一样）
    content = content.replace(
        '"Kodak_2383_D55.cube"',
        '"Kodak 5218 Kodak 2383 (by Adobe).cube"'
    )

    # 4. 关闭自动渲染，改为保存工程文件
    content = content.replace("var AUTO_RENDER = true;", "var AUTO_RENDER = false;")

    # 5. 在 main 函数末尾添加保存工程的代码（在 return 之前）
    save_code = '''
        // V15: 保存工程文件
        try {
            var projPath = "D:/AE-Work/VinlandSaga_V15.aep";
            var projFile = new File(projPath);
            app.project.save(projFile);
        } catch(e) {}
'''
    
    # 找到 main 函数里的 return JSON.stringify({status: "success" 那一行
    # 在它之前插入保存代码
    success_return = 'return JSON.stringify({\n            status: "success",'
    if success_return in content:
        content = content.replace(success_return, save_code + "\n" + success_return)

    V15_BUILD.write_text(content, encoding="utf-8")
    print(f"✅ V15 构建脚本已生成: {V15_BUILD}")
    print(f"   大小: {V15_BUILD.stat().st_size} 字节")
    return True


async def run_build_script():
    """用 aerender 执行构建脚本，创建合成并保存工程。"""
    print()
    print("=" * 60)
    print("执行 V15 构建脚本（创建合成 + 保存工程）")
    print("=" * 60)

    # 方法：用 aerender -s 执行脚本
    # 但脚本太长，用 -rjsx 从文件执行
    cmd = [
        str(AERENDER),
        "-rjsx", str(V15_BUILD),
    ]

    print(f"命令: {' '.join(cmd)[:200]}...")
    print()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        stdout_text = stdout.decode("utf-8", errors="ignore")
        stderr_text = stderr.decode("utf-8", errors="ignore")

        print("--- STDOUT ---")
        print(stdout_text[-3000:] if len(stdout_text) > 3000 else stdout_text)
        print()
        print("--- STDERR ---")
        print(stderr_text[-2000:] if len(stderr_text) > 2000 else stderr_text)
        print()

        if proc.returncode == 0:
            print("✅ 构建脚本执行成功")
            if AEP_PATH.exists():
                print(f"✅ 工程文件已保存: {AEP_PATH}")
                print(f"   大小: {AEP_PATH.stat().st_size / 1024:.1f} KB")
                return True
            else:
                print(f"⚠️  执行成功但没找到工程文件: {AEP_PATH}")
                return False
        else:
            print(f"❌ 构建脚本执行失败 (exit code: {proc.returncode})")
            return False

    except asyncio.TimeoutError:
        print("❌ 执行超时 (10 分钟)")
        return False
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        return False


async def render_aep():
    """用 aerender 渲染 aep 工程。"""
    print()
    print("=" * 60)
    print("渲染 V15 工程")
    print("=" * 60)

    if not AEP_PATH.exists():
        print(f"❌ 工程文件不存在: {AEP_PATH}")
        return False

    comp_name = "VinlandSaga_Cinematic_V15"
    cmd = [
        str(AERENDER),
        "-project", str(AEP_PATH),
        "-comp", comp_name,
        "-output", str(V15_OUTPUT),
        "-OMtemplate", "H.264",
        "-RStemplate", "Best Settings",
        "-mp", "2",
    ]

    print(f"工程: {AEP_PATH.name}")
    print(f"合成: {comp_name}")
    print(f"输出: {V15_OUTPUT.name}")
    print()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # 实时输出进度
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=30)
                if not line:
                    break
                line_text = line.decode("utf-8", errors="ignore").strip()
                if "PROGRESS" in line_text or "ERROR" in line_text or "Rendering" in line_text:
                    print(f"  {line_text[:120]}")
            except asyncio.TimeoutError:
                if proc.returncode is not None:
                    break
        
        await proc.wait()
        print()

        if proc.returncode == 0 and V15_OUTPUT.exists():
            size_mb = V15_OUTPUT.stat().st_size / (1024 * 1024)
            print("✅ 渲染成功!")
            print(f"   文件: {V15_OUTPUT}")
            print(f"   大小: {size_mb:.2f} MB")
            return True
        else:
            print(f"❌ 渲染失败 (exit code: {proc.returncode})")
            # 打印 stderr
            stderr = await proc.stderr.read()
            stderr_text = stderr.decode("utf-8", errors="ignore")
            if stderr_text.strip():
                print("错误信息:")
                print(stderr_text[-1000:])
            return False

    except Exception as e:
        print(f"❌ 渲染出错: {e}")
        return False


async def main():
    print()
    print("🎬 冰海战记 V15 - 完整构建与渲染")
    print()

    # 第一步：生成 V15 构建脚本
    if not patch_v14_to_v15():
        print("❌ 生成 V15 脚本失败")
        return 1

    # 第二步：执行构建脚本
    build_ok = await run_build_script()
    if not build_ok:
        print()
        print("⚠️  构建失败，尝试其他方法...")
        # 可以在这里加回退方案
        return 1

    # 第三步：渲染
    render_ok = await render_aep()
    if not render_ok:
        print()
        print("❌ 渲染失败")
        return 1

    print()
    print("=" * 60)
    print("🎉 V15 完成！")
    print("=" * 60)
    print(f"输出: {V15_OUTPUT}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
