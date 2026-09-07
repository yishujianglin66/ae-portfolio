"""搜索项目需要的素材片段"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from material_searcher import BilibiliAdapter, MikananiAdapter
from pathlib import Path

OUTPUT_DIR = Path("output_director/materials")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("  项目素材搜索 - 进击的巨人混剪")
print("=" * 60)

# 搜索关键词列表（按混剪需求）
search_queries = [
    "进击的巨人 利威尔 高燃",
    "进击的巨人 艾伦 变身",
    "进击的巨人 调查兵团 冲锋",
    "进击的巨人 最终季 战斗",
    "进击的巨人 OP 开场",
]

bilibili = BilibiliAdapter()
mikanani = MikananiAdapter()

print(f"\nB站可用: {bilibili.is_available()}")
print(f"蜜柑计划可用: {mikanani.is_available()}")

# 搜索B站片段
print("\n" + "=" * 60)
print("  B站素材片段")
print("=" * 60)

all_bilibili_results = []
for query in search_queries:
    print(f"\n搜索: {query}")
    try:
        videos = bilibili._search_bilibili(query, max_results=3)
        for v in videos:
            all_bilibili_results.append({**v, "search_query": query})
            print(f"  [{v['duration']}] {v['title'][:50]}")
            print(f"    链接: {v['url']}")
            print(f"    播放: {v['play']}")
    except Exception as e:
        print(f"  搜索失败: {e}")

# 搜索蜜柑计划种子
print("\n" + "=" * 60)
print("  蜜柑计划种子资源")
print("=" * 60)

for query in ["进击的巨人", "Shingeki no Kyojin"]:
    print(f"\n搜索: {query}")
    try:
        results = mikanani.search_and_download(query, OUTPUT_DIR, max_results=2)
        for r in results:
            if r.get("torrent_url"):
                print(f"  种子: {r['name']}")
                print(f"    下载: {r['torrent_url']}")
    except Exception as e:
        print(f"  搜索失败: {e}")

# 输出汇总
print("\n" + "=" * 60)
print("  素材汇总")
print("=" * 60)
print(f"\nB站视频: {len(all_bilibili_results)} 个")
for i, v in enumerate(all_bilibili_results, 1):
    print(f"{i}. [{v['duration']}] {v['title'][:40]}")
    print(f"   {v['url']}")
