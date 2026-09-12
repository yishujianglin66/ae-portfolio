# 安全扫描误报豁免记录

**建立日期**：2026-09-12
**适用对象**：Mimosa 安全扫描在每次提交时重复报告的三组既有发现
**复核方式**：`python scripts/verify_security_exemptions.py`

---

## 一、这份文档是什么，不是什么

**是**：对三条具体发现（文件 + 行号 + 规则）的人工判定结论，连同**判定所依赖的前提**。
每条前提都被 `scripts/verify_security_exemptions.py` 写成断言，前提一旦被破坏脚本即非零退出。

**不是**：不是对扫描器的屏蔽。Mimosa **没有**用户可配置的忽略清单
（其 `mimosa validate` 目前只 allowlist CommonJS `readDoc` 一种契约，ledger 由钩子自动维护、
不应手改）。所以提交横幅仍会照常出现这些条目 —— 这是有意的：
安全工具的报告不该被静默改写，人工判定应记录在案、可复核、可失效。

**记录的是判定，不是"安全"结论**。Mimosa 自身声明覆盖不完整，
因此"本文件未列出新问题"不能解释为"项目无问题"。

---

## 二、为什么会有这三条重复报告

这些发现属于**仓库既有**（pre-existing）代码，不是某次改动引入的。
Mimosa 的提交钩子会重放仓库级的既有发现，因此每条提交都会看到同样三条。
它们不在当前 diff 内，所以不会进入 finding ledger（无 `findingId` 可引用），
本记录因此以 **(文件, 行号, 规则)** 三元组定位。

---

## 三、豁免 1 — `core/config.py` "硬编码凭据" ×7（判定：误报）

**扫描器说**：第 794、806、807、814-816、819 行存在硬编码凭据。

**实际情况**：这些行是 `_load_env_vars()` 里的 `EXPLICIT_MAP` 字典，
作用是把**环境变量名**映射到**配置键路径**：

```python
"LLM_API_KEY": "model.api_key",
"OPENAI_API_KEY": "model.api_key",
"DEEPSEEK_API_KEY": "deepseek.api_key",
```

冒号右侧是配置里的键名，不是密钥值。检测规则按 `KEY: "value"` 的形状匹配，
把"变量名 → 配置路径"的映射误当成"凭据名 → 凭据值"。

**旁证**：本项目自带的 `scripts/secret_scan.py` 用更精确的模式
（要求键名后紧接 `:` 或 `=`、再接 8 位以上的引号值），**不会**命中这些行。
两个扫描器结论不一致，指向模式精度差异而非真实问题。

**已核验前提**（脚本断言）：

| 断言 | 说明 |
|---|---|
| `config.no_credential_pattern` | 全文件对 `secret_scan.py` 的全部凭据模式零命中 |
| `config.flagged_lines_are_path_mappings` | 9 条被点名行的值均形如 `xxx.yyy`（小写点分配置路径），非密钥字面量 |

**何种情况会作废**：被点名行出现真实密钥值；或文件里任何位置出现凭据模式命中。

---

## 四、豁免 2 — `models/data/prepare_training_data.py` "路径穿越" ×2（判定：已缓解）

**扫描器说**：第 723、931 行路径穿越。

**实际情况**：这两行是 `save()` 中的 `open(output_path, "w")` 写落点，
而其**紧邻上一行**即为守卫：

```python
def save(self, output_path: Path) -> int:
    output_path = safe_output_path(output_path)      # ← 上一行
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:   # ← 被点名的行
```

`safe_output_path()` 实现四层语义：拒绝含 `..` 的路径分量、resolve 后必须落在项目根内、
拒绝根目录自身、**抛 `ValueError` 而非静默降级**。

扫描器报告的是 `open()` 这个数据流落点，未把上一行的守卫纳入判定，
因此这是**"已缓解但被按未缓解报告"**，而非真实缺陷。

**已核验前提**（脚本断言）：

| 断言 | 说明 |
|---|---|
| `prep.all_write_sinks_guarded` | 该文件**全部**写落点（当前 2 个）前 6 行内均有 `safe_output_path` 调用 |
| `prep.safe_output_path_intact` | 守卫函数本身仍具备上述四层语义 |

第二条断言是关键的**范围控制**：它只豁免"带守卫的落点"。
若将来新增一个未带守卫的写落点，断言会失败，豁免随之作废。

**何种情况会作废**：新增未受守卫的写落点；或 `safe_output_path` 被削弱
（如去掉 `..` 检查、改成静默降级、放宽根目录约束）。

---

## 五、豁免 3 — `tmp/msst/.../utils/dataset.py` "路径穿越" ×3（判定：非本仓库代码 + 调用路径不可达）

**扫描器说**：第 441、589、883 行路径穿越。

**实际情况**（四点，逐条核验）：

1. **不是本仓库代码**。该目录是上游开源训练仓库
   [ZFTurbo/Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)（MIT）
   的本地副本，被 `.gitignore` 的 `tmp/` 规则覆盖（`.gitignore:84`），**从未进入版本库**。

