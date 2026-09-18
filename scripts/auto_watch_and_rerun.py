r"""后台 watcher：监控批量重跑完成，自动运行显著性重跑。

用法:
    start /B python auto_watch_and_rerun.py
    nohup python auto_watch_and_rerun.py &

策略:
1. 轮询 D:\AE-Work\rerun_results.json 是否生成
2. 生成后读取，筛选 detection_rate < 0.1 的视频
3. 自动调用 auto_saliency_rerun.py
4. 完成后写入 D:\AE-Work\saliency_rerun_done.marker
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
RESULTS_FILE = Path(r"D:\AE-Work\rerun_results.json")
SALIENCY_DONE = Path(r"D:\AE-Work\saliency_rerun_done.marker")
SALIENCY_SCRIPT = PROJECT_ROOT / "scripts" / "auto_saliency_rerun.py"


def main():
    print("[Watcher] 启动监控...")
    print(f"[Watcher] 等待 {RESULTS_FILE} 生成")
    print("[Watcher] 批量重跑完成后将自动调用显著性重跑")
    print(f"[Watcher] 完成标记: {SALIENCY_DONE}")
    print()

    start_time = time.time()
    check_interval = 30  # 每 30 秒检查一次

    while True:
        elapsed = time.time() - start_time

        # 检查批量重跑是否完成
        if RESULTS_FILE.exists():
            print(f"[Watcher] 检测到结果文件! (耗时 {elapsed/60:.1f} 分钟)")
            print("[Watcher] 等待 10 秒确保文件写入完成...")
            time.sleep(10)

            # 检查显著性重跑是否已完成
            if SALIENCY_DONE.exists():
                print("[Watcher] 显著性重跑已完成，退出")
                return

            # 启动显著性重跑
            print(f"[Watcher] 启动显著性重跑: {SALIENCY_SCRIPT}")
            print("=" * 70)
            try:
                proc = subprocess.run(
                    [PYTHON, str(SALIENCY_SCRIPT), "--threshold", "0.1", "--num-points", "3"],
                    cwd=str(PROJECT_ROOT),
                )
                if proc.returncode == 0:
                    SALIENCY_DONE.write_text(
                        f"completed at {time.strftime('%Y-%m-%d %H:%M:%S')}",
                        encoding="utf-8",
                    )
                    print(f"[Watcher] 显著性重跑完成! 标记写入: {SALIENCY_DONE}")
                else:
                    print(f"[Watcher] 显著性重跑失败，退出码: {proc.returncode}")
            except Exception as e:
                print(f"[Watcher] 异常: {e}")
            return

        # 检查超时（3 小时）
        if elapsed > 3 * 3600:
            print("[Watcher] 超时（3 小时），退出")
            return

        # 显示进度
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print(f"[Watcher] 等待中... {minutes}分{seconds}秒", flush=True)
        time.sleep(check_interval)


if __name__ == "__main__":
    main()
