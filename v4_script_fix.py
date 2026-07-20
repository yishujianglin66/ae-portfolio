#!/usr/bin/env python3
"""
调用 V4-Pro 分析并修复 AE 脚本错误
"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from ai_agent import V4Agent

agent = V4Agent()

prompt = r"""
请分析以下 AE ExtendScript 脚本的错误并提供修复方案：

## 错误信息
```
TypeError: null is not an object (line 1305)
```

## 当前合成状态
- 仅创建了 2 个图层: ["Background_Vinland", "Soundtrack"]
- 缺少: Main_Thorfinn, Battle_Vinland, Camera_Controller, Audio Controller, Global_Grading 等
- Camera_Controller 为空

## 脚本关键部分

### 空对象创建和父级链接（可能出错位置）
```javascript
function createCameraNull(comp) {
    var nullLayer = comp.layers.addNull();
    nullLayer.name = "Camera_Controller";
    nullLayer.startTime = 0;
    nullLayer.scale.setValueAtTime(0, [100, 100]);
    nullLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2]);
    nullLayer.rotation.setValueAtTime(0, 0);
    
    // 链接所有主体图层到空对象
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        if (layer.name.indexOf("Main_") >= 0 || 
            layer.name.indexOf("Battle") >= 0 || 
            layer.name.indexOf("Outro") >= 0) {
            layer.parent = nullLayer;  // 可能出错位置
        }
    }
    return nullLayer;
}
```

### 图层顺序设置（可能出错位置）
```javascript
foregroundLayer.moveToBeginning();
fxLayer.moveAfter(foregroundLayer);
outroLayer.moveAfter(fxLayer);
thorfinnBattleLayer.moveAfter(outroLayer);
battleLayer.moveAfter(thorfinnBattleLayer);
mainLayer.moveAfter(battleLayer);
bgLayer.moveAfter(mainLayer);
```

### 素材导入
```javascript
var vinlandFootage = importFootage(VIDEO_PATH + "冰海战记.mp4");
var thorfinnFootage = importFootage(VIDEO_PATH + "托尔芬.mp4");
```

## 请分析

1. **错误原因**: 为什么图层只创建了2个？可能是脚本中断在哪里？
2. **parent属性**: AE JSX 中设置 `layer.parent = nullLayer` 是否正确？
3. **moveAfter**: 是否有语法错误？
4. **修复方案**: 提供完整的修复代码

请给出可直接运行的修复代码。
"""

print("=" * 60)
print("调用 V4-Pro 分析并修复 AE 脚本错误")
print("=" * 60)

result = agent.analyze(prompt)
print("\n" + "=" * 60)
print("V4 分析结果")
print("=" * 60)
print(result)

with open("scripts/script_fix_v4.json", "w", encoding="utf-8") as f:
    f.write(result)

print("\n[已保存] scripts/script_fix_v4.json")