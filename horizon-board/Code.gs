/**
 * 모델 섭외 현황판 — 로그인 없이 링크로 보는 Apps Script 웹앱
 *
 * Claude 대시보드와 같은 화면을 Google 쪽에서 보여줘요.
 *  - 지원 메일(Gmail) + 지원자_목록 시트 + 촬영일정_신청 '응답' 탭을 읽고
 *  - 상태·촬영일·메모는 촬영일정_신청 시트의 '현황' 탭에 저장해요.
 *  - 보기 링크:   …/exec            (누구나 보기만, 연락처는 일부 가림)
 *  - 편집 링크:   …/exec?key=편집키  (상태·촬영일 저장 가능, 연락처 전체 표시)
 *
 * 배포: 배포 > 새 배포 > 웹 앱 > 실행 사용자 "나" > 액세스 권한 "모든 사용자"
 * 처음 한 번: 편집기에서 setup() 실행 → 로그에 나오는 편집 키를 확인하세요.
 */

const CONFIG = {
  TIMEZONE: 'Asia/Seoul',
  APPLICANT_SHEET_ID: '1d0MxWjRMQGoOVBPFIARXe-392ifAaZznXwRT6tOPZHY', // 지원자_목록
  REQUEST_SHEET_ID: '1luIMZPgjJ4MppOR7WYBecm7H6TsqkICR07KIQk4aWTo',   // 촬영일정_신청
  REQUEST_TAB: '응답',
  STATUS_TAB: '현황',
  GMAIL_QUERY: '(인천재활모델지원 OR 발톱모델지원) -from:me',
  GMAIL_MAX: 100,
  CACHE_SECONDS: 60,       // 같은 데이터를 1분 동안은 다시 읽지 않아요
  MASK_PHONE_FOR_VIEWERS: true,
};

const STATUS_HEADER = ['key', '이름', '구분', '지원 항목', '상태', '촬영일', '시간', '메모', '저장 시각'];

/* 기존 상태 옮기기용 데이터는 Seed.gs(저장소에 올리지 않는 파일)의 SEED_ROWS예요. setup()에서 읽어요. */

/* ---------- 화면 ---------- */

