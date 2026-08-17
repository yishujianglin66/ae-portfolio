#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预设系统命令行接口

用法:
    py -3.12 scripts/preset_cli.py --list
    py -3.12 scripts/preset_cli.py --list --category text_animation
    py -3.12 scripts/preset_cli.py --search "赛博"
    py -3.12 scripts/preset_cli.py --execute cyberpunk_glitch_text
    py -3.12 scripts/preset_cli.py --chain "cyberpunk_glitch_text,cyberpunk_grade"
    py -3.12 scripts/preset_cli.py --combo cyberpunk_title_sequence
    py -3.12 scripts/preset_cli.py --info cyberpunk_glitch_text
    py -3.12 scripts/preset_cli.py --generate cyberpunk_glitch_text --output script.jsx
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ae.preset_system import PresetSystem, PRESET_CATEGORIES
from ae.preset_executor import PresetExecutor, PresetLibrary, initialize_default_combinations


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════╗
║              预设系统命令行接口 (Preset CLI)                  ║
║                    Version 1.0.0                            ║
║  管理和执行AE预设，支持搜索、组合、批量执行                   ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def list_presets(preset_system: PresetSystem):
    print("\n📋 预设分类:")
    print("-" * 60)

    category_info = preset_system.get_category_info()
    for key, info in PRESET_CATEGORIES.items():
        count = category_info.get(key, {}).get("count", 0)
        print(f"\n{info['icon']} {info['name']} ({count}种)")
        print(f"   描述: {info['description']}")
        print(f"   命令: --category {key}")


def list_category_presets(preset_system: PresetSystem, category: str):
    if category not in PRESET_CATEGORIES:
        print(f"\n❌ 无效分类: {category}")
        print("可用分类:")
        for key, info in PRESET_CATEGORIES.items():
            print(f"  • {key} - {info['name']}")
        return

    info = PRESET_CATEGORIES[category]
    presets = preset_system.list_presets(category)

    print(f"\n{info['icon']} {info['name']} - {info['description']}")
    print("-" * 60)

    if not presets:
        print("  (暂无预设)")
        return

    for i, preset_name in enumerate(presets, 1):
        preset = preset_system.get_preset(preset_name)
        tags = ", ".join(preset.tags[:3]) if preset and preset.tags else ""
        desc = preset.description if preset else ""
        print(f"\n  {i}. {preset_name}")
        if desc:
            print(f"     描述: {desc}")
        if tags:
            print(f"     标签: {tags}")


def search_presets(preset_system: PresetSystem, keyword: str):
    results = preset_system.search_presets(keyword)

    print(f"\n🔍 搜索结果: '{keyword}'")
    print("-" * 60)

    if not results:
        print("  (未找到匹配预设)")
        return

    for i, preset in enumerate(results, 1):
        print(f"\n  {i}. {preset.name}")
        print(f"     分类: {PRESET_CATEGORIES.get(preset.category, {}).get('name', preset.category)}")
        print(f"     描述: {preset.description}")
        print(f"     标签: {', '.join(preset.tags)}")


def execute_preset(executor: PresetExecutor, preset_name: str, params: dict = None):
    params = params or {}

    print(f"\n🚀 执行预设: {preset_name}")
    print("-" * 60)

    result = executor.execute_preset(preset_name, ae_client=None, **params)

    if result.get("success"):
        print(f"\n✅ 成功")
        print(f"   预设: {result.get('preset')}")
        print(f"   分类: {result.get('category')}")
        print(f"   状态: {result.get('status', 'executed')}")

        if result.get("jsx"):
            jsx_preview = result["jsx"][:200] + "..." if len(result["jsx"]) > 200 else result["jsx"]
            print(f"\n   JSX预览:")
            print(f"   {jsx_preview}")
    else:
        print(f"\n❌ 失败")
        print(f"   错误: {result.get('error')}")


def execute_preset_chain(executor: PresetExecutor, preset_names: list, params: dict = None):
    params = params or {}

    print(f"\n🔗 执行预设链: {', '.join(preset_names)}")
    print("-" * 60)

    result = executor.execute_preset_chain(preset_names, ae_client=None, shared_params=params)

    print(f"\n📊 执行结果:")
    print(f"   总预设: {result.get('total_presets')}")
    print(f"   成功: {result.get('success_count')}")
    print(f"   失败: {result.get('failed_count')}")

    print("\n📝 详细结果:")
    for i, r in enumerate(result.get("results", []), 1):
        status = "✅" if r.get("success") else "❌"
        print(f"\n   {i}. {status} {r.get('preset')}")
        if not r.get("success"):
            print(f"      错误: {r.get('error')}")


