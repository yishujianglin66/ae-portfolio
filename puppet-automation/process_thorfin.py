"""处理托尔芬视频 - 真实补帧 + 伪高帧包装."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.services.fake_hfr_service import FakeHighFrameRateService


async def main():
    service = FakeHighFrameRateService()
    video = Path(r"D:\AE-Work\视频素材库\托尔芬.mp4")
    out_dir = Path(r"D:\AE-Work\视频素材库\processed_hfr_v2")
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        ("托尔芬_4K_60fps_smart.mp4", 60, "smart"),
        ("托尔芬_4K_120fps_smart.mp4", 120, "smart"),
        ("托尔芬_4K_60fps_full.mp4", 60, "full"),
    ]

    for name, fps, mode in tasks:
        print(f"\n[{tasks.index((name, fps, mode)) + 1}/3] {fps}fps {mode}...")
        result = await service.apply_fake_hfr(
            video, out_dir / name,
            target_fps=fps, mode=mode,
            upscale_4k=True, preserve_audio=True,
        )
        if result["success"]:
            size_mb = (out_dir / name).stat().st_size / (1024 * 1024)
            print(f"  Done! ({size_mb:.1f} MB)")
        else:
            err = result.get("error", "unknown")[:150]
            print(f"  Failed: {err}")

    print("\n输出文件:")
    for f in sorted(out_dir.glob("托尔芬_*.mp4")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
