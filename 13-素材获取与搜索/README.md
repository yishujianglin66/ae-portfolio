# 13-素材获取与搜索

> 素材获取能力体系化建设
> 创建日期：2026-07-06

## 目录结构

```
13-素材获取与搜索/
├── 01-下载器/                    # 抖音/B站/YouTube专业下载
│   ├── douyin_downloader_pro.py  # 抖音专用下载器（httpx异步）
│   ├── bilibili_downloader.py    # B站下载器（yt-dlp）
│   ├── youtube_downloader.py     # YouTube下载器（yt-dlp）
│   ├── unified_downloader.py     # 统一入口（自动平台识别）
│   └── README.md                 # 模块说明
├── 02-免费素材API/               # Pixabay/Pexels/Jamendo搜索
│   ├── pixabay_client.py         # Pixabay视频/图片API
│   ├── pexels_client.py          # Pexels视频/图片API
│   ├── jamendo_client.py         # Jamendo音乐API
│   ├── unified_search.py         # 跨平台统一搜索
│   ├── api_keys_template.json    # API密钥模板
│   └── README.md                 # 模块说明
├── 03-AI语义搜索/                # CLIP向量搜索
│   ├── frame_extractor.py        # 视频帧抽取
│   ├── clip_indexer.py           # 向量索引构建
│   ├── clip_searcher.py          # 语义搜索引擎
│   ├── vector_store.py           # 向量存储管理
│   └── README.md                 # 模块说明
└── 04-实战报告/                  # 经验储备
    ├── 2026-07-06-BGM实战检讨报告.md
    ├── bug_fix_log.md            # Bug修复日志
    └── README.md                 # 模块说明
```

## 模块能力

### 01-下载器
| 平台 | 下载器 | 特性 |
|------|--------|------|
| 抖音 | `douyin_downloader_pro.py` | httpx直连API、无水印、Cookie管理、音频提取 |
| B站 | `bilibili_downloader.py` | yt-dlp、画质选择、音频分离、收藏夹批量 |
| YouTube | `youtube_downloader.py` | yt-dlp、搜索、字幕、代理支持 |
| 统一入口 | `unified_downloader.py` | 自动平台识别、路由分发 |

### 02-免费素材API
| 平台 | API | 内容类型 | 限制 |
|------|-----|---------|------|
| Pixabay | `pixabay_client.py` | 视频/图片/音乐 | 100 req/h |
| Pexels | `pexels_client.py` | 视频/图片 | 200 req/h |
| Jamendo | `jamendo_client.py` | 音乐 | 无明确限制 |
| 统一入口 | `unified_search.py` | 跨平台并行搜索 | - |

### 03-AI语义搜索
| 功能 | 模块 | 技术 |
|------|------|------|
| 帧抽取 | `frame_extractor.py` | OpenCV、场景检测 |
| 索引构建 | `clip_indexer.py` | CLIP-ViT-L-14、512维向量 |
| 语义搜索 | `clip_searcher.py` | 余弦相似度、中英双语 |
| 向量存储 | `vector_store.py` | JSON存储、增量更新 |

## 快速使用

### 1. 抖音BGM下载
```bash
python 01-下载器/unified_downloader.py --json-input '{"func": "download_bgm", "params": {"url": "https://v.douyin.com/xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}'
```

### 2. 免费素材搜索
```bash
python 02-免费素材API/unified_search.py --json-input '{"func": "search_videos", "params": {"query": "夕阳海滩", "per_page": 10}}'
```

### 3. AI语义搜索
```bash
# 构建索引
python 03-AI语义搜索/clip_indexer.py --json-input '{"func": "build_index", "params": {"media_directory": "D:/AE-Work/视频素材库", "output_path": "D:/AE-Work/向量索引/index.json"}}'

# 语义搜索
python 03-AI语义搜索/clip_searcher.py --json-input '{"func": "search", "params": {"query": "激烈的战斗场景", "index_path": "D:/AE-Work/向量索引/index.json"}}'
```

## 配置要求

### Cookie配置
- 路径：`D:/AE-Work/cookies/douyin_cookies.txt`
- 格式：Netscape格式（yt-dlp兼容）
- 关键字段：ttwid、sessionid

### API密钥配置
- 复制`02-免费素材API/api_keys_template.json`为`api_keys.json`
- 填入真实API密钥：
  - Pixabay：https://pixabay.com/api/docs/
  - Pexels：https://www.pexels.com/api/
  - Jamendo：https://developer.jamendo.com/v3.0

### AI模型配置
- 模型：`clip-ViT-L-14`（首次加载约1GB）
- 支持CPU模式（降速但可用）
- 索引目录：`D:/AE-Work/向量索引/`

## 设计文档

详见：[docs/superpowers/specs/2026-07-06-素材获取与搜索体系设计-design.md](../docs/superpowers/specs/2026-07-06-素材获取与搜索体系设计-design.md)

## Phase8报告

详见：[03-阶段报告/Phase8-素材获取体系/PHASE8_MAIN_REPORT.md](../03-阶段报告/Phase8-素材获取体系/PHASE8_MAIN_REPORT.md)

---

**创建时间**：2026-07-06