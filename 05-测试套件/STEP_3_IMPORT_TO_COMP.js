const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('🚀 MCP 测试步骤 3/3: 导入素材到合成\n');

// 获取AE临时目录
function getAETempDir() {
  const homeDir = os.homedir();
  const bridgeDir = path.join(homeDir, 'Documents', 'ae-mcp-bridge');
  return bridgeDir;
}

const bridgeDir = getAETempDir();
const commandFile = path.join(bridgeDir, 'ae_command.json');
const resultFile = path.join(bridgeDir, 'ae_mcp_result.json');
const testImage = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";

// 写入命令
function writeCommand(command, args) {
  const commandData = {
    command,
    args,
    timestamp: new Date().toISOString(),
    status: "pending"
  };
  fs.writeFileSync(commandFile, JSON.stringify(commandData, null, 2));
}

// 重置结果文件
function clearResults() {
  const resetData = {
    status: "waiting",
    message: "Waiting for new result from After Effects...",
    timestamp: new Date().toISOString()
  };
  fs.writeFileSync(resultFile, JSON.stringify(resetData, null, 2));
}

console.log('='.repeat(70));
console.log('📋 步骤 3/3: 导入素材到合成');
console.log('='.repeat(70));
console.log('');

// 开始测试3
clearResults();
writeCommand('importFootage', {
  filePath: testImage,
  compName: 'MCP_Test_Comp'
});

console.log('✅ 导入素材到合成命令已发送');
console.log('');
console.log('📄 素材路径:', testImage);
console.log('📄 目标合成: MCP_Test_Comp');
console.log('');
console.log('💡 请检查:');
console.log('   1. AE 项目面板有素材');
console.log('   2. MCP_Test_Comp 合成中有这个素材图层');
console.log('');
console.log('🎉 恭喜！完整测试完成！');
console.log('');
console.log('='.repeat(70));
