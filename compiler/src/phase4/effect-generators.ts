// ============================================================================
// phase4/effect-generators.ts
// Phase 4 - 效果智能参数生成器
//
// 为20个常用效果提供智能参数生成能力：
//   1. Glow（发光）
//   2. Color Key（颜色键控）
//   3. CC Particle World（粒子世界）
//   4. Fractal Noise（分形噪波）
//   5. Ramp（渐变）
//   6. Gaussian Blur（高斯模糊）
//   7. Directional Blur（方向模糊）
//   8. Hue/Saturation（色相/饱和度）
//   9. Levels（色阶，替代Curves）
//  10. Color Balance（色彩平衡）
//  11. Drop Shadow（投影）
//  12. Fill（填充）
//  13. Stroke（描边）
//  14. Noise（噪波）
//  15. Unsharp Mask（锐化）
//  16. Texturize（纹理化）
//  17. Roughen Edges（粗糙边缘）
//  18. CC Lens（CC镜头）
//  19. Optics Compensation（光学补偿）
//  20. Simple Choker（简单抑制）
//
// 生成策略：
//   - 根据自然语言描述中的修饰词（强度、颜色、风格）智能计算参数值
//   - 应用参数约束和最佳实践值
//   - 支持多场景预设（如霓虹发光、柔和发光、强烈发光）
// ============================================================================

import { ColorRef, IntensityRef, TemporalRef } from "./types";
import { EFFECT_KNOWLEDGE_GRAPH, EffectNode, EffectParameter } from "./effect-knowledge-graph";

export interface EffectParams {
    matchName: string;
    displayName: string;
    settings: Record<string, number | string | number[]>;
    confidence: number;
}

export interface GeneratorContext {
    compWidth?: number;
    compHeight?: number;
    frameRate?: number;
    duration?: number;
    selectedLayerType?: string;
}

abstract class BaseGenerator {
    protected context: GeneratorContext;

    constructor(context: GeneratorContext = {}) {
        this.context = context;
    }

    abstract generate(
        modifiers: {
            intensity?: IntensityRef[];
            color?: ColorRef[];
            temporal?: TemporalRef[];
            style?: string;
        }
    ): EffectParams;

    protected getIntensityScale(intensityRefs: IntensityRef[]): number {
        if (intensityRefs.length === 0) return 1.0;
        return intensityRefs.reduce((acc, i) => acc * i.scale, 1.0);
    }

    protected clamp(value: number, min: number, max: number): number {
        return Math.max(min, Math.min(max, value));
    }
}

export class GlowGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];

        let preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Glow Threshold": this.clamp(preset.base.threshold * scaleFactor, 0, 100),
            "Glow Radius": this.clamp(preset.base.radius * scaleFactor, 0, 200),
            "Glow Intensity": this.clamp(preset.base.intensity * scaleFactor, 0, 10),
            "Glow Colors": preset.base.colors,
        };

        if (color) {
            settings["Glow Color A"] = color.rgb;
            settings["Glow Color B"] = [
                color.rgb[0] * 0.7,
                color.rgb[1] * 0.7,
                color.rgb[2] * 0.7,
            ];
        } else {
            settings["Glow Color A"] = preset.colors.a;
            settings["Glow Color B"] = preset.colors.b;
        }

        return {
            matchName: "ADBE Glo2",
            displayName: "Glow",
            settings,
            confidence: 0.85,
        };
    }

    private getPreset(style?: string) {
        const styleMap: Record<string, string> = {
            "霓虹": "neon",
            "赛博朋克": "cyberpunk",
            "柔和": "soft",
            "梦幻": "dreamy",
            "强烈": "strong",
        };
        
        const normalizedStyle = styleMap[style || ""] || style || "";
        
        const presets: Record<string, {
            base: { threshold: number; radius: number; intensity: number; colors: number[] };
            colors: { a: number[]; b: number[] };
            scale: number;
        }> = {
            "neon": {
                base: { threshold: 30, radius: 40, intensity: 2.5, colors: [1, 1, 1] },
                colors: { a: [0.2, 0.6, 1], b: [0.6, 0.2, 1] },
                scale: 1.5,
            },
            "cyberpunk": {
                base: { threshold: 25, radius: 50, intensity: 3.0, colors: [1, 1, 1] },
                colors: { a: [0.1, 0.8, 1], b: [1, 0.2, 0.8] },
                scale: 1.6,
            },
            "soft": {
                base: { threshold: 70, radius: 20, intensity: 1.0, colors: [1, 1, 1] },
                colors: { a: [1, 0.9, 0.8], b: [0.9, 0.95, 1] },
                scale: 0.6,
            },
            "dreamy": {
                base: { threshold: 60, radius: 35, intensity: 1.5, colors: [1, 1, 1] },
                colors: { a: [1, 0.8, 0.9], b: [0.8, 0.9, 1] },
                scale: 0.8,
            },
            "strong": {
                base: { threshold: 20, radius: 60, intensity: 4.0, colors: [1, 1, 1] },
                colors: { a: [1, 0.5, 0], b: [1, 0.2, 0] },
                scale: 1.8,
            },
        };

        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.toLowerCase().includes(key)) return preset;
        }

        return {
            base: { threshold: 40, radius: 25, intensity: 1.5, colors: [1, 1, 1] },
            colors: { a: [1, 0.8, 0.2], b: [0.2, 0.6, 1] },
            scale: 1.0,
        };
    }
}

