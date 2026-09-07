/*
 * ========================================================================
 * MOGRT 逆向工程与重新封装工具包 (MOGRT Toolkit)
 * 补齐 MOGRT 解压 → 修改 → 重新封装 的完整闭环
 *
 * 兼容性: AE 2025/2026 ExtendScript (ES3)
 * 依赖: 无外部依赖（使用 ExtendScript 内置功能）
 * ========================================================================
 */

#target aftereffects

var MOGRT_TOOLKIT = {
    version: "1.0",
    name: "MOGRT Toolkit"
};

// ============================================================
// 第一环: MOGRT 解压（提取 .aep 和所有资源）
// ============================================================

/**
 * 解压 MOGRT 文件到指定目录
 * MOGRT 是双层 ZIP:
 *   .mogrt (ZIP) → Project.aegraphic (ZIP) → project.aep + fonts/ + assets/ + scripts/
 *
 * @param {String} mogrtPath MOGRT文件路径
 * @param {String} outputDir 输出目录
 * @returns {Object} 解压结果
 */
function extractMOGRT(mogrtPath, outputDir) {
    var result = {
        success: false,
        mogrtPath: mogrtPath,
        outputDir: outputDir,
        extractedFiles: [],
        aepPath: "",
        fonts: [],
        assets: [],
        scripts: [],
        xmpPath: "",
        errors: []
    };

    var mogrtFile = new File(mogrtPath);
    if (!mogrtFile.exists) {
        result.errors.push("MOGRT文件不存在: " + mogrtPath);
        return result;
    }

    var outDir = new Folder(outputDir);
    if (!outDir.exists) {
        outDir.create();
    }

    // 第一层解压: .mogrt → 解压到临时目录
    var tempDir1 = Folder.temp + "/mogrt_extract_" + Date.now();
    var tempFolder1 = new Folder(tempDir1);
    tempFolder1.create();

    try {
        // 使用PowerShell解压第一层ZIP
        var cmd1 = 'powershell -Command "Expand-Archive -Path \'' + mogrtFile.fsName +
                   '\' -DestinationPath \'' + tempFolder1.fsName + '\' -Force"';

        // 执行解压
        var script1 = '$output = powershell -Command "Expand-Archive -LiteralPath \'' +
                       mogrtFile.fsName + '\' -DestinationPath \'' +
                       tempFolder1.fsName + '\' -Force" 2>&1';

        // 使用 system.callSystem 执行
        var output1 = system.callSystem(cmd1);

        // 查找 Project.aegraphic
        var aegraphicFile = null;
        var files1 = tempFolder1.getFiles();
        for (var i = 0; i < files1.length; i++) {
            if (files1[i].name === "Project.aegraphic" ||
                files1[i].name.indexOf(".aegraphic") >= 0) {
                aegraphicFile = files1[i];
                break;
            }
        }

        if (!aegraphicFile) {
            // 尝试递归查找
            function findAegraphic(folder) {
                var files = folder.getFiles();
                for (var j = 0; j < files.length; j++) {
                    if (files[j] instanceof Folder) {
                        var found = findAegraphic(files[j]);
                        if (found) return found;
                    } else if (files[j].name.indexOf(".aegraphic") >= 0) {
                        return files[j];
                    }
                }
                return null;
            }
            aegraphicFile = findAegraphic(tempFolder1);
        }

        if (!aegraphicFile) {
            result.errors.push("未找到 Project.aegraphic 文件");
            return result;
        }

        result.extractedFiles.push("Project.aegraphic");

        // 第二层解压: .aegraphic → 解压到输出目录
        var cmd2 = 'powershell -Command "Expand-Archive -Path \'' + aegraphicFile.fsName +
                   '\' -DestinationPath \'' + outDir.fsName + '\' -Force"';
        system.callSystem(cmd2);

        // 枚举解压后的文件
        function scanFiles(folder) {
            var files = folder.getFiles();
            for (var k = 0; k < files.length; k++) {
                if (files[k] instanceof Folder) {
                    scanFiles(files[k]);
                } else {
                    var fileName = files[k].name;
                    var filePath = files[k].fsName;

                    if (fileName.match(/\.aep$/i)) {
                        result.aepPath = filePath;
                        result.extractedFiles.push("project.aep");
                    } else if (fileName.match(/\.(otf|ttf|ttc)$/i)) {
                        result.fonts.push({ name: fileName, path: filePath });
                    } else if (fileName.match(/\.(png|jpg|jpeg|gif|bmp|exr|mov|mp4|avi)$/i)) {
                        result.assets.push({ name: fileName, path: filePath });
                    } else if (fileName.match(/\.(jsx|json)$/i)) {
                        result.scripts.push({ name: fileName, path: filePath });
                    } else if (fileName.match(/\.xml$/i)) {
                        result.xmpPath = filePath;
                        result.extractedFiles.push("xmp.xml");
                    }
                }
            }
        }

        scanFiles(outDir);

        result.success = result.aepPath !== "";
        if (!result.success) {
            result.errors.push("解压成功但未找到 .aep 文件");
        }

    } catch (e) {
        result.errors.push("解压失败: " + e.toString());
    }

    // 清理临时目录
    tempFolder1.remove();

    return result;
}

