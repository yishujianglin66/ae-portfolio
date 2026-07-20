$ErrorActionPreference = "Stop"

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
    
    # Remove old polyfill from middle (if exists) - simple string approach
    $oldStart = "`r`n// JSON polyfill for ExtendScript (when JSON is undefined)"
    $idx = $content.IndexOf($oldStart)
    if ($idx -lt 0) {
        $oldStart = "`n// JSON polyfill for ExtendScript (when JSON is undefined)"
        $idx = $content.IndexOf($oldStart)
    }
    
    if ($idx -ge 0) {
        # Find the end of the polyfill block - look for "// Detect AE version" or similar marker after it
        $endMarker = "`r`n// Detect AE version"
        $endIdx = $content.IndexOf($endMarker, $idx)
        if ($endIdx -lt 0) {
            $endMarker = "`n// Detect AE version"
            $endIdx = $content.IndexOf($endMarker, $idx)
        }
        if ($endIdx -lt 0) {
            # Try to find next major comment section
            $endIdx = $content.IndexOf("`r`n// ", $idx + 100)
            if ($endIdx -lt 0) { $endIdx = $content.IndexOf("`n// ", $idx + 100) }
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
    
    # Write
    try {
        [System.IO.File]::WriteAllText($FilePath, $newContent, [System.Text.Encoding]::UTF8)
        Write-Host "  Done. New size: $($newContent.Length) bytes"
        return $true
    } catch {
        Write-Host "  FAILED: $_"
        return $false
    }
}

$successCount = 0
$failCount = 0

# User-writable files
$userFiles = @(
    "C:\Users\Administrator\AppData\Roaming\Adobe\After Effects\Logs\Scripts\Startup\ae_mcp_auto_listener.jsx",
    "C:\Users\Administrator\AppData\Roaming\Adobe\After Effects\26.3\Scripts\ae_mcp_listener_v2.jsx",
    "C:\Users\Administrator\AppData\Roaming\Adobe\After Effects\26.3\Scripts\Startup\mcp-bridge-auto.jsx",
    "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae_mcp_listener.jsx"
)

foreach ($f in $userFiles) {
    if (Fix-JsonPolyfill $f) { $successCount++ } else { $failCount++ }
}

Write-Host ""
Write-Host "User files: $successCount succeeded, $failCount failed"
Write-Host ""
Write-Host "Note: Program Files (AE 2025/2026 installation dir) require admin rights."
Write-Host "Run this script as Administrator to fix those too."
