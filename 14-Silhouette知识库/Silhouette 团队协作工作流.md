# Silhouette 团队协作工作流

> 分类: 故障排查
> 更新日期: 2026-07-11
> 概述: 系统讲解 Silhouette 多人协作、任务分配、合并策略、冲突解决与审查流程

## 目录
---

- [一、团队协作概览](#一团队协作概览)
- [二、任务分配与管理](#二任务分配与管理)
- [三、协作工作流设计](#三协作工作流设计)
- [四、合并策略](#四合并策略)
- [五、冲突解决](#五冲突解决)
- [六、审查流程](#六审查流程)
- [七、协作工具与平台](#七协作工具与平台)
- [八、远程协作实践](#八远程协作实践)

---

## 一、团队协作概览

### 1.1 团队角色定义

```
VFX Supervisor（特效总监）
    │
    ├── VFX Producer（制片）
    │       └─ 进度与预算管理
    │
    ├── Compositing Lead（合成组长）
    │       └─ 技术指导与质量把关
    │
    ├── Roto Lead（Roto 组长）
    │       └─ Roto 任务分配与审查
    │
    ├── Paint Lead（Paint 组长）
    │       └─ Paint 任务分配与审查
    │
    └── Roto/Paint Artists（艺术家）
            └─ 具体执行
```

### 1.2 团队规模与分工

| 项目规模 | 团队人数 | 角色配置 |
|---------|---------|---------|
| 小型（<50 镜头） | 3-5 人 | 1 Lead + 2-4 Artists |
| 中型（50-200 镜头） | 8-15 人 | 1 Supervisor + 2 Leads + 5-12 Artists |
| 大型（200-1000 镜头） | 20-50 人 | 完整层级 + 多班次 |
| 超大型（>1000 镜头） | 50+ 人 | 多团队、多地点协作 |

### 1.3 协作挑战

1. **文件冲突**：多人同时编辑同一镜头
2. **版本混乱**：版本管理不善导致混乱
3. **质量不一致**：不同艺术家水平差异
4. **沟通成本**：远程协作沟通效率低
5. **数据同步**：大文件传输与同步

---

## 二、任务分配与管理

### 2.1 任务分配原则

**原则一：按技能分配**
- 新手：简单镜头（静态、少遮挡）
- 中级：中等复杂度（运动、多对象）
- 高级：复杂镜头（头发、运动模糊、透明）

**原则二：按效率分配**
- 相似镜头集中给同一人
- 同序列镜头尽量给同一人
- 考虑艺术家的熟悉度

**原则三：按优先级分配**
- 紧急镜头优先
- 关键镜头优先
- 长周期镜头提前启动

### 2.2 任务分配矩阵

| 镜头类型 | Junior (0-2年) | Mid (2-4年) | Senior (4+年) |
|---------|:--------------:|:-----------:|:-------------:|
| 静态背景 Roto | ✅ | ✅ | ✅ |
| 简单角色 Roto | ✅ | ✅ | ✅ |
| 复杂角色 Roto | ❌ | ✅ | ✅ |
| 头发 Roto | ❌ | ❌ | ✅ |
| 简单 Paint | ✅ | ✅ | ✅ |
| 复杂 Paint | ❌ | ✅ | ✅ |
| 跟踪 | ❌ | ✅ | ✅ |

### 2.3 任务管理系统

```python
import json
import datetime

class TaskManager:
    """任务管理系统"""

    def __init__(self):
        self.tasks = []
        self.artists = []

    def add_artist(self, name, level, skills):
        """添加艺术家"""
        artist = {
            "name": name,
            "level": level,  # junior / mid / senior
            "skills": skills,  # ["roto", "paint", "track"]
            "current_tasks": 0,
            "max_tasks": 5
        }
        self.artists.append(artist)

    def create_task(self, shot, task_type, priority, complexity):
        """创建任务"""
        task = {
            "id": f"TASK_{len(self.tasks)+1:04d}",
            "shot": shot,
            "type": task_type,  # roto / paint / track
            "priority": priority,  # 1-5
            "complexity": complexity,  # simple / medium / complex
            "status": "pending",  # pending / assigned / in_progress / review / done
            "assigned_to": None,
            "created_date": datetime.datetime.now().isoformat(),
            "due_date": None,
            "estimated_hours": self._estimate_hours(task_type, complexity)
        }
        self.tasks.append(task)
        return task

    def _estimate_hours(self, task_type, complexity):
        """估算工时"""
        base = {"roto": 4, "paint": 6, "track": 2}.get(task_type, 4)
        multiplier = {"simple": 1, "medium": 2, "complex": 4}.get(complexity, 1)
        return base * multiplier

    def auto_assign(self):
        """自动分配任务"""
        # 按优先级排序
        pending = [t for t in self.tasks if t["status"] == "pending"]
        pending.sort(key=lambda x: x["priority"], reverse=True)

        for task in pending:
            # 找到合适的艺术家
            best_artist = self._find_best_artist(task)
            if best_artist:
                task["assigned_to"] = best_artist["name"]
                task["status"] = "assigned"
                best_artist["current_tasks"] += 1
                print(f"任务 {task['id']} 分配给 {best_artist['name']}")

    def _find_best_artist(self, task):
        """找到最合适的艺术家"""
        candidates = []
        for artist in self.artists:
            # 检查技能
            if task["type"] not in artist["skills"]:
                continue

            # 检查工作负荷
            if artist["current_tasks"] >= artist["max_tasks"]:
                continue

            # 检查复杂度匹配
            if task["complexity"] == "complex" and artist["level"] == "junior":
                continue
            if task["complexity"] == "complex" and artist["level"] == "mid" and task["type"] == "roto":
                continue

            # 计算匹配分数
            score = self._calculate_score(artist, task)
            candidates.append((artist, score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return None

    def _calculate_score(self, artist, task):
        """计算匹配分数"""
        score = 0
        # 负荷越低分数越高
        score += (artist["max_tasks"] - artist["current_tasks"]) * 10
        # 级别匹配
        level_score = {"senior": 3, "mid": 2, "junior": 1}
        complexity_score = {"complex": 3, "medium": 2, "simple": 1}
        if level_score[artist["level"]] >= complexity_score[task["complexity"]]:
            score += 20
        return score

    def generate_report(self):
        """生成任务报告"""
        report = {
            "total_tasks": len(self.tasks),
            "by_status": {},
            "by_artist": {},
            "overdue": []
        }

        for task in self.tasks:
            # 按状态统计
            status = task["status"]
            report["by_status"][status] = report["by_status"].get(status, 0) + 1

            # 按艺术家统计
            if task["assigned_to"]:
                artist = task["assigned_to"]
                if artist not in report["by_artist"]:
                    report["by_artist"][artist] = {"total": 0, "done": 0}
                report["by_artist"][artist]["total"] += 1
                if task["status"] == "done":
                    report["by_artist"][artist]["done"] += 1

        return report


# 使用示例
manager = TaskManager()
manager.add_artist("张三", "senior", ["roto", "paint", "track"])
manager.add_artist("李四", "mid", ["roto", "paint"])
manager.add_artist("王五", "junior", ["roto"])

manager.create_task("SH010", "roto", 5, "complex")
manager.create_task("SH020", "paint", 3, "medium")
manager.create_task("SH030", "roto", 2, "simple")

manager.auto_assign()
print(manager.generate_report())
```

---

## 三、协作工作流设计

### 3.1 集中式协作模型

```
        ┌─────────────┐
        │  Lead/Review │
        └──────┬──────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│Artist1│ │Artist2│ │Artist3│
└───────┘ └───────┘ └───────┘
```

**特点**：
- 所有艺术家独立工作
- Lead 统一审查与合并
- 适合中小型团队

### 3.2 分散式协作模型

```
┌──────────┐     ┌──────────┐
│ Artist1  │ ←→ │ Artist2  │
│ (Roto)   │     │ (Paint)  │
└────┬─────┘     └────┬─────┘
     │                │
     └───────┬────────┘
             │
        ┌────▼────┐
        │  Lead   │
        └─────────┘
```

**特点**：
- 艺术家间可直接协作
- 需要明确的责任划分
- 适合专业分工明确的团队

### 3.3 流水线协作模型

```
Roto Artist → Paint Artist → Track Artist → Compositor
     ↓             ↓             ↓              ↓
  v001          v001          v001           v001
     ↓             ↓             ↓              ↓
  Review        Review        Review         Review
     ↓             ↓             ↓              ↓
  v002          v002          v002           v002
```

**特点**：
- 按工序顺序流转
- 每个工序有明确的输入输出
- 适合标准化生产

### 3.4 推荐工作流

**中型团队推荐**：集中式 + 流水线混合

```
1. Lead 分配任务
2. Artist 独立完成（Roto/Paint/Track）
3. Artist 提交 v001
4. Lead 审查
5. Artist 修改（v002）
6. Supervisor 终审
7. 发布 final
```

---

## 四、合并策略

### 4.1 场景：多艺术家处理同一镜头

**问题**：Artist A 做 Roto，Artist B 做 Paint，需要合并到一个项目。

**解决方案**：

```python
from fx import *

class ProjectMerger:
    """项目合并工具"""

    @staticmethod
    def merge_projects(project_a_path, project_b_path, output_path):
        """合并两个项目"""
        # 加载项目A
        proj_a = Project()
        proj_a.load(project_a_path)
        sess_a = proj_a.item(0)

        # 加载项目B
        proj_b = Project()
        proj_b.load(project_b_path)
        sess_b = proj_b.item(0)

        # 创建合并后的项目
        merged_proj = Project()
        merged_sess = Session()
        merged_sess.label = f"{sess_a.label}_merged"
        merged_sess.width = sess_a.width
        merged_sess.height = sess_a.height
        merged_sess.frameRate = sess_a.frameRate
        merged_proj.addItem(merged_sess)
        activate(merged_proj)
        activate(merged_sess)

        # 复制项目A的节点
        node_mapping_a = {}
        for i in range(sess_a.numNodes):
            node = sess_a.node(i)
            new_node = Node(node.type)
            new_node.label = node.label
            merged_sess.addNode(new_node)
            node_mapping_a[i] = new_node

            # 复制属性
            for prop_name in node.properties:
                prop = node.property(prop_name)
                new_node.property(prop_name).setValue(prop.value, 0)

        # 复制项目B的节点
        node_mapping_b = {}
        for i in range(sess_b.numNodes):
            node = sess_b.node(i)
            new_node = Node(node.type)
            new_node.label = node.label
            merged_sess.addNode(new_node)
            node_mapping_b[i] = new_node

            # 复制属性
            for prop_name in node.properties:
                prop = node.property(prop_name)
                new_node.property(prop_name).setValue(prop.value, 0)

        # 重建连接
        # ...（连接逻辑）

        # 保存
        merged_proj.save(output_path)
        print(f"合并完成: {output_path}")
```

### 4.2 分工合并策略

**策略一：按任务分工**
- Artist A：Roto（所有形状）
- Artist B：Paint（所有修复）
- 合并：Roto 节点 + Paint 节点

**策略二：按区域分工**
- Artist A：上半画面
- Artist B：下半画面
- 合并：两个 Roto 节点，各负责一半

**策略三：按对象分工**
- Artist A：角色1
- Artist B：角色2
- 合并：多个形状组合

### 4.3 合并注意事项

1. **分辨率一致**：所有项目分辨率必须相同
2. **帧率一致**：帧率必须匹配
3. **色彩空间一致**：色彩管理设置必须相同
4. **命名冲突**：合并前检查节点命名
5. **连接重建**：合并后需要重新连接节点

---

## 五、冲突解决

### 5.1 文件锁定机制

```python
import os
import json
import datetime

class FileLock:
    """文件锁定工具"""

    def __init__(self, lock_dir="locks"):
        self.lock_dir = lock_dir
        os.makedirs(lock_dir, exist_ok=True)

    def acquire(self, filepath, user):
        """获取文件锁"""
        lock_file = self._get_lock_path(filepath)

        if os.path.exists(lock_file):
            with open(lock_file) as f:
                lock = json.load(f)
            if lock["user"] != user:
                return False, f"文件被 {lock['user']} 锁定"

        lock = {
            "user": user,
            "timestamp": datetime.datetime.now().isoformat(),
            "filepath": filepath
        }

        with open(lock_file, "w") as f:
            json.dump(lock, f, indent=2)

        return True, "锁定成功"

    def release(self, filepath, user):
        """释放文件锁"""
        lock_file = self._get_lock_path(filepath)

        if not os.path.exists(lock_file):
            return True, "无锁"

        with open(lock_file) as f:
            lock = json.load(f)

        if lock["user"] != user:
            return False, "无法释放他人锁"

        os.remove(lock_file)
        return True, "已释放"

    def _get_lock_path(self, filepath):
        """获取锁文件路径"""
        filename = os.path.basename(filepath).replace(".", "_") + ".lock"
        return os.path.join(self.lock_dir, filename)


# 使用
lock = FileLock()
success, msg = lock.acquire("D:/projects/sh010.sfx", "张三")
if success:
    print("获取锁成功，可以编辑")
    # ... 工作代码 ...
    lock.release("D:/projects/sh010.sfx", "张三")
else:
    print(f"无法获取锁: {msg}")
```

### 5.2 版本冲突解决

**场景**：Artist A 和 Artist B 同时修改了 v002，产生冲突。

**解决流程**：
1. 识别冲突（版本号相同）
2. 对比两个版本差异
3. 选择保留哪些修改
4. 生成合并版本 v003

```python
class ConflictResolver:
    """冲突解决工具"""

    @staticmethod
    def resolve_conflict(version_a, version_b, resolver="lead"):
        """解决版本冲突"""
        print(f"检测到冲突:")
        print(f"  版本A: {version_a} (by Artist A)")
        print(f"  版本B: {version_b} (by Artist B)")

        # 分析差异
        differences = ProjectMerger.compare_versions(version_a, version_b)

        print(f"\n差异:")
        for diff in differences["property_changes"]:
            print(f"  {diff['node']}.{diff['property']}:")
            print(f"    A: {diff['old']}")
            print(f"    B: {diff['new']}")

        # 由 resolver 决定保留哪些
        # ... 决策逻辑 ...

        # 生成合并版本
        merged = ProjectMerger.merge_projects(version_a, version_b, "merged_v003.sfx")
        return merged
```

### 5.3 沟通冲突解决

**原则**：
1. 及时沟通：发现问题立即沟通
2. 明确责任：由 Lead 决定最终方案
3. 记录决策：所有冲突解决记录在案
4. 避免对立：以项目质量为重

---

## 六、审查流程

### 6.1 三级审查体系

```
Level 1: Artist Self-Review（自审）
    │   └─ 艺术家完成后的自我检查
    │   └─ 使用 QC 检查清单
    │   └─ 提交 v001
    ▼
Level 2: Lead Review（组长审查）
    │   └─ 技术与艺术审查
    │   └─ 提出修改意见
    │   └─ 艺术家修改后提交 v002
    ▼
Level 3: Supervisor Review（总监终审）
    │   └─ 最终质量把关
    │   └─ 批准或打回
    │   └─ 发布 final
```

### 6.2 审查标准

**技术审查**：
| 检查项 | 标准 | 容差 |
|--------|------|------|
| 帧范围 | 完整 | +2 handle |
| 分辨率 | 正确 | 严格 |
| Alpha | 0-1 | 严格 |
| 命名 | 规范 | 严格 |
| 文件完整 | 无损坏 | 严格 |

**艺术审查**：
| 检查项 | 标准 | 等级 |
|--------|------|------|
| 边缘精度 | <1px | A/B/C |
| 时序一致 | 无抖动 | A/B/C |
| 运动模糊 | 匹配 | A/B/C |
| 整体质量 | 达标 | A/B/C |

### 6.3 审查工具

```python
class ReviewSystem:
    """审查系统"""

    def __init__(self):
        self.reviews = []

    def submit_for_review(self, shot, version, artist, notes=""):
        """提交审查"""
        review = {
            "id": f"REV_{len(self.reviews)+1:04d}",
            "shot": shot,
            "version": version,
            "artist": artist,
            "submitted_date": datetime.datetime.now().isoformat(),
            "status": "pending",  # pending / approved / rejected
            "notes": notes,
            "feedback": []
        }
        self.reviews.append(review)
        return review

    def add_feedback(self, review_id, reviewer, feedback, severity="minor"):
        """添加反馈"""
        for review in self.reviews:
            if review["id"] == review_id:
                review["feedback"].append({
                    "reviewer": reviewer,
                    "feedback": feedback,
                    "severity": severity,  # minor / major / critical
                    "timestamp": datetime.datetime.now().isoformat()
                })
                break

    def approve(self, review_id, reviewer):
        """批准"""
        for review in self.reviews:
            if review["id"] == review_id:
                review["status"] = "approved"
                review["approved_by"] = reviewer
                review["approved_date"] = datetime.datetime.now().isoformat()
                break

    def reject(self, review_id, reviewer, reason):
        """打回"""
        for review in self.reviews:
            if review["id"] == review_id:
                review["status"] = "rejected"
                review["rejected_by"] = reviewer
                review["reject_reason"] = reason
                break

    def get_pending_reviews(self, reviewer=None):
        """获取待审查"""
        pending = [r for r in self.reviews if r["status"] == "pending"]
        return pending
```

### 6.4 审查会议

**每日审查会（Daily Review）**：
- 时间：每天 30-60 分钟
- 参与者：Lead + Artists
- 内容：审查昨日提交，分配今日任务
- 工具：投影 + Silhouette

**每周审查会（Weekly Review）**：
- 时间：每周 1-2 小时
- 参与者：Supervisor + Leads
- 内容：审查关键镜头，解决技术问题

**客户审查（Client Review）**：
- 时间：按里程碑
- 参与者：Supervisor + Client
- 内容：展示进度，获取反馈

---

## 七、协作工具与平台

### 7.1 项目管理工具

| 工具 | 类型 | 适用规模 | 特点 |
|------|------|---------|------|
| ShotGrid | VFX 专用 | 中大型 | 行业标准，集成度高 |
| ftrack | VFX 专用 | 中大型 | 类似 ShotGrid |
| Trello | 通用 | 小型 | 简单易用 |
| Asana | 通用 | 中型 | 灵活 |
| Jira | 通用 | 中大型 | 功能强大 |

### 7.2 文件共享

| 方案 | 速度 | 安全性 | 适用场景 |
|------|------|--------|---------|
| NAS（本地） | 快 | 高 | 同一办公室 |
| VPN + NAS | 中 | 高 | 远程办公 |
| 云存储（S3/GCS） | 中 | 中 | 跨地区协作 |
| Aspera/Signiant | 极快 | 高 | 大文件传输 |
| Google Drive/Dropbox | 慢 | 中 | 小文件 |

### 7.3 沟通工具

| 工具 | 用途 | 特点 |
|------|------|------|
| Slack/Teams | 日常沟通 | 即时、可搜索 |
| Zoom/Meet | 视频会议 | 屏幕共享 |
| Frame.io | 视频审查 | 时间码标注 |
| SyncSketch | 协作审查 | 实时同步标注 |

### 7.4 版本控制

| 工具 | 适用 | 特点 |
|------|------|------|
| Perforce | 大型工作室 | 二进制文件专业管理 |
| Git LFS | 中小型 | 开源、灵活 |
| SVN | 传统 | 简单稳定 |
| ShotGrid Versioning | VFX 专用 | 与项目管理集成 |

---

## 八、远程协作实践

### 8.1 远程协作挑战

1. **大文件传输**：EXR 序列体积大
2. **网络延迟**：影响实时协作
3. **时区差异**：沟通窗口有限
4. **安全合规**：数据安全要求
5. **团队凝聚力**：远程影响文化

### 8.2 远程协作方案

**方案一：云端工作站**
- 艺术家通过远程桌面连接云端工作站
- 数据存储在云端，不落地
- 优点：安全、统一环境
- 缺点：依赖网络质量

**方案二：本地工作站 + 云同步**
- 艺术家使用本地工作站
- 定期同步到云端
- 优点：网络依赖低
- 缺点：数据安全风险

**方案三：混合模式**
- 关键艺术家在办公室
- 非关键艺术家远程
- 优点：平衡效率与灵活
- 缺点：管理复杂

### 8.3 远程协作最佳实践

1. **明确工作时间**：约定重叠工作时间
2. **每日站会**：15 分钟同步进度
3. **详细文档**：减少口头沟通依赖
4. **异步沟通**：善用文字与录屏
5. **定期视频**：保持团队联系
6. **清晰任务**：任务描述要详细

### 8.4 安全策略

```
远程艺术家
    │
    ├─ VPN 连接（加密）
    │
    ├─ 双因素认证
    │
    ├─ 远程桌面（无数据落地）
    │
    ├─ 操作日志记录
    │
    └─ 水印保护
```

---

## 九、总结

团队协作是大型 VFX 项目成功的关键。通过：

1. **清晰的角色分工**：明确每个人的职责
2. **合理的任务分配**：技能与任务匹配
3. **规范的工作流**：减少混乱与冲突
4. **有效的审查流程**：确保质量一致
5. **合适的工具平台**：提高协作效率
6. **适应远程协作**：应对新型工作模式

可以建立高效、灵活、可扩展的团队协作体系。

---

> 相关文档：
> - [[Silhouette 项目管理最佳实践]]
> - [[Silhouette 行业标准与质量规范]]
> - [[Silhouette 在影视特效中的应用研究]]
