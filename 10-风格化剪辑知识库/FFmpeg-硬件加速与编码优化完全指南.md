# FFmpeg 硬件加速与编码优化完全指南

> 本指南以实验研究原子级别标准编写，覆盖 FFmpeg 全部硬件加速管线（CUDA/NVENC/NVDEC、Intel QSV、AMD AMF、VideoToolbox、Vulkan）、编码参数原子映射、性能基准与故障排查，提供可直接落地的命令、参数表与自动化脚本。

---

## 一、硬件加速架构

### 1.1 FFmpeg 硬件加速框架

FFmpeg 的硬件加速体系由 AVHWDeviceContext / AVHWFramesContext 两层抽象构成，通过统一的 HW Accel API 把设备初始化、帧池管理、像素格式转换、内核调度与回拷分离，使上层编码器/解码器/滤镜与底层硬件解耦。

```python
class HWAccelFramework:
    """FFmpeg 硬件加速框架原子模型"""

    HW_DEVICE_TYPES = {
        'cuda':      {'vendor': 'NVIDIA',  'context': 'AVCUDADeviceContext',     'frames_ctx': 'CUDAFramesContext',  'pix_fmt': 'cuda',   'api': 'CUDA 11.x/12.x'},
        'qsv':       {'vendor': 'Intel',   'context': 'AVQSVDeviceContext',      'frames_ctx': 'QSVFramesContext',   'pix_fmt': 'qsv',    'api': 'MediaSDK / oneVPL'},
        'd3d11va':   {'vendor': 'Microsoft','context': 'AVD3D11VADeviceContext', 'frames_ctx': 'D3D11VAFramesContext','pix_fmt': 'd3d11',  'api': 'Direct3D 11'},
        'dxva2':     {'vendor': 'Microsoft','context': 'AVDXVA2DeviceContext',   'frames_ctx': 'DXVA2FramesContext',  'pix_fmt': 'dxva2',  'api': 'DXVA 2.0'},
        'vulkan':    {'vendor': 'Khronos', 'context': 'AVVulkanDeviceContext',  'frames_ctx': 'VulkanFramesContext', 'pix_fmt': 'vulkan', 'api': 'Vulkan 1.2+'},
        'vaapi':     {'vendor': 'Linux',   'context': 'AVVAAPIDeviceContext',   'frames_ctx': 'VAAPIFramesContext',  'pix_fmt': 'vaapi',  'api': 'VA-API'},
        'vdpau':     {'vendor': 'Linux',   'context': 'AVVDPAUDeviceContext',   'frames_ctx': 'VDPAUFramesContext',  'pix_fmt': 'vdpau',  'api': 'VDPAU'},
        'videotoolbox':{'vendor':'Apple',  'context': 'AVVideotoolboxDeviceContext','frames_ctx':'VTFramesContext',   'pix_fmt': 'videotoolbox_vld', 'api': 'VideoToolbox'},
        'opencl':    {'vendor': 'Khronos', 'context': 'AVOpenCLDeviceContext',  'frames_ctx': 'OpenCLFramesContext', 'pix_fmt': 'opencl', 'api': 'OpenCL 1.2+'},
        'mediacodec':{'vendor': 'Android', 'context': 'AVMediaCodecDeviceContext','frames_ctx':'MediaCodecFramesContext','pix_fmt':'mediacodec','api':'MediaCodec'},
        'amf':       {'vendor': 'AMD',     'context': 'AVAMFDeviceContext',     'frames_ctx': 'AMFFramesContext',    'pix_fmt': 'amf',    'api': 'AMF 1.4+'},
    }

    HW_PIPELINE_STAGES = [
        # 阶段顺序：输入 → 解码 → 前处理(可选) → 编码 → 输出
        {'stage': '1.device_init',   'api': 'av_hwdevice_ctx_create',         'params': ['device', 'device_type', 'opts']},
        {'stage': '2.frames_alloc',  'api': 'av_hwframe_ctx_alloc',           'params': ['device_ctx', 'sw_format', 'width', 'height', 'initial_pool_size']},
        {'stage': '3.hw_decode',     'api': 'avcodec_send_packet/receive_frame', 'flag': 'AV_CODEC_HWACCEL'},
        {'stage': '4.hw_transfer',   'api': 'av_hwframe_transfer_data',       'direction': 'hw->sw / sw->hw'},
        {'stage': '5.hw_filter',     'api': 'AVFilterGraph with hwctx',       'filters': ['scale_cuda','scale_qsv','scale_vt']},
        {'stage': '6.hw_encode',     'api': 'avcodec_send_frame/receive_packet','encoders': ['h264_nvenc','h264_qsv','h264_videotoolbox']},
        {'stage': '7.hw_readback',   'api': 'av_hwframe_transfer_data',       'direction': 'hw->sw (可选，仅调试/验证)'},
    ]

    # 关键命令行入口
    CLI_ENTRY = {
        'init_device': '-init_hw_device {type}:{name}[={opts}]',
        'filter_format': '-filter_format {pix_fmt}',
        'hwaccel': '-hwaccel {device} -hwaccel_output_format {pix_fmt}',
        'filter_hw': '-vf scale_{hw}=W:H',
        'encoder_hw': '-c:v {encoder_hw}',
    }
```

#### 1.1.1 HW Context 系统

```python
class HWContextSystem:
    """硬件上下文生命周期原子模型"""

    DEVICE_INIT_PARAMS = {
        'cuda': {
            'required': ['device_index'],
            'optional': ['primary_ctx', 'cu_ctx'],
            'example': '-init_hw_device cuda=cu:0',
            'env': {'CUDA_VISIBLE_DEVICES': '0'},
            'notes': '默认使用 0 号设备；多卡时通过 CUDA_VISIBLE_DEVICES 或 device_index 指定'
        },
        'qsv': {
            'required': ['child_device_type'],
            'optional': ['child_device', 'impl', 'async_depth'],
            'example': '-init_hw_device qsv=hw,child_device_type=d3d11va',
            'env': {'MFX_IMPL': 'hardware'},
            'notes': 'Windows 默认 d3d11va 子设备，Linux 用 vaapi 子设备'
        },
        'vaapi': {
            'required': ['device_path'],
            'optional': ['driver', 'connection_type'],
            'example': '-init_hw_device vaapi=va:/dev/dri/renderD128',
            'env': {'LIBVA_DRIVER_NAME': 'iHD|i965|amdgpu|radeon'},
            'notes': 'Intel Arc 用 iHD，Intel 集显老平台用 i965，AMD 用 amdgpu'
        },
        'vulkan': {
            'required': ['device_index', 'instance_extensions', 'device_extensions'],
            'optional': ['queue_family_index', 'debug'],
            'example': '-init_hw_device vulkan=vk:0',
            'env': {'VK_ICD_FILENAMES': 'nvidia_icd.json|intel_icd.json'},
            'notes': '需 FFmpeg 编译时启用 --enable-vulkan；跨厂商场景需指定 ICD'
        },
        'videotoolbox': {
            'required': [],
            'optional': [],
            'example': '-init_hw_device videotoolbox=vt',
            'env': {},
            'notes': 'macOS/iOS 系统级硬件抽象，无需指定设备'
        },
        'd3d11va': {
            'required': ['device_adapter'],
            'optional': ['binding_count', 'allow_unaligned_tables'],
            'example': '-init_hw_device d3d11va=dx:0',
            'env': {},
            'notes': 'Windows 平台，QSV 与 AMF 都基于此构建'
        },
    }

    FRAMES_CTX_PARAMS = {
        'sw_format':     {'desc': '软件侧像素格式', 'values': ['nv12','yuv420p','yuv444p10le','p010le','bgra']},
        'width':         {'desc': '帧宽',            'type': 'int'},
        'height':        {'desc': '帧高',            'type': 'int'},
        'initial_pool_size': {'desc': '初始池大小',  'default': 20, 'range': '4-128'},
        'format':        {'desc': '硬件像素格式',    'values': ['cuda','qsv','vaapi','vulkan','d3d11']},
    }

    # 设备初始化失败码
    ERROR_CODES = {
        'AVERROR_UNKNOWN':           {'code': -1313558101, 'cause': '驱动缺失或硬件不支持'},
        'AVERROR_BUG2':              {'code': -558976962,  'cause': '内部 bug，通常为上下文参数非法'},
        'AVERROR_DEVICE_NOT_FOUND':  {'code': -1414549536, 'cause': '设备索引越界或物理设备不存在'},
        'AVERROR_INVALIDDATA':       {'code': -1094995529, 'cause': '驱动返回非法数据'},
        'AVERROR_EXTERNAL':          {'code': -541452821,  'cause': '外部 SDK（CUDA/QSV/AMF）返回错误'},
    }
```

#### 1.1.2 HW Accel 设备初始化实战

```bash
# 1. 查看 FFmpeg 支持的硬件加速方法
ffmpeg -hwaccels
# 典型输出：cuda qsv vaapi d3d11va dxva2 videotoolbox vulkan opencl mediacodec

# 2. 查看可用编码器（硬件类）
ffmpeg -encoders | findstr /R "nvenc qsv amf videotoolbox vulkan"
# h264_nvenc / hevc_nvenc / av1_nvenc
# h264_qsv  / hevc_qsv  / av1_qsv
# h264_amf  / hevc_amf  / av1_amf
# h264_videotoolbox / hevc_videotoolbox / prores_videotoolbox

# 3. 查看可用解码器（硬件类）
ffmpeg -decoders | findstr /R "cuvid qsv d3d11va dxva2 vulkan"

# 4. 查看特定编码器参数
ffmpeg -h encoder=h264_nvenc
ffmpeg -h encoder=hevc_qsv
ffmpeg -h encoder=av1_amf

# 5. CUDA 多卡初始化
ffmpeg -init_hw_device cuda=cu0:0 -init_hw_device cuda=cu1:1 \
       -filter_hw_device cu0 -i input.mp4 -c:v h264_nvenc -gpu 0 out0.mp4

# 6. QSV + D3D11VA 混合初始化（Windows）
ffmpeg -init_hw_device d3d11va=dx -init_hw_device qsv=hw,child_device_type=d3d11va \
       -filter_hw_device hw -i input.mp4 -c:v h264_qsv out.mp4

# 7. VAAPI 初始化（Linux Intel）
ffmpeg -init_hw_device vaapi=va:/dev/dri/renderD128 \
       -filter_hw_device va -i input.mp4 -c:v h264_vaapi out.mp4

# 8. Vulkan 初始化
ffmpeg -init_hw_device vulkan=vk:0 -filter_hw_device vk \
       -i input.mp4 -vf scale_vulkan=1920:1080 -c:v h264_vulkan out.mp4
```

#### 1.1.3 帧传输与格式转换

```python
class FrameTransferModel:
    """HW↔SW 帧传输原子模型"""

    TRANSFER_PATHS = {
        'sw_to_hw': {
            'api': 'av_hwframe_transfer_data(hwframe, swframe, 0)',
            'use_case': '软件解码 → 硬件编码 / 软件源 → 硬件滤镜',
            'overhead_us': {'nv12': 30, 'p010le': 50, 'yuv444p10le': 90},
            'bottleneck': 'PCIe 带宽 / 内存拷贝',
        },
        'hw_to_sw': {
            'api': 'av_hwframe_transfer_data(swframe, hwframe, 0)',
            'use_case': '硬件解码 → 软件滤镜 / 硬件解码 → CPU 分析',
            'overhead_us': {'nv12': 35, 'p010le': 55, 'yuv444p10le': 100},
            'bottleneck': 'PCIe 带宽 / GPU→CPU 回拷',
        },
        'hw_to_hw': {
            'api': '同设备：零拷贝；跨设备：通过 AVHWDeviceContext 桥接',
            'use_case': '硬件解码 → 硬件滤镜 → 硬件编码（最优路径）',
            'overhead_us': {'same_device': 1, 'cross_device': 80},
            'bottleneck': '驱动层映射',
        },
    }

    # 像素格式兼容性矩阵（行=源，列=目标）
    FORMAT_COMPATIBILITY = {
        'nv12':         {'nv12': True, 'p010le': False, 'yuv444p10le': False, 'bgra': True},
        'p010le':       {'nv12': False, 'p010le': True, 'yuv444p10le': False, 'bgra': True},
        'yuv444p10le':  {'nv12': False, 'p010le': False, 'yuv444p10le': True,  'bgra': True},
        'yuv420p':      {'nv12': True, 'p010le': False, 'yuv444p10le': False, 'bgra': True},
    }

    # 性能优化建议
    OPTIMIZATION_RULES = [
        {'rule': '保持帧在硬件内存中', 'reason': '避免 PCIe 回拷开销（典型 30-100μs/帧）'},
        {'rule': '统一像素格式',       'reason': '格式转换会引入额外 filter 或 upload/download 节点'},
        {'rule': '使用 hwupload/hwdownload 显式控制', 'reason': '默认自动映射可能产生意外路径'},
        {'rule': 'NV12 优先于 YUV420P', 'reason': 'NV12 为半平面格式，硬件原生支持，无 planar→packed 转换'},
        {'rule': '10bit 用 P010LE',    'reason': 'P010LE 是 NV12 的 16bit 升级版，硬件解码直接输出'},
    ]
```

### 1.2 支持的硬件平台

