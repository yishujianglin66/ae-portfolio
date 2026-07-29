# AE Knowledge Vault - 项目作品集

## 项目概览

**AE Knowledge Vault** 是一个基于多引擎协同编排的木偶风格视频自动化制作平台。该项目整合了 AI 规划、风格化合成、多软件协同等核心技术,实现了从素材获取到渲染交付的全流程自动化。

### 核心价值

- **自动化程度高**: 统一调度9+专业软件,实现跨软件协作
- **AI智能规划**: 集成多LLM API,智能分析场景与生成参数
- **风格化丰富**: 170+木偶风格预设,覆盖漫剪拉镜大师风格
- **企业级架构**: 分布式渲染、高可用部署、完整监控体系

## 技术架构

### 后端核心
- **FastAPI**: 高性能异步API框架
- **Celery**: 分布式任务队列
- **Redis**: 缓存与消息队列
- **SQLAlchemy**: ORM数据库映射
- **Pydantic**: 数据验证与序列化

### AI/ML技术栈
- **PyTorch 2.3**: 深度学习框架
- **MediaPipe**: 实时视觉处理
- **Ultralytics**: YOLO目标检测
- **ONNX Runtime**: 模型推理加速
- **LangChain**: LLM应用开发框架

### 前端界面
- **React 18**: 组件化UI框架
- **TypeScript**: 类型安全
- **Vite**: 快速构建工具
- **TailwindCSS**: 实用优先CSS框架
- **Zustand**: 轻量状态管理

### 视频处理
- **OpenCV**: 计算机视觉库
- **FFmpeg**: 音视频转码
- **MoviePy**: Python视频编辑
- **Librosa**: 音频分析
- **Whisper**: 语音识别

### 3D渲染
- **Blender (bpy)**: Python 3D建模API
- **Omniverse**: NVIDIA元宇宙平台
- **NVIDIA USD**: 通用场景描述

### 自动化工具
- **ExtendScript**: Adobe脚本引擎
- **nexrender**: AE批量渲染
- **Docker**: 容器化部署
- **Nginx**: 反向代理与负载均衡

## 核心功能模块

### 1. 多引擎协同编排系统

统一调度以下9个专业软件引擎:

| 引擎 | 版本 | 功能 | 状态 |
|------|------|------|------|
| After Effects | 2026 | Phase 3 风格化合成 | ✅ 已集成 |
| Photoshop | Beta | 素材制作 | ✅ 已集成 |
| DaVinci Resolve | 最新版 | Phase 3 调色 | ✅ 已集成 |
| Topaz Video AI | 最新版 | Phase 1 画质增强 | ✅ 已集成 |
| Silhouette | 2026 | Phase 2 抠像跟踪 | ✅ 已集成 |
| FFmpeg | 最新版 | 全流程转码 | ✅ 已就绪 |
| Blender | 最新版 | Phase 3 3D舞台 | ⏳ 待集成 |
| Media Encoder | 最新版 | 渲染输出 | ✅ 已集成 |
| nexrender | 最新版 | AE批量渲染 | ✅ 已集成 |

### 2. AI智能规划系统

#### LLM网关架构
- **三层路由架构**: TIER_1_LOCAL (5M-50M参数垂直模型) → TIER_2_MIDTIER (中端通用模型) → TIER_3_FLAGSHIP (旗舰推理模型)
- **支持的Provider**: DeepSeek V4、豆包、通义千问、GLM、Kimi
- **健康检查与自动降级**: Provider失败自动切换到fallback

#### 核心能力
- 意图识别与任务路由
- 风格分析与效果推演
- 参数智能映射
- 自动化JSX脚本生成
- 学习反馈闭环系统

### 3. 风格化预设库系统

#### 预设分类
- **漫剪拉镜大师风格**: 12位大师的标志性风格
- **木偶风格参数库**: 170+预设参数组合
- **字体预设系统**: 100+字体场景映射

#### 大师风格库
- **Xenoz**: 推拉鼻祖风格
- **Molob**: 电影感大师风格
- **Donya**: 三维空间风格
- **DxshNova**: 对角滑镜风格
- **Floby**: 韩式快剪风格
- **YashFX**: 高燃插件流风格

### 4. 音画同步系统

- 音乐结构原子分析
- BPM节拍检测与映射
- 节拍-关键帧精密映射
- 音效体系与图层操作
- 片段元数据与能量图谱

### 5. MCP统一网关

基于Model Context Protocol协议的跨软件通信系统:

- **ExtendScript MCP扩展**: AE/PS/PR/AU的脚本层通信
- **Adobe Bridge统一适配**: 统一的API抽象层
- **实时双向通信**: 支持同步与异步调用
- **跨软件任务编排**: 复杂工作流的自动编排

### 6. 可视化控制面板

基于React的专业控制面板,提供:

- 项目工作流可视化
- 实时渲染进度追踪
- 风格库浏览器
- 批量任务队列管理
- 效果素材分类管理(1000+资源)
- 历史记录与版本回溯

## 四阶段流水线

### Phase 1: 素材预处理
- 画质增强 (Topaz Video AI)
- 去噪、锐化、超分辨率
- 格式转换与编码优化

