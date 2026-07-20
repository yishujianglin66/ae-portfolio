---
title: AI辅助视频生成端到端部署完全指南
aliases: [AI视频生成部署手册, AI Video Generation Deployment Guide, AE MCP 部署指南]
tags: [部署指南, 端到端, AI辅助视频生成, MCP, AE 2025, Windows, Python, Node.js, FFmpeg]
category: 风格化剪辑知识库
status: 已完成
version: 1.0.0
created: 2026-07-06
updated: 2026-07-06
author: AE Knowledge Vault
estimated_reading: 180分钟
deployment_time: 新手4小时 / 老手1小时
---

# AI辅助视频生成端到端部署完全指南

> [!abstract] 文档定位
> 本文档是**原子级企业级部署手册**，从零开始手把手教你部署完整的 AI 辅助视频生成系统——从 Python 环境到 AE MCP 到端到端流水线的完整安装配置指南。针对 Windows 10/11 + After Effects 2025 环境深度优化，每一步都配有详细的命令行和验证方法。
>
> **前置知识**：[[AI辅助视频生成一体化工作流总览]] | [[音画匹配引擎与系统桥接工程手册]] | [[AE 自动化引擎架构设计]]

> [!warning] 重要提示
> - 本文档所有命令均针对 **Windows PowerShell 5.1+** 环境
> - 默认安装路径：`C:\Tools\` 用于工具，`C:\Projects\` 用于项目
> - 如需修改路径，请同步修改所有相关配置
> - 建议全程使用**管理员权限**运行 PowerShell

---

## 目录

- [[#第1章 部署总览|第1章 部署总览]]
- [[#第2章 基础环境准备|第2章 基础环境准备]]
- [[#第3章 Python 环境部署|第3章 Python 环境部署]]
- [[#第4章 Node.js 与 TypeScript 环境|第4章 Node.js 与 TypeScript 环境]]
- [[#第5章 FFmpeg 部署|第5章 FFmpeg 部署]]
- [[#第6章 After Effects MCP 部署|第6章 After Effects MCP 部署]]
- [[#第7章 MCP 扩展工具安装|第7章 MCP 扩展工具安装]]
- [[#第8章 Python-TS 桥接配置|第8章 Python-TS 桥接配置]]
- [[#第9章 端到端流水线部署|第9章 端到端流水线部署]]
- [[#第10章 常见软件的安装与配置|第10章 常见软件的安装与配置]]
- [[#第11章 安全与备份|第11章 安全与备份]]
- [[#第12章 部署验证与验收|第12章 部署验证与验收]]
- [[#附录A：一键部署脚本|附录A：一键部署脚本]]
- [[#附录B：版本兼容性矩阵|附录B：版本兼容性矩阵]]

---

## 第1章 部署总览

### 1.1 系统架构全景图

AI 辅助视频生成系统采用**五层架构**设计，各层之间通过标准化接口通信，确保模块解耦与独立升级。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI 辅助视频生成系统架构图                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │  Python 分析层   │    │   TS 引擎层     │    │   AE 执行层     │        │
│  │  (L1-L3 匹配)   │◄──►│  (编译器+入口)  │◄──►│  (MCP Bridge)   │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│           │                       │                       │                │
│           │                       │                       │                │
│  ┌─────────────────┐              │              ┌─────────────────┐      │
│  │  音效合成层      │◄─────────────┘              │  MCP 传输层     │      │
│  │  (FFmpeg 混音)   │                             │  (工具调用协议)  │      │
│  └─────────────────┘                             └─────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 1.1.1 五大模块详解

| 模块 | 层级 | 核心职责 | 技术栈 | 通信协议 |
|------|------|---------|--------|---------|
| **Python 分析层** | L1-L3 | 音乐分析、片段分析、音画匹配、参数反推 | Python 3.11, librosa, OpenCV, scipy, numpy | JSON over stdio / HTTP |
| **TS 引擎层** | L4-L5 | 编译器、入口调度、验证器、学习闭环 | Node.js 20+, TypeScript, esbuild | 函数调用 / MCP |
| **MCP 传输层** | 中间层 | 工具注册、调用路由、状态管理 | MCP SDK, JSON-RPC 2.0 | stdio / WebSocket |
| **AE 执行层** | 执行层 | ExtendScript 执行、合成操作、效果应用 | After Effects 2025, ExtendScript, JSX | CEP / BridgeTalk |
| **音效合成层** | 输出层 | 音效时间轴、多轨混音、响度标准化 | FFmpeg 6+, pydub, soundfile | 文件交换 / HTTP |

#### 1.1.2 核心数据流

```
用户输入 (音乐+片段+风格)
      │
      ▼
  ┌──────────┐    MusicAtom
  │ 音乐分析  │───────────┐
  └──────────┘           ▼
                    ┌──────────┐    MatchPlan
  ┌──────────┐      │ 音画匹配  │───────────┐
  │ 片段分析  │─────►└──────────┘           ▼
  └──────────┘                        ┌──────────┐    CompilerInput
                                      │ 参数反推  │───────────┐
                                      └──────────┘           ▼
                                                          ┌──────────┐
                                                          │ TS 编译器  │
                                                          └──────────┘
                                                               │
                                                               ▼ JSX
                                                          ┌──────────┐
                                                          │  MCP 桥   │
                                                          └──────────┘
                                                               │
                                                               ▼
                                                          ┌──────────┐
                                                          │ AE 执行   │
                                                          └──────────┘
                                                               │
                                                               ▼
  ┌──────────┐    音效时间轴    ┌──────────┐         最终成片
  │ 音效设计  │◄───────────────│  FFmpeg  │◄───────────┘
  └──────────┘                 └──────────┘
```

> [!info] 参考文档
> - 架构设计详情参见 [[AE 自动化引擎架构设计]]
> - 工作流详情参见 [[AI辅助视频生成一体化工作流总览]]
> - 音画匹配算法参见 [[音画匹配引擎与系统桥接工程手册]]


#### 1.1.3 各层技术选型详解

**Python 分析层技术选型**

Python 分析层是系统的「大脑」，负责所有需要 AI 算法和数值计算的任务。选择 Python 作为分析层主要基于以下考虑：

- **生态丰富**：librosa、madmom、essentia 等音频处理库都是 Python 原生
- **AI 框架支持**：PyTorch、TensorFlow 等深度学习框架首选 Python
- **科学计算**：numpy、scipy、scikit-learn 提供强大的数值计算能力
- **快速迭代**：算法研究和原型开发效率最高

Python 层主要承担以下任务：
- **音乐分析**：BPM 检测、节拍跟踪、段落结构分析、情绪识别、调性检测
- **片段分析**：场景检测、镜头切分、色彩分析、运动估计、质量评估
- **音画匹配**：基于节奏的剪辑点匹配、基于情绪的风格匹配、基于内容的场景匹配
- **参数反推**：效果参数生成、转场策略选择、节奏曲线映射

**TS 引擎层技术选型**

TypeScript 引擎层是系统的「骨架」，负责工程化、调度和编译。选择 TypeScript 的原因：

- **类型安全**：大型项目维护性好，重构成本低
- **MCP 生态**：MCP SDK 原生支持 TypeScript
- **工程化工具**：esbuild、vite 等构建工具性能优异
- **异步编程**：Node.js 异步 I/O 适合调度和编排

TS 层主要承担以下任务：
- **编译器**：将高级配置编译为 AE 可执行的 JSX 脚本
- **入口调度**：autoEdit 主入口、各阶段任务编排
- **验证器**：输入验证、输出验证、质量检查
- **学习闭环**：结果反馈、参数优化、模型迭代

**MCP 传输层技术选型**

MCP（Model Context Protocol）是连接 AI 助手与外部工具的标准协议：

- **标准化**：统一的工具注册、调用、结果格式
- **多传输方式**：支持 stdio、WebSocket、HTTP 等多种传输
- **生态丰富**：越来越多的工具提供 MCP 接口
- **Trae 原生支持**：TRAE IDE 内置 MCP 客户端

MCP 层主要承担：
- **工具注册**：将 AE 操作注册为 MCP 工具
- **调用路由**：接收 MCP 调用，路由到对应的 JSX 脚本
- **状态管理**：维护 AE 连接状态、任务队列
- **错误处理**：统一的错误码、错误信息、重试机制

**AE 执行层技术选型**

After Effects 是行业标准的视频特效软件，选择 AE 作为执行层：

- **行业标准**：专业视频制作的事实标准
- **ExtendScript**：完整的脚本 API，几乎所有操作都可脚本化
- **效果生态**：海量内置效果和第三方插件
- **表达式系统**：强大的属性关联和动画能力

AE 层主要承担：
- **合成操作**：创建合成、添加图层、设置属性
- **效果应用**：应用效果、调整参数、关键帧动画
- **渲染输出**：渲染队列、输出模块、编码设置
- **项目管理**：项目文件、素材管理、图层组织

**音效合成层技术选型**

FFmpeg 是最强大的开源音视频处理工具：

- **功能全面**：几乎支持所有音视频格式和编解码器
- **性能优异**：C 语言实现，支持硬件加速
- **脚本友好**：命令行调用，易于自动化
- **跨平台**：Windows、macOS、Linux 全平台支持

音效层主要承担：
- **音效时间轴**：音效素材剪辑、时间对齐
- **多轨混音**：音乐、音效、人声的混合
- **响度标准化**：EBU R128 标准响度处理
- **格式转换**：各种音频格式的编码转换

#### 1.1.4 部署架构模式

根据使用场景和规模，有三种部署模式可选：

**单机模式（推荐入门）**

所有组件都在同一台 Windows 电脑上运行，最简单直接：

```
┌─────────────────────────────────────┐
│         Windows 工作站               │
│                                     │
│  ┌─────────┐  ┌─────────┐          │
│  │ Python  │  │ Node.js │          │
│  │ 分析层   │  │ TS 引擎 │          │
│  └────┬────┘  └────┬────┘          │
│       │            │                │
│       └──────┬─────┘                │
│              │                      │
│  ┌───────────▼───────────┐          │
│  │  After Effects 2025   │          │
│  │  (MCP Bridge 面板)     │          │
│  └───────────────────────┘          │
│                                     │
│  ┌───────────────────────┐          │
│  │  FFmpeg (音效合成)     │          │
│  └───────────────────────┘          │
└─────────────────────────────────────┘
```

适用场景：个人使用、小型工作室、学习测试

**主从模式（推荐生产）**

一台主工作站负责 UI 和 AE 操作，多台从机器负责计算密集型任务：

```
┌──────────────────┐
│   主工作站        │
│   (AE + MCP)     │
└────────┬─────────┘
         │
         ├──────────────┐
         │              │
┌────────▼───┐   ┌──────▼─────────┐
│ 计算节点 1   │   │  计算节点 2    │
│ (Python)    │   │  (Python)     │
│ 音乐分析     │   │  片段分析      │
│ 音画匹配     │   │  FFmpeg 渲染   │
└─────────────┘   └────────────────┘
```

适用场景：中型团队、需要加速分析任务

**云端模式（企业级）**

弹性伸缩的云原生部署，适合大规模生产：

```
┌─────────────────────────────────────────┐
│           云端 VPC                       │
│                                         │
│  ┌─────────┐   ┌─────────┐             │
│  │ API 网关 │   │ 任务队列 │             │
│  └────┬────┘   └────┬────┘             │
│       │              │                  │
│  ┌────▼──────────────▼────┐            │
│  │   K8s 计算集群          │            │
│  │  (Python Worker)       │            │
│  └────────────────────────┘            │
│                                         │
└─────────────────────────────────────────┘
            ▲
            │
┌───────────┴───────────┐
│  本地工作站 (AE + MCP)  │
└───────────────────────┘
```

适用场景：大型企业、需要处理大量视频

> [!tip] 本指南范围
> 本部署指南主要覆盖**单机模式**，这是最常用也是最基础的部署方式。
> 掌握单机模式后，可以参考 [[分布式渲染与计算集群部署指南]]（待编写）升级到主从或云端模式。

### 1.2 硬件需求

#### 1.2.1 最低配置（可运行）

| 组件 | 最低要求 | 说明 |
|------|---------|------|
| CPU | Intel i5-10400 / AMD Ryzen 5 3600 | 6核12线程以上 |
| GPU | NVIDIA GTX 1660 / AMD RX 580 | 支持 CUDA / OpenCL |
| 显存 | 6 GB | 用于 Torch + OpenCV |
| 内存 | 16 GB DDR4 | Python + Node + AE 同时运行 |
| 存储 | 100 GB 可用空间 | 系统 + 工具 + 模型 + 缓存 |
| 网络 | 100 Mbps | 下载模型和依赖 |

#### 1.2.2 推荐配置（流畅运行）

| 组件 | 推荐配置 | 说明 |
|------|---------|------|
| CPU | Intel i7-13700K / AMD Ryzen 7 7800X3D | 16核以上 |
| GPU | NVIDIA RTX 4070 / AMD RX 7800 XT | 支持 CUDA 12+ |
| 显存 | 12 GB | 大模型 + 批量处理 |
| 内存 | 32 GB DDR5 | 多项目并行 + 缓存 |
| 存储 | 500 GB NVMe SSD | 高速读写素材 |
| 网络 | 500 Mbps | 快速下载大文件 |

#### 1.2.3 专业配置（生产级）

| 组件 | 专业配置 | 说明 |
|------|---------|------|
| CPU | Intel i9-14900K / AMD Ryzen 9 7950X | 24核以上 |
| GPU | NVIDIA RTX 4090 | 24GB 显存 |
| 显存 | 24 GB | 全量模型 + 批量推理 |
| 内存 | 64 GB DDR5 | 大规模并发处理 |
| 存储 | 2 TB NVMe SSD | 大型项目 + 素材库 |
| 网络 | 1 Gbps | 高速素材同步 |

> [!warning] GPU 注意事项
> - **强烈推荐 NVIDIA 显卡**：CUDA 生态最完善，Torch、OpenCV 等库原生支持
> - AMD 显卡可使用 ROCm，但 Windows 下兼容性较差
> - 核显/集显不推荐：推理速度慢，部分功能不可用

### 1.3 软件版本矩阵

#### 1.3.1 核心软件版本

| 软件 | 最低版本 | 推荐版本 | 最高兼容版本 | 说明 |
|------|---------|---------|-------------|------|
| Windows | 10 21H2 | 11 22H2+ | 11 24H2 | 64位系统 |
| PowerShell | 5.1 | 7.4+ | 7.5 | 推荐安装 PowerShell 7 |
| Python | 3.10 | 3.11.8 | 3.12 | 3.11 兼容性最佳 |
| Node.js | 18.17 | 20.11 LTS | 22.x | 20 LTS 为推荐版本 |
| npm | 9.x | 10.x | 10.x | 随 Node.js 一同安装 |
| After Effects | 2023 (23.0) | 2025 (25.0) | 2026 (26.0) | 2025 功能最完整 |
| FFmpeg | 5.1 | 6.1 | 7.x | 6.1 稳定性最佳 |
| Git | 2.39 | 2.44 | 最新 | 版本控制工具 |

#### 1.3.2 Python 核心依赖版本

| 库名 | 推荐版本 | 用途 |
|------|---------|------|
| numpy | 1.26.4 | 数值计算基础 |
| scipy | 1.11.4 | 科学计算 + 匈牙利算法 |
| librosa | 0.10.1 | 音乐分析 |
| opencv-python | 4.8.1.78 | 视频/图像处理 |
| scikit-learn | 1.3.2 | 聚类 + 分类 |
| pydub | 0.25.1 | 音频处理 |
| soundfile | 0.12.1 | 音频文件读写 |
| torch | 2.2.0 (cu121) | 深度学习推理 |
| pyyaml | 6.0.1 | YAML 配置文件 |
| fastapi | 0.109.2 | HTTP API 服务 |
| uvicorn | 0.27.1 | ASGI 服务器 |

#### 1.3.3 Node.js 核心依赖版本

| 库名 | 推荐版本 | 用途 |
|------|---------|------|
| typescript | 5.3.3 | 类型系统 |
| esbuild | 0.20.0 | 构建工具 |
| @modelcontextprotocol/sdk | 0.4.0 | MCP SDK |
| zod | 3.22.4 | 数据验证 |
| fs-extra | 11.2.0 | 文件系统增强 |

> [!tip] 版本选择原则
> - **Python 3.11**：性能比 3.10 提升 ~25%，且大多数库已兼容
> - **Node.js 20 LTS**：长期支持版本，稳定性有保障
> - **FFmpeg 6.x**：6.1 是目前最稳定的大版本，编码器齐全
> - **AE 2025**：MCP Bridge 支持最完善，新特性丰富

### 1.4 部署时间预估

#### 1.4.1 新手路径（4小时）

| 阶段 | 预计耗时 | 操作内容 |
|------|---------|---------|
| 第1-2章 | 30分钟 | 系统检查 + 包管理器安装 |
| 第3章 | 60分钟 | Python 环境 + 依赖安装 |
| 第4章 | 30分钟 | Node.js + TS 编译器构建 |
| 第5章 | 20分钟 | FFmpeg 安装与配置 |
| 第6章 | 45分钟 | AE MCP 安装 + Bridge 配置 |
| 第7章 | 30分钟 | MCP 扩展工具部署 |
| 第8章 | 30分钟 | Python-TS 桥接配置 |
| 第9章 | 25分钟 | 端到端流水线配置 |
| 第10章 | 20分钟 | 辅助软件安装 |
| 第11-12章 | 30分钟 | 安全配置 + 验证测试 |
| **总计** | **4小时** | |

#### 1.4.2 老手路径（1小时）

| 阶段 | 预计耗时 | 操作内容 |
|------|---------|---------|
| 第2-5章 | 30分钟 | 基础环境一键部署 |
| 第6-7章 | 15分钟 | MCP 安装与配置 |
| 第8-9章 | 10分钟 | 桥接与流水线配置 |
| 第12章 | 5分钟 | 冒烟测试验证 |
| **总计** | **1小时** | |

> [!success] 加速技巧
> - 新手建议逐章阅读，确保每一步验证通过再继续
> - 老手可直接跳转至 [[#附录A：一键部署脚本]] 使用自动化脚本
> - 网络较慢时，可提前下载好安装包备用

### 1.5 部署完成验证清单

> [!check] 最终验证清单
> 部署完成后，请逐项勾选以下内容，确保系统完全可用：
>
> - [ ] Windows 系统版本符合要求
> - [ ] PowerShell 可正常运行
> - [ ] Chocolatey / Scoop 包管理器可用
> - [ ] Git 安装并配置完成
> - [ ] Python 3.11 环境可用
> - [ ] 所有 Python 核心依赖导入成功
> - [ ] Node.js 20 LTS 可用
> - [ ] npm 可正常安装包
> - [ ] TypeScript 编译器可用
> - [ ] AE 编译器构建成功
> - [ ] FFmpeg 6.x 可用
> - [ ] FFmpeg 硬件加速验证通过
> - [ ] After Effects 2025 可正常启动
> - [ ] MCP Bridge 面板安装完成
> - [ ] MCP 服务可正常连接
> - [ ] 14个扩展 MCP 工具全部注册
> - [ ] JSX 脚本可在 AE 中执行
> - [ ] Python-TS 桥接 Subprocess 模式可用
> - [ ] Python-TS 桥接 FastAPI 模式可用（可选）
> - [ ] autoEdit 入口配置完成
> - [ ] 项目目录结构初始化成功
> - [ ] 端到端测试跑通完整流程

> [!note] 更多验证项
> 完整的 50+ 项验证清单请参见 [[#第12章 部署验证与验收]]

---

## 第2章 基础环境准备

### 2.1 Windows 系统检查

#### 2.1.1 系统版本检查

首先确认你的 Windows 版本符合要求：

```powershell
# 查看 Windows 版本
winver

# 或者使用 PowerShell 命令
[System.Environment]::OSVersion.Version
Get-ComputerInfo | Select-Object OsName, OsVersion, WindowsVersion
```

> [!success] 验证标准
> - Windows 10: 版本 ≥ 21H2（内部版本 19044）
> - Windows 11: 版本 ≥ 22H2（内部版本 22621）
> - 系统类型：64位操作系统

#### 2.1.2 PowerShell 版本检查

```powershell
# 查看 PowerShell 版本
$PSVersionTable.PSVersion

# 查看详细信息
$PSVersionTable
```

> [!tip] 升级 PowerShell（推荐）
> Windows 10/11 自带的 PowerShell 5.1 也能用，但推荐安装 PowerShell 7.x：
>
> ```powershell
> # 使用 winget 安装（Windows 11 自带）
> winget install Microsoft.PowerShell
>
> # 或者使用 MSI 安装包
> # 下载地址：https://aka.ms/PSWindows
> ```

#### 2.1.3 管理员权限确认

```powershell
# 检查当前是否以管理员身份运行
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

> [!warning] 重要
> 返回 `True` 表示有管理员权限，返回 `False` 请右键 PowerShell 选择「以管理员身份运行」。
> 安装大部分软件都需要管理员权限。

#### 2.1.4 系统架构检查

```powershell
# 确认系统架构（应该是 x64）
[System.Environment]::Is64BitOperatingSystem
[System.Environment]::Is64BitProcess
```

### 2.2 包管理器安装

Windows 下有两种主流包管理器：**Chocolatey** 和 **Scoop**。推荐二选一即可，新手推荐 Chocolatey。

#### 2.2.1 方案A：Chocolatey 安装（推荐）

Chocolatey 是 Windows 最成熟的包管理器，软件源最丰富。

```powershell
# 1. 检查是否已安装
choco --version

# 2. 如果未安装，执行以下命令安装
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 3. 安装完成后，刷新环境变量
refreshenv

# 4. 验证安装
choco --version
```

> [!success] 验证标准
> 输出版本号（如 `2.2.2`）表示安装成功。

**常用 Chocolatey 命令**：

```powershell
# 搜索软件
choco search <软件名>

# 安装软件
choco install <软件名> -y

# 升级软件
choco upgrade <软件名> -y

# 卸载软件
choco uninstall <软件名> -y

# 查看已安装软件
choco list --localonly
```

#### 2.2.2 方案B：Scoop 安装

Scoop 更轻量，安装到用户目录，不需要管理员权限。

```powershell
# 1. 允许本地脚本执行
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 2. 安装 Scoop
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression

# 3. 添加常用 bucket
scoop bucket add extras
scoop bucket add versions
scoop bucket add nerd-fonts

# 4. 验证安装
scoop --version
```

> [!note] 路径说明
> - Scoop 默认安装到 `C:\Users\<用户名>\scoop\`
> - 全局安装（需要管理员）到 `C:\ProgramData\scoop\`

#### 2.2.3 国内镜像加速（重要）

由于网络原因，国内用户建议配置镜像加速：

**Chocolatey 国内源**：

```powershell
# 配置中科大源
choco source add -n=ustc -s="https://mirrors.ustc.edu.cn/chocolatey/"

# 或者配置清华源
choco source add -n=tuna -s="https://mirrors.tuna.tsinghua.edu.cn/chocolatey/"

# 查看当前源
choco source list
```

**Scoop 国内镜像**：

```powershell
# 配置 scoop 本身的镜像
scoop config SCOOP_REPO "https://mirrors.ustc.edu.cn/git/scoop.git"
scoop update

# 配置 bucket 镜像
scoop bucket rm main
scoop bucket add main "https://mirrors.ustc.edu.cn/git/scoop-main.git"
```

### 2.3 Git 安装与配置

#### 2.3.1 Git 安装

**方式一：使用包管理器（推荐）**

```powershell
# Chocolatey
choco install git -y

# 或者 Scoop
scoop install git
```

**方式二：官网下载安装**

1. 访问 https://git-scm.com/download/win
2. 下载 64-bit Git for Windows Setup
3. 运行安装程序，一路 Next 即可（默认选项都没问题）

#### 2.3.2 验证安装

```powershell
# 验证 Git 版本
git --version

# 验证 Git 位置
Get-Command git | Select-Object Source
```

> [!success] 验证标准
> 输出类似 `git version 2.44.0.windows.1` 表示成功。

#### 2.3.3 Git 基础配置

```powershell
# 配置用户名（替换为你的名字）
git config --global user.name "Your Name"

# 配置邮箱（替换为你的邮箱）
git config --global user.email "your.email@example.com"

# 配置默认分支名
git config --global init.defaultBranch main

# 配置换行符处理（Windows 推荐）
git config --global core.autocrlf true

# 配置密码存储（避免每次输入密码）
git config --global credential.helper manager

# 查看所有配置
git config --list
```

#### 2.3.4 国内 Git 加速

```powershell
# GitHub 镜像加速（可选，访问 GitHub 慢时使用）
# 注意：这只是示例，实际使用时请在 clone 时替换域名
# 例如：将 https://github.com/xxx/yyy.git
# 改为：https://ghproxy.com/https://github.com/xxx/yyy.git

# 配置 Git 代理（如果你有代理）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```


