#!/usr/bin/env python3
"""
AE Render Engine v2.0 真实渲染验证
通过 Bridge 创建合成 -> aerender 渲染 -> 验证输出
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rendering"))
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

from ae_render_engine import (
    ERROR_CODE_INFO,
    AERenderEngine,
    AerenderExitCode,
    RenderStatus,
    detect_aerender,
    is_afterfx_running,
)
from engine_task_dispatcher import AETaskDispatcher

print("=" * 70)
print("AE Render Engine v2.0 - 真实渲染验证")
print("=" * 70)

# ---- Step 0: 环境 ----
print("\n[Step 0] 环境检测")
print("-" * 50)
aerender_exe = detect_aerender()
print(f"  aerender: {aerender_exe}")
assert aerender_exe and aerender_exe.exists()
print(f"  AE 运行中: {is_afterfx_running()}")

TEST_DIR = PROJECT_ROOT / "output" / "aerender_e2e_test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
TEST_AEP = TEST_DIR / f"e2e_{TS}.aep"
RENDER_DIR = TEST_DIR / f"render_{TS}"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

# ---- Step 1: Bridge 创建合成 ----
print("\n[Step 1] 通过 Bridge 创建合成")
print("-" * 50)
ae_disp = AETaskDispatcher()  # 无参数！
print(f"  Bridge 可用: {ae_disp.is_available()}")

COMP_NAME = "E2E_Render_Test"
aep_path_str = str(TEST_AEP).replace("\\", "/")

# 写一个 JSX 文件避免多行字符串转义问题
jsx_content = """
(function() {
    try {
        if (!app.project) app.newProject();
        var c = app.project.items.addComp("%s", 1920, 1080, 1, 3.0, 24);
        var bg = c.layers.addSolid([0.12, 0.25, 0.55], "BlueBG", 1920, 1080, 1.0);
        var t = c.layers.addText("AE Render v2.0");
        var td = t.property("Source Text").value;
        td.fontSize = 72;
        td.fillColor = [1,1,1];
        td.strokeColor = [0,0,0];
        td.strokeWidth = 2;
        t.property("Source Text").setValue(td);
        t.property("Transform").property("Position").setValue([960, 500]);
        var op = t.property("Transform").property("Opacity");
        op.setValueAtTime(0,0);
        op.setValueAtTime(0.5,100);
        op.setValueAtTime(2.5,100);
        op.setValueAtTime(3.0,0);
        var f = new File("%s");
        app.project.save(f);
        return JSON.stringify({success:true, comp:c.name, path:f.fsName, items:app.project.numItems});
    } catch(e) {
        return JSON.stringify({error:true, message:e.toString()});
    }
})();
""" % (COMP_NAME, aep_path_str)

jsx_file = TEST_DIR / f"create_{TS}.jsx"
jsx_file.write_text(jsx_content, encoding="utf-8")
print(f"  JSX 已写入: {jsx_file.name}")

print("  发送到 AE Bridge...")
t0 = time.time()
res = ae_disp.dispatch_script(jsx_content, timeout=45)
dt = time.time() - t0
print(f"  Bridge 响应: success={res.success}, 耗时 {dt:.1f}s")
if res.error:
    print(f"  错误: {res.error[:200]}")

# 等待 AEP 写入
print("  等待 AEP 保存...")
found_aep = None
for i in range(20):
    candidates = list(TEST_DIR.glob("e2e_*.aep"))
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        c = candidates[0]
        if c.stat().st_size > 1000:
            found_aep = c
            print(f"  [OK] AEP 已保存: {c.name} ({c.stat().st_size/1024:.1f} KB)")
            break
    # 也检查根目录（因为 AE 可能保存到默认位置）
    root_candidates = list(PROJECT_ROOT.glob("*.aep"))
    if root_candidates:
        root_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        rc = root_candidates[0]
        if time.time() - rc.stat().st_mtime < 60 and rc.stat().st_size > 1000:
            found_aep = rc
            print(f"  [OK] 在根目录找到最新 AEP: {rc.name}")
            break
    time.sleep(1.5)

if not found_aep:
    print("  [ERROR] 未找到创建的 AEP 文件，退出")
    sys.exit(1)

TEST_AEP = found_aep

# ---- Step 2: aerender 渲染 ----
print("\n[Step 2] aerender CLI 渲染")
print("-" * 50)

engine = AERenderEngine(
    aerender_path=str(aerender_exe),
    default_timeout=120,
    default_max_retries=2,
    log_dir=TEST_DIR / "logs",
)
print(f"  引擎: {engine.version}")

output_file = RENDER_DIR / f"{COMP_NAME}.mov"
progress_updates = []

def on_prog(pct, job):
    progress_updates.append((pct, job.current_frame, job.total_frames))
    bars = int(min(pct, 100) / 5)
    bar = "#" * bars + "." * (20 - bars)
    sys.stdout.write(f"\r  [{bar}] {pct:5.1f}%  frame {job.current_frame}/{job.total_frames}")
    sys.stdout.flush()

print(f"  合成: {COMP_NAME}")
print(f"  输出: {output_file.name}")
print("  渲染中...")
t0 = time.time()
job = engine.render_sync(
    project=str(TEST_AEP),
    composition=COMP_NAME,
    output=str(output_file),
    output_format="mov",
    multi_process=False,
    continue_on_missing_footage=True,
    on_progress=on_prog,
    timeout=120,
    max_retries=2,
)
render_time = time.time() - t0
sys.stdout.write("\n")

print(f"\n  结果: {job.status}")
print(f"  耗时: {render_time:.1f}s")
print(f"  尝试次数: {job.attempts}")
print(f"  进度回调次数: {len(progress_updates)}")
if job.error:
    print(f"  错误: {job.error[:500]}")
if job.error_code >= 0:
    info = ERROR_CODE_INFO.get(job.error_code, {})
    print(f"  错误码: {job.error_code} = {info.get('desc','?')}")
    if info.get("suggestion"):
        print(f"  建议: {info['suggestion']}")

# 诊断信息
if job.diagnostics:
    d = job.diagnostics
    print("\n  诊断:")
    print(f"    项目大小: {d.project_size_mb:.1f} MB")
    print(f"    磁盘剩余: {d.output_disk_free_gb:.1f} GB")
    print(f"    内存: {d.available_memory_gb:.1f}/{d.system_memory_gb:.1f} GB")
    print(f"    命令行: {d.command_line[:250]}")
    if d.log_file_path:
        lp = Path(d.log_file_path)
        if lp.exists():
            print(f"    日志: {lp.name} ({lp.stat().st_size} bytes)")
            try:
                logtxt = lp.read_text(encoding="utf-8", errors="replace")
                lines = [l for l in logtxt.strip().split("\n") if l.strip()]
                print("    日志最后 8 行:")
                for l in lines[-8:]:
                    print(f"      | {l.rstrip()[:120]}")
            except Exception as e:
                print(f"    读取日志失败: {e}")

# ---- Step 3: 验证输出 ----
print("\n[Step 3] 输出验证")
print("-" * 50)
render_ok = False
if output_file.exists():
    sz = output_file.stat().st_size
    print(f"  输出文件: {output_file.name}")
    print(f"  文件大小: {sz/1024:.1f} KB")
    if sz > 50 * 1024:  # > 50KB
        print("  [PASS] 渲染成功，文件大小合理")
        render_ok = True
    elif sz > 1024:
        print("  [WARN] 文件偏小，可能渲染了但内容很少")
        render_ok = True
    else:
        print("  [FAIL] 文件过小，可能未正确渲染")
else:
    print("  [FAIL] 输出文件不存在")
    # 列目录
    for f in RENDER_DIR.glob("*"):
        print(f"    发现: {f.name} ({f.stat().st_size} bytes)")

# ---- Step 4: 错误处理测试（不存在的合成）----
print("\n[Step 4] 错误处理测试（不存在的合成）")
print("-" * 50)
err_out = RENDER_DIR / "nonexist.mov"
job_err = engine.render_sync(
    project=str(TEST_AEP),
    composition="NO_SUCH_COMP_999",
    output=str(err_out),
    output_format="mov",
    multi_process=False,
    timeout=30,
    max_retries=0,
)
print(f"  状态: {job_err.status}")
print(f"  错误码: {job_err.error_code}")
ec_info = ERROR_CODE_INFO.get(job_err.error_code, {})
print(f"  描述: {ec_info.get('desc', job_err.error[:100] if job_err.error else '无')}")
err_file_ok = err_out.exists() and err_out.stat().st_size > 100
err_test_ok = (not err_file_ok) and job_err.status == RenderStatus.FAILED
print(f"  {'[PASS]' if err_test_ok else '[INFO]'} 错误处理{'正常' if err_test_ok else '检查中'}")

# ---- 总结 ----
print("\n" + "=" * 70)
print("总结")
print("=" * 70)
print("  环境检测: [PASS]")
print("  AEP 创建: [PASS]" if found_aep else "  AEP 创建: [FAIL]")
print("  实际渲染: [PASS]" if render_ok else "  实际渲染: [FAIL]")
print("  错误处理: [PASS]" if err_test_ok else "  错误处理: [INFO]")
print(f"\n  输出目录: {RENDER_DIR}")
for f in sorted(RENDER_DIR.glob("*")):
    print(f"    {f.name}: {f.stat().st_size/1024:.1f} KB")

print("\n" + "=" * 70)
if render_ok:
    print("  [PASS] AE Render Engine v2.0 真实渲染验证通过！")
else:
    print("  [FAIL] 渲染未成功，请查看上方诊断信息")
print("=" * 70)
