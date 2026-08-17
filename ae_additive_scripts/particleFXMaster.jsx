// particleFXMaster.jsx
// 粒子特效统一主控 - 一个入口调度所有粒子能力（对标 textFXMaster 架构）
// 用法: particleFXMaster(args)
// args = {action, ...params}
//
// 支持的 action:
//   "generate" → 生成单层粒子（类型: spark/dust/energy/embers/dissolve/rain/snow）
//   "layered"  → 一键三层粒子（前景大快/中景主体/背景微尘慢，不同混合模式）
//   "beat_burst" → 在给定 beat 时间戳上写出 Birth Rate 爆发关键帧
//   "atmosphere" → Fractal Noise 氛围层（烟雾/水墨/能量雾）
//   "catalog"  → 列出所有能力
//
// 全部参数 matchName 已于 2026-08 在中文 AE 实测验证（见 docs/ae_bridge_lessons.md）
// 注意: CC Rainfall 真实 matchName = "CSRainfall", CC Snowfall = "CSSnowfall"

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

// 兼容别名：_lib 实际提供 buildSuccess/buildError（textFXMaster 曾用错名）
function buildSuccessResponse(d) { return buildSuccess(d); }
function buildErrorResponse(code, msg) { return buildError(code, msg); }

// ============ 混合模式映射（必须用 BlendingMode 枚举对象，裸数字报错：无法转换数字枚举） ============
var BLEND = { normal: BlendingMode.NORMAL, add: BlendingMode.ADD,
    screen: BlendingMode.SCREEN, overlay: BlendingMode.OVERLAY,
    colorDodge: BlendingMode.COLOR_DODGE };

// ============ CC Particle World 属性 matchName 表（实测） ============
// 注意属性扁平排列：Producer/Physics/Particle 组内参数都是 -00xx 平铺
var PW = {
    BIRTH_RATE:   "CC Particle World-0004",
    LONGEVITY:    "CC Particle World-0005",
    POS_X:        "CC Particle World-0007",
    POS_Y:        "CC Particle World-0008",
    POS_Z:        "CC Particle World-0009",
    RAD_X:        "CC Particle World-0010",
    RAD_Y:        "CC Particle World-0011",
    RAD_Z:        "CC Particle World-0012",
    ANIMATION:    "CC Particle World-0015",
    VELOCITY:     "CC Particle World-0016",
    GRAVITY:      "CC Particle World-0018",
    RESISTANCE:   "CC Particle World-0041",
    PARTICLE_TYPE:"CC Particle World-0023",
    BIRTH_SIZE:   "CC Particle World-0024",
    DEATH_SIZE:   "CC Particle World-0025",
    SIZE_VAR:     "CC Particle World-0026",
    MAX_OPACITY:  "CC Particle World-0027",
    COLOR_MAP:    "CC Particle World-0028",
    BIRTH_COLOR:  "CC Particle World-0029",
    DEATH_COLOR:  "CC Particle World-0030",
    TRANSFER:     "CC Particle World-0039",
    RANDOM_SEED:  "CC Particle World-0104"
};

// ============ CC Particle Systems II 属性 matchName 表（实测） ============
var PS2 = {
    BIRTH_RATE:   "CC Particle Systems II-0001",
    LONGEVITY:    "CC Particle Systems II-0002",
    POSITION:     "CC Particle Systems II-0004",
    RAD_X:        "CC Particle Systems II-0005",
    RAD_Y:        "CC Particle Systems II-0006",
    ANIMATION:    "CC Particle Systems II-0009",
    VELOCITY:     "CC Particle Systems II-0010",
    GRAVITY:      "CC Particle Systems II-0012",
    RESISTANCE:   "CC Particle Systems II-0013",
    DIRECTION:    "CC Particle Systems II-0014",
    PARTICLE_TYPE:"CC Particle Systems II-0018",
    BIRTH_SIZE:   "CC Particle Systems II-0019",
    DEATH_SIZE:   "CC Particle Systems II-0020",
    SIZE_VAR:     "CC Particle Systems II-0021",
    MAX_OPACITY:  "CC Particle Systems II-0023",
    COLOR_MAP:    "CC Particle Systems II-0024",
    BIRTH_COLOR:  "CC Particle Systems II-0025",
    DEATH_COLOR:  "CC Particle Systems II-0026",
    TRANSFER:     "CC Particle Systems II-0028",
    RANDOM_SEED:  "CC Particle Systems II-0030"
};

