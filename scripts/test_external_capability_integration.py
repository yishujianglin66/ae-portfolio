# -*- coding: utf-8 -*-
"""外部前沿能力融入验收测试

图1 Prime Agent (Prime Intellect): /refine自改进循环 + 守护心跳 + 会话分离重连
图2 JoyAI-Video-Edit (京东开源): 因果流式编辑(不等完整视频) + 30FPS吞吐基准

融入模块:
- core/refine_loop.py: DirectorRefineLoop (轨迹驱动确定性修补, 零LLM成本)
- core/streaming_pipeline.py: StreamingCausalScheduler + ThroughputBenchmark
  + HeartbeatMonitor
"""
import copy
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = 0
FAIL = 0
FAILURES = []


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


def make_defect_script():
    """构造带五类缺陷的剧本: 切点离拍/三段同运镜/无energy/均分时长/无缓动"""
    segs = []
    types = ["intro", "build", "drop", "break", "outro"]
    for i, t in enumerate(types):
        segs.append({
            "name": f"seg_{t}", "type": t,
            "start": i * 3.0, "end": (i + 1) * 3.0, "duration": 3.0,
            "camera": {"camera_id": "push", "movement": "push",
                       "speed": "normal"},
            "cut_times": [i * 3.0 + 0.13],   # 故意偏离拍点
            "max_scale": 200 if t == "drop" else 100,
        })
    return {"title": "defect", "bpm": 120, "total_duration": 15,
            "segments": segs}


print("=== 1. Prime Agent /refine: 节拍吸附 ===")
from core.refine_loop import DirectorRefineLoop, get_refine_loop  # noqa: E402
from core.director_scorer import DirectorQualityScorer  # noqa: E402

loop = DirectorRefineLoop(target_score=95, max_iterations=3)
script = make_defect_script()
result = loop.refine_script(script)
scorer = DirectorQualityScorer()
beat_after = scorer.score_beat_alignment(
    [c for s in result["script"]["segments"] for c in s.get("cut_times", [])],
    120)["score"]
check("离拍切点全部吸附BPM网格", beat_after >= 99.0, str(beat_after))
check("修补后总分提升", result["final_score"] > result["initial_score"],
      f"{result['initial_score']}→{result['final_score']}")
check("轨迹记录每轮action", all(t["actions"] for t in result["trajectory"]),
      str(result["trajectory"]))

print("\n=== 2. Prime Agent /refine: 运镜去重+多样化 ===")
movs = [(s.get("camera") or {}).get("camera_id", "")
        for s in result["script"]["segments"]]
triple = any(movs[i] == movs[i+1] == movs[i+2]
             for i in range(len(movs) - 2))
check("连续三段同运镜已消除", not triple, str(movs))
check("6段(含breath_break)运镜零重复",
      len(set(movs)) == len(movs) == 6, str(movs))

print("\n=== 3. Prime Agent /refine: 弧线补全+反模式 ===")
types_after = [s.get("type") for s in result["script"]["segments"]]
check("breath_break喘息点已插入", "breath_break" in types_after,
      str(types_after))
check("全段补energy_target",
      all("energy_target" in s for s in result["script"]["segments"]))
check("时长非均分(能量包络)",
      len(set(round(s["duration"], 2) for s in result["script"]["segments"]
              if s.get("type") != "breath_break")) > 1)
check("缓动已补全", all(s.get("easing")
                        for s in result["script"]["segments"]))
check("过大缩放钳制≤150",
      max(s.get("max_scale", 100) for s in result["script"]["segments"]) <= 150)

print("\n=== 4. Prime Agent: 收敛特性+心跳 ===")
check("轨迹含最弱维度标记",
      all(t["weakest"] for t in result["trajectory"]))
check("心跳逐轮记录", len(result["heartbeats"]) >= 1,
      str(len(result["heartbeats"])))
# 已达标剧本 → 零迭代早退
good = copy.deepcopy(result["script"])
r2 = loop.refine_script(good)
check("高分剧本早退(0-1次迭代)", r2["iterations"] <= 1,
      str(r2["iterations"]))
check("工厂函数可用", isinstance(get_refine_loop(), DirectorRefineLoop))
# 全流程refine带注入generator
class _StubGen:
    def generate_script(self, prompt, analyses, style):
        return make_defect_script()
