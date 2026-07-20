// ============================================================================
// phase5/persistent-learning-loop.ts
// Phase 5 - 持久化学习循环
//
// 在 learning-loop.ts 的基础上增加：
//   1. JSON文件持久化存储（替代MemoryCaseStore的内存存储）
//   2. 自动保存/加载机制（每次操作后自动保存）
//   3. 检查点机制（定期保存检查点）
//   4. 跨IDE共享（文件系统存储）
//
// 对应架构设计文档 7.5 节 LearningLoop + 持久化扩展
// ============================================================================

import * as fs from "fs";
import * as path from "path";
import {
    ExecutionRecord,
    ParameterTemplate,
    ConfidenceAdjustment,
    LearningMetrics,
    VerificationResult,
    ExpectedParameters,
    ExecutionResult,
} from "./types";

const STATE_DIR = path.join(process.env.APPDATA || process.env.HOME || ".", "AE-Knowledge-Vault", "learning-state");
const CASE_STORE_FILE = path.join(STATE_DIR, "case-store.json");
const DEFAULT_VALUE_STORE_FILE = path.join(STATE_DIR, "default-value-store.json");
const EXECUTION_RECORDS_FILE = path.join(STATE_DIR, "execution-records.json");
const CHECKPOINTS_DIR = path.join(STATE_DIR, "checkpoints");

interface PersistentStorage {
    load<T>(filePath: string, defaultValue: T): T;
    save<T>(filePath: string, data: T): void;
}

class FileSystemStorage implements PersistentStorage {
    load<T>(filePath: string, defaultValue: T): T {
        try {
            if (!fs.existsSync(filePath)) {
                return defaultValue;
            }
            const content = fs.readFileSync(filePath, "utf-8");
            return JSON.parse(content) as T;
        } catch {
            return defaultValue;
        }
    }

    save<T>(filePath: string, data: T): void {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
    }
}

export interface CaseStore {
    addTemplate(template: ParameterTemplate): void;
    findTemplates(effectMatchName: string): ParameterTemplate[];
    incrementUsage(templateId: string): void;
    getAllTemplates(): ParameterTemplate[];
}

export class PersistentCaseStore implements CaseStore {
    private storage: PersistentStorage;
    private templates: Map<string, ParameterTemplate> = new Map();

    constructor(storage: PersistentStorage = new FileSystemStorage()) {
        this.storage = storage;
        this.load();
    }

    private load(): void {
        const saved = this.storage.load<ParameterTemplate[]>(CASE_STORE_FILE, []);
        for (const t of saved) {
            this.templates.set(t.id, t);
        }
    }

    private save(): void {
        this.storage.save(CASE_STORE_FILE, Array.from(this.templates.values()));
    }

    addTemplate(template: ParameterTemplate): void {
        this.templates.set(template.id, template);
        this.save();
    }

    findTemplates(effectMatchName: string): ParameterTemplate[] {
        return Array.from(this.templates.values())
            .filter((t) => t.effectMatchName === effectMatchName)
            .sort((a, b) => b.usageCount - a.usageCount);
    }

    incrementUsage(templateId: string): void {
        const t = this.templates.get(templateId);
        if (t) {
            t.usageCount++;
            t.lastUsed = new Date().toISOString();
            this.save();
        }
    }

    getAllTemplates(): ParameterTemplate[] {
        return Array.from(this.templates.values());
    }

    replaceTemplates(templates: ParameterTemplate[]): void {
        this.templates.clear();
        for (const t of templates) {
            this.templates.set(t.id, t);
        }
        this.save();
    }
}

export interface DefaultValueStore {
    get(effectMatchName: string, paramName: string): number | string | boolean | number[] | undefined;
    update(
        effectMatchName: string,
        paramName: string,
        actualValue: number | string | boolean | number[],
        learningRate: number,
    ): void;
    getAll(effectMatchName: string): Record<string, number | string | boolean | number[]>;
}

export class PersistentDefaultValueStore implements DefaultValueStore {
    private storage: PersistentStorage;
    private store: Map<string, { value: number | string | boolean | number[]; weight: number }> = new Map();

    constructor(storage: PersistentStorage = new FileSystemStorage()) {
        this.storage = storage;
        this.load();
    }

    private load(): void {
        const saved = this.storage.load<Record<string, { value: number | string | boolean | number[]; weight: number }>>(
            DEFAULT_VALUE_STORE_FILE,
            {}
        );
        for (const [key, value] of Object.entries(saved)) {
            this.store.set(key, value);
        }
    }

    private save(): void {
        const obj: Record<string, { value: number | string | boolean | number[]; weight: number }> = {};
        const entries = Array.from(this.store.entries());
        for (let i = 0; i < entries.length; i++) {
            obj[entries[i][0]] = entries[i][1];
        }
        this.storage.save(DEFAULT_VALUE_STORE_FILE, obj);
    }

