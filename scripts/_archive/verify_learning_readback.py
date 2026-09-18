#!/usr/bin/env python3
"""验证pipeline_runs回读"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from pathlib import Path

runs_dir = Path('data/pipeline_runs')
print(f"runs_dir exists: {runs_dir.exists()}")
if runs_dir.exists():
    dirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]
    print(f"Run dirs: {len(dirs)}")
    for d in dirs:
        result_file = d / "pipeline_result.json"
        print(f"  {d.name}: has_result={result_file.exists()}")
        if result_file.exists():
            data = json.loads(result_file.read_text(encoding='utf-8'))
            print(f"    status={data.get('status')}, stages={list(data.get('stages',{}).keys())}")

# 测试harvester
print("\n--- Testing harvester ---")
from core.experience_harvester import StructuredDataParser

p = StructuredDataParser('data')
runs = p.parse_pipeline_runs()
print(f"Harvester found {len(runs)} pipeline runs")
for r in runs:
    print(f"  {r.record_id}: success={r.overall_success}, stages={len(r.stages)}")