r3 = loop.refine("测试高燃混剪", [{"duration": 10}], generator=_StubGen())
check("全流程refine(注入generator)", r3["final_score"] > r3["initial_score"],
      f"{r3['initial_score']}→{r3['final_score']}")
check("generator来源标记", r3["generator_used"] == "injected")

print("\n=== 5. JoyAI: 因果流式调度(不等完整视频) ===")
from core.streaming_pipeline import (  # noqa: E402
    StreamSegment, StreamingCausalScheduler, HeartbeatMonitor,
    ThroughputBenchmark, causal_benchmark)

sched = StreamingCausalScheduler()
e1 = sched.feed(StreamSegment("s1", payload="intro", frames=30, deps=[]))
check("首段无依赖即处理(流式不等完整视频)", e1 == ["s1"], str(e1))
e2 = sched.feed(StreamSegment("s3", payload="drop", frames=30, deps=["s2"]))
check("依赖未就绪段挂起", e2 == [] and sched.pending_ids == ["s3"],
      str(sched.pending_ids))
e3 = sched.feed(StreamSegment("s2", payload="build", frames=30, deps=["s1"]))
check("依赖就绪波次解锁(s2→s3连锁)", e3 == ["s2", "s3"], str(e3))
check("乱序到达最终全部完成", sched.done_ids == ["s1", "s2", "s3"],
      str(sched.done_ids))
check("重复feed幂等", sched.feed(StreamSegment("s1", payload="x")) == [])
outs = [o["seg_id"] for o in sched.outputs]
check("输出顺序满足因果(s2先于s3)", outs.index("s2") < outs.index("s3"),
      str(outs))

print("\n=== 6. JoyAI: 吞吐基准(对标30FPS实时) ===")
segs = [StreamSegment(f"b{i}", payload=i, frames=90,
                      deps=[f"b{i-1}"] if i > 0 else []) for i in range(50)]
report = causal_benchmark(segs, target_fps=30.0)
print(f"  [INFO] {report}")
check("50段全部因果处理", report["emitted"] == 50, str(report["emitted"]))
check("实测FPS>0", report["fps"] > 0, str(report["fps"]))
check("纯Python调度达实时门槛(≥30FPS)", report["is_realtime"],
      f"ratio={report['realtime_ratio']}")
check("吞吐报告含实时比字段",
      "realtime_ratio" in report and "segments_per_sec" in report)

print("\n=== 7. Prime Agent: 心跳守护+会话分离重连 ===")
hb = HeartbeatMonitor(timeout=2.0)
check("未心跳视为未启动", not hb.alive())
hb.heartbeat()
check("心跳后活性=True", hb.alive() and hb.beat_count == 1)
hb._last_beat = time.time() - 10
check("超时判定死亡", not hb.alive())

sched2 = StreamingCausalScheduler()
sched2.feed(StreamSegment("a1", payload="p1", frames=10, deps=[]))
sched2.feed(StreamSegment("a2", payload="p2", frames=10, deps=["a1"]))
sched2.feed(StreamSegment("a3", payload="p3", frames=10, deps=["a2"]))
ckpt = sched2.checkpoint()
check("快照含done/pending/帧数",
      ckpt["done"] == ["a1", "a2", "a3"] and ckpt["frames_processed"] == 30,
      str(ckpt))
# 模拟会话重连: 新调度器恢复含挂起段的快照
sched3 = StreamingCausalScheduler()
sched3x = StreamingCausalScheduler()
sched3x.feed(StreamSegment("c1", payload=1, frames=10, deps=[]))
sched3x.feed(StreamSegment("c2", payload=2, frames=10, deps=["cX"]))  # 依赖未来段
ckpt2 = sched3x.checkpoint()
check("挂起段进入快照", "c2" in ckpt2["pending"], str(ckpt2["pending"]))
sched3.restore(ckpt2)
check("重连后挂起段保留", sched3.pending_ids == ["c2"],
      str(sched3.pending_ids))
e4 = sched3.feed(StreamSegment("cX", payload=0, frames=10, deps=[]))
check("重连续传解锁挂起段(cX→c2)", e4 == ["cX", "c2"], str(e4))
check("重连后已完成段不重放", sched3.done_ids == ["c1", "c2", "cX"],
      str(sched3.done_ids))

print(f"\n{'='*50}\n外部能力融入结果: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("失败项:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
