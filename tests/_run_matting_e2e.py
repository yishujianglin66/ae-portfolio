import sys, os, asyncio, json, time
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\src")

from pathlib import Path
from engines.matting.engine import MattingEngine

TEST_IMG = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\tests\output\matting_e2e\portrait_test_input.jpg")
assert TEST_IMG.exists(), f"test input missing: {TEST_IMG}"

eng = MattingEngine()
eng._model_dir = Path(r"D:\AE-Work\models\matting")
eng._model_index = {
    "modnet": eng._model_dir / "modnet_xenova.onnx",
    "rmbg14": eng._model_dir / "rmbg14.onnx",
}
print("Models loaded:", list(eng._model_index.keys()))

async def main():
    results = {}
    base_out = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\tests\output\matting_e2e")
    for model_key in ["modnet", "rmbg14"]:
        out_dir = base_out / model_key
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = await eng.human_matting(
            input_path=TEST_IMG,
            output_dir=out_dir,
            model_name=model_key,
        )
        dt = time.time() - t0
        print(f"===== {model_key} (latency={dt:.2f}s) success={r.success} =====")
        print(json.dumps(r.metadata, indent=2, ensure_ascii=False, default=str))
        if not r.success:
            print("ERROR:", r.error)
            results[model_key] = {"error": r.error}
            continue
        meta = {k: (str(v) if isinstance(v, Path) else v) for k, v in r.metadata.items()}
        results[model_key] = {"latency_s": round(dt, 2), **meta}
    return results

res = asyncio.run(main())

try:
    import cv2, numpy as np
    print()
    print("===== Alpha 质量量化 =====")
    header = ["model", "contrast", "soft_pix", "fg>95%", "bg<5%", "sharpness", "lat_s"]
    print("{:8s}  {:>8s}  {:>8s}  {:>7s}  {:>7s}  {:>9s}  {:>7s}".format(*header))
    for model_key, data in res.items():
        if "alpha_dir" not in data:
            continue
        alpha_p = Path(data["alpha_dir"]) / (TEST_IMG.stem + ".png")
        if not alpha_p.exists():
            continue
        arr = np.fromfile(str(alpha_p), dtype=np.uint8)
        a = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        contrast = float(np.std(a))
        soft = float(np.mean((a > 0.05) & (a < 0.95)))
        fg = float(np.mean(a > 0.95))
        bg = float(np.mean(a < 0.05))
        gx = cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3)
        sharp = float(np.mean(np.sqrt(gx * gx + gy * gy)))
        lat = data.get("latency_s", 0)
        print(f"{model_key:8s}  {contrast:8.3f}  {soft:8.3f}  {fg:7.3f}  {bg:7.3f}  {sharp:9.4f}  {lat:7.2f}")
except Exception as e:
    import traceback
    print(f"Metrics failed: {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("All outputs under: tests\\output\\matting_e2e\\{modnet,rmbg14}\\")
