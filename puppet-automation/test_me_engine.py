"""测试 Media Encoder 引擎."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.engines.media_encoder import PLATFORM_PRESETS, MediaEncoderEngine


def test_init():
    """Test 1: Engine init."""
    print("=== Test 1: Engine Init ===")
    engine = MediaEncoderEngine()
    print(f"  name: {engine.name}")
    print(f"  exe: {engine.executable_path}")
    print(f"  exists: {engine.executable_path.exists()}")
    print(f"  watch_folder: {engine.watch_folder_path}")
    assert engine.executable_path.exists(), "ME executable not found!"
    print("  PASS")


def test_presets():
    """Test 2: Platform presets."""
    print("\n=== Test 2: Platform Presets ===")
    for k, v in PLATFORM_PRESETS.items():
        w, h = v["resolution"]
        res = f"{w}x{h}"
        print(f"  {k}: {v['name']} - {res} {v['fps']}fps {v['bitrate']}")
    assert len(PLATFORM_PRESETS) >= 6
    print("  PASS")


async def test_async():
    """Test 3-4: Async methods."""
    engine = MediaEncoderEngine()

    print("\n=== Test 3: list_presets() ===")
    result = await engine.list_presets()
    assert result.success
    print(f"  platforms: {len(result.metadata['platforms'])}")
    for p, info in result.metadata["platforms"].items():
        print(f"    {p}: {info['name']} {info['resolution']} {info['fps']}fps")
    print("  PASS")

    print("\n=== Test 4: get_preset('douyin') ===")
    result = await engine.get_preset("douyin")
    assert result.success
    w, h = result.metadata["resolution"]
    print(f"  name: {result.metadata['name']}")
    print(f"  resolution: {w}x{h}")
    print(f"  fps: {result.metadata['fps']}")
    print(f"  bitrate: {result.metadata['bitrate']}")
    print("  PASS")

    print("\n=== Test 5: get_preset('master') ===")
    result = await engine.get_preset("master")
    assert result.success
    w, h = result.metadata["resolution"]
    print(f"  name: {result.metadata['name']}")
    print(f"  resolution: {w}x{h}")
    print(f"  bitrate: {result.metadata['bitrate']}")
    print("  PASS")

    print("\n=== Test 6: get_preset('invalid') ===")
    result = await engine.get_preset("invalid_platform")
    assert not result.success
    print(f"  correctly rejected: {result.error}")
    print("  PASS")


def main():
    test_init()
    test_presets()
    asyncio.run(test_async())
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
