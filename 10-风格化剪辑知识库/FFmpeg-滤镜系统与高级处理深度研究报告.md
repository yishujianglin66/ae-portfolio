# FFmpeg - 滤镜系统与高级处理深度研究报告

## 1. 滤镜系统概述

### 1.1 滤镜架构

FFmpeg的滤镜系统是一个强大的视频/音频处理框架，支持链式处理和复杂的滤镜图。

```python
class FilterSystemArchitecture:
    FILTER_TYPES = {
        'video': ['source', 'transform', 'effect', 'composite', 'output'],
        'audio': ['source', 'transform', 'effect', 'mix', 'output'],
        'subtitle': ['source', 'render', 'overlay', 'output']
    }
    
    FILTER_CATEGORIES = {
        'video_filters': [
            'scale', 'crop', 'transpose', 'rotate', 'flip', 'pad', 'zoompan',
            'overlay', 'blend', 'alphamerge', 'chromakey', 'colorkey',
            'eq', 'hue', 'saturation', 'contrast', 'brightness',
            'blur', 'gblur', 'boxblur', 'smartblur',
            'sharpen', 'unsharp', 'edgedetect',
            'fade', 'dissolve', 'wipe', 'slide',
            'fps', 'decimate', 'interlace', 'deinterlace',
            'drawtext', 'drawbox', 'drawgrid',
            'subtitles', 'ass', 'textsub',
            'hqdn3d', 'nlmeans', 'median',
            'yadif', 'dejudder', 'fieldorder'
        ],
        'audio_filters': [
            'volume', 'dynaudnorm', 'compand', 'equalizer',
            'highpass', 'lowpass', 'bandpass', 'bandreject',
            'afade', 'acrossfade', 'adelay',
            'aresample', 'asetrate', 'atempo',
            'amix', 'amerge', 'apad',
            'anull', 'anullsrc', 'anullsink',
            'arnndn', 'afftdn', 'highpass',
            'stereotools', 'channelmap', 'join'
        ],
        'complex_filters': [
            'overlay', 'blend', 'concat', 'split',
            'merge', 'amerge', 'amix',
            'xfade', 'acrossfade',
            'tblend', 'ipblur',
            'vstack', 'hstack', 'xstack'
        ]
    }
```

### 1.2 滤镜图概念

滤镜图是FFmpeg滤镜系统的核心概念，允许构建复杂的处理流程。

```python
class FilterGraph:
    def __init__(self):
        self.filters = []
        self.links = []
        self.inputs = []
        self.outputs = []
        
    def add_filter(self, filter_name, args=None, label=None):
        filter_node = {
            'id': f'filter_{len(self.filters) + 1}',
            'name': filter_name,
            'args': args or {},
            'label': label or filter_name,
            'inputs': [],
            'outputs': []
        }
        
        self.filters.append(filter_node)
        return {'status': 'success', 'filter': filter_node}
    
    def add_link(self, from_filter, from_pad, to_filter, to_pad):
        link = {
            'id': f'link_{len(self.links) + 1}',
            'from': {'filter': from_filter, 'pad': from_pad},
            'to': {'filter': to_filter, 'pad': to_pad}
        }
        
        self.links.append(link)
        return {'status': 'success', 'link': link}
    
    def build_command(self):
        filter_strings = []
        
        for filter_node in self.filters:
            args_str = ':'.join([f'{k}={v}' for k, v in filter_node['args'].items()])
            filter_str = f'{filter_node["name"]}={args_str}'
            
            if filter_node['label']:
                filter_str = f'[{filter_node["label"]}]{filter_str}'
                
            filter_strings.append(filter_str)
        
        return ','.join(filter_strings)
```

---

## 2. 视频滤镜详解

### 2.1 几何变换滤镜

几何变换滤镜用于对视频进行缩放、裁剪、旋转等空间变换。

