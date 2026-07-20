# MG动画制作完整指南

---

## 一、MG动画概述

### 1.1 MG动画定义与特点

MG（Motion Graphics）动画是一种将图形、文字、色彩等元素通过动态手段展现的视觉艺术形式，具有以下特点：

- **简洁明快**：扁平化设计风格，线条清晰，色彩鲜明
- **信息传达**：擅长将复杂信息转化为直观的视觉表达
- **节奏鲜明**：配合音乐节拍，节奏感强
- **风格多样**：可实现卡通、科技、文艺等多种风格
- **高效制作**：相比传统动画，制作周期更短

### 1.2 MG动画应用场景

| 场景 | 应用示例 |
|------|---------|
| **品牌宣传** | 企业宣传片、产品介绍、品牌Logo动画 |
| **信息可视化** | 数据图表动画、流程演示、科普动画 |
| **影视包装** | 片头片尾、栏目包装、字幕动画 |
| **社交媒体** | 短视频、GIF动图、广告动画 |
| **教育培训** | 教学课件、培训视频、知识科普 |

### 1.3 制作流程

```
MG动画制作流程
├── 前期策划
│   ├── 需求分析
│   ├── 脚本编写
│   ├── 分镜设计
│   └── 风格定义
├── 素材制作
│   ├── 图形绘制（AI）
│   ├── 素材收集
│   └── 资源整理
├── 动画制作
│   ├── 场景搭建
│   ├── 关键帧动画
│   ├── 表达式控制
│   └── 特效添加
├── 后期合成
│   ├── 调色处理
│   ├── 音效配乐
│   ├── 字幕添加
│   └── 最终渲染
└── 输出交付
    ├── 格式选择
    ├── 参数设置
    └── 质量检查
```

---

## 二、前期策划

### 2.1 脚本编写

```javascript
var MGScriptWriter = {
    createScript: function(config) {
        var defaults = {
            title: "Untitled MG Animation",
            duration: 60,
            fps: 24,
            scenes: []
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return {
            title: cfg.title,
            duration: cfg.duration,
            fps: cfg.fps,
            scenes: cfg.scenes,
            totalFrames: cfg.duration * cfg.fps
        };
    },
    
    createScene: function(config) {
        var defaults = {
            id: "",
            name: "",
            startTime: 0,
            duration: 10,
            description: "",
            elements: [],
            camera: null,
            background: null,
            transitions: []
        };
        
        return Object.assign({}, defaults, config);
    },
    
    createElement: function(config) {
        var defaults = {
            id: "",
            name: "",
            type: "shape",
            position: [0, 0],
            size: [100, 100],
            color: [1, 0, 0],
            opacity: 100,
            animations: []
        };
        
        return Object.assign({}, defaults, config);
    },
    
    createAnimation: function(config) {
        var defaults = {
            property: "position",
            startValue: [0, 0],
            endValue: [100, 100],
            startTime: 0,
            duration: 1,
            easing: "easeInOut"
        };
        
        return Object.assign({}, defaults, config);
    },
    
    validateScript: function(script) {
        var errors = [];
        
        if (!script.title) errors.push("缺少标题");
        if (!script.duration || script.duration <= 0) errors.push("时长无效");
        if (!script.scenes || script.scenes.length === 0) errors.push("缺少场景");
        
        for (var i = 0; i < script.scenes.length; i++) {
            var scene = script.scenes[i];
            if (!scene.id) errors.push("场景 " + (i + 1) + " 缺少ID");
            if (!scene.name) errors.push("场景 " + (i + 1) + " 缺少名称");
            if (scene.startTime + scene.duration > script.duration) {
                errors.push("场景 " + scene.name + " 超出总时长");
            }
        }
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    }
};
```

### 2.2 分镜设计

```javascript
var StoryboardDesigner = {
    createStoryboard: function(script) {
        var storyboard = {
            title: script.title,
            scenes: []
        };
        
        for (var i = 0; i < script.scenes.length; i++) {
            var scene = script.scenes[i];
            
            storyboard.scenes.push({
                sceneIndex: i + 1,
                sceneId: scene.id,
                sceneName: scene.name,
                startTime: scene.startTime,
                duration: scene.duration,
                endTime: scene.startTime + scene.duration,
                frameCount: scene.duration * script.fps,
                thumbnail: null,
                description: scene.description,
                elements: scene.elements.map(function(el) {
                    return {
                        id: el.id,
                        name: el.name,
                        type: el.type,
                        position: el.position,
                        size: el.size,
                        color: el.color
                    };
                }),
                notes: ""
            });
        }
        
        return storyboard;
    },
    
    generateTimeline: function(script) {
        var timeline = {
            totalDuration: script.duration,
            fps: script.fps,
            markers: [],
            scenes: []
        };
        
        for (var i = 0; i < script.scenes.length; i++) {
            var scene = script.scenes[i];
            
            timeline.markers.push({
                time: scene.startTime,
                label: "Scene " + (i + 1) + ": " + scene.name,
                color: "green"
            });
            
            timeline.scenes.push({
                index: i,
                name: scene.name,
                startTime: scene.startTime,
                endTime: scene.startTime + scene.duration,
                duration: scene.duration,
                elements: scene.elements
            });
        }
        
        return timeline;
    },
    
    calculateTiming: function(script) {
        var timing = {
            totalFrames: script.duration * script.fps,
            scenes: []
        };
        
        for (var i = 0; i < script.scenes.length; i++) {
            var scene = script.scenes[i];
            
            timing.scenes.push({
                sceneId: scene.id,
                startFrame: Math.floor(scene.startTime * script.fps),
                endFrame: Math.floor((scene.startTime + scene.duration) * script.fps),
                frameCount: Math.floor(scene.duration * script.fps),
                percentage: (scene.duration / script.duration) * 100
            });
        }
        
        return timing;
    }
};
```