export class ColorKeyGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];

        const tolerance = this.clamp(20 * intensityScale, 5, 80);
        const edgeFeather = this.clamp(1.0 * intensityScale, 0, 10);

        const settings: Record<string, number | number[]> = {
            "Key Color": color?.rgb || [0, 1, 0],
            "Color Tolerance": tolerance,
            "Edge Feather": edgeFeather,
            "Edge Thin": this.clamp(0.5 * intensityScale, -5, 5),
            "Edge Contrast": this.clamp(10 * intensityScale, 0, 100),
            "Smoothing": "None",
        };

        if (modifiers.style?.toLowerCase().includes("green")) {
            settings["Key Color"] = [0, 0.8, 0.2];
        } else if (modifiers.style?.toLowerCase().includes("blue")) {
            settings["Key Color"] = [0.1, 0.3, 0.9];
        } else if (modifiers.style?.toLowerCase().includes("red")) {
            settings["Key Color"] = [0.9, 0.1, 0.1];
        }

        return {
            matchName: "ADBE Color Key",
            displayName: "Color Key",
            settings,
            confidence: 0.80,
        };
    }
}

export class CCParticleWorldGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];

        let preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Birth Rate": this.clamp(preset.base.birthRate * scaleFactor, 0, 1000),
            "Longevity": this.clamp(preset.base.longevity / scaleFactor, 0.1, 10),
            "Position X": preset.base.posX,
            "Position Y": preset.base.posY,
            "Velocity": this.clamp(preset.base.velocity * scaleFactor, 0, 500),
            "Gravity": preset.base.gravity,
            "Particle Radius": this.clamp(preset.base.radius * scaleFactor, 0.1, 100),
            "Opacity": this.clamp(preset.base.opacity, 0, 100),
            "Red": color?.rgb[0] ?? preset.colors.r,
            "Green": color?.rgb[1] ?? preset.colors.g,
            "Blue": color?.rgb[2] ?? preset.colors.b,
        };

        return {
            matchName: "CC Particle World",
            displayName: "CC Particle World",
            settings,
            confidence: 0.82,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { birthRate: number; longevity: number; posX: number; posY: number; velocity: number; gravity: number; radius: number; opacity: number };
            colors: { r: number; g: number; b: number };
            scale: number;
        }> = {
            "fire": {
                base: { birthRate: 150, longevity: 1.5, posX: 0.5, posY: 0.8, velocity: 150, gravity: -80, radius: 8, opacity: 100 },
                colors: { r: 1, g: 0.4, b: 0.1 },
                scale: 1.5,
            },
            "snow": {
                base: { birthRate: 30, longevity: 5.0, posX: 0.5, posY: 0.1, velocity: 20, gravity: 30, radius: 3, opacity: 80 },
                colors: { r: 1, g: 1, b: 1 },
                scale: 0.8,
            },
            "sparkle": {
                base: { birthRate: 80, longevity: 1.0, posX: 0.5, posY: 0.5, velocity: 200, gravity: -50, radius: 2, opacity: 100 },
                colors: { r: 1, g: 0.9, b: 0.5 },
                scale: 1.2,
            },
            "smoke": {
                base: { birthRate: 20, longevity: 4.0, posX: 0.5, posY: 0.8, velocity: 30, gravity: -15, radius: 25, opacity: 60 },
                colors: { r: 0.5, g: 0.5, b: 0.5 },
                scale: 0.6,
            },
            "explosion": {
                base: { birthRate: 500, longevity: 0.8, posX: 0.5, posY: 0.5, velocity: 400, gravity: 100, radius: 15, opacity: 100 },
                colors: { r: 1, g: 0.2, b: 0 },
                scale: 2.0,
            },
        };

        for (const [key, preset] of Object.entries(presets)) {
            if (style?.toLowerCase().includes(key)) return preset;
        }

        return {
            base: { birthRate: 100, longevity: 2.0, posX: 0.5, posY: 0.5, velocity: 100, gravity: 50, radius: 10, opacity: 100 },
            colors: { r: 1, g: 0.5, b: 0.2 },
            scale: 1.0,
        };
    }
}

export class FractalNoiseGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);

        let preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Fractal Type": preset.base.fractalType,
            "Noise Type": preset.base.noiseType,
            "Contrast": this.clamp(preset.base.contrast * scaleFactor, 0, 100),
            "Brightness": this.clamp(preset.base.brightness, -100, 100),
            "Scale": this.clamp(preset.base.scale / scaleFactor, 10, 2000),
            "Complexity": this.clamp(preset.base.complexity, 1, 10),
            "Evolution": 0,
            "Evolution Speed": this.clamp(preset.base.evolutionSpeed * scaleFactor, 0, 20),
        };

        if (modifiers.color?.length) {
            const color = modifiers.color[0];
            settings["Contrast"] = this.clamp(settings["Contrast"] as number + 20, 0, 100);
            settings["Brightness"] = this.clamp(settings["Brightness"] as number + 10, -100, 100);
        }

        return {
            matchName: "ADBE Fractal Noise",
            displayName: "Fractal Noise",
            settings,
            confidence: 0.78,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { fractalType: string; noiseType: string; contrast: number; brightness: number; scale: number; complexity: number; evolutionSpeed: number };
            scale: number;
        }> = {
            "clouds": {
                base: { fractalType: "Turbulence", noiseType: "Soft Linear", contrast: 50, brightness: 0, scale: 300, complexity: 4, evolutionSpeed: 2 },
                scale: 0.8,
            },
            "fire": {
                base: { fractalType: "Turbulence", noiseType: "Linear", contrast: 70, brightness: 20, scale: 100, complexity: 6, evolutionSpeed: 8 },
                scale: 1.4,
            },
            "water": {
                base: { fractalType: "Basic", noiseType: "Soft Linear", contrast: 40, brightness: -10, scale: 200, complexity: 3, evolutionSpeed: 3 },
                scale: 0.9,
            },
            "electric": {
                base: { fractalType: "Turbulence", noiseType: "Splatter", contrast: 90, brightness: 30, scale: 50, complexity: 8, evolutionSpeed: 15 },
                scale: 1.8,
            },
            "smoke": {
                base: { fractalType: "Turbulence", noiseType: "Soft Linear", contrast: 30, brightness: -20, scale: 400, complexity: 5, evolutionSpeed: 1 },
                scale: 0.5,
            },
        };

        for (const [key, preset] of Object.entries(presets)) {
            if (style?.toLowerCase().includes(key)) return preset;
        }

        return {
            base: { fractalType: "Turbulence", noiseType: "Soft Linear", contrast: 50, brightness: 0, scale: 200, complexity: 5, evolutionSpeed: 5 },
            scale: 1.0,
        };
    }
}

