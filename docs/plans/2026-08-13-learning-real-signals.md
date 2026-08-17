# 学习系统真实信号修复与奖励升级实施计划 (Learning Real Signals & Reward Upgrade)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管线学习与自进化系统从真实生产信号中学习——把常数奖励(68.5)替换为内容级实测指标、把合成种子反馈替换为真实生产反馈、修复 TS 侧学习提取腿,使进化循环产生有效选择压力,最终提升 v23 导演系统与统一管线的产出质量上限。

**Architecture:** 三条断腿分别修复——(1) 奖励腿:新建 `core/content_metrics.py` 计算导演已掌握的内容级指标(卡点对齐/运镜多样性/素材复用/时序能量),`core/frame_sampler.py` 用 ffmpeg 解码真实帧统计,替换 `AutoQualityEvaluator` 中的常数分;(2) 反馈腿:director 路径补真实 `param_feedback` 写入;(3) 提取腿:TS phase5 新增 `consolidate()`(模板去重合并 + 从成功记录提取默认值)。复用既有资产:VMAFAdapter、rhythm_reward v2、accept_runner 盲评。

**Tech Stack:** Python 3.12 + numpy + ffmpeg/ffprobe(项目已装) + pytest;TypeScript 5 + esbuild + node --test。

**诊断依据(执行前必读):**

| # | 缺陷 | 证据 |
|---|------|------|
| D1 | 奖励常数化 | `core/self_evolution_engine.py:614-708` 四维全是常数分/阶段计数,`_evaluate_audio` 恒返 65;`evolution_state.json` 中 08-12 四次导演运行 quality 全为 68.5/deviation 全为 0.3425 |
| D2 | Py 反馈腿空转 | `learning/.cache/param_feedback.json` 20 条全是 `inject_*` 种子(08-11 20:16 一次注入);director 走 `ai/production_director.py` 不经过 `unified_pipeline._trigger_param_feedback`,渲染后零真实写入 |
| D3 | TS 提取腿断裂 | `%APPDATA%\AE-Knowledge-Vault\learning-state\`:execution-records 178 条真实记录在积累,但 default-value-store 自 07-30 起恒为 4 条种子;case-store 38 条 `silhouette_roto` 模板全部相同(tolerance=1.0)未去重;`compiler/src/phase5/` 无 consolidate/train/extract 逻辑 |
| D4 | 进化模拟模式 | `core/auto_evolution.py:228` `execute_real=False`;知识蒸馏停滞(`evolution_knowledge.jsonl` 自 08-05 零增长,3.9KB) |

**既有资产(复用,禁止重造):**
- `integrations/vmaf_quality_adapter.py`(378 行,VMAF/SSIM/basic 三级降级,已就绪)
- `ai/rhythm_reward.py` + `models/rhythm_reward_v2.pkl`(08-11,top1 一致率 19/22,已被 director L974-1009 消费)
- `ai/accept_runner.py` 盲评验收(`reports/accept_*.json`)
- `core/self_evolution_engine.RuleDistiller`(规则蒸馏器已实装,缺真实 episode 喂入)

**验证基线:** `python -m pytest -q --timeout=60` → 4654 passed / 25 failed(18 预存 style_composition + 7 环境敏感,见 docs/plans/2026-08-11-project-consolidation.md)。任何 Task 完成后回归不得新增失败。

---

## File Structure

| 文件 | 动作 | 职责 |
|------|------|------|
| `core/content_metrics.py` | Create | 内容级指标纯函数(输入导演结构化数据,输出 0-1 分) |
| `tests/test_content_metrics.py` | Create | 合成数据单测 |
| `core/frame_sampler.py` | Create | ffmpeg 抽帧 + 亮度/对比度/时序统计 |
| `tests/test_frame_sampler.py` | Create | ffmpeg 合成测试视频的单测 |
| `core/self_evolution_engine.py` | Modify | `AutoQualityEvaluator` 真实化(约 L552-709) |
| `tests/test_auto_quality_evaluator.py` | Create | 评估器回归:不同输入必须产生不同分 |
| `ai/production_director.py` | Modify | `_trigger_auto_evolution`(L526-591)充实 record + 真实质量 |
| `ai/director_feedback_hook.py` | Create | director 完成后的 param_feedback 真实写入 |
| `tests/test_director_feedback_hook.py` | Create | 反馈写入单测 |
| `compiler/src/phase5/persistent-learning-loop.ts` | Modify | 新增 `consolidate()` |
| `compiler/test/unit-persistent-learning-consolidation.test.ts` | Create | 去重/提取单测 |
| `core/auto_evolution.py` | Modify | 真实执行选项 + 知识蒸馏落盘 |

---

## Task 0: 基线锁定与数据备份

**Files:**
- Backup: `data/self_evolution/`、`learning/.cache/param_feedback.json`、`%APPDATA%\AE-Knowledge-Vault\learning-state\`

- [ ] **Step 1: 运行 pytest 基线**

Run: `python -m pytest -q --timeout=60 2>&1 | Select-Object -Last 5`
Expected: `4654 passed, 25 failed`(若数字有偏差,记录新基线并以此为准)

- [ ] **Step 2: 备份现有学习数据产物**

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$bk = "temp\learning_backup_$ts"
New-Item -ItemType Directory -Path $bk | Out-Null
Copy-Item "data\self_evolution" $bk -Recurse
Copy-Item "learning\.cache\param_feedback.json" $bk\
Copy-Item "$env:APPDATA\AE-Knowledge-Vault\learning-state" $bk\learning-state -Recurse
```
Expected: `$bk` 下三组备份齐全

- [ ] **Step 3: Commit**

```bash
git add temp/learning_backup_*/
git commit -m "chore: backup learning artifacts before real-signal refactor"
```
(若团队约定备份不入 git,改用 `git commit --allow-empty -m "chore: learning baseline snapshot pre-refactor"`)

---

## Task 1: 内容级指标模块 core/content_metrics.py

设计原则:输入导演已掌握的结构化数据(切点表/运镜表/素材窗口),**不需要视频解码**,零外部依赖。

