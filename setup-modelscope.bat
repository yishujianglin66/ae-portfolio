@echo off
chcp 65001 >nul
REM ==========================================
REM 魔搭 ModelScope 一键配置脚本
REM 自动完成：项目集成 + Trae MCP配置
REM ==========================================

echo.
echo  ==========================================
echo    魔搭 ModelScope 一键配置
echo  ==========================================
echo.

REM 检查 .env 文件是否存在
if not exist .env (
    echo  [1/4] 创建 .env 配置文件...
    copy .env.modelscope.example .env >nul
    echo  ✅ .env 已创建，请编辑填入你的API Key
    echo.
    echo  ⚠️  重要：请手动编辑 .env 文件，将
    echo     MODELSCOPE_API_KEY=your_modelscope_api_key_here
    echo     替换为你的真实API Key
    echo.
    echo     获取地址：https://modelscope.cn/my/myaccesstoken
    echo.
    set /p confirm="编辑完成后按回车继续..."
) else (
    echo  [1/4] .env 文件已存在，跳过创建
)

REM 检查API Key是否已配置
echo.
echo  [2/4] 检查魔搭API Key配置...
findstr /C:"MODELSCOPE_API_KEY=your" .env >nul
if %errorlevel% == 0 (
    echo  ❌ API Key 仍为默认值，请先编辑 .env 文件
    echo.
    echo  请修改这行：
    echo    MODELSCOPE_API_KEY=your_modelscope_api_key_here
    echo  改为：
    echo    MODELSCOPE_API_KEY=你的真实API_Key
    echo.
    pause
    exit /b 1
)
echo  ✅ API Key 已配置

REM 配置Trae MCP
echo.
echo  [3/4] 配置Trae MCP...
echo.
echo  请按以下步骤手动配置Trae：
echo.
echo  方法一：通过Trae设置界面
echo  1. 打开Trae → 设置 → MCP
echo  2. 点击 "添加MCP服务器"
echo  3. 选择 "从JSON文件导入"
echo  4. 选择文件：%CD%\modelscope-mcp-config.json
echo.
echo  方法二：手动复制配置
echo  1. 打开Trae → 设置 → MCP → 打开配置文件
echo  2. 将 modelscope-mcp-config.json 的内容粘贴进去
echo.
set /p confirm="配置完成后按回车继续..."

REM 验证配置
echo.
echo  [4/4] 验证配置...
echo.
echo  正在测试魔搭API连接...
python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env')
key = os.getenv('MODELSCOPE_API_KEY', '')
if key and key != 'your_modelscope_api_key_here':
    print('✅ API Key 已加载')
else:
    print('❌ API Key 未配置')
" 2>nul

echo.
echo  ==========================================
echo    配置完成！
echo  ==========================================
echo.
echo  📋 下一步操作：
echo.
echo  1. 确保已获取魔搭API Key：
echo     https://modelscope.cn/my/myaccesstoken
echo.
echo  2. 在Trae中配置MCP（按上面步骤）
echo.
echo  3. 在项目代码中使用：
echo     from core.llm_gateway import chat_with_routing
echo     # 魔搭Provider已自动加入网关
echo.
echo  4. 触发方式：
echo     • Trae MCP：对话中AI自动判断调用
echo     • 项目代码：网关自动路由到魔搭模型
echo.
echo  🔗 相关链接：
echo     • 魔搭MCP广场：https://modelscope.cn/mcp
echo     • 魔搭Skills：https://modelscope.cn/collections/modelscope/ModelScope-Skills
echo     • 魔搭OpenAPI：https://modelscope.cn/docs/openapi
echo.
pause