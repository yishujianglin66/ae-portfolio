// applyNewtonDynamics.jsx
// 牛顿动力学 - 为图层添加物理模拟表达式
// Phase 2 扩展 - 新增工具

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function applyNewtonDynamics(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (!args.layerIndices || !args.layerIndices.length) {
            return buildError("E109", "E109: layerIndices 参数必填且必须为非空数组");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var gravity = args.gravity !== undefined ? args.gravity : 2000;
        var bounce = args.bounce !== undefined ? args.bounce : 0.6;
        var friction = args.friction !== undefined ? args.friction : 0.98;
        var groundY = args.groundY !== undefined ? args.groundY : comp.height - 50;
        var startVelocity = args.startVelocity || [0, 0];
        var gravityDirection = args.gravityDirection || "down";
        var collisionLayers = args.collisionLayers || [];
        var mode = args.mode || "expression";

        app.beginUndoGroup("Apply Newton Dynamics");

        var resultLayers = [];

        for (var li = 0; li < args.layerIndices.length; li++) {
            var idx = args.layerIndices[li];
            if (!validateLayerIndex(comp, idx)) {
                continue;
            }

            var layer = comp.layer(idx);

            if (mode === "keyframe" || mode === "bake") {
                bakeDynamicsKeyframes(layer, comp, gravity, bounce, friction, groundY, startVelocity, gravityDirection);
            } else {
                applyDynamicsExpression(layer, comp, gravity, bounce, friction, groundY, startVelocity, gravityDirection, collisionLayers);
            }

            resultLayers.push({
                index: idx,
                name: layer.name,
                mode: mode
            });
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "牛顿动力学已应用",
            mode: mode,
            gravity: gravity,
            bounce: bounce,
            friction: friction,
            groundY: groundY,
            layers: resultLayers
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

function applyDynamicsExpression(layer, comp, gravity, bounce, friction, groundY, startVel, direction, collisionLayers) {
    var posProp = layer.property("Transform").property("Position");

    var expr = "";
    expr += "// Newton Dynamics - 牛顿物理模拟\n";
    expr += "// 重力 " + gravity + " 弹性 " + bounce + " 摩擦 " + friction + "\n";
    expr += "\n";
    expr += "vy = " + startVel[1] + ";\n";
    expr += "vx = " + startVel[0] + ";\n";
    expr += "g = " + gravity + ";\n";
    expr += "bounce = " + bounce + ";\n";
    expr += "friction = " + friction + ";\n";
    expr += "groundY = " + groundY + ";\n";
    expr += "\n";
    expr += "// 获取图层尺寸\n";
    expr += "L = thisLayer;\n";
    expr += "layerHeight = L.sourceRectAtTime(time - inPoint, false).height * L.scale[1] / 100;\n";
    expr += "layerWidth = L.sourceRectAtTime(time - inPoint, false).width * L.scale[0] / 100;\n";
    expr += "anchorOffsetY = layerHeight * (L.anchorPoint[1] / L.sourceRectAtTime(time - inPoint, false).height);\n";
    expr += "anchorOffsetX = layerWidth * (L.anchorPoint[0] / L.sourceRectAtTime(time - inPoint, false).width);\n";
    expr += "\n";
    expr += "// 初始位置\n";
    expr += "startPos = valueAtTime(inPoint);\n";
    expr += "t = time - inPoint;\n";
    expr += "\n";
    expr += "if (t <= 0) {\n";
    expr += "    value;\n";
    expr += "} else {\n";
    expr += "    // 简单的物理积分（基于帧步进）\n";
    expr += "    pos = startPos;\n";
    expr += "    velY = vy;\n";
    expr += "    velX = vx;\n";
    expr += "    fps = 1.0 / thisComp.frameDuration;\n";
    expr += "    dt = 1.0 / fps;\n";
    expr += "    steps = Math.floor(t * fps);\n";
    expr += "    \n";
    expr += "    for (i = 0; i < steps; i++) {\n";
    expr += "        // 应用重力\n";
    if (direction === "down") {
        expr += "        velY += g * dt;\n";
    } else if (direction === "up") {
        expr += "        velY -= g * dt;\n";
    } else if (direction === "left") {
        expr += "        velX -= g * dt;\n";
    } else if (direction === "right") {
        expr += "        velX += g * dt;\n";
    }
    expr += "        \n";
    expr += "        // 应用速度\n";
    expr += "        pos[0] += velX * dt;\n";
    expr += "        pos[1] += velY * dt;\n";
    expr += "        \n";
    expr += "        // 地面碰撞检测（底部）\n";
    if (direction === "down" || direction === "up") {
        expr += "        bottomY = groundY - anchorOffsetY;\n";
        expr += "        topY = anchorOffsetY;\n";
        if (direction === "down") {
            expr += "        if (pos[1] >= bottomY) {\n";
            expr += "            pos[1] = bottomY;\n";
            expr += "            velY = -velY * bounce;\n";
            expr += "            velX *= friction;\n";
            expr += "            if (Math.abs(velY) < 5) velY = 0;\n";
            expr += "        }\n";
        } else {
            expr += "        if (pos[1] <= topY) {\n";
            expr += "            pos[1] = topY;\n";
            expr += "            velY = -velY * bounce;\n";
            expr += "            velX *= friction;\n";
            expr += "            if (Math.abs(velY) < 5) velY = 0;\n";
            expr += "        }\n";
        }
    }
    expr += "        \n";
    expr += "        // 左右边界碰撞\n";
    expr += "        leftX = anchorOffsetX;\n";
    expr += "        rightX = thisComp.width - anchorOffsetX;\n";
    expr += "        if (pos[0] <= leftX) {\n";
    expr += "            pos[0] = leftX;\n";
    expr += "            velX = -velX * bounce;\n";
    expr += "        }\n";
    expr += "        if (pos[0] >= rightX) {\n";
    expr += "            pos[0] = rightX;\n";
    expr += "            velX = -velX * bounce;\n";
    expr += "        }\n";
    expr += "    }\n";
    expr += "    pos;\n";
    expr += "}\n";

    posProp.expression = expr;
}

function bakeDynamicsKeyframes(layer, comp, gravity, bounce, friction, groundY, startVel, direction) {
    var posProp = layer.property("Transform").property("Position");
    var fps = comp.frameRate;
    var startPos = posProp.valueAtTime(layer.inPoint, false);

    var pos = [startPos[0], startPos[1]];
    var velX = startVel[0];
    var velY = startVel[1];
    var dt = 1.0 / fps;

    var layerHeight = 0;
    var layerWidth = 0;
    try {
        var src = layer.sourceRectAtTime(layer.inPoint, false);
        layerHeight = src.height * layer.property("Transform").property("Scale").value[1] / 100;
        layerWidth = src.width * layer.property("Transform").property("Scale").value[0] / 100;
    } catch (e) {
        layerHeight = 100;
        layerWidth = 100;
    }

    var bottomY = groundY - layerHeight / 2;
    var topY = layerHeight / 2;
    var leftX = layerWidth / 2;
    var rightX = comp.width - layerWidth / 2;

    var totalTime = layer.outPoint - layer.inPoint;
    var totalFrames = Math.floor(totalTime * fps);

    var restingFrames = 0;

    for (var f = 0; f < totalFrames; f++) {
        var t = layer.inPoint + f / fps;

        if (direction === "down") {
            velY += gravity * dt;
        } else if (direction === "up") {
            velY -= gravity * dt;
        } else if (direction === "left") {
            velX -= gravity * dt;
        } else if (direction === "right") {
            velX += gravity * dt;
        }

        pos[0] += velX * dt;
        pos[1] += velY * dt;

        var collided = false;

        if (direction === "down" && pos[1] >= bottomY) {
            pos[1] = bottomY;
            velY = -velY * bounce;
            velX *= friction;
            collided = true;
        } else if (direction === "up" && pos[1] <= topY) {
            pos[1] = topY;
            velY = -velY * bounce;
            velX *= friction;
            collided = true;
        }

        if (pos[0] <= leftX) {
            pos[0] = leftX;
            velX = -velX * bounce;
            collided = true;
        }
        if (pos[0] >= rightX) {
            pos[0] = rightX;
            velX = -velX * bounce;
            collided = true;
        }

        if (Math.abs(velY) < 5 && Math.abs(velX) < 5 && collided) {
            restingFrames++;
        } else {
            restingFrames = 0;
        }

        if (restingFrames > fps * 0.5) {
            break;
        }

        posProp.setValueAtTime(t, [pos[0], pos[1]]);
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = applyNewtonDynamics(args);
$.write(result);