function doGet(e) {
  const key = String((e && e.parameter && e.parameter.key) || '');
  const canEdit = !!key && key === editKey_();
  const t = HtmlService.createTemplateFromFile('Board');
  t.boot = { canEdit: canEdit, key: canEdit ? key : '' };
  return t.evaluate()
    .setTitle('모델 섭외 현황')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function editKey_() {
  return PropertiesService.getScriptProperties().getProperty('EDIT_KEY') || '';
}

/* ---------- 데이터 ---------- */

function fmt_(v, pattern) {
  if (v instanceof Date) return Utilities.formatDate(v, CONFIG.TIMEZONE, pattern || 'yyyy-MM-dd HH:mm');
  return String(v == null ? '' : v).trim();
}

function table_(sheet) {
  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return [];
  const header = values[0].map(function (h) { return String(h).trim(); });
  return values.slice(1).map(function (r) {
    const o = {};
    header.forEach(function (h, i) { if (h) o[h] = r[i]; });
    return o;
  });
}

/** 지원 메일 → 행 (대시보드의 mails와 같은 규칙) */
function readMails_() {
  const threads = GmailApp.search(CONFIG.GMAIL_QUERY, 0, CONFIG.GMAIL_MAX);
  return threads.map(function (t) {
    const m = t.getMessages()[0];
    const subject = m.getSubject() || '';
    const fromName = (m.getFrom().match(/^\s*"?([^"<]+?)"?\s*</) || [])[1] || '';
    const f = /([^\s\[\]()_]+)_([남여])_(\d{1,2})_(01\d[-\s]?\d{3,4}[-\s]?\d{4})/.exec(subject);
    const phone = f ? f[4] : ((/01\d[-\s]{0,3}\d{3,4}[-\s]{0,3}\d{4}/.exec(subject) || [''])[0]).replace(/\s+/g, '');
    const ageM = /(\d{2})\s*세/.exec(subject);
    const gender = f ? f[2] : ((/[(_\s](여|남)[)_\s]/.exec(subject) || [])[1] || '');
    return {
      key: t.getId(),
      '이름': f ? f[1] : fromName.trim(),
      '성별': gender,
      '나이': f ? Number(f[3]) : (ageM ? Number(ageM[1]) : null),
      '연락처': phone,
      '지원 항목': /발톱/.test(subject) ? '발톱' : '재활',
      '지원일': Utilities.formatDate(m.getDate(), CONFIG.TIMEZONE, 'yyyy-MM-dd'),
      '지원 메일': 'https://mail.google.com/mail/#all/' + t.getId(),
      '메일 제목': subject,
      '수신 시각': m.getDate().toISOString(),
    };
  }).filter(function (r) { return r['이름']; });
}

/** 지원자_목록 시트 → 행 (대시보드의 applicants와 같은 규칙) */
function readApplicants_() {
  const sh = SpreadsheetApp.openById(CONFIG.APPLICANT_SHEET_ID).getSheets()[0];
  const keep = {
    '지원 항목': '지원 항목', '이름': '이름', '성별': '성별', '나이': '나이', '연락처': '연락처',
    '촬영 가능 일자': '촬영 가능 일자', 'SNS': 'SNS', '지원일': '지원일', '폴더 링크': '폴더 링크',
    '지원 메일': '지원 메일', '대용량 첨부(만료일)': '자료 만료', '비고': '비고', '구분': '구분',
  };
  return table_(sh).map(function (r) {
    const o = {};
    Object.keys(keep).forEach(function (h) { if (h in r) o[keep[h]] = fmt_(r[h], 'yyyy-MM-dd'); });
    const m = /#all\/([0-9a-zA-Z]+)/.exec(o['지원 메일'] || '');
    o.key = m ? m[1] : (o['이름'] || '');
    o['나이'] = o['나이'] === '' || isNaN(Number(o['나이'])) ? null : Number(o['나이']);
    return o;
  }).filter(function (o) { return o['이름']; });
}

/** 촬영일정_신청 '응답' 탭 → 행 (대시보드의 requests와 같은 규칙, 민감 정보는 빼요) */
function readRequests_() {
  const sh = SpreadsheetApp.openById(CONFIG.REQUEST_SHEET_ID).getSheetByName(CONFIG.REQUEST_TAB);
  if (!sh) return [];
  return table_(sh).map(function (r) {
    const o = {
      '접수 시각': fmt_(r['접수 시각']), '지원 항목': fmt_(r['지원 항목']), '본명': fmt_(r['본명']),
      '전화번호': fmt_(r['전화번호']), '희망 1순위': fmt_(r['희망 1순위']),
      '희망 2순위': fmt_(r['희망 2순위']), '희망 3순위': fmt_(r['희망 3순위']),
    };
    o.key = 'req' + o['전화번호'].replace(/\D/g, '');
    return o;
  }).filter(function (o) { return o['본명']; });
}

/** '현황' 탭 → 대시보드의 schedule과 같은 모양 */
function readStatus_() {
  return table_(statusSheet_()).map(function (r) {
    return {
      id: fmt_(r.key), source: fmt_(r['구분']), type: fmt_(r['지원 항목']), status: fmt_(r['상태']),
      date: fmt_(r['촬영일'], 'yyyy-MM-dd'), time: fmt_(r['시간'], 'HH:mm'), memo: fmt_(r['메모']),
      updatedAt: fmt_(r['저장 시각']),
    };
  }).filter(function (s) { return s.id; });
}

function statusSheet_() {
  const ss = SpreadsheetApp.openById(CONFIG.REQUEST_SHEET_ID);
  let sh = ss.getSheetByName(CONFIG.STATUS_TAB);
  if (!sh) {
    sh = ss.insertSheet(CONFIG.STATUS_TAB); // 맨 뒤에 만들어요 ('응답' 탭이 첫 번째로 남아야 해요)
    sh.appendRow(STATUS_HEADER);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, STATUS_HEADER.length).setFontWeight('bold');
    sh.getRange('F:G').setNumberFormat('@'); // 날짜·시간을 글자 그대로 저장
  }
  return sh;
}

function maskPhone_(p) {
  const d = String(p || '').replace(/\D/g, '');
  if (d.length < 8) return p ? '***' : '';
  return d.slice(0, 3) + '-****-' + d.slice(-4);
}

