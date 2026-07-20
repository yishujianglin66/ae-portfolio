"""
V17 自动化生产流水线 - 全链路自主执行
======================================
自动打开/关闭软件，自主判断进度，监控内存，
用 V17 视频完整走一遍生产流程。

Phase 1: 环境检查 + 内存监控
Phase 2: AE 特效制作 (通过 MCP Bridge)
Phase 3: 字幕/文字动画
Phase 4: DaVinci 调色
Phase 5: 开源工具链处理 (RIFE/MoviePy/Remotion)
Phase 6: 最终合成 + 输出
Phase 7: 生成诊断报告
"""

import os
import sys
import time
import json
import ctypes
import subprocess
import traceback

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
os.environ["PATH"] += os.pathsep + r"D:\app\FormatFactory"

# DaVinci Resolve 安装在 D 盘，需要设置环境变量指向 fusionscript DLL
_resolve_dll = r"D:\DaVinci Resolve\fusionscript.dll"
if os.path.exists(_resolve_dll):
    os.environ["RESOLVE_SCRIPT_LIB"] = _resolve_dll

V17_VIDEO = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
OUTPUT_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
LOG = []

# 软件路径
AE_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
RESOLVE_EXE = r"D:\DaVinci Resolve\Resolve.exe"

# 跟踪启动的软件(用于结束时自动关闭)
launched_apps = {}


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}][{level}] {msg}"
    LOG.append(entry)
    print(f"  {entry}")


def get_memory():
    """获取系统内存状态"""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
            ("sullAvailExtendedVirtual", ctypes.c_uint64),
        ]
    ms = MEMORYSTATUSEX()
    ms.dwLength = ctypes.sizeof(ms)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return {
        "total_gb": round(ms.ullTotalPhys / 1024**3, 1),
        "avail_gb": round(ms.ullAvailPhys / 1024**3, 1),
        "load_pct": ms.dwMemoryLoad,
    }


def check_memory_safe(min_avail_gb=2.0):
    """检查内存是否足够，不足则等待释放"""
    mem = get_memory()
    if mem["avail_gb"] < min_avail_gb:
        log(f"内存不足! 可用={mem['avail_gb']}GB, 负载={mem['load_pct']}%", "WARN")
        log("等待10秒让系统释放内存...", "WARN")
        time.sleep(10)
        mem = get_memory()
        if mem["avail_gb"] < min_avail_gb:
            log(f"内存仍不足: {mem['avail_gb']}GB, 继续执行但可能变慢", "WARN")
            return False
    log(f"内存充足: 可用={mem['avail_gb']}GB/{mem['total_gb']}GB ({100-mem['load_pct']}%空闲)")
    return True


def should_continue(max_memory_load=95):
    """自主判断是否继续下一步"""
    mem = get_memory()
    if mem["load_pct"] >= max_memory_load:
        log(f"内存负载过高({mem['load_pct']}%), 暂停等待...", "WARN")
        for _ in range(6):
            time.sleep(5)
            mem = get_memory()
            if mem["load_pct"] < max_memory_load:
                log(f"内存恢复: {mem['avail_gb']}GB 可用")
                return True
        log("内存持续高位，强制继续", "WARN")
    return True


def is_process_running(process_name):
    """检测进程是否在运行"""
    try:
        r = subprocess.run("tasklist", capture_output=True, text=True, shell=True, timeout=10)
        return process_name.lower() in r.stdout.lower()
    except Exception:
        return False


def launch_app(name, exe_path, wait_seconds=60):
    """自动启动软件并等待就绪"""
    global launched_apps
    proc_name = os.path.basename(exe_path)

    if is_process_running(proc_name):
        log(f"{name} 已在运行，跳过启动")
        launched_apps.setdefault(name, proc_name)
        return True

    if not os.path.exists(exe_path):
        log(f"{name} 未找到: {exe_path}", "WARN")
        return False

    log(f"正在启动 {name} ({exe_path})...")
    try:
        subprocess.Popen([exe_path], shell=True)
        launched_apps[name] = proc_name
        log(f"{name} 进程已启动，等待就绪(最多{wait_seconds}s)...")

        # 等待进程出现
        for i in range(wait_seconds):
            time.sleep(1)
            if is_process_running(proc_name):
                # 进程出现了，再等几秒让它完全初始化
                time.sleep(8)
                mem = get_memory()
                log(f"{name} 已就绪 (耗时{i+9}s, 内存可用={mem['avail_gb']}GB)")
                return True
        log(f"{name} 启动超时({wait_seconds}s)", "WARN")
        return False
    except Exception as e:
        log(f"{name} 启动失败: {e}", "ERROR")
        return False


