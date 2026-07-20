#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault')
from ae_mcp_client import AECommandClient

c = AECommandClient(signature_enabled=False, timeout=600)

script = '''
var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {
    if (app.project.item(i).name === "VinlandSaga_Battle_V4" && app.project.item(i) instanceof CompItem) {
        comp = app.project.item(i); break;
    }
}
if (!comp) { JSON.stringify({error: "Comp not found"}); }

var outputPath = "D:/AE-Work/output/VinlandSaga_Battle_V4.mp4";

for (var j = 1; j <= app.project.renderQueue.numItems; j++) {
    if (app.project.renderQueue.item(j).name === comp.name) {
        app.project.renderQueue.item(j).remove();
    }
}

var rq = app.project.renderQueue.items.add(comp);
var om = rq.outputModule(1);
om.file = new File(outputPath);
rq.render = true;
app.project.renderQueue.render();

JSON.stringify({status: "rendering", output: outputPath});
'''

print("开始渲染...")
result = c.send_command('executeAtomScript', {'script': script})
print(f"渲染结果: {result}")