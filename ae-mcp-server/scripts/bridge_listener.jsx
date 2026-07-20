// bridge_listener.jsx
// AE MCP Bridge 主监听脚本
// 运行后持续监听 command.json，执行对应 JSX 脚本并写入 result.json
//
// 使用方法：
//   1. 在 After Effects 中，文件 -> 脚本 -> 运行脚本文件
//   2. 选择此脚本
//   3. 脚本启动后会持续轮询 command.json
//
// 停止方法：
//   在 AE 中按 Esc 键，或重新启动脚本

#target aftereffects

(function() {
    var BRIDGE_DIR = Folder.myDocuments.fsName + "/ae-mcp-bridge";
    var TEMP_DIR = BRIDGE_DIR + "/temp";
    var COMMAND_FILE = BRIDGE_DIR + "/command.json";
    var RESULT_FILE = BRIDGE_DIR + "/result.json";
    var LOG_FILE = BRIDGE_DIR + "/bridge.log";

    var SCRIPTS_DIR = File($.fileName).parent.fsName;

    var POLL_INTERVAL = 200;
    var lastCommandTimestamp = 0;

    function log(message, level) {
        level = level || "INFO";
        var timestamp = new Date().toISOString();
        var line = "[" + timestamp + "] [" + level + "] " + message + "\n";
        try {
            var f = new File(LOG_FILE);
            f.encoding = "UTF-8";
            f.open("a");
            f.write(line);
            f.close();
        } catch (e) {}
    }

    function ensureDirs() {
        try {
            var bridgeFolder = new Folder(BRIDGE_DIR);
            if (!bridgeFolder.exists) {
                bridgeFolder.create();
            }
            var tempFolder = new Folder(TEMP_DIR);
            if (!tempFolder.exists) {
                tempFolder.create();
            }
        } catch (e) {}
    }

    function readCommand() {
        try {
            var f = new File(COMMAND_FILE);
            if (!f.exists) return null;
            f.encoding = "UTF-8";
            f.open("r");
            var content = f.read();
            f.close();
            if (!content || !content.trim()) return null;
            return JSON.parse(content);
        } catch (e) {
            return null;
        }
    }

    function writeResult(result) {
        try {
            var tmpFile = new File(RESULT_FILE + ".tmp");
            tmpFile.encoding = "UTF-8";
            tmpFile.open("w");
            tmpFile.write(JSON.stringify(result, null, 2));
            tmpFile.close();

            var resultFile = new File(RESULT_FILE);
            if (resultFile.exists) {
                resultFile.remove();
            }
            tmpFile.rename("result.json");
        } catch (e) {
            log("写入结果失败: " + e.toString(), "ERROR");
        }
    }

    function deleteCommand() {
        try {
            var f = new File(COMMAND_FILE);
            if (f.exists) {
                f.remove();
            }
        } catch (e) {}
    }

    function executeScript(command) {
        var scriptName = command.command;
        var args = command.args || {};

        log("执行脚本: " + scriptName);

        var scriptPath = SCRIPTS_DIR + "/" + scriptName + ".jsx";
        var scriptFile = new File(scriptPath);

        if (!scriptFile.exists) {
            log("脚本文件不存在: " + scriptPath, "ERROR");
            return {
                status: "error",
                errorCode: "SCRIPT_NOT_FOUND",
                message: "脚本文件不存在: " + scriptName
            };
        }

        try {
            var argsFile = new File(TEMP_DIR + "/args.json");
            argsFile.encoding = "UTF-8";
            argsFile.open("w");
            argsFile.write(JSON.stringify(args, null, 2));
            argsFile.close();
        } catch (e) {
            log("写入参数失败: " + e.toString(), "ERROR");
        }

        try {
            var result = app.doScript(scriptFile, ScriptLanguage.JAVASCRIPT, undefined, UndoMode.AUTO_UNDO);
            if (result && typeof result === "string") {
                try {
                    return JSON.parse(result);
                } catch (e) {
                    return {
                        status: "error",
                        errorCode: "PARSE_ERROR",
                        message: "结果解析失败: " + result
                    };
                }
            }
            return {
                status: "success",
                message: "脚本执行完成",
                rawResult: result
            };
        } catch (e) {
            log("脚本执行异常: " + e.toString(), "ERROR");
            return {
                status: "error",
                errorCode: "EXEC_ERROR",
                message: "脚本执行异常: " + e.toString()
            };
        }
    }

    function poll() {
        try {
            var command = readCommand();
            if (command && command.timestamp && command.timestamp !== lastCommandTimestamp) {
                lastCommandTimestamp = command.timestamp;
                log("收到命令: " + command.command);

                var result = executeScript(command);

                writeResult(result);
                deleteCommand();

                if (result.status === "success") {
                    log("命令执行成功: " + command.command);
                } else {
                    log("命令执行失败: " + command.command + " - " + (result.message || ""), "ERROR");
                }
            }
        } catch (e) {
            log("轮询异常: " + e.toString(), "ERROR");
        }
    }

    function startListener() {
        ensureDirs();
        log("========================================");
        log("AE MCP Bridge Listener 启动");
        log("桥接目录: " + BRIDGE_DIR);
        log("脚本目录: " + SCRIPTS_DIR);
        log("轮询间隔: " + POLL_INTERVAL + "ms");
        log("========================================");

        alert("AE MCP Bridge 监听已启动！\n\n桥接目录: " + BRIDGE_DIR + "\n\n按 '确定' 后监听将在后台运行。\n要停止监听，请在 AE 中按 Esc 键。");

        function loop() {
            poll();
            app.setTimeout(loop, POLL_INTERVAL);
        }

        loop();
    }

    startListener();
})();
