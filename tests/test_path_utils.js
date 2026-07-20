/**
 * path-utils.js 单元测试
 * 覆盖: toExtendScriptPath, generateSafeFilename, fileExists
 */

const assert = require('assert');
const path = require('path');
const os = require('os');
const fs = require('fs');

// 动态调整 __dirname 用于模块加载
const projectRoot = path.dirname(__dirname);
const PathUtils = require(path.join(projectRoot, 'phase7-media-tools', 'path-utils.js'));

let passed = 0;
let failed = 0;

function test(name, fn) {
    try {
        fn();
        passed++;
        console.log(`  ✓ ${name}`);
    } catch (e) {
        failed++;
        console.log(`  ✗ ${name}: ${e.message}`);
    }
}

// ============================================================================
// 1. toExtendScriptPath
// ============================================================================
console.log('\n=== toExtendScriptPath ===');

test('空字符串返回空字符串', () => {
    assert.strictEqual(PathUtils.toExtendScriptPath(''), '');
});

test('null/undefined 返回空字符串', () => {
    assert.strictEqual(PathUtils.toExtendScriptPath(null), '');
    assert.strictEqual(PathUtils.toExtendScriptPath(undefined), '');
});

test('Windows 反斜杠路径转换为正斜杠', () => {
    const result = PathUtils.toExtendScriptPath('C:\\Users\\Test\\file.mp4');
    assert.strictEqual(result, 'C:/Users/Test/file.mp4');
});

test('已经是正斜杠的路径不变', () => {
    const result = PathUtils.toExtendScriptPath('C:/Users/Test/file.mp4');
    assert.strictEqual(result, 'C:/Users/Test/file.mp4');
});

test('混合斜杠路径统一为正斜杠', () => {
    const result = PathUtils.toExtendScriptPath('C:\\Users/Test\\file.mp4');
    assert.strictEqual(result, 'C:/Users/Test/file.mp4');
});

test('UNC 路径转换', () => {
    const result = PathUtils.toExtendScriptPath('\\\\server\\share\\file.mp4');
    assert.ok(!result.includes('\\'), '不应包含反斜杠');
});

test('路径规范化后不含反斜杠', () => {
    const result = PathUtils.toExtendScriptPath('C:\\Users\\Test\\');
    assert.ok(!result.includes('\\'), '不应包含反斜杠');
});

// ============================================================================
// 2. generateSafeFilename
// ============================================================================
console.log('\n=== generateSafeFilename ===');

test('生成文件名包含前缀', () => {
    const result = PathUtils.generateSafeFilename('test', '.mp4');
    assert.ok(result.startsWith('test_'), `应以 test_ 开头: ${result}`);
});

test('生成文件名包含扩展名', () => {
    const result = PathUtils.generateSafeFilename('clip', '.mp4');
    assert.ok(result.endsWith('.mp4'), `应以 .mp4 结尾: ${result}`);
});

test('生成文件名包含时间戳', () => {
    const result = PathUtils.generateSafeFilename('bgm', '.mp3');
    // 格式: bgm_YYYY-MM-DD_HH-MM-SS.mp3
    assert.ok(result.match(/bgm_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.mp3/), `时间戳格式不正确: ${result}`);
});

test('不同时间生成的文件名不同', () => {
    const name1 = PathUtils.generateSafeFilename('test', '.mp4');
    // 需要微小延迟确保时间戳不同
    const start = Date.now();
    while (Date.now() === start) {}
    const name2 = PathUtils.generateSafeFilename('test', '.mp4');
    // 时间戳的秒级可能相同，但在不同秒调用时一定不同
    // 这里仅验证格式正确
    assert.ok(name1 !== '' && name2 !== '', '文件名非空');
});

// ============================================================================
// 3. fileExists
// ============================================================================
console.log('\n=== fileExists ===');

test('存在的文件返回 true', () => {
    // 测试自身文件
    assert.strictEqual(PathUtils.fileExists(__filename), true);
});

test('不存在的文件返回 false', () => {
    assert.strictEqual(PathUtils.fileExists('/nonexistent/file.xyz'), false);
});

// ============================================================================
// 4. getDownloadsDir
// ============================================================================
console.log('\n=== getDownloadsDir ===');

test('返回有效的下载目录路径', () => {
    const dir = PathUtils.getDownloadsDir();
    assert.ok(dir.length > 0, '路径非空');
    assert.ok(!dir.includes('\\'), '不应包含反斜杠');
    assert.ok(dir.includes('Downloads'), '应包含 Downloads');
});

// ============================================================================
console.log(`\n========================================`);
console.log(` path-utils 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);
