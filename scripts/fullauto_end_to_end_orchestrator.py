#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================
  PR → Resolve 全链路一键编排器 v1.0
  (PR全自动管线 第十章待推进任务 P3: 全链路一键编排)
==============================================================

  管线架构（对应实验报告第二章）：
  ┌─────────────────────────────────────────────────────────────┐
  │  Phase 1: PR 剪辑（Startup 脚本，主线程执行）                │
  │    ├── 素材导入 (importFiles)                               │
  │    ├── 时间轴排列 (insertClip)                              │
  │    ├── 转场效果 (addTransition, Phase 3 增强版 6 种转场)     │
  │    └── 保存 .prproj                                         │
  ├─────────────────────────────────────────────────────────────┤
  │  Phase 2: DaVinci Resolve 调色 + 渲染 (fuscript Lua)        │
  │    ├── 导入素材 → 创建时间线                                 │
  │    ├── 电影级调色 (Teal-Orange: Lift/Gamma/Gain/...)        │
  │    └── 渲染输出 (ProRes 422 HQ, 编码器已持久化)             │
  └─────────────────────────────────────────────────────────────┘

  遵循的最佳实践（来自实验报告第十二章 7 条经验）：
    #1: SetRenderSettings 返回值不可靠 → 强制 FourCC 二进制验证
    #2: 编码器选择是 UI 级设置 → 持久化后脚本无需触碰
    #4: PR Startup 脚本是唯一可靠的写入方式 → Phase 1 用此方案
    #5: fuscript.exe -lua 是 Resolve 唯一可靠通道 → Phase 2 用此方案
    #7: 验证必须到二进制层 → FourCC apch 验证 + 文件大小合理性检查

  用法：
    py -3.12 scripts/fullauto_end_to_end_orchestrator.py
    py -3.12 scripts/fullauto_end_to_end_orchestrator.py --skip-pr     # 跳过 PR 直接渲染
    py -3.12 scripts/fullauto_end_to_end_orchestrator.py --skip-render # 只跑 PR 剪辑
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import io
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ── 编码强制 UTF-8 ─────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ==============================================================
# 配置（对应报告第十一章 环境信息）
# ==============================================================
@dataclass
class Config:
    # PR
    PR_EXE: Path = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe")
    PR_PROJECT: Path = Path(r"D:\AE-Work\pr\1.prproj")
    STARTUP_DIR: Path = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup")
    STARTUP_SCRIPT_SRC: Path = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\pr_fullauto_startup.jsx")
    STARTUP_SCRIPT_DST_NAME: str = "99_pr_fullauto_executor.jsx"

    # 桥接目录（Startup 脚本读写命令/结果）
    BRIDGE_DIR: Path = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.premiere-mcp-bridge")
    CMD_FILE: str = "pr_fullauto_cmd.json"
    RES_FILE: str = "pr_fullauto_result.json"
    LOG_FILE: str = "fullauto_startup_log.txt"

    # Resolve
    RESOLVE_DIR: Path = Path(r"D:\DaVinci Resolve")
    FUSCRIPT_EXE: str = "fuscript.exe"
    RESOLVE_LUA_SCRIPT: Path = Path(
        r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\temp\_resolve_prores_pipeline.lua"
    )

    # 素材 & 输出（冰海战记素材库）
    STOCK_DIR: Path = Path(r"D:\AE-Work\视频素材库\冰海战记片段")
    BGM_PATH: Path = Path(r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3")
    OUTPUT_DIR: Path = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output")

    # 超时
    PR_RESULT_TIMEOUT: int = 240   # PR Startup 脚本最长等待时间
    PR_CLOSE_TIMEOUT: int = 40      # PR 关闭超时
    RESOLVE_TIMEOUT: int = 900      # Resolve 渲染超时（15 分钟）
    MAX_CLIPS: int = 8              # 8 个冰海战记片段（覆盖多场景）

    @property
    def cmd_path(self) -> Path: return self.BRIDGE_DIR / self.CMD_FILE

    @property
    def res_path(self) -> Path: return self.BRIDGE_DIR / self.RES_FILE

    @property
    def log_path(self) -> Path: return self.BRIDGE_DIR / self.LOG_FILE

    @property
    def startup_script_dst(self) -> Path:
        return self.STARTUP_DIR / self.STARTUP_SCRIPT_DST_NAME

    @property
    def fuscript_path(self) -> Path:
        return self.RESOLVE_DIR / self.FUSCRIPT_EXE


CFG = Config()


# ==============================================================
# Win32 工具（关闭窗口、进程检测）
# ==============================================================
WM_CLOSE = 0x0010
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002


def find_window_by_class(class_name: str) -> int | None:
    results: list[int] = []
    EWP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            if buf.value == class_name:
                results.append(hwnd)
        return True
    ctypes.windll.user32.EnumWindows(EWP(cb), 0)
    return results[0] if results else None


def is_process_running(exe_name: str) -> bool:
    r = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
        capture_output=True, text=True
    )
    return exe_name.lower() in r.stdout.lower()


