#!/usr/bin/env python3
"""
LLM 网关 + 持久化记忆系统 集成测试

验证：
1. LLMGateway 配置与降级机制
2. TokenCompressor 压缩/解压
3. MemoryStore 记忆存储/检索/经验学习
4. 双模型对抗审查接口
5. 与 AEAgentPipeline 的集成
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_llm_gateway_config():
    """测试 LLM 网关配置"""
    from core.llm_gateway import LLMGateway, LLMConfig, TaskType

    # 默认配置
    gw = LLMGateway()
    assert not gw.is_available(), "默认应不可用（无 api_key）"

    # 配置后可用
    config = LLMConfig(
        base_url="http://localhost:5273/v1",
        api_key="test-key",
        default_model="auto",
    )
    gw.configure(config)
    assert gw.is_available(), "配置后应可用"

    # 路由表
    model = gw._config.model_routing[TaskType.INTENT_CLASSIFICATION]
    assert model == "auto", f"路由模型应为 auto, 实际 {model}"

    print("  [PASS] LLM 网关配置测试")


def test_llm_gateway_env_config():
    """测试环境变量配置"""
    from core.llm_gateway import LLMGateway

    os.environ["AEKV_LLM_BASE_URL"] = "http://test-gateway:8080/v1"
    os.environ["AEKV_LLM_API_KEY"] = "env-test-key"
    os.environ["AEKV_LLM_MODEL"] = "deepseek-chat"

    gw = LLMGateway()
    gw.configure_from_env()

    assert gw._config.base_url == "http://test-gateway:8080/v1"
    assert gw._config.api_key == "env-test-key"
    assert gw._config.default_model == "deepseek-chat"
    assert gw.is_available()

    del os.environ["AEKV_LLM_BASE_URL"]
    del os.environ["AEKV_LLM_API_KEY"]
    del os.environ["AEKV_LLM_MODEL"]

    print("  [PASS] 环境变量配置测试")


def test_token_compressor():
    """测试 Token 压缩器"""
    from core.llm_gateway import TokenCompressor

    comp = TokenCompressor()

    # 压缩提示词
    original = "请详细分析这段视频的情绪，请描述场景中的人物动作"
    compressed = comp.compress_prompt(original)
    assert "请详细分析" not in compressed, "应压缩冗余词"
    assert "请描述" not in compressed, "应压缩冗余词"
    assert "分析" in compressed, "应保留核心词"
    assert "描述" in compressed, "应保留核心词"

    # 系统提示词压缩（超长截断）
    long_system = "请详细分析" * 50
    compressed_sys = comp.compress_system(long_system)
    assert len(compressed_sys) <= 203, "应截断到 200+3 字符"

    # 解压响应
    caveman_response = "意图:roto|情绪:紧张|置信度:0.85"
    decompressed = comp.decompress_response(caveman_response)
    assert "|" not in decompressed, "应将分隔符转为换行"
    assert "意图:roto" in decompressed

    # 无分隔符的响应不变
    plain = "这是一段普通回复"
    assert comp.decompress_response(plain) == plain

    print("  [PASS] Token 压缩器测试")


def test_llm_gateway_unavailable():
    """测试 LLM 不可用时的降级"""
    from core.llm_gateway import LLMGateway, LLMResponse

    gw = LLMGateway()  # 默认无配置

    result = asyncio.run(gw.chat("测试消息"))
    assert not result.success, "未配置时应返回失败"
    assert "未配置" in result.error or "不可用" in result.error

    print("  [PASS] LLM 降级测试")


def test_memory_store_basic():
    """测试记忆系统基础操作"""
    from core.memory_store import MemoryStore

    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = MemoryStore(db_path=db_path)

    try:
        # 存储记忆
        mem_id = store.remember(
            category="roto_execution",
            key="埼玉_抠像",
            content={"method": "RotoNode", "frames": 18, "success": True},
            tags=["roto", "silhouette", "埼玉"],
            confidence=0.8,
        )
        assert mem_id > 0, "应返回有效 ID"

        # 精确检索
        entry = store.recall("roto_execution", "埼玉_抠像")
        assert entry is not None, "应能检索到记忆"
        assert entry.content["method"] == "RotoNode"
        assert entry.confidence == 0.8
        assert "roto" in entry.tags

        # 再次检索，访问次数应增加
        store.recall("roto_execution", "埼玉_抠像")
        entry2 = store.recall("roto_execution", "埼玉_抠像")
        assert entry2.access_count >= 2, f"访问次数应 >= 2, 实际 {entry2.access_count}"

        # 搜索
        results = store.search("roto")
        assert len(results) >= 1, "应能搜索到记忆"
        assert results[0].key == "埼玉_抠像"

        # 删除
        deleted = store.forget("roto_execution", "埼玉_抠像")
        assert deleted, "应成功删除"
        assert store.recall("roto_execution", "埼玉_抠像") is None

        print("  [PASS] 记忆系统基础操作测试")
    finally:
        store.close()
        try:
            os.unlink(db_path)
        except PermissionError:
            pass


def test_memory_store_fts():
    """测试全文检索"""
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = MemoryStore(db_path=db_path)
    try:
        # 存储多条记忆
        store.remember("effect", "发光效果", {"type": "glow", "intensity": 0.8},
                        tags=["glow", "发光"])
        store.remember("effect", "模糊效果", {"type": "blur", "radius": 10},
                        tags=["blur", "模糊"])
        store.remember("effect", "粒子效果", {"type": "particles", "count": 500},
                        tags=["particles", "粒子"])
        store.remember("roto", "人物抠像", {"method": "RotoNode"},
                        tags=["roto", "人物"])

        # 全文搜索
        results = store.search("发光")
        assert len(results) >= 1
        assert any(r.key == "发光效果" for r in results)

        results = store.search("roto")
        assert len(results) >= 1
        assert any(r.key == "人物抠像" for r in results)

        # 分类限定搜索
        results = store.search("效果", category="effect")
        assert all(r.category == "effect" for r in results)

        print("  [PASS] 全文检索测试")
    finally:
        store.close()
        try:
            os.unlink(db_path)
        except PermissionError:
            pass


def test_memory_experience_learning():
    """测试经验学习和置信度更新"""
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = MemoryStore(db_path=db_path)
    try:
        # 存储初始经验
        store.remember(
            category="pipeline_execution",
            key="roto_glow_combo",
            content={"steps": ["roto", "glow"]},
            confidence=0.5,
        )

        # 记录成功
        store.record_outcome("pipeline_execution", "roto_glow_combo", success=True)
        entry = store.recall("pipeline_execution", "roto_glow_combo")
        assert entry.success_count == 1
        assert entry.confidence > 0, "成功后置信度应 > 0"

        # 再记录两次成功
        store.record_outcome("pipeline_execution", "roto_glow_combo", success=True)
        store.record_outcome("pipeline_execution", "roto_glow_combo", success=True)
        entry = store.recall("pipeline_execution", "roto_glow_combo")
        assert entry.success_count == 3

        # 记录一次失败
        store.record_outcome("pipeline_execution", "roto_glow_combo", success=False)
        entry = store.recall("pipeline_execution", "roto_glow_combo")
        assert entry.failure_count == 1

        # 获取经验
        experiences = store.get_experience(
            category="pipeline_execution",
            min_confidence=0.0,
        )
        assert len(experiences) >= 1

        print("  [PASS] 经验学习测试")
    finally:
        store.close()
        try:
            os.unlink(db_path)
        except PermissionError:
            pass


def test_memory_stats():
    """测试记忆系统统计"""
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = MemoryStore(db_path=db_path)
    try:
        store.remember("effect", "test1", {"v": 1})
        store.remember("effect", "test2", {"v": 2})
        store.remember("roto", "test3", {"v": 3})

        stats = store.get_stats()
        assert stats["total_memories"] == 3
        assert "effect" in stats["categories"]
        assert "roto" in stats["categories"]
        assert stats["categories"]["effect"] == 2
        assert stats["categories"]["roto"] == 1

        print("  [PASS] 记忆系统统计测试")
    finally:
        store.close()
        try:
            os.unlink(db_path)
        except PermissionError:
            pass


def test_dual_model_review_interface():
    """测试双模型对抗审查接口（不实际调用 LLM）"""
    from core.llm_gateway import LLMGateway, LLMConfig

    # 未配置的网关，dual_model_review 应返回两个失败响应
    gw = LLMGateway()

    result_a, result_b = asyncio.run(gw.dual_model_review("测试内容"))
    assert not result_a.success, "未配置时模型A应失败"
    assert not result_b.success, "未配置时模型B应失败"

    print("  [PASS] 双模型对抗审查接口测试")


def test_pipeline_integration():
    """测试与 AEAgentPipeline 的集成"""
    import tempfile
    from ae_agent_pipeline import AEAgentPipeline
    from core.memory_store import MemoryStore

    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    # 替换为临时数据库
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    # 验证所有组件已初始化
    assert pipeline._llm_gateway is not None, "LLM 网关应已初始化"
    assert pipeline._memory_store is not None, "记忆系统应已初始化"

    # LLM 网关当前未配置（无 API Key），应不可用
    assert not pipeline._llm_gateway.is_available(), "默认应不可用"

    # 记忆系统应可正常操作
    pipeline._memory_store.remember(
        category="test",
        key="integration_test",
        content={"status": "ok"},
    )
    entry = pipeline._memory_store.recall("test", "integration_test")
    assert entry is not None
    assert entry.content["status"] == "ok"

    # 清理
    pipeline._memory_store.forget("test", "integration_test")

    # 释放资源
    pipeline.close()

    print("  [PASS] Pipeline 集成测试")


def test_pipeline_confidence_cache():
    """测试 Pipeline 置信度缓存（使用记忆系统）"""
    import tempfile
    from ae_agent_pipeline import AEAgentPipeline
    from core.memory_store import MemoryStore

    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    # 替换为临时数据库
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    # 调用 _update_confidence_cache
    pipeline._update_confidence_cache("epic", "cinematic", 0.85)

    # 验证已存储
    entry = pipeline._memory_store.recall("confidence_cache", "epic_cinematic")
    assert entry is not None, "置信度缓存应已存储"
    assert entry.content["confidence"] == 0.85
    assert entry.confidence == 0.85

    # 清理
    pipeline._memory_store.forget("confidence_cache", "epic_cinematic")

    # 释放资源
    pipeline.close()

    print("  [PASS] 置信度缓存测试")


def main():
    print("=" * 60)
    print("LLM 网关 + 持久化记忆系统 集成测试")
    print("=" * 60)

    tests = [
        ("LLM 网关配置", test_llm_gateway_config),
        ("环境变量配置", test_llm_gateway_env_config),
        ("Token 压缩器", test_token_compressor),
        ("LLM 降级", test_llm_gateway_unavailable),
        ("记忆系统基础", test_memory_store_basic),
        ("全文检索", test_memory_store_fts),
        ("经验学习", test_memory_experience_learning),
        ("记忆统计", test_memory_stats),
        ("双模型审查接口", test_dual_model_review_interface),
        ("Pipeline 集成", test_pipeline_integration),
        ("置信度缓存", test_pipeline_confidence_cache),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n[Test] {name}")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] 异常: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
