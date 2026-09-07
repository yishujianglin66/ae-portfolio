// ============================================================
// PR Skills v3.1 - 修复 Speed/Lumetri/Transitions/Audio
// 基于 v3.0 探查结果：
//   - addComponent 不存在
//   - setSpeed 不存在，getSpeed 存在
//   - QE getClipAt 不存在
//   - Motion 关键帧已 OK
//   - Audio Volume 组件存在但属性名编码问题
// ============================================================
(function() {
    var BRIDGE_DIR = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge";
    var LOG_FILE = BRIDGE_DIR + "/skills_v31_log.txt";
    var RES_FILE = BRIDGE_DIR + "/pr_skills_result.json";
    var TICKS_PER_SEC = 254016000000;

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

    function log(msg) {
        try { var f = new File(LOG_FILE); f.encoding = "UTF-8"; f.open("a"); f.writeln(new Date().toLocaleTimeString() + " | " + msg); f.close(); } catch(e) {}
    }
    function writeResult(obj) {
        try { var f = new File(RES_FILE); f.encoding = "UTF-8"; f.open("w"); f.write(JSON.stringify(obj)); f.close(); } catch(e) {}
    }
    function sleep(ms) { try { $.sleep(ms); } catch(e) {} }

    log("=== Skills v3.1 FIX START ===");
    var result = { version: "3.1", steps: {} };

    // Wait for project + sequence (max 90s)
    var seq = null;
    for (var w = 0; w < 90; w++) {
        try {
            seq = app.project.activeSequence;
            if (!seq && app.project.sequences.length > 0) seq = app.project.sequences[0];
            if (seq) break;
        } catch(e) {}
        sleep(1000);
    }
    if (!seq) { log("FATAL: no sequence after 90s"); writeResult({success:false,error:"no_seq"}); return; }
    log("Seq ready after " + w + "s: " + seq.name);
    log("Seq: " + seq.name + ", V1 clips=" + seq.videoTracks[0].clips.length);

    var vt = seq.videoTracks[0];
    var clips = vt.clips;

    // ===== FIX 1: Speed Ramp via QE DOM alternative paths =====
    log("--- FIX Speed ---");
    var speedOk = 0;
    var speedInfo = [];
    var speedVals = [125, 75, 150, 90, 110];

    // Probe QE DOM structure properly
    var qeOk = false;
    try {
        app.enableQE();
        var qseq = qe.project.getActiveSequence();
        if (qseq) {
            // List qseq methods
            var qseqM = [];
            for (var m in qseq) { if (typeof qseq[m] === "function") qseqM.push(m); }
            log("  QE seq methods: " + qseqM.join(","));

            // Try different track access
            var qvt = null;
            try { qvt = qseq.getVideoTrackAt(0); } catch(e) {}
            if (!qvt) { try { qvt = qseq.videoTracks[0]; } catch(e) {} }

            if (qvt) {
                var qvtM = [];
                for (var tm in qvt) { if (typeof qvt[tm] === "function") qvtM.push(tm); }
                log("  QE track methods: " + qvtM.join(","));
                var qvtP = [];
                for (var tp in qvt) { if (typeof qvt[tp] !== "function") qvtP.push(tp + "=" + qvt[tp]); }
                log("  QE track props: " + qvtP.join(","));

                // Try different clip access methods
                var qc = null;
                try { if (qvt.getClipAt) qc = qvt.getClipAt(0); } catch(e) { speedInfo.push("getClipAt:" + e); }
                if (!qc) { try { qc = qvt.clips[0]; } catch(e) {} }
                if (!qc) { try { qc = qvt[0]; } catch(e) {} }

                if (qc) {
                    var qcM = [];
                    for (var cm in qc) { if (typeof qc[cm] === "function") qcM.push(cm); }
                    log("  QE clip methods: " + qcM.join(","));
                    var qcP = [];
                    for (var cp in qc) { if (typeof qc[cp] !== "function") qcP.push(cp); }
                    log("  QE clip props: " + qcP.join(","));
                    qeOk = true;
                } else {
                    speedInfo.push("no QE clip access");
                }
            }
        }
    } catch(qe) { speedInfo.push("QE:" + qe); }

    // Speed: try standard DOM setSpeed/setInPoint/setOutPoint approach
    for (var si = 0; si < Math.min(clips.length, 5); si++) {
        try {
            var sc = clips[si];
            var curSpeed = 1;
            try { curSpeed = sc.getSpeed(); } catch(e) {}
            // Try setSpeed (might exist but named differently)
            var speedSet = false;
            try { if (sc.setSpeed) { sc.setSpeed(speedVals[si]); speedSet = true; } } catch(e) {}
            // Try via QE
            if (!speedSet && qeOk) {
                try {
                    var qseq2 = qe.project.getActiveSequence();
                    var qvt2 = qseq2.getVideoTrackAt(0);
                    // Try accessing clip by index
                    var qc2 = null;
                    try { qc2 = qvt2.clips[si]; } catch(e) {}
                    if (qc2 && qc2.setSpeed) { qc2.setSpeed(speedVals[si]); speedSet = true; }
                } catch(e) {}
            }
            if (speedSet) { speedOk++; log("  clip" + si + " speed set to " + speedVals[si]); }
            else { speedInfo.push("clip" + si + ":no_set_method"); }
        } catch(e) { speedInfo.push("clip" + si + ":" + String(e).substring(0,30)); }
    }
    result.steps.skill2_speed = { applied: speedOk, info: speedInfo, currentSpeed: clips.length > 0 ? clips[0].getSpeed() : -1 };
    log("  Speed result: " + speedOk);

    // ===== FIX 2: Lumetri - try all possible approaches =====
    log("--- FIX Lumetri ---");
    var lumOk = 0;
    var lumInfo = [];
    // Since addComponent doesn't exist, try:
    // 1. Check if there's a hidden Lumetri via matchName scan
    // 2. Try QE DOM component access
    // 3. Try applying via project-level color management
    if (clips.length > 0) {
        var c0 = clips[0];
        // Full component scan with matchName
        var allComps = [];
        for (var lci = 0; lci < c0.components.length; lci++) {
            allComps.push(c0.components[lci].matchName + "|" + c0.components[lci].displayName);
        }
        lumInfo.push("comps:" + allComps.join(";"));

        // Try QE DOM component access
        try {
            app.enableQE();
            var qs3 = qe.project.getActiveSequence();
            var qvt3 = qs3.getVideoTrackAt(0);
            // Try to get clip components via QE
            var qclips3 = null;
            try { qclips3 = qvt3.clips; } catch(e) {}
            if (qclips3 && qclips3.length > 0) {
                var qc3 = qclips3[0];
                if (qc3 && qc3.components) {
                    lumInfo.push("qe_comps:" + qc3.components.length);
                    for (var qci = 0; qci < qc3.components.length; qci++) {
                        lumInfo.push("qe_c" + qci + ":" + qc3.components[qci].displayName);
                    }
                }
            }
        } catch(e) { lumInfo.push("qe_lum:" + String(e).substring(0,30)); }

        // Alternative: Use Opacity component to simulate color adjustment
        // (not real Lumetri, but demonstrates component property manipulation)
        var opComp = c0.components[0]; // Opacity
        if (opComp) {
            var opProps = [];
            for (var opi = 0; opi < opComp.properties.length; opi++) {
                opProps.push(opComp.properties[opi].displayName);
            }
            lumInfo.push("opacity_props:" + opProps.join(","));
        }
    }
    result.steps.skill3_lumetri = { applied: lumOk, info: lumInfo, note: "PR2025_no_addComponent_API" };
    log("  Lumetri result: " + lumOk + " (API limitation confirmed)");

    // ===== FIX 3: Transitions - try correct QE DOM methods =====
    log("--- FIX Transitions ---");
    var trOk = 0;
    var trInfo = [];
    try {
        app.enableQE();
        var qs4 = qe.project.getActiveSequence();
        var qvt4 = qs4.getVideoTrackAt(0);

        // Try accessing clips via QE
        var qClips4 = null;
        try { qClips4 = qvt4.clips; } catch(e) { trInfo.push("clips:" + e); }

        if (qClips4 && qClips4.length > 1) {
            log("  QE clips accessible: " + qClips4.length);
            var TR_NAMES = ["Cross Dissolve", "Dip to Black", "Film Dissolve"];
            for (var ti = 0; ti < Math.min(qClips4.length - 1, 4); ti++) {
                var tc = qClips4[ti];
                for (var tni = 0; tni < TR_NAMES.length; tni++) {
                    try {
                        // Try various transition API signatures
                        var tr = null;
                        try { tr = qvt4.addVideoTransition(TR_NAMES[tni], tc, 2, 0, 24, 0); } catch(e1) {}
                        if (!tr) { try { tr = qvt4.addTransition(TR_NAMES[tni], tc.end, 24); } catch(e2) {} }
                        if (!tr) { try { tr = tc.addTransition(TR_NAMES[tni], 2, 24); } catch(e3) { if (ti===0 && tni===0) trInfo.push("clip.addTrans:" + e3); } }
                        if (tr) { trOk++; log("  Transition OK: " + TR_NAMES[tni] + " at " + ti); break; }
                    } catch(e) { if (tni === 0) trInfo.push("t" + ti + ":" + String(e).substring(0,30)); }
                }
            }
        } else {
            trInfo.push("QE clips not accessible");
            // Fallback: standard DOM track.addTransition
            try {
                if (vt.addTransition) {
                    log("  std track.addTransition exists!");
                    for (var sti = 0; sti < Math.min(clips.length - 1, 4); sti++) {
                        try {
                            var added = vt.addTransition("Cross Dissolve", clips[sti].end, 1);
                            if (added) { trOk++; log("  StdDOM transition at " + sti); }
                        } catch(ste) { if (sti === 0) trInfo.push("std:" + ste); }
                    }
                } else { trInfo.push("no_addTransition_on_track"); }
            } catch(e) { trInfo.push("std_outer:" + e); }
        }
    } catch(e) { trInfo.push("outer:" + String(e).substring(0,30)); }
    result.steps.skill7_transitions = { applied: trOk, info: trInfo };
    log("  Transitions result: " + trOk);

    // ===== FIX 4: Audio Fade - iterate by index =====
    log("--- FIX Audio ---");
    var audioOk = 0;
    var audioInfo = [];
    try {
        var at = seq.audioTracks[0];
        if (at.clips.length > 0) {
            var ac = at.clips[0];
            log("  Audio clip: " + ac.name + ", comps=" + ac.components.length);
            // Iterate ALL components and ALL properties by index
            for (var aci = 0; aci < ac.components.length; aci++) {
                var acomp = ac.components[aci];
                audioInfo.push("comp" + aci + ":" + acomp.matchName);
                var aprops = acomp.properties;
                for (var api = 0; aprops && api < aprops.length; api++) {
                    var aprop = aprops[api];
                    var apVal = "";
                    try { apVal = String(aprop.getValue()); } catch(e) { apVal = "?"; }
                    var apKf = false;
                    try { apKf = aprop.isKeyframable(); } catch(e) {}
                    audioInfo.push("  p" + api + ":dn=" + aprop.displayName + " mn=" + (aprop.matchName || "?") + " val=" + apVal + " kf=" + apKf);
                    log("  AudioProp[" + aci + "][" + api + "]: " + aprop.displayName + " | " + (aprop.matchName || "?") + " = " + apVal + " kf=" + apKf);

                    // Try to set keyframes on ANY keyframable property
                    if (apKf && audioOk === 0) {
                        try {
                            var as = ac.start.ticks;
                            var ae2 = ac.end.ticks;
                            aprop.setValue(-60, true);
                            aprop.addKey(as);
                            try { aprop.setKeyValueAtKey(as, -60); } catch(e) {}
                            aprop.addKey(as + TICKS_PER_SEC);
                            try { aprop.setKeyValueAtKey(as + TICKS_PER_SEC, 0); } catch(e) {}
                            aprop.addKey(ae2 - TICKS_PER_SEC);
                            try { aprop.setKeyValueAtKey(ae2 - TICKS_PER_SEC, 0); } catch(e) {}
                            aprop.addKey(ae2);
                            try { aprop.setKeyValueAtKey(ae2, -60); } catch(e) {}
                            audioOk++;
                            log("  Audio fade applied on prop[" + aci + "][" + api + "]");
                        } catch(kfe) { audioInfo.push("kf_err:" + kfe); }
                    }
                }
            }
        } else { audioInfo.push("no_audio_clips"); }
    } catch(e) { audioInfo.push("outer:" + String(e).substring(0,30)); }
    result.steps.skill8_audio = { applied: audioOk, info: audioInfo };
    log("  Audio result: " + audioOk);

    // ===== Save & Done =====
    try { app.project.save(); } catch(e) {}
    result.success = true;
    result.completed = new Date().toLocaleString();
    writeResult(result);
    log("=== Skills v3.1 COMPLETE ===");
})();
