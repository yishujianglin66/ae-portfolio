# Adobe Media Encoder 批量渲染与格式输出指南

---

## 一、AME 架构与核心组件

### 1.1 对象模型层次

```javascript
// AME DOM 层次结构
// Application
//   └── Queue
//       └── Item
//           ├── Source
//           └── Output
//               └── Preset
```

### 1.2 核心对象

| 对象 | 描述 | 关键方法 |
|------|------|---------|
| **Application** | AME 应用程序 | addToQueue(), startQueue(), stopQueue() |
| **Queue** | 渲染队列 | items, progress, isRunning |
| **Item** | 队列项 | addOutput(), removeOutput(), status |
| **Source** | 源媒体 | filePath, duration, frameRate |
| **Output** | 输出配置 | preset, outputPath, status |
| **Preset** | 渲染预设 | name, format, codec |

### 1.3 JavaScript API 初始化

```javascript
var AME = {
    app: null,
    queue: null,
    
    init: function() {
        this.app = app;
        this.queue = this.app.queue;
        return true;
    },
    
    getQueueInfo: function() {
        if (!this.queue) return null;
        
        return {
            itemCount: this.queue.items.length,
            isRunning: this.queue.isRunning,
            progress: this.queue.progress,
            completedCount: this.queue.completedCount,
            failedCount: this.queue.failedCount
        };
    },
    
    getVersion: function() {
        return this.app.version;
    }
};
```

---

## 二、队列管理

### 2.1 队列项操作

```javascript
var QueueManager = {
    addItemToQueue: function(filePath) {
        try {
            var file = new File(filePath);
            var item = AME.app.addToQueue(file);
            return item;
        } catch (e) {
            $.writeln("添加到队列失败: " + e.message);
            return null;
        }
    },
    
    batchAddToQueue: function(filePaths) {
        var items = [];
        
        for (var i = 0; i < filePaths.length; i++) {
            var item = this.addItemToQueue(filePaths[i]);
            if (item) {
                items.push(item);
            }
        }
        
        return items;
    },
    
    addFolderToQueue: function(folderPath) {
        var folder = new Folder(folderPath);
        var files = folder.getFiles();
        var items = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            var validExts = ["mp4", "mov", "avi", "mkv", "prproj", "aep", "psd"];
            
            if (validExts.indexOf(ext) !== -1) {
                var item = this.addItemToQueue(file.fsName);
                if (item) {
                    items.push(item);
                }
            }
        }
        
        return items;
    },
    
    removeItemFromQueue: function(item) {
        try {
            item.remove();
            return true;
        } catch (e) {
            $.writeln("从队列移除失败: " + e.message);
            return false;
        }
    },
    
    clearQueue: function() {
        try {
            AME.app.queue.clear();
            return true;
        } catch (e) {
            $.writeln("清空队列失败: " + e.message);
            return false;
        }
    },
    
    reorderItems: function(items, newOrder) {
        try {
            for (var i = 0; i < newOrder.length; i++) {
                items[newOrder[i]].moveToPosition(i);
            }
            return true;
        } catch (e) {
            $.writeln("重排队列失败: " + e.message);
            return false;
        }
    },
    
    getItemInfo: function(item) {
        return {
            name: item.name,
            sourcePath: item.source.filePath,
            duration: item.source.duration,
            frameRate: item.source.frameRate,
            width: item.source.width,
            height: item.source.height,
            status: item.status.toString(),
            outputCount: item.outputs.length
        };
    },
    
    getAllItems: function() {
        return AME.app.queue.items;
    },
    
    getPendingItems: function() {
        var items = [];
        var allItems = AME.app.queue.items;
        
        for (var i = 0; i < allItems.length; i++) {
            if (allItems[i].status === QueueItemStatus.PENDING) {
                items.push(allItems[i]);
            }
        }
        
        return items;
    },
    
    getCompletedItems: function() {
        var items = [];
        var allItems = AME.app.queue.items;
        
        for (var i = 0; i < allItems.length; i++) {
            if (allItems[i].status === QueueItemStatus.COMPLETED) {
                items.push(allItems[i]);
            }
        }
        
        return items;
    },
    
    getFailedItems: function() {
        var items = [];
        var allItems = AME.app.queue.items;
        
        for (var i = 0; i < allItems.length; i++) {
            if (allItems[i].status === QueueItemStatus.FAILED) {
                items.push(allItems[i]);
            }
        }
        
        return items;
    }
};
```

### 2.2 队列控制