#### 2.3.4 Git 高级配置（推荐）

```powershell
# 配置默认分支名为 main
git config --global init.defaultBranch main

# 配置换行符处理（Windows 下重要）
git config --global core.autocrlf true
git config --global core.safecrlf warn

# 配置文件名大小写敏感（避免跨平台问题）
git config --global core.ignorecase false

# 配置提交编码
git config --global i18n.commitencoding utf-8
git config --global gui.encoding utf-8

# 配置日志输出颜色
git config --global color.ui auto

# 配置别名（提高效率）
git config --global alias.st status
git config --global alias.ci commit
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.lg "log --oneline --graph --all --decorate"

# 查看所有配置
git config --global --list
```

> [!tip] 为什么配置 core.autocrlf
> Windows 使用 CRLF（\r\n）作为换行符，而 Linux/macOS 使用 LF（\n）。
> 配置 `core.autocrlf true` 可以让 Git 在提交时自动转换为 LF，检出时转换为 CRLF，
> 避免跨平台协作时出现整文件 diff 的问题。

#### 2.3.5 SSH Key 配置（可选，推荐）

如果你使用 SSH 方式克隆 Git 仓库，需要配置 SSH Key：

```powershell
# 1. 生成 SSH Key（替换为你的邮箱）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 一路回车，使用默认路径和空密码（或设置密码）

# 2. 启动 ssh-agent
Get-Service ssh-agent | Set-Service -StartupType Manual
Start-Service ssh-agent

# 3. 添加私钥
ssh-add $env:USERPROFILE\.ssh\id_ed25519

# 4. 查看公钥，复制到 GitHub/GitLab 等平台
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub

# 5. 测试连接
ssh -T git@github.com
```

> [!success] 验证标准
> 输出类似 `Hi username! You've successfully authenticated...` 表示 SSH 配置成功。

### 2.3.6 Git LFS 安装与配置（大文件管理）

视频项目经常涉及大文件（视频素材、AE 工程、模型文件），Git LFS 可以有效管理大文件：

```powershell
# 安装 Git LFS
# Chocolatey
choco install git-lfs -y

# 或者 Scoop
scoop install git-lfs

# 初始化 Git LFS
git lfs install

# 验证安装
git lfs version
```

**常用 LFS 操作**：

```powershell
# 追踪特定类型的文件
git lfs track "*.mp4"
git lfs track "*.aep"
git lfs track "*.psd"
git lfs track "*.wav"
git lfs track "models/*.pth"

# 查看当前追踪的文件类型
git lfs track

# 查看 LFS 文件列表
git lfs ls-files

# 迁移已有仓库中的大文件到 LFS
# git lfs migrate import --include="*.mp4,*.aep,*.psd"
```

> [!warning] 注意事项
> - Git LFS 有存储配额限制（GitHub 免费版 1GB 存储 + 1GB/月带宽）
> - 克隆 LFS 仓库需要安装 Git LFS 客户端
> - 大文件 push/pull 会占用带宽，请谨慎使用

### 2.4 目录结构规划

合理的目录结构是后续维护的基础，推荐如下规划：

```
C:\
├── Tools\                      # 工具软件目录
│   ├── Python311\              # Python 安装目录
│   ├── nodejs\                 # Node.js 安装目录
│   ├── ffmpeg\                 # FFmpeg 安装目录
│   └── git\                    # Git 安装目录
│
├── Projects\                   # 项目目录
│   ├── AE-MotionStudio\        # 主项目
│   │   ├── compiler\           # TS 编译器
│   │   ├── python-server\      # Python 分析服务
│   │   ├── mcp-extension\      # MCP 扩展工具
│   │   └── scripts\            # 辅助脚本
│   └── other-projects\         # 其他项目
│
├── Cache\                      # 缓存目录
│   ├── pip-cache\              # pip 缓存
│   ├── npm-cache\              # npm 缓存
│   ├── torch-cache\            # PyTorch 模型缓存
│   └── huggingface-cache\      # HuggingFace 模型缓存
│
├── Workspace\                  # 工作目录
│   ├── AE-Projects\            # AE 工程文件
│   ├── Footage\                # 素材库
│   ├── Music\                  # 音乐库
│   └── Exports\                # 输出目录
│
└── Knowledge-Vault\            # 知识库（已存在）
    └── AE-Knowledge-Vault\     # AE 知识库
```

#### 2.4.1 创建目录结构

```powershell
# 创建基础目录
$dirs = @(
    "C:\Tools",
    "C:\Projects",
    "C:\Cache\pip-cache",
    "C:\Cache\npm-cache",
    "C:\Cache\torch-cache",
    "C:\Cache\huggingface-cache",
    "C:\Workspace\AE-Projects",
    "C:\Workspace\Footage",
    "C:\Workspace\Music",
    "C:\Workspace\Exports"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force
        Write-Host "Created: $dir"
    } else {
        Write-Host "Already exists: $dir"
    }
}
```

> [!tip] 目录选择建议
> - 工具目录建议放在系统盘 SSD 上，启动更快
> - 素材和输出目录可放在大容量 HDD 上
> - 缓存目录建议定期清理

### 2.5 环境变量配置

#### 2.5.1 查看当前环境变量

```powershell
# 查看用户环境变量
[Environment]::GetEnvironmentVariables("User")

# 查看系统环境变量
[Environment]::GetEnvironmentVariables("Machine")

# 查看 PATH
$env:PATH -split ';' | Where-Object { $_ -ne '' }
```

#### 2.5.2 添加环境变量

**用户环境变量（推荐，不需要管理员权限）**：

```powershell
# 添加到用户 PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$newPath = "C:\Tools\some-tool\bin"
if ($currentPath -notlike "*$newPath*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$newPath", "User")
    Write-Host "Added to User PATH: $newPath"
} else {
    Write-Host "Already in User PATH: $newPath"
}
```

**系统环境变量（需要管理员权限）**：

```powershell
# 添加到系统 PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$newPath = "C:\Tools\some-tool\bin"
if ($currentPath -notlike "*$newPath*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$newPath", "Machine")
    Write-Host "Added to System PATH: $newPath"
}
```

#### 2.5.3 配置常用环境变量

```powershell
# 配置缓存目录（Python）
[Environment]::SetEnvironmentVariable("PIP_CACHE_DIR", "C:\Cache\pip-cache", "User")
[Environment]::SetEnvironmentVariable("TORCH_HOME", "C:\Cache\torch-cache", "User")
[Environment]::SetEnvironmentVariable("HF_HOME", "C:\Cache\huggingface-cache", "User")
[Environment]::SetEnvironmentVariable("TRANSFORMERS_CACHE", "C:\Cache\huggingface-cache", "User")

# 配置 npm 缓存目录
npm config set cache "C:\Cache\npm-cache"

# 配置 AE 工作目录
[Environment]::SetEnvironmentVariable("AE_WORKSPACE", "C:\Workspace", "User")
```

#### 2.5.4 让环境变量立即生效

修改环境变量后，需要关闭并重新打开 PowerShell 才能生效。或者使用以下命令刷新：

```powershell
# 刷新当前会话的 PATH（仅部分生效，建议重开终端）
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

> [!warning] 注意
> 环境变量修改后，**必须重启 PowerShell** 才能完全生效。
> 某些软件可能需要重启电脑才能识别。

---

## 第3章 Python 环境部署

### 3.1 Anaconda / Miniconda 安装

Python 环境管理推荐使用 **Miniconda**（Anaconda 的精简版），它可以方便地创建和管理虚拟环境，避免依赖冲突。

#### 3.1.1 方案对比

| 方案 | 优点 | 缺点 | 推荐人群 |
|------|------|------|---------|
| **Miniconda** | 轻量（~100MB）、灵活、conda 环境管理 | 需要手动装包 | 所有用户 |
| Anaconda | 预装大量科学计算包 | 体积大（~3GB）、冗余多 | 数据科学家 |
| 系统 Python | 简单直接 | 容易搞乱系统环境 | 不推荐 |
| venv | Python 内置 | 不如 conda 灵活 | 简单项目 |

> [!success] 推荐方案
> 本指南使用 **Miniconda** 作为 Python 环境管理工具。

#### 3.1.2 Miniconda 安装

**方式一：使用包管理器**

```powershell
# Chocolatey
choco install miniconda3 -y

# 安装完成后，初始化 conda
# 以管理员身份打开 Anaconda Prompt（开始菜单搜索）
conda init powershell
```

**方式二：官网下载安装**

1. 访问 https://docs.conda.io/en/latest/miniconda.html
2. 下载 **Miniconda3 Windows 64-bit**（Python 3.11 版本）
3. 运行安装程序：
   - 安装路径：`C:\Tools\Miniconda3`
   - ✅ 勾选「Add Miniconda3 to my PATH environment variable」（不推荐，但方便）
   - 或者不勾选，使用开始菜单的「Anaconda Prompt」
4. 安装完成后，打开 Anaconda PowerShell Prompt

**方式三：命令行静默安装**

```powershell
# 下载安装包
Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-py311_24.1.2-0-Windows-x86_64.exe" -OutFile "C:\Temp\miniconda.exe"

# 静默安装
Start-Process -FilePath "C:\Temp\miniconda.exe" -ArgumentList "/S","/D=C:\Tools\Miniconda3" -Wait

# 初始化 conda
& "C:\Tools\Miniconda3\shell\condabin\conda-hook.ps1"
conda init powershell
```

#### 3.1.3 验证安装

```powershell
# 打开新的 PowerShell 窗口，验证 conda
conda --version

# 查看 conda 信息
conda info

# 查看当前环境
conda info --envs
```

> [!success] 验证标准
> 输出版本号（如 `conda 24.1.2`）表示安装成功。

#### 3.1.4 配置国内镜像源（重要）

conda 默认源在国外，国内访问很慢，必须配置镜像：

```powershell
# 配置清华镜像源
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch

# 设置搜索时显示通道地址
conda config --set show_channel_urls yes

# 查看配置
conda config --show channels
```

> [!note] 其他镜像源
> - 中科大：https://mirrors.ustc.edu.cn/anaconda/
> - 上海交大：https://mirrors.sjtug.sjtu.edu.cn/anaconda/

### 3.2 虚拟环境创建与管理

#### 3.2.1 创建专用虚拟环境

为我们的 AI 视频生成系统创建一个专用的虚拟环境：

```powershell
# 创建 Python 3.11 的虚拟环境，命名为 ae-ai
conda create -n ae-ai python=3.11 -y

# 激活环境
conda activate ae-ai

# 验证 Python 版本
python --version

# 验证 pip
pip --version
```

> [!success] 验证标准
> - Python 版本：`Python 3.11.x`
> - 命令行提示符前出现 `(ae-ai)` 表示环境已激活

#### 3.2.2 虚拟环境常用命令

```powershell
# 查看所有环境
conda env list

# 创建环境（指定 Python 版本）
conda create -n env_name python=3.11

# 激活环境
conda activate env_name

# 退出环境
conda deactivate

# 删除环境
conda remove -n env_name --all

# 克隆环境
conda create -n new_env --clone old_env

# 导出环境配置
conda env export > environment.yml

# 从配置文件创建环境
conda env create -f environment.yml
```

#### 3.2.3 pip 镜像配置

同样配置 pip 的国内镜像：

```powershell
# 配置 pip 清华源（全局）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 配置 pip 信任主机
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 查看 pip 配置
pip config list

# 或者直接写配置文件
# 配置文件位置：$env:APPDATA\pip\pip.ini
```

> [!tip] 其他 pip 镜像
> - 阿里云：https://mirrors.aliyun.com/pypi/simple/
> - 中科大：https://pypi.mirrors.ustc.edu.cn/simple/
> - 豆瓣：https://pypi.douban.com/simple/

### 3.3 核心依赖安装

激活 `ae-ai` 环境后，安装核心依赖。

#### 3.3.1 基础科学计算库

```powershell
# 确保在 ae-ai 环境中
conda activate ae-ai

# 安装 numpy + mkl（Intel MKL 加速）
conda install numpy scipy -y

# 验证 numpy
python -c "import numpy; print(f'numpy: {numpy.__version__}'); print(f'numpy config: {numpy.__config__.show()}')"
```

#### 3.3.2 音频处理库

```powershell
# librosa（音乐分析核心库）
pip install librosa==0.10.1

# soundfile（音频文件读写）
pip install soundfile==0.12.1

# pydub（高级音频处理）
pip install pydub==0.25.1

# 验证音频库
python -c "
import librosa
import soundfile
import pydub
print(f'librosa: {librosa.__version__}')
print(f'soundfile: {soundfile.__version__}')
print(f'pydub: {pydub.__version__}')
print('All audio libraries OK!')
"
```

> [!warning] librosa 依赖
> librosa 依赖 `libsndfile`，在 Windows 上通常会自动安装。
> 如果遇到问题，可以单独安装：`pip install soundfile`

#### 3.3.3 计算机视觉库

```powershell
# OpenCV（视频/图像处理）
pip install opencv-python==4.8.1.78

# opencv-contrib-python（额外模块，可选）
pip install opencv-contrib-python==4.8.1.78

# 验证 OpenCV
python -c "
import cv2
print(f'OpenCV: {cv2.__version__}')
print(f'OpenCV CUDA: {cv2.cuda.getCudaEnabledDeviceCount() > 0}')
print('OpenCV OK!')
"
```

#### 3.3.4 机器学习库

```powershell
# scikit-learn（机器学习基础）
pip install scikit-learn==1.3.2

# 验证
python -c "
import sklearn
print(f'scikit-learn: {sklearn.__version__}')
print('scikit-learn OK!')
"
```

#### 3.3.5 其他核心工具库

```powershell
# PyYAML（YAML 配置文件）
pip install pyyaml==6.0.1

# 点击（命令行工具）
pip install click==8.1.7

# 进度条
pip install tqdm==4.66.1

# 类型提示
pip install typing-extensions==4.9.0

# 验证所有核心依赖
python -c "
import yaml
import click
import tqdm
print(f'PyYAML: {yaml.__version__}')
print(f'click: {click.__version__}')
print(f'tqdm: {tqdm.__version__}')
print('All utility libraries OK!')
"
```

### 3.4 可选依赖安装

#### 3.4.1 PyTorch（深度学习）

PyTorch 是 CLIP 语义匹配等高级功能的基础。

**CUDA 版本（有 NVIDIA 显卡）**：

```powershell
# CUDA 12.1 版本（推荐，RTX 30/40 系列）
pip install torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8 版本（老显卡，RTX 20 系列及更早）
pip install torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu118
```

**CPU 版本（无 NVIDIA 显卡）**：

```powershell
pip install torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cpu
```

**验证 PyTorch 安装**：

```powershell
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU count: {torch.cuda.device_count()}')
    print(f'GPU name: {torch.cuda.get_device_name(0)}')
print('PyTorch OK!')
"
```

> [!success] 验证标准
> 有显卡的机器应该显示 `CUDA available: True`，否则检查显卡驱动和 CUDA 版本。

#### 3.4.2 madmom（高级音乐分析）

```powershell
# madmom（更精确的节拍检测）
# 注意：madmom 依赖 cython 和 numpy
pip install cython
pip install madmom==0.16.1

# 验证
python -c "
import madmom
print(f'madmom: {madmom.__version__}')
print('madmom OK!')
"
```

> [!warning] madmom 兼容性
> madmom 在 Python 3.11 上可能需要从源码编译，如果 pip 安装失败，可以尝试：
> ```powershell
> pip install git+https://github.com/CPJKU/madmom.git
> ```

#### 3.4.3 essentia（音频特征提取）

```powershell
# essentia（专业音频分析）
pip install essentia==2.1b6.dev1110

# 验证
python -c "
import essentia
print(f'essentia: {essentia.__version__}')
print('essentia OK!')
"
```

#### 3.4.4 PySceneDetect（场景检测）

```powershell
# PySceneDetect（视频场景切换检测）
pip install scenedetect[opencv]==0.6.3

# 验证
scenedetect --version

# Python 库验证
python -c "
from scenedetect import SceneManager, open_video, ContentDetector
print('PySceneDetect OK!')
"
```


### 3.4.3 依赖版本锁定与复现

为了确保环境可复现，建议锁定所有依赖版本：

```powershell
# 激活环境
conda activate ae-ai

# 导出 conda 环境配置
conda env export > environment.yml

# 导出 pip 包列表
pip freeze > requirements.txt

# 查看已安装的包
conda list
pip list
```

**environment.yml 示例**：

```yaml
name: ae-ai
channels:
  - defaults
  - conda-forge
  - pytorch
dependencies:
  - python=3.11.8
  - numpy=1.26.4
  - scipy=1.11.4
  - scikit-learn=1.4.0
  - pip=24.0
  - pip:
    - librosa==0.10.1
    - opencv-python==4.8.1.78
    - pydub==0.25.1
    - soundfile==0.12.1
```

**从配置文件复现环境**：

```powershell
# 从 environment.yml 创建环境
conda env create -f environment.yml

# 从 requirements.txt 安装 pip 依赖
pip install -r requirements.txt
```

> [!tip] 最佳实践
> - 每次重大依赖变更后都更新 environment.yml 和 requirements.txt
> - 将这两个文件纳入版本控制
> - 在新机器上部署时优先使用 environment.yml

### 3.4.4 虚拟环境管理最佳实践

```powershell
# 列出所有虚拟环境
conda env list
conda info --envs

# 激活环境
conda activate ae-ai

# 退出当前环境
conda deactivate

# 克隆环境（用于测试）
conda create --name ae-ai-test --clone ae-ai

# 删除环境（谨慎操作）
# conda remove --name ae-ai-test --all

# 清理缓存（释放空间）
conda clean --all
pip cache purge
```

> [!warning] 环境管理注意事项
> - 不要在 base 环境中安装项目依赖
> - 每个项目使用独立的虚拟环境
> - 定期清理不用的环境释放磁盘空间
> - 升级依赖前先克隆环境做测试

### 3.5 Windows 特殊问题处理

#### 3.5.1 numpy + MKL 加速

Anaconda 默认的 numpy 已经使用 MKL 加速。如果你使用系统 Python 或 venv，可能需要手动安装 MKL 版本：

```powershell
# 检查当前 numpy 是否使用 MKL
python -c "import numpy; numpy.show_config()"

# 如果没有 MKL，可以使用 conda 重新安装
conda install numpy -c conda-forge
```

**MKL 多线程配置**：

```powershell
# 配置 MKL 线程数（根据 CPU 核心数调整）
[Environment]::SetEnvironmentVariable("MKL_NUM_THREADS", "8", "User")
[Environment]::SetEnvironmentVariable("OMP_NUM_THREADS", "8", "User")
[Environment]::SetEnvironmentVariable("OPENBLAS_NUM_THREADS", "8", "User")
```

> [!tip] 性能优化
> - MKL 线程数建议设置为物理核心数（不是超线程数）
> - 过多线程反而会因线程切换降低性能
> - Intel CPU 用 MKL，AMD CPU 可以用 OpenBLAS

#### 3.5.2 CUDA 安装与配置

如果使用 NVIDIA GPU，需要安装 CUDA Toolkit：

**步骤 1：检查显卡驱动**

```powershell
# 查看显卡信息
nvidia-smi

# 查看驱动支持的最高 CUDA 版本
# 在 nvidia-smi 输出的右上角可以看到 CUDA Version
```

> [!note] 驱动版本要求
> - CUDA 12.x 需要驱动版本 ≥ 525.60
> - CUDA 11.8 需要驱动版本 ≥ 450.80
> - 驱动可以向下兼容，安装最新驱动即可

**步骤 2：安装 CUDA Toolkit（可选）**

> [!info] PyTorch 自带 CUDA
> 使用 `pip install torch` 安装的 PyTorch 已经自带了 CUDA 运行时，
> 通常不需要单独安装 CUDA Toolkit。只有在需要编译 CUDA 代码时才需要安装。

如果需要安装：

1. 访问 https://developer.nvidia.com/cuda-toolkit-archive
2. 选择对应版本（推荐 CUDA 12.1）
3. 下载并安装
4. 安装路径：`C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1`

**步骤 3：安装 cuDNN（可选）**

1. 访问 https://developer.nvidia.com/rdp/cudnn-download
2. 下载对应 CUDA 版本的 cuDNN
3. 解压后将文件复制到 CUDA 安装目录

**验证 CUDA + cuDNN**：

```powershell
# 验证 CUDA
nvcc --version

# 验证 cuDNN（通过 PyTorch）
python -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'cuDNN available: {torch.backends.cudnn.is_available()}')
print(f'cuDNN version: {torch.backends.cudnn.version()}')
"
```

#### 3.5.3 代理设置

如果在公司网络或使用代理，需要配置 pip 和 conda 的代理：

**pip 代理设置**：

```powershell
# 临时使用代理
pip install package --proxy http://127.0.0.1:7890

# 永久设置代理
pip config set global.proxy http://127.0.0.1:7890

# 取消代理
pip config unset global.proxy
```

**conda 代理设置**：

```powershell
# 设置代理
conda config --set proxy_servers.http http://127.0.0.1:7890
conda config --set proxy_servers.https http://127.0.0.1:7890

# 取消代理
conda config --remove-key proxy_servers
```

**环境变量代理**：

```powershell
# 临时设置（当前会话）
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"

# 永久设置
[Environment]::SetEnvironmentVariable("HTTP_PROXY", "http://127.0.0.1:7890", "User")
[Environment]::SetEnvironmentVariable("HTTPS_PROXY", "http://127.0.0.1:7890", "User")
```

#### 3.5.4 常见错误与解决方案

| 错误现象 | 可能原因 | 解决方案 |
|---------|---------|---------|
| `ImportError: DLL load failed` | 缺少 Visual C++ 运行库 | 安装 VC++ Redistributable |
| `ModuleNotFoundError: No module named 'cv2'` | OpenCV 未安装或环境不对 | 激活正确环境后 `pip install opencv-python` |
| `librosa 安装失败` | 缺少依赖 | 先安装 `numpy scipy soundfile` |
| `torch.cuda.is_available() 返回 False` | CUDA 不可用 | 检查显卡驱动、PyTorch CUDA 版本 |
| `pip install 很慢或超时` | 网络问题 | 配置国内镜像源或使用代理 |
| `conda 安装很慢` | 源在国外 | 配置国内 conda 镜像 |
| `Permission denied` | 权限不足 | 以管理员身份运行 PowerShell |
| `文件名太长` | Windows 路径长度限制 | 启用长路径支持 |

**启用 Windows 长路径支持**：

```powershell
# 需要管理员权限
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# 验证
Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled"
```

### 3.6 综合验证脚本

完成所有安装后，运行以下综合验证脚本：

```powershell
# 确保在 ae-ai 环境中
conda activate ae-ai

# 综合验证
python -c "
import sys
print('=' * 60)
print('Python Environment Verification')
print('=' * 60)
print(f'Python version: {sys.version}')
print(f'Python executable: {sys.executable}')
print()

# 核心库
print('--- Core Libraries ---')
import numpy
print(f'numpy: {numpy.__version__}')
import scipy
print(f'scipy: {scipy.__version__}')
import sklearn
print(f'scikit-learn: {sklearn.__version__}')
print()

# 音频库
print('--- Audio Libraries ---')
import librosa
print(f'librosa: {librosa.__version__}')
import soundfile
print(f'soundfile: {soundfile.__version__}')
import pydub
print(f'pydub: {pydub.__version__}')
print()

# 视觉库
print('--- Vision Libraries ---')
import cv2
print(f'OpenCV: {cv2.__version__}')
print(f'OpenCV CUDA: {cv2.cuda.getCudaEnabledDeviceCount() > 0}')
print()

# 深度学习
print('--- Deep Learning ---')
try:
    import torch
    print(f'PyTorch: {torch.__version__}')
    print(f'CUDA available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)}')
except ImportError:
    print('PyTorch: not installed (optional)')
print()

# 可选库
print('--- Optional Libraries ---')
try:
    import madmom
    print(f'madmom: {madmom.__version__}')
except ImportError:
    print('madmom: not installed (optional)')

try:
    import essentia
    print(f'essentia: {essentia.__version__}')
except ImportError:
    print('essentia: not installed (optional)')

try:
    import yaml
    print(f'PyYAML: {yaml.__version__}')
except ImportError:
    print('PyYAML: not installed')
print()

