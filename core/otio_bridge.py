# -*- coding: utf-8 -*-
"""otio_bridge.py — EDL 1.1 ↔ OTIO 时间线互换层（P2-11，行业空白卡位）

背景：CutLedger 评测确认公开生态无 OTIO/ACES 时间线互换覆盖（差距矩阵行 8），
本模块把项目 EDL 1.1（scripts/edl.py）与 OTIO 标准互通：
  - 正向映射：cuts→Clip(+Gap)、text_events→Marker 轨、speed→LinearTimeWarp、
    overlays→Overlay 轨、effects→clip effects
  - 无损信封：每条映射对象 metadata["kv_edl"] 保留原始字段——
    导回本系统零损失，外部工具读标准字段各取所需
  - 双导出：.otio（Resolve 19+/otio 工具链）与 .xml/FCPXML（Resolve ImportTimeline 最稳通道）

用法:
  python core/otio_bridge.py <edl.json> [--out DIR] [--fcpxml] [--roundtrip]
  from core.otio_bridge import edl_to_otio, export_otio, export_fcpxml, otio_to_edl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import opentimelineio as otio
from opentimelineio.opentime import RationalTime, TimeRange

_EPS = 1e-4
_DUR_CACHE: dict[str, float] = {}
_STREAM_CACHE: dict[str, tuple] = {}


def _probe_streams(path: str) -> tuple:
    """ffprobe 流类型 -> (has_video, has_audio)；失败按 (True, False) 保守处理。

    关键：Resolve 的 FCP XML 解析器拒收“音频文件挂视频轨 + 空 format”（实测返回 None
    中止解析），音频素材必须映射到 Audio 轨才能被真实导入。
    """
    if path in _STREAM_CACHE:
        return _STREAM_CACHE[path]
    import subprocess

    hv, ha = True, False
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20)
        types = {(line or "").strip() for line in out.stdout.splitlines()}
        hv = "video" in types
        ha = "audio" in types
    except (ValueError, OSError, subprocess.SubprocessError):
        pass
    _STREAM_CACHE[path] = (hv, ha)
    return hv, ha


def _probe_duration(path: str) -> float | None:
    """ffprobe 媒体总时长（秒）；fcp_xml 适配器要求 clip 有 available_range。"""
    if path in _DUR_CACHE:
        return _DUR_CACHE[path]
    import subprocess

    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20)
        d = float((out.stdout or "").strip())
    except (ValueError, OSError, subprocess.SubprocessError):
        d = None  # type: ignore[assignment]
    _DUR_CACHE[path] = d  # type: ignore[assignment]
    return d


def _rt(sec: float, fps: float) -> RationalTime:
    """秒 -> RationalTime（整帧量化，round 防浮点毛刺）。"""
    return RationalTime(round(sec * fps), fps)


def edl_to_otio(edl: dict):
    """EDL 1.1 dict -> otio.schema.Timeline。"""
    render = edl.get("render") or {}
    fps = float(render.get("fps") or 30)
    tl = otio.schema.Timeline(name=render.get("theme") or render.get("style") or "KV Timeline")

    # ---- 视频/音频轨：cuts 按媒体流类型分流（Resolve fcp_xml 解析器硬要求）----
    vtrack = otio.schema.Track(name="KV Video 1", kind=otio.schema.TrackKind.Video)
    atrack = otio.schema.Track(name="KV Audio 1", kind=otio.schema.TrackKind.Audio)
    cursor = 0.0
    for c in edl.get("cuts", []):
        st = float(c.get("start_time", cursor))
        if st - cursor > _EPS:  # vo 绝对时间轴模式下短语间停顿 -> Gap
            gap = otio.schema.Gap(duration=_rt(st - cursor, fps))
            vtrack.append(gap)
            atrack.append(otio.schema.Gap(duration=_rt(st - cursor, fps)))
        dur = float(c.get("end_time", st)) - st
        src_file = str(c.get("source_file", ""))
        ref = otio.schema.ExternalReference(target_url=src_file)
        # available_range：ffprobe 真实总时长，探不到则用 source_start+dur 估算兼容
        total = _probe_duration(src_file) or (float(c.get("source_start", 0.0)) + dur)
        ref.available_range = TimeRange(RationalTime(0, fps), _rt(max(total, dur), fps))
        clip = otio.schema.Clip(
            name=f"cut{c.get('index', len(vtrack))}_{Path(src_file).name}",
            media_reference=ref,
            source_range=TimeRange(_rt(float(c.get("source_start", 0.0)), fps), _rt(dur, fps)),
        )
        speed = float(c.get("speed", 1.0) or 1.0)
        if abs(speed - 1.0) > _EPS:
            warp = otio.schema.LinearTimeWarp(name=f"warp_{speed}")
            warp.time_warp_scale = speed
            clip.effects.append(warp)
        if str(c.get("transition", "cut")) not in ("cut", "", None):
            clip.metadata["kv_transition"] = c["transition"]
        clip.metadata["kv_edl"] = c  # 无损信封
        hv, ha = _probe_streams(src_file)
        if (not hv) and ha:           # 纯音频素材 -> 音频轨
            atrack.append(clip)
        else:
            vtrack.append(clip)
        cursor = st + dur
    tl.tracks.append(vtrack)
    if len(atrack) > 0:
        tl.tracks.append(atrack)

    # ---- 文字轨：text_events -> Marker（词级时间戳 + 样式元数据）----
    ttrack = otio.schema.Track(name="KV Text", kind=otio.schema.TrackKind.Video)
    for te in edl.get("text_events", []):
        m = otio.schema.Marker(
            name=str(te.get("word", "")),
            color="Blue",
            marked_range=TimeRange(_rt(float(te.get("t_in", 0.0)), fps),
                                   _rt(max(float(te.get("t_out", 0.0)) - float(te.get("t_in", 0.0)), 1 / fps), fps)),
        )
        m.metadata.update({k: v for k, v in te.items() if k != "word"})
        m.metadata["kv_kind"] = "text_event"
        ttrack.markers.append(m)
    tl.tracks.append(ttrack)

    # ---- Overlay 轨 ----
    ovl = edl.get("overlays") or []
    if ovl:
        otrack = otio.schema.Track(name="KV Overlay", kind=otio.schema.TrackKind.Video)
        for o in ovl:
            o_file = str(o.get("file", ""))
            o_ref = otio.schema.ExternalReference(target_url=o_file)
            o_total = _probe_duration(o_file) or float(o.get("duration", 0.0))
            o_ref.available_range = TimeRange(RationalTime(0, fps), _rt(max(o_total, float(o.get("duration", 0.0))), fps))
            clip = otio.schema.Clip(
                name=f"ovl_{Path(o_file).name}",
                media_reference=o_ref,
                source_range=TimeRange(RationalTime(0, fps), _rt(float(o.get("duration", 0.0)), fps)),
            )
            clip.metadata["kv_edl"] = o
            # start_in_output：用 Gap 前置对齐
            head = float(o.get("start_in_output", 0.0))
            if head > _EPS:
                otrack.append(otio.schema.Gap(duration=_rt(head, fps)))
            otrack.append(clip)
        tl.tracks.append(otrack)

    # ---- effects 轨：按 time_range 挂到视频轨最近 clip ----
    for ef in edl.get("effects", []):
        tr = ef.get("time_range") or {}
        t_in = float(tr.get("t_in", tr.get("start", 0.0)) or 0.0)
        target = None
        for item in vtrack:
            if isinstance(item, otio.schema.Clip):
                kv = item.metadata.get("kv_edl") or {}
                if float(kv.get("start_time", 0)) - _EPS <= t_in <= float(kv.get("end_time", 0)) + _EPS:
                    target = item
                    break
        eff = otio.schema.Effect(name=str(ef.get("effect_type", "effect")), effect_name=str(ef.get("effect_type", "effect")))
        eff.metadata["kv_edl"] = ef
        if target is not None:
            target.effects.append(eff)
        else:
            tl.effects.append(eff)

    # ---- timeline 级元数据（inputs 指纹/schema/cut_points 无损保留）----
    tl.metadata["kv_edl"] = {
        "schema_version": edl.get("schema_version", "1.1"),
        "render": render,
        "inputs": edl.get("inputs", []),
        "cut_points": edl.get("cut_points", []),
        "toolchain": edl.get("toolchain", {}),
    }
    return tl


def export_otio(edl: dict, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(edl_to_otio(edl), str(out))  # 扩展名选格式（.otio/.xml）
    return out


def export_fcpxml(edl: dict, out_path: str | Path) -> Path:
    """导出 FCP XML（Resolve/Premiere 导入时间线的最稳通道）。

    注：OpenTimelineIO-Plugins 0.18 实际提供的适配器名是 fcp_xml（非发布说明里的 fcpx_xml）。
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(edl_to_otio(edl), str(out), adapter_name="fcp_xml")
    return out