// ============================================================
// 第二环: 修改 MOGRT 控件参数
// ============================================================

/**
 * 打开提取的 .aep 并修改 Essential Graphics 参数
 * @param {String} aepPath .aep文件路径
 * @returns {Object} 打开结果
 */
function openMogrtProject(aepPath) {
    var result = {
        success: false,
        aepPath: aepPath,
        comps: [],
        egControls: [],
        errors: []
    };

    var aepFile = new File(aepPath);
    if (!aepFile.exists) {
        result.errors.push(".aep文件不存在: " + aepPath);
        return result;
    }

    try {
        // 打开项目
        var proj = app.open(aepFile);

        // 列出所有合成
        for (var i = 1; i <= proj.numItems; i++) {
            var item = proj.item(i);
            if (item instanceof CompItem) {
                var compInfo = {
                    name: item.name,
                    width: item.width,
                    height: item.height,
                    duration: item.duration,
                    frameRate: item.frameRate,
                    numLayers: item.numLayers
                };
                result.comps.push(compInfo);
            }
        }

        // 查找 Essential Graphics 控件
        var egComp = _findEssentialGraphicsComp(proj);
        if (egComp) {
            result.egControls = _extractEGControls(egComp);
        }

        result.success = true;

    } catch (e) {
        result.errors.push("打开项目失败: " + e.toString());
    }

    return result;
}

/**
 * 查找包含 Essential Graphics 控件的合成
 */
function _findEssentialGraphicsComp(proj) {
    // Essential Graphics 控件通常在主合成中
    for (var i = 1; i <= proj.numItems; i++) {
        var item = proj.item(i);
        if (item instanceof CompItem) {
            // 检查是否有空对象或图层带有控制器效果
            for (var j = 1; j <= item.numLayers; j++) {
                var layer = item.layer(j);
                var effects = layer.property("ADBE Effect Parade");
                if (effects) {
                    for (var k = 1; k <= effects.numProperties; k++) {
                        var fx = effects.property(k);
                        // 检查是否为控制效果
                        if (fx.matchName === "ADBE Slider Control" ||
                            fx.matchName === "ADBE Angle Control" ||
                            fx.matchName === "ADBE Color Control" ||
                            fx.matchName === "ADBE Point Control" ||
                            fx.matchName === "ADBE Checkbox Control") {
                            return item;
                        }
                    }
                }
            }
        }
    }
    return null;
}

/**
 * 提取 Essential Graphics 控件
 */
