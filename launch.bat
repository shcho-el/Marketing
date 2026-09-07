@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PORT=5001"
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="CONTENT_PORT" set "PORT=%%B"
)
set "URL=http://localhost:%PORT%"

:: 이미 떠 있으면 브라우저만 연다
powershell -NoProfile -Command ^
  "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%)).Close();exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 (
  start "" "%URL%"
  exit /b 0
)

:: 준비가 안 됐으면 start.bat 으로 보낸다
if not exist ".venv\Scripts\python.exe" (
  echo  처음 실행이라 준비가 필요합니다. start.bat 을 실행합니다...
  start "" "start.bat"
  exit /b 0
)

:: 서버를 최소화 창으로 띄운다 (창을 닫으면 서버도 꺼진다)
start "오블리브 콘텐츠 콘솔" /min cmd /c "cd /d "%~dp0" && .venv\Scripts\python.exe main.py content"

:: 열릴 때까지 최대 40초 기다렸다가 브라우저를 연다
for /l %%i in (1,1,40) do (
  timeout /t 1 /nobreak >nul
  powershell -NoProfile -Command ^
    "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%)).Close();exit 0}catch{exit 1}" >nul 2>&1
  if not errorlevel 1 (
    start "" "%URL%"
    exit /b 0
  )
)

echo.
echo  서버가 뜨지 않았습니다. 작업표시줄의 "오블리브 콘텐츠 콘솔" 창에서
echo  오류 메시지를 확인하거나, ob d 로 환경을 점검하세요.
pause
