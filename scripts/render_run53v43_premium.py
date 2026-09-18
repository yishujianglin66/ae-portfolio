# -*- coding: utf-8 -*-
"""使用MasterCut Agent渲染run53v43 premium v2特效版

调用render_cut工具，传入139个专业插件特效配置，重新渲染整片视频。
输出: output/unified_run53/polish/run53_master.mp4

退出码: 0=全部特效已上  2=部分(有类型无 RECIPES 实现)  1=失败
用法: python scripts/render_run53v43_premium.py [--dry-run]
      --dry-run 只验证 schema→plan→JSX 链路, 不占用 AE (其他会话在用 AE 时用)
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
    dry_run = "--dry-run" in sys.argv[1:]

    if not EFFECTS_JSON.exists():
        print(f"[ERROR] Effects config not found: {EFFECTS_JSON}")
        return 1

    if not dry_run and not Path(BGM_PATH).exists():
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
    print("\n[MasterCut Agent] Starting render with premium effects..."
          + ("  [DRY-RUN — 不碰 AE]" if dry_run else ""))
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
            effects=effects,
            effects_dry_run=dry_run,
        )
    except Exception as e:
        print(f"\n[ERROR] Exception during render: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ToolResult 的载荷字段是 .output — 旧代码读 result.data, hasattr() 恒为 False,
    # 于是无论渲染真实结果如何都走 FAIL 分支, 且从不读取产出。
    # 另 result.success 仅表示"工具未抛异常", 不等于渲染成功 —— 必须看链路级字段。
    out = result.output or {}
    req = int(out.get("effects_requested", len(effects)))
    applied = int(out.get("effects_applied", 0))
    unmapped = int(out.get("effects_unmapped", 0))
    skipped = int(out.get("effects_skipped", 0))

    print("\n" + "=" * 62)
    print("特效执行对账 (只报实测数, 不做任何 len(effects) 兜底)")
    print("=" * 62)
    print(f"  请求   : {req}")
    print(f"  已生效 : {applied}")
    print(f"  无实现 : {unmapped}  (类型在 RECIPES 中无 matchName)")
    print(f"  己跳过 : {skipped}  (时间区间非法/未知类型)")
    val = out.get("effects_validation") or {}
    if val and not val.get("valid", True):
        errs = val.get("errors", [])
        print(f"  schema 校验 : {len(errs)} 条不通过")
        for er in errs[:5]:
            print(f"    #{er.get('effect_index')}: {er.get('error')}")
    if unmapped:
        print("  无实现明细:")
        for t, v in sorted((out.get("unmapped_types") or {}).items(),
                           key=lambda kv: -kv[1].get("count", 0)):
            print(f"    {t}: {v.get('count')} 条 — {v.get('reason')}")

    if not result.success:
        print(f"\n[FAIL] 工具执行异常: {result.error}")
        return 1
    if out.get("effects_success") is not True:
        print(f"\n[FAIL] 特效链路未成功 (stage={out.get('effects_stage')}): "
              f"{out.get('effects_error')}")
        return 1
    if applied == 0:
        print("\n[FAIL] 0 条特效生效 — 不得视为成功")
        return 1

    if applied < req:
        print(f"\n[PARTIAL] {applied}/{req} 生效 — 补齐 RECIPES 映射前不算完整交付")
        print("  详见 tmp/effects_injection_report.json")
        return 2

    vid = out.get("effects_output") or out.get("video_path")
    if dry_run:
        print(f"\n[DRY-RUN OK] {out.get('effects_note') or '链路已验证'}")
        jsx = ROOT / "tmp" / "master_dryrun_run53.jsx"
        print(f"  JSX 产物: {jsx}"
              + (f" ({jsx.stat().st_size:,} B)" if jsx.exists() else " (未生成?)"))
        return 0
    if vid and Path(vid).exists():
        size_mb = Path(vid).stat().st_size / (1024 * 1024)
        print(f"\n[OK] {vid}  ({size_mb:.1f} MB)")
        print(f"  {out.get('effects_note') or ''}")
        return 0

    print(f"\n[FAIL] 链路报成功但产物缺失: {vid}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