function _extractEGControls(comp) {
    var controls = [];

    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var effects = layer.property("ADBE Effect Parade");
        if (!effects) continue;

        for (var j = 1; j <= effects.numProperties; j++) {
            var fx = effects.property(j);
            var controlType = "";

            switch (fx.matchName) {
                case "ADBE Slider Control":
                    controlType = "slider";
                    break;
                case "ADBE Angle Control":
                    controlType = "angle";
                    break;
                case "ADBE Color Control":
                    controlType = "color";
                    break;
                case "ADBE Point Control":
                    controlType = "point";
                    break;
                case "ADBE Checkbox Control":
                    controlType = "checkbox";
                    break;
                default:
                    continue;
            }

            var control = {
                layerName: layer.name,
                effectName: fx.name,
                controlType: controlType,
                matchName: fx.matchName,
                currentValue: null,
                expression: ""
            };

            // 获取当前值
            try {
                var param = fx.property(1);
                control.currentValue = param.value;
                control.expression = param.expression || "";
            } catch (e) {}

            controls.push(control);
        }
    }

    return controls;
}

/**
 * 修改 Essential Graphics 控件参数
 * @param {CompItem} comp 主合成
 * @param {Array} controlUpdates 控件更新数组 [{layerName, effectName, value}]
 * @returns {Object} 修改结果
 */
function modifyEGControls(comp, controlUpdates) {
    var result = {
        success: false,
        modified: 0,
        failed: 0,
        details: [],
        errors: []
    };

    for (var i = 0; i < controlUpdates.length; i++) {
        var update = controlUpdates[i];
        try {
            var layer = comp.layer(update.layerName);
            if (!layer) {
                result.failed++;
                result.details.push({ name: update.effectName, status: "layer_not_found" });
                continue;
            }

            var fx = layer.effect(update.effectName);
            if (!fx) {
                result.failed++;
                result.details.push({ name: update.effectName, status: "effect_not_found" });
                continue;
            }

            var param = fx.property(1);
            param.setValue(update.value);
            result.modified++;
            result.details.push({
                name: update.effectName,
                status: "modified",
                value: update.value
            });

        } catch (e) {
            result.failed++;
            result.details.push({ name: update.effectName, status: "error", error: e.toString() });
        }
    }

    result.success = result.failed === 0;
    return result;
}

// ============================================================
// 第三环: 重新导出 MOGRT
// ============================================================

/**
 * 将当前合成重新导出为 MOGRT
 * @param {CompItem} comp 要导出的合成
 * @param {String} outputPath 输出路径（.mogrt）
 * @param {Array} egControls Essential Graphics 控件列表
 * @returns {Object} 导出结果
 */
