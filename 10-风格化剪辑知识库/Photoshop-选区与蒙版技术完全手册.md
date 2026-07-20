# Photoshop 选区与蒙版技术完全手册

> 适用版本：Adobe Photoshop 2026 | 更新日期：2026-07-14 | 分类：Photoshop知识库

---

## 目录

- [一、选区技术基础](#一选区技术基础)
- [二、选框工具详解](#二选框工具详解)
- [三、套索工具详解](#三套索工具详解)
- [四、快速选择与魔棒工具](#四快速选择与魔棒工具)
- [五、钢笔工具与路径选区](#五钢笔工具与路径选区)
- [六、选区操作与变换](#六选区操作与变换)
- [七、蒙版技术体系](#七蒙版技术体系)
- [八、图层蒙版详解](#八图层蒙版详解)
- [九、剪贴蒙版详解](#九剪贴蒙版详解)
- [十、快速蒙版模式](#十快速蒙版模式)
- [十一、矢量蒙版详解](#十一矢量蒙版详解)
- [十二、混合选项蒙版](#十二混合选项蒙版)
- [十三、选区与蒙版自动化API](#十三选区与蒙版自动化api)
- [十四、故障排查与性能优化](#十四故障排查与性能优化)

---

## 一、选区技术基础

### 1.1 选区概念与原理

```javascript
// 选区核心概念
// Selection (选区): 定义图像中可编辑的区域
// Marquee (选框): 几何形状的选区工具
// Lasso (套索): 自由手绘选区工具
// Path (路径): 矢量线条，可转换为选区
// Mask (蒙版): 通过灰度控制选区透明度
```

### 1.2 选区类型分类

```javascript
class SelectionType {
    static get TYPES() {
        return {
            GEOMETRIC: {
                name: '几何选区',
                tools: ['矩形选框', '椭圆选框', '单行选框', '单列选框'],
                uses: ['规则区域选择', '对齐裁剪']
            },
            FREEHAND: {
                name: '自由选区',
                tools: ['套索', '多边形套索', '磁性套索'],
                uses: ['不规则形状', '边缘追踪']
            },
            COLOR_BASED: {
                name: '颜色选区',
                tools: ['魔棒', '快速选择', '色彩范围'],
                uses: ['相似颜色区域', '快速抠图']
            },
            PATH_BASED: {
                name: '路径选区',
                tools: ['钢笔工具', '形状工具'],
                uses: ['精确轮廓', '矢量选区']
            }
        };
    }
}
```

### 1.3 选区与蒙版的关系

```javascript
// 选区与蒙版的核心关系
// 选区 → 二进制蒙版（0或255）
// 蒙版 → 灰度选区（0-255，支持半透明）
// 选区是蒙版的简化形式，蒙版是选区的扩展形式

function selectionToMask(selection) {
    return {
        type: 'mask',
        data: selection.map(pixel => pixel ? 255 : 0),
        hasFeather: selection.feather > 0
    };
}

function maskToSelection(mask, threshold = 128) {
    return mask.data.map(pixel => pixel >= threshold);
}
```

---

## 二、选框工具详解

### 2.1 矩形选框工具

```javascript
class RectangularMarqueeTool {
    constructor() {
        this.tool = 'Rectangular Marquee Tool';
        this.shortcut = 'M';
        this.mode = 'normal';
        this.feather = 0;
        this.antiAlias = true;
        this.aspectRatio = 'normal';
    }

    createSelection(x, y, width, height) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Mn  '));
        desc.putEnumerated(charIDToTypeID('MkVd'), charIDToTypeID('MkVd'), charIDToTypeID('Arbn'));
        desc.putUnitDouble(charIDToTypeID('Top '), charIDToTypeID('#Pxl'), y);
        desc.putUnitDouble(charIDToTypeID('Left'), charIDToTypeID('#Pxl'), x);
        desc.putUnitDouble(charIDToTypeID('Btom'), charIDToTypeID('#Pxl'), y + height);
        desc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), x + width);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        return true;
    }

    setFixedAspectRatio(width, height) {
        this.aspectRatio = { width, height };
        const desc = new ActionDescriptor();
        desc.putEnumerated(charIDToTypeID('ApAs'), charIDToTypeID('ApAs'), charIDToTypeID('CstS'));
        desc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Prc'), width);
        desc.putUnitDouble(charIDToTypeID('Hght'), charIDToTypeID('#Prc'), height);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

### 2.2 椭圆选框工具

```javascript
class EllipticalMarqueeTool {
    constructor() {
        this.tool = 'Elliptical Marquee Tool';
        this.shortcut = 'M';
        this.mode = 'normal';
        this.feather = 0;
        this.antiAlias = true;
        this.aspectRatio = 'normal';
    }

    createSelection(x, y, width, height) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Mn  '));
        desc.putEnumerated(charIDToTypeID('MkVd'), charIDToTypeID('MkVd'), charIDToTypeID('Elps'));
        desc.putUnitDouble(charIDToTypeID('Top '), charIDToTypeID('#Pxl'), y);
        desc.putUnitDouble(charIDToTypeID('Left'), charIDToTypeID('#Pxl'), x);
        desc.putUnitDouble(charIDToTypeID('Btom'), charIDToTypeID('#Pxl'), y + height);
        desc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), x + width);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        return true;
    }

    createCircleSelection(x, y, radius) {
        this.setFixedAspectRatio(1, 1);
        return this.createSelection(x - radius, y - radius, radius * 2, radius * 2);
    }
}
```

### 2.3 选框工具模式

```javascript
// 选框工具四种模式
// 新选区 (New): 替换当前选区
// 添加到选区 (Add): 与当前选区合并
// 从选区减去 (Subtract): 从当前选区移除
// 与选区交叉 (Intersect): 取交集

class MarqueeMode {
    static get NEW() { return charIDToTypeID('FrgC'); }
    static get ADD() { return charIDToTypeID('Addt'); }
    static get SUBTRACT() { return charIDToTypeID('Sbtr'); }
    static get INTERSECT() { return charIDToTypeID('Intr'); }

    static setMode(mode) {
        const desc = new ActionDescriptor();
        desc.putEnumerated(charIDToTypeID('MkMd'), charIDToTypeID('MkMd'), mode);
        executeAction(charIDToTypeID('SetM'), desc, DialogModes.NO);
    }
}
```

---

## 三、套索工具详解

### 3.1 套索工具

```javascript
class LassoTool {
    constructor() {
        this.tool = 'Lasso Tool';
        this.shortcut = 'L';
        this.feather = 0;
        this.antiAlias = true;
        this.mode = 'normal';
    }

    createFreehandSelection(points) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Mn  '));
        
        const pathRef = new ActionReference();
        pathRef.putClass(charIDToTypeID('Path'));
        
        desc.putReference(charIDToTypeID('null'), pathRef);
        
        const pathDesc = new ActionDescriptor();
        
        const subPathList = new ActionList();
        const subPathDesc = new ActionDescriptor();
        
        subPathDesc.putEnumerated(charIDToTypeID('SbPt'), charIDToTypeID('SbPt'), charIDToTypeID('Closed'));
        
        const anchorList = new ActionList();
        points.forEach(point => {
            const anchorDesc = new ActionDescriptor();
            anchorDesc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Pxl'), point.x);
            anchorDesc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Pxl'), point.y);
            anchorList.putObject(charIDToTypeID('Anch'), anchorDesc);
        });
        
        subPathDesc.putList(charIDToTypeID('Anch'), anchorList);
        subPathList.putObject(charIDToTypeID('SbPt'), subPathDesc);
        
        pathDesc.putList(charIDToTypeID('Pth '), subPathList);
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
}
```

### 3.2 多边形套索工具

```javascript
class PolygonLassoTool {
    constructor() {
        this.tool = 'Polygon Lasso Tool';
        this.shortcut = 'L';
        this.feather = 0;
        this.antiAlias = true;
        this.mode = 'normal';
    }

    createPolygonSelection(vertices) {
        if (vertices.length < 3) {
            throw new Error('多边形至少需要3个顶点');
        }
        
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Mn  '));
        
        const pathRef = new ActionReference();
        pathRef.putClass(charIDToTypeID('Path'));
        
        desc.putReference(charIDToTypeID('null'), pathRef);
        
        const pathDesc = new ActionDescriptor();
        const subPathList = new ActionList();
        const subPathDesc = new ActionDescriptor();
        
        subPathDesc.putEnumerated(charIDToTypeID('SbPt'), charIDToTypeID('SbPt'), charIDToTypeID('Closed'));
        
        const anchorList = new ActionList();
        vertices.forEach(point => {
            const anchorDesc = new ActionDescriptor();
            anchorDesc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Pxl'), point.x);
            anchorDesc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Pxl'), point.y);
            anchorDesc.putBoolean(charIDToTypeID('Crnv'), true);
            anchorList.putObject(charIDToTypeID('Anch'), anchorDesc);
        });
        
        subPathDesc.putList(charIDToTypeID('Anch'), anchorList);
        subPathList.putObject(charIDToTypeID('SbPt'), subPathDesc);
        
        pathDesc.putList(charIDToTypeID('Pth '), subPathList);
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
}
```

### 3.3 磁性套索工具

```javascript
class MagneticLassoTool {
    constructor() {
        this.tool = 'Magnetic Lasso Tool';
        this.shortcut = 'L';
        this.feather = 0;
        this.antiAlias = true;
        this.width = 10;
        this.contrast = 10;
        this.frequency = 57;
    }

    setDetectionWidth(width) {
        this.width = Math.max(1, Math.min(256, width));
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Pxl'), this.width);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    setEdgeContrast(contrast) {
        this.contrast = Math.max(1, Math.min(100, contrast));
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Cn  '), charIDToTypeID('#Prc'), this.contrast);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    setFrequency(frequency) {
        this.frequency = Math.max(0, Math.min(100, frequency));
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Frq '), charIDToTypeID('#Prc'), this.frequency);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

---

## 四、快速选择与魔棒工具

### 4.1 快速选择工具

```javascript
class QuickSelectionTool {
    constructor() {
        this.tool = 'Quick Selection Tool';
        this.shortcut = 'W';
        this.mode = 'new';
        this.sampleAllLayers = false;
        this.autoEnhance = false;
        this.brushSize = 10;
    }

    setBrushSize(size) {
        this.brushSize = Math.max(1, Math.min(2500, size));
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Size'), charIDToTypeID('#Pxl'), this.brushSize);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    enableSampleAllLayers(enable) {
        this.sampleAllLayers = enable;
        const desc = new ActionDescriptor();
        desc.putBoolean(charIDToTypeID('Smpl'), enable);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    enableAutoEnhance(enable) {
        this.autoEnhance = enable;
        const desc = new ActionDescriptor();
        desc.putBoolean(charIDToTypeID('Enhn'), enable);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

### 4.2 魔棒工具

```javascript
class MagicWandTool {
    constructor() {
        this.tool = 'Magic Wand Tool';
        this.shortcut = 'W';
        this.tolerance = 32;
        this.antiAlias = true;
        this.contiguous = true;
        this.sampleAllLayers = false;
    }

    setTolerance(tolerance) {
        this.tolerance = Math.max(0, Math.min(255, tolerance));
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Tol '), charIDToTypeID('#Prc'), this.tolerance);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    setContiguous(contiguous) {
        this.contiguous = contiguous;
        const desc = new ActionDescriptor();
        desc.putBoolean(charIDToTypeID('Cntg'), contiguous);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    selectByColor(x, y) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Mn  '));
        desc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Pxl'), x);
        desc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Pxl'), y);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
}
```

### 4.3 色彩范围命令

```javascript
class ColorRangeCommand {
    constructor() {
        this.selectionPreview = 'none';
        this.localizedColorClusters = false;
        this.fuzziness = 40;
    }

    selectByColorRange(color, fuzziness = 40) {
        this.fuzziness = Math.max(0, Math.min(200, fuzziness));
        
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('CrRg'));
        
        desc.putEnumerated(charIDToTypeID('CrRg'), charIDToTypeID('CrRg'), charIDToTypeID('Clr '));
        desc.putUnitDouble(charIDToTypeID('Fzns'), charIDToTypeID('#Prc'), this.fuzziness);
        
        const colorDesc = new ActionDescriptor();
        colorDesc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Prc'), color.r);
        colorDesc.putUnitDouble(charIDToTypeID('Grn '), charIDToTypeID('#Prc'), color.g);
        colorDesc.putUnitDouble(charIDToTypeID('Bl  '), charIDToTypeID('#Prc'), color.b);
        
        desc.putObject(charIDToTypeID('Clr '), charIDToTypeID('Clr '), colorDesc);
        
        executeAction(charIDToTypeID('CrRg'), desc, DialogModes.NO);
    }

    selectBySkinTone() {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('CrRg'));
        desc.putEnumerated(charIDToTypeID('CrRg'), charIDToTypeID('CrRg'), charIDToTypeID('SkT '));
        executeAction(charIDToTypeID('CrRg'), desc, DialogModes.NO);
    }
}
```

---

## 五、钢笔工具与路径选区

### 5.1 钢笔工具基础

```javascript
class PenTool {
    constructor() {
        this.tool = 'Pen Tool';
        this.shortcut = 'P';
        this.mode = 'path';
        this.rubberBand = false;
        this.autoAddDelete = true;
    }

    createPath(points) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Pth '));
        
        const pathRef = new ActionReference();
        pathRef.putClass(charIDToTypeID('Path'));
        
        desc.putReference(charIDToTypeID('null'), pathRef);
        
        const pathDesc = new ActionDescriptor();
        
        const subPathList = new ActionList();
        const subPathDesc = new ActionDescriptor();
        
        subPathDesc.putEnumerated(charIDToTypeID('SbPt'), charIDToTypeID('SbPt'), charIDToTypeID('Open '));
        
        const anchorList = new ActionList();
        points.forEach(point => {
            const anchorDesc = new ActionDescriptor();
            anchorDesc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Pxl'), point.x);
            anchorDesc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Pxl'), point.y);
            
            if (point.inTangent) {
                anchorDesc.putUnitDouble(charIDToTypeID('In  '), charIDToTypeID('#Pxl'), point.inTangent.x);
                anchorDesc.putUnitDouble(charIDToTypeID('InV '), charIDToTypeID('#Pxl'), point.inTangent.y);
            }
            if (point.outTangent) {
                anchorDesc.putUnitDouble(charIDToTypeID('Out '), charIDToTypeID('#Pxl'), point.outTangent.x);
                anchorDesc.putUnitDouble(charIDToTypeID('OutV'), charIDToTypeID('#Pxl'), point.outTangent.y);
            }
            
            anchorList.putObject(charIDToTypeID('Anch'), anchorDesc);
        });
        
        subPathDesc.putList(charIDToTypeID('Anch'), anchorList);
        subPathList.putObject(charIDToTypeID('SbPt'), subPathDesc);
        
        pathDesc.putList(charIDToTypeID('Pth '), subPathList);
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    createClosedPath(points) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Pth '));
        
        const pathRef = new ActionReference();
        pathRef.putClass(charIDToTypeID('Path'));
        
        desc.putReference(charIDToTypeID('null'), pathRef);
        
        const pathDesc = new ActionDescriptor();
        
        const subPathList = new ActionList();
        const subPathDesc = new ActionDescriptor();
        
        subPathDesc.putEnumerated(charIDToTypeID('SbPt'), charIDToTypeID('SbPt'), charIDToTypeID('Closed'));
        
        const anchorList = new ActionList();
        points.forEach(point => {
            const anchorDesc = new ActionDescriptor();
            anchorDesc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Pxl'), point.x);
            anchorDesc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Pxl'), point.y);
            
            if (point.inTangent) {
                anchorDesc.putUnitDouble(charIDToTypeID('In  '), charIDToTypeID('#Pxl'), point.inTangent.x);
                anchorDesc.putUnitDouble(charIDToTypeID('InV '), charIDToTypeID('#Pxl'), point.inTangent.y);
            }
            if (point.outTangent) {
                anchorDesc.putUnitDouble(charIDToTypeID('Out '), charIDToTypeID('#Pxl'), point.outTangent.x);
                anchorDesc.putUnitDouble(charIDToTypeID('OutV'), charIDToTypeID('#Pxl'), point.outTangent.y);
            }
            
            anchorList.putObject(charIDToTypeID('Anch'), anchorDesc);
        });
        
        subPathDesc.putList(charIDToTypeID('Anch'), anchorList);
        subPathList.putObject(charIDToTypeID('SbPt'), subPathDesc);
        
        pathDesc.putList(charIDToTypeID('Pth '), subPathList);
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
}
```

### 5.2 路径转选区

```javascript
class PathToSelection {
    static convert(feather = 0, antiAlias = true) {
        const desc = new ActionDescriptor();
        
        const pathRef = new ActionReference();
        pathRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), pathRef);
        desc.putUnitDouble(charIDToTypeID('Fthr'), charIDToTypeID('#Pxl'), feather);
        desc.putBoolean(charIDToTypeID('AntA'), antiAlias);
        
        executeAction(charIDToTypeID('Make'), desc, DialogModes.NO);
    }

    static convertWithOptions(options) {
        const desc = new ActionDescriptor();
        
        const pathRef = new ActionReference();
        pathRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), pathRef);
        
        if (options.feather !== undefined) {
            desc.putUnitDouble(charIDToTypeID('Fthr'), charIDToTypeID('#Pxl'), options.feather);
        }
        if (options.antiAlias !== undefined) {
            desc.putBoolean(charIDToTypeID('AntA'), options.antiAlias);
        }
        if (options.mode) {
            desc.putEnumerated(charIDToTypeID('MkMd'), charIDToTypeID('MkMd'), options.mode);
        }
        
        executeAction(charIDToTypeID('Make'), desc, DialogModes.NO);
    }
}
```

### 5.3 形状工具

```javascript
class ShapeTool {
    constructor(shapeType) {
        this.shapeType = shapeType;
        this.mode = 'path';
        this.fillColor = null;
        this.strokeColor = null;
        this.strokeWidth = 1;
    }

    drawRectangle(x, y, width, height) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Shp '));
        desc.putEnumerated(charIDToTypeID('ShpT'), charIDToTypeID('ShpT'), charIDToTypeID('Rctn'));
        
        const pathDesc = new ActionDescriptor();
        pathDesc.putUnitDouble(charIDToTypeID('Top '), charIDToTypeID('#Pxl'), y);
        pathDesc.putUnitDouble(charIDToTypeID('Left'), charIDToTypeID('#Pxl'), x);
        pathDesc.putUnitDouble(charIDToTypeID('Btom'), charIDToTypeID('#Pxl'), y + height);
        pathDesc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), x + width);
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    drawEllipse(x, y, width, height) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Shp '));
        desc.putEnumerated(charIDToTypeID('ShpT'), charIDToTypeID('ShpT'), charIDToTypeID('Elps'));
        
        const pathDesc = new ActionDescriptor();
        pathDesc.putUnitDouble(charIDToTypeID('Top '), charIDToTypeID('#Pxl'), y);
        pathDesc.putUnitDouble(charIDToTypeID('Left'), charIDToTypeID('#Pxl'), x);
        pathDesc.putUnitDouble(charIDToTypeID('Btom'), charIDToTypeID('#Pxl'), y + height);
        pathDesc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), x + width);
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    drawPolygon(x, y, radius, sides = 6) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Shp '));
        desc.putEnumerated(charIDToTypeID('ShpT'), charIDToTypeID('ShpT'), charIDToTypeID('Polg'));
        
        const pathDesc = new ActionDescriptor();
        pathDesc.putUnitDouble(charIDToTypeID('CtrX'), charIDToTypeID('#Pxl'), x);
        pathDesc.putUnitDouble(charIDToTypeID('CtrY'), charIDToTypeID('#Pxl'), y);
        pathDesc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Pxl'), radius);
        pathDesc.putUnitDouble(charIDToTypeID('Sides'), charIDToTypeID('#Pxl'), sides);
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
}
```

---

## 六、选区操作与变换

### 6.1 选区基本操作

```javascript
class SelectionOperations {
    static deselect() {
        executeAction(charIDToTypeID('Dslc'), undefined, DialogModes.NO);
    }

    static reselect() {
        executeAction(charIDToTypeID('Rslc'), undefined, DialogModes.NO);
    }

    static invert() {
        executeAction(charIDToTypeID('Invs'), undefined, DialogModes.NO);
    }

    static saveSelection(name) {
        const desc = new ActionDescriptor();
        desc.putString(charIDToTypeID('Nm  '), name);
        executeAction(charIDToTypeID('SavS'), desc, DialogModes.NO);
    }

    static loadSelection(name) {
        const desc = new ActionDescriptor();
        const chanRef = new ActionReference();
        chanRef.putName(charIDToTypeID('Chnl'), name);
        desc.putReference(charIDToTypeID('null'), chanRef);
        executeAction(charIDToTypeID('Ld  '), desc, DialogModes.NO);
    }
}
```

### 6.2 选区变换

```javascript
class SelectionTransform {
    static freeTransform() {
        executeAction(charIDToTypeID('FrTr'), undefined, DialogModes.NO);
    }

    static scale(widthPercent, heightPercent) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Prc'), widthPercent);
        desc.putUnitDouble(charIDToTypeID('Hght'), charIDToTypeID('#Prc'), heightPercent);
        executeAction(charIDToTypeID('Sc  '), desc, DialogModes.NO);
    }

    static rotate(angle) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('#Ang'), angle);
        executeAction(charIDToTypeID('Rot '), desc, DialogModes.NO);
    }

    static skew(horizontalAngle, verticalAngle) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Ang'), horizontalAngle);
        desc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Ang'), verticalAngle);
        executeAction(charIDToTypeID('Sk  '), desc, DialogModes.NO);
    }

    static distort() {
        executeAction(charIDToTypeID('Dstt'), undefined, DialogModes.NO);
    }

    static perspective() {
        executeAction(charIDToTypeID('Prsp'), undefined, DialogModes.NO);
    }

    static expand(amount) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Amt '), charIDToTypeID('#Pxl'), amount);
        executeAction(charIDToTypeID('Expn'), desc, DialogModes.NO);
    }

    static contract(amount) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Amt '), charIDToTypeID('#Pxl'), amount);
        executeAction(charIDToTypeID('Cntr'), desc, DialogModes.NO);
    }
}
```

### 6.3 选区羽化

```javascript
class SelectionFeather {
    static setFeather(amount) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Fthr'), charIDToTypeID('#Pxl'), amount);
        executeAction(charIDToTypeID('Fthr'), desc, DialogModes.NO);
    }

    static featherSelection(amount) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Amt '), charIDToTypeID('#Pxl'), amount);
        executeAction(charIDToTypeID('Fthr'), desc, DialogModes.NO);
    }

    static refineEdge(options = {}) {
        const desc = new ActionDescriptor();
        
        if (options.radius !== undefined) {
            desc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Pxl'), options.radius);
        }
        if (options.smooth !== undefined) {
            desc.putUnitDouble(charIDToTypeID('Smth'), charIDToTypeID('#Pxl'), options.smooth);
        }
        if (options.feather !== undefined) {
            desc.putUnitDouble(charIDToTypeID('Fthr'), charIDToTypeID('#Pxl'), options.feather);
        }
        if (options.contractExpand !== undefined) {
            desc.putUnitDouble(charIDToTypeID('CnEx'), charIDToTypeID('#Pxl'), options.contractExpand);
        }
        
        executeAction(charIDToTypeID('RfEd'), desc, DialogModes.NO);
    }
}
```

---

## 七、蒙版技术体系

### 7.1 蒙版类型总览

```javascript
class MaskTypeSystem {
    static get TYPES() {
        return {
            LAYER_MASK: {
                name: '图层蒙版',
                icon: '🖼️',
                description: '通过灰度图像控制图层可见性',
                uses: ['合成抠图', '渐变过渡', '局部调整']
            },
            CLIPPING_MASK: {
                name: '剪贴蒙版',
                icon: '📎',
                description: '使用底层图层形状限制上层图层显示',
                uses: ['文字填充', '形状裁剪', '容器效果']
            },
            QUICK_MASK: {
                name: '快速蒙版',
                icon: '⚡',
                description: '临时蒙版模式，用于快速创建选区',
                uses: ['快速选区编辑', '手绘蒙版']
            },
            VECTOR_MASK: {
                name: '矢量蒙版',
                icon: '📐',
                description: '使用矢量路径控制图层可见性',
                uses: ['精确形状裁剪', '可缩放蒙版']
            },
            BLENDING_OPTIONS: {
                name: '混合选项蒙版',
                icon: '🎨',
                description: '通过混合选项创建的蒙版效果',
                uses: ['内阴影', '外发光', '渐变叠加']
            }
        };
    }
}
```

### 7.2 蒙版工作原理

```javascript
// 蒙版工作原理
// 白色 (255): 完全显示
// 黑色 (0): 完全隐藏
// 灰色 (1-254): 半透明显示

