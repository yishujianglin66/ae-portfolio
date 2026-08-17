// textFXResourceIndex.jsx
// 文字特效资源总索引 - 所有可用资源的统一查询入口
// 总计: 4998 个 .ffx 预设 + 152 个 .aex 插件 + 79 个程序化动画 + 15 个风格化效果

#include "_lib/response_utils.jsx"

var RESOURCE_INDEX = {
    // === 本地预设库 (4998 .ffx) ===
    "presets": {
        "root": "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Presets",
        "total": 4998,
        "categories": {
            "text_animations": {"path": "Text", "count": 300, "desc": "文字动画预设（18个子分类）"},
            "color_1200": {"path": "1200\u4e2a\u8272\u5f69\u9884\u8bbe", "count": 1195, "desc": "色彩调色预设"},
            "particles_898": {"path": "\u7c92\u5b50\u7279\u6548\u5b9e\u7528\u9884\u8bbe", "count": 898, "desc": "粒子特效预设"},
            "transitions_600": {"path": "600\u4e2a\u8f6c\u573a\u7279\u6548\u9884\u8bbe", "count": 602, "desc": "转场特效预设"},
            "color_275": {"path": "275\u4e2a\u8272\u5f69\u9884\u8bbe", "count": 275, "desc": "色彩预设"},
            "light_250": {"path": "\u5149\u6548\u7279\u6548", "count": 250, "desc": "光效特效"},
            "glow_250": {"path": "\u53d1\u5149\u6548\u679c", "count": 250, "desc": "发光效果"},
            "particular": {"path": "Particular", "count": 243, "desc": "Particular粒子预设"},
            "color_112": {"path": "\u53e4\u98ce\u8272\u5f69\u9884\u8bbe112\u4e2a", "count": 112, "desc": "古风色彩"},
            "toonit": {"path": "ToonItV2 Presets", "count": 79, "desc": "卡通化预设"},
            "color_70": {"path": "70\u79cd\u7535\u5f71\u7247\u8272\u5f69\u9884\u8bbe", "count": 70, "desc": "电影调色"},
            "legacy": {"path": "Legacy", "count": 65, "desc": "经典遗留预设"},
            "form": {"path": "Form", "count": 62, "desc": "Form粒子预设"},
            "shapes": {"path": "Shapes", "count": 58, "desc": "形状动画"},
            "shine": {"path": "Shine", "count": 50, "desc": "光线闪耀"},
            "trapcode_mir": {"path": "Trapcode Mir", "count": 43, "desc": "Trapcode Mir"},
            "trapcode_mir3": {"path": "Trapcode Mir 3", "count": 43, "desc": "Trapcode Mir 3"},
            "damage": {"path": "Digieffects Damage Presets AE", "count": 43, "desc": "破坏效果"},
            "holomatrix": {"path": "(Holomatrix)", "count": 31, "desc": "全息矩阵"},
            "img_creative": {"path": "Image - Creative", "count": 30, "desc": "创意图像效果"},
            "behaviors": {"path": "Behaviors", "count": 27, "desc": "行为动画"},
            "adobe_express": {"path": "Adobe Express", "count": 27, "desc": "Adobe Express"},
            "glitch": {"path": "Glitch\u6548\u679c\u9884\u8bbe", "count": 26, "desc": "故障效果"},
            "trapcode_tao": {"path": "Trapcode Tao", "count": 25, "desc": "Trapcode Tao路径"},
            "backgrounds": {"path": "Backgrounds", "count": 24, "desc": "背景动画"},
            "ink_20": {"path": "20\u4e2a\u6821\u56ed\u5c0f\u6e05\u65b0\u6c34\u58a8\u98ce", "count": 20, "desc": "水墨风格"},
            "trans_dissolves": {"path": "Transitions - Dissolves", "count": 16, "desc": "溶解转场"},
            "trans_movement": {"path": "Transitions - Movement", "count": 18, "desc": "运动转场"},
            "trans_wipes": {"path": "Transitions - Wipes", "count": 17, "desc": "擦除转场"}
        }
    },
    
    // === 外部插件 (152 .aex) ===
    "plugins": {
        "root": "c:/Users/Administrator/Desktop/AE-Knowledge-Vault/external/F-s-PluginsProjects",
        "total": 152,
        "source": "GitHub: bryful/F-s-PluginsProjects (开源免费)",
        "highlights": ["CameraShake", "InnerFlare", "Ligtning", "Mosaic", "Grain", "Emboss", "Gradient", "Chroma", "FloodFill", "BurstLines"]
    },
    
    // === 程序化脚本库 ===
    "scripts": {
        "root": "c:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_additive_scripts",
        "libraries": {
            "textAnimLibrary": {"file": "textAnimLibrary.jsx", "count": 25, "desc": "文字动画（Text Animator系统）"},
            "stylizedTextFX": {"file": "stylizedTextFX.jsx", "count": 15, "desc": "风格化视觉特效"},
            "expressionAnimLib": {"file": "expressionAnimLib.jsx", "count": 18, "desc": "表达式持续动画"},
            "artisticTextGenerator": {"file": "artisticTextGenerator.jsx", "count": 21, "desc": "一键艺术字生成"},
            "textFXMaster": {"file": "textFXMaster.jsx", "count": 0, "desc": "统一主控调度器"},
            "textPresetCatalog": {"file": "textPresetCatalog.jsx", "count": 0, "desc": "内置预设目录调度器"}
        },
        "totalProgrammatic": 79
    },
    
    // === MCP 调用路径 ===
    "mcp_paths": {
        "apply_preset": "AfterEffectsMCP.apply-preset → presetPath → 应用任意 .ffx",
        "apply_effect": "AfterEffectsMCP.apply-effect → effectMatchName + effectSettings → 添加效果",
        "set_expression": "AfterEffectsMCP.setLayerExpression → expressionString → 设置表达式",
        "create_text": "AfterEffectsMCP.run-script(createTextLayer) → 创建文字图层",
        "create_comp": "AfterEffectsMCP.create-composition → 创建合成"
    }
};

function textFXResourceIndex(args) {
    var action = args.action || "overview";
    
    if (action === "overview") {
        return buildSuccessResponse({
            totalResources: 5229,
            breakdown: {
                ffxPresets: 4998,
                aexPlugins: 152,
                programmaticAnimations: 79
            },
            presetCategories: 29,
            scriptLibraries: 6,
            mcpPaths: 5
        });
    }
    
    if (action === "presets") {
        return buildSuccessResponse(RESOURCE_INDEX.presets);
    }
    
    if (action === "plugins") {
        return buildSuccessResponse(RESOURCE_INDEX.plugins);
    }
    
    if (action === "scripts") {
        return buildSuccessResponse(RESOURCE_INDEX.scripts);
    }
    
    if (action === "mcp") {
        return buildSuccessResponse(RESOURCE_INDEX.mcp_paths);
    }
    
    return buildErrorResponse("unknown_action", "支持: overview|presets|plugins|scripts|mcp");
}

var _args = (typeof args !== "undefined") ? args : {};
textFXResourceIndex(_args);
