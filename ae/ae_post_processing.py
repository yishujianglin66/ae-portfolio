"""AE后期合成脚本 - 参考视频风格三渲二后期处理.

根据视觉模型深度分析，参考视频的AE后期流程：
1. Color Grading（冷色调分级）
2. 眼睛辉光效果（Glow + Radial Blur）
3. 胶片颗粒叠加
4. 线条增强（Find Edges + Stroke）
5. 转场动画（Vignette扩散）
6. 文字动画

使用方式：在AE中打开项目后运行此脚本，或通过puppet-automation调用
"""
import sys
import os
from pathlib import Path

def run_ae_post_processing(project_path, render_dir, output_path):
    """
    在AE中执行后期合成处理
    
    Args:
        project_path: AE项目文件路径
        render_dir: Blender渲染帧目录
        output_path: 最终输出视频路径
    """
    render_dir_clean = render_dir.replace('\\', '/')
    output_path_clean = output_path.replace('\\', '/')
    
    ae_script = """
// AE ExtendScript - 参考视频风格后期合成
// 基于视觉模型深度分析结果

(function() {
    var project = app.project;
    
    var compWidth = 1920;
    var compHeight = 1080;
    var frameRate = 24;
    var duration = 15;
    
    var mainComp = project.items.addComp("Main_Comp", compWidth, compHeight, 1, duration, frameRate);
    
    var renderFiles = new Folder("RENDER_DIR_PLACEHOLDER");
    var files = renderFiles.getFiles("frame_*.png");
    files.sort();
    
    if (files.length > 0) {
        var firstFile = files[0];
        var imageSeq = mainComp.layers.addFile(firstFile);
        imageSeq.name = "Beauty_Pass";
        imageSeq.sourceInterpretation = SourceInterpretation.FROM_MEDIA;
    }
    
    var colorGradeLayer = mainComp.layers.addAdjustmentLayer();
    colorGradeLayer.name = "Color_Grading";
    
    var lumetri = colorGradeLayer.Effects.addProperty("Lumetri Color");
    
    try {
        var basicTab = lumetri("Basic");
        basicTab("Temperature").setValue(-15);
        basicTab("Contrast").setValue(15);
        
        var curvesTab = lumetri("Curves");
        var rgbCurve = curvesTab("RGB");
        rgbCurve.setValueAtKey(0, [0, 0.05]);
        rgbCurve.setValueAtKey(1, [1, 1]);
        
        var blueCurve = curvesTab("Blue");
        blueCurve.setValueAtKey(0, [0, 0]);
        blueCurve.setValueAtKey(0.8, [0.8, 0.85]);
        blueCurve.setValueAtKey(1, [1, 1]);
    } catch(e) {
        $.writeln("Lumetri setup failed: " + e);
    }
    
    var hueSat = colorGradeLayer.Effects.addProperty("Hue/Saturation");
    hueSat("Saturation").setValue(-20);
    
    var vignetteLayer = mainComp.layers.addAdjustmentLayer();
    vignetteLayer.name = "Vignette";
    
    var vignette = vignetteLayer.Effects.addProperty("Vignette");
    vignette("Amount").setValue(0.3);
    vignette("Radius").setValue(0.7);
    vignette("Feather").setValue(0.4);
    
    var grainLayer = mainComp.layers.addSolid([0, 0, 0, 0], "Film_Grain", compWidth, compHeight, 1);
    grainLayer.name = "Film_Grain";
    
    var grain = grainLayer.Effects.addProperty("Noise");
    grain("Amount").setValue(5);
    grain("Type").setValue(2);
    
    grainLayer.blendingMode = BlendingMode.OVERLAY;
    grainLayer.opacity.setValue(15);
    
    var glowLayer = mainComp.layers.addAdjustmentLayer();
    glowLayer.name = "Glow_Enhance";
    
    var glow = glowLayer.Effects.addProperty("Glow");
    glow("Glow Radius").setValue(20);
    glow("Glow Intensity").setValue(0.3);
    glow("Glow Colors").setValue(1);
    glow("Color A").setValue([1, 0.2, 0.2]);
    glow("Color B").setValue([1, 0.8, 0.8]);
    
    var contrastLayer = mainComp.layers.addAdjustmentLayer();
    contrastLayer.name = "Contrast_Boost";
    
    var levels = contrastLayer.Effects.addProperty("Levels");
    levels("Input Black").setValue(20);
    levels("Input White").setValue(240);
    levels("Gamma").setValue(0.95);
    
    var sharpenLayer = mainComp.layers.addAdjustmentLayer();
    sharpenLayer.name = "Sharpen";
    
    var unsharp = sharpenLayer.Effects.addProperty("Unsharp Mask");
    unsharp("Amount").setValue(50);
    unsharp("Radius").setValue(0.5);
    unsharp("Threshold").setValue(5);
    
    var fadeLayer = mainComp.layers.addSolid([0, 0, 0], "Fade_To_Black", compWidth, compHeight, 1);
    fadeLayer.name = "Fade_To_Black";
    fadeLayer.startTime = duration - 1;
    
    var fadeOpacity = fadeLayer.property("Opacity");
    fadeOpacity.setValueAtKey(1, 0);
    fadeOpacity.setValueAtKey(25, 100);
    
    var key1 = fadeOpacity.key(1);
    var key2 = fadeOpacity.key(2);
    key1.interpolationType = KeyframeInterpolationType.EASE_OUT;
    key2.interpolationType = KeyframeInterpolationType.EASE_IN;
    
    var textLayer = mainComp.layers.addText("");
    textLayer.name = "Title_Text";
    textLayer.startTime = duration - 2;
    
    var textProp = textLayer.property("Source Text");
    textProp.setValue("3D转2D动画");
    
    var textDoc = textProp.value;
    textDoc.font = "思源黑体 Heavy";
    textDoc.fontSize = 72;
    textDoc.fillColor = [1, 1, 1];
    textDoc.strokeColor = [0, 0, 0];
    textDoc.strokeWidth = 3;
    
    var position = textLayer.property("Position");
    position.setValue([compWidth / 2, compHeight / 2 + 100]);
    
    var textOpacity = textLayer.property("Opacity");
    textOpacity.setValueAtKey(1, 0);
    textOpacity.setValueAtKey(30, 100);
    
    var renderQueue = app.project.renderQueue;
    var renderItem = renderQueue.items.add(mainComp);
    
    var outputModule = renderItem.outputModule(1);
    outputModule.file = new File("OUTPUT_PATH_PLACEHOLDER");
    outputModule.format = app.outputModuleFormat("H.264");
    
    $.writeln("AE后期合成项目已创建完成");
    $.writeln("合成名称: " + mainComp.name);
    $.writeln("图层数量: " + mainComp.numLayers);
})();
""".replace("RENDER_DIR_PLACEHOLDER", render_dir_clean).replace("OUTPUT_PATH_PLACEHOLDER", output_path_clean)
    
    return ae_script

if __name__ == "__main__":
    project_root = Path(__file__).parent
    render_dir = project_root / "output_director" / "reference_style_test" / "frames"
    output_dir = project_root / "output_director" / "reference_style_final"
    output_dir.mkdir(exist_ok=True)
    
    ae_project_path = output_dir / "reference_style_composition.aep"
    output_video_path = output_dir / "reference_style_final.mp4"
    
    script_content = run_ae_post_processing(
        str(ae_project_path),
        str(render_dir),
        str(output_video_path)
    )
    
    script_file = output_dir / "post_processing.jsx"
    script_file.write_text(script_content, encoding="utf-8")
    
    print(f"AE脚本已创建: {script_file}")
    print(f"AE项目路径: {ae_project_path}")
    print(f"输出视频路径: {output_video_path}")
    print(f"渲染帧目录: {render_dir}")
    
    print("\n下一步操作:")
    print("1. 打开 After Effects")
    print("2. 创建新项目")
    print("3. 运行脚本: File > Scripts > Run Script File...")
    print("4. 或通过 puppet-automation 的 AE Engine 调用")
