"""
向量存储管理
用于索引文件的加载、保存、合并、验证和统计
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def load_index(index_path: str) -> Dict[str, Any]:
    """
    加载索引文件

    参数:
        index_path: 索引文件路径

    返回:
        {
            "success": bool,
            "index_data": dict,
            "error": str (仅在失败时)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "index_data": {}
    }

    try:
        # 检查文件是否存在
        if not os.path.exists(index_path):
            result["error"] = f"索引文件不存在: {index_path}"
            return result

        # 读取JSON文件
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)

        result["index_data"] = index_data
        result["success"] = True

    except json.JSONDecodeError as e:
        result["error"] = f"JSON解析错误: {str(e)}"
    except Exception as e:
        result["error"] = f"索引加载失败: {str(e)}"

    return result


def save_index(
    index_path: str,
    index_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    保存索引文件

    参数:
        index_path: 索引文件路径
        index_data: 索引数据字典

    返回:
        {
            "success": bool,
            "index_path": str,
            "error": str (仅在失败时)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "index_path": index_path
    }

    try:
        # 创建目录（如果不存在）
        output_dir = os.path.dirname(index_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # 更新保存时间
        index_data["build_time"] = datetime.now().isoformat()

        # 原子写入：先写临时文件，成功后重命名
        tmp_path = index_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, index_path)

        result["success"] = True

    except Exception as e:
        result["error"] = f"索引保存失败: {str(e)}"

    return result


def merge_indexes(index_paths: List[str]) -> Dict[str, Any]:
    """
    合并多个索引文件

    参数:
        index_paths: 索引文件路径列表

    返回:
        {
            "success": bool,
            "merged_index": dict,
            "total_items": int,
            "merged_sources": List[str],
            "error": str (仅在失败时)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "merged_index": {},
        "total_items": 0,
        "merged_sources": []
    }

    try:
        # 检查索引路径列表是否为空
        if not index_paths:
            result["error"] = "索引路径列表为空"
            return result

        # 创建合并后的索引结构
        merged_index: Dict[str, Any] = {
            "index_version": "1.0",
            "model": "clip-ViT-L-14",
            "build_time": datetime.now().isoformat(),
            "items": []
        }

        # 用于去重的文件路径集合
        existing_files = set()

        # 遍历所有索引文件
        for index_path in index_paths:
            # 加载索引
            load_result = load_index(index_path)
            if not load_result["success"]:
                print(f"警告: 无法加载索引 {index_path}", file=sys.stderr)
                continue

            index_data = load_result["index_data"]

            # 检查索引是否有效
            if "items" not in index_data:
                print(f"警告: 索引文件格式错误 {index_path}", file=sys.stderr)
                continue

            # 合并items（去重）
            for item in index_data["items"]:
                file_path = item.get("file_path", "")
                if file_path not in existing_files:
                    merged_index["items"].append(item)
                    existing_files.add(file_path)

            result["merged_sources"].append(index_path)

        # 更新统计
        result["total_items"] = len(merged_index["items"])
        result["merged_index"] = merged_index
        result["success"] = True

    except Exception as e:
        result["error"] = f"索引合并失败: {str(e)}"

    return result


def validate_index(index_path: str) -> Dict[str, Any]:
    """
    验证索引文件完整性

    参数:
        index_path: 索引文件路径

    返回:
        {
            "success": bool,
            "valid_items": int,
            "invalid_items": int,
            "missing_files": List[str],
            "invalid_vectors": List[str],
            "error": str (仅在失败时)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "valid_items": 0,
        "invalid_items": 0,
        "missing_files": [],
        "invalid_vectors": []
    }

    try:
        # 加载索引
        load_result = load_index(index_path)
        if not load_result["success"]:
            result["error"] = load_result.get("error", "索引加载失败")
            return result

        index_data = load_result["index_data"]

        # 检查索引结构
        required_fields = ["index_version", "model", "build_time", "items"]
        for field in required_fields:
            if field not in index_data:
                result["error"] = f"索引缺少必要字段: {field}"
                return result

        # 验证每个item
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            vector = item.get("vector", [])
            is_valid = True

            # 检查文件是否存在
            if not file_path or not os.path.exists(file_path):
                result["missing_files"].append(file_path)
                is_valid = False

            # 检查向量是否有效
            if not vector or len(vector) != 512:
                result["invalid_vectors"].append(file_path)
                is_valid = False
            else:
                # 检查向量是否包含非数值
                try:
                    for val in vector:
                        if not isinstance(val, (int, float)):
                            result["invalid_vectors"].append(file_path)
                            is_valid = False
                            break
                except Exception:
                    result["invalid_vectors"].append(file_path)
                    is_valid = False

            if is_valid:
                result["valid_items"] += 1
            else:
                result["invalid_items"] += 1

        result["success"] = True

    except Exception as e:
        result["error"] = f"索引验证失败: {str(e)}"

    return result


def get_index_stats(index_path: str) -> Dict[str, Any]:
    """
    获取索引统计信息

    参数:
        index_path: 索引文件路径

    返回:
        {
            "success": bool,
            "stats": {
                "total_files": int,
                "vector_dim": int,
                "build_time": str,
                "model": str,
                "file_size": int,
                "total_size_mb": float
            },
            "error": str (仅在失败时)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "stats": {}
    }

    try:
        # 加载索引
        load_result = load_index(index_path)
        if not load_result["success"]:
            result["error"] = load_result.get("error", "索引加载失败")
            return result

        index_data = load_result["index_data"]

        # 计算文件大小
        file_size = os.path.getsize(index_path)

        # 统计信息
        stats: Dict[str, Any] = {
            "total_files": len(index_data.get("items", [])),
            "vector_dim": 512,  # CLIP标准维度
            "build_time": index_data.get("build_time", ""),
            "model": index_data.get("model", ""),
            "index_version": index_data.get("index_version", ""),
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2)
        }

        # 统计有效文件数
        valid_count = 0
        total_size = 0
        for item in index_data.get("items", []):
            file_path = item.get("file_path", "")
            if os.path.exists(file_path):
                valid_count += 1
                try:
                    total_size += os.path.getsize(file_path)
                except Exception:
                    pass

        stats["valid_files"] = valid_count
        stats["total_content_size_mb"] = round(total_size / (1024 * 1024), 2)

        result["stats"] = stats
        result["success"] = True

    except Exception as e:
        result["error"] = f"统计信息获取失败: {str(e)}"

    return result


def clean_index(index_path: str) -> Dict[str, Any]:
    """
    清理索引中的失效项（文件不存在）

    参数:
        index_path: 索引文件路径

    返回:
        {
            "success": bool,
            "removed_items": int,
            "remaining_items": int,
            "error": str (仅在失败时)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "removed_items": 0,
        "remaining_items": 0
    }

    try:
        # 加载索引
        load_result = load_index(index_path)
        if not load_result["success"]:
            result["error"] = load_result.get("error", "索引加载失败")
            return result

        index_data = load_result["index_data"]

        # 过滤有效项
        valid_items = []
        for item in index_data.get("items", []):
            file_path = item.get("file_path", "")
            if os.path.exists(file_path):
                valid_items.append(item)
            else:
                result["removed_items"] += 1

        # 更新索引
        index_data["items"] = valid_items
        index_data["build_time"] = datetime.now().isoformat()

        # 保存索引
        save_result = save_index(index_path, index_data)
        if not save_result["success"]:
            result["error"] = save_result.get("error", "索引保存失败")
            return result

        result["remaining_items"] = len(valid_items)
        result["success"] = True

    except Exception as e:
        result["error"] = f"索引清理失败: {str(e)}"

    return result


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python vector_store.py --json-input '<JSON字符串>'")
        print("示例: python vector_store.py --json-input '{\"action\": \"load_index\", \"index_path\": \"index.json\"}'")
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

        result: Dict[str, Any] = {}

        if action == "load_index":
            index_path = input_json.get("index_path", "")
            result = load_index(index_path)

        elif action == "save_index":
            index_path = input_json.get("index_path", "")
            index_data = input_json.get("index_data", {})
            result = save_index(index_path, index_data)

        elif action == "merge_indexes":
            index_paths = input_json.get("index_paths", [])
            result = merge_indexes(index_paths)

            # 如果需要保存合并后的索引
            output_path = input_json.get("output_path", "")
            if output_path and result["success"]:
                save_result = save_index(output_path, result["merged_index"])
                if save_result["success"]:
                    result["merged_index_path"] = output_path

        elif action == "validate_index":
            index_path = input_json.get("index_path", "")
            result = validate_index(index_path)

        elif action == "get_index_stats":
            index_path = input_json.get("index_path", "")
            result = get_index_stats(index_path)

        elif action == "clean_index":
            index_path = input_json.get("index_path", "")
            result = clean_index(index_path)

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