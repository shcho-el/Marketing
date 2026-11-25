/**
 * 눈썹 리얼모델 지원서 접수용 Google Apps Script
 *
 * 설치 방법
 *  1) 접수용 Google 스프레드시트 생성 → 확장 프로그램 > Apps Script
 *  2) 이 코드를 붙여넣고 FOLDER_ID 에 사진 저장용 드라이브 폴더 ID 입력
 *  3) 배포 > 새 배포 > 유형: 웹 앱
 *       - 실행 사용자: 나
 *       - 액세스 권한: 모든 사용자
 *  4) 발급된 웹 앱 URL 을 eyebrow-model.html 의 FORM_ENDPOINT 에 입력
 */
const FOLDER_ID = '여기에_드라이브_폴더_ID';
const SHEET_NAME = '눈썹모델_지원';

const HEADERS = ['접수일시', '이름', '생년월일', '연락처', '이메일', '인스타그램', '희망지역', '지원경로',
  '눈썹시술이력', '어필', '촬영물활용동의', '정면', '45도', '90도', '셀카1', '셀카2', '셀카3', '사진폴더'];
const PHOTO_KEYS = ['photo_front', 'photo_45', 'photo_90', 'selfie_1', 'selfie_2', 'selfie_3'];
const PHOTO_LABELS = ['정면', '45도', '90도', '셀카1', '셀카2', '셀카3'];

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const d = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sh.getLastRow() === 0) sh.appendRow(HEADERS).setFrozenRows(1);

    const stamp = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyyMMdd_HHmmss');
    const folder = DriveApp.getFolderById(FOLDER_ID).createFolder(`${stamp}_${d.name}_@${d.instagram}`);

    const links = PHOTO_KEYS.map((k, i) => {
      const dataUrl = d.photos && d.photos[k];
      if (!dataUrl) return '';
      const bytes = Utilities.base64Decode(dataUrl.split(',')[1]);
      const file = folder.createFile(Utilities.newBlob(bytes, 'image/jpeg', `${PHOTO_LABELS[i]}.jpg`));
      return file.getUrl();
    });

    sh.appendRow([
      Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm'),
      d.name, "'" + d.birth, "'" + d.phone, d.email, '@' + d.instagram, d.region, d.channel,
      d.brow_history, d.appeal, d.agree_media === 'Y' ? '동의' : '', ...links, folder.getUrl(),
    ]);
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