function maskOpacityToVisibility(opacity) {
    return opacity / 255;
}

function visibilityToMaskOpacity(visibility) {
    return Math.round(visibility * 255);
}

class MaskEngine {
    static applyMask(layer, maskData) {
        return layer.pixels.map((pixel, i) => {
            const maskValue = maskData[i] / 255;
            return {
                r: pixel.r * maskValue,
                g: pixel.g * maskValue,
                b: pixel.b * maskValue,
                a: pixel.a * maskValue
            };
        });
    }
}
```

---

## 八、图层蒙版详解

### 8.1 创建图层蒙版

```javascript
class LayerMask {
    static add(layer, type = 'reveal') {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        if (type === 'reveal') {
            desc.putEnumerated(charIDToTypeID('MkTy'), charIDToTypeID('MkTy'), charIDToTypeID('Rvl '));
        } else if (type === 'hide') {
            desc.putEnumerated(charIDToTypeID('MkTy'), charIDToTypeID('MkTy'), charIDToTypeID('Hd  '));
        } else if (type === 'selection') {
            desc.putEnumerated(charIDToTypeID('MkTy'), charIDToTypeID('MkTy'), charIDToTypeID('Sel '));
        }
        
        executeAction(charIDToTypeID('AddM'), desc, DialogModes.NO);
    }