// ============ 粒子类型预设（参数为归一化语义值，单位见注释） ============
// Particle Type 枚举（CC 系通用）: 1=Line 2=LensConvex 3=Star 4=Circle
//   5=FadedSphere 6=FadedCircle 7=Blobby 8=Textured 9=Shaded
// Animation 枚举: 1=DirectionAxis 2=Directional 3=Explosive 4=Twirl
//   5=Viscous 6=Gravity 7=Disorganized
// Color Map 枚举: 1=Solid 2=Birth-to-Death
// Physics 单位: velocity≈每秒粒子尺寸倍数; gravity≈世界单位/s²; 世界单位≈合成宽度
function getParticlePresets(comp) {
    var w = comp.width, h = comp.height;
    return {
        // 火花: 爆炸式向上喷射，黄→红，加色
        spark: {
            effect: "CC Particle World", blend: "add",
            set: function(e) {
                e.property(PW.BIRTH_RATE).setValue(3.0);
                e.property(PW.LONGEVITY).setValue(1.2);
                e.property(PW.POS_X).setValue(0);
                e.property(PW.POS_Y).setValue(0.3);
                e.property(PW.RAD_X).setValue(0.05);
                e.property(PW.RAD_Y).setValue(0.02);
                e.property(PW.RAD_Z).setValue(0.02);
                e.property(PW.ANIMATION).setValue(3);
                e.property(PW.VELOCITY).setValue(1.8);
                e.property(PW.GRAVITY).setValue(1.2);
                e.property(PW.PARTICLE_TYPE).setValue(4);
                e.property(PW.BIRTH_SIZE).setValue(0.04);
                e.property(PW.DEATH_SIZE).setValue(0.01);
                e.property(PW.SIZE_VAR).setValue(60);
                e.property(PW.MAX_OPACITY).setValue(100);
                e.property(PW.COLOR_MAP).setValue(2);
                e.property(PW.BIRTH_COLOR).setValue([1, 0.95, 0.6, 1]);
                e.property(PW.DEATH_COLOR).setValue([1, 0.25, 0.05, 1]);
                e.property(PW.TRANSFER).setValue(1);
            }
        },
        // 尘埃: 缓慢漂浮微尘，全屏弱光
        // 注意: CCPSII 的 Position/Radius 单位约等于像素但滑块上限 1000，必须钳制
        dust: {
            effect: "CC Particle Systems II", blend: "screen",
            set: function(e) {
                e.property(PS2.BIRTH_RATE).setValue(1.5);
                e.property(PS2.LONGEVITY).setValue(6);
                e.property(PS2.POSITION).setValue([Math.min(w / 2, 1000), Math.min(h / 2, 1000)]);
                e.property(PS2.RAD_X).setValue(Math.min(w / 2, 1000));
                e.property(PS2.RAD_Y).setValue(Math.min(h / 2, 1000));
                e.property(PS2.ANIMATION).setValue(7);
                e.property(PS2.VELOCITY).setValue(0.05);
                e.property(PS2.GRAVITY).setValue(0);
                e.property(PS2.PARTICLE_TYPE).setValue(5);
                e.property(PS2.BIRTH_SIZE).setValue(3);
                e.property(PS2.DEATH_SIZE).setValue(4);
                e.property(PS2.SIZE_VAR).setValue(0.8);
                e.property(PS2.MAX_OPACITY).setValue(0.35);
                e.property(PS2.COLOR_MAP).setValue(1);
                e.property(PS2.BIRTH_COLOR).setValue([1, 0.95, 0.85, 1]);
                e.property(PS2.DEATH_COLOR).setValue([1, 0.95, 0.85, 1]);
            }
        },
        // 能量流: 粘性汇聚流光，青→品（赛博朋克）
        energy: {
            effect: "CC Particle World", blend: "add",
            set: function(e) {
                e.property(PW.BIRTH_RATE).setValue(4.0);
                e.property(PW.LONGEVITY).setValue(2.0);
                e.property(PW.POS_X).setValue(0);
                e.property(PW.POS_Y).setValue(0);
                e.property(PW.RAD_X).setValue(0.4);
                e.property(PW.RAD_Y).setValue(0.2);
                e.property(PW.RAD_Z).setValue(0.1);
                e.property(PW.ANIMATION).setValue(5);
                e.property(PW.VELOCITY).setValue(0.8);
                e.property(PW.GRAVITY).setValue(0);
                e.property(PW.RESISTANCE).setValue(0.5);
                e.property(PW.PARTICLE_TYPE).setValue(1);
                e.property(PW.BIRTH_SIZE).setValue(0.03);
                e.property(PW.DEATH_SIZE).setValue(0.005);
                e.property(PW.SIZE_VAR).setValue(50);
                e.property(PW.MAX_OPACITY).setValue(90);
                e.property(PW.COLOR_MAP).setValue(2);
                e.property(PW.BIRTH_COLOR).setValue([0.2, 1, 1, 1]);
                e.property(PW.DEATH_COLOR).setValue([1, 0.2, 0.9, 1]);
                e.property(PW.TRANSFER).setValue(1);
            }
        },
        // 火星: 上升飘散余烬，橙红渐暗
        embers: {
            effect: "CC Particle Systems II", blend: "add",
            set: function(e) {
                e.property(PS2.BIRTH_RATE).setValue(2.0);
                e.property(PS2.LONGEVITY).setValue(3);
                e.property(PS2.POSITION).setValue([Math.min(w / 2, 1000), Math.min(h, 1000)]);
                e.property(PS2.RAD_X).setValue(Math.min(w * 0.45, 1000));
                e.property(PS2.RAD_Y).setValue(10);
                e.property(PS2.ANIMATION).setValue(2);
                e.property(PS2.VELOCITY).setValue(0.25);
                e.property(PS2.GRAVITY).setValue(-0.15);
                e.property(PS2.DIRECTION).setValue(90);
                e.property(PS2.PARTICLE_TYPE).setValue(5);
                e.property(PS2.BIRTH_SIZE).setValue(4);
                e.property(PS2.DEATH_SIZE).setValue(1);
                e.property(PS2.SIZE_VAR).setValue(0.7);
                e.property(PS2.MAX_OPACITY).setValue(0.9);
                e.property(PS2.COLOR_MAP).setValue(2);
                e.property(PS2.BIRTH_COLOR).setValue([1, 0.6, 0.15, 1]);
                e.property(PS2.DEATH_COLOR).setValue([0.3, 0.02, 0, 1]);
            }
        },
        // 粒子消散: 中心爆裂四散后消失（转场用）
        dissolve: {
            effect: "CC Particle Systems II", blend: "screen",
            set: function(e) {
                e.property(PS2.BIRTH_RATE).setValue(8.0);
                e.property(PS2.LONGEVITY).setValue(1.5);
                e.property(PS2.POSITION).setValue([Math.min(w / 2, 1000), Math.min(h / 2, 1000)]);
                e.property(PS2.RAD_X).setValue(30);
                e.property(PS2.RAD_Y).setValue(30);
                e.property(PS2.ANIMATION).setValue(3);
                e.property(PS2.VELOCITY).setValue(2.5);
                e.property(PS2.GRAVITY).setValue(0);
                e.property(PS2.RESISTANCE).setValue(0.8);
                e.property(PS2.PARTICLE_TYPE).setValue(4);
                e.property(PS2.BIRTH_SIZE).setValue(6);
                e.property(PS2.DEATH_SIZE).setValue(0.5);
                e.property(PS2.SIZE_VAR).setValue(0.5);
                e.property(PS2.MAX_OPACITY).setValue(1);
                e.property(PS2.COLOR_MAP).setValue(1);
                e.property(PS2.BIRTH_COLOR).setValue([1, 1, 1, 1]);
                e.property(PS2.DEATH_COLOR).setValue([0.6, 0.85, 1, 1]);
            }
        },
        // 雨: CC Rainfall（实测 matchName=CSRainfall）
        rain: {
            effect: "CSRainfall", blend: "normal",
            set: function(e) {
                e.property("CSRainfall-0001").setValue(3500);   // Drops
                e.property("CSRainfall-0002").setValue(2.5);    // Size
                e.property("CSRainfall-0004").setValue(4000);   // Speed
                e.property("CSRainfall-0005").setValue(-150);   // Wind
                e.property("CSRainfall-0008").setValue([0.7, 0.8, 1, 1]);
                e.property("CSRainfall-0009").setValue(40);     // Opacity
                e.property("CSRainfall-0016").setValue(0);      // Composite With Original 关
            }
        },
        // 雪: CC Snowfall（实测 matchName=CSSnowfall）
        snow: {
            effect: "CSSnowfall", blend: "normal",
            set: function(e) {
                e.property("CSSnowfall-0001").setValue(6000);   // Flakes
                e.property("CSSnowfall-0002").setValue(3);      // Size
                e.property("CSSnowfall-0005").setValue(200);    // Speed
                e.property("CSSnowfall-0007").setValue(30);     // Wind
                e.property("CSSnowfall-0018").setValue([1, 1, 1, 1]);
                e.property("CSSnowfall-0019").setValue(60);     // Opacity
                e.property("CSSnowfall-0026").setValue(0);      // Composite With Original 关
            }
        }
    };
}