---

## 三、素材制作

### 3.1 图形绘制规范

```javascript
var GraphicDesigner = {
    createMGGraphic: function(config) {
        var defaults = {
            width: 1920,
            height: 1080,
            units: "px",
            colorMode: "RGB",
            resolution: 72,
            artboards: []
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return {
            dimensions: {
                width: cfg.width,
                height: cfg.height,
                units: cfg.units
            },
            colorMode: cfg.colorMode,
            resolution: cfg.resolution,
            artboards: cfg.artboards,
            layers: [],
            assets: []
        };
    },
    
    createArtboard: function(config) {
        var defaults = {
            id: "",
            name: "",
            x: 0,
            y: 0,
            width: 1920,
            height: 1080,
            background: null,
            content: []
        };
        
        return Object.assign({}, defaults, config);
    },
    
    createShapeAsset: function(config) {
        var defaults = {
            id: "",
            name: "",
            type: "rectangle",
            fill: {
                type: "solid",
                color: [1, 1, 1],
                opacity: 100
            },
            stroke: {
                color: [0, 0, 0],
                width: 0,
                opacity: 100
            },
            transform: {
                x: 0,
                y: 0,
                width: 100,
                height: 100,
                rotation: 0,
                scale: [100, 100],
                anchor: [0, 0]
            },
            effects: []
        };
        
        return Object.assign({}, defaults, config);
    },
    
    createIconAsset: function(config) {
        var defaults = {
            id: "",
            name: "",
            category: "",
            size: 64,
            fillColor: [0.1, 0.1, 0.1],
            strokeColor: null,
            strokeWidth: 0,
            pathData: "",
            viewBox: "0 0 24 24"
        };
        
        return Object.assign({}, defaults, config);
    },
    
    createTextAsset: function(config) {
        var defaults = {
            id: "",
            name: "",
            content: "",
            fontFamily: "Arial",
            fontSize: 24,
            fontWeight: "normal",
            fillColor: [0, 0, 0],
            align: "left",
            transform: {
                x: 0,
                y: 0,
                rotation: 0,
                scale: [100, 100]
            }
        };
        
        return Object.assign({}, defaults, config);
    },
    
    createColorPalette: function(name, colors) {
        return {
            name: name,
            colors: colors.map(function(c, i) {
                return {
                    id: name + "_" + (i + 1),
                    name: name + "_" + (i + 1),
                    rgb: c,
                    hex: this._rgbToHex(c)
                };
            }.bind(this))
        };
    },
    
    _rgbToHex: function(rgb) {
        return "#" + rgb.map(function(c) {
            var hex = Math.round(c * 255).toString(16);
            return hex.length === 1 ? "0" + hex : hex;
        }).join("");
    },
    
    createGradientPreset: function(name, stops) {
        return {
            name: name,
            stops: stops
        };
    },
    
    createLineStyle: function(name, config) {
        var defaults = {
            color: [0, 0, 0],
            width: 2,
            cap: "round",
            join: "round",
            dash: []
        };
        
        return Object.assign({ name: name }, defaults, config);
    }
};
```

### 3.2 素材管理

