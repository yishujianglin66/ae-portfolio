import subprocess, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ffmpeg = r"C:\ffmpeg\bin\ffmpeg.exe"
clip_dir = r"D:\AE-Work\视频素材库\冰海战记新素材"

# Check codec of one source file
test_file = os.path.join(clip_dir, "vinland_4_4K_MAD.f30077.mp4")
result = subprocess.run(
    [ffmpeg, "-i", test_file],
    capture_output=True, text=True, encoding='utf-8', errors='replace'
)
# ffmpeg prints info to stderr
for line in result.stderr.split('\n'):
    if 'Video:' in line or 'Audio:' in line or 'Stream' in line:
        print(line.strip())
