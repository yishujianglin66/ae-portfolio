// AE工程深度分析脚本
// 通过命令行运行: AfterFX.exe -r "ae_deep_analysis.jsx"
// 分析结果写入磁盘JSON文件

// 全局辅助函数（必须在主逻辑之前定义）
function getBlendingModeName(mode) {
    var names = {0:"NORMAL",1:"ADD",2:"MULTIPLY",3:"SCREEN",4:"OVERLAY",5:"DARKEN",6:"LIGHTEN",7:"COLOR_DODGE",8:"COLOR_BURN",9:"HARD_LIGHT",10:"SOFT_LIGHT",11:"DIFFERENCE",12:"EXCLUSION",13:"HUE",14:"SATURATION",15:"COLOR",16:"LUMINOSITY",17:"ALPHA_ADD",18:"DANCING_DISSOLVE"};
    return names[mode] || ("UNKNOWN_" + mode);
}

function getKeyInterpName(t) {
    var names = {1:"LINEAR",2:"BEZIER",3:"HOLD",4:"NONE"};
    return names[t] || ("UNKNOWN_" + t);
}

function getMaskModeName(m) {
    var names = {0:"NONE",1:"ADD",2:"SUBTRACT",3:"INTERSECT",4:"LIGHTEN",5:"DARKEN",6:"DIFFERENCE",7:"ALPHA"};
    return names[m] || ("UNKNOWN_" + m);
}

function getPropInfo(prop) {
    if (!prop) return null;
    var info = {name: prop.name, matchName: prop.matchName, value: null, expression: null, keyframes: null, numKeys: 0};
    try {
        if (prop.propertyType === PropertyType.PROPERTY) {
            info.canVaryOverTime = prop.canVaryOverTime ? true : false;
            try { var expr = prop.expression; if (expr && expr.length > 0) info.expression = expr; } catch(e) {}
            if (prop.canVaryOverTime) {
                info.numKeys = prop.numKeys;
                if (prop.numKeys > 0) {
                    info.keyframes = [];
                    for (var k = 1; k <= prop.numKeys && k <= 200; k++) {
                        var kf = {time: prop.keyTime(k), inInterp: getKeyInterpName(prop.keyInInterpolationType(k)), outInterp: getKeyInterpName(prop.keyOutInterpolationType(k))};
                        try { kf.value = prop.keyValue(k); } catch(e) { kf.value = "unreadable"; }
                        try { kf.inTangent = prop.keyInSpatialTangent(k); kf.outTangent = prop.keyOutSpatialTangent(k); } catch(e) {}
                        info.keyframes.push(kf);
                    }
                } else {
                    try { info.value = prop.value; } catch(e) { info.value = "unreadable"; }
                }
            } else {
                try { info.value = prop.value; } catch(e) { info.value = "unreadable"; }
            }
        } else {
            info.propertyType = "group";
            info.numProperties = prop.numProperties;
        }
    } catch(e) { info.error = e.toString(); }
    return info;
}

