#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import shutil
import os
import sys

print("=" * 50)
print("  AE 2025 MCP Bridge 更新工具 v1.0")
print("=" * 50)
print()

source_path = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-bridge-auto.jsx"
target_path = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\mcp-bridge-auto.jsx"
backup_path = target_path + ".bak"

if not os.path.exists(source_path):
    print(f"❌ 源文件不存在: {source_path}")
    print("请确保 bridge 文件在正确位置")
    input("按任意键退出...")
    sys.exit(1)

print("📋 准备更新 AE 2025 MCP Bridge...")
print(f"源文件: {source_path}")
print(f"目标文件: {target_path}")
print()

try:
    print("🔄 创建备份...")
    if os.path.exists(target_path):
        shutil.copy2(target_path, backup_path)
        print(f"✅ 备份已创建: {backup_path}")
    else:
        print("ℹ️ 目标文件不存在，跳过备份")

    print()
    print("🔄 复制更新文件...")
    shutil.copy2(source_path, target_path)
    print("✅ 更新完成!")
    print()
    print("=" * 50)
    print("  更新成功! 请重启 AE 2025 使更改生效")
    print("=" * 50)

except Exception as e:
    print()
    print(f"❌ 更新失败: {e}")
    print()
    print("💡 请尝试以下方法:")
    print("1. 右键点击此脚本 -> 以管理员身份运行")
    print("2. 手动复制文件:")
    print(f"   从: {source_path}")
    print(f"   到: {target_path}")

print()
input("按任意键退出...")
