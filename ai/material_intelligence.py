#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaterialIntelligence — 素材内容深度识别与智能匹配引擎
=====================================================

核心能力:
1. 视觉大模型(Vision LLM)识别素材所属IP/作品、角色、场景
2. OpenCV 视觉特征分析(色调/运动/边缘/场景复杂度)
3. 素材标签体系(IP/角色/场景/情绪/动作)
4. 按目标IP智能过滤 + 按段落情绪智能匹配

技术路线:
- 帧采样 → base64编码 → Vision LLM 结构化识别
- OpenCV 颜色直方图 / 光流运动 / 边缘密度 / 人脸检测
- 双通道融合: 语义标签(VLM) + 视觉特征(CV)

用法:
    engine = MaterialIntelligenceEngine()
    # 分析单个素材
    tag = engine.analyze_video("levi_amv.mp4")
    # 批量构建索引
    index = engine.build_index(video_paths)
    # 按IP过滤
    aot_materials = index.filter_by_ip("进击的巨人")
    # 按情绪匹配
    matched = index.match_by_mood("battle", top_k=5)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

_PROJECT_ROOT = Path(__file__).parent.parent

# ================================================================
#  IP 别名归一化表 — canonical名 → 别名集合(全小写)
# ================================================================

IP_ALIASES: Dict[str, List[str]] = {
    "进击的巨人": ["进击的巨人", "attack on titan", "aot", "snk",
                "shingeki no kyojin", "shingeki", "進撃の巨人"],
    "FATE": ["fate", "fate/stay night", "fate stay night", "fate/zero",
           "fate zero", "fate ubw", "unlimited blade works", "命运之夜",
           "命运冠位指定", "fgo"],
    "黑岩射手": ["黑岩射手", "black rock shooter", "brs", "ブラックロックシューター"],
    "鬼灭之刃": ["鬼灭之刃", "鬼滅の刃", "demon slayer", "kimetsu no yaiba", "kimetsu"],
    "咒术回战": ["咒术回战", "呪術廻戦", "jujutsu kaisen", "jjk"],
    "火影忍者": ["火影忍者", "naruto", "naruto shippuden", "博人传", "boruto"],
    "海贼王": ["海贼王", "one piece", "路飞"],
    "间谍过家家": ["间谍过家家", "spy x family", "间谍家家酒"],
    "电锯人": ["电锯人", "chainsaw man", "チェンソーマン"],
    "一拳超人": ["一拳超人", "one punch man", "ワンパンマン"],
    "冰海战记": ["冰海战记", "vinland saga", "ヴィンランド・サガ"],
    "无限滑板": ["无限滑板", "sk8 the infinity", "sk8", "スケートリーディング"],
    "地缚少年花子君": ["地缚少年花子君", "花子君", "toilet-bound hanako-kun",
                  "hanako-kun", "hanako kun", "地縛少年花子くん"],
    "多洛赫多罗": ["多洛赫多罗", "dorohedoro", "异兽魔都"],
    "时光代理人": ["时光代理人", "link click"],
    "灵笼": ["灵笼", "ling long", "incarnation"],
}

# 反向索引: 别名 → canonical名
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canon, _aliases in IP_ALIASES.items():
    _canon_l = _canon.lower()
    _ALIAS_TO_CANONICAL[_canon_l] = _canon
    for _a in _aliases:
        _ALIAS_TO_CANONICAL[_a.lower()] = _canon


def normalize_ip(name: str) -> str:
    """将任意IP名称归一化到canonical名。

    例: "命运之夜：无限剑制" → "FATE", "Attack on Titan" → "进击的巨人"
    无法归一化时返回原始名称。
    """
    if not name:
        return ""
    raw = name.strip()
    l = raw.lower()
    if l in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[l]
    # 子串匹配: "fate/stay night: ubw" 包含 "fate"
    # 按别名长度降序匹配，优先更精确的别名
    for alias in sorted(_ALIAS_TO_CANONICAL.keys(), key=len, reverse=True):
        if len(alias) >= 3 and alias in l:
            return _ALIAS_TO_CANONICAL[alias]
    return raw


def ip_matches(name: str, keyword: str) -> bool:
    """判断IP名称是否匹配目标关键词（归一化后比较）"""
    if not keyword:
        return True
    if not name:
        return False
    nk, nk2 = normalize_ip(name), normalize_ip(keyword)
    if nk and nk2 and nk == nk2:
        return True
    # 归一化失败时回退到双向子串
    kw = keyword.lower().strip()
    nm = name.lower()
    return kw in nm or nm in kw


# ================================================================
#  数据结构
# ================================================================

@dataclass
class IPTag:
    """IP/作品标签"""
    ip_name: str = ""                    # 作品名 (如 "进击的巨人")
    ip_name_en: str = ""                 # 英文名 (如 "Attack on Titan")
    confidence: float = 0.0              # 识别置信度 0-1
    characters: List[str] = field(default_factory=list)  # 识别到的角色
    evidence: str = ""                   # 识别依据描述


@dataclass
class IPTimelineSegment:
    """时间线IP分段 — 原生视频理解模型输出的逐段归属"""
    start: float = 0.0
    end: float = 0.0
    ip_name: str = ""            # canonical名
    characters: List[str] = field(default_factory=list)
    confidence: float = 0.0
    description: str = ""


@dataclass
class ContentTag:
    """内容标签"""
    scene_type: str = "unknown"          # battle/action/closeup/landscape/indoor/dialogue/unknown
    mood: str = "neutral"                # epic/intense/calm/sad/dark/bright/romantic
    action_type: str = ""                # fighting/running/flying/talking/standing
    visual_style: str = ""               # dark_fantasy/mecha/slice_of_life/sports/fantasy
    color_palette: str = "neutral"       # warm/cool/dark/vibrant/muted
    motion_intensity: str = "medium"     # low/medium/high
    has_character: bool = False
    face_count: int = 0
    edge_density: float = 0.0
    avg_brightness: float = 0.0
    avg_motion: float = 0.0