```python
class HardwarePlatformMatrix:
    """硬件加速平台能力矩阵"""

    PLATFORMS = {
        'nvidia_cuda': {
            'vendor': 'NVIDIA',
            'encoders': ['h264_nvenc', 'hevc_nvenc', 'av1_nvenc'],
            'decoders': ['h264_cuvid', 'hevc_cuvid', 'av1_cuvid', 'vp9_cuvid', 'mjpeg_cuvid', 'mpeg2_cuvid', 'mpeg4_cuvid', 'vc1_cuvid', 'vp8_cuvid'],
            'filters':  ['scale_cuda', 'scale_npp', 'yadif_cuda', 'bwdif_cuda', 'chromakey_cuda', 'overlay_cuda', 'tonemap_cuda', 'transpose_cuda', 'flip_cuda', 'rotate_cuda', 'sharpen_npp', 'thumbnail_cuda'],
            'min_driver': 'R510 (2022.01)',
            'min_ffmpeg': '4.0',
            'compute_caps': '3.5+ (Kepler 及以后)',
            'gpu_families': ['GeForce RTX 40/30/20', 'Quadro RTX', 'Tesla/Quadro T4/A10/A100', 'GTX 16/10'],
            'sdk': 'CUDA 11.x/12.x + NVENC SDK',
            'license': '专有（驱动闭源，编码器接口开放）',
            'session_limit': {'consumer': 5, 'quadro': {'T4': 8, 'A10': 8, 'A100': 0}},
            'av1_support': {'encode': 'RTX 40 系列 (Ada)', 'decode': 'RTX 30 系列 (Ampere) 起'},
        },
        'intel_qsv': {
            'vendor': 'Intel',
            'encoders': ['h264_qsv', 'hevc_qsv', 'av1_qsv', 'mjpeg_qsv', 'vp9_qsv'],
            'decoders': ['h264_qsv', 'hevc_qsv', 'av1_qsv', 'vp9_qsv', 'mjpeg_qsv', 'mpeg2_qsv', 'vc1_qsv'],
            'filters':  ['scale_qsv', 'vpp_qsv', 'overlay_qsv', 'deinterlace_qsv'],
            'min_driver': '2022.Q1',
            'min_ffmpeg': '4.0',
            'hardware': ['Intel Iris Xe (11代+)', 'Intel Arc (Alchemist/Battlemage)', 'Intel Xeon with QuickSync'],
            'sdk': 'Intel MediaSDK → oneVPL (1.x+)',
            'license': '专有',
            'av1_support': {'encode': 'Arc A380+ (Alchemist)', 'decode': 'Tiger Lake (11代) 起'},
            'features': ['VPP 视频后处理', 'LookAhead', 'ROI 编码', '多层 B 帧'],
        },
        'amd_amf': {
            'vendor': 'AMD',
            'encoders': ['h264_amf', 'hevc_amf', 'av1_amf'],
            'decoders': ['通过 d3d11va/dxva2 间接硬件解码'],
            'filters':  ['无专用 AMF 滤镜，依赖 d3d11va/vaapi'],
            'min_driver': 'Adrenalin 22.x',
            'min_ffmpeg': '4.0',
            'hardware': ['Radeon RX 7000/6000/5000', 'Radeon Pro', 'APU (Ryzen APU)'],
            'sdk': 'AMF 1.4+',
            'license': '专有（SDK 开源 MIT）',
            'av1_support': {'encode': 'RX 7000 系列 (RDNA3)', 'decode': 'RX 6000 系列 (RDNA2) 起'},
            'features': ['Pre-Analysis', 'PAQ (Perceptual Adaptive Quantization)', '运动估计'],
        },
        'apple_videotoolbox': {
            'vendor': 'Apple',
            'encoders': ['h264_videotoolbox', 'hevc_videotoolbox', 'prores_videotoolbox', 'av1_videotoolbox'],
            'decoders': ['h264_videotoolbox', 'hevc_videotoolbox'],
            'filters':  ['无专用，通过 hwupload/hwdownload 桥接'],
            'min_macos': '10.13 (High Sierra)',
            'min_ffmpeg': '4.0',
            'hardware': ['Apple Silicon M1/M2/M3/M4', 'Intel Mac with iGPU'],
            'sdk': 'VideoToolbox Framework',
            'license': '专有（系统级）',
            'av1_support': {'encode': 'M3+ (硬件编码)', 'decode': 'M3+ / A17+ (硬件解码)'},
            'features': ['实时编码', '低功耗', '与 CoreMedia/AVFoundation 深度集成'],
        },
        'vulkan': {
            'vendor': 'Khronos (跨厂商)',
            'encoders': ['h264_vulkan', 'hevc_vulkan', 'av1_vulkan'],
            'decoders': ['h264_vulkan', 'hevc_vulkan', 'av1_vulkan'],
            'filters':  ['scale_vulkan', 'libplacebo', 'chromakey_vulkan', 'overlay_vulkan'],
            'min_driver': 'Vulkan 1.2 + VK_EXT_video_encode/decode',
            'min_ffmpeg': '5.0 (实验性), 6.0 (稳定)',
            'hardware': ['NVIDIA RTX 30+', 'Intel Arc', 'AMD RDNA2+', 'ARM Mali'],
            'sdk': 'Vulkan + LunarG SDK',
            'license': '开源 (MIT)',
            'av1_support': {'encode': '部分 RDNA3/Arc/Ada', 'decode': '部分硬件'},
            'features': ['跨平台', '跨厂商统一 API', '实验性生态'],
        },
    }
```

---

## 二、NVIDIA CUDA 加速

### 2.1 NVENC 编码器

#### 2.1.1 H.264 NVENC 参数详解

```python
class H264NVENCParams:
    """H.264 NVENC 编码器原子参数表"""

    CORE_PARAMS = {
        # === 预设系统（p1-p7）===
        'preset': {
            'values': ['p1','p2','p3','p4','p5','p6','p7'],
            'aliases': {'fast':'p1','medium':'p4','slow':'p7'},
            'p1': {'desc':'最快','quality':'lowest','motion_est':'low','b_ref':False},
            'p2': {'desc':'较快','quality':'low',  'motion_est':'low','b_ref':False},
            'p3': {'desc':'低延时','quality':'low', 'motion_est':'medium','b_ref':False},
            'p4': {'desc':'默认','quality':'medium','motion_est':'medium','b_ref':True},
            'p5': {'desc':'较慢','quality':'good', 'motion_est':'high','b_ref':True},
            'p6': {'desc':'慢', 'quality':'high', 'motion_est':'high','b_ref':True},
            'p7': {'desc':'最慢','quality':'best', 'motion_est':'highest','b_ref':True},
            'recommendation': '直播 p3-p4，录播 p5-p6，存档 p7'
        },
        # === 速率控制 ===
        'rc': {
            'values': ['constqp','vbr','cbr','vbr_minqp','ll_2pass_quality','ll_2pass_size','vbr_2pass'],
            'constqp': {'desc':'恒定量化参数(CQP)', 'use':'画质测试/存档'},
            'vbr':     {'desc':'可变码率',           'use':'文件分发'},
            'cbr':     {'desc':'恒定码率',           'use':'直播流'},
            'vbr_minqp':{'desc':'最小QP的VBR',       'use':'兼顾画质与码率'},
            'll_2pass_quality':{'desc':'低延迟2pass','use':'高质量直播'},
            'll_2pass_size':{'desc':'低延迟2pass大小','use':'码率受限直播'},
            'vbr_2pass':{'desc':'2pass VBR',        'use':'离线编码'},
        },
        'cbr':    {'desc':'CBR模式别名', 'type':'flag'},
        'vbr':    {'desc':'VBR模式别名', 'type':'flag'},
        'cq':     {'desc':'CQ模式(恒定质量)', 'type':'flag'},
        # === 码率与量化 ===
        'b:v':     {'desc':'目标码率', 'unit':'bits/s', 'examples':['8M','10M','20M']},
        'minrate': {'desc':'最小码率(CBR/VBR)', 'unit':'bits/s'},
        'maxrate': {'desc':'最大码率', 'unit':'bits/s'},
        'bufsize': {'desc':'VBV缓冲大小', 'unit':'bits/s', 'default':'2×maxrate'},
        'qp':      {'desc':'CQP模式QP值', 'format':'qpi:qpp:qpb', 'example':'24:26:28'},
        'cq':      {'desc':'CQ质量值', 'range':'0-51', 'recommended':'20-30'},
        'qmin':    {'desc':'最小量化参数', 'range':'0-51'},
        'qmax':    {'desc':'最大量化参数', 'range':'0-51'},
        # === GOP 结构 ===
        'g':       {'desc':'GOP长度', 'unit':'frames', 'recommendation':'2×fps (直播), 5-10s (录播)'},
        'bf':      {'desc':'B帧数量', 'range':'0-4', 'recommendation':'2-3', 'constraint':'p4及以上才支持B帧'},
        'refs':    {'desc':'参考帧数量', 'range':'0-16', 'constraint':'B帧存在时受限于DPB'},
        'keyint_min': {'desc':'最小I帧间隔', 'default':'0 (auto)'},
        # === 画质优化 ===
        'spatial_aq': {'desc':'空间自适应量化', 'type':'bool', 'recommended':'True (p5+)'},
        'temporal_aq':{'desc':'时间自适应量化', 'type':'bool', 'recommended':'True (p5+)'},
        'aq-strength':{'desc':'AQ强度', 'range':'1-15', 'default':'8'},
        'rc-lookahead':{'desc':'前瞻帧数', 'range':'0-32', 'default':'0', 'recommended':'32 (高质量)'},
        'coded_picture_format':{'values':['0','1'],'desc':'0=帧编码,1=场编码'},
        'nonref_p':  {'desc':'非参考P帧', 'type':'bool', 'use':'降低延迟'},
        'strict_gop':{'desc':'严格GOP', 'type':'bool', 'use':'避免场景切换插入额外I帧'},
        # === GPU 选择 ===
        'gpu':      {'desc':'GPU设备索引', 'default':'0'},
        # === 延迟控制 ===
        'delay':    {'desc':'延迟帧数', 'range':'0-INT_MAX', '0':'零延迟', 'default':'auto'},
        'zerolatency':{'desc':'零延迟模式', 'type':'bool'},
        # === B帧配置 ===
        'b_ref_mode':{'values':['disabled','each','middle'],'default':'middle'},
        # === 熵编码 ===
        'cabac':    {'desc':'CABAC熵编码', 'type':'bool', 'default':'True'},
        # === Slice ===
        'slice_mode':{'values':['0','1','2','3','4','5'],'0':'单slice','1':'按行数','2':'按大小'},
        # === 加密 ===
        'dpb_size': {'desc':'DPB大小', 'default':'auto'},
    }

    # 实战预设组合
    PRESETS = {
        'live_stream': {
            'preset': 'p4', 'rc': 'cbr', 'b:v': '6M', 'maxrate': '6M',
            'bufsize': '12M', 'g': '120', 'bf': '2', 'refs': '2',
            'spatial_aq': True, 'temporal_aq': False, 'rc-lookahead': 32,
            'zerolatency': True,
            'command': 'ffmpeg -i input.mp4 -c:v h264_nvenc -preset p4 -rc cbr -b:v 6M -maxrate 6M -bufsize 12M -g 120 -bf 2 -refs 2 -spatial_aq 1 -rc-lookahead 32 -zerolatency output.mp4'
        },
        'vod_high_quality': {
            'preset': 'p7', 'rc': 'vbr', 'b:v': '10M', 'maxrate': '15M',
            'bufsize': '20M', 'g': '300', 'bf': '3', 'refs': '4',
            'spatial_aq': True, 'temporal_aq': True, 'aq-strength': 10,
            'rc-lookahead': 32, 'b_ref_mode': 'middle',
            'command': 'ffmpeg -i input.mp4 -c:v h264_nvenc -preset p7 -rc vbr -b:v 10M -maxrate 15M -bufsize 20M -g 300 -bf 3 -refs 4 -spatial_aq 1 -temporal_aq 1 -aq-strength 10 -rc-lookahead 32 -b_ref_mode middle output.mp4'
        },
        'archive_cq': {
            'preset': 'p7', 'rc': 'constqp', 'qp': '22:24:26', 'g': '240',
            'bf': '4', 'refs': '6', 'spatial_aq': True, 'temporal_aq': True,
            'command': 'ffmpeg -i input.mp4 -c:v h264_nvenc -preset p7 -rc constqp -qp 22:24:26 -g 240 -bf 4 -refs 6 -spatial_aq 1 -temporal_aq 1 output.mp4'
        },
        'low_latency': {
            'preset': 'p1', 'rc': 'cbr', 'b:v': '8M', 'tune': 'll', 'g': '60',
            'bf': '0', 'zerolatency': True, 'nonref_p': True, 'strict_gop': True,
            'command': 'ffmpeg -i input.mp4 -c:v h264_nvenc -preset p1 -tune ll -rc cbr -b:v 8M -g 60 -bf 0 -zerolatency -nonref_p 1 -strict_gop output.mp4'
        },
    }
```

#### 2.1.2 H.265/HEVC NVENC 参数详解

```python
class HEVCNVENCParams:
    """HEVC NVENC 编码器原子参数表"""

    HEVC_SPECIFIC = {
        'profile': {'values':['main','main10','main444','main444-10','rext'],'recommendation':'main10 for 10bit'},
        'tier':    {'values':['main','high'],'high':'高码率允许更大缓冲'},
        'level':   {'values':['1','2','2.1','3','3.1','4','4.1','5','5.1','5.2','6','6.1','6.2']},
        # === HEVC 特有 ===
        'b_ref_mode': {'values':['disabled','each','middle'],'middle':'仅中间B帧作为参考'},
        'temporal_aq': {'desc':'时间AQ','type':'bool','note':'HEVC的temporal_aq对动态场景增益更大'},
        'spatial_aq':  {'desc':'空间AQ','type':'bool'},
        # === 10bit ===
        'pix_fmt': {'recommended':'p010le','note':'HEVC 10bit 显著优于 8bit 同码率画质'},
        # === 参考帧 ===
        'refs': {'max':16, 'recommendation':'4-6 (p7)'},
        # === 主10位与4:4:4 ===
        'lossless': {'desc':'无损编码','type':'bool','note':'仅 main444-10 支持无损'},
    }

    PRESETS = {
        '4k_hdr': {
            'preset': 'p7', 'rc': 'vbr', 'b:v': '25M', 'maxrate': '40M',
            'bufsize': '50M', 'g': '240', 'bf': '4', 'refs': '4',
            'profile': 'main10', 'pix_fmt': 'p010le',
            'spatial_aq': True, 'temporal_aq': True, 'rc-lookahead': 32,
            'command': 'ffmpeg -i input.mov -c:v hevc_nvenc -preset p7 -rc vbr -b:v 25M -maxrate 40M -bufsize 50M -g 240 -bf 4 -refs 4 -profile:v main10 -pix_fmt p010le -spatial_aq 1 -temporal_aq 1 -rc-lookahead 32 output_h265.mp4'
        },
        '10bit_archive': {
            'preset': 'p7', 'rc': 'constqp', 'qp': '20:22:24', 'profile': 'main10',
            'pix_fmt': 'p010le', 'g': '240', 'bf': '4', 'refs': '6',
            'command': 'ffmpeg -i input.mov -c:v hevc_nvenc -preset p7 -rc constqp -qp 20:22:24 -profile:v main10 -pix_fmt p010le -g 240 -bf 4 -refs 6 output.mp4'
        },
    }
```

#### 2.1.3 AV1 NVENC 参数详解

