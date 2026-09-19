# MasterCut Quick Start（5 分钟上手）

> MasterCut 是一套 **AE 深度集成**的 AI 视频生产管线：从 BGM + 素材出发，
> 一条命令产出带节奏编排、音效、调色与质量闸门的成片。
> 本文是上手最短路径；深入文档见 `docs/` 与 `02-开发文档/`。

---

## 1. 环境要求

| 项 | 要求 | 说明 |
|----|------|------|
| Python | 3.11 / 3.12 | 系统 3.13 超出 `requires-python`；用 `.venv` |
| ffmpeg | 在 `C:\ffmpeg\bin` 或 PATH | 渲染/探测依赖 |
| 显卡 | ≥8GB 显存（RTX 4060 已验证） | 评分/VLM/生成模型均 8GB 内可跑 |
| AE | 2025 (25.x) 或 2026 | 仅 AE 精修通道需要；纯管线可跳过（`MASTER_NO_AE_CHANNEL=1`） |

## 2. 安装（约 6 分钟）

```bash
# 1) 虚拟环境（uv 最快；pip 亦可）
uv venv --python 3.11 .venv
uv pip install -r requirements.txt

# 2) 重型 ML 依赖（评分/VLM/检索；首次建议夜间下）
uv pip install -r requirements-ml.txt

# 3) 离线模式（可选，避免联网重试拖慢）
#    HF 权重已在 D:/hf_cache/hub；模型走镜像时可设：
export HF_HUB_CACHE=D:/hf_cache/hub
export HF_ENDPOINT=https://hf-mirror.com   # 仅下载时需要
```

> 灾备基线：干净机器重建核心依赖 **6 分 10 秒**（49 项一次成功，实测）。

## 3. 第一条片子

```bash
# 最小调用：只需给 BGM，素材用内置池（13 部）
.venv/Scripts/python.exe scripts/unified_edit.py \
    --bgm "D:/AE-Work/音频素材库/BGM/1_from10s.mp3" \
    --duration 20 \
    --tag my_first

# 指定素材与风格（可选）
.venv/Scripts/python.exe scripts/unified_edit.py \
    --bgm <BGM.mp3> --sources <素材1.mp4> <素材2.mp4> \
    --style emotional_lyric \   # 风格卡见 data/style_cards/
    --theme "浴火重生" \         # 叙事主题（可选，走 LLM 分镜）
    --duration 30 --tag my_run
```

**产出**（`output/unified_<tag>/`）：

```
my_first_cut.mp4            # ① 编排渲染（切点/变速/转场）
my_first_lut.mp4            # + ② LUT 调色
my_first_final.mp4          # + ③ SFX 音效层
my_first_final_mastered.mp4 # + ④ 音频母带（-14 LUFS 交付口径）★最终成品
edl.json / decision_log.md  # 编辑决策清单与决策日志（可审计）
unified_report.json         # 全链报告（评分/闸门/自检结论）
```

## 4. 质量保障（自动执行，无需配置）

出片过程中自动跑四道检查，结论全部落盘：

| 检查 | 脚本 | 通过标准 |
|------|------|---------|
| 音频母带 | `scripts/master_deliver.py` | -14 LUFS / 真峰值 ≤-1.5 dBTP |
| 交付规格 | `scripts/check_delivery_spec.py` | 码率≈4Mbps/≤30fps/8bit（AKROSS 口径） |
| 切点自检 | `scripts/cutpoint_selfeval.py` | 无 frozen_cut/爆音（逐刀检测） |
| 成片评分 | `core/cnn_scorer.py` | 7 维语义分（0-10） |

**手动复检**（任意成片）：

```bash
python scripts/check_delivery_spec.py output/unified_my_first/*.mp4 --min-duration 15 --summary
python scripts/cut_visibility_v2.py --video output/unified_my_first/my_first_final_mastered.mp4
python scripts/cost_report.py                 # 成本汇总
```

## 5. 按需能力（开关式，默认关）

| 能力 | 开启方式 | 用途 |
|------|---------|------|
| 素材检索升级 | `AEKV_NORM_API=1` | 自然语言查素材（held-out R@10 1.000） |
| AE 精修通道 | 默认开；`MASTER_NO_AE_CHANNEL=1` 关 | AE 内特效/文字（需 Bridge） |
| 本地生成空镜 | ComfyUI + `scripts/r5_i2v_generate.py` | 2s 插入镜头（8GB 内跑 14B I2V） |
| 规则适用域 | 自动（按 style/duration 过滤） | 规则库不跨风格误注入 |

## 6. 目录速览

```
core/       引擎与能力（切点/音效/评分/闸门…）
ai/         编排与模型层（production_director 为引擎入口）
scripts/    工具脚本（unified_edit 为唯一编排入口）
tests/      5,500+ 用例（pytest）
data/       规则库/参照集/风格卡/演化数据
knowledge/  知识库加载层；各编号目录为知识库正文
output/     产物（每个 run 一个目录，含报告与决策日志）
docs/       文档（交接/指南）
```

## 7. 常见问题

**Q: 首次跑报 `open_clip` / `torchaudio` 版本问题？**
A: 用 `requirements-ml.txt` 完整安装；torchaudio 必须与 torch 同版本（如 torch 2.9.0 ↔ torchaudio 2.9.0+cu126）。

**Q: 没有 AE 也想出片？**
A: 加 `MASTER_NO_AE_CHANNEL=1`，全链跳过 AE 精修（本机实测 608s 出完整片）。

**Q: 想换 BGM 自动出片？**
A: 直接换 `--bgm` 路径即可；节拍分析自动适配任意 BPM（含慢歌）。

**Q: 产物太大？**
A: 母带后跑交付转码：`python scripts/master_deliver.py --in <成片> --mode delivery --bitrate 4`（15MB/30s 级）。

**Q: 评分器不可用（缺模型）？**
A: 评分自动降级跳过，不影响出片；补齐 `requirements-ml.txt` 后恢复。

---

*更系统的说明见 `README.md`；生产运维（DVC/CI/闸门纪律）见 `08-安装与部署/`。*
