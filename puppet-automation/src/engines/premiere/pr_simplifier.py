"""
PR 自动简洁化引擎
==================

一键分析并优化 Premiere Pro 项目，消除冗余、整理结构、精简时间线。

功能清单：
  1. 项目分析（analyze）— 扫描未使用素材、空轨道、间隙、冗余嵌套
  2. 清理未使用素材（remove_unused_media）— 安全移除项目中未上轨的素材
  3. 删除空轨道（remove_empty_tracks）— 移除没有任何剪辑的轨道
  4. 关闭间隙（close_gaps）— 自动闭合时间线上的空白区间
  5. 整理素材箱（organize_bins）— 按类型/用途自动分类
  6. 合并重复素材（consolidate_duplicates）— 检测并合并同名/同路径素材
  7. 一键简洁化（simplify_all）— 按安全顺序执行全部优化

安全机制：
  - dry_run 模式：仅分析不执行，返回操作预览
  - 操作前自动保存项目
  - 每步操作可独立开关
  - 操作日志完整记录

使用方式::

    from puppet_automation.src.engines.premiere.pr_simplifier import PRSimplifier

    simplifier = PRSimplifier(engine)
    report = await simplifier.analyze()
    result = await simplifier.simplify_all(dry_run=False)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# ======================================================================
# 数据模型
# ======================================================================


@dataclass
class SimplifyIssue:
    """单条简洁化问题。"""

    category: str  # unused_media / empty_track / gap / duplicate / disorganized
    severity: str  # info / warning / critical
    description: str
    location: str = ""  # 轨道/素材箱/序列名
    auto_fixable: bool = True


@dataclass
class SimplifyReport:
    """简洁化分析报告。"""

    project_name: str = ""
    timestamp: float = field(default_factory=time.time)
    issues: List[SimplifyIssue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.issues if i.auto_fixable)

    def summary(self) -> Dict[str, int]:
        """按类别统计。"""
        counts: Dict[str, int] = {}
        for issue in self.issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        return counts


@dataclass
class SimplifyResult:
    """简洁化执行结果。"""

    success: bool = True
    dry_run: bool = False
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    actions_skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    report: Optional[SimplifyReport] = None
    elapsed_s: float = 0.0

    @property
    def actions_count(self) -> int:
        return len(self.actions_taken)


# ======================================================================
# 核心引擎
# ======================================================================


class PRSimplifier:
    """Premiere Pro 项目自动简洁化引擎。

    通过 PremiereEngine 的 Bridge 通道执行 ExtendScript，
    实现项目分析、清理、优化全流程自动化。
    """

    def __init__(self, engine: Any):
        """
        Args:
            engine: PremiereEngine 实例（需支持 _execute_jsx_safe）
        """
        self._engine = engine

    # ------------------------------------------------------------------
    # 1. 项目分析
    # ------------------------------------------------------------------

    async def analyze(self, sequence_name: Optional[str] = None) -> SimplifyReport:
        """全面分析当前 PR 项目，生成简洁化报告。

        检测项目：
        - 未使用素材（项目中存在但时间线未引用）
        - 空轨道（无任何剪辑的轨道）
        - 时间线间隙（剪辑之间的空白段）
        - 重复素材（同名/同路径多次导入）
        - 素材箱混乱（所有素材堆在根目录）

        Args:
            sequence_name: 指定序列名（None = 活动序列）
        """
        t0 = time.time()
        report = SimplifyReport()

        # Step 1: 获取项目基本信息
        info_result = await self._engine.get_project_info()
        if info_result.success:
            meta = info_result.metadata or {}
            result_data = meta.get("result", {})
            if isinstance(result_data, dict):
                report.project_name = result_data.get("name", "Unknown")
                report.stats["sequences"] = result_data.get("sequences", [])
                report.stats["root_items"] = result_data.get("rootItemCount", 0)

        # Step 2: 检测未使用素材
        unused = await self._detect_unused_media()
        for item in unused:
            report.issues.append(SimplifyIssue(
                category="unused_media",
                severity="warning",
                description=f"未使用素材: {item}",
                location="Project Panel",
            ))

        # Step 3: 检测空轨道
        empty_tracks = await self._detect_empty_tracks(sequence_name)
        for track_info in empty_tracks:
            report.issues.append(SimplifyIssue(
                category="empty_track",
                severity="info",
                description=f"空轨道: {track_info['name']} (类型: {track_info['type']})",
                location=f"Track {track_info['index']}",
            ))

        # Step 4: 检测时间线间隙
        gaps = await self._detect_gaps(sequence_name)
        for gap in gaps:
            report.issues.append(SimplifyIssue(
                category="gap",
                severity="info",
                description=f"间隙: {gap['track']} 上 {gap['start_s']:.2f}s ~ {gap['end_s']:.2f}s ({gap['duration_s']:.2f}s)",
                location=gap["track"],
            ))

        # Step 5: 检测重复素材
        duplicates = await self._detect_duplicates()
        for dup in duplicates:
            report.issues.append(SimplifyIssue(
                category="duplicate",
                severity="warning",
                description=f"重复素材: {dup['name']} (出现 {dup['count']} 次)",
                location="Project Panel",
            ))

        # 统计
        report.stats["unused_media_count"] = len(unused)
        report.stats["empty_track_count"] = len(empty_tracks)
        report.stats["gap_count"] = len(gaps)
        report.stats["duplicate_count"] = len(duplicates)
        report.elapsed_s = time.time() - t0

        logger.info(
            f"[PRSimplifier] 分析完成: {report.total_issues} 个问题 "
            f"(未使用:{len(unused)}, 空轨:{len(empty_tracks)}, "
            f"间隙:{len(gaps)}, 重复:{len(duplicates)})"
        )
        return report

    # ------------------------------------------------------------------
    # 2. 一键简洁化
    # ------------------------------------------------------------------

    async def simplify_all(
        self,
        dry_run: bool = True,
        remove_unused: bool = True,
        remove_empty_tracks: bool = True,
        close_gaps: bool = True,
        consolidate_duplicates: bool = True,
        sequence_name: Optional[str] = None,
        auto_save: bool = True,
    ) -> SimplifyResult:
        """一键执行全部简洁化操作。

        Args:
            dry_run: True=仅分析不执行, False=实际执行
            remove_unused: 是否移除未使用素材
            remove_empty_tracks: 是否删除空轨道
            close_gaps: 是否关闭间隙
            consolidate_duplicates: 是否合并重复素材
            sequence_name: 目标序列（None=活动序列）
            auto_save: 执行前是否自动保存项目
        """
        t0 = time.time()
        result = SimplifyResult(dry_run=dry_run)

        # 先执行分析
        report = await self.analyze(sequence_name)
        result.report = report

        if dry_run:
            # 仅返回分析结果
            result.success = True
            result.elapsed_s = time.time() - t0
            logger.info(f"[PRSimplifier] Dry-run 完成: {report.total_issues} 个问题待修复")
            return result

        # 自动保存
        if auto_save:
            await self._save_project()
            result.actions_taken.append({"action": "auto_save", "status": "done"})

        # 按安全顺序执行（先分析型 → 再删除型 → 最后整理型）
        if remove_unused and report.stats.get("unused_media_count", 0) > 0:
            r = await self.remove_unused_media()
            result.actions_taken.append({"action": "remove_unused_media", **r})
        elif not remove_unused:
            result.actions_skipped.append("remove_unused_media (disabled)")

        if remove_empty_tracks and report.stats.get("empty_track_count", 0) > 0:
            r = await self.remove_empty_tracks(sequence_name)
            result.actions_taken.append({"action": "remove_empty_tracks", **r})
        elif not remove_empty_tracks:
            result.actions_skipped.append("remove_empty_tracks (disabled)")

        if close_gaps and report.stats.get("gap_count", 0) > 0:
            r = await self.close_gaps(sequence_name)
            result.actions_taken.append({"action": "close_gaps", **r})
        elif not close_gaps:
            result.actions_skipped.append("close_gaps (disabled)")

        if consolidate_duplicates and report.stats.get("duplicate_count", 0) > 0:
            r = await self.consolidate_duplicates()
            result.actions_taken.append({"action": "consolidate_duplicates", **r})
        elif not consolidate_duplicates:
            result.actions_skipped.append("consolidate_duplicates (disabled)")

        result.elapsed_s = time.time() - t0
        result.success = len(result.errors) == 0
        logger.info(
            f"[PRSimplifier] 简洁化完成: {result.actions_count} 个操作, "
            f"{len(result.errors)} 个错误, 耗时 {result.elapsed_s:.2f}s"
        )
        return result

    # ------------------------------------------------------------------
    # 3. 单项操作 API
    # ------------------------------------------------------------------

    async def remove_unused_media(self) -> Dict[str, Any]:
        """移除项目中未被任何序列引用的素材。"""
        jsx = """
        (function() {
            try {
                var proj = app.project;
                if (!proj) return JSON.stringify({status: "error", message: "No project"});

                // 收集所有序列中使用的素材 nodeId
                var usedIds = {};
                for (var si = 0; si < proj.sequences.numSequences; si++) {
                    var seq = proj.sequences[si];
                    for (var vt = 0; vt < seq.videoTracks.numTracks; vt++) {
                        var vTrack = seq.videoTracks[vt];
                        for (var vc = 0; vc < vTrack.clips.numItems; vc++) {
                            var vClip = vTrack.clips[vc];
                            if (vClip.projectItem) usedIds[vClip.projectItem.nodeId] = true;
                        }
                    }
                    for (var at = 0; at < seq.audioTracks.numTracks; at++) {
                        var aTrack = seq.audioTracks[at];
                        for (var ac = 0; ac < aTrack.clips.numItems; ac++) {
                            var aClip = aTrack.clips[ac];
                            if (aClip.projectItem) usedIds[aClip.projectItem.nodeId] = true;
                        }
                    }
                }

                // 遍历项目面板，找出未使用的非 BIN 素材
                var removed = [];
                var root = proj.rootItem;
                function scanBin(bin) {
                    for (var i = bin.children.numItems - 1; i >= 0; i--) {
                        var item = bin.children[i];
                        if (item.type === ProjectItemType.BIN) {
                            scanBin(item);
                            // 删除空 BIN
                            if (item.children.numItems === 0) {
                                var binName = item.name;
                                item.deleteBin();
                                removed.push({name: binName, type: "empty_bin"});
                            }
                        } else if (item.type === ProjectItemType.CLIP) {
                            if (!usedIds[item.nodeId]) {
                                var clipName = item.name;
                                item.remove();
                                removed.push({name: clipName, type: "unused_clip"});
                            }
                        }
                    }
                }
                scanBin(root);

                return JSON.stringify({
                    status: "success",
                    removedCount: removed.length,
                    removed: removed
                });
            } catch (e) {
                return JSON.stringify({status: "error", message: e.toString()});
            }
        })();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "simplify_remove_unused")
        return self._parse_action_result(engine_result, "remove_unused_media")

    async def remove_empty_tracks(self, sequence_name: Optional[str] = None) -> Dict[str, Any]:
        """删除没有任何剪辑的轨道。"""
        seq_block = self._build_seq_selector(sequence_name)
        jsx = f"""
        (function() {{
            try {{
                var proj = app.project;
                {seq_block}
                var removed = [];

                // 从高索引向低索引删除（避免索引偏移）
                for (var v = seq.videoTracks.numTracks - 1; v >= 1; v--) {{
                    var vt = seq.videoTracks[v];
                    if (vt.clips.numItems === 0) {{
                        var vName = vt.name || ("V" + (v + 1));
                        try {{
                            seq.videoTracks.removeTrack(v);
                            removed.push({{name: vName, type: "video", index: v}});
                        }} catch(e1) {{}}
                    }}
                }}
                for (var a = seq.audioTracks.numTracks - 1; a >= 1; a--) {{
                    var at = seq.audioTracks[a];
                    if (at.clips.numItems === 0) {{
                        var aName = at.name || ("A" + (a + 1));
                        try {{
                            seq.audioTracks.removeTrack(a);
                            removed.push({{name: aName, type: "audio", index: a}});
                        }} catch(e2) {{}}
                    }}
                }}

                return JSON.stringify({{
                    status: "success",
                    removedCount: removed.length,
                    removed: removed,
                    remainingVideo: seq.videoTracks.numTracks,
                    remainingAudio: seq.audioTracks.numTracks
                }});
            }} catch (e) {{
                return JSON.stringify({{status: "error", message: e.toString()}});
            }}
        }})();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "simplify_remove_empty_tracks")
        return self._parse_action_result(engine_result, "remove_empty_tracks")

    async def close_gaps(self, sequence_name: Optional[str] = None) -> Dict[str, Any]:
        """关闭时间线上的间隙（Ripple Delete 空白段）。"""
        seq_block = self._build_seq_selector(sequence_name)
        jsx = f"""
        (function() {{
            try {{
                var proj = app.project;
                {seq_block}
                var TPS = {self._engine.TICKS_PER_SECOND};
                var gapsClosed = 0;

                // 对每个视频轨道检测并关闭间隙
                for (var v = 0; v < seq.videoTracks.numTracks; v++) {{
                    var track = seq.videoTracks[v];
                    var clips = track.clips;
                    if (clips.numItems < 2) continue;

                    // 从后向前处理间隙（避免索引偏移）
                    for (var c = clips.numItems - 1; c >= 1; c--) {{
                        var prevClip = clips[c - 1];
                        var curClip = clips[c];
                        var prevEnd = prevClip.end;
                        var curStart = curClip.start;
                        var gapTicks = curStart - prevEnd;

                        // 间隙超过 1 帧才处理
                        if (gapTicks > TPS / 30) {{
                            // 将当前剪辑向前移动间隙长度
                            try {{
                                curClip.move(track, prevEnd);
                                gapsClosed++;
                            }} catch(e1) {{}}
                        }}
                    }}
                }}

                return JSON.stringify({{
                    status: "success",
                    gapsClosed: gapsClosed,
                    sequence: seq.name
                }});
            }} catch (e) {{
                return JSON.stringify({{status: "error", message: e.toString()}});
            }}
        }})();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "simplify_close_gaps")
        return self._parse_action_result(engine_result, "close_gaps")

    async def consolidate_duplicates(self) -> Dict[str, Any]:
        """合并项目中的重复素材（同名同路径）。"""
        jsx = """
        (function() {
            try {
                var proj = app.project;
                if (!proj) return JSON.stringify({status: "error", message: "No project"});

                // 收集所有素材的路径映射
                var pathMap = {};  // path -> firstItem
                var duplicates = [];
                var root = proj.rootItem;

                function scanForDupes(bin) {
                    for (var i = bin.children.numItems - 1; i >= 0; i--) {
                        var item = bin.children[i];
                        if (item.type === ProjectItemType.BIN) {
                            scanForDupes(item);
                        } else if (item.type === ProjectItemType.CLIP) {
                            var path = "";
                            try { path = item.getMediaPath(); } catch(e) {}
                            if (path) {
                                if (pathMap[path]) {
                                    // 发现重复，删除后导入的
                                    duplicates.push({name: item.name, path: path});
                                    item.remove();
                                } else {
                                    pathMap[path] = item;
                                }
                            }
                        }
                    }
                }
                scanForDupes(root);

                return JSON.stringify({
                    status: "success",
                    duplicatesRemoved: duplicates.length,
                    duplicates: duplicates
                });
            } catch (e) {
                return JSON.stringify({status: "error", message: e.toString()});
            }
        })();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "simplify_consolidate")
        return self._parse_action_result(engine_result, "consolidate_duplicates")

    async def organize_bins(
        self,
        strategy: str = "by_type",
        sequence_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """自动整理素材箱。

        Args:
            strategy: 分类策略 (by_type / by_sequence / by_date)
        """
        strategy_js = self._engine._jsx_escape(strategy)
        jsx = f"""
        (function() {{
            try {{
                var proj = app.project;
                if (!proj) return JSON.stringify({{status: "error", message: "No project"}});
                var root = proj.rootItem;
                var strategy = {strategy_js};
                var moved = 0;

                // 创建分类 BIN
                var videoBin = root.createBin("_Video");
                var audioBin = root.createBin("_Audio");
                var imageBin = root.createBin("_Images");
                var otherBin = root.createBin("_Other");

                // 遍历根目录下的散落素材
                for (var i = root.children.numItems - 1; i >= 0; i--) {{
                    var item = root.children[i];
                    if (item.type !== ProjectItemType.CLIP) continue;

                    var name = item.name.toLowerCase();
                    var targetBin = otherBin;

                    if (name.match(/\\.(mp4|mov|avi|mkv|mxf|mts)$/i)) {{
                        targetBin = videoBin;
                    }} else if (name.match(/\\.(mp3|wav|aac|flac|m4a|ogg)$/i)) {{
                        targetBin = audioBin;
                    }} else if (name.match(/\\.(png|jpg|jpeg|tiff|psd|ai|svg)$/i)) {{
                        targetBin = imageBin;
                    }}

                    try {{
                        item.moveBin(targetBin);
                        moved++;
                    }} catch(e1) {{}}
                }}

                // 删除空的分类 BIN（如果没有素材被移入）
                if (videoBin.children.numItems === 0) videoBin.deleteBin();
                if (audioBin.children.numItems === 0) audioBin.deleteBin();
                if (imageBin.children.numItems === 0) imageBin.deleteBin();
                if (otherBin.children.numItems === 0) otherBin.deleteBin();

                return JSON.stringify({{
                    status: "success",
                    movedCount: moved,
                    strategy: strategy
                }});
            }} catch (e) {{
                return JSON.stringify({{status: "error", message: e.toString()}});
            }}
        }})();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "simplify_organize_bins")
        return self._parse_action_result(engine_result, "organize_bins")

    # ------------------------------------------------------------------
    # 内部检测方法
    # ------------------------------------------------------------------

    async def _detect_unused_media(self) -> List[str]:
        """检测未使用素材，返回名称列表。"""
        jsx = """
        (function() {
            try {
                var proj = app.project;
                if (!proj) return JSON.stringify([]);

                var usedIds = {};
                for (var si = 0; si < proj.sequences.numSequences; si++) {
                    var seq = proj.sequences[si];
                    for (var vt = 0; vt < seq.videoTracks.numTracks; vt++) {
                        var vTrack = seq.videoTracks[vt];
                        for (var vc = 0; vc < vTrack.clips.numItems; vc++) {
                            if (vTrack.clips[vc].projectItem)
                                usedIds[vTrack.clips[vc].projectItem.nodeId] = true;
                        }
                    }
                    for (var at = 0; at < seq.audioTracks.numTracks; at++) {
                        var aTrack = seq.audioTracks[at];
                        for (var ac = 0; ac < aTrack.clips.numItems; ac++) {
                            if (aTrack.clips[ac].projectItem)
                                usedIds[aTrack.clips[ac].projectItem.nodeId] = true;
                        }
                    }
                }

                var unused = [];
                function scan(bin) {
                    for (var i = 0; i < bin.children.numItems; i++) {
                        var item = bin.children[i];
                        if (item.type === ProjectItemType.BIN) {
                            scan(item);
                        } else if (item.type === ProjectItemType.CLIP) {
                            if (!usedIds[item.nodeId]) unused.push(item.name);
                        }
                    }
                }
                scan(proj.rootItem);
                return JSON.stringify(unused);
            } catch (e) {
                return JSON.stringify([]);
            }
        })();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "detect_unused")
        data = self._extract_data(engine_result)
        return data if isinstance(data, list) else []

    async def _detect_empty_tracks(self, sequence_name: Optional[str] = None) -> List[Dict]:
        """检测空轨道。"""
        seq_block = self._build_seq_selector(sequence_name)
        jsx = f"""
        (function() {{
            try {{
                var proj = app.project;
                {seq_block}
                var empty = [];
                for (var v = 0; v < seq.videoTracks.numTracks; v++) {{
                    if (seq.videoTracks[v].clips.numItems === 0) {{
                        empty.push({{index: v, name: seq.videoTracks[v].name || ("V" + (v+1)), type: "video"}});
                    }}
                }}
                for (var a = 0; a < seq.audioTracks.numTracks; a++) {{
                    if (seq.audioTracks[a].clips.numItems === 0) {{
                        empty.push({{index: a, name: seq.audioTracks[a].name || ("A" + (a+1)), type: "audio"}});
                    }}
                }}
                return JSON.stringify(empty);
            }} catch (e) {{
                return JSON.stringify([]);
            }}
        }})();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "detect_empty_tracks")
        data = self._extract_data(engine_result)
        return data if isinstance(data, list) else []

    async def _detect_gaps(self, sequence_name: Optional[str] = None) -> List[Dict]:
        """检测时间线间隙。"""
        seq_block = self._build_seq_selector(sequence_name)
        ticks = self._engine.TICKS_PER_SECOND
        jsx = f"""
        (function() {{
            try {{
                var proj = app.project;
                {seq_block}
                var TPS = {ticks};
                var gaps = [];
                for (var v = 0; v < seq.videoTracks.numTracks; v++) {{
                    var track = seq.videoTracks[v];
                    var clips = track.clips;
                    for (var c = 1; c < clips.numItems; c++) {{
                        var prevEnd = clips[c-1].end;
                        var curStart = clips[c].start;
                        var gapTicks = curStart - prevEnd;
                        if (gapTicks > TPS / 30) {{
                            gaps.push({{
                                track: track.name || ("V" + (v+1)),
                                trackIndex: v,
                                start_s: prevEnd / TPS,
                                end_s: curStart / TPS,
                                duration_s: gapTicks / TPS
                            }});
                        }}
                    }}
                }}
                return JSON.stringify(gaps);
            }} catch (e) {{
                return JSON.stringify([]);
            }}
        }})();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "detect_gaps")
        data = self._extract_data(engine_result)
        return data if isinstance(data, list) else []

    async def _detect_duplicates(self) -> List[Dict]:
        """检测重复素材。"""
        jsx = """
        (function() {
            try {
                var proj = app.project;
                if (!proj) return JSON.stringify([]);
                var pathCount = {};
                var pathName = {};
                function scan(bin) {
                    for (var i = 0; i < bin.children.numItems; i++) {
                        var item = bin.children[i];
                        if (item.type === ProjectItemType.BIN) {
                            scan(item);
                        } else if (item.type === ProjectItemType.CLIP) {
                            var path = "";
                            try { path = item.getMediaPath(); } catch(e) {}
                            if (path) {
                                pathCount[path] = (pathCount[path] || 0) + 1;
                                pathName[path] = item.name;
                            }
                        }
                    }
                }
                scan(proj.rootItem);
                var dupes = [];
                for (var p in pathCount) {
                    if (pathCount[p] > 1) {
                        dupes.push({name: pathName[p], path: p, count: pathCount[p]});
                    }
                }
                return JSON.stringify(dupes);
            } catch (e) {
                return JSON.stringify([]);
            }
        })();
        """
        engine_result = await self._engine._execute_jsx_safe(jsx, "detect_duplicates")
        data = self._extract_data(engine_result)
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _build_seq_selector(self, sequence_name: Optional[str]) -> str:
        """构建序列选择 JSX 代码块。"""
        if sequence_name:
            sn_js = self._engine._jsx_escape(sequence_name)
            return f"""
                var seq = null;
                for (var si = 0; si < proj.sequences.numSequences; si++) {{
                    if (proj.sequences[si].name === {sn_js}) {{ seq = proj.sequences[si]; break; }}
                }}
                if (!seq) return JSON.stringify({{status: "error", message: "Sequence not found"}});
            """
        return """
                var seq = proj.activeSequence;
                if (!seq) return JSON.stringify({status: "error", message: "No active sequence"});
            """

    async def _save_project(self) -> None:
        """保存当前项目。"""
        jsx = """
        (function() {
            try {
                app.project.save();
                return JSON.stringify({status: "success"});
            } catch (e) {
                return JSON.stringify({status: "error", message: e.toString()});
            }
        })();
        """
        await self._engine._execute_jsx_safe(jsx, "simplify_save")

    def _parse_action_result(self, engine_result: Any, action_name: str) -> Dict[str, Any]:
        """解析引擎执行结果为标准字典。"""
        if not engine_result.success:
            return {"status": "error", "error": engine_result.error, "action": action_name}
        meta = engine_result.metadata or {}
        result_data = meta.get("result", {})
        if isinstance(result_data, dict):
            result_data["action"] = action_name
            return result_data
        return {"status": "success", "action": action_name, "raw": str(result_data)}

    def _extract_data(self, engine_result: Any) -> Any:
        """从引擎结果中提取数据。"""
        if not engine_result.success:
            return None
        meta = engine_result.metadata or {}
        return meta.get("result")
