// ============================================================================
// phase4/parameter-mapper.ts
// Phase 4 - 参数映射引擎
//
// 输入：EffectDescription（从NLU解析得到）
// 输出：具体的效果参数值（Record<string, number | string | number[]>）
//
// 核心职责：
//   1. 将词汇引用(VocabRef)映射到具体的效果matchName
//   2. 根据强度、颜色、时间等修饰词生成参数值
//   3. 应用参数约束和默认值
// ============================================================================

import { EffectDescription, VocabRef, IntensityRef, ColorRef, TemporalRef } from "./types";
import { effectGeneratorFactory, EffectParams } from "./effect-generators";
import { EFFECT_KNOWLEDGE_GRAPH, EffectCategory } from "./effect-knowledge-graph";

export interface ParameterMapping {
    matchName: string;
    settings: Record<string, number | string | number[]>;
    confidence: number;
}

export interface MapperContext {
    compWidth?: number;
    compHeight?: number;
    frameRate?: number;
    duration?: number;
    selectedLayer?: string;
}

const EFFECT_TEMPLATES: Record<string, {
    matchName: string;
    defaultSettings: Record<string, number | string | number[]>;
    parameterRange: Record<string, { min: number; max: number; step?: number }>;
    intensityScale: Record<string, number>;
}> = {
    "VT-101": {
        matchName: "ADBE Glo2",
        defaultSettings: {
            "Glow Threshold": 40,
            "Glow Radius": 25,
            "Glow Intensity": 1.5,
            "Glow Colors": [1, 1, 1],
            "Glow Color A": [1, 0.8, 0.2],
            "Glow Color B": [0.2, 0.6, 1],
        },
        parameterRange: {
            "Glow Threshold": { min: 0, max: 100 },
            "Glow Radius": { min: 0, max: 200 },
            "Glow Intensity": { min: 0, max: 10 },
        },
        intensityScale: {
            "Glow Radius": 1.0,
            "Glow Intensity": 1.0,
        },
    },
    "VT-102": {
        matchName: "ADBE Glo2",
        defaultSettings: {
            "Glow Threshold": 60,
            "Glow Radius": 50,
            "Glow Intensity": 2.0,
            "Glow Colors": [1, 1, 1],
            "Glow Color A": [1, 0.9, 0.5],
            "Glow Color B": [0.5, 0.8, 1],
        },
        parameterRange: {
            "Glow Threshold": { min: 0, max: 100 },
            "Glow Radius": { min: 0, max: 200 },
            "Glow Intensity": { min: 0, max: 10 },
        },
        intensityScale: {
            "Glow Radius": 1.2,
            "Glow Intensity": 1.3,
        },
    },
    "VT-001": {
        matchName: "ADBE Gaussian Blur 2",
        defaultSettings: {
            "Blurriness": 25,
        },
        parameterRange: {
            "Blurriness": { min: 0, max: 1000 },
        },
        intensityScale: {
            "Blurriness": 1.0,
        },
    },
    "VT-002": {
        matchName: "ADBE Directional Blur",
        defaultSettings: {
            "Blurriness": 20,
            "Direction": 0,
        },
        parameterRange: {
            "Blurriness": { min: 0, max: 100 },
            "Direction": { min: 0, max: 360 },
        },
        intensityScale: {
            "Blurriness": 1.0,
        },
    },
    "VT-301": {
        matchName: "ADBE Color Balance",
        defaultSettings: {
            "Red Shadows": 5,
            "Green Shadows": -5,
            "Blue Shadows": -10,
            "Red Midtones": 10,
            "Green Midtones": 0,
            "Blue Midtones": -5,
            "Red Highlights": 15,
            "Green Highlights": 5,
            "Blue Highlights": -5,
        },
        parameterRange: {
            "Red Shadows": { min: -100, max: 100 },
            "Green Shadows": { min: -100, max: 100 },
            "Blue Shadows": { min: -100, max: 100 },
            "Red Midtones": { min: -100, max: 100 },
            "Green Midtones": { min: -100, max: 100 },
            "Blue Midtones": { min: -100, max: 100 },
            "Red Highlights": { min: -100, max: 100 },
            "Green Highlights": { min: -100, max: 100 },
            "Blue Highlights": { min: -100, max: 100 },
        },
        intensityScale: {},
    },
    "VT-302": {
        matchName: "ADBE Color Balance",
        defaultSettings: {
            "Red Shadows": -10,
            "Green Shadows": 5,
            "Blue Shadows": 15,
            "Red Midtones": -5,
            "Green Midtones": 0,
            "Blue Midtones": 10,
            "Red Highlights": -5,
            "Green Highlights": 5,
            "Blue Highlights": 15,
        },
        parameterRange: {
            "Red Shadows": { min: -100, max: 100 },
            "Green Shadows": { min: -100, max: 100 },
            "Blue Shadows": { min: -100, max: 100 },
            "Red Midtones": { min: -100, max: 100 },
            "Green Midtones": { min: -100, max: 100 },
            "Blue Midtones": { min: -100, max: 100 },
            "Red Highlights": { min: -100, max: 100 },
            "Green Highlights": { min: -100, max: 100 },
            "Blue Highlights": { min: -100, max: 100 },
        },
        intensityScale: {},
    },
    "VT-401": {
        matchName: "CC Particle World",
        defaultSettings: {
            "Birth Rate": 100,
            "Longevity": 2.0,
            "Position X": 0.5,
            "Position Y": 0.5,
            "Velocity": 100,
            "Gravity": 50,
            "Particle Radius": 10,
            "Red": 1.0,
            "Green": 0.5,
            "Blue": 0.2,
            "Opacity": 100,
        },
        parameterRange: {
            "Birth Rate": { min: 0, max: 1000 },
            "Longevity": { min: 0.1, max: 10 },
            "Position X": { min: 0, max: 1 },
            "Position Y": { min: 0, max: 1 },
            "Velocity": { min: 0, max: 500 },
            "Gravity": { min: -200, max: 200 },
            "Particle Radius": { min: 0.1, max: 100 },
            "Opacity": { min: 0, max: 100 },
        },
        intensityScale: {
            "Birth Rate": 1.0,
            "Velocity": 1.0,
            "Particle Radius": 0.8,
        },
    },
    "VT-402": {
        matchName: "CC Particle World",
        defaultSettings: {
            "Birth Rate": 50,
            "Longevity": 4.0,
            "Position X": 0.5,
            "Position Y": 0.8,
            "Velocity": 30,
            "Gravity": -20,
            "Particle Radius": 5,
            "Red": 1.0,
            "Green": 1.0,
            "Blue": 1.0,
            "Opacity": 80,
        },
        parameterRange: {
            "Birth Rate": { min: 0, max: 500 },
            "Longevity": { min: 1, max: 15 },
            "Velocity": { min: 0, max: 100 },
            "Gravity": { min: -100, max: 100 },
            "Particle Radius": { min: 1, max: 20 },
        },
        intensityScale: {
            "Birth Rate": 1.2,
            "Velocity": 0.8,
        },
    },
};

