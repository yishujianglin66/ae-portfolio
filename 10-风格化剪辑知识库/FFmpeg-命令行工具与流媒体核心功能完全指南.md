# FFmpeg 命令行工具与流媒体核心功能完全指南

---

## 一、FFmpeg基础操作

### 1.1 命令行架构

```python
class FFmpegCommandStructure:
    COMMAND_COMPONENTS = {
        'global_options': {'description': '全局选项', 'examples': ['-y', '-n', '-v', '-stats']},
        'input_files': {'description': '输入文件', 'examples': ['-i input.mp4']},
        'codec_options': {'description': '编解码器选项', 'examples': ['-c:v libx264', '-c:a aac']},
        'filter_options': {'description': '滤镜选项', 'examples': ['-vf scale=1920:1080']},
        'output_options': {'description': '输出选项', 'examples': ['-b:v 10M', '-r 24']},
        'output_files': {'description': '输出文件', 'examples': ['output.mp4']}
    }
    
    GLOBAL_OPTIONS = {
        '-y': {'description': '覆盖输出文件', 'type': 'flag'},
        '-n': {'description': '不覆盖输出文件', 'type': 'flag'},
        '-v': {'description': '日志级别', 'type': 'value', 'values': ['quiet', 'panic', 'fatal', 'error', 'warning', 'info', 'verbose', 'debug', 'trace']},
        '-stats': {'description': '打印编码统计信息', 'type': 'flag'},
        '-progress': {'description': '进度报告', 'type': 'value'},
        '-timelimit': {'description': '编码时间限制', 'type': 'value'}
    }
    
    def __init__(self):
        self.command = ['ffmpeg']
        self.global_options = []
        self.inputs = []
        self.outputs = []
        
    def add_global_option(self, option, value=None):
        if option not in self.GLOBAL_OPTIONS:
            return {'status': 'error', 'message': f'无效的全局选项: {option}'}
            
        if value:
            self.global_options.extend([option, str(value)])
        else:
            self.global_options.append(option)
            
        return {'status': 'success', 'options': self.global_options}
        
    def add_input(self, input_path, options=None):
        options = options or {}
        
        input_spec = ['-i', input_path]
        
        if 'stream_loop' in options:
            input_spec.extend(['-stream_loop', str(options['stream_loop'])])
        if 't' in options:
            input_spec.extend(['-t', str(options['t'])])
        if 'ss' in options:
            input_spec.extend(['-ss', str(options['ss'])])
        if 'framerate' in options:
            input_spec.extend(['-framerate', str(options['framerate'])])
        if 'codec' in options:
            input_spec.extend(['-c', options['codec']])
            
        self.inputs.append({'path': input_path, 'options': options})
        self.command.extend(input_spec)
        
        return {'status': 'success', 'inputs': self.inputs}
        
    def add_output(self, output_path, options=None):
        options = options or {}
        
        output_spec = [output_path]
        
        if 'c:v' in options:
            output_spec.extend(['-c:v', options['c:v']])
        if 'c:a' in options:
            output_spec.extend(['-c:a', options['c:a']])
        if 'b:v' in options:
            output_spec.extend(['-b:v', options['b:v']])
        if 'b:a' in options:
            output_spec.extend(['-b:a', options['b:a']])
        if 'r' in options:
            output_spec.extend(['-r', str(options['r'])])
        if 's' in options:
            output_spec.extend(['-s', options['s']])
        if 'pix_fmt' in options:
            output_spec.extend(['-pix_fmt', options['pix_fmt']])
        if 't' in options:
            output_spec.extend(['-t', str(options['t'])])
        if 'y' in options and options['y']:
            output_spec.append('-y')
        if 'vn' in options and options['vn']:
            output_spec.append('-vn')
        if 'an' in options and options['an']:
            output_spec.append('-an')
            
        self.outputs.append({'path': output_path, 'options': options})
        self.command.extend(output_spec)
        
        return {'status': 'success', 'outputs': self.outputs}
        
    def build(self):
        full_command = self.command.copy()
        full_command[1:1] = self.global_options
        return ' '.join(full_command)
```

### 1.2 媒体信息查询

```python
class MediaInfo:
    PROBE_COMMANDS = {
        'basic': {'description': '基本信息', 'command': 'ffprobe -v quiet -print_format json -show_format -show_streams'},
        'streams': {'description': '流信息', 'command': 'ffprobe -v quiet -print_format json -show_streams'},
        'format': {'description': '格式信息', 'command': 'ffprobe -v quiet -print_format json -show_format'},
        'packets': {'description': '数据包信息', 'command': 'ffprobe -v quiet -print_format json -show_packets'},
        'frames': {'description': '帧信息', 'command': 'ffprobe -v quiet -print_format json -show_frames'}
    }
    
    def __init__(self):
        self.info = {}
        
    def probe(self, file_path, probe_type='basic'):
        if probe_type not in self.PROBE_COMMANDS:
            return {'status': 'error', 'message': '无效的探测类型'}
            
        import subprocess
        import json
        
        command = f"{self.PROBE_COMMANDS[probe_type]['command']} {file_path}"
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            info = json.loads(result.stdout)
            self.info = info
            return {'status': 'success', 'info': info}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
            
    def get_video_info(self):
        streams = self.info.get('streams', [])
        video_streams = [s for s in streams if s.get('codec_type') == 'video']
        
        if video_streams:
            vs = video_streams[0]
            return {
                'codec': vs.get('codec_name'),
                'resolution': f"{vs.get('width')}x{vs.get('height')}",
                'fps': vs.get('r_frame_rate'),
                'duration': vs.get('duration'),
                'bitrate': vs.get('bit_rate')
            }
        return None
        
    def get_audio_info(self):
        streams = self.info.get('streams', [])
        audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
        
        if audio_streams:
            as_ = audio_streams[0]
            return {
                'codec': as_.get('codec_name'),
                'sample_rate': as_.get('sample_rate'),
                'channels': as_.get('channels'),
                'duration': as_.get('duration'),
                'bitrate': as_.get('bit_rate')
            }
        return None
```

