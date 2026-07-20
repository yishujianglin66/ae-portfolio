-- Test Resolve Lua API
print("=== Test Resolve Connection ===")

local resolve = bmd.scriptapp("Resolve")
if not resolve then
    print("ERROR: Cannot connect to Resolve")
    os.exit(1)
end

print("Connected to Resolve: " .. tostring(resolve))
print("Version: " .. resolve:GetVersionString())

local projectManager = resolve:GetProjectManager()
print("ProjectManager: " .. tostring(projectManager))

local project = projectManager:GetCurrentProject()
if not project then
    print("No current project, creating test project...")
    project = projectManager:CreateProject("LuaTest_Project")
end

print("Project: " .. tostring(project))
if project then
    print("Project name: " .. project:GetName())
end

print("=== ALL TESTS PASSED ===")
