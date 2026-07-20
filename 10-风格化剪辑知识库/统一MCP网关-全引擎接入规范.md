# 统一MCP网关 - 全引擎接入规范

---

## 文档信息

| 项目 | 内容 |
|------|------|
| **协议版本** | MCP 2025-06-18 |
| **网关版本** | v2.0 全引擎版 |
| **接入引擎数** | 20+ |
| **架构** | 统一MCP网关 + 引擎适配器 + 资源池管理 |

---

## 一、MCP网关架构设计

### 1.1 整体架构

```
┌───────────────────────────────────────────────────────────┐
│                    上层应用 / AI规划层                      │
│              (LangChain / LlamaIndex / LLM)                │
└─────────────────────────────┬─────────────────────────────┘
                              │ MCP Client
                              ▼
┌───────────────────────────────────────────────────────────┐
│                    统一 MCP 网关                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  MCP Server (Python MCP SDK)                        │  │
│  │  - 工具注册/发现                                     │  │
│  │  - 请求路由分发                                      │  │
│  │  - 参数校验                                          │  │
│  │  - 错误处理                                          │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                         │                                  │
│  ┌──────────────────────▼──────────────────────────────┐  │
│  │  引擎适配器层 (Engine Adapters)                      │  │
│  │                                                      │  │
│  │  Adobe适配器    Silhouette    Blender适配器          │  │
│  │  (adobe-mcp)   适配器        (blender-mcp)          │  │
│  │                                                      │  │
│  │  Resolve适配器  开源AI引擎    渲染输出适配器          │  │
│  │  (dvr-mcp)     适配器         (render-mcp)           │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                         │                                  │
│  ┌──────────────────────▼──────────────────────────────┐  │
│  │  资源池管理层 (Engine Pool Manager)                   │  │
│  │  - 引擎实例池管理                                     │  │
│  │  - 并发控制 / 排队                                    │  │
│  │  - 健康检查 / 自动重启                                │  │
│  │  - 许可证管理                                         │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                         │                                  │
└─────────────────────────┼──────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │ AE / PS /│      │ Silhouette│      │ Blender │
   │ PR / AI  │      │  进程     │      │  进程   │
   │  进程    │      └─────────┘      └─────────┘
   └─────────┘
        ▲
   ┌────┴─────┐
   │  开源工具 │  ←  GPU推理池
   │  (进程)  │     (FunASR / YOLO / SAM2等)
   └──────────┘
```

### 1.2 引擎接入清单

| 引擎分类 | 引擎名称 | 接入方式 | MCP工具数量 | 优先级 |
|---------|---------|---------|------------|--------|
| **Adobe全家桶** | After Effects | COM+ExtendScript | 20+ | P0 |
| | Photoshop | COM+JavaScript | 15+ | P1 |
| | Premiere Pro | CEP/UXP | 12+ | P1 |
| | Illustrator | JavaScript | 10+ | P2 |
| | Media Encoder | Watch Folder | 5+ | P1 |
| **专业软件** | Silhouette 2026 | 内置fx Python API | 15+ | P0 |
| | DaVinci Resolve | dvr Python库 | 12+ | P1 |
| | Topaz Video AI | CLI | 8+ | P0 |
| | Blender | bpy Python API | 20+ | P0 |
| **AI推理引擎** | FunASR | Python推理 | 5+ | P0 |
| | YOLO-World | Python推理 | 6+ | P0 |
| | RVM | Python推理 | 4+ | P0 |
| | SAM2Matting | Python推理 | 5+ | P1 |
| | MediaPipe | Python推理 | 8+ | P0 |
| | DWPose | Python推理 | 4+ | P1 |
| | InternVL2 | Python推理 | 4+ | P1 |
| | Stable Diffusion | WebUI API | 10+ | P1 |
| **渲染输出** | ffmpeg | CLI+ffmpeg-python | 15+ | P0 |
| | gifski | CLI | 3+ | P1 |
| | OpenCue | Python API | 8+ | P1 |
| **其他** | MediaInfo | Python绑定 | 5+ | P1 |

---

## 二、MCP工具规范

### 2.1 工具命名规范

```
{engine}_{action}_{object}
   │        │        │
   │        │        └─ 操作对象（composition, layer, effect等）
   │        └─────────── 动作（create, delete, modify, get, execute等）
   └──────────────────── 引擎前缀（ae, ps, silhouette, blender等）
```

**示例**：
- `ae_create_composition` - AE创建合成
- `ae_modify_layer_property` - AE修改图层属性
- `silhouette_create_roto_node` - Silhouette创建Roto节点
- `blender_render_scene` - Blender渲染场景
- `ffmpeg_transcode` - ffmpeg转码