```python
class AV1NVENCParams:
    """AV1 NVENC 编码器原子参数表（仅 RTX 40 系列 / Ada 架构）"""

    AV1_SPECIFIC = {
        'profile': {'values':['main','high','professional'],'recommendation':'main'},
        'level':   {'values':['2.0','2.1','2.2','2.3','3.0','3.1','3.2','3.3','4.0','4.1','4.2','4.3','5.0','5.1','5.2','5.3','6.0','6.1','6.2','6.3','7.0','7.1','7.2','7.3']},
        'tier':    {'values':['main','high']},
        'preset':  {'values':['p1-p7'],'note':'AV1 preset 含义与 H264/HEVC 相同'},
        'rc':      {'values':['cbr','vbr','constqp','vbr_minqp']},
        'b:v':     {'recommendation':'AV1 同画质比 HEVC 省 20-30% 码率'},
        # === AV1 特有 ===
        'tile_cols': {'desc':'水平 tile 数','values':['0','1','2','4','8'],'use':'多核解码加速'},
        'tile_rows': {'desc':'垂直 tile 数','values':['0','1','2','4'],'use':'多核解码加速'},
        'qmin': {'recommendation':'比 H264 高 2-4'},
        'qmax': {'recommendation':'比 H264 高 2-4'},
        'rc-lookahead': {'max':'8','note':'AV1 NVENC 最大 lookahead=8 (受硬件限制)'},
        # === 限制 ===
        'max_bframes': 4,
        'max_refs': 8,
        'session_limit': 3,  # 消费级 RTX 40 系列 AV1 同时编码会话上限
    }

    PRESETS = {
        'av1_high_quality': {
            'preset': 'p7', 'rc': 'vbr', 'b:v': '8M', 'maxrate': '12M',
            'bufsize': '16M', 'g': '240', 'bf': '4', 'refs': '4',
            'profile': 'main', 'tile_cols': '2', 'tile_rows': '1',
            'command': 'ffmpeg -i input.mp4 -c:v av1_nvenc -preset p7 -rc vbr -b:v 8M -maxrate 12M -bufsize 16M -g 240 -bf 4 -refs 4 -profile:v main -tile_cols 2 -tile_rows 1 output_av1.mp4'
        },
        'av1_streaming': {
            'preset': 'p4', 'rc': 'cbr', 'b:v': '4M', 'g': '120',
            'bf': '2', 'refs': '2', 'tile_cols': '2',
            'command': 'ffmpeg -i input.mp4 -c:v av1_nvenc -preset p4 -rc cbr -b:v 4M -g 120 -bf 2 -refs 2 -tile_cols 2 output_av1.mp4'
        },
    }
```

### 2.2 NVDEC 解码器

```python
class NVDECDecoder:
    """NVDEC (CUVID) 解码器原子模型"""

    SUPPORTED_CODECS = {
        'h264_cuvid':    {'profiles':['Baseline','Main','High'],'max_res':'8K'},
        'hevc_cuvid':    {'profiles':['Main','Main10','Main444'],'max_res':'8K'},
        'av1_cuvid':     {'profiles':['Main','High'],'max_res':'8K','min_gpu':'RTX 30 (Ampere)'},
        'vp9_cuvid':     {'profiles':['Profile 0','Profile 1'],'max_res':'8K'},
        'vp8_cuvid':     {'profiles':[''],'max_res':'4K'},
        'mpeg2_cuvid':   {'profiles':['Main','High'],'max_res':'2K'},
        'mpeg4_cuvid':   {'profiles':['Simple','Advanced Simple'],'max_res':'2K'},
        'vc1_cuvid':     {'profiles':['Simple','Main','Advanced'],'max_res':'2K'},
        'mjpeg_cuvid':   {'profiles':[''],'max_res':'4K'},
    }

    DECODER_PARAMS = {
        'gpu':        {'desc':'GPU索引','default':'0'},
        'surfaces':   {'desc':'解码表面数','default':'auto'},
        'drop_second_field': {'desc':'丢第二场(隔行)','type':'bool'},
        'deint':      {'values':['0','2'],'0':'不处理','2':'自适应去隔行'},
        'crop':       {'desc':'裁剪 (l:t:r:b)'},
        'resize':     {'desc':'解码时缩放 WxH','note':'硬件加速缩放，零额外开销'},
        'output_format':{'values':['nv12','yuv420p','yuv444p','p010le']},
    }

    # 多流解码性能（参考 RTX 4090）
    MULTISTREAM_BENCH = {
        'h264_1080p60': {'max_streams': 32, 'gpu_util': 75},
        'h264_4k30':    {'max_streams': 12, 'gpu_util': 80},
        'hevc_1080p60': {'max_streams': 28, 'gpu_util': 70},
        'hevc_4k60':    {'max_streams': 8,  'gpu_util': 85},
        'av1_1080p60':  {'max_streams': 20, 'gpu_util': 78},
        'av1_4k60':     {'max_streams': 6,  'gpu_util': 88},
    }
```

```bash
# NVDEC 解码 + NVENC 编码（零拷贝管线）
ffmpeg -hwaccel cuda -hwaccel_output_format cuda \
       -c:v h264_cuvid -i input.mp4 \
       -c:v h264_nvenc -preset p5 -b:v 8M \
       output.mp4

# NVDEC 硬件缩放（解码时缩放，无额外开销）
ffmpeg -hwaccel cuda -c:v h264_cuvid -resize 1280x720 \
       -i input.mp4 -c:v h264_nvenc output.mp4

# 多流并行解码 + 编码（批量转码）
ffmpeg -hwaccel cuda -hwaccel_output_format cuda \
       -i input1.mp4 -i input2.mp4 -i input3.mp4 \
       -filter_complex "[0:v]scale_cuda=1280:720[v0];[1:v]scale_cuda=1280:720[v1];[2:v]scale_cuda=1280:720[v2]" \
       -map "[v0]" -c:v h264_nvenc -gpu 0 out0.mp4 \
       -map "[v1]" -c:v h264_nvenc -gpu 0 out1.mp4 \
       -map "[v2]" -c:v h264_nvenc -gpu 0 out2.mp4
```

### 2.3 CUDA 滤镜

```python
class CUDAFilters:
    """CUDA 硬件加速滤镜原子表"""

    FILTERS = {
        'scale_cuda': {
            'desc': 'GPU 缩放滤镜',
            'params': {
                'w': '目标宽度',
                'h': '目标高度',
                'format': '目标格式(nv12/p010le/yuv444p)',
                'force_original_aspect_ratio': 'decrease/increase',
                'force_divisible_by': '对齐因子',
            },
            'algos': ['bilinear','bicubic','lanczos'],
            'perf': '约为 CPU scale(lanczos) 的 5-10x',
            'example': '-vf scale_cuda=1920:1080:format=nv12'
        },
        'scale_npp': {
            'desc': 'NPP 库缩放滤镜',
            'params': {'w':'宽','h':'高','format':'格式','interp':'插值算法'},
            'algos': ['nn','linear','cubic','cubic2p_bspline','cubic2p_catmullrom','cubic2p_b05c03','super'],
            'note': 'NPP 需要 CUDA NPP 库支持，部分发行版未编译',
            'example': '-vf scale_npp=1920:1080:interp=cubic'
        },
        'yadif_cuda': {
            'desc': 'GPU 去隔行（Yadif 算法）',
            'params': {'mode':'send/send_frame/send_field'},
            'example': '-vf yadif_cuda=mode=send_frame'
        },
        'bwdif_cuda': {
            'desc': 'GPU 去隔行（Bob-Weave Deinterlace）',
            'note': '比 yadif_cuda 略快',
            'example': '-vf bwdif_cuda'
        },
        'overlay_cuda': {
            'desc': 'GPU 叠加',
            'params': {'x':'x坐标','y':'y坐标'},
            'example': '-filter_complex "[0:v][1:v]overlay_cuda=x=10:y=10"'
        },
        'chromakey_cuda': {
            'desc': 'GPU 色度键（绿幕抠像）',
            'params': {'color':'颜色','similarity':'相似度','blend':'混合度'},
            'example': '-vf chromakey_cuda=0x00FF00:0.3:0.1'
        },
        'transpose_cuda': {
            'desc': 'GPU 旋转/翻转',
            'params': {'dir':'0=90CW,1=90CCW,2=180,3=90CW+vflip'},
            'example': '-vf transpose_cuda=1'
        },
        'tonemap_cuda': {
            'desc': 'GPU 色调映射 (HDR→SDR)',
            'params': {'tonemap':'none/linear/reinhard/hable/mobius/htmaal/gamma','desat':'去饱和度','t':'目标峰值'},
            'example': '-vf tonemap_cuda=tonemap=hable:desat=0:t=100'
        },
        'thumbnail_cuda': {
            'desc': 'GPU 缩略图（自动选择代表帧）',
            'example': '-vf thumbnail_cuda=100'
        },
        'flip_cuda': {
            'desc': 'GPU 翻转',
            'params': {'type':'horizontal/vertical'},
            'example': '-vf flip_cuda=horizontal'
        },
        'rotate_cuda': {
            'desc': 'GPU 任意角度旋转',
            'params': {'angle':'弧度','outw':'输出宽','outh':'输出高'},
            'example': '-vf rotate_cuda=angle=0.5'
        },
        'sharpen_npp': {
            'desc': 'NPP 锐化',
            'example': '-vf sharpen_npp=5:5:1.0:1.0'
        },
    }

    # 全硬件管线示例
    FULL_HW_PIPELINE = {
        'desc': '解码→缩放→去隔行→编码 全 GPU 链',
        'command': 'ffmpeg -hwaccel cuda -hwaccel_output_format cuda '
                   '-c:v h264_cuvid -i input.ts '
                   '-vf "yadif_cuda=mode=send_frame,scale_cuda=1920:1080:format=nv12" '
                   '-c:v h264_nvenc -preset p5 -rc vbr -b:v 8M -bf 2 -refs 3 '
                   '-spatial_aq 1 -temporal_aq 1 -rc-lookahead 32 '
                   '-c:a aac -b:a 128k output.mp4',
        'gpu_memory_usage': '~800MB for 1080p60',
        'cpu_usage': '<5% (仅用于 I/O 与音频)',
    }
```

### 2.4 性能基准测试

```python
class NVENCBenchmark:
    """NVENC 性能基准测试数据（参考值，实测可能因驱动/系统而异）"""

    # 各代 GPU H.264 1080p60 编码性能对比
    ENCODE_FPS_H264_1080P60 = {
        # 格式：{GPU: {preset: {p1_fps, p4_fps, p7_fps, max_streams}}}
        'GTX 1080 Ti (Pascal)':   {'p1': 480, 'p4': 380, 'p7': 280, 'max_streams': 5},
        'RTX 2080 Ti (Turing)':   {'p1': 720, 'p4': 580, 'p7': 420, 'max_streams': 5},
        'RTX 3080 (Ampere)':      {'p1': 950, 'p4': 780, 'p7': 560, 'max_streams': 5},
        'RTX 4090 (Ada)':         {'p1': 1450,'p4': 1180,'p7': 850, 'max_streams': 8},
        'RTX 4080 (Ada)':         {'p1': 1200,'p4': 980, 'p7': 720, 'max_streams': 8},
        'RTX 4070 (Ada)':         {'p1': 980, 'p4': 800, 'p7': 590, 'max_streams': 5},
        'Quadro RTX 6000 (Turing)':{'p1': 800, 'p4': 650, 'p7': 480, 'max_streams': 0},
        'RTX A6000 (Ampere)':     {'p1': 1100,'p4': 900, 'p7': 660, 'max_streams': 0},
    }

    # 各代 GPU HEVC 1080p60 编码性能对比
    ENCODE_FPS_HEVC_1080P60 = {
        'GTX 1080 Ti (Pascal)':   {'p1': 380, 'p4': 280, 'p7': 200, 'max_streams': 3},
        'RTX 2080 Ti (Turing)':   {'p1': 620, 'p4': 480, 'p7': 350, 'max_streams': 5},
        'RTX 3080 (Ampere)':      {'p1': 820, 'p4': 660, 'p7': 480, 'max_streams': 5},
        'RTX 4090 (Ada)':         {'p1': 1280,'p4': 1050,'p7': 760, 'max_streams': 8},
        'RTX 4080 (Ada)':         {'p1': 1080,'p4': 880, 'p7': 640, 'max_streams': 8},
    }

    # 4K 编码性能
    ENCODE_FPS_4K = {
        'h264': {'RTX 3080': {'p1': 220, 'p4': 175, 'p7': 120}, 'RTX 4090': {'p1': 340, 'p4': 280, 'p7': 195}},
        'hevc': {'RTX 3080': {'p1': 185, 'p4': 145, 'p7': 100}, 'RTX 4090': {'p1': 290, 'p4': 235, 'p7': 165}},
        'av1':  {'RTX 4080': {'p1': 220, 'p4': 180, 'p7': 130}, 'RTX 4090': {'p1': 260, 'p4': 215, 'p7': 155}},
    }

    # 功耗与温度（1080p60 H.264 p4 预设）
    POWER_CONSUMPTION = {
        'RTX 4090': {'power_w': 65, 'temp_c': 52, 'gpu_util': 35},
        'RTX 4080': {'power_w': 55, 'temp_c': 48, 'gpu_util': 40},
        'RTX 3080': {'power_w': 80, 'temp_c': 62, 'gpu_util': 45},
        'RTX 2080 Ti': {'power_w': 95, 'temp_c': 68, 'gpu_util': 55},
    }

    # 编码速度与质量曲线（VMAF vs 码率）
    QUALITY_VS_BITRATE = {
        'h264_nvenc_p7_cq24': {'bitrate_mbps': 4.2, 'vmaf': 92.3, 'psnr_db': 38.5},
        'h264_nvenc_p7_cq26': {'bitrate_mbps': 3.1, 'vmaf': 89.8, 'psnr_db': 36.8},
        'h264_nvenc_p7_cq28': {'bitrate_mbps': 2.4, 'vmaf': 86.5, 'psnr_db': 35.1},
        'h264_nvenc_p4_cq24': {'bitrate_mbps': 4.5, 'vmaf': 91.5, 'psnr_db': 38.0},
        'h264_nvenc_p4_cq26': {'bitrate_mbps': 3.3, 'vmaf': 88.9, 'psnr_db': 36.4},
        'hevc_nvenc_p7_cq24': {'bitrate_mbps': 3.0, 'vmaf': 92.5, 'psnr_db': 38.7},
        'hevc_nvenc_p7_cq28': {'bitrate_mbps': 1.7, 'vmaf': 87.2, 'psnr_db': 35.5},
        'av1_nvenc_p7_cq24':  {'bitrate_mbps': 2.4, 'vmaf': 92.8, 'psnr_db': 38.9},
        'av1_nvenc_p7_cq28':  {'bitrate_mbps': 1.3, 'vmaf': 87.5, 'psnr_db': 35.7},
        # 同码率对比
        'libx264_slow_cq24':  {'bitrate_mbps': 3.8, 'vmaf': 93.1, 'psnr_db': 39.0},
        'libx265_slow_cq24':  {'bitrate_mbps': 2.6, 'vmaf': 93.5, 'psnr_db': 39.3},
    }
```

