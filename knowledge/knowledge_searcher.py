#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职场知识补充系统
===============

支持从多个平台搜索相关职场学习知识：
- 知乎：职场经验、行业知识
- 知网：学术文献、研究报告
- 小红书：职场技能、面试技巧
- 快手：职场视频、技能教程
- 微博：行业资讯、热点话题

使用方式：
    from knowledge_searcher import KnowledgeSearcher
    
    searcher = KnowledgeSearcher()
    
    # 搜索知识
    results = searcher.search("锂电池维护 注意事项", platforms=["知乎", "小红书"])
    
    # 智能推荐
    recommendations = searcher.recommend("设备维护技术员", context="新能源行业")
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class KnowledgeItem:
    """知识条目"""
    platform: str
    title: str
    url: str
    summary: str
    author: str = ""
    publish_date: str = ""
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0


class KnowledgeSearcher:
    """职场知识搜索器"""
    
    # 平台搜索URL模板
    PLATFORM_URLS = {
        "知乎": "https://www.zhihu.com/search?type=content&q={query}",
        "小红书": "https://www.xiaohongshu.com/search_result?keyword={query}",
        "微博": "https://s.weibo.com/weibo?q={query}",
        "快手": "https://www.kuaishou.com/search/video?searchKey={query}",
        "知网": "https://www.cnki.net/search?query={query}",
    }
    
    # 职场学习关键词库（设备维护技术员相关）
    CAREER_KEYWORDS = {
        "专业技能": [
            "设备维护", "设备检修", "故障诊断", "预防性维护",
            "锂电池", "新能源电池", "电池管理系统", "BMS",
            "电气原理图", "PLC编程", "自动化设备",
        ],
        "软技能": [
            "职场沟通", "团队协作", "汇报技巧", "会议主持",
            "班长管理", "团队领导", "冲突解决",
        ],
        "职业发展": [
            "实习转正", "职业规划", "技能提升", "晋升路径",
            "新能源行业", "智能制造", "设备工程师",
        ],
        "学习方法": [
            "高效学习", "知识管理", "时间管理", "复盘方法",
        ],
    }
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / "14-职场学习成长档案" / "05-知识补充"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 平台子目录
        for platform in self.PLATFORM_URLS.keys():
            (self.cache_dir / platform).mkdir(parents=True, exist_ok=True)
    
    def search(self, query: str, platforms: list[str] = None, max_results: int = 5) -> dict[str, list[KnowledgeItem]]:
        """搜索知识
        
        Args:
            query: 搜索关键词
            platforms: 平台列表，默认全部
            max_results: 每个平台最大结果数
            
        Returns:
            按平台分类的搜索结果
        """
        if platforms is None:
            platforms = list(self.PLATFORM_URLS.keys())
        
        results = {}
        
        for platform in platforms:
            if platform not in self.PLATFORM_URLS:
                continue
            
            # 这里返回搜索URL，实际搜索需要用户在浏览器中完成
            # 或者通过WebSearch工具搜索
            results[platform] = self._search_platform(platform, query, max_results)
        
        # 保存搜索结果
        self._save_search_results(query, results)
        
        return results
    
    def _search_platform(self, platform: str, query: str, max_results: int) -> list[KnowledgeItem]:
        """搜索单个平台"""
        # 构建搜索URL
        search_url = self.PLATFORM_URLS[platform].format(query=query)
        
        # 返回一个占位结果（实际搜索需要通过WebSearch或浏览器）
        items = [
            KnowledgeItem(
                platform=platform,
                title=f"请在{platform}搜索: {query}",
                url=search_url,
                summary=f"点击链接在{platform}中搜索相关内容",
                tags=["待搜索"],
            )
        ]
        
        return items
    
    def recommend(self, position: str, context: str = "", keywords: list[str] = None) -> dict[str, Any]:
        """智能推荐知识
        
        根据职位和上下文推荐相关学习内容。
        
        Args:
            position: 职位名称
            context: 上下文信息
            keywords: 额外关键词
            
        Returns:
            推荐结果
        """
        recommendations = {
            "position": position,
            "context": context,
            "keywords": keywords or [],
            "search_queries": [],
            "learning_paths": [],
        }
        
        # 从关键词库匹配
        matched_keywords = []
        for category, kws in self.CAREER_KEYWORDS.items():
            for kw in kws:
                if kw in position or kw in context:
                    matched_keywords.append({"category": category, "keyword": kw})
        
        recommendations["matched_keywords"] = matched_keywords
        
        # 生成搜索查询
        for mk in matched_keywords[:5]:
            query = f"{mk['keyword']} {position}"
            recommendations["search_queries"].append({
                "category": mk["category"],
                "query": query,
                "platforms": self._get_recommended_platforms(mk["category"]),
            })
        
        # 推荐学习路径
        recommendations["learning_paths"] = self._generate_learning_paths(position)
        
        return recommendations
    
    def _get_recommended_platforms(self, category: str) -> list[str]:
        """根据类别获取推荐平台"""
        platform_map = {
            "专业技能": ["知乎", "知网", "小红书"],
            "软技能": ["知乎", "小红书", "微博"],
            "职业发展": ["知乎", "小红书", "微博"],
            "学习方法": ["知乎", "小红书"],
        }
        return platform_map.get(category, ["知乎", "小红书"])
    
    def _generate_learning_paths(self, position: str) -> list[dict[str, Any]]:
        """生成学习路径"""
        paths = []
        
        if "设备维护" in position or "技术员" in position:
            paths.append({
                "name": "设备维护技能路径",
                "steps": [
                    "1. 学习设备基础知识和安全规范",
                    "2. 掌握电气原理图和机械结构",
                    "3. 学习故障诊断方法和维修工具使用",
                    "4. 实践预防性维护和日常巡检",
                    "5. 提升故障分析和问题解决能力",
                ],
            })
        
        if "班长" in position or "管理" in position:
            paths.append({
                "name": "基层管理能力路径",
                "steps": [
                    "1. 学习沟通技巧和团队协作方法",
                    "2. 掌握会议主持和任务分配技巧",
                    "3. 学习冲突处理和团队激励方法",
                    "4. 提升汇报能力和文档写作",
                    "5. 建立个人管理风格和领导力",
                ],
            })
        
        if "新能源" in position or "电池" in position:
            paths.append({
                "name": "新能源技术路径",
                "steps": [
                    "1. 学习锂电池基础原理和特性",
                    "2. 了解电池管理系统(BMS)架构",
                    "3. 掌握电池检测设备和维护工具",
                    "4. 学习电池安全规范和应急处理",
                    "5. 关注行业动态和技术发展",
                ],
            })
        
        return paths
    
    def _save_search_results(self, query: str, results: dict[str, list[KnowledgeItem]]):
        """保存搜索结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"search_{timestamp}_{query[:20]}.json"
        filepath = self.cache_dir / filename
        
        data = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": {
                platform: [
                    {
                        "platform": item.platform,
                        "title": item.title,
                        "url": item.url,
                        "summary": item.summary,
                        "tags": item.tags,
                    }
                    for item in items
                ]
                for platform, items in results.items()
            }
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_search_history(self) -> list[dict[str, Any]]:
        """获取搜索历史"""
        history = []
        
        for filepath in self.cache_dir.glob("search_*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    history.append(json.load(f))
            except:
                pass
        
        return sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def quick_search(self, topic: str) -> dict[str, str]:
        """快速搜索 - 返回各平台搜索链接
        
        Args:
            topic: 搜索主题
            
        Returns:
            各平台的搜索链接
        """
        links = {}
        
        for platform, url_template in self.PLATFORM_URLS.items():
            links[platform] = url_template.format(query=topic)
        
        return links


# 全局实例
_searcher = None


def get_searcher() -> KnowledgeSearcher:
    """获取全局搜索器实例"""
    global _searcher
    if _searcher is None:
        _searcher = KnowledgeSearcher()
    return _searcher


def search_knowledge(query: str, platforms: list[str] = None) -> dict[str, list[KnowledgeItem]]:
    """快捷函数：搜索知识"""
    return get_searcher().search(query, platforms)


def recommend_learning(position: str, context: str = "") -> dict[str, Any]:
    """快捷函数：推荐学习内容"""
    return get_searcher().recommend(position, context)


def quick_search(topic: str) -> dict[str, str]:
    """快捷函数：快速获取搜索链接"""
    return get_searcher().quick_search(topic)


if __name__ == "__main__":
    # 测试
    searcher = KnowledgeSearcher()
    
    print("=" * 60)
    print("职场知识补充系统 - 测试")
    print("=" * 60)
    
    # 智能推荐
    print("\n智能推荐测试（设备维护技术员）：")
    recommendations = searcher.recommend("设备维护技术员", "新能源锂电池")
    
    print("\n匹配关键词：")
    for kw in recommendations["matched_keywords"]:
        print(f"  - [{kw['category']}] {kw['keyword']}")
    
    print("\n推荐搜索：")
    for sq in recommendations["search_queries"][:3]:
        print(f"  - {sq['query']} -> {sq['platforms']}")
    
    print("\n学习路径：")
    for path in recommendations["learning_paths"]:
        print(f"\n  【{path['name']}】")
        for step in path["steps"]:
            print(f"    {step}")
    
    # 快速搜索
    print("\n" + "=" * 60)
    print("快速搜索测试（锂电池维护）：")
    links = searcher.quick_search("锂电池维护 注意事项")
    for platform, link in links.items():
        print(f"  [{platform}] {link}")
    
    print("\n" + "=" * 60)
    print("测试完成")