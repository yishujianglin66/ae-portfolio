"""BeatLock 真机链路：抠像合成树 + BGM 节拍锚定 → JSX → AE Bridge（M3 集成，主会话）

用法:
  py -3.12 scripts/run_ae_beatlock_compose.py [--duration 8] [--bgm <mp3>]
      [--footage <mov>] [--intensity 1.0] [--dry]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, ".")
from core.beatlock import BeatGrid, compose
from core.composition_tree import build_fate_composite_template

BRIDGE = ".ae-mcp-bridge"
CMD = f"{BRIDGE}/ae_command.json"
RES = f"{BRIDGE}/ae_result.json"
OUT = os.path.abspath(f"{BRIDGE}/_beatlock_out.txt")

BGM_DEFAULT = r"D:\AE-Work\音效素材库\BGM\渡子升级.mp3"
FOOTAGE_DEFAULT = (r"D:\AE-Work\batch_auto_frame\DL_FATE_r978_BV1qb411C79B_p1"
                   r"\DL_FATE_r978_BV1qb411C79B_p1_transparent.mov")
AUDIOMAP_DEFAULT = r"tmp/audiomap_52a283d2.json"  # 渡子升级 BGM 网格（对侧生成，缓存键含乱码路径）


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bgm", default=BGM_DEFAULT)
    ap.add_argument("--audiomap", default=AUDIOMAP_DEFAULT,
                    help="直接指定 audiomap json（跳过 BGM 分析/缓存键，避免乱码路径缓存miss）")
    ap.add_argument("--footage", default=FOOTAGE_DEFAULT)
    ap.add_argument("--duration", type=float, default=8.0)
    ap.add_argument("--intensity", type=float, default=1.0)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    tree = build_fate_composite_template(args.footage, duration=args.duration)
    tree.comp_name = "M3_Beat_Fate"
    # 标题层起点拉满：避免节拍关键帧落在图层 inPoint 之前（AE setValueAtTime 越界风险）
    for layer in tree.layers:
        if layer.type == "text":
            layer.time_range[0] = 0.0

    if args.audiomap and os.path.exists(args.audiomap):
        with open(args.audiomap, encoding="utf-8") as f:
            grid = BeatGrid.from_audiomap(json.load(f))
    else:
        grid = BeatGrid.load(args.bgm)
    if grid is None:
        print("[BeatLock] beatgrid 加载失败，回退纯合成或退出")
        return 1
    print(f"[BeatGrid] kick={len(grid.kick)} strong={len(grid.strong)} "
          f"weak={len(grid.weak)} rolls={len(grid.rolls)} bpm={grid.bpm}")

    merged, res = compose(tree, grid, fps=30, intensity=args.intensity)
    print(f"[BeatLock] anchors={len(res.anchors)} dropped={res.dropped} "
          f"warnings={len(res.warnings)}")
    for a in res.anchors[:14]:
        print(f"    {a.time:6.2f}s {a.beat_type:9s} -> {a.action:6s} on {a.layer_id}")
    for w in res.warnings[:4]:
        print(f"    [warn] {w}")
    print(f"[JSX] {len(merged)} 字符")

    if args.dry:
        print("[dry] 仅生成，不执行真机")
        return 0

    # 注入文件报告 + 关键帧校验（绕开 ae_result.json 序列化丢失）
    inject = (
        f"var _repF = new File('{OUT.replace(chr(92), chr(92)*2)}');\n"
        "_repF.encoding = 'UTF-8';\n"
        "try { _result.titleScaleKeys = String(comp.layer(1).property(\"ADBE Transform Group\").property(\"ADBE Scale\").numKeys); } catch(e) { _result.titleScaleKeys = 'ERR:' + e.toString(); }\n"
        "try { _result.titleOpacityKeys = String(comp.layer(1).property(\"ADBE Transform Group\").property(\"ADBE Opacity\").numKeys); } catch(e) { _result.titleOpacityKeys = 'ERR'; }\n"
        "try { _result.charName = comp.layer(2).name; } catch(e) { _result.charName = 'ERR'; }\n"
        "if (_repF.open('w')) { _repF.write(JSON.stringify(_result)); _repF.close(); }\n"
        "  return JSON.stringify(_result);"
    )
    merged = merged.replace("  return JSON.stringify(_result);", inject, 1)

    cmd = {"command": "executeAtomScript", "args": {"script": merged},
           "status": "pending", "timestamp": time.strftime("%Y%m%d%H%M%S")}
    for p in (CMD, RES):
        if os.path.exists(p):
            os.remove(p)
            time.sleep(0.2)
    if os.path.exists(OUT):
        os.remove(OUT)
    with open(CMD, "w", encoding="utf-8") as f:
        json.dump(cmd, f, ensure_ascii=False)
    print("命令已发送，等待 AE...")

    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(3)
        if os.path.exists(OUT):
            with open(OUT, "r", encoding="utf-8") as f:
                print("── AE 执行报告 ──")
                print(f.read())
            return 0
    print("超时（报告文件未生成）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
