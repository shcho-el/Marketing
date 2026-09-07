#!/usr/bin/env bash
# 콘텐츠 콘솔 서버 — 맥 / 리눅스
set -u
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo " [!] 아직 준비되지 않았습니다. ./start.sh 를 먼저 한 번 실행하세요."
  exit 1
fi
exec .venv/bin/python main.py content
