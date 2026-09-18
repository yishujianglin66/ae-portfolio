"""
素材库向量索引构建器
使用CLIP模型为图片和视频帧构建向量索引
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

# 延迟导入sentence_transformers，避免未安装时崩溃
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


# CLIP模型名称
MODEL_NAME = "clip-ViT-L-14"
# 向量维度（CLIP标准输出）
VECTOR_DIM = 512
# 批处理大小
BATCH_SIZE = 50
# 支持的图片格式
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}


def get_model() -> Any | None:
    """
    加载CLIP模型

    返回:
        SentenceTransformer模型对象，失败返回None
    """
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        raise ImportError("sentence_transformers 未安装，请运行: pip install sentence-transformers")

    try:
        # 加载模型（首次运行会下载约1GB）
        model = SentenceTransformer(MODEL_NAME)
        return model
    except Exception as e:
        print(f"模型加载失败: {str(e)}", file=sys.stderr)
        return None


def get_image_metadata(image_path: str) -> dict[str, Any]:
    """
    获取图片元数据

    参数:
        image_path: 图片路径

    返回:
        包含文件名、大小、尺寸等信息的字典
    """
    metadata = {}
    try:
        # 文件名和大小
        file_stat = os.stat(image_path)
        metadata["file_name"] = Path(image_path).name
        metadata["file_size"] = file_stat.st_size

        # 图片尺寸
        with Image.open(image_path) as img:
            metadata["width"] = img.width
            metadata["height"] = img.height

    except Exception:
        pass

    return metadata


def get_vector(model: Any, image_path: str) -> list[float] | None:
    """
    计算单张图片的CLIP向量

    参数:
        model: CLIP模型对象
        image_path: 图片路径

    返回:
        512维向量列表，失败返回None
    """
    try:
        # 读取图片
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # 编码为向量
        vector = model.encode(image, convert_to_numpy=True)

        # 转换为列表
        return vector.tolist()

    except Exception as e:
        print(f"向量计算失败 {image_path}: {str(e)}", file=sys.stderr)
        return None


def build_index(
    media_directory: str,
    output_path: str,
    batch_size: int = BATCH_SIZE
) -> dict[str, Any]:
    """
    为素材库所有图片/视频帧建立CLIP向量索引

    参数:
        media_directory: 素材目录
        output_path: 索引文件保存路径
        batch_size: 批处理大小，默认50

    返回:
        {
            "success": bool,
            "index_path": str,
            "total_items": int,
            "failed_items": List[str],
            "error": str (仅在失败时)
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "index_path": output_path,
        "total_items": 0,
        "failed_items": []
    }

    try:
        # 检查目录是否存在
        if not os.path.exists(media_directory):
            result["error"] = f"素材目录不存在: {media_directory}"
            return result

        # 加载模型
        model = get_model()
        if model is None:
            result["error"] = "CLIP模型加载失败"
            return result

        # 收集所有图片文件
        image_files = []
        for root, _, files in os.walk(media_directory):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = Path(file).suffix.lower()
                if file_ext in IMAGE_EXTENSIONS:
                    image_files.append(file_path)

        if not image_files:
            result["error"] = f"目录中未找到图片文件: {media_directory}"
            return result

        # 构建索引
        index_data: dict[str, Any] = {
            "index_version": "1.0",
            "model": MODEL_NAME,
            "build_time": datetime.now().isoformat(),
            "items": []
        }

        # 批处理图片
        for i in range(0, len(image_files), batch_size):
            batch = image_files[i:i + batch_size]

            for image_path in batch:
                # 计算向量
                vector = get_vector(model, image_path)
                if vector is None:
                    result["failed_items"].append(image_path)
                    continue

                # 获取元数据
                metadata = get_image_metadata(image_path)

                # 添加到索引
                index_data["items"].append({
                    "file_path": image_path,
                    "vector": vector,
                    "metadata": metadata
                })

                result["total_items"] += 1

        # 保存索引
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        result["success"] = True

    except Exception as e:
        result["error"] = f"索引构建失败: {str(e)}"

    return result


def update_index(
    index_path: str,
    new_files: list[str]
) -> dict[str, Any]:
    """
    增量更新索引（只计算新文件）

    参数:
        index_path: 索引文件路径
        new_files: 新文件路径列表

    返回:
        {
            "success": bool,
            "added_items": int,
            "failed_items": List[str],
            "error": str (仅在失败时)
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "added_items": 0,
        "failed_items": []
    }

    try:
        # 检查索引文件是否存在
        if not os.path.exists(index_path):
            result["error"] = f"索引文件不存在: {index_path}"
            return result

        # 加载现有索引
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)

        # 获取已索引的文件路径
        existing_files = {item["file_path"] for item in index_data["items"]}

        # 过滤出真正的新文件
        files_to_add = [f for f in new_files if f not in existing_files]

        if not files_to_add:
            result["success"] = True
            return result

        # 加载模型
        model = get_model()
        if model is None:
            result["error"] = "CLIP模型加载失败"
            return result

        # 为新文件计算向量
        for image_path in files_to_add:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                result["failed_items"].append(image_path)
                continue

            # 计算向量
            vector = get_vector(model, image_path)
            if vector is None:
                result["failed_items"].append(image_path)
                continue

            # 获取元数据
            metadata = get_image_metadata(image_path)

            # 添加到索引
            index_data["items"].append({
                "file_path": image_path,
                "vector": vector,
                "metadata": metadata
            })

            result["added_items"] += 1

        # 更新构建时间
        index_data["build_time"] = datetime.now().isoformat()

        # 保存索引
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        result["success"] = True

    except Exception as e:
        result["error"] = f"索引更新失败: {str(e)}"

    return result


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python clip_indexer.py --json-input '<JSON字符串>'")
        print("示例: python clip_indexer.py --json-input '{\"action\": \"build_index\", \"media_directory\": \"./images\", \"output_path\": \"index.json\"}'")
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

        if action == "build_index":
            media_directory = input_json.get("media_directory", "")
            output_path = input_json.get("output_path", "")
            batch_size = input_json.get("batch_size", BATCH_SIZE)
            result = build_index(media_directory, output_path, batch_size)

        elif action == "update_index":
            index_path = input_json.get("index_path", "")
            new_files = input_json.get("new_files", [])
            result = update_index(index_path, new_files)

        elif action == "get_vector":
            # 单独计算向量（需要指定图片路径）
            model = get_model()
            if model is None:
                result = {
                    "success": False,
                    "error": "CLIP模型加载失败"
                }
            else:
                image_path = input_json.get("image_path", "")
                vector = get_vector(model, image_path)
                if vector is not None:
                    result = {
                        "success": True,
                        "image_path": image_path,
                        "vector": vector,
                        "vector_dim": len(vector)
                    }
                else:
                    result = {
                        "success": False,
                        "error": f"向量计算失败: {image_path}"
                    }

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