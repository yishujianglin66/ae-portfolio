@echo off
REM AE Portfolio - GitHub Pages 部署脚本
REM 使用方法：双击运行此脚本，按照提示操作

echo ========================================
echo   AE Portfolio - GitHub Pages 部署
echo ========================================
echo.

REM 设置变量
set REPO_NAME=ae-portfolio
set GITHUB_USERNAME=你的GitHub用户名

echo 请先完成以下准备工作：
echo 1. 在GitHub创建仓库：%REPO_NAME%
echo 2. 仓库地址：https://github.com/%GITHUB_USERNAME%/%REPO_NAME%
echo.
pause

REM 初始化Git（如果需要）
if not exist .git (
    echo 正在初始化Git仓库...
    git init
    git branch -M main
)

REM 添加必要文件
echo 正在添加文件到Git...
git add portfolio.html
git add PROJECT_PORTFOLIO.md
git add "简历投递-公网访问方案.md"

REM 添加截图文件
echo 正在添加截图文件...
git add ae-dashboard\shot_01_dashboard.png
git add ae-dashboard\shot_02_effects.png
git add ae-dashboard\shot_03_execute.png
git add ae-dashboard\shot_05_styles.png
git add ae-dashboard\shot_06_projects.png
git add ae-dashboard\shot_07_history.png

REM 提交
echo 正在提交更改...
git commit -m "Add portfolio website for resume"

REM 添加远程仓库
echo 正在添加远程仓库...
git remote remove origin 2>nul
git remote add origin https://github.com/%GITHUB_USERNAME%/%REPO_NAME%.git

REM 推送
echo 正在推送到GitHub...
git push -u origin main

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
echo 接下来的步骤：
echo 1. 访问：https://github.com/%GITHUB_USERNAME%/%REPO_NAME%/settings/pages
echo 2. Source 选择：main 分支
echo 3. 点击：Save
echo 4. 等待1-2分钟部署
echo.
echo 你的作品集地址将是：
echo https://%GITHUB_USERNAME%.github.io/%REPO_NAME%/portfolio.html
echo.
pause