// ============================================================
// V11 自包含执行脚本 - 调色+粒子+3D三大系统
// 用法: AfterFX.exe -r wrapper_v11.jsx
// ============================================================

(function() {
    var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
    var V11_SCRIPT = PROJ_ROOT + "/scripts/vinland_saga_v11.jsx";
    var ENERGY_JSON = PROJ_ROOT + "/energy_data_v8.json";
    var AEP_PATH = "D:/AE-Work/VinlandSaga_V11.aep";
    var COMP_NAME = "VinlandSaga_Battle_V11";
    var LOG = PROJ_ROOT + "/.ae-mcp-bridge/wrapper_v11.log";

    function log(msg) {
        try {
            var f = new File(LOG);
            f.encoding = "UTF-8";
            f.open("a");
            var d = new Date();
            var ts = d.getFullYear() + "-" +
                (d.getMonth()+1) + "-" + d.getDate() +
                " " + d.getHours() + ":" + d.getMinutes() +
                ":" + d.getSeconds();
            f.write("[" + ts + "] " + msg + "\n");
            f.close();
        } catch(e) {}
    }

    function readJSON(path) {
        var f = new File(path);
        if (!f.exists) return null;
        f.encoding = "UTF-8";
        f.open("r");
        var txt = f.read();
        f.close();
        try { return JSON.parse(txt); } catch(e) {
            log("JSON parse error: " + e.toString());
            return null;
        }
    }

    function readFile(path) {
        var f = new File(path);
        if (!f.exists) return null;
        f.encoding = "UTF-8";
        f.open("r");
        var txt = f.read();
        f.close();
        return txt;
    }

    log("=== V11 Wrapper started ===");

    log("Step 1: Reading V11 script...");
    var v11code = readFile(V11_SCRIPT);
    if (!v11code) {
        log("ERROR: Cannot read V11 script");
        return;
    }
    log("V11 script loaded: " + v11code.length + " chars");

    try {
        eval(v11code);
        log("V11 script eval'd successfully");
    } catch(e) {
        log("V11 eval error: " + e.toString());
        return;
    }

    log("Step 2: Creating composition...");
    try {
        if (typeof main === "function") {
            var result = main();
            log("main() result: " + result);
        }
    } catch(e) {
        log("main() error: " + e.toString());
        return;
    }

    log("Step 3: Reading energy data...");
    var energy = readJSON(ENERGY_JSON);
    if (!energy) {
        log("ERROR: Cannot read energy data");
    } else {
        log("Energy data: " + energy.frame_times.length + " frames");

        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem &&
                item.name === COMP_NAME) {
                comp = item;
                break;
            }
        }
        if (!comp) {
            log("ERROR: Comp not found: " + COMP_NAME);
        } else {
            log("Comp found, layers: " + comp.numLayers);

            var ctrl = null;
            try { ctrl = comp.layer("Audio Controller"); } catch(e) {}
            if (!ctrl) {
                log("ERROR: Audio Controller not found");
            } else {
                var sliders = {
                    "Global Energy": energy.global_energy,
                    "LowFreq Energy": energy.low_energy,
                    "MidFreq Energy": energy.mid_energy,
                    "HighFreq Energy": energy.high_energy
                };
                var times = energy.frame_times;
                var totalKF = 0;

                for (var name in sliders) {
                    if (!sliders.hasOwnProperty(name)) continue;
                    var data = sliders[name];
                    log("Writing: " + name + " (" +
                        data.length + " frames)");

                    var eff = null;
                    for (var e = 1; e <= ctrl.property("Effects").numProperties; e++) {
                        if (ctrl.property("Effects").property(e).name === name) {
                            eff = ctrl.property("Effects").property(e);
                            break;
                        }
                    }
                    if (!eff) {
                        eff = ctrl.property("Effects")
                            .addProperty("Slider Control");
                        eff.name = name;
                    }
                    var sp = eff.property("Slider");

                    var chunkSize = 100;
                    for (var cs = 0; cs < data.length; cs += chunkSize) {
                        var ce = Math.min(cs + chunkSize, data.length);
                        for (var k = cs; k < ce; k++) {
                            try {
                                sp.setValueAtTime(
                                    times[k], data[k] * 100
                                );
                                totalKF++;
                            } catch(e) {}
                        }
                    }
                    log("  " + name + " done");
                }
                log("Total keyframes: " + totalKF);
            }
        }
    }

    log("Step 4: Saving project...");
    try {
        var f = new File(AEP_PATH);
        app.project.save(f);
        log("Project saved: " + AEP_PATH);
    } catch(e) {
        log("Save error: " + e.toString());
    }

    log("=== V11 Wrapper completed ===");
})();
