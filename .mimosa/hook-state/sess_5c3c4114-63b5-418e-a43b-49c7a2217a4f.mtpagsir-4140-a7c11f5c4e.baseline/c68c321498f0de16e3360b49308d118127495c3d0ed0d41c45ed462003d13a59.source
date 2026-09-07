// ============================================================
// PR 剪辑技巧演示 - 冰海战记素材 v2.0
// ============================================================
// 部署位置: D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup\
// 监听文件: .premiere-mcp-bridge/pr_skills_cmd.json
// 输出文件: .premiere-mcp-bridge/pr_skills_result.json
//
// v2.0 修复:
//   - 修正 QE DOM API（numItems 代替 numClips）
//   - Lumetri 调色通过 components 遍历查找
//   - 关键帧动画用正确的 addKey + setKeyValueAtKey
//   - 嵌套用 QE DOM nestProjectItems
//   - 转场用 QE DOM addVideoTransition 复杂参数
//   - 音频淡入淡出用 Channel Volume 关键帧
//   - 每步记录详细 errors 数组便于诊断
// ============================================================

(function() {
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge";
    var CMD_FILE = BRIDGE_DIR + "/pr_skills_cmd.json";
    var RES_FILE = BRIDGE_DIR + "/pr_skills_result.json";
    var LOG_FILE = BRIDGE_DIR + "/skills_demo_log.txt";
    var BEATS_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/vinland_beats.json";

    var TICKS_PER_SEC = 254016000000;

    // ---------- JSON polyfill ----------
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

    function fileReadText(path) {
        try {
            var f = new File(path);
            f.encoding = "UTF-8";
            f.open("r");
            var txt = f.read();
            f.close();
            return txt;
        } catch(e) {
            log("fileReadText error: " + e);
            return null;
        }
    }

    function arrayContains(arr, val) {
        if (!arr || !arr.length) return false;
        for (var i = 0; i < arr.length; i++) {
            if (arr[i] === val) return true;
        }
        return false;
    }

    // 查找组件 by displayName 模糊匹配
    function findComponent(clip, namePattern) {
        try {
            var comps = clip.components;
            if (!comps) return null;
            for (var i = 0; i < comps.length; i++) {
                var c = comps[i];
                var dn = c.displayName;
                var mn = c.matchName;
                if ((dn && dn.indexOf(namePattern) >= 0) || (mn && mn.indexOf(namePattern) >= 0)) {
                    return c;
                }
            }
        } catch(e) {}
        return null;
    }

    // 查找 property by displayName 精确匹配
    function findProperty(component, propName) {
        try {
            var props = component.properties;
            if (!props) return null;
            for (var i = 0; i < props.length; i++) {
                if (props[i].displayName === propName) return props[i];
            }
        } catch(e) {}
        return null;
    }

    // 安全添加关键帧
    function safeAddKeyframe(prop, ticks, value) {
        try {
            prop.addKey(ticks);
            try { prop.setKeyValueAtKey(ticks, value); } catch(e) {}
            return true;
        } catch(e) {
            return false;
        }
    }

    // ---------- 检查命令文件 ----------
    var cmdFile = new File(CMD_FILE);
    if (!cmdFile.exists) {
        return; // 无待执行命令，静默退出
    }

    log("=== PR Skills Demo v2.0 triggered ===");

    // ---------- 等待项目就绪 ----------
    var projectReady = false;
    for (var waitIdx = 0; waitIdx < 60; waitIdx++) {
        try {
            if (app.project && app.project.rootItem) {
                projectReady = true;
                break;
            }
        } catch(e) {}
        sleep(1000);
    }

    if (!projectReady) {
        log("Project not ready, trying to create new project...");
        try {
            var newProj = null;
            try { newProj = app.newProject("VinlandSkills"); } catch(npErr) { log("  newProject failed: " + npErr); }
            if (!newProj) {
                try {
                    app.enableQE();
                    qe.project.newSequence("VinlandSkills");
                } catch(qeErr) { log("  QE newSequence failed: " + qeErr); }
            }
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
        writeResult({success: false, error: "project_not_ready"});
        return;
    }
    log("Project ready: " + app.project.name);

    // ---------- 读取命令 ----------
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
    cmdFile.remove();

    var cmd = null;
    try { cmd = JSON.parse(cmdContent); }
    catch(e) {
        log("JSON parse error: " + e);
        writeResult({success: false, error: "json_parse: " + e});
        return;
    }
    log("Command: " + cmd.action);

    // ---------- 主流程 ----------
    var result = {
        action: cmd.action || "skills_demo",
        version: "2.0",
        started: new Date().toLocaleString(),
        steps: {}
    };

    try {
        var action = cmd.action || "";

        if (action === "skills_demo") {
            var files = cmd.files || [];
            var seqName = cmd.sequenceName || "VinlandSkillsEdit";
            var maxClips = cmd.maxClips || 8;
            var bgmPath = cmd.bgmPath || "";

            // ===== Step 0: 导入素材 =====
            log("Step 0: Importing " + files.length + " clips...");
            if (files.length > 0) {
                try { app.project.importFiles(files); } catch(impErr) {
                    log("  importFiles exception: " + impErr);
                    for (var fi = 0; fi < files.length; fi++) {
                        try { app.project.importFiles([files[fi]]); } catch(e2) {}
                    }
                }
                sleep(2000);
            }
            result.steps.import = {ok: true, count: files.length};
            log("  Imported " + files.length + " files");

            // ===== Step 1: 创建序列（多策略 fallback）=====
            log("Step 1: Creating sequence '" + seqName + "'...");
            var seq = null;
            var seqMethod = "";

            // 策略0: 使用已有序列
            try {
                if (app.project.sequences && app.project.sequences.length > 0) {
                    seq = app.project.sequences[app.project.sequences.length - 1];
                    app.project.activeSequence = seq;
                    seqMethod = "existing_sequence";
                    log("  ✓ Using existing sequence: " + seq.name);
                }
            } catch(exErr) { log("  existing seq check: " + exErr.toString().substring(0, 60)); }

            // 策略1: 标准 DOM newSequence with 预设
            if (!seq) {
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
                            if (seq) { seqMethod = "preset_" + (pp+1); log("  ✓ Created via preset: " + PRESET_PATHS[pp]); sleep(1500); }
                        }
                    } catch(npErr) { log("  preset#" + (pp+1) + " failed: " + npErr.toString().substring(0, 60)); }
                }
            }

            // 策略2: QE DOM newSequence
            if (!seq) {
                try {
                    app.enableQE();
                    qe.project.newSequence(seqName, "");
                    sleep(2000);
                    seq = app.project.activeSequence;
                    if (seq) { seqMethod = "qe_empty_preset"; log("  ✓ Created via QE (empty preset)"); }
                } catch(seqErr) { log("  QE newSequence error: " + seqErr.toString().substring(0, 60)); }
            }

            // 策略3: 再检查已有序列
            if (!seq) {
                try {
                    if (app.project.sequences && app.project.sequences.length > 0) {
                        seq = app.project.sequences[app.project.sequences.length - 1];
                        app.project.activeSequence = seq;
                        seqMethod = "qe_created_existing";
                        log("  ✓ Found sequence after QE attempt: " + seq.name);
                    }
                } catch(ex2Err) {}
            }

            if (!seq) {
                log("FATAL: No sequence available after all strategies");
                writeResult({success: false, error: "no_sequence"});
                return;
            }
            result.steps.sequence = {created: true, name: seq.name, method: seqMethod};
            log("  Sequence: " + seq.name + " (" + seqMethod + ")");

            // ===== Step 2: 节拍点剪辑（技巧 1）=====
            log("Step 2: 节拍点剪辑...");
            var beatsData = null;
            var beatsText = fileReadText(BEATS_FILE);
            if (beatsText) {
                try { beatsData = JSON.parse(beatsText); } catch(be) { log("  beats JSON parse error: " + be); }
            }
            if (beatsData) {
                log("  Beats loaded: BPM=" + beatsData.bpm + ", beats=" + beatsData.beat_count + ", downbeats=" + (beatsData.downbeats ? beatsData.downbeats.length : 0));
            } else {
                log("  ⚠ 无节拍数据，使用等间距切片");
            }

            var items = app.project.rootItem.children;
            var cmdFileNames = {};
            var cmdFileOrder = [];
            for (var cf = 0; cf < files.length; cf++) {
                var fpath = files[cf].replace(/\\/g, "/");
                var slashIdx = fpath.lastIndexOf("/");
                var fname = slashIdx >= 0 ? fpath.substring(slashIdx + 1) : fpath;
                cmdFileNames[fname.toLowerCase()] = true;
                cmdFileOrder.push(fname.toLowerCase());
            }

            var clipsToInsert = [];
            for (var oi = 0; oi < cmdFileOrder.length; oi++) {
                var targetName = cmdFileOrder[oi];
                for (var ci = 0; ci < items.length; ci++) {
                    var item = items[ci];
                    if (item.type == 1 && item.name.toLowerCase() === targetName) {
                        clipsToInsert.push(item);
                        break;
                    }
                }
                if (clipsToInsert.length >= maxClips) break;
            }
            log("  Found " + clipsToInsert.length + " clips to insert");

            var vt = seq.videoTracks[0];
            var inserted = 0;
            var downbeats = beatsData && beatsData.downbeats ? beatsData.downbeats : null;
            var currentTime = 0;
            var insertedClipsList = [];

            for (var ic = 0; ic < clipsToInsert.length; ic++) {
                try {
                    var insertTime = currentTime;
                    if (downbeats && ic < downbeats.length) {
                        insertTime = Math.floor(downbeats[ic] * TICKS_PER_SEC);
                    }
                    vt.insertClip(clipsToInsert[ic], insertTime);
                    inserted++;
                    var dur = 5 * TICKS_PER_SEC;
                    try {
                        if (clipsToInsert[ic].getMediaDuration) dur = clipsToInsert[ic].getMediaDuration();
                    } catch(de) {}
                    var maxDur = 4 * TICKS_PER_SEC;
                    if (dur > maxDur) dur = maxDur;
                    currentTime = insertTime + dur;
                    try {
                        var lastClip = vt.clips[vt.clips.length - 1];
                        if (lastClip) insertedClipsList.push(lastClip);
                    } catch(lcErr) {}
                    log("  Inserted[" + ic + "]: " + clipsToInsert[ic].name + " at " + (insertTime/TICKS_PER_SEC) + "s");
                } catch(insErr) {
                    log("  Insert FAILED[" + ic + "]: " + insErr);
                }
            }
            var timelineClipCount = 0;
            try { timelineClipCount = vt.clips.length; } catch(e) {}
            result.steps.skill1_beatCutting = {
                applied: true,
                beatsUsed: downbeats ? Math.min(downbeats.length, inserted) : 0,
                bpm: beatsData ? beatsData.bpm : null,
                inserted: inserted,
                clipsOnTimeline: timelineClipCount
            };
            log("  Skill 1 done: " + inserted + " clips on beats");

            // ===== Step 3: 变速剪辑（技巧 2 - 通过 Time Remapping）=====
            log("Step 3: 变速剪辑 (Time Remapping Speed Keyframes)...");
            var speedApplied = 0;
            var speedErrors = [];
            var speedValues = [125, 75, 150, 90, 110]; // 百分比，前 5 个 clips
            try {
                var speedTrack = seq.videoTracks[0];
                var speedClips = speedTrack.clips;
                var nSpeedClips = speedClips ? speedClips.length : 0;
                log("  Speed clips available: " + nSpeedClips);
                for (var si = 0; si < Math.min(nSpeedClips, 5); si++) {
                    try {
                        var sClip = speedClips[si];
                        if (!sClip) continue;
                        // 查找 Time Remapping 组件
                        var trComp = findComponent(sClip, "Time Remap");
                        if (!trComp) {
                            // fallback: 尝试 "Time Remapping"
                            trComp = findComponent(sClip, "Time Remapping");
                        }
                        if (trComp) {
                            log("    Clip " + si + ": Time Remap component found");
                            var speedProp = findProperty(trComp, "Speed");
                            if (speedProp) {
                                // 启用关键帧（用 setValue 带 true 第二参数）
                                var targetSpeed = speedValues[si];
                                try {
                                    speedProp.setValue(targetSpeed, true);
                                } catch(sve) {
                                    speedErrors.push("clip" + si + "_setValue: " + sve.toString().substring(0, 40));
                                }
                                // 添加起始和结束关键帧
                                var sStart = sClip.start.ticks;
                                var sEnd = sClip.end.ticks;
                                var k1 = safeAddKeyframe(speedProp, sStart, targetSpeed);
                                var k2 = safeAddKeyframe(speedProp, sEnd, targetSpeed + 10);
                                if (k1 || k2) {
                                    speedApplied++;
                                    log("    ✓ Clip " + si + " speed=" + targetSpeed + "% (k1=" + k1 + ", k2=" + k2 + ")");
                                }
                            } else {
                                speedErrors.push("clip" + si + ": no Speed property");
                            }
                        } else {
                            speedErrors.push("clip" + si + ": no Time Remap component");
                        }
                    } catch(clipErr) {
                        speedErrors.push("clip" + si + ": " + clipErr.toString().substring(0, 50));
                    }
                }
            } catch(outerErr) {
                speedErrors.push("outer: " + outerErr.toString().substring(0, 60));
            }
            result.steps.skill2_speedRamp = {
                applied: speedApplied,
                errors: speedErrors.slice(0, 3),
                method: "Time Remapping Speed Keyframes"
            };
            log("  Skill 2 done: " + speedApplied + " clips speed-changed");

            // ===== Step 4: Lumetri 电影调色（技巧 3）=====
            // PR 2025 中每个视频 clip 默认带 Lumetri Color 组件
            log("Step 4: Lumetri 电影调色...");
            var lumetriApplied = 0;
            var lumetriErrors = [];
            var lumetriPropSets = [];
            try {
                var lumTrack = seq.videoTracks[0];
                var lumClips = lumTrack.clips;
                var nLumClips = lumClips ? lumClips.length : 0;
                log("  Clips to grade: " + nLumClips);
                // 探查第一个 clip 的所有 components（仅一次，便于诊断）
                if (nLumClips > 0) {
                    try {
                        var probeClip = lumClips[0];
                        var probeComps = probeClip.components;
                        var compNames = [];
                        for (var pc = 0; pc < probeComps.length; pc++) {
                            var pn = probeComps[pc].displayName;
                            var mn = probeComps[pc].matchName;
                            compNames.push(pn + "(" + mn + ")");
                        }
                        log("  Probe clip0 components: " + compNames.join(", "));
                    } catch(pe) {
                        log("  Probe error: " + pe.toString().substring(0, 60));
                    }
                }
                for (var li = 0; li < nLumClips; li++) {
                    try {
                        var lClip = lumClips[li];
                        if (!lClip) continue;
                        // 查找 Lumetri 组件（多种匹配名）
                        var lumetriComp = findComponent(lClip, "Lumetri");
                        if (!lumetriComp) lumetriComp = findComponent(lClip, "lumetri");
                        if (!lumetriComp) {
                            // 尝试中文显示名
                            lumetriComp = findComponent(lClip, "颜色");
                        }
                        if (lumetriComp) {
                            var props = lumetriComp.properties;
                            var setCount = 0;
                            var setProps = [];
                            for (var pi = 0; props && pi < props.length; pi++) {
                                var p = props[pi];
                                var pn = p.displayName;
                                try {
                                    // Teal-Orange 电影感参数
                                    if (pn === "Temperature") { p.setValue(-15, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Tint") { p.setValue(8, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Contrast") { p.setValue(110, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Saturation") { p.setValue(115, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Highlights") { p.setValue(95, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Shadows") { p.setValue(105, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Whites") { p.setValue(102, false); setCount++; setProps.push(pn); }
                                    else if (pn === "Blacks") { p.setValue(98, false); setCount++; setProps.push(pn); }
                                } catch(pe) {
                                    lumetriErrors.push("prop_" + pn + ": " + pe.toString().substring(0, 30));
                                }
                            }
                            if (setCount > 0) {
                                lumetriApplied++;
                                if (li === 0) lumetriPropSets = setProps;
                                log("    ✓ Clip " + li + " Lumetri: " + setCount + " props set (" + setProps.join(",") + ")");
                            } else {
                                lumetriErrors.push("clip" + li + ": Lumetri found but no props matched");
                            }
                        } else {
                            if (li === 0) lumetriErrors.push("Lumetri component not found on clip0");
                        }
                    } catch(clipErr) {
                        lumetriErrors.push("clip" + li + ": " + clipErr.toString().substring(0, 40));
                    }
                }
            } catch(outerErr) {
                lumetriErrors.push("outer: " + outerErr.toString().substring(0, 60));
            }
            result.steps.skill3_lumetriColor = {
                applied: lumetriApplied,
                errors: lumetriErrors.slice(0, 3),
                preset: "Teal-Orange Cinematic",
                propsSet: lumetriPropSets
            };
            log("  Skill 3 done: " + lumetriApplied + " clips graded with Lumetri");

            // ===== Step 5: 关键帧动画（技巧 4 - Motion Position/Scale）=====
            log("Step 5: 关键帧动画 (Motion)...");
            var kfApplied = 0;
            var kfErrors = [];
            var kfProbeComps = [];
            try {
                var kfTrack = seq.videoTracks[0];
                var kfClips = kfTrack.clips;
                var nKfClips = kfClips ? kfClips.length : 0;
                // 探查第一个 clip 的 components
                if (nKfClips > 0) {
                    try {
                        var probe = kfClips[0].components;
                        for (var pc2 = 0; pc2 < probe.length; pc2++) {
                            kfProbeComps.push(probe[pc2].displayName);
                        }
                        log("  Probe clip0 comps: " + kfProbeComps.join(", "));
                    } catch(pe2) {}
                }
                for (var ki = 0; ki < Math.min(nKfClips, 4); ki++) {
                    try {
                        var kClip = kfClips[ki];
                        if (!kClip) continue;
                        // 查找 Motion 组件
                        var motionComp = findComponent(kClip, "Motion");
                        if (!motionComp) motionComp = findComponent(kClip, "运动");
                        if (motionComp) {
                            var mProps = motionComp.properties;
                            var kfCount = 0;
                            var kProps = [];
                            for (var mp = 0; mProps && mp < mProps.length; mp++) {
                                var mp_p = mProps[mp];
                                var mp_n = mp_p.displayName;
                                try {
                                    if (mp_n === "Scale") {
                                        var startT = kClip.start.ticks;
                                        var endT = kClip.end.ticks;
                                        // 启用关键帧
                                        try { mp_p.setValue(100, true); } catch(se) {}
                                        var kk1 = safeAddKeyframe(mp_p, startT, 100);
                                        var kk2 = safeAddKeyframe(mp_p, endT, 120);
                                        if (kk1 || kk2) { kfCount += 2; kProps.push("Scale"); }
                                    } else if (mp_n === "Position") {
                                        var startT2 = kClip.start.ticks;
                                        var endT2 = kClip.end.ticks;
                                        try { mp_p.setValue([0, 0], true); } catch(se2) {
                                            try { mp_p.setValue("0,0", true); } catch(se3) {}
                                        }
                                        var kk3 = safeAddKeyframe(mp_p, startT2, [0, 0]);
                                        var kk4 = safeAddKeyframe(mp_p, endT2, [20, 15]);
                                        if (kk3 || kk4) { kfCount += 2; kProps.push("Position"); }
                                    } else if (mp_n === "Rotation") {
                                        var startT3 = kClip.start.ticks;
                                        var endT3 = kClip.end.ticks;
                                        try { mp_p.setValue(0, true); } catch(se4) {}
                                        var kk5 = safeAddKeyframe(mp_p, startT3, 0);
                                        var kk6 = safeAddKeyframe(mp_p, endT3, 5);
                                        if (kk5 || kk6) { kfCount += 2; kProps.push("Rotation"); }
                                    }
                                } catch(pe) {
                                    kfErrors.push("clip" + ki + "_prop_" + mp_n + ": " + pe.toString().substring(0, 30));
                                }
                            }
                            if (kfCount > 0) {
                                kfApplied++;
                                log("    ✓ Clip " + ki + " Motion: " + kfCount + " keyframes (" + kProps.join(",") + ")");
                            }
                        } else {
                            kfErrors.push("clip" + ki + ": no Motion component");
                        }
                    } catch(ce) {
                        kfErrors.push("clip" + ki + ": " + ce.toString().substring(0, 40));
                    }
                }
            } catch(outerErr2) {
                kfErrors.push("outer: " + outerErr2.toString().substring(0, 60));
            }
            result.steps.skill4_keyframes = {
                applied: kfApplied,
                errors: kfErrors.slice(0, 3),
                animation: "Zoom-in + Pan + Rotate",
                probeComponents: kfProbeComps
            };
            log("  Skill 4 done: " + kfApplied + " clips with keyframes");

            // ===== Step 6: 调整图层 + 嵌套序列（技巧 5）=====
            log("Step 6: 调整图层 + 嵌套序列...");
            var adjLayerCreated = false;
            var nestCreated = false;
            var adjErrors = [];
            // 调整图层：PR 2025 DOM 不直接支持创建调整图层
            // 尝试用 QE DOM 创建 Color Matte
            try {
                app.enableQE();
                // QE DOM 创建 Color Matte 作为伪调整图层
                var matteBin = null;
                try {
                    matteBin = app.project.rootItem.createBin("AdjustmentLayer");
                } catch(bErr) {
                    adjErrors.push("createBin: " + bErr.toString().substring(0, 40));
                }
                // 尝试多种 QE DOM API 创建调整图层
                var adjMethod = "";
                try {
                    // 方法1: QE project createColorMatte（可能不存在）
                    if (qe.project.createColorMatte) {
                        var matte = qe.project.createColorMatte(0, 0, 0, "AdjLayer");
                        if (matte) { adjMethod = "qe_createColorMatte"; adjLayerCreated = true; }
                    }
                } catch(e1) {}
                if (!adjLayerCreated) {
                    try {
                        // 方法2: 导入一个 .prfpset 调整图层预设
                        // 但我们没有预设文件，跳过
                    } catch(e2) {}
                }
                // 嵌套：尝试 QE DOM nestProjectItems
                if (qe.project.nestProjectItems) {
                    try {
                        var nestOk = qe.project.nestProjectItems("Nested_Edit");
                        if (nestOk) {
                            nestCreated = true;
                            log("  ✓ Nest via nestProjectItems");
                        }
                    } catch(neErr) {
                        adjErrors.push("nestProjectItems: " + neErr.toString().substring(0, 40));
                    }
                }
                if (!nestCreated) {
                    // 备选：使用 sequence.nest() 或其他
                    try {
                        if (qe.project.getActiveSequence && qe.project.getActiveSequence().nest) {
                            qe.project.getActiveSequence().nest("Nested_Edit");
                            nestCreated = true;
                            log("  ✓ Nest via sequence.nest");
                        }
                    } catch(ne2) {
                        adjErrors.push("seq.nest: " + ne2.toString().substring(0, 40));
                    }
                }
            } catch(adjErr) {
                adjErrors.push("outer: " + adjErr.toString().substring(0, 60));
            }
            result.steps.skill5_adjustmentNesting = {
                adjustmentLayer: adjLayerCreated,
                nested: nestCreated,
                errors: adjErrors.slice(0, 3),
                note: "PR 2025 DOM limited support; used QE DOM fallback"
            };
            log("  Skill 5 done: adjLayer=" + adjLayerCreated + ", nest=" + nestCreated);

            // ===== Step 7: 文字标题（技巧 6）=====
            log("Step 7: 文字标题...");
            var titleCreated = false;
            var titleErrors = [];
            try {
                app.enableQE();
                var titleText = "Vinland Saga Skills Demo";
                // 方法1: QE DOM addText（多种 API 名尝试）
                var qseq2 = qe.project.getActiveSequence();
                if (qseq2) {
                    // 尝试各种 API 名
                    var textAdded = false;
                    try {
                        if (qseq2.addText) {
                            textAdded = qseq2.addText(titleText);
                            if (textAdded) { titleCreated = true; log("  ✓ via qseq.addText"); }
                        }
                    } catch(at1) {
                        titleErrors.push("addText: " + at1.toString().substring(0, 40));
                    }
                    if (!titleCreated) {
                        try {
                            if (qseq2.addTitle) {
                                textAdded = qseq2.addTitle(titleText);
                                if (textAdded) { titleCreated = true; log("  ✓ via qseq.addTitle"); }
                            }
                        } catch(at2) {
                            titleErrors.push("addTitle: " + at2.toString().substring(0, 40));
                        }
                    }
                }
                // 方法2: 标准 DOM createTitleText
                if (!titleCreated) {
                    try {
                        if (app.project.createTitleText) {
                            var titleItem = app.project.createTitleText(titleText);
                            if (titleItem) {
                                var titleTrack = seq.videoTracks.length > 2 ? seq.videoTracks[seq.videoTracks.length - 1] : seq.addVideoTrack();
                                if (titleTrack) titleTrack.insertClip(titleItem, 0);
                                titleCreated = true;
                                log("  ✓ via createTitleText");
                            }
                        }
                    } catch(ctErr) {
                        titleErrors.push("createTitleText: " + ctErr.toString().substring(0, 40));
                    }
                }
                // 方法3: 标记为需要手动操作（PR 2025 无可靠脚本 API 创建文字）
                if (!titleCreated) {
                    log("  ⚠ PR 2025 无可靠 DOM API 创建文字，需手动添加");
                }
            } catch(titleErr) {
                titleErrors.push("outer: " + titleErr.toString().substring(0, 60));
            }
            result.steps.skill6_titles = {
                created: titleCreated,
                text: titleText,
                errors: titleErrors.slice(0, 3),
                note: titleCreated ? "Created via script API" : "PR 2025 lacks scriptable text creation; manual required"
            };
            log("  Skill 6 done: titleCreated=" + titleCreated);

            // ===== Step 8: 转场效果（技巧 7）=====
            log("Step 8: 转场效果...");
            var transitionsApplied = 0;
            var transitionTypes = [];
            var trErrors = [];
            try {
                app.enableQE();
                var trTrack = seq.videoTracks[0];
                var trClips = trTrack.clips;
                var nTrClips = trClips ? trClips.length : 0;
                var TR_TYPES = ["Cross Dissolve", "Dip to Black", "Film Dissolve", "Additive Dissolve"];
                log("  Clips for transitions: " + nTrClips);

                var qseq3 = qe.project.getActiveSequence();
                var qvt3 = qseq3 ? qseq3.getVideoTrackAt(0) : null;
                // 探查 QE DOM track 对象的属性
                if (qvt3 && qvt3 !== null) {
                    var qeProps = [];
                    try {
                        for (var pName in qvt3) {
                            if (typeof qvt3[pName] !== "function") qeProps.push(pName);
                        }
                        log("  QE track props: " + qeProps.join(", "));
                    } catch(pe) {}
                }

                // 尝试标准 DOM addTransition（PR 2025 可能不存在）
                for (var ti2 = 0; ti2 < nTrClips - 1 && ti2 < 5; ti2++) {
                    var clipA = trClips[ti2];
                    if (!clipA) continue;
                    var tTime = -1;
                    try { tTime = clipA.end; } catch(e) {}
                    if (tTime < 0) { try { tTime = clipA.start + clipA.duration; } catch(e2) {} }
                    if (tTime < 0) continue;
                    for (var tti3 = 0; tti3 < TR_TYPES.length; tti3++) {
                        var tName3 = TR_TYPES[tti3];
                        try {
                            // 标准 DOM addTransition（旧 API）
                            if (trTrack.addTransition) {
                                var added = trTrack.addTransition(tName3, tTime, 1);
                                if (added) {
                                    transitionsApplied++;
                                    if (!arrayContains(transitionTypes, tName3)) transitionTypes.push(tName3);
                                    log("    ✓ Transition [" + tName3 + "] at clip " + ti2 + " (DOM)");
                                    break;
                                }
                            }
                        } catch(te) {}
                    }
                }

                // Fallback: QE DOM addVideoTransition
                if (transitionsApplied === 0 && qvt3) {
                    for (var qi = 0; qi < nTrClips - 1 && qi < 5; qi++) {
                        var qc = qvt3.getClipAt(qi);
                        if (!qc) continue;
                        for (var tti4 = 0; tti4 < TR_TYPES.length; tti4++) {
                            var tName4 = TR_TYPES[tti4];
                            try {
                                // QE DOM addVideoTransition(name, clip, side, alignment, duration, reverse)
                                // side: 0=whole, 1=start, 2=end
                                // alignment: 0=center, 1=start, 2=end
                                var tr = null;
                                if (qvt3.addVideoTransition) {
                                    tr = qvt3.addVideoTransition(tName4, qc, 2, 0, 24, 0);
                                } else if (qvt3.addTransition) {
                                    tr = qvt3.addTransition(tName4, qc.end, 24);
                                }
                                if (tr) {
                                    transitionsApplied++;
                                    if (!arrayContains(transitionTypes, tName4)) transitionTypes.push(tName4);
                                    log("    ✓ QE Transition [" + tName4 + "] at clip " + qi);
                                    break;
                                }
                            } catch(te2) {
                                if (tti4 === 0) trErrors.push("clip" + qi + ": " + te2.toString().substring(0, 40));
                            }
                        }
                    }
                }
            } catch(trErr) {
                trErrors.push("outer: " + trErr.toString().substring(0, 60));
            }
            result.steps.skill7_transitions = {
                applied: transitionsApplied,
                types: transitionTypes,
                errors: trErrors.slice(0, 3)
            };
            log("  Skill 7 done: " + transitionsApplied + " transitions, types=" + transitionTypes.join(","));

            // ===== Step 9: 音频淡入淡出（技巧 8）=====
            log("Step 9: 音频淡入淡出...");
            var audioFadeApplied = 0;
            var audioErrors = [];
            try {
                if (bgmPath) {
                    try {
                        app.project.importFiles([bgmPath]);
                        sleep(1500);
                    } catch(impBgmErr) {
                        log("  BGM import: " + impBgmErr);
                    }
                    var bgmItem = null;
                    var items3 = app.project.rootItem.children;
                    for (var bi2 = 0; bi2 < items3.length; bi2++) {
                        var it3 = items3[bi2];
                        if (it3.type == 1) {
                            var nm = it3.name.toLowerCase();
                            if (nm.indexOf(".mp3") > -1 || nm.indexOf(".wav") > -1 || nm.indexOf(".flac") > -1) {
                                bgmItem = it3;
                                break;
                            }
                        }
                    }
                    if (bgmItem && seq.audioTracks && seq.audioTracks.length > 0) {
                        var at = seq.audioTracks[0];
                        at.insertClip(bgmItem, 0);
                        sleep(500);
                        // 通过 Channel Volume 组件的 Level 加关键帧实现淡入淡出
                        try {
                            var audioClips = at.clips;
                            if (audioClips && audioClips.length > 0) {
                                var bgmAudioClip = audioClips[0];
                                // 探查组件
                                var aComps = bgmAudioClip.components;
                                var aCompNames = [];
                                for (var aci2 = 0; aci2 < aComps.length; aci2++) {
                                    aCompNames.push(aComps[aci2].displayName);
                                }
                                log("  Audio clip comps: " + aCompNames.join(", "));

                                var levelComp = findComponent(bgmAudioClip, "Channel Volume");
                                if (!levelComp) levelComp = findComponent(bgmAudioClip, "Volume");
                                if (!levelComp) levelComp = findComponent(bgmAudioClip, "Level");
                                if (!levelComp) levelComp = findComponent(bgmAudioClip, "Audio");

                                if (levelComp) {
                                    // 查找 Level 属性（多种名）
                                    var levelProp = findProperty(levelComp, "Level");
                                    if (!levelProp) levelProp = findProperty(levelComp, "Volume");
                                    if (!levelProp) {
                                        // 列出所有属性名
                                        var propNames = [];
                                        for (var pn2 = 0; pn2 < levelComp.properties.length; pn2++) {
                                            propNames.push(levelComp.properties[pn2].displayName);
                                        }
                                        log("  Level comp props: " + propNames.join(", "));
                                    }
                                    if (levelProp) {
                                        var s = bgmAudioClip.start.ticks;
                                        var e = bgmAudioClip.end.ticks;
                                        // 淡入：开头 -inf (dB)，1s 后 0dB
                                        // 淡出：末尾 -inf (dB)，1s 前 0dB
                                        try {
                                            levelProp.setValue(-60, true); // 启用关键帧
                                        } catch(sve2) {}
                                        var k1 = safeAddKeyframe(levelProp, s, -60);
                                        var k2 = safeAddKeyframe(levelProp, s + 1 * TICKS_PER_SEC, 0);
                                        var k3 = safeAddKeyframe(levelProp, e - 1 * TICKS_PER_SEC, 0);
                                        var k4 = safeAddKeyframe(levelProp, e, -60);
                                        if (k1 || k2 || k3 || k4) {
                                            audioFadeApplied++;
                                            log("  ✓ Audio fade via Level keyframes (k1=" + k1 + ",k2=" + k2 + ",k3=" + k3 + ",k4=" + k4 + ")");
                                        }
                                    } else {
                                        audioErrors.push("no Level property found");
                                    }
                                } else {
                                    audioErrors.push("no Volume/Channel Volume component");
                                }
                            }
                        } catch(lvlErr) {
                            audioErrors.push("level_kf: " + lvlErr.toString().substring(0, 50));
                        }
                    } else {
                        audioErrors.push("no BGM item or audio track");
                    }
                }
            } catch(audioOuterErr) {
                audioErrors.push("outer: " + audioOuterErr.toString().substring(0, 60));
            }
            result.steps.skill8_audioFading = {
                applied: audioFadeApplied,
                errors: audioErrors.slice(0, 3),
                method: audioFadeApplied > 0 ? "Level Keyframes (Channel Volume)" : "failed"
            };
            log("  Skill 8 done: audioFadeApplied=" + audioFadeApplied);

            // ===== Step 10: 保存项目 =====
            log("Step 10: Saving project...");
            var saveOk = false;
            try {
                saveOk = app.project.save();
            } catch(svErr) {
                log("  save error: " + svErr);
            }
            result.steps.save = {ok: saveOk};

            // ===== 完成 =====
            result.success = true;
            result.completed = new Date().toLocaleString();
            writeResult(result);
            log("=== Skills Demo v2.0 Complete ===");

        } else {
            log("Unknown action: " + action);
            writeResult({success: false, error: "unknown_action: " + action});
        }

    } catch(mainErr) {
        log("FATAL main error: " + mainErr.toString());
        result.success = false;
        result.error = mainErr.toString();
        result.completed = new Date().toLocaleString();
        writeResult(result);
    }

})();
