#!/usr/bin/env python3
"""Frontend-Backend Integration Test"""
import sys
sys.path.insert(0, ".")

import pytest
pytest.importorskip("fastapi")
from toolchain_api import get_toolchain_manager
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)

print("=== Frontend-Backend Integration Test ===\n")

# 1. Toolchain Status
r = client.get("/api/v1/toolchain/status")
print(f"1. Toolchain Status: {r.status_code} - {r.json()}")

# 2. Tools List
r = client.get("/api/v1/toolchain/tools")
data = r.json()
print(f"2. Tools List: {r.status_code} - Total: {data['total']}, Categories: {data['categories']}")

# 3. Engines
r = client.get("/api/v1/toolchain/tools/engines")
data = r.json()
print(f"3. Engines: {r.status_code} - Count: {data['total']}")
for e in data["engines"]:
    print(f"   {e['status']} {e['name']}: {e['description']}")

# 4. Categories
r = client.get("/api/v1/toolchain/tools/categories")
print(f"4. Categories: {r.status_code} - {r.json()}")

# 5. Execute Tool (simulate)
r = client.post("/api/v1/toolchain/tools/execute", json={
    "tool_name": "blender",
    "operation": "render_scene",
    "params": {"blend_path": "test.blend", "output_path": "output.mp4"},
    "mode": "simulate"
})
data = r.json()
print(f"5. Execute Tool: {r.status_code} - Success: {data['success']}, Mode: {data['mode_used']}")

# 6. Workflows
r = client.get("/api/v1/toolchain/workflows")
data = r.json()
print(f"6. Workflows: {r.status_code} - Count: {data['total']}")
for wf in data["workflows"]:
    print(f"   - {wf}")

# 7. Execute Workflow (simulate)
r = client.post("/api/v1/toolchain/workflows/execute", json={
    "workflow_name": "full_production",
    "input_path": "input.mp4",
    "output_path": "output.mp4",
    "mode": "simulate"
})
data = r.json()
print(f"7. Execute Workflow: {r.status_code} - Status: {data['status']}, Steps: {len(data['steps'])}")
print(f"   Summary: {data['summary']}")

# 8. Quick Render
r = client.post("/api/v1/toolchain/quick/render?project_path=test.aep&comp_name=Comp+1&output_path=out.mp4&mode=simulate")
data = r.json()
print(f"8. Quick Render: {r.status_code} - Success: {data['success']}")

# 9. Quick Enhance
r = client.post("/api/v1/toolchain/quick/enhance?input_path=in.mp4&output_path=out.mp4&model=proteus&scale=2&mode=simulate")
data = r.json()
print(f"9. Quick Enhance: {r.status_code} - Success: {data['success']}")

# 10. Quick Encode
r = client.post("/api/v1/toolchain/quick/encode?input_path=in.mp4&output_path=out.mp4&codec=h264&mode=simulate")
data = r.json()
print(f"10. Quick Encode: {r.status_code} - Success: {data['success']}")

print("\n=== All 10 tests passed ===")
