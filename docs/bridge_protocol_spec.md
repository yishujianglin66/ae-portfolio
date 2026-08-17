# AE Bridge 统一通信协议规范 v2.0

## 目录

1. [概述](#概述)
2. [协议架构](#协议架构)
3. [命令结构](#命令结构)
4. [响应结构](#响应结构)
5. [错误码体系](#错误码体系)
6. [优先级队列](#优先级队列)
7. [幂等性保证](#幂等性保证)
8. [签名验证](#签名验证)
9. [重试机制](#重试机制)
10. [超时与清理](#超时与清理)
11. [死信队列](#死信队列)
12. [文件布局](#文件布局)
13. [向后兼容](#向后兼容)

---

## 概述

### 背景

AE Bridge 是 Python 端与 After Effects (ExtendScript) 之间的通信桥梁。现有方案通过 `ae_command.json` + `ae_result.json` 文件轮询实现，但存在以下问题：

- 缺少标准化的命令/响应结构
- 没有统一的错误码体系
- 缺少幂等性保证
- 无优先级队列机制
- 重试策略不明确
- 缺少死信队列处理
- 超时清理机制不完善

### 设计目标

1. **可靠性**：确保命令不丢失、不重复执行
2. **可观测性**：完整的状态追踪与进度反馈
3. **安全性**：HMAC 签名验证防止篡改
4. **高性能**：优先级队列 + 并发控制
5. **可扩展性**：支持协议版本演进
6. **向后兼容**：平滑迁移现有系统

### 协议版本

当前版本：`2.0.0`

---

## 协议架构

### 通信模型

```
Python Client                    AE Server (ExtendScript)
     |                                  |
     |  1. 写入 ae_command.json         |
     |  (command + signature)          |
     |--------------------------------->|
     |                                  |  2. 轮询检测新命令
     |                                  |  3. 验证签名
     |                                  |  4. 执行命令
     |                                  |  5. 更新状态 (processing)
     |                                  |
     |  6. 轮询 ae_result.json          |
     |<---------------------------------|  7. 写入最终结果
     |                                  |
```

### 文件布局

默认目录：`.ae-mcp-bridge/`

| 文件 | 用途 |
|------|------|
| `ae_command.json` | 当前正在执行的命令（单命令模式） |
| `ae_result.json` | 当前命令的执行结果 |
| `command_queue/` | 命令队列目录（优先级队列模式） |
| `result_store/` | 历史结果存储目录 |
| `dead_letter/` | 死信队列目录 |
| `.mcp_secret` | HMAC 签名密钥 |
| `ae_trigger.json` | 看门狗触发文件 |

---

## 命令结构

### 字段定义

```python
{
    "protocol_version": "2.0.0",      # 协议版本号
    "command_id": "uuid-v4",          # 命令唯一标识（UUID v4）
    "command": "create_composition",  # 命令名称
    "params": { ... },                # 命令参数
    "timestamp": "ISO-8601",          # 发送时间
    "ttl": 30000,                     # 超时时间（毫秒）
    "priority": "NORMAL",             # 优先级：HIGH/NORMAL/LOW/BACKGROUND
    "idempotency_key": "string",      # 幂等键（可选）
    "metadata": {                     # 元数据（可选）
        "source": "ai_director",
        "correlation_id": "uuid",
        "tags": ["batch", "render"]
    },
    "signature": "hmac-sha256-hex",   # HMAC 签名
    "signature_alg": "HS256"          # 签名算法
}
```

### 字段详解

#### protocol_version
- **类型**：string
- **必填**：是
- **说明**：语义化版本号，用于协议兼容性检查

#### command_id
- **类型**：string (UUID v4)
- **必填**：是
- **说明**：命令的全局唯一标识符，用于结果关联和幂等判断
- **生成方式**：`uuid.uuid4()`

#### command
- **类型**：string
- **必填**：是
- **说明**：命令名称，使用 snake_case 命名风格
- **命名规范**：`<动作>_<对象>`，如 `create_composition`, `set_layer_properties`

#### params
- **类型**：object
- **必填**：是（可为空对象）
- **说明**：命令参数字典，具体结构由各命令定义

#### timestamp
- **类型**：string (ISO-8601)
- **必填**：是
- **格式**：`YYYY-MM-DDTHH:mm:ss.sssZ`（UTC）
- **示例**：`2026-07-21T10:30:00.123Z`

#### ttl
- **类型**：integer
- **必填**：是
- **单位**：毫秒
- **默认值**：30000 (30秒)
- **说明**：命令超时时间，超过此时间未完成则标记为 timeout

#### priority
- **类型**：string enum
- **必填**：是
- **可选值**：
  - `HIGH` - 高优先级（用户交互、实时操作）
  - `NORMAL` - 普通优先级（默认）
  - `LOW` - 低优先级（后台批量处理）
  - `BACKGROUND` - 后台优先级（空闲时执行）

#### idempotency_key
- **类型**：string
- **必填**：否
- **说明**：幂等键，相同幂等键的命令只执行一次
- **使用场景**：可能重复发送的操作（如网络重试）

#### metadata
- **类型**：object
- **必填**：否
- **说明**：附加元数据，用于追踪、分类、调试
- **保留字段**：
  - `source` - 命令来源标识
  - `correlation_id` - 关联ID，用于追踪跨系统调用链
  - `tags` - 标签数组，用于分类过滤

#### signature
- **类型**：string
- **必填**：否（可配置启用/禁用）
- **说明**：HMAC-SHA256 签名的十六进制字符串
- **签名内容**：除 `signature` 字段外的所有字段按 key 排序后的规范 JSON

#### signature_alg
- **类型**：string
- **必填**：否
- **默认值**：`HS256`
- **说明**：签名算法标识

---

## 响应结构

### 字段定义

```python
{
    "protocol_version": "2.0.0",
    "command_id": "uuid-v4",
    "status": "completed",          # pending/processing/completed/failed/timeout/cancelled
    "result": { ... },              # 成功时的结果数据
    "error": {                      # 失败时的错误信息
        "code": 3001,
        "message": "参数错误：comp_name 不能为空",
        "details": {
            "field": "comp_name",
            "constraint": "required"
        },
        "stack_trace": "..."        # 可选，调试用
    },
    "progress": {                   # 进行中的进度信息
        "percent": 45,
        "message": "正在导入素材...",
        "current_step": 3,
        "total_steps": 10
    },
    "started_at": "ISO-8601",       # 开始执行时间
    "finished_at": "ISO-8601",      # 完成时间
    "execution_time_ms": 1234,      # 执行耗时（毫秒）
    "attempt": 1,                   # 执行次数
    "worker_id": "ae-instance-1"    # 执行节点标识（可选）
}
```

### 状态枚举

| 状态 | 说明 | 终态 |
|------|------|------|
| `pending` | 已入队，等待执行 | 否 |
| `processing` | 正在执行中 | 否 |
| `completed` | 执行成功 | 是 |
| `failed` | 执行失败 | 是 |
| `timeout` | 执行超时 | 是 |
| `cancelled` | 已取消 | 是 |

### 状态流转

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
          ┌────────│ processing  │────────┐
          │        └──────┬──────┘        │
          │               │                │
          ▼               ▼                ▼
   ┌──────────┐    ┌────────────┐   ┌───────────┐
   │ completed│    │   failed   │   │  timeout  │
   └──────────┘    └────────────┘   └───────────┘
          │               │                │
          └───────────────┼────────────────┘
                          │
                    ┌─────────────┐
                    │  cancelled  │  (可从任意非终态取消)
                    └─────────────┘
```

---

## 错误码体系

### 错误码分类

| 区间 | 类别 | 说明 |
|------|------|------|
| 1000-1999 | 协议错误 | 格式错误、签名错误、版本不兼容 |
| 2000-2999 | AE 端错误 | AE 未运行、脚本错误、权限不足 |
| 3000-3999 | 业务错误 | 参数错误、资源不存在、操作失败 |
| 4000-4999 | 系统错误 | IO错误、内存不足、意外崩溃 |

### 协议错误 (1xxx)

| 错误码 | 名称 | 说明 | 建议处理 |
|--------|------|------|----------|
| 1001 | INVALID_JSON | JSON 格式解析失败 | 检查命令格式，重新发送 |
| 1002 | MISSING_REQUIRED_FIELD | 缺少必填字段 | 补充必填字段后重试 |
| 1003 | INVALID_FIELD_TYPE | 字段类型错误 | 修正字段类型后重试 |
| 1004 | SIGNATURE_VERIFICATION_FAILED | 签名验证失败 | 检查密钥是否匹配，防止篡改 |
| 1005 | SIGNATURE_ALGORITHM_UNSUPPORTED | 签名算法不支持 | 使用支持的算法（HS256） |
| 1006 | PROTOCOL_VERSION_INCOMPATIBLE | 协议版本不兼容 | 升级客户端或服务端 |
| 1007 | COMMAND_TOO_LARGE | 命令体过大 | 拆分命令或优化参数 |
| 1008 | INVALID_COMMAND_ID | 命令ID格式错误 | 使用标准 UUID v4 格式 |

### AE 端错误 (2xxx)

| 错误码 | 名称 | 说明 | 建议处理 |
|--------|------|------|----------|
| 2001 | AE_NOT_RUNNING | After Effects 未运行 | 启动 AE 后重试 |
| 2002 | AE_NOT_RESPONDING | AE 无响应 | 等待或重启 AE |
| 2003 | SCRIPT_EXECUTION_ERROR | 脚本执行错误 | 检查脚本逻辑，查看堆栈信息 |
| 2004 | PERMISSION_DENIED | 权限不足 | 检查文件权限和 AE 安全设置 |
| 2005 | PROJECT_NOT_OPEN | 项目未打开 | 打开项目后重试 |
| 2006 | ACTIVE_COMP_NOT_FOUND | 无活动合成 | 选择或创建合成后重试 |
| 2007 | MEMORY_INSUFFICIENT | 内存不足 | 释放内存或降低复杂度 |
| 2008 | RENDER_ENGINE_BUSY | 渲染引擎繁忙 | 等待渲染完成后重试 |
| 2009 | SCRIPT_TIMEOUT | 脚本执行超时 | 优化脚本或增加超时时间 |

### 业务错误 (3xxx)

| 错误码 | 名称 | 说明 | 建议处理 |
|--------|------|------|----------|
| 3001 | INVALID_PARAMETER | 参数错误 | 检查参数合法性 |
| 3002 | RESOURCE_NOT_FOUND | 资源不存在 | 检查资源名称/路径是否正确 |
| 3003 | RESOURCE_ALREADY_EXISTS | 资源已存在 | 使用已有资源或换名 |
| 3004 | OPERATION_NOT_SUPPORTED | 操作不支持 | 检查 AE 版本或插件是否安装 |
| 3005 | COMPOSITION_NOT_FOUND | 合成不存在 | 检查合成名称 |
| 3006 | LAYER_NOT_FOUND | 图层不存在 | 检查图层名称/索引 |
| 3007 | EFFECT_NOT_FOUND | 效果不存在 | 检查效果名称或插件是否安装 |
| 3008 | PROPERTY_NOT_FOUND | 属性不存在 | 检查属性路径 |
| 3009 | INVALID_LAYER_TYPE | 图层类型不匹配 | 检查操作是否适用于该图层类型 |
| 3010 | IMPORT_FAILED | 素材导入失败 | 检查文件格式和路径 |
| 3011 | RENDER_FAILED | 渲染失败 | 检查渲染设置和输出路径 |
| 3012 | UNDO_NOT_AVAILABLE | 撤销不可用 | 检查撤销历史 |
| 3013 | IDEMPOTENCY_CONFLICT | 幂等冲突 | 相同幂等键但参数不一致 |

### 系统错误 (4xxx)

| 错误码 | 名称 | 说明 | 建议处理 |
|--------|------|------|----------|
| 4001 | IO_ERROR | IO 读写错误 | 检查磁盘空间和文件权限 |
| 4002 | FILE_NOT_FOUND | 文件不存在 | 检查文件路径 |
| 4003 | DISK_FULL | 磁盘空间不足 | 清理磁盘空间 |
| 4004 | NETWORK_ERROR | 网络错误 | 检查网络连接 |
| 4005 | OUT_OF_MEMORY | 系统内存不足 | 关闭其他程序释放内存 |
| 4006 | UNEXPECTED_CRASH | 意外崩溃 | 重启 AE 后重试，检查稳定性 |
| 4007 | LOCK_ACQUISITION_FAILED | 文件锁获取失败 | 稍后重试，检查是否有其他进程占用 |
| 4008 | INTERNAL_ERROR | 内部错误 | 记录日志，联系开发人员 |

---

## 优先级队列

### 优先级定义

| 优先级 | 数值 | 说明 | 典型场景 |
|--------|------|------|----------|
| HIGH | 0 | 最高优先级 | 用户实时操作、UI 交互 |
| NORMAL | 1 | 普通优先级 | 默认命令、常规操作 |
| LOW | 2 | 低优先级 | 批量处理、非关键操作 |
| BACKGROUND | 3 | 后台优先级 | 空闲时执行、预加载 |

### 队列策略

1. **高优先级优先**：HIGH > NORMAL > LOW > BACKGROUND
2. **同优先级 FIFO**：同一优先级按入队顺序执行
3. **优先级老化**：低优先级命令等待超过阈值后自动升级
4. **并发控制**：可配置最大并发执行数（默认 1）

### 优先级老化规则

| 当前优先级 | 等待时间阈值 | 升级后优先级 |
|-----------|-------------|-------------|
| BACKGROUND | 5 分钟 | LOW |
| LOW | 10 分钟 | NORMAL |
| NORMAL | 不升级 | - |

---

## 幂等性保证

### 幂等键机制

1. **生成规则**：客户端为可能重复的操作生成唯一幂等键
2. **存储位置**：服务端维护已执行幂等键的结果缓存
3. **匹配逻辑**：
   - 相同幂等键 + 相同参数 → 直接返回缓存结果
   - 相同幂等键 + 不同参数 → 返回 3013 幂等冲突错误
4. **过期时间**：幂等记录默认保留 24 小时

### 适用场景

- 网络重试：防止网络超时导致重复执行
- 批量处理：任务重启后避免重复处理
- 用户误操作：防止重复点击导致多次执行

### 使用建议

```python
# 对于可安全重试的操作，使用幂等键
idempotency_key = f"create_comp_{project_id}_{comp_name}"
client.send_command(
    command="create_composition",
    params={"name": comp_name, "width": 1920, "height": 1080},
    idempotency_key=idempotency_key
)
```

---

## 签名验证

### 算法

- **算法**：HMAC-SHA256
- **输出格式**：十六进制字符串（小写）
- **密钥**：预共享密钥，存储在 `.mcp_secret` 文件中

### 签名生成步骤

1. 构造待签名对象：排除 `signature` 字段
2. 生成规范 JSON：
   - 按 key 字母顺序排序
   - 使用紧凑格式（无空格）
   - ensure_ascii=False（保留 Unicode）
3. 使用 HMAC-SHA256 计算签名
4. 转换为十六进制字符串

### 伪代码

```python
import json
import hmac
import hashlib

def generate_signature(command: dict, secret: str) -> str:
    sign_data = {k: v for k, v in command.items() if k != "signature"}
    canonical = json.dumps(sign_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
```

### 验证流程

1. 接收命令后，提取 `signature` 字段
2. 使用相同算法重新计算签名
3. 比较两个签名是否一致（使用恒定时间比较防止时序攻击）
4. 不一致则返回 1004 错误

---

## 重试机制

### 重试策略

#### 可重试错误

以下错误码支持自动重试：
- 1001 - INVALID_JSON（仅偶发情况）
- 2001 - AE_NOT_RUNNING
- 2002 - AE_NOT_RESPONDING
- 2007 - MEMORY_INSUFFICIENT
- 2008 - RENDER_ENGINE_BUSY
- 4001 - IO_ERROR
- 4003 - DISK_FULL
- 4007 - LOCK_ACQUISITION_FAILED

#### 不可重试错误

以下错误不重试，直接返回失败：
- 1004 - 签名验证失败
- 1006 - 协议版本不兼容
- 3001 - 参数错误（业务逻辑错误）
- 3002 - 资源不存在

### 退避算法

使用**指数退避 + 抖动**算法：

```
base_delay = 100ms  # 基础延迟
max_delay = 10000ms # 最大延迟
factor = 2.0        # 指数因子

delay = min(base_delay * (factor ^ attempt), max_delay)
delay = delay * random(0.5, 1.5)  # 增加抖动
```

### 默认重试配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_retries | 3 | 最大重试次数 |
| base_delay_ms | 100 | 初始重试延迟 |
| max_delay_ms | 10000 | 最大重试延迟 |
| backoff_factor | 2.0 | 指数退避因子 |
| jitter | true | 是否启用抖动 |

### 幂等性与重试

- **有幂等键**：直接重试，服务端保证幂等
- **无幂等键**：仅对安全的只读操作重试，写入操作需用户确认

---

## 超时与清理

### 超时类型

1. **命令超时 (ttl)**：命令从发送到完成的最大时间
2. **队列超时**：命令在队列中等待的最大时间
3. **执行超时**：单次执行的最大时间（用于脚本超时保护）

### 超时处理

1. 标记命令状态为 `timeout`
2. 写入错误信息（错误码 2009 或 相应超时错误）
3. 移至历史结果存储
4. 触发超时回调（如已注册）

### 清理策略

| 数据类型 | 保留时间 | 清理方式 |
|---------|---------|---------|
| 待执行命令 | 由 ttl 决定 | 超时后标记 timeout |
| 执行中结果 | 运行时 | 完成后移至历史存储 |
| 历史结果 | 24 小时 | 定时清理或按容量淘汰 |
| 死信队列 | 7 天 | 手动清理或自动过期 |

---

## 死信队列

### 进入死信的条件

1. 重试次数耗尽仍失败
2. 幂等冲突无法解决
3. 致命错误（如协议不兼容）
4. 手动标记放弃的命令

### 死信记录结构

```python
{
    "command": { ... },           # 原始命令
    "last_error": {               # 最后一次错误
        "code": 2003,
        "message": "脚本执行错误"
    },
    "attempts": 4,                # 尝试次数
    "first_failed_at": "ISO-8601",# 首次失败时间
    "last_failed_at": "ISO-8601", # 最后失败时间
    "dead_letter_reason": "max_retries_exceeded"  # 进入死信原因
}
```

### 死信处理

1. **人工干预**：管理员检查死信队列，决定是否重试
2. **批量重试**：修复问题后批量重试死信
3. **丢弃**：确认无法处理的命令手动丢弃

---

## 文件布局

### 单命令模式（兼容 v1）

```
.ae-mcp-bridge/
├── ae_command.json       # 当前命令
├── ae_result.json        # 当前结果
├── ae_trigger.json       # 触发文件
└── .mcp_secret           # 签名密钥
```

### 队列模式（v2 新增）

```
.ae-mcp-bridge/
├── command_queue/              # 命令队列
│   ├── 0_HIGH/                 # 高优先级队列
│   │   ├── cmd_uuid1.json
│   │   └── cmd_uuid2.json
│   ├── 1_NORMAL/               # 普通优先级队列
│   ├── 2_LOW/                  # 低优先级队列
│   └── 3_BACKGROUND/           # 后台优先级队列
├── result_store/               # 结果存储
│   ├── 2026-07-21/
│   │   ├── result_uuid1.json
│   │   └── result_uuid2.json
│   └── 2026-07-22/
├── dead_letter/                # 死信队列
│   ├── dl_uuid1.json
│   └── dl_uuid2.json
├── processing/                 # 执行中的命令
│   └── cmd_uuid3.json
├── ae_trigger.json             # 触发文件
└── .mcp_secret                 # 签名密钥
```

### 文件命名规范

- 命令文件：`cmd_{command_id}.json`
- 结果文件：`result_{command_id}.json`
- 死信文件：`dl_{command_id}.json`

---

## 向后兼容

### 版本协商

1. 客户端发送命令时携带 `protocol_version`
2. 服务端检查版本兼容性：
   - 主版本号相同 → 兼容
   - 主版本号不同 → 返回 1006 错误
3. 次要版本号向下兼容

### v1 兼容模式

为了平滑迁移，v2 协议支持 v1 兼容模式：

1. 检测到 v1 格式命令（无 `protocol_version` 字段）时，自动转换为 v2 格式
2. v2 响应可配置为 v1 兼容格式输出
3. 过渡期内同时支持两种格式

### 迁移路径

1. **阶段一**：客户端升级，仍发送 v1 格式，服务端同时支持
2. **阶段二**：客户端切换到 v2 格式，服务端仍兼容 v1
3. **阶段三**：确认所有客户端升级后，服务端移除 v1 支持

---

## 附录

### A. 常用命令列表

| 命令 | 说明 | 幂等 |
|------|------|------|
| `ping` | 健康检查 | 是 |
| `get_project_info` | 获取项目信息 | 是 |
| `create_composition` | 创建合成 | 条件幂等 |
| `delete_composition` | 删除合成 | 否 |
| `create_text_layer` | 创建文本图层 | 否 |
| `set_layer_properties` | 设置图层属性 | 是 |
| `apply_effect` | 应用效果 | 否 |
| `execute_script` | 执行脚本 | 否 |
| `import_footage` | 导入素材 | 条件幂等 |
| `render_queue_add` | 添加到渲染队列 | 否 |
| `render_start` | 开始渲染 | 否 |

### B. 参考实现

- Python 客户端：`ae/bridge_protocol.py` 中的 `BridgeClient`
- Python 服务端参考：`ae/bridge_protocol.py` 中的 `BridgeServer`
- AE 端 (ExtendScript)：需基于此规范实现

### C. 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 2.0.0 | 2026-07-21 | 初始版本，标准化协议、错误码、优先级队列、幂等性、重试机制 |