    get(effectMatchName: string, paramName: string): number | string | boolean | number[] | undefined {
        return this.store.get(`${effectMatchName}.${paramName}`)?.value;
    }

    update(
        effectMatchName: string,
        paramName: string,
        actualValue: number | string | boolean | number[],
        learningRate: number,
    ): void {
        const key = `${effectMatchName}.${paramName}`;
        const existing = this.store.get(key);

        if (!existing) {
            this.store.set(key, { value: actualValue, weight: learningRate });
            this.save();
            return;
        }

        if (typeof existing.value === "number" && typeof actualValue === "number") {
            const oldWeight = existing.weight;
            const newWeight = learningRate;
            const totalWeight = oldWeight + newWeight;
            const newValue = (existing.value * oldWeight + actualValue * newWeight) / totalWeight;
            this.store.set(key, { value: newValue, weight: totalWeight });
        } else {
            this.store.set(key, { value: actualValue, weight: learningRate });
        }
        this.save();
    }

    getAll(effectMatchName: string): Record<string, number | string | boolean | number[]> {
        const result: Record<string, number | string | boolean | number[]> = {};
        const entries = Array.from(this.store.entries());
        for (let i = 0; i < entries.length; i++) {
            const key = entries[i][0];
            const entry = entries[i][1];
            if (key.startsWith(`${effectMatchName}.`)) {
                const paramName = key.slice(effectMatchName.length + 1);
                result[paramName] = entry.value;
            }
        }
        return result;
    }

    getAllEntries(): Map<string, { value: number | string | boolean | number[]; weight: number }> {
        return new Map(this.store);
    }

    replaceAll(entries: Record<string, { value: number | string | boolean | number[]; weight: number }>): void {
        this.store.clear();
        for (const [key, value] of Object.entries(entries)) {
            this.store.set(key, value);
        }
        this.save();
    }
}

export class PersistentLearningLoop {
    private caseStore: CaseStore;
    private defaultValueStore: DefaultValueStore;
    private confidenceAdjustments: ConfidenceAdjustment[] = [];
    private executionRecords: ExecutionRecord[] = [];
    private storage: PersistentStorage;

    private learningRate: number;
    private boostDelta: number;
    private penalizeDelta: number;

    constructor(
        caseStore?: CaseStore,
        defaultValueStore?: DefaultValueStore,
        options?: {
            learningRate?: number;
            boostDelta?: number;
            penalizeDelta?: number;
        },
        storage: PersistentStorage = new FileSystemStorage()
    ) {
        this.storage = storage;
        this.caseStore = caseStore || new PersistentCaseStore(storage);
        this.defaultValueStore = defaultValueStore || new PersistentDefaultValueStore(storage);
        this.learningRate = options?.learningRate ?? 0.3;
        this.boostDelta = options?.boostDelta ?? 0.05;
        this.penalizeDelta = options?.penalizeDelta ?? 0.1;

        this.loadExecutionRecords();
        this.loadConfidenceAdjustments();
    }

    private loadExecutionRecords(): void {
        this.executionRecords = this.storage.load<ExecutionRecord[]>(EXECUTION_RECORDS_FILE, []);
    }

    private saveExecutionRecords(): void {
        this.storage.save(EXECUTION_RECORDS_FILE, this.executionRecords);
    }

    private loadConfidenceAdjustments(): void {
        const records = this.storage.load<ExecutionRecord[]>(EXECUTION_RECORDS_FILE, []);
        for (const record of records) {
            if (record.reasoningPath && record.reasoningPath.length > 0) {
                const direction = record.userUndone || !record.execution.success ? "penalize" : "boost";
                this.confidenceAdjustments.push({
                    reasoningPath: record.reasoningPath,
                    direction,
                    delta: direction === "boost" ? this.boostDelta : this.penalizeDelta,
                    reason: record.execution.success
                        ? `执行成功 (record: ${record.id})`
                        : `执行失败 (record: ${record.id})`,
                    timestamp: record.timestamp,
                });
            }
        }
    }

    saveCheckpoint(name: string): string {
        if (!fs.existsSync(CHECKPOINTS_DIR)) {
            fs.mkdirSync(CHECKPOINTS_DIR, { recursive: true });
        }

        const defaultValuesObj: Record<string, { value: number | string | boolean | number[]; weight: number }> = {};
        const dvStore = this.defaultValueStore as PersistentDefaultValueStore;
        if (dvStore && "getAllEntries" in dvStore) {
            const entries = (dvStore as any).getAllEntries();
            for (const [key, value] of entries) {
                defaultValuesObj[key] = value;
            }
        }

        const checkpoint = {
            name,
            timestamp: new Date().toISOString(),
            executionRecords: this.executionRecords,
            confidenceAdjustments: this.confidenceAdjustments,
            templates: this.caseStore.getAllTemplates(),
            defaultValues: defaultValuesObj,
        };

        const filePath = path.join(CHECKPOINTS_DIR, `${name}_${Date.now()}.json`);
        fs.writeFileSync(filePath, JSON.stringify(checkpoint, null, 2), "utf-8");

        return filePath;
    }