export class RampGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const color1 = modifiers.color?.[0];
        const color2 = modifiers.color?.[1];

        let preset = this.getPreset(modifiers.style);

        const settings: Record<string, number | number[]> = {
            "Start of Ramp": preset.base.startPoint,
            "Start Color": color1?.rgb || preset.colors.start,
            "End of Ramp": preset.base.endPoint,
            "End Color": color2?.rgb || preset.colors.end,
            "Ramp Shape": preset.base.shape,
            "Ramp Scatter": preset.base.scatter,
        };

        return {
            matchName: "ADBE Ramp",
            displayName: "Ramp",
            settings,
            confidence: 0.85,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { startPoint: number[]; endPoint: number[]; shape: string; scatter: number };
            colors: { start: number[]; end: number[] };
        }> = {
            "sunset": {
                base: { startPoint: [0.5, 0], endPoint: [0.5, 1], shape: "Linear Ramp", scatter: 0 },
                colors: { start: [1, 0.5, 0.2], end: [0.2, 0.3, 0.6] },
            },
            "cyberpunk": {
                base: { startPoint: [0, 0.5], endPoint: [1, 0.5], shape: "Linear Ramp", scatter: 10 },
                colors: { start: [0, 0.5, 1], end: [1, 0.2, 0.8] },
            },
            "gradient": {
                base: { startPoint: [0.5, 0], endPoint: [0.5, 1], shape: "Linear Ramp", scatter: 0 },
                colors: { start: [1, 1, 1], end: [0.2, 0.2, 0.2] },
            },
            "radial": {
                base: { startPoint: [0.5, 0.5], endPoint: [0.5, 1], shape: "Radial Ramp", scatter: 5 },
                colors: { start: [1, 0.8, 0], end: [0.1, 0.1, 0.1] },
            },
            "warmcool": {
                base: { startPoint: [0, 0.5], endPoint: [1, 0.5], shape: "Linear Ramp", scatter: 0 },
                colors: { start: [1, 0.7, 0.3], end: [0.2, 0.6, 1] },
            },
        };

        for (const [key, preset] of Object.entries(presets)) {
            if (style?.toLowerCase().includes(key)) return preset;
        }

        return {
            base: { startPoint: [0.5, 0], endPoint: [0.5, 1], shape: "Linear Ramp", scatter: 0 },
            colors: { start: [1, 1, 1], end: [0, 0, 0] },
        };
    }
}

// ============================================================================
// 新增生成器 #6 ~ #20
// ============================================================================

export class GaussianBlurGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Blurriness": this.clamp(preset.base.blurriness * scaleFactor, 0, 500),
            "Blur Dimensions": preset.base.dimensions,
        };

        return {
            matchName: "ADBE Gaussian Blur 2",
            displayName: "Gaussian Blur",
            settings,
            confidence: 0.88,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { blurriness: number; dimensions: number };
            scale: number;
        }> = {
            "soft": {
                base: { blurriness: 3, dimensions: 3 },
                scale: 0.6,
            },
            "medium": {
                base: { blurriness: 10, dimensions: 3 },
                scale: 1.0,
            },
            "strong": {
                base: { blurriness: 30, dimensions: 3 },
                scale: 1.5,
            },
            "motionblur": {
                base: { blurriness: 15, dimensions: 1 },
                scale: 1.2,
            },
            "horizontal": {
                base: { blurriness: 12, dimensions: 1 },
                scale: 1.0,
            },
            "vertical": {
                base: { blurriness: 12, dimensions: 2 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { blurriness: 10, dimensions: 3 },
            scale: 1.0,
        };
    }
}

export class DirectionalBlurGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Blur Length": this.clamp(preset.base.blurLength * scaleFactor, 0, 500),
            "Direction": preset.base.direction,
        };

        return {
            matchName: "ADBE Directional Blur",
            displayName: "Directional Blur",
            settings,
            confidence: 0.86,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { blurLength: number; direction: number };
            scale: number;
        }> = {
            "horizontal": {
                base: { blurLength: 20, direction: 90 },
                scale: 1.0,
            },
            "vertical": {
                base: { blurLength: 20, direction: 0 },
                scale: 1.0,
            },
            "diagonal": {
                base: { blurLength: 18, direction: 45 },
                scale: 1.0,
            },
            "motionblur": {
                base: { blurLength: 30, direction: 90 },
                scale: 1.4,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { blurLength: 15, direction: 90 },
            scale: 1.0,
        };
    }
}

