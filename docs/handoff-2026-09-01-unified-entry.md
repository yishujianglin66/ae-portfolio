# 交接附录 G — 统一编排 + AE 拉近通道 + 真实卡点（2026-09-01 全天，最新权威）

> 本附录覆盖 2026-09-01 全部工作。前置状态见附录 F（多段成片）与每日记录 05。
> 接手第一动作：读本文档"当前主线"与"下一步"两节，其余按需查。

---

## 一、当前主线状态（一句话）

**统一编排入口 `scripts/unified_edit.py` 已建成跑通**（运镜标注+V23引擎+LUT+SFX+评分 五能力合体），
**真实卡点修复已固化**（SFX 对齐引擎真实切点），**AE 拉近通道打通到 90%**（桥接协议补丁已写好编译过，
`enable_ae_channel=True` 的全链重跑被中断——这是接手第一件事）。

---

## 二、今日全部任务时间线

### 2.1 上午：V23 基线复现（用户指令: 用 V22/V23 素材重新编排）

| 事项 | 结果 |
|---|---|
| V22/V23 资产考古 | `tmp/render_v23_test.py`（V23 引擎调用）/`tmp/render_v22.py`（双通道版）；素材池 7 视频+BGM 全在盘（清单在脚本内） |
| V23 复现第一次 | `enable_ae_channel=True` → 桥接单线程被占死 → python 闲置（CPU 5 分钟 +0.1s）→ **决策: 关 AE 通道走纯 ffmpeg** |
| V23 复现第二次（纯 ffmpeg） | ✅ 出片 `D:/output_director/solo_pilot/v23/v23_ffmpeg_baseline.mp4`（125MB/19.4s，叙事一致性 0.75=6/8 镜头匹配主题） |
| V23.5 质感增强 | LUT 好莱坞 0.55 + SFX 18 落点 → `output/v23_5/v23_final.mp4`，零黑帧，dynamism 8.05/overall 7.28/pacing 7.73/texture 5.26 全超人工标尺 |

### 2.2 用户批评（关键转折）："训练任务到底有没有融入编排系统？"

诚实盘点结论：**训练成果（CNN头/GBDT/VLM运镜/节奏库）此前从未接入出片流程**——每次出片都是临时手拼。
→ 建统一编排入口 `scripts/unified_edit.py`（用户核心诉求的落地）。

### 2.3 下午：统一入口首轮全链 + 三个断点修复

**首跑（--tag first）遇到的三个断点，全部修复：**

1. **`resources/` 目录整体丢失**（与五模块残废覆盖同期的破坏，LUT/SFX/贴图三索引全指向它）
   → `mklink /J resources D:\AE-Work\resources` junction 重链
   → `python scripts/build_sfx_index.py`（8672 音频扫描→四池）
   → `python scripts/build_fx_asset_index.py`（14 类 420 张）
2. **bitsandbytes 没装主 python**（只在旧 venv 有）→ VLM 4bit 加载链崩（bf16 OOM→offload→段错误）
   → `pip install bitsandbytes`（0.50.2）；验证：主 python 4bit 加载 38s / 6.25GB VRAM
3. **CNN 评分头丢失** → 从嵌入重训（`python -m core.cnn_scorer --train`，140 样本）
   → 黄金标定重写（`python scripts/calibrate_cnn_head.py --write`，改善 25.8%）

**首跑结果**：`output/unified_first/unified_first.mp4`（115MB，运镜标注 7/7 成功——
source=videomae-lora-fine，**LoRA 分类器在出片流程首次真实运行**）

### 2.4 LLM 多模型自动切换链（用户指令: 额度用完自动切，不断层）

- **背景**: DashScope qwen-vl-max 403 `AllocationQuota.FreeTierOnly`（免费额度耗尽，key 有效）
- **建成** `core/llm_chain.py`：链序 DashScope→SiliconFlow Qwen3-VL-32B→8B→(ModelScope 待新 token)
  - 403/429 节点自动拉黑 30 分钟（`data/llm_chain_state.json`），过期自动重试 → **充值后无需改代码自动回主链**
  - 错误分级：额度错拉黑 / 5xx 瞬时跳过 / 网络错跳过
  - `visual_scorer._call_qwen_vl` 的 403/429 分支已接 `vision_call()`
- **四态 E2E 全过**：正常（dashscope 403→sf32b 瞬时500→sf8b 成功读图）/黑名单/恢复/混合评分
- **注意**: SiliconFlow 现役模型名是 **Qwen3-VL 系列**（Qwen2-VL 旧名 20012 不存在）；
  Qwen3-VL 拒绝 <28px 图（测试图会 400，模型本身正常）
