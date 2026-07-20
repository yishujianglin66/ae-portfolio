# AE表达式核心函数完全手册（完整版）

> 完整版 · 原子级参数控制 · 300+实战表达式 · 全面覆盖AE表达式所有核心函数
> 
> 本手册是Adobe After Effects表达式的权威参考文档，涵盖从基础语法到高级物理模拟的完整知识体系。

---

## 目录

- [一、表达式基础](#一表达式基础)
- [二、全局对象与属性](#二全局对象与属性)
- [三、数学函数库](#三数学函数库)
- [四、插值与缓动函数](#四插值与缓动函数)
- [五、向量与数组操作](#五向量与数组操作)
- [六、时间函数](#六时间函数)
- [七、随机数与噪声](#七随机数与噪声)
- [八、循环函数](#八循环函数)
- [九、属性查询函数](#九属性查询函数)
- [十、图层查询函数](#十图层查询函数)
- [十一、合成函数](#十一合成函数)
- [十二、文字表达式](#十二文字表达式)
- [十三、音频表达式](#十三音频表达式)
- [十四、路径表达式](#十四路径表达式)
- [十五、3D表达式](#十五3d表达式)
- [十六、标记表达式](#十六标记表达式)
- [十七、实用表达式库](#十七实用表达式库)

---

## 一、表达式基础

### 1.1 表达式语法基础

AE表达式是基于JavaScript的语言，用于在时间轴上自动化属性值。表达式应用于属性级别，每一帧都会被求值。

**基本语法规则**：
- 每条表达式最终必须返回一个值
- 多个语句可以使用分号分隔
- 表达式区分大小写
- 数组用方括号 `[x, y]` 表示
- 注释使用 `//` 单行或 `/* */` 多行

**最简单的表达式**：
```js
100;  // 返回固定值100
```

**带运算的表达式**：
```js
time * 360;  // 时间乘以360
```

### 1.2 表达式 vs JavaScript

AE表达式使用ExtendScript引擎（基于ES3），与标准JavaScript有以下区别：

| 特性 | 标准JavaScript | AE表达式 |
|------|---------------|---------|
| 执行环境 | 浏览器/Node | AE渲染引擎 |
| 上下文 | 全局window对象 | thisComp/thisLayer |
| DOM操作 | 支持 | 不支持 |
| 严格模式 | "use strict" | 默认严格 |
| 帧求值 | 事件驱动 | 每帧求值 |
| 性能优化 | JIT编译 | 解释执行 |

**AE扩展的JavaScript特性**：
- 向量运算（数组直接加减乘除）
- 内置全局对象（thisComp、thisLayer等）
- 预定义函数（wiggle、loopOut等）
- 时间感知（time变量自动更新）

### 1.3 表达式的执行机制

**求值时机**：
- 每帧渲染前求值
- 时间轴预览时求值
- 渲染输出时求值
- 表达式依赖的属性变化时求值

**求值顺序**：
1. AE准备渲染当前帧
2. 检查属性是否有表达式
3. 构建表达式上下文（thisComp、thisLayer、time等）
4. 执行表达式
5. 将返回值应用到属性
6. 如果有关键帧，表达式覆盖关键帧值

**缓存机制**：
- 表达式结果会被缓存
- 同一帧多次访问使用缓存值
- 时间变化时重新求值

### 1.4 表达式的性能考量

**性能优化原则**：

```js
// ❌ 慢：每帧都创建新数组
[value[0] + Math.random()*10, value[1] + Math.random()*10]

// ✅ 快：使用seedRandom避免每帧重新求值
seedRandom(index, true);
[value[0] + random(-10, 10), value[1] + random(-10, 10)]
```

**性能杀手**：
- 大量使用 `valueAtTime()` 查询
- 嵌套 `comp()` 引用
- 复杂的循环和递归
- 频繁的关键帧查询

**优化技巧**：
```js
// 使用变量缓存重复计算
myComp = comp("主合成");
myLayer = myComp.layer("控制器");
sliderVal = myLayer.effect("滑块")("滑块");

// 避免在循环中查询
n = numKeys;
sum = 0;
for (i = 1; i <= n; i++) {
    sum += key(i).value;
}
```

### 1.5 表达式调试方法

**1. 使用文本图层输出调试信息**：
```js
// 在文本图层的Source Text上应用
"位置X: " + transform.position[0] + "\n" +
"位置Y: " + transform.position[1] + "\n" +
"时间: " + time + "\n" +
"帧: " + timeToFrames(time)
```

**2. 使用try-catch捕获错误**：
```js
try {
    thisComp.layer("目标").transform.position;
} catch (err) {
    [960, 540];  // 错误时返回默认值
}
```

**3. 启用表达式调试信息**：
- Edit > Preferences > Display > Show Expression Editor
- 查看表达式错误红条
- 使用 `$.writeln()` 输出到控制台（仅在ExtendScript Toolkit中有效）

### 1.6 表达式注释写法

```js
// 单行注释 - 推荐用于简短说明

/* 
   多行注释
   用于详细说明复杂表达式
   作者：设计师
   日期：2024
*/

// 推荐写法：分段注释
// === 第一段：变量定义 ===
freq = 2;      // 频率
amp = 50;      // 振幅

// === 第二段：计算 ===
result = Math.sin(time * freq) * amp;

// === 第三段：返回 ===
value + result;
```

---

## 二、全局对象与属性

### 2.1 thisComp - 当前合成

`thisComp` 引用表达式所在的合成对象，是最常用的全局对象之一。

```js
thisComp.name                    // 合成名称
thisComp.width                   // 合成宽度（像素）
thisComp.height                  // 合成高度（像素）
thisComp.duration                // 合成时长（秒）
thisComp.frameRate               // 帧率（fps）
thisComp.frameDuration           // 单帧时长（秒）
thisComp.bgColor                 // 背景色
thisComp.pixelAspect             // 像素宽高比
thisComp.activeCamera            // 当前激活摄像机
thisComp.numLayers               // 图层数量
```

**示例**：
```js
// 让图层始终位于合成中心
[thisComp.width, thisComp.height] / 2;

// 根据合成尺寸缩放
myScale = thisComp.width / 1920;
value * myScale;
```

### 2.2 thisLayer - 当前图层

`thisLayer` 引用表达式所在的图层对象。

```js
thisLayer.name                   // 图层名称
thisLayer.index                  // 图层索引
thisLayer.inPoint                // 入点（秒）
thisLayer.outPoint               // 出点（秒）
thisLayer.startTime              // 开始时间
thisLayer.hasVideo               // 是否有视频
thisLayer.hasAudio               // 是否有音频
thisLayer.enabled                // 是否启用
thisLayer.active                 // 是否活跃
thisLayer.parent                 // 父图层
thisLayer.source                 // 源素材
```

**示例**：
```js
// 从入点开始计算时间
t = time - thisLayer.inPoint;

// 检查图层是否在活跃时间范围内
if (time >= thisLayer.inPoint && time <= thisLayer.outPoint) {
    100;
} else {
    0;
}
```

### 2.3 thisProperty - 当前属性

`thisProperty` 引用表达式所应用的属性本身。

```js
thisProperty.value               // 当前值
thisProperty.valueAtTime(t)      // 指定时间的值
thisProperty.velocityAtTime(t)   // 指定时间的速度
thisProperty.speedAtTime(t)      // 指定时间的速度大小
thisProperty.numKeys             // 关键帧数量
thisProperty.key(index)          // 指定索引的关键帧
thisProperty.nearestKey(time)    // 最近的关键帧
```

**示例**：
```js
// 获取上一个关键帧的值
n = thisProperty.nearestKey(time).index;
if (thisProperty.key(n).time > time) n--;
if (n > 0) {
    thisProperty.key(n).value;
} else {
    value;
}
```

### 2.4 time - 当前时间

`time` 是表达式求值时的当前时间（秒），是最常用的时间变量。

```js
time                             // 当前时间（秒）
time * thisComp.frameRate        // 当前帧编号
time / thisComp.duration         // 时间归一化（0-1）
```

**示例**：
```js
// 旋转动画：每秒一圈
time * 360;

// 周期2秒的振荡
Math.sin(time * Math.PI) * 50;

// 时间归一化用于插值
t = time / 2;  // 2秒完成
linear(t, 0, 1, 0, 100);
```

### 2.5 value - 当前值

`value` 是表达式应用属性的关键帧值（如果没有关键帧，则是属性的默认值）。

```js
value                            // 完整值
value[0]                         // 第一个分量（X或红色）
value[1]                         // 第二个分量（Y或绿色）
value[2]                         // 第三个分量（Z或蓝色）
value[3]                         // 第四个分量（Alpha）
```

**示例**：
```js
// 在原值基础上添加偏移
value + [50, 0];

// 只修改Y分量
[value[0], value[1] + Math.sin(time)*20];

// 数值缩放
value * 1.5;
```

### 2.6 index - 图层索引

`index` 是当前图层在合成中的序号（从1开始）。

```js
index                            // 当前图层索引
index + 1                        // 下一图层
index - 1                        // 上一图层
```

**示例**：
```js
// 图层按索引错位
timeOffset = index * 0.1;
valueAtTime(time - timeOffset);

// 索引作为随机种子
seedRandom(index, true);
random(-50, 50);

// 索引影响透明度
linear(index, 1, 10, 100, 10);
```

### 2.7 inPoint/outPoint - 入点出点

```js
inPoint                          // 图层入点（秒）
outPoint                         // 图层出点（秒）
outPoint - inPoint               // 图层时长
```

**示例**：
```js
// 从入点开始的时间
t = time - inPoint;

// 出点前淡出
fadeOut = linear(time, outPoint - 1, outPoint, 100, 0);

// 检查是否在图层范围内
if (time >= inPoint && time <= outPoint) {
    100;
} else {
    0;
}
```

### 2.8 width/height - 合成宽高

```js
thisComp.width                   // 合成宽度
thisComp.height                  // 合成高度
[thisComp.width, thisComp.height] // 合成尺寸数组
```

**示例**：
```js
// 居中
[thisComp.width/2, thisComp.height/2];

// 边缘检测
if (transform.position[0] > thisComp.width) {
    // 超出右边缘
}
```

### 2.9 duration - 合成时长

```js
thisComp.duration                // 合成总时长（秒）
thisComp.duration * thisComp.frameRate  // 总帧数
```

### 2.10 frameDuration - 帧时长

```js
thisComp.frameDuration           // 单帧时长（秒）= 1/fps
thisComp.frameRate               // 帧率
1 / thisComp.frameDuration       // 同上
```

### 2.11 fps - 帧率

```js
thisComp.frameRate               // 帧率（fps）
timeToFrames(time)               // 当前帧编号
```

### 2.12 完整属性访问路径表

| 属性 | 路径 | 类型 | 说明 |
|------|------|------|------|
| 位置 | `transform.position` | [x,y] | 图层位置 |
| 缩放 | `transform.scale` | [x,y] | 百分比缩放 |
| 旋转 | `transform.rotation` | Number | 度数 |
| 不透明度 | `transform.opacity` | Number | 0-100 |
| 锚点 | `transform.anchorPoint` | [x,y] | 锚点位置 |
| 定向 | `transform.orientation` | [x,y,z] | 3D方向 |
| X旋转 | `transform.xRotation` | Number | 度数 |
| Y旋转 | `transform.yRotation` | Number | 度数 |
| Z旋转 | `transform.rotationZ` | Number | 度数 |
| 源文本 | `text.sourceText` | String | 文本内容 |
| 源矩形 | `text.sourceRectAtTime(t)` | Object | 文本边界 |
| 时间重映射 | `timeRemap` | Number | 时间映射 |
| 音量 | `audioLevels` | [L,R] | dB |
| 遮罩路径 | `mask("遮罩 1").maskPath` | Path | 遮罩形状 |
| 遮罩羽化 | `mask("遮罩 1").maskFeather` | [x,y] | 羽化值 |
| 效果参数 | `effect("效果名")("参数名")` | Any | 效果控制 |

---

## 三、数学函数库

### 3.1 基础数学函数

**Math.abs(x)** - 绝对值
```js
Math.abs(-5)  // 返回 5
Math.abs(value[0])  // X位置的绝对值
```

**Math.round(x)** - 四舍五入
```js
Math.round(3.7)  // 返回 4
Math.round(time * 10) / 10  // 保留1位小数
```

**Math.ceil(x)** - 向上取整
```js
Math.ceil(3.2)  // 返回 4
Math.ceil(thisComp.duration / 2)  // 时长一半向上取整
```

**Math.floor(x)** - 向下取整
```js
Math.floor(3.8)  // 返回 3
Math.floor(time * 24)  // 当前帧编号（24fps）
```

**Math.max(a, b)** - 最大值
```js
Math.max(10, 20)  // 返回 20
Math.max(value[0], value[1])  // 较大值
```

**Math.min(a, b)** - 最小值
```js
Math.min(10, 20)  // 返回 10
Math.min(100, opacity)  // 限制不超过100
```

**Math.pow(base, exp)** - 幂运算
```js
Math.pow(2, 10)  // 返回 1024
Math.pow(time, 2)  // 时间的平方
```

**Math.sqrt(x)** - 平方根
```js
Math.sqrt(16)  // 返回 4
Math.sqrt(value[0]*value[0] + value[1]*value[1])  // 向量长度
```

**Math.exp(x)** - e的x次方
```js
Math.exp(1)  // 返回 2.71828...
Math.exp(-time)  // 指数衰减
```

**Math.log(x)** - 自然对数
```js
Math.log(Math.E)  // 返回 1
Math.log(10)  // 返回 2.302...
```

### 3.2 三角函数

**Math.sin(x)** - 正弦（弧度）
```js
Math.sin(Math.PI / 2)  // 返回 1
Math.sin(time * 2) * 50  // 振荡动画
```

**Math.cos(x)** - 余弦（弧度）
```js
Math.cos(0)  // 返回 1
Math.cos(time * 2) * 50  // 振荡动画
```

**Math.tan(x)** - 正切
```js
Math.tan(Math.PI / 4)  // 返回约1
```

**Math.asin(x)** - 反正弦
```js
Math.asin(1)  // 返回 Math.PI/2
```

**Math.acos(x)** - 反余弦
```js
Math.acos(0)  // 返回 Math.PI/2
```

**Math.atan(x)** - 反正切
```js
Math.atan(1)  // 返回 Math.PI/4
```

**Math.atan2(y, x)** - 双参数反正切
```js
// 计算两点之间的角度（常用于让图层朝向目标）
target = thisComp.layer("目标").transform.position;
delta = target - transform.position;
Math.atan2(delta[1], delta[0]) * 180 / Math.PI;
```

### 3.3 角度弧度转换

**degreesToRadians(deg)** - 角度转弧度
```js
degreesToRadians(90)  // 返回 Math.PI/2 ≈ 1.5708
Math.sin(degreesToRadians(30))  // 返回 0.5
```

**radiansToDegrees(rad)** - 弧度转角度
```js
radiansToDegrees(Math.PI)  // 返回 180
radiansToDegrees(Math.atan2(1, 1))  // 返回 45
```

### 3.4 随机数函数

**Math.random()** - 0到1的随机数
```js
Math.random()  // 0.0 到 1.0
Math.random() * 100  // 0 到 100
Math.random() * 2 - 1  // -1 到 1
```

**seedRandom(seed, timeless)** - 设置随机种子
```js
seedRandom(42, true);  // timeless=true，每帧相同
random(0, 100);

seedRandom(42, false);  // timeless=false，每帧不同
random(0, 100);

seedRandom(index, true);  // 每个图层不同的固定随机值
```

**gaussRandom()** - 高斯分布随机
```js
gaussRandom()  // 均值0，标准差1
gaussRandom(50, 10)  // 均值50，标准差10
```

**random(min, max)** - 范围随机
```js
random(0, 100)  // 0到100的随机数
random([0,0], [100,100])  // 二维随机向量
random([0,0,0], [100,100,100])  // 三维随机向量
```

### 3.5 数学常量

```js
Math.PI     // 圆周率 ≈ 3.141592653589793
Math.E      // 自然对数底 ≈ 2.718281828459045
Math.SQRT2  // 根号2 ≈ 1.4142135623730951
Math.LN2    // ln(2) ≈ 0.6931471805599453
Math.LN10   // ln(10) ≈ 2.302585092994046
Math.LOG2E  // log2(e) ≈ 1.4426950408889634
Math.LOG10E // log10(e) ≈ 0.4342944819032518
```

### 3.6 映射函数

**linear(t, tMin, tMax, value1, value2)** - 线性映射
```js
// t从tMin到tMax变化时，输出从value1到value2线性变化
linear(time, 0, 5, 0, 100)  // 0-5秒内0-100

// 钳制：超出范围时返回边界值
linear(time, 0, 5, 0, 100)  // time<0返回0，time>5返回100
```

**ease(t, tMin, tMax, value1, value2)** - 缓入缓出
```js
// 端点处缓入缓出
ease(time, 0, 2, 0, 100)
```

**easeIn(t, tMin, tMax, value1, value2)** - 缓入
```js
// 起始端缓慢
easeIn(time, 0, 2, 0, 100)
```

**easeOut(t, tMin, tMax, value1, value2)** - 缓出
```js
// 结束端缓慢
easeOut(time, 0, 2, 0, 100)
```

**简化形式**：
```js
linear(t, value1, value2)  // 等价于 linear(t, 0, 1, value1, value2)
ease(t, value1, value2)
```

### 3.7 钳制函数

**clamp(value, limit1, limit2)** - 限制范围
```js
clamp(150, 0, 100)  // 返回 100
clamp(-50, 0, 100)  // 返回 0
clamp(value, [0,0], [1920,1080])  // 限制在合成范围内
clamp(transform.scale, [50,50], [200,200])  // 缩放范围50-200%
```

### 3.8 其他实用函数

**length(point)** 或 **length(point1, point2)** - 长度/距离
```js
length([3, 4])  // 返回 5
length([0,0], [3,4])  // 返回 5

// 计算两图层距离
p1 = transform.position;
p2 = thisComp.layer("目标").transform.position;
length(p1, p2);
```

**normalize(vec)** - 归一化（已弃用，需手动实现）
```js
// 手动归一化
function normalize(v) {
    var len = length(v);
    return len > 0 ? [v[0]/len, v[1]/len] : v;
}
```

**dot(v1, v2)** - 点积（需手动实现）
```js
function dot(a, b) {
    return a[0]*b[0] + a[1]*b[1] + (a.length > 2 ? a[2]*b[2] : 0);
}
```

**cross(v1, v2)** - 叉积
```js
function cross(a, b) {
    return [
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    ];
}
```

---

## 四、插值与缓动函数

### 4.1 linear() - 线性插值

**完整形式**：
```js
linear(t, tMin, tMax, value1, value2)
```
- `t`: 输入值
- `tMin`, `tMax`: 输入范围
- `value1`, `value2`: 输出范围
- **返回**: 在value1和value2之间线性插值，超出范围则钳制

**示例**：
```js
// 5秒内从0到100
linear(time, 0, 5, 0, 100)

// 从入点开始的5秒动画
linear(time, inPoint, inPoint + 5, 0, 100)

// 颜色渐变
linear(time, 0, 10, [1,0,0], [0,0,1])

// 简化形式：t自动归一化
linear(progress, 0, 100)  // 等价于 linear(progress, 0, 1, 0, 100)
```

### 4.2 ease() - 缓入缓出

```js
ease(t, tMin, tMax, value1, value2)
```
在两端都进行缓动，模拟物理减速效果。

```js
// 平滑的进入退出动画
ease(time, inPoint, inPoint + 1, [960, -100], [960, 540])
```

### 4.3 easeIn() - 缓入

```js
easeIn(t, tMin, tMax, value1, value2)
```
仅在起始端缓动，常用于离开动画。

```js
// 慢慢开始然后加速
easeIn(time, inPoint, inPoint + 2, 0, 100)
```

### 4.4 easeOut() - 缓出

```js
easeOut(t, tMin, tMax, value1, value2)
```
仅在结束端缓动，常用于进入动画。

```js
// 快速进入然后减速
easeOut(time, inPoint, inPoint + 2, 0, 100)
```

### 4.5 自定义缓动曲线实现

```js
// 三次方缓动 easeInOutCubic
function easeInOutCubic(t) {
    return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2, 3)/2;
}

// 使用
t = linear(time, 0, 2, 0, 1);  // 归一化
result = easeInOutCubic(t);
linear(result, 0, 1, 0, 100);
```

### 4.6 贝塞尔曲线缓动

```js
// 三次贝塞尔曲线（模拟AE的动画曲线编辑器）
function cubicBezier(t, p1x, p1y, p2x, p2y) {
    // 简化的贝塞尔近似
    var cx = 3 * p1x;
    var bx = 3 * (p2x - p1x) - cx;
    var ax = 1 - cx - bx;
    
    var cy = 3 * p1y;
    var by = 3 * (p2y - p1y) - cy;
    var ay = 1 - cy - by;
    
    // 求解x对应t（近似）
    var x = t;
    for (var i = 0; i < 5; i++) {
        var newX = ((ax*x + bx)*x + cx)*x;
        if (Math.abs(newX - t) < 0.001) break;
        x += (t - newX) * 0.5;
    }
    
    return ((ay*x + by)*x + cy)*x;
}

// 使用AE默认缓动曲线 (0.42, 0, 0.58, 1)
t = linear(time, 0, 2, 0, 1);
result = cubicBezier(t, 0.42, 0, 0.58, 1);
linear(result, 0, 1, 0, 100);
```

### 4.7 弹性缓动实现

```js
// 弹性效果（Overshoot）
function elastic(t) {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    
    var p = 0.3;  // 周期
    var s = p / 4;
    return Math.pow(2, -10*t) * Math.sin((t-s) * (2*Math.PI) / p) + 1;
}

// 使用：5秒内弹性到达
t = linear(time, inPoint, inPoint + 5, 0, 1, true);
result = elastic(t);
linear(result, 0, 1, 0, 100);
```

### 4.8 弹跳缓动实现

```js
// 弹跳效果
function bounce(t) {
    var n = 4;  // 弹跳次数
    var decay = 0.5;  // 衰减
    
    if (t < 0) return 0;
    if (t >= 1) return 1;
    
    var phase = t * n;
    var bounceNum = Math.floor(phase);
    var localT = phase - bounceNum;
    
    // 抛物线弹跳
    var height = Math.pow(decay, bounceNum);
    return 1 - height * Math.sin(localT * Math.PI);
}

// 使用
t = linear(time, 0, 3, 0, 1);
linear(bounce(t), 0, 1, 0, 100);
```

### 4.9 20种缓动函数实现代码

```js
// === 线性缓动 ===
function easeLinear(t) { return t; }

// === 二次方 ===
function easeInQuad(t) { return t * t; }
function easeOutQuad(t) { return t * (2 - t); }
function easeInOutQuad(t) { return t < 0.5 ? 2*t*t : -1 + (4-2*t)*t; }

// === 三次方 ===
function easeInCubic(t) { return t * t * t; }
function easeOutCubic(t) { return 1 - Math.pow(1-t, 3); }
function easeInOutCubic(t) { return t<0.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2; }

// === 四次方 ===
function easeInQuart(t) { return t * t * t * t; }
function easeOutQuart(t) { return 1 - Math.pow(1-t, 4); }
function easeInOutQuart(t) { return t<0.5 ? 8*t*t*t*t : 1-Math.pow(-2*t+2,4)/2; }

// === 五次方 ===
function easeInQuint(t) { return t*t*t*t*t; }
function easeOutQuint(t) { return 1 - Math.pow(1-t, 5); }
function easeInOutQuint(t) { return t<0.5 ? 16*t*t*t*t*t : 1-Math.pow(-2*t+2,5)/2; }

// === 正弦 ===
function easeInSine(t) { return 1 - Math.cos((t*Math.PI)/2); }
function easeOutSine(t) { return Math.sin((t*Math.PI)/2); }
function easeInOutSine(t) { return -(Math.cos(Math.PI*t)-1)/2; }

// === 指数 ===
function easeInExpo(t) { return t === 0 ? 0 : Math.pow(2, 10*t - 10); }
function easeOutExpo(t) { return t === 1 ? 1 : 1 - Math.pow(2, -10*t); }
function easeInOutExpo(t) {
    if (t === 0) return 0;
    if (t === 1) return 1;
    return t < 0.5 ? Math.pow(2, 20*t-10)/2 : (2-Math.pow(2, -20*t+10))/2;
}

// === 圆形 ===
function easeInCirc(t) { return 1 - Math.sqrt(1 - Math.pow(t, 2)); }
function easeOutCirc(t) { return Math.sqrt(1 - Math.pow(t-1, 2)); }

// === Back（回弹） ===
function easeInBack(t) {
    var c1 = 1.70158;
    var c3 = c1 + 1;
    return c3 * t * t * t - c1 * t * t;
}
function easeOutBack(t) {
    var c1 = 1.70158;
    var c3 = c1 + 1;
    return 1 + c3 * Math.pow(t-1, 3) + c1 * Math.pow(t-1, 2);
}
```

---

## 五、向量与数组操作

### 5.1 数组创建与访问

```js
// 2D数组
pos = [100, 200];
pos[0]  // 100 (X)
pos[1]  // 200 (Y)

// 3D数组
pos3D = [100, 200, 50];
pos3D[2]  // 50 (Z)

// 颜色数组 [R, G, B]
color = [1, 0.5, 0];
// 颜色数组 [R, G, B, A]
colorRGBA = [1, 0.5, 0, 1];
```

### 5.2 向量运算

AE表达式支持数组直接进行算术运算：

```js
v1 = [10, 20];
v2 = [5, 3];

v1 + v2     // [15, 23] 加法
v1 - v2     // [5, 17] 减法
v1 * 2      // [20, 40] 标量乘法
v1 * v2     // [50, 60] 对应元素相乘
v1 / 2      // [5, 10] 标量除法
-v1         // [-10, -20] 取反
```

**实战示例**：
```js
// 计算两点差值
p1 = transform.position;
p2 = thisComp.layer("目标").transform.position;
delta = p2 - p1;  // 方向向量

// 缩放向量
normalized = delta / length(delta);  // 单位向量
```

### 5.3 向量长度 length()

```js
length([3, 4])  // 返回 5
length([1, 2, 2])  // 返回 3
length(transform.position)  // 到原点的距离
```

### 5.4 向量距离 length(p1, p2)

```js
length([0,0], [3,4])  // 返回 5
length([1,1,1], [4,5,1])  // 返回 5

// 实战：两图层距离
p1 = thisComp.layer("图层A").transform.position;
p2 = thisComp.layer("图层B").transform.position;
distance = length(p1, p2);
```

### 5.5 向量归一化

```js
function normalize(v) {
    var len = length(v);
    return len > 0 ? v / len : v;
}

// 使用
dir = normalize(target - position);
```

### 5.6 向量插值

```js
// 线性插值两个向量
p1 = [100, 100];
p2 = [500, 400];
t = 0.5;
result = p1 + (p2 - p1) * t;  // [300, 250]

// 使用linear函数
linear(t, 0, 1, p1, p2);
```

### 5.7 fromComp, toComp, fromWorld, toWorld

**坐标空间转换函数**：

```js
toComp(point, t=time)          // 图层空间 → 合成空间
fromComp(point, t=time)        // 合成空间 → 图层空间
toWorld(point, t=time)         // 图层空间 → 世界空间（3D）
fromWorld(point, t=time)       // 世界空间 → 图层空间（3D）
toLayerVec(vec, t=time)        // 合成向量 → 图层向量
fromLayerVec(vec, t=time)      // 图层向量 → 合成向量
```

**示例 - 合成坐标转图层坐标**：
```js
// 让图层始终指向合成中心
center = [thisComp.width/2, thisComp.height/2];
localCenter = fromComp(center);
// localCenter 是合成中心在当前图层坐标系中的位置
```

**示例 - 世界坐标转图层坐标**：
```js
// 3D图层在2D图层上的投影位置
worldPos = thisComp.layer("3D层").toWorld([0,0,0]);
localPos = fromComp(thisComp.layer("3D层").toComp([0,0,0]));
```

### 5.8 fromLayer, toLayer

```js
// 不同图层之间的坐标转换
layer1Pos = thisComp.layer("图层1").transform.position;
layer2Pos = thisComp.layer("图层2").transform.position;

// 图层1坐标系中的点转到合成坐标系
compPos = thisComp.layer("图层1").toComp([0,0]);

// 再转到图层2坐标系
localPos = thisComp.layer("图层2").fromComp(compPos);
```

### 5.9 坐标空间转换完整指南

**空间层次**：
- 图层空间（Layer Space）：以图层锚点为原点
- 合成空间（Comp Space）：以合成左上角为原点
- 世界空间（World Space）：3D世界坐标

**转换矩阵**：
```
图层空间 ←→ 合成空间 ←→ 世界空间
   fromComp/toComp      fromWorld/toWorld
```

**常用场景**：

```js
// 1. 让2D图层附着在3D图层上
target3D = thisComp.layer("3D层");
target2DPos = target3D.toComp([0,0,0]);
[target2DPos[0], target2DPos[1]];

// 2. 计算两3D图层距离
p1 = thisComp.layer("3D层A").toWorld([0,0,0]);
p2 = thisComp.layer("3D层B").toWorld([0,0,0]);
length(p1, p2);

// 3. 让图层朝向另一个图层
myPos = toComp([0,0,0]);
targetPos = thisComp.layer("目标").toComp([0,0,0]);
angle = radiansToDegrees(Math.atan2(
    targetPos[1] - myPos[1],
    targetPos[0] - myPos[0]
));
angle - transform.rotation;
```

---

## 六、时间函数

### 6.1 time - 当前时间

```js
time  // 当前时间（秒）

// 应用
time * 360  // 每秒360度
time * thisComp.frameRate  // 当前帧编号
```

### 6.2 timeToFrames - 时间转帧

```js
timeToFrames(t = time + thisComp.displayStartTime, fps = 1/thisComp.frameDuration, isDuration = false)

// 基本用法
timeToFrames(time)  // 当前帧编号
timeToFrames(time, 24)  // 24fps下的帧编号
timeToFrames(time, 30, true)  // 作为持续时间
```

**示例**：
```js
// 每5帧切换一次
frame = timeToFrames(time);
Math.floor(frame / 5) % 2;  // 0或1交替
```

### 6.3 framesToTime - 帧转时间

```js
framesToTime(frames, fps = 1/thisComp.frameDuration)

// 基本用法
framesToTime(60)  // 第60帧的时间
framesToTime(60, 24)  // 24fps下第60帧的时间
```

**示例**：
```js
// 帧延迟
delay = framesToTime(5);  // 5帧延迟
valueAtTime(time - delay);
```

### 6.4 timeToTimecode - 时间转时间码

```js
timeToTimecode(t = time + thisComp.displayStartTime, timecodeBase = 30, isDuration = false)

// 基本用法
timeToTimecode(time)  // 返回 "00:00:01:15" 格式
timeToTimecode(time, 25)  // 25fps时间码

// 在文本图层中显示时间码
timeToTimecode(time);
```

### 6.5 timeToFeetAndFrames

```js
timeToFeetAndFrames(t = time + thisComp.displayStartTime, fps = 1/thisComp.frameDuration, framesPerFoot = 16)

// 用于电影胶片格式
timeToFeetAndFrames(time);
```

### 6.6 timeToNTSCTimecode

```js
timeToNTSCTimecode(t = time + thisComp.displayStartTime, ntscDropFrame = false)

// NTSC时间码（29.97fps）
timeToNTSCTimecode(time);
timeToNTSCTimecode(time, true);  // 丢帧格式
```

### 6.7 inPoint, outPoint

```js
inPoint    // 图层入点
outPoint   // 图层出点

// 图层时长
duration = outPoint - inPoint;

// 从入点开始的相对时间
relTime = time - inPoint;

// 归一化时间（0-1）
normTime = (time - inPoint) / (outPoint - inPoint);
```

### 6.8 duration

```js
thisComp.duration  // 合成总时长

// 图层时长
layerDuration = outPoint - inPoint;

// 剩余时长
remaining = outPoint - time;
```

### 6.9 时间偏移与循环

```js
// 时间偏移
offsetTime = time - 1;  // 延迟1秒
valueAtTime(offsetTime);

// 时间倒流
reverseTime = thisComp.duration - time;
valueAtTime(reverseTime);

// 时间循环
cycleTime = (time - inPoint) % 2;  // 每2秒循环
valueAtTime(inPoint + cycleTime);
```

### 6.10 时间重映射表达式

```js
// 在时间重映射属性上应用
// 慢动作 + 加速
if (time < 1) {
    time * 0.5;  // 前半段慢一半
} else {
    0.5 + (time - 1) * 2;  // 后半段两倍速
}

// 时间冻结
freezeTime = 2;  // 第2秒冻结
if (time >= freezeTime && time < freezeTime + 1) {
    freezeTime;
} else if (time >= freezeTime + 1) {
    time - 1;  // 后续顺延
} else {
    time;
}
```

### 6.11 10个时间控制表达式

```js
// 1. 时间延迟
valueAtTime(time - 0.5);

// 2. 时间提前
valueAtTime(time + 0.5);

// 3. 时间冻结
freezeAt = 2;
time < freezeAt ? time : freezeAt;

// 4. 时间循环
cycleDur = 2;
t = (time - inPoint) % cycleDur;
valueAtTime(inPoint + t);

// 5. 时间往返
cycleDur = 2;
t = (time - inPoint) % (cycleDur * 2);
t = t < cycleDur ? t : cycleDur * 2 - t;
valueAtTime(inPoint + t);

// 6. 时间倒流
valueAtTime(outPoint - time + inPoint);

// 7. 时间缩放
scale = 0.5;  // 慢一半
valueAtTime(inPoint + (time - inPoint) * scale);

// 8. 帧步进
step = framesToTime(3);  // 每3帧一跳
Math.floor(time / step) * step;

// 9. 时间随机
seedRandom(1, false);
randomTime = random(inPoint, outPoint);
valueAtTime(randomTime);

// 10. 节拍同步
bpm = 120;
beatTime = 60 / bpm;  // 每拍时间
beat = Math.floor(time / beatTime);
beat * beatTime;
```

---

## 七、随机数与噪声

### 7.1 Math.random() - 基础随机

```js
Math.random()  // 0-1
Math.random() * 100  // 0-100
Math.random() * 2 - 1  // -1到1

// 每帧不同的随机（会闪烁）
[Math.random()*100, Math.random()*100]
```

### 7.2 seedRandom(seed, timeless) - 种子随机

```js
seedRandom(seed, timeless)
// seed: 种子值（数字）
// timeless: true=每帧相同, false=每帧不同

// timeless=true 时返回固定值
seedRandom(42, true);
random(0, 100);  // 每帧都是同一个值

// 用index作为种子，每个图层不同
seedRandom(index, true);
random(-50, 50);
```

### 7.3 gaussRandom() - 高斯随机

```js
gaussRandom()  // 均值0，标准差1
gaussRandom(mean, stddev)  // 自定义均值和标准差

// 高斯分布：大部分值接近均值，少数偏离
seedRandom(1, false);
gaussRandom(50, 10);  // 大部分在40-60之间
```

### 7.4 noise() - 柏林噪声

```js
noise(val)  // 返回 -1 到 1 之间的柏林噪声

// 1D噪声
noise(time)  // 时间维度的平滑噪声

// 2D噪声
noise([time, index])  // 时间和图层索引

// 3D噪声
noise([time, index, 0])

// 实战：平滑随机运动
freq = 1;
amp = 50;
x = noise(time * freq) * amp;
y = noise(time * freq + 100) * amp;  // +100避免相关性
value + [x, y];
```

### 7.5 wiggle(freq, amp) - 摇摆

```js
wiggle(freq, amp)
// freq: 频率（每秒变化次数）
// amp: 振幅（最大偏移量）

// 基本用法
wiggle(2, 50)  // 每秒2次，最大偏移50
wiggle(1, [20, 40])  // X和Y不同振幅

// 在原值基础上摇摆
value + wiggle(2, 10)

// 仅X轴摇摆
w = wiggle(2, 50);
[value[0] + w[0] - value[0], value[1]];  // 等价于
[wiggle(2,50)[0], value[1]];
```

### 7.6 wiggle完整形式

```js
wiggle(freq, amp, octaves = 1, amp_mult = 0.5, t = time)
// freq: 频率
// amp: 振幅
// octaves: 八度数（叠加的噪声层数）
// amp_mult: 每层八度的振幅乘数
// t: 求值时间

// 多层噪声叠加（更自然）
wiggle(2, 50, 3, 0.5)  // 3层，每层振幅减半

// 时间偏移
wiggle(2, 50, 1, 0.5, time - 0.5)  // 提前0.5秒摇摆
```

### 7.7 smooth(width, samples, t)

```js
smooth(width = 0.2, samples = 5, t = time)
// width: 平滑窗口宽度（秒）
// samples: 采样数
// t: 求值时间

// 平滑关键帧动画
smooth(0.5, 5)  // 0.5秒窗口，5个采样点

// 应用到位置
smooth(0.3, 8, time)
```

### 7.8 随机数种子控制

```js
// 全局种子
seedRandom(123, true);
a = random(0, 100);

seedRandom(123, true);  // 重置种子
b = random(0, 100);  // a === b

// 不同种子不同结果
seedRandom(1, true); r1 = random(0, 100);
seedRandom(2, true); r2 = random(0, 100);
// r1 !== r2
```

### 7.9 随机动画不闪烁技巧

```js
// ❌ 错误：每帧重新随机，会闪烁
[Math.random()*100, Math.random()*100]

// ✅ 正确：timeless=true，固定随机
seedRandom(index, true);
[random(0,100), random(0,100)]

// ✅ 平滑随机：使用noise或wiggle
wiggle(2, 50)

// ✅ 基于时间的伪随机（同帧结果相同）
seedRandom(Math.floor(time * 10), true);
random(0, 100);
```

### 7.10 15个随机效果表达式

```js
// 1. 随机位置抖动（不闪烁）
seedRandom(index, true);
value + [random(-50,50), random(-50,50)];

// 2. 随机缩放
seedRandom(index, true);
s = random(50, 150);
[s, s];

// 3. 随机旋转
seedRandom(index, true);
random(-180, 180);

// 4. 随机颜色
seedRandom(index, true);
[random(), random(), random(), 1];

// 5. 随机透明度
seedRandom(index, true);
random(20, 100);

// 6. 时间随机错位
seedRandom(index, true);
offset = random(0, 2);
valueAtTime(time - offset);

// 7. 随机延迟入场
seedRandom(index, true);
delay = random(0, 1);
linear(time, inPoint + delay, inPoint + delay + 0.5, 0, 100);

// 8. 噪声驱动浮动
n = noise(time * 0.5) * 30;
value + [n, noise(time * 0.5 + 100) * 30];

// 9. 随机闪烁（基于时间）
seedRandom(Math.floor(time * 4), true);
random(50, 100);

// 10. 多层wiggle叠加
w1 = wiggle(1, 20);
w2 = wiggle(5, 5);
value + w1 + w2;

// 11. 定向随机
seedRandom(index, true);
angle = random(0, 360);
dist = random(0, 100);
value + [Math.cos(angle*Math.PI/180)*dist, Math.sin(angle*Math.PI/180)*dist];

// 12. 随机抖动但保持运动方向
w = wiggle(3, 10);
value + w;

// 13. 渐进随机
seedRandom(index, true);
target = [random(0,1920), random(0,1080)];
linear(time, inPoint, outPoint, value, target);

// 14. 群组随机（共享种子）
groupSeed = 42;
seedRandom(groupSeed + index, true);
random(-50, 50);

// 15. 柏林噪声纹理
n1 = noise([time*2, 0]);
n2 = noise([time*2, 100]);
n3 = noise([time*2, 200]);
[n1, n2, n3, 1];
```

---

## 八、循环函数

### 8.1 loopIn(type, numKeyframes)

```js
loopIn(type = "cycle", numKeyframes = 0)
// type: 循环类型
// numKeyframes: 使用的关键帧数（0=全部）
// 在第一个关键帧之前循环
```

### 8.2 loopOut(type, numKeyframes)

```js
loopOut(type = "cycle", numKeyframes = 0)
// 在最后一个关键帧之后循环

// 基本用法
loopOut("cycle")  // 循环全部关键帧
loopOut("cycle", 2)  // 只用最后2个关键帧循环
```

### 8.3 loopInDuration(type, duration)

```js
loopInDuration(type = "cycle", duration = 0)
// duration: 循环时长（秒），0=全部
loopInDuration("cycle", 2)  // 前2秒循环
```

### 8.4 loopOutDuration(type, duration)

```js
loopOutDuration(type = "cycle", duration = 0)
// 在最后一个关键帧后按指定时长循环
loopOutDuration("cycle", 2)  // 后2秒循环
```

### 8.5 循环类型详解

**cycle - 重复循环**：
```js
loopOut("cycle")
// 动画从头到尾重复，每次都从起点开始
// 关键帧：0→100，循环后：0→100→0→100...
```

**pingpong - 往返循环**：
```js
loopOut("pingpong")
// 动画来回播放
// 关键帧：0→100，循环后：0→100→100→0→0→100...
```

**offset - 偏移循环**：
```js
loopOut("offset")
// 每次循环累加偏移
// 关键帧：0→100，循环后：0→100→100→200→200→300...
```

**continue - 延续循环**：
```js
loopOut("continue")
// 按最后关键帧的速度延续
// 关键帧：0→100（5秒），5秒后：100→120→140...
```

### 8.6 循环动画实现

```js
// 完整循环动画示例
// 关键帧设置：0秒→0，1秒→360

// 旋转循环
loopOut("cycle")  // 每1秒转一圈，无限重复

// 位置往返
loopOut("pingpong")  // 来回移动

// 持续移动
loopOut("offset")  // 不断向前移动

// 持续旋转
loopOut("continue")  // 按速度继续旋转
```

### 8.7 无缝循环技巧

```js
// 1. 确保首末关键帧值相同（用于cycle）
// 关键帧：0秒→0，2秒→360（旋转一周，视觉无缝）

// 2. 使用pingpong避免值突变
loopOut("pingpong")

// 3. 使用offset实现连续移动
// 关键帧：0秒→0，1秒→100
loopOut("offset")  // 持续向右移动

// 4. 限定循环段
loopOut("cycle", 2)  // 只循环最后2个关键帧

// 5. 时间循环（用于时间重映射）
loopOut("cycle")
```

### 8.8 10个循环动画表达式

```js
// 1. 持续旋转
loopOut("cycle");

// 2. 位置往返
loopOut("pingpong");

// 3. 持续平移
loopOut("offset");

// 4. 速度延续
loopOut("continue");

// 5. 限定段循环
loopOut("cycle", 2);

// 6. 双向循环
if (time < key(1).time) {
    loopIn("cycle");
} else {
    loopOut("cycle");
}

// 7. 时间循环（时间重映射）
loopOut("cycle");

// 8. 混合循环
amp = 100;
loopOut("cycle") + Math.sin(time * 5) * 5;

// 9. 循环+缓动
t = loopOut("cycle");
ease(t, 0, 360, 0, 360);

// 10. 自定义循环
cycleDur = 2;
t = (time - inPoint) % cycleDur;
linear(t, 0, cycleDur, key(1).value, key(2).value);
```

---

## 九、属性查询函数

### 9.1 valueAtTime(t)

```js
valueAtTime(t)
// 返回属性在时间t处的值

// 基本用法
valueAtTime(time - 1)  // 1秒前的值
valueAtTime(time + 0.5)  // 0.5秒后的值

// 时间延迟效果
thisComp.layer("目标").transform.position.valueAtTime(time - 0.5);
```

### 9.2 velocityAtTime(t)

```js
velocityAtTime(t)
// 返回属性在时间t处的速度（向量）

// 获取当前速度
velocity = transform.position.velocityAtTime(time);
speed = length(velocity);

// 冲量效果
v = velocityAtTime(time - 0.01);
value + v * 0.1;
```

### 9.3 speedAtTime(t)

```js
speedAtTime(t)
// 返回属性在时间t处的速度大小（标量）

// 速度驱动的效果
speed = transform.position.speedAtTime(time);
scale = 100 + speed * 0.5;
[scale, scale];
```

### 9.4 key(index)

```js
key(index)
// 返回指定索引的关键帧对象

// 访问关键帧属性
key(1).time   // 第1个关键帧的时间
key(1).value  // 第1个关键帧的值

// 遍历关键帧
n = numKeys;
for (i = 1; i <= n; i++) {
    // key(i)...
}
```

### 9.5 key(markerName)

```js
key("标记名")
// 返回指定名称的关键帧（主要用于标记）

// 使用标记触发
m = key("开始");
if (time >= m.time) {
    100;
} else {
    0;
}
```

### 9.6 numKeys

```js
numKeys
// 返回属性的关键帧数量

if (numKeys > 0) {
    // 有关键帧
    lastKey = key(numKeys);
}
```

### 9.7 nearestKey(time)

```js
nearestKey(time)
// 返回距离time最近的关键帧

n = nearestKey(time).index;
if (key(n).time > time) n--;  // 获取前一个关键帧

// 关键帧间插值
if (n > 0 && n < numKeys) {
    k1 = key(n);
    k2 = key(n + 1);
    t = linear(time, k1.time, k2.time, 0, 1);
    linear(t, k1.value, k2.value);
}
```

### 9.8 属性关键帧操作

```js
// 获取所有关键帧时间
times = [];
for (i = 1; i <= numKeys; i++) {
    times.push(key(i).time);
}

// 关键帧值数组
values = [];
for (i = 1; i <= numKeys; i++) {
    values.push(key(i).value);
}

// 找到特定值的关键帧
targetVal = 100;
for (i = 1; i <= numKeys; i++) {
    if (key(i).value === targetVal) {
        // 找到了
        break;
    }
}
```

### 9.9 关键帧值获取与设置

注意：表达式只能读取关键帧值，不能设置。设置需要通过脚本（.jsx）实现。

```js
// 读取关键帧值
firstVal = key(1).value;
lastVal = key(numKeys).value;

// 关键帧间线性插值
if (numKeys >= 2) {
    n = nearestKey(time).index;
    if (n > 1 && time < key(n).time) n--;
    if (n >= 1 && n < numKeys) {
        k1 = key(n);
        k2 = key(n + 1);
        linear(time, k1.time, k2.time, k1.value, k2.value);
    } else {
        value;
    }
} else {
    value;
}
```

### 9.10 10个关键帧操作表达式

```js
// 1. 关键帧触发动画
n = nearestKey(time).index;
if (key(n).time > time) n--;
if (n > 0) {
    t = time - key(n).time;
    linear(t, 0, 0.5, 100, 0);
} else {
    100;
}

// 2. 关键帧间弹性
n = nearestKey(time).index;
if (key(n).time > time) n--;
if (n > 0) {
    t = time - key(n).time;
    amp = 20;
    freq = 5;
    decay = 3;
    value + amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
} else {
    value;
}

// 3. 关键帧速度
n = nearestKey(time).index;
if (key(n).time > time) n--;
v = velocityAtTime(key(n).time - 0.001);
length(v);

// 4. 关键帧间缓动
if (numKeys >= 2) {
    n = nearestKey(time).index;
    if (time < key(n).time) n--;
    if (n >= 1 && n < numKeys) {
        k1 = key(n);
        k2 = key(n + 1);
        t = (time - k1.time) / (k2.time - k1.time);
        easeOut(t, 0, 1, k1.value, k2.value);
    }
}

// 5. 关键帧值映射
n = nearestKey(time).index;
if (key(n).time > time) n--;
key(n).value * 2;

// 6. 关键帧计数
numKeys;

// 7. 第一个关键帧值
key(1).value;

// 8. 最后一个关键帧值
key(numKeys).value;

// 9. 关键帧时间列表
times = [];
for (i = 1; i <= numKeys; i++) times.push(key(i).time);
times;

// 10. 关键帧触发事件
n = nearestKey(time).index;
if (key(n).time > time) n--;
if (n > 0 && time - key(n).time < 0.1) {
    100;  // 关键帧后0.1秒内显示
} else {
    0;
}
```

---

## 十、图层查询函数

### 10.1 thisComp.layer(index)

```js
thisComp.layer(1)  // 第1个图层
thisComp.layer(2)  // 第2个图层
thisComp.layer(index)  // 当前图层
thisComp.layer(index + 1)  // 下一个图层
thisComp.layer(index - 1)  // 上一个图层
```

### 10.2 thisComp.layer("name")

```js
thisComp.layer("控制器")  // 按名称引用
thisComp.layer("Null 1")
thisComp.layer("音频层")
```

### 10.3 图层属性访问

```js
// 基本属性
layer.transform.position
layer.transform.scale
layer.transform.rotation
layer.transform.opacity
layer.transform.anchorPoint

// 高级属性
layer.name
layer.index
layer.inPoint
layer.outPoint
layer.startTime
layer.enabled
layer.active
layer.parent
layer.source

// 3D属性
layer.transform.orientation
layer.transform.xRotation
layer.transform.yRotation
layer.transform.rotationZ

// 文本属性
layer.text.sourceText

// 音频属性
layer.audioLevels
```

### 10.4 comp("name") - 引用其他合成

```js
comp("其他合成")  // 引用指定名称的合成
comp("其他合成").layer(1).transform.position
comp("主合成").duration
```

### 10.5 图层关系：parent, index

```js
// 父图层
parentLayer = thisLayer.parent;
if (parentLayer != null) {
    parentLayer.transform.position;
}

// 图层索引
thisLayer.index
thisComp.numLayers  // 总图层数

// 相对索引
prevLayer = thisComp.layer(index - 1);
nextLayer = thisComp.layer(index + 1);
```

### 10.6 图层时间控制

```js
// 图层入出点
layer.inPoint
layer.outPoint

// 图层源时间
sourceTime = time - layer.startTime;

// 图层是否活跃
if (time >= layer.inPoint && time <= layer.outPoint) {
    // 图层在当前时间可见
}

// 图层时间偏移
layer.transform.position.valueAtTime(time - layer.startTime);
```

### 10.7 图层可见性判断

```js
// 检查图层是否在当前时间活跃
isActive = thisLayer.active;

// 检查是否在时间范围内
inRange = time >= inPoint && time < outPoint;

// 检查是否启用
isEnabled = thisLayer.enabled;

// 检查是否有视频
hasVideo = thisLayer.hasVideo;

// 综合判断
isVisible = thisLayer.active && thisLayer.enabled && thisLayer.hasVideo;
```

### 10.8 10个图层操作表达式

```js
// 1. 跟随其他图层位置
thisComp.layer("目标").transform.position;

// 2. 跟随并延迟
target = thisComp.layer("目标").transform.position;
target.valueAtTime(time - 0.3);

// 3. 相对位置
target = thisComp.layer("目标").transform.position;
target + [100, 0];  // 在目标右侧100px

// 4. 图层索引错位
offset = index * 0.1;
valueAtTime(time - offset);

// 5. 父图层跟随
if (parent != null) {
    parent.transform.position + [100, 0];
} else {
    value;
}

// 6. 相邻图层缩放
thisComp.layer(index - 1).transform.scale * 0.9;

// 7. 图层计数
thisComp.numLayers;

// 8. 最后一个图层特殊处理
if (index == thisComp.numLayers) {
    100;
} else {
    50;
}

// 9. 图层选择
targetIndex = effect("滑块")("滑块");
thisComp.layer(targetIndex).transform.position;

// 10. 多图层平均位置
sum = [0, 0];
for (i = 1; i <= 5; i++) {
    sum += thisComp.layer(i).transform.position;
}
sum / 5;
```

---

## 十一、合成函数

### 11.1 comp("name")

```js
comp("合成名称")  // 引用指定合成

// 基本属性
comp("主合成").width
comp("主合成").height
comp("主合成").duration
comp("主合成").frameRate
comp("主合成").numLayers
```

### 11.2 合成属性访问

```js
// 当前合成
thisComp.name
thisComp.width
thisComp.height
thisComp.duration
thisComp.frameRate
thisComp.frameDuration
thisComp.bgColor
thisComp.pixelAspect
thisComp.activeCamera
thisComp.numLayers

// 其他合成
comp("其他合成").layer("图层名").transform.position
```

### 11.3 多合成引用

```js
// 同时引用多个合成
mainComp = comp("主合成");
subComp = comp("子合成");
refComp = comp("参考合成");

// 跨合成引用图层
mainPos = mainComp.layer("图层1").transform.position;
subPos = subComp.layer("图层2").transform.position;
length(mainPos, subPos);
```

### 11.4 合成嵌套表达式

```js
// 当前合成被嵌套到其他合成中时的引用
// thisComp 始终引用表达式所在的合成

// 跨合成时间转换
mainTime = comp("主合成").layer("嵌套层").time;  // 主合成中的时间
localTime = time;  // 当前合成时间

// 跨合成坐标转换
mainPos = comp("主合成").layer("目标").toComp([0,0]);
localPos = fromComp(mainPos);
```

### 11.5 10个合成操作表达式

```js
// 1. 合成尺寸自适应
scaleFactor = thisComp.width / 1920;
value * scaleFactor;

// 2. 合成中心
[thisComp.width/2, thisComp.height/2];

// 3. 跨合成引用
comp("主合成").layer("控制器").effect("滑块")("滑块");

// 4. 合成时长归一化
t = time / thisComp.duration;
linear(t, 0, 1, 0, 100);

// 5. 帧率自适应
frameNum = time * thisComp.frameRate;

// 6. 合成切换
if (thisComp.name == "英文版") {
    "Hello";
} else {
    "你好";
}

// 7. 多合成参数同步
globalVal = comp("主合成").layer("全局控制").effect("值")("滑块");
globalVal;

// 8. 合成背景色驱动
thisComp.bgColor;

// 9. 嵌套合成时间映射
parentLayer = comp("主合成").layer(thisComp.name);
parentLayer.startTime;

// 10. 合成宽高比
aspect = thisComp.width / thisComp.height;
[aspect, 1] * 100;
```

---

## 十二、文字表达式

### 12.1 textIndex - 文字索引

```js
textIndex  // 当前字符的索引（在动画器中使用）

// 每个字符的延迟
delay = textIndex * 0.05;
linear(time, inPoint + delay, inPoint + delay + 0.3, 0, 100);
```

### 12.2 textTotal - 文字总数

```js
textTotal  // 文字总字符数

// 归一化进度
progress = textIndex / textTotal;
```

### 12.3 sourceText - 源文字

```js
text.sourceText  // 文字内容

// 读取文字
myText = text.sourceText.value;
myText.length;  // 字符数

// 动态文字
timecode = timeToTimecode(time);
"time: " + timecode;
```

### 12.4 文字逐字动画表达式

```js
// 在文本动画器中应用
// 每个字符从下方淡入
charDelay = 0.05;
charDuration = 0.3;
startTime = inPoint + textIndex * charDelay;

yOffset = linear(time, startTime, startTime + charDuration, 50, 0);
opacity = linear(time, startTime, startTime + charDuration, 0, 100);

// 应用到位置
value + [0, yOffset];

// 应用到不透明度
opacity;
```

### 12.5 文字颜色表达式

```js
// 逐字变色
hue = (textIndex / textTotal) * 360;
hslToRgb(hue / 360, 1, 0.5);

// 或者使用HSL直接
hue = (textIndex / textTotal + time * 0.1) % 1;
hslToRgb(hue, 1, 0.5);

function hslToRgb(h, s, l) {
    var r, g, b;
    if (s == 0) {
        r = g = b = l;
    } else {
        var hue2rgb = function(p, q, t) {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };
        var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        var p = 2 * l - q;
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
    }
    return [r, g, b];
}
```

### 12.6 文字位置表达式

```js
// 逐字波浪起伏
wave = Math.sin((time + textIndex * 0.2) * 3) * 20;
value + [0, wave];

// 逐字螺旋
angle = textIndex * 30 + time * 360;
radius = 50;
x = Math.cos(angle * Math.PI / 180) * radius;
y = Math.sin(angle * Math.PI / 180) * radius;
value + [x, y];

// 文字逐字跳跃
jump = Math.abs(Math.sin(time * 4 + textIndex * 0.5)) * 30;
value + [0, -jump];
```

### 12.7 10个文字动画表达式

```js
// 1. 打字机效果
txt = "Hello World";
visibleChars = Math.floor(time * 5);
txt.substr(0, Math.min(visibleChars, txt.length));

// 2. 逐字淡入
delay = textIndex * 0.05;
linear(time, inPoint + delay, inPoint + delay + 0.3, 0, 100);

// 3. 逐字缩放
delay = textIndex * 0.05;
scale = linear(time, inPoint + delay, inPoint + delay + 0.3, 0, 100);
[scale, scale];

// 4. 逐字旋转
delay = textIndex * 0.05;
linear(time, inPoint + delay, inPoint + delay + 0.5, -180, 0);

// 5. 逐字位置波动
Math.sin(time * 3 + textIndex * 0.3) * 10;

// 6. 文字颜色渐变
hue = textIndex / textTotal;
hslToRgb(hue, 1, 0.5);

// 7. 随机字符抖动
seedRandom(textIndex, true);
random(-10, 10);

// 8. 时间码显示
timeToTimecode(time);

// 9. 帧数显示
"Frame: " + Math.floor(time * thisComp.frameRate);

// 10. 逐字3D旋转
delay = textIndex * 0.05;
angle = linear(time, inPoint + delay, inPoint + delay + 0.5, 90, 0);
Math.sin(angle * Math.PI / 180) * 100;  // 模拟3D翻转
```

---

## 十三、音频表达式

### 13.1 audioLevels

```js
audioLevels  // [左声道, 右声道] 单位dB

// 基本用法
audio = audioLevels;
leftChannel = audio[0];
rightChannel = audio[1];
average = (audio[0] + audio[1]) / 2;

// 转换为线性振幅
linearLevel = Math.pow(10, average / 20);
```

### 13.2 audioActive

```js
audioActive  // 音频是否活跃（布尔值）

if (audioActive) {
    // 音频开关已打开
}
```

### 13.3 音频驱动动画表达式

```js
// 音频驱动缩放
audioLayer = thisComp.layer("音频");
audio = audioLayer.audioLevels;
avg = (audio[0] + audio[1]) / 2;
// dB转百分比（近似）
amp = Math.max((avg + 48) * 2, 0);  // -48dB到0dB映射到0-96
scale = 100 + amp;
[scale, scale];

// 音频驱动位置
audioLayer = thisComp.layer("音频");
avg = (audioLayer.audioLevels[0] + audioLayer.audioLevels[1]) / 2;
amp = Math.max((avg + 48) * 3, 0);
value + [0, -amp];
```

### 13.4 频率分析表达式

```js
// 使用Audio Spectrum效果
audioLayer = thisComp.layer("音频");
spectrum = audioLayer.effect("Audio Spectrum")("结束频率");

// 读取特定频率
bass = audioLayer.effect("Audio Spectrum")("频率 1");
mid = audioLayer.effect("Audio Spectrum")("频率 2");
treble = audioLayer.effect("Audio Spectrum")("频率 3");

// 不同频段驱动不同属性
bassScale = 100 + bass * 0.5;
midRotation = mid * 0.3;
trebleOpacity = 50 + treble * 0.5;
```

### 13.5 10个音频驱动表达式

```js
// 1. 音频驱动缩放
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
amp = Math.max((avg + 48) * 2, 0);
s = 100 + amp;
[s, s];

// 2. 音频驱动旋转
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
angle = (avg + 48) * 5;
angle;

// 3. 音频驱动位置
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
amp = Math.max((avg + 48) * 2, 0);
value + [Math.sin(time*10)*amp, 0];

// 4. 音频驱动透明度
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
linear(avg, -48, 0, 0, 100);

// 5. 音频驱动颜色
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
intensity = linear(avg, -48, 0, 0, 1);
[intensity, intensity * 0.5, 0, 1];

// 6. 立体声声像
audio = thisComp.layer("音频").audioLevels;
pan = audio[0] - audio[1];
value + [pan * 10, 0];

// 7. 音频触发闪烁
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
if (avg > -10) 100; else 50;

// 8. 平滑音频响应
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
smoothVal = smooth(0.2, 5);
linear(smoothVal, -48, 0, 0, 100);

// 9. 音频频谱条
freq = effect("Audio Spectrum")("频率");
freq * 100;

// 10. 节拍检测（简化）
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
threshold = -15;
isBeat = avg > threshold;
isBeat ? 100 : 50;
```

---

## 十四、路径表达式

### 14.1 path - 路径对象

```js
// 在路径属性上应用表达式
mask("遮罩 1").maskPath  // 遮罩路径
thisComp.layer("形状层").content("形状 1").content("路径 1").path  // 形状路径
```

### 14.2 path.points()

```js
path.points(t = time)  // 返回路径上的所有点

// 获取所有点
myPath = mask("遮罩 1").maskPath;
pts = myPath.points();
// pts = [[x1,y1], [x2,y2], ...]

// 第一个点
pts[0]

// 点的数量
pts.length
```

### 14.3 path.inTangents() / path.outTangents()

```js
path.inTangents()   // 返回所有点的入切线
path.outTangents()  // 返回所有点的出切线

// 获取切线
myPath = mask("遮罩 1").maskPath;
inTans = myPath.inTangents();
outTans = myPath.outTangents();
```

### 14.4 path.isClosed()

```js
path.isClosed()  // 返回路径是否闭合

if (mask("遮罩 1").maskPath.isClosed()) {
    // 闭合路径
}
```

### 14.5 path.pointOnPath()

```js
path.pointOnPath(percentage = 0, t = time)
// percentage: 0-1，路径上的位置
// t: 时间

// 路径起点
path.pointOnPath(0)

// 路径终点
path.pointOnPath(1)

// 路径中点
path.pointOnPath(0.5)

// 沿路径运动
myPath = thisComp.layer("路径层").content("路径 1").path;
progress = (time % 5) / 5;  // 5秒循环
myPath.pointOnPath(progress);
```

### 14.6 path.tangentOnPath()

```js
path.tangentOnPath(percentage = 0, t = time)
// 返回路径上某点的切线方向

// 让对象沿路径方向旋转
myPath = thisComp.layer("路径层").content("路径 1").path;
progress = (time % 5) / 5;
pos = myPath.pointOnPath(progress);
tan = myPath.tangentOnPath(progress);
angle = Math.atan2(tan[1], tan[0]) * 180 / Math.PI;
```

### 14.7 path.normalOnPath()

```js
path.normalOnPath(percentage = 0, t = time)
// 返回路径上某点的法线方向
```

### 14.8 路径动画表达式

```js
// 对象沿遮罩路径运动
myPath = thisComp.layer("控制层").mask("遮罩 1").maskPath;
progress = linear(time, 0, 5, 0, 1);  // 5秒走完路径
myPath.pointOnPath(progress);

// 旋转跟随路径
tan = myPath.tangentOnPath(progress);
Math.atan2(tan[1], tan[0]) * 180 / Math.PI;
```

### 14.9 10个路径动画表达式

```js
// 1. 沿路径运动
path = thisComp.layer("路径层").content("路径 1").path;
t = (time % 4) / 4;
path.pointOnPath(t);

// 2. 路径上的位置
path = mask("遮罩 1").maskPath;
path.pointOnPath(0.5);

// 3. 路径跟随旋转
path = thisComp.layer("路径层").content("路径 1").path;
t = (time % 4) / 4;
tan = path.tangentOnPath(t);
Math.atan2(tan[1], tan[0]) * 180 / Math.PI;

// 4. 往返路径
path = thisComp.layer("路径层").content("路径 1").path;
t = (time % 8) / 8;
t = t < 0.5 ? t * 2 : 2 - t * 2;
path.pointOnPath(t);

// 5. 多对象沿路径分布
path = thisComp.layer("路径层").content("路径 1").path;
numObjects = 10;
myT = (index - 1) / numObjects;
path.pointOnPath(myT);

// 6. 路径长度估算
path = thisComp.layer("路径层").content("路径 1").path;
pts = path.points();
totalLen = 0;
for (i = 0; i < pts.length - 1; i++) {
    totalLen += length(pts[i], pts[i+1]);
}
totalLen;

// 7. 路径变形（沿路径）
path = mask("遮罩 1").maskPath;
offset = wiggle(1, 0.1);
path.pointOnPath((time % 2) / 2 + offset[0] * 0.01);

// 8. 路径上的速度
path = thisComp.layer("路径层").content("路径 1").path;
t1 = (time % 4) / 4;
t2 = ((time + 0.01) % 4) / 4;
p1 = path.pointOnPath(t1);
p2 = path.pointOnPath(t2);
length(p2 - p1) * 100;

// 9. 闭合路径检测
path = mask("遮罩 1").maskPath;
path.isClosed() ? 100 : 0;

// 10. 路径点列表
path = mask("遮罩 1").maskPath;
path.points().length;
```

---

## 十五、3D表达式

### 15.1 3D位置 [x,y,z]

```js
// 3D位置属性
[x, y, z]

// 3D缩放
[scaleX, scaleY, scaleZ]

// 3D旋转
orientation  // [x, y, z] 方向
xRotation    // X轴旋转
yRotation    // Y轴旋转
rotationZ    // Z轴旋转
```

### 15.2 toWorld(point)

```js
toWorld(point, t = time)
// 图层空间 → 世界空间

// 获取图层在世界空间的位置
worldPos = toWorld([0, 0, 0]);

// 获取锚点在世界空间的位置
worldAnchor = toWorld(transform.anchorPoint);
```

### 15.3 fromWorld(point)

```js
fromWorld(point, t = time)
// 世界空间 → 图层空间

// 获取世界原点在图层空间的位置
localOrigin = fromWorld([0, 0, 0]);

// 获取其他3D图层在当前图层空间的位置
otherLayer = thisComp.layer("3D层");
otherWorldPos = otherLayer.toWorld([0, 0, 0]);
localPos = fromWorld(otherWorldPos);
```

### 15.4 toComp(point) / fromComp(point)

```js
toComp(point, t = time)
// 图层空间 → 合成空间（2D投影）

fromComp(point, t = time)
// 合成空间 → 图层空间

// 3D图层在合成中的2D位置
worldPos = toWorld([0, 0, 0]);
compPos = toComp([0, 0, 0]);
```

### 15.5 摄像机距离计算

```js
// 计算图层到摄像机的距离
camPos = thisComp.activeCamera.toWorld([0, 0, 0]);
layerPos = toWorld([0, 0, 0]);
distance = length(camPos, layerPos);

// 根据距离调整缩放（远近大小变化）
camPos = thisComp.activeCamera.toWorld([0, 0, 0]);
layerPos = toWorld([0, 0, 0]);
dist = length(camPos, layerPos);
focalLength = thisComp.activeCamera.cameraOption.zoom;
scaleFactor = focalLength / dist;
value * scaleFactor;
```

### 15.6 3D朝向表达式

```js
// 让3D图层朝向另一个3D图层
target = thisComp.layer("目标");
myPos = toWorld([0, 0, 0]);
targetPos = target.toWorld([0, 0, 0]);

// 计算朝向
lookAt = targetPos - myPos;

// 转换为旋转角度
// Y轴朝向
yAngle = Math.atan2(lookAt[0], lookAt[2]) * 180 / Math.PI;

// X轴朝向
xyDist = Math.sqrt(lookAt[0]*lookAt[0] + lookAt[2]*lookAt[2]);
xAngle = Math.atan2(lookAt[1], xyDist) * 180 / Math.PI;

[xAngle, yAngle, 0];  // 应用到orientation
```

### 15.7 3D空间关系

```js
// 父子图层位置继承
if (parent != null) {
    parentWorldPos = parent.toWorld([0, 0, 0]);
    myLocalPos = fromWorld(parentWorldPos);
    // ...
}

// 3D图层朝向摄像机
camPos = thisComp.activeCamera.toWorld([0, 0, 0]);
myPos = toWorld([0, 0, 0]);
diff = camPos - myPos;
xyDist = Math.sqrt(diff[0]*diff[0] + diff[2]*diff[2]);
xRot = -Math.atan2(diff[1], xyDist) * 180 / Math.PI;
yRot = Math.atan2(diff[0], diff[2]) * 180 / Math.PI;
[xRot, yRot, 0];
```

### 15.8 10个3D表达式

```js
// 1. 3D位置摆动
w = wiggle(2, 50);
value + [w[0], w[1], w[2]];

// 2. 朝向摄像机
camPos = thisComp.activeCamera.toWorld([0,0,0]);
myPos = toWorld([0,0,0]);
diff = camPos - myPos;
xyDist = Math.sqrt(diff[0]*diff[0] + diff[2]*diff[2]);
xRot = -Math.atan2(diff[1], xyDist) * 180 / Math.PI;
yRot = Math.atan2(diff[0], diff[2]) * 180 / Math.PI;
[xRot, yRot, 0];

// 3. 距离驱动透明度
camPos = thisComp.activeCamera.toWorld([0,0,0]);
myPos = toWorld([0,0,0]);
dist = length(camPos, myPos);
linear(dist, 500, 2000, 100, 0);

// 4. 3D旋转
[time*30, time*45, time*60];

// 5. Z轴距离效果
camPos = thisComp.activeCamera.toWorld([0,0,0]);
myPos = toWorld([0,0,0]);
zDist = Math.abs(camPos[2] - myPos[2]);
linear(zDist, 0, 1000, 1, 0.5);

// 6. 3D位置循环
radius = 200;
angle = time * 2;
x = Math.cos(angle) * radius;
z = Math.sin(angle) * radius;
value + [x, 0, z];

// 7. 3D摆动
freq = 1;
amp = 100;
w = wiggle(freq, amp);
value + [w[0], Math.abs(w[1]), w[2]];

// 8. 3D图层吸附到地面
groundY = 0;
currentPos = value;
[currentPos[0], groundY, currentPos[2]];

// 9. 3D缩放随距离
camPos = thisComp.activeCamera.toWorld([0,0,0]);
myPos = toWorld([0,0,0]);
dist = length(camPos, myPos);
zoom = thisComp.activeCamera.cameraOption.zoom;
scale = zoom / dist * 100;
[scale, scale, scale];

// 10. 3D路径运动
radius = 200;
height = 50;
t = time * 0.5;
x = Math.cos(t) * radius;
y = Math.sin(t * 2) * height;
z = Math.sin(t) * radius;
[x, y, z];
```

---

## 十六、标记表达式

### 16.1 marker.numKeys

```js
marker.numKeys  // 标记数量

if (marker.numKeys > 0) {
    // 有标记
}
```

### 16.2 marker.key(index)

```js
marker.key(1)  // 第1个标记
marker.key(1).time  // 标记时间
marker.key(1).comment  // 标记注释
marker.key(1).duration  // 标记时长
marker.key(1).chapter  // 章节标题
marker.key(1).url  // URL链接
marker.key(1).frameTarget  // 帧目标
marker.key(1).eventCuePoint  // 是否为事件提示点
```

### 16.3 marker.nearestKey(time)

```js
marker.nearestKey(time)  // 最近的标记
marker.nearestKey(time).index  // 最近标记的索引

// 找到当前时间之前的最后一个标记
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;
```

### 16.4 标记触发动画

```js
// 标记后开始动画
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;

if (n > 0) {
    markerTime = marker.key(n).time;
    t = time - markerTime;
    // 在标记后1秒内淡入
    linear(t, 0, 1, 0, 100);
} else {
    0;
}
```

### 16.5 标记注释解析

```js
// 读取标记注释作为参数
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;

if (n > 0) {
    comment = marker.key(n).comment;
    // 解析注释中的数值
    // 例如注释为 "scale:150"
    match = comment.match(/scale:(\d+)/);
    if (match) {
        parseInt(match[1]);
    } else {
        100;
    }
} else {
    100;
}
```

### 16.6 10个标记驱动表达式

```js
// 1. 标记触发淡入
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;
if (n > 0) {
    t = time - marker.key(n).time;
    linear(t, 0, 0.5, 0, 100);
} else {
    0;
}

// 2. 标记触发缩放
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;
if (n > 0) {
    t = time - marker.key(n).time;
    amp = 20;
    freq = 5;
    decay = 3;
    100 + amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
} else {
    100;
}

// 3. 标记间循环
if (marker.numKeys >= 2) {
    n = marker.nearestKey(time).index;
    if (marker.key(n).time > time) n--;
    nextN = Math.min(n + 1, marker.numKeys);
    if (n > 0 && nextN > n) {
        t1 = marker.key(n).time;
        t2 = marker.key(nextN).time;
        linear(time, t1, t2, 0, 100);
    }
}

// 4. 标记注释驱动
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;
if (n > 0) {
    marker.key(n).comment;
} else {
    "无标记";
}

// 5. 标记计数
marker.numKeys;

// 6. 第一个标记时间
marker.numKeys > 0 ? marker.key(1).time : 0;

// 7. 最后一个标记时间
marker.numKeys > 0 ? marker.key(marker.numKeys).time : 0;

// 8. 标记触发旋转
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;
if (n > 0) {
    t = time - marker.key(n).time;
    t * 360;  // 每秒转360度
} else {
    0;
}

// 9. 标记触发位置变化
n = marker.nearestKey(time).index;
if (marker.key(n).time > time) n--;
if (n > 0) {
    t = time - marker.key(n).time;
    yOffset = Math.sin(t * 10) * 50 * Math.exp(-t * 2);
    value + [0, yOffset];
} else {
    value;
}

// 10. 标记时长内的特殊效果
n = marker.nearestKey(time).index;
if (n > 0) {
    m = marker.key(n);
    if (time >= m.time && time <= m.time + m.duration) {
        // 在标记时长内
        100;
    } else {
        50;
    }
} else {
    50;
}
```

---

## 十七、实用表达式库

### 50个最常用表达式

#### 位置动画

```js
// 1. 从下方弹入
t = time - inPoint;
if (t < 1) {
    amp = 100;
    freq = 4;
    decay = 3;
    y = amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
    value + [0, -y + linear(t, 0, 1, 200, 0)];
} else {
    value;
}

// 2. 匀速移动
speed = 200;  // 像素/秒
value + [speed * (time - inPoint), 0];

// 3. 圆周运动
radius = 200;
angle = time * 2;  // 弧度
x = Math.cos(angle) * radius;
y = Math.sin(angle) * radius;
value + [x, y];

// 4. 抛物线
g = 500;  // 重力
v0 = -300;  // 初速度
t = time - inPoint;
value + [200 * t, v0 * t + 0.5 * g * t * t];

// 5. 跟随鼠标（近似）
target = thisComp.layer("鼠标").transform.position;
value + (target - value) * 0.1;
```

#### 缩放动画

```js
// 6. 弹性缩放
t = time - inPoint;
if (t < 1) {
    freq = 5;
    decay = 4;
    amp = 0.3;
    scale = 1 + amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
    value * scale;
} else {
    value;
}

// 7. 脉冲缩放
pulse = 1 + Math.sin(time * 4) * 0.1;
value * pulse;

// 8. 从0到100%
linear(time, inPoint, inPoint + 0.5, [0, 0], value);

// 9. 呼吸效果
breathe = 1 + Math.sin(time * 2) * 0.05;
value * breathe;

// 10. 音频驱动缩放
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
s = 100 + Math.max((avg + 48) * 2, 0);
[s, s];
```

#### 旋转动画

```js
// 11. 持续旋转
time * 360;

// 12. 摆动
amp = 30;
freq = 2;
Math.sin(time * freq * 2 * Math.PI) * amp;

// 13. 随机旋转
seedRandom(index, true);
random(-180, 180) + time * 30;

// 14. 朝向目标
target = thisComp.layer("目标").transform.position;
myPos = transform.position;
delta = target - myPos;
Math.atan2(delta[1], delta[0]) * 180 / Math.PI;

// 15. 弹性旋转
t = time - inPoint;
freq = 5;
decay = 4;
amp = 45;
value + amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
```

#### 透明度动画

```js
// 16. 淡入淡出
fadeIn = linear(time, inPoint, inPoint + 0.5, 0, 100);
fadeOut = linear(time, outPoint - 0.5, outPoint, 100, 0);
Math.min(fadeIn, fadeOut);

// 17. 闪烁
Math.sin(time * 10) > 0 ? 100 : 0;

// 18. 距离驱动透明度
target = thisComp.layer("目标").transform.position;
dist = length(transform.position, target);
linear(dist, 100, 500, 100, 0);

// 19. 音频驱动透明度
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
linear(avg, -48, 0, 0, 100);

// 20. 时间段控制
if (time > 2 && time < 5) {
    100;
} else {
    0;
}
```

#### 颜色动画

```js
// 21. 颜色循环
hue = (time * 0.1) % 1;
hslToRgb(hue, 1, 0.5);

// 22. 音频驱动颜色
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
intensity = linear(avg, -48, 0, 0, 1);
[1, intensity, 0, 1];

// 23. 颜色渐变
linear(time, 0, 5, [1, 0, 0], [0, 0, 1]);

// 24. 闪烁颜色
t = Math.sin(time * 5);
t > 0 ? [1, 0, 0] : [0, 0, 1];

// 25. 亮度驱动
ref = thisComp.layer("参考").effect("亮度")("亮度");
gray = ref / 100;
[gray, gray, gray, 1];
```

#### 时间控制

```js
// 26. 时间冻结
if (time > 3) {
    3;
} else {
    time;
}

// 27. 慢动作
time * 0.5;

// 28. 时间倒流
thisComp.duration - time;

// 29. 时间循环
cycleDur = 2;
t = (time - inPoint) % cycleDur;
inPoint + t;

// 30. 帧步进
step = framesToTime(4);
Math.floor(time / step) * step;
```

#### 物理模拟

```js
// 31. 弹簧
freq = 3;
decay = 4;
n = nearestKey(time).index;
if (key(n).time > time) n--;
if (n > 0) {
    t = time - key(n).time;
    v = -velocityAtTime(key(n).time - 0.001) * 5;
    value + v * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
} else {
    value;
}

// 32. 重力
g = 500;
t = Math.max(time - inPoint, 0);
value + [0, g * t * t * 0.5];

// 33. 惯性跟随
lag = 0.1;
target = thisComp.layer("目标").transform.position;
value + (target - value) * lag;

// 34. 阻尼振荡
amp = 100;
freq = 2;
decay = 0.5;
value + amp * Math.sin(freq * time * 2 * Math.PI) * Math.exp(-decay * time);

// 35. 弹性碰撞
t = time - inPoint;
bounce = Math.abs(Math.sin(t * 5)) * Math.exp(-t * 2);
value - bounce * 50;
```

#### 循环动画

```js
// 36. 无缝循环
loopOut("cycle");

// 37. 往返循环
loopOut("pingpong");

// 38. 持续移动
loopOut("offset");

// 39. 速度延续
loopOut("continue");

// 40. 段循环
loopOut("cycle", 2);
```

#### 随机效果

```js
// 41. 随机抖动
wiggle(2, 50);

// 42. 随机闪烁
seedRandom(Math.floor(time * 4), true);
random(50, 100);

// 43. 随机位置
seedRandom(index, true);
value + [random(-50, 50), random(-50, 50)];

// 44. 平滑噪声
noise(time * 0.5) * 50;

// 45. 多层叠加
w1 = wiggle(1, 20);
w2 = wiggle(5, 5);
value + w1 + w2;
```

#### 音频同步

```js
// 46. 音频驱动缩放
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
s = 100 + Math.max((avg + 48) * 2, 0);
[s, s];

// 47. 节拍同步
bpm = 120;
beatTime = 60 / bpm;
beat = Math.floor(time / beatTime);
if (time - beat * beatTime < 0.1) 100; else 50;

// 48. 音频驱动颜色
audio = thisComp.layer("音频").audioLevels;
avg = (audio[0] + audio[1]) / 2;
intensity = linear(avg, -48, 0, 0, 1);
[1, intensity * 0.5, 0, 1];

// 49. 频谱响应
freq = thisComp.layer("音频").effect("Audio Spectrum")("频率");
linear(freq, 0, 100, 50, 100);

// 50. 立体声像
audio = thisComp.layer("音频").audioLevels;
pan = audio[0] - audio[1];
value + [pan * 20, 0];
```

---

## 附录

### A. 表达式快捷键速查表

| 快捷键 | 功能 |
|--------|------|
| `Alt + 点击属性码表` | 添加表达式 |
| `Ctrl + Shift + E` | 启用/禁用表达式 |
| `Ctrl + Alt + =` | 展开表达式 |
| `Ctrl + Alt + -` | 折叠表达式 |
| `Esc` | 退出表达式编辑 |
| `Alt + 点击码表` | 添加/移除表达式 |
| `Ctrl + 点击表达式` | 禁用表达式 |

### B. 表达式性能优化清单

1. **缓存重复计算**：使用变量存储重复调用的值
2. **避免每帧随机**：使用 `seedRandom(seed, true)` 保持稳定
3. **减少跨合成引用**：`comp()` 调用开销大
4. **简化循环**：避免大量 `valueAtTime()` 查询
5. **使用内置函数**：`wiggle()`、`loopOut()` 比手动实现快
6. **减少关键帧查询**：缓存 `key()` 结果
7. **避免递归**：表达式不支持真正的递归
8. **使用简单运算**：加减乘除比函数调用快

### C. 常见错误与解决方案

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| Expression result must be of dimension 2 | 返回值维度不匹配 | 检查返回数组维数 |
| Undefined value used in expression | 引用了不存在的对象 | 检查图层/属性名称 |
| Expected: ; | 语法错误 | 检查语句结尾 |
| Effect is deprecated | 使用了已弃用效果 | 使用新效果替代 |
| Out of memory | 内存不足 | 优化表达式，减少循环 |

### D. 表达式 vs 脚本对比

| 特性 | 表达式 | 脚本(.jsx) |
|------|--------|-----------|
| 运行时机 | 每帧自动运行 | 手动执行 |
| 作用范围 | 单个属性 | 整个项目 |
| 修改关键帧 | 不能 | 可以 |
| 创建图层 | 不能 | 可以 |
| UI交互 | 不能 | 可以 |
| 文件操作 | 不能 | 可以 |
| 性能 | 较慢 | 较快 |

### E. 推荐学习资源

- Adobe官方表达式文档
- AE表达式参考手册（Expression Reference）
- Dan Ebberts的MotionScript网站
- After Effects Expressions论坛
- YouTube表达式教程频道

---

## 结语

> 本手册涵盖了AE表达式的所有核心函数和常用模式。掌握这些内容，可以应对95%以上的AE动画自动化需求。表达式是AE最强大的功能之一，熟练运用可以大幅提升工作效率，实现许多手动关键帧无法实现的效果。
> 
> **核心理念**：表达式不是用来替代关键帧的，而是用来增强关键帧的。最好的工作流通常是：关键帧定义主要动画，表达式处理细节和自动化。
> 
> **实践建议**：
> 1. 从简单表达式开始，逐步增加复杂度
> 2. 养成注释习惯，方便日后维护
> 3. 建立自己的表达式库，复用常用代码
> 4. 多参考优秀作品的表达式实现
> 5. 理解原理比记忆代码更重要

---

*文档版本：完整版 v2.0*  
*覆盖函数：300+*  
*实战表达式：300+*  
*最后更新：2024*
