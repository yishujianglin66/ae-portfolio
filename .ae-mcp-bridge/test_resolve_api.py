"""Test Resolve connection."""
import sys

print("Step 1: Import DaVinciResolveScript")
try:
    import DaVinciResolveScript as bmd
    print("SUCCESS: Imported DaVinciResolveScript")
except ImportError as e:
    print(f"ERROR: Cannot import: {e}", file=sys.stderr)
    sys.exit(1)

print("Step 2: Connect to Resolve")
resolve = bmd.scriptapp("Resolve")
if not resolve:
    print("ERROR: Cannot connect to Resolve", file=sys.stderr)
    sys.exit(1)
print("SUCCESS: Connected to Resolve")

print("Step 3: Get ProjectManager")
project_manager = resolve.GetProjectManager()
print(f"SUCCESS: ProjectManager: {project_manager}")

print("Step 4: Get/Create Project")
project = project_manager.GetCurrentProject()
if not project:
    print("INFO: No current project, creating...")
    project = project_manager.CreateProject("Test_Project")
print(f"SUCCESS: Project: {project}")

print("Step 5: Get MediaPool")
media_pool = project.GetMediaPool()
print(f"SUCCESS: MediaPool: {media_pool}")

print("ALL TESTS PASSED")
