#target aftereffects

(function() {
    #include "_lib/args_loader.jsx";
    #include "_lib/response_utils.jsx";

    var args = loadArgs();

    if (app.project === null || app.project.numItems === 0) {
        print(buildError("NO_PROJECT", "No project open"));
        return;
    }

    var report = {
        projectName: app.project.file.name,
        projectPath: app.project.file.fsName,
        totalComps: 0,
        totalLayers: 0,
        effectsByType: {},
        pluginEffects: [],
        standardEffects: [],
        comps: [],
        keyframeStats: { total: 0, animatedLayers: 0, keyframedEffects: 0 },
        techniques: []
    };

    function getEffectCategory(effectName) {
        var categories = {
            "Particular": "粒子特效",
            "Saber": "光效",
            "Optical Flares": "光晕",
            "Element 3D": "3D元素",
            "Trapcode": "Trapcode系列",
            "Form": "粒子网格",
            "Sound Keys": "音频响应",
            "Color Key": "抠图",
            "Keylight": "专业抠图",
            "Luma Key": "亮度抠图",
            "Extract": "提取",
            "Glow": "发光",
            "Shine": "扫光",
            "Starglow": "星光",
            "Fast Blur": "快速模糊",
            "Gaussian Blur": "高斯模糊",
            "Directional Blur": "方向模糊",
            "Motion Blur": "运动模糊",
            "Tint": "色调",
            "Curves": "曲线",
            "Levels": "色阶",
            "Hue/Saturation": "色相/饱和度",
            "Color Balance": "色彩平衡",
            "Gradient Overlay": "渐变叠加",
            "Drop Shadow": "投影",
            "Bevel Alpha": "斜面Alpha",
            "Perspective": "透视",
            "CC": "Cycore系列",
            "Time Remapping": "时间重映射",
            "Time Stretch": "时间拉伸",
            "Time Reverse": "时间反转",
            "Warp Stabilizer": "变形稳定",
            "LUT": "调色预设",
            "Displacement Map": "置换贴图",
            "Turbulent Displace": "湍流置换",
            "Slider Control": "滑块控制",
            "Checkbox Control": "复选框控制",
            "Color Control": "颜色控制",
            "Point Control": "点控制"
        };
        
        for (var cat in categories) {
            if (effectName.indexOf(cat) !== -1) {
                return categories[cat];
            }
        }
        return "其他";
    }

    function isPluginEffect(effectName) {
        var pluginKeywords = ["Particular", "Saber", "Optical Flares", "Element 3D", "Trapcode", "Form", "Sound Keys", "Color Finesse", "Magic Bullet", "Red Giant", "Boris", "Deep Glow", "Newton", "Lockdown"];
        for (var i = 0; i < pluginKeywords.length; i++) {
            if (effectName.indexOf(pluginKeywords[i]) !== -1) {
                return true;
            }
        }
        return false;
    }

    function analyzeLayer(layer, compName) {
        var layerInfo = {
            name: layer.name,
            type: layer.layerType.toString(),
            index: layer.index,
            duration: layer.outPoint - layer.inPoint,
            effects: [],
            hasKeyframes: false,
            blendMode: layer.blendMode.toString(),
            opacity: layer.opacity.value,
            scale: layer.scale.value[0] + "%"
        };

        if (layer.property("Position").numKeys > 0 ||
            layer.property("Scale").numKeys > 0 ||
            layer.property("Rotation").numKeys > 0 ||
            layer.property("Opacity").numKeys > 0) {
            layerInfo.hasKeyframes = true;
            report.keyframeStats.total += 
                layer.property("Position").numKeys +
                layer.property("Scale").numKeys +
                layer.property("Rotation").numKeys +
                layer.property("Opacity").numKeys;
        }

        for (var i = 1; i <= layer.Effects.numProperties; i++) {
            var effect = layer.Effects.property(i);
            var effectName = effect.name;
            
            var effectInfo = {
                name: effectName,
                isPlugin: isPluginEffect(effectName),
                category: getEffectCategory(effectName),
                numKeyframes: effect.numKeys
            };

            layerInfo.effects.push(effectInfo);
            
            if (effect.numKeys > 0) {
                report.keyframeStats.total += effect.numKeys;
                report.keyframeStats.keyframedEffects++;
            }

            if (!report.effectsByType[effectName]) {
                report.effectsByType[effectName] = { count: 0, category: getEffectCategory(effectName), isPlugin: isPluginEffect(effectName) };
            }
            report.effectsByType[effectName].count++;

            if (isPluginEffect(effectName)) {
                if (report.pluginEffects.indexOf(effectName) === -1) {
                    report.pluginEffects.push(effectName);
                }
            } else {
                if (report.standardEffects.indexOf(effectName) === -1) {
                    report.standardEffects.push(effectName);
                }
            }
        }

        if (layerInfo.hasKeyframes) {
            report.keyframeStats.animatedLayers++;
        }

        return layerInfo;
    }

    function analyzeComp(comp) {
        var compInfo = {
            name: comp.name,
            width: comp.width,
            height: comp.height,
            duration: comp.duration,
            frameRate: comp.frameRate,
            has3D: false,
            hasCamera: false,
            hasLight: false,
            hasAdjustmentLayer: false,
            hasPrecomp: false,
            layers: [],
            adjustmentLayers: [],
            nullObjects: [],
            shapeLayers: [],
            textLayers: [],
            footageLayers: [],
            precompLayers: []
        };

        for (var i = 1; i <= comp.numLayers; i++) {
            var layer = comp.layer(i);
            
            if (layer instanceof CameraLayer) {
                compInfo.hasCamera = true;
            }
            if (layer instanceof LightLayer) {
                compInfo.hasLight = true;
            }
            if (layer instanceof AdjustmentLayer) {
                compInfo.hasAdjustmentLayer = true;
                compInfo.adjustmentLayers.push(layer.name);
            }
            if (layer instanceof NullLayer) {
                compInfo.nullObjects.push(layer.name);
            }
            if (layer instanceof ShapeLayer) {
                compInfo.shapeLayers.push(layer.name);
            }
            if (layer instanceof TextLayer) {
                compInfo.textLayers.push(layer.name);
            }
            if (layer instanceof FootageLayer) {
                compInfo.footageLayers.push(layer.name);
            }
            if (layer.source instanceof CompItem) {
                compInfo.hasPrecomp = true;
                compInfo.precompLayers.push(layer.name);
            }

            if (layer.threeDLayer) {
                compInfo.has3D = true;
            }

            var layerInfo = analyzeLayer(layer, comp.name);
            compInfo.layers.push(layerInfo);
            report.totalLayers++;
        }

        report.comps.push(compInfo);
        report.totalComps++;

        detectTechniques(compInfo);
    }

    function detectTechniques(compInfo) {
        var effects = [];
        compInfo.layers.forEach(function(layer) {
            layer.effects.forEach(function(effect) {
                effects.push(effect.name);
            });
        });

        if (effects.indexOf("Color Key") !== -1 || effects.indexOf("Keylight") !== -1) {
            report.techniques.push("绿幕/蓝幕抠图技术");
        }
        if (effects.indexOf("Glow") !== -1 && effects.indexOf("Saber") !== -1) {
            report.techniques.push("发光光效组合");
        }
        if (effects.indexOf("Particular") !== -1) {
            report.techniques.push("粒子特效");
        }
        if (effects.indexOf("Optical Flares") !== -1) {
            report.techniques.push("镜头光晕");
        }
        if (effects.indexOf("Time Remapping") !== -1) {
            report.techniques.push("时间重映射");
        }
        if (effects.indexOf("Turbulent Displace") !== -1) {
            report.techniques.push("流体/烟雾效果");
        }
        if (effects.indexOf("Displacement Map") !== -1) {
            report.techniques.push("置换贴图");
        }
        if (effects.indexOf("LUT") !== -1) {
            report.techniques.push("LUT调色预设");
        }
        if (compInfo.hasCamera && compInfo.has3D) {
            report.techniques.push("3D摄像机运动");
        }
        if (compInfo.adjustmentLayers.length > 0) {
            report.techniques.push("调整层全局控制");
        }
        if (compInfo.nullObjects.length > 0) {
            report.techniques.push("Null对象控制器");
        }
        if (compInfo.hasPrecomp) {
            report.techniques.push("预合成组织");
        }
    }

    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem) {
            analyzeComp(item);
        }
    }

    report.techniques = [...new Set(report.techniques)];

    print(buildSuccess(report));
    return buildSuccess(report);
})();