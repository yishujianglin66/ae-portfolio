/**
 * 3D Camera DOF Template Generator
 * 三维层+摄像机景深 工程模板自动生成脚本
 * 
 * 基于一拳超人视频逆向分析结果
 * 适用: After Effects CC 2020+
 */

(function() {
    app.beginUndoGroup("Create 3D Camera DOF Template");
    
    try {
        var compWidth = 576;
        var compHeight = 768;
        var compFps = 30;
        var compDuration = 17.6;
        var compName = "3D_Camera_DOF_Template";
        
        var comp = app.project.items.addComp(
            compName,
            compWidth,
            compHeight,
            1.0,
            compDuration,
            compFps
        );
        
        comp.bgColor = [0.1, 0.1, 0.15];
        
        createLights(comp);
        createCamera(comp);
        createBackgroundLayers(comp);
        createParticleLayers(comp);
        createSubjectLayers(comp);
        createForegroundLayers(comp);
        createAdjustmentLayers(comp);
        createNullControllers(comp);
        
        alert("3D Camera DOF Template 创建成功!\n\n" +
              "• 摄像机: 双节点, 50mm, 景深开启\n" +
              "• 灯光: 三点布光 (Key/Fill/Rim)\n" +
              "• 粒子: 3层景深粒子系统\n" +
              "• 调整层: 调色/暗角/发光\n" +
              "• 控制层: Camera_Rig + Global_Controller\n\n" +
              "请替换占位图层为实际素材");
        
    } catch(e) {
        alert("创建失败: " + e.message);
    }
    
    app.endUndoGroup();
    
    function createCamera(comp) {
        var camera = comp.layers.addCamera("Main Camera", [compWidth/2, compHeight/2]);
        camera.threeDLayer = true;
        
        var cameraOpts = camera.property("ADBE Camera Options Group");
        cameraOpts.property("ADBE Camera Zoom").setValue(900);
        cameraOpts.property("ADBE Camera Depth of Field").setValue(1);
        cameraOpts.property("ADBE Camera Focus Distance").setValue(800);
        cameraOpts.property("ADBE Camera Aperture").setValue(30);
        cameraOpts.property("ADBE Camera Blur Level").setValue(180);
        cameraOpts.property("ADBE Camera Iris Shape").setValue(3);
        cameraOpts.property("ADBE Camera Iris Rotation").setValue(0);
        cameraOpts.property("ADBE Camera Iris Roundness").setValue(80);
        cameraOpts.property("ADBE Camera Iris Aspect Ratio").setValue(1.0);
        cameraOpts.property("ADBE Camera Diffraction Fringe").setValue(20);
        cameraOpts.property("ADBE Camera Highlight Gain").setValue(100);
        cameraOpts.property("ADBE Camera Highlight Threshold").setValue(50);
        
        camera.property("ADBE Transform Group").property("ADBE Position").setValue(
            [compWidth/2, compHeight/2, -1000]
        );
        
        var posExpr = 'wiggle(2, 3) + value';
        camera.property("ADBE Transform Group").property("ADBE Position").expression = posExpr;
        
        return camera;
    }
    
    function createLights(comp) {
        var keyLight = comp.layers.addLight("Key Light", [compWidth/2 - 200, compHeight/2 - 300]);
        keyLight.threeDLayer = true;
        keyLight.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(100);
        keyLight.property("ADBE Light Options Group").property("ADBE Light Color").setValue([1.0, 0.97, 0.94]);
        keyLight.property("ADBE Light Options Group").property("ADBE Light Casts Shadows").setValue(1);
        keyLight.property("ADBE Light Options Group").property("ADBE Light Shadow Darkness").setValue(80);
        keyLight.property("ADBE Light Options Group").property("ADBE Light Shadow Diffusion").setValue(15);
        keyLight.property("ADBE Transform Group").property("ADBE Position").setValue(
            [compWidth/2 - 200, compHeight/2 - 300, -400]
        );
        
        var fillLight = comp.layers.addLight("Fill Light", [compWidth/2 + 150, compHeight/2 + 100]);
        fillLight.threeDLayer = true;
        fillLight.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(35);
        fillLight.property("ADBE Light Options Group").property("ADBE Light Color").setValue([0.88, 0.94, 1.0]);
        fillLight.property("ADBE Light Options Group").property("ADBE Light Casts Shadows").setValue(0);
        fillLight.property("ADBE Transform Group").property("ADBE Position").setValue(
            [compWidth/2 + 150, compHeight/2 + 100, -100]
        );
        
        var rimLight = comp.layers.addLight("Rim Light", [compWidth/2 + 200, compHeight/2 - 100]);
        rimLight.threeDLayer = true;
        rimLight.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(70);
        rimLight.property("ADBE Light Options Group").property("ADBE Light Color").setValue([0.95, 0.97, 1.0]);
        rimLight.property("ADBE Light Options Group").property("ADBE Light Casts Shadows").setValue(0);
        rimLight.property("ADBE Transform Group").property("ADBE Position").setValue(
            [compWidth/2 + 200, compHeight/2 - 100, 300]
        );
    }
    
    function createAdjustmentLayers(comp) {
        var colorAdj = comp.layers.addSolid([1, 1, 1], "Adjustment_GlobalColor", comp.width, comp.height, comp.pixelAspect, comp.duration);
        colorAdj.adjustmentLayer = true;
        
        try {
            var lumetri = colorAdj.effects.addProperty("Lumetri Color");
        } catch(e) {}
        
        var sharpen = colorAdj.effects.addProperty("ADBE Sharpen 2");
        sharpen.property(1).setValue(25);
        
        var noise = colorAdj.effects.addProperty("ADBE Noise 2");
        noise.property(1).setValue(5);
        
        var vignetteAdj = comp.layers.addSolid([1, 1, 1], "Adjustment_Vignette", comp.width, comp.height, comp.pixelAspect, comp.duration);
        vignetteAdj.adjustmentLayer = true;
        
        try {
            var lensVignette = vignetteAdj.effects.addProperty("Lens Vignette");
            lensVignette.property(1).setValue(-20);
            lensVignette.property(2).setValue(0.6);
        } catch(e) {
            var circleMask = vignetteAdj.masks.addProperty("ADBE Mask Atom");
            circleMask.maskShape.setValue(
                Shape.newEllipse(comp.width/2, comp.height/2, comp.width*0.7, comp.height*0.7)
            );
            circleMask.inverted = true;
            circleMask.maskFeather.setValue([150, 150]);
            circleMask.maskOpacity.setValue(30);
        }
        
        var glowAdj = comp.layers.addSolid([0, 0, 0], "Adjustment_Glow", comp.width, comp.height, comp.pixelAspect, comp.duration);
        glowAdj.adjustmentLayer = true;
        glowAdj.blendingMode = BlendingMode.SCREEN;
        glowAdj.opacity.setValue(60);
        
        try {
            var glow = glowAdj.effects.addProperty("ADBE Glow 2");
            glow.property(2).setValue(70);
            glow.property(3).setValue(30);
            glow.property(4).setValue(2.0);
        } catch(e) {}
    }
    
    function createParticleLayers(comp) {
        var fgParticles = comp.layers.addSolid([0, 0, 0], "Particles_Foreground", comp.width, comp.height, comp.pixelAspect, comp.duration);
        fgParticles.threeDLayer = true;
        fgParticles.blendingMode = BlendingMode.SCREEN;
        fgParticles.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, -250]
        );
        fgParticles.property("ADBE Transform Group").property("ADBE Scale").setValue([130, 130, 130]);
        
        try {
            var ccParticle = fgParticles.effects.addProperty("CC Particle World");
            ccParticle.property("Birth Rate").setValue(15);
            ccParticle.property("Longevity (sec)").setValue(2.5);
            ccParticle.property("Position Z").setValue(-0.5);
            ccParticle.property("Radius X").setValue(1.5);
            ccParticle.property("Radius Y").setValue(1.5);
            ccParticle.property("Radius Z").setValue(0.3);
            ccParticle.property("Particle Type").setValue(8);
            ccParticle.property("Size").setValue(0.08);
            ccParticle.property("Max Opacity").setValue(80);
            ccParticle.property("Gravity").setValue(0.05);
            ccParticle.property("Wind X").setValue(0.3);
        } catch(e) {}
        
        var midParticles = comp.layers.addSolid([0, 0, 0], "Particles_Midground", comp.width, comp.height, comp.pixelAspect, comp.duration);
        midParticles.threeDLayer = true;
        midParticles.blendingMode = BlendingMode.SCREEN;
        midParticles.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, 100]
        );
        
        try {
            var ccParticle2 = midParticles.effects.addProperty("CC Particle World");
            ccParticle2.property("Birth Rate").setValue(50);
            ccParticle2.property("Longevity (sec)").setValue(3);
            ccParticle2.property("Particle Type").setValue(7);
            ccParticle2.property("Size").setValue(0.04);
            ccParticle2.property("Max Opacity").setValue(90);
            ccParticle2.property("Gravity").setValue(0.1);
        } catch(e) {}
        
        var bgParticles = comp.layers.addSolid([0, 0, 0], "Particles_Background", comp.width, comp.height, comp.pixelAspect, comp.duration);
        bgParticles.threeDLayer = true;
        bgParticles.blendingMode = BlendingMode.SCREEN;
        bgParticles.opacity.setValue(70);
        bgParticles.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, 350]
        );
        bgParticles.property("ADBE Transform Group").property("ADBE Scale").setValue([75, 75, 75]);
        
        try {
            var ccParticle3 = bgParticles.effects.addProperty("CC Particle World");
            ccParticle3.property("Birth Rate").setValue(100);
            ccParticle3.property("Longevity (sec)").setValue(5);
            ccParticle3.property("Particle Type").setValue(7);
            ccParticle3.property("Size").setValue(0.02);
            ccParticle3.property("Max Opacity").setValue(60);
            ccParticle3.property("Gravity").setValue(0.02);
        } catch(e) {}
    }
    
    function createBackgroundLayers(comp) {
        var bgSky = comp.layers.addSolid([0.15, 0.18, 0.25], "Background_Sky", comp.width, comp.height, comp.pixelAspect, comp.duration);
        bgSky.threeDLayer = true;
        bgSky.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, 400]
        );
        bgSky.property("ADBE Transform Group").property("ADBE Scale").setValue([72, 72, 72]);
        
        try {
            var fractalNoise = bgSky.effects.addProperty("Fractal Noise");
            fractalNoise.property("Fractal Type").setValue(4);
            fractalNoise.property("Noise Type").setValue(2);
            fractalNoise.property("Contrast").setValue(200);
            fractalNoise.property("Brightness").setValue(-30);
            fractalNoise.property("Scale").setValue(300);
            fractalNoise.property("Complexity").setValue(6);
        } catch(e) {}
        
        try {
            var fastBlur = bgSky.effects.addProperty("ADBE Fast Blur 2");
            fastBlur.property(1).setValue(10);
        } catch(e) {}
    }
    
    function createSubjectLayers(comp) {
        var midground = comp.layers.addSolid([0.2, 0.25, 0.3], "Midground_Element", comp.width, comp.height, comp.pixelAspect, comp.duration);
        midground.threeDLayer = true;
        midground.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, 150]
        );
        midground.property("ADBE Transform Group").property("ADBE Scale").setValue([88, 88, 88]);
        
        var labelText = addPlaceholderText(midground, "中景素材\n(建筑/景物)");
        
        var subject = comp.layers.addSolid([0.5, 0.5, 0.6], "Main_Subject", comp.width, comp.height, comp.pixelAspect, comp.duration);
        subject.threeDLayer = true;
        subject.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, 0]
        );
        
        try {
            var dropShadow = subject.effects.addProperty("ADBE Drop Shadow");
            dropShadow.property(1).setValue([0, 0, 0]);
            dropShadow.property(2).setValue(50);
            dropShadow.property(3).setValue(135);
            dropShadow.property(4).setValue(8);
            dropShadow.property(5).setValue(10);
        } catch(e) {}
        
        var labelText2 = addPlaceholderText(subject, "主体素材\n(人物/画面)");
    }
    
    function createForegroundLayers(comp) {
        var foreground = comp.layers.addSolid([0.3, 0.3, 0.35], "Foreground_Element", comp.width, comp.height, comp.pixelAspect, comp.duration);
        foreground.threeDLayer = true;
        foreground.property("ADBE Transform Group").property("ADBE Position").setValue(
            [comp.width/2, comp.height/2, -150]
        );
        foreground.property("ADBE Transform Group").property("ADBE Scale").setValue([120, 120, 120]);
        
        var labelText = addPlaceholderText(foreground, "前景素材\n(近景物体)");
    }
    
    function createNullControllers(comp) {
        var cameraRig = comp.layers.addNull(comp.duration);
        cameraRig.name = "Camera_Rig";
        cameraRig.threeDLayer = true;
        
        var controller = comp.layers.addNull(comp.duration);
        controller.name = "Global_Controller";
        controller.threeDLayer = false;
        
        try {
            var slider1 = controller.effects.addProperty("ADBE Slider Control");
            slider1.name = "Global Scale";
            slider1.property(1).setValue(100);
            
            var slider2 = controller.effects.addProperty("ADBE Slider Control");
            slider2.name = "DOF Amount";
            slider2.property(1).setValue(100);
            
            var slider3 = controller.effects.addProperty("ADBE Slider Control");
            slider3.name = "Particle Amount";
            slider3.property(1).setValue(100);
            
            var slider4 = controller.effects.addProperty("ADBE Slider Control");
            slider4.name = "Glow Intensity";
            slider4.property(1).setValue(100);
        } catch(e) {}
    }
    
    function addPlaceholderText(layer, text) {
        try {
            var textLayer = layer.source.layers.addText(text);
            return textLayer;
        } catch(e) {
            return null;
        }
    }
    
})();