def execute_combination(executor: PresetExecutor, library: PresetLibrary, combo_name: str, params: dict = None):
    combo = library.get_combination(combo_name)

    if not combo:
        print(f"\n❌ 预设组合不存在: {combo_name}")
        print("可用组合:")
        for name in library.list_combinations():
            c = library.get_combination(name)
            print(f"  • {name} - {c.description if c else ''}")
        return

    params = {**(combo.parameters or {}), **(params or {})}

    print(f"\n🎭 执行预设组合: {combo.name}")
    print(f"   描述: {combo.description}")
    print(f"   包含预设: {', '.join(combo.presets)}")
    print("-" * 60)

    result = executor.execute_preset_chain(combo.presets, ae_client=None, shared_params=params)

    print(f"\n📊 执行结果:")
    print(f"   总预设: {result.get('total_presets')}")
    print(f"   成功: {result.get('success_count')}")
    print(f"   失败: {result.get('failed_count')}")

    print("\n📝 详细结果:")
    for i, r in enumerate(result.get("results", []), 1):
        status = "✅" if r.get("success") else "❌"
        print(f"\n   {i}. {status} {r.get('preset')}")
        if not r.get("success"):
            print(f"      错误: {r.get('error')}")


def show_preset_info(preset_system: PresetSystem, preset_name: str):
    preset = preset_system.get_preset(preset_name)

    if not preset:
        print(f"\n❌ 预设不存在: {preset_name}")
        return

    print(f"\n📋 预设详情: {preset.name}")
    print("-" * 60)

    print(f"\n基本信息:")
    print(f"  • 名称: {preset.name}")
    print(f"  • 分类: {PRESET_CATEGORIES.get(preset.category, {}).get('name', preset.category)}")
    print(f"  • 子分类: {preset.subcategory}")
    print(f"  • 描述: {preset.description}")
    print(f"  • 标签: {', '.join(preset.tags)}")

    print(f"\n参数:")
    for param_name, param_info in preset.parameters.items():
        default = preset.default_values.get(param_name, "无默认值")
        print(f"  • {param_name}:")
        print(f"     类型: {param_info.get('type', 'unknown')}")
        print(f"     描述: {param_info.get('description', '')}")
        print(f"     默认值: {default}")
        if "min" in param_info:
            print(f"     最小值: {param_info['min']}")
        if "max" in param_info:
            print(f"     最大值: {param_info['max']}")
        if "options" in param_info:
            print(f"     选项: {', '.join(param_info['options'])}")

    print(f"\n兼容性:")
    ae_versions = preset.compatibility.get("ae", [])
    print(f"  • AE版本: {', '.join(ae_versions)}")


def generate_script(preset_system: PresetSystem, preset_name: str, output_path: str, params: dict = None):
    params = params or {}

    try:
        jsx_code = preset_system.generate_script(preset_name, **params)

        if output_path:
            output_file = Path(output_path)
            output_file.write_text(jsx_code, encoding="utf-8")
            print(f"\n✅ JSX脚本已生成: {output_file}")
        else:
            print(f"\n📝 生成的JSX脚本:")
            print("-" * 60)
            print(jsx_code)
            print("-" * 60)

    except ValueError as e:
        print(f"\n❌ {e}")


def list_combinations(library: PresetLibrary):
    combos = library.list_combinations()

    print("\n🎭 预设组合:")
    print("-" * 60)

    if not combos:
        print("  (暂无组合)")
        return

    for i, name in enumerate(combos, 1):
        combo = library.get_combination(name)
        print(f"\n  {i}. {name}")
        print(f"     描述: {combo.description}")
        print(f"     预设: {', '.join(combo.presets)}")


