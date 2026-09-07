/**
 * 持久化记忆系统 - MemoryStore TypeScript 版
 *
 * 设计参考：cavemem (JuliusBrussee/cavemem)
 * - localStorage: 轻量记忆，快速访问
 * - 置信度学习：根据成功/失败自动调整
 * - 经验复用：相似任务自动推荐历史经验
 *
 * 注：浏览器环境优先使用 localStorage，Node.js 环境使用内存缓存
 */

export interface MemoryEntry {
  id: number;
  category: string;
  key: string;
  content: Record<string, any>;
  tags: string[];
  confidence: number;
  createdAt: number;
  accessedAt: number;
  accessCount: number;
  successCount: number;
  failureCount: number;
}

const STORAGE_KEY = "aekv_memory_store";
const MAX_ENTRIES = 500;

export class MemoryStore {
  private entries: Map<number, MemoryEntry>;
  private nextId: number;
  private useLocalStorage: boolean;

  constructor() {
    this.entries = new Map();
    this.nextId = 1;
    this.useLocalStorage = typeof localStorage !== "undefined";
    this.load();
  }

  private load(): void {
    if (!this.useLocalStorage) return;

    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        for (const entry of data.entries || []) {
          this.entries.set(entry.id, entry);
          if (entry.id >= this.nextId) {
            this.nextId = entry.id + 1;
          }
        }
      }
    } catch (e) {
      console.warn("[MemoryStore] 加载失败:", e);
    }
  }

  private save(): void {
    if (!this.useLocalStorage) return;

    try {
      const entries = Array.from(this.entries.values());
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ entries }));
    } catch (e) {
      console.warn("[MemoryStore] 保存失败:", e);
    }
  }

  remember(params: {
    category: string;
    key: string;
    content: Record<string, any>;
    tags?: string[];
    confidence?: number;
  }): number {
    const { category, key, content, tags = [], confidence = 0.5 } = params;

    const existing = this.findByKey(category, key);
    if (existing) {
      existing.content = { ...existing.content, ...content };
      existing.tags = Array.from(new Set([...existing.tags, ...tags]));
      existing.confidence = Math.max(existing.confidence, confidence);
      existing.accessedAt = Date.now();
      this.save();
      return existing.id;
    }

    const id = this.nextId++;
    const now = Date.now();
    const entry: MemoryEntry = {
      id,
      category,
      key,
      content,
      tags,
      confidence,
      createdAt: now,
      accessedAt: now,
      accessCount: 0,
      successCount: 0,
      failureCount: 0,
    };

    this.entries.set(id, entry);

    if (this.entries.size > MAX_ENTRIES) {
      this.trimOldEntries();
    }

    this.save();
    return id;
  }

  recall(category: string, key: string): MemoryEntry | null {
    const entry = this.findByKey(category, key);
    if (!entry) return null;

    entry.accessCount++;
    entry.accessedAt = Date.now();
    this.save();

    return { ...entry };
  }

  search(params: {
    query: string;
    category?: string;
    limit?: number;
  }): MemoryEntry[] {
    const { query, category, limit = 10 } = params;
    const queryLower = query.toLowerCase();

    const results: Array<{ entry: MemoryEntry; score: number }> = [];

    for (const entry of this.entries.values()) {
      if (category && entry.category !== category) continue;

      let score = 0;

      if (entry.key.toLowerCase().includes(queryLower)) {
        score += 3;
      }

      const contentStr = JSON.stringify(entry.content).toLowerCase();
      if (contentStr.includes(queryLower)) {
        score += 2;
      }

      for (const tag of entry.tags) {
        if (tag.toLowerCase().includes(queryLower)) {
          score += 1.5;
          break;
        }
      }

      if (entry.category.toLowerCase().includes(queryLower)) {
        score += 1;
      }

      if (score > 0) {
        score *= entry.confidence;
        results.push({ entry, score });
      }
    }

    results.sort((a, b) => b.score - a.score);

    return results.slice(0, limit).map((r) => ({ ...r.entry }));
  }

  forget(category: string, key: string): boolean {
    const entry = this.findByKey(category, key);
    if (!entry) return false;

    this.entries.delete(entry.id);
    this.save();
    return true;
  }

  recordOutcome(category: string, key: string, success: boolean): void {
    const entry = this.findByKey(category, key);
    if (!entry) return;

    if (success) {
      entry.successCount++;
    } else {
      entry.failureCount++;
    }

    const total = entry.successCount + entry.failureCount;
    const baseConfidence = total > 0 ? entry.successCount / total : 0;

    const ageDays = (Date.now() - entry.accessedAt) / (1000 * 60 * 60 * 24);
    const decay = Math.max(0.3, 1 - ageDays * 0.01);

    entry.confidence = baseConfidence * decay;
    this.save();
  }

  getExperience(params: {
    category: string;
    taskKeyword?: string;
    limit?: number;
    minConfidence?: number;
  }): MemoryEntry[] {
    const { category, taskKeyword = "", limit = 5, minConfidence = 0.3 } = params;

    let entries: MemoryEntry[];

    if (taskKeyword) {
      entries = this.search({ query: taskKeyword, category, limit: limit * 2 });
    } else {
      entries = Array.from(this.entries.values())
        .filter((e) => e.category === category && e.confidence >= minConfidence)
        .sort((a, b) => {
          if (b.confidence !== a.confidence) {
            return b.confidence - a.confidence;
          }
          return b.accessCount - a.accessCount;
        })
        .slice(0, limit * 2);
    }

    return entries.filter((e) => e.confidence >= minConfidence).slice(0, limit);
  }

  getStats(): Record<string, any> {
    const entries = Array.from(this.entries.values());
    const total = entries.length;

    const avgConfidence =
      total > 0
        ? entries.reduce((sum, e) => sum + e.confidence, 0) / total
        : 0;

    const totalSuccess = entries.reduce((sum, e) => sum + e.successCount, 0);
    const totalFailure = entries.reduce((sum, e) => sum + e.failureCount, 0);

    const categoryCounts: Record<string, number> = {};
    for (const e of entries) {
      categoryCounts[e.category] = (categoryCounts[e.category] || 0) + 1;
    }

    return {
      totalMemories: total,
      avgConfidence: Math.round(avgConfidence * 1000) / 1000,
      totalSuccess,
      totalFailure,
      categories: categoryCounts,
    };
  }

  clear(): void {
    this.entries.clear();
    this.nextId = 1;
    if (this.useLocalStorage) {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  private findByKey(category: string, key: string): MemoryEntry | null {
    for (const entry of this.entries.values()) {
      if (entry.category === category && entry.key === key) {
        return entry;
      }
    }
    return null;
  }

  private trimOldEntries(): void {
    const sorted = Array.from(this.entries.values()).sort(
      (a, b) => a.accessedAt - b.accessedAt
    );

    const toRemove = sorted.slice(0, Math.floor(MAX_ENTRIES * 0.1));
    for (const entry of toRemove) {
      this.entries.delete(entry.id);
    }
  }
}

let defaultStore: MemoryStore | null = null;

export function getMemoryStore(): MemoryStore {
  if (!defaultStore) {
    defaultStore = new MemoryStore();
  }
  return defaultStore;
}