---

## 三、Intel QuickSync 加速

### 3.1 QSV 编码器

```python
class QSVEncoders:
    """Intel QuickSync Video 编码器原子表"""

    H264_QSV_PARAMS = {
        'preset': {'values':['veryfast','faster','fast','medium','slow','slower']},
        'profile': {'values':['baseline','main','high']},
        'level': {'values':['3.0','3.1','3.2','4.0','4.1','4.2','5.0','5.1','5.2']},
        'rate_control': {'values':['cbr','vbr','icq','qvbr','avbr'],'icq':'智能恒定质量','qvbr':'质量感知VBR'},
        'qmin': {'desc':'最小QP','range':'1-51'},
        'qmax': {'desc':'最大QP','range':'1-51'},
        'bit_rate': {'desc':'目标码率'},
        'max_bitrate': {'desc':'最大码率'},
        'gop_size': {'desc':'GOP长度','default':'0(auto)'},
        'bf': {'desc':'B帧数','range':'0-7','recommendation':'3'},
        'refs': {'desc':'参考帧数','range':'0-16'},
        'async_depth': {'desc':'异步深度','default':'4 (提高并行度)','range':'1-16'},
        'look_ahead': {'desc':'前瞻深度','range':'0-100','recommendation':'32'},
        'look_ahead_depth': {'desc':'前瞻帧数','range':'0-100'},
        'look_ahead_downsampling': {'values':['auto','off','2x','4x']},
        'trellis': {'values':['off','I','I+P','I+P+B']},
        'cavlc': {'desc':'使用CAVLC替代CABAC','type':'bool'},
        'idr_interval': {'desc':'IDR间隔','default':'0'},
        # === QSV 特有 ===
        'low_power': {'desc':'低功耗模式','type':'bool','note':'仅部分硬件支持'},
        'scenario': {'values':['unknown','displayremoting','videoconference','archive','livestreaming','cameracapture','videosurveillance'},
                     'livestreaming':'低延迟优化','archive':'存档优化'},
        'roi': {'desc':'感兴趣区域编码','format':'ROI列表'},
        # === VPP 参数（通过 vpp_qsv 滤镜）===
        'vpp': {
            'deinterlace': {'values':['bob','adi']},
            'denoise': {'range':'0-100'},
            'detail':  {'range':'0-100'},
            'framerate_proc': {'values':['24p','25p','30p','50i','60i']},
            'procamp': {'brightness':'-100~100','contrast':'0~10','saturation':'0~10','hue':'-180~180'},
            'scaling_mode': {'values':['auto','scale','compute']},
        },
    }

    HEVC_QSV_PARAMS = {
        'profile': {'values':['main','main10','main444','main444-10','mainsp'],
                    'recommendation':'main10 (10bit 优于 8bit 同码率 30%+)'},
        'gpb': {'desc':'Generalized P/B','type':'bool','note':'HEVC无B帧专用类型'},
        'transform_skip': {'desc':'变换跳过','type':'bool'},
        # === QSV HEVC 特有 ===
        'low_power': {'desc':'低功耗模式','note':'仅 Tiger Lake 及以后'},
    }

    AV1_QSV_PARAMS = {
        'profile': {'values':['main']},
        'preset': {'values':['veryfast','faster','fast','medium','slow','slower']},
        'tile_cols': {'values':['0','1','2','4'],'note':'0=自动'},
        'tile_rows': {'values':['0','1','2','4']},
        'async_depth': {'default':'4'},
        # === 限制 ===
        'min_hardware': 'Intel Arc A380 (Alchemist)',
        'min_driver': '31.0.101.4032+',
    }

    PRESETS = {
        'qsv_live': {
            'desc':'QSV 直播编码',
            'command':'ffmpeg -hwaccel qsv -c:v h264_qsv -i input.mp4 '
                      '-c:v h264_qsv -preset fast -profile:v high -b:v 6M -maxrate 6M '
                      '-bufsize 12M -g 120 -bf 3 -refs 4 -async_depth 4 -look_ahead 1 '
                      '-look_ahead_depth 32 -scenario livestreaming output.mp4'
        },
        'qsv_icq': {
            'desc':'QSV 智能恒定质量',
            'command':'ffmpeg -hwaccel qsv -c:v h264_qsv -i input.mp4 '
                      '-c:v h264_qsv -preset slower -profile:v high -look_ahead 1 '
                      '-look_ahead_depth 32 -rc icq -global_quality 25 -bf 3 -refs 4 output.mp4'
        },
        'qsv_hevc_10bit': {
            'desc':'QSV HEVC 10bit 高质量',
            'command':'ffmpeg -hwaccel qsv -c:v h264_qsv -i input.mp4 '
                      '-c:v hevc_qsv -preset slower -profile:v main10 -load_plugin hevc_hw '
                      '-look_ahead 1 -look_ahead_depth 40 -rc icq -global_quality 22 '
                      '-bf 4 -refs 4 -pix_fmt p010le output.mp4'
        },
        'qsv_av1': {
            'desc':'QSV AV1 (Arc)',
            'command':'ffmpeg -hwaccel qsv -c:v h264_qsv -i input.mp4 '
                      '-c:v av1_qsv -preset slower -rc icq -global_quality 25 '
                      '-tile_cols 2 -tile_rows 1 -b:v 4M output_av1.mp4'
        },
        'qsv_vpp_pipeline': {
            'desc':'QSV VPP 全管线（去隔行+降噪+缩放）',
            'command':'ffmpeg -hwaccel qsv -c:v h264_qsv -i input.ts '
                      '-vf "vpp_qsv=deinterlace=bob,denoise=50,detail=40, '
                      'w=1920:h=1080:fps=60" '
                      '-c:v h264_qsv -preset medium -b:v 8M -maxrate 10M -bufsize 16M '
                      '-bf 3 -refs 4 output.mp4'
        },
    }
```

### 3.2 QSV 解码器与滤镜

```python
class QSVDecodeFilter:
    """QSV 解码与滤镜"""

    DECODERS = {
        'h264_qsv':  {'profiles':['Baseline','Main','High']},
        'hevc_qsv':  {'profiles':['Main','Main10','Main444']},
        'av1_qsv':   {'profiles':['Main'],'min_hw':'Tiger Lake'},
        'vp9_qsv':   {'profiles':['Profile 0','Profile 2']},
        'mjpeg_qsv': {'profiles':[]},
        'mpeg2_qsv': {'profiles':['Main','High']},
        'vc1_qsv':   {'profiles':['Simple','Main','Advanced']},
    }

    FILTERS = {
        'scale_qsv': {
            'params': {'w':'宽','h':'高','format':'输出格式','mode':'scaling 模式'},
            'modes': {'auto':'自动','lowpower':'低功耗','compute':'计算'},
            'example': '-vf scale_qsv=w=1920:h=1080:mode=lowpower'
        },
        'vpp_qsv': {
            'desc': 'QSV 视频后处理',
            'params': {
                'deinterlace': '去隔行: bob/adi',
                'denoise': '降噪 0-100',
                'detail': '细节增强 0-100',
                'framerate': '帧率转换 24/25/30/50/60',
                'procamp': '亮度对比度饱和度色调',
                'w': '宽', 'h': '高',
                'scaling_mode': 'auto/scale/compute',
            },
            'example': '-vf vpp_qsv=deinterlace=bob,denoise=50,detail=40,w=1920:h=1080'
        },
        'overlay_qsv': {
            'params': {'x':'x坐标','y':'y坐标','w':'宽','h':'高'},
            'example': '-filter_complex "[0:v][1:v]overlay_qsv=x=10:y=10"'
        },
    }

    # 全 QSV 管线
    FULL_QSV_PIPELINE = {
        'command': 'ffmpeg -hwaccel qsv -hwaccel_output_format qsv '
                   '-c:v h264_qsv -i input.ts '
                   '-vf "vpp_qsv=deinterlace=bob,denoise=30,w=1920:h=1080" '
                   '-c:v h264_qsv -preset medium -b:v 8M -maxrate 10M -bufsize 16M '
                   '-bf 3 -refs 4 -async_depth 4 output.mp4',
        'note': '硬件解码→VPP后处理→硬件编码，全程零拷贝',
    }
```

### 3.3 QSV 性能基准

```python
class QSVBenchmark:
    """QSV 性能基准（参考值）"""

    ENCODE_FPS_1080P60 = {
        # H.264
        'Intel UHD 630 (8代)':         {'p_fast': 280, 'p_medium': 220, 'p_slow': 160},
        'Intel Iris Xe (11代)':        {'p_fast': 420, 'p_medium': 340, 'p_slow': 240},
        'Intel Arc A380':              {'p_fast': 580, 'p_medium': 470, 'p_slow': 330},
        'Intel Arc A750':              {'p_fast': 780, 'p_medium': 620, 'p_slow': 440},
        'Intel Arc A770':              {'p_fast': 900, 'p_medium': 720, 'p_slow': 510},
    }

    ENCODE_FPS_4K = {
        'h264': {'UHD 630': {'fast': 75,'medium': 55,'slow': 38},
                 'Arc A380':{'fast': 145,'medium':115,'slow': 80},
                 'Arc A770':{'fast': 230,'medium':185,'slow': 130}},
        'hevc': {'UHD 630': {'fast': 60,'medium': 45,'slow': 32},
                 'Arc A380':{'fast': 120,'medium': 95,'slow': 68},
                 'Arc A770':{'fast': 195,'medium':155,'slow': 110}},
        'av1':  {'Arc A380':{'fast': 85, 'medium': 65,'slow': 48},
                 'Arc A770':{'fast': 145,'medium':115,'slow': 82}},
    }

    POWER_CONSUMPTION = {
        'UHD 630':     {'power_w': 18, 'temp_c': 55},
        'Iris Xe':     {'power_w': 22, 'temp_c': 58},
        'Arc A380':    {'power_w': 35, 'temp_c': 60},
        'Arc A770':    {'power_w': 75, 'temp_c': 65},
    }

    # QSV vs NVENC vs libx264 同码率画质对比（1080p CBR 6Mbps）
    QUALITY_COMPARISON = {
        'libx264 medium':  {'vmaf': 88.5, 'fps': 90,  'cpu_util': 90},
        'libx264 slow':    {'vmaf': 91.2, 'fps': 35,  'cpu_util': 95},
        'h264_qsv medium': {'vmaf': 86.8, 'fps': 340, 'cpu_util': 8},
        'h264_qsv slow':   {'vmaf': 89.5, 'fps': 240, 'cpu_util': 10},
        'h264_nvenc p4':   {'vmaf': 87.3, 'fps': 780, 'cpu_util': 5},
        'h264_nvenc p7':   {'vmaf': 90.1, 'fps': 560, 'cpu_util': 6},
    }
```

---

## 四、AMD AMF 加速

### 4.1 AMF 编码器参数

```python
class AMFEncoders:
    """AMD AMF 编码器原子表"""

    H264_AMF_PARAMS = {
        'usage': {'values':['transcoding','ultralowlatency','lowlatency','webcam'],
                  'transcoding':'转码','ultralowlatency':'超低延迟'},
        'profile': {'values':['baseline','main','high']},
        'level': {'values':['4.0','4.1','4.2','5.0','5.1','5.2']},
        'rc': {'values':['cbr','vbr_peak','vbr_latency','cqp'],
               'cbr':'恒定','vbr_peak':'VBR峰值约束','vbr_latency':'VBR低延迟','cqp':'恒定QP'},
        'qp_i': {'desc':'I帧QP','range':'0-51'},
        'qp_p': {'desc':'P帧QP','range':'0-51'},
        'qp_b': {'desc':'B帧QP','range':'0-51'},
        'b:v': {'desc':'目标码率'},
        'maxrate': {'desc':'最大码率'},
        'bufsize': {'desc':'缓冲大小'},
        'g': {'desc':'GOP长度'},
        'bf': {'desc':'B帧数','range':'0-3'},
        'refs': {'desc':'参考帧数','range':'0-16'},
        # === AMF 特有 ===
        'quality': {'values':['speed','balanced','quality'],'balanced':'默认'},
        'preanalysis': {'desc':'预分析','type':'bool','note':'启用运动估计'},
        'paq': {'desc':'感知自适应量化','type':'bool'},
        'motion_quality': {'desc':'运动质量增强','type':'bool'},
        'enforce_hrd': {'desc':'强制HRD','type':'bool'},
        'filler_data': {'desc':'填充数据(CBR)','type':'bool'},
        'frame_skipping': {'desc':'跳帧','type':'bool'},
        'qmin': {'desc':'最小QP','range':'0-51'},
        'qmax': {'desc':'最大QP','range':'0-51'},
    }

    HEVC_AMF_PARAMS = {
        'profile': {'values':['main','main10']},
        'gop_size': {'desc':'GOP长度'},
        'bf': {'desc':'B帧数','range':'0-3'},
        'refs': {'desc':'参考帧数','range':'0-16'},
        'preanalysis': {'desc':'预分析'},
        'paq': {'desc':'PAQ'},
        # === AMF HEVC 特有 ===
        'header_insertion_mode': {'values':['none','gop','idr']},
        'gops_per_idr': {'desc':'每N个GOP一个IDR'},
        'min_qp_i': {'desc':'I帧最小QP'},
        'max_qp_i': {'desc':'I帧最大QP'},
        'min_qp_p': {'desc':'P帧最小QP'},
        'max_qp_p': {'desc':'P帧最大QP'},
    }

    AV1_AMF_PARAMS = {
        'profile': {'values':['main']},
        'usage': {'values':['transcoding','lowlatency','webcam']},
        'rc': {'values':['cbr','vbr_peak','vbr_latency','cqp']},
        'qp_i': {'range':'0-51'},
        'qp_p': {'range':'0-51'},
        'b:v': {'desc':'目标码率'},
        'gop_size': {'desc':'GOP长度'},
        'preanalysis': {'desc':'预分析'},
        'paq': {'desc':'PAQ'},
        'enforce_hrd': {'desc':'强制HRD'},
        # === AMF AV1 特有 ===
        'tile_cols': {'values':['0','1','2','4','8']},
        'tile_rows': {'values':['0','1','2','4']},
        'min_hw': 'Radeon RX 7000 系列 (RDNA3)',
    }

    PRESETS = {
        'amf_h264_live': {
            'command':'ffmpeg -hwaccel d3d11va -hwaccel_output_format d3d11va '
                      '-i input.mp4 -c:v h264_amf -usage lowlatency -rc cbr '
                      '-b:v 6M -maxrate 6M -bufsize 12M -g 120 -bf 2 -refs 4 '
                      '-quality balanced -preanalysis 1 -paq 1 output.mp4'
        },
        'amf_hevc_quality': {
            'command':'ffmpeg -hwaccel d3d11va -i input.mp4 '
                      '-c:v hevc_amf -usage transcoding -rc vbr_peak '
                      '-b:v 10M -maxrate 15M -bufsize 20M -g 300 -bf 3 -refs 4 '
                      '-quality quality -preanalysis 1 -paq 1 '
                      '-profile:v main10 -pix_fmt p010le output.mp4'
        },
        'amf_av1': {
            'command':'ffmpeg -hwaccel d3d11va -i input.mp4 '
                      '-c:v av1_amf -usage transcoding -rc vbr_peak '
                      '-b:v 6M -maxrate 9M -bufsize 12M -g 240 -bf 2 -refs 4 '
                      '-quality quality -preanalysis 1 -paq 1 '
                      '-tile_cols 2 -tile_rows 1 output_av1.mp4'
        },
    }
```

