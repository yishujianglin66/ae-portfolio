// AE Knowledge Vault - CEP Panel Client
(function() {
    "use strict";

    // CSInterface
    var cs = new CSInterface();
    var logMain = document.getElementById("log-main");
    var logInspect = document.getElementById("log-inspect");
    var logKnowledge = document.getElementById("log-knowledge");
    var statusDot = document.getElementById("status");
    var progressEl = document.getElementById("progress");
    var progressBar = document.getElementById("progress-bar");

    // Tab switching
    document.querySelectorAll(".tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            document.querySelectorAll(".tab").forEach(function(t) { t.classList.remove("active"); });
            document.querySelectorAll(".panel").forEach(function(p) { p.classList.remove("active"); });
            tab.classList.add("active");
            document.getElementById("panel-" + tab.dataset.panel).classList.add("active");
        });
    });

    // Logging
    function log(el, msg, type) {
        type = type || "info";
        var span = document.createElement("span");
        span.className = type;
        span.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg + "\n";
        el.appendChild(span);
        el.scrollTop = el.scrollHeight;
    }

    function showProgress() {
        progressEl.classList.add("active");
        progressBar.style.width = "50%";
    }
    function hideProgress() {
        progressBar.style.width = "100%";
        setTimeout(function() {
            progressEl.classList.remove("active");
            progressBar.style.width = "0%";
        }, 500);
    }

    // EvalScript wrapper
    function evalScript(script, callback) {
        cs.evalScript(script, function(result) {
            if (callback) callback(result);
        });
    }

    // Status check
    function checkStatus() {
        evalScript("app.project ? 'ok' : 'no_project'", function(result) {
            if (result === "ok") {
                statusDot.classList.add("connected");
                statusDot.classList.remove("error");
                statusDot.title = "已连接";
            } else {
                statusDot.classList.remove("connected");
                statusDot.title = "未连接";
            }
        });
    }
    checkStatus();
    setInterval(checkStatus, 5000);

    // === 主控面板 ===
    document.getElementById("btn-ping").addEventListener("click", function() {
        log(logMain, "正在检测 Bridge 连接...", "info");
        evalScript("JSON.stringify({status: 'ok', version: app.version, project: app.project.file ? app.project.file.name : '未保存'})", function(r) {
            try {
                var d = JSON.parse(r);
                log(logMain, "Bridge 连接正常", "success");
                log(logMain, "AE 版本: " + d.version, "info");
                log(logMain, "当前项目: " + d.project, "info");
            } catch(e) {
                log(logMain, "Bridge 响应异常: " + r, "error");
            }
        });
    });

    document.getElementById("btn-list").addEventListener("click", function() {
        log(logMain, "正在列出工程合成...", "info");
        showProgress();
        evalScript("(function(){var r=[];for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem){r.push({name:it.name,duration:it.duration.toFixed(1),layers:it.numLayers,fps:it.frameRate.toFixed(1)});}}return JSON.stringify(r);})()", function(r) {
            hideProgress();
            try {
                var comps = JSON.parse(r);
                log(logMain, "找到 " + comps.length + " 个合成:", "success");
                comps.forEach(function(c, i) {
                    log(logMain, "  " + (i+1) + ". " + c.name + " (" + c.duration + "s, " + c.layers + "层, fps=" + c.fps + ")", "info");
                });
            } catch(e) {
                log(logMain, "解析失败: " + r, "error");
            }
        });
    });

    document.getElementById("btn-start-listener").addEventListener("click", function() {
        log(logMain, "⚠️ CEP evalScript 无法可靠加载外部JSX文件（ExtendScript工作目录为AE安装目录）", "warn");
        log(logMain, "请手动启动 Listener：", "info");
        log(logMain, "1. AE菜单: 文件(F) > 脚本 > 运行脚本文件...", "info");
        log(logMain, "2. 选择: C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\ae_mcp_auto_listener.jsx", "info");
        log(logMain, "3. 再选择: .../start_mcp_listener.jsx (如有)", "info");
        log(logMain, "或运行 PowerShell: python ae_process_manager.py", "info");
    });

    document.getElementById("btn-screenshot").addEventListener("click", function() {
        log(logMain, "正在截取当前帧...", "info");
        evalScript("(function(){var comp=app.project.activeItem;if(!comp||!(comp instanceof CompItem))return'no_comp';var f=comp.frameRate;var t=comp.time;return JSON.stringify({comp:comp.name,time:t.toFixed(3),fps:f});})()", function(r) {
            try {
                var d = JSON.parse(r);
                log(logMain, "当前合成: " + d.comp + ", 时间: " + d.time + "s", "success");
            } catch(e) {
                log(logMain, r, "warn");
            }
        });
    });

    document.getElementById("btn-render").addEventListener("click", function() {
        log(logMain, "正在添加到渲染队列...", "info");
        evalScript("(function(){var comp=app.project.activeItem;if(!comp||!(comp instanceof CompItem))return'no_comp';app.project.renderQueue.items.add(comp);return'added:'+comp.name;})()", function(r) {
            if (r.indexOf("added:") === 0) {
                log(logMain, "已添加: " + r.substring(6), "success");
            } else {
                log(logMain, r, "warn");
            }
        });
    });

    // === 工程分析面板 ===
    document.getElementById("btn-manga-inspect").addEventListener("click", function() {
        log(logInspect, "开始深度提取工程结构...", "info");
        showProgress();
        evalScript("$.evalFile('C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/manga_inspect.jsx'); 'done';", function(r) {
            hideProgress();
            if (r.trim() === "done") {
                log(logInspect, "提取完成! 结果已保存到 tmp/manga_inspect.json", "success");
                // 读取并显示概览
                evalScript("(function(){var r=[];var tr=0;var fx=0;var layers=0;for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem){r.push(it.name);for(var j=1;j<=it.numLayers;j++){layers++;var l=it.layer(j);if(l.canSetTimeRemapEnabled)tr++;try{fx+=l.effect.numProperties;}catch(e){}}}}return JSON.stringify({comps:r.length,layers:layers,tr:tr,fx:fx});})()", function(r2) {
                    try {
                        var d = JSON.parse(r2);
                        document.getElementById("project-info").style.display = "block";
                        document.getElementById("info-name").textContent = app.project.file ? app.project.file.name : "未保存";
                        document.getElementById("info-comps").textContent = d.comps;
                        document.getElementById("info-layers").textContent = d.layers;
                        document.getElementById("info-tr").textContent = d.tr;
                        document.getElementById("info-fx").textContent = d.fx;
                    } catch(e) {}
                });
            } else {
                log(logInspect, "提取结果: " + r, "warn");
            }
        });
    });

    document.getElementById("btn-extract-expressions").addEventListener("click", function() {
        log(logInspect, "正在提取表达式...", "info");
        showProgress();
        evalScript("(function(){var r=[];for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem){for(var j=1;j<=it.numLayers;j++){var l=it.layer(j);var props=[l.position,l.scale,l.rotation,l.opacity,l.anchorPoint];for(var k=0;k<props.length;k++){var p=props[k];if(p.expression&&p.expression.length>0){r.push({comp:it.name,layer:l.name,prop:['Position','Scale','Rotation','Opacity','Anchor'][k],expr:p.expression.substring(0,200)});}}}}}return JSON.stringify(r);})()", function(r) {
            hideProgress();
            try {
                var exprs = JSON.parse(r);
                log(logInspect, "找到 " + exprs.length + " 个表达式:", "success");
                exprs.forEach(function(e) {
                    log(logInspect, "  [" + e.comp + "] " + e.layer + "." + e.prop + ": " + e.expr.substring(0, 80) + "...", "info");
                });
            } catch(e) {
                log(logInspect, "解析失败: " + r, "error");
            }
        });
    });

    document.getElementById("btn-extract-plugins").addEventListener("click", function() {
        log(logInspect, "正在提取插件清单...", "info");
        showProgress();
        evalScript("(function(){var r=[];for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem){for(var j=1;j<=it.numLayers;j++){var l=it.layer(j);try{for(var k=1;k<=l.effect.numProperties;k++){var fx=l.effect.property(k);if(fx&&fx.name){r.push({comp:it.name,layer:l.name,fx:fx.name,matchName:fx.matchName});}}}catch(e){}}}}return JSON.stringify(r);})()", function(r) {
            hideProgress();
            try {
                var fxs = JSON.parse(r);
                var counts = {};
                fxs.forEach(function(f) { counts[f.fx] = (counts[f.fx]||0) + 1; });
                log(logInspect, "找到 " + fxs.length + " 个插件实例 (" + Object.keys(counts).length + " 种):", "success");
                Object.keys(counts).sort(function(a,b){return counts[b]-counts[a];}).forEach(function(name) {
                    log(logInspect, "  " + name + " x" + counts[name], "info");
                });
            } catch(e) {
                log(logInspect, "解析失败: " + r, "error");
            }
        });
    });

    // === 知识库面板 ===
    document.getElementById("btn-save-knowledge").addEventListener("click", function() {
        log(logKnowledge, "正在保存工程知识...", "info");
        showProgress();
        // 先触发 manga_inspect，然后读取结果
        evalScript("$.evalFile('C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/manga_inspect.jsx'); 'done';", function(r) {
            hideProgress();
            if (r.trim() === "done") {
                log(logKnowledge, "工程数据已提取，正在生成知识文档...", "success");
                // 通知 Python 端处理
                log(logKnowledge, "请运行 Python 脚本将 JSON 转为知识库文档", "info");
            }
        });
    });

    document.getElementById("btn-view-knowledge").addEventListener("click", function() {
        log(logKnowledge, "正在读取知识库...", "info");
        evalScript("$.evalFile('C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/manga_inspect.jsx'); 'done';", function(r) {
            // 识别技法
            var techniques = [];
            evalScript("(function(){var hasTR=false;var hasPuppet=false;var hasAutoSway=false;var hasDeepGlow=false;var hasOptFlares=false;for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem){for(var j=1;j<=it.numLayers;j++){var l=it.layer(j);if(l.canSetTimeRemapEnabled&&l.timeRemap.numKeys>0)hasTR=true;try{for(var k=1;k<=l.effect.numProperties;k++){var fx=l.effect.property(k);if(fx.matchName.indexOf('FreePin3')>=0)hasPuppet=true;if(fx.matchName.indexOf('AutoSway')>=0)hasAutoSway=true;if(fx.matchName.indexOf('PEDG2')>=0)hasDeepGlow=true;if(fx.matchName.indexOf('OpticalFlares')>=0)hasOptFlares=true;}}catch(e){}}}}return JSON.stringify({tr:hasTR,puppet:hasPuppet,autoSway:hasAutoSway,deepGlow:hasDeepGlow,optFlares:hasOptFlares});})()", function(r2) {
                try {
                    var d = JSON.parse(r2);
                    document.getElementById("techniques-card").style.display = "block";
                    var list = document.getElementById("techniques-list");
                    list.innerHTML = "";
                    if (d.tr) { techniques.push("时间重映射(变速)"); }
                    if (d.puppet) { techniques.push("Puppet 网格变形"); }
                    if (d.autoSway) { techniques.push("AutoSway 自动飘动"); }
                    if (d.deepGlow) { techniques.push("Deep Glow 发光"); }
                    if (d.optFlares) { techniques.push("Optical Flares 光晕"); }
                    techniques.forEach(function(t) {
                        var row = document.createElement("div");
                        row.className = "row";
                        row.innerHTML = '<span class="value">✓ ' + t + '</span>';
                        list.appendChild(row);
                    });
                    log(logKnowledge, "识别到 " + techniques.length + " 种技法", "success");
                } catch(e) {
                    log(logKnowledge, "识别失败: " + r2, "error");
                }
            });
        });
    });

    document.getElementById("btn-export-report").addEventListener("click", function() {
        log(logKnowledge, "正在生成分析报告...", "info");
        log(logKnowledge, "报告将保存到: tmp/manga_inspect.json", "info");
        evalScript("$.evalFile('C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/manga_inspect.jsx'); 'done';", function(r) {
            if (r.trim() === "done") {
                log(logKnowledge, "数据已导出，请运行 Python 生成 Markdown 报告", "success");
            }
        });
    });

})();
