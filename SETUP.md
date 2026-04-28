# 네이버 블로그 키워드 순위 모니터링 시스템

네이버 블로그 탭 관련도순 기준으로 지정 키워드의 상위 20위 순위를 매일 자동 수집하여 슬랙으로 알림합니다.

---

## 구성 파일

```
marketing/
├── config.py          # 키워드·URL·설정 (여기만 수정하면 됨)
├── scraper.py         # Selenium 기반 네이버 블로그 탭 스크래퍼
├── database.py        # SQLite 순위 이력 저장
├── notifier.py        # 슬랙 Webhook 전송
├── scheduler.py       # 평일 자동 실행 스케줄러
├── main.py            # 진입점 (collect / scheduler / dashboard)
├── test_rank.py       # 키워드별 순위 디버그 출력
├── debug_scraper.py   # HTML 구조 및 링크 진단 도구
├── rankings.db        # SQLite DB (자동 생성)
└── logs/
    └── collect.log    # 실행 로그
```

---

## 1. 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.11 이상 |
| Google Chrome | 최신 버전 (자동 감지) |
| OS | Windows 10/11 권장 |

### 패키지 설치

```powershell
pip install selenium webdriver-manager beautifulsoup4 requests schedule python-dotenv
```

---

## 2. 환경변수 설정 (.env)

프로젝트 루트에 `.env` 파일 생성:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

슬랙 Webhook URL 발급: Slack → 앱 관리 → Incoming Webhooks → 새 Webhook 추가

---

## 3. config.py 설정

### 모니터링 키워드

```python
KEYWORDS = [
    "송도내성발톱",
    "인천내성발톱",
    # 추가할 키워드 계속 작성
]
```

### 우리 브랜드 블로그 포스트 URL 목록

```python
TARGET_URLS = [
    "https://blog.naver.com/아이디/포스트번호",
    # ...
]
```

> URL 형식은 반드시 `https://blog.naver.com/아이디/포스트번호` 형식으로 작성.  
> `m.blog.naver.com` 또는 `PostView.naver` 형식도 자동 정규화됨.

### 경쟁사 제외 키워드

```python
EXCLUDE_KEYWORDS = [
    "경쟁사명1",
    "경쟁사명2",
]
```

포스트 제목·설명에 이 단어가 포함되면 우리 브랜드로 매칭하지 않음.

### 주요 설정값

```python
SEARCH_DEPTH = 20       # 상위 몇 위까지 확인할지
SCHEDULE_TIME = "08:20" # 자동 수집 시각 (24시간)
TARGET_BRAND = "브랜드명" # 슬랙·DB 표시용
```

---

## 4. 수동 실행

```powershell
cd C:\Users\medib\marketing

# 즉시 1회 수집 + 슬랙 전송
python main.py collect

# 키워드 하나만 디버그 (순위 출력, 슬랙 전송 없음)
python test_rank.py 송도내성발톱 20
```

---

## 5. Windows 자동화 (Task Scheduler)

평일(월~금) 오전 8:20에 자동 실행하도록 등록합니다.

**관리자 PowerShell**에서 실행:

```powershell
Unregister-ScheduledTask -TaskName "NaverBlogRankCollect" -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "C:\Users\medib\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
    -Argument "main.py collect" `
    -WorkingDirectory "C:\Users\medib\marketing"

$trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "08:20AM"

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "NaverBlogRankCollect" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force
```

> Python 경로와 WorkingDirectory는 실제 환경에 맞게 수정하세요.

### 즉시 테스트

```powershell
Start-ScheduledTask -TaskName "NaverBlogRankCollect"
```

### 실행 결과 확인

```powershell
Get-ScheduledTaskInfo -TaskName "NaverBlogRankCollect"
# LastTaskResult: 0 = 성공, 1 = 실패

cat C:\Users\medib\marketing\logs\collect.log
```

---

## 6. 슬랙 알림 형식

```
📊 오블리브 네이버 블로그 순위 (2026년 04월 21일)

🥉  `송도내성발톱`  →  *3위*
🟢  `인천내성발톱`  →  *4위, 7위*
⬜  `인천발톱무좀`  →  *미노출*

네이버 블로그 탭 기준 상위 20위 · 오블리브
```

| 이모지 | 의미 |
|--------|------|
| 🥇🥈🥉 | 1·2·3위 |
| 🟢 | 4~5위 |
| 🟡 | 6~10위 |
| 🔴 | 11위 이상 |
| ⬜ | 미노출 (20위 밖) |

---

## 7. 순위 측정 기준

- **기준**: 네이버 블로그 탭 → 관련도순 (기본값, 일반 사용자가 보는 화면과 동일)
- **측정 범위**: 상위 20위
- **매칭 방식**: `TARGET_URLS`에 등록된 URL이 검색결과에 나타나면 해당 순위로 기록
- **제외 조건**: 포스트 제목·설명에 `EXCLUDE_KEYWORDS` 단어가 있으면 경쟁사로 간주하여 제외
- **비로그인 기준**: 헤드리스 Chrome으로 수집하므로 개인화 없는 순위

---

## 8. 문제 해결

### 미노출로만 뜨는 경우

```powershell
python debug_scraper.py 송도내성발톱
```

출력에서 확인:
- `li.bx` / `Selenium DOM: blog.naver.com 포함 링크` 항목에 포스트 링크가 있는지 확인
- 없으면 네이버 봇 차단 가능성 → `REQUEST_DELAY` 값을 늘려보세요 (config.py)

### Task Scheduler 실패 (LastTaskResult: 1)

1. Python 경로가 맞는지 확인: `where python`
2. 로그 확인: `cat logs\collect.log`
3. 직접 실행해서 에러 확인: `python main.py collect`

### 키워드 추가

`config.py`의 `KEYWORDS` 리스트에 키워드 추가 후 저장.

### 포스트 URL 추가

`config.py`의 `TARGET_URLS` 리스트에 URL 추가 후 저장.

---

## 9. 코드 업데이트 반영

```powershell
cd C:\Users\medib\marketing
git pull origin claude/keyword-ranking-monitor-utCwV
```
