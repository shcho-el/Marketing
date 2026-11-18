/**
 * 모델 촬영 — 촬영 일정 신청
 *
 * 기존 촬영 일정 신청 페이지와 별개인 새 Apps Script 프로젝트예요.
 *
 * 흐름
 *  1) 담당자가 '초대' 탭에 선정된 모델(이름·연락처·이메일·지원 항목)을 적고 makeInviteLinks()를 실행
 *     → 사람마다 개인 신청 링크가 만들어져요.
 *  2) 모델이 링크로 들어와 기본 정보·주소를 확인하고, 수·목 중 희망 일정을 최대 3개 고르고,
 *     신분증·통장 사본을 첨부해 신청해요. (한 번만 신청 가능)
 *  3) '응답' 탭에 한 줄로 기록되고, 서류는 지원자 폴더 안 '계약서류' 폴더에 저장되며, 담당자에게 메일이 가요.
 *
 * 배포: 배포 > 새 배포 > 유형 "웹 앱" > 실행 사용자 "나" > 액세스 권한 "모든 사용자"
 */

const CONFIG = {
  // 지원자 폴더들이 있는 상위 폴더 (Drive: 모델/인플루언서 > 인천재활모델지원)
  PARENT_FOLDER_ID: '1MRnHEcA1A8OPkJGDwD37jx_rkVYZ9GNo',
  // 응답·초대 시트. 비워 두면 setup() 실행 때 위 폴더에 '촬영일정_신청' 시트를 만들어요.
  SHEET_ID: '',

  TIMEZONE: 'Asia/Seoul',
  WEEKS_AHEAD: 6,              // 내일부터 몇 주 뒤까지 보여줄지
  SHOOT_WEEKDAYS: [3, 4],      // 0=일 … 3=수, 4=목
  TIMES: ['11:00', '14:00', '15:00', '16:00', '17:00'], // 오전 10시는 모든 날짜에서 닫음
  // 요일마다 빼는 시간 (3=수, 4=목). 수요일 15~16시, 목요일 16~17시는 촬영 불가
  EXCLUDE_BY_WEEKDAY: { 3: ['15:00'], 4: ['16:00'] },
  // 특정 날짜만 따로 정한 시간 (이 날은 위 규칙 대신 여기 적은 시간만 열려요)
  DATE_TIMES: { '2026-11-19': ['14:00'] },
  // 특정 날짜에서만 빼는 시간 (요일 규칙은 그대로 두고 이 시간만 닫아요)
  EXCLUDE_BY_DATE: {}, // 예: { '2026-12-10': ['11:00'] }
  MAX_PER_SLOT: 1,             // 한 시간대에 1순위로 받을 인원. 넘으면 '마감'
  BLOCKED_DATES: [],           // 촬영 없는 날 'yyyy-MM-dd'
  MAX_PICKS: 3,

  // 지원 항목별 장소 안내
  PLACES: {
    '재활': '인천대입구역 근처 재활치료의원',
    '발톱': '인천대입구역 근처 발톱치료의원',
    '': '인천대입구역 근처 발톱치료의원 또는 재활치료의원',
  },
  // 일정 변경·문의 담당자 (비우면 화면에서 숨겨요)
  CONTACT: { name: '조소희 책임', phone: '010-2791-2736', email: 'sh.cho@medibuilder.com' },

  ALLOW_WITHOUT_LINK: true,    // true면 개인 링크 없이 /exec 주소 하나로 신청 가능 (같은 전화번호는 한 번만)
  MAX_FILE_MB: 10,
  NOTIFY_EMAIL: '',            // 비우면 스크립트 소유자에게, 'off'면 안 보냄
};

const RESP_HEADER = [
  '접수 시각', '초대 코드', '지원 항목', '본명', '활동명', '전화번호', '이메일', '생년월일',
  '주소', '상세 주소', '희망 1순위', '희망 2순위', '희망 3순위',
  '신분증 사본', '통장 사본', '서류 폴더', '개인정보 동의', '고유식별정보 동의',
];
const INVITE_HEADER = ['초대 코드', '이름', '전화번호', '이메일', '지원 항목', '신청 링크', '신청 상태'];

/* ---------- 화면 ---------- */

