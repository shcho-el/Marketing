/**
 * 모델 촬영 스케줄러 — Google Apps Script 웹앱
 *
 * '촬영 슬롯' 탭을 실시간으로 읽고, 웹앱에서 수정한 내용을 같은 행에 다시 기록합니다.
 * 콘티 파일은 Google Drive '촬영 콘티' 폴더에 저장되고, 링크가 시트에 기록됩니다.
 *
 * 기존 열(A~O)은 헤더 이름으로 찾기 때문에 열 순서가 바뀌어도 동작합니다.
 * 수식이 들어 있는 셀(예: 확정 인원, 모델)은 절대 덮어쓰지 않습니다.
 */

const CONFIG = {
  // 연동할 스프레드시트 ID (주소의 /d/ 와 /edit 사이). 테스트할 때는 시트 사본의 ID로 바꾸세요.
  // 비워 두면 이 스크립트가 붙어 있는(바인딩된) 스프레드시트를 사용합니다.
  SPREADSHEET_ID: '1qFVE2hgnAj6nEE_blqUBr18rqrvQtXX6T_W8nQZq1mM',
  SHEET_NAME: '촬영 슬롯',
  MODEL_SHEET_NAME: '모델 정보',
  HEADER_ROW: 1,
  FOLDER_NAME: '촬영 콘티',
  APP_TITLE: '모델 촬영 스케줄',
};

/** 화면 필드 → 시트 헤더 이름 */
const COLS = {
  center: '센터',
  date: '일자',
  time: '시간',
  capacity: '정원',
  use: '사용',
  dirOk: '센터장 확인',
  confirmed: '확정 인원',
  modelAuto: '모델',
  memo: '메모',
  test: '테스트',
  model: '수동 배정 모델',
  status: '수동 상태',
  calendar: '캘린더 등록',
  contact: '연락 방식',
  note: '비고',
  assignee: '작업 담당자',
  links: '콘티 링크',
  files: '콘티 파일',
  id: '고유ID',
};

/** 스케줄러가 시트 오른쪽에 추가하는 열 */
const EXTRA_KEYS = ['assignee', 'links', 'files', 'id'];

/** 웹앱에서 수정 가능한 필드 (확정 인원·모델 자동 열은 제외) */
const WRITABLE = ['center', 'date', 'time', 'capacity', 'use', 'dirOk', 'memo', 'test',
  'model', 'status', 'calendar', 'contact', 'note', 'assignee', 'links', 'files'];

const BOOL_KEYS = ['dirOk', 'test', 'calendar'];

const MODEL_COLS = {
  name: '이름',
  phone: '연락처',
  gender: '성별',
  age: '연령대',
  contact: '선호 연락',
  part: '촬영 부위',
  memo: '메모',
};

const DEFAULT_OPTIONS = {
  centers: ['도수', '롱래스팅', '두피', '발톱'],
  statuses: ['조율 중', '확정', '취소'],
  contacts: ['문자', '메일', '전화', '카톡'],
  uses: ['Y', 'N'],
};

/* ───────────────────────── 메뉴 / 진입점 ───────────────────────── */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('촬영 스케줄러')
    .addItem('초기 설정 (처음 1회)', 'setup')
    .addItem('웹앱 주소 보기', 'showWebAppUrl')
    .addToUi();
}