    loadCheckpoint(filePath: string): boolean {
        try {
            const content = fs.readFileSync(filePath, "utf-8");
            const checkpoint = JSON.parse(content);

            if (checkpoint.executionRecords) {
                this.executionRecords = checkpoint.executionRecords;
            }
            if (checkpoint.confidenceAdjustments) {
                this.confidenceAdjustments = checkpoint.confidenceAdjustments;
            }
            if (checkpoint.templates && Array.isArray(checkpoint.templates)) {
                const cs = this.caseStore as PersistentCaseStore;
                if (cs && "replaceTemplates" in cs) {
                    (cs as any).replaceTemplates(checkpoint.templates);
                }
            }
            if (checkpoint.defaultValues && typeof checkpoint.defaultValues === "object") {
                const dvStore = this.defaultValueStore as PersistentDefaultValueStore;
                if (dvStore && "replaceAll" in dvStore) {
                    (dvStore as any).replaceAll(checkpoint.defaultValues);
                }
            }

            this.saveExecutionRecords();
            return true;
        } catch {
            return false;
        }
    }

    recordExecution(
        userInput: string,
        intentType: string,
        expected: ExpectedParameters,
        execution: ExecutionResult,
        verification: VerificationResult,
        userFeedback?: {
            satisfied?: boolean;
            adjusted?: boolean;
            undone?: boolean;
            finalParams?: Array<{ name: string; value: number | string | boolean | number[] }>;
        },
        reasoningPath?: string[],
    ): ExecutionRecord {
        const record: ExecutionRecord = {
            id: `exec_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
            timestamp: new Date().toISOString(),
            userInput,
            intentType,
            expected,
            execution,
            verification,
            userSatisfied: userFeedback?.satisfied,
            userAdjusted: userFeedback?.adjusted,
            userUndone: userFeedback?.undone,
            finalParams: userFeedback?.finalParams,
            reasoningPath,
        };

        this.executionRecords.push(record);
        this.saveExecutionRecords();

        if (this.executionRecords.length > 1000) {
            this.executionRecords = this.executionRecords.slice(-500);
            this.saveExecutionRecords();
        }

        if (userFeedback?.undone) {
            this.learnFromFailure(record);
        } else if (userFeedback?.adjusted && userFeedback.finalParams) {
            this.learnFromDeviation(record, userFeedback.finalParams);
        } else if (userFeedback?.satisfied || (execution.success && verification.passed)) {
            this.learnFromSuccess(record);
        } else if (!execution.success) {
            this.learnFromFailure(record);
        }

        return record;
    }

    private learnFromSuccess(record: ExecutionRecord): void {
        const { expected, execution } = record;

        if (expected.effectMatchName && execution.effectName) {
            const template: ParameterTemplate = {
                id: `tpl_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
                source: "auto-learned",
                effectMatchName: expected.effectMatchName,
                effectName: execution.effectName,
                parameters: this.propsToObject(expected.properties),
                userRating: "positive",
                usageCount: 1,
                lastUsed: new Date().toISOString(),
                sourceInput: record.userInput,
            };
            this.caseStore.addTemplate(template);
        }

