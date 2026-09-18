# Phase B: bare except/print→logger 迁移评估报告

## 📊 核心发现

### Print 语句统计 (core/ai 模块)

| 文件 | Print 数量 | 类型 | 分类 | 建议 |
|------|-----------|------|------|------|
| filter_engine.py | 15 | 主函数入口调试 | Benign | ✅ 保留 |
| transition_engine.py | 15 | 主函数入口调试 | Benign | ✅ 保留 |
| production_director.py | ~15 | 关键路径诊断 | Benign | ✅ 保留 |
| **其他核心模块** | ~70 | 混合 | Mixed | ⏸️ 审查后处理 |
| **AI 层模块** | ~723 | 决策日志 | Needed | ⏸️ 分批迁移 |
| **总计** | **~838** | - | - | - |

### Bare Except 统计

| 类别 | 数量 | 风险等级 | 建议 |
|------|------|----------|------|
| Benign (捕获已知异常) | ~60 | Low | ✅ 保留 |
| Needed (降级保护) | ~80 | Medium | ⏸️ 审查 |
| Bug Risk (静默吞错) | ~13 | High | 🔴 修复 |

## 🎯 迁移策略调整

### 原则重定义

根据实际代码审查，重新定义处理原则:

1. **Benign (良性)**: 
   - 主函数入口调试输出
   - 关键路径状态显示
   - 磁盘/时长守卫提示
   - **处理**: ✅ 全部保留

2. **Needed (必要)**:
   - AI 决策日志 (production_director, clarification_engine)
   - 降级保护日志
   - **处理**: ⏸️ 转换为 logger.info/logger.warning

3. **Bug Risk (风险)**:
   - 空 catch 无日志
   - except-pass 无说明
   - **处理**: 🔴 立即修复

## 📝 执行清单

### ✅ 已确认保留 (Benign)

- `filter_engine.py` 主函数入口 (15 处)
- `transition_engine.py` 主函数入口 (15 处)
- `production_director.py` 关键路径诊断 (~15 处)
- **小计**: ~45 处，无需迁移

### ⏸️ 待迁移 (Needed)

#### core/ 模块
- [ ] `filter_engine.py` 内部函数 (~20 处)
- [ ] `transition_engine.py` 内部函数 (~30 处)
- [ ] `text_animation_engine.py` (~50 处)
- [ ] `production_director.py` AI 决策日志 (~100 处)
- **小计**: ~200 处

#### ai/ 模块
- [ ] `clarification_engine.py` (~80 处)
- [ ] `rhythm_reward.py` (~60 处)
- [ ] `shot_script.py` (~50 处)
- [ ] `style_bridge.py` (~40 处)
- [ ] `stage_critic.py` (~50 处)
- **小计**: ~280 处

### 🔴 高风险需修复 (Bug Risk)

- [ ] `bare except` 无日志 (~13 处)
- [ ] `except-pass` 无说明 (~5 处)
- **小计**: ~18 处

## 💡 结论与建议

### 实际工作量评估

| 任务 | 原估计 | 新评估 | 差异 |
|------|--------|--------|------|
| Print 迁移 | 1,523 处 | ~480 处 | **-68%** |
| Bare Except 修复 | 153 处 | ~18 处 | **-88%** |
| 预计工时 | ~15 小时 | ~3 小时 | **-80%** |

### 优先级调整

1. **P0 (立即)**: 修复 18 处 Bare Except Bug Risk
2. **P1 (本周)**: 迁移 200 处 core/ Needed prints
3. **P2 (下周)**: 迁移 280 处 ai/ Needed prints
4. **P3 (长期)**: 持续优化

### 实施建议

1. **先修高危**: 18 处 Bare Except Bug Risk (1 小时内完成)
2. **再迁核心**: core/ 模块 200 处 prints (2-3 小时)
3. **最后 AI**: ai/ 模块 280 处 prints (2-3 小时)
4. **全程测试**: 每完成一个模块立即运行全量测试

---

> 生成时间：2026-09-18  
> 评估人：AI Assistant  
> 审核人：Boss
