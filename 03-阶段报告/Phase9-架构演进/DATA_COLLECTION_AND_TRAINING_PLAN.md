# 数据收集与模型训练方案 - AE Knowledge Vault 小模型生态

## 一、现有数据资产盘点

### 1.1 JSX代码资源（训练数据基础）

| 数据类型 | 数量 | 来源 | 用途 |
|---------|------|------|------|
| JSX脚本文件 | 200+ | 项目根目录、ae_additive_scripts、output_director | JSX代码生成模型训练 |
| 表达式模板 | 10个 | expression_template_library.json | 表达式生成 |
| 效果参数映射 | 232个 | matchname_mapping_dictionary.json | 参数预测模型 |
| 复刻预设 | 10个 | style_presets/*.jsx | 风格迁移 |
| 风格复刻脚本 | 50+ | replicate_templates/ | 代码生成样本 |

**关键文件路径**：
- 表达式模板库：[expression_template_library.json](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_director/ae_project_analysis/replicate_templates/expression_template_library.json)
- 效果预设：[effect_presets.json](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/config/effect_presets.json)
- 参数映射：[matchname_mapping_dictionary.json](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_director/ae_project_analysis/replicate_templates/matchname_mapping_dictionary.json)

### 1.2 风格分析数据（风格分类训练数据）

| 数据类型 | 数量 | 来源 | 特征维度 |
|---------|------|------|---------|
| 风格指纹JSON | 15个 | output_director/ae_10_tutorials_style/ | 色彩/亮度/饱和度/节奏/构图 |
| 项目分析数据 | 13个 | ae_project_analysis/bdata_params/ | 效果参数/图层结构 |
| 风格对比报告 | 1个 | style_comparison_report.json | 多项目对比 |

**风格类型分布**：
- 高动感、快切、暗调、低饱和（主流风格）
- 舒缓、电影感（辅助风格）
- 风格标签：cinematic, anime_puppet, glitch_digital, audio_visual 等

### 1.3 数据质量评估

| 数据集 | 完整性 | 可用性 | 备注 |
|--------|--------|--------|------|
| JSX代码 | ★★★★☆ | 高 | 需清洗注释、标准化命名 |
| 风格指纹 | ★★★★★ | 高 | 已结构化，可直接使用 |
| 效果参数 | ★★★★☆ | 中 | 需补充参数范围验证 |
| 表达式模板 | ★★★☆☆ | 中 | 样本量偏少，需扩充 |

---

## 二、数据收集方案（慢剪视频专项）

### 2.1 目标
针对"慢剪"风格（慢节奏剪辑、长镜头、电影感），从其他项目的未完成视频中收集训练数据。

### 2.2 数据收集流程

```
步骤1: 视频源定位
├── 其他项目中的慢剪视频素材
├── 用户历史项目中的未完成作品
└── 外部参考视频（如电影片段、MV等）

步骤2: 视频分析提取
├── 使用VideoStyleExtractor提取风格指纹
│   ├── 色彩分析（亮度、饱和度、色调）
│   ├── 节奏分析（剪辑率、镜头时长）
│   ├── 构图分析（边缘密度、场景复杂度）
│   └── 音频分析（BPM、能量、情绪）
├── 生成风格参数字典
└── 输出AE效果预设

步骤3: 数据标注与增强
├── 人工标注风格类别
├── 自动生成变体（亮度±10%、饱和度±15%等）
└── 构建训练/验证/测试集

步骤4: 数据集构建
├── 格式转换为模型输入格式
├── 特征归一化
└── 保存为JSONL格式
```

### 2.3 慢剪风格特征定义

| 特征维度 | 慢剪典型值 | 快剪对比值 |
|---------|-----------|-----------|
| 剪辑率 | < 1次/秒 | > 3次/秒 |
| 平均镜头时长 | > 2秒 | < 0.5秒 |
| 亮度 | 40-60（中等） | 20-50（变化大） |
| 饱和度 | 30-50（低饱和） | 40-70（较高） |
| 风格标签 | cinematic, slow_cut, cinematic_color | hyper_fast, fast_cut, high_dynamic |

### 2.4 数据收集脚本

```python
# 建议的数据收集脚本路径
# scripts/collect_slow_cut_data.py

import json
from pathlib import Path
from video.style_extractor import VideoStyleExtractor

def collect_slow_cut_data(video_paths: list[Path], output_dir: Path):
    """收集慢剪风格训练数据"""
    extractor = VideoStyleExtractor()
    dataset = []
    
    for video_path in video_paths:
        # 提取风格指纹
        fingerprint = extractor.extract(video_path)
        
        # 判断是否为慢剪风格
        if fingerprint.rhythm.cut_rate < 1.5 and fingerprint.rhythm.avg_shot_duration > 1.5:
            label = "slow_cut"
        else:
            label = "other"
        
        # 构建训练样本
        sample = {
            "video_path": str(video_path),
            "label": label,
            "features": {
                "brightness": fingerprint.color.brightness,
                "saturation": fingerprint.color.saturation,
                "cut_rate": fingerprint.rhythm.cut_rate,
                "avg_shot_duration": fingerprint.rhythm.avg_shot_duration,
                # ... 更多特征
            }
        }
        dataset.append(sample)
    
    # 保存数据集
    output_path = output_dir / "slow_cut_dataset.jsonl"
    with open(output_path, "w") as f:
        for sample in dataset:
            f.write(json.dumps(sample) + "\n")
    
    return dataset
```

---

## 三、模型部署方案

### 3.1 TIER_1 模型选型

| 模型 | 参数量 | 用途 | 部署方式 |
|------|--------|------|---------|
| **BGE-M3** | 568M | 嵌入/检索 | transformers + sentence-transformers |
| **Qwen2-0.5B** | 500M | 轻量生成 | transformers + vLLM |
| **Qwen2-1.5B** | 1.5B | 中等生成 | transformers + vLLM |
| **BGE-Small-ZH** | 33M | 中文嵌入（超轻量） | transformers |

### 3.2 本地部署架构

```
┌─────────────────────────────────────────────────────────┐
│                  TIER_1 本地模型层                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ BGE-Small-ZH │  │ Qwen2-0.5B   │  │ 本地适配器    │  │
│  │ (33M 嵌入)   │  │ (500M 生成)   │  │ LocalAdapter │  │
│  └───────┬──────┘  └───────┬──────┘  └───────┬──────┘  │
│          │                  │                  │         │
│          └──────────────────┴──────────────────┘         │
│                            ↓                             │
│                  ┌─────────────────┐                    │
│                  │ LocalModelAdapter│                    │
│                  │ (统一接口)        │                    │
│                  └────────┬────────┘                    │
│                           ↓                              │
├───────────────────────────┴──────────────────────────────┤
│                                                          │
│                     LLM Gateway                          │
│                   (统一调用入口)                          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 3.3 部署代码框架

```python
# core/local_model_adapter.py

from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json

class LocalModelType(Enum):
    BGE_SMALL_ZH = "bge-small-zh"      # 33M 中文嵌入
    BGE_M3 = "bge-m3"                   # 568M 多语言嵌入
    QWEN2_05B = "qwen2-0.5b"           # 500M 生成
    QWEN2_15B = "qwen2-1.5b"           # 1.5B 生成

@dataclass
class LocalModelConfig:
    model_type: LocalModelType
    model_path: str
    device: str = "cpu"  # 本地无GPU，使用CPU
    max_length: int = 512
    batch_size: int = 8

class LocalModelAdapter:
    """本地模型适配器 - 统一接口"""
    
    def __init__(self, config: LocalModelConfig):
        self.config = config
        self._model = None
        self._tokenizer = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """初始化模型（延迟加载）"""
        try:
            if "bge" in self.config.model_type.value:
                return await self._init_embedding_model()
            else:
                return await self._init_generation_model()
        except Exception as e:
            print(f"模型初始化失败: {e}")
            return False
    
    async def _init_embedding_model(self) -> bool:
        """初始化嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self.config.model_path,
                device=self.config.device
            )
            self._initialized = True
            return True
        except ImportError:
            # 降级到 transformers
            from transformers import AutoModel, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
            self._model = AutoModel.from_pretrained(self.config.model_path)
            self._initialized = True
            return True
    
    async def _init_generation_model(self) -> bool:
        """初始化生成模型"""
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.config.model_path,
            torch_dtype="auto"  # 自动选择精度
        )
        self._initialized = True
        return True
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """文本嵌入"""
        if not self._initialized:
            await self.initialize()
        
        if hasattr(self._model, 'encode'):
            # sentence-transformers
            embeddings = self._model.encode(texts)
            return [e.tolist() for e in embeddings]
        else:
            # transformers
            import torch
            inputs = self._tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
            with torch.no_grad():
                outputs = self._model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1)
            return embeddings.tolist()
    
    async def generate(self, prompt: str, max_new_tokens: int = 100) -> str:
        """文本生成"""
        if not self._initialized:
            await self.initialize()
        
        import torch
        inputs = self._tokenizer(prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )
        
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    def is_ready(self) -> bool:
        return self._initialized
```

### 3.4 与LLM Gateway集成

```python
# 在 core/llm_gateway.py 中添加

class LLMGateway:
    def __init__(self, config: LLMConfig):
        # ... 现有代码 ...
        self._local_adapters: Dict[str, LocalModelAdapter] = {}
        self._init_local_models()
    
    def _init_local_models(self):
        """初始化本地模型适配器"""
        tier1_config = self._config.tier_config.get("tier1_local", {})
        
        if tier1_config.get("enabled", False):
            for model_name, model_config in tier1_config.get("models", {}).items():
                adapter = LocalModelAdapter(LocalModelConfig(
                    model_type=LocalModelType(model_config["type"]),
                    model_path=model_config["path"],
                    device=model_config.get("device", "cpu"),
                ))
                self._local_adapters[model_name] = adapter
    
    async def _call_tier1_local(self, task_type: TaskType, message: str) -> LLMResponse:
        """调用TIER_1本地模型"""
        start_time = time.time()
        
        # 选择合适的本地模型
        if task_type in [TaskType.STYLE_ANALYSIS, TaskType.INTENT_CLASSIFICATION]:
            # 嵌入任务
            adapter_name = "bge-small-zh"
            adapter = self._local_adapters.get(adapter_name)
            if adapter:
                embedding = await adapter.embed([message])
                # 使用嵌入进行分类（需要额外的分类头）
                ...
        elif task_type in [TaskType.PARAMETER_OPTIMIZATION, TaskType.CODE_GENERATION]:
            # 轻量生成任务
            adapter_name = "qwen2-0.5b"
            adapter = self._local_adapters.get(adapter_name)
            if adapter:
                content = await adapter.generate(message)
                return LLMResponse(
                    content=content,
                    success=True,
                    tier=ModelTier.TIER_1_LOCAL_SPECIALIZED,
                    cost_usd=0.0,  # 本地模型免费
                    latency_ms=(time.time() - start_time) * 1000
                )
        
        # 降级到云端API
        return None
```

---

## 四、JiuwenSwarm多智能体集成

### 4.1 集成方案

项目已有OpenSpace多智能体框架，可直接利用：

```
OpenSpace/openspace/agents/
├── multi_agent_orchestrator.py  # 多智能体编排器
├── agent_definitions.py         # 智能体定义
└── turns/loop.py                # 交互循环
```

### 4.2 智能体协作模式

```
┌─────────────────────────────────────────────────────────┐
│                  多智能体协作流程                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  用户请求 → Orchestrator → 分发任务                       │
│                           │                              │
│          ┌────────────────┼────────────────┐            │
│          ↓                ↓                ↓            │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│    │ 风格分析Agent │    │ 代码生成Agent │    │ 参数优化Agent │        │
│    │ (TIER_1)  │    │ (TIER_2)  │    │ (TIER_1)  │        │
│    └─────┬────┘    └─────┬────┘    └─────┬────┘        │
│          │                │                │            │
│          └────────────────┴────────────────┘            │
│                           ↓                              │
│                    结果聚合 & 验证                         │
│                           ↓                              │
│                       最终输出                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 五、训练数据准备

### 5.1 JSX代码数据集构建

```python
# models/data/prepare_jsx_dataset.py

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class JSXSample:
    """JSX代码训练样本"""
    code: str
    task_type: str  # "effect_apply", "layer_create", "animation_keyframe"
    description: str
    parameters: dict
    source: str

def prepare_jsx_dataset(
    jsx_dir: Path,
    presets_path: Path,
    output_path: Path
) -> List[JSXSample]:
    """构建JSX代码训练数据集"""
    
    samples = []
    
    # 1. 从预设文件加载
    with open(presets_path) as f:
        presets = json.load(f)
    
    for effect_name, effect_data in presets.get("effects", {}).items():
        # 为每个预设生成训练样本
        for preset in effect_data.get("presets", []):
            sample = JSXSample(
                code=generate_effect_code(effect_name, preset["params"]),
                task_type="effect_apply",
                description=f"应用{effect_name}效果，预设：{preset['name']}",
                parameters=preset["params"],
                source="effect_presets.json"
            )
            samples.append(sample)
    
    # 2. 从JSX文件加载
    for jsx_file in jsx_dir.glob("**/*.jsx"):
        code = jsx_file.read_text(encoding="utf-8", errors="ignore")
        
        # 分类任务类型
        task_type = classify_jsx_task(code)
        
        sample = JSXSample(
            code=code,
            task_type=task_type,
            description=extract_description(code),
            parameters=extract_parameters(code),
            source=str(jsx_file)
        )
        samples.append(sample)
    
    # 3. 保存为JSONL
    with open(output_path, "w") as f:
        for sample in samples:
            f.write(json.dumps({
                "code": sample.code,
                "task_type": sample.task_type,
                "description": sample.description,
                "parameters": sample.parameters,
                "source": sample.source
            }) + "\n")
    
    return samples
