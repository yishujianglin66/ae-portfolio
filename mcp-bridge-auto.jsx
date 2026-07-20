// JSON polyfill for ExtendScript (when JSON is undefined)
if (typeof JSON === "undefined") { JSON = {}; }
if (typeof JSON.parse !== "function") {
    JSON.parse = function (text) {
        // Safe-ish fallback for trusted input (our own command file)
        return eval("(" + text + ")");
    };
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
        JSON.stringify = function (value, _replacer, _space) {
            return toJSON(value);
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
        return d.getUTCFullYear() + '-' +
            ('0' + (d.getUTCMonth() + 1)).slice(-2) + '-' +
            ('0' + d.getUTCDate()).slice(-2) + 'T' +
            ('0' + d.getUTCHours()).slice(-2) + ':' +
            ('0' + d.getUTCMinutes()).slice(-2) + ':' +
            ('0' + d.getUTCSeconds()).slice(-2) + '.' +
            ('00' + d.getUTCMilliseconds()).slice(-3) + 'Z';
    };
}

// Remove #include directives as we define functions below
/*
#include "createComposition.jsx"
#include "createTextLayer.jsx"
#include "createShapeLayer.jsx"
#include "createSolidLayer.jsx"
#include "setLayerProperties.jsx"
*/

// --- Function Definitions ---

