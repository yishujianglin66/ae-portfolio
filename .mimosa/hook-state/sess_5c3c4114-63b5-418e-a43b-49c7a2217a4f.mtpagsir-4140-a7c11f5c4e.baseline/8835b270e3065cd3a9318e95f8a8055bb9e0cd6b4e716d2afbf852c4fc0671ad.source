const fs = require('fs');
const path = require('path');
const os = require('os');

console.log('🚀 MCP 测试命令写入器启动...\n');

// 获取 AE 临时目录
function getAETempDir() {
    const homeDir = os.homedir();
    const bridgeDir = path.join(homeDir, 'Documents', 'ae-mcp-bridge');
    // 确保目录存在
    if (!fs.existsSync(bridgeDir)) {
        fs.mkdirSync(bridgeDir, { recursive: true });
        console.log('📁 创建目录:', bridgeDir);
    }
    return bridgeDir;
}

// 写入命令文件
function writeCommand(command, args) {
    const bridgeDir = getAETempDir();
    const commandFile = path.join(bridgeDir, 'ae_command.json');
    
    const commandData = {
        command,
        args,
        timestamp: new Date().toISOString(),
        status: "pending"
    };
    
    fs.writeFileSync(commandFile, JSON.stringify(commandData, null, 2));
    console.log('✅ 命令已写入:', commandFile);
    console.log('📋 命令:', command);
    console.log('📝 参数:', JSON.stringify(args, null, 2));
    return commandFile;
}

// 清除结果文件
function clearResults() {
    const bridgeDir = getAETempDir();
    const resultFile = path.join(bridgeDir, 'ae_mcp_result.json');
    
    const resetData = {
        status: "waiting",
        message: "Waiting for new result from After Effects...",
        timestamp: new Date().toISOString()
    };
    
    fs.writeFileSync(resultFile, JSON.stringify(resetData, null, 2));
    console.log('🧹 结果文件已重置');
}

// 主函数
function main() {
    const args = process.argv.slice(2);
    
    if (args.length < 1) {
        console.log('❌ 请指定命令');
        console.log('\n使用方法:');
        console.log('  node run_mcp_commands.js createComposition <name> <width> <height> <duration> <fps>');
        console.log('  node run_mcp_commands.js importFootage <filePath> [compName]');
        console.log('\n示例:');
        console.log('  node run_mcp_commands.js createComposition MCP_Test_Comp 1920 1080 10 30');
        process.exit(1);
    }
    
    const command = args[0];
    
    switch (command) {
        case 'createComposition':
            if (args.length < 6) {
                console.log('❌ 参数不足！');
                console.log('使用: createComposition <name> <width> <height> <duration> <fps>');
                process.exit(1);
            }
            clearResults();
            writeCommand('createComposition', {
                name: args[1],
                width: parseInt(args[2]),
                height: parseInt(args[3]),
                duration: parseFloat(args[4]),
                frameRate: parseFloat(args[5])
            });
            break;
            
        case 'importFootage':
            if (args.length < 2) {
                console.log('❌ 请指定素材路径！');
                process.exit(1);
            }
            clearResults();
            const importArgs = { filePath: args[1] };
            if (args[2]) importArgs.compName = args[2];
            writeCommand('importFootage', importArgs);
            break;
            
        default:
            console.log('❌ 未知命令:', command);
            process.exit(1);
    }
    
    console.log('\n🎉 命令已发送！请检查 After Effects 的 "MCP Bridge Auto" 面板');
    console.log('📋 下一步: 使用 get-results 工具获取执行结果');
}

main();