```javascript
var QueueController = {
    startQueue: function() {
        try {
            AME.app.queue.start();
            return true;
        } catch (e) {
            $.writeln("启动队列失败: " + e.message);
            return false;
        }
    },
    
    stopQueue: function() {
        try {
            AME.app.queue.stop();
            return true;
        } catch (e) {
            $.writeln("停止队列失败: " + e.message);
            return false;
        }
    },
    
    pauseQueue: function() {
        try {
            AME.app.queue.pause();
            return true;
        } catch (e) {
            $.writeln("暂停队列失败: " + e.message);
            return false;
        }
    },
    
    resumeQueue: function() {
        try {
            AME.app.queue.resume();
            return true;
        } catch (e) {
            $.writeln("恢复队列失败: " + e.message);
            return false;
        }
    },
    
    isQueueRunning: function() {
        return AME.app.queue.isRunning;
    },
    
    getQueueProgress: function() {
        return AME.app.queue.progress;
    },
    
    waitForCompletion: function(timeout) {
        var startTime = new Date().getTime();
        
        while (AME.app.queue.isRunning) {
            if (timeout && (new Date().getTime() - startTime) > timeout) {
                this.stopQueue();
                return false;
            }
            
            $.sleep(1000);
        }
        
        return true;
    },
    
    runSingleItem: function(item) {
        try {
            // 移除其他项
            var allItems = AME.app.queue.items;
            for (var i = 0; i < allItems.length; i++) {
                if (allItems[i] !== item) {
                    allItems[i].remove();
                }
            }
            
            AME.app.queue.start();
            return true;
        } catch (e) {
            $.writeln("运行单个项目失败: " + e.message);
            return false;
        }
    },
    
    runSelectedItems: function(items) {
        try {
            // 移除未选中项
            var allItems = AME.app.queue.items;
            for (var i = allItems.length - 1; i >= 0; i--) {
                if (items.indexOf(allItems[i]) === -1) {
                    allItems[i].remove();
                }
            }
            
            AME.app.queue.start();
            return true;
        } catch (e) {
            $.writeln("运行选中项目失败: " + e.message);
            return false;
        }
    }
};
```

---

## 三、输出配置

### 3.1 创建输出

```javascript
var OutputManager = {
    addOutput: function(item, preset, outputPath) {
        try {
            var output = item.addOutput();
            output.preset = preset;
            output.outputPath = outputPath;
            return output;
        } catch (e) {
            $.writeln("添加输出失败: " + e.message);
            return null;
        }
    },
    
    batchAddOutputs: function(items, preset, outputDir) {
        var outputs = [];
        
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var baseName = item.name.replace(/\.[^/.]+$/, "");
            var outputPath = outputDir + "/" + baseName + ".mp4";
            
            var output = this.addOutput(item, preset, outputPath);
            if (output) {
                outputs.push(output);
            }
        }
        
        return outputs;
    },
    
    setOutputPreset: function(output, preset) {
        try {
            output.preset = preset;
            return true;
        } catch (e) {
            $.writeln("设置输出预设失败: " + e.message);
            return false;
        }
    },
    
    setOutputPath: function(output, path) {
        try {
            output.outputPath = path;
            return true;
        } catch (e) {
            $.writeln("设置输出路径失败: " + e.message);
            return false;
        }
    },
    
    setOutputFormat: function(output, format) {
        try {
            output.format = format;
            return true;
        } catch (e) {
            $.writeln("设置输出格式失败: " + e.message);
            return false;
        }
    },
    
    setOutputCodec: function(output, codec) {
        try {
            output.codec = codec;
            return true;
        } catch (e) {
            $.writeln("设置输出编码失败: " + e.message);
            return false;
        }
    },
    
    setOutputResolution: function(output, width, height) {
        try {
            output.width = width;
            output.height = height;
            return true;
        } catch (e) {
            $.writeln("设置输出分辨率失败: " + e.message);
            return false;
        }
    },
    
    setOutputFrameRate: function(output, frameRate) {
        try {
            output.frameRate = frameRate;
            return true;
        } catch (e) {
            $.writeln("设置输出帧率失败: " + e.message);
            return false;
        }
    },
    
    setOutputBitrate: function(output, bitrate) {
        try {
            output.bitrate = bitrate;
            return true;
        } catch (e) {
            $.writeln("设置输出码率失败: " + e.message);
            return false;
        }
    },
    
    setAudioCodec: function(output, codec) {
        try {
            output.audioCodec = codec;
            return true;
        } catch (e) {
            $.writeln("设置音频编码失败: " + e.message);
            return false;
        }
    },
    
    setAudioBitrate: function(output, bitrate) {
        try {
            output.audioBitrate = bitrate;
            return true;
        } catch (e) {
            $.writeln("设置音频码率失败: " + e.message);
            return false;
        }
    },
    
    deleteOutput: function(output) {
        try {
            output.remove();
            return true;
        } catch (e) {
            $.writeln("删除输出失败: " + e.message);
            return false;
        }
    },
    
    getOutputInfo: function(output) {
        return {
            preset: output.preset.name,
            outputPath: output.outputPath,
            format: output.format.toString(),
            codec: output.codec.toString(),
            width: output.width,
            height: output.height,
            frameRate: output.frameRate,
            bitrate: output.bitrate,
            audioCodec: output.audioCodec.toString(),
            audioBitrate: output.audioBitrate,
            status: output.status.toString(),
            progress: output.progress
        };
    }
};
```

### 3.2 多格式输出