def dismiss_dialogs() -> None:
    """关闭可能弹出的模态对话框（#32770 类）"""
    EWP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            cls = buf.value
            if cls == "#32770":
                ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
                time.sleep(0.3)
            elif cls == "DroverLord - Window Class":
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.3)
        return True
    ctypes.windll.user32.EnumWindows(EWP(cb), 0)


def close_pr_gracefully(timeout: int = CFG.PR_CLOSE_TIMEOUT) -> bool:
    """优雅关闭 PR（WM_CLOSE → 超时不强杀，保留项目）"""
    if not is_process_running("Adobe Premiere Pro.exe"):
        return True
    print("  正在关闭 Premiere Pro...")
    dismiss_dialogs()
    time.sleep(0.5)
    hwnd = find_window_by_class("Premiere Pro")
    if hwnd:
        ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
    for i in range(timeout):
        time.sleep(1)
        dismiss_dialogs()
        if not is_process_running("Adobe Premiere Pro.exe"):
            print(f"  ✓ PR 已关闭 ({i+1}s)")
            return True
        if i % 5 == 4 and hwnd:
            ctypes.windll.user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
    print(f"  ⚠ PR {timeout}s 内未关闭（不强杀，跳过）")
    return False


def launch_pr_with_project() -> bool:
    """启动 PR 并打开项目（Startup 脚本会在项目打开后自动执行）"""
    print(f"  启动 PR 项目: {CFG.PR_PROJECT.name}")
    CFG.PR_PROJECT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [str(CFG.PR_EXE), str(CFG.PR_PROJECT)],
        cwd=str(CFG.PR_EXE.parent)
    )
    time.sleep(3)
    return is_process_running("Adobe Premiere Pro.exe")