print('=' * 60)
print('All core libraries OK! ✅')
print('=' * 60)
"
```

> [!success] 验证标准
> 所有核心库（numpy/scipy/librosa/cv2 等）都应该输出版本号且无报错。
> 可选库（torch/madmom/essentia）可以根据需要安装。

> [!info] 参考文档
> Python 生态详情参见 [[Python生态与系统集成深度研究报告]]

---

## 第4章 Node.js 与 TypeScript 环境

### 4.1 Node.js 安装

Node.js 是运行 TypeScript 编译器和 MCP 服务的基础。

#### 4.1.1 安装方式对比

| 安装方式 | 优点 | 缺点 | 推荐度 |
|---------|------|------|--------|
| **nvm-windows** | 多版本管理、切换方便 | 稍复杂 | ⭐⭐⭐⭐⭐ |
| 官网安装包 | 简单直接 | 多版本麻烦 | ⭐⭐⭐⭐ |
| Chocolatey | 包管理器统一管理 | 版本选择少 | ⭐⭐⭐ |
| Scoop | 轻量 | 版本选择少 | ⭐⭐⭐ |

> [!success] 推荐方案
> 开发环境推荐使用 **nvm-windows**，可以方便地切换 Node.js 版本。
> 生产环境可以直接安装 LTS 版本。

#### 4.1.2 方案A：nvm-windows（推荐）

**步骤 1：安装 nvm-windows**

```powershell
# 使用 Chocolatey 安装
choco install nvm -y

# 或者官网下载安装
# 下载地址：https://github.com/coreybutler/nvm-windows/releases
```

**步骤 2：安装 Node.js 20 LTS**

```powershell
# 安装 Node.js 20 LTS
nvm install 20.11.1

# 切换到 20.11.1
nvm use 20.11.1

# 设置默认版本
nvm alias default 20.11.1
```

**步骤 3：验证安装**

```powershell
# 验证 Node.js
node --version

# 验证 npm
npm --version

# 查看已安装的 Node 版本
nvm list
```

> [!success] 验证标准
> - Node.js 版本：`v20.11.1`（或其他 20.x LTS）
> - npm 版本：`10.x`

#### 4.1.3 方案B：官网安装包

1. 访问 https://nodejs.org/
2. 下载 **LTS** 版本（20.x）
3. 运行安装程序，一路 Next
4. 安装完成后重启 PowerShell
5. 验证：

```powershell
node --version
npm --version
```

#### 4.1.4 方案C：包管理器

```powershell
# Chocolatey
choco install nodejs-lts -y

# Scoop
scoop install nodejs-lts
```

### 4.2 npm 配置

#### 4.2.1 国内镜像配置（重要）

```powershell
# 配置淘宝镜像（推荐）
npm config set registry https://registry.npmmirror.com

# 验证配置
npm config get registry

# 或者使用 nrm 管理多个源
npm install -g nrm
nrm ls
nrm use taobao
```

> [!note] 其他 npm 镜像
> - 华为云：https://mirrors.huaweicloud.com/repository/npm/
> - 腾讯云：https://mirrors.cloud.tencent.com/npm/

#### 4.2.2 缓存目录配置

```powershell
# 设置缓存目录（默认在用户目录下，可能占用 C 盘空间）
npm config set cache "C:\Cache\npm-cache"

# 查看缓存位置
npm config get cache

# 清理缓存
npm cache clean --force
```

#### 4.2.3 全局包目录配置

```powershell
# 设置全局包安装目录
npm config set prefix "C:\Tools\npm-global"

# 将全局目录添加到 PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$npmGlobal = "C:\Tools\npm-global"
if ($currentPath -notlike "*$npmGlobal*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$npmGlobal", "User")
    Write-Host "Added npm global to PATH"
}
```

#### 4.2.4 常用 npm 命令

```powershell
# 初始化项目
npm init

# 安装依赖
npm install <package>
npm install <package> --save-dev
npm install <package> -g

# 安装项目所有依赖
npm install

# 卸载依赖
npm uninstall <package>

# 更新依赖
npm update <package>

# 查看已安装包
npm list
npm list -g --depth=0

# 查看包信息
npm info <package>

# 运行脚本
npm run <script-name>
```

### 4.3 TypeScript 与 esbuild 安装

#### 4.3.1 全局安装 TypeScript

```powershell
# 全局安装 TypeScript
npm install -g typescript@5.3.3

# 验证
tsc --version
```

#### 4.3.2 全局安装 esbuild

```powershell
# 全局安装 esbuild
npm install -g esbuild@0.20.0

# 验证
esbuild --version
```

> [!info] 关于构建工具
> - **tsc**：官方 TypeScript 编译器，类型检查最完整
> - **esbuild**：极速构建工具，比 tsc 快 100 倍，但不做类型检查
> - 实际项目中，通常用 esbuild 做开发构建，tsc 做类型检查

### 4.4 AE 编译器构建

现在我们来构建 AE 编译器（TS 引擎层的核心）。

#### 4.4.1 获取项目代码

首先确保你有项目代码，如果还没有，先克隆：

```powershell
# 进入项目目录
cd C:\Projects

# 如果有 Git 仓库，克隆它
# git clone https://github.com/your-org/ae-ai-studio.git
# cd ae-ai-studio

# 如果是本地已有项目，直接进入对应目录
# 假设编译器代码在 Knowledge Vault 的 compiler 目录下
# 我们先复制一份到项目目录

$source = "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\compiler"
$dest = "C:\Projects\AE-MotionStudio\compiler"

if (Test-Path $source) {
    New-Item -ItemType Directory -Path (Split-Path $dest) -Force
    Copy-Item -Path $source -Destination $dest -Recurse -Force
    Write-Host "Compiler copied to: $dest"
}
```

#### 4.4.2 项目结构确认

```powershell
# 进入编译器目录
cd C:\Projects\AE-MotionStudio\compiler

# 查看目录结构
Get-ChildItem

# 查看 package.json
Get-Content package.json
```

编译器的典型结构：

```
compiler/
├── src/
│   ├── phase3/          # 阶段3：效果名称映射
│   ├── phase4/          # 阶段4：NLU 解析
│   ├── phase5/          # 阶段5：验证与学习
│   ├── cli.ts           # CLI 入口
│   ├── codegen.ts       # 代码生成
│   ├── index.ts         # 主入口
│   ├── ir-builder.ts    # IR 构建器
│   ├── scheduler.ts     # 调度器
│   ├── types.ts         # 类型定义
│   └── validator.ts     # 验证器
├── test/                # 测试
├── build/               # 构建输出
├── package.json
└── tsconfig.json
```

#### 4.4.3 安装依赖

```powershell
# 确保在编译器目录
cd C:\Projects\AE-MotionStudio\compiler

# 安装依赖
npm install

# 如果网络慢，可以使用淘宝镜像
# npm install --registry=https://registry.npmmirror.com
```

> [!tip] 依赖安装慢？
> 如果 `npm install` 很慢或超时：
> 1. 配置国内镜像（见上一节）
> 2. 使用代理：`npm install --proxy http://127.0.0.1:7890`
> 3. 删除 `node_modules` 和 `package-lock.json` 后重试

#### 4.4.4 构建项目

```powershell
# 构建项目（看 package.json 中的 scripts）
npm run build

# 或者使用 tsc 直接编译
# tsc

# 或者使用 esbuild 构建
# esbuild src/index.ts --bundle --platform=node --outfile=build/index.js
```

> [!note] 构建命令
> 具体的构建命令取决于 `package.json` 中的配置，请查看 `scripts` 部分。
> 常见的有：`npm run build`、`npm run compile` 等。

#### 4.4.5 验证构建结果

```powershell
# 查看构建输出
Get-ChildItem build/

# 测试运行
node build/index.js --help

# 或者测试 CLI
node build/cli.js --help
```

### 4.5 验证脚本：npm run test:phase3

项目通常带有测试套件，运行测试验证编译器是否正常工作。

#### 4.5.1 运行 Phase 3 测试

```powershell
# 确保在编译器目录
cd C:\Projects\AE-MotionStudio\compiler

# 查看可用的测试命令
npm run

# 运行 phase3 测试
npm run test:phase3
```

#### 4.5.2 运行所有测试

```powershell
# 运行所有测试
npm test

# 或者运行特定阶段的测试
npm run test:phase4
npm run test:phase5
```

#### 4.5.3 手动测试编译器

```powershell
# 手动测试编译器（示例）
# 创建一个测试输入
$testInput = @'
{
  "compName": "Test Comp",
  "width": 1920,
  "height": 1080,
  "duration": 5,
  "framerate": 30,
  "layers": [
    {
      "type": "solid",
      "name": "Background",
      "color": [0, 0, 0]
    }
  ]
}
'@ | ConvertFrom-Json

# 测试编译器（具体命令取决于项目）
# node build/cli.js compile --input test.json --output test.jsx
```

> [!info] 参考文档
> 编译器架构详情参见 [[原子参数编译器规范]] | [[AE 自动化引擎架构设计]]

---

## 第5章 FFmpeg 部署

### 5.1 FFmpeg 安装

FFmpeg 是视频处理的瑞士军刀，用于格式转换、编码、混音等。

#### 5.1.1 安装方式对比

| 安装方式 | 优点 | 缺点 | 推荐度 |
|---------|------|------|--------|
| **官网下载** | 版本选择多、完整功能 | 手动配置环境变量 | ⭐⭐⭐⭐⭐ |
| Chocolatey | 简单自动 | 版本可能不是最新 | ⭐⭐⭐⭐ |
| Scoop | 轻量方便 | 可选版本少 | ⭐⭐⭐ |
| 源码编译 | 完全可控 | 难度大、耗时长 | ⭐⭐ |

> [!success] 推荐方案
> 推荐从 **gyan.dev** 下载 Windows 版本的 FFmpeg，功能最全、更新及时。

#### 5.1.2 方案A：官网下载（推荐）

**步骤 1：下载 FFmpeg**

1. 访问 https://www.gyan.dev/ffmpeg/builds/
2. 下载 **release essentials** 或 **release full** 版本
   - essentials：常用功能（推荐，体积小）
   - full：包含所有编码器和滤镜（功能最全）
3. 下载 `.7z` 或 `.zip` 压缩包

**步骤 2：解压到指定目录**

```powershell
# 创建目录
New-Item -ItemType Directory -Path "C:\Tools\ffmpeg" -Force

# 假设下载的文件在 Downloads 目录
# 解压到 C:\Tools\ffmpeg
# 使用 Expand-Archive（仅支持 .zip）
# Expand-Archive -Path "$env:USERPROFILE\Downloads\ffmpeg-release-essentials.zip" -DestinationPath "C:\Tools\ffmpeg"

# 如果是 .7z，需要先安装 7-Zip
# choco install 7zip -y
# 然后使用 7z 解压
# & "C:\Program Files\7-Zip\7z.exe" x "$env:USERPROFILE\Downloads\ffmpeg-release-essentials.7z" -o"C:\Tools\ffmpeg"
```

**步骤 3：配置环境变量**

```powershell
# 找到 bin 目录（解压后的目录结构可能不同，根据实际情况调整）
# 通常是 C:\Tools\ffmpeg\ffmpeg-6.1-essentials_build\bin
# 我们创建一个符号链接或重命名目录，方便后续更新

# 假设实际 bin 路径是 C:\Tools\ffmpeg\ffmpeg-6.1-essentials_build\bin
# 创建符号链接（需要管理员权限）
New-Item -ItemType SymbolicLink -Path "C:\Tools\ffmpeg\bin" -Target "C:\Tools\ffmpeg\ffmpeg-6.1-essentials_build\bin"

# 添加到 PATH
$ffmpegBin = "C:\Tools\ffmpeg\bin"
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$ffmpegBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$ffmpegBin", "User")
    Write-Host "FFmpeg added to PATH"
}

# 刷新当前会话 PATH
$env:Path += ";$ffmpegBin"
```

#### 5.1.3 方案B：Chocolatey

```powershell
# 使用 Chocolatey 安装
choco install ffmpeg -y

# 验证
ffmpeg -version
```

#### 5.1.4 方案C：Scoop

```powershell
# 使用 Scoop 安装
scoop install ffmpeg

# 验证
ffmpeg -version
```

### 5.2 环境变量配置

#### 5.2.1 验证环境变量

```powershell
# 验证 ffmpeg 可用
ffmpeg -version

# 验证 ffprobe 可用
ffprobe -version

# 验证 ffplay 可用（full 版本才有）
ffplay -version
```

> [!success] 验证标准
> - `ffmpeg -version` 输出版本信息
> - 应该显示 `ffmpeg version 6.x` 或更高
> - 同时显示 `built with gcc` 等编译信息

#### 5.2.2 FFmpeg 环境变量

```powershell
# 设置 FFmpeg 根目录
[Environment]::SetEnvironmentVariable("FFMPEG_HOME", "C:\Tools\ffmpeg", "User")

# 设置 FFmpeg 配置文件目录（可选）
[Environment]::SetEnvironmentVariable("FFMPEG_DATADIR", "C:\Tools\ffmpeg\conf", "User")
```

### 5.3 常用滤镜与编码器验证

#### 5.3.1 查看支持的编码器

```powershell
# 查看所有编码器
ffmpeg -encoders

# 查看 H.264 编码器
ffmpeg -encoders | Select-String "264"

# 查看 H.265 编码器
ffmpeg -encoders | Select-String "265"

# 查看音频编码器
ffmpeg -encoders | Select-String "aac"
```

#### 5.3.2 查看支持的滤镜

```powershell
# 查看所有滤镜
ffmpeg -filters

# 查看特定滤镜
ffmpeg -filters | Select-String "scale"
ffmpeg -filters | Select-String "fade"
ffmpeg -filters | Select-String "crop"
```

#### 5.3.3 查看支持的格式

```powershell
# 查看所有支持的格式
ffmpeg -formats

# 查看 MP4 相关
ffmpeg -formats | Select-String "mp4"
```

#### 5.3.4 快速功能测试

```powershell
# 创建测试目录
New-Item -ItemType Directory -Path "C:\Temp\ffmpeg-test" -Force
cd C:\Temp\ffmpeg-test

# 生成测试视频（10秒彩色条）
ffmpeg -f lavfi -i testsrc=duration=10:size=1920x1080:rate=30 -c:v libx264 test_video.mp4 -y

# 生成测试音频（10秒 1kHz 正弦波）
ffmpeg -f lavfi -i "sine=frequency=1000:duration=10" -c:a aac test_audio.mp3 -y

# 查看视频信息
ffprobe -v quiet -print_format json -show_format -show_streams test_video.mp4

# 视频转码测试（H.264 → H.265）
ffmpeg -i test_video.mp4 -c:v libx265 -crf 28 test_video_hevc.mp4 -y

# 混音测试
ffmpeg -i test_video.mp4 -i test_audio.mp3 -c:v copy -c:a aac -short test_mixed.mp4 -y

Write-Host "FFmpeg test completed!"
```

### 5.4 硬件加速配置

硬件加速可以大幅提升视频编码速度。

#### 5.4.1 NVIDIA NVENC 配置

**检查 NVENC 支持**：

```powershell
# 查看 FFmpeg 是否支持 NVENC
ffmpeg -encoders | Select-String "nvenc"

# 查看 NVENC 编码器详情
ffmpeg -h encoder=h264_nvenc
ffmpeg -h encoder=hevc_nvenc
```

> [!note] NVENC 要求
> - NVIDIA 显卡（Kepler 架构及以上，GTX 600 系列以后）
> - 最新显卡驱动
> - FFmpeg 编译时启用了 NVENC（gyan.dev 的版本默认支持）

**测试 NVENC 编码**：

```powershell
cd C:\Temp\ffmpeg-test

# H.264 NVENC 编码测试
ffmpeg -i test_video.mp4 -c:v h264_nvenc -preset p5 -b:v 5M test_video_nvenc.mp4 -y

# H.265 NVENC 编码测试
ffmpeg -i test_video.mp4 -c:v hevc_nvenc -preset p5 -b:v 3M test_video_hevc_nvenc.mp4 -y
```

> [!tip] NVENC 性能
> - NVENC 编码速度通常比 CPU 快 5-10 倍
> - 质量略低于 libx264（相同码率下）
> - 适合快速预览和批量处理

#### 5.4.2 Intel QSV 配置

如果使用 Intel 核显或独显，可以用 QSV 硬件加速：

```powershell
# 查看 QSV 支持
ffmpeg -encoders | Select-String "qsv"

# 测试 QSV 编码
ffmpeg -i test_video.mp4 -c:v h264_qsv -preset medium test_video_qsv.mp4 -y
```

#### 5.4.3 AMD AMF 配置

```powershell
# 查看 AMF 支持
ffmpeg -encoders | Select-String "amf"

# 测试 AMF 编码
ffmpeg -i test_video.mp4 -c:v h264_amf -quality balanced test_video_amf.mp4 -y
```

#### 5.4.4 性能对比测试

```powershell
cd C:\Temp\ffmpeg-test

Write-Host "=== CPU 编码 (libx264) ==="
Measure-Command {
    ffmpeg -i test_video.mp4 -c:v libx264 -preset fast -crf 23 output_cpu.mp4 -y -hide_banner
} | Select-Object TotalSeconds

Write-Host "=== NVENC 编码 ==="
Measure-Command {
    ffmpeg -i test_video.mp4 -c:v h264_nvenc -preset p5 -cq 23 output_nvenc.mp4 -y -hide_banner
} | Select-Object TotalSeconds
```


#### 5.4.4 Intel QSV 硬件加速配置

Intel 核显用户可以使用 QSV (Quick Sync Video) 进行硬件加速：

```powershell
# 验证 QSV 支持
ffmpeg -encoders | Select-String "qsv"
ffmpeg -decoders | Select-String "qsv"
```

> [!tip] QSV 性能特点
> - **优点**：Intel CPU 自带，无需独立显卡，功耗低
> - **缺点**：编码质量略逊于 NVENC，兼容性一般
> - **适用**：笔记本电脑、无独立显卡的工作站

**QSV 编码测试**：

```powershell
# H.264 QSV 编码
ffmpeg -i input.mp4 -c:v h264_qsv -preset medium -b:v 5M output_qsv.mp4

# H.265 QSV 编码
ffmpeg -i input.mp4 -c:v hevc_qsv -preset medium -b:v 3M output_qsv_h265.mp4
```

#### 5.4.5 AMD AMF 硬件加速配置

AMD 显卡用户可以使用 AMF (Advanced Media Framework)：

```powershell
# 验证 AMF 支持
ffmpeg -encoders | Select-String "amf"
```

**AMF 编码测试**：

```powershell
# H.264 AMF 编码
ffmpeg -i input.mp4 -c:v h264_amf -quality balanced -b:v 5M output_amf.mp4
```

#### 5.4.6 硬件加速性能对比

不同硬件加速方案的性能参考（以 1080p H.264 编码为例）：

| 编码器 | 速度 | 质量 | 功耗 | 适用显卡 |
|--------|------|------|------|---------|
| libx264 (CPU) | 1x-3x | 最好 | 高 | 所有 CPU |
| h264_nvenc | 5x-10x | 好 | 中 | NVIDIA GTX 10xx+ |
| h264_qsv | 3x-6x | 中等 | 低 | Intel HD 500+ 核显 |
| h264_amf | 4x-8x | 好 | 中 | AMD RX 500+ |

> [!note] 速度说明
> 速度单位为实时倍数，1x = 实时播放速度。例如 10x 表示 1 分钟视频需要 6 秒编码完成。
> 实际速度取决于显卡型号、CPU 性能、视频分辨率等因素。

#### 5.4.7 常用滤镜验证

FFmpeg 提供了丰富的滤镜，以下是视频生成中常用的滤镜：

```powershell
# 列出所有可用滤镜
ffmpeg -filters

# 列出特定滤镜帮助
ffmpeg -h filter=scale
ffmpeg -h filter=fade
ffmpeg -h filter=trim
```

**常用视频滤镜**：

| 滤镜 | 用途 | 示例 |
|------|------|------|
| scale | 缩放 | `scale=1920:1080` |
| crop | 裁剪 | `crop=1280:720:(iw-1280)/2:(ih-720)/2` |
| trim | 截取片段 | `trim=start=10:duration=5` |
| fade | 淡入淡出 | `fade=t=in:st=0:d=1` |
| rotate | 旋转 | `rotate=PI/6` |
| eq | 色彩调整 | `eq=brightness=0.1:contrast=1.2` |
| unsharp | 锐化 | `unsharp=5:5:1.5` |
| deshake | 防抖 | `deshake` |

**常用音频滤镜**：

| 滤镜 | 用途 | 示例 |
|------|------|------|
| volume | 音量 | `volume=1.5` |
| afade | 淡入淡出 | `afade=t=in:st=0:d=1` |
| atrim | 截取片段 | `atrim=start=0:end=10` |
| acompressor | 压缩器 | `acompressor=threshold=-20dB:ratio=4:1` |
| loudnorm | 响度标准化 | `loudnorm=I=-16:TP=-1.5:LRA=11` |
| areverse | 反向播放 | `areverse` |
| apad | 填充静音 | `apad=pad_dur=1` |
| amerge | 合并声道 | `amerge=inputs=2` |

### 5.5 验证脚本：ffmpeg -encoders | grep nvenc

在 PowerShell 中使用 `Select-String` 替代 `grep`：

```powershell
# 验证 NVENC 支持
$nvencCount = (ffmpeg -encoders 2>&1 | Select-String "nvenc").Count
Write-Host "NVENC encoders found: $nvencCount"
if ($nvencCount -gt 0) {
    Write-Host "✅ NVENC hardware acceleration is available!"
} else {
    Write-Host "❌ NVENC not available. Check GPU and driver."
}

# 完整验证脚本
Write-Host "`n=== FFmpeg Verification ===" -ForegroundColor Cyan

# 版本
$version = ffmpeg -version 2>&1 | Select-Object -First 1
Write-Host "Version: $version"

# 编解码器数量
$encoders = (ffmpeg -encoders 2>&1 | Measure-Object -Line).Lines
$decoders = (ffmpeg -decoders 2>&1 | Measure-Object -Line).Lines
$filters = (ffmpeg -filters 2>&1 | Measure-Object -Line).Lines
Write-Host "Encoders: $encoders"
Write-Host "Decoders: $decoders"
Write-Host "Filters: $filters"

# 硬件加速
$nvenc = (ffmpeg -encoders 2>&1 | Select-String "nvenc").Count
$qsv = (ffmpeg -encoders 2>&1 | Select-String "qsv").Count
Write-Host "NVENC support: $($nvenc -gt 0)"
Write-Host "QSV support: $($qsv -gt 0)"

Write-Host "`n✅ FFmpeg verification complete!" -ForegroundColor Green
```

> [!success] 验证标准
> - FFmpeg 版本 ≥ 6.0
> - 有 NVENC 或 QSV 支持（有对应显卡的情况下）
> - 基础转码测试通过

> [!info] 参考文档
> FFmpeg 在工作流中的应用参见 [[图层操作与视频修剪工具链]] | [[音效设计原子体系与音画同步]]

---

## 第6章 After Effects MCP 部署

### 6.1 MCP 架构概述

#### 6.1.1 什么是 MCP

**MCP（Model Context Protocol）** 是一种用于连接 AI 助手与外部工具的开放协议。通过 MCP，AI 助手可以调用外部工具来执行各种操作，比如操作 After Effects、查询数据库、调用 API 等。

> [!info] 参考文档
> MCP 架构详情参见 [[MCP→AE效果操作桥接规范]]

#### 6.1.2 AE MCP 通信架构

AE MCP 采用**命令文件轮询**模式实现 Node.js 与 After Effects 之间的通信：

```
┌──────────────┐     写命令      ┌──────────────────┐    轮询读取     ┌───────────────────┐
│  Node.js     │ ──────────────→ │  ae_command.json │ ──────────────→ │  AE Bridge 面板   │
│  MCP Server  │                 │  (命令文件)       │                 │  (CEP/ScriptUI)    │
└──────┬───────┘                 └──────────────────┘                 └────────┬──────────┘
       │                                                                        │
       │                        ┌──────────────────┐                            │ evalScript()
       │    读取结果             │  ae_mcp_result   │ ←──────── 写结果 ────────── │
       │ ←───────────────────── │  .json (结果文件) │                             │
       │                        └──────────────────┘                             │
       │                                                                        ▼
       │                                                              ┌──────────────────┐
       │                                                              │  ExtendScript     │
       │                                                              │  (JSX 执行引擎)   │
       │                                                              └──────────────────┘
```

**通信流程详解**：

1. **MCP Server 接收请求**：AI 助手通过 MCP 协议发送工具调用请求
2. **命令写入**：MCP Server 将命令参数序列化为 JSON，写入 `ae_command.json`
3. **Bridge 轮询**：AE Bridge 面板以 250ms 间隔轮询命令文件
4. **命令解析**：Bridge 读取命令，验证白名单，解析参数
5. **JSX 执行**：通过 `evalScript()` 调用对应的 JSX 脚本
6. **结果写入**：执行完毕，将返回值写入 `ae_mcp_result.json`
7. **结果读取**：MCP Server 读取结果，响应给调用方

#### 6.1.3 默认工具清单（22+14=36个）

| 类别 | 工具数量 | 说明 |
|------|---------|------|
| 基础工具 | 22个 | after-effects-mcp 原生工具 |
| 扩展工具 | 14个 | Phase 2 扩展工具 |
| **总计** | **36个** | |

### 6.2 after-effects-mcp 仓库克隆与安装

#### 6.2.1 获取项目代码

```powershell
# 创建项目目录
New-Item -ItemType Directory -Path "C:\Projects" -Force
cd C:\Projects

