# Silhouette 行业标准与质量规范

> 分类: 深度研究
> 更新日期: 2026-07-11
> 概述: 系统梳理 Silhouette 项目的行业交付标准、质量控制流程、验收标准与版本管理规范

## 目录
---

- [一、行业标准体系概览](#一行业标准体系概览)
- [二、交付标准规范](#二交付标准规范)
- [三、质量控制流程](#三质量控制流程)
- [四、验收标准](#四验收标准)
- [五、版本管理规范](#五版本管理规范)
- [六、色彩管理标准](#六色彩管理标准)
- [七、元数据规范](#七元数据规范)
- [八、合规与安全](#八合规与安全)

---

## 一、行业标准体系概览

### 1.1 行业标准层级

Silhouette 项目遵循多层级的标准体系：

```
国际标准（ISO/ITU）
    │
    ├─ 行业标准（ACES/Dolby/Netflix）
    │    │
    │    ├─ 公司标准（各 VFX 工作室）
    │    │    │
    │    │    └─ 项目标准（具体项目规范）
    │    │
    │    └─ 工具标准（Silhouette 内部规范）
    │
    └─ 交付标准（客户验收标准）
```

### 1.2 主要标准参考

| 标准 | 颁布机构 | 适用范围 |
|------|---------|---------|
| ACES 1.3+ | AMPAS | 色彩管理 |
| Dolby Vision | Dolby | HDR 交付 |
| Netflix Post Tech Specs | Netflix | 流媒体交付 |
| Disney Delivery Specs | Disney | 影院/流媒体 |
| IMF | SMPTE | 母版交付 |
| EXR 2.0 | OpenEXR | 文件格式 |
| VFX Industry Guidelines | VES | 通用规范 |

---

## 二、交付标准规范

### 2.1 分辨率与帧率标准

| 项目类型 | 分辨率 | 帧率 | 色深 |
|---------|--------|------|------|
| 电影（DCP） | 2048×1080 / 4096×2160 | 24 fps | 16-bit |
| 流媒体 4K | 3840×2160 | 23.976/24/25 fps | 10/12-bit |
| 流媒体 HDR | 3840×2160 | 23.976/24/25 fps | 12/16-bit |
| 电视广播 | 1920×1080 | 25/29.97/50 fps | 10-bit |
| 广告 | 1920×1080 / 3840×2160 | 24/25/30 fps | 10-bit |
| 社交媒体 | 1080×1080 / 1080×1920 | 30/60 fps | 8-bit |

### 2.2 文件格式标准

**遮罩与中间文件**：
- **格式**：OpenEXR 2.0
- **色深**：16-bit half-float（推荐）或 32-bit float
- **压缩**：ZIP（工作）或 DWAB（归档）
- **通道**：RGB + Alpha（必要时含多层遮罩）

**最终输出**：
- **影院**：DPX 10-bit log
- **流媒体**：ProRes 422 HQ / 4444 XQ
- **广播**：ProRes 422 HQ / DNxHR
- **预览**：H.264 / H.265

### 2.3 命名规范

**标准命名格式**：
```
[项目代号]_[序列号]_[镜头号]_[任务]_[版本号].[帧号].[扩展名]
```

**示例**：
```
AVTR_SEQ010_SH0140_roto_v003.0001.exr
AVTR_SEQ010_SH0140_paint_v002.0001.exr
AVTR_SEQ010_SH0140_final_v001.0001.exr
```

**字段说明**：
| 字段 | 长度 | 说明 |
|------|------|------|
| 项目代号 | 4-6 字符 | 项目缩写（大写） |
| 序列号 | SEQ+3位 | 序列编号 |
| 镜头号 | SH+4位 | 镜头编号 |
| 任务 | 小写 | roto/paint/track/final |
| 版本号 | v+3位 | 从 v001 开始 |
| 帧号 | 4位 | 从 0001 开始 |

### 2.4 交付包结构

```
SHOT_DELIVERY/
├── exr/                           # 最终 EXR 序列
│   ├── AVTR_SEQ010_SH0140_final_v001.0001.exr
│   └── ...
├── mattes/                        # 独立遮罩（可选）
│   ├── character/
│   │   └── AVTR_SEQ010_SH0140_char_v001.####.exr
│   ├── prop/
│   │   └── AVTR_SEQ010_SH0140_prop_v001.####.exr
│   └── background/
│       └── AVTR_SEQ010_SH0140_bg_v001.####.exr
├── tracking/                      # 跟踪数据
│   └── AVTR_SEQ010_SH0140_track_v001.json
├── project/                       # Silhouette 项目文件
│   └── AVTR_SEQ010_SH0140.sfx
├── proxies/                       # 代理视频
│   └── AVTR_SEQ010_SH0140_proxy.mov
├── qc/                            # QC 报告
│   ├── qc_report.md
│   └── qc_notes.txt
└── manifest.json                  # 交付清单
```

**manifest.json 示例**：
```json
{
  "shot": "AVTR_SEQ010_SH0140",
  "version": "v001",
  "date": "2026-07-11",
  "artist": "张三",
  "supervisor": "李四",
  "frameRange": [1, 240],
  "resolution": [3840, 2160],
  "frameRate": 24,
  "colorSpace": "ACEScg",
  "tasks": ["roto", "paint", "track"],
  "files": {
    "exr": "exr/AVTR_SEQ010_SH0140_final_v001.####.exr",
    "project": "project/AVTR_SEQ010_SH0140.sfx"
  }
}
```

---

## 三、质量控制流程

### 3.1 三层 QC 体系

```
Layer 1: Artist QC（自检）
    │   └─ 艺术家完成后的自我检查
    ▼
Layer 2: Lead QC（负责人审查）
    │   └─ 团队负责人或 Lead 的审查
    ▼
Layer 3: Supervisor QC（总监终审）
        └─ VFX Supervisor 的最终验收
```

### 3.2 Artist QC 检查清单

**通用检查**：
- [ ] 帧范围完整（含 +2 handle）
- [ ] 分辨率正确
- [ ] 帧率正确
- [ ] 色彩空间标记正确
- [ ] Alpha 通道正常（0-1 范围）
- [ ] 无黑帧、坏帧

**Roto 专项检查**：
- [ ] 边缘无溢出
- [ ] 无遮罩抖动（< 0.5px RMS）
- [ ] 运动模糊匹配
- [ ] 无遮罩穿透（衣物、肢体）
- [ ] 头发细节完整
- [ ] 半透明区域处理正确

**Paint 专项检查**：
- [ ] 修复区域无痕迹
- [ ] 帧间一致性
- [ ] 光影匹配
- [ ] 纹理连续
- [ ] 无克隆痕迹

**跟踪专项检查**：
- [ ] 跟踪点稳定
- [ ] 无漂移
- [ ] 遮挡处理正确
- [ ] 数据格式正确

### 3.3 Lead QC 检查清单

**技术检查**：
- [ ] 文件命名规范
- [ ] 交付包结构完整
- [ ] 元数据正确
- [ ] 版本号正确

**艺术检查**：
- [ ] 整体质量达标
- [ ] 与参考一致
- [ ] 无明显瑕疵
- [ ] 风格统一

**流程检查**：
- [ ] 项目文件可打开
- [ ] 节点结构清晰
- [ ] 无冗余节点
- [ ] 注释完整

### 3.4 Supervisor QC 检查清单

- [ ] 符合创意要求
- [ ] 与上下游一致
- [ ] 交付标准符合
- [ ] 无技术风险
- [ ] 批准发布

### 3.5 QC 报告模板

```markdown
# QC Report: AVTR_SEQ010_SH0140

## 基本信息
- **镜头**：AVTR_SEQ010_SH0140
- **版本**：v003
- **检查人**：王五
- **日期**：2026-07-11
- **结果**：PASS / FAIL / REVISE

## 检查结果

### Roto（PASS）
- 边缘精度：优
- 时序一致性：优
- 备注：头发区域需小幅修正

### Paint（PASS）
- 修复质量：优
- 帧间一致：良
- 备注：无

### 跟踪（PASS）
- 跟踪精度：0.2px
- 备注：无

## 修改建议
1. 第 45-50 帧，头发边缘增加 2px 软化
2. 第 120 帧，左手边缘小幅调整

## 结论
镜头通过 QC，建议进行小幅修正后发布。
```

---

## 四、验收标准

### 4.1 视觉验收标准

**边缘质量**：
| 等级 | 标准 | 适用 |
|------|------|------|
| A+ | 边缘误差 < 0.5px，无可见瑕疵 | 电影 |
| A | 边缘误差 < 1px，无可见瑕疵 | 流媒体 |
| B | 边缘误差 < 2px，轻微瑕疵可接受 | 广告 |
| C | 边缘误差 < 3px，瑕疵不影响观看 | 预览 |

**时序一致性**：
| 指标 | 标准 |
|------|------|
| 帧间抖动 | < 0.5px RMS |
| 突变帧 | 无（除非场景切换） |
| 运动模糊 | 与原素材视觉匹配 |

### 4.2 技术验收标准

| 检查项 | 标准 | 容差 |
|--------|------|------|
| 分辨率 | 项目要求 | ±0 |
| 帧率 | 项目要求 | ±0 |
| 色彩空间 | 正确标记 | 严格 |
| Alpha 范围 | 0.0-1.0 | 严格 |
| 色深 | ≥ 16-bit | 严格 |
| 帧范围 | 完整 + handle | +2 帧 |
| 文件完整性 | 无损坏 | 严格 |
| 元数据 | 完整 | 严格 |

### 4.3 性能验收标准

**文件大小**：
- EXR 4K 单帧：5-50 MB（视压缩）
- ProRes 422 HQ 4K：~150 MB/分钟

**加载时间**：
- 单镜头项目：< 10 秒
- 多镜头项目：< 60 秒

**渲染时间**：
- 4K 单帧 Roto：< 0.5 秒
- 4K 单帧 AI Roto：< 2 秒

---

## 五、版本管理规范

### 5.1 版本号规则

**格式**：`v[主版本].[次版本].[修订号]`

**示例**：
- `v1.0.0`：首次发布
- `v1.1.0`：新增功能
- `v1.0.1`：Bug 修复
- `v2.0.0`：重大更新

### 5.2 镜头版本管理

**版本递增规则**：
- `v001`：初版
- `v002`：QC 后修改
- `v003`：再次修改
- ...
- `final_v001`：最终版

**版本保留**：
- 保留所有历史版本
- 最终版本标记为 `final`
- 备份至归档存储

### 5.3 Git 与 Silhouette

Silhouette 项目文件（.sfx）是二进制格式，不适合 Git 直接管理。推荐方案：

**方案一：Git LFS**
```bash
git lfs install
git lfs track "*.sfx"
git lfs track "*.exr"
git add .gitattributes
```

**方案二：版本文件夹**
```
project/
├── v001/
│   └── shot.sfx
├── v002/
│   └── shot.sfx
└── current → v002/  (符号链接)
```

**方案三：Perforce/Helix Core**
- 适合大型工作室
- 支持二进制文件版本管理
- 支持文件锁定

### 5.4 命名冲突解决

**规则**：
- 同一镜头同一任务不允许同时有两个艺术家编辑
- 编辑前先 "Check Out"
- 完成后 "Check In"
- 冲突时由 Lead 协调

---

## 六、色彩管理标准

### 6.1 ACES 工作流

Silhouette 2026 全面支持 ACES 色彩管理：

```
拍摄（Log）→ IDT（输入变换）→ ACEScg（工作空间）→ ODT（输出变换）→ 显示
```

**配置**：
```python
from fx import *

proj = activeProject()
color = proj.property("colorManagement")

# 启用 ACES
color.setValue("enabled", True)
color.setValue("config", "ACES 1.3")

# 设置工作空间
color.setValue("workingSpace", "ACEScg")

# 设置显示变换
color.setValue("display", "sRGB")
color.setValue("view", "ACES 1.0 SDR-Video")
```

### 6.2 色彩空间标记

**EXR 头部必须包含**：
- `chromaticities`：色彩原色
- `whitePoint`：白点
- `adoptedNeutral`：适应中性
- `acesImageContainerFlag`：ACES 标记
- `colorSpace`：色彩空间名称

### 6.3 多显示输出

| 显示设备 | 色彩空间 | 传输特性 |
|---------|---------|---------|
| sRGB 显示器 | sRGB | sRGB Gamma |
| Rec.709 显示器 | Rec.709 | Rec.709 Gamma |
| HDR 显示器 | Rec.2020 | PQ / HLG |
| DCI 影院 | P3 D65 | Gamma 2.6 |

---

## 七、元数据规范

### 7.1 EXR 元数据

**必需元数据**：
| 字段 | 说明 | 示例 |
|------|------|------|
| `shotName` | 镜头名称 | AVTR_SEQ010_SH0140 |
| `version` | 版本号 | v003 |
| `artist` | 艺术家 | Zhang San |
| `date` | 创建日期 | 2026-07-11 |
| `frameRate` | 帧率 | 24.0 |
| `colorSpace` | 色彩空间 | ACEScg |
| `task` | 任务类型 | roto |
| `comment` | 备注 | Initial version |

### 7.2 通过脚本写入元数据

```python
from fx import *

session = activeSession()
out = session.node("OutputNode")

# 设置 EXR 元数据
meta = out.property("exrMetadata")
meta.setValue("shotName", "AVTR_SEQ010_SH0140")
meta.setValue("version", "v003")
meta.setValue("artist", "Zhang San")
meta.setValue("date", "2026-07-11")
meta.setValue("colorSpace", "ACEScg")
meta.setValue("task", "roto")
```

---

## 八、合规与安全

### 8.1 版权与水印

**预览交付**：
- 添加不可见水印（数字水印）
- 添加可见水印（如 "PREVIEW - NOT FINAL"）
- 限制分辨率（如 720p）

**最终交付**：
- 移除所有水印
- 添加版权元数据
- 加密传输

### 8.2 数据安全

**存储安全**：
- 项目文件加密存储
- 访问权限控制
- 操作日志记录
- 定期备份

**传输安全**：
- 使用加密协议（SFTP/HTTPS）
- 校验文件完整性（MD5/SHA256）
- 传输日志记录

### 8.3 NDA 与保密

- 所有项目文件标注 "CONFIDENTIAL"
- 限制外部访问
- 项目完成后销毁本地副本
- 遵守 NDA 协议

---

## 九、总结

行业标准与质量规范是 VFX 项目成功交付的基础。Silhouette 项目应严格遵循：

1. **格式标准**：使用行业通用格式（EXR/ACES）
2. **命名规范**：统一命名便于管理
3. **QC 流程**：三层 QC 确保质量
4. **版本管理**：清晰的版本追溯
5. **色彩管理**：全程 ACES 管线
6. **元数据完整**：便于追踪与管理
7. **合规安全**：保护客户资产

---

> 相关文档：
> - [[Silhouette 在影视特效中的应用研究]]
> - [[Silhouette 项目管理最佳实践]]
> - [[Silhouette 团队协作工作流]]
