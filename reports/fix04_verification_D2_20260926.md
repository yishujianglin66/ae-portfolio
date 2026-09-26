# FIX-04 欠账清偿 D-2（既有测试文件补新规格断言）

- 日期：2026-09-26｜项：方案 FIX-04（审计 F4）｜状态：部分完成 → **READY**
- 前序：实现与新增测试已在 `8ed5e08`；全仓回归覆盖消费面已在 `3ad4554`（D-1）

## 本项动作

`tests/test_multimodal_fusion_hub.py` 追加 `TestHeuristicPathsHonestMarking` 4 例，
把 FIX-04 新规格**钉进既有文件**（方案验收栏原文要求"更新该文件断言（available 默认 False + 标记存在）"；
D-1 前该文件未改，属订正清单承认的偏差）：

| 用例 | 钉住的规格 |
|---|---|
| `test_video_file_path_marked_unavailable` | `_extract_from_video`（文件大小启发式）必须 available=False + confidence=0.0 |
| `test_images_path_marked_unavailable` | `_extract_from_images` 同上 |
| `test_audio_file_path_marked_unavailable` | `_extract_from_file`（bpm=120 常量伪造）同上——F4 直接对应物 |
| `test_encode_all_with_fake_files_degrades_to_text_only` | 集成层：启发式视频+文本 → 仅 text 模态存活，`modality_weights` 不含 visual（伪造模态真实退出融合决策，非仅打标） |

与 `tests/test_fake_success_packs_fix0405.py` 构成双保险（后者锁实现，本文件锁既有测试入口规格）。

## 真实验证输出

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_multimodal_fusion_hub.py -q --timeout=120 -p no:cacheprovider
17 passed in 0.31s        # 旧 13 + 新 4，0 failed 0 skipped
$ .venv\Scripts\python.exe -m ruff check --config ruff.toml tests/test_multimodal_fusion_hub.py
All checks passed!
```

动手前 `git status` 核验：`tests/test_multimodal_fusion_hub.py`、`core/multimodal_fusion_hub.py`、
`ai/aigc_generator.py`、`ai/ai_director.py` 均无在途 diff（并行线零冲突）。

## FIX-04 验收栏终对账（全项闭环）

- ① "该文件断言更新" ✅（本次）；② "grep available=True 归零或逐处真实实现注释" ✅（D-1 时核查：
  现存 True 均为 array/text 真实计算路径且带 FIX-04 注释）；③ "unified_pipeline 相关回归不回退" ✅
  （D-1 全仓 6398 passed 覆盖）。→ **FIX-04 升 READY**。
- 下一欠账：D-3 = FIX-05 `collect_materials` 全 Mock 端到端断言。
