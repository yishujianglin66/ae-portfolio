# AE Advanced Expressions Library

## Easing & Animation Curves

### Elastic Out (Bounce)
```js
// Classic elastic bounce - use on Scale for pop-in effects
freq = 3; decay = 5; overshoot = 20;
t = Math.max(time - inPoint, 0);
v = overshoot * Math.sin(t * freq * 2 * Math.PI) / Math.exp(t * decay);
value + v;
```

### Elastic In (Anticipation)
```js
// Pull back then snap forward
freq = 4; decay = 6;
t = Math.max(time - inPoint, 0);
v = 50 * Math.sin(t * freq * 2 * Math.PI - Math.PI/2) / Math.exp(t * decay);
value + [0, v];
```

### Exponential Decay
```js
// Smooth settle - Position overshoot then settle
decay = 3; overshoot = 80;
t = Math.max(time - inPoint, 0);
offset = overshoot / Math.exp(t * decay);
value + [0, -offset];
```

### Custom Cubic Bezier Easing
```js
// Penner easing equations
function easeInOutCubic(t) { return t < 0.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2; }
dur = 1; // seconds
t = Math.min(Math.max((time - inPoint) / dur, 0), 1);
easeInOutCubic(t) * 100; // maps to 0-100
```

---

## Motion & Physics

### Inertial Bounce (Spring Physics)
```js
// Spring simulation for Position
n = 0; f = 6; // frequency
if (numKeys > 1) {
  n = nearestKey(time).index;
  if (key(n).time > time) n--;
}
if (n > 0) {
  t = time - key(n).time;
  v = -velocityAtTime(key(n).time - 0.001) * 10;
  amp = 0.08; decay = 4;
  value + v * amp * Math.sin(f * t * 2 * Math.PI) / Math.exp(decay * t);
} else { value; }
```

### Random Float (Organic Drift)
```js
// More natural than wiggle - drifts slowly
seedRandom(index, true);
freqX = 0.3 + random(0.1);
freqY = 0.4 + random(0.1);
ampX = 15 + random(10);
ampY = 10 + random(8);
phaseX = random(Math.PI * 2);
phaseY = random(Math.PI * 2);
value + [Math.sin(time * freqX + phaseX) * ampX, Math.cos(time * freqY + phaseY) * ampY];
```

### Gravity Simulation
```js
// Simulate gravity on Y axis only
g = 500; // gravity in px/s²
t = Math.max(time - inPoint, 0);
vy = g * t; // velocity increases linearly
value + [0, vy * 0.1]; // scale down for visual
```

### Pendulum Swing
```js
// Pendulum rotation
length = 200; // arm length
g = 9.8; // gravity
period = 2 * Math.PI * Math.sqrt(length / g);
angle = 30 * Math.sin(time * 2 * Math.PI / period) / Math.exp(time * 0.1);
```

---

## Text Animation

### Typewriter (Procedural)
```js
// Place on Source Text
txt = "YOUR TEXT HERE";
speed = 8; // chars per second
cursorBlink = Math.sin(time * 8) > 0 ? "|" : " ";
n = Math.floor((time - inPoint) * speed);
n = Math.min(n, txt.length);
txt.substr(0, n) + cursorBlink;
```

### Character Offset Cascade
```js
// Opacity cascade - each char fades in sequentially
delay = 0.05 * textIndex;
startT = inPoint + delay;
endT = startT + 0.4;
ease(time, startT, endT, 0, 100);
```

### Character Position Wave
```js
// Each character bounces up in sequence
delay = 0.03 * textIndex;
t = Math.max(time - (inPoint + delay), 0);
amp = 50; freq = 5; decay = 8;
offset = amp * Math.sin(t * freq * 2 * Math.PI) / Math.exp(t * decay);
value - [0, offset];
```

### Scramble Text Effect
```js
// Random character scrambling before resolving
chars = "!@#$%^&*()ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
txt = "FINAL TEXT";
seedRandom(textIndex, true);
progress = linear(time, inPoint, inPoint + 1, 0, 1);
randomIndex = Math.floor(random(chars.length));
progress < 0.5 ? chars[randomIndex] : txt[textIndex-1];
```

---

## Visual Effects

### Lens Flare Position Tracking
```js
// Auto-track flare to light source
L = thisComp.layer("Light");
L.toComp([0, 0, 0]);
```

### Vignette (Procedural)
```js
// Create vignette effect via expression on solid layer's Opacity
center = [thisComp.width/2, thisComp.height/2];
dist = length(transform.position, center);
maxDist = length([0, 0], [thisComp.width/2, thisComp.height/2]);
vignette = ease(dist, maxDist * 0.3, maxDist, 100, 0);
vignette;
```

