"""P1 VRS CV-only 路径验证"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vrs.vrs_real_analyzer import VRSRealAnalyzer


def main():
    # 找测试视频
    data_dir = Path(__file__).resolve().parent.parent / "data" / "real_amv_test"
    vids = [f for f in sorted(data_dir.glob("*.mp4")) if f.stat().st_size > 50000]
    if not vids:
        print("[SKIP] No test videos found")
        return False

    video = str(vids[0])
    print(f"[1] Testing VRSRealAnalyzer on: {Path(video).name} ({Path(video).stat().st_size//1024}KB)")

    analyzer = VRSRealAnalyzer(num_frames=12)
    result = asyncio.run(analyzer.analyze(video))

    print("\n[2] Results:")
    print(f"    success: {result.get('success')}")
    print(f"    source: {result.get('source')}")
    print(f"    confidence: {result.get('confidence')}")

    cp = result.get("color_palette", {})
    print(f"    color_palette.temperature: {cp.get('temperature')}")
    print(f"    color_palette.saturation: {cp.get('saturation')}")
    print(f"    color_palette.contrast: {cp.get('contrast')}")

    rhythm = result.get("rhythm", {})
    print(f"    rhythm.tempo: {rhythm.get('tempo')}")
    print(f"    rhythm.shot_count: {rhythm.get('shot_count')}")

    motion = result.get("motion", {})
    print(f"    motion.intensity: {motion.get('intensity')}")

    transitions = result.get("transitions", [])
    print(f"    transitions: {len(transitions)} detected")
    if transitions:
        print(f"      first: {transitions[0]}")

    effects = result.get("effects", [])
    print(f"    effects: {len(effects)} detected")
    for e in effects[:3]:
        print(f"      - {e.get('effect_name')} ({e.get('category')}, intensity={e.get('intensity')})")

    print(f"    style_tags: {result.get('style_tags', [])}")
    print(f"    color_grade: {result.get('color_grade')}")
    print(f"    errors: {result.get('errors', [])}")

    # 验证
    checks = []
    checks.append(("success == True", result.get("success") is True))
    checks.append(("source == real_opencv_analysis", result.get("source") == "real_opencv_analysis"))
    checks.append(("color_palette has data", bool(cp.get("temperature"))))
    checks.append(("rhythm has data", bool(rhythm.get("tempo"))))
    checks.append(("motion has data", motion.get("intensity", 0) > 0))
    checks.append(("confidence > 0", (result.get("confidence") or 0) > 0))
    checks.append(("no critical errors", len(result.get("errors", [])) == 0))

    print("\n[3] Verification:")
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"    [{status}] {desc}")

    print(f"\n{'='*60}")
    print(f"[RESULT] VRS CV-only: {'PASS' if all_pass else 'FAIL'}")
    print(f"{'='*60}")
    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