```python
class GeometricTransformFilters:
    FILTERS = {
        'scale': {
            'description': '缩放',
            'parameters': ['width', 'height', 'flags', 'interpolation'],
            'example': 'scale=1920:1080'
        },
        'crop': {
            'description': '裁剪',
            'parameters': ['width', 'height', 'x', 'y', 'keep_aspect'],
            'example': 'crop=1920:1080:0:0'
        },
        'transpose': {
            'description': '转置',
            'parameters': ['dir'],
            'example': 'transpose=1'
        },
        'rotate': {
            'description': '旋转',
            'parameters': ['angle', 'ow', 'oh', 'bilinear'],
            'example': 'rotate=45*PI/180'
        },
        'flip': {
            'description': '水平翻转',
            'parameters': [],
            'example': 'flip'
        },
        'pad': {
            'description': '填充',
            'parameters': ['width', 'height', 'x', 'y', 'color'],
            'example': 'pad=1920:1080:0:0:black'
        },
        'zoompan': {
            'description': '缩放平移',
            'parameters': ['zoom', 'x', 'y', 'd', 's'],
            'example': 'zoompan=zoom=1.5:x=0:y=0:d=1'
        }
    }
    
    def scale(self, width, height, flags='lanczos'):
        return f'scale={width}:{height}:flags={flags}'
    
    def crop(self, width, height, x=0, y=0):
        return f'crop={width}:{height}:{x}:{y}'
    
    def rotate(self, angle_degrees, bilinear=True):
        angle_radians = angle_degrees * 3.1415926535 / 180
        bilinear_flag = 'bilinear=1' if bilinear else ''
        return f'rotate={angle_radians}{":" + bilinear_flag if bilinear_flag else ""}'
    
    def pad_to_aspect_ratio(self, target_width, target_height, color='black'):
        return f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:{color}'
```

### 2.2 色彩校正滤镜

色彩校正滤镜用于调整视频的色彩、对比度、饱和度等参数。

```python
class ColorCorrectionFilters:
    FILTERS = {
        'eq': {
            'description': '均衡器',
            'parameters': ['brightness', 'contrast', 'saturation', 'gamma', 'gamma_r', 'gamma_g', 'gamma_b'],
            'example': 'eq=brightness=0.1:contrast=1.2:saturation=1.1'
        },
        'hue': {
            'description': '色相调整',
            'parameters': ['h', 's'],
            'example': 'hue=h=90:s=1'
        },
        'saturation': {
            'description': '饱和度调整',
            'parameters': ['s'],
            'example': 'saturation=1.5'
        },
        'contrast': {
            'description': '对比度调整',
            'parameters': ['contrast'],
            'example': 'contrast=1.2'
        },
        'brightness': {
            'description': '亮度调整',
            'parameters': ['b'],
            'example': 'brightness=0.1'
        },
        'colorbalance': {
            'description': '色彩平衡',
            'parameters': ['rs', 'gs', 'bs', 'rr', 'gr', 'br'],
            'example': 'colorbalance=rs=1.2:gs=1.0:bs=0.8'
        },
        'curves': {
            'description': '曲线调整',
            'parameters': ['preset', 'm', 'r', 'g', 'b', 'a'],
            'example': 'curves=vintage'
        },
        'lut3d': {
            'description': '3D LUT',
            'parameters': ['file', 'interpolation'],
            'example': 'lut3d=file=cinematic.cube'
        }
    }
    
    def apply_color_grade(self, brightness=0, contrast=1, saturation=1, gamma=1):
        params = []
        if brightness != 0:
            params.append(f'brightness={brightness}')
        if contrast != 1:
            params.append(f'contrast={contrast}')
        if saturation != 1:
            params.append(f'saturation={saturation}')
        if gamma != 1:
            params.append(f'gamma={gamma}')
        
        return f'eq={":".join(params)}' if params else ''
    
    def apply_lut(self, lut_file):
        return f'lut3d={lut_file}'
    
    def apply_curve_preset(self, preset):
        return f'curves={preset}'
```

### 2.3 效果滤镜

效果滤镜用于添加各种视觉效果。