def close_app(name, proc_name=None):
    """自动关闭软件释放内存"""
    if proc_name is None:
        proc_name = launched_apps.get(name)
    if not proc_name:
        return

    if is_process_running(proc_name):
        log(f"正在关闭 {name}...")
        try:
            subprocess.run(f'taskkill /IM "{proc_name}" /F', shell=True,
                           capture_output=True, timeout=15)
            time.sleep(3)
            if not is_process_running(proc_name):
                mem = get_memory()
                log(f"{name} 已关闭 (内存可用={mem['avail_gb']}GB)")
            else:
                log(f"{name} 关闭中...", "WARN")
        except Exception as e:
            log(f"{name} 关闭异常: {e}", "WARN")
    else:
        log(f"{name} 未在运行")


def close_all_apps():
    """关闭所有由脚本启动的软件"""
    log("=" * 40)
    log("清理: 关闭所有启动的软件...")
    for name, proc in list(launched_apps.items()):
        close_app(name, proc)
    launched_apps.clear()


# ================================================================
# Phase 1: 环境检查
# ================================================================
def phase1_env_check():
    print("\n" + "=" * 60)
    print("Phase 1: 环境检查 + 内存监控")
    print("=" * 60)

    mem = get_memory()
    log(f"系统内存: {mem['total_gb']}GB 总量, {mem['avail_gb']}GB 可用, 负载{mem['load_pct']}%")

    # 检查 V17 素材
    if os.path.exists(V17_VIDEO):
        size = os.path.getsize(V17_VIDEO) / 1024 / 1024
        log(f"V17 素材: {size:.1f}MB")
    else:
        log(f"V17 素材不存在: {V17_VIDEO}", "ERROR")
        return False

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 检查各工具
    tools_status = {}
    try:
        from opensource_integrations import OpenSourceHub
        hub = OpenSourceHub()
        status = hub.auto_detect()
        for k, v in status.items():
            tools_status[k] = "OK" if v else "N/A"
        log(f"开源工具: {sum(1 for v in status.values() if v)}/7 可用")
    except Exception as e:
        log(f"开源工具检查失败: {e}", "ERROR")

    try:
        from unified_tool_integrator import UnifiedToolIntegrator
        integrator = UnifiedToolIntegrator(default_mode="simulate", output_dir=OUTPUT_DIR, log_level="WARNING")
        all_tools = integrator.get_available_tools()
        avail = sum(1 for v in all_tools.values() if v)
        log(f"统一调度器: {avail}/{len(all_tools)} 工具可用")
        tools_status["unified_integrator"] = f"{avail}/{len(all_tools)}"
    except Exception as e:
        log(f"统一调度器检查失败: {e}", "ERROR")

    # AE Bridge 检查
    try:
        from ae_mcp_client import AECommandClient
        client = AECommandClient()
        result = client.send_command("ping", {})
        ae_ok = "pong" in str(result).lower() or "success" in str(result).lower()
        tools_status["ae_bridge"] = "OK" if ae_ok else "TIMEOUT"
        log(f"AE Bridge: {'连通' if ae_ok else '超时'}")
    except Exception as e:
        tools_status["ae_bridge"] = f"ERROR: {str(e)[:40]}"
        log(f"AE Bridge: {e}", "WARN")

    # DaVinci 检查
    try:
        from davinci_resolve_integration import DavinciColorist
        colorist = DavinciColorist()
        dv_ok = colorist.is_available()
        tools_status["davinci"] = "OK" if dv_ok else "N/A"
        log(f"DaVinci Resolve: {'已安装' if dv_ok else '未安装'}")
    except Exception as e:
        tools_status["davinci"] = f"ERROR"
        log(f"DaVinci: {e}", "WARN")

    log(f"环境检查完成, 工具状态: {tools_status}")
    return True


