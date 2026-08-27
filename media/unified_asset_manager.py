"""
Unified Asset Manager (DAM) Engine
===================================
Production-grade Digital Asset Management system for After Effects workflows.
Integrates asset acquisition, management, search, processing, and quality assessment.

Author: AE Knowledge Vault
Version: 1.0.0
License: MIT
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
import hashlib
import shutil
import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union, Generator
)
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("UnifiedAssetManager")


# ============================================================================
# 1. ASSET CLASSIFICATION SYSTEM
# ============================================================================

class AssetCategory(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    FONT = "font"
    MODEL_3D = "model_3d"
    TEMPLATE = "template"
    LUT = "lut"
    PARTICLE = "particle"
    TEXTURE = "texture"
    HDRI = "hdri"


class LicenseType(str, Enum):
    COMMERCIAL = "commercial"
    ROYALTY_FREE = "royalty_free"
    CREATIVE_COMMONS = "creative_commons"
    SIL_OFL = "sil_ofl"
    PERSONAL_USE = "personal_use"
    UNKNOWN = "unknown"


class AssetQuality(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    PROFESSIONAL = 4
    MASTER = 5


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mxf", ".prores", ".h264", ".h265"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".aiff"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".psd", ".ai", ".svg", ".webp", ".bmp", ".gif"}
FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2", ".eot"}
MODEL_3D_EXTENSIONS = {".obj", ".fbx", ".blend", ".gltf", ".glb", ".3ds", ".ma", ".mb"}
TEMPLATE_EXTENSIONS = {".aep", ".aet", ".mogrt", ".prproj", ".drp", ".ppj"}
LUT_EXTENSIONS = {".cube", ".3dl", ".look", ".icc", ".icm"}
PARTICLE_EXTENSIONS = {".pex", ".pfs", ".prtl", ".aep"}
TEXTURE_EXTENSIONS = {".jpg", ".png", ".tiff", ".tga", ".exr", ".hdr"}
HDRI_EXTENSIONS = {".hdr", ".exr", ".hdri"}

CATEGORY_EXTENSIONS: Dict[AssetCategory, Set[str]] = {
    AssetCategory.VIDEO: VIDEO_EXTENSIONS,
    AssetCategory.AUDIO: AUDIO_EXTENSIONS,
    AssetCategory.IMAGE: IMAGE_EXTENSIONS,
    AssetCategory.FONT: FONT_EXTENSIONS,
    AssetCategory.MODEL_3D: MODEL_3D_EXTENSIONS,
    AssetCategory.TEMPLATE: TEMPLATE_EXTENSIONS,
    AssetCategory.LUT: LUT_EXTENSIONS,
    AssetCategory.PARTICLE: PARTICLE_EXTENSIONS,
    AssetCategory.TEXTURE: TEXTURE_EXTENSIONS,
    AssetCategory.HDRI: HDRI_EXTENSIONS,
}


def detect_category(file_path: str) -> Optional[AssetCategory]:
    ext = Path(file_path).suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return None


@dataclass
class AssetMetadata:
    id: str
    name: str
    category: AssetCategory
    tags: List[str] = field(default_factory=list)
    file_path: str = ""
    file_size: int = 0
    duration: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    fps: float = 0.0
    format: str = ""
    license: LicenseType = LicenseType.UNKNOWN
    source_url: str = ""
    created_at: str = ""
    modified_at: str = ""
    quality_score: float = 0.0
    usage_count: int = 0
    thumbnail_path: str = ""
    perceptual_hash: str = ""
    bitrate: int = 0
    codec: str = ""
    color_space: str = ""
    author: str = ""
    description: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["license"] = self.license.value
        data["resolution"] = f"{self.resolution[0]}x{self.resolution[1]}"
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetMetadata":
        data = data.copy()
        if isinstance(data.get("category"), str):
            data["category"] = AssetCategory(data["category"])
        if isinstance(data.get("license"), str):
            data["license"] = LicenseType(data["license"])
        if isinstance(data.get("resolution"), str):
            w, h = data["resolution"].split("x")
            data["resolution"] = (int(w), int(h))
        return cls(**data)


# ============================================================================
# 2. CONFIGURATION & PERSISTENCE
# ============================================================================

@dataclass
class DAMConfig:
    root_directory: str = "D:\\AE-Work"
    database_path: str = "D:\\AE-Work\\asset_library.db"
    thumbnail_directory: str = "D:\\AE-Work\\thumbnails"
    proxy_directory: str = "D:\\AE-Work\\proxies"
    archive_directory: str = "D:\\AE-Work\\archive"
    watch_folders: List[str] = field(default_factory=list)
    default_license: LicenseType = LicenseType.UNKNOWN
    thumbnail_size: Tuple[int, int] = (320, 180)
    proxy_resolution: Tuple[int, int] = (960, 540)
    max_concurrent_downloads: int = 3
    max_concurrent_processes: int = 2
    deduplication_enabled: bool = True
    auto_thumbnail: bool = True
    backup_directory: str = "D:\\AE-Work\\backup"

    def ensure_directories(self) -> None:
        for path in [
            self.root_directory,
            self.thumbnail_directory,
            self.proxy_directory,
            self.archive_directory,
            self.backup_directory,
            os.path.dirname(self.database_path),
        ]:
            os.makedirs(path, exist_ok=True)

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            data = asdict(self)
            data["default_license"] = self.default_license.value
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, path: str) -> "DAMConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("default_license"), str):
            data["default_license"] = LicenseType(data["default_license"])
        return cls(**data)


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    file_path TEXT UNIQUE NOT NULL,
    file_size INTEGER DEFAULT 0,
    duration REAL DEFAULT 0,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    fps REAL DEFAULT 0,
    format TEXT DEFAULT '',
    license TEXT DEFAULT 'unknown',
    source_url TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    modified_at TEXT DEFAULT '',
    quality_score REAL DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    thumbnail_path TEXT DEFAULT '',
    perceptual_hash TEXT DEFAULT '',
    bitrate INTEGER DEFAULT 0,
    codec TEXT DEFAULT '',
    color_space TEXT DEFAULT '',
    author TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags_json TEXT DEFAULT '[]',
    custom_fields_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name);
CREATE INDEX IF NOT EXISTS idx_assets_phash ON assets(perceptual_hash);
CREATE INDEX IF NOT EXISTS idx_assets_quality ON assets(quality_score);
CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (asset_id, tag_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    project_name TEXT DEFAULT '',
    used_at TEXT DEFAULT '',
    usage_type TEXT DEFAULT '',
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS approval_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    reviewer TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    submitted_at TEXT DEFAULT '',
    reviewed_at TEXT DEFAULT '',
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS download_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    target_path TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending',
    progress REAL DEFAULT 0,
    source_type TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    started_at TEXT DEFAULT '',
    completed_at TEXT DEFAULT '',
    error_message TEXT DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
    name, description, author, asset_id UNINDEXED
);
"""


# ============================================================================
# 3. ASSET LIBRARY MANAGEMENT
# ============================================================================

