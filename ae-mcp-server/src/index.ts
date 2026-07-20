import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { tools } from './tools/index.js';
import { defaultBridge } from './bridge.js';

async function main(): Promise<void> {
  const server = new McpServer({
    name: 'ae-mcp-server',
    version: '1.0.0',
  });

  console.error(`[AE MCP Server] 启动中...`);
  console.error(`[AE MCP Server] 桥接目录: ${defaultBridge.getBridgeDir()}`);

  for (const tool of tools) {
    console.error(`[AE MCP Server] 注册工具: ${tool.name}`);

    (server as any).registerTool(
      tool.name,
      {
        description: tool.description,
        inputSchema: tool.inputSchema,
      },
      async (args: any) => {
        console.error(`[AE MCP Server] 执行工具: ${tool.name}`);
        return tool.handler(args);
      }
    );
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error(`[AE MCP Server] 已就绪，等待 MCP 客户端连接...`);
}

main().catch((error) => {
  console.error('[AE MCP Server] 启动失败:', error);
  process.exit(1);
});
