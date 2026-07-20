# AE表达式与脚本完全手册

> 适用于 After Effects 2026 | ExtendScript ES3 兼容版

> **相关文档**：本文为表达式与脚本基础完全手册。如需进阶技巧与高级应用，参见 [[AE表达式进阶宝典]]

---

## 一、表达式基础

### 1.1 什么是表达式（Expression）

表达式是 After Effects 中一种强大的编程工具，允许用户通过编写 JavaScript 代码来动态控制图层属性的数值。与手动设置关键帧不同，表达式可以根据预设的数学逻辑、其他图层的状态或时间变化自动计算属性值。

**核心概念：**
- 表达式是一段 JavaScript 代码，运行在 AE 的属性计算管道中
- 表达式的返回值会成为属性在当前时间的值
- 表达式在每一帧都会重新计算
- 表达式可以引用其他图层、效果、合成的属性值

### 1.2 表达式与关键帧的关系

表达式和关键帧可以同时存在于同一个属性上，它们的关系如下：

| 关系类型 | 说明 |
|---------|------|
| 表达式替代关键帧 | 表达式返回值直接作为属性值，关键帧被忽略 |
| 表达式读取关键帧 | 表达式可以通过 `value` 或 `valueAtTime()` 读取关键帧的值 |
| 关键帧驱动表达式 | 表达式以关键帧值为基础进行二次计算 |
| 混合使用 | 表达式可以在关键帧之间进行插值或扩展 |

**重要：** 当属性上有表达式时，属性值由表达式决定，关键帧的值可以被表达式读取但不会直接输出。

### 1.3 表达式的优势与限制

#### 优势
1. **动态联动**：一个属性的变化可以自动影响其他属性
2. **复杂动画**：用数学公式实现关键帧难以完成的复杂运动
3. **批量控制**：一个控制器可以同时控制多个图层
4. **实时更新**：修改参数后立即看到效果，无需逐帧调整
5. **可复用性**：表达式可以复制粘贴到其他属性
6. **随机性**：轻松实现随机变化的动画效果
7. **音频驱动**：根据音频振幅自动生成动画

#### 限制
1. **性能开销**：复杂表达式会增加渲染时间
2. **ES3 语法**：仅支持 JavaScript ES3 标准，不支持现代语法
3. **调试困难**：错误提示有限，调试不如专业 IDE
4. **单帧计算**：无法跨帧保存状态（需用特殊技巧）
5. **安全限制**：无法访问文件系统、网络等外部资源
6. **学习曲线**：需要一定的编程基础

### 1.4 表达式语言基础（JavaScript ES3）

After Effects 表达式基于 **ExtendScript**，这是 Adobe 对 JavaScript ES3 标准的扩展实现。

**支持的特性：**
- 变量声明（var）
- 基本数据类型（Number, String, Boolean, Array, Object, null, undefined）
- 运算符（算术、比较、逻辑、赋值、三元）
- 条件语句（if/else, switch）
- 循环语句（for, while, do-while）
- 函数定义与调用
- 内置对象（Math, Date, String, Array, Number, Object, Boolean, RegExp）
- 正则表达式（有限支持）
- try/catch 异常处理

**不支持的特性：**
- let / const 变量声明
- 箭头函数（Arrow Functions）
- 模板字符串（Template Literals）
- 解构赋值（Destructuring）
- 类（Class）语法
- Promise / async/await
- ES6+ 的 Array 方法（如 map, filter, reduce, forEach 等）
- 模块化（import/export）
- 可选链操作符（?.）
- 空值合并操作符（??）

### 1.5 添加表达式的方法

#### 方法一：键盘快捷键（推荐）
1. 在时间轴面板中选中目标图层
2. 按 `U` 键展开所有关键帧属性，或按特定快捷键展开单个属性（如 `P` 展开位置）
3. 按住 **Alt** 键（Windows）或 **Option** 键（Mac），点击属性名称前的**秒表图标** ⏱️
4. 表达式输入框会出现在属性下方

#### 方法二：菜单命令
1. 选中属性
2. 选择菜单：`动画（Animation）` → `添加表达式（Add Expression）`

#### 方法三：快捷键
选中属性后按 **Alt + Shift + =**

### 1.6 表达式开关（启用/禁用）

添加表达式后，秒表图标会变成带有等号的样式 ⏱️=，表示表达式处于启用状态。

**操作方法：**
- **启用/禁用**：点击秒表图标左侧的表达式开关（等号图标），或在表达式输入框处于激活状态时按 `Enter` 键
- **临时禁用**：在表达式开头添加 `//` 注释掉整个表达式
- **删除表达式**：按住 Alt/Option 再次点击秒表图标，或选中表达式文本后删除

### 1.7 表达式错误提示与调试

当表达式出错时，AE 会在以下位置显示错误：

1. **属性名称旁**：会出现一个黄色的警告三角形 ⚠️
2. **信息面板**：显示具体的错误信息和行号
3. **表达式输入框**：错误行会高亮显示

**常见错误类型：**
- 语法错误（SyntaxError）：括号不匹配、缺少分号等
- 引用错误（ReferenceError）：引用了不存在的变量或属性
- 类型错误（TypeError）：对错误的数据类型调用方法
- 值错误（ValueError）：返回值类型与属性不匹配

---

## 二、表达式语法基础（ES3兼容）

### 2.1 变量声明（var）

在 AE 表达式中，只能使用 `var` 关键字声明变量，不支持 `let` 和 `const`。

```javascript
// 声明变量并赋值
var speed = 5;
var amplitude = 100;
var layerName = "控制层";

// 声明多个变量
var x = 0, y = 0, z = 0;

// 变量提升（ES3 特性，注意作用域）
// var 声明的变量只有函数作用域，没有块级作用域
function example() {
    var a = 10;
    if (true) {
        var b = 20; // b 在整个函数内都可见
    }
    return a + b; // 可以正常访问 b
}
```

**注意事项：**
- 变量名区分大小写
- 变量名必须以字母、下划线或 $ 开头
- 不能使用 JavaScript 保留字
- 建议使用有意义的变量名，提高可读性

### 2.2 数据类型

#### 数字（Number）
```javascript
var intNum = 100;          // 整数
var floatNum = 3.14;       // 浮点数
var negative = -50;        // 负数
var scientific = 1.5e3;    // 科学计数法（1500）
```

#### 字符串（String）
```javascript
var str1 = "Hello World";  // 双引号
var str2 = 'AE表达式';      // 单引号
var str3 = "第" + 5 + "帧"; // 字符串拼接
var str4 = str1.length;    // 字符串长度
```

#### 数组（Array）
```javascript
var arr1 = [1, 2, 3, 4, 5];           // 数字数组
var arr2 = ["a", "b", "c"];           // 字符串数组
var arr3 = [100, 200];                // 二维坐标
var arr4 = [100, 200, 50];            // 三维坐标
var arr5 = new Array(10);             // 创建指定长度的数组

// 访问数组元素
var first = arr1[0];     // 1（索引从0开始）
var second = arr1[1];    // 2
var len = arr1.length;   // 5（数组长度）
```

#### 对象（Object）
```javascript
var obj1 = {x: 100, y: 200};          // 简单对象
var obj2 = {name: "图层A", index: 1}; // 多属性对象

// 访问对象属性
var x = obj1.x;        // 100（点表示法）
var y = obj1["y"];     // 200（方括号表示法）
var name = obj2.name;  // "图层A"
```

#### 布尔值（Boolean）
```javascript
var isActive = true;
var isVisible = false;
var result = 10 > 5;   // true
```

#### 特殊值
```javascript
var a = null;           // 空值
var b = undefined;      // 未定义
var c = 0 / 0;          // NaN（Not a Number）
var d = 1 / 0;          // Infinity（无穷大）
```

### 2.3 运算符

#### 算术运算符
```javascript
var a = 10, b = 3;

a + b;      // 13  加法
a - b;      // 7   减法
a * b;      // 30  乘法
a / b;      // 3.333...  除法
a % b;      // 1   取模（余数）
a++;        // 自增（后置）
a--;        // 自减（后置）
++a;        // 自增（前置）
--a;        // 自减（前置）
a += b;     // a = a + b
a -= b;     // a = a - b
a *= b;     // a = a * b
a /= b;     // a = a / b
```

#### 比较运算符
```javascript
var a = 10, b = 3;

a == b;     // false   等于（值相等）
a != b;     // true    不等于
a === b;    // false   严格等于（值和类型都相等）
a !== b;    // true    严格不等于
a > b;      // true    大于
a < b;      // false   小于
a >= b;     // true    大于等于
a <= b;     // false   小于等于
```

#### 逻辑运算符
```javascript
var a = true, b = false;

a && b;     // false   逻辑与（AND）
a || b;     // true    逻辑或（OR）
!a;         // false   逻辑非（NOT）

// 短路求值特性
var result1 = x && y;   // x 为假则直接返回 x，不计算 y
var result2 = x || y;   // x 为真则直接返回 x，不计算 y
```

#### 三元运算符
```javascript
// 条件 ? 值1 : 值2
// 条件为真返回值1，为假返回值2

var score = 85;
var grade = score >= 60 ? "及格" : "不及格";  // "及格"

var speed = time > 2 ? 100 : 50;  // 2秒前速度50，2秒后速度100

// 嵌套三元（可读性差，谨慎使用）
var level = score >= 90 ? "优秀" : (score >= 60 ? "及格" : "不及格");
```

### 2.4 条件语句（if/else）

```javascript
// 基本 if 语句
if (time > 2) {
    value * 2;
} else {
    value;
}

// if / else if / else
var t = time;
if (t < 1) {
    [0, 0];
} else if (t < 2) {
    [100, 0];
} else if (t < 3) {
    [100, 100];
} else {
    [0, 100];
}

// 简写（只有一条语句时可以省略大括号，不推荐）
if (time > 5) 100; else 0;

// switch 语句
var mode = effect("控制")("模式").value;
switch (mode) {
    case 1:
        value * 0.5;
        break;
    case 2:
        value * 1.5;
        break;
    case 3:
        value * 2;
        break;
    default:
        value;
}
```

### 2.5 循环语句（for/while，性能注意事项）

#### for 循环
```javascript
// 计算 1 到 10 的和
var sum = 0;
for (var i = 1; i <= 10; i++) {
    sum += i;
}
sum;  // 55

// 遍历数组
var arr = [10, 20, 30, 40, 50];
var total = 0;
for (var i = 0; i < arr.length; i++) {
    total += arr[i];
}
```

#### while 循环
```javascript
var count = 0;
var sum = 0;
while (count < 10) {
    sum += count;
    count++;
}
```

#### do-while 循环
```javascript
var i = 0;
do {
    i++;
} while (i < 10);
```

**性能注意事项：**
- 循环在每一帧都会执行，复杂循环会严重影响性能
- 避免嵌套循环，尤其是深层嵌套
- 循环次数尽量控制在 100 次以内
- 能用数学公式计算的就不要用循环
- 避免在循环内进行图层引用或属性访问
- 考虑使用 `valueAtTime` 等内置函数替代手动循环

### 2.6 函数定义与调用

```javascript
// 基本函数定义
function double(x) {
    return x * 2;
}
double(5);  // 10

// 多参数函数
function add(a, b) {
    return a + b;
}
add(3, 4);  // 7

// 返回数组的函数
function getCenter() {
    return [thisComp.width / 2, thisComp.height / 2];
}

// 函数作为值（函数表达式）
var square = function(x) {
    return x * x;
};
square(4);  // 16

// 递归函数（谨慎使用，注意性能）
function factorial(n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// 默认参数模拟（ES3 不支持默认参数语法）
function greet(name) {
    name = name || "陌生人";  // 如果 name 为假值则使用默认值
    return "你好，" + name;
}
```

### 2.7 数组操作

#### 创建数组
```javascript
var arr1 = [1, 2, 3];
var arr2 = new Array();      // 空数组
var arr3 = new Array(5);     // 长度为5的数组
var arr4 = new Array(1,2,3); // [1, 2, 3]
```

#### 访问与修改
```javascript
var arr = [10, 20, 30, 40, 50];
arr[0];         // 10（第一个元素）
arr[arr.length-1]; // 50（最后一个元素）
arr[1] = 999;   // 修改第二个元素
arr.length;     // 5（数组长度）
```

#### ES3 支持的数组方法
```javascript
var arr = [1, 2, 3];

// 添加/删除元素
arr.push(4);       // 在末尾添加，返回新长度 -> [1,2,3,4]
arr.pop();         // 删除末尾元素，返回该元素 -> [1,2,3]
arr.unshift(0);    // 在开头添加，返回新长度 -> [0,1,2,3]
arr.shift();       // 删除开头元素，返回该元素 -> [1,2,3]

// 拼接与截取
arr.concat([4,5]); // 拼接数组，返回新数组 -> [1,2,3,4,5]
arr.slice(1, 3);   // 截取子数组，返回新数组 -> [2,3]
arr.splice(1, 1);  // 删除/插入元素，修改原数组 -> 返回[2]

// 排序与反转
arr.sort();        // 排序（按字符串排序，数字需自定义比较函数）
arr.reverse();     // 反转数组

// 转换
arr.join("-");     // 连接成字符串 -> "1-2-3"
arr.toString();    // 转换为字符串 -> "1,2,3"

// 查找
arr.indexOf(2);    // 查找元素索引（ES3 可能不支持，需自定义）
```

**注意：** ES3 中不支持 `forEach`、`map`、`filter`、`reduce` 等方法，需要手动用 for 循环实现。

### 2.8 对象操作

```javascript
// 创建对象
var person = {
    name: "张三",
    age: 25,
    position: [100, 200]
};

// 访问属性
person.name;          // "张三"（点表示法）
person["age"];        // 25（方括号表示法）
person.position[0];   // 100

// 修改属性
person.age = 26;
person["name"] = "李四";

// 添加新属性
person.email = "test@example.com";

// 删除属性
delete person.age;

// 检查属性是否存在
"name" in person;     // true
person.hasOwnProperty("name");  // true

// 遍历对象属性
for (var key in person) {
    if (person.hasOwnProperty(key)) {
        var val = person[key];
        // 处理每个属性
    }
}

// 嵌套对象
var config = {
    position: {x: 100, y: 200},
    scale: {x: 100, y: 100}
};
config.position.x;  // 100
```

### 2.9 注释（// 和 /* */）

```javascript
// 这是单行注释，从 // 到行尾都是注释

var x = 10;  // 行尾注释

/*
这是多行注释
可以写很多行
所有内容都会被忽略
*/

/*
 * 常见的多行注释格式
 * 每行前面加星号
 * 提高可读性
 */

// 调试时临时禁用代码
// var temp = someComplexCalculation();
// result = temp * 2;
```

---

## 三、核心全局变量与函数

### 3.1 时间相关

#### time - 当前时间
```javascript
// time 是当前合成时间，单位为秒
// 在第 0 帧时 time = 0
// 在 25fps 下，第 25 帧时 time = 1

// 简单的随时间线性增加的值
time * 100;  // 每秒增加 100

// 旋转：每秒旋转 90 度
time * 90;

// 位置：从左向右移动
[time * 100, value[1]];
```

#### value - 属性当前值
```javascript
// value 表示属性在当前时间的关键帧值
// 如果没有关键帧，就是属性的默认值
// 表达式通常基于 value 进行修改

// 在原有值基础上加上偏移
value + 50;

// 缩放：在原基础上呼吸
[value[0] + Math.sin(time * 3) * 10, value[1] + Math.sin(time * 3) * 10];

// valueAtTime(t) - 获取指定时间的值
// 获取 0.5 秒前的值
valueAtTime(time - 0.5);

// 获取 1 秒后的值
valueAtTime(time + 1);
```

#### index - 图层索引
```javascript
// index 是当前图层在合成中的索引号
// 最上面的图层 index = 1，往下依次递增

// 根据图层索引偏移位置
[value[0] + (index - 1) * 50, value[1]];

// 根据索引延迟动画
var delay = (index - 1) * 0.1;
valueAtTime(time - delay);

// 根据索引生成不同颜色
var hue = (index - 1) * 30;  // 每个图层相差30度色相
hslToRgb([hue / 360, 1, 0.5, 1]);
```

#### thisLayer - 当前图层
```javascript
// 引用当前图层本身
thisLayer.name;           // 图层名称
thisLayer.index;          // 图层索引（等同于 index）
thisLayer.width;          // 图层宽度
thisLayer.height;         // 图层高度
thisLayer.transform.position;  // 位置属性
thisLayer.effect("效果名");    // 效果引用

// 检查图层是否是 3D 图层
thisLayer.threeDLayer;

// 检查图层是否启用
thisLayer.enabled;

// 图层的入点和出点
thisLayer.inPoint;
thisLayer.outPoint;
```

#### thisComp - 当前合成
```javascript
// 引用表达式所在的合成
thisComp.name;                 // 合成名称
thisComp.width;                // 合成宽度（像素）
thisComp.height;               // 合成高度（像素）
thisComp.duration;             // 合成持续时间（秒）
thisComp.frameDuration;        // 一帧的时间（秒），即 1/帧率
thisComp.frameRate;            // 合成帧率
thisComp.displayStartFrame;    // 显示起始帧号

// 引用合成中的图层
thisComp.layer("图层名");
thisComp.layer(1);  // 第一个图层

// 合成中的所有图层数量
thisComp.numLayers;
```

#### thisProject - 当前项目
```javascript
// 引用当前项目
thisProject.name;      // 项目名称
thisProject.path;      // 项目文件路径
thisProject.bitsPerChannel;  // 位深度

// 注意：thisProject 在表达式中功能有限
// 主要在脚本中使用
```

#### name - 图层名称
```javascript
// 当前图层的名称
name;  // 等同于 thisLayer.name

// 根据图层名称判断行为
if (name == "控制层") {
    [0, 0];
} else {
    value;
}
```

### 3.2 常用数学函数

