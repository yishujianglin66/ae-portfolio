#!/usr/bin/env python3
"""
Silhouette → AE 数据交换格式演示
展示 Silhouette 执行后输出给 AE 的完整数据结构。
"""
import json
import os
from pathlib import Path

OUTPUT_DIR = Path(r"D:\AE-Work\silhouette_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1. Roto Matte 输出格式（Silhouette → AE）
# ============================================================
roto_matte_data = {
    "version": "2.0",
    "source": "silhouette",
    "silhouette_version": "2026.0.2",
    "export_type": "roto_matte",
    "timestamp": "2026-07-10T21:30:00",
    "project": {
        "name": "AutoRoto",
        "session": "AutoRoto_bezier",
        "fps": 30.0,
        "resolution": [1920, 1080],
        "duration_frames": 120,
    },
    "pipeline": {
        "nodes": ["SourceNode", "RotoNode", "OutputNode"],
        "connections": [
            {"from": "SourceNode.output", "to": "RotoNode.foreground"},
            {"from": "RotoNode.output", "to": "OutputNode.input"}
        ],
    },
    "roto_config": {
        "shape_type": "bezier",
        "tolerance": 1.5,
        "alpha_blur": 1.5,
        "antialias": 1.0,
        "tracking": "planar",
        "keyframe_interval": 5,
    },
    "matte_output": {
        "format": "png_sequence",
        "path_pattern": "D:/AE-Work/silhouette_output/matte_roto_{frame:04d}.png",
        "start_frame": 0,
        "end_frame": 119,
        "resolution": [1920, 1080],
        "channels": "RGBA",
        "premultiplied": True,
    },
    "ae_integration": {
        "comp_name": "Roto_Matte",
        "import_path": "D:/AE-Work/silhouette_output/",
        "footage_pattern": "matte_roto_[####].png",
        "apply_as": "track_matte",
        "target_layer": "foreground_footage",
        "matte_mode": "luma",
    }
}

# ============================================================
# 2. Track 跟踪数据输出格式（Silhouette → AE）
# ============================================================
track_data = {
    "version": "2.0",
    "source": "silhouette",
    "silhouette_version": "2026.0.2",
    "export_type": "tracking",
    "timestamp": "2026-07-10T21:30:00",
    "track_config": {
        "track_type": "planar",
        "search_area": 21,
        "accuracy": "medium",
        "node_type": "TrackerNode",
    },
    "trackers": [
        {
            "name": "PlanarTrack_01",
            "type": "planar",
            "frame_range": [0, 119],
            "keyframes": [
                {"frame": 0,  "position": [480.5, 270.3], "scale": 1.0, "rotation": 0.0},
                {"frame": 10, "position": [485.2, 272.1], "scale": 1.01, "rotation": 0.2},
                {"frame": 20, "position": [491.8, 275.6], "scale": 1.03, "rotation": 0.5},
                {"frame": 30, "position": [498.3, 278.9], "scale": 1.02, "rotation": 0.3},
                {"frame": 60, "position": [512.7, 285.4], "scale": 1.05, "rotation": 0.8},
                {"frame": 90, "position": [528.1, 291.2], "scale": 1.04, "rotation": 0.6},
                {"frame": 119, "position": [545.3, 298.7], "scale": 1.06, "rotation": 1.0},
            ],
            "corners": {
                "frame_0":  [[400, 200], [560, 200], [560, 340], [400, 340]],
                "frame_60": [[430, 215], [595, 215], [595, 355], [430, 355]],
                "frame_119": [[465, 230], [625, 230], [625, 370], [465, 370]],
            }
        },
        {
            "name": "PointTrack_01",
            "type": "point",
            "frame_range": [0, 119],
            "keyframes": [
                {"frame": 0,  "position": [100.0, 100.0]},
                {"frame": 30, "position": [105.3, 102.1]},
                {"frame": 60, "position": [110.7, 104.5]},
                {"frame": 90, "position": [116.2, 106.8]},
                {"frame": 119, "position": [121.5, 109.0]},
            ],
        }
    ],
    "ae_integration": {
        "export_format": "ae_keyframes",
        "target_comp": "Main_Composition",
        "apply_to": "null_object",
        "null_name": "Silhouette_Tracker",
        "position_property": "Position",
        "scale_property": "Scale",
        "rotation_property": "Rotation",
    }
}

# ============================================================
# 3. Paint 修复输出格式（Silhouette → AE）
# ============================================================
paint_data = {
    "version": "2.0",
    "source": "silhouette",
    "silhouette_version": "2026.0.2",
    "export_type": "paint",
    "timestamp": "2026-07-10T21:30:00",
    "paint_config": {
        "mode": "clone",
        "brush_size": 25,
        "brush_hardness": 0.5,
        "node_type": "PaintNode",
    },
    "painted_frames": {
        "format": "png_sequence",
        "path_pattern": "D:/AE-Work/silhouette_output/paint_repair_{frame:04d}.png",
        "frames": [45, 46, 47, 48, 49, 50],
        "resolution": [1920, 1080],
    },
    "ae_integration": {
        "comp_name": "Paint_Repair",
        "import_path": "D:/AE-Work/silhouette_output/",
        "footage_pattern": "paint_repair_[####].png",
        "apply_as": "replace_frames",
        "target_layer": "original_footage",
        "frame_offset": 0,
    }
}

# ============================================================
# 4. AE JSX 脚本（接收 Silhouette 数据并应用到 AE 合成）
# ============================================================
ae_jsx_script = """// AE JSX 脚本：接收 Silhouette 输出并应用到合成
// 由 AE-Knowledge-Vault silhouette_executor 自动生成

(function() {
    var dataFile = new File("D:/AE-Work/silhouette_output/silhouette_to_ae.json");
    dataFile.encoding = "UTF-8";
    dataFile.open("r");
    var data = JSON.parse(dataFile.read());
    dataFile.close();

    // 1. 导入 Matte 序列
    if (data.roto_matte) {
        var matteFolder = app.project.items.addFolder("Silhouette_Matte");
        var mattePath = data.roto_matte.ae_integration.import_path;
        var mattePattern = data.roto_matte.ae_integration.footage_pattern;
        
        var matteFile = new File(mattePath + mattePattern.replace("[####]", "0000"));
        var io = new ImportOptions(matteFile);
        io.sequence = true;
        var matteFootage = app.project.importFile(io);
        matteFootage.parentFolder = matteFolder;
        matteFootage.name = "Roto_Matte_Sequence";
        
        // 创建合成
        var comp = app.project.items.addComp(
            data.roto_matte.ae_integration.comp_name,
            1920, 1080, 1.0,
            data.roto_matte.project.duration_frames / data.roto_matte.project.fps,
            data.roto_matte.project.fps
        );
        
        // 添加原始素材
        var bgLayer = comp.layers.add(data.roto_matte.ae_integration.target_layer);
        bgLayer.name = "Background";
        
        // 添加 Matte 层
        var matteLayer = comp.layers.add(matteFootage);
        matteLayer.name = "Roto_Matte";
        
        // 设置 Track Matte
        bgLayer.trackMatteType = TrackMatteType.ALPHA;
        bgLayer.trackMatteLayer = matteLayer;
        
        // 隐藏 Matte 层
        matteLayer.enabled = false;
        
        $.writeln("[AE] Roto Matte applied to composition: " + comp.name);
    }
    
    // 2. 应用跟踪数据
    if (data.tracking) {
        var comp = app.project.activeItem;
        if (comp) {
            // 创建 Null 对象
            var nullLayer = comp.layers.addNull();
            nullLayer.name = data.tracking.ae_integration.null_name;
            
            // 应用位置关键帧
            var trackers = data.tracking.trackers;
            for (var t = 0; t < trackers.length; t++) {
                var tracker = trackers[t];
                var keyframes = tracker.keyframes;
                
                for (var k = 0; k < keyframes.length; k++) {
                    var kf = keyframes[k];
                    var time = kf.frame / comp.frameRate;
                    
                    nullLayer.property("Position").setValueAtTime(time, 
                        [kf.position[0], kf.position[1]]);
                    
                    if (kf.scale !== undefined) {
                        nullLayer.property("Scale").setValueAtTime(time,
                            [kf.scale * 100, kf.scale * 100]);
                    }
                    
                    if (kf.rotation !== undefined) {
                        nullLayer.property("Rotation").setValueAtTime(time,
                            kf.rotation);
                    }
                }
                
                $.writeln("[AE] Tracker applied: " + tracker.name + 
                    " (" + keyframes.length + " keyframes)");
            }
        }
    }
    
    // 3. 应用 Paint 修复
    if (data.paint) {
        var paintPath = data.paint.ae_integration.import_path;
        var paintPattern = data.paint.ae_integration.footage_pattern;
        
        var paintFile = new File(paintPath + paintPattern.replace("[####]", "0045"));
        var io = new ImportOptions(paintFile);
        io.sequence = true;
        var paintFootage = app.project.importFile(io);
        paintFootage.name = "Paint_Repair_Sequence";
        
        // 在合成中替换指定帧
        var comp = app.project.activeItem;
        if (comp) {
            var paintLayer = comp.layers.add(paintFootage);
            paintLayer.name = "Paint_Repair";
            
            // 设置帧范围
            var frames = data.paint.painted_frames.frames;
            if (frames.length > 0) {
                var startFrame = frames[0];
                var endFrame = frames[frames.length - 1];
                paintLayer.startTime = startFrame / comp.frameRate;
                paintLayer.outPoint = (endFrame + 1) / comp.frameRate;
            }
            
            $.writeln("[AE] Paint repair applied: " + frames.length + " frames");
        }
    }
    
    $.writeln("[AE] Silhouette integration complete!");
})();
"""


# ============================================================
# 输出所有文件
# ============================================================
if __name__ == "__main__":
    # 1. 保存 Roto Matte 数据
    roto_file = OUTPUT_DIR / "silhouette_to_ae.json"
    combined = {
        "roto_matte": roto_matte_data,
        "tracking": track_data,
        "paint": paint_data,
    }
    with open(roto_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"[1] 数据文件: {roto_file}")
    
    # 2. 保存 AE JSX 脚本
    jsx_file = OUTPUT_DIR / "apply_silhouette_to_ae.jsx"
    with open(jsx_file, "w", encoding="utf-8") as f:
        f.write(ae_jsx_script)
    print(f"[2] AE JSX 脚本: {jsx_file}")
    
    # 3. 打印摘要
    print("\n" + "=" * 60)
    print("Silhouette → AE 数据交换格式")
    print("=" * 60)
    
    print("\n[1] Roto Matte 数据:")
    print(f"  管线: {' → '.join(roto_matte_data['pipeline']['nodes'])}")
    print(f"  连接: Source.output → Roto.foreground → Output.input")
    print(f"  形状: {roto_matte_data['roto_config']['shape_type']}")
    print(f"  容差: {roto_matte_data['roto_config']['tolerance']}")
    print(f"  跟踪: {roto_matte_data['roto_config']['tracking']}")
    print(f"  输出: {roto_matte_data['matte_output']['path_pattern']}")
    print(f"  帧范围: {roto_matte_data['matte_output']['start_frame']}-{roto_matte_data['matte_output']['end_frame']}")
    print(f"  AE应用: {roto_matte_data['ae_integration']['apply_as']}")
    
    print("\n[2] Track 跟踪数据:")
    for t in track_data["trackers"]:
        print(f"  {t['name']} ({t['type']}): {len(t['keyframes'])} keyframes, frames {t['frame_range'][0]}-{t['frame_range'][1]}")
    print(f"  AE应用: {track_data['ae_integration']['apply_to']}")
    
    print("\n[3] Paint 修复数据:")
    print(f"  模式: {paint_data['paint_config']['mode']}")
    print(f"  笔刷: {paint_data['paint_config']['brush_size']}px")
    print(f"  修复帧: {paint_data['painted_frames']['frames']}")
    print(f"  AE应用: {paint_data['ae_integration']['apply_as']}")
    
    print(f"\n[4] AE JSX 脚本:")
    print(f"  文件: {jsx_file}")
    print(f"  功能: 导入Matte序列 → 创建合成 → 设置Track Matte")
    print(f"        → 应用跟踪关键帧 → 导入Paint修复帧")
    
    print("\n" + "=" * 60)
    print("完整数据流:")
    print("=" * 60)
    print("""
  Silhouette 2026                        AE 2026
  ┌──────────────┐                   ┌──────────────┐
  │ Node("RotoNode")│                │              │
  │ connect()      │                 │  JSX 脚本    │
  │ alpha.blur     │                 │              │
  │      ↓         │  JSON 数据      │  导入 Matte  │
  │ OutputNode     │ ──────────────→ │  设置 Track  │
  │      ↓         │  PNG 序列       │  Matte       │
  │ matte_0000.png │ ──────────────→ │              │
  │ matte_0001.png │                 │  应用跟踪    │
  │ ...            │                 │  关键帧      │
  │ track_data.json│ ──────────────→ │              │
  └──────────────┘                   └──────────────┘
    """)
