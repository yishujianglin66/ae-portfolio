"""Test script for Fake High Frame Rate service."""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.fake_hfr_service import FakeHighFrameRateService


async def main():
    print("=" * 60)
    print("测试伪装高帧服务")
    print("=" * 60)

    service = FakeHighFrameRateService()

    # Test platform settings
    print("\n各平台推荐配置:")
    platforms = ["douyin", "bilibili", "youtube", "tiktok"]
    for platform in platforms:
        settings = service.get_optimal_settings(platform=platform)
        print(f"  {platform}: fps={settings['target_fps']}, mode={settings['mode']}, "
              f"blur={settings['blur_strength']}, alpha={settings['blend_alpha']}")

    # Test content type adjustments
    print("\n内容类型调整:")
    content_types = ["general", "action", "animation", "sports"]
    for content in content_types:
        settings = service.get_optimal_settings(platform="douyin", content_type=content)
        print(f"  {content}: blur={settings['blur_strength']}, alpha={settings['blend_alpha']}")

    # Process video from library
    input_video = Path(r"D:\AE-Work\视频素材库\冰海战记.mp4")
    if not input_video.exists():
        input_video = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\me_test\rendered\clip_0_rendered.mp4")

    print(f"\n测试视频: {input_video.name}")

    output_dir = Path(r"D:\AE-Work\视频素材库\processed_fake_hfr")
    output_dir.mkdir(parents=True, exist_ok=True)

    modes = ["smart", "blur", "blend", "full"]
    for mode in modes:
        output_path = output_dir / f"{input_video.stem}_fake_hfr_{mode}.mp4"
        print(f"\n处理模式: {mode}")

        result = await service.apply_fake_hfr(
            input_video,
            output_path,
            target_fps=30,
            mode=mode,
            upscale_4k=True,
            preserve_audio=True,
        )

        if result["success"]:
            print(f"  ✓ 成功: {output_path.name}")
        else:
            print(f"  ✗ 失败: {result.get('error', '未知错误')[:100]}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print(f"输出目录: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())