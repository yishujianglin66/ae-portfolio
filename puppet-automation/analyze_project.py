import asyncio
import json

from src.config.settings import settings
from src.engines.ae.engine import AEEngine


async def analyze_project(project_path, output_file):
    engine = AEEngine()
    
    script = '''
(function() {
    if (app.project === null || app.project.numItems === 0) {
        return JSON.stringify({error: "No project open"});
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
    return JSON.stringify(report);
})();
'''
    
    result = await engine.run_script(script, project_path)
    print(f"Success: {result.success}")
    print(f"aerender_path: {settings.aerender_path}")
    
    if result.success and result.metadata:
        stdout = result.metadata.get("stdout", "")
        print(f"Output length: {len(stdout)}")
        try:
            data = json.loads(stdout)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Analysis saved to: {output_file}")
            
            print("\n=== 分析摘要 ===")
            print(f"项目名称: {data.get('projectName', 'N/A')}")
            print(f"合成数量: {data.get('totalComps', 0)}")
            print(f"图层总数: {data.get('totalLayers', 0)}")
            print(f"关键帧总数: {data.get('keyframeStats', {}).get('total', 0)}")
            print(f"第三方插件: {len(data.get('pluginEffects', []))} 种")
            print(f"检测到的技术: {len(data.get('techniques', []))} 种")
            
            if data.get('pluginEffects'):
                print(f"\n插件列表: {', '.join(data['pluginEffects'])}")
            if data.get('techniques'):
                print(f"\n技术列表: {', '.join(data['techniques'])}")
                
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"原始输出: {stdout[:500]}")
    else:
        print(f"Error: {result.error}")

if __name__ == "__main__":
    projects = [
        ("D:/AE-Work/resources/projects/53动漫/25版打开.aep", "D:/AE-Work/analysis/53动漫_analysis.json")
    ]
    
    for project_path, output_file in projects:
        print(f"\n{'='*50}")
        print(f"分析项目: {project_path}")
        print(f"{'='*50}")
        asyncio.run(analyze_project(project_path, output_file))