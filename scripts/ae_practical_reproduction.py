#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==================================================================
 AE 工程实战预测与完整重现 - 编排主控
==================================================================

功能:
  Phase 1 - 插件检测: 自动探测 45+ 插件/效果可用性
  Phase 2 - 工程复刻: 自动重现已分析的 8 大 AE 模块结构
  Phase 3 - 报告生成: 结构化 JSON/Markdown/HTML 测试报告
  Phase 4 - 安装预览: 缺失插件安装引导提示

依赖:
  - AE 必须已启动且加载 Bridge 面板 (.ae-mcp-bridge/2_mcp_bridge_loader.jsx)
  - Python 3.10+
  - 项目内 bridges/ 模块可用

使用:
  python scripts/ae_practical_reproduction.py
  python scripts/ae_practical_reproduction.py --quick          # 快速模式
  python scripts/ae_practical_reproduction.py --plugins-only   # 仅插件检测
  python scripts/ae_practical_reproduction.py --output report  # 指定输出目录
==================================================================
"""

import json
import os
import sys
import time
import uuid
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# ============================================================
# 路径配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_DIR = PROJECT_ROOT / ".ae-mcp-bridge"
COMMAND_FILE = BRIDGE_DIR / "ae_command.json"
RESULT_FILE = BRIDGE_DIR / "ae_result.json"
SCRIPTS_DIR = PROJECT_ROOT / "ae_additive_scripts"
OUTPUT_DIR = PROJECT_ROOT / "test_outputs"

REPORT_DIR = OUTPUT_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Bridge 通信层
# ============================================================
class AEBridgeClient:
    """AE MCP 桥接客户端 - 通过 JSON 文件轮询与 AE 通信"""

    def __init__(self, bridge_dir: Path = None, timeout: int = 120):
        self.bridge_dir = bridge_dir or BRIDGE_DIR
        self.command_file = self.bridge_dir / "ae_command.json"
        self.result_file = self.bridge_dir / "ae_result.json"
        self.timeout = timeout
        self.bridge_dir.mkdir(parents=True, exist_ok=True)

    def ping(self) -> Tuple[bool, str]:
        """检测 AE Bridge 是否在线"""
        try:
            return self.send_command("ping", {}, timeout=10)
        except Exception as e:
            return False, f"Ping failed: {e}"

    def send_command(self, command: str, args: Dict = None,
                     timeout: int = None) -> Tuple[bool, Any]:
        """发送命令到 AE Bridge 并等待结果"""
        if args is None:
            args = {}
        if timeout is None:
            timeout = self.timeout

        cmd_id = str(uuid.uuid4())[:8]

        payload = {
            "command": command,
            "args": args,
            "status": "pending",
            "timestamp": time.time(),
            "cmdId": cmd_id
        }

        # 清理旧的命令文件
        self._clean_stale_files()

        # 写入命令
        try:
            with open(self.command_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            return False, f"Write command failed: {e}"

        # 轮询结果
        start = time.time()
        last_progress_log = start
        while time.time() - start < timeout:
            try:
                if not self.result_file.exists():
                    time.sleep(0.5)
                    # 每 10 秒输出一次进度
                    if time.time() - last_progress_log > 10:
                        elapsed = int(time.time() - start)
                        print(f"  ⏳ 等待 AE 响应... ({elapsed}s/{timeout}s)")
                        last_progress_log = time.time()
                    continue

                with open(self.result_file, "r", encoding="utf-8") as f:
                    result = json.load(f)

                status = result.get("status", "")
                if status == "success":
                    return True, result
                elif status == "error":
                    return False, result
                else:
                    time.sleep(0.3)
                    continue

            except (json.JSONDecodeError, OSError) as e:
                time.sleep(0.3)
                continue

        return False, f"Timeout after {timeout}s (command: {command}, id: {cmd_id})"

    def execute_atom_script(self, script_content: str, timeout: int = None) -> Tuple[bool, Any]:
        """通过 executeAtomScript 命令在 AE 中执行 ExtendScript"""
        if timeout is None:
            timeout = self.timeout
        return self.send_command("executeAtomScript", {
            "scriptContent": script_content,
            "timeoutMs": timeout * 1000
        }, timeout=timeout)

    def _clean_stale_files(self):
        """清理残留命令/结果文件"""
        try:
            for f in [self.command_file, self.result_file]:
                if f.exists():
                    # 检查文件是否过旧（> 5 分钟）
                    age = time.time() - f.stat().st_mtime
                    if age > 300:
                        f.unlink(missing_ok=True)
        except Exception:
            pass

    def get_project_info(self) -> Tuple[bool, Any]:
        """获取 AE 项目信息"""
        return self.send_command("getProjectInfo", {}, timeout=15)


# ============================================================
# Phase 1: 插件检测
# ============================================================
class PluginDetector:
    """AE 插件/效果依赖自动检测器"""

    PLUGIN_MANIFEST = {
        "Saber (Video Copilot)": {
            "category": "光效/能量",
            "matchName": "VC SaberFX",
            "vendor": "Video Copilot",
            "url": "https://www.videocopilot.net/",
            "price": "免费",
            "essential_for": ["光剑效果", "能量光束", "霓虹描边"]
        },
        "Optical Flares (Video Copilot)": {
            "category": "光效/镜头",
            "matchName": "VC Optical Flares",
            "vendor": "Video Copilot",
            "url": "https://www.videocopilot.net/products/opticalflares/",
            "price": "$124.95",
            "essential_for": ["专业镜头光斑", "电影级光效"]
        },
        "Twixtor (RE:Vision FX)": {
            "category": "时间/慢动作",
            "matchName": "REVisionFX Twixtor",
            "vendor": "RE:Vision FX",
            "url": "https://revisionfx.com/products/twixtor/",
            "price": "$595",
            "essential_for": ["超级慢动作", "时间重映射", "帧插值"]
        },
        "Magic Bullet Looks (Red Giant)": {
            "category": "调色/电影",
            "matchName": "Magic Bullet Looks",
            "vendor": "Maxon / Red Giant",
            "url": "https://www.maxon.net/red-giant/magic-bullet-suite",
            "price": "$199/年",
            "essential_for": ["电影级调色", "Looks 预设"]
        },
        "Trapcode Particular (Red Giant)": {
            "category": "粒子/3D",
            "matchName": "TC Particular",
            "vendor": "Maxon / Red Giant",
            "url": "https://www.maxon.net/red-giant/trapcode-suite",
            "price": "$399/年",
            "essential_for": ["专业3D粒子", "烟雾/火焰/魔法"]
        },
        "Trapcode Form (Red Giant)": {
            "category": "粒子/3D网格",
            "matchName": "TC Form",
            "vendor": "Maxon / Red Giant",
            "url": "https://www.maxon.net/red-giant/trapcode-suite",
            "price": "$399/年",
            "essential_for": ["3D粒子网格", "地形生成", "音频可视化"]
        },
        "BCC Lens Flare (Boris FX)": {
            "category": "光效/镜头",
            "matchName": "BCC Lens Flare",
            "vendor": "Boris FX",
            "url": "https://borisfx.com/products/continuum/",
            "price": "$695/年",
            "essential_for": ["BCC级镜头光斑", "广播级光效"]
        },
        "Sapphire LensFlare (Boris FX)": {
            "category": "光效/镜头",
            "matchName": "S_LensFlare",
            "vendor": "Boris FX",
            "url": "https://borisfx.com/products/sapphire/",
            "price": "$1695/年",
            "essential_for": ["好莱坞级光晕", "高品质光学"]
        },
        "Element 3D (Video Copilot)": {
            "category": "3D/模型",
            "matchName": "Element",
            "vendor": "Video Copilot",
            "url": "https://www.videocopilot.net/products/element2/",
            "price": "$199.95",
            "essential_for": ["3D对象渲染", "模型导入", "PBR材质"]
        },
        "Deep Glow (Plugin Everything)": {
            "category": "发光/风格",
            "matchName": "Deep Glow",
            "vendor": "Plugin Everything",
            "url": "https://aescripts.com/deep-glow/",
            "price": "$39.99",
            "essential_for": ["物理精确发光", "高级发光控制"]
        },
        "Universe VHS (Red Giant)": {
            "category": "风格/复古",
            "matchName": "Universe VHS",
            "vendor": "Maxon / Red Giant",
            "url": "https://www.maxon.net/red-giant/universe",
            "price": "$199/年",
            "essential_for": ["VHS效果", "复古录像带", "故障风格"]
        },
    }

    def __init__(self, bridge: AEBridgeClient):
        self.bridge = bridge
        self.results: Dict[str, Any] = {}

    def load_detection_script(self) -> str:
        """加载插件检测 JSX 脚本"""
        script_path = SCRIPTS_DIR / "detect_plugins.jsx"
        if not script_path.exists():
            raise FileNotFoundError(f"检测脚本不存在: {script_path}")
        return script_path.read_text(encoding="utf-8")

    def run_detection(self) -> Dict[str, Any]:
        """执行完整的插件检测流程"""
        print("\n" + "=" * 60)
        print("  🔍 Phase 1: 插件/效果依赖检测")
        print("=" * 60)

        jsx_code = self.load_detection_script()
        print(f"  📜 检测脚本: detect_plugins.jsx ({len(jsx_code)} 字符)")
        print(f"  ⏱️  超时设置: {self.bridge.timeout}s")

        success, result = self.bridge.execute_atom_script(jsx_code, timeout=180)

        if not success:
            print(f"  ❌ 检测失败: {result}")
            self.results = {"error": str(result), "success": False}
            return self.results

        # 解析 ExtendScript JSON 回传结果
        try:
            if isinstance(result, dict):
                additive = result.get("result", "")
            else:
                additive = str(result)

            # 尝试解析 JSON（可能嵌套在字符串中）
            self.results = self._parse_es_result(additive)
        except Exception as e:
            self.results = {"error": f"Parse error: {e}", "raw": str(result)[:500]}
            return self.results

        self._print_summary()
        return self.results

    def _parse_es_result(self, raw: str) -> Dict:
        """解析 ExtendScript 回传的 JSON 字符串"""
        # 尝试直接解析
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试从字符串中提取 JSON
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass

        return {"raw": raw[:1000], "parse_error": True}

    def _print_summary(self):
        """打印检测结果摘要"""
        summary = self.results.get("summary", {})
        total = summary.get("total", 0)
        available = summary.get("available", 0)
        unavailable = summary.get("unavailable", 0)

        print(f"\n  📊 检测结果: {available}/{total} 可用, {unavailable}/{total} 不可用")
        print(f"  📦 AE 版本: {self.results.get('aeVersion', 'unknown')}")

        # 列出缺失的插件
        detected = self.results.get("detected", {})
        missing = []
        for name, info in detected.items():
            if isinstance(info, dict) and not info.get("available", False):
                missing.append(name)

        if missing:
            print(f"\n  🔴 缺失插件 ({len(missing)} 个):")
            for m in missing:
                info = detected.get(m, {})
                cat = info.get("category", "?")
                desc = info.get("desc", "")
                print(f"     • {m} [{cat}] - {desc}")

    def get_missing_with_hints(self) -> List[Dict]:
        """获取缺失插件列表（含安装提示）"""
        detected = self.results.get("detected", {})
        missing = []
        for name, info in detected.items():
            if isinstance(info, dict) and not info.get("available", False):
                manifest = self.PLUGIN_MANIFEST.get(name, {})
                missing.append({
                    "name": name,
                    "category": info.get("category", "unknown"),
                    "matchName": info.get("matchName", ""),
                    "error": info.get("error", ""),
                    "vendor": manifest.get("vendor", ""),
                    "url": manifest.get("url", ""),
                    "price": manifest.get("price", "未知"),
                    "essential_for": manifest.get("essential_for", [])
                })
        return missing


# ============================================================
# Phase 2: 工程结构复刻
# ============================================================
class ProjectReplicator:
    """AE 工程结构自动复刻器"""

    MODULE_NAMES = {
        "M1_Composition": "合成管理",
        "M2_Layers": "图层系统",
        "M3_Effects": "内置效果系统",
        "M4_TextAnimation": "文字动画系统",
        "M5_3DSystem": "3D 系统",
        "M6_Expressions": "表达式系统",
        "M7_Tracking": "跟踪系统",
        "M8_RenderQueue": "渲染队列",
    }

    def __init__(self, bridge: AEBridgeClient):
        self.bridge = bridge
        self.results: Dict[str, Any] = {}

    def load_replication_script(self) -> str:
        """加载工程复刻 JSX 脚本"""
        script_path = SCRIPTS_DIR / "replicate_project.jsx"
        if not script_path.exists():
            raise FileNotFoundError(f"复刻脚本不存在: {script_path}")
        return script_path.read_text(encoding="utf-8")

    def run_replication(self) -> Dict[str, Any]:
        """执行完整工程复刻"""
        print("\n" + "=" * 60)
        print("  🏗️  Phase 2: AE 工程结构复刻")
        print("=" * 60)

        jsx_code = self.load_replication_script()
        print(f"  📜 复刻脚本: replicate_project.jsx ({len(jsx_code)} 字符)")
        print(f"  🎯 覆盖模块: {len(self.MODULE_NAMES)} 个")

        success, result = self.bridge.execute_atom_script(jsx_code, timeout=300)

        if not success:
            print(f"  ❌ 复刻失败: {result}")
            self.results = {"error": str(result), "success": False}
            return self.results

        # 解析结果
        try:
            if isinstance(result, dict):
                additive = result.get("result", "")
            else:
                additive = str(result)
            self.results = self._parse_es_result(additive)
        except Exception as e:
            self.results = {"error": f"Parse error: {e}", "raw": str(result)[:500]}
            return self.results

        self._print_summary()
        return self.results

    def _parse_es_result(self, raw: str) -> Dict:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass
        return {"raw": raw[:1000], "parse_error": True}

    def _print_summary(self):
        summary = self.results.get("summary", {})
        total = summary.get("totalTests", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        pass_rate = summary.get("passRate", 0)
        elapsed = self.results.get("totalElapsedMs", 0)

        print(f"\n  📊 复刻结果: {passed}/{total} 通过 ({pass_rate}%), "
              f"{failed} 失败, {skipped} 跳过")
        print(f"  ⏱️  耗时: {elapsed}ms ({elapsed/1000:.1f}s)")

        # 逐模块打印
        modules = self.results.get("modules", {})
        print(f"\n  📋 模块详情:")
        for mod_key in sorted(modules.keys()):
            mod = modules[mod_key]
            mod_name = self.MODULE_NAMES.get(mod_key, mod_key)
            status = mod.get("status", "?")
            p = mod.get("passed", 0)
            f = mod.get("failed", 0)
            s = mod.get("skipped", 0)
            icon = "✅" if status == "PASS" else ("⚠️" if status == "PARTIAL" else "❌")
            print(f"     {icon} {mod_name}: {p}P/{f}F/{s}S [{status}]")

            # 打印失败的测试
            for test in mod.get("tests", []):
                if test.get("status") == "FAIL":
                    print(f"        🔴 {test['name']}: {test.get('detail', '')[:100]}")
                elif test.get("status") == "SKIP":
                    print(f"        ⬜ {test['name']}: {test.get('detail', '')[:100]}")


# ============================================================
# Phase 3 & 4: 报告生成 + 安装预览
# ============================================================
class ReportGenerator:
    """结构化测试报告生成器"""

    PLUGIN_HINTS = PluginDetector.PLUGIN_MANIFEST

    def __init__(self, plugin_results: Dict, replication_results: Dict,
                 output_dir: Path = None):
        self.plugin_results = plugin_results
        self.replication_results = replication_results
        self.output_dir = output_dir or OUTPUT_DIR
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = self.timestamp

    def generate_all(self) -> Dict[str, Path]:
        """生成所有格式的报告"""
        reports = {}

        # JSON 原始报告
        json_path = self.output_dir / f"ae_reproduction_{self.session_id}.json"
        json_report = self._build_json_report()
        json_path.write_text(json.dumps(json_report, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        reports["json"] = json_path

        # Markdown 报告
        md_path = self.output_dir / f"ae_reproduction_{self.session_id}.md"
        md_report = self._build_markdown_report(json_report)
        md_path.write_text(md_report, encoding="utf-8")
        reports["markdown"] = md_path

        # HTML 报告
        html_path = self.output_dir / f"ae_reproduction_{self.session_id}.html"
        html_report = self._build_html_report(json_report)
        html_path.write_text(html_report, encoding="utf-8")
        reports["html"] = html_path

        return reports

    def _build_json_report(self) -> Dict:
        """构建结构化 JSON 报告"""
        now = datetime.now().isoformat()

        # 汇总复制结果
        rep_summary = self.replication_results.get("summary", {})
        rep_modules = self.replication_results.get("modules", {})

        # 构建模块测试详情
        module_details = {}
        for mod_key, mod in rep_modules.items():
            module_details[mod_key] = {
                "name": ProjectReplicator.MODULE_NAMES.get(mod_key, mod_key),
                "status": mod.get("status", "UNKNOWN"),
                "passed": mod.get("passed", 0),
                "failed": mod.get("failed", 0),
                "skipped": mod.get("skipped", 0),
                "tests": [
                    {
                        "name": t.get("name", ""),
                        "status": t.get("status", "?"),
                        "detail": t.get("detail", ""),
                        "time": t.get("time", "")
                    }
                    for t in mod.get("tests", [])
                ]
            }

        # 构建插件详情
        detected = self.plugin_results.get("detected", {})
        plugins_detail = {}
        for name, info in detected.items():
            if isinstance(info, dict):
                plugins_detail[name] = {
                    "available": info.get("available", False),
                    "category": info.get("category", "unknown"),
                    "matchName": info.get("matchName", ""),
                    "error": info.get("error", ""),
                    "installHint": PluginDetector.PLUGIN_MANIFEST.get(name, {})
                }

        # 缺失插件
        missing_plugins = []
        for name, info in detected.items():
            if isinstance(info, dict) and not info.get("available", False):
                manifest = PluginDetector.PLUGIN_MANIFEST.get(name, {})
                missing_plugins.append({
                    "name": name,
                    "category": info.get("category", "unknown"),
                    "vendor": manifest.get("vendor", ""),
                    "url": manifest.get("url", ""),
                    "price": manifest.get("price", "未知"),
                    "essential_for": manifest.get("essential_for", [])
                })

        return {
            "report_meta": {
                "generated_at": now,
                "session_id": self.session_id,
                "ae_version": self.plugin_results.get("aeVersion", "unknown"),
                "ae_install_path": self.plugin_results.get("aeInstallPath", "unknown"),
                "total_elapsed_ms": self.replication_results.get("totalElapsedMs", 0),
            },
            "phase1_plugin_detection": {
                "summary": self.plugin_results.get("summary", {}),
                "plugins": plugins_detail,
                "missing_plugins": missing_plugins,
                "ae_environment": {
                    "version": self.plugin_results.get("aeVersion", ""),
                    "install_path": self.plugin_results.get("aeInstallPath", ""),
                    "presets_path": self.plugin_results.get("aePresetsPath", ""),
                    "scriptui_panels": self.plugin_results.get("scriptUIPanels", []),
                }
            },
            "phase2_project_replication": {
                "summary": {
                    "total_tests": rep_summary.get("totalTests", 0),
                    "passed": rep_summary.get("passed", 0),
                    "failed": rep_summary.get("failed", 0),
                    "skipped": rep_summary.get("skipped", 0),
                    "pass_rate": rep_summary.get("passRate", 0),
                    "elapsed_ms": self.replication_results.get("totalElapsedMs", 0),
                },
                "modules": module_details,
                "errors": self._collect_errors(rep_modules),
            },
            "phase3_install_preview": {
                "missing_count": len(missing_plugins),
                "missing_plugins": missing_plugins,
                "total_estimated_cost": self._estimate_cost(missing_plugins),
            }
        }

    def _collect_errors(self, modules: Dict) -> List[Dict]:
        """收集所有失败和跳过的测试"""
        errors = []
        for mod_key, mod in modules.items():
            for test in mod.get("tests", []):
                if test.get("status") in ("FAIL", "SKIP"):
                    errors.append({
                        "module": mod_key,
                        "test": test.get("name", ""),
                        "status": test.get("status"),
                        "detail": test.get("detail", ""),
                        "time": test.get("time", "")
                    })
        return errors

    def _estimate_cost(self, missing: List[Dict]) -> str:
        """估算缺失插件总费用"""
        total_free = 0
        total_paid = 0
        for p in missing:
            price = p.get("price", "")
            if "免费" in price or "Free" in price or "free" in price:
                total_free += 1
            else:
                total_paid += 1
        return f"{total_free} 免费插件 + {total_paid} 付费插件"

    def _build_markdown_report(self, data: Dict) -> str:
        """生成 Markdown 格式报告"""
        meta = data["report_meta"]
        p1 = data["phase1_plugin_detection"]
        p2 = data["phase2_project_replication"]
        p3 = data["phase3_install_preview"]

        lines = []
        lines.append(f"# AE 工程实战预测与重现 - 测试报告")
        lines.append(f"")
        lines.append(f"**生成时间**: {meta['generated_at']}")
        lines.append(f"**会话 ID**: {meta['session_id']}")
        lines.append(f"**AE 版本**: {meta['ae_version']}")
        lines.append(f"**总耗时**: {meta['total_elapsed_ms']}ms")
        lines.append(f"")
        lines.append(f"---")

        # 总览
        lines.append(f"## 📊 执行总览")
        lines.append(f"")
        p2s = p2["summary"]
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 总测试数 | {p2s['total_tests']} |")
        lines.append(f"| 通过 | {p2s['passed']} |")
        lines.append(f"| 失败 | {p2s['failed']} |")
        lines.append(f"| 跳过 | {p2s['skipped']} |")
        lines.append(f"| 通过率 | **{p2s['pass_rate']}%** |")
        lines.append(f"| 插件可用 | {p1['summary'].get('available', 0)}/{p1['summary'].get('total', 0)} |")
        lines.append(f"")
        lines.append(f"---")

        # 模块详情
        lines.append(f"## 🧩 模块测试详情")
        lines.append(f"")
        for mod_key, mod in data["phase2_project_replication"]["modules"].items():
            status = mod["status"]
            icon = "✅" if status == "PASS" else ("⚠️" if status == "PARTIAL" else "❌")
            lines.append(f"### {icon} {mod['name']} [{status}]")
            lines.append(f"")
            lines.append(f"通过: {mod['passed']} | 失败: {mod['failed']} | 跳过: {mod['skipped']}")
            lines.append(f"")

            # 测试详情表
            if mod["tests"]:
                lines.append(f"| 测试项 | 状态 | 详情 |")
                lines.append(f"|--------|------|------|")
                for t in mod["tests"]:
                    s_icon = "✅" if t["status"] == "PASS" else ("🔴" if t["status"] == "FAIL" else "⬜")
                    detail = t["detail"].replace("\n", " ")[:120]
                    lines.append(f"| {t['name']} | {s_icon} {t['status']} | {detail} |")
                lines.append(f"")

        # 插件检测
        lines.append(f"---")
        lines.append(f"## 🔌 插件检测结果")
        lines.append(f"")
        p1s = p1["summary"]
        lines.append(f"- **AE 版本**: {p1['ae_environment'].get('version', '?')}")
        lines.append(f"- **安装路径**: `{p1['ae_environment'].get('install_path', '?')}`")
        lines.append(f"- **检测总计**: {p1s.get('total', 0)}")
        lines.append(f"- **可用**: {p1s.get('available', 0)}")
        lines.append(f"- **不可用**: {p1s.get('unavailable', 0)}")
        lines.append(f"")

        # 缺失插件
        if p3["missing_plugins"]:
            lines.append(f"### 🔴 缺失插件 ({p3['missing_count']} 个)")
            lines.append(f"")
            lines.append(f"| 插件 | 厂商 | 价格 | 获取链接 |")
            lines.append(f"|------|------|------|----------|")
            for mp in p3["missing_plugins"]:
                lines.append(f"| {mp['name']} | {mp['vendor']} | {mp['price']} | [{mp['url']}]({mp['url']}) |")
            lines.append(f"")
            lines.append(f"**预估费用**: {p3['total_estimated_cost']}")
            lines.append(f"")

        # 错误日志
        errors = data["phase2_project_replication"].get("errors", [])
        if errors:
            lines.append(f"---")
            lines.append(f"## 🐛 错误日志")
            lines.append(f"")
            for err in errors:
                lines.append(f"- **[{err['module']}]** {err['test']} ({err['status']})")
                lines.append(f"  ```")
                lines.append(f"  {err['detail']}")
                lines.append(f"  ```")
                lines.append(f"")

        # 复现步骤
        lines.append(f"---")
        lines.append(f"## 🔄 复现步骤")
        lines.append(f"")
        lines.append(f"### 前提条件")
        lines.append(f"1. 确保 Adobe After Effects **{meta['ae_version']}** 已安装并启动")
        lines.append(f"2. 确保 Bridge 面板已加载: `{p1['ae_environment'].get('scriptui_panels_path', '?')}`")
        lines.append(f"3. 确保 `.ae-mcp-bridge/` 目录存在且 Bridge 正在轮询")
        lines.append(f"")
        lines.append(f"### 执行复现")
        lines.append(f"```bash")
        lines.append(f"cd {PROJECT_ROOT}")
        lines.append(f"python scripts/ae_practical_reproduction.py")
        lines.append(f"```")
        lines.append(f"")
        lines.append(f"### 仅插件检测")
        lines.append(f"```bash")
        lines.append(f"python scripts/ae_practical_reproduction.py --plugins-only")
        lines.append(f"```")

        return "\n".join(lines)

    def _build_html_report(self, data: Dict) -> str:
        """生成 HTML 格式报告"""
        meta = data["report_meta"]
        p1 = data["phase1_plugin_detection"]
        p2 = data["phase2_project_replication"]
        p3 = data["phase3_install_preview"]

        p2s = p2["summary"]
        p1s = p1["summary"]

        # 模块表格行
        module_rows = ""
        for mod_key, mod in data["phase2_project_replication"]["modules"].items():
            status = mod["status"]
            bg = "#d4edda" if status == "PASS" else ("#fff3cd" if status == "PARTIAL" else "#f8d7da")
            icon = "✅" if status == "PASS" else ("⚠️" if status == "PARTIAL" else "❌")
            module_rows += f"""
            <tr style="background:{bg}">
                <td>{icon}</td>
                <td>{mod['name']}</td>
                <td>{mod['passed']}</td>
                <td>{mod['failed']}</td>
                <td>{mod['skipped']}</td>
                <td><strong>{status}</strong></td>
            </tr>"""

        # 测试详情
        test_details = ""
        for mod_key, mod in data["phase2_project_replication"]["modules"].items():
            test_rows = ""
            for t in mod["tests"]:
                status = t["status"]
                bg = "#d4edda" if status == "PASS" else ("#f8d7da" if status == "FAIL" else "#e2e3e5")
                s_icon = "✅" if status == "PASS" else ("🔴" if status == "FAIL" else "⬜")
                detail = t["detail"].replace("<", "&lt;").replace(">", "&gt;")[:200]
                test_rows += f"""
                <tr style="background:{bg}">
                    <td>{t['name']}</td>
                    <td>{s_icon} {status}</td>
                    <td style="font-size:0.85em">{detail}</td>
                </tr>"""

            test_details += f"""
            <details>
                <summary style="font-weight:bold;cursor:pointer">{mod['name']} [{mod['status']}]</summary>
                <table style="width:100%;margin-top:8px">
                    <tr><th>测试</th><th>状态</th><th>详情</th></tr>
                    {test_rows}
                </table>
            </details>
            <br>"""

        # 缺失插件行
        missing_plugin_rows = ""
        for mp in p3["missing_plugins"]:
            missing_plugin_rows += f"""
            <tr>
                <td>{mp['name']}</td>
                <td>{mp['vendor']}</td>
                <td>{mp['price']}</td>
                <td><a href="{mp['url']}" target="_blank">🔗 获取</a></td>
                <td>{', '.join(mp.get('essential_for', []))}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AE 工程实战预测与重现 - 测试报告</title>