- 另: LLMGateway 的 claude key（DUCK_MISS）已失效 403（账号池耗尽），check_llm_keys 会自动熔断

### 2.5 BGM 丢失事故（用户: "没bgm了"）

- **根因链**: V23 引擎出片自带 BGM → `transcode_with_lut` 内部 **`-an` 静默剥音轨** → SFX 在无声底上混
- **修复**: LUT 改 `-vf lut3d` + **`-c:a copy`**；大文件(>50MB)先压再挂；SFX 分批直混
  （amix 坑：**inputs 必须写 N+1**——BGM+N 音效，写 N 报 label 过多）
- 修复版 `output/unified_first/first_final2.mp4`（BGM+27音效 -10.8dB）已打开验证
- **已固化**进 unified_edit.py（LUT 段/SFX 段全重写）

### 2.6 真实卡点修复（用户: "卡点如何继续优化"）

- **根因**: SFX 用 0.7s 均匀假拍，画面切点却是 BGM 节拍对齐的不等间隔 → 两套时间听感不卡
- **真实切点来源**: `production_report.json → script.segments[].start_time`（29 镜头:
  `[1.5, 1.96, 2.54, 3.17, 3.75...]`，间隔 0.46-1.17s）
- **修复**: SFX 落点=真实切点；mood 映射（drop/climax→impact 0.85，build→whoosh 0.55，intro→轻 0.4）
  → `output/unified_first/first_final3.mp4`（28 落点）已打开验收
- **已固化**进 unified_edit.py（读 production_report，无则降级假拍）

### 2.7 AE 拉近通道打通（用户: "拉近训练没看到体验，是不是纯 ffmpeg"）

- **确认现状**: 是纯 ffmpeg（zoompan 2D 数字缩放）；训练的运镜成果只用在素材标注层
- **V22 双通道架构还在**: `ai/ae_render_channel.py`（JSX→贝塞尔缓动关键帧+运动模糊→aerender 进程外渲染）
- **根因定位（已 100% 修复，协议层全打通）**: 该模块发 `runScript`+`{file:...}`，但监听器白名单只有
  **`executeAtomScript`+`args.script`**（内部 `new Function(scriptStr)` 只吃脚本字符串）→
  AE 通道历史上从未真正走通（一直静默 fallback ffmpeg）
- **本次修复全部已验证**（除真实 AE 渲染需 AE 交互模式运行）：
  1. `runScript` → `executeAtomScript` ×3 处（构建/探测/关工程）
  2. jsx 文件读全文传 `args.script` + **`args.scriptContent` 双字段**（兼容主监听器 `ae_mcp_listener.jsx` 与 bg_listener `ae_mcp_bg_listener.jsx`）
  3. **HMAC 签名**（监听器 `SIGNATURE_ENABLED=true` fail-closed，无签名拒绝）→ 已生成项目根 `.mcp_secret`，离线验证 Python HMAC == JS `_canonicalize`（`tmp/_verify_bridge_sig.py`）
  4. **BOM 剥除**（JSX 文件带 BOM 供 ExtendScript 识别中文，但 eval 字符串不能带 `\ufeff`）
  5. **ping 改 executeAtomScript 探测**（监听器白名单无 ping 分支）
  6. **结果文件双读**（`ae_result.json` 主监听器 + `ae_mcp_result.json` bg_listener）
  7. **快速降级**：AE 未运行时不自动启动（防弹窗/崩溃），0.1s 内 fallback ffmpeg（修复"卡这一步骤 4 小时"根因）
  8. **JSX 无禁止模式**（`system.callsystem`/`$.evalfile`/`new function(`/`.execute(` 全安全）
- **验证工具**: `tmp/_ae_channel_selfcheck.py` — AE 交互模式运行 + 监听器驻留后一键自检完整链路
- **⚠ 唯一待办**: AE 以交互模式启动 + 监听器驻留后跑 `python tmp/_ae_channel_selfcheck.py`，再开 `enable_ae_channel=True` 重跑

---

## 三、当前文件地图（今日产物）