```javascript
var MultiFormatOutput = {
    createMultiFormatOutputs: function(item, configs, outputDir) {
        var outputs = [];
        
        for (var i = 0; i < configs.length; i++) {
            var config = configs[i];
            var baseName = item.name.replace(/\.[^/.]+$/, "");
            var ext = config.extension || "mp4";
            var suffix = config.suffix || "";
            var outputPath = outputDir + "/" + baseName + suffix + "." + ext;
            
            var output = item.addOutput();
            
            if (config.preset) {
                output.preset = config.preset;
            }
            
            if (config.format) {
                output.format = config.format;
            }
            
            if (config.codec) {
                output.codec = config.codec;
            }
            
            if (config.width && config.height) {
                output.width = config.width;
                output.height = config.height;
            }
            
            if (config.bitrate) {
                output.bitrate = config.bitrate;
            }
            
            output.outputPath = outputPath;
            outputs.push(output);
        }
        
        return outputs;
    },
    
    createWebOutputs: function(item, outputDir) {
        var configs = [
            {
                preset: this.getPresetByName("H.264 - High Bitrate"),
                suffix: "_1080p",
                extension: "mp4"
            },
            {
                preset: this.getPresetByName("H.264 - Medium Bitrate"),
                suffix: "_720p",
                extension: "mp4"
            },
            {
                preset: this.getPresetByName("WebM"),
                suffix: "_webm",
                extension: "webm"
            }
        ];
        
        return this.createMultiFormatOutputs(item, configs, outputDir);
    },
    
    createSocialOutputs: function(item, outputDir) {
        var configs = [
            {
                preset: this.getPresetByName("H.264 - Match Source - High Bitrate"),
                suffix: "_youtube",
                extension: "mp4"
            },
            {
                preset: this.getPresetByName("H.264 - Match Source - High Bitrate"),
                suffix: "_douyin",
                extension: "mp4"
            },
            {
                preset: this.getPresetByName("H.264 - Match Source - High Bitrate"),
                suffix: "_weibo",
                extension: "mp4"
            }
        ];
        
        return this.createMultiFormatOutputs(item, configs, outputDir);
    },
    
    createDeliveryOutputs: function(item, outputDir) {
        var configs = [
            {
                preset: this.getPresetByName("QuickTime - ProRes 4444"),
                suffix: "_master",
                extension: "mov"
            },
            {
                preset: this.getPresetByName("H.264 - High Bitrate"),
                suffix: "_preview",
                extension: "mp4"
            },
            {
                preset: this.getPresetByName("MPEG-2 DVD"),
                suffix: "_dvd",
                extension: "m2v"
            }
        ];
        
        return this.createMultiFormatOutputs(item, configs, outputDir);
    },
    
    getPresetByName: function(name) {
        var presets = AME.app.presets;
        
        for (var i = 0; i < presets.length; i++) {
            if (presets[i].name === name) {
                return presets[i];
            }
        }
        
        return null;
    }
};
```

---

## 四、预设管理

### 4.1 预设创建与编辑

```javascript
var PresetManager = {
    getPresets: function() {
        return AME.app.presets;
    },
    
    getPresetByName: function(name) {
        var presets = AME.app.presets;
        
        for (var i = 0; i < presets.length; i++) {
            if (presets[i].name === name) {
                return presets[i];
            }
        }
        
        return null;
    },
    
    getPresetsByFormat: function(format) {
        var presets = AME.app.presets;
        var filtered = [];
        
        for (var i = 0; i < presets.length; i++) {
            if (presets[i].format.toString() === format) {
                filtered.push(presets[i]);
            }
        }
        
        return filtered;
    },
    
    createPreset: function(config) {
        var defaults = {
            name: "Custom Preset",
            format: "H.264",
            codec: "H.264",
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 20000000,
            audioCodec: "AAC",
            audioBitrate: 256000,
            audioSampleRate: 48000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var preset = AME.app.presets.add(cfg.name);
            
            preset.format = cfg.format;
            preset.codec = cfg.codec;
            preset.width = cfg.width;
            preset.height = cfg.height;
            preset.frameRate = cfg.frameRate;
            preset.bitrate = cfg.bitrate;
            preset.audioCodec = cfg.audioCodec;
            preset.audioBitrate = cfg.audioBitrate;
            preset.audioSampleRate = cfg.audioSampleRate;
            
            return preset;
        } catch (e) {
            $.writeln("创建预设失败: " + e.message);
            return null;
        }
    },
    
    duplicatePreset: function(preset, newName) {
        try {
            var duplicated = preset.duplicate();
            duplicated.name = newName;
            return duplicated;
        } catch (e) {
            $.writeln("复制预设失败: " + e.message);
            return null;
        }
    },
    
    deletePreset: function(preset) {
        try {
            preset.remove();
            return true;
        } catch (e) {
            $.writeln("删除预设失败: " + e.message);
            return false;
        }
    },
    
    exportPreset: function(preset, outputPath) {
        try {
            var file = new File(outputPath);
            preset.export(file);
            return true;
        } catch (e) {
            $.writeln("导出预设失败: " + e.message);
            return false;
        }
    },
    
    importPreset: function(inputPath) {
        try {
            var file = new File(inputPath);
            return AME.app.presets.import(file);
        } catch (e) {
            $.writeln("导入预设失败: " + e.message);
            return null;
        }
    },
    
    savePresetCollection: function(presets, outputPath) {
        try {
            var file = new File(outputPath);
            
            var collection = {
                version: AME.app.version,
                presets: []
            };
            
            for (var i = 0; i < presets.length; i++) {
                collection.presets.push({
                    name: presets[i].name,
                    format: presets[i].format.toString(),
                    codec: presets[i].codec.toString(),
                    width: presets[i].width,
                    height: presets[i].height,
                    frameRate: presets[i].frameRate,
                    bitrate: presets[i].bitrate,
                    audioCodec: presets[i].audioCodec.toString(),
                    audioBitrate: presets[i].audioBitrate
                });
            }
            
            var f = new File(outputPath);
            f.open("w");
            f.write(JSON.stringify(collection, null, 2));
            f.close();
            
            return true;
        } catch (e) {
            $.writeln("保存预设集合失败: " + e.message);
            return false;
        }
    },
    
    getPresetInfo: function(preset) {
        return {
            name: preset.name,
            format: preset.format.toString(),
            codec: preset.codec.toString(),
            width: preset.width,
            height: preset.height,
            frameRate: preset.frameRate,
            bitrate: preset.bitrate,
            audioCodec: preset.audioCodec.toString(),
            audioBitrate: preset.audioBitrate,
            audioSampleRate: preset.audioSampleRate,
            fileSize: preset.fileSize
        };
    }
};
```

