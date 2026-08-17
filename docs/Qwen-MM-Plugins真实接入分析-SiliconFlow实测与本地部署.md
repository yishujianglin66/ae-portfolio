# Qwen-MM-Plugins 真实接入分析 — SiliconFlow 实测 + 本地部署可行性

> **创建**: 2026-08-13 | **状态**: SiliconFlow 通道已修复可用；本地部署待决策
> **核心结论**: Qwen3-VL 视觉理解已通过 SiliconFlow 真实跑通（识别动漫战斗/紧张/释放技能），
> 成本极低（¥0.08/千镜）。本地 8GB VRAM 能跑但慢，**API 路线当前最优**。

---

## 一、问题：Qwen-MM-Plugins 到底投入运行了吗？

**结论：之前没有真实运行**。三个层面实测：

| 层面 | 状态 | 证据 |
|------|------|------|
| llm_gateway qwen provider | ❌ 未启用 | 代码注册了，但 `.env` 无 `QWEN_API_KEY`，`providers` 实测为空 |
| QWEN_PRIORITY_TASKS | ❌ 死代码 | 需 `AEKV_QWEN_PRIORITY=true` + qwen provider 存在才生效 |
| SiliconFlow Qwen3-VL 通道 | ❌ 一直 400 | MIME 硬编码 JPEG bug |

**但用户只有 SiliconFlow key → 修正 MIME bug 后，Qwen3-VL 真实跑通了**。

---

## 二、修复 + 实测（本次完成）

### 根因
`build_frames_content_parts` 把图片 MIME 硬编码 `image/jpeg`，抽帧实际是 PNG 时 SiliconFlow 返回 400。

### 修复
从 base64 头嗅探真实 MIME：`/9j/`→jpeg，`iVBOR`→png。

### 实测（真实动漫帧）
```
输入: 独自升级2.mp4 抽2帧
输出: {"scene_type":"战斗","mood":"紧张","action_type":"释放技能","visual_style":"动漫"}
tokens: 193 (prompt 158 + completion 35)
```
**Qwen3-VL-8B 正确识别动漫画面语义**——这正是 Stage 2 素材-叙事匹配需要的"素材语义"能力。

---

## 三、成本对比（实测 + 官方价）

| 方案 | 单次(2帧) | 千镜 | 备注 |
|------|-----------|------|------|
| **SiliconFlow Qwen3-VL-8B (API)** | ¥0.00008 | **¥0.08** | ✅ 已实测可用，即开即用 |
| 本地 Qwen3-VL-2B (Ollama) | 电费 | 约¥0.5/天 | 需装 Ollama + 下载模型 |
| 本地 Qwen3-VL-8B INT4 | 电费 | 约¥0.5/天 | 8GB 吃紧，推理慢 |
| ARK 豆包视觉 (已有) | 更低 | — | 已配 key，另一可用通道 |

**结论：SiliconFlow API 成本近乎免费（¥0.08/千镜），本地部署无成本优势**（省的钱 < 装模型的时间 + 推理慢的代价）。

---

## 四、本地部署可行性（8GB VRAM 诚实评估）

| 模型 | 显存 | 可行性 | 速度 | 结论 |
|------|------|--------|------|------|
| Qwen3-VL-2B (INT4) | ~1.5GB | ✅ 能跑 | ~20tok/s | 慢但可用 |
| Qwen3-VL-8B (INT4/AWQ) | ~5-6GB | ⚠️ 吃紧 | ~5-8tok/s | 8GB 很慢 |
| Phi-4-multimodal | ~6GB | ⚠️ | 慢 | 需减显存占用 |

**本地真正价值**：无网络依赖 + 隐私（素材不出本机）。但本项目素材都是本地动漫，无隐私顾虑，**API 完全够用**。

---

## 五、落地建议

**当前最优：用 SiliconFlow Qwen3-VL（已修好）作为 VLM 视觉通道主力**，做 Stage 2 素材-叙事语义匹配。

**可选的本地增强（长期）**：装 Ollama + Qwen3-VL-2B 作离线兜底（网络断了还能跑），但不作为主通道。

---

## 六、下一步（Stage 2 素材-叙事匹配）

1. **用 Qwen3-VL 给素材帧打语义标签**（mood/scene_type/action_type）——已实测可行
2. **叙事角色（铺垫/蓄力/爆发/收尾）→ 匹配对应语义素材**
   - 铺垫段 → 匹配 mood=calm/dark 的素材
   - 爆发段 → 匹配 action_type=fighting/scene_type=battle 的素材
3. **对比验证**：主题驱动的素材选择是否让"镜头表达意图"而非杂乱

---

## 关键文件
- `ai/material_intelligence.py` — VLM 三通道（DuckMiss/SiliconFlow/ARK）+ 修复后的 MIME
- `core/llm_gateway.py:880` — qwen provider 注册（需 `QWEN_API_KEY` 启用，当前未用）
