const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('🚀 MCP 完整自动化测试启动...\n');

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
const projectDir = path.join(__dirname, '..');
const testImage = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";

console.log('📂 桥接目录:', bridgeDir);
console.log('📂 项目目录:', projectDir);
console.log('🎨 测试素材:', testImage);
console.log('');

// 检查素材是否存在
if (!fs.existsSync(testImage)) {
  console.log('❌ 测试素材未找到!');
  process.exit(1);
}
console.log('✅ 测试素材已就绪');

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

console.log('\n' + '='.repeat(70));
console.log('🎬 MCP 素材导入完整测试流程');
console.log('='.repeat(70));
console.log('');
console.log('📋 请确保以下内容已准备好：');
console.log('   1. After Effects 已打开');
console.log('   2. 项目已保存');
console.log('   3. "MCP Bridge Auto" 面板已打开（显示 Ready）');
console.log('');
console.log('='.repeat(70));
console.log('');
console.log('📋 测试步骤:');
console.log('');
console.log('1️⃣  创建测试合成 (MCP_Test_Comp)');
console.log('2️⃣  导入素材到项目');
console.log('3️⃣  导入素材到合成');
console.log('');
console.log('='.repeat(70));
console.log('');

// 开始测试1
clearResults();
writeCommand('createComposition', {
  name: 'MCP_Test_Comp',
  width: 1920,
  height: 1080,
  duration: 10,
  frameRate: 30
});

console.log('✅ 步骤 1/3: 创建合成命令已发送');
console.log('');
console.log('📄 现在请:');
console.log('   1. 检查 AE 中 "MCP Bridge Auto" 面板是否检测到命令');
console.log('   2. 确认 MCP_Test_Comp 已创建');
console.log('   3. 然后继续下一步测试');
console.log('');
console.log('💡 提示: 查看 AE 项目面板，应该有 MCP_Test_Comp 合成');
console.log('');
console.log('='.repeat(70));