# ==============================================================
# 日志工具
# ==============================================================
class PipelineLogger:
    def __init__(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = output_dir / f"pipeline_{ts}.log"
        self.fp = open(self.log_file, "w", encoding="utf-8")
        self.stages: list[dict] = []

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        self.fp.write(line + "\n")
        self.fp.flush()

    def section(self, title: str) -> None:
        sep = "=" * 68
        self.log("")
        self.log(sep)
        self.log(f"  {title}")
        self.log(sep)

    def start_stage(self, name: str) -> None:
        self.stages.append({"name": name, "start": time.time(), "ok": False})
        self.section(f"▶ 阶段 {len(self.stages)}: {name}")

    def end_stage(self, ok: bool, detail: str = "") -> None:
        if not self.stages:
            return
        s = self.stages[-1]
        s["ok"] = ok
        s["elapsed"] = time.time() - s["start"]
        s["detail"] = detail
        icon = "✓" if ok else "✗"
        self.log(f"  {icon} 阶段完成: {s['name']} 用时 {s['elapsed']:.1f}s {detail}")

    def final_summary(self) -> None:
        self.section("✦ 全管线最终总结")
        total = sum(s.get("elapsed", 0) for s in self.stages)
        self.log(f"  总用时: {total:.1f}s")
        self.log("")
        all_ok = True
        for i, s in enumerate(self.stages, 1):
            icon = "✓" if s.get("ok") else "✗"
            if not s.get("ok"):
                all_ok = False
            self.log(f"    {i}. {icon} {s['name']}  ({s.get('elapsed', 0):.1f}s)  {s.get('detail', '')}")
        self.log("")
        if all_ok:
            self.log("  ✓✓✓ 全链路 PASS — ProRes 422 HQ 视觉无损渲染完成!")
        else:
            self.log("  ✗ 部分阶段失败 — 请查看上方日志排查")
        self.log(f"  详细日志: {self.log_file}")
        self.fp.close()


# ==============================================================
# Phase 1: PR 剪辑（Startup 脚本）
# ==============================================================
def phase1_pr_edit(logger: PipelineLogger) -> dict | None:
    """
    Phase 1: PR Startup 脚本自动化剪辑
      - 部署 Startup 脚本（经验 #4：唯一可靠的写入方式）
      - 写入命令文件 → 关闭 PR → 启动 PR → Startup 脚本自动执行
      - 等待结果文件（包含导入/排列/转场/导出/保存 各步骤结果）
    """
    logger.start_stage("PR 剪辑 (Startup 脚本模式)")

    # 准备目录
    CFG.BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    CFG.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CFG.STARTUP_DIR.mkdir(parents=True, exist_ok=True)

    # 素材选择：从冰海战记片段中选择不同场景的片段
    all_clips = sorted(CFG.STOCK_DIR.glob("clip_*.mp4"))
    if not all_clips:
        logger.end_stage(False, f"素材目录为空: {CFG.STOCK_DIR}")
        return None

    # 选择不同场景的片段（clip_N_1 格式，每个场景的第1个片段）
    # 覆盖: S1OP1, S1ED1, S1OP2, S1ED2, S2OP1, S2ED1, S2OP2, S2ED2, 封神场面, 打戏, MAD, Revolution
    selected_clips = []
    seen_scenes = set()
    for clip in all_clips:
        # clip_N_X.mp4 → 提取场景号 N
        parts = clip.stem.split("_")
        if len(parts) >= 2:
            scene = parts[1]
            if scene not in seen_scenes:
                selected_clips.append(clip)
                seen_scenes.add(scene)
        if len(selected_clips) >= CFG.MAX_CLIPS:
            break

    # 如果不够，补充其他片段
    if len(selected_clips) < CFG.MAX_CLIPS:
        for clip in all_clips:
            if clip not in selected_clips:
                selected_clips.append(clip)
            if len(selected_clips) >= CFG.MAX_CLIPS:
                break

    media_paths = [str(p).replace("\\", "/") for p in selected_clips]
    logger.log(f"  冰海战记素材清单 ({len(media_paths)} 个):")
    for p in selected_clips:
        logger.log(f"    · {p.name} ({p.stat().st_size/1048576:.1f} MB)")

    # BGM 检查
    bgm_path_str = ""
    if CFG.BGM_PATH.exists():
        bgm_path_str = str(CFG.BGM_PATH).replace("\\", "/")
        logger.log(f"  BGM: {CFG.BGM_PATH.name} ({CFG.BGM_PATH.stat().st_size/1048576:.1f} MB)")
    else:
        logger.log(f"  ⚠ BGM 文件不存在: {CFG.BGM_PATH}")

    # 1) 部署 Startup 脚本
    logger.log("  [1/5] 部署 Startup 脚本...")
    try:
        shutil.copy2(str(CFG.STARTUP_SCRIPT_SRC), str(CFG.startup_script_dst))
        logger.log(f"    ✓ 已部署: {CFG.startup_script_dst.name}")
    except Exception as e:
        logger.end_stage(False, f"Startup 部署失败: {e}")
        return None

    # 2) 清理旧结果 & 写入命令
    logger.log("  [2/5] 写入命令文件...")
    for f in [CFG.res_path, CFG.log_path]:
        if f.exists():
            try: f.unlink()
            except: pass
    export_path = CFG.OUTPUT_DIR / "pr_phase1_output.mp4"
    cmd = {
        "action": "full_pipeline",
        "files": media_paths,
        "bgmPath": bgm_path_str,
        "sequenceName": "VinlandSagaEdit",
        "exportPath": str(export_path).replace("\\", "/"),
        "maxClips": CFG.MAX_CLIPS,
        "preset": "HD 1080p 23.976",
    }
    CFG.cmd_path.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    logger.log(f"    ✓ 命令: full_pipeline (导入{len(media_paths)}片段+BGM+排列+转场+导出+保存)")

    # 3) 关闭 PR（让 Startup 脚本在下一次启动时被触发）
    logger.log("  [3/5] 关闭 PR...")
    if not close_pr_gracefully():
        logger.log("    ⚠ PR 未完全关闭，继续尝试...")

    # 4) 启动 PR（Startup 脚本会在主线程中执行）
    logger.log("  [4/5] 启动 PR...")
    time.sleep(2)
    dismiss_dialogs()
    if not launch_pr_with_project():
        logger.end_stage(False, "PR 启动失败")
        return None
    logger.log("    ✓ PR 进程已启动，Startup 脚本将在项目加载后执行")

    # 5) 等待 Startup 脚本执行结果
    logger.log(f"  [5/5] 等待结果 (最长 {CFG.PR_RESULT_TIMEOUT}s)...")
    time.sleep(10)  # 给 PR 启动时间
    start = time.time()
    result: dict | None = None
    last_dismiss = 0
    while time.time() - start < CFG.PR_RESULT_TIMEOUT:
        dismiss_dialogs()
        if CFG.res_path.exists():
            try:
                content = CFG.res_path.read_text(encoding="utf-8")
                if content and len(content) > 5:
                    result = json.loads(content)
                    break
            except (json.JSONDecodeError, OSError):
                pass
        # 每 10s 打印一次等待状态
        elapsed = int(time.time() - start)
        if elapsed % 15 == 0 and elapsed > 0:
            logger.log(f"    ...已等待 {elapsed}s...")
        time.sleep(2)

    if result is None:
        logger.log("    ✗ 等待超时，读取 Startup 日志...")
        if CFG.log_path.exists():
            log_tail = CFG.log_path.read_text(encoding="utf-8", errors="replace")[-800:]
            logger.log(f"    Startup 日志尾部:\n{log_tail}")
        logger.end_stage(False, "PR 结果超时")
        return None

    # 分析结果
    steps = result.get("steps", {})
    arrange = steps.get("arrange", {})
    trans = steps.get("transitions", {})
    trans_info = steps.get("transitionInfo", {})
    save = steps.get("save", {})

    summary_parts = []
    imp = steps.get("import", {})
    if imp.get("ok"):
        summary_parts.append(f"导入{imp.get('count', 0)}")
    if arrange.get("inserted"):
        summary_parts.append(f"上轨{arrange.get('inserted')}/{arrange.get('totalAvailable', '?')}")
    bgm = steps.get("bgm", {})
    if bgm.get("ok") and not bgm.get("skipped"):
        summary_parts.append(f"BGM✓({bgm.get('name', '?')[:20]})")
    elif bgm.get("ok") and bgm.get("skipped"):
        summary_parts.append("BGM跳过")
    else:
        summary_parts.append("BGM✗")
    if trans:
        summary_parts.append(f"转场{trans.get('applied', 0)}")
        if trans_info.get("verifiedTransitions"):
            summary_parts[-1] += f"(验{trans_info['verifiedTransitions']})"
    if save.get("ok"):
        summary_parts.append("保存✓")

    summary = " | ".join(summary_parts)
    ok = result.get("success", False) and arrange.get("inserted", 0) > 0

    # 详细输出转场信息（Phase 3 重点！）
    if trans_info:
        logger.log("  转场验证详情 (Phase 3):")
        logger.log(f"    · 尝试方法: {', '.join(trans_info.get('methodsTried', []))}")
        logger.log(f"    · 尝试转场: {', '.join(trans_info.get('typesTried', []))}")
        logger.log(f"    · 时间轴 clips: {trans_info.get('trackClips', '?')}")
        logger.log(f"    · 报告 applied: {trans.get('applied', 0)}  verified: {trans_info.get('verifiedTransitions', '?')}")

    if trans_info.get("verifiedTransitions", 0) == 0 and arrange.get("inserted", 0) >= 2:
        logger.log("    ⚠ 转场未能自动应用（PR 脚本 API 限制），可手动补充或等待后续改进")
    elif trans_info.get("verifiedTransitions", 0) > 0:
        logger.log("    ✓ 转场验证成功!")

    # 保存结果到 output
    result_file = CFG.OUTPUT_DIR / "pr_phase1_result.json"
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.end_stage(ok, summary)
    return result


# ==============================================================
# Phase 2: Resolve 调色 + ProRes 渲染（fuscript Lua）
# ==============================================================
def phase2_resolve_render(logger: PipelineLogger) -> dict | None:
    """
    Phase 2: Resolve fuscript Lua 渲染
      - 检查 Resolve 是否运行（未运行则给出提示）
      - 调用 fuscript.exe -lua <script> 执行 Lua 脚本
      - 实时输出渲染进度
      - 最终 FourCC 验证（经验 #1 #7）
    """
    logger.start_stage("Resolve 调色 + ProRes 422 HQ 渲染 (fuscript Lua)")

    # 验证脚本 & fuscript 存在
    if not CFG.RESOLVE_LUA_SCRIPT.exists():
        logger.end_stage(False, f"Lua 脚本不存在: {CFG.RESOLVE_LUA_SCRIPT}")
        return None
    if not CFG.fuscript_path.exists():
        logger.end_stage(False, f"fuscript.exe 不存在: {CFG.fuscript_path}")
        return None

    # 检查 Resolve 进程
    resolve_running = (
        is_process_running("Resolve.exe") or
        is_process_running("DaVinci Resolve.exe")
    )
    if not resolve_running:
        logger.log("  ⚠ 未检测到 Resolve 进程")
        logger.log("  请先启动 DaVinci Resolve Studio 21.0 并保持在主界面")
        logger.log("  等待 Resolve 启动（最多 60s）...")
        start = time.time()
        while time.time() - start < 60:
            time.sleep(3)
            if (is_process_running("Resolve.exe") or
                    is_process_running("DaVinci Resolve.exe")):
                logger.log("  ✓ Resolve 已启动，等待 10s 完全加载...")
                time.sleep(10)
                resolve_running = True
                break
        if not resolve_running:
            logger.end_stage(False, "Resolve 未启动，渲染阶段跳过")
            return None

    logger.log(f"  Lua 脚本: {CFG.RESOLVE_LUA_SCRIPT.name}")
    logger.log(f"  fuscript: {CFG.fuscript_path}")
    logger.log("  说明: 编码器 Format=QuickTime / Codec=ProRes 422 HQ 通过 UI 持久化设置 (第七章)")
    logger.log("  渲染进度将由 Lua 脚本实时输出...")
    logger.log("")

    # 执行 fuscript
    cmd = [
        str(CFG.fuscript_path),
        "-lua",
        str(CFG.RESOLVE_LUA_SCRIPT)
    ]
    logger.log(f"  $ fuscript -lua {CFG.RESOLVE_LUA_SCRIPT.name}")
    logger.log("")

    render_result: dict = {"fourcc_ok": False, "output_path": None, "file_size": 0}

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(CFG.RESOLVE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace"
        )
        assert proc.stdout is not None

        last_output = ""
        start = time.time()
        while True:
            # 超时检查
            if time.time() - start > CFG.RESOLVE_TIMEOUT:
                logger.log(f"  ✗ 渲染超时 ({CFG.RESOLVE_TIMEOUT}s)，强制终止")
                proc.kill()
                break
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
                continue
            line = line.rstrip("\r\n")
            if line:
                # 解析关键输出
                if "FourCC" in line and ("apch" in line or "avc1" in line):
                    last_output = line
                    if "apch" in line and "验证通过" in line:
                        render_result["fourcc_ok"] = True
                if "输出文件:" in line:
                    last_output = line
                logger.log(f"    {line}")

        rc = proc.poll()
        elapsed = time.time() - start

        # 解析输出文件大小 & 路径
        out_files = sorted(
            [p for p in CFG.OUTPUT_DIR.glob("VinlandSaga_ProRes_Output*") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if out_files:
            render_result["output_path"] = str(out_files[0])
            render_result["file_size"] = out_files[0].stat().st_size
            sz_mb = out_files[0].stat().st_size / 1048576
            render_result["size_mb"] = sz_mb

        ok = render_result["fourcc_ok"] and rc == 0
        detail = ""
        if render_result.get("size_mb"):
            detail = f"{render_result['size_mb']:.1f} MB"
            if render_result["fourcc_ok"]:
                detail += " / FourCC=apch ✓"

        logger.end_stage(ok, detail)
        return render_result

    except FileNotFoundError as e:
        logger.end_stage(False, f"fuscript 调用失败: {e}")
        return None
    except Exception as e:
        logger.end_stage(False, f"渲染异常: {e}")
        return None


# ==============================================================
# 主入口
# ==============================================================
def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="PR → Resolve 全链路一键编排器 (Phase 3 + P3 待推进任务)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  py -3.12 scripts/fullauto_end_to_end_orchestrator.py            # 全链路
  py -3.12 scripts/fullauto_end_to_end_orchestrator.py --skip-pr  # 只跑 Resolve
  py -3.12 scripts/fullauto_end_to_end_orchestrator.py --skip-render  # 只跑 PR
        """
    )
    parser.add_argument("--skip-pr", action="store_true", help="跳过 PR 剪辑阶段，直接 Resolve 渲染")
    parser.add_argument("--skip-render", action="store_true", help="只跑 PR 剪辑，跳过 Resolve")
    parser.add_argument("--max-clips", type=int, default=CFG.MAX_CLIPS, help="最多处理多少个素材")
    args = parser.parse_args()

    CFG.MAX_CLIPS = args.max_clips

    # 创建 logger
    logger = PipelineLogger(CFG.OUTPUT_DIR)

    logger.section("✦ PR → Resolve 全链路一键编排器 v1.0")
    logger.log("  遵循 第十二章 7 条经验 & 第七章 编码器持久化最佳实践")
    logger.log(f"  PR 模式:      { '跳过' if args.skip_pr else 'Startup 脚本 (经验 #4)' }")
    logger.log(f"  Resolve 模式: { '跳过' if args.skip_render else 'fuscript -lua (经验 #5)' }")
    logger.log("  编码器验证:   FourCC=apch 二进制级检查 (经验 #1 #7)")

    pr_result = None
    render_result = None

    # Phase 1: PR
    if not args.skip_pr:
        pr_result = phase1_pr_edit(logger)
        if pr_result is None:
            logger.log("  ⚠ PR 阶段失败，是否继续 Resolve 阶段？将直接使用 stock_footage 素材渲染")
            # 继续（Resolve 可以独立处理素材）

    # Phase 2: Resolve
    if not args.skip_render:
        # PR 完成后关闭 PR（释放内存给 Resolve 渲染）
        if not args.skip_pr:
            logger.log("  PR 阶段结束，关闭 PR 释放内存...")
            close_pr_gracefully(timeout=20)
            time.sleep(3)
        render_result = phase2_resolve_render(logger)

    # 最终总结
    logger.final_summary()

    # 最终结果代码
    if args.skip_render:
        return 0 if (pr_result and pr_result.get("success")) else 1
    if args.skip_pr:
        return 0 if (render_result and render_result.get("fourcc_ok")) else 1
    return 0 if (render_result and render_result.get("fourcc_ok")) else 1


if __name__ == "__main__":
    sys.exit(main())
