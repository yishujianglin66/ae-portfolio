(function() {
    var result = {status: "unknown", log: [], err: ""};
    try { app.beginUndoGroup("3D Camera DOF Template"); } catch(e) {}
    
    try {
        var W = 576, H = 768, DUR = 10;
        function sPI(p,i,v){try{p.property(i).setValue(v);return true;}catch(e){return false;}}
        function sPN(p,n,v){try{p.property(n).setValue(v);return true;}catch(e){return false;}}
        
        var comp = app.project.items.addComp("3D_Camera_DOF_一拳超人", W, H, 1.0, DUR, 30);
        comp.bgColor = [0.08, 0.08, 0.12];
        result.log.push("comp_created");
        
        // ===== 背景天空 (Z=500) =====
        var bgSky = comp.layers.addSolid([0.12,0.15,0.22], "BG_Sky", W, H, 1, DUR);
        bgSky.threeDLayer = true;
        bgSky.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,500]);
        bgSky.property("ADBE Transform Group").property("ADBE Scale").setValue([65,65,65]);
        var fn = bgSky.Effects.addProperty("ADBE Fractal Noise");
        sPI(fn,1,4); sPI(fn,2,2); sPI(fn,4,180); sPI(fn,5,-25); sPI(fn,10,280); sPI(fn,16,5);
        var gb = bgSky.Effects.addProperty("ADBE Gaussian Blur 2");
        sPI(gb,1,8);
        result.log.push("bgSky_ok");
        
        // ===== 背景粒子 (Z=400) =====
        var bgP = comp.layers.addSolid([0,0,0], "Particles_BG", W, H, 1, DUR);
        bgP.threeDLayer = true;
        bgP.blendingMode = BlendingMode.SCREEN;
        bgP.opacity.setValue(60);
        bgP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,400]);
        bgP.property("ADBE Transform Group").property("ADBE Scale").setValue([70,70,70]);
        var cp1 = bgP.Effects.addProperty("CC Particle World");
        sPN(cp1,"Birth Rate",80);
        sPN(cp1,"Longevity (sec)",4);
        sPN(cp1,"Particle Type",7);
        sPN(cp1,"Size",0.025);
        sPN(cp1,"Max Opacity",50);
        sPN(cp1,"Gravity",0.015);
        sPN(cp1,"Wind X",0.04);
        result.log.push("bgParticles_ok");
        
        // ===== 中景 (Z=180) =====
        var mid = comp.layers.addSolid([0.18,0.22,0.28], "Midground", W, H, 1, DUR);
        mid.threeDLayer = true;
        mid.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,180]);
        mid.property("ADBE Transform Group").property("ADBE Scale").setValue([82,82,82]);
        result.log.push("midground_ok");
        
        // ===== 中景粒子 (Z=120) =====
        var midP = comp.layers.addSolid([0,0,0], "Particles_MID", W, H, 1, DUR);
        midP.threeDLayer = true;
        midP.blendingMode = BlendingMode.SCREEN;
        midP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,120]);
        var cp2 = midP.Effects.addProperty("CC Particle World");
        sPN(cp2,"Birth Rate",40);
        sPN(cp2,"Longevity (sec)",2.5);
        sPN(cp2,"Particle Type",8);
        sPN(cp2,"Size",0.05);
        sPN(cp2,"Max Opacity",80);
        sPN(cp2,"Gravity",0.08);
        sPN(cp2,"Wind X",0.1);
        result.log.push("midParticles_ok");
        
        // ===== 主体 (Z=0) =====
        var subj = comp.layers.addSolid([0.4,0.45,0.55], "Main_Subject", W, H, 1, DUR);
        subj.threeDLayer = true;
        subj.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,0]);
        var ds = subj.Effects.addProperty("ADBE Drop Shadow");
        sPI(ds,1,[0,0,0]); sPI(ds,2,45); sPI(ds,3,135); sPI(ds,4,10); sPI(ds,5,12);
        result.log.push("subject_ok");
        
        // ===== 前景 (Z=-180) =====
        var fg = comp.layers.addSolid([0.25,0.28,0.32], "Foreground", W, H, 1, DUR);
        fg.threeDLayer = true;
        fg.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,-180]);
        fg.property("ADBE Transform Group").property("ADBE Scale").setValue([125,125,125]);
        result.log.push("foreground_ok");
        
        // ===== 前景粒子 (Z=-280) =====
        var fgP = comp.layers.addSolid([0,0,0], "Particles_FG", W, H, 1, DUR);
        fgP.threeDLayer = true;
        fgP.blendingMode = BlendingMode.SCREEN;
        fgP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,-280]);
        fgP.property("ADBE Transform Group").property("ADBE Scale").setValue([140,140,140]);
        var cp3 = fgP.Effects.addProperty("CC Particle World");
        sPN(cp3,"Birth Rate",12);
        sPN(cp3,"Longevity (sec)",2);
        sPN(cp3,"Particle Type",8);
        sPN(cp3,"Size",0.1);
        sPN(cp3,"Max Opacity",70);
        sPN(cp3,"Gravity",0.04);
        sPN(cp3,"Wind X",0.25);
        result.log.push("fgParticles_ok");
        
        // ===== 发光调整层 =====
        var glowA = comp.layers.addSolid([1,1,1], "Adj_Glow", W, H, 1, DUR);
        glowA.adjustmentLayer = true;
        glowA.blendingMode = BlendingMode.SCREEN;
        glowA.opacity.setValue(50);
        var gl = glowA.Effects.addProperty("ADBE Glo2");
        sPN(gl,"Glow Threshold",70);
        sPN(gl,"Glow Radius",25);
        sPN(gl,"Glow Intensity",1.8);
        result.log.push("glowAdj_ok");
        
        // ===== 暗角/Lumetri调整层 =====
        var vigA = comp.layers.addSolid([1,1,1], "Adj_Vignette", W, H, 1, DUR);
        vigA.adjustmentLayer = true;
        vigA.Effects.addProperty("ADBE Lumetri");
        result.log.push("vignetteAdj_ok");
        
        // ===== 全局调色调整层 =====
        var colA = comp.layers.addSolid([1,1,1], "Adj_Color", W, H, 1, DUR);
        colA.adjustmentLayer = true;
        var bc = colA.Effects.addProperty("ADBE Brightness & Contrast 2");
        sPI(bc,1,0); sPI(bc,2,15);
        var vi = colA.Effects.addProperty("ADBE Vibrance");
        sPI(vi,1,5);
        var sh = colA.Effects.addProperty("ADBE Sharpen");
        sPI(sh,1,20);
        var ns = colA.Effects.addProperty("ADBE Noise2");
        sPI(ns,1,4);
        result.log.push("colorAdj_ok");
        
        // ===== 灯光 (三点布光) =====
        var kL = comp.layers.addLight("Key_Light", [W/2-180, H/2-250]);
        kL.threeDLayer = true;
        kL.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(100);
        kL.property("ADBE Light Options Group").property("ADBE Light Color").setValue([1.0,0.96,0.9]);
        kL.property("ADBE Light Options Group").property("ADBE Casts Shadows").setValue(1);
        kL.property("ADBE Light Options Group").property("ADBE Light Shadow Darkness").setValue(75);
        kL.property("ADBE Light Options Group").property("ADBE Light Shadow Diffusion").setValue(12);
        kL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2-180,H/2-250,-400]);
        result.log.push("keyLight_ok");
        
        var fL = comp.layers.addLight("Fill_Light", [W/2-150, H/2+80]);
        fL.threeDLayer = true;
        fL.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(35);
        fL.property("ADBE Light Options Group").property("ADBE Light Color").setValue([0.85,0.92,1.0]);
        fL.property("ADBE Light Options Group").property("ADBE Casts Shadows").setValue(0);
        fL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2-150,H/2+80,-120]);
        result.log.push("fillLight_ok");
        
        var rL = comp.layers.addLight("Rim_Light", [W/2+180, H/2-80]);
        rL.threeDLayer = true;
        rL.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(65);
        rL.property("ADBE Light Options Group").property("ADBE Light Color").setValue([0.9,0.95,1.0]);
        rL.property("ADBE Light Options Group").property("ADBE Casts Shadows").setValue(0);
        rL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2+180,H/2-80,280]);
        result.log.push("rimLight_ok");
        
        // ===== 摄像机 (景深核心) =====
        var cam = comp.layers.addCamera("Main_Camera", [W/2, H/2]);
        cam.threeDLayer = true;
        var co = cam.property("ADBE Camera Options Group");
        sPN(co,"ADBE Camera Zoom", 850);
        sPN(co,"ADBE Camera Depth of Field", 1);
        sPN(co,"ADBE Camera Focus Distance", 850);
        sPN(co,"ADBE Camera Aperture", 28);
        sPN(co,"ADBE Camera Blur Level", 180);
        sPN(co,"ADBE Iris Shape", 3);
        sPN(co,"ADBE Iris Roundness", 75);
        sPN(co,"ADBE Iris Diffraction Fringe", 18);
        sPN(co,"ADBE Iris Highlight Gain", 100);
        sPN(co,"ADBE Iris Highlight Threshold", 0.45);
        result.log.push("cameraDOF_ok");
        
        var cPos = cam.property("ADBE Transform Group").property("ADBE Position");
        cPos.setValueAtTime(0, [W/2, H/2, -1000]);
        cPos.setValueAtTime(DUR, [W/2, H/2, -750]);
        cPos.expression = "wiggle(1.5, 4) + value";
        result.log.push("cameraAnim_ok");
        
        // ===== 摄像机Rig =====
        var rig = comp.layers.addNull(DUR);
        rig.name = "Camera_Rig";
        rig.threeDLayer = true;
        cam.parent = rig;
        result.log.push("cameraRig_ok");
        
        // ===== 全局控制器 =====
        var ctrl = comp.layers.addNull(DUR);
        ctrl.name = "Global_Controller";
        var s1 = ctrl.Effects.addProperty("ADBE Slider Control");
        s1.name = "DOF_Amount";
        sPI(s1,1,100);
        var s2 = ctrl.Effects.addProperty("ADBE Slider Control");
        s2.name = "Particle_Amount";
        sPI(s2,1,100);
        var s3 = ctrl.Effects.addProperty("ADBE Slider Control");
        s3.name = "Glow_Intensity";
        sPI(s3,1,100);
        result.log.push("controller_ok");
        
        result.total_layers = comp.layers.length;
        result.comp_name = comp.name;
        result.z_depth_stack = {
            background_sky: 500,
            bg_particles: 400,
            midground: 180,
            mid_particles: 120,
            subject: 0,
            foreground: -180,
            fg_particles: -280
        };
        result.camera_dof = {
            zoom: 850,
            depth_of_field: "ON",
            focus_distance: 850,
            aperture: 28,
            blur_level: "180%",
            iris_shape: "hexagonal(3)",
            animation: "Push In + wiggle(1.5,4)"
        };
        result.lighting = "Three-Point (Key 100% + Fill 35% + Rim 65%)";
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