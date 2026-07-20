# Tracking Data Export Template
# 跟踪数据导出模板 - 生成多格式跟踪数据（AE/Nuke/Boujou/JSON）
# 适用于将Silhouette跟踪数据传递到下游合成软件

from fx import *
import os
import json
import time
import math


def create_pipeline(
    source_path,
    output_dir,
    frame_rate=24.0,
    track_points=None,
    export_formats=None,
    track_mode="sub_pixel",
    search_size=32
):
    """
    创建跟踪数据导出管线

    参数:
        source_path (str): 源素材路径
        output_dir (str): 输出目录
        frame_rate (float): 帧率
        track_points (list): 跟踪点列表，每个元素为 {"name": 名称, "x": x坐标, "y": y坐标}
            None则使用默认跟踪点
        export_formats (list): 导出格式列表，支持:
            "ae_keyframes" - AE关键帧
            "nuke_tracker" - Nuke跟踪
            "boujou" - Boujou格式
            "json" - JSON格式
            "csv" - CSV格式
            None则导出所有格式
        track_mode (str): 跟踪模式 sub_pixel/full_pixel/fast
        search_size (int): 搜索区域大小
    """

    # 确保输出目录存在
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # ===== 1. 创建项目与会话 =====
    print("=== 步骤1: 创建项目 ===")
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Tracking_Export"
    activate(session)
    proj.addItem(session)

    # ===== 2. 加载源素材 =====
    print("=== 步骤2: 加载素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 获取素材信息
    src_width = session.width
    src_height = session.height
    start_frame = src.property("startFrame").value
    end_frame = src.property("endFrame").value

    print(f"  分辨率: {src_width}x{src_height}")
    print(f"  帧范围: {start_frame}-{end_frame}")

    # ===== 3. 创建跟踪节点 =====
    print("=== 步骤3: 创建跟踪节点 ===")
    tracker = Node("TrackerNode")
    tracker.label = "Main_Tracker"
    session.addNode(tracker)
    src.outputs[0].connect(tracker.inputs[1])

    # 配置跟踪参数
    tracker.property("trackMode").setValue(track_mode, 0)
    tracker.property("searchSize").setValue(search_size, 0)
    tracker.property("adaptiveSearch").setValue(True, 0)  # 自适应搜索
    tracker.property("adaptTemplate").setValue(True, 0)   # 自适应模板

    # ===== 4. 添加跟踪点 =====
    print("=== 步骤4: 添加跟踪点 ===")
    if track_points is None:
        # 默认跟踪点（四角加中心）
        track_points = [
            {"name": "top_left", "x": src_width * 0.25, "y": src_height * 0.25},
            {"name": "top_right", "x": src_width * 0.75, "y": src_height * 0.25},
            {"name": "bottom_left", "x": src_width * 0.25, "y": src_height * 0.75},
            {"name": "bottom_right", "x": src_width * 0.75, "y": src_height * 0.75},
            {"name": "center", "x": src_width * 0.5, "y": src_height * 0.5}
        ]

    for point in track_points:
        tracker.addTracker(
            name=point["name"],
            x=point["x"],
            y=point["y"],
            startFrame=start_frame,
            endFrame=end_frame
        )
        print(f"  跟踪点: {point['name']} ({point['x']:.0f}, {point['y']:.0f})")

    # ===== 5. 创建平面跟踪节点（可选） =====
    print("=== 步骤5: 创建平面跟踪 ===")
    planar = Node("PlanarTrackerNode")
    planar.label = "Planar_Tracker"
    planar.property("trackMode").setValue("forward", 0)
    planar.property("adaptModel").setValue(True, 0)
    session.addNode(planar)
    src.outputs[0].connect(planar.inputs[1])

    # ===== 6. 执行跟踪 =====
    print("=== 步骤6: 执行跟踪 ===")
    tracker.track()
    print("  点跟踪完成")

    planar.track()
    print("  平面跟踪完成")

    # ===== 7. 导出多格式数据 =====
    print("=== 步骤7: 导出跟踪数据 ===")
    if export_formats is None:
        export_formats = ["ae_keyframes", "nuke_tracker", "boujou", "json", "csv"]

    tracking_dir = os.path.join(output_dir, "tracking")
    os.makedirs(tracking_dir, exist_ok=True)

    export_results = {}

    for fmt in export_formats:
        export_path = get_export_path(tracking_dir, fmt)
        success = export_single_format(tracker, fmt, export_path, frame_rate)
        if success:
            export_results[fmt] = export_path
            print(f"  {fmt}: {export_path}")

    # ===== 8. 导出平面跟踪数据 =====
    print("=== 步骤8: 导出平面跟踪数据 ===")
    planar_path = os.path.join(tracking_dir, "planar_track.json")
    export_planar_data(planar, planar_path, frame_rate)
    export_results["planar"] = planar_path
    print(f"  planar: {planar_path}")

    # ===== 9. 计算跟踪质量指标 =====
    print("=== 步骤9: 计算跟踪质量 ===")
    quality = calculate_track_quality(tracker, start_frame, end_frame)
    print(f"  平均置信度: {quality['avg_confidence']:.2f}")
    print(f"  丢失帧数: {quality['lost_frames']}")

    # ===== 10. 生成跟踪报告 =====
    print("=== 步骤10: 生成跟踪报告 ===")
    report = {
        "version": "1.0",
        "source": "silhouette",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sourceFile": source_path,
        "outputDir": output_dir,
        "frameRate": frame_rate,
        "resolution": [src_width, src_height],
        "frameRange": [start_frame, end_frame],
        "trackConfig": {
            "mode": track_mode,
            "searchSize": search_size,
            "pointCount": len(track_points),
            "trackPoints": track_points
        },
        "exportFormats": export_results,
        "quality": quality,
        "recommendations": generate_recommendations(quality)
    }

    report_path = os.path.join(tracking_dir, "track_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  报告: {report_path}")

    print(f"\n=== 跟踪数据导出完成 ===")
    print(f"输出目录: {tracking_dir}")
    print(f"导出格式: {', '.join(export_formats)}")
    print(f"跟踪点数: {len(track_points)}")
    print(f"质量评分: {quality['avg_confidence']:.2f}/1.0")

    return proj, session


def get_export_path(tracking_dir, fmt):
    """根据格式获取导出路径"""
    extensions = {
        "ae_keyframes": ".txt",
        "nuke_tracker": ".nk",
        "boujou": ".txt",
        "json": ".json",
        "csv": ".csv"
    }
    ext = extensions.get(fmt, ".txt")
    filename = f"track_data_{fmt}{ext}"
    return os.path.join(tracking_dir, filename).replace("\\", "/")


def export_single_format(tracker, fmt, export_path, frame_rate):
    """导出单种格式"""
    try:
        if fmt == "json":
            # JSON格式单独处理
            export_json_format(tracker, export_path, frame_rate)
        elif fmt == "csv":
            # CSV格式单独处理
            export_csv_format(tracker, export_path, frame_rate)
        else:
            # 使用Silhouette内置导出
            tracker.property("exportFormat").setValue(fmt, 0)
            tracker.property("exportPath").setValue(export_path, 0)
            tracker.export()
        return True
    except Exception as e:
        print(f"  导出 {fmt} 失败: {e}")
        return False


def export_json_format(tracker, output_path, frame_rate):
    """导出JSON格式跟踪数据"""
    data = {
        "version": "1.0",
        "frameRate": frame_rate,
        "exportTime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "trackers": []
    }

    for i in range(tracker.numTrackers):
        track = tracker.getTracker(i)
        track_data = {
            "name": track.name,
            "startFrame": track.startFrame,
            "endFrame": track.endFrame,
            "keyframes": []
        }

        for frame in range(track.startFrame, track.endFrame + 1):
            pos = track.getPosition(frame)
            if pos:
                track_data["keyframes"].append({
                    "frame": frame,
                    "x": round(pos[0], 4),
                    "y": round(pos[1], 4),
                    "confidence": track.getConfidence(frame) if hasattr(track, 'getConfidence') else 1.0
                })

        data["trackers"].append(track_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_csv_format(tracker, output_path, frame_rate):
    """导出CSV格式跟踪数据"""
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "tracker_name", "x", "y", "confidence"])

        for i in range(tracker.numTrackers):
            track = tracker.getTracker(i)

            for frame in range(track.startFrame, track.endFrame + 1):
                pos = track.getPosition(frame)
                if pos:
                    confidence = track.getConfidence(frame) if hasattr(track, 'getConfidence') else 1.0
                    writer.writerow([
                        frame,
                        track.name,
                        round(pos[0], 4),
                        round(pos[1], 4),
                        round(confidence, 4)
                    ])