function doGet(e) {
  // 첫 화면 데이터는 페이지에 바로 넣어서 보냄 (브라우저→서버 호출 없이 즉시 표시)
  let initial = null, initialError = '';
  try { initial = getData(); } catch (err) { initialError = String(err && err.message || err); }
  const boot = JSON.stringify({
    shootId: (e && e.parameter && e.parameter.shoot) || '',
    baseUrl: ScriptApp.getService().getUrl() || '',
    initial: initial,
    initialError: initialError,
  });
  // 데이터는 base64로 감싸 끼워 넣음 (구글 화면 변환 과정에서 글자가 바뀌어 스크립트가 깨지는 문제 방지)
  const bootB64 = Utilities.base64Encode(boot, Utilities.Charset.UTF_8);
  const html = HtmlService.createHtmlOutputFromFile('Index').getContent()
    .replace('__BOOT_B64__', function () { return bootB64; });
  return HtmlService.createHtmlOutput(html)
    .setTitle(CONFIG.APP_TITLE)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * 초기 설정: 추가 열 생성, 고유ID 부여, '모델 정보' 탭과 Drive 폴더 생성.
 * 여러 번 실행해도 안전합니다.
 */
function setup() {
  const ss = getSpreadsheet_();
  PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', ss.getId());
  const sh = getSheet_();
  ensureColumns_(sh);
  readShoots_(); // 고유ID가 없는 행에 ID 부여
  const modelSheet = ensureModelSheet_();
  const folder = getFolder_();

  const msg = '초기 설정 완료\n\n' +
    '· 촬영 슬롯 탭 오른쪽에 [작업 담당자 / 콘티 링크 / 콘티 파일 / 고유ID] 열 확인\n' +
    '· 모델 정보 탭: ' + modelSheet.getName() + '\n' +
    '· 콘티 폴더: ' + folder.getUrl() + '\n\n' +
    '이제 [배포 → 새 배포 → 웹 앱]으로 배포하세요.';
  try { SpreadsheetApp.getUi().alert(msg); } catch (err) { Logger.log(msg); }
}

function showWebAppUrl() {
  const url = ScriptApp.getService().getUrl();
  SpreadsheetApp.getUi().alert(url ? '웹앱 주소\n\n' + url : '아직 배포되지 않았습니다. [배포 → 새 배포 → 웹 앱]을 먼저 진행하세요.');
}

/* ───────────────────────── 클라이언트 API ───────────────────────── */

/** 전체 데이터 */
function getData() {
  const sh = getSheet_();
  const shoots = readShoots_();
  let folderUrl = '';
  try { folderUrl = getFolder_().getUrl(); } catch (err) { /* 권한 없음 */ }
  let user = '';
  try { user = Session.getActiveUser().getEmail(); } catch (err) { /* 무시 */ }
  return {
    shoots: shoots,
    models: readModels_(),
    options: readOptions_(sh, shoots),
    sheetUrl: getSpreadsheet_().getUrl() + '#gid=' + sh.getSheetId(),
    folderUrl: folderUrl,
    user: user,
    fetchedAt: Utilities.formatDate(new Date(), tz_(), 'yyyy-MM-dd HH:mm:ss'),
  };
}

/** 촬영 일정 저장 (id 없으면 새 행 생성). 저장된 행을 반환. */
function saveShoot(input) {
  return withLock_(function () {
    const sh = getSheet_();
    const map = ensureColumns_(sh);
    let row = input.id ? findRowById_(sh, map, input.id) : 0;
    if (input.id && !row) throw new Error('해당 일정을 시트에서 찾을 수 없습니다. 새로고침 후 다시 시도하세요.');
    if (!row) {
      row = prepareNewRow_(sh, map);
      input.id = newId_();
      sh.getRange(row, map.id).setValue(input.id);
    }
    writeRow_(sh, map, row, input);
    SpreadsheetApp.flush();
    return readShootAt_(sh, map, row);
  });
}

/** 촬영 일정 삭제 (시트 행 삭제) */
function deleteShoot(id) {
  return withLock_(function () {
    const sh = getSheet_();
    const map = ensureColumns_(sh);
    const row = findRowById_(sh, map, id);
    if (!row) throw new Error('해당 일정을 찾을 수 없습니다.');
    sh.deleteRow(row);
    return true;
  });
}

/** 콘티 파일 업로드 → Drive 저장 후 시트에 링크 기록 */
function uploadConti(id, name, mimeType, base64) {
  const sh = getSheet_();
  const map = ensureColumns_(sh);
  const before = readShootAt_(sh, map, findRowById_(sh, map, id));
  if (!before) throw new Error('해당 일정을 찾을 수 없습니다.');

  const blob = Utilities.newBlob(Utilities.base64Decode(base64), mimeType || 'application/octet-stream', name);
  const prefix = '[' + before.date + ' ' + before.center + ' ' + before.time + '] ';
  const file = getFolder_().createFile(blob).setName(prefix + name);

  return withLock_(function () {
    const row = findRowById_(sh, map, id);
    const cur = readShootAt_(sh, map, row);
    const files = cur.files.concat([{ name: name, url: file.getUrl(), fileId: file.getId() }]);
    sh.getRange(row, map.files).setValue(serializeFiles_(files));
    SpreadsheetApp.flush();
    return readShootAt_(sh, map, row);
  });
}

/** 콘티 파일 연결 해제 (trash=true면 Drive 휴지통으로 이동) */
function removeConti(id, url, trash) {
  return withLock_(function () {
    const sh = getSheet_();
    const map = ensureColumns_(sh);
    const row = findRowById_(sh, map, id);
    const cur = readShootAt_(sh, map, row);
    if (!cur) throw new Error('해당 일정을 찾을 수 없습니다.');
    const target = cur.files.filter(function (f) { return f.url === url; })[0];
    if (trash && target && target.fileId) {
      try { DriveApp.getFileById(target.fileId).setTrashed(true); } catch (err) { /* 소유자가 아니면 무시 */ }
    }
    const files = cur.files.filter(function (f) { return f.url !== url; });
    sh.getRange(row, map.files).setValue(serializeFiles_(files));
    SpreadsheetApp.flush();
    return readShootAt_(sh, map, row);
  });
}

/** 모델 정보 저장 (originalName이 있으면 해당 모델 수정) */
function saveModel(model, originalName) {
  return withLock_(function () {
    const sh = ensureModelSheet_();
    const map = headerMap_(sh);
    const name = String(model.name || '').trim();
    if (!name) throw new Error('모델 이름을 입력하세요.');
    let row = findModelRow_(sh, map, originalName || name);
    if (!originalName && row) throw new Error('같은 이름의 모델이 이미 있습니다.');
    if (originalName && originalName !== name && findModelRow_(sh, map, name)) throw new Error('같은 이름의 모델이 이미 있습니다.');
    if (!row) row = Math.max(sh.getLastRow(), CONFIG.HEADER_ROW) + 1;
    Object.keys(MODEL_COLS).forEach(function (k) {
      if (map[MODEL_COLS[k]] && model[k] !== undefined) {
        sh.getRange(row, map[MODEL_COLS[k]]).setValue(k === 'name' ? name : model[k]);
      }
    });
    SpreadsheetApp.flush();
    return readModels_();
  });
}

function deleteModel(name) {
  return withLock_(function () {
    const sh = ensureModelSheet_();
    const row = findModelRow_(sh, headerMap_(sh), name);
    if (row) sh.deleteRow(row);
    return readModels_();
  });
}

/* ───────────────────────── 시트 읽기/쓰기 ───────────────────────── */

function getSpreadsheet_() {
  if (CONFIG.SPREADSHEET_ID) return SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  let ss = null;
  try { ss = SpreadsheetApp.getActiveSpreadsheet(); } catch (err) { /* 웹앱 컨텍스트 */ }
  if (ss) return ss;
  const id = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!id) throw new Error('스프레드시트를 찾을 수 없습니다. 시트에서 [촬영 스케줄러 → 초기 설정]을 먼저 실행하세요.');
  return SpreadsheetApp.openById(id);
}

