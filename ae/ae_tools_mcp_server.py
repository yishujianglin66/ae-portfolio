"""
AE 统一 MCP Server
====================
整合所有AE模块为统一MCP工具接口：
- aerender渲染
- nexrender模板渲染
- 性能监控
- 渲染队列
- 模板管理
- Watch Folder
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 统一路径引导：注入 rendering/tools/web 等子目录，修复跨目录 import
# （ae_render_engine 等依赖位于 rendering/，不在本脚本所在的根目录）
from fastmcp import FastMCP

import bootstrap  # noqa: E402

mcp = FastMCP("AE-Tools")


# ===== aerender渲染 =====
@mcp.tool()
def ae_render(project: str, composition: str, output: str, output_format: str = "h264", reuse_ae: bool = True) -> dict:
    """通过aerender命令行渲染AE合成"""
    from ae_render_engine import AERenderEngine
    engine = AERenderEngine()
    job = engine.render(
        project=project, composition=composition, output=output,
        output_format=output_format, reuse_ae=reuse_ae,
    )
    return {"job_id": job.job_id, "status": job.status.value, "output": job.output_path}


@mcp.tool()
def ae_render_status(job_id: str) -> dict:
    """查询渲染任务状态"""
    from ae_render_engine import AERenderEngine
    engine = AERenderEngine()
    job = engine.get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress,
        "error": job.error,
    }


# ===== nexrender =====
@mcp.tool()
def nex_render(template: str, composition: str, output: str, assets_json: str = "[]") -> dict:
    """通过nexrender数据驱动渲染（assets_json: [{src,type,layer_name}]）"""
    from nexrender_integration import NexAsset, NexrenderIntegration
    nex = NexrenderIntegration()
    assets = [NexAsset(**a) for a in json.loads(assets_json)]
    job = nex.create_job(template=template, composition=composition, output=output, assets=assets)
    nex.render(job)
    return {"job_id": job.job_id, "status": job.status.value}


# ===== 性能监控 =====
@mcp.tool()
def ae_monitor_system() -> dict:
    """获取系统和AE进程性能快照"""
    from ae_performance_monitor import AEPerformanceMonitor
    mon = AEPerformanceMonitor()
    sys_info = mon.get_system_info()
    ae_info = mon.get_ae_info()
    return {
        "system": {
            "total_gb": sys_info.total_memory_gb,
            "used_gb": sys_info.used_memory_gb,
            "free_gb": sys_info.free_memory_gb,
            "mem_percent": sys_info.memory_percent,
            "cpu_percent": sys_info.cpu_percent,
        },
        "ae": ae_info.__dict__ if ae_info else None,
        "alert": mon.check_memory_alert(),
    }


@mcp.tool()
def ae_clear_cache() -> dict:
    """清理AE磁盘缓存"""
    from ae_performance_monitor import AEPerformanceMonitor
    mon = AEPerformanceMonitor()
    success = mon.clear_ae_cache()
    return {"cleared": success}


# ===== 渲染队列 =====
@mcp.tool()
def queue_add(project: str, composition: str, output: str, priority: str = "NORMAL") -> dict:
    """添加渲染任务到队列"""
    from ae_render_queue import Priority, RenderQueueManager
    qm = RenderQueueManager()
    qm.load_persisted()
    pri = Priority[priority.upper()] if priority.upper() in Priority.__members__ else Priority.NORMAL
    tid = qm.add_task(project=project, composition=composition, output=output, priority=pri)
    return {"task_id": tid, "pending": qm.pending_count}


@mcp.tool()
def queue_status() -> dict:
    """获取渲染队列状态"""
    from ae_render_queue import RenderQueueManager
    qm = RenderQueueManager()
    qm.load_persisted()
    return qm.get_report()


@mcp.tool()
def queue_cancel(task_id: str) -> dict:
    """取消队列任务"""
    from ae_render_queue import RenderQueueManager
    qm = RenderQueueManager()
    qm.load_persisted()
    ok = qm.cancel_task(task_id)
    return {"cancelled": ok}


# ===== 模板管理 =====
@mcp.tool()
def template_list(category: str = "", tag: str = "") -> dict:
    """列出AEP模板"""
    from aep_template_manager import AEPTemplateManager
    tm = AEPTemplateManager()
    templates = tm.list_templates(category=category or None, tag=tag or None)
    return {
        "total": len(templates),
        "templates": [
            {"id": t.template_id, "name": t.name, "category": t.category, "tags": t.tags}
            for t in templates
        ]
    }


@mcp.tool()
def template_register(project_path: str, name: str, category: str = "general", tags_json: str = "[]") -> dict:
    """注册AEP模板"""
    from aep_template_manager import AEPTemplateManager
    tm = AEPTemplateManager()
    tid = tm.register_template(project_path, name, category=category, tags=json.loads(tags_json))
    return {"template_id": tid, "name": name}


# ===== Watch Folder =====
@mcp.tool()
def watch_add_rule(folder: str, file_types_json: str = '["any"]', action: str = "import") -> dict:
    """添加文件夹监控规则"""
    from ae_watch_folder import FileType, WatchFolderTrigger, WatchRule
    wf = WatchFolderTrigger()
    types = [FileType(t) for t in json.loads(file_types_json)]
    wf.add_rule(WatchRule(folder=folder, file_types=types, action=action))
    return {"folder": folder, "rules": len(wf.get_rules())}


@mcp.tool()
def watch_status() -> dict:
    """获取Watch Folder状态"""
    from ae_watch_folder import WatchFolderTrigger
    wf = WatchFolderTrigger()
    return {
        "rules": len(wf.get_rules()),
        "stats": wf.get_stats(),
    }


# ===== 启动 =====
if __name__ == "__main__":
    mcp.run(transport="stdio")
