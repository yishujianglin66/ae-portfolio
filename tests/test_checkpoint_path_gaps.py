"""
resume_from_checkpoint 路径安全校验未覆盖边缘情况测试
====================================================
覆盖缺口：
  缺口A: 前缀碰撞保护（output vs output_evil）
  缺口B: Path.is_relative_to AttributeError 兼容分支 fallback
  缺口C: 路径规范化异常处理（os.path.abspath 抛异常）
  缺口D: 目录被命名为 "xxxcheckpoint.json" 的边界
  缺口E: 空白字符和尾部斜杠路径 / 多余 . 组件路径
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ============================================================
# 导入方式：sys.path 加入项目根、web/、tools/ 目录
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
TOOLS_DIR = PROJECT_ROOT / "tools"

for _p in (str(PROJECT_ROOT), str(WEB_DIR), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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



# ====================================================================
# 辅助函数
# ====================================================================

def _build_server(output_dir: Path):
    """构建 IntegratorAPIServer 实例（不启动 HTTP）。"""
    from web.integrator_api import IntegratorAPIServer

    return IntegratorAPIServer(
        default_mode="auto",
        output_dir=str(output_dir),
        preset_file=None,
        config_file=None,
    )


def _make_request(checkpoint_path: str, preset_id: str = "test-preset"):
    """构造 CheckpointResumeRequest 对象。"""
    from web.integrator_api import CheckpointResumeRequest

    return CheckpointResumeRequest(
        checkpoint_path=checkpoint_path,
        preset_id=preset_id,
        input_params=None,
    )


# ====================================================================
# 缺口A: 前缀碰撞保护
# ====================================================================

class TestGapA_PrefixCollisionProtection:
    """
    缺口A: 当 output_dir = "D:\\output" 时，
    "D:\\output_evil\\job\\checkpoint.json" 的前缀是 output，
    allowed_root_with_sep 机制（L398-L402）必须防止这种前缀碰撞。
    """

    def test_allowed_root_without_tail_sep_gets_appended(self, tmp_path):
        """output 目录不带尾反斜杠 → allowed_root_with_sep 正确追加分隔符。

        直接通过代码内省 + 实际请求来验证：若 allowed_root 未加 sep，
        前缀碰撞路径会错误地通过；正确实现则应当拒绝。
        """
        # 构造 output 目录（不带尾分隔符）
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # 构造前缀碰撞目录：output_evil（名字以 output 开头，但不是子目录）
        evil_dir = tmp_path / "output_evil" / "job"
        evil_dir.mkdir(parents=True)
        fake_ckpt = evil_dir / "checkpoint.json"
        fake_ckpt.write_text("{}", encoding="utf-8")

        server = _build_server(output_dir)  # 注意 output_dir 是 Path，不带尾 sep

        # 尝试访问 output_evil 下的 checkpoint
        req = _make_request(str(fake_ckpt))

        with pytest.raises(Exception) as exc_info:
            server.resume_from_checkpoint(req)

        # 必须是 400（路径超出范围），不是 404（文件不存在）
        # 如果 allowed_root_with_sep 没加对，is_relative_to 也会正确拒绝，
        # 但这里我们验证的是：前缀碰撞路径确实被拒绝（任意方式）
        from fastapi import HTTPException

        assert isinstance(exc_info.value, HTTPException)
        assert exc_info.value.status_code == 400
        assert "超出允许的输出目录范围" in str(exc_info.value.detail) or \
               "路径" in str(exc_info.value.detail)

    def test_allowed_root_with_tail_sep_kept_unchanged(self, tmp_path):
        """output 目录带尾反斜杠 → allowed_root_with_sep 不重复追加。

        验证：即使显式传入带尾分隔符的 output_dir，前缀碰撞路径仍被拒绝。
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_dir_str = str(output_dir) + os.sep  # 带尾分隔符

        evil_dir = tmp_path / "output_evil" / "job"
        evil_dir.mkdir(parents=True)
        fake_ckpt = evil_dir / "checkpoint.json"
        fake_ckpt.write_text("{}", encoding="utf-8")

        from web.integrator_api import IntegratorAPIServer

        server = IntegratorAPIServer(
            default_mode="auto",
            output_dir=output_dir_str,
            preset_file=None,
            config_file=None,
        )

        req = _make_request(str(fake_ckpt))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            server.resume_from_checkpoint(req)

        assert exc_info.value.status_code == 400

    def test_prefix_collision_path_rejected(self, tmp_path):
        """
        核心场景：output_evil（前缀等于 output_dir 名）必须被拒绝。

        验证 allowed_root_with_sep 机制在 startswith fallback 下能
        正确区分 "D:\\output\\" 和 "D:\\output_evil\\"。
        """
        output_dir = tmp_path / "mydata"
        output_dir.mkdir()

        # 前缀碰撞：mydata_evil（前缀恰好是 mydata）
        evil_dir = tmp_path / "mydata_evil"
        evil_dir.mkdir()
        fake_ckpt = evil_dir / "checkpoint.json"
        fake_ckpt.write_text("{}", encoding="utf-8")

        server = _build_server(output_dir)
        req = _make_request(str(fake_ckpt))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            server.resume_from_checkpoint(req)

        # 无论走 is_relative_to 分支还是 startswith fallback 分支，
        # 都必须以 400 拒绝
        assert exc_info.value.status_code == 400
        detail = str(exc_info.value.detail)
        assert "超出允许的输出目录" in detail or "路径" in detail


