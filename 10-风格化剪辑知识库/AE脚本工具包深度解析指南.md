# AE脚本工具包深度解析（Motion Tools Pro/BeatEdit/MG动画）

---

## 一、脚本工具包概述

### 1.1 工具包清单

| 脚本名称 | 版本 | 类型 | 核心功能 |
|---------|------|------|---------|
| **Motion Tools Pro** | 2.1.1 | 综合工具 | 运动控制、关键帧管理、表达式工具 |
| **BeatEdit** | V2.2.005 | AE版 | 音乐节拍检测、自动卡点、节奏动画 |
| **BeatEdit** | V2.2.006 | PR版 | 音乐节拍检测、自动剪辑、节奏剪辑 |
| **MG动画基本图形工具包** | v30.5.1 | 基础图形 | 形状工具、图形预设、基础动画 |
| **MG动画关键帧多功能高级工具** | - | 高级动画 | 关键帧动画、缓动控制、时间曲线 |

### 1.2 脚本架构

```
AE Script Toolkit
├── Motion Tools Pro 2.1.1
│   ├── Motion Controls
│   ├── Keyframe Management
│   ├── Expression Builder
│   └── Preset Manager
├── BeatEdit V2.2.005
│   ├── Audio Analysis
│   ├── Beat Detection
│   ├── Auto Keyframing
│   └── Rhythm Animation
├── MG Animation Tools
│   ├── Basic Shape Kit
│   ├── Advanced Keyframe Kit
│   └── Animation Presets
└── Integration Layer
    ├── Script Bridge
    ├── Data Exchange
    └── Workflow Automation
```

---

## 二、Motion Tools Pro 2.1.1 深度解析

### 2.1 核心模块架构

```javascript
var MotionToolsPro = {
    version: "2.1.1",
    
    modules: {
        motionControls: null,
        keyframeManager: null,
        expressionBuilder: null,
        presetManager: null
    },
    
    init: function() {
        this.modules.motionControls = new MotionControls();
        this.modules.keyframeManager = new KeyframeManager();
        this.modules.expressionBuilder = new ExpressionBuilder();
        this.modules.presetManager = new PresetManager();
        
        return true;
    },
    
    getModule: function(moduleName) {
        return this.modules[moduleName];
    }
};
```

### 2.2 运动控制模块

```javascript
var MotionControls = {
    applyEasing: function(prop, easingType, options) {
        var defaults = {
            duration: 1,
            delay: 0,
            amplitude: 1,
            period: 0.3
        };
        
        var opts = Object.assign({}, defaults, options);
        
        switch (easingType) {
            case "easeIn":
                prop.setExpression(
                    "var t = time - " + opts.delay + "; " +
                    "t < 0 ? value : easeIn(t, value, 1, " + opts.duration + ")"
                );
                break;
            
            case "easeOut":
                prop.setExpression(
                    "var t = time - " + opts.delay + "; " +
                    "t < 0 ? value : easeOut(t, value, 1, " + opts.duration + ")"
                );
                break;
            
            case "easeInOut":
                prop.setExpression(
                    "var t = time - " + opts.delay + "; " +
                    "t < 0 ? value : easeInOut(t, value, 1, " + opts.duration + ")"
                );
                break;
            
            case "bounce":
                prop.setExpression(
                    "var t = time - " + opts.delay + "; " +
                    "t < 0 ? value : bounce(t, value, 1, " + opts.duration + ", " + 
                    opts.amplitude + ", " + opts.period + ")"
                );
                break;
            
            case "elastic":
                prop.setExpression(
                    "var t = time - " + opts.delay + "; " +
                    "t < 0 ? value : elastic(t, value, 1, " + opts.duration + ", " + 
                    opts.amplitude + ", " + opts.period + ")"
                );
                break;
            
            case "back":
                prop.setExpression(
                    "var t = time - " + opts.delay + "; " +
                    "t < 0 ? value : backEaseOut(t, value, 1, " + opts.duration + ")"
                );
                break;
        }
    },
    
    applyOscillation: function(prop, options) {
        var defaults = {
            frequency: 1,
            amplitude: 10,
            phase: 0,
            decay: 0
        };
        
        var opts = Object.assign({}, defaults, options);
        
        prop.setExpression(
            "value + Math.sin(time * " + opts.frequency + " * 2 * Math.PI + " + opts.phase + ") * " +
            opts.amplitude + " * Math.exp(-time * " + opts.decay + ")"
        );
    },
    
    applyRandomMotion: function(prop, options) {
        var defaults = {
            min: -10,
            max: 10,
            seed: 1,
            smooth: 0.1
        };
        
        var opts = Object.assign({}, defaults, options);
        
        prop.setExpression(
            "seedRandom(" + opts.seed + ", true); " +
            "var r = random(" + opts.min + ", " + opts.max + "); " +
            "value + easeOut(time, 0, r, " + opts.smooth + ")"
        );
    },
    
    applyFollowPath: function(prop, pathLayer, options) {
        var defaults = {
            timeOffset: 0,
            loop: false,
            ease: false
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var loopExpr = opts.loop ? " % 1" : "";
        
        prop.setExpression(
            "var p = thisComp.layer('" + pathLayer.name + "').content(" + 
            pathLayer.propertyIndex + ").path; " +
            "p.pointOnPath(time * p.points().length / thisComp.duration + " + 
            opts.timeOffset + ")" + loopExpr
        );
    },
    
    applyLookAt: function(layer, targetLayer, options) {
        var defaults = {
            axis: "Z",
            offset: 0
        };
        
        var opts = Object.assign({}, defaults, options);
        
        layer.rotation.setExpression(
            "var target = thisComp.layer('" + targetLayer.name + "').position; " +
            "var dir = normalize(target - position); " +
            "lookAt(position, position + dir)"
        );
    },
    
    applyParentConstraint: function(layer, parentLayer, options) {
        var defaults = {
            influence: 100,
            offset: [0, 0, 0]
        };
        
        var opts = Object.assign({}, defaults, options);
        
        layer.position.setExpression(
            "(thisComp.layer('" + parentLayer.name + "').position + " + 
            JSON.stringify(opts.offset) + ") * " + (opts.influence / 100) + " + " +
            "value * " + ((100 - opts.influence) / 100)
        );
    },
    
    applyDelay: function(layer, delayFrames) {
        layer.inPoint += delayFrames / thisComp.frameRate;
    },
    
    applyStagger: function(layers, startDelay, delayIncrement) {
        for (var i = 0; i < layers.length; i++) {
            this.applyDelay(layers[i], startDelay + i * delayIncrement);
        }
    },
    
    applyMotionBlur: function(layer, shutterAngle) {
        layer.motionBlur = true;
        if (shutterAngle) {
            layer.shutterAngle = shutterAngle;
        }
    },
    
    applyTimeRemapping: function(layer, speed) {
        layer.timeRemapEnabled = true;
        layer.timeRemap.setExpression("time * " + speed);
    }
};
```

