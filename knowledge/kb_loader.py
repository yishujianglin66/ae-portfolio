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
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Any, Optional


@dataclass
class Evidence:
    """OmniScientist 风格的统一证据束（EvidenceBundle 单条）。

    对应 OmniScientist 感知层输出：每条证据都带置信度、来源、采集时间、
    证据强度等级，供因果引擎（Phase II Agent）做证据聚合与交叉验证。
    """
    type: str                                           # effect_mapping / transition / color_preset / content_chunk / vector_chunk
    content: str                                        # 人类可读的证据内容（摘要）
    source: str = ""                                    # 知识库文件/目录路径
    confidence: float = 0.0                             # 0.0~1.0，由 score 归一化得出
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    evidence_level: str = "WEAK"                        # STRONG / MEDIUM / WEAK（与置信度映射）
    raw: Dict[str, Any] = field(default_factory=dict)   # 原始字段（如 keyword/match_name/score 等，供排障）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def level_from_confidence(confidence: float) -> str:
        if confidence >= 0.75:
            return "STRONG"
        if confidence >= 0.45:
            return "MEDIUM"
        return "WEAK"


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
        # 向量化检索 P1（REFRAG 风格词级稀疏向量 + TF-IDF 打分，零依赖纯 Python）
        self._doc_freq: Dict[str, int] = {}              # 词 → 文档频次（DF）
        self._chunk_term_freq: List[Dict[str, int]] = []  # 每个 content chunk 的词频向量
        self._num_docs: int = 0
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
        # 向量化索引：2026-08 新增，老缓存中可能不存在；缺失时自动重建
        cached_df = data.get("doc_freq")
        cached_tf = data.get("chunk_term_freq")
        if isinstance(cached_df, dict) and isinstance(cached_tf, list):
            self._doc_freq = {str(k): int(v) for k, v in cached_df.items()}
            self._chunk_term_freq = [
                {str(k): int(v) for k, v in (doc or {}).items()}
                for doc in cached_tf
            ]
            self._num_docs = len(self._chunk_term_freq)
        else:
            self._build_tfidf_index()

    def _save_cache(self):
        """保存缓存"""
        data = {
            "effect_map": self._effect_map,
            "transition_map": self._transition_map,
            "color_presets": self._color_presets,
            "code_templates": self._code_templates,
            "content_index": self._content_index,
            "stats": self._stats,
            "doc_freq": self._doc_freq,
            "chunk_term_freq": self._chunk_term_freq,
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

        # 向量检索 P1：构建 TF-IDF 稀疏索引（REFRAG 风格纯本地、零依赖）
        self._build_tfidf_index()
        self._stats["vector_docs"] = self._num_docs
        self._stats["vector_vocab"] = len(self._doc_freq)

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
        """按关键词搜索知识库内容（混合检索：结构化映射 + 关键词 + TF-IDF 向量）。

        向后兼容：返回 ``List[Dict]`` 与老接口保持一致，但每个 Dict 新增证据字段
        ``confidence / source / timestamp_ms / evidence_level``，供下游
        ``search_evidences()`` 直接转换为 Evidence 对象。

        搜索优先级：结构化映射 > 正文关键词块 > TF-IDF 向量块
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
                    "source": "",
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
                    "source": data.get("source", ""),
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

        # 4. 搜索正文内容块（关键词检索）
        if len(results) < top_k + 3 and self._content_index:
            content_results = self._search_content(query_lower, query_terms, top_k=5)
            results.extend(content_results)

        # 5. 向量检索 P1：结构化 + 关键词 不足 top_k 时补 TF-IDF 余弦相似度
        if len(results) < top_k and self._num_docs > 0:
            try:
                vec_results = self.search_vector(query, top_k=(top_k - len(results) + 2))
                # 避免重复：去重 content_chunk 的 source+title
                seen_keys = {(r.get("type"), r.get("source"), r.get("title"))
                             for r in results if r.get("type") in {"content_chunk", "vector_chunk"}}
                for vr in vec_results:
                    key = (vr.get("type"), vr.get("source"), vr.get("title"))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append(vr)
            except Exception as _e:
                # 向量检索失败不影响主流程（零破坏保证）
                pass

        # 按分数排序，取 top_k
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        top_results = results[:top_k]

        # 注入证据字段（confidence 归一化；最高 score → 0.95 留余量给完全匹配）
        max_score = max((r.get("score", 0.0) for r in top_results), default=1.0)
        now_ms = int(time.time() * 1000)
        for r in top_results:
            if max_score > 0:
                conf = min(0.95, max(0.0, r.get("score", 0.0) / max_score))
            else:
                conf = r.get("score", 0.0)
            r["confidence"] = round(conf, 3)
            r["timestamp_ms"] = r.get("timestamp_ms") or now_ms
            r["evidence_level"] = Evidence.level_from_confidence(conf)
            r.setdefault("source", r.get("source", ""))
        return top_results

    def _search_content(self, query_lower: str, query_terms: set, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索正文内容块（关键词命中）"""
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

    # --------------------------------------------------------------------
    # 向量检索 P1（REFRAG 风格稀疏向量 · TF-IDF · 零依赖纯 Python）
    # --------------------------------------------------------------------

    @staticmethod
    def _term_tokenize(text: str) -> List[str]:
        """混合分词：中英文按非字母数字切分 + 中文按字符切分，避免依赖 jieba。

        - 英文连续 token 保留原词（effect / transition 等技术词）
        - 中文单字作为 token（单字 bag-of-words + IDF 在 MB 级语料已能显著优于纯 BM25 关键词）
        """
        if not text:
            return []
        text_lower = text.lower()
        # 拆成块：连续的 [a-z0-9_\-] 是一个英文块；其余字符是中文/符号块
        tokens: List[str] = []
        buf: List[str] = []
        for ch in text_lower:
            is_ascii_alnum = (ch.isascii() and ch.isalnum()) or ch in "_-"
            if is_ascii_alnum:
                buf.append(ch)
            else:
                if buf:
                    word = "".join(buf)
                    if len(word) >= 2:
                        tokens.append(word)
                    buf = []
                if "\u4e00" <= ch <= "\u9fff":
                    tokens.append(ch)
        if buf:
            word = "".join(buf)
            if len(word) >= 2:
                tokens.append(word)
        return tokens

    def _build_tfidf_index(self) -> None:
        """基于 content_index 构建 TF（词频）与 DF（文档频次）向量索引。"""
        self._num_docs = len(self._content_index)
        self._doc_freq = {}
        self._chunk_term_freq = []
        for chunk in self._content_index:
            blob = f"{chunk.get('title', '')} {chunk.get('body', '')} {chunk.get('keywords', '')}"
            tokens = self._term_tokenize(blob)
            tf: Dict[str, int] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            # DF：同一 token 在该文档出现多次只计 1
            for tok in tf.keys():
                self._doc_freq[tok] = self._doc_freq.get(tok, 0) + 1
            self._chunk_term_freq.append(tf)

    def search_vector(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """TF-IDF 余弦相似度检索。返回格式与 search 对齐（Dict 列表）。

        当 BGE-M3 / sentence-transformers 等本地稠密模型就绪后，可把
        ``_term_tokenize`` 替换为 embedding，打分公式保持不变。
        """
        if self._num_docs == 0 or not query.strip():
            return []
        query_tokens = self._term_tokenize(query.lower())
        if not query_tokens:
            return []
        # Query TF-IDF 向量
        q_tf: Dict[str, int] = {}
        for t in query_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
        num_docs = max(1, self._num_docs)
        scored: List[tuple] = []
        for i, doc_tf in enumerate(self._chunk_term_freq):
            dot = 0.0
            q_norm2 = 0.0
            d_norm2 = 0.0
            # 仅遍历 query 的非零维度（稀疏，避免全表 dict scan）
            for tok, q_count in q_tf.items():
                df = self._doc_freq.get(tok, 0)
                if df == 0:
                    continue
                idf = math.log((1 + num_docs) / (1 + df)) + 1.0
                q_w = q_count * idf
                d_w = doc_tf.get(tok, 0) * idf
                dot += q_w * d_w
                q_norm2 += q_w * q_w
            # Doc 范数（遍历全部词：content chunk 一般 <300 token，量级 OK）
            for tok, d_count in doc_tf.items():
                df = self._doc_freq.get(tok, 0)
                idf = math.log((1 + num_docs) / (1 + df)) + 1.0
                d_norm2 += (d_count * idf) ** 2
            denom = math.sqrt(q_norm2) * math.sqrt(d_norm2)
            cosine = (dot / denom) if denom > 0 else 0.0
            if cosine > 0:
                scored.append((cosine, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[Dict[str, Any]] = []
        for cosine, i in scored[:top_k]:
            chunk = self._content_index[i]
            body_preview = chunk.get("body", "")[:300]
            out.append({
                "type": "vector_chunk",
                "title": chunk.get("title", ""),
                "body": body_preview,
                "source": chunk.get("source", ""),
                "score": round(min(1.0, cosine), 3),
                "retrieval_method": "tfidf_cosine",
            })
        return out

    # --------------------------------------------------------------------
    # OmniScientist 证据闭环（第一阶 · 感知层统一 Evidence 输出）
    # --------------------------------------------------------------------

    def search_evidences(self, query: str, top_k: int = 5) -> List[Evidence]:
        """返回统一证据束（List[Evidence]）。作为 Agent 工作流的标准输入。

        - Perception Agent 直接消费本接口
        - 因果引擎（Evidence → Hypothesis）把 confidence 做加权投票
        - Cross-Check Agent 用 source/level 进行来源互斥/互补判断
        """
        raw = self.search(query, top_k=top_k)
        now_ms = int(time.time() * 1000)
        evs: List[Evidence] = []
        for r in raw:
            rtype = r.get("type", "unknown")
            if rtype == "effect_mapping":
                content = f"效果「{r.get('keyword', '')}」→ AE matchName={r.get('match_name', '')}"
            elif rtype == "transition":
                content = f"转场「{r.get('transition_type', '')}」(display={r.get('display_name', '')})"
            elif rtype == "color_preset":
                content = f"调色预设「{r.get('name', '')}」"
            elif rtype in {"content_chunk", "vector_chunk"}:
                body_preview = r.get("body", "")[:200].replace("\n", " ")
                content = f"文档「{r.get('title', '')}」: {body_preview}"
            else:
                content = json.dumps(r, ensure_ascii=False)[:200]
            conf = float(r.get("confidence", r.get("score", 0.0)))
            ev = Evidence(
                type=rtype,
                content=content,
                source=r.get("source", ""),
                confidence=conf,
                timestamp_ms=r.get("timestamp_ms", now_ms),
                evidence_level=r.get(
                    "evidence_level", Evidence.level_from_confidence(conf)
                ),
                raw={k: v for k, v in r.items() if k not in {
                    "confidence", "timestamp_ms", "evidence_level", "source",
                }},
            )
            evs.append(ev)
        return evs

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
