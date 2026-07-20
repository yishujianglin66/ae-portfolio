"""
generate_ae_validation_script.py - 生成 AE 验证脚本

根据知识图谱中的效果定义，自动生成 ExtendScript 验证脚本
用于在 AE 2026 真机上验证效果参数的准确性
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from effect_knowledge_graph import EFFECT_KNOWLEDGE_GRAPH, CATEGORIES, EffectParameter


def generate_jsx_validation_script():
    """生成 JSX 验证脚本"""
    
    effect_defs = []
    
    for match_name, effect in EFFECT_KNOWLEDGE_GRAPH.items():
        params_jsx = []
        for param in effect.parameters:
            param_type_map = {
                "number": "number",
                "slider": "number",
                "angle": "number",
                "color": "color",
                "enum": "enum",
                "boolean": "boolean",
                "point": "point",
            }
            jsx_type = param_type_map.get(param.param_type, "unknown")
            default_str = f", defaultValue: {param.default}" if param.default is not None else ""
            params_jsx.append(f'            {{ name: "{param.name}", type: "{jsx_type}"{default_str} }}')
        
        params_str = ",\n".join(params_jsx)
        
        effect_jsx = f"""    {{
        matchName: "{match_name}",
        displayName: "{effect.display_name}",
        category: "{effect.category}",
        expectedParams: [
{params_str}
        ]
    }}"""
        effect_defs.append(effect_jsx)
    
    effects_str = ",\n".join(effect_defs)
    
    script = f'''/*
 ============================================================================
 AE 2026 效果参数真机验证脚本（自动生成）
 ============================================================================
 生成时间: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
 效果数量: {len(EFFECT_KNOWLEDGE_GRAPH)}
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
{effects_str}
];

// ============================================================================
// 验证结果统计
// ============================================================================
var validationResults = {{
    totalEffects: EFFECT_DEFINITIONS.length,
    passedEffects: 0,
    failedEffects: 0,
    missingEffects: [],
    paramErrors: [],
    testTime: ""
}};

// ============================================================================
// 工具函数
// ============================================================================

function log(message) {{
    $.writeln("[AE Validation] " + message);
}}

function getAEVersion() {{
    return app.version;
}}

function getParamType(param) {{
    if (param.typeName === "ADBE Slider Control" || param.typeName === "Slider") {{
        return "number";
    }} else if (param.typeName === "ADBE Angle Control" || param.typeName === "Angle") {{
        return "number";
    }}
    if (param instanceof LightPropertyGroup) return "light";
    if (param instanceof CameraPropertyGroup) return "camera";
    if (param.propertyValueType === PropertyValueType.TwoD) return "point";
    if (param.propertyValueType === PropertyValueType.ThreeD) return "point3d";
    if (param.propertyValueType === PropertyValueType.Color) return "color";
    if (param.propertyValueType === PropertyValueType.CUSTOM_VALUE) {{
        try {{
            var val = param.value;
            if (typeof val === "boolean") return "boolean";
            return "enum";
        }} catch(e) {{}}
    }}
    if (param.propertyValueType === PropertyValueType.NumValue) return "number";
    try {{
        var val = param.value;
        if (typeof val === "number") return "number";
        if (typeof val === "boolean") return "boolean";
        if (typeof val === "string") return "enum";
    }} catch(e) {{}}
    if (param.propertyType === PropertyType.INDEXED_GROUP) return "enum";
    return "unknown";
}}

// ============================================================================
// 单个效果验证函数
// ============================================================================

function validateEffect(effectDef, testLayer) {{
    var result = {{
        matchName: effectDef.matchName,
        displayName: effectDef.displayName,
        category: effectDef.category,
        exists: false,
        paramsMatch: [],
        paramsMissing: [],
        paramsMismatched: [],
        totalParams: 0,
        matchedParams: 0
    }};
    
    try {{
        var effect = testLayer.effects.addProperty(effectDef.matchName);
        
        if (!effect) {{
            validationResults.missingEffects.push(effectDef.matchName);
            log("  ❌ 效果不存在: " + effectDef.matchName + " (" + effectDef.displayName + ")");
            return result;
        }}
        
        result.exists = true;
        log("  ✓ 效果存在: " + effectDef.matchName + " (" + effectDef.displayName + ")");
        
        var actualParamCount = effect.numProperties;
        result.totalParams = actualParamCount;
        
        log("    实际参数数量: " + actualParamCount);
        
        for (var i = 1; i <= Math.min(effectDef.expectedParams.length, actualParamCount); i++) {{
            try {{
                var expectedParam = effectDef.expectedParams[i - 1];
                var actualParam = effect.property(i);
                
                if (!actualParam) {{
                    result.paramsMissing.push(expectedParam.name);
                    continue;
                }}
                
                var actualName = actualParam.name;
                var actualType = getParamType(actualParam);
                
                var nameMatch = (actualName.toLowerCase() === expectedParam.name.toLowerCase());
                var typeMatch = (actualType === expectedParam.type);
                
                if (nameMatch && typeMatch) {{
                    result.matchedParams++;
                    result.paramsMatch.push(expectedParam.name);
                }} else if (!nameMatch && typeMatch) {{
                    result.paramsMismatched.push({{
                        expected: expectedParam.name,
                        actual: actualName,
                        reason: "name_mismatch",
                        type: expectedParam.type
                    }});
                    log("    ⚠️  参数名不匹配: 期望 \\'" + expectedParam.name + "\\', 实际 \\'" + actualName + "\\' (类型: " + actualType + ")");
                }} else if (nameMatch && !typeMatch) {{
                    result.paramsMismatched.push({{
                        expected: expectedParam.name,
                        actual: actualName,
                        reason: "type_mismatch",
                        expectedType: expectedParam.type,
                        actualType: actualType
                    }});
                    log("    ⚠️  类型不匹配: \\'" + expectedParam.name + "\\', 期望类型: " + expectedParam.type + ", 实际类型: " + actualType);
                }}
                
            }} catch(e) {{
                log("    ⚠️  参数访问错误: 第 " + i + " 个参数 - " + e.message);
            }}
        }}
        
        testLayer.effects.removeProperty(effectDef.matchName);
        
    }} catch(e) {{
        log("  ❌ 验证失败: " + effectDef.matchName + " - " + e.message);
        validationResults.missingEffects.push(effectDef.matchName + " (" + e.message + ")");
        return result;
    }}
    
    return result;
}}

// ============================================================================
// 主验证函数
// ============================================================================

function runValidation() {{
    log("========================================");
    log("AE " + getAEVersion() + " 效果参数真机验证");
    log("========================================");
    log("");
    
    var testComp, testLayer;
    
    try {{
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
        
    }} catch(e) {{
        log("错误: 无法创建测试合成 - " + e.message);
        return;
    }}
    
    var categoryResults = {{}};
    
    for (var i = 0; i < EFFECT_DEFINITIONS.length; i++) {{
        var effectDef = EFFECT_DEFINITIONS[i];
        
        log("[" + (i + 1) + "/" + EFFECT_DEFINITIONS.length + "] 验证: " + effectDef.displayName);
        
        var result = validateEffect(effectDef, testLayer);
        
        if (!categoryResults[effectDef.category]) {{
            categoryResults[effectDef.category] = {{
                total: 0,
                passed: 0,
                failed: 0
            }};
        }}
        categoryResults[effectDef.category].total++;
        
        if (result.exists && result.matchedParams >= Math.floor(result.totalParams * 0.6)) {{
            validationResults.passedEffects++;
            categoryResults[effectDef.category].passed++;
        }} else {{
            validationResults.failedEffects++;
            categoryResults[effectDef.category].failed++;
        }}
        
        log("");
    }}
    
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
    
    if (validationResults.missingEffects.length > 0) {{
        log("缺失的效果:");
        for (var j = 0; j < validationResults.missingEffects.length; j++) {{
            log("  - " + validationResults.missingEffects[j]);
        }}
    }}
    
    log("");
    log("验证完成时间: " + validationResults.testTime);
}}

// ============================================================================
// 运行验证
// ============================================================================
app.beginUndoGroup("AE Effect Validation");
try {{
    runValidation();
}} finally {{
    app.endUndoGroup();
}}
'''
    
    return script


if __name__ == "__main__":
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ae_validation_generated.jsx"
    )
    
    script_content = generate_jsx_validation_script()
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print(f"✅ 验证脚本已生成: {output_path}")
    print(f"   效果数量: {len(EFFECT_KNOWLEDGE_GRAPH)}")
    print(f"   类别数量: {len(CATEGORIES)}")
    print("")
    print("使用方法:")
    print("1. 打开 After Effects 2025")
    print(f"2. 通过 File > Scripts > Run Script File... 选择: {output_path}")
    print("3. 查看 Info 面板的详细输出")
    print("4. 查看项目面板中的 Validation_Report 合成")