    static addRevealAll() {
        this.add(null, 'reveal');
    }

    static addHideAll() {
        this.add(null, 'hide');
    }

    static addFromSelection() {
        this.add(null, 'selection');
    }
}
```

### 8.2 编辑图层蒙版

```javascript
class LayerMaskEditor {
    static enableMaskEditing(enable) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        if (enable) {
            desc.putEnumerated(charIDToTypeID('Usng'), charIDToTypeID('Usng'), charIDToTypeID('Msk '));
        } else {
            desc.putEnumerated(charIDToTypeID('Usng'), charIDToTypeID('Usng'), charIDToTypeID('Img '));
        }
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static disableMask() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Enbl'), false);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static enableMask() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Enbl'), true);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static deleteMask() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('DltM'), desc, DialogModes.NO);
    }

    static applyMask() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('AppM'), desc, DialogModes.NO);
    }
}
```

### 8.3 图层蒙版技巧

```javascript
class LayerMaskTechniques {
    static createGradientMask(gradientType = 'linear', startColor = [255, 255, 255], endColor = [0, 0, 0]) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('MkTy'), charIDToTypeID('MkTy'), charIDToTypeID('Rvl '));
        
        executeAction(charIDToTypeID('AddM'), desc, DialogModes.NO);
        
        this.enableMaskEditing(true);
        
        const gradDesc = new ActionDescriptor();
        gradDesc.putClass(charIDToTypeID('null'), charIDToTypeID('Grad'));
        
        const gradType = gradientType === 'radial' ? charIDToTypeID('RdGr') : charIDToTypeID('LnGr');
        gradDesc.putEnumerated(charIDToTypeID('Grad'), charIDToTypeID('Grad'), gradType);
        
        executeAction(charIDToTypeID('Mk  '), gradDesc, DialogModes.NO);
    }

    static createSoftEdgeMask(featherAmount = 50) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('MkTy'), charIDToTypeID('MkTy'), charIDToTypeID('Rvl '));
        
        executeAction(charIDToTypeID('AddM'), desc, DialogModes.NO);
        
        this.enableMaskEditing(true);
        
        const rectDesc = new ActionDescriptor();
        rectDesc.putClass(charIDToTypeID('null'), charIDToTypeID('Mn  '));
        rectDesc.putEnumerated(charIDToTypeID('MkVd'), charIDToTypeID('MkVd'), charIDToTypeID('Arbn'));
        
        const doc = app.activeDocument;
        rectDesc.putUnitDouble(charIDToTypeID('Top '), charIDToTypeID('#Pxl'), featherAmount);
        rectDesc.putUnitDouble(charIDToTypeID('Left'), charIDToTypeID('#Pxl'), featherAmount);
        rectDesc.putUnitDouble(charIDToTypeID('Btom'), charIDToTypeID('#Pxl'), doc.height - featherAmount);
        rectDesc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), doc.width - featherAmount);
        
        executeAction(charIDToTypeID('Mk  '), rectDesc, DialogModes.NO);
        
        SelectionFeather.setFeather(featherAmount);
        
        const fillDesc = new ActionDescriptor();
        fillDesc.putClass(charIDToTypeID('null'), charIDToTypeID('Fl  '));
        fillDesc.putEnumerated(charIDToTypeID('FlTp'), charIDToTypeID('FlTp'), charIDToTypeID('FrgC'));
        
        executeAction(charIDToTypeID('Fl  '), fillDesc, DialogModes.NO);
    }
}
```

---

## 九、剪贴蒙版详解

### 9.1 创建剪贴蒙版

```javascript
class ClippingMask {
    static create() {
        executeAction(charIDToTypeID('ClpM'), undefined, DialogModes.NO);
    }

