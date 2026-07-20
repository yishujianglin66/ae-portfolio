-- Vinland Saga V12 - DaVinci Resolve Color Grading (Lua)
-- Battle Cinematic Grade via CDL + Render

local INPUT_PATH = "D:\\AE-Work\\output\\VinlandSaga_Battle_V11.mp4"
local OUTPUT_DIR = "D:\\AE-Work\\output"
local OUTPUT_NAME = "VinlandSaga_Battle_V12"
local WIDTH = 1080
local HEIGHT = 1920
local FPS = 30

print("========================================")
print("Vinland Saga V12 - DaVinci Resolve Grade")
print("========================================")
print("Input: " .. INPUT_PATH)
print("Output: " .. OUTPUT_DIR .. "\\" .. OUTPUT_NAME .. ".mp4")
print("")

-- 1. Connect to Resolve
local resolve = Resolve()
if not resolve then
    print("ERROR: Cannot connect to Resolve")
    os.exit(1)
end
print("[1/7] Connected to Resolve " .. resolve:GetVersionString())

local projectManager = resolve:GetProjectManager()

-- Use a unique project name to avoid conflicts
local projectName = "V12_VinlandSaga_Battle_" .. os.time()
local project = projectManager:CreateProject(projectName)
if not project then
    print("ERROR: Failed to create project: " .. projectName)
    os.exit(1)
end
print("[2/7] Project: " .. project:GetName())

-- Set project settings
project:SetSetting("timelineFrameRate", tostring(FPS))
project:SetSetting("timelineResolutionWidth", tostring(WIDTH))
project:SetSetting("timelineResolutionHeight", tostring(HEIGHT))
print("  Timeline settings: " .. WIDTH .. "x" .. HEIGHT .. " @ " .. FPS .. "fps")

-- 2. Import media
local mediaPool = project:GetMediaPool()

local mediaItems = mediaPool:ImportMedia({INPUT_PATH})
if not mediaItems or #mediaItems == 0 then
    -- Try using MediaStorage
    local mediaStorage = resolve:GetMediaStorage()
    mediaItems = mediaStorage:AddItemsToMediaPool(INPUT_PATH)
end
if not mediaItems or #mediaItems == 0 then
    print("ERROR: Failed to import media")
    os.exit(1)
end
local mediaItem = mediaItems[1]
print("[3/7] Media imported: " .. mediaItem:GetName())

-- 3. Create timeline
local timelineName = "V12_Grade"
local timeline = mediaPool:CreateEmptyTimeline(timelineName)
if not timeline then
    print("ERROR: Failed to create timeline")
    os.exit(1)
end

-- Append clip to timeline
mediaPool:AppendToTimeline(mediaItem)
timeline = project:GetCurrentTimeline()
print("[4/7] Timeline created: " .. timeline:GetName())

-- Switch to color page
resolve:OpenPage("color")

-- 4. Get clip and apply grade
local videoTrackItems = timeline:GetItemListInTrack("video", 1)
if not videoTrackItems or #videoTrackItems == 0 then
    print("ERROR: No video items in timeline")
    os.exit(1)
end

local clip = videoTrackItems[1]

-- Apply CDL grade (ASC CDL: Slope, Offset, Power, Saturation)
-- Battle cinematic: slightly desaturated, cool shadows, contrasty
local cdlResult = clip:SetCDL({
    ["NodeIndex"] = "1",
    ["Slope"] = "1.1 1.05 0.95",
    ["Offset"] = "0.02 0.01 0.0",
    ["Power"] = "0.95 0.98 1.05",
    ["Saturation"] = "0.85"
})
print("[5/7] CDL grade applied: " .. tostring(cdlResult))
print("  Slope:    1.10 / 1.05 / 0.95 (R/G/B)")
print("  Offset:   0.02 / 0.01 / 0.00")
print("  Power:    0.95 / 0.98 / 1.05")
print("  Saturation: 0.85")

-- 5. Render setup
print("[6/7] Setting up render...")
resolve:OpenPage("deliver")

-- Set render settings
project:SetRenderSettings({
    ["TargetDir"] = OUTPUT_DIR,
    ["CustomName"] = OUTPUT_NAME,
    ["FormatWidth"] = WIDTH,
    ["FormatHeight"] = HEIGHT,
    ["VideoQuality"] = 80,
    ["SelectAllFrames"] = 1,
})

-- Set render format and codec
local codecResult = project:SetCurrentRenderFormatAndCodec("mp4", "H264")
print("  Format/Codec set: " .. tostring(codecResult))

-- Add render job
local jobId = project:AddRenderJob()
print("[7/7] Render job added: " .. jobId)

-- 6. Start rendering
print("")
print("Starting render...")
local renderResult = project:StartRendering(jobId)
print("Render started: " .. tostring(renderResult))

-- Wait for render to complete
local maxWait = 3600
local waited = 0
while project:IsRenderingInProgress() and waited < maxWait do
    -- Sleep using os.execute ping trick
    os.execute("ping -n 2 127.0.0.1 > NUL")
    waited = waited + 1
    if waited % 10 == 0 then
        local status = project:GetRenderJobStatus(jobId)
        if status then
            local pct = status["CompletionPercentage"] or 0
            print("  Rendering: " .. pct .. "% (" .. waited .. "s)")
        end
    end
end

-- 7. Final status
local finalStatus = project:GetRenderJobStatus(jobId)
print("")
print("========================================")
if finalStatus and finalStatus["JobStatus"] == "Complete" then
    print("RENDER_SUCCESS")
    print("Output: " .. OUTPUT_DIR .. "\\" .. OUTPUT_NAME .. ".mp4")
    print("Time taken: " .. waited .. "s")
else
    print("RENDER_FAILED")
    if finalStatus then
        print("Status: " .. tostring(finalStatus["JobStatus"]))
        for k, v in pairs(finalStatus) do
            print("  " .. k .. ": " .. tostring(v))
        end
    end
end
print("========================================")
