# -*- coding: utf-8 -*-
"""使用MasterCut Agent渲染run53v43 premium v2特效版

调用render_cut工具，传入139个专业插件特效配置，重新渲染整片视频。
输出: output/unified_run53/run53v43_premium_v2.mp4
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.mastercut_agent import MasterCutAgent

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "output" / "unified_run53" / "production_report.json"
EFFECTS_JSON = ROOT / "output" / "unified_run53" / "run53v43_effects_premium_v2.json"
OUTPUT_DIR = ROOT / "output" / "unified_run53"
BGM_PATH = r"D:\AE-Work\音频素材库\BGM\1_from10s.mp3"


def extract_sources_from_report():
    """从production_report.json提取镜头源文件列表"""
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    segments = data["segments"]
    
    # 去重获取唯一源文件
    sources = []
    seen = set()
    for seg in segments:
        src = seg.get("source")
        if src and src not in seen:
            sources.append(src)
            seen.add(src)
    
    print(f"[INFO] Extracted {len(sources)} unique source files:")
    for i, src in enumerate(sources[:5], 1):
        print(f"  [{i}] {src}")
    if len(sources) > 5:
        print(f"  ... and {len(sources) - 5} more")
    
    return sources


def main():
    if not EFFECTS_JSON.exists():
        print(f"[ERROR] Effects config not found: {EFFECTS_JSON}")
        return 1
    
    if not Path(BGM_PATH).exists():
        print(f"[ERROR] BGM not found: {BGM_PATH}")
        print("[INFO] Please update BGM_PATH in script to correct location")
        return 1
    
    # 加载特效配置
    effects = json.loads(EFFECTS_JSON.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(effects)} premium plugin effects")
    
    # 提取源文件
    sources = extract_sources_from_report()
    
    # 初始化Agent
    agent = MasterCutAgent()
    
    # 调用render_cut
    print(f"\n[MasterCut Agent] Starting render with premium effects...")
    print(f"  Sources: {len(sources)} files")
    print(f"  Effects: {len(effects)} configs")
    print(f"  BGM: {BGM_PATH}")
    print(f"  Output Dir: {OUTPUT_DIR}")
    
    try:
        result = agent.execute(
            "render_cut",
            sources=sources,
            bgm_path=BGM_PATH,
            output_dir=str(OUTPUT_DIR),
            output_name="run53v43_premium_v2.mp4",
            duration=30.0,
            theme="燃向混剪: 铺垫→蓄力→爆发→收尾 (Premium Plugin Edition)",
            style="amv_highenergy_premium",
            enable_ae=True,
            effects=effects
        )
        
        # ToolResult has .data dict with success/output_video fields
        if hasattr(result, 'data') and result.data.get("success"):
            output_video = result.data.get("output_video")
            print(f"\n[OK] Render completed!")
            print(f"  Output: {output_video}")
            if output_video and Path(output_video).exists():
                size_mb = Path(output_video).stat().st_size / (1024*1024)
                print(f"  Size: {size_mb:.1f} MB")
            print(f"  Effects Applied: {result.data.get('effects_applied', len(effects))}")
            return 0
        else:
            print(f"\n[FAIL] Render failed")
            if hasattr(result, 'data'):
                print(f"  Details: {result.data}")
            return 1
            
    except Exception as e:
        print(f"\n[ERROR] Exception during render: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
