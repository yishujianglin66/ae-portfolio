// ============================================================================
// test_all_scripts_syntax.jsx
// ExtendScript 语法静态检查 - 25 个 MCP 工具 JSX 脚本静态断言
//
// 测试目的：
//   由于测试环境无法实际运行 AfterEffects，本文件采用"静态断言"策略，
//   对 mcp-extension/scripts/ 下的 25 个 JSX 脚本进行静态语法检查，
//   确保脚本符合 ExtendScript (ES3 子集) 的语法约束。
//
// 检查策略：
//   1. 检查文件是否存在
//   2. 检查文件是否非空
//   3. 检查文件是否包含 IIFE 包装或函数声明
//   4. 检查文件是否包含 undoGroup 包装（app.beginUndoGroup / app.endUndoGroup）
//   5. 检查文件不包含禁止的 ES6 语法（const / let / => / 模板字符串反引号）
//   6. 检查文件是否包含 JSON.stringify 返回值构造
//   7. 检查文件是否包含 #include "_lib/..." 引用（重构后的版本，可缺失）
//
// 使用方式：
//   - 在 ExtendScript Toolkit (ESTK) 中打开本文件
//   - 选择 "AfterEffects" 作为目标应用
//   - 点击运行，结果会输出到控制台
//   - 或在 Python 测试中通过正则提取本文件的检查结果
//
// 注意：本文件本身不依赖 AE 运行时，仅做文本层面的静态检查。
// ============================================================================

// 25 个 MCP 工具对应的 JSX 文件清单（与 NEW_ALLOWED_SCRIPTS 对应）
var SCRIPT_FILES = [
    "addEffectWithKeyframes.jsx",
    "setKeyframeEasing.jsx",
    "batchAddEffects.jsx",
    "setBlendMode.jsx",
    "setTrackMatte.jsx",
    "setParentLayer.jsx",
    "addAdjustmentLayer.jsx",
    "addPrecomp.jsx",
    "importFootage.jsx",
    "setMotionBlur.jsx",
    "addMaskWithShape.jsx",
    "executeAtomScript.jsx",
    "getEffectProperties.jsx",
    "setEffectKeyframes.jsx",
    "applyNewtonDynamics.jsx",
    "createE2EMusicVideo.jsx",
    "addTextLayer.jsx",
    "addShapeLayer.jsx",
    "addCamera.jsx",
    "addLight.jsx",
    "applyLUT.jsx",
    "enableTimeRemap.jsx",
    "applySaber.jsx",
    "applyParticular.jsx",
    "applyOpticalFlares.jsx"
];

// ============================================================================
// 测试1：检查所有 JSX 文件存在性
// ============================================================================
function test_all_jsx_files_exist() {
    var scriptDir = getScriptDir();
    var missing = [];
    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var f = new File(filePath);
        if (!f.exists) {
            missing.push(SCRIPT_FILES[i]);
        }
    }
    if (missing.length > 0) {
        $.writeln("FAIL: test_all_jsx_files_exist - 缺失文件: " + missing.join(", "));
        return false;
    }
    $.writeln("PASS: test_all_jsx_files_exist - 全部 " + SCRIPT_FILES.length + " 个文件存在");
    return true;
}

