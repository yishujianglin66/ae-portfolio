# FIX-03 文件闭单 F3-1｜core/audio_edit_engine.py（审计 F5：不可区分降级）

- 日期：2026-09-26｜串行队列：FIX-03 文件 1/8
- 前置 `git status` 核验：目标两文件无在途 diff；HEAD=`65cd139`（并行线无新占）

## 变更（对齐契约 §1/§3："允许显式降级，禁止伪装成功"）

| 位置 | 变更 |
|---|---|
| `AudioAnalyzerAdapter._normalize`（真分析路径） | 返回增 `"analysis_path": "real"` |
| `AudioAnalyzerAdapter._fallback_analyze`（bpm=128 常量+正弦伪造） | 返回增 `"analysis_path": "fallback"` + `"is_heuristic": True` + `"fallback_reason"`；WARN 日志"不得当作踩拍真值"——旧返回与真实分析完全同构无标记的问题（F5）根治 |
| `AudioEditEngine.edit()` | 启发式时 WARN；report 增 `audio_analysis_path/audio_is_heuristic`；EDL 落盘 json 增 `analysis_path`（透传到磁盘证据，下游拿常量 BPM 不再可能不自知） |
| `tests/test_audio_edit_engine.py` | 新增 `TestAnalysisProvenance` 3 例（差集：只钉来源标记与透传，不重复既有结构断言） |

设计取舍（如实记录）：**未采用"无 librosa 即 raise"**——ai_director 与离线测试流依赖 edit() 走通全链（过度阻断会把真降级变假崩溃），契约的 `fallback + 显式标记` 语义是本文件的正确落点；ai_director 消费侧 `bpm = audio_features.get("bpm", 128)` 的兜底常量属其自身声明问题，挂账 FIX-09 扫描器覆盖。

## 真实验证输出

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_audio_edit_engine.py -q --timeout=180
6 failed, 69 passed in 0.53s
$ git stash push -- <两文件>; pytest 同命令; git stash pop     # 归因复验
6 failed, 66 passed        # ← HEAD 基线同 6 红（66=69-我的新3例），失败集合一致
```

**6 红归因结论（stash 对照实锤）**：预存于 HEAD，被 `conftest.py` collect_ignore 掩盖（该文件在排除名单，D-1 的"6398 全绿"不含它——这正是审计 §3.2b⑥"三重削弱"的又一次现场印证）。失败形态全部是 pick_transition/snap_to_beat 的**边界档位差异**（如 `'glow_flash' == 'cut'`、`4.0 == 3.5`），属实现与测试对 `>=/>` 边界语义各说各话，需独立裁决哪侧为生产真语义。

我的 3 新例全绿（69=66+3，失败集合前后一致）；消费面：

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_fake_success_packs_fix0405.py tests/test_pro_upgrade.py -q
15 passed in 2.92s          # ai_director 系消费者无感（追加键兼容）
$ .venv\Scripts\python.exe -m ruff check --config ruff.toml core/audio_edit_engine.py tests/test_audio_edit_engine.py
All checks passed!
```

## 登记与挂账

- **新发现 N-1（建议纳入方案账目 = FIX-48）**：`audio_edit_engine` 边界语义裁决（TestSnapToBeat::test_prev_snap_at_boundary + TestPickTransition 5 例）——本文件闭单不动它，避免把未归因行为改混进契约提交；修复方向：git 历史定两侧意图 → 修一侧 → 该文件从 collect_ignore 摘除（喂给 FIX-16）。
- F5 验收子项"真实链路验证"（启发式在真音频上的透传表现）→ 随 FIX-03 全批结束的统一回归+真跑核验登记。

## 复跑

```powershell
.venv\Scripts\python.exe -m pytest tests/test_audio_edit_engine.py -q --timeout=180 -p no:cacheprovider   # 预期 6 failed(预存N-1)+69 passed
.venv\Scripts\python.exe -m pytest tests/test_audio_edit_engine.py::TestAnalysisProvenance -q              # 预期 3 passed
```