# 克隆 after-effects-mcp 仓库
# 如果你有 GitHub 访问权限：
# git clone https://github.com/your-org/after-effects-mcp.git
# cd after-effects-mcp

# 如果是本地已有代码，直接复制到项目目录
# 假设代码在桌面的 after-effects-mcp-main 目录
$source = "$env:USERPROFILE\Desktop\after-effects-mcp-main"
$dest = "C:\Projects\after-effects-mcp"

if (Test-Path $source) {
    Copy-Item -Path $source -Destination $dest -Recurse -Force
    Write-Host "MCP project copied to: $dest"
} else {
    Write-Warning "Source not found: $source"
    Write-Warning "Please clone or download the after-effects-mcp project first"
}
```

#### 6.2.2 项目结构说明

```
after-effects-mcp/
├── src/
│   ├── scripts/           # JSX 脚本目录（AE 执行脚本）
│   │   ├── createComposition.jsx
│   │   ├── createTextLayer.jsx
│   │   ├── setLayerProperties.jsx
│   │   └── ... (更多 JSX 脚本)
│   ├── index.ts           # MCP Server 主入口
│   └── ... (其他 TS 文件)
├── bridge/                # AE Bridge 面板
│   ├── CSXS/              # CEP 扩展配置
│   └── ... (面板代码)
├── build/                 # 构建输出
├── package.json
├── tsconfig.json
└── README.md
```

### 6.3 npm install 与 npm run build

#### 6.3.1 安装依赖

```powershell
# 进入 MCP 项目目录
cd C:\Projects\after-effects-mcp

# 安装依赖
npm install

# 如果网络慢，使用淘宝镜像
# npm install --registry=https://registry.npmmirror.com
```

> [!tip] 依赖安装慢？
> 1. 配置 npm 国内镜像（参见第4章）
> 2. 使用代理：`npm install --proxy http://127.0.0.1:7890`
> 3. 删除 `node_modules` 和 `package-lock.json` 后重试

#### 6.3.2 构建项目

```powershell
# 构建 TypeScript
npm run build

# 验证构建结果
Get-ChildItem build/
```

> [!success] 验证标准
> - `npm run build` 执行成功，无报错
> - `build/` 目录下有 `index.js` 等输出文件

### 6.4 Bridge 面板安装

#### 6.4.1 Bridge 面板安装方式

**方式一：npm run install-bridge（推荐）**

```powershell
# 运行安装脚本
npm run install-bridge

# 或者手动运行安装脚本
# node scripts/install-bridge.js
```

**方式二：手动复制 CEP 扩展**

```powershell
# CEP 扩展目录
$cepExtensionsDir = "$env:APPDATA\Adobe\CEP\extensions"

# 创建目录（如果不存在）
New-Item -ItemType Directory -Path $cepExtensionsDir -Force

# 假设 Bridge 面板代码在项目的 bridge/ 目录下
$bridgeSource = "C:\Projects\after-effects-mcp\bridge"
$bridgeDest = "$cepExtensionsDir\AE-MCP-Bridge"

if (Test-Path $bridgeSource) {
    Copy-Item -Path $bridgeSource -Destination $bridgeDest -Recurse -Force
    Write-Host "Bridge panel installed to: $bridgeDest"
}
```

#### 6.4.2 启用 CEP 调试模式

由于我们的扩展是未签名的，需要启用 AE 的调试模式：

```powershell
# 设置注册表（需要管理员权限）
# CSXS.9 ~ CSXS.11 对应不同的 AE 版本

$regPaths = @(
    "HKCU:\Software\Adobe\CSXS.9",
    "HKCU:\Software\Adobe\CSXS.10",
    "HKCU:\Software\Adobe\CSXS.11",
    "HKCU:\Software\Adobe\CSXS.12"
)

foreach ($regPath in $regPaths) {
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force
    }
    Set-ItemProperty -Path $regPath -Name "PlayerDebugMode" -Value "1" -Type String
    Write-Host "Set PlayerDebugMode for: $regPath"
}
```

> [!warning] 重要
> 必须启用调试模式，否则未签名的扩展面板无法加载。
> 如果你有 Adobe 开发者证书并签名了扩展，可以跳过此步骤。

#### 6.4.3 验证 Bridge 面板安装

1. **启动 After Effects 2025**
2. **打开扩展面板**：菜单栏 → 窗口 → 扩展 → AE MCP Bridge
3. **确认面板打开**：应该能看到 MCP Bridge 的界面

> [!tip] 面板没看到？
> - 确认已启用 PlayerDebugMode
> - 确认扩展文件复制到了正确的目录
> - 重启 After Effects
> - 查看 AE 脚本调试控制台（帮助 → 脚本调试）

### 6.5 MCP 配置文件设置

#### 6.5.1 .mcp.json 配置

MCP 配置文件告诉 AI 助手如何连接到 MCP Server。

**Trae / Claude Desktop 配置**：

```powershell
# 配置文件位置（Trae）
# %APPDATA%\Trae\mcp.json
# 或者用户目录下的 .mcp.json

# 配置文件内容示例：
$mcpConfig = @'
{
  "mcpServers": {
    "after-effects": {
      "command": "node",
      "args": [
        "C:\\Projects\\after-effects-mcp\\build\\index.js"
      ],
      "env": {
        "AE_COMMAND_FILE": "C:\\Temp\\ae_command.json",
        "AE_RESULT_FILE": "C:\\Temp\\ae_mcp_result.json"
      }
    }
  }
}
'@

# 写入配置文件
$mcpConfigPath = "$env:USERPROFILE\.mcp.json"
$mcpConfig | Out-File -FilePath $mcpConfigPath -Encoding utf8
Write-Host "MCP config written to: $mcpConfigPath"
```

#### 6.5.2 命令文件与结果文件配置

MCP Server 和 AE Bridge 通过**命令文件**和**结果文件**通信：

| 文件 | 作用 | 默认位置 |
|------|------|---------|
| `ae_command.json` | MCP Server 写入命令，Bridge 读取 | 临时目录 |
| `ae_mcp_result.json` | Bridge 写入结果，MCP Server 读取 | 临时目录 |

**配置文件路径**：

```powershell
# 创建临时目录
New-Item -ItemType Directory -Path "C:\Temp" -Force

# 设置环境变量（推荐）
[Environment]::SetEnvironmentVariable("AE_COMMAND_FILE", "C:\Temp\ae_command.json", "User")
[Environment]::SetEnvironmentVariable("AE_RESULT_FILE", "C:\Temp\ae_mcp_result.json", "User")

# 或者在 .mcp.json 的 env 中设置
```

> [!warning] 路径必须一致
> MCP Server 和 AE Bridge 必须使用**相同的**命令文件和结果文件路径，否则无法通信。

#### 6.5.3 Trae MCP 配置

如果你使用 Trae IDE，配置方式如下：

1. **打开 Trae 设置**
2. **找到 MCP 配置**
3. **添加 after-effects MCP Server**：

```json
{
  "mcpServers": {
    "after-effects": {
      "command": "node",
      "args": ["C:\\Projects\\after-effects-mcp\\build\\index.js"],
      "env": {
        "AE_COMMAND_FILE": "C:\\Temp\\ae_command.json",
        "AE_RESULT_FILE": "C:\\Temp\\ae_mcp_result.json"
      }
    }
  }
}
```

4. **保存配置并重启 Trae**

### 6.6 AE 2025 中的 MCP Bridge 面板设置

#### 6.6.1 打开 Bridge 面板

1. 启动 **After Effects 2025**
2. 打开一个项目（或新建项目）
3. 菜单栏：**窗口 → 扩展 → AE MCP Bridge**
4. 面板应该会弹出

#### 6.6.2 面板配置

Bridge 面板通常有以下设置项：

| 设置项 | 说明 | 推荐值 |
|--------|------|--------|
| Command File | 命令文件路径 | `C:\Temp\ae_command.json` |
| Result File | 结果文件路径 | `C:\Temp\ae_mcp_result.json` |
| Poll Interval | 轮询间隔（毫秒） | `250` |
| Auto Start | 启动 AE 时自动连接 | 开启 |
| Debug Mode | 调试模式（显示日志） | 开发时开启 |

**配置步骤**：

1. 在 Bridge 面板中找到设置（齿轮图标）
2. 设置 Command File 为 `C:\Temp\ae_command.json`
3. 设置 Result File 为 `C:\Temp\ae_mcp_result.json`
4. 设置 Poll Interval 为 `250` ms
5. 点击「Connect」或「Start」按钮
6. 状态应该变为「Connected」或绿色

> [!tip] 连接不上？
> - 检查文件路径是否正确（正反斜杠）
> - 检查文件是否被占用
> - 以管理员身份运行 AE
> - 查看面板日志

#### 6.6.3 验证连接

**验证步骤**：

1. 确保 Bridge 面板显示「Connected」
2. 在 AI 助手中测试调用一个工具（如 `list-compositions`）
3. 观察 Bridge 面板是否显示收到的命令
4. 确认 AE 中有相应的操作

### 6.7 验证方法：创建测试合成

#### 6.7.1 测试工具调用

在 Trae 或其他 AI 助手中，尝试调用 MCP 工具：

**示例：创建测试合成**

```
请帮我用 after-effects MCP 创建一个测试合成：
- 名称：Deployment Test
- 分辨率：1920x1080
- 时长：5秒
- 帧率：30fps
- 背景色：黑色
```

如果成功，你应该看到：
- Bridge 面板收到了命令
- AE 中创建了名为「Deployment Test」的合成
- AI 助手收到了成功的响应

#### 6.7.2 完整验证脚本

```powershell
# 手动测试 MCP 通信（不通过 AI 助手）

# 1. 创建测试命令
$testCommand = @{
    script = "createComposition"
    params = @{
        name = "MCP Test Comp"
        width = 1920
        height = 1080
        frameRate = 30
        duration = 5
        bgColor = @(0, 0, 0)
    }
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
} | ConvertTo-Json -Depth 10

# 2. 写入命令文件
$commandFile = "C:\Temp\ae_command.json"
$testCommand | Out-File -FilePath $commandFile -Encoding utf8
Write-Host "Command written to: $commandFile"
Write-Host "Waiting for AE Bridge to execute..."

# 3. 等待结果（轮询）
$resultFile = "C:\Temp\ae_mcp_result.json"
$timeout = 30  # 30秒超时
$elapsed = 0

while ($elapsed -lt $timeout) {
    if (Test-Path $resultFile) {
        $result = Get-Content $resultFile -Raw -Encoding utf8 | ConvertFrom-Json
        Write-Host "`nResult received:" -ForegroundColor Green
        Write-Host $result
        break
    }
    Start-Sleep -Seconds 1
    $elapsed++
    Write-Host "Waiting... ${elapsed}s" -NoNewline -ForegroundColor Gray
}

if ($elapsed -ge $timeout) {
    Write-Host "`nTimeout! No result received." -ForegroundColor Red
    Write-Host "Check if AE Bridge is running and connected." -ForegroundColor Yellow
}
```

> [!success] 验证标准
> - 命令文件写入后，AE Bridge 在 1 秒内读取并执行
> - 结果文件在 5 秒内生成
> - AE 中创建了对应合成
> - 返回结果中 `success` 为 `true`

> [!info] 参考文档
> MCP 工具详细说明参见 [[07-MCP参考指南/🔗-MCP参考指南-MOC|MCP参考指南]]

---

## 第7章 MCP 扩展工具安装

### 7.1 扩展工具概述

#### 7.1.1 为什么需要扩展工具

基础的 22 个 MCP 工具只能满足简单的 AE 操作需求。对于复杂的视频生成流水线，需要更多专用工具：

| 类别 | 基础工具 | 扩展工具 |
|------|---------|---------|
| 效果操作 | 基础效果添加 | 批量添加、关键帧曲线、属性查询 |
| 图层操作 | 基础图层创建 | 混合模式、轨道蒙版、父子关系、运动模糊 |
| 合成操作 | 创建合成 | 调整层、预合成、遮罩 |
| 素材操作 | 无 | 导入素材 |
| 高级功能 | 无 | 原子脚本执行、批量操作 |

#### 7.1.2 14个扩展工具清单

Phase 2 扩展共添加 **14 个新 MCP 工具**：

| # | 工具名称 | JSX 脚本 | 功能说明 |
|---|---------|----------|---------|
| 1 | add-effect-with-keyframes | addEffectWithKeyframes.jsx | 添加带有关键帧的效果 |
| 2 | set-keyframe-easing | setKeyframeEasing.jsx | 设置关键帧缓动曲线 |
| 3 | batch-add-effects | batchAddEffects.jsx | 批量添加多个效果 |
| 4 | set-blend-mode | setBlendMode.jsx | 设置图层混合模式 |
| 5 | set-track-matte | setTrackMatte.jsx | 设置轨道蒙版 |
| 6 | set-parent-layer | setParentLayer.jsx | 设置父子图层关系 |
| 7 | add-adjustment-layer | addAdjustmentLayer.jsx | 添加调整图层 |
| 8 | add-precomp | addPrecomp.jsx | 创建预合成 |
| 9 | import-footage | importFootage.jsx | 导入素材到项目 |
| 10 | set-motion-blur | setMotionBlur.jsx | 设置运动模糊 |
| 11 | add-mask-with-shape | addMaskWithShape.jsx | 添加形状遮罩 |
| 12 | execute-atom-script | executeAtomScript.jsx | 执行原子脚本 |
| 13 | get-effect-properties | getEffectProperties.jsx | 获取效果属性列表 |
| 14 | set-effect-keyframes | setEffectKeyframes.jsx | 设置效果关键帧 |

### 7.2 JSX 脚本复制到 AE 脚本目录

#### 7.2.1 获取扩展工具代码

扩展工具代码位于知识库的 `mcp-extension` 目录：

```powershell
# 扩展工具源目录
$extensionDir = "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-extension"

# 验证源文件存在
if (Test-Path $extensionDir) {
    Write-Host "Extension directory found: $extensionDir"
    Get-ChildItem $extensionDir
} else {
    Write-Error "Extension directory not found: $extensionDir"
}
```

#### 7.2.2 复制 JSX 脚本到 MCP 项目

```powershell
# MCP 项目的脚本目录
$mcpProjectDir = "C:\Projects\after-effects-mcp"
$scriptsSourceDir = Join-Path $extensionDir "scripts"
$scriptsTargetDir = Join-Path $mcpProjectDir "src\scripts"

# 验证目标目录
if (-not (Test-Path $scriptsTargetDir)) {
    Write-Error "Target scripts directory not found: $scriptsTargetDir"
    exit 1
}

# 14 个新 JSX 脚本列表
$newScripts = @(
    "addEffectWithKeyframes.jsx",
    "setKeyframeEasing.jsx",
    "batchAddEffects.jsx",
    "setBlendMode.jsx",
    "setTrackMatte.jsx",
    "setParentLayer.jsx",
    "addAdjustmentLayer.jsx",
    "addPrecomp.jsx",
    "importFootage.jsx",
    "setMotionBlur.jsx",
    "addMaskWithShape.jsx",
    "executeAtomScript.jsx",
    "getEffectProperties.jsx",
    "setEffectKeyframes.jsx"
)

# 复制脚本
$copiedCount = 0
foreach ($script in $newScripts) {
    $srcPath = Join-Path $scriptsSourceDir $script
    $dstPath = Join-Path $scriptsTargetDir $script

    if (Test-Path $srcPath) {
        Copy-Item $srcPath $dstPath -Force
        $copiedCount++
        Write-Host "  [OK] Copied: $script" -ForegroundColor Green
    } else {
        Write-Host "  [X] Source not found: $script" -ForegroundColor Red
    }
}

Write-Host "`nTotal copied: $copiedCount / $($newScripts.Count) scripts"
```

> [!success] 验证标准
> 14 个 JSX 脚本全部成功复制到 `src/scripts/` 目录。

### 7.3 MCP server 配置更新

#### 7.3.1 修改 allowedScripts 白名单

MCP Server 有一个安全机制：只允许执行白名单中的脚本。需要把 14 个新脚本添加到白名单。

**手动修改方式**：

```powershell
# index.ts 路径
$indexTsPath = Join-Path $mcpProjectDir "src\index.ts"

# 读取文件
$indexContent = Get-Content $indexTsPath -Raw -Encoding UTF8

# 检查是否已经添加过
if ($indexContent -match "addEffectWithKeyframes") {
    Write-Host "Phase 2 entries already exist in allowedScripts" -ForegroundColor Yellow
} else {
    Write-Host "Adding 14 entries to allowedScripts array..."
    
    # 找到 "fixParticular" 条目，在它后面插入新条目
    # （实际位置取决于你的代码结构，这里只是示例）
    
    $newAllowedScripts = @'
      "addEffectWithKeyframes",
      "setKeyframeEasing",
      "batchAddEffects",
      "setBlendMode",
      "setTrackMatte",
      "setParentLayer",
      "addAdjustmentLayer",
      "addPrecomp",
      "importFootage",
      "setMotionBlur",
      "addMaskWithShape",
      "executeAtomScript",
      "getEffectProperties",
      "setEffectKeyframes"
'@

    Write-Host "Please manually add these entries to the allowedScripts array in index.ts"
    Write-Host $newAllowedScripts
}
```

#### 7.3.2 添加工具注册代码

除了白名单，还需要在 `index.ts` 中注册这 14 个新工具。

**工具注册代码结构**：

每个 MCP 工具的注册都需要：
1. 工具名称和描述
2. 参数 Schema（JSON Schema 格式）
3. 处理函数（读取参数 → 调用 JSX → 返回结果）

**使用提供的 new-tools-inline.ts**：

```powershell
# 新工具注册代码文件
$inlineToolsPath = Join-Path $extensionDir "new-tools-inline.ts"

if (Test-Path $inlineToolsPath) {
    Write-Host "Tool registration code found: $inlineToolsPath"
    
    # 将工具注册代码追加到 index.ts 末尾
    $inlineContent = Get-Content $inlineToolsPath -Raw -Encoding UTF8
    
    # 检查是否已添加
    if ($indexContent -match 'execute-atom-script') {
        Write-Host "Tool registrations already exist, skipping" -ForegroundColor Yellow
    } else {
        # 追加到文件末尾
        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $insertBlock = @"

// ============================================================================
// Phase 2 Extension - 14 new MCP tool registrations
// Deployed: $timestamp
// ============================================================================

$inlineContent
"@
        # 追加到文件（需要手动确认后执行）
        # Add-Content -Path $indexTsPath -Value $insertBlock -Encoding UTF8
        Write-Host "Tool registration code ready to be added to index.ts"
        Write-Host "Use the install.ps1 script for automated deployment"
    }
}
```

#### 7.3.3 使用 install.ps1 自动部署（推荐）

为了简化部署，我们提供了自动化安装脚本：

```powershell
# 进入扩展工具目录
cd "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-extension"

# 先预览一下要做什么（Dry Run）
.\install.ps1 -DryRun

# 如果没问题，执行正式安装
.\install.ps1 -Force
```

> [!tip] install.ps1 功能
> - 自动备份原始 index.ts
> - 复制 14 个 JSX 脚本
> - 修改 allowedScripts 白名单
> - 追加 14 个工具注册代码
> - 自动运行 `npm run build` 验证编译
> - 提供回滚方案

### 7.4 重新构建 MCP Server

修改完代码后，需要重新构建：

```powershell
# 进入 MCP 项目目录
cd C:\Projects\after-effects-mcp

# 重新构建
npm run build

# 验证构建成功
if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful! ✅" -ForegroundColor Green
} else {
    Write-Host "Build failed! ❌" -ForegroundColor Red
    exit 1
}
```

> [!warning] 构建失败怎么办？
> 1. 检查 TypeScript 语法错误
> 2. 恢复备份：`Copy-Item src\index.ts.backup-phase2 src\index.ts -Force`
> 3. 重新构建确认基础版本没问题
> 4. 逐步添加代码排查问题

### 7.5 工具验证清单

#### 7.5.1 每个工具的测试命令

部署完成后，逐个测试 14 个扩展工具：

| # | 工具名称 | 测试命令 | 预期结果 |
|---|---------|---------|---------|
| 1 | add-effect-with-keyframes | 给图层添加带关键帧的高斯模糊 | 效果添加，关键帧存在 |
| 2 | set-keyframe-easing | 设置关键帧为 Easy Ease | 关键帧缓动改变 |
| 3 | batch-add-effects | 一次添加 3 个效果 | 3 个效果都被添加 |
| 4 | set-blend-mode | 设置图层为 Screen 模式 | 混合模式改变 |
| 5 | set-track-matte | 设置 Alpha 轨道蒙版 | 蒙版生效 |
| 6 | set-parent-layer | 设置图层父子关系 | 子图层跟随父图层 |
| 7 | add-adjustment-layer | 添加调整图层 | 调整层出现在时间轴 |
| 8 | add-precomp | 选中图层预合成 | 预合成创建成功 |
| 9 | import-footage | 导入图片素材 | 素材出现在项目面板 |
| 10 | set-motion-blur | 开启运动模糊 | 运动模糊开启 |
| 11 | add-mask-with-shape | 添加圆形遮罩 | 遮罩出现 |
| 12 | execute-atom-script | 执行简单原子脚本 | 脚本执行成功 |
| 13 | get-effect-properties | 获取效果属性列表 | 返回属性数组 |
| 14 | set-effect-keyframes | 设置效果属性关键帧 | 关键帧设置成功 |

#### 7.5.2 快速验证脚本

```powershell
# 快速验证：列出所有可用的 MCP 工具
# 需要先安装 mcp-inspector 或使用 AI 助手

