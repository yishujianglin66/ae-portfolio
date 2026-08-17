# 交接文档 — M2 视觉评估闭环 / 调参器体系（2026-08-16 终态）

> 交接目的：另一程序/AI 接手继续推进。本文档是唯一权威交接源，与
> `docs/research/2026-08-16-cnn-param-tuner-foundation.md`（563 行详细科研日志）配套。
> 先读本文档的"防重复清单"和"数据卫生铁律"再动手。

---

## 一、项目背景（30 秒版）

AE-Knowledge-Vault：AE（After Effects 2025）自动合成/漫剪 AI 管线。
当前主线是 **M2 视觉评估闭环**：渲染成片 → 视觉评分（qwen-vl-max / 本地 CNN）→
按评分迭代合成参数 → 重渲染，直到达标。调参器体系包含三个模型：
**qwen**（API 评分，真值来源）、**CNN**（CLIP 帧嵌入 + Ridge 头，本地实时）、
**GBDT**（参数数值 → 评分）。生产闭环入口 `scripts/m2_auto_iterate.py --scorer hybrid`。

---

## 二、这两天完成的全部任务（按时间序，勿重复执行）

### 第一天（2026-08-15 ~ 16 上午，前一会话）
1. ✅ 评分粒度修复：qwen prompt 改"一位小数 0-10"→ 连续标签（整数 3 档是假完美）
2. ✅ Windows 死代理根因修复：注册表残留 `127.0.0.1:7897`，DashScope 改 `ProxyHandler({})` 直连（已固化在 `core/visual_scorer.py`）
3. ✅ 采集脚本健壮性：唯一文件名（防 avi 句柄冲突）+ 评分失败重试 3 次
4. ✅ 100 带帧样本采集达标 + GBDT 重训 + LOOCV 揭示真实能力（dynamism 方向一致 0.64）

### 第二天（本会话）
5. ✅ **CNN 评分头训练落地**（详见科研日志 §"CNN 评分头 LOOCV 评测"）：
   - `scripts/encode_tuning_frames.py`：open_clip ViT-L-14（本地权重离线）编码帧 → 768 维嵌入固化
   - `scripts/train_cnn_param_head.py`：Ridge + MLP 双头 LOOCV
6. ✅ **数据污染审计与修复**（§"数据质量审计与干净重训"）：
   - 发现 100 带帧样本仅 58 唯一帧目录，48 样本共享 6 个旧 `sample_*` 目录（帧↔参数错位）
   - `collect_tuning_data.py` 修复为 `run_id` 唯一命名 + 目录存在断言
   - 干净索引 `data/param_tuning/clean_index.json`
7. ✅ **CNN 生产接入**（§"CNN 评分头生产接入"）：
   - `core/cnn_scorer.py`：local / hybrid / qwen 三模式评分
   - `m2_auto_iterate.py` 加 `--scorer` 开关；数据卫生：仅 qwen 模式写真值库
   - 修 3 个 bug：临时目录竞态、键名前缀错位（qwen 无前缀 vs CNN 带前缀）、训练样本双前缀
   - 真机验收：hybrid 评分 → texture 选中 → qwen 解析 3 动作 → 应用 → 重渲染 → 落盘
8. ✅ **方法论落地**（§"方法论落地"）：
   - OpenSeeker-v2 精选小数据 → `scripts/build_gold_set.py`（四维信息量筛黄金候选）
   - OmniScientist 感知反向驱动 → `scripts/style_card_compliance.py`（风格卡达标度自检，实测 amv_highenergy 产出 boost_motion + tighten_beat）
9. ✅ **黄金集 + 标定 + 回归**（§"黄金集基准评测"、"cnn 黄金标定与基准回归"）：
   - `scripts/calibrate_gold_set.py` 校准 20 条专家标签
   - `scripts/eval_gold_benchmark.py` 基准评测（cnn 标定后 MAE 0.14 反超 qwen 0.18）
   - `scripts/calibrate_cnn_head.py` 线性标定（LOOCV ≥10% 改善才写入，实测 34.9%）
   - `tests/test_gold_benchmark.py` 回归守卫 3 条（标定存在 / MAE≤0.20 / 方向一致≥0.75）
10. ✅ **黄金集扩到 50 条**：`build_gold_set.py --offset` 增量筛选 + 校准合并
11. ✅ **hybrid 混合策略升级**：cnn 管 5 维（dynamism/text_read/texture/pacing/overall）+ qwen 管 2 维（composition/color_harmony），每轮 qwen 调用减半
12. ✅ **后台采集 52→100 干净样本**（约 100 分钟，`collect_until_n.py`）：
    - `count_samples()` 改为统计唯一帧目录（干净数）
    - 修复 `run_id` NameError（编辑误删定义，已补回）
    - GBDT 自动重训（160 总样本）
13. ✅ **采集后全链刷新**：重建 clean_index（100）→ 重编码 100 嵌入 → 重训 CNN 头
14. ✅ **黄金集 id→样本漂移事故修复**（§"黄金集 id→样本漂移事故"）：
    - 重筛（新头+新池）改变排名，按 id 绑定的标签错位（抽检 6 条 5 条错位）
    - 症状：标定改善 30%→1.9%
    - 修复：`calibrate_gold_set.py` 改**签名匹配**（params 六元组 + qwen 七维分数唯一定位样本）
    - 50/50 唯一匹配，标定恢复 30% 有效
15. ✅ **终局基准 + LOOCV + 回归 + 落盘**（§"100 干净样本 + 黄金集对齐事故修复"）

---

## 三、当前权威数字（终态，勿用旧数字）

### 黄金基准（50 条专家标签，2026-08-16 终轮）
| 模型 | 平均 MAE | 平均方向一致 |
|---|---|---|
| **cnn(标定后)** | **0.14** | **0.84** |
| gbdt(160 样本) | 0.16 | 0.79 |
| qwen | 0.25 | 0.73 |

cnn 赢 4 维（dynamism/composition/color_harmony/pacing），gbdt 赢 3 维（text_read/texture/overall），qwen 全面第三（极端组合偏乐观）。
⚠ 诚实边界：黄金样本在 CNN 头的 100 训练样本内（in-sample 偏乐观）；LOOCV 是出样保守界。

### 100 干净样本 Ridge LOOCV（出样真实泛化）
dynamism 0.88 / overall 0.83 / pacing 0.77 / composition 0.70 / text_read 0.67 / texture 0.61 / color_harmony 0.32（不可学）

---

## 四、资产清单（全部位置）

### 模型（models/output/）
| 文件 | 内容 | 状态 |
|---|---|---|
| `cnn_param_head.pkl` | Ridge 头（100 干净样本）+ 黄金标定参数 | ✅ 生产头，推理自动应用标定 |
| `param_tuner.pkl` | GBDT 7 目标（160 总样本） | ✅ ⚠ 含 48 条污染行（见遗留任务#4） |