function doGet(e) {
  const code = String((e && e.parameter && e.parameter.t) || '').trim();
  const inv = code ? findInvite_(code) : null;
  const t = HtmlService.createTemplateFromFile('Index');
  t.data = {
    code: inv ? code : '',
    linkInvalid: !!code && !inv,
    needLink: !CONFIG.ALLOW_WITHOUT_LINK && !inv,
    submitted: inv ? !!inv.status : false,
    name: inv ? inv.name : '',
    phone: inv ? inv.phone : '',
    email: inv ? inv.email : '',
    type: inv ? inv.type : '',
    places: CONFIG.PLACES,
    contact: CONFIG.CONTACT,
    maxPicks: CONFIG.MAX_PICKS,
    maxFileMb: CONFIG.MAX_FILE_MB,
  };
  return t.evaluate()
    .setTitle('촬영 일정 신청')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/* ---------- 시트 ---------- */

function book_() {
  const props = PropertiesService.getScriptProperties();
  const id = CONFIG.SHEET_ID || props.getProperty('SHEET_ID');
  if (id) return SpreadsheetApp.openById(id);
  const ss = SpreadsheetApp.create('촬영일정_신청');
  DriveApp.getFileById(ss.getId()).moveTo(DriveApp.getFolderById(CONFIG.PARENT_FOLDER_ID));
  props.setProperty('SHEET_ID', ss.getId());
  return ss;
}

function tab_(name, header) {
  const ss = book_();
  let sh = ss.getSheetByName(name);
  if (!sh) {
    const sheets = ss.getSheets();
    const first = sheets[0];
    const fresh = sheets.length === 1 && first.getLastRow() === 0 && ['초대', '응답'].indexOf(first.getName()) < 0;
    sh = fresh ? first.setName(name) : ss.insertSheet(name);
  }
  if (sh.getLastRow() === 0) {
    sh.appendRow(header);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, header.length).setFontWeight('bold');
  }
  return sh;
}

function invites_() { return tab_('초대', INVITE_HEADER); }
function responses_() { return tab_('응답', RESP_HEADER); }

function findInvite_(code) {
  if (!/^[a-f0-9]{16}$/.test(code)) return null;
  const sh = invites_();
  const last = sh.getLastRow();
  if (last < 2) return null;
  const rows = sh.getRange(2, 1, last - 1, INVITE_HEADER.length).getValues();
  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][0]) === code) {
      return {
        row: i + 2, name: String(rows[i][1] || ''), phone: String(rows[i][2] || ''),
        email: String(rows[i][3] || ''), type: String(rows[i][4] || ''), status: String(rows[i][6] || ''),
      };
    }
  }
  return null;
}

/** '초대' 탭에서 코드가 비어 있는 줄마다 개인 신청 링크를 만들어요. 편집기에서 실행하세요. */
function makeInviteLinks() {
  const url = ScriptApp.getService().getUrl();
  if (!url) throw new Error('먼저 웹 앱으로 배포한 뒤 실행해 주세요.');
  const sh = invites_();
  const last = sh.getLastRow();
  let made = 0;
  for (let r = 2; r <= last; r++) {
    const name = String(sh.getRange(r, 2).getValue() || '').trim();
    if (!name || sh.getRange(r, 1).getValue()) continue;
    const code = Utilities.getUuid().replace(/-/g, '').slice(0, 16);
    sh.getRange(r, 1).setValue(code);
    sh.getRange(r, 6).setValue(url + '?t=' + code);
    made++;
  }
  Logger.log(made + '명의 신청 링크를 만들었어요.');
}

/* ---------- 일정 ---------- */

function slotCounts_() {
  const sh = responses_();
  const last = sh.getLastRow();
  const out = {};
  if (last < 2) return out;
  const col = RESP_HEADER.indexOf('희망 1순위') + 1;
  sh.getRange(2, col, last - 1, 1).getValues().forEach(function (r) {
    const v = String(r[0] || '').trim();
    if (v) out[v] = (out[v] || 0) + 1;
  });
  return out;
}

