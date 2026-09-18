#!/usr/bin/env python3
"""
HMS (Human Measurement System) 双盲评测脚本
=============================================
生成随机化顺序的对比评测视频 + 评分表。
用于主观评估不同渲染配置的风格复刻质量。

用法:
  python scripts/hms_blind_eval.py \
    --videos tmp/renders/B0_baseline.mp4 tmp/renders/B3_v6.mp4 tmp/renders/B3_zoompan.mp4 \
    --labels "B0基线" "B3_v6" "B3_zoompan" \
    --output tmp/hms_eval/ \
    --raters 3

输出:
  - hms_eval/concat_blind.mp4  (随机顺序拼接视频，黑场分隔)
  - hms_eval/rating_sheet.json  (随机化标签映射 + 评分模板)
  - hms_eval/rating_form.html   (可视化评分表单)
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def probe_duration(video_path: str) -> float:
    """获取视频时长"""
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
           "-of", "csv=p=0", video_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def generate_concat_video(video_paths: list[str], output_path: str,
                          black_duration: float = 2.0,
                          resolution: tuple = (1920, 1080),
                          fps: int = 24):
    """将多个视频用黑场分隔拼接"""
    w, h = resolution
    # 生成黑场片段
    black_template = f"color=c=black:s={w}x{h}:d={black_duration}:r={fps}"

    # 构建 ffmpeg complex filter
    inputs = []
    filter_parts = []
    n = len(video_paths)

    for i, vp in enumerate(video_paths):
        inputs.extend(["-i", vp])
        # 标准化每个视频到统一格式
        filter_parts.append(
            f"[{i}:v]scale={w}:{h},pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={fps},format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
        )
        filter_parts.append(
            f"[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )

    # 黑场（无音频）
    filter_parts.append(
        f"color=c=black:s={w}x{h}:d={black_duration}:r={fps},format=yuv420p[blk]"
    )
    filter_parts.append("anullsrc=channel_layout=stereo:sample_rate=44100[blk_a]")

    # 拼接序列: v0, blk, v1, blk, v2, ...
    concat_inputs = []
    for i in range(n):
        concat_inputs.append(f"[v{i}][a{i}]")
        if i < n - 1:
            concat_inputs.append("[blk][blk_a]")

    n_streams = n + (n - 1)  # videos + blacks
    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={n_streams}:v=1:a=1[outv][outa]"
    )

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    print(f"  拼接 {n} 个视频 + {n-1} 个黑场间隔...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"  [WARN] ffmpeg 返回 {r.returncode}")
        # 降级：简单 concat（不统一格式）
        _fallback_concat(video_paths, output_path, black_duration)
    else:
        dur = probe_duration(output_path)
        size = Path(output_path).stat().st_size / 1024 / 1024
        print(f"  完成: {dur:.1f}s, {size:.1f}MB")


def _fallback_concat(video_paths: list[str], output_path: str, black_dur: float):
    """降级方案：生成 concat 文件列表"""
    concat_file = Path(output_path).parent / "_concat_list.txt"
    with open(concat_file, "w") as f:
        for i, vp in enumerate(video_paths):
            f.write(f"file '{vp}'\n")
            if i < len(video_paths) - 1:
                f.write(f"file 'black_{black_dur}s.mp4'\n")
    # 先创建黑场
    black_path = Path(output_path).parent / f"black_{black_dur}s.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=black:s=1920x1080:d={black_dur}:r=24",
        "-c:v", "libx264", "-preset", "fast", str(black_path)
    ], capture_output=True, timeout=30)
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", output_path
    ], capture_output=True, timeout=300)


def generate_rating_sheet(video_paths: list[str], labels: list[str],
                          output_dir: Path, n_raters: int = 3) -> dict:
    """生成随机化评分表"""
    n = len(video_paths)
    # 生成随机 ID（A, B, C... 打乱）
    ids = [chr(65 + i) for i in range(n)]
    random.shuffle(ids)

    # 映射：随机ID → 真实标签
    mapping = {}
    for vid_id, label in zip(ids, labels):
        mapping[vid_id] = label

    # 评分维度
    dimensions = [
        {"name": "风格相似度", "desc": "整体风格与参考视频的相似程度", "scale": "1-5"},
        {"name": "色彩还原度", "desc": "饱和度/对比度/色调是否接近参考", "scale": "1-5"},
        {"name": "节奏感", "desc": "切点/转场与BGM节拍的吻合度", "scale": "1-5"},
        {"name": "运镜自然度", "desc": "镜头运动是否流畅自然", "scale": "1-5"},
        {"name": "整体观感", "desc": "综合主观评价", "scale": "1-5"},
    ]

    sheet = {
        "eval_id": f"HMS_{random.randint(1000, 9999)}",
        "n_raters": n_raters,
        "video_mapping": mapping,
        "video_files": {vid_id: str(vp) for vid_id, vp in zip(ids, video_paths)},
        "dimensions": dimensions,
        "ratings": {},
        "instructions": [
            "1. 按顺序观看 concat_blind.mp4 中的各片段（黑场分隔）",
            "2. 不要尝试猜测哪个是哪个配置",
            "3. 对每个片段的每个维度打 1-5 分",
            "4. 1=很差 2=较差 3=一般 4=较好 5=优秀",
        ],
    }

    # 初始化评分模板
    for rater_id in range(1, n_raters + 1):
        sheet["ratings"][f"rater_{rater_id}"] = {}
        for vid_id in ids:
            sheet["ratings"][f"rater_{rater_id}"][vid_id] = {
                d["name"]: None for d in dimensions
            }

    return sheet


def generate_html_form(sheet: dict, output_path: Path):
    """生成 HTML 评分表单"""
    dims = sheet["dimensions"]
    mapping = sheet["video_mapping"]
    ids = sorted(mapping.keys())

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>HMS 双盲评测 - {sheet['eval_id']}</title>
<style>
body {{ font-family: 'Microsoft YaHei', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #333; }}
.info {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 10px 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
th {{ background: #4CAF50; color: white; }}
select {{ padding: 5px; font-size: 14px; }}
.note {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>HMS 双盲评测表</h1>
<div class="info">
<p><strong>评测ID:</strong> {sheet['eval_id']}</p>
<p><strong>说明:</strong> 观看 concat_blind.mp4，对每个片段（黑场分隔）打分</p>
<ol>
{''.join(f'<li>{inst}</li>' for inst in sheet['instructions'])}
</ol>
</div>

<form id="ratingForm">
<table>
<tr>
<th>片段</th>
{''.join(f'<th>{d["name"]}<br><span class="note">{d["scale"]}</span></th>' for d in dims)}
</tr>
"""
    for vid_id in ids:
        html += f"<tr><td><strong>{vid_id}</strong></td>\n"
        for d in dims:
            html += f'<td><select name="{vid_id}_{d["name"]}">\n'
            html += '<option value="">--</option>\n'
            for score in range(1, 6):
                html += f'<option value="{score}">{score}</option>\n'
            html += "</select></td>\n"
        html += "</tr>\n"

    html += """</table>
<p><strong>备注:</strong></p>
<textarea rows="4" cols="80" placeholder="整体感受、偏好排序等..."></textarea>
<br><br>
<button type="button" onclick="exportJSON()">导出评分JSON</button>
</form>

<script>
function exportJSON() {
    const form = document.getElementById('ratingForm');
    const data = {eval_id: '""" + sheet['eval_id'] + """', ratings: {}};
    const selectElements = form.querySelectorAll('select');
    selectElements.forEach(sel => {
        const [vid, ...dimParts] = sel.name.split('_');
        const dim = dimParts.join('_');
        if (!data.ratings[vid]) data.ratings[vid] = {};
        data.ratings[vid][dim] = sel.value ? parseInt(sel.value) : null;
    });
    data.notes = form.querySelector('textarea').value;
    
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'hms_rating_""" + sheet['eval_id'] + """.json';
    a.click();
}
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(f"  评分表单: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="HMS 双盲评测生成器")
    parser.add_argument("--videos", nargs="+", required=True, help="待评测视频路径")
    parser.add_argument("--labels", nargs="+", help="视频标签（与videos一一对应）")
    parser.add_argument("--output", default="tmp/hms_eval", help="输出目录")
    parser.add_argument("--raters", type=int, default=3, help="评分人数")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    videos = [Path(v) for v in args.videos]
    labels = args.labels or [v.stem for v in videos]

    if len(videos) != len(labels):
        print("[ERROR] videos 和 labels 数量不匹配")
        sys.exit(1)

    # 验证视频存在
    for v in videos:
        if not v.exists():
            print(f"[ERROR] 视频不存在: {v}")
            sys.exit(1)

    print("=== HMS 双盲评测生成 ===")
    print(f"视频数: {len(videos)}")
    for v, l in zip(videos, labels):
        dur = probe_duration(str(v))
        print(f"  {l}: {v.name} ({dur:.1f}s)")

    # 1. 生成随机顺序
    indices = list(range(len(videos)))
    random.shuffle(indices)
    shuffled_videos = [str(videos[i]) for i in indices]
    shuffled_labels = [labels[i] for i in indices]

    print(f"\n随机顺序: {shuffled_labels}")

    # 2. 拼接视频
    concat_path = output_dir / "concat_blind.mp4"
    print("\n生成拼接视频...")
    generate_concat_video(shuffled_videos, str(concat_path))

    # 3. 生成评分表
    print("\n生成评分表...")
    sheet = generate_rating_sheet(shuffled_videos, shuffled_labels, output_dir, args.raters)
    sheet_path = output_dir / "rating_sheet.json"
    sheet_path.write_text(json.dumps(sheet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  评分表: {sheet_path}")

    # 4. 生成 HTML 表单
    html_path = output_dir / "rating_form.html"
    generate_html_form(sheet, html_path)

    print("\n=== 完成 ===")
    print(f"拼接视频: {concat_path}")
    print(f"评分表:   {sheet_path}")
    print(f"评分表单: {html_path}")
    print(f"\n打开 {html_path} 进行评分，或使用 rating_sheet.json 手动填写")


if __name__ == "__main__":
    main()
