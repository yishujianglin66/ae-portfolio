// ============================================================================
// phase4/effect-description-parser.ts
// Phase 4 - 效果描述解析器
//
// 输入：用户自然语言字符串
// 输出：EffectDescription（映射到解析词汇表的标准术语）
//
// 数据来源：vocabulary-map.ts
// ============================================================================

import { EffectDescription, ColorRef, IntensityRef, TemporalRef, VocabRef } from "./types";
import {
    scanVocab,
    scanColors,
    scanIntensity,
    scanTemporal,
    getVocabStats,
} from "./vocabulary-map";

/**
 * 风格关键词映射表（用于 STYLE_COMBO 意图）
 *
 * 风格 = 多个效果的组合配方
 */
const STYLE_RECIPES: Record<string, { effectIds: string[]; description: string }> = {
    "赛博朋克": {
        effectIds: ["VT-303", "VT-101", "VT-504"],
        description: "青品色调 + 边缘发光 + 镜头畸变",
    },
    "cyberpunk": {
        effectIds: ["VT-303", "VT-101", "VT-504"],
        description: "青品色调 + 边缘发光 + 镜头畸变",
    },
    "电影感": {
        effectIds: ["VT-304", "VT-101", "VT-004"],
        description: "橙青色调 + 边缘发光 + 景深模糊",
    },
    "cinematic": {
        effectIds: ["VT-304", "VT-101", "VT-004"],
        description: "橙青色调 + 边缘发光 + 景深模糊",
    },
    "梦幻": {
        effectIds: ["VT-001", "VT-101", "VT-105"],
        description: "柔焦模糊 + 边缘发光 + 星芒",
    },
    "dreamy": {
        effectIds: ["VT-001", "VT-101", "VT-105"],
        description: "柔焦模糊 + 边缘发光 + 星芒",
    },
    "复古": {
        effectIds: ["VT-306", "VT-001"],
        description: "复古胶片色调 + 轻微模糊",
    },
    "vintage": {
        effectIds: ["VT-306", "VT-001"],
        description: "复古胶片色调 + 轻微模糊",
    },
    "霓虹": {
        effectIds: ["VT-101", "VT-303"],
        description: "霓虹边缘发光 + 青品色调",
    },
    "neon": {
        effectIds: ["VT-101", "VT-303"],
        description: "霓虹边缘发光 + 青品色调",
    },
};

/**
 * 效果描述解析器
 */
export class EffectDescriptionParser {
    /**
     * 解析自然语言 → EffectDescription
     * @param input 用户输入
     * @param intentTypeFromNLU （可选）从NLU得到的意图类型，用于辅助解析
     */
    parse(input: string, intentTypeFromNLU?: string): EffectDescription {
        const result: EffectDescription = {
            effectKeywords: [],
            styleKeywords: [],
            directionKeywords: [],
            intensityKeywords: [],
            colorKeywords: [],
            temporalKeywords: [],
        };

        if (!input || !input.trim()) return result;

        // 1. 扫描词汇
        const vocabRefs = scanVocab(input);
        const colorRefs = scanColors(input);
        const intensityRefs = scanIntensity(input);
        const temporalRefs = scanTemporal(input);

        // 2. 分类词汇
        for (const ref of vocabRefs) {
            if (ref.id.startsWith("VT-")) {
                const categoryNum = parseInt(ref.id.slice(3));
                if (categoryNum < 100) {
                    // VT-001 ~ VT-099：模糊类
                    result.effectKeywords.push(ref);
                } else if (categoryNum < 200) {
                    // VT-101 ~ VT-199：发光类
                    result.effectKeywords.push(ref);
                } else if (categoryNum < 300) {
                    // VT-201 ~ VT-299：扭曲类
                    result.effectKeywords.push(ref);
                } else if (categoryNum < 400) {
                    // VT-301 ~ VT-399：色彩类
                    result.colorKeywords.push({
                        keyword: ref.matchedKeyword,
                        rgb: [0.5, 0.5, 0.5],
                        temperature: "neutral",
                    });
                } else if (categoryNum < 500) {
                    // VT-401 ~ VT-499：粒子类
                    result.effectKeywords.push(ref);
                } else if (categoryNum < 600) {
                    // VT-501 ~ VT-599：转场类
                    result.effectKeywords.push(ref);
                } else if (categoryNum < 700) {
                    // VT-601 ~ VT-699：文字类
                    result.effectKeywords.push(ref);
                }
            } else if (ref.id.startsWith("KF-")) {
                result.effectKeywords.push(ref);
            }
        }

        // 3. 添加颜色
        result.colorKeywords.push(...colorRefs);

        // 4. 添加强度
        result.intensityKeywords.push(...intensityRefs);

        // 5. 添加时间
        result.temporalKeywords.push(...temporalRefs);

        // 6. 提取方向
        const directions = this.extractDirections(input);
        result.directionKeywords.push(...directions);

        // 7. 如果是风格组合意图，加载风格配方
        if (intentTypeFromNLU === "INTENT_STYLE_COMBO") {
            const styleName = this.extractStyleName(input);
            if (styleName) {
                const recipe = STYLE_RECIPES[styleName.toLowerCase()];
                if (recipe) {
                    // 加载配方中的所有效果
                    for (const vid of recipe.effectIds) {
                        const existing = result.effectKeywords.find((r) => r.id === vid);
                        if (!existing) {
                            // 创建虚拟引用
                            const vocabName = this.getVocabName(vid);
                            result.styleKeywords.push({
                                id: vid,
                                name: vocabName || vid,
                                matchedKeyword: styleName,
                                suggestedEffect: this.getVocabEffect(vid),
                                confidence: 0.75,
                            });
                        }
                    }
                }
            }
        }

        return result;
    }