```javascript
var AssetManager = {
    assets: {},
    categories: {},
    
    registerAsset: function(category, asset) {
        if (!this.categories[category]) {
            this.categories[category] = [];
        }
        
        this.assets[asset.id] = asset;
        this.categories[category].push(asset.id);
    },
    
    getAsset: function(assetId) {
        return this.assets[assetId];
    },
    
    getAssetsByCategory: function(category) {
        if (!this.categories[category]) return [];
        
        return this.categories[category].map(function(id) {
            return this.assets[id];
        }.bind(this));
    },
    
    removeAsset: function(assetId) {
        var asset = this.assets[assetId];
        if (!asset) return false;
        
        delete this.assets[assetId];
        
        for (var category in this.categories) {
            var index = this.categories[category].indexOf(assetId);
            if (index > -1) {
                this.categories[category].splice(index, 1);
                break;
            }
        }
        
        return true;
    },
    
    exportAssets: function(category, outputPath) {
        var assets = this.getAssetsByCategory(category);
        
        var exportData = {
            category: category,
            count: assets.length,
            exportedAt: new Date().toISOString(),
            assets: assets
        };
        
        var file = new File(outputPath);
        file.open("w");
        file.write(JSON.stringify(exportData, null, 2));
        file.close();
        
        return true;
    },
    
    importAssets: function(filePath) {
        var file = new File(filePath);
        file.open("r");
        var importData = JSON.parse(file.read());
        file.close();
        
        for (var i = 0; i < importData.assets.length; i++) {
            this.registerAsset(importData.category, importData.assets[i]);
        }
        
        return importData.assets.length;
    },
    
    listCategories: function() {
        return Object.keys(this.categories);
    },
    
    listAssets: function() {
        return Object.values(this.assets);
    }
};
```

---

## 四、动画制作核心技术

### 4.1 关键帧动画基础

```javascript
var KeyframeAnimator = {
    createPositionAnimation: function(layer, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 60,
            startPosition: [0, 0],
            endPosition: [100, 100],
            easing: "easeInOut"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var startKey = layer.position.setValueAtKeyframe(cfg.startFrame, cfg.startPosition);
        var endKey = layer.position.setValueAtKeyframe(cfg.endFrame, cfg.endPosition);
        
        this._applyEasing(layer.position, cfg.easing);
        
        return { startKey: startKey, endKey: endKey };
    },
    
    createScaleAnimation: function(layer, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 30,
            startScale: [100, 100],
            endScale: [150, 150],
            easing: "easeInOut"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var startKey = layer.scale.setValueAtKeyframe(cfg.startFrame, cfg.startScale);
        var endKey = layer.scale.setValueAtKeyframe(cfg.endFrame, cfg.endScale);
        
        this._applyEasing(layer.scale, cfg.easing);
        
        return { startKey: startKey, endKey: endKey };
    },
    
    createRotationAnimation: function(layer, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 60,
            startAngle: 0,
            endAngle: 360,
            easing: "linear"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var startKey = layer.rotation.setValueAtKeyframe(cfg.startFrame, cfg.startAngle);
        var endKey = layer.rotation.setValueAtKeyframe(cfg.endFrame, cfg.endAngle);
        
        this._applyEasing(layer.rotation, cfg.easing);
        
        return { startKey: startKey, endKey: endKey };
    },
    
    createOpacityAnimation: function(layer, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 30,
            startOpacity: 0,
            endOpacity: 100,
            easing: "easeInOut"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var startKey = layer.opacity.setValueAtKeyframe(cfg.startFrame, cfg.startOpacity);
        var endKey = layer.opacity.setValueAtKeyframe(cfg.endFrame, cfg.endOpacity);
        
        this._applyEasing(layer.opacity, cfg.easing);
        
        return { startKey: startKey, endKey: endKey };
    },
    
    createMultiPropertyAnimation: function(layer, animations) {
        var results = {};
        
        for (var propName in animations) {
            var config = animations[propName];
            
            switch (propName) {
                case "position":
                    results.position = this.createPositionAnimation(layer, config);
                    break;
                case "scale":
                    results.scale = this.createScaleAnimation(layer, config);
                    break;
                case "rotation":
                    results.rotation = this.createRotationAnimation(layer, config);
                    break;
                case "opacity":
                    results.opacity = this.createOpacityAnimation(layer, config);
                    break;
            }
        }
        
        return results;
    },
    
    _applyEasing: function(prop, easingType) {
        var keyframes = prop.keyframes();
        
        switch (easingType) {
            case "easeInOut":
                for (var i = 0; i < keyframes.length; i++) {
                    keyframes[i].setEaseIn();
                    keyframes[i].setEaseOut();
                }
                break;
            case "linear":
                for (var i = 0; i < keyframes.length; i++) {
                    keyframes[i].setInterpolationType(KeyframeInterpolationType.LINEAR);
                }
                break;
        }
    }
};
```

### 4.2 表达式动画

