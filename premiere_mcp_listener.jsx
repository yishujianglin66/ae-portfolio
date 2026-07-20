// ================================================================
// Premiere Pro MCP Bridge Listener
// 文件轮询通信 - 每次500ms检查命令文件
// ================================================================

#target premierepro

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
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge";
    var CMD_FILE = BRIDGE_DIR + "/premiere_command.json";
    var RES_FILE = BRIDGE_DIR + "/premiere_result.json";
    var LOG_FILE = BRIDGE_DIR + "/premiere_bridge.log";
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
        return { status: "success", result: "pong", app: "premiere", version: app.version };
    };
    
    // Get App Info
    handlers.getAppInfo = function(args) {
        try {
            return {
                status: "success",
                result: {
                    name: app.name || "Premiere Pro",
                    version: app.version,
                    build: app.build || "unknown",
                    path: app.path ? app.path.fsName : "unknown"
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
    
    // Get Project Info
    handlers.getProjectInfo = function(args) {
        try {
            var project = app.project;
            var sequences = [];
            if (project.sequences) {
                for (var i = 0; i < project.sequences.numSequences; i++) {
                    var seq = project.sequences[i];
                    sequences.push({
                        name: seq.name,
                        duration: seq.end ? seq.end.seconds : 0,
                        width: seq.frameSize ? seq.frameSize[0] : 0,
                        height: seq.frameSize ? seq.frameSize[1] : 0,
                        fps: seq.settings ? seq.settings.videoSettings.frameRate : 0
                    });
                }
            }
            return {
                status: "success",
                result: {
                    name: project.name || "Untitled",
                    path: project.path ? project.path.fsName : "",
                    sequences: sequences,
                    sequenceCount: sequences.length
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Import Media
    handlers.importMedia = function(args) {
        try {
            var files = args.files || [];
            var imported = [];
            var project = app.project;
            
            for (var i = 0; i < files.length; i++) {
                var filePath = files[i];
                var f = new File(filePath);
                if (f.exists) {
                    project.importFiles([filePath], false, false, false);
                    imported.push(filePath);
                }
            }
            return { status: "success", result: { imported: imported, count: imported.length } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Get Timeline Info
    handlers.getTimelineInfo = function(args) {
        try {
            var seq = app.project.activeSequence;
            if (!seq) {
                return { status: "success", result: { hasSequence: false } };
            }
            
            var tracks = [];
            // Video tracks
            if (seq.videoTracks) {
                for (var i = 0; i < seq.videoTracks.numTracks; i++) {
                    var track = seq.videoTracks[i];
                    var clips = [];
                    for (var j = 0; j < track.clips.numItems; j++) {
                        var clip = track.clips[j];
                        clips.push({
                            name: clip.name || "Clip " + j,
                            start: clip.start ? clip.start.seconds : 0,
                            end: clip.end ? clip.end.seconds : 0,
                            duration: clip.duration ? clip.duration.seconds : 0
                        });
                    }
                    tracks.push({
                        type: "video",
                        index: i,
                        name: track.name || ("V" + (i+1)),
                        clips: clips,
                        clipCount: clips.length
                    });
                }
            }
            // Audio tracks
            if (seq.audioTracks) {
                for (var i = 0; i < seq.audioTracks.numTracks; i++) {
                    var track = seq.audioTracks[i];
                    tracks.push({
                        type: "audio",
                        index: i,
                        name: track.name || ("A" + (i+1)),
                        clipCount: track.clips ? track.clips.numItems : 0
                    });
                }
            }
            
            return {
                status: "success",
                result: {
                    hasSequence: true,
                    name: seq.name,
                    duration: seq.end ? seq.end.seconds : 0,
                    width: seq.frameSize ? seq.frameSize[0] : 1920,
                    height: seq.frameSize ? seq.frameSize[1] : 1080,
                    tracks: tracks,
                    trackCount: tracks.length
                }
            };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Add Clip to Sequence
    handlers.addToSequence = function(args) {
        try {
            var seq = app.project.activeSequence;
            if (!seq) return { status: "error", error: "No active sequence" };
            
            var clipName = args.clip;
            var trackIndex = args.track || 0;
            var position = args.position || 0;
            
            // Find clip in project
            var projectItem = null;
            var rootItem = app.project.rootItem;
            for (var i = 0; i < rootItem.children.numItems; i++) {
                var item = rootItem.children[i];
                if (item.name === clipName) {
                    projectItem = item;
                    break;
                }
            }
            
            if (!projectItem) {
                return { status: "error", error: "Clip not found: " + clipName };
            }
            
            // Create clip on timeline
            var track = seq.videoTracks[trackIndex];
            var time = new Time(position);
            track.insertClip(projectItem, time);
            
            return { status: "success", result: { clip: clipName, track: trackIndex, position: position } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Apply Transition
    handlers.applyTransition = function(args) {
        try {
            var seq = app.project.activeSequence;
            if (!seq) return { status: "error", error: "No active sequence" };
            
            var transitionName = args.name || "Cross Dissolve";
            var duration = args.duration || 1.0;
            
            // Use QE DOM for transitions
            if (typeof qe !== "undefined") {
                var track = seq.videoTracks[0];
                if (track.clips.numItems > 0) {
                    var clip = track.clips[0];
                    clip.addTransition(transitionName, duration, "start");
                    return { status: "success", result: { transition: transitionName, applied: true } };
                }
            }
            
            return { status: "error", error: "QE DOM not available or no clips" };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Export Sequence
    handlers.exportSequence = function(args) {
        try {
            var seq = app.project.activeSequence;
            if (!seq) return { status: "error", error: "No active sequence" };
            
            var outputPath = args.path;
            var preset = args.preset || "H.264";
            
            // Use AMEClear or export via app
            var exporter = app.project.exportSequence(seq, outputPath);
            
            return { status: "success", result: { path: outputPath, preset: preset, exported: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Create Sequence
    handlers.createSequence = function(args) {
        try {
            var name = args.name || "New Sequence";
            var seq = app.project.sequences.createSequence(name, "sequenceID");
            return { status: "success", result: { name: seq.name, created: true } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Get Effects
    handlers.getEffects = function(args) {
        try {
            var seq = app.project.activeSequence;
            if (!seq) return { status: "success", result: { effects: [] } };
            
            var effects = [];
            var track = seq.videoTracks[0];
            if (track && track.clips.numItems > 0) {
                var clip = track.clips[0];
                if (clip.components) {
                    for (var i = 0; i < clip.components.numItems; i++) {
                        var comp = clip.components[i];
                        effects.push({
                            name: comp.displayName || comp.name,
                            matchName: comp.matchName || ""
                        });
                    }
                }
            }
            return { status: "success", result: { effects: effects } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // Set Playback Position
    handlers.setPlaybackPosition = function(args) {
        try {
            var seq = app.project.activeSequence;
            if (!seq) return { status: "error", error: "No active sequence" };
            var position = args.position || 0;
            seq.setPlayerPosition(new Time(position));
            return { status: "success", result: { position: position } };
        } catch(e) {
            return { status: "error", error: e.message };
        }
    };
    
    // ================================================================
    //  Main Loop
    // ================================================================
    log("Premiere Pro MCP Bridge Listener started");
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