### 4.2 AMF 解码与性能

```python
class AMFDecodeBenchmark:
    """AMD AMF 解码（通过 DXVA）与性能"""

    # AMF 通过 d3d11va 间接实现硬件解码
    DECODE_VIA = 'd3d11va / dxva2'

    SUPPORTED_CODECS = {
        'h264':  {'profiles':['Baseline','Main','High']},
        'hevc':  {'profiles':['Main','Main10']},
        'av1':   {'profiles':['Main'],'min_hw':'RX 6000 (RDNA2)'},
        'vp9':   {'profiles':['Profile 0','Profile 2']},
        'mpeg2': {'profiles':['Main','High']},
        'vc1':   {'profiles':['Simple','Main','Advanced']},
    }

    ENCODE_FPS_1080P60 = {
        'RX 6800 XT (RDNA2)': {'h264': {'speed': 450, 'balanced': 360, 'quality': 250},
                               'hevc': {'speed': 380, 'balanced': 300, 'quality': 210}},
        'RX 7900 XTX (RDNA3)':{'h264': {'speed': 620, 'balanced': 500, 'quality': 350},
                               'hevc': {'speed': 540, 'balanced': 430, 'quality': 300},
                               'av1':  {'speed': 320, 'balanced': 250, 'quality': 180}},
        'RX 6700 XT (RDNA2)': {'h264': {'speed': 380, 'balanced': 300, 'quality': 210},
                               'hevc': {'speed': 320, 'balanced': 250, 'quality': 175}},
    }

    POWER_CONSUMPTION = {
        'RX 7900 XTX': {'power_w': 90, 'temp_c': 65, 'gpu_util': 40},
        'RX 6800 XT':  {'power_w': 100,'temp_c': 70, 'gpu_util': 50},
        'RX 6700 XT':  {'power_w': 80, 'temp_c': 68, 'gpu_util': 55},
    }
```

---

## 五、编码器对比与选型

### 5.1 质量对比（VMAF/PSNR/SSIM）

```python
class EncoderQualityComparison:
    """编码器质量对比（1080p, 同码率 6Mbps, VMAF 越高越好）"""

    QUALITY_MATRIX = {
        # 软件编码器
        'libx264 ultrafast':  {'vmaf': 82.5, 'psnr': 35.2, 'ssim': 0.932, 'fps': 480},
        'libx264 medium':     {'vmaf': 88.5, 'psnr': 37.8, 'ssim': 0.958, 'fps': 90},
        'libx264 slow':       {'vmaf': 91.2, 'psnr': 38.8, 'ssim': 0.967, 'fps': 35},
        'libx264 veryslow':   {'vmaf': 92.5, 'psnr': 39.3, 'ssim': 0.971, 'fps': 12},
        'libx265 medium':     {'vmaf': 91.8, 'psnr': 38.5, 'ssim': 0.965, 'fps': 45},
        'libx265 slow':       {'vmaf': 94.0, 'psnr': 39.8, 'ssim': 0.974, 'fps': 18},
        'libaom-av1 cpu-used 4':{'vmaf': 95.2, 'psnr': 40.5, 'ssim': 0.978, 'fps': 8},
        'libsvtav1 preset 6': {'vmaf': 93.5, 'psnr': 39.7, 'ssim': 0.973, 'fps': 35},
        # 硬件编码器（H.264）
        'h264_nvenc p4':  {'vmaf': 87.3, 'psnr': 37.2, 'ssim': 0.955, 'fps': 780},
        'h264_nvenc p7':  {'vmaf': 90.1, 'psnr': 38.3, 'ssim': 0.964, 'fps': 560},
        'h264_qsv medium':{'vmaf': 86.8, 'psnr': 36.9, 'ssim': 0.952, 'fps': 340},
        'h264_qsv slow':  {'vmaf': 89.5, 'psnr': 37.9, 'ssim': 0.962, 'fps': 240},
        'h264_amf balanced':{'vmaf': 86.2, 'psnr': 36.7, 'ssim': 0.951, 'fps': 360},
        'h264_amf quality':{'vmaf': 88.5, 'psnr': 37.5, 'ssim': 0.959, 'fps': 250},
        'h264_videotoolbox':{'vmaf': 85.5, 'psnr': 36.3, 'ssim': 0.948, 'fps': 420},
        # 硬件编码器（HEVC）
        'hevc_nvenc p7':  {'vmaf': 92.5, 'psnr': 38.7, 'ssim': 0.968, 'fps': 510},
        'hevc_qsv slow':  {'vmaf': 91.8, 'psnr': 38.3, 'ssim': 0.965, 'fps': 220},
        'hevc_amf quality':{'vmaf': 90.5, 'psnr': 37.8, 'ssim': 0.961, 'fps': 280},
        'hevc_videotoolbox':{'vmaf': 89.2, 'psnr': 37.3, 'ssim': 0.957, 'fps': 380},
        # 硬件编码器（AV1）
        'av1_nvenc p7':   {'vmaf': 93.0, 'psnr': 39.0, 'ssim': 0.970, 'fps': 280},
        'av1_qsv slow':   {'vmaf': 92.8, 'psnr': 38.8, 'ssim': 0.969, 'fps': 115},
        'av1_amf quality':{'vmaf': 91.5, 'psnr': 38.2, 'ssim': 0.965, 'fps': 180},
    }

    # 同 VMAF 目标下的码率对比（VMAF=90, 越低越好）
    BITRATE_AT_VMAF90 = {
        'libx264 slow':     {'bitrate_mbps': 5.8, 'fps': 35},
        'libx265 slow':     {'bitrate_mbps': 3.2, 'fps': 18},
        'h264_nvenc p7':    {'bitrate_mbps': 6.5, 'fps': 560},
        'hevc_nvenc p7':    {'bitrate_mbps': 3.5, 'fps': 510},
        'av1_nvenc p7':     {'bitrate_mbps': 2.8, 'fps': 280},
        'hevc_qsv slow':    {'bitrate_mbps': 3.8, 'fps': 220},
        'av1_qsv slow':     {'bitrate_mbps': 3.1, 'fps': 115},
        'libsvtav1 p6':     {'bitrate_mbps': 2.5, 'fps': 35},
    }
```

### 5.2 速度对比

```python
class EncoderSpeedComparison:
    """编码器速度对比矩阵"""

    # 1080p60 编码速度（fps）
    SPEED_MATRIX_1080P60 = {
        # 软件
        'libx264 ultrafast': {'fps': 480, 'cpu_util': 30},
        'libx264 medium':    {'fps': 90,  'cpu_util': 90},
        'libx264 slow':      {'fps': 35,  'cpu_util': 95},
        'libx264 veryslow':  {'fps': 12,  'cpu_util': 98},
        'libx265 medium':    {'fps': 45,  'cpu_util': 95},
        'libx265 slow':      {'fps': 18,  'cpu_util': 98},
        'libsvtav1 p8':      {'fps': 90,  'cpu_util': 90},
        'libsvtav1 p6':      {'fps': 35,  'cpu_util': 95},
        'libsvtav1 p4':      {'fps': 12,  'cpu_util': 98},
        # 硬件 H.264
        'h264_nvenc p1':     {'fps': 1450,'cpu_util': 3},
        'h264_nvenc p4':     {'fps': 780, 'cpu_util': 5},
        'h264_nvenc p7':     {'fps': 560, 'cpu_util': 6},
        'h264_qsv fast':     {'fps': 420, 'cpu_util': 8},
        'h264_qsv medium':   {'fps': 340, 'cpu_util': 10},
        'h264_qsv slow':     {'fps': 240, 'cpu_util': 12},
        'h264_amf speed':    {'fps': 450, 'cpu_util': 8},
        'h264_amf balanced': {'fps': 360, 'cpu_util': 10},
        'h264_amf quality':  {'fps': 250, 'cpu_util': 12},
        'h264_videotoolbox': {'fps': 420, 'cpu_util': 5},
        # 硬件 HEVC
        'hevc_nvenc p7':     {'fps': 510, 'cpu_util': 6},
        'hevc_qsv slow':     {'fps': 220, 'cpu_util': 12},
        'hevc_amf quality':  {'fps': 280, 'cpu_util': 12},
        'hevc_videotoolbox': {'fps': 380, 'cpu_util': 5},
        # 硬件 AV1
        'av1_nvenc p7':      {'fps': 280, 'cpu_util': 6},
        'av1_qsv slow':      {'fps': 115, 'cpu_util': 12},
        'av1_amf quality':   {'fps': 180, 'cpu_util': 12},
    }

    # 4K30 编码速度
    SPEED_MATRIX_4K30 = {
        'libx264 medium':    {'fps': 22,  'cpu_util': 95},
        'libx264 slow':      {'fps': 8,   'cpu_util': 98},
        'libx265 slow':      {'fps': 4,   'cpu_util': 99},
        'h264_nvenc p4':     {'fps': 175, 'cpu_util': 5},
        'h264_nvenc p7':     {'fps': 120, 'cpu_util': 6},
        'hevc_nvenc p7':     {'fps': 100, 'cpu_util': 6},
        'av1_nvenc p7':      {'fps': 75,  'cpu_util': 6},
        'h264_qsv medium':   {'fps': 85,  'cpu_util': 10},
        'hevc_qsv slow':     {'fps': 55,  'cpu_util': 12},
    }
```

### 5.3 文件大小对比

```python
class FileSizeComparison:
    """同 VMAF 目标下的文件大小对比"""

    # 10分钟 1080p60 视频，目标 VMAF=90
    FILE_SIZE_TABLE = {
        'libx264 slow':      {'size_mb': 435, 'vmaf': 90.2, 'encode_time_s': 171},
        'libx264 medium':    {'size_mb': 510, 'vmaf': 90.0, 'encode_time_s': 67},
        'libx265 slow':      {'size_mb': 240, 'vmaf': 90.1, 'encode_time_s': 333},
        'libx265 medium':    {'size_mb': 285, 'vmaf': 90.0, 'encode_time_s': 133},
        'libsvtav1 p6':      {'size_mb': 188, 'vmaf': 90.0, 'encode_time_s': 171},
        'libsvtav1 p4':      {'size_mb': 175, 'vmaf': 90.3, 'encode_time_s': 500},
        'h264_nvenc p7':     {'size_mb': 488, 'vmaf': 90.1, 'encode_time_s': 11},
        'hevc_nvenc p7':     {'size_mb': 263, 'vmaf': 90.0, 'encode_time_s': 12},
        'av1_nvenc p7':      {'size_mb': 210, 'vmaf': 90.2, 'encode_time_s': 21},
        'h264_qsv slow':     {'size_mb': 515, 'vmaf': 90.0, 'encode_time_s': 25},
        'hevc_qsv slow':     {'size_mb': 285, 'vmaf': 90.1, 'encode_time_s': 27},
        'av1_qsv slow':      {'size_mb': 233, 'vmaf': 90.0, 'encode_time_s': 52},
    }
```

### 5.4 选型决策矩阵

```python
class EncoderSelectionMatrix:
    """编码器选型决策矩阵"""

    DECISION_MATRIX = {
        'live_stream_youtube': {
            'recommended': 'h264_nvenc p4' if 'nvidia' else 'h264_qsv fast',
            'reason': '低延迟 + 兼容性 + 稳定码率',
            'alt': ['h264_amf balanced', 'h264_videotoolbox'],
            'codec': 'H.264 (兼容性最佳)',
            'bitrate': '6-12 Mbps (1080p60)',
            'latency': '<2s',
        },
        'vod_streaming': {
            'recommended': 'hevc_nvenc p7' if 'nvidia' else 'hevc_qsv slow',
            'reason': '点播场景延迟不敏感，优先画质与压缩比',
            'alt': ['libx265 slow (CPU 充足)', 'av1_nvenc p7'],
            'codec': 'HEVC (压缩比 + 兼容性平衡)',
            'bitrate': '3-8 Mbps (1080p60)',
        },
        'archive_storage': {
            'recommended': 'av1_nvenc p7' if 'rtx40' else 'libsvtav1 p4',
            'reason': '存档场景对编码时间不敏感，最大压缩比',
            'alt': ['hevc_nvenc p7 CQ', 'libx265 veryslow'],
            'codec': 'AV1 (最高压缩比)',
            'bitrate': 'CQ 24-26',
        },
        'realtime_gaming': {
            'recommended': 'h264_nvenc p1 tune ll',
            'reason': '极低延迟，零帧丢失',
            'alt': ['h264_nvenc p3 tune ll', 'h264_qsv low_power'],
            'codec': 'H.264',
            'bitrate': '10-20 Mbps',
            'latency': '<200ms',
        },
        'mobile_delivery': {
            'recommended': 'libsvtav1 p6',
            'reason': '移动端解码兼容性 + 带宽节省',
            'alt': ['hevc_nvenc p7', 'av1_qsv slow'],
            'codec': 'AV1 / HEVC',
            'bitrate': '2-4 Mbps (1080p60)',
        },
        'broadcast_production': {
            'recommended': 'libx264 medium / h264_nvenc p7',
            'reason': '广播级画质 + 工业标准兼容性',
            'alt': ['h264_qsv slow', 'prores (后期)'],
            'codec': 'H.264 High Profile',
            'bitrate': '15-50 Mbps',
        },
        'hdr_content': {
            'recommended': 'hevc_nvenc p7 main10',
            'reason': '10bit + HDR metadata 支持',
            'alt': ['hevc_qsv slow main10', 'hevc_amf quality main10'],
            'codec': 'HEVC Main10',
            'bitrate': '20-50 Mbps (4K HDR)',
        },
    }

    # 决策树
    DECISION_TREE = [
        {'q':'是否需要实时直播?', 'y':'goto latency_sensitive', 'n':'goto quality_oriented'},
        {'q':'latency_sensitive: 延迟要求?', 'y':'<200ms → h264_nvenc p1 tune ll', 'n':'<2s → h264_nvenc p4 / h264_qsv fast'},
        {'q':'quality_oriented: 编码时间是否充裕?', 'y':'goto cpu_encode', 'n':'goto gpu_encode'},
        {'q':'cpu_encode: 是否需要最高压缩比?', 'y':'libsvtav1 p4-6 / libaom-av1', 'n':'libx265 slow / libx264 slow'},
        {'q':'gpu_encode: 是否有 AV1 硬件编码?', 'y':'av1_nvenc p7 / av1_qsv slow', 'n':'hevc_nvenc p7 / hevc_qsv slow'},
    ]
```