    static release() {
        executeAction(charIDToTypeID('RlsM'), undefined, DialogModes.NO);
    }

    static createFromLayers(baseLayerIndex, clipLayerIndex) {
        const doc = app.activeDocument;
        
        if (baseLayerIndex < clipLayerIndex) {
            const tempIndex = baseLayerIndex;
            baseLayerIndex = clipLayerIndex;
            clipLayerIndex = tempIndex;
        }
        
        doc.activeLayer = doc.layers[clipLayerIndex];
        executeAction(charIDToTypeID('ClpM'), undefined, DialogModes.NO);
    }
}
```

### 9.2 剪贴蒙版技巧

```javascript
class ClippingMaskTechniques {
    static createTextFillMask(textLayer, fillLayer) {
        const doc = app.activeDocument;
        
        const textIndex = doc.layers.getIndex(textLayer);
        const fillIndex = doc.layers.getIndex(fillLayer);
        
        if (fillIndex !== textIndex - 1) {
            fillLayer.move(textLayer, ElementPlacement.PLACEBEFORE);
        }
        
        fillLayer.clippingMask = true;
    }

    static createShapeContainer(containerLayer, contentLayers) {
        contentLayers.forEach(layer => {
            layer.move(containerLayer, ElementPlacement.PLACEBEFORE);
            layer.clippingMask = true;
        });
    }