def export_planar_data(planar, output_path, frame_rate):
    """导出平面跟踪数据"""
    data = {
        "version": "1.0",
        "frameRate": frame_rate,
        "type": "planar",
        "transforms": []
    }

    # 提取每帧的变换矩阵
    session = activeSession()
    start_frame = session.node("SourceNode").property("startFrame").value
    end_frame = session.node("SourceNode").property("endFrame").value

    for frame in range(start_frame, end_frame + 1):
        transform = planar.getTransform(frame)
        if transform:
            data["transforms"].append({
                "frame": frame,
                "matrix": transform.matrix,
                "translation": transform.translation,
                "rotation": transform.rotation,
                "scale": transform.scale
            })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def calculate_track_quality(tracker, start_frame, end_frame):
    """计算跟踪质量指标"""
    total_confidence = 0
    total_points = 0
    lost_frames = 0

    for i in range(tracker.numTrackers):
        track = tracker.getTracker(i)

        for frame in range(track.startFrame, track.endFrame + 1):
            pos = track.getPosition(frame)
            if pos:
                confidence = track.getConfidence(frame) if hasattr(track, 'getConfidence') else 0.9
                total_confidence += confidence
                total_points += 1
            else:
                lost_frames += 1

    avg_confidence = total_confidence / total_points if total_points > 0 else 0

    # 计算抖动（帧间位置变化的标准差）
    jitter = calculate_jitter(tracker)

    return {
        "avg_confidence": avg_confidence,
        "lost_frames": lost_frames,
        "total_points": total_points,
        "jitter": jitter,
        "quality_score": avg_confidence * (1 - min(jitter / 2.0, 0.5))
    }


