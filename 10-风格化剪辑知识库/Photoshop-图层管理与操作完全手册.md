# Photoshop 图层管理与操作完全手册

> 适用版本：Adobe Photoshop 2026 | 更新日期：2026-07-14 | 分类：Photoshop知识库

---

## 目录

- [一、图层核心概念](#一图层核心概念)
- [二、图层类型体系](#二图层类型体系)
- [三、图层创建与删除](#三图层创建与删除)
- [四、图层选择与排序](#四图层选择与排序)
- [五、图层变换操作](#五图层变换操作)
- [六、图层属性与样式](#六图层属性与样式)
- [七、图层组管理](#七图层组管理)
- [八、智能对象详解](#八智能对象详解)
- [九、调整图层详解](#九调整图层详解)
- [十、图层复合与状态管理](#十图层复合与状态管理)
- [十一、图层自动化API](#十一图层自动化api)
- [十二、故障排查与性能优化](#十二故障排查与性能优化)

---

## 一、图层核心概念

### 1.1 图层原理与结构

```javascript
// 图层核心概念
// Layer (图层): 图像的独立层级
// Pixel Layer (像素图层): 由像素组成的图层
// Adjustment Layer (调整图层): 用于调整下方图层的色彩
// Smart Object (智能对象): 包含嵌入图像或矢量数据
// Layer Group (图层组): 组织多个图层的容器
// Blend Mode (混合模式): 图层间的像素混合方式
```

### 1.2 图层堆栈原理

```javascript
class LayerStack {
    constructor() {
        this.layers = [];
        this.activeLayerIndex = -1;
    }

    addLayer(layer) {
        this.layers.push(layer);
        this.activeLayerIndex = this.layers.length - 1;
        return layer;
    }

    removeLayer(index) {
        if (index >= 0 && index < this.layers.length) {
            const removed = this.layers.splice(index, 1)[0];
            if (this.activeLayerIndex >= this.layers.length) {
                this.activeLayerIndex = Math.max(0, this.layers.length - 1);
            }
            return removed;
        }
        return null;
    }

    getActiveLayer() {
        return this.layers[this.activeLayerIndex] || null;
    }

    setActiveLayer(index) {
        if (index >= 0 && index < this.layers.length) {
            this.activeLayerIndex = index;
            return true;
        }
        return false;
    }

    moveLayerUp(index) {
        if (index < this.layers.length - 1) {
            const temp = this.layers[index];
            this.layers[index] = this.layers[index + 1];
            this.layers[index + 1] = temp;
            return true;
        }
        return false;
    }

    moveLayerDown(index) {
        if (index > 0) {
            const temp = this.layers[index];
            this.layers[index] = this.layers[index - 1];
            this.layers[index - 1] = temp;
            return true;
        }
        return false;
    }
}
```

### 1.3 图层与图像的关系

```javascript
function renderLayerStack(layers) {
    let result = createEmptyCanvas();
    
    layers.forEach(layer => {
        if (layer.visible) {
            result = applyBlendMode(result, layer.pixels, layer.blendMode, layer.opacity);
        }
    });
    
    return result;
}

function applyBlendMode(base, overlay, mode, opacity) {
    const opacityFactor = opacity / 100;
    
    return base.map((basePixel, i) => {
        const overlayPixel = overlay[i];
        
        let blended = { ...basePixel };
        
        switch (mode) {
            case 'normal':
                blended = blendNormal(basePixel, overlayPixel, opacityFactor);
                break;
            case 'multiply':
                blended = blendMultiply(basePixel, overlayPixel);
                break;
            case 'screen':
                blended = blendScreen(basePixel, overlayPixel);
                break;
            case 'overlay':
                blended = blendOverlay(basePixel, overlayPixel);
                break;
            default:
                blended = blendNormal(basePixel, overlayPixel, opacityFactor);
        }
        
        return blended;
    });
}

function blendNormal(base, overlay, opacity) {
    return {
        r: base.r * (1 - opacity) + overlay.r * opacity,
        g: base.g * (1 - opacity) + overlay.g * opacity,
        b: base.b * (1 - opacity) + overlay.b * opacity,
        a: base.a * (1 - opacity) + overlay.a * opacity
    };
}

function blendMultiply(base, overlay) {
    return {
        r: (base.r * overlay.r) / 255,
        g: (base.g * overlay.g) / 255,
        b: (base.b * overlay.b) / 255,
        a: Math.max(base.a, overlay.a)
    };
}

function blendScreen(base, overlay) {
    return {
        r: 255 - ((255 - base.r) * (255 - overlay.r)) / 255,
        g: 255 - ((255 - base.g) * (255 - overlay.g)) / 255,
        b: 255 - ((255 - base.b) * (255 - overlay.b)) / 255,
        a: Math.max(base.a, overlay.a)
    };
}

function blendOverlay(base, overlay) {
    const factor = overlay.a / 255;
    const baseNormalized = {
        r: base.r / 255,
        g: base.g / 255,
        b: base.b / 255
    };
    
    return {
        r: baseNormalized.r < 0.5 
            ? 2 * base.r * overlay.r / 255 
            : 255 - 2 * (255 - base.r) * (255 - overlay.r) / 255,
        g: baseNormalized.g < 0.5 
            ? 2 * base.g * overlay.g / 255 
            : 255 - 2 * (255 - base.g) * (255 - overlay.g) / 255,
        b: baseNormalized.b < 0.5 
            ? 2 * base.b * overlay.b / 255 
            : 255 - 2 * (255 - base.b) * (255 - overlay.b) / 255,
        a: Math.max(base.a, overlay.a)
    };
}
```

---

## 二、图层类型体系

### 2.1 图层类型分类

```javascript
class LayerTypeSystem {
    static get TYPES() {
        return {
            PIXEL: {
                name: '像素图层',
                icon: '🖼️',
                description: '由像素组成的标准图层',
                uses: ['图像编辑', '绘画', '合成']
            },
            ADJUSTMENT: {
                name: '调整图层',
                icon: '🎨',
                description: '调整下方图层色彩的非破坏性图层',
                uses: ['色彩校正', '色调调整', '批量处理']
            },
            SMART_OBJECT: {
                name: '智能对象',
                icon: '📦',
                description: '包含嵌入数据的容器图层',
                uses: ['非破坏性编辑', '矢量图形', '多文档链接']
            },
            SHAPE: {
                name: '形状图层',
                icon: '⬜',
                description: '矢量形状组成的图层',
                uses: ['图形设计', 'UI元素', '路径绘制']
            },
            TEXT: {
                name: '文字图层',
                icon: '📝',
                description: '可编辑文本的矢量图层',
                uses: ['排版', '标题', '字幕']
            },
            FILL: {
                name: '填充图层',
                icon: '🎭',
                description: '纯色/渐变/图案填充的图层',
                uses: ['背景', '蒙版填充', '色彩基础']
            },
            GROUP: {
                name: '图层组',
                icon: '📁',
                description: '组织多个图层的容器',
                uses: ['图层管理', '批量操作', '结构组织']
            },
            BACKGROUND: {
                name: '背景图层',
                icon: '🏞️',
                description: '锁定的底层像素图层',
                uses: ['画布基础', '图像底图']
            }
        };
    }
}
```

### 2.2 图层属性架构

```javascript
class LayerProperties {
    constructor() {
        this.name = 'Layer';
        this.visible = true;
        this.locked = false;
        this.opacity = 100;
        this.fillOpacity = 100;
        this.blendMode = 'normal';
        this.clippingMask = false;
        this.layerMask = null;
        this.vectorMask = null;
        this.effects = [];
        this.metadata = {};
    }

    serialize() {
        return {
            name: this.name,
            visible: this.visible,
            locked: this.locked,
            opacity: this.opacity,
            fillOpacity: this.fillOpacity,
            blendMode: this.blendMode,
            clippingMask: this.clippingMask,
            hasLayerMask: this.layerMask !== null,
            hasVectorMask: this.vectorMask !== null,
            effectCount: this.effects.length
        };
    }

    deserialize(data) {
        Object.assign(this, data);
        return this;
    }
}
```

---

## 三、图层创建与删除

### 3.1 创建新图层

```javascript
class LayerCreator {
    static createPixelLayer(name = 'Layer') {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Lyr '));
        desc.putString(charIDToTypeID('Nm  '), name);
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static createBackgroundLayer(color = { r: 255, g: 255, b: 255 }) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Bkgd'));
        
        const colorDesc = new ActionDescriptor();
        colorDesc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Prc'), color.r);
        colorDesc.putUnitDouble(charIDToTypeID('Grn '), charIDToTypeID('#Prc'), color.g);
        colorDesc.putUnitDouble(charIDToTypeID('Bl  '), charIDToTypeID('#Prc'), color.b);
        
        desc.putObject(charIDToTypeID('Clr '), charIDToTypeID('Clr '), colorDesc);
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static createTextLayer(text, options = {}) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Txt '));
        
        if (options.position) {
            desc.putUnitDouble(charIDToTypeID('TxtX'), charIDToTypeID('#Pxl'), options.position.x);
            desc.putUnitDouble(charIDToTypeID('TxtY'), charIDToTypeID('#Pxl'), options.position.y);
        }
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        
        const setDesc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        setDesc.putReference(charIDToTypeID('null'), layerRef);
        setDesc.putString(charIDToTypeID('Txtt'), text);
        
        executeAction(charIDToTypeID('SetT'), setDesc, DialogModes.NO);
    }

    static createShapeLayer(shapeType, bounds, options = {}) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Shp '));
        
        const shapeMap = {
            'rectangle': charIDToTypeID('Rctn'),
            'ellipse': charIDToTypeID('Elps'),
            'polygon': charIDToTypeID('Polg'),
            'star': charIDToTypeID('Str ')
        };
        
        desc.putEnumerated(charIDToTypeID('ShpT'), charIDToTypeID('ShpT'), shapeMap[shapeType]);
        
        const pathDesc = new ActionDescriptor();
        pathDesc.putUnitDouble(charIDToTypeID('Top '), charIDToTypeID('#Pxl'), bounds.top);
        pathDesc.putUnitDouble(charIDToTypeID('Left'), charIDToTypeID('#Pxl'), bounds.left);
        pathDesc.putUnitDouble(charIDToTypeID('Btom'), charIDToTypeID('#Pxl'), bounds.bottom);
        pathDesc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), bounds.right);
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static createFillLayer(type, options = {}) {
        const desc = new ActionDescriptor();
        
        const typeMap = {
            'solid': charIDToTypeID('Fl  '),
            'gradient': charIDToTypeID('Grad'),
            'pattern': charIDToTypeID('Ptn ')
        };
        
        desc.putClass(charIDToTypeID('null'), typeMap[type]);
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static createAdjustmentLayer(type, options = {}) {
        const desc = new ActionDescriptor();
        
        const typeMap = {
            'levels': charIDToTypeID('Levl'),
            'curves': charIDToTypeID('Crvs'),
            'brightnessContrast': charIDToTypeID('BrCn'),
            'colorBalance': charIDToTypeID('ClrB'),
            'hueSaturation': charIDToTypeID('HueS'),
            'selectiveColor': charIDToTypeID('SlCt'),
            'channelMixer': charIDToTypeID('Chnl'),
            'gradientMap': charIDToTypeID('GrdM'),
            'photoFilter': charIDToTypeID('PhFl'),
            'invert': charIDToTypeID('Invr'),
            'posterize': charIDToTypeID('Pstr'),
            'threshold': charIDToTypeID('Thrs'),
            'gradient': charIDToTypeID('Grad'),
            'solidColor': charIDToTypeID('Fl  '),
            'pattern': charIDToTypeID('Ptn ')
        };
        
        desc.putClass(charIDToTypeID('null'), typeMap[type]);
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static createSmartObject(filePath) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Smar'));
        
        const fileRef = new ActionReference();
        fileRef.putPath(charIDToTypeID('null'), filePath);
        
        desc.putReference(charIDToTypeID('null'), fileRef);
        
        executeAction(charIDToTypeID('Plc '), desc, DialogModes.NO);
    }

    static createLayerFromSelection() {
        executeAction(charIDToTypeID('Jmp '), undefined, DialogModes.NO);
    }

    static createLayerViaCopy() {
        executeAction(charIDToTypeID('Cp  '), undefined, DialogModes.NO);
        executeAction(charIDToTypeID('Pst '), undefined, DialogModes.NO);
    }

    static createLayerViaCut() {
        executeAction(charIDToTypeID('Cut '), undefined, DialogModes.NO);
        executeAction(charIDToTypeID('Pst '), undefined, DialogModes.NO);
    }
}
```

### 3.2 删除图层

```javascript
class LayerRemover {
    static deleteActiveLayer() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('Dlt '), desc, DialogModes.NO);
    }

    static deleteLayers(layerNames) {
        const doc = app.activeDocument;
        
        layerNames.forEach(name => {
            try {
                const layer = doc.layers.getByName(name);
                doc.activeLayer = layer;
                this.deleteActiveLayer();
            } catch (e) {
                // Layer not found
            }
        });
    }

    static deleteHiddenLayers() {
        const doc = app.activeDocument;
        const hiddenLayers = [];
        
        doc.layers.forEach(layer => {
            if (!layer.visible) {
                hiddenLayers.push(layer.name);
            }
        });
        
        this.deleteLayers(hiddenLayers);
    }

    static deleteEmptyLayers() {
        const doc = app.activeDocument;
        const emptyLayers = [];
        
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.NORMAL && 
                layer.bounds.width === 0 && 
                layer.bounds.height === 0) {
                emptyLayers.push(layer.name);
            }
        });
        
        this.deleteLayers(emptyLayers);
    }

    static deleteAdjustmentLayers() {
        const doc = app.activeDocument;
        const adjustmentLayers = [];
        
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.ADJUSTMENT) {
                adjustmentLayers.push(layer.name);
            }
        });
        
        this.deleteLayers(adjustmentLayers);
    }
}
```

---

## 四、图层选择与排序

### 4.1 图层选择

```javascript
class LayerSelector {
    static selectLayerByName(name) {
        const doc = app.activeDocument;
        
        try {
            doc.activeLayer = doc.layers.getByName(name);
            return true;
        } catch (e) {
            return false;
        }
    }

    static selectLayerByIndex(index) {
        const doc = app.activeDocument;
        
        if (index >= 0 && index < doc.layers.length) {
            doc.activeLayer = doc.layers[index];
            return true;
        }
        return false;
    }

    static selectAllLayers() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('All '));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('Slct'), desc, DialogModes.NO);
    }

    static selectVisibleLayers() {
        const doc = app.activeDocument;
        const visibleLayers = [];
        
        doc.layers.forEach(layer => {
            if (layer.visible) {
                visibleLayers.push(layer);
            }
        });
        
        if (visibleLayers.length > 0) {
            doc.activeLayer = visibleLayers[0];
            
            visibleLayers.slice(1).forEach(layer => {
                layer.selected = true;
            });
        }
    }

    static selectLayersByType(type) {
        const doc = app.activeDocument;
        const typeMap = {
            'pixel': LayerKind.NORMAL,
            'adjustment': LayerKind.ADJUSTMENT,
            'smartObject': LayerKind.SMARTOBJECT,
            'shape': LayerKind.SHAPE,
            'text': LayerKind.TEXT
        };
        
        const targetType = typeMap[type];
        const matchingLayers = [];
        
        doc.layers.forEach(layer => {
            if (layer.kind === targetType) {
                matchingLayers.push(layer);
            }
        });
        
        if (matchingLayers.length > 0) {
            doc.activeLayer = matchingLayers[0];
            
            matchingLayers.slice(1).forEach(layer => {
                layer.selected = true;
            });
        }
    }

    static selectLinkedLayers() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('SelL'), desc, DialogModes.NO);
    }

    static selectSimilarLayers() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('SelS'), desc, DialogModes.NO);
    }
}
```

### 4.2 图层排序

```javascript
class LayerSorter {
    static moveLayerToFront() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Drcn'), charIDToTypeID('Drcn'), charIDToTypeID('Frnt'));
        
        executeAction(charIDToTypeID('Mov '), desc, DialogModes.NO);
    }

    static moveLayerToBack() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Drcn'), charIDToTypeID('Drcn'), charIDToTypeID('Back'));
        
        executeAction(charIDToTypeID('Mov '), desc, DialogModes.NO);
    }

    static moveLayerUp() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Drcn'), charIDToTypeID('Drcn'), charIDToTypeID('Up  '));
        
        executeAction(charIDToTypeID('Mov '), desc, DialogModes.NO);
    }

    static moveLayerDown() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Drcn'), charIDToTypeID('Drcn'), charIDToTypeID('Down'));
        
        executeAction(charIDToTypeID('Mov '), desc, DialogModes.NO);
    }

    static moveLayerToIndex(index) {
        const doc = app.activeDocument;
        const activeLayer = doc.activeLayer;
        
        if (index >= 0 && index < doc.layers.length) {
            const targetLayer = doc.layers[index];
            
            if (index > doc.layers.getIndex(activeLayer)) {
                activeLayer.move(targetLayer, ElementPlacement.PLACEAFTER);
            } else {
                activeLayer.move(targetLayer, ElementPlacement.PLACEBEFORE);
            }
            
            return true;
        }
        return false;
    }

    static reorderLayers(order) {
        const doc = app.activeDocument;
        
        order.forEach((layerName, index) => {
            try {
                const layer = doc.layers.getByName(layerName);
                this.moveLayerToIndex(index);
            } catch (e) {
                // Layer not found
            }
        });
    }

    static reverseLayerOrder() {
        const doc = app.activeDocument;
        const layerNames = [];
        
        doc.layers.forEach(layer => {
            layerNames.push(layer.name);
        });
        
        this.reorderLayers(layerNames.reverse());
    }

    static sortLayersByName() {
        const doc = app.activeDocument;
        const layerNames = [];
        
        doc.layers.forEach(layer => {
            layerNames.push(layer.name);
        });
        
        layerNames.sort();
        this.reorderLayers(layerNames);
    }
}
```

---

## 五、图层变换操作

### 5.1 自由变换

```javascript
class LayerTransform {
    static freeTransform() {
        executeAction(charIDToTypeID('FrTr'), undefined, DialogModes.NO);
    }

    static transformAgain() {
        executeAction(charIDToTypeID('Trns'), undefined, DialogModes.NO);
    }

    static transformAgainCopy() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Cp  '), true);
        
        executeAction(charIDToTypeID('Trns'), desc, DialogModes.NO);
    }

    static scale(widthPercent, heightPercent, anchor = 'center') {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Prc'), widthPercent);
        desc.putUnitDouble(charIDToTypeID('Hght'), charIDToTypeID('#Prc'), heightPercent);
        
        executeAction(charIDToTypeID('Sc  '), desc, DialogModes.NO);
    }

    static scaleProportionally(percent) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Prc'), percent);
        desc.putUnitDouble(charIDToTypeID('Hght'), charIDToTypeID('#Prc'), percent);
        
        executeAction(charIDToTypeID('Sc  '), desc, DialogModes.NO);
    }

    static rotate(angle) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('#Ang'), angle);
        
        executeAction(charIDToTypeID('Rot '), desc, DialogModes.NO);
    }

    static rotate180() {
        this.rotate(180);
    }

    static rotate90CW() {
        this.rotate(90);
    }

    static rotate90CCW() {
        this.rotate(-90);
    }

    static skew(horizontalAngle, verticalAngle) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Ang'), horizontalAngle);
        desc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Ang'), verticalAngle);
        
        executeAction(charIDToTypeID('Sk  '), desc, DialogModes.NO);
    }

    static flipHorizontal() {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('FlpH'), charIDToTypeID('FlpH'), charIDToTypeID('Flip'));
        
        executeAction(charIDToTypeID('FlpH'), desc, DialogModes.NO);
    }

    static flipVertical() {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('FlpV'), charIDToTypeID('FlpV'), charIDToTypeID('Flip'));
        
        executeAction(charIDToTypeID('FlpV'), desc, DialogModes.NO);
    }

    static move(x, y) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('TrX '), charIDToTypeID('#Pxl'), x);
        desc.putUnitDouble(charIDToTypeID('TrY '), charIDToTypeID('#Pxl'), y);
        
        executeAction(charIDToTypeID('Trnf'), desc, DialogModes.NO);
    }

    static setPosition(x, y) {
        const doc = app.activeDocument;
        const layer = doc.activeLayer;
        
        layer.translate(x - layer.position[0], y - layer.position[1]);
    }
}
```

### 5.2 对齐与分布

```javascript
class LayerAligner {
    static alignTopEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), charIDToTypeID('Top '));
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }

    static alignVerticalCenters() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), charIDToTypeID('VCnt'));
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }

    static alignBottomEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), charIDToTypeID('Btom'));
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }

    static alignLeftEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), charIDToTypeID('Left'));
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }

    static alignHorizontalCenters() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), charIDToTypeID('HCnt'));
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }

    static alignRightEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), charIDToTypeID('Rght'));
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }

    static distributeTopEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Dstr'), charIDToTypeID('Dstr'), charIDToTypeID('Top '));
        
        executeAction(charIDToTypeID('Dstr'), desc, DialogModes.NO);
    }

    static distributeVerticalCenters() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Dstr'), charIDToTypeID('Dstr'), charIDToTypeID('VCnt'));
        
        executeAction(charIDToTypeID('Dstr'), desc, DialogModes.NO);
    }

    static distributeBottomEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Dstr'), charIDToTypeID('Dstr'), charIDToTypeID('Btom'));
        
        executeAction(charIDToTypeID('Dstr'), desc, DialogModes.NO);
    }

    static distributeLeftEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Dstr'), charIDToTypeID('Dstr'), charIDToTypeID('Left'));
        
        executeAction(charIDToTypeID('Dstr'), desc, DialogModes.NO);
    }

    static distributeHorizontalCenters() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Dstr'), charIDToTypeID('Dstr'), charIDToTypeID('HCnt'));
        
        executeAction(charIDToTypeID('Dstr'), desc, DialogModes.NO);
    }

    static distributeRightEdges() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Dstr'), charIDToTypeID('Dstr'), charIDToTypeID('Rght'));
        
        executeAction(charIDToTypeID('Dstr'), desc, DialogModes.NO);
    }

    static alignToCanvas(alignment) {
        const alignMap = {
            'top': charIDToTypeID('Top '),
            'bottom': charIDToTypeID('Btom'),
            'left': charIDToTypeID('Left'),
            'right': charIDToTypeID('Rght'),
            'center': charIDToTypeID('Cntr')
        };
        
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putEnumerated(charIDToTypeID('Algn'), charIDToTypeID('Algn'), alignMap[alignment]);
        
        executeAction(charIDToTypeID('Algn'), desc, DialogModes.NO);
    }
}
```

---

## 六、图层属性与样式

### 6.1 图层属性操作

```javascript
class LayerPropertiesManager {
    static setOpacity(opacity) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putUnitDouble(charIDToTypeID('Opct'), charIDToTypeID('#Prc'), opacity);
        
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

    static setBlendMode(mode) {
        const modeMap = {
            'normal': charIDToTypeID('Nrml'),
            'dissolve': charIDToTypeID('Dssl'),
            'darken': charIDToTypeID('Drkn'),
            'multiply': charIDToTypeID('Mltp'),
            'colorBurn': charIDToTypeID('ClrB'),
            'linearBurn': charIDToTypeID('LnBr'),
            'darkerColor': charIDToTypeID('DrkC'),
            'lighten': charIDToTypeID('Lght'),
            'screen': charIDToTypeID('Scrn'),
            'colorDodge': charIDToTypeID('ClrD'),
            'linearDodge': charIDToTypeID('LnDd'),
            'lighterColor': charIDToTypeID('LgtC'),
            'overlay': charIDToTypeID('Ovrl'),
            'softLight': charIDToTypeID('SftL'),
            'hardLight': charIDToTypeID('HrdL'),
            'vividLight': charIDToTypeID('VvdL'),
            'linearLight': charIDToTypeID('LnLt'),
            'pinLight': charIDToTypeID('PinL'),
            'hardMix': charIDToTypeID('HrdM'),
            'difference': charIDToTypeID('Dffr'),
            'exclusion': charIDToTypeID('Excl'),
            'subtract': charIDToTypeID('Sbtr'),
            'divide': charIDToTypeID('Dvd '),
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

    static setLayerName(name) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putString(charIDToTypeID('Nm  '), name);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static toggleVisibility() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('Vsbl'), desc, DialogModes.NO);
    }

    static setVisibility(visible) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Vsbl'), visible);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static toggleLock() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('Lck '), desc, DialogModes.NO);
    }

    static setLock(locked) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Lck '), locked);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

### 6.2 图层样式管理

```javascript
class LayerStyleManager {
    static copyLayerStyle() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('CpLS'), desc, DialogModes.NO);
    }

    static pasteLayerStyle() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('PstS'), desc, DialogModes.NO);
    }

    static pasteLayerStyleToLinked() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('PstL'), desc, DialogModes.NO);
    }

    static clearLayerStyle() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('ClrS'), desc, DialogModes.NO);
    }

    static saveLayerStyle(name) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putString(charIDToTypeID('Nm  '), name);
        
        executeAction(charIDToTypeID('SavS'), desc, DialogModes.NO);
    }

    static loadLayerStyle(name) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        const styleRef = new ActionReference();
        styleRef.putName(charIDToTypeID('LyrS'), name);
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putReference(charIDToTypeID('Usng'), styleRef);
        
        executeAction(charIDToTypeID('LdLS'), desc, DialogModes.NO);
    }

    static addDropShadow(options = {}) {
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
        if (options.size !== undefined) {
            shadowDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        
        styleDesc.putObject(charIDToTypeID('Sd  '), charIDToTypeID('Sd  '), shadowDesc);
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
        
        styleDesc.putObject(charIDToTypeID('OtGl'), charIDToTypeID('OtGl'), glowDesc);
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
        
        if (options.size !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Sz  '), charIDToTypeID('#Pxl'), options.size);
        }
        if (options.depth !== undefined) {
            bevelDesc.putUnitDouble(charIDToTypeID('Dpth'), charIDToTypeID('#Prc'), options.depth);
        }
        
        styleDesc.putObject(charIDToTypeID('Bvl '), charIDToTypeID('Bvl '), bevelDesc);
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

## 七、图层组管理

### 7.1 创建与编辑图层组

```javascript
class LayerGroupManager {
    static createGroup(name = 'Group') {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Grp '));
        desc.putString(charIDToTypeID('Nm  '), name);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static createGroupFromSelection(name = 'Group') {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Grp '));
        desc.putString(charIDToTypeID('Nm  '), name);
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static deleteGroup() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        executeAction(charIDToTypeID('Dlt '), desc, DialogModes.NO);
    }

    static deleteGroupWithContent() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        desc.putBoolean(charIDToTypeID('Cnts'), true);
        
        executeAction(charIDToTypeID('Dlt '), desc, DialogModes.NO);
    }

    static deleteEmptyGroups() {
        const doc = app.activeDocument;
        const emptyGroups = [];
        
        doc.layers.forEach(layer => {
            if (layer.typename === 'LayerSet' && layer.layers.length === 0) {
                emptyGroups.push(layer.name);
            }
        });
        
        emptyGroups.forEach(name => {
            try {
                const group = doc.layers.getByName(name);
                doc.activeLayer = group;
                this.deleteGroup();
            } catch (e) {
                // Group not found
            }
        });
    }

    static setGroupName(name) {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        desc.putString(charIDToTypeID('Nm  '), name);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static toggleGroupVisibility() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        executeAction(charIDToTypeID('Vsbl'), desc, DialogModes.NO);
    }

    static expandGroup() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        desc.putBoolean(charIDToTypeID('Expd'), true);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static collapseGroup() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        desc.putBoolean(charIDToTypeID('Expd'), false);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static expandAllGroups() {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.typename === 'LayerSet') {
                doc.activeLayer = layer;
                this.expandGroup();
            }
        });
    }

    static collapseAllGroups() {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.typename === 'LayerSet') {
                doc.activeLayer = layer;
                this.collapseGroup();
            }
        });
    }
}
```

### 7.2 图层与组的交互

```javascript
class LayerGroupInteraction {
    static addLayersToGroup(groupName, layerNames) {
        const doc = app.activeDocument;
        
        try {
            const group = doc.layers.getByName(groupName);
            
            layerNames.forEach(name => {
                try {
                    const layer = doc.layers.getByName(name);
                    layer.move(group, ElementPlacement.PLACEINSIDE);
                } catch (e) {
                    // Layer not found
                }
            });
        } catch (e) {
            // Group not found
        }
    }

    static removeLayerFromGroup(layerName) {
        const doc = app.activeDocument;
        
        try {
            const layer = doc.layers.getByName(layerName);
            
            if (layer.parent && layer.parent.typename === 'LayerSet') {
                const parentIndex = doc.layers.getIndex(layer.parent);
                layer.move(doc.layers[parentIndex], ElementPlacement.PLACEAFTER);
            }
        } catch (e) {
            // Layer not found
        }
    }

    static moveGroupUp() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        desc.putEnumerated(charIDToTypeID('Drcn'), charIDToTypeID('Drcn'), charIDToTypeID('Up  '));
        
        executeAction(charIDToTypeID('Mov '), desc, DialogModes.NO);
    }

    static moveGroupDown() {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        desc.putEnumerated(charIDToTypeID('Drcn'), charIDToTypeID('Drcn'), charIDToTypeID('Down'));
        
        executeAction(charIDToTypeID('Mov '), desc, DialogModes.NO);
    }

    static selectAllLayersInGroup(groupName) {
        const doc = app.activeDocument;
        
        try {
            const group = doc.layers.getByName(groupName);
            
            if (group.layers.length > 0) {
                doc.activeLayer = group.layers[0];
                
                for (let i = 1; i < group.layers.length; i++) {
                    group.layers[i].selected = true;
                }
            }
        } catch (e) {
            // Group not found
        }
    }

    static applyLayerStyleToGroup(layerStyle) {
        const desc = new ActionDescriptor();
        const groupRef = new ActionReference();
        groupRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), groupRef);
        
        const styleRef = new ActionReference();
        styleRef.putName(charIDToTypeID('LyrS'), layerStyle);
        
        desc.putReference(charIDToTypeID('Usng'), styleRef);
        
        executeAction(charIDToTypeID('LdLS'), desc, DialogModes.NO);
    }
}
```

---

## 八、智能对象详解

### 8.1 创建智能对象

```javascript
class SmartObjectManager {
    static createFromFile(filePath) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Smar'));
        
        const fileRef = new ActionReference();
        fileRef.putPath(charIDToTypeID('null'), filePath);
        
        desc.putReference(charIDToTypeID('null'), fileRef);
        
        executeAction(charIDToTypeID('Plc '), desc, DialogModes.NO);
    }

    static createFromLayer() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('MkSO'), desc, DialogModes.NO);
    }

    static createFromLayers(layerNames) {
        const doc = app.activeDocument;
        
        LayerSelector.selectLayersByType('pixel');
        this.createFromLayer();
    }

    static createLinkedSmartObject(filePath) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Smar'));
        
        const fileRef = new ActionReference();
        fileRef.putPath(charIDToTypeID('null'), filePath);
        
        desc.putReference(charIDToTypeID('null'), fileRef);
        desc.putBoolean(charIDToTypeID('Lnkd'), true);
        
        executeAction(charIDToTypeID('Plc '), desc, DialogModes.NO);
    }

    static convertToSmartObject() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('CnvS'), desc, DialogModes.NO);
    }
}
```

### 8.2 编辑智能对象

```javascript
class SmartObjectEditor {
    static editContents() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('EdtS'), desc, DialogModes.NO);
    }

    static updateContents() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('Updt'), desc, DialogModes.NO);
    }

    static replaceContents(filePath) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const fileRef = new ActionReference();
        fileRef.putPath(charIDToTypeID('null'), filePath);
        
        desc.putReference(charIDToTypeID('Usng'), fileRef);
        
        executeAction(charIDToTypeID('Rplc'), desc, DialogModes.NO);
    }

    static exportContents(outputPath) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const pathDesc = new ActionDescriptor();
        pathDesc.putPath(charIDToTypeID('null'), outputPath);
        
        desc.putObject(charIDToTypeID('T   '), charIDToTypeID('Pth '), pathDesc);
        
        executeAction(charIDToTypeID('ExpS'), desc, DialogModes.NO);
    }

    static embedLinked() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('Embd'), desc, DialogModes.NO);
    }

    static rasterize() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('Rstr'), desc, DialogModes.NO);
    }
}
```

---

## 九、调整图层详解

### 9.1 调整图层类型

```javascript
class AdjustmentLayerTypes {
    static get TYPES() {
        return {
            LEVELS: {
                name: '色阶',
                charID: charIDToTypeID('Levl'),
                description: '调整图像的明暗对比度',
                uses: ['基础校色', '对比度调整']
            },
            CURVES: {
                name: '曲线',
                charID: charIDToTypeID('Crvs'),
                description: '精确调整图像色调曲线',
                uses: ['精细校色', '色调控制']
            },
            BRIGHTNESS_CONTRAST: {
                name: '亮度/对比度',
                charID: charIDToTypeID('BrCn'),
                description: '简单调整亮度和对比度',
                uses: ['快速调整', '基础校正']
            },
            COLOR_BALANCE: {
                name: '色彩平衡',
                charID: charIDToTypeID('ClrB'),
                description: '调整阴影、中间调、高光的色彩',
                uses: ['色彩校正', '色调调整']
            },
            HUE_SATURATION: {
                name: '色相/饱和度',
                charID: charIDToTypeID('HueS'),
                description: '调整色相、饱和度和明度',
                uses: ['色彩调整', '单色效果']
            },
            SELECTIVE_COLOR: {
                name: '可选颜色',
                charID: charIDToTypeID('SlCt'),
                description: '调整特定颜色的CMYK值',
                uses: ['专业校色', '色彩微调']
            },
            CHANNEL_MIXER: {
                name: '通道混合器',
                charID: charIDToTypeID('Chnl'),
                description: '调整颜色通道的混合比例',
                uses: ['黑白转换', '通道调整']
            },
            GRADIENT_MAP: {
                name: '渐变映射',
                charID: charIDToTypeID('GrdM'),
                description: '将渐变应用到图像上',
                uses: ['创意调色', '色调映射']
            },
            PHOTO_FILTER: {
                name: '照片滤镜',
                charID: charIDToTypeID('PhFl'),
                description: '模拟滤镜效果',
                uses: ['色彩校正', '色调调整']
            },
            INVERT: {
                name: '反相',
                charID: charIDToTypeID('Invr'),
                description: '反转图像颜色',
                uses: ['创意效果', '蒙版制作']
            },
            POSTERIZE: {
                name: '阈值',
                charID: charIDToTypeID('Pstr'),
                description: '减少图像色调级数',
                uses: ['海报效果', '色调分离']
            },
            THRESHOLD: {
                name: '阈值',
                charID: charIDToTypeID('Thrs'),
                description: '将图像转换为黑白',
                uses: ['高对比度效果', '蒙版制作']
            }
        };
    }

    static create(type, options = {}) {
        const typeInfo = this.TYPES[type.toUpperCase()];
        if (!typeInfo) return false;
        
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), typeInfo.charID);
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        
        return true;
    }
}
```

### 9.2 调整图层操作

```javascript
class AdjustmentLayerManager {
    static createLevels(options = {}) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Levl'));
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        
        if (options.inputLevels) {
            this.setLevelsInput(options.inputLevels);
        }
        if (options.outputLevels) {
            this.setLevelsOutput(options.outputLevels);
        }
    }

    static setLevelsInput(levels) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const levelsDesc = new ActionDescriptor();
        levelsDesc.putUnitDouble(charIDToTypeID('Lef '), charIDToTypeID('#Pxl'), levels[0]);
        levelsDesc.putUnitDouble(charIDToTypeID('Mid '), charIDToTypeID('#Prc'), levels[1] * 100);
        levelsDesc.putUnitDouble(charIDToTypeID('Rght'), charIDToTypeID('#Pxl'), levels[2]);
        
        desc.putObject(charIDToTypeID('Levl'), charIDToTypeID('Levl'), levelsDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static setLevelsOutput(levels) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const levelsDesc = new ActionDescriptor();
        levelsDesc.putUnitDouble(charIDToTypeID('Min '), charIDToTypeID('#Pxl'), levels[0]);
        levelsDesc.putUnitDouble(charIDToTypeID('Max '), charIDToTypeID('#Pxl'), levels[1]);
        
        desc.putObject(charIDToTypeID('Levl'), charIDToTypeID('Levl'), levelsDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static createCurves(points = []) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('Crvs'));
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        
        if (points.length > 0) {
            this.setCurvesPoints(points);
        }
    }

    static setCurvesPoints(points) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const curveDesc = new ActionDescriptor();
        const curveList = new ActionList();
        
        points.forEach(point => {
            const pointDesc = new ActionDescriptor();
            pointDesc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('#Prc'), point.x);
            pointDesc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('#Prc'), point.y);
            curveList.putObject(charIDToTypeID('Pnt '), pointDesc);
        });
        
        curveDesc.putList(charIDToTypeID('Crv '), curveList);
        desc.putObject(charIDToTypeID('Crvs'), charIDToTypeID('Crvs'), curveDesc);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static createHueSaturation(options = {}) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('HueS'));
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
        
        if (options.hue !== undefined) {
            this.setHueSaturationValue('hue', options.hue);
        }
        if (options.saturation !== undefined) {
            this.setHueSaturationValue('saturation', options.saturation);
        }
        if (options.lightness !== undefined) {
            this.setHueSaturationValue('lightness', options.lightness);
        }
    }

    static setHueSaturationValue(type, value) {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        const typeMap = {
            'hue': charIDToTypeID('Hue '),
            'saturation': charIDToTypeID('Sat '),
            'lightness': charIDToTypeID('Lght')
        };
        
        desc.putUnitDouble(typeMap[type], charIDToTypeID('#Prc'), value);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static applyToSelection() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Sel '), true);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static applyToLayerBelow() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Clp '), true);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }

    static applyToAllLayers() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        desc.putBoolean(charIDToTypeID('Clp '), false);
        
        executeAction(charIDToTypeID('Set '), desc, DialogModes.NO);
    }
}
```

---

## 十、图层复合与状态管理

### 10.1 图层复合创建与管理

```javascript
class LayerCompManager {
    static createComp(name) {
        const desc = new ActionDescriptor();
        desc.putClass(charIDToTypeID('null'), charIDToTypeID('LayC'));
        desc.putString(charIDToTypeID('Nm  '), name);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }

    static deleteComp(name) {
        const desc = new ActionDescriptor();
        const compRef = new ActionReference();
        compRef.putName(charIDToTypeID('LayC'), name);
        
        desc.putReference(charIDToTypeID('null'), compRef);
        
        executeAction(charIDToTypeID('Dlt '), desc, DialogModes.NO);
    }

    static applyComp(name) {
        const desc = new ActionDescriptor();
        const compRef = new ActionReference();
        compRef.putName(charIDToTypeID('LayC'), name);
        
        desc.putReference(charIDToTypeID('null'), compRef);
        
        executeAction(charIDToTypeID('Apply'), desc, DialogModes.NO);
    }

    static updateComp(name) {
        const desc = new ActionDescriptor();
        const compRef = new ActionReference();
        compRef.putName(charIDToTypeID('LayC'), name);
        
        desc.putReference(charIDToTypeID('null'), compRef);
        
        executeAction(charIDToTypeID('Updt'), desc, DialogModes.NO);
    }

    static duplicateComp(name, newName) {
        const desc = new ActionDescriptor();
        const compRef = new ActionReference();
        compRef.putName(charIDToTypeID('LayC'), name);
        
        desc.putReference(charIDToTypeID('null'), compRef);
        desc.putString(charIDToTypeID('Nm  '), newName);
        
        executeAction(charIDToTypeID('Dplc'), desc, DialogModes.NO);
    }
}
```

### 10.2 图层状态管理

```javascript
class LayerStateManager {
    constructor() {
        this.states = [];
    }

    saveState(name) {
        const state = {
            name: name,
            layers: [],
            timestamp: new Date().getTime()
        };
        
        const doc = app.activeDocument;
        doc.layers.forEach(layer => {
            state.layers.push({
                name: layer.name,
                visible: layer.visible,
                opacity: layer.opacity,
                blendMode: layer.blendMode,
                locked: layer.locked
            });
        });
        
        this.states.push(state);
        return state;
    }

    restoreState(name) {
        const state = this.states.find(s => s.name === name);
        if (!state) return false;
        
        const doc = app.activeDocument;
        
        state.layers.forEach(layerState => {
            try {
                const layer = doc.layers.getByName(layerState.name);
                layer.visible = layerState.visible;
                layer.opacity = layerState.opacity;
                layer.blendMode = layerState.blendMode;
                layer.locked = layerState.locked;
            } catch (e) {
                // Layer not found
            }
        });
        
        return true;
    }

    clearAllStates() {
        this.states = [];
    }

    listStates() {
        return this.states.map(s => ({
            name: s.name,
            timestamp: s.timestamp,
            layerCount: s.layers.length
        }));
    }
}
```

---

## 十一、图层自动化API

### 11.1 批量图层操作

```javascript
class BatchLayerProcessor {
    static batchCreateLayers(count, options = {}) {
        for (let i = 0; i < count; i++) {
            LayerCreator.createPixelLayer(options.name || `Layer ${i + 1}`);
        }
    }

    static batchSetOpacity(layers, opacity) {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            LayerPropertiesManager.setOpacity(opacity);
        });
    }

    static batchSetBlendMode(layers, mode) {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            LayerPropertiesManager.setBlendMode(mode);
        });
    }

    static batchTransform(layers, transformFn) {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            transformFn();
        });
    }

    static batchRenameLayers(pattern) {
        const doc = app.activeDocument;
        
        doc.layers.forEach((layer, index) => {
            const newName = pattern.replace(/\{index\}/g, index + 1);
            app.activeDocument.activeLayer = layer;
            LayerPropertiesManager.setLayerName(newName);
        });
    }

    static batchAddAdjustmentLayers(types) {
        types.forEach(type => {
            AdjustmentLayerTypes.create(type);
        });
    }

    static batchCreateGroups(groupNames) {
        groupNames.forEach(name => {
            LayerGroupManager.createGroup(name);
        });
    }

    static batchConvertToSmartObjects(layers) {
        layers.forEach(layer => {
            app.activeDocument.activeLayer = layer;
            SmartObjectManager.convertToSmartObject();
        });
    }
}
```

### 11.2 图层数据导出

```javascript
class LayerDataExporter {
    static exportLayerInfo(format = 'json') {
        const doc = app.activeDocument;
        const layerInfo = [];
        
        doc.layers.forEach(layer => {
            layerInfo.push({
                name: layer.name,
                type: layer.kind.toString(),
                visible: layer.visible,
                opacity: layer.opacity,
                fillOpacity: layer.fillOpacity,
                blendMode: layer.blendMode,
                locked: layer.locked,
                hasMask: layer.masks.length > 0,
                hasEffects: layer.effects.length > 0,
                bounds: {
                    top: layer.bounds[0],
                    left: layer.bounds[1],
                    bottom: layer.bounds[2],
                    right: layer.bounds[3]
                },
                position: {
                    x: layer.position[0],
                    y: layer.position[1]
                }
            });
        });
        
        if (format === 'json') {
            return JSON.stringify(layerInfo, null, 2);
        } else if (format === 'csv') {
            const headers = ['Name', 'Type', 'Visible', 'Opacity', 'BlendMode'];
            const rows = layerInfo.map(l => [l.name, l.type, l.visible, l.opacity, l.blendMode]);
            return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
        }
        
        return layerInfo;
    }

    static exportLayerNames() {
        const doc = app.activeDocument;
        return doc.layers.map(layer => layer.name);
    }

    static exportLayerStructure() {
        const doc = app.activeDocument;
        
        function buildStructure(layer) {
            const node = {
                name: layer.name,
                type: layer.kind.toString()
            };
            
            if (layer.typename === 'LayerSet') {
                node.children = [];
                layer.layers.forEach(child => {
                    node.children.push(buildStructure(child));
                });
            }
            
            return node;
        }
        
        const structure = [];
        doc.layers.forEach(layer => {
            structure.push(buildStructure(layer));
        });
        
        return JSON.stringify(structure, null, 2);
    }
}
```

---

## 十二、故障排查与性能优化

### 12.1 常见问题排查

```javascript
class LayerTroubleshooter {
    static checkLayerIssues() {
        const issues = [];
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.NORMAL && 
                layer.bounds.width === 0 && 
                layer.bounds.height === 0) {
                issues.push({
                    type: 'empty_layer',
                    layer: layer.name,
                    message: '图层为空，无像素内容'
                });
            }
            
            if (layer.opacity === 0 && layer.visible) {
                issues.push({
                    type: 'invisible_opacity',
                    layer: layer.name,
                    message: '图层可见但透明度为0'
                });
            }
            
            if (layer.effects.length > 10) {
                issues.push({
                    type: 'too_many_effects',
                    layer: layer.name,
                    message: '图层效果过多，建议优化'
                });
            }
        });
        
        return issues;
    }

    static fixEmptyLayers() {
        LayerRemover.deleteEmptyLayers();
    }

    static detectMissingFonts() {
        const issues = [];
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.TEXT) {
                try {
                    const textItem = layer.textItem;
                } catch (e) {
                    issues.push({
                        type: 'missing_font',
                        layer: layer.name,
                        message: '文字图层缺少字体'
                    });
                }
            }
        });
        
        return issues;
    }

    static detectBrokenSmartObjects() {
        const issues = [];
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.SMARTOBJECT) {
                try {
                    const embedded = layer.smartObjectContents;
                } catch (e) {
                    issues.push({
                        type: 'broken_smart_object',
                        layer: layer.name,
                        message: '智能对象链接已损坏'
                    });
                }
            }
        });
        
        return issues;
    }
}
```

### 12.2 性能优化策略

```javascript
class LayerPerformanceOptimizer {
    static mergeVisibleLayers() {
        const desc = new ActionDescriptor();
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        executeAction(charIDToTypeID('MrgV'), desc, DialogModes.NO);
    }

    static flattenImage() {
        executeAction(charIDToTypeID('Fltt'), undefined, DialogModes.NO);
    }

    static reduceLayerCount(maxCount = 50) {
        const doc = app.activeDocument;
        
        if (doc.layers.length > maxCount) {
            const layersToMerge = doc.layers.length - maxCount;
            
            LayerSelector.selectAllLayers();
            this.mergeVisibleLayers();
        }
    }

    static disableEffectsForPreview() {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            layer.effects.forEach(effect => {
                effect.enabled = false;
            });
        });
    }

    static enableAllEffects() {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            layer.effects.forEach(effect => {
                effect.enabled = true;
            });
        });
    }

    static rasterizeSmartObjects() {
        const doc = app.activeDocument;
        
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.SMARTOBJECT) {
                app.activeDocument.activeLayer = layer;
                SmartObjectEditor.rasterize();
            }
        });
    }

    static optimizeLayerStack() {
        this.deleteHiddenLayers();
        this.deleteEmptyLayers();
        this.disableEffectsForPreview();
    }
}
```

### 12.3 最佳实践指南

```javascript
class LayerBestPractices {
    static get GUIDELINES() {
        return {
            ORGANIZATION: [
                '使用图层组组织相关图层',
                '为图层命名清晰的描述性名称',
                '保持图层顺序逻辑清晰',
                '定期清理空图层和隐藏图层'
            ],
            PERFORMANCE: [
                '避免过多调整图层叠加',
                '使用智能对象减少重复渲染',
                '预览时禁用复杂效果',
                '定期合并可见图层'
            ],
            NON_DESTRUCTIVE: [
                '优先使用调整图层而非直接调整',
                '使用蒙版而非删除像素',
                '使用智能对象保留原始数据',
                '使用图层复合保存不同版本'
            ],
            COLLABORATION: [
                '使用一致的命名规范',
                '记录图层用途注释',
                '使用图层复合展示不同方案',
                '保持文件结构清晰'
            ]
        };
    }

    static validateLayerStructure(doc) {
        const validation = {
            passed: [],
            warnings: [],
            errors: []
        };
        
        if (doc.layers.length > 100) {
            validation.warnings.push({
                message: '图层数量超过100，建议分组或合并'
            });
        }
        
        let adjustmentLayerCount = 0;
        doc.layers.forEach(layer => {
            if (layer.kind === LayerKind.ADJUSTMENT) {
                adjustmentLayerCount++;
            }
        });
        
        if (adjustmentLayerCount > 10) {
            validation.warnings.push({
                message: '调整图层数量超过10，建议优化'
            });
        }
        
        return validation;
    }
}
```

---

## 附录：快捷键速查

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Shift+N | 新建图层 |
| Ctrl+J | 通过拷贝创建图层 |
| Ctrl+Shift+J | 通过剪切创建图层 |
| Ctrl+D | 取消选择 |
| Ctrl+A | 选择全部图层 |
| Ctrl+G | 新建图层组 |
| Ctrl+Shift+G | 取消图层组 |
| Ctrl+E | 向下合并图层 |
| Ctrl+Shift+E | 合并可见图层 |
| Ctrl+Alt+Shift+E | 盖印可见图层 |
| Ctrl+T | 自由变换 |
| Ctrl+Shift+T | 再次变换 |
| Ctrl+Alt+Shift+T | 再次变换并复制 |
| Ctrl+[ | 图层下移 |
| Ctrl+] | 图层上移 |
| Ctrl+Shift+[ | 图层移至底层 |
| Ctrl+Shift+] | 图层移至顶层 |
| Ctrl+; | 隐藏/显示图层 |
| Alt+Ctrl+; | 锁定/解锁图层 |