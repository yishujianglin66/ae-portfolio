#!/usr/bin/env python3
"""
AE TS Compiler Client - TypeScript编译器Python客户端
=====================================================
通过子进程调用TS编译器CLI，将效果参数传递给编译器并获取生成的JSX代码。

当TS编译器不可用时，提供降级方案直接生成JSX代码（ES3兼容）。

用法:
    client = AETSCompilerClient()
    result = client.compile_effect("ADBE Gaussian Blur 2", {"Blurriness": 50})
    print(result["jsx_code"])
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认编译器目录
#
# 修正说明：此前写作 `dirname(__file__) / "compiler"`，解析结果为
# `integrations/compiler`，而 TypeScript 编译器实际位于**项目根**的
# `compiler/` 目录，导致 `build/cli.js` 永远找不到，
# JSX 编译链路整体不可用（报「编译器JS文件不存在」）。
# 正确做法是从本文件上溯一级到项目根再拼接。
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_COMPILER_DIR = os.path.join(_PROJECT_ROOT, "compiler")

# 子进程超时时间（秒）
COMPILER_TIMEOUT = 30


class AETSCompilerClient:
    """AE TypeScript编译器Python客户端"""

    def __init__(self, compiler_dir: str = None, use_ts_node: bool = False, enable_cache: bool = True):
        """
        初始化编译器客户端

        Args:
            compiler_dir: TypeScript编译器目录路径，默认为项目内compiler目录
            use_ts_node: True使用ts-node运行，False使用编译后的JS
            enable_cache: 启用编译结果缓存（基于输入内容hash，避免重复spawn子进程）
        """
        self.compiler_dir = compiler_dir or DEFAULT_COMPILER_DIR
        self.use_ts_node = use_ts_node

        # 编译后JS路径
        self._cli_js_path = os.path.join(self.compiler_dir, "build", "cli.js")
        # TS源码入口
        self._cli_ts_path = os.path.join(self.compiler_dir, "src", "cli.ts")

        # 编译结果缓存：相同输入直接返回，避免重复 spawn node 子进程
        self._result_cache = None
        if enable_cache:
            try:
                from performance.cache_manager import MemoryCache
                self._result_cache = MemoryCache(name="ts_compiler_results", maxsize=64)
            except ImportError:
                pass

    def _input_hash(self, input_data: dict) -> str:
        """计算编译输入的内容hash，用作缓存键。"""
        import hashlib
        # sort_keys 确保字典键顺序不影响 hash
        content = json.dumps(input_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]

    def compile_effect(
        self, match_name: str, settings: dict, context: dict = None
    ) -> dict:
        """
        编译单个效果参数

        Args:
            match_name: AE效果matchName，如 "ADBE Gaussian Blur 2"
            settings: 效果参数键值对，如 {"Blurriness": 50, "Repeat": 1}
            context: 可选上下文，包含compRef、layerRef等信息

        Returns:
            {"success": bool, "jsx_code": str, "matchName": str}
        """
        layer_ref = (context or {}).get("layerRef", "target_layer")
        layer_type = (context or {}).get("layerType", "solid")
        comp_ref = (context or {}).get("compRef", "main_comp")

        add_layer_op = {
            "op": "addLayer",
            "ref": layer_ref,
            "compRef": comp_ref,
            "layerType": layer_type,
            "name": (context or {}).get("layerName", "Target Layer"),
        }
        # solid类型必须提供color字段
        if layer_type == "solid":
            add_layer_op["color"] = (context or {}).get("color", [0, 0, 0])

        operations = [
            {
                "op": "createComp",
                "ref": comp_ref,
                "name": (context or {}).get("compName", "Effect Preview"),
                "width": (context or {}).get("width", 1920),
                "height": (context or {}).get("height", 1080),
                "frameRate": (context or {}).get("frameRate", 30),
                "duration": (context or {}).get("duration", 10),
            },
            add_layer_op,
            {
                "op": "addEffect",
                "layerRef": layer_ref,
                "matchName": match_name,
                "settings": settings or {},
            },
        ]

        input_data = {
            "metadata": {
                "source": "python_client_compile_effect",
                "description": "Single effect compilation: {}".format(match_name),
            },
            "operations": operations,
        }

        result = self._run_compiler(input_data)

        if result["success"]:
            return {
                "success": True,
                "jsx_code": result["jsx_code"],
                "matchName": match_name,
            }
        else:
            logger.warning(
                "TS编译器失败，使用降级方案: %s",
                result.get("error", "unknown"),
            )
            jsx = self._generate_standalone_jsx(
                effects=[{"matchName": match_name, "settings": settings}],
            )
            return {"success": True, "jsx_code": jsx, "matchName": match_name}

    def compile_batch(self, effects: list, context: dict = None) -> dict:
        """
        批量编译多个效果

        Args:
            effects: 效果列表，每项为 {"matchName": str, "settings": dict}
            context: 可选上下文

        Returns:
            {"success": bool, "results": list, "jsx_code": str}
        """
        layer_ref = (context or {}).get("layerRef", "target_layer")
        layer_type = (context or {}).get("layerType", "solid")
        comp_ref = (context or {}).get("compRef", "main_comp")

        add_layer_op = {
            "op": "addLayer",
            "ref": layer_ref,
            "compRef": comp_ref,
            "layerType": layer_type,
            "name": (context or {}).get("layerName", "Target Layer"),
        }
        if layer_type == "solid":
            add_layer_op["color"] = (context or {}).get("color", [0, 0, 0])

        operations = [
            {
                "op": "createComp",
                "ref": comp_ref,
                "name": (context or {}).get("compName", "Batch Effects Preview"),
                "width": (context or {}).get("width", 1920),
                "height": (context or {}).get("height", 1080),
                "frameRate": (context or {}).get("frameRate", 30),
                "duration": (context or {}).get("duration", 10),
            },
            add_layer_op,
        ]

        for i, fx in enumerate(effects):
            fx_op = {
                "op": "addEffect",
                "ref": "batch_fx_{:03d}".format(i),
                "layerRef": layer_ref,
                "matchName": fx["matchName"],
            }
            if fx.get("settings"):
                fx_op["settings"] = fx["settings"]
            operations.append(fx_op)

        input_data = {
            "metadata": {
                "source": "python_client_compile_batch",
                "description": "Batch effect compilation: {} effects".format(
                    len(effects)
                ),
            },
            "operations": operations,
        }

        result = self._run_compiler(input_data)

        if result["success"]:
            results_list = [
                {"matchName": fx["matchName"], "compiled": True} for fx in effects
            ]
            return {
                "success": True,
                "results": results_list,
                "jsx_code": result["jsx_code"],
            }
        else:
            logger.warning(
                "TS编译器批量编译失败，使用降级方案: %s",
                result.get("error", "unknown"),
            )
            jsx = self._generate_standalone_jsx(effects=effects)
            results_list = [
                {"matchName": fx["matchName"], "compiled": True} for fx in effects
            ]
            return {"success": True, "results": results_list, "jsx_code": jsx}

    def compile_from_planning(self, planning_result: dict) -> dict:
        """
        从规划结果编译完整JSX脚本

        Args:
            planning_result: AEAgentPipeline的PlanningResult的dict版本
                包含 composition, layers, effects, keyframes, transitions, timeline 等字段

        Returns:
            {"success": bool, "jsx_code": str, "command_count": int}
        """
        operations = []
        comp_ref = "main_comp"

        # 1. 创建合成
        comp_info = planning_result.get("composition") or {}
        if comp_info:
            operations.append(
                {
                    "op": "createComp",
                    "ref": comp_ref,
                    "name": comp_info.get("name", "Main Comp"),
                    "width": comp_info.get("width", 1920),
                    "height": comp_info.get("height", 1080),
                    "frameRate": comp_info.get("frameRate", 30),
                    "duration": comp_info.get("duration", 10),
                    "bgColor": comp_info.get("bgColor", [0, 0, 0]),
                }
            )

        # 2. 添加图层
        layers = planning_result.get("layers") or []
        layer_ref_map = {}
        for i, layer in enumerate(layers):
            layer_ref = layer.get("ref", "layer_{:03d}".format(i))
            layer_ref_map[i] = layer_ref

            op = {
                "op": "addLayer",
                "ref": layer_ref,
                "compRef": comp_ref,
                "layerType": layer.get("layerType", "solid"),
                "name": layer.get("name", "Layer {}".format(i + 1)),
            }

            # Text layer fields
            if layer.get("text") is not None:
                op["text"] = layer["text"]
            if layer.get("fontSize") is not None:
                op["fontSize"] = layer["fontSize"]
            if layer.get("font") is not None:
                op["font"] = layer["font"]
            if layer.get("fillColor") is not None:
                op["fillColor"] = layer["fillColor"]

            # Solid layer fields
            if layer.get("color") is not None:
                op["color"] = layer["color"]

            # Footage
            if layer.get("filePath") is not None:
                op["filePath"] = layer["filePath"]

            # Transform
            if layer.get("position") is not None:
                op["position"] = layer["position"]
            if layer.get("scale") is not None:
                op["scale"] = layer["scale"]
            if layer.get("rotation") is not None:
                op["rotation"] = layer["rotation"]
            if layer.get("opacity") is not None:
                op["opacity"] = layer["opacity"]
            if layer.get("anchorPoint") is not None:
                op["anchorPoint"] = layer["anchorPoint"]

            # Time
            if layer.get("startTime") is not None:
                op["startTime"] = layer["startTime"]
            if layer.get("inPoint") is not None:
                op["inPoint"] = layer["inPoint"]
            if layer.get("outPoint") is not None:
                op["outPoint"] = layer["outPoint"]

            # 3D
            if layer.get("is3D") is not None:
                op["is3D"] = layer["is3D"]

            operations.append(op)

        # 3. 添加效果
        effects = planning_result.get("effects") or []
        for i, fx in enumerate(effects):
            layer_idx = fx.get("layerIndex", 0)
            layer_ref = layer_ref_map.get(layer_idx, fx.get("layerRef", "target_layer"))

            op = {
                "op": "addEffect",
                "ref": fx.get("ref", "fx_{:03d}".format(i)),
                "layerRef": layer_ref,
                "matchName": fx["matchName"],
            }
            if fx.get("name"):
                op["name"] = fx["name"]
            if fx.get("settings"):
                op["settings"] = fx["settings"]
            operations.append(op)

        # 4. 添加关键帧
        keyframes_list = planning_result.get("keyframes") or []
        for i, kf in enumerate(keyframes_list):
            layer_idx = kf.get("layerIndex", 0)
            layer_ref = layer_ref_map.get(layer_idx, kf.get("layerRef", "target_layer"))

            op = {
                "op": "setKeyframe",
                "layerRef": layer_ref,
                "propertyPath": kf["propertyPath"],
                "keyframes": kf["keyframes"],
            }
            operations.append(op)

        # 5. 添加转场（映射为混合模式/表达式）
        transitions = planning_result.get("transitions") or []
        for i, tr in enumerate(transitions):
            if tr.get("blendMode"):
                layer_idx = tr.get("layerIndex", 0)
                layer_ref = layer_ref_map.get(layer_idx, tr.get("layerRef", "target_layer"))
                operations.append(
                    {
                        "op": "setBlendMode",
                        "layerRef": layer_ref,
                        "blendMode": tr["blendMode"],
                    }
                )

        # 6. 轨道遮罩
        timeline = planning_result.get("timeline") or []
        for i, tl in enumerate(timeline):
            if tl.get("trackMatte"):
                layer_idx = tl.get("layerIndex", 0)
                layer_ref = layer_ref_map.get(layer_idx, tl.get("layerRef", "target_layer"))
                matte_ref = layer_ref_map.get(tl.get("matteIndex", 0), tl.get("matteRef", "matte_layer"))
                operations.append(
                    {
                        "op": "setTrackMatte",
                        "layerRef": layer_ref,
                        "matteRef": matte_ref,
                        "matteType": tl["trackMatte"].get("type", "alpha"),
                    }
                )
            if tl.get("parent"):
                layer_idx = tl.get("layerIndex", 0)
                layer_ref = layer_ref_map.get(layer_idx, tl.get("layerRef", "target_layer"))
                parent_ref = layer_ref_map.get(tl.get("parentIndex", 0), tl.get("parentRef", "parent_layer"))
                operations.append(
                    {
                        "op": "setParent",
                        "layerRef": layer_ref,
                        "parentRef": parent_ref,
                    }
                )

        input_data = {
            "metadata": {
                "source": "python_client_compile_from_planning",
                "description": "Full planning compilation",
            },
            "operations": operations,
        }

        result = self._run_compiler(input_data)

        if result["success"]:
            return {
                "success": True,
                "jsx_code": result["jsx_code"],
                "command_count": len(operations),
            }
        else:
            logger.warning(
                "TS编译器规划编译失败，使用降级方案: %s",
                result.get("error", "unknown"),
            )
            jsx = self._generate_standalone_jsx(
                effects=effects,
                keyframes=keyframes_list,
            )
            return {
                "success": True,
                "jsx_code": jsx,
                "command_count": len(operations),
            }

    def _run_compiler(self, input_data: dict) -> dict:
        """
        内部方法：运行编译器子进程

        1. 检查结果缓存（基于输入内容hash）
        2. 将input_data写入临时JSON文件
        3. 运行node/ts-node子进程
        4. 读取输出文件
        5. 成功则写入缓存

        Args:
            input_data: 编译器输入数据（CompilerInput格式的dict）

        Returns:
            {"success": bool, "jsx_code": str, "error": str (on failure)}
        """
        # 缓存命中检查：避免重复 spawn node 子进程（最大的执行层开销）
        cache_key = None
        if self._result_cache is not None:
            cache_key = self._input_hash(input_data)
            cached = self._result_cache.get(cache_key)
            if cached is not None:
                return cached

        input_file = None
        output_file = None

        try:
            # 1. 写入临时JSON文件
            temp_dir = tempfile.gettempdir()
            ts = int(time.time() * 1000)
            input_file = os.path.join(temp_dir, "ae_compiler_input_{}.json".format(ts))
            output_file = os.path.join(
                temp_dir, "ae_compiler_output_{}.jsx".format(ts)
            )

            with open(input_file, "w", encoding="utf-8") as f:
                json.dump(input_data, f, ensure_ascii=False, indent=2)

            # 2. 构建命令
            if self.use_ts_node:
                cmd = [
                    "npx",
                    "ts-node",
                    os.path.join("src", "cli.ts"),
                    "compile",
                    input_file,
                    "-o",
                    output_file,
                ]
                cwd = self.compiler_dir
            else:
                if not os.path.isfile(self._cli_js_path):
                    return {
                        "success": False,
                        "error": "编译后JS文件不存在: {}".format(self._cli_js_path),
                    }
                cmd = [
                    "node",
                    self._cli_js_path,
                    "compile",
                    input_file,
                    "-o",
                    output_file,
                ]
                cwd = self.compiler_dir

            # 3. 运行子进程
            logger.debug("运行编译器: %s (cwd=%s)", " ".join(cmd), cwd)
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=COMPILER_TIMEOUT,
                encoding="utf-8",
            )

            if proc.returncode != 0:
                error_msg = proc.stderr.strip() or proc.stdout.strip()
                return {
                    "success": False,
                    "error": "编译器返回非零退出码({}): {}".format(
                        proc.returncode, error_msg
                    ),
                }

            # 4. 读取输出文件
            if not os.path.isfile(output_file):
                # 尝试从stdout获取（当未指定-o时可能输出到stdout）
                if proc.stdout.strip():
                    result = {"success": True, "jsx_code": proc.stdout.strip()}
                    if self._result_cache is not None and cache_key:
                        self._result_cache.set(cache_key, result)
                    return result
                return {
                    "success": False,
                    "error": "输出文件未生成: {}".format(output_file),
                }

            with open(output_file, "r", encoding="utf-8") as f:
                jsx_code = f.read()

            result = {"success": True, "jsx_code": jsx_code}
            # 成功结果写入缓存
            if self._result_cache is not None and cache_key:
                self._result_cache.set(cache_key, result)
            return result

        except FileNotFoundError as e:
            return {
                "success": False,
                "error": "编译器可执行文件未找到: {}".format(str(e)),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "编译器执行超时（{}秒）".format(COMPILER_TIMEOUT),
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": "输入JSON序列化失败: {}".format(str(e)),
            }
        except Exception as e:
            return {
                "success": False,
                "error": "编译器执行异常: {}".format(str(e)),
            }
        finally:
            # 清理临时文件
            for fpath in (input_file, output_file):
                if fpath and os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass

    def _generate_standalone_jsx(
        self, effects: list, keyframes: list = None
    ) -> str:
        """
        生成独立可执行的JSX脚本（降级方案）

        不依赖TS编译器，直接从参数生成JSX代码。
        使用AE ExtendScript语法（ES3兼容），所有AE API调用
        使用property()方法访问效果属性。

        Args:
            effects: 效果列表，每项为 {"matchName": str, "settings": dict}
            keyframes: 可选关键帧列表

        Returns:
            完整的ExtendScript JSX代码字符串
        """
        lines = []
        lines.append("(function() {")
        lines.append('    // ============================================')
        lines.append('    // AE自动化引擎 - 独立生成代码（降级模式）')
        lines.append('    // 生成时间: {}'.format(_iso_now()))
        lines.append('    // ============================================')
        lines.append("")
        lines.append("    var _results = [];")
        lines.append("    var _errors = [];")
        lines.append("")
        lines.append("    function _logResult(op, data) {")
        lines.append("        _results.push({ op: op, data: data, timestamp: new Date().getTime() });")
        lines.append("    }")
        lines.append("")
        lines.append("    function _logError(op, err) {")
        lines.append("        _errors.push({ op: op, error: err.toString(), timestamp: new Date().getTime() });")
        lines.append("    }")
        lines.append("")
        lines.append("    function resolveProperty(layer, path) {")
        lines.append("        if (!layer) return null;")
        lines.append('        var parts = path.split("/").join(".").split(".");')
        lines.append("        var current = layer;")
        lines.append("        for (var i = 0; i < parts.length; i++) {")
        lines.append("            if (!current) break;")
        lines.append("            var part = parts[i].trim();")
        lines.append("            try {")
        lines.append("                if (current.property) {")
        lines.append("                    var prop = null;")
        lines.append('                    try { prop = current.property(part); } catch (e) { prop = null; }')
        lines.append("                    if (!prop) {")
        lines.append("                        for (var j = 1; j <= (current.numProperties || 0); j++) {")
        lines.append("                            var p = current.property(j);")
        lines.append('                            if (p && (p.name === part || p.matchName === part)) {')
        lines.append("                                prop = p;")
        lines.append("                                break;")
        lines.append("                            }")
        lines.append("                        }")
        lines.append("                    }")
        lines.append("                    current = prop;")
        lines.append("                } else {")
        lines.append("                    return null;")
        lines.append("                }")
        lines.append("            } catch (e) {")
        lines.append("                return null;")
        lines.append("            }")
        lines.append("        }")
        lines.append("        return current;")
        lines.append("    }")
        lines.append("")
        lines.append('    app.beginUndoGroup("AE Auto Engine - Standalone Script");')
        lines.append("")
        lines.append("    try {")

        # 创建合成
        lines.append("")
        lines.append('        // 创建默认合成')
        lines.append('        var comp_001 = app.project.items.addComp("Auto Comp", 1920, 1080, 1, 10, 30);')
        lines.append("        if (comp_001) {")
        lines.append("            comp_001.bgColor = [0, 0, 0];")
        lines.append('            _logResult("createComp", { name: "Auto Comp", "var": "comp_001" });')
        lines.append("        }")
        lines.append("")

        # 添加默认图层
        lines.append("        // 创建默认图层")
        lines.append('        var layer_001 = comp_001.layers.addSolid([0, 0, 0], "Target Layer", 1920, 1080, 1.0, comp_001.duration);')
        lines.append("        if (layer_001) {")
        lines.append('            _logResult("addLayer", { type: "solid", "var": "layer_001" });')
        lines.append("        }")
        lines.append("")

        # 添加效果
        # 注意：AE API使用 property("ADBE Effect Parade").addProperty() 而非 Effects.add()
        # 这在中文界面和英文界面下都能稳定工作，避免大小写兼容性问题
        for i, fx in enumerate(effects):
            match_name = fx["matchName"]
            settings = fx.get("settings") or {}
            fx_var = "fx_{:03d}".format(i + 1)

            lines.append("        // 添加效果: " + match_name)
            lines.append('        var _effectsParade = null;')
            lines.append('        try { _effectsParade = layer_001.property("ADBE Effect Parade"); } catch (e) { _effectsParade = null; }')
            lines.append("        var " + fx_var + " = null;")
            lines.append("        if (_effectsParade && _effectsParade.addProperty) {")
            lines.append('            try { ' + fx_var + ' = _effectsParade.addProperty(' + _json_str(match_name) + '); } catch (e) { _logError("addEffect", e); }')
            lines.append("        } else if (layer_001.effects && layer_001.effects.add) {")
            lines.append('            try { ' + fx_var + ' = layer_001.effects.add(' + _json_str(match_name) + '); } catch (e) { _logError("addEffect", e); }')
            lines.append("        }")
            lines.append("        if (" + fx_var + ") {")

            for prop_name, value in settings.items():
                value_code = _format_jsx_value(value)
                lines.append("            var _prop = null;")
                lines.append('            try { _prop = ' + fx_var + '.property(' + _json_str(prop_name) + '); } catch (e) { _prop = null; }')
                lines.append("            if (_prop) {")
                lines.append('                try { _prop.setValue(' + value_code + '); } catch (e) { _logError("setEffectParam", e); }')
                lines.append("            }")

            lines.append('            _logResult("addEffect", { matchName: ' + _json_str(match_name) + ', "var": "' + fx_var + '" });')
            lines.append("        }")
            lines.append("")

        # 添加关键帧
        if keyframes:
            for i, kf in enumerate(keyframes):
                prop_path = kf.get("propertyPath", "")
                kf_list = kf.get("keyframes", [])

                lines.append("        // 设置关键帧: {}".format(prop_path))
                lines.append(
                    "        var _prop = resolveProperty(layer_001, {});".format(
                        _json_str(prop_path)
                    )
                )
                lines.append("        if (_prop) {")

                for j, kf_item in enumerate(kf_list):
                    kf_time = kf_item.get("time", 0)
                    kf_value = kf_item.get("value")
                    easing = kf_item.get("easing")

                    lines.append("            // keyframe {} at t={}s".format(j + 1, kf_time))
                    lines.append("            _prop.setValueAtTime({}, {});".format(
                        kf_time, _format_jsx_value(kf_value)
                    ))

                    if easing:
                        easing_type = easing.get("type", "linear")
                        interp = _map_easing_type(easing_type)
                        lines.append("            var _kIdx = _prop.nearestKeyIndex({});".format(kf_time))
                        lines.append("            _prop.setInterpolationTypeAtKey(_kIdx, {});".format(interp))

                        if easing_type not in ("linear", "hold"):
                            in_speed = easing.get("inSpeed", 0)
                            in_influence = easing.get("inInfluence", 33)
                            out_speed = easing.get("outSpeed", 0)
                            out_influence = easing.get("outInfluence", 33)
                            lines.append("            var _inEase = new KeyframeEase({}, {});".format(
                                in_speed, in_influence
                            ))
                            lines.append("            var _outEase = new KeyframeEase({}, {});".format(
                                out_speed, out_influence
                            ))
                            lines.append("            _prop.setTemporalEaseAtKey(_kIdx, [_inEase], [_outEase]);")

                lines.append(
                    '            _logResult("setKeyframe", {{ path: {}, count: {} }});'.format(
                        _json_str(prop_path), len(kf_list)
                    )
                )
                lines.append("        }")
                lines.append("")

        # 尾部
        lines.append("    } catch (e) {")
        lines.append('        _logError("top_level", e);')
        lines.append("    } finally {")
        lines.append("        app.endUndoGroup();")
        lines.append("    }")
        lines.append("")
        lines.append("    var _output = {")
        lines.append('        status: _errors.length === 0 ? "success" : "partial",')
        lines.append("        results: _results,")
        lines.append("        errors: _errors,")
        lines.append("        timestamp: new Date().toISOString()")
        lines.append("    };")
        lines.append("")
        lines.append("    $.write(JSON.stringify(_output, null, 2));")
        lines.append("})();")

        return "\n".join(lines)

    def health_check(self) -> bool:
        """
        检查编译器是否可用

        Returns:
            True如果编译器可正常运行，False否则
        """
        if self.use_ts_node:
            if not os.path.isdir(self.compiler_dir):
                return False
            ts_entry = os.path.join(self.compiler_dir, "src", "cli.ts")
            if not os.path.isfile(ts_entry):
                return False
            # 尝试运行 --version
            try:
                proc = subprocess.run(
                    ["npx", "ts-node", ts_entry, "--version"],
                    cwd=self.compiler_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return proc.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return False
        else:
            if not os.path.isfile(self._cli_js_path):
                return False
            try:
                proc = subprocess.run(
                    ["node", self._cli_js_path, "--version"],
                    cwd=self.compiler_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return proc.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return False


# ============ 辅助函数 ============


def _iso_now() -> str:
    """返回ISO格式当前时间字符串（兼容Python 3.6+）"""
    try:
        from datetime import datetime as _dt

        return _dt.now().isoformat()
    except Exception:
        return ""


def _json_str(s: str) -> str:
    """将字符串转换为JSON安全的双引号字符串"""
    return json.dumps(s, ensure_ascii=False)


def _format_jsx_value(value) -> str:
    """
    格式化值为JSX兼容的表达式

    Args:
        value: Python值（number, string, bool, list, None）

    Returns:
        ExtendScript兼容的值表达式字符串
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        # 避免Python float的无限精度
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return _json_str(value)
    if isinstance(value, (list, tuple)):
        items = ", ".join(_format_jsx_value(v) for v in value)
        return "[{}]".format(items)
    return _json_str(str(value))


def _map_easing_type(easing_type: str) -> str:
    """映射缓动类型到ExtendScript常量"""
    mapping = {
        "linear": "KeyframeInterpolationType.LINEAR",
        "bezier": "KeyframeInterpolationType.BEZIER",
        "hold": "KeyframeInterpolationType.HOLD",
        "ease_in": "KeyframeInterpolationType.BEZIER",
        "ease_out": "KeyframeInterpolationType.BEZIER",
        "ease_in_out": "KeyframeInterpolationType.BEZIER",
    }
    return mapping.get(easing_type, "KeyframeInterpolationType.BEZIER")