```javascript
var ExpressionAnimator = {
    applyWiggle: function(layer, property, config) {
        var defaults = {
            frequency: 1,
            amplitude: 10,
            octaves: 1,
            ampMult: 0.5
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        layer.property(property).expression = 
            "wiggle(" + cfg.frequency + ", " + cfg.amplitude + ", " + 
            cfg.octaves + ", " + cfg.ampMult + ")";
    },
    
    applyLoop: function(layer, property, config) {
        var defaults = {
            type: "pingpong",
            duration: 1
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var loopFn = cfg.type === "pingpong" ? "loopPingpong" : "loopOut";
        
        layer.property(property).expression = loopFn + "(\"" + cfg.type + "\", " + cfg.duration + ")";
    },
    
    applyRandom: function(layer, property, config) {
        var defaults = {
            min: 0,
            max: 100,
            seed: 1
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        layer.property(property).expression = 
            "seedRandom(" + cfg.seed + ", true); random(" + cfg.min + ", " + cfg.max + ")";
    },
    
    applyFollow: function(layer, targetLayer, config) {
        var defaults = {
            lag: 0.1,
            offset: [0, 0, 0]
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        layer.position.expression = 
            "var target = thisComp.layer('" + targetLayer.name + "').position;\n" +
            "easeOut(time, value, target + " + JSON.stringify(cfg.offset) + ", " + cfg.lag + ")";
    },
    
    applyBounce: function(layer, config) {
        var defaults = {
            amplitude: 100,
            gravity: 500,
            bounces: 3,
            stiffness: 0.5
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        layer.position.expression = 
            "var a = " + cfg.amplitude + "; var g = " + cfg.gravity + ";\n" +
            "var b = " + cfg.bounces + "; var s = " + cfg.stiffness + ";\n" +
            "var t = time;\n" +
            "for (var i = 0; i < b; i++) {\n" +
            "  var tb = Math.sqrt(2 * a / g);\n" +
            "  if (t < tb) break;\n" +
            "  t -= tb; a *= s;\n" +
            "}\n" +
            "[value[0], value[1] + a - 0.5 * g * t * t]";
    },
    
    applyStagger: function(layers, property, config) {
        var defaults = {
            delay: 0.1,
            startValue: 0,
            endValue: 100,
            duration: 0.5
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        for (var i = 0; i < layers.length; i++) {
            var layer = layers[i];
            var delayTime = i * cfg.delay;
            
            layer.property(property).expression = 
                "var t = time - " + delayTime + ";\n" +
                "t < 0 ? " + cfg.startValue + " : easeOut(t, " + cfg.startValue + ", " + cfg.endValue + ", " + cfg.duration + ")";
        }
    },
    
    removeExpression: function(layer, property) {
        layer.property(property).expression = "";
    }
};
```

### 4.3 形状图层动画

```javascript
var ShapeAnimator = {
    createShapeLayer: function(comp, config) {
        var defaults = {
            name: "Shape Layer",
            position: [comp.width / 2, comp.height / 2],
            shapes: []
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        for (var i = 0; i < cfg.shapes.length; i++) {
            this.addShapeToLayer(shapeLayer, cfg.shapes[i]);
        }
        
        shapeLayer.position.setValue(cfg.position);
        
        return shapeLayer;
    },
    
    addShapeToLayer: function(layer, shapeConfig) {
        var group = layer.property("Contents").addProperty("ADBE Vector Group");
        
        switch (shapeConfig.type) {
            case "rectangle":
                this._createRectangleShape(group, shapeConfig);
                break;
            case "circle":
                this._createCircleShape(group, shapeConfig);
                break;
            case "triangle":
                this._createTriangleShape(group, shapeConfig);
                break;
            case "star":
                this._createStarShape(group, shapeConfig);
                break;
        }
        
        return group;
    },
    
    _createRectangleShape: function(group, config) {
        var rectPath = group.property("Contents").addProperty("ADBE Vector Shape - Rect");
        rectPath.property("ADBE Rect Size").setValue([config.width || 100, config.height || 100]);
        rectPath.property("ADBE Rect Corner Radius").setValue(config.cornerRadius || 0);
        
        if (config.fill) {
            var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
            fill.property("ADBE Fill Color").setValue(config.fill);
        }
    },
    
    _createCircleShape: function(group, config) {
        var ellipsePath = group.property("Contents").addProperty("ADBE Vector Shape - Ellipse");
        ellipsePath.property("ADBE Ellipse Size").setValue([(config.radius || 50) * 2, (config.radius || 50) * 2]);
        
        if (config.fill) {
            var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
            fill.property("ADBE Fill Color").setValue(config.fill);
        }
    },
    
    _createTriangleShape: function(group, config) {
        var polyPath = group.property("Contents").addProperty("ADBE Vector Shape - Polygon");
        polyPath.property("ADBE Polygon Points").setValue(3);
        polyPath.property("ADBE Polygon Outer Radius").setValue((config.size || 100) / 2);
        
        if (config.fill) {
            var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
            fill.property("ADBE Fill Color").setValue(config.fill);
        }
    },
    
    _createStarShape: function(group, config) {
        var starPath = group.property("Contents").addProperty("ADBE Vector Shape - Star");
        starPath.property("ADBE Star Outer Radius").setValue(config.outerRadius || 50);
        starPath.property("ADBE Star Inner Radius").setValue(config.innerRadius || 25);
        starPath.property("ADBE Star Points").setValue(config.points || 5);
        
        if (config.fill) {
            var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
            fill.property("ADBE Fill Color").setValue(config.fill);
        }
    },
    
    addTrimPaths: function(shapeLayer, shapeIndex) {
        var group = shapeLayer.property("Contents").property(shapeIndex);
        var trimPaths = group.property("Contents").addProperty("ADBE Trim Paths");
        
        return trimPaths;
    },
    
    animateTrimPaths: function(trimPaths, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 60,
            startTrim: 0,
            endTrim: 100
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        trimPaths.property("ADBE Trim End").setValueAtKeyframe(cfg.startFrame, cfg.startTrim);
        trimPaths.property("ADBE Trim End").setValueAtKeyframe(cfg.endFrame, cfg.endTrim);
        
        return trimPaths;
    }
};
```