### 4.2 预设配置模板

```javascript
var PresetTemplates = {
    createH264Preset: function(name, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 20000000,
            profile: "High",
            level: "4.2",
            audioCodec: "AAC",
            audioBitrate: 256000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return PresetManager.createPreset({
            name: name,
            format: "H.264",
            codec: "H.264",
            width: cfg.width,
            height: cfg.height,
            frameRate: cfg.frameRate,
            bitrate: cfg.bitrate,
            audioCodec: cfg.audioCodec,
            audioBitrate: cfg.audioBitrate
        });
    },
    
    createProResPreset: function(name, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            codec: "ProRes 422 HQ",
            audioCodec: "PCM",
            audioBitrate: 1536000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return PresetManager.createPreset({
            name: name,
            format: "QuickTime",
            codec: cfg.codec,
            width: cfg.width,
            height: cfg.height,
            frameRate: cfg.frameRate,
            audioCodec: cfg.audioCodec,
            audioBitrate: cfg.audioBitrate
        });
    },
    
    createWebMPreset: function(name, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 10000000,
            audioCodec: "Vorbis",
            audioBitrate: 128000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return PresetManager.createPreset({
            name: name,
            format: "WebM",
            codec: "VP8",
            width: cfg.width,
            height: cfg.height,
            frameRate: cfg.frameRate,
            bitrate: cfg.bitrate,
            audioCodec: cfg.audioCodec,
            audioBitrate: cfg.audioBitrate
        });
    },
    
    createDNxHDPreset: function(name, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            codec: "DNxHD 185",
            audioCodec: "PCM",
            audioBitrate: 1536000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return PresetManager.createPreset({
            name: name,
            format: "MXF OP1a",
            codec: cfg.codec,
            width: cfg.width,
            height: cfg.height,
            frameRate: cfg.frameRate,
            audioCodec: cfg.audioCodec,
            audioBitrate: cfg.audioBitrate
        });
    },
    
    createGIFPreset: function(name, config) {
        var defaults = {
            width: 480,
            height: 270,
            frameRate: 10,
            quality: 80
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        return PresetManager.createPreset({
            name: name,
            format: "GIF",
            codec: "GIF",
            width: cfg.width,
            height: cfg.height,
            frameRate: cfg.frameRate
        });
    },
    
    createYouTubePreset: function() {
        return this.createH264Preset("YouTube - 4K", {
            width: 3840,
            height: 2160,
            frameRate: 24,
            bitrate: 45000000,
            audioBitrate: 384000
        });
    },
    
    createYouTube1080pPreset: function() {
        return this.createH264Preset("YouTube - 1080p", {
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 20000000,
            audioBitrate: 256000
        });
    },
    
    createDouyinPreset: function() {
        return this.createH264Preset("Douyin", {
            width: 1080,
            height: 1920,
            frameRate: 30,
            bitrate: 15000000,
            audioBitrate: 256000
        });
    },
    
    createWeChatPreset: function() {
        return this.createH264Preset("WeChat", {
            width: 1080,
            height: 1080,
            frameRate: 24,
            bitrate: 8000000,
            audioBitrate: 128000
        });
    },
    
    createMasterPreset: function() {
        return this.createProResPreset("Master - ProRes 4444", {
            width: 3840,
            height: 2160,
            frameRate: 24,
            codec: "ProRes 4444 XQ",
            audioBitrate: 3072000
        });
    },
    
    createProxyPreset: function() {
        return this.createH264Preset("Proxy - 1080p", {
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 5000000,
            audioBitrate: 128000
        });
    }
};
```

---

## 五、批量处理

### 5.1 批量渲染