---

## 二、视频编码解码

### 2.1 视频编码格式

```python
class VideoCodecManager:
    CODECS = {
        'h264': {
            'description': 'H.264/MPEG-4 AVC',
            'encoders': ['libx264', 'h264_nvenc', 'h264_qsv'],
            'decoders': ['h264'],
            'features': ['widely compatible', 'good compression', 'hardware support'],
            'presets': ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']
        },
        'h265': {
            'description': 'H.265/HEVC',
            'encoders': ['libx265', 'hevc_nvenc', 'hevc_qsv'],
            'decoders': ['hevc'],
            'features': ['better compression', '4K support', 'hardware support'],
            'presets': ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']
        },
        'av1': {
            'description': 'AV1',
            'encoders': ['libaom-av1', 'libsvtav1'],
            'decoders': ['av1'],
            'features': ['open source', 'best compression', 'slow encoding'],
            'presets': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        },
        'prores': {
            'description': 'Apple ProRes',
            'encoders': ['prores_ks', 'prores'],
            'decoders': ['prores'],
            'features': ['lossless', 'professional editing', 'large files'],
            'presets': ['proxy', 'lt', 'standard', 'hq', '4444', '4444xq']
        },
        'vp9': {
            'description': 'VP9',
            'encoders': ['libvpx-vp9'],
            'decoders': ['vp9'],
            'features': ['open source', 'web support', 'good quality'],
            'presets': ['0', '1', '2', '3', '4', '5', '6', '7']
        },
        'mpeg4': {
            'description': 'MPEG-4',
            'encoders': ['mpeg4'],
            'decoders': ['mpeg4'],
            'features': ['legacy compatibility', 'simple encoding'],
            'presets': []
        },
        'wmv': {
            'description': 'WMV',
            'encoders': ['wmv2'],
            'decoders': ['wmv2'],
            'features': ['Windows compatibility'],
            'presets': []
        }
    }
    
    def __init__(self):
        self.current_codec = 'h264'
        self.preset = 'medium'
        
    def set_codec(self, codec_name):
        if codec_name not in self.CODECS:
            return {'status': 'error', 'message': '无效的编码器'}
            
        self.current_codec = codec_name
        return {'status': 'success', 'codec': self.CODECS[codec_name]}
        
    def set_preset(self, preset):
        codec_info = self.CODECS.get(self.current_codec, {})
        presets = codec_info.get('presets', [])
        
        if presets and preset not in presets:
            return {'status': 'error', 'message': f'无效的预设，可用预设: {presets}'}
            
        self.preset = preset
        return {'status': 'success', 'preset': preset}
        
    def get_encode_options(self):
        codec_info = self.CODECS.get(self.current_codec, {})
        encoder = codec_info['encoders'][0]
        
        options = {
            '-c:v': encoder
        }
        
        if self.preset and codec_info.get('presets'):
            options['-preset'] = self.preset
            
        return {'status': 'success', 'options': options}
```

### 2.2 音频编码格式