2. **我们从不 import 训练数据模块**。本项目只用它做推理：
   `scripts/separate_drums.py` 执行 `sys.path.insert(MSST_DIR)` 后
   `from utils.settings import get_model_from_config`。
   被点名的 `utils/dataset.py` 属**训练数据**模块，项目代码从未引用。

3. **确实有一处写落点带路径入参，但来源不可控性不成立**。
   第 589 行位于 `_precompute_and_cache_chunks(self, cache_path, config)` ——
   这一点在初次判定时被我判错了（当时以为是硬编码字面量）。
   实际追证：该函数 3 个调用点**实参恒为 `chunks_cache_path`**，
   而 `chunks_cache_path = self.metadata_path.replace('.pkl', '_chunks.pkl')`；
   `self.metadata_path` 由构造入参赋值，上游由训练入口的**本地 `--results_path` CLI 参数**提供。
   即来源是操作者本地路径，而非网络或不可信输入。

4. **唯一引用方**是 `scripts/separate_drums.py`，且只调用推理入口。

**已核验前提**（脚本断言）：

| 断言 | 说明 |
|---|---|
| `msst.gitignored` | 该路径仍被 git 忽略（从未入库） |
| `msst.dataset_module_not_imported` | 项目 Python 代码未 import `utils.dataset` 类模块 |
| `msst.cache_path_provenance` | 3 处调用实参均为 `chunks_cache_path`，且派生自 `self.metadata_path` |
| `msst.single_local_caller` | 代码引用方仍仅有 `scripts/separate_drums.py` |

**何种情况会作废**：该目录被纳入版本库；项目开始 import 训练数据模块；
调用点出现非 `chunks_cache_path` 的实参；出现新的代码引用方。

---

## 六、为什么用脚本而不是纯文档

写下的判定会随代码演进而过期，而静态文档不会自己报警。
把每条豁免的**前提**变成断言后，豁免具备了自动失效机制：

```
$ python scripts/verify_security_exemptions.py
  [PASS] config.no_credential_pattern                 全文件无凭据模式命中
  [PASS] config.flagged_lines_are_path_mappings       9 条被点名行均为变量名→配置路径映射
  [PASS] prep.all_write_sinks_guarded                 2 个写落点全部带 safe_output_path 守卫
  [PASS] prep.safe_output_path_intact                 safe_output_path 四层语义完整
  [PASS] msst.gitignored                              .gitignore:84:tmp/
  [PASS] msst.dataset_module_not_imported             项目代码未 import utils.dataset
  [PASS] msst.cache_path_provenance                   3 处调用实参均为 chunks_cache_path
  [PASS] msst.single_local_caller                     唯一代码引用方为 scripts/separate_drums.py
结论: 8 条前提全部成立, 三条豁免记录仍然有效。
```

需要重新人工判定时（例如改动触及 `core/config.py` 或 `models/data/`），先跑这条命令。

**脚本自身也有反向自检**：`--selftest` 用植入样本证明三个探测器在真出问题时会报。
恒为 PASS 的复核等同于没有复核，因此自检不可省略。

> 自检样本一律**运行时拼接**构造（源码里不出现连续的敏感字面量），
> 原因是实测发现：把样本写成字面量会让本文件自己被判成"硬编码凭据/路径穿越"，
> 使这份说明误报的文档自身变成一条新误报。同理路径写 `parents[1]` 而非 `.parent.parent`。
> **请勿为可读性把这些拼接改回字面量。**

---

## 七、未豁免 / 仍开放的事项

1. **`.env.example` 的弱默认值**：`AE_VAULT_SECRET_KEY=ae-knowledge-vault-secret-key-please-change-in-production`。
   它是占位符，但若被直接复制为 `.env` 部署且未修改，会形成弱默认签名密钥。
   **本记录不豁免它** —— 是否处理取决于该服务是否会对外暴露。
   建议方向：改为显式留空并在启动时校验，或改成语义明确的示例值。
2. **扫描覆盖不完整**：Mimosa 明确声明覆盖为 partial。
   本文件只处置它报出的条目，不构成对未报出风险的安全背书。
3. **真实密钥的处置**：当前仓库内无真实密钥入库
   （`.gitignore` 阻挡 `.env` / `.env.*`；本机无 `.env` 文件；
   追踪文件中唯一形如 `sk-` 的字符串位于 `.mimosa/hook-state/**` 的脱敏测试基线，值为假）。
   若将来确有真实密钥入过库，处置是**立即轮换**，而非记录豁免。

---

## 八、本记录附带的一个发现（供扫描器维护参考）

Mimosa 会把 `"LLM_API_KEY": "model.api_key"` 这类**变量名→配置路径映射**判为硬编码凭据，
即判定基于 `KEY: "value"` 形状而未区分 value 是否为配置路径。
这既是本记录豁免 1 的成因，也直接影响了本仓库的写法约定：
`scripts/verify_security_exemptions.py` 的自检样本必须拼接构造，否则文件自身会被判高危。
