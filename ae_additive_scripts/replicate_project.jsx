// ============================================================
// AE 工程实战复刻脚本 - 全自动重现已分析的 AE 项目结构
// 覆盖8大模块: 合成/图层/效果/文字/3D/追踪/表达式/渲染
// 每个操作独立 try/catch，错误不中断后续步骤
// 输出: $.global.__aeAdditiveResult (JSON 报告)
// ============================================================

(function() {
    var startTime = new Date().getTime();
    var report = {
        status: "running",
        timestamp: new Date().toISOString(),
        aeVersion: "",
        projectName: "AE-Knowledge-Vault-Replication",
        summary: { totalTests: 0, passed: 0, failed: 0, skipped: 0 },
        modules: {}
    };

    // ----- 工具函数 -------------------------------------------
    function now() { return new Date().toISOString(); }
    function elapsed(startMs) { return (new Date().getTime() - startMs) + "ms"; }

    function recordTest(module, testName, passed, detail) {
        if (!report.modules[module]) {
            report.modules[module] = {
                module: module,
                status: "running",
                tests: [],
                passed: 0, failed: 0, skipped: 0
            };
        }
        var mod = report.modules[module];
        var rec = {
            name: testName,
            status: passed ? "PASS" : "FAIL",
            detail: detail || (passed ? "ok" : "error"),
            time: now()
        };
        mod.tests.push(rec);
        report.summary.totalTests++;
        if (passed) { mod.passed++; report.summary.passed++; }
        else { mod.failed++; report.summary.failed++; }
        return rec;
    }

    function skipTest(module, testName, reason) {
        if (!report.modules[module]) {
            report.modules[module] = { module: module, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };
        }
        report.modules[module].tests.push({ name: testName, status: "SKIP", detail: reason, time: now() });
        report.modules[module].skipped++;
        report.summary.skipped++;
        report.summary.totalTests++;
    }

    try {
        report.aeVersion = app.version || "unknown";
    } catch(e) {
        report.aeVersion = "unavailable";
    }

    // ----- 保存项目中已存在的合成名，避免冲突 ---------------
    var existingCompNames = [];
    try {
        for (var ei = 1; ei <= app.project.numItems; ei++) {
            var item = app.project.item(ei);
            if (item && item instanceof CompItem) {
                existingCompNames.push(item.name);
            }
        }
    } catch(e) {}

    var COMP_PREFIX = "_REPL_";

    // =========================================================
    // 模块1: 合成管理 (Composition Management)
    // =========================================================
    (function() {
        var mod = "M1_Composition";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0, comps: {} };

        // 1.1 创建标准 HD 合成
        try {
            var compHD = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30);
            recordTest(mod, "Create_HD_1080p_30fps", true,
                "1920x1080 30fps 10s comp created: " + compHD.name);
            report.modules[mod].comps.hd1080p = { name: compHD.name, width: compHD.width, height: compHD.height, frameRate: compHD.frameRate };

            // 1.2 设置合成背景色
            try {
                compHD.bgColor = [0.05, 0.05, 0.1];
                recordTest(mod, "Set_Comp_BGColor", true, "bgColor set to dark navy");
            } catch(e) {
                recordTest(mod, "Set_Comp_BGColor", false, "bgColor error: " + e.toString());
            }

            // 1.3 修改合成时长
            try {
                compHD.duration = 15;
                recordTest(mod, "Set_Comp_Duration", true, "duration extended to 15s");
            } catch(e) {
                recordTest(mod, "Set_Comp_Duration", false, "duration error: " + e.toString());
            }

        } catch(e) {
            recordTest(mod, "Create_HD_1080p_30fps", false, "Failed to create comp: " + e.toString());
        }

        // 1.4 创建竖屏合成
        try {
            var compVertical = app.project.items.addComp(COMP_PREFIX + "Vertical_1080x1920", 1080, 1920, 1, 10, 30);
            recordTest(mod, "Create_Vertical_1080x1920", true,
                "1080x1920 comp created: " + compVertical.name);
            report.modules[mod].comps.vertical = { name: compVertical.name, width: compVertical.width, height: compVertical.height };
        } catch(e) {
            recordTest(mod, "Create_Vertical_1080x1920", false, "Vertical comp error: " + e.toString());
        }

        // 1.5 创建方形合成 (1:1)
        try {
            var compSquare = app.project.items.addComp(COMP_PREFIX + "Square_1080x1080", 1080, 1080, 1, 5, 30);
            recordTest(mod, "Create_Square_1080x1080", true, "Square comp created: " + compSquare.name);
            report.modules[mod].comps.square = { name: compSquare.name };
        } catch(e) {
            recordTest(mod, "Create_Square_1080x1080", false, "Square comp error: " + e.toString());
        }

        // 1.6 创建高帧率合成 (60fps)
        try {
            var comp60fps = app.project.items.addComp(COMP_PREFIX + "HD_60fps", 1920, 1080, 1, 5, 60);
            recordTest(mod, "Create_HD_60fps", true, "60fps comp created: " + comp60fps.name);
            report.modules[mod].comps.hd60fps = { name: comp60fps.name, frameRate: comp60fps.frameRate };
        } catch(e) {
            recordTest(mod, "Create_HD_60fps", false, "60fps comp error: " + e.toString());
        }

        // 1.7 通过名称查找合成
        try {
            var found = null;
            for (var fi = 1; fi <= app.project.numItems; fi++) {
                var fiItem = app.project.item(fi);
                if (fiItem && fiItem instanceof CompItem && fiItem.name === COMP_PREFIX + "HD_1080p") {
                    found = fiItem;
                    break;
                }
            }
            recordTest(mod, "Find_Comp_By_Name", found !== null,
                found ? "Found comp: " + found.name : "Comp not found by name");
        } catch(e) {
            recordTest(mod, "Find_Comp_By_Name", false, "Find error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块2: 图层系统 (Layer System)
    // =========================================================
    (function() {
        var mod = "M2_Layers";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        if (!comp) {
            try {
                comp = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30);
            } catch(e) {
                recordTest(mod, "EnsureComp", false, "Cannot find/create base comp: " + e.toString());
                report.modules[mod].status = "FAIL";
                return;
            }
        }

        // 2.1 创建固态层
        try {
            var solid = comp.layers.addSolid([0.2, 0.3, 0.8], "Solid_Blue", 1920, 1080, 1, comp.duration);
            recordTest(mod, "Add_Solid_Layer", solid !== null, "Solid layer created: " + solid.name);
        } catch(e) {
            recordTest(mod, "Add_Solid_Layer", false, "Solid error: " + e.toString());
        }

        // 2.2 创建文字层
        try {
            var textLayer = comp.layers.addText("AE-Knowledge-Vault");
            recordTest(mod, "Add_Text_Layer", textLayer !== null && textLayer instanceof TextLayer,
                "Text layer: " + (textLayer instanceof TextLayer ? "is TextLayer ✓" : "NOT TextLayer ✗"));
        } catch(e) {
            recordTest(mod, "Add_Text_Layer", false, "Text layer error: " + e.toString());
        }

        // 2.3 创建形状图层
        try {
            var shape = comp.layers.addShape();
            recordTest(mod, "Add_Shape_Layer", shape !== null && shape instanceof ShapeLayer,
                "Shape layer: " + (shape instanceof ShapeLayer ? "is ShapeLayer ✓" : "NOT ShapeLayer ✗"));
        } catch(e) {
            recordTest(mod, "Add_Shape_Layer", false, "Shape layer error: " + e.toString());
        }

        // 2.4 创建空对象
        try {
            var nullLayer = comp.layers.addNull(comp.duration);
            recordTest(mod, "Add_Null_Layer", nullLayer !== null,
                "Null layer created: " + (nullLayer ? nullLayer.name : "null"));
        } catch(e) {
            recordTest(mod, "Add_Null_Layer", false, "Null layer error: " + e.toString());
        }

        // 2.5 创建调整图层
        try {
            var adjLayer = comp.layers.addSolid([1, 1, 1], "Adjustment_Layer", comp.width, comp.height, 1, comp.duration);
            if (adjLayer) {
                adjLayer.adjustmentLayer = true;
                recordTest(mod, "Create_Adjustment_Layer", adjLayer.adjustmentLayer === true,
                    "Adjustment layer: adjustmentLayer=" + adjLayer.adjustmentLayer);
            }
        } catch(e) {
            recordTest(mod, "Create_Adjustment_Layer", false, "Adj layer error: " + e.toString());
        }

        // 2.6 图层属性操作 - 位置
        try {
            var targetLayer = comp.layer(1);
            targetLayer.property("Position").setValue([960, 540]);
            recordTest(mod, "Layer_Position_Set", true, "Position set to [960, 540]");
        } catch(e) {
            recordTest(mod, "Layer_Position_Set", false, "Position error: " + e.toString());
        }

        // 2.7 图层属性操作 - 缩放
        try {
            var targetLayer = comp.layer(1);
            targetLayer.property("Scale").setValue([100, 100]);
            recordTest(mod, "Layer_Scale_Set", true, "Scale set to [100, 100]");
        } catch(e) {
            recordTest(mod, "Layer_Scale_Set", false, "Scale error: " + e.toString());
        }

        // 2.8 图层属性操作 - 旋转
        try {
            var targetLayer = comp.layer(1);
            targetLayer.property("Rotation").setValue(0);
            recordTest(mod, "Layer_Rotation_Set", true, "Rotation set to 0");
        } catch(e) {
            recordTest(mod, "Layer_Rotation_Set", false, "Rotation error: " + e.toString());
        }

        // 2.9 图层属性操作 - 不透明度
        try {
            var targetLayer = comp.layer(1);
            targetLayer.property("Opacity").setValue(100);
            recordTest(mod, "Layer_Opacity_Set", true, "Opacity set to 100");
        } catch(e) {
            recordTest(mod, "Layer_Opacity_Set", false, "Opacity error: " + e.toString());
        }

        // 2.10 图层启用/禁用
        try {
            var targetLayer = comp.layer(1);
            targetLayer.enabled = true;
            recordTest(mod, "Layer_Enable", targetLayer.enabled === true, "Layer enabled: " + targetLayer.enabled);
        } catch(e) {
            recordTest(mod, "Layer_Enable", false, "Enable error: " + e.toString());
        }

        // 2.11 图层锁定/解锁
        try {
            var targetLayer = comp.layer(1);
            targetLayer.locked = false;
            recordTest(mod, "Layer_Unlock", targetLayer.locked === false, "Layer locked: " + targetLayer.locked);
        } catch(e) {
            recordTest(mod, "Layer_Unlock", false, "Lock error: " + e.toString());
        }

        // 2.12 图层入点/出点
        try {
            var targetLayer = comp.layer(1);
            targetLayer.inPoint = 1;
            recordTest(mod, "Layer_InPoint_Set", true, "inPoint set to 1s");
        } catch(e) {
            recordTest(mod, "Layer_InPoint_Set", false, "inPoint error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块3: 内置效果系统 (Built-in Effects)
    // =========================================================
    (function() {
        var mod = "M3_Effects";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0, plugins: {} };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        if (!comp) {
            try { comp = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30); }
            catch(e2) { recordTest(mod, "EnsureComp", false, e2.toString()); report.modules[mod].status = "FAIL"; return; }
        }

        function tryAddEffect(layer, effectName, matchName, params) {
            try {
                var fx = layer.Effects.addProperty(matchName);
                if (!fx) {
                    return { success: false, error: "addProperty returned null", matchName: matchName };
                }
                // 尝试设置默认参数
                if (params) {
                    for (var pk in params) {
                        if (params.hasOwnProperty(pk)) {
                            try {
                                fx.property(pk).setValue(params[pk]);
                            } catch(pErr) {
                                // 参数设置失败不是致命错误
                            }
                        }
                    }
                }
                return { success: true, name: fx.name, matchName: fx.matchName };
            } catch(e) {
                return { success: false, error: e.toString(), matchName: matchName };
            }
        }

        // 在现有图层上依次添加效果
        var effectsLayer;
        try {
            effectsLayer = comp.layers.addSolid([0.5, 0.5, 0.5], "Effects_Test_Layer", comp.width, comp.height, 1, comp.duration);
        } catch(e) {}

        if (!effectsLayer) {
            recordTest(mod, "Create_Effects_Layer", false, "Cannot create test layer");
            report.modules[mod].status = "FAIL";
            return;
        }

        var builtInTests = [
            { name: "Lens_Flare",        match: "ADBE Lens Flare",              params: null },
            { name: "Glow",              match: "ADBE Glo2",                    params: null },
            { name: "Gaussian_Blur",     match: "ADBE Gaussian Blur 2",         params: {"Blurriness": 10} },
            { name: "Color_Balance",     match: "ADBE Color Balance",           params: null },
            { name: "Curves",            match: "ADBE Curves",                  params: null },
            { name: "Levels",            match: "ADBE Levels (Individual Controls)", params: null },
            { name: "Tritone",           match: "ADBE Tritone",                 params: null },
            { name: "Fill",              match: "ADBE Fill",                    params: null },
            { name: "Stroke",            match: "ADBE Stroke",                  params: null },
            { name: "Drop_Shadow",       match: "ADBE Drop Shadow",             params: null },
            { name: "Camera_Lens_Blur",  match: "ADBE Camera Lens Blur",        params: null },
            { name: "Fractal_Noise",     match: "ADBE Fractal Noise",           params: null },
            { name: "Hue_Saturation",    match: "ADBE HUE SATURATION",          params: null },
            { name: "Lumetri_Color",     match: "ADBE Lumetri",                 params: null },
            { name: "Brightness_Contrast", match: "ADBE Brightness & Contrast 2", params: null },
            { name: "Mosaic",            match: "ADBE Mosaic",                  params: null },
            { name: "Invert",            match: "ADBE Invert",                  params: null },
            { name: "Ramp",              match: "ADBE Ramp",                    params: null },
            { name: "Turbulent_Displace", match: "ADBE Turbulent Displace",     params: null },
            { name: "CC_Particle_World", match: "CC Particle World",            params: null },
            { name: "CC_Bend_It",        match: "ADBE CC Bend It",              params: null },
            { name: "Audio_Spectrum",    match: "ADBE AudSpect",                params: null },
            { name: "Exposure",          match: "ADBE Exposure2",               params: null }
        ];

        for (var bt = 0; bt < builtInTests.length; bt++) {
            var test = builtInTests[bt];
            var result = tryAddEffect(effectsLayer, test.name, test.match, test.params);
            if (result.success) {
                recordTest(mod, "Effect_" + test.name, true, "Added: " + result.name + " matchName=" + result.matchName);
                report.modules[mod].plugins[test.name] = { status: "AVAILABLE", matchName: result.matchName };
            } else {
                recordTest(mod, "Effect_" + test.name, false, "Failed: " + result.error);
                report.modules[mod].plugins[test.name] = { status: "MISSING", error: result.error };
            }
        }

        // 第三方插件探测（对已证实存在的 effectsLayer 更高效）
        var thirdPartyTests = [
            { name: "Saber_VC",          match: "VC SaberFX" },
            { name: "Optical_Flares_VC", match: "VC Optical Flares" },
            { name: "Twixtor_REVisionFX",match: "REVisionFX Twixtor" },
            { name: "Magic_Bullet_Looks",match: "Magic Bullet Looks" },
            { name: "BCC_Lens_Flare",    match: "BCC Lens Flare" },
            { name: "Sapphire_LensFlare",match: "S_LensFlare" },
            { name: "Universe_VHS_RG",   match: "Universe VHS" },
            { name: "Particular_TC",     match: "TC Particular" },
            { name: "Trapcode_Form",     match: "TC Form" },
            { name: "Trapcode_Mir",      match: "TC Mir" },
            { name: "Trapcode_Shine",    match: "TC Shine" },
            { name: "Trapcode_3DStroke", match: "TC 3D Stroke" },
            { name: "Element_3D",        match: "Element" },
            { name: "Deep_Glow_PE",      match: "Deep Glow" }
        ];

        for (var tp = 0; tp < thirdPartyTests.length; tp++) {
            var tptest = thirdPartyTests[tp];
            var tresult = tryAddEffect(effectsLayer, tptest.name, tptest.match, null);
            if (tresult.success) {
                recordTest(mod, "3rdParty_" + tptest.name, true, "INSTALLED: " + tptest.match);
                report.modules[mod].plugins[tptest.name] = { status: "AVAILABLE", matchName: tptest.match, type: "third-party" };
            } else {
                var skipMsg = "MISSING: " + tptest.match + " — 需要手动安装";
                report.modules[mod].plugins[tptest.name] = { status: "MISSING", error: tresult.error, type: "third-party", installHint: getInstallHint(tptest.name) };
                // 记录为跳过的测试（因为插件缺失是可预期的）
                skipTest(mod, "3rdParty_" + tptest.name, skipMsg);
            }
        }

        function getInstallHint(name) {
            var hints = {
                "Saber_VC":           "https://www.videocopilot.net/ → Products → Saber (免费)",
                "Optical_Flares_VC":  "https://www.videocopilot.net/ → Products → Optical Flares (付费 $124.95)",
                "Twixtor_REVisionFX": "https://revisionfx.com/products/twixtor/ (付费 $595)",
                "Magic_Bullet_Looks": "https://www.maxon.net/red-giant/magic-bullet-suite (付费 $199/年)",
                "BCC_Lens_Flare":     "https://borisfx.com/products/continuum/ (付费 $695/年)",
                "Sapphire_LensFlare": "https://borisfx.com/products/sapphire/ (付费 $1695/年)",
                "Universe_VHS_RG":    "https://www.maxon.net/red-giant/universe (付费 $199/年)",
                "Particular_TC":      "https://www.maxon.net/red-giant/trapcode-suite (付费 $399/年)",
                "Trapcode_Form":      "https://www.maxon.net/red-giant/trapcode-suite (付费 $399/年)",
                "Trapcode_Mir":       "https://www.maxon.net/red-giant/trapcode-suite (付费 $399/年)",
                "Trapcode_Shine":     "https://www.maxon.net/red-giant/trapcode-suite (付费 $399/年)",
                "Trapcode_3DStroke":  "https://www.maxon.net/red-giant/trapcode-suite (付费 $399/年)",
                "Element_3D":         "https://www.videocopilot.net/ → Products → Element 3D (付费 $199.95)",
                "Deep_Glow_PE":       "https://aescripts.com/deep-glow/ (付费 $39.99)"
            };
            return hints[name] || "请搜索插件名称获取安装信息";
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块4: 文字动画系统 (Text Animation)
    // =========================================================
    (function() {
        var mod = "M4_TextAnimation";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        if (!comp) {
            try { comp = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30); }
            catch(e2) { recordTest(mod, "EnsureComp", false, e2.toString()); report.modules[mod].status = "FAIL"; return; }
        }

        // 4.1 创建文字图层
        var textLayer;
        try {
            textLayer = comp.layers.addText("Test Animation");
            recordTest(mod, "Create_Text_Layer", textLayer !== null,
                "Text layer created: " + (textLayer ? textLayer.name : "null"));
        } catch(e) {
            recordTest(mod, "Create_Text_Layer", false, "Error: " + e.toString());
            report.modules[mod].status = "FAIL";
            return;
        }

        // 4.2 访问 TextDocument
        try {
            var textDoc = textLayer.property("Source Text").value;
            recordTest(mod, "Access_Source_Text", textDoc !== undefined && textDoc !== null,
                "Source Text accessible, font=" + (textDoc ? textDoc.font : "?"));
        } catch(e) {
            recordTest(mod, "Access_Source_Text", false, "Source Text error: " + e.toString());
        }

        // 4.3 设置 TextDocument 属性
        try {
            var textProp = textLayer.property("Source Text");
            var doc = textProp.value;
            doc.fontSize = 72;
            doc.resetCharStyle();
            doc.fontSize = 72;
            doc.justification = ParagraphJustification.CENTER_JUSTIFY;
            textProp.setValue(doc);
            recordTest(mod, "Set_FontSize_Justification", true, "fontSize=72, justification=CENTER");
        } catch(e) {
            recordTest(mod, "Set_FontSize_Justification", false, "TextDocument error: " + e.toString());
        }

        // 4.4 访问 Text Animators 组
        try {
            var textAnim = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            recordTest(mod, "Access_Text_Animators", textAnim !== null,
                "Text Animators group accessible");
        } catch(e) {
            recordTest(mod, "Access_Text_Animators", false, "Animators error: " + e.toString());
        }

        // 4.5 添加 Text Animator
        try {
            var animGroup = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            var animator = animGroup.addProperty("ADBE Text Animator");
            recordTest(mod, "Add_Text_Animator", animator !== null,
                "Text Animator added: " + (animator ? animator.name : "null"));
        } catch(e) {
            recordTest(mod, "Add_Text_Animator", false, "Add Animator error: " + e.toString());
        }

        // 4.6 添加 Range Selector
        try {
            var animGroup2 = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            var animator2 = animGroup2.addProperty("ADBE Text Animator");
            var selector = animator2.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            recordTest(mod, "Add_Range_Selector", selector !== null,
                "Range Selector added: " + (selector ? selector.name : "null"));
        } catch(e) {
            recordTest(mod, "Add_Range_Selector", false, "Selector error: " + e.toString());
        }

        // 4.7 设置 Animator Property - Opacity
        try {
            var animGroup3 = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            var animator3 = animGroup3.addProperty("ADBE Text Animator");
            animator3.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            var opacityProp = animator3.property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity");
            opacityProp.setValueAtTime(0, 0);
            opacityProp.setValueAtTime(2, 100);
            recordTest(mod, "Animator_Opacity_Keyframes", true,
                "Opacity keyframes: 0→100% over 2s");
        } catch(e) {
            recordTest(mod, "Animator_Opacity_Keyframes", false, "Opacity anim error: " + e.toString());
        }

        // 4.8 设置 Animator Property - Position (3D文字动画)
        try {
            var animGroup4 = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            var animator4 = animGroup4.addProperty("ADBE Text Animator");
            animator4.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            var posProp = animator4.property("ADBE Text Animator Properties").addProperty("ADBE Text Position 3D");
            posProp.setValueAtTime(0, [0, -100, 0]);
            posProp.setValueAtTime(2, [0, 0, 0]);
            recordTest(mod, "Animator_Position3D_Keyframes", true,
                "Position3D keyframes: slide up animation");
        } catch(e) {
            recordTest(mod, "Animator_Position3D_Keyframes", false, "Position3D error: " + e.toString());
        }

        // 4.9 设置 Animator Property - Scale
        try {
            var animGroup5 = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
            var animator5 = animGroup5.addProperty("ADBE Text Animator");
            var sel5 = animator5.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            sel5.property("ADBE Text Percent Start").setValueAtTime(0, 0);
            sel5.property("ADBE Text Percent Start").setValueAtTime(2, 100);
            var scaleProp = animator5.property("ADBE Text Animator Properties").addProperty("ADBE Text Scale 3D");
            scaleProp.setValueAtTime(0, [200, 200, 200]);
            scaleProp.setValueAtTime(2, [100, 100, 100]);
            recordTest(mod, "Animator_Scale_RangeSelector", true,
                "Scale + Range Selector: 200→100% over 2s");
        } catch(e) {
            recordTest(mod, "Animator_Scale_RangeSelector", false, "Scale/Selector error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块5: 3D 系统 (3D Features)
    // =========================================================
    (function() {
        var mod = "M5_3DSystem";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        if (!comp) {
            try { comp = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30); }
            catch(e2) { recordTest(mod, "EnsureComp", false, e2.toString()); report.modules[mod].status = "FAIL"; return; }
        }

        // 5.1 创建文字层并开启3D
        try {
            var t3d = comp.layers.addText("3D Text");
            t3d.threeDLayer = true;
            recordTest(mod, "Enable_3D_Layer", t3d.threeDLayer === true,
                "3D Layer enabled: threeDLayer=" + t3d.threeDLayer);
        } catch(e) {
            recordTest(mod, "Enable_3D_Layer", false, "3D Layer error: " + e.toString());
        }

        // 5.2 设置3D位置
        try {
            var target3d = comp.layer(comp.numLayers);
            if (target3d && target3d.threeDLayer) {
                target3d.property("Position").setValue([960, 540, 0]);
                recordTest(mod, "Set_3D_Position", true, "3D Position: [960, 540, 0]");
            } else {
                recordTest(mod, "Set_3D_Position", false, "No 3D layer found");
            }
        } catch(e) {
            recordTest(mod, "Set_3D_Position", false, "3D Pos error: " + e.toString());
        }

        // 5.3 添加摄像机
        try {
            var camera = comp.layers.addCamera("Test_Camera", [960, 540]);
            recordTest(mod, "Add_Camera", camera instanceof CameraLayer,
                "Camera added: " + (camera ? camera.name : "null") + " is CameraLayer=" + (camera instanceof CameraLayer));
        } catch(e) {
            recordTest(mod, "Add_Camera", false, "Camera error: " + e.toString());
        }

        // 5.4 添加灯光
        try {
            var light = comp.layers.addLight("Test_Light", [500, 500, -500]);
            recordTest(mod, "Add_Light", light instanceof LightLayer,
                "Light added: " + (light ? light.name : "null") + " is LightLayer=" + (light instanceof LightLayer));
        } catch(e) {
            recordTest(mod, "Add_Light", false, "Light error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块6: 表达式系统 (Expressions)
    // =========================================================
    (function() {
        var mod = "M6_Expressions";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        if (!comp) {
            try { comp = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30); }
            catch(e2) { recordTest(mod, "EnsureComp", false, e2.toString()); report.modules[mod].status = "FAIL"; return; }
        }

        var exprLayer;
        try {
            exprLayer = comp.layers.addSolid([0.3, 0.4, 0.7], "Expression_Test", comp.width, comp.height, 1, comp.duration);
        } catch(e) {
            recordTest(mod, "Create_Expr_Layer", false, e.toString());
            report.modules[mod].status = "FAIL";
            return;
        }

        // 6.1 canSetExpression 检查
        try {
            var posProp = exprLayer.property("Position");
            recordTest(mod, "CanSetExpression", posProp.canSetExpression === true,
                "Position.canSetExpression=" + posProp.canSetExpression);
        } catch(e) {
            recordTest(mod, "CanSetExpression", false, "canSetExpression error: " + e.toString());
        }

        // 6.2 wiggle 表达式
        try {
            var posProp = exprLayer.property("Position");
            posProp.expression = 'wiggle(2, 30)';
            recordTest(mod, "Expression_Wiggle", true,
                "wiggle(2,30) expression set");
        } catch(e) {
            recordTest(mod, "Expression_Wiggle", false, "wiggle error: " + e.toString());
        }

        // 6.3 loopOut 表达式
        try {
            var scaleProp = exprLayer.property("Scale");
            scaleProp.expression = 'loopOut("cycle")';
            recordTest(mod, "Expression_LoopOut", true,
                'loopOut("cycle") expression set');
        } catch(e) {
            recordTest(mod, "Expression_LoopOut", false, "loopOut error: " + e.toString());
        }

        // 6.4 time 表达式
        try {
            var rotProp = exprLayer.property("Rotation");
            rotProp.expression = 'time * 90';
            recordTest(mod, "Expression_Time", true,
                "time*90 expression set (rotation)");
        } catch(e) {
            recordTest(mod, "Expression_Time", false, "time error: " + e.toString());
        }

        // 6.5 sin 表达式
        try {
            var opacityProp = exprLayer.property("Opacity");
            opacityProp.expression = 'Math.sin(time * 3) * 50 + 50';
            recordTest(mod, "Expression_Sine", true,
                "sin oscillating opacity expression set");
        } catch(e) {
            recordTest(mod, "Expression_Sine", false, "sin error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块7: 跟踪系统 (Motion Tracking)
    // =========================================================
    (function() {
        var mod = "M7_Tracking";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        if (!comp) {
            try { comp = app.project.items.addComp(COMP_PREFIX + "HD_1080p", 1920, 1080, 1, 10, 30); }
            catch(e2) { recordTest(mod, "EnsureComp", false, e2.toString()); report.modules[mod].status = "FAIL"; return; }
        }

        var trackLayer;
        try {
            trackLayer = comp.layers.addSolid([0.4, 0.6, 0.3], "Tracker_Test", comp.width, comp.height, 1, comp.duration);
        } catch(e) {
            recordTest(mod, "Create_Track_Layer", false, e.toString());
            report.modules[mod].status = "FAIL";
            return;
        }

        // 7.1 检查 layer.property("Motion Trackers")
        try {
            var mt = trackLayer.property("ADBE Motion Trackers");
            recordTest(mod, "Access_MotionTrackers", mt !== null,
                "Motion Trackers accessible: " + (mt ? "yes" : "no"));
        } catch(e) {
            recordTest(mod, "Access_MotionTrackers", false, "MotionTrackers error: " + e.toString());
        }

        // 7.2 创建 Tracker
        try {
            var trackerAdded = false;
            try {
                var tracker = trackLayer.trackers.addTracker();
                trackerAdded = (tracker !== null && tracker !== undefined);
            } catch(e1) {
                // 新版AE可能使用不同API
                try {
                    var mt2 = trackLayer.property("ADBE Motion Trackers");
                    if (mt2) {
                        var tracker2 = mt2.addProperty("ADBE Tracker");
                        trackerAdded = (tracker2 !== null);
                    }
                } catch(e2) {}
            }
            recordTest(mod, "Add_Tracker", trackerAdded,
                "Tracker created: " + trackerAdded);
        } catch(e) {
            recordTest(mod, "Add_Tracker", false, "Tracker create error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 模块8: 渲染队列 (Render Queue)
    // =========================================================
    (function() {
        var mod = "M8_RenderQueue";
        report.modules[mod] = report.modules[mod] || { module: mod, status: "running", tests: [], passed: 0, failed: 0, skipped: 0 };

        var comp;
        try {
            for (var ci = 1; ci <= app.project.numItems; ci++) {
                var ciItem = app.project.item(ci);
                if (ciItem && ciItem instanceof CompItem && ciItem.name === COMP_PREFIX + "HD_1080p") {
                    comp = ciItem;
                    break;
                }
            }
        } catch(e) {}

        // 8.1 检查渲染队列存在性
        try {
            var rq = app.project.renderQueue;
            recordTest(mod, "Access_RenderQueue", rq !== null && rq !== undefined,
                "RenderQueue accessible");
        } catch(e) {
            recordTest(mod, "Access_RenderQueue", false, "RQ error: " + e.toString());
            report.modules[mod].status = "FAIL";
            return;
        }

        // 8.2 添加到渲染队列
        try {
            var rqItem = app.project.renderQueue.items.add(comp);
            recordTest(mod, "Add_To_RenderQueue", rqItem !== null,
                "Comp added to render queue");
        } catch(e) {
            recordTest(mod, "Add_To_RenderQueue", false, "Add to RQ error: " + e.toString());
        }

        // 8.3 设置输出模块
        try {
            var rqItems = app.project.renderQueue.items;
            if (rqItems.length > 0) {
                var lastItem = rqItems[rqItems.length - 1];
                var om = lastItem.outputModule(1);
                if (om) {
                    om.file = new File(Folder.desktop.fsName + "/_repl_test_output.avi");
                    recordTest(mod, "Set_OutputModule", true, "Output file set to desktop");
                } else {
                    recordTest(mod, "Set_OutputModule", false, "outputModule(1) returned null");
                }
            }
        } catch(e) {
            recordTest(mod, "Set_OutputModule", false, "OutputModule error: " + e.toString());
        }

        // 8.4 清除渲染队列项（不实际渲染）
        try {
            // 移除刚添加的队列项以避免干扰
            try {
                app.project.renderQueue.items[app.project.renderQueue.items.length - 1].remove();
                recordTest(mod, "Cleanup_RenderQueue", true, "RQ item removed (cleanup)");
            } catch(eC) {
                recordTest(mod, "Cleanup_RenderQueue", false, "Cleanup error: " + eC.toString());
            }
        } catch(e) {
            recordTest(mod, "Cleanup_RenderQueue", false, "Cleanup error: " + e.toString());
        }

        report.modules[mod].status = report.modules[mod].failed === 0 ? "PASS" : "PARTIAL";
    })();

    // =========================================================
    // 最终汇总
    // =========================================================
    report.status = "complete";
    report.totalElapsedMs = (new Date().getTime() - startTime);
    report.summary.passRate = report.summary.totalTests > 0
        ? Math.round((report.summary.passed / report.summary.totalTests) * 100)
        : 0;

    // 每个模块的状态汇总
    for (var mk in report.modules) {
        if (report.modules.hasOwnProperty(mk)) {
            var m = report.modules[mk];
            if (m.status === "running") {
                m.status = m.failed === 0 ? "PASS" : "PARTIAL";
            }
        }
    }

    // 输出到全局结果通道
    $.global.__aeAdditiveResult = JSON.stringify(report);
})();
