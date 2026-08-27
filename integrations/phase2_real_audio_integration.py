#!/usr/bin/env python3
"""
Phase 2: 真实音频分析 → 节拍关键帧映射 → AE Bridge 写入
======================================================
将 beat_keyframe_mapper.py 与 AE Bridge 打通，实现真正的音画同步。
"""

import os
import sys
import json
import math

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ae_mcp_client import AECommandClient
from beat_keyframe_mapper import BeatKeyframeMapper, parse_beats_from_features


def analyze_real_audio(audio_path: str) -> dict:
    """
    使用 audio_analyzer_enhanced.py 分析真实音频
    返回包含 beats, downbeats, bpm, energy_curve 的字典
    """
    try:
        from audio_analyzer_enhanced import AudioAnalyzerEnhanced
        analyzer = AudioAnalyzerEnhanced()
        features = analyzer.analyze(audio_path)
        print(f"[音频分析] 完成: {audio_path}")
        print(f"  - BPM: {features.get('bpm', 'N/A')}")
        print(f"  - 时长: {features.get('duration', 'N/A')}s")
        print(f"  - 节拍数: {len(features.get('beats', []))}")
        print(f"  - 强拍数: {len(features.get('downbeats', []))}")
        return features
    except Exception as e:
        print(f"[音频分析] 失败: {e}")
        # 回退到 librosa 快速分析
        return _fallback_analyze(audio_path)


def _fallback_analyze(audio_path: str) -> dict:
    """使用 librosa 进行快速节拍检测"""
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=None)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        # 能量曲线
        rms = librosa.feature.rms(y=y)[0]
        rms_times = librosa.frames_to_time(range(len(rms)), sr=sr).tolist()

        # 检测强拍（onset强度峰值）
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_times = librosa.times_like(onset_env, sr=sr)

        # 简单强拍检测：每个小节第一拍
        beats_per_measure = 4
        downbeats = [beat_times[i] for i in range(0, len(beat_times), beats_per_measure)]

        duration = librosa.get_duration(y=y, sr=sr)

        return {
            "bpm": float(tempo),
            "duration": duration,
            "beats": [round(t, 3) for t in beat_times],
            "downbeats": [round(t, 3) for t in downbeats],
            "energy_curve": {
                "times": [round(t, 3) for t in rms_times],
                "values": [round(float(v), 4) for v in rms],
            },
            "features": {
                "beats": [round(t, 3) for t in beat_times],
                "downbeats": [round(t, 3) for t in downbeats],
                "bpm": float(tempo),
                "energy_curve": {
                    "times": [round(t, 3) for t in rms_times],
                    "values": [round(float(v), 4) for v in rms],
                },
                "duration": duration,
            }
        }
    except Exception as e:
        print(f"[回退分析] 也失败了: {e}")
        return {}


