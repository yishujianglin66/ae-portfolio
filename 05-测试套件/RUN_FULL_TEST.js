const fs = require('fs');
const path = require('path');

console.log('🚀 MCP 完整测试执行器启动...\n');

// 项目目录
const projectDir = path.join(__dirname, '..');
const testResourcesDir = path.join(projectDir, '05-测试套件', 'test_resources');

console.log('📂 项目目录:', projectDir);
console.log('📂 测试资源目录:', testResourcesDir);

// 检查测试素材
const testImage = path.join(testResourcesDir, 'test_image.png');
if (fs.existsSync(testImage)) {
    console.log('✅ 测试素材找到:', testImage);
} else {
    console.log('❌ 测试素材未找到:', testImage);
    process.exit(1);
}

console.log('\n' + '='.repeat(60));
console.log('📋 测试说明');
console.log('='.repeat(60));
console.log('');
console.log('请在 After Effects 中运行以下脚本文件：');
console.log('');
console.log('📄 ' + path.join(__dirname, 'AE_MCP_AutoTest.jsx'));
console.log('');
console.log('运行后，测试报告将保存到：');
console.log('📄 ' + path.join(projectDir, 'mcp_test_result.json'));
console.log('');
console.log('='.repeat(60));
console.log('');
console.log('现在请在 After Effects 中运行 AE_MCP_AutoTest.jsx！');
