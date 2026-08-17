// ============================================================
// AE Knowledge Vault - Premiere Pro 全自动剪辑桥接
// 放置于: Scripts/Startup/ 目录
// PR 启动时自动加载，监听 JSON 命令并执行
// ============================================================

#target premiere

// JSON Polyfill for ExtendScript
if (typeof JSON === 'undefined') {
    JSON = {
        parse: function(text) {
            return eval('(' + text + ')');
        },
        stringify: function(value) {
            if (value === null) return 'null';
            if (typeof value === 'undefined') return 'undefined';
            if (typeof value === 'number' || typeof value === 'boolean') return String(value);
            if (typeof value === 'string') return '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r') + '"';
            if (value instanceof Array) {
                var items = [];
                for (var i = 0; i < value.length; i++) {
                    items.push(JSON.stringify(value[i]));
                }
                return '[' + items.join(',') + ']';
            }
            if (typeof value === 'object') {
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

(function() {
    // 桥接目录
    var bridgePath = Folder.temp.fsName + "/ae_kv_pr_bridge";
    var bridgeDir = new Folder(bridgePath);
    if (!bridgeDir.exists) {
        bridgeDir.create();
    }

    // 日志函数
    function log(msg) {
        try {
            var logFile = new File(bridgePath + "/bridge_log.txt");
            logFile.encoding = "UTF-8";
            logFile.open("a");
            logFile.writeln("[" + new Date().toUTCString() + "] " + msg);
            logFile.close();
        } catch(e) {}
    }

    log("=== Bridge starting ===");
    try {
        log("PR version: " + app.version);
        log("app type: " + typeof app);
        log("project: " + (app.project ? "exists" : "null"));
    } catch(e) {
        log("Version check error: " + e.toString());
    }

    // 写入就绪标记
    try {
        var readyFile = new File(bridgePath + "/bridge_ready.txt");
        readyFile.encoding = "UTF-8";
        readyFile.open("w");
        readyFile.writeln("READY");
        readyFile.writeln("version: " + app.version);
        readyFile.writeln("time: " + new Date().toUTCString());
        readyFile.close();
        log("Ready file written");
    } catch(e) {
        log("Failed to write ready file: " + e.toString());
    }

    // 命令执行函数
    function executeCommand(cmd) {
        var result = {};
        var action = cmd.action || "unknown";

        log("Executing: " + action);

        try {
            switch(action) {
                case "ping":
                    result.pong = true;
                    result.version = app.version;
                    result.timestamp = new Date().toUTCString();
                    break;

                case "importMedia":
                    result.imported = 0;
                    result.clipNames = [];
                    var files = cmd.files || [];
                    for (var i = 0; i < files.length; i++) {
                        try {
                            var f = new File(files[i]);
                            if (f.exists) {
                                var importResults = app.project.importFiles([f], 1, app.project.rootItem, 0);
                                result.imported++;
                                result.clipNames.push(f.displayName);
                                log("  imported: " + f.displayName);
                            } else {
                                log("  file not found: " + files[i]);
                            }
                        } catch(e) {
                            log("Import error: " + e.toString());
                        }
                    }
                    break;

                case "createSequence":
                    var seqName = cmd.name || "Auto Sequence";
                    try {
                        var seq = app.project.newSequence(seqName);
                        result.created = true;
                        result.sequenceName = seqName;
                        log("  Sequence created: " + seqName);
                    } catch(e) {
                        result.error = e.toString();
                        log("  Create seq error: " + e.toString());
                    }
                    break;

                case "getProjectInfo":
                    try {
                        result.numSequences = app.project.sequences.length;
                        result.numItems = app.project.rootItem.children.length;
                        result.sequences = [];
                        for (var s = 0; s < app.project.sequences.length; s++) {
                            var seq = app.project.sequences[s];
                            var seqInfo = {
                                name: seq.name,
                                videoTracks: seq.videoTracks.length,
                                audioTracks: seq.audioTracks.length
                            };
                            if (seq.videoTracks.length > 0) {
                                seqInfo.clipsOnV1 = seq.videoTracks[0].clips.length;
                            }
                            result.sequences.push(seqInfo);
                        }
                    } catch(e) {
                        result.error = e.toString();
                    }
                    break;

                case "addClipToTrack":
                    var trackIdx = cmd.track || 0;
                    var startTime = cmd.startTime || 0;
                    var clipName = cmd.clipName || "";

                    try {
                        if (app.project.sequences.length > 0) {
                            var seq = app.project.sequences[0];
                            var track = seq.videoTracks[trackIdx];

                            // 查找素材
                            var targetClip = null;
                            for (var k = 0; k < app.project.rootItem.children.length; k++) {
                                var item = app.project.rootItem.children[k];
                                if (item.type === ProjectItemType.CLIP) {
                                    if (clipName && item.name === clipName) {
                                        targetClip = item;
                                        break;
                                    }
                                    if (!clipName && !targetClip) {
                                        targetClip = item;
                                    }
                                }
                            }

                            if (targetClip) {
                                track.insertClip(targetClip, startTime);
                                result.added = true;
                                log("  Added clip: " + targetClip.name + " at " + startTime);
                            } else {
                                result.error = "Clip not found";
                            }
                        }
                    } catch(e) {
                        result.error = e.toString();
                        log("  addClip error: " + e.toString());
                    }
                    break;

                case "saveProject":
                    try {
                        app.project.save();
                        result.saved = true;
                    } catch(e) {
                        result.error = e.toString();
                    }
                    break;

                case "executeScript":
                    // 动态脚本执行
                    try {
                        var scriptCode = cmd.script || "";
                        if (scriptCode) {
                            var evalResult = eval(scriptCode);
                            result.evalResult = String(evalResult);
                            result.executed = true;
                            log("  Script executed, result: " + result.evalResult);
                        } else {
                            result.error = "Empty script";
                        }
                    } catch(e) {
                        result.error = e.toString();
                        log("  Script error: " + e.toString());
                    }
                    break;

                case "executeScriptFile":
                    // 执行脚本文件
                    try {
                        var scriptPath = cmd.scriptPath || "";
                        if (scriptPath) {
                            var scriptFile = new File(scriptPath);
                            if (scriptFile.exists) {
                                scriptFile.encoding = "UTF-8";
                                scriptFile.open("r");
                                var scriptContent = scriptFile.read();
                                scriptFile.close();
                                
                                var evalResult = eval(scriptContent);
                                result.evalResult = String(evalResult);
                                result.executed = true;
                                log("  Script file executed: " + scriptPath);
                            } else {
                                result.error = "Script file not found: " + scriptPath;
                            }
                        } else {
                            result.error = "Empty script path";
                        }
                    } catch(e) {
                        result.error = e.toString();
                        log("  Script file error: " + e.toString());
                    }
                    break;

                default:
                    result.error = "Unknown action: " + action;
            }
        } catch(e) {
            result.error = e.toString();
            log("Command error: " + e.toString());
        }

        return result;
    }

    // 处理单个命令文件
    function processCommandFile(cmdFile) {
        try {
            var cmdName = cmdFile.name;
            var resultName = cmdName.replace("cmd_", "result_");
            var resultPath = bridgePath + "/" + resultName;
            var resultFile = new File(resultPath);

            // 总是重新处理（删除旧结果文件，避免跳过）
            if (resultFile.exists) {
                try { resultFile.remove(); } catch(e) {}
            }

            // 读取命令
            var cmdStr = "";
            cmdFile.encoding = "UTF-8";
            cmdFile.open("r");
            cmdStr = cmdFile.read();
            cmdFile.close();

            var cmd = {};
            try {
                cmd = eval('(' + cmdStr + ')');
            } catch(e) {
                cmd = { action: "parse_error" };
                log("Parse error: " + e.toString());
            }

            log("Executing: " + cmd.action);

            // 执行
            var result = executeCommand(cmd);

            // 写入结果
            var resultFile = new File(resultPath);
            resultFile.encoding = "UTF-8";
            resultFile.open("w");
            resultFile.writeln(JSON.stringify({
                status: result.error ? "error" : "success",
                result: result,
                timestamp: new Date().toUTCString()
            }));
            resultFile.close();

            log("Done: " + cmd.action);
        } catch(e) {
            log("Process file error: " + e.toString());
        }
    }

    // 轮询函数
    function pollCommands() {
        try {
            var cmdFiles = bridgeDir.getFiles("cmd_*.json");
            if (cmdFiles.length > 0) {
                log("Found " + cmdFiles.length + " command(s)");
            }
            for (var i = 0; i < cmdFiles.length; i++) {
                processCommandFile(cmdFiles[i]);
            }
        } catch(e) {
            log("Poll error: " + e.toString());
        }
    }

    // 使用 app.scheduleTask 或简单的时间检查来实现轮询
    // 在 PR 中，我们用 onIdle 事件或定期检查
    log("Setting up polling mechanism...");

    // 持续轮询循环
    var pollRunning = true;

    function continuousPoll() {
        while (pollRunning) {
            try {
                pollCommands();
            } catch(e) {
                log("Poll loop error: " + e.toString());
            }
            // 休眠500ms
            $.sleep(500);
        }
    }

    // 尝试使用 app.setInterval
    try {
        if (app.setInterval) {
            app.setInterval(pollCommands, 500);
            log("Using app.setInterval (500ms)");
        } else if ($.setInterval) {
            $.setInterval(pollCommands, 500);
            log("Using $.setInterval (500ms)");
        } else {
            // PR 没有 setInterval，使用后台持续轮询
            log("No setInterval found, starting continuous poll thread");

            // 先立即执行几次，处理积压的命令
            for (var t = 0; t < 3; t++) {
                pollCommands();
                $.sleep(100);
            }

            // 启动持续轮询（在 Startup 脚本中通常会同步执行）
            // 但为了不影响 PR 启动，我们使用 app.scheduleTask
            if (app.scheduleTask) {
                log("Using app.scheduleTask");
                // 持续调度，每500ms一次
                function scheduleNext() {
                    pollCommands();
                    app.scheduleTask(scheduleNext, 500, false);
                }
                app.scheduleTask(scheduleNext, 500, false);
            } else {
                // 最后的手段：直接循环（可能阻塞但能工作）
                log("Using blocking loop (fallback)");
                for (var i = 0; i < 100; i++) {
                    pollCommands();
                    $.sleep(500);
                }
            }
        }
    } catch(e) {
        log("Setup error: " + e.toString());
    }

    log("=== Bridge initialized ===");

})();