```javascript
var BatchRenderer = {
    renderFolder: function(inputFolder, outputFolder, preset) {
        var folder = new Folder(inputFolder);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            var validExts = ["mp4", "mov", "avi", "mkv", "wmv", "flv"];
            
            if (validExts.indexOf(ext) === -1) {
                continue;
            }
            
            try {
                // 添加到队列
                var item = AME.app.addToQueue(file);
                
                // 添加输出
                var baseName = file.name.replace(/\.[^/.]+$/, "");
                var outputPath = outputFolder + "/" + baseName + ".mp4";
                
                var output = item.addOutput();
                output.preset = preset;
                output.outputPath = outputPath;
                
                results.push({
                    filename: file.name,
                    success: true,
                    outputPath: outputPath
                });
                
            } catch (e) {
                results.push({
                    filename: file.name,
                    success: false,
                    error: e.message
                });
            }
        }
        
        return results;
    },
    
    renderWithMultiFormats: function(inputFolder, outputFolder, presets) {
        var folder = new Folder(inputFolder);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            if (ext !== "mp4" && ext !== "mov") continue;
            
            try {
                var item = AME.app.addToQueue(file);
                var baseName = file.name.replace(/\.[^/.]+$/, "");
                
                var itemResults = [];
                
                for (var j = 0; j < presets.length; j++) {
                    var preset = presets[j];
                    var suffix = preset.suffix || "_" + j;
                    var extOut = preset.extension || "mp4";
                    var outputPath = outputFolder + "/" + baseName + suffix + "." + extOut;
                    
                    var output = item.addOutput();
                    output.preset = preset.preset;
                    output.outputPath = outputPath;
                    
                    itemResults.push({
                        format: preset.name,
                        outputPath: outputPath,
                        success: true
                    });
                }
                
                results.push({
                    filename: file.name,
                    outputs: itemResults
                });
                
            } catch (e) {
                results.push({
                    filename: file.name,
                    success: false,
                    error: e.message
                });
            }
        }
        
        return results;
    },
    
    renderProjectFiles: function(folderPath, outputFolder, preset) {
        var folder = new Folder(folderPath);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            
            if (ext !== "prproj" && ext !== "aep") {
                continue;
            }
            
            try {
                var item = AME.app.addToQueue(file);
                
                var baseName = file.name.replace(/\.[^/.]+$/, "");
                var outputPath = outputFolder + "/" + baseName + ".mp4";
                
                var output = item.addOutput();
                output.preset = preset;
                output.outputPath = outputPath;
                
                results.push({
                    filename: file.name,
                    success: true,
                    outputPath: outputPath
                });
                
            } catch (e) {
                results.push({
                    filename: file.name,
                    success: false,
                    error: e.message
                });
            }
        }
        
        return results;
    },
    
    runAndWait: function(timeout) {
        AME.app.queue.start();
        
        var startTime = new Date().getTime();
        
        while (AME.app.queue.isRunning) {
            if (timeout && (new Date().getTime() - startTime) > timeout) {
                AME.app.queue.stop();
                return { success: false, error: "Timeout" };
            }
            
            $.sleep(2000);
            
            var progress = AME.app.queue.progress;
            $.writeln("Progress: " + Math.round(progress * 100) + "%");
        }
        
        return {
            success: true,
            completedCount: AME.app.queue.completedCount,
            failedCount: AME.app.queue.failedCount
        };
    }
};
```

### 5.2 自动化工作流

```javascript
var AutoWorkflow = {
    automateRender: function(config) {
        var defaults = {
            inputFolder: "",
            outputFolder: "",
            presets: [],
            deleteSourceAfterRender: false,
            moveCompletedToArchive: false,
            archiveFolder: "",
            notifyOnComplete: false,
            timeout: 3600000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        // 验证输入
        if (!cfg.inputFolder || !cfg.outputFolder) {
            return { success: false, error: "输入输出文件夹不能为空" };
        }
        
        // 创建输出文件夹
        var outFolder = new Folder(cfg.outputFolder);
        if (!outFolder.exists) {
            outFolder.create();
        }
        
        // 添加文件到队列
        var folder = new Folder(cfg.inputFolder);
        var files = folder.getFiles();
        var items = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            if (ext !== "mp4" && ext !== "mov") continue;
            
            try {
                var item = AME.app.addToQueue(file);
                var baseName = file.name.replace(/\.[^/.]+$/, "");
                
                for (var j = 0; j < cfg.presets.length; j++) {
                    var preset = cfg.presets[j];
                    var outputPath = cfg.outputFolder + "/" + baseName + preset.suffix + "." + preset.extension;
                    
                    var output = item.addOutput();
                    output.preset = preset.preset;
                    output.outputPath = outputPath;
                }
                
                items.push(item);
                
            } catch (e) {
                $.writeln("添加文件失败: " + file.name + " - " + e.message);
            }
        }
        
        if (items.length === 0) {
            return { success: false, error: "没有找到可处理的文件" };
        }
        
        // 开始渲染
        $.writeln("开始渲染 " + items.length + " 个项目...");
        AME.app.queue.start();
        
        // 等待完成
        var startTime = new Date().getTime();
        
        while (AME.app.queue.isRunning) {
            if (cfg.timeout && (new Date().getTime() - startTime) > cfg.timeout) {
                AME.app.queue.stop();
                return { success: false, error: "渲染超时" };
            }
            
            $.sleep(3000);
            
            var progress = AME.app.queue.progress;
            $.writeln("渲染进度: " + Math.round(progress * 100) + "%");
        }
        
        // 后续处理
        if (cfg.moveCompletedToArchive && cfg.archiveFolder) {
            var archiveFolder = new Folder(cfg.archiveFolder);
            if (!archiveFolder.exists) {
                archiveFolder.create();
            }
            
            for (var k = 0; k < items.length; k++) {
                if (items[k].status === QueueItemStatus.COMPLETED) {
                    var sourceFile = new File(items[k].source.filePath);
                    sourceFile.move(archiveFolder);
                }
            }
        }
        
        if (cfg.deleteSourceAfterRender) {
            for (var l = 0; l < items.length; l++) {
                if (items[l].status === QueueItemStatus.COMPLETED) {
                    var sourceFile = new File(items[l].source.filePath);
                    sourceFile.remove();
                }
            }
        }
        
        $.writeln("渲染完成!");
        $.writeln("成功: " + AME.app.queue.completedCount);
        $.writeln("失败: " + AME.app.queue.failedCount);
        
        return {
            success: true,
            totalCount: items.length,
            completedCount: AME.app.queue.completedCount,
            failedCount: AME.app.queue.failedCount
        };
    },
    
    scheduleRender: function(config) {
        $.writeln("调度渲染任务:");
        $.writeln("  输入文件夹: " + config.inputFolder);
        $.writeln("  输出文件夹: " + config.outputFolder);
        $.writeln("  预设数量: " + config.presets.length);
        
        return {
            success: true,
            message: "任务已调度"
        };
    }
};
```