```python
class EffectFilters:
    FILTERS = {
        'blur': {
            'description': '模糊',
            'parameters': ['luma_radius', 'chroma_radius', 'alpha_radius'],
            'example': 'blur=5:5:0'
        },
        'gblur': {
            'description': '高斯模糊',
            'parameters': ['sigma', 'sigmaV'],
            'example': 'gblur=sigma=5'
        },
        'boxblur': {
            'description': '盒子模糊',
            'parameters': ['lr', 'lb', 'cr', 'cb', 'ar', 'ab'],
            'example': 'boxblur=5:1:5:1'
        },
        'sharpen': {
            'description': '锐化',
            'parameters': ['luma_amount', 'chroma_amount'],
            'example': 'sharpen=1.0:0.0'
        },
        'unsharp': {
            'description': '非锐化遮罩',
            'parameters': ['luma_msize_x', 'luma_msize_y', 'luma_amount', 'chroma_msize_x', 'chroma_msize_y', 'chroma_amount'],
            'example': 'unsharp=5:5:1.0:5:5:0.0'
        },
        'edgedetect': {
            'description': '边缘检测',
            'parameters': [],
            'example': 'edgedetect'
        },
        'fade': {
            'description': '淡入淡出',
            'parameters': ['type', 'start_frame', 'nb_frames', 'alpha', 'color'],
            'example': 'fade=t=in:st=0:n=30'
        },
        'xfade': {
            'description': '转场效果',
            'parameters': ['transition', 'duration', 'offset'],
            'example': 'xfade=transition=fade:duration=1:offset=10'
        },
        'drawtext': {
            'description': '绘制文字',
            'parameters': ['text', 'fontfile', 'fontsize', 'fontcolor', 'x', 'y', 'shadowcolor', 'shadowx', 'shadowy'],
            'example': 'drawtext=text=Hello:fontfile=arial.ttf:fontsize=24:x=100:y=100'
        },
        'drawbox': {
            'description': '绘制矩形',
            'parameters': ['x', 'y', 'width', 'height', 'color', 'thickness'],
            'example': 'drawbox=x=10:y=10:w=100:h=100:color=red:t=2'
        },
        'chromakey': {
            'description': '色度键',
            'parameters': ['color', 'similarity', 'blend'],
            'example': 'chromakey=color=green:similarity=0.1:blend=0.05'
        },
        'colorkey': {
            'description': '颜色键',
            'parameters': ['color', 'similarity', 'blend'],
            'example': 'colorkey=color=blue:similarity=0.1'
        }
    }
    
    def apply_gaussian_blur(self, sigma=5):
        return f'gblur=sigma={sigma}'
    
    def apply_sharpen(self, amount=1.0):
        return f'sharpen={amount}'
    
    def apply_fade(self, type='in', start_frame=0, nb_frames=30):
        return f'fade=t={type}:st={start_frame}:n={nb_frames}'
    
    def apply_transition(self, transition_type='fade', duration=1, offset=0):
        return f'xfade=transition={transition_type}:duration={duration}:offset={offset}'
    
    def add_text(self, text, font_size=24, x=0, y=0, color='white'):
        return f'drawtext=text={text}:fontsize={font_size}:fontcolor={color}:x={x}:y={y}'
    
    def apply_chromakey(self, color='green', similarity=0.1, blend=0.05):
        return f'chromakey=color={color}:similarity={similarity}:blend={blend}'
```

---

## 3. 音频滤镜详解

### 3.1 基本音频滤镜

基本音频滤镜用于调整音量、平衡、混响等参数。

