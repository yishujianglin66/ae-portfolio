#!/usr/bin/env python3
"""
分块写入能量滑块关键帧
"""

import sys
import json
import time

sys.path.insert(0, r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault')

from ae_mcp_client import AECommandClient


def write_energy_keyframes_chunked(comp_name, analysis):
    client = AECommandClient(signature_enabled=False, timeout=180)
    
    sliders = {
        "Global Energy": analysis["global_energy"],
        "LowFreq Energy": analysis["low_energy"],
        "MidFreq Energy": analysis["mid_energy"],
        "HighFreq Energy": analysis["high_energy"],
    }
    
    times = analysis["frame_times"]
    chunk_size = 100
    total_written = 0
    
    for slider_name, data in sliders.items():
        print(f"写入滑块: {slider_name} ({len(data)}帧)")
        
        for chunk_start in range(0, len(data), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(data))
            chunk_data = data[chunk_start:chunk_end]
            chunk_times = times[chunk_start:chunk_end]
            
            data_json = json.dumps(chunk_data, ensure_ascii=False)
            times_json = json.dumps(chunk_times, ensure_ascii=False)
            
            script = (
                'var comp = app.project.itemByName("' + comp_name + '");'
                'if (!comp) { return "Comp not found"; }'
                'var ctrl = comp.layer("Audio Controller");'
                'if (!ctrl) { return "Controller not found"; }'
                'var eff = null;'
                'for (var e = 1; e <= ctrl.property("Effects").numProperties; e++) {'
                '    if (ctrl.property("Effects").property(e).name === "' + slider_name + '") { eff = ctrl.property("Effects").property(e); break; }'
                '}'
                'if (!eff) { eff = ctrl.property("Effects").addProperty("Slider Control"); eff.name = "' + slider_name + '"; }'
                'var sProp = eff.property("Slider");'
                'var data = ' + data_json + ';'
                'var times = ' + times_json + ';'
                'for (var i = 0; i < data.length; i++) {'
                '    sProp.setValueAtTime(times[i], data[i] * 100);'
                '}'
                'return "Written " + data.length + " keyframes";'
            )
            
            result = client.send_command("executeAtomScript", {"script": script})
            print(f"  块[{chunk_start}-{chunk_end}]: {result.get('result', {}).get('result', 'unknown')}")
            total_written += len(chunk_data)
            time.sleep(1)
    
    print(f"总计写入: {total_written} 个关键帧")
    return total_written


def main():
    import librosa
    import numpy as np
    
    audio_path = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"
    comp_name = "VinlandSaga_Battle_V4"
    
    y, sr = librosa.load(audio_path, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)
    
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
    frame_times = np.arange(0, duration, 1.0/fps)
    
    global_env = np.interp(frame_times, rms_times, rms_norm)
    low_env = np.interp(frame_times, librosa.frames_to_time(range(len(low_energy)), sr=sr), low_energy)
    mid_env = np.interp(frame_times, librosa.frames_to_time(range(len(mid_energy)), sr=sr), mid_energy)
    high_env = np.interp(frame_times, librosa.frames_to_time(range(len(high_energy)), sr=sr), high_energy)
    
    analysis = {
        "frame_times": [round(float(t), 4) for t in frame_times],
        "global_energy": [round(float(v), 4) for v in global_env],
        "low_energy": [round(float(v), 4) for v in low_env],
        "mid_energy": [round(float(v), 4) for v in mid_env],
        "high_energy": [round(float(v), 4) for v in high_env],
    }
    
    write_energy_keyframes_chunked(comp_name, analysis)


if __name__ == "__main__":
    main()