---

## 六、编码优化策略

### 6.1 码率控制优化

```python
class BitrateControlOptimization:
    """码率控制策略原子模型"""

    RATE_CONTROL_MODES = {
        'CBR': {
            'desc': '恒定码率',
            'pros': ['码率稳定','缓冲兼容性好','直播首选'],
            'cons': ['动态场景画质波动','浪费静态场景码率'],
            'params': {'b:v':'目标','maxrate':'=b:v','bufsize':'2×b:v'},
            'use_case': '直播流(YouTube/Twitch/Bilibili)',
            'example': '-rc cbr -b:v 6M -maxrate 6M -bufsize 12M',
        },
        'VBR': {
            'desc': '可变码率',
            'pros': ['动态分配码率','画质更均匀'],
            'cons': ['码率不可预测','缓冲兼容性差'],
            'params': {'b:v':'目标','maxrate':'上限','bufsize':'缓冲'},
            'use_case': '点播/文件分发',
            'example': '-rc vbr -b:v 6M -maxrate 10M -bufsize 16M',
        },
        'CQP/CQ': {
            'desc': '恒定量化参数/恒定质量',
            'pros': ['画质一致','可预测','存档首选'],
            'cons': ['码率不可控','复杂场景码率飙升'],
            'params': {'qp':'qpi:qpp:qpb (H264)','cq':'质量值'},
            'use_case': '存档/质量基准',
            'example': '-rc constqp -qp 22:24:26 / -rc vbr -cq 24',
        },
        'VBR_2PASS': {
            'desc': '两遍 VBR',
            'pros': ['码率精确','画质最优'],
            'cons': ['编码时间翻倍','不支持实时'],
            'params': {'b:v':'目标','maxrate':'上限'},
            'use_case': '离线高质量编码',
            'example': '-pass 1 -b:v 6M ... -pass 2 -b:v 6M ...',
        },
        'ICQ': {
            'desc': '智能恒定质量 (QSV)',
            'pros': ['比CQP更智能','场景感知'],
            'cons': ['仅QSV支持'],
            'params': {'global_quality':'ICQ值 1-51'},
            'use_case': 'QSV 存档/点播',
            'example': '-rc icq -global_quality 25',
        },
        'QVBR': {
            'desc': '质量感知VBR (QSV)',
            'pros': ['兼顾画质与码率','智能分配'],
            'cons': ['仅QSV支持'],
            'params': {'global_quality':'质量','b:v':'目标码率'},
            'use_case': 'QSV 点播/直播',
            'example': '-rc qvbr -global_quality 25 -b:v 6M',
        },
    }

    # 码率分配策略
    BITRATE_ALLOCATION = {
        'uniform': {'desc':'均匀分配','use':'简单场景'},
        'content_aware': {'desc':'内容感知(LookAhead)','use':'复杂动态场景','param':'-rc-lookahead 32'},
        'aq_spatial': {'desc':'空间AQ','use':'细节丰富场景','param':'-spatial_aq 1'},
        'aq_temporal': {'desc':'时间AQ','use':'运动场景','param':'-temporal_aq 1'},
        'roi': {'desc':'ROI编码','use':'人脸/关键区域','param':'ROI映射表'},
    }

    # 场景切换检测
    SCENE_CHANGE_DETECTION = {
        'libx264': {'param':'-sc_threshold 40','default':40,'range':'0-100'},
        'libx265': {'param':'--scenecut 40','default':40},
        'h264_nvenc': {'param':'(自动,受preset影响)','note':'p4+ 启用场景切换检测'},
        'h264_qsv': {'param':'(通过lookahead自动)'},
        'libsvtav1': {'param':'--scd 1','default':1},
    }
```

### 6.2 前置处理优化

```python
class PreprocessingOptimization:
    """前置处理优化原子模型"""

    SCALING_ALGORITHMS = {
        'bilinear':  {'speed':'fastest','quality':'low','gpu':'scale_cuda/scale_qsv default'},
        'bicubic':   {'speed':'fast','quality':'medium','gpu':'scale_npp interp=cubic'},
        'lanczos':   {'speed':'slow','quality':'high','cpu':'scale=lanczos','gpu':'scale_cuda=algo=lanczos'},
        'spline':    {'speed':'slow','quality':'high','cpu':'scale=spline'},
        'lanczos3':  {'speed':'slowest','quality':'highest','cpu':'scale=flags=lanczos'},
        'gaussian':  {'speed':'fast','quality':'medium','use':'平滑降采样'},
        'zscale':    {'speed':'medium','quality':'highest','note':'基于 zimg，色度采样最优'},
    }

    DENOISE_FILTERS = {
        'hqdn3d':    {'desc':'高质量3D降噪','params':'luma_spat:luma_temp:chroma_spat:chroma_temp','example':'hqdn3d=3:2:2:2'},
        'nlmeans':   {'desc':'非局部均值降噪','params':'s:p:r','example':'nlmeans=s=8:p=3:r=7','quality':'高'},
        'bm3d':      {'desc':'BM3D降噪','quality':'highest','speed':'very slow','example':'bm3d=sigma=5'},
        'vaguedenoiser':{'desc':'小波降噪','params':'threshold:method:nsteps','example':'vaguedenoiser=threshold=2'},
        'fftdn':     {'desc':'FFT降噪','params':'sigma:nf','example':'fftdn=sigma=8'},
        'vaguedenoiser_vulkan':{'desc':'GPU小波降噪(Vulkan)','speed':'fast'},
        'nlmeans_cuda':{'desc':'GPU NLMeans','note':'实验性'},
    }

    SHARPEN_FILTERS = {
        'unsharp':     {'desc':'反锐化掩模','params':'luma_msize:luma_amount:chroma_msize:chroma_amount','example':'unsharp=5:5:1.0:5:5:0.0'},
        'unsharp_cuda':{'desc':'GPU反锐化','speed':'fast'},
        'smartblur':   {'desc':'智能模糊/锐化','example':'smartblur=lr=1:ls=-1.0'},
        'minterpolate':{'desc':'运动补偿插帧','params':'mi_mode:mc_mode:me_mode:me_fps','example':'minterpolate=fps=60:mi_mode=mci'},
        'hqdn3d+unsharp':{'desc':'降噪后锐化(常用组合)','example':'hqdn3d=3:2:2:2,unsharp=5:5:0.8'},
    }

    COLORSPACE_CONVERSION = {
        'zscale': {
            'desc': '专业色彩空间转换 (zimg)',
            'params': {'t':'空间','m':'矩阵','p':'原色','r':'范围','npl':'标称峰值'},
            'example_bt2020_to_bt709': 'zscale=t=709:m=709:p=709:r=tv,tonemap=tonemap=hable:desat=0',
        },
        'colorspace': {
            'desc': '色彩空间转换滤镜',
            'params': {'all':'全部参数','space':'空间','range':'范围'},
            'example': 'colorspace=all=bt709:iall=bt2020',
        },
        'colormatrix': {
            'desc': '色彩矩阵转换(旧)',
            'params': {'src':'源','dst':'目标'},
            'example': 'colormatrix=bt2020nc:bt709',
        },
        'tonemap': {
            'desc': '色调映射 (HDR→SDR)',
            'algorithms': {'none':'无','linear':'线性','reinhard':'Reinhard','hable':'Hable','mobius':'Mobius','gamma':'Gamma'},
            'example': 'tonemap=tonemap=hable:desat=0:t=100',
        },
    }

    # 前置处理管线示例
    PIPELINES = {
        'upscaling_enhance': {
            'desc': ' upscale + 降噪 + 锐化',
            'command': '-vf "scale=1920:1080:flags=lanczos,hqdn3d=2:1:1:1,unsharp=5:5:0.6"',
        },
        'hdr_to_sdr': {
            'desc': 'HDR10 → SDR BT.709',
            'command': '-vf "zscale=t=709:m=709:p=709:r=tv,tonemap=tonemap=hable:desat=0:t=100,zscale=t=709:m=709:p=709:r=tv,format=yuv420p"',
        },
        'denoise_sharpen_gpu': {
            'desc': 'GPU 降噪 + 锐化（CUDA）',
            'command': '-vf "hqdn3d=3:2:2:2,unsharp_cuda=5:5:0.8"  # hqdn3d 在 CPU, unsharp_cuda 在 GPU',
        },
        'frame_interpolation': {
            'desc': ' 30fps → 60fps 运动插帧',
            'command': '-vf "minterpolate=fps=60:mi_mode=mci:mc_mode=obmc:me_mode=bidir"',
        },
    }
```

### 6.3 高级编码参数

```python
class AdvancedEncodingParams:
    """高级编码参数原子模型"""

    GOP_STRUCTURE = {
        'description': 'GOP (Group of Pictures) 结构优化',
        'types': {
            'open_gop': {'desc':'开放GOP','use':'直播/低延迟','idr_interval':'大'},
            'closed_gop': {'desc':'闭合GOP','use':'存档/可剪辑','idr_interval':'=gop_size'},
        },
        'gop_size_strategy': {
            'live': {'gop':'2×fps','reason':'低延迟 + 随机访问'},
            'vod': {'gop':'5-10s','reason':'画质 + 压缩比'},
            'archive': {'gop':'10-30s','reason':'最大压缩比'},
        },
    }

    BFRAME_CONFIG = {
        'description': 'B 帧配置策略',
        'count': {
            '0': {'use':'最低延迟(直播)','quality':'low'},
            '1-2': {'use':'直播/低延迟','quality':'medium'},
            '3-4': {'use':'点播/存档','quality':'high'},
            '5+': {'use':'离线存档','quality':'highest','constraint':'受DPB限制'},
        },
        'b_ref_mode': {
            'disabled': {'desc':'B帧不作为参考','use':'兼容性最好'},
            'each': {'desc':'每个B帧都作为参考','use':'最大压缩比'},
            'middle': {'desc':'仅中间B帧作为参考','use':'压缩比与兼容性平衡'},
        },
        'b_frame_strategy': {
            'libx264': '-b_strategy 2',
            'libx265': '--b-adapt 2',
            'h264_nvenc': '-b_ref_mode middle (p4+)',
            'h264_qsv': '通过lookahead自动',
        },
    }

    REFERENCE_FRAMES = {
        'description': '参考帧管理',
        'count': {
            '1': {'use':'直播','compat':'所有设备'},
            '2-3': {'use':'直播/点播','compat':'绝大多数设备'},
            '4-5': {'use':'点播','compat':'现代设备'},
            '6-8': {'use':'存档','compat':'部分设备可能不解'},
            '9-16': {'use':'专业存档','compat':'兼容性差'},
        },
        'constraint': '参考帧数 × (B帧数+1) ≤ DPB 大小（H.264 Level 4.1 = 4, Level 5.1 = 16）',
    }

    QUANTIZATION = {
        'qp_range': {'min':0,'max':51,'recommended':'18-28 (可接受), 20-24 (优质)'},
        'qpi_qpp_qpb': {
            'typical': {'i':22,'p':24,'b':26},
            'high_quality': {'i':20,'p':22,'b':24},
            'archive': {'i':18,'p':20,'b':22},
        },
        'aq': {
            'spatial_aq': '空间AQ: 为平坦区域分配更多比特',
            'temporal_aq': '时间AQ: 为静态区域分配更多比特',
            'aq_strength': 'AQ强度 (1-15, 默认8)',
        },
    }

    LOOP_FILTER = {
        'deblock': {
            'libx264': '-deblock alpha:beta (默认 0:0)',
            'libx265': '--deblock alpha:beta (默认 0:0)',
            'recommendation': '动画: -1:-1, 真人: 0:0, 压缩比优先: 1:1',
        },
        'sao': {
            'desc': 'HEVC Sample Adaptive Offset',
            'params': {'libx265':'--no-sao (关闭)', 'hevc_nvenc':'(默认开启)'},
            'recommendation': '关闭可提升锐度但增加码率',
        },
    }
```

---

## 七、批量处理与自动化

### 7.1 批量转码脚本