```python
class AudioFilters:
    FILTERS = {
        'volume': {
            'description': '音量调整',
            'parameters': ['volume', 'replaygain', 'replaygain_preamp'],
            'example': 'volume=2.0'
        },
        'dynaudnorm': {
            'description': '动态音频归一化',
            'parameters': ['g', 'p', 'l', 'm'],
            'example': 'dynaudnorm=g=15:p=0.95:l=100'
        },
        'compand': {
            'description': '动态压缩',
            'parameters': ['attacks', 'decays', 'points', 'soft-knee', 'gain', 'volume'],
            'example': 'compand=.3|.3:1|1:-90/-60|-60/-40|-40/-30|-20/-20:6:0:-90:0.2'
        },
        'equalizer': {
            'description': '均衡器',
            'parameters': ['f', 't', 'w', 'g'],
            'example': 'equalizer=f=1000:t=q:w=1:g=5'
        },
        'highpass': {
            'description': '高通滤波器',
            'parameters': ['f', 't', 'w'],
            'example': 'highpass=f=100'
        },
        'lowpass': {
            'description': '低通滤波器',
            'parameters': ['f', 't', 'w'],
            'example': 'lowpass=f=3000'
        },
        'afade': {
            'description': '音频淡入淡出',
            'parameters': ['type', 'start_sample', 'nb_samples', 'curve'],
            'example': 'afade=t=in:st=0:n=48000'
        },
        'acrossfade': {
            'description': '音频交叉淡入淡出',
            'parameters': ['duration', 'curve1', 'curve2'],
            'example': 'acrossfade=d=1'
        },
        'adelay': {
            'description': '音频延迟',
            'parameters': ['delays'],
            'example': 'adelay=1000|1000'
        },
        'aresample': {
            'description': '音频重采样',
            'parameters': ['rate', 'resampler'],
            'example': 'aresample=44100'
        },
        'atempo': {
            'description': '音频变速',
            'parameters': ['tempo'],
            'example': 'atempo=1.5'
        },
        'amix': {
            'description': '音频混合',
            'parameters': ['inputs', 'duration', 'dropout_transition'],
            'example': 'amix=inputs=2'
        },
        'amerge': {
            'description': '音频合并',
            'parameters': ['inputs'],
            'example': 'amerge=inputs=2'
        }
    }
    
    def adjust_volume(self, volume=1.0):
        return f'volume={volume}'
    
    def apply_compression(self, attack=0.3, decay=1.0, threshold=-20):
        return f'compand={attack}|{attack}:{decay}|{decay}:-90/-60|-60/-40|-40/-30|{threshold}/{threshold}:6:0:-90:0.2'
    
    def apply_equalizer(self, frequency=1000, gain=5, width=1):
        return f'equalizer=f={frequency}:t=q:w={width}:g={gain}'
    
    def apply_fade(self, type='in', duration=1):
        nb_samples = int(duration * 48000)
        return f'afade=t={type}:st=0:n={nb_samples}'
    
    def apply_crossfade(self, duration=1):
        return f'acrossfade=d={duration}'
    
    def change_tempo(self, tempo=1.0):
        return f'atempo={tempo}'
```

### 3.2 高级音频处理

高级音频处理包括降噪、回声消除、环绕声处理等。

```python
class AdvancedAudioProcessing:
    FILTERS = {
        'arnndn': {
            'description': 'RNN降噪',
            'parameters': ['model'],
            'example': 'arnndn=model=rnnn48k.rnnn'
        },
        'afftdn': {
            'description': '频域降噪',
            'parameters': ['nf', 'tnf', 'rf', 'tf', 'bd', 'fd'],
            'example': 'afftdn=nf=-20:tnf=-40'
        },
        'highpass': {
            'description': '高通滤波',
            'parameters': ['f', 't'],
            'example': 'highpass=f=80'
        },
        'lowpass': {
            'description': '低通滤波',
            'parameters': ['f', 't'],
            'example': 'lowpass=f=15000'
        },
        'stereotools': {
            'description': '立体声工具',
            'parameters': ['level_in', 'level_out', 'balance_in', 'balance_out', 'softclip', 'mutel', 'muter', 'phasel', 'phaser'],
            'example': 'stereotools=balance_in=0.5'
        },
        'channelmap': {
            'description': '声道映射',
            'parameters': ['channel_layout', 'map'],
            'example': 'channelmap=channel_layout=stereo:map=0.0-FL|1.0-FR'
        },
        'join': {
            'description': '声道合并',
            'parameters': ['inputs', 'channel_layout'],
            'example': 'join=inputs=2:channel_layout=stereo'
        },
        'aecho': {
            'description': '回声',
            'parameters': ['in_gain', 'out_gain', 'delays', 'decays'],
            'example': 'aecho=0.8:0.8:1000:0.5'
        },
        'chorus': {
            'description': '合唱效果',
            'parameters': ['in_gain', 'out_gain', 'delays', 'decays', 'speeds', 'depths'],
            'example': 'chorus=0.6:0.9:50|60|40:0.4|0.3|0.5:2|2.3|1.5:0.4|0.3|0.3'
        },
        'reverb': {
            'description': '混响',
            'parameters': ['in_gain', 'reverb_time', 'decay', 'delay', 'mix'],
            'example': 'reverb=2.0:2.0:1000:0.5'
        }
    }
    
    def apply_noise_reduction(self, method='arnndn', model=None):
        if method == 'arnndn' and model:
            return f'arnndn=model={model}'
        elif method == 'afftdn':
            return 'afftdn=nf=-20:tnf=-40'
        return ''
    
    def apply_reverb(self, in_gain=2.0, reverb_time=2.0, delay=1000, mix=0.5):
        return f'reverb={in_gain}:{reverb_time}:{delay}:{mix}'
    
    def apply_chorus(self):
        return 'chorus=0.6:0.9:50|60|40:0.4|0.3|0.5:2|2.3|1.5:0.4|0.3|0.3'
    
    def convert_to_stereo(self):
        return 'join=inputs=2:channel_layout=stereo'
```

