"""快速渲染验证：直接测试 AERenderEngine 生产链路"""
import sys
import time
from pathlib import Path


# ==== 脚本守卫 (2026-09-24) ====
# 本文件是**手工运行的脚本**，不是 pytest 用例。模块级代码会启动 AfterFX.exe GUI
# 并在结束时 sys.exit()，被 pytest 收集时会把 pytest 杀掉、把 AE 留在桌面上
# （实测事故：用户看到"是否保存对 xxx.aep 的更改?"，点取消后 AE 关闭）。
# 故被 import 时立刻失败；`python tests/<file>.py` 直接运行不受影响。
if __name__ != "__main__":
    raise ImportError(
        "这是脚本而非 pytest 用例，请用 `python tests/"
        + __file__.replace("\\", "/").split("tests/")[-1] +
        "` 直接运行；不要用 pytest 指定该文件路径（会拉起 AE）。"
    )
# ==== /脚本守卫 ====
sys.path.insert(0, str(Path(__file__).parent.parent))

from rendering.ae_render_engine import (
    AERenderEngine,
    AerenderExitCode,
    RenderJob,
    RenderStatus,
    detect_aerender,
)

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "aerender_final_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TS = time.strftime("%Y%m%d_%H%M%S")
COMP_NAME = "FinalTest"


def create_test_aep(aerender_path: Path) -> Path:
    """用 AfterFX.exe -r 创建测试 AEP"""
    afterfx = aerender_path.parent / "AfterFX.exe"
    if not afterfx.exists():
        print(f"FAIL: AfterFX.exe not found at {afterfx}")
        sys.exit(1)
    print(f"AfterFX: {afterfx}")

    aep_path = OUTPUT_DIR / f"test_{TS}.aep"
    jsx_path = OUTPUT_DIR / f"create_{TS}.jsx"
    aep_str = str(aep_path).replace("\\", "/")

    jsx = (
        '(function(){'
        f'var p=app.newProject();'
        f'var c=p.items.addComp("{COMP_NAME}",1280,720,1,2.0,30);'
        'var s=c.layers.addSolid([0.3,0.5,0.8],"BG",1280,720,1);'
        'var t=c.layers.addText("AE Render Engine v2");'
        f'p.save(File("{aep_str}"));'
        'p.close(CloseOptions.DO_NOT_SAVE_CHANGES);'
        'app.quit();'
        '})();'
    )
    jsx_path.write_text(jsx, encoding="utf-8")
    print(f"Creating AEP: {aep_path.name}...")
    import subprocess
    t0 = time.time()
    proc = subprocess.run(
        [str(afterfx), "-r", str(jsx_path)],
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace"
    )
    dt = time.time() - t0
    if aep_path.exists():
        print(f"OK: AEP created ({aep_path.stat().st_size/1024:.1f} KB, {dt:.1f}s)")
        return aep_path
    print(f"FAIL: AEP not created (exit {proc.returncode})")
    sys.exit(1)


def main():
    print("=" * 60)
    print("AE Render Engine v2 - 最终生产验证")
    print("=" * 60)

    aerender = detect_aerender()
    if not aerender:
        print("FAIL: aerender not found")
        sys.exit(1)
    print(f"aerender: {aerender}")

    aep = create_test_aep(Path(aerender))
    out_path = OUTPUT_DIR / f"render_{TS}.mov"

    print(f"\n[渲染] comp={COMP_NAME} -> {out_path.name}")
    engine = AERenderEngine(aerender_path=str(aerender))

    last_pct = [-1.0]

    def on_progress(pct, j):
        if abs(pct - last_pct[0]) > 2:
            print(f"  ... {pct:.0f}% (frame {j.current_frame}/{j.total_frames})")
            last_pct[0] = pct

    t0 = time.time()
    job = engine.render_sync(
        project=str(aep),
        composition=COMP_NAME,
        output=str(out_path),
        output_format="mov",
        timeout=120,
        multi_process=False,  # 禁用多进程避免冷启动问题
        on_progress=on_progress,
    )
    dt = time.time() - t0

    print("\n[结果]")
    print(f"  状态: {job.status.value}")
    print(f"  耗时: {dt:.1f}s")
    print(f"  尝试次数: {job.attempts}")

    actual_out = Path(job.output_path)
    if job.status == RenderStatus.SUCCESS and actual_out.exists():
        size_kb = actual_out.stat().st_size / 1024
        print(f"  输出文件: {actual_out.name} ({size_kb:.1f} KB)")
        diag = job.diagnostics
        if diag:
            print(f"  退出码: {diag.error_code}")
        print("\n" + "=" * 60)
        print("SUCCESS: 渲染引擎 v2 生产验证通过!")
        print("=" * 60)
        return 0
    else:
        diag = job.diagnostics
        print("  失败!")
        if diag:
            print(f"  退出码: {diag.error_code}")
            print(f"  分类: {diag.error_category}")
            print(f"  描述: {diag.error_description}")
            print(f"  建议: {diag.suggestion}")
            print("\n--- stdout tail ---")
            print(diag.stdout_tail[-800:])
        print("\nFAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
