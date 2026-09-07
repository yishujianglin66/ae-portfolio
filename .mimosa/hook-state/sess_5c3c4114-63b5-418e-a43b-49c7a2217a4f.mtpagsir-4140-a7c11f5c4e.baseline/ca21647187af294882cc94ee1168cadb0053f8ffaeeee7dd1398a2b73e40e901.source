/**
 * LLM 网关层 - LLMGateway TypeScript 版
 *
 * 设计原则（基于 OmniRoute 架构 + Caveman 压缩）：
 * 1. 统一接口：兼容 OpenAI API 格式，支持任意 OmniRoute 网关
 * 2. 智能路由：根据任务类型自动选择最优模型
 * 3. 自动降级：Provider 失败时自动 failover 到备用
 * 4. Token 优化：集成压缩语法（Caveman 风格）
 * 5. 可观测：内置 token 用量追踪和成本监控
 *
 * 参考项目：
 * - OmniRoute (diegosouzapw/OmniRoute) — 多 Provider AI 网关
 * - Caveman (JuliusBrussee/caveman) — Token 压缩语法
 */

export type TaskType =
  | "intent_classification"
  | "scene_description"
  | "effect_planning"
  | "quality_review"
  | "feedback_analysis"
  | "general";

export type ProviderStatus = "healthy" | "degraded" | "unavailable";

export interface LLMConfig {
  baseUrl: string;
  apiKey: string;
  defaultModel: string;
  timeoutSeconds: number;
  maxRetries: number;
  retryDelayMs: number;
  enableCompression: boolean;
  enableFallback: boolean;
  modelRouting: Record<TaskType, string>;
  fallbackProviders: Array<{ baseUrl: string; apiKey: string }>;
}

export interface LLMResponse {
  content: string;
  model: string;
  provider: string;
  tokensInput: number;
  tokensOutput: number;
  latencyMs: number;
  success: boolean;
  error: string;
  raw?: Record<string, any>;
}

export interface ProviderHealth {
  name: string;
  status: ProviderStatus;
  consecutiveFailures: number;
  lastSuccessTime: number;
  lastError: string;
  totalRequests: number;
  totalFailures: number;
}

const DEFAULT_CONFIG: LLMConfig = {
  baseUrl: "http://localhost:5273/v1",
  apiKey: "",
  defaultModel: "auto",
  timeoutSeconds: 30,
  maxRetries: 3,
  retryDelayMs: 1000,
  enableCompression: true,
  enableFallback: true,
  modelRouting: {
    intent_classification: "auto",
    scene_description: "auto",
    effect_planning: "auto",
    quality_review: "auto",
    feedback_analysis: "auto",
    general: "auto",
  },
  fallbackProviders: [],
};

/**
 * Token 压缩器 — 参考 caveman 项目的压缩语法
 */
export class TokenCompressor {
  private static COMPRESSION_PROMPT =
    "回复须简洁如穴居人：省略冠词/连接词/客套话，" +
    "仅保留技术要点。用'|'分隔条目。";

  private static COMPRESSION_MAP: Record<string, string> = {
    "请详细分析": "分析",
    "请生成": "生成",
    "请描述": "描述",
    "你需要": "须",
    "你应该": "须",
    "请注意": "注意",
    "非常重要": "重要",
    "请确保": "确保",
    "这是一个": "这是",
    "以下是": "如下",
  };

  compressPrompt(prompt: string): string {
    let compressed = prompt;
    for (const [long, short] of Object.entries(TokenCompressor.COMPRESSION_MAP)) {
      compressed = compressed.split(long).join(short);
    }
    return compressed;
  }

  compressSystem(system: string): string {
    const compressed = this.compressPrompt(system);
    if (compressed.length > 200) {
      return compressed.slice(0, 200) + "...";
    }
    return compressed;
  }

  getCompressionSuffix(): string {
    return `\n[${TokenCompressor.COMPRESSION_PROMPT}]`;
  }

  decompressResponse(response: string): string {
    if (!response) return response;

    const parts = response.split("|").map((s) => s.trim()).filter(Boolean);
    if (parts.length <= 1) return response;

    return parts.join("\n");
  }
}

/**
 * LLM 网关 — 统一的 LLM 调用入口
 */
