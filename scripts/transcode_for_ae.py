import subprocess, sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ffmpeg = r"C:\ffmpeg\bin\ffmpeg.exe"
src_dir = r"D:\AE-Work\视频素材库\冰海战记新素材"
out_dir = r"D:\AE-Work\视频素材库\冰海战记新素材_AE"  # AE-compatible versions

os.makedirs(out_dir, exist_ok=True)

# Files used in V15 JSX
files_to_convert = [
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p01 S1OP1-MUKANJYO.f30077.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p02 S1ED1-Torches.f30080.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p03 S1OP2-Dark Crow.f30077.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p05 S2OP1-River.f30077.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p07 S2OP2-Paradox.f30080.mp4",
    "vinland_2_冰海战记第一季：最后的封神场面.f30080.mp4",
    "vinland_3_【授权转载】冰海战记第二季最精彩的打戏 托尔芬VS蛇.f30077.mp4",
    "vinland_4_4K_MAD.f30077.mp4",
    "vinland_5_【MAD⧸冰海战记】There's a revolution coming!.f30080.mp4",
]

# Also need the audio file
audio_src = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"

print(f"Source: {src_dir}")
print(f"Output: {out_dir}")
print(f"Files to convert: {len(files_to_convert)}")
print()

for i, fname in enumerate(files_to_convert):
    src_path = os.path.join(src_dir, fname)
    out_path = os.path.join(out_dir, fname)
    
    if not os.path.exists(src_path):
        print(f"[{i+1}/{len(files_to_convert)}] SKIP (not found): {fname[:50]}")
        continue
    
    if os.path.exists(out_path):
        print(f"[{i+1}/{len(files_to_convert)}] EXISTS: {fname[:50]}")
        continue
    
    print(f"[{i+1}/{len(files_to_convert)}] Converting: {fname[:50]}...")
    
    # Transcode HEVC → H.264 (high quality, AE compatible)
    # Using libx264 with CRF 16 (near lossless) + AAC audio
    cmd = [
        ffmpeg, "-y", "-i", src_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        out_path
    ]
    
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    elapsed = time.time() - start
    
    if result.returncode == 0:
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"  OK ({size_mb:.1f} MB, {elapsed:.1f}s)")
    else:
        print(f"  FAILED: {result.stderr[-200:]}")

# Copy audio file
audio_out = os.path.join(out_dir, "ae实战音乐.mp3")
if not os.path.exists(audio_out) and os.path.exists(audio_src):
    import shutil
    shutil.copy2(audio_src, audio_out)
    print(f"\nAudio copied: ae实战音乐.mp3")

print(f"\nDone! Output dir: {out_dir}")
print("Files in output:")
for f in sorted(os.listdir(out_dir)):
    size = os.path.getsize(os.path.join(out_dir, f)) / 1024 / 1024
    print(f"  {f[:60]} ({size:.1f} MB)")
