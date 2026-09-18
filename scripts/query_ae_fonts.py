#!/usr/bin/env python3
"""查询AE可用字体列表(PostScript名)"""
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"

def send(code, wait=30):
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding='utf-8')
    cmd = {'command':'runScript','args':{'code':code},
           'timestamp':datetime.now().isoformat(),'status':'pending'}
    BRIDGE_CMD.write_text(json.dumps(cmd,ensure_ascii=False), encoding='utf-8')
    time.sleep(1)
    for _ in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding='utf-8'))
            if r.get('status') != 'waiting' and 'result' in r:
                inner = r.get('result', {})
                if isinstance(inner, dict) and inner.get('success') and 'data' in inner:
                    return inner['data'].get('result', '')
                return json.dumps(r, ensure_ascii=False)
        except:
            pass
    return 'TIMEOUT'

# 查询目标字体的PostScript名
target_fonts = [
    "Impact", "Arial Black", "SimHei", "KaiTi", "LiSu", "STXingkai",
    "STHupo", "STCaiyun", "OCR A Extended", "DIN Next LT Pro",
    "Microsoft YaHei", "Noto Sans SC", "Noto Serif SC", "Yu Gothic",
    "Stencil", "Bradley Hand ITC", "Rage Italic", "STKaiti",
    "STXinwei", "YouYuan", "DengXian", "Source Sans 3",
    "Alibaba PuHuiTi 3.0", "SimFang", "FZShuTi", "Consolas",
    "Bahnschrift", "Bodoni MT", "Cooper Black", "Brush Script MT",
    "Mistral", "Palace Script MT", "Vladimir Script", "Niagara Engraved",
    "Showcard Gothic", "Snap ITC", "Curlz MT", "Chiller",
    "Harlow Solid Italic", "Broadway", "Playbill"
]

# 用AE的fonts对象查询
code = '''(function(){
var result = [];
var targetNames = ''' + json.dumps(target_fonts) + ''';
for(var i=0; i<targetNames.length; i++){
    var name = targetNames[i];
    try{
        // 尝试通过app.fonts获取(CEP) 或通过创建临时文字层测试
        var found = false;
        // 方法: 搜索系统字体
        result.push({requested: name, status: "check"});
    }catch(e){
        result.push({requested: name, status: "error", msg: e.toString()});
    }
}
// 直接列出所有可用字体(通过临时文字层)
var testComp = app.project.items.addComp("_font_test",100,100,1,1,30);
var testLayer = testComp.layers.addText("test");
var textProp = testLayer.property("Source Text");
var textDoc = textProp.value;
// 获取字体列表 - AE没有直接API列出所有字体,但我们可以测试特定字体
var fonts_to_test = ["Impact","Arial Black","SimHei","KaiTi","LiSu","STXingkai","STHupo","STCaiyun","OCR A Extended","DINNextLTPro-Bold","Microsoft YaHei","NotoSansSC-VF","NotoSerifSC-VF","YuGothic-Bold","Stencil","BradleyHandITC","RageItalic","STKaiti","STXinwei","YouYuan","DengXian-Bold","SourceSans3-Regular","AlibabaPuHuiTi-3-45-Light","SimFang","FZShuTi","Consolas","Bahnschrift","BodoniMT","CooperBlack","BrushScriptMT","Mistral","PalaceScriptMT","VladimirScript","NiagaraEngraved","ShowcardGothic","SnapITC","CurlzMT","Chiller","HarlowSolidItalic","Broadway","Playbill"];
var available = [];
for(var fi=0; fi<fonts_to_test.length; fi++){
    try{
        textDoc.font = fonts_to_test[fi];
        textProp.setValue(textDoc);
        // 如果设置成功,读回看是否匹配
        var readBack = textProp.value.font;
        available.push({name:fonts_to_test[fi], actual:readBack, ok:(readBack==fonts_to_test[fi])});
    }catch(e){
        available.push({name:fonts_to_test[fi], error:e.toString()});
    }
}
testComp.remove();
return JSON.stringify({total:available.length, fonts:available});
})();'''

print("Querying AE for available fonts...")
res = send(code, 30)
try:
    data = json.loads(res)
    fonts = data.get('fonts', [])
    print(f"\nTotal tested: {len(fonts)}")
    print(f"\n{'Font Name':<35} {'Actual':<35} {'OK'}")
    print("-" * 80)
    ok_count = 0
    for f in fonts:
        if 'error' in f:
            print(f"  {f['name']:<33} ERROR: {f['error'][:30]}")
        else:
            status = "OK" if f.get('ok') else f"DIFF({f.get('actual','')})"
            if f.get('ok'):
                ok_count += 1
            print(f"  {f['name']:<33} {f.get('actual',''):<33} {status}")
    print(f"\nAvailable: {ok_count}/{len(fonts)}")
except Exception as e:
    print(f"Parse error: {e}")
    print(f"Raw: {res[:500]}")
