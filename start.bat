@echo off
REM PokeCrawler 一键启动
REM 启动后端并同时托管前端页面，之后浏览器访问 http://127.0.0.1:8000
chcp 65001 >nul

set "PY=C:\Users\谁知道\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

cd /d "%~dp0backend"

echo.
echo   正在启动 PokeCrawler ...
echo   页面地址: http://127.0.0.1:8000
echo   停止服务: 在此窗口按 Ctrl+C
echo.

"%PY%" run.py

pause