---

## 六、格式转换

### 6.1 格式转换工具

```javascript
var FormatConverter = {
    convertToMP4: function(inputPath, outputPath, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 20000000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var item = AME.app.addToQueue(new File(inputPath));
            
            var output = item.addOutput();
            output.format = "H.264";
            output.codec = "H.264";
            output.width = cfg.width;
            output.height = cfg.height;
            output.frameRate = cfg.frameRate;
            output.bitrate = cfg.bitrate;
            output.audioCodec = "AAC";
            output.audioBitrate = 256000;
            output.outputPath = outputPath;
            
            AME.app.queue.start();
            
            while (AME.app.queue.isRunning) {
                $.sleep(1000);
            }
            
            return true;
        } catch (e) {
            $.writeln("转换为MP4失败: " + e.message);
            return false;
        }
    },
    
    convertToMOV: function(inputPath, outputPath, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            codec: "ProRes 422 HQ"
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var item = AME.app.addToQueue(new File(inputPath));
            
            var output = item.addOutput();
            output.format = "QuickTime";
            output.codec = cfg.codec;
            output.width = cfg.width;
            output.height = cfg.height;
            output.frameRate = cfg.frameRate;
            output.audioCodec = "PCM";
            output.audioBitrate = 1536000;
            output.outputPath = outputPath;
            
            AME.app.queue.start();
            
            while (AME.app.queue.isRunning) {
                $.sleep(1000);
            }
            
            return true;
        } catch (e) {
            $.writeln("转换为MOV失败: " + e.message);
            return false;
        }
    },
    
    convertToWebM: function(inputPath, outputPath, config) {
        var defaults = {
            width: 1920,
            height: 1080,
            frameRate: 24,
            bitrate: 10000000
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var item = AME.app.addToQueue(new File(inputPath));
            
            var output = item.addOutput();
            output.format = "WebM";
            output.codec = "VP8";
            output.width = cfg.width;
            output.height = cfg.height;
            output.frameRate = cfg.frameRate;
            output.bitrate = cfg.bitrate;
            output.audioCodec = "Vorbis";
            output.audioBitrate = 128000;
            output.outputPath = outputPath;
            
            AME.app.queue.start();
            
            while (AME.app.queue.isRunning) {
                $.sleep(1000);
            }
            
            return true;
        } catch (e) {
            $.writeln("转换为WebM失败: " + e.message);
            return false;
        }
    },
    
    convertToGIF: function(inputPath, outputPath, config) {
        var defaults = {
            width: 480,
            height: 270,
            frameRate: 10
        };
        
        var cfg = Object.assign({}, defaults, config);
        
        try {
            var item = AME.app.addToQueue(new File(inputPath));
            
            var output = item.addOutput();
            output.format = "GIF";
            output.codec = "GIF";
            output.width = cfg.width;
            output.height = cfg.height;
            output.frameRate = cfg.frameRate;
            output.outputPath = outputPath;
            
            AME.app.queue.start();
            
            while (AME.app.queue.isRunning) {
                $.sleep(1000);
            }
            
            return true;
        } catch (e) {
            $.writeln("转换为GIF失败: " + e.message);
            return false;
        }
    },
    
    batchConvert: function(inputFolder, outputFolder, format, config) {
        var folder = new Folder(inputFolder);
        var files = folder.getFiles();
        var results = [];
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            
            if (!(file instanceof File)) continue;
            
            var ext = file.name.split(".").pop().toLowerCase();
            if (ext !== "mp4" && ext !== "mov" && ext !== "avi") continue;
            
            var baseName = file.name.replace(/\.[^/.]+$/, "");
            var outputPath = outputFolder + "/" + baseName + "." + format.toLowerCase();
            
            var success = false;
            
            switch (format) {
                case "MP4":
                    success = this.convertToMP4(file.fsName, outputPath, config);
                    break;
                case "MOV":
                    success = this.convertToMOV(file.fsName, outputPath, config);
                    break;
                case "WebM":
                    success = this.convertToWebM(file.fsName, outputPath, config);
                    break;
                case "GIF":
                    success = this.convertToGIF(file.fsName, outputPath, config);
                    break;
            }
            
            results.push({
                filename: file.name,
                outputPath: outputPath,
                success: success
            });
        }
        
        return results;
    }
};
```

