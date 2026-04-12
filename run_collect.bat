@echo off
cd /d C:\Users\medib\marketing

:: 환경변수 로드 (.env 파일에서 읽기)
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "%%A=%%B"
)

:: 순위 수집 실행 (Python 전체 경로 명시 - 비로그인 실행 대응)
C:\Users\medib\AppData\Local\Python\pythoncore-3.14-64\python.exe main.py collect >> logs\collect.log 2>&1
