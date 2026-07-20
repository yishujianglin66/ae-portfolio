# DaVinci Resolve Color页面完全指南

> 版本: 2025-v1 | 适用: 专业调色/HDR/ACES工作流

## 一、Color页面架构

### 1.1 核心面板

| 面板 | 功能 | 快捷键 |
|------|------|--------|
| 媒体池 | 素材管理 | Shift+1 |
| 节点编辑器 | 调色节点图 | Shift+5 |
| 调色轮 | 一级/二级调色 | Shift+3 |
| 曲线 | 精确色调控制 | Shift+4 |
| 限定器 | 色彩选择 | Shift+6 |
| 运动跟踪 | 跟踪遮罩 | Shift+7 |
| 静帧库 | 参考帧存储 | Shift+8 |

### 1.2 节点类型

| 节点 | 图标 | 用途 |
|------|------|------|
| 串行节点 | 串联 | 默认，顺序处理 |
| 并行节点 | 分支 | 同时处理，混合结果 |
| 层节点 | 堆叠 | 类似PS图层 |
| 外部节点 | 外部键 | 使用外部遮罩 |
| 裁剪节点 | 裁剪 | 独立裁剪 |

### 1.3 推荐节点结构

```
标准调色节点链:
1. 降噪节点(最先)
2. 一级校正(曝光/白平衡)
3. 镜头校正(暗角/畸变)
4. 二级调色(肤色/天空)
5. 风格化(创意调色/LUT)
6. 锐化(最后)
```

## 二、一级调色

### 2.1 调色轮

| 控制 | 范围 | 用途 |
|------|------|------|
| Lift(提升) | 暗部 | 黑场/阴影调整 |
| Gamma(伽马) | 中间调 | 整体亮度 |
| Gain(增益) | 高光 | 白场/高光调整 |
| Offset(偏移) | 全局 | 整体偏移 |

### 2.2 一级校正流程

```
1. 白平衡校正
   - 使用色板/灰卡参考
   - 或目视调整(中间灰应该中性)

2. 曝光校正
   - 波形示波器: 暗部0-5, 亮部95-100
   - Lift调整暗部, Gain调整亮部

3. 对比度
   - 曲线S形增加对比
   - 或Pivot(轴心)控制

4. 饱和度
   - 整体饱和度调整
   - 色彩增强/减弱
```

## 三、二级调色

### 3.1 限定器(Qualifier)

| 参数 | 作用 | 技巧 |
|------|------|------|
| 色相 | 选择颜色范围 | 肤色选橙红区 |
| 饱和度 | 选择饱和度范围 | 排除灰/白 |
| 亮度 | 选择亮度范围 | 选择特定亮度 |
| 模糊 | 柔化选区边缘 | 2-5 |
| 反相 | 反转选区 | 选择非目标 |

### 3.2 限定器工作流

```
1. 选择限定器面板
2. 用吸管选取目标颜色
3. 按住Shift+吸管添加范围
4. 按住Alt+吸管排除范围
5. 调整HSL范围(缩小到最小)
6. 增加模糊(2-5)柔化边缘
7. 在限定区域上单独调色
```

### 3.3 肤色限定器

```
肤色选择技巧:
1. 限定器 → HSL
2. 色相: 橙红区域(0-30°)
3. 饱和度: 中等(30-80%)
4. 亮度: 中到高(30-90%)
5. 模糊: 3-5
6. 查看遮罩(高亮模式)
7. 在限定区域内调整:
   - 色温偏暖
   - 饱和度适中
   - 对比度适中
```

## 四、曲线系统

### 4.1 曲线类型

| 曲线 | 功能 |
|------|------|
| 自定义曲线 | RGB亮度曲线 |
| 色相vs色相 | 改变特定色相 |
| 色相vs饱和度 | 按色相调整饱和度 |
| 色相vs亮度 | 按色相调整亮度 |
| 亮度vs饱和度 | 按亮度调整饱和度 |
| 饱和度vs饱和度 | 按饱和度调整饱和度 |

### 4.2 曲线预设

| 曲线 | 效果 | 应用 |
|------|------|------|
| S曲线 | 增强对比 | 最常用 |
| 暗部抬起 | 胶片感 | 复古 |
| 高光压缩 | 柔和 | 电影感 |
| 通道曲线 | 色彩偏移 | 创意调色 |

## 五、色彩管理

### 5.1 达芬奇色彩管理(DCM)

```
项目设置 → 色彩管理:
方案1: 达芬奇广色域
  色彩科学: DaVinci YRGB Color Managed
  时间线色彩空间: Rec.709 Gamma 2.4
  适合: 简单工作流

方案2: ACEScct
  色彩科学: ACEScct
  ACES版本: 1.3
  适合: 专业VFX/多软件协作

方案3: 达芬奇宽色域
  色彩科学: DaVinci YRGB
  时间线: DaVinci Wide Gamut / DaVinci Intermediate
  适合: HDR多交付
```

### 5.2 HDR调色

| 格式 | 传输曲线 | 色域 | 用途 |
|------|---------|------|------|
| HDR10 | PQ | Rec.2020 | 流媒体 |
| Dolby Vision | PQ | Rec.2020 | Netflix/Apple |
| HLG | HLG | Rec.2020 | 广播 |

```
HDR调色注意事项:
1. 使用PQ/HLG曲线(非Gamma 2.4)
2. 高光可达1000-4000nits
3. 使用HDR示波器监控
4. 注意SDR保护(Trim Pass)
5. Dolby Vision需要专用硬件
```

## 六、跟踪与稳定

### 6.1 跟踪器

| 模式 | 用途 | 精度 |
|------|------|------|
| 点跟踪 | 单点运动 | 中 |
| 平面跟踪 | 平面运动 | 高 |
| 云跟踪 | 复杂运动 | 高 |