# 或者直接检查构建输出中的工具数量
$buildFile = "C:\Projects\after-effects-mcp\build\index.js"
if (Test-Path $buildFile) {
    $toolCount = (Select-String -Path $buildFile -Pattern "name:\s*`"[\w-]+`"" | Measure-Object).Count
    Write-Host "Approximate tool count in build: $toolCount"
    Write-Host "Expected: ~36 tools (22 base + 14 extension)"
}
```

#### 7.5.3 在 AI 助手中验证

在 Trae 或 Claude 中，可以这样测试：

```
请列出 after-effects MCP 的所有可用工具，看看有没有 36 个以上
```

或者直接测试一个扩展工具：

```
请用 add-adjustment-layer 工具在当前合成中添加一个调整图层，命名为 "Color Grade"
```

### 7.6 常见问题

#### 7.6.1 权限问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 拒绝访问路径 | 权限不足 | 以管理员身份运行 PowerShell / AE |
| 文件被占用 | 文件正在使用 | 关闭 AE 和 MCP Server 后再操作 |
| 无法写入注册表 | 权限不足 | 以管理员身份运行脚本 |

#### 7.6.2 路径问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 找不到脚本文件 | 路径错误 | 检查路径中的正反斜杠 |
| 命令文件不生效 | 路径不一致 | 确保 MCP Server 和 Bridge 用同一路径 |
| 相对路径不工作 | 工作目录不同 | 使用绝对路径 |

> [!tip] Windows 路径小技巧
> - PowerShell 中路径用正斜杠或双反斜杠
> - JSON 配置中用双反斜杠 `\\`
> - 推荐所有路径都用**绝对路径**

#### 7.6.3 AE 版本兼容

| AE 版本 | 兼容性 | 备注 |
|---------|--------|------|
| AE 2025 (25.x) | ✅ 完全兼容 | 推荐版本 |
| AE 2024 (24.x) | ✅ 兼容 | 功能完整 |
| AE 2023 (23.x) | ⚠️ 基本兼容 | 部分新效果可能不可用 |
| AE 2022 (22.x) | ⚠️ 部分兼容 | 可能缺少某些 API |
| AE 2021 及更早 | ❌ 不推荐 | 太老旧，API 差异大 |

> [!warning] 注意
> 扩展工具中使用的某些 ExtendScript API 可能在旧版 AE 中不可用。
> 如果使用旧版 AE，遇到问题请升级到 2025 版本。

#### 7.6.4 工具调用失败排查

```
工具调用失败排查步骤：

1. 检查 Bridge 面板状态
   → 是否 Connected？
   → 是否有错误日志？

2. 检查命令文件
   → ae_command.json 是否生成？
   → 文件内容格式是否正确？

3. 检查 JSX 脚本
   → 脚本文件是否存在？
   → 脚本语法是否正确？
   → 在 AE 中手动运行脚本试试

4. 检查结果文件
   → ae_mcp_result.json 是否生成？
   → 里面有什么错误信息？

5. 检查 MCP Server
   → Server 是否正常运行？
   → 控制台有什么报错？
```

> [!info] 参考文档
> 更多 MCP 工具参考参见 [[07-MCP参考指南/🔗-MCP参考指南-MOC|MCP参考指南]]
> 效果操作规范参见 [[MCP→AE效果操作桥接规范]]

---

## 第8章 Python-TS 桥接配置

### 8.1 桥接层概述

#### 8.1.1 为什么需要桥接

Python 擅长数据分析、AI 算法（音乐分析、视频分析、音画匹配），TypeScript 擅长工程化、MCP 集成、编译器。两者结合才能发挥最大效能。

**两种桥接模式**：

| 模式 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **Subprocess** | TS 调用 Python 子进程，通过 stdio 通信 | 简单、无需额外端口 | 每次调用启动开销大 | 新手、简单调用 |
| **FastAPI** | Python 启动 HTTP 服务，TS 通过 API 调用 | 高性能、状态保持 | 需要管理服务进程 | 生产环境、高频调用 |

> [!success] 推荐方案
> - 新手入门：先用 **Subprocess 模式**
> - 生产部署：升级到 **FastAPI 模式**

#### 8.1.2 桥接层架构

```
┌─────────────────────┐         ┌─────────────────────┐
│   TypeScript 端      │         │     Python 端       │
│                     │         │                     │
│  ┌───────────────┐  │         │  ┌───────────────┐  │
│  │   Bridge      │  │  JSON   │  │   Bridge      │  │
│  │   Client      │──┼─────────┼─►│   Server      │  │
│  └───────────────┘  │         │  └───────────────┘  │
│         │           │         │         │           │
│         ▼           │         │         ▼           │
│  ┌───────────────┐  │         │  ┌───────────────┐  │
│  │  autoEdit     │  │         │  │  音乐分析      │  │
│  │  入口函数      │  │         │  │  片段分析      │  │
│  │               │  │         │  │  音画匹配      │  │
│  └───────────────┘  │         │  │  参数反推      │  │
└─────────────────────┘         │  └───────────────┘  │
                                └─────────────────────┘
```

### 8.2 Subprocess 模式配置（最简单，推荐新手）

#### 8.2.1 工作原理

Subprocess 模式下，每次调用 Python 功能时：
1. TypeScript 启动一个 Python 子进程
2. 通过 stdin 传入 JSON 参数
3. Python 执行计算
4. 通过 stdout 返回 JSON 结果
5. 子进程退出

#### 8.2.2 Python 端脚本

创建 Python 分析服务的入口脚本：

```powershell
# 创建 Python 服务目录
$pythonServerDir = "C:\Projects\AE-MotionStudio\python-server"
New-Item -ItemType Directory -Path $pythonServerDir -Force

# 创建 main.py（子进程模式入口）
$mainPy = @'
#!/usr/bin/env python3
"""
Python Analysis Server - Subprocess Mode
通过 stdin/stdout 与 TypeScript 通信
"""
import sys
import json
import traceback

def analyze_music(music_path: str) -> dict:
    """音乐分析入口"""
    try:
        import librosa
        import numpy as np
        
        y, sr = librosa.load(music_path, sr=44100, mono=False)
        if y.ndim > 1:
            y_mono = librosa.to_mono(y)
        else:
            y_mono = y
        
        duration = librosa.get_duration(y=y_mono, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(y=y_mono, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        
        return {
            "success": True,
            "duration": duration,
            "bpm": float(tempo),
            "beat_count": len(beat_times),
            "beat_times": beat_times[:10],  # 返回前10个做示例
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_clip(clip_path: str) -> dict:
    """片段分析入口"""
    try:
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return {"success": False, "error": "Cannot open video"}
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return {
            "success": True,
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration": duration,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def match_audio_visual(music_data: dict, clip_data: list, style: str) -> dict:
    """音画匹配入口"""
    try:
        return {
            "success": True,
            "style": style,
            "matched_pairs": len(clip_data),
            "message": "Matching completed (demo mode)",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

HANDLERS = {
    "analyze_music": analyze_music,
    "analyze_clip": analyze_clip,
    "match_audio_visual": match_audio_visual,
}

def main():
    try:
        input_data = json.loads(sys.stdin.read())
        action = input_data.get("action")
        params = input_data.get("params", {})
        
        if action not in HANDLERS:
            result = {"success": False, "error": f"Unknown action: {action}"}
        else:
            result = HANDLERS[action](**params)
        
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
'@

$mainPy | Out-File -FilePath (Join-Path $pythonServerDir "main.py") -Encoding utf8
Write-Host "main.py created"
```

#### 8.2.3 TypeScript 端桥接客户端

```typescript
// bridge-client.ts - Subprocess 模式客户端
import { spawn } from 'child_process';
import * as path from 'path';

export interface BridgeRequest {
  action: string;
  params: Record<string, any>;
}

export interface BridgeResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

export class PythonBridgeClient {
  private pythonPath: string;
  private scriptPath: string;

  constructor(
    pythonPath: string = 'python',
    scriptPath: string = 'C:/Projects/AE-MotionStudio/python-server/main.py'
  ) {
    this.pythonPath = pythonPath;
    this.scriptPath = scriptPath;
  }

  async call<T = any>(request: BridgeRequest): Promise<BridgeResponse<T>> {
    return new Promise((resolve, reject) => {
      const pythonProcess = spawn(this.pythonPath, [this.scriptPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Python process exited with code ${code}: ${stderr}`));
          return;
        }

        try {
          const result = JSON.parse(stdout) as BridgeResponse<T>;
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse Python output: ${stdout}`));
        }
      });

      pythonProcess.stdin.write(JSON.stringify(request));
      pythonProcess.stdin.end();
    });
  }

  async analyzeMusic(musicPath: string) {
    return this.call({
      action: 'analyze_music',
      params: { music_path: musicPath },
    });
  }

  async analyzeClip(clipPath: string) {
    return this.call({
      action: 'analyze_clip',
      params: { clip_path: clipPath },
    });
  }
}
```

#### 8.2.4 验证 Subprocess 模式

```powershell
# 激活 Python 环境
conda activate ae-ai

# 测试 Python 脚本
cd C:\Projects\AE-MotionStudio\python-server

# 创建测试输入
$testInput = @'
{
  "action": "analyze_clip",
  "params": {
    "clip_path": "C:/Temp/ffmpeg-test/test_video.mp4"
  }
}
'@

# 通过管道调用
$testInput | python main.py
```

> [!success] 验证标准
> Python 脚本返回 JSON 格式的结果，包含 `success: true` 和分析数据。


#### 8.2.4 Subprocess 模式测试与验证

完成 Python 和 TypeScript 两端的代码后，进行测试验证：

```powershell
# 1. 先直接测试 Python 脚本
conda activate ae-ai
cd C:\Projects\AE-MotionStudio\python-server

# 创建测试输入
$testInput = @'
{
  "action": "analyze_music",
  "params": {
    "music_path": "C:/Test/test_music.mp3"
  }
}
'@

# 通过管道传入
$testInput | python main.py
```

> [!note] 预期输出
> 如果音乐文件存在，应该返回包含 duration、bpm、beat_count 等字段的 JSON。
> 如果文件不存在，会返回 success: false 和错误信息。

**TypeScript 端测试**：

```typescript
// test-bridge.ts - 测试 Subprocess 桥接
import { PythonBridgeClient } from './bridge-client';

async function testBridge() {
  const client = new PythonBridgeClient(
    'C:/Users/Administrator/miniconda3/envs/ae-ai/python.exe',
    'C:/Projects/AE-MotionStudio/python-server/main.py'
  );

  console.log('Testing analyze_clip...');
  const clipResult = await client.call('analyze_clip', {
    clip_path: 'C:/Test/test_clip.mp4'
  });
  console.log('Clip result:', JSON.stringify(clipResult, null, 2));

  console.log('\nTesting match_audio_visual...');
  const matchResult = await client.call('match_audio_visual', {
    music_data: { bpm: 120, duration: 180 },
    clip_data: [{ duration: 10 }, { duration: 15 }],
    style: 'cinematic'
  });
  console.log('Match result:', JSON.stringify(matchResult, null, 2));
}

testBridge().catch(console.error);
```

```powershell
# 编译并运行测试
cd C:\Projects\AE-MotionStudio\compiler
npx ts-node test-bridge.ts
```

#### 8.2.5 Subprocess 模式性能优化

虽然 Subprocess 模式简单，但每次调用都要启动 Python 进程，有一定开销。以下是一些优化技巧：

**批量调用**：尽量将多个小操作合并为一次调用：

```typescript
// 不好的方式：多次调用
const music = await client.call('analyze_music', { path: musicPath });
const clips = await Promise.all(
  clipPaths.map(p => client.call('analyze_clip', { clip_path: p }))
);

// 好的方式：批量调用
const batchResult = await client.call('batch_analyze', {
  music_path: musicPath,
  clip_paths: clipPaths
});
```

**预热机制**：在应用启动时先发起一次空调用，让 Python 进程提前加载库：

```typescript
async function warmup() {
  console.log('Warming up Python bridge...');
  try {
    await client.call('ping', {});
  } catch (e) {
    // 忽略预热错误
  }
  console.log('Python bridge warmup complete');
}

// 应用启动时调用
warmup();
```

> [!tip] 优化效果
> - 单次调用开销：约 500-2000ms（主要是 Python 启动和库加载）
> - 批量调用：开销摊薄到每个操作上
> - 如果需要高频调用（>1次/秒），建议升级到 FastAPI 模式

### 8.3 FastAPI 模式配置（高性能模式）

#### 8.3.1 工作原理

FastAPI 模式下，Python 作为 HTTP 服务常驻后台：
1. Python 启动 FastAPI 服务，监听某个端口（如 8000）
2. TypeScript 通过 HTTP 请求调用 API
3. Python 保持状态（模型加载到内存），响应更快
4. 支持并发请求

#### 8.3.2 安装 FastAPI 依赖

```powershell
# 激活 ae-ai 环境
conda activate ae-ai

# 安装 FastAPI + Uvicorn
pip install fastapi==0.109.2 uvicorn==0.27.1

# 验证
python -c "import fastapi; import uvicorn; print(f'FastAPI: {fastapi.__version__}'); print(f'Uvicorn: {uvicorn.__version__}')"
```

#### 8.3.3 创建 FastAPI 服务

```powershell
# 在 python-server 目录下创建 server.py
$serverPy = @'
#!/usr/bin/env python3
"""
Python Analysis Server - FastAPI Mode
高性能 HTTP API 服务
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(
    title="AI Video Analysis API",
    description="AI 辅助视频生成 - Python 分析服务",
    version="1.0.0",
)

# Pydantic 模型定义
class MusicAnalysisRequest(BaseModel):
    music_path: str

class ClipAnalysisRequest(BaseModel):
    clip_path: str

class MatchRequest(BaseModel):
    music_data: dict
    clip_data: List[dict]
    style: str = "cinematic"

class HealthResponse(BaseModel):
    status: str
    version: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/analyze/music")
async def analyze_music(request: MusicAnalysisRequest):
    """分析音乐"""
    try:
        import librosa
        import numpy as np
        
        y, sr = librosa.load(request.music_path, sr=44100, mono=False)
        if y.ndim > 1:
            y_mono = librosa.to_mono(y)
        else:
            y_mono = y
        
        duration = librosa.get_duration(y=y_mono, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(y=y_mono, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        
        return {
            "success": True,
            "duration": duration,
            "bpm": float(tempo),
            "beat_count": len(beat_times),
            "beat_times": beat_times,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/clip")
async def analyze_clip(request: ClipAnalysisRequest):
    """分析视频片段"""
    try:
        import cv2
        
        cap = cv2.VideoCapture(request.clip_path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Cannot open video file")
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return {
            "success": True,
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration": duration,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/match")
async def match_audio_visual(request: MatchRequest):
    """音画匹配"""
    try:
        return {
            "success": True,
            "style": request.style,
            "matched_pairs": len(request.clip_data),
            "message": "Matching completed",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
'@

$serverPy | Out-File -FilePath (Join-Path $pythonServerDir "server.py") -Encoding utf8
Write-Host "server.py created"
```

#### 8.3.4 启动 FastAPI 服务

```powershell
# 激活环境
conda activate ae-ai

# 进入服务目录
cd C:\Projects\AE-MotionStudio\python-server

# 启动服务（开发模式，带热重载）
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload

# 或者生产模式
# python -m uvicorn server:app --host 127.0.0.1 --port 8000 --workers 4
```

> [!warning] 注意
> 这是前台运行，关闭 PowerShell 窗口服务会停止。
> 如需后台运行，请看下一节的 Windows 服务注册。

#### 8.3.5 Windows 服务注册（NSSM）

使用 NSSM（Non-Sucking Service Manager）将 FastAPI 注册为 Windows 服务，开机自动启动。

**步骤 1：安装 NSSM**

```powershell
# 使用 Chocolatey 安装
choco install nssm -y

# 验证
nssm version
```

**步骤 2：注册服务**

```powershell
# 服务名称
$serviceName = "AE-AI-Analysis-Server"

# Python 路径（conda 环境中的 python.exe）
$pythonPath = "C:\Tools\Miniconda3\envs\ae-ai\python.exe"

# 工作目录
$workDir = "C:\Projects\AE-MotionStudio\python-server"

# 参数
$arguments = "-m uvicorn server:app --host 127.0.0.1 --port 8000"

# 注册服务
nssm install $serviceName $pythonPath $arguments
nssm set $serviceName AppDirectory $workDir
nssm set $serviceName DisplayName "AE AI Analysis Server"
nssm set $serviceName Description "AI-assisted video generation Python analysis service"

# 启动服务
nssm start $serviceName

# 查看服务状态
nssm status $serviceName
```

> [!tip] NSSM 常用命令
> ```powershell
> nssm start <服务名>    # 启动服务
> nssm stop <服务名>     # 停止服务
> nssm restart <服务名>  # 重启服务
> nssm remove <服务名>   # 删除服务
> nssm edit <服务名>     # 编辑服务配置（GUI）
> ```

#### 8.3.6 端口与防火墙配置

```powershell
# 检查端口是否被占用
netstat -ano | findstr :8000

# 如果被占用，换一个端口（如 8001）

# Windows 防火墙配置（仅本机访问不需要）
# 如果需要从其他机器访问，开放端口：
New-NetFirewallRule -DisplayName "AE AI Analysis Server" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

> [!warning] 安全提醒
> - FastAPI 默认监听 `127.0.0.1`，仅本机可访问，这是安全的
> - 如需从其他机器访问，建议配置身份验证
> - 不要直接暴露到公网

### 8.4 接口测试方法

#### 8.4.1 用 curl 测试

```powershell
# 健康检查
curl http://127.0.0.1:8000/health

# 音乐分析测试
curl -Method Post -Uri "http://127.0.0.1:8000/analyze/music" `
  -ContentType "application/json" `
  -Body '{"music_path": "C:/Temp/test_audio.mp3"}'

# 片段分析测试
curl -Method Post -Uri "http://127.0.0.1:8000/analyze/clip" `
  -ContentType "application/json" `
  -Body '{"clip_path": "C:/Temp/ffmpeg-test/test_video.mp4"}'
```

#### 8.4.2 用 PowerShell 测试

```powershell
# 健康检查
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get

# 音乐分析
$body = @{
    music_path = "C:/Temp/ffmpeg-test/test_audio.mp3"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze/music" -Method Post -Body $body -ContentType "application/json"
```

#### 8.4.3 用 Postman 测试（可选）

1. 下载安装 Postman
2. 创建新的 Collection
3. 添加请求：
   - GET `http://127.0.0.1:8000/health`
   - POST `http://127.0.0.1:8000/analyze/music`
4. 发送请求，查看响应

#### 8.4.4 TypeScript HTTP 客户端

```typescript
// bridge-http-client.ts - FastAPI 模式客户端
import axios from 'axios';

export class PythonBridgeHttpClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl;
  }

  async healthCheck() {
    const res = await axios.get(`${this.baseUrl}/health`);
    return res.data;
  }

  async analyzeMusic(musicPath: string) {
    const res = await axios.post(`${this.baseUrl}/analyze/music`, {
      music_path: musicPath,
    });
    return res.data;
  }

  async analyzeClip(clipPath: string) {
    const res = await axios.post(`${this.baseUrl}/analyze/clip`, {
      clip_path: clipPath,
    });
    return res.data;
  }

  async matchAudioVisual(musicData: any, clipData: any[], style: string) {
    const res = await axios.post(`${this.baseUrl}/match`, {
      music_data: musicData,
      clip_data: clipData,
      style,
    });
    return res.data;
  }
}
```

### 8.5 性能基准测试

#### 8.5.1 Subprocess vs FastAPI 性能对比

```powershell
# 简单性能测试
$testCount = 10

Write-Host "=== Subprocess Mode Performance ==="
$subprocessTimes = @()
for ($i = 0; $i -lt $testCount; $i++) {
    $time = Measure-Command {
        $testInput | python main.py | Out-Null
    }
    $subprocessTimes += $time.TotalMilliseconds
    Write-Host "  Request $($i+1): $($time.TotalMilliseconds)ms"
}
$subprocessAvg = ($subprocessTimes | Measure-Object -Average).Average
Write-Host "Average: $subprocessAvg ms"

Write-Host "`n=== FastAPI Mode Performance ==="
$fastapiTimes = @()
for ($i = 0; $i -lt $testCount; $i++) {
    $time = Measure-Command {
        Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get | Out-Null
    }
    $fastapiTimes += $time.TotalMilliseconds
    Write-Host "  Request $($i+1): $($time.TotalMilliseconds)ms"
}
$fastapiAvg = ($fastapiTimes | Measure-Object -Average).Average
Write-Host "Average: $fastapiAvg ms"

Write-Host "`n=== Comparison ==="
Write-Host "Subprocess avg: $subprocessAvg ms"
Write-Host "FastAPI avg:    $fastapiAvg ms"
$speedup = $subprocessAvg / $fastapiAvg
Write-Host "Speedup:        $([math]::Round($speedup, 1))x"
```

> [!note] 预期结果
> - Subprocess 模式：每次调用 500-2000ms（主要是 Python 启动开销）
> - FastAPI 模式：每次调用 10-100ms（服务已启动，模型已加载）
> - FastAPI 通常快 10-50 倍

> [!info] 参考文档
> 桥接架构详情参见 [[音画匹配引擎与系统桥接工程手册]]

---

## 第9章 端到端流水线部署

### 9.1 autoEdit 入口配置

#### 9.1.1 什么是 autoEdit

`autoEdit` 是端到端流水线的**主入口函数**，整合了从音乐分析到 AE 生成的完整流程。调用一次 `autoEdit`，系统会自动完成：

1. 音乐分析
2. 片段分析
3. 音画匹配
4. 参数反推
5. 编译器生成 JSX
6. 通过 MCP 在 AE 中执行

> [!info] 参考文档
> autoEdit 设计参见 [[AI辅助视频生成一体化工作流总览]] | [[音画匹配引擎与系统桥接工程手册]]

#### 9.1.2 autoEdit 接口定义

```typescript
// autoEdit.ts - 端到端入口

export interface AutoEditRequest {
  musicFile: string;
  clipFiles: string[];
  targetStyle: string;
  targetDuration?: number;
  targetResolution?: [number, number];
  targetFrameRate?: number;
  outputPath: string;
  preferences?: {
    cutDensity?: number;
    effectIntensity?: number;
    includeSoundDesign?: boolean;
  };
}

export interface AutoEditResult {
  outputVideo: string;
  aeProject: string;
  musicAtom: any;
  clipAtoms: any[];
  matchPlan: any;
  compilerInput: any;
  qualityReport: any;
  timing: Record<string, number>;
}

export async function autoEdit(request: AutoEditRequest): Promise<AutoEditResult> {
  const timing: Record<string, number> = {};
  const t0 = Date.now();

  // Stage 1: 音乐分析
  const t1 = Date.now();
  const musicAtom = await analyzeMusic(request.musicFile);
  timing.music_analysis = Date.now() - t1;

  // Stage 2: 片段分析
  const t2 = Date.now();
  const clipAtoms = await Promise.all(
    request.clipFiles.map(f => analyzeClip(f))
  );
  timing.clip_analysis = Date.now() - t2;

  // Stage 3: 音画匹配
  const t3 = Date.now();
  const matchPlan = await matchAudioVisual(musicAtom, clipAtoms, request.targetStyle);
  timing.matching = Date.now() - t3;

  // Stage 4: 参数反推
  const t4 = Date.now();
  const compilerInput = inferParameters(matchPlan, musicAtom, request.targetStyle);
  timing.inference = Date.now() - t4;

  // Stage 5: 编译 + AE 执行
  const t5 = Date.now();
  const aeResult = await executeInAE(compilerInput, request.outputPath);
  timing.ae_execution = Date.now() - t5;

  timing.total = Date.now() - t0;

  return {
    outputVideo: aeResult.outputVideo,
    aeProject: aeResult.projectFile,
    musicAtom,
    clipAtoms,
    matchPlan,
    compilerInput,
    qualityReport: {},
    timing,
  };
}
```

### 9.2 项目目录结构初始化

#### 9.2.1 标准项目目录结构

每个视频生成项目使用统一的目录结构：

```
Project-Name/
├── 01-策划/
│   └── 需求文档.md
├── 02-素材/
│   ├── 原始素材/
│   │   ├── music/
│   │   └── video/
│   ├── 剪辑素材/
│   └── 代理素材/
├── 03-工程/
│   ├── AE/
│   │   └── project_v1.aep
│   └── PR/
├── 04-渲染输出/
│   ├── 草稿/
│   ├── 送审版/
│   └── 最终版/
├── 05-音效/
│   ├── SFX/
│   └── Music/
├── 06-参考/
├── analysis/              # 分析中间产物
│   ├── music_atom.yaml
│   ├── clip_atoms/
│   ├── match_plan.yaml
│   └── compiler_input.json
├── cache/                 # 缓存
├── logs/                  # 日志
└── 99-归档/
```

#### 9.2.2 项目初始化脚本

```powershell
# 创建初始化脚本
$initScript = @'
#!/usr/bin/env python3
"""
项目初始化脚本
"""
import os
import sys
from datetime import datetime

def init_project(project_name: str, style: str = "cinematic", base_path: str = "C:/Workspace/AE-Projects") -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    project_dir = os.path.join(base_path, f"{date_str}-{project_name}")
    
    subdirs = [
        "01-策划",
        "02-素材/原始素材/music",
        "02-素材/原始素材/video",
        "02-素材/剪辑素材",
        "02-素材/代理素材",
        "03-工程/AE",
        "03-工程/PR",
        "04-渲染输出/草稿",
        "04-渲染输出/送审版",
        "04-渲染输出/最终版",
        "05-音效/SFX",
        "05-音效/Music",
        "06-参考",
        "analysis/clip_atoms",
        "cache",
        "logs",
        "99-归档"
    ]
    
    os.makedirs(project_dir, exist_ok=True)
    for subdir in subdirs:
        os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
    
    readme = f"""# {project_name} - 项目需求

**项目名称**：{project_name}
**开始日期**：{date_str}
**目标风格**：{style}
**目标时长**：待定
**交稿日期**：待定

## 需求描述

[在此填写项目需求]

## 素材清单

- 音乐：music/music_original.mp3
- 视频片段：
  - clip_001.mp4
  - clip_002.mp4

## 特殊要求

[在此填写特殊要求]
"""
    
    with open(os.path.join(project_dir, "01-策划/需求文档.md"), 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"Project created: {project_dir}")
    return project_dir

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python init_project.py <project_name> [style]")
        sys.exit(1)
    
    name = sys.argv[1]
    style = sys.argv[2] if len(sys.argv) > 2 else "cinematic"
    init_project(name, style)
'@

$scriptsDir = "C:\Projects\AE-MotionStudio\scripts"
New-Item -ItemType Directory -Path $scriptsDir -Force
$initScript | Out-File -FilePath (Join-Path $scriptsDir "init_project.py") -Encoding utf8
Write-Host "init_project.py created"
```

#### 9.2.3 测试项目初始化

```powershell
# 激活环境
conda activate ae-ai

# 运行初始化脚本
cd C:\Projects\AE-MotionStudio\scripts
python init_project.py "测试项目-卡点视频" cyberpunk

# 查看生成的目录结构
Get-ChildItem "C:\Workspace\AE-Projects" | Select-Object -First 5
```


#### 9.2.4 项目模板与脚手架

除了基础目录结构，还可以创建项目模板来加速新项目启动：

```powershell
# 创建模板目录
$templateDir = "C:\Projects\AE-MotionStudio\templates\default"
New-Item -ItemType Directory -Path $templateDir -Force

# 模板目录结构
$templateSubdirs = @(
  "01-策划",
  "02-素材/原始素材/music",
  "02-素材/原始素材/video",
  "02-素材/剪辑素材",
  "02-素材/代理素材",
  "03-工程/AE",
  "03-工程/PR",
  "04-渲染输出/草稿",
  "04-渲染输出/送审版",
  "04-渲染输出/最终版",
  "05-音效/SFX",
  "05-音效/Music",
  "06-参考",
  "analysis/clip_atoms",
  "cache",
  "logs",
  "99-归档"
)

foreach ($dir in $templateSubdirs) {
  New-Item -ItemType Directory -Path (Join-Path $templateDir $dir) -Force
}

Write-Host "Template created at: $templateDir"
```

**从模板创建新项目**：

```powershell
# 使用 Copy-Item 复制模板
function New-AEProject {
  param(
    [string]$Name,
    [string]$Style = "cinematic",
    [string]$BasePath = "C:\Workspace\AE-Projects",
    [string]$TemplatePath = "C:\Projects\AE-MotionStudio\templates\default"
  )
  
  $dateStr = Get-Date -Format "yyyy-MM-dd"
  $projectDir = Join-Path $BasePath "$dateStr-$Name"
  
  if (Test-Path $projectDir) {
    Write-Error "Project already exists: $projectDir"
    return
  }
  
  # 复制模板
  Copy-Item -Path $TemplatePath -Destination $projectDir -Recurse
  
  # 创建需求文档
  $readmePath = Join-Path $projectDir "01-策划\需求文档.md"
  $readmeContent = @"
# $Name - 项目需求

**项目名称**：$Name
**开始日期**：$dateStr
**目标风格**：$Style
**目标时长**：待定
**交稿日期**：待定

## 需求描述

[在此填写项目需求]

## 素材清单

- 音乐：music/music_original.mp3
- 视频片段：
  - clip_001.mp4
  - clip_002.mp4

## 特殊要求

[在此填写特殊要求]
"@
  Set-Content -Path $readmePath -Value $readmeContent -Encoding utf8
  
  Write-Host "Project created: $projectDir"
  return $projectDir
}

# 使用示例
New-AEProject -Name "测试项目" -Style "cyberpunk"
```

### 9.3 缓存目录设置

#### 9.3.1 缓存目录结构

```
C:\Cache\
├── pip-cache\              # pip 包缓存
├── npm-cache\              # npm 包缓存
├── torch-cache\            # PyTorch 模型缓存
├── huggingface-cache\      # HuggingFace 模型缓存
├── ae-analysis\            # AE 分析结果缓存
│   ├── music\              # 音乐分析缓存（按文件哈希）
│   ├── clips\              # 片段分析缓存
│   └── match\              # 匹配结果缓存
└── temp\                   # 临时文件
```

#### 9.3.2 配置缓存路径

```powershell
# 创建缓存目录
$cacheDirs = @(
    "C:\Cache\ae-analysis\music",
    "C:\Cache\ae-analysis\clips",
    "C:\Cache\ae-analysis\match",
    "C:\Cache\temp"
)

foreach ($dir in $cacheDirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# 设置环境变量
[Environment]::SetEnvironmentVariable("AE_CACHE_DIR", "C:\Cache\ae-analysis", "User")
[Environment]::SetEnvironmentVariable("AE_TEMP_DIR", "C:\Cache\temp", "User")

Write-Host "Cache directories created"
```

### 9.4 日志系统配置

#### 9.4.1 Python 日志配置

```python
# logging_config.py - 日志配置
import logging
import os
from datetime import datetime

def setup_logging(log_dir: str = "logs", level: int = logging.INFO):
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)
```

#### 9.4.2 TypeScript 日志配置

```typescript
// logger.ts
import * as fs from 'fs-extra';
import * as path from 'path';

export class Logger {
  private logDir: string;
  private logFile: string;

  constructor(logDir: string = 'logs') {
    this.logDir = logDir;
    fs.ensureDirSync(logDir);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    this.logFile = path.join(logDir, `run_${timestamp}.log`);
  }

  info(message: string, ...args: any[]) {
    const ts = new Date().toISOString();
    const line = `[${ts}] [INFO] ${message}`;
    console.log(line, ...args);
    fs.appendFileSync(this.logFile, line + '\n');
  }

  error(message: string, ...args: any[]) {
    const ts = new Date().toISOString();
    const line = `[${ts}] [ERROR] ${message}`;
    console.error(line, ...args);
    fs.appendFileSync(this.logFile, line + '\n');
  }

  warn(message: string, ...args: any[]) {
    const ts = new Date().toISOString();
    const line = `[${ts}] [WARN] ${message}`;
    console.warn(line, ...args);
    fs.appendFileSync(this.logFile, line + '\n');
  }
}
```

### 9.5 监控与告警（可选）

#### 9.5.1 简单监控脚本

```python
# monitor.py - 简单监控
import time
import psutil
import logging

logger = logging.getLogger(__name__)

def get_system_stats():
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("C:\\").percent,
    }

def monitor_loop(interval: int = 60):
    while True:
        stats = get_system_stats()
        logger.info(f"System stats: {stats}")
        
        if stats["cpu_percent"] > 90:
            logger.warning(f"High CPU usage: {stats['cpu_percent']}%")
        if stats["memory_percent"] > 90:
            logger.warning(f"High memory usage: {stats['memory_percent']}%")
        
        time.sleep(interval)
```

### 9.6 端到端测试

#### 9.6.1 准备测试素材

```powershell
# 创建测试素材目录
$testDir = "C:\Workspace\AE-Projects\2026-07-06-测试项目-卡点视频"
$testMusic = Join-Path $testDir "02-素材\原始素材\music\test_music.mp3"
$testVideo1 = Join-Path $testDir "02-素材\原始素材\video\clip_001.mp4"
$testVideo2 = Join-Path $testDir "02-素材\原始素材\video\clip_002.mp4"

# 生成测试音频（30秒）
ffmpeg -f lavfi -i "sine=frequency=440:duration=30" -c:a aac $testMusic -y

# 生成测试视频1（10秒彩色条）
ffmpeg -f lavfi -i testsrc=duration=10:size=1920x1080:rate=30 -c:v libx264 $testVideo1 -y

# 生成测试视频2（10秒曼德博集合）
ffmpeg -f lavfi -i mandelbrot=duration=10:size=1920x1080:rate=30 -c:v libx264 $testVideo2 -y

Write-Host "Test assets created"
```

#### 9.6.2 运行完整端到端测试

> [!note] 测试流程
> 以下是理想状态下的完整测试步骤。实际使用时根据你的项目代码结构调整：

```
端到端测试步骤：

1. 启动 FastAPI 服务（如果用 FastAPI 模式）
2. 启动 After Effects
3. 打开 MCP Bridge 面板，确认已连接
4. 在 Trae / AI 助手中调用 autoEdit
5. 观察各阶段执行情况
6. 验证最终输出

预期结果：
✅ 音乐分析完成（BPM、节拍）
✅ 片段分析完成（分辨率、时长）
✅ 音画匹配完成（生成 MatchPlan）
✅ 参数反推完成（生成 CompilerInput）
✅ 编译器生成 JSX 成功
✅ MCP 调用 AE 执行成功
✅ AE 中创建了合成和图层
✅ 音效合成完成（如果启用）
✅ 输出视频可播放
```

#### 9.6.3 手动分步测试

如果全自动测试有问题，可以分步测试：

**Step 1: 测试音乐分析**

```powershell
# 激活环境
conda activate ae-ai

# 测试音乐分析
python -c "
import sys
sys.path.insert(0, 'C:/Projects/AE-MotionStudio/python-server')
from main import analyze_music
result = analyze_music('C:/Workspace/AE-Projects/2026-07-06-测试项目-卡点视频/02-素材/原始素材/music/test_music.mp3')
print(result)
"
```

**Step 2: 测试片段分析**

```powershell
# 测试片段分析
python -c "
import sys
sys.path.insert(0, 'C:/Projects/AE-MotionStudio/python-server')
from main import analyze_clip
result = analyze_clip('C:/Workspace/AE-Projects/2026-07-06-测试项目-卡点视频/02-素材/原始素材/video/clip_001.mp4')
print(result)
"
```

**Step 3: 测试 MCP 工具调用**

在 AI 助手中调用 `create-composition` 工具，确认 AE 中能创建合成。

**Step 4: 测试编译器**

```powershell
# 测试编译器
cd C:\Projects\AE-MotionStudio\compiler
node build/cli.js --help
```

> [!info] 参考文档
> 端到端工作流详情参见 [[AI辅助视频生成一体化工作流总览]]
> 流水线工程实现参见 [[音画匹配引擎与系统桥接工程手册]]

---


## 第10章 常见软件的安装与配置

> [!info] 章节目标
> 本章介绍 AI 辅助视频生成工作流中常用的辅助软件，包括素材管理、音频处理、视频播放、代码编辑等工具。
> 这些软件虽然不是系统核心组件，但能大幅提升工作效率和质量。



### 10.1 素材管理工具

#### 10.1.1 Adobe Bridge（推荐）

Adobe Bridge 是 Adobe 官方的素材管理工具，与 AE/PR 无缝集成。

**安装方式**：

```powershell
# 通过 Adobe Creative Cloud 安装
# 1. 打开 Creative Cloud Desktop
# 2. 找到 Bridge，点击安装
```

**配置建议**：

| 设置项 | 推荐值 | 说明 |
|--------|--------|------|
| 缓存位置 | `D:\Bridge_Cache` | 不要放在系统盘 |
| 缓存大小 | 100 GB | 根据素材量调整 |
| 自动生成缩略图 | 开启 | 方便浏览素材 |
| 元数据写入 | 开启 | 方便搜索和筛选 |

**常用快捷键**：

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+I` | 导入素材 |
| `Ctrl+G` | 批处理重命名 |
| `Ctrl+R` | 在资源管理器中显示 |
| `Ctrl+E` | 在 After Effects 中打开 |

#### 10.1.2 Eagle（备选）

Eagle 是一款专业的素材管理软件，适合图片和视频素材的整理。

```powershell
# 官网下载：https://eagle.cool/
# 或者使用 Chocolatey
choco install eagle -y
```

#### 10.1.3 本地文件命名规范

建立统一的文件命名规范，便于检索和管理：

```
素材命名规范：
├── 视频素材：[类型]_[场景]_[时长]_[编号].mp4
│   例如：clip_city_night_10s_001.mp4
├── 音乐素材：[风格]_[BPM]_[情绪]_[编号].mp3
│   例如：music_cyberpunk_128_energetic_001.mp3
├── 音效素材：[类别]_[描述]_[编号].wav
│   例如：sfx_whoosh_fast_001.wav
└── 图片素材：[类型]_[主题]_[尺寸]_[编号].jpg
    例如：img_landscape_mountain_4k_001.jpg
```

### 10.2 音频处理工具

#### 10.2.1 Audacity（免费开源）

Audacity 是一款免费开源的音频编辑软件，适合简单的音频处理。

```powershell
# Chocolatey 安装
choco install audacity -y

# 或者官网下载
# https://www.audacityteam.org/
```

**常用功能**：
- 音频裁剪和拼接
- 音量调整和标准化
- 降噪处理
- 频谱分析
- 批量格式转换

#### 10.2.2 Adobe Audition（专业级）

Adobe Audition 是专业级音频处理软件，与 AE/PR 无缝集成。

```powershell
# 通过 Adobe Creative Cloud 安装
```

**推荐配置**：

| 设置项 | 推荐值 | 说明 |
|--------|--------|------|
| 采样率 | 48000 Hz | 视频标准 |
| 位深度 | 32-bit | 专业级 |
| 缓存位置 | `D:\Audition_Cache` | 非系统盘 |
| 多轨混音 | 5.1 声道 | 根据需要 |

#### 10.2.3 音频批量处理脚本

```powershell
# 使用 FFmpeg 批量转换音频格式
$inputDir = "C:\Workspace\Music\raw"
$outputDir = "C:\Workspace\Music\converted"

New-Item -ItemType Directory -Path $outputDir -Force

# 批量转换为 AAC 格式
Get-ChildItem $inputDir -Filter "*.wav" | ForEach-Object {
    $output = Join-Path $outputDir ($_.BaseName + ".m4a")
    ffmpeg -i $_.FullName -c:a aac -b:a 320k $output -y
    Write-Host "Converted: $($_.Name)"
}
```

### 10.3 视频播放器与校验工具

#### 10.3.1 VLC 播放器

VLC 是最强大的开源视频播放器，支持几乎所有格式。

```powershell
# Chocolatey 安装
choco install vlc -y

# 验证
vlc --version
```

**常用功能**：
- 播放几乎所有视频格式
- 视频信息查看（编码、码率、帧率）
- 逐帧播放（`E` 键前进一帧）
- 截屏（`Shift+S`）
- 批量转码

#### 10.3.2 MediaInfo

MediaInfo 是专业的媒体文件信息查看工具。

```powershell
# Chocolatey 安装
choco install mediainfo -y

# 命令行版本
choco install mediainfo-cli -y

# 验证
mediainfo --version
```

**使用示例**：

```powershell
# 查看视频文件详细信息
mediainfo "C:\Temp\test_video.mp4"

# 输出为 JSON 格式
mediainfo --Output=JSON "C:\Temp\test_video.mp4"

# 只查看视频流信息
mediainfo --Output="Video;%Codec%/%Width%x%Height%/%FrameRate%/%BitRate%" "C:\Temp\test_video.mp4"
```

#### 10.3.3 视频质量校验

```powershell
# 批量检查视频文件完整性
$videoDir = "C:\Workspace\Footage"

Get-ChildItem $videoDir -Recurse -Include "*.mp4", "*.mov", "*.avi" | ForEach-Object {
    try {
        $info = ffprobe -v quiet -print_format json -show_format -show_streams $_.FullName 2>&1 | ConvertFrom-Json
        if ($info.streams.Count -gt 0) {
            Write-Host "[OK] $($_.Name)" -ForegroundColor Green
        } else {
            Write-Host "[WARN] No streams: $($_.Name)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Corrupted: $($_.Name)" -ForegroundColor Red
    }
}
```

### 10.4 代码编辑器（VS Code + 插件推荐）

#### 10.4.1 VS Code 安装

```powershell
# Chocolatey 安装
choco install vscode -y

# 或者官网下载
# https://code.visualstudio.com/

# 验证
code --version
```

#### 10.4.2 必备插件推荐

| 插件名称 | 用途 | 推荐度 |
|---------|------|--------|
| **Python** | Python 语法高亮、调试、智能提示 | ⭐⭐⭐⭐⭐ |
| **Pylance** | Python 高性能语言服务器 | ⭐⭐⭐⭐⭐ |
| **ESLint** | JavaScript/TypeScript 代码检查 | ⭐⭐⭐⭐⭐ |
| **Prettier** | 代码格式化 | ⭐⭐⭐⭐⭐ |
| **GitLens** | Git 增强（显示作者、历史） | ⭐⭐⭐⭐ |
| **Path Intellisense** | 路径自动补全 | ⭐⭐⭐⭐ |
| **DotENV** | .env 文件语法高亮 | ⭐⭐⭐ |
| **JSON Tools** | JSON 格式化和校验 | ⭐⭐⭐ |
| **Markdown All in One** | Markdown 编辑增强 | ⭐⭐⭐⭐ |
| **YAML** | YAML 语法支持 | ⭐⭐⭐⭐ |

**批量安装插件命令**：

```powershell
# 安装推荐插件
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension eamodio.gitlens
code --install-extension christian-kohler.path-intellisense
code --install-extension mikestead.dotenv
code --install-extension eriklynd.json-tools
code --install-extension yzhang.markdown-all-in-one
code --install-extension redhat.vscode-yaml
```

#### 10.4.3 推荐设置

```json
{
  "editor.fontSize": 14,
  "editor.tabSize": 2,
  "editor.wordWrap": "on",
  "editor.formatOnSave": true,
  "files.autoSave": "onFocusChange",
  "terminal.integrated.defaultProfile.windows": "PowerShell",
  "python.defaultInterpreterPath": "C:\\Tools\\Miniconda3\\envs\\ae-ai\\python.exe",
  "[python]": {
    "editor.defaultFormatter": "ms-python.python",
    "editor.tabSize": 4
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.tabSize": 2
  },
  "[json]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```


#### 10.4.3 VS Code 常用配置

以下是推荐的 VS Code 配置项，可以在 settings.json 中设置：

```json
{
  "editor.fontSize": 14,
  "editor.lineHeight": 22,
  "editor.fontFamily": "'JetBrains Mono', Consolas, 'Courier New', monospace",
  "editor.minimap.enabled": true,
  "editor.wordWrap": "on",
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "files.autoSave": "onFocusChange",
  "files.encoding": "utf8",
  "files.eol": "\n",
  "terminal.integrated.defaultProfile.windows": "PowerShell",
  "terminal.integrated.fontSize": 13,
  "explorer.confirmDelete": false,
  "explorer.confirmDragAndDrop": false,
  "workbench.editor.enablePreview": false,
  "workbench.colorTheme": "One Dark Pro",
  "workbench.iconTheme": "vscode-icons"
}
```

> [!tip] 打开 settings.json
> 按 `Ctrl + Shift + P`，输入「Open Settings (JSON)」，选择「首选项：打开设置(JSON)」。

#### 10.4.4 键盘快捷键配置

自定义快捷键可以大幅提升效率，以下是推荐的快捷键配置：

```json
[
  {
    "key": "ctrl+d",
    "command": "editor.action.copyLinesDownAction",
    "when": "editorTextFocus"
  },
  {
    "key": "ctrl+y",
    "command": "editor.action.deleteLines",
    "when": "editorTextFocus"
  },
  {
    "key": "ctrl+shift+l",
    "command": "editor.action.formatDocument"
  },
  {
    "key": "ctrl+`",
    "command": "workbench.action.terminal.toggleTerminal"
  },
  {
    "key": "ctrl+b",
    "command": "workbench.action.toggleSidebarVisibility"
  }
]
```

> [!tip] 打开快捷键配置
> 按 `Ctrl + Shift + P`，输入「Open Keyboard Shortcuts (JSON)」即可编辑。

#### 10.4.5 其他推荐编辑器

除了 VS Code，以下编辑器也值得考虑：

| 编辑器 | 特点 | 适用场景 |
|--------|------|---------|
| **Sublime Text** | 轻量、快速、启动即开 | 快速编辑单个文件 |
| **WebStorm** | JetBrains 出品，TS/JS 开发体验最佳 | 大型 TypeScript 项目 |
| **PyCharm** | Python 开发最强 IDE | Python 分析层开发 |
| **Notepad++** | Windows 经典轻量编辑器 | 快速查看/编辑文本 |
| **Obsidian** | Markdown 知识库管理 | 文档写作、知识管理 |

> [!success] 推荐组合
> - 主编辑器：VS Code（全能、插件丰富）
> - Python 开发：PyCharm Community（免费、功能强大）
> - 文档写作：Obsidian（双向链接、知识库管理）

### 10.5 对比与合并工具

#### 10.5.1 Beyond Compare（推荐）

Beyond Compare 是专业的文件和文件夹对比工具。

```powershell
# Chocolatey 安装
choco install beyondcompare -y
```

**用途**：
- 文件内容对比（代码、配置）
- 文件夹同步
- 图片对比
- 表格数据对比
- 三方合并

#### 10.5.2 WinMerge（免费开源）

WinMerge 是免费开源的文件对比工具。

```powershell
# Chocolatey 安装
choco install winmerge -y
```

#### 10.5.3 Git 配置对比工具

```powershell
# 配置 Git 使用 Beyond Compare 作为 diff/merge 工具
git config --global diff.tool bc4
git config --global difftool.bc4.path "C:/Program Files/Beyond Compare 4/BComp.exe"
git config --global merge.tool bc4
git config --global mergetool.bc4.path "C:/Program Files/Beyond Compare 4/BComp.exe"