export class LLMGateway {
  private config: LLMConfig;
  private compressor: TokenCompressor;
  private providerHealth: Map<string, ProviderHealth>;
  private stats: {
    totalRequests: number;
    totalSuccesses: number;
    totalFailures: number;
    totalTokensInput: number;
    totalTokensOutput: number;
    totalLatencyMs: number;
  };

  constructor(config?: Partial<LLMConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.compressor = new TokenCompressor();
    this.providerHealth = new Map();
    this.stats = {
      totalRequests: 0,
      totalSuccesses: 0,
      totalFailures: 0,
      totalTokensInput: 0,
      totalTokensOutput: 0,
      totalLatencyMs: 0,
    };
    this.initProviderHealth();
  }

  private initProviderHealth(): void {
    const primaryName = this.extractProviderName(this.config.baseUrl);
    this.providerHealth.set(primaryName, {
      name: primaryName,
      status: "healthy",
      consecutiveFailures: 0,
      lastSuccessTime: 0,
      lastError: "",
      totalRequests: 0,
      totalFailures: 0,
    });

    for (const fb of this.config.fallbackProviders) {
      const name = this.extractProviderName(fb.baseUrl);
      if (!this.providerHealth.has(name)) {
        this.providerHealth.set(name, {
          name,
          status: "healthy",
          consecutiveFailures: 0,
          lastSuccessTime: 0,
          lastError: "",
          totalRequests: 0,
          totalFailures: 0,
        });
      }
    }
  }

  private extractProviderName(url: string): string {
    if (!url) return "unknown";
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  }

  configure(config: Partial<LLMConfig>): void {
    this.config = { ...this.config, ...config };
    this.initProviderHealth();
    console.info(`[LLMGateway] 配置已更新: ${this.config.baseUrl}`);
  }

  configureFromEnv(env: Record<string, string> = {}): void {
    const baseUrl =
      env.AEKV_LLM_BASE_URL || env.OPENAI_BASE_URL ||
      env.MODELSCOPE_BASE_URL || this.config.baseUrl;
    const apiKey =
      env.AEKV_LLM_API_KEY || env.OPENAI_API_KEY ||
      env.MODELSCOPE_API_KEY || this.config.apiKey;
    const model = env.AEKV_LLM_MODEL || env.MODELSCOPE_MODEL || this.config.defaultModel;

    this.config.baseUrl = baseUrl;
    this.config.apiKey = apiKey;
    this.config.defaultModel = model;

    const fallbacksStr = env.AEKV_LLM_FALLBACKS;
    if (fallbacksStr) {
      try {
        this.config.fallbackProviders = JSON.parse(fallbacksStr);
      } catch {
        console.warn("[LLMGateway] 降级 Provider 解析失败");
      }
    }

    this.initProviderHealth();
  }

  isAvailable(): boolean {
    return !!this.config.baseUrl && !!this.config.apiKey;
  }

  async chat(params: {
    message: string;
    systemPrompt?: string;
    model?: string;
    temperature?: number;
    maxTokens?: number;
    useCompression?: boolean;
  }): Promise<LLMResponse> {
    const {
      message,
      systemPrompt = "",
      model = "",
      temperature = 0.7,
      maxTokens = 4096,
      useCompression,
    } = params;

    if (!this.isAvailable()) {
      return {
        content: "",
        model: "",
        provider: "",
        tokensInput: 0,
        tokensOutput: 0,
        latencyMs: 0,
        success: false,
        error: "LLM 网关未配置（缺少 baseUrl 或 apiKey）",
      };
    }

    const shouldCompress =
      useCompression !== undefined ? useCompression : this.config.enableCompression;

    let finalMessage = message;
    let finalSystem = systemPrompt;

    if (shouldCompress) {
      finalMessage = this.compressor.compressPrompt(message);
      finalSystem = this.compressor.compressSystem(systemPrompt);
      finalMessage += this.compressor.getCompressionSuffix();
    }

    const finalModel = model || this.config.defaultModel;
    const messages: Array<{ role: string; content: string }> = [];
    if (finalSystem) {
      messages.push({ role: "system", content: finalSystem });
    }
    messages.push({ role: "user", content: finalMessage });

    let response = await this.callProvider(
      this.config.baseUrl,
      this.config.apiKey,
      finalModel,
      messages,
      temperature,
      maxTokens
    );

    if (!response.success && this.config.enableFallback) {
      for (const fb of this.config.fallbackProviders) {
        if (!fb.baseUrl || !fb.apiKey) continue;

        console.warn(`[LLMGateway] 主 Provider 失败，尝试降级: ${fb.baseUrl}`);
        response = await this.callProvider(
          fb.baseUrl,
          fb.apiKey,
          finalModel,
          messages,
          temperature,
          maxTokens
        );
        if (response.success) break;
      }
    }

    if (response.success && shouldCompress) {
      response.content = this.compressor.decompressResponse(response.content);
    }

    return response;
  }

