# AE 表达式进阶手册

> 版本: 2025-v1 | 适用: 高级表达式/表达式控制/性能优化

## 一、表达式基础

### 1.1 表达式语法

| 语法 | 说明 | 示例 |
|------|------|------|
| value | 当前值 | value |
| time | 当前时间(秒) | time |
| thisComp | 当前合成 | thisComp.width |
| thisLayer | 当前图层 | thisLayer.opacity |
| effect | 效果 | effect("Slider")("Slider") |

### 1.2 常用表达式

```javascript
// 循环动画
loopOut(type: "cycle", numKeyframes: 0);
loopOut(type: "pingpong", numKeyframes: 0);
loopOut(type: "offset", numKeyframes: 0);

// 随机值
random(minVal, maxVal);
seedRandom(seed, timeless: false);

// 线性映射
linear(t, tMin, tMax, value1, value2);
ease(t, tMin, tMax, value1, value2);

// 数学运算
Math.sin(time);
Math.cos(time);
Math.random();
Math.floor(value);
Math.ceil(value);
```

## 二、高级表达式技术

### 2.1 表达式控制

| 控制 | 用途 | 示例 |
|------|------|------|
| 滑块控制 | 数值控制 | 控制位置/大小 |
| 角度控制 | 角度控制 | 控制旋转 |
| 颜色控制 | 颜色控制 | 控制颜色 |
| 复选框控制 | 开关控制 | 启用/禁用 |
| 点控制 | 2D/3D点 | 控制位置 |
| 图层控制 | 图层选择 | 链接图层 |

```javascript
// 滑块控制
var slider = effect("Slider Control")("Slider");
value + slider;

// 颜色控制
var color = effect("Color Control")("Color");
color;

// 复选框控制
var enabled = effect("Checkbox Control")("Checkbox");
if (enabled) value; else 0;
```

### 2.2 表达式链接

```javascript
// 链接到其他属性
var source = thisComp.layer("Layer 1").transform.position;
source;

// 链接到效果参数
var effectVal = thisComp.layer("Layer 1").effect("Blur")("Blurriness");
effectVal;

// 链接到表达式控制
var control = thisComp.layer("Control").effect("Slider")("Slider");
value * control;
```

## 三、动画表达式

### 3.1 缓动表达式

```javascript
// 弹性缓动
var freq = 3;
var decay = 5;
var n = 0;
if (numKeys > 0) {
    n = nearestKey(time).index;
    if (key(n).time > time) n--;
}
if (n > 0) {
    var t = time - key(n).time;
    var amp = velocityAtTime(key(n).time - 0.001);
    var omega = freq * Math.PI * 2;
    var x = amp * Math.exp(-decay * t) * Math.sin(omega * t);
    value + x;
} else {
    value;
}

// 平滑缓动
var smoothVal = smooth(width, 0.5);
smoothVal;

// 指数缓动
var t = time - inPoint;
var duration = 1;
var startVal = 0;
var endVal = 100;
var progress = Math.min(t / duration, 1);
var eased = 1 - Math.pow(1 - progress, 3);
startVal + (endVal - startVal) * eased;
```

### 3.2 物理模拟

```javascript
// 重力模拟
var gravity = 980; // pixels/sec^2
var initialVelocity = -500;
var t = time - inPoint;
var y = initialVelocity * t + 0.5 * gravity * t * t;
value + [0, y];

// 弹簧模拟
var anchor = [0, 0];
var stiffness = 100;
var damping = 10;
var mass = 1;
// 简化弹簧公式
var displacement = value - anchor;
var force = -stiffness * displacement;
var acceleration = force / mass;
value + acceleration * time * time;

// 摆动
var freq = 2;
var amp = 50;
var offset = amp * Math.sin(freq * time * Math.PI * 2);
value + offset;
```

## 四、条件表达式

### 4.1 条件判断

```javascript
// if-else
var threshold = 50;
if (value > threshold) {
    100;
} else {
    0;
}

// 三元运算符
var result = value > 50 ? 100 : 0;
result;

// switch
var day = 1;
switch (day) {
    case 1: "Monday"; break;
    case 2: "Tuesday"; break;
    default: "Other";
}
```

### 4.2 循环表达式

```javascript
// for循环
var sum = 0;
for (var i = 0; i < 10; i++) {
    sum += i;
}
sum;

// while循环
var count = 0;
var total = 0;
while (count < 10) {
    total += count;
    count++;
}
total;

// 数组遍历
var arr = [1, 2, 3, 4, 5];
var sum = 0;
for (var i = 0; i < arr.length; i++) {
    sum += arr[i];
}
sum;
```

## 五、表达式与数据

### 5.1 数组操作

```javascript
// 创建数组
var arr = [1, 2, 3, 4, 5];

// 访问元素
var first = arr[0];
var last = arr[arr.length - 1];

// 数组方法
var sorted = arr.sort();
var reversed = arr.reverse();
var sliced = arr.slice(1, 3);

// 数组计算
var sum = arr.reduce(function(a, b) { return a + b; }, 0);
var max = Math.max.apply(null, arr);
var min = Math.min.apply(null, arr);
```

### 5.2 对象操作

```javascript
// 创建对象
var obj = {
    x: 100,
    y: 200,
    name: "Layer"
};

// 访问属性
var x = obj.x;
var name = obj["name"];

// 修改属性
obj.x = 150;

// 遍历对象
for (var key in obj) {
    var val = obj[key];
}
```

## 六、性能优化

### 6.1 表达式优化

```javascript
// 避免重复计算
// 不好
value + Math.sin(time) + Math.sin(time);

// 好
var sinVal = Math.sin(time);
value + sinVal + sinVal;

// 缓存计算结果
var pos = thisComp.layer("Layer 1").transform.position;
var x = pos[0];
var y = pos[1];
[x, y];

// 避免不必要的图层引用
// 不好
thisComp.layer("Layer 1").transform.position;
thisComp.layer("Layer 1").transform.position;

// 好
var layer = thisComp.layer("Layer 1");
var pos = layer.transform.position;
```

### 6.2 表达式错误处理

```javascript
// try-catch
try {
    var val = thisComp.layer("NonExistent").transform.position;
    val;
} catch (e) {
    [0, 0];
}

// 检查图层存在
var layerExists = thisComp.layer("Layer 1") != null;
if (layerExists) {
    thisComp.layer("Layer 1").transform.position;
} else {
    [0, 0];
}
```

## 七、表达式库

### 7.1 常用表达式库

```javascript
//  Wiggle(随机抖动)
function wiggle(freq, amp) {
    var t = time * freq;
    var x = amp * (Math.sin(t) + Math.sin(t * 2.3) * 0.5);
    var y = amp * (Math.cos(t) + Math.cos(t * 2.7) * 0.5);
    return value + [x, y];
}

//  Bounce(弹跳)
function bounce(t, amp, freq, decay) {
    return amp * Math.sin(t * freq * Math.PI * 2) * Math.exp(-decay * t);
}

//  Smooth(平滑)
function smooth(val, smoothness) {
    return smooth(val, smoothness);
}

//  Clamp(限制范围)
function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
}
```

## 八、最佳实践

### 8.1 表达式规范

- 使用变量存储重复计算
- 添加注释说明
- 避免过长的单行表达式
- 使用表达式控制简化调整
- 测试边界情况

### 8.2 调试技巧

- 使用trace()输出调试信息
- 检查表达式错误提示
- 简化表达式逐步测试
- 使用表达式选择器预览