```python
class AudioCodecManager:
    CODECS = {
        'aac': {
            'description': 'AAC',
            'encoders': ['aac'],
            'decoders': ['aac'],
            'features': ['standard for video', 'good quality', 'compatible'],
            'bitrates': ['64k', '96k', '128k', '192k', '256k', '320k']
        },
        'mp3': {
            'description': 'MP3',
            'encoders': ['libmp3lame'],
            'decoders': ['mp3'],
            'features': ['popular', 'lossy', 'good compatibility'],
            'bitrates': ['64k', '128k', '192k', '256k', '320k']
        },
        'opus': {
            'description': 'Opus',
            'encoders': ['libopus'],
            'decoders': ['opus'],
            'features': ['low latency', 'best quality', 'web standard'],
            'bitrates': ['64k', '96k', '128k', '192k']
        },
        'flac': {
            'description': 'FLAC',
            'encoders': ['flac'],
            'decoders': ['flac'],
            'features': ['lossless', 'open source', 'no patent'],
            'bitrates': []
        },
        'wav': {
            'description': 'WAV',
            'encoders': ['pcm_s16le', 'pcm_s24le', 'pcm_s32le'],
            'decoders': ['pcm_s16le', 'pcm_s24le', 'pcm_s32le'],
            'features': ['raw', 'lossless', 'high quality'],
            'bitrates': []
        },
        'ac3': {
            'description': 'AC3/Dolby Digital',
            'encoders': ['ac3'],
            'decoders': ['ac3'],
            'features': ['surround sound', 'home theater'],
            'bitrates': ['192k', '384k', '448k', '640k']
        },
        'eac3': {
            'description': 'E-AC3/Dolby Digital Plus',
            'encoders': ['eac3'],
            'decoders': ['eac3'],
            'features': ['better compression', 'Atmos support'],
            'bitrates': ['384k', '512k', '768k']
        }
    }
    
    def __init__(self):
        self.current_codec = 'aac'
        self.bitrate = '128k'
        
    def set_codec(self, codec_name):
        if codec_name not in self.CODECS:
            return {'status': 'error', 'message': '无效的编码器'}
            
        self.current_codec = codec_name
        return {'status': 'success', 'codec': self.CODECS[codec_name]}
        
    def set_bitrate(self, bitrate):
        codec_info = self.CODECS.get(self.current_codec, {})
        bitrates = codec_info.get('bitrates', [])
        
        if bitrates and bitrate not in bitrates:
            return {'status': 'error', 'message': f'无效的码率，可用码率: {bitrates}'}
            
        self.bitrate = bitrate
        return {'status': 'success', 'bitrate': bitrate}
        
    def get_encode_options(self):
        codec_info = self.CODECS.get(self.current_codec, {})
        encoder = codec_info['encoders'][0]
        
        options = {
            '-c:a': encoder
        }
        
        if self.bitrate and codec_info.get('bitrates'):
            options['-b:a'] = self.bitrate
            
        return {'status': 'success', 'options': options}
```

---

## 三、滤镜系统

### 3.1 视频滤镜

```python
class VideoFilterManager:
    FILTER_CATEGORIES = {
        'scale': {
            'description': '缩放',
            'syntax': 'scale=width:height',
            'examples': ['scale=1920:1080', 'scale=-1:720', 'scale=720:-1']
        },
        'crop': {
            'description': '裁剪',
            'syntax': 'crop=width:height:x:y',
            'examples': ['crop=1920:1080:0:0', 'crop=in_w-100:in_h-100']
        },
        'rotate': {
            'description': '旋转',
            'syntax': 'rotate=angle',
            'examples': ['rotate=PI/2', 'rotate=PI', 'rotate=-PI/2']
        },
        'transpose': {
            'description': '转置',
            'syntax': 'transpose=direction',
            'examples': ['transpose=0', 'transpose=1', 'transpose=2', 'transpose=3']
        },
        'flip': {
            'description': '水平翻转',
            'syntax': 'flip',
            'examples': ['flip']
        },
        'negate': {
            'description': '反色',
            'syntax': 'negate',
            'examples': ['negate']
        },
        'hue': {
            'description': '色调',
            'syntax': 'hue=h=value:s=value',
            'examples': ['hue=h=90', 'hue=s=0', 'hue=h=-90:s=1.5']
        },
        'saturation': {
            'description': '饱和度',
            'syntax': 'saturation=value',
            'examples': ['saturation=1.5', 'saturation=0', 'saturation=2.0']
        },
        'brightness': {
            'description': '亮度',
            'syntax': 'brightness=value',
            'examples': ['brightness=0.1', 'brightness=-0.1', 'brightness=0.2']
        },
        'contrast': {
            'description': '对比度',
            'syntax': 'contrast=value',
            'examples': ['contrast=1.2', 'contrast=0.8', 'contrast=1.5']
        },
        'blur': {
            'description': '模糊',
            'syntax': 'blur=radius:sigma',
            'examples': ['blur=5:2', 'blur=10:5']
        },
        'boxblur': {
            'description': '盒式模糊',
            'syntax': 'boxblur=lr:lc:cr:cc',
            'examples': ['boxblur=1:1:1:1', 'boxblur=5:5:5:5']
        },
        'gblur': {
            'description': '高斯模糊',
            'syntax': 'gblur=sigma',
            'examples': ['gblur=2', 'gblur=5']
        },
        'sharpness': {
            'description': '锐化',
            'syntax': 'sharpness=value',
            'examples': ['sharpness=1.5', 'sharpness=2.0']
        },
        'unsharp': {
            'description': 'USM锐化',
            'syntax': 'unsharp=luma_msize_x:luma_msize_y:luma_amount',
            'examples': ['unsharp=5:5:1.0', 'unsharp=3:3:0.5']
        },
        'overlay': {
            'description': '叠加',
            'syntax': 'overlay=x:y',
            'examples': ['overlay=10:10', 'overlay=main_w-overlay_w-10:main_h-overlay_h-10']
        },
        'drawtext': {
            'description': '绘制文字',
            'syntax': 'drawtext=text=string:fontfile=path:x=y:y=value',
            'examples': ['drawtext=text="Hello":fontfile=/path/to/font.ttf:x=10:y=10']
        },
        'fps': {
            'description': '帧率转换',
            'syntax': 'fps=fps=value',
            'examples': ['fps=fps=24', 'fps=fps=30', 'fps=fps=60']
        },
        'format': {
            'description': '像素格式转换',
            'syntax': 'format=pix_fmts=format',
            'examples': ['format=pix_fmts=yuv420p', 'format=pix_fmts=yuv444p']
        },
        'fade': {
            'description': '淡入淡出',
            'syntax': 'fade=t=type:st=start_time:d=duration',
            'examples': ['fade=t=in:st=0:d=2', 'fade=t=out:st=10:d=2']
        }
    }
    
    def __init__(self):
        self.filters = []
        
    def add_filter(self, filter_name, parameters=None):
        if filter_name not in self.FILTER_CATEGORIES:
            return {'status': 'error', 'message': '无效的滤镜'}
            
        filter_spec = filter_name
        
        if parameters:
            param_str = ':'.join([f'{k}={v}' for k, v in parameters.items()])
            filter_spec += f':{param_str}'
            
        self.filters.append(filter_spec)
        return {'status': 'success', 'filters': self.filters}
        
    def get_filter_string(self):
        if not self.filters:
            return ''
            
        return ','.join(self.filters)
        
    def clear_filters(self):
        self.filters = []
        return {'status': 'success'}
```