function exportMOGRT(comp, outputPath, egControls) {
    var result = {
        success: false,
        outputPath: outputPath,
        controlsAdded: 0,
        errors: []
    };

    if (!comp || !(comp instanceof CompItem)) {
        result.errors.push("无效的合成");
        return result;
    }

    try {
        // 方法1: 使用AE内置的MOGRT导出（需要AE 2019+）
        // 使用 ExtendScript 调用 File > Export > Motion Graphics Template

        // 方法2: 手动构建MOGRT结构
        var outputFile = new File(outputPath);

        // 先保存项目
        var tempAep = File.temp.path + "/mogrt_temp_" + Date.now() + ".aep";
        app.project.save(new File(tempAep));

        // 构建MOGRT的ZIP结构
        // 1. 创建 Project.aegraphic (ZIP包含.aep + 元数据)
        // 2. 将 .aegraphic 放入 .mogrt (ZIP)

        // 由于 ExtendScript 没有原生 ZIP 功能，使用 PowerShell
        var aegraphicPath = File.temp.path + "/mogrt_aegraphic_" + Date.now();
        var aegraphicFolder = new Folder(aegraphicPath);
        aegraphicFolder.create();

        // 复制 .aep 到 aegraphic 目录
        var aepCopy = new File(aegraphicPath + "/project.aep");
        var aepOrig = new File(tempAep);
        aepOrig.copy(aepCopy);

        // 创建 metadata 目录
        var metaFolder = new Folder(aegraphicPath + "/metadata");
        metaFolder.create();

        // 创建 essentialgraphics 目录
        var egFolder = new Folder(aegraphicPath + "/essentialgraphics");
        egFolder.create();

        // 写入 XMP 元数据
        var xmpContent = _buildXMPMetadata(comp, egControls);
        var xmpFile = new File(metaFolder.fsName + "/xmp.xml");
        xmpFile.open("w");
        xmpFile.write(xmpContent);
        xmpFile.close();

        // 写入 essentialgraphics 定义
        var egContent = _buildEGDefinition(comp, egControls);
        var egFile = new File(egFolder.fsName + "/essentialgraphics.json");
        egFile.open("w");
        egFile.write(egContent);
        egFile.close();

        // 压缩 aegraphic 目录为 ZIP
        var zipAegraphicCmd = 'powershell -Command "Compress-Archive -Path \'' +
                              aegraphicFolder.fsName + '\\*\' -DestinationPath \'' +
                              File.temp.path + '/Project.aegraphic\' -Force"';
        system.callSystem(zipAegraphicCmd);

        // 将 .aegraphic 重命名为 .zip 并压缩为 .mogrt
        var mogrtZipCmd = 'powershell -Command "Compress-Archive -Path \'' +
                          File.temp.path + '/Project.aegraphic\' -DestinationPath \'' +
                          outputFile.fsName + '\' -Force"';
        system.callSystem(mogrtZipCmd);

        // 重命名为 .mogrt
        var finalFile = new File(outputPath);
        if (!outputPath.match(/\.mogrt$/i)) {
            var zipFile = new File(outputPath);
            finalFile = new File(outputPath.replace(/\.[^.]+$/, "") + ".mogrt");
            zipFile.rename(finalFile.name);
        }

        result.success = finalFile.exists;
        result.controlsAdded = egControls ? egControls.length : 0;
        result.outputPath = finalFile.fsName;

        // 清理临时文件
        aegraphicFolder.remove();
        new File(File.temp.path + "/Project.aegraphic").remove();

    } catch (e) {
        result.errors.push("导出MOGRT失败: " + e.toString());
    }

    return result;
}

/**
 * 构建 XMP 元数据
 */
function _buildXMPMetadata(comp, controls) {
    var xmp = '<?xml version="1.0" encoding="UTF-8"?>\n';
    xmp += '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n';
    xmp += '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n';
    xmp += '    <rdf:Description rdf:about=""\n';
    xmp += '      xmlns:eg="http://ns.adobe.com/essentialgraphics/1.0/">\n';

    if (controls) {
        for (var i = 0; i < controls.length; i++) {
            var ctrl = controls[i];
            xmp += '      <eg:property eg:name="' + ctrl.name + '" eg:type="' + ctrl.type + '"/>\n';
        }
    }

    xmp += '    </rdf:Description>\n';
    xmp += '  </rdf:RDF>\n';
    xmp += '</x:xmpmeta>';

    return xmp;
}

/**
 * 构建 Essential Graphics 定义
 */
function _buildEGDefinition(comp, controls) {
    var def = {
        name: comp.name,
        compName: comp.name,
        width: comp.width,
        height: comp.height,
        frameRate: comp.frameRate,
        duration: comp.duration,
        controls: []
    };

    if (controls) {
        for (var i = 0; i < controls.length; i++) {
            def.controls.push({
                name: controls[i].name,
                type: controls[i].type,
                layerName: controls[i].layerName,
                effectName: controls[i].effectName
            });
        }
    }

    // 手动序列化为JSON
    var json = '{\n';
    json += '  "name": "' + def.name + '",\n';
    json += '  "compName": "' + def.compName + '",\n';
    json += '  "width": ' + def.width + ',\n';
    json += '  "height": ' + def.height + ',\n';
    json += '  "frameRate": ' + def.frameRate + ',\n';
    json += '  "duration": ' + def.duration + ',\n';
    json += '  "controls": [\n';
    for (var j = 0; j < def.controls.length; j++) {
        var c = def.controls[j];
        json += '    {"name": "' + c.name + '", "type": "' + c.type + '"';
        json += ', "layerName": "' + c.layerName + '"';
        json += ', "effectName": "' + c.effectName + '"}';
        if (j < def.controls.length - 1) json += ',';
        json += '\n';
    }
    json += '  ]\n';
    json += '}';

    return json;
}

