# Photoshop 企业级集成与图像处理指南

---

## 一、Photoshop 架构与核心组件

### 1.1 对象模型层次

```javascript
// Photoshop DOM 层次结构
// Application
//   └── Document
//       ├── Layer
//       │   ├── ArtLayer
//       │   ├── TextLayer
//       │   └── AdjustmentLayer
//       ├── Channel
//       ├── Path
//       └── HistoryState
```

### 1.2 核心对象

| 对象 | 描述 | 关键方法 |
|------|------|---------|
| **Application** | Photoshop 应用程序 | open(), newDocument(), quit() |
| **Document** | 当前文档 | save(), saveAs(), resizeCanvas() |
| **Layer** | 图层基类 | visible, locked, opacity |
| **ArtLayer** | 普通图层 | duplicate(), merge(), applyLayerStyle() |
| **TextLayer** | 文本图层 | contents, fontSize, fontName |
| **AdjustmentLayer** | 调整图层 | create(), setProperty() |
| **Channel** | 通道 | select(), duplicate(), invert() |
| **Path** | 路径 | makeSelection(), fillPath() |

### 1.3 JavaScript API 初始化

```javascript
var Photoshop = {
    app: null,
    doc: null,
    
    init: function() {
        this.app = app;
        this.doc = this.app.activeDocument;
        return true;
    },
    
    createNewDocument: function(config) {
        var defaults = {
            width: 1920,
            height: 1080,
            resolution: 72,
            mode: DocumentMode.RGB,
            fill: DocumentFill.WHITE,
            name: "Untitled_" + new Date().getTime()
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        this.doc = this.app.documents.add(
            cfg.width,
            cfg.height,
            cfg.resolution,
            cfg.name,
            cfg.mode,
            cfg.fill
        );
        
        return this.doc;
    },
    
    openDocument: function(filePath) {
        try {
            var file = new File(filePath);
            this.doc = this.app.open(file);
            return this.doc;
        } catch (e) {
            $.writeln("打开文档失败: " + e.message);
            return null;
        }
    },
    
    getDocumentInfo: function(doc) {
        var d = doc || this.doc;
        if (!d) return null;
        
        return {
            name: d.name,
            path: d.path,
            width: d.width,
            height: d.height,
            resolution: d.resolution,
            mode: d.mode.toString(),
            bitDepth: d.bitDepth,
            layerCount: d.layers.length,
            channelCount: d.channels.length
        };
    },
    
    getVersion: function() {
        return this.app.version;
    }
};
```

---

## 二、文档管理

### 2.1 文档创建与打开

```javascript
var DocumentManager = {
    createDocument: function(config) {
        var defaults = {
            width: 1920,
            height: 1080,
            resolution: 72,
            mode: DocumentMode.RGB,
            fill: DocumentFill.WHITE,
            name: "Untitled_" + new Date().getTime()
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            return Photoshop.app.documents.add(
                cfg.width,
                cfg.height,
                cfg.resolution,
                cfg.name,
                cfg.mode,
                cfg.fill
            );
        } catch (e) {
            $.writeln("创建文档失败: " + e.message);
            return null;
        }
    },
    
    createCanvasDocument: function(width, height, color) {
        try {
            var doc = Photoshop.app.documents.add(width, height, 72, "Canvas");
            
            var bgLayer = doc.layers[0];
            var fillColor = new SolidColor();
            
            if (color) {
                fillColor.rgb.red = color.r || 255;
                fillColor.rgb.green = color.g || 255;
                fillColor.rgb.blue = color.b || 255;
            } else {
                fillColor.rgb.red = 255;
                fillColor.rgb.green = 255;
                fillColor.rgb.blue = 255;
            }
            
            bgLayer.fill(fillColor);
            return doc;
        } catch (e) {
            $.writeln("创建画布失败: " + e.message);
            return null;
        }
    },
    
    openDocument: function(filePath) {
        try {
            var file = new File(filePath);
            return Photoshop.app.open(file);
        } catch (e) {
            $.writeln("打开文档失败: " + e.message);
            return null;
        }
    },
    
    closeDocument: function(doc) {
        try {
            (doc || Photoshop.doc).close(SaveOptions.DONOTSAVECHANGES);
            return true;
        } catch (e) {
            $.writeln("关闭文档失败: " + e.message);
            return false;
        }
    }
};
```

