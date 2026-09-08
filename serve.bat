@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

title 오블리브 콘텐츠 콘솔 (서버)

echo.
echo  ================================================
echo   콘텐츠 콘솔 서버
echo  ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo  [!] 아직 준비되지 않았습니다. start.bat 을 먼저 한 번 실행하세요.
  pause
  exit /b 1
)
set "VPY=.venv\Scripts\python.exe"

:: 방화벽 규칙 (관리자 권한일 때만 성공. 실패해도 이 PC에서는 동작함)
netsh advfirewall firewall show rule name="ObliveContentConsole" >nul 2>&1
if errorlevel 1 (
  echo  방화벽에 5001 포트를 여는 중... ^(관리자 권한이 아니면 건너뜁니다^)
  netsh advfirewall firewall add rule name="ObliveContentConsole" ^
    dir=in action=allow protocol=TCP localport=5001 >nul 2>&1
  if errorlevel 1 (
    echo  [!] 방화벽 규칙을 추가하지 못했습니다.
    echo      다른 PC에서 접속하려면 serve.bat 을 마우스 오른쪽 - 관리자 권한으로 실행하세요.
    echo      이 PC에서만 쓸 거라면 그냥 두셔도 됩니다.
    echo.
  )
)

"%VPY%" main.py content

echo.
echo  서버가 종료되었습니다.
pause
