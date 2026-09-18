"""m2_auto_iterate.py — M2 视觉评估自动多轮循环

无人值守闭环: 渲染 → qwen-vl 评分 → 低分维度自动调参 → 重渲染 → 复评
直到: 所有维度 >= 目标 或 达最大轮数。

用法:
  python scripts/m2_auto_iterate.py [--rounds 3] [--target 7] [--video edit_full.mp4]

输出: 每轮评分 JSON 到 output/m2_iteration/ 供对照分析。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.cnn_scorer import score_video_mode  # noqa: E402
from core.visual_scorer import iterate_parameters, pick_target_dim, score_closeup, score_video  # noqa: E402


def render_tree(tree, out_mp4: str, aep_name: str, lut: dict = None) -> bool:
    """合成树 → 真机执行 → 渲染 MP4。返回成功与否。

    lut: 可选 {"cube": <路径>, "strength": 0-1} — 转码阶段挂 3D LUT
    (AE 内 Lumetri LUT 参数是资产型, 脚本化会弹 UI 卡死, 故走 ffmpeg, 见 core/lut_pipeline.py)
    execute() 内部: JSX >30KB 自动走 build_batches 分批 (ExtendScript ~32KB 截断)。
    """
    """合成树 → 真机执行 → 渲染 MP4。返回成功与否。"""
    import os
    import uuid
    from pathlib import Path as P

    from core.synthesis_orchestrator import SynthesisOrchestrator
    bd = P(PROJECT) / ".ae-mcp-bridge"

    def send(code, wait=8):
        cmd_id = str(uuid.uuid4())[:8]
        # 2026-08-27: 监听器白名单只有 executeAtomScript (runScript 不在), 改协议
        cmd = {"id": cmd_id, "command": "executeAtomScript", "args": {"script": code}, "timestamp": time.time()}
        tmp = bd / f"ae_command_{cmd_id}.tmp"
        tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
        for _ in range(5):
            try:
                os.replace(str(tmp), str(bd / "ae_command.json")); break
            except PermissionError:
                time.sleep(2)
        time.sleep(wait)
        rf = bd / "ae_result.json"
        return json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {"err": "timeout"}

    # 清同名合成
    send(f'(function(){{ var n=0; for (var i=app.project.numItems; i>=1; i--)'
         f'{{ if (app.project.item(i).name.indexOf("{tree.comp_name}")>=0)'
         f'{{ app.project.item(i).remove(); n++; }} }} return "removed "+n; }})();', 6)
    # 执行
    o = SynthesisOrchestrator()
    r = o.execute(tree, dry_run=False)
    if r.get("status") != "success":
        print(f"[render] 执行失败: {r}")
        return False
    # 配置渲染队列（路径全部正斜杠, 避免 JS 反斜杠转义）
    aep = P(PROJECT) / "tmp" / aep_name
    aep_js = str(aep).replace(chr(92), "/")
    avi = P(PROJECT) / "output" / "one_pipeline" / (aep_name.replace(".aep", ".avi"))
    avi_js = str(avi).replace(chr(92), "/")
    q = send(f"""(function(){{
      var comp=null;
      for (var i=1;i<=app.project.numItems;i++){{ if (app.project.item(i).name.indexOf('{tree.comp_name}')>=0){{ comp=app.project.item(i); break; }} }}
      if (!comp) return 'notfound';
      var rq=app.project.renderQueue;
      for (var k=rq.numItems;k>=1;k--) rq.item(k).remove();
      var rqItem=rq.items.add(comp);
      var om=rqItem.outputModule(1);
      var tpls=om.templates;
      for (var ti=0;ti<tpls.length;ti++){{ if (tpls[ti]==='无损'){{ om.applyTemplate(tpls[ti]); break; }} }}
      om.file=new File('{avi_js}');
      app.project.save(File('{aep_js}'));
      return 'queued';
    }})();""")
    # 2026-08-27: executeAtomScript 经 new Function 执行, 返回串被监听器吞
    # (只见 {"executed":true}) → 判定改为验 aep 落盘时间戳 (save 是脚本最后一步)
    def _queue_ok():
        try:
            return aep.exists() and aep.stat().st_mtime > time.time() - 120
        except OSError:
            return False
    if not _queue_ok():
        # 竞态/残留结果兜底: 清掉结果重试一次
        time.sleep(5)
        q = send(f"""(function(){{
          var comp=null;
          for (var i=1;i<=app.project.numItems;i++){{ if (app.project.item(i).name.indexOf('{tree.comp_name}')>=0){{ comp=app.project.item(i); break; }} }}
          if (!comp) return 'notfound';
          var rq=app.project.renderQueue;
          for (var k=rq.numItems;k>=1;k--) rq.item(k).remove();
          var rqItem=rq.items.add(comp);
          var om=rqItem.outputModule(1);
          var tpls=om.templates;
          for (var ti=0;ti<tpls.length;ti++){{ if (tpls[ti]==='无损'){{ om.applyTemplate(tpls[ti]); break; }} }}
          om.file=new File('{avi_js}');
          app.project.save(File('{aep_js}'));
          return 'queued';
        }})();""", wait=12)
    if not _queue_ok():
        print(f"[render] 队列失败 (aep 未更新): {q}")
        return False
    # aerender
    aerender = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"
    p = subprocess.run([aerender, "-project", str(aep)], capture_output=True, text=True,
                       timeout=600, encoding="utf-8", errors="ignore")
    if not avi.exists():
        print(f"[render] 无产物: {p.stdout[-300:]}")
        return False
    # 转 MP4 (可选挂 LUT: 转码阶段 lut3d + blend 强度混合; 失败必须打印防静默)
    if lut and lut.get("cube"):
        from core.lut_pipeline import transcode_with_lut
        if not transcode_with_lut(str(avi), out_mp4, lut["cube"],
                                  float(lut.get("strength", 1.0)), crf=17):
            print(f"[render] LUT 转码失败 (avi 可能损坏/被锁: {avi})")
    else:
        _r = subprocess.run(["ffmpeg", "-y", "-i", str(avi), "-c:v", "libx264",
                             "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                             out_mp4], capture_output=True, timeout=180)
        if _r.returncode != 0:
            print(f"[render] ffmpeg 失败 rc={_r.returncode}: "
                  f"{_r.stderr.decode(errors='ignore')[-200:]}")
    # 2026-08-16 修复: aerender/ffmpeg 句柄未完全释放时 unlink 抛 PermissionError
    # （WinError 32 文件被占用）→ 重试等待句柄释放
    for _attempt in range(5):
        try:
            avi.unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(2)
    return Path(out_mp4).exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--target", type=float, default=7.0)
    ap.add_argument("--video", default="output/one_pipeline/edit_full.mp4")
    ap.add_argument("--scorer", default="hybrid", choices=["local", "hybrid", "qwen"])
    args = ap.parse_args()

    out_dir = PROJECT / "output" / "m2_iteration"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 初始树（真实素材全要素）
    from core.composition_tree import CompositionTree, EffectRef, LayerSpec
    DUR = 5.0
    FOOTAGE = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"
    tree = CompositionTree(
        comp_name="Edit_M2Auto", style_card="edit", duration=DUR,
        layers=[
            LayerSpec(id="clip", type="footage", name="FATE", z_index=0,
                      time_range=[0, DUR],
                      content={"path": str(PROJECT / FOOTAGE), "matting_mode": "rgba",
                               "fit": "cover", "source_dur": 16.37,
                               "speed_ramps": [{"t": 0, "v": 1.0}, {"t": 2.3, "v": 1.0},
                                               {"t": 2.42, "v": 0.02}, {"t": 2.6, "v": 0.02},
                                               {"t": 2.7, "v": 2.2}, {"t": 3.6, "v": 2.2},
                                               {"t": 3.8, "v": 1.0}, {"t": DUR, "v": 1.0}],
                               "edit_fx": {"punch": {}, "shake": {}}}),
            LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                      time_range=[0, DUR], content={"template": "spark", "t_hit": 2.5}),
            LayerSpec(id="title", type="text", name="Title", z_index=2,
                      time_range=[0.4, DUR - 0.4],
                      content={"text": "CLASH", "size": 200,
                               "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                               "font": "auto",
                               "char_anim": {"preset": "tracking_stagger",
                                             "duration_ms": 520, "tracking": 26},
                               "edit_fx": {"punch": {}, "glow_hit": {}}},
                      effects=[EffectRef("match", "ADBE Glo2", {"radius": 26, "intensity": 1.4})]),
            LayerSpec(id="sub", type="text", name="Sub", z_index=3,
                      time_range=[2.4, DUR - 0.4],
                      content={"text": "NO ESCAPE", "size": 64,
                               "colors": {"main": "#FF4D6D", "glow": "#FF4D6D", "accent": "#FFF"},
                               "font": "auto", "font_role": "sub",
                               "edit_fx": {"rgb_burst": {}},
                               "char_anim": {"preset": "tracking_stagger",
                                             "duration_ms": 400, "tracking": 14}}),
            LayerSpec(id="aura", type="gen_fx", name="Aura", z_index=4,
                      time_range=[0, DUR],
                      content={"prompt": "青色能量辉光", "kind": "glow",
                               "engine": "auto", "fit": "cover"}),
            LayerSpec(id="grain", type="adjustment", name="GrainPost", z_index=9,
                      time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": 9}),
        ],
        beat_events=[{"time": 2.5, "beat_type": "kick", "layer_id": "title"},
                     {"time": 1.5, "beat_type": "snare", "layer_id": "sub"},
                     {"time": 3.5, "beat_type": "snare", "layer_id": "sub"}],
    )
    sections = [{"type": "intro", "start": 0, "end": 1.4},
                {"type": "build", "start": 1.4, "end": 2.4},
                {"type": "drop", "start": 2.4, "end": 3.9},
                {"type": "outro", "start": 3.9, "end": DUR}]

    history = []
    cur_video = args.video
    for i in range(1, args.rounds + 1):
        print(f"\n=== 第 {i} 轮评分 ===")
        score = score_video(cur_video, n_frames=6)
        history.append({"round": i, "video": cur_video, "score": score})
        (out_dir / f"round{i}_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"overall={score.get('overall')} | scores={score.get('scores')}")
        print(f"issues={score.get('issues', [])}")

        # M2e: 按风格卡权重选迭代维度（低分×高权重优先, 解决 texture/composition 冲突）
        dim = pick_target_dim(score, style_card=tree.style_card, target=args.target)
        changed = False
        if dim is None:
            print("全部达标, 停止")
            break
        val = score.get("scores", {}).get(dim, 5)
        # M2a/M2b: texture 维度走特写评分 + 保护（粒子只占5%, 全帧AI看不清
        # 细节只会猜"加大粒子"→ 与 composition 矛盾振荡; 特写看清细节才迭代）
        if dim == "texture":
            closeup = score_closeup(cur_video, center_ratio=0.6)
            cv = closeup.get("texture", val)
            print(f"  [texture] 特写评分={cv} (全帧={val})")
            if cv >= args.target:
                print(f"  texture 特写达标({cv}), 跳过自动迭代")
            else:
                # 特写仍低 → 用特写 advice 迭代（粒子相关动作）
                score2 = dict(score)
                score2["scores"]["texture"] = cv
                score2["advice"] = closeup.get("advice", score.get("advice", ""))
                r = iterate_parameters(tree, score2, target_dim="texture")
                print(f"  [texture特写={cv}] {r.get('note')}")
                changed = True
        else:
            r = iterate_parameters(tree, score, target_dim=dim)
            if r.get("status") == "iterated":
                print(f"  [{dim}={val}] {r.get('note')}")
                changed = True
        if not changed:
            print("该维度达标, 停止本轮")
            break

        # 重渲染
        out_mp4 = out_dir / f"round{i+1}.mp4"
        print(f"重渲染 → {out_mp4}")
        if not render_tree(tree, str(out_mp4), f"m2_round{i}.aep"):
            print("渲染失败, 停止")
            break
        cur_video = str(out_mp4)
        # M2g: 记录参数快照（训练调参器的 (参数,评分) 样本）
        snapshot = _param_snapshot(tree)
        history[-1]["params"] = snapshot

    (out_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    # M2g: 平铺训练样本（每轮: 参数特征 + 评分标签）
    train_rows = []
    for h in history:
        if "params" in h:
            row = dict(h["params"])
            row.update({f"score_{k}": v for k, v in h["score"].get("scores", {}).items()})
            row["score_overall"] = h["score"].get("overall", 0)
            train_rows.append(row)
    # 数据卫生 (2026-08-16): qwen 模式 → 追加真值库 data/param_tuning/train_samples.jsonl;
    # local/hybrid → 分离文件, 绝不污染 qwen 真值库。键名规范化 (前缀判重)。
    DATA_SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
    if args.scorer == "qwen":
        samples_file = DATA_SAMPLES
    else:
        samples_file = out_dir / f"train_samples_{args.scorer}.jsonl"
    samples_file.parent.mkdir(parents=True, exist_ok=True)
    mode_append = "a" if samples_file.exists() else "w"
    with open(samples_file, mode_append, encoding="utf-8") as _sf:
        _sf.write("\n".join(json.dumps(r, ensure_ascii=False) for r in train_rows) + "\n")
    print(f"\n完成: {len(history)} 轮, {len(train_rows)} 训练样本 → {out_dir}")
    return 0


def _param_snapshot(tree) -> Dict[str, Any]:
    """提取合成树的关键参数向量（调参器特征）。"""
    snap: Dict[str, Any] = {"style": tree.style_card}
    for layer in tree.layers:
        fx = layer.content.get("edit_fx")
        if layer.type == "particle":
            snap["particle_template"] = layer.content.get("template", "")
            snap["psize_scale"] = layer.content.get("psize_scale", 1.0)
            snap["_pps_mult"] = layer.content.get("_pps_mult", 1.0)
            snap["_glow_mult"] = layer.content.get("_glow_mult", 1.0)
        if layer.type == "text":
            sz = layer.content.get("size", 96)
            # 主标题 = 字号最大的 text 层（sub 是次要层）
            if "text_size" not in snap or sz > snap["text_size"]:
                snap["text_size"] = sz
            snap.setdefault("text_opacity", layer.content.get("opacity", 100))
        if fx:
            if "punch" in fx:
                snap["punch_amount"] = fx["punch"].get("amount", 10.0)
            if "shake" in fx:
                snap["shake_amp"] = fx["shake"].get("amp", 12.0)
            if "rgb_burst" in fx:
                snap["chromatic_amount"] = fx["rgb_burst"].get("max_amount", 12.0)
            if "glow_hit" in fx:
                snap["glow_intensity"] = fx["glow_hit"].get("intensity", 2.5)
    return snap


if __name__ == "__main__":
    sys.exit(main())