### 2.2 文档保存

```javascript
var DocumentSaver = {
    saveAsPSD: function(doc, filePath) {
        try {
            var d = doc || Photoshop.doc;
            var file = new File(filePath);
            
            var options = new PhotoshopSaveOptions();
            options.embedColorProfile = true;
            
            d.saveAs(file, options, true, Extension.LOWERCASE);
            return true;
        } catch (e) {
            $.writeln("保存为PSD失败: " + e.message);
            return false;
        }
    },
    
    saveAsPNG: function(doc, filePath, options) {
        try {
            var d = doc || Photoshop.doc;
            var file = new File(filePath);
            
            var pngOptions = new PNGSaveOptions();
            pngOptions.interlaced = options && options.interlaced || false;
            pngOptions.compression = options && options.compression || 6;
            
            d.saveAs(file, pngOptions, true, Extension.LOWERCASE);
            return true;
        } catch (e) {
            $.writeln("保存为PNG失败: " + e.message);
            return false;
        }
    },
    
    saveAsJPEG: function(doc, filePath, quality) {
        try {
            var d = doc || Photoshop.doc;
            var file = new File(filePath);
            
            var jpegOptions = new JPEGSaveOptions();
            jpegOptions.quality = quality || 12;
            jpegOptions.formatOptions = FormatOptions.STANDARDBASELINE;
            jpegOptions.embedColorProfile = true;
            
            d.saveAs(file, jpegOptions, true, Extension.LOWERCASE);
            return true;
        } catch (e) {
            $.writeln("保存为JPEG失败: " + e.message);
            return false;
        }
    },
    
    saveForWeb: function(doc, filePath, config) {
        try {
            var d = doc || Photoshop.doc;
            var file = new File(filePath);
            
            var exportOptions = new ExportOptionsSaveForWeb();
            exportOptions.format = config && config.format || SaveDocumentType.JPEG;
            exportOptions.quality = config && config.quality || 80;
            
            d.exportDocument(file, ExportType.SAVEFORWEB, exportOptions);
            return true;
        } catch (e) {
            $.writeln("导出为Web格式失败: " + e.message);
            return false;
        }
    }
};
```

---

## 三、图层管理

### 3.1 图层创建与操作

