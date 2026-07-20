// ================================================================
// Photoshop MCP Bridge Listener
// 文件轮询通信 - 每次500ms检查命令文件
// ================================================================

#target photoshop

(function() {
    "use strict";
    
    // JSON polyfill
    if (typeof JSON === "undefined" || typeof JSON.parse !== "function") {
        // Minimal JSON support for ExtendScript
        if (typeof JSON === "undefined") { JSON = {}; }
        JSON.parse = function(str) {
            return eval("(" + str + ")");
        };
        JSON.stringify = function(obj) {
            if (obj === null || obj === undefined) return "null";
            if (typeof obj === "number" || typeof obj === "boolean") return String(obj);
            if (typeof obj === "string") {
                return '"' + obj.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r") + '"';
            }
            if (obj instanceof Array) {
                var items = [];
                for (var i = 0; i < obj.length; i++) items.push(JSON.stringify(obj[i]));
                return "[" + items.join(",") + "]";
            }
            if (typeof obj === "object") {
                var pairs = [];
                for (var k in obj) {
                    if (obj.hasOwnProperty(k)) {
                        pairs.push('"' + k + '":' + JSON.stringify(obj[k]));
                    }
                }
                return "{" + pairs.join(",") + "}";
            }
            return "null";
        };
    }
    
    // ================================================================
    //  Configuration
    // ================================================================
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.photoshop-mcp-bridge";
    var CMD_FILE = BRIDGE_DIR + "/photoshop_command.json";
    var RES_FILE = BRIDGE_DIR + "/photoshop_result.json";
    var LOG_FILE = BRIDGE_DIR + "/photoshop_bridge.log";
    var POLL_INTERVAL = 500; // ms
    
    // ================================================================
    //  Utility Functions
    // ================================================================
    function log(msg) {
        try {
            var f = new File(LOG_FILE);
            f.open("a");
            f.writeln("[" + new Date().toLocaleString() + "] " + msg);
            f.close();
        } catch(e) {}
    }
    
    function writeResult(data) {
        try {
            var f = new File(RES_FILE);
            f.open("w");
            f.write(JSON.stringify(data));
            f.close();
        } catch(e) {
            log("writeResult error: " + e.message);
        }
    }
    
    function readCommand() {
        try {
            var f = new File(CMD_FILE);
            if (!f.exists) return null;
            f.open("r");
            var content = f.read();
            f.close();
            if (!content || content.length < 5) return null;
            var cmd = JSON.parse(content);
            if (cmd.processed) return null;
            return cmd;
        } catch(e) {
            return null;
        }
    }
    
    function markProcessed() {
        try {
            var f = new File(CMD_FILE);
            if (!f.exists) return;
            f.open("r");
            var content = f.read();
            f.close();
            var cmd = JSON.parse(content);
            cmd.processed = true;
            f.open("w");
            f.write(JSON.stringify(cmd));
            f.close();
        } catch(e) {}
    }
    
    // ================================================================
    //  Command Handlers
    // ================================================================
    var handlers = {};
    
    // Ping
    handlers.ping = function(args) {
        return { status: "success", result: "pong", app: "photoshop", version: app.version };
    };
    
    // Get App Info
    handlers.getAppInfo = function(args) {
        return {
            status: "success",
            result: {
                name: app.name,
                version: app.version,
                build: app.build,
                path: app.path.fsName,
                locale: app.locale
            }
        };
    };
    
    // Execute arbitrary script
    handlers.executeScript = function(args) {
        try {
            var script = args.script || "";
            var result = eval(script);
            return { status: "success", result: String(result) };
        } catch(e) {
            return { status: "error", error: e.message, line: e.line };
        }
    };
    
    // Get Document Info
    handlers.getDocumentInfo = function(args) {
        try {
            if (!app.documents.length) {
                return { status: "success", result: { hasDocument: false } };
            }
            var doc = app.activeDocument;
            return {
                status: "success",
                result: {
                    hasDocument: true,
                    name: doc.name,
                    width: doc.width.as("px"),
                    height: doc.height.as("px"),
                    resolution: doc.resolution,
                    mode: doc.mode.toString(),
                    layers: doc.layers.length,
                    activeLayer: doc.activeLayer.name,
                    colorProfile: doc.colorProfileName
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Create Document
    handlers.createDocument = function(args) {
        try {
            var w = args.width || 1920;
            var h = args.height || 1080;
            var name = args.name || "Untitled";
            var doc = app.documents.add(w, h, 72, name, NewDocumentMode.RGB);
            return { status: "success", result: { name: doc.name, width: w, height: h } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Apply Filter
    handlers.applyFilter = function(args) {
        try {
            var filterName = args.filter;
            var params = args.params || {};
            // Common filters
            if (filterName === "gaussianBlur") {
                app.activeDocument.activeLayer.applyGaussianBlur(params.radius || 5);
            } else if (filterName === "unsharpMask") {
                app.activeDocument.activeLayer.applyUnSharpMask(params.amount || 100, params.radius || 1, params.threshold || 0);
            } else if (filterName === "noise") {
                app.activeDocument.activeLayer.applyAddNoise(params.amount || 10, NoiseDistribution.UNIFORM, false);
            } else {
                return { status: "error", error: "Unknown filter: " + filterName };
            }
            return { status: "success", result: { filter: filterName, applied: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Export Document
    handlers.exportDocument = function(args) {
        try {
            var outputPath = args.path;
            var format = args.format || "png";
            var doc = app.activeDocument;
            
            var outFile = new File(outputPath);
            
            if (format === "png") {
                var opts = new PNGSaveOptions();
                opts.compression = args.compression || 6;
                doc.saveAs(outFile, opts, true, Extension.LOWERCASE);
            } else if (format === "jpg" || format === "jpeg") {
                var opts = new JPEGSaveOptions();
                opts.quality = args.quality || 10;
                doc.saveAs(outFile, opts, true, Extension.LOWERCASE);
            } else if (format === "psd") {
                var opts = new PhotoshopSaveOptions();
                doc.saveAs(outFile, opts, true, Extension.LOWERCASE);
            } else {
                return { status: "error", error: "Unknown format: " + format };
            }
            return { status: "success", result: { path: outputPath, format: format } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Get Layers Info
    handlers.getLayersInfo = function(args) {
        try {
            var doc = app.activeDocument;
            var layers = [];
            for (var i = 0; i < doc.layers.length; i++) {
                var layer = doc.layers[i];
                layers.push({
                    name: layer.name,
                    visible: layer.visible,
                    opacity: layer.opacity,
                    blendMode: layer.blendMode.toString(),
                    kind: layer.kind.toString(),
                    bounds: {
                        x: layer.bounds[0].as("px"),
                        y: layer.bounds[1].as("px"),
                        width: (layer.bounds[2] - layer.bounds[0]).as("px"),
                        height: (layer.bounds[3] - layer.bounds[1]).as("px")
                    }
                });
            }
            return { status: "success", result: layers };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Adjust Brightness/Contrast
    handlers.adjustBrightnessContrast = function(args) {
        try {
            var doc = app.activeDocument;
            var adj = doc.activeLayer;
            // Use adjustment layer
            var brightness = args.brightness || 0;
            var contrast = args.contrast || 0;
            doc.activeLayer.adjustBrightnessContrast(brightness, contrast);
            return { status: "success", result: { brightness: brightness, contrast: contrast } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Adjust Hue/Saturation
    handlers.adjustHueSaturation = function(args) {
        try {
            // Use batch play for hue/saturation
            var desc = new ActionDescriptor();
            desc.putInteger(stringIDToTypeID("hue"), args.hue || 0);
            desc.putInteger(stringIDToTypeID("saturation"), args.saturation || 0);
            desc.putInteger(stringIDToTypeID("lightness"), args.lightness || 0);
            executeAction(stringIDToTypeID("hueSaturation"), desc, DialogModes.NO);
            return { status: "success", result: args };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Color Balance
    handlers.adjustColorBalance = function(args) {
        try {
            var desc = new ActionDescriptor();
            var levels = new ActionDescriptor();
            levels.putInteger(stringIDToTypeID("cyanRed"), args.cyanRed || 0);
            levels.putInteger(stringIDToTypeID("magentaGreen"), args.magentaGreen || 0);
            levels.putInteger(stringIDToTypeID("yellowBlue"), args.yellowBlue || 0);
            desc.putObject(stringIDToTypeID("shadowLevels"), stringIDToTypeID("colorBalance"), levels);
            desc.putObject(stringIDToTypeID("midtoneLevels"), stringIDToTypeID("colorBalance"), levels);
            desc.putObject(stringIDToTypeID("highlightLevels"), stringIDToTypeID("colorBalance"), levels);
            desc.putBoolean(stringIDToTypeID("preserveLuminosity"), args.preserveLuminosity !== false);
            executeAction(stringIDToTypeID("colorBalance"), desc, DialogModes.NO);
            return { status: "success", result: args };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Resize Image
    handlers.resizeImage = function(args) {
        try {
            var doc = app.activeDocument;
            var w = args.width ? new UnitValue(args.width, "px") : doc.width;
            var h = args.height ? new UnitValue(args.height, "px") : doc.height;
            var res = args.resolution || doc.resolution;
            doc.resizeImage(w, h, res, args.resampleMethod || ResampleMethod.BICUBIC);
            return { status: "success", result: { width: args.width, height: args.height } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Crop
    handlers.crop = function(args) {
        try {
            var doc = app.activeDocument;
            var bounds = [
                new UnitValue(args.x || 0, "px"),
                new UnitValue(args.y || 0, "px"),
                new UnitValue(args.x + (args.width || 100), "px"),
                new UnitValue(args.y + (args.height || 100), "px")
            ];
            doc.crop(bounds, args.angle || 0, args.width || doc.width.as("px"), args.height || doc.height.as("px"));
            return { status: "success", result: { cropped: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // ================================================================
    //  Main Loop
    // ================================================================
    log("Photoshop MCP Bridge Listener started");
    log("Bridge dir: " + BRIDGE_DIR);
    log("Polling every " + POLL_INTERVAL + "ms");
    
    // Create bridge dir if needed
    var dir = new Folder(BRIDGE_DIR);
    if (!dir.exists) dir.create();
    
    var running = true;
    var pollCount = 0;
    
    function poll() {
        try {
            var cmd = readCommand();
            if (cmd && cmd.command) {
                pollCount++;
                log("Command #" + pollCount + ": " + cmd.command);
                
                var handler = handlers[cmd.command];
                var result;
                
                if (handler) {
                    result = handler(cmd.args || {});
                } else {
                    result = { status: "error", error: "Unknown command: " + cmd.command };
                }
                
                result.timestamp = new Date().toISOString();
                writeResult(result);
                markProcessed();
            }
        } catch(e) {
            log("Poll error: " + e.message);
        }
        
        if (running) {
            $.sleep(POLL_INTERVAL);
            poll();
        }
    }
    
    // Start polling
    poll();
    
})();
