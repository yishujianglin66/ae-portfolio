# 🎬 AE MCP 导入素材实战测试计划

## 📋 环境准备

✅ **已确认**：
- After Effects MCP 服务器已构建
- `import-footage` 工具已可用
- MCP Bridge Auto 面板已打开（显示 "Ready - Auto-run is ON"）
- 测试素材已准备：
  - `c:\Users\Administrator\Desktop\AE-Knowledge-Vault\05-测试套件\test_resources\test_image.png`

---

## 🎯 测试用例

### 测试用例 1：基础素材导入
- **目标**：将 test_image.png 导入 AE 项目
- **参数**：
  ```json
  {
    "filePath": "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png"
  }
  ```
- **预期结果**：素材成功导入项目面板

---

### 测试用例 2：导入素材到合成
- **目标**：先创建测试合成，再导入素材并添加到合成
- **第一步**：创建测试合成
- **第二步**：导入素材并添加到合成

---

### 测试用例 3：错误处理（文件不存在）
- **目标**：测试系统对不存在文件的处理
- **参数**：
  ```json
  {
    "filePath": "c:\\nonexistent\\file.png"
  }
  ```
- **预期结果**：返回错误提示

---

### 测试用例 4：缺少必填参数
- **目标**：测试参数验证
- **预期结果**：工具提示缺少参数

---

## 🚀 执行步骤

### 方法 A：通过聊天界面调用 MCP 工具（推荐）

直接在聊天中告诉我你要进行哪个测试，我会调用相应的 MCP 工具！

---

### 方法 B：通过 MCP Bridge Auto 手动执行

1. 在 After Effects 中打开 `MCP Bridge Auto` 面板
2. 确认面板显示 "Ready - Auto-run is ON"
3. 使用你喜欢的 MCP 客户端调用 `import-footage` 工具
4. 使用 `get-results` 获取测试结果

---

### 方法 C：直接运行测试脚本

1. 在 After Effects 中，菜单：文件 → 脚本 → 运行脚本文件...
2. 选择：`05-测试套件\Simple1_CreateComp.jsx`
3. 如果成功，再选择：`05-测试套件\Simple2_ImportFootage.jsx`

---

## 📊 测试结果记录模板

| 测试用例 | 状态 | 描述 |
|---------|------|------|
| 1. 基础素材导入 | ⏳ 待测试 | |
| 2. 导入到合成 | ⏳ 待测试 | |
| 3. 错误处理 | ⏳ 待测试 | |
| 4. 参数验证 | ⏳ 待测试 | |

---

## 💡 开始测试！

准备好了吗？直接告诉我你要开始哪个测试！