### 3.2 音频滤镜

```python
class AudioFilterManager:
    FILTER_CATEGORIES = {
        'volume': {
            'description': '音量',
            'syntax': 'volume=value',
            'examples': ['volume=2.0', 'volume=0.5', 'volume=1.5']
        },
        'equalizer': {
            'description': '均衡器',
            'syntax': 'equalizer=f=frequency:t=type:w=width:g=gain',
            'examples': ['equalizer=f=1000:t=q:w=1:g=5', 'equalizer=f=200:t=q:w=1:g=-3']
        },
        'highpass': {
            'description': '高通滤波',
            'syntax': 'highpass=f=frequency',
            'examples': ['highpass=f=200', 'highpass=f=500']
        },
        'lowpass': {
            'description': '低通滤波',
            'syntax': 'lowpass=f=frequency',
            'examples': ['lowpass=f=2000', 'lowpass=f=5000']
        },
        'bass': {
            'description': '低音增强',
            'syntax': 'bass=g=gain',
            'examples': ['bass=g=5', 'bass=g=3']
        },
        'treble': {
            'description': '高音增强',
            'syntax': 'treble=g=gain',
            'examples': ['treble=g=5', 'treble=g=3']
        },
        'compressor': {
            'description': '压缩器',
            'syntax': 'acompressor=threshold=value:ratio=value',
            'examples': ['acompressor=threshold=-20dB:ratio=4']
        },
        'reverb': {
            'description': '混响',
            'syntax': 'aecho=in_gain=value:out_gain=value:delay=value',
            'examples': ['aecho=in_gain=0.5:out_gain=0.3:delay=100']
        },
        'chorus': {
            'description': '合唱效果',
            'syntax': 'chorus=in_gain=value:out_gain=value',
            'examples': ['chorus=in_gain=0.4:out_gain=0.4']
        },
        'atempo': {
            'description': '音频速度',
            'syntax': 'atempo=value',
            'examples': ['atempo=1.5', 'atempo=0.5', 'atempo=2.0']
        },
        'aresample': {
            'description': '采样率转换',
            'syntax': 'aresample=rate=value',
            'examples': ['aresample=rate=44100', 'aresample=rate=48000']
        },
        'channelsplit': {
            'description': '声道分离',
            'syntax': 'channelsplit=channel_layout=layout',
            'examples': ['channelsplit=channel_layout=stereo']
        },
        'join': {
            'description': '声道合并',
            'syntax': 'join=inputs=count:channel_layout=layout',
            'examples': ['join=inputs=2:channel_layout=stereo']
        },
        'pan': {
            'description': '声像',
            'syntax': 'pan=channel_layout:channel_definition',
            'examples': ['pan=stereo:c0=c0+c1:c1=c0+c1']
        },
        'silencedetect': {
            'description': '静音检测',
            'syntax': 'silencedetect=n=noise:duration=time',
            'examples': ['silencedetect=n=-50dB:d=2']
        },
        'loudnorm': {
            'description': '响度归一化',
            'syntax': 'loudnorm=I=integrated:LRA=loudness_range:TP=true_peak',
            'examples': ['loudnorm=I=-16:LRA=11:TP=-1.5']
        }
    }
    
    def __init__(self):
        self.filters = []
        
    def add_filter(self, filter_name, parameters=None):
        if filter_name not in self.FILTER_CATEGORIES:
            return {'status': 'error', 'message': '无效的滤镜'}
            
        filter_spec = filter_name
        
        if parameters:
            param_str = ':'.join([f'{k}={v}' for k, v in parameters.items()])
            filter_spec += f':{param_str}'
            
        self.filters.append(filter_spec)
        return {'status': 'success', 'filters': self.filters}
        
    def get_filter_string(self):
        if not self.filters:
            return ''
            
        return ','.join(self.filters)
        
    def clear_filters(self):
        self.filters = []
        return {'status': 'success'}
```

---

## 四、流媒体传输

### 4.1 RTMP流媒体

