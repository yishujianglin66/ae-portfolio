#!/usr/bin/env python3
"""
DaVinci Resolve LUT 预设库 v1.0
================================

管理 4129 个 .cube LUT 文件，提供：
- 预设名 → LUT 文件映射（按场景/风格/用途分类）
- 预设元数据（描述、适用场景、推荐强度）
- LUT 索引与搜索
- Fusion 调色脚本生成
- 多 LUT 链式应用
"""
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# LUT 库根目录
# ============================================================================

LUT_BASE_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\resources\luts")
LUT_INDEX_FILE = LUT_BASE_DIR / "_lut_index.json"


# ============================================================================
# 预设元数据定义
# ============================================================================

@dataclass
class LUTPreset:
    """LUT 预设定义"""
    name: str                    # 预设标识名
    display_name: str            # 显示名称
    category: str                # 主分类
    subcategory: str = ""        # 子分类
    description: str = ""        # 描述
    tags: list[str] = field(default_factory=list)  # 标签
    intensity_range: tuple[float, float] = (0.3, 1.0)  # 推荐强度范围
    best_for: list[str] = field(default_factory=list)    # 最佳适用场景
    mood: str = ""               # 情绪/氛围
    lut_dir_pattern: str = ""    # LUT 目录匹配模式
    lut_file_pattern: str = ""   # LUT 文件名匹配模式
    preferred_files: list[str] = field(default_factory=list)  # 精选文件编号


# ============================================================================
# 完整预设库 (40+ 预设)
# ============================================================================