---

## 五、高级动画技巧

### 5.1 粒子系统

```javascript
var ParticleSystem = {
    createParticleEmitter: function(comp, config) {
        var defaults = {
            name: "Particle Emitter",
            position: [comp.width / 2, comp.height / 2],
            particleCount: 100,
            emissionRate: 10,
            lifetime: 2,
            speed: 50,
            size: [10, 20],
            color: [1, 0.5, 0],
            gravity: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var emitter = comp.layers.addNull();
        emitter.name = cfg.name;
        emitter.position.setValue(cfg.position);
        
        var emitterEffect = emitter.Effects.addProperty("ADBE Particle Playground");
        
        emitterEffect.property("ADBE PPlay-Emission Rate").setValue(cfg.emissionRate);
        emitterEffect.property("ADBE PPlay-Life").setValue(cfg.lifetime);
        emitterEffect.property("ADBE PPlay-Velocity").setValue(cfg.speed);
        emitterEffect.property("ADBE PPlay-Size").setValue(cfg.size);
        emitterEffect.property("ADBE PPlay-Color").setValue(cfg.color);
        emitterEffect.property("ADBE PPlay-Gravity").setValue(cfg.gravity);
        
        return emitter;
    },
    
    createExplosion: function(comp, position, config) {
        var defaults = {
            name: "Explosion",
            particleCount: 200,
            speed: 100,
            size: [5, 30],
            colors: [[1, 0, 0], [1, 0.5, 0], [1, 1, 0]],
            lifetime: 0.5,
            gravity: 50
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var emitter = comp.layers.addNull();
        emitter.name = cfg.name;
        emitter.position.setValue(position);
        
        var emitterEffect = emitter.Effects.addProperty("ADBE Particle Playground");
        
        emitterEffect.property("ADBE PPlay-Emission Rate").setValue(cfg.particleCount);
        emitterEffect.property("ADBE PPlay-Life").setValue(cfg.lifetime);
        emitterEffect.property("ADBE PPlay-Velocity").setValue(cfg.speed);
        emitterEffect.property("ADBE PPlay-Size").setValue(cfg.size);
        emitterEffect.property("ADBE PPlay-Gravity").setValue(cfg.gravity);
        
        return emitter;
    },
    
    createFloatingParticles: function(comp, config) {
        var defaults = {
            name: "Floating Particles",
            position: [comp.width / 2, comp.height / 2],
            particleCount: 50,
            size: [2, 8],
            color: [1, 1, 1],
            opacity: 50,
            speed: 5,
            direction: -90
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var emitter = comp.layers.addNull();
        emitter.name = cfg.name;
        emitter.position.setValue(cfg.position);
        
        var emitterEffect = emitter.Effects.addProperty("ADBE Particle Playground");
        
        emitterEffect.property("ADBE PPlay-Emission Rate").setValue(cfg.particleCount);
        emitterEffect.property("ADBE PPlay-Life").setValue(10);
        emitterEffect.property("ADBE PPlay-Velocity").setValue(cfg.speed);
        emitterEffect.property("ADBE PPlay-Direction").setValue(cfg.direction);
        emitterEffect.property("ADBE PPlay-Size").setValue(cfg.size);
        emitterEffect.property("ADBE PPlay-Color").setValue(cfg.color);
        
        return emitter;
    }
};
```

### 5.2 摄像机与景深

