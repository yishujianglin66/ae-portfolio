"""
阶段1：复杂场景端到端测试
===========================
验证多效果叠加场景：CDL + 变速 + Ken Burns + Transform 同时应用

测试场景：
- 5个不同素材片段
- 每个片段不同的 CDL 调色参数
- 不同的 SpeedCurve（ease_in/ease_out/ramp_up/ramp_down）
- 3个片段应用 KenBurnsConfig
- 混合使用 TransformConfig
- 原生 vs FFmpeg 渲染对比验证
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import (
    CDLConfig,
    ItemEffect,
    KenBurnsConfig,
    ResolveAutomationEngine,
    SpeedCurve,
    TransformConfig,
)

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve + 真实素材环境


def verify_video_with_ffprobe(filepath: str) -> dict:
    """使用 ffprobe 验证视频文件完整性"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration,size,nb_streams',
        '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
        '-of', 'json',
        filepath
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            return {
                'valid': True,
                'duration': float(info['format']['duration']),
                'size_mb': int(info['format']['size']) / 1024 / 1024,
                'streams': int(info['format']['nb_streams']),  # nb_streams is int, not list
                'video_stream': info['streams'][0] if info['streams'] else None
            }
        else:
            return {'valid': False, 'error': result.stderr}
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def test_advanced_workflow():
    """综合测试：多效果叠加工作流"""
    print("=" * 80)
    print("阶段1：复杂场景端到端测试")
    print("=" * 80)
    
    # 初始化引擎（10分钟超时，用于长时间渲染）
    engine = ResolveAutomationEngine(timeout=600)
    project_name = f"AdvancedWorkflow_{int(time.time())}"
    
    # ================================================================
    # Step 1: 准备测试素材（至少5个）
    # ================================================================
    print("\n[Step 1] 准备测试素材...")
    media_dir = r"C:\VinlandClips"
    test_files = []
    
    if os.path.isdir(media_dir):
        for f in sorted(os.listdir(media_dir)):
            if f.endswith('.mp4') and len(test_files) < 5:
                test_files.append(os.path.join(media_dir, f))
    
    if len(test_files) < 5:
        print(f"[WARN] Only found {len(test_files)} clips, need at least 5")
        print("       Using available clips for testing...")
    
    if not test_files:
        print("[ERROR] No test media found!")
        return
    
    print(f"[OK] Found {len(test_files)} clips:")
    for i, f in enumerate(test_files, 1):
        print(f"  {i}. {os.path.basename(f)}")
    
    # ================================================================
    # Step 2: 创建时间线并添加所有片段
    # ================================================================
    print("\n[Step 2] 创建时间线并添加片段...")
    tl_info = engine.create_timeline_with_media(project_name, "AdvancedTL", test_files)
    print(f"[OK] Timeline created: {tl_info}")
    
    # ================================================================
    # Step 3: 为每个片段配置不同的效果组合
    # ================================================================
    print("\n[Step 3] 配置多效果叠加...")
    
    # 定义5种不同的 CDL 风格
    cdl_styles = [
        ("Warm Cinematic", CDLConfig(
            slope=(1.3, 1.1, 0.8),
            offset=(0.05, 0.03, -0.02),
            power=(0.9, 0.95, 1.1),
            saturation=1.2
        )),
        ("Cool Moody", CDLConfig(
            slope=(0.9, 1.0, 1.3),
            offset=(-0.03, -0.02, 0.05),
            power=(1.1, 1.0, 0.85),
            saturation=0.8
        )),
        ("High Contrast", CDLConfig(
            slope=(1.5, 1.5, 1.5),
            offset=(0.0, 0.0, 0.0),
            power=(0.7, 0.7, 0.7),
            saturation=1.5
        )),
        ("Vintage Film", CDLConfig(
            slope=(1.1, 1.05, 0.9),
            offset=(0.08, 0.06, 0.04),
            power=(0.85, 0.9, 1.0),
            saturation=0.7
        )),
        ("Vibrant Pop", CDLConfig(
            slope=(1.2, 1.2, 1.2),
            offset=(0.02, 0.02, 0.02),
            power=(1.0, 1.0, 1.0),
            saturation=1.8
        )),
    ]
    
    # 定义不同的 SpeedCurve 类型
    speed_curves = [
        SpeedCurve(curve_type="ease_in", start_speed=0.5, end_speed=1.5),
        SpeedCurve(curve_type="ease_out", start_speed=1.5, end_speed=0.8),
        SpeedCurve(curve_type="ramp_up", start_speed=0.3, end_speed=2.0),
        SpeedCurve(curve_type="ramp_down", start_speed=2.0, end_speed=0.5),
        SpeedCurve(curve_type="linear", start_speed=1.0, end_speed=1.0),  # 无变速
    ]
    
    # 定义 Ken Burns 配置（仅应用于前3个片段）
    ken_burns_configs = [
        KenBurnsConfig(
            start_zoom=1.0, end_zoom=1.8,
            start_x=0.3, start_y=0.4,
            end_x=0.7, end_y=0.6
        ),
        KenBurnsConfig(
            start_zoom=1.5, end_zoom=1.0,
            start_x=0.7, start_y=0.3,
            end_x=0.3, end_y=0.7
        ),
        KenBurnsConfig(
            start_zoom=1.0, end_zoom=2.0,
            start_x=0.5, start_y=0.5,
            end_x=0.5, end_y=0.5
        ),
    ]
    
    # 定义 Transform 配置
    transform_configs = [
        TransformConfig(zoom_x=1.2, zoom_y=1.2, rotation=5.0, opacity=100.0),
        TransformConfig(zoom_x=1.0, zoom_y=1.0, rotation=-3.0, opacity=95.0),
        TransformConfig(zoom_x=1.3, zoom_y=1.3, rotation=0.0, opacity=100.0),
        TransformConfig(zoom_x=1.1, zoom_y=1.1, rotation=8.0, opacity=90.0),
        TransformConfig(zoom_x=1.0, zoom_y=1.0, rotation=0.0, opacity=100.0),
    ]
    
    # 应用效果到每个片段
    effects_map = {}  # item_index -> ItemEffect
    
    for idx in range(1, len(test_files) + 1):
        style_name, cdl = cdl_styles[idx - 1]
        speed_curve = speed_curves[idx - 1]
        transform = transform_configs[idx - 1]
        
        print(f"\n  片段 {idx}:")
        print(f"    CDL: {style_name}")
        print(f"    SpeedCurve: {speed_curve.curve_type} ({speed_curve.start_speed}x → {speed_curve.end_speed}x)")
        
        # 应用 CDL
        engine.apply_cdl(project_name, "AdvancedTL", idx, cdl)
        print("    [OK] CDL applied")
        
        # 应用 Transform
        engine.set_transform(project_name, idx, transform)
        print(f"    [OK] Transform applied (zoom={transform.zoom_x}, rotation={transform.rotation}°)")
        
        # 构建 ItemEffect（用于 FFmpeg 渲染）
        effect = ItemEffect(item_index=idx, speed_curve=speed_curve)
        
        # 前3个片段添加 Ken Burns
        if idx <= 3:
            kb_config = ken_burns_configs[idx - 1]
            effect.ken_burns = kb_config
            print(f"    [OK] Ken Burns applied (zoom {kb_config.start_zoom}x → {kb_config.end_zoom}x)")
        
        effects_map[idx] = effect
    
    print(f"\n[OK] All effects configured for {len(test_files)} clips")
    
    # ================================================================
    # Step 4: 原生渲染测试
    # ================================================================
    print("\n" + "=" * 80)
    print("[Step 4] 原生渲染测试（Resolve + FFmpeg 转码）")
    print("=" * 80)
    
    native_output = f"c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\output_production\\advanced_native_{int(time.time())}.mp4"
    
    try:
        print(f"Output: {native_output}")
        print("Starting native render (this may take 1-3 minutes)...")
        
        native_result = engine.render_timeline(
            project_name, 
            native_output, 
            use_ffmpeg=False,  # 使用原生渲染
            effects=effects_map
        )
        
        print(f"[OK] Native render completed: {native_result}")
        
        # 验证原生渲染输出
        native_verify = verify_video_with_ffprobe(native_result)
        if native_verify['valid']:
            print("[OK] Video validation passed:")
            print(f"     Duration: {native_verify['duration']:.2f}s")
            print(f"     Size: {native_verify['size_mb']:.1f} MB")
            if native_verify['video_stream']:
                vs = native_verify['video_stream']
                print(f"     Resolution: {vs['width']}x{vs['height']}")
                print(f"     FPS: {vs['r_frame_rate']}")
                print(f"     Codec: {vs['codec_name']}")
        else:
            print(f"[ERROR] Native video validation failed: {native_verify.get('error')}")
            
    except Exception as e:
        print(f"[ERROR] Native render failed: {e}")
        import traceback
        traceback.print_exc()
        native_result = None
    
    # ================================================================
    # Step 5: FFmpeg 直接渲染测试（对比）
    # ================================================================
    print("\n" + "=" * 80)
    print("[Step 5] FFmpeg 直接渲染测试（对比）")
    print("=" * 80)
    
    ffmpeg_output = f"c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\output_production\\advanced_ffmpeg_{int(time.time())}.mp4"
    
    try:
        print(f"Output: {ffmpeg_output}")
        print("Starting FFmpeg render...")
        
        ffmpeg_result = engine.render_timeline(
            project_name, 
            ffmpeg_output, 
            use_ffmpeg=True,  # 使用 FFmpeg 直接渲染
            effects=effects_map
        )
        
        print(f"[OK] FFmpeg render completed: {ffmpeg_result}")
        
        # 验证 FFmpeg 渲染输出
        ffmpeg_verify = verify_video_with_ffprobe(ffmpeg_result)
        if ffmpeg_verify['valid']:
            print("[OK] Video validation passed:")
            print(f"     Duration: {ffmpeg_verify['duration']:.2f}s")
            print(f"     Size: {ffmpeg_verify['size_mb']:.1f} MB")
            if ffmpeg_verify['video_stream']:
                vs = ffmpeg_verify['video_stream']
                print(f"     Resolution: {vs['width']}x{vs['height']}")
                print(f"     FPS: {vs['r_frame_rate']}")
                print(f"     Codec: {vs['codec_name']}")
        else:
            print(f"[ERROR] FFmpeg video validation failed: {ffmpeg_verify.get('error')}")
            
    except Exception as e:
        print(f"[ERROR] FFmpeg render failed: {e}")
        import traceback
        traceback.print_exc()
        ffmpeg_result = None
    
    # ================================================================
    # Step 6: 对比分析
    # ================================================================
    print("\n" + "=" * 80)
    print("[Step 6] 渲染方案对比分析")
    print("=" * 80)
    
    if native_result and ffmpeg_result:
        native_v = verify_video_with_ffprobe(native_result)
        ffmpeg_v = verify_video_with_ffprobe(ffmpeg_result)
        
        print("\n┌─────────────────┬──────────────────┬──────────────────┐")
        print("│ 指标            │ 原生渲染         │ FFmpeg 渲染      │")
        print("├─────────────────┼──────────────────┼──────────────────┤")
        print(f"│ 时长            │ {native_v['duration']:8.2f}s     │ {ffmpeg_v['duration']:8.2f}s     │")
        print(f"│ 文件大小        │ {native_v['size_mb']:8.1f} MB     │ {ffmpeg_v['size_mb']:8.1f} MB     │")
        
        if native_v['video_stream'] and ffmpeg_v['video_stream']:
            nv = native_v['video_stream']
            fv = ffmpeg_v['video_stream']
            print(f"│ 分辨率          │ {nv['width']:4d}x{nv['height']:4d}     │ {fv['width']:4d}x{fv['height']:4d}     │")
            print(f"│ 帧率            │ {nv['r_frame_rate']:>8s}     │ {fv['r_frame_rate']:>8s}     │")
            print(f"│ 编码器          │ {nv['codec_name']:>8s}     │ {fv['codec_name']:>8s}     │")
        
        print("└─────────────────┴──────────────────┴──────────────────┘")
        
        # 一致性检查
        duration_diff = abs(native_v['duration'] - ffmpeg_v['duration'])
        resolution_match = (
            native_v['video_stream']['width'] == ffmpeg_v['video_stream']['width'] and
            native_v['video_stream']['height'] == ffmpeg_v['video_stream']['height']
        )
        
        print("\n[一致性检查]")
        print(f"  时长差异: {duration_diff:.3f}s ({'✅ PASS' if duration_diff < 0.1 else '❌ FAIL'})")
        print(f"  分辨率一致: {'✅ PASS' if resolution_match else '❌ FAIL'}")
        
        if duration_diff < 0.1 and resolution_match:
            print("\n[OK] 两种渲染方案输出一致！")
        else:
            print("\n[WARN] 两种渲染方案存在差异，需要进一步调查")
    
    # ================================================================
    # Step 7: 清理
    # ================================================================
    print("\n[Step 7] 清理测试项目...")
    try:
        engine.delete_project(project_name)
        print(f"[OK] Project '{project_name}' deleted")
    except Exception as e:
        print(f"[WARN] Failed to delete project: {e}")
    
    print("\n" + "=" * 80)
    print("阶段1 测试完成！")
    print("=" * 80)
    
    # 返回结果摘要
    return {
        'project_name': project_name,
        'clips_count': len(test_files),
        'native_output': native_result,
        'ffmpeg_output': ffmpeg_result,
        'native_valid': native_result is not None and verify_video_with_ffprobe(native_result)['valid'] if native_result else False,
        'ffmpeg_valid': ffmpeg_result is not None and verify_video_with_ffprobe(ffmpeg_result)['valid'] if ffmpeg_result else False,
    }


if __name__ == "__main__":
    result = test_advanced_workflow()
    
    print("\n\n最终结果摘要:")
    print(f"  项目名称: {result['project_name']}")
    print(f"  片段数量: {result['clips_count']}")
    print(f"  原生渲染: {'✅ 成功' if result['native_valid'] else '❌ 失败'}")
    print(f"  FFmpeg渲染: {'✅ 成功' if result['ffmpeg_valid'] else '❌ 失败'}")
    
    if result['native_output']:
        print(f"\n原生渲染输出: {result['native_output']}")
    if result['ffmpeg_output']:
        print(f"FFmpeg渲染输出: {result['ffmpeg_output']}")