// ============ 核心：在合成中创建一层粒子 ============
function createParticleLayer(comp, typeName, opts) {
    opts = opts || {};
    var presets = getParticlePresets(comp);
    var def = presets[typeName];
    if (!def) return { ok: false, error: "unknown_particle_type: " + typeName };

    var w = comp.width, h = comp.height;
    var layerName = opts.layerName || ("PFX_" + typeName);
    var solid = comp.layers.addSolid([0, 0, 0], layerName, w, h, comp.pixelAspect);
    solid.blendingMode = BLEND[def.blend] || BLEND.normal;

    var eff;
    try {
        eff = solid.Effects.addProperty(def.effect);
    } catch (eAdd) {
        solid.remove();
        return { ok: false, error: "add_effect_failed[" + def.effect + "]: " + eAdd.toString() };
    }

    try {
        def.set(eff);
        // 覆盖可选参数
        if (opts.birthRate !== undefined && eff.property(PW.BIRTH_RATE) !== null) {
            try { eff.property(PW.BIRTH_RATE).setValue(opts.birthRate); } catch (e1) {}
        }
        if (opts.birthRate !== undefined) {
            try { eff.property(PS2.BIRTH_RATE).setValue(opts.birthRate); } catch (e2) {}
        }
        if (opts.seed !== undefined && eff.property(PW.RANDOM_SEED) !== null) {
            try { eff.property(PW.RANDOM_SEED).setValue(opts.seed); } catch (e3) {}
            try { eff.property(PS2.RANDOM_SEED).setValue(opts.seed); } catch (e4) {}
        }
        if (opts.opacity !== undefined) solid.opacity = opts.opacity;
    } catch (eSet) {
        // 失败必须清理已创建的固态层，避免残留脏图层污染后续渲染
        try { solid.remove(); } catch (eRm) {}
        return { ok: false, error: "set_params_failed: " + eSet.toString() };
    }

    return { ok: true, layerName: layerName, layerIndex: solid.index, effect: def.effect, blend: def.blend };
}

