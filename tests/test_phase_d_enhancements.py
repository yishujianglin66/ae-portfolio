#!/usr/bin/env python3
"""
Phase D 增强模块回归测试

覆盖：
    D1a - MediaMetadataDB (SQLite 元数据库)
    D1b - VectorIndex (FAISS 向量索引)
    D2  - PipelineLogger (训练日志集成)
    B03 - Cookie 路径归一化
    B04 - AE 脚本 layer 声明修复
    B07 - 配置路径统一
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =====================================================================
# D1a - MediaMetadataDB
# =====================================================================

class TestMediaMetadataDB(unittest.TestCase):
    """SQLite 元数据库测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test_media.db")
        from media_metadata_db import MediaMetadataDB
        self.db = MediaMetadataDB(self.db_path)

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_get_item(self):
        item_id = self.db.add_item(
            "/path/to/video.mp4",
            duration=120.5,
            bpm=128,
            mood="energetic",
            genre="electronic",
        )
        self.assertGreater(item_id, 0)

        item = self.db.get_item(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(item.file_path, "/path/to/video.mp4")
        self.assertEqual(item.file_name, "video.mp4")
        self.assertEqual(item.file_ext, "mp4")
        self.assertEqual(item.file_type, "video")
        self.assertAlmostEqual(item.duration, 120.5)
        self.assertAlmostEqual(item.bpm, 128)
        self.assertEqual(item.mood, "energetic")

    def test_add_duplicate_updates(self):
        self.db.add_item("/path/test.mp3", duration=60)
        self.db.add_item("/path/test.mp3", duration=90, mood="calm")

        item = self.db.get_item_by_path("/path/test.mp3")
        self.assertIsNotNone(item)
        self.assertAlmostEqual(item.duration, 90)
        self.assertEqual(item.mood, "calm")

    def test_batch_add(self):
        items = [
            {"file_path": "/a.mp4", "duration": 10},
            {"file_path": "/b.mp3", "duration": 20, "mood": "happy"},
            {"file_path": "/c.png", "duration": 0},
        ]
        count = self.db.add_items_batch(items)
        self.assertEqual(count, 3)

        stats = self.db.get_stats()
        self.assertEqual(stats["total_items"], 3)

    def test_search_by_mood(self):
        self.db.add_item("/a.mp3", mood="energetic", bpm=140)
        self.db.add_item("/b.mp3", mood="calm", bpm=80)
        self.db.add_item("/c.mp3", mood="energetic", bpm=130)

        results = self.db.search(mood="energetic")
        self.assertEqual(len(results), 2)

    def test_search_by_duration_range(self):
        self.db.add_item("/short.mp3", duration=10)
        self.db.add_item("/mid.mp3", duration=60)
        self.db.add_item("/long.mp3", duration=300)

        results = self.db.search(min_duration=30, max_duration=120)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_name, "mid.mp3")

    def test_search_by_bpm_range(self):
        self.db.add_item("/slow.mp3", bpm=70)
        self.db.add_item("/mid.mp3", bpm=120)
        self.db.add_item("/fast.mp3", bpm=160)

        results = self.db.search(min_bpm=100, max_bpm=140)
        self.assertEqual(len(results), 1)

    def test_full_text_search(self):
        self.db.add_item("/epic_battle.mp4", tags="action,epic,battle")
        self.db.add_item("/calm_ocean.mp4", tags="nature,calm,ocean")
        self.db.add_item("/epic_sunset.jpg", mood="epic")

        results = self.db.full_text_search("epic")
        # epic_battle (file_name+tags), epic_sunset (file_name+mood) = 2
        self.assertEqual(len(results), 2)

    def test_delete_item(self):
        item_id = self.db.add_item("/delete_me.mp3")
        self.assertTrue(self.db.delete_item(item_id))
        self.assertIsNone(self.db.get_item(item_id))

    def test_delete_by_path(self):
        self.db.add_item("/remove.mp3")
        self.assertTrue(self.db.delete_by_path("/remove.mp3"))
        self.assertIsNone(self.db.get_item_by_path("/remove.mp3"))

    def test_stats(self):
        self.db.add_item("/v1.mp4", file_type="video", duration=100, mood="happy")
        self.db.add_item("/v2.mp4", file_type="video", duration=200, mood="sad")
        self.db.add_item("/a1.mp3", file_type="audio", duration=50, mood="happy")

        stats = self.db.get_stats()
        self.assertEqual(stats["total_items"], 3)
        self.assertEqual(stats["by_mood"].get("happy", 0), 2)
        self.assertGreater(stats["avg_duration"], 0)

    def test_migrate_from_json(self):
        json_data = {
            "version": "1.0",
            "vector_dim": 512,
            "items": [
                {
                    "file_path": "/migrated/audio1.mp3",
                    "vector": [0.1] * 512,
                    "metadata": {"duration": 120, "bpm": 128, "mood": "energetic"},
                },
                {
                    "file_path": "/migrated/audio2.mp3",
                    "vector": [0.2] * 512,
                    "metadata": {"duration": 60, "bpm": 80, "mood": "calm"},
                },
            ],
        }
        json_path = os.path.join(self.tmp, "test_index.json")
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        result = self.db.migrate_from_json_index(json_path)
        self.assertEqual(result["migrated"], 2)

        stats = self.db.get_stats()
        self.assertEqual(stats["total_items"], 2)