export class ParameterMapper {
    private context: MapperContext;

    constructor(context: MapperContext = {}) {
        this.context = context;
    }

    map(description: EffectDescription): ParameterMapping[] {
        const mappings: ParameterMapping[] = [];
        const seenMatchNames = new Set<string>();

        for (const vocabRef of description.effectKeywords) {
            const template = EFFECT_TEMPLATES[vocabRef.id];
            if (!template) continue;

            if (seenMatchNames.has(template.matchName)) continue;
            seenMatchNames.add(template.matchName);

            const settings = this.applyModifiers(
                { ...template.defaultSettings },
                description.intensityKeywords,
                description.colorKeywords,
                template.intensityScale,
                template.parameterRange
            );

            mappings.push({
                matchName: template.matchName,
                settings,
                confidence: vocabRef.confidence,
            });
        }

        for (const vocabRef of description.styleKeywords) {
            const template = EFFECT_TEMPLATES[vocabRef.id];
            if (!template) continue;

            if (seenMatchNames.has(template.matchName)) continue;
            seenMatchNames.add(template.matchName);

            const settings = this.applyModifiers(
                { ...template.defaultSettings },
                description.intensityKeywords,
                description.colorKeywords,
                template.intensityScale,
                template.parameterRange
            );

            mappings.push({
                matchName: template.matchName,
                settings,
                confidence: vocabRef.confidence,
            });
        }

        return mappings;
    }

    private applyModifiers(
        settings: Record<string, number | string | number[]>,
        intensityKeywords: IntensityRef[],
        colorKeywords: ColorRef[],
        intensityScale: Record<string, number>,
        parameterRange: Record<string, { min: number; max: number; step?: number }>
    ): Record<string, number | string | number[]> {
        const result = { ...settings };

        const overallScale = intensityKeywords.length > 0
            ? intensityKeywords.reduce((acc, i) => acc * i.scale, 1)
            : 1.0;

        for (const [paramName, scaleFactor] of Object.entries(intensityScale)) {
            if (result[paramName] !== undefined && typeof result[paramName] === "number") {
                result[paramName] = this.clamp(
                    result[paramName] * overallScale * scaleFactor,
                    parameterRange[paramName]?.min ?? 0,
                    parameterRange[paramName]?.max ?? 100
                );
            }
        }

        for (const colorRef of colorKeywords) {
            this.applyColorModifier(result, colorRef);
        }

        return result;
    }