### 数据
| 路径 | 内容 |
|---|---|
| `output/m2_iteration/train_samples.jsonl` | 训练真值库，160 行（100 干净 + 48 污染 + 12 无帧） |
| `data/param_tuning/clean_index.json` | **干净样本权威索引**（100 行号，基于唯一帧目录） |
| `data/param_tuning/frames/{run_id}_{n}/` | 帧库（每样本 4 帧）；`sample_*` 前缀 = 污染勿用 |
| `data/param_tuning/clip_vitl14_emb.npz` | 100×768 CLIP 嵌入（与 clean_index 对齐） |
| `output/m2_iteration/gold_set.jsonl` | **黄金集 50 条**（签名对齐 + 三方预测 + gold_label + gold_note） |
| `output/m2_iteration/gold_candidates.jsonl` | ⚠ 已废弃（漂移重筛产物）；权威重建走 `calibrate_gold_set.py` |
| `output/m2_iteration/train_samples_hybrid.jsonl` | hybrid 迭代数据（与真值库分离） |
| `output/m2_iteration/style_compliance.json` | 风格卡达标度报告（amv_highenergy 实测） |

### 代码（本会话新增/修改）
| 文件 | 作用 | 关键注意 |
|---|---|---|
| `core/cnn_scorer.py` | 本地/hybrid 评分模块 | `--train` 全量训头；`_pred_to_scores` 自动应用标定 |
| `core/visual_scorer.py` | qwen 评分真值源 | 死代理直连已固化；勿改缓存 key（完整哈希） |
| `scripts/encode_tuning_frames.py` | 帧→嵌入固化 | `--clean` 只编码干净样本 |
| `scripts/train_cnn_param_head.py` | Ridge/MLP LOOCV 评测 | 表内 GBDT 对照列是旧数字，以黄金基准为准 |
| `scripts/build_gold_set.py` | 黄金候选筛选 | `--offset` 增量；输出仅供人工审阅 |
| `scripts/calibrate_gold_set.py` | **签名匹配版黄金集重建** | 50 条标签内嵌 GOLD dict（含 qwen 签名）；权威路径 |
| `scripts/calibrate_cnn_head.py` | CNN 黄金标定 | LOOCV ≥10% 才 `--write` |
| `scripts/eval_gold_benchmark.py` | 黄金基准评测 | cnn 列实时重预测（含标定） |
| `scripts/style_card_compliance.py` | 风格卡达标度自检 | 感知→旋钮→偏差→修正动作 |
| `scripts/collect_tuning_data.py` | 参数网格采集 | run_id 唯一命名 + 存在断言（勿删） |
| `scripts/collect_until_n.py` | 无人值守采集循环 | count_samples = 唯一帧目录数 |
| `scripts/m2_auto_iterate.py` | 迭代闭环主入口 | `--scorer local\|hybrid\|qwen`；数据分离逻辑勿破坏 |
| `tests/test_gold_benchmark.py` | 回归守卫 3 条 | MAE≤0.20 / 方向≥0.75 / 标定存在 |

### 文档（录到哪里）
- **主科研日志**：`docs/research/2026-08-16-cnn-param-tuner-foundation.md`（563 行，本两天全部实验/结论/事故的详细记录，按章节追加）
- 风格卡：`data/style_cards/*.json`（8 张）+ `knowledge/style_card.py` + `ai/taste_contract.py`
- 更早的 M2/调参器历史：`docs/research/` 目录下 2026-08-13~15 各文件

---

## 五、数据卫生铁律（违反必出对齐事故）

1. **帧目录 1:1**：帧目录必须含 run_id 前缀且唯一，`collect_tuning_data.py` 的存在断言勿删。`sample_*` 前缀目录 = 历史污染，永远排除。
2. **真值库只进 qwen 数据**：只有 `--scorer qwen` 模式才追加 `train_samples.jsonl`；local/hybrid 写 `train_samples_{mode}.jsonl`。CNN 吃自己预测的标签 = 自举污染。
3. **黄金标签按内容签名绑定**（params 六元组 + qwen 七维分数），**绝不按排名 id**——重筛/重训后排名必变，id 绑定 = 标签错位（本会话事故#2）。重建黄金集一律跑 `python scripts/calibrate_gold_set.py`。
4. **标定写入门槛**：`calibrate_cnn_head.py` 无 `--write` 只验证；LOOCV 改善 <10% 不写。
5. **改模型/数据后必跑**：`pytest tests/test_gold_benchmark.py`（3 条守卫）+ `python scripts/eval_gold_benchmark.py`。
6. **干净样本判定**：以 `clean_index.json` 为准；重新生成逻辑 = 帧目录唯一 且 非 `sample_*` 前缀。

---

## 六、已证伪/已定论的方向（勿重试）

| 结论 | 证据 | 处置 |
|---|---|---|
| color_harmony 不可自动学习 | 合成画面 qwen 全评 ~8（标签天花板）；干净数据 LOOCV 0.21-0.32，Spearman 为负 | 已移出自动迭代，默认达标 |
| 整数标签 = 假完美 | 3 档低方差，GBDT 记忆即"完美"（0.90 方向一致）无泛化 | 一律小数标签 |
| pacing 不再需要序列模型 | CNN 帧嵌入学到了（LOOCV 0.77） | 保持 CNN 管 |
| GBDT 管 text_read 有优势 | 参数映射维（字号→可读） | 保持 |
| timm 工厂加载本地 CLIP | 会走网络/格式不匹配报错 | 用 `open_clip.create_model_and_transforms('ViT-L-14', pretrained=<本地ckpt路径>)` |
| HuggingFace 在线下载 | 本环境 httpx 异常，不可用 | 一律本地权重离线 |

**环境注意**：Windows 死代理已根治于代码层（DashScope 直连）；AE 是 2025 版（经 `.ae-mcp-bridge/` 文件轮询桥接 + aerender + ffmpeg 转码）。

---

## 七、遗留任务（接手即做清单，按优先级）

1. **真出样评测**：重训一个"排除黄金 50 条样本"的 CNN 头 → 黄金基准测出样 MAE（消除 in-sample 偏乐观）。做完可更新 `CONFIDENT_DIMS` 归属。
2. **GBDT 去污染重训**：当前 GBDT 是 160 行（含 48 条帧错位污染行——参数记录与实际渲染不符）。用 clean_index 的 100 行重训 `train_param_tuner.py`，黄金基准复测。
3. **param_recommend.py 升级**：仍用旧 GBDT 网格。可改为 CNN(+标定) 打分候选组合（渲染候选帧再评分，或直接 GBDT 初筛+CNN 精排）。
4. **达标度自检接进迭代闭环**：`style_card_compliance.py` 目前独立运行；可作为 `m2_auto_iterate` 每轮校验（渲染后查旋钮偏差，与 pick_target_dim 融合）。
5. **黄金集扩到 100+**：需要人工校准新候选（方法见 `calibrate_gold_set.py` 头部注释与科研日志校准规则节）；新采集样本先跑 `build_gold_set.py --offset 50 --clean` 生成候选清单。
6. **参数空间扩展**：GRID 目前 6 参数（psize/chroma/punch/shake/glow/text_size）；可加 tint 配色、粒子模板、glow 半径等，采集新维度数据。
7. **回到多段成片主线**：调参器已生产就绪，下一步是 intro/build/drop/outro 多段编排 + 逐段 hybrid 评分的完整成片闭环。

