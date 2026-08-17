"""生成 MattingEngine E2E 实测对比预览图（总体 + 发丝放大）。"""
import sys, os
import cv2
import numpy as np
from pathlib import Path

ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
OUT = ROOT / "tests" / "output" / "matting_e2e"
SRC = OUT / "portrait_test_input.jpg"


def imread(p: Path):
    data = np.fromfile(str(p), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def imwrite(p: Path, img):
    p.parent.mkdir(parents=True, exist_ok=True)
    ext = p.suffix or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(p))
    return ok


def checker_bg(shape_w, shape_h, tile=16):
    """生成棋盘格背景 (BGR)。"""
    h_tiles = (shape_h + tile - 1) // tile
    w_tiles = (shape_w + tile - 1) // tile
    c1 = np.full((tile, tile, 3), (230, 230, 230), dtype=np.uint8)
    c2 = np.full((tile, tile, 3), (150, 150, 150), dtype=np.uint8)
    row1 = np.concatenate([c1, c2], axis=1)
    row2 = np.concatenate([c2, c1], axis=1)
    block = np.concatenate([row1, row2], axis=0)
    big = np.tile(block, (h_tiles, w_tiles, 1))
    return big[:shape_h, :shape_w]


def composite_on_checker(rgba_bgra):
    """把 BGRA 叠加到棋盘格背景（透明通道合成）。"""
    h, w = rgba_bgra.shape[:2]
    bg = checker_bg(w, h)
    a = rgba_bgra[..., 3:4].astype(np.float32) / 255.0
    fg = rgba_bgra[..., :3].astype(np.float32)
    out = (fg * a + bg.astype(np.float32) * (1.0 - a)).astype(np.uint8)
    return out


def add_header(img, label, bar_h=64, color=(30, 30, 30)):
    h, w = img.shape[:2]
    bar = np.full((bar_h, w, 3), color, dtype=np.uint8)
    cv2.putText(bar, label, (18, bar_h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    return np.concatenate([bar, img], axis=0)


def load_rgbs():
    src = imread(SRC)
    h, w = src.shape[:2]
    # 统一尺寸：2560×1440 → 最大宽度 960
    TW = 960
    scale = TW / w
    new_size = (TW, int(h * scale))
    src_s = cv2.resize(src, new_size, interpolation=cv2.INTER_AREA)

    def load(p):
        rgba = imread(p)
        rgba_s = cv2.resize(rgba, new_size, interpolation=cv2.INTER_AREA)
        comp = composite_on_checker(rgba_s)
        return comp, rgba_s

    mod_p = OUT / "modnet" / "rgba" / (SRC.stem + ".png")
    rmbg_p = OUT / "rmbg14" / "rgba" / (SRC.stem + ".png")
    mod_comp, _ = load(mod_p)
    rmbg_comp, _ = load(rmbg_p)
    return src_s, mod_comp, rmbg_comp, new_size


def build_overview():
    src, mod, rmbg, sz = load_rgbs()
    a = add_header(src, "Original Input  (2560x1440 scaled)")
    b = add_header(mod, "MODNet  (25.9MB, 1.2s)")
    c = add_header(rmbg, "RMBG-1.4  (176MB, 4.9s)")
    # 三图并排
    grid = np.concatenate([a, b, c], axis=1)
    out = OUT / "01_overview_3up.jpg"
    imwrite(out, grid)
    print(f"Wrote {out}  ({grid.shape[1]}x{grid.shape[0]})")
    return out


def hair_detail_crops():
    """取原图顶部中间偏左（头顶飞散发丝）、右偏（侧脸碎发）两处做 2x 放大。"""
    src = imread(SRC)
    H, W = src.shape[:2]
    # 统一取 RGBA + alpha，然后 alpha 叠加在纯色背景上
    boxes = [
        ("top_hair", int(W * 0.28), int(H * 0.02), int(W * 0.56), int(H * 0.22)),
        ("side_hair", int(W * 0.55), int(H * 0.20), int(W * 0.35), int(H * 0.35)),
    ]
    scale = 2

    mod_rgba_p = OUT / "modnet" / "rgba" / (SRC.stem + ".png")
    rmbg_rgba_p = OUT / "rmbg14" / "rgba" / (SRC.stem + ".png")
    mod_rgba = imread(mod_rgba_p)
    rmbg_rgba = imread(rmbg_rgba_p)

    rows = []
    for name, x, y, w, h in boxes:
        # crop
        src_crop = src[y : y + h, x : x + w]
        mod_crop = mod_rgba[y : y + h, x : x + w]
        rmbg_crop = rmbg_rgba[y : y + h, x : x + w]
        src_big = cv2.resize(src_crop, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        mod_big = cv2.resize(mod_crop, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        rmbg_big = cv2.resize(rmbg_crop, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        mod_comp = composite_on_checker(mod_big)
        rmbg_comp = composite_on_checker(rmbg_big)
        # alpha 叠加到粉色背景便于看软边
        pink = np.full_like(src_big, (203, 192, 255), dtype=np.uint8)
        def overlay(rgba_bgra, bg):
            a = rgba_bgra[..., 3:4].astype(np.float32) / 255.0
            return (rgba_bgra[..., :3].astype(np.float32) * a + bg.astype(np.float32) * (1 - a)).astype(np.uint8)
        mod_pink = overlay(mod_big, pink)
        rmbg_pink = overlay(rmbg_big, pink)
        col1 = add_header(src_big, f"{name}  crop  2x")
        col2 = add_header(mod_comp, f"MODNet checker 2x  ({name})")
        col3 = add_header(rmbg_comp, f"RMBG-1.4 checker 2x  ({name})")
        col4 = add_header(mod_pink, f"MODNet pink-bg 2x")
        col5 = add_header(rmbg_pink, f"RMBG-1.4 pink-bg 2x")
        row = np.concatenate([col1, col2, col3, col4, col5], axis=1)
        out = OUT / f"02_{name}_2x.jpg"
        imwrite(out, row)
        print(f"Wrote {out}  ({row.shape[1]}x{row.shape[0]})")
        rows.append(out)
    return rows


if __name__ == "__main__":
    build_overview()
    hair_detail_crops()
    print("Done.")
