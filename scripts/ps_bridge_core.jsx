// ============================================================
// AE Knowledge Vault - Photoshop Bridge CORE
// 放置于: Photoshop/Presets/Scripts/Startup/ 目录
// PS 启动时自动加载（或通过 File > Scripts > Browse 手动加载）
//
// 核心原则：此脚本应保持稳定，不再频繁修改
// 业务逻辑通过加载外部 handler_*.jsx 文件实现
//
// 通信机制（与 PSBridgeClient.py 协议对齐）：
//   - 命令文件: .ps-mcp-bridge/ps_command.json（单文件）
//   - 结果文件: .ps-mcp-bridge/ps_result.json（单文件）
//   - 命令格式: {"command": "ping", "script": "...", "timestamp": "...", "processed": false}
//   - 结果格式: {"status": "success"/"error", "result": {...}, "timestamp": "..."}
//   - processed=true 标记命令已处理
//   - 轮询间隔: 500ms
//   - 自动加载 handler_*.jsx 文件（多文件协议兼容层）
// ============================================================

#target photoshop

// ============================================================
// JSON Polyfill（PS ExtendScript 默认无 JSON）
// ============================================================
if (typeof JSON === 'undefined') {
    JSON = {
        parse: function(text) { return eval('(' + text + ')'); },
        stringify: function(value) {
            if (value === null) return 'null';
            if (typeof value === 'undefined') return 'undefined';
            if (typeof value === 'number' || typeof value === 'boolean') return String(value);
            if (typeof value === 'string') {
                return '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t') + '"';
            }
            if (value instanceof Array) {
                var items = [];
                for (var i = 0; i < value.length; i++) items.push(JSON.stringify(value[i]));
                return '[' + items.join(',') + ']';
            }
            if (typeof value === 'object') {
                if (value instanceof Date) return '"' + value.toString() + '"';
                var props = [];
                for (var key in value) {
                    if (value.hasOwnProperty(key)) {
                        props.push(JSON.stringify(key) + ':' + JSON.stringify(value[key]));
                    }
                }
                return '{' + props.join(',') + '}';
            }
            return 'null';
        }
    };
}

// ============================================================
// 全局 PSBridge 对象
// ============================================================
var PSBridge = {
    projectRoot: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault",
    bridgeDir: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ps-mcp-bridge",
    commandFile: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ps-mcp-bridge/ps_command.json",
    resultFile: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ps-mcp-bridge/ps_result.json",
    handlers: {},
    log: null,
    version: "1.0.0",
    pollInterval: 500,  // ms
    lastProcessedTimestamp: ""  // 防止重复处理同一命令
};

// 确保目录存在
var _bridgeDir = new Folder(PSBridge.bridgeDir);
if (!_bridgeDir.exists) {
    _bridgeDir.create();
}

// ============================================================
// 日志函数
// ============================================================
PSBridge.log = function(msg) {
    try {
        var logFile = new File(PSBridge.bridgeDir + "/bridge_log.txt");
        logFile.encoding = "UTF-8";
        logFile.open("a");
        var d = new Date();
        var ts = d.getFullYear() + "-" +
                 ("0" + (d.getMonth() + 1)).slice(-2) + "-" +
                 ("0" + d.getDate()).slice(-2) + "T" +
                 ("0" + d.getHours()).slice(-2) + ":" +
                 ("0" + d.getMinutes()).slice(-2) + ":" +
                 ("0" + d.getSeconds()).slice(-2);
        logFile.writeln("[" + ts + "] " + msg);
        logFile.close();
    } catch(e) {}
};

// ============================================================
// 注册处理器
// ============================================================
PSBridge.register = function(name, handler) {
    PSBridge.handlers[name] = handler;
    PSBridge.log("Handler registered: " + name);
};

PSBridge.listHandlers = function() {
    var names = [];
    for (var k in PSBridge.handlers) {
        if (PSBridge.handlers.hasOwnProperty(k)) names.push(k);
    }
    return names;
};