### Parallax 3D (Fake Z-depth)
```js
// Place on 2D layer to simulate Z-depth parallax
zDepth = index * 100;
cam = thisComp.activeCamera;
if (cam) {
  camPos = cam.toWorld([0, 0, 0]);
  factor = zDepth / 1000;
  value + [(camPos[0] - thisComp.width/2) * factor, (camPos[1] - thisComp.height/2) * factor];
} else { value; }
```

### Pulse to Beat
```js
// Scale pulsing with beat
beatFreq = 2; // beats per second
beatAmp = 15; // scale percentage increase
pulse = Math.abs(Math.sin(time * beatFreq * Math.PI));
beat = Math.pow(pulse, 3); // sharpen the pulse
value + beat * beatAmp;
```

---

## Color & Styling

### Procedural Gradient
```js
// Color shift over time on Fill effect
t = time * 0.5;
r = Math.sin(t * 2 + 0) * 0.5 + 0.5;
g = Math.sin(t * 2 + 2) * 0.5 + 0.5;
b = Math.sin(t * 2 + 4) * 0.5 + 0.5;
[r, g, b, 1];
```

### Auto-Contrast Strobe
```js
// Quick flash on beat
beatInterval = 0.5; // seconds
phase = (time % beatInterval) / beatInterval;
flash = phase < 0.1 ? 30 : 0; // 10% duty cycle
value + flash;
```

---

## Utility Functions

### Safe Area Guide
```js
// Returns [x, y] clamped to title-safe area
margin = 0.1; // 10%
minX = thisComp.width * margin;
maxX = thisComp.width * (1 - margin);
minY = thisComp.height * margin;
maxY = thisComp.height * (1 - margin);
x = clamp(value[0], minX, maxX);
y = clamp(value[1], minY, maxY);
[x, y];
```

### Grid Snap
```js
// Snap position to grid
gridSize = 50;
x = Math.round(value[0] / gridSize) * gridSize;
y = Math.round(value[1] / gridSize) * gridSize;
[x, y];
```

### Loop Animation
```js
// Seamless loop
loopDuration = 3; // seconds
t = (time - inPoint) % loopDuration;
// Use 't' instead of 'time' in your animation
```

### Random Between (No Repetition)
```js
// Different random value each second, no repeats
seed = Math.floor(time);
seedRandom(seed, true);
random(10, 100);
```

---

## Puppet Pin & Character Rigging

### Puppet Pin → Null Binding
```js
// Place on Puppet Pin's Position property
// Allows Null to control Pin with full rotation/scale/parenting support
l = thisComp.layer("Ctrl_Wrist_R");
fromComp(l.toComp(l.anchorPoint));

// Usage:
// 1. Create Null named "Ctrl_Wrist_R"
// 2. Apply this expression to the wrist puppet pin
// 3. Now animate the Null instead of the Pin
// 4. Null supports: rotation, scale, parent chain, Easy Ease, wiggle()
```

### Null Hierarchy for IK-like Chain
```js
// Build a parent chain of Nulls for natural limb movement:
// Hip Null → Knee Null → Ankle Null (each parented to the previous)
// Moving Ankle Null = whole leg follows
// Moving Knee Null = upper leg bends naturally

// In each Null's Position, add this wiggle for subtle "living" feel:
wiggle(0.3, 3) // micro-movement = alive
```

### Arm Swing (Walk Cycle)
```js
// Place on Arm Null's Z Rotation
// Left arm and right arm should be 180° out of phase
amp = 15; // swing amplitude in degrees
freq = 1; // matches step frequency
phase = 0; // 0 for right arm, Math.PI for left arm (opposite)
Math.sin(time * freq * Math.PI * 2 + phase) * amp;

// Full walk cycle:
// Frame 0:  legs spread, right arm forward (positive rotation)
// Frame 7:  passing pose, arms neutral
// Frame 15: legs spread reversed, left arm forward
// Frame 23: passing pose, arms neutral
// Frame 30: back to frame 0
// Add loopOut("cycle", 0) on all keyframed properties
```

### Body Bounce (Walk Cycle)
```js
// Vertical body bounce during walk — on Body Null's Y Position
// Body is lowest when legs are spread, highest in passing pose
amp = 8; // bounce height in pixels
freq = 2; // twice the step frequency (bounce per step)
value - [0, Math.abs(Math.sin(time * freq * Math.PI)) * amp];
```

