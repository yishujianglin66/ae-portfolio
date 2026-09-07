#!/usr/bin/env python3
"""全量预设渲染 v2 - 修复动画丢失问题
根因: 旧版用eval()执行模板, 但模板内app.project.activeItem未指向新合成
修复: 直接注入模板代码, 替换activeItem为comp变量引用

用法: py -3.12 scripts/render_all_presets_v2.py [--batch N] [--start M]
  --batch N : 每批渲染N个(默认20)
  --start M : 从第M个开始(默认0)
  --create-only : 只创建合成不渲染
  --verify-one : 创建第一个预设后验证动画属性
"""
import json, time, sys, os, re, argparse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# === 路径 ===
ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
CONFIG = ROOT / "config" / "text_animation_presets.json"
OUTPUT = Path(r"D:\AE-Work\output\ALL_PRESETS_SHOWCASE.mp4")

DURATION = 3.0
FPS = 30
WIDTH, HEIGHT = 1920, 1080

CATEGORY_TEXTS = {
    "kinetic_typography": "KINETIC",
    "cyberpunk": "CYBER",
    "cinematic": "CINEMA",
    "social_media": "SOCIAL",
    "3d_title": "3D TITLE",
    "advanced_kinetic": "ADVANCED",
    "anime_fx": "IMPACT",
    "vfx_presets": "VFX",
    "3d_title_extended": "EXTENDED",
    "cinema_titles": "CHAPTER",
    "art_typography": "ART",
}


def load_all_presets():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    presets = []
    for cat_key, cat_data in cfg["categories"].items():
        for p in cat_data.get("presets", []):
            presets.append({
                "category": cat_key,
                "id": p["id"],
                "name": p.get("name", p["id"]),
                "jsx_template": p.get("jsx_template", ""),
                "parameters": p.get("parameters", []),
            })
    return presets


def fill_template(template, parameters):
    """用默认参数填充模板占位符, 强制duration=3"""
    jsx = template
    for param in parameters:
        key = "{{" + param["name"] + "}}"
        val = param.get("default", "")
        # 强制覆盖duration为3秒
        if param["name"] == "duration":
            val = 3.0
        if isinstance(val, bool):
            jsx = jsx.replace(key, "true" if val else "false")
        elif isinstance(val, str):
            jsx = jsx.replace(key, val)
        else:
            jsx = jsx.replace(key, str(val))
    # 清理未替换的占位符
    jsx = re.sub(r'\{\{(\w+)\}\}', '0', jsx)
    return jsx


def gen_create_jsx_v2(preset, text):
    """v2: 直接注入模板代码, 不用eval"""
    pid = preset["id"]
    comp_name = f"P3s_{pid}"
    jsx_inner = fill_template(preset["jsx_template"], preset["parameters"])

    # === 核心修复: 根据模板类型选择注入方式 ===
    if "COMP_REF" in jsx_inner:
        # 3D标题模式: 模板使用COMP_REF占位符 → 替换为comp
        preset_code = jsx_inner.replace("COMP_REF", "comp")
    elif "app.project.activeItem" in jsx_inner:
        # activeItem模式: 替换为comp变量引用
        preset_code = jsx_inner.replace("app.project.activeItem", "comp")
    else:
        # 其他模式: 设置activeItem后直接执行
        preset_code = "app.project.activeItem = comp; " + jsx_inner

    # 构建完整JSX - 直接拼接, 不用eval
    wrapper = '''(function() {
    try {
        // 删除同名旧合成
        for (var i = app.project.items.length; i >= 1; i--) {
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "''' + comp_name + '''") {
                app.project.item(i).remove();
            }
        }
        var comp = app.project.items.addComp("''' + comp_name + '''", ''' + str(WIDTH) + ''', ''' + str(HEIGHT) + ''', 1, ''' + str(DURATION) + ''', ''' + str(FPS) + ''');
        comp.bgColor = [0.02, 0.02, 0.04];
        // 创建文字图层(模板需要搜索此图层)
        var L = comp.layers.addText("''' + text + '''");
        L.name = "\\u6807\\u9898\\u6587\\u5b57";
        L.position.setValue([960, 540]);
        // 直接执行预设动画代码(非eval)
        var _presetResult = (function(){
            ''' + preset_code + '''
        })();
        return JSON.stringify({status:"success", comp:"''' + comp_name + '''", preset:_presetResult});
    } catch(e) {
        return JSON.stringify({status:"error", error:e.toString(), line:e.line});
    }
})();'''
    return wrapper, comp_name


