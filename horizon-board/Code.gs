/**
 * 모델 섭외 현황판 — 로그인 없이 링크로 보는 Apps Script 웹앱
 *
 * Claude 대시보드와 같은 화면을 Google 쪽에서 보여줘요.
 *  - 지원 메일(Gmail) + 지원자_목록 시트 + 촬영일정_신청 '응답' 탭을 읽고
 *  - 상태·촬영일·메모는 촬영일정_신청 시트의 '현황' 탭에 저장해요.
 *  - 보기 링크:   …/exec            (누구나 보기만, 연락처도 보여요)
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
  MASK_PHONE_FOR_VIEWERS: false, // true로 바꾸면 보기 링크에서 연락처를 010-****-1234처럼 가려요
};

const STATUS_HEADER = ['key', '이름', '구분', '지원 항목', '상태', '촬영일', '시간', '메모', '저장 시각'];

/* 기존 상태 옮기기용 데이터는 Seed.gs(저장소에 올리지 않는 파일)의 SEED_ROWS예요. setup()에서 읽어요. */

/* ---------- 화면 ---------- */

function doGet(e) {
  const key = String((e && e.parameter && e.parameter.key) || '');
  const canEdit = !!key && key === editKey_();
  // Claude 대시보드의 '저장' 버튼이 여는 주소: …/exec?key=…&save=1&id=…&status=…
  if (canEdit && e.parameter.save === '1') return saveFromLink_(key, e.parameter);
  const t = HtmlService.createTemplateFromFile('Board');
  t.boot = { canEdit: canEdit, key: canEdit ? key : '' };
  return t.evaluate()
    .setTitle('모델 섭외 현황')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function saveFromLink_(key, p) {
  let ok = true, msg = '';
  try {
    saveStatus(key, p.id, {
      name: p.name, source: p.source, type: p.type, status: p.status,
      date: p.date, time: p.time, memo: p.memo,
    });
  } catch (err) { ok = false; msg = err.message; }
  const esc = function (s) { return String(s || '').replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); };
  const when = [p.date, p.time].filter(String).join(' ');
  const html = '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<div style="font-family:Pretendard,system-ui,sans-serif;max-width:420px;margin:60px auto;padding:24px;border-radius:14px;' +
    'border:1px solid #e3ddd8;text-align:center;color:#2b2724">' +
    (ok
      ? '<div style="font-size:40px">✓</div><h2 style="margin:8px 0">현황판에 저장했어요</h2>' +
        '<p style="color:#6b625c">' + esc(p.name) + ' · ' + esc(p.status) + (when ? ' · ' + esc(when) : '') + '</p>' +
        '<p style="color:#6b625c;font-size:14px">이 창은 닫아도 돼요. Claude 대시보드에는 1~2분 안에 반영돼요.</p>'
      : '<h2 style="margin:8px 0;color:#b83a55">저장하지 못했어요</h2><p>' + esc(msg) + '</p>') +
    '</div>';
  return HtmlService.createHtmlOutput(html).setTitle(ok ? '저장 완료' : '저장 실패');
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
      '지원 항목': typeOfThread_(t),
      '지원일': Utilities.formatDate(m.getDate(), CONFIG.TIMEZONE, 'yyyy-MM-dd'),
      '지원 메일': 'https://mail.google.com/mail/#all/' + t.getId(),
      '메일 제목': subject,
      '수신 시각': m.getDate().toISOString(),
    };
  }).filter(function (r) { return r['이름']; });
}

