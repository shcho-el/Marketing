@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if not exist "logs" mkdir "logs" >nul 2>&1

:: 화면에도 보여 주고 파일에도 남긴다. 창이 닫혀도 기록은 남는다.
title 오블리브 콘텐츠 콘솔
.venv\Scripts\python.exe -u main.py content > "logs\server.log" 2>&1

echo.
echo  서버가 멈췄습니다. 위 내용은 logs\server.log 에도 남아 있습니다.
type "logs\server.log"
pause
