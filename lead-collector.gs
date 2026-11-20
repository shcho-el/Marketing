/**
 * 추구미 테스트 상담 신청 → 구글 스프레드시트 저장 (Google Apps Script)
 *
 * 설치 방법 (5분)
 * 1. 구글 드라이브에서 새 스프레드시트 생성 (예: "추구미 테스트 상담 DB")
 * 2. 메뉴 [확장 프로그램] → [Apps Script] → 기본 코드를 지우고 이 파일 내용을 그대로 붙여넣기 → 저장
 * 3. 오른쪽 위 [배포] → [새 배포] → 유형 선택(톱니바퀴) [웹 앱]
 *      - 실행 사용자: 나
 *      - 액세스 권한이 있는 사용자: 모든 사용자
 *    → [배포] → 권한 승인 → 표시되는 "웹 앱 URL"(https://script.google.com/macros/s/.../exec) 복사
 * 4. chugumi-test.html 의 CONFIG.submitUrl 에 그 URL 붙여넣기
 *
 * 코드를 수정한 뒤에는 [배포] → [배포 관리] → 연필 아이콘 → 버전 "새 버전" → [배포] 해야 반영됩니다. (URL은 그대로)
 * 신청이 들어오면 알림 메일을 받으려면 아래 NOTIFY_EMAIL 에 주소를 넣으세요. (비워두면 메일 없음)
 */

const SHEET_NAME = '상담신청';
const NOTIFY_EMAIL = '';

const HEADERS = [
  '접수일시', '이름', '나이', '연락처', '상담 메시지', '희망 시간대', '추구미 유형', '성별',
  '개인정보 수집·이용(필수)', '제3자 제공(필수)', '광고 수신(선택)', '동의서 버전',
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
  '유입 경로', '페이지', '답변', '기기', '상담 상태', '메모'
];

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const d = JSON.parse(e.postData.contents);

    // 서버 쪽 검증: 화면 검증을 우회한 요청 차단
    const name = String(d.name || '').trim().slice(0, 20);
    const phone = String(d.phone || '').replace(/\D/g, '');
    if (!name) return json({ ok: false, error: 'name' });
    const age = parseInt(String(d.age || '').replace(/\D/g, ''), 10);
    if (!(age >= 14 && age <= 99)) return json({ ok: false, error: 'age' });
    if (!/^01[016789]\d{7,8}$/.test(phone)) return json({ ok: false, error: 'phone' });
    if (d.consentCollect !== true || d.consentThird !== true) return json({ ok: false, error: 'consent' });

    const sheet = getSheet();
    sheet.appendRow([
      new Date(), safe(name), age, "'" + phone, safe(String(d.message || '').slice(0, 200)), safe(d.time), safe(d.resultName), safe(d.gender),
      'Y', 'Y', d.consentAd === true ? 'Y' : 'N', safe(d.consentVersion),
      safe(d.utm_source), safe(d.utm_medium), safe(d.utm_campaign), safe(d.utm_content), safe(d.utm_term),
      safe(d.referrer), safe(d.page), safe(d.answers), safe(d.userAgent), '신규', ''
    ]);

    if (NOTIFY_EMAIL) {
      MailApp.sendEmail(NOTIFY_EMAIL, '[추구미 테스트] 새 상담 신청 - ' + name,
        '이름: ' + name + ' (' + age + '세)\n연락처: ' + phone + '\n상담 메시지: ' + (d.message || '-') + '\n희망 시간대: ' + (d.time || '-') +
        '\n추구미 유형: ' + (d.resultName || '-') + '\n광고 수신 동의: ' + (d.consentAd ? 'Y' : 'N'));
    }
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: 'server' });
  } finally {
    lock.releaseLock();
  }
}

function getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) sh = ss.insertSheet(SHEET_NAME);
  // 첫 줄 항목명이 없거나 바뀌었으면 최신 항목명으로 맞춤
  const head = sh.getRange(1, 1, 1, HEADERS.length);
  if (head.getValues()[0].join('|') !== HEADERS.join('|')) {
    head.setValues([HEADERS]).setFontWeight('bold').setBackground('#f3ece9');
    sh.setFrozenRows(1);
  }
  return sh;
}

// 엑셀/시트 수식 주입 방지 (=, +, -, @ 로 시작하는 값)
function safe(v) {
  const s = String(v == null ? '' : v).slice(0, 500);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