function getSheet_() {
  const sh = getSpreadsheet_().getSheetByName(CONFIG.SHEET_NAME);
  if (!sh) throw new Error("'" + CONFIG.SHEET_NAME + "' 탭을 찾을 수 없습니다.");
  return sh;
}

function tz_() {
  return getSpreadsheet_().getSpreadsheetTimeZone() || Session.getScriptTimeZone();
}

function norm_(v) {
  return String(v == null ? '' : v).replace(/\s+/g, ' ').trim();
}

/** 헤더 이름 → 열 번호(1부터) */
function headerMap_(sh) {
  const lastCol = sh.getLastColumn();
  const map = {};
  if (lastCol < 1) return map;
  const headers = sh.getRange(CONFIG.HEADER_ROW, 1, 1, lastCol).getValues()[0];
  headers.forEach(function (h, i) {
    const key = norm_(h);
    if (key && !map[key]) map[key] = i + 1;
  });
  return map;
}

/** 필드키 → 열 번호. 추가 열이 없으면 생성. */
function ensureColumns_(sh) {
  let byHeader = headerMap_(sh);
  const missing = EXTRA_KEYS.filter(function (k) { return !byHeader[COLS[k]]; });
  if (missing.length) {
    const headers = sh.getRange(CONFIG.HEADER_ROW, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0];
    let lastHeader = 0;
    headers.forEach(function (h, i) { if (norm_(h)) lastHeader = i + 1; });
    const need = lastHeader + missing.length - sh.getMaxColumns();
    if (need > 0) sh.insertColumnsAfter(sh.getMaxColumns(), need);
    missing.forEach(function (k, i) {
      const col = lastHeader + 1 + i;
      const cell = sh.getRange(CONFIG.HEADER_ROW, col);
      if (lastHeader > 0) sh.getRange(CONFIG.HEADER_ROW, lastHeader).copyTo(cell, SpreadsheetApp.CopyPasteType.PASTE_FORMAT, false);
      cell.setValue(COLS[k]);
    });
    SpreadsheetApp.flush();
    byHeader = headerMap_(sh);
  }
  const map = {};
  Object.keys(COLS).forEach(function (k) { if (byHeader[COLS[k]]) map[k] = byHeader[COLS[k]]; });
  if (!map.center || !map.date) throw new Error("'센터', '일자' 헤더를 찾을 수 없습니다. HEADER_ROW 설정을 확인하세요.");
  return map;
}

