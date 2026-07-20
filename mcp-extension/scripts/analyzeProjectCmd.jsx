#target aftereffects

(function() {
    #include "_lib/args_loader.jsx"
    #include "_lib/response_utils.jsx"

    // 参数化：从 args.json 读取 projectPath 和 outputFile，禁止回退到硬编码默认值
    // 原硬编码值: var projectPath = "D:/AE-Work/resources/projects/53动漫/25版打开.aep";
    var args = loadArgs();
    var projectPath = args.projectPath;
    if (!projectPath) {
        print(buildError("E101", "projectPath 参数必填（args.projectPath）"));
        return;
    }

    var projectFile = new File(projectPath);
    if (!projectFile.exists) {
        print(JSON.stringify({error: "Project file not found: " + projectPath}));
        return;
    }

    app.open(projectFile);

    if (app.project === null || app.project.numItems === 0) {
        print(JSON.stringify({error: "Failed to open project"}));
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
            "Glow": "发光",
            "Shine": "扫光",
            "Starglow": "星光",
            "Gaussian Blur": "高斯模糊",
            "Curves": "曲线",
            "Levels": "色阶",
            "Hue/Saturation": "色相/饱和度",
            "CC": "Cycore系列",
            "Time Remapping": "时间重映射",
            "Turbulent Displace": "湍流置换",
            "Displacement Map": "置换贴图",
            "Warp Stabilizer": "变形稳定",
            "LUT": "调色预设"
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

    function analyzeLayer(layer) {
        var layerInfo = {
            name: layer.name,
            type: layer.layerType.toString(),
            index: layer.index,
            effects: [],
            hasKeyframes: false,
            blendMode: layer.blendMode.toString()
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
            
            if (layer instanceof CameraLayer) compInfo.hasCamera = true;
            if (layer instanceof LightLayer) compInfo.hasLight = true;
            if (layer instanceof AdjustmentLayer) {
                compInfo.hasAdjustmentLayer = true;
                compInfo.adjustmentLayers.push(layer.name);
            }
            if (layer instanceof NullLayer) compInfo.nullObjects.push(layer.name);
            if (layer instanceof ShapeLayer) compInfo.shapeLayers.push(layer.name);
            if (layer instanceof TextLayer) compInfo.textLayers.push(layer.name);
            if (layer instanceof FootageLayer) compInfo.footageLayers.push(layer.name);
            if (layer.source instanceof CompItem) {
                compInfo.hasPrecomp = true;
                compInfo.precompLayers.push(layer.name);
            }
            if (layer.threeDLayer) compInfo.has3D = true;

            var layerInfo = analyzeLayer(layer);
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

        if (effects.indexOf("Color Key") !== -1 || effects.indexOf("Keylight") !== -1) report.techniques.push("绿幕/蓝幕抠图技术");
        if (effects.indexOf("Glow") !== -1 && effects.indexOf("Saber") !== -1) report.techniques.push("发光光效组合");
        if (effects.indexOf("Particular") !== -1) report.techniques.push("粒子特效");
        if (effects.indexOf("Optical Flares") !== -1) report.techniques.push("镜头光晕");
        if (effects.indexOf("Time Remapping") !== -1) report.techniques.push("时间重映射");
        if (effects.indexOf("Turbulent Displace") !== -1) report.techniques.push("流体/烟雾效果");
        if (effects.indexOf("Displacement Map") !== -1) report.techniques.push("置换贴图");
        if (compInfo.hasCamera && compInfo.has3D) report.techniques.push("3D摄像机运动");
        if (compInfo.adjustmentLayers.length > 0) report.techniques.push("调整层全局控制");
        if (compInfo.nullObjects.length > 0) report.techniques.push("Null对象控制器");
        if (compInfo.hasPrecomp) report.techniques.push("预合成组织");
    }

    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem) {
            analyzeComp(item);
        }
    }

    report.techniques = [...new Set(report.techniques)];

    // 参数化：从 args 读取 outputFile，禁止回退到硬编码默认值
    // 原硬编码值: var outputFile = new File("D:/AE-Work/analysis/53动漫_analysis.json");
    if (!args.outputFile) {
        print(buildError("E102", "outputFile 参数必填（args.outputFile）"));
        return;
    }
    var outputFile = new File(args.outputFile);
    outputFile.open("w");
    outputFile.write(JSON.stringify(report, null, 2));
    outputFile.close();

    print(JSON.stringify(report));
})();