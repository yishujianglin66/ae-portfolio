/**
 * Phase7 - 独立版下载器
 * 
 * 直接运行此脚本，无需完整 MCP 集成
 * 用法：node standalone-downloader.js <URL> [type]
 */

const path = require('path');
const { MediaDownloader, PathUtils, AEImporter } = require('./index');

const args = process.argv.slice(2);

if (args.length < 1) {
    console.log('=' .repeat(60));
    console.log('Phase7 - 独立版下载工具');
    console.log('=' .repeat(60));
    console.log('');
    console.log('用法:');
    console.log('  node standalone-downloader.js <URL> [type]');
    console.log('');
    console.log('示例:');
    console.log('  node standalone-downloader.js "https://www.bilibili.com/..." video');
    console.log('  node standalone-downloader.js "https://www.youtube.com/..." audio');
    console.log('');
    process.exit(0);
}

const url = args[0];
const type = args[1] || 'video';

async function main() {
    console.log('=' .repeat(60));
    console.log('Phase7 - 下载任务');
    console.log('=' .repeat(60));
    console.log('');
    console.log(`URL: ${url}`);
    console.log(`类型: ${type}`);
    console.log('');
    
    try {
        console.log('⏳ 正在下载...');
        console.log('');
        
        let result;
        if (type === 'audio') {
            result = await MediaDownloader.downloadAudio(url);
        } else {
            result = await MediaDownloader.downloadVideo(url);
        }
        
        console.log('=' .repeat(60));
        console.log('✅ 下载成功！');
        console.log('=' .repeat(60));
        console.log('');
        console.log(`📂 文件路径: ${result.filePath}`);
        console.log(`🔗 安全路径: ${result.safePath}`);
        console.log('');
        
        // 生成 AE 导入脚本
        console.log('🎬 正在生成 AE 导入脚本...');
        const importCmd = AEImporter.prepareImportCommand(result.filePath, "Phase7_Download");
        const jsxPath = path.join(__dirname, '..', '05-测试套件', 'Phase7_Import_Downloaded.jsx');
        const fs = require('fs');
        fs.writeFileSync(jsxPath, importCmd.scriptContent, 'utf8');
        
        console.log('✅ AE 导入脚本已生成！');
        console.log(`📄 脚本路径: ${jsxPath}`);
        console.log('');
        console.log('🚀 下一步: 在 After Effects 中运行 Phase7_Import_Downloaded.jsx');
        console.log('');
        
    } catch (e) {
        console.error('❌ 下载失败:', e.message);
        process.exit(1);
    }
}

main();