function readShoots_() {
  const sh = getSheet_();
  const map = ensureColumns_(sh);
  const lastRow = sh.getLastRow();
  if (lastRow <= CONFIG.HEADER_ROW) return [];
  const lastCol = sh.getLastColumn();
  const range = sh.getRange(CONFIG.HEADER_ROW + 1, 1, lastRow - CONFIG.HEADER_ROW, lastCol);
  const values = range.getValues();
  const display = range.getDisplayValues();
  const tz = tz_();
  const out = [];
  const needId = [];

  values.forEach(function (vals, i) {
    const s = rowToShoot_(map, vals, display[i], tz, CONFIG.HEADER_ROW + 1 + i);
    if (!s) return;
    if (!s.id) { s.id = newId_(); needId.push(s); }
    out.push(s);
  });

  if (needId.length) {
    withLock_(function () {
      needId.forEach(function (s) {
        const cell = sh.getRange(s.row, map.id);
        if (!norm_(cell.getValue())) cell.setValue(s.id);
        else s.id = norm_(cell.getValue());
      });
    });
  }
  return out;
}

function readShootAt_(sh, map, row) {
  if (!row) return null;
  const lastCol = sh.getLastColumn();
  const r = sh.getRange(row, 1, 1, lastCol);
  return rowToShoot_(map, r.getValues()[0], r.getDisplayValues()[0], tz_(), row);
}

function rowToShoot_(map, vals, disp, tz, row) {
  const get = function (k) { return map[k] ? vals[map[k] - 1] : ''; };
  const getD = function (k) { return map[k] ? disp[map[k] - 1] : ''; };
  const center = norm_(get('center'));
  const date = fmtDate_(get('date'), getD('date'), tz);
  if (!center && !date) return null;

  const status = norm_(get('status'));
  const modelAuto = norm_(get('modelAuto'));
  const model = norm_(get('model')) || modelAuto.replace(/\s*\(.*\)\s*$/, '');
  const capRaw = get('capacity');

  return {
    id: norm_(get('id')),
    row: row,
    center: center,
    date: date,
    time: fmtTime_(get('time'), getD('time'), tz),
    capacity: capRaw === '' || capRaw == null ? '' : Number(capRaw) || '',
    use: norm_(get('use')),
    dirOk: toBool_(get('dirOk')),
    confirmed: norm_(getD('confirmed')),
    modelAuto: modelAuto,
    model: model,
    status: status,
    memo: String(get('memo') || ''),
    test: toBool_(get('test')),
    calendar: toBool_(get('calendar')),
    contact: norm_(get('contact')),
    note: String(get('note') || ''),
    assignee: norm_(get('assignee')),
    links: parseLinks_(get('links')),
    files: parseFiles_(get('files')),
  };
}

function writeRow_(sh, map, row, input) {
  const lastCol = sh.getLastColumn();
  const formulas = sh.getRange(row, 1, 1, lastCol).getFormulas()[0];
  WRITABLE.forEach(function (k) {
    if (!(k in input) || !map[k]) return;
    if (formulas[map[k] - 1]) return; // 수식 셀 보호
    let v = input[k];
    if (BOOL_KEYS.indexOf(k) >= 0) v = !!v;
    else if (k === 'links') v = serializeLinks_(v || []);
    else if (k === 'files') v = serializeFiles_(v || []);
    else if (k === 'capacity') v = v === '' || v == null ? '' : Number(v);
    else if (k === 'date' && v) v = parseDate_(v);
    else if (k === 'time' && v) v = String(v);
    else v = v == null ? '' : v;
    sh.getRange(row, map[k]).setValue(v);
  });
}