def generate_keyframes_from_beats(beats_data: dict, style: str = "default") -> list:
    """
    使用 BeatKeyframeMapper 将节拍映射为 AE 关键帧
    """
    mapper = BeatKeyframeMapper(precision_ms=10.0)

    # 解析节拍
    beats = parse_beats_from_features(beats_data)
    print(f"[映射引擎] 解析到 {len(beats)} 个节拍")

    # 定义目标事件（关键帧位置）
    # 策略: 每个节拍生成 Scale + Opacity + Rotation 三个关键帧
    target_events = []
    duration = beats_data.get("duration", 10.0)

    for beat in beats:
        bt = beat.time
        energy = beat.strength
        is_down = beat.is_downbeat

        # Scale: 强拍放大，弱拍微动
        scale_pulse = 100 + (15 if is_down else 5) * energy
        target_events.append({
            "time": bt,
            "property": "Scale",
            "value": [round(scale_pulse, 1), round(scale_pulse, 1)],
            "ease": "easeInOut" if is_down else "linear",
            "intensity": energy,
        })

        # Opacity: 能量越高越明显
        opacity = 70 + energy * 30
        target_events.append({
            "time": bt,
            "property": "Opacity",
            "value": round(opacity, 1),
            "ease": "easeOut" if is_down else "linear",
            "intensity": energy,
        })

        # Rotation: 持续累积 + 节拍摆动
        rot_base = (bt / duration) * 30
        target_events.append({
            "time": bt,
            "property": "Rotation",
            "value": round(rot_base, 1),
            "ease": "linear",
            "intensity": energy,
        })

    # 生成时间线
    result = mapper.generate_beat_synced_timeline(
        beats=beats,
        total_duration=duration,
        clip_events=target_events,
        style=style,
    )

    stats = result["statistics"]
    print(f"[时间线生成] 风格: {style}")
    print(f"  - 匹配事件: {stats['matched_events']}/{stats['total_events']}")
    print(f"  - 平均偏移: {stats['average_offset_ms']}ms")
    print(f"  - 最大偏移: {stats['max_offset_ms']}ms")
    print(f"  - 节拍覆盖: {stats['coverage']*100:.1f}%")

    # 将时间线事件转换为 AE 关键帧格式
    ae_keyframes = []
    for evt in result["timeline"]:
        prop = evt["type"]
        val = evt["value"]
        # 统一格式
        if prop == "Scale" and not isinstance(val, list):
            val = [val, val]
        ae_keyframes.append({
            "property": prop,
            "time": evt["time"],
            "value": val,
            "easeType": evt["ease"],
        })

    return ae_keyframes


def write_keyframes_to_ae(
    keyframes: list,
    comp_name: str = "E2E_VinlandSaga",
    layer_name: str = "MainVideo",
    add_expressions: bool = True,
) -> dict:
    """
    通过 AE Bridge 批量写入关键帧
    """
    client = AECommandClient(signature_enabled=False, timeout=30)

    # 构建 ExtendScript
    script_lines = [
        'var compName = "' + comp_name + '";',
        'var layerName = "' + layer_name + '";',
        'var comp = null;',
        'for (var i = 1; i <= app.project.numItems; i++) {',
        '    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {',
        '        comp = app.project.item(i); break;',
        '    }',
        '}',
        'if (!comp) { JSON.stringify({error: "Comp not found"}); }',
        'else {',
        '    var layer = null;',
        '    for (var j = 1; j <= comp.numLayers; j++) {',
        '        if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }',
        '    }',
        '    if (!layer) { JSON.stringify({error: "Layer not found"}); }',
        '    else {',
        '        var written = 0;',
        '        var kfs = ' + json.dumps(keyframes) + ';',
        '        for (var k = 0; k < kfs.length; k++) {',
        '            var kf = kfs[k];',
        '            var prop = layer.property(kf.property);',
        '            if (prop) {',
        '                prop.setValueAtTime(kf.time, kf.value);',
        '                if (kf.easeType !== "linear") {',
        '                    var idx = prop.nearestKeyIndex(kf.time);',
        '                    if (idx > 0) {',
        '                        var eIn = new KeyframeEase(0,33);',
        '                        var eOut = new KeyframeEase(0,33);',
        '                        if (kf.easeType === "easeIn") { eIn = new KeyframeEase(0,75); }',
        '                        else if (kf.easeType === "easeOut") { eOut = new KeyframeEase(0,75); }',
        '                        else if (kf.easeType === "easeInOut") { eIn = new KeyframeEase(0,75); eOut = new KeyframeEase(0,75); }',
        '                        try { prop.setTemporalEaseAtKey(idx,[eIn],[eOut]); } catch(ex) {}',
        '                    }',
        '                }',
        '                written++;',
        '            }',
        '        }',
        '        JSON.stringify({written: written, total: kfs.length});',
        '    }',
        '}',
    ]

    script = ''.join(script_lines)
    print(f"[AE Bridge] 写入 {len(keyframes)} 个关键帧...")
    result = client.send_command("executeAtomScript", {"script": script})
    print(f"[AE Bridge] 结果: {json.dumps(result, ensure_ascii=False)}")

    # 添加表达式
    if add_expressions:
        print("[AE Bridge] 添加表达式...")
        expr_script = (
            'var compName = "' + comp_name + '";'
            'var layerName = "' + layer_name + '";'
            'var comp = null;'
            'for (var i = 1; i <= app.project.numItems; i++) {'
            '    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {'
            '        comp = app.project.item(i); break;'
            '    }'
            '}'
            'if (comp) {'
            '    var layer = null;'
            '    for (var j = 1; j <= comp.numLayers; j++) {'
            '        if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }'
            '    }'
            '    if (layer) {'
            '        var opacityProp = layer.property("Opacity");'
            '        if (opacityProp) {'
            '            opacityProp.expression = '
            '                "t = time; " +'
            '                "beat = Math.sin(t * 2 * Math.PI * 2.133); " +'
            '                "80 + beat * 20;";'
            '        }'
            '        var rotProp = layer.property("Rotation");'
            '        if (rotProp) {'
            '            rotProp.expression = '
            '                "t = time; " +'
            '                "t * 3 + Math.sin(t * 2 * Math.PI * 2.133) * 5;";'
            '        }'
            '        JSON.stringify({expressions: "added"});'
            '    } else { JSON.stringify({error: "Layer not found"}); }'
            '} else { JSON.stringify({error: "Comp not found"}); }'
        )
        r2 = client.send_command("executeAtomScript", {"script": expr_script})
        print(f"[AE Bridge] 表达式结果: {json.dumps(r2, ensure_ascii=False)}")

    return result


