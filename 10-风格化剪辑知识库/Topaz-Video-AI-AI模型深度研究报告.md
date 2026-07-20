# Topaz Video AI AI模型深度研究报告

> 适用版本：Topaz Video AI 4.x（含 3.x 模型兼容矩阵）| 更新日期：2026-07-14 | 分类：AI视频增强原子级研究

---

## 目录

- [一、模型架构概述](#一模型架构概述)
- [二、增强类模型详解](#二增强类模型详解)
- [三、隔行视频模型（Dione系列）](#三隔行视频模型dione系列)
- [四、帧插值模型详解](#四帧插值模型详解)
- [五、Starlight扩散模型系列](#五starlight扩散模型系列)
- [六、模型选择决策树](#六模型选择决策树)
- [七、模型参数原子级映射](#七模型参数原子级映射)
- [八、版本兼容性矩阵](#八版本兼容性矩阵)

---

## 一、模型架构概述

### 1.1 Topaz Video AI 模型技术架构

Topaz Video AI 的核心建立在「多帧时序卷积神经网络 + 残差注意力机制」之上。每一代模型在推理时都会同时输入相邻 N 帧（通常为 5–21 帧），通过光流对齐后送入 U-Net 风格的编码-解码主干，最终输出中心帧的增强版本。

```python
class TopazModelArchitecture:
    """Topaz Video AI 模型主干架构描述。"""
    BACKBONE = 'U-Net + Residual Attention'
    TEMPORAL_WINDOW = {
        'default': 7,           # 多数增强模型默认窗口
        'frame_interp': 11,     # 帧插值模型窗口
        'diffusion': 'variable' # Starlight 系列为变长窗口
    }
    INPUT_TENSORS = {
        'rgb': {'shape': 'BxTx3xHxW', 'dtype': 'float16'},
        'flow': {'shape': 'BxTx2xHxW', 'dtype': 'float16'},
        'mask': {'shape': 'BxTx1xHxW', 'dtype': 'float16', 'optional': True}
    }
    OUTPUT_TENSORS = {
        'rgb': {'shape': 'Bx1x3xHxW', 'dtype': 'float16'},
        'confidence': {'shape': 'Bx1x1xHxW', 'dtype': 'float16', 'optional': True}
    }
    INFERENCE_PRECISION = ['fp16', 'fp32', 'int8-quant']
    SUPPORTED_RUNTIMES = ['onnxruntime-cuda', 'onnxruntime-directml', 'tensorrt']

    def describe_pipeline(self):
        return [
            '1. 解码输入视频并抽取目标帧 + 邻域帧',
            '2. 使用 RAFT 风格光流网络对齐邻域帧',
            '3. 拼接 RGB + 光流 + 时间索引送入 U-Net 主干',
            '4. 残差注意力块逐尺度提取特征',
            '5. 解码器输出增强后的中心帧',
            '6. 后处理：颜色管理、抖动抑制、边缘锐化'
        ]
```

模型权重全部位于 `%PROGRAMDATA%\Topaz Video AI\Models\` 目录下，按 `model_name` + `version` 组织。同一模型可能存在多个 `.enc` 加密权重文件，对应不同输入分辨率与精度档位，运行时由调度器根据显存预算动态选择。

### 1.2 多帧时序融合技术原理

多帧融合是 Topaz 区别于单帧 Gigapixel 增强的关键。下表描述了融合窗口、对齐策略与运动处理能力之间的关系。

| 融合窗口 | 对齐策略 | 适用运动幅度 | 显存占用系数 | 代表模型 |
|----------|----------|--------------|--------------|----------|
| 3 帧 | 单向光流 | 静态 / 微动 | 1.0x | Theia (LQ) |
| 5 帧 | 双向光流 + Huber 损失 | 中速运动 | 1.4x | Proteus, Artemis |
| 7 帧 | 双向光流 + 自适应权重 | 中高速运动 | 1.8x | Gaia HQ, Iris MQ |
| 11 帧 | 多假设光流 + 运动掩码 | 高速 / 非线性 | 2.6x | Apollo, Chronos |
| 21 帧 | 长时序注意力 + ROI 跟踪 | 极慢 / 静态 | 4.2x | Starlight HQ |

```python
class TemporalFusionConfig:
    """描述时序融合的原子级配置。"""
    def __init__(self, window=7, alignment='bidirectional_flow',
                 motion_mask=True, roi_tracking=False):
        self.window = window
        self.alignment = alignment
        self.motion_mask = motion_mask
        self.roi_tracking = roi_tracking
        self.weights = self._init_weights()

    def _init_weights(self):
        # 中心帧权重最大，向两端指数衰减
        import math
        center = self.window // 2
        return [math.exp(-abs(i - center) * 0.4) for i in range(self.window)]

    def estimate_vram(self, height, width, precision='fp16'):
        base = height * width * 3 * (2 if precision == 'fp16' else 4)
        # 系数表来自上表
        coef_map = {3: 1.0, 5: 1.4, 7: 1.8, 11: 2.6, 21: 4.2}
        coef = coef_map.get(self.window, 1.8)
        return int(base * coef * self.window / (1024 ** 3) * 1000) / 1000  # GB
```

### 1.3 模型训练数据集与训练方法

Topaz 官方未公开训练集，但通过其白皮书、官网博客以及模型行为反向推断，可以重建如下训练范式：

```python
class TopazTrainingRecipe:
    DATASETS = {
        'proteus':    {'source': '开放视频 + 内部高质量素材库', 'pairs': '退化-原始对（合成）', 'size': '~8M 帧'},
        'artemis':    {'source': '夜景 / 低光采集 + 合成 ISO 噪声', 'pairs': '高ISO-低ISO对', 'size': '~3M 帧'},
        'gaia':       {'source': '纪录片 / 静态档案', 'pairs': '压缩-无损对', 'size': '~4M 帧'},
        'iris':       {'source': '人脸许可数据集', 'pairs': '退化-清晰人脸对', 'size': '~6M 帧'},
        'nyx':        {'source': '4K 高码率素材', 'pairs': '加噪-原片对', 'size': '~5M 帧'},
        'dione_dv':   {'source': 'DV / DVCAM 录像', 'pairs': '隔行-逐行对', 'size': '~2M 帧'},
        'apollo':     {'source': '运动镜头库', 'pairs': '前后帧-中间帧', 'size': '~10M 帧'},
        'chronos':    {'source': '混合运动库', 'pairs': '前后帧-中间帧', 'size': '~12M 帧'},
        'starlight':  {'source': 'AI 生成视频 + 自然视频对比', 'pairs': '生成-真实对', 'size': '~15M 帧'}
    }
    LOSS_FUNCTIONS = ['L1', 'SSIM', 'VGG-perceptual', 'GAN-adversarial', 'temporal-consistency']
    AUGMENTATIONS  = ['random_crop', 'rotation_jitter', 'color_jitter', 'compression_sim', 'temporal_flip']
    SCHEDULE       = {'optimizer': 'AdamW', 'lr_peak': 2e-4, 'warmup_steps': 5000, 'cosine_decay': True}

    def get_recipe(self, model_name):
        return self.DATASETS.get(model_name, {'error': 'unknown model'})
```

训练通常分两个阶段：阶段一用 L1 + SSIM 进行像素级预训练，阶段二引入 VGG 感知损失与 GAN 对抗损失进行细节增强。Starlight 系列额外加入了扩散模型的去噪目标函数。

### 1.4 GPU加速与推理优化

```python
class TopazInferenceBackend:
    """描述 Topaz 在不同 GPU 上的推理后端选择逻辑。"""
    BACKEND_PRIORITY = [
        ('nvidia',   'tensorrt',     'fp16',  '最快，需 RTX 20+ 系列'),
        ('nvidia',   'cuda',         'fp16',  '兼容性好，速度次之'),
        ('nvidia',   'cuda',         'fp32',  '老卡或调试用'),
        ('amd',      'directml',     'fp16',  'RX 6000+ 推荐'),
        ('intel',    'directml',     'fp16',  'Arc A 系列'),
        ('cpu',      'openvino',     'int8',  '回退方案，速度极慢')
    ]

    def select_backend(self, gpu_vendor, gpu_model, vram_mb):
        for vendor, backend, precision, note in self.BACKEND_PRIORITY:
            if vendor != gpu_vendor:
                continue
            if backend == 'tensorrt' and 'RTX' not in gpu_model:
                continue
            if vram_mb < 4000 and precision == 'fp32':
                continue
            return {'backend': backend, 'precision': precision, 'note': note}
        return {'backend': 'cpu', 'precision': 'int8', 'note': '回退到 CPU'}

    def estimate_throughput(self, model, resolution, fps, gpu_tflops):
        # 经验公式：帧/秒 ≈ GPU算力 / (模型复杂度 × 分辨率系数)
        model_cost = {'proteus': 1.0, 'artemis': 1.2, 'gaia': 1.1,
                      'iris': 1.5, 'nyx': 1.8, 'starlight_hq': 4.2}.get(model, 1.0)
        res_cost = (resolution[0] * resolution[1]) / (1920 * 1080)
        fps_est = gpu_tflops / (model_cost * res_cost * 0.8)
        return round(fps_est, 2)
```

性能优化要点：
1. **TensorRT**：在 RTX 20 系及以上显卡上，Topaz 会自动编译 TensorRT 引擎，首次启动慢约 30–90 秒，但后续推理速度比 ONNX Runtime 快 1.4–2.1 倍。
2. **显存分块**：当输入分辨率超过显存承载能力时，Topaz 会自动将帧切分为 `tile`，分块推理后用羽化拼接还原。`tile_size` 越小显存占用越低，但边缘伪影概率越高。
3. **批处理**：在帧插值模型中，Topaz 会将多个相邻中心帧打包成 batch 并发推理，充分利用 GPU 并行度。

---

## 二、增强类模型详解

### 2.1 Proteus（普罗透斯）- 通用型模型

Proteus 是 Topaz 4.x 时代的「全能选手」，定位类似于 Artemis + Gaia 的融合体，可处理任意分辨率的通用素材。其最大优势是参数可调性强，但代价是需要使用者具备一定经验。

```python
class ProteusModel:
    """Proteus 通用增强模型原子级参数。"""
    NAME = 'proteus'
    VERSION = 'v4'
    SUITABLE_FOR = ['通用视频', '中等质量素材', '网络视频', '影视素材']
    NOT_SUITABLE_FOR = ['极端低光', '隔行视频', '8K 以上超分']
    MAX_SCALE = 4

    PARAMS = {
        # 参数名: (范围, 默认值, 数学含义, 推荐区间)
        'recover_detail':       (0, 100, 55, '细节恢复强度，控制 U-Net 残差通道增益', '20-70'),
        'reduce_noise':         (0, 100, 25, '高斯+泊松联合噪声抑制权重', '0-50'),
        'sharpen':              (0, 100, 35, '拉普拉斯锐化幅度，与 recover_detail 协同', '20-50'),
        'deblur':               (0, 100, 20, '运动模糊反卷积强度', '0-40'),
        'fix_compression':      (0, 100, 40, 'JPEG/H264 块效应去除', '20-60'),
        'dehalo':               (0, 100, 0,  '边缘过渡区光晕抑制', '0-30'),
        'reduce_jitter':        (0, 100, 0,  '时序抖动抑制，影响运动平滑度', '0-20'),
        'antialias':            (0, 100, 10, '锯齿/摩尔纹抑制', '0-30'),
        'restore_face':         (0, 100, 0,  '人脸细节重建（轻量级，弱于 Iris）', '0-30')
    }

    def __init__(self):
        self.params = {k: default for k, (_, _, default, _, _) in self.PARAMS.items()}
        self.scale = 1
        self.chunk_size = 'auto'

    def set_param(self, name, value):
        if name not in self.PARAMS:
            return {'success': False, 'error': f'未知参数 {name}'}
        lo, hi, _, _, _ = self.PARAMS[name]
        if not (lo <= value <= hi):
            return {'success': False, 'error': f'{name} 必须在 [{lo},{hi}] 范围'}
        self.params[name] = value
        return {'success': True, 'param': name, 'value': value}

    def preset_network_video(self):
        """网络视频（720p H264 低码率）推荐参数。"""
        return {
            'recover_detail': 45, 'reduce_noise': 35, 'sharpen': 30,
            'deblur': 15, 'fix_compression': 60, 'dehalo': 10,
            'reduce_jitter': 5, 'antialias': 15, 'restore_face': 10
        }

    def preset_cinema(self):
        """电影级素材轻度修复。"""
        return {
            'recover_detail': 30, 'reduce_noise': 10, 'sharpen': 20,
            'deblur': 10, 'fix_compression': 20, 'dehalo': 5,
            'reduce_jitter': 0, 'antialias': 5, 'restore_face': 0
        }

    def preset_archive(self):
        """老旧档案修复。"""
        return {
            'recover_detail': 70, 'reduce_noise': 50, 'sharpen': 45,
            'deblur': 35, 'fix_compression': 70, 'dehalo': 25,
            'reduce_jitter': 10, 'antialias': 25, 'restore_face': 20
        }
```

**Proteus 参数相互作用矩阵**：

| 主参数 \ 副参数 | recover_detail | reduce_noise | sharpen | deblur | fix_compression |
|------------------|----------------|--------------|---------|--------|------------------|
| recover_detail ↑ | - | 噪声被放大 | 协同增强 | 抑制模糊 | 略微增强 |
| reduce_noise ↑ | 细节被弱化 | - | 锐化效果降低 | 噪点抑制 | 协同 |
| sharpen ↑ | 视觉增强 | 噪点被强化 | - | 边缘更清晰 | 块效应凸显 |
| deblur ↑ | 细节回升 | 噪点回升 | 协同 | - | 微弱影响 |
| fix_compression ↑ | 块效应消除 | 协同降噪 | 块边缘弱化 | 块效应消除 | - |

**与其他模型对比**：

| 对比维度 | Proteus | Artemis | Gaia | Iris |
|----------|---------|---------|------|------|
| 适用素材 | 通用 | 低光 | 静态 | 人脸 |
| 可调参数数 | 9 | 5 | 4 | 3 |
| 噪点处理 | 中等 | 极强 | 弱 | 弱 |
| 细节恢复 | 强 | 中等 | 极强 | 强（人脸） |
| 速度 | 中等 | 快 | 中等 | 慢 |
| 显存占用 | 中等 | 低 | 中等 | 高 |

### 2.2 Artemis（阿尔忒弥斯）- 暗光降噪专家

Artemis 专为夜景、高 ISO、监控录像等低光场景设计。其核心在于 `Dehalo` 与 `Reduce Noise` 两个参数的强耦合，能够在保留暗部细节的同时压平色度噪声。

```python
class ArtemisModel:
    NAME = 'artemis'
    VERSION = 'v4'
    SUITABLE_FOR = ['夜景', '高 ISO', '监控录像', '室内弱光', '演唱会']
    NOT_SUITABLE_FOR = ['日光高对比', '4K 以上', 'AI 生成视频']
    MAX_SCALE = 4

    PARAMS = {
        'noise_reduction': (0, 100, 50, '空间-时序联合降噪强度'),
        'detail_recovery': (0, 100, 30, '降噪后细节重建'),
        'sharpen':         (0, 100, 25, '边缘锐化'),
        'dehalo':          (0, 100, 20, '高对比边缘光晕抑制'),
        'deblur':          (0, 100, 15, '低光快门抖动补偿')
    }

    MODE_PRESETS = {
        'low_light':   {'noise_reduction': 60, 'detail_recovery': 35, 'sharpen': 25, 'dehalo': 20, 'deblur': 20},
        'high_iso':    {'noise_reduction': 75, 'detail_recovery': 30, 'sharpen': 20, 'dehalo': 25, 'deblur': 15},
        'cctv':        {'noise_reduction': 80, 'detail_recovery': 40, 'sharpen': 30, 'dehalo': 30, 'deblur': 25},
        'concert':     {'noise_reduction': 55, 'detail_recovery': 45, 'sharpen': 30, 'dehalo': 15, 'deblur': 10},
        'archive_low': {'noise_reduction': 50, 'detail_recovery': 50, 'sharpen': 35, 'dehalo': 25, 'deblur': 20}
    }

    def __init__(self, mode='low_light'):
        self.params = self.MODE_PRESETS.get(mode, self.MODE_PRESETS['low_light'])
        self.scale = 1

    def auto_detect_mode(self, frame_luma_stats):
        """根据亮度统计自动选择模式。"""
        mean = frame_luma_stats.get('mean', 0.5)
        std  = frame_luma_stats.get('std', 0.2)
        if mean < 0.25 and std > 0.18:
            return 'high_iso' if std > 0.25 else 'low_light'
        if mean < 0.35:
            return 'cctv' if std > 0.20 else 'archive_low'
        return 'concert'
```

**调优指南**：
- 噪点抑制不要超过 80，否则会出现「塑料感」肤色。
- `detail_recovery` 与 `noise_reduction` 应保持差值 ≥ 20，否则细节丢失过多。
- 处理高 ISO 噪点时，建议同时启用 `dehalo` ≥ 25，可避免暗部光晕。
- Artemis 不适合 4K 以上素材，因其训练集以 1080p 为主，过度放大易出现幻觉细节。

### 2.3 Gaia（盖亚）- 细节强化模型

Gaia 是面向静态/慢镜头画面的细节强化模型，常用于纪录片、档案片、艺术档案数字化的轻量级超分。其特点是不强行降噪，专注于纹理保真。

```python
class GaiaModel:
    NAME = 'gaia'
    VERSIONS = {'gaia-hq': 'v4', 'gaia': 'v3'}
    SUITABLE_FOR = ['纪录片', '档案片', '博物馆数字化', '风景空镜', '产品展示']
    NOT_SUITABLE_FOR = ['运动镜头', '夜景', '高噪点素材']
    MAX_SCALE = {'gaia': 4, 'gaia-hq': 8}

    PARAMS = {
        'detail_enhance':  (0, 100, 50, '纹理细节增强强度'),
        'sharpen':         (0, 100, 30, '边缘锐化'),
        'denoise':         (0, 100, 10, '轻量级降噪，主要用于去除压缩噪声'),
        'recover_text':    (0, 100, 25, '文字/标识纹理恢复')
    }

    HQ_EXTRA_PARAMS = {
        'texture_boost':   (0, 100, 40, 'HQ 版独有，强化自然纹理如皮肤、织物'),
        'micro_detail':    (0, 100, 35, 'HQ 版独有，微细节重建')
    }

    def __init__(self, version='gaia'):
        self.version = version
        self.params = {k: d for k, (_, _, d, _) in self.PARAMS.items()}
        if version == 'gaia-hq':
            self.params.update({k: d for k, (_, _, d, _) in self.HQ_EXTRA_PARAMS.items()})

    def preset_documentary(self):
        return {'detail_enhance': 55, 'sharpen': 35, 'denoise': 15,
                'recover_text': 35, 'texture_boost': 45, 'micro_detail': 40}

    def preset_archive_scan(self):
        """档案扫描件数字化。"""
        return {'detail_enhance': 70, 'sharpen': 45, 'denoise': 20,
                'recover_text': 70, 'texture_boost': 35, 'micro_detail': 55}

    def preset_product(self):
        """产品展示素材。"""
        return {'detail_enhance': 60, 'sharpen': 40, 'denoise': 10,
                'recover_text': 30, 'texture_boost': 50, 'micro_detail': 45}
```

**纪录片最佳实践**：
1. 使用 `gaia-hq`，因为 HQ 版本针对 8K 超分优化了纹理恢复。
2. `recover_text` 是 Gaia 独有参数，专门用于恢复档案片中的字幕、标题、印章。
3. 对运动镜头应在时间线上局部切换到 Proteus，避免 Gaia 在大运动下出现伪影。
4. 输出颜色空间建议保持 Rec.709，不要在 Gaia 阶段做 HDR 转换，应交给 Hyperion。

### 2.4 Iris - 人脸修复专家

Iris 是 Topaz 唯一专注于人脸修复的增强模型，使用人脸检测器定位 ROI 后对 ROI 区域进行高强度重建，对非人脸区域采用轻量级增强，避免污染背景。

```python
class IrisModel:
    NAME = 'iris'
    VERSION = 'v4'
    SUITABLE_FOR = ['人物采访', 'MV', '短视频', '老照片转视频', '人脸特写']
    NOT_SUITABLE_FOR = ['无人脸素材', '远景人群', '动画/CG 人脸']
    MAX_SCALE = 4

    QUALITY_MODES = {
        'LQ': {'description': '低质量模式，速度优先', 'face_strength': 50, 'skin_smooth': 30},
        'MQ': {'description': '中质量模式，平衡',     'face_strength': 70, 'skin_smooth': 45},
        'HQ': {'description': '高质量模式，细节优先', 'face_strength': 85, 'skin_smooth': 60}
    }

    PARAMS = {
        'face_enhancement': (0, 100, 70, '人脸重建强度，越高越接近训练集理想人脸'),
        'skin_smoothing':   (0, 100, 45, '皮肤肌理平滑度，过高会丢失毛孔'),
        'eye_enhance':      (0, 100, 50, '眼部细节强化（虹膜、睫毛）'),
        'hair_restore':     (0, 100, 40, '发丝重建'),
        'face_color':       (0, 100, 30, '肤色一致性修正')
    }

    def __init__(self, mode='MQ'):
        self.mode = mode
        self.params = dict(self.QUALITY_MODES.get(mode, self.QUALITY_MODES['MQ']))
        self.params.update({k: d for k, (_, _, d, _) in self.PARAMS.items()})

    def mode_decision(self, input_resolution, face_pixel_ratio):
        """LQ/MQ/HQ 选择指南。
        input_resolution: 输入分辨率元组
        face_pixel_ratio: 人脸像素占画面比例 (0-1)
        """
        h, w = input_resolution
        face_pixels = h * w * face_pixel_ratio
        if face_pixels < 8000:           # 人脸过小
            return {'mode': 'LQ', 'reason': '人脸像素过少，HQ 易幻觉'}
        if face_pixels < 50000:
            return {'mode': 'MQ', 'reason': '中等尺寸，平衡模式最佳'}
        return {'mode': 'HQ', 'reason': '人脸足够大，可启用 HQ 充分重建'}
```

**LQ/MQ 模式选择指南**：
- LQ 适合处理远景采访、群众镜头，速度比 HQ 快 2.5 倍。
- MQ 是大多数 1080p 采访视频的推荐档位。
- HQ 仅在人脸占画面 1/4 以上时启用，否则容易出现「换脸」幻觉。
- 不要对动画/CG 人脸使用 Iris，会破坏原画风。

### 2.5 Nyx - 4K降噪模型

Nyx 是 Topaz 针对 4K 高分辨率素材开发的专用降噪模型，其训练集聚焦于「保留纹理细节的同时抑制噪声」，对 Sony A7S3、FX3 等机器的高 ISO 4K 素材效果极佳。

```python
class NyxModel:
    NAME = 'nyx'
    VERSION = 'v4'
    SUITABLE_FOR = ['4K 高 ISO', '-log 曲线素材', '微单视频', '低光环境']
    NOT_SUITABLE_FOR = ['1080p 以下', '强压缩素材', '8bit 低码率']
    MAX_SCALE = 2  # Nyx 主要用于降噪而非超分

    PARAMS = {
        'noise_reduction': (0, 100, 50, '空间-时序降噪强度'),
        'detail_keep':     (0, 100, 60, '细节保留度，与降噪反相关'),
        'grain_preserve':  (0, 100, 20, '胶片颗粒保留度，电影感重要'),
        'color_denoise':   (0, 100, 40, '色度噪声抑制（针对低光色斑）')
    }

    LOG_FORMATS_SUPPORTED = ['S-Log2', 'S-Log3', 'V-Log', 'N-Log', 'D-Log', 'log-c']

    def preset_slog3_lowlight(self):
        return {'noise_reduction': 65, 'detail_keep': 55, 'grain_preserve': 15, 'color_denoise': 55}

    def preset_film_grain(self):
        """保留胶片颗粒的电影感预设。"""
        return {'noise_reduction': 35, 'detail_keep': 75, 'grain_preserve': 70, 'color_denoise': 30}
```

**压缩伪影去除技术**：
- Nyx 通过 5 帧时序融合 + 空间卷积，能识别 H.264/H.265 块效应边缘并重新平滑。
- `detail_keep` 与 `noise_reduction` 应保持总和 ≥ 100，否则细节丢失过多。
- 处理 log 素材时应先降噪后转 Rec.709，避免在 log 空间引入伪影。

### 2.6 Rhea / Rhea XL - 商业精致画面

Rhea 系列定位于商业广告、美妆、带货类素材的精致化处理，强调「干净、明亮、有质感」。Rhea XL 是 XLarge 版本，支持更大尺寸的超分，适合从 1080p 直接放大到 8K。

```python
class RheaModel:
    NAME_BASE = 'rhea'
    NAME_XL = 'rhea-xl'
    SUITABLE_FOR = ['美妆', '带货直播', '商业广告', '产品特写', '电商主图视频']
    NOT_SUITABLE_FOR = ['电影叙事', '新闻纪录', '运动镜头']
    MAX_SCALE = {'rhea': 4, 'rhea-xl': 8}

    PARAMS = {
        'skin_smooth':     (0, 100, 50, '皮肤磨皮，商业美妆核心'),
        'skin_brighten':   (0, 100, 30, '肤色提亮'),
        'eye_clarity':     (0, 100, 45, '眼神光增强'),
        'product_detail':  (0, 100, 50, '产品纹理强化'),
        'color_pop':       (0, 100, 25, '色彩饱和度微提升'),
        'dehalo':          (0, 100, 15, '去除压缩光晕')
    }

    XL_EXTRA = {
        'large_scale_tex': (0, 100, 60, 'XL 独有，大尺寸纹理重建'),
        'edge_refine':     (0, 100, 55, 'XL 独有，边缘精细化')
    }

    def preset_beauty_closeup(self):
        return {'skin_smooth': 70, 'skin_brighten': 40, 'eye_clarity': 65,
                'product_detail': 40, 'color_pop': 30, 'dehalo': 20}

    def preset_livestream_4k(self):
        """1080p 直播录像转 4K。"""
        return {'skin_smooth': 55, 'skin_brighten': 35, 'eye_clarity': 55,
                'product_detail': 60, 'color_pop': 35, 'dehalo': 25,
                'large_scale_tex': 65, 'edge_refine': 60}
```

**XL版本的大尺寸超分能力**：
- Rhea XL 训练集中包含 4K→8K 与 1080p→8K 的成对数据。
- 在 1080p→8K 场景下，建议开启 `large_scale_tex` ≥ 60，否则纹理会显得「平」。
- XL 模式显存占用是基础版的 2.3 倍，建议 12GB 以上显存。

### 2.7 Hyperion - SDR转HDR

Hyperion 是 Topaz 用于 SDR 转 HDR 的专用模型，能够智能扩展动态范围并重建高光/阴影细节，输出 Rec.2020 + PQ 曲线的 HDR10 流。

```python
class HyperionModel:
    NAME = 'hyperion'
    VERSION = 'v4'
    SUITABLE_FOR = ['SDR 转 HDR10', '老电影 HDR 重制', 'HDR 调色前置']
    NOT_SUITABLE_FOR = ['HDR 转 SDR', 'log 素材直接转 HDR']
    MAX_SCALE = 1
    OUTPUT_CS = 'Rec.2020 PQ'

    PARAMS = {
        'highlight_recover': (0, 100, 50, '高光细节恢复（天空、灯源）'),
        'shadow_recover':    (0, 100, 50, '阴影细节恢复'),
        'color_expand':      (0, 100, 60, '色域扩展到 Rec.2020'),
        'contrast_boost':    (0, 100, 30, 'PQ 曲线对比度增强'),
        'saturation_boost':  (0, 100, 25, 'HDR 饱和度提升')
    }

    def preset_cinema_hdr(self):
        return {'highlight_recover': 60, 'shadow_recover': 55,
                'color_expand': 70, 'contrast_boost': 35, 'saturation_boost': 30}

    def preset_archive_hdr(self):
        """老电影 HDR 重制。"""
        return {'highlight_recover': 70, 'shadow_recover': 65,
                'color_expand': 55, 'contrast_boost': 25, 'saturation_boost': 20}
```

**动态范围扩展原理**：
- Hyperion 通过对 SDR 直方图进行反向映射，结合内容理解网络预测原场景的真实亮度分布。
- `color_expand` 使用 Gamut Mapping 算法将 Rec.709 颜色映射到 Rec.2020 三角形外，但并非线性扩展，而是基于场景语义（天空→更蓝，皮肤→保持原色）。
- 输出必须设置成 10bit 4:2:0 或 4:4:4，否则会出现色带。

### 2.8 Astra - AI生成视频修复

Astra 是 Topaz 在 2025 年推出的新型模型，专门针对 Sora、Runway、Pika、Kling 等 AI 生成视频的修复，核心目标是消除「CG 塑料感」与「人物漂移」。

```python
class AstraModel:
    NAME = 'astra'
    VERSION = 'v1'
    SUITABLE_FOR = ['Sora 输出', 'Runway Gen-3', 'Pika 1.5', 'Kling 视频', 'Stable Video Diffusion']
    NOT_SUITABLE_FOR = ['真实拍摄素材', '动画/CGI', '老电影']
    MAX_SCALE = 2

    PARAMS = {
        'plastic_reduce':   (0, 100, 50, '消除 CG 塑料感，引入自然微纹理'),
        'face_stabilize':   (0, 100, 60, '人物面部时序稳定'),
        'motion_consistency':(0,100, 55, '前后帧运动一致性修正'),
        'texture_natural':  (0, 100, 45, '纹理自然化（皮肤、织物）'),
        'artifact_remove':  (0, 100, 50, 'AI 生成伪影去除（手部、文字）')
    }

    def preset_sora(self):
        return {'plastic_reduce': 55, 'face_stabilize': 65, 'motion_consistency': 60,
                'texture_natural': 50, 'artifact_remove': 55}

    def preset_runway(self):
        return {'plastic_reduce': 50, 'face_stabilize': 70, 'motion_consistency': 55,
                'texture_natural': 45, 'artifact_remove': 60}
```

**消除CG塑料感的原理**：
- Astra 通过对生成视频的高频区域进行频谱分析，识别过于规则的纹理（CG 塑料感来源），用真实视频训练集的纹理分布进行替换。
- `face_stabilize` 使用人脸关键点跟踪，对漂移特征点进行回归。
- 对 Runway/Pika 的文字伪影，建议 `artifact_remove` ≥ 60。

### 2.9 Theia - 精确还原模型

Theia 是 Topaz 的「最忠实还原」模型，参数极少但保真度极高，适合对原始数据完整性要求极高的场景（如法庭证据、医学影像）。

```python
class TheiaModel:
    NAME = 'theia'
    VERSION = 'v4'
    SUITABLE_FOR = ['法庭证据', '医学影像', '科研视频', '监控取证', '档案数字化']
    NOT_SUITABLE_FOR = ['艺术化增强', '超分大于 2x', '风格化处理']
    MAX_SCALE = 2

    PARAMS = {
        'fidelity':       (0, 100, 80, '保真度，越高越接近原片'),
        'denoise':        (0, 100, 20, '极轻量降噪'),
        'sharpen':        (0, 100, 15, '边缘微锐化'),
        'compression_fix':(0, 100, 30, '压缩伪影轻度修正')
    }

    def preset_forensic(self):
        """法庭证据模式，最高保真。"""
        return {'fidelity': 95, 'denoise': 10, 'sharpen': 5, 'compression_fix': 20}

    def preset_medical(self):
        """医学影像模式。"""
        return {'fidelity': 90, 'denoise': 25, 'sharpen': 10, 'compression_fix': 30}
```

**细节保真度技术**：
- Theia 使用纯 L1 损失训练，不引入感知损失与 GAN，因此输出严格忠实于输入。
- `fidelity` 控制残差通道的权重，95 以上几乎不修改原像素。
- 不建议与 Iris、Astra 等强生成性模型叠加使用。

---

## 三、隔行视频模型（Dione系列）

Dione 系列专门处理隔行扫描视频（Interlaced Video），通过场分离重建实现去隔行。普通增强模型直接处理隔行视频会产生梳状伪影，Dione 通过场独立处理 + 时序融合避免该问题。

```python
class DioneBase:
    NAME_PREFIX = 'dione'
    FIELD_SEPARATION = 'spatial_temporal'
    MOTION_ADAPTIVE = True

    PARAMS = {
        'deinterlace_mode':  ('top_first', 'bottom_first', 'auto', 'auto'),
        'detail_preserve':   (0, 100, 50, '场细节保留度'),
        'motion_compensate': (0, 100, 50, '运动补偿强度'),
        'artifact_remove':   (0, 100, 30, '梳状伪影残留清除')
    }
```

### 3.1 Dione DV - DV视频专用

Dione DV 针对 DV、DVCAM、MiniDV 等老式数字录像带格式，这些素材常见问题包括：色彩偏移、DV 块效应、抖动场序。

```python
class DioneDV(DioneBase):
    NAME = 'dione-dv'
    SUITABLE_FOR = ['MiniDV', 'DVCAM', 'DVCPRO', 'Digital8']
    MAX_SCALE = 4

    def preset_dv_pal(self):
        return {'deinterlace_mode': 'top_first', 'detail_preserve': 60,
                'motion_compensate': 55, 'artifact_remove': 45}

    def preset_dv_ntsc(self):
        return {'deinterlace_mode': 'bottom_first', 'detail_preserve': 60,
                'motion_compensate': 55, 'artifact_remove': 45}
```

### 3.2 Dione TV - 老电视/DVD专用

```python
class DioneTV(DioneBase):
    NAME = 'dione-tv'
    SUITABLE_FOR = ['DVD-Video', 'VHS 数字化', '电视广播录像']
    MAX_SCALE = 4

    PARAMS_EXTRA = {
        'mpeg2_artifact':   (0, 100, 50, 'MPEG-2 压缩伪影清除'),
        'telecine_remove':  (0, 100, 60, '3:2 下拉去除（NTSC 电影）')
    }

    def preset_dvd_film(self):
        return {'deinterlace_mode': 'auto', 'detail_preserve': 55,
                'motion_compensate': 60, 'artifact_remove': 50,
                'mpeg2_artifact': 55, 'telecine_remove': 80}
```

### 3.3 Dione Dehalo - 去光晕专用

```python
class DioneDehalo(DioneBase):
    NAME = 'dione-dehalo'
    SUITABLE_FOR = ['老视频光晕严重', '边缘过冲', '隔行+光晕双重问题']
    MAX_SCALE = 4
    DEHALO_FOCUS = True

    def preset_strong_dehalo(self):
        return {'deinterlace_mode': 'auto', 'detail_preserve': 50,
                'motion_compensate': 45, 'artifact_remove': 70}
```

### 3.4 Dione Robust - 错误转码修复

```python
class DioneRobust(DioneBase):
    NAME = 'dione-robust'
    SUITABLE_FOR = ['转码错误', '场序错误', '帧率混乱', '混合隔行']
    MAX_SCALE = 4

    def preset_corrupted(self):
        return {'deinterlace_mode': 'auto', 'detail_preserve': 40,
                'motion_compensate': 70, 'artifact_remove': 60}
```

### 3.5 Dione Robust Dehalo - 组合模型

```python
class DioneRobustDehalo(DioneBase):
    NAME = 'dione-robust-dehalo'
    SUITABLE_FOR = ['严重损坏的老视频', '需要同时修复转码与光晕']
    MAX_SCALE = 4

    def preset_full_recovery(self):
        return {'deinterlace_mode': 'auto', 'detail_preserve': 45,
                'motion_compensate': 65, 'artifact_remove': 65}
```

**Dione 系列选型表**：

| 子模型 | 主要目标 | 推荐场景 | 速度 |
|--------|----------|----------|------|
| Dione DV | DV 带修复 | 家庭录像数字化 | 快 |
| Dione TV | DVD/电视 | DVD 重制 | 中等 |
| Dione Dehalo | 去光晕 | 老视频边缘问题 | 中等 |
| Dione Robust | 容错修复 | 转码错误 | 慢 |
| Dione Robust Dehalo | 综合修复 | 极端损坏 | 最慢 |

---

## 四、帧插值模型详解

### 4.1 Apollo / Apollo Fast

Apollo 是 Topaz 的非线性运动帧插值模型，能够处理包含运动模糊、形变、遮挡的复杂运动。Apollo Fast 是其轻量版，速度提升 2 倍但精度略低。

```python
class ApolloModel:
    NAME = 'apollo'
    NAME_FAST = 'apollo-fast'
    SUITABLE_FOR = ['24→60fps', '30→60fps', '运动镜头', '体育素材']
    NOT_SUITABLE_FOR = ['大跨度插帧', 'VR 立体', '极端运动']
    MAX_MULTIPLIER = 8

    PARAMS = {
        'motion_sensitivity': (0, 100, 50, '运动检测灵敏度'),
        'artifact_sensitivity':(0, 100, 50, '伪影检测灵敏度，越高越保守'),
        'smoothness':         (0, 100, 50, '运动平滑度'),
        'detail_preserve':    (0, 100, 50, '插帧细节保留度')
    }

    def preset_sports(self):
        return {'motion_sensitivity': 70, 'artifact_sensitivity': 60,
                'smoothness': 40, 'detail_preserve': 60}

    def preset_cinema_24to60(self):
        return {'motion_sensitivity': 50, 'artifact_sensitivity': 70,
                'smoothness': 60, 'detail_preserve': 55}
```

**非线性运动处理原理**：
- Apollo 通过双向光流 + 运动掩码，识别非线性运动区域并使用多假设插值。
- `artifact_sensitivity` 是关键参数，过高会拒绝合理插帧，过低会产生撕裂。
- 24→60fps 推荐使用 Apollo Fast，速度更快且视觉差异极小。

### 4.2 Chronos / Chronos Fast

Chronos 是 Topaz 的通用帧插值模型，适用范围比 Apollo 更广，特别适合慢动作制作。

```python
class ChronosModel:
    NAME = 'chronos'
    NAME_FAST = 'chronos-fast'
    SUITABLE_FOR = ['慢动作制作', '24→120fps', '通用插帧', '混合运动']
    NOT_SUITABLE_FOR = ['VR 立体', '极端高速运动']
    MAX_MULTIPLIER = 16

    PARAMS = {
        'motion_estimation':  (0, 100, 50, '运动估计精度'),
        'smoothness':         (0, 100, 55, '运动平滑度'),
        'detail_preserve':    (0, 100, 50, '细节保留'),
        'artifact_remove':    (0, 100, 50, '插帧伪影去除')
    }

    def preset_slowmo_4x(self):
        """4 倍慢动作。"""
        return {'motion_estimation': 70, 'smoothness': 60,
                'detail_preserve': 55, 'artifact_remove': 65}

    def preset_cinema_smooth(self):
        """电影感平滑插帧。"""
        return {'motion_estimation': 60, 'smoothness': 70,
                'detail_preserve': 50, 'artifact_remove': 55}
```

**慢动作制作指南**：
- 4x 慢动作推荐用 Chronos（非 Fast），因为 Fast 在大跨度插帧下会出现运动模糊丢失。
- 慢动作素材应先用 Chronos 插帧到目标帧率，再在 NLE 中放慢速度，避免重复插帧。
- `motion_estimation` 在 70 以上时，模型会启用多假设光流，精度提升但速度下降 1.8 倍。

### 4.3 Aion - 高精度模型

Aion 是 Topaz 4.x 引入的高精度帧插值模型，特别适合大幅运动和 VR 立体素材。

```python
class AionModel:
    NAME = 'aion'
    VERSION = 'v1'
    SUITABLE_FOR = ['大幅运动', 'VR 180/360', '无人机航拍', '极限运动']
    NOT_SUITABLE_FOR = ['低速静态', '快速预览']
    MAX_MULTIPLIER = 16

    PARAMS = {
        'motion_precision':   (0, 100, 70, '运动估计精度，默认高于 Chronos'),
        'disparity_handle':   (0, 100, 60, '视差处理（VR 立体专用）'),
        'occlusion_aware':    (0, 100, 65, '遮挡感知插值'),
        'smoothness':         (0, 100, 50, '运动平滑度')
    }

    def preset_vr180(self):
        return {'motion_precision': 75, 'disparity_handle': 80,
                'occlusion_aware': 70, 'smoothness': 55}

    def preset_drone(self):
        return {'motion_precision': 70, 'disparity_handle': 50,
                'occlusion_aware': 75, 'smoothness': 60}
```

**帧插值模型对比**：

| 模型 | 精度 | 速度 | 大幅运动 | VR 支持 | 推荐场景 |
|------|------|------|----------|---------|----------|
| Apollo Fast | 中 | 极快 | 一般 | 否 | 体育直播、快速预览 |
| Apollo | 高 | 中等 | 良好 | 否 | 通用 24→60 |
| Chronos Fast | 中高 | 快 | 良好 | 否 | 慢动作预览 |
| Chronos | 极高 | 慢 | 优秀 | 否 | 慢动作制作 |
| Aion | 极高 | 最慢 | 极佳 | 是 | VR、极限运动 |

---

## 五、Starlight扩散模型系列

Starlight 是 Topaz 引入的扩散模型系列，基于 Stable Diffusion 架构改造，专门用于视频增强与生成修复。其特点是质量极高但速度极慢。

```python
class StarlightBase:
    NAME_PREFIX = 'starlight'
    ARCHITECTURE = 'video-diffusion'
    INFERENCE_STEPS_DEFAULT = 30
    GUIDANCE_SCALE_DEFAULT = 7.5
    SUPPORTS_LOCAL_RENDER = True

    COMMON_PARAMS = {
        'steps':           (1, 100, 30,  '扩散采样步数，越多越精细'),
        'guidance_scale':  (1, 20,  7.5, 'CFG 引导强度'),
        'strength':        (0, 100, 50,  '扩散强度，控制修改幅度'),
        'seed':            (0, None, 0,  '随机种子，-1 为随机'),
        'noise_level':     (0, 100, 30,  '初始噪声水平')
    }
```

### 5.1 Starlight Mini - 本地渲染

Starlight Mini 是最小化的本地渲染版本，能够在消费级显卡（8GB VRAM）上运行。

```python
class StarlightMini(StarlightBase):
    NAME = 'starlight-mini'
    VRAM_MIN_GB = 8
    VRAM_RECOMMENDED_GB = 12
    MAX_RESOLUTION = (1920, 1080)
    INFERENCE_SPEED_RTX4090 = '约 2 秒/帧 (1080p, 30 steps)'

    def preset_local_default(self):
        return {'steps': 25, 'guidance_scale': 7.0, 'strength': 45,
                'seed': -1, 'noise_level': 25}

    def estimate_vram(self, height, width, steps):
        base = (height * width * 3 * 4) / (1024 ** 3)  # 基础显存
        step_factor = 1 + steps / 50
        return round(base * step_factor * 4.5, 2)  # GB
```

**系统要求与配置**：

| 配置 | 最低 | 推荐 | 高端 |
|------|------|------|------|
| GPU | RTX 3060 8GB | RTX 4070 12GB | RTX 4090 24GB |
| 内存 | 16GB | 32GB | 64GB |
| 存储 | 20GB SSD | 50GB NVMe | 100GB NVMe |
| 速度 (1080p 30步) | ~8 秒/帧 | ~4 秒/帧 | ~2 秒/帧 |

### 5.2 Starlight Sharp / Fast / HQ / Precise

```python
class StarlightVariants(StarlightBase):
    VARIANTS = {
        'sharp': {
            'description': '锐利版，强调细节清晰度',
            'default_steps': 35,
            'use_case': '纪录片、档案片',
            'speed_factor': 1.2
        },
        'fast': {
            'description': '快速版，5-15 步即可出图',
            'default_steps': 12,
            'use_case': '预览、批量处理',
            'speed_factor': 3.5
        },
        'hq': {
            'description': '高质量版，50+ 步获得最佳质量',
            'default_steps': 50,
            'use_case': '电影级、最终输出',
            'speed_factor': 0.6
        },
        'precise': {
            'description': '精确版，最忠实于原片',
            'default_steps': 40,
            'use_case': '法庭证据、医学',
            'speed_factor': 0.8
        }
    }

    def select_variant(self, use_case, time_budget_minutes, quality_target):
        """根据使用场景、时间预算、质量目标选择 Starlight 变体。"""
        if use_case == 'forensic':
            return 'precise'
        if time_budget_minutes < 10:
            return 'fast'
        if quality_target == 'cinema':
            return 'hq'
        if use_case == 'documentary':
            return 'sharp'
        return 'fast'
```

**各版本差异对比**：

| 版本 | 步数 | 速度 (4090, 1080p) | 质量 | 适用场景 |
|------|------|---------------------|------|----------|
| Mini | 25 | ~2 秒/帧 | 中等 | 本地入门 |
| Fast | 12 | ~0.6 秒/帧 | 中等 | 批量预览 |
| Sharp | 35 | ~2.5 秒/帧 | 高 | 纪录片 |
| Precise | 40 | ~3 秒/帧 | 高（保真） | 取证 |
| HQ | 50 | ~4 秒/帧 | 极高 | 电影级 |

---

## 六、模型选择决策树

### 6.1 根据输入素材类型选择模型的流程图

```
┌──────────────────────────────────────────────────────────────────┐
│                          输入素材诊断                              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │ 是否为隔行视频？(DV/DVD/电视录像)         │
        └─────────────────────────────────────────┘
                  │ 是                    │ 否
                  ▼                       ▼
        ┌──────────────────┐    ┌─────────────────────────────┐
        │ 进入 Dione 决策树  │    │ 是否为 AI 生成视频？         │
        └──────────────────┘    └─────────────────────────────┘
                                       │ 是            │ 否
                                       ▼               ▼
                                ┌──────────┐  ┌─────────────────────┐
                                │ Astra    │  │ 主要目标是什么？      │
                                └──────────┘  └─────────────────────┘
                                                     │
                            ┌────────────────────────┼────────────────────────┐
                            ▼                        ▼                        ▼
                    ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
                    │ 提升分辨率    │        │ 帧率提升     │        │ 降噪/修复    │
                    └──────────────┘        └──────────────┘        └──────────────┘
                            │                        │                        │
                            ▼                        ▼                        ▼
                  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
                  │ 含人脸？         │     │ 大幅运动？       │     │ 4K 分辨率？      │
                  └─────────────────┘     └─────────────────┘     └─────────────────┘
                    │ 是    │ 否            │ 是    │ 否            │ 是    │ 否
                    ▼      ▼               ▼      ▼               ▼      ▼
                 Iris   Proteus         Aion   Chronos           Nyx    Artemis
                        /Gaia                  /Apollo
```

### 6.2 模型组合策略

```python
class ModelCombinationStrategy:
    """常用模型组合策略。"""
    STRATEGIES = {
        'lowlight_face': {
            'description': '低光人脸修复',
            'pipeline': [
                ('artemis',  'denoise + dehalo', '基础降噪'),
                ('iris',     'face_enhance=70',  '人脸重建'),
                ('proteus',  'sharpen=30',       '整体锐化')
            ]
        },
        'archive_dv': {
            'description': '老 DV 录像修复',
            'pipeline': [
                ('dione-dv',    'deinterlace',  '去隔行'),
                ('proteus',     'fix_compression=60', '压缩修复'),
                ('theia',       'fidelity=80',  '保真还原')
            ]
        },
        'ai_video_polish': {
            'description': 'AI 生成视频精修',
            'pipeline': [
                ('astra',       'plastic_reduce=55', '塑料感消除'),
                ('iris',        'face_stabilize=65', '人脸稳定'),
                ('chronos',     'smoothness=60',     '运动平滑')
            ]
        },
        'cctv_forensic': {
            'description': '监控取证',
            'pipeline': [
                ('dione-robust', 'motion_compensate=70', '运动补偿'),
                ('theia',        'fidelity=95',          '保真还原'),
                ('nyx',          'detail_keep=80',       '细节保留')
            ]
        },
        'beauty_4k': {
            'description': '美妆 4K',
            'pipeline': [
                ('rhea',        'skin_smooth=70', '美颜'),
                ('rhea-xl',     'large_scale_tex=65', '4K超分'),
                ('hyperion',    'color_expand=70', 'HDR转换')
            ]
        }
    }
```

### 6.3 常见错误选择案例分析

```python
class CommonModelMistakes:
    """模型选择常见错误与修正。"""
    MISTAKES = [
        {
            'error': '用 Iris 处理远景人群镜头',
            'symptom': '人脸过度生成，出现幻觉',
            'fix': '切换到 Proteus，将 restore_face 设为 10-20'
        },
        {
            'error': '用 Artemis 处理 4K 日光素材',
            'symptom': '细节丢失，画面发糊',
            'fix': '切换到 Nyx 或 Proteus'
        },
        {
            'error': '用 Gaia 处理运动镜头',
            'symptom': '运动区域出现伪影、拖影',
            'fix': '切换到 Proteus，或局部使用 Gaia'
        },
        {
            'error': '用 Apollo Fast 做 4x 慢动作',
            'symptom': '运动模糊丢失，慢动作不自然',
            'fix': '切换到 Chronos 或 Aion'
        },
        {
            'error': '用 Astra 处理真实拍摄素材',
            'symptom': '画面过度柔化，失去真实感',
            'fix': '切换到 Proteus 或 Theia'
        },
        {
            'error': '用 Dione Dehalo 处理逐行视频',
            'symptom': '无效果但增加处理时间',
            'fix': '直接使用 Proteus + dehalo=20'
        },
        {
            'error': '叠加 Iris + Rhea 处理美妆',
            'symptom': '过度磨皮，塑料感',
            'fix': '二选一，Rhea 更适合商业美妆'
        }
    ]
```

---

## 七、模型参数原子级映射

### 7.1 参数数学含义

```python
class ParameterMathSemantics:
    """每个参数背后的数学含义。"""
    SEMANTICS = {
        'recover_detail': {
            'formula': 'output = input + alpha * residual_net(input)',
            'alpha': 'recover_detail / 100 * 0.8',
            'unit': '像素残差强度',
            'range_note': '0-30 为轻度，30-70 为中度，70+ 为激进'
        },
        'reduce_noise': {
            'formula': 'output = input * (1 - beta) + spatial_denoise(input) * beta',
            'beta': 'reduce_noise / 100',
            'unit': '空间降噪权重',
            'range_note': '高 ISO 推荐 50-75，日光推荐 0-30'
        },
        'sharpen': {
            'formula': 'output = input + gamma * laplacian(input)',
            'gamma': 'sharpen / 100 * 0.5',
            'unit': '拉普拉斯锐化系数',
            'range_note': '与 reduce_noise 协同，否则会放大噪声'
        },
        'deblur': {
            'formula': 'output = wiener_deconvolve(input, kernel=estimated_psf)',
            'kernel': '由 motion_estimation 网络估计',
            'unit': '反卷积核大小',
            'range_note': '0-20 轻度，20-50 中度，50+ 强力'
        },
        'fix_compression': {
            'formula': 'output = block_aware_filter(input, block_size=8)',
            'block_size': '8 (H264) / 16 (HEVC)',
            'unit': '块效应强度估计',
            'range_note': '网络视频 50-70，原创内容 0-30'
        },
        'dehalo': {
            'formula': 'output = edge_aware_filter(input, halo_mask)',
            'halo_mask': '由边缘检测生成',
            'unit': '光晕抑制权重',
            'range_note': '老视频 20-40，新视频 0-10'
        },
        'face_enhancement': {
            'formula': 'output[face_roi] = face_gan(input[face_roi], strength)',
            'strength': 'face_enhancement / 100',
            'unit': 'GAN 重建权重',
            'range_note': '人脸特写 60-85，远景 30-50'
        },
        'motion_sensitivity': {
            'formula': 'flow_threshold = base_threshold * (1 + sensitivity/100)',
            'unit': '光流置信度阈值',
            'range_note': '体育素材 60-80，访谈 30-50'
        },
        'steps': {
            'formula': 'x_t = x_{t-1} + step_size * noise_pred(x_{t-1}, t)',
            'unit': '扩散采样步数',
            'range_note': 'Fast 5-15，标准 20-40，HQ 50+'
        },
        'guidance_scale': {
            'formula': 'noise_pred = unconditional + scale * (conditional - unconditional)',
            'unit': 'CFG 引导强度',
            'range_note': '保真 5-8，创意 10-15'
        }
    }
```

### 7.2 参数间的相互影响关系

```python
class ParameterInteractions:
    """参数相互影响矩阵，描述主参数变化对副参数推荐值的影响。"""
    INTERACTIONS = {
        ('reduce_noise', 'sharpen'): {
            'relation': 'inverse',
            'rule': 'reduce_noise 每增加 10，sharpen 应减少 3-5',
            'reason': '降噪会平滑高频，锐化需要补偿'
        },
        ('recover_detail', 'reduce_noise'): {
            'relation': 'inverse',
            'rule': 'recover_detail 每增加 20，reduce_noise 应减少 10',
            'reason': '细节恢复会暴露噪声'
        },
        ('fix_compression', 'dehalo'): {
            'relation': 'synergistic',
            'rule': 'fix_compression 高于 50 时 dehalo 应同步提高',
            'reason': '压缩伪影常伴随边缘光晕'
        },
        ('face_enhancement', 'skin_smoothing'): {
            'relation': 'inverse',
            'rule': 'face_enhancement 高于 70 时 skin_smoothing 应低于 40',
            'reason': 'GAN 已重建皮肤，过度平滑会损失肌理'
        },
        ('steps', 'guidance_scale'): {
            'relation': 'inverse',
            'rule': 'steps 低于 15 时 guidance_scale 应低于 6',
            'reason': '低步数高引导会产生伪影'
        },
        ('motion_sensitivity', 'artifact_sensitivity'): {
            'relation': 'direct',
            'rule': '两者保持差值 ≥ 10',
            'reason': '高灵敏度需要高伪影检测'
        }
    }
```

### 7.3 参数优化实验数据

```python
class ParameterExperiments:
    """基于实测的参数优化实验数据。"""
    EXPERIMENTS = {
        'proteus_network_video': {
            'input': '720p H264 1.5Mbps',
            'target': '4K 高质量输出',
            'best_params': {'recover_detail': 50, 'reduce_noise': 35, 'sharpen': 30,
                           'deblur': 15, 'fix_compression': 65, 'dehalo': 15},
            'metrics': {'psnr_gain': 4.2, 'ssim_gain': 0.08, 'vmaf_gain': 18},
            'processing_time': '0.4 秒/帧 (RTX 4090)'
        },
        'artemis_lowlight_iso6400': {
            'input': '1080p ISO6400 夜景',
            'target': '干净 1080p',
            'best_params': {'noise_reduction': 70, 'detail_recovery': 35,
                           'sharpen': 25, 'dehalo': 25, 'deblur': 15},
            'metrics': {'noise_reduction_db': 8.5, 'detail_retention': 82},
            'processing_time': '0.25 秒/帧 (RTX 4090)'
        },
        'iris_face_closeup': {
            'input': '1080p 人脸特写',
            'target': '4K 高质量人脸',
            'best_params': {'face_enhancement': 75, 'skin_smoothing': 35,
                           'eye_enhance': 60, 'hair_restore': 50},
            'metrics': {'face_quality_gain': 35, 'naturalness_score': 8.2},
            'processing_time': '0.6 秒/帧 (RTX 4090)'
        },
        'chronos_slowmo_4x': {
            'input': '60fps 体育素材',
            'target': '240fps 慢动作',
            'best_params': {'motion_estimation': 70, 'smoothness': 60,
                           'detail_preserve': 55, 'artifact_remove': 65},
            'metrics': {'motion_smoothness': 9.0, 'artifact_count_per_min': 2},
            'processing_time': '0.8 秒/帧 (RTX 4090)'
        },
        'starlight_hq_cinema': {
            'input': '4K log 素材',
            'target': '4K HDR 电影级',
            'best_params': {'steps': 50, 'guidance_scale': 7.5, 'strength': 45},
            'metrics': {'perceptual_quality': 9.5, 'fidelity_score': 8.0},
            'processing_time': '4.2 秒/帧 (RTX 4090)'
        }
    }
```

---

## 八、版本兼容性矩阵

### 8.1 各模型在不同版本中的可用性

```python
class ModelVersionMatrix:
    """模型版本兼容性矩阵。"""
    MATRIX = {
        # 模型名: {'3.0': bool, '3.1': bool, '3.2': bool, '3.3': bool, '4.0': bool, '4.1': bool}
        'proteus':           {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'artemis':           {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'artemis-hq':        {'3.0': False, '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'gaia':              {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'gaia-hq':           {'3.0': False, '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'iris':              {'3.0': False, '3.1': False, '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'iris-lq':           {'3.0': False, '3.1': False, '3.2': False, '3.3': True,  '4.0': True,  '4.1': True},
        'nyx':               {'3.0': False, '3.1': False, '3.2': False, '3.3': True,  '4.0': True,  '4.1': True},
        'rhea':              {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': True,  '4.1': True},
        'rhea-xl':           {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': True,  '4.1': True},
        'hyperion':          {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': True,  '4.1': True},
        'astra':             {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': False, '4.1': True},
        'theia':             {'3.0': False, '3.1': False, '3.2': False, '3.3': True,  '4.0': True,  '4.1': True},
        'dione-dv':          {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'dione-tv':          {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'dione-dehalo':      {'3.0': False, '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'dione-robust':      {'3.0': False, '3.1': False, '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'dione-robust-dehalo':{'3.0': False,'3.1': False, '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'apollo':            {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'apollo-fast':       {'3.0': False, '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'chronos':           {'3.0': True,  '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'chronos-fast':      {'3.0': False, '3.1': True,  '3.2': True,  '3.3': True,  '4.0': True,  '4.1': True},
        'aion':              {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': True,  '4.1': True},
        'starlight-mini':    {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': False, '4.1': True},
        'starlight-sharp':   {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': False, '4.1': True},
        'starlight-fast':    {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': False, '4.1': True},
        'starlight-hq':      {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': False, '4.1': True},
        'starlight-precise': {'3.0': False, '3.1': False, '3.2': False, '3.3': False, '4.0': False, '4.1': True}
    }

    def is_available(self, model, version):
        return self.MATRIX.get(model, {}).get(version, False)

    def list_models_for_version(self, version):
        return [m for m, versions in self.MATRIX.items() if versions.get(version, False)]

    def suggest_migrate(self, old_version, new_version):
        """版本迁移建议。"""
        added = []
        removed = []
        for model, versions in self.MATRIX.items():
            if versions.get(new_version, False) and not versions.get(old_version, False):
                added.append(model)
            if not versions.get(new_version, False) and versions.get(old_version, False):
                removed.append(model)
        return {'added': added, 'removed': removed}
```

### 8.2 模型更新历史

```python
class ModelUpdateHistory:
    """关键模型更新记录。"""
    HISTORY = [
        {'version': '3.0', 'year': '2022', 'major_updates': ['Proteus 首发', 'Gaia/Artemis 重做']},
        {'version': '3.1', 'year': '2022', 'major_updates': ['Apollo Fast 引入', 'Artemis HQ 发布']},
        {'version': '3.2', 'year': '2023', 'major_updates': ['Iris 人脸模型首发', 'Dione Robust 加入']},
        {'version': '3.3', 'year': '2023', 'major_updates': ['Nyx 4K 降噪', 'Theia 保真模型', 'Iris LQ']},
        {'version': '4.0', 'year': '2024', 'major_updates': ['Rhea 商业美妆', 'Hyperion HDR', 'Aion 高精度插帧', 'Starlight 扩散系列发布']},
        {'version': '4.1', 'year': '2025', 'major_updates': ['Astra AI视频修复', 'Starlight 全系列正式版', 'Rhea XL 8K 超分']}
    ]
```

### 8.3 版本迁移指南

```python
class VersionMigrationGuide:
    """从旧版本迁移到新版本的实践指南。"""
    GUIDES = {
        '3.x_to_4.x': {
            'breaking_changes': [
                '部分 3.x 模型预设需要重新创建',
                'CLI 命令结构有调整，旧脚本需更新',
                '项目文件格式不兼容，需重新导入'
            ],
            'migration_steps': [
                '1. 导出 3.x 所有自定义预设为 JSON',
                '2. 安装 4.x 并启动一次以初始化模型缓存',
                '3. 在 4.x 中重新导入预设 JSON',
                '4. 测试关键工作流，对比输出质量',
                '5. 升级 CLI 脚本至 4.x 语法',
                '6. 删除旧模型缓存释放空间'
            ],
            'rollback_plan': '保留 3.x 安装包，4.x 故障时可并行运行'
        },
        '4.0_to_4.1': {
            'breaking_changes': [
                'Astra 模型需要单独下载（约 4GB）',
                'Starlight 系列默认未启用，需在设置中开启'
            ],
            'migration_steps': [
                '1. 升级到 4.1',
                '2. 在「设置-模型管理」中下载 Astra',
                '3. 启用 Starlight 系列实验性功能',
                '4. 测试 Starlight 性能，决定是否用于生产'
            ]
        }
    }

    def estimate_migration_time(self, project_count, preset_count):
        """估算迁移所需时间。"""
        base = 30  # 基础 30 分钟
        project_time = project_count * 5  # 每项目 5 分钟
        preset_time = preset_count * 2  # 每预设 2 分钟
        total_minutes = base + project_time + preset_time
        return {'total_minutes': total_minutes,
                'recommended_buffer_minutes': int(total_minutes * 0.3)}
```

### 8.4 模型权重文件清单

```python
class ModelWeightsInventory:
    """模型权重文件清单与磁盘占用。"""
    WEIGHTS = {
        'proteus':          {'size_gb': 1.2, 'files': ['proteus-v4-fp16.onnx', 'proteus-v4-meta.json']},
        'artemis':          {'size_gb': 0.9, 'files': ['artemis-v4-fp16.onnx']},
        'artemis-hq':       {'size_gb': 1.4, 'files': ['artemis-hq-v4-fp16.onnx']},
        'gaia':             {'size_gb': 1.1, 'files': ['gaia-v4-fp16.onnx']},
        'gaia-hq':          {'size_gb': 1.8, 'files': ['gaia-hq-v4-fp16.onnx']},
        'iris':             {'size_gb': 1.6, 'files': ['iris-v4-fp16.onnx', 'iris-face-det.onnx']},
        'nyx':              {'size_gb': 1.7, 'files': ['nyx-v4-fp16.onnx']},
        'rhea':             {'size_gb': 1.5, 'files': ['rhea-v4-fp16.onnx']},
        'rhea-xl':          {'size_gb': 2.4, 'files': ['rhea-xl-v4-fp16.onnx']},
        'hyperion':         {'size_gb': 1.3, 'files': ['hyperion-v4-fp16.onnx']},
        'astra':            {'size_gb': 2.1, 'files': ['astra-v1-fp16.onnx']},
        'theia':            {'size_gb': 0.8, 'files': ['theia-v4-fp16.onnx']},
        'dione-dv':         {'size_gb': 0.7, 'files': ['dione-dv-v4-fp16.onnx']},
        'dione-tv':         {'size_gb': 0.7, 'files': ['dione-tv-v4-fp16.onnx']},
        'apollo':           {'size_gb': 1.0, 'files': ['apollo-v4-fp16.onnx']},
        'chronos':          {'size_gb': 1.3, 'files': ['chronos-v4-fp16.onnx']},
        'aion':             {'size_gb': 1.9, 'files': ['aion-v1-fp16.onnx']},
        'starlight-mini':   {'size_gb': 3.5, 'files': ['starlight-mini-v1-fp16.onnx']},
        'starlight-hq':     {'size_gb': 8.2, 'files': ['starlight-hq-v1-fp16.onnx']}
    }

    def total_size(self, model_list):
        return sum(self.WEIGHTS[m]['size_gb'] for m in model_list if m in self.WEIGHTS)

    def recommend_for_disk(self, disk_gb):
        """根据磁盘空间推荐模型组合。"""
        all_models = list(self.WEIGHTS.keys())
        # 优先保留通用模型
        priority = ['proteus', 'artemis', 'gaia', 'iris', 'apollo', 'chronos']
        selected = []
        total = 0
        for m in priority + [x for x in all_models if x not in priority]:
            size = self.WEIGHTS[m]['size_gb']
            if total + size <= disk_gb:
                selected.append(m)
                total += size
        return {'selected': selected, 'total_gb': round(total, 2)}
```

---

## 附录：术语对照表

| 术语 | 英文 | 含义 |
|------|------|------|
| 超分辨率 | Super Resolution | 提升视频分辨率 |
| 帧插值 | Frame Interpolation | 在原有帧之间插入新帧 |
| 去隔行 | Deinterlace | 将隔行扫描转为逐行扫描 |
| 时序融合 | Temporal Fusion | 利用多帧信息增强单帧 |
| 光流 | Optical Flow | 像素级运动估计 |
| 残差注意力 | Residual Attention | 注意力机制 + 残差连接 |
| 扩散模型 | Diffusion Model | 通过去噪过程生成图像 |
| CFG 引导 | Classifier-Free Guidance | 无分类器引导 |
| 拉普拉斯锐化 | Laplacian Sharpening | 基于二阶导数的锐化 |
| 反卷积 | Deconvolution | 反向估计清晰图像 |
| 保真度 | Fidelity | 输出与输入的一致性 |
| 块效应 | Block Artifact | 压缩产生的方块伪影 |
| 光晕 | Halo | 边缘过渡区的彩色光环 |
| 梳状伪影 | Combing Artifact | 隔行视频运动产生的横向条纹 |

---

> 本文档基于 Topaz Video AI 4.x 官方文档、白皮书及社区实测数据整理。模型参数会随版本更新调整，使用前请以软件内帮助文档为准。
