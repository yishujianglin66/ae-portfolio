# Phase8 素材获取体系建设报告

> 报告日期：2026-07-06
> 版本：v1.0
> 状态：已完成

## 一、项目背景

基于2026-07-06 BGM实战演练（提取抖音"思响的作品-世上无难事"BGM），暴露现有素材获取体系7个关键缺陷，启动Phase8素材获取体系全面建设。

### 暴露的核心问题
1. Cookie获取曲折耗时15分钟（5次失败尝试）
2. MCP工具import-footage超时（executeAtomScript可靠）
3. librosa音频分析卡死超过60秒
4. 缺少抖音专用下载器（依赖yt-dlp不够稳定）
5. 缺少免费素材API（无法搜索替代BGM）
6. 缺少AI语义搜索（手动匹配效率低）
7. 两套实现路径配置不一致

## 二、建设目标

构建**模块化、可扩展、原子级精度**的素材获取与搜索体系，使AE-Knowledge-Vault具备：

| 目标 | 说明 | 优先级 |
|------|------|--------|
| 抖音/B站/YouTube专业下载 | 替换简陋的douyin-downloader.py | P0 |
| 免费素材API集成 | Pixabay/Pexels/Jamendo三平台搜索 | P1 |
| AI语义素材搜索 | CLIP向量索引+自然语言查询 | P2 |
| 完整实战演练经验库 | 实验报告、日志、训练产出 | P1 |

## 三、建设成果

### 3.1 目录结构

```
13-素材获取与搜索/
├── 01-下载器/           ✅ 4个Python文件
├── 02-免费素材API/      ✅ 5个文件（含API密钥模板）
├── 03-AI语义搜索/       ✅ 4个Python文件
└── 04-实战报告/         ✅ 2个Markdown文件
```

### 3.2 代码清单

| 子项目 | 文件数 | 代码量 | 状态 |
|--------|--------|--------|------|
| 01-下载器 | 4 | ~1930行 | ✅ 完成 |
| 02-免费素材API | 5 | ~1800行 | ✅ 完成 |
| 03-AI语义搜索 | 4 | ~1703行 | ✅ 完成 |
| 04-实战报告 | 2 | ~600行Markdown | ✅ 完成 |

### 3.3 功能清单

#### 01-下载器模块

| 文件 | 核心功能 | 技术栈 |
|------|---------|--------|
| `douyin_downloader_pro.py` | 短链接解析、无水印下载、Cookie管理、音频提取 | httpx异步 |
| `bilibili_downloader.py` | 视频下载、音频分离、收藏夹批量 | yt-dlp |
| `youtube_downloader.py` | 视频下载、搜索、字幕下载、代理支持 | yt-dlp |
| `unified_downloader.py` | 自动平台识别、路由分发 | importlib延迟加载 |

#### 02-免费素材API模块

| 文件 | 核心功能 | API端点 |
|------|---------|--------|
| `pixabay_client.py` | 视频/图片搜索、下载 | `pixabay.com/api/videos/` |
| `pexels_client.py` | 视频/图片搜索、热门获取 | `api.pexels.com/videos/` |
| `jamendo_client.py` | 音乐搜索、按情绪/曲风筛选、下载 | `api.jamendo.com/v3.0/tracks` |
| `unified_search.py` | 跨平台并行搜索、去重、统一返回格式 | ThreadPoolExecutor |

#### 03-AI语义搜索模块

| 文件 | 核心功能 | 技术栈 |
|------|---------|--------|
| `frame_extractor.py` | 等间隔帧抽取、场景检测关键帧 | OpenCV |
| `clip_indexer.py` | 索引构建、增量更新、批处理 | sentence-transformers |
| `clip_searcher.py` | 自然语言搜索、以图搜图、标签搜索 | CLIP余弦相似度 |
| `vector_store.py` | 索引读写、合并、验证、清理 | JSON存储 |

#### 04-实战报告模块

| 文件 | 内容 |
|------|------|
| `2026-07-06-BGM实战检讨报告.md` | 7步完整时间线、成功经验、失败教训、7个Bug清单 |
| `bug_fix_log.md` | Bug状态跟踪（已修复3个、暂缓4个） |

