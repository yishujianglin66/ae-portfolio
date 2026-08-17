"""附加式 JSX 调用助手
========================

把 ae_additive_scripts/ 下的独立 JSX 脚本组装成可作为开源 AfterEffectsMCP
``execute-atom-script`` 工具 ``scriptContent`` 参数的完整 ExtendScript 字符串。

设计原则（附加式，不改开源源码）：
- 不修改开源 bridge（mcp-bridge-auto.jsx）与开源服务器（src/index.ts）
- 复用开源 ``execute-atom-script`` 工具：它会对 scriptContent 执行 eval()
- eval() 不解析 ExtendScript 的 #include 指令，因此本助手负责把
  ``#include "_lib/xxx.jsx"`` 依赖内联进脚本，使其自包含

约定：
- 每个 JSX 定义一个与文件同名的全局函数 ``<name>(args)``，返回 JSON 字符串
  （由 _lib/response_utils.jsx 的 buildSuccess/buildError 构建）
- 组装后的脚本末尾调用该函数，并把结果存入全局 ``$.global.__aeAdditiveResult``
  供后续 run-script 读取（可选）

用法：
    py -3.12 run_additive_jsx.py applyColorCorrection '{"compName":"Comp 1","layerIndex":1}'
    py -3.12 run_additive_jsx.py applyColorCorrection '{"compName":"Comp 1","layerIndex":1}' --out payload.jsx

输出：可直接作为 execute-atom-script 的 scriptContent。
"""
import os
import re
import sys
import json
import argparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(SCRIPTS_DIR, "_lib")

_INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"\s*;?\s*$', re.MULTILINE)
_FUNC_RE = re.compile(r'function\s+([A-Za-z_]\w*)\s*\(\s*args\s*\)')


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _inline_includes(source, base_dir, depth=0, seen=None):
    """递归把 #include "_lib/xxx.jsx" 替换为对应文件内容（内联）。

    ExtendScript 的 #include 在 eval() 模式下不生效，故需手动内联。
    ``seen`` 防止同一 lib 被重复内联（多个 JSX 共享同一 lib）。
    """
    if seen is None:
        seen = set()
    if depth > 5:
        return source

    def _replace(match):
        rel = match.group(1).replace("\\", "/")
        # 仅内联 _lib 下的依赖；其他路径保持原样
        inc_path = os.path.normpath(os.path.join(base_dir, rel))
        key = os.path.normcase(inc_path)
        if key in seen:
            return "/* [inlined once] " + rel + " */"
        if not os.path.isfile(inc_path):
            return "/* [include not found] " + rel + " */"
        seen.add(key)
        inc_src = _read(inc_path)
        # 递归处理 lib 内部的 include（相对 lib 所在目录）
        inc_src = _inline_includes(inc_src, os.path.dirname(inc_path), depth + 1, seen)
        return "\n/* ===== inlined: " + rel + " ===== */\n" + inc_src + "\n"

    return _INCLUDE_RE.sub(_replace, source)


def detect_function_name(source, jsx_name):
    """检测主函数名：优先与文件同名，否则取第一个 function(args) 定义。"""
    if re.search(r'function\s+' + re.escape(jsx_name) + r'\s*\(', source):
        return jsx_name
    m = _FUNC_RE.search(source)
    if m:
        return m.group(1)
    return jsx_name


def build_script_content(jsx_name, args_dict):
    """组装自包含的 scriptContent。"""
    jsx_file = os.path.join(SCRIPTS_DIR, jsx_name + ".jsx")
    if not os.path.isfile(jsx_file):
        raise FileNotFoundError("JSX 脚本不存在: " + jsx_file)

    raw = _read(jsx_file)
    inlined = _inline_includes(raw, SCRIPTS_DIR)
    fn_name = detect_function_name(inlined, jsx_name)
    args_json = json.dumps(args_dict, ensure_ascii=False)

    tail = (
        "\n/* ===== additive invocation ===== */\n"
        "var __additiveArgs = " + args_json + ";\n"
        "var __additiveResult = " + fn_name + "(__additiveArgs);\n"
        "try { $.global.__aeAdditiveResult = __additiveResult; } catch (e) {}\n"
        "try { $.write(__additiveResult); } catch (e) {}\n"
    )
    return inlined + tail, fn_name


def list_scripts():
    """列出可用的附加 JSX 脚本。"""
    items = []
    for f in sorted(os.listdir(SCRIPTS_DIR)):
        if f.endswith(".jsx"):
            items.append(f[:-4])
    return items


def main():
    parser = argparse.ArgumentParser(description="附加式 JSX 调用助手（输出 execute-atom-script 的 scriptContent）")
    parser.add_argument("jsx_name", nargs="?", help="JSX 脚本名（不含 .jsx），如 applyColorCorrection")
    parser.add_argument("args_json", nargs="?", default="{}", help='参数字符串（JSON），如 \'{"compName":"Comp 1"}\'')
    parser.add_argument("--out", help="可选：把 scriptContent 写入指定文件")
    parser.add_argument("--list", action="store_true", help="列出所有可用附加 JSX 脚本")
    cli = parser.parse_args()

    if cli.list or not cli.jsx_name:
        print("可用附加 JSX 脚本：")
        for name in list_scripts():
            print("  - " + name)
        return

    try:
        args_dict = json.loads(cli.args_json)
    except json.JSONDecodeError as e:
        print("参数 JSON 解析失败: " + str(e), file=sys.stderr)
        sys.exit(1)

    content, fn_name = build_script_content(cli.jsx_name, args_dict)
    print("/* 主函数: " + fn_name + " | 长度: " + str(len(content)) + " 字符 */", file=sys.stderr)

    if cli.out:
        with open(cli.out, "w", encoding="utf-8") as f:
            f.write(content)
        print("/* 已写入: " + cli.out + " */", file=sys.stderr)
    else:
        sys.stdout.write(content)


if __name__ == "__main__":
    main()
