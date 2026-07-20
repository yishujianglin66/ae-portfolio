-- Debug timeline creation
local resolve = Resolve()
print("Resolve: " .. tostring(resolve))
print("Version: " .. resolve:GetVersionString())

local pm = resolve:GetProjectManager()
print("ProjectManager: " .. tostring(pm))

-- List existing projects
local projects = pm:GetProjectListInCurrentFolder()
print("Projects in current folder:")
for i, name in pairs(projects) do
    print("  " .. i .. ": " .. name)
end

-- Try loading or creating
local projectName = "V12_Debug_Test"
local project = pm:LoadProject(projectName)
if not project then
    print("Project not found, creating...")
    project = pm:CreateProject(projectName)
end
print("Project: " .. tostring(project))
if project then
    print("Project name: " .. project:GetName())
    
    -- Set timeline settings
    project:SetSetting("timelineFrameRate", "30")
    project:SetSetting("timelineResolutionWidth", "1920")
    project:SetSetting("timelineResolutionHeight", "1080")
    print("Timeline settings set")
    
    local mp = project:GetMediaPool()
    print("MediaPool: " .. tostring(mp))
    
    -- Check if there are already timelines
    local tlCount = project:GetTimelineCount()
    print("Timeline count: " .. tlCount)
    
    -- Try creating empty timeline
    local tl = mp:CreateEmptyTimeline("Test_Timeline")
    print("CreateEmptyTimeline result: " .. tostring(tl))
    
    if not tl then
        -- Try alternative: create timeline from a clip?
        print("Trying with media first...")
        -- Check root folder
        local root = mp:GetRootFolder()
        print("Root folder: " .. tostring(root))
        local clips = root:GetClipList()
        print("Clips in root: " .. #clips)
    else
        print("Timeline name: " .. tl:GetName())
    end
end

print("DEBUG DONE")
