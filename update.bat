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
  echo      (.env 와 assets 안의 로고/사진은 그대로 유지됩니다)
  echo.
  set /p FORCE="  서버 버전으로 맞출까요? (y/N) "
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

echo.
echo  완료했습니다. 서버가 켜져 있다면 창을 닫고 다시 켜야 반영됩니다.
echo.
pause
