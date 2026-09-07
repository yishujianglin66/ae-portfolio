// ================================================================
// Media Encoder MCP Bridge Listener
// 文件轮询通信 - 每次500ms检查命令文件
// ================================================================

#target mediacoder

(function() {
    "use strict";
    
    // JSON polyfill
    if (typeof JSON === "undefined" || typeof JSON.parse !== "function") {
        if (typeof JSON === "undefined") { JSON = {}; }
        JSON.parse = function(str) { return eval("(" + str + ")"); };
        JSON.stringify = function(obj) {
            if (obj === null || obj === undefined) return "null";
            if (typeof obj === "number" || typeof obj === "boolean") return String(obj);
            if (typeof obj === "string") {
                return '"' + obj.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n") + '"';
            }
            if (obj instanceof Array) {
                var items = [];
                for (var i = 0; i < obj.length; i++) items.push(JSON.stringify(obj[i]));
                return "[" + items.join(",") + "]";
            }
            if (typeof obj === "object") {
                var pairs = [];
                for (var k in obj) {
                    if (obj.hasOwnProperty(k)) pairs.push('"' + k + '":' + JSON.stringify(obj[k]));
                }
                return "{" + pairs.join(",") + "}";
            }
            return "null";
        };
    }
    
    // ================================================================
    //  Configuration
    // ================================================================
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.media_encoder-mcp-bridge";
    var CMD_FILE = BRIDGE_DIR + "/media_encoder_command.json";
    var RES_FILE = BRIDGE_DIR + "/media_encoder_result.json";
    var LOG_FILE = BRIDGE_DIR + "/media_encoder_bridge.log";
    var POLL_INTERVAL = 500;
    
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
        } catch(e) { log("writeResult error: " + e.message); }
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
        } catch(e) { return null; }
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
        return { status: "success", result: "pong", app: "media_encoder", version: app.version };
    };
    
    // Get App Info
    handlers.getAppInfo = function(args) {
        try {
            return {
                status: "success",
                result: {
                    name: app.name || "Media Encoder",
                    version: app.version,
                    path: app.path ? app.path.fsName : "unknown",
                    defaultOutputFolder: app.defaultOutputFolder ? app.defaultOutputFolder.fsName : ""
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Execute arbitrary script
    handlers.executeScript = function(args) {
        try {
            var script = args.script || "";
            var result = eval(script);
            return { status: "success", result: String(result) };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Add to Queue
    handlers.addToQueue = function(args) {
        try {
            var sourcePath = args.source;
            var presetPath = args.preset || "";
            
            var sourceFile = new File(sourcePath);
            if (!sourceFile.exists) {
                return { status: "error", error: "Source file not found: " + sourcePath };
            }
            
            // Add to encoding queue
            var encoder = app.encoder;
            var job;
            
            if (presetPath) {
                var presetFile = new File(presetPath);
                job = encoder.encode(sourceFile, presetFile);
            } else {
                // Use default H.264 preset
                job = app.encode(sourceFile, "H.264");
            }
            
            return { status: "success", result: { source: sourcePath, added: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Start Encoding
    handlers.startEncoding = function(args) {
        try {
            app.startBatch();
            return { status: "success", result: { started: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Get Queue Status
    handlers.getQueueStatus = function(args) {
        try {
            var encoder = app.encoder;
            var queueItems = [];
            
            if (encoder && encoder.queueItems) {
                for (var i = 0; i < encoder.queueItems.numItems; i++) {
                    var item = encoder.queueItems[i];
                    queueItems.push({
                        source: item.source ? item.source.fsName : "",
                        output: item.destPath ? item.destPath.fsName : "",
                        status: item.status || "unknown",
                        progress: item.progress || 0
                    });
                }
            }
            
            return {
                status: "success",
                result: {
                    queueItems: queueItems,
                    itemCount: queueItems.length,
                    isEncoding: app.isEncoding || false
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Get Available Presets
    handlers.getPresets = function(args) {
        try {
            var presets = [];
            var presetGroups = app.presets;
            
            if (presetGroups) {
                for (var i = 0; i < presetGroups.numItems; i++) {
                    var group = presetGroups[i];
                    presets.push({
                        name: group.name || "Preset " + i,
                        type: group.format || "unknown"
                    });
                }
            }
            
            // Add common built-in presets
            var commonPresets = [
                "H.264", "H.264 Match Source", "H.264 High Quality",
                "ProRes 422", "ProRes 4444",
                "MPEG4", "MPEG2",
                "HEVC (H.265)",
                "DNxHD", "DNxHR"
            ];
            
            return {
                status: "success",
                result: {
                    presets: presets,
                    commonPresets: commonPresets,
                    count: presets.length
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Set Output Format
    handlers.setOutputFormat = function(args) {
        try {
            var format = args.format || "H.264";
            var outputPath = args.path || "";
            
            if (outputPath) {
                app.defaultOutputFolder = new Folder(outputPath);
            }
            
            return { status: "success", result: { format: format, outputPath: outputPath } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Clear Queue
    handlers.clearQueue = function(args) {
        try {
            var encoder = app.encoder;
            if (encoder && encoder.queueItems) {
                // Remove all items from queue
                while (encoder.queueItems.numItems > 0) {
                    encoder.queueItems[0].remove();
                }
            }
            return { status: "success", result: { cleared: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Get Encoder Info
    handlers.getEncoderInfo = function(args) {
        try {
            return {
                status: "success",
                result: {
                    name: app.name,
                    version: app.version,
                    isEncoding: app.isEncoding || false,
                    defaultOutputFolder: app.defaultOutputFolder ? app.defaultOutputFolder.fsName : "",
                    gpuAccel: app.gpuAccelEnabled || false
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // ================================================================
    //  Main Loop
    // ================================================================
    log("Media Encoder MCP Bridge Listener started");
    log("Bridge dir: " + BRIDGE_DIR);
    
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
    
    poll();
    
})();
