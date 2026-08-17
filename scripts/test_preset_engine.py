#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预设执行引擎实战测试 - 验证所有分类的预设生成与执行流程"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 确保根目录 ae 包优先
ae_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ae")
if ae_root in sys.path:
    sys.path.remove(ae_root)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ae.preset_system import PresetSystem, PRESET_CATEGORIES
from ae.preset_executor import PresetExecutor, PresetLibrary, initialize_default_combinations


def main():
    ps = PresetSystem()
    executor = PresetExecutor(ps)
    library = PresetLibrary()
    initialize_default_combinations(library)

    print("=== 预设执行引擎实战测试 ===")
    print()

    # 1. 每个分类抽样1个预设执行 dry_run
    print("--- 1. 各分类抽样 dry_run 测试 ---")
    category_pass = 0
    category_fail = 0
    for cat in PRESET_CATEGORIES.keys():
        names = ps.list_presets(cat)
        if names:
            name = names[0]
            result = executor.execute_preset(name, ae_client=None)
            ok = result.get("success", False)
            jsx_len = len(result.get("jsx", ""))
            cat_name = PRESET_CATEGORIES[cat]["name"]
            status = "PASS" if ok else "FAIL"
            if ok:
                category_pass += 1
            else:
                category_fail += 1
            print(f"  [{status}] {cat_name}: {name} (JSX: {jsx_len} chars)")

    print(f"  分类通过: {category_pass}/{category_pass + category_fail}")
    print()

    # 2. 全量 dry_run 执行
    print("--- 2. 全量预设 dry_run 测试 ---")
    all_names = ps.list_presets()
    pass_count = 0
    fail_count = 0
    fail_list = []
    for name in all_names:
        result = executor.execute_preset(name, ae_client=None)
        if result.get("success"):
            pass_count += 1
        else:
            fail_count += 1
            fail_list.append(f"{name}: {result.get('error', 'unknown')}")

    print(f"  通过: {pass_count}/{len(all_names)}")
    print(f"  失败: {fail_count}")
    if fail_list:
        print("  失败详情:")
        for item in fail_list[:10]:
            print(f"    - {item}")
        if len(fail_list) > 10:
            print(f"    ... 还有 {len(fail_list) - 10} 个")
    print()

    # 3. 预设链测试
    print("--- 3. 预设链 dry_run 测试 ---")
    chain = ["slide_transition", "typewriter_effect", "cinematic_grade"]
    result = executor.execute_preset_chain(chain, ae_client=None)
    print(f"  链执行: {chain}")
    print(f"  总数: {result['total_presets']}, 成功: {result['success_count']}, 失败: {result['failed_count']}")
    for r in result["results"]:
        status = "PASS" if r.get("success") else "FAIL"
        print(f"    [{status}] {r.get('preset', '?')} - JSX: {len(r.get('jsx', ''))} chars")
    print()

    # 4. 预设组合测试
    print("--- 4. 预设组合 dry_run 测试 ---")
    for combo_name in library.list_combinations():
        combo = library.get_combination(combo_name)
        if combo:
            result = executor.execute_preset_chain(combo.presets, ae_client=None, shared_params=combo.parameters)
            all_ok = result["success_count"] == result["total_presets"]
            status = "PASS" if all_ok else "FAIL"
            print(f"  [{status}] {combo_name}: {combo.description}")
            print(f"    预设: {combo.presets}")
            print(f"    成功: {result['success_count']}/{result['total_presets']}")
    print()

    # 5. 搜索+执行测试
    print("--- 5. 搜索+执行 dry_run 测试 ---")
    keywords = ["赛博", "neon", "glitch", "转场", "调色", "文字", "MG", "3D", "木偶", "LUT"]
    for kw in keywords:
        results = ps.search_presets(kw)
        if results:
            name = results[0].name
            result = executor.execute_preset(name, ae_client=None)
            ok = result.get("success", False)
            jsx_len = len(result.get("jsx", ""))
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] 搜索\"{kw}\" -> {name} (JSX: {jsx_len} chars)")
        else:
            print(f"  [MISS] 搜索\"{kw}\" -> 无结果")
    print()

    # 6. 参数覆盖测试
    print("--- 6. 参数覆盖 dry_run 测试 ---")
    result = executor.execute_preset("slide_transition", ae_client=None, duration=1.2, direction="left")
    jsx = result.get("jsx", "")
    has_override = "1.2" in jsx and "left" in jsx
    status = "PASS" if has_override else "FAIL"
    print(f"  [{status}] slide_transition(duration=1.2, direction='left')")
    print(f"    JSX 包含覆盖值: {has_override}")

    # 布尔参数覆盖
    result2 = executor.execute_preset("chromatic_aberration", ae_client=None, animate=True)
    jsx2 = result2.get("jsx", "")
    has_true = "true" in jsx2 and "True" not in jsx2
    status2 = "PASS" if has_true else "FAIL"
    print(f"  [{status2}] chromatic_aberration(animate=True) -> JSX 中含 'true' 非 'True'")

    print()
    print("=== 实战测试完成 ===")

    # 汇总
    total_issues = fail_count + (0 if has_override else 1) + (0 if has_true else 1)
    if total_issues == 0:
        print("结论: 所有脚本可正常生成和输出，可进入下一阶段")
    else:
        print(f"结论: 发现 {total_issues} 个问题需要修复")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