```javascript
var LayerManager = {
    createLayer: function(name) {
        try {
            var doc = Photoshop.doc;
            var layer = doc.artLayers.add();
            layer.name = name || "Layer " + (doc.layers.length);
            return layer;
        } catch (e) {
            $.writeln("创建图层失败: " + e.message);
            return null;
        }
    },
    
    createTextLayer: function(text, config) {
        var defaults = {
            fontSize: 72,
            fontName: "Arial",
            color: {r: 0, g: 0, b: 0},
            position: {x: 0, y: 0}
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var doc = Photoshop.doc;
            var textLayer = doc.artLayers.add();
            textLayer.kind = LayerKind.TEXT;
            textLayer.name = cfg.name || "Text Layer";
            
            var textItem = textLayer.textItem;
            textItem.contents = text;
            textItem.fontSize = cfg.fontSize;
            textItem.font = cfg.fontName;
            
            var color = new SolidColor();
            color.rgb.red = cfg.color.r;
            color.rgb.green = cfg.color.g;
            color.rgb.blue = cfg.color.b;
            textItem.color = color;
            
            textItem.position = [cfg.position.x, cfg.position.y];
            
            return textLayer;
        } catch (e) {
            $.writeln("创建文本图层失败: " + e.message);
            return null;
        }
    },
    
    createAdjustmentLayer: function(type, config) {
        try {
            var doc = Photoshop.doc;
            
            var adjustmentLayer;
            switch (type) {
                case "BrightnessContrast":
                    adjustmentLayer = doc.layers.add("Brightness/Contrast");
                    break;
                case "Levels":
                    adjustmentLayer = doc.layers.add("Levels");
                    break;
                case "Curves":
                    adjustmentLayer = doc.layers.add("Curves");
                    break;
                case "HueSaturation":
                    adjustmentLayer = doc.layers.add("Hue/Saturation");
                    break;
                case "ColorBalance":
                    adjustmentLayer = doc.layers.add("Color Balance");
                    break;
                default:
                    adjustmentLayer = doc.layers.add(type);
            }
            
            if (config && config.name) {
                adjustmentLayer.name = config.name;
            }
            
            return adjustmentLayer;
        } catch (e) {
            $.writeln("创建调整图层失败: " + e.message);
            return null;
        }
    },
    
    getLayerByName: function(name) {
        var doc = Photoshop.doc;
        
        for (var i = 0; i < doc.layers.length; i++) {
            if (doc.layers[i].name === name) {
                return doc.layers[i];
            }
        }
        
        return null;
    },
    
    duplicateLayer: function(layer, name) {
        try {
            var duplicated = layer.duplicate();
            duplicated.name = name || layer.name + " copy";
            return duplicated;
        } catch (e) {
            $.writeln("复制图层失败: " + e.message);
            return null;
        }
    },
    
    deleteLayer: function(layer) {
        try {
            layer.remove();
            return true;
        } catch (e) {
            $.writeln("删除图层失败: " + e.message);
            return false;
        }
    },
    
    flattenImage: function(doc) {
        try {
            (doc || Photoshop.doc).flatten();
            return true;
        } catch (e) {
            $.writeln("拼合图像失败: " + e.message);
            return false;
        }
    }
};
```

### 3.2 图层样式

```javascript
var LayerStyles = {
    applyDropShadow: function(layer, config) {
        var defaults = {
            opacity: 75,
            angle: 120,
            distance: 5,
            size: 5,
            color: {r: 0, g: 0, b: 0}
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var color = new SolidColor();
            color.rgb.red = cfg.color.r;
            color.rgb.green = cfg.color.g;
            color.rgb.blue = cfg.color.b;
            
            layer.applyDropShadow(true, cfg.opacity, cfg.angle, cfg.distance, 0, cfg.size, color);
            return true;
        } catch (e) {
            $.writeln("应用投影失败: " + e.message);
            return false;
        }
    },
    
    applyOuterGlow: function(layer, config) {
        var defaults = {
            opacity: 75,
            size: 5,
            color: {r: 255, g: 255, b: 0}
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var color = new SolidColor();
            color.rgb.red = cfg.color.r;
            color.rgb.green = cfg.color.g;
            color.rgb.blue = cfg.color.b;
            
            layer.applyOuterGlow(true, cfg.opacity, cfg.size, color);
            return true;
        } catch (e) {
            $.writeln("应用外发光失败: " + e.message);
            return false;
        }
    },
    
    applyBevelEmboss: function(layer, config) {
        var defaults = {
            depth: 100,
            size: 5,
            angle: 120,
            altitude: 30
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            layer.applyBevelEmboss(true, BevelStyle.OUTERBEVEL, cfg.depth, cfg.size, 0, cfg.angle, cfg.altitude, 75, 75);
            return true;
        } catch (e) {
            $.writeln("应用斜面和浮雕失败: " + e.message);
            return false;
        }
    },
    
    applyColorOverlay: function(layer, color) {
        try {
            var fillColor = new SolidColor();
            fillColor.rgb.red = color.r;
            fillColor.rgb.green = color.g;
            fillColor.rgb.blue = color.b;
            
            layer.applyColorOverlay(true, fillColor);
            return true;
        } catch (e) {
            $.writeln("应用颜色叠加失败: " + e.message);
            return false;
        }
    }
};
```

---

## 四、图像调整

### 4.1 基本调整