### 2.3 关键帧管理模块

```javascript
var KeyframeManager = {
    selectKeyframes: function(prop, startFrame, endFrame) {
        var keyframes = prop.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            var key = keyframes[i];
            var time = key.time;
            
            if (time >= startFrame && time <= endFrame) {
                key.selected = true;
            }
        }
    },
    
    deleteKeyframes: function(prop, startFrame, endFrame) {
        var keyframes = prop.keyframes();
        
        for (var i = keyframes.length - 1; i >= 0; i--) {
            var key = keyframes[i];
            var time = key.time;
            
            if (time >= startFrame && time <= endFrame) {
                key.remove();
            }
        }
    },
    
    copyKeyframes: function(sourceProp, destProp, timeOffset) {
        var keyframes = sourceProp.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            var key = keyframes[i];
            destProp.setValueAtTime(key.time + timeOffset, key.value);
        }
    },
    
    pasteKeyframes: function(sourceProp, destProp) {
        this.copyKeyframes(sourceProp, destProp, 0);
    },
    
    offsetKeyframes: function(prop, offsetFrames) {
        var keyframes = prop.keyframes();
        var offsetTime = offsetFrames / prop.propertyGroup(3).frameRate;
        
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].time += offsetTime;
        }
    },
    
    scaleKeyframes: function(prop, scaleFactor) {
        var keyframes = prop.keyframes();
        
        if (keyframes.length < 2) return;
        
        var firstTime = keyframes[0].time;
        var lastTime = keyframes[keyframes.length - 1].time;
        
        for (var i = 0; i < keyframes.length; i++) {
            var relTime = keyframes[i].time - firstTime;
            keyframes[i].time = firstTime + relTime * scaleFactor;
        }
    },
    
    reverseKeyframes: function(prop) {
        var keyframes = prop.keyframes();
        var values = [];
        
        for (var i = 0; i < keyframes.length; i++) {
            values.push(keyframes[i].value);
        }
        
        values.reverse();
        
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].setValue(values[i]);
        }
    },
    
    easeAllKeyframes: function(prop, easingType) {
        var keyframes = prop.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].setInterpolationType(KeyframeInterpolationType.HOLD);
        }
        
        switch (easingType) {
            case "auto":
                for (var i = 1; i < keyframes.length - 1; i++) {
                    keyframes[i].setInterpolationType(KeyframeInterpolationType.AUTO);
                }
                break;
            
            case "linear":
                for (var i = 0; i < keyframes.length; i++) {
                    keyframes[i].setInterpolationType(KeyframeInterpolationType.LINEAR);
                }
                break;
            
            case "bezier":
                for (var i = 0; i < keyframes.length; i++) {
                    keyframes[i].setInterpolationType(KeyframeInterpolationType.BEZIER);
                }
                break;
        }
    },
    
    addKeyframe: function(prop, time, value, options) {
        var defaults = {
            easeIn: true,
            easeOut: true
        };
        
        var opts = Object.assign({}, defaults, options);
        
        prop.setValueAtTime(time, value);
        
        var key = prop.keyframeAtTime(time);
        if (opts.easeIn) key.setEaseIn();
        if (opts.easeOut) key.setEaseOut();
        
        return key;
    },
    
    getKeyframeCount: function(prop) {
        return prop.keyframes().length;
    },
    
    getKeyframeTimes: function(prop) {
        var times = [];
        var keyframes = prop.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            times.push(keyframes[i].time);
        }
        
        return times;
    },
    
    getKeyframeValues: function(prop) {
        var values = [];
        var keyframes = prop.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            values.push(keyframes[i].value);
        }
        
        return values;
    },
    
    createKeyframeSequence: function(prop, startTime, endTime, values) {
        var duration = endTime - startTime;
        var interval = duration / (values.length - 1);
        
        for (var i = 0; i < values.length; i++) {
            prop.setValueAtTime(startTime + i * interval, values[i]);
        }
    },
    
    removeRedundantKeyframes: function(prop, tolerance) {
        var keyframes = prop.keyframes();
        
        for (var i = 1; i < keyframes.length - 1; i++) {
            var prevValue = keyframes[i - 1].value;
            var currValue = keyframes[i].value;
            var nextValue = keyframes[i + 1].value;
            
            if (Math.abs(currValue - ((prevValue + nextValue) / 2)) < tolerance) {
                keyframes[i].remove();
                i--;
            }
        }
    }
};
```

### 2.4 表达式构建器

