"""
CMS 자동 업로드 모듈.

  config.py     로그인 정보 · 셀렉터 매핑 로드
  thumbnail.py  규격(880x580, 300KB) 썸네일 생성
  browser.py    Selenium 드라이버 + 로그인
  inspector.py  글쓰기 폼 구조를 덤프해 셀렉터 매핑을 자동 생성
  publish.py    실제 업로드 (기본값: 미노출 저장)

셀렉터를 코드에 박아 두지 않고 inspector가 만든 매핑 파일을 읽습니다.
CMS 화면이 바뀌어도 inspector만 다시 돌리면 됩니다.
"""

__all__ = ["config", "thumbnail", "browser", "inspector", "publish"]