export class HueSaturationGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Channel Control": preset.base.channelControl,
            "Master Hue": this.clamp(preset.base.masterHue * scaleFactor, 0, 360),
            "Master Saturation": this.clamp(preset.base.masterSaturation * scaleFactor, -100, 100),
            "Master Lightness": this.clamp(preset.base.masterLightness * scaleFactor, -100, 100),
        };

        return {
            matchName: "ADBE HUE SATURATION",
            displayName: "Hue/Saturation",
            settings,
            confidence: 0.87,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { channelControl: number; masterHue: number; masterSaturation: number; masterLightness: number };
            scale: number;
        }> = {
            "vibrant": {
                base: { channelControl: 0, masterHue: 0, masterSaturation: 30, masterLightness: 0 },
                scale: 1.0,
            },
            "desaturated": {
                base: { channelControl: 0, masterHue: 0, masterSaturation: -50, masterLightness: 0 },
                scale: 1.0,
            },
            "warmshift": {
                base: { channelControl: 0, masterHue: 15, masterSaturation: 10, masterLightness: 0 },
                scale: 1.0,
            },
            "coolshift": {
                base: { channelControl: 0, masterHue: -15, masterSaturation: 5, masterLightness: 0 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { channelControl: 0, masterHue: 0, masterSaturation: 10, masterLightness: 0 },
            scale: 1.0,
        };
    }
}

export class CurvesGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Input Black": this.clamp(preset.base.inputBlack * scaleFactor, 0, 255),
            "Input White": this.clamp(preset.base.inputWhite, 0, 255),
            "Gamma": this.clamp(preset.base.gamma, 0.1, 10),
            "Output Black": this.clamp(preset.base.outputBlack, 0, 255),
            "Output White": this.clamp(preset.base.outputWhite, 0, 255),
        };

        return {
            matchName: "ADBE Protractor2",
            displayName: "Levels",
            settings,
            confidence: 0.84,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { inputBlack: number; inputWhite: number; gamma: number; outputBlack: number; outputWhite: number };
            scale: number;
        }> = {
            "highcontrast": {
                base: { inputBlack: 20, inputWhite: 235, gamma: 1.0, outputBlack: 0, outputWhite: 255 },
                scale: 1.0,
            },
            "bright": {
                base: { inputBlack: 0, inputWhite: 255, gamma: 1.3, outputBlack: 0, outputWhite: 255 },
                scale: 1.0,
            },
            "dark": {
                base: { inputBlack: 10, inputWhite: 255, gamma: 0.8, outputBlack: 0, outputWhite: 240 },
                scale: 1.0,
            },
            "cinematic": {
                base: { inputBlack: 15, inputWhite: 240, gamma: 0.9, outputBlack: 5, outputWhite: 245 },
                scale: 1.0,
            },
            "fade": {
                base: { inputBlack: 0, inputWhite: 255, gamma: 1.0, outputBlack: 15, outputWhite: 240 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { inputBlack: 0, inputWhite: 255, gamma: 1.0, outputBlack: 0, outputWhite: 255 },
            scale: 1.0,
        };
    }
}

export class ColorBalanceGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Shadow Red Balance": this.clamp(preset.base.shadowR * scaleFactor, -100, 100),
            "Shadow Green Balance": this.clamp(preset.base.shadowG * scaleFactor, -100, 100),
            "Shadow Blue Balance": this.clamp(preset.base.shadowB * scaleFactor, -100, 100),
            "Midtone Red Balance": this.clamp(preset.base.midR * scaleFactor, -100, 100),
            "Midtone Green Balance": this.clamp(preset.base.midG * scaleFactor, -100, 100),
            "Midtone Blue Balance": this.clamp(preset.base.midB * scaleFactor, -100, 100),
            "Hilight Red Balance": this.clamp(preset.base.hiR * scaleFactor, -100, 100),
            "Hilight Green Balance": this.clamp(preset.base.hiG * scaleFactor, -100, 100),
            "Hilight Blue Balance": this.clamp(preset.base.hiB * scaleFactor, -100, 100),
        };

        return {
            matchName: "ADBE Color Balance",
            displayName: "Color Balance",
            settings,
            confidence: 0.86,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { shadowR: number; shadowG: number; shadowB: number; midR: number; midG: number; midB: number; hiR: number; hiG: number; hiB: number };
            scale: number;
        }> = {
            "warm": {
                base: { shadowR: 20, shadowG: 5, shadowB: -10, midR: 5, midG: 0, midB: -5, hiR: 10, hiG: 5, hiB: -5 },
                scale: 1.0,
            },
            "cool": {
                base: { shadowR: -10, shadowG: 0, shadowB: 20, midR: -5, midG: 0, midB: 10, hiR: -5, hiG: 5, hiB: 15 },
                scale: 1.0,
            },
            "vintage": {
                base: { shadowR: 10, shadowG: 10, shadowB: -5, midR: 10, midG: 10, midB: -5, hiR: 5, hiG: 0, hiB: -5 },
                scale: 1.0,
            },
            "cinematic": {
                base: { shadowR: -5, shadowG: -5, shadowB: 15, midR: 0, midG: 0, midB: 5, hiR: 15, hiG: 5, hiB: -5 },
                scale: 1.0,
            },
            "tealorange": {
                base: { shadowR: -15, shadowG: 5, shadowB: 20, midR: 0, midG: 0, midB: 5, hiR: 20, hiG: 5, hiB: -15 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { shadowR: 0, shadowG: 0, shadowB: 0, midR: 0, midG: 0, midB: 0, hiR: 0, hiG: 0, hiB: 0 },
            scale: 1.0,
        };
    }
}