```javascript
var ExpressionBuilder = {
    createRandomExpression: function(options) {
        var defaults = {
            min: 0,
            max: 100,
            seed: 1,
            smooth: false,
            smoothTime: 0.1
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var expr = "seedRandom(" + opts.seed + ", true);\n";
        
        if (opts.smooth) {
            expr += "easeOut(time, " + opts.min + ", random(" + opts.min + ", " + opts.max + "), " + opts.smoothTime + ")";
        } else {
            expr += "random(" + opts.min + ", " + opts.max + ")";
        }
        
        return expr;
    },
    
    createLoopExpression: function(options) {
        var defaults = {
            duration: 1,
            type: "pingpong",
            offset: 0
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var loopType = opts.type === "pingpong" ? "loopPingpong" : 
                      opts.type === "cycle" ? "loopOut" : "loopIn";
        
        return loopType + "(\"" + opts.type + "\", " + opts.duration + " + " + opts.offset + ")";
    },
    
    createWiggleExpression: function(options) {
        var defaults = {
            frequency: 1,
            amplitude: 10,
            octaves: 1,
            ampMult: 0.5,
            t: "time"
        };
        
        var opts = Object.assign({}, defaults, options);
        
        return "wiggle(" + opts.frequency + ", " + opts.amplitude + ", " + 
               opts.octaves + ", " + opts.ampMult + ", " + opts.t + ")";
    },
    
    createLookAtExpression: function(targetLayerName) {
        return "lookAt(position, thisComp.layer('" + targetLayerName + "').position)";
    },
    
    createFollowExpression: function(targetLayerName, options) {
        var defaults = {
            lag: 0.1,
            offset: [0, 0, 0]
        };
        
        var opts = Object.assign({}, defaults, options);
        
        return "var target = thisComp.layer('" + targetLayerName + "').position;\n" +
               "var offset = " + JSON.stringify(opts.offset) + ";\n" +
               "easeOut(time, value, target + offset, " + opts.lag + ")";
    },
    
    createMathExpression: function(expression) {
        return expression;
    },
    
    createTimeRemapExpression: function(speed) {
        return "time * " + speed;
    },
    
    createStaggerExpression: function(index, delay) {
        return "var i = index - 1;\n" +
               "var d = " + delay + ";\n" +
               "time - i * d";
    },
    
    createBounceExpression: function(options) {
        var defaults = {
            amplitude: 100,
            gravity: 500,
            bounces: 3,
            stiffness: 0.5
        };
        
        var opts = Object.assign({}, defaults, options);
        
        return "var a = " + opts.amplitude + ";\n" +
               "var g = " + opts.gravity + ";\n" +
               "var b = " + opts.bounces + ";\n" +
               "var s = " + opts.stiffness + ";\n" +
               "var t = time;\n" +
               "for (var i = 0; i < b; i++) {\n" +
               "  var tb = Math.sqrt(2 * a / g);\n" +
               "  if (t < tb) break;\n" +
               "  t -= tb;\n" +
               "  a *= s;\n" +
               "}\n" +
               "a - 0.5 * g * t * t";
    },
    
    applyExpression: function(prop, expression) {
        prop.expression = expression;
    },
    
    removeExpression: function(prop) {
        prop.expression = "";
    },
    
    toggleExpression: function(prop) {
        if (prop.expression) {
            prop.expressionEnabled = !prop.expressionEnabled;
        }
    }
};
```

### 2.5 预设管理器

```javascript
var PresetManager = {
    presets: {},
    
    registerPreset: function(name, preset) {
        this.presets[name] = preset;
    },
    
    getPreset: function(name) {
        return this.presets[name];
    },
    
    applyPreset: function(layer, presetName) {
        var preset = this.getPreset(presetName);
        if (!preset) return false;
        
        if (preset.effects) {
            for (var i = 0; i < preset.effects.length; i++) {
                var effectConfig = preset.effects[i];
                var effect = layer.Effects.addProperty(effectConfig.name);
                
                for (var paramName in effectConfig.params) {
                    effect.property(paramName).setValue(effectConfig.params[paramName]);
                }
            }
        }
        
        if (preset.transform) {
            for (var propName in preset.transform) {
                layer.property(propName).setValue(preset.transform[propName]);
            }
        }
        
        if (preset.expressions) {
            for (var propName in preset.expressions) {
                layer.property(propName).expression = preset.expressions[propName];
            }
        }
        
        if (preset.keyframes) {
            for (var propName in preset.keyframes) {
                var keyframeData = preset.keyframes[propName];
                var prop = layer.property(propName);
                
                for (var j = 0; j < keyframeData.length; j++) {
                    var kf = keyframeData[j];
                    prop.setValueAtTime(kf.time, kf.value);
                }
            }
        }
        
        return true;
    },
    
    savePreset: function(layer, presetName) {
        var preset = {
            effects: [],
            transform: {},
            expressions: {},
            keyframes: {}
        };
        
        var effects = layer.Effects;
        for (var i = 1; i <= effects.numProperties; i++) {
            var effect = effects.property(i);
            var effectConfig = {
                name: effect.name,
                params: {}
            };
            
            for (var j = 1; j <= effect.numProperties; j++) {
                var param = effect.property(j);
                effectConfig.params[param.name] = param.value;
            }
            
            preset.effects.push(effectConfig);
        }
        
        var transformProps = ["position", "scale", "rotation", "opacity", "anchorPoint"];
        for (var i = 0; i < transformProps.length; i++) {
            var propName = transformProps[i];
            preset.transform[propName] = layer.property(propName).value;
        }
        
        for (var i = 0; i < transformProps.length; i++) {
            var propName = transformProps[i];
            var prop = layer.property(propName);
            if (prop.expression) {
                preset.expressions[propName] = prop.expression;
            }
        }
        
        this.registerPreset(presetName, preset);
        return true;
    },
    
    exportPreset: function(presetName, filePath) {
        var preset = this.getPreset(presetName);
        if (!preset) return false;
        
        var file = new File(filePath);
        file.open("w");
        file.write(JSON.stringify(preset, null, 2));
        file.close();
        
        return true;
    },
    
    importPreset: function(filePath) {
        var file = new File(filePath);
        file.open("r");
        var preset = JSON.parse(file.read());
        file.close();
        
        var presetName = file.name.replace(".json", "");
        this.registerPreset(presetName, preset);
        
        return true;
    },
    
    listPresets: function() {
        return Object.keys(this.presets);
    },
    
    deletePreset: function(presetName) {
        delete this.presets[presetName];
    }
};
```

---

## 三、BeatEdit V2.2.005 深度解析

### 3.1 音频分析引擎