/** 비어 있는 행(센터·일자 모두 빈칸)을 찾거나, 마지막에 새 행을 만들어 반환 */
function prepareNewRow_(sh, map) {
  const lastRow = sh.getLastRow();
  if (lastRow > CONFIG.HEADER_ROW) {
    const n = lastRow - CONFIG.HEADER_ROW;
    const centers = sh.getRange(CONFIG.HEADER_ROW + 1, map.center, n, 1).getValues();
    const dates = sh.getRange(CONFIG.HEADER_ROW + 1, map.date, n, 1).getValues();
    let lastDataIdx = -1;
    for (let i = 0; i < n; i++) if (norm_(centers[i][0]) || norm_(dates[i][0])) lastDataIdx = i;
    // 마지막 데이터 행 바로 아래부터 빈 행 사용 (중간의 빈 행은 건드리지 않음)
    if (lastDataIdx + 1 < n) return CONFIG.HEADER_ROW + 1 + lastDataIdx + 1;
  }
  // 빈 행이 없으면 행을 추가하고 직전 행의 서식·드롭다운·수식을 복사
  const lastCol = sh.getLastColumn();
  sh.insertRowAfter(lastRow);
  const newRow = lastRow + 1;
  if (lastRow > CONFIG.HEADER_ROW) {
    const src = sh.getRange(lastRow, 1, 1, lastCol);
    const dst = sh.getRange(newRow, 1, 1, lastCol);
    src.copyTo(dst, SpreadsheetApp.CopyPasteType.PASTE_FORMAT, false);
    src.copyTo(dst, SpreadsheetApp.CopyPasteType.PASTE_DATA_VALIDATION, false);
    const f = src.getFormulas()[0];
    f.forEach(function (formula, i) {
      if (formula) sh.getRange(lastRow, i + 1).copyTo(sh.getRange(newRow, i + 1));
    });
    // 체크박스 열은 FALSE로 초기화
    BOOL_KEYS.forEach(function (k) { if (map[k] && !f[map[k] - 1]) sh.getRange(newRow, map[k]).setValue(false); });
  }
  return newRow;
}

function findRowById_(sh, map, id) {
  if (!id) return 0;
  const lastRow = sh.getLastRow();
  if (lastRow <= CONFIG.HEADER_ROW) return 0;
  const ids = sh.getRange(CONFIG.HEADER_ROW + 1, map.id, lastRow - CONFIG.HEADER_ROW, 1).getValues();
  for (let i = 0; i < ids.length; i++) if (norm_(ids[i][0]) === id) return CONFIG.HEADER_ROW + 1 + i;
  return 0;
}

/** 드롭다운(데이터 확인) 목록을 옵션으로 사용, 없으면 기본값 + 기존 값 */
function readOptions_(sh, shoots) {
  const map = ensureColumns_(sh);
  const pick = function (key, defaults, field) {
    let list = [];
    try {
      const dv = sh.getRange(CONFIG.HEADER_ROW + 1, map[key]).getDataValidation();
      if (dv && dv.getCriteriaType() === SpreadsheetApp.DataValidationCriteria.VALUE_IN_LIST) {
        list = dv.getCriteriaValues()[0].map(norm_);
      }
    } catch (err) { /* 무시 */ }
    if (!list.length) list = defaults.slice();
    shoots.forEach(function (s) { const v = s[field]; if (v && list.indexOf(v) < 0) list.push(v); });
    return list.filter(function (v) { return v; });
  };
  return {
    centers: map.center ? pick('center', DEFAULT_OPTIONS.centers, 'center') : DEFAULT_OPTIONS.centers,
    statuses: map.status ? pick('status', DEFAULT_OPTIONS.statuses, 'status') : DEFAULT_OPTIONS.statuses,
    contacts: map.contact ? pick('contact', DEFAULT_OPTIONS.contacts, 'contact') : DEFAULT_OPTIONS.contacts,
    uses: map.use ? pick('use', DEFAULT_OPTIONS.uses, 'use') : DEFAULT_OPTIONS.uses,
  };
}

/* ───────────────────────── 모델 정보 탭 ───────────────────────── */

function ensureModelSheet_() {
  const ss = getSpreadsheet_();
  let sh = ss.getSheetByName(CONFIG.MODEL_SHEET_NAME);
  const headers = Object.keys(MODEL_COLS).map(function (k) { return MODEL_COLS[k]; });
  if (!sh) {
    sh = ss.insertSheet(CONFIG.MODEL_SHEET_NAME);
    sh.getRange(1, 1, 1, headers.length).setValues([headers])
      .setFontWeight('bold').setBackground('#2f4f3a').setFontColor('#ffffff');
    sh.setFrozenRows(1);
    // 촬영 슬롯에 등장하는 모델 이름으로 초기 목록 생성
    const names = [];
    try {
      readShoots_().forEach(function (s) { if (s.model && names.indexOf(s.model) < 0) names.push(s.model); });
    } catch (err) { /* 무시 */ }
    if (names.length) sh.getRange(2, 1, names.length, 1).setValues(names.map(function (n) { return [n]; }));
  } else {
    // 누락된 헤더 보충
    const map = headerMap_(sh);
    let col = sh.getLastColumn();
    headers.forEach(function (h) { if (!map[h]) { col += 1; sh.getRange(1, col).setValue(h); } });
  }
  return sh;
}

