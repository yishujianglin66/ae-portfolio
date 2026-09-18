#!/usr/bin/env python3
"""部署 AE MCP Bridge JSX 脚本到 AE 脚本目录，创建桥接目录，验证服务。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

AE_ROOT = Path("C:/Program Files/Adobe/Adobe After Effects 2025")
AE_SCRIPTS = AE_ROOT / "Support Files" / "Scripts"
BRIDGE_DIR_NAME = "ae-mcp-bridge"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER = PROJECT_ROOT / "ae-mcp-server"
MCP_SCRIPTS = MCP_SERVER / "scripts"

DOCUMENTS_DIR = Path.home() / "Documents"
BRIDGE_DIR = DOCUMENTS_DIR / "ae-mcp-bridge"


def deploy_scripts() -> bool:
    """部署 JSX 脚本到 AE 脚本目录。"""
    print("=" * 60)
    print("1. 部署 AE MCP Bridge JSX 脚本")
    print("=" * 60)

    target_dir = AE_SCRIPTS / BRIDGE_DIR_NAME

    if not AE_SCRIPTS.exists():
        print(f"  ❌ AE 脚本目录不存在: {AE_SCRIPTS}")
        return False

    if target_dir.exists():
        print(f"  ⚠️  目标目录已存在，将覆盖: {target_dir}")
        shutil.rmtree(target_dir)

    try:
        shutil.copytree(MCP_SCRIPTS, target_dir)
        print(f"  ✅ 脚本已复制到: {target_dir}")

        # 统计文件
        jsx_files = list(target_dir.rglob("*.jsx"))
        lib_files = list((target_dir / "_lib").rglob("*.jsx")) if (target_dir / "_lib").exists() else []
        print(f"  📊 共 {len(jsx_files)} 个 JSX 文件（含 _lib: {len(lib_files)}）")

        for f in sorted(target_dir.glob("*.jsx")):
            print(f"    - {f.name}")
        return True
    except PermissionError:
        print(f"  ❌ 权限不足，无法写入: {target_dir}")
        print("  💡 请以管理员身份运行，或手动复制脚本目录")
        return False
    except Exception as e:
        print(f"  ❌ 复制失败: {e}")
        return False


def create_bridge_dir() -> bool:
    """创建桥接通信目录。"""
    print()
    print("=" * 60)
    print("2. 创建桥接通信目录")
    print("=" * 60)

    try:
        BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ 桥接目录: {BRIDGE_DIR}")

        # 创建测试文件验证可写
        test_file = BRIDGE_DIR / "test_write.tmp"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        print("  ✅ 读写权限验证通过")

        return True
    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
        return False


def verify_mcp_server() -> bool:
    """验证 MCP Server 构建和基本可用性。"""
    print()
    print("=" * 60)
    print("3. 验证 MCP Server")
    print("=" * 60)

    dist_index = MCP_SERVER / "dist" / "index.js"
    if not dist_index.exists():
        print("  ⚠️  dist 目录不存在，尝试构建...")
        return False

    print(f"  ✅ 构建产物存在: {dist_index}")

    # 检查 package.json
    pkg_json = MCP_SERVER / "package.json"
    if pkg_json.exists():
        import json
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        print(f"  📦 包名: {pkg.get('name', '?')}")
        print(f"  📌 版本: {pkg.get('version', '?')}")

    return True


def main() -> int:
    print("🚀 AE MCP Bridge 部署工具")
    print()

    steps = [
        deploy_scripts,
        create_bridge_dir,
        verify_mcp_server,
    ]

    results = []
    for step in steps:
        results.append(step())

    print()
    print("=" * 60)
    print("📋 部署结果")
    print("=" * 60)

    all_ok = all(results)
    if all_ok:
        print("  ✅ 全部部署成功！")
    else:
        print("  ⚠️  部分步骤失败，请检查上方日志")

    print()
    print("📝 后续步骤：")
    print("  1. 打开 After Effects 2025")
    print(f"  2. 文件 → 脚本 → 运行脚本文件 → {BRIDGE_DIR_NAME}/bridge_listener.jsx")
    print("  3. 在 IDE 中配置 MCP Server，指向:")
    print("     command: node")
    print(f"     args: [{str(dist_index)!r}]")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
