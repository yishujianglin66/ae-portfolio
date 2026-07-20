# Photoshop 色彩校正与调整深度研究报告

> 适用版本：Adobe Photoshop 2026 | 更新日期：2026-07-14 | 分类：Photoshop知识库

---

## 目录

- [一、色彩校正理论基础](#一色彩校正理论基础)
- [二、色彩空间与转换](#二色彩空间与转换)
- [三、直方图分析与应用](#三直方图分析与应用)
- [四、色阶调整技术](#四色阶调整技术)
- [五、曲线调整技术](#五曲线调整技术)
- [六、色彩平衡调整](#六色彩平衡调整)
- [七、色相/饱和度调整](#七色相饱和度调整)
- [八、选择性色彩调整](#八选择性色彩调整)
- [九、照片滤镜与渐变映射](#九照片滤镜与渐变映射)
- [十、调整图层技术](#十调整图层技术)
- [十一、自动化色彩校正API](#十一自动化色彩校正api)
- [十二、学术研究与论文索引](#十二学术研究与论文索引)

---

## 一、色彩校正理论基础

### 1.1 色彩感知模型

```javascript
class ColorPerceptionModel {
    constructor() {
        this.coneResponses = {
            S: 0,
            M: 0,
            L: 0
        };
        this.opponentChannels = {
            RG: 0,
            BY: 0,
            Luminance: 0
        };
    }
    
    calculateConeResponses(rgb) {
        const [r, g, b] = rgb;
        
        this.coneResponses.L = 0.642 * r + 0.248 * g + 0.078 * b;
        this.coneResponses.M = 0.184 * r + 0.528 * g + 0.278 * b;
        this.coneResponses.S = 0.002 * r + 0.023 * g + 0.967 * b;
        
        return this.coneResponses;
    }
    
    calculateOpponentChannels() {
        const { L, M, S } = this.coneResponses;
        
        this.opponentChannels.Luminance = (L + M) / 2;
        this.opponentChannels.RG = L - M;
        this.opponentChannels.BY = (L + M) / 2 - S;
        
        return this.opponentChannels;
    }
}
```

### 1.2 色彩误差模型

```javascript
class ColorErrorModel {
    static calculateDeltaE(lab1, lab2) {
        const [L1, a1, b1] = lab1;
        const [L2, a2, b2] = lab2;
        
        const deltaL = L2 - L1;
        const deltaA = a2 - a1;
        const deltaB = b2 - b1;
        
        return Math.sqrt(deltaL * deltaL + deltaA * deltaA + deltaB * deltaB);
    }
    
    static calculateDeltaE2000(lab1, lab2) {
        const [L1, a1, b1] = lab1;
        const [L2, a2, b2] = lab2;
        
        const Lmean = (L1 + L2) / 2;
        
        const C1 = Math.sqrt(a1 * a1 + b1 * b1);
        const C2 = Math.sqrt(a2 * a2 + b2 * b2);
        const Cmean = (C1 + C2) / 2;
        
        const G = 0.5 * (1 - Math.sqrt(Cmean ** 7 / (Cmean ** 7 + 25 ** 7)));
        
        const a1Prime = a1 * (1 + G);
        const a2Prime = a2 * (1 + G);
        
        const C1Prime = Math.sqrt(a1Prime * a1Prime + b1 * b1);
        const C2Prime = Math.sqrt(a2Prime * a2Prime + b2 * b2);
        const CmeanPrime = (C1Prime + C2Prime) / 2;
        
        const h1Prime = Math.atan2(b1, a1Prime) * 180 / Math.PI;
        const h2Prime = Math.atan2(b2, a2Prime) * 180 / Math.PI;
        
        const deltaLPrime = L2 - L1;
        const deltaCPrime = C2Prime - C1Prime;
        
        let deltaHPrime;
        if (C1Prime * C2Prime === 0) {
            deltaHPrime = 0;
        } else {
            deltaHPrime = h2Prime - h1Prime;
            if (Math.abs(deltaHPrime) > 180) {
                deltaHPrime += deltaHPrime > 0 ? -360 : 360;
            }
        }
        
        const deltaHPrimeSquared = deltaHPrime * deltaHPrime;
        
        const SL = 1 + (0.015 * (Lmean - 50) * (Lmean - 50)) / 
                   Math.sqrt(20 + (Lmean - 50) * (Lmean - 50));
        
        const SC = 1 + 0.045 * CmeanPrime;
        
        const T = 1 - 0.17 * Math.cos(Math.PI * (h1Prime - 30) / 180) +
                  0.24 * Math.cos(Math.PI * 2 * h1Prime / 180) +
                  0.32 * Math.cos(Math.PI * (3 * h1Prime + 6) / 180) -
                  0.20 * Math.cos(Math.PI * (4 * h1Prime - 63) / 180);
        
        const SH = 1 + 0.015 * CmeanPrime * T;
        
        const deltaTheta = 30 * Math.exp(-((h1Prime - 275) / 25) ** 2);
        const RC = 2 * Math.sqrt(CmeanPrime ** 7 / (CmeanPrime ** 7 + 25 ** 7));
        const RT = -RC * Math.sin(Math.PI * 2 * deltaTheta / 180);
        
        const term1 = deltaLPrime / SL;
        const term2 = deltaCPrime / SC;
        const term3 = deltaHPrimeSquared / (SH * SH);
        const term4 = RT * deltaCPrime * deltaHPrime / (SC * SH);
        
        return Math.sqrt(term1 * term1 + term2 * term2 + term3 + term4);
    }
}
```

---

## 二、色彩空间与转换

### 2.1 色彩空间定义与特性

```javascript
class ColorSpaceSystem {
    COLOR_SPACES = {
        'sRGB': {
            name: 'sRGB',
            gamma: 2.2,
            whitePoint: [0.3127, 0.3290],
            primaries: {
                red: [0.64, 0.33],
                green: [0.30, 0.60],
                blue: [0.15, 0.06]
            },
            uses: ['web', 'computer display', 'digital photography']
        },
        'Adobe RGB': {
            name: 'Adobe RGB (1998)',
            gamma: 2.2,
            whitePoint: [0.3127, 0.3290],
            primaries: {
                red: [0.64, 0.33],
                green: [0.21, 0.71],
                blue: [0.15, 0.06]
            },
            uses: ['printing', 'professional photography']
        },
        'ProPhoto RGB': {
            name: 'ProPhoto RGB',
            gamma: 1.8,
            whitePoint: [0.3457, 0.3585],
            primaries: {
                red: [0.7347, 0.2653],
                green: [0.1596, 0.8404],
                blue: [0.0366, 0.0001]
            },
            uses: ['high-end photography', 'RAW processing']
        },
        'Lab': {
            name: 'CIE Lab',
            gamma: 1.0,
            whitePoint: [0.3127, 0.3290],
            description: '设备无关色彩空间',
            uses: ['color correction', 'color matching', 'image processing']
        },
        'CMYK': {
            name: 'CMYK',
            gamma: 1.0,
            description: '印刷色彩空间',
            uses: ['printing', 'commercial print']
        }
    };
    
    getColorSpace(name) {
        return this.COLOR_SPACES[name] || null;
    }
    
    convertRGBtoLab(rgb) {
        const [r, g, b] = rgb.map(x => x / 255);
        
        const linearRgb = rgb.map(x => {
            x = x / 255;
            return x > 0.04045 ? Math.pow((x + 0.055) / 1.055, 2.4) : x / 12.92;
        });
        
        const [lr, lg, lb] = linearRgb;
        
        const x = 0.4124 * lr + 0.3576 * lg + 0.1805 * lb;
        const y = 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
        const z = 0.0193 * lr + 0.1192 * lg + 0.9505 * lb;
        
        const xn = 0.95047;
        const yn = 1.0;
        const zn = 1.08883;
        
        const fx = x / xn > 0.008856 ? Math.pow(x / xn, 1/3) : 7.787 * (x / xn) + 16/116;
        const fy = y / yn > 0.008856 ? Math.pow(y / yn, 1/3) : 7.787 * (y / yn) + 16/116;
        const fz = z / zn > 0.008856 ? Math.pow(z / zn, 1/3) : 7.787 * (z / zn) + 16/116;
        
        const L = 116 * fy - 16;
        const a = 500 * (fx - fy);
        const b = 200 * (fy - fz);
        
        return [L, a, b];
    }
    
    convertLabtoRGB(lab) {
        const [L, a, b] = lab;
        
        const fy = (L + 16) / 116;
        const fx = a / 500 + fy;
        const fz = fy - b / 200;
        
        const xn = 0.95047;
        const yn = 1.0;
        const zn = 1.08883;
        
        const x = fx > 0.206893 ? fx * fx * fx * xn : (fx - 16/116) / 7.787 * xn;
        const y = fy > 0.206893 ? fy * fy * fy * yn : (fy - 16/116) / 7.787 * yn;
        const z = fz > 0.206893 ? fz * fz * fz * zn : (fz - 16/116) / 7.787 * zn;
        
        const lr = 3.2406 * x - 1.5372 * y - 0.4986 * z;
        const lg = -0.9689 * x + 1.8758 * y + 0.0415 * z;
        const lb = 0.0557 * x - 0.2040 * y + 1.0570 * z;
        
        const rgb = [lr, lg, lb].map(x => {
            x = x > 0.0031308 ? 1.055 * Math.pow(x, 1/2.4) - 0.055 : 12.92 * x;
            return Math.round(x * 255);
        });
        
        return rgb;
    }
}
```

### 2.2 ICC色彩管理

```javascript
class ICCProfileManager {
    constructor() {
        this.profiles = {};
    }
    
    loadProfile(filePath) {
        this.profiles[filePath] = {
            filePath: filePath,
            loaded: true,
            lastModified: new Date()
        };
        return this.profiles[filePath];
    }
    
    applyProfile(image, profile) {
        return image;
    }
    
    convertWithProfiles(image, sourceProfile, destinationProfile) {
        return image;
    }
}
```

---

## 三、直方图分析与应用

### 3.1 直方图计算模型

```javascript
class HistogramAnalyzer {
    static calculateHistogram(image) {
        const histogram = {
            r: new Array(256).fill(0),
            g: new Array(256).fill(0),
            b: new Array(256).fill(0),
            l: new Array(256).fill(0)
        };
        
        for (const pixel of image) {
            const [r, g, b] = pixel;
            const l = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
            
            histogram.r[r]++;
            histogram.g[g]++;
            histogram.b[b]++;
            histogram.l[l]++;
        }
        
        return histogram;
    }
    
    static analyzeHistogram(histogram) {
        const analysis = {
            peaks: [],
            shadows: 0,
            midtones: 0,
            highlights: 0,
            contrast: 'unknown',
            exposure: 'unknown',
            clipping: {
                shadows: false,
                highlights: false
            }
        };
        
        const totalPixels = histogram.l.reduce((a, b) => a + b, 0);
        
        analysis.shadows = histogram.l.slice(0, 64).reduce((a, b) => a + b, 0);
        analysis.midtones = histogram.l.slice(64, 192).reduce((a, b) => a + b, 0);
        analysis.highlights = histogram.l.slice(192, 256).reduce((a, b) => a + b, 0);
        
        analysis.clipping.shadows = histogram.l[0] > totalPixels * 0.01;
        analysis.clipping.highlights = histogram.l[255] > totalPixels * 0.01;
        
        if (analysis.shadows > totalPixels * 0.4) {
            analysis.exposure = 'underexposed';
        } else if (analysis.highlights > totalPixels * 0.4) {
            analysis.exposure = 'overexposed';
        } else {
            analysis.exposure = 'correct';
        }
        
        const range = this._findRange(histogram.l);
        if (range < 150) {
            analysis.contrast = 'low';
        } else if (range > 220) {
            analysis.contrast = 'high';
        } else {
            analysis.contrast = 'normal';
        }
        
        return analysis;
    }
    
    static _findRange(histogram) {
        let min = 0;
        while (min < 256 && histogram[min] === 0) min++;
        
        let max = 255;
        while (max >= 0 && histogram[max] === 0) max--;
        
        return max - min;
    }
    
    static generateCorrectionSuggestions(analysis) {
        const suggestions = [];
        
        if (analysis.exposure === 'underexposed') {
            suggestions.push('增加曝光补偿');
            suggestions.push('提亮阴影区域');
        } else if (analysis.exposure === 'overexposed') {
            suggestions.push('降低曝光补偿');
            suggestions.push('恢复高光细节');
        }
        
        if (analysis.contrast === 'low') {
            suggestions.push('增加对比度');
            suggestions.push('使用S曲线调整');
        } else if (analysis.contrast === 'high') {
            suggestions.push('降低对比度');
            suggestions.push('使用柔和曲线');
        }
        
        if (analysis.clipping.shadows) {
            suggestions.push('修复阴影死黑');
        }
        
        if (analysis.clipping.highlights) {
            suggestions.push('修复高光过曝');
        }
        
        return suggestions;
    }
}
```

---

## 四、色阶调整技术

### 4.1 色阶数学模型

```javascript
class LevelsAdjustment {
    constructor() {
        this.inputBlack = 0;
        this.inputWhite = 255;
        this.inputGray = 1.0;
        this.outputBlack = 0;
        this.outputWhite = 255;
    }
    
    apply(channel, pixel) {
        let val = pixel[channel];
        
        val = (val - this.inputBlack) / (this.inputWhite - this.inputBlack);
        
        if (this.inputGray !== 1.0) {
            val = Math.pow(val, 1 / this.inputGray);
        }
        
        val = val * (this.outputWhite - this.outputBlack) + this.outputBlack;
        
        return Math.round(Math.max(0, Math.min(255, val)));
    }
    
    applyToImage(image) {
        const result = [];
        
        for (const pixel of image) {
            const newPixel = [
                this.apply(0, pixel),
                this.apply(1, pixel),
                this.apply(2, pixel)
            ];
            result.push(newPixel);
        }
        
        return result;
    }
    
    setInputLevels(black, gray, white) {
        this.inputBlack = black;
        this.inputGray = gray;
        this.inputWhite = white;
    }
    
    setOutputLevels(black, white) {
        this.outputBlack = black;
        this.outputWhite = white;
    }
}
```

### 4.2 自动色阶算法

```javascript
class AutoLevels {
    static calculateLevels(image, clipPercent = 0.1) {
        const histogram = HistogramAnalyzer.calculateHistogram(image);
        const totalPixels = histogram.l.reduce((a, b) => a + b, 0);
        
        const clipCount = Math.floor(totalPixels * clipPercent / 100);
        
        let blackPoint = 0;
        let accumulated = 0;
        while (blackPoint < 256) {
            accumulated += histogram.l[blackPoint];
            if (accumulated > clipCount) break;
            blackPoint++;
        }
        
        let whitePoint = 255;
        accumulated = 0;
        while (whitePoint >= 0) {
            accumulated += histogram.l[whitePoint];
            if (accumulated > clipCount) break;
            whitePoint--;
        }
        
        const midPoint = (blackPoint + whitePoint) / 2;
        const grayValue = midPoint / 128;
        
        return {
            inputBlack: blackPoint,
            inputWhite: whitePoint,
            inputGray: grayValue,
            outputBlack: 0,
            outputWhite: 255
        };
    }
}
```

---

## 五、曲线调整技术

### 5.1 曲线数学模型

```javascript
class CurvesAdjustment {
    constructor() {
        this.points = [[0, 0], [255, 255]];
        this.smooth = false;
    }
    
    evaluate(x) {
        if (this.points.length < 2) return x;
        
        let i = 0;
        while (i < this.points.length - 1 && this.points[i + 1][0] < x) {
            i++;
        }
        
        if (i >= this.points.length - 1) {
            return this.points[this.points.length - 1][1];
        }
        
        const [x0, y0] = this.points[i];
        const [x1, y1] = this.points[i + 1];
        
        if (x0 === x1) return y0;
        
        const t = (x - x0) / (x1 - x0);
        
        if (this.smooth) {
            return this._cubicInterpolate(t, x0, x1, y0, y1);
        } else {
            return y0 + t * (y1 - y0);
        }
    }
    
    _cubicInterpolate(t, x0, x1, y0, y1) {
        const t2 = t * t;
        const t3 = t2 * t;
        
        const cp0 = x0 + (x1 - x0) * 0.33;
        const cp1 = x0 + (x1 - x0) * 0.66;
        
        return (2 * t3 - 3 * t2 + 1) * y0 +
               (-2 * t3 + 3 * t2) * y1 +
               (t3 - 2 * t2 + t) * (y0 + (y1 - y0) * 0.5) +
               (t3 - t2) * (y0 + (y1 - y0) * 0.5);
    }
    
    applyToChannel(image, channel) {
        const result = [];
        
        for (const pixel of image) {
            const newPixel = [...pixel];
            newPixel[channel] = Math.round(this.evaluate(pixel[channel]));
            result.push(newPixel);
        }
        
        return result;
    }
    
    applyToRGB(image) {
        let result = image;
        
        result = this.applyToChannel(result, 0);
        result = this.applyToChannel(result, 1);
        result = this.applyToChannel(result, 2);
        
        return result;
    }
    
    addPoint(x, y) {
        this.points.push([x, y]);
        this.points.sort((a, b) => a[0] - b[0]);
    }
    
    removePoint(index) {
        if (this.points.length > 2) {
            this.points.splice(index, 1);
        }
    }
}
```

### 5.2 曲线预设库

```javascript
class CurvesPresets {
    PRESETS = {
        's_curve': {
            name: 'S曲线',
            points: [[0, 20], [50, 45], [200, 210], [255, 235]],
            description: '增强对比度的经典曲线',
            uses: ['人像摄影', '风景摄影']
        },
        'contrast_high': {
            name: '高对比度',
            points: [[0, 0], [60, 40], [195, 215], [255, 255]],
            description: '大幅度增强画面对比度',
            uses: ['黑白摄影', '艺术效果']
        },
        'contrast_low': {
            name: '低对比度',
            points: [[0, 30], [128, 128], [255, 225]],
            description: '降低画面对比度',
            uses: ['梦幻效果', '回忆场景']
        },
        'cinematic': {
            name: '电影感',
            points: [[0, 0], [40, 25], [128, 115], [210, 225], [255, 245]],
            redPoints: [[0, 0], [128, 135], [255, 240]],
            bluePoints: [[0, 0], [128, 120], [255, 255]],
            description: '电影级色彩分离',
            uses: ['电影调色', '视频后期']
        },
        'fade': {
            name: '褪色',
            points: [[0, 20], [128, 135], [255, 230]],
            description: '复古褪色效果',
            uses: ['复古风格', '年代感']
        },
        'portrait': {
            name: '人像优化',
            points: [[0, 0], [80, 70], [180, 190], [255, 255]],
            redPoints: [[0, 0], [128, 130], [255, 255]],
            description: '提亮肤色，增强质感',
            uses: ['人像摄影', '婚纱摄影']
        }
    };
    
    getPreset(name) {
        return this.PRESETS[name] || null;
    }
    
    listPresets() {
        return Object.keys(this.PRESETS);
    }
}
```

---

## 六、色彩平衡调整

### 6.1 色彩平衡数学模型

```javascript
class ColorBalanceAdjustment {
    constructor() {
        this.shadows = [0, 0, 0];
        this.midtones = [0, 0, 0];
        this.highlights = [0, 0, 0];
        this.preserveLuminosity = true;
    }
    
    apply(pixel) {
        const [r, g, b] = pixel;
        const luma = 0.299 * r + 0.587 * g + 0.114 * b;
        
        let adjustment;
        
        if (luma < 85) {
            adjustment = this.shadows;
        } else if (luma > 170) {
            adjustment = this.highlights;
        } else {
            adjustment = this.midtones;
        }
        
        let newR = r + adjustment[0];
        let newG = g + adjustment[1];
        let newB = b + adjustment[2];
        
        if (this.preserveLuminosity) {
            const newLuma = 0.299 * newR + 0.587 * newG + 0.114 * newB;
            const lumaDiff = luma - newLuma;
            
            newR = Math.round(newR + lumaDiff);
            newG = Math.round(newG + lumaDiff);
            newB = Math.round(newB + lumaDiff);
        }
        
        return [
            Math.max(0, Math.min(255, newR)),
            Math.max(0, Math.min(255, newG)),
            Math.max(0, Math.min(255, newB))
        ];
    }
    
    applyToImage(image) {
        return image.map(pixel => this.apply(pixel));
    }
    
    setShadows(cyanRed, magentaGreen, yellowBlue) {
        this.shadows = [cyanRed, magentaGreen, yellowBlue];
    }
    
    setMidtones(cyanRed, magentaGreen, yellowBlue) {
        this.midtones = [cyanRed, magentaGreen, yellowBlue];
    }
    
    setHighlights(cyanRed, magentaGreen, yellowBlue) {
        this.highlights = [cyanRed, magentaGreen, yellowBlue];
    }
}
```

### 6.2 色彩平衡预设

```javascript
class ColorBalancePresets {
    PRESETS = {
        'cool_tone': {
            name: '冷色调',
            shadows: [0, 0, 30],
            midtones: [0, 0, 20],
            highlights: [-10, 0, 10],
            description: '整体偏蓝绿色调',
            uses: ['夜景', '科幻场景']
        },
        'warm_tone': {
            name: '暖色调',
            shadows: [30, 10, 0],
            midtones: [20, 10, 0],
            highlights: [10, 5, 0],
            description: '整体偏橙红色调',
            uses: ['日出日落', '温馨场景']
        },
        'cinematic_teal_orange': {
            name: '电影青橙',
            shadows: [-20, 10, 30],
            midtones: [-10, 5, 20],
            highlights: [30, 10, -20],
            description: '经典电影配色：阴影青，高光橙',
            uses: ['电影调色', '商业广告']
        },
        'cross_process': {
            name: '交叉冲洗',
            shadows: [20, -10, 30],
            midtones: [10, -5, 20],
            highlights: [-10, 10, -10],
            description: '模拟胶片交叉冲洗效果',
            uses: ['复古风格', '艺术摄影']
        },
        'neutral': {
            name: '中性',
            shadows: [0, 0, 0],
            midtones: [0, 0, 0],
            highlights: [0, 0, 0],
            description: '无色彩偏移',
            uses: ['校准', '基准']
        }
    };
    
    getPreset(name) {
        return this.PRESETS[name] || null;
    }
}
```

---

## 七、色相/饱和度调整

### 7.1 色相/饱和度数学模型

```javascript
class HueSaturationAdjustment {
    constructor() {
        this.hue = 0;
        this.saturation = 0;
        this.lightness = 0;
        this.colorize = false;
        this.targetColor = null;
    }
    
    apply(pixel) {
        let [r, g, b] = pixel.map(x => x / 255);
        
        let h, s, v;
        
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const diff = max - min;
        
        if (diff === 0) {
            h = 0;
            s = 0;
        } else {
            h = Math.atan2(Math.sqrt(3) * (g - b), 2 * r - g - b) * 180 / Math.PI;
            if (h < 0) h += 360;
            s = diff / max;
        }
        v = max;
        
        h += this.hue;
        if (h > 360) h -= 360;
        if (h < 0) h += 360;
        
        s = Math.max(0, Math.min(1, s + this.saturation / 100));
        
        v = Math.max(0, Math.min(1, v + this.lightness / 100));
        
        let newR, newG, newB;
        
        const c = v * s;
        const x = c * (1 - Math.abs((h / 60) % 2 - 1));
        const m = v - c;
        
        if (h >= 0 && h < 60) {
            newR = c; newG = x; newB = 0;
        } else if (h >= 60 && h < 120) {
            newR = x; newG = c; newB = 0;
        } else if (h >= 120 && h < 180) {
            newR = 0; newG = c; newB = x;
        } else if (h >= 180 && h < 240) {
            newR = 0; newG = x; newB = c;
        } else if (h >= 240 && h < 300) {
            newR = x; newG = 0; newB = c;
        } else {
            newR = c; newG = 0; newB = x;
        }
        
        newR = Math.round((newR + m) * 255);
        newG = Math.round((newG + m) * 255);
        newB = Math.round((newB + m) * 255);
        
        return [newR, newG, newB];
    }
    
    applyToImage(image) {
        return image.map(pixel => this.apply(pixel));
    }
    
    setHue(value) {
        this.hue = value;
    }
    
    setSaturation(value) {
        this.saturation = value;
    }
    
    setLightness(value) {
        this.lightness = value;
    }
}
```

### 7.2 饱和度调整策略

```javascript
class SaturationStrategy {
    static smartSaturation(image, targetSaturation) {
        const result = [];
        
        for (const pixel of image) {
            const [r, g, b] = pixel.map(x => x / 255);
            
            const max = Math.max(r, g, b);
            const min = Math.min(r, g, b);
            const currentSaturation = max === 0 ? 0 : (max - min) / max;
            
            const adjustment = (targetSaturation - currentSaturation) * 0.5;
            
            const gray = 0.299 * r + 0.587 * g + 0.114 * b;
            
            const newR = Math.round((gray + (r - gray) * (1 + adjustment)) * 255);
            const newG = Math.round((gray + (g - gray) * (1 + adjustment)) * 255);
            const newB = Math.round((gray + (b - gray) * (1 + adjustment)) * 255);
            
            result.push([
                Math.max(0, Math.min(255, newR)),
                Math.max(0, Math.min(255, newG)),
                Math.max(0, Math.min(255, newB))
            ]);
        }
        
        return result;
    }
}
```

---

## 八、选择性色彩调整

### 8.1 选择性色彩数学模型

```javascript
class SelectiveColorAdjustment {
    constructor() {
        this.colors = {
            red: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            yellow: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            green: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            cyan: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            blue: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            magenta: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            white: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            neutral: { cyan: 0, magenta: 0, yellow: 0, black: 0 },
            black: { cyan: 0, magenta: 0, yellow: 0, black: 0 }
        };
        this.mode = 'relative';
    }
    
    apply(pixel) {
        const [r, g, b] = pixel.map(x => x / 255);
        
        const colorClass = this._classifyColor(r, g, b);
        const adjustments = this.colors[colorClass];
        
        let c = 0, m = 0, y = 0, k = 0;
        
        if (r > 0 || g > 0 || b > 0) {
            const maxRGB = Math.max(r, g, b);
            const minRGB = Math.min(r, g, b);
            
            k = 1 - maxRGB;
            c = (1 - r - k) / (1 - k) || 0;
            m = (1 - g - k) / (1 - k) || 0;
            y = (1 - b - k) / (1 - k) || 0;
        }
        
        if (this.mode === 'relative') {
            c += c * adjustments.cyan / 100;
            m += m * adjustments.magenta / 100;
            y += y * adjustments.yellow / 100;
            k += k * adjustments.black / 100;
        } else {
            c += adjustments.cyan / 100;
            m += adjustments.magenta / 100;
            y += adjustments.yellow / 100;
            k += adjustments.black / 100;
        }
        
        c = Math.max(0, Math.min(1, c));
        m = Math.max(0, Math.min(1, m));
        y = Math.max(0, Math.min(1, y));
        k = Math.max(0, Math.min(1, k));
        
        const newR = Math.round((1 - c * (1 - k) - k) * 255);
        const newG = Math.round((1 - m * (1 - k) - k) * 255);
        const newB = Math.round((1 - y * (1 - k) - k) * 255);
        
        return [newR, newG, newB];
    }
    
    _classifyColor(r, g, b) {
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const diff = max - min;
        
        if (max < 0.1) return 'black';
        if (min > 0.9) return 'white';
        if (diff < 0.15) return 'neutral';
        
        if (r >= g && r >= b) {
            if (g >= b) return 'red';
            return 'magenta';
        }
        if (g >= r && g >= b) {
            if (r >= b) return 'yellow';
            return 'green';
        }
        if (b >= r && b >= g) {
            if (r >= g) return 'magenta';
            return 'cyan';
        }
        
        return 'neutral';
    }
    
    applyToImage(image) {
        return image.map(pixel => this.apply(pixel));
    }
}
```

---

## 九、照片滤镜与渐变映射

### 9.1 照片滤镜效果

```javascript
class PhotoFilter {
    FILTERS = {
        'warming_85': {
            name: '暖色滤镜85',
            color: [255, 200, 100],
            density: 0.3,
            description: '模拟85B暖色滤镜'
        },
        'warming_81': {
            name: '暖色滤镜81',
            color: [255, 220, 150],
            density: 0.25,
            description: '模拟81暖色滤镜'
        },
        'cooling_80': {
            name: '冷色滤镜80',
            color: [100, 150, 255],
            density: 0.3,
            description: '模拟80冷色滤镜'
        },
        'cooling_82': {
            name: '冷色滤镜82',
            color: [150, 180, 255],
            density: 0.25,
            description: '模拟82冷色滤镜'
        },
        'sepia': {
            name: '棕褐色',
            color: [112, 66, 20],
            density: 0.4,
            description: '经典棕褐色调'
        },
        'infrared': {
            name: '红外线',
            color: [255, 255, 100],
            density: 0.5,
            description: '模拟红外摄影效果'
        }
    };
    
    applyFilter(image, filterName, density = null) {
        const filter = this.FILTERS[filterName];
        if (!filter) return image;
        
        const effectiveDensity = density !== null ? density : filter.density;
        const [fr, fg, fb] = filter.color;
        
        return image.map(pixel => {
            const [r, g, b] = pixel;
            
            const newR = Math.round(r * (1 - effectiveDensity) + fr * effectiveDensity);
            const newG = Math.round(g * (1 - effectiveDensity) + fg * effectiveDensity);
            const newB = Math.round(b * (1 - effectiveDensity) + fb * effectiveDensity);
            
            return [
                Math.max(0, Math.min(255, newR)),
                Math.max(0, Math.min(255, newG)),
                Math.max(0, Math.min(255, newB))
            ];
        });
    }
    
    applyCustomFilter(image, color, density) {
        const [fr, fg, fb] = color;
        
        return image.map(pixel => {
            const [r, g, b] = pixel;
            
            const newR = Math.round(r * (1 - density) + fr * density);
            const newG = Math.round(g * (1 - density) + fg * density);
            const newB = Math.round(b * (1 - density) + fb * density);
            
            return [
                Math.max(0, Math.min(255, newR)),
                Math.max(0, Math.min(255, newG)),
                Math.max(0, Math.min(255, newB))
            ];
        });
    }
}
```

### 9.2 渐变映射效果

```javascript
class GradientMap {
    constructor() {
        this.stops = [
            { position: 0, color: [0, 0, 0] },
            { position: 1, color: [255, 255, 255] }
        ];
    }
    
    apply(image) {
        return image.map(pixel => {
            const luma = Math.round(0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2]);
            const position = luma / 255;
            
            return this._interpolateColor(position);
        });
    }
    
    _interpolateColor(position) {
        let i = 0;
        while (i < this.stops.length - 1 && this.stops[i + 1].position < position) {
            i++;
        }
        
        if (i >= this.stops.length - 1) {
            return [...this.stops[this.stops.length - 1].color];
        }
        
        const stop1 = this.stops[i];
        const stop2 = this.stops[i + 1];
        
        if (stop1.position === stop2.position) {
            return [...stop1.color];
        }
        
        const t = (position - stop1.position) / (stop2.position - stop1.position);
        
        const [r1, g1, b1] = stop1.color;
        const [r2, g2, b2] = stop2.color;
        
        return [
            Math.round(r1 + t * (r2 - r1)),
            Math.round(g1 + t * (g2 - g1)),
            Math.round(b1 + t * (b2 - b1))
        ];
    }
    
    addStop(position, color) {
        this.stops.push({ position, color });
        this.stops.sort((a, b) => a.position - b.position);
    }
    
    removeStop(index) {
        if (this.stops.length > 2) {
            this.stops.splice(index, 1);
        }
    }
}
```

---

## 十、调整图层技术

### 10.1 调整图层体系

```javascript
class AdjustmentLayerSystem {
    constructor() {
        this.layers = [];
        this.activeLayer = null;
    }
    
    createLayer(type, name, settings = {}) {
        const layer = {
            id: Date.now(),
            type: type,
            name: name || `${type} Adjustment`,
            visible: true,
            opacity: 100,
            blendMode: 'Normal',
            settings: settings,
            mask: null,
            clippingMask: false
        };
        
        this.layers.push(layer);
        this.activeLayer = layer;
        
        return layer;
    }
    
    applyAllLayers(image) {
        let result = image;
        
        for (const layer of this.layers) {
            if (!layer.visible) continue;
            
            let adjusted = this._applyLayer(result, layer);
            
            adjusted = this._applyBlendMode(result, adjusted, layer);
            
            result = adjusted;
        }
        
        return result;
    }
    
    _applyLayer(image, layer) {
        switch (layer.type) {
            case 'levels':
                const levels = new LevelsAdjustment();
                levels.setInputLevels(
                    layer.settings.inputBlack || 0,
                    layer.settings.inputGray || 1,
                    layer.settings.inputWhite || 255
                );
                return levels.applyToImage(image);
            
            case 'curves':
                const curves = new CurvesAdjustment();
                if (layer.settings.points) {
                    layer.settings.points.forEach(p => curves.addPoint(p[0], p[1]));
                }
                return curves.applyToRGB(image);
            
            case 'colorBalance':
                const colorBalance = new ColorBalanceAdjustment();
                colorBalance.setShadows(
                    layer.settings.shadows[0],
                    layer.settings.shadows[1],
                    layer.settings.shadows[2]
                );
                colorBalance.setMidtones(
                    layer.settings.midtones[0],
                    layer.settings.midtones[1],
                    layer.settings.midtones[2]
                );
                colorBalance.setHighlights(
                    layer.settings.highlights[0],
                    layer.settings.highlights[1],
                    layer.settings.highlights[2]
                );
                return colorBalance.applyToImage(image);
            
            case 'hueSaturation':
                const hueSat = new HueSaturationAdjustment();
                hueSat.setHue(layer.settings.hue || 0);
                hueSat.setSaturation(layer.settings.saturation || 0);
                hueSat.setLightness(layer.settings.lightness || 0);
                return hueSat.applyToImage(image);
            
            default:
                return image;
        }
    }
    
    _applyBlendMode(base, blend, layer) {
        const opacity = layer.opacity / 100;
        
        return base.map((basePixel, i) => {
            const blendPixel = blend[i];
            
            let result;
            switch (layer.blendMode) {
                case 'Normal':
                    result = blendPixel;
                    break;
                case 'Multiply':
                    result = basePixel.map((b, j) => Math.round(b * blendPixel[j] / 255));
                    break;
                case 'Screen':
                    result = basePixel.map((b, j) => Math.round(255 - (255 - b) * (255 - blendPixel[j]) / 255));
                    break;
                case 'Overlay':
                    result = basePixel.map((b, j) => {
                        const bn = b / 255;
                        const sn = blendPixel[j] / 255;
                        return Math.round(bn < 0.5 ? 2 * bn * sn * 255 : (1 - 2 * (1 - bn) * (1 - sn)) * 255);
                    });
                    break;
                default:
                    result = blendPixel;
            }
            
            return result.map((r, j) => Math.round(basePixel[j] * (1 - opacity) + r * opacity));
        });
    }
}
```

---

## 十一、自动化色彩校正API

### 11.1 Photoshop ActionManager API

```javascript
class PhotoshopColorCorrectionAPI {
    static applyLevelsAdjustment(inputBlack, inputGray, inputWhite) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        desc.putClass(charIDToTypeID('Usng'), charIDToTypeID('Lvls'));
        
        const adjustmentDesc = new ActionDescriptor();
        adjustmentDesc.putInteger(charIDToTypeID('Blck'), inputBlack);
        adjustmentDesc.putDouble(charIDToTypeID('Gry '), inputGray);
        adjustmentDesc.putInteger(charIDToTypeID('Whte'), inputWhite);
        
        desc.putObject(charIDToTypeID('Adjs'), charIDToTypeID('Lvls'), adjustmentDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
    
    static applyCurvesAdjustment(points) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        desc.putClass(charIDToTypeID('Usng'), charIDToTypeID('Crvs'));
        
        const adjustmentDesc = new ActionDescriptor();
        
        const curveList = new ActionList();
        points.forEach(point => {
            const pointDesc = new ActionDescriptor();
            pointDesc.putUnitDouble(charIDToTypeID('Hrzn'), charIDToTypeID('Prcn'), point[0]);
            pointDesc.putUnitDouble(charIDToTypeID('Vrtc'), charIDToTypeID('Prcn'), point[1]);
            curveList.putObject(charIDToTypeID('Pnt '), pointDesc);
        });
        
        adjustmentDesc.putList(charIDToTypeID('Crv '), curveList);
        
        desc.putObject(charIDToTypeID('Adjs'), charIDToTypeID('Crvs'), adjustmentDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
    
    static applyColorBalance(shadows, midtones, highlights) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        desc.putClass(charIDToTypeID('Usng'), charIDToTypeID('ClrB'));
        
        const adjustmentDesc = new ActionDescriptor();
        
        adjustmentDesc.putInteger(charIDToTypeID('Shdw'), shadows[0]);
        adjustmentDesc.putInteger(charIDToTypeID('ShmG'), shadows[1]);
        adjustmentDesc.putInteger(charIDToTypeID('ShmB'), shadows[2]);
        
        adjustmentDesc.putInteger(charIDToTypeID('MdT '), midtones[0]);
        adjustmentDesc.putInteger(charIDToTypeID('MdmG'), midtones[1]);
        adjustmentDesc.putInteger(charIDToTypeID('MdmB'), midtones[2]);
        
        adjustmentDesc.putInteger(charIDToTypeID('Hghl'), highlights[0]);
        adjustmentDesc.putInteger(charIDToTypeID('HghG'), highlights[1]);
        adjustmentDesc.putInteger(charIDToTypeID('HghB'), highlights[2]);
        
        desc.putObject(charIDToTypeID('Adjs'), charIDToTypeID('ClrB'), adjustmentDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
    
    static applyHueSaturation(hue, saturation, lightness) {
        const desc = new ActionDescriptor();
        
        const layerRef = new ActionReference();
        layerRef.putEnumerated(charIDToTypeID('Lyr '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), layerRef);
        
        desc.putClass(charIDToTypeID('Usng'), charIDToTypeID('HueS'));
        
        const adjustmentDesc = new ActionDescriptor();
        adjustmentDesc.putInteger(charIDToTypeID('Hue '), hue);
        adjustmentDesc.putInteger(charIDToTypeID('Sat '), saturation);
        adjustmentDesc.putInteger(charIDToTypeID('Lght'), lightness);
        
        desc.putObject(charIDToTypeID('Adjs'), charIDToTypeID('HueS'), adjustmentDesc);
        
        executeAction(charIDToTypeID('Mk  '), desc, DialogModes.NO);
    }
}
```

### 11.2 批量色彩校正脚本

```javascript
class BatchColorCorrection {
    static processFolder(inputFolder, outputFolder, correctionProfile) {
        const files = inputFolder.getFiles();
        
        for (const file of files) {
            if (file instanceof File && file.name.match(/\.(jpg|jpeg|png|tif|tiff)$/i)) {
                BatchColorCorrection.processFile(file, outputFolder, correctionProfile);
            }
        }
    }
    
    static processFile(file, outputFolder, correctionProfile) {
        app.open(file);
        
        const doc = app.activeDocument;
        
        BatchColorCorrection.applyCorrection(doc, correctionProfile);
        
        const outputFile = new File(outputFolder + '/' + file.name);
        doc.saveAs(outputFile, new JPEGOptions(), true);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
    
    static applyCorrection(doc, profile) {
        if (profile.levels) {
            PhotoshopColorCorrectionAPI.applyLevelsAdjustment(
                profile.levels.inputBlack,
                profile.levels.inputGray,
                profile.levels.inputWhite
            );
        }
        
        if (profile.curves) {
            PhotoshopColorCorrectionAPI.applyCurvesAdjustment(profile.curves.points);
        }
        
        if (profile.colorBalance) {
            PhotoshopColorCorrectionAPI.applyColorBalance(
                profile.colorBalance.shadows,
                profile.colorBalance.midtones,
                profile.colorBalance.highlights
            );
        }
        
        if (profile.hueSaturation) {
            PhotoshopColorCorrectionAPI.applyHueSaturation(
                profile.hueSaturation.hue,
                profile.hueSaturation.saturation,
                profile.hueSaturation.lightness
            );
        }
    }
}
```

---

## 十二、学术研究与论文索引

### 12.1 色彩科学论文索引

```javascript
class ColorScienceResearch {
    PAPERS = [
        {
            title: 'Digital Color Management: Encoding Solutions',
            authors: ['F. Gay', 'M. S. Drew'],
            year: 2001,
            journal: 'Morgan Kaufmann',
            topic: '色彩管理',
            keyFindings: '数字色彩管理的完整指南'
        },
        {
            title: 'The CIEDE2000 Color-Difference Formula',
            authors: ['M. Melgosa', 'J. Quesada', 'E. Hita'],
            year: 2000,
            journal: 'Color Research & Application',
            topic: '色彩差异公式',
            keyFindings: '提出CIEDE2000色彩差异公式'
        },
        {
            title: 'Color Appearance Models',
            authors: ['M. D. Fairchild'],
            year: 2013,
            journal: 'Wiley',
            topic: '色彩外观模型',
            keyFindings: '色彩外观模型的全面论述'
        },
        {
            title: 'Perceptual Uniformity of Color Spaces',
            authors: ['E. D. Berns', 'R. H. Kuehni'],
            year: 2000,
            journal: 'Color Research & Application',
            topic: '色彩空间均匀性',
            keyFindings: '评估色彩空间感知均匀性的方法'
        },
        {
            title: 'Automatic White Balance for Digital Photography',
            authors: ['B. G. Kim', 'S. K. Park'],
            year: 2006,
            journal: 'IEEE Transactions on Consumer Electronics',
            topic: '自动白平衡',
            keyFindings: '数字摄影自动白平衡算法'
        }
    ];
    
    searchByTopic(topic) {
        return this.PAPERS.filter(p => p.topic.toLowerCase().includes(topic.toLowerCase()));
    }
}
```

### 12.2 关键技术参考文献

```javascript
class TechnicalReferences {
    REFERENCES = {
        'color_spaces': [
            'CIE 15:2004 - Colorimetry',
            'ICC.1:2010 - ICC Profile Format Specification',
            'ISO 15076-1:2010 - Image technology color management'
        ],
        'color_correction': [
            'Photoshop Color Correction Handbook',
            'Professional Photoshop Color Correction',
            'Color Correction for Digital Photographers'
        ],
        'image_processing': [
            'Digital Image Processing',
            'The Image Processing Handbook',
            'Color Science: Concepts and Methods'
        ]
    };
    
    getReferences(category) {
        return this.REFERENCES[category] || [];
    }
}
```

---

## 附录

### A. 色彩校正参数速查表

| 参数 | 范围 | 默认值 | 用途 |
|------|------|--------|------|
| 输入黑场 | 0~255 | 0 | 设置阴影起始点 |
| 输入灰场 | 0.1~9.99 | 1.0 | 调整Gamma值 |
| 输入白场 | 0~255 | 255 | 设置高光起始点 |
| 输出黑场 | 0~255 | 0 | 设置阴影输出 |
| 输出白场 | 0~255 | 255 | 设置高光输出 |
| 色相 | -180~180 | 0 | 色相偏移 |
| 饱和度 | -100~100 | 0 | 饱和度调整 |
| 明度 | -100~100 | 0 | 亮度调整 |

### B. 调整图层快捷键

| 操作 | 快捷键 |
|------|--------|
| 色阶 | Ctrl+L |
| 曲线 | Ctrl+M |
| 色彩平衡 | Ctrl+B |
| 色相/饱和度 | Ctrl+U |
| 可选颜色 | Ctrl+Shift+Alt+B |
| 照片滤镜 | - |
| 渐变映射 | - |
| 反相 | Ctrl+I |
| 阈值 | - |
| 色调分离 | - |

### C. 色彩校正工作流检查清单

- [ ] 检查直方图确认曝光情况
- [ ] 调整白平衡
- [ ] 设置黑场和白场
- [ ] 调整对比度（色阶或曲线）
- [ ] 调整色彩平衡
- [ ] 微调色相/饱和度
- [ ] 选择性色彩调整
- [ ] 应用滤镜或LUT
- [ ] 检查色彩一致性
- [ ] 导出前最终检查

---

> 返回总中心 → [[🎬-风格化剪辑知识库-MOC]]