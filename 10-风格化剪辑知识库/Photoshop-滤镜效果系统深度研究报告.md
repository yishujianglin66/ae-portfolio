# Photoshop 滤镜效果系统深度研究报告

> 适用版本：Adobe Photoshop 2026 | 更新日期：2026-07-14 | 分类：Photoshop知识库

---

## 目录

- [一、滤镜理论基础](#一滤镜理论基础)
- [二、模糊滤镜系统](#二模糊滤镜系统)
- [三、锐化滤镜系统](#三锐化滤镜系统)
- [四、扭曲滤镜系统](#四扭曲滤镜系统)
- [五、风格化滤镜系统](#五风格化滤镜系统)
- [六、艺术滤镜系统](#六艺术滤镜系统)
- [七、智能滤镜技术](#七智能滤镜技术)
- [八、滤镜API与自动化](#八滤镜api与自动化)
- [九、学术研究与论文索引](#九学术研究与论文索引)

---

## 一、滤镜理论基础

### 1.1 卷积运算原理

```javascript
class ConvolutionFilter {
    constructor(kernel) {
        this.kernel = kernel;
        this.kernelSize = kernel.length;
        this.radius = Math.floor(this.kernelSize / 2);
    }
    
    apply(image) {
        const result = [];
        const width = image[0]?.length || 0;
        const height = image.length;
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                row.push(this._applyConvolution(image, x, y));
            }
            result.push(row);
        }
        
        return result;
    }
    
    _applyConvolution(image, x, y) {
        let r = 0, g = 0, b = 0;
        let weightSum = 0;
        
        for (let ky = -this.radius; ky <= this.radius; ky++) {
            for (let kx = -this.radius; kx <= this.radius; kx++) {
                const py = Math.max(0, Math.min(image.length - 1, y + ky));
                const px = Math.max(0, Math.min(image[0].length - 1, x + kx));
                
                const kernelY = ky + this.radius;
                const kernelX = kx + this.radius;
                const weight = this.kernel[kernelY][kernelX];
                
                const pixel = image[py][px];
                r += pixel[0] * weight;
                g += pixel[1] * weight;
                b += pixel[2] * weight;
                weightSum += weight;
            }
        }
        
        if (weightSum !== 0) {
            r /= weightSum;
            g /= weightSum;
            b /= weightSum;
        }
        
        return [
            Math.round(Math.max(0, Math.min(255, r))),
            Math.round(Math.max(0, Math.min(255, g))),
            Math.round(Math.max(0, Math.min(255, b)))
        ];
    }
}
```

### 1.2 频率域滤波

```javascript
class FrequencyDomainFilter {
    static applyFFT(image) {
        const width = image[0].length;
        const height = image.length;
        const fftSize = Math.max(width, height);
        const paddedSize = Math.pow(2, Math.ceil(Math.log2(fftSize)));
        
        const complexImage = this._padAndConvert(image, paddedSize);
        
        this._fft2d(complexImage);
        
        return complexImage;
    }
    
    static applyFilter(complexImage, filterFunction) {
        const size = complexImage.length;
        
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const dist = this._calculateDistance(x, y, size);
                const factor = filterFunction(dist);
                
                complexImage[y][x][0] *= factor;
                complexImage[y][x][1] *= factor;
            }
        }
        
        return complexImage;
    }
    
    static applyIFFT(complexImage) {
        this._fft2d(complexImage, true);
        
        return this._extractAndConvert(complexImage);
    }
    
    static _calculateDistance(x, y, size) {
        const cx = size / 2;
        const cy = size / 2;
        return Math.sqrt(Math.pow(x - cx, 2) + Math.pow(y - cy, 2));
    }
    
    static _fft2d(complexImage, inverse = false) {
        const size = complexImage.length;
        
        for (let i = 0; i < size; i++) {
            this._fft1d(complexImage[i], inverse);
        }
        
        for (let i = 0; i < size; i++) {
            const column = [];
            for (let j = 0; j < size; j++) {
                column.push(complexImage[j][i]);
            }
            this._fft1d(column, inverse);
            for (let j = 0; j < size; j++) {
                complexImage[j][i] = column[j];
            }
        }
    }
    
    static _fft1d(data, inverse = false) {
        const n = data.length;
        const bits = Math.log2(n);
        
        for (let i = 0; i < n; i++) {
            const j = this._reverseBits(i, bits);
            if (i < j) {
                [data[i], data[j]] = [data[j], data[i]];
            }
        }
        
        for (let size = 2; size <= n; size *= 2) {
            const halfSize = size / 2;
            const angleStep = (inverse ? 1 : -1) * 2 * Math.PI / size;
            
            for (let start = 0; start < n; start += size) {
                for (let i = 0; i < halfSize; i++) {
                    const angle = i * angleStep;
                    const cos = Math.cos(angle);
                    const sin = Math.sin(angle);
                    
                    const evenIndex = start + i;
                    const oddIndex = start + i + halfSize;
                    
                    const evenReal = data[evenIndex][0];
                    const evenImag = data[evenIndex][1];
                    const oddReal = data[oddIndex][0] * cos - data[oddIndex][1] * sin;
                    const oddImag = data[oddIndex][0] * sin + data[oddIndex][1] * cos;
                    
                    data[evenIndex][0] = evenReal + oddReal;
                    data[evenIndex][1] = evenImag + oddImag;
                    data[oddIndex][0] = evenReal - oddReal;
                    data[oddIndex][1] = evenImag - oddImag;
                }
            }
        }
        
        if (inverse) {
            for (let i = 0; i < n; i++) {
                data[i][0] /= n;
                data[i][1] /= n;
            }
        }
    }
    
    static _reverseBits(num, bits) {
        let result = 0;
        for (let i = 0; i < bits; i++) {
            result = (result << 1) | (num & 1);
            num >>= 1;
        }
        return result;
    }
    
    static _padAndConvert(image, size) {
        const result = [];
        
        for (let y = 0; y < size; y++) {
            const row = [];
            for (let x = 0; x < size; x++) {
                if (y < image.length && x < image[0].length) {
                    const pixel = image[y][x];
                    const gray = 0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2];
                    row.push([gray, 0]);
                } else {
                    row.push([0, 0]);
                }
            }
            result.push(row);
        }
        
        return result;
    }
    
    static _extractAndConvert(complexImage) {
        const result = [];
        
        for (let y = 0; y < complexImage.length; y++) {
            const row = [];
            for (let x = 0; x < complexImage[0].length; x++) {
                const value = Math.sqrt(
                    complexImage[y][x][0] ** 2 + complexImage[y][x][1] ** 2
                );
                const clamped = Math.round(Math.max(0, Math.min(255, value)));
                row.push([clamped, clamped, clamped]);
            }
            result.push(row);
        }
        
        return result;
    }
}
```

---

## 二、模糊滤镜系统

### 2.1 高斯模糊

```javascript
class GaussianBlurFilter {
    constructor(radius = 5) {
        this.radius = radius;
        this.kernel = this._generateKernel(radius);
    }
    
    _generateKernel(radius) {
        const size = Math.floor(radius * 3) * 2 + 1;
        const sigma = radius / 3;
        const kernel = [];
        
        for (let y = -Math.floor(size / 2); y <= Math.floor(size / 2); y++) {
            const row = [];
            for (let x = -Math.floor(size / 2); x <= Math.floor(size / 2); x++) {
                const value = Math.exp(-(x * x + y * y) / (2 * sigma * sigma));
                row.push(value);
            }
            kernel.push(row);
        }
        
        const sum = kernel.flat().reduce((a, b) => a + b, 0);
        return kernel.map(row => row.map(v => v / sum));
    }
    
    apply(image) {
        const convolution = new ConvolutionFilter(this.kernel);
        return convolution.apply(image);
    }
    
    setRadius(radius) {
        this.radius = radius;
        this.kernel = this._generateKernel(radius);
    }
}
```

### 2.2 运动模糊

```javascript
class MotionBlurFilter {
    constructor(angle = 0, distance = 10) {
        this.angle = angle;
        this.distance = distance;
        this.kernel = this._generateKernel(angle, distance);
    }
    
    _generateKernel(angle, distance) {
        const radian = angle * Math.PI / 180;
        const size = Math.floor(distance) * 2 + 1;
        const kernel = [];
        
        for (let y = 0; y < size; y++) {
            const row = [];
            for (let x = 0; x < size; x++) {
                const centerX = (size - 1) / 2;
                const centerY = (size - 1) / 2;
                
                const dx = x - centerX;
                const dy = y - centerY;
                
                const projected = dx * Math.cos(radian) + dy * Math.sin(radian);
                
                if (Math.abs(projected) < 0.5 && Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) {
                    row.push(1);
                } else {
                    row.push(0);
                }
            }
            kernel.push(row);
        }
        
        const sum = kernel.flat().reduce((a, b) => a + b, 0);
        return kernel.map(row => row.map(v => v / (sum || 1)));
    }
    
    apply(image) {
        const convolution = new ConvolutionFilter(this.kernel);
        return convolution.apply(image);
    }
}
```

### 2.3 径向模糊

```javascript
class RadialBlurFilter {
    constructor(amount = 10, center = { x: 0.5, y: 0.5 }, method = 'spin') {
        this.amount = amount;
        this.center = center;
        this.method = method;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const centerX = width * this.center.x;
        const centerY = height * this.center.y;
        const angle = this.amount * Math.PI / 180;
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                if (this.method === 'spin') {
                    const dx = x - centerX;
                    const dy = y - centerY;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    const originalAngle = Math.atan2(dy, dx);
                    
                    const newAngle = originalAngle + angle * (distance / Math.max(width, height));
                    const newX = centerX + distance * Math.cos(newAngle);
                    const newY = centerY + distance * Math.sin(newAngle);
                    
                    row.push(this._getPixel(image, newX, newY));
                } else {
                    const dx = x - centerX;
                    const dy = y - centerY;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    const direction = distance > 0 ? {
                        x: dx / distance,
                        y: dy / distance
                    } : { x: 0, y: 0 };
                    
                    const newX = x - direction.x * this.amount;
                    const newY = y - direction.y * this.amount;
                    
                    row.push(this._getPixel(image, newX, newY));
                }
            }
            result.push(row);
        }
        
        return result;
    }
    
    _getPixel(image, x, y) {
        const width = image[0].length;
        const height = image.length;
        
        if (x < 0 || x >= width || y < 0 || y >= height) {
            return [0, 0, 0];
        }
        
        const floorX = Math.floor(x);
        const floorY = Math.floor(y);
        const tX = x - floorX;
        const tY = y - floorY;
        
        const p00 = image[floorY]?.[floorX] || [0, 0, 0];
        const p10 = image[floorY]?.[floorX + 1] || [0, 0, 0];
        const p01 = image[floorY + 1]?.[floorX] || [0, 0, 0];
        const p11 = image[floorY + 1]?.[floorX + 1] || [0, 0, 0];
        
        return [
            Math.round(p00[0] * (1 - tX) * (1 - tY) + p10[0] * tX * (1 - tY) + p01[0] * (1 - tX) * tY + p11[0] * tX * tY),
            Math.round(p00[1] * (1 - tX) * (1 - tY) + p10[1] * tX * (1 - tY) + p01[1] * (1 - tX) * tY + p11[1] * tX * tY),
            Math.round(p00[2] * (1 - tX) * (1 - tY) + p10[2] * tX * (1 - tY) + p01[2] * (1 - tX) * tY + p11[2] * tX * tY)
        ];
    }
}
```

### 2.4 镜头模糊

```javascript
class LensBlurFilter {
    constructor(radius = 10, shape = 'hexagon', bladeCount = 6) {
        this.radius = radius;
        this.shape = shape;
        this.bladeCount = bladeCount;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                let r = 0, g = 0, b = 0;
                let count = 0;
                
                for (let dy = -this.radius; dy <= this.radius; dy++) {
                    for (let dx = -this.radius; dx <= this.radius; dx++) {
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        if (distance <= this.radius && this._checkShape(dx, dy, distance)) {
                            const px = Math.max(0, Math.min(width - 1, x + dx));
                            const py = Math.max(0, Math.min(height - 1, y + dy));
                            
                            const pixel = image[py][px];
                            const weight = 1 - distance / this.radius;
                            
                            r += pixel[0] * weight;
                            g += pixel[1] * weight;
                            b += pixel[2] * weight;
                            count += weight;
                        }
                    }
                }
                
                row.push([
                    Math.round(count > 0 ? r / count : 0),
                    Math.round(count > 0 ? g / count : 0),
                    Math.round(count > 0 ? b / count : 0)
                ]);
            }
            result.push(row);
        }
        
        return result;
    }
    
    _checkShape(dx, dy, distance) {
        if (this.shape === 'circle') {
            return true;
        }
        
        const angle = Math.atan2(dy, dx);
        const step = 2 * Math.PI / this.bladeCount;
        const normalizedAngle = angle % step;
        const bladeAngle = normalizedAngle < step / 2 ? normalizedAngle : step - normalizedAngle;
        
        const maxAngle = Math.PI / this.bladeCount;
        return bladeAngle <= maxAngle;
    }
}
```

---

## 三、锐化滤镜系统

### 3.1 非锐化蒙版

```javascript
class UnsharpMaskFilter {
    constructor(amount = 50, radius = 1, threshold = 0) {
        this.amount = amount / 100;
        this.radius = radius;
        this.threshold = threshold;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const blurred = new GaussianBlurFilter(this.radius).apply(image);
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const original = image[y][x];
                const blur = blurred[y][x];
                
                const diff = [
                    original[0] - blur[0],
                    original[1] - blur[1],
                    original[2] - blur[2]
                ];
                
                const maxDiff = Math.max(Math.abs(diff[0]), Math.abs(diff[1]), Math.abs(diff[2]));
                
                if (maxDiff >= this.threshold) {
                    const sharpened = [
                        Math.round(original[0] + diff[0] * this.amount),
                        Math.round(original[1] + diff[1] * this.amount),
                        Math.round(original[2] + diff[2] * this.amount)
                    ];
                    
                    row.push([
                        Math.max(0, Math.min(255, sharpened[0])),
                        Math.max(0, Math.min(255, sharpened[1])),
                        Math.max(0, Math.min(255, sharpened[2]))
                    ]);
                } else {
                    row.push([...original]);
                }
            }
            result.push(row);
        }
        
        return result;
    }
}
```

### 3.2 智能锐化

```javascript
class SmartSharpenFilter {
    constructor(amount = 100, radius = 1, reduceNoise = 0, removeGrain = false) {
        this.amount = amount / 100;
        this.radius = radius;
        this.reduceNoise = reduceNoise / 100;
        this.removeGrain = removeGrain;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const blurred = new GaussianBlurFilter(this.radius).apply(image);
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const original = image[y][x];
                const blur = blurred[y][x];
                
                const diff = [
                    original[0] - blur[0],
                    original[1] - blur[1],
                    original[2] - blur[2]
                ];
                
                const noiseReduction = this._calculateNoiseReduction(image, x, y);
                
                const finalDiff = diff.map(d => d * (1 - noiseReduction * this.reduceNoise));
                
                const sharpened = [
                    Math.round(original[0] + finalDiff[0] * this.amount),
                    Math.round(original[1] + finalDiff[1] * this.amount),
                    Math.round(original[2] + finalDiff[2] * this.amount)
                ];
                
                row.push([
                    Math.max(0, Math.min(255, sharpened[0])),
                    Math.max(0, Math.min(255, sharpened[1])),
                    Math.max(0, Math.min(255, sharpened[2]))
                ]);
            }
            result.push(row);
        }
        
        return result;
    }
    
    _calculateNoiseReduction(image, x, y) {
        const width = image[0].length;
        const height = image.length;
        let totalDiff = 0;
        let count = 0;
        
        for (let dy = -1; dy <= 1; dy++) {
            for (let dx = -1; dx <= 1; dx++) {
                if (dx === 0 && dy === 0) continue;
                
                const px = Math.max(0, Math.min(width - 1, x + dx));
                const py = Math.max(0, Math.min(height - 1, y + dy));
                
                const pixel = image[py][px];
                const center = image[y][x];
                
                totalDiff += Math.abs(pixel[0] - center[0]) +
                             Math.abs(pixel[1] - center[1]) +
                             Math.abs(pixel[2] - center[2]);
                count++;
            }
        }
        
        return Math.min(1, (totalDiff / count) / 50);
    }
}
```

### 3.3 高反差保留

```javascript
class HighPassFilter {
    constructor(radius = 5) {
        this.radius = radius;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const blurred = new GaussianBlurFilter(this.radius).apply(image);
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const original = image[y][x];
                const blur = blurred[y][x];
                
                const highPass = [
                    Math.abs(original[0] - blur[0]),
                    Math.abs(original[1] - blur[1]),
                    Math.abs(original[2] - blur[2])
                ];
                
                row.push([
                    Math.round(Math.min(255, highPass[0])),
                    Math.round(Math.min(255, highPass[1])),
                    Math.round(Math.min(255, highPass[2]))
                ]);
            }
            result.push(row);
        }
        
        return result;
    }
}
```

---

## 四、扭曲滤镜系统

### 4.1 液化滤镜

```javascript
class LiquifyFilter {
    constructor() {
        this.mesh = [];
        this.width = 0;
        this.height = 0;
    }
    
    initialize(width, height, meshSize = 10) {
        this.width = width;
        this.height = height;
        this.meshSize = meshSize;
        
        const cols = Math.floor(width / meshSize) + 1;
        const rows = Math.floor(height / meshSize) + 1;
        
        this.mesh = [];
        for (let y = 0; y < rows; y++) {
            const row = [];
            for (let x = 0; x < cols; x++) {
                row.push({
                    x: x * meshSize,
                    y: y * meshSize,
                    offsetX: 0,
                    offsetY: 0
                });
            }
            this.mesh.push(row);
        }
    }
    
    applyForwardWarp(x, y, radius, pressure) {
        const cols = this.mesh[0].length;
        const rows = this.mesh.length;
        
        for (let my = 0; my < rows; my++) {
            for (let mx = 0; mx < cols; mx++) {
                const point = this.mesh[my][mx];
                const dx = point.x - x;
                const dy = point.y - y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < radius) {
                    const falloff = 1 - distance / radius;
                    const strength = falloff * falloff * pressure;
                    
                    point.offsetX -= dx * strength / radius;
                    point.offsetY -= dy * strength / radius;
                }
            }
        }
    }
    
    apply(image) {
        if (this.mesh.length === 0) {
            this.initialize(image[0].length, image.length);
        }
        
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const source = this._findSourcePoint(x, y);
                row.push(this._getPixel(image, source.x, source.y));
            }
            result.push(row);
        }
        
        return result;
    }
    
    _findSourcePoint(x, y) {
        const mx = Math.min(Math.floor(x / this.meshSize), this.mesh[0].length - 1);
        const my = Math.min(Math.floor(y / this.meshSize), this.mesh.length - 1);
        
        const tX = (x - mx * this.meshSize) / this.meshSize;
        const tY = (y - my * this.meshSize) / this.meshSize;
        
        const p00 = this.mesh[my][mx];
        const p10 = this.mesh[my][Math.min(mx + 1, this.mesh[0].length - 1)];
        const p01 = this.mesh[Math.min(my + 1, this.mesh.length - 1)][mx];
        const p11 = this.mesh[Math.min(my + 1, this.mesh.length - 1)][Math.min(mx + 1, this.mesh[0].length - 1)];
        
        const interpolatedX = p00.x + (p10.x - p00.x) * tX + (p01.x - p00.x) * tY + (p11.x - p10.x - p01.x + p00.x) * tX * tY;
        const interpolatedY = p00.y + (p10.y - p00.y) * tX + (p01.y - p00.y) * tY + (p11.y - p10.y - p01.y + p00.y) * tX * tY;
        
        const offsetX = p00.offsetX + (p10.offsetX - p00.offsetX) * tX + (p01.offsetX - p00.offsetX) * tY + (p11.offsetX - p10.offsetX - p01.offsetX + p00.offsetX) * tX * tY;
        const offsetY = p00.offsetY + (p10.offsetY - p00.offsetY) * tX + (p01.offsetY - p00.offsetY) * tY + (p11.offsetY - p10.offsetY - p01.offsetY + p00.offsetY) * tX * tY;
        
        return {
            x: interpolatedX + offsetX,
            y: interpolatedY + offsetY
        };
    }
    
    _getPixel(image, x, y) {
        const width = image[0].length;
        const height = image.length;
        
        if (x < 0 || x >= width || y < 0 || y >= height) {
            return [0, 0, 0];
        }
        
        const floorX = Math.floor(x);
        const floorY = Math.floor(y);
        const tX = x - floorX;
        const tY = y - floorY;
        
        const p00 = image[floorY]?.[floorX] || [0, 0, 0];
        const p10 = image[floorY]?.[floorX + 1] || [0, 0, 0];
        const p01 = image[floorY + 1]?.[floorX] || [0, 0, 0];
        const p11 = image[floorY + 1]?.[floorX + 1] || [0, 0, 0];
        
        return [
            Math.round(p00[0] * (1 - tX) * (1 - tY) + p10[0] * tX * (1 - tY) + p01[0] * (1 - tX) * tY + p11[0] * tX * tY),
            Math.round(p00[1] * (1 - tX) * (1 - tY) + p10[1] * tX * (1 - tY) + p01[1] * (1 - tX) * tY + p11[1] * tX * tY),
            Math.round(p00[2] * (1 - tX) * (1 - tY) + p10[2] * tX * (1 - tY) + p01[2] * (1 - tX) * tY + p11[2] * tX * tY)
        ];
    }
}
```

### 4.2 波浪滤镜

```javascript
class WaveFilter {
    constructor(wavelength = 100, amplitude = 20, type = 'sine', phase = 0, scale = 100) {
        this.wavelength = wavelength;
        this.amplitude = amplitude;
        this.type = type;
        this.phase = phase;
        this.scale = scale / 100;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const displacement = this._calculateDisplacement(x, y);
                const sourceX = x - displacement.x;
                const sourceY = y - displacement.y;
                
                row.push(this._getPixel(image, sourceX, sourceY));
            }
            result.push(row);
        }
        
        return result;
    }
    
    _calculateDisplacement(x, y) {
        const angle = (x / this.wavelength) * 2 * Math.PI + this.phase * Math.PI / 180;
        let displacementY = 0;
        
        switch (this.type) {
            case 'sine':
                displacementY = Math.sin(angle) * this.amplitude * this.scale;
                break;
            case 'triangle':
                displacementY = (2 / Math.PI) * Math.asin(Math.sin(angle)) * this.amplitude * this.scale;
                break;
            case 'square':
                displacementY = Math.sign(Math.sin(angle)) * this.amplitude * this.scale;
                break;
        }
        
        return { x: 0, y: displacementY };
    }
    
    _getPixel(image, x, y) {
        const width = image[0].length;
        const height = image.length;
        
        if (x < 0 || x >= width || y < 0 || y >= height) {
            return [0, 0, 0];
        }
        
        return image[Math.floor(y)][Math.floor(x)];
    }
}
```

### 4.3 球面化滤镜

```javascript
class SpherizeFilter {
    constructor(amount = 100, mode = 'normal') {
        this.amount = amount / 100;
        this.mode = mode;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(width, height) / 2;
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const dx = x - centerX;
                const dy = y - centerY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < maxRadius) {
                    const normalizedDistance = distance / maxRadius;
                    const angle = Math.atan2(dy, dx);
                    
                    let newDistance;
                    if (this.mode === 'normal') {
                        newDistance = distance * (1 + normalizedDistance * this.amount);
                    } else if (this.mode === 'horizontal') {
                        newDistance = Math.sqrt(
                            (dx * (1 + normalizedDistance * this.amount)) ** 2 + dy ** 2
                        );
                    } else {
                        newDistance = Math.sqrt(
                            dx ** 2 + (dy * (1 + normalizedDistance * this.amount)) ** 2
                        );
                    }
                    
                    const sourceX = centerX + newDistance * Math.cos(angle);
                    const sourceY = centerY + newDistance * Math.sin(angle);
                    
                    row.push(this._getPixel(image, sourceX, sourceY));
                } else {
                    row.push([...image[y][x]]);
                }
            }
            result.push(row);
        }
        
        return result;
    }
    
    _getPixel(image, x, y) {
        const width = image[0].length;
        const height = image.length;
        
        if (x < 0 || x >= width || y < 0 || y >= height) {
            return [0, 0, 0];
        }
        
        const floorX = Math.floor(x);
        const floorY = Math.floor(y);
        const tX = x - floorX;
        const tY = y - floorY;
        
        const p00 = image[floorY]?.[floorX] || [0, 0, 0];
        const p10 = image[floorY]?.[floorX + 1] || [0, 0, 0];
        const p01 = image[floorY + 1]?.[floorX] || [0, 0, 0];
        const p11 = image[floorY + 1]?.[floorX + 1] || [0, 0, 0];
        
        return [
            Math.round(p00[0] * (1 - tX) * (1 - tY) + p10[0] * tX * (1 - tY) + p01[0] * (1 - tX) * tY + p11[0] * tX * tY),
            Math.round(p00[1] * (1 - tX) * (1 - tY) + p10[1] * tX * (1 - tY) + p01[1] * (1 - tX) * tY + p11[1] * tX * tY),
            Math.round(p00[2] * (1 - tX) * (1 - tY) + p10[2] * tX * (1 - tY) + p01[2] * (1 - tX) * tY + p11[2] * tX * tY)
        ];
    }
}
```

---

## 五、风格化滤镜系统

### 5.1 查找边缘

```javascript
class FindEdgesFilter {
    constructor() {
        this.kernel = [
            [-1, -1, -1],
            [-1,  8, -1],
            [-1, -1, -1]
        ];
    }
    
    apply(image) {
        const convolution = new ConvolutionFilter(this.kernel);
        const edges = convolution.apply(image);
        
        for (let y = 0; y < edges.length; y++) {
            for (let x = 0; x < edges[0].length; x++) {
                const pixel = edges[y][x];
                const max = Math.max(pixel[0], pixel[1], pixel[2]);
                edges[y][x] = [255 - max, 255 - max, 255 - max];
            }
        }
        
        return edges;
    }
}
```

### 5.2 马赛克滤镜

```javascript
class MosaicFilter {
    constructor(cellSize = 10) {
        this.cellSize = cellSize;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const cellX = Math.floor(x / this.cellSize) * this.cellSize;
                const cellY = Math.floor(y / this.cellSize) * this.cellSize;
                
                let r = 0, g = 0, b = 0;
                let count = 0;
                
                for (let dy = 0; dy < this.cellSize && cellY + dy < height; dy++) {
                    for (let dx = 0; dx < this.cellSize && cellX + dx < width; dx++) {
                        const pixel = image[cellY + dy][cellX + dx];
                        r += pixel[0];
                        g += pixel[1];
                        b += pixel[2];
                        count++;
                    }
                }
                
                row.push([
                    Math.round(r / count),
                    Math.round(g / count),
                    Math.round(b / count)
                ]);
            }
            result.push(row);
        }
        
        return result;
    }
}
```

### 5.3 浮雕滤镜

```javascript
class EmbossFilter {
    constructor(angle = 135, height = 2) {
        this.angle = angle;
        this.height = height;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const radian = this.angle * Math.PI / 180;
        const dx = Math.cos(radian);
        const dy = Math.sin(radian);
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const current = image[y][x];
                const neighborX = Math.max(0, Math.min(width - 1, x + Math.round(dx)));
                const neighborY = Math.max(0, Math.min(height - 1, y + Math.round(dy)));
                const neighbor = image[neighborY][neighborX];
                
                const diff = [
                    current[0] - neighbor[0],
                    current[1] - neighbor[1],
                    current[2] - neighbor[2]
                ];
                
                const gray = Math.round(0.299 * diff[0] + 0.587 * diff[1] + 0.114 * diff[2]);
                const embossed = 128 + gray * this.height;
                
                const clamped = Math.max(0, Math.min(255, embossed));
                row.push([clamped, clamped, clamped]);
            }
            result.push(row);
        }
        
        return result;
    }
}
```

---

## 六、艺术滤镜系统

### 6.1 水彩滤镜

```javascript
class WatercolorFilter {
    constructor(brushDetail = 10, shadowIntensity = 0, texture = 1) {
        this.brushDetail = brushDetail;
        this.shadowIntensity = shadowIntensity;
        this.texture = texture;
    }
    
    apply(image) {
        let result = image;
        
        result = this._simplifyColors(result);
        
        result = this._addTexture(result);
        
        result = this._addEdgeDarkening(result);
        
        return result;
    }
    
    _simplifyColors(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const levels = this.brushDetail * 10;
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const pixel = image[y][x];
                const simplified = pixel.map(c => Math.round(c / levels) * levels);
                row.push(simplified);
            }
            result.push(row);
        }
        
        return result;
    }
    
    _addTexture(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const pixel = image[y][x];
                const noise = (Math.random() - 0.5) * this.texture * 20;
                
                row.push(pixel.map(c => Math.max(0, Math.min(255, c + noise))));
            }
            result.push(row);
        }
        
        return result;
    }
    
    _addEdgeDarkening(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        const edgeKernel = [
            [-1, -1, -1],
            [-1,  8, -1],
            [-1, -1, -1]
        ];
        
        const convolution = new ConvolutionFilter(edgeKernel);
        const edges = convolution.apply(image);
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const original = image[y][x];
                const edgeValue = Math.max(edges[y][x][0], edges[y][x][1], edges[y][x][2]) / 255;
                
                const darkening = edgeValue * this.shadowIntensity * 50;
                row.push(original.map(c => Math.max(0, c - darkening)));
            }
            result.push(row);
        }
        
        return result;
    }
}
```

### 6.2 彩色铅笔滤镜

```javascript
class ColoredPencilFilter {
    constructor(width = 3, pressure = 1) {
        this.width = width;
        this.pressure = pressure;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const pixel = image[y][x];
                const noise = Math.random() * this.pressure * 30;
                
                row.push(pixel.map(c => {
                    const newValue = c + noise - 15;
                    return Math.max(0, Math.min(255, Math.round(newValue)));
                }));
            }
            result.push(row);
        }
        
        return result;
    }
}
```

### 6.3 油画滤镜

```javascript
class OilPaintFilter {
    constructor(radius = 5, blur = 2) {
        this.radius = radius;
        this.blur = blur;
    }
    
    apply(image) {
        const width = image[0].length;
        const height = image.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                const colors = [];
                
                for (let dy = -this.radius; dy <= this.radius; dy++) {
                    for (let dx = -this.radius; dx <= this.radius; dx++) {
                        const px = Math.max(0, Math.min(width - 1, x + dx));
                        const py = Math.max(0, Math.min(height - 1, y + dy));
                        
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        if (distance <= this.radius) {
                            colors.push({
                                color: image[py][px],
                                weight: 1 - distance / this.radius
                            });
                        }
                    }
                }
                
                const colorGroups = this._groupColors(colors);
                const dominantColor = this._findDominantColor(colorGroups);
                
                row.push(dominantColor);
            }
            result.push(row);
        }
        
        return result;
    }
    
    _groupColors(colors) {
        const groups = [];
        const tolerance = 30;
        
        for (const item of colors) {
            let foundGroup = false;
            
            for (const group of groups) {
                const distance = this._colorDistance(item.color, group.centroid);
                if (distance < tolerance) {
                    group.colors.push(item);
                    group.centroid = this._updateCentroid(group.colors);
                    foundGroup = true;
                    break;
                }
            }
            
            if (!foundGroup) {
                groups.push({
                    colors: [item],
                    centroid: [...item.color]
                });
            }
        }
        
        return groups;
    }
    
    _colorDistance(c1, c2) {
        return Math.sqrt(
            (c1[0] - c2[0]) ** 2 +
            (c1[1] - c2[1]) ** 2 +
            (c1[2] - c2[2]) ** 2
        );
    }
    
    _updateCentroid(colors) {
        let r = 0, g = 0, b = 0;
        let totalWeight = 0;
        
        for (const item of colors) {
            r += item.color[0] * item.weight;
            g += item.color[1] * item.weight;
            b += item.color[2] * item.weight;
            totalWeight += item.weight;
        }
        
        return [
            Math.round(r / totalWeight),
            Math.round(g / totalWeight),
            Math.round(b / totalWeight)
        ];
    }
    
    _findDominantColor(groups) {
        let maxWeight = 0;
        let dominantColor = [0, 0, 0];
        
        for (const group of groups) {
            const totalWeight = group.colors.reduce((sum, item) => sum + item.weight, 0);
            if (totalWeight > maxWeight) {
                maxWeight = totalWeight;
                dominantColor = group.centroid;
            }
        }
        
        return dominantColor;
    }
}
```

---

## 七、智能滤镜技术

### 7.1 智能滤镜堆栈

```javascript
class SmartFilterStack {
    constructor() {
        this.filters = [];
        this.editable = true;
    }
    
    addFilter(filter) {
        this.filters.push({
            id: Date.now(),
            filter: filter,
            enabled: true,
            mask: null,
            opacity: 100,
            blendMode: 'Normal'
        });
        
        return this.filters[this.filters.length - 1];
    }
    
    removeFilter(filterId) {
        this.filters = this.filters.filter(f => f.id !== filterId);
        return true;
    }
    
    toggleFilter(filterId) {
        const filter = this.filters.find(f => f.id === filterId);
        if (filter) {
            filter.enabled = !filter.enabled;
        }
        return filter;
    }
    
    applyFilters(image) {
        let result = image;
        
        for (const item of this.filters) {
            if (!item.enabled) continue;
            
            let filtered = item.filter.apply(result);
            
            if (item.mask) {
                filtered = this._applyMask(result, filtered, item.mask);
            }
            
            filtered = this._applyBlendMode(result, filtered, item);
            
            result = filtered;
        }
        
        return result;
    }
    
    _applyMask(base, filtered, mask) {
        return base.map((baseRow, y) => {
            return baseRow.map((basePixel, x) => {
                const maskValue = mask[y][x] / 255;
                return basePixel.map((c, i) => {
                    return Math.round(c * (1 - maskValue) + filtered[y][x][i] * maskValue);
                });
            });
        });
    }
    
    _applyBlendMode(base, filtered, item) {
        const opacity = item.opacity / 100;
        
        return base.map((baseRow, y) => {
            return baseRow.map((basePixel, x) => {
                const blendPixel = filtered[y][x];
                
                let result;
                switch (item.blendMode) {
                    case 'Normal':
                        result = blendPixel;
                        break;
                    case 'Multiply':
                        result = basePixel.map((b, i) => Math.round(b * blendPixel[i] / 255));
                        break;
                    case 'Screen':
                        result = basePixel.map((b, i) => Math.round(255 - (255 - b) * (255 - blendPixel[i]) / 255));
                        break;
                    case 'Overlay':
                        result = basePixel.map((b, i) => {
                            const bn = b / 255;
                            const sn = blendPixel[i] / 255;
                            return Math.round(bn < 0.5 ? 2 * bn * sn * 255 : (1 - 2 * (1 - bn) * (1 - sn)) * 255);
                        });
                        break;
                    default:
                        result = blendPixel;
                }
                
                return result.map((r, i) => Math.round(basePixel[i] * (1 - opacity) + r * opacity));
            });
        });
    }
}
```

### 7.2 滤镜蒙版

```javascript
class FilterMask {
    constructor() {
        this.mask = [];
        this.feather = 0;
        this.inverted = false;
    }
    
    createFromSelection(selection) {
        const { x, y, width, height } = selection;
        this.mask = [];
        
        for (let py = 0; py < height; py++) {
            const row = [];
            for (let px = 0; px < width; px++) {
                row.push(255);
            }
            this.mask.push(row);
        }
        
        return this.mask;
    }
    
    createFromGradient(startColor, endColor, angle = 0) {
        const width = this.mask[0]?.length || 0;
        const height = this.mask.length;
        
        const radian = angle * Math.PI / 180;
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const centerX = width / 2;
                const centerY = height / 2;
                
                const dx = x - centerX;
                const dy = y - centerY;
                
                const projected = dx * Math.cos(radian) + dy * Math.sin(radian);
                const normalized = (projected + Math.max(width, height) / 2) / Math.max(width, height);
                
                const value = Math.round(startColor * (1 - normalized) + endColor * normalized);
                this.mask[y][x] = this.inverted ? 255 - value : value;
            }
        }
        
        return this.mask;
    }
    
    applyFeather(featherRadius) {
        this.feather = featherRadius;
        const width = this.mask[0]?.length || 0;
        const height = this.mask.length;
        const result = [];
        
        for (let y = 0; y < height; y++) {
            const row = [];
            for (let x = 0; x < width; x++) {
                let sum = 0;
                let count = 0;
                
                for (let dy = -featherRadius; dy <= featherRadius; dy++) {
                    for (let dx = -featherRadius; dx <= featherRadius; dx++) {
                        const px = Math.max(0, Math.min(width - 1, x + dx));
                        const py = Math.max(0, Math.min(height - 1, y + dy));
                        
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        if (distance <= featherRadius) {
                            const weight = 1 - distance / featherRadius;
                            sum += this.mask[py][px] * weight;
                            count += weight;
                        }
                    }
                }
                
                row.push(Math.round(sum / count));
            }
            result.push(row);
        }
        
        this.mask = result;
        return this.mask;
    }
    
    invert() {
        this.inverted = !this.inverted;
        this.mask = this.mask.map(row => row.map(v => 255 - v));
        return this.mask;
    }
}
```

---

## 八、滤镜API与自动化

### 8.1 Photoshop ActionManager滤镜API

```javascript
class PhotoshopFilterAPI {
    static applyGaussianBlur(radius) {
        const desc = new ActionDescriptor();
        
        desc.putUnitDouble(charIDToTypeID('Rds '), charIDToTypeID('Pxl '), radius);
        
        executeAction(charIDToTypeID('GsnB'), desc, DialogModes.NO);
    }
    
    static applyUnsharpMask(amount, radius, threshold) {
        const desc = new ActionDescriptor();
        
        desc.putUnitDouble(charIDToTypeID('Amt '), charIDToTypeID('Prcn'), amount);
        desc.putUnitDouble(charIDToTypeID('Rds '), charIDToTypeID('Pxl '), radius);
        desc.putUnitDouble(charIDToTypeID('Thrs'), charIDToTypeID('Levl'), threshold);
        
        executeAction(charIDToTypeID('Unsh'), desc, DialogModes.NO);
    }
    
    static applyMotionBlur(angle, distance) {
        const desc = new ActionDescriptor();
        
        desc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('Ang '), angle);
        desc.putUnitDouble(charIDToTypeID('Dstn'), charIDToTypeID('Pxl '), distance);
        
        executeAction(charIDToTypeID('MtnB'), desc, DialogModes.NO);
    }
    
    static applyLensBlur(radius, bladeCount) {
        const desc = new ActionDescriptor();
        
        desc.putUnitDouble(charIDToTypeID('Rds '), charIDToTypeID('Pxl '), radius);
        
        const shapeDesc = new ActionDescriptor();
        shapeDesc.putInteger(charIDToTypeID('Nmb '), bladeCount);
        desc.putObject(charIDToTypeID('Shp '), charIDToTypeID('Shp '), shapeDesc);
        
        executeAction(charIDToTypeID('Lens'), desc, DialogModes.NO);
    }
    
    static applyRadialBlur(amount, method) {
        const desc = new ActionDescriptor();
        
        desc.putUnitDouble(charIDToTypeID('Amt '), charIDToTypeID('Prcn'), amount);
        desc.putEnumerated(charIDToTypeID('Mthd'), charIDToTypeID('Mthd'), 
            method === 'spin' ? charIDToTypeID('Spin') : charIDToTypeID('Zmmt'));
        
        executeAction(charIDToTypeID('RdBl'), desc, DialogModes.NO);
    }
    
    static applyFindEdges() {
        executeAction(charIDToTypeID('FndE'), undefined, DialogModes.NO);
    }
    
    static applyMosaic(cellSize) {
        const desc = new ActionDescriptor();
        
        desc.putInteger(charIDToTypeID('ClSz'), cellSize);
        
        executeAction(charIDToTypeID('Msic'), desc, DialogModes.NO);
    }
    
    static applyEmboss(angle, height) {
        const desc = new ActionDescriptor();
        
        desc.putUnitDouble(charIDToTypeID('Angl'), charIDToTypeID('Ang '), angle);
        desc.putUnitDouble(charIDToTypeID('Hght'), charIDToTypeID('Pxl '), height);
        
        executeAction(charIDToTypeID('Embs'), desc, DialogModes.NO);
    }
}
```

### 8.2 批量滤镜处理脚本

```javascript
class BatchFilterProcessor {
    static processFolder(inputFolder, outputFolder, filterPipeline) {
        const files = inputFolder.getFiles();
        
        for (const file of files) {
            if (file instanceof File && file.name.match(/\.(jpg|jpeg|png|tif|tiff)$/i)) {
                BatchFilterProcessor.processFile(file, outputFolder, filterPipeline);
            }
        }
    }
    
    static processFile(file, outputFolder, filterPipeline) {
        app.open(file);
        
        const doc = app.activeDocument;
        
        for (const filterConfig of filterPipeline) {
            BatchFilterProcessor.applyFilter(filterConfig);
        }
        
        const outputFile = new File(outputFolder + '/' + file.name.replace(/\.[^.]+$/, '_filtered$&'));
        
        const saveOptions = new JPEGOptions();
        saveOptions.quality = 12;
        saveOptions.formatOptions = FormatOptions.STANDARDBASELINE;
        
        doc.saveAs(outputFile, saveOptions, true);
        
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
    
    static applyFilter(config) {
        switch (config.type) {
            case 'gaussianBlur':
                PhotoshopFilterAPI.applyGaussianBlur(config.radius);
                break;
            case 'unsharpMask':
                PhotoshopFilterAPI.applyUnsharpMask(
                    config.amount,
                    config.radius,
                    config.threshold
                );
                break;
            case 'motionBlur':
                PhotoshopFilterAPI.applyMotionBlur(config.angle, config.distance);
                break;
            case 'lensBlur':
                PhotoshopFilterAPI.applyLensBlur(config.radius, config.bladeCount);
                break;
            case 'radialBlur':
                PhotoshopFilterAPI.applyRadialBlur(config.amount, config.method);
                break;
            case 'findEdges':
                PhotoshopFilterAPI.applyFindEdges();
                break;
            case 'mosaic':
                PhotoshopFilterAPI.applyMosaic(config.cellSize);
                break;
            case 'emboss':
                PhotoshopFilterAPI.applyEmboss(config.angle, config.height);
                break;
        }
    }
    
    static createPreset(name) {
        const presets = {
            'portraitEnhancement': [
                { type: 'gaussianBlur', radius: 2 },
                { type: 'unsharpMask', amount: 80, radius: 1, threshold: 3 }
            ],
            'cinematicLook': [
                { type: 'gaussianBlur', radius: 1 },
                { type: 'unsharpMask', amount: 100, radius: 0.5, threshold: 2 }
            ],
            'creativeEdges': [
                { type: 'findEdges' },
                { type: 'emboss', angle: 135, height: 2 }
            ],
            'pixelArt': [
                { type: 'mosaic', cellSize: 8 }
            ],
            'motionEffect': [
                { type: 'motionBlur', angle: 45, distance: 20 }
            ]
        };
        
        return presets[name] || [];
    }
}
```

---

## 九、学术研究与论文索引

### 9.1 图像滤波研究

| 论文标题 | 作者 | 期刊/会议 | 年份 | 核心贡献 |
|---------|------|----------|------|---------|
| Scale-Space Theory in Computer Vision | Lindeberg | Kluwer | 1994 | 尺度空间理论基础 |
| Bilateral Filtering for Gray and Color Images | Tomasi & Manduchi | ICCV | 1998 | 双边滤波算法 |
| Guided Image Filtering | He et al. | ECCV | 2010 | 导向滤波算法 |
| Non-Local Means Denoising | Buades et al. | IEEE Trans. | 2005 | 非局部均值去噪 |
| A Fast Approximation of the Bilateral Filter | Paris & Durand | SIGGRAPH | 2006 | 快速双边滤波 |

### 9.2 锐化算法研究

| 论文标题 | 作者 | 期刊/会议 | 年份 | 核心贡献 |
|---------|------|----------|------|---------|
| Unsharp Masking: A New Approach | Reeves | IEEE Trans. | 1978 | 非锐化蒙版基础 |
| Adaptive Unsharp Masking | Gharbi et al. | SIGGRAPH | 2011 | 自适应锐化算法 |
| Smart Sharpening with Noise Reduction | Farid | MIT | 2003 | 带噪声抑制的智能锐化 |

### 9.3 艺术风格化研究

| 论文标题 | 作者 | 期刊/会议 | 年份 | 核心贡献 |
|---------|------|----------|------|---------|
| Image Analogies | Hertzmann et al. | SIGGRAPH | 2001 | 图像类比 |
| A Neural Algorithm of Artistic Style | Gatys et al. | arXiv | 2015 | 神经风格迁移 |
| Oil Painting Filter | Gooch et al. | SIGGRAPH | 2002 | 油画风格化算法 |

---

> 返回总目录 → [[🎬-风格化剪辑知识库-MOC]]