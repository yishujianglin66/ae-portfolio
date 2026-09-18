#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 创意规划引擎命令行接口

用法:
    py -3.12 scripts/creative_planner_cli.py "创意描述"
    py -3.12 scripts/creative_planner_cli.py --list
    py -3.12 scripts/creative_planner_cli.py --analyze "创意描述"
    py -3.12 scripts/creative_planner_cli.py --execute "创意描述"
"""

import argparse
import json
import sys
from pathlib import Path

# 添加项目根目录到 PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from ae.ai_creative_planner import AICreativePlanner


def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║              AI 创意规划引擎 (Creative Planner)              ║
║                    Version 1.0.0                            ║
║  将自然语言描述转换为结构化任务图，自动执行到 AE             ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def list_patterns(planner: AICreativePlanner):
    """列出所有可用的创意模式"""
    patterns = planner.list_available_patterns()

    print("\n📋 可用创意模式:")
    print("-" * 60)

    categories = {
        "文字动画": ["text_reveal", "text_typewriter", "text_explode", "text_wave"],
        "风格模板": ["style_cyberpunk", "style_hologram", "style_ink", "style_fire_ice", "style_neon"],
        "视频类型": ["video_opening", "video_ending", "video_music_visualization"],
    }

    for category, pattern_names in categories.items():
        print(f"\n🎨 {category}:")
        for pattern in patterns:
            if pattern["name"] in pattern_names:
                keywords = ", ".join(pattern["keywords"])
                print(f"  • {pattern['name']}")
                print(f"    描述: {pattern['description']}")
                print(f"    关键词: {keywords}")


def analyze_description(planner: AICreativePlanner, description: str):
    """分析创意描述"""
    print(f"\n🔍 分析创意描述: {description}")
    print("-" * 60)

    result = planner.parse_creative_description(description)

    analysis = result.get("analysis", {})
    task_graph = result.get("task_graph", {})

    print("\n📊 分析结果:")
    print(f"  • 置信度: {analysis.get('confidence', 0) * 100:.0f}%")
    print(f"  • 来源: {analysis.get('source', 'unknown')}")
    print(f"  • 匹配模式: {', '.join(analysis.get('patterns', []))}")
    print(f"  • 风格: {', '.join(analysis.get('styles', []))}")
    print(f"  • 动画: {', '.join(analysis.get('animations', []))}")
    print(f"  • 关键词: {', '.join(analysis.get('keywords', []))}")

    params = analysis.get("parameters", {})
    if params:
        print("\n⚙️ 提取参数:")
        for key, value in params.items():
            print(f"  • {key}: {value}")

    print("\n📋 任务图:")
    print(f"  • 项目名称: {task_graph.get('project')}")
    print(f"  • 时长: {task_graph.get('duration')} 秒")
    print(f"  • 创意模式: {task_graph.get('pattern')}")

    tasks = task_graph.get("tasks", [])
    print(f"\n  🎯 任务序列 ({len(tasks)} 个任务):")
    for i, task in enumerate(tasks, 1):
        print(f"    {i}. [{task.get('id')}] {task.get('name')}")
        task_params = task.get("params", {})
        if task_params:
            for p_key, p_value in task_params.items():
                if isinstance(p_value, dict):
                    p_value = json.dumps(p_value, ensure_ascii=False)
                print(f"       - {p_key}: {p_value}")

    # 保存任务图到文件
    output_file = Path("creative_task_graph.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(task_graph, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 任务图已保存到: {output_file}")


def execute_description(planner: AICreativePlanner, description: str, optimize: bool = False):
    """生成并执行创意描述"""
    print(f"\n🚀 生成并执行创意: {description}")
    print("-" * 60)

    result = planner.generate_and_execute(description, ae_client=None, optimize=optimize)

    analysis = result.get("analysis", {})
    task_graph = result.get("task_graph", {})
    execution = result.get("execution", {})

    print("\n📊 分析结果:")
    print(f"  • 置信度: {analysis.get('confidence', 0) * 100:.0f}%")
    print(f"  • 匹配模式: {', '.join(analysis.get('patterns', []))}")

    print("\n📋 任务图:")
    print(f"  • 项目名称: {task_graph.get('project')}")
    print(f"  • 时长: {task_graph.get('duration')} 秒")

    print("\n✅ 执行结果:")
    print(f"  • 总任务: {execution.get('total_tasks')}")
    print(f"  • 成功: {execution.get('success_count')}")
    print(f"  • 总耗时: {result.get('total_time')} 秒")

    results = execution.get("results", [])
    print("\n  📝 任务详情:")
    for task_result in results:
        status = "✅" if task_result.get("success") else "❌"
        task_id = task_result.get("task_id")
        script = task_result.get("script")
        print(f"    {status} {task_id} - {script}")
        if not task_result.get("success"):
            print(f"       错误: {task_result.get('error')}")

    # 保存完整结果
    output_file = Path("creative_execution_result.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 执行结果已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="AI 创意规划引擎 - 将自然语言描述转换为 AE 任务图",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  py -3.12 scripts/creative_planner_cli.py "赛博朋克风格文字浮现"
  py -3.12 scripts/creative_planner_cli.py --list
  py -3.12 scripts/creative_planner_cli.py --analyze "水墨风格打字机效果"
  py -3.12 scripts/creative_planner_cli.py --execute "霓虹发光片头"
        """,
    )

    parser.add_argument(
        "description",
        nargs="?",
        help="创意描述（自然语言）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的创意模式",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="仅分析创意描述，不执行",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="生成并执行任务图",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="使用 LLM 优化参数（需要配置 LLM API）",
    )
    parser.add_argument(
        "--api-url",
        help="LLM API 地址（或设置环境变量 LLM_API_URL）",
    )
    parser.add_argument(
        "--api-key",
        help="LLM API Key（或设置环境变量 LLM_API_KEY）",
    )
    parser.add_argument(
        "--model",
        default="deepseek",
        help="LLM 模型名称（默认: deepseek）",
    )

    args = parser.parse_args()

    print_banner()

    # 创建规划器实例
    planner = AICreativePlanner(
        llm_api_url=args.api_url,
        llm_api_key=args.api_key,
        model=args.model,
    )

    if args.list:
        list_patterns(planner)
        return

    if not args.description:
        parser.print_help()
        print("\n❌ 请提供创意描述或使用 --list 查看可用模式")
        return

    if args.analyze:
        analyze_description(planner, args.description)
    elif args.execute:
        execute_description(planner, args.description, optimize=args.optimize)
    else:
        # 默认模式：分析 + 显示任务图
        analyze_description(planner, args.description)


if __name__ == "__main__":
    main()