# ================================================================
# Phase 2: AE 特效制作
# ================================================================
def phase2_ae_effects():
    print("\n" + "=" * 60)
    print("Phase 2: AE 特效制作 (MCP Bridge)")
    print("=" * 60)

    if not should_continue():
        return
    check_memory_safe(3.0)

    # === 自动启动 AE ===
    log(">>> 自动启动 After Effects...")
    ae_launched = launch_app("After Effects", AE_EXE, wait_seconds=90)
    if not ae_launched:
        log("AE 启动失败，尝试继续(AE可能已在运行)...", "WARN")

    # 等待 AE Bridge 连通
    log("等待 AE Bridge 连通...")
    bridge_ready = False
    for attempt in range(6):
        try:
            from ae_mcp_client import AECommandClient
            client = AECommandClient()
            result = client.send_command("ping", {})
            if "pong" in str(result).lower() or "success" in str(result).lower():
                bridge_ready = True
                log(f"AE Bridge 已连通 (第{attempt+1}次尝试)")
                break
        except Exception:
            pass
        log(f"等待AE就绪... ({attempt+1}/6)")
        time.sleep(10)

    if not bridge_ready:
        log("AE Bridge 未连通，AE操作将跳过", "WARN")
        return

    try:
        from ae_mcp_client import AECommandClient
        client = AECommandClient()

        # 获取 AE 项目信息
        log("获取 AE 项目信息...")
        try:
            proj_info = client.send_command("getProjectInfo", {})
            log(f"项目信息: {str(proj_info)[:120]}")
        except Exception as e:
            log(f"项目信息获取失败(非致命): {e}", "WARN")

        # 通过 execute_script 创建合成
        log("通过 JSX 脚本创建 V17 测试合成...")
        create_comp_jsx = '''
var comp = app.project.items.addComp("V17_Production_Test", 1080, 1920, 1, 5, 30);
JSON.stringify({name: comp.name, width: comp.width, height: comp.height, duration: comp.duration, fps: comp.frameRate});
'''
        try:
            comp_result = client.send_command("execute_script", {"script": create_comp_jsx})
            log(f"合成创建: {str(comp_result)[:120]}")
        except Exception as e:
            log(f"合成创建异常: {e}", "WARN")

        # 通过 execute_script 导入素材
        log("通过 JSX 脚本导入 V17 素材...")
        import_jsx = f'''
var importOptions = new ImportOptions(File("{V17_VIDEO.replace(chr(92), '/')}"));
importOptions.name = "V17_Battle";
var imported = app.project.importFile(importOptions);
JSON.stringify({{name: imported.name, type: imported.typeName}});
'''
        try:
            import_result = client.send_command("execute_script", {"script": import_jsx})
            log(f"素材导入: {str(import_result)[:120]}")
        except Exception as e:
            log(f"素材导入异常: {e}", "WARN")

        # 通过 execute_script 应用效果
        log("通过 JSX 脚本应用 Lumetri Color...")
        apply_fx_jsx = '''
var comp = app.project.activeItem;
var result = {applied: false, effect: ""};
if (comp && comp.numLayers > 0) {
    var layer = comp.layer(1);
    var fx = layer.property("ADBE Effect Parade").addProperty("Lumetri Color");
    result.applied = true;
    result.effect = fx.name;
    result.layer = layer.name;
}
JSON.stringify(result);
'''
        try:
            fx_result = client.send_command("execute_script", {"script": apply_fx_jsx})
            log(f"效果应用: {str(fx_result)[:120]}")
        except Exception as e:
            log(f"效果应用异常: {e}", "WARN")

    except Exception as e:
        log(f"AE 特效阶段异常: {e}", "ERROR")

    # === AE 任务完成，关闭 AE 释放内存 ===
    log(">>> AE 任务完成，关闭 After Effects 释放内存...")
    close_app("After Effects")

    check_memory_safe(2.0)
    log("Phase 2 完成")