// ============ beat_burst：在 beat 时间点写 Birth Rate 爆发关键帧 ============
function applyBeatBurst(comp, args) {
    var layerName = args.layerName;
    var layer = findLayerByName(comp, layerName);
    if (!layer) return { ok: false, error: "layer_not_found: " + layerName };
    // 用 matchName 定位 Effect Parade（ExtendScript 中 layer.numEffects 不存在，用 numProperties）
    var eff = null;
    try { eff = layer.property("ADBE Effect Parade"); } catch (eP) { eff = null; }
    if (!eff || !eff.numProperties || eff.numProperties < 1)
        return { ok: false, error: "layer_has_no_effect: numProps=" + (eff ? eff.numProperties : "null") };
    eff = eff.property(1);

    // 定位 Birth Rate（两种粒子系）
    var br = null;
    try { br = eff.property(PW.BIRTH_RATE); } catch (e1) { br = null; }
    if (!br) { try { br = eff.property(PS2.BIRTH_RATE); } catch (e2) { br = null; } }
    if (!br) return { ok: false, error: "birth_rate_prop_not_found" };

    var beats = args.beats || [];
    var base = args.baseRate !== undefined ? args.baseRate : (br.value || 2);
    var peak = args.peakRate !== undefined ? args.peakRate : base * 5;
    var decay = args.decay !== undefined ? args.decay : 0.12;

    br.setValueAtTime(0, base);
    var applied = 0;
    for (var i = 0; i < beats.length; i++) {
        var t = beats[i];
        if (t < 0 || t > comp.duration) continue;
        br.setValueAtTime(t, peak);
        br.setValueAtTime(Math.min(t + decay, comp.duration), base);
        applied++;
    }
    return { ok: true, layerName: layerName, beatsApplied: applied, baseRate: base, peakRate: peak };
}

