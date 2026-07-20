# Illustrator 自动化脚本与批量处理完全指南

---

## 一、脚本基础

### 1.1 JavaScript基础

```javascript
// Illustrator脚本模板
#target illustrator

function main() {
    app.displayDialogs = DialogModes.NO;
    
    try {
        if (app.activeDocument === null) {
            alert("请先打开一个文档");
            return;
        }
        
        executeScript();
        
        alert("脚本执行完成");
    } catch (e) {
        alert("脚本错误: " + e.message);
    } finally {
        app.displayDialogs = DialogModes.ALL;
    }
}

function executeScript() {
    // 脚本逻辑
}

main();
```

### 1.2 核心对象

| 对象 | 用途 | 常用属性/方法 |
|------|------|-------------|
| **app** | 应用程序 | activeDocument, preferences |
| **Document** | 文档 | width, height, pages |
| **PageItem** | 页面元素 | position, size, visible |
| **PathItem** | 路径 | pathPoints, closed |
| **TextFrame** | 文本框 | contents, textRange |

---

## 二、文件批处理

### 2.1 批量打开与处理

```javascript
// 批量处理AI文件
function batchProcessAI(folderPath, outputPath) {
    var inputFolder = new Folder(folderPath);
    var outputFolder = new Folder(outputPath);
    
    if (!outputFolder.exists) {
        outputFolder.create();
    }
    
    var files = inputFolder.getFiles("*.ai");
    
    for (var i = 0; i < files.length; i++) {
        var doc = app.open(files[i]);
        
        processDocument(doc);
        
        var saveFile = new File(outputFolder.fsName + "/" + files[i].name);
        saveAsAI(doc, saveFile);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
}

function saveAsAI(doc, file) {
    var options = new IllustratorSaveOptions();
    options.compatibility = AICompatibility.ILLUSTRATOR2023;
    doc.saveAs(file, options);
}
```

### 2.2 批量导出不同格式

```javascript
// 批量导出多种格式
function batchExportFormats(inputFolder, outputFolder) {
    var files = new Folder(inputFolder).getFiles("*.ai");
    
    for (var i = 0; i < files.length; i++) {
        var doc = app.open(files[i]);
        var baseName = files[i].name.replace(/\.[^/.]+$/, "");
        
        // 导出PNG
        exportPNG(doc, outputFolder + "/" + baseName + ".png");
        
        // 导出SVG
        exportSVG(doc, outputFolder + "/" + baseName + ".svg");
        
        // 导出PDF
        exportPDF(doc, outputFolder + "/" + baseName + ".pdf");
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
}

function exportPNG(doc, filePath) {
    var options = new ExportOptionsPNG24();
    options.antiAliasing = true;
    options.horizontalScale = 100;
    options.verticalScale = 100;
    doc.exportFile(new File(filePath), ExportType.PNG24, options);
}
```

---

## 三、对象操作自动化

### 3.1 创建和操作对象

```javascript
// 创建矩形
function createRectangle(x, y, width, height, color) {
    var doc = app.activeDocument;
    var rect = doc.pathItems.rectangle(y, x, width, height);
    
    if (color) {
        rect.fillColor = color;
        rect.stroked = false;
    }
    
    return rect;
}

// 创建圆形
function createCircle(x, y, radius, color) {
    var doc = app.activeDocument;
    var circle = doc.pathItems.ellipse(y + radius, x - radius, radius * 2, radius * 2);
    circle.closed = true;
    
    if (color) {
        circle.fillColor = color;
        circle.stroked = false;
    }
    
    return circle;
}

// 创建多边形
function createPolygon(x, y, sides, radius, color) {
    var doc = app.activeDocument;
    var polygon = doc.pathItems.polygon(y, x, radius, sides);
    
    if (color) {
        polygon.fillColor = color;
        polygon.stroked = false;
    }
    
    return polygon;
}
```

### 3.2 批量操作对象

```javascript
// 批量选择和修改对象
function batchModifyObjects(properties) {
    var doc = app.activeDocument;
    
    for (var i = 0; i < doc.pageItems.length; i++) {
        var item = doc.pageItems[i];
        
        if (item.typename === "PathItem") {
            if (properties.fillColor) {
                item.fillColor = properties.fillColor;
            }
            if (properties.strokeColor) {
                item.strokeColor = properties.strokeColor;
            }
            if (properties.strokeWidth !== undefined) {
                item.strokeWidth = properties.strokeWidth;
            }
        }
    }
}

// 对齐对象
function alignObjects(alignType) {
    var doc = app.activeDocument;
    
    switch(alignType) {
        case "left":
            doc.selection.align(AlignOptions.ALIGNLEFT);
            break;
        case "center":
            doc.selection.align(AlignOptions.ALIGNHCENTER);
            break;
        case "right":
            doc.selection.align(AlignOptions.ALIGNRIGHT);
            break;
        case "top":
            doc.selection.align(AlignOptions.ALIGNTOP);
            break;
        case "middle":
            doc.selection.align(AlignOptions.ALIGNVCENTER);
            break;
        case "bottom":
            doc.selection.align(AlignOptions.ALIGNBOTTOM);
            break;
    }
}
```