// ============================================================
// 第四环: MOGRT 完整逆向流程
// ============================================================

/**
 * MOGRT 完整逆向流程
 * 解压 → 打开AEP → 提取控件 → 修改参数 → 重新导出
 *
 * @param {String} mogrtPath MOGRT文件路径
 * @param {String} outputDir 输出目录
 * @param {Array} controlUpdates 控件更新数组（可选）
 * @param {String} newMogrtPath 新MOGRT输出路径（可选）
 * @returns {Object} 完整结果
 */
function mogrtReverseFlow(mogrtPath, outputDir, controlUpdates, newMogrtPath) {
    var result = {
        steps: [],
        success: false,
        errors: []
    };

    // 步骤1: 解压MOGRT
    var step1 = { name: "解压MOGRT", status: "pending", result: null };
    step1.result = extractMOGRT(mogrtPath, outputDir);
    step1.status = step1.result.success ? "success" : "failed";
    result.steps.push(step1);

    if (!step1.result.success) {
        result.errors.push("解压失败");
        return result;
    }

    // 步骤2: 打开AEP项目
    var step2 = { name: "打开AEP项目", status: "pending", result: null };
    step2.result = openMogrtProject(step1.result.aepPath);
    step2.status = step2.result.success ? "success" : "failed";
    result.steps.push(step2);

    if (!step2.result.success) {
        result.errors.push("打开AEP失败");
        return result;
    }

    // 步骤3: 提取控件信息
    var step3 = { name: "提取控件信息", status: "pending", result: null };
    step3.result = {
        controls: step2.result.egControls,
        count: step2.result.egControls.length
    };
    step3.status = "success";
    result.steps.push(step3);

    // 步骤4: 修改控件参数（如果提供了更新）
    if (controlUpdates && controlUpdates.length > 0) {
        var step4 = { name: "修改控件参数", status: "pending", result: null };
        var comp = app.project.activeItem;
        if (comp && comp instanceof CompItem) {
            step4.result = modifyEGControls(comp, controlUpdates);
            step4.status = step4.result.success ? "success" : "warning";
        } else {
            step4.result = { error: "没有打开的合成" };
            step4.status = "failed";
        }
        result.steps.push(step4);
    }

    // 步骤5: 重新导出MOGRT（如果提供了新路径）
    if (newMogrtPath) {
        var step5 = { name: "重新导出MOGRT", status: "pending", result: null };
        var comp2 = app.project.activeItem;
        step5.result = exportMOGRT(comp2, newMogrtPath, step3.result.controls);
        step5.status = step5.result.success ? "success" : "failed";
        result.steps.push(step5);
    }

    // 总结
    var allSuccess = true;
    for (var s = 0; s < result.steps.length; s++) {
        if (result.steps[s].status === "failed") {
            allSuccess = false;
            break;
        }
    }
    result.success = allSuccess;

    return result;
}

// ============================================================
// UI 面板
// ============================================================

