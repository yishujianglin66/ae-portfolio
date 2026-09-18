# Phase B: core/ai 模块 print→logger 迁移计划

## 📊 当前状态统计

| 模块 | Print 数量 | 优先级 | 状态 |
|------|-----------|--------|------|
| core/ | ~800 | P0 (核心) | ⏳ 待迁移 |
| ai/ | ~723 | P1 (AI 层) | ⏳ 待迁移 |
| **总计** | **1,523** | - | - |

## 🎯 迁移策略

### 阶段 1: 核心基础设施 (core/)
- **目标**: 替换 logging 调用，保留关键调试信息
- **范围**: filter_engine.py, transition_engine.py, production_director.py 等
- **方法**: 
  1. 识别 print 用途 (调试/日志/错误)
  2. 转换为 logger.debug/logger.info/logger.error
  3. 添加上下文信息 (函数名、参数)

### 阶段 2: AI 层 (ai/)
- **目标**: 统一 AI 决策日志格式
- **范围**: production_director.py, clarification_engine.py 等
- **方法**:
  1. 使用结构化日志 (JSON 格式)
  2. 记录决策路径和置信度
  3. 标记关键决策点

## 📝 执行清单

### core/ 模块 (P0)

#### ✅ 已完成
- filter_params.py (新文件，无 print)

#### ⏳ 进行中
- [ ] filter_engine.py (~400 prints)
- [ ] transition_engine.py (~300 prints)
- [ ] text_animation_engine.py (~200 prints)
- [ ] production_director.py (~150 prints)
- [ ] 其他核心模块 (~73 prints)

### ai/ 模块 (P1)

#### ⏳ 待处理
- [ ] production_director.py (~200 prints)
- [ ] clarification_engine.py (~150 prints)
- [ ] rhythm_reward.py (~100 prints)
- [ ] 其他 AI 模块 (~273 prints)

## 🔧 迁移模板

```python
# Before
print(f"[DEBUG] Processing filter: {filter_name}")
print(f"Error: Invalid parameter {param_name}")

# After
import logging
logger = logging.getLogger(__name__)

logger.debug("Processing filter: %s", filter_name)
logger.error("Invalid parameter: %s", param_name)
```

## 📈 进度追踪

- **总任务**: 1,523 处 print
- **已完成**: 0 处 (filter_params.py 新文件)
- **完成率**: 0%
- **预计工时**: ~15 小时 (人工审查 + 迁移)

## ⚠️ 注意事项

1. **排除 build_text_overlay.py**: ZCode 热文件，勿碰
2. **保留关键调试**: 某些 print 用于快速诊断，需评估后保留
3. **测试验证**: 迁移后需运行全量测试确保无回归
4. **分批提交**: 每完成一个模块立即提交，便于回滚

---

> 生成时间：2026-09-18  
> 负责人：AI Assistant  
> 审核人：Boss
