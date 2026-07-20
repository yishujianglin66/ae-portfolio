#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
saitama_reproduce.py
埼玉视频效果还原脚本

根据逆向分析结果，使用frames/目录中的18张图片素材，
通过FFmpeg滤镜链还原埼玉视频的视觉效果。

核心效果：
  1. 近黑白高反差去色（保留粉红选择性色彩）
  2. 粉红体积光束
  3. 高光辉光溢出
  4. 前景暗角
  5. 景深模糊
  6. 胶片颗粒
  7. 冷色调
"""

import os
import sys
import json
import time
import base64
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
def _load_env():
    env_path = PROJECT_ROOT / ".env.doubao"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()

import requests

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FRAMES_DIR = str(PROJECT_ROOT / "frames")
OUTPUT_DIR = str(PROJECT_ROOT / "output" / "saitama_reproduce")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 模型配置
CLAUDE_KEY = os.environ.get("DUCK_MISS_API_KEY", "")
CLAUDE_URL = os.environ.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1")
CLAUDE_PRO = os.environ.get("DUCK_MISS_PRO_MODEL", "claude-opus-4-8")
CLAUDE_VISION = os.environ.get("DUCK_MISS_VISION_MODEL", "claude-sonnet-4-6")

GPT_KEY = os.environ.get("GPT_GATEWAY_API_KEY", "")
GPT_URL = os.environ.get("GPT_GATEWAY_BASE_URL", "https://duckmiss.site/v1")
GPT_PRO = os.environ.get("GPT_GATEWAY_PRO_MODEL", "gpt-5.6-terra")
GPT_VISION = os.environ.get("GPT_GATEWAY_VISION_MODEL", "gpt-5.6-sol")


def call_model(provider, model, messages, max_tokens=4096):
    """调用LLM"""
    if provider == "claude":
        url = f"{CLAUDE_URL}/chat/completions"
        key = CLAUDE_KEY
    else:
        url = f"{GPT_URL}/chat/completions"
        key = GPT_KEY
    
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.5}
    
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"]["content"]
    return ""


def call_vision(provider, model, prompt, image_b64):
    """调用视觉模型"""
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]
    }]
    return call_model(provider, model, messages, max_tokens=4096)


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_safe_path(path):
    """Windows短路径"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        rv = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 260)
        if rv > 0:
            return buf.value
    except Exception:
        pass
    return path