### 2.2 工具输入输出规范

每个MCP工具遵循统一的输入输出格式：

```python
# 工具定义模板
{
    "name": "ae_modify_layer_property",
    "description": "修改AE合成中图层的属性",
    "inputSchema": {
        "type": "object",
        "properties": {
            "comp_name": {
                "type": "string",
                "description": "合成名称"
            },
            "layer_name": {
                "type": "string",
                "description": "图层名称"
            },
            "property_name": {
                "type": "string",
                "description": "属性路径，如'Position'或'Effects/MyEffect/Opacity'"
            },
            "value": {
                "type": ["number", "string", "array", "boolean"],
                "description": "属性值"
            },
            "frame": {
                "type": "number",
                "description": "关键帧时间（秒），不填则为当前时间"
            }
        },
        "required": ["comp_name", "layer_name", "property_name", "value"]
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "是否成功"
            },
            "message": {
                "type": "string",
                "description": "操作信息"
            },
            "data": {
                "type": "object",
                "description": "返回数据"
            }
        }
    }
}
```

### 2.3 错误码规范

| 错误码 | 含义 | 说明 |
|--------|------|------|
| `ENGINE_NOT_AVAILABLE` | 引擎不可用 | 软件未启动 / 未安装 / 无授权 |
| `ENGINE_TIMEOUT` | 引擎超时 | 操作超时，可能需要重试 |
| `COMP_NOT_FOUND` | 合成不存在 | 指定的合成名称不存在 |
| `LAYER_NOT_FOUND` | 图层不存在 | 指定的图层名称不存在 |
| `PROPERTY_NOT_FOUND` | 属性不存在 | 属性路径错误 |
| `INVALID_PARAMETER` | 参数错误 | 参数类型/值不正确 |
| `LICENSE_ERROR` | 授权错误 | 许可证不足或过期 |
| `RENDER_ERROR` | 渲染错误 | 渲染失败 |
| `FILE_NOT_FOUND` | 文件不存在 | 输入文件路径错误 |
| `UNKNOWN_ERROR` | 未知错误 | 未分类的错误 |

---

## 三、核心引擎MCP工具集

### 3.1 After Effects MCP工具

#### 项目管理

| 工具名 | 功能 |
|--------|------|
| `ae_open_project` | 打开AE工程文件 |
| `ae_new_project` | 新建AE工程 |
| `ae_save_project` | 保存AE工程 |
| `ae_close_project` | 关闭当前工程 |
| `ae_get_project_info` | 获取工程信息 |

#### 合成管理

| 工具名 | 功能 |
|--------|------|
| `ae_create_composition` | 创建新合成 |
| `ae_delete_composition` | 删除合成 |
| `ae_get_composition` | 获取合成信息 |
| `ae_list_compositions` | 列出所有合成 |
| `ae_render_composition` | 渲染合成 |

#### 图层管理

| 工具名 | 功能 |
|--------|------|
| `ae_add_layer` | 添加图层 |
| `ae_delete_layer` | 删除图层 |
| `ae_move_layer` | 移动图层顺序 |
| `ae_duplicate_layer` | 复制图层 |
| `ae_get_layer_info` | 获取图层信息 |
| `ae_list_layers` | 列出合成图层 |

#### 属性控制

| 工具名 | 功能 |
|--------|------|
| `ae_set_property` | 设置图层属性值 |
| `ae_get_property` | 获取图层属性值 |
| `ae_add_keyframe` | 添加关键帧 |
| `ae_remove_keyframe` | 删除关键帧 |
| `ae_set_expression` | 设置表达式 |

#### 效果管理

| 工具名 | 功能 |
|--------|------|
| `ae_add_effect` | 添加效果 |
| `ae_remove_effect` | 移除效果 |
| `ae_set_effect_param` | 设置效果参数 |
| `ae_get_effect_param` | 获取效果参数 |
| `ae_list_effects` | 列出图层效果 |

#### 渲染控制

| 工具名 | 功能 |
|--------|------|
| `ae_render_queue_add` | 添加到渲染队列 |
| `ae_render_queue_start` | 启动渲染队列 |
| `ae_render_queue_status` | 获取渲染队列状态 |
| `ae_render_to_file` | 直接渲染到文件 |
| `ae_aerender_cli` | 调用aerender CLI |

### 3.2 Silhouette MCP工具

#### 项目与会话