# ================================================================
# Phase 3: 字幕/文字动画
# ================================================================
def phase3_subtitle_animation():
    print("\n" + "=" * 60)
    print("Phase 3: 字幕/文字动画")
    print("=" * 60)

    if not should_continue():
        return
    check_memory_safe(2.0)

    # 生成 SRT 字幕
    srt_content = """1
00:00:01,000 --> 00:00:03,500
VINLAND SAGA

2
00:00:04,000 --> 00:00:07,000
Battle Scene - V17 Production

3
00:00:08,000 --> 00:00:11,500
Cinematic Color Grading

4
00:00:12,000 --> 00:00:15,000
AI Enhanced Production Pipeline

5
00:00:16,000 --> 00:00:19,500
Full Open Source Tool Chain
"""
    srt_file = os.path.join(OUTPUT_DIR, "v17_production.srt")
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write(srt_content)
    log(f"SRT 字幕生成: {os.path.getsize(srt_file)} bytes")

    # 尝试通过 AE execute_script 导入字幕
    try:
        from ae_mcp_client import AECommandClient
        client = AECommandClient()
        srt_path_js = srt_file.replace("\\", "/")
        import_srt_jsx = f'''
var importOptions = new ImportOptions(File("{srt_path_js}"));
var imported = app.project.importFile(importOptions);
JSON.stringify({{name: imported.name, type: imported.typeName}});
'''
        log("通过 JSX 导入字幕文件...")
        result = client.send_command("execute_script", {"script": import_srt_jsx})
        log(f"字幕导入: {str(result)[:100]}")
    except Exception as e:
        log(f"AE 字幕导入异常: {e}", "WARN")

    # 生成文字动画表达式
    expressions = {
        "typewriter": 'text.sourceText = text.sourceText.substr(0, Math.floor(time*5));',
        "fade_in": 'opacity = linear(time, inPoint, inPoint+1, 0, 100);',
        "slide_up": 'value + [0, linear(time, inPoint, inPoint+0.5, 100, 0)];',
        "scale_bounce": 'value * linear(time, inPoint, inPoint+0.3, 0, 100) / 100;',
    }
    expr_file = os.path.join(OUTPUT_DIR, "text_animations.json")
    with open(expr_file, "w", encoding="utf-8") as f:
        json.dump(expressions, f, indent=2, ensure_ascii=False)
    log(f"文字动画表达式: {len(expressions)} 个模板已保存")

    check_memory_safe(2.0)
    log("Phase 3 完成")