// ============================================================
// 初始化
// ============================================================
PSBridge.log("=== PSBridge v" + PSBridge.version + " starting ===");
PSBridge.log("PS version: " + app.version);
PSBridge.log("Documents open: " + app.documents.length);

// 写入就绪标记
try {
    var readyFile = new File(PSBridge.bridgeDir + "/bridge_ready.txt");
    readyFile.encoding = "UTF-8";
    readyFile.open("w");
    readyFile.writeln("READY");
    readyFile.writeln("version: " + PSBridge.version);
    readyFile.writeln("ps_version: " + app.version);
    readyFile.writeln("time: " + new Date().toUTCString());
    readyFile.close();
} catch(e) { PSBridge.log("Failed to write ready file: " + e); }

// ============================================================
// 内部工具函数
// ============================================================

function _findDocument(name) {
    for (var i = 0; i < app.documents.length; i++) {
        if (app.documents[i].name === name) return app.documents[i];
    }
    return null;
}

function _getSaveOptions(format) {
    var fmt = (format || "psd").toLowerCase();
    switch(fmt) {
        case "psd":
            return new PhotoshopSaveOptions();
        case "png":
        case "png24":
            var pngOpts = new PNGSaveOptions();
            pngOpts.interlaced = false;
            return pngOpts;
        case "jpg":
        case "jpeg":
            var jpgOpts = new JPEGSaveOptions();
            jpgOpts.quality = 12;
            return jpgOpts;
        case "tiff":
            return new TiffSaveOptions();
        case "bmp":
            return new BMPSaveOptions();
        default:
            return new PhotoshopSaveOptions();
    }
}

// ============================================================
// 内置基础处理器（与 PSBridgeClient.py 协议对齐）
// ============================================================

// ping - 心跳检测（PSBridgeClient.ping 调用）
PSBridge.register("ping", function(cmd) {
    return {
        pong: true,
        version: app.version,
        bridgeVersion: PSBridge.version,
        timestamp: new Date().toUTCString(),
        documentsOpen: app.documents.length
    };
});

// getDocumentInfo - 获取当前文档信息（PSBridgeClient.get_document_info 调用）
PSBridge.register("getDocumentInfo", function(cmd) {
    if (app.documents.length === 0) {
        return { error: "No document open" };
    }
    var doc = cmd.name ? _findDocument(cmd.name) : app.activeDocument;
    if (!doc) return { error: "Document not found: " + cmd.name };

    var layers = [];
    for (var i = 0; i < doc.layers.length && i < 200; i++) {
        try {
            var layer = doc.layers[i];
            layers.push({
                index: i,
                name: layer.name,
                kind: layer.kind.toString(),
                visible: layer.visible,
                opacity: layer.opacity
            });
        } catch(e) {}
    }

    return {
        name: doc.name,
        path: doc.fullName ? doc.fullName.fsName : "",
        width: doc.width.as("px"),
        height: doc.height.as("px"),
        resolution: doc.resolution,
        colorMode: doc.mode.toString(),
        bitsPerChannel: doc.bitsPerChannel.toString(),
        layers: layers,
        layerCount: doc.layers.length
    };
});

// listLayers - 列出所有图层（PSBridgeClient.list_layers 调用）
PSBridge.register("listLayers", function(cmd) {
    if (app.documents.length === 0) {
        return { error: "No document open" };
    }
    var doc = cmd.name ? _findDocument(cmd.name) : app.activeDocument;
    if (!doc) return { error: "Document not found" };

    var layers = [];
    for (var i = 0; i < doc.layers.length; i++) {
        try {
            var layer = doc.layers[i];
            layers.push({
                index: i,
                name: layer.name,
                kind: layer.kind.toString(),
                visible: layer.visible
            });
        } catch(e) {}
    }
    return { layers: layers, count: layers.length };
});