def send_bridge(code, wait=30):
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except:
            pass
    return {"success": False, "error": "timeout"}


def parse_result(r):
    """解析Bridge返回, 返回(success, detail)"""
    inner = r.get("result", {})
    if isinstance(inner, dict):
        if inner.get("success") and "data" in inner:
            result_str = inner["data"].get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        return True, parsed
                    elif parsed.get("status") == "error":
                        return False, parsed.get("error", "unknown")
                except:
                    pass
            return True, result_str
        elif inner.get("success"):
            return True, "ok"
        elif "error" in inner:
            return False, inner["error"]
    return False, str(r)[:100]


def verify_animation(comp_name):
    """验证合成内是否有动画属性(关键帧/表达式/动画器)"""
    code = '''(function(){
    var comp = null;
    for(var i=1;i<=app.project.items.length;i++){
        var it=app.project.item(i);
        if(it instanceof CompItem && it.name=="''' + comp_name + '''"){comp=it;break;}
    }
    if(!comp) return JSON.stringify({error:"comp not found"});
    var info = {layers:comp.numLayers, animators:0, keyframes:0, expressions:0, effects:0};
    for(var li=1;li<=comp.numLayers;li++){
        var layer=comp.layer(li);
        try{
            var tp=layer.property("ADBE Text Properties");
            var anims=tp.property("ADBE Text Animators");
            if(anims) info.animators += anims.numProperties;
        }catch(e){}
        try{
            var tg=layer.property("ADBE Transform Group");
            for(var ki=1;ki<=tg.numProperties;ki++){
                var prop=tg.property(ki);
                if(prop.numKeys>0) info.keyframes += prop.numKeys;
                try{if(prop.expression && prop.expression.length>0) info.expressions++;}catch(e2){}
            }
        }catch(e){}
        try{
            var fx=layer.property("ADBE Effect Parade");
            if(fx) info.effects += fx.numProperties;
        }catch(e){}
    }
    return JSON.stringify(info);
})();'''
    r = send_bridge(code, 15)
    ok, detail = parse_result(r)
    # detail可能是JSON字符串或dict
    if isinstance(detail, str):
        try:
            return json.loads(detail)
        except:
            return {"raw": detail}
    elif isinstance(detail, dict):
        return detail
    return {"error": str(detail)}


