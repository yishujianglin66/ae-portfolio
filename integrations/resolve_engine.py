"""
DaVinci Resolve Studio Automation Engine
=========================================
通过 fuscript.exe + Lua 实现 Resolve 全功能自动化。
基于 CDL + LUT + SetProperty 架构（Studio 版可用 API）。

核心通信协议:
  Python → 生成 Lua 脚本 → 写入临时文件
  fuscript.exe 执行 → JSON 输出到 stdout
  Python 解析 JSON → 返回结构化结果
"""

import json
import logging
import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.resolve_discovery import find_fuscript_exe, is_process_running

logger = logging.getLogger(__name__)

# fuscript.exe 路径：由 core/resolve_discovery 统一发现（唯一权威来源）。
# 此前本常量硬编码 r"D:\app\fuscript.exe"，与 ai/resolve_executor.py、
# integrations/resolve_mcp_adapter.py、pipeline/flagship_runner.py 的各自实现
# 互不一致 —— 换台机器就会出现"已安装却被判定未找到"。
# 未找到时为空串：调用方惯用的 os.path.exists(FUSCRIPT_PATH) 自然为 False。
_fuscript_found = find_fuscript_exe()
FUSCRIPT_PATH = str(_fuscript_found) if _fuscript_found is not None else ""

# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class CDLConfig:
    """ASC CDL 调色配置"""
    slope: tuple[float, float, float] = (1.0, 1.0, 1.0)  # RGB 斜率
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB 偏移
    power: tuple[float, float, float] = (1.0, 1.0, 1.0)   # RGB 幂
    saturation: float = 1.0

@dataclass
class TransformConfig:
    """变换配置"""
    zoom_x: float = 1.0
    zoom_y: float = 1.0
    position_x: float = 0.0
    position_y: float = 0.0
    rotation: float = 0.0
    opacity: float = 100.0

@dataclass
class SpeedConfig:
    """变速配置"""
    speed: float = 1.0          # 1.0=正常, 2.0=两倍速, 0.5=半速
    retime_process: int = 0     # 0=Project, 1=Nearest, 2=Optical Flow

@dataclass
class SpeedCurve:
    """变速曲线配置"""
    curve_type: str = "linear"  # linear / ease_in / ease_out / ease_in_out / ramp_up / ramp_down
    start_speed: float = 1.0    # 起始速度倍率
    end_speed: float = 1.0      # 结束速度倍率
    duration_sec: float = 0.0   # 变速持续时间（0=整个片段）

@dataclass
class KenBurnsConfig:
    """Ken Burns 拉镜配置"""
    start_zoom: float = 1.0     # 起始缩放
    end_zoom: float = 1.5       # 结束缩放
    start_x: float = 0.5        # 起始X位置 (0.0-1.0, 0.5=中心)
    start_y: float = 0.5        # 起始Y位置
    end_x: float = 0.5          # 结束X位置
    end_y: float = 0.5          # 结束Y位置
    duration_sec: float = 0.0   # 持续时间（0=整个片段）

@dataclass
class ZoomTransition:
    """Zoom 转场配置"""
    direction: str = "in"       # in=zoom in, out=zoom out
    scale_start: float = 1.0    # 起始缩放
    scale_end: float = 3.0      # 结束缩放
    duration_sec: float = 0.5   # 转场持续时间

@dataclass
class ItemEffect:
    """片段特效配置（FFmpeg 渲染时应用）"""
    item_index: int = 0
    speed_curve: SpeedCurve | None = None
    ken_burns: KenBurnsConfig | None = None
    zoom_transition: ZoomTransition | None = None
    crop: dict[str, float] | None = None  # {left, right, top, bottom} 0.0-1.0

@dataclass
class TransitionConfig:
    """转场配置（阶段3）"""
    type: str = "whip_pan"   # whip_pan/zoom/glitch/flash/morph/iris_wipe/light_leak/film_burn
    duration: float = 0.5    # 转场持续时间（秒）

@dataclass
class ColorWheelConfig:
    """三路色轮配置（阶段3：shadows/midtones/highlights）"""
    shadows: tuple[float, float, float] = (0.0, 0.0, 0.0)     # RGB 偏移 -1.0~1.0
    midtones: tuple[float, float, float] = (0.0, 0.0, 0.0)
    highlights: tuple[float, float, float] = (0.0, 0.0, 0.0)

@dataclass
class Keyframe:
    """关键帧（阶段3）"""
    time: float = 0.0     # 时间点（秒）
    value: float = 0.0    # 属性值

@dataclass
class RenderConfig:
    """渲染配置"""
    output_path: str = ""
    preset_name: str = "H.264 Master"
    format: str = "mp4"
    codec: str = "H.264"
    resolution: str = "1920x1080"

@dataclass
class TimelineItemInfo:
    """时间线片段信息"""
    index: int = 0
    name: str = ""
    duration: float = 0.0
    start: float = 0.0
    end: float = 0.0
    speed: float = 1.0

@dataclass
class ProjectInfo:
    """项目信息"""
    name: str = ""
    timeline_count: int = 0
    current_timeline: str = ""
    items: list[TimelineItemInfo] = field(default_factory=list)


# ============================================================================
# 核心引擎
# ============================================================================

class ResolveAutomationEngine:
    """
    DaVinci Resolve Studio 自动化引擎
    
    通过 fuscript.exe 执行 Lua 脚本实现:
    - 项目管理（创建/加载/删除）
    - 素材导入与时间线编排
    - CDL 调色 + LUT 应用
    - 变速控制（SetProperty）
    - 变换控制（缩放/位移/旋转/裁切）
    - 渲染输出
    """
    
    def __init__(self, fuscript_path: str | None = None, timeout: int = 120):
        if fuscript_path is None:
            _found = find_fuscript_exe()
            fuscript_path = str(_found) if _found is not None else ""
        self.fuscript = fuscript_path
        self.timeout = timeout
        self._temp_dir = tempfile.mkdtemp(prefix="resolve_engine_")
        self._media_path_map: dict[str, str] = {}  # project_name -> {item_name: file_path}
        self._cdl_config_map: dict[str, dict[int, CDLConfig]] = {}  # project_name -> {clip_index: CDLConfig}
        
        # 阶段2：性能优化基础设施
        self._proxy_original_map: dict[str, str] = {}  # proxy_path -> original_path
        self._proxy_media_map: dict[str, dict[str, str]] = {}  # project_name -> {item_name: original_path}
        self._gpu_encoder_cache: str | None = None  # GPU 编码器检测结果缓存
        self._colorwheel_map: dict[str, dict[int, ColorWheelConfig]] = {}  # 阶段3：色轮配置
        self._lut_file_map: dict[str, dict[int, str]] = {}  # 阶段3：LUT 文件映射
        self._cache_dir = os.path.join(tempfile.gettempdir(), "resolve_render_cache")
        os.makedirs(self._cache_dir, exist_ok=True)

        # 可用性探测：**不再在构造期抛异常**（2026-09-23 集成测试暴露的缺陷）。
        # 原实现 fuscript.exe 缺失即 raise FileNotFoundError，后果是
        # `UnifiedVideoPipeline()` 在没装 Resolve 的机器上**整个构造不出来** ——
        # 连不需要 Resolve 的能力（智能调色推荐 / FFmpeg 补帧 / 风格预设）也一起
        # 不可达。实测该缺陷把 tests/test_unified_v21_e2e.py 的 5 个用例逼成
        # "整文件 skip"：用跳过掩盖问题，而不是修问题。
        # 现改为优雅降级（与本项目 CNN+VLM 分层降级、ComfyUI 降级同一原则）：
        # 构造成功并标记不可用；真正需要 Resolve 的调用点由 _require_available()
        # 抛带修复指引的明确错误。
        self.available = bool(fuscript_path) and os.path.exists(fuscript_path)
        self.unavailable_reason = (
            "" if self.available else
            f"fuscript.exe not found: {fuscript_path or '(未发现安装目录)'} "
            f"(设 AEKV_RESOLVE_HOME 指向 DaVinci Resolve 安装目录, 或先安装 Resolve)"
        )
        # API 需 Resolve.exe 处于运行状态：fuscript 本身可无头执行，但脚本内
        # Resolve() 只在活实例存在时返回句柄。可运行不代表此刻可调用。
        self.api_reachable = self.available and is_process_running()
        if not self.available:
            print(f"[ResolveAutomationEngine] 不可用, 已降级: {self.unavailable_reason}")
        elif not self.api_reachable:
            print(
                "[ResolveAutomationEngine] fuscript 已就绪但 Resolve 未运行；"
                "需 Resolve API 的调用会失败，可用 core.resolve_discovery.launch_resolve() 启动"
            )

    def _require_available(self) -> None:
        """需 Resolve 的调用点前置检查：不可用时抛可执行的明确错误。"""
        if not getattr(self, "available", False):
            raise ResolveError(f"DaVinci Resolve 不可用: {self.unavailable_reason}")

    def _ok_from(self, res: Any, what: str, *, void_api: bool = False) -> bool:
        """从 Lua 回传里取**真实**成功标志（2026-09-24 返回值诚实性审计）。

        Lua 侧契约：调 API 后 emit `{{ok = <API返回值>, ret_type = type(<API返回值>), completed = true}}`。
        Lua 表里 **nil 值会被 pairs 丢掉**，故三态天然可辨：
          · API 返回 true  → 有 "ok":true
          · API 返回 false → 有 "ok":false
          · API 返回 nil   → **没有 ok 键**（配 ret_type="nil"）

        判据按 API 契约分级、**不假设**（真机探针 2026-09-24）：
          1. 有布尔 `ok` → 用它（最硬的证据）；
          2. `void_api=True` 且 `ret_type=="nil"` → 该 API 实测不返回结果
             （`OpenPage` 对合法页与非法页**都**返回 nil），无法据返回值判定；
             按「调用已发出且未报错」记为成功，并**明确标注未经效果验证**；
          3. 其余（Bool 型 API 却拿到 nil、或回传缺字段/垃圾）→ **判为失败**，
             不得默认成功 —— 被修掉的原实现正是"注解 `-> bool` 却无条件 `return True`"。
        """
        if not isinstance(res, dict):
            logger.warning(
                f"{what}: 回传不是字典（{type(res).__name__}），无法确认成功 → 判为失败")
            return False

        ok = res.get("ok")
        if isinstance(ok, bool):
            if not ok:
                logger.warning(f"{what}: Resolve API 返回 false（操作未生效）")
            return ok

        if void_api and res.get("ret_type") == "nil" and res.get("completed") is True:
            logger.info(
                f"{what}: 该 API 无返回值（type=nil），按「调用未报错」记为成功；"
                f"注意这是**未经效果验证**的结论")
            return True

        logger.warning(
            f"{what}: 回传缺少布尔 ok（ret_type={res.get('ret_type')!r}）→ 判为失败")
        return False

    
    def __del__(self):
        """清理临时文件"""
        try:
            import shutil
            if os.path.exists(self._temp_dir):
                shutil.rmtree(self._temp_dir, ignore_errors=True)
        except:
            pass
    
    # ----------------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------------
    
    def _execute_lua(self, lua_code: str) -> dict[str, Any]:
        """
        执行 Lua 脚本并解析 JSON 输出。
        
        Lua 脚本应通过 print() 输出 JSON 到 stdout，格式:
        {"status": "ok", "data": {...}} 或 {"status": "error", "message": "..."}
        """
        # 写入临时文件
        script_path = os.path.join(self._temp_dir, f"cmd_{int(time.time()*1000)}.lua")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(lua_code)
        
        try:
            result = subprocess.run(
                [self.fuscript, script_path],
                capture_output=True, text=True,
                timeout=self.timeout,
                encoding='utf-8', errors='replace'
            )
            
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            # 解析 JSON 输出（查找最后一行有效的 JSON）
            for line in reversed(stdout.split('\n')):
                line = line.strip()
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        if data.get('status') == 'error':
                            raise ResolveError(data.get('message', 'Unknown error'))
                        return data.get('data', data)
                    except json.JSONDecodeError:
                        continue
            
            # 如果没有找到 JSON，检查是否有错误
            if result.returncode != 0 or 'error' in stderr.lower():
                raise ResolveError(f"fuscript failed (exit={result.returncode}): {stderr[:500]}")
            
            # 返回原始输出
            return {"raw": stdout, "returncode": result.returncode}
            
        except subprocess.TimeoutExpired:
            raise ResolveError(f"Lua script timed out after {self.timeout}s")
        finally:
            # 清理临时脚本
            try:
                os.remove(script_path)
            except:
                pass
    
    def _wrap_lua(self, body: str) -> str:
        """
        包装 Lua 代码，添加 JSON 输出和错误处理。
        body 中应设置 result_data 变量。
        """
        return f'''
local function json_encode_table(t)
    -- 简单 JSON 编码（fuscript 内置 JSON 支持有限）
    if type(t) == "table" then
        local parts = {{}}
        local is_array = true
        local max_n = 0
        for k, v in pairs(t) do
            if type(k) ~= "number" then is_array = false; break end
            if k > max_n then max_n = k end
        end
        if is_array and max_n == #t then
            for i, v in ipairs(t) do
                parts[i] = json_encode_table(v)
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(t) do
                local key = type(k) == "number" and tostring(k) or '"' .. tostring(k) .. '"'
                table.insert(parts, key .. ':' .. json_encode_table(v))
            end
            return '{{' .. table.concat(parts, ',') .. '}}'
        end
    elseif type(t) == "string" then
        return '"' .. t:gsub('\\\\', '\\\\\\\\'):gsub('"', '\\\\"'):gsub('\\n', '\\\\n') .. '"'
    elseif type(t) == "number" then
        return tostring(t)
    elseif type(t) == "boolean" then
        return t and "true" or "false"
    else
        return "null"
    end
end

local function emit_ok(data)
    local result = {{status = "ok", data = data or {{}}}}
    print(json_encode_table(result))
end

local function emit_error(msg)
    local result = {{status = "error", message = tostring(msg)}}
    print(json_encode_table(result))
end

local function safe_tonumber(v, default)
    if v == nil then return default or 0 end
    local ok, n = pcall(tonumber, v)
    if ok and n then return n end
    return default or 0
end

-- 用户代码
local ok, err = pcall(function()
{body}
end)

if not ok then
    emit_error(err)
end
'''
    
    # ----------------------------------------------------------------
    # 项目管理
    # ----------------------------------------------------------------
    
    def create_project(self, name: str) -> str:
        """创建并加载项目"""
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:CreateProject("{name}")
    if not proj then
        -- 尝试加载已有的
        proj = pm:LoadProject("{name}")
    end
    if not proj then
        error("Cannot create or load project: {name}")
    end
    emit_ok({{name = proj:GetName()}})
