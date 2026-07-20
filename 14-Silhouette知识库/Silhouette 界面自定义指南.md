# Silhouette 界面自定义指南

> 分类: 预设与配置
> 更新日期: 2026-07-11
> 概述: 面板布局、工具栏配置、颜色方案、工作区保存完整说明。

## 目录
1. [界面自定义概述](#1-界面自定义概述)
2. [面板布局](#2-面板布局)
3. [工具栏配置](#3-工具栏配置)
4. [颜色方案](#4-颜色方案)
5. [工作区保存](#5-工作区保存)
6. [界面脚本化](#6-界面脚本化)
7. [多显示器配置](#7-多显示器配置)
8. [最佳实践](#8-最佳实践)

---

## 1. 界面自定义概述

### 1.1 为什么自定义界面

| 价值 | 说明 |
|------|------|
| 效率提升 | 常用功能触手可及 |
| 减少疲劳 | 舒适的布局和配色 |
| 专注工作 | 隐藏不必要的面板 |
| 适应工作流 | 不同任务不同布局 |
| 个性化 | 符合个人习惯 |

### 1.2 可自定义元素

| 元素 | 说明 | 自定义程度 |
|------|------|-----------|
| 面板布局 | 面板位置和大小 | 高 |
| 工具栏 | 工具按钮配置 | 高 |
| 颜色方案 | 界面颜色主题 | 中 |
| 字体 | 界面字体大小 | 中 |
| 快捷键 | 键盘绑定 | 高 |
| 工作区 | 完整布局保存 | 高 |

### 1.3 默认界面结构

```
┌─────────────────────────────────────────────┐
│                  菜单栏                      │
├─────────┬─────────────────────┬─────────────┤
│         │                     │             │
│  工具栏  │      预览视图       │  属性面板   │
│         │                     │             │
├─────────┤                     ├─────────────┤
│         │                     │             │
│  节点图  │                     │  时间轴     │
│         │                     │             │
└─────────┴─────────────────────┴─────────────┘
```

## 2. 面板布局

### 2.1 面板类型

| 面板 | 功能 | 默认位置 |
|------|------|----------|
| 预览视图 | 图像预览 | 中央 |
| 节点图 | 节点编辑 | 左下 |
| 属性面板 | 参数调整 | 右上 |
| 时间轴 | 帧控制 | 右下 |
| 工具栏 | 工具选择 | 左侧 |
| 项目浏览器 | 文件管理 | 可浮动 |
| 历史记录 | 操作历史 | 可浮动 |
| 信息面板 | 状态信息 | 底部 |

### 2.2 布局调整

```
面板操作:
- 拖动标题栏:移动面板
- 拖动边缘:调整大小
- 拖动到边缘:停靠
- 拖出窗口:浮动
- 双击标题栏:最大化/还原
- 右键标题栏:关闭/停靠选项
```

### 2.3 常用布局方案

```python
LAYOUT_PRESETS = {
    "roto_focus": {
        "description": "Roto 专注布局",
        "panels": {
            "preview": {"position": "center", "size": "large"},
            "timeline": {"position": "bottom", "size": "medium"},
            "tools": {"position": "left", "size": "small"},
            "properties": {"position": "right", "size": "small"},
            "node_graph": {"visible": False}
        }
    },
    "paint_focus": {
        "description": "Paint 专注布局",
        "panels": {
            "preview": {"position": "center", "size": "large"},
            "tools": {"position": "left", "size": "medium"},
            "properties": {"position": "right", "size": "medium"},
            "timeline": {"position": "bottom", "size": "small"},
            "node_graph": {"visible": False}
        }
    },
    "node_focus": {
        "description": "节点图专注布局",
        "panels": {
            "node_graph": {"position": "center", "size": "large"},
            "preview": {"position": "right", "size": "medium"},
            "properties": {"position": "right", "size": "small"},
            "timeline": {"position": "bottom", "size": "small"}
        }
    },
    "tracking_focus": {
        "description": "跟踪专注布局",
        "panels": {
            "preview": {"position": "center", "size": "large"},
            "tracker_info": {"position": "right", "size": "medium"},
            "timeline": {"position": "bottom", "size": "medium"},
            "tools": {"position": "left", "size": "small"}
        }
    },
    "dual_monitor": {
        "description": "双显示器布局",
        "monitor_1": {
            "preview": {"position": "center", "size": "full"}
        },
        "monitor_2": {
            "node_graph": {"position": "left", "size": "large"},
            "properties": {"position": "right", "size": "medium"},
            "timeline": {"position": "bottom", "size": "medium"}
        }
    }
}
```

### 2.4 应用布局

```python
class LayoutManager:
    """布局管理器"""
    
    def __init__(self):
        self.current_layout = None
        self.saved_layouts = {}
    
    def apply_layout(self, layout_name):
        """应用布局"""
        layout = LAYOUT_PRESETS.get(layout_name)
        if not layout:
            print(f"未知布局: {layout_name}")
            return False
        
        # 应用面板配置
        for panel_name, config in layout.get("panels", {}).items():
            self._configure_panel(panel_name, config)
        
        self.current_layout = layout_name
        print(f"已应用布局: {layout['description']}")
        return True
    
    def _configure_panel(self, panel_name, config):
        """配置单个面板"""
        # 设置可见性
        if "visible" in config:
            set_panel_visible(panel_name, config["visible"])
        
        # 设置位置
        if "position" in config:
            set_panel_position(panel_name, config["position"])
        
        # 设置大小
        if "size" in config:
            set_panel_size(panel_name, config["size"])
    
    def save_current_layout(self, name, description=""):
        """保存当前布局"""
        layout = {
            "description": description,
            "panels": self._capture_current_layout()
        }
        self.saved_layouts[name] = layout
        return layout
    
    def _capture_current_layout(self):
        """捕获当前布局"""
        # 实际实现需要访问 UI API
        return {}
```

## 3. 工具栏配置

### 3.1 工具栏组成

```
默认工具栏:
┌──────────────────────────────────────────┐
│ [新建] [打开] [保存] | [撤销] [重做] |    │
│ [Bezier] [Select] [Pan] [Zoom] |         │
│ [播放] [上一帧] [下一帧] | [渲染]        │
└──────────────────────────────────────────┘
```

### 3.2 自定义工具栏

```python
class ToolbarConfig:
    """工具栏配置"""
    
    def __init__(self):
        self.buttons = []
        self.load_default()
    
    def load_default(self):
        """加载默认配置"""
        self.buttons = [
            {"group": "file", "items": ["new", "open", "save"]},
            {"group": "edit", "items": ["undo", "redo"]},
            {"group": "tools", "items": ["bezier", "select", "pan", "zoom"]},
            {"group": "playback", "items": ["play", "prev_frame", "next_frame"]},
            {"group": "render", "items": ["render"]}
        ]
    
    def add_button(self, group, button_id, position=None):
        """添加按钮"""
        for g in self.buttons:
            if g["group"] == group:
                if position is not None:
                    g["items"].insert(position, button_id)
                else:
                    g["items"].append(button_id)
                return True
        return False
    
    def remove_button(self, button_id):
        """移除按钮"""
        for g in self.buttons:
            if button_id in g["items"]:
                g["items"].remove(button_id)
                return True
        return False
    
    def add_group(self, group_name, position=None):
        """添加按钮组"""
        new_group = {"group": group_name, "items": []}
        if position is not None:
            self.buttons.insert(position, new_group)
        else:
            self.buttons.append(new_group)
    
    def to_dict(self):
        """转换为字典"""
        return {"buttons": self.buttons}
    
    def save(self, filepath):
        """保存配置"""
        import json
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
```

### 3.3 工具栏预设

```python
TOOLBAR_PRESETS = {
    "roto_toolbar": {
        "buttons": [
            {"group": "file", "items": ["new", "open", "save"]},
            {"group": "edit", "items": ["undo", "redo"]},
            {"group": "roto_tools", "items": ["bezier", "x_spline", "ellipse", "rectangle"]},
            {"group": "view", "items": ["pan", "zoom", "fit"]},
            {"group": "playback", "items": ["play", "prev_frame", "next_frame"]}
        ]
    },
    "paint_toolbar": {
        "buttons": [
            {"group": "file", "items": ["new", "open", "save"]},
            {"group": "edit", "items": ["undo", "redo"]},
            {"group": "paint_tools", "items": ["clone", "brush", "eraser", "blur"]},
            {"group": "brush_size", "items": ["decrease_size", "increase_size"]},
            {"group": "view", "items": ["pan", "zoom"]}
        ]
    },
    "tracking_toolbar": {
        "buttons": [
            {"group": "file", "items": ["new", "open", "save"]},
            {"group": "track_tools", "items": ["add_tracker", "track_forward", "track_backward"]},
            {"group": "playback", "items": ["play", "prev_frame", "next_frame"]}
        ]
    }
}
```

## 4. 颜色方案

### 4.1 颜色方案选项

```python
COLOR_SCHEMES = {
    "dark_default": {
        "name": "深色默认",
        "background": "#2D2D2D",
        "panel_bg": "#333333",
        "text": "#E0E0E0",
        "accent": "#4A9EFF",
        "border": "#404040",
        "highlight": "#505050"
    },
    "dark_blue": {
        "name": "深蓝",
        "background": "#1A1A2E",
        "panel_bg": "#16213E",
        "text": "#E0E0E0",
        "accent": "#0F3460",
        "border": "#1A1A2E",
        "highlight": "#533483"
    },
    "light": {
        "name": "浅色",
        "background": "#F0F0F0",
        "panel_bg": "#FFFFFF",
        "text": "#333333",
        "accent": "#0078D4",
        "border": "#CCCCCC",
        "highlight": "#E5F3FF"
    },
    "high_contrast": {
        "name": "高对比度",
        "background": "#000000",
        "panel_bg": "#1A1A1A",
        "text": "#FFFFFF",
        "accent": "#FFFF00",
        "border": "#FFFFFF",
        "highlight": "#333333"
    },
    "sepia": {
        "name": "护眼棕",
        "background": "#3E2C1B",
        "panel_bg": "#4A3826",
        "text": "#F5DEB3",
        "accent": "#D2691E",
        "border": "#5C4033",
        "highlight": "#6B4226"
    }
}
```

### 4.2 应用颜色方案

```python
class ColorSchemeManager:
    """颜色方案管理器"""
    
    def __init__(self):
        self.current_scheme = "dark_default"
        self.custom_schemes = {}
    
    def apply_scheme(self, scheme_name):
        """应用颜色方案"""
        scheme = COLOR_SCHEMES.get(scheme_name)
        if not scheme:
            print(f"未知颜色方案: {scheme_name}")
            return False
        
        # 应用颜色(概念性,实际需要 UI API)
        for element, color in scheme.items():
            if element == "name":
                continue
            self._set_color(element, color)
        
        self.current_scheme = scheme_name
        print(f"已应用颜色方案: {scheme['name']}")
        return True
    
    def _set_color(self, element, color):
        """设置元素颜色"""
        # 实际实现需要访问 UI 主题 API
        pass
    
    def create_custom_scheme(self, name, base_scheme="dark_default", overrides=None):
        """创建自定义方案"""
        base = COLOR_SCHEMES.get(base_scheme, {}).copy()
        if overrides:
            base.update(overrides)
        base["name"] = name
        self.custom_schemes[name] = base
        return base
    
    def save_scheme(self, scheme_name, filepath):
        """保存方案到文件"""
        import json
        scheme = self.custom_schemes.get(scheme_name) or COLOR_SCHEMES.get(scheme_name)
        if scheme:
            with open(filepath, "w") as f:
                json.dump(scheme, f, indent=2)
```

### 4.3 颜色方案选择建议

| 环境 | 推荐方案 | 原因 |
|------|----------|------|
| 暗室工作 | 深色 | 减少屏幕眩光 |
| 明亮办公室 | 浅色 | 提高可读性 |
| 长时间工作 | 护眼棕 | 减少眼睛疲劳 |
| 视力辅助 | 高对比度 | 最大化可读性 |
| 色彩工作 | 深色中性 | 不干扰色彩判断 |

## 5. 工作区保存

### 5.1 工作区概念

工作区(Workspace)是完整的界面配置,包括面板布局、工具栏、颜色方案等。

### 5.2 工作区管理

```python
class WorkspaceManager:
    """工作区管理器"""
    
    def __init__(self):
        self.workspaces = {}
        self.current = None
    
    def save_workspace(self, name, description=""):
        """保存当前工作区"""
        workspace = {
            "name": name,
            "description": description,
            "layout": LayoutManager().save_current_layout(name),
            "toolbar": ToolbarConfig().to_dict(),
            "color_scheme": ColorSchemeManager().current_scheme,
            "created": "2026-07-11"
        }
        
        self.workspaces[name] = workspace
        self._save_to_file(workspace)
        return workspace
    
    def load_workspace(self, name):
        """加载工作区"""
        workspace = self.workspaces.get(name)
        if not workspace:
            workspace = self._load_from_file(name)
        
        if not workspace:
            print(f"工作区不存在: {name}")
            return False
        
        # 应用配置
        LayoutManager().apply_layout(workspace.get("layout", {}).get("name"))
        ColorSchemeManager().apply_scheme(workspace.get("color_scheme", "dark_default"))
        
        self.current = name
        print(f"已加载工作区: {name}")
        return True
    
    def delete_workspace(self, name):
        """删除工作区"""
        if name in self.workspaces:
            del self.workspaces[name]
            # 删除文件
            import os
            filepath = f"/workspaces/{name}.json"
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        return False
    
    def list_workspaces(self):
        """列出所有工作区"""
        return list(self.workspaces.keys())
    
    def _save_to_file(self, workspace):
        """保存到文件"""
        import json
        import os
        os.makedirs("/workspaces", exist_ok=True)
        filepath = f"/workspaces/{workspace['name']}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(workspace, f, indent=2, ensure_ascii=False)
    
    def _load_from_file(self, name):
        """从文件加载"""
        import json
        import os
        filepath = f"/workspaces/{name}.json"
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
```

### 5.3 预设工作区

```python
PRESET_WORKSPACES = {
    "roto_master": {
        "description": "Roto 大师工作区",
        "layout": "roto_focus",
        "toolbar": "roto_toolbar",
        "color_scheme": "dark_default"
    },
    "paint_master": {
        "description": "Paint 大师工作区",
        "layout": "paint_focus",
        "toolbar": "paint_toolbar",
        "color_scheme": "dark_default"
    },
    "node_master": {
        "description": "节点图大师工作区",
        "layout": "node_focus",
        "toolbar": "default",
        "color_scheme": "dark_default"
    },
    "tracking_master": {
        "description": "跟踪大师工作区",
        "layout": "tracking_focus",
        "toolbar": "tracking_toolbar",
        "color_scheme": "dark_default"
    },
    "presentation": {
        "description": "演示工作区",
        "layout": "preview_only",
        "toolbar": "minimal",
        "color_scheme": "dark_default"
    }
}
```

## 6. 界面脚本化

### 6.1 界面自动化

```python
class UIAutomation:
    """界面自动化"""
    
    def __init__(self):
        self.actions = []
    
    def record_action(self, action_type, target, params=None):
        """记录界面操作"""
        self.actions.append({
            "type": action_type,
            "target": target,
            "params": params or {},
            "time": "2026-07-11"
        })
    
    def replay(self):
        """回放操作"""
        for action in self.actions:
            self._execute_action(action)
    
    def _execute_action(self, action):
        """执行单个操作"""
        if action["type"] == "click":
            self._click(action["target"], action["params"])
        elif action["type"] == "drag":
            self._drag(action["target"], action["params"])
        elif action["type"] == "key":
            self._keypress(action["target"])
    
    def _click(self, target, params):
        """模拟点击"""
        pass
    
    def _drag(self, target, params):
        """模拟拖拽"""
        pass
    
    def _keypress(self, key):
        """模拟按键"""
        pass
```

### 6.2 面板控制脚本

```python
def setup_custom_interface():
    """设置自定义界面"""
    # 应用布局
    layout_mgr = LayoutManager()
    layout_mgr.apply_layout("roto_focus")
    
    # 配置工具栏
    toolbar = ToolbarConfig()
    toolbar.add_button("tools", "magnetic", position=4)
    
    # 应用颜色方案
    colors = ColorSchemeManager()
    colors.apply_scheme("dark_blue")
    
    # 保存工作区
    workspace_mgr = WorkspaceManager()
    workspace_mgr.save_workspace("my_custom", "自定义工作区")
    
    print("界面设置完成")

def switch_to_task(task_name):
    """根据任务切换界面"""
    task_layouts = {
        "roto": "roto_focus",
        "paint": "paint_focus",
        "tracking": "tracking_focus",
        "node_editing": "node_focus"
    }
    
    layout = task_layouts.get(task_name)
    if layout:
        LayoutManager().apply_layout(layout)
        print(f"已切换到 {task_name} 工作区")
```

## 7. 多显示器配置

### 7.1 多显示器布局

```python
class MultiMonitorConfig:
    """多显示器配置"""
    
    def __init__(self, num_monitors=2):
        self.num_monitors = num_monitors
        self.monitor_layouts = {}
    
    def configure_dual_monitor(self):
        """配置双显示器"""
        self.monitor_layouts = {
            "primary": {
                "panels": ["preview"],
                "position": "full",
                "description": "主显示器:全屏预览"
            },
            "secondary": {
                "panels": ["node_graph", "properties", "timeline", "tools"],
                "position": "tiled",
                "description": "副显示器:控制面板"
            }
        }
        
        self._apply_configuration()
    
    def configure_triple_monitor(self):
        """配置三显示器"""
        self.monitor_layouts = {
            "left": {
                "panels": ["node_graph", "tools"],
                "description": "左屏:节点图"
            },
            "center": {
                "panels": ["preview"],
                "description": "中屏:预览"
            },
            "right": {
                "panels": ["properties", "timeline"],
                "description": "右屏:属性和时间轴"
            }
        }
        
        self._apply_configuration()
    
    def _apply_configuration(self):
        """应用配置"""
        for monitor, config in self.monitor_layouts.items():
            print(f"配置 {monitor}: {config['description']}")
            for panel in config["panels"]:
                self._move_panel_to_monitor(panel, monitor)
    
    def _move_panel_to_monitor(self, panel_name, monitor):
        """移动面板到指定显示器"""
        # 实际实现需要访问多显示器 API
        pass
```

### 7.2 显示器布局建议

```
双显示器:
┌─────────────┐  ┌─────────────┐
│             │  │  节点图     │
│   预览      │  ├─────────────┤
│   视图      │  │  属性面板   │
│             │  ├─────────────┤
│             │  │  时间轴     │
└─────────────┘  └─────────────┘

三显示器:
┌────────┐ ┌─────────────┐ ┌────────┐
│ 节点图  │ │             │ │ 属性   │
│        │ │   预览      │ ├────────┤
├────────┤ │   视图      │ │        │
│ 工具栏  │ │             │ │ 时间轴 │
└────────┘ └─────────────┘ └────────┘
```

## 8. 最佳实践

### 8.1 界面优化原则

1. **常用功能易达**:最常用的面板放在显眼位置
2. **减少切换**:一个工作流所需面板尽量同屏
3. **预览最大化**:预览视图尽可能大
4. **隐藏不必要**:不用的面板及时隐藏
5. **保存工作区**:不同任务保存不同工作区

### 8.2 工作流对应工作区

| 工作流 | 推荐工作区 | 关键面板 |
|--------|-----------|----------|
| Roto | roto_focus | 预览、工具、时间轴 |
| Paint | paint_focus | 预览、画笔工具、属性 |
| 跟踪 | tracking_focus | 预览、跟踪信息、时间轴 |
| 节点编辑 | node_focus | 节点图、预览、属性 |
| 合成 | node_focus | 节点图、预览、属性 |
| 渲染 | preview_only | 预览、渲染设置 |

### 8.3 显示器配置建议

| 显示器数 | 配置方案 | 优势 |
|----------|----------|------|
| 1 | 全功能单屏 | 紧凑,适合笔记本 |
| 2 | 主预览+副控制 | 大预览,常用方案 |
| 3 | 三屏分离 | 最高效,适合专业 |

### 8.4 颜色方案选择

| 工作环境 | 推荐方案 | 原因 |
|----------|----------|------|
| 暗室 | 深色 | 减少眩光 |
| 明亮办公室 | 浅色 | 提高可读性 |
| 色彩工作 | 深色中性 | 不干扰色彩判断 |
| 长时间 | 护眼棕 | 减少疲劳 |

### 8.5 团队界面标准

```python
TEAM_INTERFACE_STANDARD = {
    "default_workspace": "roto_master",
    "color_scheme": "dark_default",
    "toolbar": "default",
    "shortcuts": "default",
    "font_size": "medium",
    "panel_transparency": 100,
    
    "rationale": {
        "workspace": "统一工作区便于协作和教学",
        "color_scheme": "深色方案适合后期工作环境",
        "toolbar": "默认工具栏覆盖常用功能",
        "shortcuts": "默认快捷键与行业一致"
    }
}

def apply_team_standard():
    """应用团队标准界面"""
    workspace = TEAM_INTERFACE_STANDARD["default_workspace"]
    scheme = TEAM_INTERFACE_STANDARD["color_scheme"]
    
    WorkspaceManager().load_workspace(workspace)
    ColorSchemeManager().apply_scheme(scheme)
    
    print("已应用团队标准界面配置")
```

### 8.6 界面故障排除

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 面板消失 | 误关闭 | Window → 重置面板 |
| 布局混乱 | 拖动错乱 | 加载保存的工作区 |
| 字体太小 | 分辨率高 | 调整字体大小 |
| 颜色看不清 | 方案不当 | 切换颜色方案 |
| 面板重叠 | 停靠错误 | 拖出再重新停靠 |

---

## 附录:界面自定义速查

| 操作 | 方法 | 快捷方式 |
|------|------|----------|
| 移动面板 | 拖动标题栏 | — |
| 调整大小 | 拖动边缘 | — |
| 最大化面板 | 双击标题栏 | — |
| 隐藏面板 | 右键 → 关闭 | Ctrl+Shift+H |
| 重置布局 | Window → Reset | Ctrl+Shift+R |
| 保存工作区 | Window → Save Workspace | Ctrl+Shift+S |
| 切换工作区 | Window → Workspace | Ctrl+Shift+W |
| 全屏 | View → Fullscreen | F11 |

> **提示**:花 30 分钟设置好个性化的工作区,可以节省数小时的工作时间。建议根据不同任务(Roto/Paint/跟踪)分别保存工作区,一键切换。
