# Adobe Illustrator 矢量图形与MG动画指南

---

## 一、Illustrator 架构与核心组件

### 1.1 对象模型层次

```javascript
// Illustrator DOM 层次结构
// Application
//   └── Document
//       ├── Layer
//       │   ├── PageItem
//       │   │   ├── PathItem
//       │   │   ├── GroupItem
//       │   │   ├── CompoundPathItem
//       │   │   └── TextFrame
//       ├── Swatch
//       ├── Brush
//       ├── Symbol
//       └── Gradient
```

### 1.2 核心对象

| 对象 | 描述 | 关键方法 |
|------|------|---------|
| **Application** | Illustrator 应用程序 | open(), newDocument(), quit() |
| **Document** | 当前文档 | save(), saveAs(), artboards |
| **Layer** | 图层 | visible, locked, opacity |
| **PathItem** | 路径对象 | fillColor, strokeColor, width |
| **GroupItem** | 组合对象 | pageItems, addPageItem() |
| **CompoundPathItem** | 复合路径 | pathItems, holes |
| **TextFrame** | 文本框 | contents, fontSize, fontName |
| **Swatch** | 色板 | color, name, type |
| **Symbol** | 符号 | instances, registrationPoint |
| **Gradient** | 渐变 | colorStops, type |
| **Artboard** | 画板 | name, bounds, active |

### 1.3 JavaScript API 初始化

```javascript
var Illustrator = {
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
            units: "points",
            bleedTop: 0,
            bleedLeft: 0,
            bleedBottom: 0,
            bleedRight: 0,
            name: "Untitled_" + new Date().getTime()
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var docProps = new DocumentPreset();
            docProps.width = cfg.width;
            docProps.height = cfg.height;
            docProps.units = cfg.units;
            docProps.bleedTop = cfg.bleedTop;
            docProps.bleedLeft = cfg.bleedLeft;
            docProps.bleedBottom = cfg.bleedBottom;
            docProps.bleedRight = cfg.bleedRight;
            
            this.doc = this.app.documents.add(docProps);
            this.doc.name = cfg.name;
            
            return this.doc;
        } catch (e) {
            $.writeln("创建文档失败: " + e.message);
            return null;
        }
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
            units: d.units.toString(),
            layerCount: d.layers.length,
            artboardCount: d.artboards.length,
            pageItemCount: d.pageItems.length,
            version: this.app.version
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
            units: "points",
            name: "Untitled_" + new Date().getTime()
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var docProps = new DocumentPreset();
            docProps.width = cfg.width;
            docProps.height = cfg.height;
            docProps.units = cfg.units;
            
            var doc = Illustrator.app.documents.add(docProps);
            doc.name = cfg.name;
            
            return doc;
        } catch (e) {
            $.writeln("创建文档失败: " + e.message);
            return null;
        }
    },
    
    createAnimationDocument: function(width, height, fps, duration) {
        try {
            var docProps = new DocumentPreset();
            docProps.width = width;
            docProps.height = height;
            docProps.units = "points";
            
            var doc = Illustrator.app.documents.add(docProps);
            doc.name = "Animation_" + new Date().getTime();
            
            // 设置时间轴
            var timeline = doc.timeline;
            timeline.rulerOrigin = 0;
            timeline.fps = fps || 24;
            timeline.duration = duration || 10;
            
            return doc;
        } catch (e) {
            $.writeln("创建动画文档失败: " + e.message);
            return null;
        }
    },
    
    openDocument: function(filePath) {
        try {
            var file = new File(filePath);
            return Illustrator.app.open(file);
        } catch (e) {
            $.writeln("打开文档失败: " + e.message);
            return null;
        }
    },
    
    closeDocument: function(doc) {
        try {
            (doc || Illustrator.doc).close(SaveOptions.DONOTSAVECHANGES);
            return true;
        } catch (e) {
            $.writeln("关闭文档失败: " + e.message);
            return false;
        }
    },
    
    closeAllDocuments: function() {
        try {
            Illustrator.app.documents.closeAll(SaveOptions.DONOTSAVECHANGES);
            return true;
        } catch (e) {
            $.writeln("关闭所有文档失败: " + e.message);
            return false;
        }
    }
};
```

### 2.2 文档保存

