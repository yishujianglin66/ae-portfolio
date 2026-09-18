"""
语义搜索引擎
使用CLIP模型进行文本搜索、图片搜索和标签搜索

支持离线模式：
- 通过环境变量 AEK_OFFLINE_MODE=1 或 HF_HUB_OFFLINE=1 启用离线模式
- 离线模式下使用本地模型或模拟向量生成
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

_OFFLINE_MODE = os.environ.get("AEK_OFFLINE_MODE", "").lower() == "true" or \
                os.environ.get("AEK_OFFLINE_MODE", "") == "1" or \
                os.environ.get("HF_HUB_OFFLINE", "").lower() == "true" or \
                os.environ.get("HF_HUB_OFFLINE", "") == "1"

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

MODEL_NAME = "clip-ViT-L-14"
LOCAL_MODEL_DIR = os.environ.get("AEK_CLIP_MODEL_DIR", str(Path.home() / ".cache" / "clip-model"))


class MockModel:
    """模拟CLIP模型，用于离线模式或模型不可用时"""
    
    def encode(self, text_or_image, convert_to_numpy=True):
        if isinstance(text_or_image, str):
            return _text_to_simulated_vector(text_or_image)
        else:
            return _image_to_simulated_vector(text_or_image)


def _text_to_simulated_vector(text: str) -> np.ndarray:
    """基于文本内容生成模拟向量（确定性哈希）"""
    hash_val = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
    seed_val = hash_val % (2**32 - 1)
    np.random.seed(seed_val)
    vector = np.random.randn(512).astype(np.float32)
    vector /= np.linalg.norm(vector)
    return vector


def _image_to_simulated_vector(image) -> np.ndarray:
    """基于图片内容生成模拟向量"""
    try:
        img_array = np.array(image)
        hash_val = int(hashlib.md5(img_array.tobytes()).hexdigest(), 16)
        seed_val = hash_val % (2**32 - 1)
        np.random.seed(seed_val)
        vector = np.random.randn(512).astype(np.float32)
        vector /= np.linalg.norm(vector)
        return vector
    except Exception:
        np.random.seed(42)
        return np.random.randn(512).astype(np.float32)


def get_model() -> Any | None:
    """
    加载CLIP模型

    返回:
        SentenceTransformer模型对象或MockModel，失败返回None
    """
    if _OFFLINE_MODE:
        print("离线模式：使用模拟向量生成", file=sys.stderr)
        return MockModel()

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("sentence_transformers 未安装，使用模拟向量生成", file=sys.stderr)
        return MockModel()

    try:
        local_path = Path(LOCAL_MODEL_DIR)
        if local_path.exists() and len(list(local_path.iterdir())) > 0:
            print(f"从本地加载模型: {LOCAL_MODEL_DIR}", file=sys.stderr)
            model = SentenceTransformer(str(local_path), local_files_only=True)
        else:
            print(f"从HuggingFace加载模型: {MODEL_NAME}", file=sys.stderr)
            model = SentenceTransformer(MODEL_NAME)
        return model
    except Exception as e:
        print(f"模型加载失败，使用模拟向量: {str(e)}", file=sys.stderr)
        return MockModel()


def encode_text(model: Any, text: str) -> np.ndarray | None:
    """
    将文本编码为CLIP向量

    参数:
        model: CLIP模型对象
        text: 文本内容（支持中英文）

    返回:
        向量数组，失败返回None
    """
    try:
        # 使用文本编码器
        vector = model.encode(text, convert_to_numpy=True)
        return vector
    except Exception as e:
        print(f"文本编码失败: {str(e)}", file=sys.stderr)
        return None


def encode_image(model: Any, image_path: str) -> np.ndarray | None:
    """
    将图片编码为CLIP向量

    参数:
        model: CLIP模型对象
        image_path: 图片路径

    返回:
        向量数组，失败返回None
    """
    try:
        # 读取图片
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # 编码为向量
        vector = model.encode(image, convert_to_numpy=True)
        return vector
    except Exception as e:
        print(f"图片编码失败 {image_path}: {str(e)}", file=sys.stderr)
        return None


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    计算两个向量的余弦相似度

    参数:
        v1: 向量1
        v2: 向量2

    返回:
        余弦相似度值（-1到1）
    """
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)

    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0

    similarity = dot_product / (norm_v1 * norm_v2)
    return float(similarity)


def load_index(index_path: str) -> dict[str, Any] | None:
    """
    加载索引文件

    参数:
        index_path: 索引文件路径

    返回:
        索引数据字典，失败返回None
    """
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"索引加载失败: {str(e)}", file=sys.stderr)
        return None