// execute_script - 执行任意 ExtendScript（PhotoshopEngine._execute_jsx 调用）
// 这是核心命令，PhotoshopEngine.execute 走到这里
PSBridge.register("execute_script", function(cmd) {
    if (!cmd.script) return { error: "Missing script" };
    try {
        var result = eval(cmd.script);
        return { result: String(result), executed: true };
    } catch(e) {
        return { error: e.toString() };
    }
});

// getInfo - 获取 Bridge 与 PS 状态
PSBridge.register("getInfo", function(cmd) {
    var info = {
        bridgeVersion: PSBridge.version,
        psVersion: app.version,
        handlers: PSBridge.listHandlers(),
        documentsOpen: app.documents.length,
        activeDocument: null
    };
    if (app.documents.length > 0) {
        var doc = app.activeDocument;
        info.activeDocument = {
            name: doc.name,
            width: doc.width.as("px"),
            height: doc.height.as("px"),
            resolution: doc.resolution,
            colorMode: doc.mode.toString(),
            layers: doc.layers.length
        };
    }
    return info;
});

// openDocument - 打开文件
PSBridge.register("openDocument", function(cmd) {
    if (!cmd.path) return { error: "Missing path" };
    try {
        var f = new File(cmd.path);
        if (!f.exists) return { error: "File not found: " + cmd.path };
        var doc = app.open(f);
        PSBridge.log("Opened: " + doc.name);
        return { opened: true, name: doc.name, layers: doc.layers.length };
    } catch(e) {
        return { error: e.toString() };
    }
});

// closeDocument - 关闭文档
PSBridge.register("closeDocument", function(cmd) {
    try {
        if (app.documents.length === 0) return { closed: false, reason: "no document" };
        var save = (cmd.save === true) ? SaveOptions.DONATACHANGES : SaveOptions.DONOTSAVECHANGES;
        app.activeDocument.close(save);
        return { closed: true };
    } catch(e) {
        return { error: e.toString() };
    }
});

// saveDocument - 保存文档
PSBridge.register("saveDocument", function(cmd) {
    try {
        if (app.documents.length === 0) return { error: "No document open" };
        var doc = app.activeDocument;
        if (cmd.path) {
            var f = new File(cmd.path);
            var format = cmd.format || "psd";
            var saveOpts = _getSaveOptions(format);
            doc.saveAs(f, saveOpts, true, Extension.LOWERCASE);
            return { saved: true, path: cmd.path, format: format };
        } else {
            doc.save();
            return { saved: true };
        }
    } catch(e) {
        return { error: e.toString() };
    }
});

// executeScriptFile - 执行外部 JSX 文件
PSBridge.register("executeScriptFile", function(cmd) {
    if (!cmd.scriptPath) return { error: "Missing scriptPath" };
    try {
        var sf = new File(cmd.scriptPath);
        if (!sf.exists) return { error: "File not found: " + cmd.scriptPath };

        sf.encoding = "UTF-8";
        sf.open("r");
        var content = sf.read();
        sf.close();

        var result = eval(content);
        return { executed: true, result: String(result) };
    } catch(e) {
        return { error: e.toString() };
    }
});

// doAction - 执行 PS 动作
PSBridge.register("doAction", function(cmd) {
    if (!cmd.action) return { error: "Missing action name" };
    var set = cmd.set || "Default Actions";
    try {
        app.doAction(cmd.action, set);
        return { applied: true, action: cmd.action, set: set };
    } catch(e) {
        return { error: e.toString() };
    }
});