| 工具名 | 功能 |
|--------|------|
| `sil_create_project` | 创建项目 |
| `sil_open_project` | 打开项目 |
| `sil_add_source` | 添加素材源 |

#### 节点操作

| 工具名 | 功能 |
|--------|------|
| `sil_create_roto_node` | 创建Roto节点 |
| `sil_create_tracker_node` | 创建跟踪节点 |
| `sil_create_paint_node` | 创建Paint节点 |
| `sil_create_output_node` | 创建输出节点 |
| `sil_connect_nodes` | 连接节点 |
| `sil_list_nodes` | 列出所有节点 |

#### Roto操作

| 工具名 | 功能 |
|--------|------|
| `sil_import_matte` | 导入蒙版序列 |
| `sil_add_shape` | 添加形状 |
| `sil_modify_shape` | 修改形状 |
| `sil_simplify_shapes` | 简化形状 |

#### 跟踪操作

| 工具名 | 功能 |
|--------|------|
| `sil_add_tracker` | 添加跟踪点 |
| `sil_track_forward` | 向前跟踪 |
| `sil_track_backward` | 向后跟踪 |
| `sil_apply_track_to_shape` | 应用跟踪到形状 |

#### 输出操作

| 工具名 | 功能 |
|--------|------|
| `sil_set_output_format` | 设置输出格式 |
| `sil_render_output` | 渲染输出 |
| `sil_export_exr` | 导出EXR序列 |

### 3.3 Blender MCP工具

#### 场景管理

| 工具名 | 功能 |
|--------|------|
| `blender_new_scene` | 新建场景 |
| `blender_load_scene` | 加载场景文件 |
| `blender_save_scene` | 保存场景 |

#### 对象操作

| 工具名 | 功能 |
|--------|------|
| `blender_add_object` | 添加物体 |
| `blender_delete_object` | 删除物体 |
| `blender_modify_object` | 修改物体属性 |
| `blender_list_objects` | 列出物体 |

#### 材质与纹理

| 工具名 | 功能 |
|--------|------|
| `blender_create_material` | 创建材质 |
| `blender_assign_material` | 分配材质给物体 |
| `blender_set_texture` | 设置纹理贴图 |

#### 灯光与相机

| 工具名 | 功能 |
|--------|------|
| `blender_add_light` | 添加灯光 |
| `blender_add_camera` | 添加摄像机 |
| `blender_set_camera_position` | 设置摄像机位置 |
| `blender_track_camera` | 摄像机跟踪 |

#### 渲染

| 工具名 | 功能 |
|--------|------|
| `blender_render_still` | 渲染单帧 |
| `blender_render_animation` | 渲染动画 |
| `blender_set_render_settings` | 设置渲染参数 |

#### 舞台生成

| 工具名 | 功能 |
|--------|------|
| `blender_create_puppet_stage` | 创建木偶舞台 |
| `blender_create_base` | 创建底座 |
| `blender_create_curtains` | 创建幕布 |

### 3.4 其他核心工具

#### ffmpeg工具集

| 工具名 | 功能 |
|--------|------|
| `ffmpeg_transcode` | 转码 |
| `ffmpeg_extract_frames` | 抽帧 |
| `ffmpeg_concat` | 拼接 |
| `ffmpeg_add_subtitles` | 添加字幕 |
| `ffmpeg_probe` | 探测视频信息 |
| `ffmpeg_create_gif` | 生成GIF |

#### AI推理工具集

| 工具名 | 功能 |
|--------|------|
| `ai_asr_transcribe` | 语音识别（FunASR） |
| `ai_detect_objects` | 目标检测（YOLO-World） |
| `ai_pose_estimate` | 姿态估计（MediaPipe/DWPose） |
| `ai_face_mesh` | 面部关键点（FaceMesh） |
| `ai_video_matting` | 视频抠像（RVM/SAM2） |
| `ai_scene_detect` | 镜头分割（PySceneDetect+TransNetV2） |
| `ai_audio_analyze` | 音频分析（librosa） |
| `ai_generate_texture` | 纹理生成（Stable Diffusion） |

---

## 四、资源池管理

### 4.1 引擎池设计

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import threading
import time

class EngineStatus(str, Enum):
    IDLE = "idle"           # 空闲可用
    BUSY = "busy"           # 工作中
    STARTING = "starting"   # 启动中
    ERROR = "error"         # 错误状态
    OFFLINE = "offline"     # 离线

@dataclass
class EngineInstance:
    """引擎实例"""
    engine_id: str
    engine_type: str        # ae, silhouette, blender, etc.
    status: EngineStatus = EngineStatus.OFFLINE
    pid: Optional[int] = None
    last_heartbeat: float = 0
    current_task: Optional[str] = None
    error_message: str = ""
    config: dict = field(default_factory=dict)

