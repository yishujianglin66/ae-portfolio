/**
 * AE原子参数编译器 - 主入口
 * --------------------------------
 * 整合 Validator → IR Builder → Scheduler → Code Generator
 *
 * @module apc/index
 */

import { validate } from "./validator.js";
import { buildIR } from "./ir-builder.js";
import { schedule } from "./scheduler.js";
import { generateCode } from "./codegen.js";
import type { CompilerInput, CompileResult, CompileError } from "./types.js";

/**
 * 编译器选项
 */
export interface CompileOptions {
  /** 跳过验证 (仅用于测试) */
  skipValidation?: boolean;
  /** 跳过排序 (保持原顺序) */
  skipScheduling?: boolean;
  /** 生成代码时是否包含头部注释 */
  includeHeader?: boolean;
  /** 输出格式 */
  outputFormat?: "script" | "mcp-commands";
}

/**
 * 默认选项
 */
const DEFAULT_OPTIONS: Required<CompileOptions> = {
  skipValidation: false,
  skipScheduling: false,
  includeHeader: true,
  outputFormat: "script",
};

/**
 * 主编译函数
 * 输入: 原子参数JSON
 * 输出: ExtendScript代码 + 错误/警告
 */
export function compile(input: CompilerInput, options: CompileOptions = {}): CompileResult {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const startTime = Date.now();
  const errors: CompileError[] = [];
  const warnings: string[] = [];

  // 1. 验证
  if (!opts.skipValidation) {
    const validationResult = validate(input);
    if (!validationResult.valid) {
      return {
        success: false,
        script: "",
        errors: validationResult.errors,
        warnings: validationResult.warnings,
        stats: {
          operationCount: input.operations.length,
          irNodeCount: 0,
          scriptSize: 0,
          compileTimeMs: Date.now() - startTime,
        },
      };
    }
    warnings.push(...validationResult.warnings);
  }

  // 2. 构建IR
  const irResult = buildIR(input);
  if (irResult.errors.length > 0) {
    errors.push(...irResult.errors.map((e) => ({ code: "IR", message: e.message })));
  }

  // 3. 调度 (拓扑排序)
  let nodes = irResult.nodes;
  if (!opts.skipScheduling) {
    const scheduleResult = schedule(nodes);
    nodes = scheduleResult.sorted;
    if (scheduleResult.errors.length > 0) {
      errors.push(...scheduleResult.errors.map((e) => ({ code: "SCHED", message: e.message })));
    }
  }

  // 4. 代码生成
  const codegenResult = generateCode(nodes);
  if (codegenResult.errors.length > 0) {
    errors.push(...codegenResult.errors.map((e) => ({ code: "CODEGEN", message: e.message })));
  }

  const compileTimeMs = Date.now() - startTime;

  return {
    success: errors.length === 0,
    script: codegenResult.script,
    errors,
    warnings,
    stats: {
      operationCount: input.operations.length,
      irNodeCount: nodes.length,
      scriptSize: codegenResult.script.length,
      compileTimeMs,
    },
  };
}

/**
 * 从JSON字符串编译
 */
export function compileJSON(jsonString: string, options?: CompileOptions): CompileResult {
  try {
    const input = JSON.parse(jsonString) as CompilerInput;
    return compile(input, options);
  } catch (e) {
    return {
      success: false,
      script: "",
      errors: [
        {
          code: "E001",
          message: `JSON解析失败: ${String(e)}`,
        },
      ],
      warnings: [],
      stats: {
        operationCount: 0,
        irNodeCount: 0,
        scriptSize: 0,
        compileTimeMs: 0,
      },
    };
  }
}

// ============ 导出所有模块 ============

export * from "./types.js";
export { validate } from "./validator.js";
export { buildIR } from "./ir-builder.js";
export { schedule } from "./scheduler.js";
export { generateCode } from "./codegen.js";