#### Math.sin() / Math.cos() - 正余弦波
```javascript
// 正弦函数：返回 -1 到 1 之间的值
// Math.sin(时间 * 频率) * 振幅

// 垂直方向的正弦运动（上下漂浮）
var freq = 2;      // 频率：每秒 2 次
var amp = 50;      // 振幅：50 像素
[value[0], value[1] + Math.sin(time * freq * Math.PI * 2) * amp];

// 缩放呼吸效果
var freq = 1;
var amp = 10;
var s = 100 + Math.sin(time * freq * Math.PI * 2) * amp;
[s, s];

// 余弦函数：相位差 90 度
// Math.cos(x) 等同于 Math.sin(x + Math.PI/2)
Math.cos(time * 2);

// 圆周运动
var r = 100;       // 半径
var speed = 1;     // 角速度
var centerX = thisComp.width / 2;
var centerY = thisComp.height / 2;
[
    centerX + Math.cos(time * speed * Math.PI * 2) * r,
    centerY + Math.sin(time * speed * Math.PI * 2) * r
];
```

#### Math.round() / Math.floor() / Math.ceil() - 取整
```javascript
// Math.round() - 四舍五入
Math.round(3.4);   // 3
Math.round(3.6);   // 4

// Math.floor() - 向下取整
Math.floor(3.9);   // 3
Math.floor(-3.1);  // -4

// Math.ceil() - 向上取整
Math.ceil(3.1);    // 4
Math.ceil(-3.9);   // -3

// 应用：阶梯动画（每隔 0.5 秒跳一次）
var steps = Math.floor(time / 0.5);
[steps * 50, value[1]];

// 应用：像素对齐（避免子像素模糊）
[Math.round(value[0]), Math.round(value[1])];
```

#### Math.abs() - 绝对值
```javascript
Math.abs(5);       // 5
Math.abs(-5);      // 5
Math.abs(3 - 7);   // 4

// 应用：对称弹跳（类似钟摆）
var t = time % 2;  // 周期 2 秒
Math.abs(t - 1) * 100;  // 0-100-0 的三角波

// 应用：只取正数部分
Math.abs(Math.sin(time * 3)) * 50;
```

#### Math.max() / Math.min() - 最大最小
```javascript
// Math.max() - 返回最大值
Math.max(3, 7, 2, 9);   // 9

// Math.min() - 返回最小值
Math.min(3, 7, 2, 9);   // 2

// 应用：限制值的范围（钳位）
var val = time * 100;
var minVal = 0;
var maxVal = 100;
Math.min(Math.max(val, minVal), maxVal);  // 钳位在 0-100 之间

// 应用：取两个图层中较大的缩放值
var s1 = thisComp.layer("A").scale[0];
var s2 = thisComp.layer("B").scale[0];
Math.max(s1, s2);
```

#### Math.random() - 随机数
```javascript
// Math.random() - 返回 0 到 1 之间的随机数（不包括 1）
Math.random();       // 0.12345...

// 0 到 100 之间的随机数
Math.random() * 100;

// 50 到 100 之间的随机数
50 + Math.random() * 50;

// -50 到 50 之间的随机数
Math.random() * 100 - 50;

// 随机整数（0 到 9）
Math.floor(Math.random() * 10);

// 注意：Math.random() 每一帧都会重新生成
// 如果需要稳定的随机值，使用 seedRandom()
seedRandom(index, true);  // 用图层索引作为种子，true 表示静止
Math.random() * 100;      // 每个图层一个固定的随机值
```

#### Math.sqrt() - 平方根
```javascript
Math.sqrt(9);       // 3
Math.sqrt(2);       // 1.414...

// 计算两点之间的距离
var x1 = 100, y1 = 100;
var x2 = 300, y2 = 400;
var dx = x2 - x1;
var dy = y2 - y1;
Math.sqrt(dx * dx + dy * dy);  // 距离

// 等同于 length() 函数
length([dx, dy]);
```

#### Math.pow() - 幂运算
```javascript
// Math.pow(底数, 指数)
Math.pow(2, 3);     // 8 (2的3次方)
Math.pow(10, 2);    // 100 (10的平方)

// 平方（等同于 Math.pow(x, 2)）
var x = 5;
x * x;              // 25
Math.pow(x, 2);     // 25

// 立方
Math.pow(x, 3);     // 125

// 开平方（等同于 Math.sqrt(x)）
Math.pow(x, 0.5);   // 2.236...

// 应用：缓动曲线（easeInOut 的近似）
function easeInOut(t) {
    if (t < 0.5) {
        return Math.pow(t * 2, 2) / 2;
    } else {
        return 1 - Math.pow((1 - t) * 2, 2) / 2;
    }
}
```

#### Math.exp() / Math.log() - 指数/对数
```javascript
// Math.exp(x) - e 的 x 次方
Math.exp(0);        // 1 (e^0 = 1)
Math.exp(1);        // 2.718... (e^1 = e)

// Math.log(x) - 自然对数（以 e 为底）
Math.log(1);        // 0
Math.log(Math.E);   // 1

// 应用：指数衰减（弹簧/回弹效果的基础）
var decay = 3;       // 衰减系数
var amp = 100;       // 初始振幅
amp * Math.exp(-time * decay);  // 随时间指数衰减
```

#### Math.PI - 圆周率
```javascript
Math.PI;             // 3.141592653589793

// 角度转弧度
var degrees = 90;
var radians = degrees * Math.PI / 180;  // π/2

// 弧度转角度
var radians = Math.PI / 2;
var degrees = radians * 180 / Math.PI;  // 90

// 完整圆周（360度）
2 * Math.PI;         // 6.283...

// 半圆周（180度）
Math.PI;             // 3.1415...
```

### 3.3 插值函数

插值函数用于将一个范围内的值映射到另一个范围，是表达式中最常用的工具之一。

#### linear() - 线性映射
```javascript
// 语法：
// linear(t, tMin, tMax, value1, value2)
// t 在 [tMin, tMax] 范围内时，返回 [value1, value2] 的线性插值

// 参数说明：
// t - 输入值（通常是 time 或其他变量）
// tMin - 输入范围最小值
// tMax - 输入范围最大值
// value1 - 输出范围最小值
// value2 - 输出范围最大值

// 示例：时间 0-2 秒内，不透明度从 0 变到 100
linear(time, 0, 2, 0, 100);

// 示例：滑块 0-100 控制位置 0-500
var slider = effect("滑块控制")("滑块").value;
linear(slider, 0, 100, 0, 500);

// 示例：二维值插值（位置）
var startPos = [100, 100];
var endPos = [500, 400];
linear(time, 0, 3, startPos, endPos);

// 简化形式（t 在 0-1 之间时）
// linear(t, value1, value2)
linear(time / 3, [0, 0], [500, 500]);

// 注意：当 t < tMin 时返回 value1，t > tMax 时返回 value2
// 如果需要钳位，可以在外面包一层
```

#### ease() - 缓动插值（慢入慢出）
```javascript
// 语法与 linear 相同，但开始和结束时速度较慢，中间较快
// 相当于 easeIn + easeOut

// ease(t, tMin, tMax, value1, value2)

// 示例：平滑的进入和退出动画
ease(time, 0, 2, 0, 100);

// 示例：位置缓动
var start = [100, 300];
var end = [600, 300];
ease(time, 1, 3, start, end);  // 第1秒开始，第3秒结束

// 对比：
// linear - 匀速运动
// ease - 慢入慢出（最自然）
```

#### easeIn() - 缓入
```javascript
// 开始慢，逐渐加速，结束时速度最快
// easeIn(t, tMin, tMax, value1, value2)

// 示例：加速运动（类似汽车启动）
easeIn(time, 0, 2, 0, 500);

// 应用：重力加速度效果
var startY = 100;
var endY = 500;
[value[0], easeIn(time, 0, 2, startY, endY)];
```

#### easeOut() - 缓出
```javascript
// 开始快，逐渐减速，结束时速度为 0
// easeOut(t, tMin, tMax, value1, value2)

// 示例：减速运动（类似刹车）
easeOut(time, 0, 2, 0, 500);

// 应用：弹跳落地前的减速
var startY = 100;
var endY = 400;
[value[0], easeOut(time, 0, 1.5, startY, endY)];
```

**插值函数参数说明：**

| 参数 | 类型 | 说明 |
|-----|------|------|
| t | Number | 输入值（时间或其他变量） |
| tMin | Number | 输入范围下限 |
| tMax | Number | 输入范围上限 |
| value1 | Number/Array | 输出范围下限 |
| value2 | Number/Array | 输出范围上限 |

**返回值：** 与 value1/value2 同类型的插值结果

### 3.4 循环函数

循环函数用于重复关键帧动画，无需手动复制关键帧。

#### loopOut() - 向后循环
```javascript
// 在最后一个关键帧之后循环
// loopOut(type, numKeyframes, offset)

// 参数：
// type - 循环类型（字符串）
// numKeyframes - 参与循环的关键帧数（从最后往前数）
// offset - 时间偏移（可选，默认为0）

// 循环类型：
// "cycle" - 循环播放（默认）
// "pingpong" - 来回播放（正序-倒序-正序...）
// "offset" - 偏移循环（每次循环叠加偏移量）
// "continue" - 继续（根据最后一个关键帧的速度继续运动）

// 示例：循环播放所有关键帧
loopOut("cycle");

// 示例：乒乓循环（来回弹）
loopOut("pingpong");

// 示例：只循环最后 2 个关键帧
loopOut("cycle", 1);  // 倒数第1个到倒数第2个

// 示例：offset 循环（每次循环位置递增）
loopOut("offset");

// 示例：continue（匀速继续）
loopOut("continue");
```

#### loopIn() - 向前循环
```javascript
// 在第一个关键帧之前循环
// 语法与 loopOut 相同
// loopIn(type, numKeyframes, offset)

// 示例：第一个关键帧之前就开始循环
loopIn("cycle");
```

#### loopOutDuration() / loopInDuration()
```javascript
// 指定循环的持续时间，而不是关键帧数

// loopOutDuration(type, duration, offset)
// loopInDuration(type, duration, offset)

// 示例：循环最后 1 秒的动画
loopOutDuration("cycle", 1);

// 示例：乒乓循环 2 秒的内容
loopOutDuration("pingpong", 2);
```

**循环类型详解：**

| 类型 | 说明 | 适用场景 |
|-----|------|---------|
| "cycle" | 从头到尾重复播放 | 车轮旋转、循环动画 |
| "pingpong" | 正序播放完倒序播放，像乒乓球一样来回 | 呼吸、弹跳、钟摆 |
| "offset" | 每次循环叠加最后一帧与第一帧的差值 | 上升螺旋、连续前进 |
| "continue" | 根据最后一个关键帧的速度继续运动 | 抛射物、惯性运动 |

### 3.5 震动函数

#### wiggle() - 随机震动
```javascript
// wiggle(freq, amp, octaves, amp_mult, t)
// 生成自然的随机震动效果

// 参数说明：
// freq - 频率（每秒震动次数），默认值 1
// amp - 振幅（震动幅度），默认值 0
// octaves - 倍频程数（震动的细节层次），默认值 1
//           数值越大，震动越不规则、越自然
// amp_mult - 振幅倍率（每层倍频的振幅乘数），默认值 0.5
// t - 时间（用于替换默认的 time 变量），可选

// 基础用法：位置抖动
wiggle(3, 20);  // 每秒3次，振幅20像素

// 在原位置基础上抖动
value + wiggle(5, 10) - value;  // 这样写不对，正确写法：
wiggle(3, 20);  // 直接用，会自动加在 value 上
// 注意：wiggle 返回的是绝对值，不是偏移量
// 它会自动考虑属性的当前值

// 高级：多倍频程（更自然的震动）
wiggle(3, 20, 3);  // 3个倍频程，更自然

// 高级：调整振幅倍率
wiggle(3, 20, 3, 0.7);  // 每层倍频振幅乘0.7（默认0.5）

// 高级：自定义时间参数
// 让震动随时间变慢
var decayTime = time * 0.5;
wiggle(2, 30, 1, 0.5, decayTime);
```

**带衰减的 wiggle：**
```javascript
// 方法一：时间减速
var t = time * 0.5;  // 时间越久震动越慢
wiggle(3, 20, 1, 0.5, t);

// 方法二：振幅衰减
var freq = 2;
var amp = 30;
var decay = 2;  // 衰减系数
var newAmp = amp * Math.exp(-time * decay);
wiggle(freq, newAmp);

// 方法三：频率和振幅都衰减
var startFreq = 5;
var startAmp = 40;
var decay = 1.5;
var currentFreq = startFreq * Math.exp(-time * decay);
var currentAmp = startAmp * Math.exp(-time * decay);
wiggle(currentFreq, currentAmp);
```

**单一维度 wiggle：**
```javascript
// 只在 X 方向震动
var w = wiggle(3, 20);
[w[0], value[1]];

// 只在 Y 方向震动
var w = wiggle(3, 20);
[value[0], w[1]];

// 只在 Z 方向震动（3D 图层）
var w = wiggle(3, 20);
[value[0], value[1], w[2]];

// 旋转的 wiggle
wiggle(2, 15);  // 每秒2次，振幅15度

// 不透明度的 wiggle（闪烁效果）
wiggle(5, 20);  // 不透明度在 value±20 之间波动
```

### 3.6 空间函数

#### lookAt(fromPoint, atPoint) - 目标朝向
```javascript
// 计算从 fromPoint 看向 atPoint 所需的旋转值
// 返回的是 [xRotation, yRotation, zRotation] 数组

// 参数：
// fromPoint - 观察点位置（数组：[x, y] 或 [x, y, z]）
// atPoint - 目标点位置（数组）

// 示例：2D 图层指向目标（注意：返回的是 3D 旋转）
var from = thisLayer.position;
var to = thisComp.layer("目标").position;
lookAt(from, to);

// 示例：3D 摄像机看向目标
var target = thisComp.layer("目标").position;
lookAt(thisLayer.position, target);

// 注意：对于 2D 图层，lookAt 返回的旋转需要特殊处理
// 2D 图层只需要 z 旋转，可以这样计算：
var from = position;
var to = thisComp.layer("目标").position;
var dx = to[0] - from[0];
var dy = to[1] - from[1];
Math.atan2(dy, dx) * 180 / Math.PI + value;
```

#### length(vec) - 向量长度
```javascript
// 计算向量的长度（或两点间的距离）

// 计算一个向量的长度
length([3, 4]);       // 5 (3-4-5三角形)
length([1, 2, 2]);    // 3 (1+4+4=9，开方=3)

// 计算两点间的距离
var p1 = [100, 100];
var p2 = [400, 500];
length(p1 - p2);      // 500

// 等同于：
var dx = p2[0] - p1[0];
var dy = p2[1] - p1[1];
Math.sqrt(dx * dx + dy * dy);

// 应用：根据距离调整缩放
var myPos = position;
var targetPos = thisComp.layer("目标").position;
var dist = length(myPos - targetPos);
var maxDist = 500;
var s = linear(dist, 0, maxDist, 150, 50);  // 越近越大
[s, s];
```

#### normalize(vec) - 单位向量
```javascript
// 将向量归一化（长度变为 1，方向不变）

normalize([3, 4]);     // [0.6, 0.8] （长度为1）
normalize([0, 100]);   // [0, 1]

// 应用：沿方向移动指定距离
var dir = [1, 1];          // 方向向量
var normDir = normalize(dir);  // 归一化
var dist = 100;            // 移动距离
var offset = [normDir[0] * dist, normDir[1] * dist];
value + offset;
```

#### 点积、叉积

```javascript
// dot(vec1, vec2) - 点积（内积）
// 返回一个标量值
// 两个向量方向相同时点积为正，相反时为负，垂直时为0

var v1 = [1, 0];
var v2 = [0, 1];
dot(v1, v2);     // 0（垂直）

var v3 = [1, 0];
var v4 = [-1, 0];
dot(v3, v4);     // -1（相反）

// 应用：判断物体朝向是否面向目标
var direction = toWorld([0, 0, -1]);  // 图层正前方（3D）
var toTarget = normalize(target.position - position);
var facing = dot(direction, toTarget);
// facing > 0 表示面向目标，< 0 表示背向

// cross(vec1, vec2) - 叉积（外积）
// 返回一个新向量，方向垂直于两个输入向量
// 只对 3D 向量有意义

var v1 = [1, 0, 0];
var v2 = [0, 1, 0];
cross(v1, v2);   // [0, 0, 1] （右手定则）

// 应用：计算旋转轴
```

---

## 四、属性引用体系

### 4.1 图层引用

#### 通过名称引用
```javascript
// thisComp.layer("图层名称")
var ctrl = thisComp.layer("控制器");
var logo = thisComp.layer("Logo动画");

// 注意：图层名称区分大小写
// 如果图层重名，会返回找到的第一个
```

#### 通过索引引用
```javascript
// thisComp.layer(index)
// index 从 1 开始，最上面的图层是 1
var firstLayer = thisComp.layer(1);
var thirdLayer = thisComp.layer(3);

// 当前图层的索引
var myIndex = thisLayer.index;
```

#### 相对引用
```javascript
// thisComp.layer(thisLayer, offset)
// 相对当前图层的偏移

var above = thisComp.layer(thisLayer, -1);  // 上面一个图层
var below = thisComp.layer(thisLayer, 1);   // 下面一个图层
var twoAbove = thisComp.layer(thisLayer, -2);  // 上面两个图层

// 应用：延迟跟随（每个图层跟随上面一个图层）
var delay = 0.1;
var leader = thisComp.layer(thisLayer, -1);
leader.position.valueAtTime(time - delay);
```

#### layers 集合
```javascript
// thisComp.layers 是所有图层的集合
// 可以通过索引访问（从 1 开始）
var totalLayers = thisComp.numLayers;  // 图层总数

// 遍历所有图层（注意：性能开销大）
var sum = 0;
for (var i = 1; i <= thisComp.numLayers; i++) {
    var layer = thisComp.layer(i);
    sum += layer.transform.opacity;
}
sum / thisComp.numLayers;  // 平均不透明度
```

### 4.2 效果引用

#### 通过效果名称引用
```javascript
// effect("效果名称")("参数名称")

// 获取滑块控制的值
var slider = effect("滑块控制")("滑块").value;

// 获取颜色控制的值
var color = effect("颜色控制")("颜色").value;
// 返回 [r, g, b, a] 数组，每个值范围 0-1

// 获取角度控制的值
var angle = effect("角度控制")("角度").value;

// 获取复选框的值
var checkbox = effect("复选框控制")("复选框").value;
// 返回 0 或 1（0 = 未勾选，1 = 勾选）

// 获取点控制的值
var point = effect("点控制")("点").value;
// 返回 [x, y] 数组
```

