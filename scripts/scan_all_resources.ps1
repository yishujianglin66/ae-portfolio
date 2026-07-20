$ErrorActionPreference = 'Continue'

$resourcesRoot = 'D:\AE-Work\resources'
if (-not (Test-Path $resourcesRoot)) {
    Write-Error "Resources root not found: $resourcesRoot"
    exit 1
}

Write-Output "=== Resource Library Deep Scan ==="
Write-Output "Root: $resourcesRoot"
Write-Output ""

# Categories with extensions
$categories = @(
    @{Name='fonts';     Path='fonts';     Ext=@('.ttf','.otf','.ttc','.fon')},
    @{Name='luts';      Path='luts';      Ext=@('.cube','.3dl','.look','.cms')},
    @{Name='effects';   Path='effects';   Ext=@('.png','.jpg','.jpeg','.webp','.bmp','.gif')},
    @{Name='psd';       Path='psd';       Ext=@('.psd','.psb')},
    @{Name='audio';     Path='audio';     Ext=@('.mp3','.wav','.aac','.flac','.m4a','.ogg')},
    @{Name='video';     Path='video';     Ext=@('.mp4','.mov','.mkv','.avi','.m4v','.webm')},
    @{Name='models';    Path='models';    Ext=@('.fbx','.obj','.max','.blend','.3ds','.dae')},
    @{Name='davinci';   Path='davinci';   Ext=@('.drfx','.drp','.setting','.dctl')},
    @{Name='premiere';  Path='premiere';  Ext=@('.mogrt','.prfpset','.prpreset')},
    @{Name='projects';  Path='projects';  Ext=@('.aep','.aet','.aepx')}
)

$results = @()
$totalFiles = 0
$totalSizeGB = 0

foreach ($cat in $categories) {
    $catPath = Join-Path $resourcesRoot $cat.Path
    $count = 0
    $sizeBytes = 0

    if (Test-Path $catPath) {
        Get-ChildItem -Path $catPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $cat.Ext -contains $_.Extension.ToLower()
        } | ForEach-Object {
            $count++
            $sizeBytes += $_.Length
        }
    }

    $sizeGB = [math]::Round($sizeBytes / 1GB, 2)
    $totalFiles += $count
    $totalSizeGB += $sizeGB

    $results += [PSCustomObject]@{
        Category = $cat.Name
        Path = $cat.Path
        Files = $count
        SizeGB = $sizeGB
    }
}

Write-Output "Category    Files       Size(GB)    Path"
Write-Output "--------    -----       --------    ----"
foreach ($r in $results) {
    Write-Output ("{0,-11} {1,8} {2,10:0.00} GB   {3}" -f $r.Category, $r.Files, $r.SizeGB, $r.Path)
}
Write-Output "--------    -----       --------"
Write-Output ("TOTAL       {0,8} {1,10:0.00} GB" -f $totalFiles, $totalSizeGB)

# Check for archives that need extraction
Write-Output ""
Write-Output "=== Archive Files in Resources ==="
$archiveExts = @('.zip','.rar','.7z','.tar','.gz')
$archives = Get-ChildItem -Path $resourcesRoot -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $archiveExts -contains $_.Extension.ToLower()
}
if ($archives) {
    foreach ($a in $archives) {
        $sizeMB = [math]::Round($a.Length / 1MB, 2)
        Write-Output "  $($a.Name)  ($sizeMB MB)  <-  $($a.DirectoryName)"
    }
} else {
    Write-Output "  No archive files found (all extracted)"
}

# Check for software/installers
Write-Output ""
Write-Output "=== Software Installers ==="
$softwarePath = Join-Path $resourcesRoot 'software'
if (Test-Path $softwarePath) {
    $installers = Get-ChildItem -Path $softwarePath -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        @('.exe','.msi','.dmg','.pkg') -contains $_.Extension.ToLower()
    }
    foreach ($i in $installers) {
        $sizeMB = [math]::Round($i.Length / 1MB, 2)
        Write-Output "  $($i.Name)  ($sizeMB MB)"
    }
} else {
    Write-Output "  No software directory"
}
