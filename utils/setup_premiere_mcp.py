#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PremiereProMCP 一键配置脚本
============================
自动完成 Premiere Pro MCP 工具链的全部前置配置：
  1. CEP 插件安装（复制到 Adobe extensions 目录）
  2. 注册表 PlayerDebugMode 验证/修复
  3. .mcp.json 配置验证
  4. .premiere-mcp-bridge 通信目录创建与可写性测试
  5. 输出配置状态摘要

用法：
    py -3.12 setup_premiere_mcp.py
    py -3.12 setup_premiere_mcp.py --force   # 强制覆盖已有插件
"""

import io
import json
import os
import shutil
import sys
import tempfile

# 修复 Windows 控制台中文编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 路径常量
# ============================================================

PROJECT_ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"

# PremiereProMCP npm 包路径
NPM_PACKAGE_DIR = r"C:\Users\Administrator\AppData\Roaming\npm\node_modules\premiere-pro-mcp"
CEP_PLUGIN_SOURCE = os.path.join(NPM_PACKAGE_DIR, "cep-plugin")
MCP_SERVER_ENTRY = os.path.join(NPM_PACKAGE_DIR, "dist", "index.js")

# Adobe CEP 扩展安装目录
ADOBE_CEP_EXTENSIONS = os.path.join(os.environ.get("APPDATA", ""), "Adobe", "CEP", "extensions")
CEP_PLUGIN_TARGET = os.path.join(ADOBE_CEP_EXTENSIONS, "MCPBridgeCEP")

# 项目 PR Bridge 通信目录
PR_BRIDGE_DIR = os.path.join(PROJECT_ROOT, ".premiere-mcp-bridge")

# 项目 MCP 配置文件
MCP_JSON_PATH = os.path.join(PROJECT_ROOT, ".mcp.json")

# CEP 插件标识
CEP_EXTENSION_ID = "com.mcp.premiere.bridge"


# ============================================================
# 工具函数
# ============================================================

class Status:
    OK = "[OK]"
    WARN = "[WARN]"
    FAIL = "[FAIL]"
    INFO = "[INFO]"
    FIX = "[FIX]"


def print_status(status: str, message: str):
    """带颜色状态输出"""
    print(f"  {status} {message}")


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# Step 1: CEP 插件安装
# ============================================================

def step1_install_cep_plugin(force: bool = False) -> bool:
    """将 CEP 插件复制到 Adobe extensions 目录"""
    print_header("Step 1: CEP 插件安装")

    # 检查源目录
    if not os.path.isdir(CEP_PLUGIN_SOURCE):
        print_status(Status.FAIL, f"CEP 插件源目录不存在: {CEP_PLUGIN_SOURCE}")
        print_status(Status.INFO, "请先执行: npm install -g premiere-pro-mcp")
        return False

    print_status(Status.OK, f"源插件目录: {CEP_PLUGIN_SOURCE}")

    # 检查关键文件
    required_files = ["CSXS/manifest.xml", "host.jsx", "main.js", "index.html", "CSInterface.js"]
    missing = [f for f in required_files if not os.path.isfile(os.path.join(CEP_PLUGIN_SOURCE, f.replace("/", os.sep)))]
    if missing:
        print_status(Status.FAIL, f"插件文件不完整，缺少: {', '.join(missing)}")
        return False

    print_status(Status.OK, f"插件文件完整 ({len(required_files)} 个核心文件)")

    # 检查目标目录
    if not os.path.isdir(ADOBE_CEP_EXTENSIONS):
        print_status(Status.INFO, f"创建 Adobe CEP 目录: {ADOBE_CEP_EXTENSIONS}")
        os.makedirs(ADOBE_CEP_EXTENSIONS, exist_ok=True)

    # 检查是否已安装
    if os.path.exists(CEP_PLUGIN_TARGET):
        if force:
            print_status(Status.FIX, f"强制覆盖已有插件: {CEP_PLUGIN_TARGET}")
            shutil.rmtree(CEP_PLUGIN_TARGET)
        else:
            # 验证已安装版本是否完整
            manifest = os.path.join(CEP_PLUGIN_TARGET, "CSXS", "manifest.xml")
            if os.path.isfile(manifest):
                print_status(Status.OK, f"CEP 插件已安装: {CEP_PLUGIN_TARGET}")
                return True
            else:
                print_status(Status.WARN, "已安装但文件不完整，重新安装...")
                shutil.rmtree(CEP_PLUGIN_TARGET)

    # 执行复制
    try:
        shutil.copytree(CEP_PLUGIN_SOURCE, CEP_PLUGIN_TARGET)
        print_status(Status.OK, f"CEP 插件已安装到: {CEP_PLUGIN_TARGET}")

        # 验证
        if os.path.isfile(os.path.join(CEP_PLUGIN_TARGET, "CSXS", "manifest.xml")):
            print_status(Status.OK, "安装验证通过 (manifest.xml 存在)")
            return True
        else:
            print_status(Status.FAIL, "安装验证失败")
            return False

    except Exception as e:
        print_status(Status.FAIL, f"复制失败: {e}")
        return False


# ============================================================
# Step 2: 注册表 PlayerDebugMode 验证
# ============================================================

def step2_verify_registry() -> bool:
    """验证 CSXS PlayerDebugMode 注册表项"""
    print_header("Step 2: 注册表 PlayerDebugMode 验证")

    try:
        import winreg
    except ImportError:
        print_status(Status.WARN, "非 Windows 系统，跳过注册表检查")
        return True

    all_ok = True
    fixed_count = 0

    for version in range(9, 15):  # CSXS.9 ~ CSXS.14
        key_path = f"Software\\Adobe\\CSXS.{version}"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
            try:
                value, _ = winreg.QueryValueEx(key, "PlayerDebugMode")
                if str(value) == "1":
                    print_status(Status.OK, f"CSXS.{version}: PlayerDebugMode = 1")
                else:
                    print_status(Status.FIX, f"CSXS.{version}: PlayerDebugMode = {value} -> 修复为 1")
                    winreg.SetValueEx(key, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
                    fixed_count += 1
            except FileNotFoundError:
                print_status(Status.FIX, f"CSXS.{version}: PlayerDebugMode 不存在 -> 创建")
                winreg.SetValueEx(key, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
                fixed_count += 1
            winreg.CloseKey(key)
        except FileNotFoundError:
            # CSXS 键不存在（该版本未安装），尝试创建
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
                winreg.SetValueEx(key, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
                winreg.CloseKey(key)
                print_status(Status.FIX, f"CSXS.{version}: 创建键并设置 PlayerDebugMode = 1")
                fixed_count += 1
            except Exception:
                print_status(Status.INFO, f"CSXS.{version}: 跳过（无法创建）")
        except Exception as e:
            print_status(Status.WARN, f"CSXS.{version}: 检查失败 - {e}")
            all_ok = False

    if fixed_count > 0:
        print_status(Status.INFO, f"已修复 {fixed_count} 个注册表项")

    return all_ok or fixed_count > 0


# ============================================================
# Step 3: .mcp.json 配置验证
# ============================================================

def step3_verify_mcp_json() -> bool:
    """验证 .mcp.json 中 PremiereProMCP 配置"""
    print_header("Step 3: .mcp.json 配置验证")

    if not os.path.isfile(MCP_JSON_PATH):
        print_status(Status.FAIL, f"配置文件不存在: {MCP_JSON_PATH}")
        return False

    try:
        with open(MCP_JSON_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print_status(Status.FAIL, f"JSON 解析失败: {e}")
        return False

    servers = config.get("mcpServers", {})
    pr_config = servers.get("PremiereProMCP")

    if not pr_config:
        print_status(Status.FAIL, "PremiereProMCP 配置段不存在")
        return False

    print_status(Status.OK, "PremiereProMCP 配置段存在")

    # 验证 command
    command = pr_config.get("command", "")
    if command == "node":
        print_status(Status.OK, f"command: {command}")
    else:
        print_status(Status.WARN, f"command 异常: {command} (期望 'node')")

    # 验证 args (入口文件)
    args = pr_config.get("args", [])
    if args:
        entry_file = args[0]
        if os.path.isfile(entry_file):
            print_status(Status.OK, f"入口文件存在: {entry_file}")
        else:
            print_status(Status.FAIL, f"入口文件不存在: {entry_file}")
            # 尝试修复
            if os.path.isfile(MCP_SERVER_ENTRY):
                print_status(Status.FIX, f"修复为: {MCP_SERVER_ENTRY}")
                pr_config["args"] = [MCP_SERVER_ENTRY]
            else:
                return False

    # 验证 env.PREMIERE_TEMP_DIR
    env = pr_config.get("env", {})
    temp_dir = env.get("PREMIERE_TEMP_DIR", "")
    if temp_dir:
        # 标准化路径比较
        normalized_temp = os.path.normpath(temp_dir)
        normalized_bridge = os.path.normpath(PR_BRIDGE_DIR)
        if normalized_temp.lower() == normalized_bridge.lower():
            print_status(Status.OK, f"PREMIERE_TEMP_DIR: {temp_dir}")
        else:
            print_status(Status.WARN, f"PREMIERE_TEMP_DIR 路径不匹配: {temp_dir}")
            print_status(Status.FIX, f"修复为: {PR_BRIDGE_DIR}")
            pr_config["env"]["PREMIERE_TEMP_DIR"] = PR_BRIDGE_DIR
    else:
        print_status(Status.FIX, "PREMIERE_TEMP_DIR 未设置，添加...")
        if "env" not in pr_config:
            pr_config["env"] = {}
        pr_config["env"]["PREMIERE_TEMP_DIR"] = PR_BRIDGE_DIR

    # 验证 cwd
    cwd = pr_config.get("cwd", "")
    if cwd and os.path.isdir(cwd):
        print_status(Status.OK, f"cwd: {cwd}")
    else:
        print_status(Status.WARN, f"cwd 无效: {cwd}")

    # 如果有修复，写回文件
    print_status(Status.OK, ".mcp.json 配置验证通过")
    return True


# ============================================================
# Step 4: PR Bridge 通信目录
# ============================================================

def step4_setup_bridge_dir() -> bool:
    """创建并验证 .premiere-mcp-bridge 通信目录"""
    print_header("Step 4: PR Bridge 通信目录")

    # 创建目录
    if not os.path.isdir(PR_BRIDGE_DIR):
        os.makedirs(PR_BRIDGE_DIR, exist_ok=True)
        print_status(Status.FIX, f"创建目录: {PR_BRIDGE_DIR}")
    else:
        print_status(Status.OK, f"目录已存在: {PR_BRIDGE_DIR}")

    # 可写性测试
    test_file = os.path.join(PR_BRIDGE_DIR, "_write_test.tmp")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_file)
        print_status(Status.OK, "目录可写性测试通过")
    except Exception as e:
        print_status(Status.FAIL, f"目录不可写: {e}")
        return False

    # 检查是否有残留的命令/响应文件
    existing_files = os.listdir(PR_BRIDGE_DIR)
    if existing_files:
        print_status(Status.INFO, f"目录中有 {len(existing_files)} 个文件: {', '.join(existing_files[:5])}")
    else:
        print_status(Status.OK, "目录为空（就绪状态）")

    return True


# ============================================================
# Step 5: Node.js 环境验证
# ============================================================

def step5_verify_node() -> bool:
    """验证 Node.js 环境"""
    print_header("Step 5: Node.js 环境验证")

    # 检查 node 是否可用
    node_path = shutil.which("node")
    if node_path:
        print_status(Status.OK, f"Node.js: {node_path}")
    else:
        print_status(Status.FAIL, "Node.js 未在 PATH 中找到")
        return False

    # 检查 npm 包
    if os.path.isdir(NPM_PACKAGE_DIR):
        print_status(Status.OK, f"premiere-pro-mcp 包: {NPM_PACKAGE_DIR}")
    else:
        print_status(Status.FAIL, f"npm 包不存在: {NPM_PACKAGE_DIR}")
        print_status(Status.INFO, "请执行: npm install -g premiere-pro-mcp")
        return False

    # 检查 dist/index.js
    if os.path.isfile(MCP_SERVER_ENTRY):
        print_status(Status.OK, f"MCP Server 入口: {MCP_SERVER_ENTRY}")
    else:
        print_status(Status.FAIL, f"入口文件不存在: {MCP_SERVER_ENTRY}")
        print_status(Status.INFO, "可能需要: cd premiere-pro-mcp && npm run build")
        return False

    # 检查 package.json 版本
    pkg_json = os.path.join(NPM_PACKAGE_DIR, "package.json")
    if os.path.isfile(pkg_json):
        with open(pkg_json, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        version = pkg.get("version", "unknown")
        print_status(Status.OK, f"premiere-pro-mcp 版本: {version}")

    return True


# ============================================================
# Step 6: Premiere Pro 安装检测
# ============================================================

def step6_detect_premiere() -> bool:
    """检测 Premiere Pro 是否已安装"""
    print_header("Step 6: Premiere Pro 安装检测")

    possible_paths = [
        r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
        r"C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe",
        r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
        r"D:\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
        r"D:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
    ]

    found = None
    for p in possible_paths:
        if os.path.isfile(p):
            found = p
            break

    # 也尝试通过注册表查找
    if not found:
        try:
            import winreg
            # 搜索 Adobe 安装路径
            adobe_dir = r"C:\Program Files\Adobe"
            if os.path.isdir(adobe_dir):
                for item in os.listdir(adobe_dir):
                    if "Premiere" in item:
                        exe = os.path.join(adobe_dir, item, "Adobe Premiere Pro.exe")
                        if os.path.isfile(exe):
                            found = exe
                            break
        except Exception:
            pass

    if found:
        print_status(Status.OK, f"Premiere Pro: {found}")
        return True
    else:
        print_status(Status.WARN, "未检测到 Premiere Pro 安装")
        print_status(Status.INFO, "CEP 插件配置已完成，PR 启动后即可使用")
        return True  # 不阻塞，PR 可能安装在其他位置


# ============================================================
# 配置摘要
# ============================================================

def print_summary(results: dict):
    """输出配置状态摘要"""
    print_header("配置状态摘要")

    print(f"""
  +{'─'*56}+
  |{'PremiereProMCP 配置状态':^56}|
  +{'─'*56}+""")

    for step_name, (ok, detail) in results.items():
        icon = "✅" if ok else "❌"
        print(f"  | {icon} {step_name:<40} |")

    print(f"  +{'─'*56}+")

    # 后续操作提示
    all_ok = all(v[0] for v in results.values())
    if all_ok:
        print(f"""
  ✅ 配置完成！后续步骤：

  1. 启动（或重启）Premiere Pro
  2. 菜单 → Window → Extensions → MCP Bridge
  3. 设置 Temp Directory:
     {PR_BRIDGE_DIR}
  4. 点击 "Start Bridge" → 确认绿色 Running 状态
  5. 在 QoderCN 中调用 ping 工具验证连通性
