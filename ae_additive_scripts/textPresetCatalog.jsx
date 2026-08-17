// textPresetCatalog.jsx
// 内置预设目录调度器 - 直接调用 AE 300+ 内置 .ffx 文字动画预设
// 支持按名称/分类/关键词搜索并应用预设

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

// 预设根目录（AE 安装路径）
var PRESETS_ROOT = "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Presets";
var TEXT_PRESETS_DIR = PRESETS_ROOT + "/Text";
var GLITCH_PRESETS_DIR = PRESETS_ROOT + "/Glitch\u6548\u679c\u9884\u8bbe";

// 预设分类索引（完整 - 4998个预设）
var PRESET_CATEGORIES = {
    // === 文字动画 (300) ===
    "3d": "Text/3D Text",
    "animate_in": "Text/Animate In",
    "animate_out": "Text/Animate Out",
    "blurs": "Text/Blurs",
    "curves_spins": "Text/Curves and Spins",
    "expressions": "Text/Expressions",
    "fill_stroke": "Text/Fill and Stroke",
    "graphical": "Text/Graphical",
    "lights_optical": "Text/Lights and Optical",
    "mechanical": "Text/Mechanical",
    "misc": "Text/Miscellaneous",
    "multiline": "Text/Multi-Line",
    "counters": "Text/Number Counters",
    "organic": "Text/Organic",
    "paths": "Text/Paths",
    "rotation": "Text/Rotation",
    "scale": "Text/Scale",
    "tracking": "Text/Tracking",
    // === 特效类 ===
    "glitch": "Glitch\u6548\u679c\u9884\u8bbe",
    "holomatrix": "(Holomatrix)",
    "damage": "Digieffects Damage Presets AE",
    "toonit": "ToonItV2 Presets",
    // === 粒子/3D ===
    "particular": "Particular",
    "form": "Form",
    "trapcode_mir": "Trapcode Mir",
    "trapcode_mir3": "Trapcode Mir 3",
    "trapcode_tao": "Trapcode Tao",
    // === 色彩/调色 (1600+) ===
    "color_1200": "1200\u4e2a\u8272\u5f69\u9884\u8bbe",
    "color_275": "275\u4e2a\u8272\u5f69\u9884\u8bbe",
    "color_112": "\u53e4\u98ce\u8272\u5f69\u9884\u8bbe112\u4e2a",
    "color_70": "70\u79cd\u7535\u5f71\u7247\u8272\u5f69\u9884\u8bbe",
    "color_14": "\u5f71\u5b50\u7535\u5f71\u8272\u5f69\u9884\u8bbe14\u4e2a",
    "color_7": "7\u79cd\u7cbe\u54c1\u8272\u5f69",
    // === 转场 (650+) ===
    "transitions_600": "600\u4e2a\u8f6c\u573a\u7279\u6548\u9884\u8bbe",
    "trans_dissolves": "Transitions - Dissolves",
    "trans_movement": "Transitions - Movement",
    "trans_wipes": "Transitions - Wipes",
    // === 光效/特效 (1100+) ===
    "particles_898": "\u7c92\u5b50\u7279\u6548\u5b9e\u7528\u9884\u8bbe",
    "light_250": "\u5149\u6548\u7279\u6548",
    "glow_250": "\u53d1\u5149\u6548\u679c",
    "shine": "Shine",
    // === 背景/形状 ===
    "backgrounds": "Backgrounds",
    "shapes": "Shapes",
    "behaviors": "Behaviors",
    "synthetics": "Synthetics",
    // === 图像效果 ===
    "img_creative": "Image - Creative",
    "img_special": "Image - Special Effects",
    "img_utilities": "Image - Utilities",
    // === 其他 ===
    "legacy": "Legacy",
    "adobe_express": "Adobe Express",
    "ae_animation": "AE Animation Presets",
    "shadow_studio": "Shadow Studio 2",
    "ink_20": "20\u4e2a\u6821\u56ed\u5c0f\u6e05\u65b0\u6c34\u58a8\u98ce"
};

// 热门预设快速索引（名称 → 相对路径）
var POPULAR_PRESETS = {
    // 打字机
    "typewriter": "Text/Animate In/Word Processor In.ffx",
    // 故障
    "glitch_decoder": "Text/Miscellaneous/Glitchy Text Decoder.ffx",
    // 弹跳
    "bounce_in": "Text/Animate In/Bounce In.ffx",
    "scale_bounce": "Text/Mechanical/Scale Bounce.ffx",
    // 3D翻转
    "flip_3d_x": "Text/3D Text/3D Flip In Rotate X.ffx",
    "flip_3d_y": "Text/3D Text/3D Rotate in by Character.ffx",
    // 飞入
    "fly_in_chars": "Text/Graphical/Fly In By Characters.ffx",
    "fly_in_words": "Text/Graphical/Fly In By Words.ffx",
    // 波浪
    "ocean_tide": "Text/Organic/Ocean Tide.ffx",
    "ripple": "Text/Organic/Ripple In.ffx",
    // 缩放
    "scale_in": "Text/Scale/Scale In.ffx",
    "zoom_forward": "Text/Scale/Zoom Forward.ffx",
    // 旋转
    "spin_in": "Text/Rotation/Spin In.ffx",
    "whirlwind": "Text/Rotation/Whirlwind.ffx",
    // 数据流
    "data_stream": "Text/Graphical/Data Stream In.ffx",
    "encryption": "Text/Graphical/Encryption In.ffx",
    // 有机
    "wobble": "Text/Organic/Wobble In.ffx",
    "rubber": "Text/Organic/Rubber.ffx",
    // 追踪
    "tracking_expand": "Text/Tracking/Extend.ffx",
    "tracking_contract": "Text/Tracking/Contract.ffx",
    // 计数器
    "counter_timer": "Text/Number Counters/Timer Countdown Monospaced.ffx",
    "counter_percent": "Text/Number Counters/Percentage Counter Monospaced.ffx",
    // 路径
    "spiral_3d": "Text/3D Text/3D Spiral Down & Unfold.ffx",
    // 模糊
    "bad_reception": "Text/Mechanical/Bad Reception.ffx",
    // 霓虹/光学
    "superhero": "Text/Miscellaneous/Superhero In.ffx"
};