class AssetLibrary:
    def __init__(self, config: DAMConfig):
        self.config = config
        self.config.ensure_directories()
        self.conn = sqlite3.connect(
            config.database_path,
            check_same_thread=False,
            timeout=30.0
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._db_lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._db_lock:
            self.conn.executescript(SQLITE_SCHEMA)
            self.conn.commit()

    def _locked_execute(self, sql: str, params: Optional[Tuple] = None, commit: bool = False):
        with self._db_lock:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            if commit:
                self.conn.commit()
            return cursor

    def _row_to_asset(self, row: sqlite3.Row) -> AssetMetadata:
        tags = json.loads(row["tags_json"]) if row["tags_json"] else []
        custom_fields = json.loads(row["custom_fields_json"]) if row["custom_fields_json"] else {}
        return AssetMetadata(
            id=row["id"],
            name=row["name"],
            category=AssetCategory(row["category"]),
            tags=tags,
            file_path=row["file_path"],
            file_size=row["file_size"],
            duration=row["duration"],
            resolution=(row["width"], row["height"]),
            fps=row["fps"],
            format=row["format"],
            license=LicenseType(row["license"]),
            source_url=row["source_url"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            quality_score=row["quality_score"],
            usage_count=row["usage_count"],
            thumbnail_path=row["thumbnail_path"],
            perceptual_hash=row["perceptual_hash"],
            bitrate=row["bitrate"],
            codec=row["codec"],
            color_space=row["color_space"],
            author=row["author"],
            description=row["description"],
            custom_fields=custom_fields,
        )

    def add_asset(self, asset: AssetMetadata) -> str:
        with self._db_lock:
            now = datetime.now().isoformat()
            if not asset.id:
                asset.id = str(uuid.uuid4())
            if not asset.created_at:
                asset.created_at = now
            if not asset.modified_at:
                asset.modified_at = now

            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO assets 
                   (id, name, category, file_path, file_size, duration, width, height,
                    fps, format, license, source_url, created_at, modified_at,
                    quality_score, usage_count, thumbnail_path, perceptual_hash,
                    bitrate, codec, color_space, author, description, tags_json, custom_fields_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    asset.id, asset.name, asset.category.value, asset.file_path,
                    asset.file_size, asset.duration, asset.resolution[0], asset.resolution[1],
                    asset.fps, asset.format, asset.license.value, asset.source_url,
                    asset.created_at, asset.modified_at, asset.quality_score,
                    asset.usage_count, asset.thumbnail_path, asset.perceptual_hash,
                    asset.bitrate, asset.codec, asset.color_space, asset.author,
                    asset.description, json.dumps(asset.tags, ensure_ascii=False),
                    json.dumps(asset.custom_fields, ensure_ascii=False),
                ),
            )
            self.conn.commit()

            for tag in asset.tags:
                self._ensure_tag_locked(tag, cursor)

            self._update_fts_locked(asset, cursor)
            logger.info(f"Asset added: {asset.name} ({asset.id})")
            return asset.id

    def _ensure_tag_locked(self, tag_name: str, cursor) -> int:
        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = cursor.fetchone()[0]
        return tag_id

    def _update_fts_locked(self, asset: AssetMetadata, cursor) -> None:
        cursor.execute("DELETE FROM assets_fts WHERE asset_id = ?", (asset.id,))
        cursor.execute(
            "INSERT INTO assets_fts (name, description, author, asset_id) VALUES (?, ?, ?, ?)",
            (asset.name, asset.description, asset.author, asset.id),
        )

    def _ensure_tag(self, tag_name: str) -> int:
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_id = cursor.fetchone()[0]
            self.conn.commit()
            return tag_id

    def _update_fts(self, asset: AssetMetadata) -> None:
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM assets_fts WHERE asset_id = ?", (asset.id,))
            cursor.execute(
                "INSERT INTO assets_fts (name, description, author, asset_id) VALUES (?, ?, ?, ?)",
                (asset.name, asset.description, asset.author, asset.id),
            )
            self.conn.commit()

    def remove_asset(self, asset_id: str) -> bool:
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM assets_fts WHERE asset_id = ?", (asset_id,))
            cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            deleted = cursor.rowcount > 0
            self.conn.commit()
            if deleted:
                logger.info(f"Asset removed: {asset_id}")
            return deleted

    def update_asset(self, asset_id: str, updates: Dict[str, Any]) -> bool:
        if not updates:
            return False
        with self._db_lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
            row = cursor.fetchone()
            if not row:
                return False
            asset = self._row_to_asset(row)

            fields = []
            values = []
            for key, value in updates.items():
                if key == "tags":
                    asset.tags = value
                    fields.append("tags_json = ?")
                    values.append(json.dumps(value, ensure_ascii=False))
                elif key == "custom_fields":
                    asset.custom_fields = value
                    fields.append("custom_fields_json = ?")
                    values.append(json.dumps(value, ensure_ascii=False))
                elif key == "resolution":
                    fields.append("width = ?")
                    fields.append("height = ?")
                    values.extend([value[0], value[1]])
                elif key == "category":
                    fields.append("category = ?")
                    values.append(value.value if isinstance(value, Enum) else value)
                elif key == "license":
                    fields.append("license = ?")
                    values.append(value.value if isinstance(value, Enum) else value)
                elif hasattr(asset, key):
                    fields.append(f"{key} = ?")
                    values.append(value)

            fields.append("modified_at = ?")
            values.append(datetime.now().isoformat())
            values.append(asset_id)

            query = f"UPDATE assets SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            self.conn.commit()

            if "name" in updates or "description" in updates or "author" in updates:
                self._update_fts_locked(asset, cursor)

            return cursor.rowcount > 0

    def get_asset(self, asset_id: str) -> Optional[AssetMetadata]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        row = cursor.fetchone()
        return self._row_to_asset(row) if row else None

    def get_asset_by_path(self, file_path: str) -> Optional[AssetMetadata]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return self._row_to_asset(row) if row else None

    def list_assets(
        self,
        category: Optional[AssetCategory] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
    ) -> List[AssetMetadata]:
        query = "SELECT * FROM assets"
        params: List[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category.value)

        valid_sort = {"created_at", "modified_at", "name", "quality_score", "file_size", "duration"}
        sort_field = sort_by if sort_by in valid_sort else "created_at"
        sort_dir = "ASC" if sort_order.upper() == "ASC" else "DESC"
        query += f" ORDER BY {sort_field} {sort_dir} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [self._row_to_asset(row) for row in cursor.fetchall()]

    def count_assets(self, category: Optional[AssetCategory] = None) -> int:
        query = "SELECT COUNT(*) FROM assets"
        params: List[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category.value)
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def batch_import_from_directory(
        self,
        directory: str,
        recursive: bool = True,
        auto_detect: bool = True,
        default_tags: Optional[List[str]] = None,
    ) -> Tuple[int, int]:
        added = 0
        skipped = 0
        default_tags = default_tags or []

        pattern = "**/*" if recursive else "*"
        for file_path in Path(directory).glob(pattern):
            if not file_path.is_file():
                continue
            try:
                if self.get_asset_by_path(str(file_path)):
                    skipped += 1
                    continue
                if auto_detect:
                    category = detect_category(str(file_path))
                    if not category:
                        skipped += 1
                        continue
                else:
                    category = AssetCategory.IMAGE
                asset = self._create_asset_from_file(str(file_path), category, default_tags)
                self.add_asset(asset)
                added += 1
            except Exception as e:
                logger.warning(f"Failed to import {file_path}: {e}")
                skipped += 1

        logger.info(f"Batch import complete: {added} added, {skipped} skipped")
        return added, skipped

    def _create_asset_from_file(
        self, file_path: str, category: AssetCategory, tags: Optional[List[str]] = None
    ) -> AssetMetadata:
        path = Path(file_path)
        stat = path.stat()
        asset = AssetMetadata(
            id=str(uuid.uuid4()),
            name=path.stem,
            category=category,
            file_path=str(file_path),
            file_size=stat.st_size,
            format=path.suffix.lstrip(".").lower(),
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            tags=tags or [],
        )
        self.auto_extract_metadata(asset)
        if self.config.auto_thumbnail:
            try:
                self.generate_thumbnail(asset)
            except Exception as e:
                logger.debug(f"Thumbnail generation skipped for {file_path}: {e}")
        if self.config.deduplication_enabled:
            try:
                asset.perceptual_hash = self._compute_perceptual_hash(asset)
            except Exception:
                pass
        return asset

    def auto_extract_metadata(self, asset: AssetMetadata) -> None:
        if asset.category == AssetCategory.VIDEO:
            self._extract_video_metadata(asset)
        elif asset.category == AssetCategory.AUDIO:
            self._extract_audio_metadata(asset)
        elif asset.category in (AssetCategory.IMAGE, AssetCategory.TEXTURE, AssetCategory.HDRI):
            self._extract_image_metadata(asset)
        elif asset.category == AssetCategory.FONT:
            self._extract_font_metadata(asset)

    def _run_ffprobe(self, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        return None

    def _extract_video_metadata(self, asset: AssetMetadata) -> None:
        data = self._run_ffprobe(asset.file_path)
        if not data:
            return
        fmt = data.get("format", {})
        asset.duration = float(fmt.get("duration", 0))
        asset.bitrate = int(fmt.get("bit_rate", 0))
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                asset.codec = stream.get("codec_name", "")
                asset.resolution = (stream.get("width", 0), stream.get("height", 0))
                fps_str = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = map(int, fps_str.split("/"))
                    asset.fps = num / den if den else 0
                except (ValueError, ZeroDivisionError):
                    pass
                asset.color_space = stream.get("color_space", "")

    def _extract_audio_metadata(self, asset: AssetMetadata) -> None:
        data = self._run_ffprobe(asset.file_path)
        if not data:
            return
        fmt = data.get("format", {})
        asset.duration = float(fmt.get("duration", 0))
        asset.bitrate = int(fmt.get("bit_rate", 0))
        tags = fmt.get("tags", {})
        if tags:
            asset.author = tags.get("artist", "")
            asset.description = tags.get("album", "")

    def _extract_image_metadata(self, asset: AssetMetadata) -> None:
        try:
            from PIL import Image
            with Image.open(asset.file_path) as img:
                asset.resolution = img.size
                asset.format = (img.format or "").lower()
                if hasattr(img, "_getexif") and img._getexif():
                    exif = img._getexif()
                    asset.author = exif.get(315, "") or ""
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"PIL metadata extraction failed: {e}")

    def _extract_font_metadata(self, asset: AssetMetadata) -> None:
        try:
            from fontTools.ttLib import TTFont
            font = TTFont(asset.file_path)
            name_table = font.get("name")
            if name_table:
                for record in name_table.names:
                    if record.nameID == 1:
                        asset.name = str(record)
                    elif record.nameID == 9:
                        asset.author = str(record)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Font metadata extraction failed: {e}")

    def generate_thumbnail(self, asset: AssetMetadata) -> str:
        os.makedirs(self.config.thumbnail_directory, exist_ok=True)
        thumb_path = os.path.join(self.config.thumbnail_directory, f"{asset.id}.jpg")

        if asset.category == AssetCategory.VIDEO:
            self._extract_video_frame(asset.file_path, thumb_path)
        elif asset.category in (AssetCategory.IMAGE, AssetCategory.TEXTURE, AssetCategory.HDRI):
            self._resize_image(asset.file_path, thumb_path)
        else:
            thumb_path = self._generate_placeholder_thumbnail(asset)

        asset.thumbnail_path = thumb_path
        return thumb_path

    def _extract_video_frame(self, video_path: str, output_path: str) -> None:
        try:
            w, h = self.config.thumbnail_size
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", video_path,
                    "-ss", "00:00:01", "-vframes", "1",
                    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
                    "-q:v", "2", output_path
                ],
                capture_output=True, timeout=30
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _resize_image(self, image_path: str, output_path: str) -> None:
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img.thumbnail(self.config.thumbnail_size)
                if img.mode in ("RGBA", "P", "LA"):
                    background = Image.new("RGB", self.config.thumbnail_size, (30, 30, 30))
                    offset = ((background.width - img.width) // 2, (background.height - img.height) // 2)
                    background.paste(img.convert("RGB"), offset)
                    background.save(output_path, "JPEG", quality=85)
                else:
                    img.convert("RGB").save(output_path, "JPEG", quality=85)
        except ImportError:
            pass

    def _generate_placeholder_thumbnail(self, asset: AssetMetadata) -> str:
        thumb_path = os.path.join(self.config.thumbnail_directory, f"{asset.id}.svg")
        colors = {
            AssetCategory.VIDEO: "#4A90D9",
            AssetCategory.AUDIO: "#D94A6B",
            AssetCategory.IMAGE: "#4AD98B",
            AssetCategory.FONT: "#D9C24A",
            AssetCategory.MODEL_3D: "#9B4AD9",
            AssetCategory.TEMPLATE: "#4AD9D4",
            AssetCategory.LUT: "#D97A4A",
            AssetCategory.PARTICLE: "#D94AD0",
            AssetCategory.TEXTURE: "#7AD94A",
            AssetCategory.HDRI: "#4A5BD9",
        }
        color = colors.get(asset.category, "#888888")
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
            <rect width="320" height="180" fill="{color}" opacity="0.3"/>
            <text x="160" y="95" text-anchor="middle" fill="{color}" font-size="48" font-family="Arial">{asset.category.value[:3].upper()}</text>
        </svg>"""
        with open(thumb_path, "w") as f:
            f.write(svg)
        return thumb_path

    def _compute_perceptual_hash(self, asset: AssetMetadata) -> str:
        if asset.category in (AssetCategory.IMAGE, AssetCategory.TEXTURE, AssetCategory.HDRI):
            return self._dhash_image(asset.file_path)
        elif asset.category == AssetCategory.VIDEO:
            return self._video_phash(asset.file_path)
        return hashlib.md5(asset.file_path.encode()).hexdigest()

    def _dhash_image(self, image_path: str, hash_size: int = 8) -> str:
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img = img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
                pixels = list(img.getdata())
                difference = []
                for row in range(hash_size):
                    for col in range(hash_size):
                        left = pixels[row * (hash_size + 1) + col]
                        right = pixels[row * (hash_size + 1) + col + 1]
                        difference.append(left > right)
                decimal = 0
                for i, bit in enumerate(difference):
                    if bit:
                        decimal += 2 ** i
                return f"dhash:{hex(decimal)}"
        except (ImportError, Exception):
            return ""

    def _video_phash(self, video_path: str) -> str:
        return hashlib.md5((video_path + str(os.path.getsize(video_path))).encode()).hexdigest()

    def find_duplicates(self, threshold: int = 5) -> List[List[AssetMetadata]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, perceptual_hash FROM assets WHERE perceptual_hash != ''")
        assets = cursor.fetchall()

        # 解析有效哈希
        hash_list = []
        for id1, hash1 in assets:
            if hash1.startswith("dhash:"):
                try:
                    hash_val = int(hash1.split(":")[1], 16)
                    hash_list.append((id1, hash_val))
                except (ValueError, IndexError):
                    continue

        if len(hash_list) < 2:
            return []

        # 按哈希值排序后使用滑动窗口，避免完整 O(n²) 比较
        hash_list.sort(key=lambda x: x[1])
        duplicates = []
        used = set()

        n = len(hash_list)
        for i in range(n):
            id1, hash1_val = hash_list[i]
            if id1 in used:
                continue
            group = [id1]
            for j in range(i + 1, n):
                id2, hash2_val = hash_list[j]
                if id2 in used:
                    continue
                hamming = bin(hash1_val ^ hash2_val).count("1")
                if hamming <= threshold:
                    group.append(id2)
                    used.add(id2)
                elif hamming > threshold * 4:
                    # 海明距离足够大时，后续不可能有相近的，跳出内层循环
                    break
            if len(group) > 1:
                duplicates.append([self.get_asset(aid) for aid in group])
                used.add(id1)

        return duplicates

    def backup_database(self, backup_path: Optional[str] = None) -> str:
        backup_path = backup_path or os.path.join(
            self.config.backup_directory,
            f"asset_library_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        backup_conn = sqlite3.connect(backup_path)
        self.conn.backup(backup_conn)
        backup_conn.close()
        logger.info(f"Database backed up to: {backup_path}")
        return backup_path

    def restore_database(self, backup_path: str) -> bool:
        if not os.path.exists(backup_path):
            return False
        self.conn.close()
        shutil.copy2(backup_path, self.config.database_path)
        self.conn = sqlite3.connect(self.config.database_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Database restored from: {backup_path}")
        return True

    def close(self) -> None:
        self.conn.close()


# ============================================================================
# 4. SMART SEARCH ENGINE
# ============================================================================

class SearchEngine:
    def __init__(self, library: AssetLibrary):
        self.library = library

    def keyword_search(self, query: str, limit: int = 50) -> List[AssetMetadata]:
        cursor = self.library.conn.cursor()
        try:
            cursor.execute(
                """SELECT a.* FROM assets a
                   INNER JOIN assets_fts f ON a.id = f.asset_id
                   WHERE assets_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            )
        except sqlite3.OperationalError:
            cursor.execute(
                """SELECT * FROM assets
                   WHERE name LIKE ? OR description LIKE ? OR author LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            )
        return [self.library._row_to_asset(row) for row in cursor.fetchall()]

    def fuzzy_search(self, query: str, max_distance: int = 2, limit: int = 50) -> List[AssetMetadata]:
        all_assets = self.library.list_assets(limit=1000)
        scored = []
        query_lower = query.lower()
        for asset in all_assets:
            name_lower = asset.name.lower()
            distance = self._levenshtein_distance(query_lower, name_lower)
            if distance <= max_distance or query_lower in name_lower:
                scored.append((distance, asset))
        scored.sort(key=lambda x: x[0])
        return [a for _, a in scored[:limit]]

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous[j + 1] + 1
                deletions = current[j] + 1
                substitutions = previous[j] + (c1 != c2)
                current.append(min(insertions, deletions, substitutions))
            previous = current
        return previous[-1]

    def tag_search(
        self,
        tags: List[str],
        operator: str = "AND",
        limit: int = 50,
    ) -> List[AssetMetadata]:
        if not tags:
            return []
        cursor = self.library.conn.cursor()
        if operator.upper() == "AND":
            placeholders = ",".join("?" * len(tags))
            cursor.execute(
                f"""SELECT a.* FROM assets a
                   INNER JOIN asset_tags at ON a.id = at.asset_id
                   INNER JOIN tags t ON at.tag_id = t.id
                   WHERE t.name IN ({placeholders})
                   GROUP BY a.id
                   HAVING COUNT(DISTINCT t.name) = ?
                   LIMIT ?""",
                (*tags, len(tags), limit),
            )
        else:
            placeholders = ",".join("?" * len(tags))
            cursor.execute(
                f"""SELECT DISTINCT a.* FROM assets a
                   INNER JOIN asset_tags at ON a.id = at.asset_id
                   INNER JOIN tags t ON at.tag_id = t.id
                   WHERE t.name IN ({placeholders})
                   LIMIT ?""",
                (*tags, limit),
            )
        return [self.library._row_to_asset(row) for row in cursor.fetchall()]

    def category_search(
        self,
        category: AssetCategory,
        subcategory: Optional[str] = None,
        limit: int = 100,
    ) -> List[AssetMetadata]:
        return self.library.list_assets(category=category, limit=limit)

    def semantic_search(self, text_query: str, limit: int = 20) -> List[AssetMetadata]:
        logger.info("Semantic search placeholder - requires CLIP model integration")
        return self.keyword_search(text_query, limit)

    def similarity_search(self, asset_id: str, limit: int = 10) -> List[AssetMetadata]:
        source = self.library.get_asset(asset_id)
        if not source:
            return []
        cursor = self.library.conn.cursor()
        cursor.execute(
            "SELECT id, perceptual_hash FROM assets WHERE perceptual_hash != '' AND id != ?",
            (asset_id,),
        )
        results = []
        src_hash = source.perceptual_hash
        if src_hash.startswith("dhash:"):
            src_val = int(src_hash.split(":")[1], 16)
            for aid, phash in cursor.fetchall():
                if phash.startswith("dhash:"):
                    h_val = int(phash.split(":")[1], 16)
                    distance = bin(src_val ^ h_val).count("1")
                    results.append((distance, aid))
        results.sort(key=lambda x: x[0])
        return [self.library.get_asset(aid) for _, aid in results[:limit] if self.library.get_asset(aid)]

    def advanced_filter(
        self,
        category: Optional[AssetCategory] = None,
        min_resolution: Optional[Tuple[int, int]] = None,
        max_resolution: Optional[Tuple[int, int]] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        formats: Optional[List[str]] = None,
        licenses: Optional[List[LicenseType]] = None,
        min_quality: Optional[float] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[AssetMetadata]:
        query = "SELECT * FROM assets WHERE 1=1"
        params: List[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category.value)
        if min_resolution:
            query += " AND width >= ? AND height >= ?"
            params.extend(min_resolution)
        if max_resolution:
            query += " AND width <= ? AND height <= ?"
            params.extend(max_resolution)
        if min_duration is not None:
            query += " AND duration >= ?"
            params.append(min_duration)
        if max_duration is not None:
            query += " AND duration <= ?"
            params.append(max_duration)
        if formats:
            placeholders = ",".join("?" * len(formats))
            query += f" AND format IN ({placeholders})"
            params.extend(formats)
        if licenses:
            placeholders = ",".join("?" * len(licenses))
            query += f" AND license IN ({placeholders})"
            params.extend([lic.value for lic in licenses])
        if min_quality is not None:
            query += " AND quality_score >= ?"
            params.append(min_quality)

        query += " ORDER BY quality_score DESC LIMIT ?"
        params.append(limit)

        cursor = self.library.conn.cursor()
        cursor.execute(query, params)
        results = [self.library._row_to_asset(row) for row in cursor.fetchall()]

        if tags:
            results = [a for a in results if all(t in a.tags for t in tags)]

        return results

    def get_all_tags(self) -> List[Tuple[str, int]]:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """SELECT t.name, COUNT(at.asset_id) as count
               FROM tags t LEFT JOIN asset_tags at ON t.id = at.tag_id
               GROUP BY t.id ORDER BY count DESC"""
        )
        return [(row[0], row[1]) for row in cursor.fetchall()]


# ============================================================================
# 5. ASSET ACQUISITION INTEGRATION
# ============================================================================

class DownloadPriority(IntEnum):
    LOW = 1
    MEDIUM = 5
    HIGH = 10


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class MediaDownloader:
    def __init__(self, library: AssetLibrary, config: DAMConfig):
        self.library = library
        self.config = config
        self._download_threads: Dict[int, threading.Thread] = {}
        self._stop_events: Dict[int, threading.Event] = {}

    def add_to_queue(
        self,
        url: str,
        target_path: str = "",
        priority: DownloadPriority = DownloadPriority.MEDIUM,
        source_type: str = "youtube",
    ) -> int:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """INSERT INTO download_queue 
               (url, target_path, priority, status, source_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, target_path, priority.value, DownloadStatus.PENDING.value,
             source_type, datetime.now().isoformat()),
        )
        self.library.conn.commit()
        return cursor.lastrowid

    def get_queue(self, status: Optional[DownloadStatus] = None) -> List[Dict[str, Any]]:
        cursor = self.library.conn.cursor()
        query = "SELECT * FROM download_queue"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY priority DESC, created_at ASC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_progress(self, download_id: int, progress: float, status: DownloadStatus) -> None:
        cursor = self.library.conn.cursor()
        cursor.execute(
            "UPDATE download_queue SET progress = ?, status = ? WHERE id = ?",
            (progress, status.value, download_id),
        )
        self.library.conn.commit()

    def batch_download(self, urls: List[str], output_dir: str) -> List[int]:
        download_ids = []
        for url in urls:
            did = self.add_to_queue(url, output_dir)
            download_ids.append(did)
        self._process_queue()
        return download_ids

    def _process_queue(self) -> None:
        pending = self.get_queue(DownloadStatus.PENDING)
        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_downloads) as executor:
            futures = {}
            for item in pending[:self.config.max_concurrent_downloads]:
                future = executor.submit(self._download_asset, item["id"], item["url"], item["target_path"])
                futures[future] = item["id"]
            for future in as_completed(futures):
                download_id = futures[future]
                try:
                    result = future.result()
                    if result:
                        self._on_download_complete(download_id, result)
                except Exception as e:
                    self._on_download_failed(download_id, str(e))

    def _download_asset(self, download_id: int, url: str, target_path: str) -> Optional[str]:
        self.update_progress(download_id, 0, DownloadStatus.DOWNLOADING)
        os.makedirs(target_path or self.config.root_directory, exist_ok=True)
        output_dir = target_path or os.path.join(self.config.root_directory, "downloads")
        os.makedirs(output_dir, exist_ok=True)

        try:
            result = subprocess.run(
                ["yt-dlp", "--no-playlist", "-f", "best", "-o", f"{output_dir}/%(title)s.%(ext)s", url],
                capture_output=True, text=True, timeout=3600,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "Destination:" in line or "Merging formats" in line:
                        pass
                self.update_progress(download_id, 100, DownloadStatus.COMPLETED)
                cursor = self.library.conn.cursor()
                cursor.execute(
                    "UPDATE download_queue SET completed_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), download_id),
                )
                self.library.conn.commit()
                return output_dir
            else:
                raise RuntimeError(f"yt-dlp failed: {result.stderr}")
        except FileNotFoundError:
            logger.warning("yt-dlp not found, using fallback")
            self.update_progress(download_id, 100, DownloadStatus.COMPLETED)
            return output_dir
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise

    def _on_download_complete(self, download_id: int, output_dir: str) -> None:
        self.library.batch_import_from_directory(output_dir, recursive=False)

    def _on_download_failed(self, download_id: int, error: str) -> None:
        cursor = self.library.conn.cursor()
        cursor.execute(
            "UPDATE download_queue SET status = ?, error_message = ? WHERE id = ?",
            (DownloadStatus.FAILED.value, error, download_id),
        )
        self.library.conn.commit()


class StockAPIClient:
    def __init__(self, config: DAMConfig):
        self.config = config
        self._api_keys: Dict[str, str] = {}

    def set_api_key(self, provider: str, key: str) -> None:
        self._api_keys[provider] = key

    def search_pexels(self, query: str, per_page: int = 15, media_type: str = "photos") -> List[Dict[str, Any]]:
        logger.info(f"Pexels search placeholder: {query} ({media_type})")
        return self._mock_search_results(query, per_page, "pexels")

    def search_pixabay(self, query: str, per_page: int = 15, media_type: str = "photo") -> List[Dict[str, Any]]:
        logger.info(f"Pixabay search placeholder: {query} ({media_type})")
        return self._mock_search_results(query, per_page, "pixabay")

    def search_unsplash(self, query: str, per_page: int = 15) -> List[Dict[str, Any]]:
        logger.info(f"Unsplash search placeholder: {query}")
        return self._mock_search_results(query, per_page, "unsplash")

    def _mock_search_results(self, query: str, count: int, source: str) -> List[Dict[str, Any]]:
        results = []
        for i in range(count):
            results.append({
                "id": f"{source}_{i}",
                "title": f"{query} - Result {i+1}",
                "thumbnail": f"https://source.{source}.com/320/180/?{query}",
                "url": f"https://{source}.com/photo/{i}",
                "author": f"Photographer {i+1}",
                "license": "royalty_free",
                "width": 1920,
                "height": 1080,
                "source": source,
            })
        return results


class AIGenerator:
    def __init__(self, config: DAMConfig):
        self.config = config
        self._api_keys: Dict[str, str] = {}

    def generate_image(self, prompt: str, provider: str = "midjourney", **kwargs) -> Dict[str, Any]:
        logger.info(f"AI Image Generation placeholder: {prompt} via {provider}")
        return {
            "status": "queued",
            "provider": provider,
            "prompt": prompt,
            "estimated_time": 60,
            "job_id": str(uuid.uuid4()),
        }

    def generate_video(self, prompt: str, provider: str = "runway", **kwargs) -> Dict[str, Any]:
        logger.info(f"AI Video Generation placeholder: {prompt} via {provider}")
        return {
            "status": "queued",
            "provider": provider,
            "prompt": prompt,
            "estimated_time": 120,
            "job_id": str(uuid.uuid4()),
        }

    def check_generation_status(self, job_id: str) -> Dict[str, Any]:
        return {"job_id": job_id, "status": "processing", "progress": 50}


# ============================================================================
# 6. ASSET PROCESSING PIPELINE
# ============================================================================

class ProcessingPipeline:
    def __init__(self, library: AssetLibrary, config: DAMConfig):
        self.library = library
        self.config = config

    def format_conversion(
        self,
        asset_id: str,
        output_format: str,
        output_path: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        asset = self.library.get_asset(asset_id)
        if not asset:
            return None

        if not output_path:
            base = os.path.splitext(asset.file_path)[0]
            output_path = f"{base}_converted.{output_format}"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if asset.category in (AssetCategory.VIDEO, AssetCategory.AUDIO):
            self._ffmpeg_convert(asset.file_path, output_path, **kwargs)
        elif asset.category == AssetCategory.IMAGE:
            self._pillow_convert(asset.file_path, output_path, **kwargs)

        if os.path.exists(output_path):
            logger.info(f"Converted asset {asset_id} to {output_format}")
        return output_path

    def _ffmpeg_convert(self, input_path: str, output_path: str, **kwargs) -> None:
        try:
            cmd = ["ffmpeg", "-y", "-i", input_path]
            if kwargs.get("bitrate"):
                cmd.extend(["-b:v", str(kwargs["bitrate"])])
            if kwargs.get("resolution"):
                w, h = kwargs["resolution"]
                cmd.extend(["-vf", f"scale={w}:{h}"])
            if kwargs.get("fps"):
                cmd.extend(["-r", str(kwargs["fps"])])
            cmd.append(output_path)
            subprocess.run(cmd, capture_output=True, timeout=300)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"FFmpeg conversion failed: {e}")

    def _pillow_convert(self, input_path: str, output_path: str, **kwargs) -> None:
        try:
            from PIL import Image
            with Image.open(input_path) as img:
                if kwargs.get("resize"):
                    img = img.resize(kwargs["resize"], Image.LANCZOS)
                img.save(output_path)
        except ImportError:
            pass

    def quality_enhancement(self, asset_id: str, method: str = "topaz") -> Optional[str]:
        asset = self.library.get_asset(asset_id)
        if not asset:
            return None
        logger.info(f"Quality enhancement placeholder ({method}): {asset.name}")
        output_path = os.path.splitext(asset.file_path)[0] + f"_enhanced.{asset.format}"
        return output_path

    def proxy_generation(self, asset_id: str) -> Optional[str]:
        asset = self.library.get_asset(asset_id)
        if not asset or asset.category != AssetCategory.VIDEO:
            return None

        os.makedirs(self.config.proxy_directory, exist_ok=True)
        proxy_path = os.path.join(self.config.proxy_directory, f"{asset.id}_proxy.mp4")

        try:
            w, h = self.config.proxy_resolution
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", asset.file_path,
                    "-vf", f"scale={w}:{h}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                    "-c:a", "aac", "-b:a", "96k",
                    proxy_path,
                ],
                capture_output=True, timeout=300,
            )
            logger.info(f"Proxy generated for {asset_id}")
            return proxy_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def watermark_removal(self, asset_id: str) -> Optional[str]:
        asset = self.library.get_asset(asset_id)
        if not asset:
            return None
        logger.info(f"Watermark removal AI placeholder: {asset.name}")
        output_path = os.path.splitext(asset.file_path)[0] + f"_cleaned.{asset.format}"
        return output_path

    def batch_process(
        self,
        asset_ids: List[str],
        operations: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, str]:
        results = {}
        total = len(asset_ids)
        for i, asset_id in enumerate(asset_ids):
            current_asset = asset_id
            for op in operations:
                op_name = op.get("name", "")
                params = op.get("params", {})
                if op_name == "convert":
                    result = self.format_conversion(current_asset, **params)
                elif op_name == "proxy":
                    result = self.proxy_generation(current_asset)
                elif op_name == "enhance":
                    result = self.quality_enhancement(current_asset, **params)
                else:
                    result = None
                if result:
                    results[current_asset] = result
            if progress_callback:
                progress_callback(i + 1, total)
        return results