```python
class BatchTranscodeScripts:
    """批量转码自动化脚本"""

    POWERSHELL_BATCH = '''
# Windows PowerShell 批量转码脚本
$inputDir = "D:\\videos\\input"
$outputDir = "D:\\videos\\output"
$ffmpegPath = "ffmpeg"

Get-ChildItem -Path $inputDir -Include *.mp4,*.mkv,*.mov,*.avi -Recurse | ForEach-Object {
    $outputFile = Join-Path $outputDir ($_.BaseName + "_h264.mp4")
    
    # NVENC 硬件编码
    $command = "$ffmpegPath -y -i `"$($_.FullName)`" " +
               "-c:v h264_nvenc -preset p5 -rc vbr -b:v 8M -maxrate 12M -bufsize 16M " +
               "-g 240 -bf 3 -refs 4 -spatial_aq 1 -temporal_aq 1 -rc-lookahead 32 " +
               "-c:a aac -b:a 192k -movflags +faststart `"$outputFile`""
    
    Write-Host "转码: $($_.Name) → $outputFile"
    Invoke-Expression $command
}
Write-Host "批量转码完成"
'''

    BASH_BATCH = '''
#!/bin/bash
# Linux/macOS 批量转码脚本
INPUT_DIR="/data/videos/input"
OUTPUT_DIR="/data/videos/output"
LOG_FILE="/data/logs/transcode.log"

mkdir -p "$OUTPUT_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

find "$INPUT_DIR" -type f \\( -name "*.mp4" -o -name "*.mkv" -o -name "*.mov" \\) | while read -r input; do
    rel_path="${input#$INPUT_DIR/}"
    output="$OUTPUT_DIR/${rel_path%.*}_h264.mp4"
    mkdir -p "$(dirname "$output")"
    
    echo "[$(date)] 转码: $input → $output" | tee -a "$LOG_FILE"
    
    ffmpeg -y -i "$input" \
        -c:v h264_nvenc -preset p5 -rc vbr -b:v 8M -maxrate 12M -bufsize 16M \
        -g 240 -bf 3 -refs 4 -spatial_aq 1 -temporal_aq 1 -rc-lookahead 32 \
        -c:a aac -b:a 192k -movflags +faststart \
        "$output" 2>>"$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        echo "[$(date)] 成功: $output" | tee -a "$LOG_FILE"
    else
        echo "[$(date)] 失败: $input" | tee -a "$LOG_FILE"
    fi
done
echo "批量转码完成"
'''

    PYTHON_BATCH = '''
import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

class BatchTranscoder:
    def __init__(self, input_dir, output_dir, encoder='h264_nvenc'):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.encoder = encoder
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_encoding_params(self, encoder):
        params = {
            'h264_nvenc': ['-c:v','h264_nvenc','-preset','p5','-rc','vbr',
                          '-b:v','8M','-maxrate','12M','-bufsize','16M',
                          '-g','240','-bf','3','-refs','4',
                          '-spatial_aq','1','-temporal_aq','1','-rc-lookahead','32'],
            'hevc_nvenc': ['-c:v','hevc_nvenc','-preset','p7','-rc','vbr',
                          '-b:v','5M','-maxrate','8M','-bufsize','12M',
                          '-g','240','-bf','4','-refs','4',
                          '-profile:v','main10','-pix_fmt','p010le',
                          '-spatial_aq','1','-temporal_aq','1'],
            'h264_qsv': ['-c:v','h264_qsv','-preset','slower','-rc','icq',
                        '-global_quality','25','-bf','3','-refs','4',
                        '-look_ahead','1','-look_ahead_depth','32'],
        }
        return params.get(encoder, params['h264_nvenc'])
        
    def transcode(self, input_path):
        output_path = self.output_dir / (Path(input_path).stem + '_out.mp4')
        cmd = ['ffmpeg','-y','-i',str(input_path)] + self.get_encoding_params(self.encoder) + \
              ['-c:a','aac','-b:a','192k','-movflags','+faststart',str(output_path)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                return {'status':'success','input':input_path,'output':str(output_path)}
            return {'status':'error','input':input_path,'error':result.stderr[-500:]}
        except subprocess.TimeoutExpired:
            return {'status':'timeout','input':input_path}
            
    def run_batch(self, max_workers=3, extensions=('.mp4','.mkv','.mov','.avi')):
        files = [f for f in self.input_dir.rglob('*') if f.suffix.lower() in extensions]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.transcode, f): f for f in files}
            for future in as_completed(futures):
                result = future.result()
                print(f"[{result['status']}] {result['input']}")
                if result['status'] != 'success':
                    print(f"  Error: {result.get('error','unknown')}")

# 使用
transcoder = BatchTranscoder('D:/videos/input', 'D:/videos/output', 'h264_nvenc')
transcoder.run_batch(max_workers=3)
'''
```

### 7.2 多分辨率输出（自适应流）

```python
class AdaptiveBitrateStreaming:
    """自适应码率流（ABR）生成"""

    # HLS 多分辨率生成
    HLS_MULTI_RES = '''
ffmpeg -i input.mp4 \\
  -filter_complex "
    [0:v]split=3[v1][v2][v3];
    [v1]scale=1920:1080[v1out];
    [v2]scale=1280:720[v2out];
    [v3]scale=854:480[v3out]
  " \\
  -map "[v1out]" -c:v:0 h264_nvenc -preset p5 -b:v:0 5M -maxrate:0 7M -bufsize:0 10M \\
  -map "[v2out]" -c:v:1 h264_nvenc -preset p5 -b:v:1 3M -maxrate:1 4M -bufsize:1 6M \\
  -map "[v3out]" -c:v:2 h264_nvenc -preset p5 -b:v:2 1.5M -maxrate:2 2M -bufsize:2 3M \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -map a:0 -c:a:1 aac -b:a:1 96k \\
  -map a:0 -c:a:2 aac -b:a:2 64k \\
  -f hls -hls_time 6 -hls_playlist_type vod \\
  -hls_segment_filename "stream_%v/seg_%03d.ts" \\
  -master_pl_name master.m3u8 \\
  -var_stream_map "v:0,a:0 v:1,a:1 v:2,a:2" \\
  stream_%v.m3u8
'''

    # DASH 多分辨率生成
    DASH_MULTI_RES = '''
ffmpeg -i input.mp4 \\
  -filter_complex "
    [0:v]split=3[v1][v2][v3];
    [v1]scale=1920:1080[v1out];
    [v2]scale=1280:720[v2out];
    [v3]scale=854:480[v3out]
  " \\
  -map "[v1out]" -c:v:0 libx264 -preset medium -b:v:0 5M \\
  -map "[v2out]" -c:v:1 libx264 -preset medium -b:v:1 3M \\
  -map "[v3out]" -c:v:2 libx264 -preset medium -b:v:2 1.5M \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -use_template 1 -use_timeline 1 \\
  -adaptation_sets "id=0,streams=v:0,v:1,v:2 id=1,streams=a:0" \\
  -f dash manifest.mpd
'''

    # 标准分辨率阶梯
    RESOLUTION_LADDER = {
        '4K':    {'res':'3840x2160','bitrate_h264':'15-25M','bitrate_hevc':'8-15M','bitrate_av1':'5-10M'},
        '1440p': {'res':'2560x1440','bitrate_h264':'10-16M','bitrate_hevc':'5-10M','bitrate_av1':'4-7M'},
        '1080p': {'res':'1920x1080','bitrate_h264':'5-8M', 'bitrate_hevc':'3-5M', 'bitrate_av1':'2-4M'},
        '720p':  {'res':'1280x720', 'bitrate_h264':'3-5M', 'bitrate_hevc':'2-3M', 'bitrate_av1':'1-2M'},
        '480p':  {'res':'854x480',  'bitrate_h264':'1-2M', 'bitrate_hevc':'0.5-1M','bitrate_av1':'0.4-0.8M'},
        '360p':  {'res':'640x360',  'bitrate_h264':'0.5-1M','bitrate_hevc':'0.3-0.5M','bitrate_av1':'0.2-0.4M'},
    }
```

### 7.3 渲染队列管理

```python
class RenderQueueManager:
    """渲染队列管理原子模型"""

    QUEUE_SYSTEM = {
        'simple_queue': {
            'desc': '简单文件队列',
            'impl': '文本文件列表，逐个处理',
            'script': 'Get-Content queue.txt | ForEach-Object { ffmpeg ... }',
        },
        'priority_queue': {
            'desc': '优先级队列',
            'impl': '按优先级排序的 JSON 队列',
            'params': {'file':'文件','priority':'优先级','output':'输出','params':'参数'},
        },
        'gpu_pool': {
            'desc': 'GPU 池化',
            'impl': '多 GPU 并行处理',
            'params': {'gpu_id':'GPU索引','max_concurrent':'每GPU最大并发'},
        },
        'distributed': {
            'desc': '分布式队列',
            'impl': 'Redis/RabbitMQ + Worker节点',
            'params': {'worker_id':'节点ID','redis_url':'队列地址'},
        },
    }

    POWERSHELL_QUEUE = '''
# 多 GPU 渲染队列管理
$queue = @(
    @{file="video1.mp4"; gpu=0; preset="p7"; bitrate="8M"},
    @{file="video2.mp4"; gpu=0; preset="p5"; bitrate="6M"},
    @{file="video3.mp4"; gpu=1; preset="p7"; bitrate="10M"}
)

$jobs = @()
foreach ($task in $queue) {
    $jobs += Start-Job -ScriptBlock {
        param($file, $gpu, $preset, $bitrate)
        ffmpeg -y -hwaccel cuda -hwaccel_output_format cuda `
            -i $file -c:v h264_nvenc -gpu $gpu -preset $preset `
            -rc vbr -b:v $bitrate -spatial_aq 1 -temporal_aq 1 `
            "$($file -replace '\.[^.]+$', '')_out.mp4"
    } -ArgumentList $task.file, $task.gpu, $task.preset, $task.bitrate
}
$jobs | Wait-Job | Receive-Job
'''
```

### 7.4 与 AE/Premiere 集成

```python
class AdobeIntegration:
    """FFmpeg 与 Adobe 系列集成"""

    AE_WATCH_FOLDER = {
        'desc': 'AE 渲染监视文件夹 → FFmpeg 后处理',
        'workflow': [
            '1. AE 输出无损/低压缩到 watch 文件夹',
            '2. PowerShell 监视文件夹新增文件',
            '3. FFmpeg 转码为目标格式',
            '4. 完成后移动到最终输出文件夹',
        ],
        'script': '''
$watchPath = "D:\\AE_Output"
$finalPath = "D:\\Final_Output"
$watcher = New-Object System.IO.FileSystemWatcher $watchPath, "*.mov"
$watcher.EnableRaisingEvents = $true