```javascript
var ImageAdjustments = {
    brightnessContrast: function(doc, brightness, contrast) {
        try {
            (doc || Photoshop.doc).adjustBrightnessContrast(brightness, contrast);
            return true;
        } catch (e) {
            $.writeln("亮度对比度调整失败: " + e.message);
            return false;
        }
    },
    
    levels: function(doc, inputLevels) {
        try {
            (doc || Photoshop.doc).adjustLevels(inputLevels[0], inputLevels[1], inputLevels[2]);
            return true;
        } catch (e) {
            $.writeln("色阶调整失败: " + e.message);
            return false;
        }
    },
    
    curves: function(doc, curvePoints) {
        try {
            var curve = new Curve();
            for (var i = 0; i < curvePoints.length; i++) {
                curve.addPoint(curvePoints[i][0], curvePoints[i][1]);
            }
            
            (doc || Photoshop.doc).adjustCurves(curve);
            return true;
        } catch (e) {
            $.writeln("曲线调整失败: " + e.message);
            return false;
        }
    },
    
    hueSaturation: function(doc, hue, saturation, lightness) {
        try {
            (doc || Photoshop.doc).adjustHueSaturation(hue, saturation, lightness);
            return true;
        } catch (e) {
            $.writeln("色相饱和度调整失败: " + e.message);
            return false;
        }
    },
    
    autoLevels: function(doc) {
        try {
            (doc || Photoshop.doc).autoLevels();
            return true;
        } catch (e) {
            $.writeln("自动色阶失败: " + e.message);
            return false;
        }
    },
    
    autoContrast: function(doc) {
        try {
            (doc || Photoshop.doc).autoContrast();
            return true;
        } catch (e) {
            $.writeln("自动对比度失败: " + e.message);
            return false;
        }
    },
    
    autoColor: function(doc) {
        try {
            (doc || Photoshop.doc).autoColor();
            return true;
        } catch (e) {
            $.writeln("自动颜色失败: " + e.message);
            return false;
        }
    }
};
```

### 4.2 滤镜应用

```javascript
var Filters = {
    blur: function(doc, radius) {
        try {
            (doc || Photoshop.doc).filter(GaussianBlur, radius);
            return true;
        } catch (e) {
            $.writeln("高斯模糊失败: " + e.message);
            return false;
        }
    },
    
    sharpen: function(doc, amount) {
        try {
            (doc || Photoshop.doc).filter(UnsharpMask, amount, 1, 0);
            return true;
        } catch (e) {
            $.writeln("USM锐化失败: " + e.message);
            return false;
        }
    },
    
    noise: function(doc, amount) {
        try {
            (doc || Photoshop.doc).filter(AddNoise, amount, NoiseDistribution.UNIFORM, false);
            return true;
        } catch (e) {
            $.writeln("添加杂色失败: " + e.message);
            return false;
        }
    },
    
    lensFlare: function(doc, brightness) {
        try {
            (doc || Photoshop.doc).filter(LensFlare, brightness, FlareType.50300MMZOOM);
            return true;
        } catch (e) {
            $.writeln("镜头光晕失败: " + e.message);
            return false;
        }
    },
    
    oilPaint: function(doc, stylization, cleaniness) {
        try {
            (doc || Photoshop.doc).filter(OilPaint, stylization, cleaniness, 0.5, 0.5);
            return true;
        } catch (e) {
            $.writeln("油画失败: " + e.message);
            return false;
        }
    },
    
    posterEdges: function(doc, edgeThickness, edgeIntensity, posterization) {
        try {
            (doc || Photoshop.doc).filter(PosterEdges, edgeThickness, edgeIntensity, posterization);
            return true;
        } catch (e) {
            $.writeln("海报边缘失败: " + e.message);
            return false;
        }
    },
    
    emboss: function(doc, angle, height, amount) {
        try {
            (doc || Photoshop.doc).filter(Emboss, angle, height, amount);
            return true;
        } catch (e) {
            $.writeln("浮雕效果失败: " + e.message);
            return false;
        }
    }
};
```

---

## 五、选区与蒙版

### 5.1 选区操作