---

## 4. 复杂滤镜图

### 4.1 滤镜图构建

复杂滤镜图允许构建多输入/多输出的处理流程。

```python
class ComplexFilterGraphBuilder:
    def __init__(self):
        self.inputs = []
        self.filters = []
        self.outputs = []
        
    def add_input(self, label):
        self.inputs.append(label)
        return {'status': 'success'}
    
    def add_filter(self, name, args=None, label=None):
        filter_node = {
            'name': name,
            'args': args or {},
            'label': label or name
        }
        self.filters.append(filter_node)
        return {'status': 'success', 'filter': filter_node}
    
    def build_complex_filter(self):
        filter_strings = []
        
        for i, filter_node in enumerate(self.filters):
            args_str = ':'.join([f'{k}={v}' for k, v in filter_node['args'].items()])
            filter_str = f'{filter_node["name"]}={args_str}'
            
            if filter_node['label']:
                filter_str = f'[{filter_node["label"]}]{filter_str}'
                
            filter_strings.append(filter_str)
        
        return ';'.join(filter_strings)
    
    def overlay_video(self, main_input, overlay_input, x=0, y=0):
        filter_str = f'[{main_input}][{overlay_input}]overlay={x}:{y}'
        self.filters.append({'name': 'overlay', 'args': {'x': x, 'y': y}, 'label': f'{main_input}_overlay_{overlay_input}'})
        return {'status': 'success', 'filter': filter_str}
    
    def split_and_process(self, input_label, output_labels):
        split_filter = f'[{input_label}]split={len(output_labels)}'
        self.filters.append({'name': 'split', 'args': {'outputs': len(output_labels)}, 'label': f'{input_label}_split'})
        
        for i, output_label in enumerate(output_labels):
            split_filter += f'[{output_label}]'
        
        return {'status': 'success', 'filter': split_filter}
    
    def concat_videos(self, inputs, duration=None):
        concat_filter = f'[{"][".join(inputs)}]concat=n={len(inputs)}'
        
        if duration:
            concat_filter += f':v=1:a=1:d={duration}'
        else:
            concat_filter += ':v=1:a=1'
        
        self.filters.append({'name': 'concat', 'args': {'n': len(inputs)}, 'label': 'concat'})
        return {'status': 'success', 'filter': concat_filter}
```

### 4.2 实际应用示例

复杂滤镜图的实际应用示例。

```python
class ComplexFilterExamples:
    def create_picture_in_picture(self, main_video, pip_video, pip_size='320x180', x=10, y=10):
        return f'[{pip_video}]scale={pip_size}[pip_scaled];[{main_video}][pip_scaled]overlay={x}:{y}'
    
    def create_split_screen(self, video1, video2, layout='hstack'):
        if layout == 'hstack':
            return f'[{video1}][{video2}]hstack=inputs=2'
        elif layout == 'vstack':
            return f'[{video1}][{video2}]vstack=inputs=2'
        elif layout == 'grid':
            return f'[{video1}][{video2}]xstack=inputs=2:layout=2x1'
    
    def create_transition_sequence(self, videos, transition_type='fade', duration=1):
        filters = []
        
        for i in range(len(videos) - 1):
            offset = sum(self._get_duration(videos[j]) for j in range(i)) - duration
            filters.append(f'xfade=transition={transition_type}:duration={duration}:offset={offset}')
        
        return ';'.join(filters)
    
    def create_color_grading_pipeline(self, input_video):
        return f'[{input_video}]eq=brightness=0.05:contrast=1.1:saturation=1.05,hue=h=5,saturation=1.1,curves=vintage,lut3d=cinematic.cube'
    
    def create_audio_mixing_pipeline(self, audio_tracks):
        return f'[{"][".join(audio_tracks)}]amix=inputs={len(audio_tracks)}:duration=first:dropout_transition=3'
    
    def _get_duration(self, video_path):
        import subprocess
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', video_path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
```

