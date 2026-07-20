$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Drawing

# ============== Step 1: Get truly installed fonts by FontFamily name ==============
Write-Output "=== Step 1: Read installed fonts (by FontFamily) ==="

$installedFamilies = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
$installedFontObjects = @{}

# Use InstalledFontCollection (GDI+)
$ifc = New-Object System.Drawing.Text.InstalledFontCollection
foreach ($f in $ifc.Families) {
    [void]$installedFamilies.Add($f.Name)
    $installedFontObjects[$f.Name.ToLower()] = $true
}
Write-Output "InstalledFontCollection reports: $($installedFamilies.Count) font families"

# Also enumerate registry for PostScript names (covers non-GDI registered fonts)
$regPaths = @(
    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts',
    'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
)
$regFontNames = @{}
foreach ($rp in $regPaths) {
    if (Test-Path $rp) {
        $props = Get-ItemProperty -Path $rp -ErrorAction SilentlyContinue
        if ($props) {
            $props.PSObject.Properties | Where-Object {
                $_.Name -notlike 'PS*'
            } | ForEach-Object {
                # Registry value names look like "Microsoft YaHei (TrueType)" or "Arial (OpenType)"
                $regName = $_.Name
                # Strip trailing "(TrueType)" / "(OpenType)" / "bold/italic" type markers
                $cleanName = $regName -replace '\s*\((TrueType|OpenType)\)\s*$',''
                $cleanName = $cleanName -replace '\s+(Bold|Italic|Regular|Light|Medium|Black|Thin|Heavy|Semibold|Condensed)\s*$',''
                $cleanName = $cleanName.Trim()
                if ($cleanName) {
                    $regFontNames[$cleanName.ToLower()] = $regName
                }
            }
        }
    }
}
Write-Output "Registry font name entries: $($regFontNames.Count)"

# Save installed font names
$installedList = 'D:\AE-Work\installed_font_names.txt'
($installedFamilies | Sort-Object) | Out-File -FilePath $installedList -Encoding UTF8
Write-Output "Installed font family names saved: $installedList"
Write-Output ""

# ============== Step 2: Scan resource library and read font internal names ==============
Write-Output "=== Step 2: Scan resource library fonts (read internal names) ==="

$fontsRoot = 'D:\AE-Work\resources\fonts'
$fontExtensions = @('.ttf', '.otf', '.ttc')

# Use PrivateFontCollection to read internal font family name from font file
Add-Type -AssemblyName System.Drawing

$resourceFontFiles = Get-ChildItem -Path $fontsRoot -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $fontExtensions -contains $_.Extension.ToLower()
}
Write-Output "Resource font files total: $($resourceFontFiles.Count)"

$uninstalled = New-Object System.Collections.ArrayList
$alreadyInstalled = 0
$failedToRead = 0
$counter = 0
$startTime = Get-Date

foreach ($file in $resourceFontFiles) {
    $counter++
    try {
        $pfc = New-Object System.Drawing.Text.PrivateFontCollection
        $pfc.AddFontFile($file.FullName)
        if ($pfc.Families.Count -gt 0) {
            $familyName = $pfc.Families[0].Name
            $pfc.Dispose()

            # Check if this family name is already installed
            $isInstalled = $installedFamilies.Contains($familyName) -or $regFontNames.ContainsKey($familyName.ToLower())
            if (-not $isInstalled) {
                # Some font files register multiple styles; also try filename-based check as fallback
                # but the authoritative check is family name
                [void]$uninstalled.Add([PSCustomObject]@{
                    FilePath = $file.FullName
                    FileName = $file.Name
                    FamilyName = $familyName
                })
            } else {
                $alreadyInstalled++
            }
        }
    } catch {
        $failedToRead++
    }

    if ($counter % 200 -eq 0 -or $counter -eq $resourceFontFiles.Count) {
        $now = Get-Date
        $elapsed = ($now - $startTime).TotalSeconds
        $rate = if ($elapsed -gt 0) { [math]::Round($counter / $elapsed, 2) } else { 0 }
        Write-Output "  [$now] Scanned: $counter/$($resourceFontFiles.Count) | Already installed: $alreadyInstalled | Uninstalled: $($uninstalled.Count) | Failed: $failedToRead | Rate: ${rate}/s"
    }
}

Write-Output ""
Write-Output "=== Step 3: Summary ==="
Write-Output "Total resource fonts scanned: $($resourceFontFiles.Count)"
Write-Output "Already installed (by family name): $alreadyInstalled"
Write-Output "Truly uninstalled: $($uninstalled.Count)"
Write-Output "Failed to read: $failedToRead"

# Save truly uninstalled list
$uninstalledList = 'D:\AE-Work\truly_uninstalled_fonts.txt'
$uninstalled | ForEach-Object { "$($_.FilePath)|$($_.FamilyName)" } | Out-File -FilePath $uninstalledList -Encoding UTF8
Write-Output "Truly uninstalled list saved: $uninstalledList"

# Output sample
if ($uninstalled.Count -gt 0) {
    Write-Output ""
    Write-Output "---First 20 truly uninstalled fonts---"
    $uninstalled | Select-Object -First 20 | ForEach-Object {
        Write-Output "  [$($_.FamilyName)]  $($_.FileName)"
    }
}
