/**
 * @class CSInterface
 * Provides interface between CEP panel and After Effects.
 * Minimal version for AE Knowledge Vault panel.
 */
function CSInterface() {}

CSInterface.prototype.evalScript = function(script, callback) {
    if (typeof callback === "undefined") {
        callback = function() {};
    }
    try {
        window.__adobe_cep__.evalScript(script, callback);
    } catch(e) {
        callback("EvalScript error: " + e.message);
    }
};

CSInterface.prototype.getSystemPath = function(pathType) {
    var path = "";
    switch(pathType) {
        case SystemPath.EXTENSION:
            path = window.__adobe_cep__.getSystemPath(SystemPath.EXTENSION);
            break;
        case SystemPath.USER_DATA:
            path = window.__adobe_cep__.getSystemPath(SystemPath.USER_DATA);
            break;
        case SystemPath.COMMON_FILES:
            path = window.__adobe_cep__.getSystemPath(SystemPath.COMMON_FILES);
            break;
        case SystemPath.MY_DOCUMENTS:
            path = window.__adobe_cep__.getSystemPath(SystemPath.MY_DOCUMENTS);
            break;
        default:
            path = "";
    }
    return path;
};

CSInterface.prototype.getHostEnvironment = function() {
    var env = window.__adobe_cep__.getHostEnvironment();
    return JSON.parse(env);
};

CSInterface.prototype.addEventListener = function(type, listener, obj) {
    window.__adobe_cep__.addEventListener(type, listener, obj);
};

CSInterface.prototype.removeEventListener = function(type, listener, obj) {
    window.__adobe_cep__.removeEventListener(type, listener, obj);
};

CSInterface.prototype.requestOpenExtension = function(extId, params) {
    window.__adobe_cep__.requestOpenExtension(extId, params);
};

CSInterface.prototype.closeExtension = function() {
    window.__adobe_cep__.closeExtension();
};

var SystemPath = {
    EXTENSION: 0,
    COMMON_FILES: 1,
    MY_DOCUMENTS: 2,
    APPLICATION: 3,
    USER_DATA: 4,
    CACHE_DATA: 5,
    ROAMING_DATA: 6
};

var SystemColorTheme = {
    DARK: 0,
    LIGHT: 1
};
