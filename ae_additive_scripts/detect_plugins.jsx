// ============================================================
// AE 插件/效果依赖自动检测脚本
// 用于在 AE 环境中检测所有已知插件的可用性
// 输出: $.global.__aeAdditiveResult (JSON)
// ============================================================

(function() {
    var report = {
        status: "complete",
        timestamp: new Date().toISOString(),
        aeVersion: "",
        detected: {},
        missing: {},
        errors: [],
        summary: { total: 0, available: 0, unavailable: 0 }
    };

    try {
        report.aeVersion = app.version || "unknown";
    } catch(e) {
        report.aeVersion = "unavailable";
    }

    // ----- 插件清单 -------------------------------------------
    // category: "builtin" | "cycore" | "third-party" | "open-source"
    var plugins = [
        // === Adobe 内置效果 ===
        { category: "builtin",      name: "Lens Flare",          matchName: "ADBE Lens Flare",              desc: "镜头光晕" },
        { category: "builtin",      name: "Glow",                matchName: "ADBE Glo2",                    desc: "发光效果" },
        { category: "builtin",      name: "Gaussian Blur",       matchName: "ADBE Gaussian Blur 2",         desc: "高斯模糊" },
        { category: "builtin",      name: "Color Balance",       matchName: "ADBE Color Balance",           desc: "色彩平衡" },
        { category: "builtin",      name: "Curves",              matchName: "ADBE Curves",                  desc: "曲线调色" },
        { category: "builtin",      name: "Levels",              matchName: "ADBE Levels (Individual Controls)", desc: "色阶" },
        { category: "builtin",      name: "Tritone",             matchName: "ADBE Tritone",                 desc: "三色调" },
        { category: "builtin",      name: "Fill",                matchName: "ADBE Fill",                    desc: "填充" },
        { category: "builtin",      name: "Stroke",              matchName: "ADBE Stroke",                  desc: "描边" },
        { category: "builtin",      name: "Drop Shadow",         matchName: "ADBE Drop Shadow",             desc: "投影" },
        { category: "builtin",      name: "Camera Lens Blur",    matchName: "ADBE Camera Lens Blur",        desc: "相机镜头模糊" },
        { category: "builtin",      name: "Fractal Noise",       matchName: "ADBE Fractal Noise",           desc: "分形噪波" },
        { category: "builtin",      name: "Hue/Saturation",      matchName: "ADBE HUE SATURATION",          desc: "色相饱和度" },
        { category: "builtin",      name: "Lumetri Color",       matchName: "ADBE Lumetri",                 desc: "Lumetri 调色" },
        { category: "builtin",      name: "Exposure",            matchName: "ADBE Exposure2",               desc: "曝光度" },
        { category: "builtin",      name: "Brightness & Contrast", matchName: "ADBE Brightness & Contrast 2", desc: "亮度对比度" },
        { category: "builtin",      name: "Photo Filter",        matchName: "ADBE PhotoFilterPS",           desc: "照片滤镜" },
        { category: "builtin",      name: "Mosaic",              matchName: "ADBE Mosaic",                  desc: "马赛克" },
        { category: "builtin",      name: "Invert",              matchName: "ADBE Invert",                  desc: "反转" },
        { category: "builtin",      name: "Noise",               matchName: "ADBE Noise2",                  desc: "噪点" },
        { category: "builtin",      name: "Ramp",                matchName: "ADBE Ramp",                    desc: "渐变" },
        { category: "builtin",      name: "Turbulent Displace",  matchName: "ADBE Turbulent Displace",      desc: "湍流置换" },
        { category: "builtin",      name: "Motion Blur",         matchName: "ADBE Motion Blur",             desc: "运动模糊" },
        { category: "builtin",      name: "Audio Spectrum",      matchName: "ADBE AudSpect",                desc: "音频频谱" },
        { category: "builtin",      name: "CC Particle World",   matchName: "CC Particle World",            desc: "CC 粒子世界" },
        { category: "builtin",      name: "CC Bend It",          matchName: "ADBE CC Bend It",              desc: "CC 弯曲" },

        // === 第三方商业插件 ===
        { category: "third-party",  name: "Saber (VC)",           matchName: "VC SaberFX",                  desc: "光剑/能量光束 [Video Copilot]" },
        { category: "third-party",  name: "Optical Flares (VC)",  matchName: "VC Optical Flares",           desc: "专业镜头光斑 [Video Copilot]" },
        { category: "third-party",  name: "Twixtor (REVisionFX)", matchName: "REVisionFX Twixtor",          desc: "超级慢动作 [RE:Vision FX]" },
        { category: "third-party",  name: "Magic Bullet Looks",   matchName: "Magic Bullet Looks",          desc: "电影级调色 [Red Giant]" },
        { category: "third-party",  name: "BCC Lens Flare",       matchName: "BCC Lens Flare",              desc: "BCC 镜头光斑 [Boris FX]" },
        { category: "third-party",  name: "Sapphire LensFlare",   matchName: "S_LensFlare",                 desc: "高品质光晕 [Boris FX Sapphire]" },
        { category: "third-party",  name: "Universe VHS (RG)",    matchName: "Universe VHS",                desc: "VHS/复古效果 [Red Giant]" },
        { category: "third-party",  name: "Particular (Trapcode)","matchName": "TC Particular",              desc: "专业3D粒子 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode Form",        matchName: "TC Form",                     desc: "3D粒子网格 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode Mir",         matchName: "TC Mir",                      desc: "3D地形生成 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode Shine",       matchName: "TC Shine",                    desc: "体积光 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode 3D Stroke",   matchName: "TC 3D Stroke",                desc: "3D 描边 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode Starglow",    matchName: "TC Starglow",                 desc: "星光效果 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode Sound Keys",  matchName: "TC Sound Keys",               desc: "音频驱动 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Trapcode Echospace",   matchName: "TC Echospace",                desc: "3D克隆 [Red Giant Trapcode]" },
        { category: "third-party",  name: "Element 3D (VC)",      matchName: "Element",                     desc: "3D对象渲染 [Video Copilot]" },
        { category: "third-party",  name: "Deep Glow (PluginEverything)", matchName: "Deep Glow",           desc: "物理精确发光 [Plugin Everything]" },

        // === 开源/免费插件 ===
        { category: "open-source",  name: "F-s CameraShake",     matchName: "F-s CameraShake",             desc: "摄像机抖动 [F-s-Plugins]" },
        { category: "open-source",  name: "F-s InnerFlare",      matchName: "F-s InnerFlare",              desc: "内部光晕 [F-s-Plugins]" },
        { category: "open-source",  name: "F-s Lightning",       matchName: "F-s Lightning",               desc: "闪电生成 [F-s-Plugins]" },
        { category: "open-source",  name: "F-s Mosaic",          matchName: "F-s Mosaic",                  desc: "高级马赛克 [F-s-Plugins]" },
        { category: "open-source",  name: "F-s Grain",           matchName: "F-s Grain",                   desc: "胶片颗粒 [F-s-Plugins]" }
    ];

    // ----- 检测方法 -------------------------------------------
    function probePlugin(name, matchName) {
        var result = {
            name: name,
            matchName: matchName,
            available: false,
            error: null,
            method: "effect_add_property"
        };

        try {
            // 方法1：在当前合成中创建临时固态层并尝试添加效果
            if (app.project && app.project.activeItem && app.project.activeItem instanceof CompItem) {
                var comp = app.project.activeItem;
                var tempSolid = comp.layers.addSolid([0.5, 0.5, 0.5], "__plugin_probe__", comp.width, comp.height, 1.0, 0.5);
                try {
                    var fx = tempSolid.Effects.addProperty(matchName);
                    if (fx) {
                        result.available = true;
                    }
                    // 清理
                    tempSolid.remove();
                } catch(e) {
                    result.error = e.toString();
                    result.available = false;
                    // 清理失败也尝试移除
                    try { tempSolid.remove(); } catch(e2) {}
                }
            } else {
                // 方法2：无活跃合成，尝试创建临时合成
                result.method = "temp_comp_probe";
                var tempComp = app.project.items.addComp("__plugin_probe_comp__", 1920, 1080, 1, 1, 30);
                var tempSolid = tempComp.layers.addSolid([0.5, 0.5, 0.5], "__plugin_probe__", 1920, 1080, 1, 1);
                try {
                    var fx2 = tempSolid.Effects.addProperty(matchName);
                    if (fx2) {
                        result.available = true;
                    }
                } catch(e3) {
                    result.error = e3.toString();
                    result.available = false;
                }
                // 清理临时合成
                try { tempComp.remove(); } catch(e4) {}
            }
        } catch(outerErr) {
            result.error = "Probe setup failed: " + outerErr.toString();
            result.available = false;
        }

        return result;
    }

    // ----- 批量检测 -------------------------------------------
    var detectedList = [];
    var errors = [];

    for (var i = 0; i < plugins.length; i++) {
        var plugin = plugins[i];
        var probe = probePlugin(plugin.name, plugin.matchName);

        var key = plugin.name;
        report.detected[key] = {
            category: plugin.category,
            matchName: plugin.matchName,
            desc: plugin.desc,
            available: probe.available,
            error: probe.error || null,
            method: probe.method
        };

        if (probe.available) {
            report.summary.available++;
            detectedList.push(plugin.name);
        } else {
            report.summary.unavailable++;
            if (probe.error) {
                errors.push({ plugin: plugin.name, error: probe.error });
            }
        }
        report.summary.total++;
    }

    // ----- 额外检查：AE 安装路径和 PresetEffects 目录 ----------
    try {
        var aePath = Folder.appPackage ? Folder.appPackage.fsName : "unknown";
        report.aeInstallPath = aePath;

        var presetsPath = "";
        try {
            var appFolder = new Folder(Folder.appPackage.fsName);
            if (appFolder.exists) {
                presetsPath = appFolder.fsName + "/Presets";
            }
        } catch(e) {}
        report.aePresetsPath = presetsPath;

        // 检查 .ffx 预设数量
        try {
            var presetsFolder = new Folder(aePath + "/Presets");
            if (presetsFolder.exists) {
                var ffxCount = 0;
                var ffxFiles = presetsFolder.getFiles("*.ffx");
                // getFiles 可能返回大量文件
                report.ffxPresetCount = "checkable (Presets folder exists)";
            } else {
                report.ffxPresetCount = 0;
            }
        } catch(e) {
            report.ffxPresetCount = "error: " + e.toString();
        }

        // 检查 ScriptUI Panels (Bridge 文件存在性)
        try {
            var scriptUIPath = Folder.userData ? Folder.userData.fsName + "/Scripts/ScriptUI Panels" : "unknown";
            report.scriptUIPanelsPath = scriptUIPath;
            try {
                var panelFolder = new Folder(scriptUIPath);
                if (panelFolder.exists) {
                    var panelFiles = panelFolder.getFiles("*.jsx");
                    report.scriptUIPanels = [];
                    for (var pf = 0; pf < panelFiles.length && pf < 30; pf++) {
                        report.scriptUIPanels.push(panelFiles[pf].name);
                    }
                }
            } catch(e2) {
                report.scriptUIPanels = "inaccessible";
            }
        } catch(e3) {
            report.scriptUIPanelsPath = "error";
        }

    } catch(e) {
        errors.push({ plugin: "AE_PATHS", error: e.toString() });
    }

    report.errors = errors;
    report.detectedList = detectedList;

    // ----- 输出 -----------------------------------------------
    $.global.__aeAdditiveResult = JSON.stringify(report);
})();
