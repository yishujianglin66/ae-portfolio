# Puppet Video Automation Pipeline

> 木偶风格视频自动化流水线 - 多引擎协同编排系统

## 项目状态

- **版本**: 0.1.0 (Phase A - 环境搭建)
- **Python**: 3.11.9 (venv)
- **GPU**: NVIDIA RTX 4060 Laptop 8GB (CUDA 12.1)
- **操作系统**: Windows 11

## 快速开始

```powershell
# 进入项目目录
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 设置环境变量（sandbox-safe）
$env:YOLO_CONFIG_DIR = "$PWD\data\cache\ultralytics"

# 验证环境
python scripts\verify_environment.py

# 启动 API 服务
python -m uvicorn src.api.main:app --reload --port 8000

# 启动 Celery Worker（需先启动 Redis）
celery -A src.workers.celery_app worker --loglevel=info
```

## 项目结构

```
puppet-automation/
├── .env                    # 环境变量
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── venv/                   # Python 虚拟环境
├── src/
│   ├── api/                # FastAPI 入口
│   ├── config/             # 配置管理
│   ├── engines/            # 引擎适配层
│   │   ├── ae/             # After Effects
│   │   ├── ffmpeg/         # FFmpeg
│   │   ├── topaz/          # Topaz Video AI
│   │   ├── silhouette/     # Silhouette (待实现)
│   │   ├── blender/        # Blender (待实现)
│   │   └── davinci/        # DaVinci Resolve (待实现)
│   ├── mcp_gateway/        # MCP 统一网关 (待实现)
│   ├── orchestrator/       # 编排层 (待实现)
│   ├── ai_planner/         # AI 规划层 (待实现)
│   ├── workers/            # Celery 任务
│   ├── utils/              # 工具函数
│   └── models/             # 数据模型
├── data/
│   ├── input/              # 输入素材
│   ├── output/             # 输出文件
│   ├── temp/               # 临时文件
│   ├── cache/              # 缓存
│   └── projects/           # 项目文件
├── scripts/                # 安装/验证脚本
│   ├── verify_environment.py
│   ├── enable-wsl2-docker.ps1
│   ├── install-blender.ps1
│   └── install-ffmpeg.ps1
├── tests/                  # 测试
├── configs/                # 配置文件
├── docs/                   # 文档
└── logs/                   # 日志
```

## 引擎清单

| 引擎 | 状态 | 用途 |
|------|------|------|
| After Effects 2026 | ✅ 已安装 | Phase 3 风格化合成 |
| Photoshop Beta | ✅ 已安装 | 素材制作 |
| Silhouette 2026 | ✅ 已安装 | Phase 2 抠像跟踪 |
| DaVinci Resolve | ✅ 已安装 | Phase 3 调色 |
| Topaz Video AI | ✅ 已安装 | Phase 1 画质增强 |
| FFmpeg (imageio) | ✅ 已就绪 | 全流程转码 |
| Blender | ⏳ 待安装 | Phase 3 3D 舞台 |
| nexrender | ✅ 已安装 | AE 批量渲染 |
| Docker | ⏳ 待启用 | 企业级容器化 |

## 待完成事项

### 用户手动操作（需管理员权限）

1. **启用 WSL2 + 安装 Docker Desktop**:
   ```powershell
   # 右键 PowerShell → 以管理员身份运行
   powershell -ExecutionPolicy Bypass -File "scripts\enable-wsl2-docker.ps1"
   ```

2. **安装 Blender**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "scripts\install-blender.ps1"
   ```

3. **安装 FFmpeg 完整版**（可选，imageio-ffmpeg 已提供基础版）:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "scripts\install-ffmpeg.ps1"
   ```

### 后续开发任务

- [ ] 实现 Silhouette 引擎适配器（fx Python API）
- [ ] 实现 Blender 引擎适配器（bpy Python API）
- [ ] 实现 DaVinci Resolve 引擎适配器
- [ ] 实现 MCP 统一网关
- [ ] 实现编排层（四阶段流水线）
- [ ] 实现 AI 规划层（LangChain + LLM）
- [ ] 创建 Docker Compose 配置
- [ ] 编写单元测试与集成测试

## 技术栈

- **后端**: FastAPI + Celery + Redis + SQLAlchemy
- **AI/ML**: PyTorch 2.3.1+cu121 / MediaPipe / Ultralytics / ONNX Runtime
- **CV**: OpenCV / imageio / moviepy / librosa
- **LLM**: LangChain + OpenAI
- **渲染**: aerender / nexrender / FFmpeg
- **3D**: Blender (bpy)
- **监控**: Prometheus + Grafana + Flower

## 参考文档

- `10-风格化剪辑知识库/木偶视频自动化流水线-全软件最高配置落地总计划.md`
- `10-风格化剪辑知识库/Phase1-预处理全链路技术详解.md`
- `10-风格化剪辑知识库/Phase2-抠像跟踪全链路技术详解.md`
- `10-风格化剪辑知识库/Phase3-风格化合成全链路技术详解.md`
- `10-风格化剪辑知识库/Phase4-渲染输出全链路技术详解.md`
- `10-风格化剪辑知识库/统一MCP网关-全引擎接入规范.md`
- `10-风格化剪辑知识库/企业级架构落地实施手册.md`
