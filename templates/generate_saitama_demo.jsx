(function() {
    var result = {status: "unknown", log: [], layers: []};
    try { app.beginUndoGroup("Saitama Style DOF Scene"); } catch(e) {}
    
    try {
        function sPI(p,i,v){try{p.property(i).setValue(v);return true;}catch(e){return false;}}
        function sPN(p,n,v){try{p.property(n).setValue(v);return true;}catch(e){return false;}}
        
        var W = 576, H = 768, DUR = 8;
        var fps = 30;
        
        var comp = app.project.items.addComp("埼玉_眼神杀_3D景深版", W, H, 1.0, DUR, fps);
        comp.bgColor = [0.06, 0.06, 0.1];
        result.log.push("comp_created");
        
        // =============================================
        // 1. 远背景 - 废墟城市剪影 (Z=600)
        // =============================================
        var bgCity = comp.layers.addSolid([0.08, 0.1, 0.15], "BG_CitySilhouette", W, H, 1, DUR);
        bgCity.threeDLayer = true;
        bgCity.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 600]);
        bgCity.property("ADBE Transform Group").property("ADBE Scale").setValue([60, 60, 60]);
        
        // 用Fractal Noise做城市剪影纹理
        var fnCity = bgCity.Effects.addProperty("ADBE Fractal Noise");
        sPI(fnCity, 1, 6);       // Sharp
        sPI(fnCity, 2, 2);       // Noise Type: Soft Linear
        sPI(fnCity, 4, 300);     // Contrast
        sPI(fnCity, 5, 30);      // Brightness
        sPI(fnCity, 10, 80);     // Scale
        sPI(fnCity, 16, 6);      // Complexity
        
        // 裁掉上半部分，只留下部城市剪影
        var lmCity = bgCity.Effects.addProperty("ADBE Linear Wipe");
        sPI(lmCity, 1, 55);      // Transition Completion
        sPI(lmCity, 2, 180);     // Wipe Angle (从下往上)
        sPI(lmCity, 3, 20);      // Feather
        
        // 色调调整
        var tintCity = bgCity.Effects.addProperty("ADBE Tint");
        sPI(tintCity, 1, [0.05, 0.07, 0.12]);   // 黑色映射
        sPI(tintCity, 2, [0.15, 0.18, 0.25]);   // 白色映射
        
        result.log.push("bg_city_ok");
        
        // =============================================
        // 2. 背景雾气层 (Z=500)
        // =============================================
        var bgFog = comp.layers.addSolid([0.1, 0.12, 0.18], "BG_Fog", W, H, 1, DUR);
        bgFog.threeDLayer = true;
        bgFog.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 500]);
        bgFog.property("ADBE Transform Group").property("ADBE Scale").setValue([65, 65, 65]);
        bgFog.blendingMode = BlendingMode.SCREEN;
        bgFog.opacity.setValue(40);
        
        var fnFog = bgFog.Effects.addProperty("ADBE Fractal Noise");
        sPI(fnFog, 1, 1);       // Basic
        sPI(fnFog, 2, 2);       // Soft Linear
        sPI(fnFog, 4, 150);     // Contrast
        sPI(fnFog, 5, -10);     // Brightness
        sPI(fnFog, 10, 320);    // Scale
        sPI(fnFog, 16, 5);      // Complexity
        
        // 演化动画 - 雾气流动
        var evoProp = fnFog.property(24); // Evolution
        evoProp.setValueAtTime(0, 0);
        evoProp.setValueAtTime(DUR, 180);
        
        result.log.push("bg_fog_ok");
        
        // =============================================
        // 3. 背景粒子层 (Z=420)
        // =============================================
        var bgP = comp.layers.addSolid([0,0,0], "Particles_BG", W, H, 1, DUR);
        bgP.threeDLayer = true;
        bgP.blendingMode = BlendingMode.SCREEN;
        bgP.opacity.setValue(55);
        bgP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 420]);
        bgP.property("ADBE Transform Group").property("ADBE Scale").setValue([72, 72, 72]);
        
        var cp1 = bgP.Effects.addProperty("CC Particle World");
        sPN(cp1, "Birth Rate", 120);
        sPN(cp1, "Longevity (sec)", 5);
        sPN(cp1, "Particle Type", 7);    // Glow Sphere
        sPN(cp1, "Size", 0.03);
        sPN(cp1, "Max Opacity", 40);
        sPN(cp1, "Gravity", 0.02);
        sPN(cp1, "Wind X", 0.06);
        
        result.log.push("bg_particles_ok");
        
        // =============================================
        // 4. 中景废墟 (Z=200)
        // =============================================
        var mid = comp.layers.addSolid([0.12, 0.14, 0.2], "Midground_Ruins", W, H, 1, DUR);
        mid.threeDLayer = true;
        mid.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 200]);
        mid.property("ADBE Transform Group").property("ADBE Scale").setValue([85, 85, 85]);
        
        var fnMid = mid.Effects.addProperty("ADBE Fractal Noise");
        sPI(fnMid, 1, 6);       // Sharp
        sPI(fnMid, 2, 2);
        sPI(fnMid, 4, 250);
        sPI(fnMid, 5, 10);
        sPI(fnMid, 10, 120);
        sPI(fnMid, 16, 5);
        
        var lmMid = mid.Effects.addProperty("ADBE Linear Wipe");
        sPI(lmMid, 1, 40);
        sPI(lmMid, 2, 180);
        sPI(lmMid, 3, 30);
        
        var tintMid = mid.Effects.addProperty("ADBE Tint");
        sPI(tintMid, 1, [0.06, 0.08, 0.14]);
        sPI(tintMid, 2, [0.2, 0.22, 0.3]);
        
        result.log.push("mid_ruins_ok");
        
        // =============================================
        // 5. 中景粒子 (Z=120)
        // =============================================
        var midP = comp.layers.addSolid([0,0,0], "Particles_MID", W, H, 1, DUR);
        midP.threeDLayer = true;
        midP.blendingMode = BlendingMode.SCREEN;
        midP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 120]);
        
        var cp2 = midP.Effects.addProperty("CC Particle World");
        sPN(cp2, "Birth Rate", 60);
        sPN(cp2, "Longevity (sec)", 3);
        sPN(cp2, "Particle Type", 8);    // Star
        sPN(cp2, "Size", 0.06);
        sPN(cp2, "Max Opacity", 70);
        sPN(cp2, "Gravity", 0.06);
        sPN(cp2, "Wind X", 0.12);
        
        result.log.push("mid_particles_ok");
        
        // =============================================
        // 6. 主体 - 埼玉轮廓/眼神 (Z=0)
        // =============================================
        var subj = comp.layers.addSolid([0.15, 0.18, 0.25], "Saitama_Silhouette", W, H, 1, DUR);
        subj.threeDLayer = true;
        subj.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, 0]);
        subj.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([W/2, H/2, 0]);
        
        // 用圆形遮罩模拟光头轮廓
        subj.masks.addProperty("ADBE Mask Atom");
        var mask1 = subj.mask.property(1);
        mask1.name = "HeadMask";
        var maskShape = mask1.property("ADBE Mask Shape");
        var newShape = maskShape.value;
        newShape.vertices = [
            [W/2-110, H/2-140],
            [W/2+110, H/2-140],
            [W/2+130, H/2-80],
            [W/2+120, H/2+20],
            [W/2+90, H/2+100],
            [W/2-90, H/2+100],
            [W/2-120, H/2+20],
            [W/2-130, H/2-80]
        ];
        newShape.closed = true;
        maskShape.setValue(newShape);
        mask1.property("ADBE Mask Feather").setValue([15, 15]);
        
        // 脸部渐变
        var rampSubj = subj.Effects.addProperty("ADBE Ramp");
        sPI(rampSubj, 1, [W/2, H/2-120]);    // Start of Ramp
        sPI(rampSubj, 2, [0.85, 0.82, 0.78]); // Start Color - 亮色
        sPI(rampSubj, 3, [W/2, H/2+100]);      // End of Ramp
        sPI(rampSubj, 4, [0.45, 0.42, 0.48]); // End Color - 暗色
        sPI(rampSubj, 5, 1);                   // Linear Ramp
        
        result.log.push("subject_ok");
        
        // =============================================
        // 7. 眼睛高光 (Z=0 同层上方)
        // =============================================
        var eyes = comp.layers.addSolid([0,0,0], "Eye_Glow", W, H, 1, DUR);
        eyes.threeDLayer = true;
        eyes.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2-20, 0]);
        eyes.blendingMode = BlendingMode.SCREEN;
        eyes.opacity.setValue(100);
        
        // 左眼
        eyes.masks.addProperty("ADBE Mask Atom");
        var maskL = eyes.masks.property(1);
        maskL.name = "LeftEye";
        var mlShape = maskL.property("ADBE Mask Shape");
        var mlVal = mlShape.value;
        mlVal.vertices = [[-55,-12],[-25,-10],[-20,5],[-50,8],[-60,0]];
        mlVal.closed = true;
        mlShape.setValue(mlVal);
        maskL.property("ADBE Mask Feather").setValue([8, 8]);
        
        // 右眼
        eyes.masks.addProperty("ADBE Mask Atom");
        var maskR = eyes.mask.property(2);
        maskR.name = "RightEye";
        var mrShape = maskR.property("ADBE Mask Shape");
        var mrVal = mrShape.value;
        mrVal.vertices = [[25,-10],[55,-12],[60,0],[50,8],[20,5]];
        mrVal.closed = true;
        mrShape.setValue(mrVal);
        maskR.property("ADBE Mask Feather").setValue([8, 8]);
        
        // 眼睛发光
        var eyeGlow = eyes.Effects.addProperty("ADBE Glo2");
        sPN(eyeGlow, "Glow Threshold", 50);
        sPN(eyeGlow, "Glow Radius", 30);
        sPN(eyeGlow, "Glow Intensity", 2.5);
        sPN(eyeGlow, "Glow Colors", 2); // A & B Colors
        sPN(eyeGlow, "Color A", [1, 0.95, 0.8]);
        sPN(eyeGlow, "Color B", [1, 0.8, 0.4]);
        
        // 眼睛闪烁动画
        var eyeOp = eyes.property("ADBE Transform Group").property("ADBE Opacity");
        eyeOp.setValueAtTime(0, 80);
        eyeOp.setValueAtTime(1.2, 100);
        eyeOp.setValueAtTime(1.4, 60);
        eyeOp.setValueAtTime(1.6, 100);
        eyeOp.setValueAtTime(3.5, 100);
        eyeOp.setValueAtTime(3.8, 0);
        eyeOp.setValueAtTime(4.0, 100);
        
        result.log.push("eyes_ok");
        
        // =============================================
        // 8. 前景 (Z=-150)
        // =============================================
        var fg = comp.layers.addSolid([0.08, 0.1, 0.15], "Foreground_Debris", W, H, 1, DUR);
        fg.threeDLayer = true;
        fg.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, -150]);
        fg.property("ADBE Transform Group").property("ADBE Scale").setValue([130, 130, 130]);
        fg.opacity.setValue(70);
        
        var fnFg = fg.Effects.addProperty("ADBE Fractal Noise");
        sPI(fnFg, 1, 5);       // Turbulent
        sPI(fnFg, 2, 2);
        sPI(fnFg, 4, 200);
        sPI(fnFg, 5, -15);
        sPI(fnFg, 10, 180);
        sPI(fnFg, 16, 4);
        
        // 前景只留一些碎片状
        var fgTint = fg.Effects.addProperty("ADBE Tint");
        sPI(fgTint, 1, [0.03, 0.04, 0.06]);
        sPI(fgTint, 2, [0.12, 0.14, 0.18]);
        
        result.log.push("foreground_ok");
        
        // =============================================
        // 9. 前景粒子 (Z=-280)
        // =============================================
        var fgP = comp.layers.addSolid([0,0,0], "Particles_FG", W, H, 1, DUR);
        fgP.threeDLayer = true;
        fgP.blendingMode = BlendingMode.SCREEN;
        fgP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2, -280]);
        fgP.property("ADBE Transform Group").property("ADBE Scale").setValue([150, 150, 150]);
        
        var cp3 = fgP.Effects.addProperty("CC Particle World");
        sPN(cp3, "Birth Rate", 15);
        sPN(cp3, "Longevity (sec)", 2.5);
        sPN(cp3, "Particle Type", 8);    // Star
        sPN(cp3, "Size", 0.12);
        sPN(cp3, "Max Opacity", 65);
        sPN(cp3, "Gravity", 0.03);
        sPN(cp3, "Wind X", 0.3);
        
        result.log.push("fg_particles_ok");
        
        // =============================================
        // 10. 发光调整层
        // =============================================
        var glowA = comp.layers.addSolid([1,1,1], "Adj_Glow", W, H, 1, DUR);
        glowA.adjustmentLayer = true;
        glowA.blendingMode = BlendingMode.SCREEN;
        glowA.opacity.setValue(45);
        
        var gl = glowA.Effects.addProperty("ADBE Glo2");
        sPN(gl, "Glow Threshold", 65);
        sPN(gl, "Glow Radius", 20);
        sPN(gl, "Glow Intensity", 1.6);
        
        result.log.push("glow_adj_ok");
        
        // =============================================
        // 11. 暗角调整层
        // =============================================
        var vigA = comp.layers.addSolid([1,1,1], "Adj_Vignette", W, H, 1, DUR);
        vigA.adjustmentLayer = true;
        
        // 用Lens Distortion的暗角
        var ld = vigA.Effects.addProperty("ADBE Lens Distortion 2");
        sPI(ld, 4, 1);   // Remove distortion
        
        // 或者用椭圆遮罩做暗角
        vigA.masks.addProperty("ADBE Mask Atom");
        var vigMask = vigA.masks.property(1);
        vigMask.name = "Vignette";
        vigMask.inverted = true;
        var vmShape = vigMask.property("ADBE Mask Shape");
        var vmVal = vmShape.value;
        var vW = W * 0.75, vH = H * 0.7;
        vmVal.vertices = [
            [W/2-vW/2, H/2-vH/2],
            [W/2+vW/2, H/2-vH/2],
            [W/2+vW/2, H/2+vH/2],
            [W/2-vW/2, H/2+vH/2]
        ];
        vmVal.closed = true;
        vmShape.setValue(vmVal);
        vigMask.property("ADBE Mask Feather").setValue([120, 120]);
        vigMask.property("ADBE Mask Opacity").setValue(65);
        
        result.log.push("vignette_ok");
        
        // =============================================
        // 12. 颜色调整层
        // =============================================
        var colA = comp.layers.addSolid([1,1,1], "Adj_Color", W, H, 1, DUR);
        colA.adjustmentLayer = true;
        
        var bc = colA.Effects.addProperty("ADBE Brightness & Contrast 2");
        sPI(bc, 1, 5);      // Brightness
        sPI(bc, 2, 20);     // Contrast
        
        var vi = colA.Effects.addProperty("ADBE Vibrance");
        sPI(vi, 1, 8);      // Vibrance
        
        var sh = colA.Effects.addProperty("ADBE Sharpen");
        sPI(sh, 1, 25);     // Sharpen Amount
        
        var ns = colA.Effects.addProperty("ADBE Noise2");
        sPI(ns, 1, 5);      // Noise Amount
        
        result.log.push("color_adj_ok");
        
        // =============================================
        // 13. 灯光系统
        // =============================================
        // 主光 - 冷色调，前上方
        var kL = comp.layers.addLight("Key_Light", [W/2-150, H/2-200]);
        kL.threeDLayer = true;
        sPN(kL.property("ADBE Light Options Group"), "ADBE Light Intensity", 100);
        sPN(kL.property("ADBE Light Options Group"), "ADBE Light Color", [0.85, 0.9, 1.0]);
        sPN(kL.property("ADBE Light Options Group"), "ADBE Casts Shadows", 1);
        sPN(kL.property("ADBE Light Options Group"), "ADBE Light Shadow Darkness", 70);
        sPN(kL.property("ADBE Light Options Group"), "ADBE Light Shadow Diffusion", 15);
        kL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2-150, H/2-200, -350]);
        
        // 补光 - 暖色调，侧下方
        var fL = comp.layers.addLight("Fill_Light", [W/2+120, H/2+100]);
        fL.threeDLayer = true;
        sPN(fL.property("ADBE Light Options Group"), "ADBE Light Intensity", 40);
        sPN(fL.property("ADBE Light Options Group"), "ADBE Light Color", [1.0, 0.9, 0.8]);
        sPN(fL.property("ADBE Light Options Group"), "ADBE Casts Shadows", 0);
        fL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2+120, H/2+100, -100]);
        
        // 轮廓光 - 冷白，后方
        var rL = comp.layers.addLight("Rim_Light", [W/2+80, H/2-100]);
        rL.threeDLayer = true;
        sPN(rL.property("ADBE Light Options Group"), "ADBE Light Intensity", 70);
        sPN(rL.property("ADBE Light Options Group"), "ADBE Light Color", [0.9, 0.95, 1.0]);
        sPN(rL.property("ADBE Light Options Group"), "ADBE Casts Shadows", 0);
        rL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2+80, H/2-100, 250]);
        
        result.log.push("lights_ok");
        
        // =============================================
        // 14. 摄像机 (景深核心)
        // =============================================
        var cam = comp.layers.addCamera("Main_Camera", [W/2, H/2]);
        cam.threeDLayer = true;
        var co = cam.property("ADBE Camera Options Group");
        sPN(co, "ADBE Camera Zoom", 850);
        sPN(co, "ADBE Camera Depth of Field", 1);
        sPN(co, "ADBE Camera Focus Distance", 850);
        sPN(co, "ADBE Camera Aperture", 32);
        sPN(co, "ADBE Camera Blur Level", 180);
        sPN(co, "ADBE Iris Shape", 4);    // 六边形
        sPN(co, "ADBE Iris Roundness", 75);
        sPN(co, "ADBE Iris Diffraction Fringe", 15);
        sPN(co, "ADBE Iris Highlight Gain", 120);
        sPN(co, "ADBE Iris Highlight Threshold", 0.4);
        
        // 摄像机动画：缓慢推镜 + 手持抖动
        var cPos = cam.property("ADBE Transform Group").property("ADBE Position");
        cPos.setValueAtTime(0, [W/2, H/2, -1100]);
        cPos.setValueAtTime(2, [W/2, H/2, -950]);
        cPos.setValueAtTime(4, [W/2, H/2, -900]);
        cPos.setValueAtTime(6, [W/2, H/2, -850]);
        cPos.setValueAtTime(DUR, [W/2, H/2, -820]);
        cPos.expression = "wiggle(1.2, 5) + value";
        
        // 对焦距离呼吸效应
        var fDist = co.property("ADBE Camera Focus Distance");
        fDist.expression = "base = 850; breath = Math.sin(time * 0.8 * Math.PI * 2) * 10; base + breath";
        
        // 摄像机轻微旋转（增加动感）
        var cRot = cam.property("ADBE Transform Group").property("ADBE Rotation Z");
        cRot.expression = "wiggle(0.5, 0.5)";
        
        result.log.push("camera_ok");
        
        // =============================================
        // 15. 摄像机Rig
        // =============================================
        var rig = comp.layers.addNull(DUR);
        rig.name = "Camera_Rig";
        rig.threeDLayer = true;
        cam.parent = rig;
        
        // 整体轻微摇摆
        var rigRot = rig.property("ADBE Transform Group").property("ADBE Rotation Y");
        rigRot.setValueAtTime(0, -3);
        rigRot.setValueAtTime(DUR, 3);
        
        result.log.push("camera_rig_ok");
        
        // =============================================
        // 16. 全局控制器
        // =============================================
        var ctrl = comp.layers.addNull(DUR);
        ctrl.name = "Global_Controller";
        var s1 = ctrl.Effects.addProperty("ADBE Slider Control");
        s1.name = "DOF_Amount";
        sPI(s1, 1, 100);
        var s2 = ctrl.Effects.addProperty("ADBE Slider Control");
        s2.name = "Particle_Amount";
        sPI(s2, 1, 100);
        var s3 = ctrl.Effects.addProperty("ADBE Slider Control");
        s3.name = "Glow_Intensity";
        sPI(s3, 1, 100);
        
        result.log.push("controller_ok");
        
        result.total_layers = comp.layers.length;
        result.comp_name = comp.name;
        result.scene_summary = {
            duration: DUR + "s",
            resolution: W + "x" + H,
            fps: fps,
            z_layers: 9,
            particle_layers: 3,
            lights: 3,
            camera_animation: "Push In + wiggle + Y-axis swing",
            style: "Saitama serious face - 3D depth of field"
        };
        result.status = "success";
        try { app.endUndoGroup(); } catch(e) {}
        
    } catch(e) {
        result.status = "error";
        result.message = e.toString();
        try { app.endUndoGroup(); } catch(e2) {}
    }
    
    try { return JSON.stringify(result, null, 2); }
    catch(e) { return "fallback: " + result.status + " | " + (result.message||""); }
})();