#### 通过索引引用
```javascript
// effect(index)
// 索引从 1 开始，按效果面板中的顺序排列

var firstEffect = effect(1);  // 第一个效果
var secondEffect = effect(2); // 第二个效果

// 获取第一个效果的第一个参数
var val = effect(1)(1).value;
```

#### 常用效果参数引用

| 效果控件 | 参数名 | 返回值类型 | 说明 |
|---------|--------|-----------|------|
| 滑块控制（Slider Control） | "滑块" | Number | 单值数值 |
| 角度控制（Angle Control） | "角度" | Number | 角度值（度） |
| 颜色控制（Color Control） | "颜色" | Array [r,g,b,a] | 颜色值（0-1范围） |
| 点控制（Point Control） | "点" | Array [x,y] | 二维坐标 |
| 复选框控制（Checkbox Control） | "复选框" | Number | 0 或 1 |
| 图层控制（Layer Control） | "图层" | Layer 对象 | 图层引用 |

```javascript
// 完整的控件引用示例
var sliderVal = effect("滑块控制")("滑块").value;
var angleVal = effect("角度控制")("角度").value;
var colorVal = effect("颜色控制")("颜色").value;
var pointVal = effect("点控制")("点").value;
var checkVal = effect("复选框控制")("复选框").value;
var layerVal = effect("图层控制")("图层").value;

// 颜色值的分量访问
var r = colorVal[0];  // 红
var g = colorVal[1];  // 绿
var b = colorVal[2];  // 蓝
var a = colorVal[3];  // Alpha
```

### 4.3 属性路径

#### 变换属性（Transform）
```javascript
// 位置
thisLayer.transform.position;       // 完整路径
position;                           // 简写（当前图层）

// 缩放
scale;  // [100, 100] 二维，[100, 100, 100] 三维

// 旋转
rotation;           // 2D 旋转（z轴）
rotationZ;          // 3D 图层的 Z 旋转
rotationX;          // 3D 图层的 X 旋转
rotationY;          // 3D 图层的 Y 旋转

// 不透明度
opacity;  // 0-100

// 锚点
anchorPoint;

// 所有变换属性的完整路径
thisLayer.transform.position;
thisLayer.transform.anchorPoint;
thisLayer.transform.scale;
thisLayer.transform.rotation;
thisLayer.transform.opacity;
```

#### 效果属性
```javascript
// effect("效果名")("参数名")

// 例如：高斯模糊的模糊量
effect("高斯模糊")("模糊度").value;

// 例如：色阶的输入黑色
effect("色阶")("输入黑色").value;

// 效果参数也有 valueAtTime
effect("滑块控制")("滑块").valueAtTime(time - 0.5);
```

#### 蒙版属性（Mask）
```javascript
// mask("蒙版名") 或 mask(index)

// 蒙版路径
mask("蒙版 1").maskPath;

// 蒙版羽化
mask("蒙版 1").maskFeather;  // [x, y]

// 蒙版不透明度
mask("蒙版 1").maskOpacity;

// 蒙版扩展
mask("蒙版 1").maskExpansion;

// 蒙版顶点数（只读）
mask("蒙版 1").maskPath.points().length;
```

#### 文字属性（Text）
```javascript
// sourceRectAtTime(t, includeMask)
// 获取文字图层在指定时间的源矩形

var rect = sourceRectAtTime(time, false);
// 返回 {top, left, width, height} 对象

// 应用：文字居中对齐
var rect = sourceRectAtTime(time, false);
var centerX = rect.left + rect.width / 2;
var centerY = rect.top + rect.height / 2;

// 应用：根据文字长度调整背景宽度
var rect = thisComp.layer("文字").sourceRectAtTime(time, false);
[rect.width + 40, value[1]];  // 左右各加20像素边距
```

### 4.4 合成属性

```javascript
// 尺寸
thisComp.width;       // 合成宽度（像素）
thisComp.height;      // 合成高度（像素）

// 时间
thisComp.duration;    // 合成持续时间（秒）
thisComp.frameRate;   // 帧率（fps）
thisComp.frameDuration; // 一帧的时间 = 1/frameRate
thisComp.displayStartFrame;  // 显示起始帧号

// 名称
thisComp.name;

// 背景色
thisComp.bgColor;     // [r, g, b] 数组

// 像素长宽比
thisComp.pixelAspect;
```

**常用合成属性速查表：**

| 属性 | 类型 | 说明 |
|-----|------|------|
| width | Number | 宽度（像素） |
| height | Number | 高度（像素） |
| duration | Number | 持续时间（秒） |
| frameRate | Number | 帧率 |
| frameDuration | Number | 单帧时间（秒） |
| displayStartFrame | Number | 起始帧号 |
| name | String | 合成名称 |
| numLayers | Number | 图层数量 |
| bgColor | Array | 背景色 [r,g,b] |

---

## 五、常用表达式模式（实战必学）

### 5.1 控制类

#### 1. 滑块控制缩放
```javascript
// 功能：用一个滑块控制图层的缩放
// 适用：统一控制多个图层的缩放比例
// 放置位置：缩放属性

var slider = effect("滑块控制")("滑块").value;
var baseScale = 100;
var s = baseScale + slider;
[s, s];
```

**参数说明：**
- `slider`：滑块值，范围自定义
- `baseScale`：基础缩放量

**使用场景：** 一个控制器控制多个元素的整体缩放

---

#### 2. 角度控制旋转
```javascript
// 功能：用角度滑块控制图层旋转
// 适用：旋钮、指针、方向盘等旋转控制
// 放置位置：旋转属性

var angle = effect("角度控制")("角度").value;
value + angle;
```

**参数说明：**
- `angle`：角度值，可以是任意度数（正负均可）

**使用场景：** 仪表盘指针、旋转动画控制、3D旋转控制

---

#### 3. 颜色控制着色
```javascript
// 功能：用颜色控件改变图层颜色
// 适用：统一调色、主题色切换
// 放置位置：填充效果的颜色 / 色调效果的映射白色

// 方法1：直接返回颜色（用在颜色属性上）
effect("颜色控制")("颜色").value;

// 方法2：与原色混合（用在颜色属性上）
var targetColor = effect("颜色控制")("颜色").value;
var blendAmount = effect("滑块控制")("滑块").value / 100;
var origColor = [1, 1, 1, 1];  // 原始颜色

var r = origColor[0] * (1 - blendAmount) + targetColor[0] * blendAmount;
var g = origColor[1] * (1 - blendAmount) + targetColor[1] * blendAmount;
var b = origColor[2] * (1 - blendAmount) + targetColor[2] * blendAmount;
var a = origColor[3] * (1 - blendAmount) + targetColor[3] * blendAmount;
[r, g, b, a];
```

**使用场景：** 品牌色统一控制、主题切换、颜色动画

---

#### 4. 复选框开关效果
```javascript
// 功能：用复选框控制效果的开关
// 适用：效果切换、显隐控制、动画开关
// 放置位置：不透明度 / 效果参数 / 时间重映射

// 方法1：控制不透明度
var check = effect("复选框控制")("复选框").value;
check * 100;  // 勾选=100%不透明，不勾选=0%

// 方法2：控制效果强度
var check = effect("复选框控制")("复选框").value;
var amount = effect("滑块控制")("滑块").value;
check * amount;

// 方法3：带过渡的开关
var check = effect("复选框控制")("复选框").value;
var transition = 0.5;  // 过渡时间（秒）

if (check == 1) {
    ease(time, 0, transition, 0, 100);
} else {
    ease(time, 0, transition, 100, 0);
}
```

**使用场景：** 效果开关、图层显隐、动画启用/禁用

---

#### 5. 点控制位置
```javascript
// 功能：用点控件控制图层位置
// 适用：目标位置控制、锚点定位
// 放置位置：位置属性

var point = effect("点控制")("点").value;
point;
```

**进阶：相对偏移**
```javascript
// 点控制作为偏移量
var offset = effect("点控制")("点").value;
[value[0] + offset[0], value[1] + offset[1]];
```

**使用场景：** 目标追踪、位置动画控制、多图层统一位置控制

---

### 5.2 动画类

#### 1. 呼吸效果（缩放呼吸）
```javascript
// 功能：缩放的正弦呼吸动画
// 适用：心跳、呼吸、脉动效果
// 放置位置：缩放属性

var freq = 1;       // 频率（每秒呼吸次数）
var amp = 10;       // 振幅（缩放变化量）
var base = 100;     // 基础缩放

var s = base + Math.sin(time * freq * Math.PI * 2) * amp;
[s, s];
```

**参数说明：**
- `freq`：呼吸频率，值越大越快
- `amp`：呼吸幅度，值越大变化越明显
- `base`：基础缩放值

**使用场景：** 生物呼吸、灯泡发光、按钮提示

---

#### 2. 心跳动画（缩放脉冲）
```javascript
// 功能：更接近真实心跳的双脉冲效果
// 适用：心跳、警告、强调
// 放置位置：缩放属性

var freq = 1;       // 每秒心跳次数
var amp1 = 20;      // 第一波振幅
var amp2 = 10;      // 第二波振幅
var base = 100;

var t = time % (1 / freq) * freq;  // 归一化时间 0-1

// 模拟双峰心跳
var beat1 = Math.exp(-Math.pow((t - 0.1) * 10, 2)) * amp1;
var beat2 = Math.exp(-Math.pow((t - 0.25) * 8, 2)) * amp2;

var s = base + beat1 + beat2;
[s, s];
```

**使用场景：** 心电图、警告提示、生命体征

---

#### 3. 旋转循环
```javascript
// 功能：匀速旋转动画
// 适用：车轮、螺旋、加载动画
// 放置位置：旋转属性

// 匀速旋转
var speed = 90;  // 每秒旋转 90 度
time * speed;

// 加速旋转
var accel = 30;  // 加速度（度/秒²）
0.5 * accel * time * time;

// 减速旋转（从某速度减到停止）
var initSpeed = 180;  // 初始速度
var decel = 50;       // 减速度
var currentSpeed = Math.max(0, initSpeed - decel * time);
initSpeed * time - 0.5 * decel * time * time;
```

**使用场景：** 加载动画、车轮转动、机械旋转、星系旋转

---

#### 4. 漂浮动画（上下浮动）
```javascript
// 功能：正弦波上下漂浮
// 适用：悬浮元素、云朵、气球
// 放置位置：位置属性

var freq = 0.5;     // 频率
var amp = 30;       // 振幅
var offsetX = 0;    // X方向偏移（可选）

var y = value[1] + Math.sin(time * freq * Math.PI * 2) * amp;
var x = value[0] + Math.cos(time * freq * Math.PI) * offsetX;
[x, y];
```

**进阶：双频率叠加（更自然的漂浮）**
```javascript
var freq1 = 0.5;
var amp1 = 20;
var freq2 = 1.2;
var amp2 = 10;

var y = value[1] 
    + Math.sin(time * freq1 * Math.PI * 2) * amp1 
    + Math.sin(time * freq2 * Math.PI * 2) * amp2;
[value[0], y];
```

**使用场景：** 悬浮UI、水中生物、气球、云朵

---

#### 5. 螺旋运动
```javascript
// 功能：向外螺旋运动
// 适用：螺旋线、星系、漩涡
// 放置位置：位置属性

var centerX = thisComp.width / 2;
var centerY = thisComp.height / 2;
var startRadius = 0;
var endRadius = 200;
var speed = 0.5;  // 每秒圈数

var t = Math.min(time / 3, 1);  // 3秒内完成
var r = linear(t, 0, 1, startRadius, endRadius);
var angle = time * speed * Math.PI * 2;

var x = centerX + Math.cos(angle) * r;
var y = centerY + Math.sin(angle) * r;
[x, y];
```

**使用场景：** 螺旋加载动画、星系旋转、漩涡特效

---

#### 6. 钟摆效果
```javascript
// 功能：类似钟摆的往复运动
// 适用：钟摆、秋千、摇摆物体
// 放置位置：旋转属性

var amplitude = 30;   // 摆动幅度（度）
var frequency = 0.5;  // 频率（每秒次数）

// 简单正弦摆动
Math.sin(time * frequency * Math.PI * 2) * amplitude;

// 带阻尼的钟摆（逐渐停下来）
var damping = 0.5;  // 阻尼系数
var amp = amplitude * Math.exp(-time * damping);
Math.sin(time * frequency * Math.PI * 2) * amp;
```

**进阶：真实钟摆物理（大角度修正）**
```javascript
// 对于小角度，正弦波足够准确
// 大角度时周期会变长，这里用近似
var amplitude = 45;  // 度
var length = 200;    // 摆长（影响周期）

var period = 2 * Math.PI * Math.sqrt(length / 980);  // 近似周期
var freq = 1 / period;
Math.sin(time * freq * Math.PI * 2) * amplitude;
```

**使用场景：** 钟摆动画、秋千、摇摆的树枝

---

#### 7. 弹跳动画
```javascript
// 功能：落地弹跳效果
// 适用：物体落地、弹跳球、UI弹出
// 放置位置：位置属性（Y轴）

function bounce(t, amp, freq, decay) {
    // t: 时间（归一化0-1）
    // amp: 初始振幅
    // freq: 频率
    // decay: 衰减系数
    return Math.abs(Math.sin(t * freq * Math.PI * 2)) * amp * Math.exp(-t * decay);
}

var startY = 100;
var endY = 500;
var duration = 2;  // 总时长

var t = Math.min(time / duration, 1);
var fall = easeOut(t, 0, 1, 0, 1);  // 下落缓动
var bounceHeight = bounce(t, 80, 3, 4);  // 弹跳

var y = startY + (endY - startY) * fall - bounceHeight * (1 - t);
[value[0], y];
```

**使用场景：** 物体落地、弹球动画、UI元素弹出

---

#### 8. 弹性动画
```javascript
// 功能：弹性回弹效果（类似弹簧）
// 适用：弹簧、果冻、弹性物体
// 放置位置：缩放 / 位置

function elasticOut(t, amplitude, frequency, decay) {
    if (t >= 1) return 0;
    return amplitude * Math.sin(t * frequency * Math.PI * 2) * Math.exp(-t * decay);
}

// 缩放弹性（弹出后回弹）
var targetScale = 100;
var overshoot = 30;  // 过冲量
var t = Math.min(time / 0.8, 1);
var base = easeOut(t, 0, targetScale + overshoot, targetScale);
var bounce = elasticOut(t, 15, 4, 6);
var s = base + bounce;
[s, s];
```

**使用场景：** 按钮点击反馈、果冻效果、弹性UI

---

### 5.3 联动类

#### 1. 父子关系替代（表达式控制）
```javascript
// 功能：用表达式代替父子关系，更灵活
// 适用：需要条件控制的跟随、延迟跟随
// 放置位置：位置 / 旋转等

// 位置跟随（完全跟随，等同父子）
var parentLayer = thisComp.layer("父图层");
parentLayer.position;

// 带偏移的位置跟随
var parentLayer = thisComp.layer("父图层");
var offset = [50, -30];  // 偏移量
var parentPos = parentLayer.position;
[parentPos[0] + offset[0], parentPos[1] + offset[1]];

// 缩放跟随（保持自身比例）
var parentLayer = thisComp.layer("父图层");
var parentScale = parentLayer.scale[0] / 100;
[value[0] * parentScale, value[1] * parentScale];
```

**使用场景：** 复杂的多图层联动、有条件的跟随、带延迟的父子

---

#### 2. 跟随运动（延迟跟随）
```javascript
// 功能：延迟一段时间跟随目标
// 适用：拖尾、跟随动画、层级动画
// 放置位置：位置 / 缩放 / 任意属性

var delay = 0.5;  // 延迟时间（秒）
var leader = thisComp.layer("引导层");
leader.position.valueAtTime(time - delay);
```

**进阶：指数平滑跟随（更自然）**
```javascript
// 不会完全跟随时，而是平滑地趋近
var target = thisComp.layer("目标").position;
var smoothness = 5;  // 平滑度，越大跟随越紧

var dx = target[0] - value[0];
var dy = target[1] - value[1];
[
    value[0] + dx * (1 - Math.exp(-thisComp.frameDuration * smoothness)),
    value[1] + dy * (1 - Math.exp(-thisComp.frameDuration * smoothness))
];
```

**使用场景：** 蛇形运动、拖尾效果、跟随动画、软刚体模拟

---

#### 3. 多图层联动（一个控制器控制多个）
```javascript
// 功能：一个控制层控制多个子图层
// 适用：阵列动画、批量控制、整体效果
// 放置位置：子图层的变换属性

// 放在每个子图层上，统一读取控制器
var ctrl = thisComp.layer("控制器");
var masterScale = ctrl.effect("整体缩放")("滑块").value;
var offset = (index - 1) * ctrl.effect("间距")("滑块").value;

// 每个图层有不同的偏移
[value[0] + offset, value[1]];
```

**进阶：索引延迟波纹效果**
```javascript
var ctrl = thisComp.layer("控制器");
var delayPerLayer = 0.05;  // 每个图层延迟
var delay = (index - 1) * delayPerLayer;
var t = Math.max(0, time - delay);

var amp = ctrl.effect("振幅")("滑块").value;
var freq = ctrl.effect("频率")("滑块").value;

[value[0], value[1] + Math.sin(t * freq * Math.PI * 2) * amp];
```

**使用场景：** 文字动画、图像阵列、波形动画、批量控制

---

#### 4. 目标追踪（lookAt）
```javascript
// 功能：让图层始终朝向目标
// 适用：摄像机跟随、视线追踪、聚光灯
// 放置位置：旋转属性 / 方向属性

// 2D 图层指向目标
var target = thisComp.layer("目标").position;
var dx = target[0] - position[0];
var dy = target[1] - position[1];
var angle = Math.atan2(dy, dx) * 180 / Math.PI;
angle + value;  // 叠加原旋转

// 3D 图层看向目标（用 lookAt）
var target = thisComp.layer("目标").position;
lookAt(position, target);
```

**使用场景：** 角色视线、聚光灯追踪、摄像机跟随、武器瞄准

---