''')
        result = self._execute_lua(lua)
        return result.get("name", name)
    
    def load_project(self, name: str) -> str:
        """加载已有项目"""
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{name}")
    if not proj then error("Cannot load project: {name}") end
    emit_ok({{name = proj:GetName()}})
''')
        result = self._execute_lua(lua)
        return result.get("name", name)
    
    def delete_project(self, name: str) -> bool:
        """删除项目。返回 Resolve API 的真实结果（2026-09-24 修：原实现无条件 return True）。"""
        self._require_available()
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local ok = pm:DeleteProject("{name}")
    emit_ok({{ok = ok, ret_type = type(ok), completed = true, deleted = "{name}"}})
''')
        return self._ok_from(self._execute_lua(lua), f"delete_project({name})")
    
    def get_project_info(self) -> ProjectInfo:
        """获取当前项目信息。

        修复（2026-09-23）：原实现执行了 Lua 却**丢弃返回值**，无条件返回空的
        ProjectInfo —— 调用方永远拿到 name="" / timeline_count=0。即"执行过但没接线"。
        现按 _execute_lua 的真实契约（返回 data 字典）填充字段。
        仅使用本机实测可用的 API 面（GetName / GetTimelineCount / GetCurrentTimeline）。
        """
        lua = self._wrap_lua('''
    local resolve = Resolve()
    if resolve == nil then
        emit_ok({available = false})
        return
    end
    local pm = resolve:GetProjectManager()
    local name = ""
    local timeline_count = 0
    local current_timeline = ""
    if pm ~= nil then
        local proj = pm:GetCurrentProject()
        if proj ~= nil then
            local ok_n, n = pcall(function() return proj:GetName() end)
            if ok_n and n ~= nil then name = tostring(n) end
            local ok_c, c = pcall(function() return proj:GetTimelineCount() end)
            if ok_c and c ~= nil then timeline_count = tonumber(c) or 0 end
            local ok_t, tl = pcall(function() return proj:GetCurrentTimeline() end)
            if ok_t and tl ~= nil then
                local ok_tn, tn = pcall(function() return tl:GetName() end)
                if ok_tn and tn ~= nil then current_timeline = tostring(tn) end
            end
        end
    end
    emit_ok({available = true, name = name,
             timeline_count = timeline_count,
             current_timeline = current_timeline})
''')
        raw = self._execute_lua(lua)
        info = ProjectInfo()
        if not isinstance(raw, dict):
            return info
        if raw.get("available") is False:
            # fuscript 在但 Resolve 未运行：Resolve() 返回 nil
            return info
        info.name = str(raw.get("name") or "")
        try:
            info.timeline_count = int(raw.get("timeline_count") or 0)
        except (TypeError, ValueError):
            info.timeline_count = 0
        info.current_timeline = str(raw.get("current_timeline") or "")
        return info
    
    # ----------------------------------------------------------------
    # 素材导入与时间线
    # ----------------------------------------------------------------
    
    def import_media(self, project_name: str, file_paths: list[str]) -> list[str]:
        """导入素材到 MediaPool"""
        # 构建 Lua 数组
        lua_files = "{" + ", ".join(f'"{f.replace(chr(92), "/")}"' for f in file_paths) + "}"
        
        # 记录素材路径映射
        if project_name not in self._media_path_map:
            self._media_path_map[project_name] = {}
        for fp in file_paths:
            fname = os.path.basename(fp)
            self._media_path_map[project_name][fname] = fp
        
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    local mediaPool = proj:GetMediaPool()
    local imported = mediaPool:ImportMedia({lua_files})
    
    local names = {{}}
    if imported then
        for i, clip in ipairs(imported) do
            table.insert(names, clip:GetName())
        end
    end
    
    emit_ok({{imported_count = #names, names = names}})
''')
        result = self._execute_lua(lua)
        return result.get("names", [])
    
    def create_timeline_with_media(self, project_name: str, timeline_name: str, 
                                   media_files: list[str]) -> dict:
        """创建项目 + 导入素材 + 创建时间线（一步完成）"""
        lua_media = "{" + ", ".join(f'"{f.replace(chr(92), "/")}"' for f in media_files) + "}"
        
        # 记录素材路径映射
        if project_name not in self._media_path_map:
            self._media_path_map[project_name] = {}
        for fp in media_files:
            fname = os.path.basename(fp)
            self._media_path_map[project_name][fname] = fp
        
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    
    -- 创建或加载项目
    local proj = pm:CreateProject("{project_name}")
    if not proj then proj = pm:LoadProject("{project_name}") end
    if not proj then error("Cannot create project: {project_name}") end
    
    -- 修复：Resolve 默认项目分辨率为 960x540，会把 1080p 素材降采样输出；
    -- 必须在创建时间线前强制 1920x1080
    proj:SetSetting("timelineResolutionWidth", "1920")
    proj:SetSetting("timelineResolutionHeight", "1080")
    
    local mp = proj:GetMediaPool()
    
    -- 导入素材
    local imported = mp:ImportMedia({lua_media})
    if not imported or #imported == 0 then
        error("No media imported")
    end
    
    -- 创建时间线 (2026-08-13 修复: CreateEmptyTimeline+AppendToTimeline 是旧API,
    -- 当前 Resolve 版本 AppendToTimeline 对空时间线返回 nil 导致 "No media imported"。
    -- 改用 CreateTimelineFromClips 一步建时间线并添加素材, 实测通过。)
    local tl = mp:CreateTimelineFromClips("{timeline_name}", imported)
    if not tl then error("Cannot create timeline") end
    
    -- 设为当前时间线
    proj:SetCurrentTimeline(tl)
    
    -- 获取时间线信息
    local items = tl:GetItemsInTrack("video", 1)
    local item_list = {{}}
    if items then
        for k, v in pairs(items) do
            table.insert(item_list, {{
                index = k,
                name = v:GetName(),
                duration = v:GetDuration(),
                start_frame = v:GetStart(),
                end_frame = v:GetEnd()
            }})
        end
    end
    
    emit_ok({{
        project = proj:GetName(),
        timeline = tl:GetName(),
        clip_count = #imported,
        items = item_list
    }})