# 使用方法
# git difftool <文件>
# git mergetool
```

### 10.6 其他实用工具

#### 10.6.1 截图工具 - Snipaste

```powershell
# Chocolatey 安装
choco install snipaste -y
```

#### 10.6.2 颜色拾取工具 - PowerToys

```powershell
# Microsoft PowerToys（包含颜色拾取、窗口管理等）
choco install powertoys -y
```

#### 10.6.3 任务栏增强 - Everything

```powershell
# Everything - 极速文件搜索
choco install everything -y
```

> [!info] 参考文档
> 工具链集成参见 [[图层操作与视频修剪工具链]]
> 音效工具参见 [[音效设计原子体系与音画同步]]

---


## 第11章 安全与备份

### 11.1 项目文件备份策略

#### 11.1.1 3-2-1 备份原则

**3-2-1 原则**是数据备份的黄金法则：

| 原则 | 说明 | 示例 |
|------|------|------|
| **3 份副本** | 原始数据 + 2 份备份 | 本地 + 外置硬盘 + 云存储 |
| **2 种介质** | 不同类型的存储介质 | SSD + HDD + 云存储 |
| **1 份异地** | 至少一份备份在异地 | 云存储或其他物理位置 |

#### 11.1.2 备份策略建议

```
备份策略示例：
├── 实时同步（工作中）
│   ├── 本地工作目录：C:\Workspace\
│   └── 同步到：D:\Workspace_Backup\
│
├── 每日备份（自动）
│   ├── 增量备份：每日凌晨 2 点
│   ├── 保留最近 30 天
│   └── 存储位置：外置硬盘
│
├── 每周备份（自动）
│   ├── 完整备份：每周日凌晨 3 点
│   ├── 保留最近 12 周
│   └── 存储位置：NAS / 云存储
│
└── 每月归档（手动）
    ├── 完整归档：每月 1 号
    ├── 永久保存
    └── 存储位置：冷存储 / 蓝光光盘
```

#### 11.1.3 Windows 自带备份工具

**文件历史记录**：

```powershell
# 启用文件历史记录（需要外接硬盘）
# 设置 → 系统 → 存储 → 高级存储设置 → 备份选项
# 或者使用控制面板：控制面板\所有控制面板项\文件历史记录
```

**系统映像备份**：

```powershell
# 创建系统映像
# 控制面板 → 备份和还原 (Windows 7) → 创建系统映像
```

#### 11.1.4 推荐备份软件

| 软件 | 类型 | 价格 | 推荐度 |
|------|------|------|--------|
| **Duplicati** | 开源备份 | 免费 | ⭐⭐⭐⭐⭐ |
| **Veeam Agent** | 企业级 | 免费版/付费 | ⭐⭐⭐⭐ |
| **Acronis True Image** | 消费级 | 付费 | ⭐⭐⭐⭐ |
| **GoodSync** | 文件同步 | 付费 | ⭐⭐⭐ |
| **FreeFileSync** | 开源同步 | 免费 | ⭐⭐⭐⭐ |

### 11.2 版本控制（Git + Git LFS）

#### 11.2.1 Git 版本控制最佳实践

**哪些文件应该用 Git 管理**：

| 文件类型 | 是否纳入 Git | 说明 |
|---------|-------------|------|
| 源代码（.py, .ts, .js） | ✅ 是 | 文本文件，适合版本控制 |
| 配置文件（.json, .yaml） | ✅ 是 | 文本文件 |
| 文档（.md, .txt） | ✅ 是 | 文本文件 |
| JSX 脚本 | ✅ 是 | 文本文件 |
| AE 项目文件（.aep） | ⚠️ 可选 | 二进制文件，体积大 |
| 视频素材 | ❌ 否 | 体积太大 |
| 音频素材 | ❌ 否 | 体积大 |
| 渲染输出 | ❌ 否 | 可重新生成 |

#### 11.2.2 .gitignore 配置

```gitignore
# 操作系统文件
Thumbs.db
.DS_Store
*.swp
*.swo

# 日志文件
*.log
logs/

# 缓存目录
cache/
*.cache

# 临时文件
temp/
tmp/
*.tmp
*.bak

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/
env/

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# IDE
.vscode/
.idea/
*.swp
*.swo

# AE 项目（可选，根据需要决定是否纳入）
# *.aep
# *.aepx

# 视频和音频文件
*.mp4
*.mov
*.avi
*.mkv
*.mp3
*.wav
*.flac
*.aac

# 图片（大文件）
*.psd
*.ai
*.tiff
*.bmp

# 渲染输出
exports/
render/
output/
```

#### 11.2.3 Git LFS 大文件存储

对于需要版本控制的大文件（如 AE 模板、PSD 文件），使用 Git LFS：

```powershell
# 安装 Git LFS
git lfs install

# 追踪特定类型的文件
git lfs track "*.aep"
git lfs track "*.psd"
git lfs track "*.mp4"

# 查看追踪的文件类型
git lfs track

# 提交 .gitattributes 文件
git add .gitattributes
git commit -m "Track large files with Git LFS"
```

#### 11.2.4 Git 分支策略

推荐使用 **Git Flow** 或简化的分支策略：

```
main/master  ← 生产就绪代码
   ↑
develop      ← 开发分支
   ↑
