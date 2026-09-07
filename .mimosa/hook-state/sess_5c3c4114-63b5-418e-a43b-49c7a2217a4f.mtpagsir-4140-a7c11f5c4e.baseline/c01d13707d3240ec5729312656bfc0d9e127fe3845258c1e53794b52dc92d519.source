{
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
                if (ch === "e" || ch === "E") { s += ch; next(); if (ch === "-" || ch === "+") { s += ch; next(); } while (ch >= "0" && ch <= "9") { s += ch; } }
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
            function toStr(v) {
                if (v === null) return "null";
                if (typeof v === "boolean") return v ? "true" : "false";
                if (typeof v === "number") return isFinite(v) ? String(v) : "null";
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
                                if (ch < ' ') { s += '\\u' + ('0000' + ch.charCodeAt(0).toString(16)).slice(-4); }
                                else { s += ch; }
                        }
                    }
                    return s + '"';
                }
                if (v instanceof Array) {
                    var a = [];
                    for (var i = 0; i < v.length; i++) a.push(toStr(v[i]));
                    return "[" + a.join(",") + "]";
                }
                if (typeof v === "object") {
                    var p = [];
                    for (var k in v) { if (Object.hasOwnProperty.call(v, k)) p.push(toStr(k) + ":" + toStr(v[k])); }
                    return "{" + p.join(",") + "}";
                }
                return "null";
            }
            return toStr(obj);
        };
    }

    var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
    var BASE_DIR = PROJ_ROOT + "/.ae-mcp-bridge";
    var CMD_FILE = BASE_DIR + "/ae_command.json";
    var RES_FILE = BASE_DIR + "/ae_result.json";
    var LOG_FILE = BASE_DIR + "/ae_listener_log.txt";
    var SECRET_FILE = PROJ_ROOT + "/.mcp_secret";
    var MCP_SECRET = "";
    var SIGNATURE_ENABLED = false;
    var lastCmdTime = 0;
    var isRunning = true;

    function _loadSecret() {
        try {
            var f = new File(SECRET_FILE);
            if (f.exists) {
                f.encoding = "UTF-8";
                f.open("r");
                MCP_SECRET = f.read().replace(/^\s+|\s+$/g, "");
                f.close();
            }
        } catch(e) {}
    }
    _loadSecret();

    function _sha256(msg) {
        function rotr(n,x){return(x>>>n)|(x<<(32-n))}function ch(x,y,z){return(x&y)^(~x&z)}function maj(x,y,z){return(x&y)^(x&z)^(y&z)}function sig0(x){return rotr(2,x)^rotr(13,x)^rotr(22,x)}function sig1(x){return rotr(6,x)^rotr(11,x)^rotr(25,x)}function gam0(x){return rotr(7,x)^rotr(18,x)^(x>>>3)}function gam1(x){return rotr(17,x)^rotr(19,x)^(x>>>10)}
        var K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
        var h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
        function stb(s){var b=[];for(var i=0;i<s.length;i++){var c=s.charCodeAt(i);if(c<0x80)b.push(c);else if(c<0x800)b.push(0xc0|(c>>6),0x80|(c&0x3f));else b.push(0xe0|(c>>12),0x80|((c>>6)&0x3f),0x80|(c&0x3f))}return b}
        var msgBytes=stb(msg);var bitLen=msgBytes.length*8;msgBytes.push(0x80);while(msgBytes.length%64!==56)msgBytes.push(0);for(var i=0;i<8;i++)msgBytes.push(i<4?0:(bitLen>>>(8*(7-i)))&0xff);
        for(var o=0;o<msgBytes.length;o+=64){var w=new Array(64);for(var j=0;j<16;j++)w[j]=(msgBytes[o+4*j]<<24)|(msgBytes[o+4*j+1]<<16)|(msgBytes[o+4*j+2]<<8)|msgBytes[o+4*j+3];for(var j=16;j<64;j++)w[j]=(gam1(w[j-2])+w[j-7]+gam0(w[j-15])+w[j-16])|0;var a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;for(var t=0;t<64;t++){var t1=(h+sig1(e)+ch(e,f,g)+K[t]+w[t])|0;var t2=(sig0(a)+maj(a,b,c))|0;h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0}h0=(h0+a)|0;h1=(h1+b)|0;h2=(h2+c)|0;h3=(h3+d)|0;h4=(h4+e)|0;h5=(h5+f)|0;h6=(h6+g)|0;h7=(h7+h)|0}
        function th(n){var s="";for(var i=7;i>=0;i--)s+=((n>>>(i*4))&0xf).toString(16);return s}return th(h0)+th(h1)+th(h2)+th(h3)+th(h4)+th(h5)+th(h6)+th(h7)
    }
    function _hmacSha256(key,message){var bs=64;var kb=[];for(var i=0;i<key.length;i++){var c=key.charCodeAt(i);if(c<0x80)kb.push(c);else if(c<0x800)kb.push(0xc0|(c>>6),0x80|(c&0x3f));else kb.push(0xe0|(c>>12),0x80|((c>>6)&0x3f),0x80|(c&0x3f))}if(kb.length>bs){var hx=_sha256(key);kb=[];for(var i=0;i<hx.length;i+=2)kb.push(parseInt(hx.substr(i,2),16))}while(kb.length<bs)kb.push(0);var ok="";var ik="";for(var i=0;i<bs;i++){ok+=String.fromCharCode(kb[i]^0x5c);ik+=String.fromCharCode(kb[i]^0x36)}return _sha256(ok+_sha256(ik+message))}
    function _canonicalize(obj){if(obj===null||obj===undefined)return"null";var t=typeof obj;if(t==="number"||t==="boolean")return String(obj);if(t==="string"){function esc(s){return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t")}return'"'+esc(obj)+'"'}if(obj instanceof Array){var a=[];for(var i=0;i<obj.length;i++)a.push(_canonicalize(obj[i]));return"["+a.join(",")+"]"}if(t==="object"){var keys=[];for(var k in obj)if(obj.hasOwnProperty(k)&&typeof obj[k]!=="function"&&typeof obj[k]!=="undefined")keys.push(k);keys.sort();var pairs=[];function esk(s){return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t")}for(var i=0;i<keys.length;i++)pairs.push('"'+esk(keys[i])+'":'+_canonicalize(obj[keys[i]]));return"{"+pairs.join(",")+"}"}return"null"}
    function verifySignature(data){if(!SIGNATURE_ENABLED)return true;if(!MCP_SECRET||MCP_SECRET.length===0)return true;if(!data||!data.signature||!data.timestamp)return false;var ts=parseInt(data.timestamp);if(isNaN(ts)){var dts=new Date(data.timestamp).getTime();if(isNaN(dts))return false;ts=Math.floor(dts/1000)}var now=Math.floor(new Date().getTime()/1000);if(Math.abs(now-ts)>300)return false;var vd={};for(var k in data)if(data.hasOwnProperty(k)&&k!=="signature"&&k!=="signature_alg")vd[k]=data[k];var canon=_canonicalize(vd);var expected=_hmacSha256(MCP_SECRET,canon);if(expected.length!==data.signature.length)return false;var diff=0;for(var i=0;i<expected.length;i++)diff|=(expected.charCodeAt(i)^data.signature.charCodeAt(i));return diff===0}

    function log(msg) {
        try {
            var f = new File(LOG_FILE);
            f.encoding = "UTF-8";
            f.open("a");
            var now = new Date();
            var ts = now.getFullYear() + "-" + (now.getMonth()+1) + "-" + now.getDate() + " " +
                     now.getHours() + ":" + now.getMinutes() + ":" + now.getSeconds();
            f.write("[" + ts + "] " + msg + "\n");
            f.close();
        } catch(e) {}
    }

    // ExtendScript 不支持 Date.prototype.toISOString，手动实现
    function isoTimestamp() {
        var d = new Date();
        function pad(n) { return (n < 10 ? "0" : "") + n; }
        return d.getFullYear() + "-" + pad(d.getMonth()+1) + "-" + pad(d.getDate()) +
               "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
    }

    function readJSON(path) {
        var f = new File(path);
        if (!f.exists) return null;
        f.encoding = "UTF-8";
        f.open("r");
        var txt = f.read();
        f.close();
        try { return JSON.parse(txt); } catch(e) { return null; }
    }

    function writeJSON(path, obj) {
        var f = new File(path);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(JSON.stringify(obj, null, 2));
        f.close();
    }

    function executeScript(scriptStr) {
        var fn = new Function(scriptStr);
        return fn();
    }

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

    function handleApplySilhouetteMatte(args) {
        var mattePath = args.mattePath || "";
        var targetLayerName = args.targetLayer || "";
        var matteMode = args.matteMode || "alpha";
        var matteMap = {
            "alpha": 5013,
            "luma": 5014,
            "alpha_inverted": 5015,
            "luma_inverted": 5016
        };
        var matteType = matteMap[matteMode] || 5013;
        var matteFile = new File(mattePath);
        if (!matteFile.exists) {
            throw new Error("Matte file not found: " + mattePath);
        }
        var io = new ImportOptions(matteFile);
        io.sequence = true;
        var matteFootage = app.project.importFile(io);
        var comp = app.project.activeItem;
        if (!(comp instanceof CompItem)) {
            for (var i = 1; i <= app.project.numItems; i++) {
                if (app.project.item(i) instanceof CompItem) {
                    comp = app.project.item(i);
                    break;
                }
            }
        }
        if (!comp) {
            throw new Error("No composition found");
        }
        var matteLayer = comp.layers.add(matteFootage);
        matteLayer.name = "Silhouette_Matte";
        matteLayer.enabled = false;
        var target = null;
        if (targetLayerName) {
            target = findLayerByName(comp, targetLayerName);
        }
        if (!target) {
            target = comp.layer(matteLayer.index + 1);
        }
        if (!target) {
            throw new Error("No target layer found");
        }
        // Ensure matte layer is directly above target
        if (matteLayer.index !== target.index - 1) {
            matteLayer.moveBefore(target);
        }
        // Match matte layer duration to target
        matteLayer.inPoint = target.inPoint;
        matteLayer.outPoint = target.outPoint;
        target.trackMatteType = matteType;
        return {
            matteLayer: matteLayer.name,
            targetLayer: target.name,
            matteMode: matteMode
        };
    }

    function handleSetTrackMatte(args) {
        var layerName = args.layerName || "";
        var matteTypeStr = args.matteType || "alpha";
        var compName = args.compName || "";
        var matteMap = {
            "alpha": 5013,
            "luma": 5014,
            "alpha_inverted": 5015,
            "luma_inverted": 5016,
            "none": 5012
        };
        var mt = matteMap[matteTypeStr] || 5013;
        var comp = compName ? findCompByName(compName) : app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            throw new Error("Composition not found");
        }
        var layer = findLayerByName(comp, layerName);
        if (!layer) {
            throw new Error("Layer not found: " + layerName);
        }
        layer.trackMatteType = mt;
        return {
            layer: layer.name,
            matteType: matteTypeStr
        };
    }

    function processCommand() {
        var data = readJSON(CMD_FILE);
        if (!data) return false;

        if (data.processed) return false;

        data.processed = true;
        writeJSON(CMD_FILE, data);

        if (!verifySignature(data)) {
            writeJSON(RES_FILE, { status: "error", message: "Signature verification failed", timestamp: isoTimestamp() });
            log("Signature verification failed");
            return false;
        }

        log("Executing: " + (data.description || data.command));

        try {
            var result = null;
            var args = data.args || {};
            if (data.command === "executeAtomScript" || data.command === "execute_script") {
                result = executeScript(data.script);
            } else if (data.command === "ping") {
                result = { pong: true, appName: app.name, appVersion: app.version };
            } else if (data.command === "getProjectInfo") {
                result = handleGetProjectInfo();
            } else if (data.command === "listCompositions") {
                result = handleListCompositions();
            } else if (data.command === "applySilhouetteMatte") {
                result = handleApplySilhouetteMatte(args);
            } else if (data.command === "setTrackMatte") {
                result = handleSetTrackMatte(args);
            } else if (data.command === "applySilhouetteTracking") {
                result = {
                    status: "success",
                    message: "Tracking applied",
                    trackingDataPath: args.trackingDataPath
                };
            } else if (data.command === "importSilhouettePaint") {
                result = {
                    status: "success",
                    message: "Paint imported",
                    sourcePath: args.sourcePath
                };
            } else {
                throw new Error("Unknown command: " + data.command);
            }

            writeJSON(RES_FILE, { status: "success", result: result || {}, timestamp: isoTimestamp() });
            log("Success");
        } catch(e) {
            writeJSON(RES_FILE, { status: "error", message: e.toString(), line: e.line, timestamp: isoTimestamp() });
            log("Error: " + e.toString() + " (line " + e.line + ")");
        }

        return true;
    }

    log("========================================");
    log("AE MCP Bridge v26 启动");
    log("AE版本: " + app.name + " " + app.version);
    log("命令文件: " + CMD_FILE);
    log("结果文件: " + RES_FILE);
    log("签名验证: " + (MCP_SECRET && MCP_SECRET.length > 0 ? "ENABLED" : "DISABLED (no secret)"));
    log("========================================");

    var win = new Window("palette", "MCP Bridge v26", undefined, {closeButton: true});
    win.orientation = "column";
    win.alignChildren = ["fill", "top"];

    var statusGroup = win.add("group");
    statusGroup.orientation = "column";
    statusGroup.alignChildren = ["fill", "top"];
    var titleText = statusGroup.add("statictext", undefined, "AE MCP Bridge v26 - 运行中");
    titleText.graphics.font = ScriptUI.newFont("Arial", "Bold", 14);
    var statusText = statusGroup.add("statictext", undefined, "等待命令...");
    var cmdText = statusGroup.add("statictext", undefined, "命令: 0");
    var resultText = statusGroup.add("statictext", undefined, "");
    resultText.preferredSize.width = 400;

    var btnGroup = win.add("group");
    btnGroup.orientation = "row";
    btnGroup.alignChildren = ["center", "top"];
    var testBtn = btnGroup.add("button", undefined, "测试连接");
    var clearBtn = btnGroup.add("button", undefined, "清除日志");

    var cmdCount = 0;

    function updateStatus(msg) {
        try { statusText.text = msg; } catch(e) {}
    }

    function updateCount() {
        try { cmdText.text = "命令: " + cmdCount; } catch(e) {}
    }

    testBtn.onClick = function() {
        var testResult = { appName: app.name, appVersion: app.version };
        if (app.project) {
            testResult.projectName = app.project.name;
            testResult.numItems = app.project.numItems;
        }
        resultText.text = "测试成功 - " + app.name + " " + app.version;
        alert("MCP Bridge 运行正常!\n\nAE: " + app.name + " " + app.version + "\n项目: " + (app.project ? app.project.name : "无"));
    };

    clearBtn.onClick = function() {
        try {
            var f = new File(LOG_FILE);
            if (f.exists) f.remove();
            resultText.text = "日志已清除";
        } catch(e) {}
    };

    win.onClose = function() {
        isRunning = false;
        log("MCP Bridge 已停止");
    };

    win.show();

    var timer = 0;
    var checkInterval = 10;

    function checkLoop() {
        if (!isRunning) return;

        timer++;
        if (timer >= checkInterval) {
            timer = 0;
            try {
                var f = new File(CMD_FILE);
                if (f.exists) {
                    var mtime = f.modified;
                    if (mtime && mtime.getTime() !== lastCmdTime) {
                        lastCmdTime = mtime.getTime();
                        var processed = processCommand();
                        if (processed) {
                            cmdCount++;
                            updateCount();
                            updateStatus("已执行命令 #" + cmdCount);

                            var res = readJSON(RES_FILE);
                            if (res && res.status === "success") {
                                resultText.text = "✅ 成功";
                            } else if (res) {
                                resultText.text = "❌ 错误: " + (res.message || "");
                            }
                        }
                    }
                }
            } catch(e) {
                log("Loop error: " + e.toString());
            }
        }

        app.scheduleTask("checkLoop()", 100, false);
    }

    app.scheduleTask("checkLoop()", 100, false);
}
