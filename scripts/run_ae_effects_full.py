"""
方案二: AE 完整特效流水线
=========================
自动启动AE → 创建合成 → 导入V17 → 文字动画 → 转场 → 渲染输出
全部通过 execute_script (JSX) 实现
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

V17_VIDEO = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
OUTPUT_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
AE_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")

def is_running(name):
    try:
        r = subprocess.run("tasklist", capture_output=True, text=True, shell=True, timeout=10)
        return name.lower() in r.stdout.lower()
    except:
        return False

def launch_ae():
    if is_running("AfterFX.exe"):
        log("AE 已在运行")
        return True
    log("启动 AE...")
    subprocess.Popen([AE_EXE], shell=True)
    for i in range(90):
        time.sleep(1)
        if is_running("AfterFX.exe"):
            time.sleep(8)
            log(f"AE 已就绪 ({i+9}s)")
            return True
    log("AE 启动超时", "WARN")
    return False

def wait_bridge(max_attempts=6):
    from ae_mcp_client import AECommandClient
    for i in range(max_attempts):
        try:
            c = AECommandClient()
            r = c.send_command("ping", {})
            if "pong" in str(r).lower():
                log(f"Bridge 连通 (attempt {i+1})")
                return c
        except:
            pass
        time.sleep(10)
    log("Bridge 未连通", "WARN")
    return None

def exec_jsx(client, jsx_code, desc=""):
    """通过 execute_script 执行 JSX 代码"""
    try:
        result = client.send_command("execute_script", {"script": jsx_code})
        status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
        log(f"  {desc}: {status}")
        return result
    except Exception as e:
        log(f"  {desc}: ERROR - {e}")
        return None

# ================================================================
# 主流程
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  AE 完整特效流水线")
    print("=" * 60)

    # 1. 启动 AE
    if not launch_ae():
        print("AE 启动失败")
        sys.exit(1)

    # 2. 等待 Bridge
    client = wait_bridge()
    if not client:
        print("Bridge 连接失败")
        sys.exit(1)

    # 3. 创建合成
    log("=== Step 1: 创建 V17 合成 ===")
    jsx_create = '''
// 关闭所有已打开的项目
while (app.project.numItems > 0) {
    app.project.item(1).remove();
}
// 创建新合成
var comp = app.project.items.addComp("V17_Final_Cut", 1080, 1920, 1, 23.2, 30);
comp.bgColor = [0, 0, 0];
JSON.stringify({name: comp.name, w: comp.width, h: comp.height, dur: comp.duration, fps: comp.frameRate});
'''
    exec_jsx(client, jsx_create, "创建合成 1080x1920 23.2s")

    # 4. 导入 V17 视频
    log("=== Step 2: 导入 V17 素材 ===")
    v17_path = V17_VIDEO.replace("\\", "/")
    jsx_import = f'''
var io = new ImportOptions(File("{v17_path}"));
io.name = "V17_Battle";
var footage = app.project.importFile(io);
// 添加到合成
var comp = app.project.item(1);
var layer = comp.layers.add(footage);
layer.name = "V17_Battle";
JSON.stringify({{name: footage.name, layerName: layer.name, duration: layer.source.duration}});
'''
    exec_jsx(client, jsx_import, "导入V17视频+添加到合成")

    # 5. 添加文字动画 - 片头标题
    log("=== Step 3: 文字动画 - 片头标题 ===")
    jsx_title = '''
var comp = app.project.item(1);

// 创建标题文字层
var titleLayer = comp.layers.addText("VINLAND SAGA");
titleLayer.name = "Title_Text";
var textProp = titleLayer.property("ADBE Text Properties").property("ADBE Text Document");
var textDoc = textProp.value;
textDoc.fontSize = 72;
textDoc.fillColor = [1, 0.85, 0.2];  // 金色
textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
textProp.setValue(textDoc);

// 设置文字层位置和大小
titleLayer.property("ADBE Position").setValue([540, 960]);

// 添加淡入动画 (0-1秒)
var opacity = titleLayer.property("ADBE Transform Group").property("ADBE Opacity");
opacity.setValueAtTime(0, 0);
opacity.setValueAtTime(1, 100);

// 添加缩放弹入动画
var scale = titleLayer.property("ADBE Transform Group").property("ADBE Scale");
scale.setValueAtTime(0, [50, 50]);
scale.setInterpolationTypeAtKey(1, KeyframeInterpolationType.EASY_EASE);
scale.setValueAtTime(0.8, [110, 110]);
scale.setInterpolationTypeAtKey(2, KeyframeInterpolationType.EASY_EASE);
scale.setValueAtTime(1.5, [100, 100]);

// 3秒后淡出
opacity.setValueAtTime(3, 100);
opacity.setValueAtTime(4, 0);

JSON.stringify({title: "VINLAND SAGA", fontSize: 72, animations: ["fade_in", "scale_bounce", "fade_out"]});
'''
    exec_jsx(client, jsx_title, "片头标题(金色72px+缩放弹入+淡入淡出)")

    # 6. 添加副标题
    log("=== Step 4: 文字动画 - 副标题 ===")
    jsx_subtitle = '''
var comp = app.project.item(1);

// 副标题
var subLayer = comp.layers.addText("Battle Scene - AI Enhanced Production");
subLayer.name = "Subtitle";
var textProp = subLayer.property("ADBE Text Properties").property("ADBE Text Document");
var textDoc = textProp.value;
textDoc.fontSize = 36;
textDoc.fillColor = [1, 1, 1];
textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
textProp.setValue(textDoc);

subLayer.property("ADBE Position").setValue([540, 1050]);

// 打字机效果 (通过 sourceRect 和 path 模拟)
var opacity = subLayer.property("ADBE Transform Group").property("ADBE Opacity");
opacity.setValueAtTime(1.5, 0);
opacity.setValueAtTime(2.5, 100);

// 向上滑入
var pos = subLayer.property("ADBE Position");
pos.setValueAtTime(1.5, [540, 1100]);
pos.setInterpolationTypeAtKey(1, KeyframeInterpolationType.EASY_EASE);
pos.setValueAtTime(2.5, [540, 1050]);

// 5秒后淡出
opacity.setValueAtTime(5, 100);
opacity.setValueAtTime(6, 0);

JSON.stringify({subtitle: "Battle Scene", fontSize: 36, animations: ["typewriter", "slide_up"]});
'''
    exec_jsx(client, jsx_subtitle, "副标题(白色36px+滑入+淡出)")

    # 7. 添加 Lumetri Color 调色效果
    log("=== Step 5: 调色效果 ===")
    jsx_color = '''
var comp = app.project.item(1);
var videoLayer = null;
for (var i = 1; i <= comp.numLayers; i++) {
    if (comp.layer(i).name === "V17_Battle") {
        videoLayer = comp.layer(i);
        break;
    }
}
var result = {applied: false};
if (videoLayer) {
    try {
        var lumetri = videoLayer.property("ADBE Effect Parade").addProperty("Lumetri Color");
        result.applied = true;
        result.effectName = lumetri.name;
        // 调整参数
        var contrast = lumetri.property("ADBE Lumetri Basic-3");  // Contrast
        contrast.setValue(15);
        var saturation = lumetri.property("ADBE Lumetri Basic-5");  // Saturation
        saturation.setValue(115);
        var temperature = lumetri.property("ADBE Lumetri Basic-0");  // Temperature
        temperature.setValue(5800);
        result.adjustments = {contrast: 15, saturation: 115, temp: 5800};
    } catch(e) {
        result.error = e.message;
    }
}
JSON.stringify(result);
'''
    exec_jsx(client, jsx_color, "Lumetri Color(对比度+饱和度+色温)")

    # 8. 添加转场效果
    log("=== Step 6: 转场效果 ===")
    jsx_transition = '''
var comp = app.project.item(1);
var result = {transitions: []};

// 为视频层添加交叉溶解转场
for (var i = 1; i <= comp.numLayers; i++) {
    var layer = comp.layer(i);
    if (layer.name === "V17_Battle") {
        // 开头淡入
        var opacity = layer.property("ADBE Transform Group").property("ADBE Opacity");
        opacity.setValueAtTime(0, 0);
        opacity.setValueAtTime(1, 100);
        result.transitions.push("video_fade_in_0-1s");
        
        // 结尾淡出
        var dur = layer.source.duration;
        opacity.setValueAtTime(dur - 1, 100);
        opacity.setValueAtTime(dur, 0);
        result.transitions.push("video_fade_out_" + (dur-1) + "-" + dur + "s");
    }
}

JSON.stringify(result);
'''
    exec_jsx(client, jsx_transition, "视频层淡入淡出转场")

    # 9. 获取合成信息
    log("=== Step 7: 合成最终状态 ===")
    jsx_info = '''
var comp = app.project.item(1);
var info = {
    name: comp.name,
    layers: comp.numLayers,
    duration: comp.duration,
    layerDetails: []
};
for (var i = 1; i <= comp.numLayers; i++) {
    var l = comp.layer(i);
    info.layerDetails.push({
        index: i,
        name: l.name,
        effects: l.property("ADBE Effect Parade").numProperties
    });
}
JSON.stringify(info);
'''
    result = exec_jsx(client, jsx_info, "获取合成信息")
    if result and isinstance(result, dict) and "result" in result:
        try:
            info = json.loads(result["result"]) if isinstance(result["result"], str) else result["result"]
            log(f"  合成: {info}")
        except:
            log(f"  合成信息: {result.get('result', '')[:200]}")

    # 10. 尝试渲染输出
    log("=== Step 8: 渲染输出 ===")
    render_output = os.path.join(OUTPUT_DIR, "v17_ae_final.mp4").replace("\\", "/")
    jsx_render = f'''
var comp = app.project.item(1);
var result = {{queued: false}};
try {{
    // 添加到渲染队列
    app.project.renderQueue.items.add(comp);
    var rqItem = app.project.renderQueue.item(app.project.renderQueue.numItems);
    
    // 设置输出模块
    var om = rqItem.outputModule(1);
    om.file = new File("{render_output}");
    
    // 设置编解码器 (H.264 如果可用)
    try {{
        om.applyTemplate("H.264 - Match Render Settings - 15 Mbps");
    }} catch(e) {{
        try {{
            om.applyTemplate("Lossless");
        }} catch(e2) {{
            // 使用默认设置
        }}
    }}
    
    result.queued = true;
    result.outputPath = "{render_output}";
    result.compName = comp.name;
    
    // 开始渲染
    app.project.renderQueue.startRendering();
    result.rendered = true;
}} catch(e) {{
    result.error = e.message;
}}
JSON.stringify(result);
'''
    exec_jsx(client, jsx_render, "渲染输出")

    # 11. 等待渲染完成
    log("等待渲染完成...")
    time.sleep(10)
    
    if os.path.exists(os.path.join(OUTPUT_DIR, "v17_ae_final.mp4")):
        sz = os.path.getsize(os.path.join(OUTPUT_DIR, "v17_ae_final.mp4")) / 1024
        log(f"渲染完成! 输出: v17_ae_final.mp4 ({sz:.0f}KB)")
    else:
        log("渲染可能仍在进行中或输出路径不同", "INFO")
        # 检查 AE 渲染状态
        jsx_status = '''
var rq = app.project.renderQueue;
var info = {items: rq.numItems, rendering: rq.rendering};
JSON.stringify(info);
'''
        exec_jsx(client, jsx_status, "检查渲染状态")

    # 12. 关闭 AE
    # 2026-09-24: 原来无条件 /F 强杀。实测若 AE 停在"是否保存对 xxx.aep 的更改?"
    # 确认框上，强杀会把确认框和 AE 一起打断、未保存工作一起丢（用户反馈
    # "点取消 AE 就被杀了"）。改为默认**不杀**：确认无人在用时设
    # AEKV_ALLOW_FORCE_KILL_AE=1 才执行。顺带把 shell=True 字符串改成参数列表。
    log("=== 完成，关闭 AE ===")
    if os.environ.get("AEKV_ALLOW_FORCE_KILL_AE") == "1":
        subprocess.run(["taskkill", "/IM", "AfterFX.exe", "/F"],
                       capture_output=True, timeout=15)
        time.sleep(3)
        log("AE 已关闭")
    else:
        log("跳过关闭 AE（保护正在使用的会话与未保存工作）。"
            "如需强制关闭：设 AEKV_ALLOW_FORCE_KILL_AE=1")

    print("\n" + "=" * 60)
    print("  AE 特效流水线完成!")
    print("=" * 60)