def calculate_jitter(tracker):
    """计算跟踪抖动"""
    jitter_values = []

    for i in range(tracker.numTrackers):
        track = tracker.getTracker(i)
        prev_pos = None

        for frame in range(track.startFrame, track.endFrame + 1):
            pos = track.getPosition(frame)
            if pos and prev_pos:
                dx = pos[0] - prev_pos[0]
                dy = pos[1] - prev_pos[1]
                distance = math.sqrt(dx * dx + dy * dy)
                jitter_values.append(distance)
            prev_pos = pos

    if not jitter_values:
        return 0

    # 计算标准差
    mean = sum(jitter_values) / len(jitter_values)
    variance = sum((x - mean) ** 2 for x in jitter_values) / len(jitter_values)
    return math.sqrt(variance)


def generate_recommendations(quality):
    """根据质量指标生成建议"""
    recommendations = []

    if quality["avg_confidence"] < 0.7:
        recommendations.append("跟踪置信度较低，建议手动检查关键帧")

    if quality["lost_frames"] > 0:
        recommendations.append(f"有 {quality['lost_frames']} 帧跟踪丢失，需手动修复")

    if quality["jitter"] > 1.0:
        recommendations.append("跟踪抖动较大，建议启用平滑滤波")

    if quality["quality_score"] > 0.85:
        recommendations.append("跟踪质量优秀，可直接使用")
    elif quality["quality_score"] > 0.7:
        recommendations.append("跟踪质量良好，建议小幅修正")
    else:
        recommendations.append("跟踪质量一般，需要较多手动修正")

    return recommendations


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        source = sys.argv[1]
        output = sys.argv[2]
    else:
        source = "D:/footage/sample_plate.exr"
        output = "D:/output/tracking_export"

    # 自定义跟踪点
    custom_points = [
        {"name": "head", "x": 960, "y": 300},
        {"name": "left_hand", "x": 820, "y": 500},
        {"name": "right_hand", "x": 1100, "y": 500},
        {"name": "left_foot", "x": 900, "y": 900},
        {"name": "right_foot", "x": 1020, "y": 900}
    ]

    create_pipeline(
        source_path=source,
        output_dir=output,
        frame_rate=24.0,
        track_points=custom_points,
        export_formats=["ae_keyframes", "nuke_tracker", "json", "csv"],
        track_mode="sub_pixel",
        search_size=48
    )
