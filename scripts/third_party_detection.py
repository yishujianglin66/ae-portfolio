#!/usr/bin/env python3
"""
第三方软件检测脚本 - Phase 3

检测所有第三方集成软件的安装状态，验证自动降级机制。
"""

import json
import os
import subprocess
from datetime import datetime


def find_executable(name, paths):
    """在指定路径中查找可执行文件"""
    for path in paths:
        if os.path.exists(path):
            return path
        # 尝试常见变体
        for ext in ['.exe', '.bat', '.cmd']:
            if os.path.exists(path + ext):
                return path + ext
    return None

def detect_software():
    """检测所有第三方软件"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "software": []
    }

    # 1. Topaz Video AI
    topaz_paths = [
        "C:\\Program Files\\Topaz Labs LLC\\Topaz Video AI\\Topaz Video AI.exe",
        "C:\\Program Files (x86)\\Topaz Labs LLC\\Topaz Video AI\\Topaz Video AI.exe",
        os.path.expanduser("~\\AppData\\Local\\Topaz Labs LLC\\Topaz Video AI\\Topaz Video AI.exe"),
        "D:\\Program Files\\Topaz Labs LLC\\Topaz Video AI\\Topaz Video AI.exe",
        "D:\\Topaz Video AI\\Topaz Video AI.exe",
        "D:\\Topaz Labs\\Topaz Video AI\\Topaz Video AI.exe",
        "C:\\Topaz Video AI\\Topaz Video AI.exe",
        "C:\\Topaz Labs\\Topaz Video AI\\Topaz Video AI.exe",
        "D:\\topaz\\Topaz Video AI\\Topaz Video AI.exe",
        "C:\\topaz\\Topaz Video AI\\Topaz Video AI.exe",
        "D:\\top\\Topaz Video AI Pro\\Topaz Video AI BETA.exe",
        "D:\\top\\Topaz Video AI\\Topaz Video AI.exe",
        "C:\\top\\Topaz Video AI Pro\\Topaz Video AI BETA.exe"
    ]
    topaz_exe = find_executable("Topaz Video AI", topaz_paths)
    results["software"].append({
        "name": "Topaz Video AI",
        "available": topaz_exe is not None,
        "path": topaz_exe,
        "purpose": "视频超分、补帧、降噪"
    })

    # 2. DaVinci Resolve
    davinci_paths = [
        "D:\\DaVinci Resolve\\Resolve.exe",
        "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe",
        "C:\\Program Files\\DaVinci Resolve\\Resolve.exe"
    ]
    davinci_exe = find_executable("Resolve", davinci_paths)
    results["software"].append({
        "name": "DaVinci Resolve",
        "available": davinci_exe is not None,
        "path": davinci_exe,
        "purpose": "专业调色、色彩分级"
    })

    # 3. Blender
    blender_paths = [
        "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",
        "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
        "C:\\Program Files\\Blender\\blender.exe",
        "D:\\Program Files\\Blender Foundation\\Blender\\blender.exe",
        "D:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
        "D:\\Blender\\blender.exe",
        "D:\\Blender Foundation\\Blender\\blender.exe",
        "C:\\Blender\\blender.exe",
        "D:\\Blender\\Blender 5.1.0\\blender.exe",
        "D:\\Blender\\Blender 5.0\\blender.exe",
        "D:\\Blender\\Blender 4.2\\blender.exe"
    ]
    blender_exe = find_executable("blender", blender_paths)
    results["software"].append({
        "name": "Blender",
        "available": blender_exe is not None,
        "path": blender_exe,
        "purpose": "3D建模、渲染"
    })

    # 4. Adobe Photoshop
    photoshop_paths = [
        "C:\\Program Files\\Adobe\\Adobe Photoshop 2025\\Photoshop.exe",
        "C:\\Program Files\\Adobe\\Adobe Photoshop (Beta)\\Photoshop.exe",
        "C:\\Program Files\\Adobe\\Adobe Photoshop 2026\\Photoshop.exe",
        "D:\\ps\\Adobe Photoshop 2025\\Photoshop.exe",
        "D:\\Program Files\\Adobe\\Adobe Photoshop 2026\\Photoshop.exe",
        "D:\\Adobe\\Adobe Photoshop 2026\\Photoshop.exe"
    ]
    photoshop_exe = find_executable("Photoshop", photoshop_paths)
    results["software"].append({
        "name": "Adobe Photoshop",
        "available": photoshop_exe is not None,
        "path": photoshop_exe,
        "purpose": "图像处理、素材制作"
    })

    # 5. Adobe Premiere Pro
    premiere_paths = [
        "C:\\Program Files\\Adobe\\Adobe Premiere Pro 2025\\Adobe Premiere Pro.exe",
        "C:\\Program Files\\Adobe\\Adobe Premiere Pro 2026\\Adobe Premiere Pro.exe",
        "D:\\pr\\Adobe Premiere Pro 2025\\Adobe Premiere Pro.exe",
        "D:\\Program Files\\Adobe\\Adobe Premiere Pro 2026\\Adobe Premiere Pro.exe",
        "D:\\Adobe\\Adobe Premiere Pro 2026\\Adobe Premiere Pro.exe"
    ]
    premiere_exe = find_executable("Premiere Pro", premiere_paths)
    results["software"].append({
        "name": "Adobe Premiere Pro",
        "available": premiere_exe is not None,
        "path": premiere_exe,
        "purpose": "时间线剪辑"
    })

    # 6. FFmpeg
    ffmpeg_exe = None
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ffmpeg_exe = "System PATH"
    except:
        ffmpeg_paths = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            os.path.expanduser("~\\ffmpeg\\bin\\ffmpeg.exe")
        ]
        ffmpeg_exe = find_executable("ffmpeg", ffmpeg_paths)
    
    results["software"].append({
        "name": "FFmpeg",
        "available": ffmpeg_exe is not None,
        "path": ffmpeg_exe,
        "purpose": "素材转码、格式转换"
    })

    # 7. MediaPipe (Python package)
    mediapipe_available = False
    try:
        import mediapipe as mp
        mediapipe_available = True
    except ImportError:
        pass
    
    results["software"].append({
        "name": "MediaPipe",
        "available": mediapipe_available,
        "path": "Python Package" if mediapipe_available else None,
        "purpose": "人物检测、姿态估计、面部跟踪"
    })

    # 统计
    available_count = sum(1 for s in results["software"] if s["available"])
    total_count = len(results["software"])
    
    results["summary"] = {
        "total": total_count,
        "available": available_count,
        "not_available": total_count - available_count,
        "availability_rate": available_count / total_count * 100
    }

    return results

def test_integration_modules():
    """测试集成模块的自动降级机制"""
    results = {
        "modules": []
    }

    try:
        from ae_agent_pipeline import AEAgentPipeline
        pipeline = AEAgentPipeline()

        # TopazEnhancer
        try:
            te = pipeline.topaz_enhancer
            results["modules"].append({
                "name": "TopazEnhancer",
                "loaded": True,
                "available": te._available,
                "cli_path": str(te._cli_path) if te._cli_path else None
            })
        except Exception as e:
            results["modules"].append({
                "name": "TopazEnhancer",
                "loaded": False,
                "error": str(e)
            })

        # DavinciColorist
        try:
            dc = pipeline.resolve_colorist
            results["modules"].append({
                "name": "DavinciColorist",
                "loaded": True,
                "available": dc._available,
                "exe_path": str(dc._exe_path) if dc._exe_path else None
            })
        except Exception as e:
            results["modules"].append({
                "name": "DavinciColorist",
                "loaded": False,
                "error": str(e)
            })

        # Blender3DIntegrator
        try:
            bi = pipeline.blender_integrator
            results["modules"].append({
                "name": "Blender3DIntegrator",
                "loaded": True,
                "available": bi._available,
                "exe_path": str(bi._executable) if hasattr(bi, '_executable') else None
            })
        except Exception as e:
            results["modules"].append({
                "name": "Blender3DIntegrator",
                "loaded": False,
                "error": str(e)
            })

        # AIVideoGenerator
        try:
            av = pipeline.ai_video_generator
            results["modules"].append({
                "name": "AIVideoGenerator",
                "loaded": True,
                "runway_available": av._runway_available,
                "pika_available": av._pika_available
            })
        except Exception as e:
            results["modules"].append({
                "name": "AIVideoGenerator",
                "loaded": False,
                "error": str(e)
            })

        # MediaPipeIntegrator
        try:
            mp = pipeline.mediapipe_integrator
            results["modules"].append({
                "name": "MediaPipeIntegrator",
                "loaded": True,
                "mode": mp._mode
            })
        except Exception as e:
            results["modules"].append({
                "name": "MediaPipeIntegrator",
                "loaded": False,
                "error": str(e)
            })

        pipeline.close()

    except Exception as e:
        results["error"] = str(e)

    return results

def main():
    print("=" * 60)
    print("Phase 3: Third-Party Software Detection")
    print("=" * 60)
    print()

    # 检测软件
    print("[1/2] Detecting installed software...")
    software_results = detect_software()

    print("\nSoftware Status:")
    for sw in software_results["software"]:
        status = "✓" if sw["available"] else "✗"
        path_display = sw["path"] if sw["path"] else "Not found"
        print(f"  {status} {sw['name']}: {path_display}")

    summary = software_results["summary"]
    print(f"\nSummary: {summary['available']}/{summary['total']} software available ({summary['availability_rate']:.1f}%)")

    # 测试集成模块
    print("\n" + "=" * 60)
    print("[2/2] Testing integration modules...")
    module_results = test_integration_modules()

    print("\nIntegration Modules:")
    for mod in module_results.get("modules", []):
        status = "✓" if mod["loaded"] else "✗"
        available = mod.get("available", "")
        mode = mod.get("mode", "")
        exe_path = mod.get("exe_path", "") or mod.get("cli_path", "")
        runway = mod.get("runway_available", "")
        pika = mod.get("pika_available", "")
        
        details = []
        if available:
            details.append(f"available={available}")
        if mode:
            details.append(f"mode={mode}")
        if exe_path:
            details.append(f"path={exe_path[:50]}...")
        if runway:
            details.append(f"runway={runway}")
        if pika:
            details.append(f"pika={pika}")
        
        print(f"  {status} {mod['name']}: {', '.join(details)}")

    if "error" in module_results:
        print(f"  Error: {module_results['error']}")

    # 保存结果
    output_dir = "c:/Users/Administrator/Desktop/AE-Knowledge-Vault/05-测试套件/test_results"
    os.makedirs(output_dir, exist_ok=True)

    full_results = {
        "software_detection": software_results,
        "integration_modules": module_results,
        "timestamp": datetime.now().isoformat()
    }

    with open(os.path.join(output_dir, "phase3_third_party_result.json"), "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("Results saved to: phase3_third_party_result.json")
    print("=" * 60)

if __name__ == "__main__":
    main()