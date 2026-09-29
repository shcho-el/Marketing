@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if not exist "logs" mkdir "logs" >nul 2>&1

title 오블리브 콘텐츠 콘솔

:: 출력이 파일로 넘어가면 파이썬이 cp949로 인코딩하려 든다. UTF-8로 고정한다.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "LOG=logs\server.log"

:: 파이썬이 한 글자도 못 쓰고 끝나면 기록이 비어 원인을 알 수 없다.
:: 파이썬을 부르기 전에 여기까지 왔다는 사실부터 적어 둔다.
> "%LOG%" echo [%date% %time%] 서버를 켭니다
>>"%LOG%" echo 폴더: %CD%

if not exist ".venv\Scripts\python.exe" (
  >>"%LOG%" echo [X] .venv\Scripts\python.exe 이 없습니다. start.bat 을 먼저 실행하세요.
  type "%LOG%"
  pause
  exit /b 1
)

>>"%LOG%" echo 파이썬: 
.venv\Scripts\python.exe -c "import sys;print(sys.version);print(sys.executable)" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo [X] 파이썬이 실행되지 않습니다. 가상환경이 깨졌을 수 있습니다.
  >>"%LOG%" echo     .venv 폴더를 지우고 start.bat 을 다시 실행하세요.
  type "%LOG%"
  pause
  exit /b 1
)

>>"%LOG%" echo ----------------------------------------
.venv\Scripts\python.exe -u main.py content >>"%LOG%" 2>&1
set "CODE=%errorlevel%"
>>"%LOG%" echo ----------------------------------------
>>"%LOG%" echo [%date% %time%] 서버가 멈췄습니다. 종료코드 %CODE%

echo.
echo  서버가 멈췄습니다. 같은 내용이 logs\server.log 에 있습니다.
echo.
type "%LOG%"
pause
