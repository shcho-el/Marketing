# 오블리브 네이버 키워드 순위 모니터링

네이버 블로그 검색 결과에서 **오블리브**가 포함된 콘텐츠의 순위를 매일 자동 수집하고 웹 대시보드로 시각화합니다.

## 모니터링 키워드

| 키워드 |
|--------|
| 송도내성발톱 |
| 인천내성발톱 |
| 인천문제성발톱 |
| 송도문제성발톱 |
| 인천내성발톱병원 |
| 인천발톱무좀 |
| 송도발톱무좀 |
| 문제성발톱병원 |
| 문제성발톱 |

## 설치

```bash
pip install -r requirements.txt
```

## 실행

### 즉시 1회 수집
```bash
python main.py collect
```

### 매일 자동 수집 (기본 오전 9시)
```bash
python main.py scheduler
```

### 웹 대시보드 (http://localhost:5000)
```bash
python main.py dashboard
```

### 스케줄러 + 대시보드 동시 실행
```bash
python main.py all
```

## 설정 변경

`config.py` 수정:

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `SEARCH_DEPTH` | 30 | 상위 몇 위까지 확인할지 |
| `SCHEDULE_TIME` | `"09:00"` | 매일 수집 시각 |
| `REQUEST_DELAY` | 2.0초 | 요청 간 딜레이 |
| `DASHBOARD_PORT` | 5000 | 대시보드 포트 |

## 데이터 저장

SQLite (`rankings.db`)에 날짜·키워드·순위가 누적 저장됩니다.

## 대시보드 색상 기준

| 색상 | 순위 |
|------|------|
| 초록 | 1~3위 |
| 파랑 | 4~5위 |
| 노랑 | 6~10위 |
| 빨강 | 11위 이상 |
| 회색 | 미노출 (상위 30위 밖) |

---

## 콘텐츠 자동 생성기

의료법을 지키면서 SEO·AEO·GEO에 최적화된 블로그 글을 생성합니다.

```bash
python main.py auto "제목"  # 제목만 넣으면 생성→검사→썸네일→업로드까지
python main.py content    # 웹 앱 (http://localhost:5001)
```

- 제목만 넣으면 카테고리·주키워드 추론부터 CMS 업로드까지 한 번에
- 생성 → 의료법 26개 규칙 검사 → 포지셔닝 검사 → SEO/AEO/GEO 채점 → 미달 시 자동 재작성
- 본원이 시행하지 않는 시술을 언급하면 업로드 차단 (허위광고 방지)
- CMS 기본정보 필드(MetaTitle 40자·MetaDescription 80자 등)를 그대로 출력
- 부작용 고지·JSON-LD 구조화 데이터 자동 삽입
- `/lint`에서 기존 원고의 의료법 위반 표현 점검
- CMS 자동 업로드 (썸네일 자동 생성, 기본 미노출 저장)

```bash
python main.py inspect-cms   # CMS 폼 구조 분석 (최초 1회)
python main.py publish <id>  # 업로드 (기본: 연습 실행)
```

### 로컬에서 실행하기

**윈도우** — `start.bat` 더블클릭

**맥 / 리눅스** — 터미널에서 `./start.sh`

처음 실행하면 가상환경 생성 → 패키지 설치 → `.env` 생성 → 환경 점검을 거쳐
브라우저가 자동으로 열립니다. 두 번째부터는 바로 뜹니다.

문제가 있으면 `python main.py doctor`로 무엇이 빠졌는지 확인하세요.

자세한 내용은 [CONTENT.md](CONTENT.md)를 참고하세요.