---

## 5. FFmpeg滤镜Python API

### 5.1 FFmpeg Python封装

使用Python封装FFmpeg滤镜功能。

```python
class FFmpegFilterAPI:
    def __init__(self, ffmpeg_path='ffmpeg'):
        self.ffmpeg_path = ffmpeg_path
        self.filters = []
        self.inputs = []
        self.output = None
        
    def add_input(self, input_path, params=None):
        self.inputs.append({
            'path': input_path,
            'params': params or {}
        })
        return {'status': 'success'}
    
    def set_output(self, output_path, params=None):
        self.output = {
            'path': output_path,
            'params': params or {}
        }
        return {'status': 'success'}
    
    def add_video_filter(self, filter_name, args=None):
        self.filters.append({
            'type': 'video',
            'name': filter_name,
            'args': args or {}
        })
        return {'status': 'success'}
    
    def add_audio_filter(self, filter_name, args=None):
        self.filters.append({
            'type': 'audio',
            'name': filter_name,
            'args': args or {}
        })
        return {'status': 'success'}
    
    def add_complex_filter(self, filter_str):
        self.filters.append({
            'type': 'complex',
            'filter_str': filter_str
        })
        return {'status': 'success'}
    
    def build_command(self):
        command = [self.ffmpeg_path]
        
        for input_file in self.inputs:
            if input_file['params']:
                for key, value in input_file['params'].items():
                    command.extend([f'-{key}', str(value)])
            command.extend(['-i', input_file['path']])
        
        video_filters = [f for f in self.filters if f['type'] == 'video']
        audio_filters = [f for f in self.filters if f['type'] == 'audio']
        complex_filters = [f for f in self.filters if f['type'] == 'complex']
        
        if video_filters:
            vf_str = ','.join([self._build_filter_str(f) for f in video_filters])
            command.extend(['-vf', vf_str])
        
        if audio_filters:
            af_str = ','.join([self._build_filter_str(f) for f in audio_filters])
            command.extend(['-af', af_str])
        
        if complex_filters:
            cf_str = ';'.join([f['filter_str'] for f in complex_filters])
            command.extend(['-filter_complex', cf_str])
        
        if self.output:
            if self.output['params']:
                for key, value in self.output['params'].items():
                    command.extend([f'-{key}', str(value)])
            command.append(self.output['path'])
        
        return {'status': 'success', 'command': command}
    
    def _build_filter_str(self, filter_dict):
        args_str = ':'.join([f'{k}={v}' for k, v in filter_dict['args'].items()])
        return f'{filter_dict["name"]}={args_str}'
    
    def execute(self):
        command_result = self.build_command()
        
        if command_result['status'] != 'success':
            return command_result
        
        command = command_result['command']
        
        import subprocess
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {'status': 'success', 'output': result.stdout}
        else:
            return {'status': 'error', 'message': result.stderr}
```

### 5.2 滤镜链构建器

滤镜链构建器提供更便捷的滤镜组合方式。

