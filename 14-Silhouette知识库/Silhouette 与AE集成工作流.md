# Silhouette 与 AE 集成工作流

## 一、完整工作流

```
用户输入 → Intent识别 → 知识库检索 → 模板匹配 → Silhouette执行 → AE集成
```

### 1.1 数据流

```
Silhouette输出
    ↓
Matte序列 (.exr) / 跟踪数据 (.json)
    ↓
AE导入并应用
    ↓
Track Matte 设置 / 关键帧应用
    ↓
合成输出
```

---

## 二、Matte 集成

### 2.1 在 AE 中导入 Matte

```javascript
function importSilhouetteMatte(mattePath, comp) {
    var matteFile = new File(mattePath);
    if (!matteFile.exists) {
        $.writeln("[AE] Matte file not found: " + mattePath);
        return null;
    }

    var io = new ImportOptions(matteFile);
    io.sequence = true;
    var matteFootage = app.project.importFile(io);
    matteFootage.name = "Silhouette_Matte";

    var matteLayer = comp.layers.add(matteFootage);
    matteLayer.name = "Silhouette_Matte";
    matteLayer.threeDLayer = true;
    matteLayer.enabled = false;

    return matteLayer;
}
```

### 2.2 设置 Track Matte

```javascript
function applyTrackMatte(targetLayer, matteLayer) {
    targetLayer.trackMatteType = TrackMatteType.ALPHA;
    targetLayer.trackMatteLayer = matteLayer;
}
```

---

## 三、跟踪数据集成

### 3.1 读取跟踪数据

```javascript
function loadTrackingData(jsonPath) {
    var file = new File(jsonPath);
    if (!file.exists) return null;

    file.open("r");
    var content = file.read();
    file.close();

    return JSON.parse(content);
}
```

### 3.2 应用跟踪数据

```javascript
function applyTrackingData(comp, trackingData) {
    var nullObj = comp.layers.addNull();
    nullObj.name = trackingData.nullObjectName || "Silhouette_Tracker";
    nullObj.threeDLayer = true;

    var keyframes = trackingData.keyframes || {};

    if (keyframes.Position) {
        var pos = nullObj.property("ADBE Transform Group").property("ADBE Position");
        for (var i = 0; i < keyframes.Position.length; i++) {
            var k = keyframes.Position[i];
            pos.setValueAtTime(k.time, k.value);
        }
    }

    if (keyframes.Rotation) {
        var rot = nullObj.property("ADBE Transform Group").property("ADBE Rotation");
        for (var i = 0; i < keyframes.Rotation.length; i++) {
            var k = keyframes.Rotation[i];
            rot.setValueAtTime(k.time, k.value);
        }
    }

    return nullObj;
}
```

---

## 四、完整集成脚本

```javascript
(function() {
    var comp = app.project.activeItem;
    if (!(comp instanceof CompItem)) {
        alert("请先选择一个合成");
        return;
    }

    var mattePath = "D:/AE-Work/silhouette_output/matte_[####].exr";
    var trackingPath = "D:/AE-Work/silhouette_output/tracking_data.json";

    var matteLayer = importSilhouetteMatte(mattePath, comp);
    
    if (matteLayer && comp.numLayers > 0) {
        var targetLayer = comp.layer(1);
        applyTrackMatte(targetLayer, matteLayer);
        $.writeln("[AE] Track Matte applied to: " + targetLayer.name);
    }

    var trackingData = loadTrackingData(trackingPath);
    if (trackingData) {
        var trackerNull = applyTrackingData(comp, trackingData);
        $.writeln("[AE] Tracking data applied to: " + trackerNull.name);
    }

    $.writeln("[AE] Silhouette integration complete");
})();
```

---

## 五、自动工作流

### 5.1 从用户输入到 AE 合成

```python
from ae_mcp_client import AECommandClient

client = AECommandClient(signature_enabled=False)

# 1. 执行 Silhouette Roto
roto_result = client.run_silhouette_roto(
    source_path="D:/AE-Work/视频素材库/frames/frame_001.png",
    output_path="D:/AE-Work/silhouette_output/matte_[####].exr"
)

# 2. 创建 AE 合成（自动使用 Silhouette Matte）
comp_result = client.create_e2e_music_video_with_silhouette(
    comp_name="一拳超人_E2E测试",
    matte_path="D:/AE-Work/silhouette_output/matte_[####].exr"
)

print("合成创建成功:", comp_result)
```

### 5.2 完整 API 调用流程

```python
# 完整工作流
client.run_silhouette_roto(...)      # 生成遮罩
client.run_silhouette_track(...)     # 生成跟踪数据
client.run_silhouette_paint(...)     # 修复画面
client.create_e2e_music_video_with_silhouette(...)  # 创建合成
```
