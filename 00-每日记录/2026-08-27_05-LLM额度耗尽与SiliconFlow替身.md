
## 五、统一编排入口（2026-09-01, 回应用户"每次自动启用全部能力"）

**`scripts/unified_edit.py`** — 一次调用串起全链能力:
```
① 素材运镜标注 (CNN+VLM 分层, 7/7 成功 — 训练成果首次接入出片流程)
② V23 编排引擎 (BGM 节拍+高光分配+变速+品味卡 — 4075s 出 115MB 成片)
③ 质感管线 (LUT+SFX)
④ 成片评分 (CNN 标定后 hybrid)
```

**首次全链结果** (`output/unified_first/`):
- 运镜标签 7/7（zoom_in/out + 置信度 — source=videomae-lora-fine LoRA 分类器!）
- 成片 19.3s：dynamism 7.75(+0.27超人工) / overall 7.13(+0.22) / pacing 7.49(+0.23) / texture 5.23(+0.39)
- 零黑帧

**修复的三个断点（本轮）**:
1. `resources/` 目录整体丢失（LUT/SFX/贴图索引全指向它）→ junction 重链
   `D:\AE-Work\resources` + 重建 sfx/fx_assets 索引（SFX 池 8672 扫描）
2. bnb 未装主 python → 4bit 加载失败链崩溃 → pip 装 bitsandbytes 0.50.2（38s/6.25GB）
3. 121MB 大文件 LUT 超时 → 先压 12MB 再挂质感；cnn 头/标定丢失 → 重训+重标定

**已知问题（诚实）**: 统一入口的 LUT/SFX/评分在首跑中 SKIP（大文件超时+头丢失），
本轮手工补齐。unified_edit.py 需要把"先压缩再挂质感"和"评分头自检"固化进脚本。
SFX 仍用均匀假拍 — 接真实节拍（引擎 decision log 里有切点时间）是下一个改进点。

## 六、BGM 丢失事故与修复（2026-09-01 夜, 用户"没bgm了"反馈）

**根因链**:
1. V23 引擎出片自带 BGM（unified_first.mp4 有音轨 -12.5dB）
2. `transcode_with_lut` 内部 **`-an` 剥掉了音轨** → first_lut.mp4 无声
3. SFX 混音在无声底上 → final 只剩音效无 BGM

**修复（已固化进 unified_edit.py）**:
- LUT 改 `-vf lut3d` + **`-c:a copy` 保音轨**；大文件(>50MB)先压再挂
- SFX 分批直混（每批 14 个）：`[0:a]+音效 amix=inputs=N+1`（amix inputs 计数坑：
  BGM+N 音效 = N+1 输入，写成 N 会报 label 过多）
- 修复版成片: `output/unified_first/first_final2.mp4`（BGM+27 音效，-10.8dB，已打开验证）

**教训**: 每段管线动音频流时必须显式声明音轨策略（copy/重编码/剥离），默认 -an 是静默杀手。