export class DropShadowGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Shadow Color": color?.rgb || preset.base.shadowColor,
            "Opacity": this.clamp(preset.base.opacity * scaleFactor, 0, 255),
            "Direction": preset.base.direction,
            "Distance": this.clamp(preset.base.distance * scaleFactor, 0, 3000),
            "Softness": this.clamp(preset.base.softness * scaleFactor, 0, 100),
        };

        return {
            matchName: "ADBE Drop Shadow",
            displayName: "Drop Shadow",
            settings,
            confidence: 0.90,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { shadowColor: number[]; opacity: number; direction: number; distance: number; softness: number };
            scale: number;
        }> = {
            "subtle": {
                base: { shadowColor: [0, 0, 0], opacity: 80, direction: 135, distance: 2, softness: 5 },
                scale: 0.5,
            },
            "medium": {
                base: { shadowColor: [0, 0, 0], opacity: 120, direction: 135, distance: 5, softness: 15 },
                scale: 1.0,
            },
            "dramatic": {
                base: { shadowColor: [0, 0, 0], opacity: 180, direction: 135, distance: 10, softness: 40 },
                scale: 1.5,
            },
            "neon": {
                base: { shadowColor: [0, 0.5, 1], opacity: 200, direction: 135, distance: 0, softness: 30 },
                scale: 1.2,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { shadowColor: [0, 0, 0], opacity: 100, direction: 135, distance: 5, softness: 10 },
            scale: 1.0,
        };
    }
}

export class FillGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const color = modifiers.color?.[0];
        const preset = this.getPreset(modifiers.style);

        const settings: Record<string, number | number[]> = {
            "Color": color?.rgb || preset.base.color,
        };

        return {
            matchName: "ADBE Fill",
            displayName: "Fill",
            settings,
            confidence: 0.92,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { color: number[] };
        }> = {
            "red": {
                base: { color: [1, 0, 0] },
            },
            "green": {
                base: { color: [0, 0.8, 0.2] },
            },
            "blue": {
                base: { color: [0, 0.4, 1] },
            },
            "white": {
                base: { color: [1, 1, 1] },
            },
            "black": {
                base: { color: [0, 0, 0] },
            },
            "yellow": {
                base: { color: [1, 0.9, 0] },
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { color: [1, 1, 1] },
        };
    }
}

export class StrokeGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Color": color?.rgb || preset.base.color,
            "Brush Size": this.clamp(preset.base.brushSize * scaleFactor, 1, 100),
            "Brush Hardness": this.clamp(preset.base.brushHardness, 0, 1),
            "Opacity": this.clamp(preset.base.opacity * scaleFactor, 0, 100),
            "Start": preset.base.start,
            "End": preset.base.end,
        };

        return {
            matchName: "ADBE Stroke",
            displayName: "Stroke",
            settings,
            confidence: 0.84,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { color: number[]; brushSize: number; brushHardness: number; opacity: number; start: number; end: number };
            scale: number;
        }> = {
            "thin": {
                base: { color: [1, 1, 1], brushSize: 2, brushHardness: 0.95, opacity: 100, start: 0, end: 100 },
                scale: 0.5,
            },
            "thick": {
                base: { color: [1, 1, 1], brushSize: 10, brushHardness: 0.8, opacity: 100, start: 0, end: 100 },
                scale: 1.5,
            },
            "soft": {
                base: { color: [1, 1, 1], brushSize: 6, brushHardness: 0.3, opacity: 70, start: 0, end: 100 },
                scale: 1.0,
            },
            "animated": {
                base: { color: [1, 1, 1], brushSize: 4, brushHardness: 0.9, opacity: 100, start: 0, end: 0 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { color: [1, 1, 1], brushSize: 4, brushHardness: 0.9, opacity: 100, start: 0, end: 100 },
            scale: 1.0,
        };
    }
}

export class NoiseGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Amount of Noise": this.clamp(preset.base.amount * scaleFactor, 0, 100),
            "Noise Type": preset.base.noiseType,
            "Clipping": preset.base.clipping,
        };

        return {
            matchName: "ADBE Noise",
            displayName: "Noise",
            settings,
            confidence: 0.83,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { amount: number; noiseType: number; clipping: number };
            scale: number;
        }> = {
            "filmgrain": {
                base: { amount: 4, noiseType: 1, clipping: 0 },
                scale: 0.6,
            },
            "heavy": {
                base: { amount: 30, noiseType: 0, clipping: 0 },
                scale: 1.5,
            },
            "interference": {
                base: { amount: 50, noiseType: 0, clipping: 1 },
                scale: 2.0,
            },
            "subtle": {
                base: { amount: 2, noiseType: 1, clipping: 0 },
                scale: 0.4,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { amount: 5, noiseType: 0, clipping: 0 },
            scale: 1.0,
        };
    }
}

export class SharpenGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Amount": this.clamp(preset.base.amount * scaleFactor, 0, 500),
            "Radius": this.clamp(preset.base.radius, 0, 127),
            "Threshold": this.clamp(preset.base.threshold, 0, 255),
        };

        return {
            matchName: "ADBE Unsharp Mask",
            displayName: "Unsharp Mask",
            settings,
            confidence: 0.85,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { amount: number; radius: number; threshold: number };
            scale: number;
        }> = {
            "subtle": {
                base: { amount: 20, radius: 1, threshold: 10 },
                scale: 0.5,
            },
            "medium": {
                base: { amount: 50, radius: 2, threshold: 5 },
                scale: 1.0,
            },
            "strong": {
                base: { amount: 100, radius: 3, threshold: 0 },
                scale: 1.5,
            },
            "ultra": {
                base: { amount: 200, radius: 5, threshold: 0 },
                scale: 2.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { amount: 50, radius: 2, threshold: 5 },
            scale: 1.0,
        };
    }
}

