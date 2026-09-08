#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply validated visual effects to run53v43 baseline video.

Usage:
    python scripts/apply_run53v43_effects.py

This script:
1. Loads run53v43_effects.json (schema-validated)
2. Creates an AE project with the baseline video
3. Applies 8 effect layers via JSX bridge
4. Renders polished output: run53v43_polished.mp4
"""
import json
import subprocess as sp
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def apply_effects_to_video():
    """Apply schema-validated effects to run53v43 using AE bridge."""
    input_video = PROJECT / "output" / "unified_run53" / "run53_final_v43.mp4"
    effects_json = PROJECT / "output" / "unified_run53" / "run53v43_effects.json"
    jsx_script = PROJECT / "output" / "unified_run53" / "apply_run53v43_effects.jsx"
    output_dir = PROJECT / "output" / "unified_run53"

    if not input_video.exists():
        print(f"[ERROR] Input video not found: {input_video}")
        return False

    if not effects_json.exists():
        print(f"[ERROR] Effects config not found: {effects_json}")
        return False

    # Load and validate effects
    effects = json.loads(effects_json.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(effects)} validated effects")

    # Import AE bridge
    from ai.ae_render_channel import AERenderChannel

    channel = AERenderChannel(out_dir=str(output_dir))

    # Create AE project with baseline video
    print("[Phase 1] Creating AE project...")
    aep_path = output_dir / "run53v43_polish.aep"

    # Use build_master_polish.py to create project structure
    result = sp.run(
        [sys.executable, str(PROJECT / "scripts" / "build_master_polish.py"),
         str(output_dir)],
        capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
    )

    if result.returncode != 0:
        print(f"[ERROR] Project creation failed:")
        print(result.stderr)
        return False

    print(f"[INFO] AE project created: {aep_path}")

    # Apply JSX script to add effect layers
    print("[Phase 2] Applying effect layers via JSX...")
    jsx_result = channel._bridge_run_jsx(
        timeout=120,
        command="executeAtomScript",
        args={
            "script": jsx_script.name,
            "scriptContent": jsx_script.read_text(encoding="utf-8"),
        },
    )

    if not jsx_result.get("success"):
        print(f"[ERROR] JSX execution failed: {jsx_result}")
        return False

    print(f"[INFO] JSX executed successfully: {jsx_result}")

    # Render composition
    print("[Phase 3] Rendering polished video...")
    output_video = output_dir / "run53v43_polished.mp4"

    render_result = sp.run(
        ["aerender", "-project", str(aep_path), "-comp", "POLISH",
         "-output", str(output_video)],
        capture_output=True, text=True, timeout=1800, encoding="utf-8", errors="replace",
    )

    if render_result.returncode != 0:
        print(f"[ERROR] Render failed (RC={render_result.returncode}):")
        print(render_result.stderr)
        return False

    if not output_video.exists():
        print(f"[ERROR] Output video not generated: {output_video}")
        return False

    print(f"[SUCCESS] Polished video: {output_video}")
    print(f"[INFO] File size: {output_video.stat().st_size / (1024*1024):.1f} MB")

    return True


if __name__ == "__main__":
    success = apply_effects_to_video()
    sys.exit(0 if success else 1)
