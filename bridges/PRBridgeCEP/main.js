/* PR Bridge - CEP Plugin Main Script v2.0
 *
 * 核心修复：将命令轮询从 ExtendScript 移到 Chromium 上下文
 * PR 2025 的 ExtendScript 无 app.scheduleTask / $.setInterval / app.setInterval
 * 但 CEP 面板的 main.js 运行在 Chromium 中，拥有原生 setInterval！
 *
 * 架构：
 *   main.js (Chromium) --setInterval 500ms--> cs.evalScript("PRBridge_poll()")
 *   host.jsx (ExtendScript) --> processCommandFile() --> pr_command.json / pr_result.json
 *
 * 这样实现了与 AE scheduleTask 等价的持久后台轮询。
 */

var cs = new CSInterface();
var bridgeRunning = false;
var statusPollInterval = null;
var commandPollInterval = null;  // 命令轮询定时器
var commandCount = 0;
var STATUS_POLL_MS = 3000;   // UI 状态刷新间隔
var COMMAND_POLL_MS = 500;   // 命令轮询间隔（与 AE Bridge 一致）

// ============================================================
// Logging
// ============================================================
function log(msg, cls) {
  var el = document.getElementById("log");
  var entry = document.createElement("div");
  entry.className = "log-entry " + (cls || "");
  var ts = new Date().toLocaleTimeString();
  entry.textContent = "[" + ts + "] " + msg;
  el.appendChild(entry);
  el.scrollTop = el.scrollHeight;
  while (el.children.length > 100) el.removeChild(el.firstChild);
}

// ============================================================
// Status
// ============================================================
function setStatus(state, text) {
  var dot = document.getElementById("statusDot");
  dot.className = "status-dot " + state;
  document.getElementById("statusText").textContent = text;
}

function setHandlersList(names) {
  var box = document.getElementById("handlersBox");
  if (!names || names.length === 0) {
    box.textContent = "No handlers loaded";
    return;
  }
  box.innerHTML = "";
  for (var i = 0; i < names.length; i++) {
    var chip = document.createElement("span");
    chip.className = "handler-chip";
    chip.textContent = names[i];
    box.appendChild(chip);
  }
}

// ============================================================
// 命令轮询（核心修复：在 Chromium 上下文中驱动）
// ============================================================
function startCommandPolling() {
  if (commandPollInterval) return;  // 已在运行
  log("Starting command polling (" + COMMAND_POLL_MS + "ms)...", "cmd");
  commandPollInterval = setInterval(pollCommand, COMMAND_POLL_MS);
}

function stopCommandPolling() {
  if (commandPollInterval) {
    clearInterval(commandPollInterval);
    commandPollInterval = null;
    log("Command polling stopped");
  }
}

function pollCommand() {
  // 调用 ExtendScript 侧的 PRBridge_poll()
  cs.evalScript("PRBridge_poll()", function (result) {
    if (result && result !== "undefined" && result !== "EvalScript error." && result !== "") {
      try {
        var parsed = JSON.parse(result);
        if (parsed && parsed.executed) {
          commandCount++;
          var el = document.getElementById("cmdCount");
          if (el) el.textContent = String(commandCount);
          log("Cmd #" + commandCount + ": " + (parsed.command || "?") + " -> " + (parsed.status || "?"), parsed.status === "success" ? "ok" : "err");
        }
      } catch(e) {
        // 非 JSON 结果，忽略
      }
    }
  });
}

// ============================================================
// Bridge Control
// ============================================================
function startBridge() {
  log("Initializing PR Bridge (loading core JSX)...", "cmd");
  cs.evalScript("PRBridge_init()", function (result) {
    var parsed;
    try { parsed = JSON.parse(result); }
    catch (e) {
      parsed = { core: { loaded: false, error: "Invalid JSON: " + result } };
    }

    if (parsed.core && parsed.core.loaded) {
      bridgeRunning = true;
      setStatus("connected", "Running — Chromium polling active");
      log("Bridge core loaded. Version: " + (parsed.bridgeVersion || "?"), "ok");

      if (parsed.sync) {
        if (parsed.sync.synced) {
          log("Business handler synced (" + parsed.sync.bytes + " bytes)", "ok");
        } else {
          log("Business handler sync skipped: " + (parsed.sync.reason || parsed.sync.error || ""), "err");
        }
      }

      if (parsed.handlers) {
        setHandlersList(parsed.handlers);
        log("Handlers: " + parsed.handlers.join(", "), "ok");
      }
    } else {
      setStatus("error", "Failed to load core");
      var err = (parsed.core && parsed.core.error) ? parsed.core.error : "unknown";
      log("Load failed: " + err, "err");
      return;
    }

    // 获取 PR 版本
    cs.evalScript("app.version", function (version) {
      if (version && version !== "undefined" && version !== "EvalScript error.") {
        document.getElementById("prVersion").textContent = version;
      }
    });

    document.getElementById("bridgeVersion").textContent = parsed.bridgeVersion || "-";
    document.getElementById("btnStart").disabled = true;
    document.getElementById("btnStop").disabled = false;

    // 启动命令轮询（核心！）
    startCommandPolling();

    // 启动 UI 状态轮询
    if (statusPollInterval) clearInterval(statusPollInterval);
    statusPollInterval = setInterval(refreshStatus, STATUS_POLL_MS);
  });
}

function stopBridge() {
  bridgeRunning = false;
  if (statusPollInterval) {
    clearInterval(statusPollInterval);
    statusPollInterval = null;
  }
  stopCommandPolling();

  setStatus("", "Stopped");
  log("Bridge stopped (command polling halted).");

  document.getElementById("btnStart").disabled = false;
  document.getElementById("btnStop").disabled = true;
}

function reloadHandlers() {
  log("Reloading handlers...", "cmd");
  cs.evalScript(
    'var __reloadCmd = {command: "reloadHandlers", timestamp: new Date().toUTCString(), processed: false};' +
    'var __cf = new File(PRBridge.commandFile);' +
    '__cf.encoding = "UTF-8"; __cf.open("w");' +
    '__cf.writeln(JSON.stringify(__reloadCmd)); __cf.close();' +
    '"reload dispatched"',
    function (res) {
      log("Reload dispatched: " + res, "ok");
      setTimeout(refreshStatus, 800);
    }
  );
}

function refreshStatus() {
  cs.evalScript("PRBridge_status()", function (result) {
    var parsed;
    try { parsed = JSON.parse(result); }
    catch (e) { return; }

    if (parsed.running) {
      setStatus("connected", "Running — Chromium polling active");
      if (parsed.handlers) setHandlersList(parsed.handlers);
      if (parsed.version) {
        document.getElementById("bridgeVersion").textContent = parsed.version;
      }
    } else {
      setStatus("error", "Bridge not running");
    }
  });
}

// ============================================================
// Init — 自动启动，无需用户点击
// ============================================================
(function init() {
  log("PRBridgeCEP v2.0 loaded (Chromium polling mode)");
  setStatus("waiting", "Initializing...");

  // 检测 PR 版本并自动启动
  cs.evalScript("app.version", function (version) {
    if (version && version !== "undefined" && version !== "EvalScript error.") {
      document.getElementById("prVersion").textContent = version;
      log("Premiere Pro: " + version, "ok");
      // 延迟 2 秒自动启动（等待 PR 完全初始化）
      setTimeout(function () {
        log("Auto-starting bridge...");
        startBridge();
      }, 2000);
    } else {
      log("Warning: Could not detect Premiere Pro version", "err");
      setStatus("error", "PR not responding");
    }
  });
})();
