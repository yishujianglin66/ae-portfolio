/**
 * pr_mcp_bridge.jsx — Premiere Pro MCP Bridge 文件轮询监听器
 *
 * 协议：
 *   1. 监听 BASE_DIR/pr_command.json 文件变化
 *   2. 解析 JSON: {command, script, params, timestamp}
 *   3. 执行 ExtendScript 并写回 BASE_DIR/pr_result.json
 *   4. 支持心跳检测 (ping/pong)
 *
 * 使用方式：
 *   在 Premiere Pro 中运行：File > Scripts > Run Script File... > 选择本文件
 *   或通过 ExtendScript Toolkit 打开后运行
 *
 * 协议对齐：PremiereEngine._run_extendscript() 方法
 * 通信目录：与 settings.pr_bridge_dir 一致（默认 project_root/.pr-mcp-bridge/）
 */

// ============================================================
// 配置
// ============================================================

// 基础目录：与 settings.py 中 pr_bridge_dir 一致
// 默认使用项目根目录下的 .pr-mcp-bridge/
// 可通过修改 BASE_DIR 变量自定义
var BASE_DIR = Folder.appPackage.fsName + "/../.pr-mcp-bridge";
// 也尝试脚本所在目录的上级项目目录
var scriptFile = new File($.fileName);
var scriptDir = scriptFile.parent;
// 从脚本路径向上查找桥接目录（优先 .premiere-mcp-bridge，兼容 .pr-mcp-bridge）
var searchDir = scriptDir;
var bridgeDirNames = [".premiere-mcp-bridge", ".pr-mcp-bridge"];
for (var d = 0; d < bridgeDirNames.length; d++) {
    searchDir = scriptDir;
    for (var i = 0; i < 5; i++) {
        var candidate = Folder(searchDir.fsName + "/" + bridgeDirNames[d]);
        if (candidate.exists) {
            BASE_DIR = candidate.fsName;
            break;
        }
        searchDir = Folder(searchDir.parent.fsName);
    }
    if (BASE_DIR !== Folder.appPackage.fsName + "/../.pr-mcp-bridge") break;
}

var CMD_FILE = BASE_DIR + "/pr_command.json";
var RES_FILE = BASE_DIR + "/pr_result.json";
var POLL_INTERVAL_MS = 300; // 轮询间隔（毫秒）
var LISTENER_VERSION = "1.1.0";

// 日志文件
var LOG_DIR = BASE_DIR + "/logs";
var LOG_FILE = LOG_DIR + "/bridge_" + (new Date().getTime()) + ".log";

// ============================================================
// 工具函数
// ============================================================

function log(msg) {
    var timestamp = new Date().toISOString();
    var entry = "[" + timestamp + "] " + msg;
    $.writeln(entry);
    // 也写入日志文件
    try {
        var logFolder = Folder(LOG_DIR);
        if (!logFolder.exists) logFolder.create();
        var logFile = new File(LOG_FILE);
        logFile.open("a");
        logFile.writeln(entry);
        logFile.close();
    } catch (e) {
        // 日志文件写入失败不影响主流程
    }
}

function writeResult(status, result, message, line) {
    var res = {
        status: status,
        result: result,
        message: message,
        version: LISTENER_VERSION,
        timestamp: new Date().toISOString()
    };
    if (line !== undefined) {
        res.line = line;
    }
    try {
        var resFile = new File(RES_FILE);
        resFile.open("w");
        resFile.write(JSON.stringify(res));
        resFile.close();
    } catch (e) {
        log("ERROR: Failed to write result file: " + e.toString());
    }
}

function writeError(msg, line) {
    log("ERROR: " + msg + (line ? " (line: " + line + ")" : ""));
    writeResult("error", null, msg, line);
}

// ============================================================
// 命令执行
// ============================================================

