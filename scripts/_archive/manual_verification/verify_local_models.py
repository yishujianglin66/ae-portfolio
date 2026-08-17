#!/usr/bin/env python3
"""
本地模型测试脚本 - 验证TIER_1小模型部署

测试内容：
1. 模型加载测试（延迟加载验证）
2. 嵌入功能测试（BGE-Small-ZH）
3. 生成功能测试（Qwen2-0.5B）
4. 性能基准测试
5. 与LLM Gateway集成测试

运行方式：
    python tests/test_local_models.py --test load
    python tests/test_local_models.py --test embed
    python tests/test_local_models.py --test generate
    python tests/test_local_models.py --test all
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.local_model_adapter import (
    LocalModelAdapter,
    LocalModelConfig,
    LocalModelType,
    LocalModelRegistry,
    DEFAULT_MODELS,
)


def test_model_load(model_name: str) -> Dict[str, Any]:
    """测试模型加载"""
    print(f"\n[测试] 模型加载: {model_name}")
    
    config = DEFAULT_MODELS.get(model_name)
    if not config:
        print(f"  [错误] 未知模型: {model_name}")
        return {"success": False, "error": f"未知模型: {model_name}"}
    
    adapter = LocalModelAdapter(config)
    
    start_time = time.time()
    success, error = asyncio.run(adapter.initialize())
    load_time = time.time() - start_time
    
    if success:
        print(f"  [成功] 模型加载完成，耗时 {load_time:.2f}s")
        stats = adapter.get_stats()
        print(f"  [信息] 模型类型: {stats['model_type']}")
        print(f"  [信息] 是否嵌入模型: {stats['is_embedding_model']}")
        return {"success": True, "load_time": load_time, "stats": stats}
    else:
        print(f"  [失败] 模型加载失败: {error}")
        return {"success": False, "error": error}


def test_embedding(model_name: str = "bge-small-zh") -> Dict[str, Any]:
    """测试嵌入功能"""
    print(f"\n[测试] 嵌入功能: {model_name}")
    
    config = DEFAULT_MODELS.get(model_name)
    if not config:
        print(f"  [错误] 未知模型: {model_name}")
        return {"success": False, "error": f"未知模型: {model_name}"}
    
    adapter = LocalModelAdapter(config)
    
    # 初始化
    success, error = asyncio.run(adapter.initialize())
    if not success:
        print(f"  [失败] 模型初始化失败: {error}")
        return {"success": False, "error": error}
    
    # 测试嵌入
    test_texts = [
        "这是一段测试文本，用于测试嵌入模型。",
        "AE脚本是一种强大的工具。",
        "风格分类是视频分析的重要任务。",
    ]
    
    print(f"  [信息] 测试文本数量: {len(test_texts)}")
    
    start_time = time.time()
    response = asyncio.run(adapter.embed(test_texts))
    embed_time = time.time() - start_time
    
    if response.success:
        embedding_dim = len(response.embeddings[0]) if response.embeddings else 0
        print(f"  [成功] 嵌入完成")
        print(f"  [信息] 嵌入维度: {embedding_dim}")
        print(f"  [信息] 延迟: {response.latency_ms:.0f}ms")
        print(f"  [信息] 吞吐量: {len(test_texts) / embed_time:.1f} texts/s")
        return {
            "success": True,
            "embedding_dim": embedding_dim,
            "latency_ms": response.latency_ms,
            "throughput": len(test_texts) / embed_time,
        }
    else:
        print(f"  [失败] 嵌入失败: {response.error}")
        return {"success": False, "error": response.error}


def test_generation(model_name: str = "qwen2-0.5b") -> Dict[str, Any]:
    """测试生成功能"""
    print(f"\n[测试] 生成功能: {model_name}")
    
    config = DEFAULT_MODELS.get(model_name)
    if not config:
        print(f"  [错误] 未知模型: {model_name}")
        return {"success": False, "error": f"未知模型: {model_name}"}
    
    adapter = LocalModelAdapter(config)
    
    # 初始化
    success, error = asyncio.run(adapter.initialize())
    if not success:
        print(f"  [失败] 模型初始化失败: {error}")
        return {"success": False, "error": error}
    
    # 测试生成
    test_prompts = [
        "写一段AE脚本，创建一个1920x1080的合成：",
        "为图层添加Glow效果，参数设置为：",
    ]
    
    results = []
    for prompt in test_prompts:
        print(f"\n  [提示] {prompt}")
        
        start_time = time.time()
        response = asyncio.run(adapter.generate(prompt, max_new_tokens=100))
        gen_time = time.time() - start_time
        
        if response.success:
            print(f"  [生成] {response.content[:100]}...")
            print(f"  [信息] 延迟: {response.latency_ms:.0f}ms")
            results.append({
                "success": True,
                "content_length": len(response.content),
                "latency_ms": response.latency_ms,
            })
        else:
            print(f"  [失败] 生成失败: {response.error}")
            results.append({"success": False, "error": response.error})
    
    success_count = sum(1 for r in results if r.get("success"))
    avg_latency = sum(r.get("latency_ms", 0) for r in results if r.get("success")) / max(success_count, 1)
    
    return {
        "success": success_count > 0,
        "total_prompts": len(test_prompts),
        "success_count": success_count,
        "avg_latency_ms": avg_latency,
    }


def test_performance_benchmark() -> Dict[str, Any]:
    """性能基准测试"""
    print("\n[测试] 性能基准")
    
    results = {}
    
    # 嵌入性能
    if "bge-small-zh" in DEFAULT_MODELS:
        embed_result = test_embedding("bge-small-zh")
        results["embedding"] = embed_result
    
    # 生成性能
    if "qwen2-0.5b" in DEFAULT_MODELS:
        gen_result = test_generation("qwen2-0.5b")
        results["generation"] = gen_result
    
    return results


def test_gateway_integration() -> Dict[str, Any]:
    """测试与LLM Gateway集成"""
    print("\n[测试] Gateway集成")
    
    try:
        from core.llm_gateway import LLMGateway, LLMConfig, ModelTier
        
        config = LLMConfig()
        gateway = LLMGateway(config)
        
        # 检查本地适配器是否注册
        if hasattr(gateway, '_local_adapters'):
            print(f"  [信息] 已注册本地适配器: {list(gateway._local_adapters.keys())}")
            return {"success": True, "adapters": list(gateway._local_adapters.keys())}
        else:
            print(f"  [信息] Gateway暂未集成本地适配器")
            return {"success": False, "error": "Gateway未集成本地适配器"}
            
    except ImportError as e:
        print(f"  [失败] 无法导入LLM Gateway: {e}")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="本地模型测试")
    parser.add_argument("--test", choices=["load", "embed", "generate", "benchmark", "gateway", "all"], default="all")
    parser.add_argument("--model", type=str, default="bge-small-zh", help="模型名称")
    args = parser.parse_args()
    
    print("=" * 60)
    print("本地模型测试 - TIER_1 小模型部署验证")
    print("=" * 60)
    
    results = {}
    
    if args.test in ["load", "all"]:
        results["load"] = test_model_load(args.model)
    
    if args.test in ["embed", "all"]:
        results["embed"] = test_embedding("bge-small-zh")
    
    if args.test in ["generate", "all"]:
        results["generate"] = test_generation("qwen2-0.5b")
    
    if args.test in ["benchmark", "all"]:
        results["benchmark"] = test_performance_benchmark()
    
    if args.test in ["gateway", "all"]:
        results["gateway"] = test_gateway_integration()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results.items():
        if isinstance(result, dict):
            status = "✓ 通过" if result.get("success") else "✗ 失败"
            print(f"  {test_name}: {status}")
    
    print("=" * 60)
    
    # 保存结果
    output_path = PROJECT_ROOT / "data" / "local_model_test_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n结果已保存到: {output_path}")


if __name__ == "__main__":
    main()