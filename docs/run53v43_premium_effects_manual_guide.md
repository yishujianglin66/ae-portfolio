# Manual Application Guide - run53v43 Premium Effects

**Quick Reference**: How to manually apply 139 premium plugin effects in After Effects

## Prerequisites

1. Open `output/unified_run53/run53_final_v43.mp4` in After Effects
2. Ensure all professional plugins are installed:
   - Red Giant Trapcode Particular
   - Red Giant Magic Bullet Looks
   - Boris FX Sapphire (S_Glow)
   - VideoCopilot Optical Flares
   - Digieffects Delirium v2.5
   - Tiffen Dfx v4 (Film Stocks)

## Workflow

### Step 1: Import Configuration
1. Open `output/unified_run53/run53v43_effects_premium_v2.json` in a text editor
2. Keep it visible as reference while working in AE

### Step 2: Create Adjustment Layers
For each effect in the JSON config:

```javascript
// Example: Apply Sapphire Glow at 5.0s-10.0s
var adj = comp.layers.addSolid([1,1,1], 'SapphireGlow_bloom_001', 1920, 1080, 1.0);
adj.adjustmentLayer = true;
adj.startTime = 5.0;
adj.outPoint = 10.0;

var fx = adj.property('ADBE Effect Parade').addProperty('S_Glow');
fx.property('Amount').setValue(50);
fx.property('Size').setValue(100);
fx.property('Color').setValue([1.0, 1.0, 1.0]);
```

### Step 3: Effect Type Reference

#### Twixtor (Slow Motion)
```javascript
layer.stretch = 200; // 50% speed
layer.property('Scale').setValueAtTime(start, [112, 112]);
layer.property('Scale').setValueAtTime(mid, [117.6, 117.6]);
layer.property('Scale').setValueAtTime(end, [112, 112]);
```

#### Zoom/Pan
```javascript
layer.property('Scale').setValueAtTime(start, [100, 100]);
layer.property('Scale').setValueAtTime(end, [106, 106]);
layer.property('Position').setValueAtTime(start, [960, 540]);
layer.property('Position').setValueAtTime(end, [960, 540]);
```

#### Bloom (Native AE Glow)
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('ADBE Glow');
fx.property('ADBE Glow-0001').setValue(6);    // Radius
fx.property('ADBE Glow-0002').setValue(38);   // Intensity (0-100)
fx.property('ADBE Glow-0003').setValue(80);   // Threshold (0-100)
```

#### Sapphire Glow
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('S_Glow');
fx.property('Amount').setValue(50);      // 0-100
fx.property('Size').setValue(100);       // 0-200
fx.property('Color').setValue([1, 1, 1]); // RGB
```

#### Optical Flares
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('Optical Flares');
fx.property('Brightness').setValue(100);  // 0-500
fx.property('Position').setValue([960, 540]);
```

#### Bokeh (Camera Lens Blur)
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('ADBE Camera Lens Blur');
fx.property('ADBE Camera Lens Blur-0001').setValue(2.0); // Blur amount
```

#### Bad TV (Noise HLS Auto)
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');
fx.property('ADBE Noise HLS Auto-0001').setValue(9.0); // Distortion
```

#### Delirium
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('Digieffects Delirium');
fx.property('Intensity').setValue(50); // 0-100
```

#### Motion Blur (CC Force Motion Blur)
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('CC Force Motion Blur');
fx.property('CC Force Motion Blur-0001').setValue(28);  // Samples
fx.property('CC Force Motion Blur-0002').setValue(180); // Shutter angle
```

#### Radial Blur
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');
fx.property('ADBE Radial Blur-0001').setValue(50); // Amount
```

#### Burst Radial (Animated)
```javascript
fx = adj.property('ADBE Radial Blur-0001');
fx.setValueAtTime(start, 90);              // Peak
fx.setValueAtTime(start + 0.05, 45);       // Half decay
fx.setValueAtTime(start + 0.1, 0);         // Tail
```

#### Burst BadTV (Animated)
```javascript
fx = adj.property('ADBE Noise HLS Auto-0001');
fx.setValueAtTime(start, 45);              // Peak distortion
fx.setValueAtTime(start + 0.033, 22.5);    // Half decay
fx.setValueAtTime(start + 0.067, 0);       // Tail
```

#### Particular (Trapcode)
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('Trapcode Particular');
fx.property('Particles/sec').setValue(200);
fx.property('Particle Size').setValue(2.0);
fx.property('Life').setValue(1.5);
```

#### Magic Bullet Looks
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('Magic Bullet Looks');
fx.property('Strength').setValue(70); // 0-100
```

#### Film Stocks (Tiffen)
```javascript
fx = adj.property('ADBE Effect Parade').addProperty('Tiffen Film Stocks');
fx.property('Grain Amount').setValue(30); // 0-100
// Select film type from preset dropdown
```

### Step 4: Beat-Aligned Envelope Modulation

For burst effects, animate intensity with exponential decay:

```javascript
// Example: Burst Radial with envelope
var peak_time = 15.0;
var decay = 0.08;  // seconds
var tail = decay * 0.3;

fx.setValueAtTime(peak_time, 90);                    // Peak
fx.setValueAtTime(peak_time + decay/2, 45);          // Half decay
fx.setValueAtTime(peak_time + decay + tail, 0);      // Tail
```

### Step 5: Render Settings

1. Composition → Add to Render Queue
2. Output Module: H.264 High Quality
3. Output To: `output/unified_run53/run53v43_premium_v2.mp4`
4. Enable Motion Blur on composition
5. Render

## Efficiency Tips

### Batch Processing
- Group effects by time range to minimize layer creation
- Use adjustment layers that span multiple segments when possible
- Pre-compose complex effect stacks for reuse

### Keyboard Shortcuts
- `Ctrl+Alt+Y`: New adjustment layer
- `U`: Reveal animated properties
- `UU`: Reveal all modified properties
- `F9`: Easy Ease keyframes

### Plugin Presets
- Save common effect settings as Animation Presets (.ffx)
- Use Sapphire/Magic Bullet preset libraries for quick application
- Create custom presets for frequently used combinations

## Validation Checklist

After applying all 139 effects:

- [ ] Each of 116 segments has ≥1 effect applied
- [ ] All burst effects aligned to beat onsets (±0.01s)
- [ ] Envelope modulation creates smooth transitions
- [ ] No overlapping adjustment layers causing render errors
- [ ] Motion blur enabled on composition
- [ ] Output resolution matches source (1920x1080)
- [ ] Frame rate consistent (30fps)

## Estimated Time

- **Experienced AE user**: 2-3 hours
- **Moderate experience**: 3-4 hours
- **Beginner**: 4-6 hours

## Troubleshooting

### Issue: Effect not found
**Solution**: Verify plugin is installed and licensed. Check exact effect name in Effects panel.

### Issue: Render crashes
**Solution**: Disable motion blur temporarily, reduce effect count per segment, check for circular dependencies.

### Issue: Slow playback
**Solution**: Set preview resolution to Half/Quarter, enable Adaptive Resolution, close other applications.

### Issue: Color shift after effects
**Solution**: Ensure adjustment layers use correct blending mode (Normal), check color space settings.

---

**Reference Config**: `output/unified_run53/run53v43_effects_premium_v2.json`
**Source Video**: `output/unified_run53/run53_final_v43.mp4`
**Target Output**: `output/unified_run53/run53v43_premium_v2.mp4`