```javascript
var SelectionManager = {
    selectAll: function(doc) {
        try {
            (doc || Photoshop.doc).selection.selectAll();
            return true;
        } catch (e) {
            $.writeln("全选失败: " + e.message);
            return false;
        }
    },
    
    deselect: function(doc) {
        try {
            (doc || Photoshop.doc).selection.deselect();
            return true;
        } catch (e) {
            $.writeln("取消选择失败: " + e.message);
            return false;
        }
    },
    
    invertSelection: function(doc) {
        try {
            (doc || Photoshop.doc).selection.invert();
            return true;
        } catch (e) {
            $.writeln("反选失败: " + e.message);
            return false;
        }
    },
    
    selectRectangular: function(doc, top, left, bottom, right) {
        try {
            (doc || Photoshop.doc).selection.select([
                [left, top], [right, top], [right, bottom], [left, bottom]
            ], SelectionType.REPLACE, 0, false);
            return true;
        } catch (e) {
            $.writeln("矩形选择失败: " + e.message);
            return false;
        }
    },
    
    featherSelection: function(doc, pixels) {
        try {
            (doc || Photoshop.doc).selection.feather(pixels);
            return true;
        } catch (e) {
            $.writeln("羽化选区失败: " + e.message);
            return false;
        }
    },
    
    saveSelection: function(doc, name) {
        try {
            (doc || Photoshop.doc).selection.save(name);
            return true;
        } catch (e) {
            $.writeln("保存选区失败: " + e.message);
            return false;
        }
    },
    
    loadSelection: function(doc, name) {
        try {
            (doc || Photoshop.doc).selection.load(name);
            return true;
        } catch (e) {
            $.writeln("载入选区失败: " + e.message);
            return false;
        }
    }
};
```

### 5.2 蒙版操作

```javascript
var MaskManager = {
    addLayerMask: function(layer, revealAll) {
        try {
            layer.addLayerMask(revealAll);
            return layer.layerMask;
        } catch (e) {
            $.writeln("添加图层蒙版失败: " + e.message);
            return null;
        }
    },
    
    removeLayerMask: function(layer, apply) {
        try {
            layer.removeLayerMask(apply);
            return true;
        } catch (e) {
            $.writeln("移除图层蒙版失败: " + e.message);
            return false;
        }
    },
    
    invertLayerMask: function(layer) {
        try {
            layer.layerMask.invert();
            return true;
        } catch (e) {
            $.writeln("反相蒙版失败: " + e.message);
            return false;
        }
    },
    
    applyLayerMask: function(layer) {
        try {
            layer.applyLayerMask();
            return true;
        } catch (e) {
            $.writeln("应用图层蒙版失败: " + e.message);
            return false;
        }
    },
    
    createClippingMask: function(layer, baseLayer) {
        try {
            layer.createClippingMask(baseLayer);
            return true;
        } catch (e) {
            $.writeln("创建剪贴蒙版失败: " + e.message);
            return false;
        }
    }
};
```

---

## 六、路径与形状

### 6.1 路径操作