// ============ 主入口 ============
function particleFXMaster(args) {
    var action = args.action || "catalog";

    if (action === "catalog") {
        return buildSuccessResponse({
            totalCapabilities: 4,
            types: ["spark", "dust", "energy", "embers", "dissolve", "rain", "snow"],
            actions: {
                generate: "particleFXMaster({action:'generate', compName:'X', type:'spark', options:{}})",
                layered: "particleFXMaster({action:'layered', compName:'X', preset:'amv_highenergy'})",
                beat_burst: "particleFXMaster({action:'beat_burst', compName:'X', layerName:'PFX_spark', beats:[0.5,1.0], peakRate:15})",
                atmosphere: "particleFXMaster({action:'atmosphere', compName:'X', mood:'smoke'})"
            },
            verifiedMatchNames: {
                ccParticleWorld: "CC Particle World (扁平 -0004~-0104)",
                ccParticleSystemII: "CC Particle Systems II (-0001~-0030)",
                ccRainfall: "CSRainfall",
                ccSnowfall: "CSSnowfall"
            }
        });
    }

    var comp = null;
    if (args.compName) comp = findCompByName(args.compName);
    else if (args.compIndex && app.project.item(args.compIndex) instanceof CompItem) comp = app.project.item(args.compIndex);
    if (!comp) return buildErrorResponse("comp_not_found", "合成未找到。请提供 compName 或 compIndex");

    // === 生成单层粒子 ===
    if (action === "generate") {
        app.beginUndoGroup("PFX_Generate_" + (args.type || "unknown"));
        try {
            var r = createParticleLayer(comp, args.type || "spark", args.options || {});
            app.endUndoGroup();
            if (!r.ok) return buildErrorResponse("generate_failed", r.error);
            return buildSuccessResponse({ action: "generate", comp: comp.name, type: args.type,
                layerName: r.layerName, layerIndex: r.layerIndex, effect: r.effect, blend: r.blend });
        } catch (e) {
            app.endUndoGroup();
            return buildErrorResponse("generate_error", e.toString());
        }
    }

    // === 一键三层粒子 ===
    if (action === "layered") {
        // 预设：三层结构（前中后景，不同混合模式与密度）
        var LAYERED_PRESETS = {
            amv_highenergy: [
                { type: "dust",   opts: { layerName: "PFX_BG_Dust",   opacity: 45 } },
                { type: "embers", opts: { layerName: "PFX_MID_Embers", opacity: 80 } },
                { type: "spark",  opts: { layerName: "PFX_FG_Spark",  opacity: 100, birthRate: 5 } }
            ],
            cinematic: [
                { type: "dust",   opts: { layerName: "PFX_BG_Dust",   opacity: 30 } },
                { type: "dust",   opts: { layerName: "PFX_MID_Dust",  opacity: 50, seed: 7, birthRate: 2.5 } },
                { type: "snow",   opts: { layerName: "PFX_FG_Flakes", opacity: 40 } }
            ],
            cyberpunk: [
                { type: "dust",   opts: { layerName: "PFX_BG_Dust",   opacity: 40 } },
                { type: "energy", opts: { layerName: "PFX_MID_Energy", opacity: 90 } },
                { type: "rain",   opts: { layerName: "PFX_FG_Rain",   opacity: 70 } }
            ]
        };
        var preset = args.preset || "amv_highenergy";
        var plan = LAYERED_PRESETS[preset];
        if (!plan) return buildErrorResponse("unknown_layered_preset", preset);

        app.beginUndoGroup("PFX_Layered_" + preset);
        try {
            var created = [];
            for (var i = 0; i < plan.length; i++) {
                var r = createParticleLayer(comp, plan[i].type, plan[i].opts || {});
                if (r.ok) created.push({ layerName: r.layerName, effect: r.effect, blend: r.blend });
                else created.push({ type: plan[i].type, error: r.error });
            }
            app.endUndoGroup();
            return buildSuccessResponse({ action: "layered", comp: comp.name, preset: preset, layers: created });
        } catch (e) {
            app.endUndoGroup();
            return buildErrorResponse("layered_error", e.toString());
        }
    }

    // === beat 爆发关键帧 ===
    if (action === "beat_burst") {
        app.beginUndoGroup("PFX_BeatBurst");
        try {
            var r2 = applyBeatBurst(comp, args);
            app.endUndoGroup();
            if (!r2.ok) return buildErrorResponse("beat_burst_failed", r2.error);
            return buildSuccessResponse({ action: "beat_burst", comp: comp.name,
                layerName: r2.layerName, beatsApplied: r2.beatsApplied, baseRate: r2.baseRate, peakRate: r2.peakRate });
        } catch (e) {
            app.endUndoGroup();
            return buildErrorResponse("beat_burst_error", e.toString());
        }
    }

    // === 氛围层（Fractal Noise 烟雾/水墨/能量雾） ===
    if (action === "atmosphere") {
        var MOODS = {
            smoke:  { contrast: 120, brightness: -25, scaleW: 180, scaleH: 120, evoSpeed: 30, tint: [0.45, 0.45, 0.5, 1], blend: "screen", opacity: 40 },
            ink:    { contrast: 200, brightness: -55, scaleW: 260, scaleH: 260, evoSpeed: 12, tint: [0.12, 0.12, 0.16, 1], blend: "normal", opacity: 60 },
            neonfog:{ contrast: 140, brightness: -30, scaleW: 220, scaleH: 160, evoSpeed: 25, tint: [0.1, 0.9, 0.95, 1], blend: "add", opacity: 35 }
        };
        var mood = MOODS[args.mood || "smoke"];
        if (!mood) return buildErrorResponse("unknown_mood", args.mood);

        app.beginUndoGroup("PFX_Atmosphere_" + (args.mood || "smoke"));
        try {
            var w = comp.width, h = comp.height;
            var solid = comp.layers.addSolid([0, 0, 0], "PFX_Atm_" + (args.mood || "smoke"), w, h, comp.pixelAspect);
            solid.blendingMode = BLEND[mood.blend] || BLEND.normal;
            solid.opacity = mood.opacity;
            var fn = solid.Effects.addProperty("ADBE Fractal Noise");
            fn.property("ADBE Fractal Noise-0001").setValue(4);      // FractalType: Dynamic
            fn.property("ADBE Fractal Noise-0002").setValue(3);      // NoiseType: Spline
            fn.property("ADBE Fractal Noise-0004").setValue(mood.contrast);
            fn.property("ADBE Fractal Noise-0005").setValue(mood.brightness);
            fn.property("ADBE Fractal Noise-0011").setValue(mood.scaleW);  // Scale Width
            fn.property("ADBE Fractal Noise-0012").setValue(mood.scaleH);  // Scale Height
            fn.property("ADBE Fractal Noise-0015").setValue(4);      // Complexity
            fn.property("ADBE Fractal Noise-0023").expression = "time*" + mood.evoSpeed; // Evolution
            var tint = solid.Effects.addProperty("ADBE Tint");
            tint.property("ADBE Tint-0002").setValue(mood.tint);     // Map To White
            app.endUndoGroup();
            return buildSuccessResponse({ action: "atmosphere", comp: comp.name, mood: args.mood || "smoke",
                layerName: solid.name, layerIndex: solid.index });
        } catch (e) {
            app.endUndoGroup();
            return buildErrorResponse("atmosphere_error", e.toString());
        }
    }

    return buildErrorResponse("unknown_action", "未知action: " + action + "。支持: catalog|generate|layered|beat_burst|atmosphere");
}

// 入口
var _args = (typeof args !== "undefined") ? args : {};
particleFXMaster(_args);
