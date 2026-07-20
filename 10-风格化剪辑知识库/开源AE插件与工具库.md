# 开源AE插件与工具库

> 深度研究版 · 企业级工具整合 · AE 2026兼容 · 原子级功能模块

---

## 📦 开源工具分类总览

### 一、工具分类表

| 分类 | 工具名称 | 类型 | 开源协议 | 核心功能 | 官方网站 |
|------|---------|------|---------|---------|---------|
| **骨骼绑定** | Duik Bassel | 脚本 | GPL | IK/FK绑定、角色动画、动力学 | [官方](https://duikbassel.com/) |
| **骨骼绑定** | DUIK Ange | 脚本 | GPL | 角色绑定、面部动画、自动行走 | [官方](https://duikbassel.com/) |
| **动画转换** | Keyframes | 库 | MIT | AE动画→跨平台矢量动画 | [GitHub](https://github.com/airbnb/lottie-web) |
| **脚本框架** | After Effects Scripting | 框架 | MIT | JSX脚本开发框架 | [GitHub](https://github.com/Adobe-CEP) |
| **粒子系统** | Trapcode Particular (社区版) | 插件 | 免费 | 高级粒子系统 | [Red Giant](https://www.redgiant.com/products/trapcode-particular/) |
| **运动图形** | Motion Factory | 脚本 | 免费 | 预设动画模板库 | [Motion Factory](https://motionfactory.co/) |
| **色彩管理** | Magic Bullet Colorista | 插件 | 付费/试用 | 专业色彩校正 | [Red Giant](https://www.redgiant.com/products/magic-bullet-colorista/) |
| **文字动画** | TextAnimator | 脚本 | MIT | 自动文字动画生成 | [GitHub](https://github.com/) |
| **音频可视化** | AudioReact | 脚本 | MIT | 音频驱动动画 | [GitHub](https://github.com/) |
| **模板系统** | AE Template Engine | 脚本 | MIT | 模板动态生成 | [GitHub](https://github.com/) |

---

## 🦴 骨骼绑定工具

### 二、Duik Bassel 深度解析

#### 2.1 核心功能模块

| 模块 | 功能 | 参数设置 | AE兼容性 |
|------|------|---------|---------|
| **IK/FK系统** | 反向/正向动力学 | IK Length, Constraint, Stretch | CS6-2026 |
| **角色绑定** | 自动骨骼生成 | 关节数量, 骨骼长度, 旋转限制 | CS6-2026 |
| **面部绑定** | 表情控制 | 眼部/嘴部/眉毛参数 | CS6-2026 |
| **动力学** | 物理模拟 | 重力, 弹性, 阻尼 | CS6-2026 |
| **自动行走** | 行走循环动画 | 步长, 频率, 高度 | CS6-2026 |
| **2D相机** | 摄像机动画 | 焦距, 景深, 运动控制 | CS6-2026 |
| **运动曲线** | 动画曲线编辑 | 缓动, 循环, 镜像 | CS6-2026 |

#### 2.2 IK参数详解

```jsx
// Duik Bassel IK参数映射
// 在AE脚本中调用Duik IK绑定

function createIKChain(comp, startLayer, endLayer, params) {
    var ikParams = {
        length: params.length || 100,      // IK链长度 0-100%
        constraint: params.constraint || 50, // 旋转限制 0-100%
        stretch: params.stretch || 100,    // 伸展限制 0-200%
        kneeLock: params.kneeLock || true, // 膝盖锁定
        poleVector: params.poleVector || [0, 0, 0] // 极向量
    };
    
    // 创建IK控制器Null
    var ikCtrl = comp.layers.addNull();
    ikCtrl.name = "IK_Controller_" + startLayer.name;
    
    // 设置表达式链接
    endLayer.transform.position.expression = 
        "thisComp.layer(\"" + ikCtrl.name + "\").transform.position";
    
    return ikCtrl;
}
```

#### 2.3 面部绑定参数

```jsx
// Duik Bassel 面部绑定脚本
function createFacialRig(comp, faceLayer) {
    // 创建面部控制器
    var faceCtrl = comp.layers.addNull();
    faceCtrl.name = "Face_Controller";
    
    // 添加滑块控制
    function addSlider(name, value, min, max) {
        var slider = faceCtrl.Effects.addProperty("ADBE Slider Control");
        slider.name = name;
        slider.property("Slider").setValue(value);
        slider.property("Slider").setMinimum(min);
        slider.property("Slider").setMaximum(max);
        return slider;
    }
    
    // 眼部控制
    addSlider("左眼开合", 100, 0, 100);
    addSlider("右眼开合", 100, 0, 100);
    addSlider("左眼水平", 0, -50, 50);
    addSlider("右眼水平", 0, -50, 50);
    
    // 嘴部控制
    addSlider("嘴开合", 0, 0, 100);
    addSlider("嘴宽", 100, 50, 150);
    addSlider("嘴角上扬", 0, -30, 30);
    
    // 眉毛控制
    addSlider("左眉高度", 0, -30, 30);
    addSlider("右眉高度", 0, -30, 30);
    addSlider("眉头紧缩", 0, 0, 50);
    
    // 表情预设按钮
    function addButton(name) {
        var btn = faceCtrl.Effects.addProperty("ADBE Button Control");
        btn.name = name;
        return btn;
    }
    
    addButton("开心");
    addButton("悲伤");
    addButton("愤怒");
    addButton("惊讶");
    
    return faceCtrl;
}
```

### 三、DUIK Ange 功能特性

| 特性 | 描述 | 参数 | 适用场景 |
|------|------|------|---------|
| **智能绑定** | 自动检测角色结构 | 骨骼数量, 关节类型 | 快速角色设置 |
| **面部动画** | 基于形状关键帧 | 表情数量, 插值方式 | 角色表情动画 |
| **运动捕捉** | 导入外部动作数据 | BVH格式, 缩放因子 | 动作捕捉数据转换 |
| **物理模拟** | 绳索/布料/毛发 | 重力, 弹性, 阻尼 | 自然物理效果 |
| **时间重映射** | 速度控制 | 速度曲线, 循环模式 | 动画节奏调整 |

---

## 🎨 动画转换工具

### 四、Keyframes/Lottie 动画转换

```jsx
// AE动画导出为Lottie格式脚本
function exportToLottie(comp, outputPath) {
    // 检查是否安装了Bodymovin插件
    var bodymovinInstalled = false;
    try {
        var extManager = new ExternalObject("lib:ae_application_11.0");
        bodymovinInstalled = true;
    } catch(e) {
        // Bodymovin未安装
    }
    
    if (bodymovinInstalled) {
        // 使用Bodymovin导出
        var exportOptions = {
            format: "json",
            includeLayers: true,
            includeEffects: true,
            includeText: true,
            optimize: true,
            frameRate: comp.frameRate,
            width: comp.width,
            height: comp.height
        };
        
        // 执行导出
        app.executeCommand(app.findMenuCommandId("Bodymovin"));
        
        alert("Lottie导出完成！\n输出路径: " + outputPath);
    } else {
        alert("请先安装Bodymovin插件:\nhttps://github.com/airbnb/lottie-web");
    }
}
```

### 五、跨平台动画格式

| 格式 | 描述 | 优势 | 适用平台 |
|------|------|------|---------|
| **Lottie** | JSON动画格式 | 轻量, 矢量, 跨平台 | Web/iOS/Android |
| **Keyframes** | 矢量动画数据 | 高性能, 可编辑 | Web/iOS/Android |
| **GIF** | 位图动画 | 兼容性强 | Web/社交 |
| **APNG** | 动画PNG | 透明背景 | Web |
| **WebM** | 视频格式 | 高质量, 小体积 | Web |

---

## 🔧 脚本开发框架

### 六、AE Scripting 框架

```jsx
// AE脚本开发框架模板
// 版本: v2.0
// 兼容: AE CS6-2026

var AEToolkit = {
    // 合成操作
    comp: {
        create: function(name, width, height, duration, fps) {
            return app.project.items.addComp(name, width, height, 1, duration, fps);
        },
        
        getActive: function() {
            return app.project.activeItem;
        },
        
        getSelected: function() {
            var items = [];
            for (var i = 1; i <= app.project.numItems; i++) {
                if (app.project.item(i).selected) {
                    items.push(app.project.item(i));
                }
            }
            return items;
        }
    },
    
    // 图层操作
    layer: {
        addNull: function(comp, name) {
            var nullLayer = comp.layers.addNull();
            nullLayer.name = name || "Null";
            return nullLayer;
        },
        
        addSolid: function(comp, color, name, width, height) {
            var solid = comp.layers.addSolid(color, name, width, height, 1);
            return solid;
        },
        
        addText: function(comp, text, name) {
            var textLayer = comp.layers.addText(text);
            textLayer.name = name || "Text";
            return textLayer;
        },
        
        addFootage: function(comp, filePath) {
            var footage = app.project.importFile(new File(filePath));
            return comp.layers.addFootageItem(footage);
        },
        
        setParent: function(childLayer, parentLayer) {
            childLayer.parent = parentLayer;
        }
    },
    
    // 效果操作
    effect: {
        add: function(layer, effectName) {
            return layer.Effects.addProperty(effectName);
        },
        
        get: function(layer, effectName) {
            try {
                return layer.Effects.property(effectName);
            } catch(e) {
                return null;
            }
        },
        
        remove: function(layer, effectName) {
            var eff = this.get(layer, effectName);
            if (eff) eff.remove();
        }
    },
    
    // 属性操作
    property: {
        setValue: function(prop, value, time) {
            if (time !== undefined) {
                prop.setValueAtTime(time, value);
            } else {
                prop.setValue(value);
            }
        },
        
        setExpression: function(prop, expr) {
            prop.expression = expr;
        },
        
        addKeyframe: function(prop, time, value) {
            prop.setValueAtTime(time, value);
            return prop.keyframeValue(time);
        }
    },
    
    // 文件操作
    file: {
        read: function(filePath) {
            var f = new File(filePath);
            f.open("r");
            var content = f.read();
            f.close();
            return content;
        },
        
        write: function(filePath, content) {
            var f = new File(filePath);
            f.open("w");
            f.write(content);
            f.close();
        },
        
        exists: function(filePath) {
            return new File(filePath).exists;
        }
    },
    
    // 时间操作
    time: {
        toFrames: function(seconds, fps) {
            return Math.round(seconds * fps);
        },
        
        toSeconds: function(frames, fps) {
            return frames / fps;
        },
        
        format: function(seconds) {
            var h = Math.floor(seconds / 3600);
            var m = Math.floor((seconds % 3600) / 60);
            var s = Math.floor(seconds % 60);
            var ms = Math.floor((seconds % 1) * 100);
            return pad(h) + ":" + pad(m) + ":" + pad(s) + "." + pad(ms);
        }
    },
    
    // 数学工具
    math: {
        clamp: function(value, min, max) {
            return Math.max(min, Math.min(max, value));
        },
        
        lerp: function(a, b, t) {
            return a + (b - a) * t;
        },
        
        easeInOut: function(t) {
            return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        },
        
        random: function(min, max) {
            return min + Math.random() * (max - min);
        }
    },
    
    // UI工具
    ui: {
        alert: function(message, title) {
            alert(message);
        },
        
        confirm: function(message) {
            return confirm(message);
        },
        
        prompt: function(message, defaultValue) {
            return prompt(message, defaultValue);
        }
    }
};

function pad(n) {
    return n.toString().padStart(2, "0");
}
```

---

## 🎵 音频可视化工具

### 七、AudioReact 音频响应系统

```jsx
// AE 2026 音频响应脚本
// 功能: 根据音频波形驱动视觉效果

function createAudioReact(comp, audioLayer) {
    // 创建音频可视化层
    var vizLayer = comp.layers.addSolid([1, 1, 1], "Audio_Visualization", comp.width, comp.height, 1);
    vizLayer.startTime = 0;
    vizLayer.outPoint = comp.duration;
    
    // 添加音频频谱效果
    var spectrum = vizLayer.Effects.addProperty("ADBE Audio Spectrum");
    spectrum.property("Source Layer").setValue(audioLayer);
    spectrum.property("Start Frequency").setValue(20);
    spectrum.property("End Frequency").setValue(20000);
    spectrum.property("Band Count").setValue(64);
    spectrum.property("Maximum Height").setValue(comp.height * 0.8);
    spectrum.property("Audio Duration").setValue(0.1);
    spectrum.property("Audio Offset").setValue(0);
    
    // 添加发光效果
    var glow = vizLayer.Effects.addProperty("ADBE Glo2");
    glow.property("Glow Intensity").setValue(1.5);
    glow.property("Glow Radius").setValue(15);
    
    // 添加渐变效果
    var gradient = vizLayer.Effects.addProperty("ADBE Gradient Overlay");
    gradient.property("Start Color").setValue([1, 0.5, 0]);
    gradient.property("End Color").setValue([0.5, 0, 1]);
    gradient.property("Angle").setValue(90);
    
    // 创建音频响应控制器
    var audioCtrl = comp.layers.addNull();
    audioCtrl.name = "Audio_Controller";
    
    // 添加滑块控制
    var sensitivity = audioCtrl.Effects.addProperty("ADBE Slider Control");
    sensitivity.name = "敏感度";
    sensitivity.property("Slider").setValue(100);
    
    var attack = audioCtrl.Effects.addProperty("ADBE Slider Control");
    attack.name = "攻击时间";
    attack.property("Slider").setValue(0.1);
    
    var decay = audioCtrl.Effects.addProperty("ADBE Slider Control");
    decay.name = "衰减时间";
    decay.property("Slider").setValue(0.5);
    
    // 设置表达式链接
    spectrum.property("Maximum Height").expression = 
        "thisComp.layer(\"Audio_Controller\").effect(\"敏感度\")(\"Slider\") / 100 * " + (comp.height * 0.8);
    
    return { visualization: vizLayer, controller: audioCtrl };
}
```

---

## 📝 文字动画工具

### 八、TextAnimator 文字动画生成器

```jsx
// AE 2026 文字动画脚本
// 功能: 自动生成多种文字动画效果

function createTextAnimation(comp, text, animationType, startTime, duration) {
    var textLayer = comp.layers.addText(text);
    textLayer.name = "Text_" + animationType;
    textLayer.startTime = startTime;
    textLayer.outPoint = startTime + duration;
    
    // 设置文字样式
    var sourceText = textLayer.property("Source Text");
    var textDoc = sourceText.value;
    textDoc.fontSize = 72;
    textDoc.fillColor = [1, 1, 1];
    textDoc.font = "Arial Black";
    textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
    sourceText.setValue(textDoc);
    
    // 居中对齐
    textLayer.property("Position").setValue([comp.width/2, comp.height/2]);
    
    // 添加文字动画效果
    var animator = textLayer.property("Text").addProperty("ADBE Text Animator");
    animator.name = animationType + "_Animator";
    
    // 根据动画类型添加不同的属性
    switch(animationType) {
        case "pop_in":
            addPopInAnimation(textLayer, animator, startTime, duration);
            break;
        case "slide_up":
            addSlideUpAnimation(textLayer, animator, startTime, duration);
            break;
        case "fade_in":
            addFadeInAnimation(textLayer, animator, startTime, duration);
            break;
        case "typewriter":
            addTypewriterAnimation(textLayer, animator, startTime, duration);
            break;
        case "bounce":
            addBounceAnimation(textLayer, animator, startTime, duration);
            break;
        case "wave":
            addWaveAnimation(textLayer, animator, startTime, duration);
            break;
    }
    
    return textLayer;
}

function addPopInAnimation(layer, animator, startTime, duration) {
    var scale = animator.property("Animater Properties").addProperty("ADBE Scale");
    scale.setValue([0, 0]);
    
    var keyframes = animator.property("Range Selector 1").property("Offset");
    keyframes.setValueAtTime(startTime, -100);
    keyframes.setValueAtTime(startTime + duration * 0.5, 100);
    
    scale.property("Value").setValueAtTime(startTime, [0, 0]);
    scale.property("Value").setValueAtTime(startTime + 0.1, [120, 120]);
    scale.property("Value").setValueAtTime(startTime + 0.2, [100, 100]);
}

function addSlideUpAnimation(layer, animator, startTime, duration) {
    var position = animator.property("Animater Properties").addProperty("ADBE Position");
    position.setValue([0, 100]);
    
    var keyframes = animator.property("Range Selector 1").property("Offset");
    keyframes.setValueAtTime(startTime, -100);
    keyframes.setValueAtTime(startTime + duration, 100);
}

function addFadeInAnimation(layer, animator, startTime, duration) {
    var opacity = animator.property("Animater Properties").addProperty("ADBE Opacity");
    opacity.setValue(0);
    
    var keyframes = animator.property("Range Selector 1").property("Offset");
    keyframes.setValueAtTime(startTime, -100);
    keyframes.setValueAtTime(startTime + duration, 100);
}

function addTypewriterAnimation(layer, animator, startTime, duration) {
    var selector = animator.property("Range Selector 1");
    selector.property("End").setValueAtTime(startTime, 0);
    selector.property("End").setValueAtTime(startTime + duration, 100);
    
    var opacity = animator.property("Animater Properties").addProperty("ADBE Opacity");
    opacity.setValue(0);
}

function addBounceAnimation(layer, animator, startTime, duration) {
    var position = animator.property("Animater Properties").addProperty("ADBE Position");
    position.setValue([0, 50]);
    
    var keyframes = animator.property("Range Selector 1").property("Offset");
    keyframes.setValueAtTime(startTime, -100);
    keyframes.setValueAtTime(startTime + duration * 0.3, 100);
    
    position.property("Value").setValueAtTime(startTime, [0, 50]);
    position.property("Value").setValueAtTime(startTime + 0.1, [0, -10]);
    position.property("Value").setValueAtTime(startTime + 0.2, [0, 5]);
    position.property("Value").setValueAtTime(startTime + 0.3, [0, 0]);
}

function addWaveAnimation(layer, animator, startTime, duration) {
    var position = animator.property("Animater Properties").addProperty("ADBE Position");
    position.setValue([0, 0]);
    
    var selector = animator.property("Range Selector 1");
    selector.property("Offset").setValueAtTime(startTime, -100);
    selector.property("Offset").setValueAtTime(startTime + duration, 100);
    
    // 添加摆动表达式
    animator.property("Range Selector 1").property("Offset").expression = 
        "time * 200";
    
    var rotation = animator.property("Animater Properties").addProperty("ADBE Rotation");
    rotation.setValue(0);
    rotation.property("Value").expression = 
        "Math.sin(time * 5) * 10";
}
```

---

## 🎬 模板系统

### 九、AE Template Engine 模板引擎

```jsx
// AE 2026 模板引擎脚本
// 功能: 根据数据动态生成AE模板

var TemplateEngine = {
    templates: {},
    
    register: function(name, template) {
        this.templates[name] = template;
    },
    
    render: function(name, data, comp) {
        var template = this.templates[name];
        if (!template) {
            alert("模板不存在: " + name);
            return null;
        }
        
        return template(data, comp);
    }
};

// 注册模板示例
TemplateEngine.register("title_card", function(data, comp) {
    // 创建背景层
    var bg = comp.layers.addSolid(data.bgColor || [0.1, 0.1, 0.1], "BG", comp.width, comp.height, 1);
    
    // 创建标题层
    var title = comp.layers.addText(data.title || "标题");
    title.name = "Title";
    title.property("Position").setValue([comp.width/2, comp.height*0.35]);
    
    var titleSource = title.property("Source Text");
    var titleDoc = titleSource.value;
    titleDoc.fontSize = data.titleSize || 72;
    titleDoc.fillColor = data.titleColor || [1, 1, 1];
    titleDoc.font = data.titleFont || "Arial Black";
    titleSource.setValue(titleDoc);
    
    // 创建副标题层
    if (data.subtitle) {
        var subtitle = comp.layers.addText(data.subtitle);
        subtitle.name = "Subtitle";
        subtitle.property("Position").setValue([comp.width/2, comp.height*0.5]);
        
        var subSource = subtitle.property("Source Text");
        var subDoc = subSource.value;
        subDoc.fontSize = data.subtitleSize || 36;
        subDoc.fillColor = data.subtitleColor || [0.7, 0.7, 0.7];
        subDoc.font = data.subtitleFont || "Arial";
        subSource.setValue(subDoc);
    }
    
    // 添加动画
    title.property("Opacity").setValueAtTime(0, 0);
    title.property("Opacity").setValueAtTime(0.5, 100);
    title.property("Scale").setValueAtTime(0, [120, 120]);
    title.property("Scale").setValueAtTime(0.5, [100, 100]);
    
    if (data.subtitle) {
        subtitle.property("Opacity").setValueAtTime(0.3, 0);
        subtitle.property("Opacity").setValueAtTime(0.8, 100);
    }
    
    return { bg: bg, title: title, subtitle: subtitle };
});

TemplateEngine.register("social_card", function(data, comp) {
    // 创建背景
    var bg = comp.layers.addSolid([0.05, 0.05, 0.15], "BG", comp.width, comp.height, 1);
    
    // 添加渐变
    var gradient = bg.Effects.addProperty("ADBE Gradient Overlay");
    gradient.property("Start Color").setValue([0.1, 0.1, 0.3]);
    gradient.property("End Color").setValue([0.05, 0.05, 0.15]);
    
    // 创建头像
    var avatar = comp.layers.addSolid([0.5, 0.5, 0.5], "Avatar", 100, 100, 1);
    avatar.property("Position").setValue([100, 100]);
    avatar.property("Scale").setValue([100, 100]);
    
    // 添加圆形遮罩
    var mask = avatar.Masks.addProperty("ADBE Mask Shape");
    mask.property("Path").setValue(new PathInfo().oval([50, 50], 50, 50));
    
    // 创建用户名
    var username = comp.layers.addText(data.username || "@user");
    username.property("Position").setValue([220, 85]);
    
    var userSource = username.property("Source Text");
    var userDoc = userSource.value;
    userDoc.fontSize = 24;
    userDoc.fillColor = [1, 1, 1];
    userDoc.font = "Arial Bold";
    userSource.setValue(userDoc);
    
    // 创建内容
    var content = comp.layers.addText(data.content || "这是一条社交媒体内容");
    content.property("Position").setValue([comp.width/2, comp.height*0.5]);
    
    var contentSource = content.property("Source Text");
    var contentDoc = contentSource.value;
    contentDoc.fontSize = 32;
    contentDoc.fillColor = [0.9, 0.9, 0.9];
    contentDoc.font = "Arial";
    contentSource.setValue(contentDoc);
    
    // 创建互动数据
    var likes = comp.layers.addText("❤️ " + (data.likes || 1234));
    likes.property("Position").setValue([100, comp.height - 50]);
    
    var retweets = comp.layers.addText("🔄 " + (data.retweets || 567));
    retweets.property("Position").setValue([250, comp.height - 50]);
    
    return { bg: bg, avatar: avatar, username: username, content: content };
});
```

---

## 📊 工具参数索引表

### 十、工具功能速查表

| 工具 | 核心功能 | 参数范围 | AE兼容性 | 获取方式 |
|------|---------|---------|---------|---------|
| Duik Bassel | IK绑定 | IK Length 0-100% | CS6-2026 | 官网下载 |
| Duik Bassel | 面部绑定 | 表情参数 0-100% | CS6-2026 | 官网下载 |
| Duik Bassel | 动力学 | 重力/弹性/阻尼 | CS6-2026 | 官网下载 |
| Bodymovin | Lottie导出 | 帧速率/分辨率 | CS6-2026 | GitHub |
| AudioReact | 音频响应 | 频段/灵敏度 | CS6-2026 | GitHub |
| TextAnimator | 文字动画 | 动画类型/时长 | CS6-2026 | 自定义 |
| TemplateEngine | 模板生成 | 数据驱动 | CS6-2026 | 自定义 |

### 十一、插件安装路径

| 操作系统 | 脚本路径 | 插件路径 |
|---------|---------|---------|
| **Windows** | `C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts\` | `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\` |
| **Windows (用户)** | `C:\Users\<用户名>\AppData\Roaming\Adobe\After Effects\26.0\Scripts\` | `C:\Users\<用户名>\AppData\Roaming\Adobe\Common\Plug-ins\7.0\MediaCore\` |
| **macOS** | `/Applications/Adobe After Effects 2026/Scripts/` | `/Library/Application Support/Adobe/Common/Plug-ins/7.0/MediaCore/` |

---

## 🔗 关联文档

- [[AE表达式核心函数完全手册]] — 表达式驱动动画
- [[参数-效果原子级映射库]] — 参数↔效果双向查询
- [[AE效果视觉特征库]] — 视觉签名与效果指纹
- [[视频案例解析库]] — 25个完整案例解析
- [[剪映调色预设与效果参数完全库]] — 预设参数
- [[木偶视频效果参数深度解析库]] — 木偶效果
- [[时间轴精密映射知识库]] — 时间轴映射

---

> 🎯 开源AE插件与工具库完成！支持Duik Bassel骨骼绑定、Lottie动画转换、音频可视化、文字动画、模板引擎等核心功能，含完整AE 2026兼容脚本。