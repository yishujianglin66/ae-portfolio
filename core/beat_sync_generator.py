#!/usr/bin/env python3
"""音乐卡点视频生成器 - 使用素材库音乐和视频自动生成卡点视频"""

import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

OUTPUT_DIR = Path(r"D:\AE-Work\输出")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_PATH = r"D:\AE-Work\音频素材库\BGM\test_tone.wav"
VIDEO_CLIPS = [
    r"D:\AE-Work\视频素材库\57f0d1ea7bae24137c1308187ebf34c4.mp4",
    r"D:\AE-Work\视频素材库\抖音_一拳超人_埼玉.mp4"
]

def analyze_audio(audio_path):
    """音频分析：BPM检测、节拍提取、情绪分析"""
    print("=" * 60)
    print("[Step 1] 音频分析")
    print("=" * 60)
    
    try:
        import librosa
        import numpy as np
        
        print(f"  加载音频: {audio_path}")
        y, sr = librosa.load(audio_path, sr=None, duration=60)
        
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)
        
        rms = librosa.feature.rms(y=y)
        energy_mean = float(np.mean(rms))
        
        mood = "neutral"
        if energy_mean > 0.15:
            mood = "energetic"
        elif energy_mean < 0.05:
            mood = "calm"
        
        key = int(np.argmax(chroma_mean))
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        detected_key = key_names[key]
        
        tempo_val = float(tempo)
        beat_times_list = beat_times.tolist()
        
        print(f"  BPM: {tempo_val:.1f}")
        print(f"  节拍数: {len(beat_times_list)}")
        print(f"  音乐长度: {len(y)/sr:.1f}s")
        print(f"  能量: {energy_mean:.4f}")
        print(f"  情绪: {mood}")
        print(f"  调性: {detected_key}")
        print(f"  前10个节拍时间: {[round(t, 2) for t in beat_times_list[:10]]}")
        
        return {
            "success": True,
            "tempo": float(tempo),
            "beat_times": beat_times.tolist(),
            "duration": float(len(y)/sr),
            "energy": float(energy_mean),
            "mood": mood,
            "key": detected_key,
            "sr": sr
        }
    except Exception as e:
        print(f"  音频分析失败: {e}")
        return {"success": False, "error": str(e)}


def select_clips(analysis_result, video_clips):
    """根据音乐情绪选择视频片段"""
    print("\n" + "=" * 60)
    print("[Step 2] 素材选择")
    print("=" * 60)
    
    mood = analysis_result.get("mood", "neutral")
    print(f"  音乐情绪: {mood}")
    
    selected = []
    for clip in video_clips:
        if Path(clip).exists():
            size = Path(clip).stat().st_size
            print(f"  ✅ 选中: {Path(clip).name} ({size/1024/1024:.1f}MB)")
            selected.append(clip)
        else:
            print(f"  ❌ 不存在: {clip}")
    
    return {"success": True, "selected_clips": selected}


def plan_timeline(analysis_result, clips):
    """时间轴规划：根据节拍创建卡点场景"""
    print("\n" + "=" * 60)
    print("[Step 3] 时间轴规划")
    print("=" * 60)
    
    beat_times = analysis_result["beat_times"]
    tempo = analysis_result["tempo"]
    duration = analysis_result["duration"]
    
    scenes = []
    beat_interval = 60.0 / tempo
    
    clip_index = 0
    scene_id = 1
    
    for i, beat_time in enumerate(beat_times):
        if i % 4 == 0:
            scene_start = beat_time
            scene_end = min(beat_time + beat_interval * 4, duration)
            
            if scene_end - scene_start > 0.1:
                scene = {
                    "id": scene_id,
                    "start_time": scene_start,
                    "end_time": scene_end,
                    "duration": scene_end - scene_start,
                    "beat_count": 4,
                    "clip_path": clips[clip_index % len(clips)],
                    "clip_name": Path(clips[clip_index % len(clips)]).name,
                    "effects": []
                }
                
                if scene_id % 3 == 0:
                    scene["effects"].append("zoom_in")
                if scene_id % 4 == 0:
                    scene["effects"].append("crossfade")
                
                scenes.append(scene)
                scene_id += 1
                clip_index += 1
    
    print(f"  总节拍数: {len(beat_times)}")
    print(f"  生成场景数: {len(scenes)}")
    print(f"  场景详情:")
    for scene in scenes[:5]:
        print(f"    Scene {scene['id']}: {scene['start_time']:.2f}s - {scene['end_time']:.2f}s ({scene['duration']:.2f}s) - {scene['clip_name']}")
    
    return {"success": True, "scenes": scenes, "tempo": tempo, "duration": duration}


