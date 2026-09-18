import os

import numpy as np
from PIL import Image

frames_dir = r"D:\AE-Work\视频素材库\frames"

frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])

print(f"📸 共提取 {len(frames)} 帧\n")

for i, frame in enumerate(frames):
    frame_path = os.path.join(frames_dir, frame)
    
    try:
        img = Image.open(frame_path)
        width, height = img.size
        img_array = np.array(img)
        
        center = img_array[height//3:2*height//3, width//3:2*width//3]
        avg_color = np.mean(center, axis=(0, 1))
        brightness = np.mean(img_array)
        
        print(f"帧 {i+1:02d} [{frame}]")
        print(f"  分辨率: {width}x{height}")
        print(f"  中心区域颜色: R={int(avg_color[0]):3d} G={int(avg_color[1]):3d} B={int(avg_color[2]):3d}")
        print(f"  平均亮度: {brightness:.1f}")
        
        if i > 0:
            prev_frame = os.path.join(frames_dir, frames[i-1])
            prev_img = Image.open(prev_frame)
            prev_array = np.array(prev_img)
            
            diff = np.abs(img_array.astype(np.int16) - prev_array.astype(np.int16))
            diff_percent = (np.sum(diff > 30) / (height * width * 3)) * 100
            print(f"  与前帧差异: {diff_percent:.2f}%")
            if diff_percent > 30:
                print("  ⚠️ 检测到场景切换!")
        
        print()
        
    except Exception as e:
        print(f"帧 {i+1:02d} [{frame}] - 读取失败: {e}")
        print()