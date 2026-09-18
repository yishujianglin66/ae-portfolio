r"""P3P4 风格迁移 - 保存工程并渲染最终产物
1. 通过 Bridge 保存当前 AE 工程到 D:\AE-Work\StyleMigration_Neon_v2.aep
2. 获取合成名称
3. 用 aerender 渲染前 60 帧（避免内存不足）
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "video"))

from style_migration_executor import AELauncher, MCPBridgeClient

AERENDER = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"
OUTPUT_AEP = r"D:\AE-Work\StyleMigration_Neon_v2.aep"
OUTPUT_MP4 = r"D:\AE-Work\StyleMigration_Neon_v2.mp4"


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


def main():
    print("=" * 70)
    print("  P3P4 风格迁移 - 保存工程并渲染")
    print("=" * 70)

    # Step 1: 检查 AE 和 Bridge
    print("\n--- Step 1: 检查 AE 和 Bridge ---")
    if not AELauncher.is_ae_running():
        print("[FAIL] AE 未运行")
        return
    log("AE 已在运行")

    client = MCPBridgeClient(timeout=60.0)
    if not client.ping():
        print("[FAIL] Bridge ping 失败")
        return
    log("Bridge 连接正常")

    # Step 2: 查询当前工程信息
    print("\n--- Step 2: 查询当前工程信息 ---")
    info_jsx = r"""
(function() {
    var result = {};
    try {
        result.projectName = app.project.name;
        result.comps = [];
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem) {
                result.comps.push({
                    name: item.name,
                    width: item.width,
                    height: item.height,
                    duration: item.duration,
                    frameRate: item.frameRate,
                    numLayers: item.numLayers
                });
            }
        }
        result.numItems = app.project.numItems;
    } catch(e) {
        result.error = e.toString();
    }
    return JSON.stringify(result, null, 2);
})();
"""
    r = client.send_command("runScript", {"code": info_jsx})
    inner = r.get("result", {}).get("result", "")
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except Exception:
            pass

    if not isinstance(inner, dict):
        print(f"[FAIL] 无法获取工程信息: {inner}")
        return

    if inner.get("error"):
        print(f"[FAIL] 查询出错: {inner['error']}")
        return

    log(f"工程名: {inner.get('projectName')}")
    log(f"项目数: {inner.get('numItems')}")
    comps = inner.get("comps", [])
    log(f"合成数量: {len(comps)}")
    for c in comps:
        log(f"  合成: {c['name']} ({c['width']}x{c['height']}, {c['duration']:.1f}s, {c['frameRate']:.0f}fps, {c['numLayers']} layers)")

    if not comps:
        print("[FAIL] 没有合成可渲染")
        return

    # 选择第一个合成（或名为 StyleMigration 的合成）
    target_comp = None
    for c in comps:
        if "StyleMigration" in c["name"] or "Neon" in c["name"]:
            target_comp = c
            break
    if not target_comp:
        target_comp = comps[0]

    comp_name = target_comp["name"]
    log(f"目标合成: {comp_name}")

    # Step 3: 保存工程
    print("\n--- Step 3: 保存工程 ---")
    save_path_js = OUTPUT_AEP.replace("\\", "/")
    save_jsx = (
        "(function() {\n"
        "    try {\n"
        f"        var saveFile = new File('{save_path_js}');\n"
        "        var parent = saveFile.parent;\n"
        "        if (!parent.exists) {\n"
        "            parent.create();\n"
        "        }\n"
        "        app.project.save(saveFile);\n"
        "        return JSON.stringify({status: 'success', path: saveFile.fsName});\n"
        "    } catch(e) {\n"
        "        return JSON.stringify({status: 'error', message: e.toString()});\n"
        "    }\n"
        "})();\n"
    )
    r = client.send_command("runScript", {"code": save_jsx})
    inner = r.get("result", {}).get("result", "")
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except Exception:
            pass

    if isinstance(inner, dict) and inner.get("status") == "success":
        log(f"工程已保存: {inner.get('path')}")
    else:
        print(f"[FAIL] 保存失败: {inner}")
        return

    # Step 4: 关闭 AE（aerender 需要独占工程文件）
    print("\n--- Step 4: 关闭 AE（aerender 需要独占工程文件）---")
    log("正在关闭 AE...")
    AELauncher.close_ae_graceful()
    time.sleep(3)
    if AELauncher.is_ae_running():
        log("WM_CLOSE 未生效，使用 taskkill /F /T", "WARN")
        subprocess.run(["taskkill", "/F", "/T", "/IM", "AfterFX.exe"],
                       capture_output=True, timeout=30)
        time.sleep(5)
    if AELauncher.is_ae_running():
        print("[FAIL] 无法关闭 AE")
        return
    log("AE 已关闭")

    # Step 5: aerender 渲染（前 60 帧避免内存不足）
    print("\n--- Step 5: aerender 渲染 ---")
    if not Path(AERENDER).exists():
        print(f"[FAIL] aerender 不存在: {AERENDER}")
        return

    cmd = [
        AERENDER,
        "-project", OUTPUT_AEP,
        "-comp", comp_name,
        "-s", "1",
        "-e", "60",
        "-output", OUTPUT_MP4,
    ]
    log(f"渲染命令: {' '.join(cmd)}")
    log("渲染中（可能需要 1-3 分钟）...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            encoding="gbk",
            errors="replace",
        )
        log(f"aerender 退出码: {result.returncode}")

        # 打印部分输出
        stdout_lines = result.stdout.splitlines() if result.stdout else []
        if stdout_lines:
            log("输出（最后 20 行）:")
            for line in stdout_lines[-20:]:
                print(f"    {line}")

        if result.returncode == 0:
            # 检查输出文件
            if Path(OUTPUT_MP4).exists():
                size_mb = Path(OUTPUT_MP4).stat().st_size / (1024 * 1024)
                log(f"渲染成功! 输出: {OUTPUT_MP4} ({size_mb:.2f} MB)")
            else:
                log("渲染返回 0 但输出文件不存在", "WARN")
        else:
            stderr_lines = result.stderr.splitlines() if result.stderr else []
            if stderr_lines:
                log("错误输出（最后 10 行）:")
                for line in stderr_lines[-10:]:
                    print(f"    {line}")

    except subprocess.TimeoutExpired:
        print("[FAIL] 渲染超时（300s）")
        return
    except Exception as e:
        print(f"[FAIL] 渲染异常: {e}")
        return

    # 最终结论
    print("\n" + "=" * 70)
    if Path(OUTPUT_MP4).exists():
        size_mb = Path(OUTPUT_MP4).stat().st_size / (1024 * 1024)
        print("  [PASS] 渲染完成!")
        print(f"  输出: {OUTPUT_MP4}")
        print(f"  大小: {size_mb:.2f} MB")
        print("  帧范围: 1-60")
    else:
        print("  [FAIL] 渲染失败，输出文件不存在")
    print("=" * 70)


if __name__ == "__main__":
    main()
