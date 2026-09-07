import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.services.scene_detection import SceneDetectionService


async def main():
    svc = SceneDetectionService()
    result = await svc.detect_scenes(
        r"D:\AE-Work\output\TextFX_Showcase.mp4", threshold=20.0, min_scene_len=10
    )
    total = result["total_scenes"]
    print(f"Total scenes: {total}")
    for s in result["scenes"]:
        sid = s["id"]
        st = s["start_time"]
        et = s["end_time"]
        dur = s["duration"]
        print(f"  Scene {sid}: {st:.2f}s - {et:.2f}s (dur={dur:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
