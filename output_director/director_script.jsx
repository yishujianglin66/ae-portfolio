// === AI Director Auto-Generated JSX ===
var W = 1080, H = 1920, FPS = 23.976;
var TOTAL_DUR = 30;

// 1. 创建主合成
var mainComp = app.project.items.addComp("AI_Director_1784515974", 1080, 1920, 1, 30, 23.976);

// 2. 导入素材
var mat_1 = null;
try {
  var io_1 = new ImportOptions(File("D:/AE-Work/output/VinlandSaga_Battle_V17.mp4"));
  mat_1 = app.project.importFile(io_1);
  mat_1.name = "Material_1";
} catch(e) { }

// 3. 段落编排
// --- Segment 1: 序章·冰封之怒 (压抑而肃穆，暴风雨前的宁静) ---
var seg0_layer = null;
if (typeof mat_1 !== "undefined" && mat_1) {
  seg0_layer = mainComp.layers.add(mat_1);
  seg0_layer.name = "Seg1_序章·冰封之怒";
  seg0_layer.startTime = 0;
  seg0_layer.outPoint = 4;
  // Camera: 推 (slow)
  seg0_layer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(0, [100, 100]);
  seg0_layer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(4, [107.5, 107.5]);
  seg0_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(0, 0);
  seg0_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(0.3, 100);
  seg0_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(3.7, 100);
  seg0_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(4, 0);
}
// Text: 命运之刃，早已淬火
var txt0 = mainComp.layers.addText("命运之刃，早已淬火");
var tdp0 = txt0.property("ADBE Text Properties").property("ADBE Text Document");
var tdoc0 = tdp0.value;
tdoc0.fontSize = 48;
tdoc0.fillColor = [0.83, 0.69, 0.22];
tdoc0.justification = ParagraphJustification.CENTER_JUSTIFY;
tdp0.setValue(tdoc0);
txt0.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 0]);
txt0.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(0, 0);
txt0.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(0.5, 100);
txt0.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(3.5, 100);
txt0.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(4, 0);
// Effects for segment 1
if (seg0_layer) {
}

// --- Segment 2: 崛起·复仇之火 (愤怒升腾，战意渐浓) ---
var seg1_layer = null;
if (typeof mat_1 !== "undefined" && mat_1) {
  seg1_layer = mainComp.layers.add(mat_1);
  seg1_layer.name = "Seg2_崛起·复仇之火";
  seg1_layer.startTime = 4;
  seg1_layer.outPoint = 12;
  // Camera: 摇 (normal)
  seg1_layer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(4, [W/2 - 50, H/2, 0]);
  seg1_layer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(12, [W/2 + 50, H/2, 0]);
  seg1_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(4, 0);
  seg1_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(4.3, 100);
  seg1_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(11.7, 100);
  seg1_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(12, 0);
}
// Text: 仇恨是火，也是剑
var txt1 = mainComp.layers.addText("仇恨是火，也是剑");
var tdp1 = txt1.property("ADBE Text Properties").property("ADBE Text Document");
var tdoc1 = tdp1.value;
tdoc1.fontSize = 40;
tdoc1.fillColor = [1.00, 0.27, 0.00];
tdoc1.justification = ParagraphJustification.CENTER_JUSTIFY;
tdp1.setValue(tdoc1);
txt1.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H*0.85, 0]);
txt1.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(4, [W/2, H/2 + 50, 0]);
txt1.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(4.5, [W/2, H*0.85, 0]);
txt1.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(4, 0);
txt1.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(4.3, 100);
txt1.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(11.7, 100);
txt1.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(12, 0);
// Effects for segment 2
if (seg1_layer) {
}

// --- Segment 3: 激战·血染冰海 (疯狂、密集、肾上腺素飙升) ---
var seg2_layer = null;
if (typeof mat_1 !== "undefined" && mat_1) {
  seg2_layer = mainComp.layers.add(mat_1);
  seg2_layer.name = "Seg3_激战·血染冰海";
  seg2_layer.startTime = 12;
  seg2_layer.outPoint = 22;
  // Camera: 移 (fast)
  seg2_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(12, 0);
  seg2_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(12.3, 100);
  seg2_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(21.7, 100);
  seg2_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(22, 0);
}
// Text: 以血还血！
var txt2 = mainComp.layers.addText("以血还血！");
var tdp2 = txt2.property("ADBE Text Properties").property("ADBE Text Document");
var tdoc2 = tdp2.value;
tdoc2.fontSize = 60;
tdoc2.fillColor = [1.00, 1.00, 1.00];
tdoc2.justification = ParagraphJustification.CENTER_JUSTIFY;
tdp2.setValue(tdoc2);
txt2.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 0]);
txt2.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(12, [50, 50]);
txt2.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(12.3, [115, 115]);
txt2.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(12.6, [100, 100]);
txt2.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(12, 0);
txt2.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(12.2, 100);
txt2.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(21.7, 100);
txt2.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(22, 0);
// Effects for segment 3
if (seg2_layer) {
}

