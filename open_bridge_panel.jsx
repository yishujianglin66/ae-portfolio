var panelPath = "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Scripts/ScriptUI Panels/ae_mcp_bridge_v26.jsx";
var panelFile = new File(panelPath);
if (panelFile.exists) {
    $.evalFile(panelFile);
}
