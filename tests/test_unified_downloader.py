"""统一下载器单元测试"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "01-下载器"))

from unified_downloader import UnifiedDownloader, _ModuleLoader, detect_platform


class TestUnifiedDownloaderDetection(unittest.TestCase):
    """平台检测功能测试"""

    def test_detect_platform_douyin(self):
        result = UnifiedDownloader().detect_platform("https://v.douyin.com/xxx")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "douyin")
        self.assertTrue(result["supported"])

    def test_detect_platform_bilibili(self):
        result = UnifiedDownloader().detect_platform("https://www.bilibili.com/video/BVxxx")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "bilibili")
        self.assertTrue(result["supported"])

    def test_detect_platform_youtube(self):
        result = UnifiedDownloader().detect_platform("https://www.youtube.com/watch?v=xxx")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "youtube")
        self.assertTrue(result["supported"])

    def test_detect_platform_kuaishou(self):
        result = UnifiedDownloader().detect_platform("https://www.kuaishou.com/f/xxx")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "kuaishou")
        self.assertFalse(result["supported"])

    def test_detect_platform_tiktok(self):
        result = UnifiedDownloader().detect_platform("https://www.tiktok.com/@user/video/xxx")
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "tiktok")
        self.assertFalse(result["supported"])

    def test_detect_platform_unknown(self):
        result = UnifiedDownloader().detect_platform("https://example.com/video")
        self.assertTrue(result["success"])
        self.assertIsNone(result["platform"])
        self.assertFalse(result["supported"])

    def test_detect_platform_empty(self):
        result = UnifiedDownloader().detect_platform("")
        self.assertTrue(result["success"])
        self.assertIsNone(result["platform"])
        self.assertFalse(result["supported"])


class TestUnifiedDownloaderDownload(unittest.TestCase):
    """下载功能测试（离线模式）"""

    def test_download_unknown_platform(self):
        downloader = UnifiedDownloader()
        result = downloader.download("https://example.com/video")
        self.assertFalse(result["success"])
        self.assertIn("无法识别", result.get("error", ""))

    def test_download_unsupported_platform(self):
        downloader = UnifiedDownloader()
        result = downloader.download("https://www.kuaishou.com/f/xxx")
        self.assertFalse(result["success"])
        self.assertIn("暂不支持", result.get("error", ""))

    def test_download_bgm_unknown_platform(self):
        downloader = UnifiedDownloader()
        result = downloader.download_bgm("https://example.com/video")
        self.assertFalse(result["success"])
        self.assertIn("无法识别", result.get("error", ""))

    def test_get_video_info_unknown_platform(self):
        downloader = UnifiedDownloader()
        result = downloader.get_video_info("https://example.com/video")
        self.assertFalse(result["success"])
        self.assertIn("无法识别", result.get("error", ""))

    def test_get_video_info_unsupported_platform(self):
        downloader = UnifiedDownloader()
        result = downloader.get_video_info("https://www.tiktok.com/@user/video/xxx")
        self.assertFalse(result["success"])
        self.assertIn("暂不支持", result.get("error", ""))


class TestModuleLoader(unittest.TestCase):
    """模块加载器测试"""

    def setUp(self):
        _ModuleLoader.reset()

    def test_reset_clears_cache(self):
        _ModuleLoader._instances["test_key"] = "test_value"
        _ModuleLoader._errors["test_key"] = "test_error"
        _ModuleLoader.reset()
        self.assertNotIn("test_key", _ModuleLoader._instances)
        self.assertNotIn("test_key", _ModuleLoader._errors)

    def test_instance_caching(self):
        """验证缓存key命中时返回缓存实例"""
        _ModuleLoader._instances["bilibili::"] = "cached_instance"
        result, error = _ModuleLoader.get_bilibili_downloader()
        self.assertEqual(result, "cached_instance")
        self.assertIsNone(error)
        # 清理
        del _ModuleLoader._instances["bilibili::"]


if __name__ == "__main__":
    unittest.main(verbosity=2)