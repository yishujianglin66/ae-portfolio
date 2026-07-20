#!/usr/bin/env python3
"""
《冰海战记》V8 执行脚本
- 字幕动画系统重构:Text Animators + Range Selector 4种风格
- 横转竖修复:主层完整显示+上下模糊背景填充
- 后台渲染:使用 aerender.exe 避免 AE 阻塞冻结
"""

import os
import sys
import json
import time
import subprocess
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ae_mcp_client import AECommandClient

AERENDER = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"
OUTPUT = r"D:\AE-Work\output\VinlandSaga_Battle_V8.mp4"
AUDIO = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"
COMP_NAME = "VinlandSaga_Battle_V8"


def analyze_audio(audio_path):
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
        rms = librosa.feature.rms(y=y)[0]
        rms_times = librosa.frames_to_time(range(len(rms)), sr=sr)
        rms_norm = rms / (np.max(rms) + 1e-8)
        S = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        low_mask = (freqs >= 20) & (freqs < 200)
        mid_mask = (freqs >= 500) & (freqs < 2000)
        high_mask = (freqs >= 4000) & (freqs < 12000)
        low_energy = np.mean(S[low_mask, :], axis=0) if np.any(low_mask) else np.zeros(S.shape[1])
        mid_energy = np.mean(S[mid_mask, :], axis=0) if np.any(mid_mask) else np.zeros(S.shape[1])
        high_energy = np.mean(S[high_mask, :], axis=0) if np.any(high_mask) else np.zeros(S.shape[1])
        low_energy = low_energy / (np.max(low_energy) + 1e-8)
        mid_energy = mid_energy / (np.max(mid_energy) + 1e-8)
        high_energy = high_energy / (np.max(high_energy) + 1e-8)
        fps = 30
        frame_times = np.arange(0, duration, 1.0 / fps)
        global_env = np.interp(frame_times, rms_times, rms_norm)
        low_env = np.interp(frame_times, librosa.frames_to_time(range(len(low_energy)), sr=sr), low_energy)
        mid_env = np.interp(frame_times, librosa.frames_to_time(range(len(mid_energy)), sr=sr), mid_energy)
        high_env = np.interp(frame_times, librosa.frames_to_time(range(len(high_energy)), sr=sr), high_energy)
        return {
            "duration": duration, "bpm": tempo,
            "frame_times": [round(float(t), 4) for t in frame_times],
            "global_energy": [round(float(v), 4) for v in global_env],
            "low_energy": [round(float(v), 4) for v in low_env],
            "mid_energy": [round(float(v), 4) for v in mid_env],
            "high_energy": [round(float(v), 4) for v in high_env],
        }
    except Exception as e:
        print(f"音频分析失败: {e}")
        return None


def execute_ae_script(script_path):
    client = AECommandClient(signature_enabled=False, timeout=180)
    with open(script_path, "r", encoding="utf-8") as f:
        script = f.read()
    print(f"执行AE脚本: {script_path}")
    result = client.send_command("executeAtomScript", {"script": script})
    print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


def write_energy_chunked(comp_name, analysis):
    client = AECommandClient(signature_enabled=False, timeout=180)
    sliders = {
        "Global Energy": analysis["global_energy"],
        "LowFreq Energy": analysis["low_energy"],
        "MidFreq Energy": analysis["mid_energy"],
        "HighFreq Energy": analysis["high_energy"],
    }
    times = analysis["frame_times"]
    chunk_size = 100
    total = 0
    for name, data in sliders.items():
        print(f"  写入: {name} ({len(data)}帧)")
        for cs in range(0, len(data), chunk_size):
            ce = min(cs + chunk_size, len(data))
            cd = data[cs:ce]
            ct = times[cs:ce]
            dj = json.dumps(cd, ensure_ascii=False)
            tj = json.dumps(ct, ensure_ascii=False)
            script = (
                'var comp=null;'
                'for(var i=1;i<=app.project.numItems;i++){'
                'if(app.project.item(i).name==="' + comp_name + '"&&app.project.item(i) instanceof CompItem){'
                'comp=app.project.item(i);break;}}'
                'if(!comp){return "NF";}'
                'var ctrl=comp.layer("Audio Controller");'
                'if(!ctrl){return "NF";}'
                'var eff=null;'
                'for(var e=1;e<=ctrl.property("Effects").numProperties;e++){'
                'if(ctrl.property("Effects").property(e).name==="' + name + '"){eff=ctrl.property("Effects").property(e);break;}}'
                'if(!eff){eff=ctrl.property("Effects").addProperty("Slider Control");eff.name="' + name + '";}'
                'var sp=eff.property("Slider");'
                'var d=' + dj + ';var t=' + tj + ';'
                'for(var i=0;i<d.length;i++){sp.setValueAtTime(t[i],d[i]*100);}'
                'return "OK";'
            )
            client.send_command("executeAtomScript", {"script": script})
            total += len(cd)
            time.sleep(0.3)
    print(f"  总计: {total} 关键帧")


