"""SAM2 真实推理验证脚本

验证流程：
1. 从短视频中抽取帧
2. 初始化 SAM2 video predictor
3. 在第 0 帧添加点提示（画面中心）
4. 逐帧传播生成遮罩
5. 验证遮罩文件有效（非空、有白色像素）
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# 设置路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "puppet-automation"))

import cv2
import torch


def main():
    print("=" * 60)
    print("SAM2 真实推理验证")
    print("=" * 60)

    # 1. 选择测试视频（用短片段）
    test_video = Path(r"D:\AE-Work\视频素材库\冰海战记片段\clip_1_1.mp4")
    if not test_video.exists():
        # 回退到其他视频
        test_video = Path(r"D:\AE-Work\视频素材库\抖音_一拳超人_埼玉.mp4")
    
    print(f"\n[1] 测试视频: {test_video.name}")
    
    # 获取视频信息
    cap = cv2.VideoCapture(str(test_video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    print(f"    分辨率: {width}x{height} | FPS: {fps:.1f} | 帧数: {frame_count}")
    
    # 2. 抽取前 30 帧（限制处理量加快验证速度）
    frames_dir = Path(r"D:\AE-Work\output\sam2_test\frames")
    # 清理旧文件（可能有旧命名格式的帧）
    if frames_dir.exists():
        for f in frames_dir.glob("*.jpg"):
            f.unlink()
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[2] 抽取前 30 帧到 {frames_dir}")
    cap = cv2.VideoCapture(str(test_video))
    extracted = 0
    for i in range(min(30, frame_count)):
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imwrite(str(frames_dir / f"{i:05d}.jpg"), frame)
        extracted += 1
    cap.release()
    print(f"    抽取完成: {extracted} 帧")
    
    # 3. 初始化 SAM2
    print("\n[3] 初始化 SAM2 video predictor")
    checkpoint = Path(r"D:\AE-Work\models\sam2\sam2.1_hiera_base_plus.pt")
    model_cfg = "configs/sam2.1/sam2.1_hiera_b+.yaml"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"    Checkpoint: {checkpoint.name}")
    print(f"    Device: {device}")
    
    from sam2.build_sam import build_sam2_video_predictor
    
    t0 = time.time()
    predictor = build_sam2_video_predictor(
        config_file=model_cfg,
        ckpt_path=str(checkpoint),
        device=device,
    )
    t1 = time.time()
    print(f"    模型加载耗时: {t1-t0:.1f}s")
    
    # 4. 初始化视频状态
    print("\n[4] 初始化视频状态")
    with torch.inference_mode():
        inference_state = predictor.init_state(video_path=str(frames_dir))
        print("    状态初始化完成")
        
        # 5. 添加点提示（画面中心，假设主体在中心区域）
        center_x, center_y = width // 2, height // 2
        print(f"\n[5] 添加点提示: ({center_x}, {center_y}) 在第 0 帧")
        predictor.add_new_points_or_box(
            inference_state=inference_state,
            frame_idx=0,
            obj_id=0,
            points=[[center_x, center_y]],
            labels=[1],  # 正点
        )
        
        # 6. 逐帧传播
        print("\n[6] 逐帧传播生成遮罩")
        output_dir = Path(r"D:\AE-Work\output\sam2_test\masks")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        mask_count = 0
        t2 = time.time()
        for frame_idx, obj_ids, mask_logits in predictor.propagate_in_video(inference_state):
            mask = (mask_logits[0] > 0.0).cpu().numpy().astype("uint8") * 255
            # 确保是 2D 数组
            mask = mask.squeeze()
            mask_path = output_dir / f"mask_{frame_idx:05d}.png"
            cv2.imwrite(str(mask_path), mask)
            
            # 统计遮罩覆盖率
            white_pixels = int((mask > 0).sum())
            total_pixels = int(mask.size)
            coverage = white_pixels / total_pixels * 100 if total_pixels > 0 else 0
            
            mask_count += 1
            if mask_count <= 5 or mask_count % 10 == 0:
                print(f"    帧 {frame_idx}: 遮罩覆盖率 {coverage:.1f}% ({white_pixels}/{total_pixels} 像素)")
        
        t3 = time.time()
        print(f"\n    遮罩生成完成: {mask_count} 帧 | 耗时: {t3-t2:.1f}s | 平均: {(t3-t2)/max(mask_count,1):.2f}s/帧")
    
    # 7. 验证遮罩文件
    print("\n[7] 验证遮罩文件")
    masks = sorted(output_dir.glob("*.png"))
    print(f"    文件数: {len(masks)}")
    
    if len(masks) == 0:
        print("    [FAIL] 没有生成任何遮罩文件")
        return 1
    
    # 检查每个遮罩是否有效
    valid_masks = 0
    total_coverage = 0
    for m in masks:
        img = cv2.imread(str(m), cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"    [FAIL] {m.name} 无法读取")
            continue
        white = (img > 0).sum()
        total = img.shape[0] * img.shape[1]
        cov = white / total * 100
        total_coverage += cov
        if white > 0:
            valid_masks += 1
    
    avg_coverage = total_coverage / len(masks)
    print(f"    有效遮罩: {valid_masks}/{len(masks)}")
    print(f"    平均覆盖率: {avg_coverage:.1f}%")
    
    if valid_masks == len(masks) and valid_masks > 0:
        print(f"\n{'=' * 60}")
        print("  ✅ SAM2 真实推理验证通过！")
        print(f"  生成了 {valid_masks} 帧真实遮罩，平均覆盖率 {avg_coverage:.1f}%")
        print(f"  遮罩目录: {output_dir}")
        print(f"{'=' * 60}")
        
        # 清理 GPU
        del predictor
        torch.cuda.empty_cache()
        return 0
    else:
        print(f"\n{'=' * 60}")
        print("  ❌ SAM2 推理验证失败：部分遮罩无效")
        print(f"{'=' * 60}")
        del predictor
        torch.cuda.empty_cache()
        return 1


if __name__ == "__main__":
    sys.exit(main())
