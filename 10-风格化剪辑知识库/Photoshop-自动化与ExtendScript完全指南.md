# Photoshop 自动化与ExtendScript完全指南

> 版本: 2025-v1 | 适用: 批处理/自动化脚本/工作流优化

## 一、ExtendScript 基础

### 1.1 脚本环境

| 项目 | 说明 |
|------|------|
| 语言 | JavaScript (ES3兼容) |
| 执行 | 文件→脚本→浏览 / ExtendScript Toolkit |
| 调试 | ExtendScript Toolkit (ESTK) |
| 面板 | Window → Extensions (CEP) |

### 1.2 核心对象模型

```
Application (app)
├── Documents (文档集合)
│   ├── Document
│   │   ├── Layers (图层集合)
│   │   │   ├── Layer
│   │   │   ├── ArtLayer
│   │   │   └── LayerSet (图层组)
│   │   ├── Channels
│   │   ├── Selection
│   │   └── PathItems
│   ├── ActiveDocument
│   └── ActiveLayer
├── Preferences
└── Fonts
```

### 1.3 常用脚本模板

```javascript
// 基础模板
#target photoshop
var doc = app.activeDocument;
var layer = doc.activeLayer;

// 遍历所有图层
function traverseLayers(parent) {
    for (var i = 0; i < parent.layers.length; i++) {
        var layer = parent.layers[i];
        if (layer.typename === "LayerSet") {
            traverseLayers(layer); // 递归进入组
        } else {
            // 处理图层
            $.writeln(layer.name + " - " + layer.kind);
        }
    }
}
traverseLayers(doc);
```

## 二、批处理自动化

### 2.1 动作(Action)批处理

```
文件 → 自动 → 批处理
1. 选择动作集和动作
2. 源: 文件夹/导入
3. 目标: 文件夹/无
4. 选项: 覆盖"打开"命令/禁止文件浏览器
```

### 2.2 脚本批处理

```javascript
// batch_process.jsx - 批量处理文件夹中所有图片
#target photoshop
var inputFolder = Folder.selectDialog("选择输入文件夹");
var outputFolder = Folder.selectDialog("选择输出文件夹");

if (inputFolder && outputFolder) {
    var files = inputFolder.getFiles(/\.(jpg|jpeg|png|tif|tiff|psd)$/i);
    
    for (var i = 0; i < files.length; i++) {
        var doc = app.open(files[i]);
        
        // 调整大小
        doc.resizeImage(UnitValue(1920, "px"), UnitValue(1080, "px"), 72);
        
        // 锐化
        doc.activeLayer.applySmartSharpen(100, 1.2, 1);
        
        // 导出
        var outFile = new File(outputFolder + "/processed_" + files[i].name.replace(/\.[^.]+$/, ".jpg"));
        var opts = new JPEGSaveOptions();
        opts.quality = 10;
        opts.embedColorProfile = true;
        doc.saveAs(outFile, opts, true);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
    alert("处理完成! 共 " + files.length + " 个文件");
}
```

### 2.3 条件批处理

```javascript
// conditional_batch.jsx - 根据条件处理
#target photoshop
var files = Folder.selectDialog("选择文件夹").getFiles("*.psd");

for (var i = 0; i < files.length; i++) {
    var doc = app.open(files[i]);
    
    // 检查是否有智能对象
    var hasSmartObject = false;
    for (var j = 0; j < doc.layers.length; j++) {
        if (doc.layers[j].kind === LayerKind.SMARTOBJECT) {
            hasSmartObject = true;
            break;
        }
    }
    
    if (hasSmartObject) {
        // 有智能对象的PSD: 导出高质量
        exportHighQuality(doc);
    } else {
        // 普通PSD: 标准导出
        exportStandard(doc);
    }
    
    doc.close(SaveOptions.DONOTSAVECHANGES);
}
```

## 三、高级脚本技术

### 3.1 图层操作

```javascript
// 创建调整图层
var levelsLayer = doc.artLayers.add();
levelsLayer.name = "Levels Adjustment";

// 创建文字图层
var textLayer = doc.artLayers.add();
var textItem = textLayer.kind = LayerKind.TEXT;
// 注意: 需要通过ActionManager创建文字

// 复制图层到另一个文档
var sourceDoc = app.activeDocument;
var targetDoc = app.documents.add(1920, 1080, 72, "New Doc");
sourceDoc.activeLayer.duplicate(targetDoc);

// 导出所有图层为单独文件
function exportLayers(doc, outputFolder) {
    for (var i = 0; i < doc.layers.length; i++) {
        doc.activeLayer = doc.layers[i];
        // 隐藏其他图层
        for (var j = 0; j < doc.layers.length; j++) {
            doc.layers[j].visible = (j === i);
        }
        // 导出
        var opts = new PNGSaveOptions();
        var file = new File(outputFolder + "/" + doc.layers[i].name + ".png");
        doc.saveAs(file, opts);
    }
}
```

### 3.2 ActionManager 调用

```javascript
// ActionManager 可以调用PS内部所有功能
// 比DOM API更全面但更复杂

// 示例: 应用Camera Raw滤镜
function applyCameraRaw() {
    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
    desc.putReference(charIDToTypeID("null"), ref);
    
    var filterDesc = new ActionDescriptor();
    filterDesc.putPath(charIDToTypeID("FlNm"), new File("/path/to/settings.xmp"));
    desc.putObject(charIDToTypeID("Usng"), stringIDToTypeID("cameraRaw"), filterDesc);
    
    executeAction(stringIDToTypeID("cameraRawFilter"), desc, DialogModes.NO);
}
```

### 3.3 CEP 扩展面板

```
CEP (Common Extensibility Platform) 允许创建HTML/JS面板:
├── CSXS/
│   └── manifest.xml (面板配置)
├── client/
│   ├── index.html
│   ├── main.js
│   └── style.css
└── host/
    └── index.jsx (ExtendScript宿主)
```

## 四、与视频工作流自动化集成

### 4.1 自动导出素材

```javascript
// export_for_ae.jsx - 自动导出AE所需素材
#target photoshop
var doc = app.activeDocument;

// 导出PSD(保留图层)
var psdOpts = new PhotoshopSaveOptions();
psdOpts.layers = true;
doc.saveAs(new File("~/Desktop/project.psd"), psdOpts);

// 导出透明PNG序列(当前可见)
var pngOpts = new PNGSaveOptions();
doc.saveAs(new File("~/Desktop/project_preview.png"), pngOpts);

// 导出各图层为单独PNG
var layerFolder = new Folder("~/Desktop/layers");
layerFolder.create();
for (var i = 0; i < doc.layers.length; i++) {
    for (var j = 0; j < doc.layers.length; j++) {
        doc.layers[j].visible = (j === i);
    }
    doc.saveAs(new File(layerFolder + "/" + doc.layers[i].name + ".png"), pngOpts);
}
```

### 4.2 批量水印

```javascript
// batch_watermark.jsx
#target photoshop
var folder = Folder.selectDialog("选择文件夹");
var files = folder.getFiles(/\.(jpg|png)$/i);
var watermarkText = "© 2025 Studio";

for (var i = 0; i < files.length; i++) {
    var doc = app.open(files[i]);
    
    // 创建文字水印
    var wLayer = doc.artLayers.add();
    // 设置文字(通过ActionManager)
    // 位置: 右下角
    // 颜色: 白色, 50%不透明度
    // 字体: Arial, 24pt
    
    // 导出
    var opts = new JPEGSaveOptions();
    opts.quality = 10;
    doc.saveAs(files[i], opts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
}
```