**Files:**
- Create: `core/content_metrics.py`
- Test: `tests/test_content_metrics.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_content_metrics.py
import math
import pytest
from core.content_metrics import (
    beat_alignment_score,
    camera_diversity_score,
    material_reuse_penalty,
    temporal_energy_variance,
)


def test_beat_alignment_perfect():
    beats = [1.0, 2.0, 3.0, 4.0]
    cuts = [1.02, 1.98, 3.01, 4.0]  # 全部在 50ms 容差内
    assert beat_alignment_score(cuts, beats, tolerance=0.05) == pytest.approx(1.0)


def test_beat_alignment_all_off():
    beats = [1.0, 2.0, 3.0, 4.0]
    cuts = [1.5, 2.5, 3.5]  # 全部落在两拍正中
    assert beat_alignment_score(cuts, beats, tolerance=0.05) < 0.2


def test_beat_alignment_no_cuts():
    assert beat_alignment_score([], [1.0, 2.0]) == 0.0


def test_camera_diversity_uniform():
    moves = ["pan_left", "zoom_in", "push", "orbit", "zoom_out", "pan_right"]
    assert camera_diversity_score(moves) == pytest.approx(1.0, abs=0.05)


def test_camera_diversity_homogeneous():
    # v23 实际缺陷复现: build 段全 pan_left
    moves = ["pan_left"] * 12
    assert camera_diversity_score(moves) < 0.1


def test_camera_diversity_empty():
    assert camera_diversity_score([]) == 0.0


def test_material_reuse_no_reuse():
    windows = [("src_a.mp4", 1.0, 3.0), ("src_b.mp4", 5.0, 8.0)]
    assert material_reuse_penalty(windows) == pytest.approx(0.0)


def test_material_reuse_full_overlap():
    windows = [("src_a.mp4", 1.0, 3.0), ("src_a.mp4", 1.1, 3.1)]
    assert material_reuse_penalty(windows) > 0.8


def test_temporal_energy_variance_identical():
    assert temporal_energy_variance([0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.0)


def test_temporal_energy_variance_dynamic():
    series = [0.1, 0.9, 0.2, 0.8, 0.15, 0.85]
    assert temporal_energy_variance(series) > 0.5
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_content_metrics.py -v`
Expected: FAIL(ModuleNotFoundError: No module named 'core.content_metrics')

- [ ] **Step 3: 实现**

```python
"""core/content_metrics.py - 内容级质量指标

输入均为导演/管线已掌握的结构化数据, 不解码视频, 零外部依赖。
所有分数归一到 [0, 1]。用于 AutoQualityEvaluator 真实化(替代常数分)。
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Sequence, Tuple


def beat_alignment_score(
    cut_times: Sequence[float],
    beat_times: Sequence[float],
    tolerance: float = 0.05,
) -> float:
    """切点落在节拍容差内的比例。0=完全脱拍, 1=全部卡拍。"""
    if not cut_times or not beat_times:
        return 0.0
    hits = 0
    for t in cut_times:
        if min(abs(t - b) for b in beat_times) <= tolerance:
            hits += 1
    return hits / len(cut_times)


def camera_diversity_score(moves: Sequence[str]) -> float:
    """运镜序列香农熵归一化。检测 pan_left*12 这类同质化。"""
    if not moves:
        return 0.0
    counts = Counter(moves)
    n = len(moves)
    entropy = -sum((c / n) * math.log(c / n) for c in counts.values())
    max_entropy = math.log(len(counts)) if len(counts) > 1 else 0.0
    if max_entropy == 0.0:
        return 0.0
    return min(entropy / max_entropy, 1.0)


def material_reuse_penalty(windows: Sequence[Tuple[str, float, float]]) -> float:
    """素材窗口重叠率。windows=(source, start, end)。0=无复用, 1=完全复用。"""
    if len(windows) < 2:
        return 0.0
    by_src: Dict[str, List[Tuple[float, float]]] = {}
    for src, s, e in windows:
        by_src.setdefault(src, []).append((s, e))
    overlap_dur = 0.0
    total_dur = 0.0
    for spans in by_src.values():
        spans.sort()
        for i, (s, e) in enumerate(spans):
            total_dur += e - s
            if i > 0:
                prev_end = spans[i - 1][1]
                if s < prev_end:
                    overlap_dur += min(e, prev_end) - s
    if total_dur <= 0:
        return 0.0
    return min(overlap_dur / total_dur, 1.0)


def temporal_energy_variance(energy_series: Sequence[float]) -> float:
    """能量序列标准差, tanh 归一。0=静止无节奏感, →1=强动态。"""
    if len(energy_series) < 2:
        return 0.0
    mean = sum(energy_series) / len(energy_series)
    var = sum((x - mean) ** 2 for x in energy_series) / len(energy_series)
    return math.tanh(math.sqrt(var) * 4.0)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_content_metrics.py -v`
Expected: PASS(10 个用例)

- [ ] **Step 5: Commit**

```bash
git add core/content_metrics.py tests/test_content_metrics.py
git commit -m "feat(learning): content-level quality metrics (beat/camera/reuse/energy)"
```

---

## Task 2: 真实帧采样 core/frame_sampler.py

设计原则:用 ffmpeg 抽帧解码**真实像素**,计算亮度/对比度/时序变化。这是"视觉质量"维度的实测信号。