    static createMultipleClipLayers(baseLayer, layersToClip) {
        layersToClip.forEach(layer => {
            layer.move(baseLayer, ElementPlacement.PLACEBEFORE);
            layer.clippingMask = true;
        });
    }
}
```

---

## 十、快速蒙版模式

### 10.1 快速蒙版操作

```javascript
class QuickMask {
    static enter() {
        executeAction(charIDToTypeID('QkMk'), undefined, DialogModes.NO);
    }

    static exit() {
        executeAction(charIDToTypeID('QkMk'), undefined, DialogModes.NO);
    }

    static toggle() {
        executeAction(charIDToTypeID('QkMk'), undefined, DialogModes.NO);
    }

    static setColorIndicator(mode) {
        const desc = new ActionDescriptor();
        
        if (mode === 'masked') {
            desc.putEnumerated(charIDToTypeID('ClrI'), charIDToTypeID('ClrI'), charIDToTypeID('Msk '));
        } else {
            desc.putEnumerated(charIDToTypeID('ClrI'), charIDToTypeID('ClrI'), charIDToTypeID('Sel '));
        }
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static setColor(color) {
        const desc = new ActionDescriptor();
        
        const colorDesc = new ActionDescriptor();
        colorDesc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Prc'), color.r);
        colorDesc.putUnitDouble(charIDToTypeID('Grn '), charIDToTypeID('#Prc'), color.g);
        colorDesc.putUnitDouble(charIDToTypeID('Bl  '), charIDToTypeID('#Prc'), color.b);
        
        desc.putObject(charIDToTypeID('Clr '), charIDToTypeID('Clr '), colorDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static setOpacity(opacity) {
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), opacity);
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

### 10.2 快速蒙版工作流

```javascript
class QuickMaskWorkflow {
    static createSelectionWithBrush(brushSize = 50) {
        QuickMask.enter();
        
        const brushDesc = new ActionDescriptor();
        brushDesc.putUnitDouble(charIDToTypeID('Size'), charIDToTypeID('#Pxl'), brushSize);
        executeAction(charIDToTypeID('Set '), brushDesc, DialogModes.NO);
        
        const paintDesc = new ActionDescriptor();
        paintDesc.putClass(charIDToTypeID('null'), charIDToTypeID('Pnt '));
        paintDesc.putEnumerated(charIDToTypeID('PntT'), charIDToTypeID('PntT'), charIDToTypeID('Strk'));
        
        executeAction(charIDToTypeID('Pnt '), paintDesc, DialogModes.NO);
    }

    static refineSelectionWithGradient() {
        QuickMask.enter();
        
        const gradDesc = new ActionDescriptor();
        gradDesc.putClass(charIDToTypeID('null'), charIDToTypeID('Grad'));
        gradDesc.putEnumerated(charIDToTypeID('Grad'), charIDToTypeID('Grad'), charIDToTypeID('LnGr'));
        
        executeAction(charIDToTypeID('Mk  '), gradDesc, DialogModes.NO);
    }
}
```

---

## 十一、矢量蒙版详解

### 11.1 创建矢量蒙版

```javascript
class VectorMask {
    static add() {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('AddV'), desc, DialogModes.NO);
    }

    static addFromPath() {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        const pathRef = new ActionReference();
        pathRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putReference(charIDToTypeID('Usng'), pathRef);
        
        executeAction(charIDToTypeID('AddV'), desc, DialogModes.NO);
    }

    static delete() {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('DltV'), desc, DialogModes.NO);
    }

    static enable(enable) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Enbl'), enable);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

### 11.2 矢量蒙版技巧

```javascript
class VectorMaskTechniques {
    static createShapeMask(shapeType, bounds) {
        const doc = app.activeDocument;
        const activeLayer = doc.activeLayer;
        
        const pathItem = doc.pathItems.add(shapeType, [
            [bounds.left, bounds.top],
            [bounds.right, bounds.top],
            [bounds.right, bounds.bottom],
            [bounds.left, bounds.bottom]
        ]);
        
        pathItem.closed = true;
        
        VectorMask.addFromPath();
        
        pathItem.remove();
    }

    static createCompoundMask(paths) {
        const doc = app.activeDocument;
        
        paths.forEach(pathData => {
            const pathItem = doc.pathItems.add('custom', pathData.points);
            pathItem.closed = pathData.closed;
        });
        
        const combineDesc = new ActionDescriptor();
        combineDesc.putEnumerated(charIDToTypeID('Cmbd'), charIDToTypeID('Cmbd'), charIDToTypeID('Unn '));
        executeAction(charIDToTypeID('Cmbd'), combineDesc, DialogModes.NO);
        
        VectorMask.addFromPath();
    }
}
```

---

## 十二、混合选项蒙版

### 12.1 混合选项基础

```javascript
class BlendingOptions {
    static open() {
        executeAction(charIDToTypeID('Blnd'), undefined, DialogModes.NO);
    }

    static setOpacity(opacity) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), opacity);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static setBlendMode(mode) {
        const modeMap = {
            'normal': charIDToTypeID('Nrml'),
            'multiply': charIDToTypeID('Mltp'),
            'screen': charIDToTypeID('Scrn'),
            'overlay': charIDToTypeID('Ovrl'),
            'softLight': charIDToTypeID('SftL'),
            'hardLight': charIDToTypeID('HrdL'),
            'colorDodge': charIDToTypeID('ClrD'),
            'colorBurn': charIDToTypeID('ClrB'),
            'darken': charIDToTypeID('Drkn'),
            'lighten': charIDToTypeID('Lght'),
            'difference': charIDToTypeID('Dffr'),
            'exclusion': charIDToTypeID('Excl'),
            'hue': charIDToTypeID('Hue '),
            'saturation': charIDToTypeID('Sat '),
            'color': charIDToTypeID('Clr '),
            'luminosity': charIDToTypeID('Lmns')
        };
        
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Blnd'), charIDToTypeID('Blnd'), modeMap[mode] || charIDToTypeID('Nrml'));
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static setFillOpacity(opacity) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('FlOp'), charIDToTypeID('#Prc'), opacity);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

### 12.2 图层样式蒙版

```javascript
class LayerStyleMask {
    static addDropShadow(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const shadowDesc = new ActionDescriptor();
        shadowDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.blendMode) {
            shadowDesc.putEnumerated(charIDToTypeID('Blnd'), charIDToTypeID('Blnd'), 
                options.blendMode === 'multiply' ? charIDToTypeID('Mltp') : charIDToTypeID('Scrn'));
        }
        if (options.opacity !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        if (options.angle !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('#Ang'), options.angle);
        }
        if (options.distance !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Dstn'), charIDToTypeID('#Pxl'), options.distance);
        }
        if (options.spread !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Spd '), charIDToTypeID('#Prc'), options.spread);
        }
        if (options.size !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        
        styleDesc.putObject(charIDToTypeID('Sd  '), charIDToTypeID('Sd  '), shadowDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addInnerShadow(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const shadowDesc = new ActionDescriptor();
        shadowDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.opacity !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        if (options.angle !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('#Ang'), options.angle);
        }
        if (options.distance !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Dstn'), charIDToTypeID('#Pxl'), options.distance);
        }
        if (options.choke !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Chk '), charIDToTypeID('#Prc'), options.choke);
        }
        if (options.size !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        
        styleDesc.putObject(charIDToTypeID('InSd'), charIDToTypeID('InSd'), shadowDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addOuterGlow(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const glowDesc = new ActionDescriptor();
        glowDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.opacity !== undefined) {
            glowDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        if (options.size !== undefined) {
            glowDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        if (options.spread !== undefined) {
            glowDesc.putUnitDouble(charIDToTypeID('Spd '), charIDToTypeID('#Prc'), options.spread);
        }
        
        styleDesc.putObject(charIDToTypeID('OtGl'), charIDToTypeID('OtGl'), glowDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addInnerGlow(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const glowDesc = new ActionDescriptor();
        glowDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.opacity !== undefined) {
            glowDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        if (options.size !== undefined) {
            glowDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        if (options.choke !== undefined) {
            glowDesc.putUnitDouble(charIDToTypeID('Chk '), charIDToTypeID('#Prc'), options.choke);
        }
        
        styleDesc.putObject(charIDToTypeID('InGl'), charIDToTypeID('InGl'), glowDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addBevelEmboss(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const bevelDesc = new ActionDescriptor();
        bevelDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.style) {
            const styleMap = {
                'outer': charIDToTypeID('OutB'),
                'inner': charIDToTypeID('InB '),
                'emboss': charIDToTypeID('Embs'),
                'pillow': charIDToTypeID('Pllw')
            };
            bevelDesc.putEnumerated(charIDToTypeID('BvlS'), charIDToTypeID('BvlS'), styleMap[options.style]);
        }
        if (options.depth !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Dpth'), charIDToTypeID('#Prc'), options.depth);
        }
        if (options.size !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        if (options.soften !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Sftn'), charIDToTypeID('#Pxl'), options.soften);
        }
        if (options.angle !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('#Ang'), options.angle);
        }
        if (options.altitude !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Alt '), charIDToTypeID('#Ang'), options.altitude);
        }
        
        styleDesc.putObject(charIDToTypeID('Bvl '), charIDToTypeID('Bvl '), bevelDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addGradientOverlay(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const gradDesc = new ActionDescriptor();
        gradDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.opacity !== undefined) {
            gradDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        if (options.angle !== undefined) {
            gradDesc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('#Ang'), options.angle);
        }
        if (options.scale !== undefined) {
            gradDesc.putUnitDouble(charIDToTypeID('Scl '), charIDToTypeID('#Prc'), options.scale);
        }
        
        styleDesc.putObject(charIDToTypeID('GrdO'), charIDToTypeID('GrdO'), gradDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addColorOverlay(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const colorDesc = new ActionDescriptor();
        colorDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.opacity !== undefined) {
            colorDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        
        styleDesc.putObject(charIDToTypeID('ClrO'), charIDToTypeID('ClrO'), colorDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addPatternOverlay(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const patternDesc = new ActionDescriptor();
        patternDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.opacity !== undefined) {
            patternDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        if (options.scale !== undefined) {
            patternDesc.putUnitDouble(charIDToTypeID('Scl '), charIDToTypeID('#Prc'), options.scale);
        }
        
        styleDesc.putObject(charIDToTypeID('PtnO'), charIDToTypeID('PtnO'), patternDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static addStroke(options = {}) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const styleDesc = new ActionDescriptor();
        
        const strokeDesc = new ActionDescriptor();
        strokeDesc.putBoolean(charIDToTypeID('Enbl'), true);
        
        if (options.position) {
            const posMap = {
                'outside': charIDToTypeID('OutS'),
                'inside': charIDToTypeID('InS '),
                'center': charIDToTypeID('Cntr')
            };
            strokeDesc.putEnumerated(charIDToTypeID('Pos '), charIDToTypeID('Pos '), posMap[options.position]);
        }
        if (options.size !== undefined) {
            strokeDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        if (options.opacity !== undefined) {
            strokeDesc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), options.opacity);
        }
        
        styleDesc.putObject(charIDToTypeID('Strk'), charIDToTypeID('Strk'), strokeDesc);
        desc.putObject(charIDToTypeID('LyrS'), charIDToTypeID('LyrS'), styleDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

---

## 十三、选区与蒙版自动化API

### 13.1 批量蒙版处理

```javascript
class BatchMaskProcessor {
    static createMasksFromLayers(layers, maskType = 'reveal') {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            LayerMask.add(null, maskType);
        });
    }