```javascript
var CameraSystem = {
    createCamera: function(comp, config) {
        var defaults = {
            name: "Camera",
            position: [comp.width / 2, comp.height / 2, -500],
            pointOfInterest: [comp.width / 2, comp.height / 2, 0],
            zoom: 1000,
            depthOfField: false,
            aperture: 20,
            focusDistance: 500
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var camera = comp.layers.addCamera();
        camera.name = cfg.name;
        
        camera.position.setValue(cfg.position);
        camera.pointOfInterest.setValue(cfg.pointOfInterest);
        camera.zoom.setValue(cfg.zoom);
        
        if (cfg.depthOfField) {
            camera.depthOfField = true;
            camera.aperture.setValue(cfg.aperture);
            camera.focusDistance.setValue(cfg.focusDistance);
        }
        
        return camera;
    },
    
    animateCamera: function(camera, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 120,
            startPosition: [960, 540, -500],
            endPosition: [960, 540, -1000],
            easing: "easeInOut"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        camera.position.setValueAtKeyframe(cfg.startFrame, cfg.startPosition);
        camera.position.setValueAtKeyframe(cfg.endFrame, cfg.endPosition);
        
        this._applyEasing(camera.position, cfg.easing);
        
        return camera;
    },
    
    createOrbitAnimation: function(camera, config) {
        var defaults = {
            center: [960, 540, 0],
            radius: 500,
            duration: 240,
            startAngle: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        camera.position.expression = 
            "var angle = " + cfg.startAngle + " + (time / " + cfg.duration + ") * 2 * Math.PI;\n" +
            "[" + cfg.center[0] + " + Math.cos(angle) * " + cfg.radius + ", " + 
            cfg.center[1] + ", " + cfg.center[2] + " + Math.sin(angle) * " + cfg.radius + "]";
        
        camera.pointOfInterest.expression = "[" + cfg.center[0] + ", " + cfg.center[1] + ", " + cfg.center[2] + "]";
        
        return camera;
    },
    
    _applyEasing: function(prop, easingType) {
        var keyframes = prop.keyframes();
        
        if (easingType === "easeInOut") {
            for (var i = 0; i < keyframes.length; i++) {
                keyframes[i].setEaseIn();
                keyframes[i].setEaseOut();
            }
        }
    }
};
```

### 5.3 灯光与阴影

```javascript
var LightingSystem = {
    createPointLight: function(comp, config) {
        var defaults = {
            name: "Point Light",
            position: [comp.width / 2, comp.height / 2, 100],
            intensity: 100,
            color: [1, 1, 1],
            castShadows: false
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var light = comp.layers.addLight();
        light.name = cfg.name;
        light.lightType = LightType.POINT;
        
        light.position.setValue(cfg.position);
        light.intensity.setValue(cfg.intensity);
        light.color.setValue(cfg.color);
        light.castShadows = cfg.castShadows;
        
        return light;
    },
    
    createSpotLight: function(comp, config) {
        var defaults = {
            name: "Spot Light",
            position: [comp.width / 2, comp.height / 2, 200],
            pointOfInterest: [comp.width / 2, comp.height / 2, 0],
            intensity: 100,
            color: [1, 1, 1],
            coneAngle: 45,
            castShadows: false
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var light = comp.layers.addLight();
        light.name = cfg.name;
        light.lightType = LightType.SPOT;
        
        light.position.setValue(cfg.position);
        light.pointOfInterest.setValue(cfg.pointOfInterest);
        light.intensity.setValue(cfg.intensity);
        light.color.setValue(cfg.color);
        light.coneAngle.setValue(cfg.coneAngle);
        light.castShadows = cfg.castShadows;
        
        return light;
    },
    
    createAmbientLight: function(comp, config) {
        var defaults = {
            name: "Ambient Light",
            intensity: 30,
            color: [1, 1, 1]
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var light = comp.layers.addLight();
        light.name = cfg.name;
        light.lightType = LightType.AMBIENT;
        
        light.intensity.setValue(cfg.intensity);
        light.color.setValue(cfg.color);
        
        return light;
    },
    
    animateLight: function(light, config) {
        var defaults = {
            startFrame: 0,
            endFrame: 60,
            startIntensity: 100,
            endIntensity: 50,
            easing: "easeInOut"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        light.intensity.setValueAtKeyframe(cfg.startFrame, cfg.startIntensity);
        light.intensity.setValueAtKeyframe(cfg.endFrame, cfg.endIntensity);
        
        this._applyEasing(light.intensity, cfg.easing);
        
        return light;
    },
    
    _applyEasing: function(prop, easingType) {
        var keyframes = prop.keyframes();
        
        if (easingType === "easeInOut") {
            for (var i = 0; i < keyframes.length; i++) {
                keyframes[i].setEaseIn();
                keyframes[i].setEaseOut();
            }
        }
    }
};
```

---

## 六、后期合成与输出

### 6.1 调色处理

