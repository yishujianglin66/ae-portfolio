// ============================================================
// 《冰海战记》V14_safe 极简测试版
// 简化功能，确保能在 AE 2026 中正常运行
// ============================================================

var COMP_NAME = "VinlandSaga_Test";
var OUTPUT_PATH = "D:/AE-Work/output/";
var OUTPUT_FILE = "VinlandSaga_Test.mp4";
var AUTO_RENDER = true;

var CLIP_PATH = "D:/AE-Work/视频素材库/冰海战记新素材/";
var AUDIO_PATH = "D:/AE-Work/音频素材库/BGM/";
var DURATION = 23.15;
var WIDTH = 1080;
var HEIGHT = 1920;
var FRAME_RATE = 30;

var SOURCES = {
    "FIGHT_S2":  "vinland_3_【授权转载】冰海战记第二季最精彩的打戏 托尔芬VS蛇.f30077.mp4",
    "MAD_REV":   "vinland_5_【MAD⧸冰海战记】There's a revolution coming!.f30080.mp4"
};

function main() {
    try {
        // 创建合成
        var comp = app.project.items.addComposition(
            COMP_NAME, WIDTH, HEIGHT, 1, DURATION, FRAME_RATE
        );
        
        // 导入音频
        try {
            var audioFile = new File(AUDIO_PATH + "ae实战音乐.mp3");
            if (audioFile.exists) {
                var audioItem = app.project.importFile(new ImportOptions(audioFile));
                var audioLayer = comp.layers.add(audioItem);
                audioLayer.startTime = 0;
                app.project.activeItem = comp;
            }
        } catch(e) {}
        
        // 添加视频层
        var clips = [
            {src: "FIGHT_S2", start: 0, dur: 11.5},
            {src: "MAD_REV", start: 11.5, dur: 11.65}
        ];
        
        for (var i = 0; i < clips.length; i++) {
            var clip = clips[i];
            try {
                var filePath = new File(CLIP_PATH + SOURCES[clip.src]);
                if (!filePath.exists) continue;
                
                var footageItem = app.project.importFile(new ImportOptions(filePath));
                var layer = comp.layers.add(footageItem);
                layer.startTime = clip.start;
                layer.inPoint = clip.start;
                layer.outPoint = clip.start + clip.dur;
                
                // 横转竖
                layer.scale.setValue([56.25, 56.25, 100]);
                layer.position.setValue([WIDTH/2, HEIGHT/2]);
                
                // 添加背景层
                var bgLayer = comp.layers.add(footageItem);
                bgLayer.name = clip.src + "_BG";
                bgLayer.startTime = clip.start;
                bgLayer.inPoint = clip.start;
                bgLayer.outPoint = clip.start + clip.dur;
                bgLayer.scale.setValue([220, 220, 100]);
                
                var blur = bgLayer.property("Effects").addProperty("ADBE Fast Blur");
                blur.property("Blurriness").setValue(25);
                blur.property("Repeat Edge Pixels").setValue(true);
                bgLayer.opacity.setValue(40);
                
                bgLayer.moveToEnd();
            } catch(e) {}
        }
        
        // 添加调色
        try {
            var grade = comp.layers.addSolid([1,1,1], "GRADE", WIDTH, HEIGHT, 1);
            grade.adjustmentLayer = true;
            grade.startTime = 0;
            
            var cb = grade.property("Effects").addProperty("ADBE Color Balance");
            cb.property("Shadow Red Balance").setValue(-10);
            cb.property("Shadow Blue Balance").setValue(15);
            cb.property("Highlight Red Balance").setValue(15);
            cb.property("Highlight Blue Balance").setValue(-10);
            grade.opacity.setValue(60);
        } catch(e) {}
        
        // 添加文字
        try {
            var textLayer = comp.layers.addText("VINLAND SAGA");
            textLayer.startTime = 0;
            textLayer.outPoint = DURATION;
            textLayer.position.setValue([WIDTH/2, HEIGHT * 0.15]);
            
            var txtProp = textLayer.property("Source Text");
            var txtDoc = txtProp.value;
            txtDoc.font = "Arial Black";
            txtDoc.fontSize = 70;
            txtDoc.fillColor = [1, 1, 1];
            txtProp.setValue(txtDoc);
            
            textLayer.opacity.setValueAtTime(0, 0);
            textLayer.opacity.setValueAtTime(1, 100);
            textLayer.opacity.setValueAtTime(DURATION - 2, 100);
            textLayer.opacity.setValueAtTime(DURATION, 0);
        } catch(e) {}
        
        // 自动渲染
        if (AUTO_RENDER) {
            try {
                var outputFolder = new Folder(OUTPUT_PATH);
                if (!outputFolder.exists) outputFolder.create();
                
                var outputFile = new File(OUTPUT_PATH + OUTPUT_FILE);
                var renderQueue = app.project.renderQueue;
                var renderItem = renderQueue.items.add(comp);
                
                renderItem.timeSpanStart = 0;
                renderItem.timeSpanDuration = DURATION;
                
                var om = renderItem.outputModule(1);
                om.file = outputFile;
                
                try {
                    om.applyTemplate("H.264");
                } catch(e) {}
                
                renderQueue.render();
                alert("渲染开始!\\n输出: " + OUTPUT_FILE);
            } catch(e) {
                alert("渲染失败: " + e.message);
            }
        }
        
        return "SUCCESS: 合成已创建";
    } catch(e) {
        alert("错误: " + e.message);
        return "ERROR: " + e.message;
    }
}

main();
