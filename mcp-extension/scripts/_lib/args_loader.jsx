// 全局公共函数 - args.json 参数加载
// 统一的 args.json 读取入口
// 用于消除 16 个 JSX 工具中文件末尾参数读取模板的重复代码（原重复 16 次）

/**
 * 从 args.json 文件加载参数
 * @param {File} [argsFile] - 可选的参数文件路径，默认使用 ae-mcp-bridge 的临时目录
 * @returns {Object} 解析后的参数对象，文件不存在或解析失败时返回空对象
 */
function loadArgs(argsFile) {
    // 从 args.json 文件读取参数，返回对象
    var file = argsFile || new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/temp/args.json");
    if (!file.exists) return {};
    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();
    try {
        return JSON.parse(content);
    } catch (e) {
        return {};
    }
}

/**
 * 从字符串加载参数（用于内联参数解析）
 * @param {string} str - JSON 格式的参数字符串
 * @returns {Object} 解析后的参数对象，解析失败时返回空对象
 */
function loadArgsFromString(str) {
    try {
        return JSON.parse(str);
    } catch (e) {
        return {};
    }
}