function executeCommand(cmdData) {
    var command = cmdData.command || "";
    var script = cmdData.script || "";
    var params = cmdData.params || {};

    log("Executing command: " + command);

    try {
        switch (command) {
            case "ping":
                // 心跳检测
                writeResult("success", {
                    pong: true,
                    version: LISTENER_VERSION,
                    appName: app.appName,
                    appVersion: app.version,
                    project: app.project ? app.project.name : null,
                    sequence: app.project && app.project.activeSequence ? app.project.activeSequence.name : null
                });
                break;

            case "executeScript":
                // 执行 ExtendScript 代码
                if (!script) {
                    writeError("No script provided");
                    break;
                }
                try {
                    var result = eval(script);
                    // 确保结果是字符串（JSON.stringify 要求）
                    if (typeof result === "object" || Array.isArray(result)) {
                        writeResult("success", JSON.stringify(result));
                    } else if (result === undefined || result === null) {
                        writeResult("success", null);
                    } else {
                        writeResult("success", String(result));
                    }
                } catch (execError) {
                    writeError("Script execution error: " + execError.toString(), execError.line);
                }
                break;

            case "setProject":
                // 设置项目文件
                if (params.projectPath) {
                    try {
                        var projFile = new File(params.projectPath);
                        if (projFile.exists) {
                            app.openDocument(projFile);
                            writeResult("success", {project: params.projectPath});
                        } else {
                            writeError("Project file not found: " + params.projectPath);
                        }
                    } catch (e) {
                        writeError("Failed to open project: " + e.toString());
                    }
                } else {
                    writeError("No projectPath provided");
                }
                break;

            case "getInfo":
                // 获取引擎信息
                try {
                    var info = {
                        appName: app.appName,
                        appVersion: app.version,
                        project: app.project ? app.project.name : null,
                        projectPath: app.project && app.project.path ? app.project.path.fsName : null,
                        sequences: [],
                        binCount: 0
                    };
                    if (app.project) {
                        info.binCount = app.project.rootItem.children.numItems;
                        for (var i = 0; i < app.project.sequences.numSequences; i++) {
                            info.sequences.push({
                                name: app.project.sequences[i].name,
                                videoTracks: app.project.sequences[i].videoTracks.numTracks,
                                audioTracks: app.project.sequences[i].audioTracks.numTracks
                            });
                        }
                    }
                    writeResult("success", info);
                } catch (e) {
                    writeError("getInfo failed: " + e.toString());
                }
                break;

            case "status":
                // 监听器状态检测
                writeResult("success", {
                    status: "running",
                    version: LISTENER_VERSION,
                    baseDir: BASE_DIR,
                    cmdFile: CMD_FILE,
                    resFile: RES_FILE,
                    pollInterval: POLL_INTERVAL_MS,
                    uptime: Math.floor((new Date().getTime() - startTime) / 1000) + "s"
                });
                break;

            default:
                writeError("Unknown command: " + command);
                break;
        }
    } catch (e) {
        writeError("Unexpected error: " + e.toString());
    }
}

// ============================================================
// 主循环
// ============================================================

var startTime = new Date().getTime();
var lastCmdContent = "";
var loopCount = 0;

function mainLoop() {
    // 确保目录存在
    var baseFolder = Folder(BASE_DIR);
    if (!baseFolder.exists) {
        try {
            baseFolder.create();
            log("Created base directory: " + BASE_DIR);
        } catch (e) {
            log("CRITICAL: Cannot create base directory: " + BASE_DIR);
            return;
        }
    }

    // 确保日志目录存在
    var logFolder = Folder(LOG_DIR);
    if (!logFolder.exists) {
        try {
            logFolder.create();
        } catch (e) {
            // 忽略
        }
    }

    log("pr_mcp_bridge.jsx started — polling " + CMD_FILE);
    log("Version: " + LISTENER_VERSION + ", BaseDir: " + BASE_DIR);

    // 标记启动完成
    writeResult("success", {
        status: "listener_started",
        version: LISTENER_VERSION,
        baseDir: BASE_DIR,
        timestamp: new Date().toISOString()
    });

    // 主轮询循环
    while (true) {
        try {
            var cmdFile = new File(CMD_FILE);
            if (cmdFile.exists) {
                cmdFile.open("r");
                var content = cmdFile.read();
                cmdFile.close();

                if (content && content.length > 2 && content !== lastCmdContent) {
                    lastCmdContent = content;
                    try {
                        var cmdData = JSON.parse(content);
                        executeCommand(cmdData);
                        // 处理完成后删除命令文件（避免重复处理）
                        try {
                            cmdFile.remove();
                        } catch (e) {
                            // 删除失败可接受，下次会检测内容变化
                        }
                    } catch (parseError) {
                        writeError("JSON parse error: " + parseError.toString());
                    }
                }
            }
        } catch (e) {
            log("Poll error: " + e.toString());
        }

        loopCount++;
        $.sleep(POLL_INTERVAL_MS);
    }
}

// ============================================================
// 启动
// ============================================================

// 捕捉全局异常
try {
    // 显示启动对话框
    var startMsg = "pr_mcp_bridge.jsx v" + LISTENER_VERSION + "\n\n"
        + "Listening directory: " + BASE_DIR + "\n"
        + "Command file: pr_command.json\n"
        + "Result file: pr_result.json\n\n"
        + "Click OK to start listener, Cancel to exit.";
    if (confirm(startMsg, true, "Premiere MCP Bridge")) {
        mainLoop();
    } else {
        log("Listener startup cancelled by user");
    }
} catch (fatalError) {
    log("FATAL: " + fatalError.toString());
    writeResult("error", null, "Fatal: " + fatalError.toString());
}