@echo off
chcp 65001 >nul
title 律师智能中心 - 启动中...

echo.
echo   ========================================
echo     律师智能中心 - 开发环境启动
echo   ========================================
echo.

REM 获取本机局域网 IP
set "LOCAL_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" ^| findstr /v "192.168.56"') do (
    set "IP_RAW=%%a"
    set "IP_RAW=!IP_RAW: =!"
    if "!IP_RAW:~0,7!"=="192.168" set "LOCAL_IP=!IP_RAW!"
    if "!IP_RAW:~0,3!"=="10." set "LOCAL_IP=!IP_RAW!"
    if "!IP_RAW:~0,7!"=="172.16." set "LOCAL_IP=!IP_RAW!"
)
setlocal enabledelayedexpansion

echo   启动后端服务...
start "律师智能中心-后端" cmd /c "cd /d "%~dp0..\backend" && python run.py"
timeout /t 4 /nobreak >nul

echo   启动前端服务...
start "律师智能中心-前端" cmd /c "cd /d "%~dp0..\frontend" && npm run dev -- --host 0.0.0.0"

echo.
timeout /t 3 /nobreak >nul

echo   ========================================
echo     服务启动完成！
echo   ========================================
echo.
echo   [您自己访问]
echo      http://localhost:5173
echo.
if not "!LOCAL_IP!"=="" (
    echo   [分享给同事的地址（需同一WiFi）]
    echo      http://!LOCAL_IP!:5173
    echo.
    echo   把上面这个地址发给同事即可
) else (
    echo   [未检测到局域网IP，请手动查看]
    echo   打开 cmd 输入 ipconfig 找到 IPv4 地址
    echo   然后访问 http://你的IP:5173
)
echo   ========================================
echo   默认账号: demo / demo123 (体验)
echo             admin / admin123 (管理员)
echo   ========================================
echo.
pause
