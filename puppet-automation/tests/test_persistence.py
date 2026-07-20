"""Tests for the persistence layer (SQLite).

These tests use an in-memory SQLite database for speed and isolation.
They verify:
- Schema creation and migrations
- JobRepository CRUD operations
- PhaseRepository upsert/list
- PerceptionRepository save/get for video_metadata, scenes, faces, poses, audio
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
async def db():
    """Create an in-memory SQLite database for each test."""
    from src.persistence.database import Database
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


# ============================================================
# Schema
# ============================================================

class TestSchema:
    @pytest.mark.asyncio
    async def test_tables_created(self, db):
        """All expected tables should be created."""
        cursor = await db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        tables = [r[0] for r in rows if r[0] != "sqlite_sequence"]  # Filter SQLite internal table
        expected = [
            "audio_analysis", "faces", "jobs", "phases", "poses",
            "schema_version", "scenes", "video_metadata",
        ]
        assert set(tables) == set(expected)

    @pytest.mark.asyncio
    async def test_schema_version_recorded(self, db):
        """Schema version should be recorded."""
        from src.persistence.database import SCHEMA_VERSION
        cursor = await db._conn.execute("SELECT version FROM schema_version")
        row = await cursor.fetchone()
        assert row[0] == SCHEMA_VERSION


# ============================================================
# JobRepository
# ============================================================

class TestJobRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db):
        await db.jobs.create("job-1", "/tmp/video.mp4", style="wooden", status="pending")
        job = await db.jobs.get("job-1")
        assert job is not None
        assert job["job_id"] == "job-1"
        assert job["input_video"] == "/tmp/video.mp4"
        assert job["style"] == "wooden"
        assert job["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, db):
        job = await db.jobs.get("no-such-job")
        assert job is None

    @pytest.mark.asyncio
    async def test_list_all(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        await db.jobs.create("j2", "/tmp/b.mp4")
        jobs = await db.jobs.list()
        assert len(jobs) == 2
        ids = {j["job_id"] for j in jobs}
        assert ids == {"j1", "j2"}

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4", status="pending")
        await db.jobs.create("j2", "/tmp/b.mp4", status="success")
        jobs = await db.jobs.list(status="pending")
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "j1"

    @pytest.mark.asyncio
    async def test_update(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4", status="pending")
        updated = await db.jobs.update("j1", status="running", progress=50.0)
        assert updated is True
        job = await db.jobs.get("j1")
        assert job["status"] == "running"
        assert job["progress"] == 50.0

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_false(self, db):
        updated = await db.jobs.update("no-job", status="running")
        assert updated is False

    @pytest.mark.asyncio
    async def test_delete_cascades(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        await db.phases.upsert("j1", "phase1", status="success")
        # Verify phase exists
        phases = await db.phases.list_for_job("j1")
        assert len(phases) == 1

        # Delete job
        deleted = await db.jobs.delete("j1")
        assert deleted is True

        # Phase should be cascade-deleted
        phases = await db.phases.list_for_job("j1")
        assert len(phases) == 0

    @pytest.mark.asyncio
    async def test_config_json_stored_as_string(self, db):
        config = {"style": "wooden", "phases": ["phase1", "phase2"]}
        await db.jobs.create("j1", "/tmp/a.mp4", config_json=config)
        job = await db.jobs.get("j1")
        # Should be stored as JSON string
        assert isinstance(job["config_json"], str)
        loaded = json.loads(job["config_json"])
        assert loaded["style"] == "wooden"


# ============================================================
# PhaseRepository
# ============================================================

class TestPhaseRepository:
    @pytest.mark.asyncio
    async def test_upsert_and_get(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        await db.phases.upsert("j1", "phase1", status="success", output_path="/tmp/out.mp4")
        phase = await db.phases.get("j1", "phase1")
        assert phase is not None
        assert phase["phase"] == "phase1"
        assert phase["status"] == "success"
        assert phase["output_path"] == "/tmp/out.mp4"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        await db.phases.upsert("j1", "phase1", status="running")
        await db.phases.upsert("j1", "phase1", status="success", output_path="/tmp/out.mp4")
        phase = await db.phases.get("j1", "phase1")
        assert phase["status"] == "success"
        assert phase["output_path"] == "/tmp/out.mp4"

    @pytest.mark.asyncio
    async def test_list_for_job(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        await db.phases.upsert("j1", "phase1", status="success")
        await db.phases.upsert("j1", "phase2", status="running")
        phases = await db.phases.list_for_job("j1")
        assert len(phases) == 2
        phase_names = {p["phase"] for p in phases}
        assert phase_names == {"phase1", "phase2"}

    @pytest.mark.asyncio
    async def test_metadata_json_stored_as_string(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        meta = {"duration": 60, "scenes": 3}
        await db.phases.upsert("j1", "phase1", status="success", metadata_json=meta)
        phase = await db.phases.get("j1", "phase1")
        assert isinstance(phase["metadata_json"], str)
        loaded = json.loads(phase["metadata_json"])
        assert loaded["scenes"] == 3


# ============================================================
# PerceptionRepository
# ============================================================

class TestPerceptionRepository:
    @pytest.mark.asyncio
    async def test_video_metadata(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        meta = {"width": 1920, "height": 1080, "fps": 30.0, "duration": 120, "codec": "h264"}
        await db.perception.save_video_metadata("j1", meta)
        loaded = await db.perception.get_video_metadata("j1")
        assert loaded["width"] == 1920
        assert loaded["fps"] == 30.0

    @pytest.mark.asyncio
    async def test_scenes(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        scenes = [
            {"start_time": 0.0, "end_time": 10.0, "scene_type": "intro"},
            {"start_time": 10.0, "end_time": 30.0, "scene_type": "main"},
        ]
        await db.perception.save_scenes("j1", scenes)
        loaded = await db.perception.get_scenes("j1")
        assert len(loaded) == 2
        assert loaded[0]["scene_type"] == "intro"
        assert loaded[1]["start_time"] == 10.0

    @pytest.mark.asyncio
    async def test_faces(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        faces = [
            {"frame_number": 0, "face_id": 0, "bbox_x": 100, "bbox_y": 200, "bbox_w": 50, "bbox_h": 60, "confidence": 0.95},
            {"frame_number": 0, "face_id": 1, "bbox_x": 300, "bbox_y": 200, "bbox_w": 50, "bbox_h": 60, "confidence": 0.90},
        ]
        await db.perception.save_faces("j1", faces)
        loaded = await db.perception.get_faces("j1")
        assert len(loaded) == 2
        assert loaded[0]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_poses(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        poses = [
            {"frame_number": 0, "keypoints": [[0, 0], [100, 200]], "confidence": 0.88},
            {"frame_number": 1, "keypoints": [[10, 10], [110, 210]], "confidence": 0.85},
        ]
        await db.perception.save_poses("j1", poses)
        loaded = await db.perception.get_poses("j1")
        assert len(loaded) == 2
        # keypoints_json should be a string
        kp = json.loads(loaded[0]["keypoints_json"])
        assert kp == [[0, 0], [100, 200]]

    @pytest.mark.asyncio
    async def test_audio_analysis(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        audio = {
            "has_audio": True,
            "duration": 120,
            "sample_rate": 44100,
            "channels": 2,
            "bpm": 120.0,
            "beat_times": [0.5, 1.0, 1.5],
            "speech_segments": [[0, 10], [20, 30]],
        }
        await db.perception.save_audio_analysis("j1", audio)
        loaded = await db.perception.get_audio_analysis("j1")
        assert loaded["bpm"] == 120.0
        beats = json.loads(loaded["beat_times_json"])
        assert beats == [0.5, 1.0, 1.5]

    @pytest.mark.asyncio
    async def test_perception_data_deleted_on_job_delete(self, db):
        await db.jobs.create("j1", "/tmp/a.mp4")
        await db.perception.save_video_metadata("j1", {"width": 1920})
        await db.perception.save_scenes("j1", [{"start_time": 0, "end_time": 10}])
        # Delete job
        await db.jobs.delete("j1")
        # All perception data should be cascade-deleted
        assert await db.perception.get_video_metadata("j1") is None
        assert await db.perception.get_scenes("j1") == []


# ============================================================
# Database lifecycle
# ============================================================

class TestDatabaseLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager(self):
        from src.persistence.database import Database
        async with Database(":memory:") as db:
            await db.jobs.create("j1", "/tmp/a.mp4")
            job = await db.jobs.get("j1")
            assert job["job_id"] == "j1"
        # Connection should be closed after context exit
        assert db._conn is None

    @pytest.mark.asyncio
    async def test_file_db_created(self, tmp_path):
        from src.persistence.database import Database
        db_path = tmp_path / "test.db"
        async with Database(str(db_path)) as db:
            await db.jobs.create("j1", "/tmp/a.mp4")
        # File should exist on disk
        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_connect_creates_parent_dir(self, tmp_path):
        from src.persistence.database import Database
        db_path = tmp_path / "subdir" / "test.db"
        async with Database(str(db_path)) as db:
            await db.jobs.create("j1", "/tmp/a.mp4")
        assert db_path.exists()
        assert db_path.parent.exists()