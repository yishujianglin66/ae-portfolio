# -*- coding: utf-8 -*-
r"""T26: VLM多通道交叉标注管线 — 用多模态大模型重标注帧级IP标签。

通道设计:
  A: OpenAI GPT-4o-mini (视觉能力强, 成本低)
  B: 本地教师模型(EnsembleKB, 已有)
  C: (可选) SiliconFlow Qwen-VL / DashScope

仲裁: 2/3一致即采纳, 否则保留教师标签+标记低置信

Phase 2a: 先标注1000帧样本, 与教师标签对比, 量化提升
Phase 2b: 全量标注(可断点续传)

产物:
  D:\aot_corpus\vlm_labels_sample.json  — Phase 2a样本标注
  D:\aot_corpus\vlm_labels_full.json    — Phase 2b全量标注
  reports/t26_vlm_report.json           — 质量报告
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import random
import io
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
VLM_SAMPLE_OUT = Path(r"D:\aot_corpus\vlm_labels_sample.json")
VLM_FULL_OUT = Path(r"D:\aot_corpus\vlm_labels_full.json")
VLM_CKPT = Path(r"D:\aot_corpus\vlm_ckpt.json")
REPORT_DIR = ROOT / "reports"

# API配置 (SiliconFlow + Qwen3-VL-8B-Instruct)
VLM_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "sk-gwtbhthfdrjbjqljcntqatsvsvmrqytlpzxoilrgbphusvzh")
VLM_BASE_URL = "https://api.siliconflow.cn/v1"
VLM_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
VLM_MAX_RETRIES = 3
VLM_TIMEOUT = 60  # VL模型推理较慢，增加超时

# 采样参数
SAMPLE_SIZE = 1000
SAMPLE_SEED = 42

# 标注prompt (优化版: 限制IP范围+置信度校准)
IP_CANDIDATES = "进击的巨人、火影忍者、海贼王、鬼灭之刃、咒术回战、链锯人、FATE、黑岩射手、地缚少年花子君、无限滑板、灼眼的夏娜、猫和老鼠、时光代理人、灵笼、赛博朋克：边缘行者、原神、斩·赤红之瞳、某科学的超电磁炮、JOJO的奇妙冒险、Move、抽烟猫、浪客行、龙族、K、间谍过家家、葬送的芙莉莲、药屋少女的呢喃、我推的孩子、蓝色监狱、排球少年、我的英雄学院、Re:从零开始的异世界生活、为美好的世界献上祝福、无职转生、关于我转生变成史莱姆这档事、Overlord、一拳超人、灵能百分百、钢之炼金术师、死亡笔记、Code Geass、EVA、星际牛仔、攻壳机动队、心理测量者、来自深渊、迷宫饭、斗罗大陆、斗破苍穹、完美世界、凡人修仙传、一人之下、雾山五行、百妖谱、天官赐福、魔道祖师、伍六七、银魂、全职猎人、幽游白书、龙珠、数码宝贝、宝可梦、游戏王、名侦探柯南、蜡笔小新、哆啦A梦、美少女战士、魔卡少女樱、轻音少女、凉宫春日的忧郁、命运石之门、罪恶王冠、刀剑神域、在下坂本有何贵干、齐木楠雄的灾难、日常、月刊少女野崎同学、冰菓、黑之契约者、天元突破、新海诚、千与千寻、龙猫、风之谷、幽灵公主、哈尔的移动城堡、铃芽之旅、你的名字、天气之子、Promare、SSSS.GRIDMAN"

ANNOTATE_PROMPT = """你是一个专业的动漫识别专家。请分析这张图片：

1. 这张图来自哪个动漫作品？请从以下候选中选择（如果都不像，可以写"其他"并说明）：
   {candidates}
2. 画面中有哪些可辨识的角色？（如果看不清就写[]）
3. 这是什么类型的场景？（从以下选一个: battle/daily/dialog/flashback/landscape/ceremony/emotional/comedy）
4. 画面情绪基调？（从以下选一个: hot/warm/sad/tense/funny）

请严格返回JSON格式（不要其他文字，不要markdown代码块）:
{{
  "ip_top3": [{{"name": "动漫名", "confidence": 0.85}}, {{"name": "...", "confidence": 0.6}}, {{"name": "...", "confidence": 0.4}}],
  "characters": ["角色1", "角色2"],
  "scene_type": "battle",
  "mood": "hot"
}}