function readModels_() {
  const sh = getSpreadsheet_().getSheetByName(CONFIG.MODEL_SHEET_NAME);
  if (!sh || sh.getLastRow() < 2) return [];
  const map = headerMap_(sh);
  const values = sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).getDisplayValues();
  return values.map(function (r) {
    const m = {};
    Object.keys(MODEL_COLS).forEach(function (k) { m[k] = map[MODEL_COLS[k]] ? norm_(r[map[MODEL_COLS[k]] - 1]) : ''; });
    return m;
  }).filter(function (m) { return m.name; });
}

function findModelRow_(sh, map, name) {
  if (!name || !map[MODEL_COLS.name] || sh.getLastRow() < 2) return 0;
  const names = sh.getRange(2, map[MODEL_COLS.name], sh.getLastRow() - 1, 1).getValues();
  for (let i = 0; i < names.length; i++) if (norm_(names[i][0]) === name) return i + 2;
  return 0;
}

/* ───────────────────────── Drive ───────────────────────── */

function getFolder_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('CONTI_FOLDER_ID');
  if (id) {
    try { return DriveApp.getFolderById(id); } catch (err) { /* 삭제됨 → 재생성 */ }
  }
  const it = DriveApp.getFoldersByName(CONFIG.FOLDER_NAME);
  const folder = it.hasNext() ? it.next() : DriveApp.createFolder(CONFIG.FOLDER_NAME);
  props.setProperty('CONTI_FOLDER_ID', folder.getId());
  return folder;
}

/* ───────────────────────── 직렬화 / 유틸 ───────────────────────── */

// 셀 형식: 한 줄에 하나씩 "이름 | URL" (이름 생략 시 URL만)
function parseLinks_(v) {
  return String(v || '').split(/\r?\n/).map(function (line) {
    line = line.trim();
    if (!line) return null;
    const i = line.lastIndexOf(' | ');
    return i >= 0 ? { label: line.slice(0, i).trim(), url: line.slice(i + 3).trim() } : { label: '', url: line };
  }).filter(function (x) { return x && x.url; });
}

function serializeLinks_(links) {
  return links.filter(function (l) { return l && l.url; })
    .map(function (l) { return (l.label ? String(l.label).replace(/\|/g, '/') + ' | ' : '') + String(l.url).trim(); })
    .join('\n');
}

function parseFiles_(v) {
  return parseLinks_(v).map(function (l) {
    const m = l.url.match(/\/d\/([a-zA-Z0-9_-]+)/) || l.url.match(/[?&]id=([a-zA-Z0-9_-]+)/);
    return { name: l.label || '파일', url: l.url, fileId: m ? m[1] : '' };
  });
}

function serializeFiles_(files) {
  return serializeLinks_(files.map(function (f) { return { label: f.name, url: f.url }; }));
}

function fmtDate_(v, disp, tz) {
  if (v instanceof Date && !isNaN(v)) return Utilities.formatDate(v, tz, 'yyyy-MM-dd');
  const s = norm_(disp || v);
  const m = s.match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
  return m ? m[1] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[3]).slice(-2) : s;
}

function fmtTime_(v, disp, tz) {
  if (v instanceof Date && !isNaN(v)) return Utilities.formatDate(v, tz, 'HH:mm');
  const s = norm_(disp || v);
  const m = s.match(/(\d{1,2}):(\d{2})/);
  if (!m) return s;
  let h = Number(m[1]);
  if (/오후|PM/i.test(s) && h < 12) h += 12;
  if (/오전|AM/i.test(s) && h === 12) h = 0;
  return ('0' + h).slice(-2) + ':' + m[2];
}

function parseDate_(s) {
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : s;
}

function toBool_(v) {
  return v === true || String(v).toUpperCase() === 'TRUE';
}

function newId_() {
  return 'S' + Utilities.getUuid().replace(/-/g, '').slice(0, 10);
}

let LOCK_DEPTH_ = 0;
function withLock_(fn) {
  if (LOCK_DEPTH_ > 0) return fn(); // 이미 잠금 보유 중 (중첩 호출)
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  LOCK_DEPTH_++;
  try { return fn(); } finally { LOCK_DEPTH_--; lock.releaseLock(); }
}