def batch_generate(preset_system: PresetSystem, category: str, output_dir: str):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    presets = preset_system.list_presets(category)
    generated_count = 0
    failed_count = 0

    print(f"\n📦 批量生成 {PRESET_CATEGORIES.get(category, {}).get('name', category)} 预设脚本")
    print(f"   目标目录: {output_path}")
    print(f"   预设数量: {len(presets)}")
    print("-" * 60)

    for preset_name in presets:
        try:
            jsx_code = preset_system.generate_script(preset_name)
            output_file = output_path / f"{preset_name}.jsx"
            output_file.write_text(jsx_code, encoding="utf-8")
            print(f"   ✅ {preset_name}.jsx")
            generated_count += 1
        except Exception as e:
            print(f"   ❌ {preset_name} - {e}")
            failed_count += 1

    print(f"\n📊 批量生成结果:")
    print(f"   成功: {generated_count}")
    print(f"   失败: {failed_count}")


def main():
    parser = argparse.ArgumentParser(
        description="预设系统命令行接口 - 管理和执行AE预设",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  py -3.12 scripts/preset_cli.py --list
  py -3.12 scripts/preset_cli.py --list --category text_animation
  py -3.12 scripts/preset_cli.py --search "赛博"
  py -3.12 scripts/preset_cli.py --execute cyberpunk_glitch_text
  py -3.12 scripts/preset_cli.py --chain "cyberpunk_glitch_text,cyberpunk_grade"
  py -3.12 scripts/preset_cli.py --combo cyberpunk_title_sequence
  py -3.12 scripts/preset_cli.py --info cyberpunk_glitch_text
  py -3.12 scripts/preset_cli.py --generate cyberpunk_glitch_text --output script.jsx
  py -3.12 scripts/preset_cli.py --batch --category text_animation --output-dir output/jsx
        """,
    )

    parser.add_argument("--list", action="store_true", help="列出所有预设分类")
    parser.add_argument("--category", help="按分类列出预设")
    parser.add_argument("--search", help="搜索预设")
    parser.add_argument("--execute", help="执行单个预设")
    parser.add_argument("--chain", help="执行预设链（逗号分隔）")
    parser.add_argument("--combo", help="执行预设组合")
    parser.add_argument("--info", help="显示预设详细信息")
    parser.add_argument("--generate", help="生成JSX脚本")
    parser.add_argument("--output", help="输出JSX文件路径")
    parser.add_argument("--batch", action="store_true", help="批量生成脚本")
    parser.add_argument("--output-dir", help="批量输出目录")
    parser.add_argument("--list-combos", action="store_true", help="列出预设组合")
    parser.add_argument("--combo-info", help="输出指定组合的预设列表和参数(JSON格式)")
    parser.add_argument("--param", action="append", help="参数覆盖（格式: key=value）")

    args = parser.parse_args()

    print_banner()

    preset_system = PresetSystem()
    executor = PresetExecutor(preset_system)
    library = PresetLibrary()
    initialize_default_combinations(library)

    params = {}
    if args.param:
        for p in args.param:
            if "=" in p:
                key, value = p.split("=", 1)
                try:
                    params[key] = float(value)
                except ValueError:
                    params[key] = value

    if args.list:
        list_presets(preset_system)
    elif args.batch and args.category:
        batch_generate(preset_system, args.category, args.output_dir or "output/jsx")
    elif args.category:
        list_category_presets(preset_system, args.category)
    elif args.search:
        search_presets(preset_system, args.search)
    elif args.execute:
        execute_preset(executor, args.execute, params)
    elif args.chain:
        preset_names = [p.strip() for p in args.chain.split(",")]
        execute_preset_chain(executor, preset_names, params)
    elif args.combo:
        execute_combination(executor, library, args.combo, params)
    elif args.info:
        show_preset_info(preset_system, args.info)
    elif args.generate:
        generate_script(preset_system, args.generate, args.output, params)
    elif args.batch and args.category:
        batch_generate(preset_system, args.category, args.output_dir or "output/jsx")
    elif args.list_combos:
        list_combinations(library)
    elif args.combo_info:
        combo = library.get_combination(args.combo_info)
        if not combo:
            print(json.dumps({"error": f"组合不存在: {args.combo_info}"}, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps({
            "name": combo.name,
            "description": combo.description,
            "presets": combo.presets,
            "parameters": combo.parameters or {},
        }, ensure_ascii=False))
    else:
        parser.print_help()
        print("\n❌ 请指定一个操作")


if __name__ == "__main__":
    main()