---

## 八、快速验证命令（接手后先跑一遍确认环境完好）

```bash
# 1. 回归守卫（应 3 passed）
python -m pytest tests/test_gold_benchmark.py -q

# 2. 黄金基准（cnn 应 MAE 0.14 / 方向 0.84 排第一）
python scripts/eval_gold_benchmark.py

# 3. 干净样本计数（应 100）
python -c "import sys; sys.path.insert(0,'.'); from scripts.collect_until_n import count_samples; print(count_samples())"

# 4. 本地评分冒烟（应秒级出 7 维分数，需 GPU 加载 CLIP ~30s）
python -m core.cnn_scorer --video output/m2_iteration/round4.mp4 --mode local

# 5. 黄金集重建（应 50 条，无未匹配告警）
python scripts/calibrate_gold_set.py
```

---

## 九、Git 状态提醒

分支 `feat/project-consolidation-v1`。本会话新增/修改的上述脚本、`core/cnn_scorer.py`、`tests/test_gold_benchmark.py`、科研日志均**未提交**（含会话开始前既有的未提交改动）。接手者若要提交，先 `git status` 全览再分组提交，勿混入无关文件。

---

## 十、一句话总结

CNN 深度调参器已生产化（本地实时、黄金标定后 MAE 0.14 全场第一），黄金集 50 条签名对齐、回归守卫就位，100 干净样本；两起数据对齐事故（帧目录覆盖写、黄金标签 id 漂移）均已根治并沉淀为铁律；遗留 7 项任务按优先级排列，先做出样评测和 GBDT 去污染。

---

# 交接附录 B — 资源接入轮（2026-08-17 凌晨, 本附录为最新状态, 覆盖上文冲突处）

## 本轮新增（全部真机验证）
1. **LUT 管线**: core/lut_pipeline.py（ffmpeg lut3d+blend 强度, 像素级线性验证）;
   41 主题/3317 去重/492 采样池; GRID + 8 风格卡 lut 字段; **color_harmony 标签解锁实证**
   （LUT 样本 std 0.68 vs 天花板 0）; AE 内 Lumetri LUT 参数脚本化会弹 UI 卡死（已证伪）
2. **SFX 层**: core/sfx_layer.py + 四池 40×4; kick→Hit/snare→Whoosh 语义映射;
   落点验证 kick 时窗 -14.2dB vs 尾段 -19.2dB
3. **特效贴图**: core/image_fx.py + 14 类 420 张; BEAT_FX_MAP 撞拍图层
4. **字体池**: 69 候选索引（data/fonts/pool_extension.json）
5. **人工作品标尺**: 9 部成品评分（data/benchmarks/human_benchmark.json）
6. **风格视觉锚**: 4 组 CLIP 质心（data/style_cards_visual_anchor.json, 真实素材帧）
7. **端到端大验收**: output/grand_finale/finale.mp4 — 7 层(3 贴图撞拍)+好莱坞 LUT 0.7+3 SFX,
   **7/7 维 ≥ 人工均值**（color_harmony +0.03~+1.45）
8. 人工工程挖掘: 方法已建（mine_human_projects.py）, 受阻于缺字体弹窗+监听器长命令断
   （解法见 resource-module-mapping.md 稳定性手册）

## ⚠ 数据位置变更（重要! 2026-08-17 03:00 事故后迁居）
- 训练数据新家: `data/param_tuning/train_samples.jsonl`（旧 output/m2_iteration 已废）
- 黄金集: `data/param_tuning/gold_set.jsonl`（50 条标签保全, frame_dir 待签名自愈）
- 标尺: `data/benchmarks/human_benchmark.json`
- 事故: 计划清理任务删了旧目录; 已加 NEVER_DELETE + 迁 data 根治
- **明早 9 点验收前**: 采集达 100 后跑 `python scripts/morning_pipeline.py`
  （重建索引→重编码→重训 CNN→黄金签名自愈→重标定→基准→回归, 一条命令）

## AE 稳定性（今晚血泪, 必读）
- 冷启动 5-8 分钟勿杀; 215MB 无标题卡 → **AppActivate+ESC/Enter 唤醒**（通用）
- Boris FX 弹窗 → ESC+Enter; 监听器长命令后断 → ping 探活+重启
- ping 协议: `AECommandClient(timeout=50).send_command('ping', {})`

## 快速验证命令（更新版）
```bash
python -m pytest tests/test_gold_benchmark.py -q          # 回归 (黄金自愈+重标定后才全 pass)
python scripts/morning_pipeline.py                        # 采集完成后的全链
python scripts/grand_finale.py                            # 复跑端到端验收
python -m core.cnn_scorer --video output/grand_finale/finale.mp4 --mode local
```


# 交接附录 C — 参考片逆向复刻（2026-08-17 晨, 当前最新主线能力）

**用户核心需求已落地**: 给任意顶尖漫剪参考 → 自动推理剪辑技巧 → 资源库选资产 → 复刻呈现。
- `core/reference_analyzer.py`: analyze_reference(视频)→画像; profile_to_params(画像)→参数
- `scripts/replicate_reference.py --ref <参考.mp4> --tag <名>`: 一条命令端到端
- 双参考真机验证通过 (独自升级 -0.17 / 美人鱼 -0.35 overall 差距)
- 画像→资源: LUT 41 主题/贴图 14 类/SFX 四池/字号, 全部走索引防错位
- 下一步方向: 画像与 M2 迭代闭环融合 (复刻→评分→向参考分逼近的自动调参);
  多参考聚类成"风格卡自动生成" (顶尖作品 → 新风格卡)

---

# 交接附录 D — 最终状态总览（2026-08-17 11:00, 本附录为唯一最新权威, 覆盖 A/B/C 冲突处）

> 接手的程序：先读本附录，再按需读附录 B/C 与三份科研日志。所有"以何为准"以本附录为准。

---

## 一、用户当前核心需求（一切工作的准绳）

> "达到外网漫剪顶尖水平 / 给一个参考视频能推理出剪辑技巧并复刻呈现 / 合理运用资源库素材"

**已实现链路**：参考片 → qwen 技巧画像 → 参数映射 → 资源库选资产（LUT/贴图/SFX/字体）→ 新素材渲染复刻 → 双评分对比。
**当前卡点**：多镜头剪辑的层窗口 bug（已修复验证，待完整重跑）。

---

## 二、这两天全部任务清单（按时间序，标✅=已完成并验证，⚠=有状态说明）

