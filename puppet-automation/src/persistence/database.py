"""Database module for persisting pipeline results.

Provides async SQLite persistence for:
- Jobs and their lifecycle state
- Phase results (preprocess, keying, stylize, render)
- Phase1 perception outputs: video metadata, scenes, faces, poses, audio

The database path is configurable via ``settings.database_url`` (default:
``data/puppet.db``).  All operations are async via ``aiosqlite``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.config import settings

# ============================================================
# Schema version and DDL
# ============================================================

SCHEMA_VERSION = 1

DDL = """
-- Jobs table: one row per pipeline job
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    input_video TEXT NOT NULL,
    style TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0.0,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    config_json TEXT  -- PipelineJob serialized as JSON
);

-- Phase results: one row per phase per job
CREATE TABLE IF NOT EXISTS phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    output_path TEXT,
    error TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    UNIQUE(job_id, phase)
);

-- Video metadata from phase1
CREATE TABLE IF NOT EXISTS video_metadata (
    job_id TEXT PRIMARY KEY,
    width INTEGER,
    height INTEGER,
    fps REAL,
    duration REAL,
    bitrate INTEGER,
    codec TEXT,
    has_audio BOOLEAN,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Detected scenes from phase1
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    start_time REAL,
    end_time REAL,
    scene_type TEXT,
    confidence REAL,
    thumbnail_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Detected faces from phase1
CREATE TABLE IF NOT EXISTS faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    frame_number INTEGER,
    face_id INTEGER,
    bbox_x INTEGER,
    bbox_y INTEGER,
    bbox_w INTEGER,
    bbox_h INTEGER,
    confidence REAL,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Detected poses from phase1
CREATE TABLE IF NOT EXISTS poses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    frame_number INTEGER,
    keypoints_json TEXT,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Audio analysis from phase1
CREATE TABLE IF NOT EXISTS audio_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    has_audio BOOLEAN,
    duration REAL,
    sample_rate INTEGER,
    channels INTEGER,
    bpm REAL,
    beat_times_json TEXT,
    speech_segments_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Schema version marker
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_phases_job_id ON phases(job_id);
CREATE INDEX IF NOT EXISTS idx_scenes_job_id ON scenes(job_id);
CREATE INDEX IF NOT EXISTS idx_faces_job_id ON faces(job_id);
CREATE INDEX IF NOT EXISTS idx_poses_job_id ON poses(job_id);
CREATE INDEX IF NOT EXISTS idx_audio_job_id ON audio_analysis(job_id);
"""


# ============================================================
# Database manager
# ============================================================

class Database:
    """Async SQLite database wrapper with connection pooling.

    Usage::

        db = Database()
        await db.connect()
        job = await db.jobs.get("job-123")
        await db.close()
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path or getattr(settings, "database_url", "data/puppet.db"))
        self._conn: Any = None
        self._jobs: JobRepository | None = None
        self._phases: PhaseRepository | None = None
        self._perception: PerceptionRepository | None = None

    async def connect(self) -> None:
        """Open the database connection and run migrations."""
        import aiosqlite

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Enable foreign keys
        await self._conn.execute("PRAGMA foreign_keys = ON")

        # Run schema migrations
        await self._migrate()

        # Initialize repositories
        self._jobs = JobRepository(self._conn)
        self._phases = PhaseRepository(self._conn)
        self._perception = PerceptionRepository(self._conn)

        logger.info(f"Database connected: {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    async def _migrate(self) -> None:
        """Run schema migrations."""
        await self._conn.executescript(DDL)

        # Check schema version
        cursor = await self._conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        current_version = row["version"] if row else 0

        if current_version < SCHEMA_VERSION:
            # Future migrations would go here
            await self._conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            await self._conn.commit()
            logger.info(f"Database migrated to version {SCHEMA_VERSION}")

    @property
    def jobs(self) -> JobRepository:
        if self._jobs is None:
            raise RuntimeError("Database not connected")
        return self._jobs

    @property
    def phases(self) -> PhaseRepository:
        if self._phases is None:
            raise RuntimeError("Database not connected")
        return self._phases

    @property
    def perception(self) -> PerceptionRepository:
        if self._perception is None:
            raise RuntimeError("Database not connected")
        return self._perception

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


# ============================================================
# Job Repository
# ============================================================

class JobRepository:
    """CRUD for jobs table."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def create(self, job_id: str, input_video: str, **kwargs: Any) -> None:
        """Insert a new job. ``kwargs`` map to jobs columns."""
        import json
        from datetime import datetime

        columns = ["job_id", "input_video"]
        values = [job_id, input_video]
        placeholders = ["?", "?"]

        for k, v in kwargs.items():
            if k == "config_json" and not isinstance(v, str):
                v = json.dumps(v)
            columns.append(k)
            values.append(v)
            placeholders.append("?")

        sql = f"INSERT INTO jobs ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        await self._conn.execute(sql, values)
        await self._conn.commit()

    async def get(self, job_id: str) -> dict[str, Any] | None:
        """Return job row as dict, or None."""
        cursor = await self._conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List jobs, optionally filtered by status."""
        if status:
            sql = "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = [status, limit, offset]
        else:
            sql = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = [limit, offset]

        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update(self, job_id: str, **kwargs: Any) -> bool:
        """Update job columns. Returns True if row was updated."""
        import json

        if not kwargs:
            return False

        # Always update updated_at
        kwargs["updated_at"] = "CURRENT_TIMESTAMP"

        columns = []
        values = []
        for k, v in kwargs.items():
            if k == "config_json" and not isinstance(v, str):
                v = json.dumps(v)
            columns.append(f"{k} = ?")
            values.append(v)

        values.append(job_id)
        sql = f"UPDATE jobs SET {', '.join(columns)} WHERE job_id = ?"
        cursor = await self._conn.execute(sql, values)
        await self._conn.commit()
        return cursor.rowcount > 0

    async def delete(self, job_id: str) -> bool:
        """Delete a job (cascade deletes phases/perception data)."""
        cursor = await self._conn.execute(
            "DELETE FROM jobs WHERE job_id = ?", (job_id,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0


# ============================================================
# Phase Repository
# ============================================================

class PhaseRepository:
    """CRUD for phases table."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def upsert(self, job_id: str, phase: str, **kwargs: Any) -> None:
        """Insert or update a phase result."""
        import json

        # Serialize metadata_json if needed
        if "metadata_json" in kwargs and not isinstance(kwargs["metadata_json"], str):
            kwargs["metadata_json"] = json.dumps(kwargs["metadata_json"])

        # Build upsert SQL (INSERT ... ON CONFLICT DO UPDATE)
        columns = ["job_id", "phase"] + list(kwargs.keys())
        values = [job_id, phase] + list(kwargs.values())
        placeholders = ["?", "?"] + ["?"] * len(kwargs)

        update_cols = [f"{k}=excluded.{k}" for k in kwargs.keys()]
        update_clause = ", ".join(update_cols) if update_cols else "status=excluded.status"

        sql = f"""
            INSERT INTO phases ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT(job_id, phase) DO UPDATE SET {update_clause}
        """
        await self._conn.execute(sql, values)
        await self._conn.commit()

    async def get(self, job_id: str, phase: str) -> dict[str, Any] | None:
        cursor = await self._conn.execute(
            "SELECT * FROM phases WHERE job_id = ? AND phase = ?",
            (job_id, phase),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT * FROM phases WHERE job_id = ? ORDER BY id",
            (job_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ============================================================
# Perception Repository (phase1 outputs)
# ============================================================

class PerceptionRepository:
    """CRUD for perception tables: video_metadata, scenes, faces, poses, audio_analysis."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    # Video metadata
    async def save_video_metadata(self, job_id: str, meta: dict[str, Any]) -> None:
        sql = """
            INSERT OR REPLACE INTO video_metadata
            (job_id, width, height, fps, duration, bitrate, codec, has_audio, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self._conn.execute(sql, (
            job_id,
            meta.get("width"),
            meta.get("height"),
            meta.get("fps"),
            meta.get("duration"),
            meta.get("bitrate"),
            meta.get("codec"),
            meta.get("has_audio"),
            meta.get("file_size"),
        ))
        await self._conn.commit()

    async def get_video_metadata(self, job_id: str) -> dict[str, Any] | None:
        cursor = await self._conn.execute(
            "SELECT * FROM video_metadata WHERE job_id = ?", (job_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # Scenes
    async def save_scenes(self, job_id: str, scenes: list[dict[str, Any]]) -> None:
        await self._conn.execute("DELETE FROM scenes WHERE job_id = ?", (job_id,))
        for s in scenes:
            await self._conn.execute(
                "INSERT INTO scenes (job_id, start_time, end_time, scene_type, confidence, thumbnail_path) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, s.get("start_time"), s.get("end_time"), s.get("scene_type"), s.get("confidence"), s.get("thumbnail_path")),
            )
        await self._conn.commit()

    async def get_scenes(self, job_id: str) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT * FROM scenes WHERE job_id = ? ORDER BY start_time", (job_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # Faces
    async def save_faces(self, job_id: str, faces: list[dict[str, Any]]) -> None:
        import json
        await self._conn.execute("DELETE FROM faces WHERE job_id = ?", (job_id,))
        for f in faces:
            embedding = f.get("embedding")
            if embedding and not isinstance(embedding, bytes):
                embedding = json.dumps(embedding).encode()
            await self._conn.execute(
                "INSERT INTO faces (job_id, frame_number, face_id, bbox_x, bbox_y, bbox_w, bbox_h, confidence, embedding) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, f.get("frame_number"), f.get("face_id"), f.get("bbox_x"), f.get("bbox_y"), f.get("bbox_w"), f.get("bbox_h"), f.get("confidence"), embedding),
            )
        await self._conn.commit()

    async def get_faces(self, job_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT id, job_id, frame_number, face_id, bbox_x, bbox_y, bbox_w, bbox_h, confidence FROM faces WHERE job_id = ? ORDER BY frame_number LIMIT ?",
            (job_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # Poses
    async def save_poses(self, job_id: str, poses: list[dict[str, Any]]) -> None:
        import json
        await self._conn.execute("DELETE FROM poses WHERE job_id = ?", (job_id,))
        for p in poses:
            keypoints = p.get("keypoints")
            keypoints_json = json.dumps(keypoints) if keypoints else None
            await self._conn.execute(
                "INSERT INTO poses (job_id, frame_number, keypoints_json, confidence) VALUES (?, ?, ?, ?)",
                (job_id, p.get("frame_number"), keypoints_json, p.get("confidence")),
            )
        await self._conn.commit()

    async def get_poses(self, job_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        cursor = await self._conn.execute(
            "SELECT id, job_id, frame_number, keypoints_json, confidence FROM poses WHERE job_id = ? ORDER BY frame_number LIMIT ?",
            (job_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # Audio analysis
    async def save_audio_analysis(self, job_id: str, audio: dict[str, Any]) -> None:
        import json
        beat_times = audio.get("beat_times")
        beat_json = json.dumps(beat_times) if beat_times else None
        speech_segments = audio.get("speech_segments")
        speech_json = json.dumps(speech_segments) if speech_segments else None

        await self._conn.execute(
            """INSERT OR REPLACE INTO audio_analysis
               (job_id, has_audio, duration, sample_rate, channels, bpm, beat_times_json, speech_segments_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, audio.get("has_audio"), audio.get("duration"), audio.get("sample_rate"), audio.get("channels"), audio.get("bpm"), beat_json, speech_json),
        )
        await self._conn.commit()

    async def get_audio_analysis(self, job_id: str) -> dict[str, Any] | None:
        cursor = await self._conn.execute(
            "SELECT * FROM audio_analysis WHERE job_id = ?", (job_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ============================================================
# Convenience: global instance for FastAPI lifespan
# ============================================================

db = Database()