/** 내일부터 WEEKS_AHEAD주 동안의 촬영 가능 날짜 { 'yyyy-MM-dd': [{time, full}] } */
function getSlots() {
  const today = Utilities.formatDate(new Date(), CONFIG.TIMEZONE, 'yyyy-MM-dd').split('-').map(Number);
  const counts = slotCounts_();
  const out = {};
  for (let i = 1; i <= CONFIG.WEEKS_AHEAD * 7; i++) {
    const dt = new Date(Date.UTC(today[0], today[1] - 1, today[2] + i));
    if (CONFIG.SHOOT_WEEKDAYS.indexOf(dt.getUTCDay()) < 0) continue;
    const key = Utilities.formatDate(dt, 'UTC', 'yyyy-MM-dd');
    if (CONFIG.BLOCKED_DATES.indexOf(key) >= 0) continue;
    const exclude = (CONFIG.EXCLUDE_BY_WEEKDAY[dt.getUTCDay()] || [])
      .concat(CONFIG.EXCLUDE_BY_DATE[key] || []);
    const times = CONFIG.DATE_TIMES[key] ||
      CONFIG.TIMES.filter(function (t) { return exclude.indexOf(t) < 0; });
    if (!times.length) continue;
    out[key] = times.map(function (t) {
      return { time: t, full: (counts[key + ' ' + t] || 0) >= CONFIG.MAX_PER_SLOT };
    });
  }
  return out;
}

/* ---------- 제출 ---------- */

function clean_(v, max) {
  return String(v == null ? '' : v).replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, max || 200);
}

/**
 * 지원자 폴더 찾기. 이미 만들어 둔 폴더(예: 재활_김지영_여_31)가 있으면 반드시 그 폴더를 써요.
 * 폴더 이름의 두 번째 칸(이름)이 본명 또는 활동명과 같으면 같은 사람으로 봐요. 띄어쓰기는 무시해요.
 * 같은 이름 폴더가 없을 때만 새로 만들어요.
 */
function applicantFolder_(type, name, nick) {
  const parent = DriveApp.getFolderById(CONFIG.PARENT_FOLDER_ID);
  const norm = function (s) { return String(s || '').replace(/\s+/g, ''); };
  const wants = [norm(name), norm(nick)].filter(Boolean);
  const it = parent.getFolders();
  while (it.hasNext()) {
    const f = it.next();
    if (f.isTrashed()) continue; // 휴지통에 넣은 폴더는 건너뛰어요
    if (wants.indexOf(norm(f.getName().split('_')[1])) >= 0) return f;
  }
  return parent.createFolder((type || '모델') + '_' + name);
}

function subFolder_(folder, name) {
  const it = folder.getFoldersByName(name);
  return it.hasNext() ? it.next() : folder.createFolder(name);
}

function saveFile_(folder, f, label, name) {
  if (!f || !f.data) return '';
  const bytes = Utilities.base64Decode(String(f.data));
  if (!bytes.length || bytes.length > CONFIG.MAX_FILE_MB * 1024 * 1024) throw new Error(label + ' 파일 크기를 확인해 주세요.');
  const mime = clean_(f.mimeType, 100);
  if (!/^(image\/|application\/pdf$)/.test(mime)) throw new Error(label + '은 이미지나 PDF로 올려 주세요.');
  const ext = (clean_(f.name, 120).match(/\.[A-Za-z0-9]{1,5}$/) || [''])[0];
  return folder.createFile(Utilities.newBlob(bytes, mime, label + '_' + name + ext)).getUrl();
}

