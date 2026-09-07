import * as fs from 'fs';
import * as path from 'path';

export interface BridgeCommand {
  command: string;
  args: Record<string, any>;
  timestamp: number;
}

export interface BridgeResult {
  status: 'success' | 'error';
  data?: Record<string, any>;
  message?: string;
  errorCode?: string;
  [key: string]: any;
}

export interface BridgeOptions {
  bridgeDir: string;
  pollIntervalMs: number;
  timeoutMs: number;
}

const DEFAULT_OPTIONS: BridgeOptions = {
  bridgeDir: 'C:\\Users\\Administrator\\Documents\\ae-mcp-bridge',
  pollIntervalMs: 500,
  timeoutMs: 30000,
};

const MAX_RETRIES = 2;

export class AEBridge {
  private options: BridgeOptions;
  private commandPath: string;
  private resultPath: string;
  private logPath: string;
  private tempDir: string;
  private argsPath: string;

  constructor(options?: Partial<BridgeOptions>) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this.commandPath = path.join(this.options.bridgeDir, 'command.json');
    this.resultPath = path.join(this.options.bridgeDir, 'result.json');
    this.logPath = path.join(this.options.bridgeDir, 'bridge.log');
    this.tempDir = path.join(this.options.bridgeDir, 'temp');
    this.argsPath = path.join(this.tempDir, 'args.json');
    this.ensureDirs();
  }

  private ensureDirs(): void {
    try {
      if (!fs.existsSync(this.options.bridgeDir)) {
        fs.mkdirSync(this.options.bridgeDir, { recursive: true });
      }
      if (!fs.existsSync(this.tempDir)) {
        fs.mkdirSync(this.tempDir, { recursive: true });
      }
    } catch (e) {
      console.error(`[Bridge] 初始化目录失败: ${e}`);
    }
  }

  private log(message: string, level: 'info' | 'error' | 'warn' = 'info'): void {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] [${level.toUpperCase()}] ${message}\n`;
    try {
      fs.appendFileSync(this.logPath, logLine, 'utf-8');
    } catch (e) {
    }
  }

  private atomicWrite(filePath: string, data: string): void {
    const tmpPath = filePath + '.tmp';
    fs.writeFileSync(tmpPath, data, 'utf-8');
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }
    fs.renameSync(tmpPath, filePath);
  }

  private readJsonFile<T>(filePath: string): T | null {
    try {
      if (!fs.existsSync(filePath)) {
        return null;
      }
      const content = fs.readFileSync(filePath, 'utf-8');
      if (!content.trim()) {
        return null;
      }
      return JSON.parse(content) as T;
    } catch (e) {
      return null;
    }
  }

  private deleteIfExists(filePath: string): void {
    try {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    } catch (e) {
    }
  }

  async executeCommand(command: string, args: Record<string, any>): Promise<BridgeResult> {
    const timestamp = Date.now();
    this.log(`执行命令: ${command}`);

    let lastError: Error | null = null;
    for (let attempt = 1; attempt <= MAX_RETRIES + 1; attempt++) {
      try {
        this.deleteIfExists(this.resultPath);
        this.deleteIfExists(this.commandPath);

        const cmdData: BridgeCommand = {
          command,
          args,
          timestamp: timestamp + attempt,
        };

        this.atomicWrite(this.argsPath, JSON.stringify(args, null, 2));
        this.atomicWrite(this.commandPath, JSON.stringify(cmdData, null, 2));

        if (attempt > 1) {
          this.log(`第 ${attempt} 次重试...`);
        }
        this.log(`命令已写入: ${command}, 等待结果... (超时: ${this.options.timeoutMs}ms)`);

        const result = await this.waitForResult(cmdData.timestamp);

        if (result.status === 'success') {
          this.log(`命令执行成功: ${command}`);
        } else {
          this.log(`命令执行失败: ${command} - ${result.message || result.errorCode}`, 'error');
        }

        return result;
      } catch (error: any) {
        lastError = error;
        this.log(`命令执行异常 (尝试 ${attempt}/${MAX_RETRIES + 1}): ${command} - ${error.message}`, 'error');
        if (attempt <= MAX_RETRIES) {
          await new Promise(r => setTimeout(r, 1000 * attempt));
        }
      }
    }

    this.log(`命令最终失败 (${MAX_RETRIES + 1} 次尝试): ${command}`, 'error');
    return {
      status: 'error',
      errorCode: 'BRIDGE_ERROR',
      message: `桥接通信失败 (${MAX_RETRIES + 1} 次尝试后放弃): ${lastError?.message}`,
    };
  }

  private waitForResult(originalTimestamp: number): Promise<BridgeResult> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      let pollCount = 0;

      const poll = () => {
        pollCount++;

        try {
          const result = this.readJsonFile<BridgeResult>(this.resultPath);

          if (result) {
            resolve(result);
            return;
          }
        } catch (e) {
        }

        const elapsed = Date.now() - startTime;
        if (elapsed >= this.options.timeoutMs) {
          reject(new Error(`命令超时 (${this.options.timeoutMs}ms)`));
          return;
        }

        setTimeout(poll, this.options.pollIntervalMs);
      };

      setTimeout(poll, this.options.pollIntervalMs);
    });
  }

  getBridgeDir(): string {
    return this.options.bridgeDir;
  }

  getTempDir(): string {
    return this.tempDir;
  }
}

export const defaultBridge = new AEBridge();
