// ============================================================
// PR 全自动管线 - Startup 脚本主线程执行器 v2.0
// ============================================================
// 部署位置: D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup\
// 
// 工作原理:
//   PR 启动时自动执行此脚本（主线程上下文，拥有完整 UI/文件/编码权限）
//   读取 pr_fullauto_cmd.json → 执行多步操作 → 写入 pr_fullauto_result.json
//
// v2.0 改进:
//   - 添加项目加载等待（防止 Startup 脚本在项目就绪前执行）
//   - 导出使用 app.encoder.encodeSequence + H264 预设（主方法）
//   - 修复 insertClip 时间计算（使用实际素材时长）
//   - 转场使用标准 DOM addTransition（非 QE DOM）
//   - 增强错误恢复和日志
// ============================================================

(function() {
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge";
    var CMD_FILE = BRIDGE_DIR + "/pr_fullauto_cmd.json";
    var RES_FILE = BRIDGE_DIR + "/pr_fullauto_result.json";
    var LOG_FILE = BRIDGE_DIR + "/fullauto_startup_log.txt";
    
    // H.264 编码器预设路径
    var H264_PRESET = "D:/Pr25/Adobe Premiere Pro 2025/MediaIO/systempresets/3F3F3F3F_4D6F6F56/H264 Match Source - High bitrate.epr";
    
    // Ticks per second (PR 内部时间单位)
    var TICKS_PER_SEC = 254016000000;
    
    // JSON polyfill
    if (typeof JSON === "undefined") { JSON = {}; }
    if (typeof JSON.stringify !== "function") {
        JSON.stringify = function(v) {
            if (v === null || v === undefined) return "null";
            if (typeof v === "number" || typeof v === "boolean") return String(v);
            if (typeof v === "string") return '"' + v.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\n').replace(/\r/g,'\\r') + '"';
            if (v instanceof Array) { var a=[]; for(var i=0;i<v.length;i++) a.push(JSON.stringify(v[i])); return '['+a.join(',')+']'; }
            if (typeof v === "object") { var p=[]; for(var k in v) { if(v.hasOwnProperty(k)) p.push(JSON.stringify(k)+':'+JSON.stringify(v[k])); } return '{'+p.join(',')+'}'; }
            return "null";
        };
    }
    if (typeof JSON.parse !== "function") {
        JSON.parse = function(t) { return eval('(' + t + ')'); };
    }
    
    function log(msg) {
        try {
            var f = new File(LOG_FILE);
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln(new Date().toLocaleString() + " | " + msg);
            f.close();
        } catch(e) {}
    }
    
    function writeResult(obj) {
        try {
            var f = new File(RES_FILE);
            f.encoding = "UTF-8";
            f.open("w");
            f.write(JSON.stringify(obj));
            f.close();
        } catch(e) { log("writeResult error: " + e); }
    }
    
    function sleep(ms) {
        try { $.sleep(ms); } catch(e) {}
    }

    // 修复#3: ExtendScript 的 Array 可能缺 indexOf，用辅助函数替代
    function arrayContains(arr, val) {
        if (!arr || !arr.length) return false;
        for (var i = 0; i < arr.length; i++) {
            if (arr[i] === val) return true;
        }
        return false;
    }
    function arrayPushUnique(arr, val) {
        if (!arrayContains(arr, val)) arr.push(val);
        return arr;
    }

    // Check if command file exists
    var cmdFile = new File(CMD_FILE);
    if (!cmdFile.exists) {
        return; // No pending command, exit silently
    }
    
    log("=== FullAuto Executor v2.0 triggered ===");
    
    // Wait for project to be fully loaded (Startup scripts may run before project ready)
    // 增加到 60s，因为 PR 2025 可能弹出多个对话框阻塞项目加载
    var projectReady = false;
    for (var waitIdx = 0; waitIdx < 60; waitIdx++) {
        try {
            if (app.project && app.project.rootItem) {
                projectReady = true;
                break;
            }
        } catch(e) {}
        sleep(1000);
        log("Waiting for project... (" + (waitIdx+1) + "s)");
    }
    
    if (!projectReady) {
        // 尝试创建新项目（PR 2025 可能停在欢迎界面不自动加载项目）
        log("Project not ready, trying to create new project...");
        try {
            // 方法1: app.newProject
            var newProj = null;
            try {
                newProj = app.newProject("VinlandSagaEdit");
            } catch(npErr) {
                log("  newProject failed: " + npErr);
            }
            
            // 方法2: 通过 QE DOM
            if (!newProj) {
                try {
                    app.enableQE();
                    qe.project.newSequence("VinlandSagaEdit");
                } catch(qeErr) {
                    log("  QE newSequence failed: " + qeErr);
                }
            }
            
            // 等待项目就绪
            sleep(5000);
            for (var npWait = 0; npWait < 15; npWait++) {
                try {
                    if (app.project && app.project.rootItem) {
                        projectReady = true;
                        log("  New project ready after " + (npWait+1) + "s");
                        break;
                    }
                } catch(e) {}
                sleep(1000);
            }
        } catch(createErr) {
            log("  Create project error: " + createErr);
        }
    }
    
    if (!projectReady) {
        log("ERROR: Project not ready after 60s + create attempts");
        writeResult({success: false, error: "project_not_ready_60s"});
        return;
    }
    log("Project ready: " + app.project.name);
    
    // Read command
    var cmdContent = "";
    try {
        cmdFile.encoding = "UTF-8";
        cmdFile.open("r");
        cmdContent = cmdFile.read();
        cmdFile.close();
    } catch(e) {
        log("Failed to read cmd: " + e);
        writeResult({success: false, error: "cmd_read_failed: " + e});
        return;
    }
    
    // Delete command file immediately (prevent re-execution on next restart)
    cmdFile.remove();
    
    var cmd = null;
    try {
        cmd = JSON.parse(cmdContent);
    } catch(e) {
        log("JSON parse error: " + e);
        writeResult({success: false, error: "json_parse: " + e});
        return;
    }
    
    log("Command: " + cmd.action);
    
    // ============================================================
    // Execute multi-step pipeline
    // ============================================================
    var result = {
        action: cmd.action || "unknown",
        version: "2.0",
        started: new Date().toLocaleString(),
        steps: {}
    };
    
    try {
        var action = cmd.action || "";
        
        // ---- ACTION: full_pipeline ----
        if (action === "full_pipeline") {
            var files = cmd.files || [];
            var seqName = cmd.sequenceName || "FullAutoEdit";
            var exportPath = cmd.exportPath || "";
            var maxClips = cmd.maxClips || 5;
            
            // ===== Step 1: Import files =====
            if (files.length > 0) {
                log("Step 1: Importing " + files.length + " files...");
                var importOK = false;
                try {
                    importOK = app.project.importFiles(files);
                } catch(impErr) {
                    log("  importFiles exception: " + impErr);
                    // Fallback: import one by one
                    var imported = 0;
                    for (var fi = 0; fi < files.length; fi++) {
                        try {
                            app.project.importFiles([files[fi]]);
                            imported++;
                        } catch(e2) {
                            log("  Single import failed: " + files[fi] + " - " + e2);
                        }
                    }
                    importOK = imported > 0;
                    log("  Fallback single-import: " + imported + "/" + files.length);
                }
                result.steps.import = {ok: importOK, count: files.length};
                log("  importFiles result: " + importOK);
                sleep(2000); // Let PR process imported media
            } else {
                result.steps.import = {ok: true, count: 0, note: "no files"};
            }
            
            // ===== Step 2: Create sequence (多策略 fallback) =====
            log("Step 2: Creating sequence '" + seqName + "'...");
            var seq = null;
            var targetPreset = "";
            var seqCleared = false;

            // 修复#2: 多策略创建序列
            // 策略1: app.project.newSequence(name, presetPath) - 标准 DOM 方法
            var PRESET_PATHS = [
                "D:/Pr25/Adobe Premiere Pro 2025/Settings/SequencePresets/DSLR/DSLR 1080p29.97.sqpreset",
                "D:/Pr25/Adobe Premiere Pro 2025/Settings/SequencePresets/AVCHD/AVCHD 1080p30.sqpreset",
                "D:/Pr25/Adobe Premiere Pro 2025/Settings/SequencePresets/Digital SLR/DSLR 1080p29.97.sqpreset"
            ];

            for (var pp = 0; pp < PRESET_PATHS.length && !seq; pp++) {
                try {
                    var presetFile = new File(PRESET_PATHS[pp]);
                    if (presetFile.exists) {
                        seq = app.project.newSequence(seqName, PRESET_PATHS[pp]);
                        if (seq) {
                            targetPreset = "app.newSequence_preset_" + (pp+1);
                            log("  ✓ Created via preset: " + PRESET_PATHS[pp]);
                            sleep(1500);
                        }
                    }
                } catch(npErr) {
                    log("  newSequence preset#" + (pp+1) + " failed: " + npErr.toString().substring(0, 60));
                }
            }

            // 策略2: QE DOM newSequence (无预设参数，旧版兼容)
            if (!seq) {
                try {
                    app.enableQE();
                    qe.project.newSequence(seqName);
                    sleep(2000);
                    seq = app.project.activeSequence;
                    if (!seq && app.project.sequences.length > 0) {
                        seq = app.project.sequences[app.project.sequences.length - 1];
                        app.project.activeSequence = seq;
                    }
                    if (seq) targetPreset = "qe.newSequence";
                } catch(seqErr) {
                    log("  QE newSequence error: " + seqErr.toString().substring(0, 80));
                }
            }

            // 策略3: 使用现有序列，但清空时间轴 (修复 clipsOnTimeline=631 问题)
            if (!seq) {
                if (app.project.sequences.length > 0) {
                    seq = app.project.sequences[app.project.sequences.length - 1];
                    app.project.activeSequence = seq;
                    targetPreset = "existing_cleared";
                    log("  Fallback: using existing sequence '" + seq.name + "' + clearing timeline");
                }
            }

            // 清空时间轴（避免旧 clips 混入）
            if (seq) {
                try {
                    var clearVT = seq.videoTracks[0];
                    var oldClips = clearVT.clips;
                    var oldCount = oldClips ? oldClips.length : 0;
                    if (oldCount > 0) {
                        log("  Clearing " + oldCount + " old clips from timeline...");
                        for (var ci2 = oldCount - 1; ci2 >= 0; ci2--) {
                            try {
                                oldClips[ci2].remove();
                            } catch(rmErr) {
                                try { clearVT.removeItem(oldClips[ci2]); } catch(rmErr2) {}
                            }
                        }
                        seqCleared = true;
                        sleep(500);
                        var newCount = 0;
                        try { newCount = clearVT.clips.length; } catch(e) {}
                        log("  ✓ Cleared, remaining clips: " + newCount);
                    }
                } catch(clearErr) {
                    log("  Clear timeline error: " + clearErr.toString().substring(0, 60));
                }
            }
            result.steps.sequence = {
                created: !!seq,
                name: seq ? seq.name : "FAILED",
                method: targetPreset,
                timelineCleared: seqCleared
            };
            log("  Sequence: " + (seq ? seq.name : "FAILED") + " (" + targetPreset + ", cleared=" + seqCleared + ")");
            
            // ===== Step 3: Insert clips onto timeline =====
            if (seq) {
                log("Step 3: Inserting clips onto timeline...");
                var items = app.project.rootItem.children;
                var inserted = 0;
                var currentTime = 0;
                var vt = seq.videoTracks[0];

                // 修复#1: 精确匹配 cmd.files 中的文件名，避免匹配到项目原有素材
                // 从 cmd.files 提取 basename 集合 (e.g. "D:/path/clip_1_1.mp4" -> "clip_1_1.mp4")
                var cmdFileNames = {};
                var cmdFileOrder = [];
                for (var cf = 0; cf < files.length; cf++) {
                    var fpath = files[cf].replace(/\\/g, "/");
                    var slashIdx = fpath.lastIndexOf("/");
                    var fname = slashIdx >= 0 ? fpath.substring(slashIdx + 1) : fpath;
                    var fnameLower = fname.toLowerCase();
                    cmdFileNames[fnameLower] = true;
                    cmdFileOrder.push(fnameLower);
                }
                log("  Expecting " + cmdFileOrder.length + " files from cmd.files (precise match)");

                // 按命令文件顺序精确匹配项目面板中的素材
                var clipsToInsert = [];
                for (var oi = 0; oi < cmdFileOrder.length; oi++) {
                    var targetName = cmdFileOrder[oi];
                    var foundItem = null;
                    for (var ci = 0; ci < items.length; ci++) {
                        var item = items[ci];
                        if (item.type == 1 && item.name.toLowerCase() === targetName) {
                            foundItem = item;
                            break;
                        }
                    }
                    if (foundItem) {
                        clipsToInsert.push(foundItem);
                    } else {
                        log("  ⚠ Not found in project panel: " + targetName);
                    }
                    if (clipsToInsert.length >= maxClips) break;
                }
                log("  Found " + clipsToInsert.length + " clips to insert (precise match)");
                
                for (var ci = 0; ci < clipsToInsert.length; ci++) {
                    try {
                        vt.insertClip(clipsToInsert[ci], currentTime);
                        inserted++;
                        // Get actual media duration for proper spacing
                        var dur = 5 * TICKS_PER_SEC; // default 5s
                        try {
                            if (clipsToInsert[ci].getMediaDuration) {
                                dur = clipsToInsert[ci].getMediaDuration();
                            } else if (clipsToInsert[ci].duration) {
                                dur = clipsToInsert[ci].duration;
                            }
                        } catch(de) {}
                        // Limit each clip to max 10 seconds for compact edit
                        var maxDur = 10 * TICKS_PER_SEC;
                        if (dur > maxDur) dur = maxDur;
                        currentTime += dur;
                        log("  Inserted[" + ci + "]: " + clipsToInsert[ci].name + " (dur=" + (dur/TICKS_PER_SEC) + "s)");
                    } catch(insErr) {
                        log("  Insert FAILED[" + ci + "]: " + clipsToInsert[ci].name + " - " + insErr);
                        // Try overwriteClip as fallback
                        try {
                            vt.overwriteClip(clipsToInsert[ci], currentTime);
                            inserted++;
                            currentTime += 5 * TICKS_PER_SEC;
                            log("    overwriteClip fallback OK");
                        } catch(ovErr) {
                            log("    overwriteClip also failed: " + ovErr);
                        }
                    }
                }
                
                var timelineClipCount = 0;
                try { timelineClipCount = vt.clips.length; } catch(e) {}
                result.steps.arrange = {
                    inserted: inserted,
                    totalAvailable: clipsToInsert.length,
                    clipsOnTimeline: timelineClipCount,
                    totalDurationSec: currentTime / TICKS_PER_SEC
                };
                log("  Result: " + inserted + "/" + clipsToInsert.length + " inserted, timeline=" + timelineClipCount);
                
                // ===== Step 3.5: 添加 BGM 到音频轨道 =====
                if (cmd.bgmPath) {
                    log("Step 3.5: 添加 BGM 到音频轨道...");
                    try {
                        // 导入 BGM 文件
                        app.project.importFiles([cmd.bgmPath]);
                        sleep(1500);
                        
                        // 在项目面板中查找 BGM 素材
                        var bgmItem = null;
                        var items2 = app.project.rootItem.children;
                        for (var bi = 0; bi < items2.length; bi++) {
                            var item = items2[bi];
                            if (item.type == 1) {
                                var nm = item.name.toLowerCase();
                                if (nm.indexOf(".mp3") > -1 || nm.indexOf(".wav") > -1 || 
                                    nm.indexOf(".m4a") > -1 || nm.indexOf(".flac") > -1 || 
                                    nm.indexOf(".aac") > -1) {
                                    bgmItem = item;
                                    break;
                                }
                            }
                        }
                        
                        if (bgmItem && seq.audioTracks && seq.audioTracks.length > 0) {
                            var at = seq.audioTracks[0]; // A1 轨道
                            at.insertClip(bgmItem, 0); // BGM 放在时间线起点
                            var bgmDur = 0;
                            // 修复#5: 多方法获取 BGM 时长
                            try {
                                if (bgmItem.getMediaDuration) {
                                    var ticks = bgmItem.getMediaDuration();
                                    bgmDur = ticks / TICKS_PER_SEC;
                                }
                            } catch(e1) {}
                            // Fallback 1: 用 duration 属性
                            if (bgmDur <= 0) {
                                try {
                                    if (bgmItem.duration) bgmDur = bgmItem.duration / TICKS_PER_SEC;
                                } catch(e2) {}
                            }
                            // Fallback 2: 用文件大小估算 (mp3 ~128kbps = 16KB/s)
                            if (bgmDur <= 0) {
                                try {
                                    var bgmFile = new File(bgmItem.getMediaPath ? bgmItem.getMediaPath() : bgmItem.path);
                                    if (bgmFile.exists) {
                                        bgmDur = bgmFile.length / 16000; // ~128kbps = 16KB/s
                                        log("    BGM duration estimated from file size: " + bgmDur.toFixed(1) + "s");
                                    }
                                } catch(e3) {}
                            }
                            result.steps.bgm = {
                                ok: true, 
                                name: bgmItem.name, 
                                track: "A1",
                                durationSec: bgmDur
                            };
                            log("  ✓ BGM 已放置到 A1: " + bgmItem.name + " (时长=" + bgmDur + "s)");
                        } else {
                            result.steps.bgm = {ok: false, error: bgmItem ? "no_audio_track" : "bgm_not_found"};
                            log("  ✗ BGM 失败: " + (bgmItem ? "无音频轨道" : "项目中未找到 BGM"));
                        }
                    } catch(bgmErr) {
                        result.steps.bgm = {ok: false, error: bgmErr.toString()};
                        log("  BGM 异常: " + bgmErr);
                    }
                } else {
                    result.steps.bgm = {ok: true, skipped: true, note: "no bgmPath in command"};
                }
                
                // ===== Step 4: Apply transitions (Phase 3 增强版) =====
                log("Step 4: Applying transitions (Phase 3 Enhanced)...");
                var transitionsApplied = 0;
                var transitionMethodsTried = [];
                var transitionTypesTried = [];
                
                // 转场类型列表（按优先级排序）
                var TRANSITION_TYPES = [
                    "Cross Dissolve",
                    "Dip to Black",
                    "Dip to White",
                    "Film Dissolve",
                    "Additive Dissolve",
                    "Non-Additive Dissolve"
                ];
                
                try {
                    // ============================================================
                    // Approach A: 标准 DOM API 方法（优先，兼容性更好）
                    // ============================================================
                    log("  Approach A: Standard DOM API...");
                    transitionMethodsTried.push("standard_dom");
                    
                    var stdTrack = seq.videoTracks[0];
                    var stdClips = stdTrack.clips;
                    var stdClipCount = stdClips ? stdClips.length : 0;
                    log("    Standard DOM track clips: " + stdClipCount);
                    
                    if (stdClipCount >= 2) {
                        for (var sdi = 0; sdi < stdClipCount - 1 && sdi < 5; sdi++) {
                            var clipA = stdClips[sdi];
                            var clipB = stdClips[sdi + 1];
                            if (!clipA || !clipB) continue;
                            
                            // 计算转场应用时间点（clipA 的末端）
                            var transitionTime = -1;
                            try {
                                if (clipA.end !== undefined) transitionTime = clipA.end;
                                else if (clipA.outPoint !== undefined) transitionTime = clipA.outPoint;
                            } catch(ttErr) {}
                            
                            if (transitionTime < 0) {
                                try { transitionTime = clipA.start + clipA.duration; } catch(e) {}
                            }
                            
                            // 尝试多种转场类型
                            for (var tti = 0; tti < TRANSITION_TYPES.length && transitionsApplied <= sdi; tti++) {
                                var tName = TRANSITION_TYPES[tti];
                                arrayPushUnique(transitionTypesTried, tName);
                                try {
                                    // videoTrack.addTransition(name, time, alignment)
                                    // alignment: 1=Center on Cut, 2=Start at Cut, 3=End at Cut
                                    var added = false;
                                    try {
                                        added = stdTrack.addTransition(tName, transitionTime, 1);
                                    } catch(e1) {
                                        // 尝试不同参数形式：addTransition(name, startTime, duration, alignment)
                                        try {
                                            var durFrames = 12; // ~0.5s at 24fps
                                            added = stdTrack.addTransition(tName, transitionTime, durFrames, 1);
                                        } catch(e2) {}
                                    }
                                    
                                    if (added) {
                                        transitionsApplied++;
                                        log("    ✓ Standard DOM [" + tName + "] at clip " + sdi);
                                        break;
                                    }
                                } catch(trErr) {
                                    log("    ✗ StdDOM [" + tName + "] clip " + sdi + ": " + trErr.toString().substring(0, 80));
                                }
                            }
                        }
                    }
                    
                    // ============================================================
                    // Approach B: QE DOM API 方法（fallback）
                    // ============================================================
                    if (transitionsApplied === 0) {
                        log("  Approach B: QE DOM API...");
                        transitionMethodsTried.push("qe_dom");
                        app.enableQE();
                        var qseq = qe.project.getActiveSequence();
                        if (qseq) {
                            var qvt = qseq.getVideoTrackAt(0);
                            if (qvt) {
                                var numClips = qvt.numClips;
                                log("    QE track clips: " + numClips);
                                
                                for (var ti = 0; ti < numClips - 1 && ti < 5; ti++) {
                                    try {
                                        var qclip = qvt.getClipAt(ti);
                                        if (!qclip) continue;
                                        
                                        var qEndTime = -1;
                                        try { qEndTime = qclip.end; } catch(e) {}
                                        if (qEndTime < 0) {
                                            try { qEndTime = qclip.getOutPoint(); } catch(e) {}
                                        }
                                        if (qEndTime < 0) continue;
                                        
                                        // 尝试多种转场类型
                                        for (var tti2 = 0; tti2 < TRANSITION_TYPES.length; tti2++) {
                                            var tName2 = TRANSITION_TYPES[tti2];
                                            arrayPushUnique(transitionTypesTried, tName2);
                                            try {
                                                // QE DOM: addTransition(name, time, duration_in_frames)
                                                var tr = qvt.addTransition(tName2, qEndTime, 24); // 24帧 = 1秒
                                                if (tr) {
                                                    transitionsApplied++;
                                                    log("    ✓ QE DOM [" + tName2 + "] at clip " + ti);
                                                    break;
                                                }
                                            } catch(te) {
                                                log("    ✗ QEDOM [" + tName2 + "] clip " + ti + ": " + te.toString().substring(0, 60));
                                            }
                                        }
                                    } catch(outerErr) {
                                        log("    Clip " + ti + " outer error: " + outerErr.toString().substring(0, 60));
                                    }
                                }
                            } else {
                                log("    QE: cannot get video track 0");
                            }
                        } else {
                            log("    QE: cannot get active sequence");
                        }
                    }
                    
                    // ============================================================
                    // Approach C: 序列级方法 applyTransition / createTransition
                    // ============================================================
                    if (transitionsApplied === 0) {
                        log("  Approach C: Sequence-level API...");
                        transitionMethodsTried.push("sequence_level");
                        try {
                            // 尝试序列级方法
                            var methodsToTry = [
                                "createTransition", "applyTransition", "addTransition",
                                "applyDefaultTransition", "setTransition"
                            ];
                            for (var mi = 0; mi < methodsToTry.length && transitionsApplied < 2; mi++) {
                                var mname = methodsToTry[mi];
                                if (typeof seq[mname] === "function") {
                                    transitionMethodsTried.push("seq_" + mname);
                                    log("    Trying seq." + mname + "()...");
                                    try {
                                        // 尝试多种参数组合
                                        var tryCalls = [
                                            ["Cross Dissolve", 0],
                                            [0, "Cross Dissolve", 12],
                                            ["Cross Dissolve", 1, 0.5],
                                            [0, 1]
                                        ];
                                        for (var ci = 0; ci < tryCalls.length && transitionsApplied < 2; ci++) {
                                            try {
                                                var r = seq[mname].apply(seq, tryCalls[ci]);
                                                if (r) {
                                                    transitionsApplied++;
                                                    log("    ✓ seq." + mname + " success");
                                                }
                                            } catch(callErr) {}
                                        }
                                    } catch(mErr) {
                                        log("    seq." + mname + " error: " + mErr.toString().substring(0, 60));
                                    }
                                }
                            }
                        } catch(cErr) {
                            log("    Sequence-level error: " + cErr.toString().substring(0, 80));
                        }
                    }
                    
                    // ============================================================
                    // 验证：转场是否真的被应用
                    // ============================================================
                    log("  Verifying transitions on timeline...");
                    var verifiedCount = 0;
                    
                    // 验证方法1: 通过视频轨道的 transitions 属性
                    try {
                        if (stdTrack && stdTrack.transitions) {
                            verifiedCount = stdTrack.transitions.length;
                            log("    Track.transitions.length = " + verifiedCount);
                        }
                    } catch(vErr1) {
                        log("    Verify1 failed: " + vErr1.toString().substring(0, 50));
                    }
                    
                    // 验证方法2: 通过 QE DOM 查询
                    if (verifiedCount === 0) {
                        try {
                            app.enableQE();
                            var qseq2 = qe.project.getActiveSequence();
                            if (qseq2) {
                                var qvt2 = qseq2.getVideoTrackAt(0);
                                if (qvt2 && qvt2.numTransitions !== undefined) {
                                    verifiedCount = qvt2.numTransitions;
                                    log("    QE track.numTransitions = " + verifiedCount);
                                } else if (qvt2 && qvt2.getTransitionAt) {
                                    var vc = 0;
                                    while (vc < 20) {
                                        try {
                                            var tt = qvt2.getTransitionAt(vc);
                                            if (!tt) break;
                                            vc++;
                                        } catch(ee) { break; }
                                    }
                                    verifiedCount = vc;
                                    log("    QE getTransitionAt count = " + verifiedCount);
                                }
                            }
                        } catch(vErr2) {
                            log("    Verify2 failed: " + vErr2.toString().substring(0, 50));
                        }
                    }
                    
                    result.steps.transitionInfo = {
                        trackClips: stdClipCount,
                        methodsTried: transitionMethodsTried,
                        typesTried: transitionTypesTried,
                        verifiedTransitions: verifiedCount,
                        qeTrackClips: (function(){try{return qseq?qvt.numClips:0;}catch(e){return -1;}})()
                    };
                    
                } catch(transErr) {
                    log("  Transition system error: " + transErr);
                    if (transErr.line) log("    at line " + transErr.line);
                    result.steps.transitionSystemError = transErr.toString();
                }
                
                result.steps.transitions = {
                    applied: transitionsApplied,
                    verified: result.steps.transitionInfo ? result.steps.transitionInfo.verifiedTransitions : 0
                };
                log("  Transitions applied: " + transitionsApplied + " / verified: " + (result.steps.transitions.verified || 0));
                log("  Methods tried: " + transitionMethodsTried.join(", "));
                
                // ===== Step 5: Export (修复#4: 多方法尝试+文件生成验证) =====
                if (exportPath) {
                    log("Step 5: Exporting to " + exportPath);
                    var exportDone = false;
                    var exportMethods = [];
                    var fileFound = false;
                    var outFile = new File(exportPath);

                    // CRITICAL: Launch encoder first (initializes the encoding engine)
                    try {
                        var launchOK = app.encoder.launchEncoder();
                        log("  launchEncoder: " + launchOK);
                        sleep(3000);
                    } catch(le) {
                        log("  launchEncoder error: " + le);
                    }

                    app.project.activeSequence = seq;
                    sleep(500);

                    // Set In/Out points
                    try {
                        seq.setInPoint(0);
                        seq.setOutPoint(currentTime);
                        log("  In/Out set: 0 to " + (currentTime/TICKS_PER_SEC) + "s");
                    } catch(ioErr) {
                        log("  In/Out error: " + ioErr);
                    }

                    // 修复#4: 每个方法调用后立即验证文件生成，失败则尝试下一个方法
                    var EXPORT_WAIT_ROUNDS = 30; // 每方法等待 30*2=60s
                    function waitForExportFile() {
                        for (var ew = 0; ew < EXPORT_WAIT_ROUNDS; ew++) {
                            sleep(2000);
                            if (outFile.exists && outFile.length > 10240) {
                                log("  ✓ Export file ready: " + (outFile.length/1024/1024).toFixed(2) + " MB");
                                return true;
                            }
                            // 检查 encoder 状态
                            try {
                                var encStatus = app.encoder.getEncoderStatus ? app.encoder.getEncoderStatus() : null;
                                if (ew % 5 == 4) {
                                    log("  Waiting... (" + ((ew+1)*2) + "s) file=" + outFile.exists + " status=" + (encStatus ? JSON.stringify(encStatus).substring(0,80) : "n/a"));
                                }
                            } catch(esErr) {
                                if (ew % 5 == 4) log("  Waiting... (" + ((ew+1)*2) + "s) file=" + outFile.exists);
                            }
                        }
                        return false;
                    }

                    // Method 1: exportAsMediaDirect + ENCODE_IN_TO_OUT + H264 preset
                    if (!fileFound) {
                        try {
                            log("  Try 1: exportAsMediaDirect(IN_TO_OUT, H264 preset)");
                            seq.exportAsMediaDirect(exportPath, H264_PRESET, app.encoder.ENCODE_IN_TO_OUT);
                            exportMethods.push("exportAsMediaDirect_INOUT_H264");
                            log("  Try 1: called OK, waiting for file...");
                            fileFound = waitForExportFile();
                            if (!fileFound) log("  ✗ Try 1: file not generated after 60s");
                        } catch(e1) {
                            log("  Try 1 failed: " + e1);
                        }
                    }

                    // Method 2: exportAsMediaDirect + ENCODE_ENTIRE + H264 preset
                    if (!fileFound) {
                        try {
                            if (outFile.exists) outFile.remove(); // 清理失败的导出
                            sleep(500);
                            log("  Try 2: exportAsMediaDirect(ENTIRE, H264 preset)");
                            seq.exportAsMediaDirect(exportPath, H264_PRESET, app.encoder.ENCODE_ENTIRE);
                            exportMethods.push("exportAsMediaDirect_ENTIRE_H264");
                            log("  Try 2: called OK, waiting for file...");
                            fileFound = waitForExportFile();
                            if (!fileFound) log("  ✗ Try 2: file not generated after 60s");
                        } catch(e2) {
                            log("  Try 2 failed: " + e2);
                        }
                    }

                    // Method 3: encodeSequence + ENCODE_IN_TO_OUT + H264 preset (走 AME)
                    if (!fileFound) {
                        try {
                            if (outFile.exists) outFile.remove();
                            sleep(500);
                            log("  Try 3: encodeSequence(IN_TO_OUT, H264)");
                            var encResult = app.encoder.encodeSequence(seq, exportPath, H264_PRESET, app.encoder.ENCODE_IN_TO_OUT, 0);
                            exportMethods.push("encodeSequence_INOUT_H264");
                            log("  Try 3: called OK (result=" + encResult + "), waiting for file...");
                            fileFound = waitForExportFile();
                            if (!fileFound) log("  ✗ Try 3: file not generated after 60s");
                        } catch(e3) {
                            log("  Try 3 failed: " + e3);
                        }
                    }

                    // Method 4: encodeSequence + ENCODE_ENTIRE + empty preset
                    if (!fileFound) {
                        try {
                            if (outFile.exists) outFile.remove();
                            sleep(500);
                            log("  Try 4: encodeSequence(ENTIRE, empty)");
                            app.encoder.encodeSequence(seq, exportPath, "", app.encoder.ENCODE_ENTIRE, 0);
                            exportMethods.push("encodeSequence_ENTIRE_empty");
                            log("  Try 4: called OK, waiting for file...");
                            fileFound = waitForExportFile();
                            if (!fileFound) log("  ✗ Try 4: file not generated after 60s");
                        } catch(e4) {
                            log("  Try 4 failed: " + e4);
                        }
                    }

                    result.steps.export = {
                        methods: exportMethods,
                        path: exportPath,
                        called: exportMethods.length > 0,
                        fileExists: fileFound,
                        fileSize: fileFound ? outFile.length : 0,
                        fileSizeMB: fileFound ? (outFile.length/1024/1024).toFixed(2) : 0,
                        finalPath: exportPath,
                        success: fileFound
                    };
                    if (fileFound) {
                        log("  ✓✓ Export SUCCESS: " + outFile.length/1024/1024 + " MB");
                    } else {
                        log("  ✗✗ Export FAILED: all methods tried, no file generated");
                    }
                    exportDone = fileFound;
                }
                
                // ===== Step 6: Save project =====
                try {
                    app.project.save();
                    result.steps.save = {ok: true};
                    log("Step 6: Project saved");
                } catch(saveErr) {
                    result.steps.save = {ok: false, error: saveErr.toString()};
                    log("  Save failed: " + saveErr);
                }
            } else {
                result.steps.sequence = {created: false, error: "no sequence available"};
                log("FATAL: No sequence could be created or found");
            }
        }
        
        // ---- ACTION: export_only ----
        else if (action === "export_only") {
            var seq = app.project.activeSequence;
            if (!seq && app.project.sequences.length > 0) seq = app.project.sequences[0];
            
            if (seq && cmd.exportPath) {
                app.project.activeSequence = seq;
                seq.setInPoint(0);
                try { seq.setOutPoint(seq.end); } catch(e) {}
                
                try {
                    app.encoder.encodeSequence(seq, cmd.exportPath, H264_PRESET, app.encoder.ENCODE_IN_TO_OUT, 0);
                    result.steps.export = {method: "encodeSequence", called: true, path: cmd.exportPath};
                } catch(e) {
                    try {
                        seq.exportAsMediaDirect(cmd.exportPath, "", app.encoder.ENCODE_IN_TO_OUT);
                        result.steps.export = {method: "exportAsMediaDirect", called: true, path: cmd.exportPath};
                    } catch(e2) {
                        result.steps.export = {error: e.toString() + " | " + e2.toString()};
                    }
                }
            } else {
                result.steps.export = {error: "no sequence or no path"};
            }
            app.project.save();
        }
        
        // ---- ACTION: import_and_arrange ----
        else if (action === "import_and_arrange") {
            var files = cmd.files || [];
            if (files.length > 0) {
                var importOK = app.project.importFiles(files);
                result.steps.import = {ok: importOK, count: files.length};
                sleep(2000);
            }
            
            var seq = app.project.activeSequence;
            if (!seq && app.project.sequences.length > 0) seq = app.project.sequences[0];
            
            if (seq) {
                var vt = seq.videoTracks[0];
                var items = app.project.rootItem.children;
                var inserted = 0;
                var currentTime = 0;
                var maxClips = cmd.maxClips || 5;
                
                for (var i = 0; i < items.length && inserted < maxClips; i++) {
                    if (items[i].type == 1) {
                        var nm = items[i].name.toLowerCase();
                        if (nm.indexOf(".mp4") > -1 || nm.indexOf(".mov") > -1) {
                            try {
                                vt.insertClip(items[i], currentTime);
                                inserted++;
                                var dur = 5 * TICKS_PER_SEC;
                                try { if (items[i].getMediaDuration) dur = items[i].getMediaDuration(); } catch(de) {}
                                if (dur > 10 * TICKS_PER_SEC) dur = 10 * TICKS_PER_SEC;
                                currentTime += dur;
                            } catch(e) {
                                log("  insertClip error: " + e);
                            }
                        }
                    }
                }
                result.steps.arrange = {inserted: inserted, timelineClips: vt.clips.length};
            }
            app.project.save();
            result.steps.save = {ok: true};
        }
        
        // 修复#6: result.success 严格判断 — 必须导入+排列+保存都成功
        var arrangeStep = result.steps.arrange || {};
        var importStep = result.steps.import || {};
        var saveStep = result.steps.save || {};
        var seqStep = result.steps.sequence || {};
        result.success = (
            importStep.ok === true &&
            arrangeStep.inserted > 0 &&
            saveStep.ok === true &&
            !!seqStep.created
        );
        // 转场和导出为可选（不影响 success，但记录在 steps 中）
        if (!result.success) {
            log("  ⚠ Marked as FAILED: import=" + importStep.ok + " inserted=" + arrangeStep.inserted + " save=" + saveStep.ok + " seq=" + seqStep.created);
        }

    } catch(e) {
        result.success = false;
        result.error = e.toString();
        result.line = e.line;
        log("FATAL: " + e + " (line " + e.line + ")");
    }
    
    result.completed = new Date().toLocaleString();
    writeResult(result);
    log("=== Done: success=" + result.success + " ===");
    log("Steps: " + JSON.stringify(result.steps));
    
})();
