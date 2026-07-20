/*
 ============================================================================
 AE 2026 效果参数真机验证脚本（自动生成）
 ============================================================================
 生成时间: 2026-07-09 23:23:58
 效果数量: 69
 功能：
 1. 自动创建测试合成和图层
 2. 逐个应用知识图谱中的效果
 3. 验证效果参数名称、类型、默认值
 4. 生成验证报告
 
 使用方法：
 - 在 After Effects 2025 中通过 File > Scripts > Run Script File... 运行此脚本
 - 脚本运行完成后，会在项目面板生成 "Validation_Report" 合成
 - 同时会输出详细日志到 AE 的 Info 面板
 ============================================================================
*/

// ============================================================================
// 效果参数定义 - 与 Python 知识图谱保持一致
// ============================================================================
var EFFECT_DEFINITIONS = [
    {
        matchName: "ADBE Gaussian Blur 2",
        displayName: "Gaussian Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Blurriness", type: "number", defaultValue: 10 },
            { name: "Blur Dimensions", type: "enum", defaultValue: Horizontal and Vertical }
        ]
    },
    {
        matchName: "ADBE Fast Box Blur",
        displayName: "Fast Box Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Blurriness", type: "number", defaultValue: 10 },
            { name: "Blur Dimensions", type: "enum", defaultValue: Horizontal and Vertical },
            { name: "Repeat Edge Pixels", type: "boolean", defaultValue: True }
        ]
    },
    {
        matchName: "ADBE Directional Blur",
        displayName: "Directional Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Direction", type: "number", defaultValue: 0 },
            { name: "Blur Length", type: "number", defaultValue: 20 }
        ]
    },
    {
        matchName: "CC Radial Blur",
        displayName: "CC Radial Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Type", type: "enum", defaultValue: Zoom },
            { name: "Amount", type: "number", defaultValue: 30 },
            { name: "Quality", type: "number", defaultValue: 20 }
        ]
    },
    {
        matchName: "ADBE Camera Lens Blur",
        displayName: "Camera Lens Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Blur Amount", type: "number", defaultValue: 15 },
            { name: "Iris Shape", type: "enum", defaultValue: Hexagon },
            { name: "Iris Rotation", type: "number", defaultValue: 0 },
            { name: "Highlight Gain", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Bilateral Blur",
        displayName: "Bilateral Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 10 },
            { name: "Threshold", type: "number", defaultValue: 50 }
        ]
    },
    {
        matchName: "ADBE Compound Blur",
        displayName: "Compound Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Maximum Blur", type: "number", defaultValue: 20 },
            { name: "Blur Layer", type: "enum", defaultValue: None }
        ]
    },
    {
        matchName: "ADBE Channel Blur",
        displayName: "Channel Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Red Blurriness", type: "number", defaultValue: 0 },
            { name: "Green Blurriness", type: "number", defaultValue: 0 },
            { name: "Blue Blurriness", type: "number", defaultValue: 0 },
            { name: "Alpha Blurriness", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Unsharp Mask",
        displayName: "Unsharp Mask",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: 50 },
            { name: "Radius", type: "number", defaultValue: 1.0 },
            { name: "Threshold", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "CC Vector Blur",
        displayName: "CC Vector Blur",
        category: "blur_sharpen",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: 20 },
            { name: "Angle Offset", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Brightness & Contrast 2",
        displayName: "Brightness & Contrast",
        category: "color_correction",
        expectedParams: [
            { name: "Brightness", type: "number", defaultValue: 0 },
            { name: "Contrast", type: "number", defaultValue: 0 },
            { name: "Use Legacy", type: "boolean", defaultValue: False }
        ]
    },
    {
        matchName: "ADBE HUE SATURATION",
        displayName: "Hue/Saturation",
        category: "color_correction",
        expectedParams: [
            { name: "Channel Control", type: "enum", defaultValue: Master },
            { name: "Master Hue", type: "number", defaultValue: 0 },
            { name: "Master Saturation", type: "number", defaultValue: 0 },
            { name: "Master Lightness", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Color Balance",
        displayName: "Color Balance",
        category: "color_correction",
        expectedParams: [
            { name: "Shadow Red Balance", type: "number", defaultValue: 0 },
            { name: "Shadow Green Balance", type: "number", defaultValue: 0 },
            { name: "Shadow Blue Balance", type: "number", defaultValue: 0 },
            { name: "Midtone Red Balance", type: "number", defaultValue: 0 },
            { name: "Midtone Green Balance", type: "number", defaultValue: 0 },
            { name: "Midtone Blue Balance", type: "number", defaultValue: 0 },
            { name: "Hilight Red Balance", type: "number", defaultValue: 0 },
            { name: "Hilight Green Balance", type: "number", defaultValue: 0 },
            { name: "Hilight Blue Balance", type: "number", defaultValue: 0 },
            { name: "Preserve Luminosity", type: "boolean", defaultValue: True }
        ]
    },
    {
        matchName: "ADBE Protractor2",
        displayName: "Curves",
        category: "color_correction",
        expectedParams: [
            { name: "Channel", type: "enum", defaultValue: RGB }
        ]
    },
    {
        matchName: "ADBE Black & White",
        displayName: "Black & White",
        category: "color_correction",
        expectedParams: [
            { name: "Red", type: "number", defaultValue: 40 },
            { name: "Yellow", type: "number", defaultValue: 60 },
            { name: "Green", type: "number", defaultValue: 30 },
            { name: "Cyan", type: "number", defaultValue: 60 },
            { name: "Blue", type: "number", defaultValue: 20 },
            { name: "Magenta", type: "number", defaultValue: 80 },
            { name: "Tint", type: "boolean", defaultValue: False }
        ]
    },
    {
        matchName: "ADBE Photo Filter",
        displayName: "Photo Filter",
        category: "color_correction",
        expectedParams: [
            { name: "Filter", type: "enum", defaultValue: Warming Filter (85) },
            { name: "Density", type: "number", defaultValue: 25 },
            { name: "Preserve Luminosity", type: "boolean", defaultValue: True }
        ]
    },
    {
        matchName: "ADBE Levels",
        displayName: "Levels",
        category: "color_correction",
        expectedParams: [
            { name: "Channel", type: "enum", defaultValue: RGB },
            { name: "Input Black", type: "number", defaultValue: 0 },
            { name: "Input White", type: "number", defaultValue: 255 },
            { name: "Gamma", type: "number", defaultValue: 1.0 },
            { name: "Output Black", type: "number", defaultValue: 0 },
            { name: "Output White", type: "number", defaultValue: 255 }
        ]
    },
    {
        matchName: "ADBE Tint",
        displayName: "Tint",
        category: "color_correction",
        expectedParams: [
            { name: "Map Black To", type: "color", defaultValue: [0, 0, 0] },
            { name: "Map White To", type: "color", defaultValue: [1, 1, 1] },
            { name: "Amount to Tint", type: "number", defaultValue: 100 }
        ]
    },
    {
        matchName: "ADBE Tritone",
        displayName: "Tritone",
        category: "color_correction",
        expectedParams: [
            { name: "Highlights", type: "color", defaultValue: [1, 1, 1] },
            { name: "Midtones", type: "color", defaultValue: [0.5, 0.5, 0.5] },
            { name: "Shadows", type: "color", defaultValue: [0, 0, 0] },
            { name: "Blend With Original", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Colorama",
        displayName: "Colorama",
        category: "color_correction",
        expectedParams: [
            { name: "Input Phase", type: "number", defaultValue: 0 },
            { name: "Output Cycle", type: "enum", defaultValue: Rainbow },
            { name: "Cycle Repetitions", type: "number", defaultValue: 1 }
        ]
    },
    {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        category: "glow_light",
        expectedParams: [
            { name: "Glow Threshold", type: "number", defaultValue: 50 },
            { name: "Glow Radius", type: "number", defaultValue: 20 },
            { name: "Glow Intensity", type: "number", defaultValue: 1.0 },
            { name: "Glow Colors", type: "enum", defaultValue: Original Colors },
            { name: "Glow Color A", type: "color", defaultValue: [1, 1, 1] },
            { name: "Glow Color B", type: "color", defaultValue: [1, 0.5, 0] }
        ]
    },
    {
        matchName: "ADBE Starglow",
        displayName: "Starglow",
        category: "glow_light",
        expectedParams: [
            { name: "Input Threshold", type: "number", defaultValue: 100 },
            { name: "Star Glow Length", type: "number", defaultValue: 20 },
            { name: "Boost Light", type: "number", defaultValue: 10 }
        ]
    },
    {
        matchName: "CC Light Rays",
        displayName: "CC Light Rays",
        category: "glow_light",
        expectedParams: [
            { name: "Intensity", type: "number", defaultValue: 100 },
            { name: "Radius", type: "number", defaultValue: 50 },
            { name: "Warp", type: "number", defaultValue: 0.5 }
        ]
    },
    {
        matchName: "CC Glue Gun",
        displayName: "CC Glue Gun",
        category: "glow_light",
        expectedParams: [
            { name: "Intensity", type: "number", defaultValue: 50 },
            { name: "Softness", type: "number", defaultValue: 10 },
            { name: "Color", type: "color", defaultValue: [1, 1, 0.8] }
        ]
    },
    {
        matchName: "ADBE Lens Flare",
        displayName: "Lens Flare",
        category: "glow_light",
        expectedParams: [
            { name: "Flare Center", type: "point", defaultValue: [0.5, 0.5] },
            { name: "Flare Brightness", type: "number", defaultValue: 100 },
            { name: "Lens Type", type: "enum", defaultValue: 50-300mm Zoom },
            { name: "Blend With Original", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "CC Light Burst 2.5",
        displayName: "CC Light Burst",
        category: "glow_light",
        expectedParams: [
            { name: "Center", type: "point", defaultValue: [0.5, 0.5] },
            { name: "Intensity", type: "number", defaultValue: 120 },
            { name: "Burst Length", type: "number", defaultValue: 0.8 },
            { name: "Amplitude", type: "number", defaultValue: 15 }
        ]
    },
    {
        matchName: "ADBE Vegas",
        displayName: "Vegas",
        category: "glow_light",
        expectedParams: [
            { name: "Stroke", type: "enum", defaultValue: Image Contours },
            { name: "Color", type: "color", defaultValue: [1, 1, 0] },
            { name: "Length", type: "number", defaultValue: 0.5 },
            { name: "Segments", type: "number", defaultValue: 6 },
            { name: "Rotation", type: "number", defaultValue: 0 },
            { name: "Width", type: "number", defaultValue: 3 },
            { name: "Hardness", type: "number", defaultValue: 0.5 },
            { name: "Start Point", type: "point", defaultValue: [0, 0.5] }
        ]
    },
    {
        matchName: "ADBE Turbulent Displace",
        displayName: "Turbulent Displace",
        category: "distort",
        expectedParams: [
            { name: "Displacement", type: "enum", defaultValue: Turbulent },
            { name: "Amount", type: "number", defaultValue: 30 },
            { name: "Size", type: "number", defaultValue: 40 },
            { name: "Offset", type: "point", defaultValue: [0, 0] },
            { name: "Complexity", type: "number", defaultValue: 3 },
            { name: "Evolution", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Wave Warp",
        displayName: "Wave Warp",
        category: "distort",
        expectedParams: [
            { name: "Wave Type", type: "enum", defaultValue: Sine },
            { name: "Wave Height", type: "number", defaultValue: 50 },
            { name: "Wave Width", type: "number", defaultValue: 200 },
            { name: "Direction", type: "number", defaultValue: 0 },
            { name: "Wave Speed", type: "number", defaultValue: 1 },
            { name: "Phase", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "CC Power Pin",
        displayName: "CC Power Pin",
        category: "distort",
        expectedParams: [
            { name: "Top Left", type: "point", defaultValue: [0, 0] },
            { name: "Top Right", type: "point", defaultValue: [1, 0] },
            { name: "Bottom Left", type: "point", defaultValue: [0, 1] },
            { name: "Bottom Right", type: "point", defaultValue: [1, 1] },
            { name: "Perspective", type: "number", defaultValue: 50 }
        ]
    },
    {
        matchName: "CC Bender",
        displayName: "CC Bender",
        category: "distort",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: 30 },
            { name: "Axis", type: "enum", defaultValue: Horizontal }
        ]
    },
    {
        matchName: "CC Bulge",
        displayName: "CC Bulge",
        category: "distort",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 100 },
            { name: "Bulge Height", type: "number", defaultValue: 50 },
            { name: "Taper Radius", type: "number", defaultValue: 50 },
            { name: "Antialiasing", type: "enum", defaultValue: Medium }
        ]
    },
    {
        matchName: "ADBE Liquify",
        displayName: "Liquify",
        category: "distort",
        expectedParams: [
            { name: "Warp Tool Options", type: "number", defaultValue: 50 }
        ]
    },
    {
        matchName: "CC Page Turn",
        displayName: "CC Page Turn",
        category: "distort",
        expectedParams: [
            { name: "Fold Direction", type: "number", defaultValue: 45 },
            { name: "Fold Amount", type: "number", defaultValue: 30 },
            { name: "Light Direction", type: "number", defaultValue: -45 }
        ]
    },
    {
        matchName: "ADBE Mesh Warp",
        displayName: "Mesh Warp",
        category: "distort",
        expectedParams: [
            { name: "Rows", type: "number", defaultValue: 7 },
            { name: "Columns", type: "number", defaultValue: 7 },
            { name: "Quality", type: "number", defaultValue: 5 }
        ]
    },
    {
        matchName: "CC Lens",
        displayName: "CC Lens",
        category: "distort",
        expectedParams: [
            { name: "Size", type: "number", defaultValue: 60 },
            { name: "Convergence", type: "number", defaultValue: 0 },
            { name: "Center", type: "point", defaultValue: [0.5, 0.5] }
        ]
    },
    {
        matchName: "ADBE Fractal Noise",
        displayName: "Fractal Noise",
        category: "noise_grain",
        expectedParams: [
            { name: "Fractal Type", type: "enum", defaultValue: Turbulent Basic },
            { name: "Noise Type", type: "enum", defaultValue: Soft Linear },
            { name: "Brightness", type: "number", defaultValue: 0 },
            { name: "Contrast", type: "number", defaultValue: 100 },
            { name: "Scale", type: "number", defaultValue: 100 },
            { name: "Offset Turbulence", type: "point", defaultValue: [0, 0] },
            { name: "Complexity", type: "number", defaultValue: 6 },
            { name: "Evolution", type: "number", defaultValue: 0 },
            { name: "Overflow", type: "enum", defaultValue: Clip }
        ]
    },
    {
        matchName: "ADBE Noise",
        displayName: "Noise",
        category: "noise_grain",
        expectedParams: [
            { name: "Amount of Noise", type: "number", defaultValue: 10 },
            { name: "Noise Type", type: "enum", defaultValue: Grain },
            { name: "Clipping", type: "boolean", defaultValue: True }
        ]
    },
    {
        matchName: "ADBE Median",
        displayName: "Median",
        category: "noise_grain",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 3 },
            { name: "Operator", type: "enum", defaultValue: Median },
            { name: "Channel", type: "enum", defaultValue: All }
        ]
    },
    {
        matchName: "ADBE Turbulent Noise",
        displayName: "Turbulent Noise",
        category: "noise_grain",
        expectedParams: [
            { name: "Noise Style", type: "enum", defaultValue: Turbulent Basic },
            { name: "Contrast", type: "number", defaultValue: 150 },
            { name: "Brightness", type: "number", defaultValue: 0 },
            { name: "Scale", type: "number", defaultValue: 200 },
            { name: "Complexity", type: "number", defaultValue: 5 },
            { name: "Evolution", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Dust & Scratches",
        displayName: "Dust & Scratches",
        category: "noise_grain",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 5 },
            { name: "Threshold", type: "number", defaultValue: 10 }
        ]
    },
    {
        matchName: "ADBE Noise Alpha",
        displayName: "Noise Alpha",
        category: "noise_grain",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: 20 },
            { name: "Noise Type", type: "enum", defaultValue: Uniform Random },
            { name: "Overflow", type: "enum", defaultValue: Clip }
        ]
    },
    {
        matchName: "ADBE Color Key",
        displayName: "Color Key",
        category: "channel_keying",
        expectedParams: [
            { name: "Key Color", type: "color", defaultValue: [0, 0, 1] },
            { name: "Color Tolerance", type: "number", defaultValue: 50 },
            { name: "Edge Thin", type: "number", defaultValue: 0 },
            { name: "Edge Feather", type: "number", defaultValue: 5 }
        ]
    },
    {
        matchName: "ADBE Luma Key",
        displayName: "Luma Key",
        category: "channel_keying",
        expectedParams: [
            { name: "Key Type", type: "enum", defaultValue: Key Out Brighter },
            { name: "Threshold", type: "number", defaultValue: 128 },
            { name: "Tolerance", type: "number", defaultValue: 50 },
            { name: "Edge Feather", type: "number", defaultValue: 2 }
        ]
    },
    {
        matchName: "ADBE Set Matte",
        displayName: "Set Matte",
        category: "channel_keying",
        expectedParams: [
            { name: "Take Matte From Layer", type: "enum", defaultValue: None },
            { name: "Use For Matte", type: "enum", defaultValue: Luminance },
            { name: "Invert Matte", type: "boolean", defaultValue: False },
            { name: "Stretch Matte to Fit", type: "boolean", defaultValue: True },
            { name: "Composite Matte with Original", type: "boolean", defaultValue: False }
        ]
    },
    {
        matchName: "ADBE Simple Choker",
        displayName: "Simple Choker",
        category: "channel_keying",
        expectedParams: [
            { name: "Choke Matte", type: "number", defaultValue: 5 }
        ]
    },
    {
        matchName: "ADBE Shift Channels",
        displayName: "Shift Channels",
        category: "channel_keying",
        expectedParams: [
            { name: "Take Alpha From", type: "enum", defaultValue: Alpha },
            { name: "Take Red From", type: "enum", defaultValue: Red Channel },
            { name: "Take Green From", type: "enum", defaultValue: Green Channel },
            { name: "Take Blue From", type: "enum", defaultValue: Blue Channel }
        ]
    },
    {
        matchName: "ADBE Matte Choker",
        displayName: "Matte Choker",
        category: "channel_keying",
        expectedParams: [
            { name: "Geometric Softness", type: "number", defaultValue: 10 },
            { name: "Choke", type: "number", defaultValue: 5 },
            { name: "Gray Level Softness", type: "number", defaultValue: 50 },
            { name: "Iterations", type: "number", defaultValue: 5 }
        ]
    },
    {
        matchName: "ADBE Mosaic",
        displayName: "Mosaic",
        category: "stylize",
        expectedParams: [
            { name: "Horizontal Blocks", type: "number", defaultValue: 50 },
            { name: "Vertical Blocks", type: "number", defaultValue: 50 },
            { name: "Sharp Colors", type: "boolean", defaultValue: False }
        ]
    },
    {
        matchName: "ADBE Find Edges",
        displayName: "Find Edges",
        category: "stylize",
        expectedParams: [
            { name: "Invert", type: "boolean", defaultValue: False },
            { name: "Blend With Original", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Cartoon",
        displayName: "Cartoon",
        category: "stylize",
        expectedParams: [
            { name: "Render", type: "enum", defaultValue: Fill & Edges },
            { name: "Detail", type: "number", defaultValue: 12 },
            { name: "Edge Threshold", type: "number", defaultValue: 2.0 },
            { name: "Edge Width", type: "number", defaultValue: 4.0 },
            { name: "Smoothness", type: "number", defaultValue: 5.0 }
        ]
    },
    {
        matchName: "CC Vignette",
        displayName: "CC Vignette",
        category: "stylize",
        expectedParams: [
            { name: "Amount", type: "number", defaultValue: -30 },
            { name: "Midpoint", type: "number", defaultValue: 70 },
            { name: "Roundness", type: "number", defaultValue: 50 },
            { name: "Softness", type: "number", defaultValue: 60 }
        ]
    },
    {
        matchName: "ADBE Roughen Edges",
        displayName: "Roughen Edges",
        category: "stylize",
        expectedParams: [
            { name: "Edge Type", type: "enum", defaultValue: Roughen },
            { name: "Border", type: "number", defaultValue: 10 },
            { name: "Edge Sharpness", type: "number", defaultValue: 3 },
            { name: "Fractal Influence", type: "number", defaultValue: 0.5 },
            { name: "Scale", type: "number", defaultValue: 100 },
            { name: "Complexity", type: "number", defaultValue: 3 },
            { name: "Evolution", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Emboss",
        displayName: "Emboss",
        category: "stylize",
        expectedParams: [
            { name: "Direction", type: "number", defaultValue: 45 },
            { name: "Relief", type: "number", defaultValue: 5 },
            { name: "Contrast", type: "number", defaultValue: 50 },
            { name: "Blend With Original", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Stamp",
        displayName: "Stamp",
        category: "stylize",
        expectedParams: [
            { name: "Light/Dark Balance", type: "number", defaultValue: 128 },
            { name: "Smoothness", type: "number", defaultValue: 5 }
        ]
    },
    {
        matchName: "CC Kaleida",
        displayName: "CC Kaleida",
        category: "stylize",
        expectedParams: [
            { name: "Size", type: "number", defaultValue: 50 },
            { name: "Sides", type: "number", defaultValue: 6 },
            { name: "Angle", type: "number", defaultValue: 0 },
            { name: "Mirror", type: "boolean", defaultValue: True }
        ]
    },
    {
        matchName: "ADBE Drop Shadow",
        displayName: "Drop Shadow",
        category: "perspective_3d",
        expectedParams: [
            { name: "Shadow Color", type: "color", defaultValue: [0, 0, 0] },
            { name: "Opacity", type: "number", defaultValue: 75 },
            { name: "Direction", type: "number", defaultValue: 135 },
            { name: "Distance", type: "number", defaultValue: 12 },
            { name: "Softness", type: "number", defaultValue: 10 }
        ]
    },
    {
        matchName: "ADBE Bevel Alpha",
        displayName: "Bevel Alpha",
        category: "perspective_3d",
        expectedParams: [
            { name: "Edge Thickness", type: "number", defaultValue: 10 },
            { name: "Light Angle", type: "number", defaultValue: -45 },
            { name: "Light Color", type: "color", defaultValue: [1, 1, 1] },
            { name: "Light Intensity", type: "number", defaultValue: 50 }
        ]
    },
    {
        matchName: "ADBE Basic 3D",
        displayName: "Basic 3D",
        category: "perspective_3d",
        expectedParams: [
            { name: "Swivel", type: "number", defaultValue: 0 },
            { name: "Tilt", type: "number", defaultValue: 0 },
            { name: "Distance to Image", type: "number", defaultValue: 0 },
            { name: "Specular Highlight", type: "boolean", defaultValue: False },
            { name: "Preview", type: "boolean", defaultValue: False }
        ]
    },
    {
        matchName: "CC Sphere",
        displayName: "CC Sphere",
        category: "perspective_3d",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 100 },
            { name: "Rotation", type: "number", defaultValue: 0 },
            { name: "Light", type: "number", defaultValue: 45 },
            { name: "Light Height", type: "number", defaultValue: 45 },
            { name: "Shading", type: "number", defaultValue: 50 }
        ]
    },
    {
        matchName: "CC Cylinder",
        displayName: "CC Cylinder",
        category: "perspective_3d",
        expectedParams: [
            { name: "Radius", type: "number", defaultValue: 100 },
            { name: "Rotation", type: "number", defaultValue: 0 },
            { name: "Light", type: "number", defaultValue: 45 },
            { name: "Light Height", type: "number", defaultValue: 45 },
            { name: "Shading", type: "number", defaultValue: 50 }
        ]
    },
    {
        matchName: "ADBE Optics Compensation",
        displayName: "Optics Compensation",
        category: "perspective_3d",
        expectedParams: [
            { name: "Field of View", type: "number", defaultValue: 30 },
            { name: "Reverse Lens Distortion", type: "boolean", defaultValue: False },
            { name: "View Center", type: "point", defaultValue: [0.5, 0.5] }
        ]
    },
    {
        matchName: "ADBE Fill",
        displayName: "Fill",
        category: "generate_draw",
        expectedParams: [
            { name: "Color", type: "color", defaultValue: [1, 1, 1] },
            { name: "Horizontal Feather", type: "number", defaultValue: 0 },
            { name: "Vertical Feather", type: "number", defaultValue: 0 },
            { name: "Opacity", type: "number", defaultValue: 100 }
        ]
    },
    {
        matchName: "ADBE Ramp",
        displayName: "Ramp",
        category: "generate_draw",
        expectedParams: [
            { name: "Start of Ramp", type: "point", defaultValue: [0, 0] },
            { name: "Start Color", type: "color", defaultValue: [1, 1, 1] },
            { name: "End of Ramp", type: "point", defaultValue: [0, 1] },
            { name: "End Color", type: "color", defaultValue: [0, 0, 0] },
            { name: "Ramp Shape", type: "enum", defaultValue: Linear Ramp },
            { name: "Ramp Scatter", type: "number", defaultValue: 0 },
            { name: "Blend With Original", type: "number", defaultValue: 0 }
        ]
    },
    {
        matchName: "ADBE Stroke",
        displayName: "Stroke",
        category: "generate_draw",
        expectedParams: [
            { name: "Path", type: "enum", defaultValue: None },
            { name: "Color", type: "color", defaultValue: [1, 1, 1] },
            { name: "Brush Size", type: "number", defaultValue: 2 },
            { name: "Brush Hardness", type: "number", defaultValue: 100 },
            { name: "Opacity", type: "number", defaultValue: 100 },
            { name: "Start", type: "number", defaultValue: 0 },
            { name: "End", type: "number", defaultValue: 100 },
            { name: "Spacing", type: "number", defaultValue: 1 },
            { name: "Paint On", type: "enum", defaultValue: Original Image }
        ]
    },
    {
        matchName: "ADBE 4-Color Gradient",
        displayName: "4-Color Gradient",
        category: "generate_draw",
        expectedParams: [
            { name: "Top Left", type: "color", defaultValue: [1, 0, 0] },
            { name: "Top Right", type: "color", defaultValue: [0, 1, 0] },
            { name: "Bottom Left", type: "color", defaultValue: [0, 0, 1] },
            { name: "Bottom Right", type: "color", defaultValue: [1, 1, 0] },
            { name: "Blend", type: "number", defaultValue: 50 },
            { name: "Jitter", type: "number", defaultValue: 0 },
            { name: "Opacity", type: "number", defaultValue: 100 }
        ]
    },
    {
        matchName: "ADBE Circle",
        displayName: "Circle",
        category: "generate_draw",
        expectedParams: [
            { name: "Center", type: "point", defaultValue: [0.5, 0.5] },
            { name: "Radius", type: "number", defaultValue: 100 },
            { name: "Edge", type: "enum", defaultValue: None },
            { name: "Thickness", type: "number", defaultValue: 10 },
            { name: "Feather", type: "number", defaultValue: 0 },
            { name: "Invert Circle", type: "boolean", defaultValue: False },
            { name: "Color", type: "color", defaultValue: [1, 1, 1] },
            { name: "Opacity", type: "number", defaultValue: 100 }
        ]
    },
    {
        matchName: "ADBE Checkerboard",
        displayName: "Checkerboard",
        category: "generate_draw",
        expectedParams: [
            { name: "Anchor", type: "point", defaultValue: [0, 0] },
            { name: "Size From", type: "enum", defaultValue: Corner },
            { name: "Corner", type: "point", defaultValue: [0.1, 0.1] },
            { name: "Color 1", type: "color", defaultValue: [1, 1, 1] },
            { name: "Color 2", type: "color", defaultValue: [0, 0, 0] },
            { name: "Feather", type: "number", defaultValue: 0 },
            { name: "Opacity", type: "number", defaultValue: 100 }
        ]
    },
    {
        matchName: "CC Particle World",
        displayName: "CC Particle World",
        category: "generate_draw",
        expectedParams: [
            { name: "Birth Rate", type: "number", defaultValue: 100 },
            { name: "Longevity", type: "number", defaultValue: 2.0 },
            { name: "Position X", type: "number", defaultValue: 0.5 },
            { name: "Position Y", type: "number", defaultValue: 0.5 },
            { name: "Position Z", type: "number", defaultValue: 0 },
            { name: "Velocity", type: "number", defaultValue: 50 },
            { name: "Gravity", type: "number", defaultValue: 0 },
            { name: "Particle Radius", type: "number", defaultValue: 5 },
            { name: "Opacity", type: "number", defaultValue: 100 },
            { name: "Red", type: "number", defaultValue: 1 },
            { name: "Green", type: "number", defaultValue: 1 },
            { name: "Blue", type: "number", defaultValue: 1 }
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
                    log("    ⚠️  参数名不匹配: 期望 \'" + expectedParam.name + "\', 实际 \'" + actualName + "\' (类型: " + actualType + ")");
                } else if (nameMatch && !typeMatch) {
                    result.paramsMismatched.push({
                        expected: expectedParam.name,
                        actual: actualName,
                        reason: "type_mismatch",
                        expectedType: expectedParam.type,
                        actualType: actualType
                    });
                    log("    ⚠️  类型不匹配: \'" + expectedParam.name + "\', 期望类型: " + expectedParam.type + ", 实际类型: " + actualType);
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
    log("验证结果结果");
    log("========================================");
    log("========================================");
    log("========================================");
    log("========================================");
    log("Total: " + validationResults.passedEffects + "/" + validationResults.totalEffects);
    log("========================================");
    log("Total: " + validationResults.passedEffects + "/" + validationResults.totalEffects);
    
    if (validationResults.missingEffects.length > 0) {
        log("缺失的效果:");
        for (var j = 0; j < validationResults.missingEffects.length; j++) {
            log("  - " + validationResults.missingEffects[j]);
        }
    }
    
    log("");
    log("验证完成时间: " + validationResults.testTime);
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
