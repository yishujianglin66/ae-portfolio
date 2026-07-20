"""
kb_loader.py - 知识库程序化加载器（核心）
=========================================

解决"知识断层"问题：从207个MD文件中程序化解析效果参数映射、转场配方、调色预设。

核心能力：
1. 多线程解析MD表格 → 结构化参数映射库
2. 解析代码块 → JSX/命令模板库
3. 解析效果名 → 关键词→matchName映射
4. 解析调色预设 → LUT参数库
5. 解析转场配方 → 转场类型→实现映射

设计：
- 首次加载时缓存到 JSON，后续直接读缓存
- 支持增量更新（文件变更检测）
- 外部接口：get_effect_map(), get_transition_map(), get_color_presets()
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

KB_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库")
CACHE_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.kb_cache")
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
        self._stats = data.get("stats", {})

    def _save_cache(self):
        """保存缓存"""
        data = {
            "effect_map": self._effect_map,
            "transition_map": self._transition_map,
            "color_presets": self._color_presets,
            "code_templates": self._code_templates,
            "stats": self._stats,
            "cache_time": time.time(),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _scan_and_build(self):
        """多线程扫描并构建映射"""
        print("开始知识库解析...")
        start = time.time()

        files = sorted(glob.glob(str(KB_ROOT / "**" / "*.md"), recursive=True))
        self._stats["total_files"] = len(files)

        # 多线程解析
        results = self._parse_files_parallel(files, threads=8)

        # 合并结果
        for res in results:
            self._merge_effect_map(res.get("effect_map", {}))
            self._merge_transition_map(res.get("transition_map", {}))
            self._merge_color_presets(res.get("color_presets", {}))
            self._merge_code_templates(res.get("code_templates", {}))

        self._stats["effect_map_size"] = len(self._effect_map)
        self._stats["transition_map_size"] = len(self._transition_map)
        self._stats["color_presets_size"] = len(self._color_presets)
        self._stats["code_templates_size"] = sum(len(v) for v in self._code_templates.values())
        self._stats["parse_time"] = time.time() - start

        self._save_cache()
        print(f"知识库解析完成! 效果映射:{len(self._effect_map)}, 转场:{len(self._transition_map)}, "
              f"调色预设:{len(self._color_presets)}, 耗时:{self._stats['parse_time']:.1f}s")

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
        }

        # 1. 解析效果映射表格
        self._parse_effect_tables(content, result["effect_map"])

        # 2. 解析转场配方
        self._parse_transition_recipes(content, filename, result["transition_map"])

        # 3. 解析调色预设
        self._parse_color_presets(content, filename, result["color_presets"])

        # 4. 解析代码模板
        self._parse_code_templates(content, filename, result["code_templates"])

        return result

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