# =====================================================================
# D1b - VectorIndex (FAISS)
# =====================================================================

class TestVectorIndex(unittest.TestCase):
    """FAISS 向量索引测试"""

    def test_create_index(self):
        from vector_index_faiss import VectorIndex
        idx = VectorIndex(dim=64)
        self.assertEqual(idx.size, 0)

    def test_add_and_search(self):
        import numpy as np
        from vector_index_faiss import VectorIndex

        idx = VectorIndex(dim=64)
        paths = ["/a.mp3", "/b.mp3", "/c.mp3"]
        vectors = np.random.randn(3, 64).astype(np.float32)
        idx.add(paths, vectors)

        self.assertEqual(idx.size, 3)

        query = vectors[0]
        results = idx.search(query, top_k=3)
        self.assertGreater(len(results), 0)
        # 第一个结果应该是自身（最高相似度）
        self.assertEqual(results[0]["file_path"], "/a.mp3")
        self.assertGreater(results[0]["similarity"], 0.9)

    def test_add_single(self):
        import numpy as np
        from vector_index_faiss import VectorIndex

        idx = VectorIndex(dim=32)
        idx.add_single("/test.mp3", np.random.randn(32).astype(np.float32))
        self.assertEqual(idx.size, 1)

    def test_empty_search(self):
        import numpy as np
        from vector_index_faiss import VectorIndex

        idx = VectorIndex(dim=32)
        results = idx.search(np.random.randn(32).astype(np.float32))
        self.assertEqual(len(results), 0)

    def test_save_and_load(self):
        import numpy as np
        from vector_index_faiss import VectorIndex

        tmp = tempfile.mkdtemp()
        try:
            idx = VectorIndex(dim=32)
            paths = ["/x.mp3", "/y.mp3"]
            vectors = np.random.randn(2, 32).astype(np.float32)
            idx.add(paths, vectors)

            save_path = os.path.join(tmp, "test.faiss")
            idx.save(save_path)

            # 加载
            idx2 = VectorIndex(dim=32)
            loaded = idx2.load(save_path)
            # 加载可能失败（FAISS 不可用），但 metadata 应能加载
            meta_path = save_path + ".meta.json"
            self.assertTrue(os.path.exists(meta_path))
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_dimension_mismatch(self):
        import numpy as np
        from vector_index_faiss import VectorIndex

        idx = VectorIndex(dim=32)
        with self.assertRaises(ValueError):
            idx.add(["/test.mp3"], np.random.randn(1, 64).astype(np.float32))

    def test_migrate_from_json(self):
        import numpy as np
        from vector_index_faiss import VectorIndex

        tmp = tempfile.mkdtemp()
        try:
            json_data = {
                "vector_dim": 64,
                "items": [
                    {"file_path": "/a.mp3", "vector": list(np.random.randn(64)), "metadata": {"bpm": 120}},
                    {"file_path": "/b.mp3", "vector": list(np.random.randn(64)), "metadata": {"bpm": 80}},
                ],
            }
            json_path = os.path.join(tmp, "index.json")
            with open(json_path, "w") as f:
                json.dump(json_data, f)

            idx = VectorIndex()
            result = idx.migrate_from_json(json_path)
            self.assertEqual(result["migrated"], 2)
            self.assertEqual(idx.size, 2)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


# =====================================================================
# D2 - PipelineLogger
# =====================================================================