export class TexturizeGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Texture Layer": preset.base.textureLayer,
            "Texture Placement": preset.base.texturePlacement,
            "Texture Contrast": this.clamp(preset.base.contrast * scaleFactor, 0, 200),
            "Texture Brightness": this.clamp(preset.base.brightness, -100, 100),
            "Composite Operation": preset.base.compositeOp,
        };

        return {
            matchName: "ADBE Texturize",
            displayName: "Texturize",
            settings,
            confidence: 0.75,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { textureLayer: number; texturePlacement: number; contrast: number; brightness: number; compositeOp: number };
            scale: number;
        }> = {
            "subtle": {
                base: { textureLayer: 1, texturePlacement: 0, contrast: 50, brightness: 0, compositeOp: 1 },
                scale: 0.5,
            },
            "medium": {
                base: { textureLayer: 1, texturePlacement: 0, contrast: 100, brightness: 0, compositeOp: 1 },
                scale: 1.0,
            },
            "strong": {
                base: { textureLayer: 1, texturePlacement: 0, contrast: 150, brightness: 10, compositeOp: 2 },
                scale: 1.5,
            },
            "grunge": {
                base: { textureLayer: 1, texturePlacement: 1, contrast: 180, brightness: -20, compositeOp: 3 },
                scale: 2.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { textureLayer: 1, texturePlacement: 0, contrast: 100, brightness: 0, compositeOp: 1 },
            scale: 1.0,
        };
    }
}

export class RoughenEdgesGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Edge Type": preset.base.edgeType,
            "Edge Color": color?.rgb || preset.base.edgeColor,
            "Border": this.clamp(preset.base.border * scaleFactor, 0, 200),
            "Edge Sharpness": this.clamp(preset.base.edgeSharpness, 0, 10),
            "Fractal Influence": this.clamp(preset.base.fractalInfluence, 0, 1),
            "Scale": this.clamp(preset.base.scale, 10, 5000),
            "Complexity": this.clamp(preset.base.complexity, 1, 10),
            "Evolution": preset.base.evolution,
        };

        return {
            matchName: "ADBE Roughen Edges",
            displayName: "Roughen Edges",
            settings,
            confidence: 0.80,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { edgeType: number; edgeColor: number[]; border: number; edgeSharpness: number; fractalInfluence: number; scale: number; complexity: number; evolution: number };
            scale: number;
        }> = {
            "rough": {
                base: { edgeType: 1, edgeColor: [0.5, 0.5, 0.5], border: 20, edgeSharpness: 1, fractalInfluence: 0.5, scale: 100, complexity: 3, evolution: 0 },
                scale: 1.0,
            },
            "spiky": {
                base: { edgeType: 2, edgeColor: [0.3, 0.3, 0.3], border: 30, edgeSharpness: 5, fractalInfluence: 0.8, scale: 50, complexity: 6, evolution: 0 },
                scale: 1.3,
            },
            "rusty": {
                base: { edgeType: 3, edgeColor: [0.6, 0.3, 0.1], border: 40, edgeSharpness: 2, fractalInfluence: 0.6, scale: 80, complexity: 5, evolution: 0 },
                scale: 1.2,
            },
            "organic": {
                base: { edgeType: 4, edgeColor: [0.4, 0.5, 0.2], border: 15, edgeSharpness: 3, fractalInfluence: 0.7, scale: 200, complexity: 4, evolution: 0 },
                scale: 0.8,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { edgeType: 1, edgeColor: [0.5, 0.5, 0.5], border: 15, edgeSharpness: 2, fractalInfluence: 0.5, scale: 100, complexity: 3, evolution: 0 },
            scale: 1.0,
        };
    }
}

export class CCLensGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Size": this.clamp(preset.base.size * scaleFactor, 0, 300),
            "Curvature": this.clamp(preset.base.curvature * scaleFactor, -100, 100),
        };

        return {
            matchName: "CC Lens",
            displayName: "CC Lens",
            settings,
            confidence: 0.82,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { size: number; curvature: number };
            scale: number;
        }> = {
            "fisheye": {
                base: { size: 100, curvature: 80 },
                scale: 1.0,
            },
            "wideangle": {
                base: { size: 120, curvature: 40 },
                scale: 0.8,
            },
            "barrel": {
                base: { size: 80, curvature: 50 },
                scale: 1.0,
            },
            "pincushion": {
                base: { size: 80, curvature: -50 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { size: 100, curvature: 30 },
            scale: 1.0,
        };
    }
}

export class OpticsCompensationGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Field of View (FOV)": this.clamp(preset.base.fov * scaleFactor, 1, 200),
            "Reverse Lens Distortion": preset.base.reverseLens,
            "FOV Orientation": preset.base.fovOrientation,
        };

        return {
            matchName: "ADBE Optics Compensation",
            displayName: "Optics Compensation",
            settings,
            confidence: 0.83,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { fov: number; reverseLens: number; fovOrientation: number };
            scale: number;
        }> = {
            "mild": {
                base: { fov: 15, reverseLens: 0, fovOrientation: 0 },
                scale: 0.5,
            },
            "moderate": {
                base: { fov: 30, reverseLens: 0, fovOrientation: 0 },
                scale: 1.0,
            },
            "strong": {
                base: { fov: 60, reverseLens: 0, fovOrientation: 0 },
                scale: 1.5,
            },
            "reverse": {
                base: { fov: 30, reverseLens: 1, fovOrientation: 0 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { fov: 20, reverseLens: 0, fovOrientation: 0 },
            scale: 1.0,
        };
    }
}

