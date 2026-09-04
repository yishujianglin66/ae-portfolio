"""
单段 auto_frame anime 推理脚本（venv-sam2 子进程）。
- 脸检测器：anime_face_detector (YOLOv3)，检测脸 bbox → 外扩 4x 成全身框
- fallback 检测器：YOLOv8x (all class, conf=0.05) + LAB 显著性 top-K 连通域 bbox
- 所有 bbox 经 IoU=0.5 NMS 合并 → SAM2.1 single predictor 单帧分割
- mask 输出 uint8 0/255 PNG

参数通过 JSON 文件传入（支持中文路径），JSON schema:
{
  "video_path": str,           # 完整原视频路径（任意长度）
  "start_frame": int,          # 本推理的起始帧号（全局，用于 cap.set + mask 命名）
  "expected_frames": int,      # 期望推理帧数（≤ 视频总帧 - start_frame）
  "mask_dir": str,             # 输出 mask 目录
  "sam2_checkpoint": str,      # sam2.1_hiera_large.pt 之类路径
  "model_cfg": str,            # sam2.1_hiera_l.yaml 之类（相对 SAM2 repo）
  "yolov8x_path": str,         # fallback yolov8x.pt 路径
  "face_conf": float,          # anime face conf 阈值，默认 0.35
  "face_expand": float,        # 脸框外扩倍数，默认 4.0
  "yolo_conf": float,          # fallback YOLOv8x conf，默认 0.05
  "max_boxes_per_frame": int,  # 每帧最多实例，默认 5
  "sam_variant": str,          # large / base_plus / small / tiny
}
完成后写 STATUS marker 文件（同 JSON 路径 + .ok 或 .fail）
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import cv2
import numpy as np


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
    # fake score by area (larger preferred; anime chars usually not tiny)
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
    """LAB a-b 通道差 + Otsu + 形态学 → 取 top-k 最大连通域 bbox。"""
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


# ---------- detectors ----------
class HaarFaceDetector:
    """OpenCV HAAR/LBP/DNN-YuNet 人脸检测：脸框外扩成全身框。找不到级联 xml 时 ok()=False。"""
    CASCADE_NAMES = [
        "haarcascade_frontalface_default.xml",
        "haarcascade_frontalface_alt.xml",
        "haarcascade_frontalface_alt2.xml",
        "haarcascade_profileface.xml",
        "haarcascade_frontalface_alt_tree.xml",
        "lbpcascade_frontalface.xml",
        "lbpcascade_animeface.xml",
        "lbpcascade_frontalface_improved.xml",
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
        # 常见位置全盘搜（限制搜索深度）
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
                        break  # 每种根目录找到一个就够
            except Exception:
                pass
        return dirs

    def __init__(self, conf: float = 0.35, expand: float = 4.0):
        self.conf = conf
        self.expand = expand
        self._cascades: list[tuple[str, cv2.CascadeClassifier]] = []
        search_dirs = self._discover_xml_dirs()
        wanted = {n for n in self.CASCADE_NAMES}
        found: set[str] = set()
        for d in search_dirs:
            dp = Path(d)
            if not dp.is_dir():
                continue
            for name in list(wanted - found):
                p = dp / name
                try:
                    if p.exists():
                        c = cv2.CascadeClassifier(str(p))
                        if not c.empty():
                            self._cascades.append((name, c))
                            found.add(name)
                except Exception:
                    pass
        print(f"[FACE] {len(self._cascades)} cascade(s) loaded ({len(found)}/{len(self.CASCADE_NAMES)} names), "
              f"expand={expand}, search_dirs={len(search_dirs)}", file=sys.stderr)

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
                new_cy = fcy + 0.5 * fh  # 中心下移至胸部位置
                bw = fw * self.expand
                bh = fh * self.expand
                bx1 = fcx - bw * 0.5
                by1 = new_cy - bh * 0.5
                bx2 = fcx + bw * 0.5
                by2 = new_cy + bh * 0.5
                cb = clip_box([bx1, by1, bx2, by2], w, h)
                if cb:
                    key = (cb[0], cb[1], cb[2], cb[3])
                    if key not in seen:
                        seen.add(key)
                        out.append(cb)
        return out


class YOLOFallbackDetector:
    """YOLOv8x ALL CLASSES（不加类过滤）+ max_det 放宽，尽可能捞到 anime 人物框。"""
    def __init__(self, model_path: str, conf: float = 0.05):
        self.conf = conf
        self._yolo = None
        try:
            from ultralytics import YOLO
            self._yolo = YOLO(model_path, verbose=False)
            print(f"[YOLO] loaded {model_path}, conf={conf}, ALL classes", file=sys.stderr)
        except Exception as e:
            print(f"[YOLO] init FAIL: {e}", file=sys.stderr)

    def ok(self) -> bool:
        return self._yolo is not None

    def detect(self, frame_bgr: np.ndarray) -> list[list[int]]:
        if self._yolo is None:
            return []
        h, w = frame_bgr.shape[:2]
        try:
            res = self._yolo(
                frame_bgr, conf=self.conf, verbose=False,
                max_det=30, iou=0.6,
            )
        except Exception as e:
            print(f"[YOLO] predict error: {e}", file=sys.stderr)
            return []
        out = []
        for r in res:
            if r.boxes is None:
                continue
            boxes = r.boxes.xyxy.cpu().numpy() if hasattr(r.boxes, "xyxy") else None
            confs = r.boxes.conf.cpu().numpy() if hasattr(r.boxes, "conf") else None
            if boxes is None:
                continue
            n = boxes.shape[0]
            for i in range(n):
                b = boxes[i]
                score = float(confs[i]) if confs is not None and i < confs.size else 1.0
                # 极小框过滤（< 万分之一画面）
                area = (float(b[2]) - float(b[0])) * (float(b[3]) - float(b[1]))
                if area < 0.0001 * h * w and score < self.conf * 2:
                    continue
                cb = clip_box([float(b[0]), float(b[1]), float(b[2]), float(b[3])], w, h)
                if cb:
                    out.append(cb)
        return out


def sam_predictor_factory(cfg: dict):
    """返回 SAM2 predictor 实例（单帧模式）。"""
    checkpoint = cfg["sam2_checkpoint"]
    from sam2.build_sam import build_sam2
    import torch
    from core.torch_runtime import get_device

    variant = cfg.get("sam_variant", "large")
    ckpt_name = Path(checkpoint).name.lower()
    # 从 checkpoint 名判断 SAM 大版本
    if "sam2.1_" in ckpt_name:
        ver_prefix = "sam2.1"
    elif "sam2_" in ckpt_name or "sam2." in ckpt_name:
        ver_prefix = "sam2.1" if "2.1" in ckpt_name else "sam2"
    else:
        # 根据 checkpoint 文件大小粗略推断：large 模型 > 800MB 通常是 sam2.1（这里保守用 sam2.1）
        ver_prefix = "sam2.1"
    # sam2 pip 包内 configs/ 目录结构：
    #   configs/sam2/sam2_hiera_{s,t,b+,l}.yaml        (SAM 2.0)
    #   configs/sam2.1/sam2.1_hiera_{s,t,b+,l}.yaml   (SAM 2.1)
    variant_to_cfg_suffix = {
        "large": "l.yaml",
        "base_plus": "b+.yaml",
        "small": "s.yaml",
        "tiny": "t.yaml",
    }
    suffix = variant_to_cfg_suffix.get(variant, "l.yaml")
    # pip 版 sam2 的 Hydra config 搜索路径是 pkg://sam2（即包根目录），
    # 所以必须用 "configs/sam2.1/sam2.1_hiera_s.yaml" 这种完整相对路径
    CONFIG_ROOT = "configs"
    # 允许显式 model_cfg 覆盖（优先）
    explicit_cfg = (cfg.get("model_cfg") or "").strip()
    if explicit_cfg and (explicit_cfg.endswith(".yaml") or explicit_cfg.endswith(".yml")):
        # 如果用户只写了文件名（不带目录），补全前缀
        if "/" not in explicit_cfg and "\\" not in explicit_cfg:
            if explicit_cfg.startswith("sam2.1_"):
                config_file = f"{CONFIG_ROOT}/sam2.1/{explicit_cfg}"
            elif explicit_cfg.startswith("sam2_"):
                config_file = f"{CONFIG_ROOT}/sam2/{explicit_cfg}"
            else:
                config_file = f"{CONFIG_ROOT}/{ver_prefix}/{explicit_cfg}"
        elif explicit_cfg.startswith("sam2/") or explicit_cfg.startswith("sam2.1/"):
            # 已经是 "sam2.1/sam2.1_hiera_s.yaml" 格式，补 configs/ 前缀
            config_file = f"{CONFIG_ROOT}/{explicit_cfg}"
        else:
            config_file = explicit_cfg
    else:
        config_file = f"{CONFIG_ROOT}/{ver_prefix}/{ver_prefix}_hiera_{suffix}"

    device = get_device()
    print(f"[SAM2] ver={ver_prefix} variant={variant} config={config_file} ckpt={checkpoint} device={device}",
          file=sys.stderr)
    sam2_model = build_sam2(
        config_file=config_file,
        ckpt_path=checkpoint,
        device=device,
        mode="eval",
        apply_postprocessing=False,
    )
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    predictor = SAM2ImagePredictor(sam2_model)
    return predictor


# ---------- main ----------
def run(params: dict) -> dict:
    video_path = params["video_path"]
    start_frame = int(params["start_frame"])
    expected = int(params.get("expected_frames", 0))
    mask_dir = Path(params["mask_dir"])
    mask_dir.mkdir(parents=True, exist_ok=True)
    max_boxes = int(params.get("max_boxes_per_frame", 5))

    # detectors
    face = HaarFaceDetector(
        conf=float(params.get("face_conf", 0.35)),
        expand=float(params.get("face_expand", 4.0)),
    )
    yolo = YOLOFallbackDetector(
        model_path=params["yolov8x_path"],
        conf=float(params.get("yolo_conf", 0.05)),
    )

    # SAM predictor
    predictor = sam_predictor_factory(params)

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        total_frames = expected
    # 支持从源视频的任意帧开始推理（无需 ffmpeg 预切段）
    if start_frame > 0:
        seek_ok = cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        print(f"[VIDEO] seek to start_frame={start_frame}, ok={seek_ok}, total_in_video={total_frames}", file=sys.stderr)
    else:
        print(f"[VIDEO] total_frames={total_frames}, start_global={start_frame}, src={video_path}", file=sys.stderr)

    processed = 0
    nonempty = 0
    face_frames = 0
    yolo_frames = 0
    sal_frames = 0
    t0 = time.time()

    idx_in_seg = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        h, w = frame.shape[:2]

        # 1. HAAR/LBP 脸检测框 → 外扩全身框
        face_boxes = face.detect(frame) if face.ok() else []
        used_face = len(face_boxes) > 0
        if used_face:
            face_frames += 1

        # 2. YOLO all classes（任何情况都跑，补脸检测不到的帧）
        yolo_boxes = yolo.detect(frame) if yolo.ok() else []
        if len(yolo_boxes) > 0:
            yolo_frames += 1

        # 3. LAB 显著性（任何情况都补，k=5 最大连通域）
        sal_boxes = []
        try:
            sal_boxes = lab_saliency_boxes(frame, k=5, min_area_ratio=0.003)
            if sal_boxes:
                sal_frames += 1
        except Exception as e:
            print(f"[SALIENCY] err: {e}", file=sys.stderr)

        # 4. 合并 NMS
        all_boxes: list[list[int]] = []
        # priority: face → yolo → sal（已在 nms 里按面积排序，所以会保留大的）
        all_boxes.extend(face_boxes)
        all_boxes.extend(yolo_boxes)
        all_boxes.extend(sal_boxes)
        keep = nms_boxes(all_boxes, iou_thr=0.5)
        boxes = [all_boxes[i] for i in keep][:max_boxes]

        # 5. SAM2 单帧分割
        if not boxes:
            # 完全无框：fallback 到画面中间 1/3 矩形作为保底
            cx, cy = w // 2, h // 2
            bw, bh = w // 3, h // 2
            default_box = [cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2]
            cb = clip_box(default_box, w, h)
            if cb:
                boxes = [cb]

        # FP16 autocast：2.14× 加速，IoU=0.9917 基本无损（bench 实锤）
        use_fp16 = True
        amp_ctx = None
        if use_fp16:
            try:
                import torch
                if torch.cuda.is_available():
                    amp_ctx = torch.autocast(device_type="cuda", dtype=torch.float16)
            except Exception:
                amp_ctx = None

        def _do_predict():
            predictor.set_image(frame)
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
                        print(f"[SAM] frame {idx_in_seg} predict err: {e}", file=sys.stderr)
            return merged

        if amp_ctx is not None:
            with amp_ctx:
                merged_mask = _do_predict()
        else:
            merged_mask = _do_predict()

        # 保存（start_frame + idx_in_seg = 全局帧号）
        global_idx = start_frame + idx_in_seg
        out_path = mask_dir / f"mask_{global_idx:05d}.png"
        imwrite_unicode(str(out_path), merged_mask)

        if np.count_nonzero(merged_mask) > 10:
            nonempty += 1

        processed += 1
        idx_in_seg += 1
        if expected and idx_in_seg >= expected:
            break
        # 进度打点
        if idx_in_seg % 50 == 0:
            elapsed = time.time() - t0
            fps = idx_in_seg / max(1e-6, elapsed)
            print(f"[PROG] {idx_in_seg}/{total_frames} nonempty={nonempty} fps={fps:.2f} "
                  f"face_frames={face_frames} yolo_frames={yolo_frames} sal_frames={sal_frames}", file=sys.stderr)

    cap.release()
    elapsed = time.time() - t0
    return {
        "processed": processed,
        "nonempty": nonempty,
        "elapsed_sec": elapsed,
        "fps": processed / max(1e-6, elapsed),
        "face_frames": face_frames,
        "yolo_frames": yolo_frames,
        "sal_frames": sal_frames,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: infer_segment_autoframe_anime.py <params.json>", file=sys.stderr)
        sys.exit(2)
    json_path = sys.argv[1]
    with open(json_path, "r", encoding="utf-8-sig") as f:
        params = json.load(f)
    ok_path = json_path + ".ok"
    fail_path = json_path + ".fail"
    # 清理旧 marker
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
