#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault')
from ae_mcp_client import AECommandClient

c = AECommandClient(signature_enabled=False, timeout=60)

script = '''
var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {
    if (app.project.item(i).name === "VinlandSaga_Battle_V4" && app.project.item(i) instanceof CompItem) {
        comp = app.project.item(i); break;
    }
}
if (!comp) { JSON.stringify({error: "Comp not found"}); }
var ctrl = comp.layer("Audio Controller");
var keys = 0;
for(var i=1;i<=ctrl.property("Effects").numProperties;i++){
    keys += ctrl.property("Effects").property(i).property("Slider").numKeys;
}
JSON.stringify({ctrlLayer:true, totalKeys:keys});
'''

print(c.send_command('executeAtomScript', {'script': script}))