"""批量入库：将 58 个透明视频注册到 MediaMetadataDB 素材库。

采集每个 MOV 的参数（时长/分辨率/帧率/大小），关联源视频路径，
注册到 data/media_metadata.db。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT))

from media.media_metadata_db import MediaMetadataDB

FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

# 成品目录
OUTPUT_DIRS = [
    PROJECT_ROOT / "data" / "output" / "batch_auto_frame",
    Path(r"D:\AE-Work\batch_auto_frame"),
]
# 源视频目录
SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"

# BV 号提取正则
BV_RE = re.compile(r"(BV\w+)")


def ffprobe_info(path: Path) -> dict:
    """用 ffprobe 采集视频参数。"""
    cmd = [
        FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_frames,r_frame_rate,duration,codec_name,pix_fmt",
        "-show_entries", "format=duration,size",
        "-of", "json", str(path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    data = json.loads(r.stdout)
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})

    # 解析帧率 (如 "25/1" → 25.0)
    fps_str = stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    duration = float(fmt.get("duration", stream.get("duration", 0)))
    size = int(fmt.get("size", 0))

    return {
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "fps": round(fps, 2),
        "duration": round(duration, 2),
        "file_size": size,
        "codec": stream.get("codec_name", ""),
        "pix_fmt": stream.get("pix_fmt", ""),
    }


def find_source_video(mov_stem: str) -> str:
    """根据 MOV 文件名匹配源视频。"""
    # 去掉 _transparent 后缀
    name = mov_stem.replace("_transparent", "")
    # 精确匹配
    for ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm"]:
        src = SRC_DIR / f"{name}{ext}"
        if src.exists():
            return str(src)
    # 模糊匹配（去特殊字符后包含）
    for src in SRC_DIR.iterdir():
        if src.stem == name or name in src.stem or src.stem in name:
            return str(src)
    return ""


def guess_platform(name: str) -> str:
    """从文件名推断来源平台。"""
    if BV_RE.search(name):
        return "bilibili"
    if name.startswith("DL_"):
        return "bilibili"
    return "unknown"


def extract_tags(name: str) -> str:
    """从文件名提取标签。"""
    tags = ["透明视频", "alpha通道", "SAM2抠像", "auto_frame"]
    # 从文件名提取关键词
    if "海贼王" in name:
        tags.extend(["海贼王", "动漫"])
    elif "黑岩" in name:
        tags.extend(["黑岩射手", "动漫"])
    elif "FATE" in name.upper():
        tags.extend(["FATE", "动漫"])
    elif "时光代理人" in name:
        tags.extend(["时光代理人", "动漫"])
    elif "地缚少年" in name:
        tags.extend(["地缚少年花子君", "动漫"])
    elif "灵笼" in name:
        tags.extend(["灵笼", "动漫"])
    elif "教程" in name or "PR教程" in name:
        tags.extend(["教程", "技术"])
    elif "AMV" in name.upper() or "踩点" in name or "混剪" in name:
        tags.extend(["AMV", "混剪", "踩点"])
    return ",".join(tags)


def main():
    # 收集所有成品 MOV
    all_movs = []
    for base in OUTPUT_DIRS:
        if base.exists():
            all_movs.extend(sorted(base.rglob("*_transparent.mov")))

    print(f"共发现 {len(all_movs)} 个成品透明视频\n")

    db = MediaMetadataDB()

    items = []
    for mov in all_movs:
        info = ffprobe_info(mov)
        if not info:
            print(f"  ⚠ ffprobe 失败: {mov.name}")
            continue

        src_path = find_source_video(mov.stem)
        platform = guess_platform(mov.name)
        tags = extract_tags(mov.name)

        extra = {
            "source_video": src_path,
            "codec": info["codec"],
            "pix_fmt": info["pix_fmt"],
            "has_alpha": True,
            "alpha_codec": "qtrle",
            "mask_mode": "auto_frame",
            "model": "sam2.1_hiera_base_plus",
        }

        item = {
            "file_path": str(mov),
            "file_name": mov.name,
            "file_type": "video",
            "file_ext": "mov",
            "file_size": info["file_size"],
            "duration": info["duration"],
            "width": info["width"],
            "height": info["height"],
            "fps": info["fps"],
            "tags": tags,
            "source_platform": platform,
            "extra": json.dumps(extra, ensure_ascii=False),
        }
        items.append(item)
        print(f"  [{len(items):3d}] {mov.name[:50]:52s} {info['width']}x{info['height']} "
              f"{info['duration']:7.1f}s {round(info['file_size']/1048576,1):8.1f}MB")

    # 批量写入
    count = db.add_items_batch(items)
    print(f"\n入库完成: {count} 条记录写入 data/media_metadata.db")

    # 验证
    stats = db.get_stats()
    print(f"数据库统计: {stats}")

    # 查询验证
    results = db.search(file_type="video")
    alpha_count = sum(1 for r in results if "透明视频" in (r.tags or ""))
    print(f"验证: 搜索 video 类型 {len(results)} 条，其中透明视频 {alpha_count} 条")


if __name__ == "__main__":
    main()
