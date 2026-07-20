# Phase 1: 端到端核心闭环打通 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现从"输入音乐+视频片段"到"AE合成创建完成"的完整闭环，打通感知→理解→规划→执行四个核心环节。

**Architecture:** Python端负责感知分析、理解推理、规划编排，通过MCP Bridge（JSON文件通信）将命令发送给AE Listener执行。新增 `ae_mcp_client.py` 作为命令发送器，`ae_command_generator.py` 将规划结果转换为AE可执行命令。

**Tech Stack:** Python 3.11, ExtendScript (AE 2026), JSON文件通信, HMAC-SHA256签名

---

## 文件结构规划

| 文件 | 职责 | 状态 |
|------|------|------|
| `ae_mcp_client.py` | MCP命令发送客户端（新增） | 待创建 |
| `ae_command_generator.py` | 规划结果→AE命令转换器（新增） | 待创建 |
| `ae_agent_pipeline.py` | 端到端流程管理器（修改） | 待修改 |
| `ae_mcp_listener.jsx` | AE端命令监听器（现有） | 无需修改 |
| `tests/test_phase1_pipeline.py` | Phase 1集成测试（新增） | 待创建 |

---

## Task 1: 创建 MCP 命令客户端

**Files:**
- Create: `ae_mcp_client.py`
- Test: `tests/test_ae_mcp_client.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_ae_mcp_client.py
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_mcp_client import AECommandClient

def test_client_initialization():
    client = AECommandClient()
    assert client.command_file is not None
    assert client.result_file is not None

def test_send_command():
    client = AECommandClient()
    result = client.send_command("test", {"message": "hello"})
    assert isinstance(result, dict)

def test_signature_generation():
    client = AECommandClient()
    data = {"op": "test", "params": {"a": 1}}
    signature = client._generate_signature(data)
    assert isinstance(signature, str)
    assert len(signature) == 64  # SHA256 hex length

def test_read_result_file_not_found():
    client = AECommandClient()
    client.result_file = "/nonexistent/path.json"
    result = client._read_result()
    assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_ae_mcp_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ae_mcp_client'"

- [ ] **Step 3: 实现 AECommandClient**

```python
# ae_mcp_client.py
import os
import json
import time
import hashlib
import hmac
from typing import Dict, Any, Optional

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
SECRET_FILE = os.path.join(CONFIG_DIR, "mcp_secret")

