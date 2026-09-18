import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import settings
from src.engines.ffmpeg.engine import FFmpegEngine

INPUT = Path(r"D:\AE-Work\output\TextFX_Showcase.mp4")
OUTPUT = Path(r"D:\AE-Work\output\deliver\TextFX_Showcase_Short_60fps.mp4")

SEGMENTS = [
    {"name": "cyberpunk", "start": 1.5, "duration": 2.0},
    {"name": "ink", "start": 4.0, "duration": 2.0},
    {"name": "neon_glow", "start": 6.0, "duration": 2.0},
    {"name": "hologram", "start": 11.0, "duration": 2.0},
    {"name": "fire_ice", "start": 15.5, "duration": 2.5},
    {"name": "textfx_logo", "start": 21.5, "duration": 2.5},
]


async def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = settings.get_ffmpeg()
    ffmpeg = FFmpegEngine(ffmpeg_exe)

    print("[1/2] 从原视频提取 6 个精华片段并 1.35x 加速 + 画质增强...")

    with tempfile.TemporaryDirectory(prefix="textfx_short_") as tmp_dir:
        tmp = Path(tmp_dir)
        seg_paths = []
        for i, seg in enumerate(SEGMENTS):
            seg_path = tmp / f"seg_{i:02d}.mp4"
            result = await ffmpeg.convert(
                input_path=INPUT,
                output_path=seg_path,
                codec="libx264",
                crf=14,
                preset="medium",
                extra_args=[
                    "-ss", str(seg["start"]),
                    "-t", str(seg["duration"]),
                    "-vf", (
                        "setpts=PTS/1.35,"
                        "fps=30,"
                        "scale=1920:1080:flags=lanczos,"
                        "unsharp=3:3:0.8:3:3:0.5,"
                        "eq=contrast=1.12:saturation=1.18:brightness=0.03"
                    ),
                    "-pix_fmt", "yuv420p",
                    "-an",
                    "-movflags", "+faststart",
                    "-g", "30",
                    "-keyint_min", "30",
                ],
            )
            if not result.success:
                print(f"  片段 {seg['name']} 失败: {result.error}")
                return
            seg_paths.append(seg_path)
            size_kb = seg_path.stat().st_size / 1024
            print(f"  ✓ {seg['name']}: {size_kb:.0f} KB")

        concat_list = tmp / "list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in seg_paths:
                f.write(f"file '{p.as_posix()}'\n")

        print("[2/2] 拼接 + 运动补偿补帧到 60fps + 最终画质优化...")
        cmd = [
            str(ffmpeg_exe),
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264",
            "-crf", "16",
            "-preset", "slow",
            "-bf", "2",
            "-g", "60",
            "-keyint_min", "30",
            "-sc_threshold", "0",
            "-vf", (
                "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                "unsharp=5:5:1.0:5:5:0.6,"
                "eq=contrast=1.06:saturation=1.1,"
                "format=yuv420p"
            ),
            "-an",
            "-movflags", "+faststart",
            str(OUTPUT),
        ]
        code, stdout, stderr, _ = await asyncio.to_thread(
            ffmpeg._run_subprocess, cmd, timeout=3600
        )
        if code != 0:
            print(f"  最终处理失败 (exit={code})")
            print(stderr[-1000:] if stderr else "no stderr")
            return

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\n✓ 完成! 输出: {OUTPUT}")
    print(f"  文件大小: {size_mb:.2f} MB")


if __name__ == "__main__":
    asyncio.run(main())