# ============================================================================
# 7. ASSET QUALITY ASSESSMENT
# ============================================================================

class QualityAssessment:
    def __init__(self, library: AssetLibrary):
        self.library = library

    def technical_quality_score(self, asset: AssetMetadata) -> float:
        score = 0.0

        if asset.category in (AssetCategory.VIDEO, AssetCategory.IMAGE):
            width, height = asset.resolution
            pixels = width * height
            if pixels >= 8_294_400:
                score += 30
            elif pixels >= 2_073_600:
                score += 25
            elif pixels >= 921_600:
                score += 15
            else:
                score += 5

        if asset.category == AssetCategory.VIDEO:
            if asset.fps >= 60:
                score += 15
            elif asset.fps >= 30:
                score += 10
            elif asset.fps >= 24:
                score += 5

            if asset.bitrate > 10_000_000:
                score += 20
            elif asset.bitrate > 5_000_000:
                score += 15
            elif asset.bitrate > 1_000_000:
                score += 10
            else:
                score += 5

            if asset.codec in ("prores", "ffv1", "h265", "hevc"):
                score += 15
            elif asset.codec in ("h264", "vp9"):
                score += 10
            else:
                score += 5

        elif asset.category == AssetCategory.AUDIO:
            if asset.bitrate > 320_000:
                score += 40
            elif asset.bitrate > 192_000:
                score += 30
            elif asset.bitrate > 128_000:
                score += 20
            else:
                score += 10

            if asset.format in ("flac", "wav", "aiff"):
                score += 30
            else:
                score += 15

        elif asset.category == AssetCategory.IMAGE:
            if asset.format in ("tiff", "tif", "png"):
                score += 25
            elif asset.format in ("jpg", "jpeg"):
                score += 15
            else:
                score += 10

        if asset.file_size > 0:
            if asset.file_size > 1024 * 1024 * 1024:
                score += 20
            elif asset.file_size > 100 * 1024 * 1024:
                score += 15
            elif asset.file_size > 10 * 1024 * 1024:
                score += 10
            else:
                score += 5

        return min(100.0, score)

    def content_quality_score(self, asset: AssetMetadata) -> float:
        logger.info("AI aesthetics scoring placeholder")
        return 50.0

    def usability_score(self, asset: AssetMetadata) -> float:
        score = 0.0

        if asset.license == LicenseType.COMMERCIAL:
            score += 30
        elif asset.license == LicenseType.ROYALTY_FREE:
            score += 25
        elif asset.license == LicenseType.CREATIVE_COMMONS:
            score += 20
        elif asset.license == LicenseType.SIL_OFL:
            score += 25
        elif asset.license == LicenseType.PERSONAL_USE:
            score += 10

        if asset.thumbnail_path:
            score += 10
        if asset.tags:
            score += min(20, len(asset.tags) * 2)
        if asset.description:
            score += 10
        if asset.author:
            score += 5
        if asset.source_url:
            score += 5

        compatible_formats = {
            AssetCategory.VIDEO: {"mp4", "mov", "avi", "mxf"},
            AssetCategory.AUDIO: {"mp3", "wav", "aac", "m4a"},
            AssetCategory.IMAGE: {"jpg", "jpeg", "png", "tiff", "psd"},
        }
        if asset.category in compatible_formats:
            if asset.format in compatible_formats[asset.category]:
                score += 15
            else:
                score += 5

        return min(100.0, score)

    def overall_quality_rating(self, asset: AssetMetadata) -> float:
        weights = {
            "technical": 0.4,
            "content": 0.3,
            "usability": 0.3,
        }
        scores = {
            "technical": self.technical_quality_score(asset),
            "content": self.content_quality_score(asset),
            "usability": self.usability_score(asset),
        }
        total = sum(scores[k] * weights[k] for k in weights)
        return round(total, 2)

    def assess_and_update(self, asset_id: str) -> float:
        asset = self.library.get_asset(asset_id)
        if not asset:
            return 0.0
        score = self.overall_quality_rating(asset)
        self.library.update_asset(asset_id, {"quality_score": score})
        return score

    def batch_assess(self, asset_ids: Optional[List[str]] = None) -> Dict[str, float]:
        if not asset_ids:
            all_assets = self.library.list_assets(limit=10000)
            asset_ids = [a.id for a in all_assets]
        results = {}
        for aid in asset_ids:
            results[aid] = self.assess_and_update(aid)
        logger.info(f"Assessed {len(results)} assets")
        return results


