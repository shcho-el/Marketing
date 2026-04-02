@echo off
cd /d %~dp0

:: 환경변수 로드 (.env 파일에서 읽기)
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "%%A=%%B"
)

:: 순위 수집 실행
python main.py collect >> logs\collect.log 2>&1