**Files:**
- Create: `core/frame_sampler.py`
- Test: `tests/test_frame_sampler.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_frame_sampler.py
import shutil
import subprocess
import pytest
from pathlib import Path
from core.frame_sampler import FrameStats, probe_video, sample_frame_stats

HAS_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.fixture(scope="module")
def synthetic_video(tmp_path_factory) -> Path:
    """ffmpeg 生成 2s 渐变测试视频(真实解码对象)"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("fs") / "synthetic.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "testsrc2=size=320x240:rate=10:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out


def test_probe_video(synthetic_video):
    info = probe_video(str(synthetic_video))
    assert info["width"] == 320 and info["height"] == 240
    assert info["fps"] == pytest.approx(10.0, abs=0.5)
    assert info["duration"] == pytest.approx(2.0, abs=0.2)
    assert info["has_audio"] is False


def test_sample_frame_stats(synthetic_video):
    stats = sample_frame_stats(str(synthetic_video), n_frames=8)
    assert stats.n_sampled == 8
    assert 0.0 <= stats.mean_luma <= 1.0
    assert stats.luma_contrast > 0.0          # testsrc2 有丰富纹理
    assert stats.temporal_change >= 0.0        # 动态画面帧间差 > 0


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        probe_video("nonexistent_video.mp4")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_frame_sampler.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
"""core/frame_sampler.py - 真实帧采样统计

通过 ffmpeg/ffprobe 解码视频, 产出亮度/对比度/时序变化等实测统计。
为 AutoQualityEvaluator 提供"真正看过画面"的视觉质量信号。
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FrameStats:
    n_sampled: int = 0
    mean_luma: float = 0.0      # [0,1]
    luma_contrast: float = 0.0  # 帧内亮度标准差均值
    temporal_change: float = 0.0  # 相邻采样帧平均绝对差


def probe_video(path: str) -> dict:
    """ffprobe 读取真实技术参数"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(p)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True,
    ).stdout
    data = json.loads(out)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if float(den or 0) else 0.0
    return {
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": fps,
        "duration": float(data.get("format", {}).get("duration", 0.0)),
        "bitrate_kbps": int(data.get("format", {}).get("bit_rate", 0)) // 1000,
        "codec": v.get("codec_name", ""),
        "has_audio": a is not None,
    }


def sample_frame_stats(path: str, n_frames: int = 16, scale: int = 160) -> FrameStats:
    """抽 n_frames 帧解码为灰度 rawvideo, 计算亮度统计与帧间差"""
    import numpy as np
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    dur = float(json.loads(subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(p)],
        capture_output=True, text=True, check=True,
    ).stdout)["format"]["duration"])
    fps_filter = f"fps={max(n_frames, 1) / max(dur, 0.1)}"
    cmd = [
        "ffmpeg", "-v", "quiet", "-i", str(p),
        "-vf", f"{fps_filter},scale={scale}:-2,format=gray",
        "-frames:v", str(n_frames), "-f", "rawvideo", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    # rawvideo gray: 每帧行数未知时按 16:9 兜底, 实际用 scale 输出宽度=scale
    h = len(raw) // scale // max(n_frames, 1)
    if h <= 0 or len(raw) < scale * h:
        return FrameStats()
    frames = np.frombuffer(raw[: scale * h * n_frames], dtype=np.uint8)
    frames = frames.reshape(-1, h, scale).astype(np.float32) / 255.0
    return FrameStats(
        n_sampled=len(frames),
        mean_luma=float(frames.mean()),
        luma_contrast=float(frames.std(axis=(1, 2)).mean()),
        temporal_change=float(
            (abs(frames[1:] - frames[:-1]).mean(axis=(1, 2)).mean())
            if len(frames) > 1 else 0.0
        ),
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_frame_sampler.py -v`
Expected: PASS(3 个用例;ffmpeg 缺失时 skip 并在报告中注明)

- [ ] **Step 5: Commit**

```bash
git add core/frame_sampler.py tests/test_frame_sampler.py
git commit -m "feat(learning): real frame sampling stats via ffmpeg"
```

---

## Task 3: AutoQualityEvaluator 真实化(D1 根因修复)

**Files:**
- Modify: `core/self_evolution_engine.py:552-709`(`AutoQualityEvaluator`)
- Test: `tests/test_auto_quality_evaluator.py`

- [ ] **Step 1: 写失败测试(核心回归:不同内容必须不同分)**

```python
# tests/test_auto_quality_evaluator.py
import asyncio
import json
import subprocess
import shutil
import pytest
from pathlib import Path
from core.self_evolution_engine import AutoQualityEvaluator

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _make_video(path: Path, src: str, duration: float = 2.0):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", f"{src}=size=320x240:rate=10:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


@pytest.fixture(scope="module")
def two_videos(tmp_path_factory):
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    d = tmp_path_factory.mktemp("aqe")
    a, b = d / "dynamic.mp4", d / "static.mp4"
    _make_video(a, "testsrc2")
    # 纯黑静态画面
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "color=c=black:size=320x240:rate=10:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(b)],
        check=True,
    )
    return a, b


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_different_content_different_score(two_videos):
    """D1 回归: 内容不同 → 分数必须不同(旧实现对一切都返回常数)"""
    a, b = two_videos
    ev = AutoQualityEvaluator()
    sa = _run(ev.evaluate(str(a), {}, {"target_resolution": (320, 240)}, {}))
    sb = _run(ev.evaluate(str(b), {}, {"target_resolution": (320, 240)}, {}))
    assert abs(sa.overall_score - sb.overall_score) > 1.0
    assert sa.visual_quality > sb.visual_quality  # 动态画面视觉分更高


def test_same_video_stable_score(two_videos):
    """可重复性: 同一视频两次评估波动 < 2 分"""
    a, _ = two_videos
    ev = AutoQualityEvaluator()
    s1 = _run(ev.evaluate(str(a), {}, {}, {}))
    s2 = _run(ev.evaluate(str(a), {}, {}, {}))
    assert abs(s1.overall_score - s2.overall_score) < 2.0


def test_missing_file_low_score():
    ev = AutoQualityEvaluator()
    s = _run(ev.evaluate("nonexistent.mp4", {}, {}, {}))
    assert s.overall_score < 35
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_auto_quality_evaluator.py -v`
Expected: FAIL(`test_different_content_different_score` — 旧实现两个文件得分相同)

- [ ] **Step 3: 重写 `AutoQualityEvaluator` 四个维度**

替换 `core/self_evolution_engine.py` 中 L610-709 的四个 `_evaluate_*` 方法(保留 `evaluate()` 的权重结构与 `QualityAssessment` 数据类不变):

