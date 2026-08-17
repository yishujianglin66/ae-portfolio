"""
t39_run_real_pipeline.py - 用真实素材跑一次完整导演管线
=========================================================
ProductionDirector: 感知 → 编排 → 执行 → 验证
"""
import os, sys, time, json
from pathlib import Path

PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT))

VIDEO_DIR = Path(r"D:\AE-Work\resources\video")
AUDIO_DIR = Path(r"D:\AE-Work\resources")
OUTPUT_DIR = Path(r"D:\output_director\pipeline_test")


def find_anime_videos(target_keywords, max_count=5):
    """找到匹配关键词的视频"""
    results = []
    for root, dirs, files in os.walk(VIDEO_DIR):
        for f in files:
            if not f.lower().endswith(('.mp4', '.mkv', '.mov')):
                continue
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            if sz < 5 * 1024 * 1024:
                continue
            # Check keywords in path
            path_lower = fp.lower()
            for kw in target_keywords:
                if kw.lower() in path_lower or kw.lower() in f.lower():
                    results.append((fp, sz))
                    break
            if len(results) >= max_count:
                break
        if len(results) >= max_count:
            break
    return results


def find_bgm():
    """找一个合适的BGM"""
    # 优先找高燃/动漫风格的
    candidates = []
    for f in AUDIO_DIR.rglob("*.mp3"):
        sz = f.stat().st_size
        if sz > 1 * 1024 * 1024 and sz < 20 * 1024 * 1024:  # 1-20MB
            name_lower = f.stem.lower()
            if any(kw in name_lower for kw in ["attack", "epic", "battle", "燃", "code", "trailer"]):
                candidates.append((str(f), sz))
    
    if not candidates:
        # Fallback: any 2-10MB mp3
        for f in AUDIO_DIR.rglob("*.mp3"):
            sz = f.stat().st_size
            if 2 * 1024 * 1024 < sz < 10 * 1024 * 1024:
                candidates.append((str(f), sz))
                if len(candidates) >= 5:
                    break
    
    if candidates:
        # Pick the largest one (usually better quality)
        candidates.sort(key=lambda x: -x[1])
        return candidates[0][0]
    return None


def main():
    print("=" * 60)
    print("  T39: 真实素材管线运行")
    print("=" * 60)
    
    # 1. 找素材
    print("\n[1/5] 查找动漫素材视频...")
    
    # Try multiple anime IPs
    anime_keywords = [
        ["猫猫", "mao"],
        ["蓝色监狱", "blue_lock", "nagi"],
        ["辉夜", "kaguya"],
        ["独自升级", "solo"],
        ["咒术", "jujutsu", "五条悟"],
        ["初音", "miku"],
        ["byakuya"],
    ]
    
    all_videos = []
    for kws in anime_keywords:
        found = find_anime_videos(kws, max_count=3)
        for v, sz in found:
            if v not in [x[0] for x in all_videos]:
                all_videos.append((v, sz))
    
    if not all_videos:
        # Fallback: just use any large videos
        print("  未找到匹配视频，使用通用视频...")
        for root, dirs, files in os.walk(VIDEO_DIR):
            for f in files:
                if f.lower().endswith(('.mp4', '.mkv', '.mov')):
                    fp = os.path.join(root, f)
                    sz = os.path.getsize(fp)
                    if sz > 30 * 1024 * 1024:
                        all_videos.append((fp, sz))
                        if len(all_videos) >= 5:
                            break
            if len(all_videos) >= 5:
                break
    
    # Sort by size, take top 5
    all_videos.sort(key=lambda x: -x[1])
    video_paths = [v for v, _ in all_videos[:5]]
    
    print(f"  找到 {len(video_paths)} 个视频:")
    for v in video_paths:
        sz = os.path.getsize(v) / 1024 / 1024
        print(f"    {sz:.0f}MB  {os.path.basename(v)}")
    
    # 2. 找BGM
    print("\n[2/5] 查找BGM...")
    bgm = find_bgm()
    if bgm:
        sz = os.path.getsize(bgm) / 1024 / 1024
        print(f"  BGM: {os.path.basename(bgm)} ({sz:.1f}MB)")
    else:
        print("  未找到BGM，将使用无音频模式")
    
    # 3. 运行导演系统
    print("\n[3/5] 启动 ProductionDirector...")
    
    from ai.production_director import ProductionDirector
    
    director = ProductionDirector()
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 简单歌词/字幕 (可选)
    lyrics = [
        (0.0, 3.0, "ANIME MIX", "gold"),
        (3.0, 6.0, "Multi-IP Demo", "white"),
    ]
    
    try:
        result = director.render(
            video_sources=video_paths,
            bgm_path=bgm or "",
            output_dir=str(OUTPUT_DIR),
            output_name="anime_mix_demo.mp4",
            lyrics=lyrics if bgm else None,
            target_ip="",  # 混合IP
            strict=False,
            allow_mixed=True,
            verify_content=False,  # 混合IP不验证
        )
        
        print(f"\n[4/5] 渲染结果:")
        if isinstance(result, str):
            if os.path.exists(result):
                sz = os.path.getsize(result) / 1024 / 1024
                print(f"  输出: {result}")
                print(f"  大小: {sz:.1f}MB")
            else:
                print(f"  路径: {result} (文件不存在)")
        else:
            print(f"  结果: {result}")
    
    except Exception as e:
        print(f"\n  渲染异常: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: 尝试 E2E Pipeline
        print("\n  尝试 E2E Pipeline 备选方案...")
        try:
            from ae.e2e_pipeline import E2EPipeline
            pipeline = E2EPipeline(
                enable_scene_detection=True,
                enable_beat_analysis=True,
                enable_subtitles=False,
                enable_creative_planning=True,
                output_format="json",
            )
            
            result = pipeline.run(
                media_paths=video_paths[:3],
                audio_path=bgm,
                creative_description="多IP动漫混剪，快节奏卡点",
                output_dir=str(OUTPUT_DIR),
            )
            
            print(f"\n  E2E Pipeline 结果:")
            print(f"  成功: {result.success if hasattr(result, 'success') else 'N/A'}")
            if hasattr(result, 'output_dir'):
                print(f"  输出目录: {result.output_dir}")
            if hasattr(result, '__dict__'):
                for k, v in result.__dict__.items():
                    if v and not k.startswith('_'):
                        print(f"  {k}: {str(v)[:100]}")
        
        except Exception as e2:
            print(f"  E2E Pipeline 也失败: {e2}")
            import traceback
            traceback.print_exc()
    
    # 5. 检查输出
    print(f"\n[5/5] 检查输出目录:")
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.iterdir()):
            if f.is_file():
                sz = f.stat().st_size / 1024 / 1024
                print(f"  {sz:.1f}MB  {f.name}")


if __name__ == "__main__":
    main()