export class SimpleChokerGenerator extends BaseGenerator {
    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const preset = this.getPreset(modifiers.style);
        const scaleFactor = intensityScale * preset.scale;

        const settings: Record<string, number | number[]> = {
            "Choke Matte": this.clamp(preset.base.chokeMatte * scaleFactor, -200, 200),
        };

        return {
            matchName: "ADBE Simple Choker",
            displayName: "Simple Choker",
            settings,
            confidence: 0.88,
        };
    }

    private getPreset(style?: string) {
        const presets: Record<string, {
            base: { chokeMatte: number };
            scale: number;
        }> = {
            "shrink": {
                base: { chokeMatte: 5 },
                scale: 1.0,
            },
            "expand": {
                base: { chokeMatte: -5 },
                scale: 1.0,
            },
            "tight": {
                base: { chokeMatte: 15 },
                scale: 1.0,
            },
            "loose": {
                base: { chokeMatte: -15 },
                scale: 1.0,
            },
            "subtle": {
                base: { chokeMatte: 2 },
                scale: 1.0,
            },
        };

        const normalizedStyle = (style || "").toLowerCase();
        for (const [key, preset] of Object.entries(presets)) {
            if (normalizedStyle.includes(key)) return preset;
        }

        return {
            base: { chokeMatte: 0 },
            scale: 1.0,
        };
    }
}

// ============================================================================
// UniversalEffectGenerator - 通用效果生成器
// 基于知识图谱自动生成效果参数，支持所有63个AE内置效果
// ============================================================================

export class UniversalEffectGenerator extends BaseGenerator {
    private matchName: string;
    private effectNode: EffectNode;

    constructor(matchName: string, context: GeneratorContext = {}) {
        super(context);
        this.matchName = matchName;
        const node = EFFECT_KNOWLEDGE_GRAPH[matchName];
        if (!node) {
            throw new Error(`Effect not found in knowledge graph: ${matchName}`);
        }
        this.effectNode = node;
    }

    generate(modifiers: {
        intensity?: IntensityRef[];
        color?: ColorRef[];
        temporal?: TemporalRef[];
        style?: string;
    }): EffectParams {
        const intensityScale = this.getIntensityScale(modifiers.intensity || []);
        const color = modifiers.color?.[0];
        const style = modifiers.style || "";

        const settings: Record<string, number | string | number[]> = {};

        for (const param of this.effectNode.parameters) {
            settings[param.name] = this.generateParamValue(param, intensityScale, color, style);
        }

        this.applyStyleOverrides(settings, style, intensityScale, color);

        return {
            matchName: this.matchName,
            displayName: this.effectNode.displayName,
            settings,
            confidence: this.effectNode.confidence,
        };
    }

    private generateParamValue(
        param: EffectParameter,
        intensityScale: number,
        color: ColorRef | undefined,
        style: string
    ): number | string | number[] {
        switch (param.type) {
            case "number": {
                const baseValue = (param.default as number) ?? 0;
                const scale = param.intensityScale ?? 0;
                if (scale > 0 && intensityScale !== 1.0) {
                    const scaled = baseValue * (1 + (intensityScale - 1) * scale);
                    return this.clamp(scaled, param.min ?? -Infinity, param.max ?? Infinity);
                }
                return baseValue;
            }
            case "color": {
                if (color && this.isColorParamSensitive(param.name)) {
                    return color.rgb;
                }
                return (param.default as number[]) ?? [1, 1, 1];
            }
            case "enum": {
                const enumOverride = this.getEnumOverride(param.name, style);
                if (enumOverride && param.enumValues?.includes(enumOverride)) {
                    return enumOverride;
                }
                return (param.default as string) ?? (param.enumValues?.[0] ?? "");
            }
            case "boolean": {
                return param.default === true ? 1 : 0;
            }
            case "point": {
                return (param.default as number[]) ?? [0.5, 0.5];
            }
            default:
                return param.default ?? 0;
        }
    }

    private isColorParamSensitive(paramName: string): boolean {
        const colorKeywords = ["color", "tint", "tone", "hue", "glow color", "shadow color"];
        const lowerName = paramName.toLowerCase();
        return colorKeywords.some(kw => lowerName.includes(kw));
    }

    private getEnumOverride(paramName: string, style: string): string | null {
        const styleLower = style.toLowerCase();
        const paramLower = paramName.toLowerCase();

        if (paramLower.includes("blur dimensions") || paramLower.includes("dimensions")) {
            if (styleLower.includes("horizontal")) return "Horizontal";
            if (styleLower.includes("vertical")) return "Vertical";
        }

        if (paramLower.includes("ramp shape") || paramLower.includes("shape")) {
            if (styleLower.includes("radial")) return "Radial Ramp";
            if (styleLower.includes("linear")) return "Linear Ramp";
        }

        if (paramLower.includes("render")) {
            if (styleLower.includes("fill")) return "Fill";
            if (styleLower.includes("edge")) return "Edges";
        }

        return null;
    }

    private applyStyleOverrides(
        settings: Record<string, number | string | number[]>,
        style: string,
        intensityScale: number,
        color: ColorRef | undefined
    ): void {
        const styleLower = style.toLowerCase();

        if (styleLower.includes("subtle") || styleLower.includes("mild") || styleLower.includes("轻微")) {
            this.scaleAllNumberParams(settings, 0.5);
        } else if (styleLower.includes("strong") || styleLower.includes("intense") || styleLower.includes("强烈")) {
            this.scaleAllNumberParams(settings, 1.5);
        } else if (styleLower.includes("extreme") || styleLower.includes("massive") || styleLower.includes("极端")) {
            this.scaleAllNumberParams(settings, 2.0);
        }
    }

