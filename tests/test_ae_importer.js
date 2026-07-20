/**
 * ae-importer.js 单元测试
 * 覆盖: generateImportScript, prepareImportCommand
 *
 * 关注点: 生成的 ExtendScript 代码会被 AE 直接执行，
 * 路径/合成名通过字符串插值进入脚本，回归会导致 AE 脚本错误或导入失败。
 */

const assert = require('assert');
const path = require('path');

const projectRoot = path.dirname(__dirname);
const AEImporter = require(path.join(projectRoot, 'phase7-media-tools', 'ae-importer.js'));
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
// 1. generateImportScript - 基础导入（无合成名）
// ============================================================================
console.log('\n=== generateImportScript (无合成名) ===');

test('返回非空字符串', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.strictEqual(typeof script, 'string');
    assert.ok(script.length > 0, '脚本不应为空');
});

test('脚本包含安全路径', () => {
    const safePath = 'C:/Videos/clip.mp4';
    const script = AEImporter.generateImportScript(safePath, null);
    assert.ok(script.includes(safePath), '脚本应包含传入的安全路径');
});

test('脚本包含 beginUndoGroup / endUndoGroup 配对', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.ok(script.includes('app.beginUndoGroup'), '应包含 beginUndoGroup');
    assert.ok(script.includes('app.endUndoGroup'), '应包含 endUndoGroup');
    // 配对数量相等
    const beginCount = (script.match(/beginUndoGroup/g) || []).length;
    const endCount = (script.match(/endUndoGroup/g) || []).length;
    assert.strictEqual(beginCount, endCount, 'begin/endUndoGroup 应成对出现');
});

test('脚本包含 try/catch 错误处理', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.ok(script.includes('try'), '应包含 try 块');
    assert.ok(script.includes('catch'), '应包含 catch 块');
    assert.ok(script.includes('results.success = false'), 'catch 中应设置 success=false');
});

test('脚本包含 file.exists 检查', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.ok(script.includes('file.exists'), '应检查文件是否存在');
    assert.ok(script.includes('File not found'), '文件不存在时应有明确错误信息');
});

test('脚本包含 importFile 调用', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.ok(script.includes('app.project.importFile'), '应调用 importFile');
    assert.ok(script.includes('ImportOptions'), '应使用 ImportOptions');
});

test('脚本返回 success=true 与 footage 元数据', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.ok(script.includes('results.success = true'), '成功路径应设置 success=true');
    assert.ok(script.includes('results.footageName'), '应返回 footageName');
    assert.ok(script.includes('results.footageId'), '应返回 footageId');
});

test('无合成名时不包含合成查找逻辑', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', null);
    assert.ok(!script.includes('targetComp'), '无合成名时不应包含 targetComp 逻辑');
});

// ============================================================================
// 2. generateImportScript - 带合成名
// ============================================================================
console.log('\n=== generateImportScript (带合成名) ===');

test('脚本包含合成查找逻辑', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', 'MyComp');
    assert.ok(script.includes('targetComp'), '应包含 targetComp 查找逻辑');
    assert.ok(script.includes('"MyComp"'), '应包含合成名');
});

test('脚本包含合成不存在时创建逻辑', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', 'MyComp');
    assert.ok(script.includes('addComp'), '不存在时应调用 addComp 创建');
    assert.ok(script.includes('1920, 1080'), '默认创建 1920x1080');
});

test('脚本包含添加到合成并居中逻辑', () => {
    const script = AEImporter.generateImportScript('C:/Videos/clip.mp4', 'MyComp');
    assert.ok(script.includes('targetComp.layers.add'), '应将素材添加到合成');
    assert.ok(script.includes('Position'), '应设置 Position');
    assert.ok(script.includes('width / 2'), '应居中（width/2）');
});

test('不同合成名生成不同脚本', () => {
    const s1 = AEImporter.generateImportScript('C:/v.mp4', 'CompA');
    const s2 = AEImporter.generateImportScript('C:/v.mp4', 'CompB');
    assert.ok(s1 !== s2, '不同合成名应产生不同脚本');
    assert.ok(s1.includes('"CompA"') && !s1.includes('"CompB"'), 's1 应仅含 CompA');
    assert.ok(s2.includes('"CompB"') && !s2.includes('"CompA"'), 's2 应仅含 CompB');
});

// ============================================================================
// 3. prepareImportCommand - 命令准备
// ============================================================================
console.log('\n=== prepareImportCommand ===');