# ====================================================================
# 缺口B: Path.is_relative_to AttributeError 兼容分支
# ====================================================================

class TestGapB_IsRelativeToFallback:
    """
    缺口B: L409-L414 的 Python 3.9 以下兼容 fallback 分支。
    通过 mock 让 Path.is_relative_to 触发 AttributeError，
    强制走 startswith(allowed_root_with_sep) 分支。
    """

    def test_legal_path_under_output_dir_not_blocked_by_fallback(self, tmp_path):
        """
        合法 checkpoint.json（在 output_dir 下）在 fallback 分支中
        不应被 400 拦截，最终因文件不存在返回 404。
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # 构造合法路径（output_dir 下的 job/checkpoint.json），但不创建文件
        legal_ckpt = output_dir / "job" / "checkpoint.json"

        server = _build_server(output_dir)
        req = _make_request(str(legal_ckpt))

        # Mock Path.is_relative_to → AttributeError，强制走 fallback
        def _no_is_relative_to(*args, **kwargs):
            raise AttributeError("patched: is_relative_to disabled")
        with patch.object(Path, "is_relative_to", _no_is_relative_to):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)

        # 在 fallback 分支中通过了子路径检查（不是 400 越界），
        # 但文件不存在，所以应当是 404
        assert exc_info.value.status_code == 404, (
            f"期望 404（文件不存在），实际 {exc_info.value.status_code}: {exc_info.value.detail}"
        )
        assert "不存在" in str(exc_info.value.detail)

    def test_outside_path_blocked_by_fallback(self, tmp_path):
        """
        output_dir 外的路径在 fallback 分支中必须被 400 拦截。
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # 完全不相关的外部路径
        outside_ckpt = tmp_path / "somewhere_else" / "checkpoint.json"
        outside_ckpt.parent.mkdir()
        outside_ckpt.write_text("{}", encoding="utf-8")  # 文件存在，但越界

        server = _build_server(output_dir)
        req = _make_request(str(outside_ckpt))

        # Mock Path.is_relative_to → AttributeError
        def _no_is_relative_to(*args, **kwargs):
            raise AttributeError("patched: is_relative_to disabled")
        with patch.object(Path, "is_relative_to", _no_is_relative_to):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)

        # 必须是 400（越界），不是 404
        assert exc_info.value.status_code == 400
        assert "超出允许的输出目录" in str(exc_info.value.detail)

    def test_fallback_via_attribute_error_side_effect(self, tmp_path):
        """
        用 side_effect 抛 AttributeError 的方式（而非 None）来触发
        except AttributeError 分支，确保 try/except 正确工作。
        """
        output_dir = tmp_path / "work"
        output_dir.mkdir()
        legal_ckpt = output_dir / "checkpoint.json"
        # 不创建文件，预期 404

        server = _build_server(output_dir)
        req = _make_request(str(legal_ckpt))

        def _attr_error_side_effect(*args, **kwargs):
            raise AttributeError("mock: is_relative_to not available")

        with patch.object(Path, "is_relative_to", side_effect=_attr_error_side_effect):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)

        # 通过 fallback（400 越界）→ 文件不存在 404
        assert exc_info.value.status_code == 404


# ====================================================================
# 缺口C: 路径规范化异常处理
# ====================================================================

