/**
 * AE原子参数编译器 - CLI
 * --------------------------------
 * 命令行接口: 读取JSON文件 → 编译 → 输出.jsx文件
 *
 * 用法:
 *   node cli.js compile input.json -o output.jsx
 *   node cli.js compile input.json --stdout
 *   cat input.json | node cli.js compile --stdin
 *
 * @module apc/cli
 */

import * as fs from "fs";
import * as path from "path";
import { compile, compileJSON, type CompileOptions } from "./index.js";

interface CLIArgs {
  command: string;
  input?: string;
  output?: string;
  stdin?: boolean;
  stdout?: boolean;
  skipValidation?: boolean;
  pretty?: boolean;
}

function parseArgs(argv: string[]): CLIArgs {
  const args: CLIArgs = {
    command: "",
    stdin: false,
    stdout: false,
    skipValidation: false,
    pretty: false,
  };

  const positional: string[] = [];
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-o" || arg === "--output") {
      args.output = argv[++i];
    } else if (arg === "--stdin") {
      args.stdin = true;
    } else if (arg === "--stdout") {
      args.stdout = true;
    } else if (arg === "--skip-validation") {
      args.skipValidation = true;
    } else if (arg === "--pretty") {
      args.pretty = true;
    } else if (arg === "-h" || arg === "--help") {
      printHelp();
      process.exit(0);
    } else if (arg === "-v" || arg === "--version") {
      console.log("ae-atomic-compiler v0.1.0");
      process.exit(0);
    } else if (!arg.startsWith("-")) {
      if (!args.command) {
        args.command = arg;
      } else {
        positional.push(arg);
      }
    }
  }

  if (positional.length > 0 && !args.input) {
    args.input = positional[0];
  }

  return args;
}

function printHelp(): void {
  console.log(`
AE原子参数编译器 (APC) v0.1.0

用法:
  ae-compile compile <input.json> [-o output.jsx] [选项]
  cat input.json | ae-compile compile --stdin [--stdout]

命令:
  compile   编译JSON文件为ExtendScript代码

选项:
  -o, --output <file>     输出到文件
  --stdout                输出到标准输出
  --stdin                 从标准输入读取
  --skip-validation       跳过输入验证
  --pretty                美化输出
  -h, --help              显示帮助
  -v, --version           显示版本

示例:
  ae-compile compile input.json -o output.jsx
  ae-compile compile input.json --stdout
  cat input.json | ae-compile compile --stdin --stdout
`);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv);

  if (args.command !== "compile") {
    printHelp();
    process.exit(1);
  }

  // 读取输入
  let inputStr: string;
  if (args.stdin) {
    inputStr = await readStdin();
  } else if (args.input) {
    if (!fs.existsSync(args.input)) {
      console.error(`错误: 输入文件不存在: ${args.input}`);
      process.exit(1);
    }
    inputStr = fs.readFileSync(args.input, "utf8");
  } else {
    console.error("错误: 必须提供输入文件或使用 --stdin");
    process.exit(1);
  }

  // 编译
  const options: CompileOptions = {
    skipValidation: args.skipValidation,
  };

  const result = compileJSON(inputStr, options);

  // 输出结果
  if (!result.success) {
    console.error("编译失败:");
    for (const err of result.errors) {
      console.error(`  [${err.code}] ${err.message}`);
    }
    process.exit(1);
  }

  // 输出脚本
  if (args.stdout || !args.output) {
    console.log(result.script);
  }

  if (args.output) {
    const outDir = path.dirname(args.output);
    if (outDir && !fs.existsSync(outDir)) {
      fs.mkdirSync(outDir, { recursive: true });
    }
    fs.writeFileSync(args.output, result.script, "utf8");
    if (!args.stdout) {
      console.log(`编译成功: ${args.output}`);
    }
  }

  // 输出统计
  if (args.pretty) {
    console.error("\n--- 编译统计 ---");
    console.error(`操作数: ${result.stats.operationCount}`);
    console.error(`IR节点数: ${result.stats.irNodeCount}`);
    console.error(`脚本大小: ${result.stats.scriptSize} 字节`);
    console.error(`编译时间: ${result.stats.compileTimeMs}ms`);
    if (result.warnings.length > 0) {
      console.error(`警告: ${result.warnings.length}`);
      for (const w of result.warnings) {
        console.error(`  ${w}`);
      }
    }
  }
}

function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => {
      resolve(data);
    });
    process.stdin.on("error", reject);
  });
}

main().catch((err) => {
  console.error("未捕获错误:", err);
  process.exit(1);
});
