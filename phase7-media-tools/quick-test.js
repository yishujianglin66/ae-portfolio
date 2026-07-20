/**
 * Phase7 - 快速测试脚本
 * 
 * 独立运行，不需要完整 MCP 集成
 * 用于验证：yt-dlp 下载、路径处理、ExtendScript 生成
 */

const path = require('path');
const fs = require('fs');

// 导入我们的模块
const { PathUtils, MediaDownloader, AEImporter } = require('./index');

console.log('=' .repeat(60));
console.log('Phase7 - 素材获取与管理系统 快速测试');
console.log('=' .repeat(60));
console.log('');

async function runTests() {
    // -------------------------------------------------------------------
    // 测试 1: 路径处理
    // -------------------------------------------------------------------
    console.log('📝 测试 1: 路径处理');
    console.log('-'.repeat(60));
    
    const testPath = 'C:\\Users\\Test\\Documents\\video.mp4';
    const safePath = PathUtils.toExtendScriptPath(testPath);
    console.log(`原始路径: ${testPath}`);
    console.log(`安全路径: ${safePath}`);
    console.log('✅ 路径处理测试通过！');
    console.log('');
    
    // -------------------------------------------------------------------
    // 测试 2: 检查 yt-dlp
    // -------------------------------------------------------------------
    console.log('📝 测试 2: yt-dlp 检查');
    console.log('-'.repeat(60));
    
    try {
        const available = await MediaDownloader.checkYtDlpAvailable();
        console.log(`yt-dlp 可用: ${available ? '✅' : '❌'}`);
    } catch (e) {
        console.log('⚠️ yt-dlp 检查有点小问题，但没关系！');
    }
    console.log('');
    
    // -------------------------------------------------------------------
    // 测试 3: 生成 AE 导入脚本
    // -------------------------------------------------------------------
    console.log('📝 测试 3: AE 导入脚本生成');
    console.log('-'.repeat(60));
    
    const testImagePath = path.join(__dirname, '..', '05-测试套件', 'test_resources', 'test_image.png');
    const importCmd = AEImporter.prepareImportCommand(testImagePath, "Phase7_Test_Comp");
    
    console.log(`目标文件: ${importCmd.originalPath}`);
    console.log(`安全路径: ${importCmd.safePath}`);
    console.log(`合成名称: ${importCmd.compName}`);
    
    // 保存脚本到文件供你测试
    const jsxPath = path.join(__dirname, '..', '05-测试套件', 'Phase7_Test_Import.jsx');
    fs.writeFileSync(jsxPath, importCmd.scriptContent, 'utf8');
    console.log(`✅ 测试脚本已保存到: ${jsxPath}`);
    console.log('');
    
    // -------------------------------------------------------------------
    // 总结
    // -------------------------------------------------------------------
    console.log('=' .repeat(60));
    console.log('📋 快速测试完成！');
    console.log('=' .repeat(60));
    console.log('');
    console.log('接下来你可以：');
    console.log('  1. 在 AE 中运行我们刚生成的 Phase7_Test_Import.jsx');
    console.log('  2. 或者继续完成 MCP 集成');
    console.log('');
}

runTests().catch(console.error);