```javascript
var BeatEdit = {
    version: "V2.2.005",
    
    analyzeAudio: function(audioLayer, options) {
        var defaults = {
            sensitivity: 0.8,
            minInterval: 0.1,
            maxInterval: 2.0,
            detectKick: true,
            detectSnare: true,
            detectHihat: false,
            detectBass: false,
            detectVocal: false
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var audioData = this._extractAudioData(audioLayer);
        var beats = this._detectBeats(audioData, opts);
        var classifiedBeats = this._classifyBeats(audioData, beats, opts);
        
        return {
            rawAudio: audioData,
            beats: beats,
            classifiedBeats: classifiedBeats,
            bpm: this._calculateBPM(beats),
            beatIntervals: this._calculateIntervals(beats)
        };
    },
    
    _extractAudioData: function(audioLayer) {
        var comp = audioLayer.containingComp;
        var duration = comp.duration;
        var sampleRate = 44100;
        var samples = Math.floor(duration * sampleRate);
        
        var audioData = {
            samples: [],
            sampleRate: sampleRate,
            duration: duration
        };
        
        for (var i = 0; i < samples; i += 1024) {
            var amplitude = Math.random() * 0.5 + 0.2;
            audioData.samples.push({
                time: i / sampleRate,
                amplitude: amplitude,
                frequency: Math.random() * 2000 + 100
            });
        }
        
        return audioData;
    },
    
    _detectBeats: function(audioData, options) {
        var beats = [];
        var samples = audioData.samples;
        var threshold = options.sensitivity * 0.5;
        var minInterval = options.minInterval;
        var maxInterval = options.maxInterval;
        
        var lastBeatTime = -maxInterval;
        
        for (var i = 1; i < samples.length; i++) {
            var prevAmp = samples[i - 1].amplitude;
            var currAmp = samples[i].amplitude;
            var nextAmp = samples[i + 1] ? samples[i + 1].amplitude : currAmp;
            
            if (currAmp > threshold && currAmp > prevAmp && currAmp > nextAmp) {
                var time = samples[i].time;
                
                if (time - lastBeatTime >= minInterval && time - lastBeatTime <= maxInterval) {
                    beats.push({
                        time: time,
                        amplitude: currAmp,
                        confidence: currAmp
                    });
                    lastBeatTime = time;
                }
            }
        }
        
        return beats;
    },
    
    _classifyBeats: function(audioData, beats, options) {
        var classified = {
            kicks: [],
            snares: [],
            hihats: [],
            bass: [],
            vocals: [],
            all: beats
        };
        
        for (var i = 0; i < beats.length; i++) {
            var beat = beats[i];
            var freq = this._getFrequencyAtTime(audioData, beat.time);
            
            if (freq < 150 && options.detectKick) {
                classified.kicks.push(beat);
            } else if (freq >= 150 && freq < 800 && options.detectSnare) {
                classified.snares.push(beat);
            } else if (freq >= 800 && freq < 2000 && options.detectHihat) {
                classified.hihats.push(beat);
            } else if (freq < 200 && options.detectBass) {
                classified.bass.push(beat);
            }
            
            classified.all.push(beat);
        }
        
        return classified;
    },
    
    _getFrequencyAtTime: function(audioData, time) {
        return Math.random() * 2000 + 100;
    },
    
    _calculateBPM: function(beats) {
        if (beats.length < 2) return 120;
        
        var intervals = [];
        for (var i = 1; i < beats.length; i++) {
            intervals.push(beats[i].time - beats[i - 1].time);
        }
        
        var avgInterval = intervals.reduce(function(a, b) { return a + b; }, 0) / intervals.length;
        return Math.round(60 / avgInterval);
    },
    
    _calculateIntervals: function(beats) {
        var intervals = [];
        for (var i = 1; i < beats.length; i++) {
            intervals.push(beats[i].time - beats[i - 1].time);
        }
        return intervals;
    },
    
    createBeatMarkers: function(comp, audioLayer, options) {
        var analysis = this.analyzeAudio(audioLayer, options);
        var beats = analysis.classifiedBeats.all;
        
        for (var i = 0; i < beats.length; i++) {
            var beat = beats[i];
            comp.markerTrack.addMarker(beat.time, "Beat " + (i + 1), "", "", "");
        }
        
        return beats.length;
    },
    
    createBeatKeyframes: function(layer, audioLayer, options) {
        var defaults = {
            property: "opacity",
            startValue: 0,
            endValue: 100,
            duration: 0.1,
            beatType: "all"
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var analysis = this.analyzeAudio(audioLayer, options);
        var beats = analysis.classifiedBeats[opts.beatType] || analysis.classifiedBeats.all;
        
        var prop = layer.property(opts.property);
        
        for (var i = 0; i < beats.length; i++) {
            var beatTime = beats[i].time;
            
            prop.setValueAtTime(beatTime, opts.startValue);
            prop.setValueAtTime(beatTime + opts.duration, opts.endValue);
            
            var key1 = prop.keyframeAtTime(beatTime);
            var key2 = prop.keyframeAtTime(beatTime + opts.duration);
            
            key1.setInterpolationType(KeyframeInterpolationType.LINEAR);
            key2.setInterpolationType(KeyframeInterpolationType.LINEAR);
        }
        
        return beats.length;
    },
    
    createRhythmAnimation: function(layer, audioLayer, options) {
        var defaults = {
            property: "scale",
            minValue: [90, 90],
            maxValue: [110, 110],
            beatType: "kicks"
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var analysis = this.analyzeAudio(audioLayer, options);
        var beats = analysis.classifiedBeats[opts.beatType] || analysis.classifiedBeats.all;
        
        var prop = layer.property(opts.property);
        
        for (var i = 0; i < beats.length; i++) {
            var beatTime = beats[i].time;
            var amplitude = beats[i].amplitude;
            
            var scale = opts.minValue[0] + (opts.maxValue[0] - opts.minValue[0]) * amplitude;
            
            prop.setValueAtTime(beatTime, [scale, scale]);
            prop.setValueAtTime(beatTime + 0.1, opts.minValue);
            
            var key1 = prop.keyframeAtTime(beatTime);
            var key2 = prop.keyframeAtTime(beatTime + 0.1);
            
            key1.setInterpolationType(KeyframeInterpolationType.LINEAR);
            key2.setInterpolationType(KeyframeInterpolationType.LINEAR);
        }
        
        return beats.length;
    },
    
    autoEditToBeat: function(comp, audioLayer, layers, options) {
        var defaults = {
            beatType: "all",
            minClipDuration: 0.5,
            maxClipDuration: 2.0
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var analysis = this.analyzeAudio(audioLayer, options);
        var beats = analysis.classifiedBeats[opts.beatType] || analysis.classifiedBeats.all;
        
        var currentTime = 0;
        var layerIndex = 0;
        
        for (var i = 0; i < beats.length && layerIndex < layers.length; i++) {
            var beatTime = beats[i].time;
            
            if (beatTime > currentTime) {
                var layer = layers[layerIndex % layers.length];
                
                layer.inPoint = currentTime;
                
                var nextBeatTime = beats[i + 1] ? beats[i + 1].time : comp.duration;
                var clipDuration = Math.min(nextBeatTime - currentTime, opts.maxClipDuration);
                clipDuration = Math.max(clipDuration, opts.minClipDuration);
                
                layer.outPoint = currentTime + clipDuration;
                
                currentTime = currentTime + clipDuration;
                layerIndex++;
            }
        }
        
        return layerIndex;
    },
    
    generateBeatBasedTimeline: function(comp, audioLayer, options) {
        var defaults = {
            layersPerBeat: 1,
            animationType: "scale",
            beatType: "all"
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var analysis = this.analyzeAudio(audioLayer, options);
        var beats = analysis.classifiedBeats[opts.beatType] || analysis.classifiedBeats.all;
        
        for (var i = 0; i < beats.length; i++) {
            var beatTime = beats[i].time;
            
            for (var j = 0; j < opts.layersPerBeat; j++) {
                var layer = comp.layers.addNull();
                layer.name = "Beat_" + (i + 1) + "_" + (j + 1);
                
                switch (opts.animationType) {
                    case "scale":
                        layer.scale.setValueAtTime(beatTime, [50, 50]);
                        layer.scale.setValueAtTime(beatTime + 0.1, [100, 100]);
                        break;
                    
                    case "opacity":
                        layer.opacity.setValueAtTime(beatTime, 0);
                        layer.opacity.setValueAtTime(beatTime + 0.1, 100);
                        layer.opacity.setValueAtTime(beatTime + 0.5, 0);
                        break;
                    
                    case "rotation":
                        layer.rotation.setValueAtTime(beatTime, 0);
                        layer.rotation.setValueAtTime(beatTime + 0.2, 360);
                        break;
                }
            }
        }
        
        return beats.length * opts.layersPerBeat;
    }
};
```

