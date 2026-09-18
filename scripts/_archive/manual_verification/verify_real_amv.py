#!/usr/bin/env python3
"""真实漫剪视频端到端测试"""
import asyncio
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.style_pipeline import analyze_video_style
from core.style_preset_adapter import style_to_atomic_params


async def test_real_video(video_path: str):
    print("=" * 70)
    print(f" 真实漫剪视频测试: {video_path}")
    print("=" * 70)
    
    # 检查文件
    vp = Path(video_path)
    if not vp.exists():
        print(f"✗ 视频不存在: {vp.absolute()}")
        return
    
    size_mb = vp.stat().st_size / 1024 / 1024
    print(f"  文件大小: {size_mb:.2f}MB")
    print()
    
    # Stage 1: 风格分析
    print("=" * 70)
    print("Stage 1: VRS视频分析 + 风格分类")
    print("=" * 70)
    
    start = time.time()
    style_result = await analyze_video_style(str(vp), enable_vision=False, detail_level="standard")
    elapsed = (time.time() - start) * 1000
    
    print(f"  风格标签: {style_result.get('style')}")
    print(f"  置信度:   {style_result.get('confidence', 0):.2%}")
    print(f"  特征维度: {len(style_result.get('features', []))}")
    print(f"  延迟:     {elapsed:.1f}ms")
    
    if style_result.get('error'):
        print(f"  ⚠ 错误: {style_result['error']}")
    
    # 打印概率分布
    probs = style_result.get('probabilities', {})
    if probs:
        print("\n  Top-5 风格概率:")
        sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
        for style, prob in sorted_probs:
            print(f"    {style:25s} {prob:6.2%}")
    
    # Stage 2: 参数映射
    print()
    print("=" * 70)
    print("Stage 2: 风格 → 原子参数映射")
    print("=" * 70)
    
    start = time.time()
    atomic_params = style_to_atomic_params(
        style_result.get('style', 'cinematic'),
        style_result.get('confidence', 0.5),
    )
    elapsed = (time.time() - start) * 1000
    
    print(f"  效果数量: {len(atomic_params.get('effects', []))}")
    print(f"  调整项:   {list(atomic_params.get('adjustments', {}).keys())}")
    print(f"  映射延迟: {elapsed:.1f}ms")
    
    for i, effect in enumerate(atomic_params.get('effects', []), 1):
        print(f"\n  效果 {i}: {effect.get('displayName')}")
        print(f"    match_name: {effect.get('name')}")
        print(f"    category:   {effect.get('category')}")
        params = effect.get('params', {})
        if params:
            print(f"    参数数量:   {len(params)}")
            for k, v in list(params.items())[:5]:
                print(f"      - {k}: {v}")
    
    # Stage 3: JSX 脚本生成
    print()
    print("=" * 70)
    print("Stage 3: 风格 → ExtendScript JSX 脚本生成")
    print("=" * 70)
    
    try:
        from core.jsx_generator import style_result_to_jsx
        
        start = time.time()
        jsx_path = style_result_to_jsx(
            style_result=style_result,
            atomic_params=atomic_params,
            output_dir="output/real_video_test/jsx",
            video_path=str(vp.absolute()),
        )
        elapsed = (time.time() - start) * 1000
        
        jsx_file = Path(jsx_path)
        print(f"  JSX 文件: {jsx_file.name}")
        print(f"  大小:     {jsx_file.stat().st_size} 字节")
        print(f"  路径:     {jsx_path}")
        print(f"  生成延迟: {elapsed:.1f}ms")
    except Exception as e:
        print(f"  ⚠ JSX 生成失败: {e}")
        jsx_path = None
    
    # 保存结果
    output_dir = Path("output/real_video_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = output_dir / f"{vp.stem}_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "video_path": str(vp.absolute()),
            "video_size_mb": size_mb,
            "style_result": {
                "style": style_result.get('style'),
                "confidence": style_result.get('confidence'),
                "features": style_result.get('features'),
                "probabilities": style_result.get('probabilities', {}),
            },
            "atomic_params": atomic_params,
            "jsx_path": jsx_path,
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n  结果已保存: {result_file}")
    print("=" * 70)
    print(" ✓ 真实视频测试完成（视频分析+风格分类+参数映射+JSX生成）")

if __name__ == "__main__":
    video = sys.argv[1] if len(sys.argv) > 1 else "output_director/style_renders/render_cyberpunk.mp4"
    asyncio.run(test_real_video(video))