// ============================================================
// AE Knowledge Vault - Premiere Pro Bridge (安全版本)
// 放置于: Scripts/Startup/ 目录
// PR 启动时自动加载，使用 app.scheduleTask 非阻塞轮询
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

    function log(msg) {
        try {
            var f = new File(bridgePath + "/bridge_log.txt");
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln("[" + new Date().toUTCString() + "] " + msg);
            f.close();
        } catch(e) {}
    }

    log("=== Bridge v3 starting ===");

    // 写入就绪标记
    try {
        var rf = new File(bridgePath + "/bridge_ready.txt");
        rf.encoding = "UTF-8";
        rf.open("w");
        rf.writeln("READY");
        rf.writeln("version: 3.0");
        rf.close();
    } catch(e) {}

    // 处理命令
    function processCommand(cmd) {
        var result = {};
        var action = cmd.action || "unknown";

        try {
            switch(action) {
                case "ping":
                    result.pong = true;
                    result.version = app.version;
                    result.timestamp = new Date().toUTCString();
                    break;

                case "getProjectInfo":
                    result.name = app.project ? app.project.name : "none";
                    result.numSequences = app.project ? app.project.sequences.length : 0;
                    break;

                case "createSequence":
                    var name = cmd.name || "Auto Seq";
                    try {
                        app.project.newSequence(name);
                        result.created = true;
                        result.name = name;
                    } catch(e) { result.error = e.toString(); }
                    break;

                case "executeScript":
                    if (cmd.script) {
                        try {
                            result.evalResult = String(eval(cmd.script));
                            result.executed = true;
                        } catch(e) { result.error = e.toString(); }
                    }
                    break;

                default:
                    result.error = "Unknown: " + action;
            }
        } catch(e) {
            result.error = e.toString();
        }

        return result;
    }

    // 轮询命令
    function poll() {
        try {
            var files = bridgeDir.getFiles("cmd_*.json");
            for (var i = 0; i < files.length; i++) {
                var cmdFile = files[i];
                var cmdName = cmdFile.name;
                var resultName = cmdName.replace("cmd_", "result_");
                var resultPath = bridgePath + "/" + resultName;

                // 删除旧结果
                var rf = new File(resultPath);
                if (rf.exists) try { rf.remove(); } catch(e) {}

                // 读取命令
                cmdFile.encoding = "UTF-8";
                cmdFile.open("r");
                var cmdStr = cmdFile.read();
                cmdFile.close();

                var cmd = {};
                try { cmd = eval('(' + cmdStr + ')'); } catch(e) { cmd = {action: "parse_error"}; }

                log("Execute: " + cmd.action);

                // 执行
                var result = processCommand(cmd);

                // 写入结果
                var wf = new File(resultPath);
                wf.encoding = "UTF-8";
                wf.open("w");
                wf.writeln(JSON.stringify({status: result.error ? "error" : "success", result: result, timestamp: new Date().toUTCString()}));
                wf.close();

                log("Done: " + cmd.action);
            }
        } catch(e) {
            log("Poll error: " + e);
        }
    }

    // 使用 app.scheduleTask 进行非阻塞轮询（关键！）
    if (typeof app.scheduleTask === 'function') {
        log("Using app.scheduleTask");

        // 立即执行一次
        poll();

        // 定义递归调度函数
        function schedulePoll() {
            poll();
            // 每500ms调度一次（非阻塞）
            app.scheduleTask(schedulePoll, 500, false);
        }

        // 启动调度
        app.scheduleTask(schedulePoll, 500, false);
    } else {
        log("No scheduleTask, polling manually");
        // 降级方案：执行几次后停止
        for (var j = 0; j < 10; j++) {
            poll();
            $.sleep(500);
        }
    }

    log("=== Bridge initialized ===");
})();