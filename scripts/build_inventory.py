"""生成 batch_auto_frame 入库清单。

采集:
- 输入视频参数: 时长/分辨率/帧率/帧数/大小 (ffprobe)
- 产出信息: 透明视频路径/大小/遮罩帧数
输出:
- 入库清单.md (Markdown 表格)
- 入库清单.csv
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
INPUT_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUTPUT_DIRS = [
    PROJECT_ROOT / "data" / "output" / "batch_auto_frame",  # C 盘
    Path(r"D:\AE-Work\batch_auto_frame"),                   # D 盘
]
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
OUT_CSV = PROJECT_ROOT / "data" / "output" / "入库清单.csv"
OUT_MD = PROJECT_ROOT / "data" / "output" / "入库清单.md"


def ffprobe_info(video: Path) -> dict:
    """获取视频流参数。"""
    try:
        cmd = [
            FFPROBE, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(video),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        data = json.loads(r.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}

        duration = float(fmt.get("duration", 0))
        size_mb = float(fmt.get("size", 0)) / 1048576

        fps_str = stream.get("r_frame_rate", "0/0")
        try:
            num, den = fps_str.split("/")
            fps = round(float(num) / float(den), 2) if float(den) else 0
        except Exception:
            fps = 0

        return {
            "duration": duration,
            "width": stream.get("width", 0),
            "height": stream.get("height", 0),
            "fps": fps,
            "frames": stream.get("nb_frames", ""),
            "size_mb": round(size_mb, 1),
        }
    except Exception as e:
        return {"duration": 0, "width": 0, "height": 0, "fps": 0, "frames": "", "size_mb": 0}


def find_output_mov(stem: str) -> tuple[Path | None, int]:
    """在 C/D 盘查找产出 MOV，返回 (路径, 大小MB)。"""
    for odir in OUTPUT_DIRS:
        d = odir / stem
        if not d.exists():
            continue
        movs = list(d.glob("*_transparent.mov"))
        for m in movs:
            if m.stat().st_size > 1000:
                return m, round(m.stat().st_size / 1048576, 1)
        # 遮罩目录信息
    return None, 0


def count_masks(stem: str) -> int:
    """统计遮罩帧数（从 summary 或扫描目录）。"""
    for odir in OUTPUT_DIRS:
        d = odir / stem
        if not d.exists():
            continue
        mask_dirs = list(d.glob("*_masks"))
        if mask_dirs:
            return len(list(mask_dirs[0].glob("*.png")))
    return 0


def mov_frame_count(mov: Path) -> int:
    """从 MOV 提取帧数（qtrle 每帧都有遮罩，帧数≈遮罩数）。"""
    try:
        cmd = [
            FFPROBE, "-v", "error",
            "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=nb_read_frames",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(mov),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        return int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
    except Exception:
        return 0


def main():
    # 合并所有 summary 数据（遮罩数恢复用）
    mask_counts: dict[str, int] = {}
    for odir in OUTPUT_DIRS:
        sfile = odir / "batch_summary.json"
        if sfile.exists():
            try:
                data = json.loads(sfile.read_text(encoding="utf-8"))
                for r in data.get("results", []):
                    v = r.get("video", "")
                    if r.get("mask_count"):
                        mask_counts[v] = r["mask_count"]
            except Exception:
                pass

    videos = sorted(INPUT_DIR.glob("*.mp4"))
    rows = []

    print(f"扫描到 {len(videos)} 个视频...\n")

    for i, v in enumerate(videos):
        stem = v.stem
        info = ffprobe_info(v)
        mov, mov_mb = find_output_mov(stem)
        masks = mask_counts.get(stem, 0)
        if masks == 0:
            masks = count_masks(stem)
        if masks == 0 and mov:
            masks = mov_frame_count(mov)  # 遮罩已清理 → 从 MOV 帧数恢复

        total_sec = int(info["duration"])
        mm = total_sec // 60
        ss = total_sec % 60

        rows.append({
            "序号": i + 1,
            "视频文件名": v.name,
            "系列/来源": stem.split("_")[0] if "_" in stem else stem,
            "时长": f"{mm}:{ss:02d}",
            "分辨率": f"{info['width']}x{info['height']}" if info["width"] else "-",
            "帧率": info["fps"],
            "帧数": info["frames"] or round(info["duration"] * info["fps"]),
            "源大小MB": info["size_mb"],
            "遮罩帧数": masks,
            "成品MOV": mov.name if mov else "❌ 缺失",
            "成品大小MB": mov_mb,
            "输出位置": "D盘" if mov and str(mov).startswith("D:") else ("C盘" if mov else "-"),
        })
        status = "✓" if mov else "✗"
        print(f"  [{i+1}/{len(videos)}] {status} {v.name[:50]}")

    # 写 CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # 写 Markdown
    lines = []
    lines.append("# SAM2 auto_frame 批量分割 · 入库清单\n")
    lines.append(f"- **输入目录**: `{INPUT_DIR}`")
    lines.append(f"- **视频总数**: {len(rows)}")
    lines.append(f"- **成品完整**: {sum(1 for r in rows if r['成品MOV'] != '❌ 缺失')} / {len(rows)}")
    total_mov = round(sum(r["成品大小MB"] for r in rows if r["成品大小MB"]), 1)
    lines.append(f"- **成品总量**: {round(total_mov/1024, 1)} GB\n")
    lines.append("| " + " | ".join(rows[0].keys()) + " |")
    lines.append("|" + "|".join(["---"] * len(rows[0])) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(r[k]) for k in rows[0].keys()) + " |")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # 写 Excel（带样式和汇总表）
    OUT_XLSX = PROJECT_ROOT / "data" / "output" / "入库清单.xlsx"
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "入库清单"

    headers = list(rows[0].keys())
    ws.append(headers)
    for r in rows:
        ws.append([r[k] for k in headers])

    # 表头样式
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="4472C4")
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border

    # 数据样式 + 列宽
    col_widths = [6, 55, 14, 8, 12, 8, 8, 10, 12, 55, 12, 8]
    for col, w in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in row:
            c.border = border
            c.alignment = Alignment(vertical="center")
            if c.column in (1, 4, 5, 6, 7, 8, 11, 12):
                c.alignment = Alignment(horizontal="center", vertical="center")

    # 冻结首行 + 自动筛选
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{chr(64+len(headers))}{ws.max_row}"

    # 汇总表
    ws2 = wb.create_sheet("统计汇总")
    total_mov_gb = round(sum(r["成品大小MB"] for r in rows if r["成品大小MB"]) / 1024, 1)
    total_masks = sum(r["遮罩帧数"] for r in rows if isinstance(r["遮罩帧数"], int))
    total_frames = sum(r["帧数"] for r in rows if isinstance(r["帧数"], int))
    total_src = round(sum(r["源大小MB"] for r in rows) / 1024, 1)
    summary_rows = [
        ["指标", "数值"],
        ["视频总数", f"{len(rows)} 个"],
        ["成品完整率", f"{sum(1 for r in rows if r['成品MOV'] != '❌ 缺失')} / {len(rows)}"],
        ["源视频总量", f"{total_src} GB"],
        ["成品总量（qtrle MOV）", f"{total_mov_gb} GB"],
        ["总帧数", f"{total_frames:,}"],
        ["总遮罩帧数", f"{total_masks:,}"],
        ["输出分布", f"C盘 {sum(1 for r in rows if r['输出位置']=='C盘')} 个 + D盘 {sum(1 for r in rows if r['输出位置']=='D盘')} 个"],
        ["平均压缩比(源/成品)", f"1:{round(total_mov_gb/total_src, 1)}"],
    ]
    for row in summary_rows:
        ws2.append(row)
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 40
    for col in (1, 2):
        c = ws2.cell(row=1, column=col)
        c.font = header_font
        c.fill = header_fill
    for row in ws2.iter_rows(min_row=2):
        for c in row:
            c.border = border

    wb.save(OUT_XLSX)

    print(f"\n完成! 写入:")
    print(f"  CSV:  {OUT_CSV}")
    print(f"  MD:   {OUT_MD}")
    print(f"  XLSX: {OUT_XLSX}")
    print(f"  缺失成品: {sum(1 for r in rows if r['成品MOV'] == '❌ 缺失')} 个")


if __name__ == "__main__":
    main()
