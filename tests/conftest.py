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
    config.addinivalue_line("markers", "silhouette: 需要 Silhouette 环境的测试")


def pytest_collection_modifyitems(config, items):
    """自动标记慢测试"""
    for item in items:
        # 如果测试路径包含 real_ae，自动标记
        if "real_ae" in str(item.fspath):
            item.add_marker(pytest.mark.real_ae)
        # 如果测试路径包含 silhouette，自动标记
        if "silhouette" in str(item.fspath):
            item.add_marker(pytest.mark.silhouette)


# ============================================================
# 全局配置
# ============================================================

@pytest.fixture(autouse=True)
def _no_learning_persist(monkeypatch, request):
    """防止测试中持久化学习数据（配置管理测试除外）"""
    if "test_config_manager" in str(request.fspath):
        return
    monkeypatch.setenv("AEK_ENVIRONMENT", "test")
