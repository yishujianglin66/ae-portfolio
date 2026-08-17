# -*- coding: utf-8 -*-
"""
把 2026-08-12 实测经验写入长期记忆库 (MemoryStore, %APPDATA%/AE-Knowledge-Vault/memory.db)
类别约定: gui_automation / video_processing / sampling_strategy / engine_performance
可用 SearchMemory 按 title 检索 (nlu_parser 消费同一 store)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.memory_store import memory_store

EXPERIENCES = [
    dict(
        category="gui_automation",
        key="topaz_uia_full_workflow",
        content=dict(
            title="Topaz Video AI 全自动操作 (UIA)", software="Topaz Video AI Pro v7.2.0.3",
            method="UIAutomation InvokePattern + Win32 + SendKeys, 全部实测通过",
            flow="浏览视频->双击ListItem->开始编辑->4K增强&60帧预设->导出视频->Browse目录->开始导出",
            pitfalls=[
                "PID每次重启变化, 需先查询",
                "DPI150%导致坐标点击偏(用InvokePattern替代)",
                "PowerShell5.1需UTF-8 BOM防中文乱码",
                "文件对话框是Qt内嵌, 属Topaz进程",
                "渲染期(CPU持续增长)绝不触发UI, 会中断",
                "预设是Text控件但支持InvokePattern",
            ],
            render_time="120fps/2334帧 约30min (RTX4060)",
            output="120fps/2334帧/213.6MB/aac保留",
        ),
        tags=["topaz", "gui", "uia", "automation"],
        confidence=0.95,
    ),
    dict(
        category="video_processing",
        key="douyin_120fps_vs_48fps_compression",
        content=dict(
            title="抖音压缩: 120fps源比48fps源保留更多信息 (实测)",
            metric="VMAF vs 120fps真实基准: from120=89.87 vs from48=68.10 (差21.77)",
            finding="120fps AI补帧源含真实中间帧信息, 抖音压缩降采样到60fps后仍保留更多细节",
            caveat="120fps源被压缩到30fps时信息损失大(VMAF 78.84), 但优于48fps源",
            conclusion="上传抖音用120fps源更清晰; ffmpeg锐化是最大抗压缩杠杆(VMAF 99.99)",
        ),
        tags=["douyin", "120fps", "compression", "vmaf"],
        confidence=0.9,
    ),
    dict(
        category="sampling_strategy",
        key="ssim_vs_uniform_sampling",
        content=dict(
            title="SSIM自适应采样 vs 均匀采样 排序对比 (v23规划)",
            metric="Spearman秩相关0.661, SSIM保留率4.1%(1922->79帧)",
            finding="SSIM采样去重有效(剔除静止帧), 高光段两法均排第1(可信)",
            performance_bug="indices_within逐段重复全片SSIM扫描 465s->0s (已修, _is_full_scan标志+mem_cache)",
            conclusion="v23主采样切SSIM, 均匀留作fallback",
        ),
        tags=["ssim", "sampling", "highlight", "v23"],
        confidence=0.9,
    ),
    dict(
        category="engine_performance",
        key="rife_local_ffmpeg_pipeline",
        content=dict(
            title="RIFE本地补帧链路 (external/rife + torch+CUDA)",
            deps="skvideo(patch np.float/np.int for numpy2) + moviepy2 + CUDA",
            bugs=[
                "--model传文件而非目录(load_model拼{path}/flownet.pkl)",
                "产物命名{stem}_{mult}X_{fps}fps.mp4写src目录(非repo)",
                "subprocess cwd=repo需绝对化路径",
            ],
            perf="24fps->48fps 929帧 99s; 产物独立不覆盖原片",
        ),
        tags=["rife", "frame-interp", "ffmpeg", "pipeline"],
        confidence=0.9,
    ),
]

def main():
    n = 0
    for e in EXPERIENCES:
        mid = memory_store.remember(
            category=e["category"], key=e["key"],
            content=e["content"], tags=e.get("tags"), confidence=e.get("confidence", 0.5),
        )
        print(f"  [OK] [{e['category']}] {e['key']} -> id={mid}")
        n += 1
    # 验证可检索
    print(f"\n共写入 {n} 条经验. 验证检索:")
    for e in EXPERIENCES:
        got = memory_store.recall(e["category"], e["key"])
        title = (got.content or {}).get("title", "?") if got else "NOT FOUND"
        print(f"  recall [{e['category']}/{e['key']}] -> {title}")

if __name__ == "__main__":
    main()