```javascript
var ColorGrading = {
    applyLUT: function(layer, lutPath) {
        var lutEffect = layer.Effects.addProperty("ADBE LUT Filter");
        lutEffect.property("ADBE LUT File").setValue(new File(lutPath));
        
        return lutEffect;
    },
    
    applyColorBalance: function(layer, config) {
        var defaults = {
            shadowRed: 0,
            shadowGreen: 0,
            shadowBlue: 0,
            midtoneRed: 0,
            midtoneGreen: 0,
            midtoneBlue: 0,
            highlightRed: 0,
            highlightGreen: 0,
            highlightBlue: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var cbEffect = layer.Effects.addProperty("ADBE Color Balance");
        
        cbEffect.property("ADBE CB Shadow Red").setValue(cfg.shadowRed);
        cbEffect.property("ADBE CB Shadow Green").setValue(cfg.shadowGreen);
        cbEffect.property("ADBE CB Shadow Blue").setValue(cfg.shadowBlue);
        
        cbEffect.property("ADBE CB Midtone Red").setValue(cfg.midtoneRed);
        cbEffect.property("ADBE CB Midtone Green").setValue(cfg.midtoneGreen);
        cbEffect.property("ADBE CB Midtone Blue").setValue(cfg.midtoneBlue);
        
        cbEffect.property("ADBE CB Highlight Red").setValue(cfg.highlightRed);
        cbEffect.property("ADBE CB Highlight Green").setValue(cfg.highlightGreen);
        cbEffect.property("ADBE CB Highlight Blue").setValue(cfg.highlightBlue);
        
        return cbEffect;
    },
    
    applyLevels: function(layer, config) {
        var defaults = {
            inputBlack: 0,
            inputWhite: 255,
            inputGamma: 1,
            outputBlack: 0,
            outputWhite: 255
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var levelsEffect = layer.Effects.addProperty("ADBE Levels");
        
        levelsEffect.property("ADBE Levels Input Black").setValue(cfg.inputBlack);
        levelsEffect.property("ADBE Levels Input White").setValue(cfg.inputWhite);
        levelsEffect.property("ADBE Levels Gamma").setValue(cfg.inputGamma);
        levelsEffect.property("ADBE Levels Output Black").setValue(cfg.outputBlack);
        levelsEffect.property("ADBE Levels Output White").setValue(cfg.outputWhite);
        
        return levelsEffect;
    },
    
    applyHueSaturation: function(layer, config) {
        var defaults = {
            hue: 0,
            saturation: 0,
            lightness: 0,
            colorize: false
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var hsEffect = layer.Effects.addProperty("ADBE Hue/Saturation");
        
        hsEffect.property("ADBE Hue/Sat Hue").setValue(cfg.hue);
        hsEffect.property("ADBE Hue/Sat Saturation").setValue(cfg.saturation);
        hsEffect.property("ADBE Hue/Sat Lightness").setValue(cfg.lightness);
        hsEffect.property("ADBE Hue/Sat Colorize").setValue(cfg.colorize);
        
        return hsEffect;
    },
    
    applyVibrance: function(layer, amount) {
        var vibranceEffect = layer.Effects.addProperty("ADBE Vibrance");
        vibranceEffect.property("ADBE Vibrance Amount").setValue(amount || 0);
        
        return vibranceEffect;
    }
};
```

### 6.2 音效与配乐

```javascript
var AudioManager = {
    importAudio: function(project, filePath) {
        var file = new File(filePath);
        var footage = project.importFile(ImportAsType.FOOTAGE, file);
        
        return footage;
    },
    
    addAudioToComp: function(comp, audioFootage, config) {
        var defaults = {
            startAt: 0,
            volume: 100,
            name: "Audio Track"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var audioLayer = comp.layers.add(audioFootage);
        audioLayer.name = cfg.name;
        audioLayer.inPoint = cfg.startAt;
        audioLayer.volume.setValue(cfg.volume / 100);
        
        return audioLayer;
    },
    
    applyFadeIn: function(audioLayer, duration) {
        var fadeDuration = duration || 1;
        var fadeFrames = fadeDuration * audioLayer.containingComp.frameRate;
        
        audioLayer.volume.setValueAtKeyframe(0, 0);
        audioLayer.volume.setValueAtKeyframe(fadeFrames, 1);
        
        var key1 = audioLayer.volume.keyframeAtTime(0);
        var key2 = audioLayer.volume.keyframeAtTime(fadeDuration);
        
        key1.setEaseIn();
        key2.setEaseOut();
    },
    
    applyFadeOut: function(audioLayer, duration) {
        var fadeDuration = duration || 1;
        var comp = audioLayer.containingComp;
        var fadeStartFrame = (comp.duration - fadeDuration) * comp.frameRate;
        var fadeEndFrame = comp.duration * comp.frameRate;
        
        audioLayer.volume.setValueAtKeyframe(fadeStartFrame, 1);
        audioLayer.volume.setValueAtKeyframe(fadeEndFrame, 0);
        
        var key1 = audioLayer.volume.keyframeAtTime(comp.duration - fadeDuration);
        var key2 = audioLayer.volume.keyframeAtTime(comp.duration);
        
        key1.setEaseIn();
        key2.setEaseOut();
    }
};
```

### 6.3 输出设置

