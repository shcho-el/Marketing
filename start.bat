@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  ================================================
echo   오블리브 콘텐츠 생성기
echo  ================================================
echo.

:: ── 파이썬 찾기 ────────────────────────────────────────────────
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY ( where python >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo  [X] 파이썬을 찾지 못했습니다.
  echo.
  echo      https://www.python.org/downloads/ 에서 설치하세요.
  echo      설치할 때 "Add Python to PATH"를 반드시 체크해야 합니다.
  echo.
  pause
  exit /b 1
)

:: ── 가상환경 ───────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
  echo  [1/4] 가상환경을 만듭니다. 처음 한 번만 걸립니다...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo  [X] 가상환경을 만들지 못했습니다.
    pause
    exit /b 1
  )
) else (
  echo  [1/4] 가상환경 확인
)
set "VPY=.venv\Scripts\python.exe"

:: ── 패키지 ─────────────────────────────────────────────────────
if not exist ".venv\.installed" (
  echo  [2/4] 필요한 패키지를 설치합니다. 몇 분 걸립니다...
  "%VPY%" -m pip install --upgrade pip >nul 2>&1
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo  [X] 패키지 설치에 실패했습니다. 위 메시지를 확인하세요.
    pause
    exit /b 1
  )
  echo installed> ".venv\.installed"
) else (
  echo  [2/4] 패키지 확인
)

:: ── 설정 파일 ──────────────────────────────────────────────────
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo  [!] .env 파일을 만들었습니다.
  echo.
  echo      메모장으로 .env를 열어 아래를 채워주세요.
  echo        ANTHROPIC_API_KEY  원고 생성에 필요 ^(console.anthropic.com^)
  echo        CMS_USERNAME / CMS_PASSWORD   CMS 자동 업로드에 필요
  echo.
  echo      지금 채우지 않아도 화면은 열립니다. 원고 검사는 바로 쓸 수 있습니다.
  echo.
  notepad .env
)
echo  [3/4] 설정 확인

:: ── 환경 점검 ──────────────────────────────────────────────────
"%VPY%" main.py doctor

:: ── 실행 ───────────────────────────────────────────────────────
echo  [4/4] 앱을 시작합니다...
echo.
echo      주소: http://localhost:5001
echo      끄려면 이 창에서 Ctrl+C 를 누르거나 창을 닫으세요.
echo.
start "" http://localhost:5001
"%VPY%" main.py content

echo.
echo  앱이 종료되었습니다.
pause