## 四、技术亮点

### 4.1 抖音专用下载器
- **httpx异步直连**：不依赖yt-dlp，避免GPL传染风险
- **无水印技术**：`playwm → play` URL替换
- **Cookie自动管理**：验证关键字段（ttwid）、路径回退机制

### 4.2 跨平台素材搜索
- **并行调用**：ThreadPoolExecutor并行请求三个API
- **智能去重**：difflib.SequenceMatcher标题相似度（阈值0.85）
- **客户端节流**：保留1小时窗口时间戳，避免超限

### 4.3 CLIP语义搜索
- **多语言支持**：clip-ViT-L-14模型支持中文查询
- **增量索引**：只计算新文件，避免全量重建
- **失效清理**：自动检测并移除不存在文件的索引项

## 五、协议合规

| 项目 | 协议 | 集成方式 | 合规风险 |
|------|------|---------|---------|
| yt-dlp | Unlicense | pip安装 | ✅ 无风险 |
| httpx | BSD-3 | pip安装 | ✅ 无风险 |
| TikTokDownloader | GPL-3.0 | 参考思路独立实现 | ✅ 无代码引用 |
| sentence-transformers | Apache-2.0 | pip安装 | ✅ 无风险 |
| Pixabay/Pexels/Jamendo | ToS | REST调用 | ✅ 无风险 |

## 六、配置更新

### media-config.json新增字段
```json
{
  "api_keys": {
    "pixabay": "YOUR_PIXABAY_API_KEY",
    "pexels": "YOUR_PEXELS_API_KEY",
    "jamendo": "YOUR_JAMENDO_CLIENT_ID"
  },
  "ai_search": {
    "enabled": true,
    "model": "clip-ViT-L-14",
    "index_path": "D:/AE-Work/向量索引/vector_index.json"
  },
  "platforms": {
    "douyin": {"use_pro_downloader": true},
    "bilibili": {"use_bilix": false, "use_yt_dlp": true}
  }
}
```

## 七、使用指南

### 7.1 抖音BGM下载
```bash
python 13-素材获取与搜索/01-下载器/unified_downloader.py --json-input '{"func": "download_bgm", "params": {"url": "https://v.douyin.com/xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}'
```

### 7.2 免费素材搜索
```bash
python 13-素材获取与搜索/02-免费素材API/unified_search.py --json-input '{"func": "search_all", "params": {"query": "夕阳海滩", "media_type": "video"}}'
```

### 7.3 AI语义搜索
```bash
# 构建索引
python 13-素材获取与搜索/03-AI语义搜索/clip_indexer.py --json-input '{"func": "build_index", "params": {"media_directory": "D:/AE-Work/视频素材库", "output_path": "D:/AE-Work/向量索引/index.json"}}'

# 搜索
python 13-素材获取与搜索/03-AI语义搜索/clip_searcher.py --json-input '{"func": "search", "params": {"query": "激烈的战斗场景", "index_path": "D:/AE-Work/向量索引/index.json"}}'
```

## 八、下一步计划

### 短期（本周）
1. ✅ 验证抖音下载器（真实抖音链接测试）
2. ⏳ 申请免费API密钥（Pixabay/Pexels/Jamendo）
3. ⏳ 修复暂缓的4个Bug（B01/B03/B04/B07）

### 中期（本月）
4. ⏳ 构建素材库向量索引（利威尔素材库）
5. ⏳ 验证AI语义搜索效果
6. ⏳ 集成到TRAE Skill体系

### 长期（下月）
7. ⏳ 引入essentia替代librosa（工业级音频分析）
8. ⏳ 建立训练日志系统（每次实战自动生成报告）
9. ⏳ 构建素材库元数据库（持久化缓存）

## 九、建设总结

| 指标 | 数值 |
|------|------|
| 新增代码文件 | 13个Python + 3个Markdown + 1个JSON |
| 新增代码量 | ~5433行 |
| 新增功能 | 下载器4平台 + 搜索API3平台 + AI语义搜索 |
| Bug修复 | 3个已修复 + 4个暂缓 |
| 设计文档 | 1个完整设计文档 |

---

**报告生成时间**：2026-07-06 21:20
**Phase8状态**：✅ 已完成