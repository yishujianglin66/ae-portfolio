# F3: 文件导入功能测试 - 实战演练

## 📋 测试环境信息
- **测试日期**：2026-07-06
- **测试项目**：利威尔高燃混剪
- **项目目录**：`c:\Users\Administrator\Desktop\AE-Knowledge-Vault\test-projects\2026-07-06-利威尔高燃混剪`
- **MCP服务器**：after-effects-mcp-main
- **测试状态**：🔴 待执行

---

## 🎬 测试项目简介

这是一个完整的实战测试，使用利威尔·阿克曼的高燃混剪项目来测试After Effects MCP的文件导入功能。

### 项目结构
```
2026-07-06-利威尔高燃混剪/
├── 01-策划/
│   └── 需求文档.md
├── 02-素材/
│   ├── 视频素材/
│   │   └── 原始素材/
│   ├── 图片素材/
│   │   ├── test_image.png
│   │   └── test_image.svg
│   └── 音频素材/
│       ├── BGM/
│       └── 音效/
├── 03-工程/
│   ├── AE/
│   └── PR/
└── 04-渲染输出/
```

---

## 🔧 测试用例执行

### ✅ 测试准备完成
- [x] 创建完整的项目目录结构
- [x] 准备测试素材
- [x] 配置MCP服务器
- [x] 编写测试计划

---

## 🎯 实战测试步骤

### 步骤1：启动After Effects和MCP

1. 打开Adobe After Effects 2025
2. 确保MCP Bridge Auto面板已加载
3. 创建一个新项目，命名为 `利威尔高燃混剪.aep`
4. 保存到：`03-工程/AE/`

### 步骤2：创建主合成

在After Effects中创建合成：
```
合成名称：[Main]_利威尔高燃混剪_1920x1080
分辨率：1920x1080
帧率：29.97 fps
时长：30秒
背景：黑色
```

### 步骤3：使用MCP导入素材

**测试用例1：导入单张图片素材**
```
工具：import-footage
参数：
{
  "filePath": "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\test-projects\\2026-07-06-利威尔高燃混剪\\02-素材\\图片素材\\test_image.png",
  "asSequence": false
}
```

**测试用例2：导入素材到合成**
```
工具：import-footage
参数：
{
  "filePath": "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\test-projects\\2026-07-06-利威尔高燃混剪\\02-素材\\图片素材\\test_image.png",
  "compName": "[Main]_利威尔高燃混剪_1920x1080",
  "asSequence": false
}
```

**测试用例3：测试错误处理 - 文件不存在**
```
工具：import-footage
参数：
{
  "filePath": "c:\\Users\\不存在的文件.png",
  "asSequence": false
}
```

**测试用例4：测试错误处理 - 缺少必填参数**
```
工具：import-footage
参数：{}
```

---

## 📊 测试结果记录

| 测试用例 | 描述 | 状态 | 结果 |
|---------|------|------|------|
| 1 | 导入单张图片到项目 | ⏳ 待测试 | - |
| 2 | 导入图片到指定合成 | ⏳ 待测试 | - |
| 3 | 文件不存在错误处理 | ⏳ 待测试 | - |
| 4 | 缺少参数错误处理 | ⏳ 待测试 | - |

---

## 📝 后续工作

1. 执行上述测试步骤
2. 记录测试结果到表格
3. 根据测试结果修复问题（如有）
4. 继续测试其他MCP功能
