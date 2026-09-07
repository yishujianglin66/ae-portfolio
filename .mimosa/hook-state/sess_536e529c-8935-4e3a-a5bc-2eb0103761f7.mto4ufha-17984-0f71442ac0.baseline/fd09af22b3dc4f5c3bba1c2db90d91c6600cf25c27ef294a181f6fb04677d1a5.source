// executeAtomScript.jsx
// 执行原子参数编译器生成的ExtendScript脚本
// 这是 Phase 1 编译器输出 → Phase 2 MCP 执行 的直接通道
// 支持干运行验证（dryRun）和完整执行两种模式

#include "_lib/args_loader.jsx"
#include "_lib/response_utils.jsx"

// ========== 签名验证配置 ==========
var SECRET_FILE = Folder.myDocuments.fsName + "/ae-mcp-bridge/.mcp_secret";
var MCP_SECRET = "";
var SIGNATURE_ENABLED = true;

function _loadSecret() {
    try {
        var f = new File(SECRET_FILE);
        if (f.exists) {
            f.encoding = "UTF-8";
            f.open("r");
            var content = f.read();
            f.close();
            if (content) MCP_SECRET = content.replace(/\s+$/, "");
        }
    } catch(e) {}
}
_loadSecret();

function _sha256(message) {
    function rotr(n,x){return(x>>>n)|(x<<(32-n))}function ch(x,y,z){return(x&y)^(~x&z)}function maj(x,y,z){return(x&y)^(x&z)^(y&z)}function sig0(x){return rotr(2,x)^rotr(13,x)^rotr(22,x)}function sig1(x){return rotr(6,x)^rotr(11,x)^rotr(25,x)}function gam0(x){return rotr(7,x)^rotr(18,x)^(x>>>3)}function gam1(x){return rotr(17,x)^rotr(19,x)^(x>>>10)}
    var K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    var h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
    function stb(s){var b=[];for(var i=0;i<s.length;i++){var c=s.charCodeAt(i);if(c<0x80)b.push(c);else if(c<0x800)b.push(0xc0|(c>>6),0x80|(c&0x3f));else b.push(0xe0|(c>>12),0x80|((c>>6)&0x3f),0x80|(c&0x3f))}return b}
    var msg=stb(message);var bl=msg.length*8;msg.push(0x80);while(msg.length%64!==56)msg.push(0);for(var i=0;i<8;i++)msg.push(i<4?0:(bl>>>(8*(7-i)))&0xff);
    for(var o=0;o<msg.length;o+=64){var w=new Array(64);for(var j=0;j<16;j++)w[j]=(msg[o+4*j]<<24)|(msg[o+4*j+1]<<16)|(msg[o+4*j+2]<<8)|msg[o+4*j+3];for(var j=16;j<64;j++)w[j]=(gam1(w[j-2])+w[j-7]+gam0(w[j-15])+w[j-16])|0;var a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;for(var t=0;t<64;t++){var t1=(h+sig1(e)+ch(e,f,g)+K[t]+w[t])|0;var t2=(sig0(a)+maj(a,b,c))|0;h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0}h0=(h0+a)|0;h1=(h1+b)|0;h2=(h2+c)|0;h3=(h3+d)|0;h4=(h4+e)|0;h5=(h5+f)|0;h6=(h6+g)|0;h7=(h7+h)|0}
    function th(n){var s="";for(var i=7;i>=0;i--)s+=((n>>>(i*4))&0xf).toString(16);return s}return th(h0)+th(h1)+th(h2)+th(h3)+th(h4)+th(h5)+th(h6)+th(h7)
}
function _hmacSha256(key,message){var bs=64;var kb=[];for(var i=0;i<key.length;i++){var c=key.charCodeAt(i);if(c<0x80)kb.push(c);else if(c<0x800)kb.push(0xc0|(c>>6),0x80|(c&0x3f));else kb.push(0xe0|(c>>12),0x80|((c>>6)&0x3f),0x80|(c&0x3f))}if(kb.length>bs){var hx=_sha256(key);kb=[];for(var i=0;i<hx.length;i+=2)kb.push(parseInt(hx.substr(i,2),16))}while(kb.length<bs)kb.push(0);var ok="";var ik="";for(var i=0;i<bs;i++){ok+=String.fromCharCode(kb[i]^0x5c);ik+=String.fromCharCode(kb[i]^0x36)}return _sha256(ok+_sha256(ik+message))}
function _canonicalize(obj){if(obj===null||obj===undefined)return"null";var t=typeof obj;if(t==="number"||t==="boolean")return String(obj);if(t==="string"){function esc(s){return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t")}return'"'+esc(obj)+'"'}if(obj instanceof Array){var a=[];for(var i=0;i<obj.length;i++)a.push(_canonicalize(obj[i]));return"["+a.join(",")+"]"}if(t==="object"){var keys=[];for(var k in obj)if(obj.hasOwnProperty(k)&&typeof obj[k]!=="function"&&typeof obj[k]!=="undefined")keys.push(k);keys.sort();var pairs=[];function esk(s){return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t")}for(var i=0;i<keys.length;i++)pairs.push('"'+esk(keys[i])+'":'+_canonicalize(obj[keys[i]]));return"{"+pairs.join(",")+"}"}return"null"}
function verifySignature(data){if(!SIGNATURE_ENABLED)return true;if(!MCP_SECRET||MCP_SECRET.length===0)return true;if(!data||!data.signature||!data.timestamp)return false;var ts=parseInt(data.timestamp);if(isNaN(ts)){var dts=new Date(data.timestamp).getTime();if(isNaN(dts))return false;ts=Math.floor(dts/1000)}var now=Math.floor(new Date().getTime()/1000);if(Math.abs(now-ts)>300)return false;var vd={};for(var k in data)if(data.hasOwnProperty(k)&&k!=="signature"&&k!=="signature_alg")vd[k]=data[k];var canon=_canonicalize(vd);var expected=_hmacSha256(MCP_SECRET,canon);if(expected.length!==data.signature.length)return false;var diff=0;for(var i=0;i<expected.length;i++)diff|=(expected.charCodeAt(i)^data.signature.charCodeAt(i));return diff===0}

