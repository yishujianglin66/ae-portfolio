// 全局公共函数 - 响应构建
// 统一的 JSON 响应构建
// 用于消除 16 个 JSX 工具中响应构建逻辑的重复代码

/**
 * 构建成功响应
 * @param {Object} data - 要包含在响应中的数据字段（合并到响应根级）
 * @param {Object} [extra] - 可选的附加字段（同样合并到响应根级，与 data 同级）
 *   未传或 undefined 时响应结构与原 buildSuccess(data) 完全一致（向后兼容）。
 *   注意：ExtendScript 不支持默认参数，因此通过 arguments.length 检测。
 * @returns {string} JSON 格式的成功响应字符串
 *
 * 示例：
 *   buildSuccess({compName: "Comp 1"})
 *     -> {status: "success", compName: "Comp 1"}
 *   buildSuccess({compName: "Comp 1"}, {elapsedMs: 150, timestamp: "..."})
 *     -> {status: "success", compName: "Comp 1", elapsedMs: 150, timestamp: "..."}
 */
function buildSuccess(data, extra) {
    var result = { status: "success" };
    if (data) {
        for (var k in data) {
            if (data.hasOwnProperty(k)) result[k] = data[k];
        }
    }
    // 仅当显式传入 extra（arguments.length >= 2）且非 undefined/null 时合并
    if (arguments.length >= 2 && extra) {
        for (var ek in extra) {
            if (extra.hasOwnProperty(ek)) result[ek] = extra[ek];
        }
    }
    return JSON.stringify(result);
}

/**
 * 构建错误响应
 * @param {string} code - 错误代码
 * @param {string} message - 错误描述信息
 * @param {Object} [extra] - 可选的附加诊断字段（合并到错误响应根级）
 *   未传或 undefined 时响应结构与原 buildError(code, message) 完全一致（向后兼容）。
 *   注意：ExtendScript 不支持默认参数，因此通过 arguments.length 检测。
 * @returns {string} JSON 格式的错误响应字符串
 *
 * 示例：
 *   buildError("LAYER_NOT_FOUND", "Layer 'X' not found")
 *     -> {status: "error", errorCode: "LAYER_NOT_FOUND", message: "Layer 'X' not found"}
 *   buildError("EXEC_FAILED", "...", {scriptName: "addTextLayer", line: 42, elapsedMs: 123})
 *     -> {status: "error", errorCode: "EXEC_FAILED", message: "...",
 *         scriptName: "addTextLayer", line: 42, elapsedMs: 123}
 */
function buildError(code, message, extra) {
    var result = { status: "error", errorCode: code, message: message };
    // 仅当显式传入 extra（arguments.length >= 3）且非 undefined/null 时合并
    if (arguments.length >= 3 && extra) {
        for (var k in extra) {
            if (extra.hasOwnProperty(k)) result[k] = extra[k];
        }
    }
    return JSON.stringify(result);
}
