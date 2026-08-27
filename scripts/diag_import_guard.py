"""导入系统污染诊断插件（pytest 插件，只读探测）。

用于定位「隔离运行正常、全量运行报 ModuleNotFoundError」这类跨测试导入污染。

用法:
    PYTHONPATH=scripts python -m pytest -q -p diag_import_guard
    # 只诊断部分用例时同样可用：... -p diag_import_guard tests/test_xxx.py

可选环境变量:
    AEK_DIAG_IMPORT_TARGETS  逗号分隔的模块名集合，默认覆盖 aiohttp 及其依赖链
    AEK_DIAG_IMPORT_OUT      报告输出路径，默认 tmp/diag_import_report.txt

设计约束（避免观测者效应，改动前务必维持）:
- 不 import 目标模块（否则会把 sys.modules 补回来，掩盖真实失败）
- 不 patch builtins.__import__（否则 tests/conftest.py 的泄漏哨兵会对每个用例告警）
- 只做只读探测 + 包装 PathFinder.find_spec（记录返回 None 的导入尝试及调用栈）
"""
import importlib.machinery as _mach
import importlib.util as _util
import os
import sys
import traceback

_DEFAULT_TARGETS = (
    "aiohttp,multidict,yarl,aiosignal,frozenlist,"
    "propcache,async_timeout,attr,attrs,idna"
)

PREFIX_ROOTS = {
    t.strip() for t in os.environ.get(
        "AEK_DIAG_IMPORT_TARGETS", _DEFAULT_TARGETS).split(",") if t.strip()
}
TARGET = sorted(PREFIX_ROOTS)[0] if PREFIX_ROOTS else "aiohttp"

_EVENTS = []      # 快照突变事件
_ATTEMPTS = []    # PathFinder 未命中的导入尝试
_SEEN_TAIL = set()


def _watched(fullname):
    root = fullname.split(".")[0]
    return root in PREFIX_ROOTS or root.rstrip("_") in PREFIX_ROOTS


def _site_paths():
    return [p for p in sys.path if p and "site-packages" in p.lower()]


def _snap():
    """对导入系统做一次只读快照。"""
    cached = TARGET in sys.modules
    spec_repr = "<cached>"
    if cached:
        mod = sys.modules[TARGET]
        origin = getattr(getattr(mod, "__spec__", None), "origin", None)
        spec_repr = f"{type(mod).__name__}:{origin}"
    else:
        try:
            sp = _util.find_spec(TARGET)
            spec_repr = "None" if sp is None else f"found:{sp.origin}"
        except Exception as exc:  # noqa: BLE001
            spec_repr = f"raises:{type(exc).__name__}:{exc}"
    none_importers = [
        p for p in sys.path
        if p and sys.path_importer_cache.get(p, "MISS") is None
    ]
    return {
        "cached": cached,
        "spec": spec_repr,
        "path": tuple(sys.path),
        "meta": tuple(type(f).__name__ for f in sys.meta_path),
        "pic_none": tuple(none_importers),
        "pic_size": len(sys.path_importer_cache),
        "hooks": len(sys.path_hooks),
        "site_in_path": len(_site_paths()),
    }


_PREV = None
_PREV_NODE = "<session-start>"


def _record(nodeid, kind, detail):
    _EVENTS.append(f"[{kind}] {nodeid}\n    {detail}")


def pytest_collection_finish(session):
    global _PREV
    _PREV = _snap()


def _fmt_diff(prev, cur):
    lines = []
    if prev["cached"] != cur["cached"]:
        lines.append(f"cached: {prev['cached']} -> {cur['cached']}")
    if prev["spec"] != cur["spec"]:
        lines.append(f"spec: {prev['spec']} -> {cur['spec']}")
    if prev["meta"] != cur["meta"]:
        lines.append(f"meta_path: {prev['meta']} -> {cur['meta']}")
    if prev["pic_none"] != cur["pic_none"]:
        lines.append(f"pic_none: {prev['pic_none']} -> {cur['pic_none']}")
    if prev["pic_size"] != cur["pic_size"]:
        lines.append(f"pic_size: {prev['pic_size']} -> {cur['pic_size']}")
    if prev["site_in_path"] != cur["site_in_path"]:
        lines.append(f"site_in_path: {prev['site_in_path']} -> {cur['site_in_path']}")
    if prev["path"] != cur["path"]:
        lost = [p for p in prev["path"] if p not in cur["path"]]
        gained = [p for p in cur["path"] if p not in prev["path"]]
        lines.append(f"sys.path lost={lost} gained={gained}")
    return "; ".join(lines)


def pytest_runtest_teardown(item, nextitem):
    global _PREV, _PREV_NODE
    cur = _snap()
    if _PREV is not None:
        detail = _fmt_diff(_PREV, cur)
        if detail:
            _record(_PREV_NODE, "SNAPSHOT", detail)
    _PREV = cur
    _PREV_NODE = nextitem.nodeid if nextitem else "<session-end>"


_orig_find_spec = _mach.PathFinder.find_spec.__func__  # 裸函数，首参为 cls


def _find_spec_wrapper(cls, fullname, path=None, target=None):
    spec = _orig_find_spec(cls, fullname, path, target)
    if spec is None and _watched(fullname):
        tail = traceback.format_stack()[-6:-1]
        if any("diag_import_guard" in line for line in tail):
            return spec  # 本插件自身只读探测发起的查找，不算真实导入失败
        key = (fullname, tuple(t.strip() for t in tail[-2:]))
        if key not in _SEEN_TAIL:
            _SEEN_TAIL.add(key)
            _ATTEMPTS.append(
                f"MISS {fullname}\n  search_path={path if path is not None else 'sys.path'}"
                f"\n  cwd={os.getcwd()}\n  stack:\n" + "".join(tail)
            )
    return spec


_mach.PathFinder.find_spec = classmethod(_find_spec_wrapper)


def pytest_sessionfinish(session, exitstatus):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.environ.get("AEK_DIAG_IMPORT_OUT") or os.path.join(
        repo_root, "tmp", "diag_import_report.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("=== 导入系统快照突变事件 ===\n")
        fh.write("\n".join(_EVENTS) if _EVENTS else "(无突变)\n")
        fh.write("\n\n=== PathFinder 未命中的被监控导入尝试 ===\n")
        fh.write("\n---\n".join(_ATTEMPTS) if _ATTEMPTS else "(无未命中)\n")
        fh.write(f"\n\n最终快照: {_PREV}\n")
    print(f"\n[diag] 报告已写出: {out} "
          f"(突变 {len(_EVENTS)} 条, 未命中 {len(_ATTEMPTS)} 条)")