  async chatWithRouting(params: {
    message: string;
    taskType: TaskType;
    systemPrompt?: string;
    temperature?: number;
    maxTokens?: number;
  }): Promise<LLMResponse> {
    const { message, taskType, systemPrompt = "", temperature, maxTokens } = params;

    const model =
      this.config.modelRouting[taskType] || this.config.defaultModel;

    let finalTemperature = temperature;
    if (finalTemperature === undefined) {
      switch (taskType) {
        case "intent_classification":
          finalTemperature = 0.1;
          break;
        case "effect_planning":
          finalTemperature = 0.5;
          break;
        case "quality_review":
          finalTemperature = 0.2;
          break;
        default:
          finalTemperature = 0.7;
      }
    }

    return this.chat({
      message,
      systemPrompt,
      model,
      temperature: finalTemperature,
      maxTokens,
    });
  }

  private async callProvider(
    baseUrl: string,
    apiKey: string,
    model: string,
    messages: Array<{ role: string; content: string }>,
    temperature: number,
    maxTokens: number
  ): Promise<LLMResponse> {
    const providerName = this.extractProviderName(baseUrl);
    const health = this.providerHealth.get(providerName) || {
      name: providerName,
      status: "healthy" as ProviderStatus,
      consecutiveFailures: 0,
      lastSuccessTime: 0,
      lastError: "",
      totalRequests: 0,
      totalFailures: 0,
    };

    if (health.status === "unavailable") {
      return {
        content: "",
        model: "",
        provider: providerName,
        tokensInput: 0,
        tokensOutput: 0,
        latencyMs: 0,
        success: false,
        error: `Provider ${providerName} 不可用（连续失败 ${health.consecutiveFailures} 次）`,
      };
    }

    const url = `${baseUrl.replace(/\/$/, "")}/chat/completions`;
    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    };
    const body = JSON.stringify({
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
    });

    const startTime = Date.now();
    this.stats.totalRequests++;
    health.totalRequests++;

    for (let attempt = 0; attempt < this.config.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(
          () => controller.abort(),
          this.config.timeoutSeconds * 1000
        );

        const resp = await fetch(url, {
          method: "POST",
          headers,
          body,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);
        const latencyMs = Date.now() - startTime;

        if (!resp.ok) {
          const errorText = await resp.text();
          console.warn(
            `[LLMGateway] 调用失败 (HTTP ${resp.status}): ${errorText.slice(0, 200)}`
          );
          if (attempt < this.config.maxRetries - 1) {
            await this.sleep(this.config.retryDelayMs);
            continue;
          }

          health.consecutiveFailures++;
          health.totalFailures++;
          health.lastError = `HTTP ${resp.status}: ${errorText.slice(0, 200)}`;

          if (health.consecutiveFailures >= 3) {
            health.status = "unavailable";
          }

          this.providerHealth.set(providerName, health);
          this.stats.totalFailures++;

          return {
            content: "",
            model,
            provider: providerName,
            tokensInput: 0,
            tokensOutput: 0,
            latencyMs,
            success: false,
            error: `HTTP ${resp.status}: ${errorText.slice(0, 200)}`,
          };
        }

        const data = await resp.json();

        let content = "";
        if (data.choices && data.choices.length > 0) {
          content = data.choices[0]?.message?.content || "";
        }

        const usage = data.usage || {};
        const tokensIn = usage.prompt_tokens || 0;
        const tokensOut = usage.completion_tokens || 0;
        const usedModel = data.model || model;

        health.status = "healthy";
        health.consecutiveFailures = 0;
        health.lastSuccessTime = Date.now();
        this.providerHealth.set(providerName, health);

        this.stats.totalSuccesses++;
        this.stats.totalTokensInput += tokensIn;
        this.stats.totalTokensOutput += tokensOut;
        this.stats.totalLatencyMs += latencyMs;

        return {
          content,
          model: usedModel,
          provider: providerName,
          tokensInput: tokensIn,
          tokensOutput: tokensOut,
          latencyMs,
          success: true,
          raw: data,
        };
      } catch (e: any) {
        if (e.name === "AbortError") {
          console.warn(
            `[LLMGateway] 调用超时 (尝试 ${attempt + 1}/${this.config.maxRetries})`
          );
        } else {
          console.error(`[LLMGateway] 调用异常: ${e.message}`);
        }

        if (attempt < this.config.maxRetries - 1) {
          await this.sleep(this.config.retryDelayMs);
          continue;
        }

        health.consecutiveFailures++;
        health.totalFailures++;
        health.lastError = e.message || "Unknown error";
        this.providerHealth.set(providerName, health);
        this.stats.totalFailures++;

        return {
          content: "",
          model,
          provider: providerName,
          tokensInput: 0,
          tokensOutput: 0,
          latencyMs: Date.now() - startTime,
          success: false,
          error: e.message || "Unknown error",
        };
      }
    }