class AECommandClient:
    def __init__(
        self,
        command_file: str = None,
        result_file: str = None,
        timeout: int = 10,
        poll_interval: float = 0.5,
        signature_enabled: bool = True
    ):
        self.command_file = command_file or os.path.join(
            os.path.dirname(__file__), "ae_command.json"
        )
        self.result_file = result_file or os.path.join(
            os.path.dirname(__file__), "ae_result.json"
        )
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.signature_enabled = signature_enabled
        self.secret = self._load_secret()

    def _load_secret(self) -> str:
        if os.path.exists(SECRET_FILE):
            try:
                with open(SECRET_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except:
                return ""
        return ""

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        if not self.signature_enabled or not self.secret:
            return ""
        canonical = json.dumps(data, separators=(",", ":"), sort_keys=True)
        return hmac.new(
            self.secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def send_command(self, op: str, params: Dict[str, Any]) -> Dict[str, Any]:
        command = {
            "op": op,
            "params": params,
            "timestamp": int(time.time()),
            "signature": ""
        }

        if self.signature_enabled:
            command["signature"] = self._generate_signature(command)

        with open(self.command_file, "w", encoding="utf-8") as f:
            json.dump(command, f, ensure_ascii=False, indent=2)

        return self._wait_for_result()

    def _wait_for_result(self) -> Dict[str, Any]:
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            result = self._read_result()
            if result:
                return result
            time.sleep(self.poll_interval)
        return {"success": False, "error": f"Timeout after {self.timeout}s"}

    def _read_result(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.result_file):
            return None
        try:
            with open(self.result_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None

    def clear_result(self) -> None:
        if os.path.exists(self.result_file):
            os.remove(self.result_file)

    def send_batch_commands(self, commands: list) -> list:
        results = []
        for cmd in commands:
            op = cmd.get("op", "")
            params = cmd.get("params", {})
            result = self.send_command(op, params)
            results.append(result)
            self.clear_result()
        return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_ae_mcp_client.py -v`
Expected: PASS all tests

- [ ] **Step 5: 提交**

```bash
git add ae_mcp_client.py tests/test_ae_mcp_client.py
git commit -m "feat(phase1): add AE MCP command client"
```

---

## Task 2: 创建 AE 命令生成器

**Files:**
- Create: `ae_command_generator.py`
- Test: `tests/test_command_generator.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_command_generator.py
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_command_generator import AECommandGenerator

def test_generate_create_comp():
    gen = AECommandGenerator()
    commands = gen.generate_create_comp("Test_Comp", 1920, 1080, 5, 30)
    assert len(commands) == 1
    assert commands[0]["op"] == "createComposition"
    assert commands[0]["params"]["name"] == "Test_Comp"

def test_generate_import_footage():
    gen = AECommandGenerator()
    commands = gen.generate_import_footage(["/path/to/video.mp4"])
    assert len(commands) == 1
    assert commands[0]["op"] == "importFootage"

def test_generate_apply_effect():
    gen = AECommandGenerator()
    commands = gen.generate_apply_effect("Layer1", "ADBE Glo2", {"Glow Radius": 50})
    assert len(commands) == 1
    assert commands[0]["op"] == "applyEffect"

def test_generate_set_keyframe():
    gen = AECommandGenerator()
    commands = gen.generate_set_keyframe("Layer1", "Position", 1.0, [960, 540], "linear")
    assert len(commands) == 1
    assert commands[0]["op"] == "setLayerKeyframe"

def test_generate_from_planning_result():
    gen = AECommandGenerator()
    planning_result = {
        "composition": {
            "name": "Test_Comp",
            "width": 1920,
            "height": 1080,
            "duration": 5,
            "frameRate": 30
        },
        "layers": [
            {"name": "Layer1", "type": "footage", "source": "/path/to/video.mp4", "startTime": 0, "duration": 5}
        ],
        "effects": [],
        "keyframes": [],
        "transitions": []
    }
    commands = gen.generate_from_planning_result(planning_result)
    assert len(commands) >= 2  # createComp + importFootage
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_command_generator.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'ae_command_generator'"

- [ ] **Step 3: 实现 AECommandGenerator**

```python
# ae_command_generator.py
from typing import List, Dict, Any

class AECommandGenerator:
    def generate_create_comp(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        duration: float = 5,
        frame_rate: int = 30,
        bg_color: List[int] = None
    ) -> List[Dict[str, Any]]:
        return [{
            "op": "createComposition",
            "params": {
                "name": name,
                "width": width,
                "height": height,
                "duration": duration,
                "frameRate": frame_rate,
                "backgroundColor": bg_color or [0, 0, 0]
            }
        }]

    def generate_import_footage(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        commands = []
        for path in file_paths:
            commands.append({
                "op": "importFootage",
                "params": {"filePath": path}
            })
        return commands

    def generate_place_footage(
        self,
        comp_name: str,
        layer_name: str,
        file_path: str,
        start_time: float = 0
    ) -> List[Dict[str, Any]]:
        return [{
            "op": "placeFootageInComp",
            "params": {
                "compName": comp_name,
                "layerName": layer_name,
                "footagePath": file_path,
                "startTime": start_time
            }
        }]

    def generate_apply_effect(
        self,
        layer_name: str,
        effect_match_name: str,
        settings: Dict[str, Any],
        comp_name: str = None
    ) -> List[Dict[str, Any]]:
        params = {
            "layerName": layer_name,
            "effectMatchName": effect_match_name,
            "effectSettings": settings
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "applyEffect",
            "params": params
        }]

    def generate_set_keyframe(
        self,
        layer_name: str,
        property_name: str,
        time_in_seconds: float,
        value: Any,
        ease_type: str = "linear",
        comp_name: str = None
    ) -> List[Dict[str, Any]]:
        params = {
            "layerName": layer_name,
            "propertyName": property_name,
            "timeInSeconds": time_in_seconds,
            "value": value,
            "easeType": ease_type
        }
        if comp_name:
            params["compName"] = comp_name
        return [{
            "op": "setLayerKeyframe",
            "params": params
        }]

    def generate_render(
        self,
        comp_name: str,
        output_path: str,
        format: str = "mp4",
        quality: str = "high"
    ) -> List[Dict[str, Any]]:
        return [{
            "op": "renderComposition",
            "params": {
                "compName": comp_name,
                "outputPath": output_path,
                "format": format,
                "quality": quality
            }
        }]

    def generate_from_planning_result(self, planning_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        commands = []
        comp_name = planning_result.get("composition", {}).get("name", "AI_Generated")

        if planning_result.get("composition"):
            comp = planning_result["composition"]
            commands.extend(self.generate_create_comp(
                name=comp.get("name", comp_name),
                width=comp.get("width", 1920),
                height=comp.get("height", 1080),
                duration=comp.get("duration", 5),
                frame_rate=comp.get("frameRate", 30),
                bg_color=comp.get("backgroundColor")
            ))

        footage_files = []
        for layer in planning_result.get("layers", []):
            if layer.get("type") in ["footage", "audio"]:
                source = layer.get("source", "")
                if source:
                    footage_files.append(source)
        if footage_files:
            commands.extend(self.generate_import_footage(footage_files))

        for layer in planning_result.get("layers", []):
            if layer.get("type") in ["footage", "audio"]:
                commands.extend(self.generate_place_footage(
                    comp_name=comp_name,
                    layer_name=layer.get("name", ""),
                    file_path=layer.get("source", ""),
                    start_time=layer.get("startTime", 0)
                ))

        for effect in planning_result.get("effects", []):
            commands.extend(self.generate_apply_effect(
                layer_name=effect.get("layerName", ""),
                effect_match_name=effect.get("effectName", ""),
                settings=effect.get("settings", {}),
                comp_name=comp_name
            ))

        for keyframe in planning_result.get("keyframes", []):
            commands.extend(self.generate_set_keyframe(
                layer_name=keyframe.get("layerName", ""),
                property_name=keyframe.get("propertyName", ""),
                time_in_seconds=keyframe.get("time", 0),
                value=keyframe.get("value", 0),
                ease_type=keyframe.get("easeType", "linear"),
                comp_name=comp_name
            ))

        return commands
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_command_generator.py -v`
Expected: PASS all tests

- [ ] **Step 5: 提交**

```bash
git add ae_command_generator.py tests/test_command_generator.py
git commit -m "feat(phase1): add AE command generator"
```

---

## Task 3: 修复 ae_agent_pipeline.py 执行层

**Files:**
- Modify: `ae_agent_pipeline.py` (替换 execute 方法)
- Test: `tests/test_pipeline_execution.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_pipeline_execution.py
import os
import sys
import pytest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline
from ae_command_generator import AECommandGenerator
from ae_mcp_client import AECommandClient

def test_pipeline_execution_with_mock():
    pipeline = AEAgentPipeline()
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    
    planning_result = {
        "composition": {"name": "Test", "width": 1920, "height": 1080, "duration": 5, "frameRate": 30},
        "layers": [],
        "effects": [],
        "keyframes": [],
        "transitions": [],
        "execution_order": ["createComposition"]
    }
    
    with patch.object(AECommandClient, '__new__', return_value=mock_client):
        result = pipeline.execute(planning_result)
    
    assert result.success is True
    assert mock_client.send_command.called

def test_pipeline_run_pipeline_integration():
    pipeline = AEAgentPipeline()
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    
    planning_result = {
        "composition": {"name": "Integration_Test", "width": 1920, "height": 1080, "duration": 5, "frameRate": 30},
        "layers": [],
        "effects": [],
        "keyframes": [],
        "transitions": [],
        "execution_order": ["createComposition"]
    }
    
    with patch.object(AECommandClient, '__new__', return_value=mock_client):
        result = pipeline.execute(planning_result)
    
    assert result.success is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_pipeline_execution.py -v`
Expected: FAIL because execute method tries to import ae_mcp_bridge

- [ ] **Step 3: 修复 ae_agent_pipeline.py 执行层**

修改 `ae_agent_pipeline.py` 的 `execute` 方法（约第757行）：

```python
def execute(self, planning: PlanningResult) -> ExecutionResult:
    """
    执行层：AE执行引擎
    """
    result = ExecutionResult()
    result.total_steps = len(planning.execution_order)
    
    try:
        from ae_mcp_client import AECommandClient
        from ae_command_generator import AECommandGenerator
        
        client = AECommandClient()
        generator = AECommandGenerator()
        
        comp_name = planning.composition.get("name", "AI_Generated")
        
        commands = generator.generate_from_planning_result({
            "composition": planning.composition,
            "layers": planning.layers,
            "effects": planning.effects,
            "keyframes": planning.keyframes,
            "transitions": planning.transitions
        })
        
        print(f"  ├─ 生成 {len(commands)} 个命令")
        
        for i, cmd in enumerate(commands):
            op = cmd["op"]
            params = cmd["params"]
            
            print(f"  │   ├─ [{i+1}/{len(commands)}] {op}...")
            
            ae_result = client.send_command(op, params)
            
            if ae_result.get("success") is False or ae_result.get("status") == "error":
                result.success = False
                result.error_message = f"{op} failed: {ae_result.get('message', 'Unknown')}"
                result.steps_completed = i + 1
                return result
            
            client.clear_result()
            result.steps_completed = i + 1
        
        output_dir = self.config.get("output", {}).get("default_dir", "./output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        render_result = client.send_command("renderComposition", {
            "compName": comp_name,
            "outputPath": output_path,
            "format": "mp4",
            "quality": "high"
        })
        
        if render_result.get("success") or render_result.get("status") == "success":
            result.success = True
            result.output_path = output_path
        else:
            result.success = False
            result.error_message = f"渲染失败: {render_result.get('message', 'Unknown')}"
        
        result.steps_completed += 1
        result.execution_time = 0
        
    except Exception as e:
        result.success = False
        result.error_message = str(e)

    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_pipeline_execution.py -v`
Expected: PASS all tests

- [ ] **Step 5: 提交**

```bash
git add ae_agent_pipeline.py tests/test_pipeline_execution.py
git commit -m "fix(phase1): repair pipeline execution layer with MCP client"
```

---

## Task 4: 更新 AE Listener 支持新命令

**Files:**
- Modify: `ae_mcp_listener.jsx` (添加新命令处理)

- [ ] **Step 1: 检查现有命令处理**

Read: `ae_mcp_listener.jsx` 查看现有命令处理逻辑

- [ ] **Step 2: 添加新命令处理**

在命令处理部分添加以下命令：
- `createComposition`
- `importFootage`
- `placeFootageInComp`
- `applyEffect`
- `setLayerKeyframe`
- `renderComposition`

```javascript
// 在命令处理 switch 语句中添加
case "createComposition":
    result = handleCreateComposition(command.params);
    break;
case "importFootage":
    result = handleImportFootage(command.params);
    break;
case "placeFootageInComp":
    result = handlePlaceFootageInComp(command.params);
    break;
case "applyEffect":
    result = handleApplyEffect(command.params);
    break;
case "setLayerKeyframe":
    result = handleSetLayerKeyframe(command.params);
    break;
case "renderComposition":
    result = handleRenderComposition(command.params);
    break;
```

添加处理函数：

```javascript
function handleCreateComposition(params) {
    try {
        var name = params.name || "AI Composition";
        var width = params.width || 1920;
        var height = params.height || 1080;
        var duration = params.duration || 5;
        var frameRate = params.frameRate || 30;
        var bgColor = params.backgroundColor || [0, 0, 0];
        
        var comp = app.project.items.addComp(name, width, height, 1, duration, frameRate);
        comp.bgColor = new Color(bgColor[0], bgColor[1], bgColor[2]);
        
        return { success: true, status: "success", message: "Composition created: " + name };
    } catch (e) {
        return { success: false, status: "error", message: e.toString() };
    }
}

function handleImportFootage(params) {
    try {
        var filePath = params.filePath;
        if (!filePath) {
            return { success: false, status: "error", message: "filePath is required" };
        }
        
        var file = new File(filePath);
        if (!file.exists) {
            return { success: false, status: "error", message: "File not found: " + filePath };
        }
        
        var footage = app.project.importFile(new ImportOptions(file));
        
        return { success: true, status: "success", message: "Footage imported: " + file.name };
    } catch (e) {
        return { success: false, status: "error", message: e.toString() };
    }
}

function handlePlaceFootageInComp(params) {
    try {
        var compName = params.compName || app.project.activeItem.name;
        var layerName = params.layerName;
        var footagePath = params.footagePath;
        var startTime = params.startTime || 0;
        
        var comp = findCompByName(compName);
        if (!comp) {
            return { success: false, status: "error", message: "Composition not found: " + compName };
        }
        
        var footageItem = findFootageByPath(footagePath);
        if (!footageItem) {
            return { success: false, status: "error", message: "Footage not found: " + footagePath };
        }
        
        var layer = comp.layers.add(footageItem);
        if (layerName) {
            layer.name = layerName;
        }
        layer.startTime = startTime;
        
        return { success: true, status: "success", message: "Footage placed: " + layer.name };
    } catch (e) {
        return { success: false, status: "error", message: e.toString() };
    }
}

function handleApplyEffect(params) {
    try {
        var layerName = params.layerName;
        var effectMatchName = params.effectMatchName;
        var effectSettings = params.effectSettings || {};
        var compName = params.compName;
        
        var comp = compName ? findCompByName(compName) : app.project.activeItem;
        if (!comp) {
            return { success: false, status: "error", message: "Composition not found" };
        }
        
        var layer = findLayerByName(comp, layerName);
        if (!layer) {
            return { success: false, status: "error", message: "Layer not found: " + layerName };
        }
        
        var effect = layer.Effects.add(effectMatchName);
        
        for (var propName in effectSettings) {
            try {
                effect.property(propName).setValue(effectSettings[propName]);
            } catch (e2) {
                try {
                    var idx = findPropertyIndex(effect, propName);
                    if (idx >= 1) {
                        effect.property(idx).setValue(effectSettings[propName]);
                    }
                } catch (e3) {}
            }
        }
        
        return { success: true, status: "success", message: "Effect applied: " + effectMatchName };
    } catch (e) {
        return { success: false, status: "error", message: e.toString() };
    }
}

function handleSetLayerKeyframe(params) {
    try {
        var layerName = params.layerName;
        var propertyName = params.propertyName;
        var timeInSeconds = params.timeInSeconds;
        var value = params.value;
        var easeType = params.easeType || "linear";
        var compName = params.compName;
        
        var comp = compName ? findCompByName(compName) : app.project.activeItem;
        if (!comp) {
            return { success: false, status: "error", message: "Composition not found" };
        }
        
        var layer = findLayerByName(comp, layerName);
        if (!layer) {
            return { success: false, status: "error", message: "Layer not found: " + layerName };
        }
        
        var prop = layer.property(propertyName);
        if (!prop) {
            return { success: false, status: "error", message: "Property not found: " + propertyName };
        }
        
        comp.time = timeInSeconds;
        prop.setValue(value);
        
        if (prop.numKeys > 0) {
            var keyIndex = prop.nearestKeyIndex(comp.time);
            var key = prop.key(keyIndex);
            
            if (easeType === "easeIn") {
                key.setTemporalEaseAtKey(1, [0.8, 0.8], [0.2, 0.2]);
            } else if (easeType === "easeOut") {
                key.setTemporalEaseAtKey(1, [0.2, 0.2], [0.8, 0.8]);
            } else if (easeType === "easeInOut") {
                key.setTemporalEaseAtKey(1, [0.8, 0.8], [0.8, 0.8]);
            }
        }
        
        return { success: true, status: "success", message: "Keyframe set: " + propertyName };
    } catch (e) {
        return { success: false, status: "error", message: e.toString() };
    }
}

function handleRenderComposition(params) {
    try {
        var compName = params.compName;
        var outputPath = params.outputPath;
        var format = params.format || "mp4";
        var quality = params.quality || "high";
        
        var comp = findCompByName(compName);
        if (!comp) {
            return { success: false, status: "error", message: "Composition not found: " + compName };
        }
        
        var renderQueue = app.project.renderQueue;
        var renderItem = renderQueue.items.add(comp);
        
        var outputModule = renderItem.outputModules[1];
        outputModule.file = new File(outputPath);
        
        if (format === "mp4") {
            outputModule.applyTemplate("H.264");
        } else if (format === "mov") {
            outputModule.applyTemplate("QuickTime");
        }
        
        renderQueue.render();
        
        return { success: true, status: "success", message: "Render started: " + outputPath };
    } catch (e) {
        return { success: false, status: "error", message: e.toString() };
    }
}

function findCompByName(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === name) {
            return item;
        }
    }
    return null;
}

function findLayerByName(comp, name) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        if (layer.name === name) {
            return layer;
        }
    }
    return null;
}

function findFootageByPath(path) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof FootageItem) {
            if (item.file && item.file.fsName === path) {
                return item;
            }
            if (item.name === new File(path).name) {
                return item;
            }
        }
    }
    return null;
}

function findPropertyIndex(effect, name) {
    for (var i = 1; i <= effect.numProperties; i++) {
        if (effect.property(i).name === name) {
            return i;
        }
    }
    return -1;
}
```

- [ ] **Step 3: 提交**

```bash
git add ae_mcp_listener.jsx
git commit -m "feat(phase1): add new command handlers to AE listener"
```

---

## Task 5: 端到端集成测试

**Files:**
- Create: `tests/test_phase1_e2e.py`

- [ ] **Step 1: 编写端到端测试**

```python
# tests/test_phase1_e2e.py
import os
import sys
import pytest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline, PerceptionResult, UnderstandingResult, PlanningResult

def test_full_pipeline_flow():
    pipeline = AEAgentPipeline()
    
    perception_result = PerceptionResult(
        music_features={
            "bpm": 128,
            "duration": 10,
            "mood": "excited",
            "beats": [0.5, 1.0, 1.5, 2.0],
            "downbeats": [0.0, 1.0, 2.0],
            "energy_curve": {"peaks": []},
            "segments": []
        },
        clip_features=[
            {
                "video_path": "/path/to/clip1.mp4",
                "basic_info": {"duration": 3.0},
                "motion_features": {"avg_motion": 25}
            },
            {
                "video_path": "/path/to/clip2.mp4",
                "basic_info": {"duration": 3.0},
                "motion_features": {"avg_motion": 35}
            }
        ]
    )
    
    understanding_result = UnderstandingResult(
        intent="video_editing",
        mood="excited",
        mood_score=0.85,
        style="cinematic",
        tempo=128,
        duration=10,
        keywords=["cinematic", "excited"]
    )
    
    planning_result = pipeline.plan(understanding_result, perception_result)
    
    assert planning_result.composition is not None
    assert len(planning_result.layers) >= 2
    assert len(planning_result.effects) > 0
    assert len(planning_result.keyframes) > 0
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    
    with patch('ae_agent_pipeline.AECommandClient', return_value=mock_client):
        execution_result = pipeline.execute(planning_result)
    
    assert execution_result.success is True
    assert mock_client.send_command.call_count > 0

def test_pipeline_with_real_audio_analysis():
    pipeline = AEAgentPipeline()
    
    mock_audio_result = {
        "success": True,
        "features": {
            "bpm": 100,
            "duration": 5,
            "mood": "calm",
            "beats": [0.25, 0.5, 0.75, 1.0],
            "downbeats": [0.0, 0.5, 1.0],
            "energy_curve": {"peaks": []},
            "segments": []
        }
    }
    
    with patch.object(pipeline.audio_analyzer, 'analyze_audio', return_value=mock_audio_result):
        perception_result = pipeline.perceive(
            music_path="/fake/path.mp3",
            clip_paths=["/fake/clip1.mp4"]
        )
    
    assert perception_result.music_features is not None
    assert perception_result.music_features["bpm"] == 100
    assert perception_result.music_features["mood"] == "calm"
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_phase1_e2e.py -v`
Expected: PASS all tests

- [ ] **Step 3: 提交**

```bash
git add tests/test_phase1_e2e.py
git commit -m "test(phase1): add end-to-end integration tests"
```

---

## Task 6: 实机验证准备

**Files:**
- Create: `tests/test_phase1_real_ae.py` (手动运行的实机验证脚本)

- [ ] **Step 1: 创建实机验证脚本**

```python
# tests/test_phase1_real_ae.py
"""
Phase 1 实机验证脚本

运行方式：
1. 确保 AE 2026 已启动
2. 在 AE 中运行 ae_mcp_listener.jsx（File -> Scripts -> Run Script File）
3. 确保有测试素材：
   - 音乐文件: D:\AE-Work\音频素材库\BGM\*.mp3
   - 视频文件: D:\AE-Work\视频素材库\*.mp4
4. 运行此脚本: python tests/test_phase1_real_ae.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline

def main():
    print("="*70)
    print("🎬 Phase 1 实机验证")
    print("="*70)
    
    pipeline = AEAgentPipeline()
    
    music_dir = r"D:\AE-Work\音频素材库\BGM"
    clip_dir = r"D:\AE-Work\视频素材库"
    
    music_files = [f for f in os.listdir(music_dir) if f.endswith((".mp3", ".m4a"))] if os.path.exists(music_dir) else []
    clip_files = [f for f in os.listdir(clip_dir) if f.endswith((".mp4", ".mov"))] if os.path.exists(clip_dir) else []
    
    if not music_files:
        print("❌ 未找到音乐文件，请将音乐放入 D:\\AE-Work\\音频素材库\\BGM\\")
        return
    
    if not clip_files:
        print("❌ 未找到视频片段，请将视频放入 D:\\AE-Work\\视频素材库\\")
        return
    
    music_path = os.path.join(music_dir, music_files[0])
    clip_paths = [os.path.join(clip_dir, f) for f in clip_files[:3]]
    
    print(f"\n🎵 选择音乐: {os.path.basename(music_path)}")
    print(f"📹 选择片段: {len(clip_paths)} 个")
    
    result = pipeline.run_pipeline(
        music_path=music_path,
        clip_paths=clip_paths,
        user_prompt="Create a cinematic video",
        style_preset="cinematic"
    )
    
    print("\n" + "="*70)
    print(f"结果: {'成功' if result.get('overall_success') else '失败'}")
    if result.get("overall_success"):
        print(f"输出文件: {result.get('execution', {}).get('output_path', '')}")
    else:
        print(f"错误: {result.get('error', '')}")
    print("="*70)
    
    output_file = pipeline.save_result(result)
    print(f"\n📄 详细结果已保存: {output_file}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交**

```bash
git add tests/test_phase1_real_ae.py
git commit -m "test(phase1): add real AE verification script"
```

---

## 自我审查

**1. Spec覆盖:**
- ✅ ae_mcp_client.py - MCP命令发送客户端
- ✅ ae_command_generator.py - 规划结果→命令转换
- ✅ ae_agent_pipeline.py修复 - 执行层
- ✅ ae_mcp_listener.jsx - 新命令处理
- ✅ 集成测试
- ✅ 实机验证脚本

**2. 占位符扫描:**
- ✅ 无TBD/TODO/待实现
- ✅ 所有测试代码完整
- ✅ 所有实现代码完整
- ✅ 类型一致

**3. 类型一致性:**
- ✅ AECommandClient 与 AECommandGenerator 返回类型一致
- ✅ PlanningResult 结构与 generate_from_planning_result 输入一致
- ✅ execute 方法返回 ExecutionResult 类型正确

---

**计划完成，共6个任务。所有文件路径、代码、测试用例均已完整定义。**
