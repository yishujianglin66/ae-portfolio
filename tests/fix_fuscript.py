"""Apply v3.3 improvements to davinci_fuscript.py"""
import ast

p = r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\integrations\davinci_fuscript.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 1. Add projectExisted tracking
old_create = 'local project = pm:CreateProject("{project_name}")\nif not project then project = pm:LoadProject("{project_name}") end'
new_create = '''local project = pm:CreateProject("{project_name}")
local projectExisted = false
if not project then
    project = pm:LoadProject("{project_name}")
    if project then projectExisted = true end
end'''
if old_create in content:
    content = content.replace(old_create, new_create)
    changes += 1
    print("[OK] Added projectExisted tracking")
else:
    print("[SKIP] projectExisted pattern not found")

# 2. Add project cleanup after project name print
old_step2 = 'print("  Project: " .. project:GetName())\n\n-- Step 2: Get Media Pool'
new_step2 = '''print("  Project: " .. project:GetName())

-- Step 1.5: Cleanup existing project
if projectExisted then
    print("  Cleaning up existing project...")
    local tlCount = project:GetTimelineCount()
    for i = tlCount, 1, -1 do
        local tl = project:GetTimelineByIndex(i)
        if tl then pcall(function() project:DeleteTimeline(tl) end) end
    end
    local mp = project:GetMediaPool()
    if mp then
        local root = mp:GetRootFolder()
        if root then
            local oldClips = root:GetClips()
            if oldClips then
                for _, c in pairs(oldClips) do pcall(function() mp:DeleteClips({c}) end) end
                print("    Cleared " .. #oldClips .. " media pool items")
            end
        end
    end
    print("  Cleanup complete")
end

-- Step 2: Get Media Pool'''
if old_step2 in content:
    content = content.replace(old_step2, new_step2)
    changes += 1
    print("[OK] Added project cleanup")
else:
    print("[SKIP] cleanup pattern not found")

# 3. Add file existence check
old_import = '''print("\\n[Step 3] Importing " .. #mediaFiles .. " file(s)...")
local clips = {}
local importedCount = 0
local batchOk, batchResult = pcall(function() return mediaPool:ImportMedia(mediaFiles) end)'''
new_import = '''print("\\n[Step 3] Importing " .. #mediaFiles .. " file(s)...")
local clips = {}
local importedCount = 0
local failedFiles = 0
for i, path in ipairs(mediaFiles) do
    local f = io.open(path, "rb")
    if f then f:close() else print("  WARNING: File not found: " .. path); mediaFiles[i] = nil; failedFiles = failedFiles + 1 end
end
local validFiles = {}
for _, f in ipairs(mediaFiles) do if f then table.insert(validFiles, f) end end
local batchOk, batchResult = pcall(function() return mediaPool:ImportMedia(validFiles) end)'''
if old_import in content:
    content = content.replace(old_import, new_import)
    changes += 1
    print("[OK] Added file existence check")
else:
    print("[SKIP] import pattern not found")

# 4. Fix timeline creation - always fresh
old_timeline = '''-- Step 4: Create timeline
local timeline
if importedCount > 0 then
    print("\\n[Step 4] Creating timeline: {timeline_name}")
    -- 先遍历检查是否已存在同名时间线（重试时避免冲突）
    local existingTl = nil
    local tlCount = project:GetTimelineCount()
    for i = 1, tlCount do
        local tl = project:GetTimelineByIndex(i)
        if tl and tl:GetName() == "{timeline_name}" then
            existingTl = tl
            break
        end
    end
    if existingTl then
        timeline = existingTl
        print("  Timeline already exists, reusing: " .. timeline:GetName())
    else
        timeline = mediaPool:CreateTimelineFromClips("{timeline_name}", clips)
        if not timeline then timeline = mediaPool:AppendToTimeline(clips) end
    end
    if timeline then print("  Timeline: " .. timeline:GetName()) end
end'''
new_timeline = '''-- Step 4: Create timeline (fresh - cleanup already removed old ones)
local timeline
if importedCount > 0 then
    print("\\n[Step 4] Creating timeline: {timeline_name}")
    timeline = mediaPool:CreateTimelineFromClips("{timeline_name}", clips)
    if not timeline then
        timeline = mediaPool:AppendToTimeline(clips)
        if timeline then pcall(function() timeline:SetName("{timeline_name}") end) end
    end
    if timeline then print("  Timeline: " .. timeline:GetName()) end
end'''
if old_timeline in content:
    content = content.replace(old_timeline, new_timeline)
    changes += 1
    print("[OK] Fixed timeline creation")
else:
    print("[SKIP] timeline pattern not found")

# 5. Add render_config support
old_render_param = '        output_dir: Optional[str] = None,\n    ) -> str:\n        """构建全流程 Lua'
new_render_param = '        output_dir: Optional[str] = None,\n        render_config: Optional[RenderConfig] = None,\n    ) -> str:\n        """构建全流程 Lua v3.3'
if old_render_param in content:
    content = content.replace(old_render_param, new_render_param)
    changes += 1
    print("[OK] Added render_config param")

# Write back
with open(p, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
ast.parse(content)
print(f'\nAll done! {changes} changes applied, syntax OK')
