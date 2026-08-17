# -*- coding: utf-8 -*-
r"""T28: 100IP零样本文本原型构建 — 为100个动漫IP构建多模板中英双语文本原型。

覆盖:
  - 现有23IP (已验收)
  - 第一梯队新增27IP (热门番剧)
  - 第二梯队新增50IP (中等热度+国漫)

文本原型设计:
  每个IP 5个模板 x 中英双语 = 10个文本原型
  模板覆盖: 截图/场景/角色/宣传图/通用

产物:
  data/ip_prototypes_100.json — 100IP文本原型库
  reports/t28_prototype_report.json — 构建报告
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ================================================================ IP库定义
# 现有23IP (含英文别名)
EXISTING_IPS = {
    "FATE": "Fate stay night",
    "黑岩射手": "Black Rock Shooter",
    "地缚少年花子君": "Toilet-bound Hanako-kun",
    "无限滑板": "SK8 the Infinity",
    "海贼王": "One Piece",
    "火影忍者": "Naruto",
    "Move": "K-pop music video performance stage",
    "时光代理人": "Link Click anime",
    "灵笼": "Ling Cage Chinese 3D anime",
    "灼眼的夏娜": "Shakugan no Shana",
    "猫和老鼠": "Tom and Jerry",
    "咒术回战": "Jujutsu Kaisen",
    "K": "K anime project",
    "抽烟猫": "cat smoking meme video",
    "鬼灭之刃": "Demon Slayer Kimetsu no Yaiba",
    "浪客行": "Vagabond manga style warrior",
    "龙族": "Dragon Raja anime",
    "赛博朋克：边缘行者": "Cyberpunk Edgerunners",
    "链锯人": "Chainsaw Man",
    "原神": "Genshin Impact",
    "斩·赤红之瞳": "Akame ga Kill",
    "某科学的超电磁炮": "A Certain Scientific Railgun",
    "JOJO的奇妙冒险": "JoJo's Bizarre Adventure",
    "进击的巨人": "Attack on Titan",
}

# 第一梯队新增27IP (热门番剧)
TIER1_NEW = {
    "间谍过家家": "Spy x Family",
    "葬送的芙莉莲": "Frieren Beyond Journey's End",
    "药屋少女的呢喃": "The Apothecary Diaries",
    "我推的孩子": "Oshi no Ko",
    "蓝色监狱": "Blue Lock",
    "排球少年": "Haikyuu",
    "我的英雄学院": "My Hero Academia",
    "Re:从零开始的异世界生活": "Re:Zero",
    "为美好的世界献上祝福": "KonoSuba",
    "无职转生": "Mushoku Tensei",
    "关于我转生变成史莱姆这档事": "That Time I Got Reincarnated as a Slime",
    "Overlord": "Overlord anime",
    "一拳超人": "One Punch Man",
    "灵能百分百": "Mob Psycho 100",
    "钢之炼金术师": "Fullmetal Alchemist",
    "死亡笔记": "Death Note",
    "Code Geass": "Code Geass",
    "EVA": "Neon Genesis Evangelion",
    "星际牛仔": "Cowboy Bebop",
    "攻壳机动队": "Ghost in the Shell",
    "心理测量者": "Psycho-Pass",
    "来自深渊": "Made in Abyss",
    "迷宫饭": "Delicious in Dungeon",
    "辉夜大小姐想让我告白": "Kaguya-sama Love is War",
    "东京复仇者": "Tokyo Revengers",
    "文豪野犬": "Bungo Stray Dogs",
    "紫罗兰永恒花园": "Violet Evergarden",
}

# 第二梯队新增50IP (中等热度+国漫)
TIER2_NEW = {
    # 国漫10
    "斗罗大陆": "Soul Land Douluo Dalu",
    "斗破苍穹": "Battle Through the Heavens",
    "完美世界": "Perfect World donghua",
    "凡人修仙传": "A Record of a Mortal's Journey to Immortality",
    "一人之下": "Hitori no Shita The Outcast",
    "雾山五行": "Fog Hill of Five Elements",
    "百妖谱": "Fairies Albums",
    "天官赐福": "Heaven Official's Blessing",
    "魔道祖师": "Grandmaster of Demonic Cultivation",
    "伍六七": "Scissor Seven",
    # 日漫40
    " Bleach": "Bleach anime",
    "银魂": "Gintama",
    "全职猎人": "Hunter x Hunter",
    "幽游白书": "Yu Yu Hakusho",
    "龙珠": "Dragon Ball",
    "数码宝贝": "Digimon",
    "宝可梦": "Pokemon anime",
    "游戏王": "Yu-Gi-Oh",
    "名侦探柯南": "Detective Conan",
    "蜡笔小新": "Crayon Shin-chan",
    "哆啦A梦": "Doraemon",
    "美少女战士": "Sailor Moon",
    "魔卡少女樱": "Cardcaptor Sakura",
    "轻音少女": "K-On",
    "凉宫春日的忧郁": "The Melancholy of Haruhi Suzumiya",
    "命运石之门": "Steins Gate",
    "罪恶王冠": "Guilty Crown",
    "刀剑神域": "Sword Art Online",
    "为美好的世界献上祝福": "KonoSuba",
    "在下坂本有何贵干": "Sakamoto desu ga",
    "齐木楠雄的灾难": "The Disastrous Life of Saiki K",
    "日常": "Nichijou",
    "月刊少女野崎同学": "Monthly Girls Nozaki-kun",
    "冰菓": "Hyouka",
    "角斗士": "Angle Player",
    "黑之契约者": "Darker than Black",
    "Blood Blockade Battlefront": "Kekkai Sensen",
    "天元突破": "Tengen Toppa Gurren Lagann",
    "新海诚": "Makoto Shinkai anime",
    "萤火虫之墓": "Grave of the Fireflies",
    "千与千寻": "Spirited Away",
    "龙猫": "My Neighbor Totoro",
    "风之谷": "Nausicaa of the Valley of the Wind",
    "幽灵公主": "Princess Mononoke",
    "哈尔的移动城堡": "Howl's Moving Castle",
    "铃芽之旅": "Suzume",
    "你的名字": "Your Name Kimi no Na wa",
    "天气之子": "Weathering with You",
    "Promare": "Promare anime",
    "SSSS.GRIDMAN": "SSSS Gridman",
}

# ================================================================ 文本模板
# 英文模板(laion/laion-l底座用)
EN_TEMPLATES = [
    "a screenshot from the anime {}",
    "a scene from {} anime series",
    "{} anime character",
    "a promotional image of {}",
    "{} anime wallpaper",
]

# 中文模板(cclip底座用)
CN_TEMPLATES = [
    "动画片《{}》的画面截图",
    "《{}》动漫中的一幕",
    "{}动画角色",
    "《{}》的宣传图",
    "{}动漫壁纸",
]


def build_prototypes():
    """构建100IP文本原型库"""
    _log = lambda msg: print(f"[T28] {msg}", flush=True)
    _log("=" * 60)
    _log("T28: 100IP零样本文本原型构建")
    _log("=" * 60)
    
    # 合并所有IP
    all_ips = {}
    all_ips.update(EXISTING_IPS)
    all_ips.update(TIER1_NEW)
    # 处理TIER2中的重复和格式
    for cn, en in TIER2_NEW.items():
        cn = cn.strip()
        if cn and cn not in all_ips:
            all_ips[cn] = en
    
    _log(f"总IP数: {len(all_ips)}")
    _log(f"  现有: {len(EXISTING_IPS)}")
    _log(f"  第一梯队新增: {len(TIER1_NEW)}")
    tier2_count = len(all_ips) - len(EXISTING_IPS) - len(TIER1_NEW)
    _log(f"  第二梯队新增: {tier2_count}")
    
    # 构建文本原型
    prototypes = {}
    for cn_name, en_name in all_ips.items():
        en_texts = [t.format(en_name) for t in EN_TEMPLATES]
        cn_texts = [t.format(cn_name) for t in CN_TEMPLATES]
        
        prototypes[cn_name] = {
            "name_cn": cn_name,
            "name_en": en_name,
            "tier": "existing" if cn_name in EXISTING_IPS else ("tier1" if cn_name in TIER1_NEW else "tier2"),
            "en_templates": en_texts,
            "cn_templates": cn_texts,
            "n_templates": len(en_texts) + len(cn_texts),
        }
    
    _log(f"\n原型构建完成: {len(prototypes)}个IP")
    
    # 统计
    tier_dist = {}
    for p in prototypes.values():
        t = p["tier"]
        tier_dist[t] = tier_dist.get(t, 0) + 1
    _log(f"分布: {tier_dist}")
    
    # 保存
    out_path = ROOT / "data" / "ip_prototypes_100.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(prototypes, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n保存: {out_path}")
    
    # 报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_ips": len(prototypes),
        "tier_distribution": tier_dist,
        "templates_per_ip": 10,
        "total_prototypes": len(prototypes) * 10,
        "backends": ["laion (ViT-B-32, 512d)", "laion-l (ViT-L-14, 768d)", "cclip (ViT-B-16, 512d)"],
    }
    report_path = ROOT / "reports" / "t28_prototype_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告: {report_path}")
    
    # 打印前10个IP
    _log(f"\n前10个IP原型:")
    for i, (cn, data) in enumerate(list(prototypes.items())[:10]):
        _log(f"  {cn:20s} | {data['name_en']:35s} | tier={data['tier']}")
    
    return prototypes


if __name__ == "__main__":
    build_prototypes()