```python
class RTMPStreaming:
    PROTOCOLS = {
        'rtmp': {'description': 'RTMP', 'port': 1935, 'features': ['low latency', 'Adobe standard']},
        'rtmps': {'description': 'RTMP over TLS', 'port': 443, 'features': ['encrypted', 'secure']},
        'rtmpt': {'description': 'RTMP over HTTP', 'port': 80, 'features': ['firewall friendly']},
        'rtmpte': {'description': 'RTMP encrypted', 'port': 1935, 'features': ['encrypted']}
    }
    
    def __init__(self):
        self.protocol = 'rtmp'
        self.server = 'localhost'
        self.port = 1935
        self.stream_key = 'live'
        
    def set_server(self, server):
        self.server = server
        return {'status': 'success', 'server': server}
        
    def set_stream_key(self, key):
        self.stream_key = key
        return {'status': 'success', 'stream_key': key}
        
    def get_stream_url(self):
        return f'{self.protocol}://{self.server}:{self.port}/{self.stream_key}'
        
    def create_push_command(self, input_file, video_bitrate='2500k', audio_bitrate='128k', fps=30):
        url = self.get_stream_url()
        
        command = f'''ffmpeg -re -i {input_file} \
            -c:v libx264 -b:v {video_bitrate} -preset veryfast -g {fps * 2} \
            -c:a aac -b:a {audio_bitrate} -ac 2 \
            -f flv {url}'''
            
        return {'status': 'success', 'command': command}
        
    def create_pull_command(self, output_file, duration=None):
        url = self.get_stream_url()
        
        command = f'ffmpeg -i {url}'
        
        if duration:
            command += f' -t {duration}'
            
        command += f' -c copy {output_file}'
            
        return {'status': 'success', 'command': command}
```

### 4.2 HLS流媒体

```python
class HLSStreaming:
    PROFILES = {
        'baseline': {'description': 'Baseline', 'level': '3.0', 'features': ['low complexity', 'mobile']},
        'main': {'description': 'Main', 'level': '3.1', 'features': ['standard', 'most devices']},
        'high': {'description': 'High', 'level': '4.0', 'features': ['high quality', 'advanced features']}
    }
    
    def __init__(self):
        self.segment_duration = 2
        self.list_size = 6
        self.hls_time = 2
        self.hls_list_size = 6
        self.hls_flags = []
        
    def set_segment_duration(self, seconds):
        self.segment_duration = seconds
        return {'status': 'success', 'segment_duration': seconds}
        
    def add_flag(self, flag):
        flags = ['delete_segments', 'append_list', 'omit_endlist', 'program_date_time']
        if flag in flags and flag not in self.hls_flags:
            self.hls_flags.append(flag)
            return {'status': 'success', 'flags': self.hls_flags}
        return {'status': 'error', 'message': '无效的HLS标志'}
        
    def create_master_playlist(self, variants):
        playlist = '#EXTM3U\n'
        playlist += '#EXT-X-VERSION:3\n'
        
        for variant in variants:
            playlist += f'#EXT-X-STREAM-INF:BANDWIDTH={variant["bitrate"]},RESOLUTION={variant["resolution"]}\n'
            playlist += f'{variant["path"]}\n'
            
        return {'status': 'success', 'playlist': playlist}
        
    def create_encode_command(self, input_file, output_path, variants):
        command = f'ffmpeg -i {input_file} '
        
        for i, variant in enumerate(variants):
            command += f'-map 0:v:0 -map 0:a:0 '
            command += f'-c:v:{i} libx264 -b:v:{i} {variant["bitrate"]} '
            command += f'-s:{i} {variant["resolution"]} '
            command += f'-c:a:{i} aac -b:a:{i} 128k '
            command += f'-hls_time {self.hls_time} '
            command += f'-hls_list_size {self.hls_list_size} '
            
            if self.hls_flags:
                command += f'-hls_flags {"," .join(self.hls_flags)} '
                
            command += f'{output_path}/{variant["path"]} '
            
        return {'status': 'success', 'command': command}
```

---

## 五、容器格式

### 5.1 视频容器

