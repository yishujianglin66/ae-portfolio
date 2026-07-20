"""Whisper 语音识别 - 用 MoviePy 提取音频后转录"""
import os, sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
V17 = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
OUT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_final"
os.makedirs(OUT, exist_ok=True)

# 1. MoviePy 提取音频
print("Step 1: 提取音频...")
from moviepy import VideoFileClip
clip = VideoFileClip(V17)
audio_path = os.path.join(OUT, "v17_audio.wav")
if clip.audio is not None:
    clip.audio.write_audiofile(audio_path, fps=16000, nbytes=2, codec="pcm_s16le", logger=None)
    print(f"  Audio: {os.path.getsize(audio_path)/1024:.0f}KB")
else:
    print("  No audio track!")
    sys.exit(1)
clip.close()

# 2. Whisper 转录
print("Step 2: Whisper 转录...")
import whisper
model = whisper.load_model("tiny")
result = model.transcribe(audio_path, language="ja", verbose=False)
segments = result.get("segments", [])
print(f"  检测到 {len(segments)} 个片段:")
for seg in segments[:8]:
    print(f"  [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text'][:50]}")

# 3. 生成 SRT
srt_lines = []
for i, seg in enumerate(segments):
    st, et = seg["start"], seg["end"]
    sh, sm, ss = int(st//3600), int((st%3600)//60), st%60
    eh, em, es = int(et//3600), int((et%3600)//60), et%60
    srt_lines.append(str(i+1))
    srt_lines.append(f"{sh:02d}:{sm:02d}:{ss:06.3f} --> {eh:02d}:{em:02d}:{es:06.3f}")
    srt_lines.append(seg["text"].strip())
    srt_lines.append("")
srt_file = os.path.join(OUT, "v17_subtitles.srt")
with open(srt_file, "w", encoding="utf-8") as f:
    f.write("\n".join(srt_lines))
print(f"\nSRT: {os.path.getsize(srt_file)} bytes, {len(segments)} lines")
print(f"Saved: {srt_file}")