    return {
      content: "",
      model,
      provider: providerName,
      tokensInput: 0,
      tokensOutput: 0,
      latencyMs: 0,
      success: false,
      error: "重试次数耗尽",
    };
  }

  async dualModelReview(params: {
    content: string;
    reviewPrompt?: string;
  }): Promise<[LLMResponse, LLMResponse]> {
    const { content, reviewPrompt = "" } = params;

    const defaultPrompt =
      "审查以下内容的准确性、完整性和潜在问题。给出评分(0-1)和改进建议。";
    const prompt = reviewPrompt || defaultPrompt;

    const resultA = await this.chat({
      message: `${prompt}\n\n内容:\n${content}`,
      systemPrompt: "你是严格的技术审查专家",
      temperature: 0.2,
      useCompression: true,
    });

    const resultB = await this.chat({
      message: `从相反角度审查以下内容，找出模型A可能遗漏的问题:\n\n${content}`,
      systemPrompt: "你是逆向思维审查者，专门找反面问题",
      temperature: 0.8,
      useCompression: true,
    });

    return [resultA, resultB];
  }

  getStats(): Record<string, any> {
    const total = this.stats.totalRequests;
    const successRate = total > 0 ? (this.stats.totalSuccesses / total) * 100 : 0;
    const avgLatency = total > 0 ? this.stats.totalLatencyMs / total : 0;

    const providers: Record<string, any> = {};
    this.providerHealth.forEach((h, name) => {
      providers[name] = {
        status: h.status,
        consecutiveFailures: h.consecutiveFailures,
        totalRequests: h.totalRequests,
        totalFailures: h.totalFailures,
      };
    });

    return {
      totalRequests: total,
      successRate: `${successRate.toFixed(1)}%`,
      totalTokensInput: this.stats.totalTokensInput,
      totalTokensOutput: this.stats.totalTokensOutput,
      avgLatencyMs: `${avgLatency.toFixed(0)}`,
      providers,
    };
  }

  getHealth(): Record<string, any> {
    const result: Record<string, any> = {};
    this.providerHealth.forEach((h, name) => {
      result[name] = {
        status: h.status,
        lastSuccess: h.lastSuccessTime,
        consecutiveFailures: h.consecutiveFailures,
      };
    });
    return result;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

let defaultGateway: LLMGateway | null = null;

export function getLLMGateway(): LLMGateway {
  if (!defaultGateway) {
    defaultGateway = new LLMGateway();
  }
  return defaultGateway;
}

export function configureGateway(config: Partial<LLMConfig>): void {
  getLLMGateway().configure(config);
}

export function configureGatewayFromEnv(env: Record<string, string>): void {
  getLLMGateway().configureFromEnv(env);
}

export async function chat(params: {
  message: string;
  systemPrompt?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  useCompression?: boolean;
}): Promise<LLMResponse> {
  return getLLMGateway().chat(params);
}

export async function chatWithRouting(params: {
  message: string;
  taskType: TaskType;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
}): Promise<LLMResponse> {
  return getLLMGateway().chatWithRouting(params);
}
