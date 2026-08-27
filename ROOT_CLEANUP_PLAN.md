# 根目录治理方案

**日期**: 2026-08-26  
**目标**: 将159个散落的.py文件按功能域分包，建立清晰的目录结构

---

## 当前状态

- 根目录.py文件: **159个** (4.3MB)
- 根目录总项数: **420项** (117目录 + 303文件)
- 历史参考: 之前已完成过治理（138→39个），现在文件又增多了

---

## 治理策略

### 原则
1. **功能域分包**: 按业务功能将文件归入对应子目录
2. **向后兼容**: 创建import重定向层，确保旧代码无需修改
3. **渐进式迁移**: 分批执行，每批验证导入正常
4. **保留核心**: 根目录仅保留入口文件和配置文件

### 目标结构
```
根目录/
├── api_server.py              # 主API入口
├── ae_agent_pipeline.py       # 主AE管线入口
├── bootstrap.py               # 启动引导
├── ultimate_video_factory.py  # 终极视频工厂
├── config_schema.py           # 配置模式
├── database.py                # 数据库
├── exceptions.py              # 异常定义
├── logger.py                  # 日志配置
├── system_memory.py           # 系统内存
├── _import_redirect.py        # import重定向兼容层
├── pytest.ini                 # 测试配置
├── pyproject.toml             # 项目配置
├── requirements.txt           # 依赖清单
└── TASK_STATUS.md             # 任务看板
```

---

## 分包方案

### 1. ae/ - AE自动化脚本 (预计20+文件)
匹配规则: `^ae_`
- ae_agent_pipeline.py (保留根目录)
- ae_composition_presets.py → ae/
- ae_deep_analysis.jsx → ae/
- ae_extension_integrator.py → ae/
- ae_mcp_auto_listener.jsx → ae/
- ae_mcp_bridge_v26.jsx → ae/
- ae_mcp_client.py → ae/
- ... 等

### 2. bridges/ - 桥接与集成 (预计15+文件)
匹配规则: `_bridge|_mcp`
- adobe_mcp_server.py → bridges/
- adobe_mcp_bridge.py → bridges/
- mcp_bridge_client.py → bridges/
- premiere_mcp_client.py → bridges/
- ps_bridge_client.py → bridges/
- ... 等

### 3. integrations/ - 第三方集成 (已有目录)
匹配规则: `_integration\.py$`
- adobe_suite_integration.py → integrations/
- blender_3d_integration.py → integrations/
- davinci_resolve_integration.py → integrations/
- ... 等

### 4. core/ - 核心引擎 (已有目录)
匹配规则: `_engine\.py$|_orchestrator\.py$`
- filter_engine.py → core/
- transition_engine.py → core/
- text_animation_engine.py → core/
- ... 等

### 5. api/ - API服务 (新建)
匹配规则: `_api\.py$`
- api_server.py (保留根目录)
- ai_chat_api.py → api/
- camera_classifier_api.py → api/
- ... 等

### 6. scripts/ - 工具脚本 (新建)
匹配规则: `^(test_|demo_|validate_|optimize_|reverse_)`
- test_*.py → tests/ (已有目录)
- demo_*.py → scripts/
- validate_*.py → scripts/
- optimize_*.py → scripts/
- reverse_*.py → scripts/

### 7. models/ - 模型相关 (已有目录)
匹配规则: 模型训练/推理相关
- *_model.py → models/
- *_training.py → models/
- ... 等

### 8. utils/ - 工具函数 (新建)
匹配规则: 通用工具类
- *_utils.py → utils/
- *_helper.py → utils/
- ... 等

---

## 执行步骤

### Phase 1: 准备 (10分钟)
1. 备份当前状态
2. 创建新目录（如需要）
3. 生成迁移脚本

### Phase 2: 迁移 (30分钟)
1. 执行文件移动
2. 创建import重定向层
3. 验证导入正常

### Phase 3: 验证 (20分钟)
1. 运行核心模块导入测试
2. 运行pytest收集测试
3. 运行关键功能测试

---

## 风险控制

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 导入路径断裂 | 中 | 高 | 创建import重定向层 |
| 测试失败 | 中 | 中 | 分批验证，即时回滚 |
| 功能异常 | 低 | 高 | 保留根目录入口文件 |

---

## 回滚方案

如果迁移出现问题：
1. 使用git恢复到迁移前状态
2. 或删除新创建的目录和文件
3. 恢复原始文件位置

---

## 成功指标

- [ ] 根目录.py文件 < 20个
- [ ] 所有核心模块导入正常
- [ ] pytest收集无错误
- [ ] 关键功能测试通过

---

**下一步**: 执行迁移脚本
