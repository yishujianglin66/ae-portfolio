// 诊断脚本：测试AE能否访问帧文件路径
{
    var results = [];
    
    // 测试路径1: 正斜杠
    var dir1 = "D:/AE-Work/视频素材库/frames";
    var folder1 = new Folder(dir1);
    results.push("Path1 (slash): exists=" + folder1.exists + ", files=" + (folder1.exists ? folder1.getFiles("*.png").length : "N/A"));
    
    // 测试路径2: 反斜杠
    var dir2 = "D:\\AE-Work\\视频素材库\\frames";
    var folder2 = new Folder(dir2);
    results.push("Path2 (backslash): exists=" + folder2.exists + ", files=" + (folder2.exists ? folder2.getFiles("*.png").length : "N/A"));
    
    // 测试路径3: fsName
    var dir3 = Folder.myDocuments.fsName + "/../AE-Work/视频素材库/frames";
    var folder3 = new Folder(dir3);
    results.push("Path3 (relative): exists=" + folder3.exists);
    
    // 尝试读取具体文件
    var testFile = new File(dir1 + "/frame_001.png");
    results.push("frame_001.png exists=" + testFile.exists);
    
    // 显示结果
    var msg = "DIAG RESULTS:\n" + results.join("\n");
    
    // 写入结果文件
    var resFile = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/diag_result.txt");
    resFile.encoding = "UTF-8";
    resFile.open("w");
    resFile.write(msg);
    resFile.close();
    
    // 同时alert显示
    alert(msg);
}