function analyzeLayer(layer) {
    var info = {
        index: layer.index, name: layer.name,
        enabled: layer.enabled, inPoint: layer.inPoint, outPoint: layer.outPoint,
        blendingMode: getBlendingModeName(layer.blendingMode),
        isAdjustment: layer.adjustmentLayer ? true : false,
        is3D: layer.threeDLayer ? true : false,
        parent: layer.parent ? layer.parent.name : null,
        transform: null, effects: null, text: null, masks: null
    };

    // Transform
    try {
        var tr = layer.property("ADBE Transform Group");
        if (tr) {
            info.transform = {
                anchorPoint: getPropInfo(tr.property("ADBE Anchor Point")),
                position: getPropInfo(tr.property("ADBE Position")),
                scale: getPropInfo(tr.property("ADBE Scale")),
                rotation: getPropInfo(tr.property("ADBE Rotate Z")),
                opacity: getPropInfo(tr.property("ADBE Opacity"))
            };
            // 3D属性
            if (layer.threeDLayer) {
                info.transform.rotationX = getPropInfo(tr.property("ADBE Rotate X"));
                info.transform.rotationY = getPropInfo(tr.property("ADBE Rotate Y"));
                info.transform.orientation = getPropInfo(tr.property("ADBE Orientation"));
            }
        }
    } catch(e) {}

    // Effects
    try {
        var fx = layer.property("ADBE Effect Parade");
        if (fx && fx.numProperties > 0) {
            info.effects = [];
            for (var e = 1; e <= fx.numProperties; e++) {
                var effect = fx.property(e);
                var eInfo = {name: effect.name, matchName: effect.matchName, enabled: effect.enabled, properties: []};
                try {
                    if (effect.numProperties) {
                        for (var p = 1; p <= effect.numProperties && p <= 50; p++) {
                            var prop = effect.property(p);
                            if (prop) {
                                var pi = getPropInfo(prop);
                                eInfo.properties.push(pi);
                            }
                        }
                    }
                } catch(e2) {}
                info.effects.push(eInfo);
            }
        }
    } catch(e) {}

    // Text
    try {
        var tp = layer.property("ADBE Text Properties");
        if (tp) {
            var srcText = tp.property("ADBE Text Document");
            if (srcText) {
                var doc = srcText.value;
                info.text = {
                    sourceText: doc.text,
                    font: doc.font,
                    fontSize: doc.fontSize,
                    fillColor: doc.fillColor ? [doc.fillColor[0], doc.fillColor[1], doc.fillColor[2]] : null,
                    applyFill: doc.applyFill ? true : false,
                    applyStroke: doc.applyStroke ? true : false,
                    strokeColor: doc.strokeColor ? [doc.strokeColor[0], doc.strokeColor[1], doc.strokeColor[2]] : null,
                    strokeWidth: doc.strokeWidth,
                    tracking: doc.tracking,
                    fauxBold: doc.fauxBold ? true : false,
                    fauxItalic: doc.fauxItalic ? true : false
                };
            }
        }
    } catch(e) {}

    // Masks
    try {
        var mp = layer.property("ADBE Mask Parade");
        if (mp && mp.numProperties > 0) {
            info.masks = [];
            for (var m = 1; m <= mp.numProperties; m++) {
                var mask = mp.property(m);
                info.masks.push({
                    name: mask.name,
                    mode: getMaskModeName(mask.maskMode),
                    enabled: mask.enabled,
                    inverted: mask.inverted ? true : false,
                    feather: getPropInfo(mask.property("ADBE Mask Feather")),
                    opacity: getPropInfo(mask.property("ADBE Mask Opacity")),
                    expansion: getPropInfo(mask.property("ADBE Mask Expansion"))
                });
            }
        }
    } catch(e) {}

    return info;
}

function analyzeComp(comp) {
    var info = {
        name: comp.name, width: comp.width, height: comp.height,
        duration: comp.duration, fps: comp.frameRate,
        numLayers: comp.numLayers,
        bgColor: comp.bgColor ? [comp.bgColor[0], comp.bgColor[1], comp.bgColor[2]] : null,
        layers: []
    };
    for (var l = 1; l <= comp.numLayers && l <= 200; l++) {
        info.layers.push(analyzeLayer(comp.layer(l)));
    }
    return info;
}

// === 主逻辑 ===
(function() {
    var resultFile = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_director/ae_project_analysis/analysis_result.json");
    resultFile.encoding = "UTF-8";
    resultFile.open("w");

    try {
        // 从环境变量获取AEP路径
        var aepPath = $.getenv("AEP_FILE_PATH");
        if (!aepPath || aepPath === "") {
            // 默认路径
            aepPath = "D:/BaiduNetdiskDownload/AE新手10套/do you mean（简单）/9.23.aep";
        }
        
        // 抑制所有弹窗
        app.beginSuppressDialogs();
        
        var aepFile = new File(aepPath);
        if (!aepFile.exists) {
            app.endSuppressDialogs();
            resultFile.write(JSON.stringify({status:"error", message:"AEP not found: " + aepPath}));
            resultFile.close();
            return;
        }

        // 如果已有项目，先关闭
        if (app.project && app.project.file) {
            app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
        }

        var proj = app.open(aepFile);
        app.endSuppressDialogs();

        if (!proj) {
            resultFile.write(JSON.stringify({status:"error", message:"Failed to open project"}));
            resultFile.close();
            return;
        }

        var output = {
            status: "success",
            projectPath: aepPath,
            projectName: proj.file ? proj.file.name : "untitled",
            numItems: proj.numItems,
            comps: [],
            footage: [],
            folders: []
        };

        for (var i = 1; i <= proj.numItems && i <= 200; i++) {
            var item = proj.item(i);
            if (item instanceof CompItem) {
                output.comps.push(analyzeComp(item));
            } else if (item instanceof FootageItem) {
                output.footage.push({
                    name: item.name,
                    file: item.file ? item.file.fsName : "none",
                    width: item.width,
                    height: item.height,
                    duration: item.duration,
                    fps: item.frameRate
                });
            } else if (item instanceof FolderItem) {
                output.folders.push({name: item.name, numItems: item.numItems});
            }
        }

        // 不关闭项目，让用户可以查看
        resultFile.write(JSON.stringify(output, null, 2));
        resultFile.close();
        
    } catch(e) {
        try { app.endSuppressDialogs(); } catch(e2) {}
        try {
            resultFile.write(JSON.stringify({status:"error", message:e.toString(), line:e.line}));
            resultFile.close();
        } catch(e3) {}
    }
})();
