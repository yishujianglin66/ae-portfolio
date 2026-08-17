// ============================================================
// render_utils.jsx - AE 渲染工具模块
// 供 ae_auto_render_orchestrator.py 通过 Bridge 调用
// ============================================================
// 功能：
//   1. 渲染队列配置辅助
//   2. 输出模块管理
//   3. 渲染设置管理
//   4. 渲染进度查询
//   5. 渲染后验证（输出文件存在性/完整性）
//   6. 格式与编码器探测
// ============================================================

(function () {
    var RENDER_UTILS_VERSION = "1.0.0";

    // ============================================================
    // 公共 API
    // ============================================================

    /**
     * 获取所有可用的 Output Module 模板
     * @returns {Array<{name: string, isDefault: boolean}>}
     */
    function getAvailableOMTemplates() {
        var templates = [];
        try {
            var om = app.project.renderQueue.items.add(
                app.project.activeItem || app.project.item(1)
            ).outputModule(1);
            if (om) {
                // 遍历常用模板名（ExtendScript 无直接 API 列出所有模板）
                var candidates = [
                    "Lossless", "Lossless with Alpha", "Draft Movie",
                    "HDTV 1080p 29.97", "HDTV 1080p 25", "HDTV 1080p 24",
                    "HDTV 1080p 23.976", "HDTV 720p 29.97", "HDTV 720p 25",
                    "NTSC DV", "PAL DV", "NTSC DV Widescreen", "PAL DV Widescreen",
                    "Multi-Machine Sequence", "Photoshop 32-bit",
                    "AIFF 48kHz", "AIFF 44.1kHz", "WAV 48kHz", "WAV 44.1kHz",
                    "JPEG Sequence", "PNG Sequence", "Photoshop Sequence",
                    "TIFF Sequence", "Targa Sequence",
                ];
                for (var i = 0; i < candidates.length; i++) {
                    try {
                        om.applyTemplate(candidates[i]);
                        templates.push({ name: candidates[i], available: true });
                    } catch (e) {
                        templates.push({ name: candidates[i], available: false });
                    }
                }
                om.remove();
            }
        } catch (e) {
            return { error: e.toString() };
        }
        return templates;
    }

    /**
     * 获取可用的渲染设置模板
     * @returns {Array<{name: string, available: boolean}>}
     */
    function getAvailableRSTemplates() {
        var templates = [];
        var candidates = [
            "Best Settings", "Draft Settings", "DV Settings",
            "Multi-Machine Settings", "Current Settings",
        ];
        try {
            var rqItem = app.project.renderQueue.items.add(
                app.project.activeItem || app.project.item(1)
            );
            for (var i = 0; i < candidates.length; i++) {
                try {
                    rqItem.applyTemplate(candidates[i]);
                    templates.push({ name: candidates[i], available: true });
                } catch (e) {
                    templates.push({ name: candidates[i], available: false });
                }
            }
            rqItem.remove();
        } catch (e) {
            return { error: e.toString() };
        }
        return templates;
    }

    /**
     * 配置完整渲染队列
     * @param {Object} config
     *   compName         : string  - 合成名称
     *   outputPath       : string  - 输出文件完整路径
     *   omTemplate       : string  - OM 模板名 (默认 "Lossless")
     *   rsTemplate       : string  - RS 模板名 (默认 "Best Settings")
     *   resolution       : number  - 分辨率 (100=Full, 50=Half)
     *   startFrame       : number  - 起始帧 (默认 0)
     *   endFrame         : number  - 结束帧 (默认合成末尾)
     *   skipExisting     : bool    - 跳过已存在文件
     * @returns {Object} result
     */
    function configureRenderQueue(config) {
        config = config || {};
        var compName = config.compName || "";
        var outputPath = config.outputPath || (Folder.desktop.fsName + "/_ae_render_output.avi");
        var omTemplate = config.omTemplate || "Lossless";
        var rsTemplate = config.rsTemplate || "Best Settings";
        var resolution = config.resolution || 100;
        var startFrame = config.startFrame || 0;
        var endFrame = config.endFrame;
        var skipExisting = config.skipExisting || false;

        var result = {
            status: "ok",
            command: "configureRenderQueue",
            errors: [],
            warnings: [],
            setup: {},
        };

        // 查找合成
        var comp = null;
        if (compName) {
            for (var i = 1; i <= app.project.numItems; i++) {
                var it = app.project.item(i);
                if (it && it instanceof CompItem && it.name === compName) {
                    comp = it;
                    break;
                }
            }
        }
        if (!comp && app.project.activeItem instanceof CompItem) {
            comp = app.project.activeItem;
            compName = comp.name;
        }
        if (!comp) {
            result.status = "error";
            result.error = "No compositing found. compName=" + compName;
            return result;
        }

        try {
            // 清空现有渲染队列
            var rq = app.project.renderQueue;
            while (rq.numItems > 0) {
                rq.item(rq.numItems).remove();
            }

            // 添加合成到渲染队列
            var rqItem = rq.items.add(comp);
            if (!rqItem) {
                result.status = "error";
                result.error = "Failed to add comp to render queue";
                return result;
            }

            result.setup.compName = comp.name;
            result.setup.compWidth = comp.width;
            result.setup.compHeight = comp.height;
            result.setup.compDuration = comp.duration;
            result.setup.compFrameRate = comp.frameRate;

            // --- 配置输出模块 ---
            var om = rqItem.outputModule(1);
            if (om) {
                // 设置输出文件
                var outFile = new File(outputPath);
                // 确保目录存在
                var outDir = outFile.parent;
                if (!outDir.exists) {
                    outDir.create();
                }

                om.file = outFile;

                // 应用输出模块模板
                try {
                    om.applyTemplate(omTemplate);
                    result.setup.omTemplate = omTemplate;
                    result.setup.omTemplateApplied = true;
                } catch (eOM) {
                    result.warnings.push("OM template '" + omTemplate + "' failed: " + eOM.toString());
                    result.setup.omTemplate = "(default)";
                    result.setup.omTemplateApplied = false;
                }

                // 输出模块详情
                result.setup.outputFilePath = om.file.fsName;
                result.setup.outputFileExists = om.file.exists;
                result.setup.includeSourceXMP = om.includeSourceXMP;
                result.setup.includeProjectLink = om.includeProjectLink;
                result.setup.includeCryptedMetadata = om.includeCryptedMetadata;
                result.setup.audioOutputEnabled = om.audioEnabled;
            } else {
                result.errors.push("outputModule(1) returned null");
            }

            // --- 配置渲染设置 ---
            try {
                rqItem.applyTemplate(rsTemplate);
                result.setup.rsTemplate = rsTemplate;
                result.setup.rsTemplateApplied = true;
            } catch (eRS) {
                result.warnings.push("RS template '" + rsTemplate + "' failed: " + eRS.toString());
                result.setup.rsTemplate = "(default)";
                result.setup.rsTemplateApplied = false;
            }

            // 手动设置渲染分辨率
            try {
                var rs = rqItem.getSettings(GetSettingsFormat.STRING_SETTABLE);
                rs.resolution = resolution;
                rqItem.setSettings(rs, GetSettingsFormat.STRING_SETTABLE);
                result.setup.resolution = resolution;
            } catch (eRes) {
                result.errors.push("Resolution setting failed: " + eRes.toString());
            }

            // 设置帧范围
            if (startFrame !== undefined && startFrame > 0) {
                try {
                    rqItem.timeSpanStart = startFrame / comp.frameRate;
                    result.setup.startFrame = startFrame;
                } catch (eF1) {
                    result.errors.push("Start frame setting failed: " + eF1.toString());
                }
            }
            if (endFrame !== undefined && endFrame > 0) {
                try {
                    rqItem.timeSpanDuration = (endFrame - startFrame) / comp.frameRate;
                    result.setup.endFrame = endFrame;
                } catch (eF2) {
                    result.errors.push("End frame setting failed: " + eF2.toString());
                }
            }

            // 跳过现有
            if (skipExisting) {
                rqItem.skipFrames = 0; // 0 = no skip
            }

            // 最终队列状态
            result.setup.queueItemStatus = rqItem.status;
            result.setup.queueItemNumOutputModules = rqItem.numOutputModules;
            result.setup.queueItemsTotal = rq.numItems;

        } catch (e) {
            result.status = "error";
            result.error = e.toString();
            result.stack = e.stack || "";
        }

        return result;
    }

    /**
     * 查询渲染队列状态
     * @returns {Object}
     */
    function getRenderQueueStatus() {
        var info = {
            numItems: 0,
            rendering: false,
            items: [],
            canQueueInAME: false,
        };

        try {
            var rq = app.project.renderQueue;
            info.numItems = rq.numItems;
            info.rendering = rq.rendering;

            for (var i = 1; i <= rq.numItems; i++) {
                var item = rq.item(i);
                var itemInfo = {
                    index: i,
                    compName: item.comp ? item.comp.name : "(none)",
                    status: item.status, // RQItemStatus enum
                    rendered: item.rendered,
                    elapsedSeconds: item.elapsedSeconds,
                    timeSpanStart: item.timeSpanStart,
                    timeSpanDuration: item.timeSpanDuration,
                    skipFrames: item.skipFrames,
                };

                // 输出模块信息
                var om = item.outputModule(1);
                if (om) {
                    itemInfo.outputFile = om.file ? om.file.fsName : "";
                    itemInfo.outputFileExists = om.file ? om.file.exists : false;
                    itemInfo.outputFileSize = (om.file && om.file.exists)
                        ? om.file.length
                        : 0;
                }

                // 渲染设置信息
                try {
                    var rs = item.getSettings(GetSettingsFormat.STRING);
                    itemInfo.renderSettings = rs;
                } catch (e) {}

                info.items.push(itemInfo);
            }
        } catch (e) {
            info.error = e.toString();
        }

        return info;
    }

    /**
     * 清理渲染队列
     * @returns {Object}
     */
    function clearRenderQueue() {
        try {
            var rq = app.project.renderQueue;
            var count = rq.numItems;
            while (rq.numItems > 0) {
                rq.item(rq.numItems).remove();
            }
            return { status: "ok", removed: count };
        } catch (e) {
            return { status: "error", error: e.toString() };
        }
    }

    /**
     * 获取可用的视频编码器列表（通过输出模块设置探测）
     * @returns {Array<string>}
     */
    function getAvailableFormats() {
        var formats = [];
        try {
            // 检测当前系统可写的输出格式
            var testFile = new File(Folder.temp.fsName + "/_ae_format_test.avi");
            var om = app.project.renderQueue.items.add(
                app.project.activeItem || app.project.item(1)
            ).outputModule(1);

            var formatTests = [
                { ext: ".avi", format: "AVI (AVI)" },
                { ext: ".mov", format: "QuickTime (MOV)" },
                { ext: ".mp4", format: "H.264 (MP4)" },
                { ext: ".jpg", format: "JPEG Sequence" },
                { ext: ".png", format: "PNG Sequence" },
                { ext: ".psd", format: "Photoshop Sequence" },
                { ext: ".tif", format: "TIFF Sequence" },
                { ext: ".tga", format: "Targa Sequence" },
                { ext: ".bmp", format: "BMP Sequence" },
                { ext: ".wav", format: "WAV 48kHz" },
                { ext: ".aiff", format: "AIFF 48kHz" },
            ];

            for (var i = 0; i < formatTests.length; i++) {
                try {
                    om.file = new File(Folder.temp.fsName + "/_ae_test" + formatTests[i].ext);
                    formats.push(formatTests[i].format);
                } catch (e) {}
            }

            // 清理
            om.remove();
            app.project.renderQueue.item(1).remove();
        } catch (e) {
            return { error: e.toString() };
        }
        return formats;
    }

    /**
     * 验证输出文件完整性
     * @param {string} filePath - 输出文件路径
     * @param {number} expectedMinSize - 预期最小文件大小（字节）
     * @returns {Object}
     */
    function verifyOutputFile(filePath, expectedMinSize) {
        var result = {
            path: filePath,
            exists: false,
            size: 0,
            sizeStr: "",
            valid: false,
            error: "",
        };

        try {
            var f = new File(filePath);
            result.exists = f.exists;

            if (f.exists) {
                result.size = f.length;
                result.sizeStr = formatFileSize(f.length);
                result.created = f.created ? f.created.toString() : "";
                result.modified = f.modified ? f.modified.toString() : "";

                if (expectedMinSize && f.length < expectedMinSize) {
                    result.valid = false;
                    result.error = "File too small: " + f.length + " bytes (expected >= " + expectedMinSize + ")";
                } else {
                    result.valid = f.length > 0;
                }
            } else {
                result.error = "File does not exist";
            }
        } catch (e) {
            result.error = e.toString();
        }

        return result;
    }

    /**
     * 友好的文件大小格式化
     */
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
    }

    /**
     * 探测当前可用的所有效果（用于插件检测）
     * @returns {Array<{matchName: string, displayName: string, category: string}>}
     */
    function probeAllEffects() {
        var effects = [];
        var knownMatchNames = [
            // 内置效果
            "ADBE Gaussian Blur 2", "ADBE Box Blur 2", "ADBE Directional Blur",
            "ADBE Radial Blur", "ADBE Sharpen", "ADBE Unsharp Mask2",
            "ADBE Curves", "ADBE Levels", "ADBE Brightness & Contrast 2",
            "ADBE Hue/Saturation", "ADBE Color Balance", "ADBE Color Balance (HLS)",
            "ADBE Tint", "ADBE Tritone", "ADBE Fill", "ADBE Glow2",
            "ADBE Drop Shadow", "ADBE Roughen Edges", "ADBE Gradient Ramp",
            "ADBE 4-Color Gradient", "ADBE Ramp", "ADBE CC Composite",
            "ADBE Noise", "ADBE Fractal Noise", "ADBE Turbulent Noise",
            "ADBE Cell Pattern", "ADBE Checkerboard", "ADBE Circle",
            "ADBE Ellipse", "ADBE Grid", "ADBE Lens Flare", "ADBE Lightning",
            "ADBE Radio Waves", "ADBE Ramp", "ADBE Stroke", "ADBE Vegas",
            "ADBE Write-on", "ADBE Transform", "ADBE Corner Pin",
            "ADBE Displacement Map", "ADBE Time Displacement", "ADBE Timewarp",
            "ADBE Echo", "ADBE CC Force Motion Blur", "ADBE Motion Tile",
            // 常用第三方插件
            "CC Radial Fast Blur", "CC Radial Blur", "CC Vector Blur",
            "CC Cross Blur", "CC Color Offset", "CC Toner",
            "CC Burn Film", "CC Glass", "CC Lens", "CC Page Turn",
            "CC Sphere", "CC Cylinder", "CC Light Sweep", "CC Light Rays",
            "CC Light Burst 2.5", "CC Starburst", "CC Snowfall",
            "CC Rainfall", "CC Particle Systems II", "CC Particle World",
            "CC Pixel Polly", "CC Scatterize", "CC Star Burst",
        ];

        try {
            var comp = app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                // 创建一个临时合成用于探测
                for (var j = 1; j <= app.project.numItems; j++) {
                    var cit = app.project.item(j);
                    if (cit && cit instanceof CompItem) {
                        comp = cit;
                        break;
                    }
                }
            }
            if (!comp) return { error: "No comp available for effect probe" };

            var tmpLayer = comp.layers.addSolid([0.5, 0.5, 0.5], "__effect_probe__", 100, 100, 1.0);

            for (var k = 0; k < knownMatchNames.length; k++) {
                try {
                    var eff = tmpLayer.Effects.addProperty(knownMatchNames[k]);
                    if (eff) {
                        effects.push({
                            matchName: eff.matchName,
                            displayName: eff.name,
                            category: eff.parentProperty ? "effects" : "unknown",
                            available: true,
                        });
                        eff.remove();
                    }
                } catch (e) {
                    effects.push({
                        matchName: knownMatchNames[k],
                        available: false,
                        error: e.toString().substring(0, 80),
                    });
                }
            }

            tmpLayer.remove();
        } catch (e) {
            return { error: e.toString() };
        }

        return effects;
    }

    // ============================================================
    // 导出到全局作用域
    // ============================================================

    $.global.RenderUtils = {
        version: RENDER_UTILS_VERSION,
        getAvailableOMTemplates: getAvailableOMTemplates,
        getAvailableRSTemplates: getAvailableRSTemplates,
        configureRenderQueue: configureRenderQueue,
        getRenderQueueStatus: getRenderQueueStatus,
        clearRenderQueue: clearRenderQueue,
        getAvailableFormats: getAvailableFormats,
        verifyOutputFile: verifyOutputFile,
        probeAllEffects: probeAllEffects,
        formatFileSize: formatFileSize,
    };

})();