// --- Segment 4: 喘息·寂静之后 (短暂宁静，雪花飘落，内心独白) ---
var seg3_layer = null;
if (typeof mat_1 !== "undefined" && mat_1) {
  seg3_layer = mainComp.layers.add(mat_1);
  seg3_layer.name = "Seg4_喘息·寂静之后";
  seg3_layer.startTime = 22;
  seg3_layer.outPoint = 26;
  // Camera: 拉 (slow)
  seg3_layer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(22, [110.0, 110.0]);
  seg3_layer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(26, [100, 100]);
  seg3_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(22, 0);
  seg3_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(22.3, 100);
  seg3_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(25.7, 100);
  seg3_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(26, 0);
}
// Text: 杀戮的尽头，是什么？
var txt3 = mainComp.layers.addText("杀戮的尽头，是什么？");
var tdp3 = txt3.property("ADBE Text Properties").property("ADBE Text Document");
var tdoc3 = tdp3.value;
tdoc3.fontSize = 36;
tdoc3.fillColor = [0.63, 0.63, 0.63];
tdoc3.justification = ParagraphJustification.CENTER_JUSTIFY;
tdp3.setValue(tdoc3);
txt3.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H*0.15, 0]);
txt3.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(22, 0);
txt3.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(22.3, 100);
txt3.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(25.7, 100);
txt3.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(26, 0);
// Effects for segment 4
if (seg3_layer) {
}

// --- Segment 5: 终章·战士的荣耀 (悲壮、决绝、升华) ---
var seg4_layer = null;
if (typeof mat_1 !== "undefined" && mat_1) {
  seg4_layer = mainComp.layers.add(mat_1);
  seg4_layer.name = "Seg5_终章·战士的荣耀";
  seg4_layer.startTime = 26;
  seg4_layer.outPoint = 30;
  // Camera: 环绕 (normal)
  seg4_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(26, 0);
  seg4_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(26.3, 100);
  seg4_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(29.7, 100);
  seg4_layer.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(30, 0);
}
// Text: 战士之魂，永不熄灭
var txt4 = mainComp.layers.addText("战士之魂，永不熄灭");
var tdp4 = txt4.property("ADBE Text Properties").property("ADBE Text Document");
var tdoc4 = tdp4.value;
tdoc4.fontSize = 52;
tdoc4.fillColor = [0.75, 0.75, 0.75];
tdoc4.justification = ParagraphJustification.CENTER_JUSTIFY;
tdp4.setValue(tdoc4);
txt4.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 0]);
txt4.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(26, 0);
txt4.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(26.5, 100);
txt4.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(29.5, 100);
txt4.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(30, 0);
// Effects for segment 5
if (seg4_layer) {
}

// 4. 调色调整层
var colorAdj = mainComp.layers.addSolid([0.5,0.5,0.5], "Color_Grade", W, H, 1, TOTAL_DUR);
colorAdj.adjustmentLayer = true;
colorAdj.moveToEnd();
var lumetri = colorAdj.property("ADBE Effect Parade").addProperty("ADBE Lumetri");
try { lumetri.property("Temperature").setValue(15); } catch(e) {}
try { lumetri.property("Contrast").setValue(35); } catch(e) {}
try { lumetri.property("Saturation").setValue(20); } catch(e) {}

// 5. 摄像机
var cam = mainComp.layers.addCamera("Director_Cam", [W/2, H/2]);
var camOpt = cam.property("ADBE Camera Options Group");
try { camOpt.property("ADBE Camera Zoom").setValue(W); } catch(e) {}
try { camOpt.property("ADBE Camera Depth of Field").setValue(1); } catch(e) {}
cam.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [W/2, H/2, -500]);
cam.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(TOTAL_DUR, [W/2, H/2, -300]);

// 6. 渲染输出
var outDir = new Folder("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_director");
if (!outDir.exists) outDir.create();
mainComp.renderSettings = {
  "outputModule": "Lossless",
};

var rqItem = app.project.renderQueue.items.add(mainComp);
var om = rqItem.outputModule(1);
om.file = new File("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_director/director_output.mp4");
app.project.renderQueue.render();

JSON.stringify({success: true, comp: mainComp.name, layers: mainComp.numLayers});

// === 3D Stage Enhancement ===
// === Stage 3D Director - Auto Generated ===
var W = 1080, H = 1920, DUR = 30;

var mainComp = app.project.items.addComp('Stage3D_1784515974', 1080, 1920, 1, 30, 23.976);
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
// Camera: 移 (normal, intensity=1.0)
var cam = mainComp.layers.addCamera('Stage3D_Cam', [540.0, 960.0]);
cam.threeDLayer = true;
var camOpt = cam.property('ADBE Camera Options Group');
try { camOpt.property('ADBE Camera Zoom').setValue(864); } catch(e) {}
try { camOpt.property('ADBE Camera Depth of Field').setValue(1); } catch(e) {}
try { camOpt.property('ADBE Camera Focus Distance').setValue(800); } catch(e) {}
try { camOpt.property('ADBE Camera Aperture').setValue(28); } catch(e) {}
try { camOpt.property('ADBE Camera Blur Level').setValue(120); } catch(e) {}
try { camOpt.property('ADBE Iris Shape').setValue(3); } catch(e) {}

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

// --- Color Grade Adjustment ---
var colorAdj = mainComp.layers.addSolid([0.5,0.5,0.5], 'Color_Grade', W, H, 1, DUR);
colorAdj.adjustmentLayer = true;
colorAdj.moveToEnd();
var lumetri = colorAdj.property('ADBE Effect Parade').addProperty('ADBE Lumetri');
try { lumetri.property('Contrast').setValue(20); } catch(e) {}
try { lumetri.property('Saturation').setValue(15); } catch(e) {}

JSON.stringify({success: true, comp: mainComp.name, layers: mainComp.numLayers, stage3d: true});