test('返回包含全部字段的对象', () => {
    const cmd = AEImporter.prepareImportCommand('C:\\Videos\\clip.mp4', 'MyComp');
    assert.ok(typeof cmd === 'object', '应返回对象');
    assert.ok('scriptContent' in cmd, '应有 scriptContent');
    assert.ok('safePath' in cmd, '应有 safePath');
    assert.ok('originalPath' in cmd, '应有 originalPath');
    assert.ok('compName' in cmd, '应有 compName');
});

test('originalPath 保留原始 Windows 路径', () => {
    const winPath = 'C:\\Users\\Test\\clip.mp4';
    const cmd = AEImporter.prepareImportCommand(winPath, null);
    assert.strictEqual(cmd.originalPath, winPath, 'originalPath 应与输入一致');
});

test('safePath 转换反斜杠为正斜杠', () => {
    const cmd = AEImporter.prepareImportCommand('C:\\Users\\Test\\clip.mp4', null);
    assert.strictEqual(cmd.safePath, 'C:/Users/Test/clip.mp4', 'safePath 应为正斜杠');
    assert.ok(!cmd.safePath.includes('\\'), 'safePath 不应含反斜杠');
});

test('safePath 与 PathUtils.toExtendScriptPath 一致', () => {
    const winPath = 'D:\\media\\audio\\bgm.mp3';
    const cmd = AEImporter.prepareImportCommand(winPath, null);
    assert.strictEqual(cmd.safePath, PathUtils.toExtendScriptPath(winPath), '应复用 PathUtils 转换');
});

test('compName 为 null 时字段保留 null', () => {
    const cmd = AEImporter.prepareImportCommand('C:/v.mp4', null);
    assert.strictEqual(cmd.compName, null, '未传 compName 时应为 null');
});

test('compName 透传到结果', () => {
    const cmd = AEImporter.prepareImportCommand('C:/v.mp4', 'Target_Comp');
    assert.strictEqual(cmd.compName, 'Target_Comp', 'compName 应原样透传');
});

test('scriptContent 与 generateImportScript 输出一致', () => {
    const winPath = 'C:\\Videos\\clip.mp4';
    const cmd = AEImporter.prepareImportCommand(winPath, 'MyComp');
    const expected = AEImporter.generateImportScript(cmd.safePath, 'MyComp');
    assert.strictEqual(cmd.scriptContent, expected, 'scriptContent 应基于 safePath 生成');
});

test('scriptContent 中使用的是 safePath 而非 originalPath', () => {
    const winPath = 'C:\\Users\\Test\\clip.mp4';
    const cmd = AEImporter.prepareImportCommand(winPath, null);
    assert.ok(cmd.scriptContent.includes('C:/Users/Test/clip.mp4'), '脚本应含正斜杠路径');
    assert.ok(!cmd.scriptContent.includes('C:\\Users\\Test\\clip.mp4'), '脚本不应含反斜杠路径');
});

test('已是正斜杠的路径保持不变', () => {
    const cmd = AEImporter.prepareImportCommand('C:/Videos/clip.mp4', null);
    assert.strictEqual(cmd.safePath, 'C:/Videos/clip.mp4', '正斜杠路径应保持不变');
    assert.strictEqual(cmd.originalPath, 'C:/Videos/clip.mp4', 'originalPath 也应保持不变');
});

// ============================================================================
// 4. 边界条件
// ============================================================================
console.log('\n=== 边界条件 ===');

test('空路径仍生成脚本结构（不抛异常）', () => {
    const script = AEImporter.generateImportScript('', null);
    assert.ok(typeof script === 'string');
    assert.ok(script.includes('beginUndoGroup'), '应保留脚本骨架');
});

test('prepareImportCommand 空路径不抛异常', () => {
    const cmd = AEImporter.prepareImportCommand('', null);
    assert.strictEqual(cmd.safePath, '', '空路径 safePath 应为空');
    assert.strictEqual(cmd.originalPath, '', '空路径 originalPath 应为空');
});

test('含空格的路径正确处理', () => {
    const winPath = 'C:\\My Videos\\clip name.mp4';
    const cmd = AEImporter.prepareImportCommand(winPath, null);
    assert.strictEqual(cmd.safePath, 'C:/My Videos/clip name.mp4', '空格路径应保留');
    assert.ok(cmd.scriptContent.includes('C:/My Videos/clip name.mp4'), '脚本应含带空格路径');
});

test('UNC 路径转换为正斜杠', () => {
    const cmd = AEImporter.prepareImportCommand('\\\\server\\share\\file.mp4', null);
    assert.ok(!cmd.safePath.includes('\\'), 'UNC 路径也不应含反斜杠');
});

// ============================================================================
console.log(`\n========================================`);
console.log(` ae-importer 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);