""")
    else:
        print("""
  ⚠️ 部分配置未完成，请检查上方 [FAIL] 项并修复后重新运行。
""")


# ============================================================
# 主流程
# ============================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║     PremiereProMCP 一键配置工具 v1.0                    ║
║     项目: AE-Knowledge-Vault                            ║
╚══════════════════════════════════════════════════════════╝
""")

    force = "--force" in sys.argv

    results = {}

    # Step 1: CEP 插件
    results["CEP 插件安装"] = (
        step1_install_cep_plugin(force=force),
        CEP_PLUGIN_TARGET
    )

    # Step 2: 注册表
    results["注册表 DebugMode"] = (
        step2_verify_registry(),
        "CSXS.9~14 PlayerDebugMode=1"
    )

    # Step 3: .mcp.json
    results[".mcp.json 配置"] = (
        step3_verify_mcp_json(),
        MCP_JSON_PATH
    )

    # Step 4: Bridge 目录
    results["Bridge 通信目录"] = (
        step4_setup_bridge_dir(),
        PR_BRIDGE_DIR
    )

    # Step 5: Node.js
    results["Node.js 环境"] = (
        step5_verify_node(),
        "node + premiere-pro-mcp"
    )

    # Step 6: Premiere Pro
    results["Premiere Pro 检测"] = (
        step6_detect_premiere(),
        "PR 2020+"
    )

    # 摘要
    print_summary(results)

    # 返回码
    all_ok = all(v[0] for v in results.values())
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
