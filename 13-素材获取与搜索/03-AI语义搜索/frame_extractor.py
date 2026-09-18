"""
视频帧抽取器
使用OpenCV从视频中提取关键帧，支持等间隔抽取和场景变化检测
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

# 临时帧保存目录
TEMP_FRAME_DIR = "D:/AE-Work/临时帧/"


def ensure_temp_dir() -> None:
    """确保临时帧目录存在"""
    os.makedirs(TEMP_FRAME_DIR, exist_ok=True)


def extract_frames(
    video_path: str,
    interval: float = 5.0,
    max_frames: int = 20
) -> dict[str, Any]:
    """
    从视频中等间隔抽取关键帧

    参数:
        video_path: 视频文件路径
        interval: 间隔秒数，默认5秒
        max_frames: 最大帧数，默认20

    返回:
        包含帧信息和视频元数据的字典:
        {
            "success": bool,
            "frames": [{"frame_path": str, "timestamp": float, "frame_index": int}],
            "video_info": {"duration": float, "fps": float, "width": int, "height": int},
            "error": str (仅在失败时)
        }
    """
    ensure_temp_dir()

    result: dict[str, Any] = {
        "success": False,
        "frames": [],
        "video_info": {}
    }

    cap = None
    try:
        # 检查视频文件是否存在
        if not os.path.exists(video_path):
            result["error"] = f"视频文件不存在: {video_path}"
            return result

        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result["error"] = f"无法打开视频文件: {video_path}"
            cap = None
            return result

        # 获取视频基本信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0

        result["video_info"] = {
            "duration": round(duration, 2),
            "fps": round(fps, 2),
            "width": width,
            "height": height
        }

        # 计算需要抽取的帧位置
        frames_to_extract = []
        current_time = 0.0
        frame_interval = int(fps * interval)  # 帧间隔

        while current_time < duration and len(frames_to_extract) < max_frames:
            frame_index = int(current_time * fps)
            if frame_index < frame_count:
                frames_to_extract.append((frame_index, current_time))
            current_time += interval

        # 视频文件名（不含扩展名）
        video_name = Path(video_path).stem

        # 抽取并保存帧
        for idx, (frame_index, timestamp) in enumerate(frames_to_extract):
            # 设置帧位置
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

            # 读取帧
            ret, frame = cap.read()
            if not ret:
                continue

            # 生成帧文件名
            frame_filename = f"{video_name}_frame_{idx}_{timestamp:.3f}.png"
            frame_path = os.path.join(TEMP_FRAME_DIR, frame_filename)

            # 保存帧（PNG无损格式）
            cv2.imwrite(frame_path, frame)

            result["frames"].append({
                "frame_path": frame_path,
                "timestamp": round(timestamp, 3),
                "frame_index": frame_index
            })

        result["success"] = True

    except Exception as e:
        result["error"] = f"帧抽取失败: {str(e)}"
    finally:
        if cap is not None:
            cap.release()

    return result


def extract_key_frames(
    video_path: str,
    threshold: float = 30.0,
    max_frames: int = 30
) -> dict[str, Any]:
    """
    提取关键帧（基于场景变化检测）
    使用帧差法检测场景切换点，提取切换后的帧

    参数:
        video_path: 视频文件路径
        threshold: 场景变化阈值（0-255），默认30.0
        max_frames: 最大帧数，默认30

    返回:
        包含帧信息和视频元数据的字典
    """
    ensure_temp_dir()

    result: dict[str, Any] = {
        "success": False,
        "frames": [],
        "video_info": {}
    }

    cap = None
    try:
        # 检查视频文件是否存在
        if not os.path.exists(video_path):
            result["error"] = f"视频文件不存在: {video_path}"
            return result

        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result["error"] = f"无法打开视频文件: {video_path}"
            cap = None
            return result

        # 获取视频基本信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0

        result["video_info"] = {
            "duration": round(duration, 2),
            "fps": round(fps, 2),
            "width": width,
            "height": height
        }

        # 视频文件名（不含扩展名）
        video_name = Path(video_path).stem

        # 读取第一帧
        ret, prev_frame = cap.read()
        if not ret:
            result["error"] = "无法读取视频帧"
            return result

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        frame_index = 0

        # 保存第一帧
        frame_filename = f"{video_name}_frame_0_0.000.png"
        frame_path = os.path.join(TEMP_FRAME_DIR, frame_filename)
        cv2.imwrite(frame_path, prev_frame)

        result["frames"].append({
            "frame_path": frame_path,
            "timestamp": 0.0,
            "frame_index": 0
        })

        # 遍历视频检测场景变化
        while cap.isOpened() and len(result["frames"]) < max_frames:
            ret, curr_frame = cap.read()
            if not ret:
                break

            frame_index += 1
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

            # 计算帧差
            frame_diff = cv2.absdiff(prev_gray, curr_gray)
            mean_diff = cv2.mean(frame_diff)[0]

            # 如果帧差超过阈值，保存为关键帧
            if mean_diff > threshold:
                timestamp = frame_index / fps
                frame_filename = f"{video_name}_frame_{len(result['frames'])}_{timestamp:.3f}.png"
                frame_path = os.path.join(TEMP_FRAME_DIR, frame_filename)
                cv2.imwrite(frame_path, curr_frame)

                result["frames"].append({
                    "frame_path": frame_path,
                    "timestamp": round(timestamp, 3),
                    "frame_index": frame_index
                })

            prev_gray = curr_gray

        result["success"] = True

    except Exception as e:
        result["error"] = f"关键帧提取失败: {str(e)}"
    finally:
        if cap is not None:
            cap.release()

    return result


def extract_all_frames_from_directory(
    directory: str,
    interval: float = 5.0,
    max_frames_per_video: int = 20,
    method: str = "interval"
) -> dict[str, Any]:
    """
    批量处理目录下所有视频

    参数:
        directory: 视频目录路径
        interval: 间隔秒数，默认5秒
        max_frames_per_video: 每个视频最大帧数，默认20
        method: 抽取方法，"interval"（等间隔）或 "key"（场景检测）

    返回:
        包含所有视频处理结果的字典
    """
    result: dict[str, Any] = {
        "success": False,
        "videos": [],
        "total_frames": 0,
        "errors": []
    }

    try:
        # 检查目录是否存在
        if not os.path.exists(directory):
            result["errors"].append(f"目录不存在: {directory}")
            return result

        # 支持的视频格式
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}

        # 遍历目录
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            file_ext = Path(filename).suffix.lower()

            # 跳过非视频文件
            if file_ext not in video_extensions:
                continue

            # 根据方法选择抽取函数
            if method == "key":
                video_result = extract_key_frames(
                    file_path,
                    max_frames=max_frames_per_video
                )
            else:
                video_result = extract_frames(
                    file_path,
                    interval=interval,
                    max_frames=max_frames_per_video
                )

            if video_result["success"]:
                result["videos"].append({
                    "video_file": filename,
                    "frames": video_result["frames"],
                    "video_info": video_result["video_info"]
                })
                result["total_frames"] += len(video_result["frames"])
            else:
                result["errors"].append(f"{filename}: {video_result.get('error', '未知错误')}")

        result["success"] = len(result["videos"]) > 0

    except Exception as e:
        result["errors"].append(f"批量处理失败: {str(e)}")

    return result


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python frame_extractor.py --json-input '<JSON字符串>'")
        print("示例: python frame_extractor.py --json-input '{\"action\": \"extract_frames\", \"video_path\": \"test.mp4\"}'")
        sys.exit(1)

    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)

    if len(sys.argv) < 3:
        print("错误: 缺少JSON输入")
        sys.exit(1)

    try:
        # 解析JSON输入
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")

        result: dict[str, Any] = {}

        if action == "extract_frames":
            video_path = input_json.get("video_path", "")
            interval = input_json.get("interval", 5.0)
            max_frames = input_json.get("max_frames", 20)
            result = extract_frames(video_path, interval, max_frames)

        elif action == "extract_key_frames":
            video_path = input_json.get("video_path", "")
            threshold = input_json.get("threshold", 30.0)
            max_frames = input_json.get("max_frames", 30)
            result = extract_key_frames(video_path, threshold, max_frames)

        elif action == "extract_all_frames_from_directory":
            directory = input_json.get("directory", "")
            interval = input_json.get("interval", 5.0)
            max_frames_per_video = input_json.get("max_frames_per_video", 20)
            method = input_json.get("method", "interval")
            result = extract_all_frames_from_directory(
                directory, interval, max_frames_per_video, method
            )

        else:
            result = {
                "success": False,
                "error": f"未知操作: {action}"
            }

        # 输出JSON结果
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "error": f"JSON解析错误: {str(e)}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"执行错误: {str(e)}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()