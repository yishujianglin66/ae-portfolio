# Fix AE Error 146 - Cinema 4D.exe missing in Keyfiles
# Strategy: Copy Cinema 4D.exe from installed Maxon C4D to the Keyfiles CustomHook directory

$ErrorActionPreference = 'Stop'

Write-Output "=== Fix AE Error 146 - Cinema 4D.exe Missing ==="
Write-Output ""

# Source paths
$cinemaExe = "C:\Program Files\Maxon Cinema 4D 2026\Cinema 4D.exe"

# Target paths for both 25 and 26 versions
$targets = @(
    "C:\Program Files\Common Files\Adobe\Keyfiles\AfterEffects\25\CustomHook\win",
    "C:\Program Files\Common Files\Adobe\Keyfiles\AfterEffects\26\CustomHook\win"
)

if (-not (Test-Path $cinemaExe)) {
    Write-Output "ERROR: Cinema 4D.exe not found at $cinemaExe"
    Write-Output "Searching for Cinema 4D.exe on C drive..."
    $found = Get-ChildItem "C:\Program Files" -Recurse -Filter "Cinema 4D.exe" -ErrorAction SilentlyContinue -Depth 4
    if ($found) {
        $cinemaExe = $found[0].FullName
        Write-Output "Found at: $cinemaExe"
    } else {
        Write-Output "ERROR: Cannot find Cinema 4D.exe anywhere"
        exit 1
    }
}

Write-Output "Source: $cinemaExe"
Write-Output "Size: $([math]::Round((Get-Item $cinemaExe).Length / 1MB, 2)) MB"
Write-Output ""

foreach ($targetDir in $targets) {
    Write-Output "Processing: $targetDir"

    if (-not (Test-Path $targetDir)) {
        Write-Output "  Directory missing, creating..."
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    $targetFile = Join-Path $targetDir "Cinema 4D.exe"

    if (Test-Path $targetFile) {
        Write-Output "  Cinema 4D.exe already exists, skipping"
    } else {
        Write-Output "  Copying Cinema 4D.exe..."
        Copy-Item -Path $cinemaExe -Destination $targetFile -Force
        Write-Output "  Copy complete"
    }

    # Also check for other potentially needed files
    Write-Output "  Files in directory:"
    Get-ChildItem $targetDir -File | ForEach-Object {
        $size = [math]::Round($_.Length / 1MB, 2)
        Write-Output "    $($_.Name) ($size MB)"
    }
    Write-Output ""
}

Write-Output "=== Backup existing AE installation ==="
$aePath = "C:\Program Files\Adobe\Adobe After Effects 2025"
if (Test-Path $aePath) {
    Write-Output "  AE 2025 directory exists, checking size..."
    $size = (Get-ChildItem $aePath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    Write-Output "  Size: $([math]::Round($size / 1GB, 2)) GB"
} else {
    Write-Output "  No existing AE 2025 installation found"
}

Write-Output ""
Write-Output "=== Fix Complete ==="
Write-Output "Now try running the AE 2025 installer again."
