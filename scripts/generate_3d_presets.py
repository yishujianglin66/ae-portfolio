import json

presets = []

# ========== 3D 文字 (5个) ==========

# 1. 立体文字
presets.append({
    "name": "3d_extruded_text",
    "category": "3d_effect",
    "subcategory": "3d_text",
    "description": "立体文字 - 通过多层叠加模拟3D挤出效果，配合摄像机与聚光灯呈现立体文字质感",
    "tags": ["3D", "立体文字", "extruded", "text", "lighting"],
    "parameters": {
        "textLayerName": {"type": "string", "description": "目标文字图层名"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "extrusionDepth": {"type": "number", "min": 10, "max": 300, "description": "挤出深度"},
        "layerCount": {"type": "integer", "min": 5, "max": 50, "description": "层叠数量"},
        "color": {"type": "array", "description": "文字颜色 [R,G,B] 0-1"},
        "lightIntensity": {"type": "number", "min": 50, "max": 200, "description": "灯光强度"}
    },
    "default_values": {
        "textLayerName": "立体文字",
        "duration": 3.0,
        "extrusionDepth": 100,
        "layerCount": 20,
        "color": "[0.2, 0.6, 1.0]",
        "lightIntensity": 100
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: ${textLayerName},
      duration: ${duration},
      extrusionDepth: ${extrusionDepth},
      layerCount: ${layerCount},
      color: ${color},
      lightIntensity: ${lightIntensity}
    };
    var baseLayer = comp.layers.byName(p.textLayerName);
    if (!baseLayer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      baseLayer = nt;
    }
    baseLayer.threeDLayer = true;
    var src = baseLayer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = 120;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var step = p.extrusionDepth / p.layerCount;
    for (var i = 1; i < p.layerCount; i++) {
      var dup = baseLayer.duplicate();
      dup.name = p.textLayerName + "_depth_" + i;
      dup.threeDLayer = true;
      var pos = dup.property("Transform").property("Position").value;
      pos[2] = i * step;
      dup.property("Transform").property("Position").setValue(pos);
      dup.property("Transform").property("Opacity").setValue(100 - (i / p.layerCount) * 60);
    }
    var cam = comp.layers.addCamera("3D Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -1000]);
    var light = comp.layers.addLight("Spot Light", LightType.SPOT, [comp.width/2, comp.height/2, -500]);
    light.property("Light Options").property("Intensity").setValue(p.lightIntensity);
    _result = {status:"success", message:"立体文字已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 2. 文字旋转
presets.append({
    "name": "text_rotation",
    "category": "3d_effect",
    "subcategory": "3d_text",
    "description": "文字旋转 - 3D文字沿Y轴旋转，配合摄像机展示立体文字侧面",
    "tags": ["3D", "文字旋转", "rotation", "text", "camera"],
    "parameters": {
        "textLayerName": {"type": "string", "description": "目标文字图层名"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "rotationY": {"type": "number", "min": -720, "max": 720, "description": "Y轴旋转角度"},
        "color": {"type": "array", "description": "文字颜色 [R,G,B] 0-1"}
    },
    "default_values": {
        "textLayerName": "旋转文字",
        "duration": 4.0,
        "rotationY": 360,
        "color": "[1.0, 0.3, 0.3]"
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: ${textLayerName},
      duration: ${duration},
      rotationY: ${rotationY},
      color: ${color}
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    layer.threeDLayer = true;
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = 120;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var yRot = layer.property("Transform").property("Y Rotation");
    yRot.setValueAtTime(comp.time, 0);
    yRot.setValueAtTime(comp.time + p.duration, p.rotationY);
    for (var k = 1; k <= yRot.numKeys; k++) {
      yRot.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    var cam = comp.layers.addCamera("Rotation Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -900]);
    _result = {status:"success", message:"文字旋转已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 3. 文字翻转
presets.append({
    "name": "text_flip",
    "category": "3d_effect",
    "subcategory": "3d_text",
    "description": "文字翻转 - 3D文字沿X轴或Y轴做180度翻转动画，适合标题转场",
    "tags": ["3D", "文字翻转", "flip", "text", "transition"],
    "parameters": {
        "textLayerName": {"type": "string", "description": "目标文字图层名"},
        "duration": {"type": "number", "min": 0.5, "max": 5.0, "description": "动画时长"},
        "flipAxis": {"type": "string", "description": "翻转轴 X 或 Y"},
        "color": {"type": "array", "description": "文字颜色 [R,G,B] 0-1"}
    },
    "default_values": {
        "textLayerName": "翻转文字",
        "duration": 2.0,
        "flipAxis": "Y",
        "color": "[0.3, 1.0, 0.5]"
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: ${textLayerName},
      duration: ${duration},
      flipAxis: ${flipAxis},
      color: ${color}
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    layer.threeDLayer = true;
    var src = layer.property("Source Text");
    var td = src.value;
    td.fillColor = p.color;
    td.fontSize = 120;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var rotProp = (p.flipAxis === "X") ? layer.property("Transform").property("X Rotation") : layer.property("Transform").property("Y Rotation");
    rotProp.setValueAtTime(comp.time, 0);
    rotProp.setValueAtTime(comp.time + p.duration * 0.5, 180);
    rotProp.setValueAtTime(comp.time + p.duration, 360);
    for (var k = 1; k <= rotProp.numKeys; k++) {
      rotProp.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    var cam = comp.layers.addCamera("Flip Camera", [comp.width/2, comp.height/2]);
    _result = {status:"success", message:"文字翻转已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 4. 文字层叠
presets.append({
    "name": "text_stacking",
    "category": "3d_effect",
    "subcategory": "3d_text",
    "description": "文字层叠 - 多层文字在Z轴上堆叠排列，形成景深层次感，摄像机穿越而过",
    "tags": ["3D", "文字层叠", "stacking", "depth", "text"],
    "parameters": {
        "textLayerName": {"type": "string", "description": "目标文字图层名前缀"},
        "layerCount": {"type": "integer", "min": 3, "max": 20, "description": "层叠数量"},
        "zSpacing": {"type": "number", "min": 20, "max": 200, "description": "Z轴间距"},
        "color": {"type": "array", "description": "文字颜色 [R,G,B] 0-1"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "摄像机穿越时长"}
    },
    "default_values": {
        "textLayerName": "层叠文字",
        "layerCount": 8,
        "zSpacing": 80,
        "color": "[1.0, 0.8, 0.2]",
        "duration": 5.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: ${textLayerName},
      layerCount: ${layerCount},
      zSpacing: ${zSpacing},
      color: ${color},
      duration: ${duration}
    };
    for (var i = 0; i < p.layerCount; i++) {
      var layer = comp.layers.byName(p.textLayerName + "_" + i);
      if (!layer) {
        var nt = comp.layers.addText(p.textLayerName + " " + (i+1));
        nt.name = p.textLayerName + "_" + i;
        layer = nt;
      }
      layer.threeDLayer = true;
      var src = layer.property("Source Text");
      var td = src.value;
      td.fillColor = p.color;
      td.fontSize = 80 + i * 4;
      td.justification = ParagraphJustification.CENTER;
      src.setValue(td);
      layer.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, i * p.zSpacing]);
      layer.property("Transform").property("Opacity").setValue(100 - i * 8);
    }
    var cam = comp.layers.addCamera("Stack Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValueAtTime(comp.time, [comp.width/2, comp.height/2, -600]);
    cam.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [comp.width/2, comp.height/2, p.layerCount * p.zSpacing + 400]);
    _result = {status:"success", message:"文字层叠已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 5. 文字景深
presets.append({
    "name": "text_depth_of_field",
    "category": "3d_effect",
    "subcategory": "3d_text",
    "description": "文字景深 - 开启摄像机景深模糊，文字从模糊到清晰或由近及远呈现电影级焦外效果",
    "tags": ["3D", "景深", "depth_of_field", "blur", "cinematic"],
    "parameters": {
        "textLayerName": {"type": "string", "description": "目标文字图层名"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "blurAmount": {"type": "number", "min": 0, "max": 200, "description": "模糊级别"},
        "focusDistance": {"type": "number", "min": 100, "max": 2000, "description": "对焦距离"},
        "aperture": {"type": "number", "min": 0, "max": 20, "description": "光圈大小"}
    },
    "default_values": {
        "textLayerName": "景深文字",
        "duration": 4.0,
        "blurAmount": 80,
        "focusDistance": 800,
        "aperture": 8
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = {
      textLayerName: ${textLayerName},
      duration: ${duration},
      blurAmount: ${blurAmount},
      focusDistance: ${focusDistance},
      aperture: ${aperture}
    };
    var layer = comp.layers.byName(p.textLayerName);
    if (!layer) {
      var nt = comp.layers.addText(p.textLayerName);
      nt.name = p.textLayerName;
      layer = nt;
    }
    layer.threeDLayer = true;
    var src = layer.property("Source Text");
    var td = src.value;
    td.fontSize = 120;
    td.justification = ParagraphJustification.CENTER;
    src.setValue(td);
    var cam = comp.layers.addCamera("DOF Camera", [comp.width/2, comp.height/2]);
    var camOpts = cam.property("Camera Options");
    camOpts.property("Depth of Field").setValue(1);
    camOpts.property("Focus Distance").setValue(p.focusDistance);
    camOpts.property("Aperture").setValue(p.aperture);
    camOpts.property("Blur Level").setValue(p.blurAmount);
    layer.property("Transform").property("Position").setValueAtTime(comp.time, [comp.width/2, comp.height/2, 0]);
    layer.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [comp.width/2, comp.height/2, 600]);
    _result = {status:"success", message:"文字景深已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# ========== 摄像机运动 (5个) ==========

# 6. 推镜头
presets.append({
    "name": "camera_dolly_in",
    "category": "3d_effect",
    "subcategory": "camera_movement",
    "description": "推镜头 - 摄像机沿Z轴向前推进，从远景平滑推向主体，营造聚焦与紧张感",
    "tags": ["3D", "推镜头", "dolly_in", "camera", "zoom"],
    "parameters": {
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "startZ": {"type": "number", "min": -5000, "max": -500, "description": "起始Z位置"},
        "endZ": {"type": "number", "min": -800, "max": 0, "description": "结束Z位置"}
    },
    "default_values": {
        "duration": 3.0,
        "startZ": -2000,
        "endZ": -600
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { duration: ${duration}, startZ: ${startZ}, endZ: ${endZ} };
    var cam = comp.layers.byName("Dolly Cam");
    if (!cam) {
      cam = comp.layers.addCamera("Dolly Cam", [comp.width/2, comp.height/2]);
    }
    var pos = cam.property("Transform").property("Position");
    pos.setValueAtTime(comp.time, [comp.width/2, comp.height/2, p.startZ]);
    pos.setValueAtTime(comp.time + p.duration, [comp.width/2, comp.height/2, p.endZ]);
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    _result = {status:"success", message:"推镜头已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 7. 拉镜头
presets.append({
    "name": "camera_dolly_out",
    "category": "3d_effect",
    "subcategory": "camera_movement",
    "description": "拉镜头 - 摄像机沿Z轴向后拉远，从近景退向全景，营造开阔与疏离感",
    "tags": ["3D", "拉镜头", "dolly_out", "camera", "wide"],
    "parameters": {
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "startZ": {"type": "number", "min": -800, "max": 0, "description": "起始Z位置"},
        "endZ": {"type": "number", "min": -5000, "max": -500, "description": "结束Z位置"}
    },
    "default_values": {
        "duration": 3.0,
        "startZ": -600,
        "endZ": -2500
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { duration: ${duration}, startZ: ${startZ}, endZ: ${endZ} };
    var cam = comp.layers.byName("Dolly Cam");
    if (!cam) {
      cam = comp.layers.addCamera("Dolly Cam", [comp.width/2, comp.height/2]);
    }
    var pos = cam.property("Transform").property("Position");
    pos.setValueAtTime(comp.time, [comp.width/2, comp.height/2, p.startZ]);
    pos.setValueAtTime(comp.time + p.duration, [comp.width/2, comp.height/2, p.endZ]);
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    _result = {status:"success", message:"拉镜头已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 8. 环绕
presets.append({
    "name": "camera_orbit",
    "category": "3d_effect",
    "subcategory": "camera_movement",
    "description": "环绕镜头 - 摄像机围绕中心目标做圆形轨道运动，360度展示3D场景",
    "tags": ["3D", "环绕", "orbit", "camera", "360"],
    "parameters": {
        "duration": {"type": "number", "min": 2.0, "max": 20.0, "description": "动画时长"},
        "radius": {"type": "number", "min": 200, "max": 2000, "description": "轨道半径"},
        "centerX": {"type": "number", "description": "中心点X"},
        "centerY": {"type": "number", "description": "中心点Y"},
        "heightZ": {"type": "number", "description": "摄像机高度Z偏移"},
        "revolutions": {"type": "number", "min": 0.5, "max": 5.0, "description": "旋转圈数"}
    },
    "default_values": {
        "duration": 6.0,
        "radius": 800,
        "centerX": 960,
        "centerY": 540,
        "heightZ": 0,
        "revolutions": 1.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { duration: ${duration}, radius: ${radius}, centerX: ${centerX}, centerY: ${centerY}, heightZ: ${heightZ}, revolutions: ${revolutions} };
    var cam = comp.layers.byName("Orbit Cam");
    if (!cam) {
      cam = comp.layers.addCamera("Orbit Cam", [comp.width/2, comp.height/2]);
    }
    var pos = cam.property("Transform").property("Position");
    var poi = cam.property("Transform").property("Point of Interest");
    poi.setValue([p.centerX, p.centerY, 0]);
    var steps = 60;
    for (var i = 0; i <= steps; i++) {
      var t = comp.time + (p.duration / steps) * i;
      var angle = (Math.PI * 2 * p.revolutions / steps) * i;
      var x = p.centerX + p.radius * Math.cos(angle);
      var z = p.heightZ + p.radius * Math.sin(angle);
      pos.setValueAtTime(t, [x, p.centerY, z]);
    }
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k, KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR);
    }
    _result = {status:"success", message:"环绕镜头已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 9. 平移
presets.append({
    "name": "camera_pan",
    "category": "3d_effect",
    "subcategory": "camera_movement",
    "description": "平移镜头 - 摄像机在X/Y轴上平滑平移，用于横向或纵向扫视3D场景",
    "tags": ["3D", "平移", "pan", "camera", "slide"],
    "parameters": {
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "startX": {"type": "number", "description": "起始X位置"},
        "endX": {"type": "number", "description": "结束X位置"},
        "startY": {"type": "number", "description": "起始Y位置"},
        "endY": {"type": "number", "description": "结束Y位置"}
    },
    "default_values": {
        "duration": 4.0,
        "startX": 200,
        "endX": 1720,
        "startY": 540,
        "endY": 540
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { duration: ${duration}, startX: ${startX}, endX: ${endX}, startY: ${startY}, endY: ${endY} };
    var cam = comp.layers.byName("Pan Cam");
    if (!cam) {
      cam = comp.layers.addCamera("Pan Cam", [comp.width/2, comp.height/2]);
    }
    var pos = cam.property("Transform").property("Position");
    pos.setValueAtTime(comp.time, [p.startX, p.startY, -800]);
    pos.setValueAtTime(comp.time + p.duration, [p.endX, p.endY, -800]);
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    _result = {status:"success", message:"平移镜头已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 10. 升降
presets.append({
    "name": "camera_crane",
    "category": "3d_effect",
    "subcategory": "camera_movement",
    "description": "升降镜头 - 摄像机在Y轴上垂直升降，模拟摇臂效果，营造宏大或俯瞰视角",
    "tags": ["3D", "升降", "crane", "camera", "vertical"],
    "parameters": {
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "startY": {"type": "number", "description": "起始Y高度"},
        "endY": {"type": "number", "description": "结束Y高度"}
    },
    "default_values": {
        "duration": 4.0,
        "startY": 900,
        "endY": 180
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { duration: ${duration}, startY: ${startY}, endY: ${endY} };
    var cam = comp.layers.byName("Crane Cam");
    if (!cam) {
      cam = comp.layers.addCamera("Crane Cam", [comp.width/2, comp.height/2]);
    }
    var pos = cam.property("Transform").property("Position");
    pos.setValueAtTime(comp.time, [comp.width/2, p.startY, -800]);
    pos.setValueAtTime(comp.time + p.duration, [comp.width/2, p.endY, -800]);
    for (var k = 1; k <= pos.numKeys; k++) {
      pos.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    _result = {status:"success", message:"升降镜头已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# ========== 3D 图层 (5个) ==========

# 11. 卡片翻转
presets.append({
    "name": "card_flip",
    "category": "3d_effect",
    "subcategory": "3d_layer",
    "description": "卡片翻转 - 3D图层沿Y轴做180度翻转，模拟卡片正反面切换效果",
    "tags": ["3D", "卡片翻转", "flip", "card", "layer"],
    "parameters": {
        "layerName": {"type": "string", "description": "目标图层名"},
        "duration": {"type": "number", "min": 0.5, "max": 5.0, "description": "动画时长"},
        "flipAxis": {"type": "string", "description": "翻转轴 X 或 Y"},
        "cardWidth": {"type": "number", "min": 100, "max": 800, "description": "卡片宽度"},
        "cardHeight": {"type": "number", "min": 100, "max": 800, "description": "卡片高度"},
        "color": {"type": "array", "description": "卡片颜色 [R,G,B] 0-1"}
    },
    "default_values": {
        "layerName": "翻转卡片",
        "duration": 1.5,
        "flipAxis": "Y",
        "cardWidth": 400,
        "cardHeight": 300,
        "color": "[0.2, 0.5, 0.9]"
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { layerName: ${layerName}, duration: ${duration}, flipAxis: ${flipAxis}, cardWidth: ${cardWidth}, cardHeight: ${cardHeight}, color: ${color} };
    var layer = comp.layers.byName(p.layerName);
    if (!layer) {
      layer = comp.layers.addSolid(p.color, p.layerName, p.cardWidth, p.cardHeight, 1);
    }
    layer.threeDLayer = true;
    var rotProp = (p.flipAxis === "X") ? layer.property("Transform").property("X Rotation") : layer.property("Transform").property("Y Rotation");
    rotProp.setValueAtTime(comp.time, 0);
    rotProp.setValueAtTime(comp.time + p.duration * 0.5, 90);
    rotProp.setValueAtTime(comp.time + p.duration, 180);
    for (var k = 1; k <= rotProp.numKeys; k++) {
      rotProp.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
    }
    _result = {status:"success", message:"卡片翻转已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 12. 立方体
presets.append({
    "name": "cube",
    "category": "3d_effect",
    "subcategory": "3d_layer",
    "description": "立方体 - 由6个面组成的3D立方体，可旋转展示各面，适合产品展示与魔方效果",
    "tags": ["3D", "立方体", "cube", "layer", "rotation"],
    "parameters": {
        "size": {"type": "number", "min": 100, "max": 800, "description": "立方体边长"},
        "color": {"type": "array", "description": "立方体基础颜色 [R,G,B] 0-1"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"},
        "rotationSpeed": {"type": "number", "min": 0.1, "max": 5.0, "description": "旋转圈数"}
    },
    "default_values": {
        "size": 300,
        "color": "[0.4, 0.6, 0.8]",
        "duration": 5.0,
        "rotationSpeed": 1.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { size: ${size}, color: ${color}, duration: ${duration}, rotationSpeed: ${rotationSpeed} };
    var cx = comp.width / 2, cy = comp.height / 2;
    var s = p.size;
    var faces = [
      {name:"Cube_Front", pos:[cx, cy, 0], rot:[0,0,0]},
      {name:"Cube_Back", pos:[cx, cy, -s], rot:[0,180,0]},
      {name:"Cube_Left", pos:[cx-s/2, cy, -s/2], rot:[0,-90,0]},
      {name:"Cube_Right", pos:[cx+s/2, cy, -s/2], rot:[0,90,0]},
      {name:"Cube_Top", pos:[cx, cy-s/2, -s/2], rot:[90,0,0]},
      {name:"Cube_Bottom", pos:[cx, cy+s/2, -s/2], rot:[-90,0,0]}
    ];
    var nullObj = comp.layers.addNull();
    nullObj.name = "Cube_Controller";
    nullObj.threeDLayer = true;
    for (var i = 0; i < faces.length; i++) {
      var f = faces[i];
      var layer = comp.layers.addSolid(p.color, f.name, s, s, 1);
      layer.threeDLayer = true;
      layer.property("Transform").property("Position").setValue(f.pos);
      layer.property("Transform").property("Orientation").setValue(f.rot);
      layer.parent = nullObj;
    }
    var yRot = nullObj.property("Transform").property("Y Rotation");
    yRot.setValueAtTime(comp.time, 0);
    yRot.setValueAtTime(comp.time + p.duration, p.rotationSpeed * 360);
    var cam = comp.layers.addCamera("Cube Camera", [cx, cy]);
    cam.property("Transform").property("Position").setValue([cx, cy, -s*2]);
    _result = {status:"success", message:"立方体已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 13. 照片墙
presets.append({
    "name": "photo_wall",
    "category": "3d_effect",
    "subcategory": "3d_layer",
    "description": "照片墙 - 多张3D图层在空间中排列成墙状矩阵，带有Z轴随机错位与呼吸动画",
    "tags": ["3D", "照片墙", "photo_wall", "gallery", "layer"],
    "parameters": {
        "photoCount": {"type": "integer", "min": 4, "max": 50, "description": "照片数量"},
        "rows": {"type": "integer", "min": 1, "max": 10, "description": "行数"},
        "cols": {"type": "integer", "min": 1, "max": 10, "description": "列数"},
        "spacing": {"type": "number", "min": 100, "max": 600, "description": "间距"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "photoCount": 12,
        "rows": 3,
        "cols": 4,
        "spacing": 350,
        "duration": 5.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { photoCount: ${photoCount}, rows: ${rows}, cols: ${cols}, spacing: ${spacing}, duration: ${duration} };
    var idx = 0;
    for (var r = 0; r < p.rows && idx < p.photoCount; r++) {
      for (var c = 0; c < p.cols && idx < p.photoCount; c++) {
        var layer = comp.layers.addSolid([Math.random(),Math.random(),Math.random()], "Photo_" + idx, 200, 150, 1);
        layer.threeDLayer = true;
        var x = comp.width/2 + (c - (p.cols-1)/2) * p.spacing;
        var y = comp.height/2 + (r - (p.rows-1)/2) * p.spacing * 0.75;
        var z = (Math.random() - 0.5) * 400;
        layer.property("Transform").property("Position").setValueAtTime(comp.time, [x, y, z]);
        layer.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [x, y, z + (Math.random()-0.5)*200]);
        idx++;
      }
    }
    var cam = comp.layers.addCamera("Wall Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -1500]);
    _result = {status:"success", message:"照片墙已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 14. 轮播
presets.append({
    "name": "carousel",
    "category": "3d_effect",
    "subcategory": "3d_layer",
    "description": "轮播 - 多个3D图层围绕中心点圆形排列，整体旋转形成3D转盘效果",
    "tags": ["3D", "轮播", "carousel", "layer", "circular"],
    "parameters": {
        "itemCount": {"type": "integer", "min": 3, "max": 20, "description": "项目数量"},
        "radius": {"type": "number", "min": 200, "max": 1500, "description": "排列半径"},
        "duration": {"type": "number", "min": 2.0, "max": 15.0, "description": "动画时长"},
        "rotationSpeed": {"type": "number", "min": 0.5, "max": 5.0, "description": "旋转圈数"}
    },
    "default_values": {
        "itemCount": 6,
        "radius": 600,
        "duration": 6.0,
        "rotationSpeed": 1.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { itemCount: ${itemCount}, radius: ${radius}, duration: ${duration}, rotationSpeed: ${rotationSpeed} };
    var nullObj = comp.layers.addNull();
    nullObj.name = "Carousel_Controller";
    nullObj.threeDLayer = true;
    for (var i = 0; i < p.itemCount; i++) {
      var angle = (Math.PI * 2 / p.itemCount) * i;
      var layer = comp.layers.addSolid([0.2+Math.random()*0.8,0.2+Math.random()*0.8,0.2+Math.random()*0.8], "Carousel_" + i, 300, 200, 1);
      layer.threeDLayer = true;
      var x = comp.width/2 + p.radius * Math.sin(angle);
      var z = p.radius * Math.cos(angle);
      layer.property("Transform").property("Position").setValue([x, comp.height/2, z]);
      layer.property("Transform").property("Y Rotation").setValue(angle * 180 / Math.PI);
      layer.parent = nullObj;
    }
    var yRot = nullObj.property("Transform").property("Y Rotation");
    yRot.setValueAtTime(comp.time, 0);
    yRot.setValueAtTime(comp.time + p.duration, p.rotationSpeed * 360);
    var cam = comp.layers.addCamera("Carousel Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -p.radius*2]);
    _result = {status:"success", message:"轮播已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 15. 书架
presets.append({
    "name": "bookshelf",
    "category": "3d_effect",
    "subcategory": "3d_layer",
    "description": "书架 - 多个3D图层像书本一样紧密排列在书架上，带有随机倾斜与高度变化",
    "tags": ["3D", "书架", "bookshelf", "layer", "arrange"],
    "parameters": {
        "bookCount": {"type": "integer", "min": 5, "max": 30, "description": "书本数量"},
        "shelfWidth": {"type": "number", "min": 500, "max": 2000, "description": "书架宽度"},
        "bookHeight": {"type": "number", "min": 150, "max": 500, "description": "基准高度"},
        "depth": {"type": "number", "min": 20, "max": 100, "description": "书本厚度"}
    },
    "default_values": {
        "bookCount": 10,
        "shelfWidth": 1200,
        "bookHeight": 300,
        "depth": 40
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { bookCount: ${bookCount}, shelfWidth: ${shelfWidth}, bookHeight: ${bookHeight}, depth: ${depth} };
    var startX = comp.width/2 - p.shelfWidth/2;
    var bookW = p.shelfWidth / p.bookCount;
    for (var i = 0; i < p.bookCount; i++) {
      var h = p.bookHeight * (0.7 + Math.random() * 0.6);
      var layer = comp.layers.addSolid([Math.random()*0.5,Math.random()*0.3,0.1], "Book_" + i, bookW-5, h, 1);
      layer.threeDLayer = true;
      var x = startX + i * bookW + bookW/2;
      var y = comp.height/2 + (p.bookHeight - h)/2;
      layer.property("Transform").property("Position").setValue([x, y, 0]);
      layer.property("Transform").property("Z Rotation").setValue((Math.random()-0.5)*5);
    }
    var cam = comp.layers.addCamera("Shelf Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -1000]);
    _result = {status:"success", message:"书架已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# ========== 灯光效果 (5个) ==========

# 16. 聚光灯
presets.append({
    "name": "spotlight",
    "category": "3d_effect",
    "subcategory": "lighting",
    "description": "聚光灯 - 添加3D聚光灯并设置锥角与羽化，可动画照射目标，突出主体",
    "tags": ["3D", "聚光灯", "spotlight", "light", "dramatic"],
    "parameters": {
        "lightName": {"type": "string", "description": "灯光名称"},
        "intensity": {"type": "number", "min": 20, "max": 300, "description": "灯光强度"},
        "coneAngle": {"type": "number", "min": 5, "max": 120, "description": "锥角角度"},
        "coneFeather": {"type": "number", "min": 0, "max": 100, "description": "锥角羽化"},
        "color": {"type": "array", "description": "灯光颜色 [R,G,B] 0-1"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "lightName": "聚光灯",
        "intensity": 120,
        "coneAngle": 45,
        "coneFeather": 30,
        "color": "[1.0, 0.95, 0.8]",
        "duration": 4.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { lightName: ${lightName}, intensity: ${intensity}, coneAngle: ${coneAngle}, coneFeather: ${coneFeather}, color: ${color}, duration: ${duration} };
    var light = comp.layers.addLight(p.lightName, LightType.SPOT, [comp.width/2, comp.height/2, -300]);
    var opts = light.property("Light Options");
    opts.property("Intensity").setValue(p.intensity);
    opts.property("Color").setValue(p.color);
    opts.property("Cone Angle").setValue(p.coneAngle);
    opts.property("Cone Feather").setValue(p.coneFeather);
    var pos = light.property("Transform").property("Position");
    pos.setValueAtTime(comp.time, [comp.width/2, comp.height/2, -300]);
    pos.setValueAtTime(comp.time + p.duration, [comp.width*0.7, comp.height*0.3, -400]);
    _result = {status:"success", message:"聚光灯已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 17. 体积光
presets.append({
    "name": "volumetric_light",
    "category": "3d_effect",
    "subcategory": "lighting",
    "description": "体积光 - 使用分形噪波与模糊模拟光束穿过介质的丁达尔效应",
    "tags": ["3D", "体积光", "volumetric", "light", "god_ray"],
    "parameters": {
        "lightName": {"type": "string", "description": "灯光名称"},
        "intensity": {"type": "number", "min": 50, "max": 300, "description": "灯光强度"},
        "fractalAmount": {"type": "number", "min": 100, "max": 800, "description": "噪波对比度"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "lightName": "体积光",
        "intensity": 150,
        "fractalAmount": 400,
        "duration": 5.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { lightName: ${lightName}, intensity: ${intensity}, fractalAmount: ${fractalAmount}, duration: ${duration} };
    var solid = comp.layers.addSolid([1,1,1], "Volumetric_" + p.lightName, comp.width, comp.height, 1);
    var fn = solid.Effects.addProperty("ADBE Fractal Noise");
    fn.property("ADBE Fractal Noise-0001").setValue(3);
    fn.property("ADBE Fractal Noise-0003").setValue(p.fractalAmount);
    var blur = solid.Effects.addProperty("ADBE Gaussian Blur");
    blur.property("ADBE Gaussian Blur-0001").setValue(80);
    solid.blendingMode = BlendingMode.SCREEN;
    var light = comp.layers.addLight(p.lightName, LightType.SPOT, [comp.width/2, -100, -200]);
    light.property("Light Options").property("Intensity").setValue(p.intensity);
    light.property("Transform").property("Position").setValueAtTime(comp.time, [comp.width/2, -100, -200]);
    light.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [comp.width*0.6, -100, -200]);
    _result = {status:"success", message:"体积光已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 18. 光晕
presets.append({
    "name": "lens_flare",
    "category": "3d_effect",
    "subcategory": "lighting",
    "description": "光晕 - 使用镜头光晕效果模拟强光进入镜头产生的炫光与光斑",
    "tags": ["3D", "光晕", "lens_flare", "glow", "light"],
    "parameters": {
        "layerName": {"type": "string", "description": "目标图层名"},
        "flareCenter": {"type": "array", "description": "光晕中心 [X,Y]"},
        "brightness": {"type": "number", "min": 0, "max": 300, "description": "亮度"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "layerName": "光晕层",
        "flareCenter": "[960, 540]",
        "brightness": 120,
        "duration": 4.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { layerName: ${layerName}, flareCenter: ${flareCenter}, brightness: ${brightness}, duration: ${duration} };
    var layer = comp.layers.byName(p.layerName);
    if (!layer) {
      layer = comp.layers.addSolid([0,0,0], p.layerName, comp.width, comp.height, 1);
    }
    var flare = layer.Effects.addProperty("Lens Flare");
    flare.property(1).setValue(p.flareCenter);
    flare.property(2).setValueAtTime(comp.time, 0);
    flare.property(2).setValueAtTime(comp.time + p.duration * 0.3, p.brightness);
    flare.property(2).setValueAtTime(comp.time + p.duration, 0);
    layer.blendingMode = BlendingMode.SCREEN;
    _result = {status:"success", message:"光晕已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 19. 阴影
presets.append({
    "name": "drop_shadow_3d",
    "category": "3d_effect",
    "subcategory": "lighting",
    "description": "3D阴影 - 启用3D图层的材质阴影属性，添加平行光产生真实投影",
    "tags": ["3D", "阴影", "shadow", "light", "realistic"],
    "parameters": {
        "layerName": {"type": "string", "description": "目标图层名"},
        "shadowColor": {"type": "array", "description": "阴影颜色 [R,G,B] 0-1"},
        "shadowOpacity": {"type": "number", "min": 0, "max": 100, "description": "阴影不透明度"},
        "lightName": {"type": "string", "description": "灯光名称"}
    },
    "default_values": {
        "layerName": "阴影主体",
        "shadowColor": "[0, 0, 0]",
        "shadowOpacity": 70,
        "lightName": "Shadow Light"
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { layerName: ${layerName}, shadowColor: ${shadowColor}, shadowOpacity: ${shadowOpacity}, lightName: ${lightName} };
    var layer = comp.layers.byName(p.layerName);
    if (!layer) {
      layer = comp.layers.addSolid([0.5,0.5,0.5], p.layerName, 400, 300, 1);
    }
    layer.threeDLayer = true;
    var mat = layer.property("Material Options");
    mat.property("Casts Shadows").setValue(1);
    mat.property("Accepts Lights").setValue(1);
    var ground = comp.layers.addSolid([0.2,0.2,0.2], "Ground", comp.width*2, comp.height*2, 1);
    ground.threeDLayer = true;
    ground.property("Transform").property("Position").setValue([comp.width/2, comp.height, 0]);
    ground.property("Transform").property("X Rotation").setValue(-90);
    var gmat = ground.property("Material Options");
    gmat.property("Accepts Shadows").setValue(1);
    gmat.property("Casts Shadows").setValue(0);
    var light = comp.layers.addLight(p.lightName, LightType.PARALLEL, [comp.width/2, -200, -300]);
    light.property("Light Options").property("Intensity").setValue(100);
    light.property("Light Options").property("Shadow Darkness").setValue(p.shadowOpacity);
    light.property("Light Options").property("Shadow Diffusion").setValue(20);
    _result = {status:"success", message:"3D阴影已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 20. 反射
presets.append({
    "name": "reflection",
    "category": "3d_effect",
    "subcategory": "lighting",
    "description": "反射 - 复制3D图层并垂直翻转，降低透明度与模糊处理，模拟镜面反射",
    "tags": ["3D", "反射", "reflection", "mirror", "layer"],
    "parameters": {
        "layerName": {"type": "string", "description": "目标图层名"},
        "reflectOpacity": {"type": "number", "min": 10, "max": 80, "description": "反射透明度"},
        "reflectDistance": {"type": "number", "min": 50, "max": 500, "description": "反射间距"}
    },
    "default_values": {
        "layerName": "反射主体",
        "reflectOpacity": 35,
        "reflectDistance": 300
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { layerName: ${layerName}, reflectOpacity: ${reflectOpacity}, reflectDistance: ${reflectDistance} };
    var layer = comp.layers.byName(p.layerName);
    if (!layer) {
      layer = comp.layers.addSolid([0.4,0.5,0.6], p.layerName, 400, 300, 1);
    }
    layer.threeDLayer = true;
    var reflect = layer.duplicate();
    reflect.name = p.layerName + "_Reflection";
    reflect.threeDLayer = true;
    var pos = layer.property("Transform").property("Position").value;
    reflect.property("Transform").property("Position").setValue([pos[0], pos[1] + p.reflectDistance, pos[2]]);
    reflect.property("Transform").property("Scale").setValue([100, -100, 100]);
    reflect.property("Transform").property("Opacity").setValue(p.reflectOpacity);
    var blur = reflect.Effects.addProperty("ADBE Fast Blur");
    blur.property("ADBE Fast Blur-0001").setValue(5);
    _result = {status:"success", message:"反射已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# ========== 粒子 3D (5个) ==========

# 21. 粒子云
presets.append({
    "name": "particle_cloud",
    "category": "3d_effect",
    "subcategory": "particle_3d",
    "description": "粒子云 - 大量小固态层在3D空间中随机分布形成云雾状效果",
    "tags": ["3D", "粒子云", "particle_cloud", "volumetric", "scatter"],
    "parameters": {
        "particleCount": {"type": "integer", "min": 20, "max": 200, "description": "粒子数量"},
        "cloudRadius": {"type": "number", "min": 200, "max": 1500, "description": "云团半径"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "particleCount": 60,
        "cloudRadius": 500,
        "duration": 5.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { particleCount: ${particleCount}, cloudRadius: ${cloudRadius}, duration: ${duration} };
    for (var i = 0; i < p.particleCount; i++) {
      var size = 5 + Math.random() * 10;
      var layer = comp.layers.addSolid([1,1,1], "CloudParticle_" + i, size, size, 1);
      layer.threeDLayer = true;
      var theta = Math.random() * Math.PI * 2;
      var phi = Math.random() * Math.PI;
      var r = p.cloudRadius * Math.random();
      var x = comp.width/2 + r * Math.sin(phi) * Math.cos(theta);
      var y = comp.height/2 + r * Math.sin(phi) * Math.sin(theta);
      var z = r * Math.cos(phi);
      layer.property("Transform").property("Position").setValue([x, y, z]);
      layer.property("Transform").property("Opacity").setValue(30 + Math.random() * 50);
    }
    var cam = comp.layers.addCamera("Cloud Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -p.cloudRadius*3]);
    _result = {status:"success", message:"粒子云已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 22. 粒子爆炸
presets.append({
    "name": "particle_explosion",
    "category": "3d_effect",
    "subcategory": "particle_3d",
    "description": "粒子爆炸 - 粒子从中心点向四周高速飞散，模拟爆炸冲击波效果",
    "tags": ["3D", "粒子爆炸", "explosion", "particle", "impact"],
    "parameters": {
        "particleCount": {"type": "integer", "min": 20, "max": 300, "description": "粒子数量"},
        "explosionForce": {"type": "number", "min": 200, "max": 2000, "description": "爆炸力度"},
        "duration": {"type": "number", "min": 0.5, "max": 5.0, "description": "动画时长"}
    },
    "default_values": {
        "particleCount": 80,
        "explosionForce": 800,
        "duration": 2.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { particleCount: ${particleCount}, explosionForce: ${explosionForce}, duration: ${duration} };
    var center = [comp.width/2, comp.height/2, 0];
    for (var i = 0; i < p.particleCount; i++) {
      var size = 4 + Math.random() * 8;
      var layer = comp.layers.addSolid([1,0.5+Math.random()*0.5,0.2], "Explosion_" + i, size, size, 1);
      layer.threeDLayer = true;
      layer.property("Transform").property("Position").setValueAtTime(comp.time, center);
      var vx = (Math.random() - 0.5) * p.explosionForce;
      var vy = (Math.random() - 0.5) * p.explosionForce;
      var vz = (Math.random() - 0.5) * p.explosionForce;
      layer.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [center[0] + vx, center[1] + vy, center[2] + vz]);
      var op = layer.property("Transform").property("Opacity");
      op.setValueAtTime(comp.time, 100);
      op.setValueAtTime(comp.time + p.duration, 0);
    }
    _result = {status:"success", message:"粒子爆炸已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 23. 粒子龙卷风
presets.append({
    "name": "particle_tornado",
    "category": "3d_effect",
    "subcategory": "particle_3d",
    "description": "粒子龙卷风 - 粒子围绕中心轴螺旋上升，模拟龙卷风旋转卷起效果",
    "tags": ["3D", "粒子龙卷风", "tornado", "particle", "swirl"],
    "parameters": {
        "particleCount": {"type": "integer", "min": 30, "max": 200, "description": "粒子数量"},
        "tornadoHeight": {"type": "number", "min": 300, "max": 1500, "description": "龙卷风高度"},
        "tornadoRadius": {"type": "number", "min": 100, "max": 600, "description": "旋转半径"},
        "duration": {"type": "number", "min": 2.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "particleCount": 60,
        "tornadoHeight": 800,
        "tornadoRadius": 250,
        "duration": 5.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { particleCount: ${particleCount}, tornadoHeight: ${tornadoHeight}, tornadoRadius: ${tornadoRadius}, duration: ${duration} };
    for (var i = 0; i < p.particleCount; i++) {
      var size = 3 + Math.random() * 6;
      var layer = comp.layers.addSolid([0.7,0.8,0.9], "Tornado_" + i, size, size, 1);
      layer.threeDLayer = true;
      var t = Math.random();
      var h = (t - 0.5) * p.tornadoHeight;
      var angle = Math.random() * Math.PI * 2;
      var r = p.tornadoRadius * (0.3 + Math.random() * 0.7);
      var x = comp.width/2 + r * Math.cos(angle);
      var z = r * Math.sin(angle);
      var y = comp.height/2 + h;
      layer.property("Transform").property("Position").setValueAtTime(comp.time, [x, y, z]);
      layer.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [comp.width/2 + r * Math.cos(angle + Math.PI*4), y, r * Math.sin(angle + Math.PI*4)]);
    }
    _result = {status:"success", message:"粒子龙卷风已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 24. 粒子螺旋
presets.append({
    "name": "particle_spiral",
    "category": "3d_effect",
    "subcategory": "particle_3d",
    "description": "粒子螺旋 - 粒子沿3D螺旋路径分布并运动，形成DNA双螺旋或星系旋臂效果",
    "tags": ["3D", "粒子螺旋", "spiral", "particle", "helix"],
    "parameters": {
        "particleCount": {"type": "integer", "min": 30, "max": 200, "description": "粒子数量"},
        "spiralRadius": {"type": "number", "min": 100, "max": 800, "description": "螺旋半径"},
        "spiralHeight": {"type": "number", "min": 200, "max": 1200, "description": "螺旋高度"},
        "duration": {"type": "number", "min": 2.0, "max": 10.0, "description": "动画时长"},
        "turns": {"type": "number", "min": 1, "max": 10, "description": "螺旋圈数"}
    },
    "default_values": {
        "particleCount": 80,
        "spiralRadius": 300,
        "spiralHeight": 600,
        "duration": 6.0,
        "turns": 2.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { particleCount: ${particleCount}, spiralRadius: ${spiralRadius}, spiralHeight: ${spiralHeight}, duration: ${duration}, turns: ${turns} };
    for (var i = 0; i < p.particleCount; i++) {
      var size = 3 + Math.random() * 5;
      var layer = comp.layers.addSolid([0.5+Math.random()*0.5,0.8,1], "Spiral_" + i, size, size, 1);
      layer.threeDLayer = true;
      var ratio = i / p.particleCount;
      var angle = ratio * Math.PI * 2 * p.turns;
      var r = p.spiralRadius * (1 - ratio * 0.5);
      var x = comp.width/2 + r * Math.cos(angle);
      var z = r * Math.sin(angle);
      var y = comp.height/2 - p.spiralHeight/2 + ratio * p.spiralHeight;
      layer.property("Transform").property("Position").setValueAtTime(comp.time, [x, y, z]);
      layer.property("Transform").property("Position").setValueAtTime(comp.time + p.duration, [comp.width/2 + r * Math.cos(angle + Math.PI*2), y, r * Math.sin(angle + Math.PI*2)]);
    }
    var cam = comp.layers.addCamera("Spiral Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -p.spiralRadius*2]);
    _result = {status:"success", message:"粒子螺旋已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# 25. 粒子雨
presets.append({
    "name": "particle_rain",
    "category": "3d_effect",
    "subcategory": "particle_3d",
    "description": "粒子雨 - 细长粒子从上方落下，模拟3D空间中的降雨效果",
    "tags": ["3D", "粒子雨", "rain", "particle", "weather"],
    "parameters": {
        "particleCount": {"type": "integer", "min": 30, "max": 300, "description": "粒子数量"},
        "rainSpeed": {"type": "number", "min": 200, "max": 1500, "description": "下落速度系数"},
        "duration": {"type": "number", "min": 1.0, "max": 10.0, "description": "动画时长"}
    },
    "default_values": {
        "particleCount": 100,
        "rainSpeed": 600,
        "duration": 4.0
    },
    "script_template": """(function() {
  var _result = {};
  try {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
      _result = {status:"error", message:"No active comp"};
      return JSON.stringify(_result);
    }
    var p = { particleCount: ${particleCount}, rainSpeed: ${rainSpeed}, duration: ${duration} };
    for (var i = 0; i < p.particleCount; i++) {
      var size = 2 + Math.random() * 4;
      var layer = comp.layers.addSolid([0.6,0.7,0.9], "Rain_" + i, size, size*3, 1);
      layer.threeDLayer = true;
      var x = Math.random() * comp.width;
      var z = (Math.random() - 0.5) * 600;
      var startY = -50 - Math.random() * 200;
      var endY = comp.height + 50 + Math.random() * 200;
      var fallDuration = p.duration * (0.8 + Math.random() * 0.4);
      layer.property("Transform").property("Position").setValueAtTime(comp.time, [x, startY, z]);
      layer.property("Transform").property("Position").setValueAtTime(comp.time + fallDuration, [x, endY, z]);
      layer.property("Transform").property("Opacity").setValue(40 + Math.random() * 60);
    }
    var cam = comp.layers.addCamera("Rain Camera", [comp.width/2, comp.height/2]);
    cam.property("Transform").property("Position").setValue([comp.width/2, comp.height/2, -800]);
    _result = {status:"success", message:"粒子雨已应用"};
  } catch(e) {
    _result = {status:"error", message:"Error: " + e.toString()};
  }
  return JSON.stringify(_result);
})();""",
    "compatibility": {"ae": ["2024", "2025", "2026"]}
})

# Write JSON
output_path = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae\presets\3d_effect.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(presets, f, ensure_ascii=False, indent=2)

print(f"Successfully wrote {len(presets)} presets to {output_path}")