    static applyGradientMasksToLayers(layers, gradientType = 'linear') {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            LayerMaskTechniques.createGradientMask(gradientType);
        });
    }

    static batchAddDropShadow(layers, options = {}) {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            LayerStyleMask.addDropShadow(options);
        });
    }

    static batchSetOpacity(layers, opacity) {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            BlendingOptions.setOpacity(opacity);
        });
    }
}
```

### 13.2 选区自动化工作流

```javascript
class SelectionAutomation {
    static selectObjectWithMagicWand(x, y, tolerance = 32) {
        const tool = new MagicWandTool();
        tool.setTolerance(tolerance);
        tool.selectByColor(x, y);
    }

    static createComplexSelection(selectionSteps) {
        selectionSteps.forEach((step, index) => {
            if (index > 0) {
                MarqueeMode.setMode(step.mode === 'add' ? MarqueeMode.ADD : 
                    step.mode === 'subtract' ? MarqueeMode.SUBTRACT : MarqueeMode.INTERSECT);
            }
            
            if (step.type === 'rectangle') {
                const tool = new RectangularMarqueeTool();
                tool.createSelection(step.x, step.y, step.width, step.height);
            } else if (step.type === 'ellipse') {
                const tool = new EllipticalMarqueeTool();
                tool.createSelection(step.x, step.y, step.width, step.height);
            } else if (step.type === 'path') {
                const tool = new PenTool();
                tool.createClosedPath(step.points);
                PathToSelection.convert(step.feather || 0);
            }
        });
    }

