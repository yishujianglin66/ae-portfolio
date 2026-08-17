"""
kb_loader.py - 知识库程序化加载器（核心）
=========================================

解决"知识断层"问题：从400+MD文件中程序化解析效果参数映射、转场配方、调色预设，
并支持正文内容全文检索。

核心能力：
1. 多线程解析MD表格 → 结构化参数映射库
2. 解析代码块 → JSX/命令模板库
3. 解析效果名 → 关键词→matchName映射
4. 解析调色预设 → LUT参数库
5. 解析转场配方 → 转场类型→实现映射
6. 正文内容索引 → 按章节切块 + 关键词检索

设计：
- 首次加载时缓存到 JSON，后续直接读缓存
- 支持增量更新（文件变更检测）
- 外部接口：get_effect_map(), get_transition_map(), get_color_presets(), search()
"""
import os
import re
import json
import time
import glob
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent
KB_ROOT = _PROJECT_ROOT / "10-风格化剪辑知识库"
KB_ROOTS = [
    _PROJECT_ROOT / "10-风格化剪辑知识库",
    _PROJECT_ROOT / "11-大师知识库",
    _PROJECT_ROOT / "12-漫剪拉镜大师",
    _PROJECT_ROOT / "14-Silhouette 知识库",
    _PROJECT_ROOT / "15-3D模型与骨骼动画知识库",
    _PROJECT_ROOT / "13-素材获取与搜索",
]
CACHE_DIR = _PROJECT_ROOT / ".kb_cache"
CACHE_FILE = CACHE_DIR / "kb_cache.json"
CACHE_TIMEOUT = 3600  # 缓存有效期(秒)

CACHE_DIR.mkdir(parents=True, exist_ok=True)