LUT_PRESETS: dict[str, LUTPreset] = {
    # ---- 电影感系列 ----
    "cinematic": LUTPreset(
        name="cinematic",
        display_name="电影感 Cinematic",
        category="cinematic",
        description="经典电影调色，高对比度、暗角、色彩分离",
        tags=["电影", "cinematic", "大片感", "高对比"],
        intensity_range=(0.4, 0.9),
        best_for=["短片", "混剪", "叙事", "高燃"],
        mood="史诗、沉浸",
        lut_dir_pattern="Cinematic",
        preferred_files=["1", "5", "10", "20", "50"],
    ),
    "cinematic_02": LUTPreset(
        name="cinematic_02",
        display_name="电影感 II Cinematic_02",
        category="cinematic",
        description="第二套电影调色，更柔和的色调过渡",
        tags=["电影", "柔和", "叙事"],
        intensity_range=(0.3, 0.8),
        best_for=["情感", "叙事", "回忆"],
        mood="温暖、怀旧",
        lut_dir_pattern="Cinematic_02",
        preferred_files=["1", "10", "30", "50"],
    ),
    "hollywood": LUTPreset(
        name="hollywood",
        display_name="好莱坞 Hollywood",
        category="cinematic",
        description="好莱坞大片风格，青橙色调分离",
        tags=["好莱坞", "大片", "青橙", "teal-orange"],
        intensity_range=(0.5, 1.0),
        best_for=["动作", "高燃", "混剪", "商业"],
        mood="大气、震撼",
        lut_dir_pattern="Hollywood",
        preferred_files=["1", "5", "20", "50", "100"],
    ),
    "movie": LUTPreset(
        name="movie",
        display_name="电影 Movie",
        category="cinematic",
        description="经典电影胶片感，自然色彩还原",
        tags=["电影", "胶片", "自然"],
        intensity_range=(0.4, 0.9),
        best_for=["剧情", "文艺", "纪录"],
        mood="真实、沉稳",
        lut_dir_pattern="Movie",
        preferred_files=["1", "10", "30", "60"],
    ),
    "super_cinematic": LUTPreset(
        name="super_cinematic",
        display_name="超级电影感 Super Cinematic",
        category="cinematic",
        description="高级电影调色合集，多种风格可选",
        tags=["超级", "高级", "电影", "专业"],
        intensity_range=(0.3, 0.8),
        best_for=["专业", "商业", "广告"],
        mood="精致、高端",
        lut_dir_pattern="Super_Cinematic",
        preferred_files=["AJN_Effects_LUT_Antoneo", "AJN_Effects_LUT_BadBoyz"],
    ),

    # ---- 戏剧/情感系列 ----
    "dramatic": LUTPreset(
        name="dramatic",
        display_name="戏剧化 Dramatic",
        category="dramatic",
        description="高对比戏剧化调色，强调光影冲突",
        tags=["戏剧", "高对比", "冲突", "力量感"],
        intensity_range=(0.5, 1.0),
        best_for=["高燃", "战斗", "竞技", "体育"],
        mood="激烈、震撼",
        lut_dir_pattern="Dramatic",
        preferred_files=["1", "10", "30", "60", "100"],
    ),
    "silence": LUTPreset(
        name="silence",
        display_name="寂静 Silence",
        category="dramatic",
        description="低饱和冷色调，压抑沉默氛围",
        tags=["寂静", "冷色", "压抑", "沉默"],
        intensity_range=(0.4, 0.9),
        best_for=["悬疑", "惊悚", "孤独", "内省"],
        mood="压抑、不安",
        lut_dir_pattern="Silence",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 影院/放映系列 ----
    "cinema": LUTPreset(
        name="cinema",
        display_name="影院 Cinema",
        category="cinema",
        description="影院放映级调色，宽色域自然过渡",
        tags=["影院", "放映", "宽色域", "专业"],
        intensity_range=(0.3, 0.8),
        best_for=["影院级", "专业", "展示"],
        mood="专业、沉浸",
        lut_dir_pattern="Cinema",
        preferred_files=["1", "10", "50", "100"],
    ),

    # ---- 暖调系列 ----
    "warm": LUTPreset(
        name="warm",
        display_name="暖调 Warm",
        category="warm",
        description="温暖色调，偏橙黄色调",
        tags=["暖调", "温暖", "橙色", "阳光"],
        intensity_range=(0.3, 0.8),
        best_for=["日常", "vlog", "旅行", "美食"],
        mood="温馨、舒适",
        lut_dir_pattern="Summer Glow",
        preferred_files=["1", "10", "30"],
    ),
    "tropic": LUTPreset(
        name="tropic",
        display_name="热带 Tropic",
        category="warm",
        description="热带风情，高饱和暖色",
        tags=["热带", "阳光", "沙滩", "活力"],
        intensity_range=(0.4, 0.9),
        best_for=["旅行", "度假", "户外"],
        mood="热情、活力",
        lut_dir_pattern="Tropic",
        preferred_files=["1", "10", "50"],
    ),
    "paradise": LUTPreset(
        name="paradise",
        display_name="天堂 Paradise",
        category="warm",
        description="明亮通透暖色调",
        tags=["天堂", "明亮", "通透"],
        intensity_range=(0.3, 0.7),
        best_for=["风景", "旅行", "婚纱"],
        mood="梦幻、明亮",
        lut_dir_pattern="Paradise",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 冷调系列 ----
    "cool": LUTPreset(
        name="cool",
        display_name="冷调 Cool",
        category="cool",
        description="冷色调，偏蓝青色",
        tags=["冷调", "蓝色", "科技", "未来"],
        intensity_range=(0.3, 0.8),
        best_for=["科技", "未来", "冷峻", "悬疑"],
        mood="冷静、理性",
        lut_dir_pattern="Cool_Look",
        preferred_files=["1", "10", "30", "50"],
    ),

    # ---- 复古/怀旧系列 ----
    "vintage": LUTPreset(
        name="vintage",
        display_name="复古 Vintage Film",
        category="vintage",
        description="经典复古胶片感，褪色暖调",
        tags=["复古", "胶片", "褪色", "怀旧"],
        intensity_range=(0.3, 0.7),
        best_for=["回忆", "文艺", "复古"],
        mood="怀旧、温暖",
        lut_dir_pattern="Vintage Film",
        preferred_files=["1", "10", "30"],
    ),
    "old_look": LUTPreset(
        name="old_look",
        display_name="旧时光 Old Look",
        category="vintage",
        description="老照片质感，泛黄褪色",
        tags=["旧时光", "老照片", "泛黄"],
        intensity_range=(0.3, 0.7),
        best_for=["回忆", "历史", "纪录"],
        mood="怀旧、沧桑",
        lut_dir_pattern="Old_Look",
        preferred_files=["1", "10", "50"],
    ),
    "memories": LUTPreset(
        name="memories",
        display_name="回忆 Memories",
        category="vintage",
        description="柔焦暖色回忆感",
        tags=["回忆", "柔焦", "温暖"],
        intensity_range=(0.2, 0.6),
        best_for=["回忆", "婚礼", "家庭"],
        mood="温馨、柔软",
        lut_dir_pattern="Memories",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 黑白系列 ----
    "noir": LUTPreset(
        name="noir",
        display_name="黑色电影 Noir",
        category="black_white",
        description="高对比黑白，黑色电影风格",
        tags=["黑白", "noir", "高对比", "经典"],
        intensity_range=(0.5, 1.0),
        best_for=["悬疑", "犯罪", "经典", "艺术"],
        mood="冷峻、神秘",
        lut_dir_pattern="Black and White",
        preferred_files=["1", "5", "10", "20"],
    ),
    "black_white": LUTPreset(
        name="black_white",
        display_name="纯黑白 Black & White",
        category="black_white",
        description="纯净黑白转换，保留细节",
        tags=["黑白", "纯净", "艺术"],
        intensity_range=(0.4, 0.9),
        best_for=["艺术", "人像", "建筑"],
        mood="纯粹、有力",
        lut_dir_pattern="Black and White",
        preferred_files=["1", "10", "20", "30"],
    ),

    # ---- 城市/街头系列 ----
    "city": LUTPreset(
        name="city",
        display_name="城市 City",
        category="urban",
        description="城市街头风格，霓虹与混凝土",
        tags=["城市", "街头", "霓虹", "都市"],
        intensity_range=(0.4, 0.8),
        best_for=["城市", "街头", "夜景", "vlog"],
        mood="都市、现代",
        lut_dir_pattern="City",
        preferred_files=["1", "10", "50", "100"],
    ),
    "urban": LUTPreset(
        name="urban",
        display_name="都市 Urban",
        category="urban",
        description="都市质感，低饱和冷色",
        tags=["都市", "质感", "冷色"],
        intensity_range=(0.3, 0.7),
        best_for=["城市", "建筑", "时尚"],
        mood="冷峻、高级",
        lut_dir_pattern="Urban",
        preferred_files=["1", "10", "30"],
    ),

    # ---- 自然/风景系列 ----
    "nature": LUTPreset(
        name="nature",
        display_name="自然 Nature",
        category="nature",
        description="自然风光调色，绿色植被增强",
        tags=["自然", "风景", "绿色", "植被"],
        intensity_range=(0.3, 0.8),
        best_for=["风景", "自然", "户外"],
        mood="清新、自然",
        lut_dir_pattern="Nature",
        preferred_files=["1", "10", "50", "100"],
    ),
    "landscape": LUTPreset(
        name="landscape",
        display_name="风景 Landscape",
        category="nature",
        description="大场景风景调色，天空大地平衡",
        tags=["风景", "大场景", "天空"],
        intensity_range=(0.3, 0.8),
        best_for=["风景", "航拍", "旅行"],
        mood="壮阔、宁静",
        lut_dir_pattern="Landscape",
        preferred_files=["1", "10", "50"],
    ),
    "aerial": LUTPreset(
        name="aerial",
        display_name="航拍 Aerial",
        category="nature",
        description="航拍专用，天空与地面均衡曝光",
        tags=["航拍", "无人机", "天空"],
        intensity_range=(0.3, 0.7),
        best_for=["航拍", "无人机", "风景"],
        mood="自由、壮阔",
        lut_dir_pattern="Aerial",
        preferred_files=["1", "10", "30"],
    ),
    "vista": LUTPreset(
        name="vista",
        display_name="远景 Vista",
        category="nature",
        description="远景通透调色，大气透视增强",
        tags=["远景", "通透", "大气"],
        intensity_range=(0.3, 0.7),
        best_for=["远景", "山脉", "日落"],
        mood="辽远、通透",
        lut_dir_pattern="Vista",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 商业/社交系列 ----
    "commercial": LUTPreset(
        name="commercial",
        display_name="商业 Commercial",
        category="commercial",
        description="商业广告级调色，产品质感突出",
        tags=["商业", "广告", "产品", "专业"],
        intensity_range=(0.3, 0.7),
        best_for=["广告", "产品", "商业"],
        mood="精致、专业",
        lut_dir_pattern="Commercial",
        preferred_files=["1", "10", "50", "100"],
    ),
    "social_media": LUTPreset(
        name="social_media",
        display_name="社交媒体 Social Media",
        category="commercial",
        description="社交媒体风格，吸睛高饱和",
        tags=["社交", "抖音", "B站", "吸睛"],
        intensity_range=(0.3, 0.8),
        best_for=["短视频", "抖音", "B站", "小红书"],
        mood="活泼、吸睛",
        lut_dir_pattern="Social_Media",
        preferred_files=["1", "10", "30"],
    ),
    "youtube_vlog": LUTPreset(
        name="youtube_vlog",
        display_name="YouTube Vlog",
        category="commercial",
        description="Vlog 风格，自然肤色优化",
        tags=["vlog", "youtube", "日常", "自然"],
        intensity_range=(0.2, 0.6),
        best_for=["vlog", "日常", "分享"],
        mood="自然、亲和",
        lut_dir_pattern="Youtube_Vlog",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 婚礼/人像系列 ----
    "wedding": LUTPreset(
        name="wedding",
        display_name="婚礼 Wedding",
        category="wedding",
        description="婚礼柔焦暖调，肤色优化",
        tags=["婚礼", "柔焦", "浪漫"],
        intensity_range=(0.2, 0.6),
        best_for=["婚礼", "婚纱", "情侣"],
        mood="浪漫、甜蜜",
        lut_dir_pattern="Wedding",
        preferred_files=["1", "10", "50", "100"],
    ),
    "skin": LUTPreset(
        name="skin",
        display_name="肤色优化 Skin",
        category="wedding",
        description="肤色自然优化，去黄提亮",
        tags=["肤色", "人像", "美颜"],
        intensity_range=(0.2, 0.5),
        best_for=["人像", "自拍", "美妆"],
        mood="自然、清透",
        lut_dir_pattern="Skin",
        preferred_files=["1", "10", "30"],
    ),

    # ---- 旅行/冒险系列 ----
    "travel": LUTPreset(
        name="travel",
        display_name="旅行 Travel",
        category="travel",
        description="旅行记录调色，色彩鲜明自然",
        tags=["旅行", "记录", "鲜明"],
        intensity_range=(0.3, 0.7),
        best_for=["旅行", "记录", "vlog"],
        mood="自由、探索",
        lut_dir_pattern="Travel",
        preferred_files=["1", "10", "50"],
    ),
    "roadtrip": LUTPreset(
        name="roadtrip",
        display_name="公路旅行 Roadtrip",
        category="travel",
        description="公路片风格，阳光与尘土",
        tags=["公路", "旅行", "阳光"],
        intensity_range=(0.3, 0.8),
        best_for=["公路", "自驾", "户外"],
        mood="自由、粗犷",
        lut_dir_pattern="Roadtrip",
        preferred_files=["1", "10", "50"],
    ),
    "japan": LUTPreset(
        name="japan",
        display_name="日系 Japan",
        category="travel",
        description="日系清新风格，低对比柔色",
        tags=["日系", "清新", "低对比"],
        intensity_range=(0.2, 0.6),
        best_for=["日系", "清新", "文艺"],
        mood="清新、淡雅",
        lut_dir_pattern="Japan",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 特效/氛围系列 ----
    "party": LUTPreset(
        name="party",
        display_name="派对 Party",
        category="effects",
        description="派对霓虹灯光效果",
        tags=["派对", "霓虹", "灯光", "夜店"],
        intensity_range=(0.4, 0.9),
        best_for=["派对", "夜店", "活动"],
        mood="嗨、炫酷",
        lut_dir_pattern="Party",
        preferred_files=["1", "10", "50"],
    ),
    "rogue": LUTPreset(
        name="rogue",
        display_name="叛逆 Rogue",
        category="effects",
        description="叛逆暗黑色调，高对比",
        tags=["叛逆", "暗黑", "高对比"],
        intensity_range=(0.5, 1.0),
        best_for=["暗黑", "战斗", "高燃"],
        mood="叛逆、力量",
        lut_dir_pattern="Rogue",
        preferred_files=["1", "10", "50"],
    ),
    "creative": LUTPreset(
        name="creative",
        display_name="创意 Creative",
        category="effects",
        description="创意特效调色，风格化强烈",
        tags=["创意", "特效", "风格化"],
        intensity_range=(0.3, 0.8),
        best_for=["创意", "实验", "艺术"],
        mood="前卫、独特",
        lut_dir_pattern="Creative",
        preferred_files=["1", "10", "30"],
    ),
    "special_edition": LUTPreset(
        name="special_edition",
        display_name="特别版 Special Edition",
        category="effects",
        description="特别版调色，独特风格",
        tags=["特别版", "独特", "限定"],
        intensity_range=(0.3, 0.8),
        best_for=["特别", "限定", "艺术"],
        mood="独特、精致",
        lut_dir_pattern="Special_Edition",
        preferred_files=["1", "10", "30"],
    ),

    # ---- HDR/技术系列 ----
    "hdr": LUTPreset(
        name="hdr",
        display_name="HDR 高动态",
        category="technical",
        description="HDR 高动态范围，保留高光暗部细节",
        tags=["HDR", "高动态", "细节"],
        intensity_range=(0.3, 0.7),
        best_for=["HDR", "高动态", "细节保留"],
        mood="通透、立体",
        lut_dir_pattern="HDR",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 航拍/无人机系列 ----
    "drone": LUTPreset(
        name="drone",
        display_name="无人机 Drone",
        category="aerial",
        description="无人机航拍调色，天地均衡",
        tags=["无人机", "航拍", "天空"],
        intensity_range=(0.3, 0.7),
        best_for=["航拍", "无人机", "风景"],
        mood="壮阔、自由",
        lut_dir_pattern="Drone collection",
        preferred_files=["1", "10", "50"],
    ),
    "sky_views": LUTPreset(
        name="sky_views",
        display_name="天空视角 Sky Views",
        category="aerial",
        description="天空视角航拍，云层通透",
        tags=["天空", "航拍", "云层"],
        intensity_range=(0.3, 0.7),
        best_for=["航拍", "天空", "云层"],
        mood="辽阔、通透",
        lut_dir_pattern="Sky Views Drone",
        preferred_files=["1", "5", "10"],
    ),

    # ---- 户外/运动系列 ----
    "outdoors": LUTPreset(
        name="outdoors",
        display_name="户外 Outdoors",
        category="outdoor",
        description="户外运动调色，高饱和活力",
        tags=["户外", "运动", "活力"],
        intensity_range=(0.3, 0.8),
        best_for=["户外", "运动", "极限"],
        mood="活力、冒险",
        lut_dir_pattern="Outdoors",
        preferred_files=["1", "10", "30"],
    ),

    # ---- 视频博客系列 ----
    "video_blog": LUTPreset(
        name="video_blog",
        display_name="视频博客 Video Blog",
        category="vlog",
        description="视频博客自然调色",
        tags=["vlog", "博客", "自然"],
        intensity_range=(0.2, 0.6),
        best_for=["vlog", "日常", "分享"],
        mood="自然、真实",
        lut_dir_pattern="Video Blog",
        preferred_files=["1", "10", "50"],
    ),

    # ---- 精选合集 ----
    "best_luts": LUTPreset(
        name="best_luts",
        display_name="精选 Best LUTs",
        category="collection",
        description="精选最佳调色，多种风格",
        tags=["精选", "最佳", "合集"],
        intensity_range=(0.3, 0.8),
        best_for=["通用", "精选"],
        mood="多样、精致",
        lut_dir_pattern="Best_LUTs",
        preferred_files=["01", "10", "50", "100"],
    ),
}


# ============================================================================
# 场景 → 预设推荐映射
# ============================================================================

SCENE_PRESET_MAP: dict[str, list[str]] = {
    "高燃混剪": ["dramatic", "hollywood", "rogue", "cinematic"],
    "战斗场景": ["dramatic", "rogue", "silence", "noir"],
    "情感叙事": ["cinematic_02", "memories", "movie", "japan"],
    "回忆闪回": ["vintage", "old_look", "memories", "noir"],
    "城市夜景": ["city", "urban", "party", "rogue"],
    "自然风光": ["nature", "landscape", "vista", "aerial"],
    "航拍镜头": ["aerial", "drone", "sky_views", "landscape"],
    "婚礼现场": ["wedding", "skin", "memories", "paradise"],
    "人物特写": ["skin", "cinematic", "commercial", "social_media"],
    "旅行记录": ["travel", "roadtrip", "japan", "tropic"],
    "商业广告": ["commercial", "cinematic", "hollywood", "social_media"],
    "短视频/vlog": ["youtube_vlog", "social_media", "video_blog", "warm"],
    "日系清新": ["japan", "warm", "paradise", "video_blog"],
    "暗黑风格": ["noir", "rogue", "silence", "dramatic"],
    "复古怀旧": ["vintage", "old_look", "memories", "cinema"],
    "科技未来": ["cool", "urban", "creative", "rogue"],
    "派对活动": ["party", "creative", "special_edition", "rogue"],
    "户外运动": ["outdoors", "dramatic", "travel", "hdr"],
    "产品拍摄": ["commercial", "skin", "cinematic", "hdr"],
    "电影级": ["cinematic", "hollywood", "cinema", "super_cinematic"],
}


# ============================================================================
# LUT 索引引擎
# ============================================================================

class LUTLibrary:
    """LUT 库管理器"""
    
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or LUT_BASE_DIR
        self._index: dict[str, Any] | None = None
        self._file_cache: dict[str, str] = {}  # preset_name -> lut_path
    
    def _load_index(self) -> dict[str, Any]:
        """加载或构建 LUT 索引"""
        if self._index:
            return self._index
        
        # 尝试从缓存加载
        if LUT_INDEX_FILE.exists():
            with open(LUT_INDEX_FILE, "r", encoding="utf-8") as f:
                self._index = json.load(f)
            return self._index
        
        # 构建索引
        self._index = {}
        for root, dirs, files in os.walk(self.base_dir):
            cubes = [f for f in files if f.lower().endswith('.cube')]
            if cubes:
                rel = os.path.relpath(root, self.base_dir)
                self._index[rel] = {
                    "count": len(cubes),
                    "files": [os.path.join(root, f) for f in cubes]
                }
        
        # 保存索引
        with open(LUT_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
        
        return self._index
    
    def get_preset_lut(self, preset_name: str, variant: int = 1) -> str | None:
        """获取预设对应的 LUT 文件路径
        
        Args:
            preset_name: 预设名
            variant: 变体编号 (1-based)
        
        Returns:
            LUT 文件绝对路径，或 None
        """
        cache_key = f"{preset_name}_{variant}"
        if cache_key in self._file_cache:
            return self._file_cache[cache_key]
        
        preset = LUT_PRESETS.get(preset_name)
        if not preset:
            return None
        
        index = self._load_index()
        
        # 在索引中搜索匹配的目录
        for dir_name, dir_info in index.items():
            if preset.lut_dir_pattern.lower() in dir_name.lower():
                files = dir_info["files"]
                if not files:
                    continue
                
                # 选择指定变体
                if preset.preferred_files:
                    # 优先使用精选文件
                    pref_idx = (variant - 1) % len(preset.preferred_files)
                    pref_pattern = preset.preferred_files[pref_idx]
                    
                    # 搜索匹配的文件
                    for f in files:
                        if pref_pattern in os.path.basename(f):
                            self._file_cache[cache_key] = f
                            return f
                
                # 回退：按编号选择
                file_idx = (variant - 1) % len(files)
                result = files[file_idx]
                self._file_cache[cache_key] = result
                return result
        
        return None
    
    def get_all_luts_for_preset(self, preset_name: str) -> list[str]:
        """获取预设对应的所有 LUT 文件"""
        preset = LUT_PRESETS.get(preset_name)
        if not preset:
            return []
        
        index = self._load_index()
        for dir_name, dir_info in index.items():
            if preset.lut_dir_pattern.lower() in dir_name.lower():
                return dir_info["files"]
        return []
    
    def get_presets_by_category(self, category: str) -> list[LUTPreset]:
        """按分类获取预设列表"""
        return [p for p in LUT_PRESETS.values() if p.category == category]
    
    def get_presets_by_tag(self, tag: str) -> list[LUTPreset]:
        """按标签搜索预设"""
        tag_lower = tag.lower()
        return [p for p in LUT_PRESETS.values() 
                if tag_lower in [t.lower() for t in p.tags]]
    
    def get_presets_for_scene(self, scene_type: str) -> list[LUTPreset]:
        """获取场景推荐的预设列表"""
        preset_names = SCENE_PRESET_MAP.get(scene_type, [])
        return [LUT_PRESETS[n] for n in preset_names if n in LUT_PRESETS]
    
    def search_presets(self, query: str) -> list[LUTPreset]:
        """搜索预设（名称/描述/标签）"""
        query_lower = query.lower()
        results = []
        for p in LUT_PRESETS.values():
            if (query_lower in p.name.lower() or
                query_lower in p.display_name.lower() or
                query_lower in p.description.lower() or
                any(query_lower in t.lower() for t in p.tags) or
                any(query_lower in b.lower() for b in p.best_for)):
                results.append(p)
        return results
    
    def get_all_categories(self) -> list[str]:
        """获取所有分类"""
        return list(set(p.category for p in LUT_PRESETS.values()))
    
    def get_stats(self) -> dict[str, Any]:
        """获取库统计信息"""
        index = self._load_index()
        total_files = sum(info["count"] for info in index.values())
        return {
            "total_presets": len(LUT_PRESETS),
            "total_lut_files": total_files,
            "total_categories": len(index),
            "preset_categories": self.get_all_categories(),
            "scene_types": list(SCENE_PRESET_MAP.keys()),
        }
    
    def list_presets_summary(self) -> str:
        """生成预设库摘要"""
        lines = [f"=== LUT 预设库 ({len(LUT_PRESETS)} 预设) ==="]
        
        by_cat = {}
        for p in LUT_PRESETS.values():
            by_cat.setdefault(p.category, []).append(p)
        
        for cat, presets in sorted(by_cat.items()):
            lines.append(f"\n[{cat}]")
            for p in presets:
                lines.append(f"  {p.name}: {p.display_name} - {p.description}")
                lines.append(f"    标签: {', '.join(p.tags[:4])}")
                lines.append(f"    适用: {', '.join(p.best_for[:3])}")
        
        return "\n".join(lines)


# ============================================================================
# Fusion 调色脚本生成器
# ============================================================================

class FusionColorEngine:
    """通过 AddFusionComp 实现更复杂的调色效果"""
    
    @staticmethod
    def generate_brightness_contrast_lua(
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
    ) -> str:
        """生成亮度/对比度/饱和度 Fusion 合成 Lua"""
        return '''
-- Fusion Color Adjustment
local comp = item:AddFusionComp("ColorAdjust")
if comp then
    -- Note: Fusion comp created, further node setup requires Fusion scripting
    print("  Fusion comp created: ColorAdjust")
end
'''
    
    @staticmethod
    def generate_multi_lut_chain_lua(
        lut_paths: list[str],
        intensities: list[float] | None = None,
    ) -> str:
        """生成多 LUT 链式应用 Lua
        
        注意: Resolve Lua API 的 SetLUT 只支持单个 LUT，
        多次调用会覆盖。这里选择最强效果的 LUT 应用。
        """
        if not lut_paths:
            return ""
        
        if intensities is None:
            intensities = [1.0] * len(lut_paths)
        
        # 选择强度最高的 LUT
        best_idx = intensities.index(max(intensities))
        best_lut = lut_paths[best_idx].replace("\\", "\\\\")
        
        return f'''
-- Multi-LUT chain (applying strongest: variant {best_idx + 1})
print("\\n[Color] Applying best LUT from {len(lut_paths)} candidates...")
if timeline then
    local items = timeline:GetItemsInTrack("video", 1)
    if items then
        local applied = 0
        for idx, item in pairs(items) do
            local ok = pcall(function()
                item:SetLUT(1, "{best_lut}")
            end)
            if ok then applied = applied + 1 end
        end
        print("  Applied to " .. applied .. " clips")
    end
end
'''


# ============================================================================
# 便捷函数
# ============================================================================

# 全局 LUT 库实例
_lut_library: LUTLibrary | None = None

def get_lut_library() -> LUTLibrary:
    """获取全局 LUT 库实例"""
    global _lut_library
    if _lut_library is None:
        _lut_library = LUTLibrary()
    return _lut_library


def find_lut_for_preset(preset_name: str, variant: int = 1) -> str | None:
    """查找预设对应的 LUT 文件（增强版）"""
    lib = get_lut_library()
    return lib.get_preset_lut(preset_name, variant)


def get_scene_presets(scene_type: str) -> list[str]:
    """获取场景类型推荐的预设名列表"""
    return SCENE_PRESET_MAP.get(scene_type, [])


def get_preset_info(preset_name: str) -> dict[str, Any] | None:
    """获取预设详细信息"""
    preset = LUT_PRESETS.get(preset_name)
    if not preset:
        return None
    return {
        "name": preset.name,
        "display_name": preset.display_name,
        "category": preset.category,
        "description": preset.description,
        "tags": preset.tags,
        "intensity_range": preset.intensity_range,
        "best_for": preset.best_for,
        "mood": preset.mood,
        "available_luts": len(get_lut_library().get_all_luts_for_preset(preset_name)),
    }


def list_all_presets() -> list[dict[str, str]]:
    """列出所有预设概要"""
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "category": p.category,
            "description": p.description,
        }
        for p in LUT_PRESETS.values()
    ]


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    lib = get_lut_library()
    print(lib.list_presets_summary())
    print("\n" + "=" * 60)
    stats = lib.get_stats()
    print(f"\n统计: {stats['total_presets']} 预设, {stats['total_lut_files']} LUT文件, {stats['total_categories']} 分类")
    print(f"场景类型: {', '.join(stats['scene_types'][:10])}...")
