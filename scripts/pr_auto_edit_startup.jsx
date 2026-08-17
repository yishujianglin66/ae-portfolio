// ============================================================
// AE Knowledge Vault - Premiere Pro 全自动剪辑
// 放置于: Scripts/Startup/ 目录
// PR 启动时自动执行完整剪辑流程
// ============================================================

#target premiere

(function() {
    // 配置
    var bridgePath = Folder.temp.fsName + "/ae_kv_pr_bridge";
    var bridgeDir = new Folder(bridgePath);
    if (!bridgeDir.exists) {
        bridgeDir.create();
    }

    var clipDir = Folder.temp.fsName + "/ae_kv_pr_test_clips";
    var outputPath = bridgePath + "/auto_edit_output.mp4";
    var resultPath = bridgePath + "/auto_edit_result.json";
    var logPath = bridgePath + "/auto_edit_log.txt";

    // 日志
    function log(msg) {
        try {
            var f = new File(logPath);
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln("[" + new Date().toUTCString() + "] " + msg);
            f.close();
        } catch(e) {}
    }

    log("=== Auto Edit Starting ===");

    // 延迟执行，等待 PR 完全就绪
    function startAutoEdit() {
        log("PR ready, starting auto edit...");

        try {
            // 写入开始标记
            var startFile = new File(bridgePath + "/auto_edit_started.txt");
            startFile.encoding = "UTF-8";
            startFile.open("w");
            startFile.writeln("STARTED");
            startFile.writeln("time: " + new Date().toUTCString());
            startFile.close();

            var result = {
                started: new Date().toUTCString(),
                steps: {}
            };

            // Step 1: 查找素材
            log("Step 1: Finding clips...");
            var clipFolder = new Folder(clipDir);
            var clipFiles = clipFolder.getFiles("*.mp4");
            log("  Found " + clipFiles.length + " clips");
            result.steps.foundClips = clipFiles.length;

            if (clipFiles.length === 0) {
                throw new Error("No test clips found in " + clipDir);
            }

            // Step 2: 导入素材
            log("Step 2: Importing media...");
            var importedNames = [];
            for (var i = 0; i < clipFiles.length; i++) {
                try {
                    app.project.importFiles([clipFiles[i]], 1, app.project.rootItem, 0);
                    importedNames.push(clipFiles[i].displayName);
                    log("  Imported: " + clipFiles[i].displayName);
                } catch(e) {
                    log("  Import error: " + e.toString());
                }
            }
            result.steps.imported = importedNames.length;
            result.importedClips = importedNames;

            // Step 3: 创建序列
            log("Step 3: Creating sequence...");
            var seqName = "AE_KV_Auto_Edit";
            var seq = null;

            // 先尝试用第一个素材创建序列（自动匹配参数）
            try {
                // 找到第一个导入的素材
                var firstClip = null;
                for (var j = 0; j < app.project.rootItem.children.length; j++) {
                    var item = app.project.rootItem.children[j];
                    if (item.type === ProjectItemType.CLIP) {
                        firstClip = item;
                        break;
                    }
                }

                if (firstClip) {
                    seq = app.project.newSequence(seqName, firstClip);
                    log("  Sequence created from clip: " + firstClip.name);
                } else {
                    seq = app.project.newSequence(seqName);
                    log("  Sequence created (default)");
                }
            } catch(e) {
                log("  Create sequence error: " + e.toString());
                try {
                    seq = app.project.newSequence(seqName);
                    log("  Sequence created (fallback)");
                } catch(e2) {
                    log("  Fallback also failed: " + e2.toString());
                }
            }
            result.steps.sequenceCreated = (seq !== null);

            if (!seq) {
                throw new Error("Failed to create sequence");
            }

            // Step 4: 添加素材到时间轴
            log("Step 4: Adding clips to timeline...");
            var track = seq.videoTracks[0];
            var currentTime = 0;
            var clipsOnTrack = 0;

            // 遍历项目中的素材
            for (var k = 0; k < app.project.rootItem.children.length; k++) {
                var clipItem = app.project.rootItem.children[k];
                if (clipItem.type === ProjectItemType.CLIP) {
                    try {
                        track.insertClip(clipItem, currentTime);
                        // 估算片段时长（简化处理）
                        currentTime += 3.5; // 每个片段间隔3.5秒
                        clipsOnTrack++;
                        log("  Added to track: " + clipItem.name);
                    } catch(e) {
                        log("  Add clip error: " + e.toString());
                    }
                }
            }
            result.steps.clipsOnTrack = clipsOnTrack;

            // Step 5: 保存项目
            log("Step 5: Saving project...");
            try {
                var projPath = bridgePath + "/auto_edit_project.prproj";
                app.project.saveAs(new File(projPath));
                log("  Project saved to: " + projPath);
                result.projectPath = projPath;
                result.steps.saved = true;
            } catch(e) {
                log("  Save error: " + e.toString());
                result.steps.saved = false;
            }

            // Step 6: 导出
            log("Step 6: Exporting...");
            try {
                seq.exportAsMediaDirect(outputPath, "H.264", 1);
                log("  Export started: " + outputPath);
                result.steps.exportStarted = true;
                result.outputPath = outputPath;
            } catch(e) {
                log("  Export error: " + e.toString());
                result.steps.exportStarted = false;
                result.exportError = e.toString();
            }

            // 写入结果
            result.completed = new Date().toUTCString();
            result.status = "success";

            var resultFile = new File(resultPath);
            resultFile.encoding = "UTF-8";
            resultFile.open("w");
            resultFile.writeln(JSON.stringify(result));
            resultFile.close();

            log("=== Auto Edit Completed Successfully ===");

        } catch(e) {
            log("FATAL ERROR: " + e.toString());

            var errorResult = {
                status: "error",
                error: e.toString(),
                time: new Date().toUTCString()
            };

            try {
                var errFile = new File(resultPath);
                errFile.encoding = "UTF-8";
                errFile.open("w");
                errFile.writeln(JSON.stringify(errorResult));
                errFile.close();
            } catch(e2) {}
        }
    }

    // 延迟启动，确保 PR 完全就绪
    // 使用 app.scheduleTask 或简单延迟
    try {
        log("Scheduling auto edit in 5 seconds...");
        // 尝试多种延迟方式
        if (app.scheduleTask) {
            app.scheduleTask(startAutoEdit, 5.0, false);
            log("Using app.scheduleTask");
        } else {
            // 直接执行（但先写个延迟标记）
            log("No scheduler found, running after busy wait...");
            // 简单等待
            var start = new Date().getTime();
            while (new Date().getTime() - start < 5000) {
                // 忙等（不推荐，但作为备用方案）
            }
            startAutoEdit();
        }
    } catch(e) {
        log("Schedule error: " + e.toString());
        // 直接运行
        startAutoEdit();
    }

})();
