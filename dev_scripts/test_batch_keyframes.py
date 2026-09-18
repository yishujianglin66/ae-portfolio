#!/usr/bin/env python3
"""Test batch keyframe writing via executeAtomScript"""
import json

from ae_mcp_client import AECommandClient

c = AECommandClient(signature_enabled=False, timeout=30)

# Build ExtendScript for batch keyframe write
script = (
    'var compName = "E2E_VinlandSaga";'
    'var layerName = "MainVideo";'
    'var comp = null;'
    'for (var i = 1; i <= app.project.numItems; i++) {'
    '    if (app.project.item(i).name === compName &&'
    '        app.project.item(i) instanceof CompItem) {'
    '        comp = app.project.item(i); break;'
    '    }'
    '}'
    'if (!comp) { '
    '    JSON.stringify({error: "Comp not found"});'
    '} else {'
    '    var layer = null;'
    '    for (var j = 1; j <= comp.numLayers; j++) {'
    '        if (comp.layer(j).name === layerName) {'
    '            layer = comp.layer(j); break;'
    '        }'
    '    }'
    '    if (!layer) {'
    '        JSON.stringify({error: "Layer not found"});'
    '    } else {'
    '        var written = 0;'
    '        var kfs = ['
    '            {prop: "Scale", t: 0.0, v: [100,100], e: "easeOut"},'
    '            {prop: "Scale", t: 2.0, v: [120,120], e: "easeInOut"},'
    '            {prop: "Scale", t: 4.0, v: [100,100], e: "easeIn"},'
    '            {prop: "Opacity", t: 0.0, v: 100, e: "linear"},'
    '            {prop: "Opacity", t: 5.0, v: 80, e: "linear"},'
    '            {prop: "Opacity", t: 10.0, v: 100, e: "linear"},'
    '            {prop: "Rotation", t: 0.0, v: 0, e: "linear"},'
    '            {prop: "Rotation", t: 10.0, v: 15, e: "easeOut"}'
    '        ];'
    '        for (var k = 0; k < kfs.length; k++) {'
    '            var kf = kfs[k];'
    '            var prop = layer.property(kf.prop);'
    '            if (prop) {'
    '                prop.setValueAtTime(kf.t, kf.v);'
    '                if (kf.e !== "linear") {'
    '                    var idx = prop.nearestKeyIndex(kf.t);'
    '                    if (idx > 0) {'
    '                        var eIn = new KeyframeEase(0,33);'
    '                        var eOut = new KeyframeEase(0,33);'
    '                        if (kf.e === "easeIn") { eIn = new KeyframeEase(0,75); }'
    '                        else if (kf.e === "easeOut") { eOut = new KeyframeEase(0,75); }'
    '                        else if (kf.e === "easeInOut") { eIn = new KeyframeEase(0,75); eOut = new KeyframeEase(0,75); }'
    '                        try { prop.setTemporalEaseAtKey(idx,[eIn],[eOut]); } catch(ex) {}'
    '                    }'
    '                }'
    '                written++;'
    '            }'
    '        }'
    '        JSON.stringify({success: true, written: written, total: kfs.length});'
    '    }'
    '}'
)

print("=== Batch Keyframe Write Test ===")
r = c.send_command("executeAtomScript", {"script": script})
print(json.dumps(r, indent=2, ensure_ascii=False))