#### 5. 摄像机锁定
```javascript
// 功能：让图层始终面向摄像机（广告牌效果）
// 适用：3D场景中的2D元素、粒子、文字
// 放置位置：3D 图层的方向属性

// 方法1：自动朝向摄像机
lookAt(position, thisComp.activeCamera.position);

// 方法2：只绕Y轴旋转（更稳定）
var cam = thisComp.activeCamera;
var dx = cam.position[0] - position[0];
var dz = cam.position[2] - position[2];
var yRot = Math.atan2(dx, dz) * 180 / Math.PI;
[value[0], yRot, value[2]];
```

**使用场景：** 3D空间中的标牌、粒子精灵、游戏UI

---

### 5.4 音频驱动类

#### 1. 音频振幅驱动缩放
```javascript
// 功能：根据音频振幅控制缩放
// 适用：音乐可视化、节拍同步
// 放置位置：缩放属性
// 前置条件：将音频层转换为关键帧（动画→关键帧辅助→将音频转换为关键帧）

var audioLayer = thisComp.layer("音频振幅");
var amp = audioLayer.effect("两个通道")("两个通道").value;

// 将振幅映射到合适的缩放范围
var minScale = 80;
var maxScale = 150;
var s = linear(amp, 0, 50, minScale, maxScale);
[s, s];
```

**参数说明：**
- `amp`：音频振幅值（取决于音频文件，一般 0-20 左右）
- `minScale`：最低缩放（安静时）
- `maxScale`：最高缩放（大声时）

**使用场景：** 音乐节奏动画、可视化音频、节拍同步

---

#### 2. 音频频谱驱动多图层
```javascript
// 功能：每个图层对应一个频段
// 适用：频谱可视化、均衡器动画
// 放置位置：多个图层的缩放/位置属性
// 前置条件：音频频谱效果 + 提取关键帧

// 假设有 10 个图层，每个对应一个频段
var bandIndex = index - 1;  // 当前图层对应第几个频段
var audioLayer = thisComp.layer("音频");
var freq = audioLayer.effect("频谱")(bandIndex + 1).value;  // 根据实际情况调整

var height = linear(freq, 0, 100, 10, 300);
[value[0], height];
```

**使用场景：** 音乐可视化、均衡器、音频反应图形

---

#### 3. 音乐卡点关键帧生成
```javascript
// 注意：这个功能通常用脚本实现，表达式可以读取已有的关键帧
// 这里展示如何利用音频关键帧做卡点动画

// 检测节拍（音频振幅突变）
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道");
var threshold = 15;  // 阈值
var current = audio.value;
var prev = audio.valueAtTime(time - thisComp.frameDuration);

// 当前帧振幅是否超过阈值且在上升
var isBeat = current > threshold && current > prev;

// 用节拍触发动画
if (isBeat) {
    100;  // 节拍时闪一下
} else {
    0;
}
```

**使用场景：** 音乐MV、节拍同步动画、踩点效果

---

### 5.5 时间控制类

#### 1. 时间重映射控制
```javascript
// 功能：控制图层的播放时间
// 适用：时间减速、倒放、定格、循环播放
// 放置位置：时间重映射（Time Remap）属性
// 前置条件：启用时间重映射（图层→时间→启用时间重映射）

// 正常播放（等同不启用）
time;

// 加速 2 倍
time * 2;

// 减速 0.5 倍
time * 0.5;

// 延迟 1 秒开始
Math.max(0, time - 1);

// 前 2 秒静止，然后开始播放
Math.max(0, time - 2);
```

**使用场景：** 变速播放、时间扭曲、慢动作、快进效果

---

#### 2. 时间倒流
```javascript
// 功能：倒放视频
// 适用：倒放效果、时间倒流
// 放置位置：时间重映射

// 完全倒放
thisLayer.outPoint - time;

// 先正放再倒放（乒乓）
var totalTime = outPoint - inPoint;
var t = time % (totalTime * 2);
if (t < totalTime) {
    t;  // 正放
} else {
    totalTime * 2 - t;  // 倒放
}
```

**使用场景：** 倒放特效、时间倒流动画、循环视频

---

#### 3. 随机时间偏移
```javascript
// 功能：每个图层有不同的随机起始时间
// 适用：随机错峰动画、避免同步
// 放置位置：时间重映射

seedRandom(index, true);  // 用图层索引作为种子
var randomOffset = random(0, 2);  // 随机 0-2 秒偏移
var totalTime = outPoint - inPoint;

var t = time + randomOffset;
t % totalTime;  // 循环播放
```

**使用场景：** 粒子阵列、随机动画错峰、人群动画

---

#### 4. 帧抖动
```javascript
// 功能：随机跳帧（复古/故障效果）
// 适用：故障艺术、复古效果、信号干扰
// 放置位置：时间重映射

var jitterAmount = 0.1;  // 抖动幅度（秒）
var jitterFreq = 10;     // 抖动频率（每秒次数）

// 随机但稳定（每几帧变一次）
var t = Math.floor(time * jitterFreq) / jitterFreq;
seedRandom(t, true);
var offset = random(-jitterAmount, jitterAmount);
valueAtTime(time + offset);
```

**使用场景：** 故障艺术、VHS效果、信号干扰、迷幻效果

---

### 5.6 效果联动类

#### 1. 发光强度联动
```javascript
// 功能：根据其他属性控制发光强度
// 适用：能量球、辉光、发光效果
// 放置位置：发光效果的"发光强度"

// 与缩放联动（越大越亮）
var s = scale[0];
linear(s, 50, 150, 0, 200);

// 与速度联动（越快越亮）
var p = position;
var speed = length(p.velocity);
linear(speed, 0, 500, 0, 150);
```

**使用场景：** 能量效果、速度线、发光动画

---

#### 2. 模糊联动
```javascript
// 功能：运动模糊（速度越快越模糊）
// 适用：运动物体、速度感
// 放置位置：高斯模糊的"模糊度"

// 位置速度驱动模糊
var speed = length(position.velocity);
linear(speed, 0, 300, 0, 30);

// 缩放速度驱动径向模糊
var scaleSpeed = Math.abs(scale.velocity[0]);
linear(scaleSpeed, 0, 200, 0, 50);
```

**使用场景：** 运动模糊、速度感、快速移动物体

---

#### 3. 颜色联动
```javascript
// 功能：根据位置/速度等改变颜色
// 适用：热力图、状态指示、渐变着色
// 放置位置：填充颜色 / 色调效果

// 位置X控制色相
var x = position[0];
var hue = linear(x, 0, thisComp.width, 0, 360);
hslToRgb([hue / 360, 1, 0.5, 1]);

// 速度控制颜色（蓝→红）
var speed = length(position.velocity);
var minSpeed = 0;
var maxSpeed = 500;
var t = linear(speed, minSpeed, maxSpeed, 0, 1);

var blue = [0, 0.5, 1, 1];
var red = [1, 0.2, 0, 1];
[
    linear(t, 0, 1, blue[0], red[0]),
    linear(t, 0, 1, blue[1], red[1]),
    linear(t, 0, 1, blue[2], red[2]),
    1
];
```

**使用场景：** 热力图、状态指示、速度着色、渐变动画

---

#### 4. 粒子数量联动
```javascript
// 功能：根据音乐或滑块控制粒子数量
// 适用：粒子特效、音乐可视化
// 放置位置：Particular 等粒子插件的"粒子/秒"

// 音频驱动粒子数量
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
linear(audio, 0, 20, 0, 500);

// 滑块控制
effect("控制")("粒子数量").value;
```

**使用场景：** 音乐粒子、爆炸效果、气氛控制

---

## 六、实战表达式100例速查

> 按类别整理的常用表达式，每个包含功能说明、完整代码、参数说明和适用场景。

---

### 6.1 基础动画（20例）

#### 例1：匀速移动
```javascript
// 功能：水平匀速移动
// 放置：位置
var speed = 200;  // 像素/秒
[value[0] + time * speed, value[1]];
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| speed | Number | 移动速度（像素/秒） |

**适用场景：** 背景滚动、前景飞过的元素

---

#### 例2：淡入淡出
```javascript
// 功能：开始淡入，结束淡出
// 放置：不透明度
var fadeInTime = 1;   // 淡入时长（秒）
var fadeOutTime = 1;  // 淡出时长（秒）
var dur = thisLayer.outPoint - thisLayer.inPoint;
var t = time - thisLayer.inPoint;

if (t < fadeInTime) {
    linear(t, 0, fadeInTime, 0, 100);
} else if (t > dur - fadeOutTime) {
    linear(t, dur - fadeOutTime, dur, 100, 0);
} else {
    100;
}
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| fadeInTime | Number | 淡入时间（秒） |
| fadeOutTime | Number | 淡出时间（秒） |

**适用场景：** 文字出现消失、元素渐显渐隐

---

#### 例3：缩放弹出
```javascript
// 功能：从0弹性缩放到100%
// 放置：缩放
var dur = 0.8;  // 动画时长
var t = Math.min(time / dur, 1);
var overshoot = 1.2;  // 过冲量

var s = easeOut(t, 0, overshoot * 100) 
    + Math.sin(t * Math.PI * 4) * (1 - t) * 20;
[s, s];
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| dur | Number | 动画总时长 |
| overshoot | Number | 过冲系数 |

**适用场景：** 按钮出现、弹窗弹出、图标显示

---

#### 例4：旋转进入
```javascript
// 功能：旋转着出现（缩放+旋转）
// 放置：旋转
var dur = 1;
var t = Math.min(time / dur, 1);
easeOut(t, -360, 0);
```

**适用场景：** Logo出现、图标旋转进入

---

#### 例5：从左滑入
```javascript
// 功能：从左侧滑入到当前位置
// 放置：位置
var dur = 1;
var offset = 500;  // 滑动距离
var t = Math.min(time / dur, 1);
var x = easeOut(t, value[0] - offset, value[0]);
[x, value[1]];
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| dur | Number | 动画时长 |
| offset | Number | 滑动距离（像素） |

**适用场景：** 文字动画、UI滑入效果

---

#### 例6：从上落下
```javascript
// 功能：从上方落下+弹跳
// 放置：位置
var dur = 1.5;
var fallDist = 400;
var t = Math.min(time / dur, 1);

var fall = easeOut(t, 0, fallDist);
var bounce = Math.abs(Math.sin(t * Math.PI * 5)) * 30 * (1 - t);
var y = value[1] - fallDist + fall + bounce;
[value[0], y];
```

**适用场景：** 物体掉落、文字下坠

---

#### 例7：闪烁效果
```javascript
// 功能：随机闪烁
// 放置：不透明度
var freq = 10;   // 每秒闪烁次数
var minOp = 20;  // 最低不透明度
var maxOp = 100; // 最高不透明度

// 使用wiggle实现
wiggle(freq, (maxOp - minOp) / 2);
```

**适用场景：** 星光、灯光闪烁、故障效果

---

#### 例8：逐字出现
```javascript
// 功能：文字逐字淡入（需要文字动画器辅助，或用源文本）
// 放置：不透明度（配合文字范围选择器的偏移）
// 注：更简单的做法是用文字动画器的偏移+模糊
var delay = 0.5;
var t = Math.max(0, time - delay);
linear(t, 0, 1, 0, 100);
```

**适用场景：** 标题文字动画、歌词显示

---

#### 例9：沿路径运动
```javascript
// 功能：沿蒙版路径运动
// 放置：位置（需要蒙版路径）
// 前置条件：图层有一个蒙版路径
var dur = 3;
var t = Math.min(time / dur, 1);
var path = mask("蒙版 1").maskPath;
path.pointOnPath(t);
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| dur | Number | 走完路径的时间 |

**适用场景：** 轨迹运动、沿路径写字、物体沿轨道运动

---

#### 例10：自动旋转
```javascript
// 功能：自动持续旋转
// 放置：旋转
var rpm = 10;  // 每分钟转速
time * rpm * 6;  // 360/60 = 6
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| rpm | Number | 每分钟转数 |

**适用场景：** 车轮、风扇、齿轮、加载动画

---

#### 例11：波浪运动
```javascript
// 功能：正弦波上下运动
// 放置：位置
var freq = 1;    // 频率（Hz）
var amp = 50;    // 振幅（像素）
var y = value[1] + Math.sin(time * freq * Math.PI * 2) * amp;
[value[0], y];
```

**适用场景：** 漂浮物、波浪、气球

---

#### 例12：抖动效果
```javascript
// 功能：随机位置抖动
// 放置：位置
var freq = 5;   // 每秒抖动次数
var amp = 10;   // 抖动幅度
wiggle(freq, amp);
```

**适用场景：** 手持相机效果、地震、故障

---

#### 例13：缩放脉冲
```javascript
// 功能：周期性缩放脉冲
// 放置：缩放
var freq = 1;    // 每秒脉冲次数
var minS = 80;
var maxS = 120;
var s = linear(Math.sin(time * freq * Math.PI * 2), -1, 1, minS, maxS);
[s, s];
```

**适用场景：** 心跳、呼吸、发光脉冲

---

#### 例14：旋转钟摆
```javascript
// 功能：钟摆式旋转
// 放置：旋转
var freq = 0.5;  // 频率
var amp = 45;    // 最大角度
Math.sin(time * freq * Math.PI * 2) * amp;
```

**适用场景：** 钟摆、秋千、节拍器

---

#### 例15：渐显缩放
```javascript
// 功能：从小到大渐显
// 放置：缩放 + 不透明度（分别放）
// 缩放：
var dur = 1;
var t = Math.min(time / dur, 1);
var s = easeOut(t, 0, 100);
[s, s];
```

**适用场景：** 元素出现、圆形扩散

---

#### 例16：颜色渐变
```javascript
// 功能：颜色从A变到B
// 放置：填充颜色 / 效果颜色
var color1 = [1, 0, 0, 1];  // 红
var color2 = [0, 0, 1, 1];  // 蓝
var dur = 3;
var t = Math.min(time / dur, 1);
[
    linear(t, 0, 1, color1[0], color2[0]),
    linear(t, 0, 1, color1[1], color2[1]),
    linear(t, 0, 1, color1[2], color2[2]),
    1
];
```

**适用场景：** 颜色过渡、状态变化指示

---

#### 例17：螺旋放大
```javascript
// 功能：螺旋出现（旋转+放大）
// 放置：缩放 + 旋转（缩放表达式）
var dur = 2;
var t = Math.min(time / dur, 1);
var s = easeOut(t, 0, 100);
[s, s];
// 旋转表达式：
// var dur = 2;
// var t = Math.min(time / dur, 1);
// easeOut(t, -720, 0);
```

**适用场景：** 漩涡、星系、入口动画

---

#### 例18：弹性缩放
```javascript
// 功能：弹性效果（弹簧）
// 放置：缩放
function elastic(t, amp, freq, decay) {
    if (t >= 1) return 0;
    return Math.sin(t * freq * Math.PI * 2) * amp * Math.exp(-t * decay);
}
var t = Math.min(time / 0.8, 1);
var base = easeOut(t, 0, 100);
var s = base + elastic(t, 15, 4, 5);
[s, s];
```

**适用场景：** 弹簧、果冻、弹性按钮

---

#### 例19：缓动位移
```javascript
// 功能：指定时间内从A到B（缓动）
// 放置：位置
var startPos = [100, 300];
var endPos = [600, 300];
var startTime = 1;
var endTime = 3;
ease(time, startTime, endTime, startPos, endPos);
```

**适用场景：** 精确的位移动画、UI过渡

---

#### 例20：循环路径
```javascript
// 功能：循环播放关键帧路径
// 放置：位置
loopOut("cycle");
```

**适用场景：** 循环路径动画、重复运动

---

### 6.2 控制器联动（20例）

#### 例21：滑块控制位置
```javascript
// 功能：滑块控制X轴位置
// 放置：位置
var min = 0;      // 滑块0时的位置
var max = 1000;   // 滑块100时的位置
var s = effect("滑块控制")("滑块").value;
var x = linear(s, 0, 100, min, max);
[x, value[1]];
```

**适用场景：** 位置控制、滑动切换

---

#### 例22：角度控制旋转
```javascript
// 功能：角度控件直接控制旋转
// 放置：旋转
effect("角度控制")("角度").value;
```

**适用场景：** 旋钮、方向盘、指针

---

#### 例23：复选框显隐
```javascript
// 功能：勾选显示，不勾选隐藏（带过渡）
// 放置：不透明度
var check = effect("复选框控制")("复选框").value;
var transition = 0.3;
var val = check;  // 0 或 1
// 因为复选框没有关键帧，过渡需要用valueAtTime
// 简化版直接切换：
check * 100;
```

**适用场景：** 开关控制、图层显隐

---

#### 例24：颜色控制着色
```javascript
// 功能：用颜色控件改变填充色
// 放置：填充效果的颜色
effect("颜色控制")("颜色").value;
```

**适用场景：** 主题色控制、统一调色

---

#### 例25：点控制目标
```javascript
// 功能：图层指向点控件位置
// 放置：旋转
var target = effect("点控制")("点").value;
var dx = target[0] - position[0];
var dy = target[1] - position[1];
Math.atan2(dy, dx) * 180 / Math.PI + 90;  // +90因为图层默认朝上
```

**适用场景：** 指针、武器瞄准、视线追踪

---

#### 例26：主滑块控制多图层
```javascript
// 功能：一个主滑块控制多个子图层
// 放置：每个子图层的位置/缩放
var ctrl = thisComp.layer("控制器");
var master = ctrl.effect("主控制")("滑块").value;
var offset = (index - 1) * 10;  // 每层偏移
[value[0], value[1] + master + offset];
```

**适用场景：** 批量控制、阵列动画、波形

---

#### 例27：滑块范围映射
```javascript
// 功能：滑块0-100映射到任意范围
// 放置：缩放（示例）
var s = effect("滑块")("滑块").value;
var outMin = 50;
var outMax = 200;
var result = linear(s, 0, 100, outMin, outMax);
[result, result];
```

**适用场景：** 参数调整、范围映射

---

#### 例28：双滑块控制XY
```javascript
// 功能：两个滑块分别控制X和Y
// 放置：位置
var x = effect("X控制")("滑块").value;
var y = effect("Y控制")("滑块").value;
[x, y];
```