def save_project():
    """保存AE项目,aerender需要.aep文件"""
    client = AECommandClient(signature_enabled=False, timeout=60)
    aep_path = r"D:\AE-Work\VinlandSaga_V8.aep"
    script = (
        'var f=new File("' + aep_path.replace("\\", "/") + '");'
        'app.project.save(f);'
        'return JSON.stringify({path:"' + aep_path + '"});'
    )
    print(f"保存项目: {aep_path}")
    result = client.send_command("executeAtomScript", {"script": script})
    print(f"保存结果: {result}")
    return aep_path


def render_with_aerender(aep_path, comp_name, output_path):
    """使用aerender.exe命令行后台渲染,不阻塞AE GUI"""
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 如果输出文件已存在,先删除
    if os.path.exists(output_path):
        os.remove(output_path)

    cmd = [
        AERENDER,
        "-project", aep_path,
        "-comp", comp_name,
        "-output", output_path,
        "-OMtemplate", "H.264",
        "-continueOnMissingFootage",
    ]
    print(f"启动aerender后台渲染...")
    print(f"命令: {' '.join(cmd)}")
    print(f"输出: {output_path}")

    # 启动aerender(非阻塞,后台运行)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )
    return proc


def monitor_render(proc, output_path, timeout=900):
    """监控渲染进度"""
    start = time.time()
    last_size = 0
    last_update = start

    while True:
        if proc.poll() is not None:
            # 进程结束
            print(f"\n渲染进程结束,退出码: {proc.returncode}")
            break

        elapsed = time.time() - start
        if elapsed > timeout:
            print(f"\n超时({timeout}s),终止渲染")
            proc.terminate()
            break

        # 检查输出文件大小
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            if size != last_size:
                last_size = size
                last_update = time.time()
                print(f"\r[{elapsed:.0f}s] 输出: {size/1024/1024:.2f} MB", end="", flush=True)
            else:
                # 文件大小未变化
                if time.time() - last_update > 60:
                    print(f"\n[警告] 输出文件60s未变化,可能渲染卡住")
                    # 但aerender进程可能仍在编码,继续等待
        else:
            print(f"\r[{elapsed:.0f}s] 渲染中...", end="", flush=True)

        time.sleep(5)

    # 读取剩余输出
    try:
        out, _ = proc.communicate(timeout=10)
        if out:
            print(f"\naerender输出(尾部):\n{out[-2000:]}")
    except:
        pass


def main():
    print("=" * 60)
    print("《冰海战记》V8 - 字幕动画系统重构")
    print("Text Animators + Range Selector 4种风格")
    print("横转竖修复 + aerender后台渲染")
    print("=" * 60)

    # Step 1: 音频分析
    print("\n[1/5] 音频分析...")
    analysis = analyze_audio(AUDIO)
    if not analysis:
        print("音频分析失败")
        return
    print(f"  时长: {analysis['duration']:.2f}s | BPM: {analysis['bpm']:.1f}")

    # Step 2: 创建V8合成
    print("\n[2/5] 创建V8合成...")
    result = execute_ae_script("scripts/vinland_saga_v8.jsx")
    try:
        inner = json.loads(result.get("result", {}).get("result", "{}"))
        if inner.get("error"):
            print(f"失败: {inner['error']}")
            return
        print(f"  成功: {inner.get('layers', '?')}层, {inner.get('clips', '?')}素材")
    except:
        print(f"  结果: {result}")

    # Step 3: 写入能量滑块
    print("\n[3/5] 写入能量滑块...")
    write_energy_chunked(COMP_NAME, analysis)

    # Step 4: 保存项目
    print("\n[4/5] 保存AE项目...")
    aep_path = save_project()
    time.sleep(3)

    # Step 5: aerender后台渲染
    print("\n[5/5] 启动aerender后台渲染...")
    proc = render_with_aerender(aep_path, COMP_NAME, OUTPUT)
    monitor_render(proc, OUTPUT, timeout=1200)

    # 验证输出
    print("\n" + "=" * 60)
    if os.path.exists(OUTPUT):
        size = os.path.getsize(OUTPUT)
        print(f"V8渲染完成!")
        print(f"文件大小: {size/1024/1024:.2f} MB")
        print(f"输出: {OUTPUT}")
    else:
        print("渲染可能未完成,检查aerender输出")
    print("=" * 60)


if __name__ == "__main__":
    main()