<style>
    body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; max-width: 1100px; margin: 0 auto; padding: 20px; background: #f0f2f5; color: #1a1a2e; }}
    .card {{ background: white; border-radius: 12px; padding: 24px; margin: 16px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    h1 {{ color: #0d47a1; border-bottom: 3px solid #1976d2; padding-bottom: 11px; }}
    h2 {{ color: #1565c0; margin-top: 24px; }}
    h3 {{ color: #1976d2; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }}
    .stat {{ text-align: center; padding: 16px; border-radius: 8px; }}
    .stat.pass {{ background: #e8f5e9; }}
    .stat.fail {{ background: #ffebee; }}
    .stat.skip {{ background: #f5f5f5; }}
    .stat .num {{ font-size: 2em; font-weight: bold; }}
    .stat .label {{ font-size: 0.9em; color: #666; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
    th {{ background: #e3f2fd; font-weight: 600; }}
    details {{ margin: 8px 0; }}
    .progress-bar {{ background: #e0e0e0; border-radius: 8px; height: 24px; overflow: hidden; }}
    .progress-fill {{ height: 100%; border-radius: 8px; background: linear-gradient(90deg, #4caf50 {p2s['pass_rate']}%, #ff9800 {p2s['pass_rate']}%); }}
    .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 16px; margin: 12px 0; border-radius: 4px; }}
    .error {{ background: #f8d7da; border-left: 4px solid #dc3545; padding: 12px 16px; margin: 12px 0; border-radius: 4px; }}
    .success {{ background: #d4edda; border-left: 4px solid #28a745; padding: 12px 16px; margin: 12px 0; border-radius: 4px; }}
    .meta {{ color: #666; font-size: 0.9em; }}
    a {{ color: #1976d2; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>

<h1>🧪 AE 工程实战预测与重现</h1>
<p class="meta">生成时间: {meta['generated_at']} | 会话: {meta['session_id']} | AE: {meta['ae_version']}</p>

<div class="grid">
    <div class="stat pass">
        <div class="num">{p2s['passed']}</div>
        <div class="label">✅ 通过</div>
    </div>
    <div class="stat fail">
        <div class="num">{p2s['failed']}</div>
        <div class="label">🔴 失败</div>
    </div>
    <div class="stat skip">
        <div class="num">{p2s['skipped']}</div>
        <div class="label">⬜ 跳过</div>
    </div>
    <div class="stat pass">
        <div class="num">{p2s['pass_rate']}%</div>
        <div class="label">📊 通过率</div>
    </div>
    <div class="stat {'pass' if p1s.get('available',0) > 0 else 'fail'}">
        <div class="num">{p1s.get('available', 0)}/{p1s.get('total', 0)}</div>
        <div class="label">🔌 插件可用</div>
    </div>
</div>

<!-- 进度条 -->
<div class="progress-bar">
    <div class="progress-fill" style="width:{p2s['pass_rate']}%"></div>
</div>
<p style="text-align:center;margin:4px 0 16px">总耗时: {meta['total_elapsed_ms']}ms</p>

<!-- 模块总览 -->
<div class="card">
    <h2>📋 模块测试总览</h2>
    <table>
        <tr><th></th><th>模块</th><th>通过</th><th>失败</th><th>跳过</th><th>状态</th></tr>
        {module_rows}
    </table>
</div>

<!-- 测试详情 -->
<div class="card">
    <h2>🔍 逐测试详情</h2>
    {test_details}
</div>

<!-- 插件检测 -->
<div class="card">
    <h2>🔌 插件/效果依赖检测</h2>
    <p>AE 安装路径: <code>{p1['ae_environment'].get('install_path', '?')}</code></p>
    <p>检测总计: <strong>{p1s.get('total', 0)}</strong> 个效果 |
       可用: <strong style="color:green">{p1s.get('available', 0)}</strong> |
       不可用: <strong style="color:red">{p1s.get('unavailable', 0)}</strong></p>

    <div class="{'warning' if p3['missing_plugins'] else 'success'}">
        <h3>{'🔴 缺失插件安装提示' if p3['missing_plugins'] else '✅ 所有已知插件已安装'}</h3>
        {"<p>以下 '{0}' 个插件未检测到，需要手动安装后才能使用对应效果功能:</p>".format(p3['missing_count']) if p3['missing_plugins'] else ''}
    </div>

    {'<table><tr><th>插件</th><th>厂商</th><th>价格</th><th>获取</th><th>适用场景</th></tr>' + missing_plugin_rows + '</table>' if missing_plugin_rows else ''}

    <p>💡 <strong>预估费用</strong>: {p3['total_estimated_cost']}</p>
</div>

<!-- 错误日志 -->
<div class="card">
    <h2>🐛 错误与异常日志</h2>
    {self._build_error_section_html(data)}
</div>

<!-- 复现步骤 -->
<div class="card">
    <h2>🔄 复现步骤</h2>
    <ol>
        <li>启动 <strong>Adobe After Effects {meta['ae_version']}</strong></li>
        <li>确认 Bridge 面板已加载</li>
        <li>执行: <code>python scripts/ae_practical_reproduction.py</code></li>
    </ol>
</div>

<p style="text-align:center;color:#999;margin-top:32px;">
    由 AE-Knowledge-Vault 实战预测系统生成 | {meta['generated_at']}
</p>

</body>
</html>"""

    def _build_error_section_html(self, data: Dict) -> str:
        errors = data["phase2_project_replication"].get("errors", [])
        if not errors:
            return '<div class="success">✅ 无错误记录</div>'

        lines = []
        for err in errors[:30]:  # 最多显示30条
            icon = "🔴" if err["status"] == "FAIL" else "⬜"
            lines.append(f"""
            <div class="{'error' if err['status'] == 'FAIL' else 'warning'}">
                <strong>{icon} [{err['module']}] {err['test']}</strong><br>
                <pre style="font-size:0.85em;margin:4px 0">{err['detail']}</pre>
                <span style="font-size:0.8em;color:#888">{err['time']}</span>
            </div>""")
        return "\n".join(lines)

    def print_install_preview(self):
        """终端打印安装预览提示"""
        p3_data = self._build_json_report()["phase3_install_preview"]
        missing = p3_data["missing_plugins"]

        if not missing:
            print("\n  ✅ 所有已知插件依赖已满足！")
            return

        print("\n" + "=" * 60)
        print("  📦 Phase 4: 缺失插件安装预览")
        print("=" * 60)
        print(f"\n  检测到 {len(missing)} 个缺失插件:\n")

        for i, mp in enumerate(missing, 1):
            print(f"  {i}. {mp['name']}")
            print(f"     厂商: {mp['vendor']}")
            print(f"     价格: {mp['price']}")
            print(f"     获取: {mp['url']}")
            if mp.get("essential_for"):
                print(f"     用途: {', '.join(mp['essential_for'])}")
            print()

        print(f"  预估总费用: {p3_data['total_estimated_cost']}")
        print(f"\n  💡 提示: 可先安装免费插件（Saber 等），付费插件按需获取。")


# ============================================================
# 主流程编排
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="AE 工程实战预测与完整重现",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/ae_practical_reproduction.py                 # 完整流程
  python scripts/ae_practical_reproduction.py --quick          # 快速模式
  python scripts/ae_practical_reproduction.py --plugins-only   # 仅插件检测
  python scripts/ae_practical_reproduction.py --output ./reports  # 指定输出
        """
    )
    parser.add_argument("--quick", action="store_true",
                        help="快速模式（缩短超时）")
    parser.add_argument("--plugins-only", action="store_true",
                        help="仅执行插件检测")
    parser.add_argument("--output", type=str, default=None,
                        help="报告输出目录")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Bridge 命令超时秒数")
    args = parser.parse_args()

    timeout = args.timeout or (30 if args.quick else 120)
    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    print("=" * 60)
    print("  🧪 AE-Knowledge-Vault 实战预测与重现系统")
    print("  ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    # 检查 Bridge 目录
    if not BRIDGE_DIR.exists():
        print(f"\n  ⚠️  Bridge 目录不存在: {BRIDGE_DIR}")
        print(f"  💡 请先确保 AE 已启动且 Bridge 面板已加载")
        print(f"  📖 运行 .ae-mcp-bridge/2_mcp_bridge_loader.jsx")
        print(f"\n  🔧 切换到离线诊断模式...")

        # 离线模式：生成模板报告
        offline_report = generate_offline_report(output_dir)
        print(f"\n  📄 离线报告已生成:")
        for fmt, path in offline_report.items():
            print(f"     {fmt}: {path}")
        return

    # 初始化 Bridge 客户端
    bridge = AEBridgeClient(bridge_dir=BRIDGE_DIR, timeout=timeout)

    # 连接测试
    print(f"\n  📡 检测 AE Bridge 连接...")
    online, ping_result = bridge.ping()
    if not online:
        print(f"  ⚠️  Bridge 未响应: {ping_result}")
        print(f"  💡 请确认:")
        print(f"     1. AE 已启动")
        print(f"     2. Bridge 面板 (2_mcp_bridge_loader.jsx) 已加载")
        print(f"     3. Bridge 目录正确: {BRIDGE_DIR}")
        print(f"\n  🔧 切换到离线诊断模式...")
        offline_report = generate_offline_report(output_dir)
        print(f"\n  📄 离线报告已生成:")
        for fmt, path in offline_report.items():
            print(f"     {fmt}: {path}")
        return

    print(f"  ✅ Bridge 在线 (响应: {str(ping_result)[:80]})")

    # Phase 1: 插件检测
    plugin_results = {}
    detector = PluginDetector(bridge)
    try:
        plugin_results = detector.run_detection()
    except Exception as e:
        print(f"  ❌ 插件检测异常: {e}")
        traceback.print_exc()
        plugin_results = {"error": str(e), "success": False}

    if args.plugins_only:
        print("\n  ✅ 插件检测完成（--plugins-only 模式）")
        return

    # Phase 2: 工程复刻
    replication_results = {}
    if not args.plugins_only:
        replicator = ProjectReplicator(bridge)
        try:
            replication_results = replicator.run_replication()
        except Exception as e:
            print(f"  ❌ 工程复刻异常: {e}")
            traceback.print_exc()
            replication_results = {"error": str(e), "success": False}

    # Phase 3: 报告生成
    print("\n" + "=" * 60)
    print("  📝 Phase 3: 生成结构化报告")
    print("=" * 60)

    report_gen = ReportGenerator(
        plugin_results=plugin_results,
        replication_results=replication_results,
        output_dir=output_dir
    )
    reports = report_gen.generate_all()

    # Phase 4: 安装预览
    print("\n" + "=" * 60)
    print("  📦 Phase 4: 缺失插件安装预览")
    print("=" * 60)
    report_gen.print_install_preview()

    # 最终结果
    print("\n" + "=" * 60)
    print("  🎉 实战预测与重现完成!")
    print("=" * 60)
    print(f"\n  📄 报告文件:")
    for fmt, path in reports.items():
        print(f"     {fmt}: {path}")

    # 如果在 HTML 报告中，尝试打开
    html_path = reports.get("html")
    if html_path and html_path.exists():
        print(f"\n  🌐 浏览器打开 HTML 报告: {html_path}")
        try:
            import webbrowser
            webbrowser.open(f"file:///{html_path.as_posix()}")
        except Exception:
            pass


def generate_offline_report(output_dir: Path) -> Dict[str, Path]:
    """离线模式报告 - 当 AE Bridge 不可用时生成"""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    # 构建 JSON 版离线报告
    report_data = {
        "report_meta": {
            "generated_at": now.isoformat(),
            "session_id": timestamp,
            "ae_version": "OFFLINE_DIAGNOSTIC",
            "total_elapsed_ms": 0,
            "mode": "offline_diagnostic"
        },
        "phase1_plugin_detection": {
            "summary": {"total": 0, "available": 0, "unavailable": 0},
            "plugins": {},
            "missing_plugins": [],
            "ae_environment": {"version": "未连接", "install_path": "未检测"}
        },
        "phase2_project_replication": {
            "summary": {"total_tests": 0, "passed": 0, "failed": 0, "skipped": 0},
            "modules": {},
            "errors": [{
                "module": "SYSTEM",
                "test": "BridgeConnection",
                "status": "FAIL",
                "detail": "AE Bridge 未连接，所有工程复刻测试被跳过。请启动 AE 并加载 Bridge 面板 (.ae-mcp-bridge/2_mcp_bridge_loader.jsx)"
            }]
        },
        "phase3_install_preview": {
            "missing_count": 0,
            "missing_plugins": [],
            "total_estimated_cost": "N/A (离线模式)"
        },
        "offline_note": "此报告在离线诊断模式下生成。需要 AE 运行并加载 Bridge 面板以执行实际测试。"
    }

    json_path = output_dir / f"ae_reproduction_{timestamp}_offline.json"
    json_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    # Markdown 离线报告
    md_lines = [
        f"# AE 工程实战预测与重现 - 离线诊断报告",
        f"",
        f"**生成时间**: {now.isoformat()}",
        f"**模式**: ⚠️ 离线诊断 (AE Bridge 未连接)",
        f"",
        f"---",
        f"",
        f"## ❌ Bridge 连接失败",
        f"",
        f"无法连接到 AE MCP Bridge (`{BRIDGE_DIR}`)。",
        f"",
        f"### 排障步骤",
        f"1. 确认 **Adobe After Effects** 已启动",
        f"2. 在 AE 中手动加载 Bridge 面板:",
        f"   - 文件 → 脚本 → 运行脚本文件",
        f"   - 选择: `{SCRIPTS_DIR.parent / '.ae-mcp-bridge' / '2_mcp_bridge_loader.jsx'}`",
        f"3. 查看 AE 的 ExtendScript 控制台是否有错误信息",
        f"4. 确认 Bridge 目录存在: `{BRIDGE_DIR}`",
        f"5. 确认 `ae_command.json` 文件有写入权限",
        f"",
        f"### 修复后重新运行",
        f"```bash",
        f"cd {PROJECT_ROOT}",
        f"python scripts/ae_practical_reproduction.py",
        f"```",
        f"",
        f"---",
        f"*由 AE-Knowledge-Vault 离线诊断系统生成*"
    ]
    md_path = output_dir / f"ae_reproduction_{timestamp}_offline.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {"json": json_path, "markdown": md_path}


if __name__ == "__main__":
    main()
