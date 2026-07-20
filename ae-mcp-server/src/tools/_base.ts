import { z } from 'zod';
import { defaultBridge, BridgeResult } from '../bridge.js';

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, z.ZodType<any>>;
  handler: (args: any) => Promise<any>;
}

export function createTool(
  name: string,
  description: string,
  inputSchema: Record<string, z.ZodType<any>>,
  scriptCommand: string
): ToolDefinition {
  return {
    name,
    description,
    inputSchema,
    handler: async (args: any) => {
      const result = await defaultBridge.executeCommand(scriptCommand, args);
      return handleBridgeResult(result);
    },
  };
}

export function handleBridgeResult(result: BridgeResult): any {
  if (result.status === 'success') {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } else {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
      isError: true,
    };
  }
}

export { defaultBridge };
