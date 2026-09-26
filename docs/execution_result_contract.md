---
tags: [契约, 执行结果, 成功语义, 防伪造, 质量治理]
date: 2026-09-26
status: ACTIVE
owner: 修复方案 FIX-01（09-计划文件/2026-09-26_全量问题修复执行方案.md）
based_on:
  - 03-阶段报告/项目文档扫描与模块功能评价_2026-09-24.md §3.2b / §7.0 / §7.0b
  - .trae/rules/evidence-gate-rules.md（闸门①②⑤）
  - docs/ae_bridge_lessons.md §4（产物校验须实测）
---

# 执行结果契约（Execution Result Contract）v1.0

> **一句话**：`success=True` 不是结论，是**待验证的声明**。任何执行结果在进入下游、
> 写入报告、参与退出码之前，必须能回答一个问题——**"这个成功是真实执行，还是仿真替身？"**
> 回答不出者，一律按失败处理（诚实失败纪律，见本契约第 5 节）。
>
> 本契约是 0924 审计确认的 16 条"伪造成功"路径（六类形态 A-F）的根治判据，
> 被 FIX-02~09 全部引用。**关键词检索对本族问题无效**（全库 0 个 stub/FIXME 标记），
> 唯一可靠判别是本契约的结构化标记 + `scripts/scan_untrusted_success.py` 扫描（FIX-09）。

---

## 1. 核心字段定义

任何返回"执行成功"语义的对象（dict / dataclass / Result 对象 / JSON 报告），必须携带：

| 字段 | 类型 | 必填条件 | 取值与语义 |
|------|------|----------|-----------|
| `success` | bool | 总是 | 对外结论字段 |
| `execution_path` | str | **`success=True` 时必填** | `real` = 真实执行且产物经内容级验证；`simulated` = 仿真/占位（仅显式请求）；`fallback` = 走了声明过的降级链（须附 `fallback_reason`） |
| `fallback_reason` | str | `execution_path=fallback` 时必填 | 降级触发原因（如 `"engine_offline"` / `"api_timeout"`） |
| `evidence` | object | 产生文件/数据时必填 | 至少含产物路径 + 一种内容级验证（ffprobe 通过 / SHA-256 / 像素统计 / exists+非空且非占位魔数） |

**判定规则（消费端强制）**：

```
success=True 且无 execution_path        → 不合法，视为失败（抛 UntrustedSuccessError）
success=True 且 execution_path=simulated → 仅当调用方显式请求过 simulate 才可用
success=True 且 execution_path=fallback  → 可用，但必须透传标记，报告不得写成 real
mode_used / result.mode 等状态字段        → 必须如实反映实际执行路径，禁止"内部转
                                            simulate 而字段仍报 real"（C 类形态，本契约定义为最严重违规）
```

## 2. 产物落盘规范（反"存在性欺骗"）

`exists()` / 文件大小 **不构成**成功证据（0924 审计 A 类形态：假产物写在期望路径上，
连磁盘取证都会通过）。因此：

1. **仿真产物禁止占用期望路径**：一律落 `<output_dir>/simulated/<name>` 或文件名加
   `.simulated` 后缀；期望路径上只允许出现真实执行产物。
2. 仿真产物必须携带可识别魔数或同名 `<file>.meta.json`（内容 `{"execution_path":"simulated"}`）。
3. 消费端校验产物的最低标准 = **存在 + 内容特征**（ffprobe 可读 / 魔数非
   `SIMULATED_MATTE`、`AI_VIDEO_SIMULATED_OUTPUT`、`TOPAZ_SIMULATED_OUTPUT`、
   `RESOLVE_GRADED_OUTPUT` 等已知占位串 / 像素统计非纯色块）。
4. 降级链末端不得是 Mock 类："所有真实源不可用"的结果是**显式失败**，不是占位品入池
   （F6 教训：Mock 恒可用 + 消费端只判 success ⇒ 蓝色占位片被剪进成片）。

## 3. 默认值纪律

- 执行模式的**默认值必须是 `real`**（或等价显式失败语义）；`simulate` 只能由调用方
  逐次显式传入，禁止作为类/函数/配置的缺省值。
- `auto` 模式允许存在，但其语义收窄为："尝试 real，失败则**显式报错**或降级到
  **声明过的备源**（`execution_path=fallback`）"——**静默降级到 simulate 是本契约定义的违规**。
- HTTP API / CLI 的 mode 参数同理（B 类形态：默认 auto 即默认吃仿真路径）。

## 4. 进展声明规范（反"从未发生的进展"）

