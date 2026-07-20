# Silhouette 多软件协作流程

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: Silhouette+AE+Nuke+Premiere 协作、文件格式、版本控制完整说明。

## 目录
1. [协作概述](#1-协作概述)
2. [软件分工](#2-软件分工)
3. [文件格式标准](#3-文件格式标准)
4. [版本控制](#4-版本控制)
5. [协作工作流](#5-协作工作流)
6. [数据传递规范](#6-数据传递规范)
7. [自动化协作](#7-自动化协作)
8. [最佳实践](#8-最佳实践)

---

## 1. 协作概述

### 1.1 多软件协作的必要性

现代 VFX 制作涉及多个专业软件,每个软件有其优势领域,协作是必然选择。

### 1.2 协作挑战

| 挑战 | 说明 | 解决方案 |
|------|------|----------|
| 格式兼容 | 不同软件支持不同格式 | 统一交换格式 |
| 坐标系差异 | Y轴方向不同 | 转换工具 |
| 色彩空间 | 不同色彩管理 | 统一色彩管线 |
| 版本管理 | 多人修改文件 | 版本控制系统 |
| 数据丢失 | 软件间传递丢失信息 | 完整元数据 |

### 1.3 协作架构

```
                    ┌─────────────┐
                    │  Premiere   │ ← 剪辑、最终输出
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ After Effects│ ← 合成、特效
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌─────▼─────┐ ┌───────▼───────┐
    │ Silhouette  │ │   Nuke    │ │    其他工具    │
    │ Roto/Paint  │ │  高级合成  │ │  3D/音频/等   │
    └─────────────┘ └───────────┘ └───────────────┘
```

## 2. 软件分工

### 2.1 各软件职责

| 软件 | 主要职责 | 输出 | 接收 |
|------|----------|------|------|
| Silhouette | Roto、Paint、跟踪 | Matte序列、跟踪数据 | 原始素材 |
| After Effects | 合成、动效、特效 | 合成结果、动态链接 | Matte、素材 |
| Nuke | 高级合成、3D合成 | 合成结果 | Matte、3D渲染 |
| Premiere | 剪辑、调色、输出 | 最终视频 | 合成结果 |

### 2.2 任务分配原则

```
需要 Roto? → Silhouette
需要 Paint 修复? → Silhouette
需要跟踪? → Silhouette(2D) 或 3D 软件(3D)
需要合成? → AE(简单) 或 Nuke(复杂)
需要剪辑? → Premiere
需要最终输出? → Premiere 或 AE
```

## 3. 文件格式标准

### 3.1 交换格式选择

| 数据类型 | 推荐格式 | 备选 | 说明 |
|----------|----------|------|------|
| 图像序列 | EXR | TIFF/DPX | 无损、多通道 |
| 视频 | ProRes | DNxHR | 高质量 |
| 遮罩 | EXR(Alpha) | PNG | 含 Alpha |
| 跟踪数据 | JSON | TXT | 结构化 |
| 项目文件 | 原生格式 | XML | 软件特定 |
| 元数据 | JSON | XML | 通用 |

### 3.2 命名规范

```
全局命名规范:
[项目]_[镜头]_[类型]_[对象]_[版本]_[帧号].[扩展名]

示例:
PROJ001_SH0100_PLATE_original_v01_0001.exr
PROJ001_SH0100_MATTE_character_v02_0001.exr
PROJ001_SH0100_TRACK_face_v01.json
PROJ001_SH0100_COMP_final_v03_0001.exr
```

### 3.3 目录结构

```
/project_root/
  /00_admin/           # 管理文件
    /contracts/
    /schedules/
  /01_source/          # 原始素材
    /footage/
    /audio/
    /references/
  /02_silhouette/      # Silhouette 工作
    /projects/
    /exports/
      /mattes/
      /tracks/
      /paints/
  /03_ae/              # After Effects 工作
    /projects/
    /renders/
  /04_nuke/            # Nuke 工作
    /scripts/
    /renders/
  /05_premiere/        # Premiere 工作
    /projects/
    /exports/
  /06_delivery/        # 交付
    /v01/
    /v02/
    /final/
  /07_archive/         # 归档
```

## 4. 版本控制

### 4.1 版本号规范

```
版本号格式:v[主版本].[次版本]

主版本:重大修改
次版本:小修改

示例:
v1.0 — 初始版本
v1.1 — 小修改
v2.0 — 重大修改
```

### 4.2 版本管理策略

```python
class VersionManager:
    """版本管理器"""
    
    def __init__(self, project_root):
        self.project_root = project_root
    
    def create_version(self, task, version_num, files):
        """创建新版本"""
        import os
        import shutil
        
        version_dir = os.path.join(
            self.project_root,
            f"v{version_num:02d}"
        )
        os.makedirs(version_dir, exist_ok=True)
        
        # 复制文件
        for src in files:
            dst = os.path.join(version_dir, os.path.basename(src))
            shutil.copy2(src, dst)
        
        # 创建版本信息
        info = {
            "version": version_num,
            "task": task,
            "created": "2026-07-11",
            "files": [os.path.basename(f) for f in files]
        }
        
        import json
        with open(os.path.join(version_dir, "version_info.json"), "w") as f:
            json.dump(info, f, indent=2)
        
        return version_dir
    
    def get_latest_version(self, task):
        """获取最新版本"""
        import os
        versions = []
        
        for item in os.listdir(self.project_root):
            if item.startswith("v") and item[1:].isdigit():
                versions.append(int(item[1:]))
        
        return max(versions) if versions else 0
    
    def compare_versions(self, v1, v2):
        """对比两个版本"""
        # 返回差异
        pass
```

### 4.3 Git 集成

```python
class GitIntegration:
    """Git 版本控制集成"""
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
    
    def commit_version(self, message, files=None):
        """提交版本"""
        import subprocess
        
        if files:
            for f in files:
                subprocess.run(
                    ["git", "add", f],
                    cwd=self.repo_path
                )
        else:
            subprocess.run(
                ["git", "add", "."],
                cwd=self.repo_path
            )
        
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_path
        )
    
    def create_tag(self, version, message=""):
        """创建版本标签"""
        import subprocess
        subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", message],
            cwd=self.repo_path
        )
```

## 5. 协作工作流

### 5.1 标准 VFX 协作流程

```
1. 剪辑(Premiere)
   ↓ 输出 EDL/XML + 代理视频
2. 镜头分配
   ↓ 每个镜头分配给艺术家
3. Roto/Silhouette
   ↓ 输出 Matte 序列
4. 跟踪/Silhouette
   ↓ 输出跟踪数据
5. 合成/AE 或 Nuke
   ↓ 接收 Matte + 跟踪
   ↓ 输出合成结果
6. 审核
   ↓ 反馈或通过
7. 最终输出/Premiere
   ↓ 嵌入剪辑
8. 交付
```

### 5.2 Silhouette 在协作中的角色

```python
class SilhouetteCollaboration:
    """Silhouette 协作工具"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.silhouette_dir = os.path.join(project_root, "02_silhouette")
    
    def receive_from_edit(self, edit_data):
        """从剪辑接收镜头信息"""
        # 解析 EDL/XML
        shots = parse_edit_data(edit_data)
        
        # 为每个镜头创建 Silhouette 项目
        for shot in shots:
            self.create_shot_project(shot)
        
        return shots
    
    def create_shot_project(self, shot):
        """为镜头创建 Silhouette 项目"""
        from fx import *
        
        project = Project()
        session = Session()
        session.label = shot["id"]
        project.addItem(session)
        
        # 设置参数
        session.width = shot["width"]
        session.height = shot["height"]
        session.frameRate = shot["frame_rate"]
        
        # 保存项目
        project_path = os.path.join(
            self.silhouette_dir, "projects", f"{shot['id']}.sfx"
        )
        project.save(project_path)
        
        return project_path
    
    def export_for_compositor(self, shot_id, output_type="all"):
        """为合成师导出数据"""
        shot_dir = os.path.join(self.silhouette_dir, "exports", shot_id)
        
        exports = {}
        
        if output_type in ("all", "matte"):
            exports["matte"] = os.path.join(shot_dir, "mattes")
        
        if output_type in ("all", "track"):
            exports["track"] = os.path.join(shot_dir, "tracks")
        
        if output_type in ("all", "paint"):
            exports["paint"] = os.path.join(shot_dir, "paints")
        
        return exports
    
    def deliver_to_compositor(self, shot_id, compositor="ae"):
        """交付给合成师"""
        exports = self.export_for_compositor(shot_id)
        
        # 根据合成软件生成接收说明
        if compositor == "ae":
            instructions = self.generate_ae_instructions(exports)
        elif compositor == "nuke":
            instructions = self.generate_nuke_instructions(exports)
        
        return exports, instructions
```

### 5.3 审核与反馈流程

```python
class ReviewSystem:
    """审核系统"""
    
    def __init__(self):
        self.reviews = []
    
    def submit_for_review(self, shot_id, version, artist, file_path):
        """提交审核"""
        review = {
            "shot_id": shot_id,
            "version": version,
            "artist": artist,
            "file": file_path,
            "status": "pending",
            "submitted": "2026-07-11",
            "feedback": None
        }
        self.reviews.append(review)
        return review
    
    def add_feedback(self, shot_id, version, feedback, status="changes"):
        """添加反馈"""
        for review in self.reviews:
            if review["shot_id"] == shot_id and review["version"] == version:
                review["feedback"] = feedback
                review["status"] = status
                return review
        return None
    
    def get_pending(self):
        """获取待审核"""
        return [r for r in self.reviews if r["status"] == "pending"]
    
    def get_approved(self):
        """获取已通过"""
        return [r for r in self.reviews if r["status"] == "approved"]
```

## 6. 数据传递规范

### 6.1 元数据标准

```python
def create_metadata(shot_id, task, artist, version):
    """创建标准元数据"""
    return {
        "project": "PROJ001",
        "shot": shot_id,
        "task": task,
        "artist": artist,
        "version": version,
        "created": "2026-07-11",
        "software": "silhouette",
        "frame_rate": 24,
        "resolution": [1920, 1080],
        "colorspace": "acescg"
    }

def embed_metadata(output_node, metadata):
    """嵌入元数据到输出"""
    import json
    metadata_str = json.dumps(metadata)
    
    # 设置到输出节点的元数据属性
    prop = output_node.property("metadata")
    if prop:
        prop.setValue(metadata_str, 0)
```

### 6.2 传递清单

```python
class DeliveryManifest:
    """交付清单"""
    
    def __init__(self):
        self.items = []
    
    def add_item(self, name, path, type, description=""):
        """添加交付项"""
        self.items.append({
            "name": name,
            "path": path,
            "type": type,
            "description": description
        })
    
    def to_json(self, output_path):
        """导出为 JSON"""
        import json
        manifest = {
            "manifest_version": "1.0",
            "created": "2026-07-11",
            "items": self.items
        }
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    def validate(self):
        """验证所有文件存在"""
        import os
        missing = []
        for item in self.items:
            if not os.path.exists(item["path"]):
                missing.append(item["name"])
        return missing

# 使用
manifest = DeliveryManifest()
manifest.add_item("character_matte", "/exports/mattes/character/", "sequence")
manifest.add_item("track_data", "/exports/tracks/track.json", "data")
manifest.add_item("painted_plate", "/exports/paints/plate_v01.mov", "video")
manifest.to_json("/exports/manifest.json")
```

## 7. 自动化协作

### 7.1 自动化流水线

```python
class CollaborationPipeline:
    """自动化协作流水线"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.steps = []
    
    def add_step(self, name, software, action):
        """添加流水线步骤"""
        self.steps.append({
            "name": name,
            "software": software,
            "action": action
        })
    
    def run(self, shot_id):
        """运行流水线"""
        results = {}
        
        for step in self.steps:
            print(f"执行: {step['name']} ({step['software']})")
            
            try:
                result = step["action"](shot_id, self.project_root)
                results[step["name"]] = {"status": "success", "result": result}
            except Exception as e:
                results[step["name"]] = {"status": "failed", "error": str(e)}
                break
        
        return results

# 定义流水线
pipeline = CollaborationPipeline("/project_root")
pipeline.add_step("roto", "silhouette", run_roto)
pipeline.add_step("track", "silhouette", run_tracking)
pipeline.add_step("composite", "nuke", run_composite)
pipeline.add_step("edit", "premiere", run_edit)
```

### 7.2 状态同步

```python
class StatusSync:
    """状态同步"""
    
    def __init__(self, shared_state_file):
        self.state_file = shared_state_file
    
    def update_status(self, shot_id, task, status, artist=None):
        """更新状态"""
        import json
        import os
        
        state = {}
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                state = json.load(f)
        
        if shot_id not in state:
            state[shot_id] = {}
        
        state[shot_id][task] = {
            "status": status,
            "artist": artist,
            "updated": "2026-07-11"
        }
        
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def get_status(self, shot_id=None):
        """获取状态"""
        import json
        import os
        
        if not os.path.exists(self.state_file):
            return {}
        
        with open(self.state_file, "r") as f:
            state = json.load(f)
        
        if shot_id:
            return state.get(shot_id, {})
        return state
```

## 8. 最佳实践

### 8.1 协作原则

1. **明确分工**:每个软件负责明确任务
2. **统一格式**:全流程使用统一交换格式
3. **版本控制**:所有输出都有版本号
4. **及时同步**:状态变更及时通知
5. **文档齐全**:每个步骤有操作文档

### 8.2 文件管理

| 原则 | 说明 |
|------|------|
| 只读源文件 | 原始素材不修改 |
| 独立输出目录 | 每个软件独立输出 |
| 命名一致 | 全项目统一命名 |
| 定期清理 | 清理中间文件 |
| 备份重要版本 | 关键版本多重备份 |

### 8.3 沟通规范

```
任务交接清单:
□ 任务描述明确
□ 文件路径完整
□ 版本号正确
□ 帧范围一致
□ 色彩空间标注
□ 特殊要求说明
□ 截止时间明确
```

### 8.4 质量控制

```python
def qc_check(shot_id, deliverables):
    """质量控制检查"""
    issues = []
    
    for item in deliverables:
        # 检查文件存在
        if not os.path.exists(item["path"]):
            issues.append(f"{item['name']}: 文件不存在")
            continue
        
        # 检查帧数
        if item["type"] == "sequence":
            frame_count = count_files(item["path"])
            expected = item.get("expected_frames")
            if expected and frame_count != expected:
                issues.append(f"{item['name']}: 帧数不匹配")
        
        # 检查分辨率
        # 检查色彩空间
        # 检查命名规范
    
    return issues
```

---

## 附录:软件间数据流

```
Premiere (剪辑)
    ↓ EDL/XML + 代理
Silhouette (Roto/Paint/Track)
    ↓ EXR(Matte) + JSON(Track)
Nuke/AE (合成)
    ↓ EXR(合成结果)
Premiere (最终输出)
    ↓ MP4/MOV
交付
```

| 传递 | 格式 | 说明 |
|------|------|------|
| Premiere → Silhouette | XML + 代理 | 镜头信息 |
| Silhouette → Nuke | EXR + JSON | Matte + 跟踪 |
| Silhouette → AE | EXR + TXT | Matte + 跟踪 |
| Nuke → Premiere | EXR/MOV | 合成结果 |
| AE → Premiere | 动态链接/MOV | 合成结果 |

> **提示**:多软件协作最重要的是统一规范。在项目启动阶段,所有参与方应共同确定格式、命名、色彩空间等标准,避免后期混乱。