```javascript
var PathManager = {
    createPath: function(doc, name) {
        try {
            return (doc || Photoshop.doc).pathItems.add(name || "Path");
        } catch (e) {
            $.writeln("创建路径失败: " + e.message);
            return null;
        }
    },
    
    createRectanglePath: function(doc, top, left, bottom, right, name) {
        try {
            var d = doc || Photoshop.doc;
            var path = d.pathItems.rectangle(top, left, right - left, bottom - top);
            path.name = name || "Rectangle";
            return path;
        } catch (e) {
            $.writeln("创建矩形路径失败: " + e.message);
            return null;
        }
    },
    
    createCirclePath: function(doc, centerX, centerY, radius, name) {
        try {
            var d = doc || Photoshop.doc;
            var path = d.pathItems.ellipse(centerY - radius, centerX - radius, radius * 2, radius * 2);
            path.name = name || "Circle";
            return path;
        } catch (e) {
            $.writeln("创建圆形路径失败: " + e.message);
            return null;
        }
    },
    
    createPolygonPath: function(doc, centerX, centerY, radius, sides, name) {
        try {
            var d = doc || Photoshop.doc;
            var path = d.pathItems.polygon(centerX, centerY, radius, sides);
            path.name = name || "Polygon";
            return path;
        } catch (e) {
            $.writeln("创建多边形路径失败: " + e.message);
            return null;
        }
    },
    
    makeSelectionFromPath: function(path, feather) {
        try {
            path.makeSelection(feather || 0);
            return true;
        } catch (e) {
            $.writeln("路径转为选区失败: " + e.message);
            return false;
        }
    },
    
    fillPath: function(path, color) {
        try {
            var solidColor = new SolidColor();
            solidColor.rgb.red = color.r;
            solidColor.rgb.green = color.g;
            solidColor.rgb.blue = color.b;
            
            path.fillPath(solidColor);
            return true;
        } catch (e) {
            $.writeln("填充路径失败: " + e.message);
            return false;
        }
    },
    
    strokePath: function(path, color, width) {
        try {
            var solidColor = new SolidColor();
            solidColor.rgb.red = color.r;
            solidColor.rgb.green = color.g;
            solidColor.rgb.blue = color.b;
            
            path.strokePath(solidColor, width || 1);
            return true;
        } catch (e) {
            $.writeln("描边路径失败: " + e.message);
            return false;
        }
    }
};
```

---

## 七、批量处理

### 7.1 批量图像处理

```javascript
var BatchProcessor = {
    processFolder: function(inputFolder, outputFolder, actions) {
        var folder = new Folder(inputFolder);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            if (ext !== "jpg" && ext !== "jpeg" && ext !== "png") {
                continue;
            }
            
            var result = this._processFile(file, outputFolder, actions);
            results.push(result);
        }
        
        return results;
    },
    
    _processFile: function(file, outputFolder, actions) {
        try {
            var doc = Photoshop.app.open(file);
            
            for (var j = 0; j < actions.length; j++) {
                var action = actions[j];
                
                switch (action.type) {
                    case "resize":
                        doc.resizeImage(action.width, action.height, 72, ResampleMethod.BICUBICSHARPER);
                        break;
                    case "brightnessContrast":
                        doc.adjustBrightnessContrast(action.brightness, action.contrast);
                        break;
                    case "levels":
                        doc.adjustLevels(action.shadow, action.midtone, action.highlight);
                        break;
                    case "sharpen":
                        doc.filter(UnsharpMask, action.amount || 100, 1, 0);
                        break;
                    case "blur":
                        doc.filter(GaussianBlur, action.radius || 1);
                        break;
                }
            }
            
            var outputFile = new File(outputFolder + "/" + file.name);
            
            if (file.name.toLowerCase().endsWith(".png")) {
                var pngOptions = new PNGSaveOptions();
                doc.saveAs(outputFile, pngOptions, true, Extension.LOWERCASE);
            } else {
                var jpegOptions = new JPEGSaveOptions();
                jpegOptions.quality = 12;
                doc.saveAs(outputFile, jpegOptions, true, Extension.LOWERCASE);
            }
            
            doc.close(SaveOptions.DONOTSAVECHANGES);
            
            return { filename: file.name, success: true };
            
        } catch (e) {
            return { filename: file.name, success: false, error: e.message };
        }
    },
    
    batchResize: function(inputFolder, outputFolder, width, height) {
        var actions = [{ type: "resize", width: width, height: height }];
        return this.processFolder(inputFolder, outputFolder, actions);
    },
    
    batchSharpen: function(inputFolder, outputFolder, amount) {
        var actions = [{ type: "sharpen", amount: amount || 100 }];
        return this.processFolder(inputFolder, outputFolder, actions);
    },
    
    batchWatermark: function(inputFolder, outputFolder, watermarkText) {
        var folder = new Folder(inputFolder);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            try {
                var doc = Photoshop.app.open(file);
                
                var textLayer = doc.artLayers.add();
                textLayer.kind = LayerKind.TEXT;
                
                var textItem = textLayer.textItem;
                textItem.contents = watermarkText;
                textItem.fontSize = 24;
                textItem.font = "Arial";
                
                var color = new SolidColor();
                color.rgb.red = 255;
                color.rgb.green = 255;
                color.rgb.blue = 255;
                textItem.color = color;
                
                textItem.position = [doc.width - 100, doc.height - 30];
                textLayer.opacity = 50;
                
                var outputFile = new File(outputFolder + "/" + file.name);
                var jpegOptions = new JPEGSaveOptions();
                jpegOptions.quality = 12;
                doc.saveAs(outputFile, jpegOptions, true, Extension.LOWERCASE);
                
                doc.close(SaveOptions.DONOTSAVECHANGES);
                
                results.push({ filename: file.name, success: true });
                
            } catch (e) {
                results.push({ filename: file.name, success: false, error: e.message });
            }
        }
        
        return results;
    }
};
```