### 8-16 白天（M2 调参器/视觉评估闭环轮）
- ✅ CNN 深度调参器：CLIP ViT-L-14 编码帧→Ridge 头，LOOCV dynamism 0.88/overall 0.83
- ✅ 黄金集 50 条（专家标签）+ 签名匹配重建 + 回归守卫 test_gold_benchmark.py
- ✅ cnn 黄金标定（斜率门槛 ≥0.5 防语义演化反转）
- ✅ 数据污染审计：48 样本共享帧目录→clean_index 干净样本机制

### 8-17 凌晨（资源接入轮 + 清理事故 + 复刻管线）
- ✅ **LUT 管线**（core/lut_pipeline.py）：41 主题/3317 去重/采样池 492；ffmpeg lut3d+blend 强度（像素级线性验证）；风格卡 lut 字段；GRID 采集；**color_harmony 标签解锁**（std 0→0.68）
- ✅ **SFX 音效层**（core/sfx_layer.py）：四池 40×4（impact/whoosh/riser/glitch）；kick→Hit/snare→Whoosh 语义映射；落点声学验证
- ✅ **特效贴图层**（core/image_fx.py）：14 类 420 张；BEAT_FX_MAP 撞拍
- ✅ **字体池**（scripts/extend_font_pool.py）：69 候选索引
- ✅ **人工作品标尺**（scripts/human_benchmark.py）：9 部成品评分
- ✅ **风格视觉锚**（data/style_cards_visual_anchor.json）：4 组 CLIP 质心
- ✅ **端到端大验收**（output/grand_finale/finale.mp4）：7/7 维≥人工标尺（color_harmony +1.45）
- ✅ **03:00 清理事故根治**：计划任务删了 output/m2_iteration 训练数据 → NEVER_DELETE 白名单 + 数据全链迁 data/param_tuning（12 文件）
- ✅ 通宵采集 100 + 黄金定向补采 40 = **140 干净样本**；黄金 50/50 签名自愈；重标定 25.8%；回归 3/3
- ✅ **参考片逆向复刻**（core/reference_analyzer.py + scripts/replicate_reference.py）：双参考真机验证（独自升级 -0.17 / 美人鱼 -0.35）
- ⚠ 用户批评"差距天差地别" → 诚实自检：单镜头无剪辑（场景切换 0/s vs 参考 0.6/s），视觉AI评"业余/半成品"
- ✅ 多镜头剪辑尝试（scripts/multishot_replica.py）：8 镜头×5 素材

### 8-17 上午（多镜头 bug 调试，进行中）
- ✅ Bug 链路三层定位：
  1. 多镜头同 z_index → JSX 变量名 `layer0` 全撞 → 修唯一 z_index
  2. 中文 AE `typeName` 返回"合成"不是"Composition" → `instanceof CompItem` 修复（这也修好了人工工程挖掘返回 0 合成的旧 bug）
  3. **根因（最小真机实验铁证）**：`inPoint` 在 `outPoint` 之后赋值时，AE 把 outPoint 抬成 `inPoint+原out`（shot1: 2.05→3.05）→ 层互相覆盖、多镜头失效
- ✅ **顺序修复已写入 core/layer_builders.py**（startTime → inPoint → outPoint）
- ✅ **最小验证已通过**（output/minimal_fix.json：out=1.05/2.05/3.05 全部正确）
- ⚠ 完整 multishot 重跑尚未执行（AE 刚恢复）——**接手第一件事**

---

## 三、资产位置总表（全部核实存在）

