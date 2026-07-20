# 修复 AE 安装目录下 JSON polyfill 位置问题（需要管理员权限）
# 右键 -> 使用 PowerShell 运行，或直接运行会自动请求管理员权限

# Check if running as admin
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting admin privileges..."
    Start-Process powershell -Verb runAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "Running as Administrator. Fixing system-level AE scripts..."
Write-Host ""

$polyfill = @"
// JSON polyfill for ExtendScript (when JSON is undefined)
if (typeof JSON === "undefined") { JSON = {}; }
if (typeof JSON.parse !== "function") {
    JSON.parse = function (text) {
        // Safe-ish fallback for trusted input (our own command file)
        return eval("(" + text + ")");
    };
}
if (typeof JSON.stringify !== "function") {
    (function () {
        function esc(str) {
            return (str + "")
                .replace(/\\/g, "\\\\")
                .replace(/"/g, '\\"')
                .replace(/\n/g, "\\n")
                .replace(/\r/g, "\\r")
                .replace(/\t/g, "\\t");
        }
        function toJSON(val) {
            if (val === null) return "null";
            var t = typeof val;
            if (t === "number" || t === "boolean") return String(val);
            if (t === "string") return '"' + esc(val) + '"';
            if (val instanceof Array) {
                var a = [];
                for (var i = 0; i < val.length; i++) a.push(toJSON(val[i]));
                return "[" + a.join(",") + "]";
            }
            if (t === "object") {
                var props = [];
                for (var k in val) {
                    if (val.hasOwnProperty(k) && typeof val[k] !== "function" && typeof val[k] !== "undefined") {
                        props.push('"' + esc(k) + '":' + toJSON(val[k]));
                    }
                }
                return "{" + props.join(",") + "}";
            }
            return "null";
        }
        JSON.stringify = function (value, _replacer, _space) {
            return toJSON(value);
        };
    })();
}

"@

function Fix-JsonPolyfill {
    param([string]$FilePath)
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "SKIP (not found): $FilePath"
        return $false
    }
    
    Write-Host "Processing: $FilePath"
    
    $content = Get-Content $FilePath -Raw -Encoding UTF8
    
    # Check if polyfill is already at top
    if ($content -match "^(\s*//[^\r\n]*[\r\n]+)*\s*// JSON polyfill for ExtendScript") {
        Write-Host "  Polyfill already at top, skipping"
        return $true
    }
    
    # Remove old polyfill from middle (if exists)
    $oldStart = "`r`n// JSON polyfill for ExtendScript (when JSON is undefined)"
    $idx = $content.IndexOf($oldStart)
    if ($idx -lt 0) {
        $oldStart = "`n// JSON polyfill for ExtendScript (when JSON is undefined)"
        $idx = $content.IndexOf($oldStart)
    }
    
    if ($idx -ge 0) {
        $endMarker = "`r`n// Detect AE version"
        $endIdx = $content.IndexOf($endMarker, $idx)
        if ($endIdx -lt 0) {
            $endMarker = "`n// Detect AE version"
            $endIdx = $content.IndexOf($endMarker, $idx)
        }
        if ($endIdx -ge 0) {
            $content = $content.Substring(0, $idx) + "`r`n" + $content.Substring($endIdx)
            Write-Host "  Removed old polyfill from middle"
        }
    }
    
    # Find first non-comment, non-blank line
    $lines = $content -split "`r?`n"
    $insertAt = 0
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i].Trim()
        if ($line -eq "" -or $line.StartsWith("//")) {
            continue
        }
        $insertAt = $i
        break
    }
    
    $newLines = @()
    for ($i = 0; $i -lt $insertAt; $i++) {
        $newLines += $lines[$i]
    }
    $newLines += ""
    $newLines += ($polyfill -split "`r?`n")
    for ($i = $insertAt; $i -lt $lines.Count; $i++) {
        $newLines += $lines[$i]
    }
    
    $newContent = $newLines -join "`r`n"
    
    # Backup
    $backup = $FilePath + ".bak"
    Copy-Item $FilePath $backup -Force
    Write-Host "  Backup: $backup"
    
    # Write
    try {
        [System.IO.File]::WriteAllText($FilePath, $newContent, [System.Text.Encoding]::UTF8)
        Write-Host "  Done."
        return $true
    } catch {
        Write-Host "  FAILED: $_"
        return $false
    }
}

$systemFiles = @(
    "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\Startup\mcp-bridge-auto.jsx",
    "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\mcp-bridge-auto.jsx",
    "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\mcp-bridge-auto.jsx"
)

$successCount = 0
$failCount = 0

foreach ($f in $systemFiles) {
    if (Fix-JsonPolyfill $f) { $successCount++ } else { $failCount++ }
}

Write-Host ""
Write-Host "System files: $successCount succeeded, $failCount failed"
Write-Host ""
Write-Host "Press Enter to exit..."
Read-Host
