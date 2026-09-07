#!/usr/bin/env python3
"""Read-only check that the external LFS object backup mirrors .git/lfs/objects.

A git bundle carries no LFS payloads, so the backup store is the only copy of
the object bytes outside .git. This proves it is complete and uncorrupted.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AE_KV_REPO", Path(__file__).resolve().parents[1]))
SRC = REPO / ".git" / "lfs" / "objects"
DST = Path(os.environ.get("AE_KV_LFS_BACKUP", REPO.parent / "ae-kv-lfs-backup-20260829" / "objects"))

OID_RE = re.compile(r"^[0-9a-f]{64}$")


def oid_from(rel: str) -> str | None:
    """Resolve a store-relative path like ab/cd/<64hex> to its OID."""
    parts = rel.split("/")
    if len(parts) != 3:
        return None
    a, b, name = parts
    if len(a) != 2 or len(b) != 2 or not OID_RE.fullmatch(name):
        return None
    if name.startswith(a + b):
        return name
    return None


def enumerate_store(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        oid = oid_from(path.relative_to(root).as_posix())
        if oid is None:
            print(f"  MALFORMED  {path}")
            continue
        found[oid] = path
    return found


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pointer_oids() -> list[str]:
    """OIDs of every LFS pointer in the checked-out tree."""
    out = subprocess.run(["git", "-C", str(REPO), "lfs", "ls-files", "-l"],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"git lfs ls-files failed: {out.stderr.strip()}")
    oids = []
    for line in out.stdout.splitlines():
        fields = line.split()
        if fields and OID_RE.fullmatch(fields[0]):
            oids.append(fields[0])
    return oids


def main() -> int:
    if not SRC.is_dir():
        print(f"FAIL: repo LFS store missing: {SRC}")
        return 1
    if not DST.is_dir():
        print(f"FAIL: backup LFS store missing: {DST}")
        return 1

    src, dst = enumerate_store(SRC), enumerate_store(DST)
    print(f"repo store:   {len(src)} objects  ({SRC})")
    print(f"backup store: {len(dst)} objects  ({DST})")

    missing = sorted(set(src) - set(dst))
    extra = sorted(set(dst) - set(src))
    for oid in missing:
        print(f"  MISSING  {oid} (in repo, absent from backup)")
    for oid in extra:
        print(f"  EXTRA    {oid} (in backup, absent from repo)")

    size_bad = hash_bad = 0
    total = 0
    for oid in sorted(set(src) & set(dst)):
        src_path, dst_path = src[oid], dst[oid]
        if src_path.stat().st_size != dst_path.stat().st_size:
            print(f"  SIZE MISMATCH {oid} ({src_path.stat().st_size} vs {dst_path.stat().st_size})")
            size_bad += 1
            continue
        if sha256_of(src_path) != oid or sha256_of(dst_path) != oid:
            print(f"  SHA256 BAD    {oid}")
            hash_bad += 1
            continue
        total += src_path.stat().st_size

    oids = pointer_oids()
    covered = [oid for oid in oids if oid in src]
    for oid in oids:
        if oid not in src:
            print(f"  POINTER NOT CHECKED OUT {oid}")

    print(f"mirrored: {len(set(src) & set(dst))}, bytes verified: {total}")
    print(f"coverage: {len(covered)}/{len(oids)} LFS pointers present in repo store")

    failed = bool(missing or extra or size_bad or hash_bad or len(covered) != len(oids))
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