### 数据（data/，永不被计划清理）
| 路径 | 内容 |
|---|---|
| data/param_tuning/train_samples.jsonl | **140 干净样本**（含 LUT 维度 + 黄金补采） |
| data/param_tuning/gold_set.jsonl | **50 条黄金**（签名自愈 frame_dir 全补全） |
| data/param_tuning/clip_vitl14_emb.npz | 100×768 CLIP 嵌入 |
| data/param_tuning/clean_index.json | 干净样本索引 |
| data/luts/sampling.json | LUT 采样池（41 主题） |
| data/sfx/index.json | 音效四池 |
| data/fx_assets/index.json | 贴图 14 类 420 张 |
| data/fonts/pool_extension.json | 字体 69 候选 |
| data/benchmarks/human_benchmark.json | 人工作品标尺 |
| data/style_cards_visual_anchor.json | 4 组视觉锚质心 |
| data/style_cards/*.json | 8 风格卡（含 lut 字段） |

### 模型（models/output/）
| 文件 | 状态 |
|---|---|
| cnn_param_head.pkl | **n=140, 6 维标定**（color_harmony 因 slope<0.5 合法跳过） |
| param_tuner.pkl | GBDT 140 样本 |

### 成片（output/，**output/m2_iteration 已被清理删除，勿再引用**）
| 成片 | 说明 |
|---|---|
| output/grand_finale/finale.mp4 | 大验收（7 层+LUT+SFX） |
| output/replicate_solo_leveling/replica.mp4 | 独自升级参考复刻 |
| output/replicate_mermaid/replica.mp4 | 美人鱼参考复刻 |
| output/multishot_cut3/cutflow.mp4 | 多镜头尝试第 3 版（未修顺序 bug 前） |

### 代码（本轮核心）
| 文件 | 作用 | 关键注意 |
|---|---|---|
| core/reference_analyzer.py | 参考片→画像→参数 | profile_to_params 映射 |
| scripts/replicate_reference.py | 复刻端到端 | --ref 任意参考.mp4 |
| scripts/multishot_replica.py | 多镜头剪辑 | **USE_RAMPS=False（变速注入按层内时间会错位，待修绝对时间）** |
| core/layer_builders.py | 图层 JSX 生成 | **已修 inPoint/outPoint 顺序** |
| core/lut_pipeline.py / sfx_layer.py / image_fx.py | 三大资产模块 | 全生产 |
| core/render_cleanup.py | 清理器 | 已加 NEVER_DELETE + .jsonl 白名单 |
| scripts/morning_pipeline.py | 晨间全链 | 采集后一条命令 |
| scripts/dialog_guard.ps1 | AE 弹窗看护 | PS1 需 UTF-8 BOM 防中文乱码 |

### 文档（docs/，全部落盘）
| 文档 | 内容 |
|---|---|
| docs/handoff-2026-08-16-m2-tuner.md | **本交接**（附录 D 最新） |
| docs/research/2026-08-16-resource-module-mapping.md | 资源↔模块映射 + 全轮实录 + 诚实自评 + 多镜头调试 |
| docs/research/2026-08-16-cnn-param-tuner-foundation.md | M2 调参器完整科研日志 |

---

## 四、防重复/已证伪清单（勿重做）

| 项 | 结论 |
|---|---|
| AE 内 Lumetri LUT 参数脚本化 | 会弹 UI 卡死，**已证伪**，走 ffmpeg |
| HSV 验证 LUT 强度 | 深色帧 RGB 微偏→S 暴涨假象，**必须用 RGB 像素差** |
| 黄金标签按排名 id 绑定 | 重筛后必漂移，**签名匹配（params+qwen分）** |
| typeName 判合成 | 中文 AE 返回"合成"，**用 instanceof CompItem** |
| inPoint 后于 outPoint 赋值 | AE 抬 out，**顺序必须 start→in→out** |
| color_harmony 自动迭代 | LUT 后语义演化，标定 slope<0.5 跳过，待新黄金标签 |
| 参考片逆向 | **已建成**，勿重建，直接 replicate_reference.py |
| 数据在 output/m2_iteration | **已删**，全在 data/param_tuning |

---

## 五、遗留任务（接手即做，按优先级）

1. **【第一优先】完整重跑多镜头**：`rm -f .ae-mcp-bridge/ae_command.json .ae-mcp-bridge/ae_result.json` + `python scripts/multishot_replica.py --tag cut4` → 用边界帧差判定脚本验证 **7/7 硬切**（>25 阈值）。判定脚本见 resource-module-mapping.md 终章。
2. **开 USE_RAMPS**：speed_ramps 注入是按层内时间的，错峰层（startTime 前移）会错位——需改成绝对时间或逐层偏移，这是下一轮变速增强。
3. **多镜头配画像闭环**：multishot 目前硬编码美人鱼画像，应接 replicate 的 profile（参考→画像→多镜头树）——把"复刻"从单镜头升级为多镜头版。
4. **文字排版系统**：诚实自评第 3 差项——工业粗体 vs 顶尖风格化排版（圆圈边框/手写体/分层字）。
5. **多层特效叠加**：自评第 4 差项——单层贴图 vs 多层光效。
6. **新黄金标签**：LUT 时代 color_harmony 的色彩审美校准（当前该维未标定）。
7. **人工工程挖掘补跑**：mine_human_projects.py 已修 typeName bug，AE 空闲时可跑（每工程弹缺字体对话框→用 dialog_guard）。
8. **监听器长命令断链修复**（工程性）：长命令后 checkForCommands 自调度链断，需心跳自检/重注册兜底。

---

## 六、AE 稳定性手册（必读，全踩过）

| 症状 | 解法 |
|---|---|
| 冷启动慢（322MB 日志+5000 字体） | **等 5-8 分钟勿杀** |
| 215MB 无标题深卡 | **AppActivate 激活 + ESC/Enter 唤醒**（通用） |
| Boris FX Continuum Error 弹窗 | ESC+Enter 关（dialog_guard.ps1 后台看护） |
| prefs 损坏 | 换出 25.3 重建；新 prefs 需 `Pref_SCRIPTING_FILE_NETWORK_SECURITY=1` |
| 监听器断链 | ping 探活：`AECommandClient(timeout=50).send_command('ping', {})` |
| 长命令后死 | 重启 AE + 唤醒法 |
| aerender 正常 GUI 卡 | 引擎无恙，纯 UI 层 |

**重启标准流程**：taskkill AfterFX → 清 ae_command.json/ae_result.json → start AfterFX.exe → 等 5-8 分钟 → 唤醒预案（Boris 判定+AppActivate）→ ping 确认。

---

## 七、快速验证命令（接手先跑确认环境）

```bash
# 1. 回归（应 3 passed）
python -m pytest tests/test_gold_benchmark.py -q
# 2. 黄金基准（cnn MAE 0.15 / 方向 0.81 第一）
python scripts/eval_gold_benchmark.py
# 3. 数据核实（140 样本 / 50 黄金）
wc -l data/param_tuning/train_samples.jsonl data/param_tuning/gold_set.jsonl
# 4. AE 探活
python -c "import sys; sys.path.insert(0,'.'); from ae.ae_command_client import AECommandClient; print(AECommandClient(timeout=50).send_command('ping',{}).get('status'))"
# 5. 最小层窗口验证（应 out=1.05/2.05/3.05 OK）— 脚本在 resource-module-mapping 终章
# 6. 完整多镜头（第一优先遗留）
python scripts/multishot_replica.py --tag cut4
```

---

## 八、Git 状态

分支 `feat/project-consolidation-v1`，**大量改动未提交**（core/layer_builders.py、core/render_cleanup.py、core/synthesis_orchestrator.py、8 风格卡、新增 8 脚本+3 模块+3 文档+数据索引）。接手者若要提交：先 `git status` 全览，按"数据/模型/代码/文档/资源"分组提交，勿混入。

---

## 九、一句话总结

M2 调参器体系（140 样本/黄金 50/标定/回归）与三大资源资产（LUT 41 主题/SFX 四池/贴图 14 类）全部生产就绪；参考片逆向复刻闭环已建成并通过双参考验证；当前唯一卡点"多镜头层窗口 bug"**根因已锁定并修复、最小验证通过**，只差完整重跑确认 7/7 硬切——那是"效果演示器"到"剪辑系统"的最后一步。

---

# 交接附录 E — 复刻/多段轮增量（2026-08-17 19:30，最新权威，覆盖 D 遗留任务）

> 本附录记录：接手程序完成的 8 模块（实验报告 `tmp/实验报告_20260817_详细版.md` 679 行）+ 本程序
> 深挖出的**关键新根因**（JSX 截断 → 多段成片后半黑屏）+ 分批修复现状 + 当前唯一卡点解法。

---

## 一、接手程序已完成（实验报告全录，勿重做）

| 模块 | 结果 | 产物 |
|---|---|---|
| multishot 硬切 | ✅ 7/7 PASS（局部显著性判据 + 变速层时间重构） | output/multishot_cut_ramp3/verify_hard_cuts.json |
| A 真出样评测 | ✅ CNN 排除黄金 50 条重训（90 样本），out-sample MAE 0.250 vs in 0.155（+61% 乐观偏差） | models/output/cnn_param_head_excl_gold.pkl |
| B GBDT 去污染 | ✅ 几乎无偏差（-3%），12 维特征 | models/output/param_tuner_clean.pkl |
| C 两阶段推荐 | ⚠️ GBDT top10→CNN 精排，新参数无方差退化中 | output/m2_iteration/recommend.json |
| D 达标度闭环 | ✅ _apply_compliance_actions() 接入 m2_auto_iterate | scripts/m2_auto_iterate.py（--compliance-gate） |
| E 参数空间扩展 | ✅ FEATURES 9→12（tint/particle/glow_radius），向量化预测 | train_param_tuner.py + param_recommend.py |
| F 多段成片 | ⚠️ 真机渲染完成但**后半黑屏**（本程序新根因，见下） | output/multisegment_finale/seg1~seg3/ |
| AE 桥接恢复 | ✅ `-r start_mcp_listener.jsx` 重启法 | 见附录 D 手册 |

**实验报告**：`tmp/实验报告_20260817_详细版.md`（679 行，13 章+附录，含各模块问题/解法/复现命令）。

---

## 二、本程序新发现（关键！多段成片黑屏根因 + 修复）

### 根因：ExtendScript 单脚本 ~32KB 截断
- **现象**：seg1-3 的 drop(5.2s起)/outro 全黑；texture 增强三招（粒子6/3+LUT 0.6+grain 3层+全屏贴图）评分纹丝不动（5.20→5.21）
- **真因链**：multisegment 树 30 层 → JSX 55033 字符 → **超 ExtendScript ~32KB 上限，后半被静默丢弃** → drop/outro 层从未创建 → 黑屏（评分器抽帧恰好避开，被掩盖）
- **铁证**：`tmp/multisegment_finale.aep` 只含 13 层（intro/build），本地 generate_jsx 却有 30 层
- **修复（已落盘）**：
  1. `core/synthesis_orchestrator.py` 新增 `JsxProjectBuilder.build_batches(tree, max_chars=24000)`——分批 IIFE，首批建 comp，后续批按 comp 名找回继续加层，尾批跑 post_lines
  2. `SynthesisOrchestrator.execute()` 接分批通道：`len(jsx) > 30000` 自动分批
  3. 本地验证：3 批 [24194, 21782, 10243]，30 层全覆盖 ✅

### 当前唯一卡点（接手第一件事）
- **seg4 分批重渲染被损坏 AVI 卡住**：首次超时被杀 → `output/one_pipeline/multisegment_finale.avi`（1GB）损坏且**仍被占用**（aerender 残留句柄，AVI_BUSY）→ ffmpeg 读坏文件静默失败 → render_tree 返回 False
- **解法**：
  ```bash
  taskkill //F //IM aerender.exe   # 杀残留（AVI 占用方）
  sleep 8 && rm -f output/one_pipeline/multisegment_finale.avi
  rm -f .ae-mcp-bridge/ae_command.json .ae-mcp-bridge/ae_result.json
  python scripts/multisegment_finale.py --tag seg4   # 后台无限时跑（渲染 ~7 分钟）
  ```
- **验证标准**：seg4 finale.mp4 全 10s 无黑帧（t=0.5/2/3.5/5.2/6/7/9 亮度 >1）+ texture 应显著 >5.21
- **已知待补**：`scripts/m2_auto_iterate.py` 转码段静默失败路径的打印加固**未落盘**（本程序替换未生效，文件仍是旧版）——接手者顺手补：LUT/ffmpeg 失败时打印 rc+stderr

---

## 三、资产位置（新增，其余见附录 D）

| 路径 | 内容 |
|---|---|
| tmp/实验报告_20260817_详细版.md | 接手程序 8 模块完整实验报告（679 行） |
| models/output/cnn_param_head_excl_gold.pkl | 90 样本出样头（诚实评分用） |
| models/output/param_tuner_clean.pkl | 12 维 GBDT（无偏差） |
| output/multishot_cut_ramp3/verify_hard_cuts.json | 7/7 硬切验证 |
| output/multisegment_finale/seg1~3/finale.mp4 | ⚠️ 后半黑屏版（勿当成果） |
| tmp/multisegment_finale.aep | 黑屏铁证（仅 13 层） |

## 四、防重复/新证伪追加

| 项 | 结论 |
|---|---|
| multishot 7/7 硬切 | ✅ 已验证，勿重跑 |
| 多段成片 texture 增强（粒子/grain/LUT/贴图） | **根因是黑屏不是参数**——修复分批后重新对比才有效 |
| JSX 超 30KB | 必须走 build_batches 分批（ExtendScript ~32KB 截断） |
| AVI 残留 | aerender 句柄未释放 → 杀进程再删 |

## 五、遗留任务（更新版，接附录 D 第 5 节）

1. **【第一优先】清 AVI → 重跑 seg4 → 验证全片无黑帧 + texture 提升**（解法见上）
2. 补 m2_auto_iterate 转码静默失败打印
3. 分批验证通过后，重评 multisegment 真实纹理水平（此前 texture=5.21 是黑屏假象）
4. AE 渲染端接入 tint/particle/glow_radius（报告 E 模块）产生训练方差 → 重训
5. 段级评分（报告 11.2-4）
6. 黄金集 100+（报告 11.2-3）
7. mine_human_projects 重跑（AE 空闲、--max-projects 1）
8. 监听器长命令断链根治（scheduleTask 自调度心跳兜底）

## 六、AE 状态（已核实）

- ping success（19:16:28），监听器活跃
- 三个 AfterFX.com 小进程 = aerender 命令行渲染器残留，AVI 占用方

---

# 交接附录 F — seg4 分批重渲染终验（2026-08-17 21:00，最新状态）

> 本附录覆盖附录 E 中“seg4 清 AVI → 重跑 → 验证”的当前状态。根因结论不变：ExtendScript 单脚本约 32KB 上限导致 30 层 JSX 截断；本附录记录的是清理卡点、无限等待修复、唯一 AVI 路径修复和最终真机验证。

## 一、接手第一优先任务结果

附录 E 原第一优先任务：清理 aerender 残留/损坏 AVI，重跑 `seg4`，验证全片无黑帧和 texture 真值。

结果：✅ 已完成。

- 原损坏文件：`output/one_pipeline/multisegment_finale.avi`，约 1GB，曾被 After Effects 命令行残留句柄占用。
- 目标渲染子进程：`AfterFX.com`，命令行对应 `tmp/multisegment_finale.aep`。
- 初次 `aerender.exe` 名称查询未找到；进一步定位到目标 `AfterFX.com` PID `48304`。
- 进程退出后 Windows 文件句柄仍未立即释放，删除/改名旧 AVI 均被安全删除 shim 或系统句柄拒绝；未强行删除用户证据。
- 后续改用唯一 AVI 路径，绕过旧文件句柄：`multisegment_finale_b975d9c4.avi`。

## 二、本轮新增修复

### 1. AE 分批执行改为无限等待

文件：`core/synthesis_orchestrator.py`

- `AECommandClient(timeout=300)` 改为 `AECommandClient(timeout=None)`。
- 分批 3/3 曾因固定 300 秒超时失败；现在分批命令不会被 300 秒客户端超时截断。

文件：`ae/ae_bridge_base.py`

- `_wait_for_result()` 改为支持：

```python
while self.timeout is None or time.time() - start_time < self.timeout:
```

- `timeout=None` 表示无限等待，保持默认有限超时调用方的旧行为。

### 2. 每次渲染使用唯一 AVI 文件名

文件：`scripts/m2_auto_iterate.py`

- 原固定输出：`output/one_pipeline/multisegment_finale.avi`。
- 新输出：`output/one_pipeline/multisegment_finale_<uuid8>.avi`。
- 目的：绕开 Windows 上旧 AVI 的残留句柄，避免新渲染覆盖失败。

### 3. 转码失败可见化

文件：`scripts/m2_auto_iterate.py`、`core/lut_pipeline.py`

- aerender 缺产物时打印 return code 和 stderr 尾部。
- 普通 ffmpeg 转码改为无限等待，并打印 return code/stderr。
- LUT 转码改为无限等待；失败时记录 ffmpeg return code 和 stderr。
- AVI 清理失败时只打印警告，不阻断已经生成的 MP4。
- 该修复补齐了附录 E 中“`m2_auto_iterate` 转码静默失败打印未落盘”的遗留项。

## 三、seg4 最终执行证据

最终成功运行使用：

```powershell
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe' scripts\multisegment_finale.py --tag seg4
```

执行结果：

- 合成树：30 层
- 镜头：8
- 粒子：11
- 文字：4
- FX：2
- 节拍：11
- JSX：3 批全部成功
- AE 真机渲染：成功
- LUT 转码：`ok=True`
- SFX：11 个落点
- 总耗时：约 2937 秒
- 主渲染阶段耗时：约 2794 秒

最终产物：

- `output/multisegment_finale/seg4/base.mp4`
- `output/multisegment_finale/seg4/finale.mp4`
- `output/multisegment_finale/seg4/report.json`
- `output/multisegment_finale/seg4/tree.json`
- `output/multisegment_finale/seg4/stats.json`

权威报告：`output/multisegment_finale/seg4/report.json`

## 四、无黑帧验证

验证文件：`output/multisegment_finale/seg4/finale.mp4`

视频元数据：

- FPS：30
- 帧数：300
- 时长：10.0 秒

按附录 E 指定时间点采样：`0.5 / 2 / 3.5 / 5.2 / 6 / 7 / 9` 秒。

结果：

| 时间 | 读帧 | 平均 BGR 亮度 | 结论 |
|---:|---:|---:|---|
| 0.5s | 成功 | 43.417 | 非黑 |
| 2.0s | 成功 | 86.840 | 非黑 |
| 3.5s | 成功 | 19.141 | 非黑 |
| 5.2s | 成功 | 13.010 | 非黑 |
| 6.0s | 成功 | 22.324 | 非黑 |
| 7.0s | 成功 | 23.747 | 非黑 |
| 9.0s | 成功 | 16.580 | 非黑 |

结论：7/7 采样点均成功读帧，均未出现后半黑屏。这里的“无黑帧”是指定边界采样验证，不等同于逐帧 300/300 全量亮度扫描；如果需要严格全帧守卫，下一任务应补充逐帧扫描脚本。

## 五、texture 真值

`report.json`：

- `score_texture = 5.07`
- `score_overall = 6.93`
- `score_dynamism = 7.39`
- `score_pacing = 7.31`
- texture 评分来源：CNN
- composition/color harmony 来源：Qwen

重要解释：

- 此次 `5.07` 是分批修复和真实成片无黑屏后的 texture 结果。
- 旧版 `5.20 → 5.21` 不能继续作为 texture 增强证据，因为旧版后半层从未创建，评分抽帧掩盖了黑屏。
- 当前结果没有证明 texture 已达标，只证明黑屏根因已解除并得到真实评分。

## 六、验证命令

### 1. 读取报告

```powershell
Get-Content output/multisegment_finale/seg4/report.json
```

### 2. 视频元数据和边界帧采样

```powershell
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe' -c "import cv2; p=r'output/multisegment_finale/seg4/finale.mp4'; cap=cv2.VideoCapture(p); print(cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT))"
```

### 3. 检查当前渲染代码

```powershell
Select-String -Path core/synthesis_orchestrator.py -Pattern 'AECommandClient\(timeout=None\)'
Select-String -Path ae/ae_bridge_base.py -Pattern 'self.timeout is None'
Select-String -Path scripts/m2_auto_iterate.py -Pattern 'uuid.uuid4|LUT 转码|AVI 清理跳过'
```

## 七、当前遗留任务更新

1. ✅ 清 AVI/规避残留句柄 → 完成唯一 AVI 路径渲染。
2. ✅ 重跑 `seg4` → 3 批 JSX、30 层全覆盖、真机渲染成功。
3. ✅ 验证无黑屏 + texture 真值 → 7/7 边界采样非黑，texture=5.07。
4. ✅ 补 `m2_auto_iterate` 转码静默失败打印 → 已补 return code/stderr 和 LUT 状态打印。
5. ⏳ 分批修复后重新评估 texture → 已取得真实值 5.07；下一步是接入 tint/particle/glow_radius 真机方差并重新训练。
6. ⏳ 段级评分 → 仍未实现，需分别评分 intro/build/drop/outro，定位 texture 低分段。
7. ⏳ 黄金集 100+ → 仍未完成。
8. ⏳ `mine_human_projects.py` 重跑 → 等 AE 空闲后执行，建议 `--max-projects 1`。
9. ⏳ 监听器长命令断链根治 → 仍需 scheduleTask 自调度心跳/重注册兜底。

## 八、当前接手第一件事

本附录的第一优先任务已完成。下一程序不要重复清理或重跑 `seg4`，除非 `finale.mp4` 被明确判定损坏。

建议下一步顺序：

1. 逐帧扫描 `finale.mp4`，建立 300/300 全量非黑守卫。
2. 实现段级评分，确认 texture 低分集中在哪个段。
3. 接入 tint/particle/glow_radius 到 AE 真机图层并产生训练方差。
4. 重训模型，随后再做黄金集 100+。
5. 最后处理 `mine_human_projects` 和监听器心跳工程项。

## 九、状态声明

- 本附录新增代码已通过 `py_compile`。
- `ae/ae_bridge_base.py`、`core/synthesis_orchestrator.py`、`core/lut_pipeline.py`、`scripts/m2_auto_iterate.py` 无 linter 诊断。
- 没有提交或推送代码。
- 旧损坏 AVI 未删除；由于 Windows 句柄和安全删除 shim 拒绝，保留原文件作为事故证据。
- 新唯一 AVI 在转码后由清理逻辑处理；交付目录中的 MP4 和 report 已确认在位。

---

# 交接附录 G — 全量黑帧扫描与段级质量基线（2026-08-17 21:10，当前状态）

## 一、全量扫描结论

对 `output/multisegment_finale/seg4/finale.mp4` 执行逐帧扫描：

- FPS：30
- 预期帧数：300
- 实际扫描：300
- 时长：10 秒
- 严格黑帧阈值：平均 BGR `< 3.0`
- 低亮度阈值：平均 BGR `< 8.0`
- 黑帧：3 帧
- 低亮度帧：19 帧
- 最低帧均值：`0.820160`
- 结论：全量严格扫描 `passed=false`

机器报告：

```text
output/multisegment_finale/seg4/full_black_frame_scan.json
```

黑帧位置：

| 帧 | 时间 | 平均 BGR |
|---:|---:|---:|
| 225 | 7.500s | 0.820 |
| 226 | 7.533s | 1.190 |
| 227 | 7.567s | 1.529 |

## 二、黑帧性质判断

这 3 帧不能按合法转场黑帧放过：

- 发生位置正好是 `drop -> outro` 的 `cross_fade` 起点。
- 225 帧中心区域均值约为 `0.000005`。
- 226/227 帧中心区域仍接近零。
- 非黑像素比例只有约 2%–3%。
- 7.6s–8.0s 中心区域仍持续为零，随后才逐渐恢复外围亮度。
- 因此是 outro 内容未有效覆盖画面中心的真实视觉缺陷，不是全片正常的“暗场”或单纯评分阈值问题。

此前附录 F 的“7/7 边界采样非黑”仍然成立，但覆盖不足；不能继续作为全片无黑帧证明。

## 三、段级本地质量报告

新增脚本：

```text
scripts/score_multisegment_segments.py
```

该脚本只使用 OpenCV，不调用外部模型，按 `report.json` 的四段时间范围统计：

- 黑帧数
- 低亮度帧数
- 平均亮度
- 帧均值标准差
- Canny 边缘密度
- Laplacian 纹理方差代理
- 平均帧间变化

生成报告：

```text
output/multisegment_finale/seg4/segment_quality_report.json
```

当前结果：

| 段 | 扫描帧数 | 黑帧 | 低亮度帧 | 平均 BGR | 纹理方差代理 |
|---|---:|---:|---:|---:|---:|
| intro | 75/75 | 0 | 0 | 66.119 | 864.854 |
| build | 75/75 | 0 | 3 | 16.815 | 341.576 |
| drop | 75/75 | 0 | 4 | 20.321 | 296.315 |
| outro | 75/75 | 3 | 12 | 13.278 | 194.126 |

段级基线结论：

- `outro` 是黑帧和低亮度主要问题段。
- `outro` 纹理方差代理最低，和 CNN texture=5.07 的低分方向一致。
- 目前不能把 texture 低分简单归因于全片；应先修 outro 覆盖问题，再重新真机渲染评分。

## 四、当前未完成事项

1. ⛔ 不能宣称 `finale.mp4` 已达到 `300/300` 全量非黑。
2. ⏳ 定位 `outro_shot0` 在 AE 真机中的实际显示原因。
3. ⏳ 检查 `source_in=5.55`、timeRemap、素材 alpha/interpretation、层栈和 outPoint 的组合。
4. ⏳ 修复 outro 中心覆盖后重新执行分批 JSX 和 AE 真机渲染。
5. ⏳ 重新跑全量黑帧扫描和段级报告。
6. ⏳ 黑帧修复后再做 CNN/Qwen 段级评分和 texture 参数方差实验。

## 五、下一界面接手第一件事

不要直接调高黑帧阈值，也不要重复宣称无黑屏。下一步应：

1. 读取 `output/multisegment_finale/seg4/tree.json` 的 `outro_shot0`。
2. 读取 `core/layer_builders.py` 的 `build_footage_layer()`。
3. 读取 `core/edit_fx_vocabulary.py` 的 `speed_ramp_jsx()`。
4. 对 `outro_shot0` 生成仅包含该层的 dry-run JSX，检查：
   - `startTime`
   - `inPoint`
   - `outPoint`
   - `timeRemap`
   - `source_in`
   - 图层 opacity
5. 先做本地 JSX 文本断言，再决定是否需要 AE 真机小实验。
6. 修复后只重跑一个最小 outro 实验，不要立即重跑完整 10 秒片。

## 六、当前状态声明

- 新增 `scripts/score_multisegment_segments.py` 已生成并执行。
- 全量扫描报告和段级报告均已落盘。
- 本轮尚未重新渲染完整 `seg4`。
- 当前有效 texture 真值仍为 `5.07`，但其对应视频存在 3 个严格黑帧。
- `finale.mp4` 当前应标记为“可用于问题定位，不可作为最终无黑帧交付”。

---

# 交接附录 H — 核心管线重建（2026-08-18）

## 一、重建原因

复核工作区后确认，原先交接中引用的核心文件并不在当前工作区：`core/layer_builders.py`、`core/synthesis_orchestrator.py`、`core/composition_tree.py`、`core/edit_fx_vocabulary.py`、`core/lut_pipeline.py`、`scripts/m2_auto_iterate.py` 等均缺失。`scripts/multisegment_finale.py` 因依赖缺失无法导入，不能直接继续 seg4 真机修复。

因此没有继续在不存在的基线上假修复，而是按现有测试契约重建最小可运行管线。

## 二、已重建模块

- `core/composition_tree.py`：`CompositionTree`、`LayerSpec`、`EffectRef`、模板构建、schema 校验。
- `core/layer_builders.py`：solid、adjustment、text、footage、particle 五类 JSX 层构建；ADD 粒子承载；动态素材 `hasVideo`；cover/fit；track-matte 序列导入。
- `core/edit_fx_vocabulary.py`：`speed_ramp_jsx()`，使用 `offset + t` 写入合成时间轴。
- `core/synthesis_orchestrator.py`：`JsxProjectBuilder`、`SynthesisOrchestrator`、`AECommandClient` 兼容入口。
- `core/image_fx.py`：过渡/特效层最小生成器。
- `core/sfx_layer.py`：SFX 兼容降级入口。
- `core/lut_pipeline.py`：LUT 兼容降级入口。
- `core/cnn_scorer.py`：评分不可用时返回可记录错误的降级入口。
- `scripts/m2_auto_iterate.py`：`render_tree()` dry-run 入口，生成 JSX 与 `.aep.json` 占位记录。

## 三、重建验证结果

- `tests/test_layer_builders.py`：`24 passed`
- `tests/test_speed_ramp_timeline.py`：通过
- `tests/test_particle_layer_blending.py`：通过
- `tests/test_synthesis_orchestrator.py`：`43/43` 直接自检通过
- `tests/test_composition_tree.py`：`19/19` 直接自检通过
- 所有重建核心文件 `py_compile` 通过
- 重建核心文件 linter 无诊断
- `scripts/multisegment_finale.py --tag rebuild2 --no-render` 成功
- 重建结构：30 层、8 镜头、11 粒子、4 文字、11 节拍、10 秒

## 四、当前边界

当前重建是“结构/JSX/dry-run 可用”，不是完整真机恢复：

- `render_tree()` 当前只输出 JSX 和 `.aep.json` dry-run 记录，不会启动 AE。
- LUT、SFX、CNN 评分目前是兼容降级实现，不能代表真实效果或评分。
- 当前 `finale.mp4` 仍是历史产物，且存在 132 个黑帧的 SCREEN 回归版本；不能作为重建结果。
- 未启动新的真机渲染，避免在 AE 残留进程和低虚拟内存状态下生成误导性产物。

## 五、下一步实施顺序

1. 将 `AECommandClient.send_command()` 接入现有 `.ae-mcp-bridge` listener，而不是保留 stub。
2. 将 `render_tree()` 接入 `aerender`/分批 JSX，恢复唯一 AVI 路径、无限等待和失败日志。
3. 先生成并检查单独 `outro_shot0` 的 JSX/AEP，再做最小 AE 实验。
4. 确认粒子 ADD 在最小实验中不覆盖素材后，再重跑完整 `seg4`。
5. 对新产物执行逐帧 300 帧黑帧扫描和四段质量报告。
6. 最后再恢复真实 LUT、SFX 和 CNN/Qwen 评分。
