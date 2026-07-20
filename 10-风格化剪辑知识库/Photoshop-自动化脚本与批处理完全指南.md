# Photoshop 自动化脚本与批处理完全指南

---

## 一、脚本基础

### 1.1 JavaScript基础

```javascript
// Photoshop脚本模板
#target photoshop

function main() {
    app.displayDialogs = DialogModes.NO;
    
    try {
        // 检查是否有打开的文档
        if (app.documents.length === 0) {
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
| **app** | 应用程序 | documents, preferences |
| **Document** | 文档 | width, height, layers |
| **Layer** | 图层 | name, opacity, visible |
| **Selection** | 选区 | selectAll(), invert() |
| **Channel** | 通道 | redChannel, greenChannel |

---

## 二、批处理操作

### 2.1 文件批处理

```javascript
// 批量处理文件夹中的图片
function batchProcess(folderPath, outputPath) {
    var inputFolder = new Folder(folderPath);
    var outputFolder = new Folder(outputPath);
    
    if (!outputFolder.exists) {
        outputFolder.create();
    }
    
    var files = inputFolder.getFiles("*.jpg");
    
    for (var i = 0; i < files.length; i++) {
        var file = files[i];
        var doc = app.open(file);
        
        // 处理逻辑
        processDocument(doc);
        
        // 保存
        var saveFile = new File(outputFolder.fsName + "/" + file.name);
        saveAsJPEG(doc, saveFile);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
}

function saveAsJPEG(doc, file) {
    var options = new JPEGSaveOptions();
    options.quality = 12;
    options.embedColorProfile = true;
    doc.saveAs(file, options);
}
```

### 2.2 动作录制与执行

```javascript
// 执行动作
function executeActionSet(actionSetName, actionName) {
    var actionSet = app.actionSets.getByName(actionSetName);
    var action = actionSet.actions.getByName(actionName);
    action.play();
}

// 录制动作
function recordAction(actionName) {
    app.beginRecording();
    // 操作...
    app.endRecording();
}
```

---

## 三、图层操作自动化

### 3.1 图层管理

```javascript
// 创建图层
function createLayer(name) {
    var doc = app.activeDocument;
    var layer = doc.artLayers.add();
    layer.name = name;
    return layer;
}

// 批量重命名图层
function renameLayers(prefix) {
    var doc = app.activeDocument;
    
    for (var i = 0; i < doc.layers.length; i++) {
        doc.layers[i].name = prefix + "_" + (i + 1);
    }
}

// 合并可见图层
function mergeVisibleLayers() {
    var doc = app.activeDocument;
    doc.mergeVisibleLayers();
}
```

### 3.2 图层样式

```javascript
// 添加图层样式
function addLayerStyle(layer, styleType) {
    switch(styleType) {
        case "dropShadow":
            layer.applyStyle("Drop Shadow");
            break;
        case "bevelEmboss":
            layer.applyStyle("Bevel and Emboss");
            break;
        case "outerGlow":
            layer.applyStyle("Outer Glow");
            break;
    }
}

// 自定义图层样式
function createCustomStyle(layer) {
    var effects = layer.layerEffects;
    
    // 添加阴影
    var shadow = effects.add(EffectType.DROPSHADOW);
    shadow.size = 10;
    shadow.opacity = 50;
    shadow.angle = 135;
    
    // 添加描边
    var stroke = effects.add(EffectType.STROKE);
    stroke.size = 2;
    stroke.color = new SolidColor();
    stroke.color.rgb.hexValue = "FFFFFF";
}
```

---

## 四、选区与蒙版自动化

### 4.1 选区操作

```javascript
// 创建选区
function createSelection(rect) {
    var doc = app.activeDocument;
    var sel = doc.selection;
    
    sel.select([
        [rect.left, rect.top],
        [rect.right, rect.top],
        [rect.right, rect.bottom],
        [rect.left, rect.bottom]
    ]);
}

// 扩展选区
function expandSelection(pixels) {
    app.activeDocument.selection.expand(pixels);
}

// 收缩选区
function contractSelection(pixels) {
    app.activeDocument.selection.contract(pixels);
}

// 羽化选区
function featherSelection(radius) {
    app.activeDocument.selection.feather(radius);
}
```

### 4.2 蒙版操作

```javascript
// 添加图层蒙版
function addLayerMask(layer) {
    layer.addLayerMask();
}

// 从选区创建蒙版
function createMaskFromSelection(layer) {
    layer.addLayerMask();
    layer.mask.invert();
}

// 应用蒙版
function applyMask(layer) {
    layer.applyLayerMask();
}

// 删除蒙版
function removeMask(layer) {
    layer.removeLayerMask();
}
```

---

## 五、滤镜自动化

### 5.1 应用滤镜

```javascript
// 应用滤镜
function applyFilter(filterName) {
    var doc = app.activeDocument;
    
    switch(filterName) {
        case "gaussianBlur":
            doc.activeLayer.applyGaussianBlur(5);
            break;
        case "unsharpMask":
            doc.activeLayer.applyUnsharpMask(50, 1, 0);
            break;
        case "motionBlur":
            doc.activeLayer.applyMotionBlur(0, 10);
            break;
    }
}

// 智能滤镜
function applySmartFilter(filterName) {
    var layer = app.activeDocument.activeLayer;
    layer.convertToSmartObject();
    
    var smartFilters = layer.smartFilters;
    smartFilters.add(filterName);
}
```

### 5.2 批量滤镜应用

```javascript
// 批量应用滤镜到所有图层
function applyFilterToAllLayers(filterName) {
    var doc = app.activeDocument;
    
    for (var i = 0; i < doc.layers.length; i++) {
        doc.activeLayer = doc.layers[i];
        applyFilter(filterName);
    }
}
```

---

## 六、色彩调整自动化

### 6.1 调整图层

```javascript
// 创建调整图层
function createAdjustmentLayer(type) {
    var doc = app.activeDocument;
    var layer = doc.artLayers.add();
    
    switch(type) {
        case "levels":
            var levels = layer.adjustmentLayer;
            levels.kind = AdjustmentLayerKind.LEVELS;
            break;
        case "curves":
            var curves = layer.adjustmentLayer;
            curves.kind = AdjustmentLayerKind.CURVES;
            break;
        case "hueSaturation":
            var hueSat = layer.adjustmentLayer;
            hueSat.kind = AdjustmentLayerKind.HUESATURATION;
            break;
    }
    
    return layer;
}

// 自动色阶
function autoLevels() {
    app.activeDocument.autoLevels();
}

// 自动对比度
function autoContrast() {
    app.activeDocument.autoContrast();
}

// 自动颜色
function autoColor() {
    app.activeDocument.autoColor();
}
```

### 6.2 批量色彩调整

```javascript
// 批量调整图片色彩
function batchColorAdjust(inputFolder, outputFolder) {
    var files = new Folder(inputFolder).getFiles("*.jpg");
    
    for (var i = 0; i < files.length; i++) {
        var doc = app.open(files[i]);
        
        // 自动颜色调整
        doc.autoColor();
        
        // 保存
        var saveFile = new File(outputFolder + "/" + files[i].name);
        var options = new JPEGSaveOptions();
        options.quality = 12;
        doc.saveAs(saveFile, options);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
}
```

---

## 七、文件格式与保存

### 7.1 多格式导出

```javascript
// 导出多种格式
function exportMultipleFormats(doc, basePath) {
    // 导出JPEG
    var jpegOptions = new JPEGSaveOptions();
    jpegOptions.quality = 12;
    doc.saveAs(new File(basePath + ".jpg"), jpegOptions);
    
    // 导出PNG
    var pngOptions = new PNGSaveOptions();
    pngOptions.interlaced = false;
    doc.saveAs(new File(basePath + ".png"), pngOptions);
    
    // 导出PSD
    var psdOptions = new PhotoshopSaveOptions();
    psdOptions.embedColorProfile = true;
    doc.saveAs(new File(basePath + ".psd"), psdOptions);
}
```

### 7.2 批量转换格式

```javascript
// 批量转换图片格式
function batchConvertFormat(inputFolder, outputFolder, targetFormat) {
    var files = new Folder(inputFolder).getFiles();
    
    for (var i = 0; i < files.length; i++) {
        if (files[i] instanceof File && files[i].hidden === false) {
            var doc = app.open(files[i]);
            var baseName = files[i].name.replace(/\.[^/.]+$/, "");
            var saveFile = new File(outputFolder + "/" + baseName + "." + targetFormat);
            
            switch(targetFormat.toLowerCase()) {
                case "jpg":
                case "jpeg":
                    var jpegOptions = new JPEGSaveOptions();
                    jpegOptions.quality = 12;
                    doc.saveAs(saveFile, jpegOptions);
                    break;
                case "png":
                    var pngOptions = new PNGSaveOptions();
                    doc.saveAs(saveFile, pngOptions);
                    break;
                case "tif":
                case "tiff":
                    var tiffOptions = new TiffSaveOptions();
                    tiffOptions.embedColorProfile = true;
                    doc.saveAs(saveFile, tiffOptions);
                    break;
            }
            
            doc.close(SaveOptions.DONOTSAVECHANGES);
        }
    }
}
```

---

## 八、图像大小与分辨率

### 8.1 调整图像大小

```javascript
// 调整图像大小
function resizeImage(width, height, resampleMethod) {
    var doc = app.activeDocument;
    
    doc.resizeImage(
        UnitValue(width, "px"),
        UnitValue(height, "px"),
        doc.resolution,
        resampleMethod
    );
}

// 按比例缩放
function scaleImage(scalePercent) {
    var doc = app.activeDocument;
    var newWidth = doc.width * (scalePercent / 100);
    var newHeight = doc.height * (scalePercent / 100);
    
    doc.resizeImage(newWidth, newHeight);
}
```

### 8.2 批量调整大小

```javascript
// 批量调整图片大小
function batchResize(inputFolder, outputFolder, maxWidth, maxHeight) {
    var files = new Folder(inputFolder).getFiles("*.jpg");
    
    for (var i = 0; i < files.length; i++) {
        var doc = app.open(files[i]);
        
        // 计算缩放比例
        var scale = Math.min(maxWidth / doc.width, maxHeight / doc.height);
        
        if (scale < 1) {
            var newWidth = doc.width * scale;
            var newHeight = doc.height * scale;
            doc.resizeImage(newWidth, newHeight);
        }
        
        var saveFile = new File(outputFolder + "/" + files[i].name);
        var options = new JPEGSaveOptions();
        options.quality = 12;
        doc.saveAs(saveFile, options);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
}
```

---

## 九、常用脚本示例

### 9.1 水印添加

```javascript
// 添加文字水印
function addWatermark(text) {
    var doc = app.activeDocument;
    
    // 创建文字图层
    var textLayer = doc.artLayers.add();
    textLayer.kind = LayerKind.TEXT;
    textLayer.textItem.contents = text;
    textLayer.textItem.size = 24;
    textLayer.textItem.color.rgb.hexValue = "FFFFFF";
    textLayer.opacity = 50;
    
    // 移动到右下角
    textLayer.translate(doc.width - 200, doc.height - 50);
}
```

### 9.2 批量重命名

```javascript
// 批量重命名文件
function batchRename(inputFolder, prefix) {
    var files = new Folder(inputFolder).getFiles("*.jpg");
    
    for (var i = 0; i < files.length; i++) {
        var newName = prefix + "_" + String(i + 1).padStart(4, "0") + ".jpg";
        files[i].rename(newName);
    }
}
```

---

## 十、性能优化

### 10.1 脚本优化技巧

| 技巧 | 说明 |
|------|------|
| **关闭对话框** | `app.displayDialogs = DialogModes.NO` |
| **关闭历史记录** | `app.preferences.enableHistory = false` |
| **批量处理** | 一次性处理多个文件 |
| **缓存对象** | 避免重复查询DOM |
| **使用原生方法** | 优先使用内置方法而非循环 |

### 10.2 内存管理

```javascript
// 优化内存使用
function optimizeMemory() {
    app.purge(PurgeTarget.CACHES);
    app.purge(PurgeTarget.HISTORY);
}
```

---

> **关联文档**：
> - [[Photoshop-图像处理完全指南]]
> - [[Photoshop-图层管理与操作完全手册]]
> - [[Photoshop-企业级集成与图像处理指南]]