| 文件 | 内容 |
|---|---|
| `scripts/unified_edit.py` | **统一编排入口**（五能力合体; 已含 BGM 保轨+真实卡点修复） |
| `core/llm_chain.py` | 多模型自动切换链（403 拉黑 30min）— **本次重建并 E2E 验证四态** |
| `core/visual_scorer.py` | 已接 llm_chain（403/429 分支）— **本次接线并验证 score_frames 降级链** |
| `ai/ae_render_channel.py` | **桥接协议全打通**（executeAtomScript/script+scriptContent/HMAC签名/BOM剥除/ping改探测/双结果文件/快速降级） |
| `core/paths.py` | 从 git 恢复（此前被误删，ae_render_channel 依赖） |
| `.mcp_secret` | 项目根签名密钥（监听器 fail-closed 必需，已生成） |
| `tmp/_verify_bridge_sig.py` | 签名一致性离线验证（Python HMAC == JS canonicalize） |
| `tmp/_ae_channel_selfcheck.py` | AE 通道一键自检（AE 就绪时跑） |
| `output/unified_first/` | 统一入口首跑全套：unified_first.mp4(115MB 原片) / first_lut2.mp4(LUT+音轨) / **first_final3.mp4(真实卡点终版)** / unified_report.json / production_report.json(真实切点在这) |
| `output/v23_5/v23_final.mp4` | V23.5 质感版（4 维超人工标尺） |
| `data/sfx/index.json` `data/fx_assets/index.json` | junction 后重建的索引 |
| `00-每日记录/2026-08-27_05-*.md` | LLM 链/BGM 事故/统一入口全记录 |

---

## 四、踩坑清单（今日新增，接手必读）

| # | 坑 | 规避 |
|---|---|---|
| 1 | AE 桥是**单线程**：长 JSX 执行时 ping/查询全排队等死（seg10/11 卡 4h+ 的根因） | 大树走分批+批间验层数（`synthesis_orchestrator.build_batches`+`_wait_batch_applied`）；或纯 ffmpeg |
| 2 | 监听器白名单**只有 executeAtomScript**（runScript → Unknown command） | 一切桥接命令用 executeAtomScript+args.script |
| 3 | `executeScript=new Function(str)` **不吃 {file}** | 必须传脚本全文字符串 |
| 4 | `transcode_with_lut` 的 `-an` **静默剥音轨** | 带乐成片一律 `-vf lut3d`+`-c:a copy` |
| 5 | ffmpeg **amix inputs=N+1**（BGM+N 音效），写 N 报 label 过多 | 分批混（每批≤14）+ 计数+1 |
| 6 | 大文件（>50MB）直挂 LUT/SFX **超时** | 先 `crf 20` 压到 ~12MB（保音轨 copy） |
| 7 | SiliconFlow 模型名是 **Qwen3-VL** 系（旧名 20012）；<28px 图 400 | 测试用真实帧 |
| 8 | `resources/` 是 **junction 指向 D:\AE-Work\resources**（本体重链，勿删） | 若 LUT/SFX 又"无可用"先查 junction |
| 9 | bitsandbytes 必须**主 python 有**（bnb 在才走 4bit，否则 bf16 OOM 崩） | `python -c "import bitsandbytes"` 自检 |
| 10 | 数学字母文件名素材（𝘿𝙞𝙚 𝙁𝙤𝙧 𝙔𝙖𝙣.mp4）在大批导入时**挂起 AE** | 已从两脚本换掉；勿加回 |
| 11 | AE 强杀引发崩溃恢复弹窗+prefs 损坏连锁 | 标准重启流程（附录D 六节）；先 AppActivate+ESC 唤醒 |
| 12 | CEPHtmlEngine（Adobe CC 后台）吃 3.8GB→页面文件耗尽→评分崩（os error 1455） | 渲染+评分前 taskkill CEPHtmlEngine |
| 13 | 监听器 `SIGNATURE_ENABLED=true` **fail-closed**：无签名命令直接拒绝 | 命令带 HMAC 签名（项目根 `.mcp_secret`，Python/JS canonical 已对齐） |
| 14 | `AfterFX.exe -r script.jsx` **不是驻留模式**：脚本执行完进程退出，监听器无机会轮询 | 监听器需在 AE 交互模式内驻留（File > Scripts 或 Startup） |
| 15 | `core/paths.py`、`core/llm_chain.py` 等**曾被误删**（文件地图有但磁盘无） | 已从 git 恢复 paths.py / 重建 llm_chain.py；改动前先 `git status` 查 |
| 16 | AE 未运行时会**自动启动+90s 硬等**（弹窗/崩溃风险+拖慢流程） | `_ensure_ae_running(auto_launch=False)` 默认快速降级（0.1s），不自动启动 |

---

## 五、下一步（接手任务清单，按优先级）

### ①【第一优先】AE 拉近通道最终验证（协议层已全打通，只剩 AE 就绪后一键自检）
```bash
# 1. AE 以交互模式启动 + 监听器驻留（File > Scripts > ae_mcp_listener.jsx，
#    或标准流程: 重启→5-8分钟→AppActivate+ESC唤醒）
# 2. 一键自检完整链路（签名→executeAtomScript 探测→结果文件）:
python tmp/_ae_channel_selfcheck.py
#    预期输出: [OK] 签名一致性 / [OK] executeAtomScript 探测成功 / ✅ 通道协议链路完整可用
# 3. 自检通过后开 AE 通道重跑:
#    scripts/unified_edit.py 里 enable_ae_channel=False 改 True（render 调用处）
#    python scripts/unified_edit.py --tag aechan
# 4. 验收: 日志出现 "[AE通道] N个高级运镜镜头" 且 "成功渲染 N/M 镜头";
#    成片 zoom 镜头应有贝塞尔缓动+运动模糊（对比 v23 ffmpeg 版可辨）
# 5. 若 AE 未运行: 现在会 0.1s 快速降级 ffmpeg（不自动启动、不卡流程、不弹窗）
```