/** 화면이 5분마다 부르는 함수: 네 가지 데이터를 한 번에 돌려줘요 */
function getRaw(key) {
  const canEdit = !!key && key === editKey_();
  const cache = CacheService.getScriptCache();
  const cached = cache.get('raw');
  let raw;
  if (cached) {
    raw = JSON.parse(cached);
  } else {
    raw = { mails: [], applicants: [], requests: [], schedule: [], errors: [], at: new Date().toISOString() };
    [['mails', readMails_], ['applicants', readApplicants_], ['requests', readRequests_], ['schedule', readStatus_]]
      .forEach(function (p) {
        try { raw[p[0]] = p[1](); } catch (err) { raw.errors.push(p[0] + ': ' + err.message); }
      });
    try { cache.put('raw', JSON.stringify(raw), CONFIG.CACHE_SECONDS); } catch (err) { /* 너무 크면 캐시 생략 */ }
  }
  if (!canEdit && CONFIG.MASK_PHONE_FOR_VIEWERS) {
    raw.mails.forEach(function (r) { r['연락처'] = maskPhone_(r['연락처']); r['메일 제목'] = ''; });
    raw.applicants.forEach(function (r) { r['연락처'] = maskPhone_(r['연락처']); });
    raw.requests.forEach(function (r) { r['전화번호'] = maskPhone_(r['전화번호']); });
  }
  raw.canEdit = canEdit;
  return raw;
}

/* ---------- 저장 (편집 링크로 연 사람만) ---------- */

function saveStatus(key, id, obj) {
  if (!key || key !== editKey_()) throw new Error('편집 링크로 열어야 저장할 수 있어요.');
  id = String(id || '').replace(/[^0-9A-Za-z]/g, '');
  if (!id) throw new Error('지원자를 먼저 골라 주세요.');
  const clean = function (v, n) { return String(v == null ? '' : v).replace(/[\u0000-\u0009\u000b-\u001f]/g, ' ').trim().slice(0, n || 100); };
  const row = [
    id, clean(obj.name, 30),
    ['자체 지원', '인플루언서'].indexOf(obj.source) >= 0 ? obj.source : '자체 지원',
    ['재활', '발톱', '재활+발톱'].indexOf(obj.type) >= 0 ? obj.type : '재활',
    ['검토 대기', '연락 중', '희망 일정', '일정 확정', '촬영 완료', '보류', '미선정'].indexOf(obj.status) >= 0 ? obj.status : '검토 대기',
    /^\d{4}-\d{2}-\d{2}$/.test(obj.date || '') ? obj.date : '',
    /^\d{2}:\d{2}$/.test(obj.time || '') ? obj.time : '',
    clean(obj.memo, 500),
    new Date().toISOString(),
  ];
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const sh = statusSheet_();
    const last = sh.getLastRow();
    const ids = last > 1 ? sh.getRange(2, 1, last - 1, 1).getValues().map(function (r) { return String(r[0]); }) : [];
    const i = ids.indexOf(id);
    if (i >= 0) sh.getRange(i + 2, 1, 1, row.length).setValues([row]);
    else sh.appendRow(row);
  } finally {
    lock.releaseLock();
  }
  CacheService.getScriptCache().remove('raw');
  return { ok: true };
}

/* ---------- 처음 설정 ---------- */

function setup() {
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('EDIT_KEY')) props.setProperty('EDIT_KEY', Utilities.getUuid().replace(/-/g, '').slice(0, 20));
  const sh = statusSheet_();
  const seed = (typeof SEED_ROWS !== 'undefined') ? SEED_ROWS : [];
  if (sh.getLastRow() < 2 && seed.length) {
    sh.getRange(2, 1, seed.length, STATUS_HEADER.length).setValues(seed);
  }
  getRaw(editKey_()); // 권한 승인용으로 한 번 읽어봐요
  const url = ScriptApp.getService().getUrl();
  Logger.log('편집 키: ' + editKey_());
  if (url) {
    Logger.log('보기 링크: ' + url);
    Logger.log('편집 링크: ' + url + '?key=' + editKey_());
  } else {
    Logger.log('배포한 뒤 다시 setup()을 실행하면 보기·편집 링크가 나와요.');
  }
}