/** 스레드 안의 지원자 메일 제목을 모두 보고 재활 / 발톱 / 재활+발톱을 정해요 (같은 메일에 발톱으로 다시 지원한 경우 포함) */
function typeOfThread_(t) {
  const me = Session.getEffectiveUser().getEmail();
  const subjects = t.getMessages().filter(function (m) { return m.getFrom().indexOf(me) < 0; })
    .map(function (m) { return m.getSubject() || ''; });
  const hasFoot = subjects.some(function (s) { return /발톱/.test(s); });
  const hasRehab = subjects.some(function (s) { return /재활/.test(s); });
  return hasFoot && hasRehab ? '재활+발톱' : (hasFoot ? '발톱' : '재활');
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

/* ---------- 이름 바로잡기 ---------- */

/** 지원자_목록 시트와 '현황' 탭에서 이름을 한 번에 바꿔요. 아래 fixName()을 고쳐서 실행하세요. */
function renameApplicant_(oldName, newName) {
  let changed = 0;
  const swap = function (sheet, header) {
    const values = sheet.getDataRange().getValues();
    const col = values[0].map(function (h) { return String(h).trim(); }).indexOf(header);
    if (col < 0) return;
    for (let r = 1; r < values.length; r++) {
      if (String(values[r][col]).trim() === oldName) { sheet.getRange(r + 1, col + 1).setValue(newName); changed++; }
    }
  };
  swap(SpreadsheetApp.openById(CONFIG.APPLICANT_SHEET_ID).getSheets()[0], '이름');
  swap(statusSheet_(), '이름');
  CacheService.getScriptCache().remove('raw');
  Logger.log(oldName + ' → ' + newName + ': ' + changed + '칸 바꿨어요.');
}

function fixName() {
  renameApplicant_('차예지', '박예지');
}

/* ---------- 지원 메일 → Drive 폴더 자동 정리 (30분마다) ---------- */

const FOLDER_CONFIG = {
  PARENT_FOLDER_ID: '1MRnHEcA1A8OPkJGDwD37jx_rkVYZ9GNo', // 인천재활모델지원
  LOOKBACK: 'newer_than:30d',
  MAX_DOWNLOAD_MB: 45,   // 대용량 첨부(네이버·다음 링크)는 이 크기까지 직접 받아 넣어요
};

/** 처음 한 번 실행: 30분마다 autoFolder가 돌도록 등록해요 (이미 있으면 다시 만들지 않아요) */
function installAutoFolder() {
  ScriptApp.getProjectTriggers().forEach(function (tr) {
    if (tr.getHandlerFunction() === 'autoFolder') ScriptApp.deleteTrigger(tr);
  });
  ScriptApp.newTrigger('autoFolder').timeBased().everyMinutes(30).create();
  autoFolder();
  Logger.log('30분마다 자동 폴더 정리를 등록했어요.');
}

function autoFolder() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return;
  try {
    const me = Session.getEffectiveUser().getEmail();
    const props = PropertiesService.getScriptProperties();
    const done = JSON.parse(props.getProperty('FOLDERED') || '{}');
    const parent = DriveApp.getFolderById(FOLDER_CONFIG.PARENT_FOLDER_ID);
    const aliases = phoneAliases_();
    const log = [];
    const threads = GmailApp.search(CONFIG.GMAIL_QUERY + ' ' + FOLDER_CONFIG.LOOKBACK, 0, 50);
    threads.forEach(function (t) {
      t.getMessages().forEach(function (m) {
        if (done[m.getId()] || m.getFrom().indexOf(me) >= 0) return;
        const info = parseApplicant_(m);
        if (!info) return;
        const folder = findOrCreateFolder_(parent, info, aliases);
        const saved = saveMailFiles_(folder, m, info.name);
        done[m.getId()] = Date.now();
        log.push(info.name + ' → ' + folder.getName() + ' (' + saved + ')');
      });
    });
    // 오래된 기록은 정리 (60일)
    const cutoff = Date.now() - 60 * 24 * 3600 * 1000;
    Object.keys(done).forEach(function (k) { if (done[k] < cutoff) delete done[k]; });
    props.setProperty('FOLDERED', JSON.stringify(done));
    try { registerApplicants_(threads, parent, aliases, me).forEach(function (s) { log.push(s); }); }
    catch (e) { Logger.log('지원자_목록 등록 실패: ' + e); }
    if (log.length) { CacheService.getScriptCache().remove('raw'); Logger.log(log.join('\n')); }
  } finally {
    lock.releaseLock();
  }
}