**适用场景：** 2D位置控制、手柄控制

---

#### 例29：滑块控制速度
```javascript
// 功能：滑块控制动画播放速度
// 放置：时间重映射
var speed = effect("速度")("滑块").value;  // 1 = 正常速度
time * speed;
```

**适用场景：** 变速控制、速度调整

---

#### 例30：颜色混合控制
```javascript
// 功能：滑块控制两种颜色混合
// 放置：颜色属性
var c1 = effect("颜色A")("颜色").value;
var c2 = effect("颜色B")("颜色").value;
var mix = effect("混合")("滑块").value / 100;
[
    c1[0] * (1 - mix) + c2[0] * mix,
    c1[1] * (1 - mix) + c2[1] * mix,
    c1[2] * (1 - mix) + c2[2] * mix,
    c1[3] * (1 - mix) + c2[3] * mix
];
```

**适用场景：** 颜色过渡、渐变控制

---

#### 例31：复选框切换效果
```javascript
// 功能：勾选用效果A，不勾选用效果B
// 放置：效果参数（如不透明度）
var check = effect("开关")("复选框").value;
var effectA = effect("效果A")("数量").value;
var effectB = effect("效果B")("数量").value;
check == 1 ? effectA : effectB;
```

**适用场景：** 效果切换、模式切换

---

#### 例32：图层控制跟随
```javascript
// 功能：跟随指定图层（图层控件选择）
// 放置：位置
var target = effect("目标图层")("图层").value;
target.position;
```

**适用场景：** 动态选择跟随目标

---

#### 例33：音频滑块映射
```javascript
// 功能：音频振幅映射到滑块范围
// 放置：任意属性
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
linear(audio, 0, 30, 0, 100);
```

**适用场景：** 音频驱动任何属性

---

#### 例34：计数滑块
```javascript
// 功能：数字计数动画（从0数到N）
// 放置：滑块（或源文本）
var startVal = 0;
var endVal = 1000;
var dur = 3;
var t = Math.min(time / dur, 1);
easeOut(t, startVal, endVal);
```

**适用场景：** 数字滚动、计数器、进度显示

---

#### 例35：百分比显示
```javascript
// 功能：滑块值显示为百分比文字
// 放置：源文本（文字图层）
var val = effect("进度")("滑块").value;
Math.round(val) + "%";
```

**适用场景：** 进度条文字、百分比显示

---

#### 例36：滑块控制模糊
```javascript
// 功能：滑块控制模糊程度
// 放置：高斯模糊的模糊度
effect("模糊量")("滑块").value;
```

**适用场景：** 景深控制、聚焦调整

---

#### 例37：滑块控制发光
```javascript
// 功能：滑块控制发光强度
// 放置：发光效果的发光强度
effect("发光强度")("滑块").value;
```

**适用场景：** 亮度控制、辉光调整

---

#### 例38：多滑块混合控制
```javascript
// 功能：多个滑块混合控制一个属性
// 放置：位置（示例）
var offsetX = effect("偏移X")("滑块").value;
var offsetY = effect("偏移Y")("滑块").value;
var baseX = effect("基础X")("滑块").value;
var baseY = effect("基础Y")("滑块").value;
[baseX + offsetX, baseY + offsetY];
```

**适用场景：** 复杂参数控制、精细调整

---

#### 例39：角度控制方向
```javascript
// 功能：角度控制移动方向+滑块控制距离
// 放置：位置
var angle = effect("方向")("角度").value;
var dist = effect("距离")("滑块").value;
var rad = angle * Math.PI / 180;
var x = value[0] + Math.cos(rad) * dist;
var y = value[1] + Math.sin(rad) * dist;
[x, y];
```

**适用场景：** 极坐标控制、方向+距离

---

#### 例40：复选框反转
```javascript
// 功能：勾选时隐藏，不勾选时显示（反逻辑）
// 放置：不透明度
var check = effect("反转开关")("复选框").value;
(1 - check) * 100;
```

**适用场景：** 反向开关、禁用状态

---

### 6.3 三维相关（15例）

#### 例41：广告牌效果
```javascript
// 功能：3D图层始终面向摄像机
// 放置：方向（3D图层）
lookAt(position, thisComp.activeCamera.position);
```

**适用场景：** 3D空间中的标牌、粒子精灵

---

#### 例42：3D旋转自动
```javascript
// 功能：3D图层自动绕Y轴旋转
// 放置：Y旋转
var speed = 90;  // 度/秒
time * speed;
```

**适用场景：** 3D物体旋转、展示动画

---

#### 例43：摄像机环绕
```javascript
// 功能：摄像机绕中心点环绕
// 放置：摄像机位置
var center = [thisComp.width/2, thisComp.height/2, 0];
var radius = 500;
var speed = 0.2;  // 圈/秒
var angle = time * speed * Math.PI * 2;
var height = 200;
[
    center[0] + Math.cos(angle) * radius,
    center[1] - height,
    center[2] + Math.sin(angle) * radius
];
```

**适用场景：** 产品展示、场景巡游

---

#### 例44：景深距离联动
```javascript
// 功能：摄像机焦距对准目标图层
// 放置：摄像机的焦距
var cam = thisLayer;
var target = thisComp.layer("目标").position;
var camPos = cam.position;
length(camPos - target);
```

**适用场景：** 自动对焦、景深跟随

---

#### 例45：3D目标朝向
```javascript
// 功能：3D图层看向目标
// 放置：方向（3D图层）
var target = thisComp.layer("目标").position;
lookAt(position, target);
```

**适用场景：** 角色视线、聚光灯、炮塔

---

#### 例46：Z轴深度缩放
```javascript
// 功能：根据Z轴位置自动调整缩放（模拟真实透视）
// 放置：缩放（伪3D，不需要开启3D图层）
var z = position[2];  // 如果是3D图层
var focal = 1000;     // 焦距
var s = value[0] * (focal / (focal - z));
[s, s];
```

**适用场景：** 2.5D效果、伪3D透视

---

#### 例47：Z轴排序（图层顺序）
```javascript
// 注意：表达式不能改变图层顺序
// 替代方案：用脚本或手动调整
// 这里提供一个计算Z深度的表达式
// 放置：不透明度（调试用，显示深度）
// 实际应用中用脚本排序
position[2];
```

**适用场景：** 3D空间深度管理

---

#### 例48：3D路径动画
```javascript
// 功能：3D空间中沿路径运动+始终朝向运动方向
// 放置：位置（需要3D蒙版路径，或手动计算）
// 方向：
var speed = 100;
var nextPos = position.valueAtTime(time + 0.1);
lookAt(position, nextPos);
```

**适用场景：** 飞行路径、摄像机运动

---

#### 例49：3D波动（正弦）
```javascript
// 功能：Z轴正弦波动
// 放置：位置（3D图层）
var freq = 1;
var amp = 50;
var z = value[2] + Math.sin(time * freq * Math.PI * 2) * amp;
[value[0], value[1], z];
```

**适用场景：** 3D波浪、浮动平台

---

#### 例50：摄像机震动
```javascript
// 功能：摄像机位置随机抖动
// 放置：摄像机位置
var freq = 2;
var amp = 15;
wiggle(freq, amp);
```

**适用场景：** 地震、爆炸、手持效果

---

#### 例51：3D图层矩阵变换
```javascript
// 功能：获取图层的世界坐标
// 放置：位置（显示用）
// 获取锚点的世界坐标
toWorld(anchorPoint);
```

**适用场景：** 3D空间坐标转换、全局定位

---

#### 例52：从世界坐标到图层坐标
```javascript
// 功能：世界坐标转换为图层内坐标
// 放置：位置
var worldPoint = thisComp.layer("参考").toWorld([0,0,0]);
fromWorld(worldPoint);
```

**适用场景：** 坐标系统转换、空间映射

---

#### 例53：3D旋转跟随
```javascript
// 功能：3D图层旋转跟随父层（更灵活）
// 放置：X/Y/Z旋转
var parent = thisComp.layer("父级");
var offset = 30;  // 偏移角度
parent.rotationX + offset;
```

**适用场景：** 复杂的3D层级动画

---

#### 例54：距离感应缩放
```javascript
// 功能：离摄像机越近越大（模拟真实）
// 放置：缩放
var cam = thisComp.activeCamera;
var dist = length(position - cam.position);
var baseDist = 500;
var s = value[0] * (baseDist / dist);
[s, s];
```

**适用场景：** 真实感3D、空间感强化

---

#### 例55：3D聚光灯瞄准
```javascript
// 功能：聚光灯始终照向目标
// 放置：灯光的兴趣点（Point of Interest）
thisComp.layer("目标").position;
```

**适用场景：** 舞台灯光、追光灯、手电筒

---

### 6.4 音频驱动（10例）

#### 例56：音频驱动缩放
```javascript
// 功能：音乐节拍驱动缩放
// 放置：缩放
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
var base = 80;
var maxAdd = 70;
var s = base + linear(audio, 0, 30, 0, maxAdd);
[s, s];
```

**前置条件：** 动画→关键帧辅助→将音频转换为关键帧

**适用场景：** 音乐可视化、节拍跳动

---

#### 例57：音频驱动不透明度
```javascript
// 功能：音乐越响越亮
// 放置：不透明度
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
linear(audio, 0, 30, 20, 100);
```

**适用场景：** 音乐灯光、节拍闪烁

---

#### 例58：左/右声道分离
```javascript
// 功能：左声道控制左元素，右声道控制右元素
// 放置：左元素的缩放
var left = thisComp.layer("音频振幅").effect("左通道")("左通道").value;
linear(left, 0, 20, 50, 150);
// 右元素：
// var right = thisComp.layer("音频振幅").effect("右通道")("右通道").value;
```

**适用场景：** 立体声可视化、左右分离效果

---

#### 例59：音频驱动旋转
```javascript
// 功能：音量越大转得越快
// 放置：旋转
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
var speed = linear(audio, 0, 30, 10, 200);
time * speed;
```

**适用场景：** 唱片旋转、风扇、音乐驱动动画

---

#### 例60：音频频谱柱状图
```javascript
// 功能：多个图层组成频谱柱状图
// 放置：每个柱子的缩放Y（或位置Y）
// 前置：音频频谱效果+提取关键帧（10个频段）
var bandIndex = index - 1;  // 假设有10个图层
var audio = thisComp.layer("音频");
var val = audio.effect("频谱")(bandIndex + 1).value;
var h = linear(val, 0, 100, 5, 300);
[value[0], h];
```

**适用场景：** 音乐可视化、均衡器效果

---

#### 例61：节拍检测触发
```javascript
// 功能：检测节拍触发闪白
// 放置：不透明度（调整图层）
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道");
var threshold = 18;
var current = audio.value;
var prev = audio.valueAtTime(time - thisComp.frameDuration);
var isBeat = current > threshold && current > prev;
isBeat ? 50 : 0;
```

**适用场景：** 节拍闪光、踩点动画

---

#### 例62：音频驱动粒子
```javascript
// 功能：音量控制粒子数量
// 放置：Particular的"粒子/秒"
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
linear(audio, 0, 30, 0, 500);
```

**适用场景：** 音乐粒子、爆炸节奏

---

#### 例63：音频驱动颜色
```javascript
// 功能：音量控制颜色饱和度
// 放置：色调/饱和度效果的饱和度
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
linear(audio, 0, 30, 0, 100);
```

**适用场景：** 音乐节奏变色、情绪可视化

---

#### 例64：低音驱动震动
```javascript
// 功能：低频驱动画面震动
// 放置：调整图层的位置（整体震动）
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
var amp = linear(audio, 0, 30, 0, 20);
wiggle(10, amp);
```

**适用场景：** 重低音震动、爆炸感

---

#### 例65：音频波形绘制
```javascript
// 注意：表达式不能直接绘制波形
// 可以用波形效果 + 高度控制
// 放置：波形效果的高度
var audio = thisComp.layer("音频振幅").effect("两个通道")("两个通道").value;
linear(audio, 0, 30, 50, 200);
```

**适用场景：** 音频波形显示、语音动画

---

### 6.5 文字动画（15例）

#### 例66：文字长度适配背景
```javascript
// 功能：背景宽度随文字长度自动调整
// 放置：背景图层的缩放X / 蒙版路径
var textLayer = thisComp.layer("文字");
var rect = textLayer.sourceRectAtTime(time, false);
var padding = 40;  // 左右边距
var targetWidth = rect.width + padding;
[targetWidth / thisLayer.width * 100, value[1]];
```

**适用场景：** 自适应文字框、按钮背景

---

#### 例67：文字居中对齐
```javascript
// 功能：文字图层位置自动居中
// 放置：文字图层位置
var rect = sourceRectAtTime(time, false);
var x = rect.left + rect.width / 2;
var y = rect.top + rect.height / 2;
[x, y];
```

**适用场景：** 动态文字居中、对齐调整

---

#### 例68：逐字淡入（文字动画器辅助）
```javascript
// 功能：配合文字动画器的范围选择器实现逐字出现
// 放置：范围选择器-偏移（在文字动画器里）
var delay = 0;
var speed = 0.1;  // 每字时间
var t = Math.max(0, time - delay);
t / speed;  // 偏移量
```

**适用场景：** 打字机效果、逐字出现

---

#### 例69：数字滚动计数
```javascript
// 功能：数字从0滚动到目标值
// 放置：源文本
var start = 0;
var end = 9999;
var dur = 3;
var t = Math.min(time / dur, 1);
var val = easeOut(t, start, end);
Math.round(val).toString();
```

**适用场景：** 数据展示、计数器、进度数字

---

#### 例70：日期时间显示
```javascript
// 功能：显示当前日期时间（项目时间，非实时）
// 放置：源文本
var d = new Date();
d.getFullYear() + "-" + (d.getMonth()+1) + "-" + d.getDate();
```

**适用场景：** 时间戳、日期显示

---

#### 例71：文字大小写转换
```javascript
// 功能：将文字转为大写
// 放置：源文本
var orig = "Hello World";
orig.toUpperCase();  // 大写
// orig.toLowerCase();  // 小写
```

**适用场景：** 文字格式化、统一大小写

---

#### 例72：文字拼接组合
```javascript
// 功能：组合多个文字
// 放置：源文本
var prefix = "得分：";
var score = Math.round(time * 100);
prefix + score;
```

**适用场景：** 动态文字组合、标签+值

---

#### 例73：文字闪烁光标
```javascript
// 功能：末尾闪烁的光标（打字效果）
// 放置：源文本
var text = "正在输入";
var blinkSpeed = 0.5;
var showCursor = Math.floor(time / blinkSpeed) % 2 == 0;
text + (showCursor ? "|" : "");
```

**适用场景：** 打字效果、命令行风格

---

#### 例74：路径文字动画
```javascript
// 功能：文字沿路径运动（路径文字+首字边距）
// 放置：路径文字选项-首字边距
var dur = 5;
var t = Math.min(time / dur, 1);
easeOut(t, -500, 1000);
```

**适用场景：** 沿路径流动的文字、曲线标题

---

#### 例75：随机字符替换
```javascript
// 功能：类似黑客帝国的字符变化
// 放置：源文本
var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
var len = 10;
var result = "";
seedRandom(Math.floor(time * 10), false);
for (var i = 0; i < len; i++) {
    var idx = Math.floor(Math.random() * chars.length);
    result += chars[idx];
}
result;
```

**适用场景：** 黑客效果、解码动画、随机文字

---

#### 例76：文字行距自适应
```javascript
// 功能：多行文字垂直居中
// 放置：锚点Y
var rect = sourceRectAtTime(time, false);
rect.top + rect.height / 2;
```

**适用场景：** 多行文字居中、动态文本框

---

#### 例77：字符索引变色
```javascript
// 功能：指定范围的字符变色（用文字动画器）
// 放置：文字动画器-填充颜色
// 配合范围选择器使用，直接设置颜色
[1, 0, 0, 1];  // 红色
```

**适用场景：** 关键字高亮、重点标注

---

#### 例78：文字波浪效果
```javascript
// 功能：文字上下波动
// 放置：文字动画器的位置Y + 范围选择器（使用表达式选择器）
// 选择器-数量：
var freq = 2;
var amp = 30;
var offset = textIndex * 0.1;
Math.sin((time + offset) * freq * Math.PI * 2) * 50 + 50;
```

**适用场景：** 波浪文字、跳动文字

---

#### 例79：打字机效果
```javascript
// 功能：逐字出现的打字机效果
// 放置：源文本
var fullText = "这是一段打字机效果的文字";
var charSpeed = 0.1;  // 每个字符的时间
var numChars = Math.floor(time / charSpeed);
numChars = Math.min(numChars, fullText.length);
fullText.substr(0, numChars);
```

**适用场景：** 对话显示、打字效果、代码输入

---

#### 例80：数字格式化（千分位）
```javascript
// 功能：数字加千分位逗号
// 放置：源文本
function formatNumber(num) {
    var str = Math.round(num).toString();
    var result = "";
    var count = 0;
    for (var i = str.length - 1; i >= 0; i--) {
        result = str[i] + result;
        count++;
        if (count % 3 == 0 && i > 0) {
            result = "," + result;
        }
    }
    return result;
}
var num = time * 1000;
formatNumber(num);
```

**适用场景：** 大数据展示、金额显示

---

### 6.6 粒子特效（10例）

#### 例81：粒子数量滑块控制
```javascript
// 功能：滑块控制Particular粒子数量
// 放置：Particular - 粒子/秒（Particles/sec）
effect("控制")("粒子数量").value;
```

**适用场景：** 粒子浓度控制、爆发动画

---

#### 例82：粒子速度控制
```javascript
// 功能：滑块控制粒子速度
// 放置：Particular - 速度（Velocity）
effect("控制")("速度").value;
```

**适用场景：** 粒子速度调整、快慢控制

---

#### 例83：粒子大小动画
```javascript
// 功能：粒子尺寸随时间变化
// 放置：Particular - 粒子大小（Size）
var t = time;
easeOut(t, 0, 2, 0, 20);  // 0-2秒从小到大
```

**适用场景：** 粒子生长、爆炸扩散

---