# ================================================================
# Phase 4: DaVinci 调色
# ================================================================
def phase4_davinci_color():
    print("\n" + "=" * 60)
    print("Phase 4: DaVinci Resolve 调色")
    print("=" * 60)

    if not should_continue():
        return
    check_memory_safe(4.0)

    # === 自动启动 DaVinci Resolve ===
    # 关键: 设置 RESOLVE_SCRIPT_LIB 环境变量指向正确的 DLL
    resolve_dll = r"D:\DaVinci Resolve\fusionscript.dll"
    if os.path.exists(resolve_dll):
        os.environ["RESOLVE_SCRIPT_LIB"] = resolve_dll
        log(f"设置 RESOLVE_SCRIPT_LIB={resolve_dll}")
    else:
        log(f"Resolve DLL 未找到: {resolve_dll}", "WARN")

    log(">>> 自动启动 DaVinci Resolve...")
    dv_launched = launch_app("DaVinci Resolve", RESOLVE_EXE, wait_seconds=90)

    if not dv_launched:
        log("DaVinci Resolve 启动失败，调色降级为模拟模式", "WARN")

    # === 等待 Resolve API 就绪 ===
    # Resolve 进程启动后需要 60-120秒 初始化 Fusion 引擎
    # 策略: 先等窗口出现，再尝试 API 连接
    log("等待 DaVinci Resolve UI 就绪...")

    # 第一步: 等待 Resolve 主窗口出现
    import ctypes
    user32 = ctypes.windll.user32
    ui_ready = False
    for i in range(30):  # 最多等 30秒
        time.sleep(2)
        hwnd = user32.FindWindowW(None, "DaVinci Resolve")
        if hwnd:
            ui_ready = True
            log(f"Resolve 窗口已出现 (耗时{(i+1)*2}s)")
            break
        # 也检查英文标题
        hwnd2 = user32.FindWindowW(None, "DaVinci Resolve")
        if hwnd2:
            ui_ready = True
            log(f"Resolve 窗口已出现 (耗时{(i+1)*2}s)")
            break
    if not ui_ready:
        log("未检测到 Resolve 窗口，继续尝试 API...", "WARN")

    # 第二步: 等待 Fusion 引擎 API 就绪 (最多 120秒)
    log("等待 Fusion 引擎 API 初始化(最多120s)...")
    resolve_api_ready = False
    for attempt in range(24):  # 24×5s = 120秒
        time.sleep(5)
        try:
            running = is_process_running("Resolve.exe")
            if not running:
                log(f"Resolve 进程未检测到 (attempt {attempt+1}/24)")
                continue
            # 清除缓存的失败导入
            for mod_name in list(sys.modules.keys()):
                if 'DaVinciResolveScript' in mod_name or 'fusionscript' in mod_name:
                    del sys.modules[mod_name]
            # 确保 Resolve scripting 路径在 sys.path
            resolve_script_path = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
            if resolve_script_path not in sys.path and os.path.exists(resolve_script_path):
                sys.path.insert(0, resolve_script_path)
            try:
                import DaVinciResolveScript
                resolve_app = DaVinciResolveScript.scriptapp("Resolve")
                if resolve_app is not None:
                    pm = resolve_app.GetProjectManager()
                    resolve_api_ready = True
                    log(f"DaVinci API 已就绪! (第{attempt+1}次检测, 总耗时约{(attempt+1)*5}s)")
                    break
                else:
                    if (attempt+1) % 4 == 0:
                        log(f"Resolve instance 为 None (attempt {attempt+1}/24)")
            except Exception as api_e:
                if (attempt+1) % 4 == 0:
                    log(f"API 加载尝试 {attempt+1}/24: {str(api_e)[:60]}")
        except Exception as e:
            log(f"检测异常 {attempt+1}/24: {str(e)[:60]}")

    if not resolve_api_ready:
        log("DaVinci API 未就绪，调色将使用模拟模式", "WARN")

    # === 执行调色 ===
    try:
        # 重新创建 colorist(确保检测到最新状态)
        from davinci_resolve_integration import DavinciColorist
        colorist = DavinciColorist()

        if resolve_api_ready:
            log("DaVinci Resolve API 已连接, 执行真实调色...")
        else:
            log("DaVinci API 不可用, 使用模拟调色", "WARN")

        output_path = os.path.join(OUTPUT_DIR, "v17_davinci_graded.mp4")
        try:
            result = colorist.color_grade(
                input_path=V17_VIDEO,
                output_path=output_path,
            )
            if hasattr(result, 'success'):
                log(f"调色结果: success={result.success}, mode={result.mode}")
                if hasattr(result, 'output_path') and result.output_path:
                    log(f"输出路径: {result.output_path}")
                if hasattr(result, 'error') and result.error:
                    log(f"错误信息: {result.error}", "WARN")
            elif hasattr(result, 'status'):
                log(f"调色结果: status={result.status}")
            else:
                log(f"调色结果: {str(result)[:150]}")
        except Exception as e:
            log(f"调色执行异常: {e}", "WARN")

    except Exception as e:
        log(f"DaVinci 阶段异常: {e}", "ERROR")

    # === DaVinci 任务完成，关闭释放内存 ===
    log(">>> DaVinci 任务完成，关闭 Resolve 释放内存...")
    close_app("DaVinci Resolve")

    check_memory_safe(2.0)
    log("Phase 4 完成")


