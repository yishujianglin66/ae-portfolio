# Bug修复日志

> 创建日期：2026-07-06
> 状态跟踪：记录素材获取体系发现的Bug及修复进度

---

## Bug清单

| ID | Bug名称 | 文件 | 优先级 | 状态 | 修复日期 |
|----|---------|------|--------|------|----------|
| B01 | importFootage MCP超时 | mcp-bridge-auto.jsx | 🔴 高 | ✅ 已修复 | 2026-07-19 |
| B02 | download_video文件检测错误 | media-fetcher.py | 🔴 高 | ✅ 已修复 | 2026-07-06 |
| B03 | Cookie路径不一致 | media-config.json | 🔴 高 | ✅ 已修复 | 2026-07-19 |
| B04 | generate_ae_script未声明layer | media-manager.py | 🟡 中 | ✅ 已修复 | 2026-07-19 |
| B05 | search_online虚假平台支持 | media-search.py | 🟡 中 | ✅ 已修复 | 2026-07-06 |
| B06 | FFmpeg -ss位置错误 | ffmpeg-toolkit.py | 🔴 高 | ✅ 已修复 | 2026-07-06 |
| B07 | 两套实现默认目录不一致 | path-utils.js | 🟡 中 | ✅ 已修复 | 2026-07-19 |

---

## Bug详细记录

### B01: importFootage MCP超时
- **发现场景**：2026-07-06 BGM实战演练，步骤4导入BGM到AE
- **现象**：调用MCP `import-footage`工具，Bridge返回"Unknown command: importFootage"
- **原因分析**：
  - Bridge轮询超时仅 8000ms，对于大文件导入不够
  - 无重试机制，单次失败即报错
- **修复方案**：
  1. 超时从 8000ms 增加到 30000ms（`ae-mcp-server/src/bridge.ts`）
  2. 添加 3 次重试机制（指数退避 1s/2s/3s）
  3. 轮询间隔从 200ms 调整到 500ms 减少 IO 压力
- **状态**：✅ 已修复（2026-07-19）

### B02: download_video文件检测错误
- **发现场景**：代码审查（调研报告）
- **现象**：download_video方法遍历整个output_dir查找新文件，会把旧文件也塞进结果
- **原因分析**：使用`os.listdir`遍历目录匹配扩展名，而非让yt-dlp返回下载路径
- **修复方案**：改用yt-dlp的`--print after_move:filepath`参数
- **修复代码**：
  ```python
  # 原代码（错误）
  files_before = set(os.listdir(output_dir))
  # ...执行yt-dlp...
  files_after = set(os.listdir(output_dir))
  new_files = files_after - files_before  # 会包含所有新文件，包括无关文件
  
  # 修复后代码
  cmd = [..., "--print", "after_move:filepath", ...]
  result = subprocess.run(cmd, capture_output=True)
  filepath = result.stdout.strip()  # yt-dlp直接返回下载文件路径
  ```
- **状态**：✅ 已修复（2026-07-06）

### B03: Cookie路径不一致
- **发现场景**：2026-07-06 BGM实战演练，步骤2Cookie获取
- **现象**：
  - `config/media-config.json`指向`D:/AE-Work/cookies/douyin_cookies.txt`
  - 实际文件在`c:\Users\Administrator\Desktop\AE-Knowledge-Vault\cookies\douyin_cookies.txt`
- **修复方案**：
  1. `media-config.json` 所有 cookie_path 改为项目相对路径 `./cookies/xxx_cookies.txt`
  2. `media-manager.py` 添加 `_normalize_paths()` 方法自动解析相对路径
  3. `douyin_downloader_pro.py` DEFAULT_COOKIE_PATH 改为项目内路径，回退机制增强
- **状态**：✅ 已修复（2026-07-19）

### B04: generate_ae_script未声明layer
- **发现场景**：代码审查（调研报告）
- **现象**：media-manager.py生成的AE脚本引用了未定义的`layer`变量
- **修复方案**：在生成 Gaussian Blur / Glow 效果脚本前，先声明 `var effectLayer = comp.layers.addSolid(...)`
- **状态**：✅ 已修复（2026-07-19）

### B05: search_online虚假平台支持
- **发现场景**：代码审查（调研报告）
- **现象**：media-search.py使用`dysearch/bsearch/ksearch`前缀调用yt-dlp搜索
- **原因分析**：
  - yt-dlp仅支持`ytsearch`（YouTube搜索）
  - `dysearch`/`bsearch`/`ksearch`前缀不是yt-dlp原生支持，会静默返回空