function buildMOGRTToolkitUI() {
    var panel = (this instanceof Panel) ? this : new Window("palette", "MOGRT工具包 v" + MOGRT_TOOLKIT.version, undefined, { resizeable: true });
    panel.orientation = "column";
    panel.alignChildren = ["fill", "top"];
    panel.spacing = 4;
    panel.margins = 8;

    // MOGRT文件选择
    var fileGroup = panel.add("group");
    fileGroup.orientation = "row";
    fileGroup.add("statictext", [0, 0, 60, 20], "MOGRT:");
    var fileInput = fileGroup.add("edittext", [0, 0, 280, 20], "");
    var browseBtn = fileGroup.add("button", [0, 0, 60, 20], "浏览...");

    browseBtn.onClick = function() {
        var file = File.openDialog("选择MOGRT文件", "*.mogrt", false);
        if (file) {
            fileInput.text = file.fsName;
        }
    };

    // 输出目录
    var outGroup = panel.add("group");
    outGroup.orientation = "row";
    outGroup.add("statictext", [0, 0, 60, 20], "输出目录:");
    var outInput = outGroup.add("edittext", [0, 0, 280, 20], "~/Desktop/mogrt_extracted");
    var outBtn = outGroup.add("button", [0, 0, 60, 20], "选择...");
    outBtn.onClick = function() {
        var folder = Folder.selectDialog("选择输出目录");
        if (folder) outInput.text = folder.fsName;
    };

    // 按钮
    var btnGroup = panel.add("group");
    btnGroup.orientation = "row";
    var extractBtn = btnGroup.add("button", [0, 0, 120, 25], "解压MOGRT");
    var openBtn = btnGroup.add("button", [0, 0, 120, 25], "打开AEP项目");
    var flowBtn = btnGroup.add("button", [0, 0, 120, 25], "完整逆向流程");

    // 日志输出
    var logGroup = panel.add("panel", [0, 0, 440, 220], "日志输出");
    var logText = logGroup.add("edittext", [0, 0, 420, 190], "", { multiline: true, scrolling: true });
    logText.text = "MOGRT工具包 v" + MOGRT_TOOLKIT.version + " 已就绪\n";

    function log(msg) {
        logText.text += msg + "\n";
    }

    // 解压按钮
    extractBtn.onClick = function() {
        var path = fileInput.text;
        if (!path) { log("请选择MOGRT文件"); return; }
        var outDir = outInput.text || "~/Desktop/mogrt_extracted";

        log("正在解压: " + path);
        var result = extractMOGRT(path, outDir);
        if (result.success) {
            log("解压成功!");
            log("  AEP路径: " + result.aepPath);
            log("  字体数: " + result.fonts.length);
            log("  素材数: " + result.assets.length);
            log("  脚本数: " + result.scripts.length);
        } else {
            log("解压失败: " + result.errors.join("; "));
        }
    };

    // 打开AEP按钮
    openBtn.onClick = function() {
        var outDir = outInput.text || "~/Desktop/mogrt_extracted";
        var aepFile = new File(outDir + "/project.aep");
        if (!aepFile.exists) {
            // 搜索aep文件
            var folder = new Folder(outDir);
            var files = folder.getFiles("*.aep");
            if (files.length > 0) {
                aepFile = files[0];
            } else {
                log("未找到.aep文件，请先解压MOGRT");
                return;
            }
        }

        log("正在打开AEP: " + aepFile.fsName);
        var result = openMogrtProject(aepFile.fsName);
        if (result.success) {
            log("打开成功!");
            log("  合成数: " + result.comps.length);
            for (var i = 0; i < result.comps.length; i++) {
                log("    " + result.comps[i].name + " (" + result.comps[i].width + "x" + result.comps[i].height + ")");
            }
            log("  EGP控件数: " + result.egControls.length);
            for (var j = 0; j < result.egControls.length; j++) {
                log("    " + result.egControls[j].effectName + " [" + result.egControls[j].controlType + "] = " + result.egControls[j].currentValue);
            }
        } else {
            log("打开失败: " + result.errors.join("; "));
        }
    };

    // 完整逆向流程按钮
    flowBtn.onClick = function() {
        var path = fileInput.text;
        if (!path) { log("请选择MOGRT文件"); return; }
        var outDir = outInput.text || "~/Desktop/mogrt_extracted";

        log("=== 启动MOGRT完整逆向流程 ===");
        var result = mogrtReverseFlow(path, outDir, null, null);

        for (var i = 0; i < result.steps.length; i++) {
            var step = result.steps[i];
            var icon = step.status === "success" ? "[OK]" : step.status === "failed" ? "[FAIL]" : "[WARN]";
            log(icon + " " + step.name + ": " + step.status);
        }

        log(result.success ? "=== 完成: 全部成功 ===" : "=== 完成: 存在错误 ===");
    };

    panel.layout.layout(true);
    if (panel instanceof Window) {
        panel.center();
        panel.show();
    }

    return panel;
}

// 启动
if (typeof buildMOGRTToolkitUI === "function") {
    try {
        buildMOGRTToolkitUI();
    } catch (e) {
        alert("MOGRT工具包启动失败: " + e.toString());
    }
}