---

## 四、文本操作自动化

### 4.1 创建和修改文本

```javascript
// 创建文本框
function createTextFrame(x, y, width, height, text, fontSize) {
    var doc = app.activeDocument;
    var textFrame = doc.textFrames.add();
    
    textFrame.geometricBounds = [y, x, y + height, x + width];
    textFrame.contents = text;
    
    if (fontSize) {
        textFrame.textRange.characterAttributes.size = fontSize;
    }
    
    return textFrame;
}

// 修改文本属性
function modifyTextAttributes(textFrame, attributes) {
    var range = textFrame.textRange;
    
    if (attributes.font) {
        range.characterAttributes.textFont = app.textFonts.getByName(attributes.font);
    }
    if (attributes.size) {
        range.characterAttributes.size = attributes.size;
    }
    if (attributes.color) {
        range.characterAttributes.fillColor = attributes.color;
    }
    if (attributes.leading) {
        range.characterAttributes.leading = attributes.leading;
    }
}
```

### 4.2 批量文本处理

```javascript
// 批量替换文本
function batchReplaceText(oldText, newText) {
    var doc = app.activeDocument;
    
    for (var i = 0; i < doc.textFrames.length; i++) {
        var textFrame = doc.textFrames[i];
        textFrame.contents = textFrame.contents.replace(oldText, newText);
    }
}

// 批量调整字体大小
function batchResizeText(scalePercent) {
    var doc = app.activeDocument;
    
    for (var i = 0; i < doc.textFrames.length; i++) {
        var textFrame = doc.textFrames[i];
        var currentSize = textFrame.textRange.characterAttributes.size;
        textFrame.textRange.characterAttributes.size = currentSize * (scalePercent / 100);
    }
}
```

---

## 五、路径操作自动化

### 5.1 路径创建和编辑

```javascript
// 创建自定义路径
function createCustomPath(points) {
    var doc = app.activeDocument;
    var path = doc.pathItems.add();
    
    path.setEntirePath(points);
    path.closed = true;
    
    return path;
}

// 简化路径
function simplifyPath(path, tolerance) {
    path.simplify(tolerance, true, true, true, false, false, false);
}

// 偏移路径
function offsetPath(path, offset) {
    var newPath = path.offsetPath(offset);
    return newPath;
}
```

### 5.2 路径布尔运算

```javascript
// 路径联合
function unitePaths(paths) {
    var result = paths[0];
    
    for (var i = 1; i < paths.length; i++) {
        result = result.unite(paths[i]);
    }
    
    return result;
}

// 路径减去
function subtractPaths(target, subtractors) {
    var result = target;
    
    for (var i = 0; i < subtractors.length; i++) {
        result = result.subtractPath(subtractors[i]);
    }
    
    return result;
}

// 路径相交
function intersectPaths(paths) {
    var result = paths[0];
    
    for (var i = 1; i < paths.length; i++) {
        result = result.intersect(paths[i]);
    }
    
    return result;
}
```

---

## 六、颜色和样式

### 6.1 颜色管理

```javascript
// 创建RGB颜色
function createRGBColor(red, green, blue) {
    var color = new RGBColor();
    color.red = red;
    color.green = green;
    color.blue = blue;
    return color;
}

// 创建CMYK颜色
function createCMYKColor(cyan, magenta, yellow, black) {
    var color = new CMYKColor();
    color.cyan = cyan;
    color.magenta = magenta;
    color.yellow = yellow;
    color.black = black;
    return color;
}

// 创建渐变色
function createGradientColor(colors, locations) {
    var gradient = new Gradient();
    gradient.type = GradientType.LINEAR;
    
    for (var i = 0; i < colors.length; i++) {
        var stop = new GradientStop();
        stop.color = colors[i];
        stop.location = locations[i] || (i / (colors.length - 1)) * 100;
        gradient.gradientStops.add(stop);
    }
    
    return gradient;
}
```

### 6.2 样式管理

