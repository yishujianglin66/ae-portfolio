// ============================================================
// PR Skills Demo v3.0 - 一步到位：导入+探查+执行
// 通过 MCP Bridge eval 触发
// ============================================================
(function() {
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge";
    var LOG_FILE = BRIDGE_DIR + "/skills_v3_log.txt";
    var RES_FILE = BRIDGE_DIR + "/pr_skills_result.json";
    var BEATS_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/vinland_beats.json";
    var TICKS_PER_SEC = 254016000000;

    // JSON polyfill
    if (typeof JSON === "undefined") { JSON = {}; }
    if (!JSON.stringify) { JSON.stringify = function(v) {
        if (v === null || v === undefined) return "null";
        if (typeof v === "number" || typeof v === "boolean") return String(v);
        if (typeof v === "string") return '"' + v.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\n') + '"';
        if (v instanceof Array) { var a=[]; for(var i=0;i<v.length;i++) a.push(JSON.stringify(v[i])); return '['+a.join(',')+']'; }
        if (typeof v === "object") { var p=[]; for(var k in v) { if(v.hasOwnProperty(k)) p.push('"'+k+'":'+JSON.stringify(v[k])); } return '{'+p.join(',')+'}'; }
        return "null";
    };}
    if (!JSON.parse) { JSON.parse = function(t) { return eval('(' + t + ')'); }; }

    var _logLines = [];
    function log(msg) {
        _logLines.push(new Date().toLocaleTimeString() + " | " + msg);
        try {
            var f = new File(LOG_FILE);
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln(new Date().toLocaleTimeString() + " | " + msg);
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
        } catch(e) {}
    }
    function fileRead(path) {
        try { var f = new File(path); f.encoding = "UTF-8"; f.open("r"); var t = f.read(); f.close(); return t; } catch(e) { return null; }
    }
    function sleep(ms) { try { $.sleep(ms); } catch(e) {} }

    log("=== Skills v3.0 START ===");

    var result = { version: "3.0", steps: {} };
    var files = [
        "C:/VinlandClips/clip_1_1.mp4", "C:/VinlandClips/clip_2_1.mp4",
        "C:/VinlandClips/clip_3_1.mp4", "C:/VinlandClips/clip_4_1.mp4",
        "C:/VinlandClips/clip_5_1.mp4", "C:/VinlandClips/clip_6_1.mp4",
        "C:/VinlandClips/clip_7_1.mp4", "C:/VinlandClips/clip_8_1.mp4"
    ];
    var bgmPath = "C:/VinlandBGM/bgm.mp3";

    // ===== STEP 1: Import =====
    log("Step1: Import " + files.length + " clips + BGM");
    try {
        app.project.importFiles(files.concat([bgmPath]));
        sleep(3000);
    } catch(e) {
        // fallback: one by one
        for (var fi = 0; fi < files.length; fi++) {
            try { app.project.importFiles([files[fi]]); } catch(e2) {}
        }
        try { app.project.importFiles([bgmPath]); } catch(e3) {}
        sleep(3000);
    }
    var itemCount = app.project.rootItem.children.length;
    log("  Imported items: " + itemCount);
    result.steps.import = { ok: itemCount > 0, count: itemCount };

    // ===== STEP 2: Create Sequence =====
    log("Step2: Create sequence");
    var seq = null;
    // Try existing
    if (app.project.sequences.length > 0) {
        seq = app.project.sequences[0];
        log("  Using existing: " + seq.name);
    }
    // Try QE create
    if (!seq) {
        try {
            app.enableQE();
            qe.project.newSequence("VinlandEdit", "");
            sleep(2000);
            seq = app.project.activeSequence;
            if (seq) log("  QE created: " + seq.name);
        } catch(e) { log("  QE seq err: " + e); }
    }
    // Re-check
    if (!seq && app.project.sequences.length > 0) {
        seq = app.project.sequences[0];
    }
    if (!seq) {
        log("FATAL: no sequence");
        result.success = false; result.error = "no_sequence";
        writeResult(result); return;
    }
    app.project.activeSequence = seq;
    result.steps.sequence = { name: seq.name };

    // ===== STEP 3: Insert clips on beats =====
    log("Step3: Beat cutting");
    var beatsData = null;
    var bt = fileRead(BEATS_FILE);
    if (bt) { try { beatsData = JSON.parse(bt); } catch(e) {} }
    var downbeats = beatsData ? beatsData.downbeats : null;

    // Find imported clips in project
    var items = app.project.rootItem.children;
    var clipsToInsert = [];
    for (var ci = 0; ci < files.length; ci++) {
        var fname = files[ci].split("/").pop().toLowerCase();
        for (var ii = 0; ii < items.length; ii++) {
            if (items[ii].type == 1 && items[ii].name.toLowerCase() === fname) {
                clipsToInsert.push(items[ii]);
                break;
            }
        }
    }
    log("  Clips found: " + clipsToInsert.length);

    var vt = seq.videoTracks[0];
    var inserted = 0;
    var curTime = 0;
    for (var ic = 0; ic < clipsToInsert.length; ic++) {
        try {
            var t = (downbeats && ic < downbeats.length) ? Math.floor(downbeats[ic] * TICKS_PER_SEC) : curTime;
            vt.insertClip(clipsToInsert[ic], t);
            inserted++;
            curTime = t + 3 * TICKS_PER_SEC;
        } catch(e) { log("  insert err[" + ic + "]: " + e); }
    }
    log("  Inserted: " + inserted);
    result.steps.skill1_beatCut = { inserted: inserted, bpm: beatsData ? beatsData.bpm : null };

    // ===== STEP 4: PROBE clip API =====
    log("Step4: Probing clip API...");
    var probe = { components: [], methods: [], qeMethods: [] };
    var clips = vt.clips;
    if (clips.length > 0) {
        var c0 = clips[0];
        // Standard DOM components
        var comps = c0.components;
        for (var pi = 0; pi < comps.length; pi++) {
            var comp = comps[pi];
            var propNames = [];
            try {
                for (var pj = 0; pj < comp.properties.length; pj++) {
                    propNames.push(comp.properties[pj].displayName);
                }
            } catch(e) {}
            probe.components.push({ dn: comp.displayName, mn: comp.matchName, props: propNames });
            log("  COMP: " + comp.displayName + " | " + comp.matchName + " | props=" + propNames.join(","));
        }
        // addComponent test
        try {
            var addResult = c0.addComponent("AE.ADBE Lumetri");
            log("  addComponent(AE.ADBE Lumetri) = " + addResult);
            probe.addComponent_lumetri = String(addResult);
        } catch(e) { log("  addComponent err: " + e); probe.addComponent_lumetri = "ERR:" + e; }
        // speed methods
        probe.getSpeed = typeof c0.getSpeed;
        probe.setSpeed = typeof c0.setSpeed;
        try { probe.speedVal = c0.getSpeed(); } catch(e) { probe.speedVal = "ERR"; }
        log("  speed: get=" + probe.getSpeed + " set=" + probe.setSpeed + " val=" + probe.speedVal);

        // QE DOM probe
        try {
            app.enableQE();
            var qseq = qe.project.getActiveSequence();
            if (qseq) {
                var qvt = qseq.getVideoTrackAt(0);
                if (qvt && qvt.numItems > 0) {
                    var qc = qvt.getClipAt(0);
                    if (qc) {
                        for (var qm in qc) {
                            if (typeof qc[qm] === "function") probe.qeMethods.push(qm);
                        }
                        log("  QE clip methods: " + probe.qeMethods.join(","));
                        // Try QE speed
                        try { probe.qeSpeed = qc.speed; log("  QE clip.speed = " + qc.speed); } catch(e) {}
                    }
                    // QE track methods
                    var qtMethods = [];
                    for (var tm in qvt) { if (typeof qvt[tm] === "function") qtMethods.push(tm); }
                    probe.qeTrackMethods = qtMethods;
                    log("  QE track methods: " + qtMethods.join(","));
                }
            }
        } catch(qe) { log("  QE probe err: " + qe); }
    }
    result.steps.probe = probe;

    // ===== STEP 5: Speed Ramp (technique 2) =====
    log("Step5: Speed Ramp");
    var speedOk = 0;
    var speedErrors = [];
    var speedVals = [125, 75, 150, 90, 110];
    for (var si = 0; si < Math.min(clips.length, 5); si++) {
        try {
            var sc = clips[si];
            // Method 1: Time Remapping component
            var trComp = null;
            for (var tc = 0; tc < sc.components.length; tc++) {
                var cmn = sc.components[tc].matchName;
                var cdn = sc.components[tc].displayName;
                if (cmn.indexOf("Time") >= 0 || cdn.indexOf("Time") >= 0 || cdn.indexOf("时间") >= 0) {
                    trComp = sc.components[tc]; break;
                }
            }
            if (trComp) {
                var sp = null;
                for (var spI = 0; spI < trComp.properties.length; spI++) {
                    if (trComp.properties[spI].displayName.indexOf("Speed") >= 0 || trComp.properties[spI].displayName.indexOf("速度") >= 0) {
                        sp = trComp.properties[spI]; break;
                    }
                }
                if (sp) { sp.setValue(speedVals[si], true); speedOk++; log("  clip" + si + " speed via TimeRemap"); continue; }
            }
            // Method 2: QE DOM setSpeed
            try {
                app.enableQE();
                var qs2 = qe.project.getActiveSequence();
                var qvt2 = qs2.getVideoTrackAt(0);
                var qc2 = qvt2.getClipAt(si);
                if (qc2 && qc2.setSpeed) { qc2.setSpeed(speedVals[si]); speedOk++; log("  clip" + si + " speed via QE"); continue; }
            } catch(qse) {}
            speedErrors.push("clip" + si + ": no method");
        } catch(e) { speedErrors.push("clip" + si + ": " + String(e).substring(0,40)); }
    }
    result.steps.skill2_speed = { applied: speedOk, errors: speedErrors };
    log("  Speed done: " + speedOk);

    // ===== STEP 6: Lumetri Color (technique 3) =====
    log("Step6: Lumetri Color");
    var lumOk = 0;
    var lumErrors = [];
    for (var li = 0; li < clips.length; li++) {
        try {
            var lc = clips[li];
            var lumComp = null;
            for (var lci = 0; lci < lc.components.length; lci++) {
                var lmn = lc.components[lci].matchName;
                var ldn = lc.components[lci].displayName;
                if (lmn.indexOf("Lumetri") >= 0 || ldn.indexOf("Lumetri") >= 0 || ldn.indexOf("颜色") >= 0) {
                    lumComp = lc.components[lci]; break;
                }
            }
            if (!lumComp && li === 0) {
                // Try addComponent on first clip
                try { lc.addComponent("AE.ADBE Lumetri"); sleep(500); } catch(ace) {}
                // Re-scan
                for (var lci2 = 0; lci2 < lc.components.length; lci2++) {
                    var lmn2 = lc.components[lci2].matchName;
                    if (lmn2.indexOf("Lumetri") >= 0 || lmn2.indexOf("Color") >= 0) {
                        lumComp = lc.components[lci2]; break;
                    }
                }
            }
            if (lumComp) {
                var setN = 0;
                for (var lp = 0; lp < lumComp.properties.length; lp++) {
                    var lprop = lumComp.properties[lp];
                    var lpn = lprop.displayName;
                    try {
                        if (lpn === "Temperature" || lpn === "色温") { lprop.setValue(-15, false); setN++; }
                        else if (lpn === "Contrast" || lpn === "对比度") { lprop.setValue(110, false); setN++; }
                        else if (lpn === "Saturation" || lpn === "饱和度") { lprop.setValue(120, false); setN++; }
                        else if (lpn === "Tint" || lpn === "色调") { lprop.setValue(8, false); setN++; }
                    } catch(pe) {}
                }
                if (setN > 0) { lumOk++; if (li === 0) log("  Lumetri props set: " + setN); }
            } else {
                if (li === 0) lumErrors.push("Lumetri not found after addComponent");
            }
        } catch(e) { lumErrors.push("clip" + li + ": " + String(e).substring(0,30)); }
    }
    result.steps.skill3_lumetri = { applied: lumOk, errors: lumErrors };
    log("  Lumetri done: " + lumOk);

    // ===== STEP 7: Keyframe Animation (technique 4) =====
    log("Step7: Keyframes");
    var kfOk = 0;
    var kfErrors = [];
    for (var ki = 0; ki < Math.min(clips.length, 4); ki++) {
        try {
            var kc = clips[ki];
            var motionComp = null;
            for (var mci = 0; mci < kc.components.length; mci++) {
                var mmn = kc.components[mci].matchName;
                var mdn = kc.components[mci].displayName;
                if (mmn.indexOf("Motion") >= 0 || mdn.indexOf("Motion") >= 0 || mdn.indexOf("运动") >= 0) {
                    motionComp = kc.components[mci]; break;
                }
            }
            if (motionComp) {
                var kStart = kc.start.ticks;
                var kEnd = kc.end.ticks;
                var kfSet = 0;
                for (var mpi = 0; mpi < motionComp.properties.length; mpi++) {
                    var mp = motionComp.properties[mpi];
                    var mpn = mp.displayName;
                    try {
                        if (mpn === "Scale" || mpn === "缩放") {
                            mp.setValue(100, true);
                            mp.addKey(kStart); try { mp.setKeyValueAtKey(kStart, 100); } catch(e) {}
                            mp.addKey(kEnd); try { mp.setKeyValueAtKey(kEnd, 120); } catch(e) {}
                            kfSet++;
                        } else if (mpn === "Position" || mpn === "位置") {
                            mp.setValue([0,0], true);
                            mp.addKey(kStart); mp.addKey(kEnd);
                            kfSet++;
                        } else if (mpn === "Rotation" || mpn === "旋转") {
                            mp.setValue(0, true);
                            mp.addKey(kStart); try { mp.setKeyValueAtKey(kStart, 0); } catch(e) {}
                            mp.addKey(kEnd); try { mp.setKeyValueAtKey(kEnd, 3); } catch(e) {}
                            kfSet++;
                        }
                    } catch(pe) { if (ki === 0) kfErrors.push(mpn + ": " + String(pe).substring(0,25)); }
                }
                if (kfSet > 0) { kfOk++; if (ki === 0) log("  Motion kf set: " + kfSet + " props"); }
                else if (ki === 0) {
                    // Log all prop names for debug
                    var allP = [];
                    for (var dbg = 0; dbg < motionComp.properties.length; dbg++) allP.push(motionComp.properties[dbg].displayName);
                    log("  Motion props available: " + allP.join(","));
                    kfErrors.push("no Scale/Position/Rotation matched, props=" + allP.join(","));
                }
            } else { kfErrors.push("clip" + ki + ": no Motion comp"); }
        } catch(e) { kfErrors.push("clip" + ki + ": " + String(e).substring(0,30)); }
    }
    result.steps.skill4_keyframes = { applied: kfOk, errors: kfErrors };
    log("  Keyframes done: " + kfOk);

    // ===== STEP 8: Transitions (technique 7) =====
    log("Step8: Transitions");
    var trOk = 0;
    var trErrors = [];
    var TR_NAMES = ["Cross Dissolve", "Dip to Black", "Film Dissolve"];
    try {
        app.enableQE();
        var qs3 = qe.project.getActiveSequence();
        var qvt3 = qs3.getVideoTrackAt(0);
        if (qvt3) {
            for (var ti = 0; ti < Math.min(qvt3.numItems - 1, 4); ti++) {
                var tc2 = qvt3.getClipAt(ti);
                if (!tc2) continue;
                for (var tni = 0; tni < TR_NAMES.length; tni++) {
                    try {
                        // addVideoTransition(name, clip, side, alignment, duration, reverse)
                        var tr = qvt3.addVideoTransition(TR_NAMES[tni], tc2, 2, 0, 24, 0);
                        if (tr) { trOk++; log("  Transition: " + TR_NAMES[tni] + " at clip" + ti); break; }
                    } catch(te) {
                        if (tni === 0) trErrors.push("clip" + ti + ": " + String(te).substring(0,40));
                    }
                }
            }
            // Fallback: standard DOM
            if (trOk === 0) {
                var stdTrack = seq.videoTracks[0];
                if (stdTrack.addTransition) {
                    for (var sti = 0; sti < Math.min(stdTrack.clips.length - 1, 4); sti++) {
                        try {
                            var stClip = stdTrack.clips[sti];
                            var added = stdTrack.addTransition(TR_NAMES[0], stClip.end, 1);
                            if (added) { trOk++; log("  StdDOM transition at clip" + sti); }
                        } catch(ste) { if (sti === 0) trErrors.push("std: " + String(ste).substring(0,40)); }
                    }
                } else { trErrors.push("no addTransition on track"); }
            }
        }
    } catch(e) { trErrors.push("outer: " + String(e).substring(0,40)); }
    result.steps.skill7_transitions = { applied: trOk, errors: trErrors };
    log("  Transitions done: " + trOk);

    // ===== STEP 9: Audio Fade (technique 8) =====
    log("Step9: Audio fade");
    var audioOk = 0;
    var audioErrors = [];
    try {
        // Find BGM in project
        var bgmItem = null;
        var allItems = app.project.rootItem.children;
        for (var bi = 0; bi < allItems.length; bi++) {
            var bn = allItems[bi].name.toLowerCase();
            if (allItems[bi].type == 1 && (bn.indexOf("bgm") >= 0 || bn.indexOf(".mp3") >= 0)) {
                bgmItem = allItems[bi]; break;
            }
        }
        if (bgmItem && seq.audioTracks.length > 0) {
            var at = seq.audioTracks[0];
            at.insertClip(bgmItem, 0);
            sleep(1000);
            var aClips = at.clips;
            if (aClips.length > 0) {
                var ac = aClips[0];
                // Find volume component
                var volComp = null;
                for (var aci = 0; aci < ac.components.length; aci++) {
                    var acmn = ac.components[aci].matchName;
                    var acdn = ac.components[aci].displayName;
                    if (acmn.indexOf("Volume") >= 0 || acdn.indexOf("Volume") >= 0 || acdn.indexOf("音量") >= 0 ||
                        acmn.indexOf("Channel") >= 0 || acdn.indexOf("Channel") >= 0) {
                        volComp = ac.components[aci]; break;
                    }
                }
                if (volComp) {
                    var levelP = null;
                    for (var lpi = 0; lpi < volComp.properties.length; lpi++) {
                        var lpn2 = volComp.properties[lpi].displayName;
                        if (lpn2.indexOf("Level") >= 0 || lpn2.indexOf("Volume") >= 0 || lpn2.indexOf("音量") >= 0) {
                            levelP = volComp.properties[lpi]; break;
                        }
                    }
                    if (levelP) {
                        var as = ac.start.ticks;
                        var ae = ac.end.ticks;
                        levelP.setValue(-60, true);
                        levelP.addKey(as); try { levelP.setKeyValueAtKey(as, -60); } catch(e) {}
                        levelP.addKey(as + TICKS_PER_SEC); try { levelP.setKeyValueAtKey(as + TICKS_PER_SEC, 0); } catch(e) {}
                        levelP.addKey(ae - TICKS_PER_SEC); try { levelP.setKeyValueAtKey(ae - TICKS_PER_SEC, 0); } catch(e) {}
                        levelP.addKey(ae); try { levelP.setKeyValueAtKey(ae, -60); } catch(e) {}
                        audioOk++;
                        log("  Audio fade keyframes set");
                    } else {
                        // List props for debug
                        var apn = [];
                        for (var apd = 0; apd < volComp.properties.length; apd++) apn.push(volComp.properties[apd].displayName);
                        audioErrors.push("no Level prop, available: " + apn.join(","));
                        log("  VolComp props: " + apn.join(","));
                    }
                } else {
                    // List all audio components
                    var acn = [];
                    for (var acd = 0; acd < ac.components.length; acd++) acn.push(ac.components[acd].displayName + "|" + ac.components[acd].matchName);
                    audioErrors.push("no Volume comp, available: " + acn.join(","));
                    log("  Audio comps: " + acn.join(","));
                }
            }
        } else { audioErrors.push("no BGM or audio track"); }
    } catch(e) { audioErrors.push("outer: " + String(e).substring(0,40)); }
    result.steps.skill8_audio = { applied: audioOk, errors: audioErrors };
    log("  Audio done: " + audioOk);

    // ===== STEP 10: Save (non-blocking) =====
    log("Step10: Save");
    try { app.project.save(); } catch(e) { log("  save err: " + e); }

    // ===== DONE =====
    result.success = true;
    result.completed = new Date().toLocaleString();
    writeResult(result);
    log("=== Skills v3.0 COMPLETE ===");
})();