### 7.2 自动化动作

```javascript
var ActionManager = {
    playAction: function(actionName, actionSetName) {
        try {
            Photoshop.app.doAction(actionName, actionSetName);
            return true;
        } catch (e) {
            $.writeln("播放动作失败: " + e.message);
            return false;
        }
    },
    
    batchPlayAction: function(folderPath, actionName, actionSetName, outputFolder) {
        var folder = new Folder(folderPath);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            try {
                var doc = Photoshop.app.open(file);
                Photoshop.app.doAction(actionName, actionSetName);
                
                var outputFile = new File(outputFolder + "/" + file.name);
                doc.saveAs(outputFile);
                
                doc.close(SaveOptions.DONOTSAVECHANGES);
                
                results.push({ filename: file.name, success: true });
                
            } catch (e) {
                results.push({ filename: file.name, success: false, error: e.message });
            }
        }
        
        return results;
    },
    
    getActionSets: function() {
        try {
            return Photoshop.app.actionSets;
        } catch (e) {
            $.writeln("获取动作集失败: " + e.message);
            return [];
        }
    },
    
    getActionsInSet: function(actionSetName) {
        try {
            var actionSet = Photoshop.app.actionSets.getByName(actionSetName);
            return actionSet.actions;
        } catch (e) {
            $.writeln("获取动作失败: " + e.message);
            return [];
        }
    }
};
```

---

## 八、与其他 Adobe 应用集成

### 8.1 动态链接

```javascript
var DynamicLinkManager = {
    editInCameraRaw: function(doc) {
        try {
            (doc || Photoshop.doc).openInCameraRaw();
            return true;
        } catch (e) {
            $.writeln("在Camera Raw中编辑失败: " + e.message);
            return false;
        }
    },
    
    importFromIllustrator: function(aiPath) {
        try {
            var file = new File(aiPath);
            return Photoshop.app.open(file);
        } catch (e) {
            $.writeln("从Illustrator导入失败: " + e.message);
            return null;
        }
    },
    
    exportToIllustrator: function(doc, outputPath) {
        try {
            var d = doc || Photoshop.doc;
            var file = new File(outputPath);
            
            var exportOptions = new ExportOptionsIllustrator();
            d.exportDocument(file, ExportType.ILLUSTRATOR, exportOptions);
            
            return true;
        } catch (e) {
            $.writeln("导出到Illustrator失败: " + e.message);
            return false;
        }
    },
    
    sendToPremiere: function(doc, outputPath) {
        try {
            var d = doc || Photoshop.doc;
            var file = new File(outputPath);
            
            var exportOptions = new ExportOptionsQuickTime();
            d.exportDocument(file, ExportType.QUICKTIME, exportOptions);
            
            return true;
        } catch (e) {
            $.writeln("发送到Premiere失败: " + e.message);
            return false;
        }
    },
    
    importFromPremiere: function(prprojPath) {
        try {
            var file = new File(prprojPath);
            return Photoshop.app.open(file);
        } catch (e) {
            $.writeln("从Premiere导入失败: " + e.message);
            return null;
        }
    }
};
```