---

## 七、与其他 Adobe 应用集成

### 7.1 动态链接

```javascript
var DynamicLinkManager = {
    importFromPremiere: function(prprojPath, sequenceName) {
        try {
            var file = new File(prprojPath);
            var item = AME.app.addToQueue(file);
            
            if (sequenceName) {
                // 选择特定序列
                for (var i = 0; i < item.source.sequences.length; i++) {
                    if (item.source.sequences[i].name === sequenceName) {
                        item.source.selectedSequence = item.source.sequences[i];
                        break;
                    }
                }
            }
            
            return item;
        } catch (e) {
            $.writeln("从Premiere导入失败: " + e.message);
            return null;
        }
    },
    
    importFromAE: function(aepPath, compName) {
        try {
            var file = new File(aepPath);
            var item = AME.app.addToQueue(file);
            
            if (compName) {
                for (var i = 0; i < item.source.comps.length; i++) {
                    if (item.source.comps[i].name === compName) {
                        item.source.selectedComp = item.source.comps[i];
                        break;
                    }
                }
            }
            
            return item;
        } catch (e) {
            $.writeln("从AE导入失败: " + e.message);
            return null;
        }
    },
    
    importFromPhotoshop: function(psdPath) {
        try {
            var file = new File(psdPath);
            var item = AME.app.addToQueue(file);
            return item;
        } catch (e) {
            $.writeln("从Photoshop导入失败: " + e.message);
            return null;
        }
    },
    
    sendToPremiere: function(outputPath) {
        try {
            var prApp = new Application("Adobe Premiere Pro");
            prApp.activate();
            
            var file = new File(outputPath);
            prApp.project.importFiles([file]);
            
            return true;
        } catch (e) {
            $.writeln("发送到Premiere失败: " + e.message);
            return false;
        }
    },
    
    sendToAE: function(outputPath) {
        try {
            var aeApp = new Application("Adobe After Effects");
            aeApp.activate();
            
            var file = new File(outputPath);
            aeApp.project.importFile(ImportAsType.FOOTAGE, file);
            
            return true;
        } catch (e) {
            $.writeln("发送到AE失败: " + e.message);
            return false;
        }
    },
    
    sendToMediaBrowser: function(outputPath) {
        try {
            var file = new File(outputPath);
            
            var prApp = new Application("Adobe Premiere Pro");
            prApp.project.importFiles([file]);
            
            var aeApp = new Application("Adobe After Effects");
            aeApp.project.importFile(ImportAsType.FOOTAGE, file);
            
            return true;
        } catch (e) {
            $.writeln("发送到媒体浏览器失败: " + e.message);
            return false;
        }
    }
};
```

### 7.2 项目交换

```javascript
var ProjectExchange = {
    exportProjectQueue: function(outputPath) {
        try {
            var queueData = {
                version: AME.app.version,
                items: []
            };
            
            var items = AME.app.queue.items;
            
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                
                var itemData = {
                    sourcePath: item.source.filePath,
                    name: item.name,
                    outputs: []
                };
                
                for (var j = 0; j < item.outputs.length; j++) {
                    var output = item.outputs[j];
                    
                    itemData.outputs.push({
                        presetName: output.preset.name,
                        outputPath: output.outputPath,
                        format: output.format.toString(),
                        codec: output.codec.toString(),
                        width: output.width,
                        height: output.height,
                        frameRate: output.frameRate
                    });
                }
                
                queueData.items.push(itemData);
            }
            
            var file = new File(outputPath);
            file.open("w");
            file.write(JSON.stringify(queueData, null, 2));
            file.close();
            
            return true;
        } catch (e) {
            $.writeln("导出队列失败: " + e.message);
            return false;
        }
    },
    
    importProjectQueue: function(inputPath) {
        try {
            var file = new File(inputPath);
            file.open("r");
            var queueData = JSON.parse(file.read());
            file.close();
            
            for (var i = 0; i < queueData.items.length; i++) {
                var itemData = queueData.items[i];
                
                var item = AME.app.addToQueue(new File(itemData.sourcePath));
                
                for (var j = 0; j < itemData.outputs.length; j++) {
                    var outputData = itemData.outputs[j];
                    
                    var preset = PresetManager.getPresetByName(outputData.presetName);
                    
                    var output = item.addOutput();
                    output.preset = preset;
                    output.outputPath = outputData.outputPath;
                }
            }
            
            return true;
        } catch (e) {
            $.writeln("导入队列失败: " + e.message);
            return false;
        }
    }
};
```

---

## 八、企业级部署

### 8.1 环境配置

