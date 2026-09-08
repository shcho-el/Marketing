@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

title 오블리브 콘텐츠 콘솔 실행

if not exist "logs" mkdir "logs" >nul 2>&1

set "PORT=5001"
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="CONTENT_PORT" set "PORT=%%B"
)
set "URL=http://localhost:%PORT%"

:: ── 최신 코드 받기 ────────────────────────────────────────────────
:: 바로가기로만 여는 분들은 update.bat 을 따로 실행하지 않는다.
:: 그러면 새로 만든 기능이 화면에 없고, 그게 "구현이 안 된 것"처럼 보인다.
set "UPDATED=0"
where git >nul 2>&1
if not errorlevel 1 (
  echo.
  echo  최신 코드를 확인합니다...
  git fetch --quiet origin >nul 2>&1
  set "BEHIND="
  set "UPSTREAM="
  for /f "tokens=*" %%B in ('git rev-parse --abbrev-ref --symbolic-full-name @{u} 2^>nul') do set "UPSTREAM=%%B"
  if "!UPSTREAM!"=="" (
    for /f "tokens=*" %%B in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "UPSTREAM=origin/%%B"
  )
  for /f %%C in ('git rev-list --count "HEAD..!UPSTREAM!" 2^>nul') do set "BEHIND=%%C"
  if not "!BEHIND!"=="" if not "!BEHIND!"=="0" (
    echo  업데이트 !BEHIND!개를 받아옵니다...
    git pull --ff-only --quiet origin "!UPSTREAM:origin/=!"
    if errorlevel 1 (
      echo.
      echo  [!] 자동으로 받지 못했습니다. 고쳐 둔 파일이 있을 수 있습니다.
      echo      이 창을 닫고 update.bat 을 실행해 주세요. 옛 코드로 계속 진행합니다.
      echo.
    ) else (
      set "UPDATED=1"
      echo  받았습니다. 패키지를 맞춥니다...
      if exist ".venv\Scripts\python.exe" (
        .venv\Scripts\python.exe -m pip install -q -r requirements.txt
      )
    )
  ) else (
    echo  최신입니다.
  )
)

:: ── 이미 떠 있는 서버 처리 ────────────────────────────────────────
call :alive
if "!ALIVE!"=="1" (
  if "!UPDATED!"=="1" (
    echo  코드를 새로 받았습니다. 서버를 다시 켭니다...
    call :stopserver
    call :alive
    if "!ALIVE!"=="1" (
      echo.
      echo  [!] 서버를 끄지 못했습니다. "오블리브 콘텐츠 콘솔" 창에서 Ctrl+C 로 끄고
      echo      이 바로가기를 다시 눌러 주세요. 지금은 옛 화면이 열립니다.
      echo.
      timeout /t 6 /nobreak >nul
      start "" "%URL%"
      exit /b 0
    )
  ) else (
    start "" "%URL%"
    exit /b 0
  )
)

:: ── 준비가 안 됐으면 start.bat 으로 보낸다 ────────────────────────
if not exist ".venv\Scripts\python.exe" (
  echo  처음 실행이라 준비가 필요합니다. start.bat 을 실행합니다...
  start "" "start.bat"
  exit /b 0
)

:: ── 서버 기동 ─────────────────────────────────────────────────────
:: 기록을 logs\server.log 에 남긴다. 창이 최소화되어 있어 오류가 그냥
:: 사라지면 무엇이 잘못됐는지 알 길이 없다.
echo  서버를 켭니다...
start "오블리브 콘텐츠 콘솔" /min cmd /c "tools\run_server.bat"

for /l %%i in (1,1,40) do (
  timeout /t 1 /nobreak >nul
  call :alive
  if "!ALIVE!"=="1" (
    start "" "%URL%"
    exit /b 0
  )
)

echo.
echo  ================================================
echo   서버가 뜨지 않았습니다.
echo  ================================================
echo.
if exist "logs\server.log" (
  echo  마지막 기록입니다:
  echo.
  powershell -NoProfile -Command "Get-Content -LiteralPath 'logs\server.log' -Tail 25"
  echo.
  echo  ^(전체 기록: logs\server.log^)
) else (
  echo  기록 파일이 없습니다. 파이썬이 아예 실행되지 않았을 수 있습니다.
)
echo.
echo  ob d  또는  .venv\Scripts\python.exe main.py doctor  로 환경을 점검해 보세요.
echo.
pause
exit /b 1

:: ── 서브루틴 ──────────────────────────────────────────────────────
:alive
set "ALIVE=0"
powershell -NoProfile -Command ^
  "try{(New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%)).Close();exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 set "ALIVE=1"
exit /b 0

:stopserver
if exist "logs\server.pid" (
  set /p SRVPID=<"logs\server.pid"
  if not "!SRVPID!"=="" taskkill /PID !SRVPID! /T /F >nul 2>&1
)
for /l %%i in (1,1,10) do (
  timeout /t 1 /nobreak >nul
  call :alive
  if "!ALIVE!"=="0" exit /b 0
)
exit /b 0