```javascript
var DocumentSaver = {
    save: function(doc, filePath) {
        try {
            var d = doc || Illustrator.doc;
            
            if (filePath) {
                var file = new File(filePath);
                d.saveAs(file);
            } else {
                d.save();
            }
            
            return true;
        } catch (e) {
            $.writeln("保存文档失败: " + e.message);
            return false;
        }
    },
    
    saveAsAI: function(doc, filePath) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(filePath);
            
            var options = new IllustratorSaveOptions();
            options.embedFonts = true;
            options.embedLinkedFiles = true;
            options.preserveEditability = true;
            
            d.saveAs(file, options);
            return true;
        } catch (e) {
            $.writeln("保存为AI失败: " + e.message);
            return false;
        }
    },
    
    saveAsPDF: function(doc, filePath, options) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(filePath);
            
            var pdfOptions = new PDFSaveOptions();
            pdfOptions.compatibility = PDFCompatibility.ACROBAT7;
            pdfOptions.preserveEditability = true;
            pdfOptions.embedFonts = true;
            
            if (options) {
                pdfOptions.viewAfterSaving = options.viewAfterSaving || false;
                pdfOptions.optimizeForWeb = options.optimizeForWeb || false;
            }
            
            d.saveAs(file, pdfOptions);
            return true;
        } catch (e) {
            $.writeln("保存为PDF失败: " + e.message);
            return false;
        }
    },
    
    saveAsSVG: function(doc, filePath, options) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(filePath);
            
            var svgOptions = new SVGSaveOptions();
            svgOptions.embedFonts = true;
            svgOptions.encoding = SVGEncoding.UTF8;
            svgOptions.preserveEditability = true;
            
            if (options) {
                svgOptions.responsive = options.responsive || false;
                svgOptions.includeSliceMarks = options.includeSliceMarks || false;
            }
            
            d.saveAs(file, svgOptions);
            return true;
        } catch (e) {
            $.writeln("保存为SVG失败: " + e.message);
            return false;
        }
    },
    
    saveAsPNG: function(doc, filePath, resolution) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(filePath);
            
            var pngOptions = new PNGSaveOptions();
            pngOptions.resolution = resolution || 72;
            pngOptions.transparency = true;
            pngOptions.antiAliasing = true;
            
            d.saveAs(file, pngOptions);
            return true;
        } catch (e) {
            $.writeln("保存为PNG失败: " + e.message);
            return false;
        }
    },
    
    saveAsJPEG: function(doc, filePath, quality) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(filePath);
            
            var jpegOptions = new JPEGSaveOptions();
            jpegOptions.quality = quality || 12;
            jpegOptions.embedColorProfile = true;
            
            d.saveAs(file, jpegOptions);
            return true;
        } catch (e) {
            $.writeln("保存为JPEG失败: " + e.message);
            return false;
        }
    },
    
    exportForWeb: function(doc, filePath, config) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(filePath);
            
            var exportOptions = new ExportOptionsSaveForWeb();
            exportOptions.format = config && config.format || SaveDocumentType.PNG;
            exportOptions.quality = config && config.quality || 80;
            exportOptions.optimized = true;
            
            d.exportFile(file, ExportType.SAVEFORWEB, exportOptions);
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

### 3.1 图层操作

```javascript
var LayerManager = {
    createLayer: function(name) {
        try {
            var doc = Illustrator.doc;
            var layer = doc.layers.add();
            layer.name = name || "Layer " + (doc.layers.length);
            return layer;
        } catch (e) {
            $.writeln("创建图层失败: " + e.message);
            return null;
        }
    },
    
    createLayerStructure: function() {
        var doc = Illustrator.doc;
        
        var layers = {
            backgrounds: this.createLayer("Backgrounds"),
            elements: this.createLayer("Elements"),
            text: this.createLayer("Text"),
            effects: this.createLayer("Effects"),
            guides: this.createLayer("Guides")
        };
        
        // 设置引导层不可打印
        if (layers.guides) {
            layers.guides.printable = false;
        }
        
        return layers;
    },
    
    getLayerByName: function(name) {
        var doc = Illustrator.doc;
        
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
    
    setLayerVisible: function(layer, visible) {
        try {
            layer.visible = visible;
            return true;
        } catch (e) {
            $.writeln("设置图层可见性失败: " + e.message);
            return false;
        }
    },
    
    setLayerLocked: function(layer, locked) {
        try {
            layer.locked = locked;
            return true;
        } catch (e) {
            $.writeln("设置图层锁定失败: " + e.message);
            return false;
        }
    },
    
    setLayerOpacity: function(layer, opacity) {
        try {
            layer.opacity = opacity;
            return true;
        } catch (e) {
            $.writeln("设置图层透明度失败: " + e.message);
            return false;
        }
    },
    
    movePageItemToLayer: function(pageItem, layer) {
        try {
            pageItem.moveToLayer(layer);
            return true;
        } catch (e) {
            $.writeln("移动对象到图层失败: " + e.message);
            return false;
        }
    },
    
    mergeLayers: function(layers) {
        try {
            var doc = Illustrator.doc;
            doc.activeLayer = layers[0];
            
            for (var i = 1; i < layers.length; i++) {
                layers[i].merge();
            }
            
            return doc.activeLayer;
        } catch (e) {
            $.writeln("合并图层失败: " + e.message);
            return null;
        }
    },
    
    getLayerInfo: function(layer) {
        return {
            name: layer.name,
            visible: layer.visible,
            locked: layer.locked,
            opacity: layer.opacity,
            printable: layer.printable,
            pageItemCount: layer.pageItems.length,
            index: layer.index
        };
    }
};
```

---

## 四、路径绘制

### 4.1 基本形状

```javascript
var ShapeDrawer = {
    drawRectangle: function(doc, x, y, width, height, config) {
        var defaults = {
            fillColor: null,
            strokeColor: null,
            strokeWidth: 1,
            cornerRadius: 0,
            name: "Rectangle"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            var rect = d.pathItems.rectangle(y, x, width, height);
            rect.name = cfg.name;
            
            if (cfg.fillColor) {
                var fill = new RGBColor();
                fill.red = cfg.fillColor.r;
                fill.green = cfg.fillColor.g;
                fill.blue = cfg.fillColor.b;
                rect.filled = true;
                rect.fillColor = fill;
            }
            
            if (cfg.strokeColor) {
                var stroke = new RGBColor();
                stroke.red = cfg.strokeColor.r;
                stroke.green = cfg.strokeColor.g;
                stroke.blue = cfg.strokeColor.b;
                rect.stroked = true;
                rect.strokeColor = stroke;
                rect.strokeWidth = cfg.strokeWidth;
            }
            
            if (cfg.cornerRadius > 0) {
                rect.cornerRadius = cfg.cornerRadius;
            }
            
            return rect;
        } catch (e) {
            $.writeln("绘制矩形失败: " + e.message);
            return null;
        }
    },
    
    drawCircle: function(doc, x, y, radius, config) {
        var defaults = {
            fillColor: null,
            strokeColor: null,
            strokeWidth: 1,
            name: "Circle"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            var circle = d.pathItems.ellipse(y - radius, x - radius, radius * 2, radius * 2);
            circle.name = cfg.name;
            
            if (cfg.fillColor) {
                var fill = new RGBColor();
                fill.red = cfg.fillColor.r;
                fill.green = cfg.fillColor.g;
                fill.blue = cfg.fillColor.b;
                circle.filled = true;
                circle.fillColor = fill;
            }
            
            if (cfg.strokeColor) {
                var stroke = new RGBColor();
                stroke.red = cfg.strokeColor.r;
                stroke.green = cfg.strokeColor.g;
                stroke.blue = cfg.strokeColor.b;
                circle.stroked = true;
                circle.strokeColor = stroke;
                circle.strokeWidth = cfg.strokeWidth;
            }
            
            return circle;
        } catch (e) {
            $.writeln("绘制圆形失败: " + e.message);
            return null;
        }
    },
    
    drawPolygon: function(doc, x, y, radius, sides, config) {
        var defaults = {
            fillColor: null,
            strokeColor: null,
            strokeWidth: 1,
            name: "Polygon"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            var polygon = d.pathItems.polygon(y, x, radius, sides);
            polygon.name = cfg.name;
            
            if (cfg.fillColor) {
                var fill = new RGBColor();
                fill.red = cfg.fillColor.r;
                fill.green = cfg.fillColor.g;
                fill.blue = cfg.fillColor.b;
                polygon.filled = true;
                polygon.fillColor = fill;
            }
            
            if (cfg.strokeColor) {
                var stroke = new RGBColor();
                stroke.red = cfg.strokeColor.r;
                stroke.green = cfg.strokeColor.g;
                stroke.blue = cfg.strokeColor.b;
                polygon.stroked = true;
                polygon.strokeColor = stroke;
                polygon.strokeWidth = cfg.strokeWidth;
            }
            
            return polygon;
        } catch (e) {
            $.writeln("绘制多边形失败: " + e.message);
            return null;
        }
    },
    
    drawLine: function(doc, x1, y1, x2, y2, config) {
        var defaults = {
            strokeColor: {r: 0, g: 0, b: 0},
            strokeWidth: 1,
            name: "Line"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            
            var line = d.pathItems.add("Line");
            line.name = cfg.name;
            
            var points = line.pathPoints;
            var startPoint = points.add();
            startPoint.anchor = [x1, y1];
            startPoint.leftDirection = [x1, y1];
            startPoint.rightDirection = [x1, y1];
            
            var endPoint = points.add();
            endPoint.anchor = [x2, y2];
            endPoint.leftDirection = [x2, y2];
            endPoint.rightDirection = [x2, y2];
            
            var stroke = new RGBColor();
            stroke.red = cfg.strokeColor.r;
            stroke.green = cfg.strokeColor.g;
            stroke.blue = cfg.strokeColor.b;
            
            line.stroked = true;
            line.strokeColor = stroke;
            line.strokeWidth = cfg.strokeWidth;
            
            return line;
        } catch (e) {
            $.writeln("绘制线条失败: " + e.message);
            return null;
        }
    }
};
```

### 4.2 自定义路径

```javascript
var PathCreator = {
    createPath: function(doc, points, config) {
        var defaults = {
            fillColor: null,
            strokeColor: null,
            strokeWidth: 1,
            closed: true,
            name: "Path"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            
            var path = d.pathItems.add(cfg.name);
            var pathPoints = path.pathPoints;
            
            for (var i = 0; i < points.length; i++) {
                var point = points[i];
                var pathPoint = pathPoints.add();
                
                pathPoint.anchor = [point.x, point.y];
                
                if (point.leftDirection) {
                    pathPoint.leftDirection = point.leftDirection;
                } else {
                    pathPoint.leftDirection = [point.x, point.y];
                }
                
                if (point.rightDirection) {
                    pathPoint.rightDirection = point.rightDirection;
                } else {
                    pathPoint.rightDirection = [point.x, point.y];
                }
            }
            
            path.closed = cfg.closed;
            
            if (cfg.fillColor) {
                var fill = new RGBColor();
                fill.red = cfg.fillColor.r;
                fill.green = cfg.fillColor.g;
                fill.blue = cfg.fillColor.b;
                path.filled = true;
                path.fillColor = fill;
            }
            
            if (cfg.strokeColor) {
                var stroke = new RGBColor();
                stroke.red = cfg.strokeColor.r;
                stroke.green = cfg.strokeColor.g;
                stroke.blue = cfg.strokeColor.b;
                path.stroked = true;
                path.strokeColor = stroke;
                path.strokeWidth = cfg.strokeWidth;
            }
            
            return path;
        } catch (e) {
            $.writeln("创建路径失败: " + e.message);
            return null;
        }
    },
    
    createCompoundPath: function(doc, paths, config) {
        var defaults = {
            fillColor: null,
            strokeColor: null,
            strokeWidth: 1,
            name: "Compound Path"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            
            var compoundPath = d.compoundPathItems.add(cfg.name);
            
            for (var i = 0; i < paths.length; i++) {
                paths[i].moveToEnd(compoundPath);
            }
            
            if (cfg.fillColor) {
                var fill = new RGBColor();
                fill.red = cfg.fillColor.r;
                fill.green = cfg.fillColor.g;
                fill.blue = cfg.fillColor.b;
                compoundPath.filled = true;
                compoundPath.fillColor = fill;
            }
            
            if (cfg.strokeColor) {
                var stroke = new RGBColor();
                stroke.red = cfg.strokeColor.r;
                stroke.green = cfg.strokeColor.g;
                stroke.blue = cfg.strokeColor.b;
                compoundPath.stroked = true;
                compoundPath.strokeColor = stroke;
                compoundPath.strokeWidth = cfg.strokeWidth;
            }
            
            return compoundPath;
        } catch (e) {
            $.writeln("创建复合路径失败: " + e.message);
            return null;
        }
    }
};
```

---

## 五、文本处理

### 5.1 文本框操作

```javascript
var TextManager = {
    createTextFrame: function(doc, x, y, width, height, config) {
        var defaults = {
            contents: "",
            fontSize: 12,
            fontName: "Arial",
            fillColor: {r: 0, g: 0, b: 0},
            alignment: ParagraphAlignment.LEFT,
            name: "Text Frame"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            
            var textFrame = d.textFrames.add();
            textFrame.name = cfg.name;
            
            textFrame.contents = cfg.contents;
            
            var textRange = textFrame.textRange;
            textRange.characterAttributes.size = cfg.fontSize;
            textRange.characterAttributes.textFont = app.textFonts.getByName(cfg.fontName);
            
            var fill = new RGBColor();
            fill.red = cfg.fillColor.r;
            fill.green = cfg.fillColor.g;
            fill.blue = cfg.fillColor.b;
            textRange.characterAttributes.fillColor = fill;
            
            textFrame.paragraphAttributes.justification = cfg.alignment;
            
            textFrame.position = [x, y];
            textFrame.width = width;
            textFrame.height = height;
            
            return textFrame;
        } catch (e) {
            $.writeln("创建文本框失败: " + e.message);
            return null;
        }
    },
    
    createPointText: function(doc, x, y, config) {
        var defaults = {
            contents: "",
            fontSize: 12,
            fontName: "Arial",
            fillColor: {r: 0, g: 0, b: 0},
            name: "Point Text"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var d = doc || Illustrator.doc;
            
            var textFrame = d.textFrames.add();
            textFrame.name = cfg.name;
            textFrame.kind = TextType.POINTTEXT;
            
            textFrame.contents = cfg.contents;
            
            var textRange = textFrame.textRange;
            textRange.characterAttributes.size = cfg.fontSize;
            textRange.characterAttributes.textFont = app.textFonts.getByName(cfg.fontName);
            
            var fill = new RGBColor();
            fill.red = cfg.fillColor.r;
            fill.green = cfg.fillColor.g;
            fill.blue = cfg.fillColor.b;
            textRange.characterAttributes.fillColor = fill;
            
            textFrame.position = [x, y];
            
            return textFrame;
        } catch (e) {
            $.writeln("创建点文本失败: " + e.message);
            return null;
        }
    },
    
    setTextContents: function(textFrame, contents) {
        try {
            textFrame.contents = contents;
            return true;
        } catch (e) {
            $.writeln("设置文本内容失败: " + e.message);
            return false;
        }
    },
    
    setTextSize: function(textFrame, size) {
        try {
            textFrame.textRange.characterAttributes.size = size;
            return true;
        } catch (e) {
            $.writeln("设置文本大小失败: " + e.message);
            return false;
        }
    },
    
    setTextFont: function(textFrame, fontName) {
        try {
            textFrame.textRange.characterAttributes.textFont = app.textFonts.getByName(fontName);
            return true;
        } catch (e) {
            $.writeln("设置文本字体失败: " + e.message);
            return false;
        }
    },
    
    convertTextToOutline: function(textFrame) {
        try {
            return textFrame.createOutline();
        } catch (e) {
            $.writeln("转换文本为轮廓失败: " + e.message);
            return null;
        }
    }
};
```

---

## 六、渐变与颜色

### 6.1 渐变操作

```javascript
var GradientManager = {
    createLinearGradient: function(stops) {
        try {
            var gradient = new Gradient();
            gradient.type = GradientType.LINEAR;
            
            for (var i = 0; i < stops.length; i++) {
                var stop = stops[i];
                var colorStop = gradient.gradientStops.add();
                
                colorStop.position = stop.position;
                
                var color = new RGBColor();
                color.red = stop.r;
                color.green = stop.g;
                color.blue = stop.b;
                colorStop.color = color;
            }
            
            return gradient;
        } catch (e) {
            $.writeln("创建线性渐变失败: " + e.message);
            return null;
        }
    },
    
    createRadialGradient: function(stops) {
        try {
            var gradient = new Gradient();
            gradient.type = GradientType.RADIAL;
            
            for (var i = 0; i < stops.length; i++) {
                var stop = stops[i];
                var colorStop = gradient.gradientStops.add();
                
                colorStop.position = stop.position;
                
                var color = new RGBColor();
                color.red = stop.r;
                color.green = stop.g;
                color.blue = stop.b;
                colorStop.color = color;
            }
            
            return gradient;
        } catch (e) {
            $.writeln("创建径向渐变失败: " + e.message);
            return null;
        }
    },
    
    applyGradientToPath: function(path, gradient) {
        try {
            path.filled = true;
            path.fillColor = gradient;
            return true;
        } catch (e) {
            $.writeln("应用渐变到路径失败: " + e.message);
            return false;
        }
    }
};
```

### 6.2 色板管理

```javascript
var SwatchManager = {
    createRGBSwatch: function(name, color) {
        try {
            var doc = Illustrator.doc;
            
            var rgbColor = new RGBColor();
            rgbColor.red = color.r;
            rgbColor.green = color.g;
            rgbColor.blue = color.b;
            
            var swatch = doc.swatches.add();
            swatch.name = name;
            swatch.colorType = ColorModel.RGB;
            swatch.color = rgbColor;
            
            return swatch;
        } catch (e) {
            $.writeln("创建RGB色板失败: " + e.message);
            return null;
        }
    },
    
    createCMYKSwatch: function(name, color) {
        try {
            var doc = Illustrator.doc;
            
            var cmykColor = new CMYKColor();
            cmykColor.cyan = color.c;
            cmykColor.magenta = color.m;
            cmykColor.yellow = color.y;
            cmykColor.black = color.k;
            
            var swatch = doc.swatches.add();
            swatch.name = name;
            swatch.colorType = ColorModel.CMYK;
            swatch.color = cmykColor;
            
            return swatch;
        } catch (e) {
            $.writeln("创建CMYK色板失败: " + e.message);
            return null;
        }
    },
    
    getSwatchByName: function(name) {
        var doc = Illustrator.doc;
        
        for (var i = 0; i < doc.swatches.length; i++) {
            if (doc.swatches[i].name === name) {
                return doc.swatches[i];
            }
        }
        
        return null;
    },
    
    createColorPalette: function(name, colors) {
        var swatches = [];
        
        for (var i = 0; i < colors.length; i++) {
            var colorName = name + "_" + (i + 1);
            var swatch = this.createRGBSwatch(colorName, colors[i]);
            if (swatch) {
                swatches.push(swatch);
            }
        }
        
        return swatches;
    }
};
```

---

## 七、符号管理

### 7.1 符号操作

```javascript
var SymbolManager = {
    createSymbol: function(doc, pageItem, name) {
        try {
            var d = doc || Illustrator.doc;
            
            var symbol = d.symbols.add();
            symbol.name = name || "Symbol " + (d.symbols.length);
            
            pageItem.moveToEnd(symbol);
            
            return symbol;
        } catch (e) {
            $.writeln("创建符号失败: " + e.message);
            return null;
        }
    },
    
    placeSymbolInstance: function(doc, symbol, x, y) {
        try {
            var d = doc || Illustrator.doc;
            
            var instance = d.symbolItems.add(symbol);
            instance.position = [x, y];
            
            return instance;
        } catch (e) {
            $.writeln("放置符号实例失败: " + e.message);
            return null;
        }
    },
    
    getSymbolByName: function(name) {
        var doc = Illustrator.doc;
        
        for (var i = 0; i < doc.symbols.length; i++) {
            if (doc.symbols[i].name === name) {
                return doc.symbols[i];
            }
        }
        
        return null;
    },
    
    batchPlaceSymbolInstances: function(doc, symbol, positions) {
        var instances = [];
        
        for (var i = 0; i < positions.length; i++) {
            var pos = positions[i];
            var instance = this.placeSymbolInstance(doc, symbol, pos.x, pos.y);
            if (instance) {
                instances.push(instance);
            }
        }
        
        return instances;
    }
};
```

---

## 八、MG动画基础

### 8.1 时间轴操作

```javascript
var TimelineManager = {
    getTimeline: function(doc) {
        var d = doc || Illustrator.doc;
        return d.timeline;
    },
    
    setFps: function(doc, fps) {
        try {
            var timeline = this.getTimeline(doc);
            timeline.fps = fps;
            return true;
        } catch (e) {
            $.writeln("设置帧率失败: " + e.message);
            return false;
        }
    },
    
    setDuration: function(doc, duration) {
        try {
            var timeline = this.getTimeline(doc);
            timeline.duration = duration;
            return true;
        } catch (e) {
            $.writeln("设置时长失败: " + e.message);
            return false;
        }
    },
    
    playAnimation: function(doc) {
        try {
            var timeline = this.getTimeline(doc);
            timeline.play();
            return true;
        } catch (e) {
            $.writeln("播放动画失败: " + e.message);
            return false;
        }
    },
    
    stopAnimation: function(doc) {
        try {
            var timeline = this.getTimeline(doc);
            timeline.stop();
            return true;
        } catch (e) {
            $.writeln("停止动画失败: " + e.message);
            return false;
        }
    },
    
    addKeyframe: function(pageItem, property, frame, value) {
        try {
            var keyframe = pageItem.addKeyframe(property, frame);
            keyframe.setValue(value);
            return keyframe;
        } catch (e) {
            $.writeln("添加关键帧失败: " + e.message);
            return null;
        }
    },
    
    addPositionKeyframes: function(pageItem, startFrame, endFrame, startPos, endPos) {
        try {
            pageItem.addKeyframe("position", startFrame).setValue(startPos);
            pageItem.addKeyframe("position", endFrame).setValue(endPos);
            return true;
        } catch (e) {
            $.writeln("添加位置关键帧失败: " + e.message);
            return false;
        }
    },
    
    addScaleKeyframes: function(pageItem, startFrame, endFrame, startScale, endScale) {
        try {
            pageItem.addKeyframe("scale", startFrame).setValue(startScale);
            pageItem.addKeyframe("scale", endFrame).setValue(endScale);
            return true;
        } catch (e) {
            $.writeln("添加缩放关键帧失败: " + e.message);
            return false;
        }
    },
    
    addRotationKeyframes: function(pageItem, startFrame, endFrame, startAngle, endAngle) {
        try {
            pageItem.addKeyframe("rotation", startFrame).setValue(startAngle);
            pageItem.addKeyframe("rotation", endFrame).setValue(endAngle);
            return true;
        } catch (e) {
            $.writeln("添加旋转关键帧失败: " + e.message);
            return false;
        }
    },
    
    addOpacityKeyframes: function(pageItem, startFrame, endFrame, startOpacity, endOpacity) {
        try {
            pageItem.addKeyframe("opacity", startFrame).setValue(startOpacity);
            pageItem.addKeyframe("opacity", endFrame).setValue(endOpacity);
            return true;
        } catch (e) {
            $.writeln("添加透明度关键帧失败: " + e.message);
            return false;
        }
    },
    
    setEasing: function(keyframe, easingType) {
        try {
            keyframe.interpolationType = easingType;
            return true;
        } catch (e) {
            $.writeln("设置缓动失败: " + e.message);
            return false;
        }
    }
};
```

### 8.2 动画预设

```javascript
var AnimationPresets = {
    createMoveAnimation: function(pageItem, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 60,
            startX: 0,
            startY: 0,
            endX: 100,
            endY: 0,
            easing: KeyframeInterpolationType.EASEINEASEOUT
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var startKeyframe = pageItem.addKeyframe("position", cfg.startFrame);
            startKeyframe.setValue([cfg.startX, cfg.startY]);
            startKeyframe.interpolationType = cfg.easing;
            
            var endKeyframe = pageItem.addKeyframe("position", cfg.endFrame);
            endKeyframe.setValue([cfg.endX, cfg.endY]);
            endKeyframe.interpolationType = cfg.easing;
            
            return { startKeyframe: startKeyframe, endKeyframe: endKeyframe };
        } catch (e) {
            $.writeln("创建位移动画失败: " + e.message);
            return null;
        }
    },
    
    createScaleAnimation: function(pageItem, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 30,
            startScale: 100,
            endScale: 150,
            easing: KeyframeInterpolationType.EASEINEASEOUT
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var startKeyframe = pageItem.addKeyframe("scale", cfg.startFrame);
            startKeyframe.setValue([cfg.startScale, cfg.startScale]);
            startKeyframe.interpolationType = cfg.easing;
            
            var endKeyframe = pageItem.addKeyframe("scale", cfg.endFrame);
            endKeyframe.setValue([cfg.endScale, cfg.endScale]);
            endKeyframe.interpolationType = cfg.easing;
            
            return { startKeyframe: startKeyframe, endKeyframe: endKeyframe };
        } catch (e) {
            $.writeln("创建缩放动画失败: " + e.message);
            return null;
        }
    },
    
    createRotationAnimation: function(pageItem, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 60,
            startAngle: 0,
            endAngle: 360,
            easing: KeyframeInterpolationType.LINEAR
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var startKeyframe = pageItem.addKeyframe("rotation", cfg.startFrame);
            startKeyframe.setValue(cfg.startAngle);
            startKeyframe.interpolationType = cfg.easing;
            
            var endKeyframe = pageItem.addKeyframe("rotation", cfg.endFrame);
            endKeyframe.setValue(cfg.endAngle);
            endKeyframe.interpolationType = cfg.easing;
            
            return { startKeyframe: startKeyframe, endKeyframe: endKeyframe };
        } catch (e) {
            $.writeln("创建旋转动画失败: " + e.message);
            return null;
        }
    },
    
    createFadeAnimation: function(pageItem, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 30,
            startOpacity: 0,
            endOpacity: 100,
            easing: KeyframeInterpolationType.EASEINEASEOUT
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var startKeyframe = pageItem.addKeyframe("opacity", cfg.startFrame);
            startKeyframe.setValue(cfg.startOpacity);
            startKeyframe.interpolationType = cfg.easing;
            
            var endKeyframe = pageItem.addKeyframe("opacity", cfg.endFrame);
            endKeyframe.setValue(cfg.endOpacity);
            endKeyframe.interpolationType = cfg.easing;
            
            return { startKeyframe: startKeyframe, endKeyframe: endKeyframe };
        } catch (e) {
            $.writeln("创建淡入淡出动画失败: " + e.message);
            return null;
        }
    },
    
    createBounceAnimation: function(pageItem, config) {
        var defaults = {
            startFrame: 0,
            bounceCount: 3,
            amplitude: 100
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var frameDuration = 30;
            var startPos = pageItem.position;
            
            for (var i = 0; i < cfg.bounceCount; i++) {
                var startFrame = cfg.startFrame + i * frameDuration;
                var peakFrame = startFrame + frameDuration / 2;
                var endFrame = startFrame + frameDuration;
                
                var bounceHeight = cfg.amplitude * Math.pow(0.6, i);
                
                pageItem.addKeyframe("position", startFrame).setValue(startPos);
                pageItem.addKeyframe("position", peakFrame).setValue([startPos[0], startPos[1] - bounceHeight]);
                pageItem.addKeyframe("position", endFrame).setValue(startPos);
            }
            
            return true;
        } catch (e) {
            $.writeln("创建弹跳动画失败: " + e.message);
            return false;
        }
    },
    
    createPulseAnimation: function(pageItem, config) {
        var defaults = {
            startFrame: 0,
            pulseCount: 5,
            scaleAmount: 120
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var frameDuration = 24;
            
            for (var i = 0; i < cfg.pulseCount; i++) {
                var startFrame = cfg.startFrame + i * frameDuration;
                var peakFrame = startFrame + frameDuration / 2;
                var endFrame = startFrame + frameDuration;
                
                pageItem.addKeyframe("scale", startFrame).setValue([100, 100]);
                pageItem.addKeyframe("scale", peakFrame).setValue([cfg.scaleAmount, cfg.scaleAmount]);
                pageItem.addKeyframe("scale", endFrame).setValue([100, 100]);
            }
            
            return true;
        } catch (e) {
            $.writeln("创建脉冲动画失败: " + e.message);
            return false;
        }
    }
};
```

---

## 九、与其他 Adobe 应用集成

### 9.1 动态链接

```javascript
var DynamicLinkManager = {
    exportToAE: function(doc, outputPath) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(outputPath);
            
            var exportOptions = new ExportOptionsAfterEffects();
            d.exportFile(file, ExportType.AFTEREFFECTS, exportOptions);
            
            return true;
        } catch (e) {
            $.writeln("导出到AE失败: " + e.message);
            return false;
        }
    },
    
    exportToPremiere: function(doc, outputPath) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(outputPath);
            
            var exportOptions = new ExportOptionsQuickTime();
            d.exportFile(file, ExportType.QUICKTIME, exportOptions);
            
            return true;
        } catch (e) {
            $.writeln("导出到Premiere失败: " + e.message);
            return false;
        }
    },
    
    exportToPhotoshop: function(doc, outputPath) {
        try {
            var d = doc || Illustrator.doc;
            var file = new File(outputPath);
            
            var exportOptions = new ExportOptionsPhotoshop();
            exportOptions.exportAsLayers = true;
            exportOptions.writeLayers = true;
            
            d.exportFile(file, ExportType.PHOTOSHOP, exportOptions);
            
            return true;
        } catch (e) {
            $.writeln("导出到Photoshop失败: " + e.message);
            return false;
        }
    },
    
    importFromPhotoshop: function(psdPath) {
        try {
            var file = new File(psdPath);
            return Illustrator.app.open(file);
        } catch (e) {
            $.writeln("从Photoshop导入失败: " + e.message);
            return null;
        }
    }
};
```

---

## 十、企业级部署

### 10.1 环境配置

```javascript
var AIEnvironment = {
    getSystemInfo: function() {
        return {
            version: Illustrator.app.version,
            platform: Illustrator.app.platform,
            ram: Illustrator.app.systemInfo.ram,
            gpu: Illustrator.app.systemInfo.gpu
        };
    },
    
    setScratchDisks: function(disks) {
        try {
            Illustrator.app.scratchDisks = disks;
            return true;
        } catch (e) {
            $.writeln("设置暂存盘失败: " + e.message);
            return false;
        }
    },
    
    clearCache: function() {
        try {
            Illustrator.app.clearCache();
            return true;
        } catch (e) {
            $.writeln("清除缓存失败: " + e.message);
            return false;
        }
    },
    
    exportPreferences: function(outputPath) {
        try {
            Illustrator.app.preferences.exportPreferences(File(outputPath));
            return true;
        } catch (e) {
            $.writeln("导出首选项失败: " + e.message);
            return false;
        }
    },
    
    importPreferences: function(inputPath) {
        try {
            Illustrator.app.preferences.importPreferences(File(inputPath));
            return true;
        } catch (e) {
            $.writeln("导入首选项失败: " + e.message);
            return false;
        }
    }
};
```

### 10.2 脚本部署

```javascript
var ScriptDeployer = {
    installScript: function(scriptPath, menuName) {
        try {
            var scriptFile = new File(scriptPath);
            Illustrator.app.scriptMenu.installScript(scriptFile, menuName);
            return true;
        } catch (e) {
            $.writeln("安装脚本失败: " + e.message);
            return false;
        }
    },
    
    uninstallScript: function(menuName) {
        try {
            Illustrator.app.scriptMenu.uninstallScript(menuName);
            return true;
        } catch (e) {
            $.writeln("卸载脚本失败: " + e.message);
            return false;
        }
    },
    
    runScript: function(scriptPath) {
        try {
            var scriptFile = new File(scriptPath);
            Illustrator.app.doScript(scriptFile);
            return true;
        } catch (e) {
            $.writeln("运行脚本失败: " + e.message);
            return false;
        }
    }
};
```

---

*本指南涵盖 Illustrator 企业级集成的完整知识体系，包括 JavaScript API、文档管理、图层系统、路径绘制、文本处理、渐变颜色、符号管理、MG动画、动态链接等核心模块*