```python
class ContainerFormatManager:
    FORMATS = {
        'mp4': {
            'description': 'MPEG-4',
            'extensions': ['.mp4'],
            'codecs': ['h264', 'h265', 'aac', 'mp3'],
            'features': ['universal', 'streaming', 'metadata'],
            'limitations': ['no chapter support', 'limited subtitle']
        },
        'mov': {
            'description': 'QuickTime',
            'extensions': ['.mov'],
            'codecs': ['h264', 'h265', 'prores', 'aac', 'pcm'],
            'features': ['professional', 'chapter support', 'multiple tracks'],
            'limitations': ['large files', 'Apple ecosystem']
        },
        'mkv': {
            'description': 'Matroska',
            'extensions': ['.mkv'],
            'codecs': ['h264', 'h265', 'av1', 'vp9', 'aac', 'opus', 'flac'],
            'features': ['open source', 'multiple tracks', 'subtitles', 'chapters'],
            'limitations': ['limited hardware support']
        },
        'avi': {
            'description': 'AVI',
            'extensions': ['.avi'],
            'codecs': ['mpeg4', 'h264', 'mp3', 'pcm'],
            'features': ['legacy compatibility', 'simple'],
            'limitations': ['no streaming', 'limited metadata']
        },
        'webm': {
            'description': 'WebM',
            'extensions': ['.webm'],
            'codecs': ['vp8', 'vp9', 'av1', 'opus', 'vorbis'],
            'features': ['open source', 'web standard', 'good compression'],
            'limitations': ['limited player support']
        },
        'flv': {
            'description': 'Flash Video',
            'extensions': ['.flv'],
            'codecs': ['h264', 'vp6', 'mp3', 'aac'],
            'features': ['streaming', 'RTMP support'],
            'limitations': ['deprecated', 'limited features']
        },
        'ts': {
            'description': 'MPEG Transport Stream',
            'extensions': ['.ts'],
            'codecs': ['h264', 'h265', 'mp2', 'aac'],
            'features': ['streaming', 'error recovery', 'broadcast'],
            'limitations': ['large files', 'complex structure']
        },
        'mxf': {
            'description': 'MXF',
            'extensions': ['.mxf'],
            'codecs': ['dnxhd', 'prores', 'h264'],
            'features': ['professional broadcast', 'metadata'],
            'limitations': ['complex', 'large files']
        }
    }
    
    def __init__(self):
        self.format = 'mp4'
        
    def set_format(self, format_name):
        if format_name not in self.FORMATS:
            return {'status': 'error', 'message': '无效的容器格式'}
            
        self.format = format_name
        return {'status': 'success', 'format': self.FORMATS[format_name]}
        
    def get_supported_codecs(self):
        return self.FORMATS.get(self.format, {}).get('codecs', [])
        
    def is_compatible(self, video_codec, audio_codec):
        codecs = self.get_supported_codecs()
        return video_codec in codecs and audio_codec in codecs
```

---

## 六、批量处理与自动化

### 6.1 批量转换工具

```python
class BatchProcessor:
    def __init__(self):
        self.files = []
        self.output_format = 'mp4'
        self.video_codec = 'h264'
        self.audio_codec = 'aac'
        self.output_dir = './output'
        
    def add_file(self, file_path):
        import os
        if os.path.exists(file_path):
            self.files.append(file_path)
            return {'status': 'success', 'files': self.files}
        return {'status': 'error', 'message': '文件不存在'}
        
    def add_directory(self, dir_path, extensions=None):
        import os
        extensions = extensions or ['.mp4', '.mov', '.avi', '.mkv']
        
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in extensions):
                    self.files.append(os.path.join(root, file))
                    
        return {'status': 'success', 'file_count': len(self.files)}
        
    def set_output_dir(self, dir_path):
        import os
        os.makedirs(dir_path, exist_ok=True)
        self.output_dir = dir_path
        return {'status': 'success', 'output_dir': dir_path}
        
    def process_batch(self):
        results = []
        
        for input_file in self.files:
            import os
            filename = os.path.splitext(os.path.basename(input_file))[0]
            output_file = os.path.join(self.output_dir, f'{filename}.{self.output_format}')
            
            command = f'ffmpeg -i "{input_file}" -c:v {self.video_codec} -c:a {self.audio_codec} "{output_file}"'
            
            result = {
                'input': input_file,
                'output': output_file,
                'command': command,
                'status': 'pending'
            }
            results.append(result)
            
        return {'status': 'success', 'results': results}
```

### 6.2 Python API集成

```python
class FFmpegPythonAPI:
    def __init__(self):
        self.commands = []
        
    def convert(self, input_file, output_file, video_codec='libx264', audio_codec='aac', options=None):
        options = options or {}
        
        command = ['ffmpeg', '-i', input_file]
        
        if options.get('video_bitrate'):
            command.extend(['-b:v', options['video_bitrate']])
        if options.get('audio_bitrate'):
            command.extend(['-b:a', options['audio_bitrate']])
        if options.get('fps'):
            command.extend(['-r', str(options['fps'])])
        if options.get('resolution'):
            command.extend(['-s', options['resolution']])
        if options.get('preset'):
            command.extend(['-preset', options['preset']])
        if options.get('crf'):
            command.extend(['-crf', str(options['crf'])])
        if options.get('t'):
            command.extend(['-t', str(options['t'])])
        if options.get('ss'):
            command.extend(['-ss', str(options['ss'])])
            
        command.extend(['-c:v', video_codec, '-c:a', audio_codec, output_file])
        
        return {'status': 'success', 'command': ' '.join(command)}
        
    def extract_audio(self, input_file, output_file, audio_codec='aac'):
        command = f'ffmpeg -i "{input_file}" -vn -c:a {audio_codec} "{output_file}"'
        return {'status': 'success', 'command': command}
        
    def extract_video(self, input_file, output_file, video_codec='libx264'):
        command = f'ffmpeg -i "{input_file}" -an -c:v {video_codec} "{output_file}"'
        return {'status': 'success', 'command': command}
        
    def trim(self, input_file, output_file, start_time, duration):
        command = f'ffmpeg -i "{input_file}" -ss {start_time} -t {duration} -c copy "{output_file}"'
        return {'status': 'success', 'command': command}
        
    def merge(self, input_files, output_file):
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for input_file in input_files:
                f.write(f"file '{input_file}'\n")
            list_file = f.name
            
        command = f'ffmpeg -f concat -safe 0 -i "{list_file}" -c copy "{output_file}"'
        
        return {'status': 'success', 'command': command, 'list_file': list_file}
        
    def add_subtitle(self, input_file, subtitle_file, output_file):
        command = f'ffmpeg -i "{input_file}" -i "{subtitle_file}" -c copy -c:s mov_text "{output_file}"'
        return {'status': 'success', 'command': command}
        
    def overlay_watermark(self, input_file, watermark_file, output_file, position='bottom-right'):
        positions = {
            'top-left': '10:10',
            'top-right': 'main_w-overlay_w-10:10',
            'bottom-left': '10:main_h-overlay_h-10',
            'bottom-right': 'main_w-overlay_w-10:main_h-overlay_h-10',
            'center': '(main_w-overlay_w)/2:(main_h-overlay_h)/2'
        }
        
        pos = positions.get(position, 'main_w-overlay_w-10:main_h-overlay_h-10')
        
        command = f'ffmpeg -i "{input_file}" -i "{watermark_file}" -filter_complex "overlay={pos}" "{output_file}"'
        return {'status': 'success', 'command': command}
```