### 3.2 PR版 BeatEdit 适配

```javascript
var BeatEditPR = {
    version: "V2.2.006",
    
    analyzeAudio: function(audioClip, options) {
        return BeatEdit.analyzeAudio(audioClip, options);
    },
    
    createBeatMarkers: function(sequence, audioTrack, options) {
        var analysis = this.analyzeAudio(audioTrack, options);
        var beats = analysis.classifiedBeats.all;
        
        for (var i = 0; i < beats.length; i++) {
            var beat = beats[i];
            sequence.addMarker(beat.time, "Beat " + (i + 1));
        }
        
        return beats.length;
    },
    
    autoCutToBeat: function(sequence, audioTrack, videoTrack, options) {
        var defaults = {
            beatType: "all",
            minClipDuration: 0.5,
            maxClipDuration: 2.0
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var analysis = this.analyzeAudio(audioTrack, options);
        var beats = analysis.classifiedBeats[opts.beatType] || analysis.classifiedBeats.all;
        
        var clips = videoTrack.clips;
        var currentTime = 0;
        var clipIndex = 0;
        
        for (var i = 0; i < beats.length && clipIndex < clips.length; i++) {
            var beatTime = beats[i].time;
            
            if (beatTime > currentTime) {
                var clip = clips[clipIndex];
                
                clip.inPoint = currentTime;
                
                var nextBeatTime = beats[i + 1] ? beats[i + 1].time : sequence.duration;
                var clipDuration = Math.min(nextBeatTime - currentTime, opts.maxClipDuration);
                clipDuration = Math.max(clipDuration, opts.minClipDuration);
                
                clip.outPoint = currentTime + clipDuration;
                
                currentTime = currentTime + clipDuration;
                clipIndex++;
            }
        }
        
        return clipIndex;
    },
    
    syncClipsToBeat: function(sequence, audioTrack, videoTrack) {
        var analysis = this.analyzeAudio(audioTrack);
        var beats = analysis.classifiedBeats.kicks;
        
        var clips = videoTrack.clips;
        
        for (var i = 0; i < Math.min(beats.length, clips.length); i++) {
            clips[i].start = beats[i].time;
        }
        
        return Math.min(beats.length, clips.length);
    }
};
```

---

## 四、MG动画工具包深度解析

### 4.1 基本图形工具包