@dataclass
class MaterialIntelTag:
    """素材智能标签 — 融合VLM语义识别 + CV视觉特征"""
    video_path: str = ""
    filename: str = ""
    duration: float = 0.0
    fps: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    file_hash: str = ""                  # 文件哈希(用于缓存)

    # VLM 语义识别
    ip_tags: List[IPTag] = field(default_factory=list)
    primary_ip: str = ""                 # 最主要归属IP (canonical名)
    description: str = ""                # VLM对画面的自然语言描述
    is_mixed: bool = False               # 是否多IP混剪
    content_kind: str = "unknown"        # anime_amv/tutorial/effect_demo/music_video/live_action/unknown

    # CV 视觉特征
    content: ContentTag = field(default_factory=ContentTag)

    # 时间线特征
    scene_changes: List[float] = field(default_factory=list)
    high_motion_regions: List[Dict] = field(default_factory=list)
    ip_timeline: List[IPTimelineSegment] = field(default_factory=list)  # 逐段IP归属(原生视频理解)

    # 元数据
    analysis_time: float = 0.0
    vlm_model: str = ""
    frame_count_analyzed: int = 0

    @property
    def ip_names(self) -> List[str]:
        """所有识别到的IP名"""
        return [t.ip_name for t in self.ip_tags if t.ip_name]

    def matches_ip(self, ip_keyword: str, strict: bool = True) -> bool:
        """检查素材是否匹配给定IP关键词。

        strict=True (生产模式): 语义化匹配 —
        1. 归一化后比对所有IP标签 (含别名表)
        2. 排除负面证据: 如果素材已被高置信度识别为其他IP，
           且描述/文件名中没有目标关键词的直接证据，则拒绝匹配。
           (杜绝 "描述里偶然提到" 导致的误混入)
        3. 教程/特效演示类内容永不匹配任何IP

        strict=False (宽松模式): 任一通道出现关键词即匹配。
        """
        kw = ip_keyword.lower().strip()
        if not kw:
            return True
        # 教程/演示类内容绝不能混入IP成片
        if self.content_kind in ("tutorial", "effect_demo"):
            return False

        # 正向证据: IP标签归一化匹配
        for tag in self.ip_tags:
            if tag.confidence < 0.3:
                continue
            if ip_matches(tag.ip_name, ip_keyword) or ip_matches(tag.ip_name_en, ip_keyword):
                return True
        # 主IP归一化匹配
        if self.primary_ip and ip_matches(self.primary_ip, ip_keyword):
            return True

        # 描述/文件名中的直接关键词证据
        desc_hit = kw in self.description.lower()
        file_hit = kw in self.filename.lower()

        if not strict:
            return desc_hit or file_hit

        # 严格模式: 有直接关键词证据
        if desc_hit or file_hit:
            # 但如果主IP被高置信度识别为其他IP → 负面排除
            if self.primary_ip:
                canon_primary = normalize_ip(self.primary_ip)
                canon_target = normalize_ip(ip_keyword)
                if (canon_primary and canon_target
                        and canon_primary != canon_target
                        and self.ip_tags
                        and self.ip_tags[0].confidence >= 0.8):
                    return False
            return True
        return False

    def to_dict(self) -> Dict:
        d = {
            "video_path": self.video_path,
            "filename": self.filename,
            "duration": self.duration,
            "fps": self.fps,
            "resolution": list(self.resolution),
            "file_hash": self.file_hash,
            "primary_ip": self.primary_ip,
            "description": self.description,
            "is_mixed": self.is_mixed,
            "content_kind": self.content_kind,
            "ip_tags": [
                {"ip_name": t.ip_name, "ip_name_en": t.ip_name_en,
                 "confidence": t.confidence, "characters": t.characters,
                 "evidence": t.evidence}
                for t in self.ip_tags
            ],
            "content": {
                "scene_type": self.content.scene_type,
                "mood": self.content.mood,
                "action_type": self.content.action_type,
                "visual_style": self.content.visual_style,
                "color_palette": self.content.color_palette,
                "motion_intensity": self.content.motion_intensity,
                "has_character": self.content.has_character,
                "face_count": self.content.face_count,
                "edge_density": round(self.content.edge_density, 4),
                "avg_brightness": round(self.content.avg_brightness, 1),
                "avg_motion": round(self.content.avg_motion, 2),
            },
            "scene_changes": self.scene_changes,
            "ip_timeline": [
                {"start": round(s.start, 2), "end": round(s.end, 2),
                 "ip_name": s.ip_name, "characters": s.characters,
                 "confidence": s.confidence, "description": s.description}
                for s in self.ip_timeline
            ],
            "analysis_time": round(self.analysis_time, 2),
            "vlm_model": self.vlm_model,
            "frame_count_analyzed": self.frame_count_analyzed,
        }
        return d


# ================================================================
#  素材索引 — 支持过滤与匹配
# ================================================================

class MaterialIndex:
    """素材索引 — 支持IP过滤和情绪匹配"""

    def __init__(self):
        self.tags: Dict[str, MaterialIntelTag] = {}  # path -> tag

    def add(self, tag: MaterialIntelTag):
        self.tags[tag.video_path] = tag

    def filter_by_ip(self, ip_keyword: str, strict: bool = True) -> List[str]:
        """按IP关键词过滤素材，返回匹配的视频路径列表

        strict=True: 语义化严格匹配(含负面排除)，生产模式默认。
        """
        if not ip_keyword:
            return list(self.tags.keys())
        return [path for path, tag in self.tags.items()
                if tag.matches_ip(ip_keyword, strict=strict)]

    def select_for_ip(self, target_ip: str,
                      allow_mixed: bool = False,
                      allow_unknown: bool = False) -> Dict[str, List[str]]:
        """生产级素材选择 — 返回 matched/excluded/mixed/unknown 四类。

        - matched:  匹配目标IP且内容类型合规的素材
        - mixed:    多IP混剪素材 (默认排除，allow_mixed=True时纳入matched)
        - unknown:  未识别出IP的素材 (默认排除)
        - excluded: 明确属于其他IP或教程类的素材
        """
        result: Dict[str, List[str]] = {
            "matched": [], "mixed": [], "unknown": [], "excluded": [],
        }
        if not target_ip:
            result["matched"] = list(self.tags.keys())
            return result

        for path, tag in self.tags.items():
            # 教程/演示类永远排除
            if tag.content_kind in ("tutorial", "effect_demo"):
                result["excluded"].append(path)
                continue
            if tag.matches_ip(target_ip, strict=True):
                if tag.is_mixed:
                    if allow_mixed:
                        result["matched"].append(path)
                    else:
                        result["mixed"].append(path)
                else:
                    result["matched"].append(path)
            elif not tag.primary_ip and not tag.ip_tags:
                if allow_unknown:
                    result["matched"].append(path)
                else:
                    result["unknown"].append(path)
            else:
                result["excluded"].append(path)
        return result

    def match_by_mood(self, target_mood: str, top_k: int = 5) -> List[str]:
        """按情绪匹配素材，返回最匹配的路径列表"""
        mood_map = {
            "epic": ["epic", "intense", "battle"],
            "intense": ["intense", "epic", "battle"],
            "battle": ["intense", "epic", "battle"],
            "calm": ["calm", "sad", "neutral"],
            "sad": ["sad", "calm", "dark"],
            "dark": ["dark", "intense", "sad"],
            "bright": ["bright", "calm", "neutral"],
            "climax": ["intense", "epic", "battle"],
            "intro": ["calm", "neutral", "epic"],
            "build": ["neutral", "epic", "intense"],
            "break": ["calm", "sad", "neutral"],
            "outro": ["calm", "neutral", "sad"],
        }
        target_set = set(mood_map.get(target_mood, [target_mood]))
        scored = []
        for path, tag in self.tags.items():
            score = 0
            if tag.content.mood in target_set:
                score += 3
            if tag.content.scene_type in target_set:
                score += 2
            if target_mood in ("battle", "intense", "epic") and tag.content.motion_intensity == "high":
                score += 1
            if target_mood in ("calm", "sad", "break") and tag.content.motion_intensity == "low":
                score += 1
            scored.append((path, score))
        scored.sort(key=lambda x: -x[1])
        return [p for p, s in scored[:top_k] if s > 0]

    def get_smart_assignment(self, seg_idx: int, total_segs: int,
                             target_mood: str, target_ip: str = "",
                             candidates: Optional[List[str]] = None) -> Optional[str]:
        """为段落智能分配素材 — 同时考虑IP过滤和情绪匹配

        candidates: 显式候选集(生产模式由 select_for_ip 预先确定)。
                    传入时不再隐式放宽，候选为空直接返回 None，
                    由调用方决定如何处理(严格模式下应报错而非降级)。
        """
        # 1. 确定候选集
        if candidates is not None:
            pool = list(candidates)
        elif target_ip:
            pool = self.filter_by_ip(target_ip, strict=True)
        else:
            pool = list(self.tags.keys())

        if not pool:
            # 生产级语义: 无匹配素材时返回None，绝不隐式回退到全部素材
            return None

        # 2. 按情绪排序
        mood_ranked = self.match_by_mood(target_mood, top_k=len(pool))
        # 保持候选集范围内的
        ranked = [p for p in mood_ranked if p in pool]
        if not ranked:
            ranked = pool

        # 3. 多样性: 不同段落尽量用不同素材
        # 按seg_idx偏移选择，避免所有段用同一个素材
        offset = seg_idx % len(ranked)
        return ranked[offset]

    def save(self, path: str):
        data = {p: t.to_dict() for p, t in self.tags.items()}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for p, d in data.items():
            tag = self._from_dict(d)
            self.tags[p] = tag

    @staticmethod
    def _from_dict(d: Dict) -> MaterialIntelTag:
        ip_tags = [
            IPTag(ip_name=normalize_ip(t.get("ip_name", "")),
                  ip_name_en=t.get("ip_name_en", ""),
                  confidence=t.get("confidence", 0), characters=t.get("characters", []),
                  evidence=t.get("evidence", ""))
            for t in d.get("ip_tags", [])
        ]
        cd = d.get("content", {})
        content = ContentTag(
            scene_type=cd.get("scene_type", "unknown"),
            mood=cd.get("mood", "neutral"),
            action_type=cd.get("action_type", ""),
            visual_style=cd.get("visual_style", ""),
            color_palette=cd.get("color_palette", "neutral"),
            motion_intensity=cd.get("motion_intensity", "medium"),
            has_character=cd.get("has_character", False),
            face_count=cd.get("face_count", 0),
            edge_density=cd.get("edge_density", 0),
            avg_brightness=cd.get("avg_brightness", 0),
            avg_motion=cd.get("avg_motion", 0),
        )
        res = d.get("resolution", [0, 0])
        return MaterialIntelTag(
            video_path=d.get("video_path", ""),
            filename=d.get("filename", ""),
            duration=d.get("duration", 0),
            fps=d.get("fps", 0),
            resolution=tuple(res) if isinstance(res, list) else res,
            file_hash=d.get("file_hash", ""),
            ip_tags=ip_tags,
            primary_ip=normalize_ip(d.get("primary_ip", "")),
            description=d.get("description", ""),
            is_mixed=d.get("is_mixed", False),
            content_kind=d.get("content_kind", "unknown"),
            content=content,
            scene_changes=d.get("scene_changes", []),
            ip_timeline=[
                IPTimelineSegment(start=s.get("start", 0), end=s.get("end", 0),
                                  ip_name=normalize_ip(s.get("ip_name", "")),
                                  characters=s.get("characters", []),
                                  confidence=s.get("confidence", 0),
                                  description=s.get("description", ""))
                for s in d.get("ip_timeline", [])
            ],
            analysis_time=d.get("analysis_time", 0),
            vlm_model=d.get("vlm_model", ""),
            frame_count_analyzed=d.get("frame_count_analyzed", 0),
        )