''')
        return self._execute_lua(lua)
    
    # ----------------------------------------------------------------
    # CDL 调色
    # ----------------------------------------------------------------
    
    def apply_cdl(self, project_name: str, timeline_name: str,
                  item_index: int, cdl: CDLConfig) -> bool:
        """对指定片段应用 CDL 调色。

        返回 Resolve API 的真实结果（2026-09-24 修）：原实现 Lua 里已经把
        `local ok = item:SetCDL(...)` 接住了，却只 emit `cdl_applied = true` —— 真相在手上被丢掉。
        注意：`_cdl_config_map` 的登记是**为 FFmpeg 渲染路径**服务的（与 Resolve 调用成败无关），
        故仍在调用前记录，不随返回值回滚。
        """
        self._require_available()
        # 记录 CDL 配置用于后续 FFmpeg 渲染
        if project_name not in self._cdl_config_map:
            self._cdl_config_map[project_name] = {}
        self._cdl_config_map[project_name][item_index] = cdl
        
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    local tl = proj:GetCurrentTimeline()
    if not tl then error("No current timeline") end
    
    local items = tl:GetItemsInTrack("video", 1)
    if not items then error("No items in timeline") end
    
    local item = items[{item_index}]
    if not item then error("Item {item_index} not found") end
    
    local ok = item:SetCDL({{
        Slope = {{{cdl.slope[0]}, {cdl.slope[1]}, {cdl.slope[2]}}},
        Offset = {{{cdl.offset[0]}, {cdl.offset[1]}, {cdl.offset[2]}}},
        Power = {{{cdl.power[0]}, {cdl.power[1]}, {cdl.power[2]}}},
        Saturation = {cdl.saturation}
    }})
    
    emit_ok({{ok = ok, ret_type = type(ok), completed = true, item = item:GetName()}})
''')
        return self._ok_from(
            self._execute_lua(lua), f"apply_cdl({project_name}#{item_index})")
    
    def apply_lut(self, project_name: str, timeline_name: str,
                  item_index: int, lut_path: str) -> bool:
        """对指定片段应用 LUT。返回 Resolve API 的真实结果（2026-09-24 修）。"""
        self._require_available()
        lut_lua = lut_path.replace("\\", "/")
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    local tl = proj:GetCurrentTimeline()
    if not tl then error("No current timeline") end
    
    local items = tl:GetItemsInTrack("video", 1)
    local item = items[{item_index}]
    if not item then error("Item {item_index} not found") end
    
    local ok = item:SetLUT("{lut_lua}")
    emit_ok({{ok = ok, ret_type = type(ok), completed = true, item = item:GetName(), lut = "{lut_lua}"}})
''')
        return self._ok_from(
            self._execute_lua(lua), f"apply_lut({project_name}#{item_index})")
    
    # ----------------------------------------------------------------
    # 变速控制
    # ----------------------------------------------------------------
    
    def set_speed(self, project_name: str, item_index: int, 
                  speed: float, retime_process: int = 0) -> bool:
        """设置片段播放速度。返回 Resolve API 的真实结果（2026-09-24 修）。"""
        self._require_available()
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    local tl = proj:GetCurrentTimeline()
    if not tl then error("No current timeline") end
    
    local items = tl:GetItemsInTrack("video", 1)
    local item = items[{item_index}]
    if not item then error("Item {item_index} not found") end
    
    local ok = item:SetProperty("Speed", {speed})
    if {retime_process} > 0 then
        ok = item:SetProperty("RetimeProcess", {retime_process}) and ok
    end
    
    emit_ok({{ok = ok, ret_type = type(ok), completed = true,
             item = item:GetName(), speed = {speed}, duration = item:GetDuration()}})
''')
        return self._ok_from(
            self._execute_lua(lua), f"set_speed({project_name}#{item_index})")
    
    # ----------------------------------------------------------------
    # 变换控制
    # ----------------------------------------------------------------
    
    def set_transform(self, project_name: str, item_index: int,
                      transform: TransformConfig) -> bool:
        """设置片段变换参数。返回 Resolve API 的真实结果（2026-09-24 修）。

        6 个 SetProperty 逐个与 `ok` 相与 —— 任一项失败即整体 False（不再一律 True）。
        """
        self._require_available()
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    local tl = proj:GetCurrentTimeline()
    local items = tl:GetItemsInTrack("video", 1)
    local item = items[{item_index}]
    if not item then error("Item {item_index} not found") end
    
    local ok = item:SetProperty("Zoom X", {transform.zoom_x})
    ok = item:SetProperty("Zoom Y", {transform.zoom_y}) and ok
    ok = item:SetProperty("Position X", {transform.position_x}) and ok
    ok = item:SetProperty("Position Y", {transform.position_y}) and ok
    ok = item:SetProperty("Rotation", {transform.rotation}) and ok
    ok = item:SetProperty("Opacity", {transform.opacity}) and ok
    
    emit_ok({{ok = ok, ret_type = type(ok), completed = true, item = item:GetName()}})