    private applyColorModifier(
        settings: Record<string, number | string | number[]>,
        colorRef: ColorRef
    ): void {
        if (Array.isArray(settings["Glow Color A"])) {
            settings["Glow Color A"] = colorRef.rgb;
        }
        if (Array.isArray(settings["Glow Color B"])) {
            const baseRgb = settings["Glow Color B"] as number[];
            settings["Glow Color B"] = [
                baseRgb[0] * 0.7 + colorRef.rgb[0] * 0.3,
                baseRgb[1] * 0.7 + colorRef.rgb[1] * 0.3,
                baseRgb[2] * 0.7 + colorRef.rgb[2] * 0.3,
            ];
        }
        if (typeof settings["Red"] === "number") {
            settings["Red"] = colorRef.rgb[0];
        }
        if (typeof settings["Green"] === "number") {
            settings["Green"] = colorRef.rgb[1];
        }
        if (typeof settings["Blue"] === "number") {
            settings["Blue"] = colorRef.rgb[2];
        }
    }

    private clamp(value: number, min: number, max: number): number {
        return Math.max(min, Math.min(max, value));
    }

    // ========================================================================
    // 知识图谱驱动的参数映射（新API）
    // ========================================================================

    mapFromMatchName(
        matchName: string,
        options: {
            intensity?: number;
            color?: { rgb: number[] };
            style?: string;
            temporal?: TemporalRef[];
        } = {}
    ): ParameterMapping | null {
        const intensityRefs: IntensityRef[] = options.intensity
            ? [{ id: "manual", scale: options.intensity, confidence: 1.0 }]
            : [];
        const colorRefs: ColorRef[] = options.color
            ? [{ id: "manual", rgb: options.color.rgb, confidence: 1.0 }]
            : [];

        const result = effectGeneratorFactory.generateEffectByMatchName(matchName, {
            intensity: intensityRefs,
            color: colorRefs,
            style: options.style,
            temporal: options.temporal,
        });

        if (!result) return null;

        return {
            matchName: result.matchName,
            settings: result.settings,
            confidence: result.confidence,
        };
    }

    mapFromEffectName(
        effectName: string,
        options: {
            intensity?: number;
            color?: { rgb: number[] };
            style?: string;
        } = {}
    ): ParameterMapping | null {
        const intensityRefs: IntensityRef[] = options.intensity
            ? [{ id: "manual", scale: options.intensity, confidence: 1.0 }]
            : [];
        const colorRefs: ColorRef[] = options.color
            ? [{ id: "manual", rgb: options.color.rgb, confidence: 1.0 }]
            : [];

        const result = effectGeneratorFactory.generateEffect(effectName, {
            intensity: intensityRefs,
            color: colorRefs,
            style: options.style,
        });

        if (!result) return null;

        return {
            matchName: result.matchName,
            settings: result.settings,
            confidence: result.confidence,
        };
    }

    getEffectsByCategory(category: EffectCategory): string[] {
        return effectGeneratorFactory.getEffectsByCategory(category);
    }

    getTotalEffectCount(): number {
        return effectGeneratorFactory.getEffectCount();
    }

    getEffectInfo(matchName: string) {
        return EFFECT_KNOWLEDGE_GRAPH[matchName] || null;
    }

    searchEffects(keyword: string): string[] {
        const lowerKeyword = keyword.toLowerCase();
        return Object.keys(EFFECT_KNOWLEDGE_GRAPH).filter(matchName => {
            const effect = EFFECT_KNOWLEDGE_GRAPH[matchName];
            return (
                effect.displayName.toLowerCase().includes(lowerKeyword) ||
                effect.tags.some(tag => tag.toLowerCase().includes(lowerKeyword)) ||
                effect.description.toLowerCase().includes(lowerKeyword)
            );
        });
    }

    getTemplate(vocabId: string): typeof EFFECT_TEMPLATES[string] | undefined {
        return EFFECT_TEMPLATES[vocabId];
    }

    listAvailableEffects(): string[] {
        return Object.keys(EFFECT_TEMPLATES);
    }

    listAllEffects(): string[] {
        return Object.keys(EFFECT_KNOWLEDGE_GRAPH);
    }

    setContext(context: Partial<MapperContext>): void {
        this.context = { ...this.context, ...context };
        effectGeneratorFactory.setContext({
            compWidth: context.compWidth,
            compHeight: context.compHeight,
            frameRate: context.frameRate,
            duration: context.duration,
        });
    }
}

export const parameterMapper = new ParameterMapper();