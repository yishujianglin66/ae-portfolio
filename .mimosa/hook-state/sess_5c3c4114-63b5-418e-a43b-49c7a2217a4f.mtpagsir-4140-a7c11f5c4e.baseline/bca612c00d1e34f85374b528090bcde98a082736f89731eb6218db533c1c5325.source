// Phase 2 验证脚本
var compName = "E2E_VinlandSaga";
var layerName = "MainVideo";
var result = {};

var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {
    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {
        comp = app.project.item(i); break;
    }
}

if (!comp) {
    result.error = "Comp not found";
} else {
    var layer = null;
    for (var j = 1; j <= comp.numLayers; j++) {
        if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }
    }

    if (!layer) {
        result.error = "Layer not found";
    } else {
        // 检查关键帧数量
        result.scaleKeys = layer.property("Scale").numKeys;
        result.opacityKeys = layer.property("Opacity").numKeys;
        result.rotationKeys = layer.property("Rotation").numKeys;

        // 检查表达式
        result.hasOpacityExpr = layer.property("Opacity").expression.length > 0;
        result.hasRotationExpr = layer.property("Rotation").expression.length > 0;

        // 检查 Audio Controller
        var ctrl = null;
        for (var c = 1; c <= comp.numLayers; c++) {
            if (comp.layer(c).name === "Audio Controller") { ctrl = comp.layer(c); break; }
        }
        result.hasAudioController = ctrl !== null;
        if (ctrl) {
            result.controllerEffects = ctrl.property("Effects").numProperties;
        }

        // 检查 Glow 表达式
        var glowExpr = false;
        for (var e = 1; e <= layer.property("Effects").numProperties; e++) {
            var eff = layer.property("Effects").property(e);
            if (eff.matchName.indexOf("Glo") >= 0) {
                try {
                    var gp = eff.property("Glow Threshold") || eff.property(1);
                    if (gp && gp.expression.length > 0) glowExpr = true;
                } catch(ex) {}
            }
        }
        result.hasGlowExpr = glowExpr;
    }
}

return JSON.stringify(result);
