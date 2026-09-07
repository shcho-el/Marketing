#!/usr/bin/env bash
# 오블리브 콘텐츠 생성기 — 맥 / 리눅스용 실행 스크립트
set -u
cd "$(dirname "$0")"

echo
echo " ================================================"
echo "  오블리브 콘텐츠 생성기"
echo " ================================================"
echo

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo " [X] 파이썬을 찾지 못했습니다. python.org 에서 설치하세요."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo " [1/4] 가상환경을 만듭니다. 처음 한 번만 걸립니다..."
  "$PY" -m venv .venv || { echo " [X] 가상환경 생성 실패"; exit 1; }
else
  echo " [1/4] 가상환경 확인"
fi
VPY=".venv/bin/python"

if [ ! -f ".venv/.installed" ]; then
  echo " [2/4] 필요한 패키지를 설치합니다. 몇 분 걸립니다..."
  "$VPY" -m pip install --upgrade pip >/dev/null 2>&1
  "$VPY" -m pip install -r requirements.txt || { echo " [X] 패키지 설치 실패"; exit 1; }
  touch ".venv/.installed"
else
  echo " [2/4] 패키지 확인"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo
  echo " [!] .env 파일을 만들었습니다. 아래를 채워주세요:"
  echo "       ANTHROPIC_API_KEY            원고 생성에 필요"
  echo "       CMS_USERNAME / CMS_PASSWORD  CMS 자동 업로드에 필요"
  echo "     지금 채우지 않아도 화면은 열립니다."
  echo
fi
echo " [3/4] 설정 확인"

"$VPY" main.py doctor

echo " [4/4] 앱을 시작합니다..."
echo
echo "     주소: http://localhost:5001"
echo "     끄려면 Ctrl+C"
echo
( sleep 2
  if command -v open >/dev/null 2>&1; then open http://localhost:5001
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:5001
  fi ) >/dev/null 2>&1 &

exec "$VPY" main.py content
