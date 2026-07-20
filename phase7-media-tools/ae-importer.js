/**
 * Phase7 - AE 导入工具
 * 
 * 使用 executeAtomScript 方法，确保可靠导入
 */

const PathUtils = require('./path-utils');

class AEImporter {
    
    /**
     * 生成导入素材的 ExtendScript 代码
     * @param {string} safePath - ExtendScript 安全的路径（正斜杠）
     * @param {string} compName - 目标合成名称（可选）
     * @returns {string} ExtendScript 代码
     */
    static generateImportScript(safePath, compName = null) {
        const compPart = compName ? `
            // 查找或创建目标合成
            var targetComp = null;
            for (var i = 1; i <= app.project.items.length; i++) {
                var item = app.project.items[i];
                if (item.typeName === "Composition" && item.name === "${compName}") {
                    targetComp = item;
                    break;
                }
            }
            
            if (!targetComp) {
                // 如果不存在，创建新合成
                targetComp = app.project.items.addComp("${compName}", 1920, 1080, 1, 10, 30);
                targetComp.bgColor = [0, 0, 0];
            }
            
            // 添加到合成并居中
            var layer = targetComp.layers.add(importedFootage);
            layer.property("Position").setValue([targetComp.width / 2, targetComp.height / 2]);
        ` : '';
        
        return `(function() {
            app.beginUndoGroup("AE MCP Import");
            
            var results = {};
            
            try {
                var file = new File("${safePath}");
                
                if (!file.exists) {
                    results.success = false;
                    results.error = "File not found at: " + "${safePath}";
                } else {
                    var importOptions = new ImportOptions(file);
                    var importedFootage = app.project.importFile(importOptions);
                    
                    results.success = true;
                    results.footageName = importedFootage.name;
                    results.footageId = importedFootage.id;
                    
                    ${compPart}
                }
            } catch (e) {
                results.success = false;
                results.error = e.toString();
            }
            
            app.endUndoGroup();
            
            return results;
        })();`;
    }
    
    /**
     * 准备导入素材的 MCP 命令
     * @param {string} winPath - Windows 路径（自动转换为安全路径）
     * @param {string} compName - 目标合成名称（可选）
     * @returns {object} 准备好的命令参数
     */
    static prepareImportCommand(winPath, compName = null) {
        const safePath = PathUtils.toExtendScriptPath(winPath);
        const scriptContent = this.generateImportScript(safePath, compName);
        
        return {
            scriptContent: scriptContent,
            safePath: safePath,
            originalPath: winPath,
            compName: compName
        };
    }
}

module.exports = AEImporter;