#### 例84：粒子颜色渐变
```javascript
// 功能：粒子颜色随生命时间变化
// 放置：Particular - 颜色渐变（用生命期颜色）
// 注：一般直接在效果里设置渐变，表达式示例：
var life = 2;  // 粒子生命
var t = (time % life) / life;
var r = linear(t, 0, 1, 1, 0);
var g = 0.5;
var b = linear(t, 0, 1, 0, 1);
[r, g, b];
```

**适用场景：** 粒子颜色变化、火焰颜色

---

#### 例85：粒子重力调整
```javascript
// 功能：滑块控制重力
// 放置：Particular - 物理-空气-重力（Gravity）
effect("控制")("重力").value;
```

**适用场景：** 粒子下落速度调整

---

#### 例86：粒子发射器位置跟随
```javascript
// 功能：粒子发射器跟随图层运动
// 放置：Particular - 位置XY
thisComp.layer("发射器").position;
```

**适用场景：** 移动的粒子源、拖尾效果

---

#### 例87：粒子爆发（0到峰值）
```javascript
// 功能：瞬间爆发然后减少
// 放置：粒子/秒
var peakTime = 0.1;
var peakValue = 1000;
if (time < peakTime) {
    linear(time, 0, peakTime, 0, peakValue);
} else {
    easeOut(time, peakTime, 2, peakValue, 0);
}
```

**适用场景：** 爆炸效果、烟花、喷发

---

#### 例88：粒子风力控制
```javascript
// 功能：滑块控制风力
// 放置：Particular - 物理-空气-风向X/Y
effect("控制")("风力X").value;
```

**适用场景：** 粒子飘散方向控制

---

#### 例89：粒子生命时间控制
```javascript
// 功能：滑块控制粒子存活时间
// 放置：粒子生命（Life）
effect("控制")("生命").value;
```

**适用场景：** 粒子寿命调整、尾迹长度

---

#### 例90：粒子旋转速度
```javascript
// 功能：粒子自转速度
// 放置：Particular - 粒子-旋转-旋转速度
effect("控制")("旋转速度").value;
```

**适用场景：** 碎片旋转、粒子自旋

---

### 6.7 高级技巧（10例）

#### 例91：缓动函数自定义
```javascript
// 功能：自定义缓动曲线
// 放置：任意属性
function easeInOutCustom(t) {
    // 自定义S曲线
    if (t < 0.5) {
        return Math.pow(t * 2, 3) / 2;
    } else {
        return 1 - Math.pow((1 - t) * 2, 3) / 2;
    }
}
var t = Math.min(time / 2, 1);
var eased = easeInOutCustom(t);
linear(eased, 0, 1, 0, 500);
```

**适用场景：** 特殊缓动需求、自定义运动曲线

---

#### 例92：贝塞尔插值
```javascript
// 功能：模拟贝塞尔曲线插值
// 放置：位置
function bezier(t, p0, p1, p2, p3) {
    var t2 = t * t;
    var t3 = t2 * t;
    var mt = 1 - t;
    var mt2 = mt * mt;
    var mt3 = mt2 * mt;
    return [
        mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0],
        mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
    ];
}
var p0 = [100, 300];
var p1 = [300, 100];
var p2 = [500, 500];
var p3 = [700, 300];
var t = Math.min(time / 3, 1);
bezier(t, p0, p1, p2, p3);
```

**适用场景：** 贝塞尔路径、精确曲线控制

---

#### 例93：状态机（多阶段动画）
```javascript
// 功能：按时间分阶段执行不同动画
// 放置：位置
var phase = 0;
var t = time;

if (t < 1) {
    phase = 1;
} else if (t < 2) {
    phase = 2;
} else if (t < 3) {
    phase = 3;
}

switch (phase) {
    case 1:
        // 阶段1：从左进入
        [linear(t, 0, 1, -100, 200), 300];
        break;
    case 2:
        // 阶段2：上下浮动
        [200, 300 + Math.sin((t-1) * Math.PI * 2) * 30];
        break;
    case 3:
        // 阶段3：向右退出
        [linear(t, 2, 3, 200, 800), 300];
        break;
    default:
        [200, 300];
}
```

**适用场景：** 复杂的多阶段动画、状态切换

---

#### 例94：Lerp函数（线性插值封装）
```javascript
// 功能：更直观的线性插值函数
// 放置：任意属性
function lerp(a, b, t) {
    return a + (b - a) * t;
}
var t = Math.min(time / 2, 1);
lerp(0, 100, t);
```

**适用场景：** 代码复用、更清晰的插值逻辑

---

#### 例95：Clamp（钳位）函数
```javascript
// 功能：限制值在最小最大值之间
// 放置：任意属性
function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
}
var val = time * 100;
clamp(val, 0, 100);  // 限制在0-100
```

**适用场景：** 范围限制、边界约束

---

#### 例96：Map函数（范围映射）
```javascript
// 功能：将值从一个范围映射到另一个范围
// 放置：任意属性
function map(val, inMin, inMax, outMin, outMax) {
    return outMin + (outMax - outMin) * ((val - inMin) / (inMax - inMin));
}
var input = 50;
map(input, 0, 100, 0, 500);  // 50 -> 250
```

**适用场景：** 参数映射、单位换算

---

#### 例97：距离感应效果
```javascript
// 功能：两个图层距离越近效果越强
// 放置：效果参数
var other = thisComp.layer("目标").position;
var dist = length(position - other);
var maxDist = 300;
linear(dist, 0, maxDist, 100, 0);  // 越近越强
```

**适用场景：** 近场感应、磁力效果、交互反馈

---

#### 例98：自动居中合成
```javascript
// 功能：图层自动居中到合成
// 放置：位置
[thisComp.width / 2, thisComp.height / 2];
```

**适用场景：** 快速居中、对齐合成中心

---

#### 例99：随机但稳定（seedRandom）
```javascript
// 功能：每个图层有固定的随机值
// 放置：不透明度 / 位置偏移等
seedRandom(index, true);  // 用图层索引做种子，静止
var randomVal = Math.random() * 50;
50 + randomVal;
```

**适用场景：** 随机但一致的变化、阵列差异化

---

#### 例100：循环pingpong
```javascript
// 功能：关键帧乒乓循环（来回播放）
// 放置：带关键帧的属性
loopOut("pingpong");
```

**适用场景：** 往复运动、呼吸、钟摆

---

## 七、ExtendScript脚本开发基础

### 7.1 脚本与表达式的区别

| 特性 | 表达式（Expression） | 脚本（Script） |
|-----|---------------------|----------------|
| 运行时机 | 每一帧自动计算 | 用户手动触发或事件触发 |
| 作用对象 | 单个属性 | 整个项目、合成、图层等 |
| 能力范围 | 只读为主，只能修改所在属性值 | 几乎无限制，可创建/删除/修改任何内容 |
| 运行环境 | 属性计算管道 | AE主应用程序 |
| 文件格式 | 纯文本（写在属性上） | .jsx 文件 |
| 持久化 | 保存在项目文件中 | 独立的外部文件 |
| 性能影响 | 逐帧计算，影响渲染速度 | 执行一次，不影响实时渲染 |
| 调试难度 | 较难（错误信息有限） | 较易（可用 ESTK 调试） |

**核心区别：**
- **表达式**是被动的，每一帧自动重新计算，返回属性值
- **脚本**是主动的，由用户执行一次，可以执行任何操作

### 7.2 ExtendScript Toolkit 介绍

ExtendScript Toolkit（ESTK）是 Adobe 官方提供的脚本开发工具，用于编写和调试 ExtendScript 脚本。

**主要功能：**
- 代码编辑器（语法高亮、自动补全）
- 调试器（断点、单步执行、变量查看）
- JavaScript 控制台
- 对象模型查看器（Object Model Viewer）
- 多应用程序支持（AE、PS、AI 等）

**启动方式：**
- Windows：开始菜单 → Adobe → ExtendScript Toolkit
- 或者在 AE 中：文件 → 脚本 → 打开脚本编辑器

**注意：** 从 AE 2020 之后，Adobe 逐渐弃用 ESTK，推荐使用 VS Code + ExtendScript Debugger 插件进行开发。

### 7.3 脚本文件格式（.jsx）

AE 脚本文件使用 `.jsx` 扩展名，本质上是 JavaScript 文件。

**基本结构：**
```javascript
// 这是一个简单的 AE 脚本示例
// 文件名：HelloWorld.jsx

// 检查是否有项目打开
if (app.project == null) {
    alert("请先打开一个项目！");
    exit();
}

// 获取当前活动合成
var comp = app.project.activeItem;
if (comp == null || !(comp instanceof CompItem)) {
    alert("请先选择一个合成！");
    exit();
}

// 执行操作
alert("当前合成名称：" + comp.name + "\n图层数量：" + comp.numLayers);
```

**脚本头部规范：**
```javascript
/* =========================================
   脚本名称：我的脚本
   版本：1.0
   作者：XXX
   说明：这是一个示例脚本
   ========================================= */

// 使用严格模式（可选，但推荐）
// #target aftereffects

// 立即执行函数包裹，避免污染全局命名空间
(function() {
    // 你的代码在这里
    
    // 检查前提条件
    if (!app.project) {
        alert("请先打开项目");
        return;
    }
    
    // 主逻辑
    // ...
    
})();
```

### 7.4 运行脚本的方法

#### 方法一：菜单运行
1. 文件 → 脚本 → 运行脚本文件...
2. 选择 .jsx 文件
3. 脚本开始执行

#### 方法二：快速运行
1. 将 .jsx 文件放入 AE 安装目录的 `Scripts/ScriptUI Panels` 文件夹
2. 重启 AE
3. 在 窗口 菜单中找到并点击脚本名

#### 方法三：拖放运行
直接将 .jsx 文件拖入 AE 界面（某些版本支持）

#### 方法四：快捷键
可以通过设置自定义快捷键来运行常用脚本

#### 方法五：命令行
```bash
# Windows 命令行调用
AfterFX.exe -r "C:\path\to\script.jsx"
```

**安全设置：**
- 首次运行脚本时，AE 会询问是否允许执行
- 可以在 编辑 → 首选项 → 脚本和表达式 中设置：
  - 允许脚本写入文件和访问网络（默认关闭）
  - 允许脚本在应用程序启动时运行

### 7.5 脚本调试方法

#### 方法一：alert 调试（最简单）
```javascript
var comp = app.project.activeItem;
alert("合成名称：" + comp.name);
alert("图层数量：" + comp.numLayers);
```

#### 方法二：$.writeln 输出到控制台
```javascript
// 输出到 ESTK 控制台
$.writeln("当前时间：" + new Date());
$.writeln("图层数：" + app.project.activeItem.numLayers);
```

#### 方法三：ESTK 调试器
1. 用 ESTK 打开脚本
2. 设置断点（点击行号）
3. 按 F5 开始调试
4. 使用 F10（单步跳过）、F11（单步进入）、F8（继续）

#### 方法四：try/catch 错误捕获
```javascript
try {
    // 可能出错的代码
    var layer = app.project.activeItem.layer(999);  // 不存在的图层
} catch (e) {
    alert("出错了：\n" + e.message + "\n行号：" + e.line);
}
```

### 7.6 AE脚本DOM结构

AE 脚本的对象模型是一个层级结构：

```
app（应用程序）
├── project（项目）
│   ├── items（项目项集合）
│   │   ├── CompItem（合成）
│   │   │   ├── layers（图层集合）
│   │   │   │   ├── AVLayer（音视频图层）
│   │   │   │   ├── TextLayer（文字图层）
│   │   │   │   ├── CameraLayer（摄像机）
│   │   │   │   ├── LightLayer（灯光）
│   │   │   │   ├── ShapeLayer（形状图层）
│   │   │   │   └── ...（其他图层类型）
│   │   │   └── renderQueue（渲染队列）
│   │   ├── FootageItem（素材）
│   │   ├── FolderItem（文件夹）
│   │   └── ...（其他项目项）
│   └── renderQueue（渲染队列）
├── prefs（首选项）
├── version（版本信息）
└── ...（其他应用级对象）
```

### 7.7 常用对象详解

#### app - 应用程序对象
```javascript
// 应用程序信息
app.name;              // "Adobe After Effects"
app.version;           // 版本号，如 "24.0"
app.buildNumber;       // 构建号
app.osName;            // 操作系统名称

// 项目操作
app.project;           // 当前项目对象
app.project.file;      // 项目文件路径
app.project.save();    // 保存项目
app.project.saveAs(file); // 另存为

// 创建新项目
app.newProject();

// 打开项目
app.open(File("路径/到/项目.aep"));

// 退出
app.quit();
```

#### project - 项目对象
```javascript
var proj = app.project;

// 项目属性
proj.name;             // 项目名称
proj.file;             // 项目文件
proj.bitsPerChannel;   // 位深度（8, 16, 32）

// 项目项操作
proj.items;            // 所有项目项集合
proj.numItems;         // 项目项数量
proj.item(1);          // 第1个项目项（索引从1开始）
proj.itemByName("名称"); // 按名称查找

// 活动项（当前选中的）
proj.activeItem;       // 当前活动的合成或素材

// 新建合成
var newComp = proj.items.addComp(
    "新合成",    // 名称
    1920,        // 宽度
    1080,        // 高度
    1,           // 像素长宽比
    10,          // 持续时间（秒）
    25           // 帧率
);

// 导入素材
var file = new File("C:/path/to/video.mp4");
var footage = proj.importFile(new ImportOptions(file));

// 新建文件夹
var folder = proj.items.addFolder("我的文件夹");
```

#### CompItem - 合成对象
```javascript
var comp = app.project.activeItem;

// 合成属性
comp.name;             // 名称
comp.width;            // 宽度
comp.height;           // 高度
comp.duration;         // 持续时间（秒）
comp.frameRate;        // 帧率
comp.bgColor;          // 背景色 [r, g, b]

// 图层操作
comp.layers;           // 图层集合
comp.numLayers;        // 图层数量
comp.layer(1);         // 第1个图层（最上面是1）
comp.layer("图层名");  // 按名称找图层

// 添加图层
// 新建纯色层
var solid = comp.layers.addSolid(
    [1, 0, 0],     // 颜色 [r, g, b]
    "红色固态层",   // 名称
    1920,          // 宽度
    1080,          // 高度
    1,             // 像素比
    comp.duration  // 持续时间
);

// 新建空对象
var nullLayer = comp.layers.addNull();
nullLayer.name = "控制器";

// 新建文字层
var textLayer = comp.layers.addText("Hello World");

// 新建调整层
var adjLayer = comp.layers.addAdjustmentLayer();

// 新建形状层
var shapeLayer = comp.layers.addShape();

// 新建摄像机
var camera = comp.layers.addCamera("摄像机", [comp.width/2, comp.height/2]);

// 新建灯光
var light = comp.layers.addLight("灯光", [comp.width/2, comp.height/2]);

// 复制图层
var copy = layer.duplicate();

// 删除图层
layer.remove();
```

#### Layer - 图层对象
```javascript
var layer = comp.layer(1);

// 图层属性
layer.name;            // 名称
layer.index;           // 索引
layer.enabled;         // 是否启用
layer.solo;            // 独奏
layer.locked;          // 锁定
layer.shy;             // 害羞
layer.guideLayer;      // 引导层
layer.threeDLayer;     // 是否3D图层
layer.inPoint;         // 入点
layer.outPoint;        // 出点
layer.startTime;       // 开始时间
layer.width;           // 宽度
layer.height;          // 高度

// 变换属性
layer.transform.position;      // 位置
layer.transform.anchorPoint;   // 锚点
layer.transform.scale;         // 缩放
layer.transform.rotation;      // 旋转（2D）
layer.transform.opacity;       // 不透明度

// 效果
layer.effect;                   // 效果集合
layer.effect(1);                // 第1个效果
layer.effect("效果名");         // 按名称找效果

// 添加效果
var effect = layer.effect.addProperty("ADBE Gaussian Blur 2");
// 或者用效果名称（可能需要内部名称）
var gaussianBlur = layer.effect.addProperty("高斯模糊");

// 父级
layer.parent;          // 父图层
layer.parent = otherLayer;  // 设置父级

// 蒙版
layer.mask;            // 蒙版集合
layer.mask(1);         // 第1个蒙版

// 时间重映射
layer.timeRemapEnabled = true;  // 启用时间重映射
```

#### Property - 属性对象
```javascript
var prop = layer.transform.position;

// 属性值
prop.value;            // 当前值（合成时间）
prop.valueAtTime(t);   // 指定时间的值
prop.numKeys;          // 关键帧数量

// 关键帧操作
prop.setValueAtTime(t, value);  // 在时间t设置关键帧
prop.key(1);            // 第1个关键帧
prop.keyTime(1);        // 第1个关键帧的时间
prop.keyValue(1);       // 第1个关键帧的值

// 添加表达式
prop.expression = "time * 100";
prop.expressionEnabled = true;

// 属性名称
prop.name;             // 属性名
prop.matchName;        // 属性匹配名（内部名称）

// 移除关键帧
prop.removeKey(1);     // 删除第1个关键帧
prop.removeAllKeyframes();  // 删除所有关键帧
```

---

## 八、常用脚本片段

### 8.1 图层操作

#### 创建纯色层
```javascript
// 创建一个红色纯色层
var comp = app.project.activeItem;
var solidLayer = comp.layers.addSolid(
    [1, 0, 0],           // 颜色 RGB (0-1)
    "红色背景",          // 图层名称
    comp.width,          // 宽度
    comp.height,         // 高度
    comp.pixelAspect,    // 像素长宽比
    comp.duration        // 持续时间
);
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| color | Array | [r, g, b] 颜色值 (0-1) |
| name | String | 图层名称 |
| width | Number | 宽度（像素） |
| height | Number | 高度（像素） |
| pixelAspect | Number | 像素长宽比 |
| duration | Number | 持续时间（秒） |

**适用场景：** 批量创建纯色背景、占位图层

---

#### 创建空对象
```javascript
// 创建空对象控制器
var comp = app.project.activeItem;
var nullLayer = comp.layers.addNull(comp.duration);
nullLayer.name = "总控制器";

// 添加到合成顶部
nullLayer.moveToBeginning();
```

**适用场景：** 表达式控制器、父子关系的父级、虚拟参考点

---

#### 创建调整层
```javascript
// 创建调整图层
var comp = app.project.activeItem;
var adjLayer = comp.layers.addAdjustmentLayer();
adjLayer.name = "调色调整层";

