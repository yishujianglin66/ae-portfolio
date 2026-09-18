"""
AE MCP 工具验证套件 - 命令行入口
================================

提供简洁的 CLI 入口来运行 AE MCP 工具真实环境验证。

使用示例：
    # 运行所有分类的验证
    python ae/run_mcp_validation.py --all

    # 仅运行核心 (A 级) 工具
    python ae/run_mcp_validation.py --category core

    # 验证单个工具
    python ae/run_mcp_validation.py --tool create_composition

    # 输出 HTML 报告到指定目录
    python ae/run_mcp_validation.py --all --report html --output reports/

    # 强制使用真实 AE 客户端（无 AE 时报错）
    python ae/run_mcp_validation.py --all --real-ae
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

# 路径调整：允许脚本以 python ae/run_mcp_validation.py 方式直接运行
_THIS = Path(__file__).resolve()
_PROJECT_ROOT = _THIS.parent.parent
for _p in (str(_THIS.parent), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ae.tests.test_mcp_tools_validation import (  # noqa: E402
    CATEGORY_DEFINITIONS,
    CATEGORY_DISPLAY_NAMES,
    MCPToolValidationSuite,
    ToolValidationResult,
    ToolValidator,
    ValidationReport,
)


def setup_logging(verbose: bool) -> None:
    """配置日志。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    cats = ",".join(CATEGORY_DEFINITIONS.keys())
    parser = argparse.ArgumentParser(
        prog="ae-mcp-validation",
        description="AE MCP 工具真实环境验证 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
可用分类: {cats}

示例:
  %(prog)s --all                       # 验证所有工具
  %(prog)s --category core             # 仅 A 级工具
  %(prog)s --category core,important   # A + B 级
  %(prog)s --tool create_composition   # 单个工具
  %(prog)s --all --report html         # 输出 HTML 报告
  %(prog)s --all --real-ae             # 强制使用真实 AE
        """,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="运行所有分类的验证（A + B + C）",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        help=f"运行指定分类，可选 {cats}，多个用逗号分隔",
    )
    parser.add_argument(
        "--tool",
        "-t",
        type=str,
        help="仅验证单个工具（按 AEMCPClient 方法名）",
    )
    parser.add_argument(
        "--report",
        "-r",
        type=str,
        choices=["text", "json", "markdown", "html", "all"],
        default="text",
        help="报告输出格式 (默认: text，仅终端)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="reports/mcp_validation",
        help="报告输出目录 (默认: reports/mcp_validation)",
    )
    parser.add_argument(
        "--bridge-dir",
        type=str,
        default=None,
        help="Bridge 通信目录（仅真实环境生效）",
    )
    parser.add_argument(
        "--real-ae",
        action="store_true",
        help="强制使用真实 AE 客户端（无 AE 时报错）",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="列出所有可用工具",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出 (DEBUG 日志)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="静默模式（仅打印最终报告）",
    )
    return parser.parse_args()


def list_all_tools() -> None:
    """列出所有可用工具。"""
    print("\n可用 MCP 工具列表：\n")
    for cat, validators in CATEGORY_DEFINITIONS.items():
        print(f"  [{cat}] {CATEGORY_DISPLAY_NAMES.get(cat, cat)}")
        for cls in validators:
            print(f"    - {cls.tool_name:<30} {cls.description}")
        print()
    print(f"总计: {sum(len(v) for v in CATEGORY_DEFINITIONS.values())} 个工具\n")


def _print_text_report(report: ValidationReport) -> None:
    """打印文本报告到终端。"""
    print()
    print("=" * 70)
    print("  AE MCP 工具验证报告")
    print("=" * 70)
    print(f"  测试环境:       {report.environment}")
    print(f"  AE 版本:        {report.ae_version}")
    print(f"  MCP 版本:       {report.mcp_server_version}")
    print(f"  开始时间:       {report.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  结束时间:       {report.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    duration = (report.end_time - report.start_time).total_seconds()
    print(f"  总耗时:         {duration:.2f}s")
    print()
    print(f"  总工具数:       {report.total_tools}")
    print(f"  ✅ 通过:         {report.passed}")
    print(f"  ❌ 失败:         {report.failed}")
    print(f"  ⏭️  跳过:         {report.skipped}")
    print(f"  ⚠️  错误:         {report.errors}")
    print(f"  通过率:         {report.pass_rate:.1f}%")
    print(f"  平均延迟:       {report.avg_latency_ms:.1f}ms")
    print(f"  P95 延迟:       {report.p95_latency_ms:.1f}ms")
    print("=" * 70)

    if report.category_stats:
        print("\n分类统计：")
        print("-" * 70)
        print(f"  {'分类':<12} {'总数':>5} {'通过':>5} {'失败':>5} {'跳过':>5} {'错误':>5} {'通过率':>8}")
        for cs in report.category_stats:
            print(
                f"  {cs.category:<12} {cs.total:>5} {cs.passed:>5} {cs.failed:>5} "
                f"{cs.skipped:>5} {cs.errored:>5} {cs.pass_rate:>7.1f}%"
            )
        print("-" * 70)

    # 详细结果
    print("\n详细结果：")
    print("-" * 70)
    for r in report.results:
        msg = f"  {r.status_emoji} [{r.status:<5}] {r.tool_name:<28} {r.latency_ms:>7.1f}ms"
        if r.error_message:
            msg += f"  ⚠ {r.error_message[:40]}"
        print(msg)
    print("-" * 70)

    # 总结
    print()
    if report.pass_rate >= 95:
        print("  🎉 整体可用性极佳！")
    elif report.pass_rate >= 80:
        print("  ✅ 整体可用性良好")
    elif report.pass_rate >= 60:
        print("  ⚠️  可用性中等，需要优化")
    else:
        print("  ❌ 可用性较差，需要重点修复")


async def run_async(args: argparse.Namespace) -> int:
    """异步运行验证并返回退出码。"""
    suite = MCPToolValidationSuite(
        bridge_dir=args.bridge_dir,
        use_real_ae=args.real_ae,
        categories=_parse_categories(args),
    )

    await suite.setup_ae_environment()

    if args.tool:
        # 单工具模式
        result = await suite.validate_tool(args.tool)
        # 构造临时 report
        report = ValidationReport(
            total_tools=1,
            passed=1 if result.status == "pass" else 0,
            failed=1 if result.status in ("fail", "error") else 0,
            skipped=1 if result.status == "skip" else 0,
            errors=1 if result.status == "error" else 0,
            pass_rate=100.0 if result.status == "pass" else 0.0,
            results=[result],
            start_time=result.timestamp,
            end_time=datetime_safe_now(),
            environment=suite._environment,
            ae_version=suite._ae_version,
            mcp_server_version=suite._mcp_server_version,
        )
        suite.report = report
        _emit_report(suite, args)
        return 0 if result.status == "pass" else 1

    # 全量 / 分类模式
    report = await suite.run_all()
    _emit_report(suite, args)
    return 0 if report.pass_rate >= 80 else 1


def datetime_safe_now():
    """安全获取当前时间，便于测试 monkeypatch。"""
    from datetime import datetime
    return datetime.now()


def _parse_categories(args: argparse.Namespace) -> list[str] | None:
    """根据 args 决定运行的分类列表。"""
    if args.all:
        return list(CATEGORY_DEFINITIONS.keys())
    if args.category:
        cats = [c.strip() for c in args.category.split(",") if c.strip()]
        # 校验
        unknown = [c for c in cats if c not in CATEGORY_DEFINITIONS]
        if unknown:
            print(f"❌ 未知分类: {unknown}")
            print(f"   可用: {list(CATEGORY_DEFINITIONS.keys())}")
            sys.exit(2)
        return cats
    # 默认：所有分类（与 --all 等价）
    return list(CATEGORY_DEFINITIONS.keys())


def _emit_report(suite: MCPToolValidationSuite, args: argparse.Namespace) -> None:
    """根据 args 输出报告。"""
    if args.quiet:
        # 静默模式：只输出报告
        pass
    fmt = args.report

    if fmt in ("text", "all"):
        if not args.quiet:
            _print_text_report(suite.report)

    if fmt in ("json", "all"):
        path = Path(args.output)
        path.mkdir(parents=True, exist_ok=True)
        p = path / "validation.json"
        p.write_text(
            json.dumps(suite.report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"\n📄 JSON 报告: {p}")

    if fmt in ("markdown", "all"):
        path = Path(args.output)
        path.mkdir(parents=True, exist_ok=True)
        p = path / "validation.md"
        p.write_text(suite.generate_markdown_report(), encoding="utf-8")
        if not args.quiet:
            print(f"📄 Markdown 报告: {p}")

    if fmt in ("html", "all"):
        path = Path(args.output)
        path.mkdir(parents=True, exist_ok=True)
        p = path / "validation.html"
        p.write_text(suite.generate_html_report(), encoding="utf-8")
        if not args.quiet:
            print(f"📄 HTML 报告: {p}")

    if fmt == "all" and not args.quiet:
        print(f"\n✅ 所有报告已保存到: {args.output}")


def main() -> int:
    """CLI 入口函数。"""
    args = parse_args()
    setup_logging(verbose=args.verbose and not args.quiet)

    if args.list:
        list_all_tools()
        return 0

    try:
        return asyncio.run(run_async(args))
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        return 130
    except Exception as e:  # noqa: BLE001
        logging.exception("验证运行失败")
        print(f"\n❌ 错误: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
