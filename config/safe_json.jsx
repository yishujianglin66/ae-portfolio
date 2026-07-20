// safe_json.jsx
// 安全的 JSON 解析器 - 完全不使用 eval
// 适用于 ExtendScript (ES3) 环境
// 基于 JSON-js (Public Domain) 实现，仅使用递归下降解析

{
    if (typeof JSON === "undefined") { JSON = {}; }

    if (typeof JSON.parse !== "function") {
        JSON.parse = (function () {
            var at;
            var ch;
            var escapee = {
                '"': '"',
                "\\": "\\",
                "/": "/",
                b: "\b",
                f: "\f",
                n: "\n",
                r: "\r",
                t: "\t"
            };
            var text;

            function error(m) {
                var err = new Error(m);
                err.name = "SyntaxError";
                throw err;
            }

            function next(c) {
                if (c && c !== ch) {
                    error("Expected '" + c + "' instead of '" + ch + "'");
                }
                ch = text.charAt(at);
                at += 1;
                return ch;
            }

            function number() {
                var number;
                var string = "";

                if (ch === "-") {
                    string = "-";
                    next("-");
                }
                while (ch >= "0" && ch <= "9") {
                    string += ch;
                    next();
                }
                if (ch === ".") {
                    string += ".";
                    while (next() && ch >= "0" && ch <= "9") {
                        string += ch;
                    }
                }
                if (ch === "e" || ch === "E") {
                    string += ch;
                    next();
                    if (ch === "-" || ch === "+") {
                        string += ch;
                        next();
                    }
                    while (ch >= "0" && ch <= "9") {
                        string += ch;
                        next();
                    }
                }
                number = +string;
                if (!isFinite(number)) {
                    error("Bad number");
                } else {
                    return number;
                }
            }

            function string() {
                var hex;
                var i;
                var string = "";
                var uffff;

                if (ch === '"') {
                    while (next()) {
                        if (ch === '"') {
                            next();
                            return string;
                        } else if (ch === "\\") {
                            next();
                            if (ch === "u") {
                                uffff = 0;
                                for (i = 0; i < 4; i += 1) {
                                    hex = parseInt(next(), 16);
                                    if (!isFinite(hex)) {
                                        break;
                                    }
                                    uffff = uffff * 16 + hex;
                                }
                                string += String.fromCharCode(uffff);
                            } else if (typeof escapee[ch] === "string") {
                                    string += escapee[ch];
                                } else {
                                    break;
                                }
                        } else {
                            string += ch;
                        }
                    }
                }
                error("Bad string");
            }

            function white() {
                while (ch && ch <= " ") {
                    next();
                }
            }

            function word() {
                switch (ch) {
                case "t":
                    next("t");
                    next("r");
                    next("u");
                    next("e");
                    return true;
                case "f":
                    next("f");
                    next("a");
                    next("l");
                    next("s");
                    next("e");
                    return false;
                case "n":
                    next("n");
                    next("u");
                    next("l");
                    next("l");
                    return null;
                }
                error("Unexpected '" + ch + "'");
            }

            function value() {
                white();
                switch (ch) {
                case "{":
                    return object();
                case "[":
                    return array();
                case '"':
                    return string();
                case "-":
                    return number();
                default:
                    return ch >= "0" && ch <= "9"
                        ? number()
                        : word();
                }
            }

            function array() {
                var array = [];

                if (ch === "[") {
                    next("[");
                    white();
                    if (ch === "]") {
                        next("]");
                        return array;
                    }
                    while (ch) {
                        array.push(value());
                        white();
                        if (ch === "]") {
                            next("]");
                            return array;
                        }
                        next(",");
                        white();
                    }
                }
                error("Bad array");
            }

            function object() {
                var key;
                var object = {};

                if (ch === "{") {
                    next("{");
                    white();
                    if (ch === "}") {
                        next("}");
                        return object;
                    }
                    while (ch) {
                        key = string();
                        white();
                        next(":");
                        if (Object.hasOwnProperty.call(object, key)) {
                            error("Duplicate key '" + key + "'");
                        }
                        object[key] = value();
                        white();
                        if (ch === "}") {
                            next("}");
                            return object;
                        }
                        next(",");
                        white();
                    }
                }
                error("Bad object");
            }

            return function (source, reviver) {
                var result;

                text = String(source);
                at = 0;
                ch = " ";
                result = value();
                white();
                if (ch) {
                    error("Syntax error");
                }

                return (typeof reviver === "function")
                    ? (function walk(holder, key) {
                        var k;
                        var v;
                        var val = holder[key];
                        if (val && typeof val === "object" && !(val instanceof Date)) {
                            if (val instanceof Array) {
                            for (k = val.length - 1; k >= 0; k -= 1) {
                                v = walk(val, k);
                                if (v !== undefined) {
                                    val[k] = v;
                                } else {
                                    val.splice(k, 1);
                                }
                            }
                        } else {
                            var keys = [];
                            for (k in val) {
                                if (Object.prototype.hasOwnProperty.call(val, k)) {
                                    keys.push(k);
                                }
                            }
                            for (var i = 0; i < keys.length; i += 1) {
                                k = keys[i];
                                v = walk(val, k);
                                if (v !== undefined) {
                                    val[k] = v;
                                } else {
                                    delete val[k];
                                }
                            }
                        }
                    })({"": result}, "")
                    : result;
            };
        })();
    }

    if (typeof JSON.stringify !== "function") {
        (function () {
            function esc(str) {
                return (str + "")
                    .replace(/\\/g, "\\\\")
                    .replace(/"/g, '\\"')
                    .replace(/\n/g, "\\n")
                    .replace(/\r/g, "\\r")
                    .replace(/\t/g, "\\t");
            }
            function toJSON(val) {
                if (val === null) return "null";
                var t = typeof val;
                if (t === "number" || t === "boolean") return String(val);
                if (t === "string") return '"' + esc(val) + '"';
                if (val instanceof Array) {
                    var a = [];
                    for (var i = 0; i < val.length; i++) a.push(toJSON(val[i]));
                    return "[" + a.join(",") + "]";
                }
                if (t === "object") {
                    var props = [];
                    for (var k in val) {
                        if (val.hasOwnProperty(k) && typeof val[k] !== "function" && typeof val[k] !== "undefined") {
                            props.push('"' + esc(k) + '":' + toJSON(val[k]));
                        }
                    }
                    return "{" + props.join(",") + "}";
                }
                return "null";
            }
            JSON.stringify = function (value, _replacer, _space) { return toJSON(value); };
        })();
    }

    if (!Date.prototype.toISOString) {
        Date.prototype.toISOString = function () {
            var d = this;
            function pad(n) { return n < 10 ? "0" + n : "" + n; }
            return d.getUTCFullYear() + '-' +
                pad(d.getUTCMonth() + 1) + '-' +
                pad(d.getUTCDate()) + 'T' +
                pad(d.getUTCHours()) + ':' +
                pad(d.getUTCMinutes()) + ':' +
                pad(d.getUTCSeconds()) + '.' +
                (d.getUTCMilliseconds() < 100 ? "0" : "") +
                (d.getUTCMilliseconds() < 10 ? "0" : "") +
                d.getUTCMilliseconds() + 'Z';
        };
    }
}