```python
class FilterChainBuilder:
    def __init__(self):
        self.video_filters = []
        self.audio_filters = []
        
    def scale(self, width, height):
        self.video_filters.append(f'scale={width}:{height}')
        return self
    
    def crop(self, width, height, x=0, y=0):
        self.video_filters.append(f'crop={width}:{height}:{x}:{y}')
        return self
    
    def rotate(self, angle):
        radians = angle * 3.1415926535 / 180
        self.video_filters.append(f'rotate={radians}')
        return self
    
    def color_grade(self, brightness=0, contrast=1, saturation=1):
        params = []
        if brightness != 0:
            params.append(f'brightness={brightness}')
        if contrast != 1:
            params.append(f'contrast={contrast}')
        if saturation != 1:
            params.append(f'saturation={saturation}')
        
        if params:
            self.video_filters.append(f'eq={":".join(params)}')
        return self
    
    def apply_lut(self, lut_file):
        self.video_filters.append(f'lut3d={lut_file}')
        return self
    
    def blur(self, sigma=5):
        self.video_filters.append(f'gblur=sigma={sigma}')
        return self
    
    def sharpen(self, amount=1.0):
        self.video_filters.append(f'sharpen={amount}')
        return self
    
    def fade_in(self, duration=1):
        frames = int(duration * 30)
        self.video_filters.append(f'fade=t=in:st=0:n={frames}')
        return self
    
    def fade_out(self, duration=1, start_time=0):
        frames = int(duration * 30)
        self.video_filters.append(f'fade=t=out:st={start_time}:n={frames}')
        return self
    
    def adjust_volume(self, volume=1.0):
        self.audio_filters.append(f'volume={volume}')
        return self
    
    def audio_fade_in(self, duration=1):
        samples = int(duration * 48000)
        self.audio_filters.append(f'afade=t=in:st=0:n={samples}')
        return self
    
    def audio_fade_out(self, duration=1, start_time=0):
        samples = int(duration * 48000)
        self.audio_filters.append(f'afade=t=out:st={start_time}:n={samples}')
        return self
    
    def build_video_filter(self):
        return ','.join(self.video_filters)
    
    def build_audio_filter(self):
        return ','.join(self.audio_filters)
    
    def build_both(self):
        return {
            'video': self.build_video_filter(),
            'audio': self.build_audio_filter()
        }
```

---

## 6. 性能优化策略

### 6.1 滤镜性能优化

滤镜性能优化策略包括硬件加速、滤镜顺序优化和参数调整。

```python
class FilterPerformanceOptimizer:
    OPTIMIZATION_TECHNIQUES = {
        'hardware_acceleration': {
            'description': '硬件加速',
            'techniques': ['CUDA', 'VA-API', 'QSV', 'Vulkan'],
            'ffmpeg_flags': ['-hwaccel cuda', '-hwaccel vaapi', '-hwaccel qsv']
        },
        'filter_order': {
            'description': '滤镜顺序优化',
            'techniques': ['先裁剪后缩放', '先降噪后锐化', '先色彩校正后特效'],
            'reasoning': '减少后续滤镜处理的数据量'
        },
        'parameter_tuning': {
            'description': '参数调优',
            'techniques': ['降低模糊半径', '减少采样率', '优化滤镜参数'],
            'reasoning': '平衡质量与性能'
        },
        'parallel_processing': {
            'description': '并行处理',
            'techniques': ['线程数设置', '帧线程数设置'],
            'ffmpeg_flags': ['-threads', '-frame_threads']
        },
        'avoid_unnecessary_filters': {
            'description': '避免不必要的滤镜',
            'techniques': ['合并相似滤镜', '移除冗余处理'],
            'reasoning': '减少处理步骤'
        }
    }
    
    def optimize_command(self, command, optimization_level='medium'):
        optimized_command = command.copy()
        
        if optimization_level in ['high', 'medium']:
            optimized_command.insert(1, '-hwaccel')
            optimized_command.insert(2, 'auto')
        
        if optimization_level == 'high':
            optimized_command.append('-threads')
            optimized_command.append('16')
            optimized_command.append('-frame_threads')
            optimized_command.append('4')
        
        return {'status': 'success', 'command': optimized_command}
    
    def suggest_filter_order(self, filters):
        optimized_order = []
        
        crop_filters = [f for f in filters if 'crop' in f]
        scale_filters = [f for f in filters if 'scale' in f and 'crop' not in f]
        denoise_filters = [f for f in filters if any(x in f for x in ['hqdn3d', 'nlmeans', 'afftdn'])]
        color_filters = [f for f in filters if any(x in f for x in ['eq', 'hue', 'saturation', 'curves', 'lut3d'])]
        effect_filters = [f for f in filters if any(x in f for x in ['blur', 'sharpen', 'fade', 'xfade'])]
        
        optimized_order.extend(crop_filters)
        optimized_order.extend(scale_filters)
        optimized_order.extend(denoise_filters)
        optimized_order.extend(color_filters)
        optimized_order.extend(effect_filters)
        
        return {'status': 'success', 'optimized_order': optimized_order}
```

---

## 7. 企业级应用场景

### 7.1 批量视频处理

批量视频处理在企业场景中的应用包括：

