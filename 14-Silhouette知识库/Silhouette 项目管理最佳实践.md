# Silhouette 项目管理最佳实践

> 分类: 故障排查
> 更新日期: 2026-07-11
> 概述: 系统讲解 Silhouette 项目组织、文件命名、版本控制、备份策略与交付流程的最佳实践

## 目录
---

- [一、项目组织结构](#一项目组织结构)
- [二、文件命名规范](#二文件命名规范)
- [三、版本控制](#三版本控制)
- [四、备份策略](#四备份策略)
- [五、交付流程](#五交付流程)
- [六、自动化管理脚本](#六自动化管理脚本)
- [七、项目管理检查清单](#七项目管理检查清单)

---

## 一、项目组织结构

### 1.1 标准项目目录结构

```
PROJECT_NAME/
├── 01_资料/                         # 项目资料
│   ├── brief/                       # 项目简报
│   ├── reference/                   # 参考资料
│   │   ├── roto_reference/          # Roto 参考视频
│   │   ├── paint_reference/         # Paint 参考图片
│   │   └── style_guide/             # 风格指南
│   └── client_feedback/             # 客户反馈
│
├── 02_素材/                         # 原始素材
│   ├── plates/                      # 原始 plate
│   │   ├── seq010/                  # 按序列组织
│   │   └── seq020/
│   ├── luts/                        # LUT 文件
│   └── metadata/                    # 素材元数据
│
├── 03_工作文件/                     # Silhouette 工作文件
│   ├── seq010/
│   │   ├── sh010/                   # 按镜头组织
│   │   │   ├── sh010_roto_v001.sfx
│   │   │   ├── sh010_roto_v002.sfx
│   │   │   └── sh010_paint_v001.sfx
│   │   └── sh020/
│   └── seq020/
│
├── 04_输出/                         # 渲染输出
│   ├── seq010/
│   │   ├── sh010/
│   │   │   ├── roto/                # Roto 遮罩序列
│   │   │   ├── paint/               # Paint 结果
│   │   │   └── tracking/            # 跟踪数据
│   │   └── sh020/
│   └── seq020/
│
├── 05_交付/                         # 交付文件
│   ├── v001/                        # 交付版本
│   ├── v002/
│   └── final/
│
├── 06_归档/                         # 项目归档
│   ├── project_archive.zip          # 项目文件归档
│   └── delivery_archive.zip         # 交付归档
│
└── 99_临时/                         # 临时文件
    ├── scratch/                     # 临时工作
    └── trash/                       # 回收站
```

### 1.2 目录设计原则

**原则一：按序列/镜头组织**
- 顶层按序列（Sequence）划分
- 二层按镜头（Shot）划分
- 三层按任务（Task）划分

**原则二：编号清晰**
- 序列：`seq010`, `seq020`, `seq030`...
- 镜头：`sh010`, `sh020`, `sh030`...
- 版本：`v001`, `v002`, `v003`...

**原则三：功能分区**
- 素材、工作、输出、交付分离
- 临时文件单独区域
- 归档文件独立存放

### 1.3 大型项目优化

对于 500+ 镜头的大型项目，建议：

```
PROJECT_NAME/
├── seq001-050/      # 每 50 个序列一个分区
├── seq051-100/
├── seq101-150/
└── ...
```

---

## 二、文件命名规范

### 2.1 标准命名格式

**项目文件**：
```
[项目]_[序列]_[镜头]_[任务]_v[版本].sfx
```

示例：`AVTR_SEQ010_SH0140_roto_v003.sfx`

**输出序列**：
```
[项目]_[序列]_[镜头]_[任务]_v[版本].[帧号].[扩展名]
```

示例：`AVTR_SEQ010_SH0140_roto_v003.0001.exr`

**跟踪数据**：
```
[项目]_[序列]_[镜头]_track_v[版本].json
```

### 2.2 命名规则

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 项目 | 4-6 大写字母 | AVTR | 项目代号 |
| 序列 | SEQ+3位数字 | SEQ010 | 序列编号 |
| 镜头 | SH+4位数字 | SH0140 | 镜头编号 |
| 任务 | 小写英文 | roto/paint/track/final | 任务类型 |
| 版本 | v+3位数字 | v003 | 版本号 |
| 帧号 | 4位数字 | 0001 | 帧编号（补零） |

### 2.3 任务类型代码

| 代码 | 含义 |
|------|------|
| `roto` | Rotoscoping |
| `paint` | Paint 修复 |
| `track` | 跟踪 |
| `key` | 抠像 |
| `comp` | 合成 |
| `final` | 最终版本 |
| `wip` | 工作中 |
| `review` | 待审查 |

### 2.4 自动化命名脚本

```python
import os
from fx import *

class ShotNamer:
    """镜头命名工具"""

    def __init__(self, project_code="PROJ"):
        self.project_code = project_code

    def generate_name(self, seq, shot, task, version, ext="exr", frame=None):
        """生成标准文件名"""
        name = f"{self.project_code}_SEQ{seq:03d}_SH{shot:04d}_{task}_v{version:03d}"

        if frame is not None:
            name += f".{frame:04d}"

        name += f".{ext}"
        return name

    def generate_path(self, base_dir, seq, shot, task, version, ext="exr", frame=None):
        """生成标准路径"""
        filename = self.generate_name(seq, shot, task, version, ext, frame)
        path = os.path.join(
            base_dir,
            f"seq{seq:03d}",
            f"sh{shot:04d}",
            task,
            filename
        )
        return path.replace("\\", "/")

# 使用
namer = ShotNamer("AVTR")
print(namer.generate_name(10, 140, "roto", 3, "exr", 1))
# 输出: AVTR_SEQ010_SH0140_roto_v003.0001.exr

print(namer.generate_path("D:/output", 10, 140, "roto", 3))
# 输出: D:/output/seq010/sh0140/roto/AVTR_SEQ010_SH0140_roto_v003.exr
```

---

## 三、版本控制

### 3.1 版本号规则

**主版本号**：`v001, v002, v003...`
- 每次重大修改递增
- QC 后的修改递增
- 客户反馈后的修改递增

**次版本号**：`v001.1, v001.2...`
- 小幅调整
- 内部迭代
- 不影响主版本

### 3.2 版本管理策略

```
v001（初版）
    ↓ Artist QC
v002（自检后修改）
    ↓ Lead QC
v003（Lead 审查后修改）
    ↓ Supervisor QC
v004（总监审查后修改）
    ↓ 客户审查
v005（客户反馈后修改）
    ↓ 最终批准
final_v001（最终版）
```

### 3.3 版本对比

```python
import os
from fx import *

class VersionComparator:
    """版本对比工具"""

    @staticmethod
    def compare_versions(session, version_a, version_b):
        """对比两个版本的差异"""
        # 实现版本对比逻辑
        differences = {
            "node_count": 0,
            "property_changes": [],
            "shape_changes": []
        }

        # 加载版本A
        proj_a = Project()
        proj_a.load(version_a)
        sess_a = proj_a.item(0)

        # 加载版本B
        proj_b = Project()
        proj_b.load(version_b)
        sess_b = proj_b.item(0)

        # 对比节点数
        differences["node_count"] = sess_b.numNodes - sess_a.numNodes

        # 对比属性
        for i in range(min(sess_a.numNodes, sess_b.numNodes)):
            node_a = sess_a.node(i)
            node_b = sess_b.node(i)

            for prop_name in node_a.properties:
                val_a = node_a.property(prop_name).value
                val_b = node_b.property(prop_name).value
                if val_a != val_b:
                    differences["property_changes"].append({
                        "node": node_a.label,
                        "property": prop_name,
                        "old": val_a,
                        "new": val_b
                    })

        return differences
```

### 3.4 Git LFS 集成

**.gitattributes**：
```
*.sfx filter=lfs diff=lfs merge=lfs -text
*.exr filter=lfs diff=lfs merge=lfs -text
*.dpx filter=lfs diff=lfs merge=lfs -text
*.mov filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
```

**.gitignore**：
```
# 临时文件
99_临时/
*.tmp
*.bak

# 缓存
.cache/
*.pyc

# 大文件（使用 LFS）
*.exr
*.dpx
```

### 3.5 提交规范

**提交信息格式**：
```
[类型] [镜头] 描述

[可选正文]
```

**类型**：
- `feat`：新功能
- `fix`：修复
- `roto`：Roto 工作
- `paint`：Paint 工作
- `track`：跟踪工作
- `qc`：QC 修改
- `docs`：文档

**示例**：
```
[roto] [SH0140] 完成角色 Roto v003

- 修复第 45-50 帧头发边缘
- 增加运动模糊处理
- 通过 Lead QC
```

---

## 四、备份策略

### 4.1 3-2-1 备份原则

- **3** 份数据副本
- **2** 种不同存储介质
- **1** 份异地备份

### 4.2 备份层级

```
工作盘（NVMe）
    ↓ 实时同步
本地备份（HDD）
    ↓ 每日
异地备份（NAS/云）
    ↓ 每周
冷存储（LTO 磁带）
```

### 4.3 自动备份脚本

```python
import os
import shutil
import datetime
import hashlib
from fx import *

class ProjectBackup:
    """项目备份工具"""

    def __init__(self, project_dir, backup_root="D:/backups"):
        self.project_dir = project_dir
        self.backup_root = backup_root

    def backup(self, label=""):
        """执行备份"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{os.path.basename(self.project_dir)}_{timestamp}"
        if label:
            backup_name += f"_{label}"

        backup_path = os.path.join(self.backup_root, backup_name)

        # 复制文件
        shutil.copytree(self.project_dir, backup_path)

        # 生成校验文件
        self._generate_checksum(backup_path)

        # 记录备份日志
        self._log_backup(backup_path, label)

        print(f"备份完成: {backup_path}")
        return backup_path

    def _generate_checksum(self, path):
        """生成校验文件"""
        checksum_file = os.path.join(path, "checksum.md5")
        with open(checksum_file, "w") as f:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file == "checksum.md5":
                        continue
                    filepath = os.path.join(root, file)
                    md5 = self._calculate_md5(filepath)
                    relpath = os.path.relpath(filepath, path)
                    f.write(f"{md5}  {relpath}\n")

    def _calculate_md5(self, filepath):
        """计算文件 MD5"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _log_backup(self, backup_path, label):
        """记录备份日志"""
        log_file = os.path.join(self.backup_root, "backup_log.csv")
        with open(log_file, "a") as f:
            f.write(f"{datetime.datetime.now()},{backup_path},{label}\n")

    def cleanup_old_backups(self, max_backups=10):
        """清理旧备份"""
        backups = []
        for d in os.listdir(self.backup_root):
            if d.startswith(os.path.basename(self.project_dir)):
                backups.append(d)

        backups.sort(reverse=True)

        # 保留最新的 max_backups 个
        for old in backups[max_backups:]:
            old_path = os.path.join(self.backup_root, old)
            shutil.rmtree(old_path)
            print(f"删除旧备份: {old_path}")


# 使用
backup = ProjectBackup("D:/projects/AVTR", "D:/backups")
backup.backup("daily")
backup.cleanup_old_backups(max_backups=10)
```

### 4.4 自动保存配置

```python
from fx import *

# 配置自动保存
proj = activeProject()
autosave = proj.property("autosave")

autosave.setValue("enabled", True)
autosave.setValue("interval", 300)  # 5 分钟
autosave.setValue("maxFiles", 10)   # 保留 10 个
autosave.setValue("path", "D:/autosave")
```

---

## 五、交付流程

### 5.1 交付前检查清单

```python
class DeliveryChecker:
    """交付检查工具"""

    def __init__(self, shot_path):
        self.shot_path = shot_path
        self.checks = []

    def check_all(self):
        """执行所有检查"""
        self.check_file_naming()
        self.check_frame_range()
        self.check_resolution()
        self.check_color_space()
        self.check_alpha_channel()
        self.check_metadata()
        self.check_file_integrity()

        return self._generate_report()

    def check_file_naming(self):
        """检查文件命名"""
        # 实现命名检查
        pass

    def check_frame_range(self):
        """检查帧范围"""
        # 检查帧数是否正确
        pass

    def check_resolution(self):
        """检查分辨率"""
        # 检查分辨率是否符合要求
        pass

    def check_color_space(self):
        """检查色彩空间"""
        # 检查 EXR 头部色彩空间标记
        pass

    def check_alpha_channel(self):
        """检查 Alpha 通道"""
        # 检查 Alpha 通道范围
        pass

    def check_metadata(self):
        """检查元数据"""
        # 检查 EXR 元数据
        pass

    def check_file_integrity(self):
        """检查文件完整性"""
        # 检查文件是否损坏
        pass

    def _generate_report(self):
        """生成检查报告"""
        passed = sum(1 for c in self.checks if c["status"] == "pass")
        failed = sum(1 for c in self.checks if c["status"] == "fail")

        report = f"""
=== 交付检查报告 ===
镜头: {self.shot_path}
通过: {passed}
失败: {failed}

详细结果:
"""
        for check in self.checks:
            status = "✅" if check["status"] == "pass" else "❌"
            report += f"{status} {check['name']}: {check['message']}\n"

        return report
```

### 5.2 交付包生成

```python
import os
import shutil
import json
from fx import *

class DeliveryPackager:
    """交付包生成工具"""

    def __init__(self, shot_info):
        self.shot_info = shot_info

    def package(self, output_dir):
        """生成交付包"""
        package_dir = os.path.join(output_dir, self.shot_info["shot_name"])
        os.makedirs(package_dir, exist_ok=True)

        # 创建子目录
        dirs = ["exr", "mattes", "tracking", "project", "proxies", "qc"]
        for d in dirs:
            os.makedirs(os.path.join(package_dir, d), exist_ok=True)

        # 复制 EXR 序列
        self._copy_exr(package_dir)

        # 复制遮罩
        self._copy_mattes(package_dir)

        # 复制跟踪数据
        self._copy_tracking(package_dir)

        # 复制项目文件
        self._copy_project(package_dir)

        # 生成代理视频
        self._generate_proxy(package_dir)

        # 生成 manifest
        self._generate_manifest(package_dir)

        # 生成 QC 报告
        self._generate_qc_report(package_dir)

        print(f"交付包已生成: {package_dir}")
        return package_dir

    def _generate_manifest(self, package_dir):
        """生成 manifest.json"""
        manifest = {
            "shot": self.shot_info["shot_name"],
            "version": self.shot_info["version"],
            "date": self.shot_info["date"],
            "artist": self.shot_info["artist"],
            "frameRange": self.shot_info["frame_range"],
            "resolution": self.shot_info["resolution"],
            "frameRate": self.shot_info["frame_rate"],
            "colorSpace": self.shot_info["color_space"],
            "tasks": self.shot_info["tasks"],
            "files": {
                "exr": "exr/",
                "mattes": "mattes/",
                "tracking": "tracking/",
                "project": "project/"
            }
        }

        manifest_path = os.path.join(package_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
```

### 5.3 交付流程图

```
完成工作
    ↓
Artist QC（自检）
    ↓
生成交付包 v001
    ↓
Lead QC（负责人审查）
    ↓
修改（如有）
    ↓
生成交付包 v002
    ↓
Supervisor QC（总监审查）
    ↓
修改（如有）
    ↓
生成交付包 final
    ↓
客户审查
    ↓
修改（如有）
    ↓
最终交付
    ↓
归档
```

---

## 六、自动化管理脚本

### 6.1 项目初始化

```python
import os
from fx import *

class ProjectInitializer:
    """项目初始化工具"""

    def __init__(self, project_name, base_dir="D:/projects"):
        self.project_name = project_name
        self.base_dir = base_dir

    def initialize(self):
        """初始化项目目录结构"""
        project_dir = os.path.join(self.base_dir, self.project_name)

        # 创建目录结构
        dirs = [
            "01_资料/brief",
            "01_资料/reference/roto_reference",
            "01_资料/reference/paint_reference",
            "01_资料/reference/style_guide",
            "01_资料/client_feedback",
            "02_素材/plates",
            "02_素材/luts",
            "02_素材/metadata",
            "03_工作文件",
            "04_输出",
            "05_交付",
            "06_归档",
            "99_临时/scratch",
            "99_临时/trash",
        ]

        for d in dirs:
            os.makedirs(os.path.join(project_dir, d), exist_ok=True)

        # 创建 README
        self._create_readme(project_dir)

        # 创建配置文件
        self._create_config(project_dir)

        print(f"项目初始化完成: {project_dir}")
        return project_dir

    def _create_readme(self, project_dir):
        """创建项目说明"""
        readme = f"""# {self.project_name}

## 项目信息
- 创建日期: {datetime.datetime.now().strftime("%Y-%m-%d")}
- 项目代号: {self.project_name}

## 目录结构
- 01_资料: 项目资料与参考
- 02_素材: 原始素材
- 03_工作文件: Silhouette 工作文件
- 04_输出: 渲染输出
- 05_交付: 交付文件
- 06_归档: 项目归档
- 99_临时: 临时文件
"""
        with open(os.path.join(project_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

    def _create_config(self, project_dir):
        """创建项目配置"""
        import json
        config = {
            "project_name": self.project_name,
            "resolution": [3840, 2160],
            "frame_rate": 24.0,
            "color_space": "ACEScg",
            "naming_convention": "{project}_{seq}_{shot}_{task}_v{version}",
            "version_control": True,
            "backup_enabled": True,
            "backup_interval": 300
        }

        config_path = os.path.join(project_dir, "project_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)


# 使用
initializer = ProjectInitializer("AVTR")
initializer.initialize()
```

### 6.2 批量镜头管理

```python
import os
import csv
from fx import *

class ShotManager:
    """镜头管理工具"""

    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.shots = []

    def load_shot_list(self, csv_path):
        """从 CSV 加载镜头列表"""
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.shots.append(row)
        print(f"加载 {len(self.shots)} 个镜头")

    def create_shot_structure(self):
        """为所有镜头创建目录"""
        for shot in self.shots:
            seq = shot["sequence"]
            sh = shot["shot"]

            shot_dir = os.path.join(
                self.project_dir,
                "03_工作文件",
                f"seq{seq:03d}",
                f"sh{sh:04d}"
            )
            os.makedirs(shot_dir, exist_ok=True)

            # 创建输出目录
            output_dir = os.path.join(
                self.project_dir,
                "04_输出",
                f"seq{seq:03d}",
                f"sh{sh:04d}"
            )
            for task in ["roto", "paint", "track"]:
                os.makedirs(os.path.join(output_dir, task), exist_ok=True)

    def generate_status_report(self):
        """生成镜头状态报告"""
        report = []
        for shot in self.shots:
            status = {
                "shot": f"SEQ{shot['sequence']:03d}_SH{shot['shot']:04d}",
                "roto": self._check_status(shot, "roto"),
                "paint": self._check_status(shot, "paint"),
                "track": self._check_status(shot, "track"),
                "qc": self._check_qc(shot)
            }
            report.append(status)

        return report

    def _check_status(self, shot, task):
        """检查任务状态"""
        # 实现状态检查
        pass
```

---

## 七、项目管理检查清单

### 7.1 项目启动检查

- [ ] 创建标准目录结构
- [ ] 配置项目参数（分辨率、帧率、色彩空间）
- [ ] 导入镜头列表
- [ ] 创建镜头目录
- [ ] 配置自动保存
- [ ] 配置备份策略
- [ ] 分配艺术家任务
- [ ] 建立版本控制

### 7.2 项目进行中检查

- [ ] 每日检查进度
- [ ] 监控磁盘空间
- [ ] 执行每日备份
- [ ] 更新镜头状态
- [ ] 跟踪问题与风险
- [ ] 定期 QC 检查

### 7.3 项目交付检查

- [ ] 所有镜头通过 QC
- [ ] 生成交付包
- [ ] 验证文件完整性
- [ ] 检查命名规范
- [ ] 确认色彩空间
- [ ] 生成 manifest
- [ ] 客户确认

### 7.4 项目归档检查

- [ ] 完成项目归档
- [ ] 验证归档完整性
- [ ] 清理临时文件
- [ ] 释放工作盘空间
- [ ] 更新项目数据库
- [ ] 总结经验教训

---

## 八、总结

良好的项目管理是 Silhouette 工作流顺畅运行的基础。通过：

1. **标准化目录结构**：便于文件查找与管理
2. **规范命名**：避免混淆与错误
3. **严格版本控制**：可追溯的修改历史
4. **可靠备份**：防止数据丢失
5. **清晰交付流程**：确保质量与效率
6. **自动化工具**：减少人工错误

可以建立高效、可靠、可扩展的项目管理体系。

---

> 相关文档：
> - [[Silhouette 团队协作工作流]]
> - [[Silhouette 行业标准与质量规范]]
> - [[Silhouette 常见问题与解决方案]]
