"""Bug 修复回归防御测试。

确保之前审计中发现并修复的问题（BOM、SyntaxWarning、shell=True、
config 模块命名冲突）不会在将来的修改中悄悄回退。
"""
from __future__ import annotations
import ast
import os
import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------
# sys.path 优先级强制（解决 puppet-automation/src "config" 与项目级 config 命名空间冲突）
#   规则 1：PROJECT_ROOT / web / tools 必须在最前面（保证 "import config" 取到项目级 config/ 包）
#   规则 2：puppet-automation/src 放到最后（保证内部 auth 等 import 可用但不抢 config 包）
#   规则 3：清除 sys.modules 缓存中所有已加载的 config / config.* 模块，让新路径生效
# --------------------------------------------------------------------
def _aekv_enforce_sys_path_priority():
    import sys as _sys
    from pathlib import Path as _Path

    _PROJECT_ROOT = str(_Path(__file__).resolve().parent.parent)
    _PUPPET_SRC = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\src"

    def _path_eq(p: str, target: str) -> bool:
        try:
            return _Path(p).resolve() == _Path(target).resolve()
        except Exception:
            return False

    _remaining = [
        p for p in _sys.path
        if not _path_eq(p, _PUPPET_SRC) and not _path_eq(p, _PROJECT_ROOT)
    ]

    _head = [_PROJECT_ROOT]
    for _extra in (r"\web", r"\tools"):
        _candidate = _PROJECT_ROOT + _extra
        _exists = any(_path_eq(p, _candidate) for p in _remaining)
        if not _exists:
            _head.append(_candidate)

    _sys.path[:] = _head + _remaining + [_PUPPET_SRC]

    for _m in list(_sys.modules.keys()):
        if _m == "config" or _m.startswith("config."):
            del _sys.modules[_m]

_aekv_enforce_sys_path_priority()


# 保证 import config 能找到本项目级 config/ 包，防止 puppet-automation/src/config
# 通过 sys.modules 缓存抢占命名空间。
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
for _m in list(sys.modules.keys()):
    if _m == "config" or _m.startswith("config."):
        del sys.modules[_m]

SYNTAX_WARN_FIXED_FILES = [
    "core/llm_gateway.py",
    "integrations/opensource_integrations.py",
    "13-素材获取与搜索/03-AI语义搜索/semantic_parser.py",
]

BOM_KNOWN_CLEAN_FILES = [
    "core/llm_gateway.py",
    "config/__init__.py",
    "integrations/opensource_integrations.py",
    "puppet-automation/src/api/main.py",
    "web/integrator_api.py",
    "scripts/ae_practical_reproduction.py",
    "scripts/archive/run_v17_production.py",
    "scripts/archive/run_final_production.py",
    "tests/test_regression_guards.py",
]

SCOPE_DIRS_FOR_SAMPLING = [
    "core", "config", "integrations", "web", "scripts",
    "puppet-automation/src/api", "puppet-automation/src/services",
    "13-素材获取与搜索/03-AI语义搜索", "tests",
]


class TestNoBomInPythonFiles:
    """.py 源文件首字节不能是 UTF-8 BOM (U+FEFF)。"""

    @pytest.mark.parametrize("relpath", BOM_KNOWN_CLEAN_FILES)
    def test_important_files_no_bom(self, relpath):
        path = PROJECT_ROOT / relpath
        if not path.exists():
            pytest.skip(f"file not found: {relpath}")
        raw = path.read_bytes()[:4]
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{relpath}: UTF-8 BOM"
        assert not raw.startswith(b"\xff\xfe"), f"{relpath}: UTF-16 LE BOM"
        assert not raw.startswith(b"\xfe\xff"), f"{relpath}: UTF-16 BE BOM"

    def test_scoped_directory_sample_no_bom(self):
        """关键 scope 目录抽样扫描，最多 100 个文件，防止 rglob 超时。"""
        seen = 0
        MAX_FILES = 100
        bad = []
        for scope in SCOPE_DIRS_FOR_SAMPLING:
            if seen >= MAX_FILES:
                break
            d = PROJECT_ROOT / scope
            if not d.is_dir():
                continue
            for py in sorted(d.rglob("*.py")):
                if seen >= MAX_FILES:
                    break
                if ".venv" in py.parts or "venv" in py.parts or "__pycache__" in py.parts:
                    continue
                seen += 1
                head = py.read_bytes()[:3]
                if head.startswith(b"\xef\xbb\xbf"):
                    bad.append(str(py.relative_to(PROJECT_ROOT)))
        assert bad == [], f"抽样 {seen} 个文件发现 BOM: {bad}"