# ================================================================
#  核心引擎: MaterialIntelligenceEngine
# ================================================================

class MaterialIntelligenceEngine:
    """素材内容深度识别引擎

    双通道分析:
    1. Vision LLM (Claude/Doubao-Vision) — 语义级IP/角色/场景识别
    2. OpenCV — 视觉特征(色调/运动/边缘/人脸)
    """

    # 已知动漫IP关键词库 (用于辅助匹配)
    KNOWN_IPS = {
        "进击的巨人": ["attack on titan", "aot", "snk", "shingeki", "利威尔", "艾伦",
                     "三笠", "艾尔文", "韩吉", "兵长", "调查兵团", "巨人"],
        "FATE": ["fate", "fate stay night", "fate zero", "saber", "卫宫", "远坂"],
        "黑岩射手": ["black rock shooter", "黑岩", "brs"],
        "鬼灭之刃": ["demon slayer", "kimetsu", "炭治郎", "祢豆子"],
        "咒术回战": ["jujutsu kaisen", "五条", "虎杖", "的场"],
        "无限滑板": ["sk8 the infinity", "滑板", "sk8"],
        "电锯人": ["chainsaw man", "电锯人", "デンジ"],
        "一拳超人": ["one punch man", "一拳超人", "埼玉"],
        "冰海战记": ["vinland saga", "冰海战记", "托尔芬", "托尔兹"],
        "间谍过家家": ["spy x family", "间谍", "阿尼亚"],
    }

    def __init__(
        self,
        frame_sample_count: int = 4,
        cache_dir: Optional[str] = None,
        use_vlm: bool = True,
        use_cv: bool = True,
        use_local_classifier: bool = True,
    ):
        self.frame_sample_count = frame_sample_count
        self.cache_dir = Path(cache_dir or str(_PROJECT_ROOT / "cache" / "material_intel"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.use_vlm = use_vlm
        self.use_cv = use_cv
        self.use_local_classifier = use_local_classifier

        # 延迟加载
        self._cv2 = None
        self._env = None
        self._proto_kb = None
        self._index = MaterialIndex()

    def _ensure_cv2(self):
        if self._cv2 is None:
            import cv2
            self._cv2 = cv2

    def _load_env(self) -> Dict[str, str]:
        if self._env is not None:
            return self._env
        env = {}
        env_file = _PROJECT_ROOT / ".env.doubao"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
        self._env = env
        return env

    # ================================================================
    #  公开 API
    # ================================================================

    def analyze_video(self, video_path: str, use_cache: bool = True) -> MaterialIntelTag:
        """分析单个视频素材 — 返回智能标签"""
        video_path = str(video_path)
        t0 = time.time()

        # 检查缓存
        cache_key = self._make_cache_key(video_path)
        cache_path = self.cache_dir / f"{cache_key}.json"
        if use_cache and cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tag = MaterialIndex._from_dict(data)
                print(f"  [缓存] {Path(video_path).name}: IP={tag.primary_ip}")
                return tag
            except Exception:
                pass

        print(f"  [分析] {Path(video_path).name}...")

        # 1. 基础信息 + CV特征
        self._ensure_cv2()
        basic_info, cv_features, frames_b64 = self._cv_analyze(video_path)

        # 2. VLM 语义识别 — 优先尝试原生视频理解通道(时序级识别)
        vlm_result = {}
        vlm_model_used = ""
        if self.use_vlm:
            vlm_result, vlm_model_used = self._ark_video_native(video_path, env=self._load_env())
        if not vlm_result and self.use_vlm and frames_b64:
            vlm_result, vlm_model_used = self._vlm_analyze(frames_b64, video_path)

        # 3. 融合标签
        tag = self._fuse_tag(video_path, basic_info, cv_features, vlm_result)
        tag.analysis_time = time.time() - t0
        tag.vlm_model = vlm_model_used
        tag.frame_count_analyzed = len(frames_b64)
        # 原生视频通道附带的时间线分段
        for seg in vlm_result.get("timeline", []) or []:
            try:
                tag.ip_timeline.append(IPTimelineSegment(
                    start=float(seg.get("start", 0)), end=float(seg.get("end", 0)),
                    ip_name=normalize_ip(seg.get("ip_name", "")),
                    characters=seg.get("characters", []) if isinstance(seg.get("characters"), list) else [],
                    confidence=float(seg.get("confidence", 0)),
                    description=str(seg.get("description", "")),
                ))
            except Exception:
                continue

        # 4. 本地CLIP分类器仲裁(P2.3) — VLM缺席时补位/一致时交叉印证
        if self.use_local_classifier:
            try:
                self._local_ip_arbitrate(tag, video_path)
            except Exception as e:
                print(f"    [WARN] 本地分类器仲裁异常(已忽略): {e}")

        # 保存缓存
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(tag.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        print(f"    → IP={tag.primary_ip or '未识别'}"
              f"{'(混剪)' if tag.is_mixed else ''}, 类型={tag.content_kind}, "
              f"场景={tag.content.scene_type}, 情绪={tag.content.mood}, "
              f"耗时={tag.analysis_time:.1f}s")
        return tag

    def build_index(self, video_paths: List[str],
                    output_json: Optional[str] = None) -> MaterialIndex:
        """批量分析视频素材，构建素材索引"""
        print(f"\n{'=' * 60}")
        print(f"素材智能索引构建 — {len(video_paths)} 个素材")
        print(f"{'=' * 60}")

        index = MaterialIndex()
        for i, path in enumerate(video_paths):
            if not Path(path).exists():
                print(f"  [{i+1}/{len(video_paths)}] 跳过(不存在): {Path(path).name}")
                continue
            try:
                tag = self.analyze_video(path)
                index.add(tag)
            except Exception as e:
                print(f"  [{i+1}/{len(video_paths)}] 分析失败: {e}")

        # 保存索引
        if output_json:
            index.save(output_json)
            print(f"\n索引已保存: {output_json}")

        # 统计
        ip_counts: Dict[str, int] = {}
        for tag in index.tags.values():
            ip = tag.primary_ip or "未识别"
            ip_counts[ip] = ip_counts.get(ip, 0) + 1
        print(f"\nIP分布:")
        for ip, count in sorted(ip_counts.items(), key=lambda x: -x[1]):
            print(f"  {ip}: {count} 个素材")

        self._index = index
        return index

    def get_index(self) -> MaterialIndex:
        return self._index

    # ================================================================
    #  CV 视觉特征分析
    # ================================================================

    def _cv_analyze(self, video_path: str) -> Tuple[Dict, Dict, List[str]]:
        """OpenCV 视觉特征分析 + 帧采样"""
        import numpy as np
        cv2 = self._cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        basic_info = {
            "fps": fps, "total_frames": total_frames,
            "width": width, "height": height, "duration": duration,
        }

        # 均匀采样
        n_frames = min(self.frame_sample_count, total_frames)
        sample_indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)

        brightness_list = []
        saturation_list = []
        edge_density_list = []
        motion_list = []
        face_total = 0
        frames_with_faces = 0
        prev_gray = None
        frames_b64 = []
        scene_changes = []
        prev_hist = None

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            brightness_list.append(float(np.mean(gray)))
            saturation_list.append(float(np.mean(hsv[:, :, 1])))

            # 边缘密度
            edges = cv2.Canny(gray, 50, 150)
            edge_density_list.append(float(edges.sum()) / (edges.shape[0] * edges.shape[1] * 255))

            # 运动估计
            if prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
                mag = float(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2).mean())
                motion_list.append(mag)

            # 人脸检测 (OpenCV 5.x 移除了 CascadeClassifier，用肤色近似)
            n_faces = 0
            try:
                # 简单肤色检测: HSV中皮肤色域
                skin_mask = cv2.inRange(hsv, (0, 30, 60), (25, 180, 255))
                skin_ratio = float(skin_mask.sum()) / (skin_mask.shape[0] * skin_mask.shape[1] * 255)
                if skin_ratio > 0.05:
                    n_faces = 1  # 有皮肤区域即认为可能有角色
            except Exception:
                pass
            face_total += n_faces
            if n_faces > 0:
                frames_with_faces += 1

            # 场景切换检测
            hist = cv2.normalize(
                cv2.calcHist([gray], [0], None, [64], [0, 256]), None
            ).flatten()
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                if diff > 0.3:
                    scene_changes.append(float(idx / fps))
            prev_hist = hist

            prev_gray = gray.copy()

            # 保存帧用于VLM (缩放到合理尺寸)
            if len(frames_b64) < self.frame_sample_count:
                # 缩放到最大边 640px 以节省token
                h, w = frame.shape[:2]
                scale = min(640 / max(h, w), 1.0)
                if scale < 1.0:
                    small = cv2.resize(frame, (int(w * scale), int(h * scale)))
                else:
                    small = frame
                _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
                b64 = base64.b64encode(buf).decode("utf-8")
                frames_b64.append(b64)

        cap.release()

        # 汇总CV特征
        n_samples = max(len(brightness_list), 1)
        avg_brightness = sum(brightness_list) / n_samples
        avg_saturation = sum(saturation_list) / n_samples
        avg_edge = sum(edge_density_list) / n_samples if edge_density_list else 0
        avg_motion = sum(motion_list) / len(motion_list) if motion_list else 0

        # 色调判断
        warm_count = sum(1 for s in saturation_list if s > 80)
        cool_count = sum(1 for s in saturation_list if s < 40)
        if warm_count > n_samples * 0.6:
            color_palette = "warm"
        elif cool_count > n_samples * 0.6:
            color_palette = "cool"
        elif avg_brightness < 50:
            color_palette = "dark"
        elif avg_saturation > 100:
            color_palette = "vibrant"
        else:
            color_palette = "neutral"

        # 运动强度
        if avg_motion > 10:
            motion_intensity = "high"
        elif avg_motion > 3:
            motion_intensity = "medium"
        else:
            motion_intensity = "low"

        # 场景类型(CV推断)
        has_char = frames_with_faces > len(sample_indices) * 0.3
        if avg_motion > 15 and avg_edge > 0.1:
            scene_type = "battle"
        elif avg_motion > 10:
            scene_type = "action"
        elif has_char and avg_edge < 0.05:
            scene_type = "closeup"
        elif avg_edge < 0.03 and avg_motion < 2:
            scene_type = "landscape"
        elif has_char:
            scene_type = "dialogue"
        else:
            scene_type = "unknown"

        # 情绪(CV推断)
        if avg_brightness < 40 and avg_saturation < 40:
            mood = "dark"
        elif avg_brightness < 50 and len(scene_changes) > 5:
            mood = "intense"
        elif avg_brightness > 70 and avg_saturation > 60:
            mood = "bright"
        elif avg_motion > 10:
            mood = "epic"
        else:
            mood = "neutral"

        cv_features = {
            "avg_brightness": avg_brightness,
            "avg_saturation": avg_saturation,
            "avg_edge_density": avg_edge,
            "avg_motion": avg_motion,
            "face_count_total": face_total,
            "frames_with_faces": frames_with_faces,
            "has_character": has_char,
            "color_palette": color_palette,
            "motion_intensity": motion_intensity,
            "scene_type_cv": scene_type,
            "mood_cv": mood,
            "scene_changes": scene_changes,
        }

        return basic_info, cv_features, frames_b64

    # ================================================================
    #  VLM 语义识别
    # ================================================================

    def build_frames_content_parts(self, frames_b64: List[str]) -> List:
        """构建抽帧多模态请求内容(图像帧+标准分析提示词)，供各通道独立评测复用"""
        prompt = """你是一个专业的动漫视频内容分析专家。这些是从一段视频中均匀采样的帧画面，请仔细分析并输出以下信息。

请严格以JSON格式输出，不要输出其他内容：
{
    "works": [
        {"ip_name": "作品中文名", "ip_name_en": "作品英文名", "confidence": 0.0到1.0, "characters": ["角色名"], "evidence": "判断依据"}
    ],
    "is_mixed": 是否为多部不同作品的混剪AMV(true/false),
    "content_kind": "内容性质: anime_amv(动漫作品/混剪)/tutorial(软件教程，如AE、PR教程)/effect_demo(特效演示)/music_video(MV)/live_action(真人影视)/unknown",
    "scene_description": "对画面内容的简要描述(1-2句话)",
    "scene_type": "场景类型: battle/action/closeup/landscape/indoor/dialogue/unknown",
    "mood": "画面情绪: epic/intense/calm/sad/dark/bright/romantic/neutral",
    "action_type": "主要动作: fighting/running/flying/talking/standing/other",
    "visual_style": "视觉风格: dark_fantasy/mecha/slice_of_life/sports/fantasy/sci_fi/other",
    "evidence": "你做出作品归属判断的关键依据(角色外貌特征/服装/标志性元素/文字水印等)"
}

注意：
1. works数组列出画面中出现的所有作品；单一作品视频只填1项；混剪AMV请尽量列出所有能辨认的作品，按出现比重降序
2. 如果是软件教程（如AE/PR操作界面演示、字幕制作教学），content_kind填tutorial，works填空数组[]
3. 如果画面中出现字幕/水印提及作品名，可作为高置信度证据
4. 完全无法辨认作品时，works填空数组[]
5. 只输出JSON，不要有其他文字"""
        content_parts = []
        selected = frames_b64[:6] if len(frames_b64) > 6 else frames_b64
        for b64 in selected:
            # 2026-08-13 修复: MIME 硬编码 image/jpeg 但抽帧可能是 PNG,
            # SiliconFlow 等通道对 MIME 不匹配返回 400。从 base64 头嗅探真实类型。
            if b64.startswith("/9j/"):  # JPEG
                _mime = "image/jpeg"
            elif b64.startswith("iVBOR"):  # PNG
                _mime = "image/png"
            else:
                _mime = "image/jpeg"
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{_mime};base64,{b64}"}
            })
        content_parts.append({"type": "text", "text": prompt})
        return content_parts

    def _vlm_analyze(self, frames_b64: List[str], video_path: str) -> Tuple[Dict, str]:
        """使用视觉大模型识别素材内容 — 三通道自动切换 + 重试"""
        if not frames_b64:
            return {}, ""

        env = self._load_env()

        # 构建多图消息内容 (标准提示词复用)
        content_parts = self.build_frames_content_parts(frames_b64)

        # 三通道依次尝试，每通道带重试
        # 2026-08-13: DuckMiss(claude-sonnet-4-6) 余额不足, 禁用。
        # 主通道 = SiliconFlow Qwen3-VL(用户有key), 兜底 = ARK 豆包。
        for caller, name in (
            (self._call_siliconflow_vision, "SiliconFlow"),
            (self._call_ark_vision, "ARK"),
        ):
            for attempt in range(2):
                try:
                    result, model = caller(content_parts, env)
                except Exception as e:
                    print(f"    [VLM] {name} 异常: {e}")
                    result, model = None, ""
                if result:
                    return result, model
                if attempt == 0:
                    time.sleep(3)  # 重试前退避

        print("    [WARN] VLM 全部通道失败，仅使用CV特征")
        return {}, ""

    def _ark_video_native(self, video_path: str, env: Optional[Dict] = None,
                          ask_timeline: bool = True) -> Tuple[Dict, str]:
        """ARK 原生视频理解通道 — 直接传整段视频给 Seed-1.6-Vision。

        相比抽帧方案的优势：
        1. 时序信息完整 — 能发现帧间IP切换(多IP混剪判定从"碰运气"变为确定性)
        2. 输出时间线分段 timeline — 支持场景级IP片段抽取
        3. 模型专为视频理解优化(256k上下文/事件定位)
        失败时返回({}, "")，由上层回退到抽帧三通道。
        """
        if env is None:
            env = self._load_env()
        api_key = env.get("DOUBAO_API_KEY", "")
        # 豆包视觉模型须经推理接入点(ep-)调用；直连模型ID返回404。
        # 优先用 ARK_ENDPOINT_VISION，回退到模型ID（兼容未来开通直连）
        model = env.get("ARK_ENDPOINT_VISION", "") or env.get(
            "ARK_MODEL_VISION_SEED_1_6", "doubao-seed-1-6-vision-250722")
        if not api_key:
            return {}, ""

        # 超大视频先用ffmpeg压缩再传(控制payload)；快切素材需保质量否则IP特征丢失
        upload_path = video_path
        try:
            if Path(video_path).stat().st_size > 20 * 1024 * 1024:
                tmp_dir = self.cache_dir / "video_shrink"
                tmp_dir.mkdir(parents=True, exist_ok=True)
                shrunk = tmp_dir / f"{self._make_cache_key(video_path)}_v2.mp4"
                if not shrunk.exists():
                    import subprocess
                    import shutil
                    try:
                        from core.paths import ffmpeg_bin as _paths_ffmpeg
                    except ImportError:
                        _paths_ffmpeg = lambda: r"C:\ffmpeg\bin\ffmpeg.exe"
                    ffmpeg = shutil.which("ffmpeg") or _paths_ffmpeg()
                    subprocess.run(
                        [ffmpeg, "-y", "-i", video_path, "-vf", "scale=-2:720",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                         "-an", str(shrunk)],
                        capture_output=True, timeout=300)
                if shrunk.exists() and shrunk.stat().st_size > 0:
                    upload_path = str(shrunk)
        except Exception as e:
            print(f"    [VideoNative] 压缩失败，直传原片: {e}")

        try:
            import base64
            with open(upload_path, "rb") as f:
                video_b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            print(f"    [VideoNative] 读取视频失败: {e}")
            return {}, ""

        timeline_block = """
    "timeline": [
        {"start": 起始秒数, "end": 结束秒数, "ip_name": "该段所属作品中文名", "characters": ["出场角色"], "confidence": 0.0到1.0, "description": "该段画面内容一句话描述"}
    ],""" if ask_timeline else ""
        timeline_note = (
            "\n6. timeline必须按时间顺序覆盖整个视频时间轴，相邻段首尾衔接；"
            "每次画面切换到不同作品或明显不同场景时必须另起新段，"
            "混剪视频通常有很多段，不要合并不同作品的段；无法辨认的段ip_name填空字符串"
            if ask_timeline else ""
        )

        prompt = f"""你是动漫视频内容分析专家。这是一段完整的视频，请观看全部画面(注意画面随时间的变化)并输出分析结果。

请严格以JSON格式输出，不要输出其他内容：
{{
    "works": [
        {{"ip_name": "作品中文名", "ip_name_en": "作品英文名", "confidence": 0.0到1.0, "characters": ["角色名"], "evidence": "判断依据"}}
    ],
    "is_mixed": 是否为多部不同作品的混剪AMV(true/false),
    "content_kind": "内容性质: anime_amv/tutorial/effect_demo/music_video/live_action/unknown",{timeline_block}
    "scene_description": "对整体内容的简要描述(1-2句话)",
    "scene_type": "battle/action/closeup/landscape/indoor/dialogue/unknown",
    "mood": "epic/intense/calm/sad/dark/bright/romantic/neutral",
    "action_type": "fighting/running/flying/talking/standing/other",
    "visual_style": "dark_fantasy/mecha/slice_of_life/sports/fantasy/sci_fi/other",
    "evidence": "作品归属的关键依据(角色特征/服装/标志性元素/字幕水印等)"
}}

注意：
1. works列出视频中出现的所有作品，按出现比重降序；单一作品只填1项
2. 仔细观察不同时间段画面是否切换到不同作品 — 这是is_mixed判定的核心依据
3. 软件教程(AE/PR操作界面)content_kind填tutorial，works填[]
4. 字幕/水印提及作品名是高置信度证据
5. 只输出JSON，不要其他文字{timeline_note}"""

        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        try:
            import urllib.request
            data = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": [
                    {"type": "video_url",
                     "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                    {"type": "text", "text": prompt},
                ]}],
                "max_tokens": 6000,
                "temperature": 0.3,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }, method="POST")
            with urllib.request.urlopen(req, timeout=300) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_vlm_response(content)
            if parsed:
                tl = len(parsed.get("timeline", []) or [])
                print(f"    [VLM] ARK视频原生 {model}: 已解析 (时间线{tl}段)")
                return parsed, f"{model}(video-native)"
            print(f"    [VideoNative] {model}: 响应解析失败")
        except Exception as e:
            print(f"    [VideoNative] {model} 失败: {str(e)[:120]}")
        return {}, ""

    def get_ip_timeline(self, video_path: str) -> List[Dict]:
        """获取视频的场景级IP时间线分段(原生视频理解)。

        返回 [{"start","end","ip_name","characters","confidence","description"}]，
        ip_name已归一化；失败返回空列表。
        """
        video_path = str(video_path)
        # 缓存命中直接取
        cache_path = self.cache_dir / f"{self._make_cache_key(video_path)}.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tl = data.get("ip_timeline", [])
                if tl:
                    return tl
            except Exception:
                pass
        parsed, _ = self._ark_video_native(video_path, ask_timeline=True)
        segs = []
        for seg in parsed.get("timeline", []) or []:
            try:
                segs.append({
                    "start": float(seg.get("start", 0)),
                    "end": float(seg.get("end", 0)),
                    "ip_name": normalize_ip(seg.get("ip_name", "")),
                    "characters": seg.get("characters", []),
                    "confidence": float(seg.get("confidence", 0)),
                    "description": str(seg.get("description", "")),
                })
            except Exception:
                continue
        # 回写缓存 — 避免重复计费 + 持久化时间线
        if segs:
            try:
                data = {}
                if cache_path.exists():
                    data = json.load(open(cache_path, encoding="utf-8"))
                    if not isinstance(data, dict):
                        data = {}
                data.setdefault("filename", Path(video_path).name)
                data["ip_timeline"] = segs
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"    [Timeline] 缓存回写失败: {e}")
        return segs

    # ---------------- 统一通道调度 (P1.3) ----------------

    CHANNELS = ("ark-video-native", "duckmiss-frames",
                "siliconflow-frames", "ark-frames")

    def call_channel(self, channel: str, video_path: str,
                     frames_count: int = 6) -> Tuple[Optional[Dict], str]:
        """统一通道调度入口 — 四个VLM通道同一签名，互不降级。

        channel:
          ark-video-native   ARK原生视频理解(整段视频直传，含timeline)
          duckmiss-frames    DuckMiss抽帧
          siliconflow-frames SiliconFlow抽帧
          ark-frames         ARK抽帧(ep接入点优先)
        返回 (parsed_dict, model_name)；失败返回 (None, "")。
        """
        video_path = str(video_path)
        env = self._load_env()
        if channel == "ark-video-native":
            parsed, model = self._ark_video_native(video_path, env=env,
                                                   ask_timeline=True)
            return (parsed or None), model
        # 抽帧通道: 统一用标准提示词构造
        frames = self.extract_frames_b64(video_path, count=frames_count)
        if not frames:
            return None, ""
        parts = self.build_frames_content_parts(frames)
        if channel == "duckmiss-frames":
            return self._call_duckmiss_vision(parts, env)
        if channel == "siliconflow-frames":
            return self._call_siliconflow_vision(parts, env)
        if channel == "ark-frames":
            return self._call_ark_vision(parts, env)
        raise ValueError(f"未知通道: {channel}，可选: {self.CHANNELS}")

    def _call_duckmiss_vision(self, content_parts: List, env: Dict) -> Tuple[Optional[Dict], str]:
        """DuckMiss Claude Vision API"""
        api_key = env.get("DUCK_MISS_API_KEY", "")
        if not api_key:
            return None, ""
        url = env.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1") + "/chat/completions"
        model = env.get("DUCK_MISS_VISION_MODEL", "claude-sonnet-4-6")

        try:
            import urllib.request
            data = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": 1000,
                "temperature": 0.3,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "MaterialIntel/1.0",
            }, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_vlm_response(content)
            if parsed:
                print(f"    [VLM] DuckMiss {model}: 已解析")
                return parsed, model
        except Exception as e:
            print(f"    [VLM] DuckMiss 失败: {e}")
        return None, ""

    def _call_siliconflow_vision(self, content_parts: List, env: Dict) -> Tuple[Optional[Dict], str]:
        """SiliconFlow Qwen3-VL API — 备用视觉通道"""
        api_key = env.get("SILICONFLOW_API_KEY", "")
        if not api_key:
            return None, ""
        url = env.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/") + "/chat/completions"
        model = env.get("SILICONFLOW_VISION_MODEL", "Qwen/Qwen3-VL-8B-Instruct")

        try:
            import urllib.request
            data = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": 1200,
                "temperature": 0.3,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._parse_vlm_response(content)
            if parsed:
                print(f"    [VLM] SiliconFlow {model}: 已解析")
                return parsed, model
        except Exception as e:
            print(f"    [VLM] SiliconFlow 失败: {e}")
        return None, ""

    def _call_ark_vision(self, content_parts: List, env: Dict) -> Tuple[Optional[Dict], str]:
        """ARK Vision API (豆包视觉模型) — 依次尝试新版模型名"""
        api_key = env.get("DOUBAO_API_KEY", "")
        if not api_key:
            return None, ""
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        # 豆包视觉模型须经推理接入点(ep-)调用，模型ID直连普遍404；ep优先
        candidates = [
            env.get("ARK_ENDPOINT_VISION", ""),
            env.get("ARK_MODEL_VISION_1_5_PRO_32K", ""),
            env.get("ARK_MODEL_VISION_1_5_PRO", ""),
            env.get("ARK_MODEL_VISION_SEED_1_6", ""),
            env.get("ARK_MODEL_VISION_PRO", ""),
        ]
        candidates = [m for m in candidates if m]

        import urllib.request
        import urllib.error
        for model in candidates:
            try:
                data = json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": content_parts}],
                    "max_tokens": 1200,
                    "temperature": 0.3,
                }).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }, method="POST")
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = resp.read().decode("utf-8")
                    result = json.loads(raw)
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = self._parse_vlm_response(content)
                if parsed:
                    print(f"    [VLM] ARK {model}: 已解析")
                    return parsed, model
            except Exception as e:
                msg = str(e)
                print(f"    [VLM] ARK {model} 失败: {msg[:80]}")
                # 404/模型不存在 → 尝试下一个模型
                continue
        return None, ""

    def _parse_vlm_response(self, content: str) -> Optional[Dict]:
        """解析VLM返回的JSON"""
        if not content:
            return None
        import re
        # 尝试直接解析
        try:
            return json.loads(content.strip())
        except Exception:
            pass
        # 提取 ```json ... ```
        m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', content)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # 提取 { ... }
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None

    # ================================================================
    #  标签融合
    # ================================================================

    def _fuse_tag(self, video_path: str, basic_info: Dict,
                  cv_features: Dict, vlm_result: Dict) -> MaterialIntelTag:
        """融合CV特征和VLM语义，生成最终标签"""
        p = Path(video_path)

        # IP标签 — 支持新版works数组格式，兼容旧版单ip_name格式
        ip_tags: List[IPTag] = []
        primary_ip = ""
        is_mixed = False
        content_kind = "unknown"
        description = ""
        scene_type = cv_features.get("scene_type_cv", "unknown")
        mood = cv_features.get("mood_cv", "neutral")
        action_type = ""
        visual_style = ""

        if vlm_result:
            content_kind = vlm_result.get("content_kind", "unknown") or "unknown"
            is_mixed = bool(vlm_result.get("is_mixed", False))
            description = vlm_result.get("scene_description", "")

            works = vlm_result.get("works")
            if not isinstance(works, list):
                # 兼容旧格式: 单 ip_name 字段
                works = []
                if vlm_result.get("ip_name"):
                    works = [{
                        "ip_name": vlm_result.get("ip_name", ""),
                        "ip_name_en": vlm_result.get("ip_name_en", ""),
                        "confidence": vlm_result.get("confidence", 0),
                        "characters": vlm_result.get("characters", []),
                        "evidence": vlm_result.get("evidence", ""),
                    }]

            for w in works:
                if not isinstance(w, dict):
                    continue
                ip_name = (w.get("ip_name") or "").strip()
                conf = float(w.get("confidence", 0) or 0)
                if not ip_name or conf <= 0.3:
                    continue
                # 归一化到canonical名
                canon = normalize_ip(ip_name)
                ip_tags.append(IPTag(
                    ip_name=canon,
                    ip_name_en=(w.get("ip_name_en") or "").strip(),
                    confidence=conf,
                    characters=w.get("characters", []) or [],
                    evidence=w.get("evidence", "") or "",
                ))
            # 按置信度降序
            ip_tags.sort(key=lambda t: -t.confidence)
            if ip_tags:
                primary_ip = ip_tags[0].ip_name
            # 多个高置信度IP → 判定混剪
            high_conf = [t for t in ip_tags if t.confidence >= 0.6]
            if len(high_conf) >= 2:
                is_mixed = True

        # 如果没有VLM识别到IP，尝试从文件名匹配已知IP库
        if not primary_ip:
            fname = p.name.lower()
            for ip, keywords in self.KNOWN_IPS.items():
                for kw in keywords:
                    if kw.lower() in fname:
                        ip_tags.append(IPTag(
                            ip_name=ip, confidence=0.6,
                            evidence=f"文件名匹配: {kw}",
                        ))
                        primary_ip = ip
                        break
                if primary_ip:
                    break

        # 文件名启发式内容性质 (兜底)
        if content_kind == "unknown":
            fname_l = p.name.lower()
            if any(k in fname_l for k in ("教程", "教学", "tutorial", "学会", "一分钟学")):
                content_kind = "tutorial"
            elif any(k in fname_l for k in ("效果", "特效", "glitch", "rgb")):
                content_kind = "effect_demo"
            elif any(k in fname_l for k in ("amv", "mad", "混剪", "踩点", "燃向", "高燃")):
                content_kind = "anime_amv"

        # 内容标签 — VLM优先，CV兜底
        if vlm_result:
            scene_type = vlm_result.get("scene_type", scene_type) or scene_type
            mood = vlm_result.get("mood", mood) or mood
            action_type = vlm_result.get("action_type", "") or ""
            visual_style = vlm_result.get("visual_style", "") or ""

        content = ContentTag(
            scene_type=scene_type,
            mood=mood,
            action_type=action_type,
            visual_style=visual_style,
            color_palette=cv_features.get("color_palette", "neutral"),
            motion_intensity=cv_features.get("motion_intensity", "medium"),
            has_character=cv_features.get("has_character", False),
            face_count=cv_features.get("face_count_total", 0),
            edge_density=cv_features.get("avg_edge_density", 0),
            avg_brightness=cv_features.get("avg_brightness", 0),
            avg_motion=cv_features.get("avg_motion", 0),
        )

        # 文件哈希
        file_hash = self._make_cache_key(video_path)

        return MaterialIntelTag(
            video_path=video_path,
            filename=p.name,
            duration=basic_info.get("duration", 0),
            fps=basic_info.get("fps", 0),
            resolution=(basic_info.get("width", 0), basic_info.get("height", 0)),
            file_hash=file_hash,
            ip_tags=ip_tags,
            primary_ip=primary_ip,
            description=description,
            is_mixed=is_mixed,
            content_kind=content_kind,
            content=content,
            scene_changes=cv_features.get("scene_changes", []),
            vlm_model="",
            frame_count_analyzed=self.frame_sample_count,
        )

    # ================================================================
    #  本地CLIP分类器仲裁 (P2.3)
    # ================================================================

    def _get_proto_kb(self):
        """懒加载本地CLIP原型知识库(进程内单例)"""
        if self._proto_kb is None:
            from ai.ip_proto_classifier import ProtoKB, GOLDEN
            golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
            self._proto_kb = ProtoKB.build(set(golden.keys()))
        return self._proto_kb

    def _local_ip_arbitrate(self, tag: MaterialIntelTag, video_path: str) -> None:
        """本地CLIP few-shot原型分类器参与IP仲裁。

        规则(VLM权威不变, 竞技场结论 ARK-VideoNative 91.7%胜出):
        1. VLM有结果且本地一致 → 追加交叉印证证据
        2. VLM有结果但本地不一致 → 保留VLM, 记录分歧供人工复核
        3. VLM无结果且本地高置信(库内类+conf≥0.5+margin≥0.01) → 补位
        """
        from ai.ip_proto_classifier import predict_video, C_CONF_PASS, C_ACC_MARGIN_PASS
        kb = self._get_proto_kb()
        local = predict_video(video_path, kb)
        lip = local.get("primary_ip") or ""
        if not lip or not local.get("n_frames"):
            return
        lconf = float(local.get("confidence", 0.0))
        lmargin = float(local.get("acc_margin", 0.0))
        in_library = lip in kb.img_embs

        if tag.primary_ip:
            if ip_matches(lip, tag.primary_ip):
                tag.ip_tags.append(IPTag(
                    ip_name=lip, confidence=min(0.9, lconf),
                    evidence=f"本地CLIP原型交叉印证(conf={lconf},margin={lmargin})",
                ))
                print(f"    [仲裁] 本地CLIP与VLM一致: {lip} (conf={lconf})")
            else:
                print(f"    [仲裁] 本地CLIP分歧: local={lip} vs vlm={tag.primary_ip} "
                      f"(保留VLM权威)")
        else:
            if in_library and lconf >= C_CONF_PASS and lmargin >= C_ACC_MARGIN_PASS:
                tag.primary_ip = normalize_ip(lip)
                tag.ip_tags.append(IPTag(
                    ip_name=lip, confidence=round(min(0.75, lconf), 2),
                    evidence=f"本地CLIP原型补位(VLM缺席, conf={lconf})",
                ))
                print(f"    [仲裁] 本地CLIP补位: {lip} (conf={lconf})")
            else:
                print(f"    [仲裁] 本地CLIP不足以补位: {lip} "
                      f"(in_library={in_library}, conf={lconf}, margin={lmargin})")

    # ================================================================
    #  成片内容复核 — 生产交付的最后防线
    # ================================================================

    def extract_frames_b64(self, video_path: str, count: int = 4) -> List[str]:
        """从视频均匀抽帧并转base64 (供VLM复核)"""
        self._ensure_cv2()
        cv2 = self._cv2
        import numpy as np

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            return []
        indices = np.linspace(int(total * 0.05), int(total * 0.95), count, dtype=int)
        frames_b64 = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret:
                continue
            h, w = frame.shape[:2]
            scale = min(640 / max(h, w), 1.0)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frames_b64.append(base64.b64encode(buf).decode("utf-8"))
        cap.release()
        return frames_b64

    def extract_frames_window_b64(self, video_path: str,
                                  start_sec: float, end_sec: float,
                                  count: int = 2) -> List[str]:
        """按时间窗口抽帧转base64 — 素材语义分段分析 (2026-08-13 Stage2)。

        叙事角色(铺垫/爆发)需要匹配素材中对应语义的时间窗口,
        整段分析太粗(实测 5s=孤独 → 55s=战斗 同素材可区分)。
        """
        self._ensure_cv2()
        cv2 = self._cv2
        import numpy as np

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        dur = max(float(end_sec - start_sec), 0.1)
        frames_b64 = []
        for i in range(count):
            t = start_sec + dur * (i + 0.5) / count
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ret, frame = cap.read()
            if not ret:
                continue
            h, w = frame.shape[:2]
            scale = min(640 / max(h, w), 1.0)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frames_b64.append(base64.b64encode(buf).decode("utf-8"))
        cap.release()
        return frames_b64

    def verify_video_ip(self, video_path: str, target_ip: str,
                        frame_count: int = 4) -> Dict[str, Any]:
        """成片内容复核 — 抽帧让VLM确认成片确为目标IP内容。

        Returns:
            {"verified": bool, "reason": str, "model": str,
             "detected_ips": [str], "frames_checked": int}
        """
        result: Dict[str, Any] = {
            "verified": False, "reason": "", "model": "",
            "detected_ips": [], "frames_checked": 0,
        }
        if not target_ip:
            result["verified"] = True
            result["reason"] = "未指定目标IP，跳过复核"
            return result

        frames_b64 = self.extract_frames_b64(video_path, frame_count)
        result["frames_checked"] = len(frames_b64)
        if not frames_b64:
            result["reason"] = "无法从成片抽帧"
            return result

        env = self._load_env()
        canon_target = normalize_ip(target_ip)
        prompt = f"""你是视频内容审核专家。这些是从一段已剪辑成片视频中均匀采样的帧。
请判断：这段视频的画面内容是否主要属于作品《{target_ip}》(或其公认别名)？

请严格以JSON格式输出：
{{
    "detected_ips": ["画面中辨认到的作品名列表"],
    "target_present": true或false表示《{target_ip}》内容是否占主体(≥50%画面),
    "ratio_estimate": 0.0到1.0估计目标作品画面占比,
    "reason": "简短判断依据"
}}
只输出JSON。"""

        content_parts = []
        for b64 in frames_b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        content_parts.append({"type": "text", "text": prompt})

        for caller in (self._call_siliconflow_vision,
                       self._call_ark_vision):
            try:
                parsed, model = caller(content_parts, env)
            except Exception:
                parsed, model = None, ""
            if parsed:
                result["model"] = model
                result["detected_ips"] = parsed.get("detected_ips", []) or []
                ratio = float(parsed.get("ratio_estimate", 0) or 0)
                present = bool(parsed.get("target_present", False))
                result["reason"] = parsed.get("reason", "")
                # 通过标准: VLM明确认定 + 占比≥0.5
                result["verified"] = present and ratio >= 0.5
                # 归一化后再判一次: 检测到的IP里有目标canonical名
                if not result["verified"]:
                    for ip in result["detected_ips"]:
                        if normalize_ip(ip) == canon_target:
                            result["verified"] = ratio >= 0.5
                            break
                return result

        result["reason"] = "VLM复核不可用，无法验证"
        return result

    # ================================================================
    #  工具方法
    # ================================================================

    def _make_cache_key(self, video_path: str) -> str:
        """生成缓存键 — 基于文件路径+修改时间+大小"""
        p = Path(video_path)
        if p.exists():
            stat = p.stat()
            raw = f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}"
        else:
            raw = str(video_path)
        return hashlib.md5(raw.encode()).hexdigest()[:12]


