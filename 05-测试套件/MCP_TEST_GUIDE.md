# 🚀 MCP 素材导入完整测试指南

## 📋 前提条件
- ✅ After Effects 已打开
- ✅ 项目已保存
- ✅ "MCP Bridge Auto" 面板已打开（显示 "Ready - Auto-run is ON"）

---

## 🎯 完整测试流程（3个步骤）

### 步骤 1: 创建测试合成
```bash
cd "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\05-测试套件"
node FULL_MCP_TEST.js
```

**检查**: 确认 AE 中创建了 `MCP_Test_Comp` 合成

---

### 步骤 2: 导入素材到项目
```bash
node STEP_2_IMPORT_FOOTAGE.js
```

**检查**: 确认 AE 项目面板中有 `test_image.png`

---

### 步骤 3: 导入素材到合成
```bash
node STEP_3_IMPORT_TO_COMP.js
```

**检查**: 确认素材已添加到 `MCP_Test_Comp` 合成中

---

## 📁 可用的测试文件

| 文件 | 说明 |
|------|------|
| `FULL_MCP_TEST.js` | 步骤 1 - 创建测试合成 |
| `STEP_2_IMPORT_FOOTAGE.js` | 步骤 2 - 导入素材到项目 |
| `STEP_3_IMPORT_TO_COMP.js` | 步骤 3 - 导入素材到合成 |
| `AE_MCP_AutoTest.jsx` | 在 AE 中直接运行的完整测试（一键式） |
| `MCP_DIRECT_TEST.js` | 直接模拟 MCP 服务器的测试 |

---

## 💡 备用方案（一键式测试）

如果分步测试有问题，也可以在 AE 中直接运行:

1. 在 AE 菜单中: `文件 > 脚本 > 运行脚本文件...`
2. 选择: `c:\Users\Administrator\Desktop\AE-Knowledge-Vault\05-测试套件\AE_MCP_AutoTest.jsx`
3. 这将运行完整测试并显示结果

---

## ✅ 成功标准

测试完成后，你应该在 AE 中看到:

1. **项目面板**: `MCP_Test_Comp` 合成 + `test_image.png` 素材
2. **合成面板**: `MCP_Test_Comp` 合成中包含 `test_image.png` 图层
3. **图层位置**: 素材居中显示

---

## 🎉 完成！

请按顺序运行上面的 3 个步骤，然后告诉我结果！