---

## 九、企业级部署

### 9.1 环境配置

```javascript
var PSEnvironment = {
    getSystemInfo: function() {
        return {
            version: Photoshop.app.version,
            platform: Photoshop.app.platform,
            ram: Photoshop.app.systemInfo.ram,
            gpu: Photoshop.app.systemInfo.gpu
        };
    },
    
    setScratchDisks: function(disks) {
        try {
            Photoshop.app.scratchDisks = disks;
            return true;
        } catch (e) {
            $.writeln("设置暂存盘失败: " + e.message);
            return false;
        }
    },
    
    clearCache: function() {
        try {
            Photoshop.app.clearCache();
            return true;
        } catch (e) {
            $.writeln("清除缓存失败: " + e.message);
            return false;
        }
    },
    
    exportPreferences: function(outputPath) {
        try {
            Photoshop.app.preferences.exportPreferences(File(outputPath));
            return true;
        } catch (e) {
            $.writeln("导出首选项失败: " + e.message);
            return false;
        }
    },
    
    importPreferences: function(inputPath) {
        try {
            Photoshop.app.preferences.importPreferences(File(inputPath));
            return true;
        } catch (e) {
            $.writeln("导入首选项失败: " + e.message);
            return false;
        }
    }
};
```

### 9.2 脚本部署

```javascript
var ScriptDeployer = {
    installScript: function(scriptPath, menuName) {
        try {
            var scriptFile = new File(scriptPath);
            Photoshop.app.scriptMenu.installScript(scriptFile, menuName);
            return true;
        } catch (e) {
            $.writeln("安装脚本失败: " + e.message);
            return false;
        }
    },
    
    uninstallScript: function(menuName) {
        try {
            Photoshop.app.scriptMenu.uninstallScript(menuName);
            return true;
        } catch (e) {
            $.writeln("卸载脚本失败: " + e.message);
            return false;
        }
    },
    
    runScript: function(scriptPath) {
        try {
            var scriptFile = new File(scriptPath);
            Photoshop.app.doScript(scriptFile);
            return true;
        } catch (e) {
            $.writeln("运行脚本失败: " + e.message);
            return false;
        }
    }
};
```

---

## 十、性能优化

### 10.1 缓存管理

```javascript
var CacheManager = {
    clearUndoHistory: function(doc) {
        try {
            (doc || Photoshop.doc).purge(PurgeTarget.UNDOHISTORY);
            return true;
        } catch (e) {
            $.writeln("清除历史记录失败: " + e.message);
            return false;
        }
    },
    
    purgeCache: function() {
        try {
            Photoshop.app.purge(PurgeTarget.CACHE);
            return true;
        } catch (e) {
            $.writeln("清除缓存失败: " + e.message);
            return false;
        }
    },
    
    purgeAll: function() {
        try {
            Photoshop.app.purge(PurgeTarget.ALL);
            return true;
        } catch (e) {
            $.writeln("清除所有失败: " + e.message);
            return false;
        }
    }
};
```

### 10.2 性能监控

```javascript
var PerformanceMonitor = {
    getPerformanceMetrics: function() {
        return {
            memoryUsage: Photoshop.app.systemInfo.memoryUsage,
            gpuUsage: Photoshop.app.systemInfo.gpuUsage,
            openDocuments: Photoshop.app.documents.length
        };
    },
    
    getPerformanceReport: function() {
        var metrics = this.getPerformanceMetrics();
        var recommendations = [];
        
        if (metrics.memoryUsage > 85) {
            recommendations.push("内存使用率过高，建议清理缓存");
        }
        
        if (metrics.openDocuments > 10) {
            recommendations.push("打开文档过多，建议关闭不需要的文档");
        }
        
        return { metrics: metrics, recommendations: recommendations };
    }
};
```

---

*本指南涵盖 Photoshop 企业级集成的完整知识体系，包括 JavaScript API、文档管理、图层系统、图像调整、滤镜应用、选区蒙版、路径形状、批量处理、动态链接等核心模块*