class TestGapC_PathNormalizationException:
    """
    缺口C: L381-L387 try/except 捕获 os.path.abspath 异常。
    用 mock 让 os.path.abspath 抛异常，验证抛 HTTPException(400) 而不是崩溃。
    """

    def test_abspath_unicode_encode_error_becomes_400(self, tmp_path):
        """os.path.abspath 抛 UnicodeEncodeError → HTTPException(400)。"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        server = _build_server(output_dir)
        # 使用任意合法路径字符串，mock 会在 abspath 时炸掉
        req = _make_request(str(output_dir / "checkpoint.json"))

        def _raise_unicode(*args, **kwargs):
            raise UnicodeEncodeError("utf-8", b"\\xff\\xfe", 0, 2, "mock encoding error")

        with patch("os.path.abspath", side_effect=_raise_unicode):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)

        assert exc_info.value.status_code == 400
        assert "路径规范化失败" in str(exc_info.value.detail)

    def test_abspath_os_error_becomes_400(self, tmp_path):
        """os.path.abspath 抛 OSError → HTTPException(400)。"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        server = _build_server(output_dir)
        req = _make_request(str(output_dir / "checkpoint.json"))

        def _raise_os(*args, **kwargs):
            raise OSError(22, "mock os error: Invalid argument")

        with patch("os.path.abspath", side_effect=_raise_os):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)

        assert exc_info.value.status_code == 400
        assert "路径规范化失败" in str(exc_info.value.detail)

    def test_abspath_generic_exception_becomes_400(self, tmp_path):
        """os.path.abspath 抛通用 Exception → HTTPException(400)。

        因为 L383 用的是 `except Exception`，所以任何异常都要被吞成 400。
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        server = _build_server(output_dir)
        req = _make_request(str(output_dir / "checkpoint.json"))

        with patch("os.path.abspath", side_effect=RuntimeError("mock boom")):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)

        assert exc_info.value.status_code == 400


# ====================================================================
# 缺口D: 目录被命名为 "xxxcheckpoint.json" 的边界
# ====================================================================

class TestGapD_DirectoryNamedCheckpointJson:
    """
    缺口D: 构造路径 output_dir / "fakecheckpoint.json" / "checkpoint.json"
    其中 fakecheckpoint.json 是目录名（名字恰好含 checkpoint.json 后缀），
    最终路径组件也是 checkpoint.json，但它是一个目录而非文件。

    预期：安全校验1/2/3/4 通过 → 到 L426 is_file 返回 400 "不是文件"。
    """

    def _build_scenario(self, tmp_path: Path):
        """
        构造场景：
          <output>/fakecheckpoint.json/        ← 目录（名字伪装成 JSON 文件）
          <output>/fakecheckpoint.json/checkpoint.json  ← 这是一个目录（不是文件）
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # 伪装目录 fakecheckpoint.json
        fake_dir = output_dir / "fakecheckpoint.json"
        fake_dir.mkdir()

        # 再在里面建一个也叫 checkpoint.json 的目录
        ckpt_dir = fake_dir / "checkpoint.json"
        ckpt_dir.mkdir()  # 是目录，不是文件！

        return output_dir, ckpt_dir

    def test_directory_final_component_is_400_not_file(self, tmp_path):
        """最终路径 checkpoint.json 是目录 → 必须返回 400 '不是文件'。"""
        output_dir, ckpt_dir = self._build_scenario(tmp_path)

        server = _build_server(output_dir)
        req = _make_request(str(ckpt_dir))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            server.resume_from_checkpoint(req)

        # 应当是 is_file 检查失败（L426-L428），400 "不是文件"
        assert exc_info.value.status_code == 400, (
            f"期望 400（不是文件），实际 {exc_info.value.status_code}: {exc_info.value.detail}"
        )
        assert "不是文件" in str(exc_info.value.detail)

    def test_prefix_dir_name_with_checkpoint_still_passes_suffix_check(self, tmp_path):
        """
        确认：父目录名中包含 "checkpoint.json" 不会干扰
        normalized_path.endswith("checkpoint.json") 的后缀检查。

        只要最终 basename 是 checkpoint.json（即便它是目录），
        后缀校验 (L390) 也应通过。
        """
        output_dir, ckpt_dir = self._build_scenario(tmp_path)

        # normalized_path 应该是 <output>/fakecheckpoint.json/checkpoint.json
        normalized = os.path.abspath(str(ckpt_dir))
        assert normalized.endswith("checkpoint.json"), (
            f"后缀校验前提失效: {normalized} 不以 checkpoint.json 结尾"
        )
        # final component 必须是 checkpoint.json（是目录）
        assert os.path.basename(normalized) == "checkpoint.json"
        assert os.path.isdir(normalized)

        # 此时调用会因为 is_file 失败返回 400
        server = _build_server(output_dir)
        req = _make_request(str(ckpt_dir))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            server.resume_from_checkpoint(req)

        # 确认不是 400 "路径必须以 checkpoint.json 结尾"（即 L390 没误拦）
        detail = str(exc_info.value.detail)
        assert "路径必须以 checkpoint.json 结尾" not in detail
        # 确认是"不是文件"
        assert "不是文件" in detail