Register-ObjectEvent $watcher "Created" -Action {
    $file = $Event.SourceEventArgs.FullPath
    Start-Sleep -Seconds 5  # 等待文件写入完成
    
    $output = Join-Path $finalPath ([System.IO.Path]::GetFileNameWithoutExtension($file) + ".mp4")
    ffmpeg -y -i "$file" -c:v h264_nvenc -preset p7 -rc vbr -b:v 10M `
        -c:a aac -b:a 192k -movflags +faststart "$output"
    
    if (Test-Path $output) { Remove-Item $file }
}
'''
    }

    PREMIERE_DIRECT = {
        'desc': 'Premiere 直接调用 FFmpeg（通过 XMP/Watch Folder）',
        'workflow': [
            '1. Premiere 序列 → 导出 → Watch Folder',
            '2. FFmpeg 监视 → 自动转码',
            '3. 输出到目标平台规格',
        ],
    }

    MEDIA_ENCODER_BRIDGE = {
        'desc': 'Media Encoder + FFmpeg 混合管线',
        'use_case': 'AE/Premiere 渲染 ProRes/DNxHR → FFmpeg 硬件转码为 H.264/HEVC',
        'command': 'ffmpeg -i prores_output.mov -c:v hevc_nvenc -preset p7 -rc vbr -b:v 8M -c:a aac final.mp4',
    }
```

---

## 八、故障排查

### 8.1 硬件加速不生效

```python
class HardwareAccelTroubleshoot:
    """硬件加速故障排查"""

    SYMPTOMS_AND_SOLUTIONS = {
        'hwaccel_not_used': {
            'symptom': 'CPU 使用率高，GPU 使用率为 0',
            'causes': [
                '未指定 -hwaccel 参数',
                '编码器未使用硬件编码器（如使用 libx264 而非 h264_nvenc）',
                '滤镜链中包含 CPU 滤镜，导致 hw→sw 回拷',
                'FFmpeg 未编译硬件加速支持',
            ],
            'diagnosis': [
                'ffmpeg -hwaccels  # 检查支持的硬件加速方法',
                'ffmpeg -encoders | grep nvenc  # 检查编码器',
                'ffmpeg -buildconf  # 检查编译选项',
            ],
            'solutions': [
                '添加 -hwaccel cuda -hwaccel_output_format cuda',
                '使用硬件编码器 -c:v h264_nvenc',
                '替换 CPU 滤镜为 GPU 滤镜 (scale→scale_cuda)',
                '重新编译 FFmpeg 或使用支持硬件加速的版本',
            ],
        },
        'cuda_error': {
            'symptom': 'CUDA error: no kernel image is available for execution on the device',
            'causes': ['GPU 计算能力不匹配', 'CUDA 版本与驱动不匹配'],
            'solutions': [
                '更新 NVIDIA 驱动到最新版本',
                '检查 GPU 计算能力: nvidia-smi --query-gpu=compute_cap --format=csv',
                'NVENC 需要 compute capability 3.5+ (Kepler 及以后)',
            ],
        },
        'nvenc_session_limit': {
            'symptom': 'OpenEncodeSessionEx failed: out of memory (10)',
            'causes': ['消费级 GPU NVENC 会话数限制 (3-5 个)'],
            'solutions': [
                '减少同时编码的流数量',
                '使用 Quadro/Tesla GPU (无会话限制)',
                '应用 NVENC 会话限制补丁 (NVIDIA 驱动修改)',
                '切换到 QSV/AMF 编码器分担负载',
            ],
        },
        'qsv_init_failed': {
            'symptom': 'Error initializing an MFX session',
            'causes': ['Intel 显卡驱动未安装', 'MediaSDK/oneVPL 未安装'],
            'solutions': [
                '安装 Intel 显卡驱动',
                '安装 Intel Media SDK (旧) 或 oneVPL (新)',
                'Windows: 检查 D3D11 是否可用',
                'Linux: 检查 /dev/dri/renderD128 是否存在',
            ],
        },
        'amf_not_found': {
            'symptom': 'Unknown encoder h264_amf',
            'causes': ['FFmpeg 未编译 AMF 支持', 'AMD 驱动未安装'],
            'solutions': [
                '使用支持 AMF 的 FFmpeg 版本',
                '安装 AMD Adrenalin 驱动',
                '检查 AMF Runtime 是否安装',
            ],
        },
        'vaapi_init_failed': {
            'symptom': 'Failed to initialise VAAPI connection',
            'causes': ['VA-API 驱动未安装', '设备路径错误'],
            'solutions': [
                '安装 libva 和 vaapi-driver',
                '检查设备: ls /dev/dri/',
                '设置 LIBVA_DRIVER_NAME=iHD (Intel) 或 amdgpu (AMD)',
                ' vainfo  # 检查 VA-API 状态',
            ],
        },
    }
```

### 8.2 编码质量问题

```python
class EncodingQualityTroubleshoot:
    """编码质量故障排查"""

    ISSUES = {
        'blocky_artifacts': {
            'symptom': '画面出现块状伪影，尤其在运动场景',
            'causes': ['码率过低', 'CBR 模式下复杂场景码率不足', '缺少 AQ'],
            'solutions': [
                '提高码率或使用 VBR 模式',
                '启用 spatial_aq 和 temporal_aq',
                '增加 maxrate 和 bufsize',
                '使用更高质量预设 (p5-p7)',
            ],
        },
        'banding': {
            'symptom': '渐变区域出现色带',
            'causes': ['8bit 深度', '码率不足'],
            'solutions': [
                '使用 10bit 编码 (pix_fmt p010le, profile main10)',
                '提高码率',
                '添加 dithering: -vf format=yuv420p10le',
            ],
        },
        'color_shift': {
            'symptom': '编码后颜色偏移',
            'causes': ['色彩范围不匹配 (TV vs PC range)', '色彩矩阵错误'],
            'solutions': [
                '指定色彩范围: -color_range tv/pc',
                '指定色彩矩阵: -colorspace bt709',
                '指定原色: -color_primaries bt709',
                '指定传输特性: -color_trc bt709',
                '使用 zscale 滤镜精确转换',
            ],
            'command': 'ffmpeg -i input.mp4 -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:v h264_nvenc output.mp4',
        },
        'temporal_flicker': {
            'symptom': '画面闪烁/抖动',
            'causes': ['B帧过多导致时域不稳定', 'temporal_aq 未启用'],
            'solutions': [
                '减少 B帧数量',
                '启用 temporal_aq',
                '增加 refs 参考帧',
                '使用更高质量预设',
            ],
        },
        'soft_blurry': {
            'symptom': '画面偏软/模糊',
            'causes': ['码率不足', '默认 deblock 过强', '缺少锐化'],
            'solutions': [
                '提高码率',
                '调整 deblock 参数 (libx264: -deblock -1:-1)',
                '添加 unsharp 滤镜: -vf unsharp=5:5:0.6',
                '关闭 SAO (HEVC: -x265-params no-sao=1)',
            ],
        },
    }
```

### 8.3 性能瓶颈诊断

```python
class PerformanceBottleneck:
    """性能瓶颈诊断"""

    DIAGNOSTIC_TOOLS = {
        'gpu_monitor': {
            'nvidia': 'nvidia-smi dmon -s pucvmet -d 1',
            'intel':  'intel_gpu_top',
            'amd':    'radeontop',
        },
        'ffmpeg_stats': {
            'cpu': '-stats',
            'progress': '-progress pipe:1',
            'benchmark': '-benchmark',
        },
        'profiling': {
            'filter_graph': '-filter_threads 1 -debug 1',
            'frame_timing': '-v debug',
        },
    }

    BOTTLENECK_MATRIX = {
        'cpu_bottleneck': {
            'symptom': 'CPU 100%, GPU <30%',
            'causes': ['CPU 滤镜 (scale, hqdn3d)', '音频编码', 'I/O 瓶颈'],
            'solutions': [
                '替换 CPU 滤镜为 GPU 滤镜',
                '使用硬件音频编码器 (如有)',
                '增加 -threads 参数',
                '使用 SSD 替代 HDD',
            ],
        },
        'gpu_bottleneck': {
            'symptom': 'GPU 100%, CPU <30%',
            'causes': ['GPU 性能不足', '并发流过多', '预设过高'],
            'solutions': [
                '降低预设 (p7→p5)',
                '减少并发流数量',
                '升级 GPU',
                '使用多 GPU 分流',
            ],
        },
        'io_bottleneck': {
            'symptom': 'CPU/GPU 均未满载，编码速度低',
            'causes': ['磁盘读写慢', '网络 I/O (流媒体)', '文件系统碎片'],
            'solutions': [
                '使用 NVMe SSD',
                '使用 RAM Disk (小文件)',
                '优化文件系统 (ext4/xfs)',
                '分离输入输出到不同磁盘',
            ],
        },
        'memory_bottleneck': {
            'symptom': '内存使用率高，频繁交换',
            'causes': ['大文件处理', '滤镜图过大', '并发过多'],
            'solutions': [
                '减少并发数量',
                '优化滤镜图 (避免大量 split)',
                '增加物理内存',
            ],
        },
        'pcie_bottleneck': {
            'symptom': '硬件加速场景下 GPU 利用率波动',
            'causes': ['频繁 hw↔sw 帧传输', 'PCIe 带宽不足'],
            'solutions': [
                '保持帧在硬件内存中 (避免 hwdownload)',
                '使用全硬件管线',
                '检查 PCIe 通道数 (x16 vs x8)',
            ],
        },
    }
```

### 8.4 兼容性问题

```python
class CompatibilityIssues:
    """兼容性故障排查"""

    ISSUES = {
        'quicktime_playback': {
            'symptom': 'QuickTime Player 无法播放 NVENC 编码的文件',
            'cause': 'QuickTime 对 H.264 profile/level 限制严格',
            'solution': '使用 -profile:v high -level 4.1 -pix_fmt yuv420p',
        },
        'browser_playback': {
            'symptom': '浏览器无法播放 HEVC/AV1',
            'cause': '浏览器编解码器支持差异',
            'solution': {
                'chrome': 'HEVC 需要硬件解码支持, AV1 默认支持',
                'firefox': 'HEVC 不支持 (Windows 可通过组件), AV1 支持',
                'safari': 'HEVC 支持, AV1 需 macOS 13+',
            },
            'fallback': '同时输出 H.264 + HEVC/AV1',
        },
        'mobile_playback': {
            'symptom': '移动设备播放卡顿/不兼容',
            'cause': '移动设备硬件解码能力有限',
            'solution': {
                'android': 'H.264 Baseline/Main, HEVC Main',
                'ios': 'H.264 High, HEVC Main10, AV1 (iOS 16+)',
            },
            'params': '-profile:v baseline -level 3.1 -pix_fmt yuv420p -maxrate 2M -bufsize 4M',
        },
        'hdr_playback': {
            'symptom': 'HDR 视频在 SDR 显示器上颜色异常',
            'cause': '缺少色调映射',
            'solution': '添加 tonemap 滤镜: -vf tonemap=tonemap=hable:desat=0',
            'command': 'ffmpeg -i hdr_input.mp4 -vf "zscale=t=709:m=709:p=709:r=tv,tonemap=tonemap=hable:desat=0,zscale=t=709:m=709:p=709:r=tv,format=yuv420p" -c:v h264_nvenc sdr_output.mp4',
        },
        'broadcast_compat': {
            'symptom': '广播系统拒绝编码文件',
            'cause': '广播标准要求 (B-frame, GOP, Level)',
            'solution': {
                'params': '-bf 2 -g 60 -refs 4 -level 4.1 -profile:v high',
                'color': '-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709',
                'audio': '-c:a aac -b:a 192k -ar 48000 -ac 2',
            },
        },
    }
```

---

## 附录

### 附录 A: 硬件加速命令速查表

```bash
# === CUDA/NVENC ===
# 硬件解码 + 硬件编码 (零拷贝)
ffmpeg -hwaccel cuda -hwaccel_output_format cuda -c:v h264_cuvid -i input.mp4 -c:v h264_nvenc -preset p5 -b:v 8M output.mp4

# 硬件解码 + GPU缩放 + 硬件编码
ffmpeg -hwaccel cuda -hwaccel_output_format cuda -i input.mp4 -vf scale_cuda=1280:720 -c:v h264_nvenc -preset p5 output.mp4

# HEVC 10bit HDR
ffmpeg -hwaccel cuda -i input.mov -c:v hevc_nvenc -preset p7 -profile:v main10 -pix_fmt p010le -b:v 20M -spatial_aq 1 -temporal_aq 1 output.mp4

# AV1 (RTX 40)
ffmpeg -hwaccel cuda -i input.mp4 -c:v av1_nvenc -preset p7 -b:v 6M -tile_cols 2 -tile_rows 1 output_av1.mp4

# === QSV ===
ffmpeg -hwaccel qsv -c:v h264_qsv -i input.mp4 -c:v h264_qsv -preset slow -rc icq -global_quality 25 output.mp4

# QSV VPP (去隔行+降噪+缩放)
ffmpeg -hwaccel qsv -i input.ts -vf "vpp_qsv=deinterlace=bob,denoise=50,w=1920:h=1080" -c:v h264_qsv output.mp4

# === AMF ===
ffmpeg -hwaccel d3d11va -i input.mp4 -c:v h264_amf -usage lowlatency -rc cbr -b:v 6M output.mp4

# === VideoToolbox (macOS) ===
ffmpeg -hwaccel videotoolbox -i input.mp4 -c:v h264_videotoolbox -b:v 8M output.mp4

# === VAAPI (Linux) ===
ffmpeg -hwaccel vaapi -hwaccel_output_format vaapi -i input.mp4 -vf scale_vaapi=1280:720 -c:v h264_vaapi -b:v 6M output.mp4

# === Vulkan ===
ffmpeg -init_hw_device vulkan=vk:0 -filter_hw_device vk -i input.mp4 -vf scale_vulkan=1920:1080 -c:v h264_vulkan output.mp4

# === 两遍编码 (NVENC) ===
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc -preset p5 -pass 1 -b:v 8M -an -f mp4 /dev/null
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc -preset p5 -pass 2 -b:v 8M -c:a aac output.mp4

# === 质量评估 (VMAF) ===
ffmpeg -i reference.mp4 -i distorted.mp4 -lavfi libvmaf="model=version=vmaf_v0.6.1" -f null -

# === 硬件解码性能测试 ===
ffmpeg -hwaccel cuda -c:v h264_cuvid -i input.mp4 -f null - -benchmark
```

### 附录 B: 编码器参数对比表

| 参数 | libx264 | h264_nvenc | h264_qsv | h264_amf | h264_videotoolbox |
|------|---------|------------|----------|----------|-------------------|
| 预设系统 | ultrafast-veryslow | p1-p7 | veryfast-slower | speed/balanced/quality | 无 |
| 速率控制 | CBR/VBR/CQP/2pass | CBR/VBR/CQ/2pass | CBR/VBR/ICQ/QVBR | CBR/VBR/CQP | CBR/VBR |
| 最大B帧 | 16 | 4 | 7 | 3 | 2 |
| 最大参考帧 | 16 | 16 | 16 | 16 | 4 |
| 空间AQ | yes | yes (p4+) | yes | yes (PAQ) | no |
| 时间AQ | yes | yes (p4+) | yes | yes | no |
| LookAhead | yes | yes (0-32) | yes (0-100) | yes (PreAnalysis) | no |
| 10bit | yes | yes | yes | yes | yes |
| 4:4:4 | yes | yes | yes | no | yes |
| 无损编码 | yes | yes | yes | no | no |
| ROI编码 | no | yes | yes | yes | no |
| 会话限制 | 无 | 3-8 | 无 | 无 | 无 |
| 跨平台 | 全平台 | NVIDIA | Intel | AMD | Apple |

### 附录 C: 性能基准测试数据

| 编码器 | 1080p60 fps | 4K30 fps | VMAF@6M | 功耗(W) | CPU(%) |
|--------|-------------|----------|---------|---------|--------|
| libx264 medium | 90 | 22 | 88.5 | 95(CPU) | 90 |
| libx264 slow | 35 | 8 | 91.2 | 95 | 95 |
| libx265 slow | 18 | 4 | 94.0 | 99 | 98 |
| libsvtav1 p6 | 35 | 8 | 93.5 | 95 | 95 |
| h264_nvenc p4 | 780 | 175 | 87.3 | 65 | 5 |
| h264_nvenc p7 | 560 | 120 | 90.1 | 70 | 6 |
| hevc_nvenc p7 | 510 | 100 | 92.5 | 75 | 6 |
| av1_nvenc p7 | 280 | 75 | 93.0 | 80 | 6 |
| h264_qsv slow | 240 | 55 | 89.5 | 35 | 12 |
| hevc_qsv slow | 220 | 50 | 91.8 | 40 | 12 |
| h264_amf quality | 250 | 58 | 88.5 | 75 | 12 |

### 附录 D: GPU 兼容性列表

| GPU | H.264 编码 | HEVC 编码 | AV1 编码 | HEVC 10bit | NVDEC | 最大并发 |
|------|-----------|-----------|---------|-----------|-------|---------|
| GTX 1080 Ti | yes | yes | no | yes | yes | 5 |
| RTX 2080 Ti | yes | yes | no | yes | yes | 5 |
| RTX 3060 | yes | yes | no | yes | yes | 5 |
| RTX 3080 | yes | yes | no | yes | yes | 5 |
| RTX 4060 | yes | yes | yes | yes | yes | 5 |
| RTX 4080 | yes | yes | yes | yes | yes | 8 |
| RTX 4090 | yes | yes | yes | yes | yes | 8 |
| Quadro T4 | yes | yes | no | yes | yes | 0(无限) |
| RTX A6000 | yes | yes | no | yes | yes | 0(无限) |

| Intel GPU | H.264 | HEVC | AV1 | VPP | 最大并发 |
|-----------|-------|------|-----|-----|---------|
| UHD 630 (8代) | yes | yes | no | yes | 无限 |
| Iris Xe (11代) | yes | yes | decode only | yes | 无限 |
| Arc A380 | yes | yes | yes | yes | 无限 |
| Arc A750 | yes | yes | yes | yes | 无限 |
| Arc A770 | yes | yes | yes | yes | 无限 |

| AMD GPU | H.264 | HEVC | AV1 | 最大并发 |
|---------|-------|------|-----|---------|
| RX 580 | yes | no | no | 无限 |
| RX 5700 XT | yes | yes | no | 无限 |
| RX 6700 XT | yes | yes | decode only | 无限 |
| RX 6800 XT | yes | yes | decode only | 无限 |
| RX 7900 XTX | yes | yes | yes | 无限 |

---

> **版本**: 2026.07 | **标准**: 实验研究原子级别 | **适用**: FFmpeg 6.0+ / 7.0+
> **更新日志**: 2026.07 初版，覆盖 CUDA/QSV/AMF/VideoToolbox/Vulkan 全硬件平台