---

## 七、编码质量与优化

### 7.1 码率控制

```python
class BitrateControl:
    MODES = {
        'cbr': {'description': '恒定码率', 'syntax': '-b:v <bitrate>', 'features': ['consistent quality', 'good for streaming']},
        'vbr': {'description': '可变码率', 'syntax': '-b:v <bitrate> -maxrate <bitrate> -bufsize <buffer>', 'features': ['better compression', 'variable quality']},
        'crf': {'description': '恒定质量因子', 'syntax': '-crf <value>', 'features': ['consistent quality', 'auto bitrate'], 'values': {'libx264': [0, 51], 'libx265': [0, 51]}}
    }
    
    def __init__(self):
        self.mode = 'crf'
        self.crf_value = 23
        
    def set_mode(self, mode):
        if mode not in self.MODES:
            return {'status': 'error', 'message': '无效的码率控制模式'}
            
        self.mode = mode
        return {'status': 'success', 'mode': self.MODES[mode]}
        
    def set_crf(self, value):
        if 0 <= value <= 51:
            self.crf_value = value
            return {'status': 'success', 'crf': value}
        return {'status': 'error', 'message': 'CRF值必须在0-51之间'}
        
    def get_options(self):
        if self.mode == 'crf':
            return {'-crf': str(self.crf_value)}
        elif self.mode == 'cbr':
            return {'-b:v': '10M'}
        elif self.mode == 'vbr':
            return {'-b:v': '10M', '-maxrate': '15M', '-bufsize': '20M'}
        return {}
```

### 7.2 质量评估

```python
class QualityAssessment:
    METRICS = {
        'psnr': {'description': '峰值信噪比', 'command': 'psnr', 'range': '[0, inf)', 'higher_better': True},
        'ssim': {'description': '结构相似性', 'command': 'ssim', 'range': '[0, 1]', 'higher_better': True},
        'vmaf': {'description': '视频多方法评估融合', 'command': 'libvmaf', 'range': '[0, 100]', 'higher_better': True}
    }
    
    def __init__(self):
        self.metric = 'psnr'
        
    def set_metric(self, metric):
        if metric not in self.METRICS:
            return {'status': 'error', 'message': '无效的评估指标'}
            
        self.metric = metric
        return {'status': 'success', 'metric': self.METRICS[metric]}
        
    def calculate(self, reference_file, distorted_file):
        metric_info = self.METRICS[self.metric]
        
        if self.metric == 'psnr':
            command = f'ffmpeg -i "{reference_file}" -i "{distorted_file}" -filter_complex "[0:v][1:v]psnr" -f null -'
        elif self.metric == 'ssim':
            command = f'ffmpeg -i "{reference_file}" -i "{distorted_file}" -filter_complex "[0:v][1:v]ssim" -f null -'
        elif self.metric == 'vmaf':
            command = f'ffmpeg -i "{reference_file}" -i "{distorted_file}" -filter_complex "[0:v][1:v]libvmaf" -f null -'
            
        return {'status': 'success', 'command': command, 'metric': self.metric}
```

---

## 八、完整工作流示例