### 6.2 稳定化

```
1. 选中剪辑 → 检查器 → 稳定
2. 分析运动
3. 选择稳定模式:
   - 透视(默认)
   - 相似(轻微)
   - 平移(仅位移)
4. 调整平滑度
5. 裁剪比例
```
# DaVinci Resolve Color页面完全指南

> 适用版本：DaVinci Resolve Studio 21.0 | 更新日期：2026-07-14 | 分类：DaVinci Resolve知识库

---

## 目录

- [一、Color页面核心概念](#一color页面核心概念)
- [二、节点调色架构](#二节点调色架构)
- [三、色轮系统详解](#三色轮系统详解)
- [四、曲线调色技术](#四曲线调色技术)
- [五、一级校色技术](#五一级校色技术)
- [六、二级调色技术](#六二级调色技术)
- [七、LUT系统与应用](#七lut系统与应用)
- [八、Color页面API自动化](#八color页面api自动化)
- [九、故障排查](#九故障排查)
- [十、性能优化](#十性能优化)

---

## 一、Color页面核心概念

### 1.1 Color页面定位

Color页面是DaVinci Resolve的核心调色工作区，具有以下特点：

| 特性 | 说明 |
|------|------|
| **专业调色** | 电影级专业调色系统 |
| **节点调色** | 基于节点的非破坏性调色 |
| **色轮系统** | 完整的Lift/Gamma/Gain色轮 |
| **曲线调色** | RGB曲线、色相饱和度曲线等 |
| **LUT支持** | 完整的LUT加载和应用 |
| **匹配工具** | 自动颜色匹配工具 |
| **跟踪稳定** | 集成跟踪和稳定功能 |

### 1.2 界面布局

```python
# Color页面界面布局
# ┌─────────────────────────────────────────────────────────┐
# │ 工具栏 (Toolbar)                                       │
# │ 节点工具/视图控制/渲染设置                              │
# ├─────────────────────────────────────────────────────────┤
# │ 节点图 (Node Graph)       │ 监视器 (Viewer)            │
# │ 调色节点/节点连接          │ 视频预览/示波器            │
# ├───────────────────────────┼─────────────────────────────┤
# │ 检查器 (Inspector)        │ 画廊 (Gallery)             │
# │ 节点参数/色轮/曲线         │ 静帧存储/调色预设          │
# └───────────────────────────┴─────────────────────────────┘
```

### 1.3 核心快捷键

```python
class ColorPageShortcuts:
    """Color页面核心快捷键"""
    
    NAVIGATION = {
        "Space": "播放/暂停",
        "J/K/L": "倒放/暂停/正放",
        "1-9": "切换示波器",
        "F": "帧精确模式",
        "H": "适合视图",
        "Z": "缩放工具",
        "Shift+Z": "重置缩放"
    }
    
    NODE_OPERATIONS = {
        "Ctrl+Space": "添加节点",
        "Delete": "删除节点",
        "Ctrl+D": "复制节点",
        "Ctrl+G": "编组节点",
        "M": "创建合并节点",
        "P": "创建并行节点",
        "S": "创建串行节点",
        "Tab": "切换节点类型"
    }
    
    COLOR_TOOLS = {
        "L": "Lift色轮",
        "G": "Gamma色轮",
        "N": "Gain色轮",
        "O": "Offset色轮",
        "C": "曲线编辑器",
        "V": "色相饱和度曲线",
        "T": "色阶",
        "Y": "LUT",
        "B": "模糊",
        "X": "降噪"
    }
```

---

## 二、节点调色架构

### 2.1 节点类型分类

```python
class ColorNodeTypes:
    """调色节点类型分类"""
    
    PRIMARY = [
        "Corrector",     # 校正节点（主调色）
        "ColorWheel",    # 色轮节点
        "Curves",        # 曲线节点
        "Levels",        # 色阶节点
        "HueSat",        # 色相饱和度节点
        "Log",           # Log节点
        "CDL"            # ASC CDL节点
    ]
    
    SECONDARY = [
        "Qualifier",     # 限定器节点
        "PowerWindow",   # 动态窗口节点
        "Tracker",       # 跟踪节点
        "Stabilizer",    # 稳定节点
        "Keyer",         # 键控节点
        "Blade",         # 刀片节点
        "Blur"           # 模糊节点
    ]
    
    UTILITY = [
        "LUT",           # LUT节点
        "Blur",          # 模糊节点
        "Denoise",       # 降噪节点
        "Sharpen",       # 锐化节点
        "Deflicker",     # 去闪烁节点
        "FrameHold",     # 帧冻结节点
        "Timecode"       # 时间码节点
    ]
    
    TRANSFORM = [
        "Transform",     # 变换节点
        "CornerPin",     # 四角定位节点
        "Warp",          # 变形节点
        "Resize",        # 缩放节点
        "Crop"           # 裁剪节点
    ]
    
    MERGE = [
        "Merge",         # 合并节点
        "Layer",         # 图层节点
        "Compound",      # 复合节点
        "Parallel",      # 并行节点
        "Serial"         # 串行节点
    ]
```

### 2.2 节点图操作

```python
class ColorNodeGraphManager:
    """调色节点图管理器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.color_page = None
        self.node_graph = None
    
    def get_color_page(self):
        """获取调色页"""
        try:
            project = self.engine.get_project()
            self.color_page = project.GetColorPage()
            return self.color_page
        except Exception as e:
            print(f"获取调色页失败: {e}")
            return None
    
    def get_node_graph(self):
        """获取节点图"""
        try:
            if not self.color_page:
                self.get_color_page()
            
            self.node_graph = self.color_page.GetNodeGraph()
            return self.node_graph
        except Exception as e:
            print(f"获取节点图失败: {e}")
            return None
    
    def create_node(self, node_type="Corrector", input_node=None):
        """创建节点"""
        try:
            node_graph = self.get_node_graph()
            
            if input_node:
                node = node_graph.AddNode(node_type, input_node)
            else:
                node = node_graph.AddNode(node_type)
            
            return node
        except Exception as e:
            print(f"创建节点失败 {node_type}: {e}")
            return None
    
    def connect_nodes(self, from_node, to_node):
        """连接节点"""
        try:
            from_node.ConnectTo(to_node)
            return True
        except Exception as e:
            print(f"连接节点失败: {e}")
            return False
    
    def delete_node(self, node):
        """删除节点"""
        try:
            self.node_graph.DeleteNode(node)
            return True
        except Exception as e:
            print(f"删除节点失败: {e}")
            return False
    
    def get_selected_nodes(self):
        """获取选中节点"""
        try:
            return self.node_graph.GetSelectedNodes()
        except Exception as e:
            print(f"获取选中节点失败: {e}")
            return []
    
    def select_node(self, node):
        """选中节点"""
        try:
            self.node_graph.SelectNode(node)
            return True
        except Exception as e:
            print(f"选中节点失败: {e}")
            return False
    
    def clear_selection(self):
        """清除选择"""
        try:
            self.node_graph.ClearSelection()
            return True
        except Exception as e:
            print(f"清除选择失败: {e}")
            return False
```

---

## 三、色轮系统详解

### 3.1 色轮基础操作

```python
class ColorWheelSystem:
    """色轮系统"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.node_graph = None
    
    def set_node_graph(self, node_graph):
        """设置节点图"""
        self.node_graph = node_graph
    
    def set_lift(self, node, values):
        """设置Lift色轮"""
        try:
            node.SetParameterValue("Lift", values)
            return True
        except Exception as e:
            print(f"设置Lift失败: {e}")
            return False
    
    def set_gamma(self, node, values):
        """设置Gamma色轮"""
        try:
            node.SetParameterValue("Gamma", values)
            return True
        except Exception as e:
            print(f"设置Gamma失败: {e}")
            return False
    
    def set_gain(self, node, values):
        """设置Gain色轮"""
        try:
            node.SetParameterValue("Gain", values)
            return True
        except Exception as e:
            print(f"设置Gain失败: {e}")
            return False
    
    def set_offset(self, node, values):
        """设置Offset"""
        try:
            node.SetParameterValue("Offset", values)
            return True
        except Exception as e:
            print(f"设置Offset失败: {e}")
            return False
    
    def apply_color_balance(self, node, lift, gamma, gain, offset=None):
        """应用完整色彩平衡"""
        success = True
        success &= self.set_lift(node, lift)
        success &= self.set_gamma(node, gamma)
        success &= self.set_gain(node, gain)
        
        if offset:
            success &= self.set_offset(node, offset)
        
        return success
    
    def set_lift_saturation(self, node, value):
        """设置Lift饱和度"""
        try:
            node.SetParameterValue("Lift Saturation", value)
            return True
        except Exception as e:
            print(f"设置Lift饱和度失败: {e}")
            return False
    
    def set_gamma_saturation(self, node, value):
        """设置Gamma饱和度"""
        try:
            node.SetParameterValue("Gamma Saturation", value)
            return True
        except Exception as e:
            print(f"设置Gamma饱和度失败: {e}")
            return False
    
    def set_gain_saturation(self, node, value):
        """设置Gain饱和度"""
        try:
            node.SetParameterValue("Gain Saturation", value)
            return True
        except Exception as e:
            print(f"设置Gain饱和度失败: {e}")
            return False
```

### 3.2 色轮调色风格预设

```python
class ColorGradePresets:
    """调色风格预设"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.color_wheel = ColorWheelSystem(resolve_engine)
    
    def apply_warm_cinematic(self, node):
        """应用暖色电影风格"""
        return self.color_wheel.apply_color_balance(
            node,
            lift=[0.08, 0.03, -0.03],
            gamma=[0, 0, 0],
            gain=[0.02, -0.02, -0.05],
            offset=[0.01, 0, -0.01]
        )
    
    def apply_cool_cinematic(self, node):
        """应用冷色电影风格"""
        return self.color_wheel.apply_color_balance(
            node,
            lift=[-0.05, -0.01, 0.06],
            gamma=[0, 0, 0],
            gain=[-0.02, 0.03, 0.08],
            offset=[-0.01, 0, 0.01]
        )
    
    def apply_teal_orange(self, node):
        """应用青橙风格"""
        return self.color_wheel.apply_color_balance(
            node,
            lift=[-0.02, 0.03, 0.01],
            gamma=[0.02, 0, -0.02],
            gain=[0.03, -0.02, -0.05],
            offset=[0, 0, 0]
        )
    
    def apply_high_contrast(self, node):
        """应用高对比度风格"""
        return self.color_wheel.apply_color_balance(
            node,
            lift=[-0.05, -0.05, -0.05],
            gamma=[0, 0, 0],
            gain=[0.05, 0.05, 0.05],
            offset=[0, 0, 0]
        )
    
    def apply_low_contrast(self, node):
        """应用低对比度风格"""
        return self.color_wheel.apply_color_balance(
            node,
            lift=[0.03, 0.03, 0.03],
            gamma=[0, 0, 0],
            gain=[-0.03, -0.03, -0.03],
            offset=[0, 0, 0]
        )
    
    def apply_desaturated(self, node):
        """应用低饱和度风格"""
        success = self.color_wheel.apply_color_balance(
            node,
            lift=[0, 0, 0],
            gamma=[0, 0, 0],
            gain=[0, 0, 0]
        )
        
        success &= self.color_wheel.set_lift_saturation(node, -0.3)
        success &= self.color_wheel.set_gamma_saturation(node, -0.3)
        success &= self.color_wheel.set_gain_saturation(node, -0.3)
        
        return success
```

---

## 四、曲线调色技术

### 4.1 RGB曲线

```python
class RGBCurveTools:
    """RGB曲线工具"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def set_rgb_curve(self, node, curve_points):
        """设置RGB曲线"""
        try:
            node.SetParameterValue("RGB Curve", curve_points)
            return True
        except Exception as e:
            print(f"设置RGB曲线失败: {e}")
            return False
    
    def set_red_curve(self, node, curve_points):
        """设置红色曲线"""
        try:
            node.SetParameterValue("Red Curve", curve_points)
            return True
        except Exception as e:
            print(f"设置红色曲线失败: {e}")
            return False
    
    def set_green_curve(self, node, curve_points):
        """设置绿色曲线"""
        try:
            node.SetParameterValue("Green Curve", curve_points)
            return True
        except Exception as e:
            print(f"设置绿色曲线失败: {e}")
            return False
    
    def set_blue_curve(self, node, curve_points):
        """设置蓝色曲线"""
        try:
            node.SetParameterValue("Blue Curve", curve_points)
            return True
        except Exception as e:
            print(f"设置蓝色曲线失败: {e}")
            return False
    
    def apply_contrast_curve(self, node):
        """应用对比度曲线"""
        curve_points = [
            [0, 0],
            [0.2, 0.12],
            [0.5, 0.5],
            [0.8, 0.88],
            [1, 1]
        ]
        return self.set_rgb_curve(node, curve_points)
    
    def apply_soft_contrast(self, node):
        """应用柔和对比度曲线"""
        curve_points = [
            [0, 0],
            [0.25, 0.22],
            [0.5, 0.5],
            [0.75, 0.78],
            [1, 1]
        ]
        return self.set_rgb_curve(node, curve_points)
    
    def apply_log_to_linear(self, node):
        """应用Log转线性曲线"""
        curve_points = [
            [0, 0],
            [0.3, 0.15],
            [0.5, 0.4],
            [0.7, 0.65],
            [0.9, 0.85],
            [1, 1]
        ]
        return self.set_rgb_curve(node, curve_points)
    
    def apply_linear_to_log(self, node):
        """应用线性转Log曲线"""
        curve_points = [
            [0, 0],
            [0.15, 0.3],
            [0.4, 0.5],
            [0.65, 0.7],
            [0.85, 0.9],
            [1, 1]
        ]
        return self.set_rgb_curve(node, curve_points)
```

### 4.2 色相饱和度曲线

```python
class HueSatCurveTools:
    """色相饱和度曲线工具"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def set_hue_vs_sat(self, node, curve_points):
        """设置色相vs饱和度曲线"""
        try:
            node.SetParameterValue("Hue vs Sat", curve_points)
            return True
        except Exception as e:
            print(f"设置色相vs饱和度曲线失败: {e}")
            return False
    
    def set_hue_vs_hue(self, node, curve_points):
        """设置色相vs色相曲线"""
        try:
            node.SetParameterValue("Hue vs Hue", curve_points)
            return True
        except Exception as e:
            print(f"设置色相vs色相曲线失败: {e}")
            return False
    
    def set_hue_vs_luma(self, node, curve_points):
        """设置色相vs亮度曲线"""
        try:
            node.SetParameterValue("Hue vs Luma", curve_points)
            return True
        except Exception as e:
            print(f"设置色相vs亮度曲线失败: {e}")
            return False
    
    def set_sat_vs_sat(self, node, curve_points):
        """设置饱和度vs饱和度曲线"""
        try:
            node.SetParameterValue("Sat vs Sat", curve_points)
            return True
        except Exception as e:
            print(f"设置饱和度vs饱和度曲线失败: {e}")
            return False
    
    def set_luma_vs_sat(self, node, curve_points):
        """设置亮度vs饱和度曲线"""
        try:
            node.SetParameterValue("Luma vs Sat", curve_points)
            return True
        except Exception as e:
            print(f"设置亮度vs饱和度曲线失败: {e}")
            return False
    
    def apply_orange_teal_look(self, node):
        """应用青橙色调"""
        hue_vs_hue = [
            [0, 0],
            [0.08, 0.05],
            [0.15, 0],
            [0.55, 0],
            [0.62, 0.03],
            [0.7, 0],
            [1, 0]
        ]
        
        hue_vs_sat = [
            [0, 0],
            [0.12, 0.15],
            [0.18, 0],
            [0.58, 0],
            [0.65, 0.15],
            [0.72, 0],
            [1, 0]
        ]
        
        success = self.set_hue_vs_hue(node, hue_vs_hue)
        success &= self.set_hue_vs_sat(node, hue_vs_sat)
        
        return success
    
    def desaturate_neutrals(self, node):
        """降低中性色饱和度"""
        sat_vs_sat = [
            [0, 0],
            [0.1, 0],
            [0.2, -0.2],
            [0.8, -0.2],
            [0.9, 0],
            [1, 0]
        ]
        
        return self.set_sat_vs_sat(node, sat_vs_sat)
```

---

## 五、一级校色技术

### 5.1 白平衡调整

```python
class WhiteBalanceTools:
    """白平衡调整工具"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def set_temp(self, node, value):
        """设置色温"""
        try:
            node.SetParameterValue("Temp", value)
            return True
        except Exception as e:
            print(f"设置色温失败: {e}")
            return False
    
    def set_tint(self, node, value):
        """设置色调"""
        try:
            node.SetParameterValue("Tint", value)
            return True
        except Exception as e:
            print(f"设置色调失败: {e}")
            return False
    
    def set_white_balance(self, node, temp, tint):
        """设置白平衡"""
        success = self.set_temp(node, temp)
        success &= self.set_tint(node, tint)
        return success
    
    def auto_white_balance(self, node):
        """自动白平衡"""
        try:
            node.AutoWhiteBalance()
            return True
        except Exception as e:
            print(f"自动白平衡失败: {e}")
            return False
    
    def apply_daylight_balance(self, node):
        """应用日光白平衡"""
        return self.set_white_balance(node, 5500, 0)
    
    def apply_tungsten_balance(self, node):
        """应用钨丝灯白平衡"""
        return self.set_white_balance(node, 3200, 0)
    
    def apply_shade_balance(self, node):
        """应用阴影白平衡"""
        return self.set_white_balance(node, 7000, -10)
    
    def apply_cloudy_balance(self, node):
        """应用阴天白平衡"""
        return self.set_white_balance(node, 6500, 5)
```

### 5.2 对比度与曝光

```python
class ContrastExposureTools:
    """对比度与曝光调整工具"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def set_contrast(self, node, value):
        """设置对比度"""
        try:
            node.SetParameterValue("Contrast", value)
            return True
        except Exception as e:
            print(f"设置对比度失败: {e}")
            return False
    
    def set_pivot(self, node, value):
        """设置对比度中心"""
        try:
            node.SetParameterValue("Contrast Pivot", value)
            return True
        except Exception as e:
            print(f"设置对比度中心失败: {e}")
            return False
    
    def set_exposure(self, node, value):
        """设置曝光"""
        try:
            node.SetParameterValue("Exposure", value)
            return True
        except Exception as e:
            print(f"设置曝光失败: {e}")
            return False
    
    def set_contrast_lift(self, node, value):
        """设置对比度Lift"""
        try:
            node.SetParameterValue("Contrast Lift", value)
            return True
        except Exception as e:
            print(f"设置对比度Lift失败: {e}")
            return False
    
    def set_contrast_gamma(self, node, value):
        """设置对比度Gamma"""
        try:
            node.SetParameterValue("Contrast Gamma", value)
            return True
        except Exception as e:
            print(f"设置对比度Gamma失败: {e}")
            return False
    
    def set_contrast_gain(self, node, value):
        """设置对比度Gain"""
        try:
            node.SetParameterValue("Contrast Gain", value)
            return True
        except Exception as e:
            print(f"设置对比度Gain失败: {e}")
            return False
    
    def apply_standard_contrast(self, node):
        """应用标准对比度"""
        return self.set_contrast(node, 1.0)
    
    def apply_high_contrast(self, node):
        """应用高对比度"""
        return self.set_contrast(node, 1.2)
    
    def apply_low_contrast(self, node):
        """应用低对比度"""
        return self.set_contrast(node, 0.8)
```

---

## 六、二级调色技术

### 6.1 限定器

```python
class QualifierTools:
    """限定器工具"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def set_hue_range(self, node, start, end):
        """设置色相范围"""
        try:
            node.SetParameterValue("Hue Low", start)
            node.SetParameterValue("Hue High", end)
            return True
        except Exception as e:
            print(f"设置色相范围失败: {e}")
            return False
    
    def set_saturation_range(self, node, start, end):
        """设置饱和度范围"""
        try:
            node.SetParameterValue("Sat Low", start)
            node.SetParameterValue("Sat High", end)
            return True
        except Exception as e:
            print(f"设置饱和度范围失败: {e}")
            return False
    
    def set_luma_range(self, node, start, end):
        """设置亮度范围"""
        try:
            node.SetParameterValue("Luma Low", start)
            node.SetParameterValue("Luma High", end)
            return True
        except Exception as e:
            print(f"设置亮度范围失败: {e}")
            return False
    
    def set_feather(self, node, value):
        """设置羽化"""
        try:
            node.SetParameterValue("Feather", value)
            return True
        except Exception as e:
            print(f"设置羽化失败: {e}")
            return False
    
    def set_blur(self, node, value):
        """设置模糊"""
        try:
            node.SetParameterValue("Blur", value)
            return True
        except Exception as e:
            print(f"设置模糊失败: {e}")
            return False
    
    def select_skin_tone(self, node):
        """选择肤色"""
        return self.set_hue_range(node, 0.05, 0.18)
    
    def select_sky(self, node):
        """选择天空"""
        return self.set_hue_range(node, 0.55, 0.72)
    
    def select_grass(self, node):
        """选择草地"""
        return self.set_hue_range(node, 0.25, 0.4)
    
    def select_warm_colors(self, node):
        """选择暖色"""
        success = self.set_hue_range(node, 0, 0.2)
        success &= self.set_hue_range(node, 0.85, 1.0)
        return success
    
    def select_cool_colors(self, node):
        """选择冷色"""
        return self.set_hue_range(node, 0.45, 0.75)
```

### 6.2 动态窗口

```python
class PowerWindowTools:
    """动态窗口工具"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def create_circular_window(self, node, center_x=0.5, center_y=0.5, radius=0.2):
        """创建圆形窗口"""
        try:
            node.SetParameterValue("Window Type", "Circle")
            node.SetParameterValue("Center X", center_x)
            node.SetParameterValue("Center Y", center_y)
            node.SetParameterValue("Radius", radius)
            return True
        except Exception as e:
            print(f"创建圆形窗口失败: {e}")
            return False
    
    def create_linear_window(self, node, start_x=0.2, start_y=0.3, end_x=0.8, end_y=0.7):
        """创建线性窗口"""
        try:
            node.SetParameterValue("Window Type", "Linear")
            node.SetParameterValue("Start X", start_x)
            node.SetParameterValue("Start Y", start_y)
            node.SetParameterValue("End X", end_x)
            node.SetParameterValue("End Y", end_y)
            return True
        except Exception as e:
            print(f"创建线性窗口失败: {e}")
            return False
    
    def create_polygon_window(self, node, points):
        """创建多边形窗口"""
        try:
            node.SetParameterValue("Window Type", "Polygon")
            
            for i, point in enumerate(points):
                node.SetParameterValue(f"Point {i+1} X", point[0])
                node.SetParameterValue(f"Point {i+1} Y", point[1])
            
            return True
        except Exception as e:
            print(f"创建多边形窗口失败: {e}")
            return False
    
    def create_gradient_window(self, node, center_x=0.5, center_y=0.5, angle=0):
        """创建渐变窗口"""
        try:
            node.SetParameterValue("Window Type", "Gradient")
            node.SetParameterValue("Center X", center_x)
            node.SetParameterValue("Center Y", center_y)
            node.SetParameterValue("Angle", angle)
            return True
        except Exception as e:
            print(f"创建渐变窗口失败: {e}")
            return False
    
    def set_window_feather(self, node, inner=0.05, outer=0.1):
        """设置窗口羽化"""
        try:
            node.SetParameterValue("Feather Inner", inner)
            node.SetParameterValue("Feather Outer", outer)
            return True
        except Exception as e:
            print(f"设置窗口羽化失败: {e}")
            return False
    
    def enable_tracking(self, node):
        """启用跟踪"""
        try:
            node.SetParameterValue("Track", 1)
            return True
        except Exception as e:
            print(f"启用跟踪失败: {e}")
            return False
    
    def disable_tracking(self, node):
        """禁用跟踪"""
        try:
            node.SetParameterValue("Track", 0)
            return True
        except Exception as e:
            print(f"禁用跟踪失败: {e}")
            return False
```

---

## 七、LUT系统与应用

### 7.1 LUT管理

```python
class LUTManager:
    """LUT管理器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def apply_lut(self, node, lut_path):
        """应用LUT"""
        try:
            node.SetParameterValue("LUT", lut_path)
            node.SetParameterValue("LUT On", 1)
            return True
        except Exception as e:
            print(f"应用LUT失败: {e}")
            return False
    
    def set_lut_strength(self, node, strength=1.0):
        """设置LUT强度"""
        try:
            node.SetParameterValue("LUT Mix", strength)
            return True
        except Exception as e:
            print(f"设置LUT强度失败: {e}")
            return False
    
    def create_lut_from_node(self, node, output_path):
        """从节点创建LUT"""
        try:
            node.ExportLUT(output_path)
            return True
        except Exception as e:
            print(f"导出LUT失败: {e}")
            return False
    
    def apply_camera_lut(self, node, lut_path):
        """应用摄像机LUT"""
        try:
            node.SetParameterValue("Camera LUT", lut_path)
            node.SetParameterValue("Camera LUT On", 1)
            return True
        except Exception as e:
            print(f"应用摄像机LUT失败: {e}")
            return False
    
    def apply_creative_lut(self, node, lut_path):
        """应用创意LUT"""
        return self.apply_lut(node, lut_path)
    
    def batch_apply_lut(self, clips, lut_path, strength=1.0):
        """批量应用LUT"""
        success_count = 0
        
        for clip in clips:
            node_graph = clip.GetNodeGraph()
            node = node_graph.GetFirstNode()
            
            if node:
                if self.apply_lut(node, lut_path):
                    self.set_lut_strength(node, strength)
                    success_count += 1
        
        return success_count
    
    def get_available_luts(self):
        """获取可用LUT列表"""
        try:
            project = self.engine.get_project()
            color_page = project.GetColorPage()
            return color_page.GetAvailableLUTs()
        except Exception as e:
            print(f"获取LUT列表失败: {e}")
            return []
```

### 7.2 LUT应用流程

```python
class LUTApplicationWorkflow:
    """LUT应用工作流"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.lut_manager = LUTManager(resolve_engine)
    
    def apply_grading_chain(self, node):
        """应用完整调色链"""
        try:
            # 1. 应用摄像机LUT（如果有）
            camera_lut_path = "D:/LUTs/Camera/RED_Log_709.lut"
            self.lut_manager.apply_camera_lut(node, camera_lut_path)
            
            # 2. 一级校色
            color_wheel = ColorWheelSystem(self.engine)
            color_wheel.apply_color_balance(
                node,
                lift=[0, 0, 0],
                gamma=[0, 0, 0],
                gain=[0, 0, 0]
            )
            
            # 3. 曲线调整
            curves = RGBCurveTools(self.engine)
            curves.apply_contrast_curve(node)
            
            # 4. 应用创意LUT
            creative_lut_path = "D:/LUTs/Creative/Cinematic_01.lut"
            self.lut_manager.apply_creative_lut(node, creative_lut_path)
            self.lut_manager.set_lut_strength(node, 0.6)
            
            return True
        except Exception as e:
            print(f"应用调色链失败: {e}")
            return False
    
    def apply_film_emulation(self, node, film_type="Kodak_2383"):
        """应用胶片模拟"""
        lut_paths = {
            "Kodak_2383": "D:/LUTs/Film/Kodak_2383.lut",
            "Kodak_2203": "D:/LUTs/Film/Kodak_2203.lut",
            "Fuji_3510": "D:/LUTs/Film/Fuji_3510.lut",
            "Fuji_3500": "D:/LUTs/Film/Fuji_3500.lut",
            "Sony_S-Log3": "D:/LUTs/Film/Sony_S-Log3.lut"
        }
        
        lut_path = lut_paths.get(film_type)
        
        if lut_path:
            return self.lut_manager.apply_lut(node, lut_path)
        
        return False
    
    def apply_log_conversion(self, node, camera_type="RED"):
        """应用Log转换"""
        lut_paths = {
            "RED": "D:/LUTs/Log/RED_Log_to_709.lut",
            "Sony": "D:/LUTs/Log/Sony_S-Log3_to_709.lut",
            "Canon": "D:/LUTs/Log/Canon_C-Log_to_709.lut",
            "Panasonic": "D:/LUTs/Log/Panasonic_V-Log_to_709.lut",
            "Arri": "D:/LUTs/Log/Arri_LogC_to_709.lut"
        }
        
        lut_path = lut_paths.get(camera_type)
        
        if lut_path:
            return self.lut_manager.apply_camera_lut(node, lut_path)
        
        return False
```

---

## 八、Color页面API自动化

### 8.1 Color页面自动化引擎

```python
class ColorPageAutomation:
    """Color页面自动化引擎"""
    
    def __init__(self):
        self.resolve = None
        self.project_manager = None
        self.project = None
        self.color_page = None
        self.node_graph = None
    
    def initialize(self):
        """初始化Resolve"""
        import DaVinciResolveScript as bmd
        
        self.resolve = bmd.scriptapp("Resolve")
        if not self.resolve:
            return False
        
        self.project_manager = self.resolve.GetProjectManager()
        self.project = self.project_manager.GetCurrentProject()
        
        if not self.project:
            return False
        
        self.color_page = self.project.GetColorPage()
        if not self.color_page:
            return False
        
        self.node_graph = self.color_page.GetNodeGraph()
        
        return True
    
    def apply_auto_color_grade(self, timeline):
        """应用自动调色"""
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    # 获取或创建校正节点
                    node_graph = clip.GetNodeGraph()
                    
                    if not node_graph.GetNodes():
                        node_graph.AddNode("Corrector")
                    
                    nodes = node_graph.GetNodes()
                    if nodes:
                        corrector = nodes[0]
                        
                        # 自动白平衡
                        corrector.AutoWhiteBalance()
                        
                        # 应用默认对比度
                        corrector.SetParameterValue("Contrast", 1.0)
            
            return True
        except Exception as e:
            print(f"应用自动调色失败: {e}")
            return False
    
    def apply_cinematic_look(self, timeline):
        """应用电影风格调色"""
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    node_graph = clip.GetNodeGraph()
                    
                    # 创建校正节点
                    corrector = node_graph.AddNode("Corrector")
                    
                    # 应用电影风格
                    corrector.SetParameterValue("Lift", [0.08, 0.03, -0.03])
                    corrector.SetParameterValue("Gamma", [0, 0, 0])
                    corrector.SetParameterValue("Gain", [0.02, -0.02, -0.05])
                    corrector.SetParameterValue("Contrast", 1.1)
                    corrector.SetParameterValue("Saturation", 0.95)
            
            return True
        except Exception as e:
            print(f"应用电影风格调色失败: {e}")
            return False
    
    def batch_apply_lut(self, timeline, lut_path):
        """批量应用LUT"""
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    node_graph = clip.GetNodeGraph()
                    nodes = node_graph.GetNodes()
                    
                    if nodes:
                        node = nodes[0]
                        node.SetParameterValue("LUT", lut_path)
                        node.SetParameterValue("LUT On", 1)
            
            return True
        except Exception as e:
            print(f"批量应用LUT失败: {e}")
            return False
```

### 8.2 脚本执行示例

```python
# Color页面自动化脚本示例

def run_color_page_automation():
    """运行Color页面自动化"""
    automation = ColorPageAutomation()
    
    if not automation.initialize():
        print("Resolve初始化失败")
        return
    
    # 获取当前时间线
    timeline = automation.project.GetCurrentTimeline()
    
    if not timeline:
        print("未找到时间线")
        return
    
    # 应用自动调色
    if automation.apply_auto_color_grade(timeline):
        print("自动调色完成")
    else:
        print("自动调色失败")
    
    # 应用电影风格
    if automation.apply_cinematic_look(timeline):
        print("电影风格调色完成")
    else:
        print("电影风格调色失败")
    
    # 批量应用LUT
    if automation.batch_apply_lut(timeline, "D:/LUTs/Cinematic_01.lut"):
        print("批量应用LUT完成")
    else:
        print("批量应用LUT失败")

if __name__ == "__main__":
    run_color_page_automation()
```

---

## 九、故障排查

### 9.1 常见问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| **颜色异常** | LUT加载错误或色彩空间不匹配 | 检查LUT路径和色彩空间设置 |
| **节点渲染失败** | 节点参数超出范围或连接错误 | 检查节点参数和连接 |
| **跟踪漂移** | 跟踪设置不当或画面变化过大 | 调整跟踪参数或重新跟踪 |
| **窗口边缘明显** | 羽化不足或模糊不够 | 增加羽化和模糊参数 |
| **性能下降** | 节点过多或特效过于复杂 | 减少节点数量或简化特效 |
| **导出颜色不一致** | 渲染设置或色彩管理问题 | 检查渲染设置和色彩管理 |

### 9.2 故障排查工具

```python
class ColorPageTroubleshooter:
    """Color页面故障排查"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def check_node_errors(self, timeline):
        """检查节点错误"""
        errors = []
        
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    node_graph = clip.GetNodeGraph()
                    nodes = node_graph.GetNodes()
                    
                    for node in nodes:
                        if not node.IsValid():
                            errors.append({
                                "clip": clip.GetName(),
                                "node": node.GetName(),
                                "error": "无效节点"
                            })
            
            return errors
        except Exception as e:
            print(f"检查节点错误失败: {e}")
            return []
    
    def check_lut_loading(self, timeline):
        """检查LUT加载"""
        errors = []
        
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    node_graph = clip.GetNodeGraph()
                    nodes = node_graph.GetNodes()
                    
                    for node in nodes:
                        lut_path = node.GetParameterValue("LUT")
                        
                        if lut_path and not os.path.exists(lut_path):
                            errors.append({
                                "clip": clip.GetName(),
                                "node": node.GetName(),
                                "lut_path": lut_path,
                                "error": "LUT文件不存在"
                            })
            
            return errors
        except Exception as e:
            print(f"检查LUT加载失败: {e}")
            return []
    
    def check_color_space(self, timeline):
        """检查色彩空间"""
        issues = []
        
        try:
            timeline_settings = timeline.GetSetting("timelineColorSpace")
            project_settings = self.engine.get_project().GetSetting("projectColorSpace")
            
            if timeline_settings != project_settings:
                issues.append({
                    "type": "color_space_mismatch",
                    "timeline_space": timeline_settings,
                    "project_space": project_settings
                })
            
            return issues
        except Exception as e:
            print(f"检查色彩空间失败: {e}")
            return []
```

---

## 十、性能优化

### 10.1 Color页面性能优化策略

```python
class ColorPagePerformanceOptimizer:
    """Color页面性能优化"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def optimize_render_cache(self):
        """优化渲染缓存"""
        try:
            project = self.engine.get_project()
            
            project.SetCacheSettings({
                "CacheMode": "Smart",
                "PreRenderEffects": True,
                "CacheOnImport": False,
                "CacheLocation": "D:/ResolveCache"
            })
            
            return True
        except Exception as e:
            print(f"优化渲染缓存失败: {e}")
            return False
    
    def reduce_node_complexity(self, timeline, max_nodes=10):
        """减少节点复杂度"""
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    node_graph = clip.GetNodeGraph()
                    nodes = node_graph.GetNodes()
                    
                    # 如果节点过多，禁用多余节点
                    if len(nodes) > max_nodes:
                        for i, node in enumerate(nodes):
                            if i >= max_nodes:
                                node.SetEnabled(False)
            
            return True
        except Exception as e:
            print(f"减少节点复杂度失败: {e}")
            return False
    
    def disable_secondary_grades(self, timeline):
        """禁用二级调色"""
        try:
            tracks = timeline.GetTracks()
            video_tracks = tracks.GetVideoTracks()
            
            for track in video_tracks:
                clips = track.GetItemsInTrack()
                
                for clip in clips:
                    node_graph = clip.GetNodeGraph()
                    nodes = node_graph.GetNodes()
                    
                    for node in nodes:
                        node_type = node.GetType()
                        
                        if node_type in ["Qualifier", "PowerWindow", "Tracker"]:
                            node.SetEnabled(False)
            
            return True
        except Exception as e:
            print(f"禁用二级调色失败: {e}")
            return False
    
    def optimize_viewer_settings(self):
        """优化视图设置"""
        try:
            project = self.engine.get_project()
            
            project.SetViewerSettings({
                "Resolution": "Half",
                "Quality": "Draft",
                "DisableEffects": False,
                "UseGPUAcceleration": True
            })
            
            return True
        except Exception as e:
            print(f"优化视图设置失败: {e}")
            return False
```

### 10.2 GPU加速配置

```python
class GPUAccelerationConfig:
    """GPU加速配置"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def configure_gpu_for_color(self):
        """配置GPU加速"""
        try:
            gpus = self.engine.resolve.GetGPUs()
            
            if not gpus:
                return False
            
            # 设置主GPU
            primary_gpu = gpus[0]
            self.engine.resolve.SetPrimaryGPU(primary_gpu.GetID())
            
            # 启用CUDA加速
            self.engine.resolve.SetGPUAccelerationMode("CUDA")
            
            # 启用OpenCL加速
            self.engine.resolve.SetOpenCLAcceleration(True)
            
            return True
        except Exception as e:
            print(f"配置GPU加速失败: {e}")
            return False
    
    def check_gpu_status(self):
        """检查GPU状态"""
        try:
            gpus = self.engine.resolve.GetGPUs()
            
            gpu_status = []
            for gpu in gpus:
                gpu_status.append({
                    "name": gpu.GetName(),
                    "memory": gpu.GetMemory(),
                    "status": gpu.GetStatus(),
                    "acceleration": gpu.IsAccelerated()
                })
            
            return gpu_status
        except Exception as e:
            print(f"检查GPU状态失败: {e}")
            return []
```

---

## 附录：Color页面参数速查表

### 色轮参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `Lift` | list | [-1,1] x 3 | 黑电平调整 |
| `Gamma` | list | [-1,1] x 3 | 伽马调整 |
| `Gain` | list | [-1,1] x 3 | 白电平调整 |
| `Offset` | list | [-1,1] x 3 | 偏移调整 |
| `Lift Saturation` | float | -1-1 | Lift饱和度 |
| `Gamma Saturation` | float | -1-1 | Gamma饱和度 |
| `Gain Saturation` | float | -1-1 | Gain饱和度 |

### 白平衡参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `Temp` | float | 1500-20000 | 色温(K) |
| `Tint` | float | -100-100 | 色调 |

### 对比度参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `Contrast` | float | 0-3 | 对比度 |
| `Contrast Pivot` | float | 0-1 | 对比度中心 |
| `Exposure` | float | -5-5 | 曝光 |

### LUT参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `LUT` | str | 文件路径 | LUT文件路径 |
| `LUT On` | int | 0-1 | LUT开关 |
| `LUT Mix` | float | 0-1 | LUT混合强度 |
| `Camera LUT` | str | 文件路径 | 摄像机LUT路径 |
| `Camera LUT On` | int | 0-1 | 摄像机LUT开关 |

### 限定器参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `Hue Low` | float | 0-1 | 色相下限 |
| `Hue High` | float | 0-1 | 色相上限 |
| `Sat Low` | float | 0-1 | 饱和度下限 |
| `Sat High` | float | 0-1 | 饱和度上限 |
| `Luma Low` | float | 0-1 | 亮度下限 |
| `Luma High` | float | 0-1 | 亮度上限 |
| `Feather` | float | 0-1 | 羽化 |
| `Blur` | float | 0-100 | 模糊 |