# ================================================================
#  CLI 自测入口
# ================================================================

if __name__ == "__main__":
    import glob

    data_dir = _PROJECT_ROOT / "data" / "real_amv_test"
    videos = sorted(glob.glob(str(data_dir / "*.mp4")))

    if not videos:
        print("[WARN] 没有可测试的视频文件")
        sys.exit(0)

    print(f"找到 {len(videos)} 个视频素材")

    engine = MaterialIntelligenceEngine(frame_sample_count=4)

    # 构建索引
    index = engine.build_index(
        videos,
        output_json=str(_PROJECT_ROOT / "cache" / "material_intel" / "index.json"),
    )

    # 测试IP过滤
    print(f"\n{'=' * 60}")
    print("IP过滤测试:")
    for ip_kw in ["进击的巨人", "FATE", "黑岩", "无限滑板"]:
        matched = index.filter_by_ip(ip_kw)
        print(f"  '{ip_kw}': {len(matched)} 个素材")
        for m in matched[:3]:
            print(f"    - {Path(m).name}")

    # 测试情绪匹配
    print(f"\n情绪匹配测试:")
    for mood in ["battle", "calm", "dark"]:
        matched = index.match_by_mood(mood, top_k=3)
        print(f"  '{mood}': {[Path(m).name[:30] for m in matched]}")

    print(f"\n完成!")
