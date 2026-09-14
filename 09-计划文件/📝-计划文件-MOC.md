---
tags: [MOC, 计划]
---

# 计划文件

## 当前执行方案

- [[2026-09-11_管线集成与Skill封装落地方案]] — 基于 41 源外部调研（`DEEP_RESEARCH_视频管线集成与Skill封装.md`）+ 代码实读：EDL 桥三段扩展(effects/text_events/overlays) + 集成顺序 Step0-5 + Skill 卡片粒度(按效果类型×功能域) + SemVer/in-toto/单一真源版本维护 · status: PLAN（集成咽喉期主方案）
- [[2026-09-11_文字高级化_描边体系与三维层推进方案]] — 文字线 v11 过 Boss 验收后的能力边界探针实证（图层样式/文字挤压脚本门控不可启用、动画器描边可用、摄像机方案实测否决、高级 3D 渲染器默认）+ W1-W4 波次（描边体系/三维层 Z 纵深/高级 3D/叙事化分级）· status: PLAN（文字线现行子方案）
- [[2026-09-10_多线整合全面推进计划]] — 综合 09-09/10 实际进展（R1 钳制/R3 满分/R4 修复/木偶线闭环/测试清零）重新校准的统一计划：新增缺口 K1-K10（文字线停滞/R1 残余未定性/双链无桥/证据未入库等）、波次 0-4 重排、里程碑重校准、GLM-5.3 胜任度矩阵、多会话协作规约 · status: PLAN（现行主计划；⚠️ 09-11 补注：K1 文字线停滞已推进到 v15 / K2 R1 残余已闭环 v7 PASS，详见文末《执行进展同步补注》）
- [[2026-09-08_三报告整合与统一任务目标]] — 三份 09-08 报告 + E0/E1/E2 方案合并为统一任务表（A 工程收口 / B 主攻 / C 评估底座 / D 能力补课 / E 能力扩张），含 5 项报告-磁盘差异核验与选型冲突决议 · status: PLAN（已被 09-10 计划校准）
- [[2026-09-08_调研驱动推进方案修正]] — R1-R8 修正案（H3 证伪、检索三档、GEPA 定型、新增 R7/R8）· status: PLAN
- [[2026-09-05_开源增强选型与规则蒸馏方案]] — MasterCut 增强三波推进（E0 音乐锚定+防灾底座 / E1 规则蒸馏引擎 / E2 能力扩张）+ 全网开源选型（许可证已核验）· status: PLAN（E0 波已 READY，E1-1 已落地）

## EDL 桥落地补丁（Step0-2b · 2026-09-12/13 全部落地, 63 passed）

- [[Step0_EDL_v1.1_补丁草案]] — edl.py: EDL v1.1 三轨(effects/text_events/overlays) + lint L7 + 双兼容 · ✅ APPLIED
- [[Step1_AE链消费EDL_补丁草案]] — load_edl 闸门 + build_master_polish/build_text_overlay --edl 消费 + Step1.5 白名单放宽(接受 R1 修复run) · ✅ §2§3§4+Step1.5 APPLIED（真实数据实证 视觉6/8+文字25）
- [[Step2_编排器接线与EDL轨道回填_草案]] — chicken-egg 分析 + inject_edl_tracks 事后回填 · ✅ §2 APPLIED（round-trip 实证）
- [[Step2b_mastercut_agent接线_补丁草案]] — mastercut_agent 白名单放宽 + tag 派生守卫 + inject 自动接线 · ✅ APPLIED（AE e2e 待真实 run）

## 历史计划

- [[开发路线图-阶段A至E]] — 五段管线总蓝图（2026-07-23）
- [[2026-08-20_全项目扫描分析与提升方案]] — P0/P1/P2 治理方案
- [[v20会话交接-独自升级AMV全记录与集成设计方案]] — AMV 管线 v20 记录
- [[ae-golden-riddle]] — AE 黄金谜题计划（2026-06，阶段0遗产）

## 相关报告

- [[AUDIT_REPORT]] — 项目审计报告（含风险评估和改进建议）
- [[PHASE5_DELIVERY_PACKAGE]] — 后续路线图（短期/中期/长期优先级）

---

> 返回 → [[🏠-AE知识中心]]
