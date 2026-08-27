#!/usr/bin/env python3
"""
Silhouette fx API 模拟器 v2.0
基于 Silhouette 2026.0.2 真实 API 验证结果更新。

真实 API 关键发现（2026-07-10 验证）：
- 节点创建: Node("RotoNode") 直接用类型名
- 节点连接: src.outputs[0].connect(dst.inputs[n]) （没有 Pipe 类）
- RotoNode 端口: 5 inputs(obey_matte,foreground,background,occlusion,data), 5 outputs(output,colorComp,composite,channels,objects)
- SourceNode 端口: 0 inputs, 1 output
- OutputNode 端口: 1 input, 0 outputs
- 属性: node.properties (dict), node.property(name) 获取 Property 对象
- Property: Property(name, type_str) 创建, setValue(value, frame) 设置
- 版本: version 是 float 变量，不是函数
- Action: 脚本通过 Action 类注册到菜单
"""

import os
import time
import json
from typing import Any, Dict, List, Optional


# ============================================================
# 基础类型
# ============================================================

class Point:
    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"


class Size:
    def __init__(self, width: float = 0.0, height: float = 0.0):
        self.width = width
        self.height = height
    
    def __repr__(self):
        return f"Size({self.width}, {self.height})"


class Recti:
    def __init__(self, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
    
    @property
    def width(self) -> int:
        return self.right - self.left
    
    @property
    def height(self) -> int:
        return self.bottom - self.top
    
    def __repr__(self):
        return f"Recti({self.left}, {self.top}, {self.right}, {self.bottom})"


class Property:
    def __init__(self, name: str, type_str: str = "number"):
        self.name = name
        self._type = type_str
        self._values: Dict[int, Any] = {}
        self._default: Any = self._get_default(type_str)
    
    def _get_default(self, type_str: str) -> Any:
        defaults = {
            "number": 0,
            "float": 0.0,
            "int": 0,
            "bool": False,
            "string": "",
            "point": Point(),
            "size": Size(),
            "rect": Recti(),
        }
        return defaults.get(type_str, 0)
    
    def getValue(self, frame: int = 0) -> Any:
        return self._values.get(frame, self._default)
    
    def setValue(self, value: Any, frame: int = 0) -> None:
        self._values[frame] = value
    
    @property
    def value(self) -> Any:
        return self.getValue(0)
    
    @value.setter
    def value(self, v: Any):
        self.setValue(v, 0)
    
    def is_default(self) -> bool:
        return len(self._values) == 0
    
    def __repr__(self):
        return f"<Property '{self.name}'>"


# ============================================================
# 端口 (Port)
# ============================================================

class Port:
    def __init__(self, name: str, direction: str = "input"):
        self.name = name
        self.direction = direction  # "input" or "output"
        self._source: Optional['Port'] = None
        self._targets: List['Port'] = []
        self._node: Optional['Node'] = None
    
    @property
    def source(self) -> Optional['Port']:
        return self._source
    
    @source.setter
    def source(self, src: Optional['Port']):
        raise AttributeError("attribute 'source' of 'Port' objects is not writable")
    
    @property
    def node(self) -> Optional['Node']:
        return self._node
    
    def connect(self, target_port: 'Port') -> None:
        if target_port.direction != "input":
            raise ValueError("Can only connect to input ports")
        target_port._source = self
        if target_port not in self._targets:
            self._targets.append(target_port)
    
    def disconnect(self, target_port: 'Port') -> None:
        if target_port in self._targets:
            self._targets.remove(target_port)
        if target_port._source is self:
            target_port._source = None
    
    def __repr__(self):
        return f"<Port '{self.name}' ({self.direction})>"


# ============================================================
# 节点 (Node)
# ============================================================

_NODE_PORT_CONFIGS = {
    "SourceNode": {
        "inputs": [],
        "outputs": ["output"],
    },
    "OutputNode": {
        "inputs": ["input"],
        "outputs": [],
    },
    "RotoNode": {
        "inputs": ["obey_matte", "foreground", "background", "occlusion", "data"],
        "outputs": ["output", "colorComp", "composite", "channels", "objects"],
    },
    "TrackerNode": {
        "inputs": ["input", "mask"],
        "outputs": ["output", "data"],
    },
    "PaintNode": {
        "inputs": ["input", "mask", "clone"],
        "outputs": ["output"],
    },
    "CompositeNode": {
        "inputs": ["fg", "bg", "matte"],
        "outputs": ["output"],
    },
}

_DEFAULT_PROPS = {
    "SourceNode": ["note", "node.format", "node.dod", "gpu.enable", "markers",
                   "preserveAlpha", "alpha", "alpha.type", "alpha.fill",
                   "stream", "stream.primary", "stream.secondary", "stream.depth",
                   "offset", "extend", "center"],
    "RotoNode": ["note", "obey_matte", "obey_matte.obey", "obey_matte.invert",
                 "obey_matte.opacity", "obey_matte.channel", "node.format",
                 "node.dod", "gpu.enable", "markers", "cache.enable",
                 "objects", "alpha", "alpha.preserve", "alpha.invert",
                 "alpha.blur", "color", "color.enable", "color.outline",
                 "color.opacity", "motionBlur", "motionBlur.enable",
                 "motionBlur.shutterAngle", "motionBlur.shutterPhase",
                 "motionBlur.samples", "antialias"],
}

class Node:
    def __init__(self, type_str: str = "Node"):
        self.type = type_str
        self.label = type_str.replace("Node", "") if type_str.endswith("Node") else type_str
        self.inputs: List[Port] = []
        self.outputs: List[Port] = []
        self._properties: Dict[str, Property] = {}
        self._parent = None
        
        config = _NODE_PORT_CONFIGS.get(type_str, {
            "inputs": ["input"],
            "outputs": ["output"],
        })
        
        for name in config["inputs"]:
            port = Port(name, "input")
            port._node = self
            self.inputs.append(port)
        
        for name in config["outputs"]:
            port = Port(name, "output")
            port._node = self
            self.outputs.append(port)
        
        prop_names = _DEFAULT_PROPS.get(type_str, ["note", "node.format", "node.dod", "gpu.enable", "markers"])
        for pname in prop_names:
            self._properties[pname] = Property(pname, "number")
    
    @property
    def properties(self):
        return self._properties
    
    @property
    def parent(self):
        return self._parent
    
    def property(self, name):
        return self._properties.get(name)
    
    def addProperty(self, prop):
        self._properties[prop.name] = prop
    
    def __repr__(self):
        return f"{self.type}: {self.label}"


# ============================================================
# Object 基类
# ============================================================

class Object:
    def __init__(self, type_str: str = "Object", label: str = ""):
        self.type = type_str
        self.label = label or type_str
        self._properties: Dict[str, Property] = {}
        self._parent = None
    
    @property
    def properties(self):
        return self._properties
    
    @property
    def parent(self):
        return self._parent
    
    def property(self, name):
        return self._properties.get(name)
    
    def __repr__(self):
        return f"Object({self.type}, {self.label})"


def createObject(type_str: str) -> Object:
    return Object(type_str)


# ============================================================
# Session / Project
# ============================================================

class Session(Object):
    def __init__(self, label: str = "Session"):
        super().__init__("Session", label)
        self.width: int = 1920
        self.height: int = 1080
        self.frameRate: float = 30.0
        self._nodes: List[Node] = []
    
    def addNode(self, node: Node) -> None:
        if node not in self._nodes:
            self._nodes.append(node)
            node._parent = self
    
    def removeNode(self, node: Node) -> None:
        if node in self._nodes:
            self._nodes.remove(node)
            node._parent = None
    
    @property
    def nodes(self) -> List[Node]:
        return list(self._nodes)
    
    def __repr__(self):
        return f"Session('{self.label}')"


class Project(Object):
    def __init__(self):
        super().__init__("Project", "Project")
        self._items: List[Object] = []
        self._sessions: List[Session] = []
    
    def addItem(self, item: Object) -> None:
        self._items.append(item)
        item._parent = self
        if isinstance(item, Session):
            self._sessions.append(item)
    
    @property
    def sessions(self) -> List[Session]:
        return list(self._sessions)
    
    @property
    def items(self) -> List[Object]:
        return list(self._items)
    
    def __repr__(self):
        return "Project:"


# ============================================================
# 全局函数和变量
# ============================================================

version = 2026.0
versionString = "2026.0.2"
versionMajor = 2026
versionMinor = 0
buildNumber = 1234

_active_project: Optional[Project] = None
_active_session: Optional[Session] = None


def activeProject() -> Optional[Project]:
    return _active_project


def activeSession() -> Optional[Session]:
    return _active_session


def activate(item: Object) -> None:
    global _active_project, _active_session
    if isinstance(item, Project):
        _active_project = item
    elif isinstance(item, Session):
        _active_session = item


def addNode(node: Node, session: Optional[Session] = None) -> Node:
    s = session or _active_session
    if s:
        s.addNode(node)
    return node


def getNodes() -> List[str]:
    return list(_NODE_PORT_CONFIGS.keys())


def getNodeInfo(node_type: str) -> Dict[str, Any]:
    config = _NODE_PORT_CONFIGS.get(node_type, {"inputs": [], "outputs": []})
    return {
        "type": node_type,
        "inputs": config["inputs"],
        "outputs": config["outputs"],
    }


# ============================================================
# Action 基类
# ============================================================

class Action:
    def __init__(self, menu_path: str):
        self.menu_path = menu_path
    
    def execute(self):
        pass
    
    def available(self):
        return True


_actions: List[Action] = []


def addAction(action: Action) -> None:
    _actions.append(action)


def getActions() -> List[Action]:
    return list(_actions)


# ============================================================
# 辅助：打印所有可用符号
# ============================================================

def list_available() -> List[str]:
    symbols = []
    for name in globals():
        if not name.startswith('_'):
            symbols.append(name)
    return sorted(symbols)