function parseApplicant_(m) {
  const subject = m.getSubject() || '';
  const f = /([^\s\[\]()_]+)_([남여])_(\d{1,2})_(01\d[-\s]?\d{3,4}[-\s]?\d{4})/.exec(subject);
  const fromName = ((m.getFrom().match(/^\s*"?([^"<]+?)"?\s*</) || [])[1] || '').trim();
  const name = f ? f[1] : fromName;
  if (!name) return null;
  const phone = (f ? f[4] : ((/01\d[-\s]{0,3}\d{3,4}[-\s]{0,3}\d{4}/.exec(subject) || [''])[0])).replace(/\D/g, '');
  const ageM = /(\d{2})\s*세/.exec(subject);
  return {
    name: name, phone: phone,
    gender: f ? f[2] : ((/[(_\s](여|남)[)_\s]/.exec(subject) || [])[1] || ''),
    age: f ? f[3] : (ageM ? ageM[1] : ''),
    type: /발톱/.test(subject) ? '발톱' : '재활',
  };
}

/** 전화번호 → 이 사람이 쓴 이름들 (신청서의 본명·활동명, 지원자_목록 이름) */
function phoneAliases_() {
  const out = {};
  const add = function (p, n) {
    const d = String(p || '').replace(/\D/g, ''); n = String(n || '').trim();
    if (!d || !n) return;
    (out[d] = out[d] || []).indexOf(n) < 0 && out[d].push(n);
  };
  try {
    const sh = SpreadsheetApp.openById(CONFIG.REQUEST_SHEET_ID).getSheetByName(CONFIG.REQUEST_TAB);
    if (sh) table_(sh).forEach(function (r) { add(r['전화번호'], r['본명']); add(r['전화번호'], r['활동명']); });
  } catch (e) { /* 없으면 건너뜀 */ }
  try {
    table_(SpreadsheetApp.openById(CONFIG.APPLICANT_SHEET_ID).getSheets()[0])
      .forEach(function (r) { add(r['연락처'], r['이름']); });
  } catch (e) { /* 없으면 건너뜀 */ }
  return out;
}

/** 이미 있는 지원자 폴더(이름이 같거나, 같은 전화번호로 쓴 다른 이름)를 찾고, 없으면 만들어요 */
function findOrCreateFolder_(parent, info, aliases) {
  const norm = function (s) { return String(s || '').replace(/\s+/g, ''); };
  const wants = [info.name].concat(aliases[info.phone] || []).map(norm);
  const it = parent.getFolders();
  while (it.hasNext()) {
    const f = it.next();
    if (!f.isTrashed() && wants.indexOf(norm(f.getName().split('_')[1])) >= 0) return f;
  }
  const parts = [info.type, info.name, info.gender, info.age].filter(String);
  return parent.createFolder(parts.join('_'));
}

function hasFile_(folder, name) {
  const it = folder.getFilesByName(name);
  while (it.hasNext()) { if (!it.next().isTrashed()) return true; }
  return false;
}

/** 메일 첨부(본문 사진 포함)와 대용량 첨부 링크 파일을 폴더에 넣어요. 같은 이름 파일이 있으면 건너뛰어요. */
function saveMailFiles_(folder, m, name) {
  let n = 0;
  m.getAttachments({ includeInlineImages: true, includeAttachments: true }).forEach(function (a) {
    // 이름 없는 HTML 조각(메일 본문 사본)은 지원 자료가 아니라서 건너뛰어요
    if (!a.getName() && /html|plain/.test(a.getContentType() || '')) return;
    const fname = a.getName() || ('첨부_' + (n + 1));
    if (hasFile_(folder, fname)) return;
    folder.createFile(a.copyBlob().setName(fname));
    n++;
  });
  const html = m.getBody();
  const links = [];
  const re = /href="(https:\/\/(?:bigfile\.mail\.naver\.com\/download\?fid=|attach\.mail\.daum\.net\/bigfile\/)[^"]+)"[^>]*?(?:title="([^"]+?)\s*")?/g;
  let mm;
  while ((mm = re.exec(html))) {
    const url = mm[1].replace(/&amp;/g, '&');
    if (links.some(function (l) { return l.url === url; })) continue;
    links.push({ url: url, title: (mm[2] || '').replace(/&amp;/g, '&').replace(/\s*다운로드$/, '').trim() });
  }
  const failed = [];
  links.forEach(function (l) {
    if (l.title && hasFile_(folder, l.title)) return;
    try {
      const res = UrlFetchApp.fetch(l.url, { muteHttpExceptions: true, followRedirects: true });
      const blob = res.getBlob();
      if (res.getResponseCode() !== 200 || blob.getBytes().length > FOLDER_CONFIG.MAX_DOWNLOAD_MB * 1024 * 1024) throw new Error('size');
      const cd = String((res.getAllHeaders() || {})['Content-Disposition'] || '');
      const fromHeader = decodeURIComponent(((cd.match(/filename\*=UTF-8''([^;]+)/i) || [])[1]) || '') ||
        ((cd.match(/filename="?([^";]+)"?/i) || [])[1] || '');
      const fname = l.title || fromHeader || ('대용량첨부_' + (n + 1));
      if (hasFile_(folder, fname)) return;
      folder.createFile(blob.setName(fname));
      n++;
    } catch (e) {
      failed.push((l.title || '대용량 첨부') + '\n' + l.url);
    }
  });
  if (failed.length) {
    const doc = '대용량첨부_다운로드링크_' + name + '.txt';
    if (!hasFile_(folder, doc)) {
      folder.createFile(doc, '자동으로 받지 못한 대용량 첨부예요. 링크로 받아 이 폴더에 올려 주세요.\n\n' + failed.join('\n\n'), MimeType.PLAIN_TEXT);
    }
  }
  return n + '개 저장' + (failed.length ? ', 링크 ' + failed.length + '개' : '');
}


/* ---------- 새 지원자 → 지원자_목록 시트 자동 등록 ---------- */

/** 시트에 없는 지원자(메일 ID·연락처 둘 다 없음)를 한 줄 추가해요. 이미 있는 사람이 다른 항목으로 또 지원하면 지원 항목을 재활+발톱으로 바꿔요. */
function registerApplicants_(threads, parent, aliases, me) {
  const sh = SpreadsheetApp.openById(CONFIG.APPLICANT_SHEET_ID).getSheets()[0];
  const values = sh.getDataRange().getValues();
  const header = values[0].map(function (x) { return String(x).trim(); });
  const col = function (name) { return header.indexOf(name); };
  const digits = function (v) { return String(v || '').replace(/\D/g, ''); };
  const rows = values.slice(1);
  const out = [];
  threads.slice().reverse().forEach(function (t) {
    const msgs = t.getMessages().filter(function (m) { return m.getFrom().indexOf(me) < 0; });
    if (!msgs.length) return;
    const m = msgs[0];
    const info = parseApplicant_(m);
    if (!info) return;
    const type = typeOfThread_(t);
    const tid = t.getId();
    const iMail = col('지원 메일'), iPhone = col('연락처'), iType = col('지원 항목');
    const at = rows.findIndex(function (r) {
      return (iMail >= 0 && String(r[iMail]).indexOf(tid) >= 0) ||
        (info.phone && iPhone >= 0 && digits(r[iPhone]) === info.phone);
    });
    if (at >= 0) {
      const cur = iType >= 0 ? String(rows[at][iType] || '') : '';
      const both = /재활/.test(cur + type) && /발톱/.test(cur + type);
      if (iType >= 0 && both && cur !== '재활+발톱') {
        sh.getRange(at + 2, iType + 1).setValue('재활+발톱');
        rows[at][iType] = '재활+발톱';
        out.push(info.name + ': 지원 항목을 재활+발톱으로 바꿨어요');
      }
      return;
    }
    const folder = findOrCreateFolder_(parent, info, aliases);
    const body = m.getPlainBody() || '';
    const files = m.getAttachments({ includeInlineImages: false }).map(function (a) { return a.getName(); }).filter(String);
    const big = (m.getBody().match(/title="([^"]+?)\s*다운로드"/g) || [])
      .map(function (s) { return s.replace(/^title="|\s*다운로드"$/g, ''); });
    const d = m.getDate();
    const rec = {
      '지원 항목': type, '이름': info.name, '성별': info.gender, '나이': info.age,
      '연락처': info.phone.replace(/^(\d{3})(\d{3,4})(\d{4})$/, '$1-$2-$3'),
      '촬영 가능 일자': pickLine_(body, /(촬영\s*가능|가능\s*(한\s*)?(일자|날짜|일정|요일|시간))/) || '[미기재]',
      'SNS': pickSns_(body),
      '거주지': pickLine_(body, /(거주지|사는\s*곳|거주\s*지역|주소)/) || '[미기재]',
      '통증·체형 고민': pickLine_(body, /(통증|체형|고민|불편)/) || '[미기재]',
      '키/몸무게': pickBody_(body),
      '지원일': Utilities.formatDate(d, 'Asia/Seoul', 'yyyy-MM-dd'),
      '폴더 링크': folder.getUrl(),
      '지원 메일': 'https:' + '//mail.google.com/mail/#all/' + tid,
      '메일 첨부파일': files.join(', ') || '없음',
      '대용량 첨부(만료일)': big.join(', ') || '없음',
      '비고': '자동 등록 · 내용 확인 필요',
    };
    const row = header.map(function (hd) { return hd in rec ? rec[hd] : ''; });
    sh.appendRow(row);
    const last = sh.getLastRow();
    if (iPhone >= 0) sh.getRange(last, iPhone + 1).setNumberFormat('@').setValue(rec['연락처']);
    rows.push(row);
    out.push(info.name + ': 지원자_목록에 추가했어요');
  });
  return out;
}

/** 본문에서 "항목: 값" 형태의 줄을 찾아 값만 돌려줘요 (최대 80자) */
function pickLine_(body, re) {
  const lines = body.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    if (!re.test(l) || !/[:：]/.test(l)) continue;
    let v = l.split(/[:：]/).slice(1).join(':').trim();
    if (!v && /[:：]\s*$/.test(l) && lines[i + 1]) v = lines[i + 1].trim();
    v = v.replace(/^[-–·•\s]+/, '');
    if (v) return v.slice(0, 80);
  }
  return '';
}

function pickSns_(body) {
  const url = /https?:\/\/(?:www\.)?(?:instagram\.com|instagr\.am)\/[^\s)>\]"'<]+/i.exec(body);
  if (url) return url[0];
  const handle = /(?:인스타(?:그램)?|instagram|insta)[^\n@]{0,15}@?\s*([A-Za-z0-9._]{3,30})/i.exec(body);
  if (handle && !/^(com|www|http)/i.test(handle[1])) return 'https:' + '//www.instagram.com/' + handle[1] + '/';
  const other = /https?:\/\/(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|blog\.naver\.com)\/[^\s)>\]"'<]+/i.exec(body);
  return other ? other[0] : '';
}

function pickBody_(body) {
  const m = /(1[4-9]\d)(?:\.\d)?\s*(?:cm)?\s*[\/,·\s]+\s*(\d{2})(?:\.\d)?\s*kg/i.exec(body);
  return m ? m[1] + '/' + m[2] : '';
}

/** 지금 바로 한 번 등록해 보고 싶을 때 실행하세요 (자동 정리와 같은 일을 해요) */
function registerNow() { autoFolder(); }
