$filePath = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts\Startup\fixParticular.jsx"

if (-not (Test-Path $filePath)) {
    Write-Host "File not found: $filePath"
    exit 1
}

$content = Get-Content $filePath -Raw

if ($content -match 'JSON\.parse|JSON\.stringify') {
    if ($content -notmatch 'typeof JSON') {
        Write-Host "Adding JSON polyfill to fixParticular.jsx..."
        
        $jsonPolyfill = @"
// JSON polyfill for ExtendScript (must be at top)
if (typeof JSON === "undefined") { JSON = {}; }
if (typeof JSON.parse !== "function") {
    JSON.parse = function (text) {
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
        
        $newContent = $jsonPolyfill + $content
        Set-Content -Path $filePath -Value $newContent -NoNewline
        Write-Host "Successfully added JSON polyfill to $filePath"
    } else {
        Write-Host "JSON polyfill already exists in $filePath"
    }
} else {
    Write-Host "No JSON usage found in $filePath"
}
