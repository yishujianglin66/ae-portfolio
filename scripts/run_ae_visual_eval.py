"""M2 视觉评估真机链路：强度变体 ×2 → AE 真机合成 → 拍点帧导出 → 评分对比

用法:
  py -3.12 scripts/run_ae_visual_eval.py [--duration 6] [--dry] [--frame-times 0.55,2.57]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, ".")
from core.composition_tree import build_fate_composite_template
from core.beatlock import BeatGrid, compose
from core.visual_eval_gateway import VisualEvalGateway

BRIDGE = ".ae-mcp-bridge"
CMD = f"{BRIDGE}/ae_command.json"
RES = f"{BRIDGE}/ae_result.json"
OUT = os.path.abspath(f"{BRIDGE}/_m2_eval_out.txt")

AUDIOMAP = r"tmp/audiomap_52a283d2.json"
FOOTAGE = (r"D:\AE-Work\batch_auto_frame\DL_FATE_r978_BV1qb411C79B_p1"
           r"\DL_FATE_r978_BV1qb411C79B_p1_transparent.mov")
FRAME_DIR = os.path.abspath("output/step2_locator/m2_frames")


def send_and_wait(jsx: str, report_path: str, timeout: int = 240) -> dict:
    """发送 executeAtomScript，等 JSX 写入的 JSON 报告文件"""
    report_path = os.path.abspath(report_path)
    # 若 JSX 是合成工程脚本（含 _result 返回），注入文件报告；否则要求 JSX 自带写报告
    if "  return JSON.stringify(_result);" in jsx:
        inject = (
            f"var _repF = new File('{report_path.replace(chr(92), chr(92)*2)}');\n"
            "_repF.encoding = 'UTF-8';\n"
            "if (_repF.open('w')) { _repF.write(JSON.stringify(_result)); _repF.close(); }\n"
            "  return JSON.stringify(_result);"
        )
        jsx = jsx.replace("  return JSON.stringify(_result);", inject, 1)
    cmd = {"command": "executeAtomScript", "args": {"script": jsx},
           "status": "pending", "timestamp": time.strftime("%Y%m%d%H%M%S")}
    for p in (CMD, RES):
        if os.path.exists(p):
            os.remove(p)
            time.sleep(0.2)
    if os.path.exists(report_path):
        os.remove(report_path)
    with open(CMD, "w", encoding="utf-8") as f:
        json.dump(cmd, f, ensure_ascii=False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                return json.loads(f.read())
    raise TimeoutError(f"{report_path} 超时")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=6.0)
    ap.add_argument("--frame-times", default="0.55,2.57",
                    help="拍点帧采样时刻（punch峰值, flash低谷），逗号分隔")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    times = [float(x) for x in args.frame_times.split(",") if x.strip()]

    with open(AUDIOMAP, encoding="utf-8") as f:
        grid = BeatGrid.from_audiomap(json.load(f))
    print(f"[BeatGrid] kick={len(grid.kick)} strong={len(grid.strong)} bpm={grid.bpm:.0f}")

    variants = []
    for tag, intensity in (("A", 0.8), ("B", 1.2)):
        tree = build_fate_composite_template(FOOTAGE, duration=args.duration)
        tree.comp_name = f"M2_Eval_{tag}"
        for layer in tree.layers:
            if layer.type == "text":
                layer.time_range[0] = 0.0
        merged, res = compose(tree, grid, fps=30, intensity=intensity)
        print(f"[{tag}] intensity={intensity} anchors={len(res.anchors)} "
              f"jsx={len(merged)} 字符")
        variants.append({"label": tag, "tree": tree, "jsx": merged,
                         "params": {"intensity": intensity}})

    if args.dry:
        print("[dry] 仅生成，不执行真机")
        return 0

    # 1) 真机执行两个变体
    for v in variants:
        rep = send_and_wait(v["jsx"], f"{BRIDGE}/_m2_{v['label']}.txt")
        print(f"[AE {v['label']}] {rep.get('status')} layers_actual={rep.get('layers_actual')}")

    # 2) 拍点帧导出（saveFrameToPng，AE 2023+ 原生）
    os.makedirs(FRAME_DIR, exist_ok=True)
    frame_paths = {}
    for v in variants:
        pngs = []
        for t in times:
            p = os.path.abspath(f"{FRAME_DIR}/M2_{v['label']}_t{t:.2f}.png").replace("\\", "\\\\")
            rep_path = os.path.abspath(
                f"{BRIDGE}/_m2_frame_{v['label']}_{str(t).replace('.', '_')}.txt")
            jsx = (
                "(function() {\n"
                "var comp = null;\n"
                "for (var i = 1; i <= app.project.numItems; i++) { "
                "var it = app.project.item(i); "
                f"if (it instanceof CompItem && it.name === '{v['tree'].comp_name}') "
                "{ comp = it; break; } }\n"
                "var rep = {status: comp ? 'success' : 'error', t: " + str(t) + ", "
                "comp: comp ? comp.name : 'not found'};\n"
                "try { if (comp) comp.saveFrameToPng(" + str(t) + ", new File('" + p + "')); "
                "rep.saved = true; } catch(e) { rep.status = 'error'; rep.message = e.toString(); }\n"
                f"var _repF = new File('{rep_path.replace(chr(92), chr(92)*2)}');\n"
                "_repF.encoding = 'UTF-8';\n"
                "if (_repF.open('w')) { _repF.write(JSON.stringify(rep)); _repF.close(); }\n"
                "return JSON.stringify(rep);\n"
                "})();"
            )
            rep = send_and_wait(jsx, rep_path, timeout=120)
            if rep.get("status") == "success":
                pngs.append(p.replace("\\\\", "\\"))
        frame_paths[v["label"]] = pngs
    print(f"[frames] A={len(frame_paths['A'])} 张, B={len(frame_paths['B'])} 张")

    # 3) 视觉评分对比（VLM 可用则 VLM，否则启发式并诚实标注）
    gw = VisualEvalGateway(backend="auto", context="FATE 抠像合成 强度变体对比")
    report = gw.compare_variants_sync([
        {"label": "A(intensity=0.8)", "image_paths": frame_paths["A"],
         "params": {"intensity": 0.8}},
        {"label": "B(intensity=1.2)", "image_paths": frame_paths["B"],
         "params": {"intensity": 1.2}},
    ])
    print("── M2 评分报告 ──")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
