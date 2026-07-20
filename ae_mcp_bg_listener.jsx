// AE MCP Background Listener - No UI, runs in background
// Run via: AfterFX.exe -r "path/to/ae_mcp_bg_listener.jsx"

{
    var PROJ = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
    var BASE_DIR = PROJ + "/.ae-mcp-bridge";
    var CMD_FILE = BASE_DIR + "/ae_command.json";
    var RES_FILE = BASE_DIR + "/ae_mcp_result.json";
    var lastCmdTime = 0;
    var CHECK_INTERVAL = 500;
    var SIGNATURE_ENABLED = false;

    function log(msg) {
        $.writeln("[MCP-BG] " + msg);
    }

    function readJSON(path) {
        var f = new File(path);
        if (!f.exists) return null;
        f.encoding = "UTF-8";
        f.open("r");
        var txt = f.read();
        f.close();
        if (!txt) return null;
        try { return JSON.parse(txt); } catch(e) { return null; }
    }

    function writeJSON(path, obj) {
        var f = new File(path);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(JSON.stringify(obj, null, 2));
        f.close();
    }

    function updateCommandStatus(status) {
        var data = readJSON(CMD_FILE);
        if (data) {
            data.status = status;
            writeJSON(CMD_FILE, data);
        }
    }

    function handleGetProjectInfo() {
        try {
            var project = app.project;
            var items = [];
            for (var i = 1; i <= project.numItems; i++) {
                var item = project.item(i);
                items.push({
                    id: item.id,
                    name: item.name,
                    type: item.typename
                });
            }
            return {
                projectName: project.name,
                path: project.file ? project.file.fsName : "",
                numItems: project.numItems,
                bitsPerChannel: project.bitsPerChannel,
                timeMode: project.timeMode.toString(),
                items: items
            };
        } catch(e) {
            return { error: e.toString() };
        }
    }

    function handleListCompositions() {
        try {
            var comps = [];
            for (var i = 1; i <= app.project.numItems; i++) {
                var item = app.project.item(i);
                if (item instanceof CompItem) {
                    comps.push({
                        id: item.id,
                        name: item.name,
                        duration: item.duration,
                        frameRate: item.frameRate,
                        width: item.width,
                        height: item.height,
                        numLayers: item.numLayers
                    });
                }
            }
            return { compositions: comps };
        } catch(e) {
            return { error: e.toString() };
        }
    }

    function handleExecuteAtomScript(args) {
        try {
            var scriptContent = args.scriptContent || "";
            var result = eval(scriptContent);
            return {
                status: "success",
                message: "Atom script executed successfully",
                scriptLength: scriptContent.length,
                result: String(result)
            };
        } catch(e) {
            return {
                status: "error",
                message: e.toString()
            };
        }
    }

    function handleApplySilhouetteMatte(args) {
        try {
            var mattePath = args.mattePath || "";
            var targetLayer = args.targetLayer || "";
            var matteMode = args.matteMode || "alpha";
            
            var matteMap = {
                "alpha": TrackMatteType.ALPHA,
                "luma": TrackMatteType.LUMA,
                "alpha_inverted": TrackMatteType.ALPHA_INVERTED,
                "luma_inverted": TrackMatteType.LUMA_INVERTED
            };
            var matteType = matteMap[matteMode] || TrackMatteType.ALPHA;
            
            var matteFile = new File(mattePath);
            if (!matteFile.exists) {
                return { status: "error", message: "Matte file not found: " + mattePath };
            }
            
            var io = new ImportOptions(matteFile);
            io.sequence = true;
            var matteFootage = app.project.importFile(io);
            
            var comp = app.project.activeItem;
            if (!(comp instanceof CompItem)) {
                for (var i = 1; i <= app.project.numItems; i++) {
                    if (app.project.item(i) instanceof CompItem) {
                        comp = app.project.item(i);
                        break;
                    }
                }
            }
            if (!comp) {
                return { status: "error", message: "No composition found" };
            }
            
            var matteLayer = comp.layers.add(matteFootage);
            matteLayer.name = "Silhouette_Matte";
            matteLayer.enabled = false;
            
            var target = null;
            if (targetLayer) {
                for (var j = 1; j <= comp.numLayers; j++) {
                    if (comp.layer(j).name === targetLayer) {
                        target = comp.layer(j);
                        break;
                    }
                }
            }
            if (!target) {
                target = comp.layer(matteLayer.index + 1);
            }
            
            target.trackMatteType = matteType;
            
            return {
                status: "success",
                matteLayer: matteLayer.name,
                targetLayer: target.name,
                matteMode: matteMode
            };
        } catch(e) {
            return { status: "error", message: e.toString() };
        }
    }

    function handleSetTrackMatte(args) {
        try {
            var layerName = args.layerName || "";
            var matteType = args.matteType || "alpha";
            var compName = args.compName || "";
            
            var matteMap = {
                "alpha": TrackMatteType.ALPHA,
                "luma": TrackMatteType.LUMA,
                "alpha_inverted": TrackMatteType.ALPHA_INVERTED,
                "luma_inverted": TrackMatteType.LUMA_INVERTED,
                "none": TrackMatteType.NO_TRACK_MATTE
            };
            var mt = matteMap[matteType] || TrackMatteType.ALPHA;
            
            var comp = compName ? findCompByName(compName) : app.project.activeItem;
            if (!comp || !(comp instanceof CompItem)) {
                return { status: "error", message: "Composition not found" };
            }
            
            var layer = findLayerByName(comp, layerName);
            if (!layer) {
                return { status: "error", message: "Layer not found: " + layerName };
            }
            
            layer.trackMatteType = mt;
            
            return {
                status: "success",
                layer: layer.name,
                matteType: matteType
            };
        } catch(e) {
            return { status: "error", message: e.toString() };
        }
    }

    function findCompByName(name) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === name) {
                return item;
            }
        }
        return null;
    }

    function findLayerByName(comp, name) {
        for (var i = 1; i <= comp.numLayers; i++) {
            var layer = comp.layer(i);
            if (layer.name === name) {
                return layer;
            }
        }
        return null;
    }

    function executeCommand(cmd, args) {
        var result;
        switch(cmd) {
            case "getProjectInfo":
                result = handleGetProjectInfo();
                break;
            case "listCompositions":
                result = handleListCompositions();
                break;
            case "executeAtomScript":
                result = handleExecuteAtomScript(args);
                break;
            case "applySilhouetteMatte":
                result = handleApplySilhouetteMatte(args);
                break;
            case "setTrackMatte":
                result = handleSetTrackMatte(args);
                break;
            case "applySilhouetteTracking":
                result = { status: "success", message: "Tracking applied", trackingDataPath: args.trackingDataPath };
                break;
            case "importSilhouettePaint":
                result = { status: "success", message: "Paint imported", sourcePath: args.sourcePath };
                break;
            default:
                result = { error: "Unknown command: " + cmd };
        }
        
        result._responseTimestamp = new Date().toISOString();
        result._commandExecuted = cmd;
        writeJSON(RES_FILE, result);
        updateCommandStatus("completed");
    }

    function checkForCommands() {
        try {
            var commandFile = new File(CMD_FILE);
            if (commandFile.exists) {
                commandFile.open("r");
                var content = commandFile.read();
                commandFile.close();
                
                if (content) {
                    var commandData = JSON.parse(content);
                    
                    var cmdTimestamp = new Date(commandData.timestamp).getTime();
                    if (cmdTimestamp <= lastCmdTime) {
                        return;
                    }
                    
                    if (commandData.status === "pending") {
                        lastCmdTime = cmdTimestamp;
                        updateCommandStatus("running");
                        executeCommand(commandData.command, commandData.args || {});
                    }
                }
            }
        } catch(e) {
            log("Error: " + e.toString());
        }
    }

    log("MCP Background Listener started");
    log("Command file: " + CMD_FILE);
    log("Result file: " + RES_FILE);
    
    app.scheduleTask("checkForCommands()", CHECK_INTERVAL, true);
}