class KBLoader:
    _instance: Optional["KBLoader"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._effect_map: Dict[str, str] = {}
        self._transition_map: Dict[str, Any] = {}
        self._color_presets: Dict[str, Any] = {}
        self._code_templates: Dict[str, List[str]] = {}
        self._content_index: List[Dict[str, Any]] = []  # 正文内容块索引
        self._stats: Dict[str, Any] = {}
        self._initialized = True
        self._load_or_scan()

    def _load_or_scan(self):
        """加载缓存或重新扫描"""
        if CACHE_FILE.exists():
            age = time.time() - CACHE_FILE.stat().st_mtime
            if age < CACHE_TIMEOUT:
                self._load_cache()
                print(f"知识库缓存加载成功 (age={age:.0f}s)")
                return
        self._scan_and_build()

    def _load_cache(self):
        """从缓存加载"""
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._effect_map = data.get("effect_map", {})
        self._transition_map = data.get("transition_map", {})
        self._color_presets = data.get("color_presets", {})
        self._code_templates = data.get("code_templates", {})
        self._content_index = data.get("content_index", [])
        self._stats = data.get("stats", {})

    def _save_cache(self):
        """保存缓存"""
        data = {
            "effect_map": self._effect_map,
            "transition_map": self._transition_map,
            "color_presets": self._color_presets,
            "code_templates": self._code_templates,
            "content_index": self._content_index,
            "stats": self._stats,
            "cache_time": time.time(),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _scan_and_build(self):
        """多线程扫描并构建映射"""
        print("开始知识库解析...")
        start = time.time()

        # 扫描所有知识库目录
        files = []
        for kb_root in KB_ROOTS:
            if kb_root.exists():
                files.extend(sorted(glob.glob(str(kb_root / "**" / "*.md"), recursive=True)))
        self._stats["total_files"] = len(files)
        self._stats["kb_roots"] = [r.name for r in KB_ROOTS if r.exists()]

        # 多线程解析
        results = self._parse_files_parallel(files, threads=8)

        # 合并结果
        for res in results:
            self._merge_effect_map(res.get("effect_map", {}))
            self._merge_transition_map(res.get("transition_map", {}))
            self._merge_color_presets(res.get("color_presets", {}))
            self._merge_code_templates(res.get("code_templates", {}))
            # 合并正文内容块
            self._content_index.extend(res.get("content_chunks", []))

        self._stats["effect_map_size"] = len(self._effect_map)
        self._stats["transition_map_size"] = len(self._transition_map)
        self._stats["color_presets_size"] = len(self._color_presets)
        self._stats["code_templates_size"] = sum(len(v) for v in self._code_templates.values())
        self._stats["content_chunks_size"] = len(self._content_index)
        self._stats["parse_time"] = time.time() - start

        self._save_cache()
        print(f"知识库解析完成! 效果映射:{len(self._effect_map)}, 转场:{len(self._transition_map)}, "
              f"调色预设:{len(self._color_presets)}, 正文块:{len(self._content_index)}, "
              f"耗时:{self._stats['parse_time']:.1f}s")

    def _parse_files_parallel(self, files: List[str], threads: int = 8) -> List[Dict]:
        """多线程解析文件"""
        results = []
        lock = threading.Lock()

        def worker(file_list):
            local_results = []
            for f in file_list:
                try:
                    res = self._parse_file(f)
                    if res:
                        local_results.append(res)
                except Exception as e:
                    pass
            with lock:
                results.extend(local_results)

        chunks = [[] for _ in range(threads)]
        for i, f in enumerate(files):
            chunks[i % threads].append(f)

        thread_list = []
        for i in range(threads):
            if chunks[i]:
                t = threading.Thread(target=worker, args=(chunks[i],))
                thread_list.append(t)
                t.start()

        for t in thread_list:
            t.join()

        return results

    def _parse_file(self, filepath: str) -> Dict[str, Any]:
        """解析单个文件"""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        filename = os.path.basename(filepath)
        result = {
            "filename": filename,
            "effect_map": {},
            "transition_map": {},
            "color_presets": {},
            "code_templates": {},
            "content_chunks": [],
        }

        # 1. 解析效果映射表格
        self._parse_effect_tables(content, result["effect_map"])

        # 2. 解析转场配方
        self._parse_transition_recipes(content, filename, result["transition_map"])

        # 3. 解析调色预设
        self._parse_color_presets(content, filename, result["color_presets"])

        # 4. 解析代码模板
        self._parse_code_templates(content, filename, result["code_templates"])

        # 5. 提取正文内容块（按 ## 章节切分）
        result["content_chunks"] = self._extract_content_chunks(content, filepath, filename)

        return result

    def _extract_content_chunks(self, content: str, filepath: str, filename: str) -> List[Dict[str, Any]]:
        """按 ## 章节标题切分正文，生成可检索的内容块"""
        chunks = []
        # 按 ## 级标题切分
        sections = re.split(r'\n(?=## )', content)
        for section in sections:
            section = section.strip()
            if len(section) < 50:  # 跳过太短的片段
                continue
            # 提取标题
            title_match = re.match(r'^#+\s+(.+)', section)
            title = title_match.group(1).strip() if title_match else filename
            # 截取正文（最多 800 字符）
            body = section[:800].strip()
            # 生成关键词摘要（标题 + 前 200 字）
            keywords_text = f"{title} {section[:200]}".lower()
            chunks.append({
                "title": title,
                "body": body,
                "source": filename,
                "filepath": filepath,
                "keywords": keywords_text,
            })
        return chunks

    def _parse_effect_tables(self, content: str, effect_map: Dict):
        """解析效果关键词→matchName映射表格"""
        tables = re.findall(r'\|([^\n]+)\|\n\|[-:| ]+\|\n((?:\|[^\n]+\|\n?)+)', content, re.MULTILINE)
        for header, rows_text in tables:
            header_cols = [c.strip() for c in header.split("|") if c.strip()]
            if len(header_cols) < 2:
                continue

            # 查找关键词和matchName列
            kw_idx = -1
            match_idx = -1
            for i, col in enumerate(header_cols):
                if any(k in col for k in ["关键词", "keyword", "名称", "name"]):
                    kw_idx = i
                if any(k in col for k in ["matchName", "MatchName", "效果名", "效果"]):
                    match_idx = i

            if kw_idx == -1 or match_idx == -1:
                continue

            for row in rows_text.strip().split("\n"):
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if len(cols) > max(kw_idx, match_idx):
                    kw = cols[kw_idx]
                    mn = cols[match_idx]
                    if kw and mn:
                        effect_map[kw] = mn

        # 从文本中直接提取效果名（fallback）
        for match in re.finditer(r"(ADBE|CC|TC|VC|BCC|RB) [A-Za-z][A-Za-z0-9 ]+(?=\s|,|\.|`|$)", content):
            full_name = match.group(0).strip()
            parts = full_name.split(None, 1)
            if len(parts) == 2:
                prefix, name = parts
                keywords = [name.lower(), name.replace(" ", "_").lower()]
                for kw in keywords:
                    if kw not in effect_map:
                        effect_map[kw] = full_name

    def _parse_transition_recipes(self, content: str, filename: str, transition_map: Dict):
        """解析转场类型→实现映射"""
        transition_patterns = [
            (r"(linear_wipe|radial_wipe|zoom_blur|glitch|light_leak|ink_spread|card_flip|block_dissolve|fade|slide)",
             r"效果[:：]\s*(ADBE [A-Za-z ]+|CC [A-Za-z ]+)"),
        ]
        for trans_type_pattern, effect_pattern in transition_patterns:
            for match in re.finditer(trans_type_pattern, content):
                trans_type = match.group(1)
                if trans_type not in transition_map:
                    transition_map[trans_type] = {"display_name": self._get_transition_display(trans_type)}

    def _parse_color_presets(self, content: str, filename: str, color_presets: Dict):
        """解析调色预设参数"""
        # 查找调色参数块
        lut_pattern = re.compile(r"(?i)(?:LUT|调色预设|颜色配置)\s*[:：]\s*(.*?)\n", re.DOTALL)
        for match in lut_pattern.finditer(content):
            preset_text = match.group(1).strip()
            if len(preset_text) < 5:
                continue
            preset_name = re.search(r"([\u4e00-\u9fa5a-zA-Z0-9]+)", preset_text)
            if preset_name:
                name = preset_name.group(1)
                if name not in color_presets:
                    color_presets[name] = {"source": filename, "params": preset_text[:100]}

    def _parse_code_templates(self, content: str, filename: str, code_templates: Dict):
        """解析代码模板"""
        code_blocks = re.findall(r'```(\w+)?\n([\s\S]*?)```', content, re.MULTILINE)
        for lang, code in code_blocks:
            lang = lang or "text"
            if lang not in code_templates:
                code_templates[lang] = []
            if len(code) > 10:
                code_templates[lang].append({
                    "source": filename,
                    "code": code.strip()[:2000],
                })

    def _merge_effect_map(self, new_map: Dict):
        """合并效果映射（知识库优先）"""
        for kw, mn in new_map.items():
            if kw not in self._effect_map:
                self._effect_map[kw] = mn

    def _merge_transition_map(self, new_map: Dict):
        """合并转场映射"""
        for trans_type, data in new_map.items():
            if trans_type not in self._transition_map:
                self._transition_map[trans_type] = data

    def _merge_color_presets(self, new_map: Dict):
        """合并调色预设"""
        for name, data in new_map.items():
            if name not in self._color_presets:
                self._color_presets[name] = data

    def _merge_code_templates(self, new_map: Dict):
        """合并代码模板"""
        for lang, templates in new_map.items():
            if lang not in self._code_templates:
                self._code_templates[lang] = []
            self._code_templates[lang].extend(templates)

    def _get_transition_display(self, trans_type: str) -> str:
        """转场类型→中文显示名"""
        mapping = {
            "linear_wipe": "线性擦除",
            "radial_wipe": "径向擦除",
            "zoom_blur": "缩放模糊",
            "glitch": "故障风格",
            "light_leak": "光效叠加",
            "ink_spread": "墨水扩散",
            "card_flip": "卡片翻转",
            "block_dissolve": "像素方块化",
            "fade": "淡入淡出",
            "slide": "滑动",
        }
        return mapping.get(trans_type, trans_type)

    def get_effect_map(self) -> Dict[str, str]:
        """获取效果关键词→matchName映射"""
        return self._effect_map

    def get_transition_map(self) -> Dict[str, Any]:
        """获取转场类型→实现映射"""
        return self._transition_map

    def get_color_presets(self) -> Dict[str, Any]:
        """获取调色预设"""
        return self._color_presets

    def get_code_templates(self, lang: Optional[str] = None) -> Dict[str, Any]:
        """获取代码模板"""
        if lang:
            return self._code_templates.get(lang, [])
        return self._code_templates

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats

    # --------------------------------------------------------------------
    # 知识检索增强（Phase 4）
    # --------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """按关键词搜索知识库内容

        支持中文/英文关键词匹配，返回最相关的知识片段。
        搜索优先级：结构化映射 > 正文内容块

        Args:
            query: 搜索查询（可以是效果名、转场类型、风格关键词等）
            top_k: 返回最多几条结果

        Returns:
            相关知识片段列表，每项包含 type/content/source 字段
        """
        query_lower = query.lower().strip()
        query_terms = set(query_lower.split())
        results: List[Dict[str, Any]] = []

        # 1. 搜索效果映射
        for kw, match_name in self._effect_map.items():
            score = self._compute_relevance(query_lower, query_terms, kw, match_name)
            if score > 0:
                results.append({
                    "type": "effect_mapping",
                    "keyword": kw,
                    "match_name": match_name,
                    "score": score,
                })

        # 2. 搜索转场映射
        for trans_type, data in self._transition_map.items():
            score = self._compute_relevance(
                query_lower, query_terms, trans_type,
                data.get("display_name", "")
            )
            if score > 0:
                results.append({
                    "type": "transition",
                    "transition_type": trans_type,
                    "display_name": data.get("display_name", ""),
                    "score": score,
                })

        # 3. 搜索调色预设
        for name, data in self._color_presets.items():
            score = self._compute_relevance(query_lower, query_terms, name, "")
            if score > 0:
                results.append({
                    "type": "color_preset",
                    "name": name,
                    "source": data.get("source", ""),
                    "score": score,
                })

        # 4. 搜索正文内容块（当结构化结果不足时补充）
        if len(results) < top_k and self._content_index:
            content_results = self._search_content(query_lower, query_terms, top_k=5)
            results.extend(content_results)

        # 按分数排序，取 top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _search_content(self, query_lower: str, query_terms: set, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索正文内容块"""
        results = []
        for chunk in self._content_index:
            keywords = chunk.get("keywords", "")
            # 计算匹配度
            matched = sum(1 for t in query_terms if t in keywords)
            if matched == 0:
                continue
            score = round(matched / len(query_terms) * 0.7, 2) if query_terms else 0
            if score > 0:
                results.append({
                    "type": "content_chunk",
                    "title": chunk.get("title", ""),
                    "body": chunk.get("body", "")[:300],
                    "source": chunk.get("source", ""),
                    "score": score,
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_context_for_llm(self, task_type: str, query: str) -> str:
        """为 LLM 调用生成知识库上下文文本

        根据任务类型和查询，生成可注入 system prompt 的知识片段。

        Args:
            task_type: 任务类型 (effect_apply / transition / color_grading / general)
            query: 用户查询/意图描述

        Returns:
            格式化的知识上下文字符串，可直接拼入 prompt
        """
        results = self.search(query, top_k=5)

        if not results:
            return ""

        context_parts = ["[知识库参考]"]

        for item in results:
            if item["type"] == "effect_mapping":
                context_parts.append(
                    f"- 效果: {item['keyword']} → AE matchName: {item['match_name']}"
                )
            elif item["type"] == "transition":
                context_parts.append(
                    f"- 转场: {item['transition_type']} ({item['display_name']})"
                )
            elif item["type"] == "color_preset":
                context_parts.append(
                    f"- 调色预设: {item['name']} (来源: {item['source']})"
                )
            elif item["type"] == "content_chunk":
                body_preview = item.get("body", "")[:150].replace("\n", " ")
                context_parts.append(
                    f"- 文档「{item['title']}」: {body_preview}... (来源: {item['source']})"
                )

        return "\n".join(context_parts)

    def _compute_relevance(self, query_lower: str, query_terms: set,
                           key: str, value: str) -> float:
        """计算查询与知识条目之间的相关性分数

        Args:
            query_lower: 小写查询字符串
            query_terms: 查询分词集合
            key: 知识条目的键/名称
            value: 知识条目的值/描述

        Returns:
            相关性分数 (0.0 ~ 1.0)，0 表示不相关
        """
        key_lower = key.lower()
        value_lower = value.lower()
        combined = f"{key_lower} {value_lower}"

        # 完全匹配
        if query_lower == key_lower:
            return 1.0

        # 查询是键的子串，或键是查询的子串
        if query_lower in key_lower or key_lower in query_lower:
            return 0.8

        # 分词匹配率
        if query_terms:
            matched = sum(1 for t in query_terms if t in combined)
            ratio = matched / len(query_terms)
            if ratio > 0:
                return round(ratio * 0.6, 2)

        return 0.0

    def get_instance():
        """便捷工厂方法"""
        return KBLoader()


if __name__ == "__main__":
    loader = KBLoader()
    print("\n=== 知识库加载器验证 ===")
    print(f"效果映射条目: {len(loader.get_effect_map())}")
    print(f"转场类型: {len(loader.get_transition_map())}")
    print(f"调色预设: {len(loader.get_color_presets())}")

    print("\n=== 示例效果映射 ===")
    effect_map = loader.get_effect_map()
    for kw, mn in list(effect_map.items())[:15]:
        print(f"  {kw:<25} → {mn}")

    print("\n=== 示例转场 ===")
    trans_map = loader.get_transition_map()
    for tt, data in list(trans_map.items())[:10]:
        print(f"  {tt:<20} → {data.get('display_name', '')}")

    print("\n=== 示例调色预设 ===")
    presets = loader.get_color_presets()
    for name, data in list(presets.items())[:10]:
        print(f"  {name:<20} → {data.get('source', '')}")

    print("\n=== 代码模板分类 ===")
    templates = loader.get_code_templates()
    for lang, items in templates.items():
        print(f"  {lang:<15} → {len(items)} 个模板")