### Breathing Idle Animation
```js
// Subtle breathing for idle characters — on Chest/Spine Null's Scale
breathRate = 0.3; // breaths per second (18/min = relaxed)
breathDepth = 3; // scale percentage change
breath = Math.sin(time * breathRate * Math.PI * 2) * breathDepth;
value + [breath * 0.3, breath]; // X slightly less than Y
```

---

## Camera & 3D Expressions

### Handheld Camera Shake
```js
// Place on Camera Position — subtle documentary feel
wiggle(0.5, 6) // low freq, small amplitude

// Place on Camera Rotation for added realism
wiggle(0.3, 1.5)

// Combined: Position shake + Rotation shake = natural handheld
// Increase freq for action, decrease for calm scenes
```

### Focus Pull (Rack Focus)
```js
// Auto focus pull — on Camera Focus Distance
startFocus = 200;  // foreground
endFocus = 1200;   // background
pullStart = 1.0;   // seconds
pullEnd = 3.0;     // seconds
ease(time, pullStart, pullEnd, startFocus, endFocus);
```

### Parallax Depth (2.5D)
```js
// Simulate Z-depth parallax on 2D layers
// Each layer has different zDepth (index * layerSpacing)
zDepth = index * 80; // 80px spacing between layers
camX = thisComp.activeCamera.transform.position[0];
centerX = thisComp.width / 2;
factor = zDepth / 1000;
value + [(camX - centerX) * factor, 0];

// Layer 1 (zDepth=80):  foreground, moves more
// Layer 5 (zDepth=400): background, moves less
// Animate camera X position to see parallax effect
```

### Auto-Orient to Camera (Look At)
```js
// Makes a 3D layer always face the camera — on Y Rotation
cam = thisComp.activeCamera;
camPos = cam.toWorld([0,0,0]);
layerPos = toWorld(anchorPoint);
delta = camPos - layerPos;
radiansToDegrees(Math.atan2(delta[0], delta[2]));
```

---

## Color & Procedural Effects

### Depth-Based Color Grade
```js
// Apply to a color correction effect — warmer near, cooler far
// Requires a Depth Map layer
depthMap = thisComp.layer("Depth Map");
depth = depthMap.sampleImage(position, [1,1])[0]; // 0=near, 1=far
warmth = linear(depth, 0, 1, 0, -15); // cool down in distance
brightness = linear(depth, 0, 1, 0, -10); // darken in distance
value + [warmth, brightness, 0]; // RGB offset
```

### Light Wrap (Edge Blend)
```js
// Simulate background light wrapping around foreground edges
// Place on an Adjustment Layer above the foreground subject
bg = thisComp.layer("Background");
fg = thisComp.layer("Foreground");
edgeMask = fg.sampleImage(position, [3,3])[3]; // alpha at edges
bgColor = bg.sampleImage(position, [1,1]);
linear(edgeMask, 0, 1, bgColor * 0.3, [0,0,0,0]); // 30% wrap
```

### Flicker / Candle Light
```js
// Simulate candle/torch flicker on a light's Intensity
seedRandom(Math.floor(time * 10), true);
flicker = random(80, 120); // base flicker
detail = Math.sin(time * 30) * random(3, 8); // high-freq detail
slowSway = Math.sin(time * 0.7) * 10; // slow ambient sway
flicker + detail + slowSway;
```

---

## Data & Dynamic

### Beat Detection (from Audio Amplitude)
```js
// Scale pulse that snaps to beats
audioAmp = thisComp.layer("Audio Amplitude").effect("Both Channels")("Slider");
threshold = 15; // trigger level
beat = audioAmp > threshold ? 1 : 0;
// Use 'beat' to trigger scale pops, opacity flashes, etc.
```

### Counter / Timer
```js
// Animated number counter — on Source Text
startNum = 0;
endNum = 100;
duration = 2; // seconds
progress = linear(time, inPoint, inPoint + duration, startNum, endNum);
Math.round(progress).toString();
```

### Clock / Time Display
```js
// Real-time clock — on Source Text
currentTime = time + 3600; // start at 01:00:00
hours = Math.floor(currentTime / 3600) % 24;
minutes = Math.floor(currentTime / 60) % 60;
seconds = Math.floor(currentTime) % 60;
function pad(n) { return n < 10 ? "0" + n : n; }
pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
```

### Grid Distribution
```js
// Auto-arrange layers in a grid — on Position
cols = 5;
gap = 20;
cellW = 150;
cellH = 100;
startX = thisComp.width / 2 - (cols * (cellW + gap)) / 2;
startY = 100;
col = (index - 1) % cols;
row = Math.floor((index - 1) / cols);
[startX + col * (cellW + gap), startY + row * (cellH + gap)];
```
