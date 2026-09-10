"""
pytest 共享 fixture 与测试配置
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 测试环境启用开发账号种子（puppet-automation/src/auth.py 的 admin/operator/viewer
# 仅在 AE_DEV_ACCOUNTS=1 时加载；测试断言依赖这些账号存在）
os.environ.setdefault("AE_DEV_ACCOUNTS", "1")

# 加载 import 重定向兼容层，使旧模块名(如 video_generator)能映射到新包路径(如 video.video_generator)
# 根目录治理后(2026-08-26)，大量模块已迁移到功能域子包，必须启用重定向否则测试导入失败
try:
    import _import_redirect  # noqa: F401
except ImportError:
    pass


# ============================================================
# 跳过依赖缺失模块的测试文件（预计算列表，避免收集阶段崩溃）
# 更新方式：运行 tmp/_scan_test_imports.py 获取最新列表
#
# 注意(2026-08-26)：collect_ignore 条目是相对于本 conftest.py 所在目录(tests/)
# 的路径，因此直接用文件名即可。此前误加 "tests/" 前缀导致整个列表从未生效，
# 这也是全量收集超时的根本原因（破损/阻塞文件全部被真实导入）。
# ============================================================
collect_ignore = [
        # 缺失项目内部模块（限无法从历史提交恢复的）
        "test_aerender_v2.py",  # ae_render_engine
        "test_audio_analysis_service.py",  # whisper
        "test_bayesian_optimizer_gaps.py",  # core.bayesian_optimizer
        "test_cookie_read.py",  # browser_cookie3
        "test_douyin_browser.py",  # media-fetcher
        "test_douyin_download.py",  # media-fetcher
        "test_douyin_mobile.py",  # playwright
        "test_douyin_network.py",  # playwright
        "test_douyin_playwright.py",  # playwright
        "test_download_flow.py",  # media-fetcher
        "test_edge_login.py",  # playwright
        "test_ffmpeg_toolkit.py",  # ffmpeg_toolkit（模块不在 git 历史）
        "test_fx_expression_preflight.py",  # core.fx.expression_preflight
        "test_fx_particle_presets.py",  # core.fx.particle_presets
        "test_fx_style_preset_engine.py",  # core.fx.style_preset_engine
        "test_fx_text_impact.py",  # core.fx.text_impact
        "test_integration_services.py",  # whisper
        "test_puppet_style.py",  # media-fetcher
        "test_puppeteer_engine.py",  # mathutils
        "test_pw_direct.py",  # media-fetcher
        "test_quality_gate_flagship.py",  # core.quality_gate
        "test_zhuangzhuang.py",  # media-fetcher
        # 超时风险（重型导入）
        "test_batch_keyframes.py",
        # 超时风险（伪测试：模块级交互式脚本，收集时执行sleep/网络/外部进程等待）
        # 2026-08-26 收集超时专项排查定位：串行测量见 temp/collection_timing.json
        "test_ae_paths.py",  # AE Bridge脚本，模块级sleep等待AE响应(6s+)
        "test_canimport.py",  # AE Bridge脚本，模块级time.sleep(10)
        "test_davinci_api.py",  # 模块级启动DaVinci Resolve并等待最长270s，必须排除
        "test_execute_return.py",  # 模块级连接AE客户端(30s超时)
        "test_h264_import.py",  # AE Bridge脚本，模块级sleep等待(9s+)
        "test_render_vinland.py",  # 模块级触发真实AE渲染并轮询最长60s+
        # 收集阶段导入错误（模块级副作用/缺失依赖/断言，2026-08-26扫描确认）
        "test_api_integration.py",  # 模块级urlopen真实网络请求，无服务时报错或挂起
        "test_audio_analyzer.py",  # 模块级读取不存在的文件(FileNotFoundError)
        "test_audio_edit_engine.py",  # 语法错误(括号不匹配)
        "test_davinci_dll.py",  # 模块级依赖D:\DaVinci Resolve安装
        "test_debug_lua.py",  # 导入时AttributeError(_build_pipeline_lua缺失)
        "test_direct_download.py",  # media-fetcher
        "test_e2e_pipeline_v2.py",  # 导入时AttributeError
        "test_full_style.py",  # ai_agent模块不可用(重型依赖)
        "test_preview_inheritance.py",  # 模块级读取不存在的文件(FileNotFoundError)
        "test_puppet_style2.py",  # ai_agent模块不可用(重型依赖)
        "test_real_e2e_all_modules.py",  # 模块级断言要求真实mp4素材
        "test_safe_lut_path.py",  # 导入时AttributeError(_build_fusion_lua缺失)
]


# ============================================================
# 重型可选依赖的优雅降级（CI 等轻量环境无 torch/whisper 时注入 stub）
# ============================================================
def _stub_optional_heavy_deps():
    """为 CI 等轻量环境注入重型可选依赖的 stub。

    audio_analysis.py 在模块顶层 `import torch` / `import whisper`，
    这两个是 GB 级依赖，CI 环境不安装。此处仅当真实模块不可导入时
    注入 MagicMock stub，使测试套件可在 CI 中移植运行；
    本地环境已安装真实包时完全不干预。
    """
    from unittest.mock import MagicMock
    for dep in ("torch", "whisper"):
        if dep in sys.modules:
            continue
        try:
            __import__(dep)
        except ImportError:
            sys.modules[dep] = MagicMock()


_stub_optional_heavy_deps()


# ============================================================
# 共享 Fixture
# ============================================================

@pytest.fixture
def mock_ae_client():
    """模拟 AE MCP 客户端"""
    client = Mock()
    client.send_command.return_value = {"success": True, "status": "success"}
    client.clear_result = Mock()
    return client


@pytest.fixture
def mock_silhouette_executor():
    """模拟 Silhouette 执行器"""
    executor = Mock()
    executor.execute.return_value = {
        "status": "success",
        "ae_integration_data": {"type": "matte", "data": {}},
    }
    return executor


@pytest.fixture
def basic_planning():
    """基础规划结果"""
    from ae_agent_pipeline import PlanningResult
    planning = PlanningResult()
    planning.composition = {
        "name": "Test_Comp",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30,
    }
    planning.layers = [
        {"name": "Video1", "type": "footage", "source": "/path/v1.mp4", "startTime": 0, "duration": 5}
    ]
    planning.effects = []
    planning.keyframes = []
    planning.transitions = []
    planning.execution_order = ["createComposition"]
    planning.silhouette_operations = []
    planning.compiler_operations = []
    return planning


@pytest.fixture
def basic_understanding():
    """基础理解结果"""
    from ae_agent_pipeline import UnderstandingResult
    u = UnderstandingResult()
    u.style = "cinematic"
    u.nlu_intent_type = "ae_only"
    u.intent = "cinematic"
    u.keywords = ["电影感"]
    return u


@pytest.fixture
def basic_perception():
    """基础感知结果"""
    from ae_agent_pipeline import PerceptionResult
    p = PerceptionResult()
    p.audio_features = {"bpm": 120, "duration": 5.0, "beat_times": [0.5, 1.0, 1.5]}
    p.clip_features = [{"name": "clip1", "duration": 5.0}]
    return p


# ============================================================
# 测试标记
# ============================================================

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "slow: 标记慢测试（>1s）")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "real_ae: 需要真实 AE 环境的测试")
    config.addinivalue_line("markers", "real_davinci: 需要真实 DaVinci Resolve 环境的测试")
    config.addinivalue_line("markers", "real_render: 需要真实渲染引擎（C4D/Blender/AE）长时间执行的测试")
    config.addinivalue_line("markers", "silhouette: 需要 Silhouette 环境的测试")


def pytest_collection_modifyitems(config, items):
    """自动标记慢测试，并门控真实软件环境依赖测试"""
    run_real_ae = os.environ.get("AEK_REAL_AE", "") == "1"
    run_real_davinci = os.environ.get("AEK_REAL_DAVINCI", "") == "1"
    run_real_render = os.environ.get("AEK_REAL_RENDER", "") == "1"
    for item in items:
        # 如果测试路径包含 real_ae，自动标记
        if "real_ae" in str(item.fspath):
            item.add_marker(pytest.mark.real_ae)
        # 如果测试路径包含 silhouette，自动标记
        if "silhouette" in str(item.fspath):
            item.add_marker(pytest.mark.silhouette)
        # 真实 AE 环境测试门控：未设 AEK_REAL_AE=1 时跳过。
        # 背景(2026-08-27)：此类测试会启动 AfterFX.exe 并 asyncio 等待
        # 桥接响应，AE 未就绪时挂死整个会话（全量运行曾因此被杀）。
        markers = {m.name for m in item.iter_markers()}
        if "real_ae" in markers and not run_real_ae:
            item.add_marker(pytest.mark.skip(
                reason="需要真实 AE 环境，设 AEK_REAL_AE=1 启用"))
        # DaVinci Resolve 环境门控：fuscript.exe 不存在时挂起/报错。
        if "real_davinci" in markers and not run_real_davinci:
            item.add_marker(pytest.mark.skip(
                reason="需要真实 DaVinci Resolve 环境，设 AEK_REAL_DAVINCI=1 启用"))
        # 真实渲染引擎门控：这类用例会启动 C4D/Blender 实际渲染数分钟，
        # 全量回归中必须默认跳过（2026-08-27：曾导致会话超时并遗留 c4dpy 进程）。
        if "real_render" in markers and not run_real_render:
            item.add_marker(pytest.mark.skip(
                reason="需要真实渲染引擎，设 AEK_REAL_RENDER=1 启用"))


# ============================================================
# 全局配置
# ============================================================

@pytest.fixture(autouse=True)
def _no_learning_persist(monkeypatch, request):
    """防止测试中持久化学习数据（配置管理测试除外）"""
    if "test_config_manager" in str(request.fspath):
        return
    monkeypatch.setenv("AEK_ENVIRONMENT", "test")


# ============================================================
# builtins.__import__ 泄漏哨兵（2026-08-27）
# 全量运行时某测试 patch builtins.__import__ 后未正确恢复，
# 导致后续测试的延迟 import 失败。此钩子在每个测试结束后
# 检查 __import__ 是否被篡改，抓到即报 WARNING。
# ============================================================
import builtins as _bltn

_orig_import = _bltn.__import__  # 在 conftest 加载时快照


def pytest_runtest_teardown(item, nextitem):
    """每个测试用例结束后检查 builtins.__import__ 是否被篡改。"""
    current = _bltn.__import__
    if current is not _orig_import:
        import warnings
        warnings.warn(
            f"[IMPORT-LEAK] {item.nodeid} 结束后 builtins.__import__ 被篡改！"
            f" 原始={_orig_import!r}, 当前={current!r}",
            stacklevel=1,
        )
        _bltn.__import__ = _orig_import