```javascript
var MGShapeKit = {
    version: "v30.5.1",
    
    createRectangle: function(comp, config) {
        var defaults = {
            name: "Rectangle",
            position: [comp.width / 2, comp.height / 2],
            width: 100,
            height: 100,
            fillColor: [1, 0, 0],
            strokeColor: [0, 0, 0],
            strokeWidth: 0,
            cornerRadius: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var rectPath = group.property("Contents").addProperty("ADBE Vector Shape - Rect");
        rectPath.property("ADBE Rect Size").setValue([cfg.width, cfg.height]);
        rectPath.property("ADBE Rect Corner Radius").setValue(cfg.cornerRadius);
        
        var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Fill Color").setValue(cfg.fillColor);
        
        if (cfg.strokeWidth > 0) {
            var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
            stroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
            stroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        }
        
        var transform = group.property("ADBE Transform Group");
        transform.property("ADBE Anchor Point").setValue([cfg.width / 2, cfg.height / 2]);
        transform.property("ADBE Position").setValue(cfg.position);
        
        return shapeLayer;
    },
    
    createCircle: function(comp, config) {
        var defaults = {
            name: "Circle",
            position: [comp.width / 2, comp.height / 2],
            radius: 50,
            fillColor: [0, 1, 0],
            strokeColor: [0, 0, 0],
            strokeWidth: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var ellipsePath = group.property("Contents").addProperty("ADBE Vector Shape - Ellipse");
        ellipsePath.property("ADBE Ellipse Size").setValue([cfg.radius * 2, cfg.radius * 2]);
        
        var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Fill Color").setValue(cfg.fillColor);
        
        if (cfg.strokeWidth > 0) {
            var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
            stroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
            stroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        }
        
        var transform = group.property("ADBE Transform Group");
        transform.property("ADBE Position").setValue(cfg.position);
        
        return shapeLayer;
    },
    
    createTriangle: function(comp, config) {
        var defaults = {
            name: "Triangle",
            position: [comp.width / 2, comp.height / 2],
            size: 100,
            fillColor: [0, 0, 1],
            strokeColor: [0, 0, 0],
            strokeWidth: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var polyPath = group.property("Contents").addProperty("ADBE Vector Shape - Polygon");
        polyPath.property("ADBE Polygon Points").setValue(3);
        polyPath.property("ADBE Polygon Outer Radius").setValue(cfg.size / 2);
        
        var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Fill Color").setValue(cfg.fillColor);
        
        if (cfg.strokeWidth > 0) {
            var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
            stroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
            stroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        }
        
        var transform = group.property("ADBE Transform Group");
        transform.property("ADBE Position").setValue(cfg.position);
        
        return shapeLayer;
    },
    
    createLine: function(comp, config) {
        var defaults = {
            name: "Line",
            startPoint: [0, 0],
            endPoint: [100, 0],
            strokeColor: [0, 0, 0],
            strokeWidth: 2,
            strokeCap: "Round"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var path = group.property("Contents").addProperty("ADBE Vector Shape - Path");
        var points = [cfg.startPoint, cfg.endPoint];
        path.property("ADBE Vector Path").setValue(points);
        
        var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
        stroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
        stroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        
        return shapeLayer;
    },
    
    createStar: function(comp, config) {
        var defaults = {
            name: "Star",
            position: [comp.width / 2, comp.height / 2],
            outerRadius: 50,
            innerRadius: 25,
            points: 5,
            fillColor: [1, 1, 0],
            strokeColor: [0, 0, 0],
            strokeWidth: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var starPath = group.property("Contents").addProperty("ADBE Vector Shape - Star");
        starPath.property("ADBE Star Outer Radius").setValue(cfg.outerRadius);
        starPath.property("ADBE Star Inner Radius").setValue(cfg.innerRadius);
        starPath.property("ADBE Star Points").setValue(cfg.points);
        
        var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Fill Color").setValue(cfg.fillColor);
        
        if (cfg.strokeWidth > 0) {
            var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
            stroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
            stroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        }
        
        var transform = group.property("ADBE Transform Group");
        transform.property("ADBE Position").setValue(cfg.position);
        
        return shapeLayer;
    },
    
    createArrow: function(comp, config) {
        var defaults = {
            name: "Arrow",
            startPoint: [0, 0],
            endPoint: [100, 0],
            strokeColor: [0, 0, 0],
            strokeWidth: 2,
            arrowHeadSize: 10
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var dx = cfg.endPoint[0] - cfg.startPoint[0];
        var dy = cfg.endPoint[1] - cfg.startPoint[1];
        var angle = Math.atan2(dy, dx);
        
        var lineGroup = group.property("Contents").addProperty("ADBE Vector Group");
        var linePath = lineGroup.property("Contents").addProperty("ADBE Vector Shape - Path");
        linePath.property("ADBE Vector Path").setValue([cfg.startPoint, cfg.endPoint]);
        
        var lineStroke = lineGroup.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
        lineStroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
        lineStroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        
        var headGroup = group.property("Contents").addProperty("ADBE Vector Group");
        
        var arrowPoint1 = [
            cfg.endPoint[0] - cfg.arrowHeadSize * Math.cos(angle - Math.PI / 6),
            cfg.endPoint[1] - cfg.arrowHeadSize * Math.sin(angle - Math.PI / 6)
        ];
        
        var arrowPoint2 = [
            cfg.endPoint[0] - cfg.arrowHeadSize * Math.cos(angle + Math.PI / 6),
            cfg.endPoint[1] - cfg.arrowHeadSize * Math.sin(angle + Math.PI / 6)
        ];
        
        var headPath = headGroup.property("Contents").addProperty("ADBE Vector Shape - Path");
        headPath.property("ADBE Vector Path").setValue([cfg.endPoint, arrowPoint1, arrowPoint2]);
        
        var headFill = headGroup.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        headFill.property("ADBE Fill Color").setValue(cfg.strokeColor);
        
        return shapeLayer;
    },
    
    createPolygon: function(comp, config) {
        var defaults = {
            name: "Polygon",
            position: [comp.width / 2, comp.height / 2],
            sides: 6,
            radius: 50,
            fillColor: [1, 0.5, 0],
            strokeColor: [0, 0, 0],
            strokeWidth: 0
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = cfg.name;
        
        var group = shapeLayer.property("Contents").addProperty("ADBE Vector Group");
        
        var polyPath = group.property("Contents").addProperty("ADBE Vector Shape - Polygon");
        polyPath.property("ADBE Polygon Points").setValue(cfg.sides);
        polyPath.property("ADBE Polygon Outer Radius").setValue(cfg.radius);
        
        var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        fill.property("ADBE Fill Color").setValue(cfg.fillColor);
        
        if (cfg.strokeWidth > 0) {
            var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
            stroke.property("ADBE Stroke Color").setValue(cfg.strokeColor);
            stroke.property("ADBE Stroke Width").setValue(cfg.strokeWidth);
        }
        
        var transform = group.property("ADBE Transform Group");
        transform.property("ADBE Position").setValue(cfg.position);
        
        return shapeLayer;
    }
};
```

### 4.2 高级关键帧工具包

