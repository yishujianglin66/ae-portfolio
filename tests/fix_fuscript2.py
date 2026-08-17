"""Apply remaining v3.3 improvements"""
import ast

p = r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\integrations\davinci_fuscript.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 3. Add file existence check (use actual file content patterns)
old_import = '''print("\\\\n[Step 3] Importing " .. #mediaFiles .. " file(s)...")
local clips = {{}}
local importedCount = 0
local batchOk, batchResult = pcall(function() return mediaPool:ImportMedia(mediaFiles) end)'''

new_import = '''print("\\\\n[Step 3] Importing " .. #mediaFiles .. " file(s)...")
local clips = {{}}
local importedCount = 0
local failedFiles = 0
for i, path in ipairs(mediaFiles) do
    local f = io.open(path, "rb")
    if f then f:close() else print("  WARNING: File not found: " .. path); mediaFiles[i] = nil; failedFiles = failedFiles + 1 end
end
local validFiles = {{}}
for _, f in ipairs(mediaFiles) do if f then table.insert(validFiles, f) end end
local batchOk, batchResult = pcall(function() return mediaPool:ImportMedia(validFiles) end)'''

if old_import in content:
    content = content.replace(old_import, new_import)
    changes += 1
    print("[OK] Added file existence check")
else:
    print("[SKIP] import pattern not found")

# 4. Fix timeline creation
old_timeline = '''-- Step 4: Create timeline
local timeline
if importedCount > 0 then
    print("\\\\n[Step 4] Creating timeline: {timeline_name}")
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
    print("\\\\n[Step 4] Creating timeline: {timeline_name}")
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

# Write back
with open(p, 'w', encoding='utf-8') as f:
    f.write(content)

ast.parse(content)
print(f'\nDone! {changes} more changes applied, syntax OK')