''')
        return self._ok_from(
            self._execute_lua(lua), f"set_transform({project_name}#{item_index})")
    
    # ----------------------------------------------------------------
    # 高级特效（FFmpeg 渲染时应用）
    # ----------------------------------------------------------------
    
    def apply_speed_curve(self, project_name: str, item_index: int,
                          curve: SpeedCurve) -> bool:
        """
        对片段应用变速曲线。
        在 Resolve 中设置基础速度，实际曲线效果在 FFmpeg 渲染时应用。

        2026-09-24 修：原实现丢弃 `set_speed` 的结果并无条件 return True —— 现原样返回。
        """
        # Resolve 中设置平均速度
        avg_speed = (curve.start_speed + curve.end_speed) / 2.0
        return self.set_speed(project_name, item_index, avg_speed)
    
    def apply_ken_burns(self, project_name: str, item_index: int,
                        config: KenBurnsConfig) -> bool:
        """
        对片段应用 Ken Burns 拉镜效果。
        在 Resolve 中设置起始/结束变换，实际动画在 FFmpeg 渲染时生成。

        2026-09-24 修：原实现丢弃 `set_transform` 的结果并无条件 return True —— 现原样返回。
        """
        # 设置起始变换
        start_tf = TransformConfig(
            zoom_x=config.start_zoom, zoom_y=config.start_zoom,
            position_x=(config.start_x - 0.5) * 100,
            position_y=(config.start_y - 0.5) * 100,
        )
        return self.set_transform(project_name, item_index, start_tf)
    
    def get_timeline_info(self, project_name: str) -> dict:
        """获取时间线详细信息（用于 FFmpeg 渲染决策）"""
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    local tl = proj:GetCurrentTimeline()
    if not tl then error("No current timeline") end
    
    local items = tl:GetItemsInTrack("video", 1)
    local item_list = {{}}
    if items then
        for k, v in pairs(items) do
            -- Try to get CDL values (may not be available via API)
            local cdl_ok, cdl_val = pcall(function() return v:GetCDL() end)
            local cdl_data = nil
            if cdl_ok and cdl_val then
                cdl_data = {{
                    slope_r = cdl_val.Slope and cdl_val.Slope[1] or 1.0,
                    slope_g = cdl_val.Slope and cdl_val.Slope[2] or 1.0,
                    slope_b = cdl_val.Slope and cdl_val.Slope[3] or 1.0,
                    offset_r = cdl_val.Offset and cdl_val.Offset[1] or 0.0,
                    offset_g = cdl_val.Offset and cdl_val.Offset[2] or 0.0,
                    offset_b = cdl_val.Offset and cdl_val.Offset[3] or 0.0,
                    power_r = cdl_val.Power and cdl_val.Power[1] or 1.0,
                    power_g = cdl_val.Power and cdl_val.Power[2] or 1.0,
                    power_b = cdl_val.Power and cdl_val.Power[3] or 1.0,
                    saturation = cdl_val.Saturation or 1.0,
                }}
            end
            
            table.insert(item_list, {{
                index = k,
                name = v:GetName(),
                duration = v:GetDuration(),
                start_frame = v:GetStart(),
                end_frame = v:GetEnd(),
                speed = safe_tonumber(v:GetProperty("Speed"), 1.0),
                zoom_x = safe_tonumber(v:GetProperty("Zoom X"), 1.0),
                zoom_y = safe_tonumber(v:GetProperty("Zoom Y"), 1.0),
                pos_x = safe_tonumber(v:GetProperty("Position X"), 0.0),
                pos_y = safe_tonumber(v:GetProperty("Position Y"), 0.0),
                rotation = safe_tonumber(v:GetProperty("Rotation"), 0.0),
                opacity = safe_tonumber(v:GetProperty("Opacity"), 100.0),
                cdl = cdl_data,
            }})
        end
    end
    
    emit_ok({{
        timeline = tl:GetName(),
        fps = safe_tonumber(proj:GetSetting("timelineFrameRate"), 24.0),
        width = safe_tonumber(proj:GetSetting("timelineResolutionWidth"), 1920),
        height = safe_tonumber(proj:GetSetting("timelineResolutionHeight"), 1080),
        items = item_list
    }})
''')
        return self._execute_lua(lua)
    
    # ----------------------------------------------------------------
    # 渲染输出
    # ----------------------------------------------------------------
    
    def _render_with_ffmpeg(self, project_name: str, output_path: str,
                             effects: dict[int, ItemEffect] | None = None) -> str:
        """
        使用 FFmpeg 渲染（推荐）。
        从 Resolve 获取时间线信息，然后用 FFmpeg 处理素材并应用效果。
        """
        # 获取时间线详细信息
        tl_info = self.get_timeline_info(project_name)
        items = tl_info.get("items", [])
        fps = tl_info.get("fps", 24.0)
        
        if not items:
            raise ResolveError("No items in timeline")
        
        # 获取该项目的素材路径映射
        media_map = self._media_path_map.get(project_name, {})
        
        # 构建 FFmpeg 命令（支持特效）
        ffmpeg_cmd = self._build_ffmpeg_command(project_name, items, output_path, media_map, effects, fps)
        
        logger.info(f"Running FFmpeg: {shlex.join(ffmpeg_cmd)}")
        try:
            subprocess.run(ffmpeg_cmd, check=True,
                          capture_output=True, timeout=300)
            if os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"Render complete: {output_path} ({size_mb:.1f}MB)")
            return output_path
        except subprocess.TimeoutExpired:
            raise ResolveError("FFmpeg render timed out")
        except subprocess.CalledProcessError as e:
            raise ResolveError(f"FFmpeg failed: {e.stderr.decode()[:500] if e.stderr else str(e)}")
    
    def _build_ffmpeg_command(self, project_name: str, items: list[dict], output_path: str,
                               media_map: dict[str, str] | None = None,
                               effects: dict[int, ItemEffect] | None = None,
                               fps: float = 24.0,
                               apply_cdl_from_resolve: bool = True) -> list[str]:
        """
        构建 FFmpeg 命令（支持多素材拼接 + 每片段特效 + CDL 调色）
        
        Args:
            items: 时间线片段信息
            output_path: 输出路径
            media_map: 素材名→路径映射
            effects: 片段索引→ItemEffect 映射
            fps: 时间线帧率
            apply_cdl_from_resolve: 是否从 Resolve 读取并应用 CDL 调色
        """
        if not items:
            return ""
        
        media_map = media_map or {}
        effects = effects or {}
        
        # 解析每个 item 的素材路径
        inputs = []
        for item in items:
            item_name = item.get("name", "")
            file_path = media_map.get(item_name, "")
            if not file_path:
                for d in [r"C:\VinlandClips", r"C:\Users\Administrator\Desktop"]:
                    candidate = os.path.join(d, item_name)
                    if os.path.exists(candidate):
                        file_path = candidate
                        break
            if file_path and os.path.exists(file_path):
                inputs.append((file_path, item))
        
        if not inputs:
            raise ResolveError(f"No media files found for items. Map: {media_map}")
        
        # 构建每个片段的滤镜
        filter_parts = []
        for i, (path, item) in enumerate(inputs):
            idx = item.get("index", i + 1)
            speed = item.get("speed", 1.0)
            effect = effects.get(idx)
            
            vf_parts = []
            
            # CDL 调色（从 Python 层追踪的配置中读取）
            cdl = self._cdl_config_map.get(project_name, {}).get(idx)
            if cdl:
                # FFmpeg eq 滤镜近似实现 ASC CDL
                # Slope → contrast/gamma, Offset → brightness, Power → gamma, Saturation → saturation
                avg_slope = (cdl.slope[0] + cdl.slope[1] + cdl.slope[2]) / 3.0
                avg_offset = (cdl.offset[0] + cdl.offset[1] + cdl.offset[2]) / 3.0
                avg_power = (cdl.power[0] + cdl.power[1] + cdl.power[2]) / 3.0
                sat = cdl.saturation
                
                # 映射到 FFmpeg eq 参数（更精确的转换公式）
                # Slope 主要影响对比度和高光
                contrast = max(0.5, min(3.0, avg_slope))
                # Offset 影响整体亮度
                brightness = max(-0.5, min(0.5, avg_offset * 0.8))
                # Power 影响伽马曲线
                gamma = max(0.4, min(2.5, avg_power))
                # Saturation 直接映射
                saturation = max(0.0, min(5.0, sat))
                
                vf_parts.append(f"eq=contrast={contrast:.3f}:brightness={brightness:.3f}:gamma={gamma:.3f}:saturation={saturation:.3f}")
            
            # ✅ 阶段3：LUT 应用（lut3d 滤镜）
            lut_file = self._lut_file_map.get(project_name, {}).get(idx)
            if lut_file and os.path.exists(lut_file):
                lut_path_ff = lut_file.replace("\\", "/").replace(":", "\\:")
                vf_parts.append(f"lut3d='{lut_path_ff}'")
            
            # ✅ 阶段3：色轮调整（colorbalance 滤镜）
            cw = self._colorwheel_map.get(project_name, {}).get(idx)
            if cw:
                sh, mid, hi = cw.shadows, cw.midtones, cw.highlights
                vf_parts.append(
                    f"colorbalance=rs={sh[0]:.3f}:gs={sh[1]:.3f}:bs={sh[2]:.3f}"
                    f":rm={mid[0]:.3f}:gm={mid[1]:.3f}:bm={mid[2]:.3f}"
                    f":rh={hi[0]:.3f}:gh={hi[1]:.3f}:bh={hi[2]:.3f}")
            
            # 变速
            if speed != 1.0 and speed > 0:
                pts = 1.0 / speed
                vf_parts.append(f"setpts={pts}*PTS")
            
            # 变速曲线
            if effect and effect.speed_curve:
                sc = effect.speed_curve
                vf_parts = []  # 覆盖上面的简单变速
                if sc.curve_type == "ease_in":
                    # 慢→快: PTS 从 start_speed 渐变到 end_speed
                    vf_parts.append(
                        f"setpts=PTS*({sc.start_speed}+({sc.end_speed}-{sc.start_speed})*PTS/duration)"
                    )
                elif sc.curve_type == "ease_out":
                    vf_parts.append(
                        f"setpts=PTS*({sc.end_speed}+({sc.start_speed}-{sc.end_speed})*(1-PTS/duration))"
                    )
                elif sc.curve_type == "ramp_up":
                    vf_parts.append(
                        f"setpts=PTS*({sc.start_speed}+({sc.end_speed}-{sc.start_speed})*PTS/duration)")
                elif sc.curve_type == "ramp_down":
                    vf_parts.append(
                        f"setpts=PTS*({sc.end_speed}+({sc.start_speed}-{sc.end_speed})*PTS/duration)")
            
            # Ken Burns 拉镜（zoompan 使用算术表达式，d=1 适配视频输入）
            if effect and effect.ken_burns:
                kb = effect.ken_burns
                total_frames = max(int(item.get("duration", 84)), 1)
                sz = (kb.end_zoom - kb.start_zoom) / total_frames
                sx = (kb.end_x - kb.start_x) / total_frames
                sy = (kb.end_y - kb.start_y) / total_frames
                vf_parts.append(
                    f"zoompan=z='{kb.start_zoom}+{sz:.5f}*on'"
                    f":x='({kb.start_x}+{sx:.5f}*on)*(iw-iw/zoom)'"
                    f":y='({kb.start_y}+{sy:.5f}*on)*(ih-ih/zoom)'"
                    f":d=1:s=1920x1080:fps={int(fps)}")
            
            # 裁切
            if effect and effect.crop:
                c = effect.crop
                l = c.get("left", 0)
                r = c.get("right", 0)
                t = c.get("top", 0)
                b = c.get("bottom", 0)
                if any([l, r, t, b]):
                    vf_parts.append(f"crop=iw*({1-l-r}):ih*({1-t-b}):iw*{l}:ih*{t}")
            
            if vf_parts:
                filter_parts.append(f"[{i}:v]{','.join(vf_parts)}[v{i}]")
            else:
                filter_parts.append(f"[{i}:v]null[v{i}]")
        
        # Concat 拼接
        n = len(inputs)
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[outv]")
        filter_complex = ";".join(filter_parts)
        
        input_args = [a for p, _ in inputs for a in ("-i", p)]
        
        # ✅ 阶段2：GPU 加速编码器选择
        codec_args = shlex.split(self._get_encoder_args(), posix=False)
        
        cmd = (["ffmpeg", "-y"] + input_args
               + ["-filter_complex", filter_complex, "-map", "[outv]"]
               + codec_args + [output_path])
        
        return cmd
    
    # ----------------------------------------------------------------
    # 阶段2：GPU 加速优化
    # ----------------------------------------------------------------
    
    def _detect_gpu_encoder(self) -> str:
        """
        检测可用的 GPU 硬件编码器（优先级：NVENC > QSV > AMF）
        
        Returns:
            编码器名称（如 'h264_nvenc'），无 GPU 时返回空字符串
        """
        if self._gpu_encoder_cache is not None:
            return self._gpu_encoder_cache
        
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=15)
            encoders = result.stdout
            
            # 按优先级检测
            if 'h264_nvenc' in encoders:
                self._gpu_encoder_cache = 'h264_nvenc'
            elif 'h264_qsv' in encoders:
                self._gpu_encoder_cache = 'h264_qsv'
            elif 'h264_amf' in encoders:
                self._gpu_encoder_cache = 'h264_amf'
            else:
                self._gpu_encoder_cache = ''
        except Exception as e:
            logger.warning(f"GPU encoder detection failed: {e}")
            self._gpu_encoder_cache = ''
        
        if self._gpu_encoder_cache:
            logger.info(f"GPU encoder detected: {self._gpu_encoder_cache}")
        else:
            logger.info("No GPU encoder found, using CPU (libx264)")
        
        return self._gpu_encoder_cache
    
    def _get_encoder_args(self, quality: str = "high") -> str:
        """
        获取编码器参数（自动选择 GPU 或 CPU）
        
        Args:
            quality: 'high'（高质量）/ 'fast'（快速）/ 'preview'（预览）

        注：强制 yuv420p —— zoompan 等滤镜会产出 rgb/yuv444p，
        nvenc 直接透传导致 AE 无法解码 H.264（AE 只支持 4:2:0），
        混合工作流 Stage B 曾因此黑屏（见 ae_bridge_lessons.md）。
        """
        gpu = self._detect_gpu_encoder()
        
        if gpu == 'h264_nvenc':
            # NVENC: p1最快/p7最慢, cq 质量控制；-g 48 固定 2s 关键帧（@24fps），
            # 保证剪辑软件 seek/逐帧编辑流畅，避免默认超长 GOP 错误传播
            presets = {'high': '-preset p6 -rc vbr -cq 20 -b:v 0 -tune hq -g 48',
                       'fast': '-preset p4 -rc vbr -cq 23 -b:v 0 -g 48',
                       'preview': '-preset p1 -rc constqp -qp 28 -g 48'}
            return f'-c:v h264_nvenc {presets.get(quality, presets["fast"])} -pix_fmt yuv420p'
        elif gpu == 'h264_qsv':
            return '-c:v h264_qsv -preset medium -global_quality 23 -g 48 -pix_fmt yuv420p'
        elif gpu == 'h264_amf':
            return '-c:v h264_amf -quality quality -rc cqp -qp 23 -g 48 -pix_fmt yuv420p'
        else:
            presets = {'high': '-preset slow -crf 20 -g 48',
                       'fast': '-preset fast -crf 23 -g 48',
                       'preview': '-preset veryfast -crf 28 -g 48'}
            return f'-c:v libx264 {presets.get(quality, presets["fast"])} -pix_fmt yuv420p'
    
    def _render_with_resolve(self, project_name: str, output_path: str,
                             preset: str = "H.264 Master") -> str:
        """
        使用 Resolve 内置渲染器（保留所有特效），然后自动转码为 MP4。
        
        流程：
        1. Resolve 原生渲染 → .mov 文件（保留 CDL/LUT/变速等所有效果）
        2. FFmpeg 快速转码 → .mp4 文件（无损，几秒钟）
        
        使用异步执行 + 文件轮询机制，避免 emit_ok 通信超时问题。
        """
        import threading
        
        # 分离输出目录和文件名
        output_dir = os.path.dirname(output_path).replace("\\", "/")
        filename = os.path.basename(output_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        # Resolve 总是输出 .mov，我们稍后用 FFmpeg 转码
        temp_mov = os.path.join(output_dir, f"{name_without_ext}_temp.mov")
        temp_mov_lua = temp_mov.replace("\\", "/")
        
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    
    -- 切换到 Deliver 页面
    resolve:OpenPage("deliver")
    
    -- 加载渲染预设
    local preset_ok = proj:LoadRenderPreset("{preset}")
    if not preset_ok then
        print("Warning: Preset '{preset}' not found, using defaults")
    end
    
    -- 设置渲染输出（Resolve 会输出 .mov）
    local render_settings = {{
        TargetDir = "{output_dir}",
        CustomName = "{name_without_ext}_temp",
        ExportVideo = true,
        ExportAudio = true,
        SelectAllFrames = true
    }}
    
    local settings_ok = proj:SetRenderSettings(render_settings)
    if not settings_ok then
        error("Failed to set render settings")
    end
    
    -- 添加渲染任务
    local jobId = proj:AddRenderJob()
    if not jobId or jobId == "" then error("Failed to add render job") end
    
    print("✅ Render job added: " .. tostring(jobId))
    
    -- 开始渲染
    proj:StartRendering(jobId)
    
    -- 等待渲染完成
    local max_wait = 1800  -- 30分钟
    local waited = 0
    while waited < max_wait do
        local status = proj:GetRenderJobStatus(jobId)
        if status then
            local pct = status.completionPercentage or 0
            local st = status.status or "Unknown"
            print(string.format("  Progress: %d%% - Status: %s", pct, st))
            
            if st == "Complete" then
                print("✅ Native render completed!")
                break
            elseif st == "Failed" then
                error("❌ Render failed: " .. (status.error or "Unknown error"))
            end
        end
        
        os.execute("timeout /t 2 /nobreak >nul")
        waited = waited + 2
    end
    
    if waited >= max_wait then
        error("⚠️  Render timeout after 30 minutes")
    end
    
    -- 清理渲染任务
    proj:DeleteAllRenderJobs()
    
    -- 不再使用 emit_ok，直接退出
    print("Lua script finished")
''')
        
        # ✅ 异步执行 Lua 脚本（不等待返回）
        logger.info("Starting native render (async)...")
        lua_thread = threading.Thread(
            target=self._execute_lua_async,
            args=(lua,),
            daemon=True
        )
        lua_thread.start()
        
        # ✅ 文件轮询：等待 .mov 文件生成
        logger.info(f"Waiting for output file: {temp_mov}")
        max_wait_seconds = 1800  # 30分钟
        check_interval = 5  # 每5秒检查一次
        waited = 0
        
        while waited < max_wait_seconds:
            if os.path.exists(temp_mov):
                # 验证文件大小（至少 1KB）
                file_size = os.path.getsize(temp_mov)
                if file_size > 1024:
                    logger.info(f"✅ Output file detected: {temp_mov} ({file_size/1024/1024:.1f}MB)")
                    break
            
            time.sleep(check_interval)
            waited += check_interval
            
            # 每30秒打印一次进度
            if waited % 30 == 0:
                logger.info(f"  Waiting... {waited}s elapsed")
        
        if waited >= max_wait_seconds:
            raise ResolveError(f"Native render timeout after {max_wait_seconds}s - file not found: {temp_mov}")
        
        # 等待 Lua 线程结束（最多再等30秒）
        lua_thread.join(timeout=30)
        
        # 检查临时 .mov 文件是否存在
        if not os.path.exists(temp_mov):
            raise ResolveError(f"Native render failed: {temp_mov} not found")
        
        mov_size = os.path.getsize(temp_mov)
        logger.info(f"Native render complete: {temp_mov} ({mov_size/1024/1024:.1f}MB)")
        
        # ✅ 使用 FFmpeg 快速转码为 MP4（无损，保留所有效果）
        # 转码命令: ffmpeg -y -i <temp_mov> -c copy <output_path>
        logger.info(f"Converting to MP4: {output_path}")
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", temp_mov, "-c", "copy", output_path]
        
        try:
            subprocess.run(ffmpeg_cmd, check=True, 
                          capture_output=True, timeout=60)
            
            if os.path.exists(output_path):
                mp4_size = os.path.getsize(output_path)
                logger.info(f"✅ MP4 conversion complete: {output_path} ({mp4_size/1024/1024:.1f}MB)")
                
                # 删除临时 .mov 文件
                try:
                    os.remove(temp_mov)
                    logger.info(f"Cleaned up temp file: {temp_mov}")
                except:
                    pass
                
                return output_path
            else:
                raise ResolveError("FFmpeg conversion failed: output file not created")
                
        except subprocess.TimeoutExpired:
            raise ResolveError("FFmpeg conversion timed out")
        except subprocess.CalledProcessError as e:
            stderr_msg = e.stderr.decode()[:500] if e.stderr else str(e)
            raise ResolveError(f"FFmpeg conversion failed: {stderr_msg}")
    
    def _execute_lua_async(self, lua_script: str):
        """异步执行 Lua 脚本（不等待返回结果）"""
        try:
            self._execute_lua(lua_script)
        except Exception as e:
            logger.warning(f"Async Lua execution warning: {e}")
            # 不抛出异常，让文件轮询机制处理
    
    # ----------------------------------------------------------------
    # 阶段2：代理媒体工作流
    # ----------------------------------------------------------------
    
    def create_proxy_media(self, project_name: str, proxy_height: int = 1080) -> dict[str, str]:
        """
        代理媒体工作流：将高分辨率素材（4K）自动降采样为 1080p 代理文件用于编辑。
        
        渲染时调用 restore_original_media() 自动替换回原始素材。
        
        Args:
            project_name: 项目名称
            proxy_height: 代理文件高度（默认 1080）
        
        Returns:
            {item_name: proxy_path} 映射
        """
        tl_info = self.get_timeline_info(project_name)
        items = tl_info.get("items", [])
        if not items:
            raise ResolveError(f"No items in timeline for project: {project_name}")
        
        media_map = self._media_path_map.get(project_name, {})
        
        proxy_dir = os.path.join(self._temp_dir, "proxies")
        os.makedirs(proxy_dir, exist_ok=True)
        
        if project_name not in self._proxy_media_map:
            self._proxy_media_map[project_name] = {}
        
        proxy_map = {}
        for item in items:
            item_name = item.get("name", "")
            original = media_map.get(item_name, "")
            
            # 在默认目录中查找素材
            if not original or not os.path.exists(original):
                for d in [r"C:\VinlandClips", r"C:\Users\Administrator\Desktop"]:
                    candidate = os.path.join(d, item_name)
                    if os.path.exists(candidate):
                        original = candidate
                        break
            
            if not original or not os.path.exists(original):
                logger.warning(f"Source media not found for: {item_name}, skipping proxy")
                continue
            
            proxy_path = os.path.join(proxy_dir, f"proxy_{item_name}")
            
            # 已存在则跳过（缓存复用）
            if not os.path.exists(proxy_path):
                # 降采样：宽度自适应保持比例，crf 28 快速生成
                cmd = (["ffmpeg", "-y", "-i", original,
                        "-vf", f"scale=-2:{proxy_height}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                        "-c:a", "aac", "-b:a", "128k", proxy_path])
                try:
                    subprocess.run(cmd, check=True,
                                   capture_output=True, timeout=300)
                    logger.info(f"Proxy created: {item_name} -> {proxy_height}p")
                except subprocess.CalledProcessError as e:
                    stderr_msg = e.stderr.decode(errors='ignore')[:300] if e.stderr else str(e)
                    logger.warning(f"Proxy creation failed for {item_name}: {stderr_msg}")
                    continue
            
            # 记录映射关系
            self._proxy_original_map[proxy_path] = original
            self._proxy_media_map[project_name][item_name] = original
            media_map[item_name] = proxy_path  # 编辑时使用代理
            proxy_map[item_name] = proxy_path
        
        self._media_path_map[project_name] = media_map
        logger.info(f"Proxy workflow enabled for {len(proxy_map)} clips")
        return proxy_map
    
    def restore_original_media(self, project_name: str) -> int:
        """
        恢复原始素材：渲染前将代理文件替换回原始高分辨率素材。
        
        Returns:
            恢复的素材数量
        """
        originals = self._proxy_media_map.get(project_name, {})
        if not originals:
            return 0
        
        media_map = self._media_path_map.get(project_name, {})
        restored = 0
        for item_name, original_path in originals.items():
            media_map[item_name] = original_path
            restored += 1
        
        self._media_path_map[project_name] = media_map
        logger.info(f"Restored {restored} original media files for rendering")
        return restored
    
    # ----------------------------------------------------------------
    # 阶段2：渲染缓存机制
    # ----------------------------------------------------------------
    
    def _get_cache_key(self, project_name: str, item: dict,
                       effect: ItemEffect | None = None) -> str:
        """基于片段参数生成缓存键（MD5 hash）"""
        import hashlib
        
        item_name = item.get("name", "")
        media_map = self._media_path_map.get(project_name, {})
        source_path = media_map.get(item_name, item_name)
        
        # 源文件修改时间（文件变更时缓存自动失效）
        source_mtime = 0
        if os.path.exists(source_path):
            source_mtime = os.path.getmtime(source_path)
        
        cdl = None
        cdl_map = self._cdl_config_map.get(project_name, {})
        idx = item.get("index", 0)
        if idx in cdl_map:
            c = cdl_map[idx]
            cdl = f"s{c.slope}o{c.offset}p{c.power}sat{c.saturation}"
        
        raw = json.dumps({
            'name': item_name,
            'duration': item.get('duration', 0),
            'effect': repr(effect) if effect else None,
            'cdl': cdl,
            'mtime': source_mtime,
        }, default=str)
        
        return hashlib.md5(raw.encode()).hexdigest()
    
    def _get_cached_segment(self, cache_key: str) -> str | None:
        """查找缓存的片段渲染结果"""
        cache_path = os.path.join(self._cache_dir, f"{cache_key}.mp4")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1024:
            return cache_path
        return None
    
    def _save_cached_segment(self, cache_key: str, segment_path: str):
        """保存片段渲染结果到缓存"""
        import shutil
        cache_path = os.path.join(self._cache_dir, f"{cache_key}.mp4")
        try:
            shutil.copy2(segment_path, cache_path)
        except Exception as e:
            logger.warning(f"Failed to cache segment: {e}")
    
    # ----------------------------------------------------------------
    # 阶段2：分段并行渲染
    # ----------------------------------------------------------------
    
    def _build_single_segment_command(self, project_name: str, item: dict,
                                       idx: int, output_path: str,
                                       media_map: dict[str, str],
                                       effects: dict[int, ItemEffect] | None,
                                       fps: float = 24.0) -> list[str]:
        """
        构建单片段渲染命令（简化版滤镜，避免 zoompan lerp 语法问题）
        """
        item_name = item.get("name", "")
        source = media_map.get(item_name, "")
        if not source or not os.path.exists(source):
            for d in [r"C:\VinlandClips", r"C:\Users\Administrator\Desktop"]:
                candidate = os.path.join(d, item_name)
                if os.path.exists(candidate):
                    source = candidate
                    break
        
        if not source or not os.path.exists(source):
            raise ResolveError(f"Source media not found: {item_name}")
        
        vf_parts = []
        
        # CDL 调色
        cdl = self._cdl_config_map.get(project_name, {}).get(idx)
        if cdl:
            avg_slope = (cdl.slope[0] + cdl.slope[1] + cdl.slope[2]) / 3.0
            avg_offset = (cdl.offset[0] + cdl.offset[1] + cdl.offset[2]) / 3.0
            avg_power = (cdl.power[0] + cdl.power[1] + cdl.power[2]) / 3.0
            contrast = max(0.5, min(3.0, avg_slope))
            brightness = max(-0.5, min(0.5, avg_offset * 0.8))
            gamma = max(0.4, min(2.5, avg_power))
            saturation = max(0.0, min(5.0, cdl.saturation))
            vf_parts.append(
                f"eq=contrast={contrast:.3f}:brightness={brightness:.3f}"
                f":gamma={gamma:.3f}:saturation={saturation:.3f}")
        
        # 效果（变速 + Ken Burns）
        effect = (effects or {}).get(idx)
        if effect:
            # Ken Burns 拉镜（zoompan，使用算术表达式而非 lerp，d=1 适配视频输入）
            if effect.ken_burns:
                kb = effect.ken_burns
                total_frames = max(int(item.get("duration", 84)), 1)
                sz = (kb.end_zoom - kb.start_zoom) / total_frames
                sx = (kb.end_x - kb.start_x) / total_frames
                sy = (kb.end_y - kb.start_y) / total_frames
                vf_parts.append(
                    f"zoompan=z='{kb.start_zoom}+{sz:.5f}*on'"
                    f":x='({kb.start_x}+{sx:.5f}*on)*(iw-iw/zoom)'"
                    f":y='({kb.start_y}+{sy:.5f}*on)*(ih-ih/zoom)'"
                    f":d=1:s=1920x1080:fps={int(fps)}")
            # 线性变速
            elif effect.speed_curve:
                sc = effect.speed_curve
                avg_speed = (sc.start_speed + sc.end_speed) / 2.0
                if abs(avg_speed - 1.0) > 0.01:
                    vf_parts.append(f"setpts=PTS/{avg_speed:.3f}")
        
        # 统一分辨率（确保 concat 拼接时尺寸一致）
        if not any(p.startswith("zoompan") for p in vf_parts):
            vf_parts.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
        
        vf = ",".join(vf_parts) if vf_parts else "null"
        codec_args = shlex.split(self._get_encoder_args(quality="fast"), posix=False)
        
        return (["ffmpeg", "-y", "-i", source, "-vf", vf]
                + codec_args + ["-an", "-r", str(int(fps)), output_path])
    
    def render_segments_parallel(self, project_name: str, output_path: str,
                                  effects: dict[int, ItemEffect] | None = None,
                                  max_workers: int = 4) -> str:
        """
        分段并行渲染：将时间线按片段拆分，多线程并行渲染，最后用 FFmpeg concat 拼接。
        
        优势：
        - 多片段并行处理，充分利用多核 CPU / GPU
        - 结合渲染缓存，相同参数片段不重复渲染
        
        Args:
            project_name: 项目名称
            output_path: 输出路径
            effects: 片段索引→ItemEffect 映射
            max_workers: 并行线程数（默认 4）
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        tl_info = self.get_timeline_info(project_name)
        items = tl_info.get("items", [])
        fps = tl_info.get("fps", 24.0)
        if not items:
            raise ResolveError("No items in timeline")
        
        media_map = self._media_path_map.get(project_name, {})
        
        seg_dir = os.path.join(self._temp_dir, "segments")
        os.makedirs(seg_dir, exist_ok=True)
        
        cache_hits = 0
        
        def render_one(item, i):
            nonlocal cache_hits
            idx = item.get("index", i + 1)
            
            # 检查缓存
            cache_key = self._get_cache_key(project_name, item, (effects or {}).get(idx))
            cached = self._get_cached_segment(cache_key)
            if cached:
                cache_hits += 1
                logger.info(f"Cache hit for segment {idx}: {item.get('name')}")
                return idx, cached
            
            # 渲染片段
            seg_path = os.path.join(seg_dir, f"seg_{idx:03d}.mp4")
            cmd = self._build_single_segment_command(
                project_name, item, idx, seg_path, media_map, effects, fps)
            subprocess.run(cmd, check=True,
                           capture_output=True, timeout=300)
            
            # 保存缓存
            self._save_cached_segment(cache_key, seg_path)
            return idx, seg_path
        
        # 并行渲染所有片段
        logger.info(f"Rendering {len(items)} segments in parallel (workers={max_workers})...")
        segment_results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(render_one, item, i) for i, item in enumerate(items)]
            for fut in as_completed(futures):
                idx, seg_path = fut.result()  # 异常会在此抛出
                segment_results[idx] = seg_path
        
        if cache_hits:
            logger.info(f"Cache hits: {cache_hits}/{len(items)} segments")
        
        # 按顺序拼接
        segments = [segment_results[item.get("index", i + 1)] for i, item in enumerate(items)]
        
        concat_list = os.path.join(seg_dir, "concat_list.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(f"file '{s}'\n")
        
        concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                      "-i", concat_list, "-c", "copy", output_path]
        subprocess.run(concat_cmd, check=True,
                       capture_output=True, timeout=120)
        
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            logger.info(f"Parallel render complete: {output_path} ({size_mb:.1f}MB)")
            return output_path
        
        raise ResolveError("Parallel render failed: output not created")
    
    # ================================================================
    # 阶段3：专业级高级剪辑功能（对标百万播放量 AMV/MAD）
    # ================================================================
    
    # 转场类型 → FFmpeg xfade 滤镜映射
    XFADE_TRANSITION_MAP = {
        'whip_pan': 'hlwind',      # 甩镜：水平风切
        'zoom': 'zoomin',          # 缩放转场
        'glitch': 'pixelize',      # 故障风：像素化
        'flash': 'fadewhite',      # 白闪
        'morph': 'dissolve',       # 溶解变形
        'iris_wipe': 'circlecrop', # 圆形光圈擦除
        'light_leak': 'hlslice',   # 漏光（近似）
        'film_burn': 'fadeblack',  # 胶片烧灼（近似）
    }
    
    # ----------------------------------------------------------------
    # 1. 精准节拍剪辑
    # ----------------------------------------------------------------
    
    def _get_media_duration(self, path: str) -> float | None:
        """获取媒体文件时长（秒）"""
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(r.stdout.strip())
        except Exception:
            return None
    
    def detect_beats(self, audio_path: str, bpm: float | None = None,
                     min_beat_interval: float = 0.3) -> list[float]:
        """
        提取音频节拍点。
        
        策略：
        - 提供 bpm → 用节拍网格生成（稳定可靠）
        - 否则用 FFmpeg silencedetect 检测静音断点作为切点
        
        Returns:
            节拍时间点列表（秒）
        """
        import re
        
        if bpm and bpm > 0:
            dur = self._get_media_duration(audio_path) or 60.0
            interval = 60.0 / bpm
            beats = []
            t = interval
            while t < dur:
                beats.append(round(t, 3))
                t += interval
            logger.info(f"Beat grid generated: {len(beats)} beats at {bpm} BPM")
            return beats
        
        cmd = ["ffmpeg", "-i", audio_path, "-af",
               f"silencedetect=noise=-30dB:d={min_beat_interval}", "-f", "null", "-"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        beats = [float(m) for m in re.findall(r'silence_end:\s*([\d.]+)', result.stderr)]
        
        # 去重排序 + 最小间隔过滤
        beats = sorted(set(beats))
        filtered, last = [], -999.0
        for b in beats:
            if b - last >= min_beat_interval:
                filtered.append(b)
                last = b
        
        logger.info(f"Detected {len(filtered)} beats via silencedetect")
        return filtered
    
    def beat_sync_edit(self, clip_paths: list[str], audio_path: str,
                       output_path: str, bpm: float | None = None,
                       transition: TransitionConfig | None = None) -> str:
        """
        精准节拍剪辑：自动对齐片段切换点到音频节拍。
        
        每个节拍区间对应一个片段（循环使用），可用转场连接。
        """
        beats = self.detect_beats(audio_path, bpm=bpm)
        if len(beats) < 2:
            raise ResolveError("Not enough beats detected (need >= 2)")
        
        import uuid
        seg_dir = os.path.join(self._temp_dir, f"beat_segments_{uuid.uuid4().hex[:8]}")
        os.makedirs(seg_dir, exist_ok=True)
        codec = self._get_encoder_args(quality="fast")
        
        segments = []
        clip_idx = 0
        for i in range(len(beats)):
            start = beats[i - 1] if i > 0 else 0.0
            seg_dur = beats[i] - start
            if seg_dur < 0.1:
                continue
            
            src = clip_paths[clip_idx % len(clip_paths)]
            clip_idx += 1
            seg_path = os.path.join(seg_dir, f"beat_{i:03d}.mp4")
            
            # 循环播放源片段并裁剪到节拍时长，统一 1080p
            vf_norm = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
                       "pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
            cmd = (["ffmpeg", "-y", "-stream_loop", "-1", "-i", src,
                    "-t", f"{seg_dur:.3f}", "-vf", vf_norm]
                   + shlex.split(codec, posix=False)
                   + ["-r", "24", "-an", seg_path])
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            segments.append(seg_path)
        
        logger.info(f"Beat sync: {len(segments)} segments cut to beats")
        
        # 转场连接或简单拼接
        if transition:
            return self.render_with_transitions(segments, output_path,
                                                [transition] * (len(segments) - 1))
        
        list_file = os.path.join(seg_dir, "concat_list.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(f"file '{s}'\n")
        
        # 混入节拍音频
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", list_file, "-i", audio_path,
               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
               "-shortest", output_path]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        
        if os.path.exists(output_path):
            logger.info(f"Beat sync edit complete: {output_path}")
            return output_path
        raise ResolveError("Beat sync edit failed")
    
    # ----------------------------------------------------------------
    # 2. 动态速度曲线（贝塞尔平滑）
    # ----------------------------------------------------------------
    
    def dynamic_speed_ramp(self, source_path: str, output_path: str,
                            control_points: list[tuple[float, float]] | None = None,
                            fps: int = 24) -> str:
        """
        动态速度曲线：基于控制点的平滑变速（类似 PR Time Remapping）。
        
        Args:
            control_points: [(t, speed), ...] t∈[0,1] 归一化时间，speed 为速度倍率
                            例如 [(0,1.0),(0.4,2.5),(0.6,2.5),(1,0.5)] 加速后减速
        
        实现：余弦平滑采样速度曲线 → 分段积分生成 setpts 嵌套表达式
        """
        import math
        
        if not control_points:
            control_points = [(0.0, 1.0), (0.5, 2.0), (1.0, 1.0)]
        
        duration = self._get_media_duration(source_path)
        if not duration:
            raise ResolveError(f"Cannot read duration: {source_path}")
        
        pts = sorted(control_points, key=lambda p: p[0])
        
        # 采样 32 个点的速度曲线（余弦平滑 = 平滑贝塞尔缓动）
        N = 32
        samples = []
        for i in range(N + 1):
            t = i / N
            j = 0
            while j < len(pts) - 2 and t > pts[j + 1][0]:
                j += 1
            (t0, s0), (t1, s1) = pts[j], pts[j + 1]
            dt = t1 - t0
            u = 0.0 if dt <= 1e-6 else max(0.0, min(1.0, (t - t0) / dt))
            u_smooth = (1 - math.cos(u * math.pi)) / 2  # 余弦缓动
            speed = s0 + (s1 - s0) * u_smooth
            samples.append((t * duration, max(0.05, speed)))
        
        # 分段积分：T(t) = 输出时间
        boundaries = []  # (t_end, T_acc, t_a, speed)
        T_acc = 0.0
        for k in range(len(samples) - 1):
            t_a, s_a = samples[k]
            t_b, _ = samples[k + 1]
            boundaries.append((t_b, T_acc, t_a, s_a))
            T_acc += (t_b - t_a) / s_a
        
        # 构建嵌套 if() 表达式（setpts 无 t 变量，用 PTS*TB 换算秒，结果除以 TB 转时间基）
        last_end, last_T, last_ta, last_s = boundaries[-1]
        expr = f"(({last_T:.4f}+({{T}}-{last_ta:.4f})/{last_s:.4f})/TB)"
        for t_b, T0, t_a, s_a in reversed(boundaries[:-1]):
            seg = f"({T0:.4f}+({{T}}-{t_a:.4f})/{s_a:.4f})"
            expr = f"if(lt({{T}},{t_b:.4f}),({seg}/TB),{expr})"
        expr = expr.replace("{T}", "PTS*TB")
        
        codec = self._get_encoder_args(quality="high")
        cmd = (["ffmpeg", "-y", "-i", source_path,
                "-vf", f"setpts='{expr}'"]
               + shlex.split(codec, posix=False)
               + ["-r", str(fps), "-an", output_path])
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        
        if os.path.exists(output_path):
            new_dur = self._get_media_duration(output_path)
            logger.info(f"Speed ramp complete: {duration:.1f}s -> {new_dur:.1f}s")
            return output_path
        raise ResolveError("Speed ramp failed")
    
    # ----------------------------------------------------------------
    # 3. 高级转场系统（8 种专业转场）
    # ----------------------------------------------------------------
    
    def apply_transition(self, clip_a: str, clip_b: str, output_path: str,
                         transition: str = "whip_pan", duration: float = 0.5) -> str:
        """对两个片段应用指定转场（基于 FFmpeg xfade）"""
        xfade = self.XFADE_TRANSITION_MAP.get(transition)
        if not xfade:
            raise ResolveError(
                f"Unknown transition: {transition}. "
                f"Available: {list(self.XFADE_TRANSITION_MAP.keys())}")
        
        da = self._get_media_duration(clip_a) or 3.0
        offset = max(0.1, da - duration)
        codec = self._get_encoder_args(quality="fast")
        
        # 统一分辨率 + 时间戳重置 + xfade
        fc = (
            f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[a];"
            f"[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[b];"
            f"[a][b]xfade=transition={xfade}:duration={duration}:offset={offset:.3f}[v]")
        
        cmd = (["ffmpeg", "-y", "-i", clip_a, "-i", clip_b,
                "-filter_complex", fc, "-map", "[v]"]
               + shlex.split(codec, posix=False)
               + ["-an", output_path])
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        
        if os.path.exists(output_path):
            return output_path
        raise ResolveError(f"Transition '{transition}' failed")
    
    def render_with_transitions(self, clip_paths: list[str], output_path: str,
                                 transitions: list[TransitionConfig] | None = None) -> str:
        """
        多片段转场链式渲染：依次对相邻片段应用转场。
        
        Args:
            transitions: 长度为 len(clip_paths)-1 的转场配置列表，
                         每个配置对应第 i 和第 i+1 个片段之间的转场
        """
        if len(clip_paths) < 2:
            raise ResolveError("Need at least 2 clips for transitions")
        
        if not transitions:
            transitions = [TransitionConfig()] * (len(clip_paths) - 1)
        if len(transitions) < len(clip_paths) - 1:
            transitions = list(transitions) + [TransitionConfig()] * (
                len(clip_paths) - 1 - len(transitions))
        
        # 预处理：统一所有片段为 1080p 无音频（xfade 要求尺寸一致）
        # ✅ 每次调用使用唯一目录，避免跨调用缓存冲突（旧 norm 文件被误复用）
        import uuid
        pre_dir = os.path.join(self._temp_dir, f"transition_clips_{uuid.uuid4().hex[:8]}")
        os.makedirs(pre_dir, exist_ok=True)
        codec = self._get_encoder_args(quality="fast")
        
        normalized = []
        for i, src in enumerate(clip_paths):
            norm_path = os.path.join(pre_dir, f"norm_{i:03d}.mp4")
            vf_norm = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
                       "pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
            cmd = (["ffmpeg", "-y", "-i", src, "-vf", vf_norm]
                   + shlex.split(codec, posix=False)
                   + ["-r", "24", "-an", norm_path])
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            normalized.append(norm_path)
        
        # 迭代应用转场
        current = normalized[0]
        for i in range(1, len(normalized)):
            tc = transitions[i - 1]
            tmp_out = os.path.join(pre_dir, f"chain_{i:03d}.mp4")
            self.apply_transition(current, normalized[i], tmp_out,
                                  transition=tc.type, duration=tc.duration)
            current = tmp_out
            logger.info(f"Transition {i}/{len(normalized)-1} applied: {tc.type}")
        
        # 移动到最终输出位置
        import shutil
        shutil.move(current, output_path)
        logger.info(f"Transition chain complete: {output_path}")
        return output_path
    
    # ----------------------------------------------------------------
    # 4. 色彩科学工作流（LUT / 色轮 / 色彩匹配）
    # ----------------------------------------------------------------
    
    def apply_lut_file(self, project_name: str, item_index: int, cube_path: str) -> bool:
        """
        应用 .cube LUT 文件（FFmpeg 渲染时通过 lut3d 滤镜应用）。
        Resolve 侧的 apply_lut() 另行处理原生渲染路径。
        """
        if not os.path.exists(cube_path):
            raise ResolveError(f"LUT file not found: {cube_path}")
        
        self._lut_file_map.setdefault(project_name, {})[item_index] = cube_path
        logger.info(f"LUT tracked for item {item_index}: {os.path.basename(cube_path)}")
        return True
    
    def apply_color_wheel(self, project_name: str, item_index: int,
                          config: ColorWheelConfig) -> bool:
        """
        三路色轮调整（shadows/midtones/highlights）。
        FFmpeg 渲染时通过 colorbalance 滤镜应用。
        """
        self._colorwheel_map.setdefault(project_name, {})[item_index] = config
        logger.info(f"Color wheel tracked for item {item_index}")
        return True
    
    def _get_avg_rgb(self, path: str, at_fraction: float = 0.5) -> tuple[float, float, float]:
        """提取指定位置的单帧平均 RGB（scale=1:1 技巧，返回 0~1）"""
        dur = self._get_media_duration(path) or 0
        ss = max(0.0, dur * at_fraction - 0.1)
        cmd = ['ffmpeg', '-ss', f'{ss:.2f}', '-i', path, '-frames:v', '1',
               '-vf', 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            data = r.stdout[-3:] if r.stdout else b''
            if len(data) >= 3:
                return (data[0] / 255.0, data[1] / 255.0, data[2] / 255.0)
        except Exception as e:
            logger.warning(f"avg RGB extraction failed: {e}")
        return (0.5, 0.5, 0.5)
    
    def match_color(self, source_path: str, reference_path: str) -> ColorWheelConfig:
        """
        自动色彩匹配：计算源与参考片段的平均色彩差异，
        生成可用于 apply_color_wheel 的校正配置。
        """
        src_rgb = self._get_avg_rgb(source_path)
        ref_rgb = self._get_avg_rgb(reference_path)
        
        midtones = tuple(
            max(-0.5, min(0.5, (r - s) * 0.5))
            for r, s in zip(ref_rgb, src_rgb)
        )
        logger.info(f"Color match: src={src_rgb}, ref={ref_rgb}, correction={midtones}")
        return ColorWheelConfig(midtones=midtones)
    
    # ----------------------------------------------------------------
    # 5. 关键帧动画系统
    # ----------------------------------------------------------------
    
    def build_keyframe_expression(self, keyframes: list[Keyframe],
                                   mode: str = "linear",
                                   time_var: str = "t") -> str:
        """
        将关键帧列表构建为 FFmpeg 时间表达式。
        
        Args:
            mode: linear（线性）/ ease（余弦缓动）/ bezier（平滑曲线）/ hold（保持）
            time_var: 时间变量名（setpts/rotate 用 t；zoompan 用 on/fps）
        """
        if not keyframes:
            return "1.0"
        kfs = sorted(keyframes, key=lambda k: k.time)
        if len(kfs) == 1:
            return f"{kfs[0].value:.4f}"
        
        T = time_var
        expr = f"{kfs[-1].value:.4f}"
        for i in range(len(kfs) - 2, -1, -1):
            k0, k1 = kfs[i], kfs[i + 1]
            dt = max(k1.time - k0.time, 1e-6)
            dv = k1.value - k0.value
            u = f"(({T}-{k0.time:.4f})/{dt:.4f})"
            
            if mode == "hold":
                seg = f"{k0.value:.4f}"
            elif mode == "ease":
                seg = f"({k0.value:.4f}+{dv:.4f}*((1-cos({u}*3.14159265))/2))"
            elif mode == "bezier":
                # 三次贝塞尔 smoothstep: u²(3-2u)
                seg = f"({k0.value:.4f}+{dv:.4f}*({u}*{u}*(3-2*{u})))"
            else:  # linear
                seg = f"({k0.value:.4f}+{dv:.4f}*{u})"
            
            expr = f"if(lt({T},{k1.time:.4f}),{seg},{expr})"
        return expr
    
    def set_keyframe_animation(self, source_path: str, output_path: str,
                                animations: dict[str, list[Keyframe]],
                                mode: str = "linear", fps: int = 24) -> str:
        """
        关键帧动画系统：对 zoom/x/y/rotation/opacity 设置多关键帧动画。
        
        Args:
            animations: {'zoom': [Keyframe...], 'x': ..., 'rotation': ..., 'opacity': ...}
                        zoom: 缩放倍率; x/y: 0~1 位置; rotation: 角度; opacity: 0~1
            mode: linear / ease / bezier / hold
        """
        vf_parts = []
        
        # zoom/x/y 通过 zoompan 表达式实现（zoompan 无 t/fps 变量，用 on/字面fps 计算时间）
        if any(k in animations for k in ('zoom', 'x', 'y')):
            tvar = f"on/{fps}"
            z_expr = self.build_keyframe_expression(animations.get('zoom', []), mode, tvar) \
                if animations.get('zoom') else "1.0"
            x_expr = self.build_keyframe_expression(animations.get('x', []), mode, tvar) \
                if animations.get('x') else "0.5"
            y_expr = self.build_keyframe_expression(animations.get('y', []), mode, tvar) \
                if animations.get('y') else "0.5"
            vf_parts.append(
                f"zoompan=z='{z_expr}'"
                f":x='({x_expr})*(iw-iw/zoom)'"
                f":y='({y_expr})*(ih-ih/zoom)'"
                f":d=1:s=1920x1080:fps={fps}")
        
        # rotation 通过 rotate 滤镜表达式实现（rotate 用帧号 n/字面fps 近似时间）
        if animations.get('rotation'):
            r_expr = self.build_keyframe_expression(animations['rotation'], mode, f"n/{fps}")
            vf_parts.append(f"rotate=a='({r_expr})*PI/180':fillcolor=black")
        
        # opacity 通过 geq 亮度缩放近似（对黑色背景混合）
        if animations.get('opacity'):
            o_expr = self.build_keyframe_expression(animations['opacity'], mode, f"n/{fps}")
            vf_parts.append(
                f"geq=r='clip(r(X,Y)*({o_expr}),0,255)'"
                f":g='clip(g(X,Y)*({o_expr}),0,255)'"
                f":b='clip(b(X,Y)*({o_expr}),0,255)'")
            logger.warning("Opacity keyframes use geq approximation (slow)")
        
        if 'blur' in animations:
            logger.warning("Blur keyframes not supported in FFmpeg path "
                           "(gblur sigma has no expression support)")
        
        if not vf_parts:
            raise ResolveError("No supported animation attributes provided")
        
        codec = self._get_encoder_args(quality="high")
        cmd = (["ffmpeg", "-y", "-i", source_path, "-vf", ",".join(vf_parts)]
               + shlex.split(codec, posix=False)
               + ["-an", output_path])
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        
        if os.path.exists(output_path):
            logger.info(f"Keyframe animation complete: {output_path}")
            return output_path
        raise ResolveError("Keyframe animation failed")
    
    def render_timeline(self, project_name: str, output_path: str,
                        preset: str = "H.264 Master", use_ffmpeg: bool = True,
                        effects: dict[int, ItemEffect] | None = None) -> str:
        """
        渲染当前时间线。
        
        Args:
            project_name: 项目名称
            output_path: 输出文件路径
            preset: 渲染预设（仅 use_ffmpeg=False 时使用）
            use_ffmpeg: 是否使用 FFmpeg 渲染（推荐，更快更可靠）
            effects: 片段特效映射 {item_index: ItemEffect}
        """
        if use_ffmpeg:
            return self._render_with_ffmpeg(project_name, output_path, effects)
        else:
            return self._render_with_resolve(project_name, output_path, preset)
    
    # ----------------------------------------------------------------
    # 页面切换
    # ----------------------------------------------------------------
    
    def switch_page(self, page: str) -> bool:
        """切换页面 (edit/color/fusion/deliver)。

        2026-09-24 返回值诚实性审计：原实现无条件 return True。
        真机探针结论：`resolve:OpenPage(...)` **不返回任何结果** ——
        对合法页（"edit"）与非法页（"__bogus__"）**都返回 nil**，故无法据返回值判定成败。
        现按 void_api 处理：调用未报错即返回 True，但日志明确标注"未经效果验证"，
        不再把 nil 误判成失败（第一版写死 `ok == true` 曾把成功页切换报成 False）。
        """
        self._require_available()
        lua = self._wrap_lua(f'''
    local resolve = Resolve()
    local ok = resolve:OpenPage("{page}")
    emit_ok({{ok = ok, ret_type = type(ok), completed = true, page = "{page}"}})
''')
        return self._ok_from(self._execute_lua(lua), f"switch_page({page})",
                             void_api=True)
    
    # ----------------------------------------------------------------
    # 高级操作
    # ----------------------------------------------------------------
    
    def apply_preset_grade(self, project_name: str, item_index: int,
                           preset_name: str) -> bool:
        """
        应用预设调色方案。
        preset_name: "cinematic_warm" | "cinematic_cool" | "high_contrast" | 
                     "film_look" | "bleach_bypass" | "teal_orange"
        """
        presets = {
            "cinematic_warm": CDLConfig(
                slope=(1.1, 1.05, 0.95), offset=(0.02, 0.01, -0.01),
                power=(1.0, 1.0, 1.05), saturation=1.1
            ),
            "cinematic_cool": CDLConfig(
                slope=(0.95, 1.0, 1.1), offset=(-0.01, 0.0, 0.03),
                power=(1.05, 1.0, 0.95), saturation=0.95
            ),
            "high_contrast": CDLConfig(
                slope=(1.3, 1.3, 1.3), offset=(-0.05, -0.05, -0.05),
                power=(0.9, 0.9, 0.9), saturation=1.2
            ),
            "film_look": CDLConfig(
                slope=(1.05, 1.0, 0.98), offset=(0.01, 0.005, 0.02),
                power=(1.1, 1.05, 0.95), saturation=0.9
            ),
            "bleach_bypass": CDLConfig(
                slope=(1.2, 1.2, 1.2), offset=(0.0, 0.0, 0.0),
                power=(1.3, 1.3, 1.3), saturation=0.5
            ),
            "teal_orange": CDLConfig(
                slope=(1.1, 1.0, 0.9), offset=(-0.02, 0.0, 0.05),
                power=(1.0, 1.05, 0.95), saturation=1.15
            ),
        }
        
        if preset_name not in presets:
            raise ValueError(f"Unknown preset: {preset_name}. Available: {list(presets.keys())}")
        
        return self.apply_cdl(project_name, "", item_index, presets[preset_name])
    
    def full_pipeline(self, project_name: str, timeline_name: str,
                      media_files: list[str],
                      grades: dict[int, CDLConfig] | None = None,
                      speeds: dict[int, float] | None = None,
                      transforms: dict[int, TransformConfig] | None = None,
                      lut_map: dict[int, str] | None = None,
                      effects: dict[int, 'ItemEffect'] | None = None,
                      output_path: str = "",
                      render_preset: str = "H.264 Master") -> dict:
        """
        完整管线：导入 → 时间线 → 调色 → 变速 → 变换 → 渲染
        """
        result = {"steps": []}
        
        # Step 1: 创建项目 + 时间线
        logger.info("Step 1: Creating timeline with media...")
        tl_info = self.create_timeline_with_media(project_name, timeline_name, media_files)
        result["steps"].append({"step": "create_timeline", "status": "ok", "data": tl_info})
        
        # Step 2: 应用调色
        if grades:
            for idx, cdl in grades.items():
                logger.info(f"Step 2: Applying CDL to item {idx}...")
                self.apply_cdl(project_name, timeline_name, idx, cdl)
                result["steps"].append({"step": "cdl", "item": idx, "status": "ok"})
        
        # Step 3: 应用 LUT
        if lut_map:
            for idx, lut_path in lut_map.items():
                logger.info(f"Step 3: Applying LUT to item {idx}...")
                self.apply_lut(project_name, timeline_name, idx, lut_path)
                result["steps"].append({"step": "lut", "item": idx, "status": "ok"})
        
        # Step 4: 变速
        if speeds:
            for idx, speed in speeds.items():
                logger.info(f"Step 4: Setting speed for item {idx} to {speed}x...")
                self.set_speed(project_name, idx, speed)
                result["steps"].append({"step": "speed", "item": idx, "speed": speed, "status": "ok"})
        
        # Step 5: 变换
        if transforms:
            for idx, tf in transforms.items():
                logger.info(f"Step 5: Applying transform to item {idx}...")
                self.set_transform(project_name, idx, tf)
                result["steps"].append({"step": "transform", "item": idx, "status": "ok"})
        
        # Step 6: 渲染
        if output_path:
            logger.info(f"Step 6: Rendering to {output_path}...")
            rendered = self.render_timeline(project_name, output_path, render_preset, effects=effects)
            result["steps"].append({"step": "render", "output": rendered, "status": "ok"})
        
        result["project"] = project_name
        result["timeline"] = timeline_name
        result["status"] = "ok"
        return result


# ============================================================================
# 异常类
# ============================================================================

class ResolveError(Exception):
    """Resolve 自动化错误"""
    pass


# ============================================================================
# 便捷函数
# ============================================================================

def quick_grade_and_render(media_files: list[str], output_path: str,
                           preset_grade: str = "cinematic_warm",
                           speed: float = 1.0,
                           project_name: str = "AutoGrade_Render") -> dict:
    """快速调色+渲染一体化函数"""
    engine = ResolveAutomationEngine()
    
    return engine.full_pipeline(
        project_name=project_name,
        timeline_name="Main_Timeline",
        media_files=media_files,
        grades={i: _get_preset(preset_grade) for i in range(1, len(media_files) + 1)},
        speeds={i: speed for i in range(1, len(media_files) + 1)} if speed != 1.0 else None,
        output_path=output_path
    )


def _get_preset(name: str) -> CDLConfig:
    """获取预设调色"""
    presets = {
        "cinematic_warm": CDLConfig(slope=(1.1, 1.05, 0.95), offset=(0.02, 0.01, -0.01),
                                     power=(1.0, 1.0, 1.05), saturation=1.1),
        "cinematic_cool": CDLConfig(slope=(0.95, 1.0, 1.1), offset=(-0.01, 0.0, 0.03),
                                     power=(1.05, 1.0, 0.95), saturation=0.95),
        "high_contrast": CDLConfig(slope=(1.3, 1.3, 1.3), offset=(-0.05, -0.05, -0.05),
                                    power=(0.9, 0.9, 0.9), saturation=1.2),
        "film_look": CDLConfig(slope=(1.05, 1.0, 0.98), offset=(0.01, 0.005, 0.02),
                                power=(1.1, 1.05, 0.95), saturation=0.9),
    }
    return presets.get(name, CDLConfig())
