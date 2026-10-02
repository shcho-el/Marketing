// 회식 장소 투표 — 누구나 링크로 투표하는 공개 버전.
// 이 스크립트가 붙은 Google 시트의 "votes" 탭에 한 사람당 한 줄로 저장합니다.

const DEADLINE = new Date('2026-10-02T21:00:00+09:00').getTime();
const PLACES = {
  q1: { gudoro: '구도로통닭 종각점', hoo: '청계천 휴 (HOO)', hansabal: '한사발포차 종각점' },
  q2: { mido: '미도갈비', gogikkun: '고기꾼 김춘배 종로점', daechan: '대찬횟집 종각점', daenamu: '대나무숙성회관 종각점', insaeng: '인생횟집 종각본점' },
};
const HEADER = ['이름', '1차', '2차', '남길 말', '저장 시각'];

// ?action=list → JSON (GitHub Pages 버전이 호출). 그 외 → 투표 페이지 자체.
function doGet(e) {
  if (e && e.parameter && e.parameter.action === 'list') return json_({ ok: true, votes: getVotes() });
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('회식 장소, 당신의 선택은?')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName('votes');
  if (!sh) {
    sh = ss.insertSheet('votes');
    sh.appendRow(HEADER);
    sh.setFrozenRows(1);
  }
  return sh;
}

function idOf_(q, name) {
  const map = PLACES[q];
  return Object.keys(map).find(k => map[k] === name) || '';
}

// 시트 수식으로 해석되지 않도록 사용자가 입력한 글자를 그대로 저장
function plain_(s) {
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function getVotes() {
  const sh = sheet_();
  const n = sh.getLastRow();
  if (n < 2) return [];
  return sh.getRange(2, 1, n - 1, 5).getValues()
    .filter(r => String(r[0]).trim())
    .map(r => ({
      name: String(r[0]).trim(),
      q1: idOf_('q1', String(r[1])),
      q2: idOf_('q2', String(r[2])),
      note: String(r[3] || ''),
      updatedAt: r[4] instanceof Date ? r[4].getTime() : 0,
    }));
}

function submitVote(v) {
  if (Date.now() > DEADLINE) throw new Error('closed');
  const name = String((v && v.name) || '').trim().slice(0, 20);
  if (!name) throw new Error('name');
  if (!PLACES.q1[v.q1] || !PLACES.q2[v.q2]) throw new Error('choice');
  const note = String(v.note || '').trim().slice(0, 300);
  const row = [plain_(name), PLACES.q1[v.q1], PLACES.q2[v.q2], plain_(note), new Date()];

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sh = sheet_();
    const n = sh.getLastRow();
    const names = n > 1 ? sh.getRange(2, 1, n - 1, 1).getValues().map(r => String(r[0]).replace(/^'/, '').trim()) : [];
    const i = names.indexOf(name);
    if (i >= 0) sh.getRange(i + 2, 1, 1, 5).setValues([row]);
    else sh.appendRow(row);
  } finally {
    lock.releaseLock();
  }
  return getVotes();
}

// GitHub Pages 버전의 투표 제출 (본문: JSON 문자열)
function doPost(e) {
  try {
    const v = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    return json_({ ok: true, votes: submitVote(v) });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