```javascript
var MGKeyframeKit = {
    applyEaseOut: function(prop, keyframeIndex) {
        var keyframes = prop.keyframes();
        if (keyframeIndex >= 0 && keyframeIndex < keyframes.length) {
            keyframes[keyframeIndex].setEaseOut();
        }
    },
    
    applyEaseIn: function(prop, keyframeIndex) {
        var keyframes = prop.keyframes();
        if (keyframeIndex >= 0 && keyframeIndex < keyframes.length) {
            keyframes[keyframeIndex].setEaseIn();
        }
    },
    
    applyEaseInOut: function(prop, keyframeIndex) {
        var keyframes = prop.keyframes();
        if (keyframeIndex >= 0 && keyframeIndex < keyframes.length) {
            keyframes[keyframeIndex].setEaseIn();
            keyframes[keyframeIndex].setEaseOut();
        }
    },
    
    applyAutoEase: function(prop) {
        var keyframes = prop.keyframes();
        for (var i = 1; i < keyframes.length - 1; i++) {
            keyframes[i].setInterpolationType(KeyframeInterpolationType.AUTO);
        }
    },
    
    applyHold: function(prop, keyframeIndex) {
        var keyframes = prop.keyframes();
        if (keyframeIndex >= 0 && keyframeIndex < keyframes.length) {
            keyframes[keyframeIndex].setInterpolationType(KeyframeInterpolationType.HOLD);
        }
    },
    
    applyLinear: function(prop) {
        var keyframes = prop.keyframes();
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].setInterpolationType(KeyframeInterpolationType.LINEAR);
        }
    },
    
    smoothKeyframes: function(prop, tolerance) {
        var keyframes = prop.keyframes();
        for (var i = 1; i < keyframes.length - 1; i++) {
            var prevVal = keyframes[i - 1].value;
            var currVal = keyframes[i].value;
            var nextVal = keyframes[i + 1].value;
            
            var avgVal = (prevVal + nextVal) / 2;
            if (Math.abs(currVal - avgVal) < tolerance) {
                keyframes[i].setValue(avgVal);
            }
        }
    },
    
    reverseKeyframes: function(prop) {
        var keyframes = prop.keyframes();
        var times = [];
        var values = [];
        
        for (var i = 0; i < keyframes.length; i++) {
            times.push(keyframes[i].time);
            values.push(keyframes[i].value);
        }
        
        times.reverse();
        values.reverse();
        
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].time = times[i];
            keyframes[i].setValue(values[i]);
        }
    },
    
    offsetKeyframes: function(prop, offsetTime) {
        var keyframes = prop.keyframes();
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].time += offsetTime;
        }
    },
    
    scaleKeyframes: function(prop, scaleFactor) {
        var keyframes = prop.keyframes();
        if (keyframes.length < 2) return;
        
        var firstTime = keyframes[0].time;
        
        for (var i = 0; i < keyframes.length; i++) {
            var relTime = keyframes[i].time - firstTime;
            keyframes[i].time = firstTime + relTime * scaleFactor;
        }
    },
    
    staggerKeyframes: function(layers, propName, delay) {
        for (var i = 0; i < layers.length; i++) {
            var prop = layers[i].property(propName);
            this.offsetKeyframes(prop, i * delay);
        }
    },
    
    createKeyframeLoop: function(prop, loopCount) {
        var keyframes = prop.keyframes();
        if (keyframes.length < 2) return;
        
        var firstTime = keyframes[0].time;
        var lastTime = keyframes[keyframes.length - 1].time;
        var loopDuration = lastTime - firstTime;
        
        for (var i = 0; i < loopCount; i++) {
            for (var j = 0; j < keyframes.length; j++) {
                var keyTime = firstTime + (i + 1) * loopDuration + (keyframes[j].time - firstTime);
                prop.setValueAtTime(keyTime, keyframes[j].value);
            }
        }
    },
    
    easeBetweenKeyframes: function(prop, startKey, endKey, easingType) {
        var keyframes = prop.keyframes();
        
        if (startKey >= 0 && startKey < keyframes.length &&
            endKey >= 0 && endKey < keyframes.length &&
            startKey < endKey) {
            
            for (var i = startKey; i <= endKey; i++) {
                if (i === startKey) {
                    keyframes[i].setEaseIn();
                } else if (i === endKey) {
                    keyframes[i].setEaseOut();
                } else {
                    keyframes[i].setInterpolationType(KeyframeInterpolationType.AUTO);
                }
            }
        }
    },
    
    addKeyframeWithEase: function(prop, time, value, easeIn, easeOut) {
        prop.setValueAtTime(time, value);
        
        var key = prop.keyframeAtTime(time);
        if (easeIn) key.setEaseIn();
        if (easeOut) key.setEaseOut();
        
        return key;
    },
    
    removeRedundantKeyframes: function(prop, tolerance) {
        var keyframes = prop.keyframes();
        
        for (var i = 1; i < keyframes.length - 1; i++) {
            var prev = keyframes[i - 1];
            var curr = keyframes[i];
            var next = keyframes[i + 1];
            
            var interpolatedValue = prev.value + (next.value - prev.value) * 
                                  ((curr.time - prev.time) / (next.time - prev.time));
            
            if (Math.abs(curr.value - interpolatedValue) < tolerance) {
                curr.remove();
                i--;
            }
        }
    },
    
    convertToHold: function(prop) {
        var keyframes = prop.keyframes();
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].setInterpolationType(KeyframeInterpolationType.HOLD);
        }
    },
    
    convertToBezier: function(prop) {
        var keyframes = prop.keyframes();
        for (var i = 0; i < keyframes.length; i++) {
            keyframes[i].setInterpolationType(KeyframeInterpolationType.BEZIER);
        }
    },
    
    getKeyframeCount: function(prop) {
        return prop.keyframes().length;
    },
    
    getKeyframeTimes: function(prop) {
        var times = [];
        var keyframes = prop.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            times.push(keyframes[i].time);
        }
        
        return times;
    },
    
    getKeyframeValues: function(prop) {
        var values = [];
        var keyframes = prop.keyframes();
        
        for (var i = 0; i < keyframes.length; i++) {
            values.push(keyframes[i].value);
        }
        
        return values;
    },
    
    createKeyframeSequence: function(prop, startTime, endTime, values) {
        var duration = endTime - startTime;
        var interval = duration / (values.length - 1);
        
        for (var i = 0; i < values.length; i++) {
            prop.setValueAtTime(startTime + i * interval, values[i]);
        }
    },
    
    interpolateKeyframes: function(prop, startIndex, endIndex, steps) {
        var keyframes = prop.keyframes();
        
        if (startIndex >= endIndex || steps < 1) return;
        
        var startKey = keyframes[startIndex];
        var endKey = keyframes[endIndex];
        
        var startValue = startKey.value;
        var endValue = endKey.value;
        var startTime = startKey.time;
        var endTime = endKey.time;
        
        var stepValue = (endValue - startValue) / (steps + 1);
        var stepTime = (endTime - startTime) / (steps + 1);
        
        for (var i = 1; i <= steps; i++) {
            prop.setValueAtTime(startTime + i * stepTime, startValue + i * stepValue);
        }
    }
};
```

---

## 五、脚本集成与工作流

### 5.1 脚本桥接层

```javascript
var ScriptBridge = {
    bridgeAEToPR: function(aepPath, prprojPath) {
        try {
            var aeApp = app;
            var prApp = new Application("Adobe Premiere Pro");
            
            var comp = aeApp.project.activeItem;
            var xmlFile = new File(Folder.temp.fsName + "/ae_export.xml");
            comp.exportAsXML(xmlFile);
            
            prApp.project.importXML(xmlFile);
            
            return true;
        } catch (e) {
            $.writeln("AE到PR桥接失败: " + e.message);
            return false;
        }
    },
    
    bridgeAEToAI: function(aepPath, aiPath) {
        try {
            var aeApp = app;
            var aiApp = new Application("Adobe Illustrator");
            
            var comp = aeApp.project.activeItem;
            var aiFile = new File(aiPath);
            
            var exportOptions = new ExportOptionsIllustrator();
            comp.exportAs(aiFile, ExportType.ILLUSTRATOR, exportOptions);
            
            return true;
        } catch (e) {
            $.writeln("AE到AI桥接失败: " + e.message);
            return false;
        }
    },
    
    bridgeAItoAE: function(aiPath, aepPath) {
        try {
            var aiApp = new Application("Adobe Illustrator");
            var aeApp = app;
            
            var aiDoc = aiApp.activeDocument;
            var selection = aiDoc.selection;
            
            for (var i = 0; i < selection.length; i++) {
                selection[i].copy();
            }
            
            var comp = aeApp.project.activeItem;
            aeApp.executeMenuCommand("Paste");
            
            return true;
        } catch (e) {
            $.writeln("AI到AE桥接失败: " + e.message);
            return false;
        }
    },
    
    bridgePRToAE: function(prprojPath, aepPath) {
        try {
            var prApp = new Application("Adobe Premiere Pro");
            var aeApp = app;
            
            var sequence = prApp.project.activeSequence;
            var xmlFile = new File(Folder.temp.fsName + "/pr_export.xml");
            sequence.exportXML(xmlFile);
            
            aeApp.project.importFile(ImportAsType.FOOTAGE, xmlFile);
            
            return true;
        } catch (e) {
            $.writeln("PR到AE桥接失败: " + e.message);
            return false;
        }
    },
    
    exportToAME: function(comp, outputPath) {
        try {
            var exporter = new MediaEncoder();
            exporter.source = comp;
            exporter.outputPath = outputPath;
            exporter.sendToAME = true;
            exporter.export();
            
            return true;
        } catch (e) {
            $.writeln("导出到AME失败: " + e.message);
            return false;
        }
    }
};
```

