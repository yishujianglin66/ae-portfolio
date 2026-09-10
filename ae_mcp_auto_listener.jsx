{
    if (typeof JSON === "undefined") { JSON = {}; }
    if (typeof JSON.parse !== "function") {
        JSON.parse = (function () {
            var at, ch, text;
            var escapee = {
                '"': '"', "\\": "\\", "/": "/",
                b: "\b", f: "\f", n: "\n", r: "\r",
                t: "\t"
            };
            function error(m) {
                var e = new Error(m);
                e.name = "SyntaxError";
                throw e;
            }
            function next(c) {
                if (c && c !== ch) {
                    error("Expected '" + c + "' instead of '" +
                        ch + "'");
                }
                ch = text.charAt(at);
                at++;
                return ch;
            }
            function number() {
                var s = "";
                if (ch === "-") { s = "-"; next("-"); }
                while (ch >= "0" && ch <= "9") {
                    s += ch; next();
                }
                if (ch === ".") {
                    s += ".";
                    while (next() && ch >= "0" && ch <= "9") {
                        s += ch;
                    }
                }
                if (ch === "e" || ch === "E") {
                    s += ch; next();
                    if (ch === "-" || ch === "+") {
                        s += ch; next();
                    }
                    while (ch >= "0" && ch <= "9") { s += ch; }
                }
                var n = +s;
                if (!isFinite(n)) error("Bad number");
                return n;
            }
            function string() {
                var s = "";
                if (ch === '"') {
                    while (next()) {
                        if (ch === '"') { next(); return s; }
                        if (ch === "\\") {
                            next();
                            if (ch === "u") {
                                var u = 0;
                                for (var i = 0; i < 4; i++) {
                                    var h = parseInt(next(), 16);
                                    if (!isFinite(h)) break;
                                    u = u * 16 + h;
                                }
                                s += String.fromCharCode(u);
                            } else if (typeof escapee[ch] ===
                                "string") {
                                s += escapee[ch];
                            } else break;
                        } else s += ch;
                    }
                }
                error("Bad string");
            }
            function white() {
                while (ch && ch <= " ") next();
            }
            function word() {
                switch (ch) {
                case "t":
                    next("t"); next("r"); next("u");
                    next("e");
                    return true;
                case "f":
                    next("f"); next("a"); next("l");
                    next("s"); next("e");
                    return false;
                case "n":
                    next("n"); next("u"); next("l");
                    next("l");
                    return null;
                }
                error("Unexpected '" + ch + "'");
            }
            function val() {
                white();
                switch (ch) {
                case "{": return obj();
                case "[": return arr();
                case '"': return string();
                case "-": return number();
                default:
                    return ch >= "0" && ch <= "9" ?
                        number() : word();
                }
            }
            function arr() {
                var a = [];
                if (ch === "[") {
                    next("["); white();
                    if (ch === "]") { next("]"); return a; }
                    while (ch) {
                        a.push(val()); white();
                        if (ch === "]") { next("]"); return a; }
                        next(","); white();
                    }
                }
                error("Bad array");
            }
            function obj() {
                var k, o = {};
                if (ch === "{") {
                    next("{"); white();
                    if (ch === "}") { next("}"); return o; }
                    while (ch) {
                        k = string(); white(); next(":");
                        if (Object.hasOwnProperty.call(o, k)) {
                            error("Duplicate key '" + k + "'");
                        }
                        o[k] = val(); white();
                        if (ch === "}") { next("}"); return o; }
                        next(","); white();
                    }
                }
                error("Bad object");
            }
            return function (source) {
                text = String(source);
                at = 0;
                ch = " ";
                var result = val();
                white();
                if (ch) error("Syntax error");
                return result;
            };
        })();
    }
    if (typeof JSON.stringify !== "function") {
        JSON.stringify = function (obj) {
            function toStr(v) {
                if (v === null) return "null";
                if (typeof v === "boolean") {
                    return v ? "true" : "false";
                }
                if (typeof v === "number") {
                    return isFinite(v) ? String(v) : "null";
                }
                if (typeof v === "string") {
                    var s = '"', i, ch;
                    for (i = 0; i < v.length; i++) {
                        ch = v.charAt(i);
                        switch (ch) {
                        case '"': s += '\\"'; break;
                        case '\\': s += '\\\\'; break;
                        case '\b': s += '\\b'; break;
                        case '\f': s += '\\f'; break;
                        case '\n': s += '\\n'; break;
                        case '\r': s += '\\r'; break;
                        case '\t': s += '\\t'; break;
                        default:
                            if (ch < ' ') {
                                var hex = ch.charCodeAt(0)
                                    .toString(16);
                                s += '\\u' +
                                    ('0000' + hex).slice(-4);
                            } else { s += ch; }
                        }
                    }
                    return s + '"';
                }
                if (v instanceof Array) {
                    var a = [];
                    for (var i = 0; i < v.length; i++) {
                        a.push(toStr(v[i]));
                    }
                    return "[" + a.join(",") + "]";
                }
                if (typeof v === "object") {
                    var p = [];
                    for (var k in v) {
                        if (Object.hasOwnProperty.call(v, k)) {
                            p.push(toStr(k) + ":" +
                                toStr(v[k]));
                        }
                    }
                    return "{" + p.join(",") + "}";
                }
                return "null";
            }
            return toStr(obj);
        };
    }

    function startMcpListener() {
    // ===== File path constants =====
    var PROJ_ROOT =
        "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
    var BASE_DIR = PROJ_ROOT + "/.ae-mcp-bridge";
    var CMD_FILE = BASE_DIR + "/ae_command.json";
    var RES_FILE = BASE_DIR + "/ae_result.json";
    var LOG_FILE = BASE_DIR + "/ae_auto_listener.log";
    var isRunning = true;
    var lastCmdTime = 0;

    // ===== Helper functions =====
    function log(msg) {
        try {
            var f = new File(LOG_FILE);
            f.encoding = "UTF-8";
            f.open("a");
            var now = new Date();
            var ts = now.getFullYear() + "-" +
                (now.getMonth() + 1) + "-" + now.getDate() +
                " " + now.getHours() + ":" + now.getMinutes() +
                ":" + now.getSeconds();
            f.write("[" + ts + "] " + msg + "\n");
            f.close();
        } catch (e) {}
    }

    function readJSON(path) {
        var f = new File(path);
        if (!f.exists) return null;
        f.encoding = "UTF-8";
        f.open("r");
        var txt = f.read();
        f.close();
        try { return JSON.parse(txt); } catch (e) {
            return null;
        }
    }

    function writeJSON(path, obj) {
        var f = new File(path);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(JSON.stringify(obj));
        f.close();
    }

    function findCompByName(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem &&
                item.name === name) {
                return item;
            }
        }
        return null;
    }

    function findLayerByName(comp, name) {
        for (var i = 1; i <= comp.numLayers; i++) {
            var layer = comp.layer(i);
            if (layer.name === name) {
                return layer;
            }
        }
        return null;
    }

    function executeScript(scriptStr) {
        return eval(scriptStr);
    }

    // ===== Command handlers =====

    function handlePing() {
        return {
            pong: true,
            appName: app.name,
            appVersion: app.version
        };
    }

    function handleGetProjectInfo() {
        var project = app.project;
        var items = [];
        for (var i = 1; i <= project.numItems; i++) {
            var item = project.item(i);
            items.push({
                id: item.id,
                name: item.name,
                type: item.typename
            });
        }
        return {
            projectName: project.name,
            path: project.file ? project.file.fsName : "",
            numItems: project.numItems,
            bitsPerChannel: project.bitsPerChannel,
            timeMode: project.timeMode.toString(),
            items: items
        };
    }

    function handleListCompositions() {
        var comps = [];
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem) {
                comps.push({
                    id: item.id,
                    name: item.name,
                    duration: item.duration,
                    frameRate: item.frameRate,
                    width: item.width,
                    height: item.height,
                    numLayers: item.numLayers
                });
            }
        }
        return { compositions: comps };
    }

    function handleCreateComposition(args) {
        try {
            var name = args.name || "New Comp";
            var w = args.width || 1920;
            var h = args.height || 1080;
            var dur = args.duration || 10;
            var fps = args.frameRate || 30;
            var bg = args.bgColor || [0, 0, 0];
            var comp = app.project.items.addComp(
                name, w, h, 1, dur, fps
            );
            comp.bgColor = bg;
            return {
                name: comp.name,
                width: comp.width,
                height: comp.height,
                duration: comp.duration,
                frameRate: comp.frameRate
            };
        } catch (e) {
            throw new Error("createComposition: " +
                e.toString());
        }
    }

    function handleImportFootage(args) {
        try {
            var fp = args.filePath || "";
            var asSeq = args.importAsSequence || false;
            if (!fp) throw new Error("filePath required");
            var f = new File(fp);
            if (!f.exists) {
                throw new Error("File not found: " + fp);
            }
            var io = new ImportOptions(f);
            io.sequence = asSeq;
            var item = app.project.importFile(io);
            return {
                name: item.name,
                type: item.typename,
                id: item.id
            };
        } catch (e) {
            throw new Error("importFootage: " + e.toString());
        }
    }

    function handleAddLayerToComp(args) {
        try {
            var compName = args.compName || "";
            var ftName = args.footageName || "";
            var lName = args.layerName || "";
            var st = args.startTime || 0;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var footage = null;
            for (var i = 1; i <= app.project.numItems; i++)
            {
                var item = app.project.item(i);
                if (item.name === ftName) {
                    footage = item; break;
                }
            }
            if (!footage) {
                throw new Error("Footage not found: " +
                    ftName);
            }
            var layer = comp.layers.add(footage);
            if (lName) layer.name = lName;
            if (st !== 0) layer.startTime = st;
            return {
                layer: layer.name,
                index: layer.index,
                comp: comp.name
            };
        } catch (e) {
            throw new Error("addLayerToComp: " +
                e.toString());
        }
    }

    function handlePrecompose(args) {
        try {
            var compName = args.compName || "";
            var layerNames = args.layerNames || [];
            var pcName = args.precompName || "Precomp";
            var moveAll = args.moveAllAttrs !== false;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layerIndices = [];
            for (var i = 0; i < layerNames.length; i++)
            {
                var lyr = findLayerByName(comp,
                    layerNames[i]);
                if (lyr) layerIndices.push(lyr.index);
            }
            if (layerIndices.length === 0) {
                throw new Error("No valid layers found");
            }
            for (var i = 1; i <= comp.numLayers; i++) {
                comp.layer(i).selected = false;
            }
            for (var i = 0; i < layerIndices.length; i++)
            {
                comp.layer(layerIndices[i]).selected = true;
            }
            var pc = comp.layers.precompose(
                layerIndices, pcName, moveAll
            );
            return {
                precompName: pcName,
                precompId: pc.id
            };
        } catch (e) {
            throw new Error("precompose: " + e.toString());
        }
    }

    function handleSetExpression(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var propName = args.propertyName || "";
            var expr = args.expressionText || "";
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            var prop = layer.property(propName);
            if (!prop) {
                throw new Error("Property not found: " +
                    propName);
            }
            prop.expression = expr;
            return {
                layer: layerName,
                property: propName,
                expression: expr
            };
        } catch (e) {
            throw new Error("setExpression: " +
                e.toString());
        }
    }

    function handleSetBlendingMode(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var bmStr = args.blendingMode || "NORMAL";
            var bmMap = {
                "NORMAL": BlendingMode.NORMAL,
                "ADD": BlendingMode.ADD,
                "MULTIPLY": BlendingMode.MULTIPLY,
                "SCREEN": BlendingMode.SCREEN,
                "OVERLAY": BlendingMode.OVERLAY,
                "DARKEN": BlendingMode.DARKEN,
                "LIGHTEN": BlendingMode.LIGHTEN,
                "COLORDODGE":
                    BlendingMode.COLOR_DODGE,
                "COLORBURN":
                    BlendingMode.COLOR_BURN,
                "HARDLIGHT":
                    BlendingMode.HARD_LIGHT,
                "SOFTLIGHT":
                    BlendingMode.SOFT_LIGHT,
                "DIFFERENCE":
                    BlendingMode.DIFFERENCE,
                "EXCLUSION":
                    BlendingMode.EXCLUSION,
                "HUE": BlendingMode.HUE,
                "SATURATION":
                    BlendingMode.SATURATION,
                "COLOR": BlendingMode.COLOR,
                "LUMINOSITY":
                    BlendingMode.LUMINOSITY,
                "DISSOLVE": BlendingMode.DISSOLVE,
                "STENCILALPHA":
                    BlendingMode.STENCIL_ALPHA,
                "STENCILLUMA":
                    BlendingMode.STENCIL_LUMA,
                "SILHOUETTEALPHA":
                    BlendingMode.SILHOUETTE_ALPHA,
                "SILHOUETTELUMA":
                    BlendingMode.SILHOUETTE_LUMA,
                "ALPHAADD":
                    BlendingMode.ALPHA_ADD,
                "ALPHAIllum":
                    BlendingMode.ALPHA_ILLUMINATE
            };
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            var bm = bmMap[bmStr.toUpperCase()];
            if (bm === undefined) {
                throw new Error(
                    "Unknown blending mode: " + bmStr
                );
            }
            layer.blendingMode = bm;
            return {
                layer: layerName,
                blendingMode: bmStr
            };
        } catch (e) {
            throw new Error("setBlendingMode: " +
                e.toString());
        }
    }

    function handleAddMask(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var maskName = args.maskName || "Mask 1";
            var shape = args.maskShape || "rect";
            var feather = args.maskFeather || 0;
            var opacity = args.maskOpacity || 100;
            var modeStr = args.maskMode || "add";
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            var mask = layer.property(
                "ADBE Mask Parade"
            ).addProperty("ADBE Mask Atom");
            if (maskName) mask.name = maskName;
            var modeMap = {
                "add": MaskMode.ADD,
                "subtract": MaskMode.SUBTRACT,
                "intersect": MaskMode.INTERSECT,
                "difference": MaskMode.DIFFERENCE,
                "none": MaskMode.NONE
            };
            var mm = modeMap[modeStr.toLowerCase()];
            if (mm !== undefined) mask.maskMode = mm;
            var w = layer.width || comp.width;
            var h = layer.height || comp.height;
            var shapeProp = mask.property(
                "ADBE Mask Shape"
            );
            var newShape = new Shape();
            if (shape === "rect") {
                newShape.vertices = [
                    [0 - w / 2, 0 - h / 2],
                    [w - w / 2, 0 - h / 2],
                    [w - w / 2, h - h / 2],
                    [0 - w / 2, h - h / 2]
                ];
                newShape.inTangents = [
                    [0, 0], [0, 0], [0, 0], [0, 0]
                ];
                newShape.outTangents = [
                    [0, 0], [0, 0], [0, 0], [0, 0]
                ];
                newShape.closed = true;
            } else if (shape === "ellipse") {
                var cx = 0, cy = 0;
                var rx = w / 2, ry = h / 2;
                var k = 0.5522847498;
                newShape.vertices = [
                    [cx, cy - ry],
                    [cx + rx, cy],
                    [cx, cy + ry],
                    [cx - rx, cy]
                ];
                newShape.inTangents = [
                    [-rx * k, 0], [0, -ry * k],
                    [rx * k, 0], [0, ry * k]
                ];
                newShape.outTangents = [
                    [rx * k, 0], [0, ry * k],
                    [-rx * k, 0], [0, -ry * k]
                ];
                newShape.closed = true;
            } else {
                newShape.vertices = [
                    [0 - w / 2, 0 - h / 2],
                    [w - w / 2, 0 - h / 2],
                    [w - w / 2, h - h / 2],
                    [0 - w / 2, h - h / 2]
                ];
                newShape.inTangents = [
                    [0, 0], [0, 0], [0, 0], [0, 0]
                ];
                newShape.outTangents = [
                    [0, 0], [0, 0], [0, 0], [0, 0]
                ];
                newShape.closed = true;
            }
            shapeProp.setValue(newShape);
            if (feather > 0) {
                mask.property(
                    "ADBE Mask Feather"
                ).setValue([feather, feather]);
            }
            mask.property(
                "ADBE Mask Opacity"
            ).setValue(opacity);
            return {
                mask: maskName,
                shape: shape,
                mode: modeStr
            };
        } catch (e) {
            throw new Error("addMask: " + e.toString());
        }
    }

    function handleAddTextLayer(args) {
        try {
            var compName = args.compName || "";
            var text = args.text || "Text";
            var lName = args.layerName || "";
            var fontSize = args.fontSize || 72;
            var fontName = args.fontName || "Arial";
            var fc = args.fillColor || [1, 1, 1];
            var pos = args.position || null;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var textDoc = new TextDocument(text);
            textDoc.fontSize = fontSize;
            textDoc.font = fontName;
            textDoc.fillColor = fc;
            var layer = comp.layers.addText(textDoc);
            if (lName) layer.name = lName;
            if (pos && pos.length >= 2) {
                layer.property("Position").setValue(pos);
            }
            return {
                layer: layer.name,
                index: layer.index,
                text: text
            };
        } catch (e) {
            throw new Error("addTextLayer: " +
                e.toString());
        }
    }

    function handleAddSolidLayer(args) {
        try {
            var compName = args.compName || "";
            var lName = args.layerName || "Solid";
            var w = args.width || 1920;
            var h = args.height || 1080;
            var color = args.color || [1, 0, 0];
            var dur = args.duration || 10;
            var isAdj = args.isAdjustment || false;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var solid = comp.layers.addSolid(
                color, lName, w, h, 1, dur
            );
            if (isAdj) solid.adjustmentLayer = true;
            return {
                layer: solid.name,
                index: solid.index,
                isAdjustment: isAdj
            };
        } catch (e) {
            throw new Error("addSolidLayer: " +
                e.toString());
        }
    }

    function handleAddShapeLayer(args) {
        try {
            var compName = args.compName || "";
            var lName = args.layerName || "Shape";
            var shapeType = args.shapeType || "rect";
            var size = args.size || 200;
            var fc = args.fillColor || [1, 1, 0];
            var sc = args.strokeColor || null;
            var sw = args.strokeWidth || 0;
            var pos = args.position || null;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = comp.layers.addShape();
            if (lName) layer.name = lName;
            if (pos && pos.length >= 2) {
                layer.property("Position").setValue(pos);
            }
            var grp = layer.property(
                "ADBE Root Vectors"
            ).addProperty("ADBE Vector Group");
            var contents = grp.property(
                "ADBE Vectors Group"
            );
            var pathGrp = contents.addProperty(
                "ADBE Vector Shape - Group"
            );
            var pathProp = pathGrp.property(
                "ADBE Vector Shape"
            );
            var newShape = new Shape();
            var half = size / 2;
            if (shapeType === "ellipse") {
                var k = 0.5522847498;
                newShape.vertices = [
                    [0, -half], [half, 0],
                    [0, half], [-half, 0]
                ];
                newShape.inTangents = [
                    [-half * k, 0], [0, -half * k],
                    [half * k, 0], [0, half * k]
                ];
                newShape.outTangents = [
                    [half * k, 0], [0, half * k],
                    [-half * k, 0], [0, -half * k]
                ];
            } else {
                newShape.vertices = [
                    [-half, -half], [half, -half],
                    [half, half], [-half, half]
                ];
                newShape.inTangents = [
                    [0, 0], [0, 0], [0, 0], [0, 0]
                ];
                newShape.outTangents = [
                    [0, 0], [0, 0], [0, 0], [0, 0]
                ];
            }
            newShape.closed = true;
            pathProp.setValue(newShape);
            var fill = contents.addProperty(
                "ADBE Vector Graphic - Fill"
            );
            fill.property(
                "ADBE Vector Fill Color"
            ).setValue(fc);
            if (sc && sw > 0) {
                var stroke = contents.addProperty(
                    "ADBE Vector Graphic - Stroke"
                );
                stroke.property(
                    "ADBE Vector Stroke Color"
                ).setValue(sc);
                stroke.property(
                    "ADBE Vector Stroke Width"
                ).setValue(sw);
            }
            return {
                layer: layer.name,
                index: layer.index,
                shapeType: shapeType
            };
        } catch (e) {
            throw new Error("addShapeLayer: " +
                e.toString());
        }
    }

    function handleSetLayer3D(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var is3D = args.is3D || false;
            var pos3D = args.position3D || null;
            var orient = args.orientation || null;
            var scale3D = args.scale3D || null;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            layer.threeDLayer = is3D;
            if (is3D && pos3D && pos3D.length >= 3) {
                layer.property("Position")
                    .setValue(pos3D);
            }
            if (is3D && orient && orient.length >= 3) {
                layer.property("Orientation")
                    .setValue(orient);
            }
            if (is3D && scale3D && scale3D.length >= 3) {
                layer.property("Scale")
                    .setValue(scale3D);
            }
            return {
                layer: layerName,
                is3D: is3D
            };
        } catch (e) {
            throw new Error("setLayer3D: " + e.toString());
        }
    }

    function handleAddCamera(args) {
        try {
            var compName = args.compName || "";
            var camName = args.cameraName || "Camera";
            var focal = args.focalLength || 50;
            var pos = args.position || null;
            var poi = args.pointOfInterest || null;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var cam = comp.layers.addCamera(
                camName,
                [comp.width / 2, comp.height / 2]
            );
            cam.property(
                "ADBE Camera Options Group"
            ).property(
                "ADBE Camera Focal Length"
            ).setValue(focal);
            if (pos && pos.length >= 3) {
                cam.property("Position").setValue(pos);
            }
            if (poi && poi.length >= 3) {
                cam.property(
                    "Point of Interest"
                ).setValue(poi);
            }
            return {
                camera: camName,
                index: cam.index,
                focalLength: focal
            };
        } catch (e) {
            throw new Error("addCamera: " + e.toString());
        }
    }

    function handleAddLight(args) {
        try {
            var compName = args.compName || "";
            var lName = args.lightName || "Light";
            var lType = args.lightType || "Point";
            var intensity = args.intensity || 100;
            var color = args.color || [1, 1, 1];
            var pos = args.position || null;
            var poi = args.pointOfInterest || null;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var typeMap = {
                "Point": LightType.POINT,
                "Spot": LightType.SPOT,
                "Parallel": LightType.PARALLEL,
                "Ambient": LightType.AMBIENT
            };
            var lt = typeMap[lType] || LightType.POINT;
            var center = [comp.width / 2, comp.height / 2];
            var light = comp.layers.addLight(
                lName, center
            );
            light.lightType = lt;
            light.property(
                "ADBE Light Options Group"
            ).property(
                "ADBE Light Intensity"
            ).setValue(intensity);
            light.property(
                "ADBE Light Options Group"
            ).property(
                "ADBE Light Color"
            ).setValue(color);
            if (pos && pos.length >= 3) {
                light.property("Position")
                    .setValue(pos);
            }
            if (poi && poi.length >= 3) {
                light.property(
                    "Point of Interest"
                ).setValue(poi);
            }
            return {
                light: lName,
                index: light.index,
                lightType: lType
            };
        } catch (e) {
            throw new Error("addLight: " + e.toString());
        }
    }

    function handleRenderQueue(args) {
        try {
            var compName = args.compName || "";
            var outPath = args.outputPath || "";
            var fmt = args.format || "h264";
            var startR = args.startRender !== false;
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            if (!outPath) {
                throw new Error("outputPath required");
            }
            var rqItem = app.project.renderQueue.items
                .add(comp);
            var tmplMap = {
                "h264": "H.264",
                "mov": "Lossless",
                "png": "PNG Sequence",
                "tiff": "TIFF Sequence"
            };
            var tmpl = tmplMap[fmt] || "H.264";
            var om = rqItem.outputModule(1);
            try {
                om.applyTemplate(tmpl);
            } catch (ex) {
                log("Template " + tmpl + " not found, " +
                    "using default");
            }
            om.file = new File(outPath);
            if (startR) {
                app.project.renderQueue.render();
            }
            return {
                comp: comp.name,
                outputPath: outPath,
                format: fmt,
                renderStarted: startR
            };
        } catch (e) {
            throw new Error("renderQueue: " +
                e.toString());
        }
    }

    function handleAddEffect(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var matchName = args.effectMatchName || "";
            var settings = args.effectSettings || {};
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            if (!matchName) {
                throw new Error(
                    "effectMatchName required"
                );
            }
            var effect = layer.property(
                "ADBE Effect Parade"
            ).addProperty(matchName);
            for (var key in settings) {
                if (settings.hasOwnProperty(key)) {
                    try {
                        var prop = effect.property(key);
                        if (prop) {
                            prop.setValue(settings[key]);
                        }
                    } catch (ex) {
                        log("Effect setting " + key +
                            " failed: " + ex.toString());
                    }
                }
            }
            return {
                effect: effect.name,
                matchName: matchName,
                layer: layerName
            };
        } catch (e) {
            throw new Error("addEffect: " + e.toString());
        }
    }

    function handleSetKeyframe(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var propName = args.propertyName || "";
            var time = args.timeInSeconds || 0;
            var value = args.value;
            var easeType = args.easeType || "linear";
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            var prop = layer.property(propName);
            if (!prop) {
                throw new Error(
                    "Property not found: " + propName
                );
            }
            if (value === undefined) {
                throw new Error("value required");
            }
            prop.setValueAtTime(time, value);
            if (easeType !== "linear") {
                var idx = prop.nearestKeyIndex(time);
                if (idx > 0) {
                    var easeIn = new KeyframeEase(0, 33);
                    var easeOut = new KeyframeEase(0, 33);
                    if (easeType === "easeIn") {
                        easeIn = new KeyframeEase(0, 75);
                    } else if (easeType === "easeOut") {
                        easeOut = new KeyframeEase(0, 75);
                    } else if (easeType === "easeInOut") {
                        easeIn = new KeyframeEase(0, 75);
                        easeOut = new KeyframeEase(0, 75);
                    }
                    try {
                        prop.setTemporalEaseAtKey(
                            idx, [easeIn], [easeOut]
                        );
                    } catch (ex) {
                        log("Ease failed: " +
                            ex.toString());
                    }
                }
            }
            return {
                layer: layerName,
                property: propName,
                time: time,
                easeType: easeType
            };
        } catch (e) {
            throw new Error("setKeyframe: " +
                e.toString());
        }
    }

    function handleSetKeyframeBatch(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var keyframes = args.keyframes || [];
            var expressions = args.expressions || {};
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            var written = 0;
            var failed = 0;
            var failList = [];
            for (var i = 0; i < keyframes.length; i++) {
                try {
                    var kf = keyframes[i];
                    var propName = kf.property || "";
                    var time = kf.time || 0;
                    var val = kf.value;
                    var easeType = kf.easeType ||
                        "linear";
                    var prop = layer.property(propName);
                    if (!prop) {
                        failed++;
                        failList.push(propName + 
                            " not found");
                        continue;
                    }
                    prop.setValueAtTime(time, val);
                    if (easeType !== "linear") {
                        var idx = prop.nearestKeyIndex(
                            time);
                        if (idx > 0) {
                            var easeIn = new
                                KeyframeEase(0, 33);
                            var easeOut = new
                                KeyframeEase(0, 33);
                            if (easeType === "easeIn") {
                                easeIn = new
                                    KeyframeEase(0, 75);
                            } else if (easeType ===
                                "easeOut") {
                                easeOut = new
                                    KeyframeEase(0, 75);
                            } else if (easeType ===
                                "easeInOut") {
                                easeIn = new
                                    KeyframeEase(0, 75);
                                easeOut = new
                                    KeyframeEase(0, 75);
                            }
                            try {
                                prop.setTemporalEaseAtKey(
                                    idx, [easeIn],
                                    [easeOut]
                                );
                            } catch (ex) {
                                log("Ease failed: " +
                                    ex.toString());
                            }
                        }
                    }
                    written++;
                } catch (ex2) {
                    failed++;
                    failList.push("kf " + i + ": " +
                        ex2.toString());
                }
            }
            for (var expKey in expressions) {
                if (expressions.hasOwnProperty(expKey)) {
                    try {
                        var expProp = layer.property(
                            expKey);
                        if (expProp) {
                            expProp.expression =
                                expressions[expKey];
                        }
                    } catch (ex3) {
                        failList.push("exp " + expKey +
                            ": " + ex3.toString());
                    }
                }
            }
            return {
                layer: layerName,
                written: written,
                failed: failed,
                total: keyframes.length,
                failures: failList
            };
        } catch (e) {
            throw new Error("setKeyframeBatch: " +
                e.toString());
        }
    }

    function handleGetLayerProperties(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var propNames = args.propertyNames || [];
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            var result = {};
            for (var i = 0; i < propNames.length; i++) {
                var pn = propNames[i];
                try {
                    var prop = layer.property(pn);
                    if (prop) {
                        result[pn] = prop.value;
                    }
                } catch (ex) {
                    result[pn] = "Error: " + ex.toString();
                }
            }
            return {
                layer: layerName,
                properties: result
            };
        } catch (e) {
            throw new Error(
                "getLayerProperties: " + e.toString()
            );
        }
    }

    function handleApplyPreset(args) {
        try {
            var compName = args.compName || "";
            var layerName = args.layerName || "";
            var presetPath = args.presetPath || "";
            var comp = compName ?
                findCompByName(compName) :
                app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " +
                    layerName);
            }
            if (!presetPath) {
                throw new Error("presetPath required");
            }
            var presetFile = new File(presetPath);
            if (!presetFile.exists) {
                throw new Error(
                    "Preset not found: " + presetPath
                );
            }
            layer.applyPreset(presetFile);
            return {
                layer: layerName,
                presetPath: presetPath
            };
        } catch (e) {
            throw new Error("applyPreset: " +
                e.toString());
        }
    }

    function handleExecuteAtomScript(args) {
        try {
            var script = args.script || "";
            if (!script) {
                throw new Error("script required");
            }
            var result = executeScript(script);
            return {
                executed: true,
                result: result
            };
        } catch (e) {
            throw new Error("executeAtomScript: " +
                e.toString());
        }
    }

    // ===== Command Router =====
    function processCommand() {
        var data = readJSON(CMD_FILE);
        if (!data) return false;
        if (data.processed) return false;

        data.processed = true;
        writeJSON(CMD_FILE, data);

        log("Executing: " +
            (data.description || data.command));

        try {
            var result = null;
            var args = data.args || {};

            if (data.command === "ping") {
                result = handlePing();
            } else if (data.command ===
                "getProjectInfo") {
                result = handleGetProjectInfo();
            } else if (data.command ===
                "listCompositions") {
                result = handleListCompositions();
            } else if (data.command ===
                "createComposition") {
                result = handleCreateComposition(args);
            } else if (data.command ===
                "importFootage") {
                result = handleImportFootage(args);
            } else if (data.command ===
                "addLayerToComp") {
                result = handleAddLayerToComp(args);
            } else if (data.command === "precompose") {
                result = handlePrecompose(args);
            } else if (data.command ===
                "setExpression") {
                result = handleSetExpression(args);
            } else if (data.command ===
                "setBlendingMode") {
                result = handleSetBlendingMode(args);
            } else if (data.command === "addMask") {
                result = handleAddMask(args);
            } else if (data.command === "addTextLayer") {
                result = handleAddTextLayer(args);
            } else if (data.command === "addSolidLayer")
            {
                result = handleAddSolidLayer(args);
            } else if (data.command === "addShapeLayer")
            {
                result = handleAddShapeLayer(args);
            } else if (data.command === "setLayer3D") {
                result = handleSetLayer3D(args);
            } else if (data.command === "addCamera") {
                result = handleAddCamera(args);
            } else if (data.command === "addLight") {
                result = handleAddLight(args);
            } else if (data.command === "renderQueue") {
                result = handleRenderQueue(args);
            } else if (data.command === "addEffect") {
                result = handleAddEffect(args);
            } else if (data.command === "setKeyframe") {
                result = handleSetKeyframe(args);
            } else if (data.command ===
                "setKeyframeBatch") {
                result = handleSetKeyframeBatch(args);
            } else if (data.command ===
                "getLayerProperties") {
                result = handleGetLayerProperties(args);
            } else if (data.command === "applyPreset") {
                result = handleApplyPreset(args);
            } else if (data.command ===
                "executeAtomScript" ||
                data.command === "execute_script") {
                result = handleExecuteAtomScript(args);
            } else {
                throw new Error(
                    "Unknown command: " + data.command
                );
            }

            var d = new Date();
            var ts = d.getFullYear() + "-" +
                (d.getMonth()+1) + "-" + d.getDate() +
                " " + d.getHours() + ":" +
                d.getMinutes() + ":" + d.getSeconds();
            writeJSON(RES_FILE, {
                status: "success",
                result: result || {},
                timestamp: ts
            });
            log("Success");
        } catch (e) {
            var d2 = new Date();
            var ts2 = d2.getFullYear() + "-" +
                (d2.getMonth()+1) + "-" + d2.getDate() +
                " " + d2.getHours() + ":" +
                d2.getMinutes() + ":" + d2.getSeconds();
            writeJSON(RES_FILE, {
                status: "error",
                message: e.toString(),
                line: e.line,
                timestamp: ts2
            });
            log("Error: " + e.toString() +
                " (line " + e.line + ")");
        }

        return true;
    }

    // ===== Polling loop =====
    function checkForCommands() {
        if (!isRunning) return;
        try {
            var f = new File(CMD_FILE);
            if (f.exists) {
                var mtime = f.modified;
                if (mtime &&
                    mtime.getTime() !== lastCmdTime) {
                    lastCmdTime = mtime.getTime();
                    processCommand();
                }
            }
        } catch (e) {
            log("Loop error: " + e.toString());
        }
        // 2026-09-10 实证：单发自续链（..., false）在本机 AE2025 首次后即死，
        // recurring=true 才存活——故自续调度移除，启动处统一挂 recurring（防任务增殖）。
    }

    // Expose to global scope so scheduleTask string eval can find it
    $.global.checkForCommands = checkForCommands;

    // ===== Startup log =====
    log("========================================");
    log("AE MCP Auto Listener started");
    log("AE: " + app.name + " " + app.version);
    log("CMD_FILE: " + CMD_FILE);
    log("RES_FILE: " + RES_FILE);
    log("========================================");

    log("Starting command polling loop (recurring)");
    checkForCommands();
    app.scheduleTask(
        "$.global.checkForCommands()", 500, true
    );
    } // end startMcpListener
}

// Export for Startup delayed loading
$.global.__startMcpPolling = startMcpListener;

// Auto-start on script load/reload
startMcpListener();