def run_phase2_pipeline(
    audio_path: str = None,
    comp_name: str = "E2E_VinlandSaga",
    layer_name: str = "MainVideo",
    style: str = "default",
):
    """
    Phase 2 完整流水线:
    真实音频分析 -> 节拍映射 -> AE关键帧写入
    """
    print("=" * 60)
    print("Phase 2: 真实音频驱动关键帧流水线")
    print("=" * 60)

    # 1. 寻找可用音频
    if not audio_path or not os.path.exists(audio_path):
        candidates = [
            r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\audio_raw.wav",
            r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\audio_processed.wav",
            r"D:\AE-Work\音频素材库\BGM\抖音_BGM_世上无难事.mp3",
        ]
        for c in candidates:
            if os.path.exists(c):
                audio_path = c
                break

    if not audio_path or not os.path.exists(audio_path):
        print("[错误] 未找到可用音频文件，Phase 2 无法继续")
        print("[建议] 请提供音频文件路径或放置 audio_raw.wav 到项目根目录")
        return False

    print(f"\n[1/4] 音频分析: {audio_path}")
    features = analyze_real_audio(audio_path)
    if not features:
        return False

    print(f"\n[2/4] 节拍映射: 生成关键帧")
    keyframes = generate_keyframes_from_beats(features, style=style)
    if not keyframes:
        return False

    print(f"\n[3/4] AE Bridge: 写入 {len(keyframes)} 个关键帧")
    result = write_keyframes_to_ae(keyframes, comp_name, layer_name)

    print(f"\n[4/4] 完成!")
    print(f"  - 音频: {audio_path}")
    print(f"  - 关键帧: {len(keyframes)}")
    print(f"  - 合成: {comp_name} -> {layer_name}")

    # 保存映射结果
    report_path = ".ae-mcp-bridge/phase2_result.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "audio_path": audio_path,
            "keyframes_count": len(keyframes),
            "ae_result": result,
            "style": style,
        }, f, ensure_ascii=False, indent=2)
    print(f"  - 报告: {report_path}")

    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2: 真实音频驱动AE关键帧")
    parser.add_argument("--audio", help="音频文件路径")
    parser.add_argument("--comp", default="E2E_VinlandSaga", help="AE合成名称")
    parser.add_argument("--layer", default="MainVideo", help="AE图层名称")
    parser.add_argument("--style", default="default", help="映射风格 (default/on_beat/off_beat/double_time/half_time)")
    args = parser.parse_args()

    success = run_phase2_pipeline(
        audio_path=args.audio,
        comp_name=args.comp,
        layer_name=args.layer,
        style=args.style,
    )
    sys.exit(0 if success else 1)