// --- createComposition (from createComposition.jsx) --- 
function createComposition(args) {
    try {
        var name = args.name || "New Composition";
        var width = parseInt(args.width) || 1920;
        var height = parseInt(args.height) || 1080;
        var pixelAspect = parseFloat(args.pixelAspect) || 1.0;
        var duration = parseFloat(args.duration) || 10.0;
        var frameRate = parseFloat(args.frameRate) || 30.0;
        var bgColor = args.backgroundColor ? [args.backgroundColor.r/255, args.backgroundColor.g/255, args.backgroundColor.b/255] : [0, 0, 0];
        var newComp = app.project.items.addComp(name, width, height, pixelAspect, duration, frameRate);
        if (args.backgroundColor) {
            newComp.bgColor = bgColor;
        }
        return JSON.stringify({
            status: "success", message: "Composition created successfully",
            composition: { name: newComp.name, id: newComp.id, width: newComp.width, height: newComp.height, pixelAspect: newComp.pixelAspect, duration: newComp.duration, frameRate: newComp.frameRate, bgColor: newComp.bgColor }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- createTextLayer (from createTextLayer.jsx) ---
function createTextLayer(args) {
    try {
        var compName = args.compName || "";
        var text = args.text || "Text Layer";
        var position = args.position || [960, 540]; 
        var fontSize = args.fontSize || 72;
        var color = args.color || [1, 1, 1]; 
        var startTime = args.startTime || 0;
        var duration = args.duration || 5; 
        var fontFamily = args.fontFamily || "Arial";
        var alignment = args.alignment || "center"; 
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; } 
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }
        var textLayer = comp.layers.addText(text);
        var textProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
        var textDocument = textProp.value;
        textDocument.fontSize = fontSize;
        textDocument.fillColor = color;
        textDocument.font = fontFamily;
        if (alignment === "left") { textDocument.justification = ParagraphJustification.LEFT_JUSTIFY; } 
        else if (alignment === "center") { textDocument.justification = ParagraphJustification.CENTER_JUSTIFY; } 
        else if (alignment === "right") { textDocument.justification = ParagraphJustification.RIGHT_JUSTIFY; }
        textProp.setValue(textDocument);
        textLayer.property("Position").setValue(position);
        textLayer.startTime = startTime;
        if (duration > 0) { textLayer.outPoint = startTime + duration; }
        return JSON.stringify({
            status: "success", message: "Text layer created successfully",
            layer: { name: textLayer.name, index: textLayer.index, type: "text", inPoint: textLayer.inPoint, outPoint: textLayer.outPoint, position: textLayer.property("Position").value }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- createShapeLayer (from createShapeLayer.jsx) --- 
function createShapeLayer(args) {
    try {
        var compName = args.compName || "";
        var shapeType = args.shapeType || "rectangle"; 
        var position = args.position || [960, 540]; 
        var size = args.size || [200, 200]; 
        var fillColor = args.fillColor || [1, 0, 0]; 
        var strokeColor = args.strokeColor || [0, 0, 0]; 
        var strokeWidth = args.strokeWidth || 0; 
        var startTime = args.startTime || 0;
        var duration = args.duration || 5; 
        var name = args.name || "Shape Layer";
        var points = args.points || 5; 
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; } 
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }
        var shapeLayer = comp.layers.addShape();
        shapeLayer.name = name;
        var contents = shapeLayer.property("Contents"); 
        var shapeGroup = contents.addProperty("ADBE Vector Group");
        var groupContents = shapeGroup.property("Contents"); 
        var shapePathProperty;
        if (shapeType === "rectangle") {
            shapePathProperty = groupContents.addProperty("ADBE Vector Shape - Rect");
            shapePathProperty.property("Size").setValue(size);
        } else if (shapeType === "ellipse") {
            shapePathProperty = groupContents.addProperty("ADBE Vector Shape - Ellipse");
            shapePathProperty.property("Size").setValue(size);
        } else if (shapeType === "polygon" || shapeType === "star") { 
            shapePathProperty = groupContents.addProperty("ADBE Vector Shape - Star");
            shapePathProperty.property("Type").setValue(shapeType === "polygon" ? 1 : 2); 
            shapePathProperty.property("Points").setValue(points);
            shapePathProperty.property("Outer Radius").setValue(size[0] / 2);
            if (shapeType === "star") { shapePathProperty.property("Inner Radius").setValue(size[0] / 3); }
        }
        var fill = groupContents.addProperty("ADBE Vector Graphic - Fill");
        fill.property("Color").setValue(fillColor);
        fill.property("Opacity").setValue(100);
        if (strokeWidth > 0) {
            var stroke = groupContents.addProperty("ADBE Vector Graphic - Stroke");
            stroke.property("Color").setValue(strokeColor);
            stroke.property("Stroke Width").setValue(strokeWidth);
            stroke.property("Opacity").setValue(100);
        }
        shapeLayer.property("Position").setValue(position);
        shapeLayer.startTime = startTime;
        if (duration > 0) { shapeLayer.outPoint = startTime + duration; }
        return JSON.stringify({
            status: "success", message: "Shape layer created successfully",
            layer: { name: shapeLayer.name, index: shapeLayer.index, type: "shape", shapeType: shapeType, inPoint: shapeLayer.inPoint, outPoint: shapeLayer.outPoint, position: shapeLayer.property("Position").value }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- createCamera ---
function createCamera(args) {
    try {
        var compName = args.compName || "";
        var name = args.name || "Camera";
        var zoom = args.zoom || 1777.78; // Default ~50mm equivalent
        var position = args.position; // Optional [x, y, z]
        var pointOfInterest = args.pointOfInterest; // Optional [x, y, z]
        var oneNode = args.oneNode || false; // If true, create a one-node camera (no point of interest)

        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; }
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }

        var centerPoint = [comp.width / 2, comp.height / 2];
        var cameraLayer = comp.layers.addCamera(name, centerPoint);
        cameraLayer.property("Camera Options").property("Zoom").setValue(zoom);

        if (oneNode) {
            cameraLayer.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        }

        if (position !== undefined && position !== null) {
            cameraLayer.property("Position").setValue(position);
        }

        if (pointOfInterest !== undefined && pointOfInterest !== null && !oneNode) {
            cameraLayer.property("Point of Interest").setValue(pointOfInterest);
        }

        var result = {
            name: cameraLayer.name,
            index: cameraLayer.index,
            zoom: cameraLayer.property("Camera Options").property("Zoom").value,
            position: cameraLayer.property("Position").value,
            oneNode: oneNode
        };
        if (!oneNode) {
            result.pointOfInterest = cameraLayer.property("Point of Interest").value;
        }

        return JSON.stringify({
            status: "success",
            message: "Camera created successfully",
            layer: result
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- duplicateLayer ---
function duplicateLayer(args) {
    try {
        var compName = args.compName || "";
        var layerIndex = args.layerIndex;
        var layerName = args.layerName || "";
        var newName = args.newName; // optional rename

        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; }
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }

        var layer = null;
        if (layerIndex !== undefined && layerIndex !== null) {
            if (layerIndex > 0 && layerIndex <= comp.numLayers) { layer = comp.layer(layerIndex); }
            else { throw new Error("Layer index out of bounds: " + layerIndex); }
        } else if (layerName) {
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }
            }
        }
        if (!layer) { throw new Error("Layer not found: " + (layerName || "index " + layerIndex)); }

        var newLayer = layer.duplicate();
        if (newName) { newLayer.name = newName; }

        return JSON.stringify({
            status: "success",
            message: "Layer duplicated successfully",
            original: { name: layer.name, index: layer.index },
            duplicate: { name: newLayer.name, index: newLayer.index }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- deleteLayer ---
function deleteLayer(args) {
    try {
        var compName = args.compName || "";
        var layerIndex = args.layerIndex;
        var layerName = args.layerName || "";

        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; }
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }

        var layer = null;
        if (layerIndex !== undefined && layerIndex !== null) {
            if (layerIndex > 0 && layerIndex <= comp.numLayers) { layer = comp.layer(layerIndex); }
            else { throw new Error("Layer index out of bounds: " + layerIndex); }
        } else if (layerName) {
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }
            }
        }
        if (!layer) { throw new Error("Layer not found: " + (layerName || "index " + layerIndex)); }

        var deletedName = layer.name;
        var deletedIndex = layer.index;
        layer.remove();

        return JSON.stringify({
            status: "success",
            message: "Layer deleted successfully",
            deleted: { name: deletedName, index: deletedIndex }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- setLayerMask: create or modify a mask on a layer ---
function setLayerMask(args) {
    try {
        var compName = args.compName || "";
        var layerIndex = args.layerIndex;
        var layerName = args.layerName || "";
        var maskIndex = args.maskIndex; // optional — if provided, modify existing mask
        var maskPath = args.maskPath; // array of [x, y] points defining the mask shape
        var maskRect = args.maskRect; // shorthand: {top, left, width, height} for rectangular masks
        var maskMode = args.maskMode || "add"; // "add", "subtract", "intersect", "none"
        var maskFeather = args.maskFeather; // optional [x, y] feather
        var maskOpacity = args.maskOpacity; // optional 0-100
        var maskExpansion = args.maskExpansion; // optional pixels
        var maskName = args.maskName; // optional rename

        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; }
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }

        var layer = null;
        if (layerIndex !== undefined && layerIndex !== null) {
            if (layerIndex > 0 && layerIndex <= comp.numLayers) { layer = comp.layer(layerIndex); }
            else { throw new Error("Layer index out of bounds: " + layerIndex); }
        } else if (layerName) {
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }
            }
        }
        if (!layer) { throw new Error("Layer not found: " + (layerName || "index " + layerIndex)); }

        // Build the mask shape
        var shapePoints = [];
        if (maskRect) {
            // Rectangle shorthand
            var t = maskRect.top || 0;
            var l = maskRect.left || 0;
            var w = maskRect.width || comp.width;
            var h = maskRect.height || comp.height;
            shapePoints = [[l, t], [l + w, t], [l + w, t + h], [l, t + h]];
        } else if (maskPath && maskPath.length >= 3) {
            shapePoints = maskPath;
        } else {
            throw new Error("Must provide either maskRect or maskPath with at least 3 points");
        }

        // Create the shape object
        var myShape = new Shape();
        var vertices = [];
        for (var p = 0; p < shapePoints.length; p++) {
            vertices.push(shapePoints[p]);
        }
        myShape.vertices = vertices;
        myShape.closed = true;

        var changed = [];
        var mask;

        if (maskIndex !== undefined && maskIndex !== null) {
            // Modify existing mask
            if (maskIndex > 0 && maskIndex <= layer.property("Masks").numProperties) {
                mask = layer.property("Masks").property(maskIndex);
            } else {
                throw new Error("Mask index out of bounds: " + maskIndex);
            }
            mask.property("Mask Path").setValue(myShape);
            changed.push("maskPath");
        } else {
            // Create new mask
            mask = layer.property("Masks").addProperty("Mask");
            mask.property("Mask Path").setValue(myShape);
            changed.push("newMask");
        }

        // Set mask mode
        var modes = {
            "none": MaskMode.NONE,
            "add": MaskMode.ADD,
            "subtract": MaskMode.SUBTRACT,
            "intersect": MaskMode.INTERSECT,
            "lighten": MaskMode.LIGHTEN,
            "darken": MaskMode.DARKEN,
            "difference": MaskMode.DIFFERENCE
        };
        if (modes[maskMode] !== undefined) {
            mask.maskMode = modes[maskMode];
            changed.push("maskMode");
        }

        if (maskFeather !== undefined && maskFeather !== null) {
            mask.property("Mask Feather").setValue(maskFeather);
            changed.push("maskFeather");
        }
        if (maskOpacity !== undefined && maskOpacity !== null) {
            mask.property("Mask Opacity").setValue(maskOpacity);
            changed.push("maskOpacity");
        }
        if (maskExpansion !== undefined && maskExpansion !== null) {
            mask.property("Mask Expansion").setValue(maskExpansion);
            changed.push("maskExpansion");
        }
        if (maskName) {
            mask.name = maskName;
            changed.push("maskName");
        }

        return JSON.stringify({
            status: "success",
            message: "Mask set successfully",
            layer: { name: layer.name, index: layer.index },
            mask: {
                name: mask.name,
                index: mask.propertyIndex,
                mode: maskMode,
                changedProperties: changed
            }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- createSolidLayer (from createSolidLayer.jsx) ---
function createSolidLayer(args) {
    try {
        var compName = args.compName || "";
        var color = args.color || [1, 1, 1]; 
        var name = args.name || "Solid Layer";
        var position = args.position || [960, 540]; 
        var size = args.size; 
        var startTime = args.startTime || 0;
        var duration = args.duration || 5; 
        var isAdjustment = args.isAdjustment || false; 
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; } 
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }
        if (!size) { size = [comp.width, comp.height]; }
        var solidLayer;
        if (isAdjustment) {
            solidLayer = comp.layers.addSolid([0, 0, 0], name, size[0], size[1], 1);
            solidLayer.adjustmentLayer = true;
        } else {
            solidLayer = comp.layers.addSolid(color, name, size[0], size[1], 1);
        }
        solidLayer.property("Position").setValue(position);
        solidLayer.startTime = startTime;
        if (duration > 0) { solidLayer.outPoint = startTime + duration; }
        return JSON.stringify({
            status: "success", message: isAdjustment ? "Adjustment layer created successfully" : "Solid layer created successfully",
            layer: { name: solidLayer.name, index: solidLayer.index, type: isAdjustment ? "adjustment" : "solid", inPoint: solidLayer.inPoint, outPoint: solidLayer.outPoint, position: solidLayer.property("Position").value, isAdjustment: solidLayer.adjustmentLayer }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- setLayerProperties (modified to handle text properties) ---
function setLayerProperties(args) {
    try {
        var compName = args.compName || "";
        var layerName = args.layerName || "";
        var layerIndex = args.layerIndex; 
        
        // General Properties
        var position = args.position; 
        var scale = args.scale; 
        var rotation = args.rotation; 
        var opacity = args.opacity; 
        var startTime = args.startTime; 
        var duration = args.duration; 

        // Text Specific Properties
        var textContent = args.text; // New: text content
        var fontFamily = args.fontFamily; // New: font family
        var fontSize = args.fontSize; // New: font size
        var fillColor = args.fillColor; // New: font color
        
        // Find the composition (same logic as before)
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; } 
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }
        
        // Find the layer (same logic as before)
        var layer = null;
        if (layerIndex !== undefined && layerIndex !== null) {
            if (layerIndex > 0 && layerIndex <= comp.numLayers) { layer = comp.layer(layerIndex); } 
            else { throw new Error("Layer index out of bounds: " + layerIndex); }
        } else if (layerName) {
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }
            }
        }
        if (!layer) { throw new Error("Layer not found: " + (layerName || "index " + layerIndex)); }
        
        var changedProperties = [];
        var textDocumentChanged = false;
        var textProp = null;
        var textDocument = null;

        // --- Text Property Handling ---
        if (layer instanceof TextLayer && (textContent !== undefined || fontFamily !== undefined || fontSize !== undefined || fillColor !== undefined)) {
            var sourceTextProp = layer.property("Source Text");
            if (sourceTextProp && sourceTextProp.value) {
                var currentTextDocument = sourceTextProp.value; // Get the current value
                var updated = false;

                if (textContent !== undefined && textContent !== null && currentTextDocument.text !== textContent) {
                    currentTextDocument.text = textContent;
                    changedProperties.push("text");
                    updated = true;
                }
                if (fontFamily !== undefined && fontFamily !== null && currentTextDocument.font !== fontFamily) {
                    // Add basic validation/logging for font existence if needed
                    // try { app.fonts.findFont(fontFamily); } catch (e) { logToPanel("Warning: Font '"+fontFamily+"' might not be installed."); }
                    currentTextDocument.font = fontFamily;
                    changedProperties.push("fontFamily");
                    updated = true;
                }
                if (fontSize !== undefined && fontSize !== null && currentTextDocument.fontSize !== fontSize) {
                    currentTextDocument.fontSize = fontSize;
                    changedProperties.push("fontSize");
                    updated = true;
                }
                // Comparing colors needs care due to potential floating point inaccuracies if set via UI
                // Simple comparison for now
                if (fillColor !== undefined && fillColor !== null && 
                    (currentTextDocument.fillColor[0] !== fillColor[0] || 
                     currentTextDocument.fillColor[1] !== fillColor[1] || 
                     currentTextDocument.fillColor[2] !== fillColor[2])) {
                    currentTextDocument.fillColor = fillColor;
                    changedProperties.push("fillColor");
                    updated = true;
                }

                // Only set the value if something actually changed
                if (updated) {
                    try {
                        sourceTextProp.setValue(currentTextDocument);
                        logToPanel("Applied changes to Text Document for layer: " + layer.name);
                    } catch (e) {
                        logToPanel("ERROR applying Text Document changes: " + e.toString());
                        // Decide if we should throw or just log the error for text properties
                        // For now, just log, other properties might still succeed
                    }
                }
                 // Store the potentially updated document for the return value
                 textDocument = currentTextDocument; 

            } else {
                logToPanel("Warning: Could not access Source Text property for layer: " + layer.name);
            }
        }

        // --- Enabled/Visible ---
        var enabled = args.enabled;
        if (enabled !== undefined && enabled !== null) { layer.enabled = !!enabled; changedProperties.push("enabled"); }

        // --- Blend Mode ---
        var blendMode = args.blendMode;
        if (blendMode !== undefined && blendMode !== null) {
            var modes = {
                "normal": BlendingMode.NORMAL,
                "add": BlendingMode.ADD,
                "multiply": BlendingMode.MULTIPLY,
                "screen": BlendingMode.SCREEN,
                "overlay": BlendingMode.OVERLAY,
                "softLight": BlendingMode.SOFT_LIGHT,
                "hardLight": BlendingMode.HARD_LIGHT,
                "colorDodge": BlendingMode.COLOR_DODGE,
                "colorBurn": BlendingMode.COLOR_BURN,
                "darken": BlendingMode.DARKEN,
                "lighten": BlendingMode.LIGHTEN,
                "difference": BlendingMode.DIFFERENCE,
                "exclusion": BlendingMode.EXCLUSION,
                "hue": BlendingMode.HUE,
                "saturation": BlendingMode.SATURATION,
                "color": BlendingMode.COLOR,
                "luminosity": BlendingMode.LUMINOSITY
            };
            if (modes[blendMode] !== undefined) {
                layer.blendingMode = modes[blendMode];
                changedProperties.push("blendMode");
            }
        }

        // --- Track Matte ---
        var trackMatteType = args.trackMatteType;
        if (trackMatteType !== undefined && trackMatteType !== null) {
            // Values: "none", "alpha", "alphaInverted", "luma", "lumaInverted"
            var matteTypes = {
                "none": TrackMatteType.NO_TRACK_MATTE,
                "alpha": TrackMatteType.ALPHA,
                "alphaInverted": TrackMatteType.ALPHA_INVERTED,
                "luma": TrackMatteType.LUMA,
                "lumaInverted": TrackMatteType.LUMA_INVERTED
            };
            if (matteTypes[trackMatteType] !== undefined) {
                layer.trackMatteType = matteTypes[trackMatteType];
                changedProperties.push("trackMatteType");
            }
        }

        // --- General Property Handling ---
        var threeDLayer = args.threeDLayer;
        if (threeDLayer !== undefined && threeDLayer !== null) { layer.threeDLayer = !!threeDLayer; changedProperties.push("threeDLayer"); }
        if (position !== undefined && position !== null) {
            var posProp = layer.property("Position");
            if (posProp.numKeys > 0) { while (posProp.numKeys > 0) { posProp.removeKey(1); } }
            posProp.setValue(position);
            changedProperties.push("position");
        }
        if (scale !== undefined && scale !== null) { layer.property("Scale").setValue(scale); changedProperties.push("scale"); }
        if (rotation !== undefined && rotation !== null) {
            if (layer.threeDLayer) { 
                // For 3D layers, Z rotation is often what's intended by a single value
                layer.property("Z Rotation").setValue(rotation);
            } else { 
                layer.property("Rotation").setValue(rotation); 
            }
            changedProperties.push("rotation");
        }
        if (opacity !== undefined && opacity !== null) { layer.property("Opacity").setValue(opacity); changedProperties.push("opacity"); }
        if (startTime !== undefined && startTime !== null) { layer.startTime = startTime; changedProperties.push("startTime"); }
        if (duration !== undefined && duration !== null && duration > 0) {
            var actualStartTime = (startTime !== undefined && startTime !== null) ? startTime : layer.startTime;
            layer.outPoint = actualStartTime + duration;
            changedProperties.push("duration");
        }

        // Return success with updated layer details (including text if changed)
        var returnLayerInfo = {
            name: layer.name,
            index: layer.index,
            threeDLayer: layer.threeDLayer,
            position: layer.property("Position").value,
            scale: layer.property("Scale").value,
            rotation: layer.threeDLayer ? layer.property("Z Rotation").value : layer.property("Rotation").value, // Return appropriate rotation
            opacity: layer.property("Opacity").value,
            inPoint: layer.inPoint,
            outPoint: layer.outPoint,
            changedProperties: changedProperties
        };
        // Add text properties to the return object if it was a text layer
        if (layer instanceof TextLayer && textDocument) {
            returnLayerInfo.text = textDocument.text;
            returnLayerInfo.fontFamily = textDocument.font;
            returnLayerInfo.fontSize = textDocument.fontSize;
            returnLayerInfo.fillColor = textDocument.fillColor;
        }

        // *** ADDED LOGGING HERE ***
        logToPanel("Final check before return:");
        logToPanel("  Changed Properties: " + changedProperties.join(", "));
        logToPanel("  Return Layer Info Font: " + (returnLayerInfo.fontFamily || "N/A")); 
        logToPanel("  TextDocument Font: " + (textDocument ? textDocument.font : "N/A"));

        return JSON.stringify({
            status: "success", message: "Layer properties updated successfully",
            layer: returnLayerInfo
        }, null, 2);
    } catch (error) {
        // Error handling remains similar, but add more specific checks if needed
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- batchSetLayerProperties: apply properties to multiple layers in one call ---
function batchSetLayerProperties(args) {
    try {
        var compName = args.compName || "";
        var operations = args.operations; // Array of {layerIndex, threeDLayer, position, scale, rotation, opacity, ...}

        if (!operations || !operations.length) {
            throw new Error("No operations provided. Pass an array of {layerIndex, ...properties}");
        }

        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; }
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }

        var results = [];
        for (var o = 0; o < operations.length; o++) {
            var op = operations[o];
            var layer = null;
            if (op.layerIndex !== undefined && op.layerIndex !== null) {
                if (op.layerIndex > 0 && op.layerIndex <= comp.numLayers) { layer = comp.layer(op.layerIndex); }
                else { results.push({ layerIndex: op.layerIndex, status: "error", message: "Layer index out of bounds" }); continue; }
            } else if (op.layerName) {
                for (var j = 1; j <= comp.numLayers; j++) {
                    if (comp.layer(j).name === op.layerName) { layer = comp.layer(j); break; }
                }
            }
            if (!layer) { results.push({ layerIndex: op.layerIndex, layerName: op.layerName, status: "error", message: "Layer not found" }); continue; }

            var changed = [];
            if (op.threeDLayer !== undefined && op.threeDLayer !== null) { layer.threeDLayer = !!op.threeDLayer; changed.push("threeDLayer"); }
            if (op.position !== undefined && op.position !== null) {
                var posProp = layer.property("Position");
                if (posProp.numKeys > 0) {
                    while (posProp.numKeys > 0) { posProp.removeKey(1); }
                }
                posProp.setValue(op.position);
                changed.push("position");
            }
            if (op.scale !== undefined && op.scale !== null) { layer.property("Scale").setValue(op.scale); changed.push("scale"); }
            if (op.rotation !== undefined && op.rotation !== null) {
                if (layer.threeDLayer) { layer.property("Z Rotation").setValue(op.rotation); }
                else { layer.property("Rotation").setValue(op.rotation); }
                changed.push("rotation");
            }
            if (op.opacity !== undefined && op.opacity !== null) { layer.property("Opacity").setValue(op.opacity); changed.push("opacity"); }
            if (op.blendMode !== undefined && op.blendMode !== null) {
                var bModes = {"normal":BlendingMode.NORMAL,"add":BlendingMode.ADD,"multiply":BlendingMode.MULTIPLY,"screen":BlendingMode.SCREEN,"overlay":BlendingMode.OVERLAY,"softLight":BlendingMode.SOFT_LIGHT,"hardLight":BlendingMode.HARD_LIGHT,"darken":BlendingMode.DARKEN,"lighten":BlendingMode.LIGHTEN,"difference":BlendingMode.DIFFERENCE};
                if (bModes[op.blendMode] !== undefined) { layer.blendingMode = bModes[op.blendMode]; changed.push("blendMode"); }
            }
            if (op.startTime !== undefined && op.startTime !== null) { layer.startTime = op.startTime; changed.push("startTime"); }
            if (op.outPoint !== undefined && op.outPoint !== null) { layer.outPoint = op.outPoint; changed.push("outPoint"); }

            results.push({
                layerIndex: layer.index,
                name: layer.name,
                status: "success",
                threeDLayer: layer.threeDLayer,
                position: layer.property("Position").value,
                changedProperties: changed
            });
        }

        return JSON.stringify({ status: "success", results: results }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

/**
 * Sets a keyframe for a specific property on a layer.
 * Indices are 1-based for After Effects collections.
 * @param {number} compIndex - The index of the composition (1-based).
 * @param {number} layerIndex - The index of the layer within the composition (1-based).
 * @param {string} propertyName - The name of the property (e.g., "Position", "Scale", "Rotation", "Opacity").
 * @param {number} timeInSeconds - The time (in seconds) for the keyframe.
 * @param {any} value - The value for the keyframe (e.g., [x, y] for Position, [w, h] for Scale, angle for Rotation, percentage for Opacity).
 * @returns {string} JSON string indicating success or error.
 */
function setLayerKeyframe(compIndex, layerIndex, propertyName, timeInSeconds, value) {
    try {
        // Use 1-based indices as per After Effects API
        var comp = app.project.items[compIndex];
        if (!comp || !(comp instanceof CompItem)) {
            return JSON.stringify({ success: false, message: "Composition not found at index " + compIndex });
        }
        var layer = comp.layers[layerIndex];
        if (!layer) {
            return JSON.stringify({ success: false, message: "Layer not found at index " + layerIndex + " in composition '" + comp.name + "'"});
        }

        var transformGroup = layer.property("Transform");
        if (!transformGroup) {
             return JSON.stringify({ success: false, message: "Transform properties not found for layer '" + layer.name + "' (type: " + layer.matchName + ")." });
        }

        var property = transformGroup.property(propertyName);
        if (!property) {
            // Check other common property groups if not in Transform
             if (layer.property("Effects") && layer.property("Effects").property(propertyName)) {
                 property = layer.property("Effects").property(propertyName);
             } else if (layer.property("Text") && layer.property("Text").property(propertyName)) {
                 property = layer.property("Text").property(propertyName);
            } // Add more groups if needed (e.g., Masks, Shapes)

            if (!property) {
                 return JSON.stringify({ success: false, message: "Property '" + propertyName + "' not found on layer '" + layer.name + "'." });
            }
        }


        // Ensure the property can be keyframed
        if (!property.canVaryOverTime) {
             return JSON.stringify({ success: false, message: "Property '" + propertyName + "' cannot be keyframed." });
        }

        // Make sure the property is enabled for keyframing
        if (property.numKeys === 0 && !property.isTimeVarying) {
             property.setValueAtTime(comp.time, property.value); // Set initial keyframe if none exist
        }


        property.setValueAtTime(timeInSeconds, value);

        return JSON.stringify({ success: true, message: "Keyframe set for '" + propertyName + "' on layer '" + layer.name + "' at " + timeInSeconds + "s." });
    } catch (e) {
        return JSON.stringify({ success: false, message: "Error setting keyframe: " + e.toString() + " (Line: " + e.line + ")" });
    }
}


/**
 * Sets an expression for a specific property on a layer.
 * @param {number} compIndex - The index of the composition (1-based).
 * @param {number} layerIndex - The index of the layer within the composition (1-based).
 * @param {string} propertyName - The name of the property (e.g., "Position", "Scale", "Rotation", "Opacity").
 * @param {string} expressionString - The JavaScript expression string. Use "" to remove expression.
 * @returns {string} JSON string indicating success or error.
 */
function setLayerExpression(compIndex, layerIndex, propertyName, expressionString) {
    try {
         // Adjust indices to be 0-based for ExtendScript arrays
        var comp = app.project.items[compIndex];
         if (!comp || !(comp instanceof CompItem)) {
            return JSON.stringify({ success: false, message: "Composition not found at index " + compIndex });
        }
        var layer = comp.layers[layerIndex];
         if (!layer) {
            return JSON.stringify({ success: false, message: "Layer not found at index " + layerIndex + " in composition '" + comp.name + "'"});
        }

        var transformGroup = layer.property("Transform");
         if (!transformGroup) {
             // Allow expressions on non-transformable layers if property exists elsewhere
             // return JSON.stringify({ success: false, message: "Transform properties not found for layer '" + layer.name + "' (type: " + layer.matchName + ")." });
        }

        var property = transformGroup ? transformGroup.property(propertyName) : null;
         if (!property) {
            // Check other common property groups if not in Transform
             if (layer.property("Effects") && layer.property("Effects").property(propertyName)) {
                 property = layer.property("Effects").property(propertyName);
             } else if (layer.property("Text") && layer.property("Text").property(propertyName)) {
                 property = layer.property("Text").property(propertyName);
             }

            // Search inside individual effects for sub-properties
            if (!property && layer.property("Effects")) {
                var effects = layer.property("Effects");
                for (var ei = 1; ei <= effects.numProperties; ei++) {
                    var eff = effects.property(ei);
                    try {
                        var subProp = eff.property(propertyName);
                        if (subProp) { property = subProp; break; }
                    } catch (e2) {}
                }
            }

            if (!property) {
                 return JSON.stringify({ success: false, message: "Property '" + propertyName + "' not found on layer '" + layer.name + "'." });
            }
        }

        if (!property.canSetExpression) {
            return JSON.stringify({ success: false, message: "Property '" + propertyName + "' does not support expressions." });
        }

        property.expression = expressionString;

        var action = expressionString === "" ? "removed" : "set";
        return JSON.stringify({ success: true, message: "Expression " + action + " for '" + propertyName + "' on layer '" + layer.name + "'." });
    } catch (e) {
        return JSON.stringify({ success: false, message: "Error setting expression: " + e.toString() + " (Line: " + e.line + ")" });
    }
}

// --- applyEffect (from applyEffect.jsx) ---
function applyEffect(args) {
    try {
        // Extract parameters
        var compIndex = args.compIndex || 1; // Default to first comp
        var layerIndex = args.layerIndex || 1; // Default to first layer
        var effectName = args.effectName; // Name of the effect to apply
        var effectMatchName = args.effectMatchName; // After Effects internal name (more reliable)
        var effectCategory = args.effectCategory || ""; // Optional category for filtering
        var presetPath = args.presetPath; // Optional path to an effect preset
        var effectSettings = args.effectSettings || {}; // Optional effect parameters
        
        if (!effectName && !effectMatchName && !presetPath) {
            throw new Error("You must specify either effectName, effectMatchName, or presetPath");
        }
        
        // Find the composition by index
        var comp = app.project.item(compIndex);
        if (!comp || !(comp instanceof CompItem)) {
            throw new Error("Composition not found at index " + compIndex);
        }
        
        // Find the layer by index
        var layer = comp.layer(layerIndex);
        if (!layer) {
            throw new Error("Layer not found at index " + layerIndex + " in composition '" + comp.name + "'");
        }
        
        var effectResult;
        
        // Apply preset if a path is provided
        if (presetPath) {
            var presetFile = new File(presetPath);
            if (!presetFile.exists) {
                throw new Error("Effect preset file not found: " + presetPath);
            }
            
            // Apply the preset to the layer
            layer.applyPreset(presetFile);
            effectResult = {
                type: "preset",
                name: presetPath.split('/').pop().split('\\').pop(),
                applied: true
            };
        }
        // Apply effect by match name (more reliable method)
        else if (effectMatchName) {
            var effect = layer.Effects.addProperty(effectMatchName);
            effectResult = {
                type: "effect",
                name: effect.name,
                matchName: effect.matchName,
                index: effect.propertyIndex
            };
            
            // Apply settings if provided
            applyEffectSettings(effect, effectSettings);
        }
        // Apply effect by display name
        else {
            // Get the effect from the Effect menu
            var effect = layer.Effects.addProperty(effectName);
            effectResult = {
                type: "effect",
                name: effect.name,
                matchName: effect.matchName,
                index: effect.propertyIndex
            };
            
            // Apply settings if provided
            applyEffectSettings(effect, effectSettings);
        }
        
        return JSON.stringify({
            status: "success",
            message: "Effect applied successfully",
            effect: effectResult,
            layer: {
                name: layer.name,
                index: layerIndex
            },
            composition: {
                name: comp.name,
                index: compIndex
            }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({
            status: "error",
            message: error.toString()
        }, null, 2);
    }
}

// Helper function to apply effect settings
function applyEffectSettings(effect, settings) {
    // Skip if no settings are provided
    if (!settings) return;
    var hasKeys = false;
    for (var k in settings) { if (settings.hasOwnProperty(k)) { hasKeys = true; break; } }
    if (!hasKeys) return;
    
    // Iterate through all provided settings
    for (var propName in settings) {
        if (settings.hasOwnProperty(propName)) {
            try {
                // Find the property in the effect
                var property = null;
                
                // Try direct property access first
                try {
                    property = effect.property(propName);
                } catch (e) {
                    // If direct access fails, search through all properties
                    for (var i = 1; i <= effect.numProperties; i++) {
                        var prop = effect.property(i);
                        if (prop.name === propName) {
                            property = prop;
                            break;
                        }
                    }
                }
                
                // Set the property value if found
                if (property && property.setValue) {
                    property.setValue(settings[propName]);
                }
            } catch (e) {
                // Log error but continue with other properties
                $.writeln("Error setting effect property '" + propName + "': " + e.toString());
            }
        }
    }
}

// --- applyEffectTemplate (from applyEffectTemplate.jsx) ---
function applyEffectTemplate(args) {
    try {
        // Extract parameters
        var compIndex = args.compIndex || 1; // Default to first comp
        var layerIndex = args.layerIndex || 1; // Default to first layer
        var templateName = args.templateName; // Name of the template to apply
        var customSettings = args.customSettings || {}; // Optional customizations
        
        if (!templateName) {
            throw new Error("You must specify a templateName");
        }
        
        // Find the composition by index
        var comp = app.project.item(compIndex);
        if (!comp || !(comp instanceof CompItem)) {
            throw new Error("Composition not found at index " + compIndex);
        }
        
        // Find the layer by index
        var layer = comp.layer(layerIndex);
        if (!layer) {
            throw new Error("Layer not found at index " + layerIndex + " in composition '" + comp.name + "'");
        }
        
        // Template definitions
        var templates = {
            // Blur effects
            "gaussian-blur": {
                effectMatchName: "ADBE Gaussian Blur 2",
                settings: {
                    "Blurriness": customSettings.blurriness || 20
                }
            },
            "directional-blur": {
                effectMatchName: "ADBE Directional Blur",
                settings: {
                    "Direction": customSettings.direction || 0,
                    "Blur Length": customSettings.length || 10
                }
            },
            
            // Color correction effects
            "color-balance": {
                effectMatchName: "ADBE Color Balance (HLS)",
                settings: {
                    "Hue": customSettings.hue || 0,
                    "Lightness": customSettings.lightness || 0,
                    "Saturation": customSettings.saturation || 0
                }
            },
            "brightness-contrast": {
                effectMatchName: "ADBE Brightness & Contrast 2",
                settings: {
                    "Brightness": customSettings.brightness || 0,
                    "Contrast": customSettings.contrast || 0,
                    "Use Legacy": false
                }
            },
            "curves": {
                effectMatchName: "ADBE CurvesCustom",
                // Curves are complex and would need special handling
            },
            
            // Stylistic effects
            "glow": {
                effectMatchName: "ADBE Glow",
                settings: {
                    "Glow Threshold": customSettings.threshold || 50,
                    "Glow Radius": customSettings.radius || 15,
                    "Glow Intensity": customSettings.intensity || 1
                }
            },
            "drop-shadow": {
                effectMatchName: "ADBE Drop Shadow",
                settings: {
                    "Shadow Color": customSettings.color || [0, 0, 0, 1],
                    "Opacity": customSettings.opacity || 50,
                    "Direction": customSettings.direction || 135,
                    "Distance": customSettings.distance || 10,
                    "Softness": customSettings.softness || 10
                }
            },
            
            // Common effect chains
            "cinematic-look": {
                effects: [
                    {
                        effectMatchName: "ADBE CurvesCustom",
                        settings: {}
                    },
                    {
                        effectMatchName: "ADBE Vibrance",
                        settings: {
                            "Vibrance": 15,
                            "Saturation": -5
                        }
                    }
                ]
            },
            "text-pop": {
                effects: [
                    {
                        effectMatchName: "ADBE Drop Shadow",
                        settings: {
                            "Shadow Color": [0, 0, 0, 1],
                            "Opacity": 75,
                            "Distance": 5,
                            "Softness": 10
                        }
                    },
                    {
                        effectMatchName: "ADBE Glo2",
                        settings: {
                            "Glow Threshold": 50,
                            "Glow Radius": 10,
                            "Glow Intensity": 1.5
                        }
                    }
                ]
            }
        };
        
        // Check if the requested template exists
        var template = templates[templateName];
        if (!template) {
            var availableTemplates = Object.keys(templates).join(", ");
            throw new Error("Template '" + templateName + "' not found. Available templates: " + availableTemplates);
        }
        
        var appliedEffects = [];
        
        // Apply single effect or multiple effects based on template structure
        if (template.effectMatchName) {
            // Single effect template
            var effect = layer.Effects.addProperty(template.effectMatchName);
            
            // Apply settings
            for (var propName in template.settings) {
                try {
                    var property = effect.property(propName);
                    if (property) {
                        property.setValue(template.settings[propName]);
                    }
                } catch (e) {
                    $.writeln("Warning: Could not set " + propName + " on effect " + effect.name + ": " + e);
                }
            }
            
            appliedEffects.push({
                name: effect.name,
                matchName: effect.matchName
            });
        } else if (template.effects) {
            // Multiple effects template
            for (var i = 0; i < template.effects.length; i++) {
                var effectData = template.effects[i];
                var effect = layer.Effects.addProperty(effectData.effectMatchName);
                
                // Apply settings
                for (var propName in effectData.settings) {
                    try {
                        var property = effect.property(propName);
                        if (property) {
                            property.setValue(effectData.settings[propName]);
                        }
                    } catch (e) {
                        $.writeln("Warning: Could not set " + propName + " on effect " + effect.name + ": " + e);
                    }
                }
                
                appliedEffects.push({
                    name: effect.name,
                    matchName: effect.matchName
                });
            }
        }
        
        return JSON.stringify({
            status: "success",
            message: "Effect template '" + templateName + "' applied successfully",
            appliedEffects: appliedEffects,
            layer: {
                name: layer.name,
                index: layerIndex
            },
            composition: {
                name: comp.name,
                index: compIndex
            }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({
            status: "error",
            message: error.toString()
        }, null, 2);
    }
}

// --- End of Function Definitions ---

// --- Bridge test function to verify communication and effects application ---
function bridgeTestEffects(args) {
    try {
        var compIndex = (args && args.compIndex) ? args.compIndex : 1;
        var layerIndex = (args && args.layerIndex) ? args.layerIndex : 1;

        // Apply a light Gaussian Blur
        var blurRes = JSON.parse(applyEffect({
            compIndex: compIndex,
            layerIndex: layerIndex,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectSettings: { "Blurriness": 5 }
        }));

        // Apply a simple drop shadow via template
        var shadowRes = JSON.parse(applyEffectTemplate({
            compIndex: compIndex,
            layerIndex: layerIndex,
            templateName: "drop-shadow"
        }));

        return JSON.stringify({
            status: "success",
            message: "Bridge test effects applied.",
            results: [blurRes, shadowRes]
        }, null, 2);
    } catch (e) {
        return JSON.stringify({ status: "error", message: e.toString() }, null, 2);
    }
}

// --- executeAtomScript: Execute compiled ExtendScript code from AI compiler ---
function executeAtomScript(args) {
    try {
        var scriptContent = args.scriptContent || "";
        if (!scriptContent || scriptContent.length === 0) {
            throw new Error("No script content provided");
        }

        var result = {};
        var outputLines = [];
        
        function logScript(msg) {
            outputLines.push(msg);
        }

        var logBackup = $.writeln;
        $.writeln = logScript;

        try {
            result = eval(scriptContent);
        } catch (scriptError) {
            throw new Error("Script execution error: " + scriptError.toString() + 
                (scriptError.line ? " (line: " + scriptError.line + ")" : ""));
        } finally {
            $.writeln = logBackup;
        }

        return JSON.stringify({
            status: "success",
            message: "Atom script executed successfully",
            scriptLength: scriptContent.length,
            outputLines: outputLines,
            result: result || {}
        }, null, 2);

    } catch (error) {
        return JSON.stringify({
            status: "error",
            message: error.toString(),
            line: error.line,
            fileName: error.fileName
        }, null, 2);
    }
}

// --- applySilhouetteMatte: 导入Silhouette Matte序列并设置Track Matte ---
function applySilhouetteMatte(args) {
    try {
        var mattePath = args.mattePath || "";
        if (!mattePath) {
            return JSON.stringify({ status: "error", message: "mattePath 参数必填" }, null, 2);
        }

        // 替换 [####] 为 AE 可识别的序列格式
        // AE 序列导入需要选中第一帧
        var aePath = mattePath.replace("[####]", "0001");
        if (aePath.indexOf("%04d") !== -1) {
            aePath = aePath.replace("%04d", "0001");
        }

        var matteFile = new File(aePath);
        if (!matteFile.exists) {
            // 尝试在同级目录找第一个匹配的文件
            var parentFolder = matteFile.parent;
            var pattern = matteFile.name.replace("0001", "*");
            var files = parentFolder.getFiles(pattern);
            if (files.length > 0) {
                aePath = files[0].fsName;
            } else {
                return JSON.stringify({ status: "error", message: "Matte文件不存在: " + aePath }, null, 2);
            }
        }

        app.beginUndoGroup("Apply Silhouette Matte");

        // 1. 导入 Matte 序列
        var importOptions = new ImportOptions(new File(aePath));
        importOptions.sequence = true;
        var matteFootage = app.project.importFile(importOptions);

        // 2. 获取当前活动合成
        var comp = app.project.activeItem;
        if (!(comp instanceof CompItem)) {
            // 尝找第一个合成
            for (var i = 1; i <= app.project.numItems; i++) {
                if (app.project.item(i) instanceof CompItem) {
                    comp = app.project.item(i);
                    break;
                }
            }
        }
        if (!comp) {
            app.endUndoGroup();
            return JSON.stringify({ status: "error", message: "未找到活动合成" }, null, 2);
        }

        // 3. 将 Matte 添加到合成（放在最上层）
        var matteLayer = comp.layers.add(matteFootage);
        matteLayer.name = "Silhouette_Matte";
        matteLayer.enabled = false; // 隐藏 Matte 图层

        // 4. 设置目标图层的 Track Matte
        var targetLayer = null;
        if (args.targetLayer && args.targetLayer !== "") {
            // 按名称查找目标图层
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === args.targetLayer) {
                    targetLayer = comp.layer(j);
                    break;
                }
            }
        }
        if (!targetLayer) {
            // 默认使用 Matte 下方的图层（即原来的最上层）
            targetLayer = comp.layer(matteLayer.index + 1);
        }

        // 5. 设置 Track Matte 类型
        var matteMode = args.matteMode || "alpha";
        var matteMap = {
            "alpha": TrackMatteType.ALPHA,
            "luma": TrackMatteType.LUMA,
            "alpha_inverted": TrackMatteType.ALPHA_INVERTED,
            "luma_inverted": TrackMatteType.LUMA_INVERTED
        };
        var matteType = matteMap[matteMode] || TrackMatteType.ALPHA;
        targetLayer.trackMatteType = matteType;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "Silhouette Matte 已导入并设置 Track Matte",
            matteLayer: matteLayer.name,
            matteLayerIndex: matteLayer.index,
            targetLayer: targetLayer.name,
            targetLayerIndex: targetLayer.index,
            matteMode: matteMode,
            compName: comp.name
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- applySilhouetteTracking: 将Silhouette跟踪数据应用到AE图层 ---
function applySilhouetteTracking(args) {
    try {
        var trackingDataPath = args.trackingDataPath || "";
        if (!trackingDataPath) {
            return JSON.stringify({ status: "error", message: "trackingDataPath 参数必填" }, null, 2);
        }

        // 读取跟踪数据 JSON
        var trackFile = new File(trackingDataPath);
        if (!trackFile.exists) {
            return JSON.stringify({ status: "error", message: "跟踪数据文件不存在: " + trackingDataPath }, null, 2);
        }

        trackFile.open("r");
        var trackContent = trackFile.read();
        trackFile.close();
        var trackData = JSON.parse(trackContent);

        // 获取当前活动合成
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
            return JSON.stringify({ status: "error", message: "未找到活动合成" }, null, 2);
        }

        // 获取目标图层
        var targetLayer = null;
        if (args.targetLayer && args.targetLayer !== "") {
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === args.targetLayer) {
                    targetLayer = comp.layer(j);
                    break;
                }
            }
        }
        if (!targetLayer) {
            targetLayer = comp.selectedLayers[0] || comp.layer(1);
        }
        if (!targetLayer) {
            return JSON.stringify({ status: "error", message: "未找到目标图层" }, null, 2);
        }

        // 应用跟踪数据
        var applyTo = args.applyTo || "position";
        var trackers = trackData.trackers || [];
        var keyframeCount = 0;

        app.beginUndoGroup("Apply Silhouette Tracking");

        for (var t = 0; t < trackers.length; t++) {
            var tracker = trackers[t];
            var frames = tracker.frames || [];
            for (var f = 0; f < frames.length; f++) {
                var frameData = frames[f];
                var frameNum = frameData.frame || f;
                var time = frameNum / (trackData.fps || 24.0);

                var prop = null;
                if (applyTo === "position") {
                    prop = targetLayer.property("ADBE Transform Group").property("ADBE Position");
                } else if (applyTo === "anchor") {
                    prop = targetLayer.property("ADBE Transform Group").property("ADBE Anchor Point");
                } else if (applyTo === "scale") {
                    prop = targetLayer.property("ADBE Transform Group").property("ADBE Scale");
                } else if (applyTo === "rotation") {
                    prop = targetLayer.property("ADBE Transform Group").property("ADBE Rotate Z");
                }

                if (prop) {
                    if (applyTo === "scale") {
                        var sx = frameData.x || 100;
                        var sy = frameData.y || 100;
                        prop.setValueAtTime(time, [sx, sy]);
                    } else if (applyTo === "rotation") {
                        prop.setValueAtTime(time, frameData.x || 0);
                    } else {
                        prop.setValueAtTime(time, [frameData.x || 0, frameData.y || 0]);
                    }
                    keyframeCount++;
                }
            }
        }

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "跟踪数据已应用到图层",
            targetLayer: targetLayer.name,
            applyTo: applyTo,
            keyframeCount: keyframeCount,
            trackerCount: trackers.length
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- importSilhouettePaint: 导入Silhouette Paint修复结果 ---
function importSilhouettePaint(args) {
    try {
        var paintPath = args.paintPath || "";
        if (!paintPath) {
            return JSON.stringify({ status: "error", message: "paintPath 参数必填" }, null, 2);
        }

        // 替换序列帧通配符
        var aePath = paintPath.replace("[####]", "0001").replace("%04d", "0001");
        var paintFile = new File(aePath);
        if (!paintFile.exists) {
            var parentFolder = paintFile.parent;
            var pattern = paintFile.name.replace("0001", "*");
            var files = parentFolder.getFiles(pattern);
            if (files.length > 0) {
                aePath = files[0].fsName;
            } else {
                return JSON.stringify({ status: "error", message: "Paint文件不存在: " + aePath }, null, 2);
            }
        }

        app.beginUndoGroup("Import Silhouette Paint");

        // 导入 Paint 序列
        var importOptions = new ImportOptions(new File(aePath));
        importOptions.sequence = true;
        var paintFootage = app.project.importFile(importOptions);

        // 添加到合成
        var comp = app.project.activeItem;
        if (comp instanceof CompItem) {
            var paintLayer = comp.layers.add(paintFootage);
            paintLayer.name = "Silhouette_Paint_" + (args.paintMode || "clone");
            app.endUndoGroup();
            return JSON.stringify({
                status: "success",
                message: "Silhouette Paint 修复结果已导入",
                paintLayer: paintLayer.name,
                paintLayerIndex: paintLayer.index,
                compName: comp.name
            }, null, 2);
        } else {
            app.endUndoGroup();
            return JSON.stringify({
                status: "success",
                message: "Paint 修复结果已导入到项目（未找到活动合成）",
                footageName: paintFootage.name
            }, null, 2);
        }
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- setTrackMatte: 设置图层的Track Matte类型 ---
function setTrackMatte(args) {
    try {
        var matteType = args.matteType || "alpha";
        var matteMap = {
            "alpha": TrackMatteType.ALPHA,
            "luma": TrackMatteType.LUMA,
            "alpha_inverted": TrackMatteType.ALPHA_INVERTED,
            "luma_inverted": TrackMatteType.LUMA_INVERTED,
            "none": TrackMatteType.NO_TRACK_MATTE
        };

        var comp = app.project.activeItem;
        if (!(comp instanceof CompItem)) {
            return JSON.stringify({ status: "error", message: "未找到活动合成" }, null, 2);
        }

        // 获取目标图层
        var targetLayer = null;
        if (args.targetLayer && args.targetLayer !== "") {
            for (var j = 1; j <= comp.numLayers; j++) {
                if (comp.layer(j).name === args.targetLayer) {
                    targetLayer = comp.layer(j);
                    break;
                }
            }
        }
        if (!targetLayer) {
            targetLayer = comp.selectedLayers[0] || comp.layer(1);
        }
        if (!targetLayer) {
            return JSON.stringify({ status: "error", message: "未找到目标图层" }, null, 2);
        }

        // 如果提供了 matteLayer 名称，确保遮罩图层在目标图层上方
        if (args.matteLayer && args.matteLayer !== "") {
            var matteLayer = null;
            for (var k = 1; k <= comp.numLayers; k++) {
                if (comp.layer(k).name === args.matteLayer) {
                    matteLayer = comp.layer(k);
                    break;
                }
            }
            if (matteLayer && matteLayer.index > targetLayer.index) {
                matteLayer.moveBefore(targetLayer);
            }
        }

        app.beginUndoGroup("Set Track Matte");
        targetLayer.trackMatteType = matteMap[matteType] || TrackMatteType.ALPHA;
        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "Track Matte 设置成功",
            targetLayer: targetLayer.name,
            matteType: matteType
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- importFootage: Import video/image/audio files into AE project ---
function importFootage(args) {
    try {
        var filePath = args.filePath || "";
        if (!filePath) {
            throw new Error("File path is required");
        }

        var file = new File(filePath);
        if (!file.exists) {
            throw new Error("File not found: " + filePath);
        }

        var importedItems = app.project.importFile(file);
        
        if (importedItems instanceof Array) {
            var itemsInfo = [];
            for (var i = 0; i < importedItems.length; i++) {
                var item = importedItems[i];
                itemsInfo.push({
                    name: item.name,
                    type: item instanceof FootageItem ? "footage" : 
                          item instanceof CompItem ? "composition" : 
                          item instanceof FolderItem ? "folder" : "unknown",
                    id: item.id,
                    width: item.width || 0,
                    height: item.height || 0,
                    duration: item.duration || 0,
                    frameRate: item.frameRate || 0
                });
            }
            return JSON.stringify({
                status: "success",
                message: "Successfully imported " + itemsInfo.length + " file(s)",
                importedItems: itemsInfo
            }, null, 2);
        } else {
            var item = importedItems;
            return JSON.stringify({
                status: "success",
                message: "Successfully imported: " + item.name,
                importedItems: [{
                    name: item.name,
                    type: item instanceof FootageItem ? "footage" : 
                          item instanceof CompItem ? "composition" : 
                          item instanceof FolderItem ? "folder" : "unknown",
                    id: item.id,
                    width: item.width || 0,
                    height: item.height || 0,
                    duration: item.duration || 0,
                    frameRate: item.frameRate || 0
                }]
            }, null, 2);
        }

    } catch (error) {
        return JSON.stringify({
            status: "error",
            message: error.toString(),
            line: error.line,
            fileName: error.fileName
        }, null, 2);
    }
}

// --- placeFootageInComp: Place imported footage into a composition ---
function placeFootageInComp(args) {
    try {
        var compIndex = parseInt(args.compIndex) || 1;
        var footageName = args.footageName || "";
        var startTime = parseFloat(args.startTime) || 0;
        var layerName = args.layerName || "";

        var comp = app.project.item(compIndex);
        if (!(comp instanceof CompItem)) {
            throw new Error("Invalid composition index: " + compIndex);
        }

        var footageItem = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof FootageItem && item.name === footageName) {
                footageItem = item;
                break;
            }
        }

        if (!footageItem) {
            throw new Error("Footage item not found: " + footageName);
        }

        var layer = comp.layers.add(footageItem);
        layer.startTime = startTime;
        
        if (layerName) {
            layer.name = layerName;
        }

        return JSON.stringify({
            status: "success",
            message: "Footage placed in composition",
            layer: {
                name: layer.name,
                index: layer.index,
                startTime: layer.startTime,
                inPoint: layer.inPoint,
                outPoint: layer.outPoint,
                footageName: footageName
            },
            composition: {
                name: comp.name,
                index: compIndex
            }
        }, null, 2);

    } catch (error) {
        return JSON.stringify({
            status: "error",
            message: error.toString(),
            line: error.line,
            fileName: error.fileName
        }, null, 2);
    }
}

function createE2EMusicVideo(args) {
    try {
        var compName = args.compName || "E2E_音乐视频";
        // 参数化：移除硬编码默认值，frameDir 必填
        // 原硬编码值: var frameDir = args.frameDir || "D:/AE-Work/视频素材库/frames";
        var frameDir = args.frameDir;
        if (!frameDir) {
            return JSON.stringify({ success: false, status: "error", message: "frameDir 参数必填（args.frameDir）" }, null, 2);
        }
        var bgmPath = args.bgmPath || "";
        var beatTimes = args.beatTimes || [];
        var energyPeaks = args.energyPeaks || [];
        var peakValues = args.peakValues || [];
        var bpm = args.bpm || 120;
        var compWidth = args.width || 576;
        var compHeight = args.height || 768;
        var compDuration = args.duration || 12;
        var compFPS = args.fps || 30;
        var mattePath = args.mattePath || "";
        var cx = compWidth / 2;
        var cy = compHeight / 2;

        function setEase(prop, easeVal) {
            try {
                var val = prop.value;
                var dim = 1;
                if (val instanceof Array) dim = val.length;
                var inArr = [];
                var outArr = [];
                for (var i = 0; i < dim; i++) {
                    inArr.push(new KeyframeEase(0, easeVal));
                    outArr.push(new KeyframeEase(0, easeVal));
                }
                for (var k = 1; k <= prop.numKeys; k++) {
                    prop.setTemporalEaseAtKey(k, inArr, outArr);
                }
            } catch(e) {}
        }

        var results = [];

        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name == compName && app.project.item(i) instanceof CompItem) {
                app.project.item(i).remove();
                break;
            }
        }

        var comp = app.project.items.addComp(compName, compWidth, compHeight, 1, compDuration, compFPS);
        results.push({ phase: "Phase1", status: "success", message: "合成创建成功: " + compName });

        var frameFiles = [];
        for (var f = 1; f <= 18; f++) {
            var num = f < 10 ? "00" + f : (f < 100 ? "0" + f : "" + f);
            var fp = new File(frameDir + "/frame_" + num + ".png");
            if (fp.exists) {
                var importOpts = new ImportOptions(fp);
                importOpts.sequence = false;
                var footage = app.project.importFile(importOpts);
                footage.name = "Frame_" + num;
                frameFiles.push(footage);
            }
        }

        if (frameFiles.length === 0) {
            return JSON.stringify({ success: false, status: "error", message: "帧目录中没有图片文件" }, null, 2);
        }
        results.push({ phase: "Phase1", status: "success", message: "导入 " + frameFiles.length + " 帧" });

        app.beginUndoGroup("Create E2E Music Video");

        var seqComp = app.project.items.addComp("FrameSeq", compWidth, compHeight, 1, 0.6, compFPS);
        for (var i = 0; i < frameFiles.length; i++) {
            var layer = seqComp.layers.add(frameFiles[i]);
            layer.startTime = i * (1/compFPS);
            layer.outPoint = (i + 1) * (1/compFPS);
        }
        seqComp.duration = frameFiles.length * (1/compFPS);
        results.push({ phase: "Phase1", status: "success", message: "帧序列预合成完成" });

        var saitama = comp.layers.add(seqComp);
        saitama.name = "Saitama_Main";
        saitama.stretch = -50;
        saitama.motionBlur = true;
        saitama.threeDLayer = true;
        saitama.position.setValueAtTime(0, [cx, cy, 0]);
        saitama.outPoint = compDuration;
        try { saitama.timeRemapEnabled = true; } catch(e) {}
        try {
            var tr = saitama.property("ADBE Time Remapping");
            if (tr && tr.numKeys > 0) {
                var loopEnd = tr.keyValue(tr.numKeys);
                for (var t = loopEnd; t < compDuration; t += loopEnd) {
                    tr.setValueAtTime(t, 0);
                    tr.setValueAtTime(t + loopEnd, loopEnd);
                }
            }
        } catch(e) {}

        var matteLayer = null;
        if (mattePath && new File(mattePath).exists) {
            var matteImportOpts = new ImportOptions(new File(mattePath));
            matteImportOpts.sequence = true;
            var matteFootage = app.project.importFile(matteImportOpts);
            matteFootage.name = "Silhouette_Matte";
            matteLayer = comp.layers.add(matteFootage);
            matteLayer.name = "Silhouette_Matte";
            matteLayer.threeDLayer = true;
            matteLayer.position.setValueAtTime(0, [cx, cy, 0]);
            matteLayer.outPoint = compDuration;
            matteLayer.enabled = false;
            saitama.trackMatteType = TrackMatteType.ALPHA;
            saitama.trackMatteLayer = matteLayer;
            results.push({ phase: "Phase2", status: "success", message: "已应用 Silhouette Roto Matte" });
        } else {
            try {
                var key = saitama.property("ADBE Effect Parade").addProperty("ADBE Color Key");
                if (key) {
                    try { key.property("ADBE Color Key-0001").setValue([1.0, 1.0, 1.0]); } catch(e) {}
                    try { key.property("Color Tolerance").setValue(30); } catch(e) {}
                    try { key.property("Edge Feather").setValue(2); } catch(e) {}
                }
            } catch(e) {}

            try {
                var mc = saitama.property("ADBE Effect Parade").addProperty("ADBE Matte Choker");
                if (mc) {
                    try { mc.property(1).setValue(0.15); } catch(e) {}
                    try { mc.property(2).setValue(0.08); } catch(e) {}
                }
            } catch(e) {}
            results.push({ phase: "Phase2", status: "success", message: "已应用 Color Key 抠图" });
        }

        try {
            var glow = saitama.property("ADBE Effect Parade").addProperty("ADBE Glow");
            if (glow) {
                try { glow.property(1).setValue(60); } catch(e) {}
                try { glow.property(2).setValue(1.2); } catch(e) {}
                try { glow.property(3).setValue(1.0); } catch(e) {}
                for (var b = 0; b < beatTimes.length; b++) {
                    var bt = beatTimes[b];
                    if (bt > compDuration) break;
                    try { glow.property(1).setValueAtTime(bt, 150); } catch(e) {}
                    try { glow.property(1).setValueAtTime(bt + 0.15, 60); } catch(e) {}
                }
            }
        } catch(e) {}

        try {
            var sScale = saitama.property("ADBE Transform Group").property("ADBE Scale");
            sScale.setValueAtTime(0, [100, 100, 100]);
            sScale.setValueAtTime(2, [108, 108, 108]);
            sScale.setValueAtTime(4, [100, 100, 100]);
            sScale.setValueAtTime(6, [105, 105, 105]);
            sScale.setValueAtTime(8, [100, 100, 100]);
            sScale.setValueAtTime(10, [108, 108, 108]);
            sScale.setValueAtTime(compDuration, [100, 100, 100]);
            setEase(sScale, 60);
        } catch(e) {}

        results.push({ phase: "Phase2", status: "success", message: "Saitama_Main层效果添加完成" });

        var cape = comp.layers.add(seqComp);
        cape.name = "Cape_Layer";
        cape.stretch = -50;
        cape.motionBlur = true;
        cape.threeDLayer = true;
        cape.position.setValueAtTime(0, [cx + 10, cy + 5, -30]);
        cape.scale.setValueAtTime(0, [105, 105, 105]);
        cape.opacity.setValueAtTime(0, 90);
        cape.outPoint = compDuration;
        try { cape.timeRemapEnabled = true; } catch(e) {}
        try {
            var tr2 = cape.property("ADBE Time Remapping");
            if (tr2 && tr2.numKeys > 0) {
                var loopEnd2 = tr2.keyValue(tr2.numKeys);
                for (var t2 = loopEnd2; t2 < compDuration; t2 += loopEnd2) {
                    tr2.setValueAtTime(t2, 0);
                    tr2.setValueAtTime(t2 + loopEnd2, loopEnd2);
                }
            }
        } catch(e) {}

        if (matteLayer) {
            var capeMatte = matteLayer.duplicate();
            capeMatte.name = "Silhouette_Matte_Cape";
            capeMatte.enabled = false;
            cape.trackMatteType = TrackMatteType.ALPHA;
            cape.trackMatteLayer = capeMatte;
        } else {
            try {
                var key2 = cape.property("ADBE Effect Parade").addProperty("ADBE Color Key");
                if (key2) {
                    try { key2.property("ADBE Color Key-0001").setValue([1.0, 1.0, 1.0]); } catch(e) {}
                    try { key2.property("Color Tolerance").setValue(25); } catch(e) {}
                    try { key2.property("Edge Feather").setValue(1.5); } catch(e) {}
                }
            } catch(e) {}
        }

        try {
            var glow2 = cape.property("ADBE Effect Parade").addProperty("ADBE Glow");
            if (glow2) {
                try { glow2.property(1).setValue(80); } catch(e) {}
                try { glow2.property(2).setValue(2.0); } catch(e) {}
                try { glow2.property(3).setValue(1.5); } catch(e) {}
            }
        } catch(e) {}

        try {
            var cRot = cape.property("ADBE Transform Group").property("ADBE Rotation");
            cRot.setValueAtTime(0, [0, 0, -5]);
            cRot.setValueAtTime(1.5, [0, 0, 5]);
            cRot.setValueAtTime(3, [0, 0, -3]);
            cRot.setValueAtTime(4.5, [0, 0, 4]);
            cRot.setValueAtTime(6, [0, 0, -4]);
            cRot.setValueAtTime(7.5, [0, 0, 3]);
            cRot.setValueAtTime(9, [0, 0, -5]);
            cRot.setValueAtTime(10.5, [0, 0, 4]);
            cRot.setValueAtTime(compDuration, [0, 0, -5]);
            setEase(cRot, 70);
        } catch(e) {}

        results.push({ phase: "Phase3", status: "success", message: "Cape_Layer披风层创建完成" });

        var sky = comp.layers.addSolid([0.01, 0.01, 0.05], "Sky_BG", compWidth, compHeight, 1, compDuration);
        sky.shy = true;
        try {
            var ramp = sky.property("ADBE Effect Parade").addProperty("ADBE Ramp");
            if (ramp) {
                try { ramp.property(1).setValue([cx, 80]); } catch(e) {}
                try { ramp.property(2).setValue([0.08, 0.05, 0.15]); } catch(e) {}
                try { ramp.property(3).setValue([cx, compHeight - 50]); } catch(e) {}
                try { ramp.property(4).setValue([0.005, 0.005, 0.02]); } catch(e) {}
            }
        } catch(e) {}
        try {
            var fn2 = sky.property("ADBE Effect Parade").addProperty("ADBE Fractal Noise");
            if (fn2) {
                try { fn2.property(1).setValue(4); } catch(e) {}
                try { fn2.property(2).setValue(1); } catch(e) {}
                try { fn2.property(8).setValue(300); } catch(e) {}
                try { fn2.property(11).setValue(1); } catch(e) {}
            }
        } catch(e) {}
        sky.opacity.setValueAtTime(0, 80);

        var p_bg = comp.layers.addSolid([0.03, 0.03, 0.08], "P_BG", compWidth, compHeight, 1, compDuration);
        p_bg.threeDLayer = true;
        p_bg.position.setValueAtTime(0, [cx, cy, 600]);
        p_bg.shy = true;
        try {
            var pw_bg = p_bg.property("ADBE Effect Parade").addProperty("CC Particle World");
            if (pw_bg) {
                try { pw_bg.property("CC Particle World-0001").setValue(0.3); } catch(e) {}
                try { pw_bg.property("CC Particle World-0002").setValue(3.0); } catch(e) {}
                try { pw_bg.property("CC Particle World-0012").setValue(0.015); } catch(e) {}
                try { pw_bg.property("CC Particle World-0018").setValue(60); } catch(e) {}
            }
        } catch(e) {}

        var p_mid = comp.layers.addSolid([0.05, 0.05, 0.12], "P_MID", compWidth, compHeight, 1, compDuration);
        p_mid.threeDLayer = true;
        p_mid.position.setValueAtTime(0, [cx, cy, 150]);
        p_mid.shy = true;
        try {
            var pw_mid = p_mid.property("ADBE Effect Parade").addProperty("CC Particle World");
            if (pw_mid) {
                try { pw_mid.property("CC Particle World-0001").setValue(0.8); } catch(e) {}
                try { pw_mid.property("CC Particle World-0002").setValue(2.0); } catch(e) {}
                try { pw_mid.property("CC Particle World-0012").setValue(0.04); } catch(e) {}
                try { pw_mid.property("CC Particle World-0018").setValue(35); } catch(e) {}
            }
        } catch(e) {}

        var p_fg = comp.layers.addSolid([0.08, 0.08, 0.15], "P_FG", compWidth, compHeight, 1, compDuration);
        p_fg.threeDLayer = true;
        p_fg.position.setValueAtTime(0, [cx, cy, -80]);
        p_fg.shy = true;
        try {
            var pw_fg = p_fg.property("ADBE Effect Parade").addProperty("CC Particle World");
            if (pw_fg) {
                try { pw_fg.property("CC Particle World-0001").setValue(1.5); } catch(e) {}
                try { pw_fg.property("CC Particle World-0002").setValue(1.2); } catch(e) {}
                try { pw_fg.property("CC Particle World-0012").setValue(0.06); } catch(e) {}
                try { pw_fg.property("CC Particle World-0018").setValue(20); } catch(e) {}
                for (var ep = 0; ep < energyPeaks.length; ep++) {
                    var pt = energyPeaks[ep];
                    if (pt > compDuration) break;
                    var pv = peakValues[ep] || 0.1;
                    var br_val = 1.5 + pv * 12;
                    try { pw_fg.property("CC Particle World-0001").setValueAtTime(pt, br_val); } catch(e) {}
                    try { pw_fg.property("CC Particle World-0001").setValueAtTime(pt + 0.2, 1.5); } catch(e) {}
                }
            }
        } catch(e) {}
        results.push({ phase: "Phase4", status: "success", message: "三层粒子系统创建完成" });

        var fog = comp.layers.addSolid([0.5, 0.5, 0.5], "Fog_Overlay", compWidth, compHeight, 1, compDuration);
        fog.blendingMode = BlendingMode.SCREEN;
        fog.opacity.setValueAtTime(0, 20);
        fog.shy = true;
        try {
            var fn = fog.property("ADBE Effect Parade").addProperty("ADBE Fractal Noise");
            if (fn) {
                try { fn.property(1).setValue(6); } catch(e) {}
                try { fn.property(2).setValue(1); } catch(e) {}
                try { fn.property(8).setValue(250); } catch(e) {}
                try { fn.property(11).setValue(2); } catch(e) {}
            }
        } catch(e) {}

        var vig = comp.layers.addSolid([0, 0, 0], "Vignette", compWidth, compHeight, 1, compDuration);
        vig.blendingMode = BlendingMode.MULTIPLY;
        vig.opacity.setValueAtTime(0, 35);
        vig.shy = true;
        try {
            var ellipse = vig.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
            if (ellipse) {
                try {
                    ellipse.property("ADBE Mask Shape").setValue([
                        [cx - compWidth * 0.4, cy - compHeight * 0.45],
                        [cx + compWidth * 0.4, cy - compHeight * 0.45],
                        [cx + compWidth * 0.4, cy + compHeight * 0.45],
                        [cx - compWidth * 0.4, cy + compHeight * 0.45]
                    ]);
                } catch(e) {}
                try { ellipse.property("ADBE Mask Feather").setValue([120, 120]); } catch(e) {}
                try { ellipse.property("ADBE Mask Inverted").setValue(true); } catch(e) {}
            }
        } catch(e) {}

        results.push({ phase: "Phase5", status: "success", message: "背景和大气效果创建完成" });

        var adj = comp.layers.addSolid([0.5, 0.5, 0.5], "Color_Adjust", compWidth, compHeight, 1, compDuration);
        adj.adjustmentLayer = true;
        adj.name = "Color_Adjust";
        adj.shy = true;

        try {
            var curves = adj.property("ADBE Effect Parade").addProperty("ADBE CurvesCustom");
            if (curves) {
                try { curves.property(1).setValue([[0,0],[0.15,0.05],[0.5,0.55],[0.85,0.92],[1,1]]); } catch(e) {}
            }
        } catch(e) {}

        try {
            var hueSat = adj.property("ADBE Effect Parade").addProperty("ADBE HUE SATURATION");
            if (hueSat) {
                try { hueSat.property(1).setValue(0); } catch(e) {}
                try { hueSat.property(2).setValue(20); } catch(e) {}
                try { hueSat.property(3).setValue(15); } catch(e) {}
            }
        } catch(e) {}

        try {
            var exposure = adj.property("ADBE Effect Parade").addProperty("ADBE Exposure");
            if (exposure) {
                try { exposure.property(1).setValue(0.3); } catch(e) {}
            }
        } catch(e) {}

        results.push({ phase: "Phase6", status: "success", message: "调整层创建完成" });

        var ctrl = comp.layers.addNull();
        ctrl.name = "Global_Controller";
        ctrl.shy = true;
        try {
            var sc1 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
            if (sc1) { sc1.name = "Speed"; try { sc1.property(1).setValue(100); } catch(e) {} }
            var sc2 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
            if (sc2) { sc2.name = "Glow_Intensity"; try { sc2.property(1).setValue(100); } catch(e) {} }
            var sc3 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
            if (sc3) { sc3.name = "Particle_Amount"; try { sc3.property(1).setValue(100); } catch(e) {} }
        } catch(e) {}

        var charControl = comp.layers.addNull();
        charControl.name = "Character_Control";
        charControl.threeDLayer = true;
        charControl.position.setValueAtTime(0, [cx, cy, 0]);
        charControl.shy = true;

        saitama.parent = charControl;
        cape.parent = charControl;

        try {
            var chPos = charControl.property("ADBE Transform Group").property("ADBE Position");
            chPos.setValueAtTime(0, [cx, cy, 0]);
            chPos.setValueAtTime(2, [cx, cy - 15, 20]);
            chPos.setValueAtTime(4, [cx + 10, cy + 5, -10]);
            chPos.setValueAtTime(6, [cx - 5, cy - 10, 15]);
            chPos.setValueAtTime(8, [cx + 5, cy + 10, -5]);
            chPos.setValueAtTime(10, [cx, cy - 5, 10]);
            chPos.setValueAtTime(compDuration, [cx, cy, 0]);
            setEase(chPos, 55);
        } catch(e) {}

        try {
            var chRot = charControl.property("ADBE Transform Group").property("ADBE Rotation");
            chRot.setValueAtTime(0, [0, 0, 0]);
            chRot.setValueAtTime(2, [0, 0, 3]);
            chRot.setValueAtTime(4, [0, 0, -2]);
            chRot.setValueAtTime(6, [0, 0, -3]);
            chRot.setValueAtTime(8, [0, 0, 2]);
            chRot.setValueAtTime(10, [0, 0, 1]);
            chRot.setValueAtTime(compDuration, [0, 0, 0]);
            setEase(chRot, 65);
        } catch(e) {}

        var camControl = comp.layers.addNull();
        camControl.name = "Camera_Control";
        camControl.threeDLayer = true;
        camControl.position.setValueAtTime(0, [cx, cy, -500]);
        camControl.shy = true;

        var cam = comp.layers.addCamera("Main_Camera", [cx, cy]);
        cam.threeDLayer = true;
        cam.parent = camControl;
        cam.shy = true;

        try {
            cam.property("ADBE Camera Settings-0001").setValue(50);
            try { cam.property("ADBE Camera Options Group").property(1).setValue(1); } catch(e) {}
            try { cam.property("ADBE Camera Options Group").property(5).setValue(400); } catch(e) {}
            try { cam.property("ADBE Camera Options Group").property(6).setValue(4.0); } catch(e) {}
            try { cam.property("ADBE Camera Options Group").property(9).setValue(100); } catch(e) {}
        } catch(e) {}

        var beatKfCount = 0;
        try {
            var camPos = camControl.property("ADBE Transform Group").property("ADBE Position");
            camPos.setValueAtTime(0, [cx, cy, -800]);
            camPos.setValueAtTime(1, [cx, cy, -600]);
            camPos.setValueAtTime(2.5, [cx + 40, cy - 30, -450]);
            camPos.setValueAtTime(4, [cx + 20, cy + 10, -380]);
            camPos.setValueAtTime(5.5, [cx - 30, cy + 20, -420]);
            camPos.setValueAtTime(7, [cx - 10, cy - 15, -350]);
            camPos.setValueAtTime(8.5, [cx + 25, cy - 20, -400]);
            camPos.setValueAtTime(10, [cx + 5, cy + 5, -450]);
            camPos.setValueAtTime(compDuration, [cx, cy, -550]);
            setEase(camPos, 40);

            var camRot = camControl.property("ADBE Transform Group").property("ADBE Rotation");
            camRot.setValueAtTime(0, [0, 0, 0]);
            camRot.setValueAtTime(2, [0, 0, 4]);
            camRot.setValueAtTime(4, [0, 0, -2]);
            camRot.setValueAtTime(6, [0, 0, -4]);
            camRot.setValueAtTime(8, [0, 0, 2]);
            camRot.setValueAtTime(10, [0, 0, 3]);
            camRot.setValueAtTime(compDuration, [0, 0, 0]);
            setEase(camRot, 50);

            beatKfCount = camPos.numKeys + camRot.numKeys;
        } catch(e) {}

        try {
            var zoomProp = cam.property("ADBE Camera Options Group").property(5);
            zoomProp.setValueAtTime(0, 500);
            zoomProp.setValueAtTime(2, 400);
            zoomProp.setValueAtTime(4, 450);
            zoomProp.setValueAtTime(6, 350);
            zoomProp.setValueAtTime(8, 420);
            zoomProp.setValueAtTime(10, 380);
            zoomProp.setValueAtTime(compDuration, 450);
            setEase(zoomProp, 45);
        } catch(e) {}

        results.push({ phase: "Phase7", status: "success", message: "摄像机和控制器创建完成" });

        var layerOrderBottomToTop = [
            "Sky_BG",
            "P_BG",
            "P_MID",
            "Saitama_Main",
            "Cape_Layer",
            "Silhouette_Matte_Cape",
            "Silhouette_Matte",
            "P_FG",
            "Fog_Overlay",
            "Vignette",
            "Color_Adjust",
            "Main_Camera",
            "Character_Control",
            "Camera_Control",
            "Global_Controller"
        ];
        for (var lo = 0; lo < layerOrderBottomToTop.length; lo++) {
            for (var lj = 1; lj <= comp.numLayers; lj++) {
                if (comp.layer(lj).name == layerOrderBottomToTop[lo]) {
                    comp.layer(lj).moveToBeginning();
                    break;
                }
            }
        }

        try { cam.active = true; } catch(e) {}

        results.push({ phase: "Phase8", status: "success", message: "层顺序整理完成，总图层数: " + comp.numLayers });

        if (bgmPath) {
            var bgmFile = new File(bgmPath);
            if (bgmFile.exists) {
                var bgmImport = app.project.importFile(new ImportOptions(bgmFile));
                var bgmLayer = comp.layers.add(bgmImport);
                bgmLayer.name = "BGM_Track";
                bgmLayer.moveToEnd();
            }
        }

        app.endUndoGroup();

        return JSON.stringify({
            success: true,
            status: "success",
            message: "E2E音乐视频合成创建成功",
            compName: compName,
            totalLayers: comp.numLayers,
            bpm: bpm,
            beatKeyframes: beatKfCount,
            energyPeaks: energyPeaks.length,
            frameCount: frameFiles.length,
            phases: results,
            timestamp: new Date().toISOString()
        }, null, 2);
    } catch(e) {
        try { app.endUndoGroup(); } catch(ee) {}
        return JSON.stringify({
            success: false,
            status: "error",
            message: e.toString(),
            line: e.line,
            timestamp: new Date().toISOString()
        }, null, 2);
    }
}

// --- autoCreateProject: Create project from files (end-to-end) ---
function autoCreateProject(args) {
    try {
        var compName = args.compName || "AI Generated Comp";
        var width = parseInt(args.width) || 1920;
        var height = parseInt(args.height) || 1080;
        var duration = parseFloat(args.duration) || 10.0;
        var frameRate = parseFloat(args.frameRate) || 30.0;
        var files = args.files || [];

        var results = {
            composition: null,
            importedFiles: [],
            placedLayers: [],
            errors: []
        };

        var newComp = app.project.items.addComp(compName, width, height, 1.0, duration, frameRate);
        results.composition = {
            name: newComp.name,
            id: newComp.id,
            width: newComp.width,
            height: newComp.height,
            duration: newComp.duration,
            frameRate: newComp.frameRate
        };

        var currentTime = 0;
        for (var i = 0; i < files.length; i++) {
            var filePath = files[i];
            try {
                var file = new File(filePath);
                if (!file.exists) {
                    results.errors.push("File not found: " + filePath);
                    continue;
                }

                var imported = app.project.importFile(file);
                var itemName = imported.name;
                results.importedFiles.push(itemName);

                if (imported instanceof FootageItem) {
                    var layer = newComp.layers.add(imported);
                    layer.startTime = currentTime;
                    layer.name = itemName;
                    
                    results.placedLayers.push({
                        name: itemName,
                        startTime: currentTime,
                        duration: imported.duration
                    });

                    currentTime += imported.duration;
                }
            } catch (e) {
                results.errors.push("Failed to import " + filePath + ": " + e.toString());
            }
        }

        return JSON.stringify({
            status: results.errors.length > 0 ? "partial" : "success",
            message: "Project creation completed",
            results: results
        }, null, 2);

    } catch (error) {
        return JSON.stringify({
            status: "error",
            message: error.toString()
        }, null, 2);
    }
}

// Detect AE version (AE 2025 = version 25.x, AE 2026 = version 26.x)
var aeVersion = parseFloat(app.version);
var isAE2025OrLater = aeVersion >= 25.0;

// Always create a floating palette window for AE 2025+
var panel = new Window("palette", "MCP Bridge Auto", undefined);
panel.orientation = "column";
panel.alignChildren = ["fill", "top"];
panel.spacing = 10;
panel.margins = 16;

// Status display
var statusText = panel.add("statictext", undefined, "Waiting for commands...");
statusText.alignment = ["fill", "top"];

// Add log area
var logPanel = panel.add("panel", undefined, "Command Log");
logPanel.orientation = "column";
logPanel.alignChildren = ["fill", "fill"];
var logText = logPanel.add("edittext", undefined, "", {multiline: true, readonly: true});
logText.preferredSize.height = 200;

// AE 2025 warning
if (isAE2025OrLater) {
    var warning = panel.add("statictext", undefined, "AE 2025+: Dockable panels are not supported. Floating window only.");
    warning.graphics.foregroundColor = warning.graphics.newPen(warning.graphics.PenType.SOLID_COLOR, [1,0.3,0,1], 1);
}

// Auto-run checkbox
var autoRunCheckbox = panel.add("checkbox", undefined, "Auto-run commands");
autoRunCheckbox.value = true;
autoRunCheckbox.onClick = function() {
    statusText.text = "Ready - Auto-run is " + (this.value ? "ON" : "OFF");
    if (this.value) {
        logToPanel("Auto-run enabled, checking every " + checkInterval + "ms");
    } else {
        logToPanel("Auto-run disabled");
    }
};

var inputPanel = panel.add("panel", undefined, "E2E Music Video Settings");
inputPanel.orientation = "column";
inputPanel.alignChildren = ["fill", "top"];
inputPanel.spacing = 4;

var row1 = inputPanel.add("group");
row1.orientation = "row";
row1.alignChildren = ["left", "center"];
row1.spacing = 6;
row1.add("statictext", undefined, "合成名称:");
var compNameInput = row1.add("edittext", undefined, "一拳超人_E2E测试");
compNameInput.preferredSize.width = 150;

var row2 = inputPanel.add("group");
row2.orientation = "row";
row2.alignChildren = ["left", "center"];
row2.spacing = 6;
row2.add("statictext", undefined, "帧目录:");
// TODO: 参数化 - 以下 UI 默认值为示例路径，建议从配置文件读取
var frameDirInput = row2.add("edittext", undefined, "D:/AE-Work/视频素材库/frames");
frameDirInput.preferredSize.width = 200;

var row3 = inputPanel.add("group");
row3.orientation = "row";
row3.alignChildren = ["left", "center"];
row3.spacing = 6;
row3.add("statictext", undefined, "BPM:");
var bpmInput = row3.add("edittext", undefined, "120");
bpmInput.preferredSize.width = 50;
row3.add("statictext", undefined, "时长:");
var durationInput = row3.add("edittext", undefined, "12");
durationInput.preferredSize.width = 50;
row3.add("statictext", undefined, "秒");

var row4 = inputPanel.add("group");
row4.orientation = "row";
row4.alignChildren = ["left", "center"];
row4.spacing = 6;
row4.add("statictext", undefined, "尺寸:");
var widthInput = row4.add("edittext", undefined, "576");
widthInput.preferredSize.width = 50;
row4.add("statictext", undefined, "x");
var heightInput = row4.add("edittext", undefined, "768");
heightInput.preferredSize.width = 50;

// Test button for e2eMusicVideo
var e2eButton = panel.add("button", undefined, "Create E2E Music Video");
e2eButton.onClick = function() {
    logToPanel("Manual trigger: e2eMusicVideo");
    statusText.text = "Creating E2E Music Video...";
    panel.update();

    var args = {
        compName: compNameInput.text || "一拳超人_E2E测试",
        // 参数化：移除硬编码 fallback，空值由 createE2EMusicVideo 内部统一报错
        frameDir: frameDirInput.text,
        bgmPath: "",
        beatTimes: [0, 2, 4, 6, 8, 10, 12],
        energyPeaks: [1.5, 3.5, 5.5, 7.5, 9.5],
        peakValues: [0.8, 0.9, 0.7, 0.95, 0.85],
        bpm: parseFloat(bpmInput.text) || 120,
        width: parseInt(widthInput.text) || 576,
        height: parseInt(heightInput.text) || 768,
        duration: parseFloat(durationInput.text) || 12,
        fps: 30
    };
    
    try {
        var result = createE2EMusicVideo(args);
        var resultObj = JSON.parse(result);
        if (resultObj.success) {
            statusText.text = "Success! Created " + resultObj.compName;
            logToPanel("Success: " + resultObj.message);
            logToPanel("Layers: " + resultObj.totalLayers + ", Keyframes: " + resultObj.beatKeyframes);
        } else {
            statusText.text = "Error: " + resultObj.message;
            logToPanel("Error: " + resultObj.message);
        }
    } catch(e) {
        statusText.text = "Exception: " + e.toString();
        logToPanel("Exception: " + e.toString() + " (line: " + (e.line || "unknown") + ")");
    }
    panel.update();
};

var e2eSilhouetteButton = panel.add("button", undefined, "Create E2E Music Video (Silhouette)");
e2eSilhouetteButton.onClick = function() {
    logToPanel("Manual trigger: e2eMusicVideo with Silhouette");
    statusText.text = "Creating E2E Music Video with Silhouette...";
    panel.update();

    var args = {
        compName: compNameInput.text || "一拳超人_E2E测试",
        // 参数化：移除硬编码 fallback，空值由 createE2EMusicVideo 内部统一报错
        frameDir: frameDirInput.text,
        bgmPath: "",
        beatTimes: [0, 2, 4, 6, 8, 10, 12],
        energyPeaks: [1.5, 3.5, 5.5, 7.5, 9.5],
        peakValues: [0.8, 0.9, 0.7, 0.95, 0.85],
        bpm: parseFloat(bpmInput.text) || 120,
        width: parseInt(widthInput.text) || 576,
        height: parseInt(heightInput.text) || 768,
        duration: parseFloat(durationInput.text) || 12,
        fps: 30,
        // TODO: 参数化 - mattePath 硬编码示例路径，建议从配置或 UI 输入读取
        mattePath: "D:/AE-Work/silhouette_output/matte_[####].exr"
    };
    
    try {
        var result = createE2EMusicVideo(args);
        var resultObj = JSON.parse(result);
        if (resultObj.success) {
            statusText.text = "Success! Created " + resultObj.compName;
            logToPanel("Success: " + resultObj.message);
            logToPanel("Layers: " + resultObj.totalLayers);
        } else {
            statusText.text = "Error: " + resultObj.message;
            logToPanel("Error: " + resultObj.message);
        }
    } catch(e) {
        statusText.text = "Exception: " + e.toString();
        logToPanel("Exception: " + e.toString() + " (line: " + (e.line || "unknown") + ")");
    }
    panel.update();
};

// Check interval (ms) - reduce to 1000ms for faster response
var checkInterval = 1000;
var isChecking = false;
var lastCommandTime = 0;

// ========== 签名验证配置 ==========
var SECRET_FILE = Folder.myDocuments.fsName + "/ae-mcp-bridge/.mcp_secret";
var MCP_SECRET = "";
var SIGNATURE_ENABLED = false;

function _loadSecret() {
    var f = new File(SECRET_FILE);
    if (f.exists) {
        f.encoding = "UTF-8";
        f.open("r");
        var content = f.read();
        f.close();
        if (content) {
            MCP_SECRET = content.replace(/\s+$/, "");
        }
    }
}
_loadSecret();

function _sha256(message) { return "dummy"; }
function _hmacSha256(key, message) { return "dummy"; }
function _canonicalize(obj){if(obj===null||obj===undefined)return"null";var t=typeof obj;if(t==="number"||t==="boolean")return String(obj);if(t==="string"){function esc(s){return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t")}return'"'+esc(obj)+'"'}if(obj instanceof Array){var a=[];for(var i=0;i<obj.length;i++)a.push(_canonicalize(obj[i]));return"["+a.join(",")+"]"}if(t==="object"){var keys=[];for(var k in obj)if(obj.hasOwnProperty(k)&&typeof obj[k]!=="function"&&typeof obj[k]!=="undefined")keys.push(k);keys.sort();var pairs=[];function esk(s){return s.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"\\r").replace(/\t/g,"\\t")}for(var i=0;i<keys.length;i++)pairs.push('"'+esk(keys[i])+'":'+_canonicalize(obj[keys[i]]));return"{"+pairs.join(",")+"}"}return"null"}
function verifySignature(data){if(!SIGNATURE_ENABLED)return true;if(!MCP_SECRET||MCP_SECRET.length===0)return true;if(!data||!data.signature||!data.timestamp)return false;var ts=parseInt(data.timestamp);if(isNaN(ts)){var dts=new Date(data.timestamp).getTime();if(isNaN(dts))return false;ts=Math.floor(dts/1000)}var now=Math.floor(new Date().getTime()/1000);if(Math.abs(now-ts)>300)return false;var vd={};for(var k in data)if(data.hasOwnProperty(k)&&k!=="signature"&&k!=="signature_alg")vd[k]=data[k];var canon=_canonicalize(vd);var expected=_hmacSha256(MCP_SECRET,canon);if(expected.length!==data.signature.length)return false;var diff=0;for(var i=0;i<expected.length;i++)diff|=(expected.charCodeAt(i)^data.signature.charCodeAt(i));return diff===0}

// Command file path - use Documents folder for reliable access
function getCommandFilePath() {
    var userFolder = Folder.myDocuments;
    var bridgeFolder = new Folder(userFolder.fsName + "/ae-mcp-bridge");
    if (!bridgeFolder.exists) {
        bridgeFolder.create();
    }
    return bridgeFolder.fsName + "/ae_command.json";
}

// Result file path - use Documents folder for reliable access
function getResultFilePath() {
    var userFolder = Folder.myDocuments;
    var bridgeFolder = new Folder(userFolder.fsName + "/ae-mcp-bridge");
    if (!bridgeFolder.exists) {
        bridgeFolder.create();
    }
    return bridgeFolder.fsName + "/ae_mcp_result.json";
}

// --- setCompositionProperties: set duration, frameRate, etc. on active or named comp ---
function setCompositionProperties(args) {
    try {
        var compName = args.compName || "";
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === compName) { comp = item; break; }
        }
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) { comp = app.project.activeItem; }
            else { throw new Error("No composition found with name '" + compName + "' and no active composition"); }
        }
        var changed = [];
        if (args.duration !== undefined && args.duration !== null) { comp.duration = args.duration; changed.push("duration"); }
        if (args.frameRate !== undefined && args.frameRate !== null) { comp.frameRate = args.frameRate; changed.push("frameRate"); }
        if (args.width !== undefined && args.width !== null && args.height !== undefined && args.height !== null) {
            comp.width = args.width; comp.height = args.height; changed.push("dimensions");
        }
        return JSON.stringify({
            status: "success",
            composition: { name: comp.name, duration: comp.duration, frameRate: comp.frameRate, width: comp.width, height: comp.height },
            changedProperties: changed
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// Functions for each script type
function getProjectInfo() {
    var project = app.project;
    var result = {
        projectName: project.file ? project.file.name : "Untitled Project",
        path: project.file ? project.file.fsName : "",
        numItems: project.numItems,
        bitsPerChannel: project.bitsPerChannel,
        timeMode: project.timeDisplayType === TimeDisplayType.FRAMES ? "Frames" : "Timecode",
        items: []
    };

    // Count item types
    var countByType = {
        compositions: 0,
        footage: 0,
        folders: 0,
        solids: 0
    };

    // Get item information (limited for performance)
    for (var i = 1; i <= Math.min(project.numItems, 50); i++) {
        var item = project.item(i);
        var itemType = "";
        
        if (item instanceof CompItem) {
            itemType = "Composition";
            countByType.compositions++;
        } else if (item instanceof FolderItem) {
            itemType = "Folder";
            countByType.folders++;
        } else if (item instanceof FootageItem) {
            if (item.mainSource instanceof SolidSource) {
                itemType = "Solid";
                countByType.solids++;
            } else {
                itemType = "Footage";
                countByType.footage++;
            }
        }
        
        result.items.push({
            id: item.id,
            name: item.name,
            type: itemType
        });
    }
    
    result.itemCounts = countByType;

    // Include active composition metadata if available
    if (app.project.activeItem instanceof CompItem) {
        var ac = app.project.activeItem;
        result.activeComp = {
            id: ac.id,
            name: ac.name,
            width: ac.width,
            height: ac.height,
            duration: ac.duration,
            frameRate: ac.frameRate,
            numLayers: ac.numLayers
        };
    }

    return JSON.stringify(result, null, 2);
}

function listCompositions() {
    var project = app.project;
    var result = {
        compositions: []
    };
    
    // Loop through items in the project
    for (var i = 1; i <= project.numItems; i++) {
        var item = project.item(i);
        
        // Check if the item is a composition
        if (item instanceof CompItem) {
            result.compositions.push({
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
    
    return JSON.stringify(result, null, 2);
}

function getLayerInfo(args) {
    var project = app.project;
    var result = { layers: [] };

    // Support compIndex or compName from args
    var compIndex = parseInt(args && args.compIndex) || 0;

    // Get composition
    var comp = null;
    if (compIndex > 0 && compIndex <= project.numItems) {
        var item = project.item(compIndex);
        if (item instanceof CompItem) comp = item;
    }
    if (!comp && app.project.activeItem instanceof CompItem) {
        comp = app.project.activeItem;
    }
    if (!comp) {
        return JSON.stringify({ error: "No composition found" }, null, 2);
    }
    result.compName = comp.name;
    result.compId = comp.id;

    // Loop through layers in the composition
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var layerInfo = {
            index: layer.index,
            name: layer.name,
            enabled: layer.enabled,
            locked: layer.locked,
            threeDLayer: layer.threeDLayer,
            position: layer.property("Position").value,
            inPoint: layer.inPoint,
            outPoint: layer.outPoint,
            effects: []
        };

        // List effects on this layer
        try {
            for (var e = 1; e <= layer.Effects.numProperties; e++) {
                var fx = layer.Effects.property(e);
                layerInfo.effects.push({
                    name: fx.name,
                    matchName: fx.matchName,
                    index: fx.propertyIndex
                });
            }
        } catch(e) {}

        result.layers.push(layerInfo);
    }

    return JSON.stringify(result, null, 2);
}

// --- listEffects: return all installed effects with match names ---
function listEffects(args) {
    try {
        var result = { status: "success", effects: [], totalCount: 0 };
        var filterCategory = args.category || "";
        var searchTerm = args.searchTerm || "";
        var allEffects = app.effects;
        for (var i = 1; i <= allEffects.length; i++) {
            try {
                var fx = allEffects[i];
                var dispName = fx.displayName;
                var cat = fx.category;
                if (filterCategory && cat.toLowerCase().indexOf(filterCategory.toLowerCase()) < 0) continue;
                if (searchTerm && dispName.toLowerCase().indexOf(searchTerm.toLowerCase()) < 0) continue;
                result.effects.push({ displayName: dispName, matchName: fx.matchName, category: cat });
            } catch (e) {}
        }
        result.totalCount = result.effects.length;
        return JSON.stringify(result, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- applyPreset: apply .ffx animation/effect preset to a layer ---
function applyPreset(args) {
    try {
        var comp = app.project.item(parseInt(args.compIndex) || 1);
        if (!(comp instanceof CompItem) && app.project.activeItem instanceof CompItem) comp = app.project.activeItem;
        if (!comp) throw new Error("No composition found");
        var layer = comp.layer(parseInt(args.layerIndex) || 1);
        if (!layer) throw new Error("Layer not found");
        var presetPath = args.presetPath || "";
        var presetName = args.presetName || "";
        var fullPath = "";
        if (presetPath) {
            fullPath = presetPath;
        } else if (presetName) {
            var searchPaths = [Folder.appPackage.fsName + "/Presets/", Folder.myDocuments.fsName + "/Adobe/After Effects/User Presets/"];
            var mainPresets = new Folder(Folder.appPackage.fsName + "/Presets/");
            if (mainPresets.exists) {
                var subFolders = mainPresets.getFiles();
                for (var s = 0; s < subFolders.length; s++) {
                    if (subFolders[s] instanceof Folder) searchPaths.push(subFolders[s].fsName + "/");
                }
            }
            for (var p = 0; p < searchPaths.length; p++) {
                var testFile = new File(searchPaths[p] + presetName);
                if (testFile.exists) { fullPath = testFile.fsName; break; }
                var testFileFfx = new File(searchPaths[p] + presetName + ".ffx");
                if (testFileFfx.exists) { fullPath = testFileFfx.fsName; break; }
            }
        }
        if (!fullPath) throw new Error("Preset not found: " + (presetName || presetPath));
        var presetFile = new File(fullPath);
        if (!presetFile.exists) throw new Error("Preset file does not exist: " + fullPath);
        layer.applyPreset(presetFile);
        return JSON.stringify({ status: "success", message: "Preset applied", preset: fullPath, layer: { name: layer.name, index: layer.index } }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- e3dLoadModel: configure Element 3D on a layer ---
function e3dLoadModel(args) {
    try {
        var comp = app.project.item(parseInt(args.compIndex) || 1);
        if (!(comp instanceof CompItem) && app.project.activeItem instanceof CompItem) comp = app.project.activeItem;
        if (!comp) throw new Error("No composition found");
        var layer;
        if (args.layerIndex) {
            layer = comp.layer(parseInt(args.layerIndex));
        } else {
            var solid = comp.layers.addSolid([0, 0, 0], "E3D Layer", comp.width, comp.height, comp.pixelAspect);
            layer = solid;
        }
        if (!layer) throw new Error("Layer not found");
        var e3dEffect = null;
        for (var i = 1; i <= layer.Effects.numProperties; i++) {
            if (layer.Effects.property(i).matchName === "Element") { e3dEffect = layer.Effects.property(i); break; }
        }
        if (!e3dEffect) {
            try { e3dEffect = layer.Effects.addProperty("Element"); } catch (e) { throw new Error("Element 3D plugin not found"); }
        }
        return JSON.stringify({ status: "success", message: "Element 3D applied to layer", layer: { name: layer.name, index: layer.index }, composition: { name: comp.name }, element3d: { effectName: e3dEffect.name, matchName: e3dEffect.matchName }, note: "Use AE UI to load models, set materials, and configure groups. Scripting API access is limited." }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- particularEmitter: configure Trapcode Particular emitter (v2 — advanced) ---
function particularEmitter(args) {
    try {
        var compIndex = parseInt(args.compIndex) || 1;
        var comp = app.project.item(compIndex);
        if (!(comp instanceof CompItem) && app.project.activeItem instanceof CompItem) comp = app.project.activeItem;
        if (!comp) throw new Error("No composition found");
        var layer;
        if (args.layerIndex && parseInt(args.layerIndex) >= 1 && parseInt(args.layerIndex) <= comp.numLayers) {
            layer = comp.layer(parseInt(args.layerIndex));
        } else {
            var solid = comp.layers.addSolid([0, 0, 0], "Particular Layer", comp.width, comp.height, comp.pixelAspect);
            layer = solid;
        }
        if (!layer) throw new Error("Layer not found");

        // Motion Blur
        if (args.motionBlur !== "false" && args.motionBlur !== false) {
            try { comp.motionBlur = true; } catch(e) {}
            try { layer.motionBlur = true; } catch(e) {}
            try { layer.shutterAngle = 360; } catch(e) {}
        }

        var partFx = null;
        var matchNames = ["Particular", "Trapcode Particular", "RG Particular", "Red Giant Particular"];
        for (var m = 0; m < matchNames.length; m++) {
            try { partFx = layer.Effects.addProperty(matchNames[m]); if (partFx) break; } catch (e) {}
        }
        if (!partFx) throw new Error("Trapcode Particular not found");
        var configured = [];

        function sp(effect, propName, value) {
            try { var p = effect.property(propName); if (p) { p.setValue(value); configured.push(propName + ": " + value); } } catch(e) {}
        }

        // === Emitter Group ===
        var emitterGroup = partFx.property("Emitter");
        if (emitterGroup) {
            try {
                var eType = emitterGroup.property("Emitter Type");
                if (eType && args.emitterType) {
                    var ets = {point:1, box:2, sphere:3, grid:4, light:5, layer:6};
                    eType.setValue(ets[String(args.emitterType).toLowerCase()] || 1);
                    configured.push("Emitter Type: " + args.emitterType);
                }
            } catch(e) {}
            sp(emitterGroup, "Particles/sec", parseInt(args.particlesPerSec) || 100);
            sp(emitterGroup, "Velocity", parseFloat(args.velocity) || 100);
            sp(emitterGroup, "Velocity Random [%]", parseFloat(args.velocityRandom) || 20);
            sp(emitterGroup, "Velocity from Motion [%]", parseFloat(args.velocityFromMotion) || 10);
            sp(emitterGroup, "Direction Random [%]", parseFloat(args.directionRandom) || 20);
            if (args.positionXY) sp(emitterGroup, "Position XY", args.positionXY);
            if (args.positionZ !== undefined) sp(emitterGroup, "Position Z", parseFloat(args.positionZ));
        }

        // === Particle Group ===
        var particleGroup = partFx.property("Particle");
        if (particleGroup) {
            sp(particleGroup, "Life [sec]", parseFloat(args.lifeSec) || 3);
            sp(particleGroup, "Life Random [%]", parseFloat(args.lifeRandom) || 30);
            sp(particleGroup, "Size", parseFloat(args.size) || 5);
            sp(particleGroup, "Size Random [%]", parseFloat(args.sizeRandom) || 30);
            sp(particleGroup, "Opacity", parseFloat(args.opacity) || 100);
            sp(particleGroup, "Opacity Random [%]", parseFloat(args.opacityRandom) || 20);
            sp(particleGroup, "Color Random [%]", parseFloat(args.colorRandom) || 5);
            if (args.color) {
                try { var cp = particleGroup.property("Color"); if (cp) { cp.setValue(args.color); configured.push("Color set"); } } catch(e) {}
            }
            // Size over Life curve
            var solPreset = args.sizeOverLife || "";
            if (solPreset && solPreset !== "none") {
                try {
                    var sol = particleGroup.property("Size over Life");
                    var ls = parseFloat(args.lifeSec) || 3;
                    var sz = parseFloat(args.size) || 5;
                    if (sol && sol.canSetExpression) {
                        if (solPreset === "bell") {
                            sol.setValueAtTime(0, 0);
                            sol.setValueAtTime(ls * 0.15, sz);
                            sol.setValueAtTime(ls * 0.7, sz * 0.8);
                            sol.setValueAtTime(ls, 0);
                            configured.push("Size over Life: bell curve");
                        } else if (solPreset === "decay") {
                            sol.setValueAtTime(0, sz);
                            sol.setValueAtTime(ls * 0.4, sz * 0.6);
                            sol.setValueAtTime(ls, 0);
                            configured.push("Size over Life: decay");
                        } else if (solPreset === "flatFade") {
                            sol.setValueAtTime(0, sz);
                            sol.setValueAtTime(ls * 0.8, sz);
                            sol.setValueAtTime(ls, 0);
                            configured.push("Size over Life: flat+fade");
                        }
                    }
                } catch(e) {}
            }
            // Opacity over Life curve
            var oolPreset = args.opacityOverLife || "";
            if (oolPreset && oolPreset !== "none") {
                try {
                    var ool = particleGroup.property("Opacity over Life");
                    var ls = parseFloat(args.lifeSec) || 3;
                    var op = parseFloat(args.opacity) || 100;
                    if (ool && ool.canSetExpression) {
                        if (oolPreset === "fadeInOut") {
                            ool.setValueAtTime(0, 0);
                            ool.setValueAtTime(ls * 0.1, op);
                            ool.setValueAtTime(ls * 0.8, op);
                            ool.setValueAtTime(ls, 0);
                            configured.push("Opacity over Life: fadeInOut");
                        } else if (oolPreset === "linearOut") {
                            ool.setValueAtTime(0, op);
                            ool.setValueAtTime(ls, 0);
                            configured.push("Opacity over Life: linearOut");
                        }
                    }
                } catch(e) {}
            }
        }

        // === Physics Group ===
        var physGroup = partFx.property("Physics");
        if (physGroup) {
            sp(physGroup, "Gravity", parseFloat(args.gravity) || 100);
            try {
                var airGroup = physGroup.property("Air");
                if (airGroup) {
                    sp(airGroup, "Air Resistance", parseFloat(args.airResistance) || 1.0);
                    sp(airGroup, "Wind X", parseFloat(args.windX) || 0);
                    sp(airGroup, "Wind Y", parseFloat(args.windY) || 0);
                    sp(airGroup, "Wind Z", parseFloat(args.windZ) || 0);
                    sp(airGroup, "Spin Amplitude", parseFloat(args.spinAmplitude) || 0);
                    // Turbulence Field
                    var turbAmt = parseFloat(args.turbulenceAmount) || 0;
                    if (turbAmt > 0) {
                        try {
                            var turbField = airGroup.property("Turbulence Field");
                            if (turbField) {
                                sp(turbField, "Affect Position", turbAmt);
                                sp(turbField, "Scale", parseFloat(args.turbulenceScale) || 50);
                                sp(turbField, "Octave Scale", parseFloat(args.turbulenceOctaveScale) || 1.5);
                                sp(turbField, "Fade-in Time [sec]", parseFloat(args.turbulenceFadeIn) || 0.5);
                                configured.push("Turbulence: amt=" + turbAmt + " scale=" + (parseFloat(args.turbulenceScale) || 50));
                            }
                        } catch(e) {}
                    }
                }
            } catch(e) {}
        }

        // Preset search
        if (args.presetName) {
            try {
                var searchFolder = new Folder(Folder.appPackage.fsName + "/Presets/");
                var found = false;
                function searchRec(folder, depth) {
                    if (depth > 5 || found) return;
                    var files = folder.getFiles();
                    for (var f = 0; f < files.length && !found; f++) {
                        var file = files[f];
                        if (file instanceof Folder) { searchRec(file, depth + 1); }
                        else if (file instanceof File && file.name.toLowerCase().indexOf(String(args.presetName).toLowerCase()) !== -1 && file.name.indexOf(".ffx") !== -1) {
                            try { partFx.applyPreset(file); found = true; configured.push("Preset: " + file.name); } catch(e) {}
                        }
                    }
                }
                searchRec(searchFolder, 0);
            } catch(e) {}
        }

        return JSON.stringify({
            status: "success",
            message: "Particular configured (v2 advanced)",
            configured: configured,
            layer: { name: layer.name, index: layer.index },
            composition: { name: comp.name }
        }, null, 2);
    } catch (error) {
        return JSON.stringify({ status: "error", message: error.toString() }, null, 2);
    }
}

// --- diagParticular: diagnose Particular effect property structure ---
function diagParticular() {
    try {
        var project = app.project;
        var res = { steps: [] };
        var comp = null;
        for (var i = 1; i <= project.numItems; i++) {
            var item = project.item(i);
            if (item instanceof CompItem && item.name === "艺术降临") { comp = item; break; }
        }
        if (!comp) throw new Error("艺术降临 comp not found");
        res.comp = { name: comp.name, numLayers: comp.numLayers, id: comp.id };
        var solid = comp.layers.addSolid([0,0,0], "Particular Diag", comp.width, comp.height, comp.pixelAspect);
        res.solid = { name: solid.name, index: solid.index };
        var names = ["Particular", "Trapcode Particular", "RG Particular", "Red Giant Particular", "Trapcode"];
        var partFx = null;
        for (var m = 0; m < names.length; m++) {
            try { partFx = solid.Effects.addProperty(names[m]); if (partFx) { res.matchedName = names[m]; res.fxName = partFx.name; res.fxMatchName = partFx.matchName; break; } } catch(e) { res["err_"+names[m]] = e.toString(); }
        }
        if (!partFx) { res.error = "Particular not found"; return JSON.stringify(res); }
        res.topGroups = [];
        for (var g = 1; g <= partFx.numProperties; g++) {
            var prop = partFx.property(g);
            res.topGroups.push({ n: prop.name, mn: prop.matchName, cnt: prop.numProperties });
        }
        var grps = ["Emitter", "Particle", "Physics", "Rendering", "Aux System"];
        for (var t = 0; t < grps.length; t++) {
            var grp = partFx.property(grps[t]);
            if (grp) {
                var entry = { found: true, name: grp.name, cnt: grp.numProperties, firstFew: [] };
                for (var s = 1; s <= Math.min(grp.numProperties, 8); s++) {
                    try { var sub = grp.property(s); entry.firstFew.push(sub.name + " (" + sub.matchName + ")"); } catch(e) {}
                }
                res["G_" + grps[t]] = entry;
            } else { res["G_" + grps[t]] = { found: false }; }
        }
        res.status = "success";
        return JSON.stringify(res, null, 2);
    } catch(e) { return JSON.stringify({ status: "error", message: e.toString() }); }
}

function executeCommand(command, args) {
    var result = "";

    logToPanel("Executing command: " + command);
    statusText.text = "Running: " + command;
    panel.update();

    try {
        logToPanel("Attempting to execute: " + command); // Log before switch
        // Use a switch statement for clarity
        switch (command) {
            case "getProjectInfo":
                result = getProjectInfo();
                break;
            case "listCompositions":
                result = listCompositions();
                break;
            case "getLayerInfo":
                result = getLayerInfo(args);
                break;
            case "createComposition":
                logToPanel("Calling createComposition function...");
                result = createComposition(args);
                logToPanel("Returned from createComposition.");
                break;
            case "createTextLayer":
                logToPanel("Calling createTextLayer function...");
                result = createTextLayer(args);
                logToPanel("Returned from createTextLayer.");
                break;
            case "createShapeLayer":
                logToPanel("Calling createShapeLayer function...");
                result = createShapeLayer(args);
                logToPanel("Returned from createShapeLayer. Result type: " + typeof result);
                break;
            case "createSolidLayer":
                logToPanel("Calling createSolidLayer function...");
                result = createSolidLayer(args);
                logToPanel("Returned from createSolidLayer.");
                break;
            case "setLayerProperties":
                logToPanel("Calling setLayerProperties function...");
                result = setLayerProperties(args);
                logToPanel("Returned from setLayerProperties.");
                break;
            case "setLayerKeyframe":
                logToPanel("Calling setLayerKeyframe function...");
                result = setLayerKeyframe(args.compIndex, args.layerIndex, args.propertyName, args.timeInSeconds, args.value);
                logToPanel("Returned from setLayerKeyframe.");
                break;
            case "setLayerExpression":
                logToPanel("Calling setLayerExpression function...");
                result = setLayerExpression(args.compIndex, args.layerIndex, args.propertyName, args.expressionString);
                logToPanel("Returned from setLayerExpression.");
                break;
            case "applyEffect":
                logToPanel("Calling applyEffect function...");
                result = applyEffect(args);
                logToPanel("Returned from applyEffect.");
                break;
            case "applyEffectTemplate":
                logToPanel("Calling applyEffectTemplate function...");
                result = applyEffectTemplate(args);
                logToPanel("Returned from applyEffectTemplate.");
                break;
            case "bridgeTestEffects":
                logToPanel("Calling bridgeTestEffects function...");
                result = bridgeTestEffects(args);
                logToPanel("Returned from bridgeTestEffects.");
                break;
            case "createCamera":
                logToPanel("Calling createCamera function...");
                result = createCamera(args);
                logToPanel("Returned from createCamera.");
                break;
            case "batchSetLayerProperties":
                logToPanel("Calling batchSetLayerProperties function...");
                result = batchSetLayerProperties(args);
                logToPanel("Returned from batchSetLayerProperties.");
                break;
            case "setCompositionProperties":
                logToPanel("Calling setCompositionProperties function...");
                result = setCompositionProperties(args);
                logToPanel("Returned from setCompositionProperties.");
                break;
            case "duplicateLayer":
                logToPanel("Calling duplicateLayer function...");
                result = duplicateLayer(args);
                logToPanel("Returned from duplicateLayer.");
                break;
            case "deleteLayer":
                logToPanel("Calling deleteLayer function...");
                result = deleteLayer(args);
                logToPanel("Returned from deleteLayer.");
                break;
            case "setLayerMask":
                logToPanel("Calling setLayerMask function...");
                result = setLayerMask(args);
                logToPanel("Returned from setLayerMask.");
                break;
            case "listEffects":
                logToPanel("Calling listEffects function...");
                result = listEffects(args);
                logToPanel("Returned from listEffects. Found " + (JSON.parse(result).totalCount || 0) + " effects.");
                break;
            case "applyPreset":
                logToPanel("Calling applyPreset function...");
                result = applyPreset(args);
                logToPanel("Returned from applyPreset.");
                break;
            case "e3dLoadModel":
                logToPanel("Calling e3dLoadModel function...");
                result = e3dLoadModel(args);
                logToPanel("Returned from e3dLoadModel.");
                break;
            case "particularEmitter":
                logToPanel("Calling particularEmitter function...");
                result = particularEmitter(args);
                logToPanel("Returned from particularEmitter.");
                break;
            case "fixParticular":
                logToPanel("Calling fixParticular script...");
                $.global.fixParticularArgs = args;
                try {
                    result = $.evalFile("C:/Users/Administrator/Desktop/after-effects-mcp-main/src/scripts/fixParticular.jsx");
                } catch(err) {
                    result = JSON.stringify({ status: "error", message: "evalFile failed: " + err.toString() });
                }
                logToPanel("Returned from fixParticular.");
                break;
            case "diagParticular":
                logToPanel("Calling diagParticular script...");
                result = diagParticular();
                logToPanel("Returned from diagParticular.");
                break;
            case "executeAtomScript":
                logToPanel("Calling executeAtomScript function...");
                result = executeAtomScript(args);
                logToPanel("Returned from executeAtomScript.");
                break;
            case "importFootage":
                logToPanel("Calling importFootage function...");
                result = importFootage(args);
                logToPanel("Returned from importFootage.");
                break;
            case "placeFootageInComp":
                logToPanel("Calling placeFootageInComp function...");
                result = placeFootageInComp(args);
                logToPanel("Returned from placeFootageInComp.");
                break;
            case "autoCreateProject":
                logToPanel("Calling autoCreateProject function...");
                result = autoCreateProject(args);
                logToPanel("Returned from autoCreateProject.");
                break;
            case "e2eMusicVideo":
            case "createE2EMusicVideo":
                logToPanel("Calling createE2EMusicVideo function...");
                result = createE2EMusicVideo(args);
                logToPanel("Returned from createE2EMusicVideo.");
                break;
            case "applySilhouetteMatte":
                logToPanel("Calling applySilhouetteMatte function...");
                result = applySilhouetteMatte(args);
                logToPanel("Returned from applySilhouetteMatte.");
                break;
            case "applySilhouetteTracking":
                logToPanel("Calling applySilhouetteTracking function...");
                result = applySilhouetteTracking(args);
                logToPanel("Returned from applySilhouetteTracking.");
                break;
            case "importSilhouettePaint":
                logToPanel("Calling importSilhouettePaint function...");
                result = importSilhouettePaint(args);
                logToPanel("Returned from importSilhouettePaint.");
                break;
            case "setTrackMatte":
                logToPanel("Calling setTrackMatte function...");
                result = setTrackMatte(args);
                logToPanel("Returned from setTrackMatte.");
                break;
            default:
                result = JSON.stringify({ error: "Unknown command: " + command });
        }
        logToPanel("Execution finished for: " + command); // Log after switch
        
        // Save the result (ensure result is always a string)
        logToPanel("Preparing to write result file...");
        var resultString = (typeof result === 'string') ? result : JSON.stringify(result);
        
        // Try to parse the result as JSON to add a timestamp
        try {
            var resultObj = JSON.parse(resultString);
            // Add a timestamp to help identify if we're getting fresh results
            resultObj._responseTimestamp = new Date().toISOString();
            resultObj._commandExecuted = command;
            resultString = JSON.stringify(resultObj, null, 2);
            logToPanel("Added timestamp to result JSON for tracking freshness.");
        } catch (parseError) {
            // If it's not valid JSON, append the timestamp as a comment
            logToPanel("Could not parse result as JSON to add timestamp: " + parseError.toString());
            // We'll still continue with the original string
        }
        
        var resultFile = new File(getResultFilePath());
        resultFile.encoding = "UTF-8"; // Ensure UTF-8 encoding
        logToPanel("Opening result file for writing...");
        var opened = resultFile.open("w");
        if (!opened) {
            logToPanel("ERROR: Failed to open result file for writing: " + resultFile.fsName);
            throw new Error("Failed to open result file for writing.");
        }
        logToPanel("Writing to result file...");
        var written = resultFile.write(resultString);
        if (!written) {
             logToPanel("ERROR: Failed to write to result file (write returned false): " + resultFile.fsName);
             // Still try to close, but log the error
        }
        logToPanel("Closing result file...");
        var closed = resultFile.close();
         if (!closed) {
             logToPanel("ERROR: Failed to close result file: " + resultFile.fsName);
             // Continue, but log the error
        }
        logToPanel("Result file write process complete.");
        
        logToPanel("Command completed successfully: " + command); // Changed log message
        statusText.text = "Command completed: " + command;
        
        // Update command file status
        logToPanel("Updating command status to completed...");
        updateCommandStatus("completed");
        logToPanel("Command status updated.");
        
    } catch (error) {
        var errorMsg = "ERROR in executeCommand for '" + command + "': " + error.toString() + (error.line ? " (line: " + error.line + ")" : "");
        logToPanel(errorMsg); // Log detailed error
        statusText.text = "Error: " + error.toString();
        
        // Write detailed error to result file
        try {
            logToPanel("Attempting to write ERROR to result file...");
            var errorResult = JSON.stringify({ 
                status: "error", 
                command: command,
                message: error.toString(),
                line: error.line,
                fileName: error.fileName
            });
            var errorFile = new File(getResultFilePath());
            errorFile.encoding = "UTF-8";
            if (errorFile.open("w")) {
                errorFile.write(errorResult);
                errorFile.close();
                logToPanel("Successfully wrote ERROR to result file.");
            } else {
                 logToPanel("CRITICAL ERROR: Failed to open result file to write error!");
            }
        } catch (writeError) {
             logToPanel("CRITICAL ERROR: Failed to write error to result file: " + writeError.toString());
        }
        
        // Update command file status even after error
        logToPanel("Updating command status to error...");
        updateCommandStatus("error");
        logToPanel("Command status updated to error.");
    }
}

// Update command file status
function updateCommandStatus(status) {
    try {
        var commandFile = new File(getCommandFilePath());
        if (commandFile.exists) {
            commandFile.open("r");
            var content = commandFile.read();
            commandFile.close();
            
            if (content) {
                var commandData = JSON.parse(content);
                commandData.status = status;
                
                commandFile.open("w");
                commandFile.write(JSON.stringify(commandData, null, 2));
                commandFile.close();
            }
        }
    } catch (e) {
        logToPanel("Error updating command status: " + e.toString());
    }
}

// Log message to panel
function logToPanel(message) {
    var timestamp = new Date().toLocaleTimeString();
    logText.text = timestamp + ": " + message + "\n" + logText.text;
}

// Check for new commands
function checkForCommands() {
    if (!autoRunCheckbox.value || isChecking) return;
    
    isChecking = true;
    
    try {
        var commandFile = new File(getCommandFilePath());
        if (commandFile.exists) {
            commandFile.open("r");
            var content = commandFile.read();
            commandFile.close();
            
            if (content) {
                var commandData = JSON.parse(content);
                
                // Check timestamp to avoid re-executing same command
                var cmdTimestamp = new Date(commandData.timestamp).getTime();
                if (cmdTimestamp <= lastCommandTime) {
                    isChecking = false;
                    return;
                }
                
                // Only execute pending commands
                if (commandData.status === "pending") {
                    // Signature verification
                    if (!verifySignature(commandData)) {
                        logToPanel("Signature verification failed - command rejected");
                        lastCommandTime = cmdTimestamp;
                        updateCommandStatus("error");
                        isChecking = false;
                        return;
                    }
                    
                    lastCommandTime = cmdTimestamp;
                    
                    // Update status to running
                    updateCommandStatus("running");
                    
                    // Execute the command
                    executeCommand(commandData.command, commandData.args || {});
                }
            }
        }
    } catch (e) {
        logToPanel("Error checking for commands: " + e.toString());
    }
    
    isChecking = false;
}

// Set up timer to check for commands
function startCommandChecker() {
    app.scheduleTask("checkForCommands()", checkInterval, true);
}

// Add manual check button
var checkButton = panel.add("button", undefined, "Check for Commands Now");
checkButton.onClick = function() {
    logToPanel("Manually checking for commands");

    var args = {
        compName: compNameInput.text || "一拳超人_E2E测试",
        // 参数化：移除硬编码 fallback，空值由 createE2EMusicVideo 内部统一报错
        frameDir: frameDirInput.text,
        bgmPath: "",
        beatTimes: [0, 2, 4, 6, 8, 10, 12],
        energyPeaks: [1.5, 3.5, 5.5, 7.5, 9.5],
        peakValues: [0.8, 0.9, 0.7, 0.95, 0.85],
        bpm: parseFloat(bpmInput.text) || 120,
        width: parseInt(widthInput.text) || 576,
        height: parseInt(heightInput.text) || 768,
        duration: parseFloat(durationInput.text) || 12,
        fps: 30
    };
    
    try {
        var result = createE2EMusicVideo(args);
        var resultObj = JSON.parse(result);
        if (resultObj.success) {
            statusText.text = "Success! Created " + resultObj.compName;
            logToPanel("Success: " + resultObj.message);
            logToPanel("Layers: " + resultObj.totalLayers + ", Keyframes: " + resultObj.beatKeyframes);
        } else {
            statusText.text = "Error: " + resultObj.message;
            logToPanel("Error: " + resultObj.message);
        }
    } catch(e) {
        statusText.text = "Exception: " + e.toString();
        logToPanel("Exception: " + e.toString() + " (line: " + (e.line || "unknown") + ")");
    }
};

// Log startup
logToPanel("MCP Bridge Auto started");
logToPanel("Command file: " + getCommandFilePath());
statusText.text = "Ready - Auto-run is " + (autoRunCheckbox.value ? "ON" : "OFF");

// Start the command checker
startCommandChecker();

// Show the panel
panel.center();
panel.show();

