#!/usr/bin/env python3
"""部署 create-e2e-music-video MCP工具到 after-effects-mcp-main"""
import shutil
import os

MCP_DIR = r"c:\Users\Administrator\Desktop\after-effects-mcp-main"
SRC_FILE = os.path.join(MCP_DIR, "src", "index.ts")
SCRIPTS_DIR = os.path.join(MCP_DIR, "src", "scripts")
VAULT_SCRIPT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-extension\scripts\createE2EMusicVideo.jsx"

print("=== E2E Music Video MCP Tool Deployment ===")

# Step 1: Copy JSX script
print("[1/4] Copying JSX script...")
shutil.copy2(VAULT_SCRIPT, os.path.join(SCRIPTS_DIR, "createE2EMusicVideo.jsx"))
print("  OK: createE2EMusicVideo.jsx copied")

# Step 2: Read index.ts
print("[2/4] Reading index.ts...")
with open(SRC_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Step 3: Add to allowedScripts
print("[3/4] Patching allowedScripts + tool registration...")
if '"createE2EMusicVideo"' in content:
    print("  SKIP: createE2EMusicVideo already exists")
else:
    # Add to allowedScripts
    content = content.replace(
        '"setEffectKeyframes"\n    ]',
        '"setEffectKeyframes",\n      "createE2EMusicVideo"\n    ]'
    )

    # Register tool before main()
    tool_code = '''
// ============================================================================
// E2E Music Video Tool - One-click full composition creation
// ============================================================================

server.tool(
  "create-e2e-music-video",
  "一键创建完整音乐视频合成。包含帧序列导入、主体/披风层处理、粒子系统、背景大气、调色、摄像机节拍同步、BGM导入等全部步骤。使用AE内置效果(ADBE Color Key/ADBE Glo2/ADBE Ramp)确保兼容性。需要先在AE中运行mcp-bridge-auto.jsx监听",
  {
    compName: z.string().optional().default("E2E_音乐视频").describe("合成名称"),
    frameDir: z.string().optional().default("D:/AE-Work/视频素材库/frames").describe("帧序列目录"),
    bgmPath: z.string().optional().describe("背景音乐文件路径"),
    beatTimes: z.array(z.number()).optional().describe("节拍时间点数组（秒）"),
    energyPeaks: z.array(z.number()).optional().describe("能量峰值时间点数组（秒）"),
    peakValues: z.array(z.number()).optional().describe("能量峰值强度数组"),
    bpm: z.number().optional().default(0).describe("音乐BPM"),
    width: z.number().int().positive().optional().default(576).describe("合成宽度"),
    height: z.number().int().positive().optional().default(768).describe("合成高度"),
    duration: z.number().positive().optional().default(12).describe("合成时长（秒）"),
    fps: z.number().int().positive().optional().default(30).describe("帧率")
  },
  async ({ compName, frameDir, bgmPath, beatTimes, energyPeaks, peakValues, bpm, width, height, duration, fps }) => {
    try {
      clearResultsFile();
      writeCommandFile("createE2EMusicVideo", {
        compName: compName || "E2E_音乐视频",
        frameDir: frameDir || "D:/AE-Work/视频素材库/frames",
        bgmPath: bgmPath || "",
        beatTimes: beatTimes || [],
        energyPeaks: energyPeaks || [],
        peakValues: peakValues || [],
        bpm: bpm || 0,
        width: width || 576,
        height: height || 768,
        duration: duration || 12,
        fps: fps || 30
      });
      const result = await waitForBridgeResult("createE2EMusicVideo", 30000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

'''

    insert_point = "async function main() {"
    content = content.replace(insert_point, tool_code + insert_point)
    print("  OK: Tool registered")

with open(SRC_FILE, "w", encoding="utf-8") as f:
    f.write(content)

# Step 4: Build
print("[4/4] Building...")
import subprocess
result = subprocess.run(
    ["npm", "run", "build"],
    cwd=MCP_DIR,
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
print(f"  Exit code: {result.returncode}")

if result.returncode == 0:
    print("\n=== Deployment Complete ===")
    print("Tool: create-e2e-music-video")
    print("Next: Restart Trae MCP server, then call the tool")
else:
    print("\n=== Build Failed ===")
