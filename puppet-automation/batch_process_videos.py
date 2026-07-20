"""Batch video processing script - 4K upscale + cinematic filters."""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.beat_video_service import BeatVideoService


async def process_video(
    service: BeatVideoService,
    input_path: Path,
    output_path: Path,
    style: str = "teal_orange",
) -> dict:
    """Process a single video with 4K upscale and cinematic filter."""
    try:
        info = await service._get_video_info(input_path)
        print(f"  Input: {info['width']}x{info['height']}, {info['duration']:.1f}s")
        
        result = await service.create_beat_video(
            input_video=input_path,
            output_path=output_path,
            mode="scene",
            cinematic_style=style,
            clip_duration=999,
            enable_zoom=False,
            upscale_4k=True,
        )
        
        if result["success"]:
            print(f"  ✓ Output: {output_path.name}")
        else:
            print(f"  ✗ Failed: {result.get('error', 'Unknown error')[:100]}")
        return result
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {"success": False, "error": str(e)}


async def main():
    print("=" * 60)
    print("批量视频处理 - 4K超分 + 电影滤镜")
    print("视频素材库: D:/AE-Work/视频素材库")
    print("=" * 60)
    
    # Video library path
    video_library = Path(r"D:/AE-Work/视频素材库")
    
    if not video_library.exists():
        print(f"错误: 视频素材库路径不存在: {video_library}")
        return
    
    # Find video files in library
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    video_files = []
    for ext in video_extensions:
        for f in video_library.glob(f"*{ext}"):
            video_files.append(f)
    
    print(f"\n找到 {len(video_files)} 个视频文件:")
    for i, f in enumerate(video_files, 1):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {i}. {f.name} ({size_mb:.2f} MB)")
    
    # Create output directory
    output_dir = video_library / "processed_4k"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process videos
    print(f"\n开始处理...")
    service = BeatVideoService()
    
    styles = ["teal_orange", "warm_cinematic", "cool_mood", "vintage_film", "noir"]
    
    results = []
    for i, video_path in enumerate(video_files, 1):
        print(f"\n[{i}/{len(video_files)}] {video_path.name}")
        
        # Use alternating styles
        style = styles[(i - 1) % len(styles)]
        output_name = f"{video_path.stem}_4k_{style}.mp4"
        output_path = output_dir / output_name
        
        result = await process_video(service, video_path, output_path, style=style)
        result["input"] = str(video_path)
        result["output"] = str(output_path)
        result["style"] = style
        results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r.get("success"))
    print(f"成功: {success_count}/{len(results)}")
    print(f"输出目录: {output_dir}")
    
    # List outputs
    print("\n输出文件:")
    for f in sorted(output_dir.glob("*.mp4")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    asyncio.run(main())