// ============================================================
// Premiere Pro 全自动剪辑脚本
// 功能：导入素材 → 创建序列 → 添加剪辑 → 应用转场 → 调色 → 导出
// 使用方式：
//   方式1: "Adobe Premiere Pro.exe" -r this_script.jsx
//   方式2: 放入 Scripts/Startup/ 目录，PR 启动时自动运行
// ============================================================

(function() {
    // 配置
    var CONFIG = {
        clipsDir: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/pr_final_output/clips/",
        outputDir: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/pr_final_output/pr_export/",
        sequenceName: "Auto Edit Sequence",
        transitionDuration: 0.5,
        clipDuration: 3.0
    };

    // 结果记录
    var result = {
        status: "running",
        startTime: new Date().toISOString(),
        steps: [],
        imported: 0,
        transitions: 0,
        effectsAdded: 0
    };

    function log(step, msg) {
        result.steps.push({ step: step, message: msg, time: new Date().toISOString() });
    }

    function saveResult(status) {
        result.status = status;
        result.endTime = new Date().toISOString();

        var outDir = new Folder(CONFIG.outputDir);
        if (!outDir.exists) outDir.create();

        var outFile = new File(outDir.fsName + "/auto_edit_result.json");
        outFile.open("w");
        outFile.write(JSON.stringify(result, null, 2));
        outFile.close();
    }

    try {
        // ===== 步骤 1: 创建/获取项目 =====
        log("step1", "准备项目");

        var proj;
        if (app.project) {
            proj = app.project;
            log("step1", "使用现有项目");
        } else {
            // 创建新项目
            var projPath = new Folder(CONFIG.outputDir);
            if (!projPath.exists) projPath.create();
            app.newProject();
            app.project.save(projPath.fsName + "/auto_edit.prproj");
            proj = app.project;
            log("step1", "创建新项目");
        }

        // ===== 步骤 2: 导入素材 =====
        log("step2", "导入素材");

        var clipsFolder = new Folder(CONFIG.clipsDir);
        if (!clipsFolder.exists) {
            throw new Error("素材目录不存在: " + CONFIG.clipsDir);
        }

        var clipFiles = clipsFolder.getFiles("clip_*.mp4");
        clipFiles.sort(function(a, b) { return a.name.localeCompare(b.name); });

        var importedClips = [];
        for (var i = 0; i < clipFiles.length; i++) {
            try {
                var file = clipFiles[i];
                var filesToImport = new Array(file.fsName);
                proj.importFiles(filesToImport, true, proj.rootItem, false);

                // 找到刚导入的素材
                for (var j = 0; j < proj.rootItem.children.numItems; j++) {
                    var child = proj.rootItem.children[j];
                    if (child.name === file.displayName) {
                        importedClips.push(child);
                        break;
                    }
                }
                result.imported++;
            } catch (e) {
                log("step2", "导入失败: " + clipFiles[i].name + " - " + e.toString());
            }
        }

        log("step2", "成功导入 " + result.imported + " 个素材");

        if (importedClips.length === 0) {
            throw new Error("没有导入任何素材");
        }

        // ===== 步骤 3: 创建序列 =====
        log("step3", "创建序列");

        var seq = null;
        // 查找现有同名序列
        for (var s = 0; s < proj.sequences.numSequences; s++) {
            if (proj.sequences[s].name === CONFIG.sequenceName) {
                seq = proj.sequences[s];
                break;
            }
        }

        if (!seq) {
            // 创建新序列 - 尝试使用 DSLR 1080p30 预设
            try {
                seq = proj.createNewSequence(CONFIG.sequenceName, "DSLR 1080p30");
            } catch (e) {
                // 如果预设不存在，创建默认序列
                try {
                    seq = proj.createNewSequence(CONFIG.sequenceName);
                } catch (e2) {
                    // 最后的 fallback: 用第一个素材创建序列
                    if (importedClips.length > 0) {
                        seq = proj.createNewSequenceFromClips(
                            CONFIG.sequenceName,
                            [importedClips[0]],
                            proj.rootItem
                        );
                    }
                }
            }
        }

        if (!seq) {
            throw new Error("无法创建序列");
        }

        log("step3", "序列创建成功: " + seq.name);

        // ===== 步骤 4: 添加剪辑到时间轴 =====
        log("step4", "添加剪辑到时间轴");

        var videoTrack = seq.videoTracks[0];
        var currentTime = 0;

        for (var c = 0; c < importedClips.length; c++) {
            try {
                var clip = importedClips[c];
                // 插入到轨道
                videoTrack.insertClip(clip, currentTime);
                currentTime += CONFIG.clipDuration;
            } catch (e) {
                log("step4", "添加剪辑失败: " + clip.name + " - " + e.toString());
            }
        }

        log("step4", "添加了 " + videoTrack.clips.numItems + " 个剪辑到时间轴");

        // ===== 步骤 5: 应用转场 =====
        log("step5", "应用转场效果");

        for (var t = 0; t < videoTrack.clips.numItems - 1; t++) {
            try {
                var trackClip = videoTrack.clips[t];
                var trans = trackClip.applyTransition("Cross Dissolve");
                if (trans) {
                    trans.duration = CONFIG.transitionDuration;
                    result.transitions++;
                }
            } catch (e) {
                // 跳过失败的转场
            }
        }

        log("step5", "应用了 " + result.transitions + " 个转场");

        // ===== 步骤 6: 应用调色效果 =====
        log("step6", "应用 Lumetri 调色");

        for (var e = 0; e < videoTrack.clips.numItems; e++) {
            try {
                var gClip = videoTrack.clips[e];
                gClip.effects.addVideoEffect("Lumetri Color");
                result.effectsAdded++;
            } catch (ex) {
                // 跳过失败的效果
            }
        }

        log("step6", "添加了 " + result.effectsAdded + " 个 Lumetri Color 效果");

        // ===== 步骤 7: 保存项目 =====
        log("step7", "保存项目");
        proj.save();
        log("step7", "项目已保存");

        // ===== 步骤 8: 导出视频 =====
        log("step8", "导出视频");

        try {
            var outputPath = CONFIG.outputDir + "final_export.mp4";
            // 尝试导出
            seq.exportAsMediaDirect(outputPath, "H.264", 1);
            log("step8", "导出已启动: " + outputPath);
            result.exporting = true;
            result.outputPath = outputPath;
        } catch (e) {
            log("step8", "导出失败: " + e.toString());
            result.exportError = e.toString();
        }

        // ===== 完成 =====
        saveResult("success");
        log("done", "全自动剪辑完成!");

    } catch (e) {
        result.error = e.toString();
        result.errorLine = e.line || "unknown";
        saveResult("error");
    }

    return JSON.stringify(result, null, 2);
})();