# ====================================================================
# 缺口E: 空白字符和尾部斜杠路径
# ====================================================================

class TestGapE_TrailingSlashesAndDotComponents:
    """
    缺口E:
      1. raw_path 尾部带多余反斜杠
      2. 包含多余 . 组件的路径（如 "././checkpoint.json"）
         — 包含 .. 才会被校验1拦截，所以 . 组件最终看 endswith 正常工作。
    """

    def test_trailing_backslash_does_not_break_suffix_check(self, tmp_path):
        """raw_path 尾部带多余反斜杠 → 规范化后仍然正确识别 checkpoint.json。

        注意：尾部反斜杠通常不会导致 endswith("checkpoint.json") 通过，
        但 abspath 规范化行为视系统而定。此测试验证该路径的行为是合理的
        （要么抛后缀错误 400，要么是越界 / 不存在错误），重点是**不能崩溃**。
        """
        output_dir = tmp_path / "output"
        job_dir = output_dir / "job"
        job_dir.mkdir(parents=True)
        real_ckpt = job_dir / "checkpoint.json"
        real_ckpt.write_text("{}", encoding="utf-8")

        # 在 checkpoint.json 后再追加一个反斜杠（注意是字符串层面追加）
        raw_path = str(real_ckpt) + os.sep
        server = _build_server(output_dir)
        req = _make_request(raw_path)

        from fastapi import HTTPException

        try:
            server.resume_from_checkpoint(req)
            # 如果没抛异常也 OK（某些平台 abspath 会去掉尾斜杠）
        except HTTPException as e:
            # 任一合理 HTTP 错误都可以接受，只要不是非 HTTPException 的崩溃
            assert e.status_code in (400, 404)

    def test_leading_and_multiple_dot_components_not_blocked_by_safety_1(self, tmp_path):
        """
        路径包含 . 组件（././checkpoint.json） — "." 组件不是 ".."，
        所以校验1不会拦截。验证 endswith("checkpoint.json") 能正常工作，
        最终通过路径检查后返回 404（文件不存在）或实际文件存在则走后续。
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        real_ckpt = output_dir / "checkpoint.json"
        real_ckpt.write_text("{}", encoding="utf-8")

        # 用 "." 组件拼装相对路径。注意：这是相对于 cwd 的，我们需要
        # 切换到 output_dir 让 "././checkpoint.json" 解析成真实文件路径
        raw_path = os.path.join(".", ".", "checkpoint.json")

        server = _build_server(output_dir)
        req = _make_request(raw_path)

        from fastapi import HTTPException

        # 切换 cwd 到 output_dir 再调用
        old_cwd = os.getcwd()
        try:
            os.chdir(str(output_dir))
            try:
                # 文件存在 + 是文件 + 在 output_dir 下 → 会继续执行到创建 integrator
                # 那一步。我们不关心后续（会因缺少 preset_file 等出错），只要
                # 不被 400 误拦就行。可能抛各种非 HTTPException，这里只确认非 400。
                server.resume_from_checkpoint(req)
            except HTTPException as e:
                # 如果被 400（路径校验）拦下来了，那就是 bug
                if e.status_code == 400:
                    detail = str(e.detail)
                    # 唯独不接受"路径包含非法 '..' 组件"这种误报
                    assert ".." not in detail or "非法 '..' 组件" not in detail, (
                        f"'.' 组件被误判为 '..' 组件！detail: {detail}"
                    )
        finally:
            os.chdir(old_cwd)

    def test_multiple_dot_components_normalize_correctly(self, tmp_path):
        """
        验证："././subdir/./checkpoint.json" 规范化后 endswith 正确，
        且 Path.is_relative_to 通过（合法场景）。
        """
        output_dir = tmp_path / "output"
        subdir = output_dir / "subdir"
        subdir.mkdir(parents=True)

        # 不创建文件，预期 404
        raw_path = os.path.join(".", ".", "subdir", ".", "checkpoint.json")

        server = _build_server(output_dir)
        req = _make_request(raw_path)

        from fastapi import HTTPException

        old_cwd = os.getcwd()
        try:
            os.chdir(str(output_dir))
            with pytest.raises(HTTPException) as exc_info:
                server.resume_from_checkpoint(req)
            # 只要路径规范化正确，它在 output_dir/subdir 下，所以通过校验4，
            # 再因不存在 → 404
            assert exc_info.value.status_code == 404, (
                f"期望 404，实际 {exc_info.value.status_code}: {exc_info.value.detail}"
            )
            assert "不存在" in str(exc_info.value.detail)
        finally:
            os.chdir(old_cwd)


# ====================================================================
# 直接运行入口
# ====================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

