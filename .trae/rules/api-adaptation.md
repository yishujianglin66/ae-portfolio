---
alwaysApply: true
description: 多 LLM API 自动适配与接入规范
---

# 多 LLM API 自动适配规范

## 核心原则
项目接入多家 LLM Provider（DeepSeek、豆包、通义、GLM、Kimi 等），所有调用必须通过 `core/llm_gateway.py` 统一网关，由网关负责**自动适配、智能路由、健康检查、自动降级**。业务代码禁止直连任何 Provider 的 HTTP API。

## 网关架构（LLMGateway）
```
业务代码 → llm_gateway.chat() / chat_with_routing()
                ↓
        ┌───────────────┐
        │  LLMGateway   │
        ├───────────────┤
        │ • Provider 健康跟踪    │
        │ • 任务类型→模型映射     │
        │ • 自动降级 failover    │
        │ • Token 压缩           │
        │ • 用量与成本追踪        │
        └───────────────┘
                ↓
        Primary Provider  →  Fallback Providers
```

## Provider 接入规范
新增 Provider 必须遵循 OpenAI 兼容协议，并按以下步骤接入：

1. **配置注册**：在 `core/config.py` 的默认配置中添加 Provider URL + API Key 字段
2. **环境变量**：使用 `AEKV_LLM_*` 前缀，敏感信息通过 `.env` 注入，禁止硬编码
3. **Provider 识别**：网关通过 `_extract_provider_name(url)` 自动从 URL 提取 Provider 名
4. **健康跟踪**：新 Provider 自动加入 `_provider_health` 字典，跟踪 `status / latency / error_count`
5. **降级链路**：在 `LLMConfig.fallback_providers` 中配置降级顺序
6. **日志脱敏**：所有日志输出必须经 `_sanitize_log_text()` 处理，掩码 `Authorization` / `sk-*` / `api_key=*`

## 模型选择策略（chat_with_routing）
按 `TaskType` 自动选择模型档位：

| TaskType | 模型档位 | 典型场景 |
|----------|---------|---------|
| `intent_classification` | FLASH | 意图识别、简单分类 |
| `code_generation` | PRO + SPECIALIZED | 代码生成、调试 |
| `complex_analysis` | PRO | 架构设计、风格分析、多模态理解 |
| `deep_reasoning` | THINKING | 多步推理、决策分析 |
| `vision_understanding` | VISION | 图像分析、视频帧理解 |
| `image_generation` | IMAGE_GENERATION | 文生图 |
| `video_generation` | VIDEO_GENERATION | 文生视频 / 图生视频 |
| `embedding` | EMBEDDING | 向量化检索 |
| `translation` | SPECIALIZED | 专业翻译 |
| `batch_processing` | FLASH | 大规模批量处理 |

完整模型清单见 `model_router.py` 顶部注释。

## 自动降级策略
1. 主 Provider 调用失败（超时 / 5xx / 限流）→ 自动切换到 `fallback_providers[0]`
2. 切换前更新 `ProviderHealth.status = UNHEALTHY`，记录失败原因
3. 健康检查恢复后，`ProviderHealth.status` 自动转回 `HEALTHY`
4. 所有 Provider 全部失败时，抛出 `LLMUnavailableError`，由上层决定是否重试

## 客户端封装规范
- `deepseek_v4_client.py`、`doubao_client.py` 等独立客户端**仅作为网关的内部实现细节**，不对外暴露
- 新增 Provider 时，优先扩展 `LLMGateway._call_provider()` 而非新建独立客户端文件
- 若 Provider 协议特殊（非 OpenAI 兼容），可在 `core/providers/` 下新建适配器，但必须实现统一接口

## 用量与成本
- 每次调用记录 `input_tokens / output_tokens / cost / latency`
- 通过 `observability.py` 上报指标
- 业务代码可通过 `llm_gateway.get_usage_stats()` 查询累计用量

## 安全约束
- API Key 仅存于 `.env` / 环境变量，禁止提交到 Git
- `.env.example` 提供字段模板但不包含真实值
- 生产环境强制校验 `AEKV_LLM_API_KEY` 非空且非默认值
- 日志中不得出现完整 API Key 或 Bearer Token
