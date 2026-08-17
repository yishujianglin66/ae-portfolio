// ============================================================
// AE Knowledge Vault - Premiere Pro Bridge v4
// 放置于: Scripts/Startup/ 目录
// PR 启动时自动加载，使用 app.setTimeout 非阻塞轮询
// ============================================================

#target premiere

// JSON Polyfill
if (typeof JSON === 'undefined') {
    JSON = {
        parse: function(text) { return eval('(' + text + ')'); },
        stringify: function(v) {
            if (v === null) return 'null';
            if (typeof v === 'undefined') return 'undefined';
            if (typeof v === 'number' || typeof v === 'boolean') return String(v);
            if (typeof v === 'string') return '"' + v.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r') + '"';
            if (v instanceof Array) { var a = []; for (var i = 0; i < v.length; i++) a.push(JSON.stringify(v[i])); return '[' + a.join(',') + ']'; }
            if (typeof v === 'object') { var o = []; for (var k in v) if (v.hasOwnProperty(k)) o.push(JSON.stringify(k) + ':' + JSON.stringify(v[k])); return '{' + o.join(',') + '}'; }
            return 'null';
        }
    };
}

(function() {
    var bridgePath = Folder.temp.fsName + "/ae_kv_pr_bridge";
    var bridgeDir = new Folder(bridgePath);
    if (!bridgeDir.exists) bridgeDir.create();

    var logPath = bridgePath + "/bridge_log.txt";
    var readyPath = bridgePath + "/bridge_ready.txt";
    var pollInterval = 300;

    var handlers = {};

    function log(msg) {
        try {
            var f = new File(logPath);
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln("[" + new Date().toUTCString() + "] " + msg);
            f.close();
        } catch(e) {}
    }

    function writeReady() {
        try {
            var f = new File(readyPath);
            f.encoding = "UTF-8";
            f.open("w");
            f.writeln("READY");
            f.writeln("version: 4.0");
            f.writeln("time: " + new Date().toUTCString());
            f.close();
        } catch(e) {}
    }

    function loadAllHandlers() {
        try {
            var handlerFiles = bridgeDir.getFiles("handler_*.jsx");
            for (var i = 0; i < handlerFiles.length; i++) {
                var hf = handlerFiles[i];
                try {
                    hf.encoding = "UTF-8";
                    hf.open("r");
                    var code = hf.read();
                    hf.close();
                    eval(code);
                    log("Loaded handler: " + hf.name);
                } catch(e) {
                    log("Error loading " + hf.name + ": " + e);
                }
            }
        } catch(e) {
            log("loadAllHandlers error: " + e);
        }
    }

    function registerHandler(action, func) {
        handlers[action] = func;
    }

    function processCommand(cmd) {
        var result = { data: null, error: null };
        var action = cmd.action;

        try {
            if (handlers[action]) {
                result.data = handlers[action](cmd);
                return result;
            }

            switch(action) {
                case "ping":
                    result.data = { pong: true, time: new Date().toUTCString(), version: "4.0" };
                    break;

                case "getInfo":
                    result.data = {
                        appName: app.name,
                        version: app.version,
                        projectName: app.project ? app.project.name : "no project",
                        sequenceCount: app.project ? app.project.sequences.length : 0
                    };
                    break;

                case "getProjectInfo":
                    if (!app.project) {
                        result.error = "No project open";
                    } else {
                        var seqs = [];
                        for (var i = 0; i < app.project.sequences.length; i++) {
                            seqs.push({
                                name: app.project.sequences[i].name,
                                id: app.project.sequences[i].sequenceID
                            });
                        }
                        result.data = { name: app.project.name, sequences: seqs };
                    }
                    break;

                case "createSequence":
                    if (!app.project) {
                        result.error = "No project open";
                    } else {
                        var seqName = cmd.name || "New Sequence";
                        try {
                            app.project.newSequence(seqName);
                            var newSeq = null;
                            for (var j = 0; j < app.project.sequences.length; j++) {
                                if (app.project.sequences[j].name === seqName) {
                                    newSeq = app.project.sequences[j];
                                    break;
                                }
                            }
                            result.data = { name: seqName, created: true, id: newSeq ? newSeq.sequenceID : null };
                        } catch(e) {
                            result.error = "Create sequence failed: " + e.message;
                        }
                    }
                    break;

                case "importMedia":
                    if (!app.project) {
                        result.error = "No project open";
                    } else {
                        var files = cmd.files || [];
                        var imported = [];
                        for (var k = 0; k < files.length; k++) {
                            try {
                                var file = new File(files[k]);
                                if (file.exists) {
                                    app.project.importFiles([file]);
                                    imported.push(files[k]);
                                }
                            } catch(e) {
                                log("Import error: " + files[k] + " - " + e);
                            }
                        }
                        result.data = { imported: imported, count: imported.length };
                    }
                    break;

                case "saveProject":
                    if (!app.project) {
                        result.error = "No project open";
                    } else {
                        app.project.save();
                        result.data = { saved: true };
                    }
                    break;

                case "executeScript":
                    if (cmd.script) {
                        try {
                            var scriptResult = eval(cmd.script);
                            result.data = { result: scriptResult ? String(scriptResult) : null };
                        } catch(e) {
                            result.error = "Script error: " + e.message;
                        }
                    } else {
                        result.error = "No script provided";
                    }
                    break;

                case "reloadHandlers":
                    handlers = {};
                    loadAllHandlers();
                    result.data = { reloaded: true, handlerCount: 0 };
                    var hCount = 0;
                    for (var hk in handlers) if (handlers.hasOwnProperty(hk)) hCount++;
                    result.data.handlerCount = hCount;
                    break;

                default:
                    result.error = "Unknown action: " + action;
            }
        } catch(e) {
            result.error = e.toString();
        }

        return result;
    }

    function poll() {
        try {
            var files = bridgeDir.getFiles("cmd_*.json");
            for (var i = 0; i < files.length; i++) {
                var cmdFile = files[i];
                var cmdName = cmdFile.name;
                var resultName = cmdName.replace("cmd_", "result_");
                var resultPath = bridgePath + "/" + resultName;

                var rf = new File(resultPath);
                if (rf.exists) try { rf.remove(); } catch(e) {}

                cmdFile.encoding = "UTF-8";
                cmdFile.open("r");
                var cmdStr = cmdFile.read();
                cmdFile.close();

                var cmd = {};
                try { cmd = eval('(' + cmdStr + ')'); } catch(e) { cmd = {action: "parse_error"}; }

                log("Execute: " + cmd.action);

                var result = processCommand(cmd);

                var wf = new File(resultPath);
                wf.encoding = "UTF-8";
                wf.open("w");
                wf.writeln(JSON.stringify({
                    status: result.error ? "error" : "success",
                    result: result,
                    timestamp: new Date().toUTCString()
                }));
                wf.close();

                try { cmdFile.remove(); } catch(e) {}

                log("Done: " + cmd.action);
            }
        } catch(e) {
            log("Poll error: " + e);
        }
    }

    function startPolling() {
        poll();
        app.setTimeout(startPolling, pollInterval);
    }

    log("=== Bridge v4 starting ===");
    log("Using app.setTimeout for non-blocking polling");

    loadAllHandlers();
    writeReady();
    startPolling();

    log("=== Bridge initialized ===");

    window.aeKVBridge = {
        registerHandler: registerHandler,
        handlers: handlers
    };
})();