class EnginePool:
    """引擎资源池"""
    
    def __init__(self):
        self.engines: Dict[str, List[EngineInstance]] = {}
        self._lock = threading.Lock()
        self._task_queue: dict = {}
    
    def register_engine(self, engine_type: str, instance: EngineInstance):
        """注册引擎实例"""
        with self._lock:
            if engine_type not in self.engines:
                self.engines[engine_type] = []
            self.engines[engine_type].append(instance)
    
    def acquire_engine(self, engine_type: str, 
                       timeout: float = 300.0) -> Optional[EngineInstance]:
        """
        获取一个可用的引擎实例
        如果没有可用的，等待直到超时
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._lock:
                instances = self.engines.get(engine_type, [])
                for inst in instances:
                    if inst.status == EngineStatus.IDLE:
                        inst.status = EngineStatus.BUSY
                        inst.last_heartbeat = time.time()
                        return inst
            
            time.sleep(0.5)
        
        return None
    
    def release_engine(self, engine_id: str, 
                       status: EngineStatus = EngineStatus.IDLE,
                       error: str = ""):
        """释放引擎实例"""
        with self._lock:
            for instances in self.engines.values():
                for inst in instances:
                    if inst.engine_id == engine_id:
                        inst.status = status
                        inst.current_task = None
                        inst.error_message = error
                        inst.last_heartbeat = time.time()
                        return
    
    def get_available_count(self, engine_type: str) -> int:
        """获取可用引擎数量"""
        with self._lock:
            instances = self.engines.get(engine_type, [])
            return sum(1 for i in instances if i.status == EngineStatus.IDLE)
    
    def health_check(self):
        """健康检查：清理超时的引擎"""
        with self._lock:
            for instances in self.engines.values():
                for inst in instances:
                    if inst.status == EngineStatus.BUSY:
                        # 超过2小时无心跳 → 标记错误
                        if time.time() - inst.last_heartbeat > 7200:
                            inst.status = EngineStatus.ERROR
                            inst.error_message = "heartbeat timeout"
```

### 4.2 并发控制策略

```
任务请求
    │
    ▼
┌──────────────────────┐
│  请求队列             │  ← 按优先级排序
│  (Priority Queue)    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  调度器               │
│  - FIFO + 优先级     │
│  - 公平性保证         │
│  - 死锁检测          │
└──────────┬───────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
GPU推理池     商业软件池
(FunASR等)    (AE/Sil/Blender)
    │             │
    └──────┬──────┘
           │
           ▼
      结果回调
```

---

## 五、MCP网关实现

### 5.1 基于Python MCP SDK的网关实现

```python
from mcp.server import Server
from mcp.types import Tool, TextContent
import json
import asyncio
from typing import List, Any

class MCPServer:
    """统一MCP服务器"""
    
    def __init__(self):
        self.server = Server("puppet-automation-mcp")
        self.engine_pool = EnginePool()
        self._register_tools()
    
    def _register_tools(self):
        """注册所有MCP工具"""
        
        # AE工具
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return self._get_all_tools()
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            result = await self._route_tool(name, arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    
    async def _route_tool(self, tool_name: str, 
                          arguments: dict) -> dict:
        """工具路由分发"""
        try:
            # 根据前缀确定引擎类型
            engine_type = self._get_engine_type(tool_name)
            
            # 从资源池获取引擎
            engine = self.engine_pool.acquire_engine(engine_type)
            if not engine:
                return {
                    "success": False,
                    "error": "ENGINE_NOT_AVAILABLE",
                    "message": f"No available {engine_type} engine"
                }
            
            try:
                # 执行具体操作
                result = await self._execute_tool(engine, tool_name, arguments)
                return result
            finally:
                # 释放引擎
                self.engine_pool.release_engine(engine.engine_id)
        
        except Exception as e:
            return {
                "success": False,
                "error": "UNKNOWN_ERROR",
                "message": str(e)
            }
    
    def _get_engine_type(self, tool_name: str) -> str:
        """根据工具名获取引擎类型"""
        prefix_map = {
            "ae_": "after_effects",
            "ps_": "photoshop",
            "pr_": "premiere",
            "ai_": "illustrator",
            "sil_": "silhouette",
            "blender_": "blender",
            "ffmpeg_": "ffmpeg",
            "ai_": "ai_inference",  # 注意：和illustrator区分
            "topaz_": "topaz",
            "davinci_": "davinci",
        }
        
        for prefix, engine_type in prefix_map.items():
            if tool_name.startswith(prefix):
                return engine_type
        
        return "unknown"
    
    async def _execute_tool(self, engine: EngineInstance,
                            tool_name: str,
                            arguments: dict) -> dict:
        """执行具体工具"""
        # 实际实现中，这里会调用具体的引擎适配器
        # 每个引擎类型有自己的适配器类
        
        engine_type = self._get_engine_type(tool_name)
        
        if engine_type == "after_effects":
            return await self._execute_ae_tool(engine, tool_name, arguments)
        elif engine_type == "silhouette":
            return await self._execute_sil_tool(engine, tool_name, arguments)
        elif engine_type == "blender":
            return await self._execute_blender_tool(engine, tool_name, arguments)
        elif engine_type == "ffmpeg":
            return await self._execute_ffmpeg_tool(tool_name, arguments)
        elif engine_type == "ai_inference":
            return await self._execute_ai_tool(tool_name, arguments)
        else:
            return {
                "success": False,
                "error": "UNKNOWN_ENGINE",
                "message": f"Unknown engine type: {engine_type}"
            }
    
    async def run(self):
        """运行MCP服务器（stdio模式）"""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, 
                                  self.server.create_initialization_options())
```

---

## 六、与AI规划层集成

### 6.1 LangChain 集成示例

```python
from langchain_mcp import MCPToolkit
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

async def create_puppet_agent():
    """创建木偶视频自动化Agent"""
    
    # 连接MCP服务器
    toolkit = MCPToolkit.from_client(
        # 使用stdio连接本地MCP服务器
        command=["python", "mcp_server.py"],
    )
    
    # 获取所有工具
    tools = toolkit.get_tools()
    
    # LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)
    
    # Prompt模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业的木偶视频自动化制作助手。
你可以使用提供的MCP工具来完成视频制作任务。

工作流程：
1. 分析用户需求
2. 调用预处理工具（语音识别、镜头分割、目标检测等）
3. 调用抠像跟踪工具（蒙版生成、姿态估计等）
4. 调用风格化工具（AE合成、Blender场景等）
5. 调用渲染输出工具
6. 返回最终结果

注意事项：
- 先进行预处理，再进行抠像跟踪，最后风格化渲染
- 每一步操作前确认前置条件
- 遇到错误自动重试或尝试替代方案
- 报告进度和结果
"""),
        ("user", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    # 创建Agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True,
        max_iterations=50,
    )
    
    return agent_executor