**协议层已全部修复并验证**（`ai/ae_render_channel.py`）：
- executeAtomScript + script/scriptContent 双字段（兼容两个监听器）
- HMAC 签名（`.mcp_secret` 已生成，Python/JS 签名一致性离线验证通过）
- BOM 剥除 / ping 改探测 / 双结果文件读取
- **AE 未运行 0.1s 快速降级**（不再卡 4 小时）

### ② 卡点进一步优化（真实切点已对齐，剩下三招）
1. 音效**前置 30-50ms**（瞬态到达延迟补偿，人工剪辑惯技）：`adelay={t*1000-40}`
2. BGM onset 层（引擎检测到 84 个 onset vs 29 切点）：drop 段加半拍轻音效
3. 重拍双层（kick 切点=impact+低频 boom 叠加）

### ③ 用户反馈观察项（看完 first_final3.mp4 待用户评价）
- 真实卡点版听感是否改善
- 粒子/文字粗糙问题（历史 PRO 资产移植方案在每日记录 05 第三节，未开始）

### ④ 长期（附录 E/F 遗留）
- 监听器断链根治（心跳自检+自动重注册）
- multisegment 桥接路线 vs 统一入口路线**二选一收敛**（建议保留统一入口）
- ModelScope 换 token / 豆包开接入点（入 llm_chain 第 4/5 节点）

---

## 六、能力-训练融合现状总表（用户最关心的）

| 训练/建设成果 | 接入出片流程状态 |
|---|---|
| VLM 运镜分类器（4bit 本地） | ✅ unified_edit 能力② 每素材打标签（首跑 7/7） |
| CNN 评分头+黄金标定 | ✅ unified_edit 能力⑤ 成片评分 |
| LUT 41 主题库 | ✅ 能力④ 按风格卡选主题 |
| SFX 四池（8672 扫描） | ✅ 能力④ **真实切点对齐**（2.6 修复后） |
| V23 编排引擎（节拍/高光/变速/品味卡） | ✅ 能力③ 主干 |
| 多模型评分链 | ✅ 403 自动切 SiliconFlow |
| 节奏库（人工 1.2/s） | ⚠ 部分（SEGMENT_PROFILES 用过；统一入口走引擎自身节奏） |
| GBDT 调参器 | ❌ 未接入（两阶段推荐退化解锁需 AE 新参数方差） |
| LoRA 拉近渲染（贝塞尔+运动模糊） | 🔶 **90%**——协议补丁已应用，差 ① 的验证重跑 |
| 光流运镜标签库（58 条） | ❌ 未接入（三角验证证明与 VLM 语义分歧，先挂起） |

---

## 七、快速验证命令

```bash
# 1. 回归（应 3 passed）
python -m pytest tests/test_gold_benchmark.py -q
# 2. 统一入口出片（纯 ffmpeg，~15-70 分钟）
python scripts/unified_edit.py --tag <名字> --bgm <BGM.mp3> --theme "<主题>"
# 3. LLM 链状态（本次重建，四态 E2E 已验证）
python -c "import sys; sys.path.insert(0,'.'); from core.llm_chain import chain_status; import json; print(json.dumps(chain_status(), ensure_ascii=False))"
# 4. AE 通道一键自检（AE 交互模式 + 监听器驻留后跑）
python tmp/_ae_channel_selfcheck.py
# 5. 真实切点查看
python -c "import json; pr=json.loads(open('output/unified_first/production_report.json',encoding='utf-8').read()); print([round(s['start_time'],2) for s in pr['script']['segments']])"
```

---

## 八、一句话给接手者

统一编排入口已把"训练成果接入出片"从 0 做到 8/10；真实卡点与 BGM 两大听感修复已落地；
**AE 拉近通道协议层已全打通**（executeAtomScript+签名+BOM+快速降级，见第五节①）——AE 交互模式运行后跑
`python tmp/_ae_channel_selfcheck.py` 通过即开 `enable_ae_channel=True` 重跑，LoRA 拉近训练就完整呈现了。
LLM 多模型自动切换链已重建并 E2E 验证（DashScope 403 → 自动降级 SiliconFlow Qwen3-VL-32B 成功读图）。
