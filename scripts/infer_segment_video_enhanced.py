"""
Tier 1 + Tier 2 增强推理脚本（venv-sam2 子进程）
=================================================
Tier 1: SAM2 video 传播模式
  - 关键帧间隔 N=15 帧，auto_frame 检测 box → SAM2 video predictor 注入 → 传播
  - 传播失败帧（mask 面积 < 关键帧 mask 的 30%）回退到 auto_frame 单帧预测
  - 多角色支持：每个 box 作为独立 obj_id 注入

Tier 2: 边缘精修后处理
  - Guided Filter（radius=8, eps=0.01）以原图为引导锐化 mask 边缘
  - 形态学 Close（3x3 椭圆核）填补小空洞
  - 形态学 Open（2x2 椭圆核）去除孤立噪点
  - Alpha 羽化：边缘 2px 高斯模糊
  - 连通域清理：面积 < 500px 的独立区域删除

参数通过 JSON 文件传入（与 infer_segment_autoframe_anime.py 兼容）：
{
  "video_path": str,
  "start_frame": int,
  "expected_frames": int,
  "mask_dir": str,
  "sam2_checkpoint": str,
  "model_cfg": str,
  "yolov8x_path": str,
  "face_conf": float,
  "face_expand": float,
  "yolo_conf": float,
  "max_boxes_per_frame": int,
  "sam_variant": str,
  "keyframe_interval": int,     // Tier 1: 关键帧间隔，默认 15
  "motion_levels_path": str,    // Layer 1: L0 输出的 motion_levels.json 路径；空=退化老逻辑（全 static + keyframe_interval）
  "enable_temporal_stabilize": bool,  // Layer 2A: 光流warp时序稳定（默认 False；需 motion_levels_path 提供 flow_cache）
  "flow_scale": float,          // Layer 2A: flow_cache 相对全分辨率的缩放（默认 0.25）
  "enable_edge_refine": bool,   // Tier 2: 是否启用边缘精修，默认 True
}
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

import cv2
import numpy as np
import torch

from core.torch_runtime import get_device, infer_ctx

# Layer 2A: RIFE warplayer（CUDA 双线性 warp），失败则禁用稳定（向后兼容）
try:
    sys.path.append(str(Path(__file__).resolve().parent.parent / "external" / "rife" / "model"))
    from warplayer import warp as _rife_warp  # type: ignore
except Exception:
    _rife_warp = None

# Layer 2A 融合权重（方案 §4A.3）: (w_raw, w_prev)
STAB_WEIGHTS = {"static": (0.5, 0.5), "mid": (0.6, 0.4), "fast": (0.75, 0.25)}


# ---------- utilities ----------
def imread_unicode(p: str) -> np.ndarray:
    if not Path(p).exists():
        return None
    buf = np.fromfile(p, dtype=np.uint8)
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def imwrite_unicode(p: str, img: np.ndarray, ext: str = ".png") -> bool:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    buf.tofile(p)
    return True


def clip_box(box: list[float], w: int, h: int) -> list[int]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, int(round(x1))))
    y1 = max(0, min(h - 1, int(round(y1))))
    x2 = max(0, min(w, int(round(x2))))
    y2 = max(0, min(h, int(round(y2))))
    if x2 <= x1 or y2 <= y1:
        return []
    return [x1, y1, x2, y2]


def nms_boxes(boxes: list[list[float]], iou_thr: float = 0.5) -> list[int]:
    if not boxes:
        return []
    boxes_np = np.array(boxes, dtype=np.float64)
    x1 = boxes_np[:, 0]; y1 = boxes_np[:, 1]; x2 = boxes_np[:, 2]; y2 = boxes_np[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = areas.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        ww = np.maximum(0.0, xx2 - xx1)
        hh = np.maximum(0.0, yy2 - yy1)
        inter = ww * hh
        union = areas[i] + areas[order[1:]] - inter
        iou = np.where(union > 0, inter / union, 0.0)
        inds = np.where(iou <= iou_thr)[0]
        order = order[inds + 1]
    return keep


def lab_saliency_boxes(frame_bgr: np.ndarray, k: int = 3, min_area_ratio: float = 0.005) -> list[list[int]]:
    h, w = frame_bgr.shape[:2]
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    dev_a = np.abs(a.astype(np.int16) - 128)
    dev_b = np.abs(b.astype(np.int16) - 128)
    sal = np.maximum(dev_a, dev_b).astype(np.uint8)
    sal = cv2.GaussianBlur(sal, (5, 5), 0)
    _, mask = cv2.threshold(sal, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    areas = stats[:, cv2.CC_STAT_AREA]
    min_area = int(min_area_ratio * h * w)
    idx = [i for i in range(1, n) if areas[i] >= min_area]
    idx.sort(key=lambda i: areas[i], reverse=True)
    result = []
    for i in idx[:k]:
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        result.append([int(x), int(y), int(x + bw), int(y + bh)])
    return result


# ---------- Tier 2: edge refinement ----------
# Layer 3 (M3): 按运动级别自适应参数表（方案 §5.1；Guided radius 以代码现状 4 为准，方案原文引用行号已过时）
PARAM_TABLE = {
    # level: (guided_radius, close_kernel, close_iters, open_kernel, open_iters, feather_ksize, min_area)
    "static": (4, 3, 2, 2, 1, 7, 500),
    "mid":    (4, 5, 3, 2, 1, 5, 400),
    "fast":   (4, 5, 3, 2, 1, 3, 300),
}


def refine_mask_edge(mask: np.ndarray, guide_bgr: np.ndarray, motion_level: str = "static") -> np.ndarray:
    """
    Tier 2 边缘精修链（Layer 3 按运动级别自适应参数）：
    1. Guided Filter（或 jointBilateralFilter fallback）以原图为引导锐化 mask 边缘
    2. 形态学 Close（static 3x3x2 / mid-fast 5x5x3）填补小空洞与快速段撕裂
    3. 形态学 Open（2x2 椭圆核）去除孤立噪点
    4. Alpha 羽化（static 7x7≈3px / mid 5x5≈2px / fast 3x3≈1px）
    5. 连通域清理：面积 < min_area（static 500 / mid 400 / fast 300）的独立区域删除
    """
    _r, _ck, _ci, _ok, _oi, _fk, _min_area = PARAM_TABLE.get(motion_level, PARAM_TABLE["static"])
    h, w = mask.shape[:2]

    # 0. 软输入二值化：stab 融合输出为软 alpha（0-255 连续值）；guided filter + threshold(127)
    #    假设二值输入（2026-08-14 M4 实证：软 mask 大片 127 附近值 → guided 输出 p50=73 → 阈值塌缩清空）
    mask = np.where(mask > 64, 255, 0).astype(np.uint8)

    # 1. Guided Filter（纯 numpy 实现，不依赖 opencv-contrib）
    guide_gray = cv2.cvtColor(guide_bgr, cv2.COLOR_BGR2GRAY)
    guide_f = guide_gray.astype(np.float32) / 255.0
    src_f = mask.astype(np.float32) / 255.0
    radius = _r
    eps = 0.01
    ksize = (radius * 2 + 1, radius * 2 + 1)
    mean_I = cv2.boxFilter(guide_f, cv2.CV_32F, ksize)
    mean_p = cv2.boxFilter(src_f, cv2.CV_32F, ksize)
    mean_Ip = cv2.boxFilter(guide_f * src_f, cv2.CV_32F, ksize)
    mean_II = cv2.boxFilter(guide_f * guide_f, cv2.CV_32F, ksize)
    cov_Ip = mean_Ip - mean_I * mean_p
    var_I = mean_II - mean_I * mean_I
    a_coef = cov_Ip / (var_I + eps)
    b_coef = mean_p - a_coef * mean_I
    mean_a = cv2.boxFilter(a_coef, cv2.CV_32F, ksize)
    mean_b = cv2.boxFilter(b_coef, cv2.CV_32F, ksize)
    mask_guided = (mean_a * guide_f + mean_b) * 255.0
    mask_u8 = np.clip(mask_guided, 0, 255).astype(np.uint8)

    # 二值化（Guided Filter 输出是浮点）
    _, mask_bin = cv2.threshold(mask_u8, 127, 255, cv2.THRESH_BINARY)

    # 2. 形态学 Close：填补内部小空洞（mid/fast 更大核补快速段撕裂）
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_ck, _ck))
    closed = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k_close, iterations=_ci)

    # 3. 形态学 Open：去除孤立噪点
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_ok, _ok))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, k_open, iterations=_oi)

    # 4. 大空洞填充：flood fill 从边界填充外部，取反得到「前景+内部空洞」，减去 opened 得到「仅内部空洞」
    # filled: flood fill (0,0) → 外部背景=255，内部前景/空洞区域保持原值(0/255)
    filled_bg = opened.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(filled_bg, flood_mask, (0, 0), 255)
    # 仅内部空洞 = (所有非背景区域) - (已有前景)
    holes_only = cv2.bitwise_and(cv2.bitwise_not(filled_bg), cv2.bitwise_not(opened))
    # 限制空洞面积：只填 >50px 的闭合空洞，避免填掉背景细缝
    n_h, labels_h, stats_h, _ = cv2.connectedComponentsWithStats(holes_only, connectivity=4)
    valid_holes = np.zeros_like(holes_only)
    for i in range(1, n_h):
        if 50 < stats_h[i, cv2.CC_STAT_AREA] < 0.1 * h * w:  # 上限10%避免大背景被误填
            valid_holes[labels_h == i] = 255
    final_mask = cv2.bitwise_or(opened, valid_holes)

    # 5. 连通域清理：删除 < min_area 的碎片（快运动降低阈值避免误删边缘小碎片）
    n_cc, labels_cc, stats_cc, _ = cv2.connectedComponentsWithStats(final_mask, connectivity=8)
    cleaned = np.zeros_like(final_mask)
    for i in range(1, n_cc):
        if stats_cc[i, cv2.CC_STAT_AREA] >= _min_area:
            cleaned[labels_cc == i] = 255

    # 6. Alpha 羽化：static 3px 柔边 / mid 2px / fast 1px 硬边防糊
    alpha = cv2.GaussianBlur(cleaned, (_fk, _fk), 0)

    return alpha


# ---------- Layer 2A: temporal stabilization (M2) ----------
def stabilize_temporal(mask_raw: np.ndarray, prev_stab: np.ndarray | None,
                       flow_full: np.ndarray, level: str, device: str = "cuda") -> np.ndarray:
    """光流 warp 时序稳定（方案 §4A.3）：0.6×Mask_N + 0.4×Warp(Mask_{N-1}→N)。

    flow_full: 全分辨率 (H, W, 2) float32 光流（像素位移）。
    权重按 level: static(0.5/0.5) mid(0.6/0.4) fast(0.75/0.25)。
    """
    if prev_stab is None or _rife_warp is None:
        return mask_raw
    h, w = mask_raw.shape[:2]
    flow_t = torch.from_numpy(flow_full).permute(2, 0, 1).unsqueeze(0).float().to(device)
    prev_t = torch.from_numpy(prev_stab.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(device)
    with infer_ctx(device):
        warped = _rife_warp(prev_t, flow_t).squeeze(0).squeeze(0).cpu().numpy()  # float 0~255
    w_raw, w_prev = STAB_WEIGHTS.get(level, (0.6, 0.4))
    fused = np.clip(w_raw * mask_raw.astype(np.float32) + w_prev * warped, 0, 255)
    return fused.astype(np.uint8)


# ---------- detectors (reused from original) ----------
class HaarFaceDetector:
    CASCADE_NAMES = [
        "haarcascade_frontalface_default.xml",
        "haarcascade_frontalface_alt.xml",
        "haarcascade_frontalface_alt2.xml",
        "haarcascade_profileface.xml",
        "lbpcascade_frontalface.xml",
        "lbpcascade_animeface.xml",
    ]

    @staticmethod
    def _discover_xml_dirs() -> list[str]:
        dirs: list[str] = []
        try:
            d = cv2.data.haarcascades
            if d and Path(d).is_dir():
                dirs.append(d)
        except Exception:
            pass
        roots: list[Path] = []
        for root_path in [r"D:\AE-Work", r"C:\Users\Administrator\AppData\Local\Programs\Python",
                          Path.home() / "AppData" / "Local"]:
            try:
                p = Path(root_path)
                if p.is_dir():
                    roots.append(p)
            except Exception:
                continue
        seen: set[str] = set()
        for r in roots:
            try:
                for p in r.rglob("haarcascade_frontalface_default.xml"):
                    parent = str(p.parent)
                    if parent not in seen:
                        seen.add(parent)
                        dirs.append(parent)
                        break
            except Exception:
                pass
        return dirs

    def __init__(self, conf: float = 0.35, expand: float = 4.0):
        self.expand = expand
        self._cascades: list[tuple[str, cv2.CascadeClassifier]] = []
        search_dirs = self._discover_xml_dirs()
        found: set[str] = set()
        for d in search_dirs:
            dp = Path(d)
            if not dp.is_dir():
                continue
            for name in list(set(self.CASCADE_NAMES) - found):
                p = dp / name
                try:
                    if p.exists():
                        c = cv2.CascadeClassifier(str(p))
                        if not c.empty():
                            self._cascades.append((name, c))
                            found.add(name)
                except Exception:
                    pass
        print(f"[FACE] {len(self._cascades)} cascade(s) loaded, expand={expand}", file=sys.stderr)

    def ok(self) -> bool:
        return len(self._cascades) > 0

    def detect(self, frame_bgr: np.ndarray) -> list[list[int]]:
        if not self._cascades:
            return []
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
        except Exception:
            pass
        out = []
        seen: set[tuple[int, int, int, int]] = set()
        for name, cas in self._cascades:
            try:
                if "lbp" in name:
                    faces = cas.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(24, 24))
                else:
                    faces = cas.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
            except Exception:
                continue
            for (fx, fy, fw, fh) in faces:
                fw = max(1, int(fw)); fh = max(1, int(fh))
                fcx = fx + fw * 0.5
                fcy = fy + fh * 0.5
                new_cy = fcy + 0.5 * fh
                bw = fw * self.expand
                bh = fh * self.expand
                bx1 = fcx - bw * 0.5; by1 = new_cy - bh * 0.5
                bx2 = fcx + bw * 0.5; by2 = new_cy + bh * 0.5
                cb = clip_box([bx1, by1, bx2, by2], w, h)
                if cb:
                    key = (cb[0], cb[1], cb[2], cb[3])
                    if key not in seen:
                        seen.add(key)
                        out.append(cb)
        return out


class YOLOFallbackDetector:
    def __init__(self, model_path: str, conf: float = 0.05):
        self.conf = conf
        self._yolo = None
        try:
            from ultralytics import YOLO
            self._yolo = YOLO(model_path, verbose=False)
            print(f"[YOLO] loaded {model_path}, conf={conf}", file=sys.stderr)
        except Exception as e:
            print(f"[YOLO] init FAIL: {e}", file=sys.stderr)

    def ok(self) -> bool:
        return self._yolo is not None

    def detect(self, frame_bgr: np.ndarray) -> list[list[int]]:
        if self._yolo is None:
            return []
        h, w = frame_bgr.shape[:2]
        try:
            res = self._yolo(frame_bgr, conf=self.conf, verbose=False, max_det=30, iou=0.6)
        except Exception:
            return []
        out = []
        for r in res:
            if r.boxes is None:
                continue
            boxes = r.boxes.xyxy.cpu().numpy() if hasattr(r.boxes, "xyxy") else None
            if boxes is None:
                continue
            for i in range(boxes.shape[0]):
                b = boxes[i]
                area = (float(b[2]) - float(b[0])) * (float(b[3]) - float(b[1]))
                if area < 0.0001 * h * w:
                    continue
                cb = clip_box([float(b[0]), float(b[1]), float(b[2]), float(b[3])], w, h)
                if cb:
                    out.append(cb)
        return out


# ---------- detection helper ----------
def detect_boxes_on_frame(frame_bgr: np.ndarray, face_det: HaarFaceDetector,
                          yolo_det: YOLOFallbackDetector, max_boxes: int = 5) -> list[list[int]]:
    """运行三检测器融合，返回 NMS 合并后的 box 列表。"""
    face_boxes = face_det.detect(frame_bgr) if face_det.ok() else []
    yolo_boxes = yolo_det.detect(frame_bgr) if yolo_det.ok() else []
    sal_boxes = []
    try:
        sal_boxes = lab_saliency_boxes(frame_bgr, k=5, min_area_ratio=0.003)
    except Exception:
        pass

    all_boxes: list[list[int]] = []
    all_boxes.extend(face_boxes)
    all_boxes.extend(yolo_boxes)
    all_boxes.extend(sal_boxes)
    keep = nms_boxes(all_boxes, iou_thr=0.5)
    boxes = [all_boxes[i] for i in keep][:max_boxes]
    return boxes


# ---------- SAM2 builders ----------
def _resolve_config(params: dict, variant: str) -> str:
    ckpt_name = Path(params["sam2_checkpoint"]).name.lower()
    if "sam2.1_" in ckpt_name:
        ver_prefix = "sam2.1"
    else:
        ver_prefix = "sam2"
    suffix_map = {"large": "l.yaml", "base_plus": "b+.yaml", "small": "s.yaml", "tiny": "t.yaml"}
    suffix = suffix_map.get(variant, "l.yaml")
    explicit = (params.get("model_cfg") or "").strip()
    if explicit and explicit.endswith((".yaml", ".yml")):
        if "/" not in explicit and "\\" not in explicit:
            if explicit.startswith("sam2.1_"):
                return f"configs/sam2.1/{explicit}"
            elif explicit.startswith("sam2_"):
                return f"configs/sam2/{explicit}"
            else:
                return f"configs/{ver_prefix}/{explicit}"
        elif explicit.startswith("sam2/") or explicit.startswith("sam2.1/"):
            return f"configs/{explicit}"
        else:
            return explicit
    return f"configs/{ver_prefix}/{ver_prefix}_hiera_{suffix}"


def build_image_predictor(params: dict):
    """构建 SAM2 单帧 predictor（用于关键帧检测和回退）。"""
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    variant = params.get("sam_variant", "large")
    config_file = _resolve_config(params, variant)
    device = get_device()
    print(f"[SAM2-IMG] config={config_file} variant={variant} device={device}", file=sys.stderr)
    model = build_sam2(config_file=config_file, ckpt_path=params["sam2_checkpoint"],
                       device=device, mode="eval", apply_postprocessing=False)
    return SAM2ImagePredictor(model)


def build_video_predictor(params: dict):
    """构建 SAM2 video predictor（用于传播模式）。"""
    import torch
    from sam2.build_sam import build_sam2_video_predictor

    variant = params.get("sam_variant", "large")
    config_file = _resolve_config(params, variant)
    device = get_device()
    print(f"[SAM2-VID] config={config_file} variant={variant} device={device}", file=sys.stderr)
    return build_sam2_video_predictor(config_file=config_file, ckpt_path=params["sam2_checkpoint"],
                                      device=device, mode="eval")


def sam_single_frame_predict(predictor, frame_bgr: np.ndarray, boxes: list[list[int]],
                             top_k: int = 1, max_area_ratio: float = 0.40) -> np.ndarray:
    """单帧 SAM2 分割（用于关键帧和回退）。
    精度优先约束（2026-08-14 用户反馈糊块后校准）：
      top_k=1: 只取最大检测框（多框合并=假阳性糊块根源）
      max_area_ratio=0.40: mask 面积超 40% 视为传播伪影 → 拒绝输出空
    """
    h, w = frame_bgr.shape[:2]
    if not boxes:
        return np.zeros((h, w), dtype=np.uint8)
    if top_k and len(boxes) > top_k:
        boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)[:top_k]
    predictor.set_image(frame_bgr)
    merged = np.zeros((h, w), dtype=np.uint8)
    for box in boxes:
        try:
            mask_res, scores, _ = predictor.predict(
                box=np.array([box[0], box[1], box[2], box[3]], dtype=np.float32),
                multimask_output=True,
            )
            if mask_res is None or len(mask_res) == 0:
                continue
            best_i = int(np.argmax(np.asarray(scores).reshape(-1)))
            m = (mask_res[best_i] > 0.0).astype(np.uint8) * 255
            merged = cv2.bitwise_or(merged, m)
        except Exception as e:
            print(f"[SAM-IMG] predict err: {e}", file=sys.stderr)
    if max_area_ratio and float(np.count_nonzero(merged)) / (h * w) > max_area_ratio:
        return np.zeros((h, w), dtype=np.uint8)  # 糊块拒绝
    return merged


# ---------- main pipeline ----------
def run(params: dict) -> dict:
    video_path = params["video_path"]
    start_frame = int(params["start_frame"])
    expected = int(params.get("expected_frames", 0))
    mask_dir = Path(params["mask_dir"])
    mask_dir.mkdir(parents=True, exist_ok=True)
    max_boxes = int(params.get("max_boxes_per_frame", 5))
    keyframe_interval = int(params.get("keyframe_interval", 15))
    enable_edge_refine = bool(params.get("enable_edge_refine", True))

    # detectors
    face_det = HaarFaceDetector(
        conf=float(params.get("face_conf", 0.35)),
        expand=float(params.get("face_expand", 4.0)),
    )
    yolo_det = YOLOFallbackDetector(
        model_path=params["yolov8x_path"],
        conf=float(params.get("yolo_conf", 0.3)),  # 精度优先：0.3（原 0.05 假阳性糊块，2026-08-14 校准）
    )

    # SAM predictors (video predictor only for memory efficiency; image predictor lazy)
    _img_predictor_holder = {"p": None}

    def get_img_predictor_lazy():
        if _img_predictor_holder["p"] is None:
            print("[IMG-PRED] lazy constructing (first fallback)...", file=sys.stderr)
            _img_predictor_holder["p"] = build_image_predictor(params)
        return _img_predictor_holder["p"]

    video_predictor = build_video_predictor(params)
    print("[SAM2] loaded ONLY video predictor (image predictor will lazy build if fallback needed)", file=sys.stderr)

    # FP16 autocast
    use_fp16 = True
    amp_ctx = None
    if use_fp16:
        try:
            import torch
            if torch.cuda.is_available():
                amp_ctx = torch.autocast(device_type="cuda", dtype=torch.float16)
                print("[FP16] autocast enabled", file=sys.stderr)
        except Exception:
            amp_ctx = None

    # 读取视频帧
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        total_frames = expected
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        print(f"[VIDEO] seek to {start_frame}, total={total_frames}", file=sys.stderr)

    # 读取所有需要的帧到内存（段长通常 500 帧，1280x720 ~ 1.3GB，可接受）
    frames: list[np.ndarray] = []
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
        if expected and len(frames) >= expected:
            break
    cap.release()
    N = len(frames)
    H, W = frames[0].shape[:2] if N > 0 else (0, 0)
    print(f"[VIDEO] read {N} frames {W}x{H}", file=sys.stderr)

    if N == 0:
        return {"status": "fail", "error": "no frames read"}

    # ===== Layer 1: motion routing (M1) =====
    motion_levels_path = str(params.get("motion_levels_path") or "")
    levels: list[str] = []
    if motion_levels_path and os.path.exists(motion_levels_path):
        try:
            with open(motion_levels_path, "r", encoding="utf-8") as f:
                _ml = json.load(f)
            _lv = _ml.get("motion_level") or []
            if len(_lv) >= N:
                levels = [str(x) for x in _lv[:N]]
            print(f"[MOTION-ROUTE] loaded {len(levels)} levels from {motion_levels_path}", file=sys.stderr)
        except Exception as e:
            print(f"[MOTION-ROUTE] load FAIL: {e} -> degrade uniform", file=sys.stderr)
            levels = []
    if not levels:
        levels = ["static"] * N

    KI_TABLE = {"static": 8, "mid": 4, "fast": None}          # 方案 §3.2
    THR_TABLE = {"static": 0.3, "mid": 0.4, "fast": 1.0}      # 方案 §3.2

    def level_of(fi: int) -> str:
        return levels[fi] if 0 <= fi < len(levels) else "static"

    # —— 路由模式序列日志：video ↔ auto_frame 切换计数（M1-B 证据）
    route_log_lines: list[str] = []
    prev_route_mode: str | None = None
    mode_switches = 0
    for fi in range(N):
        lv = level_of(fi)
        mode = "auto_frame" if lv == "fast" else "video"
        if mode != prev_route_mode:
            route_log_lines.append(f"[MOTION_ROUTE] fi={fi} level={lv} mode={mode}")
            if prev_route_mode is not None:
                mode_switches += 1
            prev_route_mode = mode
    for _ln in route_log_lines:
        print(_ln, file=sys.stderr)
    print(f"[MOTION_ROUTE] total_mode_switches={mode_switches} fast_frames={levels.count('fast')} "
          f"mid_frames={levels.count('mid')} static_frames={levels.count('static')}", file=sys.stderr)
    routed_fast_count = 0
    routed_weak_frames = 0  # 弱锚点段（原生注入<10%）整段路由 auto_frame 的帧数（QC 校准）

    # ===== Layer 2A: temporal stabilization setup (M2) =====
    enable_temporal_stabilize = bool(params.get("enable_temporal_stabilize", False))
    flow_scale = float(params.get("flow_scale", 0.25))
    flow_cache_dir = ""
    flow_offset = 0
    if motion_levels_path and os.path.exists(motion_levels_path):
        try:
            with open(motion_levels_path, "r", encoding="utf-8") as _f:
                _ml = json.load(_f)
                flow_cache_dir = str(_ml.get("flow_cache_dir") or "")
                # 全片 flow_cache 用全局帧号命名时，段内 idx 需加偏移（整片生产化多段支持）
                flow_offset = int(_ml.get("flow_offset") or 0)
        except Exception:
            flow_cache_dir = ""
    if enable_temporal_stabilize and (_rife_warp is None or not flow_cache_dir or not os.path.isdir(flow_cache_dir)):
        print(f"[STAB] disabled: warplayer={_rife_warp is not None} flow_cache_dir={flow_cache_dir}",
              file=sys.stderr)
        enable_temporal_stabilize = False
    _flow_cache: dict[int, np.ndarray] = {}

    def _load_flow_full(idx: int) -> np.ndarray:
        """加载段内 idx 的光流并放大到全分辨率（缓存）。flow_cache[idx+flow_offset] = flow(idx-1→idx)。"""
        if idx in _flow_cache:
            return _flow_cache[idx]
        flow_p = Path(flow_cache_dir) / f"{idx + flow_offset:05d}.npy"
        if not flow_p.exists():
            flow = np.zeros((H, W, 2), dtype=np.float32)
        else:
            flow_small = np.load(str(flow_p))
            if flow_small.shape[0] != H or flow_small.shape[1] != W:
                flow = cv2.resize(flow_small, (W, H), interpolation=cv2.INTER_LINEAR) * (1.0 / max(flow_scale, 1e-3))
            else:
                flow = flow_small
            flow = flow.astype(np.float32)
        _flow_cache[idx] = flow
        return flow

    # ===== Tier 1: SAM2 Video 传播模式 =====
    print(f"\n=== Tier 1: SAM2 Video Propagation (keyframe_interval={keyframe_interval}) ===", file=sys.stderr)

    # 1. 保存帧为 JPEG 到临时目录（SAM2 video predictor 需要）
    tmp_dir = Path(tempfile.mkdtemp(prefix="sam2vid_"))
    print(f"[TMP] frame dir: {tmp_dir}", file=sys.stderr)
    for i in range(N):
        jpg_path = tmp_dir / f"{i:05d}.jpg"
        cv2.imwrite(str(jpg_path), frames[i], [cv2.IMWRITE_JPEG_QUALITY, 95])

    # 2. 初始化 video predictor state
    state = video_predictor.init_state(
        video_path=str(tmp_dir),
        offload_video_to_cpu=True,
        async_loading_frames=False,
    )
    print(f"[SAM2-VID] state initialized for {N} frames", file=sys.stderr)

    # 3. 关键帧检测 + 注入
    # 关键优化：不构建 SAM2 image predictor（节省 ~1.7GB GPU 显存，避免 OOM）
    # 改用 video predictor.add_new_points_or_box() 的 out_mask 作为关键帧 mask
    # 消融实验 E4 实锤：add_new_points_or_box 返回的 mask 质量等价于 image predictor
    # 关键帧调度：按运动级别自适应 ki（Layer 1，方案 §3.2）；fast 帧不设 KF 锚点（PIT-1）
    # QC 校准(2026-08-13)：离开 fast 段（场景切/闪切）后的首个 static/mid 帧必须重锚定 KF，
    #   否则传播从切点前锚点继续 → 跨切必崩（area→0% → fallback 风暴）
    if any(lv != "static" for lv in levels):
        _kfs: list[int] = []
        _i = 0
        _just_left_fast = False
        while _i < N:
            _lv = level_of(_i)
            _ki = KI_TABLE.get(_lv, keyframe_interval)
            if _ki is None:  # fast: 逐帧 auto_frame，不注入传播锚点
                _just_left_fast = True
                _i += 1
                continue
            if _just_left_fast:
                # 切点/快运动段之后重锚定：当前帧就是新 KF
                _kfs.append(_i)
                _i += max(1, int(_ki))
                _just_left_fast = False
                continue
            _kfs.append(_i)
            _i += max(1, int(_ki))
        keyframe_indices = sorted(set(_kfs)) or [0]
        print(f"[KEYFRAME] motion-adaptive {len(keyframe_indices)} keyframes (KI_TABLE={KI_TABLE}, post-fast re-anchor)", file=sys.stderr)
    else:
        keyframe_indices = list(range(0, N, keyframe_interval))
    keyframe_masks: dict[int, np.ndarray] = {}
    keyframe_boxes: dict[int, list[list[int]]] = {}
    # —— 新增：记录每个 KF 的 video predictor 原生注入比例（不含 img_pred fallback 影响）
    kf_video_inject_ratios: dict[int, float] = {}
    kf_quality_log: dict[int, float] = {}

    print(f"[KEYFRAME] {len(keyframe_indices)} keyframes: {keyframe_indices[:10]}... (no img_predictor)", file=sys.stderr)

    for kf_idx in keyframe_indices:
        frame = frames[kf_idx]
        fused_boxes = detect_boxes_on_frame(frame, face_det, yolo_det, max_boxes)
        # ================================================================
        # 注入策略：YOLO pure ∪ fused 去重，按面积降序取 Top-N（默认 N=5），
        # 逐个尝试 add_new_points_or_box，保留获得 out_mask nz 最多的那个。
        # (避免：单一盒贴边/不完整→SAM2 返回-1024 空 mask)
        # ================================================================
        yolo_boxes_pure = yolo_det.detect(frame) if yolo_det.ok() else []
        # 去重合并
        def _box_tuple(b): return (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
        seen = set()
        merged_candidates: list[list[int]] = []
        for blist in (fused_boxes, yolo_boxes_pure):
            for b in blist:
                t = _box_tuple(b)
                if t in seen:
                    continue
                seen.add(t)
                merged_candidates.append([int(t[0]), int(t[1]), int(t[2]), int(t[3])])
        # 面积降序
        merged_candidates.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
        # 默认盒兜底
        if not merged_candidates:
            cx, cy = W // 2, H // 2
            bw, bh = W // 3, H // 2
            default_box = [cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2]
            cb = clip_box(default_box, W, H)
            if cb:
                merged_candidates = [cb]
                fused_boxes = fused_boxes or [cb]

        keyframe_boxes[kf_idx] = fused_boxes  # fallback auto_frame 仍用融合盒

        # 尝试 Top-N 候选盒（N<=5）找 nz 最大注入
        MAX_TRY_BOXES = 5
        best_nz = -1
        best_box: list[int] = merged_candidates[0]
        best_kf_mask: np.ndarray | None = None
        tried_stats = []
        for try_box in merged_candidates[:MAX_TRY_BOXES]:
            box_t = torch.tensor(try_box, dtype=torch.float32, device="cpu").reshape(1, 4)
            try:
                if amp_ctx is not None:
                    with amp_ctx:
                        _, _, out_mask_try = video_predictor.add_new_points_or_box(
                            state, frame_idx=kf_idx, obj_id=1, box=box_t,
                            clear_old_points=True, normalize_coords=False)
                else:
                    _, _, out_mask_try = video_predictor.add_new_points_or_box(
                        state, frame_idx=kf_idx, obj_id=1, box=box_t,
                        clear_old_points=True, normalize_coords=False)
                if hasattr(out_mask_try, 'cpu'):
                    om_try = out_mask_try.cpu().numpy()
                else:
                    om_try = np.array(out_mask_try)
                obj_idx = 0
                if om_try.shape[0] > obj_idx:
                    m2 = om_try[obj_idx]
                    if m2.ndim == 3 and m2.shape[0] == 1:
                        m2 = m2[0]
                    nz_try = int(np.count_nonzero(m2 > 0.0))
                    tried_stats.append((try_box, nz_try, float(m2.min()), float(m2.max())))
                    if nz_try > best_nz:
                        best_nz = nz_try
                        best_box = try_box
                        best_kf_mask = ((m2 > 0.0).astype(np.uint8) * 255).copy()
            except Exception as e_try:
                tried_stats.append((try_box, -1, 0.0, 0.0))
                print(f"  [KF {kf_idx}] try_box={try_box} err: {e_try}", file=sys.stderr)
        inject_nonzero = max(0, best_nz)
        kf_mask_from_video = best_kf_mask if best_kf_mask is not None else np.zeros((H, W), dtype=np.uint8)
        if best_nz < 0:
            inject_nonzero = 0
            kf_mask_from_video = np.zeros((H, W), dtype=np.uint8)
        pure_areas = sorted([(b[2]-b[0])*(b[3]-b[1]) for b in yolo_boxes_pure], reverse=True)[:5] if yolo_boxes_pure else []
        fused_areas = sorted([(b[2]-b[0])*(b[3]-b[1]) for b in fused_boxes], reverse=True)[:5] if fused_boxes else []
        ts = ", ".join([f"({b} nz={n} min/max={mn:.1f}/{mx:.1f})" for (b, n, mn, mx) in tried_stats[:4]])
        print(f"  [KF {kf_idx}] yolo_pure_N={len(yolo_boxes_pure)}, fused_N={len(fused_boxes)}\n"
              f"    pure_top5_area={pure_areas}\n    fused_top5_area={fused_areas}\n"
              f"    tried={ts}\n    WIN best_box={best_box} nz={inject_nonzero} ({inject_nonzero/(W*H):.2%})",
              file=sys.stderr)
        # 上面的 Top-N 候选盒尝试已经设置好了 best_box / inject_nonzero / kf_mask_from_video
        # 且最后一次尝试仍以 best_box 注入：需要保证最终 video predictor 内 obj_id=1
        # 的 prompt 是我们选出来的最佳 box，这样 propagation 从最优质锚点出发。
        # （上面循环中最后注入的是 tried_stats[-1] 的 box，不一定是 WINNER box，
        #  因此显式重注入 WINNER box，clear_old_points=True。）
        if inject_nonzero > 0:
            winner_box_t = torch.tensor(best_box, dtype=torch.float32, device="cpu").reshape(1, 4)
            try:
                if amp_ctx is not None:
                    with amp_ctx:
                        video_predictor.add_new_points_or_box(
                            state, frame_idx=kf_idx, obj_id=1, box=winner_box_t,
                            clear_old_points=True, normalize_coords=False)
                else:
                    video_predictor.add_new_points_or_box(
                        state, frame_idx=kf_idx, obj_id=1, box=winner_box_t,
                        clear_old_points=True, normalize_coords=False)
            except Exception:
                pass

        # 如果 video predictor 注入得到 mask 在 [1%, 40%] 合理区间，用它；否则 fallback 到 image predictor 单帧
        # （2026-08-14 精度校准：video 注入全幅 mask=糊块，需同样面积约束）
        kf_area_ratio = inject_nonzero / (W * H)
        # —— 保存「video predictor 原生注入比例」（用于修改 A 的 DYN-KF strong 判断，不受 img_pred fallback 干扰）
        kf_video_inject_ratios[kf_idx] = kf_area_ratio
        if 0.01 <= kf_area_ratio <= 0.40:
            keyframe_masks[kf_idx] = kf_mask_from_video
        else:
            print(f"  [KF {kf_idx}] video mask out of [1%,40%] ({kf_area_ratio:.2%}), fallback img_predictor", file=sys.stderr)
            img_pred = get_img_predictor_lazy()
            if amp_ctx is not None:
                with amp_ctx:
                    keyframe_masks[kf_idx] = sam_single_frame_predict(img_pred, frame, fused_boxes)
            else:
                keyframe_masks[kf_idx] = sam_single_frame_predict(img_pred, frame, fused_boxes)

    # ========================================================================
    # 修改 A：动态加密关键帧
    # 扫描关键帧序列，若相邻「strong KF (video注入>=3%)」之间间隔 > 原 keyframe_interval*1.5，
    # 且中间存在 weak KF，则在 gap 中点递归补充注入新 KF，直到无长 gap 或 间隔<=3 帧。
    # 解决：KF105/KF135 video 注入完全失败 → 相邻 strong KF 间隔过大 → 传播中途崩溃。
    # 修正 v2：用 kf_video_inject_ratios（video 原生注入）判断 strong，
    #   不用最终 keyframe_masks 面积（img_pred fallback 后都很大，会导致误判 strong）。
    # ========================================================================
    WEAK_KF_VIDEO_THRESHOLD = 0.03  # video 注入 <3% 视为 weak（需要 img_pred fallback 的那种）
    STRONG_KF_VIDEO_THRESHOLD = 0.03  # >=3% 视为 strong（video 注入成功）
    MAX_GAP_RATIO = 1.5  # 相邻 strong KF 间隔 > 原 ki*1.5 → 加密

    def is_strong_kf_video(kf_i: int) -> bool:
        """用 video predictor 原生注入比例判断 strong（不含 img_pred fallback 影响）。"""
        return kf_video_inject_ratios.get(kf_i, 0.0) >= STRONG_KF_VIDEO_THRESHOLD

    # —— 找 strong KF 列表（依据 video 原生注入比例），识别过长 gap
    strong_list = sorted([ki for ki in keyframe_indices if is_strong_kf_video(ki)])
    print(f"[DYN-KF] strong KFs (video_inject>={STRONG_KF_VIDEO_THRESHOLD:.0%}): {strong_list}", file=sys.stderr)
    if len(strong_list) >= 2:
        max_allowed_gap = int(keyframe_interval * MAX_GAP_RATIO)
        extra_kfs_to_add: list[int] = []
        for si in range(1, len(strong_list)):
            gap = strong_list[si] - strong_list[si - 1]
            if gap > max_allowed_gap:
                # 在 gap 内均匀插入 ceil(gap / max_allowed_gap) - 1 个中间 KF
                n_insert = (gap + max_allowed_gap - 1) // max_allowed_gap - 1
                for ti in range(1, n_insert + 1):
                    mid_kf = strong_list[si - 1] + (gap * ti) // (n_insert + 1)
                    if (0 <= mid_kf < N and mid_kf not in keyframe_indices
                            and mid_kf not in extra_kfs_to_add
                            and level_of(mid_kf) != "fast"):  # PIT-1: fast 帧不注入传播锚点
                        extra_kfs_to_add.append(mid_kf)
        if extra_kfs_to_add:
            print(f"[DYN-KF] detected long strong gaps, inserting {len(extra_kfs_to_add)} mid keyframes: {extra_kfs_to_add[:10]}...", file=sys.stderr)
            for mid_kf in sorted(extra_kfs_to_add):
                frame = frames[mid_kf]
                fused_boxes_mid = detect_boxes_on_frame(frame, face_det, yolo_det, max_boxes)
                yolo_boxes_pure_mid = yolo_det.detect(frame) if yolo_det.ok() else []
                def _bt(b): return (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
                seen_mid = set()
                merged_mid: list[list[int]] = []
                for bl in (fused_boxes_mid, yolo_boxes_pure_mid):
                    for b in bl:
                        t = _bt(b)
                        if t in seen_mid:
                            continue
                        seen_mid.add(t)
                        merged_mid.append([int(t[0]), int(t[1]), int(t[2]), int(t[3])])
                merged_mid.sort(key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
                if not merged_mid:
                    cx, cy = W // 2, H // 2
                    bw, bh = W // 3, H // 2
                    cb_def = clip_box([cx-bw//2, cy-bh//2, cx+bw//2, cy+bh//2], W, H)
                    if cb_def:
                        merged_mid = [cb_def]
                        fused_boxes_mid = fused_boxes_mid or [cb_def]
                keyframe_boxes[mid_kf] = fused_boxes_mid
                best_nz_m = -1
                best_box_m: list[int] = merged_mid[0]
                best_mask_m: np.ndarray | None = None
                for try_box in merged_mid[:5]:
                    box_t = torch.tensor(try_box, dtype=torch.float32, device="cpu").reshape(1, 4)
                    try:
                        if amp_ctx is not None:
                            with amp_ctx:
                                _, _, om_try = video_predictor.add_new_points_or_box(
                                    state, frame_idx=mid_kf, obj_id=1, box=box_t,
                                    clear_old_points=True, normalize_coords=False)
                        else:
                            _, _, om_try = video_predictor.add_new_points_or_box(
                                state, frame_idx=mid_kf, obj_id=1, box=box_t,
                                clear_old_points=True, normalize_coords=False)
                        if hasattr(om_try, 'cpu'):
                            om_np = om_try.cpu().numpy()
                        else:
                            om_np = np.array(om_try)
                        if om_np.shape[0] > 0:
                            m2 = om_np[0]
                            if m2.ndim == 3 and m2.shape[0] == 1:
                                m2 = m2[0]
                            nz = int(np.count_nonzero(m2 > 0.0))
                            if nz > best_nz_m:
                                best_nz_m = nz
                                best_box_m = try_box
                                best_mask_m = ((m2 > 0.0).astype(np.uint8) * 255).copy()
                    except Exception:
                        pass
                inject_nz_m = max(0, best_nz_m)
                kf_mask_m = best_mask_m if best_mask_m is not None else np.zeros((H, W), dtype=np.uint8)
                if inject_nz_m > 0:
                    wbox_t = torch.tensor(best_box_m, dtype=torch.float32, device="cpu").reshape(1, 4)
                    try:
                        if amp_ctx is not None:
                            with amp_ctx:
                                video_predictor.add_new_points_or_box(
                                    state, frame_idx=mid_kf, obj_id=1, box=wbox_t,
                                    clear_old_points=True, normalize_coords=False)
                        else:
                            video_predictor.add_new_points_or_box(
                                state, frame_idx=mid_kf, obj_id=1, box=wbox_t,
                                clear_old_points=True, normalize_coords=False)
                    except Exception:
                        pass
                ratio_m = inject_nz_m / (W * H)
                # 新 KF 结果：video 注入 >=1% 用 video；否则 img_pred
                if ratio_m >= 0.01:
                    keyframe_masks[mid_kf] = kf_mask_m
                else:
                    print(f"  [DYN-KF {mid_kf}] video too small ({ratio_m:.2%}), use img_pred", file=sys.stderr)
                    img_pred = get_img_predictor_lazy()
                    if amp_ctx is not None:
                        with amp_ctx:
                            keyframe_masks[mid_kf] = sam_single_frame_predict(img_pred, frame, fused_boxes_mid)
                    else:
                        keyframe_masks[mid_kf] = sam_single_frame_predict(img_pred, frame, fused_boxes_mid)
                kf_quality_log[mid_kf] = float(np.count_nonzero(keyframe_masks[mid_kf])) / (W * H)
                keyframe_indices.append(mid_kf)
        keyframe_indices = sorted(set(keyframe_indices))
        print(f"[DYN-KF] final {len(keyframe_indices)} keyframes", file=sys.stderr)

    # 4. 传播（严格复用消融实验 E4 成功模式，立即消费不返回生成器）
    # 修改 B：在 _do_propagate 中加入实时崩溃检测 + 提前 break
    #   逻辑：定位当前帧所在 KF 段（keyframe_indices 中不大于 fi 的最大值对应段），
    #   取该段 KF 的 kf_area。若连续 CONSECUTIVE_COLLAPSE=3 帧 area < kf_area*0.1 且
    #   area < 0.002*W*H，则判定该段传播崩溃 → 提前 break generator 省时间。
    #   （崩溃帧在后面的 fallback 阶段会被自动补全。）
    print(f"\n[PROP] propagating from frame 0... (FP16={amp_ctx is not None})", file=sys.stderr)
    t0_prop = time.time()
    propagated_masks: dict[int, np.ndarray] = {}
    prop_error = None

    # —— 提前构建 KF 段索引（keyframe_indices 已排序），用于 O(1) 定位 fi→seg_start
    sorted_kf = sorted(keyframe_indices)
    kf_areas_for_seg: dict[int, float] = {}
    for ki in sorted_kf:
        km = keyframe_masks.get(ki)
        if km is not None:
            kf_areas_for_seg[ki] = float(np.count_nonzero(km))
        else:
            kf_areas_for_seg[ki] = 0.0
    MIN_AREA_ABS = 0.002 * W * H  # 2‰ 以下视为可能崩溃
    CONSECUTIVE_COLLAPSE = 3
    WEAK_KF_ANCHOR_RATIO = 0.10  # 原生 video 注入 <10% → 弱锚点段 → 整段路由 auto_frame（QC 校准）

    def seg_for_frame(fi: int) -> int:
        """返回 fi 所在段的 seg_start（在 sorted_kf 中左闭右开最近者）。"""
        import bisect
        pos = bisect.bisect_right(sorted_kf, fi) - 1
        if pos < 0:
            return sorted_kf[0] if sorted_kf else 0
        return sorted_kf[pos]

    def _do_propagate():
        results_list = []
        gen = video_predictor.propagate_in_video(state, start_frame_idx=0)
        consec_small = 0
        last_seg_kf_area: float | None = None
        for fi, oids, vm in gen:
            if fi >= N:
                break
            if hasattr(vm, 'cpu'):
                vm_np = vm.cpu().numpy()
            else:
                vm_np = np.array(vm)
            merged = np.zeros((H, W), dtype=np.uint8)
            for idx_in_list, oid in enumerate(oids):
                if idx_in_list >= vm_np.shape[0]:
                    continue
                m = vm_np[idx_in_list]
                if m.ndim == 3 and m.shape[0] == 1:
                    m = m[0]
                merged = cv2.bitwise_or(merged, ((m > 0.0).astype(np.uint8) * 255))
            area_cnt = float(np.count_nonzero(merged))
            area = area_cnt / (W * H)
            if fi < 5 or fi % 50 == 0:
                print(f"  [PROP] f{fi}: objs={oids}, vm_shape={vm_np.shape}, area={area:.2%}", file=sys.stderr)
            results_list.append((fi, merged))

            # —— 修改 B：连续小面积崩溃检测 + 跳过当前段剩余帧（不终止后续段）
            seg_kf = seg_for_frame(fi)
            seg_kf_area = kf_areas_for_seg.get(seg_kf, 0.0)
            seg_kf_area_rel = seg_kf_area / (W * H) if (W * H) > 0 else 0.0
            # 当前帧是否「远小于 KF 质量」：相对比例 <10% 且 绝对比例 <2‰ ，且 KF 本身不是极小 (<0.5%)
            seg_kf_small_ok = seg_kf_area_rel >= 0.005  # KF mask 本身不是特别小才有意义判断崩溃
            if seg_kf_small_ok and (area_cnt < seg_kf_area * 0.1 and area_cnt < MIN_AREA_ABS):
                consec_small += 1
                if consec_small >= CONSECUTIVE_COLLAPSE:
                    # 找到下一段的起始关键帧
                    next_seg_start = None
                    for k in sorted_kf:
                        if k > fi:
                            next_seg_start = k
                            break
                    if next_seg_start is not None:
                        skip_n = next_seg_start - fi - 1
                        print(f"  [PROP-COLLAPSE] f{fi}: {CONSECUTIVE_COLLAPSE} consecutive frames below KF*0.1, "
                              f"skip current segment. (seg_KF={seg_kf}, KF_area={seg_kf_area/(W*H):.2%}, "
                              f"cur_area={area:.2%}, skip {skip_n} frames to f{next_seg_start})", file=sys.stderr)
                        # 跳过当前段剩余帧（丢弃结果，后续会走 fallback 补全）
                        for _ in range(skip_n):
                            try:
                                next(gen)
                            except StopIteration:
                                break
                    else:
                        print(f"  [PROP-COLLAPSE] f{fi}: {CONSECUTIVE_COLLAPSE} consecutive frames below KF*0.1, "
                              f"no more segments, finish. (seg_KF={seg_kf}, cur_area={area:.2%})", file=sys.stderr)
                        break
                    consec_small = 0
            else:
                consec_small = 0
            last_seg_kf_area = seg_kf_area
        return results_list

    try:
        if amp_ctx is not None:
            with amp_ctx:
                prop_results = _do_propagate()
        else:
            prop_results = _do_propagate()
        for fi, merged in prop_results:
            propagated_masks[fi] = merged
        print(f"[PROP] consume done: {len(prop_results)} items (expect {N})", file=sys.stderr)
    except Exception as e:
        prop_error = e
        print(f"[PROP] ABORTED with error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc(file=sys.stderr)

    prop_elapsed = time.time() - t0_prop
    print(f"[PROP] elapsed={prop_elapsed:.1f}s, propagated_masks={len(propagated_masks)}/{N}", file=sys.stderr)
    if prop_error is not None:
        print(f"[PROP] ERROR_HAPPENED: {type(prop_error).__name__}: {prop_error}", file=sys.stderr)

    # 5. 回退检测：传播失败帧用 auto_frame 单帧预测
    # 修改 C：
    #   C1. 面积骤降抑制：上一帧非空 (>0.5%) → 当前帧 < 上一帧*0.2 → 直接触发 fallback（跳变帧）
    #   C2. 传播缺失帧补全：不在 propagated_masks 中的帧（修改 B 早停后遗留）→ 直接 fallback
    #   C3. 关键帧 seg_start 边界用 sorted_kf + bisect 定位，与传播崩溃检测保持一致
    fallback_count = 0
    final_masks: list[np.ndarray] = [np.zeros((H, W), dtype=np.uint8) for _ in range(N)]

    # 先填充传播结果（注意 propagated_masks 可能不全，缺失的留 zeros 后面 fallback）
    for idx in range(N):
        if idx in propagated_masks:
            final_masks[idx] = propagated_masks[idx]

    # —— 预计算每帧面积（用于 C1 跳变检测）
    _frame_areas: list[float] = [0.0] * N
    for idx in range(N):
        _frame_areas[idx] = float(np.count_nonzero(final_masks[idx]))

    # 按 seg_start 遍历，sorted_kf 已排序
    AREA_JUMP_DROP_RATIO = 0.2  # 骤降：当前帧 < 上一帧 * 0.2（下降超过 80%）
    AREA_JUMP_PREV_MIN = 0.005 * W * H  # 上一帧至少 0.5% 画面占比才判定跳变
    BLOB_MAX_RATIO = 0.40  # 精度优先：传播 mask >40% 画面 = 糊块伪影 → 回退精确检测（2026-08-14 校准）
    AREA_JUMP_CURR_MAX = 0.03 * W * H  # 修正：当前帧绝对面积必须 <3% 才判定真崩溃（避免人物缩小误判）
    for seg_idx, seg_start in enumerate(sorted_kf):
        seg_end = min((sorted_kf[seg_idx + 1]) if seg_idx + 1 < len(sorted_kf) else N, N)
        kf_mask = keyframe_masks.get(seg_start)
        if kf_mask is None:
            # 此段无 KF mask 结果，整个段直接 fallback
            for idx in range(seg_start, seg_end):
                boxes = keyframe_boxes.get(seg_start, [])
                if not boxes:
                    boxes = detect_boxes_on_frame(frames[idx], face_det, yolo_det, max_boxes)
                if not boxes:
                    continue
                img_pred = get_img_predictor_lazy()
                if amp_ctx is not None:
                    with amp_ctx:
                        fb_mask = sam_single_frame_predict(img_pred, frames[idx], boxes)
                else:
                    fb_mask = sam_single_frame_predict(img_pred, frames[idx], boxes)
                final_masks[idx] = fb_mask
                fallback_count += 1
            continue
        kf_area = float(np.count_nonzero(kf_mask))
        # seg_start 本身用 KF mask（最高质量）
        final_masks[seg_start] = kf_mask
        _frame_areas[seg_start] = kf_area

        mid_streak = 0  # mid 级别连续命中 KF 比例阈值的帧数（连续 2 帧才触发 fallback，方案 §3.2）
        seg_weak_anchor = kf_video_inject_ratios.get(seg_start, 0.0) < WEAK_KF_ANCHOR_RATIO
        if seg_weak_anchor:
            print(f"  [MOTION_ROUTE] seg={seg_start} weak-anchor "
                  f"(native_inject={kf_video_inject_ratios.get(seg_start, 0.0):.2%}) -> auto_frame segment",
                  file=sys.stderr)
        for idx in range(seg_start, seg_end):
            if idx == seg_start:
                # 已用 KF mask，跳过 fallback
                continue
            lv = level_of(idx)

            # —— Layer 1 路由：fast 帧 或 弱锚点段 → auto_frame 单帧
            #    （PIT-1: 快运动/快切禁止传播；弱锚点段: 原生 video 注入 < WEAK_KF_ANCHOR_RATIO
            #      传播必崩 → 整段确定性路由，不计入失败 fallback）
            if lv == "fast" or seg_weak_anchor:
                boxes = keyframe_boxes.get(seg_start, [])
                if not boxes:
                    boxes = detect_boxes_on_frame(frames[idx], face_det, yolo_det, max_boxes)
                if boxes:
                    img_pred = get_img_predictor_lazy()
                    if amp_ctx is not None:
                        with amp_ctx:
                            fb_mask = sam_single_frame_predict(img_pred, frames[idx], boxes)
                    else:
                        fb_mask = sam_single_frame_predict(img_pred, frames[idx], boxes)
                else:
                    fb_mask = np.zeros((H, W), dtype=np.uint8)
                final_masks[idx] = fb_mask
                _frame_areas[idx] = float(np.count_nonzero(fb_mask))
                if lv == "fast":
                    routed_fast_count += 1
                else:
                    routed_weak_frames += 1
                continue

            prop_mask = final_masks[idx]
            prop_area = _frame_areas[idx]
            prev_area = _frame_areas[idx - 1] if idx > 0 else 0.0

            # —— C1：面积骤降抑制（上一帧正常，这帧突然掉 80%+，且当前帧绝对面积 <3% → 真崩溃）
            is_jump_failure = (
                prev_area >= AREA_JUMP_PREV_MIN and
                prop_area < prev_area * AREA_JUMP_DROP_RATIO and
                prop_area < AREA_JUMP_CURR_MAX
            )
            # —— C2：传播缺失（propagated_masks 中没有这帧 → 视为崩溃）
            is_missing_propagation = idx not in propagated_masks
            # —— 原有判定：mask 面积相对 KF 过小
            # 修正 D：weak KF（video 注入<3%）的 kf_area 来自 img_pred fallback，通常很大，
            #   但 SAM2 内部缺少真实锚点注入 → 传播结果相对 KF 偏小是预期内的，不是崩溃。
            #   仅对 strong KF（video 注入>=3%）段启用 kf_ratio_fail 判定。
            seg_is_strong_kf = kf_video_inject_ratios.get(seg_start, 0.0) >= STRONG_KF_VIDEO_THRESHOLD
            # —— Layer 1：按 level 的 KF 比例阈值（THR_TABLE）；mid 需连续 2 帧命中才触发（方案 §3.2）
            kf_ratio_thr = THR_TABLE.get(lv, 0.3)
            if lv == "mid":
                if seg_is_strong_kf and prop_area < kf_area * kf_ratio_thr and prop_area < 0.001 * W * H:
                    mid_streak += 1
                else:
                    mid_streak = 0
                is_kf_ratio_fail = seg_is_strong_kf and mid_streak >= 2
            else:
                mid_streak = 0
                is_kf_ratio_fail = (
                    seg_is_strong_kf and
                    prop_area < kf_area * kf_ratio_thr and
                    prop_area < 0.001 * W * H
                )

            # —— C3（精度优先校准 2026-08-14）：传播输出全幅糊块（>40%）→ 回退精确单帧检测
            #    （用户反馈：57% 中位面积=糊块；传播伪影在暗场/低对比帧产生 30-80% 全幅 mask）
            is_blob_failure = prop_area > BLOB_MAX_RATIO * W * H

            need_fallback = is_jump_failure or is_missing_propagation or is_kf_ratio_fail or is_blob_failure

            if need_fallback:
                reason_bits = []
                if is_jump_failure: reason_bits.append(f"jump({prev_area/(W*H):.2%}→{prop_area/(W*H):.2%})")
                if is_missing_propagation: reason_bits.append("missing")
                if is_kf_ratio_fail: reason_bits.append(f"kf<{kf_area/(W*H):.2%}*{kf_ratio_thr}")
                if is_blob_failure: reason_bits.append(f"blob({prop_area/(W*H):.2%}>{BLOB_MAX_RATIO:.0%})")
                reason_str = ",".join(reason_bits)
                print(f"  [FALLBACK] frame {idx}: prop_area={prop_area/(W*H):.2%} reason={reason_str}",
                      file=sys.stderr)
                boxes = keyframe_boxes.get(seg_start, [])
                if not boxes:
                    boxes = detect_boxes_on_frame(frames[idx], face_det, yolo_det, max_boxes)
                if not boxes:
                    # 没有检测盒，用上一帧的 bbox 扩展（基于上一帧 mask 的 bbox 扩大 1.2x）
                    if idx > 0:
                        prev_mask = final_masks[idx - 1]
                        if np.count_nonzero(prev_mask) > 100:
                            ys, xs = np.where(prev_mask > 0)
                            bx1, bx2 = int(max(0, xs.min()-20)), int(min(W-1, xs.max()+20))
                            by1, by2 = int(max(0, ys.min()-20)), int(min(H-1, ys.max()+20))
                            bw, bh = bx2 - bx1, by2 - by1
                            cx, cy = bx1 + bw*0.5, by1 + bh*0.5
                            bw2, bh2 = bw * 1.2, bh * 1.2
                            ex = clip_box([cx-bw2*0.5, cy-bh2*0.5, cx+bw2*0.5, cy+bh2*0.5], W, H)
                            if ex:
                                boxes = [ex]
                if boxes:
                    img_pred = get_img_predictor_lazy()
                    if amp_ctx is not None:
                        with amp_ctx:
                            fb_mask = sam_single_frame_predict(img_pred, frames[idx], boxes)
                    else:
                        fb_mask = sam_single_frame_predict(img_pred, frames[idx], boxes)
                else:
                    fb_mask = np.zeros((H, W), dtype=np.uint8)
                final_masks[idx] = fb_mask
                _frame_areas[idx] = float(np.count_nonzero(fb_mask))
                fallback_count += 1

    print(f"\n[FALLBACK] {fallback_count} frames fell back to auto_frame (routed_fast={routed_fast_count}, "
          f"routed_weak={routed_weak_frames}, mode_switches={mode_switches})", file=sys.stderr)

    # ===== Tier 2: 边缘精修 =====
    if enable_edge_refine:
        print(f"\n=== Tier 2: Edge Refinement ({N} masks) ===", file=sys.stderr)
        t0_refine = time.time()
        prev_stab: np.ndarray | None = None
        for idx in range(N):
            mask = final_masks[idx]
            if np.count_nonzero(mask) < 10:
                # 空 mask 跳过
                continue
            frame = frames[idx]
            # Layer 2A: 在 Tier2 空间平滑之前做时序稳定（避免把时序信息糊掉，方案 §4A.3）
            if enable_temporal_stabilize:
                lv = level_of(idx)
                if lv == "fast":
                    # 快运动/硬切帧不做 warp 融合：切点两侧内容无关，warp 先验失效，
                    # 且融合拖影会污染后续 static 帧（M4 实证 6 空帧根因之一）；链在此断裂
                    prev_stab = None
                else:
                    mask = stabilize_temporal(mask, prev_stab, _load_flow_full(idx), lv)
                    prev_stab = mask
            refined = refine_mask_edge(mask, frame, level_of(idx))
            final_masks[idx] = refined
        refine_elapsed = time.time() - t0_refine
        print(f"[REFINE] done in {refine_elapsed:.1f}s (temporal_stabilize={enable_temporal_stabilize})",
              file=sys.stderr)

    # ===== 保存 =====
    print("\n=== Saving masks ===", file=sys.stderr)
    nonempty = 0
    for idx in range(N):
        global_idx = start_frame + idx
        out_path = mask_dir / f"mask_{global_idx:05d}.png"
        imwrite_unicode(str(out_path), final_masks[idx])
        if np.count_nonzero(final_masks[idx]) > 10:
            nonempty += 1

    # 路由日志落盘（M1-B 证据：grep "[MOTION_ROUTE]" qc_routing_log.txt）
    try:
        (mask_dir / "qc_routing_log.txt").write_text(
            "\n".join(route_log_lines) + "\n", encoding="utf-8")
    except Exception:
        pass

    # 清理临时目录
    try:
        import shutil
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
    except Exception:
        pass

    elapsed = time.time() - t0_prop + 0.001
    result = {
        "processed": N,
        "nonempty": nonempty,
        "empty": N - nonempty,
        "nonempty_rate": nonempty / N,
        "keyframes": len(keyframe_indices),
        "fallback_count": fallback_count,
        "fallback_rate": fallback_count / N,
        "fallback_rate_excl_routed": fallback_count / N if N else 0.0,
        "keyframe_interval": keyframe_interval,
        "edge_refine": enable_edge_refine,
        "temporal_stabilize": enable_temporal_stabilize,
        "motion_route": {
            "active": bool(motion_levels_path),
            "levels_path": motion_levels_path,
            "fast_frames": levels.count("fast"),
            "mid_frames": levels.count("mid"),
            "static_frames": levels.count("static"),
            "mode_switches": mode_switches,
            "routed_fast_count": routed_fast_count,
            "routed_weak_frames": routed_weak_frames,
        },
        "propagation_elapsed_s": round(prop_elapsed, 1),
        "refine_elapsed_s": round(refine_elapsed, 1) if enable_edge_refine else 0,
        "total_elapsed_s": round(elapsed, 1),
    }
    print(f"\n[RESULT] {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: infer_segment_video_enhanced.py <params.json>", file=sys.stderr)
        sys.exit(2)
    json_path = sys.argv[1]
    with open(json_path, "r", encoding="utf-8-sig") as f:
        params = json.load(f)
    ok_path = json_path + ".ok"
    fail_path = json_path + ".fail"
    for p in [ok_path, fail_path]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    try:
        res = run(params)
        res["status"] = "ok"
        with open(ok_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print(json.dumps(res, ensure_ascii=False))
    except Exception as e:
        tb = traceback.format_exc()
        err = {"status": "fail", "error": str(e), "traceback": tb}
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(err, f, ensure_ascii=False, indent=2)
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