function submitApplication(form) {
  const inv = form.code ? findInvite_(String(form.code)) : null;
  if (!inv && !CONFIG.ALLOW_WITHOUT_LINK) throw new Error('개인 신청 링크로 들어와 주세요.');
  if (inv && inv.status) throw new Error('이미 신청하셨어요. 변경은 담당자에게 문의해 주세요.');

  const name = clean_(form.name, 30);
  // 010-1234-5678 형태로 맞춰 저장 (시트가 숫자로 바꿔 앞자리 0이 사라지지 않게)
  const pd = clean_(form.phone, 20).replace(/\D/g, '');
  const phone = pd.length === 11 ? pd.replace(/(\d{3})(\d{4})(\d{4})/, '$1-$2-$3')
    : pd.length === 10 ? pd.replace(/(\d{3})(\d{3})(\d{4})/, '$1-$2-$3') : pd;
  const email = clean_(form.email, 100);
  const birth = clean_(form.birth, 8).replace(/\D/g, '');
  const addr = clean_(form.addr, 200);
  const addr2 = clean_(form.addr2, 100);
  const type = inv && inv.type ? inv.type : (['재활', '발톱'].indexOf(form.type) >= 0 ? form.type : '');
  if (!name || phone.replace(/\D/g, '').length < 10 || !/^\S+@\S+\.\S+$/.test(email) ||
      !/^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$/.test(birth) || !addr) {
    throw new Error('기본 정보를 다시 확인해 주세요.');
  }
  if (!form.agreePrivacy || !form.agreeUnique) throw new Error('필수 동의 항목에 체크해 주세요.');

  const slots = getSlots();
  const valid = {};
  Object.keys(slots).forEach(function (d) { slots[d].forEach(function (t) { valid[d + ' ' + t.time] = t.full; }); });
  const picks = (form.picks || []).map(String).filter(function (p) { return p in valid; }).slice(0, CONFIG.MAX_PICKS);
  if (!picks.length) throw new Error('희망 일정을 하나 이상 골라 주세요.');
  if (!form.idCard || !form.bankBook) throw new Error('신분증 사본과 통장 사본을 첨부해 주세요.');

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    if (alreadyApplied_(phone)) {
      throw new Error('이 전화번호로 이미 신청하셨어요. 일정 변경은 담당자에게 문의해 주세요.');
    }
    if ((slotCounts_()[picks[0]] || 0) >= CONFIG.MAX_PER_SLOT) {
      throw new Error('1순위로 고른 ' + picks[0] + ' 시간이 방금 마감됐어요. 다른 시간을 골라 주세요.');
    }
    const docs = subFolder_(applicantFolder_(type, name, clean_(form.nick, 30)), '계약서류');
    const idUrl = saveFile_(docs, form.idCard, '신분증', name);
    const bankUrl = saveFile_(docs, form.bankBook, '통장', name);
    const now = Utilities.formatDate(new Date(), CONFIG.TIMEZONE, 'yyyy-MM-dd HH:mm');

    responses_().appendRow([
      now, inv ? form.code : '', type, name, clean_(form.nick, 30), phone, email,
      birth.slice(0, 4) + '-' + birth.slice(4, 6) + '-' + birth.slice(6, 8), addr, addr2,
      picks[0] || '', picks[1] || '', picks[2] || '', idUrl, bankUrl, docs.getUrl(), '동의', '동의',
    ]);
    if (inv) invites_().getRange(inv.row, 7).setValue('신청 완료 ' + now);

    notify_(type, name, picks, docs.getUrl());
    return { ok: true, name: name, picks: picks };
  } finally {
    lock.releaseLock();
  }
}

/** 같은 전화번호로 이미 접수된 신청이 있는지 */
function alreadyApplied_(phone) {
  const want = String(phone).replace(/\D/g, '');
  const sh = responses_();
  const last = sh.getLastRow();
  if (!want || last < 2) return false;
  const col = RESP_HEADER.indexOf('전화번호') + 1;
  return sh.getRange(2, col, last - 1, 1).getValues()
    .some(function (r) { return String(r[0]).replace(/\D/g, '') === want; });
}

function notify_(type, name, picks, folderUrl) {
  if (CONFIG.NOTIFY_EMAIL === 'off') return;
  const to = CONFIG.NOTIFY_EMAIL || Session.getEffectiveUser().getEmail();
  if (!to) return;
  MailApp.sendEmail({
    to: to,
    subject: '[촬영 일정 신청] ' + (type ? type + ' · ' : '') + name,
    body: name + ' 님이 촬영 일정을 신청했어요.\n\n희망 일정: ' + picks.join(' / ') + '\n서류 폴더: ' + folderUrl,
  });
}

/** 처음 한 번 편집기에서 실행: 권한 승인 + 시트(응답·초대 탭) 만들기 */
function setup() {
  responses_(); // 첫 번째 탭이 '응답'이어야 대시보드가 바로 읽어요
  invites_();
  Logger.log('시트: ' + book_().getUrl());
}
