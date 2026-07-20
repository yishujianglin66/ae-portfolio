"""快速测试 resource_index_service 是否正常工作。"""
import asyncio
import sys
from pathlib import Path

# 添加项目根路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "puppet-automation"))

async def main():
    from src.services.resource_index_service import resource_index_service

    print("=== Resource Index Service Test ===")
    print("Building index (first call triggers scan)...")
    await resource_index_service.refresh_index()

    summary = resource_index_service.get_index_summary()
    print(f"\nIndex Summary:")
    total = 0
    for cat, count in sorted(summary.items()):
        print(f"  {cat:12s}: {count:6d}")
        total += count
    print(f"  {'TOTAL':12s}: {total:6d}")

    # Test find_font (newly extracted MFTongXin should be there)
    test_cases = [
        ("fonts", "MFTongXin"),
        ("fonts", "华文中宋"),
        ("luts", "cinematic"),
        ("luts", ".cube"),
        ("effects", "particle"),
        ("davinci", "Motion Blur"),
        ("davinci", "MONO"),
        ("premiere", "mogrt"),
    ]
    print("\n=== Find Resource Tests ===")
    for cat, name in test_cases:
        path = await resource_index_service.find_resource(cat, name)
        status = "FOUND" if path else "MISS"
        path_str = str(path)[:80] + "..." if path and len(str(path)) > 80 else (str(path) if path else "-")
        print(f"  [{cat:10s}] '{name}': {status} -> {path_str}")

if __name__ == "__main__":
    asyncio.run(main())
