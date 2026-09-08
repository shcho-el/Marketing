# -*- coding: utf-8 -*-
"""
화면 출력 인코딩을 UTF-8로 고정한다.

한글 윈도우의 기본 코드페이지는 cp949다. 출력을 파일이나 파이프로 넘기면
파이썬이 cp949로 인코딩하려 하고, 줄표(—)처럼 cp949에 없는 글자 하나에서
UnicodeEncodeError가 나 프로그램 전체가 멈춘다.

안내 문구 한 줄 때문에 서버가 뜨지 않는 일은 없어야 한다. 그래서 실행
시작 지점마다 이 함수를 부른다. errors="replace"까지 두어, 어떤 글자가
와도 출력이 죽지 않게 한다.
"""

import sys


def use_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass  # 다시 설정할 수 없는 스트림이면 그대로 둔다
