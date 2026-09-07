const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('🚀 MCP 素材导入测试启动...\n');

// 检查项目路径
const projectDir = path.join(__dirname, '..');
const testResourcesDir = path.join(projectDir, '05-测试套件', 'test_resources');

console.log('📂 项目目录:', projectDir);
console.log('📂 测试资源目录:', testResourcesDir);

// 检查测试素材是否存在
const testImage = path.join(testResourcesDir, 'test_image.png');
if (fs.existsSync(testImage)) {
    console.log('✅ 测试素材找到:', testImage);
} else {
    console.log('❌ 测试素材未找到:', testImage);
}

// 创建测试说明
console.log('\n' + '='.repeat(60));
console.log('📋 测试说明：');
console.log('='.repeat(60));
console.log('');
console.log('1. 确保 After Effects 已打开并保存了项目');
console.log('2. 确保 "MCP Bridge Auto" 面板已打开并显示 "Ready - Auto-run is ON"');
console.log('3. 在 AE 中运行脚本: 05-测试套件/MCP_RunTestViaBridge.jsx');
console.log('4. 测试完成后，结果会保存到: mcp_test_result.json');
console.log('');
console.log('='.repeat(60));
console.log('');

console.log('📝 测试脚本位置:');
console.log('   ' + path.join(__dirname, 'MCP_RunTestViaBridge.jsx'));
console.log('');
console.log('现在请在 After Effects 中运行上述脚本！');
