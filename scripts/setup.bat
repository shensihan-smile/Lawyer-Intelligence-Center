@echo off
chcp 65001 >nul
echo ========================================
echo   律师智能中心 - 环境初始化
echo ========================================
echo.

echo [1/3] 安装 Python 依赖...
cd /d "%~dp0..\backend"
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Python 依赖安装失败！请检查网络或 Python 环境。
    pause
    exit /b 1
)
echo Python 依赖安装完成！

echo.
echo [2/3] 初始化数据库...
python -m app.core.seed
if %errorlevel% neq 0 (
    echo 数据库初始化失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 安装前端依赖...
cd /d "%~dp0..\frontend"
npm install
if %errorlevel% neq 0 (
    echo 前端依赖安装失败！请检查网络或 Node.js 环境。
    pause
    exit /b 1
)
echo 前端依赖安装完成！

echo.
echo ========================================
echo   环境初始化完成！
echo ========================================
echo.
echo 请运行 dev.bat 启动开发环境。
pause