def search(
    query: str,
    index_path: str,
    top_k: int = 10
) -> dict[str, Any]:
    """
    根据自然语言查询搜索素材

    参数:
        query: 中文或英文查询语句
        index_path: 索引文件路径
        top_k: 返回结果数，默认10

    返回:
        {
            "success": bool,
            "query": str,
            "results": [{"file_path": str, "similarity": float, "metadata": dict}],
            "error": str (仅在失败时)
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "query": query,
        "results": []
    }

    try:
        # 加载索引
        index_data = load_index(index_path)
        if index_data is None:
            result["error"] = f"索引文件加载失败: {index_path}"
            return result

        # 检查索引是否有效
        if "items" not in index_data or len(index_data["items"]) == 0:
            result["error"] = "索引为空或格式错误"
            return result

        # 加载模型
        model = get_model()
        if model is None:
            result["error"] = "CLIP模型加载失败"
            return result

        # 编码查询文本
        query_vector = encode_text(model, query)
        if query_vector is None:
            result["error"] = "查询文本编码失败"
            return result

        # 计算相似度
        similarities = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            vector = item.get("vector", [])
            metadata = item.get("metadata", {})

            # 检查文件是否存在
            if not os.path.exists(file_path):
                continue

            # 转换向量
            item_vector = np.array(vector)

            # 计算相似度
            similarity = cosine_similarity(query_vector, item_vector)
            similarities.append({
                "file_path": file_path,
                "similarity": round(similarity, 4),
                "metadata": metadata
            })

        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        # 返回top_k结果
        result["results"] = similarities[:top_k]
        result["success"] = True

    except Exception as e:
        result["error"] = f"搜索失败: {str(e)}"

    return result


def search_by_image(
    image_path: str,
    index_path: str,
    top_k: int = 10
) -> dict[str, Any]:
    """
    图片搜索（以图搜图）

    参数:
        image_path: 查询图片路径
        index_path: 索引文件路径
        top_k: 返回结果数，默认10

    返回:
        {
            "success": bool,
            "query_image": str,
            "results": [{"file_path": str, "similarity": float, "metadata": dict}],
            "error": str (仅在失败时)
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "query_image": image_path,
        "results": []
    }

    try:
        # 检查查询图片是否存在
        if not os.path.exists(image_path):
            result["error"] = f"查询图片不存在: {image_path}"
            return result

        # 加载索引
        index_data = load_index(index_path)
        if index_data is None:
            result["error"] = f"索引文件加载失败: {index_path}"
            return result

        # 检查索引是否有效
        if "items" not in index_data or len(index_data["items"]) == 0:
            result["error"] = "索引为空或格式错误"
            return result

        # 加载模型
        model = get_model()
        if model is None:
            result["error"] = "CLIP模型加载失败"
            return result

        # 编码查询图片
        query_vector = encode_image(model, image_path)
        if query_vector is None:
            result["error"] = "查询图片编码失败"
            return result

        # 计算相似度
        similarities = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            vector = item.get("vector", [])
            metadata = item.get("metadata", {})

            # 跳过自己（如果是同一张图片）
            if file_path == image_path:
                continue

            # 检查文件是否存在
            if not os.path.exists(file_path):
                continue

            # 转换向量
            item_vector = np.array(vector)

            # 计算相似度
            similarity = cosine_similarity(query_vector, item_vector)
            similarities.append({
                "file_path": file_path,
                "similarity": round(similarity, 4),
                "metadata": metadata
            })

        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        # 返回top_k结果
        result["results"] = similarities[:top_k]
        result["success"] = True

    except Exception as e:
        result["error"] = f"图片搜索失败: {str(e)}"

    return result


def search_by_tags(
    tags: list[str],
    index_path: str,
    top_k: int = 10
) -> dict[str, Any]:
    """
    标签搜索（组合多个关键词）

    参数:
        tags: 标签列表（如 ["夕阳", "海滩", "浪漫"]）
        index_path: 索引文件路径
        top_k: 返回结果数，默认10

    返回:
        {
            "success": bool,
            "tags": List[str],
            "results": [{"file_path": str, "similarity": float, "metadata": dict}],
            "error": str (仅在失败时)
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "tags": tags,
        "results": []
    }

    try:
        # 检查标签是否为空
        if not tags:
            result["error"] = "标签列表为空"
            return result

        # 加载索引
        index_data = load_index(index_path)
        if index_data is None:
            result["error"] = f"索引文件加载失败: {index_path}"
            return result

        # 检查索引是否有效
        if "items" not in index_data or len(index_data["items"]) == 0:
            result["error"] = "索引为空或格式错误"
            return result

        # 加载模型
        model = get_model()
        if model is None:
            result["error"] = "CLIP模型加载失败"
            return result

        # 编码每个标签并组合
        tag_vectors = []
        for tag in tags:
            vector = encode_text(model, tag)
            if vector is not None:
                tag_vectors.append(vector)

        if not tag_vectors:
            result["error"] = "所有标签编码失败"
            return result

        # 组合标签向量（平均）
        combined_vector = np.mean(tag_vectors, axis=0)

        # 计算相似度
        similarities = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            vector = item.get("vector", [])
            metadata = item.get("metadata", {})

            # 检查文件是否存在
            if not os.path.exists(file_path):
                continue

            # 转换向量
            item_vector = np.array(vector)

            # 计算相似度
            similarity = cosine_similarity(combined_vector, item_vector)
            similarities.append({
                "file_path": file_path,
                "similarity": round(similarity, 4),
                "metadata": metadata
            })

        # 按相似度排序
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        # 返回top_k结果
        result["results"] = similarities[:top_k]
        result["success"] = True

    except Exception as e:
        result["error"] = f"标签搜索失败: {str(e)}"

    return result


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python clip_searcher.py --json-input '<JSON字符串>'")
        print("示例: python clip_searcher.py --json-input '{\"action\": \"search\", \"query\": \"夕阳下的海滩\", \"index_path\": \"index.json\"}'")
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

        if action == "search":
            query = input_json.get("query", "")
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 10)
            result = search(query, index_path, top_k)

        elif action == "search_by_image":
            image_path = input_json.get("image_path", "")
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 10)
            result = search_by_image(image_path, index_path, top_k)

        elif action == "search_by_tags":
            tags = input_json.get("tags", [])
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 10)
            result = search_by_tags(tags, index_path, top_k)

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