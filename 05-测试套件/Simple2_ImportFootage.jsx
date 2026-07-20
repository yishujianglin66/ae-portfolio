// 最简单的测试脚本 v1.0 - 导入素材
// 兼容性最高的版本

var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
var file = new File(filePath);
var importOptions = new ImportOptions(file);
var footage = app.project.importFile(importOptions);
alert("成功！\n\n已导入素材：" + footage.name);