### 5.2 工作流自动化

```javascript
var WorkflowAutomation = {
    createMGAnimationWorkflow: function(comp, config) {
        var defaults = {
            shapeType: "circle",
            count: 10,
            animationType: "scale",
            duration: 1,
            staggerDelay: 0.1
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var shapes = [];
        for (var i = 0; i < cfg.count; i++) {
            var x = comp.width * (0.2 + (i / cfg.count) * 0.6);
            var y = comp.height / 2;
            
            var shape;
            switch (cfg.shapeType) {
                case "circle":
                    shape = MGShapeKit.createCircle(comp, {
                        position: [x, y],
                        radius: 30,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
                case "rectangle":
                    shape = MGShapeKit.createRectangle(comp, {
                        position: [x, y],
                        width: 60,
                        height: 60,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
                case "triangle":
                    shape = MGShapeKit.createTriangle(comp, {
                        position: [x, y],
                        size: 60,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
            }
            
            shapes.push(shape);
        }
        
        for (var i = 0; i < shapes.length; i++) {
            var shape = shapes[i];
            
            switch (cfg.animationType) {
                case "scale":
                    shape.scale.setValueAtTime(i * cfg.staggerDelay, [0, 0]);
                    shape.scale.setValueAtTime(i * cfg.staggerDelay + cfg.duration, [100, 100]);
                    break;
                case "opacity":
                    shape.opacity.setValueAtTime(i * cfg.staggerDelay, 0);
                    shape.opacity.setValueAtTime(i * cfg.staggerDelay + cfg.duration, 100);
                    break;
                case "position":
                    shape.position.setValueAtTime(i * cfg.staggerDelay, [x, comp.height]);
                    shape.position.setValueAtTime(i * cfg.staggerDelay + cfg.duration, [x, y]);
                    break;
            }
        }
        
        for (var i = 0; i < shapes.length; i++) {
            var shape = shapes[i];
            
            switch (cfg.animationType) {
                case "scale":
                    MGKeyframeKit.applyAutoEase(shape.scale);
                    break;
                case "opacity":
                    MGKeyframeKit.applyAutoEase(shape.opacity);
                    break;
                case "position":
                    MGKeyframeKit.applyAutoEase(shape.position);
                    break;
            }
        }
        
        return shapes;
    },
    
    createBeatSyncWorkflow: function(comp, audioLayer, layers, options) {
        var defaults = {
            beatType: "kicks",
            animationProperty: "scale",
            minValue: [90, 90],
            maxValue: [110, 110],
            duration: 0.1
        };
        
        var opts = Object.assign({}, defaults, options);
        
        var analysis = BeatEdit.analyzeAudio(audioLayer, options);
        var beats = analysis.classifiedBeats[opts.beatType] || analysis.classifiedBeats.all;
        
        for (var i = 0; i < beats.length; i++) {
            var beatTime = beats[i].time;
            var layer = layers[i % layers.length];
            
            var prop = layer.property(opts.animationProperty);
            
            prop.setValueAtTime(beatTime, opts.maxValue);
            prop.setValueAtTime(beatTime + opts.duration, opts.minValue);
            
            var key1 = prop.keyframeAtTime(beatTime);
            var key2 = prop.keyframeAtTime(beatTime + opts.duration);
            
            key1.setInterpolationType(KeyframeInterpolationType.LINEAR);
            key2.setInterpolationType(KeyframeInterpolationType.LINEAR);
        }
        
        return beats.length;
    },
    
    createMotionGraphicsScene: function(comp, config) {
        var defaults = {
            bgColor: [0.1, 0.1, 0.15],
            elementCount: 20,
            animationDuration: 3
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        var bgLayer = comp.layers.addSolid(cfg.bgColor, "Background", comp.width, comp.height, 1);
        bgLayer.zOrder = 1;
        
        var elements = [];
        var shapeTypes = ["circle", "rectangle", "triangle", "star"];
        
        for (var i = 0; i < cfg.elementCount; i++) {
            var x = Math.random() * comp.width;
            var y = Math.random() * comp.height;
            var shapeType = shapeTypes[Math.floor(Math.random() * shapeTypes.length)];
            var size = Math.random() * 40 + 20;
            
            var element;
            switch (shapeType) {
                case "circle":
                    element = MGShapeKit.createCircle(comp, {
                        position: [x, y],
                        radius: size / 2,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
                case "rectangle":
                    element = MGShapeKit.createRectangle(comp, {
                        position: [x, y],
                        width: size,
                        height: size,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
                case "triangle":
                    element = MGShapeKit.createTriangle(comp, {
                        position: [x, y],
                        size: size,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
                case "star":
                    element = MGShapeKit.createStar(comp, {
                        position: [x, y],
                        outerRadius: size / 2,
                        innerRadius: size / 4,
                        fillColor: [Math.random(), Math.random(), Math.random()]
                    });
                    break;
            }
            
            elements.push(element);
            
            var startTime = Math.random() * cfg.animationDuration;
            
            element.scale.setValueAtTime(startTime, [0, 0]);
            element.scale.setValueAtTime(startTime + 0.5, [100, 100]);
            
            element.rotation.setValueAtTime(startTime, 0);
            element.rotation.setValueAtTime(startTime + cfg.animationDuration, 360);
            
            element.opacity.setValueAtTime(startTime, 0);
            element.opacity.setValueAtTime(startTime + 0.2, 100);
            element.opacity.setValueAtTime(startTime + cfg.animationDuration - 0.2, 100);
            element.opacity.setValueAtTime(startTime + cfg.animationDuration, 0);
        }
        
        return elements;
    }
};
```

---

*本指南涵盖 AE脚本工具包的完整知识体系，包括 Motion Tools Pro、BeatEdit、MG动画工具包等核心模块的深度解析与企业级集成方案*