// 添加调色效果
adjLayer.effect.addProperty("曲线");
```

**适用场景：** 统一调色、全局效果、批量调整

---

#### 创建文字层
```javascript
// 创建文字图层
var comp = app.project.activeItem;
var textLayer = comp.layers.addText("Hello World");
textLayer.name = "标题文字";

// 设置文字属性
var textProp = textLayer.property("Source Text");
var textDocument = textProp.value;
textDocument.fontSize = 72;
textDocument.font = "Microsoft YaHei";
textDocument.fillColor = [1, 1, 1];  // 白色
textProp.setValue(textDocument);
```

**适用场景：** 批量生成文字、标题动画、字幕

---

#### 删除图层
```javascript
// 删除指定名称的图层
var comp = app.project.activeItem;
var layerName = "要删除的图层";

try {
    var layer = comp.layer(layerName);
    layer.remove();
    alert("图层已删除：" + layerName);
} catch (e) {
    alert("找不到图层：" + layerName);
}
```

**适用场景：** 清理无用图层、批量删除

---

#### 排序图层
```javascript
// 按图层名称排序
var comp = app.project.activeItem;
var layers = [];

// 先收集所有图层名
for (var i = 1; i <= comp.numLayers; i++) {
    layers.push(comp.layer(i));
}

// 按名称排序
layers.sort(function(a, b) {
    return a.name.localeCompare(b.name);
});

// 重新排列（从下往上）
for (var j = 0; j < layers.length; j++) {
    layers[j].moveToEnd();
}
```

**适用场景：** 整理图层面板、按名称/类型排序

---

#### 重命名图层
```javascript
// 批量重命名图层（添加前缀）
var comp = app.project.activeItem;
var prefix = "新_";

app.beginUndoGroup("批量重命名");  // 开始撤销组

for (var i = 1; i <= comp.numLayers; i++) {
    var layer = comp.layer(i);
    if (layer.name.indexOf(prefix) !== 0) {
        layer.name = prefix + layer.name;
    }
}

app.endUndoGroup();  // 结束撤销组
```

**适用场景：** 批量重命名、统一命名规范

---

#### 设置父子关系
```javascript
// 设置子图层的父级
var comp = app.project.activeItem;
var parentLayer = comp.layer("控制器");
var childLayer = comp.layer("子图层");

childLayer.parent = parentLayer;
```

**适用场景：** 批量设置父子关系、层级动画

---

### 8.2 效果操作

#### 添加效果
```javascript
// 给图层添加效果
var layer = app.project.activeItem.layer(1);

// 添加高斯模糊
var gaussianBlur = layer.effect.addProperty("ADBE Gaussian Blur 2");
gaussianBlur.name = "高斯模糊";

// 添加色阶
var levels = layer.effect.addProperty("ADBE Color Balance");
levels.name = "色彩平衡";
```

**注意：** 有些效果需要使用内部匹配名（matchName），可以通过 ESTK 的对象模型查看器查询。

**适用场景：** 批量添加效果、效果预设

---

#### 删除效果
```javascript
// 删除指定效果
var layer = app.project.activeItem.layer(1);
var effectName = "高斯模糊";

try {
    var effect = layer.effect(effectName);
    effect.remove();
    alert("效果已删除");
} catch (e) {
    alert("找不到效果：" + effectName);
}
```

**适用场景：** 清理无用效果、批量移除

---

#### 设置效果参数
```javascript
// 设置效果参数值
var layer = app.project.activeItem.layer(1);
var effect = layer.effect("高斯模糊");

// 设置模糊度
var blurProperty = effect("模糊度");
blurProperty.setValue(25);

// 设置关键帧
blurProperty.setValueAtTime(0, 0);
blurProperty.setValueAtTime(1, 25);
blurProperty.setValueAtTime(2, 0);
```

**适用场景：** 批量设置效果、参数动画

---

#### 获取效果列表
```javascript
// 获取图层所有效果并列出
var layer = app.project.activeItem.layer(1);
var effectList = "图层 \"" + layer.name + "\" 的效果列表：\n\n";

for (var i = 1; i <= layer.effect.numProperties; i++) {
    var eff = layer.effect(i);
    effectList += i + ". " + eff.name + "  (" + eff.matchName + ")\n";
}

alert(effectList);
```

**适用场景：** 查看效果信息、调试

---

### 8.3 关键帧操作

#### 添加关键帧
```javascript
// 给位置属性添加关键帧
var layer = app.project.activeItem.layer(1);
var posProp = layer.transform.position;

// 在指定时间设置关键帧
posProp.setValueAtTime(0, [100, 100]);
posProp.setValueAtTime(2, [500, 300]);
posProp.setValueAtTime(4, [200, 500]);
```

**适用场景：** 程序化动画、批量生成关键帧

---

#### 删除关键帧
```javascript
// 删除所有关键帧
var prop = app.project.activeItem.layer(1).transform.position;
prop.removeAllKeyframes();

// 删除指定索引的关键帧
prop.removeKey(2);  // 删除第2个关键帧
```

**适用场景：** 清理关键帧、重置动画

---

#### 修改关键帧值
```javascript
// 修改第1个关键帧的值
var prop = app.project.activeItem.layer(1).transform.position;
if (prop.numKeys > 0) {
    var firstKeyTime = prop.keyTime(1);
    prop.setValueAtTime(firstKeyTime, [50, 50]);
}
```

**适用场景：** 批量调整关键帧数值

---

#### 移动关键帧
```javascript
// 将所有关键帧向右移动 1 秒
var prop = app.project.activeItem.layer(1).transform.position;
var offset = 1;  // 偏移量（秒）

app.beginUndoGroup("移动关键帧");

for (var i = prop.numKeys; i >= 1; i--) {
    var oldTime = prop.keyTime(i);
    var newTime = oldTime + offset;
    prop.setKeyTime(i, newTime);
}

app.endUndoGroup();
```

**适用场景：** 批量移动关键帧、调整动画时间

---

#### 缓动设置
```javascript
// 设置关键帧缓动（Easy Ease）
var prop = app.project.activeItem.layer(1).transform.position;

// 设置所有关键帧为自动贝塞尔
for (var i = 1; i <= prop.numKeys; i++) {
    prop.setTemporalEaseAtKey(
        i,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER
    );
}

// 设置关键帧为缓入缓出
for (var i = 1; i <= prop.numKeys; i++) {
    prop.setInterpolationTypeAtKey(
        i,
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.BEZIER
    );
}
```

**适用场景：** 批量设置缓动、统一动画曲线

---

### 8.4 合成操作

#### 创建合成
```javascript
// 创建新合成
var proj = app.project;
var newComp = proj.items.addComp(
    "我的新合成",   // 名称
    1920,           // 宽度
    1080,           // 高度
    1,              // 像素长宽比
    10,             // 持续时间（秒）
    25              // 帧率 (fps)
);

// 设置背景色
newComp.bgColor = [0.2, 0.2, 0.2];  // 深灰色

alert("合成已创建：" + newComp.name);
```

| 参数 | 类型 | 说明 |
|-----|------|------|
| name | String | 合成名称 |
| width | Number | 宽度（像素） |
| height | Number | 高度（像素） |
| pixelAspect | Number | 像素长宽比 |
| duration | Number | 持续时间（秒） |
| frameRate | Number | 帧率 |

**适用场景：** 批量创建合成、模板生成

---

#### 设置合成参数
```javascript
// 修改合成设置
var comp = app.project.activeItem;

// 修改名称
comp.name = "新合成名称";

// 修改尺寸
comp.width = 1280;
comp.height = 720;

// 修改帧率
comp.frameRate = 30;

// 修改背景色
comp.bgColor = [0, 0, 0];  // 黑色

// 修改持续时间
comp.duration = 15;  // 15秒
```

**适用场景：** 批量修改合成设置、尺寸调整

---

#### 获取合成信息
```javascript
// 获取当前合成的详细信息
var comp = app.project.activeItem;

var info = "";
info += "合成名称：" + comp.name + "\n";
info += "尺寸：" + comp.width + " × " + comp.height + "\n";
info += "帧率：" + comp.frameRate + " fps\n";
info += "时长：" + comp.duration.toFixed(2) + " 秒\n";
info += "图层数量：" + comp.numLayers + "\n";
info += "背景色：" + comp.bgColor.join(", ");

alert(info);
```

**适用场景：** 项目检查、信息统计

---

#### 渲染队列操作
```javascript
// 将合成添加到渲染队列
var comp = app.project.activeItem;
var rq = app.project.renderQueue;

// 添加到渲染队列
var rqItem = rq.items.add(comp);

// 设置输出模块
var om = rqItem.outputModule(1);
om.file = new File("C:/output/myVideo.mp4");

// 设置输出格式（可能需要调整）
om.setSettings({
    "Format": "H.264",
    "Video Output": {
        "Quality": 80
    }
});

// 开始渲染
rq.render();
```

**适用场景：** 批量渲染、自动化输出

---

### 8.5 项目操作

#### 导入素材
```javascript
// 导入单个素材文件
var proj = app.project;
var file = new File("C:/Videos/clip.mp4");

if (file.exists) {
    var importOptions = new ImportOptions(file);
    var footage = proj.importFile(importOptions);
    alert("已导入：" + footage.name);
} else {
    alert("文件不存在！");
}
```

**适用场景：** 批量导入素材、素材管理

---

#### 新建文件夹
```javascript
// 在项目中新建文件夹
var proj = app.project;
var folder = proj.items.addFolder("素材");

// 创建子文件夹
var subFolder = proj.items.addFolder("视频素材");
subFolder.parentFolder = folder;
```

**适用场景：** 项目结构整理、素材分类

---

#### 查找素材
```javascript
// 按名称查找项目项
var proj = app.project;
var searchName = "视频";
var results = [];

for (var i = 1; i <= proj.numItems; i++) {
    var item = proj.item(i);
    if (item.name.indexOf(searchName) !== -1) {
        results.push(item);
    }
}

var msg = "找到 " + results.length + " 个匹配项：\n\n";
for (var j = 0; j < results.length; j++) {
    msg += (j+1) + ". " + results[j].name + "\n";
}
alert(msg);
```

**适用场景：** 素材查找、项目整理

---

#### 保存项目
```javascript
// 保存当前项目
var proj = app.project;

// 普通保存
proj.save();

// 另存为
var saveFile = new File("C:/Projects/newProject.aep");
proj.saveAs(saveFile);

// 增量保存（保存副本）
var saveCopy = new File("C:/Projects/backup.aep");
proj.saveAsCopy(saveCopy);
```

**适用场景：** 自动备份、批量保存

---

## 九、表达式性能优化

### 9.1 表达式对性能的影响

表达式在 AE 中是逐帧计算的，每一帧都要重新执行所有相关表达式。这会对渲染性能产生显著影响：

**性能影响因素：**
1. **表达式数量**：表达式越多，计算量越大
2. **表达式复杂度**：循环、嵌套引用、图层遍历会大幅增加计算时间
3. **引用层数**：引用其他图层会触发依赖计算
4. **采样次数**：`valueAtTime` 等时间采样会额外计算
5. **图层数量**：多图层联动呈指数级增长

**性能表现：**
- 预览时卡顿、跳帧
- 渲染速度变慢
- 内存占用增加
- 风扇转速加快（CPU/GPU 高负载）

### 9.2 优化原则

#### 原则一：避免不必要的计算
```javascript
// 不好：每次都重新计算
var centerX = thisComp.width / 2;
var centerY = thisComp.height / 2;
var angle = time * 2;
[centerX + Math.cos(angle) * 100, centerY + Math.sin(angle) * 100];

// 好一点：尽量减少重复计算
// （表达式中没有静态变量，只能尽量简化逻辑）
var t = time * 2;
var r = 100;
var cx = thisComp.width / 2;
var cy = thisComp.height / 2;
[cx + Math.cos(t) * r, cy + Math.sin(t) * r];
```

#### 原则二：缓存中间结果
```javascript
// 不好：多次调用同一个函数
var a = Math.sin(time) * 100;
var b = Math.sin(time) * 50;
var c = Math.sin(time) * 25;

// 好：计算一次，重复使用
var sinVal = Math.sin(time);
var a = sinVal * 100;
var b = sinVal * 50;
var c = sinVal * 25;
```

#### 原则三：减少图层引用
```javascript
// 不好：多次引用同一个图层
var x = thisComp.layer("控制器").effect("滑块1")("滑块").value;
var y = thisComp.layer("控制器").effect("滑块2")("滑块").value;
var z = thisComp.layer("控制器").effect("滑块3")("滑块").value;

// 好：保存图层引用
var ctrl = thisComp.layer("控制器");
var x = ctrl.effect("滑块1")("滑块").value;
var y = ctrl.effect("滑块2")("滑块").value;
var z = ctrl.effect("滑块3")("滑块").value;
```

#### 原则四：避免循环
```javascript
// 不好：100次循环，性能差
var sum = 0;
for (var i = 1; i <= 100; i++) {
    sum += i;
}
sum;

// 好：用数学公式代替循环
var n = 100;
n * (n + 1) / 2;
```

#### 原则五：减少 valueAtTime 的使用
```javascript
// 不好：多次采样
var past1 = valueAtTime(time - 0.1);
var past2 = valueAtTime(time - 0.2);
var past3 = valueAtTime(time - 0.3);
(past1 + past2 + past3) / 3;

// 好：尽量减少采样次数，或者用更简单的方法
// 如果只需要延迟，用一次就够
valueAtTime(time - 0.2);
```

#### 原则六：避免遍历所有图层
```javascript
// 不好：遍历所有图层（图层多的时候极慢）
var total = 0;
for (var i = 1; i <= thisComp.numLayers; i++) {
    total += thisComp.layer(i).transform.opacity;
}
total / thisComp.numLayers;

// 好：用控制层集中存储数据，避免遍历
// （提前把数据存在控制层的滑块上）
effect("平均值")("滑块").value;
```

### 9.3 常见性能陷阱

#### 陷阱一：过度使用 wiggle
```javascript
// 一般情况
wiggle(5, 10);

// 高倍频程（octaves 参数越大越慢）
wiggle(5, 10, 5);  // 5个倍频程，比默认1个慢很多

// 建议：除非必要，否则保持 octaves = 1（默认）
wiggle(5, 10, 1);
```

#### 陷阱二：递归引用（循环依赖）
```javascript
// 危险！图层A引用图层B，图层B引用图层A
// 可能导致死循环或无限递归

// 图层A的位置表达式：
thisComp.layer("B").position;

// 图层B的位置表达式：
thisComp.layer("A").position;
// 这会导致错误或性能灾难
```

#### 陷阱三：长链引用
```javascript
// 不好：链式引用过长
thisComp.layer("A").effect("E1")("P1").value + 
thisComp.layer("B").effect("E2")("P2").value + 
thisComp.layer("C").effect("E3")("P3").value;

// 注意：每个图层引用都会触发该图层的所有表达式计算
// 如果 A/B/C 又引用了其他图层，性能会指数级下降
```

#### 陷阱四：不必要的 sourceRectAtTime
```javascript
// sourceRectAtTime 相对较慢，不要滥用
var rect = sourceRectAtTime(time, true);
rect.width;

// 如果只需要宽度，不要获取整个rect对象后只使用一个属性
// （实际上没办法，只能尽量少调用）
```

#### 陷阱五：表达式控制层滥用
```javascript
// 不好：每个图层都去读控制层的10个效果参数
// 10个图层 × 10个参数 = 100次属性访问

// 好：将常用的组合值存在一个属性里
// 例如用位置的 x 和 y 存两个值
```

### 9.4 优化前后对比

**优化前（性能差）：**
```javascript
// 一个位置表达式
var total = 0;
var count = 0;
for (var i = 1; i <= thisComp.numLayers; i++) {
    var layer = thisComp.layer(i);
    if (layer.name.indexOf("元素") !== -1) {
        total += layer.transform.position[0];
        count++;
    }
}
var avgX = total / count;

var totalY = 0;
var countY = 0;
for (var i = 1; i <= thisComp.numLayers; i++) {
    var layer = thisComp.layer(i);
    if (layer.name.indexOf("元素") !== -1) {
        totalY += layer.transform.position[1];
        countY++;
    }
}
var avgY = totalY / countY;

[avgX + Math.sin(time * 3) * 50, avgY + Math.cos(time * 3) * 50];
```

**问题分析：**
- 2 次遍历所有图层
- 每次遍历都检查图层名
- 重复的逻辑

**优化后（性能好）：**
```javascript
// 思路：用一个控制层预先计算好平均值
// 控制层的"平均X"滑块：一次遍历计算并存起来
// 本表达式只读取滑块值 + 简单计算

var ctrl = thisComp.layer("控制器");
var avgX = ctrl.effect("统计")("平均X").value;
var avgY = ctrl.effect("统计")("平均Y").value;

