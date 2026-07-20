// === Audio-Driven Edit (BPM=128.0) ===
var W=1920, H=1080, DUR=30.0, FPS=30;

var comp = app.project.items.addComp('AudioEdit', W, H, 1, DUR, FPS);

var audioFile = null;
try { var aio = new ImportOptions(File('D:/AE-Work/output/VinlandSaga_Battle_V17.mp4')); audioFile = app.project.importFile(aio); } catch(e) {}
if (audioFile) { var aLy = comp.layers.add(audioFile); aLy.name = 'BGM'; }

// --- Clip 1: energy=0.643, speed=1.2x ---
var mat_0 = null;
try { var io_0 = new ImportOptions(File('D:/AE-Work/output/VinlandSaga_Battle_V17.mp4')); mat_0 = app.project.importFile(io_0); } catch(e) {}
if (mat_0) {
  var ly_0 = comp.layers.add(mat_0);
  ly_0.name = 'Clip_1';
  ly_0.startTime = 0.0;
  ly_0.outPoint = 29.531;
  ly_0.timeRemapEnabled = true;
  try {
    ly_0.property('ADBE Effect Parade').property('ADBE Time Remapping').setValueAtTime(0, 0.0);
    ly_0.property('ADBE Effect Parade').property('ADBE Time Remapping').setValueAtTime(29.531, 35.4372);
  } catch(e) {}
  ly_0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0.0, 0);
  ly_0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(0.2, 100);
  ly_0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(29.331, 100);
  ly_0.property('ADBE Transform Group').property('ADBE Opacity').setValueAtTime(29.531, 0);
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(9.375, [107.2, 107.2]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(9.525, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(9.844, [109.5, 109.5]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(9.994, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(10.312, [111.7, 111.7]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(10.462, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(10.781, [113.4, 113.4]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(10.931000000000001, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(11.25, [114.5, 114.5]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(11.4, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(11.719, [115.0, 115.0]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(11.869, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(12.188, [114.8, 114.8]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(12.338000000000001, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(12.656, [113.8, 113.8]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(12.806000000000001, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(13.125, [112.2, 112.2]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(13.275, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(13.594, [110.2, 110.2]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(13.744, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(14.062, [107.9, 107.9]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(14.212, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(14.531, [105.6, 105.6]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(14.681000000000001, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(15.0, [103.4, 103.4]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(15.15, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(15.469, [101.7, 101.7]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(15.619, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(15.938, [100.5, 100.5]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(16.088, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(16.875, [100.2, 100.2]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(17.025, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(17.344, [101.2, 101.2]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(17.494, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(17.812, [102.7, 102.7]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(17.962, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(18.281, [104.7, 104.7]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(18.430999999999997, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(18.75, [107.0, 107.0]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(18.9, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(19.219, [109.4, 109.4]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(19.369, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(24.375, [112.8, 112.8]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(24.525, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(24.844, [110.1, 110.1]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(24.994, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(25.312, [107.3, 107.3]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(25.462, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(25.781, [104.6, 104.6]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(25.930999999999997, [100, 100]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(26.25, [101.9, 101.9]); } catch(e) {}
  try { ly_0.property('ADBE Transform Group').property('ADBE Scale').setValueAtTime(26.4, [100, 100]); } catch(e) {}
}

// --- Beat Markers ---
var markerLayer = comp.layers.addSolid([1,0,0], 'BeatMarkers', 2, 2, 1, DUR);
markerLayer.opacity = 0;
markerLayer.property('ADBE Marker Group').addMarker(0.0, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(0.469, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(0.938, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(1.406, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(1.875, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(2.344, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(2.812, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(3.281, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(3.75, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(4.219, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(4.688, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(5.156, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(5.625, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(6.094, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(6.562, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(7.031, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(7.5, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(7.969, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(8.438, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(8.906, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(9.375, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(9.844, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(10.312, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(10.781, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(11.25, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(11.719, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(12.188, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(12.656, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(13.125, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(13.594, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(14.062, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(14.531, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(15.0, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(15.469, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(15.938, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(16.406, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(16.875, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(17.344, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(17.812, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(18.281, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(18.75, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(19.219, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(19.688, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(20.156, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(20.625, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(21.094, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(21.562, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(22.031, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(22.5, 'beat', 0.1);
markerLayer.property('ADBE Marker Group').addMarker(22.969, 'beat', 0.1);

// --- Adjustment Layer ---
var adj = comp.layers.addSolid([0.5,0.5,0.5], 'Adjust', W, H, 1, DUR);
adj.adjustmentLayer = true;
try { var sharp = adj.Effects.addProperty('ADBE Sharpen'); sharp.property('ADBE Sharpen-0001').setValue(39); } catch(e) {}

JSON.stringify({success: true, bpm: 128.0, clips: 1, beats: 64});