def build_master_and_render(presets, created_comps):
    """创建总合成 + 渲染"""
    print("\n[Phase 2] Building master comp & rendering...")

    # 创建总合成JSX
    master_jsx = '''(function(){
    try{
      var comps=[];
      for(var i=1;i<=app.project.items.length;i++){
        var it=app.project.item(i);
        if(it instanceof CompItem && it.name.indexOf("P3s_")==0){
          comps.push(it);
        }
      }
      if(comps.length==0){return JSON.stringify({status:"error",msg:"no P3s_ comps"});}
      comps.sort(function(a,b){return a.name<b.name?-1:1;});
      var seg=3.0;
      var total=comps.length*seg;
      // 删除旧总合成
      for(var j=app.project.items.length;j>=1;j--){
        var jt=app.project.item(j);
        if(jt instanceof CompItem && jt.name=="ALL_PRESETS_SHOWCASE"){jt.remove();}
      }
      var master=app.project.items.addComp("ALL_PRESETS_SHOWCASE",1920,1080,1,total,30);
      master.bgColor=[0,0,0];
      for(var k=0;k<comps.length;k++){
        var layer=master.layers.add(comps[k]);
        layer.startTime=k*seg;
        layer.outPoint=(k+1)*seg;
      }
      return JSON.stringify({status:"success",comps:comps.length,duration:total});
    }catch(e){return JSON.stringify({status:"error",msg:e.toString()});}
    })();'''

    print("  Creating master comp...")
    r = send_bridge(master_jsx, 30)
    ok, detail = parse_result(r)
    if not ok:
        print(f"  FAILED to create master: {detail}")
        return False
    print(f"  Master comp: {detail}")

    # 查询可用模板
    tpl_jsx = '''(function(){
    try{
      var master=null;
      for(var i=1;i<=app.project.items.length;i++){
        var it=app.project.item(i);
        if(it instanceof CompItem && it.name=="ALL_PRESETS_SHOWCASE"){master=it;break;}
      }
      if(!master){return JSON.stringify({err:"no master"});}
      var rq=app.project.renderQueue.items.add(master);
      var tpls=rq.outputModule(1).templates;
      rq.remove();
      return JSON.stringify({templates:tpls});
    }catch(e){return JSON.stringify({err:e.toString()});}
    })();'''
    r = send_bridge(tpl_jsx, 15)
    ok, detail = parse_result(r)
    mp4_tpl = None
    if ok and isinstance(detail, str):
        try:
            info = json.loads(detail)
            for t in info.get("templates", []):
                if "h.264" in t.lower() or "mp4" in t.lower():
                    mp4_tpl = t
                    break
        except:
            pass
    elif ok and isinstance(detail, dict):
        for t in detail.get("templates", []):
            if "h.264" in t.lower() or "mp4" in t.lower():
                mp4_tpl = t
                break

    print(f"  Output template: {mp4_tpl or 'default'}")

    # 删除旧输出
    if OUTPUT.parent.exists():
        for f in OUTPUT.parent.glob("ALL_PRESETS_SHOWCASE.*"):
            try:
                f.unlink()
            except:
                pass
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # 渲染
    out_unix = str(OUTPUT).replace("\\", "/")
    tpl_apply = f'om.applyTemplate("{mp4_tpl}");' if mp4_tpl else ''
    render_jsx = '''(function(){
    try{
      var master=null;
      for(var i=1;i<=app.project.items.length;i++){
        var it=app.project.item(i);
        if(it instanceof CompItem && it.name=="ALL_PRESETS_SHOWCASE"){master=it;break;}
      }
      if(!master){return JSON.stringify({status:"error",msg:"master not found"});}
      var rq=app.project.renderQueue.items.add(master);
      var om=rq.outputModule(1);
      ''' + tpl_apply + '''
      om.file=new File("''' + out_unix + '''");
      app.project.renderQueue.render();
      return JSON.stringify({status:"rendered",duration:master.duration});
    }catch(e){return JSON.stringify({status:"error",msg:e.toString(),line:e.line});}
    })();'''

    print("  Rendering (this takes several minutes for 5+ min video)...")
    r = send_bridge(render_jsx, 1200)
    ok, detail = parse_result(r)
    if ok:
        print(f"  Render complete: {detail}")
        return True
    else:
        print(f"  Render FAILED: {detail}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--create-only", action="store_true")
    parser.add_argument("--verify-one", action="store_true")
    args = parser.parse_args()

    presets = load_all_presets()
    total = len(presets)

    print(f"\n{'='*60}")
    print(f"  ALL PRESETS RENDER v2 (animation fix)")
    print(f"  {total} presets x {DURATION}s = {total*DURATION/60:.1f} min video")
    print(f"  FIX: direct code injection (no eval)")
    print(f"{'='*60}\n")

    # === Phase 1: 创建带动画的合成 ===
    end_idx = min(args.start + args.batch, total)
    created = []
    failed = []

    for i in range(args.start, end_idx):
        p = presets[i]
        text = CATEGORY_TEXTS.get(p["category"], "TEXT")
        print(f"  [{i+1}/{total}] {p['id']}...", end=" ", flush=True)

        jsx, comp_name = gen_create_jsx_v2(p, text)
        r = send_bridge(jsx, 25)
        ok, detail = parse_result(r)

        if ok:
            print("OK")
            created.append(comp_name)
        else:
            err_msg = str(detail)[:80]
            print(f"FAIL ({err_msg})")
            failed.append({"id": p["id"], "error": err_msg})

    print(f"\n  Created: {len(created)}/{end_idx - args.start}")
    if failed:
        print(f"  Failed ({len(failed)}):")
        for f in failed[:5]:
            print(f"    - {f['id']}: {f['error']}")

    # === 验证第一个合成的动画 ===
    if args.verify_one and created:
        print(f"\n[Verify] Checking animation in {created[0]}...")
        info = verify_animation(created[0])
        print(f"  Result: {json.dumps(info, ensure_ascii=False)}")
        animators = info.get("animators", 0)
        keyframes = info.get("keyframes", 0)
        effects = info.get("effects", 0)
        if animators > 0 or keyframes > 0 or effects > 0:
            print(f"  ANIMATION CONFIRMED: {animators} animators, {keyframes} keyframes, {effects} effects")
        else:
            print(f"  WARNING: No animation detected!")

    # === Phase 2: 总合成 + 渲染 ===
    if not args.create_only and len(created) > 0:
        build_master_and_render(presets, created)

    # === Summary ===
    print(f"\n{'='*60}")
    print(f"  DONE - {len(created)} comps created")
    if OUTPUT.exists():
        mb = OUTPUT.stat().st_size / (1024*1024)
        print(f"  Output: {OUTPUT} ({mb:.1f} MB)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