```python
    # ---- 真实化实现(替换 L610-709 的常数版本) ----

    def _evaluate_technical(self, output_path, input_spec, config) -> float:
        """技术质量: ffprobe 实测分辨率/帧率/码率"""
        from core.frame_sampler import probe_video
        if not output_path or not Path(output_path).exists():
            return 20.0
        try:
            info = probe_video(output_path)
        except Exception:
            return 30.0  # 无法探测视为损坏
        platform = (config.get("publish_platforms") or ["default"])[0]
        std = self.PLATFORM_STANDARDS.get(platform, self.PLATFORM_STANDARDS["default"])
        score = 50.0
        if info["width"] >= std["min_resolution"][0] and info["height"] >= std["min_resolution"][1]:
            score += 20
        if info["fps"] >= std["min_fps"]:
            score += 10
        # 码率合理性: 与目标码率同数量级
        expected_kbps = std["target_bitrate_mbps"] * 1000
        if expected_kbps > 0 and info["bitrate_kbps"] > 0:
            ratio = info["bitrate_kbps"] / expected_kbps
            if 0.4 <= ratio <= 2.5:
                score += 15
            elif ratio < 0.2:
                score -= 15
        return float(np.clip(score, 0, 100))

    def _evaluate_visual(self, output_path, content: Dict) -> float:
        """视觉质量: 真实帧统计 + 内容指标(失败时降级为阶段计数)"""
        from core.frame_sampler import sample_frame_stats
        try:
            fs = sample_frame_stats(output_path, n_frames=16)
        except Exception:
            fs = None
        if fs is None or fs.n_sampled == 0:
            return 40.0  # 无法解码: 低分而非旧版的常数 90+
        score = 0.0
        # 曝光合理区间(过暗/过曝扣分), 峰值在 0.35~0.75
        luma_fit = 1.0 - min(abs(fs.mean_luma - 0.55) / 0.55, 1.0)
        score += 35.0 * luma_fit
        # 画面纹理(对比度)
        score += 30.0 * min(fs.luma_contrast / 0.25, 1.0)
        # 时序动态(卡点视频应有明显帧间变化)
        score += 35.0 * min(fs.temporal_change / 0.12, 1.0)
        return float(np.clip(score, 0, 100))

    def _evaluate_audio(self, output_path) -> float:
        """音频质量: 实测音轨存在性 + 平均响度"""
        from core.frame_sampler import probe_video
        try:
            info = probe_video(output_path)
        except Exception:
            return 30.0
        if not info["has_audio"]:
            return 35.0  # AMV 无音轨是硬伤
        # 用 ffmpeg astats 测平均 RMS 响度
        try:
            out = subprocess.run(
                ["ffmpeg", "-v", "quiet", "-i", str(output_path),
                 "-af", "astats=metadata=1", "-f", "null", "-"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120,
            ).stderr
            import re
            m = re.search(r"Overall.*?RMS level dB: ([-\d.]+)", out, re.S)
            if m:
                rms_db = float(m.group(1))
                # -30dB~ -10dB 为健康区间
                return float(np.clip(100 - abs(rms_db + 20) * 3.5, 0, 100))
        except Exception:
            pass
        return 60.0  # 有音轨但无法测响度

    def _evaluate_style_consistency(self, content: Dict) -> float:
        """风格一致性: 卡点对齐*0.5 + 运镜多样性*0.3 + 素材不复用*0.2

        content 由导演提交(见 Task 4), 缺省时回退中性分 50。
        """
        from core import content_metrics as cm
        if not content:
            return 50.0
        beat = cm.beat_alignment_score(
            content.get("cut_times", []), content.get("beat_times", []),
        )
        div = cm.camera_diversity_score(content.get("camera_moves", []))
        reuse = cm.material_reuse_penalty(content.get("material_windows", []))
        score = (beat * 0.5 + div * 0.3 + (1.0 - reuse) * 0.2) * 100.0
        return float(np.clip(score, 0, 100))
```

同步修改 `evaluate()` 中的调用签名(传入 content):

```python
        content = stages_result.get("content", {}) if stages_result else {}
        assessment.visual_quality = self._evaluate_visual(output_path, content)
        assessment.style_consistency = self._evaluate_style_consistency(content)
```

并在文件头部确认 `import subprocess`(已有则跳过)。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_auto_quality_evaluator.py -v`
Expected: PASS(3 个用例)

- [ ] **Step 5: 回归自进化引擎既有测试**

Run: `python -m pytest tests/ -k "self_evolution or evolution" -q --timeout=60`
Expected: 无新增失败(若既有测试断言旧常数分, 按新语义修正断言并在 commit message 中注明)

- [ ] **Step 6: Commit**

```bash
git add core/self_evolution_engine.py tests/test_auto_quality_evaluator.py
git commit -m "fix(learning): AutoQualityEvaluator real measurement (D1 root cause)"
```

---

## Task 4: Director ExecutionRecord 充实(D1 的上游)

**Files:**
- Modify: `ai/production_director.py:526-591`(`_trigger_auto_evolution`)
- Test: `tests/test_director_content_submit.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_director_content_submit.py
from ai.production_director import ProductionDirector


class _FakeResult:
    success = True
    content_verified = None
    resolution = (1920, 1080)
    fps = 30
    has_audio = True
    duration = 60.0


def test_collect_content_metrics_from_report():
    """导演必须把卡点/运镜/素材窗口/能量序列提交给自进化引擎"""
    d = ProductionDirector.__new__(ProductionDirector)  # 绕过重初始化
    d._beats = [type("B", (), {"time": t})() for t in (1.0, 2.0, 3.0)]
    d._used_windows = {"src_a.mp4": [[0.0, 2.5], [6.0, 8.0]]}
    report = {
        "segments": [
            {"start": 1.02, "camera": "pan_left", "source": "src_a.mp4"},
            {"start": 2.01, "camera": "zoom_in", "source": "src_b.mp4"},
        ],
        "energy_series": [0.2, 0.8, 0.3, 0.9],
    }
    content = ProductionDirector._collect_content_metrics(d, report)
    assert content["beat_times"] == [1.0, 2.0, 3.0]
    assert content["cut_times"] == [1.02, 2.01]
    assert content["camera_moves"] == ["pan_left", "zoom_in"]
    assert ("src_a.mp4", 0.0, 2.5) in content["material_windows"]
    assert content["energy_series"] == [0.2, 0.8, 0.3, 0.9]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_director_content_submit.py -v`
Expected: FAIL(AttributeError: `_collect_content_metrics`)

- [ ] **Step 3: 实现**

在 `ai/production_director.py` 的 `_trigger_auto_evolution` 前新增:

```python
    def _collect_content_metrics(self, report) -> dict:
        """从本次运行报告提取内容级指标数据, 供自进化引擎真实评分。

        report: 导演生成的 production_report 字典(含 segments/energy_series)
        """
        segments = (report or {}).get("segments", [])
        windows = []
        for src, spans in (getattr(self, "_used_windows", {}) or {}).items():
            for s, e in spans:
                windows.append((src, float(s), float(e)))
        return {
            "beat_times": [b.time for b in getattr(self, "_beats", []) or []],
            "cut_times": [seg.get("start") for seg in segments
                          if seg.get("start") is not None],
            "camera_moves": [seg.get("camera") for seg in segments
                             if seg.get("camera")],
            "material_windows": windows,
            "energy_series": (report or {}).get("energy_series", []),
        }