# 使用示例
async def main():
    agent = await create_puppet_agent()
    
    result = await agent.ainvoke({
        "input": """请将 /path/to/video.mp4 制作成木质风格的木偶视频，
                   要求：定格动画效果、有关节和提线、舞台背景、电影感调色。
                   输出1080p MP4格式。"""
    })
    
    print(result["output"])
```

---

## 七、监控与运维

### 7.1 监控指标

| 指标类别 | 指标名称 | 说明 |
|---------|---------|------|
| **引擎状态** | engine_up | 引擎是否在线 |
| | engine_cpu | 引擎CPU使用率 |
| | engine_memory | 引擎内存使用 |
| | engine_gpu | GPU使用率（AI推理） |
| **任务指标** | tasks_total | 总任务数 |
| | tasks_success | 成功任务数 |
| | tasks_failed | 失败任务数 |
| | task_duration | 任务耗时 |
| | task_queue_length | 队列长度 |
| **性能指标** | tool_calls_total | 工具调用总数 |
| | tool_latency | 工具调用延迟 |
| | render_speed | 渲染速度（帧/秒） |
| **质量指标** | quality_score | 输出质量评分 |
| | error_rate | 错误率 |

### 7.2 Prometheus监控集成

```python
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# 指标定义
engine_up = Gauge('engine_up', 'Engine status', ['engine_type', 'engine_id'])
task_duration = Histogram('task_duration_seconds', 'Task duration', 
                          ['engine_type', 'task_type'])
tool_calls_total = Counter('tool_calls_total', 'Total tool calls',
                           ['engine_type', 'tool_name'])
task_queue_length = Gauge('task_queue_length', 'Task queue length')
error_count = Counter('errors_total', 'Total errors', 
                      ['engine_type', 'error_type'])

def start_monitoring(port: int = 8000):
    """启动监控服务"""
    start_http_server(port)
```

---

> **关联文档**：
> - [[企业级架构落地实施手册]]
> - [[木偶视频自动化流水线-全软件最高配置落地总计划]]
> - [[批量生产与项目管理指南]]