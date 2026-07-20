(function() {
            app.beginUndoGroup("AE MCP Import");
            
            var results = {};
            
            try {
                var file = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/05-测试套件/test_resources/test_image.png");
                
                if (!file.exists) {
                    results.success = false;
                    results.error = "File not found at: " + "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/05-测试套件/test_resources/test_image.png";
                } else {
                    var importOptions = new ImportOptions(file);
                    var importedFootage = app.project.importFile(importOptions);
                    
                    results.success = true;
                    results.footageName = importedFootage.name;
                    results.footageId = importedFootage.id;
                    
                    
            // 查找或创建目标合成
            var targetComp = null;
            for (var i = 1; i <= app.project.items.length; i++) {
                var item = app.project.items[i];
                if (item.typeName === "Composition" && item.name === "Phase7_Test_Comp") {
                    targetComp = item;
                    break;
                }
            }
            
            if (!targetComp) {
                // 如果不存在，创建新合成
                targetComp = app.project.items.addComp("Phase7_Test_Comp", 1920, 1080, 1, 10, 30);
                targetComp.bgColor = [0, 0, 0];
            }
            
            // 添加到合成并居中
            var layer = targetComp.layers.add(importedFootage);
            layer.property("Position").setValue([targetComp.width / 2, targetComp.height / 2]);
        
                }
            } catch (e) {
                results.success = false;
                results.error = e.toString();
            }
            
            app.endUndoGroup();
            
            return results;
        })();