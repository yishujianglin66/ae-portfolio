# F5 优化设计书 — CEP 桥接 + 进度回调

> **模块**: F5 — 人声分离 CLI (Python)
> **优先级**: 🟡 P1
> **日期**: 2026-06-05

## 变更摘要

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| CEP 桥接 | 无 async 模式 | `--job-id` + `--check` 状态查询 |
| 进度报告 | 无 | 作业状态文件 (.job_*.json) |
| ffprobe 调用 | 重复 2× | 保持 (两个独立场景) |

## 新增 CLI 模式

### 异步提交
```bash
python F5_vocal_separate.py music.wav --job-id abc123 --json-only
# → {"status": "OK", "job_id": "abc123", "mode": "async"}
```

### 状态查询
```bash
python F5_vocal_separate.py --check abc123
# → {"status": "RUNNING", "message": "Job in progress"}
# → {"status": "OK", "job": {"status": "completed", "result": {...}}}
```

## 状态文件

位置: `~/Desktop/VocalSep5_Output/.job_<job_id>.json`

```json
{"status": "submitted", "progress": 0}
{"status": "processing", "progress": 10}
{"status": "completed", "progress": 100, "result": {...}}
{"status": "failed", "error": "..."}
```
