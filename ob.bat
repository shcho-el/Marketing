@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "VPY=.venv\Scripts\python.exe"
) else (
  where py >nul 2>&1 && set "VPY=py -3"
  if not defined VPY set "VPY=python"
)

if "%~1"=="" (
  %VPY% main.py
  echo.
  pause
  exit /b 0
)

%VPY% main.py %*