```javascript
// 应用样式
function applyStyle(item, styleName) {
    var style = app.activeDocument.characterStyles.getByName(styleName);
    if (style) {
        item.applyCharacterStyle(style);
    }
}

// 创建字符样式
function createCharacterStyle(name, attributes) {
    var doc = app.activeDocument;
    var style = doc.characterStyles.add(name);
    
    if (attributes.font) {
        style.characterAttributes.textFont = app.textFonts.getByName(attributes.font);
    }
    if (attributes.size) {
        style.characterAttributes.size = attributes.size;
    }
    if (attributes.color) {
        style.characterAttributes.fillColor = attributes.color;
    }
    
    return style;
}

// 创建段落样式
function createParagraphStyle(name, attributes) {
    var doc = app.activeDocument;
    var style = doc.paragraphStyles.add(name);
    
    if (attributes.alignment) {
        style.paragraphAttributes.justification = attributes.alignment;
    }
    if (attributes.leading) {
        style.paragraphAttributes.spaceAfter = attributes.leading;
    }
    
    return style;
}
```

---

## 七、图层操作

### 7.1 图层管理

```javascript
// 创建图层
function createLayer(name, color) {
    var doc = app.activeDocument;
    var layer = doc.layers.add();
    layer.name = name;
    
    if (color) {
        layer.color = color;
    }
    
    return layer;
}

// 移动对象到图层
function moveToLayer(item, layer) {
    item.moveToBeginning(layer);
}

// 批量移动对象到图层
function batchMoveToLayer(items, layer) {
    for (var i = 0; i < items.length; i++) {
        items[i].moveToBeginning(layer);
    }
}
```

### 7.2 图层属性

```javascript
// 显示/隐藏图层
function toggleLayerVisibility(layer, visible) {
    layer.visible = visible;
}

// 锁定/解锁图层
function toggleLayerLock(layer, locked) {
    layer.locked = locked;
}

// 合并图层
function mergeLayers(layers) {
    var doc = app.activeDocument;
    var targetLayer = layers[0];
    
    for (var i = 1; i < layers.length; i++) {
        layers[i].mergeLayers(targetLayer);
    }
    
    return targetLayer;
}
```

---

## 八、画板操作

### 8.1 画板管理

```javascript
// 创建画板
function createArtboard(x, y, width, height, name) {
    var doc = app.activeDocument;
    var artboard = doc.artboards.add([x, y, x + width, y + height]);
    
    if (name) {
        artboard.name = name;
    }
    
    return artboard;
}

// 设置活动画板
function setActiveArtboard(index) {
    app.activeDocument.artboards.setActiveArtboardIndex(index);
}

// 调整画板大小
function resizeArtboard(artboard, width, height) {
    var rect = artboard.artboardRect;
    artboard.artboardRect = [rect[0], rect[1], rect[0] + width, rect[1] - height];
}
```

### 8.2 批量画板操作

```javascript
// 批量创建画板
function batchCreateArtboards(count, width, height, spacing) {
    var doc = app.activeDocument;
    var currentX = 0;
    var currentY = 0;
    
    for (var i = 0; i < count; i++) {
        doc.artboards.add([currentX, currentY, currentX + width, currentY - height]);
        currentX += width + spacing;
        
        if ((i + 1) % 4 === 0) {
            currentX = 0;
            currentY -= height + spacing;
        }
    }
}
```

---

## 九、常用脚本示例

### 9.1 生成图标

```javascript
// 生成图标网格
function generateIconGrid(iconSize, columns, rows, spacing) {
    var doc = app.activeDocument;
    var startX = 100;
    var startY = 100;
    
    for (var row = 0; row < rows; row++) {
        for (var col = 0; col < columns; col++) {
            var x = startX + col * (iconSize + spacing);
            var y = startY + row * (iconSize + spacing);
            
            var rect = createRectangle(x, y, iconSize, iconSize);
            rect.strokeColor = createRGBColor(100, 100, 100);
            rect.strokeWidth = 1;
        }
    }
}
```

### 9.2 创建图表

```javascript
// 创建柱状图
function createBarChart(data, x, y, width, height) {
    var doc = app.activeDocument;
    var barWidth = width / data.length;
    var maxValue = Math.max.apply(null, data);
    
    for (var i = 0; i < data.length; i++) {
        var barHeight = (data[i] / maxValue) * height;
        var barX = x + i * barWidth;
        var barY = y - barHeight;
        
        var bar = createRectangle(barX, barY, barWidth - 5, barHeight);
        bar.fillColor = createRGBColor(50 + i * 30, 100, 150);
    }
}
```

---

## 十、性能优化

### 10.1 脚本优化技巧

| 技巧 | 说明 |
|------|------|
| **关闭对话框** | `app.displayDialogs = DialogModes.NO` |
| **禁用屏幕刷新** | `app.scriptPreferences.enableRedraw = false` |
| **批量操作** | 使用数组操作而非逐个操作 |
| **缓存对象** | 避免重复查询DOM |
| **使用原生方法** | 优先使用内置方法 |

### 10.2 内存管理

```javascript
// 优化内存使用
function optimizeMemory() {
    app.purge();
}
```

---

> **关联文档**：
> - [[Illustrator-矢量图形与MG动画完全手册]]
> - [[Illustrator-矢量图形与MG动画指南]]