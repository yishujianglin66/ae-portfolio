/*
 ============================================================================
 AE 2026 效果参数真机验证脚本
 ============================================================================
 功能：
 1. 自动创建测试合成和图层
 2. 逐个应用知识图谱中的效果
 3. 验证效果参数名称、类型、默认值
 4. 生成验证报告
 
 使用方法：
 - 在 After Effects 2026 中通过 File > Scripts > Run Script File... 运行此脚本
 - 脚本运行完成后，会在项目面板生成 "Validation_Report" 合成
 - 同时会输出详细日志到 AE 的 Info 面板
 ============================================================================
*/

// ============================================================================
// 效果参数定义 - 与 Python 知识图谱保持一致
// ============================================================================
var EFFECT_DEFINITIONS = [
    // ========================================================================
    // 模糊与锐化类 (blur_sharpen)
    // ========================================================================
    {
        matchName: "ADBE Gaussian Blur 2",
        displayName: "Gaussian Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Blurriness", type: "number", defaultValue: 10.0 },
            { name: "Blur Dimensions", type: "enum" },
            { name: "Repeat Edge Pixels", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Fast Box Blur",
        displayName: "Fast Box Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Blur Radius", type: "number", defaultValue: 10.0 },
            { name: "Blur Dimensions", type: "enum" },
            { name: "Repeat Edge Pixels", type: "boolean" },
            { name: "Blur Quality", type: "number" }
        ]
    },
    {
        matchName: "ADBE Camera Lens Blur",
        displayName: "Camera Lens Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Blur Amount", type: "number", defaultValue: 20.0 }
        ]
    },
    {
        matchName: "ADBE Directional Blur",
        displayName: "Directional Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Direction", type: "number", defaultValue: 0.0 },
            { name: "Blur Length", type: "number", defaultValue: 20.0 }
        ]
    },
    {
        matchName: "ADBE Radial Blur",
        displayName: "Radial Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: 10.0 },
            { name: "Center", type: "point" },
            { name: "Type", type: "enum" },
            { name: "Antialiasing", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Bilateral Blur",
        displayName: "Bilateral Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 10.0 },
            { name: "Threshold", type: "number", defaultValue: 50.0 },
            { name: "Colorize", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Channel Blur",
        displayName: "Channel Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Red Blurriness", type: "number", defaultValue: 0.0 },
            { name: "Green Blurriness", type: "number", defaultValue: 0.0 },
            { name: "Blue Blurriness", type: "number", defaultValue: 0.0 },
            { name: "Alpha Blurriness", type: "number", defaultValue: 0.0 },
            { name: "Blur Dimensions", type: "enum" },
            { name: "Repeat Edge Pixels", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Unsharp Mask",
        displayName: "Unsharp Mask",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: 50.0 },
            { name: "Radius", type: "number", defaultValue: 1.0 },
            { name: "Threshold", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "CC Radial Blur",
        displayName: "CC Radial Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Type", type: "enum" },
            { name: "Amount", type: "number", defaultValue: 30.0 },
            { name: "Quality", type: "number", defaultValue: 3.0 },
            { name: "Center", type: "point" }
        ]
    },
    {
        matchName: "CC Vector Blur",
        displayName: "CC Vector Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Type", type: "enum" },
            { name: "Amount", type: "number", defaultValue: 15.0 },
            { name: "Angle Offset", type: "number", defaultValue: 0.0 },
            { name: "Revolutions", type: "number", defaultValue: 1.0 },
            { name: "Vector Map", type: "enum" },
            { name: "Vector Property", type: "enum" },
            { name: "Softness", type: "number", defaultValue: 10.0 }
        ]
    },
    
    // ========================================================================
    // 颜色校正类 (color_correction)
    // ========================================================================
    {
        matchName: "ADBE Brightness & Contrast 2",
        displayName: "Brightness & Contrast",
        category: "color_correction",
        expectedParams: [
            { name: "Brightness", type: "number", defaultValue: 0.0 },
            { name: "Contrast", type: "number", defaultValue: 0.0 },
            { name: "Use Legacy", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE HUE SATURATION",
        displayName: "Hue/Saturation",
        category: "color_correction",
        expectedParams: [
            { name: "Channel Control", type: "enum" },
            { name: "Master Hue", type: "number", defaultValue: 0.0 },
            { name: "Master Saturation", type: "number", defaultValue: 0.0 },
            { name: "Master Lightness", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Color Balance",
        displayName: "Color Balance",
        category: "color_correction",
        expectedParams: [
            { name: "Shadow Red Balance", type: "number", defaultValue: 0.0 },
            { name: "Shadow Green Balance", type: "number", defaultValue: 0.0 },
            { name: "Shadow Blue Balance", type: "number", defaultValue: 0.0 },
            { name: "Midtone Red Balance", type: "number", defaultValue: 0.0 },
            { name: "Midtone Green Balance", type: "number", defaultValue: 0.0 },
            { name: "Midtone Blue Balance", type: "number", defaultValue: 0.0 },
            { name: "Hilight Red Balance", type: "number", defaultValue: 0.0 },
            { name: "Hilight Green Balance", type: "number", defaultValue: 0.0 },
            { name: "Hilight Blue Balance", type: "number", defaultValue: 0.0 },
            { name: "Preserve Luminosity", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Protractor2",
        displayName: "Curves",
        category: "color_correction",
        expectedParams: [
            { name: "Channel", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Black & White",
        displayName: "Black & White",
        category: "color_correction",
        expectedParams: [
            { name: "Red", type: "number", defaultValue: 40.0 },
            { name: "Yellow", type: "number", defaultValue: 60.0 },
            { name: "Green", type: "number", defaultValue: 30.0 },
            { name: "Cyan", type: "number", defaultValue: 60.0 },
            { name: "Blue", type: "number", defaultValue: 20.0 },
            { name: "Magenta", type: "number", defaultValue: 80.0 },
            { name: "Tint", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Photo Filter",
        displayName: "Photo Filter",
        category: "color_correction",
        expectedParams: [
            { name: "Filter", type: "enum" },
            { name: "Density", type: "number", defaultValue: 25.0 },
            { name: "Preserve Luminosity", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Levels",
        displayName: "Levels",
        category: "color_correction",
        expectedParams: [
            { name: "Channel", type: "enum" },
            { name: "Input Black", type: "number", defaultValue: 0.0 },
            { name: "Input White", type: "number", defaultValue: 255.0 },
            { name: "Gamma", type: "number", defaultValue: 1.0 },
            { name: "Output Black", type: "number", defaultValue: 0.0 },
            { name: "Output White", type: "number", defaultValue: 255.0 }
        ]
    },
    {
        matchName: "ADBE Colorama",
        displayName: "Colorama",
        category: "color_correction",
        expectedParams: [
            { name: "Output Cycle", type: "enum" },
            { name: "Cycle Repetitions", type: "number", defaultValue: 1.0 },
            { name: "Input Phase", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Change Color",
        displayName: "Change Color",
        category: "color_correction",
        expectedParams: [
            { name: "View", type: "enum" },
            { name: "Hue Transform", type: "number", defaultValue: 0.0 },
            { name: "Lightness Transform", type: "number", defaultValue: 0.0 },
            { name: "Saturation Transform", type: "number", defaultValue: 0.0 },
            { name: "Color To Change", type: "color" },
            { name: "Matching Tolerance", type: "number" }
        ]
    },
    {
        matchName: "ADBE Tritone",
        displayName: "Tritone",
        category: "color_correction",
        expectedParams: [
            { name: "Highlights", type: "color" },
            { name: "Midtones", type: "color" },
            { name: "Shadows", type: "color" },
            { name: "Blend With Original", type: "number", defaultValue: 0.0 }
        ]
    },
    
    // ========================================================================
    // 发光与灯光类 (glow_light)
    // ========================================================================
    {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        category: "glow_light",
        expectedParams: [
            { name: "Glow Based On", type: "enum" },
            { name: "Glow Threshold", type: "number", defaultValue: 75.0 },
            { name: "Glow Radius", type: "number", defaultValue: 20.0 },
            { name: "Glow Intensity", type: "number", defaultValue: 2.0 },
            { name: "Composite Original", type: "enum" },
            { name: "Glow Operation", type: "enum" },
            { name: "Glow Colors", type: "enum" },
            { name: "Color Looping", type: "enum" }
        ]
    },
    {
        matchName: "CC Light Rays",
        displayName: "CC Light Rays",
        category: "glow_light",
        expectedParams: [
            { name: "Intensity", type: "number", defaultValue: 120.0 },
            { name: "Radius", type: "number", defaultValue: 80.0 },
            { name: "Center", type: "point" },
            { name: "Color", type: "color" },
            { name: "Period", type: "number", defaultValue: 5.0 },
            { name: "Shape", type: "enum" }
        ]
    },
    {
        matchName: "CC Light Sweep",
        displayName: "CC Light Sweep",
        category: "glow_light",
        expectedParams: [
            { name: "Center", type: "point" },
            { name: "Direction", type: "number", defaultValue: 0.0 },
            { name: "Shape", type: "enum" },
            { name: "Width", type: "number", defaultValue: 50.0 },
            { name: "Sweep Intensity", type: "number", defaultValue: 100.0 },
            { name: "Edge Intensity", type: "number", defaultValue: 50.0 },
            { name: "Edge Thickness", type: "number", defaultValue: 3.0 }
        ]
    },
    {
        matchName: "CC Light Burst 2.5",
        displayName: "CC Light Burst 2.5",
        category: "glow_light",
        expectedParams: [
            { name: "Center", type: "point" },
            { name: "Intensity", type: "number", defaultValue: 120.0 },
            { name: "Burst", type: "number", defaultValue: 2.0 },
            { name: "Speed", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Lens Flare",
        displayName: "Lens Flare",
        category: "glow_light",
        expectedParams: [
            { name: "Flare Center", type: "point" },
            { name: "Flare Brightness", type: "number", defaultValue: 100.0 },
            { name: "Lens Type", type: "enum" },
            { name: "Blend With Original", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Shine",
        displayName: "Shine",
        category: "glow_light",
        expectedParams: [
            { name: "Source Point", type: "point" },
            { name: "Ray Length", type: "number", defaultValue: 3.0 },
            { name: "Shimmer", type: "number", defaultValue: 300.0 },
            { name: "Boost Light", type: "number", defaultValue: 1.0 },
            { name: "Colorize", type: "enum" }
        ]
    },
    {
        matchName: "CC Glow",
        displayName: "CC Glow",
        category: "glow_light",
        expectedParams: [
            { name: "Glow Radius", type: "number", defaultValue: 15.0 },
            { name: "Glow Brightness", type: "number", defaultValue: 80.0 },
            { name: "Glow Colors", type: "enum" },
            { name: "Glow Shape", type: "enum" }
        ]
    },
    
    // ========================================================================
    // 扭曲类 (distort)
    // ========================================================================
    {
        matchName: "ADBE Wave Warp",
        displayName: "Wave Warp",
        category: "distort",
        expectedParams: [
            { name: "Wave Type", type: "enum" },
            { name: "Wave Height", type: "number", defaultValue: 25.0 },
            { name: "Wave Width", type: "number", defaultValue: 80.0 },
            { name: "Direction", type: "number", defaultValue: 0.0 },
            { name: "Wave Speed", type: "number", defaultValue: 2.0 },
            { name: "Pinning", type: "enum" },
            { name: "Phase", type: "number", defaultValue: 0.0 },
            { name: "Antialiasing", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Bulge",
        displayName: "Bulge",
        category: "distort",
        expectedParams: [
            { name: "Horizontal Radius", type: "number", defaultValue: 50.0 },
            { name: "Vertical Radius", type: "number", defaultValue: 50.0 },
            { name: "Bulge Center", type: "point" },
            { name: "Bulge Height", type: "number", defaultValue: 50.0 },
            { name: "Taper Radius", type: "number", defaultValue: 1.0 },
            { name: "Antialiasing", type: "enum" },
            { name: "Pinning", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Displacement Map",
        displayName: "Displacement Map",
        category: "distort",
        expectedParams: [
            { name: "Displacement Map Layer", type: "enum" },
            { name: "Use For Horizontal Displacement", type: "enum" },
            { name: "Max Horizontal Displacement", type: "number", defaultValue: 10.0 },
            { name: "Use For Vertical Displacement", type: "enum" },
            { name: "Max Vertical Displacement", type: "number", defaultValue: 10.0 },
            { name: "Displacement Map Behavior", type: "enum" },
            { name: "Edge Behavior", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Turbulent Displace",
        displayName: "Turbulent Displace",
        category: "distort",
        expectedParams: [
            { name: "Displacement", type: "enum" },
            { name: "Amount", type: "number", defaultValue: 30.0 },
            { name: "Size", type: "number", defaultValue: 40.0 },
            { name: "Offset", type: "point" },
            { name: "Complexity", type: "number", defaultValue: 5.0 },
            { name: "Evolution", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Liquify",
        displayName: "Liquify",
        category: "distort",
        expectedParams: [
            { name: "Tools", type: "enum" },
            { name: "Brush Size", type: "number", defaultValue: 100.0 },
            { name: "Brush Pressure", type: "number", defaultValue: 50.0 },
            { name: "Distortion Percentage", type: "number", defaultValue: 100.0 }
        ]
    },
    {
        matchName: "ADBE Mesh Warp",
        displayName: "Mesh Warp",
        category: "distort",
        expectedParams: [
            { name: "Rows", type: "number", defaultValue: 7.0 },
            { name: "Columns", type: "number", defaultValue: 7.0 },
            { name: "Quality", type: "number", defaultValue: 1.0 },
            { name: "Distortion Mesh", type: "number" }
        ]
    },
    {
        matchName: "CC Bend It",
        displayName: "CC Bend It",
        category: "distort",
        expectedParams: [
            { name: "Start Point", type: "point" },
            { name: "End Point", type: "point" },
            { name: "Bend", type: "number", defaultValue: 50.0 },
            { name: "Distortion", type: "number", defaultValue: 20.0 },
            { name: "Render Prestart", type: "enum" }
        ]
    },
    {
        matchName: "CC Page Turn",
        displayName: "CC Page Turn",
        category: "distort",
        expectedParams: [
            { name: "Controls", type: "enum" },
            { name: "Fold Position", type: "point" },
            { name: "Fold Direction", type: "number", defaultValue: 60.0 },
            { name: "Fold Radius", type: "number", defaultValue: 0.5 },
            { name: "Render", type: "enum" }
        ]
    },
    {
        matchName: "CC Ripple Pulse",
        displayName: "CC Ripple Pulse",
        category: "distort",
        expectedParams: [
            { name: "Intensity", type: "number", defaultValue: 50.0 },
            { name: "Center", type: "point" },
            { name: "Time Span", type: "number", defaultValue: 1.0 },
            { name: "Pulse Level", type: "number", defaultValue: 100.0 }
        ]
    },
    
    // ========================================================================
    // 噪波与颗粒类 (noise_grain)
    // ========================================================================
    {
        matchName: "ADBE Noise",
        displayName: "Noise",
        category: "noise_grain",
        expectedParams: [
            { name: "Amount of Noise", type: "number", defaultValue: 10.0 },
            { name: "Noise Type", type: "enum" },
            { name: "Clip Result Values", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Fractal Noise",
        displayName: "Fractal Noise",
        category: "noise_grain",
        expectedParams: [
            { name: "Fractal Type", type: "enum" },
            { name: "Noise Type", type: "enum" },
            { name: "Invert", type: "boolean" },
            { name: "Contrast", type: "number", defaultValue: 100.0 },
            { name: "Brightness", type: "number", defaultValue: 0.0 },
            { name: "Overflow", type: "enum" },
            { name: "Transform", type: "number" },
            { name: "Complexity", type: "number", defaultValue: 5.0 }
        ]
    },
    {
        matchName: "ADBE Turbulent Noise",
        displayName: "Turbulent Noise",
        category: "noise_grain",
        expectedParams: [
            { name: "Fractal Type", type: "enum" },
            { name: "Noise Type", type: "enum" },
            { name: "Invert", type: "boolean" },
            { name: "Contrast", type: "number", defaultValue: 100.0 },
            { name: "Brightness", type: "number", defaultValue: 0.0 },
            { name: "Complexity", type: "number", defaultValue: 5.0 }
        ]
    },
    {
        matchName: "ADBE Remove Grain",
        displayName: "Remove Grain",
        category: "noise_grain",
        expectedParams: [
            { name: "Viewing Mode", type: "enum" },
            { name: "Preview Region", type: "number" },
            { name: "Noise Reduction Settings", type: "number" },
            { name: "Fine Tuning", type: "number" },
            { name: "Temporal Filtering", type: "number" }
        ]
    },
    {
        matchName: "ADBE Match Grain",
        displayName: "Match Grain",
        category: "noise_grain",
        expectedParams: [
            { name: "Viewing Mode", type: "enum" },
            { name: "Noise Source Layer", type: "enum" },
            { name: "Compensate for Existing Noise", type: "number", defaultValue: 100.0 }
        ]
    },
    {
        matchName: "ADBE Add Grain",
        displayName: "Add Grain",
        category: "noise_grain",
        expectedParams: [
            { name: "Viewing Mode", type: "enum" },
            { name: "Preset", type: "enum" },
            { name: "Intensity", type: "number", defaultValue: 50.0 },
            { name: "Size", type: "number", defaultValue: 1.0 },
            { name: "Softness", type: "number", defaultValue: 0.5 }
        ]
    },
    
    // ========================================================================
    // 通道与键控类 (channel_keying)
    // ========================================================================
    {
        matchName: "ADBE Color Key",
        displayName: "Color Key",
        category: "channel_keying",
        expectedParams: [
            { name: "Key Color", type: "color" },
            { name: "Color Tolerance", type: "number", defaultValue: 0.0 },
            { name: "Edge Thin", type: "number", defaultValue: 0.0 },
            { name: "Edge Feather", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Luma Key",
        displayName: "Luma Key",
        category: "channel_keying",
        expectedParams: [
            { name: "Key Type", type: "enum" },
            { name: "Threshold", type: "number", defaultValue: 0.0 },
            { name: "Tolerance", type: "number", defaultValue: 0.0 },
            { name: "Edge Thin", type: "number", defaultValue: 0.0 },
            { name: "Edge Feather", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Keylight",
        displayName: "Keylight (1.2)",
        category: "channel_keying",
        expectedParams: [
            { name: "Screen Colour", type: "color" },
            { name: "Screen Gain", type: "number", defaultValue: 1.0 },
            { name: "Screen Balance", type: "number", defaultValue: 0.5 },
            { name: "Despill Bias", type: "color" },
            { name: "Alpha Bias", type: "color" },
            { name: "Screen Pre-blur", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Set Channels",
        displayName: "Set Channels",
        category: "channel_keying",
        expectedParams: [
            { name: "Source Layer", type: "enum" },
            { name: "Red Channel", type: "enum" },
            { name: "Green Channel", type: "enum" },
            { name: "Blue Channel", type: "enum" },
            { name: "Alpha Channel", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Shift Channels",
        displayName: "Shift Channels",
        category: "channel_keying",
        expectedParams: [
            { name: "Take Red From", type: "enum" },
            { name: "Take Green From", type: "enum" },
            { name: "Take Blue From", type: "enum" },
            { name: "Take Alpha From", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Minimax",
        displayName: "Minimax",
        category: "channel_keying",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 1.0 },
            { name: "Channel", type: "enum" },
            { name: "Operation", type: "enum" },
            { name: "Direction", type: "enum" },
            { name: "Don't Shrink Edges", type: "boolean" }
        ]
    },
    
    // ========================================================================
    // 风格化类 (stylize)
    // ========================================================================
    {
        matchName: "ADBE Mosaic",
        displayName: "Mosaic",
        category: "stylize",
        expectedParams: [
            { name: "Horizontal Blocks", type: "number", defaultValue: 50.0 },
            { name: "Vertical Blocks", type: "number", defaultValue: 50.0 },
            { name: "Sharp Colors", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Find Edges",
        displayName: "Find Edges",
        category: "stylize",
        expectedParams: [
            { name: "Invert", type: "boolean" },
            { name: "Blend With Original", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "CC Vignette",
        displayName: "CC Vignette",
        category: "stylize",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: -0.5 },
            { name: "Angle", type: "number", defaultValue: 0.0 },
            { name: "Midpoint", type: "number", defaultValue: 0.5 }
        ]
    },
    {
        matchName: "CC Threshold",
        displayName: "CC Threshold",
        category: "stylize",
        expectedParams: [
            { name: "Threshold", type: "number", defaultValue: 50.0 },
            { name: "Invert", type: "boolean" }
        ]
    },
    {
        matchName: "CC Threshold RGB",
        displayName: "CC Threshold RGB",
        category: "stylize",
        expectedParams: [
            { name: "Red", type: "number", defaultValue: 50.0 },
            { name: "Green", type: "number", defaultValue: 50.0 },
            { name: "Blue", type: "number", defaultValue: 50.0 },
            { name: "Invert", type: "boolean" }
        ]
    },
    {
        matchName: "ADBE Roughen Edges",
        displayName: "Roughen Edges",
        category: "stylize",
        expectedParams: [
            { name: "Edge Type", type: "enum" },
            { name: "Edge Color", type: "color" },
            { name: "Border", type: "number", defaultValue: 5.0 },
            { name: "Edge Sharpness", type: "number", defaultValue: 0.5 },
            { name: "Fractal Influence", type: "number", defaultValue: 50.0 },
            { name: "Scale", type: "number", defaultValue: 100.0 },
            { name: "Stretch Width or Height", type: "number", defaultValue: 1.0 },
            { name: "Offset (Turbulence)", type: "point" },
            { name: "Complexity", type: "number", defaultValue: 3.0 },
            { name: "Evolution", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Stylize Motion Tile",
        displayName: "Motion Tile",
        category: "stylize",
        expectedParams: [
            { name: "Tile Center", type: "point" },
            { name: "Tile Width", type: "number", defaultValue: 100.0 },
            { name: "Tile Height", type: "number", defaultValue: 100.0 },
            { name: "Output Width", type: "number", defaultValue: 100.0 },
            { name: "Output Height", type: "number", defaultValue: 100.0 },
            { name: "Mirror Edges", type: "boolean" },
            { name: "Phase", type: "number", defaultValue: 0.0 },
            { name: "Horizontal Phase", type: "boolean" },
            { name: "Vertical Phase", type: "boolean" }
        ]
    },
    {
        matchName: "CC Kaleida",
        displayName: "CC Kaleida",
        category: "stylize",
        expectedParams: [
            { name: "Center", type: "point" },
            { name: "Size", type: "number", defaultValue: 200.0 },
            { name: "Mirroring", type: "number", defaultValue: 20.0 },
            { name: "Rotation", type: "number", defaultValue: 0.0 },
            { name: "Sides", type: "number", defaultValue: 6.0 }
        ]
    },
    
    // ========================================================================
    // 透视与3D类 (perspective_3d)
    // ========================================================================
    {
        matchName: "ADBE Corner Pin",
        displayName: "Corner Pin",
        category: "perspective_3d",
        expectedParams: [
            { name: "Upper Left", type: "point" },
            { name: "Upper Right", type: "point" },
            { name: "Lower Left", type: "point" },
            { name: "Lower Right", type: "point" }
        ]
    },
    {
        matchName: "ADBE Basic 3D",
        displayName: "Basic 3D",
        category: "perspective_3d",
        expectedParams: [
            { name: "Swivel", type: "number", defaultValue: 0.0 },
            { name: "Tilt", type: "number", defaultValue: 0.0 },
            { name: "Distance to Image", type: "number", defaultValue: 0.0 },
            { name: "Specular Highlight", type: "boolean" },
            { name: "Preview", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Bevel Alpha",
        displayName: "Bevel Alpha",
        category: "perspective_3d",
        expectedParams: [
            { name: "Edge Thickness", type: "number", defaultValue: 2.0 },
            { name: "Light Angle", type: "number", defaultValue: -45.0 },
            { name: "Light Color", type: "color" },
            { name: "Light Intensity", type: "number", defaultValue: 0.5 }
        ]
    },
    {
        matchName: "ADBE Drop Shadow",
        displayName: "Drop Shadow",
        category: "perspective_3d",
        expectedParams: [
            { name: "Shadow Color", type: "color" },
            { name: "Opacity", type: "number", defaultValue: 75.0 },
            { name: "Direction", type: "number", defaultValue: 135.0 },
            { name: "Distance", type: "number", defaultValue: 5.0 },
            { name: "Softness", type: "number", defaultValue: 5.0 },
            { name: "Shadow Only", type: "boolean" }
        ]
    },
    {
        matchName: "CC Cylinder",
        displayName: "CC Cylinder",
        category: "perspective_3d",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 50.0 },
            { name: "Position X", type: "number", defaultValue: 0.0 },
            { name: "Position Y", type: "number", defaultValue: 0.0 },
            { name: "Rotate", type: "number", defaultValue: 0.0 },
            { name: "Light Intensity", type: "number", defaultValue: 0.5 },
            { name: "Render", type: "enum" }
        ]
    },
    {
        matchName: "CC Sphere",
        displayName: "CC Sphere",
        category: "perspective_3d",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 100.0 },
            { name: "Offset", type: "point" },
            { name: "Rotation X", type: "number", defaultValue: 0.0 },
            { name: "Rotation Y", type: "number", defaultValue: 0.0 },
            { name: "Rotation Z", type: "number", defaultValue: 0.0 },
            { name: "Light", type: "number" },
            { name: "Render", type: "enum" }
        ]
    },
    
    // ========================================================================
    // 生成与绘制类 (generate_draw)
    // ========================================================================
    {
        matchName: "ADBE Ramp",
        displayName: "Ramp",
        category: "generate_draw",
        expectedParams: [
            { name: "Start of Ramp", type: "point" },
            { name: "Start Color", type: "color" },
            { name: "End of Ramp", type: "point" },
            { name: "End Color", type: "color" },
            { name: "Ramp Shape", type: "enum" },
            { name: "Ramp Scatter", type: "number", defaultValue: 0.0 },
            { name: "Blend With Original", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE 4-Color Gradient",
        displayName: "4-Color Gradient",
        category: "generate_draw",
        expectedParams: [
            { name: "Position 1", type: "point" },
            { name: "Color 1", type: "color" },
            { name: "Position 2", type: "point" },
            { name: "Color 2", type: "color" },
            { name: "Position 3", type: "point" },
            { name: "Color 3", type: "color" },
            { name: "Position 4", type: "point" },
            { name: "Color 4", type: "color" },
            { name: "Blend", type: "number", defaultValue: 30.0 },
            { name: "Jitter", type: "number", defaultValue: 0.0 },
            { name: "Opacity", type: "number", defaultValue: 100.0 },
            { name: "Blending Mode", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Checkerboard",
        displayName: "Checkerboard",
        category: "generate_draw",
        expectedParams: [
            { name: "Anchor", type: "point" },
            { name: "Size From", type: "enum" },
            { name: "Corner", type: "point" },
            { name: "Width", type: "number", defaultValue: 20.0 },
            { name: "Height", type: "number", defaultValue: 20.0 },
            { name: "Feather", type: "number" },
            { name: "Color 1", type: "color" },
            { name: "Color 2", type: "color" },
            { name: "Blend With Original", type: "number", defaultValue: 0.0 }
        ]
    },
    {
        matchName: "ADBE Circle",
        displayName: "Circle",
        category: "generate_draw",
        expectedParams: [
            { name: "Center", type: "point" },
            { name: "Radius", type: "number", defaultValue: 50.0 },
            { name: "Edge", type: "enum" },
            { name: "Feather", type: "number", defaultValue: 0.0 },
            { name: "Invert Circle", type: "boolean" },
            { name: "Color", type: "color" },
            { name: "Opacity", type: "number", defaultValue: 100.0 },
            { name: "Blending Mode", type: "enum" }
        ]
    },
    {
        matchName: "ADBE Grid",
        displayName: "Grid",
        category: "generate_draw",
        expectedParams: [
            { name: "Anchor", type: "point" },
            { name: "Size From", type: "enum" },
            { name: "Corner", type: "point" },
            { name: "Width", type: "number", defaultValue: 20.0 },
            { name: "Height", type: "number", defaultValue: 20.0 },
            { name: "Border", type: "number", defaultValue: 5.0 },
            { name: "Feather", type: "number" },
            { name: "Invert Grid", type: "boolean" },
            { name: "Color", type: "color" },
            { name: "Opacity", type: "number", defaultValue: 100.0 },
            { name: "Blending Mode", type: "enum" }
        ]
    },
    {
        matchName: "CC Glue Gun",
        displayName: "CC Glue Gun",
        category: "generate_draw",
        expectedParams: [
            { name: "Branding", type: "number", defaultValue: 50.0 },
            { name: "Scaling", type: "number", defaultValue: 100.0 },
            { name: "Stickiness", type: "number", defaultValue: 80.0 },
            { name: "Tendril", type: "number", defaultValue: 20.0 }
        ]
    },
    {
        matchName: "CC Light Wipe",
        displayName: "CC Light Wipe",
        category: "generate_draw",
        expectedParams: [
            { name: "Transition Completion", type: "number", defaultValue: 0.0 },
            { name: "Direction", type: "number", defaultValue: 90.0 },
            { name: "Shape", type: "enum" },
            { name: "Softness", type: "number", defaultValue: 30.0 },
            { name: "Intensity", type: "number", defaultValue: 200.0 },
            { name: "Color", type: "color" }
        ]
    }
];

// ============================================================================
// 验证结果统计
// ============================================================================
var validationResults = {
    totalEffects: EFFECT_DEFINITIONS.length,
    passedEffects: 0,
    failedEffects: 0,
    missingEffects: [],
    paramErrors: [],
    testTime: ""
};

// ============================================================================
// 工具函数
// ============================================================================

function log(message) {
    $.writeln("[AE Validation] " + message);
}

function getAEVersion() {
    return app.version;
}

function getParamType(param) {
    if (param.typeName === "ADBE Slider Control" || param.typeName === "Slider") {
        return "number";
    } else if (param.typeName === "ADBE Angle Control" || param.typeName === "Angle") {
        return "number";
    }
    if (param instanceof LightPropertyGroup) return "light";
    if (param instanceof CameraPropertyGroup) return "camera";
    if (param.propertyValueType === PropertyValueType.TwoD) return "point";
    if (param.propertyValueType === PropertyValueType.ThreeD) return "point3d";
    if (param.propertyValueType === PropertyValueType.Color) return "color";
    if (param.propertyValueType === PropertyValueType.CUSTOM_VALUE) {
        try {
            var val = param.value;
            if (typeof val === "boolean") return "boolean";
            return "enum";
        } catch(e) {}
    }
    if (param.propertyValueType === PropertyValueType.NumValue) return "number";
    try {
        var val = param.value;
        if (typeof val === "number") return "number";
        if (typeof val === "boolean") return "boolean";
        if (typeof val === "string") return "enum";
    } catch(e) {}
    if (param.propertyType === PropertyType.INDEXED_GROUP) return "enum";
    return "unknown";
}

// ============================================================================
// 单个效果验证函数
// ============================================================================

function validateEffect(effectDef, testLayer) {
    var result = {
        matchName: effectDef.matchName,
        displayName: effectDef.displayName,
        category: effectDef.category,
        exists: false,
        paramsMatch: [],
        paramsMissing: [],
        paramsMismatched: [],
        totalParams: 0,
        matchedParams: 0
    };
    
    try {
        var effect = testLayer.effects.addProperty(effectDef.matchName);
        
        if (!effect) {
            validationResults.missingEffects.push(effectDef.matchName);
            log("  ❌ 效果不存在: " + effectDef.matchName + " (" + effectDef.displayName + ")");
            return result;
        }
        
        result.exists = true;
        log("  ✓ 效果存在: " + effectDef.matchName + " (" + effectDef.displayName + ")");
        
        var actualParamCount = effect.numProperties;
        result.totalParams = actualParamCount;
        
        log("    实际参数数量: " + actualParamCount);
        
        for (var i = 1; i <= Math.min(effectDef.expectedParams.length, actualParamCount); i++) {
            try {
                var expectedParam = effectDef.expectedParams[i - 1];
                var actualParam = effect.property(i);
                
                if (!actualParam) {
                    result.paramsMissing.push(expectedParam.name);
                    continue;
                }
                
                var actualName = actualParam.name;
                var actualType = getParamType(actualParam);
                
                var nameMatch = (actualName.toLowerCase() === expectedParam.name.toLowerCase());
                var typeMatch = (actualType === expectedParam.type);
                
                if (nameMatch && typeMatch) {
                    result.matchedParams++;
                    result.paramsMatch.push(expectedParam.name);
                } else if (!nameMatch && typeMatch) {
                    result.paramsMismatched.push({
                        expected: expectedParam.name,
                        actual: actualName,
                        reason: "name_mismatch",
                        type: expectedParam.type
                    });
                    log("    ⚠️  参数名不匹配: 期望 '" + expectedParam.name + "', 实际 '" + actualName + "' (类型: " + actualType + ")");
                } else if (nameMatch && !typeMatch) {
                    result.paramsMismatched.push({
                        expected: expectedParam.name,
                        actual: actualName,
                        reason: "type_mismatch",
                        expectedType: expectedParam.type,
                        actualType: actualType
                    });
                    log("    ⚠️  类型不匹配: '" + expectedParam.name + "', 期望类型: " + expectedParam.type + ", 实际类型: " + actualType);
                }
                
            } catch(e) {
                log("    ⚠️  参数访问错误: 第 " + i + " 个参数 - " + e.message);
            }
        }
        
        testLayer.effects.removeProperty(effectDef.matchName);
        
    } catch(e) {
        log("  ❌ 验证失败: " + effectDef.matchName + " - " + e.message);
        validationResults.missingEffects.push(effectDef.matchName + " (" + e.message + ")");
        return result;
    }
    
    return result;
}

// ============================================================================
// 主验证函数
// ============================================================================

function runValidation() {
    log("========================================");
    log("AE " + getAEVersion() + " 效果参数真机验证");
    log("========================================");
    log("");
    
    var testComp, testLayer;
    
    try {
        var project = app.project;
        testComp = project.items.addComp(
            "Validation_Test_Comp",
            1920, 1080,
            1.0,
            5,
            30
        );
        
        var solidLayer = testComp.layers.addSolid(
            [0.5, 0.5, 0.5],
            "Test_Layer",
            1920, 1080,
            1.0,
            5
        );
        testLayer = solidLayer;
        
        log("已创建测试合成和图层");
        log("");
        
    } catch(e) {
        log("错误: 无法创建测试合成 - " + e.message);
        return;
    }
    
    var categoryResults = {};
    
    for (var i = 0; i < EFFECT_DEFINITIONS.length; i++) {
        var effectDef = EFFECT_DEFINITIONS[i];
        
        log("[" + (i + 1) + "/" + EFFECT_DEFINITIONS.length + "] 验证: " + effectDef.displayName);
        
        var result = validateEffect(effectDef, testLayer);
        
        if (!categoryResults[effectDef.category]) {
            categoryResults[effectDef.category] = {
                total: 0,
                passed: 0,
                failed: 0
            };
        }
        categoryResults[effectDef.category].total++;
        
        if (result.exists && result.matchedParams >= Math.floor(result.totalParams * 0.6)) {
            validationResults.passedEffects++;
            categoryResults[effectDef.category].passed++;
        } else {
            validationResults.failedEffects++;
            categoryResults[effectDef.category].failed++;
        }
        
        log("");
    }
    
    validationResults.testTime = new Date().toString();
    
    log("========================================");
    log("验证结果汇总");
    log("========================================");
    log("总效果数: " + validationResults.totalEffects);
    log("通过: " + validationResults.passedEffects);
    log("失败/不完整: " + validationResults.failedEffects);
    log("通过率: " + Math.round(validationResults.passedEffects / validationResults.totalEffects * 100) + "%");
    log("");
    
    log("分类统计:");
    for (var cat in categoryResults) {
        if (categoryResults.hasOwnProperty(cat)) {
            var catRes = categoryResults[cat];
            log("  " + cat + ": " + catRes.passed + "/" + catRes.total + 
                " (" + Math.round(catRes.passed / catRes.total * 100) + "%)");
        }
    }
    log("");
    
    if (validationResults.missingEffects.length > 0) {
        log("缺失/失败的效果:");
        for (var j = 0; j < validationResults.missingEffects.length; j++) {
            log("  - " + validationResults.missingEffects[j]);
        }
        log("");
    }
    
    log("验证完成时间: " + validationResults.testTime);
    
    try {
        var reportText = "";
        reportText += "AE " + getAEVersion() + " 效果参数验证报告\n";
        reportText += "========================================\n\n";
        reportText += "总效果数: " + validationResults.totalEffects + "\n";
        reportText += "通过: " + validationResults.passedEffects + "\n";
        reportText += "失败: " + validationResults.failedEffects + "\n";
        reportText += "通过率: " + Math.round(validationResults.passedEffects / validationResults.totalEffects * 100) + "%\n";
        reportText += "\n分类统计:\n";
        for (var cat2 in categoryResults) {
            if (categoryResults.hasOwnProperty(cat2)) {
                var cr = categoryResults[cat2];
                reportText += "  " + cat2 + ": " + cr.passed + "/" + cr.total + 
                    " (" + Math.round(cr.passed / cr.total * 100) + "%)\n";
            }
        }
        reportText += "\n验证时间: " + validationResults.testTime + "\n";
        
        var textLayer = testComp.layers.addText("验证报告");
        var textProp = textLayer.property("Source Text");
        textProp.setValue(reportText);
        textLayer.name = "Validation_Report";
        
        log("报告已添加到合成: Validation_Report");
        
    } catch(e) {
        log("生成报告失败: " + e.message);
    }
    
    log("");
    log("验证完成！");
}

// ============================================================================
// 运行验证
// ============================================================================
app.beginUndoGroup("AE Effect Validation");
try {
    runValidation();
} finally {
    app.endUndoGroup();
}