```javascript
var ExportManager = {
    exportToMP4: function(comp, outputPath, config) {
        var defaults = {
            codec: "H.264",
            quality: 100,
            resolution: [1920, 1080],
            fps: 24,
            audioCodec: "AAC",
            audioBitrate: 128000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var exporter = new MediaEncoder();
        exporter.source = comp;
        exporter.outputPath = outputPath;
        
        exporter.videoCodec = cfg.codec;
        exporter.videoQuality = cfg.quality;
        exporter.resolution = cfg.resolution;
        exporter.fps = cfg.fps;
        exporter.audioCodec = cfg.audioCodec;
        exporter.audioBitrate = cfg.audioBitrate;
        
        exporter.export();
        
        return true;
    },
    
    exportToGIF: function(comp, outputPath, config) {
        var defaults = {
            startFrame: 0,
            endFrame: null,
            resolution: [480, 270],
            fps: 15,
            quality: 80,
            loop: true
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var endFrame = cfg.endFrame || comp.duration * comp.frameRate;
        
        var exporter = new MediaEncoder();
        exporter.source = comp;
        exporter.outputPath = outputPath;
        exporter.format = "GIF";
        
        exporter.startFrame = cfg.startFrame;
        exporter.endFrame = endFrame;
        exporter.resolution = cfg.resolution;
        exporter.fps = cfg.fps;
        exporter.quality = cfg.quality;
        exporter.loop = cfg.loop;
        
        exporter.export();
        
        return true;
    },
    
    exportToPNGSequence: function(comp, outputPath, config) {
        var defaults = {
            startFrame: 0,
            endFrame: null,
            resolution: [1920, 1080],
            bitDepth: 8,
            transparency: true
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var endFrame = cfg.endFrame || comp.duration * comp.frameRate;
        
        var exporter = new MediaEncoder();
        exporter.source = comp;
        exporter.outputPath = outputPath;
        exporter.format = "PNG Sequence";
        
        exporter.startFrame = cfg.startFrame;
        exporter.endFrame = endFrame;
        exporter.resolution = cfg.resolution;
        exporter.bitDepth = cfg.bitDepth;
        exporter.transparency = cfg.transparency;
        
        exporter.export();
        
        return true;
    },
    
    sendToMediaEncoder: function(comp, config) {
        var defaults = {
            preset: "Match Source - High Bitrate",
            outputPath: ""
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var exporter = new MediaEncoder();
        exporter.source = comp;
        exporter.outputPath = cfg.outputPath;
        exporter.preset = cfg.preset;
        exporter.sendToAME = true;
        
        exporter.export();
        
        return true;
    }
};
```

---

## 七、企业级项目管理

### 7.1 项目模板

```javascript
var ProjectTemplate = {
    createMGProject: function(config) {
        var defaults = {
            name: "MG Animation Project",
            width: 1920,
            height: 1080,
            fps: 24,
            duration: 60,
            pixelAspectRatio: "Square",
            workingSpace: "sRGB"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return {
            name: cfg.name,
            dimensions: {
                width: cfg.width,
                height: cfg.height,
                fps: cfg.fps,
                duration: cfg.duration,
                pixelAspectRatio: cfg.pixelAspectRatio,
                workingSpace: cfg.workingSpace
            },
            folders: {
                assets: "Assets/",
                footage: "Footage/",
                audio: "Audio/",
                compositions: "Comps/",
                renders: "Renders/",
                presets: "Presets/"
            },
            colorPalette: [],
            fontList: [],
            effects: [],
            expressions: []
        };
    },
    
    applyTemplate: function(project, template) {
        // 创建文件夹结构
        for (var folderName in template.folders) {
            project.items.addFolder(folderName);
        }
        
        // 导入预设
        if (template.effects) {
            for (var i = 0; i < template.effects.length; i++) {
                var effect = template.effects[i];
                project.items.addFile(new File(template.folders.presets + effect));
            }
        }
        
        return project;
    }
};
```

### 7.2 版本控制

```javascript
var VersionControl = {
    versions: [],
    
    saveVersion: function(project, description) {
        var version = {
            id: Date.now(),
            timestamp: new Date().toISOString(),
            description: description,
            projectName: project.name,
            itemCount: project.items.length,
            compCount: project.items.numItems
        };
        
        this.versions.push(version);
        
        return version;
    },
    
    getVersion: function(versionId) {
        return this.versions.find(function(v) { return v.id === versionId; });
    },
    
    listVersions: function() {
        return this.versions;
    },
    
    compareVersions: function(versionId1, versionId2) {
        var v1 = this.getVersion(versionId1);
        var v2 = this.getVersion(versionId2);
        
        if (!v1 || !v2) return null;
        
        return {
            version1: v1,
            version2: v2,
            timeDiff: new Date(v2.timestamp) - new Date(v1.timestamp),
            itemCountDiff: v2.itemCount - v1.itemCount
        };
    }
};
```

---

*本指南涵盖 MG动画制作的完整知识体系，包括前期策划、素材制作、动画核心技术、高级技巧、后期合成与企业级项目管理等模块*
