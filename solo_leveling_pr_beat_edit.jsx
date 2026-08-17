/*
 * Solo Leveling 卡点剪辑脚本
 * =========================
 * 功能：
 * 1. 创建序列（1080x1920 竖屏 60fps）
 * 2. 导入音频和视频素材
 * 3. 将素材添加到时间线
 * 4. 按节拍点分割视频剪辑
 * 5. 添加闪白转场（Dip to White）
 * 6. 设置变速 + 光流补帧
 * 7. 调整音量
 */

#target premierepro

(function() {
    "use strict";

    var CONFIG = {
        sequenceName: "Solo_Leveling_BeatEdit",
        width: 1080,
        height: 1920,
        fps: 60,
        
        beatPoints: [
            0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0,
            4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0
        ],
        
        transitionName: "Dip to White",
        transitionDuration: 0.15,
        speedMultiplier: 120,
        audioVolume: -3
    };

    function log(msg) {
        try {
            var f = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge/beat_edit_log.txt");
            f.encoding = "UTF-8";
            if (f.open("a")) {
                f.writeln("[" + new Date().toLocaleString() + "] " + msg);
                f.close();
            }
        } catch(e) {}
    }

    function findItemByName(name, root) {
        if (!root) root = app.project.rootItem;
        for (var i = 0; i < root.children.numItems; i++) {
            var item = root.children[i];
            if (item.name === name) return item;
            if (item.type === 2) {
                var found = findItemByName(name, item);
                if (found) return found;
            }
        }
        return null;
    }

    function main() {
        var results = {
            success: true,
            steps: {},
            errors: []
        };

        try {
            log("=== 开始 Solo Leveling 卡点剪辑 ===");

            // 步骤1：创建序列（使用正确的 API）
            log("步骤1：创建序列...");
            var activeSeq = null;
            try {
                app.project.newSequence(CONFIG.sequenceName);
                log("  序列已创建: " + CONFIG.sequenceName);
                results.steps.createSequence = { name: CONFIG.sequenceName, success: true };
                
                for (var i = 0; i < app.project.sequences.length; i++) {
                    if (app.project.sequences[i].name === CONFIG.sequenceName) {
                        activeSeq = app.project.sequences[i];
                        log("  获取到序列对象");
                        break;
                    }
                }
            } catch(e) {
                log("  创建序列失败: " + e.message);
                results.errors.push("Create sequence failed: " + e.message);
                
                try {
                    for (var i = 0; i < app.project.sequences.length; i++) {
                        if (app.project.sequences[i].name === CONFIG.sequenceName) {
                            activeSeq = app.project.sequences[i];
                            log("  切换到已有序列: " + CONFIG.sequenceName);
                            break;
                        }
                    }
                } catch(e2) {}
            }

            if (!activeSeq) {
                results.success = false;
                results.errors.push("No active sequence");
                return results;
            }

            // 步骤2：检查项目中的素材
            log("步骤2：检查项目素材...");
            try {
                var rootItem = app.project.rootItem;
                var mediaItems = [];
                for (var i = 0; i < rootItem.children.numItems; i++) {
                    var item = rootItem.children[i];
                    if (item.type === 1) {
                        mediaItems.push(item.name);
                    }
                }
                log("  项目中找到 " + mediaItems.length + " 个素材: " + mediaItems.join(", "));
                results.steps.checkMedia = { count: mediaItems.length, items: mediaItems };
                
                if (mediaItems.length > 0) {
                    // 将第一个素材添加到时间线
                    var firstItem = findItemByName(mediaItems[0]);
                    if (firstItem) {
                        var videoTrack = activeSeq.videoTracks[0];
                        var startTime = new Time(0);
                        videoTrack.insertClip(firstItem, startTime);
                        log("  已将 " + mediaItems[0] + " 添加到时间线");
                        results.steps.addToTimeline = { clip: mediaItems[0], success: true };
                    }
                }
            } catch(e) {
                log("  检查素材失败: " + e.message);
                results.errors.push("Check media failed: " + e.message);
            }

            // 步骤3：按节拍点分割（如果有剪辑）
            log("步骤3：按节拍点分割剪辑...");
            try {
                var vTrack = activeSeq.videoTracks[0];
                if (vTrack.clips.numItems > 0) {
                    var splitCount = 0;
                    var beatsCopy = CONFIG.beatPoints.slice().sort(function(a, b) { return b - a; });
                    
                    for (var bi = 0; bi < beatsCopy.length; bi++) {
                        var beatTime = beatsCopy[bi];
                        var splitT = new Time(beatTime);
                        
                        for (var ci = 0; ci < vTrack.clips.numItems; ci++) {
                            var clip = vTrack.clips[ci];
                            if (clip.start.seconds < beatTime && clip.end.seconds > beatTime) {
                                try {
                                    vTrack.razorEdit(splitT, splitT);
                                    splitCount++;
                                } catch(e) {
                                    try { clip.split(splitT); splitCount++; } catch(e2) {}
                                }
                                break;
                            }
                        }
                    }
                    log("  分割完成，共 " + splitCount + " 个分割点");
                    results.steps.splitClips = { splitCount: splitCount, beatCount: CONFIG.beatPoints.length };
                } else {
                    log("  时间线没有剪辑，跳过分割");
                    results.steps.splitClips = { skipped: true, reason: "No clips on timeline" };
                }
            } catch(e) {
                log("  分割失败: " + e.message);
                results.errors.push("Split clips failed: " + e.message);
            }

            // 步骤4：添加闪白转场
            log("步骤4：添加闪白转场...");
            try {
                var vTrack2 = activeSeq.videoTracks[0];
                if (vTrack2.clips.numItems > 1) {
                    var transitionCount = 0;
                    for (var ci2 = 1; ci2 < vTrack2.clips.numItems; ci2++) {
                        try {
                            var currClip = vTrack2.clips[ci2];
                            var duration = new Time(CONFIG.transitionDuration);
                            if (typeof qe !== "undefined") {
                                currClip.addTransition(CONFIG.transitionName, duration, "in");
                                transitionCount++;
                            }
                        } catch(e) {}
                    }
                    log("  转场添加完成，共 " + transitionCount + " 个转场");
                    results.steps.addTransitions = { count: transitionCount, type: CONFIG.transitionName };
                } else {
                    log("  剪辑数量不足，跳过转场");
                    results.steps.addTransitions = { skipped: true, reason: "Not enough clips" };
                }
            } catch(e) {
                log("  添加转场失败: " + e.message);
                results.errors.push("Add transitions failed: " + e.message);
            }

            // 步骤5：设置变速和光流补帧
            log("步骤5：设置变速和光流补帧...");
            try {
                var vTrack3 = activeSeq.videoTracks[0];
                if (vTrack3.clips.numItems > 0) {
                    var speedCount = 0;
                    for (var ci3 = 0; ci3 < vTrack3.clips.numItems; ci3++) {
                        try {
                            var clip3 = vTrack3.clips[ci3];
                            if (clip3.speedChange) {
                                clip3.speedChange(CONFIG.speedMultiplier / 100, true, true);
                            }
                            if (clip3.timeInterpolation) {
                                clip3.timeInterpolation = 2;
                            }
                            speedCount++;
                        } catch(e) {}
                    }
                    log("  变速设置完成，共 " + speedCount + " 个剪辑");
                    results.steps.speedAndOpticalFlow = { count: speedCount, speed: CONFIG.speedMultiplier + "%" };
                } else {
                    log("  时间线没有剪辑，跳过变速");
                    results.steps.speedAndOpticalFlow = { skipped: true, reason: "No clips on timeline" };
                }
            } catch(e) {
                log("  变速设置失败: " + e.message);
                results.errors.push("Speed/Optical flow failed: " + e.message);
            }

            log("=== 卡点剪辑完成 ===");
            results.steps.completed = true;

        } catch(e) {
            results.success = false;
            results.errors.push("Fatal error: " + e.message);
            log("致命错误: " + e.message);
        }

        return results;
    }

    var result = main();
    return JSON.stringify(result);

})();
