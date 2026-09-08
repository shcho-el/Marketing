@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

title CMS 폼 읽기

echo.
echo  ================================================
echo   CMS 글쓰기 폼 읽기
echo  ================================================
echo.
echo  블로그 관리자 페이지에 로그인해 입력 칸의 이름을 읽어옵니다.
echo  글을 쓰거나 저장하지 않습니다. 읽기만 합니다.
echo.
echo  브라우저 창이 뜨면 진행 과정을 눈으로 보실 수 있습니다.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo  [!] 아직 준비가 안 됐습니다. start.bat 을 먼저 실행하세요.
  echo.
  pause
  exit /b 1
)

.venv\Scripts\python.exe main.py inspect-cms --show

echo.
echo  ================================================
echo  위 결과를 그대로 복사해 보내 주세요.
echo  (아이디와 비밀번호는 결과에 포함되지 않습니다)
echo  ================================================
echo.
pause
