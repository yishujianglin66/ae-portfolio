const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('=== STEP: USING executeAtomScript (FINAL FIX) ===');

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

// IMPORTANT: Use FORWARD SLASHES for the path in the script!
const testImage = "c:/Users/Administrator/Desktop/AE-Knowledge-Vault/05-测试套件/test_resources/test_image.png";

// Clear results first
console.log('Clearing previous results...');
const resetData = {
  status: "waiting",
  message: "Waiting for final fixed test...",
  timestamp: new Date().toISOString()
};
fs.writeFileSync(resultFile, JSON.stringify(resetData, null, 2));

// The FINAL FIXED script - Using FORWARD SLASHES in path!
const scriptContent = `(function() {
  app.beginUndoGroup("MCP Test - Final Full Import");

  var testResults = [];

  try {
    // Step 1: Create composition
    var comp = app.project.items.addComp("MCP_Test_FINAL", 1920, 1080, 1, 10, 30);
    comp.bgColor = [0, 0, 0];
    testResults.push({
      step: 1,
      name: "Create Comp",
      status: "success",
      details: "Created comp: " + comp.name
    });

    // Step 2: Import footage - USE FORWARD SLASHES!
    var file = new File("${testImage}");
    if (!file.exists) {
      testResults.push({
        step: 2,
        name: "Import Footage",
        status: "error",
        details: "File not found at: " + "${testImage}"
      });
    } else {
      var importOptions = new ImportOptions(file);
      var footage = app.project.importFile(importOptions);
      testResults.push({
        step: 2,
        name: "Import Footage",
        status: "success",
        details: "Imported: " + footage.name
      });

      // Step 3: Add to comp and center
      var layer = comp.layers.add(footage);
      layer.property("Position").setValue([comp.width/2, comp.height/2]);
      testResults.push({
        step: 3,
        name: "Add to Comp",
        status: "success",
        details: "Added layer index: " + layer.index
      });
    }
  } catch(e) {
    testResults.push({
      step: "error",
      name: "Exception",
      status: "error",
      details: e.toString()
    });
  }

  app.endUndoGroup();

  return {
    success: true,
    testResults: testResults
  };
})();`;

// Send executeAtomScript command
const commandData = {
  command: "executeAtomScript",
  args: {
    scriptContent: scriptContent
  },
  timestamp: new Date().toISOString(),
  status: "pending"
};

fs.writeFileSync(commandFile, JSON.stringify(commandData, null, 2));

console.log('✅ FINAL executeAtomScript command sent!');
console.log('  Path fixed with FORWARD SLASHES!');
console.log('');
console.log('Now:');
console.log('1. Click "Check for Commands Now" in AE panel');
console.log('2. This time it should IMPORT the footage!');
