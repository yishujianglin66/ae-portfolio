"""测试伪装高帧 v2 - 真实补帧 + 视觉增强."""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.fake_hfr_service import FakeHighFrameRateService


async def main():
    print("=" * 60)
    print("伪装高帧 v2 - 真实补帧 + 视觉增强")
    print("=" * 60)

    service = FakeHighFrameRateService()

    # 视频素材库
    video_library = Path(r"D:\AE-Work\视频素材库")
    output_dir = video_library / "processed_hfr_v2"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 找到所有视频
    video_files = []
    for ext in [".mp4", ".avi", ".mov", ".mkv"]:
        video_files.extend(video_library.glob(f"*{ext}"))

    print(f"\n视频素材库: {video_library}")
    print(f"找到 {len(video_files)} 个视频:")
    for i, f in enumerate(video_files, 1):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {i}. {f.name} ({size_mb:.1f} MB)")

    # 先用第一个视频测试 60fps
    test_video = video_files[0]
    print(f"\n测试视频: {test_video.name}")
    print(f"目标: 4K + 60fps真实补帧 + smart模式增强")

    output_60 = output_dir / f"{test_video.stem}_4K_60fps_smart.mp4"
    print(f"\n[1] 60fps 真实补帧 + smart增强...")
    result = await service.apply_fake_hfr(
        test_video,
        output_60,
        target_fps=60,
        mode="smart",
        blur_strength=0.3,
        blend_alpha=0.3,
        sharpen_amount=1.5,
        upscale_4k=True,
        preserve_audio=True,
    )
    if result["success"]:
        size_mb = output_60.stat().st_size / (1024 * 1024)
        print(f"  ✓ 成功! ({size_mb:.1f} MB)")
        print(f"    输出: {output_60.name}")
    else:
        print(f"  ✗ 失败: {result.get('error', '未知')[:200]}")

    # 测试 120fps
    output_120 = output_dir / f"{test_video.stem}_4K_120fps_smart.mp4"
    print(f"\n[2] 120fps 真实补帧 + smart增强...")
    result = await service.apply_fake_hfr(
        test_video,
        output_120,
        target_fps=120,
        mode="smart",
        blur_strength=0.3,
        blend_alpha=0.3,
        sharpen_amount=1.5,
        upscale_4k=True,
        preserve_audio=True,
    )
    if result["success"]:
        size_mb = output_120.stat().st_size / (1024 * 1024)
        print(f"  ✓ 成功! ({size_mb:.1f} MB)")
        print(f"    输出: {output_120.name}")
    else:
        print(f"  ✗ 失败: {result.get('error', '未知')[:200]}")

    # 测试 full 模式 (60fps)
    output_full = output_dir / f"{test_video.stem}_4K_60fps_full.mp4"
    print(f"\n[3] 60fps 真实补帧 + full模式 (含调色)...")
    result = await service.apply_fake_hfr(
        test_video,
        output_full,
        target_fps=60,
        mode="full",
        blur_strength=0.3,
        blend_alpha=0.3,
        sharpen_amount=1.5,
        upscale_4k=True,
        preserve_audio=True,
    )
    if result["success"]:
        size_mb = output_full.stat().st_size / (1024 * 1024)
        print(f"  ✓ 成功! ({size_mb:.1f} MB)")
        print(f"    输出: {output_full.name}")
    else:
        print(f"  ✗ 失败: {result.get('error', '未知')[:200]}")

    # 汇总
    print("\n" + "=" * 60)
    print("输出文件:")
    print(f"目录: {output_dir}\n")
    for f in sorted(output_dir.glob("*.mp4")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