- **修复方案**：移除虚假前缀，明确标注只支持YouTube搜索，其他平台标注"coming soon"
- **修复代码**：
  ```python
  # 原代码（错误）
  if platform == "douyin":
      search_prefix = "dysearch"
  elif platform == "bilibili":
      search_prefix = "bsearch"
  
  # 修复后代码
  if platform == "youtube":
      search_prefix = "ytsearch"
  elif platform in ["douyin", "bilibili", "kuaishou"]:
      return {"success": False, "error": f"{platform}搜索暂未支持，coming soon"}
  ```
- **状态**：✅ 已修复（2026-07-06）

### B06: FFmpeg -ss位置错误
- **发现场景**：代码审查（调研报告）
- **现象**：ffmpeg-toolkit.py的extract_video_segment方法中`-ss`在`-i`之前
- **原因分析**：
  - FFmpeg参数顺序：`-ss`在`-i`之前是seek到关键帧（快但不精确）
  - `-ss`在`-i`之后是精确seek（慢但精确）
- **修复方案**：把`-ss`移到`-i`之后
- **修复代码**：
  ```python
  # 原代码（不精确）
  cmd = ["ffmpeg", "-y", "-ss", f"{start_time:.2f}", "-i", input_file, ...]
  
  # 修复后代码（精确）
  cmd = ["ffmpeg", "-y", "-i", input_file, "-ss", f"{start_time:.2f}", ...]
  ```
- **状态**：✅ 已修复（2026-07-06）

### B07: 两套实现默认目录不一致
- **发现场景**：代码审查（调研报告）
- **现象**：Python版默认`D:/AE-Work/`，Node.js版默认`os.homedir()/Downloads`
- **修复方案**：
  1. `phase7-media-tools/path-utils.js` 添加 `_loadConfig()` 统一读取 `media-config.json`
  2. `getMediaDir()` 和 `getDownloadsDir()` 优先使用配置中的路径
  3. 新建 `config/config_manager.py` 统一配置管理器，支持环境变量覆盖
- **状态**：✅ 已修复（2026-07-19）

---

## 修复验证记录

### B02验证（download_video文件检测）
- **验证方法**：读取修复后代码确认使用`--print after_move:filepath`
- **验证结果**：✅ 通过

### B05验证（search_online虚假平台）
- **验证方法**：读取修复后代码确认移除虚假前缀
- **验证结果**：✅ 通过

### B06验证（FFmpeg -ss位置）
- **验证方法**：读取修复后代码确认参数顺序
- **验证结果**：✅ 通过

---

## 暂缓Bug说明

所有 7 个 Bug 均已修复（2026-07-19 更新）：

| Bug | 修复日期 | 修复文件 |
|------|---------|----------|
| B01 | 2026-07-19 | `ae-mcp-server/src/bridge.ts` |
| B02 | 2026-07-06 | `media-fetcher.py` |
| B03 | 2026-07-19 | `config/media-config.json` + `media-manager.py` + `douyin_downloader_pro.py` |
| B04 | 2026-07-19 | `media-manager.py` |
| B05 | 2026-07-06 | `media-search.py` |
| B06 | 2026-07-06 | `ffmpeg-toolkit.py` |
| B07 | 2026-07-19 | `phase7-media-tools/path-utils.js` + `config/config_manager.py` |

---

**日志更新时间**：2026-07-20

---

## Phase D 增强记录（2026-07-20）

### D1a: SQLite 元数据库
- **新建文件**: `media_metadata_db.py`
- **功能**: 替代 JSON 文件索引，提供高效的素材元数据存储与查询
- **特性**: SQLite WAL 模式、多条件搜索、全文搜索、JSON 迁移工具、CLI 接口
- **测试**: 11 项单元测试全部通过

### D1b: FAISS 向量索引
- **新建文件**: `vector_index_faiss.py`
- **功能**: 替代 JSON 向量线性扫描，提供 O(log n) 近似最近邻检索
- **特性**: FAISS IndexFlatIP、归一化向量余弦相似度、numpy 降级方案、JSON 迁移
- **测试**: 7 项单元测试全部通过

### D2: 训练日志系统集成
- **修改文件**: `training_logger.py`
- **改动**: 硬编码路径替换为 ConfigManager、新增 PipelineLogger 类
- **特性**: 5 层管线日志记录、结构化报告生成

### D3: 自动化回归测试
- **新建文件**: `tests/test_phase_d_enhancements.py`
- **覆盖**: D1a/D1b/D2 + B03/B04/B07 修复验证
- **结果**: 27 项测试全部通过

### D4: MCP 工具扩展
- **新建文件**: `clip-search.ts`, `get-config.ts`, `library-stats.ts`
- **修改文件**: `ae-mcp-server/src/tools/index.ts`
- **功能**: CLIP 语义搜索、配置读取、素材库统计
- **MCP 工具总数**: 18 个（原有 15 + 新增 3）

### config_manager.py 修复
- **问题**: 两个实现被拼接导致 `from __future__` 语法错误
- **修复**: 合并为单一文件，保留 ConfigManager 类和函数式 API