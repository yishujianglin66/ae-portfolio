// pr_readback.jsx — PR 时间线脚本级回读（P3-2 交付物）
// 遍历所有序列：轨道/clip/速度/Motion关键帧，写入 .premiere-mcp-bridge/pr_readback.txt
var _out = [];
function _log(s) { _out.push(String(s)); }
var _TPS = 254016000000;
function _sec(t) {
    try {
        if (t && typeof t === 'object' && typeof t.seconds === 'number') return t.seconds;
        if (typeof t === 'number') return t / _TPS;
    } catch (eX) {}
    return -1;
}
try {
    var proj = app.project;
    _log('PROJECT=' + proj.name);
    var nSeq = proj.sequences.length;
    _log('SEQ_COUNT=' + nSeq);
    for (var i = 0; i < nSeq; i++) {
        var seq = proj.sequences[i];
        var durS = -1;
        try { durS = _sec(seq.end); } catch (eD) {}
        _log('[SEQ ' + i + '] name=' + seq.name + ' dur=' + durS.toFixed(3) + ' fps=' + seq.framerate);
        var vt = seq.videoTracks;
        _log('  VTRACKS=' + vt.numTracks);
        for (var v = 0; v < vt.numTracks; v++) {
            var tr = vt[v];
            var clips = tr.clips;
            var locked = false;
            try { locked = tr.isLocked(); } catch (eL) {}
            _log('  [V' + v + '] clips=' + clips.numItems + ' locked=' + locked);
            for (var c = 0; c < clips.numItems; c++) {
                var cl = clips[c];
                var spd = -1;
                try { spd = cl.getSpeed(); } catch (eS) {}
                var st = -1, en = -1;
                try { st = _sec(cl.start); en = _sec(cl.end); } catch (eT) {}
                _log('    clip[' + c + '] name=' + cl.name + ' type=' + cl.type +
                     ' start=' + st.toFixed(3) + ' end=' + en.toFixed(3) + ' speed=' + spd);
                try {
                    var comps = cl.components;
                    for (var k = 0; k < comps.numItems; k++) {
                        var comp = comps[k];
                        var isMotion = false;
                        try { isMotion = (comp.matchName === 'AE.ADBE Motion'); } catch (eM) {}
                        if (!isMotion) {
                            try { isMotion = (comp.displayName.indexOf('Motion') >= 0 || comp.displayName.indexOf('\u8FD0\u52A8') >= 0); } catch (eM2) {}
                        }
                        if (isMotion) {
                            var props = comp.properties;
                            for (var p = 0; p < props.numItems; p++) {
                                var pr2 = props[p];
                                try {
                                    if (pr2.isTimeVarying && pr2.isTimeVarying()) {
                                        var nk = 0;
                                        try { nk = pr2.getKeys().length; } catch (eK) {}
                                        _log('      kf: ' + pr2.displayName + ' keys=' + nk);
                                    }
                                } catch (eP) {}
                            }
                        } else {
                            try {
                                _log('      comp: ' + comp.displayName + ' (' + comp.matchName + ')');
                            } catch (eCN) {}
                        }
                    }
                } catch (eC) {}
            }
        }
        var at = seq.audioTracks;
        _log('  ATRACKS=' + at.numTracks);
        for (var a = 0; a < at.numTracks; a++) {
            var atr = at[a];
            var aclips = atr.clips;
            _log('  [A' + a + '] clips=' + aclips.numItems);
            for (var ac = 0; ac < aclips.numItems; ac++) {
                var acl = aclips[ac];
                var ast = -1, aen = -1;
                try { ast = _sec(acl.start); aen = _sec(acl.end); } catch (eT2) {}
                _log('    aclip[' + ac + '] name=' + acl.name + ' start=' + ast.toFixed(3) + ' end=' + aen.toFixed(3));
            }
        }
    }
    _log('RB_STATUS=OK');
} catch (e) {
    _log('RB_STATUS=ERROR ' + e.toString());
}
var _f = new File('C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge/pr_readback.txt');
_f.encoding = 'UTF-8';
_f.open('w');
_f.write(_out.join('\r\n'));
_f.close();
'RB lines=' + _out.length;