function textPresetCatalog(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "compName \u53c2\u6570\u5fc5\u586b");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "layerIndex \u53c2\u6570\u5fc5\u586b\u4e14\u5fc5\u987b\u4e3a\u6570\u5b57");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "\u5408\u6210\u672a\u627e\u5230: " + args.compName);
        }
        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {
            return buildError("E102", "\u56fe\u5c42\u7d22\u5f15\u65e0\u6548: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);
        var action = args.action || "apply"; // apply | list | search

        // === 列出分类 ===
        if (action === "list_categories") {
            var cats = [];
            for (var key in PRESET_CATEGORIES) {
                if (PRESET_CATEGORIES.hasOwnProperty(key)) {
                    cats.push({ id: key, path: PRESET_CATEGORIES[key] });
                }
            }
            return buildSuccess({ categories: cats, count: cats.length });
        }

        // === 列出热门预设 ===
        if (action === "list_popular") {
            var popular = [];
            for (var name in POPULAR_PRESETS) {
                if (POPULAR_PRESETS.hasOwnProperty(name)) {
                    popular.push({ name: name, path: POPULAR_PRESETS[name] });
                }
            }
            return buildSuccess({ presets: popular, count: popular.length });
        }

        // === 列出指定分类下的预设 ===
        if (action === "list") {
            var category = args.category || "animate_in";
            var catPath = PRESET_CATEGORIES[category];
            if (!catPath) {
                return buildError("E103", "\u672a\u77e5\u5206\u7c7b: " + category);
            }
            var dir = new Folder(PRESETS_ROOT + "/" + catPath);
            if (!dir.exists) {
                return buildError("E104", "\u9884\u8bbe\u76ee\u5f55\u4e0d\u5b58\u5728: " + dir.fsName);
            }
            var files = dir.getFiles("*.ffx");
            var presetList = [];
            for (var i = 0; i < files.length; i++) {
                presetList.push(files[i].name.replace(/\.ffx$/i, ""));
            }
            return buildSuccess({ category: category, presets: presetList, count: presetList.length });
        }

        // === 搜索预设 ===
        if (action === "search") {
            var keyword = (args.keyword || "").toLowerCase();
            if (!keyword) {
                return buildError("E105", "keyword \u53c2\u6570\u5fc5\u586b");
            }
            var results = [];
            // 搜索所有分类
            for (var catKey in PRESET_CATEGORIES) {
                if (!PRESET_CATEGORIES.hasOwnProperty(catKey)) continue;
                var searchDir = new Folder(PRESETS_ROOT + "/" + PRESET_CATEGORIES[catKey]);
                if (!searchDir.exists) continue;
                var searchFiles = searchDir.getFiles("*.ffx");
                for (var j = 0; j < searchFiles.length; j++) {
                    var fname = searchFiles[j].name.replace(/\.ffx$/i, "");
                    if (fname.toLowerCase().indexOf(keyword) >= 0) {
                        results.push({ name: fname, category: catKey, file: searchFiles[j].fsName });
                    }
                }
            }
            return buildSuccess({ keyword: keyword, results: results, count: results.length });
        }

        // === 应用预设 ===
        if (action === "apply") {
            var presetFile = null;

            // 方式1：通过热门名称
            if (args.presetName && POPULAR_PRESETS[args.presetName]) {
                presetFile = new File(PRESETS_ROOT + "/" + POPULAR_PRESETS[args.presetName]);
            }
            // 方式2：通过分类+名称
            else if (args.presetName && args.category) {
                var catDir = PRESET_CATEGORIES[args.category] || args.category;
                presetFile = new File(PRESETS_ROOT + "/" + catDir + "/" + args.presetName + ".ffx");
            }
            // 方式3：通过完整路径
            else if (args.presetPath) {
                presetFile = new File(args.presetPath);
            }
            // 方式4：通过名称在所有分类中搜索
            else if (args.presetName) {
                for (var ck in PRESET_CATEGORIES) {
                    if (!PRESET_CATEGORIES.hasOwnProperty(ck)) continue;
                    var tryFile = new File(PRESETS_ROOT + "/" + PRESET_CATEGORIES[ck] + "/" + args.presetName + ".ffx");
                    if (tryFile.exists) {
                        presetFile = tryFile;
                        break;
                    }
                }
            }

            if (!presetFile || !presetFile.exists) {
                return buildError("E106", "\u9884\u8bbe\u6587\u4ef6\u672a\u627e\u5230: " + (args.presetName || args.presetPath || "unknown"));
            }

            app.beginUndoGroup("Apply Text Preset: " + presetFile.name);
            layer.applyPreset(presetFile);
            app.endUndoGroup();

            return buildSuccess({
                applied: presetFile.name.replace(/\.ffx$/i, ""),
                layer: layer.name,
                layerIndex: args.layerIndex,
                comp: args.compName
            }, { message: "\u9884\u8bbe\u5e94\u7528\u6210\u529f" });
        }

        return buildError("E100", "\u672a\u77e5 action: " + action + "\u3002\u652f\u6301: apply|list|list_categories|list_popular|search");
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", error.toString());
    }
}