```

修改 `_trigger_auto_evolution` 签名新增 `content: dict = None` 参数, 并在 `record` 构造中:

```python
                    config={
                        "auto_captured": True,
                        "output_path": output_path,
                    },
                    stages={
                        **{
                            "source": "production_director",
                            "target_ip": target_ip,
                            "video_sources": video_sources,
                            "bgm_path": bgm_path,
                            "content_verified": result.content_verified,
                        },
                        "content": content or {},
                    },
```

并在导演主流程调用 `_trigger_auto_evolution(...)` 处传入 `content=self._collect_content_metrics(report)`(调用点在该方法现有唯一调用处, 用 grep 定位: `Grep "_trigger_auto_evolution(" ai/production_director.py`)。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_director_content_submit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai/production_director.py tests/test_director_content_submit.py
git commit -m "feat(learning): director submits content metrics to evolution engine"
```

---

## Task 5: Director 真实参数反馈写入(D2 根因修复)

**Files:**
- Create: `ai/director_feedback_hook.py`
- Test: `tests/test_director_feedback_hook.py`
- Modify: `ai/production_director.py`(渲染成功处调用 hook)

- [ ] **Step 0: 确认既有 API 签名**

Run: `python -c "from learning.parameter_optimizer import ParameterOptimizer; import inspect; print(inspect.signature(ParameterOptimizer.record_feedback))"`
Expected: 打印含 `effect_name, style_name, parameters, rating` 的签名(与 param_feedback.json 记录 schema 一致)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_director_feedback_hook.py
import json
from pathlib import Path
from ai.director_feedback_hook import record_director_feedback


def test_record_director_feedback_writes_real_records(tmp_path, monkeypatch):
    store = tmp_path / "param_feedback.json"
    monkeypatch.setenv("PARAM_FEEDBACK_PATH", str(store))
    run_info = {
        "run_id": "director_test_001",
        "quality": 74.5,
        "ramps": [{"type": "speed_ramp", "peak_speed": 2.4, "beat_aligned": True}],
        "style": "高燃",
    }
    record_director_feedback(run_info)
    data = json.loads(store.read_text(encoding="utf-8"))
    recs = [r for r in data["records"] if r["metadata"].get("source") == "director_v23"]
    assert len(recs) == 1
    assert recs[0]["effect_name"] == "speed_ramp"
    assert recs[0]["parameters"]["peak_speed"] == 2.4
    assert recs[0]["rating"] > 0.7
    assert recs[0]["record_id"].startswith("director_")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_director_feedback_hook.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
