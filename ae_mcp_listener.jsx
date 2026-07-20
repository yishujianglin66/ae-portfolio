    if (typeof JSON === "undefined") { JSON = {}; }
    if (typeof JSON.parse !== "function") {
        JSON.parse = (function () {
            var at, ch, text;
            var escapee = {'"':'"',"\\":"\\","/":"/",b:"\b",f:"\f",n:"\n",r:"\r",t:"\t"};
            function error(m) { var e = new Error(m); e.name = "SyntaxError"; throw e; }
            function next(c) { if (c && c !== ch) error("Expected '"+c+"' instead of '"+ch+"'"); ch = text.charAt(at); at++; return ch; }
            function number() {
                var s = "";
                if (ch === "-") { s = "-"; next("-"); }
                while (ch >= "0" && ch <= "9") { s += ch; next(); }
                if (ch === ".") { s += "."; while (next() && ch >= "0" && ch <= "9") s += ch; }
                if (ch === "e" || ch === "E") { s += ch; next(); if (ch === "-" || ch === "+") { s += ch; next(); } while (ch >= "0" && ch <= "9") { s += ch; next(); } }
                var n = +s; if (!isFinite(n)) error("Bad number"); return n;
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
                                for (var i = 0; i < 4; i++) { var h = parseInt(next(), 16); if (!isFinite(h)) break; u = u * 16 + h; }
                                s += String.fromCharCode(u);
                            } else if (typeof escapee[ch] === "string") { s += escapee[ch]; } else break;
                        } else s += ch;
                    }
                }
                error("Bad string");
            }
            function white() { while (ch && ch <= " ") next(); }
            function word() {
                switch (ch) {
                case "t": next("t"); next("r"); next("u"); next("e"); return true;
                case "f": next("f"); next("a"); next("l"); next("s"); next("e"); return false;
                case "n": next("n"); next("u"); next("l"); next("l"); return null;
                }
                error("Unexpected '"+ch+"'");
            }
            function val() { white(); switch (ch) { case "{": return obj(); case "[": return arr(); case '"': return string(); case "-": return number(); default: return ch >= "0" && ch <= "9" ? number() : word(); } }
            function arr() {
                var a = [];
                if (ch === "[") {
                    next("["); white(); if (ch === "]") { next("]"); return a; }
                    while (ch) { a.push(val()); white(); if (ch === "]") { next("]"); return a; } next(","); white(); }
                }
                error("Bad array");
            }
            function obj() {
                var k, o = {};
                if (ch === "{") {
                    next("{"); white(); if (ch === "}") { next("}"); return o; }
                    while (ch) {
                        k = string(); white(); next(":");
                        if (Object.hasOwnProperty.call(o, k)) error("Duplicate key '"+k+"'");
                        o[k] = val(); white();
                        if (ch === "}") { next("}"); return o; }
                        next(","); white();
                    }
                }
                error("Bad object");
            }
            return function (source) {
                text = String(source); at = 0; ch = " ";
                var result = val(); white();
                if (ch) error("Syntax error");
                return result;
            };
        })();
    }
    if (typeof JSON.stringify !== "function") {
        JSON.stringify = function(obj) {
            function esc(s) { return (s+"").replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t"); }
            function toStr(v) {
                if (v===null||v===undefined) return "null";
                var t=typeof v;
                if (t==="number"||t==="boolean") return String(v);
                if (t==="string") return '"'+esc(v)+'"';
                if (v instanceof Array) { var a=[]; for(var i=0;i<v.length;i++) a.push(toStr(v[i])); return "["+a.join(",")+"]"; }
                if (t==="object") { var p=[]; for(var k in v) if(v.hasOwnProperty(k)&&typeof v[k]!=="function"&&typeof v[k]!=="undefined") p.push('"'+esc(k)+'":'+toStr(v[k])); return "{"+p.join(",")+"}"; }
                return "null";
            }
            return toStr(obj);
        };
    }

    var CMD_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json";
    var RES_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json";
    var lastCmdTime = 0;
    var isRunning = true;

    // ========== 签名验证配置 ==========
    // 从配置文件读取密钥（如果存在）
    var SECRET_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.mcp_secret";
    var MCP_SECRET = "";
    var SIGNATURE_ENABLED = true;
    var MAX_TIMESTAMP_DIFF = 300; // 5 分钟

    function _loadSecret() {
        var f = new File(SECRET_FILE);
        if (f.exists) {
            f.encoding = "UTF-8";
            f.open("r");
            var content = f.read();
            f.close();
            if (content) {
                MCP_SECRET = content.replace(/\s+$/, "");
            }
        }
    }
    _loadSecret();

    // ========== SHA-256 实现（用于 HMAC 验证） ==========
    function _sha256(message) {
        function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }
        function ch(x, y, z) { return (x & y) ^ (~x & z); }
        function maj(x, y, z) { return (x & y) ^ (x & z) ^ (y & z); }
        function sig0(x) { return rotr(2, x) ^ rotr(13, x) ^ rotr(22, x); }
        function sig1(x) { return rotr(6, x) ^ rotr(11, x) ^ rotr(25, x); }
        function gam0(x) { return rotr(7, x) ^ rotr(18, x) ^ (x >>> 3); }
        function gam1(x) { return rotr(17, x) ^ rotr(19, x) ^ (x >>> 10); }

        var K = [
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
        ];

        var h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
        var h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

        function strToBytes(str) {
            var bytes = [];
            for (var i = 0; i < str.length; i++) {
                var c = str.charCodeAt(i);
                if (c < 0x80) {
                    bytes.push(c);
                } else if (c < 0x800) {
                    bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
                } else {
                    bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
                }
            }
            return bytes;
        }

        var msg = strToBytes(message);
        var bitLen = msg.length * 8;

        msg.push(0x80);
        while ((msg.length % 64) !== 56) msg.push(0);
        for (var i = 0; i < 8; i++) {
            msg.push(i < 4 ? 0 : (bitLen >>> (8 * (7 - i))) & 0xff);
        }

        for (var offset = 0; offset < msg.length; offset += 64) {
            var w = new Array(64);
            for (var j = 0; j < 16; j++) {
                w[j] = (msg[offset + 4*j] << 24) | (msg[offset + 4*j + 1] << 16) |
                       (msg[offset + 4*j + 2] << 8) | msg[offset + 4*j + 3];
            }
            for (var j = 16; j < 64; j++) {
                w[j] = (gam1(w[j-2]) + w[j-7] + gam0(w[j-15]) + w[j-16]) | 0;
            }

            var a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;

            for (var t = 0; t < 64; t++) {
                var t1 = (h + sig1(e) + ch(e, f, g) + K[t] + w[t]) | 0;
                var t2 = (sig0(a) + maj(a, b, c)) | 0;
                h = g; g = f; f = e; e = (d + t1) | 0;
                d = c; c = b; b = a; a = (t1 + t2) | 0;
            }

            h0 = (h0 + a) | 0; h1 = (h1 + b) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0;
            h4 = (h4 + e) | 0; h5 = (h5 + f) | 0; h6 = (h6 + g) | 0; h7 = (h7 + h) | 0;
        }

        function toHex(n) {
            var s = "";
            for (var i = 7; i >= 0; i--) {
                s += ((n >>> (i * 4)) & 0xf).toString(16);
            }
            return s;
        }

        return toHex(h0) + toHex(h1) + toHex(h2) + toHex(h3) +
               toHex(h4) + toHex(h5) + toHex(h6) + toHex(h7);
    }

    function _hmacSha256(key, message) {
        var blockSize = 64;
        var keyBytes = [];
        for (var i = 0; i < key.length; i++) {
            var c = key.charCodeAt(i);
            if (c < 0x80) {
                keyBytes.push(c);
            } else if (c < 0x800) {
                keyBytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
            } else {
                keyBytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
            }
        }
        if (keyBytes.length > blockSize) {
            var hexHash = _sha256(key);
            keyBytes = [];
            for (var i = 0; i < hexHash.length; i += 2) {
                keyBytes.push(parseInt(hexHash.substr(i, 2), 16));
            }
        }
        while (keyBytes.length < blockSize) keyBytes.push(0);

        var oKeyPad = "";
        var iKeyPad = "";
        for (var i = 0; i < blockSize; i++) {
            oKeyPad += String.fromCharCode(keyBytes[i] ^ 0x5c);
            iKeyPad += String.fromCharCode(keyBytes[i] ^ 0x36);
        }

        return _sha256(oKeyPad + _sha256(iKeyPad + message));
    }

    // ========== 规范 JSON 序列化（用于签名验证） ==========
    function _canonicalize(obj) {
        if (obj === null || obj === undefined) return "null";
        var t = typeof obj;
        if (t === "number" || t === "boolean") return String(obj);
        if (t === "string") {
            function esc(s) { return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t"); }
            return '"' + esc(obj) + '"';
        }
        if (obj instanceof Array) {
            var a = [];
            for (var i = 0; i < obj.length; i++) a.push(_canonicalize(obj[i]));
            return "[" + a.join(",") + "]";
        }
        if (t === "object") {
            var keys = [];
            for (var k in obj) {
                if (obj.hasOwnProperty(k) && typeof obj[k] !== "function" && typeof obj[k] !== "undefined") {
                    keys.push(k);
                }
            }
            keys.sort();
            var pairs = [];
            function esk(s) { return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t"); }
            for (var i = 0; i < keys.length; i++) {
                pairs.push('"' + esk(keys[i]) + '":' + _canonicalize(obj[keys[i]]));
            }
            return "{" + pairs.join(",") + "}";
        }
        return "null";
    }

    // ========== 签名验证函数 ==========
    function verifySignature(data) {
        if (!SIGNATURE_ENABLED) {
            return true;
        }
        if (!MCP_SECRET || MCP_SECRET.length === 0) {
            log("No secret key found - signature verification FAILED (fail-closed)");
            return false;
        }
        if (!data || !data.signature || !data.timestamp) {
            return false;
        }

        var ts = parseInt(data.timestamp);
        if (isNaN(ts)) {
            var dateTs = new Date(data.timestamp).getTime();
            if (isNaN(dateTs)) return false;
            ts = Math.floor(dateTs / 1000);
        }
        var now = Math.floor(new Date().getTime() / 1000);
        if (Math.abs(now - ts) > MAX_TIMESTAMP_DIFF) {
            log("Signature verification failed: timestamp out of range");
            return false;
        }

        var verifyData = {};
        for (var k in data) {
            if (data.hasOwnProperty(k) && k !== "signature" && k !== "signature_alg") {
                verifyData[k] = data[k];
            }
        }

        var canonical = _canonicalize(verifyData);
        var expectedSig = _hmacSha256(MCP_SECRET, canonical);

        if (expectedSig.length !== data.signature.length) {
            return false;
        }

        var diff = 0;
        for (var i = 0; i < expectedSig.length; i++) {
            diff |= (expectedSig.charCodeAt(i) ^ data.signature.charCodeAt(i));
        }
        return diff === 0;
    }

    function log(msg) {
        $.writeln("[MCP] " + msg);
    }

    function readJSON(path) {
        var f = new File(path);
        if (!f.exists) return null;
        f.encoding = "UTF-8";
        f.open("r");
        var txt = f.read();
        f.close();
        if (!txt) return null;
        try { return JSON.parse(txt); } catch(e) { return null; }
    }

    function writeJSON(path, obj) {
        var f = new File(path);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(JSON.stringify(obj, null, 2));
        f.close();
    }

    function updateStatus(status) {
        var data = readJSON(CMD_FILE);
        if (data) {
            data.status = status;
            writeJSON(CMD_FILE, data);
        }
    }

    // ========== 辅助函数 ==========
    function findCompByName(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === name) {
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

    function findFootageByPath(path) {
        var fileName = "";
        var pathParts = path.split("/");
        if (pathParts.length === 1) {
            pathParts = path.split("\\");
        }
        if (pathParts.length > 0) {
            fileName = pathParts[pathParts.length - 1];
        }
        
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof FootageItem) {
                if (item.file && item.file.fsName === path) {
                    return item;
                }
                if (item.name === fileName) {
                    return item;
                }
            }
        }
        return null;
    }

    function findPropertyIndex(parent, name) {
        try {
            for (var i = 1; i <= parent.numProperties; i++) {
                var prop = parent.property(i);
                if (prop.name === name) {
                    return i;
                }
            }
        } catch(e) {}
        return -1;
    }

    function setEffectProperty(effect, propName, value) {
        // 先尝试按名称访问
        try {
            effect.property(propName).setValue(value);
            return true;
        } catch(e1) {
            // 再尝试按索引访问
            try {
                var idx = findPropertyIndex(effect, propName);
                if (idx >= 1) {
                    effect.property(idx).setValue(value);
                    return true;
                }
            } catch(e2) {}
        }
        return false;
    }

    // ========== 命令处理函数 ==========
    function handleCreateComposition(params) {
        try {
            var name = params.name || "AI Composition";
            var width = params.width || 1920;
            var height = params.height || 1080;
            var duration = params.duration || 5;
            var frameRate = params.frameRate || 30;
            var bgColor = params.backgroundColor || [0, 0, 0];
            
            var comp = app.project.items.addComp(name, width, height, 1, duration, frameRate);
            comp.bgColor = [bgColor[0] / 255, bgColor[1] / 255, bgColor[2] / 255];
            
            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Composition created: " + name,
                compName: name,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleImportFootage(params) {
        try {
            var filePath = params.filePath;
            if (!filePath) {
                throw new Error("filePath is required");
            }
            
            var file = new File(filePath);
            if (!file.exists) {
                throw new Error("File not found: " + filePath);
            }
            
            var importOptions = new ImportOptions(file);
            var footage = app.project.importFile(importOptions);
            
            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Footage imported: " + file.name,
                footageName: footage.name,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handlePlaceFootageInComp(params) {
        try {
            var compName = params.compName;
            var layerName = params.layerName;
            var footagePath = params.footagePath;
            var startTime = params.startTime || 0;
            
            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found: " + compName);
            }
            
            var footageItem = findFootageByPath(footagePath);
            if (!footageItem) {
                throw new Error("Footage not found: " + footagePath);
            }
            
            var layer = comp.layers.add(footageItem);
            if (layerName) {
                layer.name = layerName;
            }
            layer.startTime = startTime;
            
            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Footage placed: " + layer.name,
                layerIndex: layer.index,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleApplyEffect(params) {
        try {
            var layerName = params.layerName;
            var effectMatchName = params.effectMatchName;
            var effectSettings = params.effectSettings || {};
            var compName = params.compName;
            
            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }
            
            var debugInfo = [];
            debugInfo.push("Layer type: " + typeof layer);
            debugInfo.push("Layer name: " + layer.name);
            debugInfo.push("Layer has Effects: " + (layer.Effects !== undefined));
            debugInfo.push("Layer has effects: " + (layer.effects !== undefined));
            debugInfo.push("Layer has property: " + (layer.property !== undefined));
            
            var effect;
            var effectsParade = null;
            
            if (typeof layer.property === 'function') {
                try {
                    effectsParade = layer.property("ADBE Effect Parade");
                } catch(e2) {
                    debugInfo.push("effectsParade error: " + e2.toString());
                }
            }
            
            if (effectsParade && typeof effectsParade.addProperty === 'function') {
                try {
                    effect = effectsParade.addProperty(effectMatchName);
                } catch(e2) {
                    debugInfo.push("addProperty error: " + e2.toString());
                    throw new Error("Cannot add effect: " + effectMatchName + ". Debug: " + debugInfo.join(" | "));
                }
            } else if (layer.effects && typeof layer.effects.add === 'function') {
                effect = layer.effects.add(effectMatchName);
            } else if (layer.Effects && typeof layer.Effects.add === 'function') {
                effect = layer.Effects.add(effectMatchName);
            } else {
                throw new Error("Layer does not support effects. Debug: " + debugInfo.join(" | "));
            }
            
            var appliedCount = 0;
            for (var propName in effectSettings) {
                if (effectSettings.hasOwnProperty(propName)) {
                    if (setEffectProperty(effect, propName, effectSettings[propName])) {
                        appliedCount++;
                    }
                }
            }
            
            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Effect applied: " + effectMatchName + " (" + appliedCount + " properties set)",
                effectName: effect.name,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleSetLayerKeyframe(params) {
        try {
            var layerName = params.layerName;
            var propertyName = params.propertyName;
            var timeInSeconds = params.timeInSeconds;
            var value = params.value;
            var easeType = params.easeType || "linear";
            var compName = params.compName;
            
            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }
            
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }
            
            var prop = layer.property(propertyName);
            if (!prop) {
                throw new Error("Property not found: " + propertyName);
            }
            
            // 设置时间指针并添加关键帧
            comp.time = timeInSeconds;
            prop.setValue(value);
            
            // 设置缓动
            if (prop.numKeys > 0 && easeType !== "linear") {
                var keyIndex = prop.nearestKeyIndex(comp.time);
                var keyTime = prop.keyTime(keyIndex);
                
                // 确保是当前时间的关键帧
                if (Math.abs(keyTime - comp.time) < 0.001) {
                    try {
                        if (easeType === "easeIn") {
                            var easeIn = new KeyframeEase(0.8, 0.8);
                            prop.setTemporalEaseAtKey(keyIndex, [easeIn], [new KeyframeEase(0.2, 0.2)]);
                        } else if (easeType === "easeOut") {
                            var easeOut = new KeyframeEase(0.2, 0.2);
                            prop.setTemporalEaseAtKey(keyIndex, [easeOut], [new KeyframeEase(0.8, 0.8)]);
                        } else if (easeType === "easeInOut") {
                            var ease = new KeyframeEase(0.8, 0.8);
                            prop.setTemporalEaseAtKey(keyIndex, [ease], [ease]);
                        }
                    } catch(easeErr) {
                        // 缓动设置失败不影响整体成功
                    }
                }
            }
            
            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Keyframe set: " + propertyName + " at " + timeInSeconds + "s",
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleRenderComposition(params) {
        try {
            var compName = params.compName;
            var outputPath = params.outputPath;
            var format = params.format || "mp4";
            var quality = params.quality || "high";
            var waitForCompletion = params.waitForCompletion !== false; // 默认 true

            var comp = findCompByName(compName);
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found: " + compName);
            }

            var renderQueue = app.project.renderQueue;
            var renderItem = renderQueue.items.add(comp);

            var outputModule = renderItem.outputModules[1];
            outputModule.file = new File(outputPath);

            try {
                if (format === "mp4" || format === "h264") {
                    outputModule.applyTemplate("H.264");
                } else if (format === "mov" || format === "quicktime") {
                    outputModule.applyTemplate("QuickTime");
                }
            } catch(templateErr) {
            }

            // 启动渲染
            renderQueue.render();

            if (waitForCompletion) {
                // 等待渲染完成
                var maxWaitMs = params.maxWaitMs || 300000; // 默认 5 分钟
                var waited = 0;
                var pollInterval = 500;
                while (renderQueue.isRendering && waited < maxWaitMs) {
                    $.sleep(pollInterval);
                    waited += pollInterval;
                }

                if (renderQueue.isRendering) {
                    // 超时
                    writeJSON(RES_FILE, {
                        success: false,
                        status: "timeout",
                        message: "Render timed out after " + (maxWaitMs / 1000) + "s",
                        outputPath: outputPath,
                        timestamp: new Date().toISOString()
                    });
                    return;
                }

                // 检查输出文件是否存在
                var outputFile = new File(outputPath);
                if (!outputFile.exists) {
                    writeJSON(RES_FILE, {
                        success: false,
                        status: "error",
                        message: "Render completed but output file not found: " + outputPath,
                        outputPath: outputPath,
                        timestamp: new Date().toISOString()
                    });
                    return;
                }

                // 检查文件大小
                var fileSize = outputFile.length;
                if (fileSize < 1000) {
                    writeJSON(RES_FILE, {
                        success: false,
                        status: "error",
                        message: "Render output file too small (" + fileSize + " bytes), likely corrupted",
                        outputPath: outputPath,
                        fileSize: fileSize,
                        timestamp: new Date().toISOString()
                    });
                    return;
                }

                writeJSON(RES_FILE, {
                    success: true,
                    status: "success",
                    message: "Render completed: " + outputPath,
                    outputPath: outputPath,
                    fileSize: fileSize,
                    renderItemIndex: renderItem.index,
                    renderTimeMs: waited,
                    timestamp: new Date().toISOString()
                });
            } else {
                // 不等待完成，仅返回队列状态
                writeJSON(RES_FILE, {
                    success: true,
                    status: "queued",
                    message: "Render queued (added to render queue): " + outputPath,
                    outputPath: outputPath,
                    renderItemIndex: renderItem.index,
                    timestamp: new Date().toISOString()
                });
            }
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    // ========== 参数查询命令 (Phase5 ResultVerifier 依赖) ==========

    function handleGetEffectProperties(params) {
        try {
            var compName = params.compName;
            var layerName = params.layerName;
            var effectName = params.effectName || params.effectMatchName;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found: " + compName);
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            var effectsParade = null;
            if (typeof layer.property === 'function') {
                effectsParade = layer.property("ADBE Effect Parade");
            }
            if (!effectsParade) {
                writeJSON(RES_FILE, {
                    success: true,
                    status: "success",
                    effectName: "",
                    properties: {},
                    message: "No effect parade found on layer",
                    timestamp: new Date().toISOString()
                });
                return;
            }

            var result = {};
            var matchedEffect = null;

            // 遍历所有效果，查找匹配的
            for (var i = 1; i <= effectsParade.numProperties; i++) {
                var eff = effectsParade.property(i);
                if (!eff || !eff.enabled) continue;

                var effMatchName = eff.matchName || "";
                var effDisplayName = eff.name || "";

                // 匹配条件：matchName 或 displayName 包含目标名称
                var isMatch = false;
                if (effectName) {
                    if (effMatchName === effectName ||
                        effDisplayName === effectName ||
                        effMatchName.indexOf(effectName) !== -1 ||
                        effectName.indexOf(effDisplayName) !== -1) {
                        isMatch = true;
                    }
                } else {
                    // 无指定效果名，返回第一个效果
                    isMatch = true;
                }

                if (isMatch) {
                    matchedEffect = eff;
                    result["effectName"] = effDisplayName;
                    result["matchName"] = effMatchName;
                    result["enabled"] = eff.enabled;

                    // 读取所有属性
                    var props = {};
                    for (var j = 1; j <= eff.numProperties; j++) {
                        var prop = eff.property(j);
                        if (!prop) continue;
                        var propName = prop.name || prop.matchName || ("prop_" + j);
                        var propValue = null;
                        try {
                            if (prop.propertyValueType === PropertyValueType.NO_VALUE) {
                                propValue = null;
                            } else if (prop.numKeys > 0) {
                                // 有关键帧，取当前时间值
                                propValue = prop.valueAtTime(comp.time, false);
                            } else {
                                propValue = prop.value;
                            }
                        } catch(ve) {
                            propValue = null;
                        }
                        props[propName] = {
                            value: propValue,
                            matchName: prop.matchName || "",
                            propertyValueType: prop.propertyValueType ? prop.propertyValueType.toString() : "",
                        };
                    }
                    result["properties"] = props;
                    break;
                }
            }

            if (!matchedEffect) {
                writeJSON(RES_FILE, {
                    success: true,
                    status: "success",
                    effectName: "",
                    properties: {},
                    message: "Effect not found: " + effectName,
                    timestamp: new Date().toISOString()
                });
            } else {
                writeJSON(RES_FILE, {
                    success: true,
                    status: "success",
                    effectName: result.effectName,
                    matchName: result.matchName,
                    properties: result.properties,
                    timestamp: new Date().toISOString()
                });
            }
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleGetLayerProperties(params) {
        try {
            var compName = params.compName;
            var layerName = params.layerName;
            var propertyNames = params.propertyNames || []; // 可选：指定属性名列表

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found: " + compName);
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            var result = {
                layerName: layer.name,
                index: layer.index,
                enabled: layer.enabled,
                properties: {}
            };

            // 默认查询的 Transform 属性
            var defaultProps = [
                "ADBE Transform Group",
            ];
            var transformProps = [
                "ADBE Position",
                "ADBE Scale",
                "ADBE Rotation",
                "ADBE Opacity",
                "ADBE Anchor Point",
                "ADBE Orientation",
            ];

            // 读取 Transform 属性
            var transformGroup = null;
            try {
                transformGroup = layer.property("ADBE Transform Group");
            } catch(e) {}

            if (transformGroup) {
                for (var t = 0; t < transformProps.length; t++) {
                    try {
                        var prop = transformGroup.property(transformProps[t]);
                        if (prop) {
                            var val = null;
                            if (prop.numKeys > 0) {
                                val = prop.valueAtTime(comp.time, false);
                            } else {
                                val = prop.value;
                            }
                            result.properties[transformProps[t]] = {
                                value: val,
                                name: prop.name || transformProps[t],
                            };
                        }
                    } catch(pe) {}
                }
            }

            // 读取额外指定的属性
            for (var i = 0; i < propertyNames.length; i++) {
                try {
                    var pName = propertyNames[i];
                    var prop2 = layer.property(pName);
                    if (prop2) {
                        var val2 = null;
                        if (prop2.numKeys > 0) {
                            val2 = prop2.valueAtTime(comp.time, false);
                        } else {
                            val2 = prop2.value;
                        }
                        result.properties[pName] = {
                            value: val2,
                            name: prop2.name || pName,
                        };
                    }
                } catch(pe2) {}
            }

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                layerName: result.layerName,
                index: result.index,
                properties: result.properties,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    // ========== 脚本安全校验 ==========
    var FORBIDDEN_PATTERNS = [
        "system.callsystem",   // 执行系统命令
        "$.evalfile",          // 加载并执行外部 JSX 文件
        "new function(",        // 动态函数创建（等效 eval）
        ".execute("            // File.execute() 启动外部程序
    ];
    var MAX_SCRIPT_SIZE = 1048576; // 1MB

    function _validateScriptSafety(script) {
        if (!script) return "Empty script";
        if (script.length > MAX_SCRIPT_SIZE) return "Script exceeds size limit (1MB)";
        var lower = script.toLowerCase();
        for (var i = 0; i < FORBIDDEN_PATTERNS.length; i++) {
            if (lower.indexOf(FORBIDDEN_PATTERNS[i]) !== -1) {
                return "Script contains forbidden API: " + FORBIDDEN_PATTERNS[i];
            }
        }
        return null;
    }

    function executeAtom(args) {
        try {
            var script = "";
            var scriptPath = args.scriptPath || args.filePath || "";
            if (scriptPath) {
                var f = new File(scriptPath);
                if (!f.exists) throw new Error("Script file not found: " + scriptPath);
                f.encoding = "UTF-8";
                f.open("r");
                script = f.read();
                f.close();
            } else {
                script = (args.scriptContent || args.script || "");
            }
            if (!script) throw new Error("No script content or path");
            var safetyError = _validateScriptSafety(script);
            if (safetyError) throw new Error("Safety check failed: " + safetyError);
            var result = eval(script);
            writeJSON(RES_FILE, { status: "success", result: result || {}, timestamp: new Date().toISOString() });
        } catch(e) {
            writeJSON(RES_FILE, { status: "error", message: e.toString(), line: e.line, timestamp: new Date().toISOString() });
        }
    }

            function handleE2EMusicVideo(params) {
        try {
            var compName = params.compName || "E2E_音乐视频";
            var frameDir = params.frameDir || "D:/AE-Work/视频素材库/frames";
            var bgmPath = params.bgmPath || "";
            var beatTimes = params.beatTimes || [];
            var energyPeaks = params.energyPeaks || [];
            var peakValues = params.peakValues || [];
            var bpm = params.bpm || 120;
            var compWidth = params.width || 576;
            var compHeight = params.height || 768;
            var compDuration = params.duration || 12;
            var compFPS = params.fps || 30;

            var results = [];

            for (var i = 1; i <= app.project.numItems; i++) {
                if (app.project.item(i).name == compName && app.project.item(i) instanceof CompItem) {
                    app.project.item(i).remove();
                    break;
                }
            }

            var comp = app.project.items.addComp(compName, compWidth, compHeight, 1, compDuration, compFPS);
            results.push({ phase: "Phase1", status: "success", message: "合成创建成功: " + compName });

            var frameFiles = [];
            for (var f = 1; f <= 18; f++) {
                var num = f < 10 ? "0" + f : "" + f;
                var fp = new File(frameDir + "/frame_" + num + ".png");
                if (fp.exists) {
                    var importOpts = new ImportOptions(fp);
                    importOpts.sequence = false;
                    var footage = app.project.importFile(importOpts);
                    footage.name = "Frame_" + num;
                    frameFiles.push(footage);
                }
            }

            if (frameFiles.length === 0) {
                throw new Error("帧目录中没有图片文件");
            }
            results.push({ phase: "Phase1", status: "success", message: "导入 " + frameFiles.length + " 帧" });

            app.beginUndoGroup("Create E2E Music Video");

            var seqComp = app.project.items.addComp("FrameSeq", compWidth, compHeight, 1, 0.6, compFPS);
            for (var i = 0; i < frameFiles.length; i++) {
                var layer = seqComp.layers.add(frameFiles[i]);
                layer.startTime = i * (1/compFPS);
                layer.outPoint = (i + 1) * (1/compFPS);
            }
            seqComp.duration = frameFiles.length * (1/compFPS);

            var seqLayer = comp.layers.add(seqComp);
            seqLayer.name = "FrameSeq";
            seqLayer.stretch = -50;
            seqLayer.motionBlur = true;
            results.push({ phase: "Phase1", status: "success", message: "帧序列预合成完成" });

            var saitama = seqLayer.duplicate();
            saitama.name = "Saitama_Main";

            try {
                var key = saitama.property("ADBE Effect Parade").addProperty("ADBE Color Key");
                if (key) {
                    try { key.property("Color Tolerance").setValue(20); } catch(e) {}
                    try { key.property("Edge Feather").setValue(1); } catch(e) {}
                }
            } catch(e) {}

            try {
                var glow = saitama.property("ADBE Effect Parade").addProperty("ADBE Glo2");
                if (glow) {
                    try { glow.property("Glow Threshold").setValue(80); } catch(e) {}
                    try { glow.property("Glow Radius").setValue(1.5); } catch(e) {}
                    try { glow.property("Glow Intensity").setValue(1.2); } catch(e) {}
                }
            } catch(e) {}

            try {
                var mc = saitama.property("ADBE Effect Parade").addProperty("ADBE Simple Choker");
                if (mc) {
                    try { mc.property("Choke Matte").setValue(5); } catch(e) {}
                }
            } catch(e) {}

            try {
                var tint = saitama.property("ADBE Effect Parade").addProperty("ADBE Tint");
                if (tint) {
                    try { tint.property(1).setValue([0.1, 0.15, 0.3]); } catch(e) {}
                    try { tint.property(2).setValue([0.8, 0.85, 1.0]); } catch(e) {}
                    try { tint.property(3).setValue(0.15); } catch(e) {}
                }
            } catch(e) {}
            results.push({ phase: "Phase2", status: "success", message: "Saitama_Main层效果添加完成" });

            var cape = saitama.duplicate();
            cape.name = "Cape_Layer";
            cape.threeDLayer = true;
            cape.position.setValue([compWidth * 0.525, compHeight * 0.5, -50]);
            cape.scale.setValue([105, 105, 105]);

            while (cape.property("ADBE Effect Parade").numProperties > 0) {
                try { cape.property("ADBE Effect Parade").property(1).remove(); } catch(e) {}
            }

            try {
                var key2 = cape.property("ADBE Effect Parade").addProperty("ADBE Color Key");
                if (key2) {
                    try { key2.property("Color Tolerance").setValue(15); } catch(e) {}
                }
            } catch(e) {}

            try {
                var glow2 = cape.property("ADBE Effect Parade").addProperty("ADBE Glo2");
                if (glow2) {
                    try { glow2.property("Glow Threshold").setValue(70); } catch(e) {}
                    try { glow2.property("Glow Radius").setValue(2.0); } catch(e) {}
                    try { glow2.property("Glow Intensity").setValue(1.5); } catch(e) {}
                }
            } catch(e) {}

            try {
                var tint2 = cape.property("ADBE Effect Parade").addProperty("ADBE Tint");
                if (tint2) {
                    try { tint2.property(1).setValue([0.9, 0.9, 0.95]); } catch(e) {}
                    try { tint2.property(2).setValue([1.0, 1.0, 1.0]); } catch(e) {}
                    try { tint2.property(3).setValue(0.3); } catch(e) {}
                }
            } catch(e) {}
            results.push({ phase: "Phase3", status: "success", message: "Cape_Layer披风层创建完成" });

            var p_bg = comp.layers.addSolid([0.05, 0.05, 0.1], "P_BG", compWidth, compHeight, 1, compDuration);
            p_bg.threeDLayer = true;
            p_bg.position.setValue([compWidth/2, compHeight/2, 800]);
            try {
                var pw_bg = p_bg.property("ADBE Effect Parade").addProperty("CC Particle World");
                if (pw_bg) {
                    try { pw_bg.property("Birth Rate").setValue(0.5); } catch(e) {}
                    try { pw_bg.property("Longevity").setValue(2.0); } catch(e) {}
                    try { pw_bg.property("Size").setValue(0.02); } catch(e) {}
                }
            } catch(e) {}

            var p_mid = comp.layers.addSolid([0.1, 0.1, 0.15], "P_MID", compWidth, compHeight, 1, compDuration);
            p_mid.threeDLayer = true;
            p_mid.position.setValue([compWidth/2, compHeight/2, 200]);
            try {
                var pw_mid = p_mid.property("ADBE Effect Parade").addProperty("CC Particle World");
                if (pw_mid) {
                    try { pw_mid.property("Birth Rate").setValue(1.0); } catch(e) {}
                    try { pw_mid.property("Longevity").setValue(1.5); } catch(e) {}
                    try { pw_mid.property("Size").setValue(0.05); } catch(e) {}
                }
            } catch(e) {}

            var p_fg = comp.layers.addSolid([0.15, 0.15, 0.2], "P_FG", compWidth, compHeight, 1, compDuration);
            p_fg.threeDLayer = true;
            p_fg.position.setValue([compWidth/2, compHeight/2, -100]);
            try {
                var pw_fg = p_fg.property("ADBE Effect Parade").addProperty("CC Particle World");
                if (pw_fg) {
                    try { pw_fg.property("Birth Rate").setValue(2.0); } catch(e) {}
                    try { pw_fg.property("Longevity").setValue(1.0); } catch(e) {}
                    try { pw_fg.property("Size").setValue(0.08); } catch(e) {}

                    for (var ep = 0; ep < energyPeaks.length; ep++) {
                        var pt = energyPeaks[ep];
                        if (pt > compDuration) break;
                        var pv = peakValues[ep] || 0.1;
                        var br_val = 2.0 + pv * 10;
                        try { pw_fg.property("Birth Rate").setValueAtTime(pt, br_val); } catch(e) {}
                    }
                }
            } catch(e) {}
            results.push({ phase: "Phase4", status: "success", message: "三层粒子系统创建完成" });

            var sky = comp.layers.addSolid([0.02, 0.02, 0.08], "Sky_BG", compWidth, compHeight, 1, compDuration);
            try {
                var ramp = sky.property("ADBE Effect Parade").addProperty("ADBE Ramp");
                if (ramp) {
                    try { ramp.property("Start of Ramp").setValue([compWidth/2, 100]); } catch(e) {}
                    try { ramp.property("Start Color").setValue([0.05, 0.05, 0.15]); } catch(e) {}
                    try { ramp.property("End of Ramp").setValue([compWidth/2, compHeight - 68]); } catch(e) {}
                    try { ramp.property("End Color").setValue([0.01, 0.01, 0.03]); } catch(e) {}
                }
            } catch(e) {}

            var fog = comp.layers.addSolid([0.5, 0.5, 0.5], "Fog_Overlay", compWidth, compHeight, 1, compDuration);
            fog.blendingMode = BlendingMode.SCREEN;
            fog.opacity.setValue(25);
            try {
                var fn = fog.property("ADBE Effect Parade").addProperty("ADBE Fractal Noise");
                if (fn) {
                    try { fn.property("Contrast").setValue(50); } catch(e) {}
                    try { fn.property("Scale").setValue(200); } catch(e) {}
                }
            } catch(e) {}

            var vig = comp.layers.addSolid([0, 0, 0], "Vignette", compWidth, compHeight, 1, compDuration);
            vig.blendingMode = BlendingMode.MULTIPLY;
            vig.opacity.setValue(40);
            results.push({ phase: "Phase5", status: "success", message: "背景和大气效果创建完成" });

            var adj = comp.layers.addSolid([0.5, 0.5, 0.5], "Color_Adjust", compWidth, compHeight, 1, compDuration);
            adj.adjustmentLayer = true;
            adj.name = "Color_Adjust";

            try {
                var curves = adj.property("ADBE Effect Parade").addProperty("ADBE CurvesCustom");
                if (curves) {
                    try { curves.property(1).setValue([[0,0],[0.2,0.1],[0.5,0.5],[0.8,0.9],[1,1]]); } catch(e) {}
                }
            } catch(e) {}

            try {
                var hueSat = adj.property("ADBE Effect Parade").addProperty("ADBE HUE SATURATION");
                if (hueSat) {
                    try { hueSat.property("Master Saturation").setValue(15); } catch(e) {}
                    try { hueSat.property("Master Lightness").setValue(10); } catch(e) {}
                }
            } catch(e) {}

            var cam = comp.layers.addCamera("Main_Camera", [compWidth/2, compHeight/2]);
            try {
                cam.property("ADBE Camera Settings-0001").setValue(50);
            } catch(e) {}

            var beatKfCount = 0;
            try {
                var camPos = cam.property("ADBE Transform Group").property("ADBE Position");
                camPos.setValueAtTime(0, [compWidth/2, compHeight/2, -600]);
                camPos.setValueAtTime(4, [compWidth/2, compHeight/2, -500]);
                camPos.setValueAtTime(8, [compWidth/2 + 12, compHeight/2 + 6, -550]);
                camPos.setValueAtTime(compDuration, [compWidth/2, compHeight/2, -600]);

                for (var k = 1; k <= camPos.numKeys; k++) {
                    camPos.setTemporalEaseAtKey(k, [new KeyframeEase(0, 33)], [new KeyframeEase(0, 33)]);
                }
                beatKfCount = camPos.numKeys;
            } catch(e) {}

            var ctrl = comp.layers.addNull();
            ctrl.name = "Global_Controller";
            try {
                var sc1 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
                if (sc1) { sc1.name = "Speed"; try { sc1.property(1).setValue(100); } catch(e) {} }
                var sc2 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
                if (sc2) { sc2.name = "Glow_Intensity"; try { sc2.property(1).setValue(100); } catch(e) {} }
                var sc3 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
                if (sc3) { sc3.name = "Particle_Amount"; try { sc3.property(1).setValue(100); } catch(e) {} }
            } catch(e) {}
            results.push({ phase: "Phase6", status: "success", message: "调整层、摄像机、控制器创建完成" });

            var layerOrder = ["Sky_BG", "P_BG", "P_MID", "FrameSeq", "Saitama_Main", "Cape_Layer", "P_FG", "Fog_Overlay", "Vignette", "Color_Adjust"];
            for (var lo = 0; lo < layerOrder.length; lo++) {
                for (var lj = 1; lj <= comp.numLayers; lj++) {
                    if (comp.layer(lj).name == layerOrder[lo]) {
                        comp.layer(lj).moveToEnd();
                        break;
                    }
                }
            }
            for (var lk = 1; lk <= comp.numLayers; lk++) {
                if (comp.layer(lk).name == "Main_Camera") comp.layer(lk).moveToBeginning();
                if (comp.layer(lk).name == "Global_Controller") comp.layer(lk).moveToBeginning();
            }
            results.push({ phase: "Phase7", status: "success", message: "层顺序整理完成" });

            if (bgmPath) {
                var bgmFile = new File(bgmPath);
                if (bgmFile.exists) {
                    var bgmImport = app.project.importFile(new ImportOptions(bgmFile));
                    var bgmLayer = comp.layers.add(bgmImport);
                    bgmLayer.name = "BGM_Track";
                    bgmLayer.moveToEnd();
                }
            }

            app.endUndoGroup();

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "E2E音乐视频合成创建成功",
                compName: compName,
                totalLayers: comp.numLayers,
                bpm: bpm,
                beatKeyframes: beatKfCount,
                energyPeaks: energyPeaks.length,
                frameCount: frameFiles.length,
                phases: results,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            try { app.endUndoGroup(); } catch(ee) {}
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                line: e.line,
                timestamp: new Date().toISOString()
            });
        }
    }

    // ========== 表达式/遮罩/混合模式/父级/轨道遮罩命令 ==========

    function handleSetExpression(params) {
        try {
            var layerName = params.layerName;
            var propertyPath = params.propertyPath;
            var expression = params.expression || "";
            var compName = params.compName;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            // 通过 propertyPath 定位属性并设置表达式
            var prop = layer.property(propertyPath);
            if (!prop) {
                throw new Error("Property not found: " + propertyPath);
            }
            prop.expression = expression;

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Expression set: " + propertyPath + " on " + layerName,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleAddMask(params) {
        try {
            var layerName = params.layerName;
            var maskPath = params.maskPath || [];
            var maskName = params.maskName || "Mask 1";
            var compName = params.compName;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            // 获取遮罩组并添加新遮罩
            var maskParade = layer.property("ADBE Mask Parade");
            if (!maskParade) {
                throw new Error("Mask parade not found on layer");
            }
            var mask = maskParade.addProperty("ADBE Mask");
            if (maskName) {
                mask.name = maskName;
            }

            // 如果提供了遮罩路径（顶点数组），设置遮罩形状
            if (maskPath && maskPath.length > 0) {
                try {
                    var maskShape = mask.property("ADBE Mask Shape");
                    var shape = new Shape();
                    shape.vertices = maskPath;
                    shape.closed = true;
                    maskShape.setValue(shape);
                } catch(shapeErr) {
                    // 遮罩形状设置失败不影响整体成功
                }
            }

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Mask added: " + maskName + " on " + layerName,
                maskName: mask.name,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleSetBlendMode(params) {
        try {
            var layerName = params.layerName;
            var blendMode = params.blendMode || "normal";
            var compName = params.compName;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            // 混合模式字符串到 BlendingMode 枚举的映射
            var blendModeMap = {
                "normal": BlendingMode.NORMAL,
                "screen": BlendingMode.SCREEN,
                "multiply": BlendingMode.MULTIPLY,
                "overlay": BlendingMode.OVERLAY,
                "add": BlendingMode.ADD,
                "difference": BlendingMode.DIFFERENCE,
                "exclusion": BlendingMode.EXCLUSION,
                "hardlight": BlendingMode.HARD_LIGHT,
                "softlight": BlendingMode.SOFT_LIGHT,
                "colordodge": BlendingMode.COLOR_DODGE,
                "colorburn": BlendingMode.COLOR_BURN,
                "linearburn": BlendingMode.LINEAR_BURN,
                "lineardodge": BlendingMode.LINEAR_DODGE,
                "vividlight": BlendingMode.VIVID_LIGHT,
                "linearlight": BlendingMode.LINEAR_LIGHT,
                "pinlight": BlendingMode.PIN_LIGHT,
                "hardmix": BlendingMode.HARD_MIX,
                "classiccolordodge": BlendingMode.CLASSIC_COLOR_DODGE,
                "classiccolorburn": BlendingMode.CLASSIC_COLOR_BURN
            };

            var mode = blendModeMap[blendMode.toLowerCase()];
            if (mode === undefined) {
                // 未知模式默认使用 NORMAL
                mode = BlendingMode.NORMAL;
            }
            layer.blendingMode = mode;

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Blend mode set: " + blendMode + " on " + layerName,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleSetParent(params) {
        try {
            var layerName = params.layerName;
            var parentLayerName = params.parentLayerName;
            var compName = params.compName;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            var parentLayer = findLayerByName(comp, parentLayerName);
            if (!parentLayer) {
                throw new Error("Parent layer not found: " + parentLayerName);
            }

            // 设置父级图层
            layer.parent = parentLayer;

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Parent set: " + layerName + " -> " + parentLayerName,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleSetTrackMatte(params) {
        try {
            var layerName = params.layerName;
            var matteLayerName = params.matteLayerName;
            var matteType = params.matteType || "alpha";
            var compName = params.compName;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                throw new Error("Layer not found: " + layerName);
            }

            var matteLayer = findLayerByName(comp, matteLayerName);
            if (!matteLayer) {
                throw new Error("Matte layer not found: " + matteLayerName);
            }

            // 轨道遮罩类型字符串到 TrackMatteType 枚举的映射
            var matteTypeMap = {
                "alpha": TrackMatteType.ALPHA,
                "alphainverted": TrackMatteType.ALPHA_INVERTED,
                "luma": TrackMatteType.LUMA,
                "lumainverted": TrackMatteType.LUMA_INVERTED
            };

            var matteTypeEnum = matteTypeMap[matteType.toLowerCase()];
            if (matteTypeEnum === undefined) {
                // 未知类型默认使用 ALPHA
                matteTypeEnum = TrackMatteType.ALPHA;
            }

            // 轨道遮罩要求遮罩层位于被遮罩层的上方
            matteLayer.moveBefore(layer);
            layer.trackMatteType = matteTypeEnum;

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Track matte set: " + matteLayerName + " -> " + layerName + " (" + matteType + ")",
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }


    function handleAddPrecomp(params) {
        try {
            var compName = params.compName;
            var name = params.name || "Precomp";
            var layerIndices = params.layerIndices || [];
            var moveAllAttributes = params.moveAllAttributes !== false;

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            if (!layerIndices || layerIndices.length === 0) {
                throw new Error("layerIndices is required");
            }

            // 验证所有图层索引
            for (var li = 0; li < layerIndices.length; li++) {
                var idx = layerIndices[li];
                if (idx < 1 || idx > comp.numLayers) {
                    throw new Error("Invalid layer index: " + idx);
                }
            }

            app.beginUndoGroup("Add Precomp");

            // 清除所有图层选中状态
            for (var c = 1; c <= comp.numLayers; c++) {
                comp.layer(c).selected = false;
            }

            // 选中要预合成的图层
            for (var s = 0; s < layerIndices.length; s++) {
                comp.layer(layerIndices[s]).selected = true;
            }

            // 执行预合成
            var precomp = comp.layers.precompose(layerIndices, name, moveAllAttributes);

            // 清除所有图层选中状态
            for (var c2 = 1; c2 <= comp.numLayers; c2++) {
                comp.layer(c2).selected = false;
            }

            app.endUndoGroup();

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Precomp created: " + precomp.name,
                precompName: precomp.name,
                precompDuration: precomp.duration,
                sourceLayerCount: layerIndices.length,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            try { app.endUndoGroup(); } catch(ue) {}
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function handleApplyNewtonDynamics(params) {
        try {
            var compName = params.compName;
            var layerIndices = params.layerIndices || [];
            var mode = params.mode || "expression";
            var gravity = params.gravity !== undefined ? params.gravity : 2000;
            var bounce = params.bounce !== undefined ? params.bounce : 0.6;
            var friction = params.friction !== undefined ? params.friction : 0.98;
            var groundY = params.groundY;
            var startVelocity = params.startVelocity || [0, 0];
            var gravityDirection = params.gravityDirection || "down";

            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                throw new Error("Composition not found");
            }

            if (!layerIndices || layerIndices.length === 0) {
                throw new Error("layerIndices is required");
            }

            if (groundY === undefined || groundY === null) {
                groundY = comp.height - 50;
            }

            app.beginUndoGroup("Apply Newton Dynamics");

            var resultLayers = [];

            for (var li = 0; li < layerIndices.length; li++) {
                var idx = layerIndices[li];
                if (idx < 1 || idx > comp.numLayers) continue;

                var layer = comp.layer(idx);

                if (mode === "keyframe" || mode === "bake") {
                    bakeDynamicsKeyframes(layer, comp, gravity, bounce, friction, groundY, startVelocity, gravityDirection);
                } else {
                    applyDynamicsExpression(layer, comp, gravity, bounce, friction, groundY, startVelocity, gravityDirection);
                }

                resultLayers.push({
                    index: idx,
                    name: layer.name
                });
            }

            app.endUndoGroup();

            writeJSON(RES_FILE, {
                success: true,
                status: "success",
                message: "Newton dynamics applied to " + resultLayers.length + " layers",
                mode: mode,
                gravity: gravity,
                bounce: bounce,
                friction: friction,
                groundY: groundY,
                layers: resultLayers,
                timestamp: new Date().toISOString()
            });
        } catch(e) {
            try { app.endUndoGroup(); } catch(ue) {}
            writeJSON(RES_FILE, {
                success: false,
                status: "error",
                message: e.toString(),
                timestamp: new Date().toISOString()
            });
        }
    }

    function applyDynamicsExpression(layer, comp, gravity, bounce, friction, groundY, startVel, direction) {
        var posProp = layer.property("Transform").property("Position");

        var expr = "// Newton Dynamics - 牛顿物理模拟\n";
        expr += "vy = " + startVel[1] + ";\n";
        expr += "vx = " + startVel[0] + ";\n";
        expr += "g = " + gravity + ";\n";
        expr += "bounce = " + bounce + ";\n";
        expr += "friction = " + friction + ";\n";
        expr += "groundY = " + groundY + ";\n";
        expr += "\n";
        expr += "L = thisLayer;\n";
        expr += "src = L.sourceRectAtTime(time - inPoint, false);\n";
        expr += "layerHeight = src.height * L.scale[1] / 100;\n";
        expr += "layerWidth = src.width * L.scale[0] / 100;\n";
        expr += "anchorOffsetY = layerHeight * (L.anchorPoint[1] / src.height);\n";
        expr += "anchorOffsetX = layerWidth * (L.anchorPoint[0] / src.width);\n";
        expr += "\n";
        expr += "startPos = valueAtTime(inPoint);\n";
        expr += "t = time - inPoint;\n";
        expr += "\n";
        expr += "if (t <= 0) {\n";
        expr += "    value;\n";
        expr += "} else {\n";
        expr += "    pos = startPos;\n";
        expr += "    velY = vy;\n";
        expr += "    velX = vx;\n";
        expr += "    fps = 1.0 / thisComp.frameDuration;\n";
        expr += "    dt = 1.0 / fps;\n";
        expr += "    steps = Math.floor(t * fps);\n";
        expr += "    \n";
        expr += "    for (i = 0; i < steps; i++) {\n";

        if (direction === "down") {
            expr += "        velY += g * dt;\n";
        } else if (direction === "up") {
            expr += "        velY -= g * dt;\n";
        } else if (direction === "left") {
            expr += "        velX -= g * dt;\n";
        } else {
            expr += "        velX += g * dt;\n";
        }

        expr += "        pos[0] += velX * dt;\n";
        expr += "        pos[1] += velY * dt;\n";
        expr += "        \n";

        if (direction === "down") {
            expr += "        bottomY = groundY - anchorOffsetY;\n";
            expr += "        if (pos[1] >= bottomY) {\n";
            expr += "            pos[1] = bottomY;\n";
            expr += "            velY = -velY * bounce;\n";
            expr += "            velX *= friction;\n";
            expr += "            if (Math.abs(velY) < 5) velY = 0;\n";
            expr += "        }\n";
        } else if (direction === "up") {
            expr += "        topY = anchorOffsetY;\n";
            expr += "        if (pos[1] <= topY) {\n";
            expr += "            pos[1] = topY;\n";
            expr += "            velY = -velY * bounce;\n";
            expr += "            velX *= friction;\n";
            expr += "            if (Math.abs(velY) < 5) velY = 0;\n";
            expr += "        }\n";
        }

        expr += "        leftX = anchorOffsetX;\n";
        expr += "        rightX = thisComp.width - anchorOffsetX;\n";
        expr += "        if (pos[0] <= leftX) {\n";
        expr += "            pos[0] = leftX;\n";
        expr += "            velX = -velX * bounce;\n";
        expr += "        }\n";
        expr += "        if (pos[0] >= rightX) {\n";
        expr += "            pos[0] = rightX;\n";
        expr += "            velX = -velX * bounce;\n";
        expr += "        }\n";
        expr += "    }\n";
        expr += "    pos;\n";
        expr += "}\n";

        posProp.expression = expr;
    }

    function bakeDynamicsKeyframes(layer, comp, gravity, bounce, friction, groundY, startVel, direction) {
        var posProp = layer.property("Transform").property("Position");
        var fps = comp.frameRate;
        var startPos = posProp.valueAtTime(layer.inPoint, false);

        var pos = [startPos[0], startPos[1]];
        var velX = startVel[0];
        var velY = startVel[1];
        var dt = 1.0 / fps;

        var layerHeight = 100;
        var layerWidth = 100;
        try {
            var src = layer.sourceRectAtTime(layer.inPoint, false);
            layerHeight = src.height * layer.property("Transform").property("Scale").value[1] / 100;
            layerWidth = src.width * layer.property("Transform").property("Scale").value[0] / 100;
        } catch(e) {}

        var bottomY = groundY - layerHeight / 2;
        var topY = layerHeight / 2;
        var leftX = layerWidth / 2;
        var rightX = comp.width - layerWidth / 2;

        var totalTime = layer.outPoint - layer.inPoint;
        var totalFrames = Math.floor(totalTime * fps);

        var restingFrames = 0;

        for (var f = 0; f < totalFrames; f++) {
            var t = layer.inPoint + f / fps;

            if (direction === "down") velY += gravity * dt;
            else if (direction === "up") velY -= gravity * dt;
            else if (direction === "left") velX -= gravity * dt;
            else velX += gravity * dt;

            pos[0] += velX * dt;
            pos[1] += velY * dt;

            var collided = false;

            if (direction === "down" && pos[1] >= bottomY) {
                pos[1] = bottomY;
                velY = -velY * bounce;
                velX *= friction;
                collided = true;
            } else if (direction === "up" && pos[1] <= topY) {
                pos[1] = topY;
                velY = -velY * bounce;
                velX *= friction;
                collided = true;
            }

            if (pos[0] <= leftX) {
                pos[0] = leftX;
                velX = -velX * bounce;
                collided = true;
            }
            if (pos[0] >= rightX) {
                pos[0] = rightX;
                velX = -velX * bounce;
                collided = true;
            }

            if (Math.abs(velY) < 5 && Math.abs(velX) < 5 && collided) {
                restingFrames++;
            } else {
                restingFrames = 0;
            }

            if (restingFrames > fps * 0.5) break;

            posProp.setValueAtTime(t, [pos[0], pos[1]]);
        }
    }

    function checkOnce() {
        var data = readJSON(CMD_FILE);
        if (!data) return;
        if (data.status !== "pending") return;
        var ts = data.timestamp ? new Date(data.timestamp).getTime() : 0;
        if (ts < lastCmdTime) return;

        if (!verifySignature(data)) {
            log("Signature verification failed - command rejected");
            writeJSON(RES_FILE, {
                status: "error",
                error: "signature_verification_failed",
                message: "Command signature verification failed",
                timestamp: new Date().toISOString()
            });
            updateStatus("completed");
            return;
        }

        lastCmdTime = ts;

        log("Executing: " + (data.description || data.command));
        updateStatus("running");

        // 命令分发
        var cmd = data.command || data.op;
        var params = data.params || data.args || {};

        if (cmd === "executeAtomScript" || cmd === "execute_script") {
            executeAtom(data.args || data);
        } else if (cmd === "createComposition") {
            handleCreateComposition(params);
        } else if (cmd === "importFootage") {
            handleImportFootage(params);
        } else if (cmd === "placeFootageInComp") {
            handlePlaceFootageInComp(params);
        } else if (cmd === "applyEffect") {
            handleApplyEffect(params);
        } else if (cmd === "setLayerKeyframe") {
            handleSetLayerKeyframe(params);
        } else if (cmd === "renderComposition") {
            handleRenderComposition(params);
        } else if (cmd === "getEffectProperties" || cmd === "get_effect_properties") {
            handleGetEffectProperties(params);
        } else if (cmd === "getLayerProperties" || cmd === "get_layer_properties") {
            handleGetLayerProperties(params);
        } else if (cmd === "e2eMusicVideo" || cmd === "e2e_music_video") {
            handleE2EMusicVideo(params);
        } else if (cmd === "setExpression") {
            handleSetExpression(params);
        } else if (cmd === "addMask") {
            handleAddMask(params);
        } else if (cmd === "setBlendMode") {
            handleSetBlendMode(params);
        } else if (cmd === "setParent") {
            handleSetParent(params);
        } else if (cmd === "addPrecomp" || cmd === "precompose" || cmd === "precomp") {
            handleAddPrecomp(params);
        } else if (cmd === "applyNewtonDynamics" || cmd === "newton_dynamics" || cmd === "newtonDynamics") {
            handleApplyNewtonDynamics(params);
        } else if (cmd === "setTrackMatte") {
            handleSetTrackMatte(params);
        } else {
            writeJSON(RES_FILE, { status: "error", message: "Unknown command: " + cmd, timestamp: new Date().toISOString() });
        }

        updateStatus("completed");
        log("Done.");
    }

    // Main loop using scheduleTask
    function startListener() {
        if (!app.scheduleTask) {
            alert("AE版本不支持scheduleTask");
            return;
        }
        // scheduleTask expects a string that evals to a function call
        $.global.__mcp_listener_check__ = function() {
            if (isRunning) {
                try { checkOnce(); } catch(e) { log("Error: " + e.toString()); }
            }
        };
        app.scheduleTask("__mcp_listener_check__()", 1000, true);
        log("MCP Listener started. Command file: " + CMD_FILE);
    }

    startListener();

    // Also expose manual trigger
    $.global.mcpCheckNow = function() { checkOnce(); };
}

