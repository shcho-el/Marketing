# 모델 섭외 현황판 (Apps Script)

Claude 섭외 현황 대시보드와 같은 화면을, 로그인 없이 링크로 볼 수 있게 만든 Google Apps Script 웹앱입니다.

- `Code.gs` — 서버 코드. Gmail 지원 메일·지원자_목록 시트·촬영일정_신청 `응답` 탭을 읽고, 상태·촬영일·메모는 촬영일정_신청 시트의 `현황` 탭에 저장합니다.
- `Board.html` — 화면. Apps Script에서 HTML 파일 이름을 `Board`로 만드세요.
- `build_board.py` — 대시보드 페이지(index.html)에서 `Board.html`을 다시 만드는 스크립트.
- `Seed.gs` — 기존 상태를 옮겨 넣는 데이터 파일. 개인정보가 들어 있어 저장소에는 올리지 않습니다 (담당자에게 따로 전달).

## 설정
1. script.google.com → 새 프로젝트 → `Code.gs` 붙여넣기
2. `+` → 스크립트 → 이름 `Seed` → 전달받은 `Seed.gs` 붙여넣기
3. `+` → HTML → 이름 `Board` → `Board.html` 붙여넣기
4. `setup` 실행 → 권한 승인 (Gmail·스프레드시트·Drive)
5. 배포 → 새 배포 → 웹 앱 / 실행 사용자: 나 / 액세스: 모든 사용자
6. `setup` 한 번 더 실행 → 로그에 **보기 링크**와 **편집 링크**가 나옵니다.

- 보기 링크: 누구나 볼 수 있고, 연락처도 보입니다. (`Code.gs`의 `MASK_PHONE_FOR_VIEWERS`를 `true`로 바꾸면 가려짐)
- 편집 링크(`?key=…`): 상태·촬영일·메모를 저장할 수 있습니다. 담당자만 쓰세요.