```

### 5.2 风格分类数据集构建

```python
# models/data/prepare_style_dataset.py

import json
from pathlib import Path

def prepare_style_dataset(
    fingerprint_dir: Path,
    output_path: Path
) -> List[dict]:
    """构建风格分类训练数据集"""
    
    samples = []
    
    for fp_file in fingerprint_dir.glob("fp_*.json"):
        with open(fp_file) as f:
            fingerprint = json.load(f)
        
        # 提取特征向量
        features = {
            "brightness": fingerprint.get("brightness", 0),
            "saturation": fingerprint.get("saturation", 0),
            "cut_rate": fingerprint.get("cut_rate", 0),
            "avg_shot_duration": fingerprint.get("avg_shot_duration", 0),
            # ... 更多特征
        }
        
        # 提取标签
        style_tags = fingerprint.get("style_tags", [])
        label = style_tags[0] if style_tags else "unknown"
        
        samples.append({
            "features": features,
            "label": label,
            "source": fp_file.stem
        })
    
    # 保存
    with open(output_path, "w") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")
    
    return samples
```

---

## 六、执行计划

### 阶段1：数据准备（1-2天）
1. 运行数据收集脚本，构建训练数据集
2. 清洗和标准化JSX代码数据
3. 标注慢剪风格样本

### 阶段2：模型部署（2-3天）
1. 下载BGE-Small-ZH和Qwen2-0.5B模型
2. 实现LocalModelAdapter
3. 集成到LLM Gateway

### 阶段3：训练微调（3-5天）
1. 准备训练数据
2. 微调风格分类模型
3. 微调JSX代码生成模型

### 阶段4：集成测试（1-2天）
1. 端到端性能测试
2. 成本对比分析
3. 优化推理速度