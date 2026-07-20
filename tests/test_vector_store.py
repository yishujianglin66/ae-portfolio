"""向量存储单元测试"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

from vector_store import (
    load_index,
    save_index,
    merge_indexes,
    validate_index,
    get_index_stats,
    clean_index,
)


class TestLoadIndex(unittest.TestCase):
    """索引加载测试"""

    def test_load_nonexistent(self):
        result = load_index("/nonexistent/path/index.json")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result.get("error", ""))

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            result = load_index(temp_path)
            self.assertFalse(result["success"])
            self.assertIn("解析错误", result.get("error", ""))
        finally:
            os.unlink(temp_path)

    def test_load_valid_index(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "index_version": "1.0",
                "model": "clip-ViT-L-14",
                "build_time": "2024-01-01T00:00:00",
                "items": []
            }, f)
            temp_path = f.name

        try:
            result = load_index(temp_path)
            self.assertTrue(result["success"])
            self.assertIn("index_version", result["index_data"])
            self.assertIn("items", result["index_data"])
        finally:
            os.unlink(temp_path)


class TestSaveIndex(unittest.TestCase):
    """索引保存测试"""

    def test_save_index(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = os.path.join(tmp_dir, "test_index.json")
            index_data = {
                "index_version": "1.0",
                "model": "clip-ViT-L-14",
                "items": []
            }

            result = save_index(index_path, index_data)
            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(index_path))

            with open(index_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            self.assertEqual(saved_data["index_version"], "1.0")
            self.assertIn("build_time", saved_data)

    def test_save_index_with_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = os.path.join(tmp_dir, "nested", "path", "test_index.json")
            index_data = {"items": []}

            result = save_index(index_path, index_data)
            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(index_path))

    def test_save_index_atomic_no_tmp_residue(self):
        """原子写入成功后不应残留 .tmp 文件"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = os.path.join(tmp_dir, "test_index.json")
            index_data = {"index_version": "1.0", "items": [{"file_path": "x.mp4", "vector": [0.1] * 512}]}

            result = save_index(index_path, index_data)
            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(index_path))
            # 原子写入后临时文件应已被重命名，不存在残留
            self.assertFalse(os.path.exists(index_path + ".tmp"))

    def test_save_index_preserves_existing_on_overwrite(self):
        """覆盖写入时原文件内容应被完整替换，不留半截数据"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = os.path.join(tmp_dir, "test_index.json")
            old_data = {"index_version": "1.0", "items": [{"file_path": "old.mp4", "vector": [0.1] * 512}]}
            save_index(index_path, old_data)

            new_data = {"index_version": "2.0", "items": [{"file_path": "new.mp4", "vector": [0.2] * 512}]}
            result = save_index(index_path, new_data)
            self.assertTrue(result["success"])

            with open(index_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["index_version"], "2.0")
            self.assertEqual(len(saved["items"]), 1)
            self.assertEqual(saved["items"][0]["file_path"], "new.mp4")


class TestMergeIndexes(unittest.TestCase):
    """索引合并测试"""

    def test_merge_empty_list(self):
        result = merge_indexes([])
        self.assertFalse(result["success"])
        self.assertIn("为空", result.get("error", ""))

    def test_merge_single_index(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = os.path.join(tmp_dir, "index1.json")
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump({
                    "index_version": "1.0",
                    "model": "clip-ViT-L-14",
                    "build_time": "2024-01-01",
                    "items": [{"file_path": "file1.mp4", "vector": [0.1] * 512}]
                }, f)

            result = merge_indexes([index_path])
            self.assertTrue(result["success"])
            self.assertEqual(result["total_items"], 1)
            self.assertEqual(len(result["merged_index"]["items"]), 1)

    def test_merge_multiple_indexes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index1_path = os.path.join(tmp_dir, "index1.json")
            with open(index1_path, "w", encoding="utf-8") as f:
                json.dump({
                    "index_version": "1.0",
                    "model": "clip-ViT-L-14",
                    "build_time": "2024-01-01",
                    "items": [{"file_path": "file1.mp4", "vector": [0.1] * 512}]
                }, f)

            index2_path = os.path.join(tmp_dir, "index2.json")
            with open(index2_path, "w", encoding="utf-8") as f:
                json.dump({
                    "index_version": "1.0",
                    "model": "clip-ViT-L-14",
                    "build_time": "2024-01-02",
                    "items": [{"file_path": "file2.mp4", "vector": [0.2] * 512}]
                }, f)

            result = merge_indexes([index1_path, index2_path])
            self.assertTrue(result["success"])
            self.assertEqual(result["total_items"], 2)
            self.assertEqual(len(result["merged_sources"]), 2)

    def test_merge_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index1_path = os.path.join(tmp_dir, "index1.json")
            with open(index1_path, "w", encoding="utf-8") as f:
                json.dump({
                    "index_version": "1.0",
                    "model": "clip-ViT-L-14",
                    "build_time": "2024-01-01",
                    "items": [{"file_path": "same_file.mp4", "vector": [0.1] * 512}]
                }, f)

            index2_path = os.path.join(tmp_dir, "index2.json")
            with open(index2_path, "w", encoding="utf-8") as f:
                json.dump({
                    "index_version": "1.0",
                    "model": "clip-ViT-L-14",
                    "build_time": "2024-01-02",
                    "items": [{"file_path": "same_file.mp4", "vector": [0.2] * 512}]
                }, f)

            result = merge_indexes([index1_path, index2_path])
            self.assertTrue(result["success"])
            self.assertEqual(result["total_items"], 1)


class TestValidateIndex(unittest.TestCase):
    """索引验证测试"""

    def test_validate_nonexistent(self):
        result = validate_index("/nonexistent/path/index.json")
        self.assertFalse(result["success"])

    def test_validate_missing_fields(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"items": []}, f)
            temp_path = f.name

        try:
            result = validate_index(temp_path)
            self.assertFalse(result["success"])
            self.assertIn("缺少", result.get("error", ""))
        finally:
            os.unlink(temp_path)

    def test_validate_valid_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "index_version": "1.0",
                "model": "clip-ViT-L-14",
                "build_time": "2024-01-01",
                "items": []
            }, f)
            temp_path = f.name

        try:
            result = validate_index(temp_path)
            self.assertTrue(result["success"])
            self.assertEqual(result["valid_items"], 0)
            self.assertEqual(result["invalid_items"], 0)
        finally:
            os.unlink(temp_path)

    def test_validate_invalid_vector(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "index_version": "1.0",
                "model": "clip-ViT-L-14",
                "build_time": "2024-01-01",
                "items": [
                    {"file_path": "/nonexistent/file.mp4", "vector": [0.1] * 512},
                    {"file_path": "/nonexistent/file2.mp4", "vector": [0.1] * 256},
                ]
            }, f)
            temp_path = f.name

        try:
            result = validate_index(temp_path)
            self.assertTrue(result["success"])
            self.assertEqual(result["valid_items"], 0)
            self.assertEqual(result["invalid_items"], 2)
            self.assertEqual(len(result["missing_files"]), 2)
            self.assertEqual(len(result["invalid_vectors"]), 1)
        finally:
            os.unlink(temp_path)


class TestGetIndexStats(unittest.TestCase):
    """索引统计测试"""

    def test_stats_nonexistent(self):
        result = get_index_stats("/nonexistent/path/index.json")
        self.assertFalse(result["success"])

    def test_stats_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "index_version": "1.0",
                "model": "clip-ViT-L-14",
                "build_time": "2024-01-01",
                "items": []
            }, f)
            temp_path = f.name

        try:
            result = get_index_stats(temp_path)
            self.assertTrue(result["success"])
            self.assertIn("total_files", result["stats"])
            self.assertIn("file_size", result["stats"])
            self.assertIn("file_size_mb", result["stats"])
        finally:
            os.unlink(temp_path)


class TestCleanIndex(unittest.TestCase):
    """索引清理测试"""

    def test_clean_nonexistent(self):
        result = clean_index("/nonexistent/path/index.json")
        self.assertFalse(result["success"])

    def test_clean_valid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = os.path.join(tmp_dir, "index.json")
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump({
                    "index_version": "1.0",
                    "model": "clip-ViT-L-14",
                    "build_time": "2024-01-01",
                    "items": [
                        {"file_path": "/nonexistent/file1.mp4", "vector": [0.1] * 512},
                        {"file_path": "/nonexistent/file2.mp4", "vector": [0.2] * 512},
                    ]
                }, f)

            result = clean_index(index_path)
            self.assertTrue(result["success"])
            self.assertEqual(result["removed_items"], 2)
            self.assertEqual(result["remaining_items"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)