feature/*    ← 功能分支
hotfix/*     ← 紧急修复
release/*    ← 发布准备
```

**常用 Git 命令**：

```powershell
# 创建功能分支
git checkout -b feature/new-tool develop

# 完成功能，合并回 develop
git checkout develop
git merge --no-ff feature/new-tool
git branch -d feature/new-tool

# 打标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin --tags
```

### 11.3 依赖锁定

#### 11.3.1 Python 依赖锁定

**使用 requirements.txt**：

```powershell
# 激活环境
conda activate ae-ai

# 导出当前所有依赖
pip freeze > requirements.txt

# 从 requirements.txt 安装
pip install -r requirements.txt
```

**使用 environment.yml（conda）**：

```powershell
# 导出 conda 环境
conda env export > environment.yml

# 从 environment.yml 创建环境
conda env create -f environment.yml
```

**使用 Poetry（更高级）**：

```powershell
# 安装 Poetry
pip install poetry

# 初始化项目
poetry init

# 添加依赖
poetry add numpy scipy librosa

# 安装依赖（根据 poetry.lock）
poetry install
```

#### 11.3.2 Node.js 依赖锁定

**package-lock.json**：

```powershell
# npm 自动生成 package-lock.json
# 确保 package-lock.json 提交到 Git

# 安装锁定版本（精确安装）
npm ci

# 正常安装（可能更新小版本）
npm install
```

**使用 pnpm（推荐）**：

```powershell
# 安装 pnpm
npm install -g pnpm

# 安装依赖
pnpm install

# 好处：更快、更省磁盘空间
```

#### 11.3.3 版本号规范

遵循 **语义化版本（Semantic Versioning）**：

```
版本号格式：主版本号.次版本号.修订号

- 主版本号（MAJOR）：不兼容的 API 修改
- 次版本号（MINOR）：向下兼容的功能性新增
- 修订号（PATCH）：向下兼容的问题修正

示例：
1.0.0 → 1.0.1（修复 bug）
1.0.1 → 1.1.0（新增功能）
1.1.0 → 2.0.0（破坏性变更）
```

### 11.4 敏感信息管理

#### 11.4.1 常见敏感信息

| 类型 | 示例 | 风险 |
|------|------|------|
| API Key | OpenAI API Key、云服务密钥 | 盗用产生费用 |
| 数据库密码 | MySQL、Redis 密码 | 数据泄露 |
| 私钥文件 | SSH 私钥、证书私钥 | 未授权访问 |
| Token | GitHub Token、JWT | 身份冒用 |
| 配置文件中的密码 | config.yaml 中的明文密码 | 配置泄露 |

#### 11.4.2 环境变量管理

**使用 .env 文件**：

```powershell
# 创建 .env 文件（不要提交到 Git！）
# .env

# Python 路径
PYTHON_PATH=C:\Tools\Miniconda3\envs\ae-ai\python.exe

# API Key（如果有）
# OPENAI_API_KEY=sk-xxxxxxxxxx

# 项目路径
PROJECT_ROOT=C:\Projects\AE-MotionStudio

# 缓存目录
CACHE_DIR=C:\Cache\ae-analysis
```

**.gitignore 中添加**：

```gitignore
# 环境变量文件
.env
.env.local
.env.*.local
```

**Python 中读取 .env**：

```python
# 安装 python-dotenv
# pip install python-dotenv

from dotenv import load_dotenv
import os

load_dotenv()  # 加载 .env 文件

python_path = os.getenv("PYTHON_PATH")
api_key = os.getenv("OPENAI_API_KEY")
```

**TypeScript 中读取 .env**：

```typescript
// 安装 dotenv
// npm install dotenv

import * as dotenv from 'dotenv';
dotenv.config();

const pythonPath = process.env.PYTHON_PATH;
const apiKey = process.env.OPENAI_API_KEY;
```

#### 11.4.3 Windows 凭据管理器

对于更敏感的信息，使用 Windows 凭据管理器：

```powershell
# 查看凭据管理器
rundll32.exe keymgr.dll, KRShowKeyMgr

# 或者使用 PowerShell 的 SecretManagement 模块
Install-Module -Name Microsoft.PowerShell.SecretManagement -Scope CurrentUser
Install-Module -Name Microsoft.PowerShell.SecretStore -Scope CurrentUser

# 注册保管库
Register-SecretVault -Name LocalStore -ModuleName Microsoft.PowerShell.SecretStore

# 设置密码
Set-Secret -Name "ApiKey" -Secret "your-api-key-here"

# 读取密码
Get-Secret -Name "ApiKey"
```


### 11.4 敏感信息管理

#### 11.4.1 API Key 与凭证管理

在 AI 视频生成系统中，可能涉及以下敏感信息：

- HuggingFace API Key（下载模型）
- 云存储服务密钥（备份）
- 第三方服务 API Key
- 数据库连接密码
- 内部服务令牌

**管理原则**：

1. **永不硬编码**：不要将密钥直接写在代码中
2. **环境变量传递**：通过环境变量注入敏感信息
3. **配置文件隔离**：敏感配置单独存放，不纳入版本控制
4. **定期轮换**：定期更换密钥，降低泄露风险

#### 11.4.2 环境变量配置

```powershell
# 设置用户级环境变量（仅当前用户可见）
[Environment]::SetEnvironmentVariable("HF_API_KEY", "your_api_key_here", "User")
[Environment]::SetEnvironmentVariable("CLOUD_STORAGE_SECRET", "your_secret_here", "User")

# 验证设置
[Environment]::GetEnvironmentVariable("HF_API_KEY", "User")
```

**Python 中读取环境变量**：

```python
import os

hf_api_key = os.environ.get("HF_API_KEY")
if not hf_api_key:
    raise ValueError("HF_API_KEY environment variable not set")

# 使用 .env 文件（推荐开发环境）
# from dotenv import load_dotenv
# load_dotenv()  # 从 .env 文件加载
```

**TypeScript 中读取环境变量**：

```typescript
const hfApiKey = process.env.HF_API_KEY;
if (!hfApiKey) {
  throw new Error("HF_API_KEY environment variable not set");
}
```

#### 11.4.3 .env 文件使用规范

开发环境中可以使用 `.env` 文件管理敏感信息，但必须遵守以下规则：

```
# .env 文件示例
HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxx
CLOUD_SECRET=yyyyyyyyyyyyyyyyyyyy

# .gitignore 中必须添加
.env
.env.local
.env.*.local
*.pem
*.key
*.p12
```

> [!warning] 重要提醒
> - `.env` 文件**绝对不能**提交到 Git 仓库
> - 在 `.gitignore` 中明确排除所有敏感文件
> - 共享项目时使用 `.env.example` 提供模板，不包含真实值

#### 11.4.4 Windows 凭据管理器

Windows 提供了凭据管理器（Credential Manager），可以安全存储密码和密钥：

```powershell
# 使用 cmdkey 命令存储凭据（简单场景）
cmdkey /generic:AE-Video-Generator /user:api_key /pass:your_secret_key

# 查看存储的凭据
cmdkey /list

# 删除凭据
# cmdkey /delete:AE-Video-Generator
```

> [!note] 更安全的方案
> 对于企业级部署，建议使用专门的密钥管理服务：
> - **Azure Key Vault**：微软云密钥管理
> - **HashiCorp Vault**：开源密钥管理
> - **AWS Secrets Manager**：AWS 密钥管理


### 11.5 灾难恢复预案

#### 11.5.1 灾难等级定义

| 等级 | 描述 | 恢复时间目标（RTO） |
|------|------|-------------------|
| **P0 - 严重** | 系统完全不可用，数据丢失 | 24 小时 |
| **P1 - 高** | 核心功能不可用 | 4 小时 |
| **P2 - 中** | 部分功能不可用 | 1 小时 |
| **P3 - 低** | 轻微问题，不影响核心功能 | 随时修复 |

#### 11.5.2 常见灾难恢复步骤

**场景 1：系统崩溃，无法启动**

```
恢复步骤：
1. 从系统映像恢复系统（如果有）
2. 或者重装系统
3. 重新安装所有软件（参考本指南）
4. 从备份恢复项目文件
5. 验证环境可用性
6. 恢复正常工作
```

**场景 2：误删重要文件**

```
恢复步骤：
1. 检查回收站
2. 检查文件历史记录（Windows）
3. 检查 Git 版本历史
4. 检查备份文件
5. 使用数据恢复软件（如 Recuva、DiskGenius）
6. 如果非常重要，找专业数据恢复公司
```

**场景 3：AE 项目文件损坏**

```
恢复步骤：
1. 尝试打开自动保存文件
   - AE 自动保存位置：我的文档\Adobe\After Effects Auto-Save
2. 尝试从备份恢复
3. 尝试导入到新项目中
4. 尝试使用 .aepx 格式（XML 文本格式）
5. 如果有 Git 版本，回退到上一版本
```

#### 11.5.3 定期演练

> [!important] 重要
> 备份不是目的，**能恢复**才是目的。建议每季度进行一次恢复演练：
>
> 1. 随机选择一个项目
> 2. 从备份中恢复
> 3. 验证项目完整性
> 4. 记录恢复时间和问题
> 5. 优化备份策略

> [!info] 参考文档
> 知识库管理规范参见 [[AE知识库管理规范]]

---


## 第12章 部署验证与验收

### 12.1 部署验证检查清单（50+ 项）

#### 12.1.1 基础环境验证（10 项）

| # | 检查项 | 验证方法 | 预期结果 |
|---|--------|---------|---------|
| 1 | Windows 版本 | `winver` | Windows 10 21H2+ 或 Windows 11 22H2+ |
| 2 | PowerShell 版本 | `$PSVersionTable.PSVersion` | 5.1+ 或 7.x |
| 3 | 管理员权限 | 安全主体检查 | 返回 True |
| 4 | Chocolatey / Scoop | `choco --version` / `scoop --version` | 输出版本号 |
| 5 | Git 安装 | `git --version` | 输出版本号 |
| 6 | Git 配置 | `git config --list` | user.name 和 user.email 已设置 |
| 7 | 目录结构 | `Test-Path` 检查 | 所有目录存在 |
| 8 | 环境变量 | `$env:PATH` | 工具路径已添加 |
| 9 | 缓存目录 | `Test-Path` 检查 | 缓存目录存在 |
| 10 | 网络连接 | `ping google.com` | 网络正常 |

#### 12.1.2 Python 环境验证（10 项）

| # | 检查项 | 验证方法 | 预期结果 |
|---|--------|---------|---------|
| 11 | Conda 安装 | `conda --version` | 输出版本号 |
| 12 | 虚拟环境存在 | `conda env list` | ae-ai 环境存在 |
| 13 | Python 版本 | `python --version` | Python 3.11.x |
| 14 | numpy | `import numpy` | 导入成功，输出版本 |
| 15 | scipy | `import scipy` | 导入成功，输出版本 |
| 16 | librosa | `import librosa` | 导入成功，输出版本 |
| 17 | OpenCV | `import cv2` | 导入成功，输出版本 |
| 18 | scikit-learn | `import sklearn` | 导入成功，输出版本 |
| 19 | PyTorch | `import torch` | 导入成功，CUDA 可用 |
| 20 | FastAPI | `import fastapi` | 导入成功（可选） |

#### 12.1.3 Node.js 环境验证（8 项）

| # | 检查项 | 验证方法 | 预期结果 |
|---|--------|---------|---------|
| 21 | Node.js 版本 | `node --version` | v20.x LTS |
| 22 | npm 版本 | `npm --version` | 10.x |
| 23 | npm 镜像 | `npm config get registry` | 国内镜像或官方 |
| 24 | TypeScript | `tsc --version` | 输出版本号 |
| 25 | esbuild | `esbuild --version` | 输出版本号 |
| 26 | 编译器依赖 | `ls node_modules` | node_modules 存在 |
| 27 | 编译器构建 | `npm run build` | 构建成功 |
| 28 | 编译器测试 | `npm test` | 测试通过 |

#### 12.1.4 FFmpeg 验证（5 项）

| # | 检查项 | 验证方法 | 预期结果 |
|---|--------|---------|---------|
| 29 | FFmpeg 版本 | `ffmpeg -version` | 6.x 或更高 |
| 30 | ffprobe 可用 | `ffprobe -version` | 输出版本号 |
| 31 | H.264 编码 | `ffmpeg -encoders \| findstr libx264` | 支持 libx264 |
| 32 | H.265 编码 | `ffmpeg -encoders \| findstr libx265` | 支持 libx265 |
| 33 | 硬件加速 | `ffmpeg -encoders \| findstr nvenc` | NVENC 可用（如有 N 卡） |

#### 12.1.5 AE MCP 验证（12 项）

| # | 检查项 | 验证方法 | 预期结果 |
|---|--------|---------|---------|
| 34 | AE 2025 可启动 | 手动启动 AE | 正常启动 |
| 35 | Bridge 面板安装 | AE 窗口 → 扩展 | AE MCP Bridge 可见 |
| 36 | CEP 调试模式 | 注册表检查 | PlayerDebugMode=1 |
| 37 | MCP Server 构建 | `npm run build` | 构建成功 |
| 38 | 基础工具数量 | MCP 工具列表 | 22+ 基础工具 |
| 39 | 扩展工具数量 | MCP 工具列表 | 14 个扩展工具 |
| 40 | 总工具数量 | MCP 工具列表 | 36+ 个工具 |
| 41 | create-composition 工具 | 调用测试 | 创建合成成功 |
| 42 | add-effect 工具 | 调用测试 | 添加效果成功 |
| 43 | add-adjustment-layer 工具 | 调用测试 | 添加调整图层成功 |
| 44 | 命令文件轮询 | 检查 ae_command.json | 文件被正确读取 |
| 45 | 结果文件返回 | 检查 ae_mcp_result.json | 结果正确写入 |

#### 12.1.6 端到端验证（8 项）

| # | 检查项 | 验证方法 | 预期结果 |
|---|--------|---------|---------|
| 46 | Python 子进程模式 | stdio 调用测试 | 返回 JSON 结果 |
| 47 | FastAPI 服务（可选） | 健康检查 | 返回 200 OK |
| 48 | 音乐分析接口 | 调用 analyze_music | 返回 BPM、节拍等 |
| 49 | 片段分析接口 | 调用 analyze_clip | 返回视频信息 |
| 50 | 音画匹配接口 | 调用 match | 返回匹配结果 |
| 51 | 编译器调用 | 运行编译器 | 生成 JSX 成功 |
| 52 | MCP 调用 AE | 调用工具 | AE 中执行成功 |
| 53 | 完整端到端测试 | 跑通完整流程 | 输出视频 |


#### 12.1.2 模块级检查清单（续）

**Python 分析层检查（20项）**

| 序号 | 检查项 | 验证方法 | 预期结果 | 状态 |
|------|--------|---------|---------|------|
| 1 | Python 版本正确 | `python --version` | 3.11.x | ☐ |
| 2 | conda 环境可用 | `conda activate ae-ai` | 无错误 | ☐ |
| 3 | numpy 可导入 | `python -c "import numpy; print(numpy.__version__)"` | 输出版本号 | ☐ |
| 4 | scipy 可导入 | `python -c "import scipy; print(scipy.__version__)"` | 输出版本号 | ☐ |
| 5 | librosa 可导入 | `python -c "import librosa; print(librosa.__version__)"` | 输出版本号 | ☐ |
| 6 | opencv 可导入 | `python -c "import cv2; print(cv2.__version__)"` | 输出版本号 | ☐ |
| 7 | scikit-learn 可导入 | `python -c "import sklearn; print(sklearn.__version__)"` | 输出版本号 | ☐ |
| 8 | pydub 可导入 | `python -c "import pydub; print(pydub.__version__)"` | 输出版本号 | ☐ |
| 9 | soundfile 可导入 | `python -c "import soundfile; print(soundfile.__version__)"` | 输出版本号 | ☐ |
| 10 | torch 可导入（可选） | `python -c "import torch; print(torch.__version__)"` | 输出版本号 | ☐ |
| 11 | CUDA 可用（可选） | `python -c "import torch; print(torch.cuda.is_available())"` | True | ☐ |
| 12 | madmom 可导入（可选） | `python -c "import madmom; print(madmom.__version__)"` | 输出版本号 | ☐ |
| 13 | essentia 可导入（可选） | `python -c "import essentia; print(essentia.__version__)"` | 输出版本号 | ☐ |
| 14 | pyscenedetect 可导入（可选） | `python -c "import scenedetect; print(scenedetect.__version__)"` | 输出版本号 | ☐ |
| 15 | fastapi 可导入（可选） | `python -c "import fastapi; print(fastapi.__version__)"` | 输出版本号 | ☐ |
| 16 | 音乐分析脚本运行 | `python main.py analyze_music test.mp3` | 返回有效结果 | ☐ |
| 17 | 片段分析脚本运行 | `python main.py analyze_clip test.mp4` | 返回有效结果 | ☐ |
| 18 | 音画匹配脚本运行 | `python main.py match ...` | 返回有效结果 | ☐ |
| 19 | 分析结果缓存正常 | 检查缓存目录 | 有缓存文件生成 | ☐ |
| 20 | 日志输出正常 | 检查日志文件 | 日志格式正确 | ☐ |

**TS 引擎层检查（15项）**

| 序号 | 检查项 | 验证方法 | 预期结果 | 状态 |
|------|--------|---------|---------|------|
| 1 | Node.js 版本正确 | `node --version` | v20.x LTS | ☐ |
| 2 | npm 版本正确 | `npm --version` | 10.x | ☐ |
| 3 | TypeScript 可用 | `npx tsc --version` | 5.x | ☐ |
| 4 | 依赖安装完整 | `npm ls` | 无缺失依赖 | ☐ |
| 5 | 项目编译通过 | `npm run build` | 编译成功 | ☐ |
| 6 | 编译器可用 | `node dist/compiler.js` | 正常启动 | ☐ |
| 7 | autoEdit 入口可用 | 单元测试 | 通过 | ☐ |
| 8 | Subprocess 桥接可用 | 桥接测试 | 调用成功 | ☐ |
| 9 | FastAPI 桥接可用（可选） | API 测试 | 调用成功 | ☐ |
| 10 | 验证器工作正常 | 验证测试 | 通过 | ☐ |
| 11 | 错误处理正常 | 错误测试 | 正确报错 | ☐ |
| 12 | 日志系统正常 | 检查日志 | 输出正确 | ☐ |
| 13 | 配置文件加载正常 | 启动测试 | 配置正确 | ☐ |
| 14 | 单元测试通过 | `npm test` | 全部通过 | ☐ |
| 15 | 类型检查通过 | `npx tsc --noEmit` | 无错误 | ☐ |

**MCP 传输层检查（10项）**

| 序号 | 检查项 | 验证方法 | 预期结果 | 状态 |
|------|--------|---------|---------|------|
| 1 | MCP Server 启动 | 启动命令 | 正常启动 | ☐ |
| 2 | 基础工具注册 | `tools/list` | 返回工具列表 | ☐ |
| 3 | 扩展工具注册 | `tools/list` | 36个工具 | ☐ |
| 4 | 工具调用正常 | `tools/call` | 返回正确结果 | ☐ |
| 5 | 错误处理正常 | 调用错误命令 | 正确错误信息 | ☐ |
| 6 | Trae MCP 配置正确 | Trae 设置 | MCP 已连接 | ☐ |
| 7 | 命令文件生成正常 | 检查工作目录 | 有 ae_command.json | ☐ |
| 8 | 结果文件读取正常 | 检查工作目录 | 有 ae_mcp_result.json | ☐ |
| 9 | 并发调用正常 | 同时调用多个工具 | 无冲突 | ☐ |
| 10 | 日志记录完整 | 检查 MCP 日志 | 有详细日志 | ☐ |

**AE 执行层检查（12项）**

| 序号 | 检查项 | 验证方法 | 预期结果 | 状态 |
|------|--------|---------|---------|------|
| 1 | AE 2025 正常启动 | 启动 AE | 正常打开 | ☐ |
| 2 | MCP Bridge 面板可见 | 窗口菜单 | 面板存在 | ☐ |
| 3 | Bridge 面板连接正常 | 查看面板状态 | 已连接 | ☐ |
| 4 | CEP 调试模式开启 | 注册表检查 | PlayerDebugMode=1 | ☐ |
| 5 | JSX 脚本目录正确 | 检查脚本目录 | 脚本存在 | ☐ |
| 6 | 允许脚本列表配置 | 检查配置 | 白名单正确 | ☐ |
| 7 | 新建合成工具可用 | MCP 调用 | 合成创建成功 | ☐ |
| 8 | 添加图层工具可用 | MCP 调用 | 图层添加成功 | ☐ |
| 9 | 应用效果工具可用 | MCP 调用 | 效果应用成功 | ☐ |
| 10 | 设置关键帧工具可用 | MCP 调用 | 关键帧设置成功 | ☐ |
| 11 | 项目保存工具可用 | MCP 调用 | 项目保存成功 | ☐ |
| 12 | 渲染队列工具可用 | MCP 调用 | 渲染添加成功 | ☐ |

**音效合成层检查（8项）**

| 序号 | 检查项 | 验证方法 | 预期结果 | 状态 |
|------|--------|---------|---------|------|
| 1 | FFmpeg 版本正确 | `ffmpeg -version` | 6.0+ | ☐ |
| 2 | FFprobe 可用 | `ffprobe -version` | 正常输出 | ☐ |
| 3 | 常用编码器可用 | `ffmpeg -encoders` | h264/aac 等 | ☐ |
| 4 | 硬件加速可用（可选） | `ffmpeg -encoders \| grep nvenc` | nvenc 存在 | ☐ |
| 5 | 音频转码正常 | 转码测试 | 成功生成文件 | ☐ |
| 6 | 视频转码正常 | 转码测试 | 成功生成文件 | ☐ |
| 7 | 多轨混音正常 | 混音测试 | 成功生成文件 | ☐ |
| 8 | 响度标准化正常 | 响度测试 | 响度符合标准 | ☐ |

### 12.2 冒烟测试流程

#### 12.2.1 什么是冒烟测试

**冒烟测试（Smoke Test）** 是一种快速验证测试，用于确认系统的核心功能是否正常工作。它不测试细节，只验证「系统能不能跑起来」。

> [!note] 命名由来
> 「冒烟测试」这个词来源于硬件测试：给新硬件上电，如果没有冒烟，说明基本没问题。

#### 12.2.2 冒烟测试步骤

**预计耗时：15 分钟**

```
冒烟测试流程：
├── Step 1: 环境检查（2 分钟）
│   ├── 验证 Python 可用
│   ├── 验证 Node.js 可用
│   └── 验证 FFmpeg 可用
│
├── Step 2: Python 核心库测试（3 分钟）
│   ├── 测试 numpy/scipy
│   ├── 测试 librosa
│   └── 测试 OpenCV
│
├── Step 3: MCP 服务测试（5 分钟）
│   ├── 构建 MCP Server
│   ├── 启动 AE
│   ├── 打开 Bridge 面板
│   └── 测试创建合成
│
├── Step 4: 编译器测试（3 分钟）
│   ├── 构建编译器
│   └── 运行测试用例
│
└── Step 5: 快速集成测试（2 分钟）
    ├── 测试音乐分析
    └── 测试片段分析
```

#### 12.2.3 冒烟测试脚本

```powershell
# smoke-test.ps1 - 冒烟测试脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Video Generation - Smoke Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$passed = 0
$failed = 0

function Test-Check {
    param(
        [string]$Name,
        [scriptblock]$Test
    )
    
    Write-Host "  Testing: $Name ... " -NoNewline
    try {
        & $Test
        Write-Host "PASS" -ForegroundColor Green
        $script:passed++
    } catch {
        Write-Host "FAIL" -ForegroundColor Red
        Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
        $script:failed++
    }
}

# 1. 基础环境
Write-Host "[1/5] Base Environment" -ForegroundColor Yellow

Test-Check "Python" {
    $v = python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python not found" }
}

Test-Check "Node.js" {
    $v = node --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Node.js not found" }
}

Test-Check "FFmpeg" {
    $v = ffmpeg -version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "FFmpeg not found" }
}

Write-Host ""

# 2. Python 库
Write-Host "[2/5] Python Libraries" -ForegroundColor Yellow

Test-Check "numpy" {
    python -c "import numpy; print(numpy.__version__)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "numpy import failed" }
}

Test-Check "librosa" {
    python -c "import librosa; print(librosa.__version__)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "librosa import failed" }
}

Test-Check "OpenCV" {
    python -c "import cv2; print(cv2.__version__)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "cv2 import failed" }
}

Write-Host ""

# 3. Node.js 项目
Write-Host "[3/5] Node.js Projects" -ForegroundColor Yellow

Test-Check "MCP Server build" {
    Push-Location "C:\Projects\after-effects-mcp"
    npm run build 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "MCP build failed" }
    Pop-Location
}

Test-Check "Compiler build" {
    Push-Location "C:\Projects\AE-MotionStudio\compiler"
    npm run build 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Compiler build failed" }
    Pop-Location
}

Write-Host ""

# 4. 结果
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Smoke Test Results" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Passed: $passed" -ForegroundColor Green
Write-Host "  Failed: $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($failed -eq 0) {
    Write-Host "  ✅ All smoke tests passed!" -ForegroundColor Green
} else {
    Write-Host "  ❌ Some tests failed. Check the errors above." -ForegroundColor Red
    exit 1
}
```

### 12.3 集成测试流程

#### 12.3.1 什么是集成测试

**集成测试（Integration Test）** 验证各个模块之间的交互是否正常。比冒烟测试更全面，但比完整的端到端测试快。

#### 12.3.2 集成测试用例

**测试用例 1：音乐分析 → 片段分析 → 音画匹配**

```
测试目标：验证 Python 分析层的三个核心模块串联正常

步骤：
1. 准备测试音频（30 秒）
2. 准备测试视频（2 个片段）
3. 调用 analyze_music
4. 调用 analyze_clip（2 次）
5. 调用 match_audio_visual
6. 验证返回结果结构正确

预期结果：
- 音乐分析返回 BPM、节拍点
- 片段分析返回分辨率、时长、帧率
- 匹配返回匹配对列表
- 所有接口在合理时间内返回
```

**测试用例 2：编译器 → MCP → AE**

```
测试目标：验证 TS 引擎层和 AE 执行层的串联

步骤：
1. 准备 CompilerInput（简单的测试用例）
2. 运行编译器生成 JSX
3. 通过 MCP 调用 execute-atom-script
4. 在 AE 中验证结果

预期结果：
- 编译器生成有效的 JSX
- MCP 调用成功
- AE 中创建了对应的合成和图层
- 没有报错
```

**测试用例 3：Python-TS 桥接**

```
测试目标：验证 Python 和 TypeScript 之间的通信

Subprocess 模式：
1. 从 TS 端调用 Python 子进程
2. 传入音乐分析请求
3. 验证返回结果

FastAPI 模式（可选）：
1. 启动 FastAPI 服务
2. 从 TS 端发送 HTTP 请求
3. 验证返回结果
4. 测试并发请求
```

### 12.4 性能基准测试

#### 12.4.1 为什么需要性能基准

性能基准测试的目的：
1. 了解当前系统的性能基线
2. 优化前后对比，验证优化效果
3. 发现性能瓶颈
4. 预估大规模项目的耗时

#### 12.4.2 性能测试指标

| 指标 | 说明 | 测试方法 |
|------|------|---------|
| **音乐分析耗时** | 分析一首 3 分钟歌曲的时间 | 计时 analyze_music |
| **片段分析耗时** | 分析一个 10 秒片段的时间 | 计时 analyze_clip |
| **匹配算法耗时** | 音画匹配的计算时间 | 计时 match_audio_visual |
| **编译器耗时** | 编译生成 JSX 的时间 | 计时 compiler |
| **AE 执行耗时** | MCP 调用 + AE 执行的时间 | 计时 AE 操作 |
| **端到端总耗时** | 从输入到输出的总时间 | 计时 autoEdit |

#### 12.4.3 性能测试脚本

```python
# benchmark.py - 性能基准测试
import time
import json
import statistics

def benchmark(func, *args, n=5, **kwargs):
    """运行函数 n 次，返回统计信息"""
    times = []
    for i in range(n):
        t0 = time.time()
        result = func(*args, **kwargs)
        t1 = time.time()
        times.append(t1 - t0)
        print(f"  Run {i+1}: {t1-t0:.3f}s")
    
    return {
        "min": min(times),
        "max": max(times),
        "avg": statistics.mean(times),
        "median": statistics.median(times),
        "std": statistics.stdev(times) if len(times) > 1 else 0
    }

def main():
    print("=" * 60)
    print("Performance Benchmark")
    print("=" * 60)
    
    results = {}
    
    # 音乐分析
    print("\n[1/4] Music Analysis")
    music_path = "test_music.mp3"
    results["music_analysis"] = benchmark(analyze_music, music_path)
    
    # 片段分析
    print("\n[2/4] Clip Analysis")
    clip_path = "test_clip.mp4"
    results["clip_analysis"] = benchmark(analyze_clip, clip_path)
    
    # 匹配
    print("\n[3/4] Audio-Visual Matching")
    music_data = {"bpm": 120, "beat_times": [1, 2, 3]}
    clip_data = [{"duration": 10}, {"duration": 15}]
    results["matching"] = benchmark(match_audio_visual, music_data, clip_data, "cinematic")
    
    # 保存结果
    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)
    for name, stats in results.items():
        print(f"\n{name}:")
        print(f"  Avg: {stats['avg']:.3f}s")
        print(f"  Min: {stats['min']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")
        print(f"  Median: {stats['median']:.3f}s")
    
    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to benchmark_results.json")

if __name__ == "__main__":
    main()
```

### 12.5 部署文档与交接

#### 12.5.1 部署文档清单

部署完成后，应该整理以下文档：

| 文档 | 用途 | 更新频率 |
|------|------|---------|
| **部署手册**（本文档） | 从零开始部署指南 | 大版本更新时 |
| **环境配置清单** | 记录所有版本号和配置 | 每次环境变更 |
| **账号密码清单** | API Key、凭证等 | 每次变更 |
| **运维手册** | 日常运维、故障处理 | 持续更新 |
| **性能基线报告** | 性能基准测试结果 | 每季度/重大优化后 |

#### 12.5.2 环境配置清单模板

```markdown
# 环境配置清单

## 服务器信息
- 操作系统：Windows 11 Pro 22H2
- CPU：Intel i7-13700K
- GPU：NVIDIA RTX 4070 12GB
- 内存：32 GB DDR5
- 存储：1 TB NVMe SSD

## 软件版本
- Python：3.11.8
- Node.js：20.11.1 LTS
- FFmpeg：6.1
- After Effects：2025 (25.0)
- Git：2.44.0

## Python 核心依赖
- numpy：1.26.4
- scipy：1.11.4
- librosa：0.10.1
- opencv-python：4.8.1.78
- torch：2.2.0+cu121
- fastapi：0.109.2

## Node.js 核心依赖
- typescript：5.3.3
- @modelcontextprotocol/sdk：0.4.0
- esbuild：0.20.0

## 配置信息
- 项目根目录：C:\Projects\AE-MotionStudio
- MCP Server 路径：C:\Projects\after-effects-mcp
- Python 环境：ae-ai (conda)
- 缓存目录：C:\Cache\ae-analysis
- 临时目录：C:\Cache\temp
```

#### 12.5.3 交接检查清单

```
交接检查清单：
├── [ ] 部署文档完整（本文档）
├── [ ] 环境配置清单已更新
├── [ ] 账号密码已安全移交
├── [ ] 冒烟测试通过
├── [ ] 集成测试通过
├── [ ] 性能基准已记录
├── [ ] 备份策略已配置
├── [ ] 监控告警已配置（可选）
├── [ ] 接收人已验证环境可用
├── [ ] 接收人已完成一次完整操作
```

> [!success] 部署完成
> 恭喜！如果你通过了所有验证测试，说明 AI 辅助视频生成系统已经成功部署！
>
> 接下来你可以：
> - 阅读 [[AI辅助视频生成一体化工作流总览]] 了解完整工作流
> - 阅读 [[音画匹配引擎与系统桥接工程手册]] 深入了解系统架构
> - 开始你的第一个 AI 辅助视频生成项目！

---


## 附录A：一键部署脚本

### A.1 Windows PowerShell 部署脚本

以下是一个自动化部署脚本，可以一键安装大部分依赖。

> [!warning] 注意事项
> - 请以**管理员身份**运行 PowerShell
> - 脚本执行时间约 30-60 分钟（取决于网络速度）
> - 建议先阅读脚本内容，了解每一步做什么
> - 如遇错误，可以分段执行，手动排查问题

#### A.1.1 一键部署脚本

```powershell
# ============================================================================
# AI 辅助视频生成系统 - 一键部署脚本
# 版本：1.0.0
# 适用：Windows 10/11 + PowerShell 5.1+
# ============================================================================

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI 视频生成系统 - 一键部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 配置变量
# ============================================================================
$InstallDir = "C:\Tools"
$ProjectDir = "C:\Projects\AE-MotionStudio"
$CacheDir = "C:\Cache"
$WorkspaceDir = "C:\Workspace"

$PythonVersion = "3.11"
$NodeVersion = "20.11.1"
$CondaEnvName = "ae-ai"

Write-Host "[配置]" -ForegroundColor Yellow
Write-Host "  安装目录: $InstallDir"
Write-Host "  项目目录: $ProjectDir"
Write-Host "  缓存目录: $CacheDir"
Write-Host ""

# ============================================================================
# Step 1: 基础检查
# ============================================================================
Write-Host "[1/8] 基础环境检查" -ForegroundColor Yellow

# 检查 Windows 版本
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "  Windows 版本: $($os.Caption)"
Write-Host "  系统架构: $($os.OSArchitecture)"

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host "  管理员权限: $isAdmin"

if (-not $isAdmin) {
    Write-Error "请以管理员身份运行此脚本！"
    exit 1
}

# 检查 PowerShell 版本
Write-Host "  PowerShell 版本: $($PSVersionTable.PSVersion)"

Write-Host "  ✅ 基础检查通过" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 2: 安装 Chocolatey
# ============================================================================
Write-Host "[2/8] 安装 Chocolatey 包管理器" -ForegroundColor Yellow

if (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "  Chocolatey 已安装: $(choco --version)"
} else {
    Write-Host "  正在安装 Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    refreshenv
    Write-Host "  ✅ Chocolatey 安装完成" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# Step 3: 安装基础工具
# ============================================================================
Write-Host "[3/8] 安装基础工具" -ForegroundColor Yellow

$tools = @(
    @{name = "git"; check = "git --version"},
    @{name = "7zip"; check = "7z --version"},
    @{name = "ffmpeg"; check = "ffmpeg -version"},
    @{name = "vscode"; check = "code --version"},
    @{name = "nssm"; check = "nssm version"},
    @{name = "vlc"; check = "vlc --version"},
    @{name = "mediainfo-cli"; check = "mediainfo --version"}
)

foreach ($tool in $tools) {
    Write-Host "  安装 $($tool.name)..."
    try {
        choco install $tool.name -y
        Write-Host "    ✅ $($tool.name) 安装完成" -ForegroundColor Green
    } catch {
        Write-Host "    ⚠️  $($tool.name) 安装可能失败，请手动检查" -ForegroundColor Yellow
    }
}

refreshenv
Write-Host ""

# ============================================================================
# Step 4: 安装 Miniconda
# ============================================================================
Write-Host "[4/8] 安装 Miniconda (Python $PythonVersion)" -ForegroundColor Yellow

$condaPath = "$InstallDir\Miniconda3"

if (Test-Path $condaPath) {
    Write-Host "  Miniconda 已安装"
} else {
    Write-Host "  下载 Miniconda..."
    $installer = "$env:TEMP\miniconda.exe"
    Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-py311_24.1.2-0-Windows-x86_64.exe" -OutFile $installer
    
    Write-Host "  安装 Miniconda..."
    Start-Process -FilePath $installer -ArgumentList "/S","/D=$condaPath" -Wait
    
    Write-Host "  ✅ Miniconda 安装完成" -ForegroundColor Green
}

# 初始化 conda
Write-Host "  初始化 conda..."
& "$condaPath\shell\condabin\conda-hook.ps1"
conda init powershell 2>&1 | Out-Null

refreshenv
Write-Host ""

# ============================================================================
# Step 5: 创建 Python 虚拟环境
# ============================================================================
Write-Host "[5/8] 配置 Python 环境" -ForegroundColor Yellow

# 检查环境是否存在
$envExists = conda env list | Select-String $CondaEnvName
if ($envExists) {
    Write-Host "  虚拟环境 $CondaEnvName 已存在"
} else {
    Write-Host "  创建虚拟环境 $CondaEnvName..."
    conda create -n $CondaEnvName python=$PythonVersion -y
    Write-Host "  ✅ 虚拟环境创建完成" -ForegroundColor Green
}

# 激活环境并安装依赖
Write-Host "  安装 Python 依赖（这可能需要几分钟）..."
conda activate $CondaEnvName

# 配置 pip 清华源
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn 2>&1 | Out-Null

# 安装核心依赖
pip install numpy scipy librosa soundfile pydub opencv-python scikit-learn pyyaml 2>&1 | Out-Null

# 安装可选依赖
pip install fastapi uvicorn 2>&1 | Out-Null

# 尝试安装 PyTorch（CPU 版本，CUDA 版本请手动安装）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu 2>&1 | Out-Null

Write-Host "  ✅ Python 依赖安装完成" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 6: 安装 Node.js
# ============================================================================
Write-Host "[6/8] 安装 Node.js" -ForegroundColor Yellow

if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "  Node.js 已安装: $(node --version)"
} else {
    Write-Host "  安装 nvm-windows..."
    choco install nvm -y
    refreshenv
    
    Write-Host "  安装 Node.js $NodeVersion..."
    nvm install $NodeVersion
    nvm use $NodeVersion
    nvm alias default $NodeVersion
    
    Write-Host "  ✅ Node.js 安装完成" -ForegroundColor Green
}

# 配置 npm 镜像
npm config set registry https://registry.npmmirror.com 2>&1 | Out-Null
Write-Host "  npm 镜像已配置为淘宝源"

# 安装全局工具
npm install -g typescript@5.3.3 esbuild@0.20.0 2>&1 | Out-Null
Write-Host "  ✅ TypeScript 和 esbuild 安装完成" -ForegroundColor Green

Write-Host ""

# ============================================================================
# Step 7: 创建目录结构
# ============================================================================
Write-Host "[7/8] 创建目录结构" -ForegroundColor Yellow

$dirs = @(
    "$ProjectDir\compiler",
    "$ProjectDir\python-server",
    "$ProjectDir\scripts",
    "$ProjectDir\mcp-extension",
    "$CacheDir\pip-cache",
    "$CacheDir\npm-cache",
    "$CacheDir\torch-cache",
    "$CacheDir\huggingface-cache",
    "$CacheDir\ae-analysis\music",
    "$CacheDir\ae-analysis\clips",
    "$CacheDir\ae-analysis\match",
    "$CacheDir\temp",
    "$WorkspaceDir\AE-Projects",
    "$WorkspaceDir\Footage",
    "$WorkspaceDir\Music",
    "$WorkspaceDir\Exports"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  创建: $dir"
    }
}

# 配置环境变量
[Environment]::SetEnvironmentVariable("PIP_CACHE_DIR", "$CacheDir\pip-cache", "User")
[Environment]::SetEnvironmentVariable("TORCH_HOME", "$CacheDir\torch-cache", "User")
[Environment]::SetEnvironmentVariable("HF_HOME", "$CacheDir\huggingface-cache", "User")
[Environment]::SetEnvironmentVariable("AE_CACHE_DIR", "$CacheDir\ae-analysis", "User")
[Environment]::SetEnvironmentVariable("AE_TEMP_DIR", "$CacheDir\temp", "User")
[Environment]::SetEnvironmentVariable("AE_WORKSPACE", $WorkspaceDir, "User")

npm config set cache "$CacheDir\npm-cache" 2>&1 | Out-Null

Write-Host "  ✅ 目录结构创建完成" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 8: 验证安装
# ============================================================================
Write-Host "[8/8] 验证安装" -ForegroundColor Yellow

$passed = 0
$failed = 0

function Test-Tool {
    param([string]$Name, [string]$Command)
    
    Write-Host "  验证 $Name ... " -NoNewline
    try {
        $result = Invoke-Expression $Command 2>&1
        Write-Host "✅" -ForegroundColor Green
        $script:passed++
    } catch {
        Write-Host "❌" -ForegroundColor Red
        $script:failed++
    }
}

Test-Tool "Git" "git --version"
Test-Tool "FFmpeg" "ffmpeg -version"
Test-Tool "Node.js" "node --version"
Test-Tool "npm" "npm --version"
Test-Tool "TypeScript" "tsc --version"
Test-Tool "Python" "python --version"

conda activate $CondaEnvName
Test-Tool "numpy" "python -c 'import numpy; print(numpy.__version__)'"
Test-Tool "librosa" "python -c 'import librosa; print(librosa.__version__)'"
Test-Tool "OpenCV" "python -c 'import cv2; print(cv2.__version__)'"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  通过: $passed"
Write-Host "  失败: $failed"
Write-Host ""
Write-Host "  后续步骤："
Write-Host "  1. 安装 After Effects 2025"
Write-Host "  2. 安装 MCP Bridge 面板（参见第6章）"
Write-Host "  3. 配置 MCP 扩展工具（参见第7章）"
Write-Host "  4. 运行冒烟测试（参见第12章）"
Write-Host ""
Write-Host "  详细说明请参阅部署指南文档"
Write-Host ""
```

### A.2 使用方法与注意事项

#### A.2.1 使用方法

1. **以管理员身份打开 PowerShell**
2. **保存脚本**：将上面的脚本保存为 `deploy.ps1`
3. **执行策略**：允许脚本运行
   ```powershell
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. **运行脚本**：
   ```powershell
   .\deploy.ps1
   ```
5. **等待完成**：脚本会自动执行所有步骤
6. **后续配置**：完成后按照脚本提示进行后续手动配置

#### A.2.2 注意事项

> [!warning] 重要提醒
> 1. **网络连接**：确保网络连接稳定，建议使用代理或国内镜像
> 2. **磁盘空间**：确保 C 盘至少有 50GB 可用空间
> 3. **耐心等待**：Python 依赖安装可能需要较长时间
> 4. **分步执行**：如果某一步失败，可以注释掉已完成的步骤，从失败处继续
> 5. **手动验证**：脚本完成后，请手动运行验证步骤确认

#### A.2.3 自定义配置

可以修改脚本开头的配置变量来自定义安装路径：

```powershell
$InstallDir = "D:\Tools"       # 改成你想要的工具目录
$ProjectDir = "D:\Projects"      # 项目目录
$CacheDir = "D:\Cache"             # 缓存目录
$CondaEnvName = "my-env"           # conda 环境名
```

### A.3 常见错误与回滚方案

#### A.3.1 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| 权限不足 | 不是管理员运行 | 右键 PowerShell → 以管理员身份运行 |
| 执行策略限制 | PowerShell 默认不允许脚本运行 | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| 网络超时 | 网络连接问题 | 配置代理或使用国内镜像 |
| 磁盘空间不足 | C 盘空间不够 | 清理磁盘或修改安装路径 |
| 依赖安装失败 | 网络或兼容性问题 | 手动安装失败的包 |

#### A.3.2 回滚方案

如果部署失败或需要清理：

**完全卸载**：

```powershell
# 1. 删除 conda 环境
conda remove -n ae-ai --all

# 2. 删除项目目录
Remove-Item -Recurse -Force "C:\Projects\AE-MotionStudio"

# 3. 删除缓存目录
Remove-Item -Recurse -Force "C:\Cache"

# 4. 卸载 Chocolatey 安装的软件（可选）
# choco uninstall git ffmpeg vscode -y

# 5. 卸载 Miniconda（可选）
# & "C:\Tools\Miniconda3\Uninstall-Miniconda3.exe" /S
```

**部分回滚**：

如果只是某个组件有问题，只需要重新安装对应部分即可，不需要全部卸载。

---

## 附录B：版本兼容性矩阵

### B.1 AE 版本 × MCP 版本 × Node 版本 × Python 版本

#### B.1.1 核心组件兼容性矩阵

| AE 版本 | MCP Server 版本 | Node.js 版本 | Python 版本 | 兼容性 | 备注 |
|---------|----------------|-------------|------------|--------|------|
| **AE 2025 (25.x)** | 0.4.x | 20.x LTS | 3.11 | ✅ 完全兼容 | 推荐组合，功能最完整 |
| AE 2025 (25.x) | 0.4.x | 18.x LTS | 3.11 | ✅ 兼容 | Node 18 也可以 |
| AE 2025 (25.x) | 0.3.x | 20.x LTS | 3.11 | ⚠️ 基本兼容 | 缺少部分新功能 |
| AE 2024 (24.x) | 0.4.x | 20.x LTS | 3.11 | ✅ 完全兼容 | 功能完整 |
| AE 2024 (24.x) | 0.3.x | 18.x LTS | 3.10 | ✅ 兼容 | 稳定组合 |
| AE 2023 (23.x) | 0.4.x | 20.x LTS | 3.11 | ⚠️ 基本兼容 | 部分新效果不可用 |
| AE 2023 (23.x) | 0.3.x | 18.x LTS | 3.10 | ✅ 兼容 | 稳定但功能较少 |
| AE 2022 (22.x) | 0.3.x | 16.x LTS | 3.9 | ⚠️ 部分兼容 | 可能缺少 API |
| AE 2021 及更早 | 0.2.x | 14.x | 3.8 | ❌ 不推荐 | 太老旧 |

> [!success] 推荐组合
> **最佳推荐**：AE 2025 + MCP 0.4.x + Node.js 20 LTS + Python 3.11
>
> 这是功能最完整、测试最充分的组合。

#### B.1.2 FFmpeg 版本兼容性

| FFmpeg 版本 | Python 库兼容性 | 编码器支持 | 推荐度 |
|------------|----------------|-----------|--------|
| **6.1.x** | 完全兼容 | H.264/H.265/AV1 | ⭐⭐⭐⭐⭐ |
| 6.0.x | 完全兼容 | H.264/H.265/AV1 | ⭐⭐⭐⭐ |
| 5.1.x | 基本兼容 | H.264/H.265 | ⭐⭐⭐⭐ |
| 4.4.x | 基本兼容 | H.264/H.265 | ⭐⭐⭐ |
| 4.x 更早 | 可能有问题 | 功能较少 | ⭐⭐ |

### B.2 已知不兼容组合

#### B.2.1 明确不兼容的组合

| 组合 | 问题 | 解决方案 |
|------|------|---------|
| AE 2025 + Node.js 16.x | MCP SDK 不支持 | 升级到 Node.js 18+ |
| AE 2022 + Python 3.11 | 部分 JSX 脚本不兼容 | 使用 Python 3.9-3.10 |
| FFmpeg 3.x + librosa 0.10+ | 音频解码问题 | 升级 FFmpeg 到 5.x+ |
| Python 3.12 + madmom | madmom 不兼容 | 使用 Python 3.11 |
| Python 3.12 + 部分 OpenCV 旧版 | 编译问题 | 使用 Python 3.11 或升级 OpenCV |

#### B.2.2 Windows 版本限制

| Windows 版本 | 限制 |
|-------------|------|
| Windows 7 | ❌ 不支持（Node.js 18+ 不支持 Win7） |
| Windows 8/8.1 | ⚠️ 部分支持（可能有兼容性问题） |
| Windows 10 21H2+ | ✅ 完全支持 |
| Windows 11 22H2+ | ✅ 完全支持（推荐） |

### B.3 升级路径建议

#### B.3.1 升级顺序建议

从旧版本升级建议升级顺序：

```
升级顺序：
1. 备份当前环境
   ↓
2. 升级 Python 依赖
   ↓
3. 升级 Node.js 依赖
   ↓
4. 升级 MCP Server
   ↓
5. 升级 After Effects
   ↓
6. 测试验证
```

#### B.3.2 版本升级检查清单

升级前检查：
- [ ] 备份所有项目文件
- [ ] 导出当前 conda 环境配置
- [ ] 备份 package-lock.json
- [ ] 记录当前所有版本号
- [ ] 阅读更新日志，了解破坏性变更
- [ ] 在测试环境先升级验证

升级后验证：
- [ ] 运行冒烟测试
- [ ] 运行集成测试
- [ ] 验证核心功能正常
- [ ] 检查性能是否下降
- [ ] 更新文档

#### B.3.3 降级方案

如果升级后出现问题，可以按以下步骤降级：

**Python 环境降级**：
```powershell
# 导出当前环境（备份）
conda env export > environment_backup.yml

# 删除有问题的环境
conda remove -n ae-ai --all

# 从备份的旧配置重新创建
conda env create -f environment_old.yml
```

**Node.js 版本切换**：
```powershell
# 使用 nvm 切换版本
nvm install 18.19.0
nvm use 18.19.0

# 重新安装依赖
rm -rf node_modules
npm install
```

**MCP Server 降级**：
```powershell
# 回退到指定版本
git checkout v0.3.0

# 重新构建
npm install
npm run build
```

> [!info] 参考文档
> 更多架构信息参见 [[AE 自动化引擎架构设计]]
> MCP 协议参见 [[MCP→AE效果操作桥接规范]]

---

## 写在最后

恭喜你完成了 AI 辅助视频生成系统的全部部署工作！从 Python 环境配置到 AE MCP 桥接，从 FFmpeg 硬件加速到端到端流水线，你已经掌握了构建完整 AI 视频生成系统所需的全部技能。

部署只是开始，真正的价值在于不断优化和迭代。建议你：

1. **先跑通一次完整流程**，熟悉每个环节的输入输出
2. **记录遇到的问题和解决方案**，积累自己的知识库
3. **逐步优化性能**，从硬件加速到算法调优，持续提升效率
4. **参与社区交流**，分享经验，学习最佳实践

希望这份部署指南能帮助你顺利开启 AI 辅助视频创作的旅程。如果在部署过程中遇到问题，可以参考知识库中的其他文档，也可以在实践中不断探索和总结。

祝你创作愉快，产出更多精彩的视频作品！