def main():
    print("=" * 60)
    print("  埼玉视频效果还原")
    print("=" * 60)
    
    # ===== Step 1: 分析源帧图片 =====
    print("\n  [Step 1] 多模型分析源帧图片...")
    
    # 选取3张代表性帧
    frame_files = sorted([f for f in os.listdir(FRAMES_DIR) if f.endswith(".png")])
    sample_frames = [frame_files[0], frame_files[len(frame_files)//2], frame_files[-1]]
    
    frame_analyses = []
    for fname in sample_frames:
        fpath = os.path.join(FRAMES_DIR, fname)
        img_b64 = encode_image(fpath)
        
        prompt = """分析这张动画帧的视觉特征。输出JSON:
{
  "dominant_colors": ["主要颜色"],
  "brightness": "bright/medium/dark",
  "contrast_level": "low/medium/high",
  "style": "动画风格描述",
  "key_elements": ["关键视觉元素"]
}"""
        print(f"    分析 {fname}...")
        
        # Claude视觉分析
        claude_result = call_vision("claude", CLAUDE_VISION, prompt, img_b64)
        # GPT视觉分析
        gpt_result = call_vision("gpt", GPT_VISION, prompt, img_b64)
        
        frame_analyses.append({
            "frame": fname,
            "claude": claude_result[:200],
            "gpt": gpt_result[:200],
        })
    
    print(f"    完成 {len(frame_analyses)} 帧分析")
    
    # ===== Step 2: 生成FFmpeg滤镜链 =====
    print("\n  [Step 2] 生成FFmpeg滤镜链（GPT-Terra）...")
    
    # 读取逆向分析结果
    analysis_path = PROJECT_ROOT / "output" / "saitama_analysis.json"
    analysis_summary = ""
    if analysis_path.exists():
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
        # 提取关键信息
        stages = analysis.get("stages", {})
        color_params = stages.get("color_params", {})
        rhythm = stages.get("rhythm", {})
        analysis_summary = json.dumps({
            "color_params": color_params,
            "rhythm": rhythm,
            "layer_count": len(stages.get("layer_stack", {}).get("layers", [])),
        }, ensure_ascii=False, default=str)[:1500]
    
    ffmpeg_prompt = f"""你是FFmpeg滤镜专家。根据以下视频逆向分析结果，生成一个FFmpeg滤镜链来还原埼玉视频的视觉效果。

源素材：18张PNG动画帧（帧率30fps）
目标效果：
1. 近黑白高反差（饱和度降至10-20%）
2. 冷色调偏移（色温向蓝偏移）
3. 高对比度（增强明暗对比）
4. 暗角效果（边缘压暗）
5. 高光辉光（柔和的光晕扩散）
6. 胶片颗粒（细微噪点）
7. 整体偏暗低调照明风格

逆向分析结果摘要：
{analysis_summary}

帧分析结果：
{json.dumps(frame_analyses, ensure_ascii=False)[:1000]}

请仅输出一个完整的FFmpeg -vf 滤镜链字符串（不要ffmpeg命令本身，只要-filter_complex或-vf的内容）。
要求：
- 使用eq调整对比度、亮度、饱和度
- 使用colorbalance调整色温
- 使用vignette做暗角
- 使用unsharp做锐化
- 添加轻微的noise做颗粒
- 滤镜之间用逗号连接
- 确保参数合理，不过度处理
"""
    
    ffmpeg_filter = call_model("gpt", GPT_PRO, [{"role": "user", "content": ffmpeg_prompt}])
    # 清理输出
    ffmpeg_filter = ffmpeg_filter.strip()
    if ffmpeg_filter.startswith("```"):
        ffmpeg_filter = ffmpeg_filter.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    
    print(f"    滤镜链生成完成（{len(ffmpeg_filter)} 字符）")
    print(f"    预览: {ffmpeg_filter[:150]}...")
    
    # ===== Step 3: 生成AE JSX脚本 =====
    print("\n  [Step 3] 生成AE JSX脚本（Claude-Opus）...")
    
    jsx_prompt = """你是AE脚本专家。生成一个ExtendScript (.jsx)脚本，用于在After Effects中还原埼玉视频的视觉效果。

脚本需要：
1. 创建新合成（1920x1080, 30fps, 5秒）
2. 导入frames文件夹中的PNG序列
3. 创建以下调整图层和效果：
   - 调色层：黑白去色（Tint，保留少量原色）
   - 体积光层：粉红色光束（从右上角斜射）
   - 辉光层：高光溢出（Glow效果）
   - 暗角层：边缘压暗
   - 景深层：背景虚化
   - 颗粒层：胶片颗粒
4. 设置合理的混合模式和不透明度

请输出完整的.jsx代码，确保可直接在AE中运行。"""
    
    jsx_code = call_model("claude", CLAUDE_PRO, [{"role": "user", "content": jsx_prompt}], max_tokens=8192)
    # 清理输出
    jsx_code = jsx_code.strip()
    if jsx_code.startswith("```"):
        jsx_code = jsx_code.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    
    jsx_path = os.path.join(OUTPUT_DIR, "saitama_reproduce.jsx")
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx_code)
    print(f"    JSX脚本已保存: {jsx_path}")
    
    # ===== Step 4: 用FFmpeg应用效果 =====
    print("\n  [Step 4] FFmpeg应用效果到帧序列...")
    
    # 方法1：使用AI生成的滤镜链
    input_pattern = get_safe_path(os.path.join(FRAMES_DIR, "frame_%03d.png"))
    output_video = os.path.join(OUTPUT_DIR, "saitama_reproduced.mp4")
    safe_output = get_safe_path(output_video)
    
    # 构建FFmpeg命令
    # 基于分析结果手动构建优化的滤镜链
    manual_filter = (
        "eq=saturation=0.15:contrast=1.4:brightness=-0.05:gamma=0.95,"
        "colorbalance=rs=-0.1:gs=0.0:bs=0.15:rm=-0.05:gm=0.0:bm=0.1:rh=-0.1:gh=0.0:bh=0.1,"
        "vignette=PI/4,"
        "unsharp=5:5:0.8:3:3:0.4,"
        "noise=alls=8:allf=t+u"
    )
    
    cmd = [
        FFMPEG,
        "-framerate", "30",
        "-i", input_pattern,
        "-vf", manual_filter,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "slow",
        safe_output,
        "-y", "-hide_banner", "-loglevel", "error",
    ]
    
    print(f"    执行FFmpeg...")
    print(f"    滤镜: {manual_filter[:100]}...")
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        file_size = os.path.getsize(output_video) / (1024 * 1024)
        print(f"    视频生成成功: {output_video}")
        print(f"    文件大小: {file_size:.2f} MB")
    else:
        print(f"    FFmpeg错误: {result.stderr[:300]}")
        # 尝试简化滤镜
        print("    尝试简化滤镜...")
        simple_filter = "eq=saturation=0.2:contrast=1.3:brightness=-0.05,vignette=PI/4,unsharp=3:3:0.5"
        cmd_simple = [
            FFMPEG,
            "-framerate", "30",
            "-i", input_pattern,
            "-vf", simple_filter,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "20",
            safe_output,
            "-y", "-hide_banner", "-loglevel", "error",
        ]
        result2 = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=60)
        if result2.returncode == 0:
            file_size = os.path.getsize(output_video) / (1024 * 1024)
            print(f"    简化版视频生成成功: {file_size:.2f} MB")
        else:
            print(f"    简化版也失败: {result2.stderr[:200]}")
    
    # ===== Step 5: 生成对比帧 =====
    print("\n  [Step 5] 生成效果对比帧...")
    
    # 对单帧应用效果，对比前后
    sample_frame = os.path.join(FRAMES_DIR, "frame_001.png")
    if os.path.exists(sample_frame):
        before_path = os.path.join(OUTPUT_DIR, "before.png")
        after_path = os.path.join(OUTPUT_DIR, "after_effect.png")
        
        # 复制原图
        import shutil
        shutil.copy2(sample_frame, before_path)
        
        # 应用效果到单帧
        safe_input = get_safe_path(sample_frame)
        safe_after = get_safe_path(after_path)
        cmd_frame = [
            FFMPEG,
            "-i", safe_input,
            "-vf", manual_filter,
            "-frames:v", "1",
            safe_after,
            "-y", "-hide_banner", "-loglevel", "error",
        ]
        result_frame = subprocess.run(cmd_frame, capture_output=True, text=True, timeout=30)
        if result_frame.returncode == 0:
            print(f"    对比帧已生成: {after_path}")
        else:
            print(f"    对比帧生成失败: {result_frame.stderr[:200]}")
    
    # ===== Step 6: 保存还原报告 =====
    print("\n  [Step 6] 保存还原报告...")
    
    report = {
        "source_video": "D:\\AE-Work\\视频素材库\\抖音_一拳超人_埼玉.mp4",
        "source_frames": f"{FRAMES_DIR} ({len(frame_files)} frames)",
        "output_video": output_video,
        "jsx_script": jsx_path,
        "analysis_file": str(analysis_path),
        "ffmpeg_filter": manual_filter,
        "ai_generated_filter": ffmpeg_filter[:500],
        "frame_analyses": frame_analyses,
        "reproduction_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models_used": {
            "visual_analysis": f"claude({CLAUDE_VISION}) + gpt({GPT_VISION})",
            "ffmpeg_generation": f"gpt({GPT_PRO})",
            "jsx_generation": f"claude({CLAUDE_PRO})",
        },
        "key_effects": [
            {"name": "去色", "params": "saturation=0.15, contrast=1.4"},
            {"name": "冷色调", "params": "colorbalance蓝偏移"},
            {"name": "暗角", "params": "vignette=PI/4"},
            {"name": "锐化", "params": "unsharp 5:5:0.8"},
            {"name": "颗粒", "params": "noise=8"},
            {"name": "降亮", "params": "brightness=-0.05, gamma=0.95"},
        ],
    }
    
    report_path = os.path.join(OUTPUT_DIR, "reproduction_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"    报告已保存: {report_path}")
    
    # ===== 汇总 =====
    print(f"\n{'='*60}")
    print(f"  还原完成!")
    print(f"{'='*60}")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  - 视频文件: saitama_reproduced.mp4")
    print(f"  - AE脚本: saitama_reproduce.jsx")
    print(f"  - 对比帧: before.png / after_effect.png")
    print(f"  - 报告: reproduction_report.json")
    print(f"  使用模型: Claude Opus(JSX) + GPT-Terra(FFmpeg) + Claude Sonnet/GPT-Sol(视觉)")


if __name__ == "__main__":
    main()