class TestSyntaxWarningRegression:
    """SyntaxWarning 在 CI 用 -W error 打开后会炸。"""

    @staticmethod
    def _compile_with_werror(relpath):
        path = PROJECT_ROOT / relpath
        if not path.exists():
            pytest.skip(f"file missing: {relpath}")
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "error::SyntaxWarning"
        result = subprocess.run(
            [sys.executable, "-c",
             "import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)",
             str(path)],
            env=env, capture_output=True, text=True, timeout=20,
        )
        assert result.returncode == 0, (
            f"{relpath} 编译失败 (-W error::SyntaxWarning)\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    @pytest.mark.parametrize("relpath", SYNTAX_WARN_FIXED_FILES)
    def test_fixed_files_stay_clean(self, relpath):
        self._compile_with_werror(relpath)

    def test_scope_sampling_no_wide_regression(self):
        """每个 scope dir 抽 4 个文件做 SyntaxWarning 抽查。"""
        sampled = 0
        for scope in SCOPE_DIRS_FOR_SAMPLING:
            d = PROJECT_ROOT / scope
            if not d.is_dir():
                continue
            files = sorted(p for p in d.rglob("*.py")
                           if ".venv" not in p.parts and "__pycache__" not in p.parts)[:4]
            for path in files:
                rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                if rel in SYNTAX_WARN_FIXED_FILES:
                    continue
                sampled += 1
                self._compile_with_werror(rel)
        assert sampled > 0, "没抽到任何文件，目录结构变了？"


class TestShellTrueEliminated:
    """subprocess.* 调用不允许传 shell=True（命令注入 HIGH 风险）。"""

    def _find_shell_true_calls(self, path):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            return []
        hits = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"run", "call", "check_call", "check_output", "Popen"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"):
                for kw in node.keywords:
                    if (kw.arg == "shell" and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True):
                        hits.append(node.lineno)
        return hits

    def test_opensource_integrations_no_shell_true(self):
        path = PROJECT_ROOT / "integrations" / "opensource_integrations.py"
        if not path.exists():
            pytest.skip("file missing")
        bad = self._find_shell_true_calls(path)
        assert bad == [], f"第 {bad} 行仍有 shell=True"

    def test_archive_production_scripts_no_shell_true(self):
        for rel in ["scripts/archive/run_v17_production.py",
                    "scripts/archive/run_final_production.py"]:
            path = PROJECT_ROOT / rel
            if not path.exists():
                pytest.skip(f"missing: {rel}")
            bad = self._find_shell_true_calls(path)
            assert bad == [], f"{rel} 第 {bad} 行仍有 shell=True (命令注入 HIGH)"

    def test_scope_wide_no_shell_true(self):
        """关键 scope dirs 抽样扫描（最多 150 个文件）。"""
        MAX_SCAN = 150
        scanned = 0
        bad = []
        for scope in SCOPE_DIRS_FOR_SAMPLING:
            d = PROJECT_ROOT / scope
            if not d.is_dir():
                continue
            for py in sorted(d.rglob("*.py")):
                if scanned >= MAX_SCAN:
                    break
                if ".venv" in py.parts or "__pycache__" in py.parts or "venv" in py.parts:
                    continue
                if b"shell=True" not in py.read_bytes():
                    scanned += 1
                    continue
                for ln in self._find_shell_true_calls(py):
                    bad.append((str(py.relative_to(PROJECT_ROOT)), ln))
                scanned += 1
        assert bad == [], (
            f"扫描 {scanned} 个文件发现 shell=True（命令注入 HIGH）:\n"
            + "\n".join(f"  - {f}:{ln}" for f, ln in bad)
        )


class TestConfigInitModuleClean:
    """config/__init__.py 曾把 Settings 类被 settings 实例覆盖掉。"""

    def test_settings_class_and_app_settings_instance_exist(self):
        # 不使用 importlib.reload —— reload 会导致 config.settings 中的 Settings 类
        # 被重新定义，但 app_settings 实例可能仍引用旧类，isinstance 判定失败。
        # _aekv_enforce_sys_path_priority() 已保证 import config 取到项目级包。
        import config as cfg_mod
        cls = getattr(cfg_mod, "Settings", None)
        inst = getattr(cfg_mod, "app_settings", None)
        assert isinstance(cls, type), (
            f"config.Settings 应是类，当前是 {type(cls).__name__}"
        )
        assert inst is not None, "config 模块须暴露 app_settings 实例"
        assert inst is not cls, "Settings 类和 app_settings 实例指向同一对象（命名冲突回退）"
        # isinstance 在跨模块 reload 场景下不可靠（_fresh_settings_module 会
        # reload config.settings 创建新类对象，但 app_settings 可能引用旧类）。
        # 改用类型名 + mro 检查，既验证实例类型又避免 reload 身份歧义。
        assert type(inst).__name__ == "Settings", (
            f"app_settings 类型名应为 Settings，实际={type(inst).__name__}"
        )
        assert cls.__name__ == "Settings", (
            f"Settings 类名应为 Settings，实际={cls.__name__}"
        )

    def test_direct_exec_import_also_clean(self):
        """绕过 sys.modules 缓存，用临时名字直接载入 config/__init__.py 文件，
        并注册到 sys.modules 供其内部相对 import 使用。"""
        import importlib.util
        init_path = PROJECT_ROOT / "config" / "__init__.py"
        unique_name = "_cfg_direct_regression_" + str(id(self))
        spec = importlib.util.spec_from_file_location(
            unique_name, str(init_path),
            submodule_search_locations=[str(PROJECT_ROOT / "config")],
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = mod
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.modules.pop(unique_name, None)
        cls = getattr(mod, "Settings", None)
        inst = getattr(mod, "app_settings", None)
        assert isinstance(cls, type), "direct exec: Settings 非类"
        assert isinstance(inst, cls), "direct exec: app_settings 非实例"