var t = time * 3;
var r = 50;
[avgX + Math.cos(t) * r, avgY + Math.sin(t) * r];
```

**性能提升：**
- 图层遍历从 2 次变为 0 次（在控制层算好）
- 本帧计算量极小
- 可复用性更强

### 9.5 什么时候用表达式 vs 关键帧

| 场景 | 推荐方式 | 原因 |
|-----|---------|------|
| 简单的固定动画 | 关键帧 | 性能最好，直观 |
| 需要实时调整参数 | 表达式+控制器 | 灵活，可预览 |
| 随机性效果 | 表达式 | 关键帧很难做随机 |
| 音乐同步 | 表达式+音频关键帧 | 自动匹配，调整方便 |
| 复杂的物理模拟 | 表达式/脚本 | 数学计算更精确 |
| 大量图层联动 | 表达式+控制层 | 批量控制效率高 |
| 最终输出前 | 关键帧（烘焙） | 渲染更快 |
| 单次微调 | 关键帧 | 简单直接 |

**经验法则：**
1. **能用关键帧就用关键帧**：关键帧性能最好
2. **需要调整就用表达式**：表达式更灵活
3. **最终渲染前烘焙**：确认不再修改后，将表达式转为关键帧（动画→关键帧辅助→将表达式转换为关键帧）
4. **控制层集中管理**：所有可调参数放在一个控制层，其他图层引用

**烘焙表达式的方法：**
1. 选中带有表达式的属性
2. 菜单：动画（Animation）→ 关键帧辅助（Keyframe Assistant）→ 将表达式转换为关键帧（Convert Expression to Keyframes）
3. 等待生成完成
4. 删除表达式（表达式会被自动禁用或删除）

---

## 十、表达式调试技巧

### 10.1 表达式错误类型

当表达式出错时，AE 会在属性名称旁显示黄色警告三角形 ⚠️，并在信息面板显示错误信息。

#### 语法错误（SyntaxError）
**原因：** 代码不符合 JavaScript 语法规范

**常见情况：**
- 括号不匹配（少了或多了）
- 缺少分号（虽然不强制，但有时会导致问题）
- 引号不闭合
- 使用了 ES6+ 语法（let/const/箭头函数等）
- 关键字拼写错误

**示例错误信息：**
```
SyntaxError: missing ) after argument list
SyntaxError: unterminated string literal
SyntaxError: Unexpected token '='
```

---

#### 引用错误（ReferenceError）
**原因：** 引用了不存在的变量、属性或函数

**常见情况：**
- 变量名拼写错误
- 图层/效果名称拼写错误
- 使用了未声明的变量
- 访问不存在的属性

**示例错误信息：**
```
ReferenceError: 'wigle' is undefined
ReferenceError: 'thisComp.layer("控制层")' has no property named 'effect("滑块")'
```

---

#### 类型错误（TypeError）
**原因：** 对错误的数据类型执行了不支持的操作

**常见情况：**
- 对字符串调用数学方法
- 对数字调用字符串方法
- 属性维度不匹配（期望二维数组，返回了一维）
- undefined 上访问属性

**示例错误信息：**
```
TypeError: null is not an object (evaluating 'layer.position')
TypeError: value.toUpperCase is not a function
```

---

#### 值错误（ValueError）
**原因：** 返回值的类型或维度与属性不匹配

**常见情况：**
- 位置属性返回了单个数字（应该是二维或三维数组）
- 颜色属性返回了 [r,g,b] 而不是 [r,g,b,a]
- 缩放属性返回了字符串

**示例错误信息：**
```
ValueError: could not convert value to a Number/Array/Color
ValueError: expected 2-dimensional array
```

---

### 10.2 常见错误及解决方法

#### 错误1：图层找不到
```javascript
// 错误代码
thisComp.layer("控制器").position;

// 错误信息：ReferenceError: 'thisComp.layer("控制器")' is undefined
```

**解决方法：**
1. 检查图层名称是否完全一致（区分大小写）
2. 检查图层是否存在于合成中
3. 图层可能被删除或重命名了
4. 使用 try/catch 容错

```javascript
// 安全写法
var layerName = "控制器";
var layer;
try {
    layer = thisComp.layer(layerName);
} catch (e) {
    // 找不到图层时返回默认值
    [0, 0];
}
layer.position;
```

---

#### 错误2：效果找不到
```javascript
// 错误代码
effect("高斯模糊")("模糊度").value;

// 错误信息：ReferenceError: ... has no property named 'effect("高斯模糊")'
```

**解决方法：**
1. 检查效果名称是否正确
2. 检查效果是否已添加到图层
3. 注意中文/英文名称（如果AE是英文版，要用英文）
4. 效果可能被删除或重命名了

---

#### 错误3：数组维度不匹配
```javascript
// 错误代码（位置属性需要二维数组）
time * 100;  // 返回单个数字，不是数组

// 错误信息：ValueError: could not convert value
```

**解决方法：**
- 位置属性返回 `[x, y]` 或 `[x, y, z]`
- 缩放属性返回 `[x, y]` 或 `[x, y, z]`
- 颜色属性返回 `[r, g, b, a]`
- 单值属性（旋转、不透明度）返回单个数字

```javascript
// 正确写法（位置属性）
[time * 100, value[1]];  // 只改变X，Y保持原值
```

---

#### 错误4：除以零
```javascript
// 错误代码
var ratio = 100 / 0;  // Infinity

// 可能导致后续计算出问题
```

**解决方法：**
```javascript
var denominator = someValue;
if (denominator == 0) {
    0;  // 或其他默认值
} else {
    100 / denominator;
}
```

---

#### 错误5：循环引用
```javascript
// 图层A的位置：
thisComp.layer("B").position;

// 图层B的位置：
thisComp.layer("A").position;

// 结果：错误或性能灾难
```

**解决方法：**
- 确保引用链是单向的，不要形成环
- 用控制层作为中心，其他图层引用控制层
- 避免 A→B→C→A 的循环引用

---

#### 错误6：使用了 ES6+ 语法
```javascript
// 错误代码（不支持 let）
let speed = 100;

// 错误代码（不支持箭头函数）
var double = x => x * 2;

// 错误代码（不支持模板字符串）
var str = `值是${value}`;
```

**解决方法：**
- 全部使用 `var` 声明变量
- 使用普通函数 `function() {}`
- 使用字符串拼接 `+`

```javascript
// 正确写法
var speed = 100;

var double = function(x) { return x * 2; };

var str = "值是" + value;
```

---

### 10.3 调试技巧

#### 技巧一：分段注释测试
当表达式很长且不知道哪里错了时，逐段注释排查：

```javascript
// 第一步：先让表达式能运行
value;  // 返回默认值，确认没有语法错误

// 第二步：逐步添加代码
var a = 10;
// var b = 20;  // 先注释掉
// var c = a + b;
a;  // 测试 a 是否正常

// 第三步：逐步取消注释，直到找到问题
```

---

#### 技巧二：用 value 兜底
在不确定的地方先用 `value` 代替，确保表达式至少能返回有效值：

```javascript
// 不确定计算对不对时，先返回 value 看是否报错
var result;
try {
    // 可能出错的复杂计算
    result = someComplexCalculation();
} catch (e) {
    result = value;  // 出错时用默认值
}
result;
```

---

#### 技巧三：简化问题
如果复杂表达式出错，先简化到最小可复现版本：

```javascript
// 原始复杂表达式
var a = thisComp.layer("A").effect("E1")("P1").value;
var b = thisComp.layer("B").effect("E2")("P2").value;
var c = Math.sin(a * b) * 100;
var d = c + value[0];
[d, value[1]];

// 简化测试1：只返回 value
// value;

// 简化测试2：只测试 a
// [a, value[1]];

// 简化测试3：测试 a + b
// [a + b, value[1]];

// 逐步添加，直到找到出错的那一行
```

---

#### 技巧四：检查数据类型
不确定变量类型时，可以通过返回值观察：

```javascript
// 返回字符串看类型
typeof someVariable;  // 返回 "number", "string", "object" 等

// 返回数组长度
// someArray.length;  // 看数组有几个元素
```

---

#### 技巧五：使用信息面板
AE 的「信息」面板（Window → Info）会显示表达式错误：

1. 打开信息面板（Ctrl+Alt+E / Cmd+Opt+E）
2. 选中出错的属性
3. 查看错误信息和行号

错误信息格式通常是：
```
错误类型: 错误描述
行: X
```

---

#### 技巧六：复制到纯文本编辑器
复杂的表达式可以复制到 VS Code 或其他编辑器中：

1. 选中表达式全部内容，复制
2. 粘贴到代码编辑器
3. 检查括号匹配、语法高亮
4. 修改后复制回去

**推荐编辑器：**
- VS Code（安装 JavaScript 语法支持）
- Sublime Text
- Notepad++

---

#### 技巧七：用滑块调试验证
不确定计算结果是否正确时，可以用滑块显示中间值：

1. 给图层添加一个滑块控制效果
2. 在滑块的表达式中输出你想查看的中间值
3. 观察滑块数值变化来验证计算是否正确

```javascript
// 在滑块表达式中输出调试值
var intermediateValue = time * 2;
intermediateValue;  // 通过滑块数值看结果
```

---

### 10.4 错误信息解读

#### 常见错误信息对照表

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `missing ) after argument list` | 括号不匹配 | 检查括号是否成对 |
| `unterminated string literal` | 字符串引号没闭合 | 检查引号 |
| `is undefined` | 引用了不存在的东西 | 检查名称拼写、是否存在 |
| `has no property named` | 访问了不存在的属性 | 检查属性路径 |
| `could not convert value` | 返回值类型不对 | 确保返回正确维度的数组 |
| `null is not an object` | 对象是 null | 检查图层/效果是否存在 |
| `Unexpected token` | 语法错误，遇到了意外的符号 | 检查语法，可能用了ES6 |
| `Out of memory` | 内存不足 | 表达式太复杂，优化或减少循环 |

---

#### 阅读错误堆栈
复杂错误可能有调用栈，从上往下看：

```
JavaScript Error:
    ReferenceError: 'something' is undefined
    Line: 15
    -> Function: myFunction
    -> Global Code
```

**解读：**
- 第 15 行出错
- 在 `myFunction` 函数中
- 错误原因：`something` 未定义

---

## 十一、脚本书写规范

### 11.1 命名规范

#### 变量命名
- 使用有意义的英文单词，避免拼音和无意义的 a/b/c
- 使用小驼峰命名法（camelCase）
- 布尔值用 is/has/can 等前缀

```javascript
// 好的命名
var compWidth = 1920;
var layerIndex = 1;
var isEnabled = true;
var hasEffect = false;
var totalFrames = 150;

// 不好的命名
var w = 1920;         // 不明确
var a = 1;             // 无意义
var yincang = true;    // 拼音
var is_not_hidden = false;  // 下划线（不用驼峰）
```

#### 函数命名
- 使用动词开头，表示动作
- 使用小驼峰命名法
- 函数名应该描述它做什么

```javascript
// 好的命名
function createSolid() { }
function getLayerByName(name) { }
function calculateDistance(p1, p2) { }
function renameAllLayers(prefix) { }

// 不好的命名
function solid() { }         // 名词，不是动作
function doStuff() { }       // 太模糊
function func1() { }         // 编号命名
```

#### 常量命名
- 全部大写，单词间用下划线分隔
- 在脚本顶部定义

```javascript
var DEFAULT_WIDTH = 1920;
var DEFAULT_HEIGHT = 1080;
var MAX_LAYERS = 100;
var FPS = 25;
```

#### 图层/合成命名
- 使用有意义的名称
- 可以加前缀表示类型

```javascript
// 好的命名
"Ctrl_Main"       // 控制器
"BG_Gradient"     // 背景
"UI_Button"       // UI元素
"Text_Title"      // 标题文字

// 不好的命名
"新建纯色层 1"    // 默认名称
"图层 2"           // 无意义编号
"aaa"              // 随意命名
```

### 11.2 注释规范

#### 文件头部注释
每个脚本文件开头都应该有文件说明注释：

```javascript
/* =========================================
   脚本名称：批量重命名工具
   版本：v1.0.0
   作者：XXX
   日期：2025-01-01
   说明：批量为选中图层添加前缀/后缀
   使用方法：选中图层后运行脚本
   ========================================= */
```

#### 函数注释
每个公共函数都应该有功能说明：

```javascript
/*
 * 创建一个纯色图层
 * @param {CompItem} comp - 目标合成
 * @param {Array} color - 颜色 [r, g, b] (0-1)
 * @param {String} name - 图层名称
 * @param {Number} width - 宽度
 * @param {Number} height - 高度
 * @return {AVLayer} 创建的纯色图层
 */
function createSolidLayer(comp, color, name, width, height) {
    return comp.layers.addSolid(color, name, width, height, 1, comp.duration);
}
```

#### 行内注释
复杂的逻辑处添加行内注释，说明为什么这么做：

```javascript
// 从下往上排列，避免索引错乱
for (var i = layers.length - 1; i >= 0; i--) {
    layers[i].moveToEnd();
}

// 使用 UndoGroup 让操作可以一步撤销
app.beginUndoGroup("批量重命名");
// ... 操作 ...
app.endUndoGroup();
```

**注意：** 注释应该说明「为什么」而不是「做什么」，代码本身已经说明了做什么。

### 11.3 错误处理

#### 检查前提条件
脚本开头检查必要的前提条件：

```javascript
// 检查是否有项目
if (!app.project) {
    alert("请先打开一个项目文件！");
    exit();
}

// 检查是否选中合成
var comp = app.project.activeItem;
if (!comp || !(comp instanceof CompItem)) {
    alert("请先选择一个合成！");
    exit();
}

// 检查是否有选中的图层
if (comp.selectedLayers.length === 0) {
    alert("请先选中至少一个图层！");
    exit();
}
```

#### try/catch 包裹
可能出错的代码用 try/catch 包裹：

```javascript
try {
    // 可能出错的操作
    var layer = comp.layer("不存在的图层");
    layer.name = "新名称";
} catch (e) {
    alert("操作失败：\n" + e.message);
}
```

#### 用户输入验证
如果脚本有用户输入（如 prompt），验证输入有效性：

```javascript
var userInput = prompt("请输入前缀：", "图层");
if (userInput === null) {
    // 用户取消了
    exit();
}
if (userInput === "") {
    alert("前缀不能为空！");
    exit();
}
```

### 11.4 代码结构

#### 使用立即执行函数
将整个脚本包裹在立即执行函数中，避免污染全局命名空间：

```javascript
(function() {
    // 所有代码写在这里
    
    // 这里的变量都是局部变量，不会影响全局
    
    function main() {
        // 主逻辑
    }
    
    main();  // 执行主函数
    
})();
```

#### 主函数结构
脚本应该有一个清晰的主入口函数：

```javascript
(function() {
    
    // 入口函数
    function main() {
        // 1. 检查前提条件
        if (!checkPrerequisites()) return;
        
        // 2. 获取用户输入
        var config = getUserInput();
        if (!config) return;
        
        // 3. 执行操作
        app.beginUndoGroup("我的脚本操作");
        try {
            performAction(config);
        } catch (e) {
            alert("出错了：\n" + e.message);
        }
        app.endUndoGroup();
        
        // 4. 完成提示
        alert("操作完成！");
    }
    
    // 检查前提条件
    function checkPrerequisites() {
        if (!app.project) {
            alert("请先打开项目");
            return false;
        }
        return true;
    }
    
    // 获取用户输入
    function getUserInput() {
        // ...
        return { prefix: "新_" };
    }
    
    // 执行操作
    function performAction(config) {
        // ...
    }
    
    // 启动
    main();
    
})();
```

#### 模块化拆分
功能复杂时，按功能拆分函数：

```javascript
// 不好：一个超长的函数
function doEverything() {
    // 100 行代码...
}

// 好：拆分成小函数
function createLayers() { }
function addEffects() { }
function setKeyframes() { }
function arrangeLayers() { }
```

### 11.5 兼容性注意事项（ES3）

#### 变量声明
```javascript
// ✅ 正确：使用 var
var name = "AE";
var count = 10;

// ❌ 错误：使用 let/const
// let name = "AE";
// const count = 10;
```

#### 函数定义
```javascript
// ✅ 正确：普通函数
function add(a, b) {
    return a + b;
}

// ✅ 正确：函数表达式
var multiply = function(a, b) {
    return a * b;
};

// ❌ 错误：箭头函数
// const add = (a, b) => a + b;
```

#### 字符串
```javascript
// ✅ 正确：字符串拼接
var name = "世界";
var greeting = "你好，" + name + "！";

// ❌ 错误：模板字符串
// var greeting = `你好，${name}！`;
```

#### 数组方法
```javascript
// ES3 不支持 forEach/map/filter/reduce
// 用 for 循环代替

// ✅ 正确：for 循环遍历
var arr = [1, 2, 3];
var sum = 0;
for (var i = 0; i < arr.length; i++) {
    sum += arr[i];
}

// ❌ 错误：forEach
// arr.forEach(function(item) { sum += item; });
```

#### 对象方法
```javascript
// ES3 不支持 Object.keys/values/assign
// 用 for...in 代替

// ✅ 正确：for...in 遍历
var obj = {a: 1, b: 2};
for (var key in obj) {
    if (obj.hasOwnProperty(key)) {
        var val = obj[key];
    }
}

// ❌ 错误：Object.keys
// Object.keys(obj);
```

#### 数组创建
```javascript
// ✅ 推荐：字面量方式
var arr = [1, 2, 3];

// 也可以：构造函数方式
var arr2 = new Array(1, 2, 3);
```

#### 默认参数
```javascript
// ES3 不支持默认参数语法

// ✅ 正确：手动判断
function greet(name) {
    name = name || "陌生人";  // 注意：假值都会触发默认值
    return "你好，" + name;
}

// 更严谨的写法
function greet(name) {
    if (name === undefined) {
        name = "陌生人";
    }
    return "你好，" + name;
}

// ❌ 错误：默认参数语法
// function greet(name = "陌生人") { }
```

#### 严格模式
```javascript
// ES3 不支持 "use strict"
// 不要在脚本开头加 "use strict";
```

### 11.6 其他最佳实践

#### 使用 UndoGroup
所有修改操作都应该包在 UndoGroup 中，让用户可以一步撤销：

```javascript
app.beginUndoGroup("批量创建图层");

// 执行多个操作
// ...

app.endUndoGroup();
```

#### 保存用户选择
操作前保存用户的选择，操作后恢复：

```javascript
// 保存当前选择
var selectedLayers = comp.selectedLayers;

// 执行操作...

// 恢复选择（如果需要）
for (var i = 0; i < selectedLayers.length; i++) {
    selectedLayers[i].selected = true;
}
```

#### 性能优化
- 避免在循环中重复获取属性
- 缓存经常访问的对象引用

```javascript
// 不好：每次循环都访问 comp.layer(i).transform.position
for (var i = 1; i <= comp.numLayers; i++) {
    var x = comp.layer(i).transform.position[0];
    var y = comp.layer(i).transform.position[1];
}

// 好：缓存引用
for (var i = 1; i <= comp.numLayers; i++) {
    var layer = comp.layer(i);
    var pos = layer.transform.position;
    var x = pos[0];
    var y = pos[1];
}
```

#### 测试建议
1. 在空项目中测试
2. 在复杂项目中测试
3. 测试边界情况（0个图层、很多图层）
4. 测试撤销功能
5. 测试不同版本 AE 的兼容性

---

> **文档版本：** v1.0  
> **适用版本：** After Effects 2026  
> **最后更新：** 2025年

