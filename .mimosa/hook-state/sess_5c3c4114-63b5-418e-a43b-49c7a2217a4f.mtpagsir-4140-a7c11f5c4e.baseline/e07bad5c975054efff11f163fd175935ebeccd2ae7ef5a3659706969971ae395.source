const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('=== STEP 1: IMPORT FOOTAGE ONLY ===');

// Get bridge paths
function getAETempDir() {
  const homeDir = os.homedir();
  const bridgeDir = path.join(homeDir, 'Documents', 'ae-mcp-bridge');
  if (!fs.existsSync(bridgeDir)) {
    fs.mkdirSync(bridgeDir, { recursive: true });
  }
  return bridgeDir;
}

const bridgeDir = getAETempDir();
const commandFile = path.join(bridgeDir, 'ae_command.json');
const resultFile = path.join(bridgeDir, 'ae_mcp_result.json');

const testImage = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";

// Clear results first
console.log('Clearing previous results...');
const resetData = {
  status: "waiting",
  message: "Waiting for importFootage...",
  timestamp: new Date().toISOString()
};
fs.writeFileSync(resultFile, JSON.stringify(resetData, null, 2));

// Send importFootage command ONLY - no compName
const commandData = {
  command: "importFootage",
  args: {
    filePath: testImage
  },
  timestamp: new Date().toISOString(),
  status: "pending"
};

fs.writeFileSync(commandFile, JSON.stringify(commandData, null, 2));

console.log('✅ importFootage command sent!');
console.log('');
console.log('Now:');
console.log('1. Check AE "MCP Bridge Auto" panel - should see logs');
console.log('2. Click "Check for Commands Now" if needed');
console.log('3. Check if test_image.png is in AE project');