    static refineSelectionWithMask(feather = 10, smooth = 5) {
        SelectionFeather.refineEdge({
            radius: feather,
            smooth: smooth,
            feather: feather
        });
    }
}
```

### 13.3 蒙版状态管理

```javascript
class MaskStateManager {
    constructor() {
        this.states = [];
    }

    saveState(name) {
        const state = {
            name: name,
            masks: [],
            timestamp: new Date().getTime()
        };
        
        const doc = app.activeDocument;
        doc.layers.forEach(layer => {
            if (layer.masks.length > 0) {
                state.masks.push({
                    layerName: layer.name,
                    maskCount: layer.masks.length,
                    hasLayerMask: layer.layerMask !== null,
                    hasVectorMask: layer.vectorMask !== null
                });
            }
        });
        
        this.states.push(state);
        return state;
    }

    restoreState(name) {
        const state = this.states.find(s => s.name === name);
        if (!state) return false;
        
        const doc = app.activeDocument;
        
        state.masks.forEach(maskInfo => {
            const layer = doc.layers.getByName(maskInfo.layerName);
            if (layer) {
                app.activeDocument.activeLayer = layer;
                
                if (!maskInfo.hasLayerMask && layer.layerMask) {
                    LayerMaskEditor.deleteMask();
                }
                if (!maskInfo.hasVectorMask && layer.vectorMask) {
                    VectorMask.delete();
                }
            }
        });
        
        return true;
    }

