# 회식 장소 투표 — 링크만 있으면 누구나 투표하는 버전

claude.ai 계정 없이 링크만 눌러 투표할 수 있는 버전입니다. 투표는 Google 시트에 저장됩니다.

## 배포 (약 5분, 한 번만)

1. Google 드라이브에서 **새 Google 스프레드시트**를 만듭니다. (이름 예: 회식 장소 투표)
2. 메뉴 **확장 프로그램 → Apps Script**를 엽니다.
3. 기본 `Code.gs` 내용을 지우고 이 폴더의 `Code.gs`를 통째로 붙여 넣습니다.
4. 왼쪽 **파일 +** → **HTML** → 이름을 `Index`로 만들고, 이 폴더의 `Index.html`을 통째로 붙여 넣습니다.
5. 오른쪽 위 **배포 → 새 배포** → 유형 **웹 앱**
   - 다음 사용자 인증 정보로 실행: **나**
   - 액세스 권한이 있는 사용자: **모든 사용자**
6. **배포**를 누르고 권한을 승인합니다. ("확인되지 않은 앱" 경고가 나오면 고급 → 이동)
7. 나온 **웹 앱 URL**(`https://script.google.com/macros/s/.../exec`)을 팀에 공유합니다.

## 동작

- 이름을 입력하고 1차·2차를 모두 골라야 제출됩니다. 같은 이름으로 다시 제출하면 수정됩니다.
- 결과는 15초마다 자동으로 새로 고쳐집니다.
- 2026-10-02 19:08 (KST) 이후에는 서버에서도 저장을 거부합니다.
- 시트의 `votes` 탭에서 투표 내역(이름, 1차, 2차, 남길 말, 저장 시각)을 바로 볼 수 있습니다.

## 페이지 수정 후 다시 만들기

`../index.html`(claude.ai 아티팩트 버전)을 고친 뒤 `python3 apps-script/build.py`를 실행하면
`Index.html`이 다시 만들어집니다. Apps Script에 붙여 넣고 **배포 → 배포 관리 → 수정 → 새 버전**으로 갱신하세요.

## GitHub Pages로 열기 (https://shcho-el.github.io/Marketing/)

`docs/index.html`이 같은 투표 페이지의 GitHub Pages 버전입니다. 투표는 위 Apps Script 웹 앱에 저장됩니다.

1. 위 "배포" 1~7단계로 Apps Script 웹 앱 URL을 만듭니다.
2. 그 URL을 `docs/api-url.txt`에 한 줄로 넣고 `python3 team-dinner-survey/apps-script/build.py`를 실행해 커밋합니다.
3. GitHub 저장소 **Settings → Pages → Build and deployment**
   - Source: **Deploy from a branch**
   - Branch: 이 페이지가 있는 브랜치, 폴더 **/docs** → Save
4. 1~2분 뒤 `https://shcho-el.github.io/Marketing/`에서 열립니다.