```python
class FFmpegWorkflowExample:
    def __init__(self):
        self.video_codec = VideoCodecManager()
        self.audio_codec = AudioCodecManager()
        self.video_filter = VideoFilterManager()
        self.audio_filter = AudioFilterManager()
        self.container = ContainerFormatManager()
        
    def process_video(self, input_file, output_file):
        print('=== FFmpeg视频处理工作流 ===')
        
        print('\n1. 设置视频编码')
        self.video_codec.set_codec('h264')
        self.video_codec.set_preset('medium')
        video_opts = self.video_codec.get_encode_options()
        print(f'视频编码器: {video_opts["options"]["-c:v"]}')
        
        print('\n2. 设置音频编码')
        self.audio_codec.set_codec('aac')
        self.audio_codec.set_bitrate('128k')
        audio_opts = self.audio_codec.get_encode_options()
        print(f'音频编码器: {audio_opts["options"]["-c:a"]}')
        
        print('\n3. 添加视频滤镜')
        self.video_filter.add_filter('scale', {'w': 1920, 'h': 1080})
        self.video_filter.add_filter('fps', {'fps': 24})
        self.video_filter.add_filter('fade', {'t': 'in', 'st': 0, 'd': 2})
        self.video_filter.add_filter('fade', {'t': 'out', 'st': 10, 'd': 2})
        print(f'视频滤镜: {self.video_filter.get_filter_string()}')
        
        print('\n4. 添加音频滤镜')
        self.audio_filter.add_filter('volume', {'volume': 1.2})
        self.audio_filter.add_filter('loudnorm', {'I': -16, 'LRA': 11, 'TP': -1.5})
        print(f'音频滤镜: {self.audio_filter.get_filter_string()}')
        
        print('\n5. 设置输出容器')
        self.container.set_format('mp4')
        print(f'输出格式: {self.container.format}')
        
        command = f'''ffmpeg -i "{input_file}" \
            -vf "{self.video_filter.get_filter_string()}" \
            -af "{self.audio_filter.get_filter_string()}" \
            {video_opts["options"]["-c:v"]} {video_opts["options"].get("-preset", "")} \
            {audio_opts["options"]["-c:a"]} {audio_opts["options"].get("-b:a", "")} \
            -crf 23 \
            "{output_file}"'''
            
        print(f'\n生成命令: {command}')
        
        return {
            'status': 'success',
            'command': command,
            'video_codec': self.video_codec.current_codec,
            'audio_codec': self.audio_codec.current_codec,
            'video_filters': self.video_filter.filters,
            'audio_filters': self.audio_filter.filters,
            'container': self.container.format
        }

if __name__ == '__main__':
    workflow = FFmpegWorkflowExample()
    
    result = workflow.process_video(
        input_file='input.mp4',
        output_file='output.mp4'
    )
    
    print(f'\n=== 工作流完成 ===')
    print(f'状态: {result["status"]}')
    print(f'视频编码: {result["video_codec"]}')
    print(f'音频编码: {result["audio_codec"]}')
```

---

## 附录：常用命令速查

```python
class FFmpegCommandReference:
    COMMANDS = {
        'convert': {
            'description': '格式转换',
            'example': 'ffmpeg -i input.mp4 output.mkv'
        },
        'extract_audio': {
            'description': '提取音频',
            'example': 'ffmpeg -i input.mp4 -vn audio.mp3'
        },
        'extract_video': {
            'description': '提取视频',
            'example': 'ffmpeg -i input.mp4 -an video.mp4'
        },
        'trim': {
            'description': '裁剪视频',
            'example': 'ffmpeg -i input.mp4 -ss 00:00:10 -t 00:00:20 output.mp4'
        },
        'merge': {
            'description': '合并视频',
            'example': 'ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4'
        },
        'resize': {
            'description': '调整尺寸',
            'example': 'ffmpeg -i input.mp4 -vf scale=1920:1080 output.mp4'
        },
        'change_fps': {
            'description': '改变帧率',
            'example': 'ffmpeg -i input.mp4 -vf fps=24 output.mp4'
        },
        'add_watermark': {
            'description': '添加水印',
            'example': 'ffmpeg -i input.mp4 -i watermark.png -filter_complex "overlay=10:10" output.mp4'
        },
        'add_subtitle': {
            'description': '添加字幕',
            'example': 'ffmpeg -i input.mp4 -i subtitle.srt -c copy -c:s mov_text output.mp4'
        },
        'stream_rtmp': {
            'description': '推流到RTMP',
            'example': 'ffmpeg -re -i input.mp4 -c:v libx264 -c:a aac -f flv rtmp://server/live/stream'
        },
        'hls_stream': {
            'description': '生成HLS流',
            'example': 'ffmpeg -i input.mp4 -hls_time 2 -hls_list_size 6 output.m3u8'
        },
        'rotate': {
            'description': '旋转视频',
            'example': 'ffmpeg -i input.mp4 -vf rotate=PI/2 output.mp4'
        },
        'flip': {
            'description': '翻转视频',
            'example': 'ffmpeg -i input.mp4 -vf flip output.mp4'
        },
        'color_correct': {
            'description': '色彩校正',
            'example': 'ffmpeg -i input.mp4 -vf "brightness=0.1:saturation=1.2" output.mp4'
        },
        'compress': {
            'description': '压缩视频',
            'example': 'ffmpeg -i input.mp4 -crf 28 output.mp4'
        },
        'info': {
            'description': '查看媒体信息',
            'example': 'ffprobe -v quiet -print_format json -show_format -show_streams input.mp4'
        }
    }
    
    def get_command(self, name):
        if name in self.COMMANDS:
            return {'status': 'success', 'command': self.COMMANDS[name]}
        return {'status': 'error', 'message': '命令不存在'}
        
    def search(self, keyword):
        results = []
        for name, cmd in self.COMMANDS.items():
            if keyword.lower() in name.lower() or keyword.lower() in cmd['description'].lower():
                results.append({'name': name, **cmd})
                
        if results:
            return {'status': 'success', 'results': results}
        return {'status': 'error', 'message': '未找到匹配的命令'}
```
