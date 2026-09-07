// apply3DComposition.jsx
// 3D 合成增强 - 创建和管理 3D 合成场景
// Phase 5-1 扩展 - 核心功能补全之三

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

function apply3DComposition(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "compName 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "合成未找到: " + args.compName);
        }

        // 参数解析
        var layerIndices = args.layerIndices || [];
        var enable3D = args.enable3D !== false && args.enable3D !== "false";
        var position = args.position || null;
        var orientation = args.orientation || null;
        var material = args.material || "standard";
        var lighting = args.lighting || null;
        var cameraAnimation = args.cameraAnimation || null;
        var depthOfField = args.depthOfField || null;

        app.beginUndoGroup("Apply 3D Composition");

        var processedLayers = [];
        var appliedProps = [];

        // 批量处理图层
        for (var i = 0; i < layerIndices.length; i++) {
            var idx = Number(layerIndices[i]);
            if (isNaN(idx) || !validateLayerIndex(comp, idx)) {
                appliedProps.push("layer_skip_invalid:" + layerIndices[i]);
                continue;
            }

            var layer = comp.layer(idx);

            // 启用/禁用 3D 图层
            if (enable3D) {
                try {
                    layer.threeDLayer = true;
                    appliedProps.push("layer_3d_enabled:" + idx);
                } catch (e) {
                    appliedProps.push("layer_3d_failed:" + idx);
                    continue;
                }
            } else {
                try {
                    layer.threeDLayer = false;
                    appliedProps.push("layer_3d_disabled:" + idx);
                } catch (e) {
                    appliedProps.push("layer_3d_disable_failed:" + idx);
                    continue;
                }
            }

            // 设置 3D 位置
            if (enable3D && position) {
                try {
                    var posProp = layer.property("ADBE Transform Group").property("ADBE Position");
                    var currentPos = posProp.value;
                    var newPos = [
                        position[0] !== undefined ? Number(position[0]) : currentPos[0],
                        position[1] !== undefined ? Number(position[1]) : currentPos[1],
                        position[2] !== undefined ? Number(position[2]) : (currentPos.length > 2 ? currentPos[2] : 0)
                    ];
                    posProp.setValue(newPos);
                    appliedProps.push("position_set:" + idx);
                } catch (e) {
                    appliedProps.push("position_failed:" + idx);
                }
            }

            // 设置 3D 方向（Orientation）
            if (enable3D && orientation) {
                try {
                    var orientProp = layer.property("ADBE Transform Group").property("ADBE Orientation");
                    var newOrient = [
                        Number(orientation[0]) || 0,
                        Number(orientation[1]) || 0,
                        Number(orientation[2]) || 0
                    ];
                    orientProp.setValue(newOrient);
                    appliedProps.push("orientation_set:" + idx);
                } catch (e) {
                    appliedProps.push("orientation_failed:" + idx);
                }
            }

            // 材质效果模拟
            if (enable3D && material && material !== "standard") {
                try {
                    if (material === "glow") {
                        var glowFx = layer.Effects.addProperty("ADBE Glo2i");
                        if (glowFx) {
                            glowFx.property("Glow Threshold").setValue(0.6);
                            glowFx.property("Glow Radius").setValue(20);
                            glowFx.property("Glow Intensity").setValue(1.5);
                            appliedProps.push("material_glow:" + idx);
                        }
                    } else if (material === "metal") {
                        var ccFx = layer.Effects.addProperty("ADBE Color Control");
                        if (ccFx) {
                            ccFx.property("Color").setValue([0.7, 0.7, 0.75]);
                            appliedProps.push("material_metal:" + idx);
                        }
                        // 添加锐化增强金属感
                        try {
                            var sharpFx = layer.Effects.addProperty("ADBE Sharpen");
                            sharpFx.property("Sharpen Amount").setValue(30);
                        } catch (sharpenErr) {}
                    } else if (material === "glass") {
                        var blurFx = layer.Effects.addProperty("ADBE Fast Blur");
                        if (blurFx) {
                            blurFx.property("Blurriness").setValue(2);
                            appliedProps.push("material_glass:" + idx);
                        }
                        try {
                            var brightFx = layer.Effects.addProperty("ADBE Brightness & Contrast 2");
                            brightFx.property("Brightness").setValue(10);
                            brightFx.property("Contrast").setValue(-10);
                        } catch (bcErr) {}
                    }
                } catch (e) {
                    appliedProps.push("material_failed:" + idx);
                }
            }

            processedLayers.push({
                layerIndex: idx,
                layerName: layer.name,
                threeDEnabled: layer.threeDLayer
            });
        }

        // 创建 3D 灯光
        var lightInfo = null;
        if (lighting) {
            try {
                var lightTypeStr = (lighting.type || "point").toLowerCase();
                var lightType = LightType.POINT;
                if (lightTypeStr === "parallel") lightType = LightType.PARALLEL;
                else if (lightTypeStr === "spot") lightType = LightType.SPOT;
                else if (lightTypeStr === "ambient") lightType = LightType.AMBIENT;

                var lightColor = lighting.color || [1, 1, 1];
                var lightIntensity = lighting.intensity !== undefined ? Number(lighting.intensity) : 100;
                var lightPos = lighting.position || [comp.width / 2, comp.height / 2, -500];

                var lightLayer = comp.layers.addLight("3D_Light_" + lightTypeStr, lightType);
                lightLayer.property("ADBE Transform Group").property("ADBE Position").setValue(lightPos);

                var lightOptions = lightLayer.property("ADBE Light Options Group");
                lightOptions.property("ADBE Light Intensity").setValue(lightIntensity);
                lightOptions.property("ADBE Light Color").setValue([lightColor[0], lightColor[1], lightColor[2]]);

                // 聚光灯额外参数
                if (lightType === LightType.SPOT && lighting.spotAngle !== undefined) {
                    try {
                        lightOptions.property("ADBE Light Cone Angle").setValue(Number(lighting.spotAngle));
                    } catch (e) {}
                    if (lighting.spotFeather !== undefined) {
                        try {
                            lightOptions.property("ADBE Light Cone Feather").setValue(Number(lighting.spotFeather));
                        } catch (e) {}
                    }
                }

                lightInfo = {
                    name: lightLayer.name,
                    type: lightTypeStr,
                    index: lightLayer.index,
                    intensity: lightIntensity
                };
                appliedProps.push("light_created:" + lightTypeStr);
            } catch (e) {
                appliedProps.push("light_failed:" + e.toString());
            }
        }

        // 创建 3D 摄像机
        var cameraInfo = null;
        if (cameraAnimation || depthOfField) {
            try {
                var camPos = [comp.width / 2, comp.height / 2, -1000];
                if (args.cameraPosition) {
                    camPos = [
                        Number(args.cameraPosition[0]) || comp.width / 2,
                        Number(args.cameraPosition[1]) || comp.height / 2,
                        Number(args.cameraPosition[2]) || -1000
                    ];
                }
                var cameraLayer = comp.layers.addCamera("3D_Camera", [camPos[0], camPos[1]]);
                cameraLayer.property("ADBE Transform Group").property("ADBE Position").setValue(camPos);

                var camOptions = cameraLayer.property("ADBE Camera Options Group");

                // 景深设置
                if (depthOfField && depthOfField.enabled) {
                    try {
                        camOptions.property("ADBE Camera Depth of Field").setValue(1);
                        if (depthOfField.focusDistance !== undefined) {
                            camOptions.property("ADBE Camera Focus Distance").setValue(Number(depthOfField.focusDistance));
                        }
                        if (depthOfField.aperture !== undefined) {
                            camOptions.property("ADBE Camera Aperture").setValue(Number(depthOfField.aperture));
                        }
                        if (depthOfField.blurLevel !== undefined) {
                            camOptions.property("ADBE Camera Blur Level").setValue(Number(depthOfField.blurLevel));
                        }
                        appliedProps.push("depth_of_field_enabled");
                    } catch (e) {
                        appliedProps.push("depth_of_field_failed:" + e.toString());
                    }
                }

                // 摄像机动画
                if (cameraAnimation) {
                    var animPath = cameraAnimation.path || "orbit";
                    var animDuration = cameraAnimation.duration !== undefined ? Number(cameraAnimation.duration) : 5;
                    var camTransform = cameraLayer.property("ADBE Transform Group");
                    var camPosProp = camTransform.property("ADBE Position");
                    var camPointOfInterest = camTransform.property("ADBE Point of Interest");

                    if (animPath === "orbit") {
                        var radius = cameraAnimation.radius !== undefined ? Number(cameraAnimation.radius) : Math.min(comp.width, comp.height) * 0.8;
                        var center = [comp.width / 2, comp.height / 2, 0];
                        var frames = Math.floor(animDuration * comp.frameRate);
                        for (var f = 0; f <= frames; f++) {
                            var t = f / comp.frameRate;
                            var angle = (f / frames) * Math.PI * 2;
                            var x = center[0] + Math.cos(angle) * radius;
                            var y = center[1] + Math.sin(angle) * radius;
                            var z = center[2] + radius * 0.5;
                            camPosProp.setValueAtTime(t, [x, y, z]);
                            camPointOfInterest.setValueAtTime(t, center);
                        }
                        appliedProps.push("camera_orbit_animation:" + animDuration + "s");
                    } else if (animPath === "dolly") {
                        var startZ = cameraAnimation.startZ !== undefined ? Number(cameraAnimation.startZ) : -500;
                        var endZ = cameraAnimation.endZ !== undefined ? Number(cameraAnimation.endZ) : -2000;
                        var frames = Math.floor(animDuration * comp.frameRate);
                        for (var f = 0; f <= frames; f++) {
                            var t = f / comp.frameRate;
                            var z = startZ + (endZ - startZ) * (f / frames);
                            camPosProp.setValueAtTime(t, [comp.width / 2, comp.height / 2, z]);
                            camPointOfInterest.setValueAtTime(t, [comp.width / 2, comp.height / 2, 0]);
                        }
                        appliedProps.push("camera_dolly_animation:" + animDuration + "s");
                    } else if (animPath === "crane") {
                        var frames = Math.floor(animDuration * comp.frameRate);
                        var craneHeight = cameraAnimation.craneHeight !== undefined ? Number(cameraAnimation.craneHeight) : 300;
                        for (var f = 0; f <= frames; f++) {
                            var t = f / comp.frameRate;
                            var y = comp.height / 2 + Math.sin((f / frames) * Math.PI) * craneHeight;
                            camPosProp.setValueAtTime(t, [comp.width / 2, y, -1000]);
                            camPointOfInterest.setValueAtTime(t, [comp.width / 2, comp.height / 2, 0]);
                        }
                        appliedProps.push("camera_crane_animation:" + animDuration + "s");
                    } else if (animPath === "push_in") {
                        var frames = Math.floor(animDuration * comp.frameRate);
                        var startZ = -800;
                        var endZ = -400;
                        for (var f = 0; f <= frames; f++) {
                            var t = f / comp.frameRate;
                            var z = startZ + (endZ - startZ) * (f / frames);
                            camPosProp.setValueAtTime(t, [comp.width / 2, comp.height / 2, z]);
                            camPointOfInterest.setValueAtTime(t, [comp.width / 2, comp.height / 2, 0]);
                        }
                        appliedProps.push("camera_push_in_animation:" + animDuration + "s");
                    }
                }

                cameraInfo = {
                    name: cameraLayer.name,
                    index: cameraLayer.index,
                    position: camPos
                };
                appliedProps.push("camera_created");
            } catch (e) {
                appliedProps.push("camera_failed:" + e.toString());
            }
        }

        app.endUndoGroup();

        return buildSuccess({
            processedLayers: processedLayers,
            lightInfo: lightInfo,
            cameraInfo: cameraInfo,
            enable3D: enable3D,
            material: material,
            appliedProps: appliedProps
        }, { message: "3D 合成设置成功" });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", error.toString());
    }
}

// 从 args.json 读取参数
var argsFile = new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json");
var args = {};
if (argsFile.exists) {
    argsFile.open("r");
    var _content = argsFile.read();
    argsFile.close();
    if (_content) {
        try { args = JSON.parse(_content); } catch (_e) { args = {}; }
    }
}

var result = apply3DComposition(args);
$.write(result);