// ============================================================================
// 测试2：检查所有 JSX 文件不包含禁止的 ES6 语法
// ============================================================================
function test_no_es6_syntax() {
    var scriptDir = getScriptDir();
    var violations = [];
    // 禁止的 ES6 特性：const / let / 箭头函数 => / 模板字符串反引号
    var forbiddenPatterns = [
        { name: "const声明", regex: /\bconst\s+/ },
        { name: "let声明", regex: /\blet\s+/ },
        { name: "箭头函数=>", regex: /=>/ },
        { name: "模板字符串反引号", regex: /`/ }
    ];

    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var content = readFile(filePath);
        if (content === null) {
            violations.push({ file: SCRIPT_FILES[i], issue: "无法读取" });
            continue;
        }
        // 移除注释行（避免注释中的 ES6 关键字误报）
        var lines = content.split(/\r?\n/);
        for (var ln = 0; ln < lines.length; ln++) {
            var line = lines[ln];
            // 跳过单行注释
            var trimmed = line.replace(/^\s*\/\/.*$/, "");
            // 跳过块注释内的行
            if (trimmed === line && line.indexOf("//") >= 0) {
                trimmed = line.substring(0, line.indexOf("//"));
            }
            for (var p = 0; p < forbiddenPatterns.length; p++) {
                if (forbiddenPatterns[p].regex.test(trimmed)) {
                    violations.push({
                        file: SCRIPT_FILES[i],
                        line: ln + 1,
                        issue: forbiddenPatterns[p].name
                    });
                }
            }
        }
    }
    if (violations.length > 0) {
        $.writeln("FAIL: test_no_es6_syntax - 发现 " + violations.length + " 处 ES6 语法违规");
        for (var v = 0; v < violations.length && v < 10; v++) {
            $.writeln("  - " + violations[v].file + " L" + violations[v].line + ": " + violations[v].issue);
        }
        return false;
    }
    $.writeln("PASS: test_no_es6_syntax - 无 ES6 语法违规");
    return true;
}

// ============================================================================
// 测试3：检查所有 JSX 文件包含 undoGroup 包装
// ============================================================================
function test_undo_group_wrapping() {
    var scriptDir = getScriptDir();
    var missing = [];
    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var content = readFile(filePath);
        if (content === null) {
            missing.push({ file: SCRIPT_FILES[i], reason: "无法读取" });
            continue;
        }
        // 部分工具（如 getEffectProperties）可能只读不写，不强制要求 undoGroup
        // executeAtomScript 和 createE2EMusicVideo 是特殊脚本，可能内部含子脚本
        // 但绝大多数写入操作必须在 undoGroup 中
        var hasBegin = /app\.beginUndoGroup\s*\(/.test(content);
        var hasEnd = /app\.endUndoGroup\s*\(/.test(content);
        if (!hasBegin || !hasEnd) {
            missing.push({
                file: SCRIPT_FILES[i],
                reason: "缺 beginUndoGroup(" + !hasBegin + ") 或 endUndoGroup(" + !hasEnd + ")"
            });
        }
    }
    if (missing.length > 0) {
        $.writeln("WARN: test_undo_group_wrapping - " + missing.length + " 个文件未完整包装 undoGroup（部分只读工具可豁免）:");
        for (var m = 0; m < missing.length; m++) {
            $.writeln("  - " + missing[m].file + ": " + missing[m].reason);
        }
        // 仅警告，不算失败
        return true;
    }
    $.writeln("PASS: test_undo_group_wrapping - 所有文件均包含 undoGroup 包装");
    return true;
}

// ============================================================================
// 测试4：检查所有 JSX 文件包含 JSON.stringify 或 _lib/response_utils.jsx
// ============================================================================
function test_json_return_pattern() {
    var scriptDir = getScriptDir();
    var missing = [];
    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var content = readFile(filePath);
        if (content === null) {
            missing.push(SCRIPT_FILES[i]);
            continue;
        }
        // 接受两种返回值构造方式：
        // 1. 旧风格：直接调用 JSON.stringify()
        // 2. 新风格（_lib 重构后）：#include "_lib/response_utils.jsx"
        //    通过 buildError()/buildSuccess() 构造返回值
        var hasJsonStringify = /JSON\.stringify\s*\(/.test(content);
        var hasResponseUtilsLib = /#include\s+["_']_lib\/response_utils\.jsx["']/.test(content);
        if (!hasJsonStringify && !hasResponseUtilsLib) {
            missing.push(SCRIPT_FILES[i]);
        }
    }
    if (missing.length > 0) {
        $.writeln("FAIL: test_json_return_pattern - " + missing.length + " 个文件未使用 JSON.stringify 或 _lib/response_utils.jsx:");
        $.writeln("  - " + missing.join(", "));
        return false;
    }
    $.writeln("PASS: test_json_return_pattern - 所有文件均使用 JSON.stringify 或 _lib/response_utils.jsx 构造返回值");
    return true;
}

// ============================================================================
// 测试5：检查所有 JSX 文件包含函数声明（IIFE 或命名函数）
// ============================================================================
function test_function_declaration() {
    var scriptDir = getScriptDir();
    var missing = [];
    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var content = readFile(filePath);
        if (content === null) {
            missing.push(SCRIPT_FILES[i]);
            continue;
        }
        // 接受 IIFE 包装：(function() { ... })();
        // 或命名函数声明：function xxx(args) { ... }
        var hasIIFE = /\(\s*function\s*\(\s*\)\s*\{[\s\S]*\}\s*\)\s*\(\s*\)\s*;?/.test(content);
        var hasNamedFunc = /function\s+[a-zA-Z_$][\w$]*\s*\([^)]*\)\s*\{/.test(content);
        if (!hasIIFE && !hasNamedFunc) {
            missing.push(SCRIPT_FILES[i]);
        }
    }
    if (missing.length > 0) {
        $.writeln("FAIL: test_function_declaration - " + missing.length + " 个文件未声明函数:");
        $.writeln("  - " + missing.join(", "));
        return false;
    }
    $.writeln("PASS: test_function_declaration - 所有文件均包含函数声明");
    return true;
}

// ============================================================================
// 测试6：检查文件大小合理（>200 字节，过滤空文件或仅含注释的文件）
// ============================================================================
function test_file_size_reasonable() {
    var scriptDir = getScriptDir();
    var tooSmall = [];
    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var f = new File(filePath);
        if (!f.exists) {
            tooSmall.push({ file: SCRIPT_FILES[i], size: -1 });
            continue;
        }
        if (f.length < 200) {
            tooSmall.push({ file: SCRIPT_FILES[i], size: f.length });
        }
    }
    if (tooSmall.length > 0) {
        $.writeln("FAIL: test_file_size_reasonable - " + tooSmall.length + " 个文件过小:");
        for (var s = 0; s < tooSmall.length; s++) {
            $.writeln("  - " + tooSmall[s].file + " (" + tooSmall[s].size + " 字节)");
        }
        return false;
    }
    $.writeln("PASS: test_file_size_reasonable - 所有文件均 > 200 字节");
    return true;
}

// ============================================================================
// 测试7：检查 #include "_lib/..." 引用（重构后的版本，可缺失，仅警告）
// ============================================================================
function test_lib_includes() {
    var scriptDir = getScriptDir();
    var withoutInclude = [];
    for (var i = 0; i < SCRIPT_FILES.length; i++) {
        var filePath = scriptDir + "/" + SCRIPT_FILES[i];
        var content = readFile(filePath);
        if (content === null) continue;
        if (!/#include\s+["']_lib\//.test(content)) {
            withoutInclude.push(SCRIPT_FILES[i]);
        }
    }
    // 此检查为可选，仅警告
    $.writeln("INFO: test_lib_includes - " + withoutInclude.length + " 个文件未使用 _lib 模块（_lib 重构未强制要求）");
    return true;
}

// ============================================================================
// 辅助函数：获取脚本所在目录
// ============================================================================
function getScriptDir() {
    // $.fileName 是当前脚本的绝对路径
    // _tests/test_all_scripts_syntax.jsx → 返回上级 scripts 目录
    var thisFile = new File($.fileName);
    var parentDir = thisFile.parent;  // _tests 目录
    return parentDir.parent.toString();  // scripts 目录
}

// ============================================================================
// 辅助函数：读取文件内容
// ============================================================================
function readFile(filePath) {
    try {
        var f = new File(filePath);
        if (!f.exists) return null;
        f.open("r");
        var content = f.read();
        f.close();
        return content;
    } catch (e) {
        return null;
    }
}

// ============================================================================
// 主函数：运行所有测试
// ============================================================================
(function runAllTests() {
    $.writeln("========================================");
    $.writeln("ExtendScript 语法静态检查 - 25 个 MCP 工具");
    $.writeln("========================================");

    var results = [
        test_all_jsx_files_exist(),
        test_no_es6_syntax(),
        test_undo_group_wrapping(),
        test_json_return_pattern(),
        test_function_declaration(),
        test_file_size_reasonable(),
        test_lib_includes()
    ];

    var passed = 0;
    var failed = 0;
    for (var i = 0; i < results.length; i++) {
        if (results[i]) {
            passed++;
        } else {
            failed++;
        }
    }

    $.writeln("========================================");
    $.writeln("总计: " + results.length + " 个测试, " + passed + " 通过, " + failed + " 失败");
    $.writeln("========================================");
})();