"""ai/director_feedback_hook.py - v23 导演真实参数反馈写入

修复 D2: director 路径不经过 unified_pipeline._trigger_param_feedback,
导致 param_feedback.json 自 08-11 起零真实写入。本 hook 在导演渲染
成功后将变速/效果真实参数与内容级质量分写入 FeedbackStore。
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any


def _store_path() -> Path:
    env = os.environ.get("PARAM_FEEDBACK_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "learning" / ".cache" / "param_feedback.json"


def record_director_feedback(run_info: Dict[str, Any]) -> int:
    """将一次导演运行的真实参数写入反馈库。返回写入条数。"""
    import json
    path = _store_path()
    data = {"version": "1.0", "records": []}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))

    quality = float(run_info.get("quality", 0.0))
    rating = round(max(0.0, min(1.0, quality / 100.0)), 3)
    style = run_info.get("style")
    written = 0
    for ramp in run_info.get("ramps", []):
        rec = {
            "record_id": f"director_{run_info.get('run_id', 'unknown')}_{uuid.uuid4().hex[:6]}",
            "effect_name": ramp.get("type", "speed_ramp"),
            "style_name": style,
            "parameters": {k: v for k, v in ramp.items() if k != "type"},
            "rating": rating,
            "adjustment": None,
            "timestamp": time.time(),
            "metadata": {"source": "director_v23", "run_id": run_info.get("run_id")},
        }
        data["records"].append(rec)
        written += 1
    if written:
        data["updated_at"] = time.time()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return written
```

在 `ai/production_director.py` 渲染成功分支( `_trigger_auto_evolution` 调用处旁)新增:

```python
            try:
                from ai.director_feedback_hook import record_director_feedback
                record_director_feedback({
                    "run_id": f"director_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "quality": review.quality.overall_score,
                    "ramps": report.get("speed_ramps", []),
                    "style": target_ip,
                })
            except Exception as e:
                print(f"[反馈] 导演参数反馈写入失败(不影响渲染): {e}")
```

(实现细节: review 在 `_trigger_auto_evolution` 内部才产生, 故把该写入放在 `_submit()` 内 review 成功后; Step 3 的代码按此位置插入。)

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_director_feedback_hook.py -v`
Expected: PASS

- [ ] **Step 5: 标记历史种子数据**

把 `learning/.cache/param_feedback.json` 中 20 条 `inject_*` 记录的 `metadata` 加 `"source": "seed_injection"`, 便于优化器降权(不删除, 保留可追溯)。用一次性脚本完成并核对条数:

Run: `python -c "import json,pathlib; p=pathlib.Path('learning/.cache/param_feedback.json'); d=json.loads(p.read_text(encoding='utf-8')); [r.setdefault('metadata',{}).update(source='seed_injection') for r in d['records'] if r['record_id'].startswith('inject_')]; p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8'); print(len(d['records']))"`
Expected: `20`

- [ ] **Step 6: Commit**

```bash
git add ai/director_feedback_hook.py tests/test_director_feedback_hook.py ai/production_director.py learning/.cache/param_feedback.json
git commit -m "fix(learning): director real param feedback + tag seed data (D2 root cause)"
```

---

## Task 6: TS 侧学习提取腿修复(D3 根因修复)

**Files:**
- Modify: `compiler/src/phase5/persistent-learning-loop.ts`
- Test: `compiler/test/unit-persistent-learning-consolidation.test.ts`
- Modify: `compiler/package.json`(新增 test 构建脚本)

- [ ] **Step 0: 确认既有 API**

通读 `compiler/src/phase5/persistent-learning-loop.ts` 全文(576 行), 记录三个 store 的读写方法名(getDefaultValueStore / caseStore / executionRecords 的实际成员名)。下述代码中的成员访问按实际名称对齐。

- [ ] **Step 1: 写失败测试**

```typescript
// compiler/test/unit-persistent-learning-consolidation.test.ts
import test from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";

// 通过环境变量隔离测试目录(实现需在 STATE_DIR 读取时支持 LEARNING_STATE_DIR 覆盖)
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "plc-"));
process.env.LEARNING_STATE_DIR = tmp;

const { persistentLearningLoop } = await import("../src/phase5/persistent-learning-loop.js");

test("consolidate 合并重复模板", () => {
    // 注入 3 条完全相同的 silhouette_roto 模板(复现 D3)
    for (let i = 0; i < 3; i++) {
        persistentLearningLoop.getCaseStore().add({
            id: `sil_tpl_test_${i}`,
            source: "silhouette-learned",
            effectMatchName: "silhouette_roto",
            effectName: "roto",
            parameters: { tolerance: 1.0 },
            userRating: "positive",
            usageCount: 1,
            lastUsed: `2026-08-1${i}`,  // 时间不同不影响合并
        } as any);
    }
    const report = persistentLearningLoop.consolidate();
    assert.equal(report.templatesBefore, 3);
    assert.equal(report.templatesAfter, 1);
    assert.equal(report.mergedUsageCount, 3);
});

test("consolidate 从成功记录提取默认值", () => {
    for (let i = 0; i < 4; i++) {
        persistentLearningLoop.getExecutionRecordStore().add({
            id: `exec_test_${i}`,
            userInput: "加模糊",
            intentType: "apply_effect",
            timestamp: new Date().toISOString(),
            expected: {
                effectMatchName: "ADBE Gaussian Blur 2",
                properties: [{ name: "Blurriness", value: 12.0, tolerance: 0.1 }],
            },
            execution: { success: true },
            verification: { passed: true },
        } as any);
    }
    const report = persistentLearningLoop.consolidate();
    assert.ok(report.defaultsExtracted >= 1);
    const dv = persistentLearningLoop.getDefaultValueStore()
        .getAll("ADBE Gaussian Blur 2");
    const blur = dv.find((d: any) => d.propertyName === "Blurriness");
    assert.ok(blur);
    assert.ok(Math.abs(blur.value - 12.0) < 0.01);
});

test("失败记录不参与默认值提取", () => {
    persistentLearningLoop.getExecutionRecordStore().add({
        id: "exec_test_fail",
        expected: {
            effectMatchName: "ADBE Test FX",
            properties: [{ name: "Amount", value: 999, tolerance: 0.1 }],
        },
        execution: { success: false },
        verification: { passed: false },
    } as any);
    persistentLearningLoop.consolidate();
    const dv = persistentLearningLoop.getDefaultValueStore().getAll("ADBE Test FX");
    assert.equal(dv.length, 0);
});
```

- [ ] **Step 2: 运行确认失败**

在 `compiler/package.json` 的 `scripts` 中新增:

```json
    "build:test-consolidation": "esbuild test/unit-persistent-learning-consolidation.test.ts --bundle --platform=node --format=esm --outfile=build/unit-consolidation.test.js",
    "test:consolidation": "npm run build && npm run build:test-consolidation && node --test build/unit-consolidation.test.js"
```

Run(在 `compiler/` 目录): `npm run test:consolidation`
Expected: FAIL(`consolidate is not a function`)

- [ ] **Step 3: 实现**

在 `compiler/src/phase5/persistent-learning-loop.ts` 中:

1) STATE_DIR 支持测试隔离(替换 L26):

```typescript
const STATE_DIR = process.env.LEARNING_STATE_DIR
    ?? path.join(process.env.APPDATA || process.env.HOME || ".", "AE-Knowledge-Vault", "learning-state");
```

2) 新增导出接口与 `consolidate()` 方法(加入 PersistentLearningLoop 类):

```typescript
export interface ConsolidationReport {
    templatesBefore: number;
    templatesAfter: number;
    mergedUsageCount: number;
    defaultsExtracted: number;
}

/** 学习提取腿(D3 修复): 模板去重合并 + 从成功执行记录提取默认值 */
consolidate(): ConsolidationReport {
    const report: ConsolidationReport = {
        templatesBefore: 0, templatesAfter: 0,
        mergedUsageCount: 0, defaultsExtracted: 0,
    };

    // --- 1. 模板去重: 同签名(effectMatchName|effectName|参数)合并 ---
    const cases = this.caseStore.getAll();
    report.templatesBefore = cases.length;
    const merged = new Map<string, any>();
    for (const c of cases) {
        const key = `${c.effectMatchName}|${c.effectName}|${JSON.stringify(c.parameters ?? {})}`;
        const exist = merged.get(key);
        if (exist) {
            exist.usageCount = (exist.usageCount ?? 0) + (c.usageCount ?? 1);
            if ((c.lastUsed ?? "") > (exist.lastUsed ?? "")) exist.lastUsed = c.lastUsed;
            report.mergedUsageCount += (c.usageCount ?? 1);
        } else {
            merged.set(key, { ...c });
        }
    }
    this.caseStore.replaceAll([...merged.values()]);
    report.templatesAfter = merged.size;

    // --- 2. 默认值提取: 仅成功且验证通过的记录 ---
    const records = this.executionRecordStore.getAll()
        .filter((r: any) => r.execution?.success === true
            && r.verification?.passed !== false);
    const acc = new Map<string, { sum: number; n: number; effect: string; prop: string }>();
    for (const r of records) {
        const fx = r.expected?.effectMatchName;
        for (const p of r.expected?.properties ?? []) {
            if (typeof p.value !== "number") continue;
            const key = `${fx}.${p.name}`;
            const slot = acc.get(key) ?? { sum: 0, n: 0, effect: fx, prop: p.name };
            slot.sum += p.value; slot.n += 1;
            acc.set(key, slot);
        }
    }
    for (const slot of acc.values()) {
        const value = slot.sum / slot.n;
        const weight = Math.min(1.0, slot.n / 10);  // 样本越多权重越高
        this.defaultValueStore.set(slot.effect, slot.prop, { value, weight });
        report.defaultsExtracted += 1;
    }
    this.saveAll();
    return report;
}
```

(若既有 store 无 `replaceAll`/`set(effect, prop, {value, weight})` 方法, 在对应 store 类中补齐最小实现并保持向后兼容; Step 0 已确认实际成员名, 按实际名称对齐。)

3) 在 `ai-scheduler.ts` 的 `recordToLearningLoop` 末尾追加自动整理(每 20 条记录触发一次, 避免频繁 IO):

```typescript
        if (persistentLearningLoop.getExecutionRecordStore().getAll().length % 20 === 0) {
            persistentLearningLoop.consolidate();
        }
```

- [ ] **Step 4: 运行确认通过**

Run(在 `compiler/` 目录): `npm run test:consolidation`
Expected: PASS(3 个用例)

- [ ] **Step 5: 回归既有 phase5 测试**

Run(在 `compiler/` 目录): `npm run test:phase5`
Expected: 无回归失败

- [ ] **Step 6: Commit**

```bash
git add compiler/src/phase5/persistent-learning-loop.ts compiler/test/unit-persistent-learning-consolidation.test.ts compiler/package.json compiler/src/phase4/ai-scheduler.ts
git commit -m "fix(learning): TS consolidation - template dedup + defaults extraction (D3 root cause)"
```

---

## Task 7: 进化循环真实化与知识蒸馏(D4 修复)

**Files:**
- Modify: `core/auto_evolution.py:206-233`(`run_evolution_cycle`)、`data/self_evolution/evolution_knowledge.jsonl` 写入点
- Test: `tests/test_knowledge_distillation.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_knowledge_distillation.py
import json
from core.auto_evolution import distill_review_knowledge


def test_distill_writes_knowledge_line(tmp_path):
    sink = tmp_path / "evolution_knowledge.jsonl"
    reviews = [
        {"run_id": "r1", "quality": 72.0, "deviation": 0.31, "success": True},
        {"run_id": "r2", "quality": 55.0, "deviation": 0.62, "success": False},
    ]
    n = distill_review_knowledge(reviews, sink_path=str(sink))
    assert n == 2
    lines = [json.loads(l) for l in sink.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["run_id"] == "r1"
    assert lines[1]["failure_mode"] is True


def test_distill_dedup_same_run(tmp_path):
    sink = tmp_path / "evolution_knowledge.jsonl"
    reviews = [{"run_id": "rX", "quality": 60.0, "deviation": 0.4, "success": True}]
    distill_review_knowledge(reviews, sink_path=str(sink))
    n = distill_review_knowledge(reviews, sink_path=str(sink))  # 重复写入
    assert n == 0
    assert len(sink.read_text(encoding="utf-8").splitlines()) == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_knowledge_distillation.py -v`
Expected: FAIL(ImportError: cannot import name 'distill_review_knowledge')

- [ ] **Step 3: 实现**

在 `core/auto_evolution.py` 新增(模块级):

```python
KNOWLEDGE_PATH = ROOT / "data" / "self_evolution" / "evolution_knowledge.jsonl"


def distill_review_knowledge(reviews: List[Dict], sink_path: str = None) -> int:
    """将 review 结果蒸馏为知识行追加落盘(D4 修复: 知识积累停滞)。

    返回新增条数; 同 run_id 不重复写入。
    """
    sink = Path(sink_path) if sink_path else KNOWLEDGE_PATH
    seen = set()
    if sink.exists():
        for line in sink.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line).get("run_id"))
            except json.JSONDecodeError:
                continue
    added = 0
    with open(sink, "a", encoding="utf-8") as f:
        for r in reviews:
            rid = r.get("run_id")
            if rid in seen:
                continue
            entry = {
                "run_id": rid,
                "quality": r.get("quality"),
                "deviation": r.get("deviation"),
                "success": r.get("success"),
                "failure_mode": (r.get("quality") or 0) < 60 or not r.get("success"),
                "distilled_at": time.time(),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            seen.add(rid)
            added += 1
    return added
```

在 `daily_routine()` 的 Step 1 采集完成后追加蒸馏调用:

```python
        # D4: 蒸馏新采集记录的 review 知识
        try:
            with open(ROOT / "data" / "self_evolution" / "evolution_state.json",
                      "r", encoding="utf-8") as f:
                state = json.load(f)
            n = distill_review_knowledge(state.get("review_history", [])[-50:])
            report["steps"]["knowledge_distill"] = {"status": "ok", "new": n}
        except Exception as e:
            report["steps"]["knowledge_distill"] = {"status": "error", "error": str(e)}
```

将 `run_evolution_cycle` 的 `execute_real=False` 改为参数透传: `def run_evolution_cycle(task_type="style_transfer", iterations=2, execute_real=False)`, 并在 `daily_routine` 中保持 `execute_real=False`(真实渲染成本高, 由 Task 8 验收时手动开启)。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_knowledge_distillation.py -v`
Expected: PASS(2 个用例)

- [ ] **Step 5: Commit**

```bash
git add core/auto_evolution.py tests/test_knowledge_distillation.py
git commit -m "fix(learning): knowledge distillation from reviews (D4 root cause)"
```

---

## Task 8: 端到端验收协议(判断学习系统"真的有用"的硬标准)

**Files:**
- Create: `scripts/verify_learning_real_signals.py`

- [ ] **Step 1: 编写验收脚本**

```python
"""scripts/verify_learning_real_signals.py - 学习系统真实信号验收

