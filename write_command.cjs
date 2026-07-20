// 将 deep_analysis_v5.jsx 写入 ae_command.json
const fs = require('fs');
const path = require('path');

const jsxPath = 'C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\deep_analysis_v5.jsx';
const jsonPath = 'C:\\Users\\Administrator\\Documents\\ae-mcp-bridge\\ae_command.json';

const scriptContent = fs.readFileSync(jsxPath, 'utf8');

const command = {
    args: {
        scriptContent: scriptContent,
        scriptName: 'deep_analysis_v5',
        dryRun: false
    },
    command: 'executeAtomScript'
};

fs.writeFileSync(jsonPath, JSON.stringify(command, null, 4), 'utf8');
console.log('命令文件已写入: ' + jsonPath);
console.log('脚本长度: ' + scriptContent.length + ' 字符');
