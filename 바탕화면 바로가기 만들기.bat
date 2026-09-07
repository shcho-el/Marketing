@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  바탕화면 바로가기를 만듭니다.
echo.

if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe tools\make_icon.py
) else (
  where py >nul 2>&1 && (py -3 tools\make_icon.py) || (python tools\make_icon.py)
)

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\make_shortcut.ps1"
pause
