# Adobe Illustrator 矢量图形与MG动画完全手册

> 适用版本：Adobe Illustrator 2026 | 更新日期：2026-07-14 | 分类：Illustrator知识库

---

## 目录

- [一、AI架构与核心组件](#一ai架构与核心组件)
- [二、路径绘制系统](#二路径绘制系统)
- [三、图层管理系统](#三图层管理系统)
- [四、色彩系统与渐变](#四色彩系统与渐变)
- [五、符号系统与实例](#五符号系统与实例)
- [六、变换与变形](#六变换与变形)
- [七、效果与滤镜](#七效果与滤镜)
- [八、文字处理系统](#八文字处理系统)
- [九、图表与数据可视化](#九图表与数据可视化)
- [十、MG动画基础](#十mg动画基础)
- [十一、AI自动化API](#十一ai自动化api)
- [十二、故障排查与性能优化](#十二故障排查与性能优化)

---

## 一、AI架构与核心组件

### 1.1 对象模型层次

```javascript
// AI DOM 层次结构
// Application
//   └── Document
//       ├── Layer
//       │   ├── PathItem
//       │   ├── CompoundPathItem
//       │   ├── GroupItem
//       │   ├── TextFrame
//       │   └── PlacedItem
//       ├── Symbol
//       ├── Swatch
//       └── Gradient
```

### 1.2 核心对象

| 对象 | 描述 | 关键方法 |
|------|------|---------|
| **Application** | AI 应用程序 | open(), newDocument(), activeDocument |
| **Document** | 文档 | layers, symbols, swatches, gradients |
| **Layer** | 图层 | pageItems, visible, locked, opacity |
| **PathItem** | 路径对象 | pathPoints, filled, stroked, closed |
| **CompoundPathItem** | 复合路径 | paths, filled, stroked |
| **GroupItem** | 群组 | pageItems, ungroup(), regroup() |
| **TextFrame** | 文本框 | contents, textRange, paragraphs |
| **PlacedItem** | 置入对象 | replace(), embed(), unembed() |
| **Symbol** | 符号 | instances, definition, registrationPoint |
| **Swatch** | 色板 | colorType, colorValue |
| **Gradient** | 渐变 | gradientStops, type, angle |

### 1.3 JavaScript API 初始化

```javascript
var AI = {
    app: null,
    doc: null,
    
    init: function() {
        this.app = app;
        this.doc = app.activeDocument;
        return true;
    },
    
    createDocument: function(options) {
        this.doc = this.app.documents.add(
            options.width || 1920,
            options.height || 1080,
            options.rasterEffect || RasterEffectResolution.SCREEN,
            options.name || 'Untitled'
        );
        return this.doc;
    },
    
    openDocument: function(filePath) {
        this.doc = this.app.open(new File(filePath));
        return this.doc;
    },
    
    closeDocument: function(save) {
        if (save) {
            this.doc.save();
        }
        this.doc.close();
    },
    
    getDocumentInfo: function() {
        if (!this.doc) return null;
        
        return {
            name: this.doc.name,
            width: this.doc.width,
            height: this.doc.height,
            colorMode: this.doc.colorMode,
            rasterEffect: this.doc.rasterEffect,
            layerCount: this.doc.layers.length,
            symbolCount: this.doc.symbols.length,
            swatchCount: this.doc.swatches.length
        };
    },
    
    getVersion: function() {
        return this.app.version;
    }
};
```

### 1.4 AI与Adobe全家桶集成

```javascript
class AIIntegration {
    static exportToAE(compName, compositionType) {
        var desc = new ActionDescriptor();
        
        var appRef = new ActionReference();
        appRef.putEnumerated(charIDToTypeID('Prpr'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), appRef);
        desc.putString(charIDToTypeID('Nm  '), compName);
        
        var typeRef = new ActionReference();
        typeRef.putEnumerated(
            charIDToTypeID('CmpT'), 
            charIDToTypeID('CmpT'), 
            charIDToTypeID(compositionType || 'MV  ')
        );
        desc.putReference(charIDToTypeID('CmpT'), typeRef);
        
        executeAction(charIDToTypeID('AddQ'), desc, DialogModes.NO);
    }

    static exportToPSD(filePath, options) {
        var desc = new ActionDescriptor();
        
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var pathDesc = new ActionDescriptor();
        pathDesc.putPath(charIDToTypeID('null'), new File(filePath));
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        if (options?.layers) {
            desc.putBoolean(charIDToTypeID('Layr'), true);
        }
        if (options?.trim) {
            desc.putBoolean(charIDToTypeID('Trm '), true);
        }
        
        executeAction(charIDToTypeID('Exp '), desc, DialogModes.NO);
    }

    static exportToSVG(filePath, options) {
        var desc = new ActionDescriptor();
        
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var pathDesc = new ActionDescriptor();
        pathDesc.putPath(charIDToTypeID('null'), new File(filePath));
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        if (options?.embedImages) {
            desc.putBoolean(charIDToTypeID('Embd'), true);
        }
        if (options?.preserveEditability) {
            desc.putBoolean(charIDToTypeID('Pres'), true);
        }
        
        executeAction(charIDToTypeID('Exp '), desc, DialogModes.NO);
    }

    static dynamicLinkToAE() {
        executeAction(charIDToTypeID('DynL'), undefined, DialogModes.NO);
    }
}
```

---

## 二、路径绘制系统

### 2.1 基本形状绘制

```javascript
class ShapeTool {
    static createRectangle(x, y, width, height, options = {}) {
        var path = AI.doc.pathItems.rectangle(y, x, width, height);
        
        if (options.fillColor) {
            path.filled = true;
            path.fillColor = options.fillColor;
        } else {
            path.filled = false;
        }
        
        if (options.strokeColor) {
            path.stroked = true;
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        } else {
            path.stroked = false;
        }
        
        if (options.cornerRadius) {
            path.roundAllCorners(options.cornerRadius);
        }
        
        return path;
    }

    static createEllipse(x, y, width, height, options = {}) {
        var path = AI.doc.pathItems.ellipse(y, x, width, height);
        
        if (options.fillColor) {
            path.filled = true;
            path.fillColor = options.fillColor;
        } else {
            path.filled = false;
        }
        
        if (options.strokeColor) {
            path.stroked = true;
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        } else {
            path.stroked = false;
        }
        
        return path;
    }

    static createCircle(x, y, radius, options = {}) {
        return this.createEllipse(x - radius, y - radius, radius * 2, radius * 2, options);
    }

    static createPolygon(x, y, radius, sides, options = {}) {
        var path = AI.doc.pathItems.polygon(y, x, radius, sides);
        
        if (options.fillColor) {
            path.filled = true;
            path.fillColor = options.fillColor;
        } else {
            path.filled = false;
        }
        
        if (options.strokeColor) {
            path.stroked = true;
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        } else {
            path.stroked = false;
        }
        
        return path;
    }

    static createStar(x, y, outerRadius, innerRadius, points, options = {}) {
        var path = AI.doc.pathItems.star(y, x, outerRadius, innerRadius, points);
        
        if (options.fillColor) {
            path.filled = true;
            path.fillColor = options.fillColor;
        } else {
            path.filled = false;
        }
        
        if (options.strokeColor) {
            path.stroked = true;
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        } else {
            path.stroked = false;
        }
        
        return path;
    }

    static createLine(startX, startY, endX, endY, options = {}) {
        var path = AI.doc.pathItems.add();
        
        path.setEntirePath([
            [startX, startY],
            [endX, endY]
        ]);
        
        path.filled = false;
        path.stroked = true;
        path.strokeColor = options.strokeColor || this.createRGBColor(0, 0, 0);
        path.strokeWidth = options.strokeWidth || 1;
        
        return path;
    }
}
```

### 2.2 自定义路径绘制

```javascript
class PathBuilder {
    static createPath(points, options = {}) {
        var path = AI.doc.pathItems.add();
        
        path.setEntirePath(points);
        
        if (options.closed !== undefined) {
            path.closed = options.closed;
        }
        
        if (options.fillColor) {
            path.filled = true;
            path.fillColor = options.fillColor;
        } else {
            path.filled = false;
        }
        
        if (options.strokeColor) {
            path.stroked = true;
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        } else {
            path.stroked = false;
        }
        
        return path;
    }

    static createArc(x, y, width, height, startAngle, endAngle, options = {}) {
        var path = AI.doc.pathItems.add();
        var points = [];
        
        var startRad = (startAngle * Math.PI) / 180;
        var endRad = (endAngle * Math.PI) / 180;
        
        var cx = x + width / 2;
        var cy = y + height / 2;
        var rx = width / 2;
        var ry = height / 2;
        
        points.push([cx + rx * Math.cos(startRad), cy + ry * Math.sin(startRad)]);
        
        if (endAngle - startAngle > 180) {
            var midAngle = (startAngle + endAngle) / 2;
            var midRad = (midAngle * Math.PI) / 180;
            points.push([cx + rx * Math.cos(midRad), cy + ry * Math.sin(midRad)]);
        }
        
        points.push([cx + rx * Math.cos(endRad), cy + ry * Math.sin(endRad)]);
        
        path.setEntirePath(points);
        
        if (options.fillColor) {
            path.filled = true;
            path.fillColor = options.fillColor;
        } else {
            path.filled = false;
        }
        
        if (options.strokeColor) {
            path.stroked = true;
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        } else {
            path.stroked = false;
        }
        
        return path;
    }

    static createBezierPath(start, control1, control2, end, options = {}) {
        var path = AI.doc.pathItems.add();
        
        var pathPoints = path.pathPoints;
        var pp1 = pathPoints.add();
        pp1.anchor = start;
        pp1.leftDirection = start;
        pp1.rightDirection = control1;
        
        var pp2 = pathPoints.add();
        pp2.anchor = end;
        pp2.leftDirection = control2;
        pp2.rightDirection = end;
        
        path.filled = options.filled || false;
        path.stroked = options.stroked !== undefined ? options.stroked : true;
        
        if (options.fillColor) {
            path.fillColor = options.fillColor;
        }
        if (options.strokeColor) {
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        }
        
        return path;
    }

    static createSpline(points, options = {}) {
        var path = AI.doc.pathItems.add();
        
        var pathPoints = path.pathPoints;
        
        points.forEach(function(point, index) {
            var pp = pathPoints.add();
            pp.anchor = point;
            
            if (index === 0) {
                pp.leftDirection = point;
                var nextPoint = points[1];
                pp.rightDirection = [
                    point[0] + (nextPoint[0] - point[0]) / 3,
                    point[1] + (nextPoint[1] - point[1]) / 3
                ];
            } else if (index === points.length - 1) {
                pp.rightDirection = point;
                var prevPoint = points[points.length - 2];
                pp.leftDirection = [
                    point[0] - (point[0] - prevPoint[0]) / 3,
                    point[1] - (point[1] - prevPoint[1]) / 3
                ];
            } else {
                var prevPoint = points[index - 1];
                var nextPoint = points[index + 1];
                pp.leftDirection = [
                    point[0] - (nextPoint[0] - prevPoint[0]) / 6,
                    point[1] - (nextPoint[1] - prevPoint[1]) / 6
                ];
                pp.rightDirection = [
                    point[0] + (nextPoint[0] - prevPoint[0]) / 6,
                    point[1] + (nextPoint[1] - prevPoint[1]) / 6
                ];
            }
        });
        
        path.filled = options.filled || false;
        path.stroked = options.stroked !== undefined ? options.stroked : true;
        
        if (options.fillColor) {
            path.fillColor = options.fillColor;
        }
        if (options.strokeColor) {
            path.strokeColor = options.strokeColor;
            path.strokeWidth = options.strokeWidth || 1;
        }
        
        return path;
    }
}
```

### 2.3 路径操作

```javascript
class PathOperations {
    static unite(paths) {
        paths[0].selected = true;
        for (var i = 1; i < paths.length; i++) {
            paths[i].selected = true;
        }
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Unite'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static subtractFront(paths) {
        paths[0].selected = true;
        for (var i = 1; i < paths.length; i++) {
            paths[i].selected = true;
        }
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Sbtr'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static intersect(paths) {
        paths[0].selected = true;
        for (var i = 1; i < paths.length; i++) {
            paths[i].selected = true;
        }
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Intr'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static excludeOverlap(paths) {
        paths[0].selected = true;
        for (var i = 1; i < paths.length; i++) {
            paths[i].selected = true;
        }
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Excl'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static expand(path) {
        path.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Expand'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static offsetPath(path, offset) {
        path.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putUnitDouble(charIDToTypeID('Ofst'), charIDToTypeID('Pxl '), offset);
        
        executeAction(charIDToTypeID('Ofst'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static outlineStroke(path) {
        path.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('OtlS'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static simplifyPath(path, options = {}) {
        path.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        if (options.tolerance !== undefined) {
            desc.putUnitDouble(charIDToTypeID('Tolr'), charIDToTypeID('Pxl '), options.tolerance);
        }
        
        executeAction(charIDToTypeID('Smpl'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }
}
```

---

## 三、图层管理系统

### 3.1 图层创建与管理

```javascript
class LayerManager {
    static createLayer(name, options = {}) {
        var layer = AI.doc.layers.add();
        layer.name = name || 'Layer ' + AI.doc.layers.length;
        
        if (options.visible !== undefined) {
            layer.visible = options.visible;
        }
        if (options.locked !== undefined) {
            layer.locked = options.locked;
        }
        if (options.opacity !== undefined) {
            layer.opacity = options.opacity;
        }
        if (options.blendMode) {
            layer.blendMode = options.blendMode;
        }
        
        return layer;
    }

    static getLayerByName(name) {
        for (var i = 0; i < AI.doc.layers.length; i++) {
            if (AI.doc.layers[i].name === name) {
                return AI.doc.layers[i];
            }
        }
        return null;
    }

    static deleteLayer(layer) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.remove();
            return true;
        }
        return false;
    }

    static duplicateLayer(layer, newName) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            var newLayer = layer.duplicate();
            newLayer.name = newName || layer.name + ' copy';
            return newLayer;
        }
        return null;
    }

    static renameLayer(layer, newName) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.name = newName;
            return true;
        }
        return false;
    }

    static moveLayer(layer, index) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.zOrder(ZOrderMethod.SENDTOBACK);
            for (var i = 0; i < index; i++) {
                layer.zOrder(ZOrderMethod.BRINGFORWARD);
            }
            return true;
        }
        return false;
    }

    static showLayer(layer) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.visible = true;
            return true;
        }
        return false;
    }

    static hideLayer(layer) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.visible = false;
            return true;
        }
        return false;
    }

    static lockLayer(layer) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.locked = true;
            return true;
        }
        return false;
    }

    static unlockLayer(layer) {
        if (typeof layer === 'string') {
            layer = this.getLayerByName(layer);
        }
        if (layer) {
            layer.locked = false;
            return true;
        }
        return false;
    }

    static listLayers() {
        var layers = [];
        for (var i = 0; i < AI.doc.layers.length; i++) {
            var layer = AI.doc.layers[i];
            layers.push({
                name: layer.name,
                visible: layer.visible,
                locked: layer.locked,
                opacity: layer.opacity,
                blendMode: layer.blendMode,
                itemCount: layer.pageItems.length
            });
        }
        return layers;
    }
}
```

### 3.2 图层组管理

```javascript
class LayerGroupManager {
    static createGroup(name) {
        var group = AI.doc.layers.add();
        group.name = name || 'Group ' + AI.doc.layers.length;
        return group;
    }

    static addToGroup(item, group) {
        if (typeof group === 'string') {
            group = LayerManager.getLayerByName(group);
        }
        if (group && item) {
            item.moveToEnd(group);
            return true;
        }
        return false;
    }

    static removeFromGroup(item) {
        var layer = AI.doc.layers[0];
        if (layer && item) {
            item.moveToEnd(layer);
            return true;
        }
        return false;
    }

    static createNestedGroup(parentGroup, name) {
        var group = AI.doc.layers.add();
        group.name = name || 'Nested Group';
        
        if (parentGroup) {
            group.moveToEnd(parentGroup);
        }
        
        return group;
    }

    static flattenGroup(group) {
        if (typeof group === 'string') {
            group = LayerManager.getLayerByName(group);
        }
        if (group) {
            group.pageItems.everyItem().selected = true;
            
            var desc = new ActionDescriptor();
            var targetRef = new ActionReference();
            targetRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
            desc.putReference(charIDToTypeID('null'), targetRef);
            
            executeAction(charIDToTypeID('Fltt'), desc, DialogModes.NO);
            
            return true;
        }
        return false;
    }
}
```

---

## 四、色彩系统与渐变

### 4.1 颜色创建

```javascript
class ColorSystem {
    static createRGBColor(red, green, blue) {
        var color = new RGBColor();
        color.red = Math.min(255, Math.max(0, red));
        color.green = Math.min(255, Math.max(0, green));
        color.blue = Math.min(255, Math.max(0, blue));
        return color;
    }

    static createCMYKColor(cyan, magenta, yellow, black) {
        var color = new CMYKColor();
        color.cyan = Math.min(100, Math.max(0, cyan));
        color.magenta = Math.min(100, Math.max(0, magenta));
        color.yellow = Math.min(100, Math.max(0, yellow));
        color.black = Math.min(100, Math.max(0, black));
        return color;
    }

    static createHSBColor(hue, saturation, brightness) {
        var color = new HSBColor();
        color.hue = Math.min(360, Math.max(0, hue));
        color.saturation = Math.min(100, Math.max(0, saturation));
        color.brightness = Math.min(100, Math.max(0, brightness));
        return color;
    }

    static createGrayColor(gray) {
        var color = new GrayColor();
        color.gray = Math.min(100, Math.max(0, gray));
        return color;
    }

    static hexToRGB(hex) {
        hex = hex.replace('#', '');
        var r = parseInt(hex.substring(0, 2), 16);
        var g = parseInt(hex.substring(2, 4), 16);
        var b = parseInt(hex.substring(4, 6), 16);
        return this.createRGBColor(r, g, b);
    }

    static rgbToHex(r, g, b) {
        return '#' + 
            Math.round(r).toString(16).padStart(2, '0') +
            Math.round(g).toString(16).padStart(2, '0') +
            Math.round(b).toString(16).padStart(2, '0');
    }

    static createSpotColor(name, color) {
        var spotColor = new SpotColor();
        spotColor.name = name;
        spotColor.colorType = ColorModel.SPOT;
        spotColor.alternateColor = color;
        return spotColor;
    }

    static createGlobalColor(name, color) {
        var swatch = AI.doc.swatches.add();
        swatch.name = name;
        swatch.colorType = ColorModel.PROCESS;
        swatch.colorValue = color;
        return swatch;
    }
}
```

### 4.2 渐变系统

```javascript
class GradientSystem {
    static createLinearGradient(stops, options = {}) {
        var gradient = AI.doc.gradients.add();
        gradient.type = GradientType.LINEAR;
        gradient.angle = options.angle || 0;
        gradient.aspectRatio = options.aspectRatio || 1;
        
        this.setGradientStops(gradient, stops);
        
        return gradient;
    }

    static createRadialGradient(stops, options = {}) {
        var gradient = AI.doc.gradients.add();
        gradient.type = GradientType.RADIAL;
        gradient.aspectRatio = options.aspectRatio || 1;
        gradient.radialOrigin = options.radialOrigin || [0.5, 0.5];
        
        this.setGradientStops(gradient, stops);
        
        return gradient;
    }

    static createFreeformGradient(stops, options = {}) {
        var gradient = AI.doc.gradients.add();
        gradient.type = GradientType.FREEFORM;
        
        this.setGradientStops(gradient, stops);
        
        return gradient;
    }

    static setGradientStops(gradient, stops) {
        while (gradient.gradientStops.length > 0) {
            gradient.gradientStops[0].remove();
        }
        
        stops.forEach(function(stop) {
            var gs = gradient.gradientStops.add();
            gs.color = stop.color;
            gs.location = stop.location || 50;
            gs.midPoint = stop.midPoint || 50;
        });
    }

    static createGradientSwatch(name, gradient) {
        var swatch = AI.doc.swatches.add();
        swatch.name = name;
        swatch.colorType = ColorModel.GRADIENT;
        swatch.gradient = gradient;
        return swatch;
    }

    static applyGradientToPath(path, gradient) {
        path.filled = true;
        path.fillColor = new GradientColor();
        path.fillColor.gradient = gradient;
    }

    static createRainbowGradient() {
        var stops = [
            { location: 0, color: ColorSystem.createHSBColor(0, 100, 100) },
            { location: 17, color: ColorSystem.createHSBColor(60, 100, 100) },
            { location: 33, color: ColorSystem.createHSBColor(120, 100, 100) },
            { location: 50, color: ColorSystem.createHSBColor(180, 100, 100) },
            { location: 67, color: ColorSystem.createHSBColor(240, 100, 100) },
            { location: 83, color: ColorSystem.createHSBColor(300, 100, 100) },
            { location: 100, color: ColorSystem.createHSBColor(360, 100, 100) }
        ];
        
        return this.createLinearGradient(stops);
    }

    static createDuotoneGradient(color1, color2) {
        var stops = [
            { location: 0, color: color1 },
            { location: 100, color: color2 }
        ];
        
        return this.createLinearGradient(stops);
    }
}
```

### 4.3 色板管理

```javascript
class SwatchManager {
    static addSwatch(name, color) {
        var swatch = AI.doc.swatches.add();
        swatch.name = name;
        
        if (color.constructor.name === 'RGBColor' || 
            color.constructor.name === 'CMYKColor' || 
            color.constructor.name === 'HSBColor' || 
            color.constructor.name === 'GrayColor') {
            swatch.colorType = ColorModel.PROCESS;
            swatch.colorValue = color;
        } else if (color.constructor.name === 'Gradient') {
            swatch.colorType = ColorModel.GRADIENT;
            swatch.gradient = color;
        } else if (color.constructor.name === 'Pattern') {
            swatch.colorType = ColorModel.PATTERN;
            swatch.pattern = color;
        }
        
        return swatch;
    }

    static getSwatchByName(name) {
        for (var i = 0; i < AI.doc.swatches.length; i++) {
            if (AI.doc.swatches[i].name === name) {
                return AI.doc.swatches[i];
            }
        }
        return null;
    }

    static deleteSwatch(name) {
        var swatch = this.getSwatchByName(name);
        if (swatch) {
            swatch.remove();
            return true;
        }
        return false;
    }

    static duplicateSwatch(name, newName) {
        var swatch = this.getSwatchByName(name);
        if (swatch) {
            var newSwatch = swatch.duplicate();
            newSwatch.name = newName;
            return newSwatch;
        }
        return null;
    }

    static renameSwatch(oldName, newName) {
        var swatch = this.getSwatchByName(oldName);
        if (swatch) {
            swatch.name = newName;
            return true;
        }
        return false;
    }

    static listSwatches() {
        var swatches = [];
        for (var i = 0; i < AI.doc.swatches.length; i++) {
            var swatch = AI.doc.swatches[i];
            swatches.push({
                name: swatch.name,
                colorType: swatch.colorType,
                colorValue: swatch.colorValue ? this.formatColor(swatch.colorValue) : null
            });
        }
        return swatches;
    }

    static formatColor(color) {
        if (color.constructor.name === 'RGBColor') {
            return `RGB(${color.red}, ${color.green}, ${color.blue})`;
        } else if (color.constructor.name === 'CMYKColor') {
            return `CMYK(${color.cyan}%, ${color.magenta}%, ${color.yellow}%, ${color.black}%)`;
        } else if (color.constructor.name === 'HSBColor') {
            return `HSB(${color.hue}°, ${color.saturation}%, ${color.brightness}%)`;
        } else if (color.constructor.name === 'GrayColor') {
            return `Gray(${color.gray}%)`;
        }
        return color.constructor.name;
    }

    static createColorPalette(name, colors) {
        colors.forEach(function(color, index) {
            this.addSwatch(name + ' ' + (index + 1), color);
        }, this);
    }
}
```

---

## 五、符号系统与实例

### 5.1 符号创建与管理

```javascript
class SymbolManager {
    static createSymbol(name, definition) {
        var symbol = AI.doc.symbols.add(definition);
        symbol.name = name;
        
        return symbol;
    }

    static getSymbolByName(name) {
        for (var i = 0; i < AI.doc.symbols.length; i++) {
            if (AI.doc.symbols[i].name === name) {
                return AI.doc.symbols[i];
            }
        }
        return null;
    }

    static deleteSymbol(name) {
        var symbol = this.getSymbolByName(name);
        if (symbol) {
            symbol.remove();
            return true;
        }
        return false;
    }

    static duplicateSymbol(name, newName) {
        var symbol = this.getSymbolByName(name);
        if (symbol) {
            var newSymbol = symbol.duplicate();
            newSymbol.name = newName;
            return newSymbol;
        }
        return null;
    }

    static renameSymbol(oldName, newName) {
        var symbol = this.getSymbolByName(oldName);
        if (symbol) {
            symbol.name = newName;
            return true;
        }
        return false;
    }

    static updateSymbol(symbol, newDefinition) {
        if (typeof symbol === 'string') {
            symbol = this.getSymbolByName(symbol);
        }
        if (symbol && newDefinition) {
            symbol.definition = newDefinition;
            return true;
        }
        return false;
    }

    static listSymbols() {
        var symbols = [];
        for (var i = 0; i < AI.doc.symbols.length; i++) {
            var symbol = AI.doc.symbols[i];
            symbols.push({
                name: symbol.name,
                instanceCount: symbol.instances.length,
                registrationPoint: symbol.registrationPoint
            });
        }
        return symbols;
    }
}
```

### 5.2 符号实例管理

```javascript
class SymbolInstanceManager {
    static placeInstance(symbol, x, y) {
        if (typeof symbol === 'string') {
            symbol = SymbolManager.getSymbolByName(symbol);
        }
        if (symbol) {
            var instance = AI.doc.symbolItems.add(symbol);
            instance.position = [x, y];
            return instance;
        }
        return null;
    }

    static placeMultipleInstances(symbol, positions) {
        var instances = [];
        positions.forEach(function(pos) {
            var instance = this.placeInstance(symbol, pos[0], pos[1]);
            if (instance) {
                instances.push(instance);
            }
        }, this);
        return instances;
    }

    static replaceInstance(instance, newSymbol) {
        if (typeof newSymbol === 'string') {
            newSymbol = SymbolManager.getSymbolByName(newSymbol);
        }
        if (instance && newSymbol) {
            instance.symbol = newSymbol;
            return true;
        }
        return false;
    }

    static breakLink(instance) {
        if (instance) {
            instance.breakLink();
            return true;
        }
        return false;
    }

    static breakAllLinks(symbol) {
        if (typeof symbol === 'string') {
            symbol = SymbolManager.getSymbolByName(symbol);
        }
        if (symbol) {
            symbol.instances.everyItem().breakLink();
            return true;
        }
        return false;
    }

    static setInstanceTransform(instance, transform) {
        if (transform.scale !== undefined) {
            instance.scale(transform.scale);
        }
        if (transform.rotation !== undefined) {
            instance.rotate(transform.rotation);
        }
        if (transform.skew !== undefined) {
            instance.skew(transform.skew);
        }
        if (transform.position !== undefined) {
            instance.position = transform.position;
        }
    }

    static createInstanceGrid(symbol, startX, startY, cols, rows, spacingX, spacingY) {
        var instances = [];
        
        for (var row = 0; row < rows; row++) {
            for (var col = 0; col < cols; col++) {
                var x = startX + col * spacingX;
                var y = startY + row * spacingY;
                var instance = this.placeInstance(symbol, x, y);
                if (instance) {
                    instances.push(instance);
                }
            }
        }
        
        return instances;
    }

    static createInstancePattern(symbol, patternFunc, count) {
        var instances = [];
        
        for (var i = 0; i < count; i++) {
            var pos = patternFunc(i);
            var instance = this.placeInstance(symbol, pos[0], pos[1]);
            if (instance) {
                if (pos.scale !== undefined) {
                    instance.scale(pos.scale);
                }
                if (pos.rotation !== undefined) {
                    instance.rotate(pos.rotation);
                }
                if (pos.opacity !== undefined) {
                    instance.opacity = pos.opacity;
                }
                instances.push(instance);
            }
        }
        
        return instances;
    }
}
```

---

## 六、变换与变形

### 6.1 基础变换

```javascript
class TransformSystem {
    static move(item, dx, dy) {
        var pos = item.position;
        item.position = [pos[0] + dx, pos[1] + dy];
    }

    static moveTo(item, x, y) {
        item.position = [x, y];
    }

    static scale(item, factor, center) {
        if (center) {
            item.scaleAboutPoint(factor, factor, center[0], center[1]);
        } else {
            item.scale(factor, factor);
        }
    }

    static scaleTo(item, width, height) {
        var bounds = item.geometricBounds;
        var currentWidth = bounds[2] - bounds[0];
        var currentHeight = bounds[3] - bounds[1];
        
        var scaleX = width / currentWidth;
        var scaleY = height / currentHeight;
        
        item.scale(scaleX, scaleY);
    }

    static rotate(item, angle, center) {
        if (center) {
            item.rotateAboutPoint(angle, center[0], center[1]);
        } else {
            item.rotate(angle);
        }
    }

    static skew(item, angleX, angleY) {
        item.skew(angleX, angleY);
    }

    static reflect(item, axis, center) {
        if (axis === 'horizontal') {
            item.scale(-1, 1, center ? center[0] : undefined, center ? center[1] : undefined);
        } else if (axis === 'vertical') {
            item.scale(1, -1, center ? center[0] : undefined, center ? center[1] : undefined);
        } else if (axis === 'diagonal') {
            item.rotate(180, center ? center[0] : undefined, center ? center[1] : undefined);
        }
    }

    static transform(item, matrix) {
        item.transform(matrix);
    }

    static getBounds(item) {
        return item.geometricBounds;
    }

    static getCenter(item) {
        var bounds = item.geometricBounds;
        return [
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2
        ];
    }
}
```

### 6.2 高级变形

```javascript
class WarpSystem {
    static applyWarp(item, warpStyle, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var styleRef = new ActionReference();
        styleRef.putEnumerated(
            charIDToTypeID('WrpS'), 
            charIDToTypeID('WrpS'), 
            charIDToTypeID(warpStyle)
        );
        desc.putReference(charIDToTypeID('WrpS'), styleRef);
        
        if (options.bend !== undefined) {
            desc.putInteger(charIDToTypeID('Bnd '), options.bend);
        }
        if (options.horizontalDistortion !== undefined) {
            desc.putInteger(charIDToTypeID('Hrzn'), options.horizontalDistortion);
        }
        if (options.verticalDistortion !== undefined) {
            desc.putInteger(charIDToTypeID('Vrtc'), options.verticalDistortion);
        }
        
        executeAction(charIDToTypeID('Wrp '), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyMeshWarp(item, rows, cols) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putInteger(charIDToTypeID('Rows'), rows);
        desc.putInteger(charIDToTypeID('Cols '), cols);
        
        executeAction(charIDToTypeID('Mesh'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyEnvelopeDistort(item, warpObject) {
        item.selected = true;
        warpObject.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Envl'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static createPuckerBloat(item, amount) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putInteger(charIDToTypeID('Amt '), amount);
        
        executeAction(charIDToTypeID('PckB'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static createTwirl(item, angle) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putInteger(charIDToTypeID('Angl'), angle);
        
        executeAction(charIDToTypeID('Twrl'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static createSqueeze(item, amount) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putInteger(charIDToTypeID('Amt '), amount);
        
        executeAction(charIDToTypeID('Sqz '), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }
}
```

---

## 七、效果与滤镜

### 7.1 效果应用

```javascript
class EffectSystem {
    static applyDropShadow(item, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('DrSh')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        
        if (options.blendMode) {
            var modeRef = new ActionReference();
            modeRef.putEnumerated(
                charIDToTypeID('BlnM'), 
                charIDToTypeID('BlnM'), 
                charIDToTypeID(options.blendMode)
            );
            effDesc.putReference(charIDToTypeID('BlnM'), modeRef);
        }
        
        if (options.opacity !== undefined) {
            effDesc.putInteger(charIDToTypeID('Opct'), options.opacity);
        }
        if (options.xOffset !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('XOfs'), charIDToTypeID('Pxl '), options.xOffset);
        }
        if (options.yOffset !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('YOfs'), charIDToTypeID('Pxl '), options.yOffset);
        }
        if (options.blur !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Blr '), charIDToTypeID('Pxl '), options.blur);
        }
        
        var color = options.color || ColorSystem.createRGBColor(0, 0, 0);
        effDesc.putObject(charIDToTypeID('Clr '), charIDToTypeID('RGBC'), color);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('DrSh'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyInnerShadow(item, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('InSh')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        
        if (options.opacity !== undefined) {
            effDesc.putInteger(charIDToTypeID('Opct'), options.opacity);
        }
        if (options.xOffset !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('XOfs'), charIDToTypeID('Pxl '), options.xOffset);
        }
        if (options.yOffset !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('YOfs'), charIDToTypeID('Pxl '), options.yOffset);
        }
        if (options.blur !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Blr '), charIDToTypeID('Pxl '), options.blur);
        }
        
        var color = options.color || ColorSystem.createRGBColor(0, 0, 0);
        effDesc.putObject(charIDToTypeID('Clr '), charIDToTypeID('RGBC'), color);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('InSh'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyOuterGlow(item, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('OtGl')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        
        if (options.opacity !== undefined) {
            effDesc.putInteger(charIDToTypeID('Opct'), options.opacity);
        }
        if (options.blur !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Blr '), charIDToTypeID('Pxl '), options.blur);
        }
        
        var color = options.color || ColorSystem.createRGBColor(255, 255, 0);
        effDesc.putObject(charIDToTypeID('Clr '), charIDToTypeID('RGBC'), color);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('OtGl'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyInnerGlow(item, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('InGl')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        
        if (options.opacity !== undefined) {
            effDesc.putInteger(charIDToTypeID('Opct'), options.opacity);
        }
        if (options.blur !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Blr '), charIDToTypeID('Pxl '), options.blur);
        }
        
        var color = options.color || ColorSystem.createRGBColor(255, 255, 0);
        effDesc.putObject(charIDToTypeID('Clr '), charIDToTypeID('RGBC'), color);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('InGl'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyBevelEmboss(item, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('BvlE')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        
        if (options.style) {
            var styleRef = new ActionReference();
            styleRef.putEnumerated(
                charIDToTypeID('BvlS'), 
                charIDToTypeID('BvlS'), 
                charIDToTypeID(options.style)
            );
            effDesc.putReference(charIDToTypeID('BvlS'), styleRef);
        }
        
        if (options.depth !== undefined) {
            effDesc.putInteger(charIDToTypeID('Dpth'), options.depth);
        }
        if (options.size !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('Pxl '), options.size);
        }
        if (options.soften !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Sftn'), charIDToTypeID('Pxl '), options.soften);
        }
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('BvlE'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }
}
```

### 7.2 艺术效果

```javascript
class ArtisticEffects {
    static applyFeather(item, radius) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putUnitDouble(charIDToTypeID('Fthr'), charIDToTypeID('Pxl '), radius);
        
        executeAction(charIDToTypeID('Fthr'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyGaussianBlur(item, radius) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('GsBl')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        effDesc.putUnitDouble(charIDToTypeID('Rad '), charIDToTypeID('Pxl '), radius);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('GsBl'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyMotionBlur(item, angle, distance) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('MtBl')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        effDesc.putInteger(charIDToTypeID('Angl'), angle);
        effDesc.putUnitDouble(charIDToTypeID('Dstn'), charIDToTypeID('Pxl '), distance);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('MtBl'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyPixelate(item, size) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('PxlT')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        effDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('Pxl '), size);
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('PxlT'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static applyRoughenEdges(item, options = {}) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var effRef = new ActionReference();
        effRef.putEnumerated(
            charIDToTypeID('Efct'), 
            charIDToTypeID('Efct'), 
            charIDToTypeID('RghE')
        );
        desc.putReference(charIDToTypeID('Efct'), effRef);
        
        var effDesc = new ActionDescriptor();
        
        if (options.size !== undefined) {
            effDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('Pxl '), options.size);
        }
        if (options.detail !== undefined) {
            effDesc.putInteger(charIDToTypeID('Dtll'), options.detail);
        }
        if (options.roughness !== undefined) {
            effDesc.putInteger(charIDToTypeID('Rghn'), options.roughness);
        }
        
        desc.putObject(charIDToTypeID('Efct'), charIDToTypeID('RghE'), effDesc);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }
}
```

---

## 八、文字处理系统

### 8.1 文本创建与编辑

```javascript
class TextSystem {
    static createPointText(x, y, content, options = {}) {
        var textFrame = AI.doc.textFrames.add();
        textFrame.contents = content || '';
        textFrame.position = [x, y];
        
        if (options.fontSize) {
            textFrame.textRange.characterAttributes.size = options.fontSize;
        }
        if (options.fontFamily) {
            textFrame.textRange.characterAttributes.textFont = options.fontFamily;
        }
        if (options.fillColor) {
            textFrame.textRange.characterAttributes.fillColor = options.fillColor;
        }
        if (options.strokeColor) {
            textFrame.textRange.characterAttributes.strokeColor = options.strokeColor;
            textFrame.textRange.characterAttributes.strokeWeight = options.strokeWeight || 1;
        }
        if (options.leading) {
            textFrame.textRange.paragraphAttributes.leading = options.leading;
        }
        if (options.alignment) {
            textFrame.textRange.paragraphAttributes.justification = options.alignment;
        }
        
        return textFrame;
    }

    static createAreaText(x, y, width, height, content, options = {}) {
        var textFrame = AI.doc.textFrames.add();
        textFrame.contents = content || '';
        textFrame.geometricBounds = [y + height, x, y, x + width];
        
        if (options.fontSize) {
            textFrame.textRange.characterAttributes.size = options.fontSize;
        }
        if (options.fontFamily) {
            textFrame.textRange.characterAttributes.textFont = options.fontFamily;
        }
        if (options.fillColor) {
            textFrame.textRange.characterAttributes.fillColor = options.fillColor;
        }
        if (options.strokeColor) {
            textFrame.textRange.characterAttributes.strokeColor = options.strokeColor;
            textFrame.textRange.characterAttributes.strokeWeight = options.strokeWeight || 1;
        }
        if (options.leading) {
            textFrame.textRange.paragraphAttributes.leading = options.leading;
        }
        if (options.alignment) {
            textFrame.textRange.paragraphAttributes.justification = options.alignment;
        }
        
        return textFrame;
    }

    static createPathText(path, content, options = {}) {
        var textFrame = AI.doc.textFrames.add();
        textFrame.contents = content || '';
        
        path.selected = true;
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('OnPth'), desc, DialogModes.NO);
        
        if (options.fontSize) {
            textFrame.textRange.characterAttributes.size = options.fontSize;
        }
        if (options.fontFamily) {
            textFrame.textRange.characterAttributes.textFont = options.fontFamily;
        }
        if (options.fillColor) {
            textFrame.textRange.characterAttributes.fillColor = options.fillColor;
        }
        
        return textFrame;
    }

    static setTextStyle(textFrame, style) {
        if (style.fontSize) {
            textFrame.textRange.characterAttributes.size = style.fontSize;
        }
        if (style.fontFamily) {
            textFrame.textRange.characterAttributes.textFont = style.fontFamily;
        }
        if (style.fillColor) {
            textFrame.textRange.characterAttributes.fillColor = style.fillColor;
        }
        if (style.strokeColor) {
            textFrame.textRange.characterAttributes.strokeColor = style.strokeColor;
            textFrame.textRange.characterAttributes.strokeWeight = style.strokeWeight || 1;
        }
        if (style.leading) {
            textFrame.textRange.paragraphAttributes.leading = style.leading;
        }
        if (style.alignment) {
            textFrame.textRange.paragraphAttributes.justification = style.alignment;
        }
        if (style.tracking) {
            textFrame.textRange.characterAttributes.tracking = style.tracking;
        }
        if (style.baselineShift) {
            textFrame.textRange.characterAttributes.baselineShift = style.baselineShift;
        }
    }

    static convertToOutlines(textFrame) {
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('CrO '), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }

    static findReplace(textFrame, findText, replaceText, options = {}) {
        var found = textFrame.textRange.find(findText);
        
        found.forEach(function(textRange) {
            textRange.contents = replaceText;
            
            if (options.replaceFormat) {
                this.setTextStyle(textRange.parentTextFrame, options.replaceFormat);
            }
        }, this);
        
        return found.length;
    }
}
```

---

## 九、图表与数据可视化

### 9.1 图表创建

```javascript
class ChartSystem {
    static createColumnChart(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.COLUMN;
        chart.data = data;
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createBarChart(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.BAR;
        chart.data = data;
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createLineChart(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.LINE;
        chart.data = data;
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createAreaChart(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.AREA;
        chart.data = data;
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createPieChart(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.PIE;
        chart.data = data;
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createScatterChart(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.SCATTER;
        chart.data = data;
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createDataMatrix(headers, rows) {
        var data = [];
        data.push(headers);
        rows.forEach(function(row) {
            data.push(row);
        });
        return data;
    }

    static updateChartData(chart, newData) {
        chart.data = newData;
    }

    static convertChartToArtwork(chart) {
        chart.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Grph'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Ungr'), desc, DialogModes.NO);
        
        return AI.doc.selection;
    }
}
```

### 9.2 数据可视化工具

```javascript
class DataVisualization {
    static createHistogram(data, options = {}) {
        var chart = AI.doc.graphItems.add();
        chart.graphType = GraphType.COLUMN;
        
        var headers = ['Category'];
        var row = ['Value'];
        
        data.forEach(function(value, index) {
            headers.push('Bar ' + (index + 1));
            row.push(value);
        });
        
        chart.data = [headers, row];
        
        if (options.width) chart.width = options.width;
        if (options.height) chart.height = options.height;
        
        return chart;
    }

    static createProgressBar(progress, options = {}) {
        var width = options.width || 200;
        var height = options.height || 20;
        var x = options.x || 0;
        var y = options.y || 0;
        
        var background = ShapeTool.createRectangle(x, y, width, height, {
            fillColor: options.bgColor || ColorSystem.createRGBColor(200, 200, 200)
        });
        
        var progressWidth = width * (progress / 100);
        var foreground = ShapeTool.createRectangle(x, y, progressWidth, height, {
            fillColor: options.fgColor || ColorSystem.createRGBColor(0, 128, 255)
        });
        
        return { background, foreground };
    }

    static createDonutChart(data, options = {}) {
        var total = data.reduce(function(sum, val) { return sum + val; }, 0);
        var radius = options.radius || 50;
        var innerRadius = options.innerRadius || 25;
        var x = options.x || 0;
        var y = options.y || 0;
        
        var startAngle = 0;
        var segments = [];
        
        data.forEach(function(value, index) {
            var angle = (value / total) * 360;
            var color = options.colors ? options.colors[index] : 
                ColorSystem.createHSBColor((index * 60) % 360, 80, 90);
            
            var segment = PathBuilder.createArc(
                x - radius, y - radius, 
                radius * 2, radius * 2, 
                startAngle, startAngle + angle,
                { fillColor: color }
            );
            
            segments.push(segment);
            startAngle += angle;
        });
        
        var innerCircle = ShapeTool.createCircle(x, y, innerRadius, {
            fillColor: options.bgColor || ColorSystem.createRGBColor(255, 255, 255)
        });
        
        return { segments, innerCircle };
    }

    static createSparkline(data, options = {}) {
        var width = options.width || 100;
        var height = options.height || 30;
        var x = options.x || 0;
        var y = options.y || 0;
        
        var min = Math.min(...data);
        var max = Math.max(...data);
        var range = max - min || 1;
        
        var points = data.map(function(value, index) {
            var px = x + (index / (data.length - 1)) * width;
            var py = y + height - ((value - min) / range) * height;
            return [px, py];
        });
        
        return PathBuilder.createSpline(points, {
            strokeColor: options.color || ColorSystem.createRGBColor(0, 128, 255),
            strokeWidth: options.strokeWidth || 2,
            filled: false
        });
    }
}
```

---

## 十、MG动画基础

### 10.1 时间轴动画

```javascript
class AnimationSystem {
    static createTimeline() {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Timl'), desc, DialogModes.NO);
    }

    static setAnimationDuration(seconds) {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putInteger(charIDToTypeID('Durn'), seconds * 1000);
        
        executeAction(charIDToTypeID('Durn'), desc, DialogModes.NO);
    }

    static setFrameRate(fps) {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putInteger(charIDToTypeID('FrRt'), fps);
        
        executeAction(charIDToTypeID('FrRt'), desc, DialogModes.NO);
    }

    static addKeyframe(item, property, time, value) {
        item.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        desc.putString(charIDToTypeID('Prpr'), property);
        desc.putInteger(charIDToTypeID('Time'), time);
        desc.putString(charIDToTypeID('Valu'), value);
        
        executeAction(charIDToTypeID('AddK'), desc, DialogModes.NO);
    }

    static createMotionPath(item, points) {
        item.selected = true;
        
        var path = PathBuilder.createPath(points, { filled: false, stroked: false });
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('MtnP'), desc, DialogModes.NO);
        
        return path;
    }

    static createFadeAnimation(item, startOpacity, endOpacity, duration) {
        this.addKeyframe(item, 'Opacity', 0, startOpacity);
        this.addKeyframe(item, 'Opacity', duration, endOpacity);
    }

    static createScaleAnimation(item, startScale, endScale, duration) {
        this.addKeyframe(item, 'ScaleX', 0, startScale);
        this.addKeyframe(item, 'ScaleY', 0, startScale);
        this.addKeyframe(item, 'ScaleX', duration, endScale);
        this.addKeyframe(item, 'ScaleY', duration, endScale);
    }

    static createRotationAnimation(item, startAngle, endAngle, duration) {
        this.addKeyframe(item, 'Rotation', 0, startAngle);
        this.addKeyframe(item, 'Rotation', duration, endAngle);
    }

    static createPositionAnimation(item, startPos, endPos, duration) {
        this.addKeyframe(item, 'PositionX', 0, startPos[0]);
        this.addKeyframe(item, 'PositionY', 0, startPos[1]);
        this.addKeyframe(item, 'PositionX', duration, endPos[0]);
        this.addKeyframe(item, 'PositionY', duration, endPos[1]);
    }

    static exportAnimation(filePath, options = {}) {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var pathDesc = new ActionDescriptor();
        pathDesc.putPath(charIDToTypeID('null'), new File(filePath));
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        if (options.format) {
            var fmtRef = new ActionReference();
            fmtRef.putEnumerated(
                charIDToTypeID('Fmt '), 
                charIDToTypeID('Fmt '), 
                charIDToTypeID(options.format)
            );
            desc.putReference(charIDToTypeID('Fmt '), fmtRef);
        }
        
        executeAction(charIDToTypeID('Exp '), desc, DialogModes.NO);
    }
}
```

### 10.2 动画预设

```javascript
class AnimationPresets {
    static createBounceIn(item, duration = 1000) {
        AnimationSystem.addKeyframe(item, 'ScaleX', 0, 0);
        AnimationSystem.addKeyframe(item, 'ScaleY', 0, 0);
        AnimationSystem.addKeyframe(item, 'ScaleX', duration * 0.5, 120);
        AnimationSystem.addKeyframe(item, 'ScaleY', duration * 0.5, 120);
        AnimationSystem.addKeyframe(item, 'ScaleX', duration, 100);
        AnimationSystem.addKeyframe(item, 'ScaleY', duration, 100);
    }

    static createFadeIn(item, duration = 1000) {
        AnimationSystem.createFadeAnimation(item, 0, 100, duration);
    }

    static createSlideIn(item, direction = 'left', duration = 1000) {
        var startPos = [0, 0];
        var endPos = [0, 0];
        
        switch (direction) {
            case 'left':
                startPos = [-200, 0];
                break;
            case 'right':
                startPos = [200, 0];
                break;
            case 'top':
                startPos = [0, -200];
                break;
            case 'bottom':
                startPos = [0, 200];
                break;
        }
        
        AnimationSystem.createPositionAnimation(item, startPos, endPos, duration);
    }

    static createSpinIn(item, rotations = 1, duration = 1000) {
        AnimationSystem.createRotationAnimation(item, 0, rotations * 360, duration);
        AnimationSystem.createScaleAnimation(item, 0, 100, duration);
    }

    static createPulse(item, duration = 1000, repetitions = -1) {
        AnimationSystem.addKeyframe(item, 'ScaleX', 0, 100);
        AnimationSystem.addKeyframe(item, 'ScaleY', 0, 100);
        AnimationSystem.addKeyframe(item, 'ScaleX', duration * 0.5, 110);
        AnimationSystem.addKeyframe(item, 'ScaleY', duration * 0.5, 110);
        AnimationSystem.addKeyframe(item, 'ScaleX', duration, 100);
        AnimationSystem.addKeyframe(item, 'ScaleY', duration, 100);
    }

    static createWiggle(item, duration = 1000, amplitude = 10, frequency = 5) {
        for (var i = 0; i <= duration; i += 100) {
            var offsetX = (Math.random() - 0.5) * amplitude * 2;
            var offsetY = (Math.random() - 0.5) * amplitude * 2;
            AnimationSystem.addKeyframe(item, 'PositionX', i, offsetX);
            AnimationSystem.addKeyframe(item, 'PositionY', i, offsetY);
        }
    }

    static createTypewriter(textFrame, duration = 1000) {
        var text = textFrame.contents;
        var charDuration = duration / text.length;
        
        for (var i = 0; i <= text.length; i++) {
            var time = i * charDuration;
            textFrame.textRange.characterAttributes.opacity = 0;
            textFrame.textRange.characters[0].characterAttributes.opacity = 100;
        }
    }
}
```

---

## 十一、AI自动化API

### 11.1 脚本基础框架

```javascript
var AIScript = {
    init: function() {
        this.app = app;
        this.doc = app.activeDocument;
        return this;
    },
    
    createDocument: function(options) {
        this.doc = this.app.documents.add(
            options.width || 1920,
            options.height || 1080,
            options.rasterEffect || RasterEffectResolution.SCREEN,
            options.name || 'Untitled'
        );
        return this.doc;
    },
    
    openDocument: function(filePath) {
        this.doc = this.app.open(new File(filePath));
        return this.doc;
    },
    
    saveDocument: function(filePath) {
        this.doc.saveAs(new File(filePath));
    },
    
    closeDocument: function(save) {
        if (save) {
            this.doc.save();
        }
        this.doc.close();
    },
    
    exportToPNG: function(filePath, options) {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var pathDesc = new ActionDescriptor();
        pathDesc.putPath(charIDToTypeID('null'), new File(filePath));
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        if (options?.resolution) {
            desc.putInteger(charIDToTypeID('Rslt'), options.resolution);
        }
        
        executeAction(charIDToTypeID('Exp '), desc, DialogModes.NO);
    },
    
    exportToSVG: function(filePath, options) {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var pathDesc = new ActionDescriptor();
        pathDesc.putPath(charIDToTypeID('null'), new File(filePath));
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Exp '), desc, DialogModes.NO);
    },
    
    exportToAE: function(compName) {
        AIIntegration.exportToAE(compName);
    }
};
```

### 11.2 批量处理脚本

```javascript
function batchProcessImages(inputFolder, outputFolder, processFunc) {
    var fs = new Folder(inputFolder);
    var files = fs.getFiles();
    
    files.forEach(function(file) {
        if (file.constructor.name === 'File') {
            var extension = file.name.split('.').pop().toLowerCase();
            if (['ai', 'eps', 'pdf', 'svg'].includes(extension)) {
                try {
                    AIScript.init().openDocument(file.fsName);
                    
                    processFunc();
                    
                    var outputPath = outputFolder + '/' + file.name.replace('.' + extension, '_processed.ai');
                    AIScript.init().saveDocument(outputPath);
                    
                    AIScript.init().closeDocument(false);
                } catch (e) {
                    // Skip failed files
                }
            }
        }
    });
}

function generateIcons(count, width, height, outputFolder) {
    for (var i = 0; i < count; i++) {
        AIScript.init().createDocument({ width: width, height: height });
        
        var randomColor = ColorSystem.createHSBColor(Math.random() * 360, 70 + Math.random() * 30, 80 + Math.random() * 20);
        var shapeType = Math.floor(Math.random() * 4);
        
        var shape;
        switch (shapeType) {
            case 0:
                shape = ShapeTool.createCircle(width/2, height/2, Math.min(width, height) * 0.3, { fillColor: randomColor });
                break;
            case 1:
                shape = ShapeTool.createRectangle(width * 0.25, height * 0.25, width * 0.5, height * 0.5, { fillColor: randomColor });
                break;
            case 2:
                shape = ShapeTool.createPolygon(width/2, height/2, Math.min(width, height) * 0.3, 6, { fillColor: randomColor });
                break;
            case 3:
                shape = ShapeTool.createStar(width/2, height/2, Math.min(width, height) * 0.3, Math.min(width, height) * 0.15, 5, { fillColor: randomColor });
                break;
        }
        
        var outputPath = outputFolder + '/icon_' + (i + 1) + '.ai';
        AIScript.init().saveDocument(outputPath);
        AIScript.init().closeDocument(false);
    }
}

function exportAllArtboardsToPNG(outputFolder, resolution) {
    for (var i = 0; i < app.activeDocument.artboards.length; i++) {
        var artboard = app.activeDocument.artboards[i];
        artboard.visible = true;
        
        for (var j = 0; j < app.activeDocument.artboards.length; j++) {
            if (j !== i) {
                app.activeDocument.artboards[j].visible = false;
            }
        }
        
        var outputPath = outputFolder + '/' + artboard.name + '.png';
        AIScript.init().exportToPNG(outputPath, { resolution: resolution });
    }
}
```

---

## 十二、故障排查与性能优化

### 12.1 常见错误与解决方案

```javascript
class ErrorDiagnostics {
    static get COMMON_ERRORS() {
        return {
            'FontNotFound': {
                message: '字体未找到',
                causes: ['字体未安装', '字体名称错误', '字体文件损坏'],
                solutions: ['安装缺失字体', '检查字体名称', '重新安装字体']
            },
            'FileCorrupt': {
                message: '文件损坏',
                causes: ['文件保存中断', '磁盘错误', '版本不兼容'],
                solutions: ['尝试恢复备份', '检查磁盘', '使用兼容版本打开']
            },
            'MemoryFull': {
                message: '内存不足',
                causes: ['文档过大', '内存不足', '缓存过多'],
                solutions: ['关闭其他程序', '清理缓存', '增加系统内存']
            },
            'FilterNotAvailable': {
                message: '滤镜不可用',
                causes: ['滤镜未安装', '版本不支持', 'GPU加速问题'],
                solutions: ['安装滤镜', '更新软件', '关闭GPU加速']
            },
            'InvalidPath': {
                message: '无效路径',
                causes: ['路径不存在', '权限不足', '文件名错误'],
                solutions: ['检查路径', '获取权限', '修正文件名']
            },
            'MissingPlugin': {
                message: '插件缺失',
                causes: ['插件未安装', '插件版本不兼容'],
                solutions: ['安装插件', '更新插件版本']
            }
        };
    }

    static diagnoseError(errorCode) {
        return this.COMMON_ERRORS[errorCode] || null;
    }

    static checkSystemRequirements() {
        const requirements = {
            minimumRAM: 8 * 1024 * 1024 * 1024,
            recommendedRAM: 16 * 1024 * 1024 * 1024,
            minimumDiskSpace: 10 * 1024 * 1024 * 1024,
            recommendedDiskSpace: 50 * 1024 * 1024 * 1024
        };
        
        return {
            requirements: requirements
        };
    }
}
```

### 12.2 性能优化策略

```javascript
class PerformanceOptimizer {
    static optimizeDocument() {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Optm'), desc, DialogModes.NO);
    }

    static disableGPUAcceleration() {
        app.preferences.gpuAcceleration = false;
    }

    static enableGPUAcceleration() {
        app.preferences.gpuAcceleration = true;
    }

    static setRasterEffectResolution(resolution) {
        app.activeDocument.rasterEffect = resolution;
    }

    static clearCache() {
        var cacheFolder = app.preferences.cacheFolder;
        var folder = new Folder(cacheFolder);
        if (folder.exists) {
            var files = folder.getFiles();
            files.forEach(function(file) {
                if (file.constructor.name === 'File') {
                    file.remove();
                }
            });
        }
    }

    static reduceDocumentSize() {
        this.flattenLayers();
        this.removeUnusedSwatches();
        this.removeUnusedSymbols();
        this.optimizePaths();
    }

    static flattenLayers() {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Fltt'), desc, DialogModes.NO);
    }

    static removeUnusedSwatches() {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Swtc'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('RmUn'), desc, DialogModes.NO);
    }

    static removeUnusedSymbols() {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Symb'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('RmUn'), desc, DialogModes.NO);
    }

    static optimizePaths() {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Path'), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Smpl'), desc, DialogModes.NO);
    }

    static getDocumentStats() {
        var doc = app.activeDocument;
        return {
            pageItems: doc.pageItems.length,
            layers: doc.layers.length,
            symbols: doc.symbols.length,
            swatches: doc.swatches.length,
            gradients: doc.gradients.length,
            fontsUsed: doc.fonts.length
        };
    }
}
```

---

---

## 十三、学术研究与论文索引

### 13.1 矢量图形学术论文索引

| 论文标题 | 作者 | 发表年份 | 期刊/会议 | 核心贡献 |
|---------|------|---------|----------|---------|
| Scale-Invariant Feature Transform | Lowe | 2004 | IJCV | SIFT特征检测算法 |
| Vectorization of Raster Images | Cohen et al. | 1995 | CVGIP | 位图矢量化方法 |
| Curve Reconstruction from Unorganized Points | Hoppe et al. | 1992 | SIGGRAPH | 点云曲线重建 |
| A New Approach to Variable-Bandwidth Smoothing | Green | 1991 | IEEE T-PAMI | 可变带宽平滑 |
| Bezier Curve Fitting with Adaptive Control Points | Wang et al. | 2006 | CGF | 自适应控制点贝塞尔拟合 |
| Polygon Simplification with Preservation of Characteristic Features | Saalfeld | 1999 | Computer Graphics Forum | 特征保留多边形简化 |
| Skeleton-Based Vectorization of Line Drawings | Wu et al. | 2019 | IEEE TIP | 骨架矢量化方法 |
| Deep Vector Graphics: Learning to Vectorize | Li et al. | 2020 | ICCV | 深度学习矢量化 |

### 13.2 图形设计与排版学术论文

| 论文标题 | 作者 | 发表年份 | 期刊/会议 | 核心贡献 |
|---------|------|---------|----------|---------|
| Computational Typography | Tam et al. | 2019 | SIGGRAPH | 计算排版理论 |
| Layout Optimization with Constrained Reinforcement Learning | Zhang et al. | 2020 | ACM MM | 布局优化 |
| AutoLayout: Automated Graphic Design Layout | Deng et al. | 2021 | AAAI | 自动化布局设计 |
| Neural Typography Design | Liu et al. | 2021 | ICCV | 神经网络字体设计 |
| Learning Design Principles from Humans | Lin et al. | 2022 | ACM CHI | 设计原则学习 |

### 13.3 行业标准文档

| 标准编号 | 标准名称 | 发布机构 | 发布年份 |
|---------|---------|---------|---------|
| ISO 14496-8 | MPEG-4 Part 8: Animation Framework eXtension | ISO/IEC | 2004 |
| W3C SVG | Scalable Vector Graphics | W3C | 2011 |
| W3C CSS | Cascading Style Sheets | W3C | 2018 |
| PDF/A | PDF for Archiving | ISO | 2005 |

### 13.4 学术资源推荐

**期刊**：
- ACM Transactions on Graphics (TOG)
- IEEE Transactions on Visualization and Computer Graphics (TVCG)
- Computer Graphics Forum (CGF)
- Journal of Visual Communication and Image Representation

**会议**：
- ACM SIGGRAPH
- IEEE Visualization (VIS)
- ACM CHI
- Eurographics

**研究机构**：
- MIT Media Lab
- Adobe Research
- Google Research
- Max Planck Institute for Informatics

**开源项目**：
- Inkscape: 开源矢量图形编辑器
- Sketch.js: Canvas绘图库
- Paper.js: 矢量图形脚本框架
- Snap.svg: SVG操作库

---

## 附录：Illustrator API参考表

### A.1 核心对象与方法

| 对象 | 方法 | 说明 |
|------|------|------|
| Application | open(), newDocument() | 打开/新建文档 |
| Document | layers, symbols, swatches | 获取资源集合 |
| Layer | pageItems, visible, locked | 图层属性 |
| PathItem | pathPoints, filled, stroked | 路径属性 |
| TextFrame | contents, textRange | 文本属性 |
| Symbol | instances, definition | 符号管理 |
| Swatch | colorType, colorValue | 色板属性 |

### A.2 脚本执行环境变量

| 变量 | 类型 | 说明 |
|------|------|------|
| app | Application | 应用程序对象 |
| $.writeln() | Function | 输出调试信息 |
| File | Object | 文件操作对象 |
| Folder | Object | 文件夹操作对象 |

### A.3 常用Action IDs

| 操作 | charID | 说明 |
|------|--------|------|
| 创建选区 | 'seld' | Select |
| 取消选择 | 'dsel' | Deselect |
| 复制 | 'copy' | Copy |
| 粘贴 | 'past' | Paste |
| 删除 | 'dele' | Delete |

---

**文档版本**: v1.1  
**适用版本**: Adobe Illustrator 2026  
**最后更新**: 2026-07-14  
**分类**: Illustrator知识库