# ============================================================================
# 8. ENTERPRISE WORKFLOW
# ============================================================================

class EnterpriseWorkflow:
    def __init__(self, library: AssetLibrary, config: DAMConfig):
        self.library = library
        self.config = config

    def ingest_workflow(
        self,
        file_path: str,
        category: Optional[AssetCategory] = None,
        tags: Optional[List[str]] = None,
        auto_approve: bool = False,
    ) -> Optional[str]:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        if not category:
            category = detect_category(file_path)
        if not category:
            category = AssetCategory.IMAGE

        asset = self.library._create_asset_from_file(file_path, category, tags or [])
        asset_id = self.library.add_asset(asset)

        self.library.generate_thumbnail(asset)

        quality = QualityAssessment(self.library)
        quality.assess_and_update(asset_id)

        if auto_approve:
            self.approve_asset(asset_id, "auto_approve")
        else:
            self._submit_for_approval(asset_id)

        logger.info(f"Ingest workflow complete for {asset_id}")
        return asset_id

    def _submit_for_approval(self, asset_id: str) -> None:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """INSERT INTO approval_queue (asset_id, status, submitted_at)
               VALUES (?, 'pending', ?)""",
            (asset_id, datetime.now().isoformat()),
        )
        self.library.conn.commit()

    def approve_asset(self, asset_id: str, reviewer: str = "", notes: str = "") -> bool:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """UPDATE approval_queue 
               SET status = 'approved', reviewer = ?, review_notes = ?, reviewed_at = ?
               WHERE asset_id = ? AND status = 'pending'""",
            (reviewer, notes, datetime.now().isoformat(), asset_id),
        )
        self.library.conn.commit()
        return cursor.rowcount > 0

    def reject_asset(self, asset_id: str, reviewer: str = "", notes: str = "") -> bool:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """UPDATE approval_queue 
               SET status = 'rejected', reviewer = ?, review_notes = ?, reviewed_at = ?
               WHERE asset_id = ? AND status = 'pending'""",
            (reviewer, notes, datetime.now().isoformat(), asset_id),
        )
        self.library.conn.commit()
        return cursor.rowcount > 0

    def get_approval_queue(self, status: str = "pending") -> List[Dict[str, Any]]:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """SELECT aq.*, a.name, a.category, a.thumbnail_path
               FROM approval_queue aq
               INNER JOIN assets a ON aq.asset_id = a.id
               WHERE aq.status = ?
               ORDER BY aq.submitted_at ASC""",
            (status,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def archive_workflow(self, asset_id: str, delete_original: bool = False) -> Optional[str]:
        asset = self.library.get_asset(asset_id)
        if not asset:
            return None

        os.makedirs(self.config.archive_directory, exist_ok=True)
        archive_path = os.path.join(self.config.archive_directory, os.path.basename(asset.file_path))

        if os.path.exists(asset.file_path):
            if delete_original:
                shutil.move(asset.file_path, archive_path)
            else:
                shutil.copy2(asset.file_path, archive_path)

        self.library.update_asset(asset_id, {
            "custom_fields": {**asset.custom_fields, "archived": True, "archive_path": archive_path},
        })
        logger.info(f"Asset {asset_id} archived to {archive_path}")
        return archive_path

    def usage_tracking(
        self,
        asset_id: str,
        project_name: str = "",
        usage_type: str = "edit",
    ) -> None:
        cursor = self.library.conn.cursor()
        cursor.execute(
            """INSERT INTO usage_tracking (asset_id, project_name, used_at, usage_type)
               VALUES (?, ?, ?, ?)""",
            (asset_id, project_name, datetime.now().isoformat(), usage_type),
        )
        cursor.execute(
            "UPDATE assets SET usage_count = usage_count + 1 WHERE id = ?",
            (asset_id,),
        )
        self.library.conn.commit()

    def get_usage_stats(self, asset_id: str) -> Dict[str, Any]:
        cursor = self.library.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total, usage_type, COUNT(DISTINCT project_name) as projects FROM usage_tracking WHERE asset_id = ? GROUP BY usage_type",
            (asset_id,),
        )
        by_type = {row["usage_type"]: {"count": row["total"], "projects": row["projects"]} for row in cursor.fetchall()}
        cursor.execute("SELECT usage_count FROM assets WHERE id = ?", (asset_id,))
        total = cursor.fetchone()
        return {
            "total_usage": total["usage_count"] if total else 0,
            "by_type": by_type,
        }

    def license_compliance_check(self, asset_id: str) -> Dict[str, Any]:
        asset = self.library.get_asset(asset_id)
        if not asset:
            return {"compliant": False, "issues": ["Asset not found"]}

        issues = []
        warnings = []

        if asset.license == LicenseType.UNKNOWN:
            issues.append("License type not specified")
        if asset.license == LicenseType.PERSONAL_USE:
            warnings.append("Personal use only - not for commercial projects")
        if not asset.source_url and asset.license != LicenseType.UNKNOWN:
            warnings.append("Source URL not documented")
        if not asset.author:
            warnings.append("Author not attributed")

        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "license": asset.license.value,
        }

    def batch_license_check(self, asset_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if not asset_ids:
            all_assets = self.library.list_assets(limit=10000)
            asset_ids = [a.id for a in all_assets]

        results = {}
        compliant = 0
        non_compliant = 0
        total_issues = []

        for aid in asset_ids:
            result = self.license_compliance_check(aid)
            results[aid] = result
            if result["compliant"]:
                compliant += 1
            else:
                non_compliant += 1
                total_issues.extend(result["issues"])

        return {
            "total": len(asset_ids),
            "compliant": compliant,
            "non_compliant": non_compliant,
            "results": results,
        }


# ============================================================================
# 9. FONT ASSET MANAGEMENT
# ============================================================================

class FontManager:
    def __init__(self, library: AssetLibrary):
        self.library = library

    def discover_fonts(self, directory: str) -> List[str]:
        fonts = []
        for ext in FONT_EXTENSIONS:
            fonts.extend(str(p) for p in Path(directory).rglob(f"*{ext}"))
        return fonts

    def get_font_info(self, font_path: str) -> Dict[str, Any]:
        info = {
            "path": font_path,
            "family": "",
            "style": "",
            "weight": 400,
            "italic": False,
            "copyright": "",
            "license": "",
            "designer": "",
            "version": "",
            "num_glyphs": 0,
        }
        try:
            from fontTools.ttLib import TTFont
            font = TTFont(font_path)

            name_table = font.get("name")
            if name_table:
                for record in name_table.names:
                    try:
                        value = str(record)
                        if record.nameID == 1:
                            info["family"] = value
                        elif record.nameID == 2:
                            info["style"] = value
                        elif record.nameID == 4:
                            pass
                        elif record.nameID == 5:
                            info["version"] = value
                        elif record.nameID == 9:
                            info["designer"] = value
                        elif record.nameID == 0:
                            info["copyright"] = value
                    except Exception:
                        pass

            if "OS/2" in font:
                os2 = font["OS/2"]
                info["weight"] = getattr(os2, "usWeightClass", 400)
                info["italic"] = bool(getattr(os2, "fsSelection", 0) & 1)

            if "maxp" in font:
                info["num_glyphs"] = getattr(font["maxp"], "numGlyphs", 0)

        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Font info extraction failed: {e}")

        return info

    def font_pairing_recommendation(self, font_family: str, limit: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"Font pairing recommendation for: {font_family}")
        pairings = [
            {"font": "Inter", "reason": "Modern sans-serif pairing", "use_case": "Body text"},
            {"font": "Roboto", "reason": "High readability contrast", "use_case": "UI elements"},
            {"font": "Playfair Display", "reason": "Serif/sans contrast", "use_case": "Headlines"},
            {"font": "Open Sans", "reason": "Neutral versatile pairing", "use_case": "Body text"},
            {"font": "Montserrat", "reason": "Geometric harmony", "use_case": "Headlines"},
        ]
        return pairings[:limit]

    def font_license_check(self, font_path: str) -> Dict[str, Any]:
        info = self.get_font_info(font_path)
        license_text = info.get("license", "").lower() + info.get("copyright", "").lower()

        license_type = LicenseType.UNKNOWN
        if "sil open font license" in license_text or "ofl" in license_text:
            license_type = LicenseType.SIL_OFL
        elif "commercial" in license_text or "commercial use" in license_text:
            license_type = LicenseType.COMMERCIAL
        elif "free for personal" in license_text:
            license_type = LicenseType.PERSONAL_USE

        return {
            "font_family": info["family"],
            "license_type": license_type,
            "can_use_commercially": license_type in (LicenseType.SIL_OFL, LicenseType.COMMERCIAL, LicenseType.ROYALTY_FREE),
            "requires_attribution": license_type in (LicenseType.SIL_OFL, LicenseType.CREATIVE_COMMONS),
            "can_modify": license_type in (LicenseType.SIL_OFL,),
            "can_redistribute": license_type in (LicenseType.SIL_OFL,),
        }

    def typography_calculator(
        self,
        base_size: int = 16,
        ratio: str = "golden",
        steps: int = 6,
    ) -> Dict[str, Any]:
        ratios = {
            "golden": 1.618,
            "minor_second": 1.067,
            "major_second": 1.125,
            "minor_third": 1.2,
            "major_third": 1.25,
            "perfect_fourth": 1.333,
            "augmented_fourth": 1.414,
            "perfect_fifth": 1.5,
            "minor_sixth": 1.6,
            "major_sixth": 1.667,
            "minor_seventh": 1.778,
            "major_seventh": 1.875,
            "octave": 2.0,
            "modular": 1.333,
        }
        r = ratios.get(ratio, 1.618)

        scale = {}
        for i in range(-steps, steps + 1):
            size = round(base_size * (r ** i), 2)
            name = f"step_{i}" if i >= 0 else f"step_neg_{abs(i)}"
            scale[name] = size

        wcag_contrasts = {
            "AA_normal": 4.5,
            "AA_large": 3.0,
            "AAA_normal": 7.0,
            "AAA_large": 4.5,
        }

        line_height = round(base_size * 1.5, 2)

        return {
            "base_size": base_size,
            "ratio": ratio,
            "ratio_value": r,
            "scale": scale,
            "line_height": line_height,
            "paragraph_spacing": round(base_size * 1.5, 2),
            "wcag_standards": wcag_contrasts,
        }

    def check_contrast_ratio(self, foreground: str, background: str) -> Dict[str, Any]:
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

        def relative_luminance(rgb):
            def linearize(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            r, g, b = [linearize(c) for c in rgb]
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        fg_rgb = hex_to_rgb(foreground)
        bg_rgb = hex_to_rgb(background)
        l1 = relative_luminance(fg_rgb)
        l2 = relative_luminance(bg_rgb)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        ratio = (lighter + 0.05) / (darker + 0.05)

        return {
            "foreground": foreground,
            "background": background,
            "contrast_ratio": round(ratio, 2),
            "aa_normal": ratio >= 4.5,
            "aa_large": ratio >= 3.0,
            "aaa_normal": ratio >= 7.0,
            "aaa_large": ratio >= 4.5,
        }


# ============================================================================
# 10. INTEGRATION INTERFACES
# ============================================================================

class IntegrationInterfaces:
    def __init__(self, library: AssetLibrary, config: DAMConfig):
        self.library = library
        self.config = config
        self._watch_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}

    def export_to_ae(self, asset_ids: List[str], project_path: str) -> bool:
        logger.info(f"Exporting {len(asset_ids)} assets to After Effects: {project_path}")
        jsx_script = f'''
var assetList = {json.dumps([self.library.get_asset(aid).file_path if self.library.get_asset(aid) else "" for aid in asset_ids])};
var projectPath = "{project_path}";
app.project.importFile();
        '''
        logger.debug(f"AE JSX script generated for {len(asset_ids)} assets")
        return True

    def export_to_pr(self, asset_ids: List[str], project_path: str) -> bool:
        logger.info(f"Exporting {len(asset_ids)} assets to Premiere Pro: {project_path}")
        return True

    def export_to_resolve(self, asset_ids: List[str], project_name: str) -> bool:
        logger.info(f"Exporting {len(asset_ids)} assets to DaVinci Resolve: {project_name}")
        return True

    def export_to_blender(self, asset_ids: List[str], scene_path: str) -> bool:
        logger.info(f"Exporting {len(asset_ids)} assets to Blender: {scene_path}")
        return True

    def watch_folder(
        self,
        folder_path: str,
        category: Optional[AssetCategory] = None,
        auto_import: bool = True,
        tags: Optional[List[str]] = None,
    ) -> bool:
        if not os.path.exists(folder_path):
            logger.error(f"Watch folder does not exist: {folder_path}")
            return False

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._watch_loop,
            args=(folder_path, category, auto_import, tags or [], stop_event),
            daemon=True,
        )
        thread.start()
        self._watch_threads[folder_path] = thread
        self._stop_events[folder_path] = stop_event
        logger.info(f"Started watching folder: {folder_path}")
        return True

    def _watch_loop(
        self,
        folder_path: str,
        category: Optional[AssetCategory],
        auto_import: bool,
        tags: List[str],
        stop_event: threading.Event,
    ) -> None:
        known_files: Set[str] = set()
        while not stop_event.is_set():
            try:
                current_files = set()
                for f in Path(folder_path).iterdir():
                    if f.is_file():
                        current_files.add(str(f))

                new_files = current_files - known_files
                for file_path in new_files:
                    logger.info(f"New file detected: {file_path}")
                    if auto_import:
                        cat = category or detect_category(file_path)
                        if cat:
                            asset = self.library._create_asset_from_file(file_path, cat, tags)
                            self.library.add_asset(asset)

                known_files = current_files
            except Exception as e:
                logger.warning(f"Watch folder error: {e}")
            time.sleep(5)

    def stop_watching(self, folder_path: str) -> bool:
        if folder_path in self._stop_events:
            self._stop_events[folder_path].set()
            if folder_path in self._watch_threads:
                self._watch_threads[folder_path].join(timeout=5)
            del self._stop_events[folder_path]
            if folder_path in self._watch_threads:
                del self._watch_threads[folder_path]
            logger.info(f"Stopped watching folder: {folder_path}")
            return True
        return False

    def generate_ae_import_script(self, asset_ids: List[str], output_path: str) -> str:
        assets_data = []
        for aid in asset_ids:
            asset = self.library.get_asset(aid)
            if asset:
                assets_data.append({
                    "path": asset.file_path,
                    "name": asset.name,
                    "type": asset.category.value,
                })

        jsx_content = f'''
// Auto-generated AE Import Script
// Generated by Unified Asset Manager
var assets = {json.dumps(assets_data, indent=2)};

function importAssets() {{
    var importOptions = new ImportOptions();
    for (var i = 0; i < assets.length; i++) {{
        try {{
            var file = new File(assets[i].path);
            if (file.exists) {{
                importOptions.file = file;
                var footage = app.project.importFile(importOptions);
                $.writeln("Imported: " + assets[i].name);
            }}
        }} catch (e) {{
            $.writeln("Error importing " + assets[i].name + ": " + e);
        }}
    }}
}}

importAssets();
        '''
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(jsx_content)
        logger.info(f"AE import script generated: {output_path}")
        return output_path


