@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  ================================================
echo   업데이트
echo  ================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo  [X] git 을 찾지 못했습니다.
  echo      https://git-scm.com/download/win 에서 설치하세요.
  echo.
  pause
  exit /b 1
)

echo  현재 버전:
git log --oneline -1
echo.

echo  받아오는 중...
git fetch origin
if errorlevel 1 (
  echo.
  echo  [X] 서버에서 받아오지 못했습니다. 인터넷 연결을 확인하세요.
  pause
  exit /b 1
)

git pull
if errorlevel 1 (
  echo.
  echo  [!] 로컬에 바뀐 파일이 있어 그냥 합칠 수 없습니다.
  echo      코드를 직접 고치지 않으셨다면 서버 버전으로 맞추면 됩니다.
  echo      ^(.env 와 assets 안의 로고/사진은 그대로 유지됩니다^)
  echo.
  set /p FORCE="  서버 버전으로 맞출까요? [y/N] "
  if /i "!FORCE!"=="y" (
    for /f "tokens=*" %%B in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%B"
    git reset --hard "origin/!BRANCH!"
    if errorlevel 1 (
      echo  [X] 실패했습니다. 이 창의 내용을 그대로 보내주세요.
      pause
      exit /b 1
    )
  ) else (
    echo  취소했습니다.
    pause
    exit /b 1
  )
)

echo.
echo  업데이트 후 버전:
git log --oneline -1
echo.

:: 새 패키지가 생겼을 수 있으니 한 번 맞춰 준다
if exist ".venv\Scripts\python.exe" (
  echo  패키지 확인 중...
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
  echo.
  .venv\Scripts\python.exe main.py doctor
)


:: ── 돌고 있는 서버 다시 켜기 ──────────────────────────────────────
:: 파이썬은 실행 중에 코드를 다시 읽지 않는다. 코드만 받아 놓고 서버를
:: 그대로 두면 화면은 새것인데 동작은 옛것이다. 같은 오류가 그대로 난다.
set "PORT=5001"
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="CONTENT_PORT" set "PORT=%%B"
)

netstat -an | findstr /c:":!PORT! " >nul 2>&1
if not errorlevel 1 (
  echo  서버가 켜져 있습니다. 새 코드로 다시 켭니다...
  if exist "logs\server.pid" (
    set /p SRVPID=<"logs\server.pid"
    if not "!SRVPID!"=="" taskkill /PID !SRVPID! /T /F >nul 2>&1
  )
  timeout /t 2 /nobreak >nul
  netstat -an | findstr /c:":!PORT! " >nul 2>&1
  if not errorlevel 1 (
    echo.
    echo  [!] 서버를 끄지 못했습니다.
    echo      "오블리브 콘텐츠 콘솔" 창에서 Ctrl+C 로 끄고 바로가기를 다시 눌러 주세요.
    echo      끄지 않으면 옛 코드가 그대로 돕니다.
    echo.
  ) else (
    start "" "launch.bat"
    echo  다시 켰습니다.
  )
)

echo.
echo  완료했습니다.
echo.
pause