### Phase 2: 抠像与跟踪
- 人物抠像 (Silhouette)
- 运动跟踪与稳定
- 蒙版生成与优化

### Phase 3: 风格化合成
- AE合成构建
- 特效应用与参数调优
- 调色与风格化
- 3D舞台渲染 (Blender/Omniverse)

### Phase 4: 渲染输出
- 多格式渲染 (Media Encoder)
- 批量渲染队列 (nexrender)
- 质量检查与交付

## 资源库体系

### 效果素材库 (1000+)
- **UV动画类**: 火焰、闪电、光效等
- **光点类**: 粒子、光束、能量球等
- **刀光类**: 轨迹、光束、旋转光等
- **图案类**: 法阵、符号、装饰元素等
- **序列帧贴图**: 动态纹理与特效

### 知识库文档 (50+)
- AE自动化引擎架构设计
- 木偶视频制作核心指南
- 风格化剪辑技巧与预设
- 多软件集成方案
- 音画匹配推演系统
- 企业级架构落地手册

### 字体预设系统 (100+)
- 场景化字体映射
- 风格化字体组合
- 动态字体效果预设

## 技术亮点

### 1. 统一LLM网关
- 多Provider自动适配与路由
- 健康检查与自动降级
- 用量与成本追踪
- 日志脱敏与安全控制

### 2. 原子参数编译器
- TypeScript编译器链
- Phase 3/4/5三阶段编译
- 参数-效果原子级映射
- JSX代码自动生成

### 3. 学习反馈闭环
- 执行记录持久化
- 置信度动态调整
- 案例库积累
- 默认值优化

### 4. 企业级可观测性
- Prometheus指标收集
- Grafana可视化监控
- Flower任务监控
- 日志聚合与分析

## 开发环境

### 硬件配置
- **操作系统**: Windows 11
- **GPU**: NVIDIA GeForce RTX 4060 Laptop GPU (8GB VRAM)
- **CPU**: Intel Core Ultra处理器
- **内存**: 32GB DDR5
- **存储**: NVMe SSD

### 软件环境
- **Python**: 3.11.9 (venv)
- **Node.js**: v18+ (for compiler)
- **Docker**: Docker Desktop with WSL2
- **IDE**: Visual Studio Code + PyCharm
- **AE**: After Effects 2026 (英文版)

## 项目结构

```
AE-Knowledge-Vault/
├── puppet-automation/       # 后端自动化引擎
│   ├── src/
│   │   ├── api/             # FastAPI入口
│   │   ├── engines/         # 引擎适配层
│   │   ├── services/        # 业务逻辑层
│   │   ├── orchestrator/    # 编排层
│   │   └── ai_planner/      # AI规划层
│   ├── tests/               # 测试套件
│   └── requirements.txt
├── ae-dashboard/            # React前端面板
│   ├── src/
│   │   ├── components/      # UI组件
│   │   ├── pages/           # 页面模块
│   │   └── store/           # 状态管理
│   └── package.json
├── compiler/                # TypeScript编译器
│   ├── src/
│   │   ├── phase3/          # Phase 3编译器
│   │   ├── phase4/          # Phase 4编译器
│   │   └── phase5/          # Phase 5编译器
│   └── package.json
├── core/                    # 核心基础设施
│   ├── llm_gateway.py       # LLM统一网关
│   ├── workflow_orchestrator.py  # 工作流编排
│   └── observability.py     # 可观测性
├── resources/               # 资源库
│   ├── effects/             # 效果素材
│   └── video/               # 视频素材
├── config/                  # 配置中心
│   ├── style_presets.json   # 风格预设
│   ├── font_presets.json    # 字体预设
│   └── effect_presets.json  # 效果预设
└── 10-风格化剪辑知识库/     # 知识库文档
```

## 部署方式

### 开发环境
```powershell
# 后端启动
cd puppet-automation
.\venv\Scripts\Activate.ps1
python -m uvicorn src.api.main:app --reload --port 8000

# 前端启动
cd ae-dashboard
npm install
npm run dev
```

### 生产部署
```powershell
# Docker Compose
docker-compose up -d

# Nginx反向代理
nginx -c nginx/nginx.conf
```

## 未来规划

### 短期目标 (1-3个月)
- 完成Blender引擎集成
- 实现Omniverse渲染桥接
- 优化LLM网关性能
- 扩充预设库至300+

### 中期目标 (3-6个月)
- 实现Web端完整工作流
- 集成更多AI模型
- 支持实时协作
- 移动端监控应用

### 长期目标 (6-12个月)
- SaaS化部署
- 多租户支持
- API开放平台
- 社区生态建设

## 联系信息

- **项目路径**: `C:\Users\Administrator\Desktop\AE-Knowledge-Vault`
- **作品集页面**: `portfolio.html`
- **开发环境**: Windows 11 + NVIDIA RTX 4060
- **技术栈**: Python 3.11 + React 18 + TypeScript

---

**项目亮点总结**: 该项目展示了在视频自动化领域的深度技术积累,涵盖AI集成、多软件协同、企业级架构设计等多个技术维度,适合作为个人技术能力的全面展示。