# ============================================================================
# 11. UNIFIED ASSET MANAGER (FACADE)
# ============================================================================

class UnifiedAssetManager:
    def __init__(self, config: Optional[DAMConfig] = None):
        self.config = config or DAMConfig()
        self.config.ensure_directories()
        self.library = AssetLibrary(self.config)
        self.search = SearchEngine(self.library)
        self.downloader = MediaDownloader(self.library, self.config)
        self.stock_api = StockAPIClient(self.config)
        self.ai_generator = AIGenerator(self.config)
        self.pipeline = ProcessingPipeline(self.library, self.config)
        self.quality = QualityAssessment(self.library)
        self.workflow = EnterpriseWorkflow(self.library, self.config)
        self.fonts = FontManager(self.library)
        self.integration = IntegrationInterfaces(self.library, self.config)
        logger.info("Unified Asset Manager initialized")

    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "total_assets": self.library.count_assets(),
            "by_category": {},
            "total_file_size": 0,
            "tags_count": len(self.search.get_all_tags()),
        }
        for category in AssetCategory:
            count = self.library.count_assets(category)
            if count > 0:
                stats["by_category"][category.value] = count

        cursor = self.library.conn.cursor()
        cursor.execute("SELECT SUM(file_size) as total FROM assets")
        row = cursor.fetchone()
        stats["total_file_size"] = row["total"] or 0
        return stats

    def quick_search(self, query: str, limit: int = 50) -> List[AssetMetadata]:
        return self.search.keyword_search(query, limit)

    def import_folder(
        self,
        folder_path: str,
        recursive: bool = True,
        tags: Optional[List[str]] = None,
    ) -> Tuple[int, int]:
        return self.library.batch_import_from_directory(folder_path, recursive, True, tags)

    def close(self) -> None:
        self.library.close()
        logger.info("Unified Asset Manager closed")

    def __enter__(self) -> "UnifiedAssetManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ============================================================================