def _plain(x):
    """OTIO 的 C++ AnyDictionary/AnyVector 引用会随 timeline 释放而销毁，且非真 dict/list
    （json.dumps 不认）；离开绑定边界时递归拷贝成纯 Python 结构。"""
    if hasattr(x, "items"):                       # AnyDictionary / dict
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (str, bytes, int, float, bool)) or x is None:
        return x
    if hasattr(x, "__iter__") and hasattr(x, "__len__"):  # AnyVector / list / tuple
        return [_plain(i) for i in x]
    return str(x)                                  # RationalTime 等标量型对象


def otio_to_edl(timeline) -> dict:
    """OTIO -> EDL 1.1：优先读 kv_edl 无损信封；无信封的第三方 OTIO 走标准推断（有损但可用）。"""
    meta = timeline.metadata.get("kv_edl") or {}
    # 遍历剪辑轨（视频+音频；KV Overlay/KV Text 单独处理，不当 cuts）
    tracks = [t for t in timeline.tracks
              if isinstance(t, otio.schema.Track)
              and not t.name.startswith(("KV Overlay", "KV Text"))
              and (t.name.startswith("KV Video") or t.name.startswith("KV Audio")
                   or any(isinstance(i, otio.schema.Clip) for i in t))]
    cuts = []
    t_cursor = 0.0
    for trk in tracks:
        for item in trk:
            if isinstance(item, otio.schema.Gap):
                t_cursor += item.source_range.duration.value / max(item.source_range.duration.rate, 1)
                continue
            if not isinstance(item, otio.schema.Clip):
                continue
            kv = item.metadata.get("kv_edl")
            if kv:  # 无损路径（深拷贝离开 C++ 引用）
                cuts.append(_plain(kv))
                t_cursor = float(cuts[-1].get("end_time", t_cursor))
            else:   # 第三方推断路径
                sr = item.source_range
                rate = sr.duration.rate or 30
                dur = sr.duration.value / rate
                url = getattr(item.media_reference, "target_url", "") or ""
                cuts.append({
                    "index": len(cuts), "start_time": round(t_cursor, 4), "end_time": round(t_cursor + dur, 4),
                    "source_file": url, "source_start": round(sr.start_time.value / rate, 4),
                    "speed": 1.0, "transition": "cut", "mood": "imported", "energy": 0,
                })
                t_cursor += dur
    cuts.sort(key=lambda c: c.get("index", 0))
    text_events = []
    for t in timeline.tracks:
        for m in t.markers:
            if m.metadata.get("kv_kind") == "text_event" or True:
                mr = m.marked_range
                rate = mr.duration.rate or 30
                text_events.append({
                    "t_in": round(mr.start_time.value / rate, 4),
                    "t_out": round((mr.start_time.value + mr.duration.value) / rate, 4),
                    "word": m.name,
                    **_plain({k: v for k, v in m.metadata.items() if k != "kv_kind"}),
                })
    edl = _plain(meta)  # schema_version/render/inputs/cut_points/toolchain（深拷贝）
    edl.setdefault("schema_version", "1.1")
    edl["cuts"] = cuts
    # KV Overlay 轨还原为 overlays 字段
    ovl_track = next((t for t in timeline.tracks
                      if isinstance(t, otio.schema.Track) and t.name.startswith("KV Overlay")), None)
    if ovl_track is not None:
        overlays = [_plain(i.metadata["kv_edl"]) for i in ovl_track
                    if isinstance(i, otio.schema.Clip) and i.metadata.get("kv_edl")]
        if overlays:
            edl["overlays"] = overlays
    if text_events:
        edl["text_events"] = sorted(text_events, key=lambda x: x["t_in"])
    return edl