```javascript
var AMEEnvironment = {
    getSystemInfo: function() {
        return {
            version: AME.app.version,
            platform: AME.app.platform,
            ram: AME.app.systemInfo.ram,
            gpu: AME.app.systemInfo.gpu,
            diskSpace: AME.app.systemInfo.diskSpace
        };
    },
    
    setOutputFolder: function(folderPath) {
        try {
            AME.app.preferences.setPref("General", "DefaultOutputFolder", folderPath);
            return true;
        } catch (e) {
            $.writeln("设置默认输出文件夹失败: " + e.message);
            return false;
        }
    },
    
    setTempFolder: function(folderPath) {
        try {
            AME.app.preferences.setPref("General", "TempFolder", folderPath);
            return true;
        } catch (e) {
            $.writeln("设置临时文件夹失败: " + e.message);
            return false;
        }
    },
    
    setMaxConcurrentRender: function(max) {
        try {
            AME.app.preferences.setPref("General", "MaxConcurrentRender", max);
            return true;
        } catch (e) {
            $.writeln("设置最大并发渲染数失败: " + e.message);
            return false;
        }
    },
    
    setUseGPU: function(enable) {
        try {
            AME.app.preferences.setPref("General", "UseGPU", enable);
            return true;
        } catch (e) {
            $.writeln("设置GPU加速失败: " + e.message);
            return false;
        }
    },
    
    exportPreferences: function(outputPath) {
        try {
            AME.app.preferences.exportPreferences(File(outputPath));
            return true;
        } catch (e) {
            $.writeln("导出首选项失败: " + e.message);
            return false;
        }
    },
    
    importPreferences: function(inputPath) {
        try {
            AME.app.preferences.importPreferences(File(inputPath));
            return true;
        } catch (e) {
            $.writeln("导入首选项失败: " + e.message);
            return false;
        }
    }
};
```

### 8.2 脚本部署

```javascript
var ScriptDeployer = {
    installScript: function(scriptPath, menuName) {
        try {
            var scriptFile = new File(scriptPath);
            AME.app.scriptMenu.installScript(scriptFile, menuName);
            return true;
        } catch (e) {
            $.writeln("安装脚本失败: " + e.message);
            return false;
        }
    },
    
    uninstallScript: function(menuName) {
        try {
            AME.app.scriptMenu.uninstallScript(menuName);
            return true;
        } catch (e) {
            $.writeln("卸载脚本失败: " + e.message);
            return false;
        }
    },
    
    getInstalledScripts: function() {
        try {
            return AME.app.scriptMenu.getScripts();
        } catch (e) {
            $.writeln("获取脚本列表失败: " + e.message);
            return [];
        }
    },
    
    runScript: function(scriptPath) {
        try {
            var scriptFile = new File(scriptPath);
            AME.app.doScript(scriptFile);
            return true;
        } catch (e) {
            $.writeln("运行脚本失败: " + e.message);
            return false;
        }
    }
};
```

---

## 九、性能优化

### 9.1 缓存管理

```javascript
var CacheManager = {
    clearCache: function() {
        try {
            AME.app.clearCache();
            return true;
        } catch (e) {
            $.writeln("清除缓存失败: " + e.message);
            return false;
        }
    },
    
    setCacheSize: function(maxSizeMB) {
        try {
            AME.app.preferences.setPref("General", "MaxCacheSize", maxSizeMB);
            return true;
        } catch (e) {
            $.writeln("设置缓存大小失败: " + e.message);
            return false;
        }
    },
    
    clearCompletedItems: function() {
        try {
            var items = AME.app.queue.items;
            
            for (var i = items.length - 1; i >= 0; i--) {
                if (items[i].status === QueueItemStatus.COMPLETED) {
                    items[i].remove();
                }
            }
            
            return true;
        } catch (e) {
            $.writeln("清除已完成项失败: " + e.message);
            return false;
        }
    },
    
    clearFailedItems: function() {
        try {
            var items = AME.app.queue.items;
            
            for (var i = items.length - 1; i >= 0; i--) {
                if (items[i].status === QueueItemStatus.FAILED) {
                    items[i].remove();
                }
            }
            
            return true;
        } catch (e) {
            $.writeln("清除失败项失败: " + e.message);
            return false;
        }
    }
};
```

### 9.2 性能监控

```javascript
var PerformanceMonitor = {
    getPerformanceMetrics: function() {
        return {
            queueProgress: AME.app.queue.progress,
            isRunning: AME.app.queue.isRunning,
            completedCount: AME.app.queue.completedCount,
            failedCount: AME.app.queue.failedCount,
            activeRenderCount: AME.app.queue.activeRenderCount,
            memoryUsage: AME.app.systemInfo.memoryUsage,
            gpuUsage: AME.app.systemInfo.gpuUsage
        };
    },
    
    getPerformanceReport: function() {
        var metrics = this.getPerformanceMetrics();
        var recommendations = [];
        
        if (metrics.memoryUsage > 85) {
            recommendations.push("内存使用率过高，建议关闭其他应用");
        }
        
        if (metrics.gpuUsage > 90) {
            recommendations.push("GPU使用率过高，建议降低渲染质量");
        }
        
        return {
            metrics: metrics,
            recommendations: recommendations
        };
    },
    
    monitorRendering: function(callback) {
        var interval = setInterval(function() {
            if (!AME.app.queue.isRunning) {
                clearInterval(interval);
                callback({
                    completed: AME.app.queue.completedCount,
                    failed: AME.app.queue.failedCount
                });
                return;
            }
            
            callback({
                progress: AME.app.queue.progress,
                completed: AME.app.queue.completedCount,
                failed: AME.app.queue.failedCount,
                isRunning: true
            });
        }, 2000);
        
        return interval;
    }
};
```

---

*本指南涵盖 Adobe Media Encoder 企业级集成的完整知识体系，包括队列管理、输出配置、预设管理、批量渲染、格式转换、动态链接、性能优化等核心模块*
