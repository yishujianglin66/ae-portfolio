// ============================================================
// PR 业务 Handler - 卡点剪辑等业务逻辑
// 由 pr_bridge_core.jsx 自动加载（loadAllHandlers 扫描 handler_*.jsx）
//
// 注意：此文件为单一来源（scripts/），由 PRBridgeCEP/host.jsx 同步到
//   .premiere-mcp-bridge/handler_pr_business.jsx 后被加载。
//   业务变更请修改本文件，PR 重启或 Reload Handlers 后自动生效。
//
// 以下 handler 已由 pr_bridge_core.jsx 内置，此处不再重复定义：
//   - ping / getInfo / execute_script / registerHandler / reloadHandlers
//   - listSequences / getProjectInfo / executeScriptFile
// 本文件仅保留核心未覆盖的业务逻辑：序列创建/素材导入/轨道编辑/转场/效果/保存
// ============================================================

// 序列创建（修复版）
PRBridge.register("createSequence", function(cmd) {
    var name = cmd.name || "Auto Sequence";
    try {
        var seq = app.project.newSequence(name);
        PRBridge.log("Sequence created: " + name);
        return { name: name, created: true };
    } catch(e) {
        PRBridge.log("Create sequence error: " + e);
        return { error: e.toString() };
    }
});

// 导入素材
PRBridge.register("importMedia", function(cmd) {
    if (!cmd.files || !cmd.files.length) {
        return { error: "No files specified" };
    }

    var imported = [];
    var errors = [];

    for (var i = 0; i < cmd.files.length; i++) {
        try {
            var f = new File(cmd.files[i]);
            if (f.exists) {
                app.project.importFiles([f], 1, app.project.rootItem, 0);
                imported.push(f.displayName);
                PRBridge.log("Imported: " + f.displayName);
            } else {
                errors.push("File not found: " + cmd.files[i]);
            }
        } catch(e) {
            errors.push(cmd.files[i] + ": " + e.toString());
        }
    }

    return { imported: imported, errors: errors, count: imported.length };
});

// 添加素材到轨道
PRBridge.register("addClipToTrack", function(cmd) {
    var trackIdx = cmd.track || 0;
    var startTime = cmd.startTime || 0;
    var clipName = cmd.clipName || "";

    try {
        if (app.project.sequences.length === 0) {
            return { error: "No sequences in project" };
        }

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

        if (!targetClip) {
            return { error: "Clip not found" };
        }

        track.insertClip(targetClip, startTime);
        PRBridge.log("Added clip: " + targetClip.name);
        return { added: true, clip: targetClip.name };
    } catch(e) {
        return { error: e.toString() };
    }
});

// 应用转场
PRBridge.register("applyTransition", function(cmd) {
    var clipIndex = cmd.clipIndex || 0;
    var track = cmd.track || 0;
    var transition = cmd.transition || "Cross Dissolve";
    var duration = cmd.duration || 0.5;

    try {
        if (app.project.sequences.length === 0) {
            return { error: "No sequences" };
        }

        var seq = app.project.sequences[0];
        var t = seq.videoTracks[track];

        if (t.clips.numItems <= clipIndex) {
            return { error: "Clip index out of range" };
        }

        var clip = t.clips[clipIndex];
        if (typeof qe !== 'undefined') {
            clip.addTransition(transition, duration, "start");
            PRBridge.log("Applied transition: " + transition);
            return { applied: true, transition: transition };
        }
        return { error: "QE DOM not available" };
    } catch(e) {
        return { error: e.toString() };
    }
});

// 应用效果
PRBridge.register("addEffect", function(cmd) {
    var clipIndex = cmd.clipIndex || 0;
    var effect = cmd.effect || "Lumetri Color";
    var track = cmd.track || 0;

    try {
        if (app.project.sequences.length === 0) {
            return { error: "No sequences" };
        }

        var seq = app.project.sequences[0];
        var t = seq.videoTracks[track];

        if (t.clips.numItems <= clipIndex) {
            return { error: "Clip index out of range" };
        }

        var clip = t.clips[clipIndex];
        if (typeof qe !== 'undefined') {
            clip.addEffect(effect);
            PRBridge.log("Added effect: " + effect);
            return { applied: true, effect: effect };
        }
        return { error: "QE DOM not available" };
    } catch(e) {
        return { error: e.toString() };
    }
});

// 保存项目
PRBridge.register("saveProject", function(cmd) {
    try {
        app.project.save();
        PRBridge.log("Project saved");
        return { saved: true };
    } catch(e) {
        return { error: e.toString() };
    }
});

PRBridge.log("Business handlers loaded");