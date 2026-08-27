"""visual_scorer — M2 视觉评估闭环网关（直连 DashScope qwen-vl-max）

渲染帧 → Qwen-VL 多模态 → 结构化评分（维度打分 + 缺陷列表 + 建议）。

直连 DashScope（2026-08-16 实测: core.llm_gateway 的 gateway 只加载
deepseek/doubao 两个 provider, siliconflow/qwen 未注册, 视觉评分走不通;
改为直连 QWEN_BASE_URL + qwen-vl-max, 实测返回专业评审级 JSON）。

维度（对应顶尖 edit 观感要素）:
  dynamism / composition / color_harmony / text_read / texture / pacing

用法:
    from core.visual_scorer import score_video, iterate_parameters
    r = score_video("output.mp4", n_frames=6)
    # r = {"scores": {...}, "issues": [...], "advice": "...", "overall": n}
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# M2c: 视觉评分缓存目录（相同帧+prompt 命中直接返回, 省 API 计费）
_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "visual_scores"

DIMENSIONS = ["dynamism", "composition", "color_harmony", "text_read", "texture", "pacing"]

# ── M2e: 风格卡 → 维度优先级权重 ─────────────────────────────────────
# 解决 texture(加大粒子) 与 composition(缩小粒子) 的审美冲突:
# 不同风格卡的"重点维度"不同, 迭代时按权重选优先攻克的低分维度。
# weight>0 的维度参与自动迭代; 权重越高越优先。
STYLE_DIM_WEIGHTS = {
    "amv":       {"dynamism": 3, "pacing": 3, "composition": 2,
                  "color_harmony": 2, "texture": 1, "text_read": 1},   # 高燃: 节奏优先
    "cyberpunk": {"composition": 3, "color_harmony": 3, "texture": 2,
                  "text_read": 2, "dynamism": 1, "pacing": 1},         # 赛博: 构图+色彩
    "ambient":   {"color_harmony": 3, "texture": 2, "composition": 2,
                  "pacing": 2, "dynamism": 1, "text_read": 1},         # 氛围: 色彩质感
    "edit":      {"dynamism": 3, "pacing": 3, "composition": 2,
                  "color_harmony": 2, "texture": 2, "text_read": 2},   # 顶尖edit: 均衡偏节奏
    "vintage":   {"color_harmony": 3, "texture": 3, "composition": 2,
                  "text_read": 2, "dynamism": 1, "pacing": 1},         # 复古: 质感色彩
}
_DEFAULT_DIM_WEIGHTS = {"dynamism": 2, "composition": 2, "color_harmony": 2,
                        "text_read": 2, "texture": 2, "pacing": 2}


def get_dim_priority(style_card: str) -> Dict[str, int]:
    """风格卡 → 维度优先级权重（未知卡回退均衡）。"""
    return STYLE_DIM_WEIGHTS.get(style_card, _DEFAULT_DIM_WEIGHTS)

_PROMPT = (
    "你是资深动漫剪辑/动态设计评审。评估这组画面帧。"
    "严格只输出JSON（评分用一位小数 0-10, 如 7.3, 分辨率要求高）: "
    '{"scores":{"dynamism":0-10,"composition":0-10,"color_harmony":0-10,'
    '"text_read":0-10,"texture":0-10,"pacing":0-10},'
    '"issues":["具体问题1","具体问题2"],"advice":"最值得改的一项建议","overall":0-10}'
)


def _load_env() -> None:
    """从项目 .env 读 QWEN 配置（无 python-dotenv 依赖）。"""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _extract_json(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"scores": {}, "issues": [], "advice": "", "overall": 0}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"scores": {}, "issues": [], "advice": "", "overall": 0}


def _frame_to_b64(path: str, max_side: int = 768) -> str:
    import cv2
    import numpy as np
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"帧读取失败: {path}")
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        sc = max_side / max(h, w)
        img = cv2.resize(img, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise ValueError("帧编码失败")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _call_qwen_vl(frames_b64: List[str], prompt: str) -> Dict[str, Any]:
    """直连 DashScope compatible-mode 多模态（OpenAI 兼容格式）。"""
    _load_env()
    key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    base = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.environ.get("QWEN_VISION_MODEL", "qwen-vl-max")
    if not key:
        return {"error": "缺 QWEN_API_KEY"}
    content: list = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}
        for b in frames_b64
    ]
    content.append({"type": "text", "text": prompt})
    payload = {"model": model, "messages": [{"role": "user", "content": content}]}
    # M2c: 缓存 + 重试（生产级: 视觉 API 偶发超时/限流, 缓存避免重复计费）
    # 2026-08-16 修复: key 曾只取 frames_b64[:2000] —— 图像前部(背景)在迭代中
    # 不变导致 base64 前缀碰撞, 3 轮评分命中同一旧缓存假收敛。改用完整哈希。
    cache_key = hashlib.md5(
        (prompt + "|" + "|".join(frames_b64)).encode()).hexdigest()[:16]
    cache_file = Path(_CACHE_DIR) / f"{cache_key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    # 死代理直连 (2026-08-16 修复): Windows 注册表残留 Clash 代理配置时代理进程
    # 已死, urlopen 默认走系统代理必报 WinError 10061。DashScope 国内服务无需代理。
    _opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_err = ""
    for attempt in range(3):  # 重试 3 次
        try:
            with _opener.open(req, timeout=120) as resp:
                d = json.loads(resp.read())
            text = d["choices"][0]["message"]["content"]
            result = _extract_json(text)
            if not result.get("error"):
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            return result
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt < 2:  # 最后一次失败后不再空等
                time.sleep(3 * (attempt + 1))
    return {"error": last_err}


def score_video(video_path: str, n_frames: int = 6,
                prompt: str = _PROMPT) -> Dict[str, Any]:
    """视频均匀抽帧聚合评分。"""
    import cv2
    import tempfile
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return {"error": "无法打开视频"}
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            return {"error": "空视频"}
        n = min(n_frames, total)
        step = (total - 1) / max(n - 1, 1)
        idxs = [round(i * step) for i in range(n)]
        frames_b64: List[str] = []
        with tempfile.TemporaryDirectory() as td:
            for gi in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
                ret, f = cap.read()
                if not ret:
                    continue
                fp = Path(td) / f"f{gi:04d}.jpg"
                cv2.imwrite(str(fp), f, [cv2.IMWRITE_JPEG_QUALITY, 82])
                frames_b64.append(_frame_to_b64(str(fp)))
    finally:
        cap.release()
    if not frames_b64:
        return {"error": "无帧"}
    return _call_qwen_vl(frames_b64, prompt)


_CLOSEUP_PROMPT = (
    "这是动漫画面中央区域放大特写。请重点评估特效/粒子细节的质感(texture)和层次。"
    "严格只输出JSON: "
    '{"texture":0-10,"issues":["细节问题"],"advice":"最值得改的一项",'
    '"grain_ok":true/false,"particle_detail":0-10}'
)


_SEQUENCE_PROMPT = (
    "这是一段按时间顺序排列的画面帧序列（从节拍前到节拍后，已标注时间）。"
    "请评估节奏感(pacing)和动态冲击：节拍处画面变化是否到位、有无呼吸感、"
    "加速/定格是否有效。严格只输出JSON: "
    '{"pacing":0-10,"dynamism":0-10,"issues":["节奏问题"],'
    '"advice":"最值得改的一项","frame_diff_ok":true/false}'
)


def score_sequence(video_path: str, t_start: float, t_end: float,
                   n_frames: int = 8, prompt: str = _SEQUENCE_PROMPT) -> Dict[str, Any]:
    """时序评分（M2f）: 指定时间窗口连续帧序列评分 pacing。

    旧 score_video 抽均匀帧（首/中/尾），pacing 只能靠模型推理。
    本函数抽节拍窗口（如 drop 段 2.3-3.5s）的连续帧，帧间标注时间，
    让模型真正看到"节拍处画面是否变化/定格/加速"——pacing 维度的硬证据。
    同时返回帧间差异统计（diffs）作为客观对照。
    """
    import cv2
    import tempfile
    import numpy as np
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return {"error": "无法打开视频"}
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        f0 = max(0, int(t_start * fps))
        f1 = min(total - 1, int(t_end * fps))
        n = min(n_frames, max(f1 - f0 + 1, 1))
        if f1 <= f0:
            return {"error": "时间窗口无效"}
        step = max(1, (f1 - f0) // max(n - 1, 1))
        idxs = [f0 + i * step for i in range(n) if f0 + i * step <= f1]
        if len(idxs) < 2:
            return {"error": "帧太少"}
        frames_b64: List[str] = []
        diffs: List[float] = []
        prev = None
        with tempfile.TemporaryDirectory() as td:
            for gi in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
                ret, f = cap.read()
                if not ret:
                    continue
                g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                if prev is not None:
                    diffs.append(float(np.mean(np.abs(g.astype(np.int32) - prev))))
                prev = g
                fp = Path(td) / f"seq_{gi:04d}.jpg"
                cv2.imwrite(str(fp), f, [cv2.IMWRITE_JPEG_QUALITY, 82])
                frames_b64.append(_frame_to_b64(str(fp)))
    finally:
        cap.release()
    if len(frames_b64) < 2:
        return {"error": "无帧"}
    # 时间标注注入 prompt（让模型知道帧是连续的节拍窗口）
    window_prompt = (f"{prompt} 时间窗口: {t_start:.2f}s → {t_end:.2f}s, "
                     f"{len(frames_b64)} 帧, 帧间隔约 {step / fps:.2f}s")
    result = _call_qwen_vl(frames_b64, window_prompt)
    result["diffs"] = [round(d, 1) for d in diffs]
    result["diff_mean"] = round(float(np.mean(diffs)), 2) if diffs else 0.0
    result["window"] = [round(t_start, 2), round(t_end, 2)]
    return result


def score_closeup(video_path: str, center_ratio: float = 0.5,
                  frame_idx: Optional[int] = None) -> Dict[str, Any]:
    """特写评分（M2a）: 裁中央 region 放大评分 texture 细节。

    解决全帧评分的 texture 振荡——全帧里粒子只占 5%, AI 看不清细节
    只能猜（表现为反复建议"加大粒子"）。放大后 AI 能看清粒子透明度/
    层次, 给出可执行建议（2026-08-16 实测: 建议从"加大"变为
    "透明度渐变+动态变化"）。
    """
    import cv2
    import tempfile
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return {"error": "无法打开视频"}
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            return {"error": "空视频"}
        if frame_idx is None:
            frame_idx = total // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_idx, total - 1))
        ret, f = cap.read()
    finally:
        cap.release()
    if not ret:
        return {"error": "帧读取失败"}
    h, w = f.shape[:2]
    r = max(center_ratio, 0.1)
    x0, x1 = int(w * (1 - r) / 2), int(w * (1 + r) / 2)
    y0, y1 = int(h * (1 - r) / 2), int(h * (1 + r) / 2)
    crop = f[y0:y1, x0:x1]
    # 放大回原尺寸（让 AI 看清细节）
    crop = cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC)
    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "closeup.jpg"
        cv2.imwrite(str(fp), crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return _call_qwen_vl([_frame_to_b64(str(fp))], _CLOSEUP_PROMPT)


def score_frames(frame_paths: List[str], prompt: str = _PROMPT) -> Dict[str, Any]:
    """指定帧文件评分。"""
    return _call_qwen_vl([_frame_to_b64(p) for p in frame_paths], prompt)


def iterate_parameters(tree, score: Dict[str, Any],
                       target_dim: str = "dynamism") -> Dict[str, Any]:
    """参数迭代（M2 闭环 v2）: AI advice 语义驱动, 返回新树。

    v2 升级（2026-08-16）: 硬编码幅度方向只对部分维度有效（实测 text_read 方向
    错误——AI 说"文字遮挡面部"应缩小, 旧规则却放大）。改为让 qwen-vl 输出
    结构化动作: {"actions":[{"param":"particle_size","dir":"down","amount":0.3}]}
    动作参数名 → 合成树字段映射见 _ACTION_MAP。
    """
    scores = score.get("scores", {})
    cur = scores.get(target_dim, 5)
    if cur >= 7:
        return {"status": "ok", "tree": tree, "note": f"{target_dim}={cur} 已达标"}

    advice = score.get("advice", "")
    # 1. 让 qwen-vl 解析 advice → 结构化动作
    actions = _parse_advice_actions(advice, target_dim, cur)
    if not actions:
        # 2. 解析失败回退启发式（仅保留语义正确的方向）
        return _heuristic_fallback(tree, target_dim, cur)

    # 3. 应用动作到合成树
    applied = _apply_actions(tree, actions)
    if applied:
        return {"status": "iterated", "tree": tree, "note": f"{target_dim}={cur} → {actions}"}
    return {"status": "iterated", "tree": tree,
            "note": f"{target_dim}={cur} (advice 无匹配动作, 回退启发式)"}


def pick_target_dim(score: Dict[str, Any], style_card: str = "edit",
                    target: float = 7.0) -> Optional[str]:
    """M2e: 按风格卡权重选迭代维度。

    排序键 = (score 差距) / 权重 —— 低分且高优先级的维度先攻。
    例: edit 风格下 dynamism 权重 3, texture 权重 2 → 同分时先攻 dynamism。
    解决 texture(加大粒子) vs composition(缩小粒子) 的冲突:
    高燃风格(edit/amv) 优先保 dynamism, 复古(ambient/vintage) 优先保 texture。
    """
    scores = score.get("scores", {})
    weights = get_dim_priority(style_card)
    candidates = []
    for dim, val in scores.items():
        if val >= target:
            continue
        w = weights.get(dim, 2)
        # 低分 × 高权重 = 高优先（除以权重使差距等价化）
        priority = (target - val) * w
        candidates.append((priority, dim, val))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


# ── advice → 动作解析 ─────────────────────────────────────────────

_ACTION_PROMPT = (
    "根据这条剪辑评审建议, 输出结构化调参动作。"
    "只输出JSON数组: [{\"param\":\"particle_size|particle_count|glow_strength|"
    "text_size|chromatic_amount|punch_amount|shake_amp|opacity\","
    "\"dir\":\"up|down\",\"amount\":0.0-0.5}] "
    "amount是幅度比例(如0.3=调30%)。无法对应则输出[]。"
    "建议: {advice}"
)


def _parse_advice_actions(advice: str, dim: str, cur: float) -> List[Dict[str, Any]]:
    if not advice.strip():
        return []
    _load_env()
    key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        return []
    base = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.environ.get("QWEN_FLASH_MODEL", "qwen-flash")
    payload = {"model": model,
               "messages": [{"role": "user",
                             "content": _ACTION_PROMPT.replace("{advice}", advice)}]}
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        _opener2 = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 死代理直连
        with _opener2.open(req, timeout=60) as resp:
            d = json.loads(resp.read())
        text = d["choices"][0]["message"]["content"]
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            return []
        acts = json.loads(m.group(0))
        return [a for a in acts if a.get("param") and a.get("dir") in ("up", "down")]
    except Exception:
        return []


# 动作参数名 → 合成树字段操作
_ACTION_MAP = {
    "particle_size": ("particle", "psize_scale", "mul"),
    "particle_count": ("particle", "_pps_mult", "mul"),
    "glow_strength": ("particle", "_glow_mult", "mul"),
    "text_size": ("text", "size", "mul"),
    "chromatic_amount": ("edit_fx", "rgb_burst.max_amount", "mul"),
    "punch_amount": ("edit_fx", "punch.amount", "mul"),
    "shake_amp": ("edit_fx", "shake.amp", "mul"),
    "opacity": ("text", "opacity", "mul"),
}


def _apply_actions(tree, actions: List[Dict[str, Any]]) -> bool:
    applied = False
    for a in actions:
        spec = _ACTION_MAP.get(a["param"])
        if not spec:
            continue
        target_type, field, mode = spec
        factor = 1 + a["amount"] * (1 if a["dir"] == "up" else -1)
        for layer in tree.layers:
            if target_type == "edit_fx":
                # edit_fx 挂在层 content 上（当前模板为 text 层），有就作用，
                # 与 _heuristic_fallback 的语义保持一致
                fx = layer.content.get("edit_fx")
                if not fx:
                    continue
                parts = field.split(".")
                node = fx.get(parts[0])
                if len(parts) > 1 and isinstance(node, dict):
                    # 'shake.amp' / 'punch.amount' / 'rgb_burst.max_amount'
                    node[parts[1]] = max(6.0, node.get(parts[1], 12.0) * factor)
                elif len(parts) == 1 and not isinstance(node, dict):
                    fx[parts[0]] = node * factor
                else:
                    continue  # 结构与动作不匹配（如点路径指向标量）
                applied = True
            elif (target_type == "particle" and layer.type == "particle"
                    or target_type == "text" and layer.type == "text"):
                if field == "psize_scale":
                    layer.content["psize_scale"] = max(0.3, layer.content.get("psize_scale", 1.0) * factor)
                elif field == "size":
                    layer.content["size"] = max(24, int(layer.content.get("size", 96) * factor))
                elif field == "opacity":
                    layer.content["opacity"] = min(100, layer.content.get("opacity", 100) * factor)
                else:
                    # 粒子 _pps_mult/_glow_mult 暂存 multiplier
                    layer.content[field] = max(0.5, layer.content.get(field, 1.0) * factor)
                applied = True
    return applied


def _heuristic_fallback(tree, target_dim: str, cur: float) -> Dict[str, Any]:
    """回退启发式（仅保留语义正确的方向, 2026-08-16 修正）:
      dynamism 低 → punch/shake 加强
      color_harmony 低 → 色差收敛
      composition 低 → 粒子缩小
      text_read 低 → 文字缩小(修正: 旧规则放大是反的)
    """
    for layer in tree.layers:
        fx = layer.content.get("edit_fx")
        if target_dim == "dynamism" and fx:
            if "punch" in fx:
                fx["punch"]["amount"] = fx["punch"].get("amount", 10.0) * 1.2
            if "shake" in fx:
                fx["shake"]["amp"] = fx["shake"].get("amp", 12.0) * 1.2
        elif target_dim == "color_harmony" and fx and "rgb_burst" in fx:
            fx["rgb_burst"]["max_amount"] = max(6.0, fx["rgb_burst"].get("max_amount", 12.0) * 0.8)
        elif target_dim == "composition" and layer.type == "particle":
            layer.content["psize_scale"] = max(0.3, layer.content.get("psize_scale", 1.0) * 0.7)
        elif target_dim == "text_read" and layer.type == "text":
            layer.content["size"] = max(24, int(layer.content.get("size", 96) * 0.9))
    return {"status": "iterated", "tree": tree, "note": f"{target_dim}={cur} 启发式回退"}


__all__ = ["score_video", "score_frames", "score_closeup", "score_sequence",
           "iterate_parameters", "pick_target_dim", "get_dim_priority", "DIMENSIONS"]