// exportLayerAsPNG - 导出指定图层为 PNG
PSBridge.register("exportLayerAsPNG", function(cmd) {
    if (app.documents.length === 0) return { error: "No document open" };
    if (!cmd.outputDir) return { error: "Missing outputDir" };
    if (!cmd.layerName) return { error: "Missing layerName" };

    try {
        var doc = app.activeDocument;
        var layer = null;
        for (var i = 0; i < doc.layers.length; i++) {
            if (doc.layers[i].name === cmd.layerName) {
                layer = doc.layers[i];
                break;
            }
        }
        if (!layer) return { error: "Layer not found: " + cmd.layerName };

        var originalVisibility = [];
        for (var j = 0; j < doc.layers.length; j++) {
            originalVisibility.push(doc.layers[j].visible);
            doc.layers[j].visible = (doc.layers[j] === layer);
        }

        var layerDoc = doc.duplicate();
        try {
            layerDoc.crop(layer.bounds);
        } catch(e) {}

        var outputFile = new File(cmd.outputDir + "/" + cmd.layerName.replace(/[\\/:*?"<>|]/g, "_") + ".png");
        var pngOpts = new PNGSaveOptions();
        pngOpts.interlaced = false;
        pngOpts.compression = 9;

        layerDoc.saveAs(outputFile, pngOpts, true, Extension.LOWERCASE);
        layerDoc.close(SaveOptions.DONOTSAVECHANGES);

        for (var k = 0; k < doc.layers.length; k++) {
            doc.layers[k].visible = originalVisibility[k];
        }

        return {
            exported: true,
            layer: cmd.layerName,
            path: outputFile.fsName
        };
    } catch(e) {
        return { error: e.toString() };
    }
});

// exportAllLayers - 导出所有可见图层为 PNG
PSBridge.register("exportAllLayers", function(cmd) {
    if (app.documents.length === 0) return { error: "No document open" };
    if (!cmd.outputDir) return { error: "Missing outputDir" };

    try {
        var doc = app.activeDocument;
        var outputFolder = new Folder(cmd.outputDir);
        if (!outputFolder.exists) outputFolder.create();

        var originalVisibility = [];
        var exported = [];

        for (var i = 0; i < doc.layers.length; i++) {
            var layer = doc.layers[i];
            if (!layer.visible && !cmd.includeHidden) continue;

            originalVisibility = [];
            for (var j = 0; j < doc.layers.length; j++) {
                originalVisibility.push(doc.layers[j].visible);
                doc.layers[j].visible = (j === i);
            }

            try {
                var layerDoc = doc.duplicate();
                try { layerDoc.crop(layer.bounds); } catch(e) {}

                var safeName = layer.name.replace(/[\\/:*?"<>|]/g, "_");
                var outputFile = new File(cmd.outputDir + "/" + safeName + ".png");
                var pngOpts = new PNGSaveOptions();
                pngOpts.interlaced = false;

                layerDoc.saveAs(outputFile, pngOpts, true, Extension.LOWERCASE);
                layerDoc.close(SaveOptions.DONOTSAVECHANGES);
                exported.push(safeName);
            } catch(e) {
                PSBridge.log("Failed to export layer " + layer.name + ": " + e);
            }
        }

        for (var k = 0; k < doc.layers.length; k++) {
            doc.layers[k].visible = originalVisibility[k];
        }

        return { exported: exported, count: exported.length };
    } catch(e) {
        return { error: e.toString() };
    }
});

// smartObjectExport - 智能对象/分层 PSD 导出（显隐图层法修复版）
// 修复要点：
//   1. 显隐图层法：保存原始 visibility → 只显示目标层 → 导出 → 还原 visibility
//   2. 递归遍历 LayerSets（图层组），保留组结构（导出名含父组路径）
//   3. 保留 alpha 透明（PNGSaveOptions + 文档透明背景）
//   4. 区别于 exportAllLayers：本 handler 递归进入图层组，导出叶子图层
PSBridge.register("smartObjectExport", function(cmd) {
    if (app.documents.length === 0) return { error: "No document open" };
    if (!cmd.outputDir) return { error: "Missing outputDir" };

    try {
        var doc = cmd.docName ? _findDocument(cmd.docName) : app.activeDocument;
        if (!doc) return { error: "Document not found: " + cmd.docName };

        var outputFolder = new Folder(cmd.outputDir);
        if (!outputFolder.exists) outputFolder.create();

        var includeHidden = cmd.includeHidden === true;

        // 1. 递归收集所有可导出叶子图层（进入 LayerSets）
        var exportList = [];
        function _collect(layers, parentPath) {
            for (var i = 0; i < layers.length; i++) {
                var lyr = layers[i];
                var fullPath = parentPath ? (parentPath + "/" + lyr.name) : lyr.name;
                if (lyr.typename === "LayerSet") {
                    _collect(lyr.layers, fullPath);
                } else {
                    exportList.push({ layer: lyr, path: fullPath });
                }
            }
        }
        _collect(doc.layers, "");

        // 2. 保存原始 visibility 快照（仅顶层，用于还原）
        var snapshot = [];
        for (var s = 0; s < doc.layers.length; s++) {
            snapshot.push(doc.layers[s].visible);
        }

        var exported = [];
        var errors = [];

        // 3. 对每个目标图层执行"显隐图层法"
        for (var i = 0; i < exportList.length; i++) {
            var entry = exportList[i];
            var lyr = entry.layer;

            if (!lyr.visible && !includeHidden) continue;

            // 显隐图层法：先全部隐藏顶层，再只显示当前目标层所在链
            for (var j = 0; j < doc.layers.length; j++) {
                doc.layers[j].visible = false;
            }
            try { lyr.visible = true; } catch(e) { errors.push(entry.path + ": " + e); continue; }

            try {
                var layerDoc = doc.duplicate();
                try { layerDoc.crop(lyr.bounds); } catch(e) {}

                var safeName = entry.path.replace(/[\\/:*?"<>|]/g, "_");
                var outputFile = new File(cmd.outputDir + "/" + safeName + ".png");

                var pngOpts = new PNGSaveOptions();
                pngOpts.interlaced = false;
                pngOpts.compression = 9;

                layerDoc.saveAs(outputFile, pngOpts, true, Extension.LOWERCASE);
                layerDoc.close(SaveOptions.DONOTSAVECHANGES);
                exported.push(safeName);
            } catch(e) {
                errors.push(entry.path + ": " + e.toString());
            }
        }

        // 4. 还原原始 visibility
        for (var k = 0; k < doc.layers.length; k++) {
            try { doc.layers[k].visible = snapshot[k]; } catch(e) {}
        }

        return {
            exported: exported,
            count: exported.length,
            errors: errors,
            method: "visibility_toggle_recursive"
        };
    } catch(e) {
        return { error: e.toString() };
    }
});

// applyLut - 应用 Color Lookup（LUT）
PSBridge.register("applyLut", function(cmd) {
    if (app.documents.length === 0) return { error: "No document open" };
    if (!cmd.lutPath) return { error: "Missing lutPath" };

    try {
        var desc = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("AdjL"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        desc.putReference(charIDToTypeID("null"), ref);

        desc.putString(charIDToTypeID("Nm  "), "Color Lookup");
        desc.putEnumerated(charIDToTypeID("LutE"), charIDToTypeID("LutT"), charIDToTypeID("Lut3"));

        var lutFile = new File(cmd.lutPath);
        if (lutFile.exists) {
            desc.putPath(charIDToTypeID("LutP"), lutFile);
        }

        executeAction(charIDToTypeID("Mk  "), desc, DialogModes.NO);

        return { applied: true, lutPath: cmd.lutPath };
    } catch(e) {
        return { error: e.toString() };
    }
});

// exportLut - 真正导出 .cube LUT 文件（修复版）
// 修复要点：
//   1. 调用 Photoshop "Export > Color Lookup Tables..." 的 AM API，直接产出 .cube
//   2. 支持 lutSize 参数（32/64）
//   3. 若文档无 Color Lookup 调整图层，自动创建一个
//   4. 可选保留 PSD 备份（savePsd=true）
//   注意：AM 键值可能因 PS 版本而异，若失败请用 ScriptListener 录制精确键值
PSBridge.register("exportLut", function(cmd) {
    if (app.documents.length === 0) return { error: "No document open" };
    if (!cmd.outputPath) return { error: "Missing outputPath" };

    var lutSize = cmd.lutSize || 32;
    var cubePath = cmd.outputPath.replace(/\.psd$/i, ".cube");
    if (!/\.cube$/i.test(cubePath)) cubePath = cubePath + ".cube";

    try {
        var doc = cmd.docName ? _findDocument(cmd.docName) : app.activeDocument;
        if (!doc) return { error: "Document not found: " + cmd.docName };

        // 1. 检查是否已有 Color Lookup 调整图层；没有则创建
        var hasColorLookup = false;
        for (var i = 0; i < doc.layers.length; i++) {
            try {
                if (doc.layers[i].kind === LayerKind.COLORLOOKUP) {
                    hasColorLookup = true;
                    doc.activeLayer = doc.layers[i];
                    break;
                }
            } catch(e) {}
        }

        if (!hasColorLookup) {
            var mkDesc = new ActionDescriptor();
            var mkRef = new ActionReference();
            mkRef.putClass(stringIDToTypeID("adjustmentLayer"));
            mkDesc.putReference(charIDToTypeID("null"), mkRef);
            var layerDesc = new ActionDescriptor();
            layerDesc.putClass(stringIDToTypeID("colorLookup"));
            mkDesc.putObject(charIDToTypeID("Usng"), stringIDToTypeID("adjustmentLayer"), layerDesc);
            executeAction(charIDToTypeID("Mk  "), mkDesc, DialogModes.NO);
            PSBridge.log("Created Color Lookup adjustment layer");
        }

        // 2. 选中 Color Lookup 调整图层（导出 API 需要它被激活）
        for (var j = 0; j < doc.layers.length; j++) {
            try {
                if (doc.layers[j].kind === LayerKind.COLORLOOKUP) {
                    doc.activeLayer = doc.layers[j];
                    break;
                }
            } catch(e) {}
        }

        // 3. 调用 Photoshop 的 "Export > Color Lookup Tables..." AM API
        //    对应菜单：File > Export > Color Lookup Tables...
        var exportDesc = new ActionDescriptor();
        var exportRef = new ActionReference();
        exportRef.putEnumerated(
            charIDToTypeID("AdjL"),
            charIDToTypeID("Ordn"),
            charIDToTypeID("Trgt")
        );
        exportDesc.putReference(charIDToTypeID("null"), exportRef);

        // LUT 格式：.cube
        exportDesc.putEnumerated(
            charIDToTypeID("LUTf"),
            charIDToTypeID("LUTe"),
            charIDToTypeID("Cube")
        );

        // 输出路径
        var cubeFile = new File(cubePath);
        exportDesc.putPath(charIDToTypeID("In  "), cubeFile);

        // LUT 尺寸（32 或 64）
        exportDesc.putInteger(charIDToTypeID("LUTs"), lutSize);

        // 执行导出
        executeAction(charIDToTypeID("Expt"), exportDesc, DialogModes.NO);

        // 4. 验证 .cube 文件已生成
        var resultFile = new File(cubePath);
        if (!resultFile.exists) {
            return {
                error: "LUT export action completed but .cube file not found at: " + cubePath,
                note: "PS version may not support Color Lookup Tables export, or AM keys differ. Use ScriptListener to verify keys."
            };
        }

        // 5. 可选：保存带 Color Lookup 调整图层的 PSD（备份）
        var psdPath = null;
        if (cmd.savePsd !== false) {
            psdPath = cubePath.replace(/\.cube$/i, ".psd");
            var psdFile = new File(psdPath);
            var psdOpts = new PhotoshopSaveOptions();
            doc.saveAs(psdFile, psdOpts, true, Extension.LOWERCASE);
        }

        return {
            exported: true,
            cubePath: cubePath,
            psdPath: psdPath,
            lutSize: lutSize,
            method: "photoshop_export_action"
        };
    } catch(e) {
        return {
            error: "Photoshop LUT export failed: " + e.toString(),
            hint: "Ensure PS CC 2015+ and an adjustment layer is active. Run ScriptListener to capture exact AM keys.",
            attemptedCubePath: cubePath
        };
    }
});

// smartCutout - 智能抠图（Select Subject + Mask）
PSBridge.register("smartCutout", function(cmd) {
    if (app.documents.length === 0) return { error: "No document open" };

    try {
        var doc = app.activeDocument;
        var activeLayer = doc.activeLayer;

        try {
            var desc = new ActionDescriptor();
            var ref = new ActionReference();
            ref.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            desc.putReference(charIDToTypeID("null"), ref);
            executeAction(stringIDToTypeID("selectSubject"), desc, DialogModes.NO);
        } catch(e) {
            PSBridge.log("Select Subject failed (may not be supported): " + e);
        }

        try {
            var maskDesc = new ActionDescriptor();
            maskDesc.putClass(charIDToTypeID("Nw  "), charIDToTypeID("Chnl"));
            var maskRef = new ActionReference();
            maskRef.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
            maskDesc.putReference(charIDToTypeID("At  "), maskRef);
            maskDesc.putEnumerated(charIDToTypeID("Usng"), charIDToTypeID("UsrM"), charIDToTypeID("RvlS"));
            executeAction(charIDToTypeID("Mk  "), maskDesc, DialogModes.NO);
        } catch(e) {
            PSBridge.log("Mask creation failed: " + e);
        }

        return { cutout: true, layer: activeLayer.name };
    } catch(e) {
        return { error: e.toString() };
    }
});

// batchProcess - 批量处理（执行动作）
PSBridge.register("batchProcess", function(cmd) {
    if (!cmd.inputDir) return { error: "Missing inputDir" };
    if (!cmd.action) return { error: "Missing action name" };
    if (!cmd.outputDir) return { error: "Missing outputDir" };

    try {
        var inputFolder = new Folder(cmd.inputDir);
        var outputFolder = new Folder(cmd.outputDir);
        if (!outputFolder.exists) outputFolder.create();

        var pattern = cmd.pattern || "*.jpg";
        var files = inputFolder.getFiles(pattern);
        var processed = 0;
        var errors = [];

        for (var i = 0; i < files.length; i++) {
            try {
                var doc = app.open(files[i]);
                app.doAction(cmd.action, cmd.setAction || "Default Actions");

                var outputFile = new File(cmd.outputDir + "/" + doc.name);
                var jpgOpts = new JPEGSaveOptions();
                jpgOpts.quality = 12;
                doc.saveAs(outputFile, jpgOpts, true, Extension.LOWERCASE);
                doc.close(SaveOptions.DONOTSAVECHANGES);
                processed++;
            } catch(e) {
                errors.push(files[i].name + ": " + e.toString());
            }
        }

        return {
            processed: processed,
            total: files.length,
            errors: errors
        };
    } catch(e) {
        return { error: e.toString() };
    }
});

// reloadHandlers - 重新加载所有 handler
PSBridge.register("reloadHandlers", function(cmd) {
    PSBridge.log("Reloading handlers...");
    loadAllHandlers();
    return {
        reloaded: true,
        handlers: PSBridge.listHandlers()
    };
});

// ============================================================
// 命令处理（单文件协议，与 PSBridgeClient.py 对齐）
// ============================================================
function processCommandFile() {
    try {
        var cmdFile = new File(PSBridge.commandFile);
        if (!cmdFile.exists) return;

        cmdFile.encoding = "UTF-8";
        cmdFile.open("r");
        var cmdStr = cmdFile.read();
        cmdFile.close();

        if (!cmdStr) return;

        var cmd = {};
        try { cmd = JSON.parse(cmdStr); }
        catch(e) {
            try { cmd = eval('(' + cmdStr + ')'); }
            catch(e2) {
                PSBridge.log("Parse error: " + e2);
                cmd = { command: "parse_error" };
            }
        }

        // 已处理过该命令则跳过
        if (cmd.processed === true) return;
        var cmdTs = cmd.timestamp || "";
        if (cmdTs && cmdTs === PSBridge.lastProcessedTimestamp) return;

        var commandName = cmd.command || cmd.action;  // 兼容 action 字段
        PSBridge.log("Executing: " + commandName);

        // 删除旧结果文件
        var resultFile = new File(PSBridge.resultFile);
        if (resultFile.exists) {
            try { resultFile.remove(); } catch(e) {}
        }

        // 查找处理器
        var handler = PSBridge.handlers[commandName];
        var result;
        var status = "success";

        if (handler) {
            try {
                result = handler(cmd);
                if (result && result.error) status = "error";
            } catch(e) {
                result = { error: e.toString() };
                status = "error";
                PSBridge.log("Handler error: " + e);
            }
        } else {
            result = { error: "Unknown command: " + commandName };
            status = "error";
            PSBridge.log("No handler for: " + commandName);
        }

        // 写入结果
        var rf = new File(PSBridge.resultFile);
        rf.encoding = "UTF-8";
        rf.open("w");
        rf.writeln(JSON.stringify({
            status: status,
            result: result,
            timestamp: new Date().toUTCString()
        }));
        rf.close();

        // 标记命令已处理（写入 ps_command.json，processed=true）
        cmd.processed = true;
        PSBridge.lastProcessedTimestamp = cmdTs;
        var cf = new File(PSBridge.commandFile);
        cf.encoding = "UTF-8";
        cf.open("w");
        cf.writeln(JSON.stringify(cmd));
        cf.close();

        PSBridge.log("Done: " + commandName + " (" + status + ")");
    } catch(e) {
        PSBridge.log("Process error: " + e);
    }
}

// ============================================================
// 自动加载所有 handler_*.jsx 文件
// ============================================================
function loadAllHandlers() {
    try {
        var handlerFiles = _bridgeDir.getFiles("handler_*.jsx");
        PSBridge.log("Found " + handlerFiles.length + " handler file(s) in bridge dir");

        for (var i = 0; i < handlerFiles.length; i++) {
            _loadHandlerFile(handlerFiles[i]);
        }
    } catch(e) {
        PSBridge.log("Load handlers error: " + e);
    }
}

function _loadHandlerFile(handlerFile) {
    try {
        handlerFile.encoding = "UTF-8";
        handlerFile.open("r");
        var content = handlerFile.read();
        handlerFile.close();

        // 在 PSBridge 上下文中执行
        var fn = new Function("PSBridge", content);
        fn(PSBridge);
        PSBridge.log("Loaded handler: " + handlerFile.name);
    } catch(e) {
        PSBridge.log("Failed to load " + handlerFile.name + ": " + e);
    }
}

// 加载所有 handler
loadAllHandlers();

// ============================================================
// 启动轮询
// ============================================================
PSBridge.log("Starting polling (interval=" + PSBridge.pollInterval + "ms)...");
PSBridge.log("Handlers: " + PSBridge.listHandlers().join(", "));

var pollEnabled = true;

// PS 提供 app.scheduleTask（与 AE 类似）
try {
    if (typeof app.scheduleTask === 'function') {
        $.global.__psBridgePoll = function() {
            if (pollEnabled) {
                try { processCommandFile(); } catch(e) { PSBridge.log("Poll error: " + e); }
                app.scheduleTask("$.global.__psBridgePoll()", PSBridge.pollInterval, false);
            }
        };
        app.scheduleTask("$.global.__psBridgePoll()", PSBridge.pollInterval, false);
        PSBridge.log("Using app.scheduleTask for polling");
    } else if (typeof $.setInterval === 'function') {
        $.setInterval(processCommandFile, PSBridge.pollInterval);
        PSBridge.log("Using $.setInterval for polling");
    } else {
        PSBridge.log("WARN: No scheduling API available, polling disabled");
    }
} catch(e) {
    PSBridge.log("Polling setup error: " + e);
}

PSBridge.log("=== PSBridge initialized ===");

// 导出到全局
$.global.PSBridge = PSBridge;

// 返回值（供外部调用验证）
"PSBridge v" + PSBridge.version + " ready";
