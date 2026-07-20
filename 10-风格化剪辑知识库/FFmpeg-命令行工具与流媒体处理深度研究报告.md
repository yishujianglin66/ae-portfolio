# FFmpeg 命令行工具与流媒体处理深度研究报告

> 适用版本：FFmpeg 7.0 | 更新日期：2026-07-14 | 分类：视频处理知识库

---

## 目录

- [一、FFmpeg架构体系](#一ffmpeg架构体系)
- [二、命令行工具与基础用法](#二命令行工具与基础用法)
- [三、视频编码与解码技术](#三视频编码与解码技术)
- [四、滤镜系统与效果处理](#四滤镜系统与效果处理)
- [五、音频处理与编码](#五音频处理与编码)
- [六、流媒体与网络传输](#六流媒体与网络传输)
- [七、Python API与自动化集成](#七python-api与自动化集成)
- [八、编码理论与学术研究](#八编码理论与学术研究)

---

## 一、FFmpeg架构体系

### 1.1 系统架构设计

```python
class FFmpegArchitecture:
    VERSION = "7.0"
    
    COMPONENTS = {
        'libavcodec': '音视频编解码库',
        'libavformat': '多媒体容器格式库',
        'libavfilter': '滤镜处理库',
        'libavdevice': '设备输入输出库',
        'libavutil': '工具函数库',
        'libswscale': '图像缩放库',
        'libswresample': '音频重采样库',
        'libpostproc': '后处理库'
    }
    
    SUPPORTED_FORMATS = {
        'video': ['H.264', 'H.265/HEVC', 'AV1', 'VP9', 'MPEG-4', 'MPEG-2', 'WMV', 'ProRes'],
        'audio': ['AAC', 'MP3', 'WAV', 'FLAC', 'Opus', 'Vorbis', 'PCM'],
        'container': ['MP4', 'MKV', 'MOV', 'AVI', 'FLV', 'WebM', 'MPEG-TS', 'MPEG-PS']
    }
    
    def __init__(self):
        self.components = {}
        self.enabled_components = []
        
    def initialize_component(self, component_name):
        if component_name in self.COMPONENTS:
            self.components[component_name] = {
                'status': 'initialized',
                'description': self.COMPONENTS[component_name],
                'version': self.VERSION
            }
            self.enabled_components.append(component_name)
            return {'success': True, 'component': component_name}
        return {'success': False, 'error': f"Component {component_name} not found"}
    
    def get_component_info(self, component_name):
        return self.components.get(component_name, {'error': 'Component not found'})
    
    def list_supported_formats(self, media_type=None):
        if media_type:
            return self.SUPPORTED_FORMATS.get(media_type, [])
        return self.SUPPORTED_FORMATS
    
    def check_codec_support(self, codec_name):
        supported_codecs = {
            'video': ['h264', 'h265', 'hevc', 'av1', 'vp9', 'mpeg4', 'mpeg2video', 'prores'],
            'audio': ['aac', 'mp3', 'wav', 'flac', 'opus', 'vorbis', 'pcm_s16le']
        }
        
        codec_lower = codec_name.lower()
        for media_type, codecs in supported_codecs.items():
            if codec_lower in codecs:
                return {'supported': True, 'media_type': media_type, 'codec': codec_lower}
        return {'supported': False, 'codec': codec_lower}
```

### 1.2 核心数据结构

```python
class FFmpegDataStructures:
    class Stream:
        def __init__(self, stream_type, index):
            self.type = stream_type
            self.index = index
            self.codec = None
            self.codec_parameters = {}
            self.time_base = None
            self.duration = None
            self.frames = []
            
        def set_codec(self, codec_name, params=None):
            self.codec = codec_name
            self.codec_parameters = params or {}
            
        def add_frame(self, frame_data):
            self.frames.append({
                'data': frame_data,
                'timestamp': len(self.frames),
                'duration': 1
            })
            
    class Packet:
        def __init__(self):
            self.stream_index = None
            self.data = None
            self.pts = None
            self.dts = None
            self.duration = None
            self.size = None
            self.flags = 0
            
        def set_data(self, data, stream_index):
            self.data = data
            self.stream_index = stream_index
            self.size = len(data)
            
        def is_keyframe(self):
            return bool(self.flags & 0x01)
            
    class Frame:
        def __init__(self):
            self.width = 0
            self.height = 0
            self.format = None
            self.pts = None
            self.duration = None
            self.data = []
            self.linesize = []
            self.samples = 0
            self.sample_rate = 0
            self.channels = 0
            
        def set_video_params(self, width, height, format):
            self.width = width
            self.height = height
            self.format = format
            
        def set_audio_params(self, samples, sample_rate, channels):
            self.samples = samples
            self.sample_rate = sample_rate
            self.channels = channels
            
    class CodecContext:
        def __init__(self):
            self.codec = None
            self.width = 0
            self.height = 0
            self.pix_fmt = None
            self.bit_rate = 0
            self.frame_rate = None
            self.sample_rate = 0
            self.channels = 0
            self.sample_fmt = None
            self.time_base = None
            
        def configure_video(self, codec, width, height, bit_rate, frame_rate):
            self.codec = codec
            self.width = width
            self.height = height
            self.bit_rate = bit_rate
            self.frame_rate = frame_rate
            
        def configure_audio(self, codec, sample_rate, channels, bit_rate):
            self.codec = codec
            self.sample_rate = sample_rate
            self.channels = channels
            self.bit_rate = bit_rate
```

---

## 二、命令行工具与基础用法

### 2.1 基本命令结构

```python
class FFmpegCommandBuilder:
    def __init__(self):
        self.command = ['ffmpeg']
        self.inputs = []
        self.outputs = []
        self.options = []
        
    def add_input(self, input_path, params=None):
        params = params or {}
        
        input_spec = ['-i', input_path]
        
        if params.get('stream_loop'):
            input_spec.extend(['-stream_loop', str(params['stream_loop'])])
        if params.get('t'):
            input_spec.extend(['-t', str(params['t'])])
        if params.get('ss'):
            input_spec.extend(['-ss', str(params['ss'])])
        if params.get('framerate'):
            input_spec.extend(['-framerate', str(params['framerate'])])
        
        self.inputs.append({'path': input_path, 'params': params})
        self.command.extend(input_spec)
        
        return self
    
    def add_output(self, output_path, params=None):
        params = params or {}
        
        output_spec = [output_path]
        
        if params.get('c:v'):
            output_spec.extend(['-c:v', params['c:v']])
        if params.get('c:a'):
            output_spec.extend(['-c:a', params['c:a']])
        if params.get('b:v'):
            output_spec.extend(['-b:v', params['b:v']])
        if params.get('b:a'):
            output_spec.extend(['-b:a', params['b:a']])
        if params.get('r'):
            output_spec.extend(['-r', str(params['r'])])
        if params.get('s'):
            output_spec.extend(['-s', params['s']])
        if params.get('pix_fmt'):
            output_spec.extend(['-pix_fmt', params['pix_fmt']])
        if params.get('t'):
            output_spec.extend(['-t', str(params['t'])])
        if params.get('y'):
            output_spec.append('-y')
        if params.get('vn'):
            output_spec.append('-vn')
        if params.get('an'):
            output_spec.append('-an')
        
        self.outputs.append({'path': output_path, 'params': params})
        self.command.extend(output_spec)
        
        return self
    
    def add_option(self, option, value=None):
        if value is not None:
            self.command.extend([option, str(value)])
        else:
            self.command.append(option)
        self.options.append({'option': option, 'value': value})
        return self
    
    def add_filter(self, filter_complex):
        self.command.extend(['-filter_complex', filter_complex])
        return self
    
    def build(self):
        return ' '.join(self.command)
    
    def reset(self):
        self.command = ['ffmpeg']
        self.inputs = []
        self.outputs = []
        self.options = []
        return self
```

### 2.2 常用命令示例

```python
class FFmpegCommonCommands:
    @staticmethod
    def convert_video(input_path, output_path, codec='libx264', bitrate='5M'):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_output(output_path, {
                          'c:v': codec,
                          'b:v': bitrate,
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def extract_audio(input_path, output_path, codec='aac', bitrate='192k'):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_output(output_path, {
                          'c:a': codec,
                          'b:a': bitrate,
                          'vn': True,
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def extract_frames(input_path, output_pattern, frame_rate=1):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_output(output_pattern, {
                          'r': frame_rate,
                          'f': 'image2',
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def resize_video(input_path, output_path, width, height):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_output(output_path, {
                          's': f"{width}x{height}",
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def trim_video(input_path, output_path, start_time, duration):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path, {'ss': start_time}) \
                      .add_output(output_path, {
                          't': duration,
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def concat_videos(input_list, output_path):
        list_content = "\n".join([f"file '{path}'" for path in input_list])
        list_file = 'concat_list.txt'
        
        with open(list_file, 'w') as f:
            f.write(list_content)
        
        builder = FFmpegCommandBuilder()
        return builder.add_input(list_file, {'f': 'concat', 'safe': 0}) \
                      .add_output(output_path, {
                          'c': 'copy',
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def add_watermark(input_path, output_path, watermark_path, position='top-right'):
        position_map = {
            'top-left': '0:0',
            'top-right': 'main_w-overlay_w:0',
            'bottom-left': '0:main_h-overlay_h',
            'bottom-right': 'main_w-overlay_w:main_h-overlay_h',
            'center': '(main_w-overlay_w)/2:(main_h-overlay_h)/2'
        }
        
        filter_complex = f"overlay={position_map.get(position, '0:0')}"
        
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_input(watermark_path) \
                      .add_filter(filter_complex) \
                      .add_output(output_path, {'y': True}) \
                      .build()
    
    @staticmethod
    def encode_h265(input_path, output_path, bitrate='5M', preset='medium'):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_output(output_path, {
                          'c:v': 'libx265',
                          'b:v': bitrate,
                          'preset': preset,
                          'crf': 23,
                          'y': True
                      }) \
                      .build()
    
    @staticmethod
    def encode_av1(input_path, output_path, bitrate='3M', cpu_used=4):
        builder = FFmpegCommandBuilder()
        return builder.add_input(input_path) \
                      .add_output(output_path, {
                          'c:v': 'libaom-av1',
                          'b:v': bitrate,
                          'cpu-used': cpu_used,
                          'crf': 30,
                          'y': True
                      }) \
                      .build()
```

---

## 三、视频编码与解码技术

### 3.1 H.264编码参数详解

```python
class H264Encoder:
    PRESETS = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 
               'medium', 'slow', 'slower', 'veryslow', 'placebo']
    
    PROFILES = ['baseline', 'main', 'high', 'high10', 'high422', 'high444']
    
    LEVELS = ['1', '1b', '1.1', '1.2', '1.3', '2', '2.1', '2.2', '3', '3.1', 
              '3.2', '4', '4.1', '4.2', '5', '5.1', '5.2']
    
    def __init__(self):
        self.settings = {}
        
    def configure(self, params):
        self.settings = {
            'preset': params.get('preset', 'medium'),
            'crf': params.get('crf', 23),
            'profile': params.get('profile', 'high'),
            'level': params.get('level', '4.1'),
            'bitrate': params.get('bitrate'),
            'maxrate': params.get('maxrate'),
            'bufsize': params.get('bufsize'),
            'gop_size': params.get('gop_size', 250),
            'keyint_min': params.get('keyint_min', 25),
            'scenecut': params.get('scenecut', 40),
            'intra_refresh': params.get('intra_refresh', 0),
            'bframes': params.get('bframes', 3),
            'b_pyramid': params.get('b_pyramid', 'normal'),
            'weightp': params.get('weightp', 2),
            'weightb': params.get('weightb', 1),
            'trellis': params.get('trellis', 1),
            'ref': params.get('ref', 4),
            'mixed_refs': params.get('mixed_refs', 1),
            'me_method': params.get('me_method', 'hex'),
            'me_range': params.get('me_range', 16),
            'subq': params.get('subq', 7),
            'partitions': params.get('partitions', 'all'),
            'direct_pred': params.get('direct_pred', 'auto'),
            'fast_pskip': params.get('fast_pskip', 1),
            'aud': params.get('aud', 0),
            'nal_hrd': params.get('nal_hrd', 'none'),
            'filler': params.get('filler', 0),
            'rc_lookahead': params.get('rc_lookahead', 40),
            'aq_mode': params.get('aq_mode', 1),
            'aq_strength': params.get('aq_strength', 1.0),
            'deblock': params.get('deblock', '1:1'),
            'psy': params.get('psy', 1),
            'psy_rd': params.get('psy_rd', '1.0:0.0'),
            'psy_rdoq': params.get('psy_rdoq', '1.0'),
            'chroma_qp_offset': params.get('chroma_qp_offset', 0),
            'deadzone_inter': params.get('deadzone_inter', 21),
            'deadzone_intra': params.get('deadzone_intra', 11),
            'fast_pskip': params.get('fast_pskip', 1),
            'mbtree': params.get('mbtree', 1),
            'lookahead_threads': params.get('lookahead_threads', 0),
            'threads': params.get('threads', 0)
        }
        
        return self.settings
    
    def generate_command(self, input_path, output_path):
        cmd = ['ffmpeg', '-i', input_path]
        
        cmd.extend(['-c:v', 'libx264'])
        
        if self.settings.get('preset'):
            cmd.extend(['-preset', self.settings['preset']])
        if self.settings.get('crf'):
            cmd.extend(['-crf', str(self.settings['crf'])])
        if self.settings.get('profile'):
            cmd.extend(['-profile:v', self.settings['profile']])
        if self.settings.get('level'):
            cmd.extend(['-level', self.settings['level']])
        if self.settings.get('bitrate'):
            cmd.extend(['-b:v', self.settings['bitrate']])
        if self.settings.get('maxrate'):
            cmd.extend(['-maxrate', self.settings['maxrate']])
        if self.settings.get('bufsize'):
            cmd.extend(['-bufsize', self.settings['bufsize']])
        if self.settings.get('gop_size'):
            cmd.extend(['-g', str(self.settings['gop_size'])])
        if self.settings.get('bframes'):
            cmd.extend(['-bf', str(self.settings['bframes'])])
        if self.settings.get('ref'):
            cmd.extend(['-refs', str(self.settings['ref'])])
        if self.settings.get('aq_mode'):
            cmd.extend(['-aq-mode', str(self.settings['aq_mode'])])
        
        cmd.extend(['-y', output_path])
        
        return ' '.join(cmd)
    
    def estimate_bitrate(self, duration_seconds, target_size_mb):
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        bitrate_bps = target_size_bits / duration_seconds
        bitrate_kbps = int(bitrate_bps / 1000)
        
        return f"{bitrate_kbps}k"
```

### 3.2 H.265/HEVC编码参数详解

```python
class H265Encoder:
    PRESETS = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 
               'medium', 'slow', 'slower', 'veryslow']
    
    PROFILES = ['main', 'main10', 'main422', 'main444']
    
    def __init__(self):
        self.settings = {}
        
    def configure(self, params):
        self.settings = {
            'preset': params.get('preset', 'medium'),
            'crf': params.get('crf', 28),
            'profile': params.get('profile', 'main10'),
            'bitrate': params.get('bitrate'),
            'maxrate': params.get('maxrate'),
            'bufsize': params.get('bufsize'),
            'gop_size': params.get('gop_size', 250),
            'keyint_min': params.get('keyint_min', 25),
            'scenecut': params.get('scenecut', 40),
            'bframes': params.get('bframes', 4),
            'b_pyramid': params.get('b_pyramid', '1'),
            'weightp': params.get('weightp', '1'),
            'weightb': params.get('weightb', '1'),
            'rc_lookahead': params.get('rc_lookahead', 25),
            'aq_mode': params.get('aq_mode', 1),
            'aq_strength': params.get('aq_strength', 1.0),
            'aq_temporal': params.get('aq_temporal', 1),
            'cutree': params.get('cutree', 1),
            'intra_du': params.get('intra_du', 1),
            'inter_du': params.get('inter_du', 1),
            'me': params.get('me', 'hex'),
            'merange': params.get('merange', 57),
            'subme': params.get('subme', 5),
            'rect': params.get('rect', 1),
            'amp': params.get('amp', 1),
            'early_skip': params.get('early_skip', 1),
            'rdoq_level': params.get('rdoq_level', 2),
            'rdoq_strength': params.get('rdoq_strength', 1.0),
            'rd_refine': params.get('rd_refine', 2),
            'limit_refs': params.get('limit_refs', 3),
            'limit_modes': params.get('limit_modes', 0),
            'max_merge': params.get('max_merge', 5),
            'tskip': params.get('tskip', 1),
            'tskipfast': params.get('tskipfast', 1),
            'cu_lossless': params.get('cu_lossless', 0),
            'no_sao': params.get('no_sao', 0),
            'strong_intra_smoothing': params.get('strong_intra_smoothing', 0),
            'signhide': params.get('signhide', 1),
            'deblock': params.get('deblock', '-1:-1'),
            'sao': params.get('sao', 1),
            'sao_non_deblock': params.get('sao_non_deblock', 0),
            'b_intra': params.get('b_intra', 0),
            'b_open_gop': params.get('b_open_gop', 0),
            'bframe_bias': params.get('bframe_bias', 0),
            'hrd': params.get('hrd', 'none'),
            'filler': params.get('filler', 0),
            'frames_ref': params.get('frames_ref', 3),
            'low_delay': params.get('low_delay', 0),
            'repeat_headers': params.get('repeat_headers', 0),
            'aud': params.get('aud', 0),
            'info': params.get('info', '0'),
            'fps': params.get('fps')
        }
        
        return self.settings
    
    def generate_command(self, input_path, output_path):
        cmd = ['ffmpeg', '-i', input_path]
        
        cmd.extend(['-c:v', 'libx265'])
        
        if self.settings.get('preset'):
            cmd.extend(['-preset', self.settings['preset']])
        if self.settings.get('crf'):
            cmd.extend(['-crf', str(self.settings['crf'])])
        if self.settings.get('profile'):
            cmd.extend(['-profile:v', self.settings['profile']])
        if self.settings.get('bitrate'):
            cmd.extend(['-b:v', self.settings['bitrate']])
        if self.settings.get('gop_size'):
            cmd.extend(['-g', str(self.settings['gop_size'])])
        if self.settings.get('bframes'):
            cmd.extend(['-bf', str(self.settings['bframes'])])
        
        cmd.extend(['-y', output_path])
        
        return ' '.join(cmd)
```

### 3.3 AV1编码参数详解

```python
class AV1Encoder:
    CPU_USED_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8]
    
    def __init__(self):
        self.settings = {}
        
    def configure(self, params):
        self.settings = {
            'cpu_used': params.get('cpu_used', 4),
            'crf': params.get('crf', 30),
            'bitrate': params.get('bitrate'),
            'maxrate': params.get('maxrate'),
            'bufsize': params.get('bufsize'),
            'gop_size': params.get('gop_size', 240),
            'keyint_min': params.get('keyint_min', 0),
            'tile_rows': params.get('tile_rows', 0),
            'tile_cols': params.get('tile_cols', 0),
            'threads': params.get('threads', 0),
            'row_mt': params.get('row_mt', 1),
            'frame_parallel': params.get('frame_parallel', 1),
            'auto-alt-ref': params.get('auto-alt-ref', 1),
            'lag-in-frames': params.get('lag_in_frames', 25),
            'arnr-maxframes': params.get('arnr_maxframes', 7),
            'arnr-strength': params.get('arnr_strength', 5),
            'arnr-type': params.get('arnr_type', 'centered'),
            'sharpness': params.get('sharpness', 0),
            'tune-content': params.get('tune_content', 'default'),
            'lossless': params.get('lossless', 0),
            'error-resilient': params.get('error_resilient', 0),
            'enable-dnl-denoising': params.get('enable_dnl_denoising', 1),
            'enable-chroma-dnl': params.get('enable_chroma_dnl', 1),
            'disable-cdef': params.get('disable_cdef', 0),
            'disable-loopfilter': params.get('disable_loopfilter', 0),
            'quant-b-adapt': params.get('quant_b_adapt', 1),
            'delta-q-mode': params.get('delta_q_mode', 0),
            'delta-q-strength': params.get('delta_q_strength', 1.0),
            'min-q': params.get('min_q', 0),
            'max-q': params.get('max_q', 255),
            'cq-level': params.get('cq_level'),
            'rate-control': params.get('rate_control', 'q')
        }
        
        return self.settings
    
    def generate_command(self, input_path, output_path):
        cmd = ['ffmpeg', '-i', input_path]
        
        cmd.extend(['-c:v', 'libaom-av1'])
        
        if self.settings.get('cpu_used'):
            cmd.extend(['-cpu-used', str(self.settings['cpu_used'])])
        if self.settings.get('crf'):
            cmd.extend(['-crf', str(self.settings['crf'])])
        if self.settings.get('bitrate'):
            cmd.extend(['-b:v', self.settings['bitrate']])
        if self.settings.get('gop_size'):
            cmd.extend(['-g', str(self.settings['gop_size'])])
        if self.settings.get('tile_rows'):
            cmd.extend(['-tile-rows', str(self.settings['tile_rows'])])
        if self.settings.get('tile_cols'):
            cmd.extend(['-tile-cols', str(self.settings['tile_cols'])])
        if self.settings.get('threads'):
            cmd.extend(['-threads', str(self.settings['threads'])])
        if self.settings.get('lag_in_frames'):
            cmd.extend(['-lag-in-frames', str(self.settings['lag_in_frames'])])
        
        cmd.extend(['-y', output_path])
        
        return ' '.join(cmd)
```

---

## 四、滤镜系统与效果处理

### 4.1 滤镜架构与语法

```python
class FFmpegFilterSystem:
    FILTER_CATEGORIES = {
        'video': ['scale', 'crop', 'rotate', 'transpose', 'flip', 'hflip', 'vflip',
                  'overlay', 'drawtext', 'boxblur', 'gblur', 'smartblur', 'sharpen',
                  'eq', 'colorchannelmixer', 'hue', 'saturation', 'contrast', 'brightness',
                  'fps', 'decimate', 'setpts', 'settb', 'trim', 'atrim', 'concat'],
        'audio': ['volume', 'pan', 'stereotools', 'equalizer', 'bass', 'treble',
                  'acompressor', 'adelay', 'acrossfade', 'apad', 'aresample'],
        'overlay': ['overlay', 'blend', 'overlay_cuda'],
        'color': ['color', 'palettegen', 'paletteuse', 'colorkey'],
        'transform': ['scale', 'crop', 'transpose', 'rotate', 'zoompan'],
        'effect': ['vignette', 'unsharp', 'hqdn3d', 'deband', 'gradfun']
    }
    
    def __init__(self):
        self.filters = []
        
    def add_filter(self, filter_name, params=None):
        params = params or {}
        
        filter_spec = filter_name
        
        if params:
            param_list = []
            for key, value in params.items():
                if isinstance(value, bool):
                    param_list.append(f"{key}={1 if value else 0}")
                elif isinstance(value, (int, float)):
                    param_list.append(f"{key}={value}")
                else:
                    param_list.append(f"{key}='{value}'")
            
            filter_spec += ':' + ':'.join(param_list)
        
        self.filters.append(filter_spec)
        return self
    
    def add_chain(self, filters):
        self.filters.extend(filters)
        return self
    
    def build_complex(self, inputs=None, outputs=None):
        inputs = inputs or ['[0:v]']
        outputs = outputs or ['[outv]']
        
        filter_str = ''
        
        if len(inputs) > 1:
            filter_str = ';'.join(inputs) + ';'
        
        filter_str += ','.join(self.filters)
        
        if outputs:
            filter_str += ''.join(outputs)
        
        return filter_str
    
    def build_simple(self):
        return ','.join(self.filters)
    
    def reset(self):
        self.filters = []
        return self
```

### 4.2 常用滤镜示例

```python
class FFmpegFilterExamples:
    @staticmethod
    def create_vignette(strength=0.5):
        return f"vignette=PI/4:{strength}:0:0:1"
    
    @staticmethod
    def create_blur(radius=5):
        return f"boxblur=luma_radius={radius}:chroma_radius={radius}"
    
    @staticmethod
    def create_sharpen(amount=1.0):
        return f"unsharp=5:5:{amount}"
    
    @staticmethod
    def create_color_correction(brightness=0, contrast=0, saturation=0, hue=0):
        filters = []
        if brightness != 0:
            filters.append(f"eq=brightness={brightness}")
        if contrast != 0:
            filters.append(f"eq=contrast={contrast}")
        if saturation != 0:
            filters.append(f"eq=saturation={saturation}")
        if hue != 0:
            filters.append(f"hue=h={hue}")
        return ','.join(filters)
    
    @staticmethod
    def create_text_overlay(text, x=10, y=10, fontsize=24, color='white'):
        return f"drawtext=text='{text}':x={x}:y={y}:fontsize={fontsize}:fontcolor={color}"
    
    @staticmethod
    def create_logo_overlay(logo_path, x=10, y=10, alpha=1.0):
        return f"overlay={x}:{y}:format=yuv420:alpha={alpha}"
    
    @staticmethod
    def create_fade_in(duration=1):
        return f"fade=t=in:st=0:d={duration}"
    
    @staticmethod
    def create_fade_out(start_time, duration=1):
        return f"fade=t=out:st={start_time}:d={duration}"
    
    @staticmethod
    def create_crossfade(duration=1):
        return f"xfade=transition=fade:d={duration}"
    
    @staticmethod
    def create_speed_effect(speed=2.0):
        atempo = min(speed, 2.0)
        return f"setpts=PTS/{speed},atempo={atempo}"
    
    @staticmethod
    def create_reverse():
        return "reverse"
    
    @staticmethod
    def create_loop(count=2):
        return f"loop=loop={count}:size=0:start=0"
    
    @staticmethod
    def create_frame_rate_conversion(fps=24):
        return f"fps=fps={fps}"
    
    @staticmethod
    def create_deinterlace():
        return "yadif"
    
    @staticmethod
    def create_denoise():
        return "hqdn3d"
    
    @staticmethod
    def create_deband():
        return "deband"
    
    @staticmethod
    def create_color_key(key_color='green', similarity=0.1):
        return f"colorkey=color={key_color}:similarity={similarity}:blend=0.1"
    
    @staticmethod
    def create_chroma_key(key_color='green', threshold=0.1):
        return f"chromakey=color={key_color}:similarity={threshold}:blend=0.1"
    
    @staticmethod
    def create_gradual_zoom(start_zoom=1.0, end_zoom=1.5, duration=10):
        return f"zoompan=z='{start_zoom}+({end_zoom}-{start_zoom})*t/{duration}':d=1"
    
    @staticmethod
    def create_pan_zoom(x='(iw/2)', y='(ih/2)', zoom=1.2):
        return f"zoompan=z={zoom}:x={x}:y={y}:d=1"
```

### 4.3 复杂滤镜链构建

```python
class ComplexFilterBuilder:
    def __init__(self):
        self.filter_chains = {}
        self.inputs = {}
        self.outputs = {}
        self.next_label_id = 0
        
    def add_input(self, name, spec):
        self.inputs[name] = spec
        return self
    
    def add_output(self, name, spec):
        self.outputs[name] = spec
        return self
    
    def create_chain(self, chain_name, filters):
        label = f"[v{self.next_label_id}]"
        self.next_label_id += 1
        
        chain_str = ','.join(filters) + label
        self.filter_chains[chain_name] = {
            'filters': filters,
            'output_label': label,
            'chain_str': chain_str
        }
        
        return label
    
    def link_chains(self, chains):
        result = []
        for chain in chains:
            if chain in self.filter_chains:
                result.append(self.filter_chains[chain]['chain_str'])
        return ';'.join(result)
    
    def build(self):
        parts = []
        
        for input_name, spec in self.inputs.items():
            parts.append(spec)
        
        for chain_name, chain_data in self.filter_chains.items():
            parts.append(chain_data['chain_str'])
        
        for output_name, spec in self.outputs.items():
            parts.append(spec)
        
        return ';'.join(parts)
    
    def build_color_grading(self, input_label='[0:v]'):
        filters = [
            'eq=contrast=1.1:brightness=0.05',
            'colorchannelmixer=rr=1:rg=0:rb=0:gr=0:gg=1.1:gb=0:br=0:bg=0:bb=1',
            'saturation=1.2',
            'hue=h=-5',
            'vignette=PI/4:0.3'
        ]
        return self.create_chain('color_grading', filters)
    
    def build_watermark(self, input_label='[0:v]', watermark_input='[1:v]'):
        filters = [
            f"{watermark_input}scale=100:100[wm]",
            f"{input_label}[wm]overlay=W-w-10:H-h-10"
        ]
        return self.create_chain('watermark', filters)
    
    def build_composite(self, main_input='[0:v]', overlay_input='[1:v]', position='center'):
        position_map = {
            'top-left': '0:0',
            'top-right': 'W-w:0',
            'bottom-left': '0:H-h',
            'bottom-right': 'W-w:H-h',
            'center': '(W-w)/2:(H-h)/2'
        }
        
        filters = [
            f"{main_input}{overlay_input}overlay={position_map[position]}"
        ]
        return self.create_chain('composite', filters)
```

---

## 五、音频处理与编码

### 5.1 音频编码参数详解

```python
class AudioEncoder:
    CODECS = {
        'aac': {'bitrates': ['64k', '96k', '128k', '192k', '256k', '320k'], 'quality': ['low', 'medium', 'high']},
        'mp3': {'bitrates': ['64k', '96k', '128k', '192k', '256k', '320k'], 'quality': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']},
        'opus': {'bitrates': ['64k', '96k', '128k', '192k', '256k'], 'quality': ['0', '1', '2', '3', '4', '5', '6', '7']},
        'flac': {'bitrates': ['auto'], 'quality': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']},
        'wav': {'bitrates': ['auto'], 'quality': ['pcm_s16le', 'pcm_s24le', 'pcm_f32le']}
    }
    
    def __init__(self):
        self.settings = {}
        
    def configure(self, codec, params):
        if codec not in self.CODECS:
            return {'error': f"Codec {codec} not supported"}
        
        self.settings = {
            'codec': codec,
            'bitrate': params.get('bitrate'),
            'quality': params.get('quality'),
            'sample_rate': params.get('sample_rate', 44100),
            'channels': params.get('channels', 2),
            'sample_fmt': params.get('sample_fmt', 's16'),
            'cutoff': params.get('cutoff'),
            'profile': params.get('profile')
        }
        
        return self.settings
    
    def generate_command(self, input_path, output_path):
        cmd = ['ffmpeg', '-i', input_path]
        
        cmd.extend(['-c:a', self.settings['codec']])
        
        if self.settings.get('bitrate'):
            cmd.extend(['-b:a', self.settings['bitrate']])
        if self.settings.get('quality'):
            cmd.extend(['-q:a', str(self.settings['quality'])])
        if self.settings.get('sample_rate'):
            cmd.extend(['-ar', str(self.settings['sample_rate'])])
        if self.settings.get('channels'):
            cmd.extend(['-ac', str(self.settings['channels'])])
        if self.settings.get('sample_fmt'):
            cmd.extend(['-sample_fmt', self.settings['sample_fmt']])
        if self.settings.get('cutoff'):
            cmd.extend(['-cutoff', str(self.settings['cutoff'])])
        if self.settings.get('profile'):
            cmd.extend(['-profile:a', self.settings['profile']])
        
        cmd.extend(['-vn', '-y', output_path])
        
        return ' '.join(cmd)
    
    def get_codec_info(self, codec):
        return self.CODECS.get(codec, {'error': 'Codec not found'})
```

### 5.2 音频滤镜与效果

```python
class AudioFilterSystem:
    FILTERS = {
        'volume': {'description': '音量控制', 'params': ['volume', 'replaygain', 'eval']},
        'equalizer': {'description': '均衡器', 'params': ['f', 't', 'w', 'g', 'Q']},
        'bass': {'description': '低音增强', 'params': ['gain', 'frequency', 'width']},
        'treble': {'description': '高音增强', 'params': ['gain', 'frequency', 'width']},
        'acompressor': {'description': '音频压缩器', 'params': ['threshold', 'ratio', 'attack', 'release']},
        'adegain': {'description': '自动增益控制', 'params': ['type', 'target', 'maxgain', 'mingain']},
        'adelay': {'description': '音频延迟', 'params': ['delays', 'all']},
        'acrossfade': {'description': '交叉淡入淡出', 'params': ['duration', 'overlap', 'curve']},
        'apad': {'description': '音频填充', 'params': ['pad_dur', 'pad_start', 'pad_end']},
        'aresample': {'description': '音频重采样', 'params': ['sample_rate', 'format', 'resampler']},
        'pan': {'description': '声道映射', 'params': ['channel_layout', 'map']},
        'stereotools': {'description': '立体声工具', 'params': ['mode', 'balance_in', 'balance_out']},
        'silencedetect': {'description': '静音检测', 'params': ['n', 'd']},
        'afftdn': {'description': '频域降噪', 'params': ['nf', 'tnf', 'rf']},
        'highpass': {'description': '高通滤波器', 'params': ['frequency', 'width']},
        'lowpass': {'description': '低通滤波器', 'params': ['frequency', 'width']}
    }
    
    def __init__(self):
        self.filters = []
        
    def add_filter(self, filter_name, params=None):
        params = params or {}
        
        filter_spec = filter_name
        
        if params:
            param_list = []
            for key, value in params.items():
                if isinstance(value, bool):
                    param_list.append(f"{key}={1 if value else 0}")
                else:
                    param_list.append(f"{key}={value}")
            
            if param_list:
                filter_spec += '=' + ':'.join(param_list)
        
        self.filters.append(filter_spec)
        return self
    
    def build(self):
        return ','.join(self.filters)
    
    def reset(self):
        self.filters = []
        return self
    
    def create_equalizer_preset(self, preset='flat'):
        presets = {
            'flat': [],
            'bass_boost': ['equalizer=f=60:t=q:w=1:g=5', 'equalizer=f=120:t=q:w=1:g=3'],
            'treble_boost': ['equalizer=f=2000:t=q:w=1:g=3', 'equalizer=f=5000:t=q:w=1:g=5'],
            'vocal_boost': ['equalizer=f=1000:t=q:w=1:g=3', 'equalizer=f=2000:t=q:w=1:g=4'],
            'noise_reduction': ['afftdn=nf=-20:tnf=-20']
        }
        
        self.filters.extend(presets.get(preset, []))
        return self
    
    def create_fade_effect(self, type='in', duration=1):
        if type == 'in':
            self.add_filter('afade', {'t': 'in', 'st': 0, 'd': duration})
        elif type == 'out':
            self.add_filter('afade', {'t': 'out', 'st': 0, 'd': duration})
        return self
    
    def create_volume_effect(self, volume=1.0):
        self.add_filter('volume', {'volume': volume})
        return self
    
    def create_compressor(self, threshold=-20, ratio=4.0, attack=5, release=50):
        self.add_filter('acompressor', {
            'threshold': f'{threshold}dB',
            'ratio': ratio,
            'attack': attack,
            'release': release
        })
        return self
```

---

## 六、流媒体与网络传输

### 6.1 RTMP流媒体推流

```python
class RTMPStreamer:
    def __init__(self):
        self.settings = {}
        
    def configure(self, params):
        self.settings = {
            'rtmp_url': params.get('rtmp_url'),
            'stream_key': params.get('stream_key'),
            'video_codec': params.get('video_codec', 'libx264'),
            'audio_codec': params.get('audio_codec', 'aac'),
            'video_bitrate': params.get('video_bitrate', '2500k'),
            'audio_bitrate': params.get('audio_bitrate', '192k'),
            'fps': params.get('fps', 30),
            'resolution': params.get('resolution', '1280x720'),
            'gop_size': params.get('gop_size', 60),
            'preset': params.get('preset', 'fast'),
            'crf': params.get('crf', 23),
            'bufsize': params.get('bufsize', '5000k'),
            'maxrate': params.get('maxrate', '2500k'),
            'threads': params.get('threads', 4),
            'live': params.get('live', True),
            'metadata': params.get('metadata', {})
        }
        
        return self.settings
    
    def generate_push_command(self, input_source):
        if not self.settings.get('rtmp_url'):
            return {'error': 'RTMP URL is required'}
        
        cmd = ['ffmpeg']
        
        if isinstance(input_source, list):
            for src in input_source:
                cmd.extend(['-i', src])
        else:
            cmd.extend(['-i', input_source])
        
        cmd.extend([
            '-c:v', self.settings['video_codec'],
            '-c:a', self.settings['audio_codec'],
            '-b:v', self.settings['video_bitrate'],
            '-b:a', self.settings['audio_bitrate'],
            '-r', str(self.settings['fps']),
            '-s', self.settings['resolution'],
            '-g', str(self.settings['gop_size']),
            '-preset', self.settings['preset'],
            '-crf', str(self.settings['crf']),
            '-maxrate', self.settings['maxrate'],
            '-bufsize', self.settings['bufsize'],
            '-threads', str(self.settings['threads']),
            '-f', 'flv'
        ])
        
        if self.settings.get('live'):
            cmd.append('-re')
        
        rtmp_url = self.settings['rtmp_url']
        if self.settings.get('stream_key'):
            rtmp_url += '/' + self.settings['stream_key']
        
        cmd.append(rtmp_url)
        
        return ' '.join(cmd)
    
    def generate_pull_command(self, output_path):
        if not self.settings.get('rtmp_url'):
            return {'error': 'RTMP URL is required'}
        
        cmd = ['ffmpeg', '-i', self.settings['rtmp_url']]
        
        cmd.extend([
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-f', 'flv',
            '-y', output_path
        ])
        
        return ' '.join(cmd)
    
    def generate_hls_command(self, input_source, hls_path):
        cmd = ['ffmpeg', '-i', input_source]
        
        cmd.extend([
            '-c:v', self.settings['video_codec'],
            '-c:a', self.settings['audio_codec'],
            '-b:v', self.settings['video_bitrate'],
            '-b:a', self.settings['audio_bitrate'],
            '-r', str(self.settings['fps']),
            '-s', self.settings['resolution'],
            '-g', str(self.settings['gop_size']),
            '-preset', self.settings['preset'],
            '-crf', str(self.settings['crf']),
            '-hls_time', '2',
            '-hls_list_size', '6',
            '-hls_flags', 'delete_segments',
            '-hls_segment_filename', f'{hls_path}/segment_%03d.ts',
            '-f', 'hls',
            f'{hls_path}/stream.m3u8'
        ])
        
        return ' '.join(cmd)
```

### 6.2 HLS流媒体处理

```python
class HLSStreamer:
    def __init__(self):
        self.settings = {}
        
    def configure(self, params):
        self.settings = {
            'hls_time': params.get('hls_time', 2),
            'hls_list_size': params.get('hls_list_size', 6),
            'hls_flags': params.get('hls_flags', 'delete_segments'),
            'hls_segment_filename': params.get('hls_segment_filename'),
            'hls_base_url': params.get('hls_base_url'),
            'hls_allow_cache': params.get('hls_allow_cache', 1),
            'hls_segment_type': params.get('hls_segment_type', 'mpegts'),
            'hls_key_info_file': params.get('hls_key_info_file'),
            'hls_master_pl_name': params.get('hls_master_pl_name'),
            'video_codec': params.get('video_codec', 'libx264'),
            'audio_codec': params.get('audio_codec', 'aac'),
            'video_bitrate': params.get('video_bitrate', '2500k'),
            'audio_bitrate': params.get('audio_bitrate', '192k'),
            'fps': params.get('fps', 30),
            'resolution': params.get('resolution', '1280x720'),
            'preset': params.get('preset', 'fast'),
            'crf': params.get('crf', 23)
        }
        
        return self.settings
    
    def generate_master_playlist(self, variants):
        playlist = "#EXTM3U\n"
        playlist += "#EXT-X-VERSION:3\n\n"
        
        for variant in variants:
            playlist += f"#EXT-X-STREAM-INF:BANDWIDTH={variant['bandwidth']},"
            playlist += f"RESOLUTION={variant['resolution']},"
            playlist += f"CODECS=\"{variant['codecs']}\"\n"
            playlist += f"{variant['url']}\n\n"
        
        return playlist
    
    def generate_encode_command(self, input_path, output_path):
        cmd = ['ffmpeg', '-i', input_path]
        
        cmd.extend([
            '-c:v', self.settings['video_codec'],
            '-c:a', self.settings['audio_codec'],
            '-b:v', self.settings['video_bitrate'],
            '-b:a', self.settings['audio_bitrate'],
            '-r', str(self.settings['fps']),
            '-s', self.settings['resolution'],
            '-preset', self.settings['preset'],
            '-crf', str(self.settings['crf']),
            '-hls_time', str(self.settings['hls_time']),
            '-hls_list_size', str(self.settings['hls_list_size']),
            '-hls_flags', self.settings['hls_flags']
        ])
        
        if self.settings.get('hls_segment_filename'):
            cmd.extend(['-hls_segment_filename', self.settings['hls_segment_filename']])
        if self.settings.get('hls_base_url'):
            cmd.extend(['-hls_base_url', self.settings['hls_base_url']])
        if self.settings.get('hls_key_info_file'):
            cmd.extend(['-hls_key_info_file', self.settings['hls_key_info_file']])
        
        cmd.extend(['-f', 'hls', '-y', output_path])
        
        return ' '.join(cmd)
    
    def generate_variants_command(self, input_path, output_dir, variants):
        commands = []
        
        for variant in variants:
            cmd = ['ffmpeg', '-i', input_path]
            
            cmd.extend([
                '-c:v', self.settings['video_codec'],
                '-c:a', self.settings['audio_codec'],
                '-b:v', variant['bitrate'],
                '-b:a', self.settings['audio_bitrate'],
                '-r', str(variant.get('fps', self.settings['fps'])),
                '-s', variant['resolution'],
                '-preset', self.settings['preset'],
                '-crf', str(self.settings['crf']),
                '-hls_time', str(self.settings['hls_time']),
                '-hls_list_size', str(self.settings['hls_list_size']),
                '-hls_flags', self.settings['hls_flags'],
                '-hls_segment_filename', f'{output_dir}/{variant["name"]}_segment_%03d.ts',
                '-f', 'hls',
                '-y', f'{output_dir}/{variant["name"]}.m3u8'
            ])
            
            commands.append(' '.join(cmd))
        
        return commands
```

---

## 七、Python API与自动化集成

### 7.1 Python Subprocess封装

```python
import subprocess
import shlex
import json
import os

class FFmpegPythonAPI:
    def __init__(self):
        self.ffmpeg_path = 'ffmpeg'
        self.ffprobe_path = 'ffprobe'
        self.output_dir = '.'
        
    def set_ffmpeg_path(self, path):
        self.ffmpeg_path = path
        return self
    
    def set_output_dir(self, path):
        self.output_dir = path
        os.makedirs(path, exist_ok=True)
        return self
    
    def run_command(self, command, capture_output=True):
        if isinstance(command, list):
            cmd = command
        else:
            cmd = shlex.split(command)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': result.stderr,
                    'stdout': result.stdout,
                    'returncode': result.returncode
                }
            
            return {
                'success': True,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Command timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_video_info(self, file_path):
        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            file_path
        ]
        
        result = self.run_command(cmd)
        
        if result['success']:
            try:
                info = json.loads(result['stdout'])
                return {'success': True, 'info': info}
            except json.JSONDecodeError:
                return {'success': False, 'error': 'Failed to parse JSON output'}
        
        return result
    
    def get_video_duration(self, file_path):
        info = self.get_video_info(file_path)
        
        if info['success']:
            format_info = info['info'].get('format', {})
            duration = float(format_info.get('duration', 0))
            return {'success': True, 'duration': duration}
        
        return info
    
    def get_video_resolution(self, file_path):
        info = self.get_video_info(file_path)
        
        if info['success']:
            streams = info['info'].get('streams', [])
            for stream in streams:
                if stream.get('codec_type') == 'video':
                    width = stream.get('width')
                    height = stream.get('height')
                    return {'success': True, 'width': width, 'height': height}
        
        return {'success': False, 'error': 'Video stream not found'}
    
    def convert_video(self, input_path, output_path, codec='libx264', bitrate='5M', **kwargs):
        builder = FFmpegCommandBuilder()
        builder.add_input(input_path)
        
        output_params = {
            'c:v': codec,
            'b:v': bitrate,
            'y': True
        }
        output_params.update(kwargs)
        
        builder.add_output(output_path, output_params)
        
        command = builder.build()
        return self.run_command(command)
    
    def extract_audio(self, input_path, output_path, codec='aac', bitrate='192k'):
        builder = FFmpegCommandBuilder()
        builder.add_input(input_path)
        builder.add_output(output_path, {
            'c:a': codec,
            'b:a': bitrate,
            'vn': True,
            'y': True
        })
        
        command = builder.build()
        return self.run_command(command)
    
    def trim_video(self, input_path, output_path, start_time, duration):
        builder = FFmpegCommandBuilder()
        builder.add_input(input_path, {'ss': start_time})
        builder.add_output(output_path, {
            't': duration,
            'y': True
        })
        
        command = builder.build()
        return self.run_command(command)
    
    def resize_video(self, input_path, output_path, width, height):
        builder = FFmpegCommandBuilder()
        builder.add_input(input_path)
        builder.add_output(output_path, {
            's': f"{width}x{height}",
            'y': True
        })
        
        command = builder.build()
        return self.run_command(command)
    
    def add_watermark(self, input_path, output_path, watermark_path, position='top-right'):
        command = FFmpegCommonCommands.add_watermark(input_path, output_path, watermark_path, position)
        return self.run_command(command)
    
    def encode_h265(self, input_path, output_path, bitrate='5M', preset='medium'):
        command = FFmpegCommonCommands.encode_h265(input_path, output_path, bitrate, preset)
        return self.run_command(command)
    
    def encode_av1(self, input_path, output_path, bitrate='3M', cpu_used=4):
        command = FFmpegCommonCommands.encode_av1(input_path, output_path, bitrate, cpu_used)
        return self.run_command(command)
    
    def extract_frames(self, input_path, output_pattern, frame_rate=1):
        command = FFmpegCommonCommands.extract_frames(input_path, output_pattern, frame_rate)
        return self.run_command(command)
```

---

## 八、编码理论与学术研究

### 8.1 视频编码基础理论

#### 熵编码原理

| 编码方法 | 原理 | 应用场景 | 特点 |
|---------|------|---------|------|
| Huffman编码 | 基于概率的变长编码 | H.264 CABAC/CAVLC | 最优前缀码，无失真 |
| Arithmetic编码 | 区间划分编码 | H.264 CABAC | 接近熵极限，复杂度高 |
| Exp-Golomb编码 | 指数哥伦布编码 | 量化系数编码 | 简单高效，适合小数值 |

#### 变换编码原理

```python
class TransformCoding:
    def dct_transform(self, block):
        n = len(block)
        result = [[0.0] * n for _ in range(n)]
        
        for u in range(n):
            for v in range(n):
                sum_val = 0.0
                for x in range(n):
                    for y in range(n):
                        sum_val += block[x][y] * \
                                  math.cos((2*x+1)*u*math.pi/(2*n)) * \
                                  math.cos((2*y+1)*v*math.pi/(2*n))
                
                alpha_u = 1/math.sqrt(n) if u == 0 else math.sqrt(2/n)
                alpha_v = 1/math.sqrt(n) if v == 0 else math.sqrt(2/n)
                
                result[u][v] = alpha_u * alpha_v * sum_val
        
        return result
    
    def idct_transform(self, block):
        n = len(block)
        result = [[0.0] * n for _ in range(n)]
        
        for x in range(n):
            for y in range(n):
                sum_val = 0.0
                for u in range(n):
                    for v in range(n):
                        alpha_u = 1/math.sqrt(n) if u == 0 else math.sqrt(2/n)
                        alpha_v = 1/math.sqrt(n) if v == 0 else math.sqrt(2/n)
                        sum_val += alpha_u * alpha_v * block[u][v] * \
                                  math.cos((2*x+1)*u*math.pi/(2*n)) * \
                                  math.cos((2*y+1)*v*math.pi/(2*n))
                
                result[x][y] = sum_val
        
        return result
    
    def zigzag_scan(self, block):
        n = len(block)
        result = []
        
        for sum_val in range(2*n - 1):
            if sum_val < n:
                start_x, start_y = sum_val, 0
            else:
                start_x, start_y = n-1, sum_val - n + 1
            
            x, y = start_x, start_y
            while x >= 0 and y < n:
                result.append(block[x][y])
                x -= 1
                y += 1
        
        return result
```

### 8.2 帧间预测技术

```python
class InterFramePrediction:
    BLOCK_SIZES = ['4x4', '8x8', '16x16', '32x32', '64x64']
    
    SEARCH_ALGORITHMS = ['full_search', 'hex_search', 'diamond_search', 'epzs']
    
    def __init__(self):
        self.search_range = 16
        self.block_size = '16x16'
        self.search_algorithm = 'hex_search'
        
    def configure(self, params):
        self.search_range = params.get('search_range', 16)
        self.block_size = params.get('block_size', '16x16')
        self.search_algorithm = params.get('search_algorithm', 'hex_search')
        
    def motion_estimation(self, current_frame, reference_frame, block_position):
        block_size = tuple(map(int, self.block_size.split('x')))
        bx, by = block_position
        
        best_mv = (0, 0)
        best_cost = float('inf')
        
        if self.search_algorithm == 'hex_search':
            best_mv, best_cost = self._hex_search(current_frame, reference_frame, 
                                                  bx, by, block_size)
        elif self.search_algorithm == 'full_search':
            best_mv, best_cost = self._full_search(current_frame, reference_frame, 
                                                   bx, by, block_size)
        
        return {'motion_vector': best_mv, 'cost': best_cost}
    
    def _full_search(self, current_frame, reference_frame, bx, by, block_size):
        best_mv = (0, 0)
        best_cost = float('inf')
        
        for dx in range(-self.search_range, self.search_range + 1):
            for dy in range(-self.search_range, self.search_range + 1):
                cost = self._calculate_cost(current_frame, reference_frame, 
                                           bx, by, dx, dy, block_size)
                if cost < best_cost:
                    best_cost = cost
                    best_mv = (dx, dy)
        
        return best_mv, best_cost
    
    def _hex_search(self, current_frame, reference_frame, bx, by, block_size):
        search_points = [
            (0, 0), (0, -1), (0, 1), (-1, 0), (1, 0),
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        ]
        
        best_mv = (0, 0)
        best_cost = float('inf')
        step = self.search_range
        
        while step >= 1:
            for dx, dy in search_points:
                mv_x, mv_y = best_mv[0] + dx * step, best_mv[1] + dy * step
                cost = self._calculate_cost(current_frame, reference_frame,
                                           bx, by, mv_x, mv_y, block_size)
                if cost < best_cost:
                    best_cost = cost
                    best_mv = (mv_x, mv_y)
            step //= 2
        
        return best_mv, best_cost
    
    def _calculate_cost(self, current_frame, reference_frame, bx, by, dx, dy, block_size):
        bw, bh = block_size
        cost = 0
        
        for y in range(bh):
            for x in range(bw):
                current_pixel = current_frame[by + y][bx + x]
                ref_pixel = reference_frame[by + y + dy][bx + x + dx]
                cost += abs(current_pixel - ref_pixel)
        
        return cost
```

### 8.3 码率控制算法

```python
class RateControl:
    MODE_TYPES = ['CBR', 'VBR', 'CRF', 'ABR']
    
    def __init__(self):
        self.mode = 'CRF'
        self.target_bitrate = 5000000
        self.buffer_size = 10000000
        self.crf = 23
        self.qmin = 0
        self.qmax = 51
        self.frame_count = 0
        self.bit_usage = 0
        
    def configure(self, params):
        self.mode = params.get('mode', 'CRF')
        self.target_bitrate = params.get('target_bitrate', 5000000)
        self.buffer_size = params.get('buffer_size', 10000000)
        self.crf = params.get('crf', 23)
        self.qmin = params.get('qmin', 0)
        self.qmax = params.get('qmax', 51)
        
    def calculate_qp(self, frame_complexity):
        if self.mode == 'CRF':
            return self.crf
        
        elif self.mode == 'CBR':
            target_bits_per_frame = self.target_bitrate / 30
            actual_bits = frame_complexity * 1000
            
            if actual_bits > target_bits_per_frame:
                return min(self.qmax, self.crf + 2)
            else:
                return max(self.qmin, self.crf - 2)
        
        elif self.mode == 'VBR':
            complexity_ratio = frame_complexity / 100
            return max(self.qmin, min(self.qmax, int(self.crf * complexity_ratio)))
        
        return self.crf
    
    def update_buffer(self, frame_bits):
        self.bit_usage += frame_bits
        
        if self.bit_usage > self.buffer_size:
            return {'status': 'overflow', 'qp_adjustment': 2}
        elif self.bit_usage < self.buffer_size * 0.1:
            return {'status': 'underflow', 'qp_adjustment': -2}
        
        return {'status': 'normal', 'qp_adjustment': 0}
```

### 8.4 学术论文索引

#### 视频编码基础
- *"The H.264/AVC Video Compression Standard"* - Wiegand et al. (2003)
- *"Overview of the High Efficiency Video Coding (HEVC) Standard"* - Sullivan et al. (2012)
- *"AV1: A New Open Source Video Codec"* - Bjontegaard et al. (2018)

#### 熵编码
- *"Arithmetic Coding for Data Compression"* - Witten et al. (1987)
- *"Context-Based Adaptive Binary Arithmetic Coding in the H.264/AVC Video Compression Standard"* - Marpe et al. (2003)

#### 变换编码
- *"Discrete Cosine Transform"* - Ahmed et al. (1974)
- *"The Karhunen-Loève Transform: Its Application to Image Processing"* - Andrews and Patterson (1976)

#### 运动估计
- *"Block Matching Algorithms for Motion Estimation"* - Jain and Jain (1981)
- *"A New Diamond Search Algorithm for Fast Block-Matching Motion Estimation"* - Zhu et al. (2000)

---

## 附录

### A. 常用命令速查表

| 操作 | 命令示例 | 说明 |
|------|---------|------|
| 格式转换 | `ffmpeg -i input.mp4 output.mkv` | 转换视频格式 |
| 提取音频 | `ffmpeg -i input.mp4 -vn output.mp3` | 提取音频轨道 |
| 提取帧 | `ffmpeg -i input.mp4 -r 1 frame_%04d.png` | 按帧率提取帧 |
| 视频剪切 | `ffmpeg -ss 00:01:00 -i input.mp4 -t 00:00:30 output.mp4` | 从1分钟开始剪30秒 |
| 分辨率调整 | `ffmpeg -i input.mp4 -s 1280x720 output.mp4` | 调整分辨率 |
| H.264编码 | `ffmpeg -i input.mp4 -c:v libx264 -crf 23 output.mp4` | 使用H.264编码 |
| H.265编码 | `ffmpeg -i input.mp4 -c:v libx265 -crf 28 output.mp4` | 使用H.265编码 |
| 合并视频 | `ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4` | 无损合并视频 |
| 添加水印 | `ffmpeg -i input.mp4 -i watermark.png -filter_complex overlay output.mp4` | 添加水印 |
| RTMP推流 | `ffmpeg -i input.mp4 -c copy -f flv rtmp://server/live/stream` | 推流到RTMP服务器 |

### B. CRF质量对照表

| CRF值 | 质量 | 文件大小 | 适用场景 |
|-------|------|---------|---------|
| 0 | 无损 | 最大 | 存档/后期制作 |
| 18 | 极高 | 大 | 高质量交付 |
| 20 | 高 | 较大 | 专业视频 |
| 23 | 中高 | 适中 | 标准网络视频 |
| 26 | 中等 | 较小 | 一般网络视频 |
| 28 | 较低 | 小 | 移动端/低带宽 |
| 30+ | 低 | 最小 | 预览/缩略图 |

### C. 常见错误码与解决方案

| 错误码 | 原因 | 解决方案 |
|--------|------|---------|
| -1 | 找不到文件 | 检查文件路径是否正确 |
| -2 | 找不到编解码器 | 检查是否安装对应编码器 |
| -3 | 内存不足 | 增加内存或降低分辨率/比特率 |
| -5 | 编码参数错误 | 检查编码参数是否合法 |
| -11 | 信号中断 | 检查输入源是否正常 |
| -1094995529 | 硬件加速错误 | 禁用硬件加速或更新驱动 |