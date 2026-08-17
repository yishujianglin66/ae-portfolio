---
alwaysApply: true
description: AE 大流程项目核心规范 - 覆盖多子系统与多 LLM API 适配
---

# AE 大流程项目核心规范

## 项目身份
本项目是"AE 大流程项目"（AE Knowledge Vault），覆盖从素材获取、音频分析、AE 合成、调色、剪辑到交付的完整视频制作链路。
项目根目录：`C:\Users\Administrator\Desktop\AE-Knowledge-Vault`

### 子系统划分
| 子系统 | 路径 | 职责 |
|--------|------|------|
| 核心基础设施 | `core/` | LLM 网关、配置管理、工作流编排、事件总线、状态机、可观测性 |
| 视频流水线 | `puppet-automation/` | AE/FFmpeg/Topaz/Silhouette/Blender/DaVinci/ME 引擎层 |
| 原子编译器 | `compiler/` | TypeScript 原子参数编译器（phase3/4/5） |
| 前端面板 | `ae-dashboard/` | React + Vite 控制面板 |
| Web 集成 | `integrator_web/` | 浏览器端集成界面 |
| MCP 扩展 | `mcp-extension/` | AE MCP 桥接扩展 |
| 配置中心 | `config/` | 多环境配置 + 风格预设 |
| 知识库 | `10-风格化剪辑知识库/` 等 | Obsidian 知识库 |
| 根目录脚本 | `*.py` / `*.jsx` | 独立工具脚本与实验代码 |

## 架构约定
- **引擎层** (`puppet-automation/src/engines/`)：每个外部软件一个引擎，继承 `BaseEngine`，实现 `execute()` 方法
- **服务层** (`puppet-automation/src/services/`)：业务逻辑封装，不直接操作外部软件
- **API 层** (`puppet-automation/src/api/main.py`)：FastAPI 端点，所有新功能必须注册到 `app.state.engines`
- **配置层** (`puppet-automation/src/config/settings.py` 与 `core/config.py`)：路径和参数集中管理，使用 `Path` 类型
- **LLM 网关** (`core/llm_gateway.py`)：所有 LLM 调用必须经网关，禁止业务代码直连 API
- **工作流编排** (`core/workflow_orchestrator.py`)：多步骤任务通过 Orchestrator 调度，支持依赖、并行、重试

## 代码风格
- Python 3.11+，使用 `from __future__ import annotations`
- 类型注解必须完整：`def func(x: str | Path) -> Dict[str, Any]:`
- 日志统一使用 `loguru`（业务层）或 `logging`（core 层）
- 异步优先：所有 I/O 操作使用 `async def` + `await asyncio.to_thread()`
- 路径统一使用 `pathlib.Path`，禁止使用 `os.path`（兼容老代码除外）
- 文档字符串使用三引号，中文编写

## 引擎开发规范（puppet-automation）
新增引擎必须：
1. 在 `puppet-automation/src/engines/{name}/` 下创建模块
2. 继承 `BaseEngine`，设置 `name` 类属性
3. 实现 `async def execute(self, **kwargs) -> EngineResult` 分发方法
4. 在 `puppet-automation/src/config/settings.py` 添加路径配置
5. 在 `puppet-automation/src/api/main.py` 的 `engine_classes` 字典注册
6. 添加对应的 API 端点
7. 编写 `tests/test_{name}_engine.py` 测试

## 测试规范
- Python 测试：`tests/` 目录，命名 `test_{module}.py`，使用 `pytest` + `pytest-asyncio`
- TypeScript 测试：`compiler/test/` 目录
- 每个引擎必须有初始化测试和核心功能测试
- 临时文件使用 `tempfile.TemporaryDirectory()` 清理
- E2E 测试产物输出到 `output/e2e_test/`