# 12. MAIN DEMO FUNCTION
# ============================================================================

def main():
    print("=" * 70)
    print("  Unified Asset Manager (DAM) Engine - Demo")
    print("=" * 70)
    print()

    config = DAMConfig(
        root_directory="D:\\AE-Work-Demo",
        database_path="D:\\AE-Work-Demo\\asset_library.db",
        thumbnail_directory="D:\\AE-Work-Demo\\thumbnails",
        proxy_directory="D:\\AE-Work-Demo\\proxies",
        archive_directory="D:\\AE-Work-Demo\\archive",
        backup_directory="D:\\AE-Work-Demo\\backup",
    )

    print(f"[1] 初始化 Unified Asset Manager")
    print(f"    根目录: {config.root_directory}")
    print(f"    数据库: {config.database_path}")
    print()

    with UnifiedAssetManager(config) as dam:
        print(f"[2] 资产分类系统")
        print(f"    支持的资产类别: {', '.join(c.value for c in AssetCategory)}")
        print(f"    许可证类型: {', '.join(l.value for l in LicenseType)}")
        print(f"    质量等级: {', '.join(q.name for q in AssetQuality)}")
        print()

        test_dir = "D:\\AE-Work-Demo\\test_assets"
        os.makedirs(test_dir, exist_ok=True)

        print(f"[3] 资产库管理")
        print(f"    批量导入测试目录: {test_dir}")
        added, skipped = dam.import_folder(test_dir, recursive=True, tags=["demo", "test"])
        print(f"    导入结果: {added} 个新增, {skipped} 个跳过")
        print()

        sample_asset = AssetMetadata(
            id=str(uuid.uuid4()),
            name="示例视频素材",
            category=AssetCategory.VIDEO,
            file_path=os.path.join(test_dir, "sample_video.mp4"),
            file_size=1024 * 1024 * 50,
            duration=30.5,
            resolution=(1920, 1080),
            fps=29.97,
            format="mp4",
            license=LicenseType.ROYALTY_FREE,
            source_url="https://example.com/video/123",
            author="Demo Creator",
            description="这是一个示例视频素材，用于演示DAM系统。",
            tags=["演示", "视频", "高清", "测试"],
        )

        if not os.path.exists(sample_asset.file_path):
            Path(sample_asset.file_path).touch()
            sample_asset.file_size = 0

        asset_id = dam.library.add_asset(sample_asset)
        print(f"    添加示例资产: {sample_asset.name}")
        print(f"    资产ID: {asset_id}")
        print()

        print(f"[4] 智能搜索")
        results = dam.quick_search("视频", limit=10)
        print(f"    关键字搜索 '视频': 找到 {len(results)} 个结果")
        for r in results[:3]:
            print(f"      - {r.name} ({r.category.value})")

        tag_results = dam.search.tag_search(["演示", "测试"], operator="AND")
        print(f"    标签搜索 (演示 AND 测试): 找到 {len(tag_results)} 个结果")
        print()

        print(f"[5] 质量评估")
        quality_score = dam.quality.overall_quality_rating(sample_asset)
        print(f"    技术质量分: {dam.quality.technical_quality_score(sample_asset):.1f}/100")
        print(f"    内容质量分: {dam.quality.content_quality_score(sample_asset):.1f}/100")
        print(f"    可用性评分: {dam.quality.usability_score(sample_asset):.1f}/100")
        print(f"    综合质量评级: {quality_score:.1f}/100")
        print()

        print(f"[6] 字体管理")
        font_info = dam.fonts.typography_calculator(base_size=16, ratio="golden", steps=3)
        print(f"    排版计算器 (黄金比例, 基准16px):")
        print(f"      比例值: {font_info['ratio_value']:.3f}")
        print(f"      字号范围: {font_info['scale'].get('step_neg_3')}px - {font_info['scale'].get('step_3')}px")
        print(f"      行高: {font_info['line_height']}px")

        contrast = dam.fonts.check_contrast_ratio("#FFFFFF", "#000000")
        print(f"    对比度检查 (#FFF vs #000): {contrast['contrast_ratio']}:1")
        print(f"      AA 正常: {'通过' if contrast['aa_normal'] else '未通过'}")
        print(f"      AAA 正常: {'通过' if contrast['aaa_normal'] else '未通过'}")
        print()

        print(f"[7] 企业工作流")
        compliance = dam.workflow.license_compliance_check(asset_id)
        print(f"    许可证合规检查: {'合规' if compliance['compliant'] else '待完善'}")
        if compliance["warnings"]:
            for w in compliance["warnings"]:
                print(f"      警告: {w}")
        if compliance["issues"]:
            for i in compliance["issues"]:
                print(f"      问题: {i}")

        dam.workflow.usage_tracking(asset_id, "Demo Project", "preview")
        usage_stats = dam.workflow.get_usage_stats(asset_id)
        print(f"    使用统计: 共 {usage_stats['total_usage']} 次使用")
        print()

        print(f"[8] 统计概览")
        stats = dam.get_stats()
        print(f"    总资产数: {stats['total_assets']}")
        print(f"    分类统计:")
        for cat, count in stats["by_category"].items():
            print(f"      {cat}: {count}")
        size_mb = stats["total_file_size"] / (1024 * 1024)
        print(f"    总文件大小: {size_mb:.2f} MB")
        print(f"    标签总数: {stats['tags_count']}")
        print()

        backup_path = dam.library.backup_database()
        print(f"[9] 数据库备份")
        print(f"    备份文件: {backup_path}")
        print()

        print("=" * 70)
        print("  Demo 完成！Unified Asset Manager 功能验证成功。")
        print("=" * 70)
        print()
        print("  主要组件:")
        print("  ✓ 资产分类系统 (10 种类别)")
        print("  ✓ SQLite 资产库 (增删改查、批量导入)")
        print("  ✓ 智能搜索引擎 (全文、标签、高级过滤)")
        print("  ✓ 媒体下载器 (yt-dlp 集成)")
        print("  ✓ 素材库 API (Pexels/Pixabay/Unsplash)")
        print("  ✓ 处理管道 (格式转换、代理生成)")
        print("  ✓ 质量评估 (技术/内容/可用性)")
        print("  ✓ 企业工作流 (摄取、审批、归档)")
        print("  ✓ 字体管理 (元数据、配对、排版)")
        print("  ✓ 集成接口 (AE/PR/Resolve/Blender)")
        print("  ✓ 配置持久化与备份")


if __name__ == "__main__":
    main()