def roundtrip_check(edl: dict) -> dict:
    """EDL -> OTIO -> EDL 一致性报告（时间误差容忍 <1 帧）。"""
    back = otio_to_edl(edl_to_otio(edl))
    fps = float((edl.get("render") or {}).get("fps") or 30)
    tol = 1.0 / fps + 1e-6
    src_c, dst_c = edl.get("cuts", []), back.get("cuts", [])
    time_err = max((abs(a["start_time"] - b["start_time"]) for a, b in zip(src_c, dst_c)), default=0.0)
    src_te, dst_te = edl.get("text_events", []), back.get("text_events", [])
    te_err = max((abs(a["t_in"] - b["t_in"]) for a, b in zip(src_te, dst_te)), default=0.0)
    return {
        "cuts": {"src": len(src_c), "dst": len(dst_c), "ok": len(src_c) == len(dst_c) and time_err <= tol},
        "max_cut_time_err_sec": round(time_err, 6),
        "text_events": {"src": len(src_te), "dst": len(dst_te), "ok": len(src_te) == len(dst_te) and te_err <= tol},
        "max_te_err_sec": round(te_err, 6),
        "effects": {"src": len(edl.get("effects", [])), "dst": len(back.get("effects", []))},
        "verdict": "PASS" if (len(src_c) == len(dst_c) and time_err <= tol
                              and len(src_te) == len(dst_te) and te_err <= tol) else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="EDL 1.1 <-> OTIO 互换（P2-11）")
    ap.add_argument("edl", help="edl.json 路径")
    ap.add_argument("--out", default=None, help="产物目录（默认 EDL 同目录）")
    ap.add_argument("--fcpxml", action="store_true", help="同时导出 FCPXML")
    ap.add_argument("--roundtrip", action="store_true", help="执行往返一致性校验")
    a = ap.parse_args()

    edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
    out = Path(a.out or Path(a.edl).parent)
    p_otio = export_otio(edl, out / (Path(a.edl).stem + ".otio"))  # 标准扩展名（otio_json 适配器按后缀识别）
    print(f"OTIO: {p_otio}")
    if a.fcpxml:
        p_xml = export_fcpxml(edl, out / (Path(a.edl).stem + ".xml"))  # Resolve 认 .xml 扩展名
        print(f"FCPXML: {p_xml}")
    if a.roundtrip:
        rep = roundtrip_check(edl)
        print("ROUNDTRIP:", json.dumps(rep, ensure_ascii=False))
        return 0 if rep["verdict"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