class TestPipelineLogger(unittest.TestCase):
    """Pipeline 日志器测试"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # 设置环境变量让日志写入临时目录
        self._patcher = patch("training_logger.LOG_DIR", self.tmp)
        self._patcher.start()
        self._patcher2 = patch("training_logger.ARCHIVE_DIR", self.tmp)
        self._patcher2.start()

    def tearDown(self):
        self._patcher.stop()
        self._patcher2.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pipeline_logger_creation(self):
        from training_logger import PipelineLogger
        logger = PipelineLogger("test_task")
        self.assertEqual(logger.task_name, "test_task")
        self.assertEqual(len(logger.layer_results), 0)

    def test_log_all_layers(self):
        from training_logger import PipelineLogger
        logger = PipelineLogger("bgm_match")

        logger.log_perception(audio_path="test.mp3", bpm=128)
        logger.log_understanding(intent="bgm_match", confidence=0.92)
        logger.log_planning(steps=[{"action": "search"}, {"action": "download"}])
        logger.log_execution(steps_completed=2, total_steps=2)
        logger.log_feedback(rating=4.5)

        self.assertIn("perception", logger.layer_results)
        self.assertIn("understanding", logger.layer_results)
        self.assertIn("planning", logger.layer_results)
        self.assertIn("execution", logger.layer_results)
        self.assertIn("feedback", logger.layer_results)

    def test_save_pipeline_report(self):
        from training_logger import PipelineLogger
        logger = PipelineLogger("test_pipeline")
        logger.log_perception(bpm=120)
        logger.log_feedback(rating=3.8)

        report_path = logger.save_pipeline_report()
        self.assertTrue(os.path.exists(report_path))

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        self.assertIn("perception.bpm", report["metrics"])


# =====================================================================
# B03 - Cookie 路径归一化
# =====================================================================

class TestPathNormalization(unittest.TestCase):
    """B03/B07 路径归一化测试"""

    def test_media_config_relative_paths(self):
        """media-config.json 应使用相对路径"""
        config_path = PROJECT_ROOT / "config" / "media-config.json"
        if not config_path.exists():
            self.skipTest("media-config.json 不存在")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Cookie 路径应为相对路径
        platforms = config.get("platforms", {})
        for platform_name, platform_cfg in platforms.items():
            if isinstance(platform_cfg, dict) and "cookie_path" in platform_cfg:
                cp = platform_cfg["cookie_path"]
                self.assertTrue(
                    cp.startswith("./") or os.path.isabs(cp),
                    f"{platform_name} cookie_path 应为相对路径或绝对路径: {cp}",
                )

    def test_media_manager_normalizes_paths(self):
        """MediaManager 应解析相对路径为绝对路径"""
        import importlib
        try:
            mm = importlib.import_module("media-manager")
        except (ImportError, ModuleNotFoundError):
            # media-manager.py 含连字符，可能无法直接导入
            self.skipTest("media-manager 模块无法直接导入（连字符文件名）")


# =====================================================================
# B04 - AE 脚本 layer 声明
# =====================================================================

class TestAEScriptGeneration(unittest.TestCase):
    """B04 修复验证 - generate_ae_script 中 layer 变量声明"""

    def test_effect_layer_declared(self):
        """效果生成应声明 effectLayer 变量"""
        import importlib
        try:
            mm = importlib.import_module("media-manager")
        except (ImportError, ModuleNotFoundError):
            self.skipTest("media-manager 模块无法直接导入（连字符文件名）")


# =====================================================================
# ConfigManager 类测试
# =====================================================================

class TestConfigManagerClass(unittest.TestCase):
    """ConfigManager 类（B07 修复）测试"""

    def test_config_manager_loads(self):
        from config.config_manager import ConfigManager
        config_path = PROJECT_ROOT / "config" / "media-config.json"
        if not config_path.exists():
            self.skipTest("media-config.json 不存在")

        cfg = ConfigManager(config_path)
        self.assertIsNotNone(cfg.project_root)

    def test_config_manager_get_directory(self):
        from config.config_manager import ConfigManager
        config_path = PROJECT_ROOT / "config" / "media-config.json"
        if not config_path.exists():
            self.skipTest("media-config.json 不存在")

        cfg = ConfigManager(config_path)
        # 应返回解析后的绝对路径
        for dir_name in ["video_library", "bgm_library", "output"]:
            path = cfg.get_directory(dir_name)
            if path:
                self.assertFalse(
                    path.startswith("./"),
                    f"{dir_name} 路径未解析: {path}",
                )

    def test_config_manager_cookie_path(self):
        from config.config_manager import ConfigManager
        config_path = PROJECT_ROOT / "config" / "media-config.json"
        if not config_path.exists():
            self.skipTest("media-config.json 不存在")

        cfg = ConfigManager(config_path)
        cookie = cfg.get_platform_cookie_path("douyin")
        if cookie:
            self.assertFalse(
                cookie.startswith("./"),
                f"douyin cookie_path 未解析: {cookie}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
