// === Stage 3D Director - Auto Generated ===
var W = 1080, H = 1920, DUR = 30;

var mainComp = app.project.items.addComp('Stage3D_1784503981', 1080, 1920, 1, 30, 30);
mainComp.bgColor = [0.05, 0.05, 0.08];

// --- Materials ---
var mat_1 = null;
try { var io_1 = new ImportOptions(File('D:/AE-Work/output/VinlandSaga_Battle_V17.mp4')); mat_1 = app.project.importFile(io_1); } catch(e) {}

// --- Parallax Layers ---
// Parallax Layer 1: Z=0
if (typeof mat_1 !== 'undefined' && mat_1) {
  var pLayer0 = mainComp.layers.add(mat_1);
  pLayer0.name = 'Parallax_1';
  pLayer0.threeDLayer = true;
  pLayer0.property('ADBE Transform Group').property('ADBE Position').setValue([540.0, 960.0, 0]);
  pLayer0.property('ADBE Transform Group').property('ADBE Scale').setValue([100.0, 100.0]);
}

// --- Camera ---
// Camera: push_in (normal, intensity=1.0)
var cam = mainComp.layers.addCamera('Stage3D_Cam', [540.0, 960.0]);
cam.threeDLayer = true;
var camOpt = cam.property('ADBE Camera Options Group');
try { camOpt.property('ADBE Camera Zoom').setValue(864); } catch(e) {}
try { camOpt.property('ADBE Camera Depth of Field').setValue(1); } catch(e) {}
try { camOpt.property('ADBE Camera Focus Distance').setValue(800); } catch(e) {}
try { camOpt.property('ADBE Camera Aperture').setValue(28); } catch(e) {}
try { camOpt.property('ADBE Camera Blur Level').setValue(120); } catch(e) {}
try { camOpt.property('ADBE Iris Shape').setValue(3); } catch(e) {}
cam.property('ADBE Transform Group').property('ADBE Position').setValueAtTime(0, [540.0, 960.0, -800]);
cam.property('ADBE Transform Group').property('ADBE Position').setValueAtTime(15.0, [540.0, 960.0, -600]);
cam.property('ADBE Transform Group').property('ADBE Position').setValueAtTime(30, [540.0, 960.0, -400]);
cam.property('ADBE Transform Group').property('ADBE Position').expression = 'wiggle(1.5, 3) + value';

// --- Lighting ---
// === Three-Point Lighting ===
// Key Light (主光)
var keyLight = mainComp.layers.addLight('Key_Light', [756, 480]);
keyLight.threeDLayer = true;
keyLight.property('ADBE Light Options Group').property('ADBE Light Type').setValue(0);
keyLight.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(100);
keyLight.property('ADBE Light Options Group').property('ADBE Light Color').setValue([1.0, 0.96, 0.9]);
keyLight.property('ADBE Light Options Group').property('ADBE Casts Shadows').setValue(1);
keyLight.property('ADBE Light Options Group').property('ADBE Light Shadow Darkness').setValue(75);
keyLight.property('ADBE Light Options Group').property('ADBE Light Shadow Diffusion').setValue(12);
keyLight.property('ADBE Transform Group').property('ADBE Position').setValue([756, 480, -350]);
// Fill Light (补光)
var fillLight = mainComp.layers.addLight('Fill_Light', [378, 1152]);
fillLight.threeDLayer = true;
fillLight.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(35);
fillLight.property('ADBE Light Options Group').property('ADBE Light Color').setValue([0.85, 0.92, 1.0]);
fillLight.property('ADBE Light Options Group').property('ADBE Casts Shadows').setValue(0);
fillLight.property('ADBE Transform Group').property('ADBE Position').setValue([378, 1152, -100]);
// Rim Light (轮廓光)
var rimLight = mainComp.layers.addLight('Rim_Light', [756, 768]);
rimLight.threeDLayer = true;
rimLight.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(65);
rimLight.property('ADBE Light Options Group').property('ADBE Light Color').setValue([0.9, 0.95, 1.0]);
rimLight.property('ADBE Light Options Group').property('ADBE Casts Shadows').setValue(0);
rimLight.property('ADBE Transform Group').property('ADBE Position').setValue([756, 768, 300]);

// --- 3D Transitions ---
// 3D Transition: cube_flip_y (0.8s)
var transPivot = mainComp.layers.addNull(0.8);
transPivot.name = 'TransPivot';
transPivot.threeDLayer = true;
transPivot.property('ADBE Transform Group').property('ADBE Position').setValue([540.0, 960.0, 0]);
var transRot = transPivot.property('ADBE Transform Group').property('ADBE Rotation Y');
transRot.setValueAtTime(0, 0);
transRot.setValueAtTime(0.8, -90);
// 3D Transition: door_open (0.7s)
// Left door
var doorL = mainComp.layers.addSolid([0,0,0], 'Door_L', 540.0, 1920, 1, 0.7);
doorL.threeDLayer = true;
doorL.property('ADBE Transform Group').property('ADBE Anchor Point').setValue([540.0, 960.0, 0]);
doorL.property('ADBE Transform Group').property('ADBE Position').setValue([0, 960.0, 0]);
doorL.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime(0, 0);
doorL.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime(0.7, -90);
// Right door
var doorR = mainComp.layers.addSolid([0,0,0], 'Door_R', 540.0, 1920, 1, 0.7);
doorR.threeDLayer = true;
doorR.property('ADBE Transform Group').property('ADBE Anchor Point').setValue([0, 960.0, 0]);
doorR.property('ADBE Transform Group').property('ADBE Position').setValue([540.0, 960.0, 0]);
doorR.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime(0, 0);
doorR.property('ADBE Transform Group').property('ADBE Rotation Y').setValueAtTime(0.7, 90);

// --- Color Grade Adjustment ---
var colorAdj = mainComp.layers.addSolid([0.5,0.5,0.5], 'Color_Grade', W, H, 1, DUR);
colorAdj.adjustmentLayer = true;
colorAdj.moveToEnd();
var lumetri = colorAdj.property('ADBE Effect Parade').addProperty('ADBE Lumetri');
try { lumetri.property('Contrast').setValue(20); } catch(e) {}
try { lumetri.property('Saturation').setValue(15); } catch(e) {}

JSON.stringify({success: true, comp: mainComp.name, layers: mainComp.numLayers, stage3d: true});