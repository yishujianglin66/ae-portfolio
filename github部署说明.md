# GitHub Pages 部署说明

## 第一步：在GitHub创建仓库

1. 打开浏览器，访问：https://github.com/new
2. 填写仓库信息：
   - Repository name: `ae-portfolio`
   - Description: `AE Knowledge Vault - 智能视频自动化制作平台作品集`
   - 选择 `Public`（公开）
   - 不要勾选 "Add a README file"
   - 不要勾选 ".gitignore" 和 "license"
3. 点击 `Create repository` 按钮

## 第二步：推送代码到GitHub

创建仓库后，GitHub会显示推送命令。复制并运行以下命令：

```powershell
cd c:\Users\Administrator\Desktop\AE-Knowledge-Vault\portfolio

git remote add origin https://github.com/yishujianglin66/ae-portfolio.git
git branch -M main
git push -u origin main
```

## 第三步：启用GitHub Pages

1. 推送成功后，访问：https://github.com/yishujianglin66/ae-portfolio/settings/pages
2. 在 "Source" 部分：
   - 选择 `Deploy from a branch`
   - Branch 选择 `main`
   - 点击 `Save`

3. 等待1-2分钟，页面会刷新并显示：
   ```
   Your site is published at https://yishujianglin66.github.io/ae-portfolio/
   ```

## 第四步：访问作品集

**你的作品集地址**：
```
https://yishujianglin66.github.io/ae-portfolio/
```

## 快速链接

- 创建仓库：https://github.com/new
- 仓库设置：https://github.com/yishujianglin66/ae-portfolio/settings
- Pages设置：https://github.com/yishujianglin66/ae-portfolio/settings/pages
- 作品集地址：https://yishujianglin66.github.io/ae-portfolio/

---

## 如果推送失败

如果遇到权限问题，请使用以下命令：

```powershell
# 方法1：使用Personal Access Token
git remote set-url origin https://<token>@github.com/yishujianglin66/ae-portfolio.git

# 方法2：使用SSH（如果已配置）
git remote set-url origin git@github.com:yishujianglin66/ae-portfolio.git
```

---

**当前状态**：
✅ Git仓库已初始化
✅ 代码已提交
⏳ 等待创建GitHub远程仓库
⏳ 等待推送代码
⏳ 等待启用Pages