重要:
- confidence必须真实反映你的确信程度: 非常确定=0.9-1.0, 比较确定=0.7-0.9, 有点像=0.5-0.7, 不太确定=0.3-0.5
- 不要给所有结果都打0.98以上的高分
- 如果完全看不出是哪个动漫，ip_top3第一个写"其他"，confidence写0.3以下
- 动漫名用中文""".format(candidates=IP_CANDIDATES)


def _log(msg: str):
    print(f"[T26] {msg}", flush=True)


# ---------------------------------------------------------------- OpenAI通道
class OpenAIAnnotator:
    """GPT-4o-mini视觉标注通道"""
    
    def __init__(self):
        import openai
        self.client = openai.OpenAI(api_key=VLM_API_KEY, base_url=VLM_BASE_URL)
        self.model = VLM_MODEL
        self._cost = 0.0
    
    def annotate(self, img_path: str) -> Optional[dict]:
        """标注单帧, 返回解析后的JSON或None"""
        try:
            # 读取图片并编码为base64
            with open(img_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            
            for attempt in range(VLM_MAX_RETRIES):
                try:
                    resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": ANNOTATE_PROMPT},
                                {"type": "image_url", "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_data}",
                                    "detail": "low"
                                }}
                            ]
                        }],
                        max_tokens=500,
                        temperature=0.1,
                    )
                    text = resp.choices[0].message.content.strip()
                    
                    # 估算成本 (gpt-4o-mini: $0.15/1M input, $0.60/1M output)
                    usage = resp.usage
                    self._cost += (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1e6
                    
                    # 解析JSON
                    # 去掉可能的markdown代码块
                    if text.startswith("```"):
                        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                    
                    result = json.loads(text)
                    return result
                    
                except json.JSONDecodeError:
                    if attempt == VLM_MAX_RETRIES - 1:
                        _log(f"  JSON解析失败: {text[:100]}...")
                        return None
                except Exception as e:
                    if attempt == VLM_MAX_RETRIES - 1:
                        _log(f"  API错误: {e}")
                        return None
                    time.sleep(1)
        except Exception as e:
            _log(f"  读图失败: {e}")
            return None
    
    @property
    def cost(self):
        return self._cost


# ---------------------------------------------------------------- 教师通道
class TeacherAnnotator:
    """本地教师模型(T20伪标签)标注通道 — 直接读取已有伪标签"""
    
    def __init__(self):
        # 直接加载T20伪标签作为教师通道的参考
        self._cache = {}
        if PSEUDO_LABELS.exists():
            pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
            for p in pseudo:
                self._cache[Path(p["frame_path"]).name] = p
    
    def annotate(self, img_path: str) -> Optional[dict]:
        """从T20伪标签获取教师标注"""
        frame_name = Path(img_path).name
        entry = self._cache.get(frame_name)
        if entry:
            return {
                "ip_top3": [{"name": entry["ip"], "confidence": entry["confidence"]}],
                "characters": [],
                "scene_type": "unknown",
                "mood": "unknown",
            }
        return None


# ---------------------------------------------------------------- 仲裁逻辑
def consensus_vote(results: Dict[str, Optional[dict]]) -> dict:
    """三通道投票仲裁, 返回最终标签"""
    votes = {}
    annotators_detail = {}
    
    for channel, result in results.items():
        if result is None:
            continue
        annotators_detail[channel] = result.get("ip_top3", [{}])[0].get("name", "") if result.get("ip_top3") else ""
        top1 = annotators_detail[channel]
        if top1:
            votes[top1] = votes.get(top1, 0) + 1
    
    if not votes:
        return {"ip": "unknown", "confidence": 0.0, "source": "no_vote"}
    
    # 取票数最多的
    best_ip, best_votes = max(votes.items(), key=lambda x: x[1])
    total_voters = len([v for v in results.values() if v is not None])
    
    # 置信度: 一致率
    confidence = best_votes / max(total_voters, 1)
    
    # 合并其他信息
    best_result = None
    for ch, r in results.items():
        if r and annotators_detail.get(ch) == best_ip:
            best_result = r
            break
    
    merged = {
        "ip": best_ip,
        "ip_confidence": round(confidence, 3),
        "characters": best_result.get("characters", []) if best_result else [],
        "scene_type": best_result.get("scene_type", "unknown") if best_result else "unknown",
        "mood": best_result.get("mood", "unknown") if best_result else "unknown",
        "annotation_source": "vlm_consensus",
        "annotators": annotators_detail,
        "votes": votes,
    }
    return merged


# ---------------------------------------------------------------- 数据准备
def load_pseudolabel_frames() -> List[dict]:
    """加载T20伪标签帧列表"""
    if not PSEUDO_LABELS.exists():
        _log(f"伪标签不存在: {PSEUDO_LABELS}")
        return []
    pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
    _log(f"T20伪标签: {len(pseudo)}帧")
    return pseudo


def sample_frames(pseudo: List[dict], n: int, seed: int = 42) -> List[dict]:
    """分层抽样: 按置信度区间均匀采样"""
    random.seed(seed)
    
    # 按置信度分桶
    high = [p for p in pseudo if p["confidence"] >= 0.8]  # 高置信
    mid = [p for p in pseudo if 0.6 <= p["confidence"] < 0.8]  # 中置信
    low = [p for p in pseudo if p["confidence"] < 0.6]  # 低置信
    
    _log(f"置信度分布: high(>=0.8)={len(high)}, mid(0.6-0.8)={len(mid)}, low(<0.6)={len(low)}")
    
    # 分层抽样: 低置信过采样(这些最可能有错)
    n_high = int(n * 0.4)
    n_mid = int(n * 0.35)
    n_low = min(n - n_high - n_mid, len(low))
    
    sampled = []
    sampled.extend(random.sample(high, min(n_high, len(high))))
    sampled.extend(random.sample(mid, min(n_mid, len(mid))))
    sampled.extend(random.sample(low, n_low))
    
    random.shuffle(sampled)
    _log(f"抽样: {len(sampled)}帧 (high={min(n_high,len(high))}, mid={min(n_mid,len(mid))}, low={n_low})")
    return sampled


# ---------------------------------------------------------------- 主流程
def run_sample_annotation(n_frames: int = SAMPLE_SIZE):
    """Phase 2a: 标注n_frames帧样本, 对比教师标签"""
    _log("=" * 60)
    _log(f"Phase 2a: VLM样本标注 ({n_frames}帧)")
    _log("=" * 60)
    
    # 加载数据
    pseudo = load_pseudolabel_frames()
    if not pseudo:
        return None
    samples = sample_frames(pseudo, n_frames)
    
    # 初始化标注器
    _log("\n初始化标注器...")
    openai_ann = OpenAIAnnotator()
    _log(f"  VLM: {VLM_MODEL} (SiliconFlow)")
    
    # 逐帧标注
    results = []
    t0 = time.time()
    
    for i, entry in enumerate(samples):
        frame_path = entry["frame_path"]
        teacher_ip = entry["ip"]
        teacher_conf = entry["confidence"]
        
        if not Path(frame_path).exists():
            continue
        
        # OpenAI通道
        vlm_result = openai_ann.annotate(frame_path)
        
        # 仲裁(单通道: 仅VLM)
        if vlm_result and vlm_result.get("ip_top3"):
            vlm_ip = vlm_result["ip_top3"][0].get("name", "")
            vlm_conf = vlm_result["ip_top3"][0].get("confidence", 0)
        else:
            vlm_ip = ""
            vlm_conf = 0
        
        # 一致性判定
        agree = (vlm_ip == teacher_ip) if vlm_ip else None
        
        result_entry = {
            "frame_path": frame_path,
            "frame_name": Path(frame_path).name,
            "teacher_ip": teacher_ip,
            "teacher_confidence": teacher_conf,
            "vlm_ip": vlm_ip,
            "vlm_confidence": vlm_conf,
            "vlm_detail": vlm_result,
            "agree": agree,
            "scene_type": vlm_result.get("scene_type", "") if vlm_result else "",
            "mood": vlm_result.get("mood", "") if vlm_result else "",
            "characters": vlm_result.get("characters", []) if vlm_result else [],
        }
        results.append(result_entry)
        
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(samples) - i - 1) / rate
            _log(f"  进度: {i+1}/{len(samples)} | {elapsed:.0f}s | {rate:.1f}帧/s | ETA {eta:.0f}s | cost=${openai_ann.cost:.3f}")
    
    elapsed = time.time() - t0
    
    # 统计
    total = len(results)
    agreed = sum(1 for r in results if r["agree"] is True)
    disagreed = sum(1 for r in results if r["agree"] is False)
    no_vlm = sum(1 for r in results if r["agree"] is None)
    
    _log(f"\n{'='*60}")
    _log(f"Phase 2a 结果: {total}帧标注完成")
    _log(f"  耗时: {elapsed:.1f}s ({total/elapsed:.1f}帧/s)")
    _log(f"  成本: ${openai_ann.cost:.4f}")
    _log(f"  VLM-教师一致: {agreed}/{total} = {agreed/max(total,1):.3f}")
    _log(f"  VLM-教师分歧: {disagreed}/{total} = {disagreed/max(total,1):.3f}")
    _log(f"  VLM无结果: {no_vlm}/{total}")
    
    # 分歧分析
    if disagreed > 0:
        _log(f"\n  分歧样本(前10):")
        for r in results:
            if r["agree"] is False:
                _log(f"    {r['frame_name'][:40]:40s} | 教师={r['teacher_ip']:15s}(conf={r['teacher_confidence']:.2f}) VLM={r['vlm_ip']:15s}(conf={r['vlm_confidence']:.2f})")
                if sum(1 for x in results if x["agree"] is False) > 10:
                    break
    
    # 场景/情绪分布
    scene_dist = Counter(r["scene_type"] for r in results if r["scene_type"])
    mood_dist = Counter(r["mood"] for r in results if r["mood"])
    _log(f"\n  场景分布: {dict(scene_dist.most_common(8))}")
    _log(f"  情绪分布: {dict(mood_dist.most_common(8))}")
    
    # 保存
    VLM_SAMPLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    VLM_SAMPLE_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n  结果保存: {VLM_SAMPLE_OUT}")
    
    # 报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": "2a_sample",
        "n_frames": total,
        "elapsed_s": round(elapsed, 1),
        "cost_usd": round(openai_ann.cost, 4),
        "agree_rate": round(agreed / max(total, 1), 4),
        "disagree_rate": round(disagreed / max(total, 1), 4),
        "scene_distribution": dict(scene_dist.most_common()),
        "mood_distribution": dict(mood_dist.most_common()),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "t26_vlm_sample_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return report


def run_full_annotation():
    """Phase 2b: 全量标注(可断点续传)"""
    _log("=" * 60)
    _log("Phase 2b: VLM全量标注")
    _log("=" * 60)
    
    pseudo = load_pseudolabel_frames()
    if not pseudo:
        return None
    
    # 断点续传
    done_frames = set()
    existing_results = []
    if VLM_CKPT.exists():
        try:
            ckpt = json.loads(VLM_CKPT.read_text(encoding="utf-8"))
            done_frames = set(ckpt.get("done_frames", []))
            existing_results = ckpt.get("results", [])
            _log(f"断点续传: {len(done_frames)}帧已完成")
        except Exception:
            pass
    
    # 过滤已完成
    remaining = [p for p in pseudo if p["frame_path"] not in done_frames]
    _log(f"剩余: {len(remaining)}帧 (总{len(pseudo)}, 已完成{len(done_frames)})")
    
    openai_ann = OpenAIAnnotator()
    results = list(existing_results)
    t0 = time.time()
    CKPT_INTERVAL = 500
    
    for i, entry in enumerate(remaining):
        frame_path = entry["frame_path"]
        if not Path(frame_path).exists():
            continue
        
        vlm_result = openai_ann.annotate(frame_path)
        
        if vlm_result and vlm_result.get("ip_top3"):
            vlm_ip = vlm_result["ip_top3"][0].get("name", "")
            vlm_conf = vlm_result["ip_top3"][0].get("confidence", 0)
        else:
            vlm_ip = ""
            vlm_conf = 0
        
        agree = (vlm_ip == entry["ip"]) if vlm_ip else None
        
        results.append({
            "frame_path": frame_path,
            "frame_name": Path(frame_path).name,
            "teacher_ip": entry["ip"],
            "teacher_confidence": entry["confidence"],
            "vlm_ip": vlm_ip,
            "vlm_confidence": vlm_conf,
            "vlm_detail": vlm_result,
            "agree": agree,
            "scene_type": vlm_result.get("scene_type", "") if vlm_result else "",
            "mood": vlm_result.get("mood", "") if vlm_result else "",
            "characters": vlm_result.get("characters", []) if vlm_result else [],
        })
        done_frames.add(frame_path)
        
        # 断点保存
        if (i + 1) % CKPT_INTERVAL == 0:
            VLM_CKPT.write_text(json.dumps({
                "done_frames": list(done_frames),
                "results": results,
            }, ensure_ascii=False), encoding="utf-8")
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            _log(f"  [CKPT] {len(done_frames)}/{len(pseudo)} | {rate:.1f}帧/s | cost=${openai_ann.cost:.2f}")
    
    # 最终保存
    VLM_FULL_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    VLM_CKPT.unlink(missing_ok=True)
    
    elapsed = time.time() - t0
    total = len(results)
    agreed = sum(1 for r in results if r["agree"] is True)
    
    _log(f"\n全量标注完成: {total}帧, 一致率={agreed/max(total,1):.3f}, 耗时={elapsed:.0f}s, cost=${openai_ann.cost:.2f}")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["2a", "2b"], default="2a", help="2a=样本标注, 2b=全量标注")
    parser.add_argument("--n", type=int, default=SAMPLE_SIZE, help="Phase 2a样本数")
    args = parser.parse_args()
    
    if args.phase == "2a":
        run_sample_annotation(args.n)
    else:
        run_full_annotation()
