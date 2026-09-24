# 贡献指南（工程约定）

> 面向在本仓库改代码/写测试的人（含未来的自己）。内容来自实际踩过的坑，
> 每条都注明**为什么**，因为"照着做但不知道为什么"的约定会在第一次赶工时被绕过。
> 最近一次大更新：2026-09-22（覆盖率补测四轮之后）。

---

## 一、提交前必做

```bash
# 1) 跑你改到的那一片（快）
python -m pytest tests/<相关文件> -q

# 2) 跑全量（约 12-15 分钟；改过共享代码就必须跑）
python -m pytest -q --timeout=300 -p no:cacheprovider

# 3) 需要跟 CI 覆盖率作业对齐时，用 CI 同款参数
python -m pytest -q --timeout=300 -p no:cacheprovider --ignore=mcp-extension \
       --cov --cov-branch --cov-report=json:reports/coverage.json --cov-fail-under=29
```

**⚠️ `--timeout=300` 不能省。** 少了它，个别轮询型用例在 coverage 拖慢执行后会**挂住**，
表现为"永远不结束"而不是失败 —— 我们实测卡在 78% 超过 13 分钟，只能手杀进程。

---

## 二、写测试的三条铁律

### 1. 先按「行为」比对既有断言，只写差集

**不要**只 grep"谁 import 了这个模块"，要 grep**你要断言的那个行为**
（函数名 / 配置字段名 / 类名），把同域测试文件全部列出来，逐条比对后才动笔。

- 反面案例：为 `PipelineConfig` 的钳制逻辑写了 57 项，实测覆盖率只动了 **5 行**
  —— 因为 `tests/test_pipeline_config_validation.py` 早已把这一层断言得很完整。
  同样的坑在 `llm_gateway` 上踩过一次（第二次复发）。
- 判断方法：**新写的测试如果覆盖率几乎不动，先去核对是不是出现了重复**
  （但也别反过来只盯覆盖率 —— 见第 2 条）。

### 2. 「被执行」≠「被断言」

行覆盖只说明代码路径跑过，不说明它的**语义**被检查过。
`FLAG=" "`（空白串）走默认分支、而不是当作 falsy —— 这种边界跑一百遍也不会红。

所以：**断言要写"值"，不要只写"不抛异常"**；返回 `None` 的降级路径要断言"就是 None 且没副作用"。

### 3. 枚举/类身份比较（`is`）不可靠 —— 用 `.value`

本套件里有测试会 `importlib.reload()` 生产模块（`tests/test_formal_spec.py` 为验证
"绑定幂等"重载 `pipeline.unified_pipeline`）。`reload` 会**在原模块对象上重跑代码、
换掉全部类对象**，于是：

```python
cfg.detect_mode() is PipelineMode.TEXT_TOPIC   # 单独跑绿，全量跑红！
```

两侧打印一模一样（同名同值），但一个是旧类、一个是新类。
**改为按值比较** `cfg.detect_mode().value == "text_topic"`，对 reload 免疫、也不依赖执行顺序。

---

## 三、覆盖率的正确读法

- **水位与地板**：全量实测 **34.18%**（2026-09-22，6106 passed / 0 failed）。
  ratchet 地板写在 `pyproject.toml` 的 `[tool.coverage.report] fail_under`（= 29，与 CI 的
  `--cov-fail-under` 必须一致，有闸门测试盯着）。**改一处即可同时约束 CI 与本地**。
- **单文件覆盖率有 ±15 行噪声**：增减 A 模块的测试可能让 B 模块的被测行数漂移
  （导入时序 / 追踪附着时机；coverage 自己的 `module-not-measured` 警告即属此类）。
  **只有大幅增量才当战果，±20 行以内不作结论。**
- **剩余未覆盖多为编排/集成层**（`production_director` / `unified_pipeline` /
  `flagship_runner` 的 stage_*）。这类要靠**集成测试**（真实素材 + 引擎在场）来提升，
  再切纯函数的边际收益很低。
- **看"该补哪里"用快照**：`python scripts/coverage_summary.py`（把 6MB 原始报告压成 4KB
  摘要：按包、未覆盖最多的文件、god 文件专项）；快照入仓在 `reports/coverage_summary.json`。

---

## 四、安全扫描器（Mimosa）误报怎么处理

它会在写入源码/测试时做静态检查，**测试数据也会被审视**：

| 触发 | 处理 |
|------|------|
| 测试里出现形似真凭据的串（如 AWS 文档的示例 key 会按"硬编码凭据"拦） | 换低熵合成值（`just-a-test-value`），变量名也别带 `SECRET/KEY/TOKEN` 语义 |
| 命令列表里出现变量/字典取值（被判"命令注入"） | 测试夹具用**全字面量命令行**，不做字符串插值 |
| 提示 MD5 弱算法 | 若用途是**指纹**（缓存/去重）而非安全原语，**保留并写明理由** —— 换算法会改变既有调用方比对的摘要值，属行为变更而非修复 |

---

## 五、手上有的可复用设施（别重复造）

| 工具 | 用途 |
|------|------|
| `scripts/coverage_summary.py` | 覆盖率快照（按包 / 最差文件 / god 文件） |
| `tests/test_ci_config_consistency.py` | 配置一致性闸门（fail_under 单一真相源、CI 产物、source 覆盖核心包） |
| `tests/test_syspath_hygiene.py` | sys.path 膨胀防回涨（重复条目/唯一数上界/不得写死配置） |
| `scripts/beat_anchor_check.py` | 成片**切点**落鼓点率（真实 stem 锚点） |
| `scripts/punch_beat_check.py` | 成片**运镜撞击**落点、包络占空比、**包络完整度**（撞击 N 次里几次真播完；`--no-envelope-fit` 可复刻 2026-09-23 之前的排程以对比历史数字） |
| `scripts/check_delivery_spec.py` | 交付规格（含"音视频等长"这项缺陷探针） |
| `scripts/ae_channel_status.py` | AE 三轨通道客观盘点（含监听器解析实测） |
| `scripts/log_acceptance.py` | 听感/A-B 裁决入日志（R8③ 数据前置） |
| `scripts/rule_registry.py` | 规则库生命周期（seed/vote/retire + 适用域校验） |

---

## 六、报告习惯（本项目特有）

- **先测再改**：定位问题先拿客观数据（磁盘/进程/实测指标），别只读文档自述。
  文档会过时 —— `TASK_STATUS.md` 在 2026-08-31 后冻结，引用其状态前先核实磁盘。
- **战果要能复跑**：每个结论配一条能重跑的命令与落盘证据（报告/json）。
- **反例也要留档**：测出来的"不达标"比"达标"更值钱（例如单源占比 10% > 声明的 8%），
  数值与阈值一起记进报告，别只写结论。
- **别把"声明"当事实**：`_probe_duration` 失败回退 60.0 这类隐患，
  写测试**锁住现状**并注明是隐患，而不是假装它安全。

---

*相关：`.github/workflows/quality-hardening.yml`（覆盖率作业注释里有同样的要点）·
`03-阶段报告/覆盖率补测第 1-4 轮报告_2026-09-2x.md`（这些结论的实测出处）*