- 循环/流水线体内没有真实执行该动作（训练/渲染/请求）时，**不得**：打印完成、写
  `status=complete`、生成"成功"报告、以退出码 0 结束。
- 注册表/索引类文件（如 `models/model_registry.json`）的每条 `trained/done/active`
  记录必须可被存在性+一致性脚本复验（闸门①）；复验失败自动标 `missing_artifact`。
- 仿真输入驱动的流程（如进化 `--simulate`）产物头部必须强制标注
  `"input_mode": "simulated"`，读者不得将其当作真实执行结论（闸门⑤的 PLAN/READY 分级）。

## 5. 诚实失败样板（既有正面纪律，全仓推广）

优先复用仓库内已确立的模式，宁失败不造假：

| 样板 | 位置 | 行为 |
|------|------|------|
| NotImplementedError 显式化 | `tools/toolchain_manager.py`、`ae/distributed_renderer.py:532` | "诚实失败，而非伪造成功" |
| 拒绝空渲染 | `scripts/build_master_polish.py`（零特效 `sys.exit(3)`） | 上层假绿灯不可接受 |
| 明示不可注入类型 | 同上 `SCHEMA_UNMAPPED` | 静默丢弃会让上层报"139 特效已应用" |
| 可区分降级标记 | `opensource_integrations.py`（`status="simulated"` + `reason`）、各 adapter 的 `simulated_output: True` | **已有标记文化——本契约补的是"消费端强制检查"** |
| 闸门真实 FAIL 披露 | 七关闸门（0926 实践：拦→修→过全链路实证） | 真实 FAIL 优于全绿自夸 |

## 6. 已知违规反例索引（对照 0924 审计 §7.0b 六类）

| 形态 | 反例（修复归属 FIX-xx） | 契约对应条款 |
|------|------------------------|--------------|
| A 伪造产物文件 | `silhouette_executor._create_simulated_output`、topaz/davinci/blender simulate 写期望路径（FIX-03） | §2.1-2.3 |
| B 伪造成功 | `ai/auto_produce.py` step6 硬编码 ok→退出码（FIX-02）；api_server 吞异常回伪指标（FIX-02）；`api/toolchain_api.py` 默认 auto（FIX-02） | §1 判定规则、§3 |
| C 伪装成 real | `tools/unified_tool_integrator.py` `_execute_real` 内转 simulate 不改 mode_used（FIX-06） | §1"状态字段如实反映" |
| D 词汇表不匹配 | 命令名不在 listener 22 条表→必然失败却可能报 processed（FIX-08） | §1 evidence 必填 |
| E 路径分裂 | PR/PS/ME/AU Python 与 JSX 读写不同目录，永不相遇（FIX-07） | §1 无标记=失败 |
| F 守护网空转 | `TestSimulateVsRealContract` 全 skip（FIX-09） | §5 消费端强制 |

> 反例**只作对照，不作免责**：新增代码命中以上任一形态，CI 扫描（FIX-09）直接判违规。

## 7. 白名单与例外机制

- 完全由标准库/确定性计算构成、无"外部执行"语义的函数（纯函数、配置读取等）不在
  本契约范围；判定基准 = 是否可能"声称做了外部工作"。
- 扫描器（`scripts/scan_untrusted_success.py`，FIX-09 落地）白名单条目**必须带理由注释**，
  无理由白名单视同违规。
- 测试夹具中的构造性 `success=True` 不在扫描范围（测试数据非执行结果）。

## 8. 异常与工具映射

| 项 | 值 |
|----|----|
| 违规异常 | `exceptions.UntrustedSuccessError`（注意：**根级 `exceptions.py`**，非 core/；0924 审计"exceptions.py 1,031 行"指根级文件） |
| 错误码 | `ErrorCode.UNTRUSTED_SUCCESS = "E504"`（E5xx 工作流族） |
| CI 执行点 | FIX-09（扫描器 report-only 起步 → 基线清零后转阻断） |
| 消费端接线 | FIX-02（auto_produce/HTTP 默认值）、FIX-05（素材入池白名单）、FIX-06（mode_used 如实化） |

## 9. 版本与修订

- v1.0（2026-09-26）：随 FIX-01 初版发布。修订须同步更新 `tests/test_execution_contract_schema.py`
  的结构断言，并追加"编号+日期"记录到文末。

### 修订记录
- 2026-09-26 v1.0 初版（FIX-01）。方案原文误写 `core/exceptions.py`，实施时实测修正为根级
  `exceptions.py`（本文件 §8 已记录）——即证据闸门④"快照失效即结论失效"的又一实例。