    clearAllStates() {
        this.states = [];
    }
}
```

---

## 十四、故障排查与性能优化

### 14.1 常见问题排查

```javascript
class MaskTroubleshooter {
    static checkMaskIssues() {
        const issues = [];
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.layerMask) {
                if (!layer.layerMask.enabled) {
                    issues.push({
                        type: 'disabled_mask',
                        layer: layer.name,
                        message: '图层蒙版已禁用'
                    });
                }
            }
            
            if (layer.masks.length > 5) {
                issues.push({
                    type: 'too_many_masks',
                    layer: layer.name,
                    message: '蒙版数量过多，建议合并'
                });
            }
        });
        
        return issues;
    }

    static fixDisabledMasks() {
        const doc = app.activeDocument;
        doc.layers.forEach(layer => {
            if (layer.layerMask && !layer.layerMask.enabled) {
                app.activeDocument.activeLayer = layer;
                LayerMaskEditor.enableMask();
            }
        });
    }

    static detectMaskConflicts() {
        const conflicts = [];
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.layerMask && layer.vectorMask) {
                conflicts.push({
                    layer: layer.name,
                    message: '同时存在图层蒙版和矢量蒙版，可能导致冲突'
                });
            }
        });
        
        return conflicts;
    }
}
```

### 14.2 性能优化策略

```javascript
class MaskPerformanceOptimizer {
    static optimizeLargeMasks(maxSize = 1000) {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.layerMask) {
                const maskPixels = layer.layerMask.bounds;
                const maskArea = maskPixels.width * maskPixels.height;
                
                if (maskArea > maxSize * maxSize) {
                    this.reduceMaskResolution(layer, maxSize);
                }
            }
        });
    }

    static reduceMaskResolution(layer, maxSize) {
        app.activeDocument.activeLayer = layer;
        LayerMaskEditor.enableMaskEditing(true);
        
        const scalePercent = (maxSize / Math.max(layer.layerMask.bounds.width, 
            layer.layerMask.bounds.height)) * 100;
        
        const desc = new ActionDescriptor();
        desc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Prc'), scalePercent);
        desc.putUnitDouble(charIDToTypeID('Hght'), charIDToTypeID('#Prc'), scalePercent);
        executeAction(charIDToTypeID('Sc  '), desc, DialogModes.NO);
        
        LayerMaskEditor.enableMaskEditing(false);
    }

    static mergeRedundantMasks() {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.masks.length > 1) {
                app.activeDocument.activeLayer = layer;
                
                const desc = new ActionDescriptor();
                desc.putEnumerated(charIDToTypeID('Cmbd'), charIDToTypeID('Cmbd'), charIDToTypeID('Intr'));
                executeAction(charIDToTypeID('Cmbd'), desc, DialogModes.NO);
            }
        });
    }

    static disableMasksForPreview() {
        const doc = app.activeDocument;
        doc.layers.forEach(layer => {
            if (layer.layerMask) {
                layer.layerMask.enabled = false;
            }
        });
    }

    static enableAllMasks() {
        const doc = app.activeDocument;
        doc.layers.forEach(layer => {
            if (layer.layerMask) {
                layer.layerMask.enabled = true;
            }
        });
    }
}
```

### 14.3 最佳实践指南

```javascript
class MaskBestPractices {
    static get GUIDELINES() {
        return {
            PERFORMANCE: [
                '避免在单个图层上使用超过5个蒙版',
                '对于大型图像，使用矢量蒙版代替像素蒙版',
                '在预览时临时禁用复杂蒙版',
                '定期合并冗余蒙版'
            ],
            QUALITY: [
                '使用羽化而非模糊滤镜处理蒙版边缘',
                '对于精确边缘，使用钢笔工具创建路径',
                '利用快速蒙版进行精细选区调整',
                '使用调整边缘工具优化选区质量'
            ],
            WORKFLOW: [
                '先创建选区，再添加蒙版',
                '使用剪贴蒙版组织图层结构',
                '利用图层样式增强蒙版效果',
                '定期保存蒙版状态便于回溯'
            ]
        };
    }

    static validateMaskWorkflow(doc) {
        const validation = {
            passed: [],
            warnings: [],
            errors: []
        };
        
        doc.layers.forEach(layer => {
            if (layer.clippingMask) {
                const baseLayerIndex = doc.layers.getIndex(layer) + 1;
                if (baseLayerIndex >= doc.layers.length) {
                    validation.errors.push({
                        layer: layer.name,
                        message: '剪贴蒙版缺少基础图层'
                    });
                }
            }
        });
        
        return validation;
    }
}
```

---

## 附录：快捷键速查

| 快捷键 | 功能 |
|--------|------|
| M | 选框工具 |
| L | 套索工具 |
| W | 快速选择/魔棒工具 |
| P | 钢笔工具 |
| Q | 快速蒙版模式 |
| Ctrl+D | 取消选择 |
| Ctrl+Shift+I | 反选 |
| Ctrl+Alt+D | 羽化选区 |
| Ctrl+J | 通过拷贝创建图层 |
| Ctrl+Shift+J | 通过剪切创建图层 |
| Alt+单击蒙版缩略图 | 显示蒙版 |
| Shift+单击蒙版缩略图 | 禁用/启用蒙版 |
| Alt+Shift+单击蒙版缩略图 | 以红色叠加显示蒙版 |