function executeAtomScript(args) {
    try {
        var scriptContent = args.scriptContent;
        var scriptName = args.scriptName || "atom-script-unnamed";
        var timeout = args.timeout || 10000;
        var dryRun = args.dryRun === true;

        if (!scriptContent || typeof scriptContent !== "string") {
            return buildError("E111", "E111: scriptContent 必须为非空字符串", {
                scriptName: scriptName,
                timestamp: new Date().toISOString()
            });
        }

        // 干运行模式：仅检查语法
        if (dryRun) {
            try {
                // 尝试解析脚本（不执行）
                var fn = new Function(scriptContent);
                return buildSuccess({
                    message: "干运行验证通过",
                    dryRun: true,
                    syntaxValid: true,
                    scriptName: scriptName,
                    contentLength: scriptContent.length,
                    timestamp: new Date().toISOString()
                });
            } catch (e) {
                return buildError("E111", "E111: 语法错误 - " + e.toString(), {
                    scriptName: scriptName,
                    timestamp: new Date().toISOString()
                });
            }
        }

        // ========== 脚本安全校验 ==========
        var FORBIDDEN_PATTERNS = [
            "system.callsystem",   // 执行系统命令
            "$.evalfile",          // 加载并执行外部 JSX 文件
            "new function(",        // 动态函数创建（等效 eval）
            ".execute("            // File.execute() 启动外部程序
        ];
        var MAX_SCRIPT_SIZE = 1048576; // 1MB

        function _validateScriptSafety(script) {
            if (!script) return "Empty script";
            if (script.length > MAX_SCRIPT_SIZE) return "Script exceeds size limit (1MB)";
            var lower = script.toLowerCase();
            for (var i = 0; i < FORBIDDEN_PATTERNS.length; i++) {
                if (lower.indexOf(FORBIDDEN_PATTERNS[i]) !== -1) {
                    return "Script contains forbidden API: " + FORBIDDEN_PATTERNS[i];
                }
            }
            return null;
        }

        var safetyError = _validateScriptSafety(scriptContent);
        if (safetyError) {
            return buildError("E201", "E201: " + safetyError, {
                scriptName: scriptName,
                timestamp: new Date().toISOString()
            });
        }

        // 完整执行模式
        app.beginUndoGroup("AE Atom Script - " + scriptName);

        var execResult = null;
        var execError = null;
        var startTime = new Date().getTime();

        try {
            // 编译器输出的脚本本身就是 IIFE 包装，可直接 eval
            eval(scriptContent);
            execResult = "executed";
        } catch (e) {
            execError = e.toString();
            execResult = "error";
        }

        app.endUndoGroup();

        var elapsed = new Date().getTime() - startTime;

        if (execError) {
            return buildError("E200", "E200: " + execError, {
                scriptName: scriptName,
                elapsedMs: elapsed,
                timestamp: new Date().toISOString()
            });
        }

        return buildSuccess({
            message: "原子脚本执行完成",
            scriptName: scriptName,
            result: execResult,
            elapsedMs: elapsed,
            contentLength: scriptContent.length,
            executedAt: new Date().toISOString()
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", error.toString(), {
            scriptName: args.scriptName || "unknown",
            timestamp: new Date().toISOString()
        });
    }
}

// 从 args.json 读取参数（与现有项目模式一致）
var args = loadArgs();

// 签名验证：独立入口时必须验证 args 中的签名
if (!verifySignature(args)) {
    $.write(buildError("E403", "Signature verification failed - command rejected"));
} else {
    var result = executeAtomScript(args);
    $.write(result);
}
