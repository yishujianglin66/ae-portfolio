const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('🚀 MCP 直接测试启动...\n');

// 获取AE临时目录
function getAETempDir() {
  const homeDir = os.homedir();
  const bridgeDir = path.join(homeDir, 'Documents', 'ae-mcp-bridge');
  if (!fs.existsSync(bridgeDir)) {
    fs.mkdirSync(bridgeDir, { recursive: true });
    console.log('📁 创建桥接目录:', bridgeDir);
  }
  return bridgeDir;
}

const bridgeDir = getAETempDir();
const commandFile = path.join(bridgeDir, 'ae_command.json');
const resultFile = path.join(bridgeDir, 'ae_mcp_result.json');

console.log('📂 桥接目录:', bridgeDir);
console.log('📄 命令文件:', commandFile);
console.log('📄 结果文件:', resultFile);

// 测试素材路径
const testImage = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
console.log('🎨 测试素材:', testImage);

// 写入命令函数
function writeCommand(command, args) {
  const commandData = {
    command,
    args,
    timestamp: new Date().toISOString(),
    status: "pending"
  };
  fs.writeFileSync(commandFile, JSON.stringify(commandData, null, 2));
  console.log('\n✅ 命令已发送:', command);
  console.log('📝 参数:', JSON.stringify(args, null, 2));
}

// 重置结果文件
function clearResults() {
  const resetData = {
    status: "waiting",
    message: "Waiting for new result from After Effects...",
    timestamp: new Date().toISOString()
  };
  fs.writeFileSync(resultFile, JSON.stringify(resetData, null, 2));
  console.log('🧹 结果文件已重置');
}

console.log('\n' + '='.repeat(60));
console.log('📋 测试步骤');
console.log('='.repeat(60));
console.log('');
console.log('步骤 1: 创建测试合成');
console.log('步骤 2: 导入测试素材');
console.log('步骤 3: 导入素材到合成');
console.log('');
console.log('='.repeat(60));
console.log('');

// 开始第一个测试
clearResults();
writeCommand('createComposition', {
  name: 'MCP_Test_Comp',
  width: 1920,
  height: 1080,
  duration: 10,
  frameRate: 30
});

console.log('\n🎉 请在 After Effects 中打开 "MCP Bridge Auto" 面板！');
console.log('   面板将自动检测并执行命令！');
console.log('\n📋 后续步骤：');
console.log('   1. 检查AE中是否创建了 MCP_Test_Comp');
console.log('   2. 然后我们继续测试导入功能');
