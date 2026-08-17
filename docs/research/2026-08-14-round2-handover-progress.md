# 2026-08-14 移交清单推进报告（第 2 轮）

> 承接 `docs/research/2026-08-14-audit-summary-report.md` 的 P1/P2 移交清单，
> 本轮完成 4 项，第 5 项完成评估准备。

## ① Registry 双体系统一 ✅

- 确认两体系**分工不同**：`models/model_registry.json`=资产清单（盘上有什么），
  `models/deployment/model_registry.py`=生命周期注册中心（哪个版本可用，staging/
  production/A-B）→ 不合并，改为**桥接**。
- 新增 `ModelRegistry.sync_from_inventory()`：清单新增模型 → staging 登记；
  已有登记 → 仅回填 path/metadata，**不覆盖生命周期状态**（测试验证 promote 后
  同步不回滚）。
- 默认路径 `"./model_registry"`（cwd 相对，曾散落 4 份副本）→ 稳定绝对路径
  `data/model_lifecycle`；新增模块级 `load_registry()`。
- 测试 `tests/test_model_registry_bridge.py` 5 用例。

## ② 知识卡批量扩展 ✅

- **8 张风格卡**（原 3 + 新 5）：cinematic_film（青橙调色）、vintage_film（复古
  胶片）、high_key_bright（高调明亮）、hardcore_battle（硬核战斗）、
  emotional_lyric（抒情文艺）——全部经 `card_to_director_inputs` 桥接验证，
  可直接 `render(style_id=...)` 消费。
- **EBU SKOS 对齐的转场分类法** `knowledge/transition_taxonomy.py`：14 种转场的
  量化 schema（kind/default_dur/rhythm_fit/xfade 滤镜名），补齐知识审计指出的
  "转场节奏无量化 schema"真缺口；`validate_xfade_consistency()` 与生产
  XFADE_MAP 自动校验（一致）；补 `cross_dissolve`→`("fade",0.30)` 真叠化映射。

## ③ 测试工程补齐 ✅

- 安装 pytest-cov 7.1.0 + coverage 7.15.4，**fail_under=60 从纸面变实测**：
  6 个核心模块覆盖率 **77.58%**（taste_contract 96.9% / style_card 92.1% /
  camera_decision 86.3% / error_diagnostician 78.3%）。
- **error_diagnostician 补测**（审计"最该补"第 1 位）：12 用例覆盖规则引擎、
  缓存 TTL、LLM 响应解析与 0.85 校准、统计持久化。
- **68 个脚本式伪测试迁移** `tests/` → `dev_scripts/`（git mv 保历史）：
  pytest 收集 **170s → 68s（-60%）**，收集数 4984 → 4916（口径真实化），
  消除收集期真实网络/文件副作用。

## ④ kandinsky-videomae-large A/B 评估 + 三级级联 ✅

- 下载 ai-forever/kandinsky-videomae-large-camera-motion（1159MB, 18 运镜类
  +3 镜头类多标签头）至 `D:\AE-Data\Models\VideoMAE-MovieShots\kandinsky-large`。
- **A/B 实测**（58 素材, `models/output/videomae_ab_20260814.json`）：
  - 推理快 2.5×（0.065s vs 0.166s/镜，GPU）
  - **base 版系统性偏差**：68%（38/56）素材被贴 pan_left，其中 8 例被
    kandinsky 以 0.86-1.0 置信判为 static（base 判 Motion 0.74-0.94 → 误标）
  - kandinsky 有效标签置信中位 0.99，且能表达 orbit/shake 等 base 无能力类；
    43% 拒绝率是"undefined"诚实拒标（阈值 0.3-0.5 敏感性实测无差异）
- **结论落地**：`classify_cascade()` 三级级联（kandinsky 高精度优先 → base
  兜底 → 光流规则），导演 T3 已切换级联注入；级联 3 用例测试。

## ⑤ ToriiGate 评估准备（P1 候选，未实施）

- 许可核验：`Minthy/ToriiGate-v0.4-7B/2B` = **Apache-2.0** ✅（干净可商用）
- 基于 Qwen2.5-VL，2B 变体适配 RTX 4060 8GB（bf16 ~4GB / GGUF 量化 ~2-3GB）
- 为图像级 VLM（视频需抽帧），W6 接入路径 = 帧采样 + chat_template + 氛围标注
  prompt；属下一轮实施项。

## 验证汇总

| 项 | 结果 |
|---|---|
| 本轮新增/回归测试 | 87 passed / 0 failed |
| 核心模块覆盖率 | 77.58%（阈值 60% ✅） |
| pytest 收集耗时 | 170s → 68s |
| A/B 评估素材 | 58 条真实素材，双模型全量 |
| kandinsky 推理 | GPU 0.065s/镜（base 2.5×） |

## 下一步（按优先级）

1. ToriiGate-2B 下载 + W6 氛围标注模块（许可已核验）
2. BeatNetLite 卡点三层信号（节拍/下拍/结构）
3. 用 `style_id="hardcore_battle"` 跑真实管线验证新卡效果
4. 上帝文件拆分 / PR Bridge 硬编码修复（D-24）
