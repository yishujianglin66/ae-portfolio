"""
语义解析器 - 解析用户输入提取语义和音频参数

支持自然语言输入，自动识别：
- 视觉描述（用于CLIP语义搜索）
- 音频参数（BPM、情绪、曲风）
- 素材类型（视频/BGM/图片）
- 质量要求（高清/无水印）
"""

from __future__ import annotations

import json
import re
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedQuery:
    """解析后的查询结构"""
    # 原始输入
    raw_input: str = ""
    
    # 语义查询（用于CLIP搜索）
    semantic_query: str = ""
    
    # 音频特征
    target_bpm: Optional[float] = None
    bpm_range: Optional[tuple] = None
    mood: Optional[str] = None
    mood_score: Optional[float] = None
    genre: Optional[str] = None
    
    # 素材类型
    media_type: str = "video"  # video, audio, image
    
    # 质量要求
    quality: str = "medium"  # low, medium, high, 4k
    watermark_free: bool = False
    duration_range: Optional[tuple] = None
    
    # 平台偏好
    preferred_platforms: List[str] = field(default_factory=list)
    
    # 关键词标签
    tags: List[str] = field(default_factory=list)
    
    # 置信度
    confidence: float = 0.0


class SemanticParser:
    """语义解析器"""
    
    # 情绪词映射（扩展版）
    MOOD_KEYWORDS = {
        "开心": ("happy", 0.9),
        "快乐": ("happy", 0.85),
        "欢乐": ("happy", 0.8),
        "愉悦": ("happy", 0.85),
        "愉快": ("happy", 0.8),
        "欢乐": ("happy", 0.75),
        "喜庆": ("happy", 0.8),
        "欢快": ("happy", 0.85),
        "兴奋": ("excited", 0.9),
        "激动": ("excited", 0.85),
        "激情": ("excited", 0.8),
        "狂热": ("excited", 0.85),
        "高涨": ("excited", 0.8),
        "悲伤": ("sad", 0.9),
        "忧伤": ("sad", 0.85),
        "忧郁": ("sad", 0.8),
        "难过": ("sad", 0.75),
        "哀伤": ("sad", 0.85),
        "悲痛": ("sad", 0.9),
        "伤感": ("sad", 0.8),
        "落寞": ("sad", 0.8),
        "愤怒": ("angry", 0.9),
        "生气": ("angry", 0.85),
        "愤慨": ("angry", 0.85),
        "暴怒": ("angry", 0.9),
        "平静": ("calm", 0.9),
        "宁静": ("calm", 0.85),
        "平和": ("calm", 0.8),
        "安详": ("calm", 0.85),
        "放松": ("relaxed", 0.9),
        "舒缓": ("relaxed", 0.85),
        "悠闲": ("relaxed", 0.8),
        "惬意": ("relaxed", 0.85),
        "浪漫": ("romantic", 0.9),
        "温馨": ("romantic", 0.85),
        "甜蜜": ("romantic", 0.8),
        "柔情": ("romantic", 0.85),
        "柔情蜜意": ("romantic", 0.8),
        "唯美": ("romantic", 0.8),
        "励志": ("inspirational", 0.9),
        "激昂": ("inspirational", 0.85),
        "振奋": ("inspirational", 0.85),
        "鼓舞": ("inspirational", 0.8),
        "热血": ("energetic", 0.9),
        "动感": ("energetic", 0.85),
        "活力": ("energetic", 0.8),
        "元气": ("energetic", 0.85),
        "奔放": ("energetic", 0.8),
        "紧张": ("tense", 0.9),
        "悬疑": ("tense", 0.85),
        "紧迫": ("tense", 0.8),
        "急促": ("tense", 0.85),
        "恐怖": ("scary", 0.9),
        "惊悚": ("scary", 0.85),
        "吓人": ("scary", 0.8),
        "诡异": ("scary", 0.85),
        "神秘": ("mysterious", 0.9),
        "奇幻": ("mysterious", 0.8),
        "魔幻": ("mysterious", 0.85),
        "玄幻": ("mysterious", 0.8),
        "搞笑": ("funny", 0.9),
        "幽默": ("funny", 0.85),
        "诙谐": ("funny", 0.8),
        "滑稽": ("funny", 0.85),
        "爆笑": ("funny", 0.9),
        "深情": ("emotional", 0.9),
        "感人": ("emotional", 0.85),
        "动人": ("emotional", 0.8),
        "温馨感人": ("emotional", 0.85),
        "震撼": ("epic", 0.9),
        "大气": ("epic", 0.85),
        "史诗": ("epic", 0.8),
        "磅礴": ("epic", 0.85),
        "壮丽": ("epic", 0.8),
        "辉煌": ("epic", 0.85),
        "庄严": ("epic", 0.8),
        "温馨治愈": ("healing", 0.9),
        "治愈": ("healing", 0.85),
        "温暖": ("healing", 0.8),
        "抚慰": ("healing", 0.85),
        "空灵": ("ethereal", 0.9),
        "飘渺": ("ethereal", 0.85),
        "梦幻": ("ethereal", 0.8),
        "唯美梦幻": ("ethereal", 0.85),
        "酷炫": ("cool", 0.9),
        "炫酷": ("cool", 0.9),
        "帅气": ("cool", 0.8),
        "潮流": ("cool", 0.85),
        "时尚": ("cool", 0.8),
        "复古": ("vintage", 0.9),
        "怀旧": ("vintage", 0.85),
        "经典": ("vintage", 0.8),
        "年代感": ("vintage", 0.85),
    }
    
    # 曲风关键词（扩展版）
    GENRE_KEYWORDS = {
        "流行": "pop",
        "流行音乐": "pop",
        "流行歌曲": "pop",
        "摇滚": "rock",
        "摇滚乐": "rock",
        "重金属": "metal",
        "电子": "electronic",
        "电音": "electronic",
        "电子音乐": "electronic",
        "EDM": "electronic",
        "古典": "classical",
        "古典音乐": "classical",
        "爵士": "jazz",
        "爵士乐": "jazz",
        "嘻哈": "hiphop",
        "说唱": "hiphop",
        "Rap": "hiphop",
        "民谣": "folk",
        "民谣歌曲": "folk",
        "古风": "chinese_folk",
        "国风": "chinese_folk",
        "中国风": "chinese_folk",
        "传统音乐": "chinese_folk",
        "R&B": "rnb",
        "节奏布鲁斯": "rnb",
        "蓝调": "blues",
        "蓝调音乐": "blues",
        "乡村": "country",
        "乡村音乐": "country",
        "金属": "metal",
        "金属乐": "metal",
        "朋克": "punk",
        "朋克摇滚": "punk",
        "舞曲": "dance",
        "慢摇": "dance",
        "迪斯科": "dance",
        "纯音乐": "instrumental",
        "轻音乐": "light_music",
        "背景音乐": "light_music",
        "钢琴": "piano",
        "钢琴曲": "piano",
        "钢琴独奏": "piano",
        "吉他": "guitar",
        "吉他曲": "guitar",
        "吉他独奏": "guitar",
        "小提琴": "violin",
        "小提琴曲": "violin",
        "大提琴": "cello",
        "萨克斯": "saxophone",
        "小号": "trumpet",
        "长笛": "flute",
        "二胡": "chinese_erhu",
        "古筝": "chinese_guzheng",
        "琵琶": "chinese_pipa",
        "合成器": "synth",
        "合成器流行": "synth",
        "氛围": "ambient",
        "氛围音乐": "ambient",
        "New Age": "new_age",
        "新世纪": "new_age",
        "世界音乐": "world",
        "民族音乐": "world",
        "电影配乐": "film_score",
        "影视配乐": "film_score",
        "原声音乐": "film_score",
        "OST": "film_score",
        "游戏音乐": "game",
        "游戏配乐": "game",
        "广告音乐": "commercial",
        "广告配乐": "commercial",
        "企业宣传片": "commercial",
        "纪录片": "documentary",
        "纪录片配乐": "documentary",
        "婚礼音乐": "wedding",
        "婚礼配乐": "wedding",
        "喜庆音乐": "wedding",
        "悲伤音乐": "sad_music",
        "哀乐": "sad_music",
        "葬礼音乐": "sad_music",
        "儿童音乐": "children",
        "儿歌": "children",
        "摇篮曲": "children",
        "圣诞音乐": "christmas",
        "节日音乐": "holiday",
        "春节音乐": "holiday",
        "情人节": "valentine",
        "浪漫音乐": "romantic_music",
        "情歌": "romantic_music",
        "情歌对唱": "romantic_music",
        "励志音乐": "inspirational",
        "激励音乐": "inspirational",
        "正能量": "inspirational",
        "动感音乐": "energetic",
        "活力音乐": "energetic",
        "快节奏": "energetic",
        "慢节奏": "slow",
        "舒缓音乐": "slow",
        "放松音乐": "slow",
        "冥想音乐": "meditation",
        "瑜伽音乐": "meditation",
        "睡眠音乐": "sleep",
        "助眠音乐": "sleep",
        "白噪音": "sleep",
        "恐怖音乐": "horror",
        "悬疑音乐": "horror",
        "惊悚音乐": "horror",
        "科幻音乐": "sci-fi",
        "未来感": "sci-fi",
        "太空音乐": "sci-fi",
        "史诗音乐": "epic",
        "大气音乐": "epic",
        "震撼音乐": "epic",
        "管弦乐": "orchestra",
        "交响乐": "orchestra",
        "合唱团": "choral",
        "阿卡贝拉": "a cappella",
        "翻唱": "cover",
        "改编": "cover",
        "混音": "remix",
        "Remix": "remix",
        "现场版": "live",
        "演唱会": "live",
        "Demo": "demo",
        "小样": "demo",
        "原创": "original",
        "独立音乐": "indie",
        "地下音乐": "indie",
        "实验音乐": "experimental",
        "先锋音乐": "experimental",
        "工业音乐": "industrial",
        "哥特": "gothic",
        "暗黑": "gothic",
        "低保真": "lo-fi",
        "Lo-fi": "lo-fi",
        "低保真音乐": "lo-fi",
        "卧室流行": "bedroom_pop",
        "冲浪摇滚": "surf_rock",
        "车库摇滚": "garage_rock",
        "英伦摇滚": "britpop",
        "独立摇滚": "indie_rock",
        "另类摇滚": "alternative_rock",
        "后朋克": "post_punk",
        "新浪潮": "new_wave",
        "放克": "funk",
        "放克音乐": "funk",
        "拉丁音乐": "latin",
        "萨尔萨": "salsa",
        "雷鬼": "reggae",
        "雷鬼音乐": "reggae",
        "Dub": "dub",
        "Dancehall": "dancehall",
        "浩室": "house",
        "House音乐": "house",
        "Techno": "techno",
        "Trance": "trance",
        "Drum&Bass": "drum_and_bass",
        "DnB": "drum_and_bass",
        "Dubstep": "dubstep",
        "Trap": "trap",
        "Future Bass": "future_bass",
        "Chillwave": "chillwave",
        "Synthwave": "synthwave",
        "蒸汽波音乐": "vaporwave",
        "蒸汽波": "vaporwave",
        "城市流行": "city_pop",
        "KPOP": "kpop",
        "韩国流行": "kpop",
        "JPOP": "jpop",
        "日本流行": "jpop",
        "偶像音乐": "idol",
        "动漫音乐": "anime",
        "动画音乐": "anime",
        "特摄音乐": "tokusatsu",
        "特摄剧": "tokusatsu",
    }
    
    # 平台关键词（扩展版）
    PLATFORM_KEYWORDS = {
        "抖音": "douyin",
        "抖音短视频": "douyin",
        "抖音音乐": "douyin",
        "抖音热门": "douyin",
        "B站": "bilibili",
        "哔哩哔哩": "bilibili",
        "Bilibili": "bilibili",
        "B站音乐": "bilibili",
        "B站热门": "bilibili",
        "YouTube": "youtube",
        "youtube": "youtube",
        "油管": "youtube",
        "Youtube": "youtube",
        "YouTube音乐": "youtube",
        "YouTube热门": "youtube",
        "快手": "kuaishou",
        "快手短视频": "kuaishou",
        "快手热门": "kuaishou",
        "TikTok": "tiktok",
        "tiktok": "tiktok",
        "TikTok音乐": "tiktok",
        "TikTok热门": "tiktok",
        "小红书": "xiaohongshu",
        "小红书笔记": "xiaohongshu",
        "小红书种草": "xiaohongshu",
        "微博": "weibo",
        "微博热门": "weibo",
        "微博音乐": "weibo",
        "网易云": "netease",
        "网易云音乐": "netease",
        "网易云音乐": "netease",
        "QQ音乐": "qqmusic",
        "QQ音乐": "qqmusic",
        "酷狗": "kugou",
        "酷狗音乐": "kugou",
        "酷我": "kuwo",
        "酷我音乐": "kuwo",
        "虾米": "xiami",
        "虾米音乐": "xiami",
        "Apple Music": "apple_music",
        "苹果音乐": "apple_music",
        "Spotify": "spotify",
        "声破天": "spotify",
        "网易云": "netease",
        "咪咕": "migu",
        "咪咕音乐": "migu",
        "QQ音乐": "qqmusic",
        "全民K歌": "kge",
        "唱吧": "changba",
        "喜马拉雅": "ximalaya",
        "Podcast": "podcast",
        "播客": "podcast",
        "荔枝": "lizhi",
        "蜻蜓FM": "qingting",
        "网易云播客": "netease_podcast",
        "B站直播": "bilibili_live",
        "抖音直播": "douyin_live",
        "快手直播": "kuaishou_live",
        "YY直播": "yy",
        "虎牙": "huya",
        "斗鱼": "douyu",
        "Twitch": "twitch",
        "Twitch直播": "twitch",
        "A站": "acfun",
        "AcFun": "acfun",
        "Acfun": "acfun",
        "爱奇艺": "iqiyi",
        "爱奇艺视频": "iqiyi",
        "腾讯视频": "tencent_video",
        "优酷": "youku",
        "优酷视频": "youku",
        "芒果TV": "mangotv",
        "芒果TV": "mangotv",
        "哔哩哔哩动画": "bilibili",
        "腾讯动漫": "tencent_comic",
        "爱奇艺动漫": "iqiyi_comic",
        "PP视频": "ppvideo",
        "搜狐视频": "sohu_video",
        "乐视": "le_video",
        "暴风影音": "baofeng",
        "西瓜视频": "xigua",
        "火山小视频": "huoshan",
        "皮皮虾": "pipixia",
        "微视": "weishi",
        "秒拍": "miaopai",
        "美拍": "meipai",
        "小咖秀": "xiaokaxiu",
        "FaceU": "faceu",
        "快手极速版": "kuaishou",
        "抖音极速版": "douyin",
        "今日头条": "toutiao",
        "头条": "toutiao",
        "抖音火山版": "douyin",
        "TikTok国际版": "tiktok",
        "抖音海外版": "tiktok",
        "YouTube Shorts": "youtube",
        "YouTube短视频": "youtube",
        "Instagram": "instagram",
        "IG": "instagram",
        "Ins": "instagram",
        "Reels": "instagram",
        "Facebook": "facebook",
        "FB": "facebook",
        "Messenger": "messenger",
        "WhatsApp": "whatsapp",
        "Twitter": "twitter",
        "X": "twitter",
        "Twitter视频": "twitter",
        "Reddit": "reddit",
        "Reddit视频": "reddit",
        "Vimeo": "vimeo",
        "Dailymotion": "dailymotion",
        "Vevo": "vevo",
        "SoundCloud": "soundcloud",
        "SoundCloud音乐": "soundcloud",
        "Bandcamp": "bandcamp",
        "Bandcamp音乐": "bandcamp",
        "Mixcloud": "mixcloud",
        "Beatport": "beatport",
        "Beatport音乐": "beatport",
        "Traxsource": "traxsource",
        "Junodownload": "junodownload",
        "Discogs": "discogs",
        "Last.fm": "lastfm",
        "RateYourMusic": "rym",
        "AllMusic": "allmusic",
        "Genius": "genius",
        "Genius歌词": "genius",
        "AZLyrics": "azlyrics",
        "MetroLyrics": "metrolyrics",
        "QQ音乐": "qqmusic",
        "酷我音乐": "kuwo",
        "酷狗音乐": "kugou",
        "咪咕音乐": "migu",
        "网易云音乐": "netease",
        "喜马拉雅": "ximalaya",
        "荔枝FM": "lizhi",
        "蜻蜓FM": "qingting",
        "懒人听书": "lanshu",
        "企鹅FM": "qie_fm",
        "多听FM": "duoting",
        "氧气听书": "yangqi",
        "听听FM": "tingting",
        "考拉FM": "kaola",
        "凤凰FM": "fenghuang",
        "优听Radio": "youlisten",
        "爱音斯坦FM": "aiyinsitan",
        "中国广播": "cnradio",
        "央广之声": "cnradio",
        "喜马拉雅FM": "ximalaya",
    }
    
    # 质量关键词（长词优先匹配）
    QUALITY_KEYWORDS = {
        "4K高清": "4k",
        "8K超清": "4k",
        "蓝光": "high",
        "超清": "high",
        "4K": "4k",
        "8K": "4k",
        "高清": "high",
        "标清": "low",
    }
    
    # 素材类型关键词
    MEDIA_TYPE_KEYWORDS = {
        "视频": "video",
        "素材": "video",
        "画面": "video",
        "片段": "video",
        "BGM": "audio",
        "音乐": "audio",
        "音频": "audio",
        "配乐": "audio",
        "图片": "image",
        "照片": "image",
        "封面": "image",
    }
    
    # BPM范围关键词（注意：长词优先匹配，避免"快手"被"快"误匹配）
    BPM_RANGES = {
        "舒缓": (60, 90),
        "中等速度": (90, 120),
        "正常速度": (90, 120),
        "动感": (120, 150),
        "极速": (150, 200),
    }
    
    # 中文虚词（用于清理语义查询）
    STOP_WORDS = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
    
    def __init__(self):
        self._confidence = 0.0
        self._parsed_query = ParsedQuery()
    
    def parse(self, input_text: str) -> ParsedQuery:
        """解析用户输入"""
        self._parsed_query = ParsedQuery(raw_input=input_text)
        self._confidence = 0.0
        score_count = 0
        
        # 提取语义查询（去除所有参数关键词后的纯描述）
        semantic_query = self._extract_semantic_query(input_text)
        if semantic_query:
            self._parsed_query.semantic_query = semantic_query
            self._confidence += 0.2
            score_count += 1
        
        # 提取BPM
        bpm_result = self._extract_bpm(input_text)
        if bpm_result:
            self._parsed_query.target_bpm = bpm_result.get("target")
            self._parsed_query.bpm_range = bpm_result.get("range")
            self._confidence += 0.15
            score_count += 1
        
        # 提取情绪
        mood_result = self._extract_mood(input_text)
        if mood_result:
            self._parsed_query.mood = mood_result["mood"]
            self._parsed_query.mood_score = mood_result["score"]
            self._confidence += 0.15
            score_count += 1
        
        # 提取曲风
        genre = self._extract_genre(input_text)
        if genre:
            self._parsed_query.genre = genre
            self._confidence += 0.1
            score_count += 1
        
        # 提取素材类型
        media_type = self._extract_media_type(input_text)
        if media_type:
            self._parsed_query.media_type = media_type
            self._confidence += 0.1
            score_count += 1
        
        # 提取质量要求
        quality = self._extract_quality(input_text)
        if quality:
            self._parsed_query.quality = quality
            self._confidence += 0.05
            score_count += 1
        
        # 提取无水印要求
        self._parsed_query.watermark_free = self._extract_watermark_free(input_text)
        if self._parsed_query.watermark_free:
            self._confidence += 0.05
            score_count += 1
        
        # 提取平台偏好
        platforms = self._extract_platforms(input_text)
        if platforms:
            self._parsed_query.preferred_platforms = platforms
            self._confidence += 0.05
            score_count += 1
        
        # 提取标签
        tags = self._extract_tags(input_text)
        if tags:
            self._parsed_query.tags = tags
            self._confidence += 0.05
            score_count += 1
        
        # 计算置信度
        if score_count > 0:
            self._parsed_query.confidence = min(self._confidence, 1.0)
        
        return self._parsed_query
    
    def _extract_semantic_query(self, text: str) -> str:
        """提取语义查询（去除参数关键词和虚词）"""
        cleaned = text
        
        # 移除BPM精确值（如 "BPM120", "120BPM"）
        cleaned = re.sub(r"\d+\s*BPM|BPM\s*\d+", "", cleaned, flags=re.IGNORECASE)
        
        # 按关键词长度降序排列移除，避免部分匹配
        # 移除情绪词
        for kw in sorted(self.MOOD_KEYWORDS.keys(), key=len, reverse=True):
            cleaned = cleaned.replace(kw, " ")
        
        # 移除曲风词
        for kw in sorted(self.GENRE_KEYWORDS.keys(), key=len, reverse=True):
            cleaned = cleaned.replace(kw, " ")
        
        # 移除平台词
        for kw in sorted(self.PLATFORM_KEYWORDS.keys(), key=len, reverse=True):
            cleaned = cleaned.replace(kw, " ")
        
        # 移除质量词
        for kw in sorted(self.QUALITY_KEYWORDS.keys(), key=len, reverse=True):
            cleaned = cleaned.replace(kw, " ")
        
        # 移除类型词
        for kw in sorted(self.MEDIA_TYPE_KEYWORDS.keys(), key=len, reverse=True):
            cleaned = cleaned.replace(kw, " ")
        
        # 移除其他参数词
        cleaned = re.sub(r"无水印|去水印|无标识|纯净|高清无水印", " ", cleaned)
        cleaned = re.sub(r"舒缓|动感|极速|中等速度|正常速度", " ", cleaned)
        
        # 移除中文虚词
        for word in self.STOP_WORDS:
            cleaned = cleaned.replace(word, " ")
        
        # 移除多余空格和标点
        cleaned = re.sub(r"[，。！？、；：""''（）【】\[\]{}]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # 如果清理后为空或只有单字，返回原始文本（保留完整语义）
        if len(cleaned) <= 0:
            return text
        
        # 如果清理后长度不到原始长度的10%且原始文本较长，说明几乎全是参数词，返回原始文本
        if len(cleaned) < len(text) * 0.1 and len(text) > 10:
            return text
        
        return cleaned
    
    def _extract_bpm(self, text: str) -> Optional[Dict[str, Any]]:
        """提取BPM值或范围"""
        # 精确BPM值
        bpm_match = re.search(r"(\d{2,3})\s*BPM|BPM\s*(\d{2,3})", text, flags=re.IGNORECASE)
        if bpm_match:
            bpm = int(bpm_match.group(1) or bpm_match.group(2))
            return {"target": float(bpm), "range": (bpm - 5, bpm + 5)}
        
        # 描述性BPM范围
        for kw, bpm_range in self.BPM_RANGES.items():
            if kw in text:
                target_bpm = sum(bpm_range) / 2
                return {"target": float(target_bpm), "range": bpm_range}
        
        return None
    
    def _extract_mood(self, text: str) -> Optional[Dict[str, Any]]:
        """提取情绪"""
        best_mood = None
        best_score = 0.0
        
        for kw, (mood, score) in self.MOOD_KEYWORDS.items():
            if kw in text:
                if score > best_score:
                    best_mood = mood
                    best_score = score
        
        if best_mood:
            return {"mood": best_mood, "score": best_score}
        
        return None
    
    def _extract_genre(self, text: str) -> Optional[str]:
        """提取曲风（优先匹配更长更具体的关键词）"""
        best_genre = None
        best_len = 0
        
        for kw, genre in self.GENRE_KEYWORDS.items():
            if kw in text and len(kw) > best_len:
                best_genre = genre
                best_len = len(kw)
        
        return best_genre
    
    def _extract_media_type(self, text: str) -> Optional[str]:
        """提取素材类型"""
        for kw, media_type in self.MEDIA_TYPE_KEYWORDS.items():
            if kw in text:
                return media_type
        return None
    
    def _extract_quality(self, text: str) -> Optional[str]:
        """提取质量要求"""
        for kw, quality in self.QUALITY_KEYWORDS.items():
            if kw in text:
                return quality
        return None
    
    def _extract_watermark_free(self, text: str) -> bool:
        """提取无水印要求"""
        watermark_keywords = ["无水印", "去水印", "无标识", "纯净", "高清无水印"]
        return any(kw in text for kw in watermark_keywords)
    
    def _extract_platforms(self, text: str) -> List[str]:
        """提取平台偏好（去重）"""
        platforms = []
        seen = set()
        for kw, platform in self.PLATFORM_KEYWORDS.items():
            if kw in text and platform not in seen:
                platforms.append(platform)
                seen.add(platform)
        return platforms
    
    def _extract_tags(self, text: str) -> List[str]:
        """提取关键词标签"""
        tags = []
        
        # 提取情绪词作为标签
        for kw in self.MOOD_KEYWORDS:
            if kw in text:
                tags.append(kw)
        
        # 提取曲风词作为标签
        for kw in self.GENRE_KEYWORDS:
            if kw in text:
                tags.append(kw)
        
        return tags


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python semantic_parser.py --json-input '<JSON字符串>'")
        print("示例: python semantic_parser.py --json-input '{\"query\": \"开心的流行音乐 BPM120 抖音 BGM\"}'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        query = input_json.get("query", "")
        
        parser = SemanticParser()
        parsed = parser.parse(query)
        
        result = {
            "success": True,
            "raw_input": parsed.raw_input,
            "semantic_query": parsed.semantic_query,
            "target_bpm": parsed.target_bpm,
            "bpm_range": parsed.bpm_range,
            "mood": parsed.mood,
            "mood_score": parsed.mood_score,
            "genre": parsed.genre,
            "media_type": parsed.media_type,
            "quality": parsed.quality,
            "watermark_free": parsed.watermark_free,
            "preferred_platforms": parsed.preferred_platforms,
            "tags": parsed.tags,
            "confidence": round(parsed.confidence, 2),
        }
        
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "error": f"JSON解析错误: {str(e)}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"执行错误: {str(e)}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