def create_ae_composition(timeline_plan):
    """AE合成创建：导入素材并设置关键帧"""
    print("\n" + "=" * 60)
    print("[Step 4] AE合成创建")
    print("=" * 60)
    
    try:
        from ae_mcp_client import AECommandClient
        
        client = AECommandClient(timeout=30)
        duration = timeline_plan["duration"]
        scenes = timeline_plan["scenes"]
        
        result = client.send_command("createComposition", {
            "name": "Beat_Sync_Video",
            "width": 1920,
            "height": 1080,
            "duration": duration + 2.0,
            "frameRate": 30.0
        })
        
        if result.get("status") != "success":
            print(f"  ❌ 创建合成失败: {result.get('message')}")
            return {"success": False, "error": result.get("message")}
        
        print(f"  ✅ 合成创建成功: {result['composition']['name']}")
        
        jsx_script = f"""
            var comp = app.project.items.itemByName("Beat_Sync_Video");
            if (comp) {{
                comp.openInViewer();
                
                var layers = [];
                var scenes = {json.dumps(scenes, indent=2)};
                
                for (var i = 0; i < scenes.length; i++) {{
                    var scene = scenes[i];
                    var file = new File(scene.clip_path);
                    
                    if (file.exists) {{
                        var importOptions = new ImportOptions(file);
                        var footage = app.project.importFile(importOptions);
                        
                        var layer = comp.layers.add(footage);
                        layer.startTime = scene.start_time;
                        layer.outPoint = scene.end_time;
                        layer.name = "Scene_" + scene.id;
                        
                        if (scene.effects && scene.effects.indexOf("zoom_in") >= 0) {{
                            var scaleProp = layer.property("Scale");
                            scaleProp.setValueAtTime(scene.start_time, [100, 100]);
                            scaleProp.setValueAtTime(scene.end_time, [110, 110]);
                        }}
                        
                        if (i > 0) {{
                            var prevLayer = comp.layers[i];
                            prevLayer.outPoint = scene.start_time;
                        }}
                        
                        layers.push({{id: scene.id, name: layer.name, startTime: layer.startTime}});
                    }}
                }}
                
                JSON.stringify({{status: "success", layersCreated: layers.length, scenes: scenes.length}});
            }} else {{
                JSON.stringify({{status: "error", message: "Composition not found"}});
            }}
        """
        
        result_file = OUTPUT_DIR / "ae_beat_sync_script.jsx"
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(jsx_script)
        
        print(f"  ✅ JSX脚本已生成: {result_file}")
        print(f"  ✅ 计划导入 {len(scenes)} 个场景")
        
        return {
            "success": True,
            "composition_name": "Beat_Sync_Video",
            "scenes_count": len(scenes),
            "duration": duration,
            "script_path": str(result_file),
            "scenes": scenes
        }
    except Exception as e:
        print(f"  ❌ AE操作失败: {e}")
        return {"success": False, "error": str(e)}


def export_video(composition_result):
    """视频导出：渲染并保存最终视频"""
    print("\n" + "=" * 60)
    print("[Step 5] 视频导出")
    print("=" * 60)
    
    try:
        output_path = OUTPUT_DIR / f"beat_sync_video_{int(time.time())}.mp4"
        
        jsx_export = f"""
            var comp = app.project.items.itemByName("Beat_Sync_Video");
            if (comp) {{
                var renderQueue = app.project.renderQueue.items.add(comp);
                
                var outputModule = renderQueue.item(1).outputModule(1);
                outputModule.applyTemplate("H.264");
                
                var outputFile = new File("{output_path}");
                renderQueue.item(1).outputModule(1).file = outputFile;
                
                renderQueue.render();
                
                JSON.stringify({{status: "success", outputPath: "{output_path}", rendering: true}});
            }} else {{
                JSON.stringify({{status: "error", message: "Composition not found"}});
            }}
        """
        
        export_script = OUTPUT_DIR / "ae_export_script.jsx"
        with open(export_script, "w", encoding="utf-8") as f:
            f.write(jsx_export)
        
        print(f"  ✅ 导出脚本已生成: {export_script}")
        print(f"  ✅ 输出路径: {output_path}")
        print(f"  ℹ️  请在AE中运行导出脚本完成渲染")
        
        return {
            "success": True,
            "output_path": str(output_path),
            "export_script": str(export_script),
            "composition": composition_result.get("composition_name")
        }
    except Exception as e:
        print(f"  ❌ 导出失败: {e}")
        return {"success": False, "error": str(e)}


def generate_report(results):
    """生成完整报告"""
    print("\n" + "=" * 60)
    print("[最终报告] 音乐卡点视频生成")
    print("=" * 60)
    
    report = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "steps": results,
        "summary": {}
    }
    
    passed = sum(1 for r in results.values() if r.get("success"))
    total = len(results)
    
    report["summary"] = {
        "total_steps": total,
        "passed": passed,
        "overall": "PASS" if passed == total else "PARTIAL"
    }
    
    print("\n步骤结果:")
    for name, result in results.items():
        status = "✅" if result.get("success") else "❌"
        print(f"  {status} {name}: {'成功' if result.get('success') else '失败'}")
        if "error" in result and result["error"]:
            print(f"     错误: {result['error']}")
    
    if results.get("timeline_plan"):
        scenes = results["timeline_plan"]["scenes"]
        print(f"\n时间轴详情:")
        print(f"  BPM: {results['timeline_plan']['tempo']:.1f}")
        print(f"  音乐长度: {results['timeline_plan']['duration']:.1f}s")
        print(f"  场景数: {len(scenes)}")
        for scene in scenes[:5]:
            print(f"    Scene {scene['id']}: {scene['start_time']:.2f}s - {scene['end_time']:.2f}s")
    
    output_path = OUTPUT_DIR / "beat_sync_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n报告已保存: {output_path}")
    
    return report


if __name__ == "__main__":
    results = {}
    
    results["audio_analysis"] = analyze_audio(AUDIO_PATH)
    if not results["audio_analysis"]["success"]:
        print("音频分析失败，终止流程")
        sys.exit(1)
    
    results["clip_selection"] = select_clips(results["audio_analysis"], VIDEO_CLIPS)
    
    results["timeline_plan"] = plan_timeline(results["audio_analysis"], results["clip_selection"]["selected_clips"])
    
    results["ae_composition"] = create_ae_composition(results["timeline_plan"])
    
    results["video_export"] = export_video(results["ae_composition"])
    
    generate_report(results)