- 视频转码：批量转换视频格式
- 水印添加：批量添加公司水印
- 尺寸调整：批量调整视频尺寸
- 色彩校正：批量调整视频色彩
- 音频处理：批量调整音频参数

### 7.2 实时流媒体处理

实时流媒体处理在企业场景中的应用包括：

- 直播流处理：实时滤镜处理
- 视频会议：实时背景模糊
- 监控视频：实时分析和处理
- 视频转码：实时格式转换

---

## 附录：滤镜参考

### A.1 常用视频滤镜列表

| 滤镜名称 | 类别 | 主要用途 | 示例 |
|----------|------|----------|------|
| scale | 几何 | 缩放 | scale=1920:1080 |
| crop | 几何 | 裁剪 | crop=1920:1080 |
| rotate | 几何 | 旋转 | rotate=45*PI/180 |
| flip | 几何 | 翻转 | flip |
| pad | 几何 | 填充 | pad=1920:1080:(ow-iw)/2:(oh-ih)/2 |
| eq | 色彩 | 均衡器 | eq=brightness=0.1:contrast=1.2 |
| hue | 色彩 | 色相 | hue=h=90 |
| saturation | 色彩 | 饱和度 | saturation=1.5 |
| curves | 色彩 | 曲线 | curves=vintage |
| lut3d | 色彩 | 3D LUT | lut3d=cinematic.cube |
| gblur | 效果 | 高斯模糊 | gblur=sigma=5 |
| sharpen | 效果 | 锐化 | sharpen=1.0 |
| unsharp | 效果 | 非锐化遮罩 | unsharp=5:5:1.0 |
| fade | 效果 | 淡入淡出 | fade=t=in:n=30 |
| xfade | 效果 | 转场 | xfade=transition=fade:d=1 |
| drawtext | 效果 | 文字 | drawtext=text=Hello:fontsize=24 |
| chromakey | 效果 | 色度键 | chromakey=color=green |
| overlay | 合成 | 叠加 | overlay=10:10 |
| hstack | 合成 | 水平堆叠 | hstack=inputs=2 |
| vstack | 合成 | 垂直堆叠 | vstack=inputs=2 |
| concat | 合成 | 拼接 | concat=n=2:v=1:a=1 |

### A.2 常用音频滤镜列表

| 滤镜名称 | 类别 | 主要用途 | 示例 |
|----------|------|----------|------|
| volume | 基本 | 音量 | volume=2.0 |
| dynaudnorm | 基本 | 动态归一化 | dynaudnorm=g=15 |
| compand | 基本 | 动态压缩 | compand=.3|.3:1|1:-90/-60 |
| equalizer | 均衡 | 均衡器 | equalizer=f=1000:g=5 |
| highpass | 滤波 | 高通 | highpass=f=100 |
| lowpass | 滤波 | 低通 | lowpass=f=3000 |
| afade | 效果 | 淡入淡出 | afade=t=in:n=48000 |
| acrossfade | 效果 | 交叉淡入淡出 | acrossfade=d=1 |
| atempo | 变速 | 变速 | atempo=1.5 |
| aresample | 重采样 | 重采样 | aresample=44100 |
| amix | 混合 | 混合 | amix=inputs=2 |
| amerge | 合并 | 合并 | amerge=inputs=2 |
| arnndn | 降噪 | RNN降噪 | arnndn=model=rnnn48k.rnnn |
| afftdn | 降噪 | 频域降噪 | afftdn=nf=-20 |
| reverb | 效果 | 混响 | reverb=2.0:2.0:1000:0.5 |
| chorus | 效果 | 合唱 | chorus=0.6:0.9:50|60|40 |

### A.3 滤镜性能对比

| 滤镜 | 性能影响 | 建议优化方式 |
|------|----------|--------------|
| scale | 低 | 使用硬件加速 |
| crop | 低 | 优先执行 |
| gblur | 中 | 降低sigma值 |
| sharpen | 低 | 使用默认参数 |
| lut3d | 中 | 使用较小LUT |
| overlay | 中 | 优化叠加顺序 |
| concat | 低 | 使用segment模式 |
| eq | 低 | 合并多个调整 |
| hstack/vstack | 中 | 限制输入数量 |
| xfade | 中 | 使用简单转场 |