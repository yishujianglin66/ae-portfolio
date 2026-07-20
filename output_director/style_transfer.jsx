// === Style Transfer: cinematic ===
var W = 1080, H = 1920, DUR = 23.2;

var comp = app.project.items.addComp('StyleTransfer_cinematic', 1080, 1920, 1, 23.2, 30.0);

var mat_1 = null;
try { var io = new ImportOptions(File('D:/AE-Work/output/VinlandSaga_Battle_V17.mp4')); mat_1 = app.project.importFile(io); } catch(e) {}

// --- Layers ---
if (mat_1) {
  var ly0 = comp.layers.add(mat_1);
  ly0.name = 'StyleLayer_1';
  ly0.startTime = 0.0;
  ly0.outPoint = 23.2;
  ly0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0.0, 0);
  ly0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0.3, 100);
  ly0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(22.9, 100);
  ly0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(23.2, 0);
}

// --- Style Effects (cinematic) ---
var adjLayer = comp.layers.addSolid([0.5,0.5,0.5], 'StyleAdj', W, H, 1, DUR);
adjLayer.adjustmentLayer = true;
adjLayer.moveToEnd();
try {
  var fx = adjLayer.Effects.addProperty('ADBE Brightness & Contrast 2');
  try { fx.property('Brightness').setValue(5.0); } catch(e) {}
  try { fx.property('Contrast').setValue(25.0); } catch(e) {}
  try { fx.property('Use Legacy').setValue(0); } catch(e) {}
} catch(e) {}
try {
  var fx = adjLayer.Effects.addProperty('ADBE Color Balance');
  try { fx.property('Red Shadow Level').setValue(5.0); } catch(e) {}
  try { fx.property('Green Shadow Level').setValue(2.0); } catch(e) {}
  try { fx.property('Blue Shadow Level').setValue(-3.0); } catch(e) {}
  try { fx.property('Red Midtone Level').setValue(8.0); } catch(e) {}
  try { fx.property('Green Midtone Level').setValue(4.0); } catch(e) {}
  try { fx.property('Blue Midtone Level').setValue(-5.0); } catch(e) {}
  try { fx.property('Red Highlight Level').setValue(3.0); } catch(e) {}
  try { fx.property('Green Highlight Level').setValue(2.0); } catch(e) {}
  try { fx.property('Blue Highlight Level').setValue(-2.0); } catch(e) {}
  try { fx.property('Preserve Luminosity').setValue(1); } catch(e) {}
} catch(e) {}
try {
  var fx = adjLayer.Effects.addProperty('ADBE Glo2');
  try { fx.property('Glow Threshold').setValue(70.0); } catch(e) {}
  try { fx.property('Glow Radius').setValue(15.0); } catch(e) {}
  try { fx.property('Glow Intensity').setValue(0.8); } catch(e) {}
  try { fx.property('Composite Original').setValue(On Top); } catch(e) {}
  try { fx.property('Glow Colors').setValue(A & B Colors); } catch(e) {}
  try { fx.property('Color Looping').setValue(Sawtooth B>A); } catch(e) {}
  try { fx.property('Color A').setValue([1.0, 0.8, 0.5, 1.0]); } catch(e) {}
  try { fx.property('Color B').setValue([1.0, 0.6, 0.3, 1.0]); } catch(e) {}
} catch(e) {}

// --- Text Style ---
var title = comp.layers.addText('CINEMATIC');
var tdp = title.property('ADBE Text Properties').property('ADBE Text Document');
var td = tdp.value;
td.fontSize = 48;
td.fillColor = [1, 1, 1];
td.justification = ParagraphJustification.CENTER_JUSTIFY;
tdp.setValue(td);
title.property('ADBE Transform Group').property('ADBE Position').setValue([W/2, H/2, 0]);
title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0, 0);
title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0.5, 100);
title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(3, 100);
title.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(3.5, 0);

JSON.stringify({success: true, style: 'cinematic', layers: comp.numLayers});