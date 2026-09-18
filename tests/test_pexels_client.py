"""Pexels客户端纯函数单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "02-免费素材API"))

from pexels_client import (
    VALID_ORIENTATIONS,
    VALID_QUALITIES,
    normalize_photo_result,
    normalize_video_result,
)


class TestNormalizeVideoResult(unittest.TestCase):
    """视频结果归一化测试"""

    def test_normalize_full_video(self):
        raw = {
            "id": 12345,
            "duration": 120,
            "url": "https://www.pexels.com/video/test",
            "video_files": [
                {
                    "id": 1,
                    "quality": "hd",
                    "link": "https://cdn.com/video_hd.mp4",
                    "width": 1920,
                    "height": 1080,
                },
                {
                    "id": 2,
                    "quality": "sd",
                    "link": "https://cdn.com/video_sd.mp4",
                    "width": 640,
                    "height": 360,
                },
            ],
            "video_pictures": [
                {"id": 1, "picture": "https://cdn.com/thumb.jpg"},
                {"id": 2, "picture": "https://cdn.com/thumb2.jpg"},
            ],
            "user": {
                "id": 100,
                "name": "Test Photographer",
                "url": "https://www.pexels.com/@test",
            },
        }
        result = normalize_video_result(raw)
        self.assertEqual(result["platform"], "pexels")
        self.assertEqual(result["id"], "12345")
        self.assertEqual(result["type"], "video")
        self.assertEqual(result["title"], "")
        self.assertEqual(result["url"], "https://cdn.com/video_hd.mp4")
        self.assertEqual(result["thumbnail"], "https://cdn.com/thumb.jpg")
        self.assertEqual(result["duration"], 120)
        self.assertEqual(result["width"], 1920)
        self.assertEqual(result["height"], 1080)
        self.assertEqual(result["author"], "Test Photographer")
        self.assertEqual(result["author_url"], "https://www.pexels.com/@test")
        self.assertEqual(result["page_url"], "https://www.pexels.com/video/test")
        self.assertEqual(result["license"], "Pexels License (free to use)")
        self.assertEqual(result["size"], 0)
        self.assertIn("raw", result)

    def test_normalize_video_no_hd_quality(self):
        raw = {
            "id": 67890,
            "duration": 60,
            "video_files": [
                {
                    "id": 1,
                    "quality": "sd",
                    "link": "https://cdn.com/video_sd.mp4",
                    "width": 640,
                    "height": 360,
                },
            ],
            "video_pictures": [],
            "user": {},
        }
        result = normalize_video_result(raw)
        self.assertEqual(result["url"], "https://cdn.com/video_sd.mp4")
        self.assertEqual(result["width"], 640)
        self.assertEqual(result["height"], 360)
        self.assertEqual(result["thumbnail"], "")
        self.assertEqual(result["author"], "")
        self.assertEqual(result["author_url"], "")

    def test_normalize_video_empty_files(self):
        raw = {
            "id": 11111,
            "video_files": [],
            "video_pictures": [],
            "user": None,
        }
        result = normalize_video_result(raw)
        self.assertEqual(result["url"], "")
        self.assertEqual(result["width"], 0)
        self.assertEqual(result["height"], 0)
        self.assertEqual(result["thumbnail"], "")
        self.assertEqual(result["author"], "")

    def test_normalize_video_none_files(self):
        raw = {
            "id": 22222,
            "video_files": None,
            "video_pictures": None,
            "user": None,
        }
        result = normalize_video_result(raw)
        self.assertEqual(result["url"], "")
        self.assertEqual(result["width"], 0)
        self.assertEqual(result["height"], 0)
        self.assertEqual(result["thumbnail"], "")

    def test_normalize_video_empty_raw(self):
        raw = {}
        result = normalize_video_result(raw)
        self.assertEqual(result["platform"], "pexels")
        self.assertEqual(result["id"], "")
        self.assertEqual(result["type"], "video")
        self.assertEqual(result["url"], "")
        self.assertEqual(result["duration"], 0)

    def test_normalize_video_id_is_string(self):
        raw = {"id": 999}
        result = normalize_video_result(raw)
        self.assertIsInstance(result["id"], str)
        self.assertEqual(result["id"], "999")

    def test_normalize_video_preserves_raw(self):
        raw = {"id": 123, "extra_field": "value"}
        result = normalize_video_result(raw)
        self.assertEqual(result["raw"]["id"], 123)
        self.assertEqual(result["raw"]["extra_field"], "value")

    def test_normalize_video_quality_case_insensitive(self):
        raw = {
            "id": 33333,
            "video_files": [
                {
                    "quality": "HD",
                    "link": "https://cdn.com/video.mp4",
                    "width": 1920,
                    "height": 1080,
                },
            ],
        }
        result = normalize_video_result(raw)
        self.assertEqual(result["url"], "https://cdn.com/video.mp4")


class TestNormalizePhotoResult(unittest.TestCase):
    """图片结果归一化测试"""

    def test_normalize_full_photo(self):
        raw = {
            "id": 54321,
            "width": 1920,
            "height": 1080,
            "url": "https://www.pexels.com/photo/test",
            "photographer": "Test Photographer",
            "photographer_url": "https://www.pexels.com/@test",
            "alt": "A beautiful landscape",
            "src": {
                "original": "https://cdn.com/original.jpg",
                "large2x": "https://cdn.com/large2x.jpg",
                "large": "https://cdn.com/large.jpg",
                "small": "https://cdn.com/small.jpg",
                "tiny": "https://cdn.com/tiny.jpg",
                "preview": "https://cdn.com/preview.jpg",
            },
        }
        result = normalize_photo_result(raw)
        self.assertEqual(result["platform"], "pexels")
        self.assertEqual(result["id"], "54321")
        self.assertEqual(result["type"], "image")
        self.assertEqual(result["title"], "A beautiful landscape")
        self.assertEqual(result["url"], "https://cdn.com/large2x.jpg")
        self.assertEqual(result["thumbnail"], "https://cdn.com/small.jpg")
        self.assertEqual(result["width"], 1920)
        self.assertEqual(result["height"], 1080)
        self.assertEqual(result["author"], "Test Photographer")
        self.assertEqual(result["author_url"], "https://www.pexels.com/@test")
        self.assertEqual(result["page_url"], "https://www.pexels.com/photo/test")
        self.assertEqual(result["license"], "Pexels License (free to use)")
        self.assertEqual(result["duration"], 0)
        self.assertEqual(result["size"], 0)

    def test_normalize_photo_no_large2x(self):
        raw = {
            "id": 99999,
            "src": {
                "large": "https://cdn.com/large.jpg",
                "small": "https://cdn.com/small.jpg",
            },
        }
        result = normalize_photo_result(raw)
        self.assertEqual(result["url"], "https://cdn.com/large.jpg")

    def test_normalize_photo_only_original(self):
        raw = {
            "id": 88888,
            "src": {
                "original": "https://cdn.com/original.jpg",
            },
        }
        result = normalize_photo_result(raw)
        self.assertEqual(result["url"], "https://cdn.com/original.jpg")
        self.assertEqual(result["thumbnail"], "")

    def test_normalize_photo_empty_src(self):
        raw = {
            "id": 77777,
            "src": {},
        }
        result = normalize_photo_result(raw)
        self.assertEqual(result["url"], "")
        self.assertEqual(result["thumbnail"], "")

    def test_normalize_photo_none_src(self):
        raw = {
            "id": 66666,
            "src": None,
        }
        result = normalize_photo_result(raw)
        self.assertEqual(result["url"], "")
        self.assertEqual(result["thumbnail"], "")

    def test_normalize_photo_empty_raw(self):
        raw = {}
        result = normalize_photo_result(raw)
        self.assertEqual(result["platform"], "pexels")
        self.assertEqual(result["id"], "")
        self.assertEqual(result["type"], "image")
        self.assertEqual(result["url"], "")
        self.assertEqual(result["title"], "")

    def test_normalize_photo_id_is_string(self):
        raw = {"id": 12345}
        result = normalize_photo_result(raw)
        self.assertIsInstance(result["id"], str)
        self.assertEqual(result["id"], "12345")

    def test_normalize_photo_preserves_raw(self):
        raw = {"id": 54321, "extra": "data"}
        result = normalize_photo_result(raw)
        self.assertEqual(result["raw"]["id"], 54321)
        self.assertEqual(result["raw"]["extra"], "data")

    def test_normalize_photo_no_alt(self):
        raw = {"id": 11111, "src": {"large": "https://cdn.com/large.jpg"}}
        result = normalize_photo_result(raw)
        self.assertEqual(result["title"], "")


class TestConstants(unittest.TestCase):
    """常量定义测试"""

    def test_valid_orientations_contains_expected_values(self):
        self.assertIn("landscape", VALID_ORIENTATIONS)
        self.assertIn("portrait", VALID_ORIENTATIONS)
        self.assertIn("square", VALID_ORIENTATIONS)
        self.assertIn("", VALID_ORIENTATIONS)

    def test_valid_qualities_contains_expected_values(self):
        self.assertIn("hd", VALID_QUALITIES)
        self.assertIn("sd", VALID_QUALITIES)
        self.assertIn("uhd", VALID_QUALITIES)

    def test_valid_orientations_is_set(self):
        self.assertIsInstance(VALID_ORIENTATIONS, set)

    def test_valid_qualities_is_set(self):
        self.assertIsInstance(VALID_QUALITIES, set)


if __name__ == "__main__":
    unittest.main(verbosity=2)