    /**
     * 提取方向关键词
     */
    private extractDirections(input: string): string[] {
        const directions: string[] = [];
        const dirMap = [
            { keyword: "向上", value: "up" },
            { keyword: "向下", value: "down" },
            { keyword: "向左", value: "left" },
            { keyword: "向右", value: "right" },
            { keyword: "向外", value: "out" },
            { keyword: "向内", value: "in" },
            { keyword: "向上", value: "up" },
            { keyword: "up", value: "up" },
            { keyword: "down", value: "down" },
            { keyword: "left", value: "left" },
            { keyword: "right", value: "right" },
            { keyword: "out", value: "out" },
            { keyword: "in", value: "in" },
        ];
        const seen = new Set<string>();
        for (const d of dirMap) {
            if (input.includes(d.keyword) && !seen.has(d.value)) {
                seen.add(d.value);
                directions.push(d.value);
            }
        }
        return directions;
    }

    /**
     * 提取风格名
     */
    private extractStyleName(input: string): string | undefined {
        // 优先匹配关键词
        for (const style of Object.keys(STYLE_RECIPES)) {
            if (input.toLowerCase().includes(style.toLowerCase())) {
                return style;
            }
        }
        // 模式匹配
        const m = input.match(/(\S{1,10}?)\s*风格/);
        return m?.[1];
    }

    /**
     * 获取词汇名
     */
    private getVocabName(vocabId: string): string | undefined {
        // 这里硬编码一些常见的词汇名（实际可从 vocabulary-map 中查询）
        const names: Record<string, string> = {
            "VT-001": "均匀模糊扩散",
            "VT-101": "边缘发光",
            "VT-303": "青品对比色调",
            "VT-304": "橙青电影色调",
            "VT-306": "复古胶片色调",
            "VT-504": "旋转转场",
            "VT-105": "星芒",
            "VT-004": "镜头光斑模糊",
        };
        return names[vocabId];
    }

    /**
     * 获取词汇建议的效果
     */
    private getVocabEffect(vocabId: string): string | undefined {
        const effects: Record<string, string> = {
            "VT-001": "ADBE Gaussian Blur 2",
            "VT-101": "ADBE Glo2",
            "VT-303": "ADBE Curves",
            "VT-304": "ADBE Curves",
            "VT-306": "ADBE Colorista",
            "VT-504": "ADBE Transform",
            "VT-105": "ADBE Starglow",
            "VT-004": "ADBE Camera Lens Blur",
        };
        return effects[vocabId];
    }
}

/**
 * 单例实例
 */
export const effectDescriptionParser = new EffectDescriptionParser();

/**
 * 获取风格配方
 */
export function getStyleRecipe(styleName: string): { effectIds: string[]; description: string } | undefined {
    return STYLE_RECIPES[styleName.toLowerCase()];
}

/**
 * 获取所有可用风格
 */
export function getAllStyles(): string[] {
    return Object.keys(STYLE_RECIPES);
}

/**
 * 获取词汇统计
 */
export function getStats() {
    return getVocabStats();
}