    private scaleAllNumberParams(
        settings: Record<string, number | string | number[]>,
        factor: number
    ): void {
        for (const param of this.effectNode.parameters) {
            if (param.type === "number" && param.intensityScale && param.intensityScale > 0) {
                const current = settings[param.name] as number;
                const baseValue = (param.default as number) ?? 0;
                const diff = current - baseValue;
                settings[param.name] = this.clamp(
                    baseValue + diff * factor,
                    param.min ?? -Infinity,
                    param.max ?? Infinity
                );
            }
        }
    }
}

// ============================================================================
// SPECIALIZED_GENERATORS - 专用效果生成器（20个复杂效果）
// ============================================================================

const SPECIALIZED_GENERATORS: Record<string, typeof BaseGenerator> = {
    "ADBE Glo2": GlowGenerator,
    "ADBE Color Key": ColorKeyGenerator,
    "CC Particle World": CCParticleWorldGenerator,
    "ADBE Fractal Noise": FractalNoiseGenerator,
    "ADBE Ramp": RampGenerator,
    "ADBE Gaussian Blur 2": GaussianBlurGenerator,
    "ADBE Directional Blur": DirectionalBlurGenerator,
    "ADBE HUE SATURATION": HueSaturationGenerator,
    "ADBE Protractor2": CurvesGenerator,
    "ADBE Color Balance": ColorBalanceGenerator,
    "ADBE Drop Shadow": DropShadowGenerator,
    "ADBE Fill": FillGenerator,
    "ADBE Stroke": StrokeGenerator,
    "ADBE Noise": NoiseGenerator,
    "ADBE Unsharp Mask": SharpenGenerator,
    "ADBE Texturize": TexturizeGenerator,
    "ADBE Roughen Edges": RoughenEdgesGenerator,
    "CC Lens": CCLensGenerator,
    "ADBE Optics Compensation": OpticsCompensationGenerator,
    "ADBE Simple Choker": SimpleChokerGenerator,
};

// ============================================================================
// GENERATOR_REGISTRY - matchName → Generator 类映射（63个效果）
// 动态生成：有专用生成器用专用的，否则用通用生成器
// ============================================================================

export function getGeneratorClass(matchName: string): typeof BaseGenerator {
    const specialized = SPECIALIZED_GENERATORS[matchName];
    if (specialized) return specialized;
    if (EFFECT_KNOWLEDGE_GRAPH[matchName]) {
        return class extends UniversalEffectGenerator {
            constructor(context: GeneratorContext = {}) {
                super(matchName, context);
            }
        };
    }
    throw new Error(`Effect not found: ${matchName}`);
}

export const ALL_EFFECT_MATCHNAMES: string[] = Object.keys(EFFECT_KNOWLEDGE_GRAPH);

export const GENERATOR_REGISTRY: Record<string, typeof BaseGenerator> =
    ALL_EFFECT_MATCHNAMES.reduce((acc, matchName) => {
        acc[matchName] = getGeneratorClass(matchName);
        return acc;
    }, {} as Record<string, typeof BaseGenerator>);

export class EffectGeneratorFactory {
    private generators: Map<string, BaseGenerator> = new Map();
    private context: GeneratorContext;

    constructor(context: GeneratorContext = {}) {
        this.context = context;
        this.initAllGenerators();
    }

    private initAllGenerators(): void {
        for (const matchName of ALL_EFFECT_MATCHNAMES) {
            const GeneratorClass = getGeneratorClass(matchName);
            const generator = new GeneratorClass(this.context);
            const key = this.normalizeName(matchName);
            this.generators.set(key, generator);
            const displayName = EFFECT_KNOWLEDGE_GRAPH[matchName].displayName;
            this.generators.set(this.normalizeName(displayName), generator);
        }
    }

    private normalizeName(name: string): string {
        return name.toLowerCase().replace(/[^a-z0-9]/g, "");
    }

    getGenerator(effectName: string): BaseGenerator | undefined {
        return this.generators.get(this.normalizeName(effectName));
    }

    getGeneratorByMatchName(matchName: string): BaseGenerator | undefined {
        return this.generators.get(this.normalizeName(matchName));
    }

    listAvailableGenerators(): string[] {
        return ALL_EFFECT_MATCHNAMES;
    }

    getEffectCount(): number {
        return ALL_EFFECT_MATCHNAMES.length;
    }

    getEffectsByCategory(category: string): string[] {
        return ALL_EFFECT_MATCHNAMES.filter(
            name => EFFECT_KNOWLEDGE_GRAPH[name].category === category
        );
    }

    generateEffect(
        effectName: string,
        modifiers: {
            intensity?: IntensityRef[];
            color?: ColorRef[];
            temporal?: TemporalRef[];
            style?: string;
        }
    ): EffectParams | undefined {
        const generator = this.getGenerator(effectName);
        if (!generator) return undefined;
        return generator.generate(modifiers);
    }

    generateEffectByMatchName(
        matchName: string,
        modifiers: {
            intensity?: IntensityRef[];
            color?: ColorRef[];
            temporal?: TemporalRef[];
            style?: string;
        }
    ): EffectParams | undefined {
        const generator = this.getGeneratorByMatchName(matchName);
        if (!generator) return undefined;
        return generator.generate(modifiers);
    }

    setContext(context: Partial<GeneratorContext>): void {
        this.context = { ...this.context, ...context };
        for (const generator of this.generators.values()) {
            generator.context = { ...generator.context, ...context };
        }
    }
}

export const effectGeneratorFactory = new EffectGeneratorFactory();