# ================================================================
# Phase 5: 开源工具链处理
# ================================================================
def phase5_opensource_processing():
    print("\n" + "=" * 60)
    print("Phase 5: 开源工具链处理")
    print("=" * 60)

    if not should_continue():
        return
    check_memory_safe(3.0)

    # 5.1 MoviePy 视频处理
    log("MoviePy: 加载 V17 视频...")
    try:
        try:
            from moviepy import VideoFileClip
        except ImportError:
            from moviepy.editor import VideoFileClip

        clip = VideoFileClip(V17_VIDEO)
        log(f"MoviePy: V17 加载成功 {clip.duration:.1f}s {clip.size}")

        # 截取精华片段 (前8秒)
        log("MoviePy: 截取精华片段(0-8s)...")
        highlight = clip.subclipped(0, min(8, clip.duration))
        out_highlight = os.path.join(OUTPUT_DIR, "v17_highlight.mp4")
        highlight.write_videofile(out_highlight, codec="libx264", audio=False,
                                  logger=None, fps=clip.fps)
        log(f"MoviePy: 精华片段 {os.path.getsize(out_highlight)/1024:.0f}KB")
        highlight.close()

        # 2倍速版本
        log("MoviePy: 生成2倍速版本...")
        fast = clip.with_speed_scaled(2.0)
        out_fast = os.path.join(OUTPUT_DIR, "v17_2x_speed.mp4")
        fast.write_videofile(out_fast, codec="libx264", audio=False,
                             logger=None, fps=clip.fps)
        log(f"MoviePy: 2倍速 {os.path.getsize(out_fast)/1024:.0f}KB")
        fast.close()

        # 720p 缩放版本
        log("MoviePy: 生成720p版本...")
        scale = 720 / clip.h
        w720 = int(clip.w * scale)
        resized = clip.resized((w720, 720))
        out_720 = os.path.join(OUTPUT_DIR, "v17_720p.mp4")
        resized.write_videofile(out_720, codec="libx264", audio=False,
                                logger=None, fps=clip.fps)
        log(f"MoviePy: 720p {os.path.getsize(out_720)/1024:.0f}KB ({w720}x720)")
        resized.close()

        # 提取关键帧
        log("MoviePy: 提取关键帧...")
        import cv2
        frame_times = [0, clip.duration * 0.25, clip.duration * 0.5,
                       clip.duration * 0.75, clip.duration - 0.1]
        for i, t in enumerate(frame_times):
            frame = clip.get_frame(t)
            frame_path = os.path.join(OUTPUT_DIR, f"v17_keyframe_{i:02d}.png")
            cv2.imwrite(frame_path, frame)
        log(f"MoviePy: {len(frame_times)} 个关键帧已提取")

        clip.close()

    except Exception as e:
        log(f"MoviePy 处理异常: {e}", "ERROR")
        traceback.print_exc()

    check_memory_safe(2.0)

    # 5.2 OpenCV 场景分析
    log("OpenCV: 场景切换检测...")
    try:
        import cv2
        import numpy as np
        cap = cv2.VideoCapture(V17_VIDEO)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        scenes = []
        prev_hist = None
        step = max(1, total // 200)
        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.normalize(cv2.calcHist([gray], [0], None, [64], [0, 256]),
                                 None).flatten()
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > 0.3:
                    scenes.append({"frame": i, "time": round(i/fps, 1), "diff": round(diff, 3)})
            prev_hist = hist
        cap.release()
        log(f"OpenCV: 检测到 {len(scenes)} 个场景切换点")
    except Exception as e:
        log(f"OpenCV 异常: {e}", "ERROR")

    check_memory_safe(2.0)

    # 5.3 RIFE/SAM2/Remotion 状态报告
    try:
        from opensource_integrations import OpenSourceHub
        hub = OpenSourceHub()
        status = hub.auto_detect()
        for tool, ok in status.items():
            log(f"  {tool}: {'READY' if ok else 'N/A'}")
    except Exception as e:
        log(f"OpenSourceHub: {e}", "WARN")

    check_memory_safe(2.0)
    log("Phase 5 完成")


# ================================================================
# Phase 6: 最终合成
# ================================================================
def phase6_final_compose():
    print("\n" + "=" * 60)
    print("Phase 6: 最终合成 + 输出")
    print("=" * 60)

    if not should_continue():
        return
    check_memory_safe(3.0)

    # 用 FFmpeg 生成 GIF 预览
    log("FFmpeg: 生成 GIF 预览...")
    gif_out = os.path.join(OUTPUT_DIR, "v17_final_preview.gif")
    r = subprocess.run(
        f'ffmpeg -y -i "{V17_VIDEO}" -t 3 -vf "scale=320:-1" -r 10 "{gif_out}"',
        shell=True, capture_output=True, text=True, timeout=30
    )
    if os.path.exists(gif_out):
        log(f"GIF 预览: {os.path.getsize(gif_out)/1024:.0f}KB")
    else:
        log("GIF 生成失败(非致命)", "WARN")

    # 生成缩略图序列
    log("FFmpeg: 生成缩略图序列...")
    thumb_dir = os.path.join(OUTPUT_DIR, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    subprocess.run(
        f'ffmpeg -y -i "{V17_VIDEO}" -vf "fps=1,scale=160:-1" "{thumb_dir}/thumb_%03d.jpg"',
        shell=True, capture_output=True, text=True, timeout=30
    )
    thumbs = [f for f in os.listdir(thumb_dir) if f.endswith(".jpg")] if os.path.exists(thumb_dir) else []
    log(f"缩略图: {len(thumbs)} 张")

    check_memory_safe(2.0)
    log("Phase 6 完成")


# ================================================================
# Phase 7: 诊断报告
# ================================================================
def phase7_report():
    print("\n" + "=" * 60)
    print("Phase 7: 生成诊断报告")
    print("=" * 60)

    mem = get_memory()
    log(f"最终内存: 可用={mem['avail_gb']}GB, 负载={mem['load_pct']}%")

    # 统计输出文件
    output_files = []
    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            fp = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(fp):
                output_files.append({
                    "name": f,
                    "size_kb": round(os.path.getsize(fp) / 1024, 1),
                })
    log(f"输出文件: {len(output_files)} 个")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target": V17_VIDEO,
        "memory_final": mem,
        "output_files": output_files,
        "log": LOG,
    }

    # 清理非序列化对象
    def clean(obj):
        if isinstance(obj, dict):
            return {str(k): clean(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [clean(i) for i in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif hasattr(obj, 'item'):
            return obj.item()
        return str(obj)[:200]

    report_file = os.path.join(OUTPUT_DIR, "production_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(clean(report), f, ensure_ascii=False, indent=2)
    log(f"报告已保存: {report_file}")

    # 文本日志
    log_file = os.path.join(OUTPUT_DIR, "production_log.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"V17 自动化生产流水线日志\n")
        f.write(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"目标: {V17_VIDEO}\n")
        f.write(f"{'='*60}\n\n")
        for entry in LOG:
            f.write(f"  {entry}\n")
        f.write(f"\n{'='*60}\n")
        f.write(f"输出文件: {len(output_files)} 个\n")
        for of in output_files:
            f.write(f"  {of['name']} ({of['size_kb']}KB)\n")
    log(f"日志已保存: {log_file}")

    print("\n" + "=" * 60)
    print("  生产流水线执行完毕")
    print(f"  输出: {len(output_files)} 个文件")
    print(f"  内存: {mem['avail_gb']}GB 可用")
    print("=" * 60)


# ================================================================
# 主入口
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  V17 自动化生产流水线")
    print("  自主执行 + 内存监控 + 智能判断")
    print("=" * 60)

    start = time.time()

    if phase1_env_check():
        # Phase 2: 自动启动AE → 执行特效 → 自动关闭AE
        phase2_ae_effects()
        # Phase 3: 字幕动画(复用AE连接，AE已在Phase2启动)
        # 注意: Phase2已关闭AE，Phase3如需AE需重新启动
        phase3_subtitle_animation()
        # Phase 4: 自动启动DaVinci → 调色 → 自动关闭DaVinci
        phase4_davinci_color()
        # Phase 5-6: 开源工具+合成(不需要AE/DaVinci)
        phase5_opensource_processing()
        phase6_final_compose()
    else:
        log("环境检查失败, 中止执行", "ERROR")

    # 确保所有启动的软件都已关闭
    close_all_apps()
    phase7_report()

    elapsed = time.time() - start
    print(f"\n  总耗时: {elapsed:.1f}s")
