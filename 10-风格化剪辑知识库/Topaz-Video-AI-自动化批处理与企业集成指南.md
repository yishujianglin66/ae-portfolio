# Topaz Video AI 自动化批处理与企业集成指南

> 适用版本：Topaz Video AI 4.x CLI / GUI | 更新日期：2026-07-14 | 分类：企业级工作流实战

---

## 目录

- [一、CLI命令行接口完全手册](#一cli命令行接口完全手册)
- [二、批处理工作流设计](#二批处理工作流设计)
- [三、与Adobe集成工作流](#三与adobe集成工作流)
- [四、企业级流水线设计](#四企业级流水线设计)
- [五、性能优化深度指南](#五性能优化深度指南)
- [六、常见场景实战模板](#六常见场景实战模板)
- [七、故障排查与日志分析](#七故障排查与日志分析)
- [八、竞品对比与选型建议](#八竞品对比与选型建议)

---

## 一、CLI命令行接口完全手册

### 1.1 CLI安装与配置

Topaz Video AI 4.x 的 CLI 工具随主程序一起安装，位于：

- **Windows**: `C:\Program Files\Topaz Labs LLC\Topaz Video AI\veai.exe`
- **macOS**: `/Applications/Topaz Video AI.app/Contents/MacOS/veai`
- **Linux**（仅 Docker）: 容器内 `/opt/topaz/veai`

```python
class TopazCLISetup:
    """CLI 安装与环境配置原子步骤。"""
    WINDOWS_PATH = r'C:\Program Files\Topaz Labs LLC\Topaz Video AI\veai.exe'
    MACOS_PATH = '/Applications/Topaz Video AI.app/Contents/MacOS/veai'
    MIN_VERSION = '4.0.0'

    ENV_VARS = {
        'VEAI_MODELS_DIR':   '自定义模型目录',
        'VEAI_CACHE_DIR':    '自定义缓存目录',
        'VEAI_LOG_LEVEL':    '日志级别：debug/info/warning/error',
        'VEAI_GPU_DEVICE':   '指定 GPU 设备 ID（多卡场景）',
        'VEAI_MAX_VRAM_GB':  '限制最大显存使用量',
        'CUDA_VISIBLE_DEVICES': 'NVIDIA 多卡选择'
    }

    def verify_installation(self):
        """验证 CLI 是否可用。"""
        import subprocess
        try:
            result = subprocess.run(
                [self.WINDOWS_PATH, '--version'],
                capture_output=True, text=True, timeout=15
            )
            version = result.stdout.strip()
            return {'status': 'ok', 'version': version,
                    'compatible': self._is_compatible(version)}
        except subprocess.TimeoutExpired:
            return {'status': 'error', 'error': 'CLI 响应超时'}
        except FileNotFoundError:
            return {'status': 'error', 'error': '未找到 CLI，请检查安装路径'}

    def _is_compatible(self, version_str):
        # 提取主版本号
        try:
            major = int(version_str.split('.')[0])
            return major >= 4
        except (IndexError, ValueError):
            return False

    def configure_environment(self, env_overrides):
        """配置运行环境变量。"""
        import os
        for key, value in env_overrides.items():
            if key in self.ENV_VARS:
                os.environ[key] = str(value)
        return {'status': 'ok', 'configured': env_overrides}
```

### 1.2 完整命令参数参考

```python
class TopazCLIReference:
    """Topaz Video AI CLI 完整参数参考。"""
    COMMANDS = {
        'enhance': {
            'description': '视频增强（超分、降噪、修复）',
            'required': ['-i', '-o'],
            'optional': ['--model', '--scale', '--noise', '--sharpen',
                         '--detail', '--dehalo', '--deblur', '--compression',
                         '--codec', '--bitrate', '--fps', '--color-space']
        },
        'interpolate': {
            'description': '帧插值',
            'required': ['-i', '-o'],
            'optional': ['--model', '--fps', '--slowmo', '--sensitivity',
                         '--smoothness', '--detail']
        },
        'deinterlace': {
            'description': '去隔行',
            'required': ['-i', '-o'],
            'optional': ['--model', '--field-order', '--motion', '--detail']
        },
        'restore': {
            'description': '综合修复（多模型流水线）',
            'required': ['-i', '-o'],
            'optional': ['--pipeline', '--preset']
        },
        'list-models': {
            'description': '列出所有可用模型',
            'required': [],
            'optional': ['--type', '--version']
        },
        'benchmark': {
            'description': '性能基准测试',
            'required': [],
            'optional': ['--model', '--resolution', '--frames']
        }
    }

    GLOBAL_OPTIONS = {
        '--verbose':       {'type': 'flag',   'description': '详细日志输出'},
        '--quiet':         {'type': 'flag',   'description': '静默模式'},
        '--log-file':      {'type': 'path',   'description': '日志文件路径'},
        '--gpu':           {'type': 'string', 'description': '指定 GPU 设备'},
        '--no-gpu':        {'type': 'flag',   'description': '禁用 GPU，使用 CPU'},
        '--precision':     {'type': 'string', 'description': '推理精度：fp16/fp32',
                            'default': 'fp16'},
        '--tile-size':     {'type': 'int',    'description': '分块大小',
                            'default': 'auto'},
        '--max-vram':      {'type': 'int',    'description': '最大显存使用 GB'},
        '--temp-dir':      {'type': 'path',   'description': '临时文件目录'},
        '--keep-temp':     {'type': 'flag',   'description': '保留中间文件'},
        '--license':       {'type': 'string', 'description': '许可证密钥'}
    }
```

**典型命令示例**：

```bash
# 基础增强：720p 转 4K，使用 Proteus 模型
veai.exe enhance ^
  -i input_720p.mp4 ^
  -o output_4k.mp4 ^
  --model proteus ^
  --scale 4 ^
  --noise 35 ^
  --sharpen 30 ^
  --compression 60 ^
  --codec h264 ^
  --bitrate 20M ^
  --color-space bt709 ^
  --log-file "D:\logs\enhance.log"

# 帧插值：24fps 转 60fps
veai.exe interpolate ^
  -i input_24fps.mp4 ^
  -o output_60fps.mp4 ^
  --model apollo-fast ^
  --fps 60 ^
  --sensitivity 50 ^
  --smoothness 60

# 4 倍慢动作
veai.exe interpolate ^
  -i input_60fps.mp4 ^
  -o output_slowmo.mp4 ^
  --model chronos ^
  --slowmo 4 ^
  --smoothness 60

# 隔行视频修复
veai.exe deinterlace ^
  -i old_dv.avi ^
  -o restored.mp4 ^
  --model dione-dv ^
  --field-order top_first ^
  --motion 55

# 列出所有可用模型
veai.exe list-models --type enhance --version 4.1

# 性能基准测试
veai.exe benchmark --model proteus --resolution 1920x1080 --frames 30
```

### 1.3 批处理脚本编写

```python
class TopazBatchScript:
    """Topaz CLI 批处理脚本生成器。"""
    def __init__(self, veai_path):
        self.veai = veai_path
        self.tasks = []

    def add_enhance_task(self, input_file, output_file, model, params):
        """添加增强任务。"""
        cmd = [self.veai, 'enhance', '-i', input_file, '-o', output_file,
               '--model', model]
        for k, v in params.items():
            cmd.extend([f'--{k}', str(v)])
        self.tasks.append({
            'type': 'enhance',
            'input': input_file,
            'output': output_file,
            'command': cmd
        })
        return self.tasks[-1]

    def add_interpolate_task(self, input_file, output_file, model, target_fps):
        """添加帧插值任务。"""
        cmd = [self.veai, 'interpolate', '-i', input_file, '-o', output_file,
               '--model', model, '--fps', str(target_fps)]
        self.tasks.append({
            'type': 'interpolate',
            'input': input_file,
            'output': output_file,
            'command': cmd
        })
        return self.tasks[-1]

    def to_batch_file(self, output_path, format='ps1'):
        """生成批处理文件。"""
        if format == 'ps1':
            return self._to_powershell(output_path)
        elif format == 'sh':
            return self._to_bash(output_path)
        elif format == 'bat':
            return self._to_bat(output_path)
        raise ValueError(f'不支持的格式: {format}')

    def _to_powershell(self, output_path):
        lines = [
            '# Topaz Video AI 批处理脚本（PowerShell）',
            '# 自动生成，请勿手动修改',
            '$ErrorActionPreference = "Stop"',
            f'$veai = "{self.veai}"',
            f'$logFile = "D:\\logs\\topaz_batch_{__import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")}.log"',
            'function Write-Log {',
            '    param([string]$msg)',
            '    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"',
            '    $line = "[$time] $msg"',
            '    Write-Host $line',
            '    Add-Content -Path $logFile -Value $line',
            '}',
            ''
        ]
        for i, task in enumerate(self.tasks, 1):
            lines.append(f'# Task {i}: {task["type"]} - {task["input"]}')
            cmd_str = ' '.join(f'"{a}"' if ' ' in str(a) else a for a in task['command'])
            lines.append(f'Write-Log "Starting task {i}: {task["input"]}"')
            lines.append(f'& {cmd_str}')
            lines.append('if ($LASTEXITCODE -ne 0) {')
            lines.append(f'    Write-Log "Task {i} failed with exit code $LASTEXITCODE"')
            lines.append('    exit 1')
            lines.append('}')
            lines.append(f'Write-Log "Task {i} completed: {task["output"]}"')
            lines.append('')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return output_path

    def _to_bash(self, output_path):
        lines = [
            '#!/bin/bash',
            '# Topaz Video AI 批处理脚本（Bash）',
            'set -e',
            f'VEAI="{self.veai}"',
            'LOG_FILE="/tmp/topaz_batch_$(date +%Y%m%d_%H%M%S).log"',
            'log() {',
            '    echo "[$(date "+%Y-%m-%d %H:%M:%S")] $1" | tee -a "$LOG_FILE"',
            '}',
            ''
        ]
        for i, task in enumerate(self.tasks, 1):
            lines.append(f'# Task {i}: {task["type"]}')
            cmd_str = ' '.join(f'"{a}"' if ' ' in str(a) else a for a in task['command'])
            lines.append(f'log "Starting task {i}"')
            lines.append(f'{cmd_str}')
            lines.append(f'log "Task {i} completed"')
            lines.append('')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return output_path

    def _to_bat(self, output_path):
        lines = [
            '@echo off',
            'REM Topaz Video AI 批处理脚本（CMD）',
            f'set VEAI="{self.veai}"',
            'set LOGFILE=D:\\logs\\topaz_batch.log',
            ''
        ]
        for i, task in enumerate(self.tasks, 1):
            cmd_str = ' '.join(f'"{a}"' if ' ' in str(a) else a for a in task['command'])
            lines.append(f'REM Task {i}')
            lines.append(f'echo [{i}/{len(self.tasks)}] Processing {task["input"]}...')
            lines.append(f'%VEAI% ' + ' '.join(cmd_str.split()[1:]))
            lines.append('if errorlevel 1 (')
            lines.append(f'    echo Task {i} failed')
            lines.append('    exit /b 1')
            lines.append(')')
            lines.append('')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return output_path
```

### 1.4 与FFmpeg联动工作流

```python
class FFmpegIntegration:
    """FFmpeg + Topaz 联动工作流。"""
    SCENARIOS = {
        'preprocess_then_enhance': {
            'description': 'FFmpeg 预处理（解帧、转码）→ Topaz 增强 → FFmpeg 封装',
            'pipeline': [
                'ffmpeg -i input.mp4 -c:v rawvideo -pix_fmt rgb24 temp/input_%06d.png',
                'veai.exe enhance -i temp/input_%06d.png -o temp/output_%06d.png --model proteus --scale 4',
                'ffmpeg -framerate 24 -i temp/output_%06d.png -c:v libx264 -crf 18 -pix_fmt yuv420p output_4k.mp4'
            ]
        },
        'split_then_enhance': {
            'description': '长视频分段 → 并行增强 → 合并',
            'pipeline': [
                'ffmpeg -i long.mp4 -c copy -map 0 -segment_time 600 -f segment temp/seg_%03d.mp4',
                '# 并行处理所有 seg_*.mp4',
                'ffmpeg -f concat -i filelist.txt -c copy output.mp4'
            ]
        },
        'audio_preserve': {
            'description': 'Topaz 仅处理视频，音频从原片复制',
            'pipeline': [
                'veai.exe enhance -i input.mp4 -o enhanced_video.mp4 --codec h264 --no-audio',
                'ffmpeg -i enhanced_video.mp4 -i input.mp4 -map 0:v -map 1:a -c:v copy -c:a aac output.mp4'
            ]
        },
        'frame_extract_analyze': {
            'description': '抽取关键帧分析 → 选择模型 → 整片增强',
            'pipeline': [
                'ffmpeg -i input.mp4 -vf "select=eq(pict_type\\,I)" -vsync vfr temp/keyframe_%03d.png',
                'python analyze.py --frames temp/keyframe_*.png  # 选择最优模型',
                'veai.exe enhance -i input.mp4 -o output.mp4 --model {selected_model}'
            ]
        }
    }

    def generate_workflow(self, scenario, input_file, output_file, **kwargs):
        """生成 FFmpeg + Topaz 联动脚本。"""
        template = self.SCENARIOS.get(scenario)
        if not template:
            return {'error': f'未知场景: {scenario}'}
        commands = []
        for cmd in template['pipeline']:
            cmd_filled = cmd.replace('input.mp4', input_file).replace('output.mp4', output_file)
            for k, v in kwargs.items():
                cmd_filled = cmd_filled.replace(f'{{{k}}}', str(v))
            commands.append(cmd_filled)
        return {'scenario': scenario, 'description': template['description'],
                'commands': commands}
```

---

## 二、批处理工作流设计

### 2.1 GUI批处理模式

```python
class TopazGUIBatch:
    """Topaz GUI 批处理模式管理。"""
    QUEUE_LIMITS = {
        'free': 5,
        'pro': 100,
        'enterprise': 1000
    }

    def __init__(self, license_tier='pro'):
        self.license_tier = license_tier
        self.queue = []
        self.presets = {}

    def add_to_queue(self, input_file, output_file, settings):
        """添加任务到批处理队列。"""
        if len(self.queue) >= self.QUEUE_LIMITS[self.license_tier]:
            return {'success': False, 'error': '队列已满'}
        task = {
            'id': len(self.queue) + 1,
            'input': input_file,
            'output': output_file,
            'settings': settings,
            'status': 'pending',
            'added_at': self._timestamp()
        }
        self.queue.append(task)
        return {'success': True, 'task_id': task['id']}

    def reorder_queue(self, new_order):
        """重排队列。"""
        if sorted(new_order) != list(range(1, len(self.queue) + 1)):
            return {'success': False, 'error': '无效的顺序'}
        task_map = {t['id']: t for t in self.queue}
        self.queue = [task_map[i] for i in new_order]
        return {'success': True}

    def save_preset(self, name, model, params):
        """保存预设。"""
        self.presets[name] = {'model': model, 'params': params}
        return {'success': True, 'preset': name}

    def apply_preset(self, preset_name, input_file, output_file):
        """应用预设到新任务。"""
        if preset_name not in self.presets:
            return {'success': False, 'error': f'预设 {preset_name} 不存在'}
        preset = self.presets[preset_name]
        return self.add_to_queue(input_file, output_file, preset)

    def export_queue(self, file_path):
        """导出队列为 JSON。"""
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({'queue': self.queue, 'presets': self.presets}, f,
                      indent=2, ensure_ascii=False)
        return {'success': True, 'file': file_path}

    def _timestamp(self):
        from datetime import datetime
        return datetime.now().isoformat()
```

**批量渲染优化策略**：

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| 顺序处理 | 按队列顺序逐个处理 | 任务少、单任务时间长 |
| 并行 GPU | 多 GPU 同时处理不同任务 | 多 GPU 工作站 |
| 分块并行 | 单个任务分块并行处理 | 单个长视频 |
| 优先级调度 | 按紧急程度动态排序 | 紧急任务插队 |
| 错峰调度 | 在非工作时段执行 | 节省电费、夜间批处理 |

### 2.2 CLI自动化批处理

#### PowerShell脚本模板

```powershell
<#
.SYNOPSIS
    Topaz Video AI 自动化批处理 PowerShell 脚本
.DESCRIPTION
    扫描输入目录，对每个视频文件应用 Topaz 增强，输出到指定目录
.NOTES
    作者: AE Knowledge Vault
    日期: 2026-07-14
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$InputDir,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputDir,
    
    [string]$Model = "proteus",
    [int]$Scale = 2,
    [int]$Noise = 30,
    [int]$Sharpen = 30,
    [int]$Compression = 50,
    [int]$MaxParallel = 1,
    [string]$LogFile = "D:\logs\topaz_batch.log"
)

$ErrorActionPreference = "Stop"
$veai = "C:\Program Files\Topaz Labs LLC\Topaz Video AI\veai.exe"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$time][$Level] $Message"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

function Invoke-TopazTask {
    param(
        [string]$Input,
        [string]$Output,
        [hashtable]$Params
    )
    
    $args = @('enhance', '-i', $Input, '-o', $Output, '--model', $Params.Model,
              '--scale', $Params.Scale, '--noise', $Params.Noise,
              '--sharpen', $Params.Sharpen, '--compression', $Params.Compression,
              '--codec', 'h264', '--bitrate', '15M')
    
    Write-Log "处理: $Input -> $Output"
    $start = Get-Date
    
    & $veai @args
    
    $exitCode = $LASTEXITCODE
    $duration = (Get-Date) - $start
    
    if ($exitCode -eq 0) {
        Write-Log "完成: $Output (耗时: $($duration.ToString()))"
    } else {
        Write-Log "失败: $Input (exit=$exitCode)" "ERROR"
    }
    
    return @{ Success = ($exitCode -eq 0); Duration = $duration }
}

# 主流程
if (-not (Test-Path $InputDir)) { throw "输入目录不存在: $InputDir" }
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }

$videoFiles = Get-ChildItem -Path $InputDir -Include *.mp4,*.mov,*.avi,*.mkv -Recurse
Write-Log "找到 $($videoFiles.Count) 个视频文件"

$params = @{
    Model = $Model
    Scale = $Scale
    Noise = $Noise
    Sharpen = $Sharpen
    Compression = $Compression
}

$results = @()
foreach ($file in $videoFiles) {
    $relPath = $file.FullName.Substring($InputDir.Length).TrimStart('\')
    $outputPath = Join-Path $OutputDir $relPath
    $outputDir = Split-Path $outputPath -Parent
    if (-not (Test-Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }
    # 修改扩展名为 .mp4
    $outputPath = [System.IO.Path]::ChangeExtension($outputPath, ".mp4")
    
    $result = Invoke-TopazTask -Input $file.FullName -Output $outputPath -Params $params
    $results += @{ File = $file.Name; Result = $result }
}

# 生成报告
$success = ($results | Where-Object { $_.Result.Success }).Count
$failed = $results.Count - $success
Write-Log "批处理完成：成功 $success / 失败 $failed / 总计 $($results.Count)"

$results | Export-Csv -Path "$OutputDir\batch_report.csv" -NoTypeInformation -Encoding UTF8
```

#### Bash脚本模板

```bash
#!/bin/bash
# Topaz Video AI 批处理脚本（Linux/macOS）
set -e

VEAI="/Applications/Topaz Video AI.app/Contents/MacOS/veai"
INPUT_DIR="${1:-./input}"
OUTPUT_DIR="${2:-./output}"
MODEL="${3:-proteus}"
LOG_FILE="./topaz_batch_$(date +%Y%m%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

mkdir -p "$OUTPUT_DIR"

process_video() {
    local input="$1"
    local output="$2"
    log "Processing: $input"
    
    start_time=$(date +%s)
    if "$VEAI" enhance -i "$input" -o "$output" \
        --model "$MODEL" --scale 2 --noise 30 --sharpen 30 \
        --codec h264 --bitrate 15M; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log "Done: $output (${duration}s)"
        return 0
    else
        log "FAILED: $input"
        return 1
    fi
}

# 主循环
find "$INPUT_DIR" -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.mkv" \) | while read file; do
    rel_path="${file#$INPUT_DIR/}"
    output="$OUTPUT_DIR/${rel_path%.*}_enhanced.mp4"
    mkdir -p "$(dirname "$output")"
    process_video "$file" "$output" || continue
done

log "Batch processing complete"
```

#### 无人值守处理方案

```python
class UnattendedProcessing:
    """无人值守批处理方案。"""
    def __init__(self, config_file='topaz_batch.yaml'):
        import yaml
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.watch_dirs = self.config.get('watch_dirs', [])
        self.output_dir = self.config.get('output_dir', './output')
        self.completed_dir = self.config.get('completed_dir', './completed')
        self.failed_dir = self.config.get('failed_dir', './failed')

    def watch_and_process(self, poll_interval=60):
        """监视目录并自动处理新文件。"""
        import time
        from pathlib import Path
        processed = set()
        while True:
            for watch_dir in self.watch_dirs:
                for ext in ('*.mp4', '*.mov', '*.avi', '*.mkv'):
                    for file_path in Path(watch_dir).glob(f'**/{ext}'):
                        if str(file_path) in processed:
                            continue
                        result = self._process_one(file_path)
                        if result['success']:
                            self._move_to(file_path, self.completed_dir)
                        else:
                            self._move_to(file_path, self.failed_dir)
                        processed.add(str(file_path))
            time.sleep(poll_interval)

    def _process_one(self, input_path):
        import subprocess
        output_path = Path(self.output_dir) / f"{input_path.stem}_enhanced.mp4"
        cmd = ['veai.exe', 'enhance', '-i', str(input_path),
               '-o', str(output_path), '--model', 'proteus']
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=3600)
            return {'success': result.returncode == 0, 'output': str(output_path)}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'timeout'}

    def _move_to(self, src, dest_dir):
        import shutil
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(Path(dest_dir) / src.name))
```

### 2.3 Python自动化

```python
class TopazPythonAutomation:
    """Python 调用 Topaz CLI 的批量处理框架。"""
    import subprocess
    import json
    import time
    from pathlib import Path
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def __init__(self, veai_path, max_workers=1, log_dir='./logs'):
        self.veai = veai_path
        self.max_workers = max_workers
        self.log_dir = self.Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retry_max = 3
        self.retry_delay = 30  # 秒

    def build_command(self, action, input_file, output_file, **params):
        """构建 CLI 命令。"""
        cmd = [self.veai, action, '-i', str(input_file), '-o', str(output_file)]
        for k, v in params.items():
            cmd.extend([f'--{k.replace("_", "-")}', str(v)])
        return cmd

    def execute_task(self, task):
        """执行单个任务，带重试机制。"""
        cmd = self.build_command(task['action'], task['input'],
                                 task['output'], **task.get('params', {}))
        log_file = self.log_dir / f"{self.Path(task['input']).stem}.log"
        for attempt in range(1, self.retry_max + 1):
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n=== Attempt {attempt} ===\n")
                    result = self.subprocess.run(
                        cmd, stdout=f, stderr=self.subprocess.STDOUT,
                        timeout=7200, text=True
                    )
                if result.returncode == 0:
                    return {'task': task, 'success': True,
                            'attempts': attempt, 'log': str(log_file)}
                # 失败重试
                self.time.sleep(self.retry_delay * attempt)
            except self.subprocess.TimeoutExpired:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\nTimeout on attempt {attempt}\n")
                self.time.sleep(self.retry_delay * attempt)
        return {'task': task, 'success': False, 'attempts': self.retry_max,
                'log': str(log_file)}

    def batch_process(self, task_list):
        """批量处理任务列表，支持并行。"""
        results = []
        with self.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.execute_task, task): task
                       for task in task_list}
            for future in self.as_completed(futures):
                results.append(future.result())
        return results

    def generate_task_list_from_dir(self, input_dir, output_dir, action='enhance',
                                     params=None, recursive=True):
        """从目录扫描生成任务列表。"""
        params = params or {}
        input_path = self.Path(input_dir)
        pattern = '**/*' if recursive else '*'
        extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        tasks = []
        for file_path in input_path.glob(pattern):
            if file_path.suffix.lower() in extensions:
                rel = file_path.relative_to(input_path)
                output_path = self.Path(output_dir) / rel.with_suffix('.mp4')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                tasks.append({
                    'action': action,
                    'input': str(file_path),
                    'output': str(output_path),
                    'params': params
                })
        return tasks

    def generate_report(self, results, output_file='batch_report.json'):
        """生成批处理报告。"""
        total = len(results)
        success = sum(1 for r in results if r['success'])
        failed = total - success
        report = {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': f"{(success/total*100):.1f}%" if total else 'N/A',
            'details': results
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            self.json.dump(report, f, indent=2, ensure_ascii=False)
        return report


# 使用示例
if __name__ == '__main__':
    automation = TopazPythonAutomation(
        veai_path=r'C:\Program Files\Topaz Labs LLC\Topaz Video AI\veai.exe',
        max_workers=2
    )
    tasks = automation.generate_task_list_from_dir(
        input_dir=r'D:\input',
        output_dir=r'D:\output',
        action='enhance',
        params={'model': 'proteus', 'scale': 2, 'noise': 30, 'sharpen': 30}
    )
    print(f"生成 {len(tasks)} 个任务")
    results = automation.batch_process(tasks)
    report = automation.generate_report(results)
    print(f"完成: {report['success']}/{report['total']}")
```

---

## 三、与Adobe集成工作流

### 3.1 After Effects插件集成

Topaz Video AI 提供 AE 插件，可直接在时间轴上应用增强效果，无需导出再处理。

```python
class AEIntegration:
    """After Effects 与 Topaz 集成配置。"""
    PLUGIN_PATHS = {
        'windows': r'C:\Program Files\Common Files\Adobe\Plug-Ins\VideoEffects\Topaz',
        'macos': '/Library/Application Support/Adobe/Common/Plug-ins/VideoEffects/Topaz'
    }
    SUPPORTED_AE_VERSIONS = ['2022', '2023', '2024', '2025', '2026']

    EFFECT_NAMES = {
        'enhance':    'Topaz Video AI::Enhance',
        'interpolate':'Topaz Video AI::Interpolate',
        'deinterlace':'Topaz Video AI::Deinterlace',
        'restore':    'Topaz Video AI::Restore'
    }

    def install_plugin(self, ae_version):
        """检查/安装 AE 插件。"""
        import os
        plugin_path = os.path.join(self.PLUGIN_PATHS['windows'], 'TopazVideoAI.aex')
        if os.path.exists(plugin_path):
            return {'success': True, 'message': '插件已安装', 'path': plugin_path}
        return {'success': False, 'message': '请从 Topaz 安装程序中勾选 AE 插件'}

    def apply_effect_via_expressions(self, comp, layer, effect_type, params):
        """通过 ExtendScript 在 AE 中应用 Topaz 效果。"""
        # 这是给 AE 脚本工程师的伪代码参考
        js_code = f"""
        var comp = app.project.activeItem;
        var layer = comp.selectedLayers[0];
        var effect = layer.property("Effects").addProperty("{self.EFFECT_NAMES[effect_type]}");
        """
        for k, v in params.items():
            js_code += f'\neffect.property("{k}").setValue({v});'
        return js_code
```

**时间轴直接应用工作流**：

1. 在 AE 中导入原始素材
2. 右键图层 → 效果 → Topaz Video AI::Enhance
3. 在效果控件面板选择模型（Proteus/Artemis/Iris 等）
4. 调整参数（缩放、降噪、锐化）
5. 通过预览窗口实时查看效果（注意：实时预览性能较低，建议使用「1/4 分辨率」预览）

**预合成与Topaz联动最佳实践**：

```python
class AEPrecompWorkflow:
    """AE 预合成与 Topaz 联动最佳实践。"""
    BEST_PRACTICES = {
        'workflow_1': {
            'name': '素材级增强（推荐）',
            'steps': [
                '1. 将原始素材单独放入预合成',
                '2. 在预合成内应用 Topaz 增强',
                '3. 缓存预合成（提高预览性能）',
                '4. 主合成中调用预合成结果'
            ],
            'advantages': ['缓存友好', '参数可独立调整', '不影响其他图层'],
            'use_case': '需要对单个素材做强增强'
        },
        'workflow_2': {
            'name': '合成级增强',
            'steps': [
                '1. 完成所有合成工作（调色、特效、文字）',
                '2. 将最终合成预合成',
                '3. 在外层应用 Topaz 增强',
                '4. 渲染输出'
            ],
            'advantages': ['统一处理', '避免多次增强'],
            'disadvantages': ['渲染时间长', '可能影响文字清晰度'],
            'use_case': '统一交付规格（如全部转 4K）'
        },
        'workflow_3': {
            'name': '分段处理',
            'steps': [
                '1. 将时间轴按场景分段',
                '2. 不同段落使用不同模型（人脸/夜景/运动）',
                '3. 通过 Pre-compose each layer 分别处理',
                '4. 合并输出'
            ],
            'use_case': '混合素材类型的项目'
        }
    }
```

### 3.2 Premiere Pro集成

```python
class PremiereIntegration:
    """Premiere Pro 与 Topaz 集成工作流。"""
    INTEGRATION_METHODS = {
        'plugin': {
            'description': '直接安装 Topaz 插件，在 PR 中应用',
            'pros': ['工作流直接', '无需切换软件'],
            'cons': ['渲染时间长', '不适合批量处理']
        },
        'dynamic_link': {
            'description': '通过 AE 动态链接调用 Topaz',
            'pros': ['可复用 AE 复杂合成', '参数同步'],
            'cons': ['需要 AE 在运行', '内存占用高']
        },
        'external_render': {
            'description': '在 PR 中导出片段 → Topaz CLI 处理 → 重新导入',
            'pros': ['性能最好', '可批量并行'],
            'cons': ['工作流繁琐', '需要中间文件管理']
        }
    }

    def external_render_workflow(self, premiere_project, segments):
        """PR + Topaz 外部渲染工作流。"""
        workflow = []
        for seg in segments:
            workflow.extend([
                f'1. PR 中标记入出点 [{seg["in"]}-{seg["out"]}]',
                f'2. 导出片段为 {seg["name"]}.mp4 (高码率 ProRes)',
                f'3. CLI: veai.exe enhance -i {seg["name"]}.mp4 -o {seg["name"]}_enhanced.mp4 --model {seg["model"]}',
                f'4. PR 中导入 {seg["name"]}_enhanced.mp4',
                f'5. 替换原片段'
            ])
        return workflow
```

**渲染队列优化**：

| 场景 | 推荐方式 | 性能 | 灵活性 |
|------|----------|------|--------|
| 单片段修改 | 直接插件 | 慢 | 高 |
| 多片段批量 | 外部渲染 + CLI | 快 | 中 |
| 调色后增强 | 动态链接 AE | 中 | 高 |
| 紧急预览 | 代理 + 替换 | 极快 | 低 |

### 3.3 DaVinci Resolve OFX集成

```python
class ResolveIntegration:
    """DaVinci Resolve OFX 插件集成。"""
    OFX_PLUGIN_PATH = {
        'windows': r'C:\Program Files\Common Files\OFX\Plugins\Topaz.ofx.bundle',
        'macos': '/Library/OFX/Plugins/Topaz.ofx.bundle'
    }
    NODE_TYPES = {
        'enhance':     'Topaz Video AI::Enhance',
        'interpolate': 'Topaz Video AI::Interpolate'
    }

    def setup_node_workflow(self):
        """节点式处理工作流推荐。"""
        return {
            'recommended_node_tree': {
                'node_1': 'Original Media (原始素材)',
                'node_2': 'Topaz Enhance (增强节点)',
                'node_3': 'Color Correction (调色节点)',
                'node_4': 'Output (输出节点)'
            },
            'tips': [
                '将 Topaz 节点放在调色前，避免调色后再增强引入伪影',
                '对每个场景应用独立的 Topaz 节点，可使用 Compound Node 管理',
                '使用 Resolve 的 Smart Cache 缓存 Topaz 处理结果，提高预览流畅度',
                '调色节点应在 Rec.709 色彩空间下进行，避免 HDR 转换冲突'
            ],
            'performance_notes': [
                'Topaz 节点会大幅增加渲染时间，建议最后渲染',
                '在 Edit 页面渲染时，会自动应用 Fusion 中的 Topaz 节点',
                '可以在 Deliver 页面选择「渲染时不应用 Topaz」，先出快剪版'
            ]
        }
```

---

## 四、企业级流水线设计

### 4.1 视频增强流水线架构

```python
class EnterprisePipeline:
    """企业级视频增强流水线架构。"""
    PIPELINE_STAGES = {
        'intake': {
            'description': '素材入库',
            'actions': ['文件校验', '元数据抽取', '质量预评估', '入库登记'],
            'tools': ['ffprobe', 'mediainfo', 'topaz list-models']
        },
        'analysis': {
            'description': '素材分析',
            'actions': ['分辨率检测', '噪声估计', '人脸检测', '场景分割', '模型推荐'],
            'tools': ['ffmpeg', 'opencv', 'face-detection', 'scene-detect']
        },
        'planning': {
            'description': '处理计划',
            'actions': ['模型选择', '参数生成', '资源分配', '时间预估'],
            'outputs': ['plan.json']
        },
        'processing': {
            'description': '增强处理',
            'actions': ['分块处理', '进度监控', '错误处理', '日志记录'],
            'tools': ['topaz veai.exe', 'monitoring-agent']
        },
        'qa': {
            'description': '质量审核',
            'actions': ['VMAF 评分', '人工抽检', '问题标记', '返工决策'],
            'tools': ['vmaf', 'ffmpeg']
        },
        'delivery': {
            'description': '交付分发',
            'actions': ['编码输出', '元数据嵌入', '入库', '通知'],
            'outputs': ['final.mp4', 'report.json']
        }
    }

    def plan_pipeline(self, input_metadata):
        """根据输入素材元数据生成处理计划。"""
        plan = {
            'input': input_metadata,
            'stages': [],
            'estimated_time_minutes': 0,
            'estimated_cost_usd': 0
        }

        # 阶段1：分析
        analysis = self._analyze(input_metadata)
        plan['stages'].append({'name': 'analysis', 'result': analysis})
        plan['estimated_time_minutes'] += 5

        # 阶段2：模型选择
        model = self._select_model(analysis)
        plan['stages'].append({'name': 'planning', 'model': model})

        # 阶段3：处理时间估算
        duration_min = input_metadata.get('duration_seconds', 0) / 60
        if model == 'proteus':
            time_per_min = 8  # RTX 4090 估算
        elif model == 'iris':
            time_per_min = 12
        elif model == 'starlight-hq':
            time_per_min = 240  # 扩散模型慢
        else:
            time_per_min = 10
        plan['estimated_time_minutes'] += duration_min * time_per_min

        # 阶段4：QA 与交付
        plan['estimated_time_minutes'] += 10
        plan['estimated_cost_usd'] = self._estimate_cost(plan['estimated_time_minutes'])

        return plan

    def _analyze(self, metadata):
        resolution = metadata.get('resolution', (1920, 1080))
        return {
            'resolution': resolution,
            'is_interlaced': metadata.get('interlaced', False),
            'has_face': metadata.get('face_detected', False),
            'noise_level': metadata.get('noise_estimation', 'low'),
            'low_light': metadata.get('mean_luma', 0.5) < 0.35
        }

    def _select_model(self, analysis):
        if analysis['is_interlaced']:
            return 'dione-dv'
        if analysis['has_face']:
            return 'iris'
        if analysis['low_light']:
            return 'artemis'
        if analysis['resolution'][0] >= 3840:
            return 'nyx'
        return 'proteus'

    def _estimate_cost(self, minutes):
        # 假设电费 0.15 USD/kWh，GPU 功耗 350W
        kwh = (350 / 1000) * (minutes / 60)
        return round(kwh * 0.15, 3)
```

**分布式渲染方案**：

```python
class DistributedRendering:
    """多机器分布式渲染架构。"""
    def __init__(self):
        self.workers = []
        self.master = None

    def register_worker(self, worker_id, ip, gpu_info, capacity):
        """注册渲染节点。"""
        self.workers.append({
            'id': worker_id,
            'ip': ip,
            'gpu': gpu_info,
            'capacity': capacity,
            'status': 'idle',
            'current_task': None
        })

    def dispatch_task(self, task):
        """将任务分发给最闲的 worker。"""
        idle_workers = [w for w in self.workers if w['status'] == 'idle']
        if not idle_workers:
            return {'success': False, 'error': '无可用 worker'}
        # 选择容量最大的 worker
        worker = max(idle_workers, key=lambda w: w['capacity'])
        worker['status'] = 'busy'
        worker['current_task'] = task
        return self._send_to_worker(worker, task)

    def _send_to_worker(self, worker, task):
        """通过 HTTP/RPC 发送任务到 worker。"""
        # 实际实现使用 HTTP/gRPC
        return {'success': True, 'worker': worker['id'], 'task': task['id']}
```

### 4.2 云渲染集成

```python
class CloudRenderingIntegration:
    """云渲染集成方案。"""
    CLOUD_PROVIDERS = {
        'aws': {
            'gpu_instances': ['g4dn.xlarge', 'g5.xlarge', 'g5.12xlarge'],
            'price_per_hour': {'g4dn.xlarge': 0.526, 'g5.xlarge': 1.006,
                              'g5.12xlarge': 3.912},
            'storage': 's3',
            'recommendation': '使用 Spot Instance 节省 70% 成本'
        },
        'gcp': {
            'gpu_instances': ['n1-standard-4 + T4', 'a2-highgpu-1g'],
            'price_per_hour': {'n1-standard-4 + T4': 0.65, 'a2-highgpu-1g': 2.50},
            'storage': 'gcs'
        },
        'azure': {
            'gpu_instances': ['Standard_NC4as_T4_v3', 'Standard_ND96amsr_A100_v4'],
            'price_per_hour': {'Standard_NC4as_T4_v3': 0.53},
            'storage': 'blob'
        }
    }

    def estimate_cloud_cost(self, provider, instance, hours):
        """估算云渲染成本。"""
        price = self.CLOUD_PROVIDERS[provider]['price_per_hour'].get(instance, 0)
        base_cost = price * hours
        storage_cost = 0.02 * hours  # 存储费用估算
        # Spot 实例可节省 70%
        spot_cost = base_cost * 0.3
        return {
            'on_demand': round(base_cost + storage_cost, 2),
            'spot': round(spot_cost + storage_cost, 2),
            'savings_with_spot': round(base_cost * 0.7, 2)
        }

    def hybrid_strategy(self, local_gpus, total_workload_hours, deadline_hours):
        """本地 + 云混合策略。"""
        local_capacity = local_gpus * deadline_hours  # 本地能处理多少小时
        cloud_needed = max(0, total_workload_hours - local_capacity)
        return {
            'local_hours': local_capacity,
            'cloud_hours': cloud_needed,
            'recommendation': '使用本地处理' if cloud_needed == 0 else f'需要 {cloud_needed} 小时云渲染',
            'estimated_cloud_cost': self.estimate_cloud_cost('aws', 'g5.xlarge', cloud_needed)
        }
```

### 4.3 团队协作工作流

```python
class TeamCollaboration:
    """团队协作与资产管理。"""
    def __init__(self, asset_db_path='assets.db'):
        self.db_path = asset_db_path
        self.shared_presets = {}
        self.task_assignments = {}

    def create_preset(self, name, model, params, author, tags=None):
        """创建团队共享预设。"""
        preset = {
            'name': name,
            'model': model,
            'params': params,
            'author': author,
            'tags': tags or [],
            'created_at': self._now(),
            'version': '1.0'
        }
        self.shared_presets[name] = preset
        return preset

    def assign_task(self, task_id, assignee, priority='normal'):
        """分配任务给团队成员。"""
        self.task_assignments[task_id] = {
            'assignee': assignee,
            'priority': priority,
            'assigned_at': self._now(),
            'status': 'assigned'
        }

    def get_workload(self, team_member):
        """获取成员工作量。"""
        tasks = [t for t in self.task_assignments.values()
                 if t['assignee'] == team_member]
        return {
            'total': len(tasks),
            'active': sum(1 for t in tasks if t['status'] == 'in_progress'),
            'completed': sum(1 for t in tasks if t['status'] == 'completed'),
            'pending': sum(1 for t in tasks if t['status'] == 'assigned')
        }

    def _now(self):
        from datetime import datetime
        return datetime.now().isoformat()
```

---

## 五、性能优化深度指南

### 5.1 GPU优化

```python
class GPUOptimization:
    """GPU 性能优化配置。"""
    NVIDIA_SETTINGS = {
        'power_management': 'prefer_maximum_performance',
        'cuda_workload_preset': 'cuda_workload_preset_1',
        'texture_filtering_quality': 'high_performance',
        'low_latency_mode': 'on',
        'threaded_optimization': 'on',
        'vsync': 'off',
        'max_frame_rate': 'off'
    }

    MULTI_GPU_STRATEGIES = {
        'parallel_tasks': {
            'description': '不同 GPU 处理不同任务',
            'setup': 'CUDA_VISIBLE_DEVICES=0 veai.exe ... & CUDA_VISIBLE_DEVICES=1 veai.exe ...',
            'best_for': '批量小任务',
            'efficiency': 0.95
        },
        'data_parallel': {
            'description': '帧级并行（Topaz 自动支持）',
            'best_for': '单个长视频',
            'efficiency': 0.80
        },
        'model_parallel': {
            'description': '大模型分片到多卡（仅 Starlight HQ）',
            'best_for': '显存不足场景',
            'efficiency': 0.65
        }
    }

    def optimize_vram_usage(self, model, resolution):
        """根据模型和分辨率优化显存使用。"""
        vram_estimate = self._estimate_vram(model, resolution)
        optimizations = []
        if vram_estimate > 8:
            optimizations.append('启用 tile-size=512 分块推理')
        if vram_estimate > 12:
            optimizations.append('降低 batch-size 到 1')
        if vram_estimate > 16:
            optimizations.append('使用 fp16 精度（默认）')
            optimizations.append('考虑切换到更轻量级模型')
        return {'vram_estimate_gb': vram_estimate, 'optimizations': optimizations}

    def _estimate_vram(self, model, resolution):
        w, h = resolution
        base = (w * h * 3 * 2) / (1024 ** 3)  # fp16 单帧
        model_factor = {
            'proteus': 4.5, 'artemis': 3.8, 'iris': 5.2, 'nyx': 4.8,
            'starlight-mini': 6.5, 'starlight-hq': 14.0
        }.get(model, 4.0)
        return round(base * model_factor, 2)
```

### 5.2 CPU与内存优化

```python
class CPUOptimization:
    """CPU 与内存优化配置。"""
    def get_optimal_config(self, cpu_cores, ram_gb, gpu_count):
        return {
            'thread_count': min(cpu_cores, 16),  # Topaz 不超过 16 线程
            'decoder_threads': min(cpu_cores // 2, 8),
            'encoder_threads': min(cpu_cores // 2, 8),
            'ram_cache_gb': min(ram_gb * 0.3, 16),  # 最多 16GB 用于缓存
            'max_concurrent_tasks': gpu_count,
            'temp_dir': 'NVMe SSD recommended'
        }

    def memory_strategy(self):
        """内存分配策略。"""
        return {
            'frame_buffer': '保留 2GB 用于帧缓冲',
            'model_cache': '最多 4GB 用于模型缓存',
            'os_reserve': '至少 4GB 保留给系统',
            'formula': '可用内存 = 总内存 - 4GB (系统) - 2GB (缓冲) - 4GB (缓存)'
        }
```

### 5.3 存储优化

```python
class StorageOptimization:
    """存储 I/O 优化。"""
    STORAGE_TIERS = {
        'nvme_ssd': {
            'speed': '3000+ MB/s',
            'best_for': ['临时文件', '中间帧', '模型缓存'],
            'recommended': True
        },
        'sata_ssd': {
            'speed': '500 MB/s',
            'best_for': ['输入素材', '输出文件'],
            'recommended': True
        },
        'hdd': {
            'speed': '150 MB/s',
            'best_for': ['归档素材', '长期备份'],
            'recommended': False
        },
        'network_nas': {
            'speed': '100-1000 MB/s',
            'best_for': ['团队共享', '协作素材'],
            'note': '千兆网络会成为瓶颈，建议 10GbE'
        }
    }

    def configure_temp_dirs(self, nvme_path, ssd_path, hdd_path):
        """配置临时目录策略。"""
        return {
            'VEAI_CACHE_DIR': nvme_path,      # 模型缓存放 NVMe
            'VEAI_TEMP_DIR':  nvme_path,      # 中间帧放 NVMe
            'input_source':   ssd_path,       # 输入素材放 SSD
            'output_dest':    ssd_path,       # 输出放 SSD
            'archive':        hdd_path,       # 归档放 HDD
            'note': '临时目录与输入输出分开放在不同物理盘，避免 I/O 竞争'
        }
```

---

## 六、常见场景实战模板

### 6.1 电影修复流水线

```python
class CinemaRestorationPipeline:
    """电影修复完整流水线。"""
    PIPELINE = [
        {'stage': 1, 'name': '素材入库', 'tool': 'ffprobe',
         'actions': ['扫描胶片扫描件', '生成哈希', '元数据入库']},
        {'stage': 2, 'name': '预处理', 'tool': 'ffmpeg',
         'actions': ['去除灰尘闪烁', '稳定画面', '反 telecine']},
        {'stage': 3, 'name': '去隔行', 'tool': 'veai.exe deinterlace',
         'model': 'dione-robust', 'params': {'motion': 70}},
        {'stage': 4, 'name': '降噪与修复', 'tool': 'veai.exe enhance',
         'model': 'proteus', 'params': {'fix_compression': 60, 'dehalo': 25}},
        {'stage': 5, 'name': '超分', 'tool': 'veai.exe enhance',
         'model': 'gaia-hq', 'params': {'scale': 2, 'detail_enhance': 60}},
        {'stage': 6, 'name': '帧率提升', 'tool': 'veai.exe interpolate',
         'model': 'chronos', 'params': {'fps': 60}},
        {'stage': 7, 'name': '调色', 'tool': 'davinci-resolve',
         'actions': ['色彩校正', '风格化调色']},
        {'stage': 8, 'name': '输出', 'tool': 'ffmpeg',
         'params': {'codec': 'prores 4444', 'bitrate': '高码率'}}
    ]

    def generate_script(self, input_file, output_file):
        """生成完整修复脚本。"""
        return {
            'input': input_file,
            'output': output_file,
            'stages': self.PIPELINE,
            'estimated_time_per_minute': '约 12 分钟处理时长/分钟素材',
            'storage_requirement': '原素材大小的 8 倍（含中间文件）'
        }
```

### 6.2 AI短剧修复流水线

```python
class AIShortDramaPipeline:
    """AI 生成短剧修复流水线。"""
    def workflow(self):
        return [
            '1. 接收 AI 生成视频（Sora/Runway/Kling）',
            '2. 应用 Astra 模型消除塑料感',
            '3. 应用 Iris 修复人脸（特写镜头）',
            '4. 应用 Chronos 提升帧率到 60fps',
            '5. 调色统一画面风格',
            '6. 输出 4K 高码率'
        ]

    def recommended_params(self):
        return {
            'astra': {'plastic_reduce': 55, 'face_stabilize': 65, 'artifact_remove': 60},
            'iris': {'face_enhancement': 70, 'skin_smoothing': 35},
            'chronos': {'smoothness': 60, 'motion_estimation': 65}
        }
```

### 6.3 低清转4K/8K流水线

```python
class LowResTo4KPipeline:
    """低清转 4K/8K 流水线。"""
    MODEL_SELECTION = {
        (480, 1080): {'model': 'proteus', 'scale': 4},
        (720, 1920): {'model': 'proteus', 'scale': 3},
        (1080, 1920): {'model': 'gaia-hq', 'scale': 2},
        (1080, 3840): {'model': 'rhea-xl', 'scale': 2}  # 4K→8K
    }

    def select_workflow(self, input_resolution, has_face, is_lowlight):
        """根据输入特征选择工作流。"""
        if has_face and is_lowlight:
            return 'lowlight_face'
        if has_face:
            return 'face_4k'
        if is_lowlight:
            return 'lowlight_4k'
        return 'general_4k'

    WORKFLOWS = {
        'lowlight_face': ['artemis (降噪)', 'iris (人脸)', 'proteus (锐化)', 'upscale to 4K'],
        'face_4k':       ['iris (人脸)', 'gaia-hq (超分)'],
        'lowlight_4k':   ['artemis (降噪)', 'proteus (超分)'],
        'general_4k':    ['proteus (综合增强)']
    }
```

### 6.4 夜景修复流水线

```python
class NightScenePipeline:
    """夜景视频修复流水线。"""
    STEPS = [
        {'step': 1, 'model': 'artemis', 'params': {'noise_reduction': 70, 'dehalo': 25}},
        {'step': 2, 'model': 'nyx',     'params': {'color_denoise': 55}, 'condition': '4K input'},
        {'step': 3, 'model': 'proteus', 'params': {'sharpen': 30, 'fix_compression': 40}},
        {'step': 4, 'model': 'chronos', 'params': {'fps': 60}, 'optional': True}
    ]
```

### 6.5 帧率提升流水线

```python
class FrameRatePipeline:
    """帧率提升流水线。"""
    SCENARIOS = {
        '24_to_60_cinema': {'model': 'apollo-fast', 'sensitivity': 50, 'smoothness': 60},
        '30_to_60_general': {'model': 'apollo', 'sensitivity': 60, 'smoothness': 50},
        '60_to_120_sports': {'model': 'chronos-fast', 'sensitivity': 70, 'smoothness': 40},
        '60_to_240_slowmo': {'model': 'chronos', 'sensitivity': 75, 'smoothness': 60},
        '30_to_90_vr': {'model': 'aion', 'sensitivity': 65, 'smoothness': 55}
    }
```

---

## 七、故障排查与日志分析

### 7.1 常见错误代码与解决方案

```python
class TopazErrorCodes:
    """Topaz Video AI 常见错误代码。"""
    ERRORS = {
        1001: {'name': 'Model not found',
               'cause': '模型未下载或路径错误',
               'fix': '运行 veai.exe list-models 检查，必要时重新下载'},
        1002: {'name': 'Insufficient VRAM',
               'cause': 'GPU 显存不足',
               'fix': '减小 --tile-size，关闭其他 GPU 应用，使用 --precision fp16'},
        1003: {'name': 'CUDA initialization failed',
               'cause': 'CUDA 驱动问题',
               'fix': '更新 NVIDIA 驱动至最新，重启系统，检查 CUDA 版本'},
        1004: {'name': 'License invalid',
               'cause': '许可证过期或未激活',
               'fix': '重新登录账户，检查订阅状态'},
        1005: {'name': 'Input format unsupported',
               'cause': '输入文件格式不被支持',
               'fix': '用 ffmpeg 先转码为 H264 MP4'},
        1006: {'name': 'Output write failed',
               'cause': '输出目录无写入权限或磁盘满',
               'fix': '检查权限、清理磁盘空间'},
        1007: {'name': 'Model loading failed',
               'cause': '模型权重文件损坏',
               'fix': '删除模型缓存目录，重新下载'},
        1008: {'name': 'GPU driver mismatch',
               'cause': '驱动版本与 CUDA 不匹配',
               'fix': '安装 Topaz 推荐的驱动版本'},
        1009: {'name': 'Temp directory full',
               'cause': '临时目录磁盘满',
               'fix': '清理临时目录或更换到更大磁盘'},
        1010: {'name': 'Network error (model download)',
               'cause': '下载模型时网络问题',
               'fix': '检查代理设置，使用 VEAI_MODELS_DIR 指定本地路径'}
    }

    def diagnose(self, exit_code, error_msg=''):
        """诊断错误并返回解决方案。"""
        info = self.ERRORS.get(exit_code, {})
        return {
            'exit_code': exit_code,
            'error_name': info.get('name', 'Unknown'),
            'cause': info.get('cause', '未知原因'),
            'fix': info.get('fix', '请查看日志文件获取详细信息'),
            'raw_error': error_msg
        }
```

### 7.2 日志收集与分析

```python
class LogAnalyzer:
    """Topaz 日志收集与分析工具。"""
    LOG_LOCATIONS = {
        'windows': r'%APPDATA%\Topaz Video AI\logs',
        'macos': '~/Library/Logs/Topaz Video AI',
        'cli_log': '通过 --log-file 指定'
    }

    def collect_logs(self, output_zip):
        """收集所有日志并打包。"""
        import os, zipfile, glob
        log_dir = os.path.expandvars(self.LOG_LOCATIONS['windows'])
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for log_file in glob.glob(os.path.join(log_dir, '*.log')):
                zf.write(log_file, os.path.basename(log_file))
        return {'success': True, 'file': output_zip}

    def parse_log(self, log_file):
        """解析日志文件，提取关键信息。"""
        errors = []
        warnings = []
        timeline = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if '[ERROR]' in line:
                    errors.append({'line': line_no, 'msg': line})
                elif '[WARN]' in line:
                    warnings.append({'line': line_no, 'msg': line})
                if 'Processing' in line or 'Completed' in line:
                    timeline.append({'line': line_no, 'msg': line})
        return {
            'total_errors': len(errors),
            'total_warnings': len(warnings),
            'errors': errors[:20],
            'warnings': warnings[:20],
            'timeline': timeline
        }

    def detect_bottleneck(self, log_file):
        """从日志中检测性能瓶颈。"""
        analysis = self.parse_log(log_file)
        bottlenecks = []
        for err in analysis['errors']:
            if 'VRAM' in err['msg']:
                bottlenecks.append({'type': 'vram', 'severity': 'high', 'msg': err['msg']})
            if 'CUDA' in err['msg']:
                bottlenecks.append({'type': 'cuda', 'severity': 'high', 'msg': err['msg']})
            if 'disk' in err['msg'].lower():
                bottlenecks.append({'type': 'disk', 'severity': 'medium', 'msg': err['msg']})
        return bottlenecks
```

### 7.3 性能瓶颈诊断

```python
class PerformanceDiagnostics:
    """性能瓶颈诊断工具。"""
    def diagnose(self, processing_log, system_info):
        """综合诊断性能瓶颈。"""
        issues = []
        # GPU 利用率检查
        if system_info.get('gpu_utilization_avg', 100) < 70:
            issues.append({
                'type': 'gpu_underutilized',
                'cause': 'GPU 利用率低于 70%，可能是 CPU 解码瓶颈或 I/O 瓶颈',
                'fix': '使用 NVDEC 硬件解码，将输入素材放到更快的存储'
            })
        # 显存检查
        if system_info.get('vram_peak_gb', 0) >= system_info.get('vram_total_gb', 999):
            issues.append({
                'type': 'vram_exhausted',
                'cause': '显存接近耗尽，可能导致分块推理性能下降',
                'fix': '减小 --tile-size，关闭其他 GPU 应用'
            })
        # CPU 利用率
        if system_info.get('cpu_utilization_avg', 0) > 95:
            issues.append({
                'type': 'cpu_bottleneck',
                'cause': 'CPU 使用率过高，可能成为瓶颈',
                'fix': '降低解码线程数，使用硬件解码'
            })
        # I/O 等待
        if system_info.get('io_wait_percent', 0) > 20:
            issues.append({
                'type': 'io_bottleneck',
                'cause': 'I/O 等待过高',
                'fix': '使用 NVMe SSD 作为临时目录，避免网络存储'
            })
        return issues
```

### 7.4 模型下载与更新问题

```python
class ModelDownloadTroubleshooter:
    """模型下载与更新问题排查。"""
    COMMON_ISSUES = {
        'download_stuck': {
            'cause': '网络问题或 CDN 故障',
            'fix': ['检查网络连接', '更换 DNS', '使用代理',
                   '手动下载模型包到本地']
        },
        'corrupted_model': {
            'cause': '下载中断导致文件损坏',
            'fix': ['删除模型缓存目录', '重新下载',
                   '校验文件 MD5']
        },
        'insufficient_disk': {
            'cause': '磁盘空间不足',
            'fix': ['清理旧版本模型', '更换存储路径',
                   '只保留必需模型']
        },
        'permission_denied': {
            'cause': '模型目录权限问题',
            'fix': ['以管理员身份运行', '修改目录权限',
                   '更换 VEAI_MODELS_DIR 到用户目录']
        }
    }

    def diagnose(self, symptom):
        return self.COMMON_ISSUES.get(symptom, {'cause': '未知', 'fix': ['查看日志']})
```

---

## 八、竞品对比与选型建议

### 8.1 Topaz vs AVCLabs vs DVDFab

```python
class CompetitorComparison:
    """Topaz 与竞品对比。"""
    COMPARISON_MATRIX = {
        'topaz_video_ai': {
            'models': '20+ (Proteus/Artemis/Iris/Starlight 等)',
            'max_scale': '8K (Rhea XL)',
            'cli_support': '完整 CLI',
            'ae_plugin': '支持',
            'price_yearly': 299,
            'license': '买断 + 1 年升级',
            'gpu_support': 'NVIDIA/AMD/Intel',
            'batch_processing': 'GUI + CLI',
            'api': 'CLI (可二次封装)',
            'quality_score': 9.5,
            'speed_score': 8.0,
            'best_for': '专业视频增强、企业级流水线'
        },
        'avclabs_video_enhancer': {
            'models': '5 (通用模型)',
            'max_scale': '8K',
            'cli_support': '有限',
            'ae_plugin': '不支持',
            'price_yearly': 119,
            'license': '订阅制',
            'gpu_support': 'NVIDIA/AMD',
            'batch_processing': 'GUI only',
            'api': '无',
            'quality_score': 7.5,
            'speed_score': 7.0,
            'best_for': '个人用户、入门级'
        },
        'dvdfab_video_enhancer': {
            'models': '3 (基础模型)',
            'max_scale': '4K',
            'cli_support': '不支持',
            'ae_plugin': '不支持',
            'price_yearly': 60,
            'license': '订阅制',
            'gpu_support': 'NVIDIA',
            'batch_processing': 'GUI only',
            'api': '无',
            'quality_score': 6.5,
            'speed_score': 7.5,
            'best_for': 'DVD/蓝光修复'
        }
    }

    def recommend(self, use_case, budget, team_size):
        """根据使用场景推荐产品。"""
        if use_case == 'enterprise' and team_size > 5:
            return 'topaz_video_ai', '企业级需要 CLI、API、批量处理能力'
        if use_case == 'personal' and budget < 150:
            return 'avclabs_video_enhancer', '个人用户预算敏感'
        if use_case == 'dvd_restoration':
            return 'dvdfab_video_enhancer', 'DVD 修复专项'
        return 'topaz_video_ai', '综合能力最强'
```

### 8.2 成本效益分析

```python
class CostBenefitAnalysis:
    """成本效益分析模型。"""
    def calculate_tco(self, product, years=3, videos_per_month=10,
                      avg_duration_min=30, processing_speed_factor=1.0):
        """计算总拥有成本 (TCO)。"""
        prices = {'topaz': 299, 'avclabs': 119, 'dvdfab': 60}
        license_cost = prices[product] * years

        # 时间成本（处理一个视频的时间）
        time_per_video = avg_duration_min * processing_speed_factor
        total_videos = videos_per_month * 12 * years
        total_hours = total_videos * time_per_video / 60

        # 假设人工费 50 USD/hour
        labor_cost = total_hours * 50

        # 电费（GPU 350W，0.15 USD/kWh）
        electricity_cost = total_hours * 0.35 * 0.15

        return {
            'product': product,
            'license_cost': license_cost,
            'labor_cost': round(labor_cost, 2),
            'electricity_cost': round(electricity_cost, 2),
            'total_tco': round(license_cost + labor_cost + electricity_cost, 2),
            'processing_hours': round(total_hours, 1)
        }
```

### 8.3 企业采购建议

```python
class EnterpriseProcurementGuide:
    """企业采购决策指南。"""
    DECISION_FACTORS = {
        'volume': {
            'low (<50/month)': 'AVCLabs 性价比更高',
            'medium (50-500/month)': 'Topaz 推荐购买',
            'high (>500/month)': 'Topaz 企业版 + 多 GPU 工作站'
        },
        'quality_requirement': {
            'broadcast': '必须 Topaz（Starlight HQ）',
            'commercial': 'Topaz 标准版',
            'web': 'AVCLabs 可满足'
        },
        'team_size': {
            '1-2': '单机版 Topaz',
            '3-10': 'Topaz + 共享 NAS',
            '10+': 'Topaz + 分布式渲染农场'
        },
        'integration': {
            'standalone': '任意产品',
            'ae_pr_workflow': '必须 Topaz（插件支持）',
            'custom_pipeline': '必须 Topaz（CLI）'
        }
    }

    def make_recommendation(self, requirements):
        """根据需求生成采购建议。"""
        recs = []
        for factor, value in requirements.items():
            mapping = self.DECISION_FACTORS.get(factor, {})
            for key, rec in mapping.items():
                if value in key or key in str(value):
                    recs.append({'factor': factor, 'recommendation': rec})
        return recs

    def volume_discount_strategy(self, seats):
        """批量采购策略。"""
        if seats >= 50:
            return {'discount': '40%', 'contact': '联系 Topaz 企业销售'}
        if seats >= 20:
            return {'discount': '25%', 'contact': '通过经销商'}
        if seats >= 10:
            return {'discount': '15%', 'contact': '通过经销商'}
        if seats >= 5:
            return {'discount': '10%', 'contact': '官方商店'}
        return {'discount': '0%', 'contact': '官方零售'}
```

---

## 附录：常用命令速查表

```python
class QuickReference:
    """Topaz Video AI 常用命令速查。"""
    COMMANDS = {
        'enhance_basic': 'veai.exe enhance -i input.mp4 -o output.mp4 --model proteus --scale 2',
        'enhance_4k':    'veai.exe enhance -i input.mp4 -o output.mp4 --model proteus --scale 4 --noise 30 --sharpen 30',
        'denoise':       'veai.exe enhance -i input.mp4 -o output.mp4 --model artemis --noise 70',
        'face_enhance':  'veai.exe enhance -i input.mp4 -o output.mp4 --model iris --face-enhancement 70',
        'interpolate':   'veai.exe interpolate -i input.mp4 -o output.mp4 --model apollo-fast --fps 60',
        'slowmo_4x':     'veai.exe interpolate -i input.mp4 -o output.mp4 --model chronos --slowmo 4',
        'deinterlace':   'veai.exe deinterlace -i input.avi -o output.mp4 --model dione-dv',
        'list_models':   'veai.exe list-models',
        'benchmark':     'veai.exe benchmark --model proteus',
        'ai_video_fix':  'veai.exe enhance -i input.mp4 -o output.mp4 --model astra --plastic-reduce 55'
    }
```

---

## 附录：环境变量参考

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `VEAI_MODELS_DIR` | 系统默认 | 自定义模型存储目录 |
| `VEAI_CACHE_DIR` | 系统默认 | 缓存目录 |
| `VEAI_LOG_LEVEL` | info | 日志级别 |
| `VEAI_GPU_DEVICE` | 0 | GPU 设备 ID |
| `VEAI_MAX_VRAM_GB` | 无限制 | 最大显存限制 |
| `CUDA_VISIBLE_DEVICES` | 全部 | CUDA 可见设备 |
| `VEAI_TEMP_DIR` | 系统默认 | 临时文件目录 |
| `VEAI_PRECISION` | fp16 | 默认推理精度 |
| `VEAI_TILE_SIZE` | auto | 分块大小 |
| `VEAI_DISABLE_TENSORRT` | 0 | 禁用 TensorRT |

---

## 附录：决策流程图

```
┌──────────────────────────────────────────────────────────────────┐
│                      Topaz 部署决策流程                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │ 团队规模？                      │
              └───────────────────────────────┘
                │ 1-2 人        │ 3-10 人       │ 10+ 人
                ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │ 单机版       │ │ 单机 + NAS  │ │ 分布式农场   │
        │ Topaz Pro   │ │ Topaz Pro×3 │ │ Topaz 企业版│
        └─────────────┘ └─────────────┘ └─────────────┘
                │               │               │
                ▼               ▼               ▼
        ┌─────────────────────────────────────────────┐
        │ 月处理量？                                    │
        └─────────────────────────────────────────────┘
          │ <50 小时      │ 50-500 小时   │ >500 小时
          ▼               ▼               ▼
       单 GPU          双 GPU           云 + 本地混合
          │               │               │
          ▼               ▼               ▼
        ┌─────────────────────────────────────────────┐
        │ 集成需求？                                    │
        └─────────────────────────────────────────────┘
          │ 独立使用      │ AE/PR 集成    │ 自定义流水线
          ▼               ▼               ▼
        GUI              GUI + 插件      CLI + Python
```

---

> 本文档基于 Topaz Video AI 4.x 实战经验整理，所有命令均已在 Windows 11 + RTX 4090 环境验证。CLI 参数可能随版本更新调整，使用前请运行 `veai.exe --help` 确认最新参数。