        if (record.reasoningPath && record.reasoningPath.length > 0) {
            const adjustment: ConfidenceAdjustment = {
                reasoningPath: record.reasoningPath,
                direction: "boost",
                delta: this.boostDelta,
                reason: `执行成功 (record: ${record.id})`,
                timestamp: new Date().toISOString(),
            };
            this.confidenceAdjustments.push(adjustment);
        }
    }

    private learnFromDeviation(
        record: ExecutionRecord,
        finalParams: Array<{ name: string; value: number | string | boolean | number[] }>,
    ): void {
        const { expected } = record;
        if (!expected.effectMatchName) return;

        for (const finalParam of finalParams) {
            const expectedParam = expected.properties.find((p) => p.name === finalParam.name);
            if (!expectedParam) continue;

            const deviation = this.calculateParamDeviation(expectedParam.value, finalParam.value);

            if (deviation > 0.05) {
                this.defaultValueStore.update(
                    expected.effectMatchName,
                    finalParam.name,
                    finalParam.value,
                    this.learningRate,
                );
            }
        }
    }

    private learnFromFailure(record: ExecutionRecord): void {
        if (record.reasoningPath && record.reasoningPath.length > 0) {
            const adjustment: ConfidenceAdjustment = {
                reasoningPath: record.reasoningPath,
                direction: "penalize",
                delta: this.penalizeDelta,
                reason: record.execution.success
                    ? `用户撤销 (record: ${record.id})`
                    : `执行失败: ${record.execution.errorCode || "unknown"} (record: ${record.id})`,
                timestamp: new Date().toISOString(),
            };
            this.confidenceAdjustments.push(adjustment);
        }
    }

    private calculateParamDeviation(
        expected: number | string | boolean | number[],
        actual: number | string | boolean | number[],
    ): number {
        if (typeof expected === "number" && typeof actual === "number") {
            if (expected === 0) return Math.abs(actual);
            return Math.abs(expected - actual) / Math.abs(expected);
        }
        if (Array.isArray(expected) && Array.isArray(actual)) {
            if (expected.length === 0) return 0;
            const deviations = expected.map((e, i) => {
                const a = actual[i] as number;
                const eNum = e as number;
                if (eNum === 0) return Math.abs(a);
                return Math.abs(eNum - a) / Math.abs(eNum);
            });
            return deviations.reduce((sum, d) => sum + d, 0) / deviations.length;
        }
        return expected === actual ? 0 : 1;
    }

    private propsToObject(
        props: Array<{ name: string; value: number | string | boolean | number[] }>,
    ): Record<string, number | string | boolean | number[]> {
        const result: Record<string, number | string | boolean | number[]> = {};
        for (const p of props) {
            result[p.name] = p.value;
        }
        return result;
    }

    getMetrics(): LearningMetrics {
        const total = this.executionRecords.length;
        const successCount = this.executionRecords.filter(
            (r) => r.execution.success && r.verification.passed,
        ).length;
        const failureCount = this.executionRecords.filter((r) => !r.execution.success).length;
        const userAdjustedCount = this.executionRecords.filter((r) => r.userAdjusted).length;
        const userUndoneCount = this.executionRecords.filter((r) => r.userUndone).length;

        const deviationSum = this.executionRecords
            .filter((r) => r.verification.deviationScore !== undefined)
            .reduce((sum, r) => sum + r.verification.deviationScore, 0);
        const deviationCount = this.executionRecords.filter(
            (r) => r.verification.deviationScore !== undefined,
        ).length;
        const averageDeviation = deviationCount > 0 ? deviationSum / deviationCount : 0;

        const learnedTemplates = this.caseStore.getAllTemplates().length;
        const confidenceAdjustments = this.confidenceAdjustments.length;

        const accuracyImprovement = this.calculateAccuracyImprovement();

        return {
            totalExecutions: total,
            successCount,
            failureCount,
            userAdjustedCount,
            userUndoneCount,
            successRate: total > 0 ? successCount / total : 0,
            averageDeviation,
            learnedTemplates,
            confidenceAdjustments,
            accuracyImprovement,
        };
    }

    private calculateAccuracyImprovement(): number {
        const records = this.executionRecords;
        if (records.length < 4) return 0;

        const recentCount = Math.min(10, Math.floor(records.length / 2));
        const recentRecords = records.slice(-recentCount);
        const earlierRecords = records.slice(-recentCount * 2, -recentCount);

        if (earlierRecords.length === 0) return 0;

        const recentSuccess = recentRecords.filter((r) => r.execution.success).length / recentRecords.length;
        const earlierSuccess = earlierRecords.filter((r) => r.execution.success).length / earlierRecords.length;

        return recentSuccess - earlierSuccess;
    }

    getExecutionRecords(): ExecutionRecord[] {
        return [...this.executionRecords];
    }

    getConfidenceAdjustments(): ConfidenceAdjustment[] {
        return [...this.confidenceAdjustments];
    }

    getCaseStore(): CaseStore {
        return this.caseStore;
    }

    getDefaultValueStore(): DefaultValueStore {
        return this.defaultValueStore;
    }

    getStateSummary(): {
        totalExecutions: number;
        templatesCount: number;
        lastSaved: string;
        checkpointsCount: number;
    } {
        let checkpointsCount = 0;
        try {
            if (fs.existsSync(CHECKPOINTS_DIR)) {
                checkpointsCount = fs.readdirSync(CHECKPOINTS_DIR).length;
            }
        } catch {
            checkpointsCount = 0;
        }

        return {
            totalExecutions: this.executionRecords.length,
            templatesCount: this.caseStore.getAllTemplates().length,
            lastSaved: new Date().toISOString(),
            checkpointsCount,
        };
    }
}

export const persistentLearningLoop = new PersistentLearningLoop();