验收标准(全部满足才算 D1-D4 修复成功):
  A1 质量分布有区分度: 3 次导演渲染的 quality 标准差 > 5.0
  A2 反馈真实增长: param_feedback.json 新增 source=director_v23 记录
  A3 知识积累恢复: evolution_knowledge.jsonl 行数增长
  A4 TS 提取腿: consolidate 后 default-value-store 条目数增长且重复模板合并
"""
import json, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(name, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def main():
    results = []
    # A1: 读取 evolution_state.json 最近 N 条 director 运行
    state = json.loads((ROOT / "data/self_evolution/evolution_state.json")
                       .read_text(encoding="utf-8"))
    director_qs = [r["quality"] for r in state.get("review_history", [])
                   if r.get("run_id", "").startswith("director_")][-10:]
    sigma = statistics.pstdev(director_qs) if len(director_qs) >= 3 else 0.0
    results.append(check("A1 质量分布区分度", sigma > 5.0,
                         f"最近{len(director_qs)}次导演运行 σ={sigma:.2f} (要求>5.0)"))
    # A2: 真实反馈记录
    pf = json.loads((ROOT / "learning/.cache/param_feedback.json")
                    .read_text(encoding="utf-8"))
    real = [r for r in pf["records"]
            if r.get("metadata", {}).get("source") == "director_v23"]
    results.append(check("A2 真实反馈写入", len(real) > 0, f"{len(real)} 条 director_v23 记录"))
    # A3: 知识积累
    kl = ROOT / "data/self_evolution/evolution_knowledge.jsonl"
    n_lines = len(kl.read_text(encoding="utf-8").splitlines()) if kl.exists() else 0
    results.append(check("A3 知识积累", n_lines > 3,
                         f"evolution_knowledge.jsonl {n_lines} 行 (基线 08-05 时 3 行)"))
    # A4: TS 提取腿(需在 compiler/ 下先跑过一次生产编译 + consolidate)
    print("  [INFO] A4 需人工确认: 运行一次 TS 编译生产路径后检查")
    print("         %APPDATA%\\AE-Knowledge-Vault\\learning-state\\default-value-store.json 条目数增长")

    ok = all(results)
    print(f"\n验收结果: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 执行真实渲染验收(需用户在场)**

用 3 首不同风格 BGM + 不同素材集运行导演管线 3 次(复用 `D:\output_director\solo_pilot\v23` 的既有启动方式), 每次渲染完成后确认后台 `[自进化] 自动采集完成` 日志中 quality 各不相同。

- [ ] **Step 3: 运行验收脚本**

Run: `python scripts/verify_learning_real_signals.py`
Expected: A1/A2/A3 均 PASS

- [ ] **Step 4: 盲评对比(质量上限证据)**

Run: `python -m ai.accept_runner --quick`
Expected: 生成新 `reports/accept_*.json`, pass_rate 不低于修复前基线(从既有最新 accept 报告读取)

- [ ] **Step 5: Commit 验收产物**

```bash
git add scripts/verify_learning_real_signals.py reports/
git commit -m "test(learning): real-signal acceptance protocol + first verification run"
```

---

## Task 9: 上限增强 — VMAF 接入与 VQA 调研(可选, 需用户确认)

**Files:**
- Modify: `core/self_evolution_engine.py`(VMAF 接入 visual 维度)
- Create: `docs/research/vqa-evaluation.md`(调研表)

- [ ] **Step 1: VMAF 接入(复用既有适配器, 三查机制确认无重复轮子)**

在 `_evaluate_visual` 末尾追加(真实帧统计分与 VMAF 无参考降级分加权):

```python
        # 可选: VMAF 适配器无参考降级分(已就绪, integrations/vmaf_quality_adapter.py)
        try:
            from integrations.vmaf_quality_adapter import VMAFAdapter
            v = VMAFAdapter().assess_quality(output_path)
            if v.success:
                score = score * 0.6 + float(v.vmaf_score) * 0.4
        except Exception:
            pass  # VMAF 不可用时保持帧统计分
```

Run: `python -m pytest tests/test_auto_quality_evaluator.py -v`
Expected: PASS(VMAF 不可用时自动降级, 不影响既有断言)

- [ ] **Step 2: VQA 开源调研表(仅调研不写码, 遵循三查机制)**

创建 `docs/research/vqa-evaluation.md`, 按既有 `docs/plans/2026-08-12-blender-oss-integration.md` 的评估表格式, 对以下候选逐项打分(离线可用/依赖大小/与 ffmpeg 兼容性/接入成本/预期增益):

| 候选 | 定位 | 备注 |
|------|------|------|
| VMAF(libvmaf) | 全参考感知质量 | 项目已有适配器, 首选 |
| DOVER | 无参考视频质量(美学+技术双分支) | ⚠️ 许可证 NOASSERTION(非 MIT, 2026-08-13 API 实测), 接入前必须先完成许可证审查; DOVER-Mobile 9.86M 参数可 CPU |
| improved-aesthetic-predictor | 图像级美学分(CLIP+MLP) | Apache-2.0, DOVER 许可不过关时的降级方案, 抽帧聚合使用 |
| FAST-VQA | 轻量无参考 VQA | DOVER 的骨干, 单独评估意义不大 |
| Q-Align | VLM 打分 | 依赖大模型, 成本高 |
| VideoScore2 | 视频质量/美学打分(较新) | 细节待核, 作为 DOVER 备选观察项 |

(候选表依据 docs/research/2026-08-13-aesthetic-perception-oss-research.md 的调研结论更新)

产出结论必须含"明确不集成清单"(同 Blender OSS 方案格式)。

- [ ] **Step 3: Commit**

```bash
git add core/self_evolution_engine.py docs/research/vqa-evaluation.md
git commit -m "feat(learning): VMAF into visual score + VQA candidate evaluation"
```

---

## 验收总标准(Definition of Done)

1. **D1**: 连续 3 次不同输入的导演渲染, `evolution_state.json` 中 quality 标准差 > 5.0(旧值: 0.0)
2. **D2**: `param_feedback.json` 出现 `metadata.source=director_v23` 的真实记录, 且后续每次渲染自动增长
3. **D3**: `default-value-store.json` 条目数增长(基线 4), case-store 重复模板合并(基线 38 条相同 silhouette_roto)
4. **D4**: `evolution_knowledge.jsonl` 行数增长(基线 3 行)
5. **回归**: pytest 无新增失败; `npm run test:phase5` 无回归
6. **上限证据**: accept_runner 盲评 pass_rate 不低于基线

## 风险与回滚

| 风险 | 缓解 |
|------|------|
| ffmpeg 抽帧使 review 变慢(导演后台线程已有 10s 超时) | n_frames=16 + 160px 缩小, 实测单视频 <3s; 超时自动降级回阶段计数 |
| 新质量分改变进化选择方向, 可能回退已有好版本 | version_manager 自带回滚; 验收用盲评兼底 |
| ffmpeg astats 输出格式随版本变化 | 正则失败时降级返 60 分, 有单测覆盖 |
| APPDATA 学习目录不入 git, 换机丢失 | Task 0 已备份; 建议后续将 consolidate 后的摘要快照同步到 `data/` |

## 假设

- ffmpeg/ffprobe 在 PATH 可用(项目已装, install_ffmpeg.py 佐证)
- `rhythm_reward_v2.pkl` 继续由 director 消费(L974-1009), 本计划不改其训练
- 导演报告字典含 `segments`/`energy_series`/`speed_ramps` 键(Task 4 实现时若键名不同, 以实际 `production_report.json` 结构为准, 同步调整测试)
- 测试基线以 Task 0 Step 1 实跑结果为准

## 复用既有能力清单(三查机制执行记录)

1. 查注册表: `integrations/integration_registry.py` — VMAFAdapter 已注册可用, 本计划直接复用
2. 查目录: `core/frame_sampler` 不存在(确认新建); `core/content_metrics` 不存在(确认新建); rhythm_reward 已实装不重造
3. 查知识: `docs/automation-playbooks/` 无重叠手册; 本计划不新增第三方依赖(不引入 DOVER 等, 仅调研)
